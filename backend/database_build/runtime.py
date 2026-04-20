from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass
class JobSummary:
    applied: int = 0
    skipped: int = 0
    errors: int = 0


def commit_or_rollback(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
