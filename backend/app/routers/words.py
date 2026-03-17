from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Definition, Derivation, Etymology, RelatedWord, Word
from app.schemas import (
    BulkWordRequest,
    DefinitionRead,
    DerivationCreate,
    DerivationRead,
    DerivationUpdate,
    DefinitionUpdate,
    EtymologyComponentSearchResponse,
    EtymologyRead,
    EtymologyUpdate,
    RelatedWordCreate,
    RelatedWordRead,
    RelatedWordUpdate,
    WordCreateRequest,
    WordFullUpdate,
    WordListResponse,
    WordRead,
)
from app.services.gpt_service import enrich_core_image_and_branches, generate_structured_word_data
from app.services.etymology_component_service import get_component_cache, normalize_component_text
from app.services.scraper import build_scrapers
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services import word_service
from app.services.word_ingest_service import ingest_word_or_phrase
from app.services.wordnet_service import get_wordnet_snapshot
from app.scripts.updaters import (
    _enrich_phrase_and_related_meanings,
    _normalize_structured_derivations_and_phrases,
    _normalize_structured_forms,
)
from app.utils.pos_labels import normalize_part_of_speech

router = APIRouter(prefix="/api/words", tags=["words"])


WordSortBy = Literal["last_viewed_at", "created_at", "updated_at", "word"]
SortOrder = Literal["desc", "asc"]


def _word_query():
    return select(Word).options(
        joinedload(Word.definitions),
        joinedload(Word.etymology).joinedload(Etymology.component_items),
        joinedload(Word.derivations),
        joinedload(Word.related_words),
        joinedload(Word.images),
        joinedload(Word.chat_sessions),
    )


def _resolve_component_link(db: Session, component: dict) -> tuple[int | None, bool]:
    return word_service.resolve_component_link(db, component)


def _to_word_read(db: Session, word: Word) -> WordRead:
    return word_service.to_word_read(db, word)


def _apply_structured_payload(db: Session, word: Word, payload: dict) -> None:
    word_service.apply_structured_payload(db, word, payload)


def _replace_definitions(word: Word, definitions: list[dict]) -> None:
    word_service.replace_definitions(word, definitions)


def _split_comma_items(text: str) -> list[str]:
    return word_service.split_comma_items(text)


def _replace_derivations(db: Session, word: Word, derivations: list[dict]) -> None:
    word_service.replace_derivations(db, word, derivations)


def _replace_related_words(db: Session, word: Word, related_words: list[dict]) -> None:
    word_service.replace_related_words(db, word, related_words)


def _link_related_words(db: Session, word: Word) -> None:
    word_service.link_related_words(db, word)


def _link_derivations(db: Session, word: Word) -> None:
    word_service.link_derivations(db, word)


def _has_etymology_component(word: Word, component_text: str) -> bool:
    return word_service.has_etymology_component(word, component_text)


def _resolve_component_meaning(words: list[Word], component_text: str) -> str | None:
    return word_service.resolve_component_meaning(words, component_text)


def _aggregate_related_words(words: list[Word]) -> list[dict]:
    return word_service.aggregate_related_words(words)


def _aggregate_derivations(words: list[Word]) -> list[dict]:
    return word_service.aggregate_derivations(words)


def _core_image_is_generic(word_text: str, core_image: object) -> bool:
    value = str(core_image or "").strip()
    if not value:
        return True
    generic_patterns = {
        f"{word_text}: central concept",
        f"core image for {word_text}",
        f"etymology for {word_text}",
    }
    return value.lower() in {pattern.lower() for pattern in generic_patterns}


def _needs_etymology_enrichment(word_text: str, structured: dict) -> bool:
    ety = structured.get("etymology")
    if not isinstance(ety, dict):
        return False
    core_image = ety.get("core_image")
    branches = ety.get("branches")
    has_branches = isinstance(branches, list) and len(branches) > 0
    return _core_image_is_generic(word_text, core_image) or not has_branches


def _apply_enriched_etymology(structured: dict, enriched: dict | None) -> dict:
    if not enriched:
        return structured
    ety = structured.setdefault("etymology", {})
    if not isinstance(ety, dict):
        return structured
    core_image = str(enriched.get("core_image", "")).strip()
    branches = enriched.get("branches")
    if core_image:
        ety["core_image"] = core_image
    if isinstance(branches, list) and branches:
        ety["branches"] = branches
    return structured


