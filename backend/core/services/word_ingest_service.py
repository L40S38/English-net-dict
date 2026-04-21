from __future__ import annotations

import asyncio
import json as _debug_json
import os as _debug_os
import re
import sqlite3 as _debug_sqlite3
import time as _debug_time
from dataclasses import dataclass
from pathlib import Path as _DebugPath
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError as _DebugOperationalError
from sqlalchemy.orm import Session

# #region agent log
_DEBUG_LOG_PATH = _DebugPath(__file__).resolve().parents[3] / "debug-3d94a9.log"


def _debug_log(hypothesis_id: str, message: str, data: dict | None = None, location: str = "word_ingest_service.py") -> None:
    try:
        payload = {
            "sessionId": "3d94a9",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(_debug_time.time() * 1000),
            "pid": _debug_os.getpid(),
        }
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(_debug_json.dumps(payload, default=str, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion

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
from core.services.word_service import apply_structured_payload, enrich_etymology as enrich_existing_etymology
from core.services.wordnet_service import get_wordnet_snapshot

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
    _need_enrich = _needs_etymology_enrichment(word_text, structured)
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
    backfill_existing_etymology: bool = False,
) -> tuple[Word, bool]:
    # #region agent log
    _entry_ts = _debug_time.monotonic()
    _debug_log(
        "H1",
        "create_or_get_word_entry",
        {"normalized": normalized, "backfill": backfill_existing_etymology},
        location="word_ingest_service.py:_create_or_get_word:entry",
    )
    # #endregion
    existing = _find_word(db, normalized)
    # #region agent log
    _debug_log(
        "H1",
        "after_find_word",
        {
            "normalized": normalized,
            "existing_id": getattr(existing, "id", None),
            "elapsed_s": round(_debug_time.monotonic() - _entry_ts, 3),
        },
        location="word_ingest_service.py:_create_or_get_word:after_find",
    )
    # #endregion
    if existing:
        _existing_ety = existing.etymology
        _existing_branches = list(_existing_ety.branches) if _existing_ety else []
        _needs_etymology_backfill = (
            _existing_ety is None
            or len(_existing_branches) == 0
            or _core_image_is_generic(existing.word, _existing_ety.core_image if _existing_ety else None)
        )
        if backfill_existing_etymology and _needs_etymology_backfill:
            enrich_existing_etymology(db, existing)
            db.flush()
            _refreshed = _find_word(db, normalized) or existing
            return _refreshed, False
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
    # #region agent log
    _flush_started = _debug_time.monotonic()
    _elapsed_since_entry = _flush_started - _entry_ts
    try:
        _conn = db.connection()
        _in_tx = bool(db.in_transaction())
        _raw_conn = getattr(_conn, "connection", None)
        _raw_info = str(type(_raw_conn))
    except Exception as _conn_exc:  # noqa: BLE001
        _in_tx = None
        _raw_info = f"conn_err:{_conn_exc}"
    _debug_log(
        "H1",
        "pre_flush_state",
        {
            "normalized": normalized,
            "elapsed_since_create_or_get_entry_s": round(_elapsed_since_entry, 3),
            "in_transaction": _in_tx,
            "raw_conn_type": _raw_info,
        },
        location="word_ingest_service.py:_create_or_get_word:pre_flush",
    )
    try:
        db.flush()
    except _DebugOperationalError as _op_exc:
        _flush_failed_at = _debug_time.monotonic()
        _orig = getattr(_op_exc, "orig", None)
        _err_code = None
        _err_name = None
        _err_msg = None
        if isinstance(_orig, _debug_sqlite3.OperationalError):
            _err_code = getattr(_orig, "sqlite_errorcode", None)
            _err_name = getattr(_orig, "sqlite_errorname", None)
            _err_msg = str(_orig)
        _debug_log(
            "H1",
            "flush_operational_error",
            {
                "normalized": normalized,
                "elapsed_since_create_or_get_entry_s": round(_flush_failed_at - _entry_ts, 3),
                "elapsed_flush_wait_s": round(_flush_failed_at - _flush_started, 3),
                "sqlite_errorcode": _err_code,
                "sqlite_errorname": _err_name,
                "sqlite_error_msg": _err_msg,
            },
            location="word_ingest_service.py:_create_or_get_word:flush_except",
        )
        raise
    _flush_done = _debug_time.monotonic()
    _debug_log(
        "H1",
        "flush_ok",
        {
            "normalized": normalized,
            "elapsed_flush_s": round(_flush_done - _flush_started, 3),
        },
        location="word_ingest_service.py:_create_or_get_word:flush_ok",
    )
    # #endregion
    apply_structured_payload(db, word, structured)
    link_existing_phrases_for_word(db, word)
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
            backfill_existing_etymology=False,
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
            backfill_existing_etymology=True,
        )
        if created:
            created_count += 1
        _append_phrase_if_missing(db, word, phrase_text, phrase_meaning)
        results.append(word)
    return IngestResult(words=results, created_count=created_count, split_applied=True)
