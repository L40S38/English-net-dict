"""Fix stale '_old' foreign key targets in etymology + chat_messages tables.

A past SQLite table recreate (rename-to-`_old` / create-new / copy / drop-old)
on `etymologies` and `chat_sessions` left dependent child tables' FOREIGN KEY
clauses pointing at the now-gone `etymologies_old` / `chat_sessions_old`
tables (SQLite bakes FK target names in as literal text and does not rewrite
them in other tables when a table is renamed). With `PRAGMA foreign_keys=ON`,
any INSERT into these child tables now fails with
"no such table: main.etymologies_old". This migration recreates each
affected table with the FK pointed at the correct current table, preserving
all existing rows and indexes.

Revision ID: 007_fix_stale_old_fks
Revises: 006_listening_practice
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007_fix_stale_old_fks"
down_revision = "006_listening_practice"
branch_labels = None
depends_on = None


def _has_stale_fk(bind, table_name: str, stale_target: str) -> bool:
    sql = bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).scalar()
    return bool(sql and stale_target in sql)


def _recreate_table(bind, table_name: str, create_sql: str, index_sqls: list[str]) -> None:
    tmp_name = f"{table_name}_tmp_fix"
    op.execute(f"ALTER TABLE {table_name} RENAME TO {tmp_name}")
    op.execute(create_sql)
    columns = [row[1] for row in bind.execute(sa.text(f"PRAGMA table_info({tmp_name})")).fetchall()]
    column_list = ", ".join(columns)
    op.execute(f"INSERT INTO {table_name} ({column_list}) SELECT {column_list} FROM {tmp_name}")
    op.execute(f"DROP TABLE {tmp_name}")
    for index_sql in index_sqls:
        op.execute(index_sql)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "etymology_branches" in existing_tables and _has_stale_fk(bind, "etymology_branches", "etymologies_old"):
        _recreate_table(
            bind,
            "etymology_branches",
            """
            CREATE TABLE etymology_branches (
                id INTEGER NOT NULL,
                etymology_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                label VARCHAR(255) NOT NULL,
                meaning_en VARCHAR(255),
                meaning_ja VARCHAR(255),
                PRIMARY KEY (id),
                FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE
            )
            """,
            ["CREATE INDEX ix_etymology_branches_etymology_id ON etymology_branches (etymology_id)"],
        )

    if "etymology_component_items" in existing_tables and _has_stale_fk(
        bind, "etymology_component_items", "etymologies_old"
    ):
        _recreate_table(
            bind,
            "etymology_component_items",
            """
            CREATE TABLE etymology_component_items (
                id INTEGER NOT NULL,
                etymology_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                component_text VARCHAR(128) NOT NULL,
                meaning TEXT,
                type VARCHAR(32) NOT NULL,
                component_id INTEGER, variant_id INTEGER,
                PRIMARY KEY (id),
                FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE,
                FOREIGN KEY(component_id) REFERENCES etymology_components (id) ON DELETE SET NULL
            )
            """,
            [
                "CREATE INDEX ix_etymology_component_items_etymology_id ON etymology_component_items (etymology_id)",
                "CREATE INDEX ix_etymology_component_items_component_id ON etymology_component_items (component_id)",
                "CREATE INDEX ix_etymology_component_items_variant_id ON etymology_component_items (variant_id)",
            ],
        )

    if "etymology_variants" in existing_tables and _has_stale_fk(bind, "etymology_variants", "etymologies_old"):
        _recreate_table(
            bind,
            "etymology_variants",
            """
            CREATE TABLE etymology_variants (
                id INTEGER NOT NULL,
                etymology_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL,
                label VARCHAR(128),
                excerpt TEXT,
                PRIMARY KEY (id),
                FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE
            )
            """,
            ["CREATE INDEX ix_etymology_variants_etymology_id ON etymology_variants (etymology_id)"],
        )

    if "etymology_language_chain_links" in existing_tables and _has_stale_fk(
        bind, "etymology_language_chain_links", "etymologies_old"
    ):
        _recreate_table(
            bind,
            "etymology_language_chain_links",
            """
            CREATE TABLE etymology_language_chain_links (
                id INTEGER NOT NULL,
                etymology_id INTEGER NOT NULL,
                variant_id INTEGER,
                sort_order INTEGER NOT NULL,
                lang VARCHAR(32) NOT NULL,
                lang_name VARCHAR(64),
                word VARCHAR(128) NOT NULL,
                relation VARCHAR(32),
                PRIMARY KEY (id),
                FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE,
                FOREIGN KEY(variant_id) REFERENCES etymology_variants (id) ON DELETE CASCADE
            )
            """,
            [
                "CREATE INDEX ix_etymology_language_chain_links_variant_id "
                "ON etymology_language_chain_links (variant_id)",
                "CREATE INDEX ix_etymology_language_chain_links_etymology_id "
                "ON etymology_language_chain_links (etymology_id)",
            ],
        )

    if "etymology_component_meanings" in existing_tables and _has_stale_fk(
        bind, "etymology_component_meanings", "etymologies_old"
    ):
        _recreate_table(
            bind,
            "etymology_component_meanings",
            """
            CREATE TABLE etymology_component_meanings (
                id INTEGER NOT NULL,
                etymology_id INTEGER NOT NULL,
                variant_id INTEGER,
                sort_order INTEGER NOT NULL,
                component_text VARCHAR(128) NOT NULL,
                meaning TEXT NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE,
                FOREIGN KEY(variant_id) REFERENCES etymology_variants (id) ON DELETE CASCADE
            )
            """,
            [
                "CREATE INDEX ix_etymology_component_meanings_etymology_id "
                "ON etymology_component_meanings (etymology_id)",
                "CREATE INDEX ix_etymology_component_meanings_variant_id "
                "ON etymology_component_meanings (variant_id)",
            ],
        )

    if "etymology_json_migrated" in existing_tables and _has_stale_fk(
        bind, "etymology_json_migrated", "etymologies_old"
    ):
        _recreate_table(
            bind,
            "etymology_json_migrated",
            """
            CREATE TABLE etymology_json_migrated (
                etymology_id INTEGER NOT NULL PRIMARY KEY,
                FOREIGN KEY(etymology_id) REFERENCES etymologies (id) ON DELETE CASCADE
            )
            """,
            [],
        )

    if "chat_messages" in existing_tables and _has_stale_fk(bind, "chat_messages", "chat_sessions_old"):
        _recreate_table(
            bind,
            "chat_messages",
            """
            CREATE TABLE chat_messages (
                id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                role VARCHAR(16) NOT NULL,
                content TEXT NOT NULL,
                citations JSON NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
            )
            """,
            ["CREATE INDEX ix_chat_messages_session_id ON chat_messages (session_id)"],
        )


def downgrade() -> None:
    # The prior state was a data-integrity bug (FK pointing at a dropped table),
    # not a meaningful schema version; nothing useful to revert to.
    pass
