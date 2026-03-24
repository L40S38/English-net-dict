from __future__ import annotations

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
    DefinitionUpdate,
    DerivationCreate,
    DerivationRead,
    DerivationUpdate,
    EtymologyComponentSearchResponse,
    EtymologyRead,
    EtymologyUpdate,
    InflectionCheckRequest,
    InflectionCheckResponse,
    InflectionCheckResult,
    RelatedWordCreate,
    RelatedWordRead,
    RelatedWordUpdate,
    WordCheckFound,
    WordCheckResponse,
    WordCreateRequest,
    WordFullUpdate,
    WordListResponse,
    WordRead,
)
from app.services import word_service
from app.services.etymology_component_service import get_component_cache, normalize_component_text
from app.services.lemma_service import (
    detect_lemma,
    detect_lemma_candidates,
    detect_word_has_own_content,
    suggest_inflection_action,
)
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.spelling_suggestions import build_spellchecker, collect_spelling_suggestions
from app.services.word_ingest_service import IngestOptions, ingest_word_or_phrase
from app.services.word_merge_service import link_to_lemma, merge_into_lemma
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
        joinedload(Word.phrases),
        joinedload(Word.lemma_ref),
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


def _serialize_lemma_candidates(candidates: list) -> list[dict]:
    return [
        {
            "lemma": item.lemma_word,
            "lemma_word_id": item.lemma_word_id,
            "inflection_type": item.inflection_type,
            "has_own_content": item.has_own_content,
            "confidence": item.confidence,
            "source": item.source,
            "score": item.score,
        }
        for item in candidates
    ]


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


@router.get("", response_model=WordListResponse)
def list_words(
    q: str | None = Query(default=None),
    sort_by: WordSortBy = Query(default="last_viewed_at"),
    sort_order: SortOrder = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> WordListResponse:
    sort_clauses = word_service.word_sort_clauses(sort_by, sort_order)
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
async def create_word(
    payload: WordCreateRequest,
    llm_mode: Literal["sync", "async"] = Query("async"),
    phrase_enrich_mode: Literal["sequential", "parallel"] = Query("parallel"),
    example_mode: Literal["sequential", "parallel_thread", "parallel_async"] = Query("parallel_async"),
    phrase_parallelism: int = Query(8, ge=1, le=32),
    db: Session = Depends(get_db),
) -> list[WordRead]:
    options = IngestOptions(
        llm_mode=llm_mode,
        phrase_enrich_mode=phrase_enrich_mode,
        example_mode=example_mode,
        phrase_parallelism=phrase_parallelism,
    )
    payload_cache: dict[str, dict] = {}
    meaning_cache: dict[str, str | None] = {}
    scraper = WiktionaryScraper()
    action = payload.inflection_action
    input_word = payload.word.strip()
    if not input_word:
        raise HTTPException(status_code=400, detail="word is required")
    try:
        if action == "merge":
            lemma_target = (payload.lemma_word or input_word).strip()
            if not lemma_target:
                raise HTTPException(status_code=400, detail="lemma_word is required for merge")
            lemma_result = await ingest_word_or_phrase(
                db,
                lemma_target,
                scraper=scraper,
                payload_cache=payload_cache,
                meaning_cache=meaning_cache,
                options=options,
            )
            lemma_word = db.scalar(_word_query().where(func.lower(Word.word) == lemma_target.lower()))
            if lemma_word is None:
                raise HTTPException(status_code=500, detail="Failed to create/find lemma word")
            inflected_word = db.scalar(_word_query().where(func.lower(Word.word) == input_word.lower()))
            if inflected_word and inflected_word.id != lemma_word.id:
                merge_into_lemma(db, inflected_word, lemma_word)
            result_words = [lemma_word]
            _ = lemma_result
        elif action == "link":
            lemma_target = (payload.lemma_word or "").strip()
            if not lemma_target:
                raise HTTPException(status_code=400, detail="lemma_word is required for link")
            await ingest_word_or_phrase(
                db,
                lemma_target,
                scraper=scraper,
                payload_cache=payload_cache,
                meaning_cache=meaning_cache,
                options=options,
            )
            await ingest_word_or_phrase(
                db,
                input_word,
                scraper=scraper,
                payload_cache=payload_cache,
                meaning_cache=meaning_cache,
                options=options,
            )
            lemma_word = db.scalar(_word_query().where(func.lower(Word.word) == lemma_target.lower()))
            inflected_word = db.scalar(_word_query().where(func.lower(Word.word) == input_word.lower()))
            if lemma_word is None or inflected_word is None:
                raise HTTPException(status_code=500, detail="Failed to create/find words for link")
            candidate = await detect_lemma(input_word, db, scraper=scraper)
            inflection_type = candidate.inflection_type if candidate else "inflection"
            link_to_lemma(db, inflected_word, lemma_word, inflection_type)
            result_words = [inflected_word, lemma_word]
        else:
            result = await ingest_word_or_phrase(
                db,
                input_word,
                scraper=scraper,
                payload_cache=payload_cache,
                meaning_cache=meaning_cache,
                options=options,
            )
            result_words = list(result.words)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    for word in result_words:
        db.refresh(word)
    return [_to_word_read(db, word) for word in result_words]


@router.post("/bulk", response_model=list[WordRead])
async def bulk_create_words(
    payload: BulkWordRequest,
    llm_mode: Literal["sync", "async"] = Query("async"),
    phrase_enrich_mode: Literal["sequential", "parallel"] = Query("parallel"),
    example_mode: Literal["sequential", "parallel_thread", "parallel_async"] = Query("parallel_async"),
    phrase_parallelism: int = Query(8, ge=1, le=32),
    db: Session = Depends(get_db),
) -> list[WordRead]:
    options = IngestOptions(
        llm_mode=llm_mode,
        phrase_enrich_mode=phrase_enrich_mode,
        example_mode=example_mode,
        phrase_parallelism=phrase_parallelism,
    )
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
            options=options,
        )
        for word in result.words:
            result_words[word.id] = word
    db.commit()
    words = list(result_words.values())
    for word in words:
        db.refresh(word)
    return [_to_word_read(db, word) for word in words]


