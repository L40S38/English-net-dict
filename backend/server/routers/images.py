from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from core.database import get_db
from core.models import Word
from core.schemas import GenerateImageRequest, WordImageRead
from core.services.image_service import build_image_prompt, generate_word_image

router = APIRouter(prefix="/api/words", tags=["images"])


@router.post("/{word_id}/generate-image", response_model=WordImageRead)
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


@router.get("/{word_id}/default-image-prompt")
def get_default_image_prompt(word_id: int, db: Session = Depends(get_db)) -> dict:
    stmt = select(Word).where(Word.id == word_id).options(joinedload(Word.etymology))
    word = db.scalar(stmt)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return {"prompt": build_image_prompt(word)}
