from __future__ import annotations

import pytest

from core.utils.text_helpers import is_multi_token, normalize_phrase_entries, slugify


@pytest.mark.parametrize(
    "text",
    [
        "../../../etc/evil",
        "../../somewhere/evil",
        "..\\..\\windows\\evil",
    ],
)
def test_slugify_strips_path_traversal(text: str) -> None:
    slug = slugify(text)
    assert "/" not in slug
    assert "\\" not in slug
    assert ".." not in slug


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("normal word", "normal-word"),
        ("CamelCase! Test", "camelcase-test"),
        ("  spaced  out  ", "spaced-out"),
    ],
)
def test_slugify_matches_expected_output(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_falls_back_when_empty_after_strip() -> None:
    assert slugify("!!!") == "item"
    assert slugify("") == "item"


@pytest.mark.parametrize("raw", [None, {"phrase": "not a list"}, "just a string", 42])
def test_normalize_phrase_entries_rejects_non_list_input(raw: object) -> None:
    assert normalize_phrase_entries(raw) == []


def test_normalize_phrase_entries_handles_string_items() -> None:
    assert normalize_phrase_entries([" kick the bucket ", "", "  "]) == [
        {"phrase": "kick the bucket", "meaning": ""},
    ]


def test_normalize_phrase_entries_handles_dict_items_with_fallback_keys() -> None:
    raw = [
        {"phrase": "break the ice", "meaning": "to ease tension"},
        {"text": "spill the beans", "meaning_en": "reveal a secret"},
        {"phrase": "  ", "meaning": "dropped because phrase is blank"},
        {"meaning": "dropped because no phrase/text key"},
    ]
    assert normalize_phrase_entries(raw) == [
        {"phrase": "break the ice", "meaning": "to ease tension"},
        {"phrase": "spill the beans", "meaning": "reveal a secret"},
    ]


def test_normalize_phrase_entries_skips_unsupported_item_types() -> None:
    assert normalize_phrase_entries(["valid phrase", 123, None, ["nested"]]) == [
        {"phrase": "valid phrase", "meaning": ""},
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello", False),
        ("", False),
        ("   ", False),
        ("hello world", True),
        ("  hello   world  ", True),
        ("a b c", True),
    ],
)
def test_is_multi_token(text: str, expected: bool) -> None:
    assert is_multi_token(text) is expected
