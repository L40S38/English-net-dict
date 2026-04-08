from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from core.config import settings


def run_alembic_migrations() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    try:
        if _migration_already_at_head(config):
            return
    except Exception:
        # Introspection or script layout issues: still run upgrade to be safe.
        pass

    from alembic import command

    command.upgrade(config, "head")


def _migration_already_at_head(config: Config) -> bool:
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    script_dir = ScriptDirectory.from_config(config)
    heads = script_dir.get_heads()
    if len(heads) != 1:
        return False

    head = heads[0]
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        return False

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current = context.get_current_revision()
    finally:
        engine.dispose()

    return current == head
