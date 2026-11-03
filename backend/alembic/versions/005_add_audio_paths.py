"""Add audio_path columns for TTS playback.

Revision ID: 005_add_audio_paths
Revises: 004_definition_examples
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005_add_audio_paths"
down_revision = "004_definition_examples"
branch_labels = None
depends_on = None

_TARGETS = ["words", "definition_examples", "phrases", "phrase_definitions"]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in _TARGETS:
        existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
        if "audio_path" in existing_columns:
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(sa.Column("audio_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    for table_name in _TARGETS:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column("audio_path")
