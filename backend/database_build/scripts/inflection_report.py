from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.orm import joinedload

from core.models import Word
from database_build.ops.common import create_session, prepare_database
from database_build.ops.inflection import (
    apply_known_inflection_fixes,
    build_inflection_report_rows,
    write_inflection_report,
)
from database_build.selectors import load_words


async def run(
    db_path: str | None,
    output: Path,
    *,
    word_filter: str | None = None,
    limit: int | None = None,
    apply_known_fixes: bool = False,
    dry_run: bool = False,
    use_db_near: bool = False,
    spellchecker_merge_db: bool = False,
) -> None:
    prepare_database(db_path)
    db = create_session(db_path)
    try:
        words = load_words(db, word_filter=word_filter, limit=limit, joinedloads=(joinedload(Word.etymology),))
        rows = await build_inflection_report_rows(
            words,
            db,
            use_db_near=use_db_near,
            spellchecker_merge_db=spellchecker_merge_db,
        )
        if apply_known_fixes:
            updated, skipped = apply_known_inflection_fixes(db)
            print(f"KNOWN_FIXES: updated={updated} skipped={skipped}")
        if dry_run:
            db.rollback()
            print(f"ROWS: {len(rows)} (dry-run)")
            return
        write_inflection_report(output, rows)
        db.commit()
        print(f"Report written: {output}")
        print(f"Rows: {len(rows)}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate inflection report from DB words")
    parser.add_argument("--db", type=str, default=None, help="DB path or SQLAlchemy URL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--word", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply-known-fixes", action="store_true")
    parser.add_argument("--db-near", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--spellchecker-merge-db", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args()
    asyncio.run(
        run(
            args.db,
            args.output,
            word_filter=args.word,
            limit=args.limit,
            apply_known_fixes=args.apply_known_fixes,
            dry_run=args.dry_run,
            use_db_near=args.db_near,
            spellchecker_merge_db=args.spellchecker_merge_db,
        )
    )


if __name__ == "__main__":
    main()
