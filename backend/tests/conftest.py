from __future__ import annotations

import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import core.models  # noqa: F401  registers all tables on Base.metadata
from core.database import Base


@pytest.fixture()
def db_session() -> Generator[Session]:
    """Yields a Session backed by a throwaway SQLite file, never the real app DB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        engine = create_engine(f"sqlite:///{Path(tmp_dir) / 'test.db'}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()
            engine.dispose()
