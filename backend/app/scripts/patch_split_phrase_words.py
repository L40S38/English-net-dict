"""
パッチスクリプト:
空白を含む誤登録熟語を単語へ分割して再登録し、
元熟語を分割先単語の成句欄へ意味付きで移植してから削除する。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re

from sqlalchemy import func, select

from app.config import settings
from app.models import Word
from app.routers.words import _apply_enriched_etymology, _needs_etymology_enrichment
from app.schemas import WordCreateRequest
from app.scripts.patch_base import (
    add_common_args,
    create_session,
    is_multi_token,
    load_words,
    normalize_phrase_entries,
    prepare_database,
    scrape_all,
)
from app.services.gpt_service import enrich_core_image_and_branches, generate_structured_word_data
from app.services.phrase_meaning_service import resolve_meaning_ja_ddgs
from app.services.word_service import apply_structured_payload
from app.services.wordnet_service import get_wordnet_snapshot


def _tokenize_phrase(phrase: str) -> list[str]:
    tokens = [t.strip().lower() for t in re.split(r"\s+", phrase.strip()) if t.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique


async def _build_structured_payload(
    word_text: str,
) -> dict:
    wordnet_data = get_wordnet_snapshot(word_text)
    scraped_data = await scrape_all(word_text)
    structured = generate_structured_word_data(word_text, wordnet_data, scraped_data)
    if _needs_etymology_enrichment(word_text, structured):
        enriched = enrich_core_image_and_branches(
            word_text=word_text,
            definitions=structured.get("definitions", []),
            etymology_data=structured.get("etymology", {}),
        )
        structured = _apply_enriched_etymology(structured, enriched)
    forms = structured.get("forms")
    if isinstance(forms, dict):
        forms["phrases"] = normalize_phrase_entries(forms.get("phrases"))
        structured["forms"] = forms
    return structured


def _find_word(db, word_text: str) -> Word | None:
    normalized = word_text.strip().lower()
    if not normalized:
        return None
    return db.scalar(select(Word).where(func.lower(Word.word) == normalized))


async def run(dry_run: bool = False, limit: int | None = None, word_filter: str | None = None) -> None:
    logging.getLogger("app.services.web_word_search").setLevel(logging.ERROR)
    prepare_database()
    db = create_session()
    ddgs_cache: dict[str, str | None] = {}
    payload_cache: dict[str, dict] = {}

    added_words = 0
    skipped_words = 0
    phrases_appended = 0
    phrases_skipped = 0
    deleted_phrases = 0
    errors = 0

    try:
        base_limit = 1 if word_filter else None
        words = load_words(db, word_filter=word_filter, limit=base_limit)
        targets = [word for word in words if is_multi_token(word.word)]
        if limit is not None:
            targets = targets[:limit]
        total = len(targets)
        if total == 0:
            print("対象の熟語がありません。")
            print(f"接続先DB: {settings.database_url}")
            print("想定データがある場合は、DATABASE_URL または data/db/data.db を確認してください。")
            return
        print(f"対象熟語: {total} 件" + (" (dry-run)" if dry_run else ""))

        for idx, phrase_word in enumerate(targets, start=1):
            phrase_text = phrase_word.word.strip()
            try:
                tokens = _tokenize_phrase(phrase_text)
                if not tokens:
                    print(f"  [{idx}/{total}] {phrase_text} SKIP (empty tokens)")
                    db.rollback()
                    continue

                phrase_meaning = resolve_meaning_ja_ddgs(phrase_text, ddgs_cache)
                created_or_existing: list[Word] = []
                local_appended = 0
                local_phrase_skipped = 0

                for token in tokens:
                    existing = _find_word(db, token)
                    if existing:
                        skipped_words += 1
                        created_or_existing.append(existing)
                        continue

                    structured = payload_cache.get(token)
                    if structured is None:
                        structured = await _build_structured_payload(token)
                        payload_cache[token] = structured
                    new_word = Word(word=WordCreateRequest(word=token).word)
                    db.add(new_word)
                    db.flush()
                    apply_structured_payload(db, new_word, structured)
                    added_words += 1
                    created_or_existing.append(new_word)

                for token_word in created_or_existing:
                    forms = dict(token_word.forms or {})
                    phrases = normalize_phrase_entries(forms.get("phrases"))
                    key_set = {entry["phrase"].strip().lower() for entry in phrases if entry.get("phrase", "").strip()}
                    phrase_key = phrase_text.lower()
                    if phrase_key in key_set:
                        phrases_skipped += 1
                        local_phrase_skipped += 1
                        continue
                    phrases.append({"phrase": phrase_text, "meaning": phrase_meaning or ""})
                    forms["phrases"] = phrases
                    token_word.forms = forms
                    phrases_appended += 1
                    local_appended += 1

                db.delete(phrase_word)
                deleted_phrases += 1

                if dry_run:
                    print(
                        f"  [{idx}/{total}] {phrase_text} WOULD_UPDATE "
                        f"(tokens={len(tokens)} appended={local_appended} phrase_skipped={local_phrase_skipped} delete=1)"
                    )
                    db.rollback()
                else:
                    db.commit()
                    print(
                        f"  [{idx}/{total}] {phrase_text} UPDATED "
                        f"(tokens={len(tokens)} appended={local_appended} phrase_skipped={local_phrase_skipped} delete=1)"
                    )
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"  [{idx}/{total}] {phrase_text} ERROR: {exc}")
    finally:
        db.close()

    print("---")
    print(f"ADDED_WORDS: {added_words}")
    print(f"SKIPPED_WORDS: {skipped_words}")
    print(f"PHRASES_APPENDED: {phrases_appended}")
    print(f"PHRASES_SKIPPED: {phrases_skipped}")
    print(f"DELETED_PHRASES: {deleted_phrases}")
    print(f"ERRORS: {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="熟語誤登録を単語分割へ移行して成句へ移植")
    add_common_args(parser)
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word))


if __name__ == "__main__":
    main()
