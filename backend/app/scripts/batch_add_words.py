"""
Offline batch import script: add words listed in a text file.

uv run python -m app.scripts.batch_add_words --file app/scripts/words_to_add.txt
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

# Run from backend directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models import Word
from app.scripts.patch_base import add_common_args, create_session, prepare_database
from app.services.lemma_service import detect_lemma, suggest_inflection_action
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.word_ingest_service import ingest_word_or_phrase
from app.services.word_merge_service import link_to_lemma, merge_into_lemma


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


async def run(
    file_path: Path,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
    skip_inflection_check: bool = False,
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
        raw_words = _read_word_list(file_path)
        targets = _select_words(raw_words, word_filter=word_filter, limit=limit)
        total = len(targets)
        if total == 0:
            print("No target words found in input.")
            return

        print(f"Targets: {total}" + (" (dry-run)" if dry_run else ""))
        for idx, source in enumerate(targets, start=1):
            normalized = source.strip().lower()
            if not normalized:
                skipped += 1
                print(f"  [{idx}/{total}] {source} SKIPPED (blank)")
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
                        if lemma_result.created_count > 0:
                            added += lemma_result.created_count
                            print(f"  [{idx}/{total}] {normalized} MERGED -> {lemma_target}")
                        else:
                            skipped += 1
                            print(f"  [{idx}/{total}] {normalized} MERGE-SKIPPED (lemma exists)")
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
                            link_to_lemma(
                                db,
                                inflected_word,
                                lemma_word,
                                candidate.inflection_type or "inflection",
                            )
                        created_total = lemma_result.created_count + inflected_result.created_count
                        if created_total > 0:
                            added += created_total
                            print(f"  [{idx}/{total}] {normalized} LINKED -> {lemma_target}")
                        else:
                            skipped += 1
                            print(f"  [{idx}/{total}] {normalized} LINK-SKIPPED (exists)")
                        if dry_run:
                            db.rollback()
                        else:
                            db.commit()
                        continue

                if dry_run:
                    result = await ingest_word_or_phrase(
                        db,
                        normalized,
                        scraper=scraper,
                        payload_cache=payload_cache,
                        meaning_cache=phrase_cache,
                    )
                    if result.created_count > 0:
                        added += result.created_count
                        print(f"  [{idx}/{total}] {normalized} WOULD_ADD ({result.created_count})")
                    else:
                        skipped += 1
                        print(f"  [{idx}/{total}] {normalized} SKIPPED (exists)")
                    db.rollback()
                    continue

                result = await ingest_word_or_phrase(
                    db,
                    normalized,
                    scraper=scraper,
                    payload_cache=payload_cache,
                    meaning_cache=phrase_cache,
                )
                if result.created_count > 0:
                    db.commit()
                    added += result.created_count
                    print(f"  [{idx}/{total}] {normalized} ADDED ({result.created_count})")
                else:
                    skipped += 1
                    db.rollback()
                    print(f"  [{idx}/{total}] {normalized} SKIPPED (exists)")
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"  [{idx}/{total}] {normalized} ERROR: {exc}")
    finally:
        db.close()

    print("---")
    print(f"ADDED: {added}")
    print(f"SKIPPED: {skipped}")
    print(f"ERRORS: {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add new words offline from a text file")
    add_common_args(parser)
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).resolve().parent / "words_to_add.txt",
        help="Input text file path (one word per line)",
    )
    parser.add_argument(
        "--skip-inflection-check",
        action="store_true",
        help="Skip inflection-to-lemma check and keep legacy behavior",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            file_path=args.file,
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
            skip_inflection_check=args.skip_inflection_check,
        )
    )


if __name__ == "__main__":
    main()
