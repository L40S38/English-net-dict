from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Phrase, Word, WordPhrase
from app.schemas import PhraseCreate, PhraseRead, PhraseUpdate
from app.services.phrase_service import get_or_create_phrase, link_phrase_to_word, list_word_phrases, merge_meanings

router = APIRouter(prefix="/api", tags=["phrases"])


@router.get("/phrases", response_model=list[PhraseRead])
def list_phrases(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[PhraseRead]:
    stmt = select(Phrase).order_by(func.lower(Phrase.text), Phrase.id)
    if q:
        keyword = q.strip()
        if keyword:
            stmt = stmt.where(Phrase.text.ilike(f"%{keyword}%"))
    items = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    return [PhraseRead.model_validate(item) for item in items]


@router.get("/phrases/{phrase_id}", response_model=PhraseRead)
def get_phrase(phrase_id: int, db: Session = Depends(get_db)) -> PhraseRead:
    phrase = db.get(Phrase, phrase_id)
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return PhraseRead.model_validate(phrase)


@router.post("/phrases", response_model=PhraseRead)
def create_phrase(payload: PhraseCreate, db: Session = Depends(get_db)) -> PhraseRead:
    try:
        phrase = get_or_create_phrase(db, payload.text, payload.meaning)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(phrase)
    return PhraseRead.model_validate(phrase)


@router.put("/phrases/{phrase_id}", response_model=PhraseRead)
def update_phrase(phrase_id: int, payload: PhraseUpdate, db: Session = Depends(get_db)) -> PhraseRead:
    phrase = db.get(Phrase, phrase_id)
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    phrase.meaning = merge_meanings(payload.meaning)
    db.commit()
    db.refresh(phrase)
    return PhraseRead.model_validate(phrase)


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
    return [PhraseRead.model_validate(item) for item in list_word_phrases(db, word_id)]


@router.post("/words/{word_id}/phrases", response_model=PhraseRead)
def add_phrase_to_word(word_id: int, payload: PhraseCreate, db: Session = Depends(get_db)) -> PhraseRead:
    word = db.get(Word, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    try:
        phrase = get_or_create_phrase(db, payload.text, payload.meaning)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    link_phrase_to_word(db, word, phrase)
    db.commit()
    db.refresh(phrase)
    return PhraseRead.model_validate(phrase)


@router.delete("/words/{word_id}/phrases/{phrase_id}")
def delete_phrase_from_word(word_id: int, phrase_id: int, db: Session = Depends(get_db)) -> dict:
    link = db.scalar(select(WordPhrase).where(WordPhrase.word_id == word_id, WordPhrase.phrase_id == phrase_id))
    if not link:
        raise HTTPException(status_code=404, detail="Word phrase link not found")
    db.delete(link)
    db.commit()
    return {"ok": True}
