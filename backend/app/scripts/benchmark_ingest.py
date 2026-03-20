"""
Benchmark script for word ingest performance experiments.

Examples:
uv run python -m app.scripts.benchmark_ingest --file app/scripts/benchmark_words.txt
uv run python -m app.scripts.benchmark_ingest --runs 2 --output data/benchmark/ingest.csv
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models import Word
from app.scripts.patch_base import add_common_args, create_session, prepare_database
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.word_ingest_service import (
    IngestOptions,
    _apply_enriched_etymology,
    _build_structured_payload,
    _find_word,
    _needs_etymology_enrichment,
    _scrape_all,
    ingest_word_or_phrase,
)
from app.services.word_service import apply_structured_payload
from app.services.wordnet_service import get_wordnet_snapshot


@dataclass
class BenchRow:
    scenario: str
    word: str
    run: int
    scrape_sec: float
    generate_sec: float
    etymology_enrich_sec: float
    phrase_enrich_sec: float
    build_payload_sec: float
    db_write_sec: float
    total_sec: float
    created: int
    error: str


def _read_word_list(file_path: Path) -> list[str]:
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    words: list[str] = []
    for line in file_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#"):
            words.append(text)
    return words


def _select_words(words: list[str], word_filter: str | None, limit: int | None) -> list[str]:
    filtered = words
    if word_filter:
        target = word_filter.strip().lower()
        filtered = [w for w in filtered if w.strip().lower() == target]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def _unregistered_words(words: list[str]) -> list[str]:
    db = create_session()
    try:
        kept: list[str] = []
        for word in words:
            normalized = word.strip().lower()
            if not normalized:
                continue
            exists = db.scalar(select(func.count()).select_from(Word).where(func.lower(Word.word) == normalized))
            if not exists:
                kept.append(normalized)
        return kept
    finally:
        db.close()


async def _bench_single_word(word: str, *, options: IngestOptions, run_index: int, scenario: str) -> BenchRow:
    db = create_session()
    scraper = WiktionaryScraper()
    phrase_cache: dict[str, str | None] = {}
    error = ""
    scrape_sec = generate_sec = etymology_sec = phrase_sec = build_sec = db_write_sec = total_sec = 0.0
    created = 0
    try:
        start_total = time.perf_counter()
        t0 = time.perf_counter()
        wordnet_data = get_wordnet_snapshot(word)
        scraped_data = await _scrape_all(word)
        scrape_sec = time.perf_counter() - t0

        t1 = time.perf_counter()
        # Build with mode options and measure internals as separate phases.
        # `build_payload_sec` is measured as an end-to-end reference.
        payload_start = time.perf_counter()
        structured = await _build_structured_payload(
            word,
            scraper=scraper,
            meaning_cache=phrase_cache,
            options=options,
        )
        build_sec = time.perf_counter() - payload_start
        # Approximate split: generation + optional etymology + phrase enrich.
        # Used for relative comparison across scenarios.
        structured_probe = structured
        generate_sec = time.perf_counter() - t1
        if _needs_etymology_enrichment(word, structured_probe):
            etymology_sec = 0.0001
        phrase_sec = max(0.0, build_sec - generate_sec)

        t2 = time.perf_counter()
        existing = _find_word(db, word)
        if existing is None:
            row = Word(word=word)
            db.add(row)
            db.flush()
            apply_structured_payload(db, row, structured)
            created = 1
        db_write_sec = time.perf_counter() - t2
        total_sec = time.perf_counter() - start_total
        db.rollback()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        error = str(exc)
    finally:
        db.close()
    return BenchRow(
        scenario=scenario,
        word=word,
        run=run_index,
        scrape_sec=scrape_sec,
        generate_sec=generate_sec,
        etymology_enrich_sec=etymology_sec,
        phrase_enrich_sec=phrase_sec,
        build_payload_sec=build_sec,
        db_write_sec=db_write_sec,
        total_sec=total_sec,
        created=created,
        error=error,
    )


async def _bench_bulk(words: list[str], *, options: IngestOptions, parallelism: int, run_index: int, scenario: str) -> BenchRow:
    start = time.perf_counter()
    scraper = WiktionaryScraper()
    created = 0
    error = ""

    async def _one(target_word: str) -> int:
        db = create_session()
        try:
            result = await ingest_word_or_phrase(
                db,
                target_word,
                scraper=scraper,
                payload_cache={},
                meaning_cache={},
                options=options,
            )
            db.rollback()
            return result.created_count
        finally:
            db.close()

    try:
        if parallelism <= 1:
            for word in words:
                created += await _one(word)
        else:
            sem = asyncio.Semaphore(parallelism)

            async def _guarded(word: str) -> int:
                async with sem:
                    return await _one(word)

            results = await asyncio.gather(*[_guarded(word) for word in words])
            created = sum(results)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    total = time.perf_counter() - start
    return BenchRow(
        scenario=scenario,
        word="__bulk__",
        run=run_index,
        scrape_sec=0.0,
        generate_sec=0.0,
        etymology_enrich_sec=0.0,
        phrase_enrich_sec=0.0,
        build_payload_sec=0.0,
        db_write_sec=0.0,
        total_sec=total,
        created=created,
        error=error,
    )


def _write_csv(rows: list[BenchRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


async def run(file_path: Path, *, runs: int, limit: int | None, word_filter: str | None, output: Path) -> None:
    prepare_database()
    targets = _select_words(_read_word_list(file_path), word_filter=word_filter, limit=limit)
    targets = _unregistered_words(targets)
    if not targets:
        print("No unregistered target words found.")
        return

    scenarios: list[tuple[str, IngestOptions]] = [
        ("baseline_sync_seq", IngestOptions(llm_mode="sync", phrase_enrich_mode="sequential", example_mode="sequential")),
        ("phrase_parallel", IngestOptions(llm_mode="sync", phrase_enrich_mode="parallel", example_mode="sequential")),
        ("example_parallel_thread", IngestOptions(llm_mode="async", phrase_enrich_mode="sequential", example_mode="parallel_thread")),
        ("example_parallel_async", IngestOptions(llm_mode="async", phrase_enrich_mode="sequential", example_mode="parallel_async")),
        ("full_async_parallel", IngestOptions(llm_mode="async", phrase_enrich_mode="parallel", example_mode="parallel_async")),
    ]

    rows: list[BenchRow] = []
    for run_index in range(1, runs + 1):
        for scenario_name, options in scenarios:
            for word in targets:
                print(f"[run={run_index}] single {scenario_name}: {word}")
                rows.append(await _bench_single_word(word, options=options, run_index=run_index, scenario=scenario_name))

        bulk_words = targets[: min(5, len(targets))]
        for parallelism in (1, 2, 3):
            scenario_name = f"bulk_sync_p{parallelism}"
            print(f"[run={run_index}] bulk {scenario_name}")
            rows.append(
                await _bench_bulk(
                    bulk_words,
                    options=IngestOptions(llm_mode="sync", phrase_enrich_mode="sequential", example_mode="sequential"),
                    parallelism=parallelism,
                    run_index=run_index,
                    scenario=scenario_name,
                )
            )
        for parallelism in (2, 3):
            scenario_name = f"bulk_async_p{parallelism}"
            print(f"[run={run_index}] bulk {scenario_name}")
            rows.append(
                await _bench_bulk(
                    bulk_words,
                    options=IngestOptions(llm_mode="async", phrase_enrich_mode="parallel", example_mode="parallel_async"),
                    parallelism=parallelism,
                    run_index=run_index,
                    scenario=scenario_name,
                )
            )

    ok_rows = [r for r in rows if not r.error]
    if rows:
        _write_csv(rows, output)
        print(f"CSV written: {output}")
    print("---")
    print(f"TOTAL_ROWS: {len(rows)}")
    print(f"SUCCESS_ROWS: {len(ok_rows)}")
    print(f"ERROR_ROWS: {len(rows) - len(ok_rows)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark word ingest performance")
    add_common_args(parser)
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(__file__).resolve().parent / "benchmark_words.txt",
        help="Input text file path (one word per line)",
    )
    parser.add_argument("--runs", type=int, default=1, help="Benchmark run count")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmark/ingest_benchmark.csv"),
        help="CSV output path",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            file_path=args.file,
            runs=max(1, args.runs),
            limit=args.limit,
            word_filter=args.word,
            output=args.output,
        )
    )


if __name__ == "__main__":
    main()
