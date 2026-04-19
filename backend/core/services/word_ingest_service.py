from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.models import Word
from core.services.gpt_service import enrich_core_image_and_branches, generate_structured_word_data
from core.services.gpt_service_parallel import (
    ExampleMode,
    enrich_core_image_and_branches_async,
    generate_structured_word_data_async,
)
from core.services.phrase_meaning_service import resolve_meaning_ja_ddgs
from core.services.phrase_service import (
    get_or_create_phrase,
    link_existing_phrases_for_word,
    link_phrase_to_word,
    normalize_phrase_text,
)
from core.services.scraper import build_scrapers
from core.services.scraper.wiktionary import WiktionaryScraper
from core.services.word_data_helpers import (
    enrich_phrase_and_related_meanings as _enrich_phrase_and_related_meanings,
)
from core.services.word_data_helpers import (
    enrich_phrase_and_related_meanings_parallel as _enrich_phrase_and_related_meanings_parallel,
)
from core.services.word_data_helpers import (
    normalize_structured_derivations_and_phrases as _normalize_structured_derivations_and_phrases,
)
from core.services.word_data_helpers import normalize_structured_forms as _normalize_structured_forms
from core.services.word_service import apply_structured_payload
from core.services.wordnet_service import get_wordnet_snapshot
from core.utils.dbg_log import dbg as _dbg

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
    return [t for t in re.split(r"\s+", str(text or "").strip()) if t]


def is_phrase_text(text: str) -> bool:
    return len(_tokenize(text)) >= 2


def _unique_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for token in _tokenize(text):
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(token)
    return unique


_PHRASE_PLACEHOLDER_TOKENS = {"A", "B", "C", "O", "S", "~"}


def is_placeholder_token(token: str) -> bool:
    value = str(token or "").strip()
    if not value:
        return False
    if value == "~":
        return True
    normalized = value
    if normalized.endswith("'s") or normalized.endswith("’s"):
        normalized = normalized[:-2]
    return normalized in _PHRASE_PLACEHOLDER_TOKENS


def _canonicalize_phrase_token(token: str) -> str:
    value = str(token or "").strip()
    if not value:
        return value
    if value == "~":
        return "~"
    normalized = value
    if normalized.endswith("'s") or normalized.endswith("’s"):
        base = normalized[:-2]
        if base in _PHRASE_PLACEHOLDER_TOKENS:
            return f"{base}'s"
    if normalized in _PHRASE_PLACEHOLDER_TOKENS:
        return normalized
    return value


def normalize_phrase_for_store(text: str) -> str:
    raw_tokens = [t for t in re.split(r"\s+", str(text or "").strip()) if t]
    if not raw_tokens:
        return ""
    canonical = [_canonicalize_phrase_token(token) for token in raw_tokens]
    return normalize_phrase_text(" ".join(canonical))


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
    # region agent log
    _ety_initial = structured.get("etymology") if isinstance(structured, dict) else None
    _branches_initial = _ety_initial.get("branches") if isinstance(_ety_initial, dict) else None
    _core_image_initial = _ety_initial.get("core_image") if isinstance(_ety_initial, dict) else None
    _dbg(
        "word_ingest_service.py:_build_structured_payload(after_llm)",
        "structured payload built",
        {
            "word": word_text,
            "llm_mode": mode.llm_mode,
            "definitions_count": len(structured.get("definitions", []) or []) if isinstance(structured, dict) else None,
            "core_image": _core_image_initial,
            "branches_count": len(_branches_initial) if isinstance(_branches_initial, list) else None,
            "raw_description_len": len(str((_ety_initial or {}).get("raw_description") or "")) if isinstance(_ety_initial, dict) else 0,
        },
        hypothesis_id="A",
    )
    # endregion
    _need_enrich = _needs_etymology_enrichment(word_text, structured)
    # region agent log
    _dbg(
        "word_ingest_service.py:_build_structured_payload(needs_enrich)",
        "needs_etymology_enrichment decision",
        {"word": word_text, "needs_enrich": _need_enrich, "llm_mode": mode.llm_mode},
        hypothesis_id="C",
    )
    # endregion
    if _need_enrich:
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
        # region agent log
        _enr_branches = (enriched or {}).get("branches") if isinstance(enriched, dict) else None
        _dbg(
            "word_ingest_service.py:_build_structured_payload(enriched_received)",
            "enrichment result",
            {
                "word": word_text,
                "llm_mode": mode.llm_mode,
                "enriched_is_none": enriched is None,
                "enriched_core_image": (enriched or {}).get("core_image") if isinstance(enriched, dict) else None,
                "enriched_branches_count": len(_enr_branches) if isinstance(_enr_branches, list) else 0,
            },
            hypothesis_id="B",
        )
        # endregion
        structured = _apply_enriched_etymology(structured, enriched)
    # region agent log
    _ety_final = structured.get("etymology") if isinstance(structured, dict) else None
    _branches_final = _ety_final.get("branches") if isinstance(_ety_final, dict) else None
    _dbg(
        "word_ingest_service.py:_build_structured_payload(final)",
        "final structured payload",
        {
            "word": word_text,
            "llm_mode": mode.llm_mode,
            "final_branches_count": len(_branches_final) if isinstance(_branches_final, list) else 0,
            "final_core_image": _ety_final.get("core_image") if isinstance(_ety_final, dict) else None,
        },
        hypothesis_id="A",
    )
    # endregion
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


