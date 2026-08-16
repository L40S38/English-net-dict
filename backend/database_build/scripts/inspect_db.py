from __future__ import annotations

import argparse

from sqlalchemy import create_engine, text

from core.database import engine as default_engine
from database_build.ops.common import normalize_db_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect DB tables and schema")
    parser.add_argument("--db", type=str, default=None, help="DB path or SQLAlchemy URL")
    parser.add_argument("--table", type=str, default=None, help="Show schema for a specific table")
    args = parser.parse_args()

    db_url = normalize_db_url(args.db)
    target_engine = (
        default_engine
        if db_url is None
        else create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)
    )
    with target_engine.connect() as conn:
        if args.table:
            rows = conn.execute(text(f"PRAGMA table_info({args.table})")).mappings().all()
            print(f"=== {args.table} schema ===")
            for row in rows:
                print(f"{row.get('name')} {row.get('type')}")
            return
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).all()
        print("=== tables ===")
        for row in rows:
            table = row[0]
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
            print(f"{table}: {count}")


if __name__ == "__main__":
    main()
