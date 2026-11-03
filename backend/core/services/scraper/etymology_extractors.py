from __future__ import annotations

import re
from typing import Callable

from core.utils.etymology_component_sanitize import sanitize_etymology_component_token
from core.utils.etymology_components import (
    ETYMOLOGY_META_LEMMA_BLOCKLIST,
    ETYMOLOGY_PLUS_STOPWORDS,
    looks_like_morpheme,
)

# Wiktionary 英語 Etymology 本文から語源成分を抽出する。テンプレート優先 → 平文「+」フォールバック → 候補語列。
# 本ファイル内の説明コメントはすべて # 行コメントで統一する。

# --- 平文「A + B」型の語源行を正規表現で掴むための断片（extract_etymology_components 内の「+」マッチ用）---
# Wiktionary は「+」の直後に LRM(U+200E)/RLM 等を入れることがある。これらは \s に含まれず、
# 「over- +\u200e joy」のように見える行で「+」と右オペランドが繋がらないとマッチしなくなる。
_ETY_AFTER_PLUS = r"(?:\s|[\u00ad\u200b-\u200f\u202a-\u202e\ufeff])*"
# 右オペランド: 「joy」型（英字始まり）か、接尾辞の「-ly」型（先頭がハイフン類で [^\W\d_] に当てはまらない）。
_ETY_PLUS_RIGHT_OPERAND = (
    r"[^\W\d_][^\s,.;:)]{0,31}|[-–—\u2010][a-zA-Z\u00c0-\u024f]{1,30}"
)
# 本来は語源由来として全言語コードを許容したいが、ノイズ・誤検出・保守コストの観点から
# 現状は実データで必要な言語だけを暫定 allowlist で絞っている（不足言語は段階的に追加）。
_ETYMON_M_LANG_ALLOWLIST: frozenset[str] = frozenset(
    {
        "en",
        "enm",
        "ang",
        "ja",
        "la",
        "la-lat",
        "la-med",
        "la-vul",
        "grc",
        "fro",
        "frm",
        "xno",
        "gem-pro",
        "gmw-pro",
        "ine-pro",
        "cel-pro",
        "ath-pro",
        "non",
        "odt",
        "ofs",
        "osx",
        "goh",
        "dum",
        "ml.",
        "vl.",
    }
)

AddComponent = Callable[[str, str, str], None]

_ETYMON_LANG_ORIGIN_LABELS: dict[str, str] = {
    "la": "ラテン語由来",
    "la-lat": "後期ラテン語由来",
    "la-med": "中世ラテン語由来",
    "la-vul": "俗ラテン語由来",
    "fr": "フランス語由来",
    "fro": "古フランス語由来",
    "frm": "中期フランス語由来",
    "grc": "古代ギリシャ語由来",
    "ang": "古英語由来",
    "enm": "中英語由来",
    "xno": "アングロ・ノルマン語由来",
    "ja": "日本語由来",
}


def clean_token(value: str) -> str:
    # テンプレ引数に付くページ内アンカーを落とす（例: pactus#Noun → pactus、ramp#Verb → ramp）。
    token = value.strip()
    token = re.sub(r"^[\s\(\[\{'\"]+", "", token)
    if "#" in token:
        token = token.split("#", 1)[0].rstrip()
    # テンプレ引数に混ざる wiki マークアップ残骸を除去する（例: [[numerō]]、'''even'''）。
    token = token.replace("'''", "").replace("''", "")
    token = token.replace("[[", "").replace("]]", "")
    token = token.replace("[", "").replace("]", "")
    # wiki 展開後に残る孤立した ')' を除去し、平衡な括弧は保持する（例: in) numerō → in numerō）。
    if ")" in token:
        balanced_chars: list[str] = []
        open_parens = 0
        for ch in token:
            if ch == "(":
                open_parens += 1
                balanced_chars.append(ch)
            elif ch == ")":
                if open_parens > 0:
                    open_parens -= 1
                    balanced_chars.append(ch)
            else:
                balanced_chars.append(ch)
        token = "".join(balanced_chars)
    # surf の lang:morpheme 形式（例: ang:ā）から morpheme 部分だけを残す。
    if re.fullmatch(r"[a-z]{2,3}:.+", token):
        token = token.split(":", 1)[1]
    # 末尾除去: 文字クラス内の「,.」はカンマ〜ピリオドの範囲になりハイフン(U+002D)を含むため、
    # 「over-」の末尾ハイフンが削られ「over」になる。ピリオドは \. で区切って範囲にしない。
    token = re.sub(r"[\s\]\}',\"。．、,\.;:]+$", "", token)
    # 括弧付きの祖語形（例: *mey- (change)）は閉じ括弧を保持し、
    # 右端に余分な ')' が連なるケースだけ除去する。
    while token.endswith(")") and token.count(")") > token.count("("):
        token = token[:-1].rstrip()
    return token


