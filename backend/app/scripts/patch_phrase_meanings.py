"""
パッチスクリプト: 成句・慣用句/熟語の意味を補完する。
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy.orm import joinedload

from app.models import Word
from app.services.scraper.wiktionary import WiktionaryScraper

from app.scripts.patch_base import (
    add_common_args,
    create_session,
    load_words,
    prepare_database,
    print_diffs,
    print_summary,
)
from app.scripts.updaters import enrich_phrase_meanings

JOINEDLOADS = (
    joinedload(Word.derivations),
    joinedload(Word.related_words),
)


async def run(dry_run: bool = False, limit: int | None = None, word_filter: str | None = None) -> None:
    logging.getLogger("app.services.web_word_search").setLevel(logging.ERROR)
    prepare_database()
    db = create_session()
    scraper = WiktionaryScraper()
    cache: dict[str, str | None] = {}
    updated = 0
    skipped = 0
    errors = 0
    try:
        words = load_words(db, word_filter=word_filter, limit=limit, joinedloads=JOINEDLOADS)
        total = len(words)
        if total == 0:
            print("登録単語がありません。")
            return
        print(f"対象: {total} 件" + (" (dry-run)" if dry_run else ""))

        for idx, word in enumerate(words, start=1):
            try:
                diffs = await enrich_phrase_meanings(db, word, scraper=scraper, cache=cache)
                if not diffs:
                    skipped += 1
                    print(f"  [{idx}/{total}] {word.word} SKIP (no diff)")
                    if dry_run:
                        db.rollback()
                    continue

                if dry_run:
                    print(f"  [{idx}/{total}] {word.word} WOULD_UPDATE")
                    print_diffs(diffs)
                    db.rollback()
                    updated += 1
                    continue

                db.commit()
                updated += 1
                print(f"  [{idx}/{total}] {word.word} UPDATED")
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"  [{idx}/{total}] {word.word} ERROR: {exc}")
    finally:
        db.close()
    print_summary(updated, skipped, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="成句・慣用句/熟語の意味を補完")
    add_common_args(parser)
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word))


if __name__ == "__main__":
    main()
