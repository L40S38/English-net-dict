from __future__ import annotations

import re

from core.services.scraper.etymology_extractors import (
    _ETY_AFTER_PLUS,
    _ETY_PLUS_RIGHT_OPERAND,
    detect_same_word_foreign_origin,
    extract_etymology_components,
)

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

_LANG_CODE_TO_WIKI_HEADING: dict[str, str] = {
    "la": "Latin",
    "la-lat": "Latin",
    "la-med": "Latin",
    "la-vul": "Latin",
    "la-new": "Latin",
    "fr": "French",
    "fro": "Old French",
    "frm": "Middle French",
    "xno": "Anglo-Norman",
    "enm": "Middle English",
    "ang": "Old English",
    "grc": "Ancient Greek",
    "non": "Old Norse",
    "de": "German",
    "nl": "Dutch",
    "it": "Italian",
    "es": "Spanish",
    "pt": "Portuguese",
    "ar": "Arabic",
}


class WiktionaryParserMixin:
    @classmethod
    def _extract_etymology_components(cls, raw_etymology: str, word: str) -> list[dict]:
        return extract_etymology_components(raw_etymology, word, cls._compact_wikitext)

    @classmethod
    def _extract_language_chain(cls, raw_etymology: str) -> list[dict]:
        chain: list[dict] = []
        for match in re.finditer(
            r"\{\{((?:bor|der|inh)\+?)\|([^}]*)\}\}",
            raw_etymology,
            flags=re.IGNORECASE,
        ):
            relation = match.group(1).lower().rstrip("+")
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

    @classmethod
    def _extract_etymology_blocks_from_language_section(cls, language_body: str) -> list[str]:
        heading_matches = list(
            re.finditer(r"^(={3,})\s*([^=\n]+?)\s*=+\s*$", language_body, flags=re.MULTILINE)
        )
        if not heading_matches:
            return []

        blocks: list[str] = []
        for idx, heading in enumerate(heading_matches):
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if not cls._is_etymology_section_heading(title):
                continue
            block_end = len(language_body)
            for nxt in heading_matches[idx + 1 :]:
                if len(nxt.group(1)) <= level:
                    block_end = nxt.start()
                    break
            body = language_body[heading.end() : block_end].strip()
            if body and body not in blocks:
                blocks.append(body)
        return blocks

    @classmethod
    def _follow_same_word_etymology(
        cls,
        full_wikitext: str,
        word: str,
        etymology_bodies: list[str],
        etymology_components: list[dict],
    ) -> list[dict]:
        if not etymology_bodies:
            return etymology_components

        merged = list(etymology_components or [])
        queue: list[tuple[str, str]] = []
        seen_queue: set[tuple[str, str]] = set()
        visited: set[tuple[str, str]] = set()

        for raw in etymology_bodies:
            hit = detect_same_word_foreign_origin(raw, word)
            if not hit:
                continue
            lang_code, term = hit
            normalized = term.lower().strip().strip("-")
            seed = (lang_code.lower(), normalized)
            if seed in seen_queue:
                continue
            seen_queue.add(seed)
            queue.append((lang_code.lower(), term))

            lang_name = _LANG_NAMES.get(lang_code.lower(), lang_code)
            origin = [{"text": term, "meaning": f"{lang_name}由来", "type": "root"}]
            merged = cls._merge_unique_dict_items_by_text(merged, origin)

        while queue:
            lang_code, term = queue.pop(0)
            normalized = term.lower().strip().strip("-")
            marker = (lang_code, normalized)
            if marker in visited:
                continue
            visited.add(marker)

            heading = _LANG_CODE_TO_WIKI_HEADING.get(lang_code)
            if not heading:
                continue
            language_body = cls._extract_language_section_raw(full_wikitext, heading)
            if not language_body:
                continue
            etymology_blocks = cls._extract_etymology_blocks_from_language_section(language_body)
            if not etymology_blocks:
                continue

            for block in etymology_blocks:
                comps = extract_etymology_components(block, term, cls._compact_wikitext)
                if comps:
                    merged = cls._merge_unique_dict_items_by_text(merged, comps)
                next_hit = detect_same_word_foreign_origin(block, term)
                if not next_hit:
                    continue
                next_lang, next_term = next_hit
                next_normalized = next_term.lower().strip().strip("-")
                next_key = (next_lang.lower(), next_normalized)
                if next_key in visited or next_key in seen_queue:
                    continue
                seen_queue.add(next_key)
                queue.append((next_lang.lower(), next_term))
                next_lang_name = _LANG_NAMES.get(next_lang.lower(), next_lang)
                origin = [{"text": next_term, "meaning": f"{next_lang_name}由来", "type": "root"}]
                merged = cls._merge_unique_dict_items_by_text(merged, origin)

        return merged
