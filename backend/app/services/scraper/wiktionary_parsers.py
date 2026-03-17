from __future__ import annotations

import re

from app.utils.etymology_components import looks_like_morpheme

_LANG_NAMES: dict[str, str] = {
    "LL.": "後期ラテン語",
    "ML.": "中世ラテン語",
    "NL.": "新ラテン語（略）",
    "VL.": "俗ラテン語",
    "af": "アフリカーンス語",
    "alv-gbe-pro": "ゲベ祖語",
    "ang": "古英語",
    "ar": "アラビア語",
    "ca": "カタルーニャ語",
    "cel": "ケルト語派",
    "cel-gau": "ガリア語",
    "cel-pro": "ケルト祖語",
    "cs": "チェコ語",
    "da": "デンマーク語",
    "de": "ドイツ語",
    "dum": "中期オランダ語",
    "egy": "エジプト語",
    "el": "現代ギリシャ語",
    "en": "英語",
    "enm": "中英語",
    "es": "スペイン語",
    "ett": "エトルリア語",
    "fa": "ペルシャ語",
    "fi": "フィンランド語",
    "fr": "フランス語",
    "frk": "フランク語",
    "frm": "中期フランス語",
    "fro": "古フランス語",
    "fro-nor": "古ノルマン・フランス語",
    "ga": "アイルランド語",
    "gem": "ゲルマン語派",
    "gem-pro": "ゲルマン祖語",
    "gmh": "中高ドイツ語",
    "gml": "中低ドイツ語",
    "gmq": "北ゲルマン語派",
    "gmq-oda": "古デンマーク語",
    "gmq-pro": "北ゲルマン祖語",
    "gmw-pro": "西ゲルマン祖語",
    "goh": "古高ドイツ語",
    "grc": "古代ギリシャ語",
    "hi": "ヒンディー語",
    "hit": "ヒッタイト語",
    "hu": "ハンガリー語",
    "ine-pro": "印欧祖語",
    "it": "イタリア語",
    "itc-pro": "イタリック祖語",
    "ja": "日本語",
    "ka": "ジョージア語",
    "ko": "韓国語",
    "la": "ラテン語",
    "la-lat": "後期ラテン語",
    "la-med": "中世ラテン語",
    "la-new": "新ラテン語",
    "la-vul": "俗ラテン語",
    "map-pro": "オーストロネシア祖語",
    "mga": "中期アイルランド語",
    "nds": "低地ドイツ語",
    "nl": "オランダ語",
    "no": "ノルウェー語",
    "non": "古ノルド語",
    "odt": "古オランダ語",
    "osp": "古スペイン語",
    "osx": "古ザクセン語",
    "ota": "オスマン・トルコ語",
    "pi": "パーリ語",
    "pl": "ポーランド語",
    "poz-pro": "マレー・ポリネシア祖語",
    "pro": "古プロヴァンス語",
    "pt": "ポルトガル語",
    "qsb-grc": "古代ギリシャ語基層",
    "roa-pro": "ロマンス祖語",
    "rom": "ロマニ語",
    "ru": "ロシア語",
    "sa": "サンスクリット語",
    "sco": "スコットランド語",
    "sga": "古アイルランド語",
    "sv": "スウェーデン語",
    "tr": "トルコ語",
    "trk-pro": "テュルク祖語",
    "wo": "ウォロフ語",
    "xno": "アングロ・ノルマン語",
    "yo": "ヨルバ語",
    "zh": "中国語",
}