def _word_sort_clauses(sort_by: WordSortBy, sort_order: SortOrder):
    direction = sort_order == "asc"
    if sort_by == "word":
        primary = func.lower(Word.word).asc() if direction else func.lower(Word.word).desc()
    elif sort_by == "created_at":
        primary = Word.created_at.asc() if direction else Word.created_at.desc()
    elif sort_by == "updated_at":
        primary = Word.updated_at.asc() if direction else Word.updated_at.desc()
    else:
        # 未閲覧(null)が混ざっても末尾に揃える。
        primary = Word.last_viewed_at.asc().nullslast() if direction else Word.last_viewed_at.desc().nullslast()

    tie_breaker = Word.id.asc() if direction else Word.id.desc()
    return [primary, tie_breaker]


async def _scrape_all(word: str) -> list[dict]:
    scrapers = build_scrapers()
    tasks = [scraper.scrape(word) for scraper in scrapers]
    return list(await asyncio.gather(*tasks))


@router.get("", response_model=WordListResponse)
def list_words(
    q: str | None = Query(default=None),
    sort_by: WordSortBy = Query(default="last_viewed_at"),
    sort_order: SortOrder = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> WordListResponse:
    sort_clauses = _word_sort_clauses(sort_by, sort_order)
    stmt = _word_query().order_by(*sort_clauses)
    if q:
        raw = q.strip()
        # Support Japanese comma "、" and regular commas/spaces.
        tokens = [t.strip() for t in raw.replace("、", ",").split(",")]
        keywords = [t for token in tokens for t in token.split() if t]
        if not keywords:
            keywords = [raw]

        def _definition_matches(text: str):
            pat = f"%{text}%"
            return exists(
                select(1)
                .select_from(Definition)
                .where(Definition.word_id == Word.id)
                .where(
                    or_(
                        Definition.meaning_ja.ilike(pat),
                        Definition.meaning_en.ilike(pat),
                        Definition.example_en.ilike(pat),
                        Definition.example_ja.ilike(pat),
                    )
                )
            )

        predicates = []
        for kw in keywords:
            pat = f"%{kw}%"
            predicates.append(or_(Word.word.ilike(pat), _definition_matches(kw)))

        stmt = stmt.where(or_(*predicates)).order_by(
            # Keep "starts with" boost for English word matches only.
            or_(*[Word.word.ilike(f"{kw}%") for kw in keywords]).desc(),
            *sort_clauses,
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique())
    return WordListResponse(items=[_to_word_read(db, x) for x in items], total=total)


@router.get("/suggest", response_model=list[str])
def suggest_words(
    q: str = Query(default="", min_length=0),
    limit: int = Query(default=10, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[str]:
    keyword = q.strip()
    if not keyword:
        return []
    # 先頭一致を優先し、続いて部分一致。同一条件内は last_viewed_at, updated_at でソート。
    prefix_first = Word.word.ilike(f"{keyword}%")
    stmt = (
        select(Word.word)
        .where(Word.word.ilike(f"%{keyword}%"))
        .order_by(prefix_first.desc(), Word.last_viewed_at.desc(), Word.updated_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.get("/by-text/{word_text}", response_model=WordRead)
def get_word_by_text(word_text: str, db: Session = Depends(get_db)) -> WordRead:
    normalized = word_text.strip().lower()
    word = db.scalar(_word_query().where(func.lower(Word.word) == normalized))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    word.last_viewed_at = datetime.utcnow()
    db.commit()
    db.refresh(word)
    return _to_word_read(db, word)


@router.get("/by-etymology-component", response_model=EtymologyComponentSearchResponse)
async def list_words_by_etymology_component(
    text: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> EtymologyComponentSearchResponse:
    normalized_text = normalize_component_text(text)
    if not normalized_text:
        raise HTTPException(status_code=400, detail="text is required")
    words = list(db.scalars(_word_query().order_by(Word.updated_at.desc())).unique())
    filtered = [word for word in words if _has_etymology_component(word, normalized_text)]
    resolved_meaning = _resolve_component_meaning(filtered, normalized_text)
    component_cache = get_component_cache(db, normalized_text)
    if component_cache and component_cache.resolved_meaning != resolved_meaning:
        component_cache.resolved_meaning = resolved_meaning
        db.commit()
        db.refresh(component_cache)
    aggregated_related_words = _aggregate_related_words(filtered)
    aggregated_derivations = _aggregate_derivations(filtered)
    total = len(filtered)
    start = (page - 1) * page_size
    items = filtered[start : start + page_size]
    return EtymologyComponentSearchResponse(
        component_text=normalized_text,
        resolved_meaning=(component_cache.resolved_meaning if component_cache else resolved_meaning),
        wiktionary={
            "meanings": (component_cache.wiktionary_meanings if component_cache else []) or [],
            "related_terms": (component_cache.wiktionary_related_terms if component_cache else []) or [],
            "derived_terms": (component_cache.wiktionary_derived_terms if component_cache else []) or [],
            "source_url": component_cache.wiktionary_source_url if component_cache else None,
        },
        aggregated={
            "related_words": aggregated_related_words,
            "derivations": aggregated_derivations,
        },
        items=[_to_word_read(db, x) for x in items],
        total=total,
    )


@router.get("/{word_id}", response_model=WordRead)
def get_word(word_id: int, db: Session = Depends(get_db)) -> WordRead:
    word = db.scalar(_word_query().where(Word.id == word_id))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    word.last_viewed_at = datetime.utcnow()
    db.commit()
    db.refresh(word)
    return _to_word_read(db, word)


@router.post("", response_model=list[WordRead])
async def create_word(payload: WordCreateRequest, db: Session = Depends(get_db)) -> list[WordRead]:
    try:
        result = await ingest_word_or_phrase(
            db,
            payload.word,
            scraper=WiktionaryScraper(),
            payload_cache={},
            meaning_cache={},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    for word in result.words:
        db.refresh(word)
    return [_to_word_read(db, word) for word in result.words]


@router.post("/bulk", response_model=list[WordRead])
async def bulk_create_words(payload: BulkWordRequest, db: Session = Depends(get_db)) -> list[WordRead]:
    scraper = WiktionaryScraper()
    payload_cache: dict[str, dict] = {}
    meaning_cache: dict[str, str | None] = {}
    result_words: dict[int, Word] = {}
    for item in payload.words:
        if not item.strip():
            continue
        result = await ingest_word_or_phrase(
            db,
            item,
            scraper=scraper,
            payload_cache=payload_cache,
            meaning_cache=meaning_cache,
        )
        for word in result.words:
            result_words[word.id] = word
    db.commit()
    words = list(result_words.values())
    for word in words:
        db.refresh(word)
    return [_to_word_read(db, word) for word in words]


@router.put("/{word_id}", response_model=WordRead)
def update_word(word_id: int, payload: WordCreateRequest, db: Session = Depends(get_db)) -> WordRead:
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    word.word = payload.word.strip().lower()
    db.commit()
    db.refresh(word)
    return _to_word_read(db, word)


@router.delete("/{word_id}")
def delete_word(word_id: int, db: Session = Depends(get_db)) -> dict:
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    db.delete(word)
    db.commit()
    return {"ok": True}


@router.post("/{word_id}/rescrape", response_model=WordRead)
async def rescrape_word(word_id: int, db: Session = Depends(get_db)) -> WordRead:
    word = db.scalar(_word_query().where(Word.id == word_id))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    wordnet_data = get_wordnet_snapshot(word.word)
    scraped_data = await _scrape_all(word.word)
    structured = generate_structured_word_data(word.word, wordnet_data, scraped_data)
    if _needs_etymology_enrichment(word.word, structured):
        enriched = enrich_core_image_and_branches(
            word_text=word.word,
            definitions=structured.get("definitions", []),
            etymology_data=structured.get("etymology", {}),
        )
        structured = _apply_enriched_etymology(structured, enriched)
    structured = _normalize_structured_forms(structured)
    structured = _normalize_structured_derivations_and_phrases(structured)
    await _enrich_phrase_and_related_meanings(structured, WiktionaryScraper(), {})
    _apply_structured_payload(db, word, structured)
    db.commit()
    db.refresh(word)
    return _to_word_read(db, word)


@router.post("/{word_id}/enrich-etymology", response_model=EtymologyRead)
def enrich_etymology(word_id: int, db: Session = Depends(get_db)) -> EtymologyRead:
    word = db.scalar(_word_query().where(Word.id == word_id))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    if not word.etymology:
        word.etymology = Etymology(word_id=word.id)
        db.flush()

    etymology_payload = word_service.build_etymology_enrich_payload(word.etymology)
    definition_payload = [
        {
            "part_of_speech": definition.part_of_speech,
            "meaning_en": definition.meaning_en,
            "meaning_ja": definition.meaning_ja,
            "example_en": definition.example_en,
            "example_ja": definition.example_ja,
        }
        for definition in word.definitions
    ]
    enriched = enrich_core_image_and_branches(
        word_text=word.word,
        definitions=definition_payload,
        etymology_data=etymology_payload,
    )
    if enriched:
        core_image = str(enriched.get("core_image", "")).strip()
        branches = enriched.get("branches")
        if core_image:
            word.etymology.core_image = core_image
        if isinstance(branches, list) and branches:
            word_service._apply_etymology_branches(word.etymology, branches)

    db.commit()
    db.refresh(word.etymology)
    ety_data = word_service._build_etymology_read(db, word.etymology)
    return EtymologyRead.model_validate(ety_data)


@router.put("/{word_id}/definitions/{def_id}", response_model=DefinitionRead)
def update_definition(
    word_id: int,
    def_id: int,
    payload: DefinitionUpdate,
    db: Session = Depends(get_db),
) -> DefinitionRead:
    definition = db.get(Definition, def_id)
    if not definition or definition.word_id != word_id:
        raise HTTPException(status_code=404, detail="Definition not found")
    for key, value in payload.model_dump().items():
        if key == "part_of_speech":
            setattr(definition, key, normalize_part_of_speech(value))
        else:
            setattr(definition, key, value)
    db.commit()
    db.refresh(definition)
    return DefinitionRead.model_validate(definition)


@router.put("/{word_id}/full", response_model=WordRead)
def update_word_full(word_id: int, payload: WordFullUpdate, db: Session = Depends(get_db)) -> WordRead:
    word = db.scalar(_word_query().where(Word.id == word_id))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    if payload.word is not None:
        word.word = payload.word.strip().lower()
    word.phonetic = payload.phonetic
    word.forms = payload.forms or {}

    _replace_definitions(word, [item.model_dump() for item in payload.definitions])
    if payload.etymology is not None:
        if not word.etymology:
            word.etymology = Etymology()
        word_service.apply_etymology_update(db, word.etymology, payload.etymology.model_dump())
    _replace_derivations(db, word, [item.model_dump() for item in payload.derivations])
    _replace_related_words(db, word, [item.model_dump() for item in payload.related_words])

    db.commit()
    db.refresh(word)
    return _to_word_read(db, word)


@router.put("/{word_id}/etymology", response_model=EtymologyRead)
def update_etymology(word_id: int, payload: EtymologyUpdate, db: Session = Depends(get_db)) -> EtymologyRead:
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    if not word.etymology:
        word.etymology = Etymology(word_id=word.id)
    word_service.apply_etymology_update(db, word.etymology, payload.model_dump())
    db.commit()
    db.refresh(word.etymology)
    return EtymologyRead.model_validate(word.etymology)


@router.post("/{word_id}/derivations", response_model=DerivationRead)
def create_derivation(word_id: int, payload: DerivationCreate, db: Session = Depends(get_db)) -> DerivationRead:
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    split_words = _split_comma_items(payload.derived_word)
    if not split_words:
        raise HTTPException(status_code=400, detail="derived_word is required")
    created_items: list[Derivation] = []
    for derived_word in split_words:
        item = Derivation(
            word_id=word_id,
            derived_word=derived_word,
            part_of_speech=normalize_part_of_speech(payload.part_of_speech),
            meaning_ja=payload.meaning_ja,
            sort_order=payload.sort_order,
        )
        db.add(item)
        created_items.append(item)
    db.flush()
    _link_derivations(db, word)
    db.commit()
    db.refresh(created_items[0])
    return DerivationRead.model_validate(created_items[0])


@router.put("/{word_id}/derivations/{der_id}", response_model=DerivationRead)
def update_derivation(
    word_id: int,
    der_id: int,
    payload: DerivationUpdate,
    db: Session = Depends(get_db),
) -> DerivationRead:
    derivation = db.get(Derivation, der_id)
    word = db.get(Word, word_id)
    if not derivation or derivation.word_id != word_id:
        raise HTTPException(status_code=404, detail="Derivation not found")
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    split_words = _split_comma_items(payload.derived_word)
    if not split_words:
        raise HTTPException(status_code=400, detail="derived_word is required")
    derivation.derived_word = split_words[0]
    derivation.part_of_speech = normalize_part_of_speech(payload.part_of_speech)
    derivation.meaning_ja = payload.meaning_ja
    derivation.sort_order = payload.sort_order
    for extra_word in split_words[1:]:
        db.add(
            Derivation(
                word_id=word_id,
                derived_word=extra_word,
                part_of_speech=normalize_part_of_speech(payload.part_of_speech),
                meaning_ja=payload.meaning_ja,
                sort_order=payload.sort_order,
            )
        )
    db.flush()
    _link_derivations(db, word)
    db.commit()
    db.refresh(derivation)
    return DerivationRead.model_validate(derivation)


@router.delete("/{word_id}/derivations/{der_id}")
def delete_derivation(word_id: int, der_id: int, db: Session = Depends(get_db)) -> dict:
    derivation = db.get(Derivation, der_id)
    if not derivation or derivation.word_id != word_id:
        raise HTTPException(status_code=404, detail="Derivation not found")
    db.delete(derivation)
    db.commit()
    return {"ok": True}


@router.post("/{word_id}/related-words", response_model=RelatedWordRead)
def create_related_word(word_id: int, payload: RelatedWordCreate, db: Session = Depends(get_db)) -> RelatedWordRead:
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    split_words = _split_comma_items(payload.related_word)
    if not split_words:
        raise HTTPException(status_code=400, detail="related_word is required")
    created_items: list[RelatedWord] = []
    for related_word in split_words:
        item = RelatedWord(
            word_id=word_id,
            related_word=related_word,
            relation_type=payload.relation_type,
            note=payload.note,
        )
        db.add(item)
        created_items.append(item)
    db.flush()
    _link_related_words(db, word)
    db.commit()
    db.refresh(created_items[0])
    return RelatedWordRead.model_validate(created_items[0])


@router.put("/{word_id}/related-words/{rel_id}", response_model=RelatedWordRead)
def update_related_word(
    word_id: int,
    rel_id: int,
    payload: RelatedWordUpdate,
    db: Session = Depends(get_db),
) -> RelatedWordRead:
    rel = db.get(RelatedWord, rel_id)
    word = db.get(Word, word_id)
    if not word or not rel or rel.word_id != word_id:
        raise HTTPException(status_code=404, detail="Related word not found")
    split_words = _split_comma_items(payload.related_word)
    if not split_words:
        raise HTTPException(status_code=400, detail="related_word is required")
    rel.related_word = split_words[0]
    rel.relation_type = payload.relation_type
    rel.note = payload.note
    for extra_word in split_words[1:]:
        db.add(
            RelatedWord(
                word_id=word_id,
                related_word=extra_word,
                relation_type=payload.relation_type,
                note=payload.note,
            )
        )
    db.flush()
    _link_related_words(db, word)
    db.commit()
    db.refresh(rel)
    return RelatedWordRead.model_validate(rel)


@router.delete("/{word_id}/related-words/{rel_id}")
def delete_related_word(word_id: int, rel_id: int, db: Session = Depends(get_db)) -> dict:
    rel = db.get(RelatedWord, rel_id)
    if not rel or rel.word_id != word_id:
        raise HTTPException(status_code=404, detail="Related word not found")
    db.delete(rel)
    db.commit()
    return {"ok": True}
