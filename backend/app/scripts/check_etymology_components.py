"""
登録済み単語の語源成分を一覧し、ミスパース候補（テンプレート残り・品詞・日本語ラベル等）を検出する。

表示時には正規化により不正な成分は非表示・短縮されるが、DB に残っている件数を把握するために利用する。

使い方（backend をカレントに、venv 等を有効化した状態で）:
  python -m app.scripts.check_etymology_components       # 集計＋問題ありを最大50件ずつ表示
  python -m app.scripts.check_etymology_components --csv  # 全件を CSV で出力
"""
from __future__ import annotations

import argparse
from sqlalchemy.orm import joinedload

from app.models import Etymology, Word
from app.scripts.patch_base import create_session, load_words, prepare_database
from app.utils.etymology_components import (
    JAPANESE_LABEL_SUBSTRINGS,
    KNOWN_POS_LABELS,
    looks_like_morpheme,
    normalize_component_text,
)


def _classify_issue(text: str, normalized: str | None) -> str:
    """問題の種別を返す（etymology_components の正規化・判定方針に合わせる）。"""
    t = (text or "").strip()
    if not t:
        return "empty"
    if normalized is None:
        if "=" in t:
            return "named_param"  # リンク・品詞・メタ情報の named 引数
        if t.lower() in KNOWN_POS_LABELS:
            return "pos_label"  # 品詞ラベル（無視）
        if any(sub in t for sub in JAPANESE_LABEL_SUBSTRINGS):
            return "japanese_label"  # 日本語ラベル（名詞形成接尾辞等）。日本語由来語は ok 扱い
        if "|" in t:
            return "template_residue"  # テンプレート残りで抽出できなかった
        if not looks_like_morpheme(t):
            return "non_morpheme"  # 他言語（ギリシャ・サンスクリット等）やその他
        return "invalid"
    if normalized != t:
        if "<" in t and ">" in t:
            return "link_fragment"  # <id:...> 等のリンク表記を除去して語根のみ表示
        return "template_residue"  # テンプレート残りから語根を抽出した（表示は normalized）
    return "ok"


# 集計・表示順とラベル（方針に合わせた説明）
ISSUE_ORDER_AND_LABELS: list[tuple[str, str]] = [
    ("template_residue", "テンプレート残り（| 含む。表示時は語根のみ抽出）"),
    ("link_fragment", "リンク/ID 表記（<id:...> 等を除去して語根のみ表示）"),
    ("pos_label", "品詞ラベル（noun/verb 等。無視）"),
    ("japanese_label", "日本語ラベル（接尾辞・接頭辞・名詞形成等。無視。日本語由来語は ok）"),
    ("named_param", "named 引数（id1=, pos1=, t1=, lang= 等。無視）"),
    ("non_morpheme", "語根らしくない（他言語表記・その他。無視）"),
    ("invalid", "不正（その他）"),
    ("empty", "空"),
    ("ok", "問題なし"),
]


JOINEDLOADS = (
    joinedload(Word.etymology).joinedload(Etymology.component_items),
)


def run(output_csv: bool = False, word_filter: str | None = None) -> None:
    prepare_database()
    db = create_session()
    try:
        words = load_words(db, word_filter=word_filter, joinedloads=JOINEDLOADS)
        total_words = len(words)
        words_with_etymology = [w for w in words if w.etymology and w.etymology.component_items]
        total_components = sum(
            len(w.etymology.component_items) for w in words_with_etymology if w.etymology
        )

        rows: list[tuple[str, str, str | None, str]] = []
        for word in words_with_etymology:
            if not word.etymology:
                continue
            for item in word.etymology.component_items:
                text = (item.component_text or "").strip()
                norm = normalize_component_text(text) if text else None
                issue = _classify_issue(text, norm)
                rows.append((word.word, text, norm, issue))

        # 集計
        by_issue: dict[str, list[tuple[str, str, str | None]]] = {}
        for word, text, norm, issue in rows:
            by_issue.setdefault(issue, []).append((word, text, norm))

        # 表示
        if output_csv:
            print("word,component_text,normalized,issue")
            for word, text, norm, issue in rows:
                norm_str = norm if norm is not None else ""
                # CSV 用にダブルクォート・カンマエスケープ
                text_esc = text.replace('"', '""') if text else ""
                norm_esc = (norm or "").replace('"', '""')
                print(f'"{word}","{text_esc}","{norm_esc}","{issue}"')
            return

        print(f"登録単語数: {total_words}")
        print(f"語源あり（成分1件以上）: {len(words_with_etymology)} 単語")
        print(f"語源成分レコード数: {total_components}")
        print()

        for issue_key, label in ISSUE_ORDER_AND_LABELS:
            items = by_issue.get(issue_key, [])
            if not items:
                continue
            print(f"【{label}】 {len(items)} 件")
            if issue_key != "ok":
                for word, text, norm in items[:50]:  # 最大50件表示
                    norm_str = f" → {norm}" if norm is not None else " (表示で非表示)"
                    print(f"  {word}: {text!r}{norm_str}")
                if len(items) > 50:
                    print(f"  ... 他 {len(items) - 50} 件")
            print()

        problem_issue_keys = [
            "template_residue", "link_fragment", "pos_label", "japanese_label", "named_param",
            "non_morpheme", "invalid", "empty",
        ]
        problem_count = sum(len(by_issue.get(k, [])) for k in problem_issue_keys)
        if problem_count > 0:
            print(f"ミスパース候補 合計: {problem_count} 件（上記の通り。表示時には正規化で除外または短縮されます）")
        else:
            print("ミスパース候補は 0 件でした。")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="登録単語の語源成分を一覧し、ミスパース候補を検出"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="CSV で全件出力（word, component_text, normalized, issue）",
    )
    parser.add_argument("--word", type=str, default=None, help="指定した単語のみ処理（完全一致・大文字小文字無視）")
    args = parser.parse_args()
    run(output_csv=args.csv, word_filter=args.word)


if __name__ == "__main__":
    main()
