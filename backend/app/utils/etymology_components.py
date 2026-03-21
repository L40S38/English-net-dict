"""語源成分テキストの正規化・検証（パーサーと保存の両方で利用）。"""
from __future__ import annotations

import re

# 品詞ラベルやテンプレート引数として成分に含めたくない語
KNOWN_POS_LABELS: frozenset[str] = frozenset(
    {"noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction"}
)

# 平文説明や比較メモで頻出する一般語。語源成分としては採用しない。
ETYMOLOGY_PLUS_STOPWORDS: frozenset[str] = frozenset(
    {"variant", "form", "cognate", "noun", "verb", "compare", "compar", "etc", "cf"}
)

# 候補語列フォールバック時に除外するメタ語。
ETYMOLOGY_META_LEMMA_BLOCKLIST: frozenset[str] = frozenset({"etc", "e.g", "i.e", "cf", "compar"})

# 日本語の「語源ラベル」（接尾辞・接頭辞・品詞形成など）に含まれる語。これらを含む文字列は無視する。
# 日本語由来の単語（津波・空手など）は含めないので、一律に日本語を弾かない。
JAPANESE_LABEL_SUBSTRINGS: tuple[str, ...] = (
    "接尾辞",
    "接頭辞",
    "名詞形成",
    "動詞形成",
    "形容詞形成",
    "語根要素",
    "接頭要素",
    "語源要素",
)

# named 引数でリンク・品詞・メタ情報を示すプレフィックス（これで始まる or 含む場合は無視）
NAMED_PARAM_LINK_POS_PREFIXES: tuple[str, ...] = (
    "id1=",
    "id2=",
    "pos1=",
    "pos2=",
    "t1=",
    "t2=",
    "lang=",
    "nocat=",
    "gloss1=",
    "gloss2=",
    "alt1=",
    "alt2=",
)


def _is_japanese_etymology_label(text: str) -> bool:
    """Wiktionary 等の日本語ラベル（名詞形成接尾辞など）か。由来語（津波等）は False。"""
    t = (text or "").strip()
    if not t:
        return False
    for sub in JAPANESE_LABEL_SUBSTRINGS:
        if sub in t:
            return True
    return False


def _is_named_param_link_or_pos(text: str) -> bool:
    """リンク・品詞・メタ情報を示す named 引数形式か。由来でないなら True（除外する）。"""
    t = (text or "").strip()
    if "=" not in t:
        return False
    # id1=, pos1=, t1=, lang= など明らかにメタ情報の形式なら除外
    lower = t.lower()
    for prefix in NAMED_PARAM_LINK_POS_PREFIXES:
        if prefix in lower or lower.startswith(prefix.rstrip("=")):
            return True
    return True  # それ以外の key=value も由来語としては扱わない


def looks_like_morpheme(text: str) -> bool:
    """語根・接辞らしい文字列か（named param・品詞・日本語ラベルは False）。日本語由来語（津波等）は True。"""
    t = (text or "").strip()
    if not t or len(t) > 64:
        return False
    # Wiktionary のリンク/ID 表記 <id:...> 等は語根でない
    if re.search(r"<[^>]+>", t):
        return False
    if _is_named_param_link_or_pos(t):
        return False
    lower = t.lower()
    if lower in KNOWN_POS_LABELS:
        return False
    # 日本語ラベルのみ無視。日本語由来語は許可する（CJK を含んでいてもラベルでなければ OK）
    if re.search(r"[\u3000-\u9fff\uac00-\ud7af\uff00-\uffef]", t):
        if _is_japanese_etymology_label(t):
            return False
        return True  # 津波・空手など
    if not re.search(r"[a-zA-Z\u00c0-\u024f]", t):
        return False
    return True


def normalize_component_text(text: str) -> str | None:
    """テンプレート残り（m|la|mittere||送る）から語根部分を抜き出す。不正なら None。"""
    t = (text or "").strip()
    if not t:
        return None
    # Wiktionary のリンク/ID 表記 <id:...> 等を除去して語根だけ取り出す
    t = re.sub(r"<[^>]+>", "", t).strip()
    if not t:
        return None
    if "|" in t:
        parts = [p.strip() for p in t.split("|") if p.strip()]
        best = None
        for p in parts:
            if "=" in p:
                continue
            if looks_like_morpheme(p) and (best is None or len(p) > len(best or "")):
                best = p
        if best:
            return best
        return None
    if looks_like_morpheme(t):
        return t
    return None