@router.post("/check", response_model=WordCheckResponse)
def check_words(payload: BulkWordRequest, db: Session = Depends(get_db)) -> WordCheckResponse:
    normalized_targets: list[str] = []
    for item in payload.words:
        value = item.strip()
        if not value:
            continue
        if value in normalized_targets:
            continue
        normalized_targets.append(value)

    if not normalized_targets:
        return WordCheckResponse(found=[], not_found=[])

    lowered = [item.lower() for item in normalized_targets]
    stmt = select(Word).where(func.lower(Word.word).in_(lowered))
    matched_words = list(db.scalars(stmt))
    by_lower = {word.word.lower(): word for word in matched_words}

    found: list[WordCheckFound] = []
    not_found: list[str] = []
    for original in normalized_targets:
        matched = by_lower.get(original.lower())
        if matched:
            found.append(WordCheckFound(id=matched.id, word=matched.word))
        else:
            not_found.append(original)
    return WordCheckResponse(found=found, not_found=not_found)


@router.post("/check-inflection", response_model=InflectionCheckResponse)
async def check_inflection(payload: InflectionCheckRequest, db: Session = Depends(get_db)) -> InflectionCheckResponse:
    targets: list[str] = []
    if payload.word and payload.word.strip():
        targets.append(payload.word.strip())
    for item in payload.words:
        value = item.strip()
        if not value:
            continue
        targets.append(value)
    if not targets:
        return InflectionCheckResponse(result=None, results=[])

    deduped: list[str] = []
    seen: set[str] = set()
    for item in targets:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    scraper = WiktionaryScraper()
    db_words = list(db.scalars(select(Word.word)))
    by_lower = {str(w).strip().lower(): str(w).strip() for w in db_words if str(w).strip()}
    spellchecker = build_spellchecker(
        list(by_lower.values()),
        merge_db_vocabulary=payload.spellchecker_merge_db,
    )
    own_content_cache: dict[str, bool] = {}
    results: list[InflectionCheckResult] = []
    for word_text in deduped:
        word_has_own_content = await detect_word_has_own_content(
            word_text,
            scraper=scraper,
            cache=own_content_cache,
        )
        candidates = await detect_lemma_candidates(word_text, db, scraper=scraper)
        spelling_candidates_payload: list[dict] = []
        selected_spelling: str | None = None
        selected = candidates[0] if candidates else None
        if not selected:
            for spelling_info in collect_spelling_suggestions(
                word_text,
                by_lower,
                spellchecker,
                use_db_near=payload.use_db_near,
            ):
                spelling = str(spelling_info.get("spelling", "")).strip()
                if not spelling:
                    continue
                spelling_lemmas = await detect_lemma_candidates(spelling, db, scraper=scraper)
                if selected is None and spelling_lemmas:
                    selected_spelling = spelling
                    selected = spelling_lemmas[0]
                spelling_candidates_payload.append(
                    {
                        "spelling": spelling,
                        "source": spelling_info.get("source") or "",
                        "lemma_candidates": _serialize_lemma_candidates(spelling_lemmas),
                        "selected_lemma": spelling_lemmas[0].lemma_word if spelling_lemmas else None,
                        "lemma_resolution": (
                            "resolved_from_inflection"
                            if spelling_lemmas and spelling_lemmas[0].lemma_word.lower() != spelling.lower()
                            else ("direct" if spelling_lemmas else "manual")
                        ),
                    }
                )
        suggestion = suggest_inflection_action(selected)
        results.append(
            InflectionCheckResult(
                word=word_text,
                is_inflected=(selected is not None) or bool(spelling_candidates_payload),
                word_has_own_content=word_has_own_content,
                selected_lemma=(selected.lemma_word if selected else None),
                selected_lemma_word_id=(selected.lemma_word_id if selected else None),
                selected_inflection_type=(selected.inflection_type if selected else None),
                selected_has_own_content=(selected.has_own_content if selected else None),
                selected_confidence=(selected.confidence if selected else None),
                selected_source=(selected.source if selected else None),
                selected_score=(selected.score if selected else None),
                selected_spelling=selected_spelling,
                lemma_resolution=(
                    "resolved_from_inflection"
                    if selected_spelling and selected and selected.lemma_word.lower() != selected_spelling.lower()
                    else ("direct" if selected else None)
                ),
                lemma_candidates=_serialize_lemma_candidates(candidates),
                spelling_candidates=spelling_candidates_payload,
                suggestion=suggestion or "register_as_is",
            )
        )
    if payload.word and not payload.words:
        return InflectionCheckResponse(result=results[0], results=results)
    return InflectionCheckResponse(result=None, results=results)


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
    await word_service.rescrape(db, word)
    db.commit()
    db.refresh(word)
    return _to_word_read(db, word)


@router.post("/{word_id}/enrich-etymology", response_model=EtymologyRead)
def enrich_etymology(word_id: int, db: Session = Depends(get_db)) -> EtymologyRead:
    word = db.scalar(_word_query().where(Word.id == word_id))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    etymology = word_service.enrich_etymology(db, word)
    db.commit()
    db.refresh(etymology)
    ety_data = word_service._build_etymology_read(db, etymology)
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
    forms = dict(payload.forms or {})
    forms.pop("phrases", None)
    word.forms = forms

    _replace_definitions(word, [item.model_dump() for item in payload.definitions])
    if payload.etymology is not None:
        if not word.etymology:
            word.etymology = Etymology()
        word_service.apply_etymology_update(db, word.etymology, payload.etymology.model_dump())
    _replace_derivations(db, word, [item.model_dump() for item in payload.derivations])
    _replace_related_words(db, word, [item.model_dump() for item in payload.related_words])
    if "phrases" in payload.model_fields_set:
        word_service.replace_word_phrases(
            db,
            word,
            [item.model_dump() for item in payload.phrases],
        )

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
