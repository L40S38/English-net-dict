from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import joinedload

from core.database import engine
from core.models import Etymology, EtymologyVariant, Word
from core.services.scraper.wiktionary import WiktionaryScraper
from database_build.ops import definitions as definitions_ops
from database_build.ops import etymology as etymology_ops
from database_build.ops import etymology_components as ety_comp_ops
from database_build.ops import forms as forms_ops
from database_build.ops import inflection as inflection_ops
from database_build.ops import phrases as phrases_ops
from database_build.ops import word as word_ops
from database_build.ops.common import create_session, normalize_db_url, prepare_database
from database_build.reporting import print_diffs, print_summary
from database_build.selectors import load_words


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=str, default=None, help="DB path or SQLAlchemy URL")
    parser.add_argument("--dry-run", action="store_true", help="更新せずに差分だけ確認")
    parser.add_argument("--limit", type=int, default=None, metavar="N", help="先頭 N 件だけ処理")
    parser.add_argument("--word", type=str, default=None, help="指定した単語のみ処理")


async def _run_word_refresh(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    scraper = WiktionaryScraper()
    cache: dict[str, str | None] = {}
    updated = 0
    skipped = 0
    errors = 0
    try:
        words = load_words(
            db,
            word_filter=args.word,
            limit=args.limit,
            joinedloads=(
                joinedload(Word.definitions),
                joinedload(Word.etymology).joinedload(Etymology.component_items),
                joinedload(Word.derivations),
                joinedload(Word.related_words),
                joinedload(Word.images),
            ),
        )
        for idx, word in enumerate(words, start=1):
            try:
                diffs = await word_ops.refresh_word_data(db, word, scraper=scraper, cache=cache)
                if not diffs:
                    skipped += 1
                    if args.dry_run:
                        db.rollback()
                    continue
                if args.dry_run:
                    print(f"[{idx}/{len(words)}] {word.word} WOULD_UPDATE")
                    print_diffs(diffs)
                    db.rollback()
                    updated += 1
                    continue
                db.commit()
                updated += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"[{idx}/{len(words)}] {word.word} ERROR: {exc}")
    finally:
        db.close()
    print_summary(updated, skipped, errors)
    return 0 if errors == 0 else 1


async def _run_word_rescrape(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    errors = 0
    try:
        words = load_words(db, word_filter=args.word, limit=args.limit)
        for word in words:
            try:
                await word_ops.rescrape_word(db, word)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"{word.word} ERROR: {exc}")
    finally:
        db.close()
    return 0 if errors == 0 else 1


