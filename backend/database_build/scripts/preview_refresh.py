from __future__ import annotations

import argparse
import asyncio

from sqlalchemy.orm import joinedload

from core.models import Etymology, Word
from core.services.scraper.wiktionary import WiktionaryScraper
from database_build.ops.common import create_session, prepare_database
from database_build.ops.word import refresh_word_data
from database_build.reporting import print_diffs
from database_build.selectors import load_words


async def run(db_path: str | None, word: str | None, limit: int | None) -> None:
    prepare_database(db_path)
    db = create_session(db_path)
    scraper = WiktionaryScraper()
    cache: dict[str, str | None] = {}
    try:
        words = load_words(
            db,
            word_filter=word,
            limit=limit,
            joinedloads=(
                joinedload(Word.definitions),
                joinedload(Word.etymology).joinedload(Etymology.component_items),
                joinedload(Word.derivations),
                joinedload(Word.related_words),
                joinedload(Word.images),
            ),
        )
        for idx, item in enumerate(words, start=1):
            try:
                diffs = await refresh_word_data(db, item, scraper=scraper, cache=cache)
                if not diffs:
                    print(f"[{idx}/{len(words)}] {item.word} SKIP (no diff)")
                    db.rollback()
                    continue
                print(f"[{idx}/{len(words)}] {item.word} WOULD_UPDATE")
                print_diffs(diffs)
                db.rollback()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                print(f"[{idx}/{len(words)}] {item.word} ERROR: {exc}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview refresh result without updating DB")
    parser.add_argument("--db", type=str, default=None, help="DB path or SQLAlchemy URL")
    parser.add_argument("--word", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(run(args.db, args.word, args.limit))


if __name__ == "__main__":
    main()
