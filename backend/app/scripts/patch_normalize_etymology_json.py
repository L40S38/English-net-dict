"""
パッチスクリプト: etymologies の JSON 列を正規化テーブルに移行する。

使い方（backend をカレントに）:
  python -m app.scripts.patch_normalize_etymology_json [--dry-run] [--limit N] [--word WORD]

実行前に DB バックアップを取ること。実行後、アプリを再起動すると runtime_sqlite が
etymologies テーブルを再作成して JSON 列を除去する。
"""

from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.migrations import run_runtime_migrations

from app.scripts.patch_base import add_common_args, print_summary


def _parse_json(raw: object) -> list:
    if raw in (None, "", "[]"):
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _ensure_migrated_table(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS etymology_json_migrated (
              etymology_id INTEGER NOT NULL PRIMARY KEY,
              FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE
            )
            """
        )
    )


def _is_migrated(conn, etymology_id: int) -> bool:
    r = conn.execute(
        text("SELECT 1 FROM etymology_json_migrated WHERE etymology_id = :id"),
        {"id": etymology_id},
    ).first()
    return r is not None


def _migrate_etymology(
    conn,
    etymology_id: int,
    branches: list,
    language_chain: list,
    component_meanings: list,
    etymology_variants: list,
) -> tuple[int, int, int, int]:
    """Migrate one etymology. Returns (branches, links, meanings, variants) counts."""
    branches_count = 0
    links_count = 0
    meanings_count = 0
    variants_count = 0

    for idx, b in enumerate(branches):
        if isinstance(b, dict):
            label = str(b.get("label", "")).strip()
        elif isinstance(b, str):
            label = b.strip()
        else:
            continue
        if not label:
            continue
        meaning_en = str(b.get("meaning_en", "")).strip() or None if isinstance(b, dict) else None
        meaning_ja = str(b.get("meaning_ja", "")).strip() or None if isinstance(b, dict) else None
        conn.execute(
            text(
                """
                INSERT INTO etymology_branches (etymology_id, sort_order, label, meaning_en, meaning_ja)
                VALUES (:etymology_id, :sort_order, :label, :meaning_en, :meaning_ja)
                """
            ),
            {
                "etymology_id": etymology_id,
                "sort_order": idx,
                "label": label,
                "meaning_en": meaning_en,
                "meaning_ja": meaning_ja,
            },
        )
        branches_count += 1

    for idx, link in enumerate(language_chain):
        if not isinstance(link, dict):
            continue
        lang = str(link.get("lang", "")).strip()
        word = str(link.get("word", "")).strip()
        if not lang or not word:
            continue
        lang_name = str(link.get("lang_name", "")).strip() or None
        relation = str(link.get("relation", "")).strip() or None
        conn.execute(
            text(
                """
                INSERT INTO etymology_language_chain_links
                  (etymology_id, variant_id, sort_order, lang, lang_name, word, relation)
                VALUES (:etymology_id, NULL, :sort_order, :lang, :lang_name, :word, :relation)
                """
            ),
            {
                "etymology_id": etymology_id,
                "sort_order": idx,
                "lang": lang,
                "lang_name": lang_name,
                "word": word,
                "relation": relation,
            },
        )
        links_count += 1

    for idx, item in enumerate(component_meanings):
        if not isinstance(item, dict):
            continue
        ctext = str(item.get("text", item.get("component_text", ""))).strip()
        meaning = str(item.get("meaning", "")).strip()
        if not ctext:
            continue
        conn.execute(
            text(
                """
                INSERT INTO etymology_component_meanings
                  (etymology_id, variant_id, sort_order, component_text, meaning)
                VALUES (:etymology_id, NULL, :sort_order, :component_text, :meaning)
                """
            ),
            {
                "etymology_id": etymology_id,
                "sort_order": idx,
                "component_text": ctext,
                "meaning": meaning,
            },
        )
        meanings_count += 1

    for v_idx, v in enumerate(etymology_variants):
        if not isinstance(v, dict):
            continue
        label = str(v.get("label", "")).strip() or None
        excerpt = str(v.get("excerpt", "")).strip() or None
        conn.execute(
            text(
                """
                INSERT INTO etymology_variants (etymology_id, sort_order, label, excerpt)
                VALUES (:etymology_id, :sort_order, :label, :excerpt)
                """
            ),
            {
                "etymology_id": etymology_id,
                "sort_order": v_idx,
                "label": label,
                "excerpt": excerpt,
            },
        )
        variant_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
        variants_count += 1

        components = _parse_json(v.get("components", []))
        for c_idx, comp in enumerate(components):
            if not isinstance(comp, dict):
                continue
            text_val = str(comp.get("text", "")).strip()
            if not text_val:
                continue
            meaning = str(comp.get("meaning", "")).strip() or None
            comp_type = str(comp.get("type", "root")).strip() or "root"
            conn.execute(
                text(
                    """
                    INSERT INTO etymology_component_items
                      (etymology_id, variant_id, sort_order, component_text, meaning, type, component_id)
                    VALUES (:etymology_id, :variant_id, :sort_order, :component_text, :meaning, :type, NULL)
                    """
                ),
                {
                    "etymology_id": etymology_id,
                    "variant_id": variant_id,
                    "sort_order": c_idx,
                    "component_text": text_val,
                    "meaning": meaning,
                    "type": comp_type,
                },
            )

        var_component_meanings = _parse_json(v.get("component_meanings", []))
        for cm_idx, cm in enumerate(var_component_meanings):
            if not isinstance(cm, dict):
                continue
            ctext = str(cm.get("text", cm.get("component_text", ""))).strip()
            meaning = str(cm.get("meaning", "")).strip()
            if not ctext:
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO etymology_component_meanings
                      (etymology_id, variant_id, sort_order, component_text, meaning)
                    VALUES (:etymology_id, :variant_id, :sort_order, :component_text, :meaning)
                    """
                ),
                {
                    "etymology_id": etymology_id,
                    "variant_id": variant_id,
                    "sort_order": cm_idx,
                    "component_text": ctext,
                    "meaning": meaning,
                },
            )

        var_language_chain = _parse_json(v.get("language_chain", []))
        for lc_idx, link in enumerate(var_language_chain):
            if not isinstance(link, dict):
                continue
            lang = str(link.get("lang", "")).strip()
            word = str(link.get("word", "")).strip()
            if not lang or not word:
                continue
            lang_name = str(link.get("lang_name", "")).strip() or None
            relation = str(link.get("relation", "")).strip() or None
            conn.execute(
                text(
                    """
                    INSERT INTO etymology_language_chain_links
                      (etymology_id, variant_id, sort_order, lang, lang_name, word, relation)
                    VALUES (:etymology_id, :variant_id, :sort_order, :lang, :lang_name, :word, :relation)
                    """
                ),
                {
                    "etymology_id": etymology_id,
                    "variant_id": variant_id,
                    "sort_order": lc_idx,
                    "lang": lang,
                    "lang_name": lang_name,
                    "word": word,
                    "relation": relation,
                },
            )

    conn.execute(
        text("INSERT OR IGNORE INTO etymology_json_migrated (etymology_id) VALUES (:id)"),
        {"id": etymology_id},
    )
    return branches_count, links_count, meanings_count, variants_count


