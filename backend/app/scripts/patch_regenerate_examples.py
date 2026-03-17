"""
パッチスクリプト: 登録済み単語のプレースホルダー例文を再生成する。
"""
from __future__ import annotations

import argparse

from sqlalchemy.orm import joinedload

from app.config import settings
from app.models import Word
from app.services.gpt_service import _fill_empty_examples_with_gpt
from app.scripts.patch_base import (
    FieldDiff,
    add_common_args,
    create_session,
    load_words,
    prepare_database,
    print_diffs,
    print_summary,
)

JOINEDLOADS = (joinedload(Word.definitions),)


def _regenerate_examples_for_word(word: Word) -> list[FieldDiff]:
    definitions = list(word.definitions or [])
    if not definitions:
        return []

    definition_payloads = [
        {
            "part_of_speech": definition.part_of_speech,
            "meaning_en": definition.meaning_en,
            "example_en": definition.example_en,
        }
        for definition in definitions
    ]
    _fill_empty_examples_with_gpt(word.word, definition_payloads)

    diffs: list[FieldDiff] = []
    for definition, payload in zip(definitions, definition_payloads):
        before = definition.example_en or ""
        after = str(payload.get("example_en", "")).strip()
        if after and after != before:
            definition.example_en = after
            diffs.append(
                FieldDiff(
                    name=f"definition[{definition.sort_order}].example_en",
                    before=before,
                    after=after,
                )
            )
    return diffs


def run(dry_run: bool = False, limit: int | None = None, word_filter: str | None = None) -> None:
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
            print("想定データがある場合は、DATABASE_URL または data/db/data.db を確認してください。")
            return

        print(f"対象: {total} 件" + (" (dry-run)" if dry_run else ""))
        for idx, word in enumerate(words, start=1):
            try:
                diffs = _regenerate_examples_for_word(word)
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
    parser = argparse.ArgumentParser(description="登録済み単語のプレースホルダー例文を再生成")
    add_common_args(parser)
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word)


if __name__ == "__main__":
    main()
