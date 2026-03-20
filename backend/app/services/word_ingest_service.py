from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Word
from app.services.gpt_service import enrich_core_image_and_branches, generate_structured_word_data
from app.services.gpt_service_parallel import (
    ExampleMode,
    enrich_core_image_and_branches_async,
    generate_structured_word_data_async,
)
from app.services.phrase_service import get_or_create_phrase, link_phrase_to_word, normalize_phrase_text
from app.services.phrase_meaning_service import resolve_meaning_ja_ddgs
from app.services.scraper import build_scrapers
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.word_service import apply_structured_payload
from app.services.wordnet_service import get_wordnet_snapshot
from app.scripts.updaters import (
    _enrich_phrase_and_related_meanings,
    _enrich_phrase_and_related_meanings_parallel,
    _normalize_structured_derivations_and_phrases,
    _normalize_structured_forms,
)


@dataclass
class IngestResult:
    words: list[Word]
    created_count: int
    split_applied: bool


@dataclass
class IngestOptions:
    llm_mode: Literal["sync", "async"] = "async"
    phrase_enrich_mode: Literal["sequential", "parallel"] = "parallel"
    phrase_parallelism: int = 8
    example_mode: ExampleMode = "parallel_async"


def _normalize_text(text: str) -> str:
    return text.strip().lower()


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", _normalize_text(text)) if t]


def is_phrase_text(text: str) -> bool:
    return len(_tokenize(text)) >= 2


def _unique_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for token in _tokenize(text):
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique


async def _scrape_all(word_text: str) -> list[dict]:
    scrapers = build_scrapers()
    tasks = [scraper.scrape(word_text) for scraper in scrapers]
    return list(await asyncio.gather(*tasks))


def _core_image_is_generic(word_text: str, core_image: object) -> bool:
    value = str(core_image or "").strip()
    if not value:
        return True
    generic_patterns = {
        f"{word_text}: central concept",
        f"core image for {word_text}",
        f"etymology for {word_text}",
    }
    return value.lower() in {pattern.lower() for pattern in generic_patterns}


def _needs_etymology_enrichment(word_text: str, structured: dict) -> bool:
    ety = structured.get("etymology")
    if not isinstance(ety, dict):
        return False
    core_image = ety.get("core_image")
    branches = ety.get("branches")
    has_branches = isinstance(branches, list) and len(branches) > 0
    return _core_image_is_generic(word_text, core_image) or not has_branches


def _apply_enriched_etymology(structured: dict, enriched: dict | None) -> dict:
    if not enriched:
        return structured
    ety = structured.setdefault("etymology", {})
    if not isinstance(ety, dict):
        return structured
    core_image = str(enriched.get("core_image", "")).strip()
    branches = enriched.get("branches")
    if core_image:
        ety["core_image"] = core_image
    if isinstance(branches, list) and branches:
        ety["branches"] = branches
    return structured


async def _build_structured_payload(
    word_text: str,
    *,
    scraper: WiktionaryScraper,
    meaning_cache: dict[str, str | None],
    options: IngestOptions | None = None,
) -> dict:
    mode = options or IngestOptions()
    wordnet_data = get_wordnet_snapshot(word_text)
    scraped_data = await _scrape_all(word_text)
    if mode.llm_mode == "async":
        structured = await generate_structured_word_data_async(
            word_text,
            wordnet_data,
            scraped_data,
            example_mode=mode.example_mode,
        )
    else:
        structured = generate_structured_word_data(word_text, wordnet_data, scraped_data)
    if _needs_etymology_enrichment(word_text, structured):
        if mode.llm_mode == "async":
            enriched = await enrich_core_image_and_branches_async(
                word_text=word_text,
                definitions=structured.get("definitions", []),
                etymology_data=structured.get("etymology", {}),
            )
        else:
            enriched = enrich_core_image_and_branches(
                word_text=word_text,
                definitions=structured.get("definitions", []),
                etymology_data=structured.get("etymology", {}),
            )
        structured = _apply_enriched_etymology(structured, enriched)
    structured = _normalize_structured_forms(structured)
    structured = _normalize_structured_derivations_and_phrases(structured)
    if mode.phrase_enrich_mode == "parallel":
        await _enrich_phrase_and_related_meanings_parallel(
            structured,
            scraper,
            meaning_cache,
            concurrency=mode.phrase_parallelism,
        )
    else:
        await _enrich_phrase_and_related_meanings(structured, scraper, meaning_cache)
    return structured


def _find_word(db: Session, normalized: str) -> Word | None:
    return db.scalar(select(Word).where(func.lower(Word.word) == normalized))


async def _create_or_get_word(
    db: Session,
    normalized: str,
    *,
    scraper: WiktionaryScraper,
    payload_cache: dict[str, dict],
    meaning_cache: dict[str, str | None],
    options: IngestOptions | None = None,
) -> tuple[Word, bool]:
    existing = _find_word(db, normalized)
    if existing:
        return existing, False

    structured = payload_cache.get(normalized)
    if structured is None:
        structured = await _build_structured_payload(
            normalized,
            scraper=scraper,
            meaning_cache=meaning_cache,
            options=options,
        )
        payload_cache[normalized] = structured

    existing = _find_word(db, normalized)
    if existing:
        return existing, False

    word = Word(word=normalized)
    db.add(word)
    db.flush()
    apply_structured_payload(db, word, structured)
    return word, True


def _append_phrase_if_missing(db: Session, word: Word, phrase: str, meaning: str) -> bool:
    text = normalize_phrase_text(phrase)
    if not text:
        return False
    phrase_obj = get_or_create_phrase(db, text, meaning)
    before_count = len(word.phrase_links or [])
    link_phrase_to_word(db, word, phrase_obj)
    return len(word.phrase_links or []) > before_count


async def ingest_word_or_phrase(
    db: Session,
    raw_text: str,
    *,
    scraper: WiktionaryScraper,
    payload_cache: dict[str, dict],
    meaning_cache: dict[str, str | None],
    options: IngestOptions | None = None,
) -> IngestResult:
    normalized = _normalize_text(raw_text)
    if not normalized:
        raise ValueError("word is required")

    if not is_phrase_text(normalized):
        word, created = await _create_or_get_word(
            db,
            normalized,
            scraper=scraper,
            payload_cache=payload_cache,
            meaning_cache=meaning_cache,
            options=options,
        )
        return IngestResult(words=[word], created_count=1 if created else 0, split_applied=False)

    tokens = _unique_tokens(normalized)
    phrase_meaning = resolve_meaning_ja_ddgs(normalized, meaning_cache) or ""
    results: list[Word] = []
    created_count = 0
    for token in tokens:
        word, created = await _create_or_get_word(
            db,
            token,
            scraper=scraper,
            payload_cache=payload_cache,
            meaning_cache=meaning_cache,
            options=options,
        )
        if created:
            created_count += 1
        _append_phrase_if_missing(db, word, normalized, phrase_meaning)
        results.append(word)
    return IngestResult(words=results, created_count=created_count, split_applied=True)
