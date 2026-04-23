from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.models import Phrase, Word, WordPhrase
from core.schemas import (
    PhraseCheckFound,
    PhraseCheckRequest,
    PhraseCheckResponse,
    PhraseCreate,
    PhraseFullUpdate,
    PhraseRead,
    PhraseUpdate,
    WordSummary,
)
from core.services.phrase_ingest_service import enrich_phrase
from core.services.phrase_service import (
    apply_full_update,
    get_or_create_phrase,
    link_phrase_to_word,
    list_phrase_words,
    list_word_phrases,
    merge_meanings,
    normalize_phrase_text,
)
from core.services.scraper.wiktionary import WiktionaryScraper

router = APIRouter(prefix="/api", tags=["phrases"])
PhraseSortBy = Literal["created_at", "updated_at", "text"]
SortOrder = Literal["desc", "asc"]


def _phrase_query():
    return select(Phrase).options(
        joinedload(Phrase.definitions),
        joinedload(Phrase.images),
        joinedload(Phrase.word_links).joinedload(WordPhrase.word_ref),
        joinedload(Phrase.chat_sessions),
    )


def _to_phrase_read(db: Session, phrase: Phrase) -> PhraseRead:
    words = list_phrase_words(db, phrase.id)
    return PhraseRead.model_validate(
        {
            "id": phrase.id,
            "text": phrase.text,
            "meaning": phrase.meaning or "",
            "created_at": phrase.created_at,
            "updated_at": phrase.updated_at,
            "definitions": phrase.definitions,
            "images": phrase.images,
            "words": [WordSummary.model_validate(word) for word in words],
            "chat_session_count": len(phrase.chat_sessions),
            "wiktionary_synonyms": phrase.wiktionary_synonyms or [],
            "wiktionary_antonyms": phrase.wiktionary_antonyms or [],
            "wiktionary_see_also": phrase.wiktionary_see_also or [],
            "wiktionary_derived_terms": phrase.wiktionary_derived_terms or [],
            "wiktionary_phrases": phrase.wiktionary_phrases or [],
        }
    )


@router.get("/phrases", response_model=list[PhraseRead])
def list_phrases(
    q: str | None = Query(default=None),
    sort_by: PhraseSortBy = Query(default="updated_at"),
    sort_order: SortOrder = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[PhraseRead]:
    direction_desc = sort_order == "desc"
    if sort_by == "text":
        sort_clauses = [func.lower(Phrase.text).desc() if direction_desc else func.lower(Phrase.text).asc(), Phrase.id.desc() if direction_desc else Phrase.id.asc()]
    elif sort_by == "created_at":
        sort_clauses = [Phrase.created_at.desc() if direction_desc else Phrase.created_at.asc(), Phrase.id.desc() if direction_desc else Phrase.id.asc()]
    else:
        sort_clauses = [Phrase.updated_at.desc() if direction_desc else Phrase.updated_at.asc(), Phrase.id.desc() if direction_desc else Phrase.id.asc()]

    stmt = _phrase_query().order_by(*sort_clauses)
    if q:
        keyword = q.strip()
        if keyword:
            stmt = stmt.where(Phrase.text.ilike(f"%{keyword}%"))
    items = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique())
    return [_to_phrase_read(db, item) for item in items]


@router.get("/phrases/{phrase_id}", response_model=PhraseRead)
def get_phrase(phrase_id: int, db: Session = Depends(get_db)) -> PhraseRead:
    phrase = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return _to_phrase_read(db, phrase)


@router.get("/phrases/{phrase_id}/words", response_model=list[WordSummary])
def get_phrase_words(phrase_id: int, db: Session = Depends(get_db)) -> list[WordSummary]:
    phrase = db.get(Phrase, phrase_id)
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return [WordSummary.model_validate(word) for word in list_phrase_words(db, phrase_id)]


@router.post("/phrases", response_model=PhraseRead)
async def create_phrase(payload: PhraseCreate, db: Session = Depends(get_db)) -> PhraseRead:
    try:
        phrase = get_or_create_phrase(db, payload.text, payload.meaning)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await enrich_phrase(db, phrase, scraper=WiktionaryScraper(), cache={})
    db.commit()
    refreshed = db.scalar(_phrase_query().where(Phrase.id == phrase.id))
    if not refreshed:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return _to_phrase_read(db, refreshed)


