"""
パッチスクリプト: 登録済み単語の（画像以外の）データを一括再取得する。
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy.orm import joinedload

from app.config import settings
from app.models import Etymology, Word
from app.services.scraper.wiktionary import WiktionaryScraper

from app.scripts.patch_base import (
    add_common_args,
    create_session,
    load_words,
    prepare_database,
    print_diffs,
    print_summary,
)
from app.scripts.updaters import refresh_word_data

JOINEDLOADS = (
    joinedload(Word.definitions),
    joinedload(Word.etymology).joinedload(Etymology.component_items),
    joinedload(Word.derivations),
    joinedload(Word.related_words),
    joinedload(Word.images),
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
            print(f"接続先DB: {settings.database_url}")
            print("想定データがある場合は、DATABASE_URL または data/db/data.db を確認してください。")
            return
        print(f"対象: {total} 件" + (" (dry-run)" if dry_run else ""))

        for idx, word in enumerate(words, start=1):
            try:
                diffs = await refresh_word_data(db, word, scraper=scraper, cache=cache)
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
    parser = argparse.ArgumentParser(description="登録単語の（画像以外の）データを一括再取得")
    add_common_args(parser)
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word))


if __name__ == "__main__":
    main()
