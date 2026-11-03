from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.orm import Session

import core.services.phrase_ingest_service as phrase_ingest_service
from core.models import Phrase
from core.services.phrase_ingest_service import enrich_phrase


class _FakeScraper:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.scrape_calls = 0

    async def scrape(self, text: str) -> dict:
        self.scrape_calls += 1
        return self.data


def test_enrich_phrase_reuses_phrase_cache_across_a_simulated_lock_retry(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: without phrase_cache, a SQLite-lock retry that rolls back and
    re-creates the same Phrase row (see ingest_word_or_phrase) would re-scrape
    Wiktionary and re-call OpenAI translation every attempt. With phrase_cache keyed
    by phrase text, the second attempt for the same phrase must reuse the cached
    scrape/translation result instead of redoing the external calls."""
    scraper = _FakeScraper(
        {
            "synonyms": ["give up"],
            "antonyms": [],
            "see_also": [],
            "derived_terms": [],
            "phrases": [],
            "definitions": [
                {
                    "part_of_speech": "verb",
                    "meaning_en": "to stop trying",
                    "example_en": "He threw in the towel.",
                }
            ],
        }
    )
    translate_calls = {"n": 0}

    def fake_translate(phrase_text: str, items: list[dict]) -> list[dict]:
        translate_calls["n"] += 1
        return [{"meaning_ja": "諦める", "example_ja": "彼は諦めた。"} for _ in items]

    monkeypatch.setattr(phrase_ingest_service, "translate_phrase_definitions", fake_translate)

    meaning_cache: dict[str, str | None] = {"throw in the towel": "諦める"}
    phrase_cache: dict[str, dict] = {}

    phrase1 = Phrase(text="throw in the towel", meaning="")
    db_session.add(phrase1)
    db_session.flush()
    asyncio.run(
        enrich_phrase(db_session, phrase1, scraper=scraper, cache=meaning_cache, phrase_cache=phrase_cache)
    )

    assert scraper.scrape_calls == 1
    assert translate_calls["n"] == 1
    assert phrase1.wiktionary_synonyms == ["give up"]
    assert phrase1.definitions[0].meaning_ja == "諦める"

    # Simulate what happens after a SQLite-lock OperationalError: db.rollback()
    # discards the uncommitted Phrase row, and the retry creates a fresh one for the
    # same phrase text (find_phrase_by_text returns None again).
    db_session.rollback()
    phrase2 = Phrase(text="throw in the towel", meaning="")
    db_session.add(phrase2)
    db_session.flush()
    asyncio.run(
        enrich_phrase(db_session, phrase2, scraper=scraper, cache=meaning_cache, phrase_cache=phrase_cache)
    )

    assert scraper.scrape_calls == 1  # not re-scraped
    assert translate_calls["n"] == 1  # not re-translated
    assert phrase2.wiktionary_synonyms == ["give up"]
    assert phrase2.definitions[0].meaning_ja == "諦める"


def test_enrich_phrase_without_phrase_cache_still_works(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """phrase_cache is optional - phrases.py's routes (no retry loop) don't pass one.
    enrich_phrase must still work correctly without it, just without the caching
    benefit (each call re-scrapes/re-translates)."""
    scraper = _FakeScraper(
        {
            "definitions": [
                {"part_of_speech": "phrase", "meaning_en": "easy", "example_en": ""},
            ],
        }
    )
    monkeypatch.setattr(
        phrase_ingest_service,
        "translate_phrase_definitions",
        lambda phrase_text, items: [{"meaning_ja": "楽勝", "example_ja": ""} for _ in items],
    )

    phrase = Phrase(text="a piece of cake", meaning="")
    db_session.add(phrase)
    db_session.flush()

    result = asyncio.run(
        enrich_phrase(db_session, phrase, scraper=scraper, cache={"a piece of cake": "楽勝"})
    )

    assert result is phrase
    assert scraper.scrape_calls == 1
    assert phrase.definitions[0].meaning_ja == "楽勝"
