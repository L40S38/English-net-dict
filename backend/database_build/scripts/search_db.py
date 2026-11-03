from __future__ import annotations

import argparse

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from core.database import SessionLocal
from core.models import Definition, Etymology, Word
from database_build.ops.common import normalize_db_url


def _session(db: str | None) -> Session:
    db_url = normalize_db_url(db)
    if db_url is None:
        return SessionLocal()
    target_engine = create_engine(db_url, connect_args={"check_same_thread": False, "timeout": 30}, future=True)
    session_local = sessionmaker(bind=target_engine, autoflush=False, autocommit=False, class_=Session)
    return session_local()


def main() -> None:
    parser = argparse.ArgumentParser(description="Search words/definitions/etymology from DB")
    parser.add_argument("--db", type=str, default=None, help="DB path or SQLAlchemy URL")
    parser.add_argument("--query", type=str, required=True, help="Search keyword")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    db = _session(args.db)
    try:
        keyword = args.query.strip()
        if not keyword:
            return
        pat = f"%{keyword}%"
        stmt = (
            select(Word.word, Definition.meaning_en, Definition.meaning_ja, Etymology.raw_description)
            .join(Definition, Definition.word_id == Word.id, isouter=True)
            .join(Etymology, Etymology.word_id == Word.id, isouter=True)
            .where(
                or_(
                    Word.word.ilike(pat),
                    Definition.meaning_en.ilike(pat),
                    Definition.meaning_ja.ilike(pat),
                    Etymology.raw_description.ilike(pat),
                )
            )
            .order_by(func.lower(Word.word))
            .limit(args.limit)
        )
        rows = db.execute(stmt).all()
        for word, meaning_en, meaning_ja, raw_description in rows:
            m_en = (meaning_en or "").strip()
            m_ja = (meaning_ja or "").strip()
            ety = (raw_description or "").strip()
            print(f"{word}\t{m_en}\t{m_ja}\t{ety[:80]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
