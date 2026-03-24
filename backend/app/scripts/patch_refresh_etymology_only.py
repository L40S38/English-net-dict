"""
パッチスクリプト: 登録済み単語の語源データのみを再取得する。
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.orm import joinedload

from app.config import settings
from app.models import Etymology, Word
from app.scripts.patch_base import (
    add_common_args,
    create_session,
    load_words,
    prepare_database,
    print_diffs,
    print_summary,
)
from app.scripts.updaters import enrich_etymology_map, refresh_etymology_only
from app.services.scraper.wiktionary import WiktionaryScraper

JOINEDLOADS = (
    joinedload(Word.etymology).joinedload(Etymology.component_items),
    joinedload(Word.etymology).joinedload(Etymology.branches),
    joinedload(Word.etymology).joinedload(Etymology.variants),
)


def _load_word_set_from_file(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"Word list file not found: {path}")
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        words.add(text.lower())
    return words


def _select_targets(
    db,
    *,
    word_filter: str | None,
    word_list: Path | None,
    limit: int | None,
    empty_only: bool,
) -> list[Word]:
    words = load_words(db, word_filter=word_filter, limit=None, joinedloads=JOINEDLOADS)
    if word_list is not None:
        selected = _load_word_set_from_file(word_list)
        words = [word for word in words if word.word.lower() in selected]
    if empty_only:
        words = [
            word
            for word in words
            if (word.etymology is None) or len(word.etymology.component_items or []) == 0
        ]
    if limit is not None:
        words = words[:limit]
    return words


async def run(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
    all_words: bool = False,  # noqa: ARG001 - 明示的指定を受けるため保持
    word_list: Path | None = None,
    empty_only: bool = False,
    enrich_if_empty: bool = False,
    delay: float = 0.0,
) -> None:
    prepare_database()
    db = create_session()
    scraper = WiktionaryScraper()
    updated = 0
    skipped = 0
    errors = 0
    try:
        words = _select_targets(
            db,
            word_filter=word_filter,
            word_list=word_list,
            limit=limit,
            empty_only=empty_only,
        )
        total = len(words)
        if total == 0:
            print("対象単語がありません。")
            print(f"接続先DB: {settings.database_url}")
            print("想定データがある場合は、DATABASE_URL または data/db/data.db を確認してください。")
            return
        print(f"対象: {total} 件" + (" (dry-run)" if dry_run else ""))

        for idx, word in enumerate(words, start=1):
            try:
                if idx > 1 and delay > 0:
                    await asyncio.sleep(delay)
                # Retry policy is centralized in WiktionaryScraper._fetch_parse.
                # Do not retry at script layer (e.g., parse payload not found should fail fast).
                diffs = await refresh_etymology_only(db, word, scraper=scraper)
                if enrich_if_empty:
                    enrich_diffs = enrich_etymology_map(db, word, only_missing=True)
                    diffs.extend(enrich_diffs)
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
    parser = argparse.ArgumentParser(description="登録単語の語源データのみを再取得")
    add_common_args(parser)
    parser.add_argument("--all", action="store_true", help="全単語を対象として処理する（既定動作）。")
    parser.add_argument("--word-list", type=Path, default=None, help="対象単語を列挙したテキストファイル。")
    parser.add_argument(
        "--empty-only",
        action="store_true",
        help="etymology component が空の単語のみ対象にする。",
    )
    parser.add_argument(
        "--enrich-if-empty",
        action="store_true",
        help="core_image / branches が不足している場合のみ補完を試みる。",
    )
    parser.add_argument("--delay", type=float, default=0.0, help="単語ごとの待機秒数。")
    args = parser.parse_args()
    asyncio.run(
        run(
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
            all_words=args.all,
            word_list=args.word_list,
            empty_only=args.empty_only,
            enrich_if_empty=args.enrich_if_empty,
            delay=args.delay,
        )
    )


if __name__ == "__main__":
    main()
