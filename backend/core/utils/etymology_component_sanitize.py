"""Wiktionary 由来の語源成分テキストを保存・表示前にサニタイズする。"""

from __future__ import annotations

import re
import unicodedata

from core.utils.etymology_components import (
    JAPANESE_LABEL_SUBSTRINGS,
    KNOWN_POS_LABELS,
    looks_like_morpheme,
    normalize_component_text,
)


def _is_japanese_etymology_label_token(s: str) -> bool:
    """日本語の語源メタラベル（名詞形成接尾辞等）か。由来語そのものは除外しない。"""
    for sub in JAPANESE_LABEL_SUBSTRINGS:
        if sub in s:
            return True
    return False


def _token_allow_non_latin_etymology(s: str) -> bool:
    """ギリシャ語由来など、looks_like_morpheme が主にラテン字を想定して False になりがちなトークンを救済する。

    プレビュー30件で pharmacy の φαρμακεία 等が該当する。
    """
    if "|" in s or "=" in s or "<" in s:
        return False
    if len(s) > 64 or not s.strip():
        return False
    if _is_japanese_etymology_label_token(s):
        return False
    has_letter = False
    for ch in s:
        if ch in "*-–—·'ʼ":
            continue
        cat = unicodedata.category(ch)
        if cat.startswith("L"):
            has_letter = True
        elif cat in ("Mn", "Mc", "Nd"):
            continue
        elif ch.isspace():
            continue
        else:
            return False
    return has_letter


def sanitize_etymology_component_token(raw: str) -> str | None:
    """語源成分として採用する文字列を返す。ノイズなら None。

    tmp-etymology-refresh-preview 先頭30件で見えたパターンを主な対象とする。
    """
    s = (raw or "").strip()
    if not s:
        # 空は成分として意味がないため除外
        return None

    # 接尾辞プレースホルダのみ（例: pharmacy の no_cap に出ていた単独 `-`）を除くため
    if re.fullmatch(r"[-–—_\.·]+", s):
        return None

    # テンプレ未展開の残骸（例: commission の m|la|mittere||送る）。パイプ列は正規化で語を取れる場合のみ採用するため
    if "|" in s:
        normalized = normalize_component_text(s)
        if normalized:
            s = normalized
        else:
            return None

    # 英語品詞ラベル単体（commission の noun 等）。looks_like_morpheme が False でも救済分岐で通るのを防ぐため
    if s.lower() in KNOWN_POS_LABELS:
        return None

    # メタラベル・品詞単体・named 引数ゴミを除くため（既存 looks_like_morpheme）
    if looks_like_morpheme(s):
        return s

    # 上記に当てはまらないがギリシャ語等、由来として妥当な表記を除かないため
    if _token_allow_non_latin_etymology(s):
        return s

    return None
