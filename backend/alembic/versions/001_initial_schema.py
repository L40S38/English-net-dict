"""Initial schema.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-20
"""

from __future__ import annotations

from alembic import op

from app.database import Base
from app import models  # noqa: F401

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