def normalize_template_arg(value: str) -> str:
    # {{af|en|chemic<id:chemical>|-al}} のようなテンプレ内メタ情報を除去する。
    return re.sub(r"<[^>]+>", "", re.sub(r"\s+", "", value))


def _split_pipe_args_skip_lang(pipe_inner: str) -> list[str]:
    # テンプレ内を | で分割し、先頭が言語コード（en, la-lat 等）なら1トークン落とす。
    args = [x.strip() for x in pipe_inner.split("|") if x.strip()]
    if len(args) >= 1 and re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9-]+)?", args[0].lower()):
        return args[1:]
    return args


def _strip_leading_lang(args: list[str]) -> list[str]:
    # surf の +com/+af の直後に残る en 等をもう一度落とすときなどに使う。
    if args and re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9-]+)?", args[0].lower()):
        return args[1:]
    return args


def _contains_latin(text: str) -> bool:
    return bool(re.search(r"[a-zA-Z\u00c0-\u024f]", text or ""))


def _is_language_code_token(text: str) -> bool:
    t = (text or "").strip().lower()
    return bool(re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9-]+)?", t))


def _is_named_template_arg(text: str) -> bool:
    t = (text or "").strip()
    if not t or "=" not in t or t.startswith(":"):
        return False
    eq_idx = t.find("=")
    lt_idx = t.find("<")
    if lt_idx != -1 and eq_idx > lt_idx:
        return False
    name = t[:eq_idx].strip()
    return bool(re.fullmatch(r"[A-Za-z0-9_-]+", name))