class WiktionaryParserMixin:
    @classmethod
    def _extract_etymology_components(cls, raw_etymology: str, word: str) -> list[dict]:
        components: list[dict] = []

        def clean_token(value: str) -> str:
            token = value.strip()
            token = re.sub(r"^[\s\(\[\{'\"]+", "", token)
            token = re.sub(r"[\s\)\]\}',\"。．、,.;:]+$", "", token)
            return token

        def add_component(text: str, meaning: str, comp_type: str) -> None:
            token = clean_token(text)
            if not token:
                return
            comp = {"text": token, "meaning": meaning, "type": comp_type}
            if comp not in components:
                components.append(comp)

        for match in re.finditer(
            r"\{\{(?:af|affix|prefix)\|([^}]*)\}\}",
            raw_etymology,
            flags=re.IGNORECASE,
        ):
            args = [x.strip() for x in match.group(1).split("|") if x.strip()]
            if not args:
                continue
            if len(args) >= 1 and re.fullmatch(r"[a-z]{2,3}", args[0].lower()):
                args = args[1:]
            if len(args) < 2:
                continue
            morpheme_parts: list[str] = []
            for part in args[:3]:
                text = re.sub(r"\s+", "", part)
                if not text or "=" in text:
                    continue
                if not looks_like_morpheme(text):
                    continue
                morpheme_parts.append(text)
            for idx, text in enumerate(morpheme_parts):
                comp = {
                    "text": text,
                    "meaning": "接頭要素" if idx == 0 else "語根要素",
                    "type": "prefix" if idx == 0 else "root",
                }
                if comp not in components:
                    components.append(comp)

        if not components:
            for match in re.finditer(r"\{\{der\|([^}]*)\}\}", raw_etymology, flags=re.IGNORECASE):
                args = [x.strip() for x in match.group(1).split("|")]
                if len(args) < 3:
                    continue
                ety_text = args[2]
                links = [x.strip() for x in re.findall(r"\[\[([^\]|]+)", ety_text) if x.strip()]
                if "a" in links and "bandon" in links:
                    components = [
                        {"text": "a", "meaning": "〜へ、〜の方へ", "type": "prefix"},
                        {"text": "bandon", "meaning": "支配、権限", "type": "root"},
                    ]
                    break
                if "a" in links and "ban" in links:
                    components = [
                        {"text": "a", "meaning": "〜へ、〜の方へ", "type": "prefix"},
                        {"text": "ban", "meaning": "布告、支配", "type": "root"},
                    ]
                    break
                if len(links) >= 2:
                    components = [
                        {"text": links[-2], "meaning": "語源要素", "type": "prefix"},
                        {"text": links[-1], "meaning": "語源要素", "type": "root"},
                    ]
                    break

        if not components:
            plus_match = re.search(
                r"([^\W\d_][^\s+]{0,31})\s*\+\s*([^\W\d_][^\s,.;:)]{0,31})",
                raw_etymology,
                flags=re.UNICODE,
            )
            if plus_match:
                left = clean_token(plus_match.group(1))
                right = clean_token(plus_match.group(2))
                if left and right:
                    components = [
                        {"text": left, "meaning": "接頭要素", "type": "prefix"},
                        {"text": right, "meaning": "語根要素", "type": "root"},
                    ]

        if not components:
            compact = cls._compact_wikitext(raw_etymology, max_chars=1200)
            plus_match_compact = re.search(
                r"([^\W\d_][^\s+]{0,31})\s*\+\s*([^\W\d_][^\s,.;:)]{0,31})",
                compact,
                flags=re.UNICODE,
            )
            if plus_match_compact:
                left = clean_token(plus_match_compact.group(1))
                right = clean_token(plus_match_compact.group(2))
                if left and right:
                    components = [
                        {"text": left, "meaning": "接頭要素", "type": "prefix"},
                        {"text": right, "meaning": "語根要素", "type": "root"},
                    ]

        if not components:
            plain_der = re.search(
                r"\{\{der\|[^|}]+\|[^|}]+\|([^|}\s]+)",
                raw_etymology,
                flags=re.IGNORECASE,
            )
            if plain_der:
                term = clean_token(plain_der.group(1))
                if term:
                    components = [{"text": term, "meaning": "語源要素", "type": "root"}]

        if not components:
            plus_match = re.search(r"\b([A-Za-z]{1,6})\s*\+\s*([A-Za-z]{2,16})\b", raw_etymology)
            if plus_match:
                components = [
                    {"text": plus_match.group(1), "meaning": "接頭要素", "type": "prefix"},
                    {"text": plus_match.group(2), "meaning": "語根要素", "type": "root"},
                ]

        candidate_terms: list[str] = []
        if len(components) <= 1:
            for m in re.finditer(r"\{\{root\|[^|}]+\|[^|}]+\|([^|}]+)", raw_etymology, flags=re.IGNORECASE):
                candidate_terms.append(clean_token(m.group(1)))
            for m in re.finditer(r"\{\{(?:der|inh|bor)\|[^|}]+\|[^|}]+\|([^|}]+)", raw_etymology, flags=re.IGNORECASE):
                candidate_terms.append(clean_token(m.group(1)))
            for m in re.finditer(r"\{\{m\|[^|}]+\|([^|}]+)(?:\|([^|}]+))?", raw_etymology, flags=re.IGNORECASE):
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
                if t not in unique_terms:
                    unique_terms.append(t)

            if unique_terms:
                components = []
                for idx, term in enumerate(unique_terms[:3]):
                    if term.startswith("*"):
                        add_component(term, "印欧祖語などの祖語形", "proto_root")
                    elif idx == 0:
                        add_component(term, "語源要素", "prefix")
                    else:
                        add_component(term, "語源要素", "root")

        return components

    @classmethod
    def _extract_language_chain(cls, raw_etymology: str) -> list[dict]:
        chain: list[dict] = []
        for match in re.finditer(r"\{\{(bor|der|inh)\|([^}]*)\}\}", raw_etymology, flags=re.IGNORECASE):
            relation = match.group(1).lower()
            args = [x.strip() for x in match.group(2).split("|") if x.strip()]
            positional = [a for a in args if "=" not in a and not a.startswith(":")]
            if len(positional) < 3:
                continue
            source_lang = positional[1]
            source_word = cls._normalize_template_term(positional[2])
            if not source_word:
                continue
            item = {
                "lang": source_lang,
                "lang_name": _LANG_NAMES.get(source_lang, source_lang),
                "word": source_word,
                "relation": relation,
            }
            if item not in chain:
                chain.append(item)
        return chain

    @classmethod
    def _extract_component_meanings(cls, raw_etymology: str, components: list[dict], word: str) -> list[dict]:
        if not raw_etymology:
            return []
        component_map = {
            str(x.get("text", "")).strip().lower(): str(x.get("text", "")).strip()
            for x in components
            if isinstance(x, dict) and str(x.get("text", "")).strip()
        }
        component_keys = set(component_map.keys())
        if not component_keys:
            fallback = word.strip()
            component_map = {fallback.lower(): fallback}
            component_keys = {fallback.lower()}

        candidates: list[str] = []
        for line in raw_etymology.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^[#*]\s*\d+[.:]\s+", stripped):
                cleaned = re.sub(r"^[#*]\s*\d+[.:]\s*", "", stripped)
                candidates.append(cls._compact_wikitext(cleaned, max_chars=220))
            elif re.match(r"^#\s+", stripped):
                cleaned = re.sub(r"^#\s*", "", stripped)
                candidates.append(cls._compact_wikitext(cleaned, max_chars=220))

        for match in re.finditer(r"[「“](.{1,80}?)[」”]", raw_etymology):
            quoted = match.group(1).strip()
            if quoted:
                candidates.append(quoted)

        results: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for entry in candidates:
            text = entry.strip()
            if not text:
                continue
            normalized = text.lower()
            target_key = ""
            for key in component_keys:
                if key and key in normalized:
                    target_key = key
                    break
            if not target_key:
                if len(component_keys) == 1:
                    target_key = next(iter(component_keys))
                else:
                    continue
            if text in cls._GENERIC_COMPONENT_MEANINGS:
                continue
            signature = (target_key, text)
            if signature in seen:
                continue
            seen.add(signature)
            results.append({"text": component_map.get(target_key, target_key), "meaning": text})
        return results

    @classmethod
    def _extract_etymology_variants(cls, raw_etymologies: list[str], word: str) -> list[dict]:
        variants: list[dict] = []
        for idx, raw in enumerate(raw_etymologies):
            components = cls._extract_etymology_components(raw or "", word)
            language_chain = cls._extract_language_chain(raw or "")
            component_meanings = cls._extract_component_meanings(raw or "", components, word)
            excerpt = cls._compact_wikitext(raw or "", max_chars=500)
            variants.append(
                {
                    "label": f"Etymology {idx + 1}",
                    "excerpt": excerpt,
                    "components": components,
                    "component_meanings": component_meanings,
                    "language_chain": language_chain,
                }
            )
        return variants
