from __future__ import annotations

import re
import uuid
from pathlib import Path

from openai import OpenAI
from sqlalchemy.orm import Session

from core.config import settings
from core.models import DefinitionExample, Phrase, PhraseDefinition, Word


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "audio"


def synthesize_speech(text: str, slug: str, voice: str | None = None) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")
    if not text.strip():
        raise RuntimeError("Text is empty")

    audio_dir = Path(settings.audio_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{slug}-{uuid.uuid4().hex[:8]}.mp3"
    file_path = audio_dir / filename

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.audio.speech.create(
        model=settings.openai_tts_model,
        voice=voice or settings.openai_tts_voice,
        input=text,
    )
    response.stream_to_file(file_path)

    return f"audio/{filename}"


def generate_word_audio(db: Session, word: Word) -> Word:
    word.audio_path = synthesize_speech(word.word, _slugify(word.word))
    db.flush()
    return word


def generate_example_audio(db: Session, example: DefinitionExample) -> DefinitionExample:
    example.audio_path = synthesize_speech(example.example_en, f"example-{example.id}")
    db.flush()
    return example


def generate_phrase_audio(db: Session, phrase: Phrase) -> Phrase:
    phrase.audio_path = synthesize_speech(phrase.text, _slugify(phrase.text))
    db.flush()
    return phrase


def generate_phrase_definition_audio(db: Session, phrase_definition: PhraseDefinition) -> PhraseDefinition:
    phrase_definition.audio_path = synthesize_speech(
        phrase_definition.example_en, f"phrase-example-{phrase_definition.id}"
    )
    db.flush()
    return phrase_definition
