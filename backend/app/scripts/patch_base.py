from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

# backend をカレントにして実行する想定
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.database import Base, SessionLocal, engine
from app.migrations import run_runtime_migrations
from app.models import Word
from app.services.scraper import build_scrapers


@dataclass
class FieldDiff:
    name: str
    before: Any
    after: Any


def prepare_database() -> None:
    Base.metadata.create_all(bind=engine)
    run_runtime_migrations(engine)


def create_session() -> Session:
    return SessionLocal()


def load_words(
    db: Session,
    *,
    word_filter: str | None = None,
    limit: int | None = None,
    joinedloads: tuple = (),
) -> list[Word]:
    stmt = select(Word)
    for jl in joinedloads:
        stmt = stmt.options(jl)
    stmt = stmt.order_by(Word.id)
    if word_filter:
        stmt = stmt.where(func.lower(Word.word) == word_filter.strip().lower())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).unique())


def normalize_phrase_entries(raw_phrases: object) -> list[dict[str, str]]:
    if not isinstance(raw_phrases, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in raw_phrases:
        if isinstance(item, str):
            phrase = item.strip()
            if phrase:
                normalized.append({"phrase": phrase, "meaning": ""})
            continue
        if not isinstance(item, dict):
            continue
        phrase = str(item.get("phrase", item.get("text", ""))).strip()
        if not phrase:
            continue
        meaning = str(item.get("meaning", item.get("meaning_en", item.get("meaning_ja", "")))).strip()
        normalized.append({"phrase": phrase, "meaning": meaning})
    return normalized


def is_multi_token(text: str) -> bool:
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    return len(tokens) >= 2


async def scrape_all(word_text: str) -> list[dict]:
    scrapers = build_scrapers()
    tasks = [scraper.scrape(word_text) for scraper in scrapers]
    return list(await asyncio.gather(*tasks))


def debug_json(value: object, max_len: int = 800) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true", help="更新せずに変更前後だけ表示")
    parser.add_argument("--limit", type=int, default=None, metavar="N", help="先頭 N 件だけ処理")
    parser.add_argument("--word", type=str, default=None, help="指定した単語のみ処理（完全一致・大文字小文字無視）")


def print_diffs(diffs: list[FieldDiff], indent: str = "    ") -> None:
    for diff in diffs:
        print(f"{indent}{diff.name}(before): {debug_json(diff.before)}")
        print(f"{indent}{diff.name}(after):  {debug_json(diff.after)}")


def print_summary(updated: int, skipped: int, errors: int) -> None:
    print("---")
    print(f"UPDATED: {updated}")
    print(f"SKIPPED: {skipped}")
    print(f"ERRORS: {errors}")

