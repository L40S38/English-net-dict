from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.database import Base, SessionLocal, engine
from core.migrations import run_alembic_migrations
from core.services.scraper import build_scrapers


def normalize_db_url(db: str | None) -> str | None:
    if db is None:
        return None
    raw = db.strip()
    if not raw:
        return None
    if "://" in raw:
        return raw
    resolved = Path(raw).expanduser().resolve()
    return f"sqlite:///{resolved.as_posix()}"


def create_session(db: str | None = None) -> Session:
    db_url = normalize_db_url(db)
    if db_url is None:
        return SessionLocal()
    custom_engine = create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)
    session_local = sessionmaker(bind=custom_engine, autoflush=False, autocommit=False, class_=Session)
    return session_local()


def prepare_database(db: str | None = None) -> None:
    db_url = normalize_db_url(db)
    if db_url is None:
        Base.metadata.create_all(bind=engine)
        run_alembic_migrations()
        return
    custom_engine = create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)
    Base.metadata.create_all(bind=custom_engine)


async def scrape_all(word_text: str) -> list[dict]:
    scrapers = build_scrapers()
    tasks = [scraper.scrape(word_text) for scraper in scrapers]
    return list(await asyncio.gather(*tasks))
