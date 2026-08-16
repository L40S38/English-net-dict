from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from pathlib import Path

from openai import OpenAI

from core.config import settings

_CACHE_DIR = Path(settings.data_dir) / "cache"
_CACHE_PATH = _CACHE_DIR / "embedding_cache.db"
_EMBED_MODEL = "text-embedding-3-small"


def _connect() -> sqlite3.Connection:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_CACHE_PATH, timeout=30)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS embedding_cache (
          cache_key TEXT PRIMARY KEY,
          model TEXT NOT NULL,
          text_value TEXT NOT NULL,
          embedding_json TEXT NOT NULL
        )
        """
    )
    return conn


def _cache_key(model_name: str, text: str) -> str:
    payload = f"{model_name}\n{text.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_many(model_name: str, texts: list[str]) -> dict[str, list[float]]:
    keys = [_cache_key(model_name, text) for text in texts]
    if not keys:
        return {}
    placeholders = ",".join("?" for _ in keys)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT text_value, embedding_json
            FROM embedding_cache
            WHERE cache_key IN ({placeholders}) AND model = ?
            """,
            [*keys, model_name],
        ).fetchall()
    out: dict[str, list[float]] = {}
    for text_value, embedding_json in rows:
        try:
            values = [float(x) for x in str(embedding_json).split(",") if x]
            if values:
                out[str(text_value)] = values
        except ValueError:
            continue
    return out


def _save_many(model_name: str, text_to_embedding: dict[str, list[float]]) -> None:
    if not text_to_embedding:
        return
    rows: list[tuple[str, str, str, str]] = []
    for text, embedding in text_to_embedding.items():
        key = _cache_key(model_name, text)
        values = ",".join(str(float(v)) for v in embedding)
        rows.append((key, model_name, text, values))
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO embedding_cache (cache_key, model, text_value, embedding_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
              model = excluded.model,
              text_value = excluded.text_value,
              embedding_json = excluded.embedding_json
            """,
            rows,
        )


def embed_texts_sync(texts: list[str], *, model_name: str = _EMBED_MODEL) -> list[list[float]]:
    cleaned = [str(t).strip() for t in texts]
    cached = _load_many(model_name, cleaned)
    missing = [text for text in cleaned if text and text not in cached]

    if missing and settings.openai_api_key:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(model=model_name, input=missing)
        fetched: dict[str, list[float]] = {}
        for text, item in zip(missing, response.data, strict=False):
            fetched[text] = [float(v) for v in item.embedding]
        _save_many(model_name, fetched)
        cached.update(fetched)

    output: list[list[float]] = []
    for text in cleaned:
        if not text:
            output.append([])
            continue
        values = cached.get(text, [])
        output.append(values)
    return output


async def embed_texts(texts: list[str], *, model_name: str = _EMBED_MODEL) -> list[list[float]]:
    return await asyncio.to_thread(embed_texts_sync, texts, model_name=model_name)

