from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

# #region agent log
import itertools as _debug_itertools
import json as _debug_json
import os as _debug_os
import threading as _debug_threading
import time as _debug_time
from pathlib import Path as _DebugPath

_DEBUG_LOG_PATH = _DebugPath(__file__).resolve().parents[2] / "debug-3d94a9.log"
_debug_session_counter = _debug_itertools.count(1)
_debug_active_sessions: dict[int, dict] = {}
_debug_active_lock = _debug_threading.Lock()


def _debug_log(hypothesis_id: str, message: str, data: dict | None = None, location: str = "database.py") -> None:
    try:
        payload = {
            "sessionId": "3d94a9",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(_debug_time.time() * 1000),
            "pid": _debug_os.getpid(),
        }
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(_debug_json.dumps(payload, default=str, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion


class Base(DeclarativeBase):
    pass


def _ensure_data_dirs() -> None:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.image_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.nltk_data_dir).mkdir(parents=True, exist_ok=True)

    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.replace("sqlite:///", "", 1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


_ensure_data_dirs()

is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


if is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        # Improve SQLite behavior under concurrent read/write access.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


# #region agent log
_DEBUG_WRITE_PREFIXES = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "COMMIT", "BEGIN", "ROLLBACK")


@event.listens_for(engine, "before_cursor_execute")
def _debug_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    _stmt = str(statement or "").strip()
    _head = _stmt.split("\n", 1)[0][:140].upper()
    if not _head.startswith(_DEBUG_WRITE_PREFIXES):
        return
    _debug_log(
        "H1",
        "sql_write",
        {
            "stmt_head": _stmt.split("\n", 1)[0][:200],
            "thread": _debug_threading.get_ident(),
            "conn_id": id(conn),
        },
        location="database.py:before_cursor_execute",
    )
# #endregion


def get_db() -> Generator[Session]:
    db = SessionLocal()
    # #region agent log
    _dbg_id = next(_debug_session_counter)
    _dbg_start = _debug_time.monotonic()
    with _debug_active_lock:
        _debug_active_sessions[_dbg_id] = {"start": _dbg_start}
        _snapshot_ids = sorted(_debug_active_sessions.keys())
    _debug_log(
        "H2",
        "get_db_enter",
        {"dbg_session_id": _dbg_id, "concurrent_sessions": _snapshot_ids, "thread": _debug_threading.get_ident()},
        location="database.py:get_db:enter",
    )
    # #endregion
    try:
        yield db
    finally:
        # #region agent log
        try:
            _in_tx = bool(db.in_transaction())
        except Exception:
            _in_tx = None
        with _debug_active_lock:
            _debug_active_sessions.pop(_dbg_id, None)
            _snapshot_ids_exit = sorted(_debug_active_sessions.keys())
        _debug_log(
            "H2",
            "get_db_exit",
            {
                "dbg_session_id": _dbg_id,
                "elapsed_s": round(_debug_time.monotonic() - _dbg_start, 3),
                "in_transaction_before_close": _in_tx,
                "remaining_sessions": _snapshot_ids_exit,
                "thread": _debug_threading.get_ident(),
            },
            location="database.py:get_db:exit",
        )
        # #endregion
        db.close()
