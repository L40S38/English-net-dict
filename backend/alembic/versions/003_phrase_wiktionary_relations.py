"""Phrase: Wiktionary relation lists (synonyms, see also, etc.).

Revision ID: 003_phrase_wiktionary_relations
Revises: 002_phrase_detail
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_phrase_wiktionary_relations"
down_revision = "002_phrase_detail"
branch_labels = None
depends_on = None

_json_empty = sa.text("'[]'")


def upgrade() -> None:
    # 001 builds the schema from the live `core.models` metadata, so on a
    # fresh database `phrases` already has these columns. Skip any column
    # that already exists so this migration is also a no-op there.
    bind = op.get_bind()
    existing_columns = {col["name"] for col in sa.inspect(bind).get_columns("phrases")}

    with op.batch_alter_table("phrases") as batch_op:
        if "wiktionary_synonyms" not in existing_columns:
            batch_op.add_column(
                sa.Column("wiktionary_synonyms", sa.JSON(), nullable=False, server_default=_json_empty),
            )
        if "wiktionary_antonyms" not in existing_columns:
            batch_op.add_column(
                sa.Column("wiktionary_antonyms", sa.JSON(), nullable=False, server_default=_json_empty),
            )
        if "wiktionary_see_also" not in existing_columns:
            batch_op.add_column(
                sa.Column("wiktionary_see_also", sa.JSON(), nullable=False, server_default=_json_empty),
            )
        if "wiktionary_derived_terms" not in existing_columns:
            batch_op.add_column(
                sa.Column("wiktionary_derived_terms", sa.JSON(), nullable=False, server_default=_json_empty),
            )
        if "wiktionary_phrases" not in existing_columns:
            batch_op.add_column(
                sa.Column("wiktionary_phrases", sa.JSON(), nullable=False, server_default=_json_empty),
            )


def downgrade() -> None:
    with op.batch_alter_table("phrases") as batch_op:
        batch_op.drop_column("wiktionary_phrases")
        batch_op.drop_column("wiktionary_derived_terms")
        batch_op.drop_column("wiktionary_see_also")
        batch_op.drop_column("wiktionary_antonyms")
        batch_op.drop_column("wiktionary_synonyms")
