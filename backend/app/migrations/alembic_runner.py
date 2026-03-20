from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import settings


def run_alembic_migrations() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