def _split_top_level_pipes(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    brace_depth = 0
    angle_depth = 0
    i = 0
    while i < len(text):
        two = text[i : i + 2]
        if two == "{{":
            brace_depth += 1
            buf.append(two)
            i += 2
            continue
        if two == "}}" and brace_depth > 0:
            brace_depth -= 1
            buf.append(two)
            i += 2
            continue
        ch = text[i]
        if ch == "<":
            angle_depth += 1
        elif ch == ">" and angle_depth > 0:
            angle_depth -= 1
        if ch == "|" and brace_depth == 0 and angle_depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _iter_template_bodies(raw: str, names: frozenset[str]) -> list[str]:
    names_pat = "|".join(re.escape(name) for name in sorted(names))
    pattern = re.compile(r"\{\{\s*(?:" + names_pat + r")\s*\|", flags=re.IGNORECASE)
    results: list[str] = []
    idx = 0
    while idx < len(raw):
        match = pattern.search(raw, idx)
        if not match:
            break
        body_start = match.end()
        depth = 1
        i = body_start
        while i < len(raw):
            if raw.startswith("{{", i):
                depth += 1
                i += 2
                continue
            if raw.startswith("}}", i):
                depth -= 1
                if depth == 0:
                    results.append(raw[body_start:i])
                    idx = i + 2
                    break
                i += 2
                continue
            i += 1
        else:
            idx = body_start
    return results


def _extract_angle_segment(text: str, start: int) -> tuple[str | None, int]:
    if start < 0 or start >= len(text) or text[start] != "<":
        return None, start
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    return None, start + 1


def _parse_etymon_term(raw_term: str) -> tuple[str | None, str]:
    term = (raw_term or "").strip()
    if not term:
        return None, ""
    # etymon 引数の inline modifier（<id:...>, <ety:...> 等）は語形抽出時には除外する。
    term = term.split("<", 1)[0].strip()
    term = term.replace("'''", "").replace("''", "")
    if ":" in term:
        lang, tail = term.split(":", 1)
        if _is_language_code_token(lang):
            return lang.lower(), tail.strip()
    return None, term


def _normalize_etymon_keyword(raw_keyword: str) -> str:
    kw = ":" + (raw_keyword or "").strip().lstrip(":").lower()
    if kw in {":derived"}:
        return ":der"
    if kw in {":inherited"}:
        return ":inh"
    if kw in {":borrowed"}:
        return ":bor"
    if kw in {":affix"}:
        return ":af"
    if kw in {":back-formation"}:
        return ":bf"
    if kw in {":clipping"}:
        return ":clip"
    return kw


def _collect_ety_chain_terms(raw_term: str) -> list[tuple[str, str]]:
    collected: list[tuple[str, str]] = []
    visited: set[str] = set()

    def walk(text: str) -> None:
        lower = text.lower()
        idx = 0
        while True:
            pos = lower.find("<ety:", idx)
            if pos == -1:
                return
            segment, next_idx = _extract_angle_segment(text, pos)
            if segment is None:
                idx = pos + 1
                continue
            idx = next_idx
            normalized_segment = segment.strip()
            if normalized_segment in visited:
                continue
            visited.add(normalized_segment)
            if not normalized_segment.lower().startswith("ety:"):
                continue
            payload = normalized_segment[4:].strip()
            if not payload:
                continue
            first_lt = payload.find("<")
            if first_lt == -1:
                continue
            keyword = _normalize_etymon_keyword(payload[:first_lt].strip() or ":from")
            children = payload[first_lt:]
            child_idx = 0
            while child_idx < len(children):
                child_start = children.find("<", child_idx)
                if child_start == -1:
                    break
                child, child_end = _extract_angle_segment(children, child_start)
                if child is None:
                    child_idx = child_start + 1
                    continue
                child_idx = child_end
                child_text = child.strip()
                _, parsed_term = _parse_etymon_term(child_text)
                token = clean_token(parsed_term)
                core = token.lstrip("-").rstrip("-")
                if token and looks_like_morpheme(core):
                    collected.append((keyword, token))
                walk(child_text)

    walk(raw_term or "")
    return collected


def _infer_etymon_component_type(keyword: str, token: str) -> tuple[str, str]:
    kw = _normalize_etymon_keyword(keyword)
    if kw in {":af", ":afeq"}:
        if token.startswith("-"):
            return "接尾辞要素", "suffix"
        if token.endswith("-"):
            return "接頭要素", "prefix"
        return "語根要素", "root"
    if kw in {":bf", ":clip", ":deverbal"}:
        return "語源要素", "root"
    return "語源要素", "root"


def _extract_etymon_templates(raw: str, word: str, add: AddComponent) -> None:
    base = (word or "").lower().strip().strip("-")
    for body in _iter_template_bodies(raw, frozenset({"etymon", "ety"})):
        args = [x.strip() for x in _split_top_level_pipes(body)]
        if not args:
            continue
        current_lang: str | None = None
        current_keyword = ":from"
        for arg in args:
            if not arg:
                continue
            if _is_named_template_arg(arg):
                continue
            if current_lang is None and _is_language_code_token(arg):
                current_lang = arg.lower()
                continue
            if current_lang and current_lang != "en":
                break
            if arg.startswith(":"):
                current_keyword = _normalize_etymon_keyword(arg)
                continue
            if _is_language_code_token(arg):
                # `:af|en|...` のような keyword 直下の補助言語指定は語源要素ではないためスキップする。
                continue
            _, parsed_term = _parse_etymon_term(arg)
            token = clean_token(parsed_term)
            core = token.lstrip("-").rstrip("-")
            if not token or not core or not looks_like_morpheme(core):
                continue
            if token.lower().strip("-") != base:
                meaning, comp_type = _infer_etymon_component_type(current_keyword, token)
                add(token, meaning, comp_type)
            for nested_keyword, nested_token in _collect_ety_chain_terms(arg):
                nested_core = nested_token.lstrip("-").rstrip("-")
                if not nested_token or not nested_core or not looks_like_morpheme(nested_core):
                    continue
                if nested_token.lower().strip("-") == base:
                    continue
                nested_meaning, nested_type = _infer_etymon_component_type(nested_keyword, nested_token)
                add(nested_token, nested_meaning, nested_type)


def _looks_like_cjk_language_label(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and bool(re.fullmatch(r"[\u3000-\u9fff]+語", t))


def _accept_plain_plus_pair(left: str, right: str, *, compact_mode: bool = False) -> bool:
    left_token = clean_token(left)
    right_token = clean_token(right)
    if not left_token or not right_token:
        return False
    if "|" in left_token or "|" in right_token:
        return False
    if left_token.lower() in ETYMOLOGY_PLUS_STOPWORDS or right_token.lower() in ETYMOLOGY_PLUS_STOPWORDS:
        return False
    left_core = left_token.lstrip("-").rstrip("-")
    right_core = right_token.lstrip("-").rstrip("-")
    if not left_core or not right_core:
        return False
    if not looks_like_morpheme(left_core) or not looks_like_morpheme(right_core):
        return False
    if _looks_like_cjk_language_label(right_core):
        return False
    # compact 側は「in- + ラテン語」のような言語名誤検出を抑えるため右辺にラテン字を要求。
    if compact_mode and not _contains_latin(right_core):
        return False
    return True


def _extract_suf_templates(raw: str, add: AddComponent) -> None:
    # {{suf|en|stem|ly|id2=...}} / {{suffix|...}}：英語版で「tentatively」等の語源がこのテンプレのみのことがある。
    # 先頭の af/affix より前に処理し、語幹を root・接尾辞を「-ly」形式で suffix にする。
    for match in re.finditer(
        r"\{\{(?:suf|suffix)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        raw_args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if not raw_args:
            continue
        if raw_args[0].lower() != "en":
            continue
        args = _strip_leading_lang(raw_args)
        if len(args) < 2:
            continue
        stem = normalize_template_arg(args[0])
        suf_raw = normalize_template_arg(args[1])
        if not stem or not suf_raw or "=" in stem or "=" in suf_raw:
            continue
        if not looks_like_morpheme(stem):
            continue
        suf_text = suf_raw if suf_raw.startswith("-") else f"-{suf_raw}"
        if not looks_like_morpheme(suf_text.lstrip("-")):
            continue
        add(stem, "語根要素", "root")
        add(suf_text, "接尾辞要素", "suffix")


def _extract_surf_templates(raw: str, add: AddComponent) -> None:
    # {{surf|en|re-|turn}} / {{surface analysis|en|full-|fill}}：表面分析。末尾/先頭ハイフンで prefix・suffix・root を分ける。
    # {{surf|+com|en|short|fall}} / {{surf|+af|en|insure|-ance}}：先頭の +com・+af は表示用フラグのため捨て、続く言語コードも除去する。
    for match in re.finditer(
        r"\{\{(?:surf|surface analysis)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        args = _split_pipe_args_skip_lang(match.group(1))
        had_plus = False
        had_plus_suf = False
        while args and args[0].startswith("+"):
            had_plus = True
            if args[0].lower() in {"+suf", "+suffix"}:
                had_plus_suf = True
            args = args[1:]
        if had_plus:
            args = _strip_leading_lang(args)
        if not args:
            continue
        morpheme_parts: list[str] = []
        for part in args[:3]:
            text = normalize_template_arg(part)
            if not text or "=" in text:
                continue
            if not looks_like_morpheme(text.lstrip("-").rstrip("-")):
                continue
            morpheme_parts.append(text)
        for idx, text in enumerate(morpheme_parts):
            if had_plus_suf and idx > 0 and not text.startswith("-"):
                text = f"-{text}"
            if text.startswith("-"):
                add(text, "接尾辞要素", "suffix")
            elif text.endswith("-"):
                add(text, "接頭要素", "prefix")
            else:
                add(text, "語根要素", "root")


def _extract_compound_templates(raw: str, add: AddComponent) -> None:
    # {{compound|en|door|way}} / {{com|en|lap|top|t1=...}}：複合語。en のみ処理。2語目が - で始まれば suffix 扱い。
    for match in re.finditer(
        r"\{\{(?:com|compound)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        raw_args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if not raw_args:
            continue
        if raw_args[0].lower() != "en":
            continue
        args = _strip_leading_lang(raw_args)
        morphemes: list[str] = []
        for part in args[:3]:
            text = normalize_template_arg(part)
            if not text or "=" in text:
                continue
            core = text.lstrip("-").rstrip("-")
            if not looks_like_morpheme(core):
                continue
            morphemes.append(text)
        if len(morphemes) < 2:
            continue
        add(morphemes[0], "語根要素", "root")
        second = morphemes[1]
        if second.startswith("-"):
            add(second, "接尾辞要素", "suffix")
        elif second.endswith("-"):
            add(second, "接頭要素", "prefix")
        else:
            add(second, "語根要素", "root")


def _extract_confix_templates(raw: str, add: AddComponent) -> None:
    # {{confix|en|ophthalmo|logy}}：接頭+接尾の学術語。第2要素は -logy 形式の suffix に正規化する。
    for match in re.finditer(r"\{\{confix\|([^}]*)\}\}", raw, flags=re.IGNORECASE):
        raw_args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if not raw_args:
            continue
        if raw_args[0].lower() != "en":
            continue
        args = _strip_leading_lang(raw_args)
        if len(args) < 2:
            continue
        first = normalize_template_arg(args[0])
        second = normalize_template_arg(args[1])
        if not first or not second or "=" in first or "=" in second:
            continue
        if not looks_like_morpheme(first.lstrip("-").rstrip("-")):
            continue
        if not looks_like_morpheme(second.lstrip("-").rstrip("-")):
            continue
        add(first, "接頭要素", "prefix")
        suffix = second if second.startswith("-") else f"-{second}"
        add(suffix, "接尾辞要素", "suffix")


def _extract_backformation_templates(raw: str, add: AddComponent) -> None:
    # {{back-formation|en|evaluation}} / {{bf|en|illustration}} / {{back-form|en|...}}：逆成。元の長い語を root として採用する。
    for match in re.finditer(
        r"\{\{(?:back-formation|back-form|bf)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        raw_args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if not raw_args:
            continue
        if raw_args[0].lower() != "en":
            continue
        args = _strip_leading_lang(raw_args)
        if not args:
            continue
        term = re.sub(r"<[^>]+>", "", args[0]).strip()
        if not term or "=" in term:
            continue
        if not looks_like_morpheme(term.lstrip("-").rstrip("-")):
            continue
        add(term, "語根要素", "root")


def _extract_deverbal_templates(raw: str, add: AddComponent) -> None:
    # {{deverbal|en|check up}} のような句動詞由来を分割し、check / up を root として追加する。
    for match in re.finditer(r"\{\{deverbal\|([^}]*)\}\}", raw, flags=re.IGNORECASE):
        positional = [x.strip() for x in match.group(1).split("|") if x.strip() and "=" not in x]
        while positional and re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9-]+)?", positional[0].lower()):
            positional = positional[1:]
        if not positional:
            continue
        # 1つ目の語句（例: "check up"）だけを対象にし、空白区切りで語根を追加する。
        parts = [clean_token(x) for x in positional[0].split()]
        for part in parts:
            if not part:
                continue
            core = part.lstrip("-").rstrip("-")
            if not looks_like_morpheme(core):
                continue
            add(part, "語源要素", "root")


def detect_same_word_foreign_origin(raw_etymology: str, word: str) -> tuple[str, str] | None:
    # {{der|en|la|exterior}} / {{bor+|en|fr|expertise}} のような「同単語の別言語由来」を検出する。
    base = word.lower().strip().strip("-")
    for match in re.finditer(
        r"\{\{(?:der|inh|bor|uder|lbor|ubor)\+?\|([^|}]+)\|([^|}]+)\|([^|}\s]+)",
        raw_etymology,
        flags=re.IGNORECASE,
    ):
        source_lang = (match.group(2) or "").strip().lower()
        term = clean_token(match.group(3))
        if not source_lang or not term:
            continue
        if term.lower().strip().strip("-") == base:
            return source_lang, term
    return None


def _extract_af_templates(raw: str, add: AddComponent) -> None:
    # {{af|en|stem|-al}} / {{affix|...}} / {{prefix|...}}：接辞分解。第1要素を prefix、以降を root として追加。
    for match in re.finditer(
        r"\{\{(?:af|affix|prefix)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        raw_args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if not raw_args:
            continue
        if raw_args[0].lower() != "en":
            continue
        args = _strip_leading_lang(raw_args)
        if len(args) < 2:
            continue
        morpheme_parts: list[str] = []
        for part in args[:3]:
            text = normalize_template_arg(part)
            if not text or "=" in text:
                continue
            if not looks_like_morpheme(text):
                continue
            morpheme_parts.append(text)
        for idx, text in enumerate(morpheme_parts):
            add(
                text,
                "接頭要素" if idx == 0 else "語根要素",
                "prefix" if idx == 0 else "root",
            )


def _extract_pre_templates(raw: str, add: AddComponent) -> None:
    # {{pre|la-lat|nocat=1|com-|t1=...|mēnsūrātus}}：接頭辞+語幹。named（= を含む）を捨て、拡張言語コードを先頭から削ってから
    # 位置引数の先頭2つを prefix / root とする（la-lat を com- と誤認しないため af から分離している）。
    for match in re.finditer(r"\{\{pre\|([^}]*)\}\}", raw, flags=re.IGNORECASE):
        positional = [x.strip() for x in match.group(1).split("|") if x.strip() and "=" not in x]
        while positional and re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9-]+)?", positional[0].lower()):
            positional = positional[1:]
        if len(positional) < 2:
            continue
        first = normalize_template_arg(positional[0])
        second = normalize_template_arg(positional[1])
        if not first or not second:
            continue
        if not looks_like_morpheme(first.lstrip("-").rstrip("-")):
            continue
        if not looks_like_morpheme(second.lstrip("-").rstrip("-")):
            continue
        add(first, "接頭要素", "prefix")
        add(second, "語根要素", "root")


def _try_der_linked_morphemes(
    components: list[dict], raw: str, word: str, add: AddComponent
) -> None:
    # {{der|en|fro|...|From [[a]] [[bandon]]}} のように第3引数が説明文で、[[link]] に形態素が並ぶケース。
    # abandon / a+ban の特例と、リンクが2個以上あるとき末尾2つを prefix/root にする（der| のみ対象）。
    if components:
        return
    for match in re.finditer(r"\{\{der\+?\|([^}]*)\}\}", raw, flags=re.IGNORECASE):
        args = [x.strip() for x in match.group(1).split("|")]
        if len(args) < 3:
            continue
        ety_text = args[2]
        links = [x.strip() for x in re.findall(r"\[\[([^\]|]+)", ety_text) if x.strip()]
        # 対象語自身（self-word）は語源成分に採用しない。
        base = word.lower().strip().strip("-")
        links = [x for x in links if x.lower().strip().strip("-") != base]
        if "a" in links and "bandon" in links:
            components.clear()
            add("a", "〜へ、〜の方へ", "prefix")
            add("bandon", "支配、権限", "root")
            return
        if "a" in links and "ban" in links:
            components.clear()
            add("a", "〜へ、〜の方へ", "prefix")
            add("ban", "布告、支配", "root")
            return
        if len(links) >= 2:
            components.clear()
            add(links[-2], "語源要素", "prefix")
            add(links[-1], "語源要素", "root")
            return


def _try_plain_plus_unicode(components: list[dict], raw: str, add: AddComponent) -> None:
    # 平文の「A + B」（例: over- + joy、tentative + -ly）。テンプレが無い場合のフォールバック。
    if components:
        return
    plus_match = re.search(
        r"([^\W\d_][^\s+\|]{0,31})\s*\+"
        + _ETY_AFTER_PLUS
        + "("
        + _ETY_PLUS_RIGHT_OPERAND
        + ")",
        raw,
        flags=re.UNICODE,
    )
    if plus_match:
        left = clean_token(plus_match.group(1))
        right = clean_token(plus_match.group(2))
        if _accept_plain_plus_pair(left, right):
            components.clear()
            add(left, "接頭要素", "prefix")
            add(right, "語根要素", "root")


def _try_plain_plus_on_compacted(
    components: list[dict],
    raw: str,
    compact_fn: Callable[[str, int], str],
    add: AddComponent,
) -> None:
    # 上と同じ「+」分解だが、テンプレ展開後の平文（_compact_wikitext）に対しても試す。
    if components:
        return
    compact = compact_fn(raw, max_chars=1200)
    plus_match_compact = re.search(
        r"([^\W\d_][^\s+\|]{0,31})\s*\+"
        + _ETY_AFTER_PLUS
        + "("
        + _ETY_PLUS_RIGHT_OPERAND
        + ")",
        compact,
        flags=re.UNICODE,
    )
    if plus_match_compact:
        left = clean_token(plus_match_compact.group(1))
        right = clean_token(plus_match_compact.group(2))
        if _accept_plain_plus_pair(left, right, compact_mode=True):
            components.clear()
            add(left, "接頭要素", "prefix")
            add(right, "語根要素", "root")


def _try_der_plain_third_arg(
    components: list[dict], raw: str, word: str, add: AddComponent
) -> None:
    # まだ成分が空のとき、{{uder|en|la|remūnerātiō}} / {{lbor|en|la|...}} / {{bor+|...}} など
    # 第4パイプ位置が単一見出し語になるテンプレの先頭1件だけを root にする。
    if components:
        return
    plain_der = re.search(
        r"\{\{(?:der|inh|bor|uder|lbor|ubor)\+?\|[^|}]+\|[^|}]+\|([^|}\s]+)",
        raw,
        flags=re.IGNORECASE,
    )
    if plain_der:
        term = clean_token(plain_der.group(1))
        if term and term.lower().strip("-") != word.lower().strip():
            components.clear()
            add(term, "語源要素", "root")


def _try_ascii_plus_fallback(components: list[dict], raw: str, add: AddComponent) -> None:
    # ASCII 限定の短い「word + word / word + -ly」用。左は最大6文字（接頭辞風）のため長い語幹は上の UNICODE 側に任せる。
    if components:
        return
    plus_match = re.search(
        r"\b([A-Za-z]{1,6})\s*\+"
        + _ETY_AFTER_PLUS
        + r"([A-Za-z]{2,16}|[-–—\u2010][A-Za-z]{1,15})\b",
        raw,
    )
    if plus_match:
        left = clean_token(plus_match.group(1))
        right = clean_token(plus_match.group(2))
        if _accept_plain_plus_pair(left, right):
            components.clear()
            add(left, "接頭要素", "prefix")
            add(right, "語根要素", "root")


def _maybe_fill_from_candidate_terms(
    components: list[dict],
    raw: str,
    word: str,
    add: AddComponent,
) -> None:
    # 成分が0〜1件のときのフォールバック。{{root|...|*pie}}・{{der|inh|bor|uder|lbor|ubor|...|term}}・{{m|lang|lemma}} から
    # 語を列挙し、対象語自身・メタ語を除いてすべて語源要素として並べる（件数上限なし）。
    candidate_terms: list[str] = []
    if len(components) > 1:
        return
    for m in re.finditer(r"\{\{root\|[^|}]+\|[^|}]+\|([^|}]+)", raw, flags=re.IGNORECASE):
        candidate_terms.append(clean_token(m.group(1)))
    for m in re.finditer(
        r"\{\{(?:der|inh|bor|uder|lbor|ubor)\+?\|[^|}]+\|[^|}]+\|([^|}]+)",
        raw,
        flags=re.IGNORECASE,
    ):
        candidate_terms.append(clean_token(m.group(1)))
    for m in re.finditer(r"\{\{m\|([^|}]+)\|([^|}]+)(?:\|([^|}]+))?", raw, flags=re.IGNORECASE):
        lang = (m.group(1) or "").strip().lower()
        if lang not in _ETYMON_M_LANG_ALLOWLIST:
            continue
        first = clean_token(m.group(2))
        candidate_terms.append(first)
    for m in re.finditer(r"\{\{(?:doublet|dbt)\|en\|([^|}]+)", raw, flags=re.IGNORECASE):
        candidate_terms.append(clean_token(m.group(1)))

    base = word.lower().strip()
    unique_terms: list[str] = []
    for t in candidate_terms:
        if not t:
            continue
        normalized = t.lower().strip("-")
        if normalized == base:
            continue
        if normalized in ETYMOLOGY_META_LEMMA_BLOCKLIST or normalized in ETYMOLOGY_PLUS_STOPWORDS:
            continue
        if t not in unique_terms:
            unique_terms.append(t)

    if not unique_terms:
        return
    existing_texts = {str(c.get("text", "")).lower().strip("-") for c in components}
    # 語源上重要語（例: astounen）の取りこぼし防止のため件数上限は設けない。既存成分を保持しつつ追記する。
    for idx, term in enumerate(unique_terms):
        normalized_term = term.lower().strip("-")
        if normalized_term in existing_texts:
            continue
        if term.startswith("*"):
            add(term, "印欧祖語などの祖語形", "proto_root")
        elif not components and idx == 0:
            add(term, "語源要素", "prefix")
        else:
            add(term, "語源要素", "root")
        existing_texts.add(normalized_term)


def extract_etymology_components(
    raw_etymology: str,
    word: str,
    compact_fn: Callable[[str, int], str],
) -> list[dict]:
    # 呼び出し順：suf → surf（+修飾子除去）→ af → pre → compound → confix → back-formation → deverbal
    # → derリンク特例
    # → 平文+（原文/compact）→ der系単一第4引数 → ASCII+ → 候補語列。
    # 引用注(ref)に含まれる URL・本文は語源抽出ノイズになるため、先に除去する。
    raw_etymology = re.sub(r"<ref[^>]*>.*?</ref>", "", raw_etymology, flags=re.IGNORECASE | re.DOTALL)
    raw_etymology = re.sub(r"<ref[^>]*/\s*>", "", raw_etymology, flags=re.IGNORECASE)

    components: list[dict] = []

    def add_component(text: str, meaning: str, comp_type: str) -> None:
        token = clean_token(text)
        if not token:
            return
        # sanitize：パイプ残骸・品詞ラベル単体などを弾く
        sanitized = sanitize_etymology_component_token(token)
        if not sanitized:
            return
        comp = {"text": sanitized, "meaning": meaning, "type": comp_type}
        if comp not in components:
            components.append(comp)

    _extract_suf_templates(raw_etymology, add_component)
    _extract_surf_templates(raw_etymology, add_component)
    _extract_af_templates(raw_etymology, add_component)
    _extract_pre_templates(raw_etymology, add_component)
    _extract_compound_templates(raw_etymology, add_component)
    _extract_confix_templates(raw_etymology, add_component)
    _extract_backformation_templates(raw_etymology, add_component)
    _extract_deverbal_templates(raw_etymology, add_component)
    if not components:
        _extract_etymon_templates(raw_etymology, word, add_component)
    _try_der_linked_morphemes(components, raw_etymology, word, add_component)
    _try_plain_plus_unicode(components, raw_etymology, add_component)
    _try_plain_plus_on_compacted(components, raw_etymology, compact_fn, add_component)
    _try_der_plain_third_arg(components, raw_etymology, word, add_component)
    _try_ascii_plus_fallback(components, raw_etymology, add_component)
    _maybe_fill_from_candidate_terms(components, raw_etymology, word, add_component)
    if not components:
        same_word_origin = detect_same_word_foreign_origin(raw_etymology, word)
        if same_word_origin:
            lang_code, term = same_word_origin
            meaning = _ETYMON_LANG_ORIGIN_LABELS.get(lang_code, f"{lang_code}由来")
            add_component(term, meaning, "root")
    return components