async def _run_word_add(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    try:
        added, skipped, errors = await word_ops.add_words_from_file(
            db,
            Path(args.file),
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
            skip_inflection_check=args.skip_inflection_check,
        )
    finally:
        db.close()
    print("---")
    print(f"ADDED: {added}")
    print(f"SKIPPED: {skipped}")
    print(f"ERRORS: {errors}")
    return 0 if errors == 0 else 1


async def _run_etymology_refresh(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    scraper = WiktionaryScraper()
    updated = 0
    skipped = 0
    errors = 0
    try:
        words = load_words(
            db,
            word_filter=args.word,
            limit=args.limit,
            joinedloads=(
                joinedload(Word.etymology).joinedload(Etymology.component_items),
                joinedload(Word.etymology).joinedload(Etymology.branches),
                joinedload(Word.etymology).joinedload(Etymology.variants),
            ),
        )
        for idx, word in enumerate(words, start=1):
            try:
                diffs = await etymology_ops.refresh_etymology_only(db, word, scraper=scraper)
                if args.enrich_if_empty:
                    diffs.extend(etymology_ops.enrich_etymology_map(db, word, only_missing=True))
                if not diffs:
                    skipped += 1
                    if args.dry_run:
                        db.rollback()
                    continue
                if args.dry_run:
                    print(f"[{idx}/{len(words)}] {word.word} WOULD_UPDATE")
                    print_diffs(diffs)
                    db.rollback()
                    updated += 1
                    continue
                db.commit()
                updated += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"[{idx}/{len(words)}] {word.word} ERROR: {exc}")
    finally:
        db.close()
    print_summary(updated, skipped, errors)
    return 0 if errors == 0 else 1


def _run_etymology_enrich(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    updated = 0
    skipped = 0
    errors = 0
    try:
        words = load_words(
            db,
            word_filter=args.word,
            limit=args.limit,
            joinedloads=(
                joinedload(Word.definitions),
                joinedload(Word.etymology).options(
                    joinedload(Etymology.component_items),
                    joinedload(Etymology.branches),
                    joinedload(Etymology.variants).joinedload(EtymologyVariant.component_items),
                    joinedload(Etymology.variants).joinedload(EtymologyVariant.component_meanings),
                    joinedload(Etymology.variants).joinedload(EtymologyVariant.language_chain_links),
                    joinedload(Etymology.language_chain_links),
                    joinedload(Etymology.component_meanings),
                ),
            ),
        )
        for idx, word in enumerate(words, start=1):
            try:
                diffs = etymology_ops.enrich_etymology_map(db, word, only_missing=args.only_missing)
                if not diffs:
                    skipped += 1
                    if args.dry_run:
                        db.rollback()
                    continue
                if args.dry_run:
                    print(f"[{idx}/{len(words)}] {word.word} WOULD_UPDATE")
                    print_diffs(diffs)
                    db.rollback()
                    updated += 1
                    continue
                db.commit()
                updated += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"[{idx}/{len(words)}] {word.word} ERROR: {exc}")
    finally:
        db.close()
    print_summary(updated, skipped, errors)
    return 0 if errors == 0 else 1


def _run_etymology_normalize_json(args: argparse.Namespace) -> int:
    db_url = normalize_db_url(args.db)
    target_engine = (
        engine
        if db_url is None
        else create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            future=True,
        )
    )
    updated, skipped, errors = etymology_ops.normalize_etymology_json(
        target_engine,
        dry_run=args.dry_run,
        limit=args.limit,
        word_filter=args.word,
    )
    print_summary(updated, skipped, errors)
    return 0 if errors == 0 else 1


