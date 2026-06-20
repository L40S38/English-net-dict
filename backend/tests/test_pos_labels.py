from __future__ import annotations

import pytest

from core.utils.pos_labels import normalize_part_of_speech


@pytest.mark.parametrize("value", [None, ""])
def test_normalize_part_of_speech_handles_missing_value(value: str | None) -> None:
    assert normalize_part_of_speech(value) == "不明 unknown"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("n", "名詞 noun"),
        ("noun", "名詞 noun"),
        ("NOUN", "名詞 noun"),
        ("v", "動詞 verb"),
        ("adj", "形容詞 adjective"),
        ("adv", "副詞 adverb"),
        ("prep", "前置詞 preposition"),
    ],
)
def test_normalize_part_of_speech_maps_known_abbreviations(value: str, expected: str) -> None:
    assert normalize_part_of_speech(value) == expected


def test_normalize_part_of_speech_is_idempotent_on_already_normalized_label() -> None:
    assert normalize_part_of_speech("名詞 noun") == "名詞 noun"


def test_normalize_part_of_speech_collapses_self_referential_parens() -> None:
    assert normalize_part_of_speech("conjunction (conjunction)") == "接続詞 conjunction"


def test_normalize_part_of_speech_falls_back_to_substring_match() -> None:
    assert normalize_part_of_speech("proper noun") == "名詞 noun"


def test_normalize_part_of_speech_unknown_value_passes_through_with_key() -> None:
    assert normalize_part_of_speech("xyz") == "xyz (xyz)"
