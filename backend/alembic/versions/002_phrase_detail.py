"""Add phrase definitions/images and phrase chat scope.

Revision ID: 002_phrase_detail
Revises: 001_initial_schema
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002_phrase_detail"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 001 builds the schema from the live `core.models` metadata, so on a fresh
    # database these tables/columns already exist by the time this migration
    # runs. Guard each step so this migration is also a no-op there, while
    # still applying correctly to a database that ran 001 before phrase
    # detail support was added to models.py.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "phrase_definitions" not in existing_tables:
        op.create_table(
            "phrase_definitions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("phrase_id", sa.Integer(), sa.ForeignKey("phrases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("part_of_speech", sa.String(length=64), nullable=False, server_default="phrase"),
            sa.Column("meaning_en", sa.Text(), nullable=False, server_default=""),
            sa.Column("meaning_ja", sa.Text(), nullable=False, server_default=""),
            sa.Column("example_en", sa.Text(), nullable=False, server_default=""),
            sa.Column("example_ja", sa.Text(), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_phrase_definitions_phrase_id", "phrase_definitions", ["phrase_id"])

        # existing phrases bootstrap: keep detail screen non-empty before first enrich
        op.execute(
            sa.text(
                """
                INSERT INTO phrase_definitions (phrase_id, part_of_speech, meaning_en, meaning_ja, example_en, example_ja, sort_order)
                SELECT id, 'phrase', '', COALESCE(meaning, ''), '', '', 0
                FROM phrases
                """
            )
        )

    if "phrase_images" not in existing_tables:
        op.create_table(
            "phrase_images",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("phrase_id", sa.Integer(), sa.ForeignKey("phrases.id", ondelete="CASCADE"), nullable=False),
            sa.Column("file_path", sa.String(length=512), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_phrase_images_phrase_id", "phrase_images", ["phrase_id"])

    chat_session_columns = {col["name"] for col in inspector.get_columns("chat_sessions")}
    with op.batch_alter_table("chat_sessions") as batch_op:
        if "phrase_id" not in chat_session_columns:
            batch_op.add_column(sa.Column("phrase_id", sa.Integer(), nullable=True))
            batch_op.create_index("ix_chat_sessions_phrase_id", ["phrase_id"])
            batch_op.create_foreign_key(
                "fk_chat_sessions_phrase_id_phrases",
                "phrases",
                ["phrase_id"],
                ["id"],
                ondelete="CASCADE",
            )
        batch_op.drop_constraint("ck_chat_sessions_scope", type_="check")
        batch_op.create_check_constraint(
            "ck_chat_sessions_scope",
            "(word_id IS NOT NULL AND component_text IS NULL AND component_id IS NULL AND group_id IS NULL AND phrase_id IS NULL) OR "
            "(word_id IS NULL AND group_id IS NULL AND phrase_id IS NULL AND (component_text IS NOT NULL OR component_id IS NOT NULL)) OR "
            "(group_id IS NOT NULL AND word_id IS NULL AND component_text IS NULL AND component_id IS NULL AND phrase_id IS NULL) OR "
            "(phrase_id IS NOT NULL AND word_id IS NULL AND component_text IS NULL AND component_id IS NULL AND group_id IS NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_constraint("ck_chat_sessions_scope", type_="check")
        batch_op.drop_constraint("fk_chat_sessions_phrase_id_phrases", type_="foreignkey")
        batch_op.drop_index("ix_chat_sessions_phrase_id")
        batch_op.drop_column("phrase_id")
        batch_op.create_check_constraint(
            "ck_chat_sessions_scope",
            "(word_id IS NOT NULL AND component_text IS NULL AND component_id IS NULL AND group_id IS NULL) OR "
            "(word_id IS NULL AND group_id IS NULL AND (component_text IS NOT NULL OR component_id IS NOT NULL)) OR "
            "(group_id IS NOT NULL AND word_id IS NULL AND component_text IS NULL AND component_id IS NULL)",
        )

    op.drop_index("ix_phrase_images_phrase_id", table_name="phrase_images")
    op.drop_table("phrase_images")
    op.drop_index("ix_phrase_definitions_phrase_id", table_name="phrase_definitions")
    op.drop_table("phrase_definitions")