async def _run_inflection_import(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    try:
        added, skipped, errors = await inflection_ops.import_inflection_csv(
            db,
            file_path=Path(args.input),
            dry_run=args.dry_run,
            limit=args.limit,
            word_filter=args.word,
        )
    finally:
        db.close()
    print("---")
    print(f"ADDED: {added}")
    print(f"SKIPPED: {skipped}")
    print(f"ERRORS: {errors}")
    return 0 if errors == 0 else 1


async def _run_inflection_report(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    try:
        words = load_words(db, word_filter=args.word, limit=args.limit, joinedloads=(joinedload(Word.etymology),))
        rows = await inflection_ops.build_inflection_report_rows(
            words,
            db,
            use_db_near=args.db_near,
            spellchecker_merge_db=args.spellchecker_merge_db,
        )
        if args.apply_known_fixes:
            updated, skipped = inflection_ops.apply_known_inflection_fixes(db)
            if args.dry_run:
                db.rollback()
            else:
                db.commit()
            print(f"KNOWN_FIXES: updated={updated} skipped={skipped}")
        inflection_ops.write_inflection_report(Path(args.output), rows)
        print(f"Report written: {args.output}")
    finally:
        db.close()
    return 0


async def _run_phrases_enrich(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    scraper = WiktionaryScraper()
    cache: dict[str, str | None] = {}
    updated = 0
    skipped = 0
    errors = 0
    try:
        words = load_words(
            db,
            word_filter=args.word,
            limit=args.limit,
            joinedloads=(joinedload(Word.derivations), joinedload(Word.related_words)),
        )
        for idx, word in enumerate(words, start=1):
            try:
                diffs = await phrases_ops.enrich_phrase_meanings(db, word, scraper=scraper, cache=cache)
                if not diffs:
                    skipped += 1
                    if args.dry_run:
                        db.rollback()
                    continue
                if args.dry_run:
                    print(f"[{idx}/{len(words)}] {word.word} WOULD_UPDATE")
                    print_diffs(diffs)
                    db.rollback()
                    updated += 1
                    continue
                db.commit()
                updated += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"[{idx}/{len(words)}] {word.word} ERROR: {exc}")
    finally:
        db.close()
    print_summary(updated, skipped, errors)
    return 0 if errors == 0 else 1


async def _run_phrases_split(args: argparse.Namespace) -> int:
    prepare_database(args.db)
    db = create_session(args.db)
    ddgs_cache: dict[str, str | None] = {}
    payload_cache: dict[str, dict] = {}
    added_words = 0
    phrases_appended = 0
    phrases_skipped = 0
    errors = 0
    try:
        words = load_words(db, word_filter=args.word, limit=args.limit)
        targets = [word for word in words if " " in word.word.strip()]
        for phrase_word in targets:
            try:
                a, p, s = await phrases_ops.split_phrase_words(
                    db,
                    phrase_word,
                    ddgs_cache=ddgs_cache,
                    payload_cache=payload_cache,
                )
                added_words += a
                phrases_appended += p
                phrases_skipped += s
                if args.dry_run:
                    db.rollback()
                else:
                    db.commit()
            except Exception as exc:  # noqa: BLE001
                errors += 1
                db.rollback()
                print(f"{phrase_word.word} ERROR: {exc}")
    finally:
        db.close()
    print("---")
    print(f"ADDED_WORDS: {added_words}")
    print(f"PHRASES_APPENDED: {phrases_appended}")
    print(f"PHRASES_SKIPPED: {phrases_skipped}")
    print(f"ERRORS: {errors}")
    return 0 if errors == 0 else 1


def _run_inspect(args: argparse.Namespace) -> int:
    db_url = normalize_db_url(args.db)
    target_engine = (
        engine
        if db_url is None
        else create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            future=True,
        )
    )
    with target_engine.connect() as conn:
        if args.inspect_action == "tables":
            rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).all()
            for row in rows:
                print(row[0])
            return 0
        if args.inspect_action == "schema":
            table = args.table
            if not table:
                raise ValueError("--table is required for schema")
            rows = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
            print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2))
            return 0
    return 0


def _run_search(args: argparse.Namespace) -> int:
    db = create_session(args.db)
    try:
        keyword = (args.word or "").strip().lower()
        if not keyword:
            return 0
        rows = db.execute(
            select(Word.id, Word.word)
            .where(func.lower(Word.word).like(f"%{keyword}%"))
            .order_by(Word.id.asc())
            .limit(args.limit or 50)
        ).all()
        for row in rows:
            print(f"{row[0]}\t{row[1]}")
    finally:
        db.close()
    return 0


