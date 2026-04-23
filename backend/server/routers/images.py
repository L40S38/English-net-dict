from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.models import Phrase, Word, WordPhrase
from core.schemas import GenerateImageRequest, PhraseImageRead, WordImageRead
from core.services.image_service import (
    build_image_prompt,
    build_phrase_image_prompt,
    generate_phrase_image,
    generate_word_image,
)

router = APIRouter(prefix="/api", tags=["images"])


@router.post("/words/{word_id}/generate-image", response_model=WordImageRead)
def generate_image(
    word_id: int,
    payload: GenerateImageRequest,
    db: Session = Depends(get_db),
) -> WordImageRead:
    stmt = select(Word).where(Word.id == word_id).options(joinedload(Word.etymology), joinedload(Word.images))
    word = db.scalar(stmt)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    image = generate_word_image(db, word, payload.prompt)
    db.commit()
    db.refresh(image)
    return WordImageRead.model_validate(image)


@router.get("/words/{word_id}/default-image-prompt")
def get_default_image_prompt(word_id: int, db: Session = Depends(get_db)) -> dict:
    stmt = select(Word).where(Word.id == word_id).options(joinedload(Word.etymology))
    word = db.scalar(stmt)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return {"prompt": build_image_prompt(word)}


@router.post("/phrases/{phrase_id}/generate-image", response_model=PhraseImageRead)
def generate_phrase_image_route(
    phrase_id: int,
    payload: GenerateImageRequest,
    db: Session = Depends(get_db),
) -> PhraseImageRead:
    stmt = (
        select(Phrase)
        .where(Phrase.id == phrase_id)
        .options(
            joinedload(Phrase.definitions),
            joinedload(Phrase.word_links).joinedload(WordPhrase.word_ref),
            joinedload(Phrase.images),
        )
    )
    phrase = db.scalar(stmt)
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    image = generate_phrase_image(db, phrase, payload.prompt)
    db.commit()
    db.refresh(image)
    return PhraseImageRead.model_validate(image)


@router.get("/phrases/{phrase_id}/default-image-prompt")
def get_phrase_default_image_prompt(phrase_id: int, db: Session = Depends(get_db)) -> dict:
    stmt = select(Phrase).where(Phrase.id == phrase_id).options(
        joinedload(Phrase.definitions),
        joinedload(Phrase.word_links).joinedload(WordPhrase.word_ref),
    )
    phrase = db.scalar(stmt)
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return {"prompt": build_phrase_image_prompt(phrase)}
