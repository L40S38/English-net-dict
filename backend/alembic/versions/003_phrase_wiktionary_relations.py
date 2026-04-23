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
    with op.batch_alter_table("phrases") as batch_op:
        batch_op.add_column(
            sa.Column("wiktionary_synonyms", sa.JSON(), nullable=False, server_default=_json_empty),
        )
        batch_op.add_column(
            sa.Column("wiktionary_antonyms", sa.JSON(), nullable=False, server_default=_json_empty),
        )
        batch_op.add_column(
            sa.Column("wiktionary_see_also", sa.JSON(), nullable=False, server_default=_json_empty),
        )
        batch_op.add_column(
            sa.Column("wiktionary_derived_terms", sa.JSON(), nullable=False, server_default=_json_empty),
        )
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
