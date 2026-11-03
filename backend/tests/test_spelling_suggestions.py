from __future__ import annotations

from core.services.spelling_suggestions import collect_spelling_suggestions


def test_collect_spelling_suggestions_returns_empty_with_no_sources() -> None:
    assert collect_spelling_suggestions("anything", {}, None) == []


def test_collect_spelling_suggestions_db_near_finds_close_matches() -> None:
    by_lower = {"apple": "Apple", "ample": "Ample", "apply": "Apply"}

    result = collect_spelling_suggestions(
        "aple",
        by_lower,
        None,
        use_db_near=True,
        db_near_cutoff=0.6,
    )

    assert result
    assert all(item["source"] == "db_near" for item in result)
    assert {item["spelling"] for item in result} <= set(by_lower.values())


def test_collect_spelling_suggestions_db_near_excludes_exact_match() -> None:
    by_lower = {"apple": "Apple"}

    result = collect_spelling_suggestions("apple", by_lower, None, use_db_near=True)

    assert result == []


def test_collect_spelling_suggestions_respects_db_near_n_limit() -> None:
    by_lower = {f"aaaa{i}": f"Aaaa{i}" for i in range(10)}

    result = collect_spelling_suggestions(
        "aaaa",
        by_lower,
        None,
        use_db_near=True,
        db_near_n=3,
        db_near_cutoff=0.1,
    )

    assert len(result) <= 3
