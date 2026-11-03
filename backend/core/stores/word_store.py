from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import Word


class WordStore:
    @staticmethod
    def find_by_normalized_word(db: Session, normalized_word: str) -> Word | None:
        return db.scalar(select(Word).where(func.lower(Word.word) == normalized_word))

    @staticmethod
    def find_linked_word_id(db: Session, raw_word: str) -> int | None:
        normalized_word = raw_word.strip().lower()
        if not normalized_word:
            return None
        linked = WordStore.find_by_normalized_word(db, normalized_word)
        return linked.id if linked else None
