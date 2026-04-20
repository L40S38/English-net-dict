from __future__ import annotations

import argparse

from sqlalchemy.orm import joinedload

from core.models import Etymology, Word
from core.utils.etymology_components import (
    JAPANESE_LABEL_SUBSTRINGS,
    KNOWN_POS_LABELS,
    looks_like_morpheme,
    normalize_component_text,
)
from database_build.ops.common import create_session, prepare_database
from database_build.selectors import load_words

JOINEDLOADS = (joinedload(Word.etymology).joinedload(Etymology.component_items),)


def _classify_issue(text: str, normalized: str | None) -> str:
    t = (text or "").strip()
    if not t:
        return "empty"
    if normalized is None:
        if "=" in t:
            return "named_param"
        if t.lower() in KNOWN_POS_LABELS:
            return "pos_label"
        if any(sub in t for sub in JAPANESE_LABEL_SUBSTRINGS):
            return "japanese_label"
        if "|" in t:
            return "template_residue"
        if not looks_like_morpheme(t):
            return "non_morpheme"
        return "invalid"
    if normalized != t:
        if "<" in t and ">" in t:
            return "link_fragment"
        return "template_residue"
    return "ok"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check etymology component parse quality")
    parser.add_argument("--db", type=str, default=None, help="DB path or SQLAlchemy URL")
    parser.add_argument("--word", type=str, default=None)
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args()

    prepare_database(args.db)
    db = create_session(args.db)
    try:
        words = load_words(db, word_filter=args.word, joinedloads=JOINEDLOADS)
        rows: list[tuple[str, str, str | None, str]] = []
        for word in words:
            if not word.etymology:
                continue
            for item in word.etymology.component_items:
                text = (item.component_text or "").strip()
                norm = normalize_component_text(text) if text else None
                issue = _classify_issue(text, norm)
                rows.append((word.word, text, norm, issue))
        if args.csv:
            print("word,component_text,normalized,issue")
            for word, text, norm, issue in rows:
                text_esc = text.replace('"', '""')
                norm_esc = (norm or "").replace('"', '""')
                print(f'"{word}","{text_esc}","{norm_esc}","{issue}"')
            return
        by_issue: dict[str, int] = {}
        for _, _, _, issue in rows:
            by_issue[issue] = by_issue.get(issue, 0) + 1
        print(f"TOTAL_COMPONENTS: {len(rows)}")
        for key in sorted(by_issue):
            print(f"{key}: {by_issue[key]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
