from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import Etymology, Word
from core.services import word_service
from core.services.gpt_service import generate_structured_word_data
from core.services.lemma_service import detect_lemma, suggest_inflection_action
from core.services.scraper.wiktionary import WiktionaryScraper
from core.services.word_data_helpers import (
    enrich_phrase_and_related_meanings as _enrich_phrase_and_related_meanings,
)
from core.services.word_data_helpers import (
    normalize_structured_derivations_and_phrases as _normalize_structured_derivations_and_phrases,
)
from core.services.word_data_helpers import normalize_structured_forms as _normalize_structured_forms
from core.services.word_ingest_service import ingest_word_or_phrase
from core.services.word_merge_service import link_to_lemma, merge_into_lemma
from core.services.wordnet_service import get_wordnet_snapshot
from database_build.ops.common import scrape_all
from database_build.reporting import FieldDiff

_PLACEHOLDER_MEANINGS = {"", "Wiktionaryの派生語"}


def _word_snapshot(word: Word) -> dict[str, Any]:
    ety = word.etymology
    phrases = [{"phrase": p.text, "meaning": p.meaning or ""} for p in sorted(word.phrases, key=lambda x: x.id)]
    branches = []
    if ety:
        branches = [
            {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
            for b in sorted(ety.branches, key=lambda x: (x.sort_order, x.id))
        ]
    return {
        "phonetic": word.phonetic,
        "definitions_count": len(word.definitions or []),
        "phrases": phrases,
        "core_image": (ety.core_image if ety else "") or "",
        "branches": branches,
        "derivations_count": len(word.derivations or []),
        "related_words_count": len(word.related_words or []),
    }


def _snapshot_diffs(before: dict[str, Any], after: dict[str, Any], keys: list[str]) -> list[FieldDiff]:
    diffs: list[FieldDiff] = []
    for key in keys:
        if before.get(key) != after.get(key):
            diffs.append(FieldDiff(name=key, before=before.get(key), after=after.get(key)))
    return diffs


async def refresh_word(
    db: Session,
    word: Word,
    *,
    scraper: WiktionaryScraper | None = None,
    cache: dict[str, str | None] | None = None,
) -> list[FieldDiff]:
    before = _word_snapshot(word)
    wordnet_data = get_wordnet_snapshot(word.word)
    scraped_data = await scrape_all(word.word)
    structured = generate_structured_word_data(word.word, wordnet_data, scraped_data)
    structured = _normalize_structured_forms(structured)
    structured = _normalize_structured_derivations_and_phrases(structured)
    if scraper is not None and cache is not None:
        await _enrich_phrase_and_related_meanings(structured, scraper, cache)
    word_service.apply_structured_payload(db, word, structured)
    after = _word_snapshot(word)
    return _snapshot_diffs(
        before,
        after,
        [
            "phonetic",
            "definitions_count",
            "phrases",
            "core_image",
            "branches",
            "derivations_count",
            "related_words_count",
        ],
    )


async def refresh_word_data(
    db: Session,
    word: Word,
    *,
    scraper: WiktionaryScraper | None = None,
    cache: dict[str, str | None] | None = None,
) -> list[FieldDiff]:
    return await refresh_word(db, word, scraper=scraper, cache=cache)


async def rescrape_word(db: Session, word: Word) -> Word:
    await word_service.rescrape(db, word)
    db.commit()
    db.refresh(word)
    return word


def enrich_word_etymology(db: Session, word: Word) -> Etymology:
    etymology = word_service.enrich_etymology(db, word)
    db.commit()
    db.refresh(etymology)
    return etymology


def _read_word_list(file_path: Path) -> list[str]:
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    words: list[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        words.append(text)
    return words


def _select_words(words: list[str], word_filter: str | None, limit: int | None) -> list[str]:
    filtered = words
    if word_filter:
        target = word_filter.strip().lower()
        filtered = [w for w in filtered if w.strip().lower() == target]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


async def add_words_from_file(
    db: Session,
    file_path: Path,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
    skip_inflection_check: bool = False,
) -> tuple[int, int, int]:
    logging.getLogger("core.services.web_word_search").setLevel(logging.ERROR)
    added = 0
    skipped = 0
    errors = 0
    scraper = WiktionaryScraper()
    phrase_cache: dict[str, str | None] = {}
    payload_cache: dict[str, dict] = {}

    raw_words = _read_word_list(file_path)
    targets = _select_words(raw_words, word_filter=word_filter, limit=limit)
    for source in targets:
        normalized = source.strip().lower()
        if not normalized:
            skipped += 1
            continue
        try:
            if not skip_inflection_check:
                candidate = await detect_lemma(normalized, db, scraper=scraper)
                suggestion = suggest_inflection_action(candidate)
                if suggestion == "merge" and candidate:
                    lemma_target = candidate.lemma_word.strip().lower()
                    lemma_result = await ingest_word_or_phrase(
                        db,
                        lemma_target,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    lemma_word = db.scalar(select(Word).where(func.lower(Word.word) == lemma_target))
                    inflected_word = db.scalar(select(Word).where(func.lower(Word.word) == normalized))
                    if lemma_word and inflected_word and lemma_word.id != inflected_word.id:
                        merge_into_lemma(db, inflected_word, lemma_word)
                    added += lemma_result.created_count
                    if dry_run:
                        db.rollback()
                    else:
                        db.commit()
                    continue
                if suggestion == "link" and candidate:
                    lemma_target = candidate.lemma_word.strip().lower()
                    lemma_result = await ingest_word_or_phrase(
                        db,
                        lemma_target,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    inflected_result = await ingest_word_or_phrase(
                        db,
                        normalized,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    lemma_word = db.scalar(select(Word).where(func.lower(Word.word) == lemma_target))
                    inflected_word = db.scalar(select(Word).where(func.lower(Word.word) == normalized))
                    if lemma_word and inflected_word:
                        link_to_lemma(db, inflected_word, lemma_word, candidate.inflection_type or "inflection")
                    added += lemma_result.created_count + inflected_result.created_count
                    if dry_run:
                        db.rollback()
                    else:
                        db.commit()
                    continue

            result = await ingest_word_or_phrase(
                db,
                normalized,
                scraper=scraper,
                payload_cache=payload_cache,
                meaning_cache=phrase_cache,
            )
            if result.created_count > 0:
                added += result.created_count
            else:
                skipped += 1
            if dry_run:
                db.rollback()
            else:
                db.commit()
        except Exception:  # noqa: BLE001
            errors += 1
            db.rollback()
    return added, skipped, errors
