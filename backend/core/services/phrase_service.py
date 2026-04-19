from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.models import Phrase, Word, WordPhrase


def normalize_phrase_text(text: str) -> str:
    # Keep letter case; normalize spacing and width only.
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value


def split_meanings(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"[，,]", str(text or ""))]
    seen: "OrderedDict[str, None]" = OrderedDict()
    for part in parts:
        if not part:
            continue
        if part in seen:
            continue
        seen[part] = None
    return list(seen.keys())


def merge_meanings(*values: str) -> str:
    seen: "OrderedDict[str, None]" = OrderedDict()
    for value in values:
        for part in split_meanings(value):
            if part in seen:
                continue
            seen[part] = None
    return "，".join(seen.keys())


def phrase_to_payload(phrase: Phrase | None) -> dict[str, str | int] | None:
    if not phrase:
        return None
    return {
        "id": phrase.id,
        "text": phrase.text,
        "meaning": phrase.meaning or "",
        "created_at": phrase.created_at,
        "updated_at": phrase.updated_at,
    }


def find_phrase_by_text(db: Session, raw_text: str) -> Phrase | None:
    normalized = normalize_phrase_text(raw_text)
    if not normalized:
        return None
    stmt = select(Phrase).where(Phrase.text == normalized)
    return db.scalar(stmt)


def _tokenize_phrase_text(text: str) -> list[str]:
    return [token for token in re.split(r"\s+", normalize_phrase_text(text).lower()) if token]


def find_phrases_containing_token(db: Session, token: str) -> list[Phrase]:
    normalized_token = normalize_phrase_text(token).lower()
    if not normalized_token:
        return []
    stmt = (
        select(Phrase)
        .where(
            or_(
                func.lower(Phrase.text) == normalized_token,
                func.lower(Phrase.text).like(f"{normalized_token} %"),
                func.lower(Phrase.text).like(f"% {normalized_token}"),
                func.lower(Phrase.text).like(f"% {normalized_token} %"),
            )
        )
        .order_by(func.lower(Phrase.text), Phrase.id)
    )
    candidates = list(db.scalars(stmt))
    return [phrase for phrase in candidates if normalized_token in _tokenize_phrase_text(phrase.text)]


def get_or_create_phrase(db: Session, raw_text: str, meaning: str = "") -> Phrase:
    normalized = normalize_phrase_text(raw_text)
    if not normalized:
        raise ValueError("phrase text is required")
    phrase = find_phrase_by_text(db, normalized)
    if phrase:
        merged = merge_meanings(phrase.meaning or "", meaning or "")
        if merged != (phrase.meaning or ""):
            phrase.meaning = merged
        return phrase

    phrase = Phrase(text=normalized, meaning=merge_meanings(meaning or ""))
    db.add(phrase)
    db.flush()
    return phrase


def link_phrase_to_word(db: Session, word: Word, phrase: Phrase) -> None:
    exists_stmt = select(WordPhrase.id).where(WordPhrase.word_id == word.id, WordPhrase.phrase_id == phrase.id)
    if db.scalar(exists_stmt):
        return
    db.add(WordPhrase(word_id=word.id, phrase_id=phrase.id))
    db.flush()


def link_existing_phrases_for_word(db: Session, word: Word) -> int:
    linked_count = 0
    for phrase in find_phrases_containing_token(db, word.word):
        exists_stmt = select(WordPhrase.id).where(WordPhrase.word_id == word.id, WordPhrase.phrase_id == phrase.id)
        already_linked = db.scalar(exists_stmt) is not None
        link_phrase_to_word(db, word, phrase)
        if not already_linked:
            linked_count += 1
    return linked_count


def replace_word_phrases(db: Session, word: Word, phrase_entries: list[dict[str, str]]) -> None:
    existing_links = list(word.phrase_links or [])
    for link in existing_links:
        word.phrase_links.remove(link)
    db.flush()

    for entry in phrase_entries:
        text = normalize_phrase_text(entry.get("text", ""))
        if not text:
            continue
        phrase = get_or_create_phrase(db, text, entry.get("meaning", ""))
        link_phrase_to_word(db, word, phrase)


def list_word_phrases(db: Session, word_id: int) -> list[Phrase]:
    stmt = (
        select(Phrase)
        .join(WordPhrase, WordPhrase.phrase_id == Phrase.id)
        .where(WordPhrase.word_id == word_id)
        .order_by(func.lower(Phrase.text), Phrase.id)
    )
    return list(db.scalars(stmt))
