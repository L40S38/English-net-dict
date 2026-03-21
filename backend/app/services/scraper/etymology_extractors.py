from __future__ import annotations

import re
from typing import Callable

from app.utils.etymology_component_sanitize import sanitize_etymology_component_token
from app.utils.etymology_components import (
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

AddComponent = Callable[[str, str, str], None]


def clean_token(value: str) -> str:
    # テンプレ引数に付くページ内アンカーを落とす（例: pactus#Noun → pactus、ramp#Verb → ramp）。
    token = value.strip()
    token = re.sub(r"^[\s\(\[\{'\"]+", "", token)
    if "#" in token:
        token = token.split("#", 1)[0].rstrip()
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
        args = _split_pipe_args_skip_lang(match.group(1))
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
        while args and args[0].startswith("+"):
            args = args[1:]
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
        for text in morpheme_parts:
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
        term = normalize_template_arg(args[0])
        if not term or "=" in term:
            continue
        if not looks_like_morpheme(term.lstrip("-").rstrip("-")):
            continue
        add(term, "語根要素", "root")


def _extract_af_templates(raw: str, add: AddComponent) -> None:
    # {{af|en|stem|-al}} / {{affix|...}} / {{prefix|...}}：接辞分解。第1要素を prefix、以降を root として追加。
    for match in re.finditer(
        r"\{\{(?:af|affix|prefix)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        args = _split_pipe_args_skip_lang(match.group(1))
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


def _try_der_linked_morphemes(components: list[dict], raw: str, add: AddComponent) -> None:
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


def _try_der_plain_third_arg(components: list[dict], raw: str, add: AddComponent) -> None:
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
        if term:
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
    for m in re.finditer(r"\{\{m\|[^|}]+\|([^|}]+)(?:\|([^|}]+))?", raw, flags=re.IGNORECASE):
        first = clean_token(m.group(1))
        candidate_terms.append(first)

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
    components.clear()
    # 語源上重要語（例: astounen）の取りこぼし防止のため件数上限は設けない。ノイズは sanitize で抑制する。
    for idx, term in enumerate(unique_terms):
        if term.startswith("*"):
            add(term, "印欧祖語などの祖語形", "proto_root")
        elif idx == 0:
            add(term, "語源要素", "prefix")
        else:
            add(term, "語源要素", "root")


def extract_etymology_components(
    raw_etymology: str,
    word: str,
    compact_fn: Callable[[str, int], str],
) -> list[dict]:
    # 呼び出し順：suf → surf（+修飾子除去）→ af → pre → compound → confix → back-formation → derリンク特例
    # → 平文+（原文/compact）→ der系単一第4引数 → ASCII+ → 候補語列。
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
    _try_der_linked_morphemes(components, raw_etymology, add_component)
    _try_plain_plus_unicode(components, raw_etymology, add_component)
    _try_plain_plus_on_compacted(components, raw_etymology, compact_fn, add_component)
    _try_der_plain_third_arg(components, raw_etymology, add_component)
    _try_ascii_plus_fallback(components, raw_etymology, add_component)
    _maybe_fill_from_candidate_terms(components, raw_etymology, word, add_component)
    return components
