from __future__ import annotations

import pytest

from core.services.word_service import split_comma_items


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("apple, banana, cherry", ["apple", "banana", "cherry"]),
        ("apple、banana、cherry", ["apple", "banana", "cherry"]),
        ("apple,  banana ,cherry", ["apple", "banana", "cherry"]),
    ],
)
def test_split_comma_items_basic(text: str, expected: list[str]) -> None:
    assert split_comma_items(text) == expected


def test_split_comma_items_ignores_commas_inside_balanced_parens() -> None:
    text = "abandon(捨てる、放棄する), forsake(見捨てる, 断念する)"
    assert split_comma_items(text) == ["abandon(捨てる、放棄する)", "forsake(見捨てる, 断念する)"]


def test_split_comma_items_handles_fullwidth_parens() -> None:
    text = "捨てる（放棄する、見捨てる）, 断念する"
    assert split_comma_items(text) == ["捨てる（放棄する、見捨てる）", "断念する"]


def test_split_comma_items_with_unclosed_paren_does_not_swallow_later_commas() -> None:
    """Regression test: an unclosed '(' (e.g. from a scraper's mid-word
    truncation) previously left `depth` stuck above 0 for the rest of the
    string, so every comma after that point was treated as "inside
    parentheses" and silently merged into one giant item instead of being
    split.
    """
    text = "abandon (to give up, quit, forsake"
    result = split_comma_items(text)
    assert result == ["abandon (to give up", "quit", "forsake"]


def test_split_comma_items_with_unmatched_closing_paren_does_not_swallow_commas() -> None:
    text = "quit), forsake, abandon"
    result = split_comma_items(text)
    assert result == ["quit)", "forsake", "abandon"]


def test_split_comma_items_dedupes_case_insensitively() -> None:
    assert split_comma_items("Forsake, forsake, FORSAKE") == ["Forsake"]


def test_split_comma_items_drops_empty_segments() -> None:
    assert split_comma_items("apple,, ,banana") == ["apple", "banana"]


def test_split_comma_items_empty_input_returns_empty_list() -> None:
    assert split_comma_items("") == []