async def _run_preview_refresh(args: argparse.Namespace) -> int:
    args.dry_run = True
    return await _run_word_refresh(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified CLI for database_build operations")
    sub = parser.add_subparsers(dest="domain", required=True)

    word = sub.add_parser("word")
    word_sub = word.add_subparsers(dest="action", required=True)
    word_refresh = word_sub.add_parser("refresh")
    _add_common_args(word_refresh)
    word_refresh.set_defaults(handler=lambda a: asyncio.run(_run_word_refresh(a)))
    word_rescrape = word_sub.add_parser("rescrape")
    _add_common_args(word_rescrape)
    word_rescrape.set_defaults(handler=lambda a: asyncio.run(_run_word_rescrape(a)))
    word_add = word_sub.add_parser("add")
    _add_common_args(word_add)
    word_add.add_argument("--file", type=str, default="database_build/data/words_to_add.example.txt")
    word_add.add_argument("--skip-inflection-check", action="store_true")
    word_add.set_defaults(handler=lambda a: asyncio.run(_run_word_add(a)))

    ety = sub.add_parser("etymology")
    ety_sub = ety.add_subparsers(dest="action", required=True)
    ety_refresh = ety_sub.add_parser("refresh")
    _add_common_args(ety_refresh)
    ety_refresh.add_argument("--enrich-if-empty", action="store_true")
    ety_refresh.set_defaults(handler=lambda a: asyncio.run(_run_etymology_refresh(a)))
    ety_enrich = ety_sub.add_parser("enrich-map")
    _add_common_args(ety_enrich)
    ety_enrich.add_argument("--only-missing", action="store_true")
    ety_enrich.set_defaults(handler=_run_etymology_enrich)
    ety_norm = ety_sub.add_parser("normalize-json")
    _add_common_args(ety_norm)
    ety_norm.set_defaults(handler=_run_etymology_normalize_json)

    ety_comp = sub.add_parser("etymology-components")
    ety_comp_sub = ety_comp.add_subparsers(dest="action", required=True)
    ety_comp_create = ety_comp_sub.add_parser("create")
    _add_common_args(ety_comp_create)
    ety_comp_create.add_argument("--component", required=True)

    async def _handler_comp_create(a: argparse.Namespace) -> int:
        db = create_session(a.db)
        try:
            await ety_comp_ops.create_component_if_missing(db, a.component.strip().lower())
        finally:
            db.close()
        return 0

    ety_comp_create.set_defaults(handler=lambda a: asyncio.run(_handler_comp_create(a)))
    ety_comp_rescrape = ety_comp_sub.add_parser("rescrape")
    _add_common_args(ety_comp_rescrape)
    ety_comp_rescrape.add_argument("--component", required=True)

    async def _handler_comp_rescrape(a: argparse.Namespace) -> int:
        db = create_session(a.db)
        try:
            await ety_comp_ops.rescrape_component(db, a.component.strip().lower())
        finally:
            db.close()
        return 0

    ety_comp_rescrape.set_defaults(handler=lambda a: asyncio.run(_handler_comp_rescrape(a)))

    phrases = sub.add_parser("phrases")
    phrases_sub = phrases.add_subparsers(dest="action", required=True)
    phrases_enrich = phrases_sub.add_parser("enrich")
    _add_common_args(phrases_enrich)
    phrases_enrich.set_defaults(handler=lambda a: asyncio.run(_run_phrases_enrich(a)))
    phrases_split = phrases_sub.add_parser("split")
    _add_common_args(phrases_split)
    phrases_split.set_defaults(handler=lambda a: asyncio.run(_run_phrases_split(a)))

    inflection = sub.add_parser("inflection")
    inflection_sub = inflection.add_subparsers(dest="action", required=True)
    inflection_import = inflection_sub.add_parser("import")
    _add_common_args(inflection_import)
    inflection_import.add_argument("--input", required=True, type=str)
    inflection_import.set_defaults(handler=lambda a: asyncio.run(_run_inflection_import(a)))
    inflection_report = inflection_sub.add_parser("report")
    _add_common_args(inflection_report)
    inflection_report.add_argument("--output", required=True, type=str)
    inflection_report.add_argument("--apply-known-fixes", action="store_true")
    inflection_report.add_argument("--db-near", action=argparse.BooleanOptionalAction, default=False)
    inflection_report.add_argument("--spellchecker-merge-db", action=argparse.BooleanOptionalAction, default=False)
    inflection_report.set_defaults(handler=lambda a: asyncio.run(_run_inflection_report(a)))

    inspect = sub.add_parser("inspect")
    inspect_sub = inspect.add_subparsers(dest="inspect_action", required=True)
    inspect_tables = inspect_sub.add_parser("tables")
    _add_common_args(inspect_tables)
    inspect_tables.set_defaults(handler=_run_inspect)
    inspect_schema = inspect_sub.add_parser("schema")
    _add_common_args(inspect_schema)
    inspect_schema.add_argument("--table", required=True)
    inspect_schema.set_defaults(handler=_run_inspect)

    search = sub.add_parser("search")
    _add_common_args(search)
    search.set_defaults(handler=_run_search)

    preview = sub.add_parser("preview")
    preview_sub = preview.add_subparsers(dest="preview_action", required=True)
    preview_refresh = preview_sub.add_parser("refresh")
    _add_common_args(preview_refresh)
    preview_refresh.set_defaults(handler=lambda a: asyncio.run(_run_preview_refresh(a)))

    defs = sub.add_parser("definitions")
    defs_sub = defs.add_subparsers(dest="action", required=True)
    defs_regen = defs_sub.add_parser("regenerate-examples")
    _add_common_args(defs_regen)

    def _run_defs_regen(a: argparse.Namespace) -> int:
        prepare_database(a.db)
        db = create_session(a.db)
        updated = 0
        skipped = 0
        errors = 0
        try:
            words = load_words(db, word_filter=a.word, limit=a.limit, joinedloads=(joinedload(Word.definitions),))
            for word in words:
                try:
                    diffs = definitions_ops.regenerate_examples_for_word(word)
                    if not diffs:
                        skipped += 1
                        continue
                    if a.dry_run:
                        db.rollback()
                    else:
                        db.commit()
                    updated += 1
                except Exception:  # noqa: BLE001
                    errors += 1
                    db.rollback()
        finally:
            db.close()
        print_summary(updated, skipped, errors)
        return 0 if errors == 0 else 1

    defs_regen.set_defaults(handler=_run_defs_regen)

    form = sub.add_parser("forms")
    form_sub = form.add_subparsers(dest="action", required=True)
    forms_marker = form_sub.add_parser("normalize-markers")
    _add_common_args(forms_marker)
    forms_noise = form_sub.add_parser("fix-noise")
    _add_common_args(forms_noise)

    async def _run_forms_marker(a: argparse.Namespace) -> int:
        db = create_session(a.db)
        updated = 0
        skipped = 0
        errors = 0
        try:
            words = load_words(db, word_filter=a.word, limit=a.limit)
            for word in words:
                try:
                    forms = dict(word.forms or {})
                    next_forms = forms_ops.normalize_marker_forms(word.word, forms)
                    if next_forms == forms:
                        skipped += 1
                        continue
                    word.forms = next_forms
                    if a.dry_run:
                        db.rollback()
                    else:
                        db.commit()
                    updated += 1
                except Exception:  # noqa: BLE001
                    errors += 1
                    db.rollback()
        finally:
            db.close()
        print_summary(updated, skipped, errors)
        return 0 if errors == 0 else 1

    async def _run_forms_noise(a: argparse.Namespace) -> int:
        db = create_session(a.db)
        updated = 0
        skipped = 0
        errors = 0
        try:
            words = load_words(db, word_filter=a.word, limit=a.limit)
            for word in words:
                forms = dict(word.forms or {})
                if not forms_ops.has_noise(forms):
                    skipped += 1
                    continue
                try:
                    next_forms = await forms_ops.refresh_forms_from_wiktionary(word.word, forms)
                    if next_forms == forms:
                        skipped += 1
                        continue
                    word.forms = next_forms
                    if a.dry_run:
                        db.rollback()
                    else:
                        db.commit()
                    updated += 1
                except Exception:  # noqa: BLE001
                    errors += 1
                    db.rollback()
        finally:
            db.close()
        print_summary(updated, skipped, errors)
        return 0 if errors == 0 else 1

    forms_marker.set_defaults(handler=lambda a: asyncio.run(_run_forms_marker(a)))
    forms_noise.set_defaults(handler=lambda a: asyncio.run(_run_forms_noise(a)))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        raise SystemExit(2)
    raise SystemExit(handler(args))


if __name__ == "__main__":
    main()
