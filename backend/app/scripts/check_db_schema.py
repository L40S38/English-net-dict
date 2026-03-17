"""
一時スクリプト: data.db の構造を確認し、移行済みかどうかを判定する。

使い方:
  uv run python -m app.scripts.check_db_schema
"""

from __future__ import annotations

from sqlalchemy import text

from app.config import settings
from app.database import engine


def main() -> None:
    print(f"接続先: {settings.database_url}")
    print()

    with engine.connect() as conn:
        r = conn.execute(text("PRAGMA table_info(etymologies)"))
        cols = [row._mapping for row in r]
        print("=== etymologies columns ===")
        col_names = []
        for c in cols:
            name = c["name"]
            col_names.append(name)
            print(f"  {name} {c['type']}")

        r2 = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name LIKE 'etymology%' ORDER BY name"
            )
        )
        tables = [row[0] for row in r2]
        print()
        print("=== etymology-related tables ===")
        for t in tables:
            r3 = conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
            cnt = r3.scalar()
            print(f"  {t}: {cnt} rows")

        r4 = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='etymology_json_migrated'"
            )
        )
        has_migrated_table = r4.first() is not None
        migrated_count = 0
        if has_migrated_table:
            r5 = conn.execute(text("SELECT COUNT(*) FROM etymology_json_migrated"))
            migrated_count = r5.scalar() or 0
            print()
            print("etymology_json_migrated:", migrated_count, "rows")

    print()
    json_cols = {"branches", "language_chain", "component_meanings", "etymology_variants"}
    has_any_json = bool(json_cols & set(col_names))
    has_new_tables = "etymology_branches" in tables

    if has_any_json and migrated_count == 0:
        print("判定: 移行前（JSON 列あり、新テーブル空）→ パッチ実行が必要")
    elif has_any_json and migrated_count > 0:
        print("判定: 移行途中（JSON 列残存、一部移行済み）→ パッチ再実行で続行可能")
    elif not has_any_json and has_new_tables:
        print("判定: 移行済み（JSON 列なし、新テーブルあり）")
    else:
        print("判定: 新規 DB または不明")


if __name__ == "__main__":
    main()
