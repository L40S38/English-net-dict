import sqlite3
from pathlib import Path


def main() -> int:
    db_path = Path("data/db/data.db")
    print("DB:", db_path.resolve())
    if not db_path.exists():
        print("ERROR: data/db/data.db が見つかりません")
        return 2

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    def table_exists(name: str) -> bool:
        cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cur.fetchone() is not None

    def show_table(name: str) -> None:
        print(f"\n== {name} ==")
        cur.execute(f"PRAGMA table_info({name})")
        for cid, col, ctype, notnull, dflt, pk in cur.fetchall():
            print(f"- {cid}: {col} {ctype} NOTNULL={notnull} DEFAULT={dflt} PK={pk}")
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,))
        row = cur.fetchone()
        print("\nCREATE SQL:")
        print((row[0] if row and row[0] else "").strip())

    for t in ("word_groups", "word_group_items"):
        exists = table_exists(t)
        print(f"{t} exists:", exists)
        if exists:
            show_table(t)

    print("\nAll tables containing 'group':")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%group%' ORDER BY name")
    for (name,) in cur.fetchall():
        print("-", name)

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