async def build_structured_payloads_parallel(
    words: list[str],
    *,
    scraper: WiktionaryScraper,
    meaning_cache: dict[str, str | None],
    options: IngestOptions | None = None,
    concurrency: int = 4,
) -> dict[str, dict]:
    """Build structured payloads concurrently for normalized unique words."""
    if not words:
        return {}
    limit = max(1, int(concurrency))
    sem = asyncio.Semaphore(limit)
    normalized_words: list[str] = []
    seen: set[str] = set()
    for word in words:
        normalized = _normalize_text(word)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_words.append(normalized)

    async def _build_one(word_text: str) -> tuple[str, dict]:
        async with sem:
            payload = await _build_structured_payload(
                word_text,
                scraper=scraper,
                meaning_cache=meaning_cache,
                options=options,
            )
            return word_text, payload

    built = await asyncio.gather(*[_build_one(word_text) for word_text in normalized_words])
    return {word_text: payload for word_text, payload in built}


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
        # region agent log
        _ety = existing.etymology
        _branches = list(_ety.branches) if _ety else []
        _dbg(
            "word_ingest_service.py:_create_or_get_word(existing_returned)",
            "returning EXISTING word without rebuild",
            {
                "word": normalized,
                "definitions_count": len(existing.definitions or []),
                "branches_count": len(_branches),
                "core_image": _ety.core_image if _ety else None,
                "derivations_count": len(existing.derivations or []),
                "phrases_count": len(existing.phrases or []),
            },
            hypothesis_id="F",
        )
        # endregion
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
        # region agent log
        _dbg(
            "word_ingest_service.py:_create_or_get_word(existing_returned_after_build)",
            "EXISTING found AFTER build (race) - skipping apply_structured_payload!",
            {"word": normalized},
            hypothesis_id="G",
        )
        # endregion
        return existing, False

    word = Word(word=normalized)
    db.add(word)
    db.flush()
    apply_structured_payload(db, word, structured)
    link_existing_phrases_for_word(db, word)
    # region agent log
    _ety_after = word.etymology
    _branches_after = list(_ety_after.branches) if _ety_after else []
    _dbg(
        "word_ingest_service.py:_create_or_get_word(after_apply)",
        "after apply_structured_payload",
        {
            "word": normalized,
            "definitions_count": len(word.definitions or []),
            "branches_count": len(_branches_after),
            "core_image": _ety_after.core_image if _ety_after else None,
            "derivations_count": len(word.derivations or []),
            "phrases_count": len(word.phrases or []),
        },
        hypothesis_id="H",
    )
    # endregion
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

    phrase_text = normalize_phrase_for_store(raw_text)
    if not phrase_text:
        raise ValueError("phrase is required")
    tokens = _unique_tokens(raw_text)
    phrase_meaning = (await resolve_meaning_ja_ddgs(phrase_text, meaning_cache)) or ""
    results: list[Word] = []
    created_count = 0
    for token in tokens:
        if is_placeholder_token(token):
            continue
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
        _append_phrase_if_missing(db, word, phrase_text, phrase_meaning)
        results.append(word)
    return IngestResult(words=results, created_count=created_count, split_applied=True)
