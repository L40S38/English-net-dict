"""Word definitions: move examples into child table.

Revision ID: 004_definition_examples
Revises: 003_phrase_wiktionary_relations
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "004_definition_examples"
down_revision = "003_phrase_wiktionary_relations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "definition_examples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("definition_id", sa.Integer(), sa.ForeignKey("definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("example_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("example_ja", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_definition_examples_definition_id",
        "definition_examples",
        ["definition_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO definition_examples (definition_id, example_en, example_ja, sort_order)
            SELECT id, COALESCE(example_en, ''), COALESCE(example_ja, ''), 0
            FROM definitions
            """
        )
    )
    with op.batch_alter_table("definitions") as batch_op:
        batch_op.drop_column("example_en")
        batch_op.drop_column("example_ja")


def downgrade() -> None:
    with op.batch_alter_table("definitions") as batch_op:
        batch_op.add_column(sa.Column("example_ja", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("example_en", sa.Text(), nullable=False, server_default=""))
    op.execute(
        sa.text(
            """
            UPDATE definitions
            SET
              example_en = COALESCE((
                SELECT de.example_en
                FROM definition_examples AS de
                WHERE de.definition_id = definitions.id
                ORDER BY de.sort_order, de.id
                LIMIT 1
              ), ''),
              example_ja = COALESCE((
                SELECT de.example_ja
                FROM definition_examples AS de
                WHERE de.definition_id = definitions.id
                ORDER BY de.sort_order, de.id
                LIMIT 1
              ), '')
            """
        )
    )
    op.drop_index("ix_definition_examples_definition_id", table_name="definition_examples")
    op.drop_table("definition_examples")

