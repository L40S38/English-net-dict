"""Add step column to listening_attempts and a listening_weak_phrases table.

Lets read-aloud attempts be persisted alongside dictation attempts (tagged via
`step`) and lets multi-word mistakes that match a known dictionary phrase be
recorded separately from single-word mistakes, so weak pronunciation areas
can be surfaced at both the word and phrase level.

Revision ID: 009_add_attempt_step_weak_phrases
Revises: 008_add_attempt_voice
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "009_add_attempt_step_weak_phrases"
down_revision = "008_add_attempt_voice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    columns = {col["name"] for col in inspector.get_columns("listening_attempts")}
    if "step" not in columns:
        op.add_column(
            "listening_attempts",
            sa.Column("step", sa.String(length=16), nullable=False, server_default="dictation"),
        )

    if "listening_weak_phrases" not in inspector.get_table_names():
        op.create_table(
            "listening_weak_phrases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "attempt_id",
                sa.Integer(),
                sa.ForeignKey("listening_attempts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("phrase_text", sa.String(length=255), nullable=False),
            sa.Column(
                "matched_phrase_id",
                sa.Integer(),
                sa.ForeignKey("phrases.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_listening_weak_phrases_attempt_id", "listening_weak_phrases", ["attempt_id"])
        op.create_index("ix_listening_weak_phrases_phrase_text", "listening_weak_phrases", ["phrase_text"])
        op.create_index("ix_listening_weak_phrases_matched_phrase_id", "listening_weak_phrases", ["matched_phrase_id"])


def downgrade() -> None:
    op.drop_table("listening_weak_phrases")
    op.drop_column("listening_attempts", "step")
