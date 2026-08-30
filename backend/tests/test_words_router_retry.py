from __future__ import annotations

import asyncio
import sqlite3

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from server.routers.words import _run_with_sqlite_lock_retry


def _locked_error(message: str = "database is locked") -> OperationalError:
    return OperationalError("COMMIT", {}, sqlite3.OperationalError(message))


def test_run_with_sqlite_lock_retry_retries_when_commit_itself_is_locked(db_session: Session) -> None:
    """Regression test for the bug where `create_word`'s db.commit() sat outside the
    retry's try/except, so a lock error raised by commit() itself was never retried.
    `_run_with_sqlite_lock_retry` (used by both create_word and
    _ingest_bulk_item_with_commit) must retry a commit-time lock the same way it
    retries an ingest-time one."""
    call_count = {"fn": 0, "commit": 0}
    original_commit = db_session.commit

    def flaky_commit() -> None:
        call_count["commit"] += 1
        if call_count["commit"] == 1:
            raise _locked_error()
        original_commit()

    db_session.commit = flaky_commit  # type: ignore[method-assign]

    async def fn() -> str:
        call_count["fn"] += 1
        return "result"

    result = asyncio.run(_run_with_sqlite_lock_retry(db_session, fn))

    assert result == "result"
    assert call_count["fn"] == 2  # fn was re-run after the commit-time lock error
    assert call_count["commit"] == 2


def test_run_with_sqlite_lock_retry_reraises_lock_error_after_exhausting_retries(db_session: Session) -> None:
    def always_locked_commit() -> None:
        raise _locked_error()

    db_session.commit = always_locked_commit  # type: ignore[method-assign]

    async def fn() -> str:
        return "unused"

    with pytest.raises(OperationalError):
        asyncio.run(_run_with_sqlite_lock_retry(db_session, fn))


def test_run_with_sqlite_lock_retry_does_not_retry_unrelated_operational_errors(db_session: Session) -> None:
    def broken_commit() -> None:
        raise OperationalError("COMMIT", {}, sqlite3.OperationalError("no such table: ghost"))

    db_session.commit = broken_commit  # type: ignore[method-assign]

    call_count = {"fn": 0}

    async def fn() -> str:
        call_count["fn"] += 1
        return "unused"

    with pytest.raises(OperationalError):
        asyncio.run(_run_with_sqlite_lock_retry(db_session, fn))

    assert call_count["fn"] == 1  # not retried - this isn't a lock/busy error
