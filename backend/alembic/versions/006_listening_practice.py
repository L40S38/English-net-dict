"""Add listening/shadowing practice tables.

Revision ID: 006_listening_practice
Revises: 005_add_audio_paths
Create Date: 2026-06-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006_listening_practice"
down_revision = "005_add_audio_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "listening_scripts" not in existing_tables:
        op.create_table(
            "listening_scripts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("topic", sa.String(length=255), nullable=True),
            sa.Column("level", sa.String(length=32), nullable=True),
            sa.Column("is_conversation", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("generation_mode", sa.String(length=16), nullable=False, server_default="random"),
            sa.Column("source_type", sa.String(length=16), nullable=False, server_default="ai_generated"),
            sa.Column("source_url", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "listening_speakers" not in existing_tables:
        op.create_table(
            "listening_speakers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "script_id",
                sa.Integer(),
                sa.ForeignKey("listening_scripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("label", sa.String(length=64), nullable=False),
            sa.Column("voice", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_listening_speakers_script_id", "listening_speakers", ["script_id"])

    if "listening_lines" not in existing_tables:
        op.create_table(
            "listening_lines",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "script_id",
                sa.Integer(),
                sa.ForeignKey("listening_scripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "speaker_id",
                sa.Integer(),
                sa.ForeignKey("listening_speakers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("translation_ja", sa.Text(), nullable=True),
        )
        op.create_index("ix_listening_lines_script_id", "listening_lines", ["script_id"])
        op.create_index("ix_listening_lines_speaker_id", "listening_lines", ["speaker_id"])

    if "listening_line_audios" not in existing_tables:
        op.create_table(
            "listening_line_audios",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "line_id",
                sa.Integer(),
                sa.ForeignKey("listening_lines.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("voice", sa.String(length=32), nullable=False),
            sa.Column("audio_path", sa.String(length=512), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_listening_line_audios_line_id", "listening_line_audios", ["line_id"])

    if "listening_sessions" not in existing_tables:
        op.create_table(
            "listening_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "script_id",
                sa.Integer(),
                sa.ForeignKey("listening_scripts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("current_step", sa.String(length=16), nullable=False, server_default="listen"),
            sa.Column("playback_speed", sa.Float(), nullable=False, server_default="1.0"),
            sa.Column("dictation_level", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="in_progress"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_listening_sessions_script_id", "listening_sessions", ["script_id"])

    if "listening_attempts" not in existing_tables:
        op.create_table(
            "listening_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "session_id",
                sa.Integer(),
                sa.ForeignKey("listening_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "line_id",
                sa.Integer(),
                sa.ForeignKey("listening_lines.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("dictation_level", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("user_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_listening_attempts_session_id", "listening_attempts", ["session_id"])
        op.create_index("ix_listening_attempts_line_id", "listening_attempts", ["line_id"])

    if "listening_word_results" not in existing_tables:
        op.create_table(
            "listening_word_results",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "attempt_id",
                sa.Integer(),
                sa.ForeignKey("listening_attempts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("word_text", sa.String(length=128), nullable=False),
            sa.Column(
                "matched_word_id",
                sa.Integer(),
                sa.ForeignKey("words.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_listening_word_results_attempt_id", "listening_word_results", ["attempt_id"])
        op.create_index("ix_listening_word_results_word_text", "listening_word_results", ["word_text"])
        op.create_index("ix_listening_word_results_matched_word_id", "listening_word_results", ["matched_word_id"])


def downgrade() -> None:
    op.drop_table("listening_word_results")
    op.drop_table("listening_attempts")
    op.drop_table("listening_sessions")
    op.drop_table("listening_line_audios")
    op.drop_table("listening_lines")
    op.drop_table("listening_speakers")
    op.drop_table("listening_scripts")
