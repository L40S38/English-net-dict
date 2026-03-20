"""Import inflection relationships from a word list.

Usage:
    uv run python -m app.scripts.batch_inflection_import --input app/scripts/words_to_add.txt
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path

from sqlalchemy import func, select

from app.models import Word
from app.scripts.patch_base import add_common_args, create_session, prepare_database
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.word_ingest_service import ingest_word_or_phrase
from app.services.word_merge_service import link_to_lemma, merge_into_lemma

VALID_ACTIONS = {"merge", "link", "register_as_is"}


def _find_word(db, text: str) -> Word | None:
    normalized = text.strip().lower()
    if not normalized:
        return None
    return db.scalar(select(Word).where(func.lower(Word.word) == normalized))


def _read_rows(file_path: Path) -> list[dict[str, str]]:
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    with file_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


async def run(
    file_path: Path,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
) -> None:
    prepare_database()
    db = create_session()
    added = 0
    skipped = 0
    errors = 0
    scraper = WiktionaryScraper()
    phrase_cache: dict[str, str | None] = {}
    payload_cache: dict[str, dict] = {}

    try:
        rows = _read_rows(file_path)
        if word_filter:
            target = word_filter.strip().lower()
            rows = [row for row in rows if str(row.get("word", "")).strip().lower() == target]
        if limit is not None:
            rows = rows[:limit]
        total = len(rows)
        if total == 0:
            print("No target rows found in input.")
            return

        print(f"Targets: {total}" + (" (dry-run)" if dry_run else ""))
        for idx, row in enumerate(rows, start=1):
            word = str(row.get("word", "")).strip()
            action = str(row.get("action", "")).strip()
            suggestion = str(row.get("suggestion", "")).strip()
            lemma = str(row.get("lemma", "")).strip()
            selected_lemma = str(row.get("selected_lemma", "")).strip()
            inflection_type = str(row.get("inflection_type", "")).strip() or "inflection"
            if not word:
                skipped += 1
                continue
            if not action:
                action = suggestion
                if action:
                    print(f"  [{idx}/{total}] {word} action is empty -> fallback to suggestion '{action}'")
            if action not in VALID_ACTIONS:
                errors += 1
                print(f"  [{idx}/{total}] {word} ERROR: invalid action '{action}'")
                continue

            try:
                if action == "register_as_is":
                    result = await ingest_word_or_phrase(
                        db,
                        word,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    added += result.created_count
                    print(f"  [{idx}/{total}] {word} REGISTER_AS_IS ({result.created_count})")
                elif action == "merge":
                    lemma_target = selected_lemma or lemma or word
                    lemma_result = await ingest_word_or_phrase(
                        db,
                        lemma_target,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    lemma_word = _find_word(db, lemma_target)
                    inflected_word = _find_word(db, word)
                    if lemma_word and inflected_word and lemma_word.id != inflected_word.id:
                        merge_into_lemma(db, inflected_word, lemma_word)
                    added += lemma_result.created_count
                    print(f"  [{idx}/{total}] {word} MERGE -> {lemma_target}")
                elif action == "link":
                    lemma_target = selected_lemma or lemma
                    if not lemma_target:
                        raise ValueError("lemma is required for link action")
                    lemma_result = await ingest_word_or_phrase(
                        db,
                        lemma_target,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    inflected_result = await ingest_word_or_phrase(
                        db,
                        word,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    lemma_word = _find_word(db, lemma_target)
                    inflected_word = _find_word(db, word)
                    if not lemma_word or not inflected_word:
                        raise ValueError("failed to resolve lemma/inflected words for link")
                    link_to_lemma(db, inflected_word, lemma_word, inflection_type)
                    added += lemma_result.created_count + inflected_result.created_count
                    print(f"  [{idx}/{total}] {word} LINK -> {lemma_target}")

                if dry_run:
                    db.rollback()
                else:
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"  [{idx}/{total}] {word} ERROR: {exc}")
    finally:
        db.close()

    print("---")
    print(f"ADDED: {added}")
    print(f"SKIPPED: {skipped}")
    print(f"ERRORS: {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import words using action columns from inflection report CSV")
    add_common_args(parser)
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).resolve().parent / "batch_inflection_report.csv",
        help="Input CSV path",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            file_path=args.file,
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
        )
    )


if __name__ == "__main__":
    main()
