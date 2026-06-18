from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import DefinitionExample, Phrase, PhraseDefinition, Word
from core.schemas import DefinitionExampleRead, PhraseDefinitionRead, PhraseRead, WordRead
from core.services import word_service
from core.services.tts_service import (
    generate_example_audio,
    generate_phrase_audio,
    generate_phrase_definition_audio,
    generate_word_audio,
)
from server.routers.phrases import _phrase_query, _to_phrase_read
from server.routers.words import _word_query

router = APIRouter(prefix="/api", tags=["audio"])


@router.post("/words/{word_id}/generate-audio", response_model=WordRead)
def generate_word_audio_route(word_id: int, db: Session = Depends(get_db)) -> WordRead:
    word = db.scalar(_word_query().where(Word.id == word_id))
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    try:
        generate_word_audio(db, word)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    refreshed = db.scalar(_word_query().where(Word.id == word_id))
    return word_service.to_word_read(db, refreshed)


@router.post("/words/{word_id}/examples/{example_id}/generate-audio", response_model=DefinitionExampleRead)
def generate_example_audio_route(word_id: int, example_id: int, db: Session = Depends(get_db)) -> DefinitionExampleRead:
    example = db.scalar(
        select(DefinitionExample)
        .join(DefinitionExample.definition_ref)
        .where(DefinitionExample.id == example_id, DefinitionExample.definition_ref.has(word_id=word_id))
    )
    if not example:
        raise HTTPException(status_code=404, detail="Example not found")
    try:
        generate_example_audio(db, example)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    db.refresh(example)
    return DefinitionExampleRead.model_validate(example)


@router.post("/phrases/{phrase_id}/generate-audio", response_model=PhraseRead)
def generate_phrase_audio_route(phrase_id: int, db: Session = Depends(get_db)) -> PhraseRead:
    phrase = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    if not phrase:
        raise HTTPException(status_code=404, detail="Phrase not found")
    try:
        generate_phrase_audio(db, phrase)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    refreshed = db.scalar(_phrase_query().where(Phrase.id == phrase_id))
    return _to_phrase_read(db, refreshed)


@router.post(
    "/phrases/{phrase_id}/definitions/{definition_id}/generate-audio",
    response_model=PhraseDefinitionRead,
)
def generate_phrase_definition_audio_route(
    phrase_id: int, definition_id: int, db: Session = Depends(get_db)
) -> PhraseDefinitionRead:
    phrase_definition = db.scalar(
        select(PhraseDefinition).where(
            PhraseDefinition.id == definition_id, PhraseDefinition.phrase_id == phrase_id
        )
    )
    if not phrase_definition:
        raise HTTPException(status_code=404, detail="Phrase definition not found")
    try:
        generate_phrase_definition_audio(db, phrase_definition)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    db.refresh(phrase_definition)
    return PhraseDefinitionRead.model_validate(phrase_definition)
