from __future__ import annotations

import json
import re
import unicodedata

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.config import settings


def run_runtime_migrations(engine: Engine) -> None:
    # Lightweight migrations for existing SQLite DBs.
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        def has_table(table: str) -> bool:
            rows = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name = :name"),
                {"name": table},
            ).all()
            return bool(rows)

        def has_column(table: str, column: str) -> bool:
            columns = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
            names = {str(col.get("name", "")) for col in columns}
            return column in names

        def is_not_null(table: str, column: str) -> bool:
            columns = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
            for col in columns:
                if str(col.get("name", "")) == column:
                    return bool(col.get("notnull"))
            return False

        def normalize_phrase_text(raw: object) -> str:
            value = unicodedata.normalize("NFKC", str(raw or ""))
            value = value.strip()
            value = re.sub(r"\s+", " ", value)
            return value

        def split_meanings(raw: object) -> list[str]:
            text_value = str(raw or "")
            parts = [part.strip() for part in re.split(r"[，,]", text_value)]
            seen: list[str] = []
            for part in parts:
                if not part:
                    continue
                if part in seen:
                    continue
                seen.append(part)
            return seen

        def merge_meanings(*values: object) -> str:
            merged: list[str] = []
            for value in values:
                for part in split_meanings(value):
                    if part in merged:
                        continue
                    merged.append(part)
            return "，".join(merged)

        if not has_column("words", "forms"):
            conn.execute(text("ALTER TABLE words ADD COLUMN forms JSON"))
            conn.execute(text("UPDATE words SET forms = '{}' WHERE forms IS NULL"))
        if not has_column("words", "last_viewed_at"):
            conn.execute(text("ALTER TABLE words ADD COLUMN last_viewed_at DATETIME"))
            conn.execute(text("UPDATE words SET last_viewed_at = updated_at WHERE last_viewed_at IS NULL"))
        if not has_column("words", "lemma_word_id"):
            conn.execute(text("ALTER TABLE words ADD COLUMN lemma_word_id INTEGER"))
        if not has_column("words", "inflection_type"):
            conn.execute(text("ALTER TABLE words ADD COLUMN inflection_type VARCHAR(32)"))
        if has_column("words", "forms"):
            rows = conn.execute(text("SELECT id, forms FROM words ORDER BY id")).mappings().all()
            for row in rows:
                raw_forms = row.get("forms")
                if raw_forms in (None, ""):
                    continue
                try:
                    parsed_forms = json.loads(raw_forms) if isinstance(raw_forms, str) else raw_forms
                except Exception:
                    continue
                if not isinstance(parsed_forms, dict):
                    continue
                raw_phrases = parsed_forms.get("phrases")
                if not isinstance(raw_phrases, list):
                    continue
                normalized_phrases: list[dict[str, str]] = []
                changed = False
                for item in raw_phrases:
                    if isinstance(item, str):
                        phrase = item.strip()
                        if not phrase:
                            continue
                        normalized_phrases.append({"phrase": phrase, "meaning": ""})
                        changed = True
                        continue
                    if isinstance(item, dict):
                        phrase = str(item.get("phrase", item.get("text", ""))).strip()
                        if not phrase:
                            continue
                        meaning = str(
                            item.get("meaning", item.get("meaning_en", item.get("meaning_ja", "")))
                        ).strip()
                        normalized_phrases.append({"phrase": phrase, "meaning": meaning})
                        if set(item.keys()) != {"phrase", "meaning"}:
                            changed = True
                        continue
                    changed = True
                if not changed and len(normalized_phrases) == len(raw_phrases):
                    continue
                next_forms = dict(parsed_forms)
                next_forms["phrases"] = normalized_phrases
                conn.execute(
                    text("UPDATE words SET forms = :forms WHERE id = :id"),
                    {"id": int(row["id"]), "forms": json.dumps(next_forms, ensure_ascii=False)},
                )
        if not has_column("etymologies", "language_chain"):
            conn.execute(text("ALTER TABLE etymologies ADD COLUMN language_chain JSON"))
            conn.execute(text("UPDATE etymologies SET language_chain = '[]' WHERE language_chain IS NULL"))
        if not has_column("etymologies", "component_meanings"):
            conn.execute(text("ALTER TABLE etymologies ADD COLUMN component_meanings JSON"))
            conn.execute(text("UPDATE etymologies SET component_meanings = '[]' WHERE component_meanings IS NULL"))
        if not has_column("etymologies", "etymology_variants"):
            conn.execute(text("ALTER TABLE etymologies ADD COLUMN etymology_variants JSON"))
            conn.execute(text("UPDATE etymologies SET etymology_variants = '[]' WHERE etymology_variants IS NULL"))
        if not has_column("derivations", "linked_word_id"):
            conn.execute(text("ALTER TABLE derivations ADD COLUMN linked_word_id INTEGER"))

        if not has_table("etymology_component_items"):
            conn.execute(
                text(
                    """
                    CREATE TABLE etymology_component_items (
                      id INTEGER NOT NULL PRIMARY KEY,
                      etymology_id INTEGER NOT NULL,
                      sort_order INTEGER NOT NULL DEFAULT 0,
                      component_text VARCHAR(128) NOT NULL,
                      meaning TEXT,
                      type VARCHAR(32) NOT NULL DEFAULT 'root',
                      component_id INTEGER,
                      FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE,
                      FOREIGN KEY(component_id) REFERENCES etymology_components (id) ON DELETE SET NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_component_items_etymology_id "
                    "ON etymology_component_items (etymology_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_component_items_component_id "
                    "ON etymology_component_items (component_id)"
                )
            )

        if has_column("etymologies", "components"):
            rows = conn.execute(text("SELECT id, components FROM etymologies ORDER BY id")).mappings().all()
            for row in rows:
                etymology_id = int(row["id"])
                exists = conn.execute(
                    text("SELECT 1 FROM etymology_component_items WHERE etymology_id = :id LIMIT 1"),
                    {"id": etymology_id},
                ).first()
                if exists:
                    continue
                raw = row.get("components")
                if raw in (None, "", "[]"):
                    continue
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    parsed = []
                if not isinstance(parsed, list):
                    continue
                for idx, item in enumerate(parsed):
                    if not isinstance(item, dict):
                        continue
                    text_value = str(item.get("text", "")).strip()
                    if not text_value:
                        continue
                    component_id = conn.execute(
                        text(
                            "SELECT id FROM etymology_components "
                            "WHERE lower(component_text) = :text LIMIT 1"
                        ),
                        {"text": text_value.lower()},
                    ).scalar()
                    conn.execute(
                        text(
                            """
                            INSERT INTO etymology_component_items
                              (etymology_id, sort_order, component_text, meaning, type, component_id)
                            VALUES
                              (:etymology_id, :sort_order, :component_text, :meaning, :type, :component_id)
                            """
                        ),
                        {
                            "etymology_id": etymology_id,
                            "sort_order": int(item.get("sort_order", idx) or idx),
                            "component_text": text_value,
                            "meaning": str(item.get("meaning", "")).strip() or None,
                            "type": str(item.get("type", "root")).strip() or "root",
                            "component_id": component_id,
                        },
                    )
        has_legacy_components = has_column("etymologies", "components")
        legacy_components_notnull = is_not_null("etymologies", "components") if has_legacy_components else False
        if has_legacy_components and legacy_components_notnull:
            conn.execute(text("ALTER TABLE etymologies RENAME TO etymologies_old"))
            conn.execute(
                text(
                    """
                    CREATE TABLE etymologies (
                      id INTEGER NOT NULL PRIMARY KEY,
                      word_id INTEGER NOT NULL UNIQUE,
                      origin_word VARCHAR(128),
                      origin_language VARCHAR(64),
                      core_image TEXT,
                      branches JSON NOT NULL,
                      language_chain JSON NOT NULL,
                      component_meanings JSON NOT NULL,
                      etymology_variants JSON NOT NULL,
                      raw_description TEXT,
                      FOREIGN KEY(word_id) REFERENCES words (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO etymologies
                      (id, word_id, origin_word, origin_language, core_image, branches, language_chain,
                       component_meanings, etymology_variants, raw_description)
                    SELECT
                      old.id,
                      old.word_id,
                      old.origin_word,
                      old.origin_language,
                      old.core_image,
                      COALESCE(old.branches, '[]'),
                      COALESCE(old.language_chain, '[]'),
                      COALESCE(old.component_meanings, '[]'),
                      COALESCE(old.etymology_variants, '[]'),
                      old.raw_description
                    FROM etymologies_old old
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_etymologies_word_id ON etymologies (word_id)"))
            conn.execute(text("DROP TABLE etymologies_old"))
        if has_table("chat_sessions") and not has_column("chat_sessions", "component_text"):
            conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN component_text VARCHAR(128)"))

        if has_table("chat_sessions"):
            must_rebuild = (
                is_not_null("chat_sessions", "word_id")
                or not has_column("chat_sessions", "component_id")
                or not has_column("chat_sessions", "group_id")
            )
            if must_rebuild:
                old_has_component_id = has_column("chat_sessions", "component_id")
                old_has_group_id = has_column("chat_sessions", "group_id")
                conn.execute(text("ALTER TABLE chat_sessions RENAME TO chat_sessions_old"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE chat_sessions (
                          id INTEGER NOT NULL PRIMARY KEY,
                          word_id INTEGER,
                          component_text VARCHAR(128),
                          component_id INTEGER,
                          group_id INTEGER,
                          title VARCHAR(255) NOT NULL,
                          created_at DATETIME NOT NULL,
                          updated_at DATETIME NOT NULL,
                          CONSTRAINT ck_chat_sessions_scope CHECK (
                            (word_id IS NOT NULL AND component_text IS NULL AND component_id IS NULL
                              AND group_id IS NULL)
                            OR
                            (word_id IS NULL AND group_id IS NULL
                              AND (component_text IS NOT NULL OR component_id IS NOT NULL))
                            OR
                            (group_id IS NOT NULL AND word_id IS NULL
                              AND component_text IS NULL AND component_id IS NULL)
                          ),
                          FOREIGN KEY(word_id) REFERENCES words (id) ON DELETE CASCADE,
                          FOREIGN KEY(component_id) REFERENCES etymology_components (id) ON DELETE SET NULL,
                          FOREIGN KEY(group_id) REFERENCES word_groups (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
                component_id_sql = "old.component_id" if old_has_component_id else "NULL"
                group_id_sql = "old.group_id" if old_has_group_id else "NULL"
                conn.execute(
                    text(
                        f"""
                        INSERT INTO chat_sessions
                          (id, word_id, component_text, component_id, group_id, title, created_at, updated_at)
                        SELECT
                          old.id,
                          old.word_id,
                          CASE WHEN old.word_id IS NOT NULL THEN NULL ELSE lower(trim(old.component_text)) END,
                          COALESCE({component_id_sql}, ec.id),
                          {group_id_sql},
                          old.title,
                          old.created_at,
                          old.updated_at
                        FROM chat_sessions_old old
                        LEFT JOIN etymology_components ec
                          ON lower(ec.component_text) = lower(old.component_text)
                        """
                    )
                )
                conn.execute(text("DROP TABLE chat_sessions_old"))

        if has_table("chat_sessions"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_sessions_word_id ON chat_sessions (word_id)"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_chat_sessions_component_text "
                    "ON chat_sessions (component_text)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_chat_sessions_component_id "
                    "ON chat_sessions (component_id)"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_sessions_group_id ON chat_sessions (group_id)"))

        # Normalize etymology JSON columns: create new tables and add variant_id
        if not has_table("etymology_branches"):
            conn.execute(
                text(
                    """
                    CREATE TABLE etymology_branches (
                      id INTEGER NOT NULL PRIMARY KEY,
                      etymology_id INTEGER NOT NULL,
                      sort_order INTEGER NOT NULL DEFAULT 0,
                      label VARCHAR(255) NOT NULL,
                      meaning_en VARCHAR(255),
                      meaning_ja VARCHAR(255),
                      FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_branches_etymology_id "
                    "ON etymology_branches (etymology_id)"
                )
            )
        if not has_table("etymology_variants"):
            conn.execute(
                text(
                    """
                    CREATE TABLE etymology_variants (
                      id INTEGER NOT NULL PRIMARY KEY,
                      etymology_id INTEGER NOT NULL,
                      sort_order INTEGER NOT NULL DEFAULT 0,
                      label VARCHAR(128),
                      excerpt TEXT,
                      FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_variants_etymology_id "
                    "ON etymology_variants (etymology_id)"
                )
            )
        if not has_table("etymology_language_chain_links"):
            conn.execute(
                text(
                    """
                    CREATE TABLE etymology_language_chain_links (
                      id INTEGER NOT NULL PRIMARY KEY,
                      etymology_id INTEGER NOT NULL,
                      variant_id INTEGER,
                      sort_order INTEGER NOT NULL DEFAULT 0,
                      lang VARCHAR(32) NOT NULL,
                      lang_name VARCHAR(64),
                      word VARCHAR(128) NOT NULL,
                      relation VARCHAR(32),
                      FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE,
                      FOREIGN KEY(variant_id) REFERENCES etymology_variants (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_language_chain_links_etymology_id "
                    "ON etymology_language_chain_links (etymology_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_language_chain_links_variant_id "
                    "ON etymology_language_chain_links (variant_id)"
                )
            )
        if not has_table("etymology_component_meanings"):
            conn.execute(
                text(
                    """
                    CREATE TABLE etymology_component_meanings (
                      id INTEGER NOT NULL PRIMARY KEY,
                      etymology_id INTEGER NOT NULL,
                      variant_id INTEGER,
                      sort_order INTEGER NOT NULL DEFAULT 0,
                      component_text VARCHAR(128) NOT NULL,
                      meaning TEXT NOT NULL,
                      FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE,
                      FOREIGN KEY(variant_id) REFERENCES etymology_variants (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_component_meanings_etymology_id "
                    "ON etymology_component_meanings (etymology_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_component_meanings_variant_id "
                    "ON etymology_component_meanings (variant_id)"
                )
            )
        if has_table("etymology_component_items") and not has_column("etymology_component_items", "variant_id"):
            conn.execute(text("ALTER TABLE etymology_component_items ADD COLUMN variant_id INTEGER"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_etymology_component_items_variant_id "
                    "ON etymology_component_items (variant_id)"
                )
            )

        # Recreate etymologies without JSON columns (run after patch_normalize_etymology_json has migrated data)
        def _etymology_json_migrated() -> bool:
            if not has_table("etymology_json_migrated"):
                return False
            r = conn.execute(text("SELECT COUNT(*) FROM etymology_json_migrated")).scalar()
            return r is not None and int(r) > 0

        has_json_cols = any(
            has_column("etymologies", c)
            for c in ("branches", "language_chain", "component_meanings", "etymology_variants")
        )
        if has_json_cols and _etymology_json_migrated():
            conn.execute(text("ALTER TABLE etymologies RENAME TO etymologies_old"))
            conn.execute(
                text(
                    """
                    CREATE TABLE etymologies (
                      id INTEGER NOT NULL PRIMARY KEY,
                      word_id INTEGER NOT NULL UNIQUE,
                      origin_word VARCHAR(128),
                      origin_language VARCHAR(64),
                      core_image TEXT,
                      raw_description TEXT,
                      FOREIGN KEY(word_id) REFERENCES words (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO etymologies (id, word_id, origin_word, origin_language, core_image, raw_description)
                    SELECT id, word_id, origin_word, origin_language, core_image, raw_description
                    FROM etymologies_old
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_etymologies_word_id ON etymologies (word_id)"))
            conn.execute(text("DROP TABLE etymologies_old"))

        if not has_table("phrases"):
            conn.execute(
                text(
                    """
                    CREATE TABLE phrases (
                      id INTEGER NOT NULL PRIMARY KEY,
                      text VARCHAR(255) NOT NULL UNIQUE,
                      meaning TEXT NOT NULL DEFAULT '',
                      created_at DATETIME NOT NULL,
                      updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_phrases_text ON phrases (text)"))

        if not has_table("word_groups"):
            conn.execute(
                text(
                    """
                    CREATE TABLE word_groups (
                      id INTEGER NOT NULL PRIMARY KEY,
                      name VARCHAR(128) NOT NULL,
                      description TEXT NOT NULL DEFAULT '',
                      created_at DATETIME NOT NULL,
                      updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_word_groups_name ON word_groups (name)"))

        if not has_table("word_group_items"):
            conn.execute(
                text(
                    """
                    CREATE TABLE word_group_items (
                      id INTEGER NOT NULL PRIMARY KEY,
                      group_id INTEGER NOT NULL,
                      item_type VARCHAR(16) NOT NULL DEFAULT 'word',
                      word_id INTEGER,
                      definition_id INTEGER,
                      phrase_id INTEGER,
                      phrase_text VARCHAR(255),
                      phrase_meaning TEXT,
                      sort_order INTEGER NOT NULL DEFAULT 0,
                      created_at DATETIME NOT NULL,
                      FOREIGN KEY(group_id) REFERENCES word_groups (id) ON DELETE CASCADE,
                      FOREIGN KEY(word_id) REFERENCES words (id) ON DELETE CASCADE,
                      FOREIGN KEY(definition_id) REFERENCES definitions (id) ON DELETE CASCADE,
                      FOREIGN KEY(phrase_id) REFERENCES phrases (id) ON DELETE SET NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_word_group_items_group_id ON word_group_items (group_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_word_group_items_word_id ON word_group_items (word_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_word_group_items_definition_id ON word_group_items (definition_id)"
                )
            )
        if not has_table("phrases"):
            conn.execute(
                text(
                    """
                    CREATE TABLE phrases (
                      id INTEGER NOT NULL PRIMARY KEY,
                      text VARCHAR(255) NOT NULL UNIQUE,
                      meaning TEXT NOT NULL DEFAULT '',
                      created_at DATETIME NOT NULL,
                      updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_phrases_text ON phrases (text)"))
        if not has_table("word_phrases"):
            conn.execute(
                text(
                    """
                    CREATE TABLE word_phrases (
                      id INTEGER NOT NULL PRIMARY KEY,
                      word_id INTEGER NOT NULL,
                      phrase_id INTEGER NOT NULL,
                      created_at DATETIME NOT NULL,
                      FOREIGN KEY(word_id) REFERENCES words (id) ON DELETE CASCADE,
                      FOREIGN KEY(phrase_id) REFERENCES phrases (id) ON DELETE CASCADE,
                      CONSTRAINT uq_word_phrases_word_id_phrase_id UNIQUE (word_id, phrase_id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_word_phrases_word_id ON word_phrases (word_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_word_phrases_phrase_id ON word_phrases (phrase_id)"))
        if has_table("word_group_items") and not has_column("word_group_items", "phrase_id"):
            conn.execute(text("ALTER TABLE word_group_items ADD COLUMN phrase_id INTEGER"))
        if has_table("word_group_items"):
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_word_group_items_phrase_id ON word_group_items (phrase_id)"))

        if has_table("word_group_items"):
            phrase_rows = conn.execute(
                text(
                    "SELECT id, phrase_text, phrase_meaning FROM word_group_items "
                    "WHERE item_type = 'phrase' AND phrase_text IS NOT NULL AND trim(phrase_text) <> ''"
                )
            ).mappings().all()
        else:
            phrase_rows = []
        word_rows = conn.execute(text("SELECT id, forms FROM words ORDER BY id")).mappings().all()
        phrase_map_rows = conn.execute(text("SELECT id, text, meaning FROM phrases ORDER BY id")).mappings().all()
        phrase_map: dict[str, dict] = {}
        for row in phrase_map_rows:
            normalized = normalize_phrase_text(row.get("text"))
            if not normalized:
                continue
            phrase_map[normalized] = {
                "id": int(row["id"]),
                "text": normalized,
                "meaning": str(row.get("meaning") or ""),
            }

        def ensure_phrase_id(raw_text: object, raw_meaning: object) -> int | None:
            text_value = normalize_phrase_text(raw_text)
            if not text_value:
                return None
            meaning_value = str(raw_meaning or "").strip()
            existing = phrase_map.get(text_value)
            if existing:
                merged = merge_meanings(existing.get("meaning", ""), meaning_value)
                if merged != existing.get("meaning", ""):
                    conn.execute(
                        text("UPDATE phrases SET meaning = :meaning, updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                        {"id": existing["id"], "meaning": merged},
                    )
                    existing["meaning"] = merged
                return int(existing["id"])
            conn.execute(
                text(
                    "INSERT INTO phrases (text, meaning, created_at, updated_at) "
                    "VALUES (:text, :meaning, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"text": text_value, "meaning": merge_meanings(meaning_value)},
            )
            phrase_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()
            if phrase_id is None:
                return None
            phrase_map[text_value] = {
                "id": int(phrase_id),
                "text": text_value,
                "meaning": merge_meanings(meaning_value),
            }
            return int(phrase_id)

        for row in word_rows:
            forms_raw = row.get("forms")
            if forms_raw in (None, ""):
                continue
            try:
                parsed_forms = json.loads(forms_raw) if isinstance(forms_raw, str) else forms_raw
            except Exception:
                continue
            if not isinstance(parsed_forms, dict):
                continue
            raw_phrase_items = parsed_forms.get("phrases")
            if not isinstance(raw_phrase_items, list):
                continue
            for item in raw_phrase_items:
                if isinstance(item, str):
                    phrase_id = ensure_phrase_id(item, "")
                elif isinstance(item, dict):
                    phrase_id = ensure_phrase_id(
                        item.get("phrase", item.get("text", "")),
                        item.get("meaning", item.get("meaning_ja", item.get("meaning_en", ""))),
                    )
                else:
                    phrase_id = None
                if phrase_id is None:
                    continue
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO word_phrases (word_id, phrase_id, created_at) "
                        "VALUES (:word_id, :phrase_id, CURRENT_TIMESTAMP)"
                    ),
                    {"word_id": int(row["id"]), "phrase_id": int(phrase_id)},
                )

            next_forms = dict(parsed_forms)
            next_forms.pop("phrases", None)
            conn.execute(
                text("UPDATE words SET forms = :forms WHERE id = :id"),
                {"id": int(row["id"]), "forms": json.dumps(next_forms, ensure_ascii=False)},
            )

        for row in phrase_rows:
            phrase_id = ensure_phrase_id(row.get("phrase_text"), row.get("phrase_meaning"))
            if phrase_id is None:
                continue
            conn.execute(
                text("UPDATE word_group_items SET phrase_id = :phrase_id WHERE id = :id"),
                {"id": int(row["id"]), "phrase_id": int(phrase_id)},
            )

        if not has_table("group_images"):
            conn.execute(
                text(
                    """
                    CREATE TABLE group_images (
                      id INTEGER NOT NULL PRIMARY KEY,
                      group_id INTEGER NOT NULL,
                      file_path VARCHAR(512) NOT NULL,
                      prompt TEXT NOT NULL,
                      is_active BOOLEAN NOT NULL DEFAULT 1,
                      created_at DATETIME NOT NULL,
                      FOREIGN KEY(group_id) REFERENCES word_groups (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_group_images_group_id ON group_images (group_id)"))
