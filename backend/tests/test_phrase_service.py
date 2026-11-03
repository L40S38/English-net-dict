from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from core.models import Word
from core.services.phrase_service import (
    find_phrase_by_text,
    get_or_create_phrase,
    link_phrase_to_word,
    merge_meanings,
    normalize_phrase_text,
    split_meanings,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  hello   world  ", "hello world"),
        ("Ｈｅｌｌｏ　Ｗｏｒｌｄ", "Hello World"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalize_phrase_text(text: str | None, expected: str) -> None:
    assert normalize_phrase_text(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a, b, c", ["a", "b", "c"]),
        ("a，b，c", ["a", "b", "c"]),
        ("a, a, b", ["a", "b"]),
        ("", []),
        (None, []),
    ],
)
def test_split_meanings(text: str | None, expected: list[str]) -> None:
    assert split_meanings(text) == expected


def test_merge_meanings_dedupes_preserving_first_seen_order() -> None:
    assert merge_meanings("a, b", "b, c") == "a，b，c"


def test_merge_meanings_with_no_values_returns_empty_string() -> None:
    assert merge_meanings() == ""


def test_get_or_create_phrase_creates_new_row(db_session: Session) -> None:
    phrase = get_or_create_phrase(db_session, "kick the bucket", "to die")
    db_session.commit()

    assert phrase.id is not None
    assert phrase.text == "kick the bucket"
    assert phrase.meaning == "to die"


def test_get_or_create_phrase_is_case_insensitive_and_merges_meanings(db_session: Session) -> None:
    first = get_or_create_phrase(db_session, "Spill the Beans", "reveal a secret")
    db_session.commit()

    second = get_or_create_phrase(db_session, "spill the beans", "to tell")
    db_session.commit()

    assert second.id == first.id
    assert second.meaning == "reveal a secret，to tell"


def test_find_phrase_by_text_returns_none_when_missing(db_session: Session) -> None:
    assert find_phrase_by_text(db_session, "does not exist") is None


def test_link_phrase_to_word_is_idempotent(db_session: Session) -> None:
    word = Word(word="bucket")
    db_session.add(word)
    db_session.flush()
    phrase = get_or_create_phrase(db_session, "kick the bucket", "to die")

    link_phrase_to_word(db_session, word, phrase)
    link_phrase_to_word(db_session, word, phrase)
    db_session.commit()

    assert [p.id for p in word.phrases] == [phrase.id]
