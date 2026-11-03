"""Add voice column to listening_attempts for weak-voice analytics.

Records which TTS voice was actually playing when a dictation attempt was
made, so later analysis can compute per-voice accuracy. Denormalized at
record_attempt() time rather than derived from the line's current primary
audio variant, since the primary variant can change after the fact (e.g.
via the voice-compare panel) and would otherwise misattribute history.

Revision ID: 008_add_attempt_voice
Revises: 007_fix_stale_old_fks
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "008_add_attempt_voice"
down_revision = "007_fix_stale_old_fks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("listening_attempts")}
    if "voice" not in columns:
        op.add_column("listening_attempts", sa.Column("voice", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("listening_attempts", "voice")