def run(
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
) -> None:
    if not settings.database_url.startswith("sqlite"):
        print("このスクリプトは SQLite のみ対応しています。")
        return

    run_runtime_migrations(engine)

    updated = 0
    skipped = 0
    errors = 0
    total_branches = 0
    total_links = 0
    total_meanings = 0
    total_variants = 0

    with engine.begin() as conn:
        if not conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='etymologies'")
        ).first():
            print("etymologies テーブルがありません。")
            return

        cols = {
            r["name"]
            for r in conn.execute(text("PRAGMA table_info(etymologies)")).mappings().all()
        }
        json_cols = {"branches", "language_chain", "component_meanings", "etymology_variants"}
        has_any_json = bool(json_cols & cols)
        if not has_any_json:
            print("etymologies に JSON 列がありません（既に移行済み）。")
            return

        _ensure_migrated_table(conn)

        select_cols = [
            c for c in ["branches", "language_chain", "component_meanings", "etymology_variants"]
            if c in cols
        ]
        if not select_cols:
            return
        select_sql = ", ".join(select_cols)

        if word_filter:
            word_row = conn.execute(
                text("SELECT id FROM words WHERE lower(word) = :w"),
                {"w": word_filter.strip().lower()},
            ).first()
            if not word_row:
                print(f"単語 '{word_filter}' が見つかりません。")
                return
            word_id = word_row[0]
            stmt = text(
                f"SELECT id, {select_sql} FROM etymologies WHERE word_id = :word_id ORDER BY id"
            )
            rows = conn.execute(stmt, {"word_id": word_id}).mappings().all()
        else:
            stmt = text(f"SELECT id, {select_sql} FROM etymologies ORDER BY id")
            rows = conn.execute(stmt).mappings().all()
        if limit is not None:
            rows = rows[:limit]

        total = len(rows)
        print(f"対象: {total} 件" + (" (dry-run)" if dry_run else ""))
        print(f"接続先DB: {settings.database_url}")

        for idx, row in enumerate(rows, start=1):
            etymology_id = int(row["id"])
            if _is_migrated(conn, etymology_id):
                skipped += 1
                if idx <= 5 or total <= 10:
                    print(f"  [{idx}/{total}] etymology_id={etymology_id} SKIP (already migrated)")
                continue

            try:
                branches = _parse_json(row.get("branches")) if "branches" in row else []
                language_chain = _parse_json(row.get("language_chain")) if "language_chain" in row else []
                component_meanings = _parse_json(row.get("component_meanings")) if "component_meanings" in row else []
                etymology_variants = _parse_json(row.get("etymology_variants")) if "etymology_variants" in row else []

                if dry_run:
                    b, l, m, v = 0, 0, 0, 0
                    for x in branches:
                        if isinstance(x, dict) and str(x.get("label", "")).strip():
                            b += 1
                        elif isinstance(x, str) and x.strip():
                            b += 1
                    for x in language_chain:
                        if isinstance(x, dict) and str(x.get("lang", "")).strip() and str(x.get("word", "")).strip():
                            l += 1
                    for x in component_meanings:
                        if isinstance(x, dict) and str(x.get("text", x.get("component_text", ""))).strip():
                            m += 1
                    for x in etymology_variants:
                        if isinstance(x, dict):
                            v += 1
                    total_branches += b
                    total_links += l
                    total_meanings += m
                    total_variants += v
                    updated += 1
                    if idx <= 5 or total <= 10:
                        print(f"  [{idx}/{total}] etymology_id={etymology_id} WOULD_MIGRATE branches={b} links={l} meanings={m} variants={v}")
                    continue

                b, l, m, v = _migrate_etymology(
                    conn, etymology_id, branches, language_chain, component_meanings, etymology_variants
                )
                total_branches += b
                total_links += l
                total_meanings += m
                total_variants += v
                updated += 1
                if idx <= 5 or total <= 10:
                    print(f"  [{idx}/{total}] etymology_id={etymology_id} MIGRATED branches={b} links={l} meanings={m} variants={v}")
            except Exception as exc:
                errors += 1
                print(f"  [{idx}/{total}] etymology_id={etymology_id} ERROR: {exc}")
                if not dry_run:
                    raise

    print("---")
    print(f"Migrated: {updated} etymologies")
    print(f"Skipped: {skipped} (already migrated)")
    print(f"Errors: {errors}")
    if updated > 0:
        print(f"Inserted: branches={total_branches} links={total_links} meanings={total_meanings} variants={total_variants}")
    print_summary(updated, skipped, errors)


def main() -> None:
    parser = argparse.ArgumentParser(description="etymologies の JSON 列を正規化テーブルに移行")
    add_common_args(parser)
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, word_filter=args.word)


if __name__ == "__main__":
    main()
