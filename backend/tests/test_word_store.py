from __future__ import annotations

from sqlalchemy.orm import Session

from core.models import Word
from core.stores.word_store import WordStore


def test_find_by_normalized_word_is_case_insensitive(db_session: Session) -> None:
    db_session.add(Word(word="Serendipity"))
    db_session.commit()

    found = WordStore.find_by_normalized_word(db_session, "serendipity")

    assert found is not None
    assert found.word == "Serendipity"


def test_find_by_normalized_word_returns_none_when_missing(db_session: Session) -> None:
    assert WordStore.find_by_normalized_word(db_session, "doesnotexist") is None


def test_find_linked_word_id_strips_and_lowercases(db_session: Session) -> None:
    word = Word(word="lexicon")
    db_session.add(word)
    db_session.commit()

    assert WordStore.find_linked_word_id(db_session, "  LEXICON  ") == word.id


def test_find_linked_word_id_returns_none_for_blank_input(db_session: Session) -> None:
    assert WordStore.find_linked_word_id(db_session, "   ") is None