@router.post("/phrases/{phrase_id}/enrich", response_model=PhraseRead)
async def enrich_phrase_route(phrase_id: int, db: Session = Depends(get_db)) -> PhraseRead:
    phrase = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    await enrich_phrase(db, phrase, scraper=WiktionaryScraper(), cache={})
    db.commit()
    refreshed = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    if not refreshed:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return _to_phrase_read(db, refreshed)


@router.post("/phrases/check", response_model=PhraseCheckResponse)
def check_phrases(payload: PhraseCheckRequest, db: Session = Depends(get_db)) -> PhraseCheckResponse:
    normalized_targets: list[str] = []
    normalized_map: dict[str, str] = {}
    for item in payload.texts:
        value = normalize_phrase_text(item)
        if not value:
            continue
        key = value.lower()
        if key in normalized_map:
            continue
        normalized_map[key] = value
        normalized_targets.append(value)

    if not normalized_targets:
        return PhraseCheckResponse(found=[], not_found=[])

    lowered = [item.lower() for item in normalized_targets]
    stmt = select(Phrase).where(func.lower(Phrase.text).in_(lowered))
    matched_phrases = list(db.scalars(stmt))
    by_lower = {phrase.text.lower(): phrase for phrase in matched_phrases}

    found: list[PhraseCheckFound] = []
    not_found: list[str] = []
    for original in normalized_targets:
        matched = by_lower.get(original.lower())
        if matched:
            found.append(PhraseCheckFound(id=matched.id, text=matched.text))
        else:
            not_found.append(original)
    return PhraseCheckResponse(found=found, not_found=not_found)


@router.put("/phrases/{phrase_id}", response_model=PhraseRead)
def update_phrase(phrase_id: int, payload: PhraseUpdate, db: Session = Depends(get_db)) -> PhraseRead:
    phrase = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    phrase.meaning = merge_meanings(payload.meaning)
    db.commit()
    db.refresh(phrase)
    return _to_phrase_read(db, phrase)


@router.put("/phrases/{phrase_id}/full", response_model=PhraseRead)
def update_phrase_full(phrase_id: int, payload: PhraseFullUpdate, db: Session = Depends(get_db)) -> PhraseRead:
    phrase = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    try:
        apply_full_update(db, phrase, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    refreshed = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    if not refreshed:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return _to_phrase_read(db, refreshed)


@router.delete("/phrases/{phrase_id}")
def delete_phrase(phrase_id: int, db: Session = Depends(get_db)) -> dict:
    phrase = db.get(Phrase, phrase_id)
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    db.delete(phrase)
    db.commit()
    return {"ok": True}


@router.get("/words/{word_id}/phrases", response_model=list[PhraseRead])
def list_phrases_for_word(word_id: int, db: Session = Depends(get_db)) -> list[PhraseRead]:
    if not db.get(Word, word_id):
        raise HTTPException(status_code=404, detail="Word not found")
    phrases = list_word_phrases(db, word_id)
    phrase_ids = [item.id for item in phrases]
    if not phrase_ids:
        return []
    detailed = list(db.scalars(_phrase_query().where(Phrase.id.in_(phrase_ids))).unique())
    by_id = {item.id: item for item in detailed}
    return [_to_phrase_read(db, by_id[item.id]) for item in phrases if item.id in by_id]


@router.post("/words/{word_id}/phrases", response_model=PhraseRead)
async def add_phrase_to_word(word_id: int, payload: PhraseCreate, db: Session = Depends(get_db)) -> PhraseRead:
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    try:
        phrase = get_or_create_phrase(db, payload.text, payload.meaning)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    link_phrase_to_word(db, word, phrase)
    await enrich_phrase(db, phrase, scraper=WiktionaryScraper(), cache={})
    db.commit()
    refreshed = db.scalar(_phrase_query().where(Phrase.id == phrase.id))
    if not refreshed:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return _to_phrase_read(db, refreshed)


@router.delete("/words/{word_id}/phrases/{phrase_id}")
def delete_phrase_from_word(word_id: int, phrase_id: int, db: Session = Depends(get_db)) -> dict:
    link = db.scalar(select(WordPhrase).where(WordPhrase.word_id == word_id, WordPhrase.phrase_id == phrase_id))
    if not link:
        raise HTTPException(status_code=404, detail="Word phrase link not found")
    db.delete(link)
    db.commit()
    return {"ok": True}
