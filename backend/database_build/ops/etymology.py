from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from core.models import Etymology, Word
from core.services.gpt_service import enrich_core_image_and_branches
from core.services.scraper.wiktionary import WiktionaryScraper
from core.services.word_service import apply_etymology_update
from database_build.reporting import FieldDiff


def _snapshot_diffs(before: dict[str, Any], after: dict[str, Any], keys: list[str]) -> list[FieldDiff]:
    diffs: list[FieldDiff] = []
    for key in keys:
        if before.get(key) != after.get(key):
            diffs.append(FieldDiff(name=key, before=before.get(key), after=after.get(key)))
    return diffs


def _safe_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _etymology_snapshot(word: Word) -> dict[str, Any]:
    def _safe_id(value: Any) -> int:
        ident = getattr(value, "id", None)
        return ident if isinstance(ident, int) else -1

    ety = word.etymology
    if not ety:
        return {
            "has_etymology": False,
            "origin_word": None,
            "origin_language": None,
            "core_image": "",
            "raw_description": None,
            "components": [],
            "language_chain": [],
            "component_meanings": [],
            "variants": [],
            "branches": [],
        }
    return {
        "has_etymology": True,
        "origin_word": ety.origin_word,
        "origin_language": ety.origin_language,
        "core_image": ety.core_image or "",
        "raw_description": ety.raw_description,
        "components": [
            {"text": c.component_text, "meaning": c.meaning, "type": c.type}
            for c in sorted(ety.component_items, key=lambda x: (x.sort_order, x.id))
        ],
        "language_chain": [
            {"lang": link.lang, "lang_name": link.lang_name, "word": link.word, "relation": link.relation}
            for link in sorted(
                [link for link in ety.language_chain_links if link.variant_id is None],
                key=lambda x: (x.sort_order, x.id),
            )
        ],
        "component_meanings": [
            {"text": cm.component_text, "meaning": cm.meaning}
            for cm in sorted(
                [cm for cm in ety.component_meanings if cm.variant_id is None],
                key=_safe_id,
            )
        ],
        "variants": [
            {
                "label": v.label,
                "excerpt": v.excerpt,
                "components": [
                    {"text": c.component_text, "meaning": c.meaning, "type": c.type}
                    for c in sorted(v.component_items, key=lambda x: (x.sort_order, x.id))
                ],
                "component_meanings": [
                    {"text": cm.component_text, "meaning": cm.meaning}
                    for cm in sorted(v.component_meanings, key=_safe_id)
                ],
                "language_chain": [
                    {"lang": link.lang, "lang_name": link.lang_name, "word": link.word, "relation": link.relation}
                    for link in sorted(v.language_chain_links, key=lambda x: (x.sort_order, x.id))
                ],
            }
            for v in sorted(ety.variants, key=lambda x: (x.sort_order, x.id))
        ],
        "branches": [
            {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
            for b in sorted(ety.branches, key=lambda x: (x.sort_order, x.id))
        ],
    }


async def refresh_etymology(
    db: Session,
    word: Word,
    *,
    scraper: WiktionaryScraper | None = None,
) -> list[FieldDiff]:
    before = _etymology_snapshot(word)
    scraper_impl = scraper or WiktionaryScraper()
    scraped = await scraper_impl.scrape(word.word)
    if not isinstance(scraped, dict) or scraped.get("error"):
        error_text = (
            str(scraped.get("error", "unknown scrape error")) if isinstance(scraped, dict) else "invalid payload"
        )
        raise RuntimeError(f"failed to scrape etymology for {word.word}: {error_text}")

    if not word.etymology:
        word.etymology = Etymology(word_id=word.id)
    existing = word.etymology
    payload = {
        "components": _safe_list(scraped.get("etymology_components")),
        "language_chain": _safe_list(scraped.get("language_chain")),
        "component_meanings": _safe_list(scraped.get("component_meanings")),
        "etymology_variants": _safe_list(scraped.get("etymology_variants")),
        "raw_description": str(scraped.get("etymology_excerpt") or existing.raw_description or "").strip() or None,
        "origin_word": existing.origin_word,
        "origin_language": existing.origin_language,
        "core_image": existing.core_image,
        "branches": [
            {"label": b.label or "", "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
            for b in sorted(existing.branches, key=lambda x: (x.sort_order, x.id))
        ],
    }
    apply_etymology_update(db, existing, payload)
    after = _etymology_snapshot(word)
    return _snapshot_diffs(
        before,
        after,
        ["raw_description", "components", "language_chain", "component_meanings", "variants"],
    )


async def refresh_etymology_only(
    db: Session,
    word: Word,
    *,
    scraper: WiktionaryScraper | None = None,
) -> list[FieldDiff]:
    return await refresh_etymology(db, word, scraper=scraper)


def _core_image_is_generic(word_text: str, core_image: object) -> bool:
    value = str(core_image or "").strip()
    if not value:
        return True
    generic_patterns = {
        f"{word_text}: central concept",
        f"core image for {word_text}",
        f"etymology for {word_text}",
    }
    return value.lower() in {pattern.lower() for pattern in generic_patterns}


def _build_etymology_payload(word: Word) -> dict:
    from core.services.word_service import build_etymology_enrich_payload

    return build_etymology_enrich_payload(word.etymology)


def _build_definition_payload(word: Word) -> list[dict]:
    return [
        {
            "part_of_speech": definition.part_of_speech,
            "meaning_en": definition.meaning_en,
            "meaning_ja": definition.meaning_ja,
            "example_en": definition.example_en,
            "example_ja": definition.example_ja,
        }
        for definition in word.definitions
    ]


def enrich_etymology_map(db: Session, word: Word, *, only_missing: bool = False) -> list[FieldDiff]:  # noqa: ARG001
    from core.services.word_service import _apply_etymology_branches

    ety = word.etymology
    if only_missing:
        has_branches = bool(ety and len(ety.branches) > 0)
        if ety and not _core_image_is_generic(word.word, ety.core_image) and has_branches:
            return []

    enriched = enrich_core_image_and_branches(
        word_text=word.word,
        definitions=_build_definition_payload(word),
        etymology_data=_build_etymology_payload(word),
    )
    if not enriched:
        return []

    new_core_image = str(enriched.get("core_image", "")).strip()
    new_branches = enriched.get("branches")
    has_new_branches = isinstance(new_branches, list) and len(new_branches) > 0
    if not new_core_image and not has_new_branches:
        return []

    if not word.etymology:
        word.etymology = Etymology(word_id=word.id)

    diffs: list[FieldDiff] = []
    before_core = (word.etymology.core_image or "").strip()
    before_branches = [
        {"label": b.label, "meaning_en": b.meaning_en, "meaning_ja": b.meaning_ja}
        for b in word.etymology.branches
    ]
    if new_core_image and new_core_image != before_core:
        word.etymology.core_image = new_core_image
        diffs.append(FieldDiff(name="core_image", before=before_core, after=new_core_image))
    if has_new_branches and new_branches != before_branches:
        _apply_etymology_branches(word.etymology, list(new_branches))
        diffs.append(FieldDiff(name="branches", before=before_branches, after=list(new_branches)))
    return diffs


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
    conn.execute(
        text("INSERT OR IGNORE INTO etymology_json_migrated (etymology_id) VALUES (:id)"),
        {"id": etymology_id},
    )
    return branches_count, links_count, meanings_count, variants_count


def normalize_etymology_json(
    engine: Engine,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    word_filter: str | None = None,
) -> tuple[int, int, int]:
    updated = 0
    skipped = 0
    errors = 0
    with engine.begin() as conn:
        cols = {r["name"] for r in conn.execute(text("PRAGMA table_info(etymologies)")).mappings().all()}
        json_cols = {"branches", "language_chain", "component_meanings", "etymology_variants"}
        if not (json_cols & cols):
            return updated, skipped, errors
        _ensure_migrated_table(conn)
        select_cols = [
            c for c in ["branches", "language_chain", "component_meanings", "etymology_variants"] if c in cols
        ]
        select_sql = ", ".join(select_cols)
        if word_filter:
            word_row = conn.execute(
                text("SELECT id FROM words WHERE lower(word) = :w"),
                {"w": word_filter.strip().lower()},
            ).first()
            if not word_row:
                return updated, skipped, errors
            rows = conn.execute(
                text(f"SELECT id, {select_sql} FROM etymologies WHERE word_id = :word_id ORDER BY id"),
                {"word_id": word_row[0]},
            ).mappings().all()
        else:
            rows = conn.execute(text(f"SELECT id, {select_sql} FROM etymologies ORDER BY id")).mappings().all()
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            etymology_id = int(row["id"])
            if _is_migrated(conn, etymology_id):
                skipped += 1
                continue
            try:
                branches = _parse_json(row.get("branches")) if "branches" in row else []
                language_chain = _parse_json(row.get("language_chain")) if "language_chain" in row else []
                component_meanings = _parse_json(row.get("component_meanings")) if "component_meanings" in row else []
                etymology_variants = _parse_json(row.get("etymology_variants")) if "etymology_variants" in row else []
                if dry_run:
                    updated += 1
                    continue
                _migrate_etymology(conn, etymology_id, branches, language_chain, component_meanings, etymology_variants)
                updated += 1
            except Exception:  # noqa: BLE001
                errors += 1
                if not dry_run:
                    raise
    return updated, skipped, errors
