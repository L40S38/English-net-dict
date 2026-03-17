"""
パッチスクリプト: 登録済み単語のコアイメージと意味の分岐をLLMで補完する。

使い方（backend をカレントに）:
  python -m app.scripts.patch_enrich_etymology_map [--dry-run] [--limit N] [--word WORD] [--only-missing]
"""

from __future__ import annotations

import argparse

from sqlalchemy.orm import joinedload

from app.config import settings
from app.models import Etymology, EtymologyVariant, Word

from app.scripts.patch_base import (
    add_common_args,
    create_session,
    load_words,
    prepare_database,
    print_diffs,
    print_summary,
)
from app.scripts.updaters import enrich_etymology_map

JOINEDLOADS = (
    joinedload(Word.definitions),
    joinedload(Word.etymology).options(
        joinedload(Etymology.component_items),
        joinedload(Etymology.branches),
        joinedload(Etymology.variants).joinedload(EtymologyVariant.component_items),
        joinedload(Etymology.variants).joinedload(EtymologyVariant.component_meanings),
        joinedload(Etymology.variants).joinedload(EtymologyVariant.language_chain_links),
        joinedload(Etymology.language_chain_links),
        joinedload(Etymology.component_meanings),
    ),
)


def run(
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
    only_missing: bool = False,
) -> None:
    if not settings.openai_api_key:
        print("OPENAI_API_KEY が未設定のため実行できません。")
        return

    prepare_database()
    db = create_session()
    updated = 0
    skipped = 0
    errors = 0
    try:
        words = load_words(db, word_filter=word_filter, limit=limit, joinedloads=JOINEDLOADS)
        total = len(words)
        if total == 0:
            print("登録単語がありません。")
            print(f"接続先DB: {settings.database_url}")
            return
        print(f"対象: {total} 件" + (" (dry-run)" if dry_run else ""))

        for idx, word in enumerate(words, start=1):
            try:
                diffs = enrich_etymology_map(db, word, only_missing=only_missing)
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
    parser = argparse.ArgumentParser(description="登録単語のコアイメージ・意味の分岐をLLMで補完")
    add_common_args(parser)
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="core_image が未設定/汎用値、または branches が空の単語のみ処理",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word, only_missing=args.only_missing)


if __name__ == "__main__":
    main()

