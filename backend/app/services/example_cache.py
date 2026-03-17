from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings


_CACHE_DIR = Path(settings.data_dir) / "cache"
_CACHE_PATH = _CACHE_DIR / "example_cache.db"


def _connect() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_CACHE_PATH, timeout=30)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS example_cache (
          cache_key TEXT PRIMARY KEY,
          example_en TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """
    )
    return conn


def make_cache_key(system_prompt: str, model: str, user_content: str) -> str:
    payload = "\n".join([system_prompt.strip(), model.strip(), user_content.strip()])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_example(cache_key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT example_en FROM example_cache WHERE cache_key = :cache_key LIMIT 1",
            {"cache_key": cache_key},
        ).fetchone()
    if not row:
        return None
    value = str(row[0]).strip()
    return value or None


def save_cached_example(cache_key: str, example_en: str) -> None:
    value = (example_en or "").strip()
    if not cache_key or not value:
        return
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO example_cache (cache_key, example_en, created_at)
            VALUES (:cache_key, :example_en, :created_at)
            ON CONFLICT(cache_key) DO UPDATE SET
              example_en = excluded.example_en,
              created_at = excluded.created_at
            """,
            {
                "cache_key": cache_key,
                "example_en": value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
