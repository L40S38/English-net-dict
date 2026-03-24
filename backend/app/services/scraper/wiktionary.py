from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config import DATA_DIR
from app.services.scraper.base import BaseScraper
from app.services.scraper.wiktionary_parsers import WiktionaryParserMixin

logger = logging.getLogger(__name__)

_SCRAPE_CACHE_DIR = DATA_DIR / "scrape_cache"


def _retry_after_seconds(response: httpx.Response, fallback: float) -> float:
    """429/503 応答の Retry-After（秒数または HTTP-date）を解釈する。"""
    ra = (response.headers.get("Retry-After") or "").strip()
    if not ra:
        return max(fallback, 2.0)
    if ra.isdigit():
        return max(float(ra), fallback, 2.0)
    try:
        dt = parsedate_to_datetime(ra)
        wait = dt.timestamp() - time.time()
        return max(wait, fallback, 2.0)
    except (TypeError, ValueError, OSError):
        return max(fallback, 2.0)

_LANG_NAMES: dict[str, str] = {
    "en": "英語", "enm": "中英語", "ang": "古英語",
    "fr": "フランス語", "frm": "中期フランス語", "fro": "古フランス語",
    "la": "ラテン語", "ML.": "中世ラテン語", "VL.": "俗ラテン語", "LL.": "後期ラテン語",
    "grc": "古代ギリシャ語", "el": "現代ギリシャ語",
    "gem-pro": "ゲルマン祖語", "gmw-pro": "西ゲルマン祖語",
    "ine-pro": "印欧祖語",
    "ar": "アラビア語", "fa": "ペルシャ語",
    "es": "スペイン語", "it": "イタリア語", "pt": "ポルトガル語",
    "de": "ドイツ語", "nl": "オランダ語", "nds": "低地ドイツ語",
    "non": "古ノルド語", "da": "デンマーク語", "sv": "スウェーデン語", "no": "ノルウェー語",
    "ja": "日本語", "zh": "中国語", "ko": "韓国語",
    "gml": "中低ドイツ語", "gmh": "中高ドイツ語",
    "osp": "古スペイン語",
    "sa": "サンスクリット語", "pi": "パーリ語",
    "hit": "ヒッタイト語",
    "ru": "ロシア語", "pl": "ポーランド語", "cs": "チェコ語",
    "tr": "トルコ語", "fi": "フィンランド語", "hu": "ハンガリー語",
}

_FORM_NOISE_TOKENS = {"of", "from", "for", "to", "by", "and", "or", "the", "a", "an"}


class WiktionaryScraper(WiktionaryParserMixin, BaseScraper):
    source_name = "wiktionary"
    _FETCH_MAX_RETRIES = 20
    _FETCH_BASE_DELAY_429 = 5.0
    _FETCH_BASE_DELAY_OTHER = 3.0

    _GENERIC_COMPONENT_MEANINGS = {"語源要素", "語根要素", "接頭要素"}

    def __init__(self, *, cache_dir: Path | None = None, use_cache: bool = True) -> None:
        self._cache_dir = cache_dir or _SCRAPE_CACHE_DIR
        self._use_cache = use_cache
        self._memory_cache: dict[str, dict] = {}
        if self._use_cache:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _cache_key(word: str) -> str:
        return word.strip().lower()

    def _cache_path(self, word: str) -> Path:
        key = self._cache_key(word)
        safe = key.replace("/", "__SLASH__").replace("\\", "__BSLASH__")
        return self._cache_dir / f"{safe}.json"

    def _load_cache(self, word: str) -> dict | None:
        key = self._cache_key(word)
        if key in self._memory_cache:
            return self._memory_cache[key]
        if not self._use_cache:
            return None
        path = self._cache_path(word)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._memory_cache[key] = data
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def _save_cache(self, word: str, data: dict) -> None:
        key = self._cache_key(word)
        self._memory_cache[key] = data
        if not self._use_cache:
            return
        try:
            path = self._cache_path(word)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
    _POS_SECTION_MAP: dict[str, str] = {
        "noun": "noun",
        "proper noun": "noun",
        "verb": "verb",
        "adjective": "adjective",
        "adverb": "adverb",
        "pronoun": "pronoun",
        "preposition": "preposition",
        "conjunction": "conjunction",
        "interjection": "interjection",
        "determiner": "determiner",
        "article": "determiner",
        "numeral": "noun",
        "participle": "adjective",
        "phrase": "phrase",
    }

    @staticmethod
    def _normalize_template_term(raw: str) -> str:
        value = raw.strip()
        if ":" in value:
            value = value.split(":", 1)[1]
        value = re.sub(r"<[^>]+>", "", value)
        return value.strip()

    @staticmethod
    def _template_to_text(inner: str) -> str:
        parts = [p.strip() for p in inner.split("|")]
        if not parts:
            return " "
        # der+/bor+/inh+ などは抽出上 der/bor/inh と同等に扱う。
        name = parts[0].lower().rstrip("+")
        args = parts[1:]
        positional = [a for a in args if a and "=" not in a and not a.startswith(":")]
        if not positional:
            return " "

        if name in {"af", "affix", "prefix", "pre"} and len(positional) >= 2:
            core = positional[1:]
            if len(core) >= 2:
                return " + ".join(core[:3])
            return positional[-1]
        # {{surf|en|re-|turn}} / {{surface analysis|en|full-|fill}} を平文の A + B に展開する。
        if name in {"surf", "surface analysis"} and len(positional) >= 2:
            core = positional[1:]
            if len(core) >= 2:
                return " + ".join(core[:3])
            return positional[-1]
        # {{suf|en|stem|ly|id2=...}}（例: tentatively の語源）。_template_to_text が未対応だとテンプレが空白に
        # 置換され「From  .」→ 句読点前の空白潰しで etymology 抜粋が「From.」だけになるため、平文「stem + -ly」に展開する。
        if name in {"suf", "suffix"} and len(positional) >= 3:
            stem = WiktionaryScraper._normalize_template_term(positional[1])
            suf = WiktionaryScraper._normalize_template_term(positional[2])
            if stem and suf:
                affix = suf if suf.startswith("-") else f"-{suf}"
                return f"{stem} + {affix}"
            return stem or suf or " "
        if name in {"bor", "der", "inh", "cog"}:
            lang_label = _LANG_NAMES.get(positional[1], "") if len(positional) >= 2 else ""
            term = WiktionaryScraper._normalize_template_term(positional[2]) if len(positional) >= 3 else ""
            if not term:
                term = WiktionaryScraper._normalize_template_term(positional[-1])
            if lang_label and term:
                return f"{lang_label} {term}"
            return term or " "
        if name in {"m", "l", "mention", "link"}:
            term = WiktionaryScraper._normalize_template_term(positional[1]) if len(positional) >= 2 else WiktionaryScraper._normalize_template_term(positional[-1])
            return term or " "
        if name == "etyl":
            lang_code = positional[0] if positional else ""
            lang_name = _LANG_NAMES.get(lang_code, lang_code)
            return lang_name
        if name in {"root", "etymon", "doublet"}:
            return " "
        return " "

    @staticmethod
    def _compact_wikitext(text: str, max_chars: int = 1400) -> str:
        compact = text
        for _ in range(3):
            if "{{" not in compact:
                break
            compact = re.sub(
                r"\{\{([^{}]*)\}\}",
                lambda m: f" {WiktionaryScraper._template_to_text(m.group(1))} ",
                compact,
            )
        compact = re.sub(r"\[\[([^|\]]*\|)?([^\]]+)\]\]", r"\2", compact)
        compact = re.sub(r"<[^>]+>", " ", compact)
        compact = re.sub(r"\s+([,.;:])", r"\1", compact)
        compact = re.sub(r"\s+", " ", compact).strip()
        return compact[:max_chars]

    @staticmethod
    def _extract_section_body_raw(
        wikitext: str, section_title: str, sections: list[dict] | None = None,
    ) -> str | None:
        heading = re.search(
            rf"^=+\s*{re.escape(section_title)}\s*=+\s*$", wikitext, flags=re.MULTILINE,
        )
        if heading:
            body = wikitext[heading.end() :]
            next_heading = re.search(r"^=+\s*[^=\n].*?=+\s*$", body, flags=re.MULTILINE)
            if next_heading:
                body = body[: next_heading.start()]
            return body.strip() or None

        if sections:
            target_sec = None
            for sec in sections:
                if str(sec.get("line", "")).strip().lower() == section_title.lower():
                    target_sec = sec
                    break
            if target_sec is not None:
                sec_index = int(target_sec.get("index", "0"))
                all_headings = list(
                    re.finditer(r"^(=+)\s*[^\n]*?\s*=+\s*$", wikitext, flags=re.MULTILINE)
                )
                if 1 <= sec_index <= len(all_headings):
                    match = all_headings[sec_index - 1]
                    body = wikitext[match.end() :]
                    next_h = re.search(r"^=+\s*[^=\n].*?=+\s*$", body, flags=re.MULTILINE)
                    if next_h:
                        body = body[: next_h.start()]
                    return body.strip() or None

        return None

    @staticmethod
    def _extract_section_body(
        wikitext: str, section_title: str, max_chars: int = 1800,
        sections: list[dict] | None = None,
    ) -> str | None:
        raw = WiktionaryScraper._extract_section_body_raw(wikitext, section_title, sections=sections)
        if not raw:
            return None
        excerpt = WiktionaryScraper._compact_wikitext(raw, max_chars=max_chars)
        return excerpt or None

    @staticmethod
    def _find_section_title(sections: list[dict], *names: str) -> str | None:
        lowered = {x.lower() for x in names}
        for sec in sections:
            line = str(sec.get("line", "")).strip()
            if line.lower() in lowered:
                return line
        return None

    @staticmethod
    def _find_section_titles_prefix(sections: list[dict], *prefixes: str) -> list[str]:
        lowered = tuple(x.lower() for x in prefixes)
        titles: list[str] = []
        for sec in sections:
            line = str(sec.get("line", "")).strip()
            line_lower = line.lower()
            if line and line_lower.startswith(lowered):
                titles.append(line)
        return titles

    # en.wiktionary: ===Etymology=== / ===Etymology 1===（「Etymological」などは除外）
    _EN_SECTION_ETYMOLOGY_HEADING = re.compile(r"^etymology(?:\s+\d+)?$", re.IGNORECASE)

    @staticmethod
    def _is_etymology_section_heading(line: str) -> bool:
        """TOC 行が語源専用セクションか（Etymology / Etymology 1、語源…、由来…）。"""
        raw = line.strip()
        if not raw:
            return False
        if WiktionaryScraper._EN_SECTION_ETYMOLOGY_HEADING.fullmatch(raw):
            return True
        # ja.wiktionary 等
        if raw.startswith("語源"):
            return True
        if raw.startswith("由来"):
            return True
        return False

    @staticmethod
    def _find_etymology_section_titles(sections: list[dict]) -> list[str]:
        return [
            str(sec.get("line", "")).strip()
            for sec in sections
            if WiktionaryScraper._is_etymology_section_heading(str(sec.get("line", "")))
        ]

    @staticmethod
    def _strip_wiki_category_links(text: str) -> str:
        """セクション末尾などに紛れ込む [[Category:...]] を除去（ページ下部カテゴリの混入対策）。"""
        if not text:
            return text
        return re.sub(r"\[\[Category:[^\]]+\]\]", "", text, flags=re.IGNORECASE).strip()

    @staticmethod
    def _merge_unique_str_items(*values: list[str]) -> list[str]:
        merged: list[str] = []
        for items in values:
            for item in items:
                text = str(item).strip()
                if text and text not in merged:
                    merged.append(text)
        return merged

    @staticmethod
    def _merge_unique_dict_items(*values: list[dict]) -> list[dict]:
        merged: list[dict] = []
        for items in values:
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item not in merged:
                    merged.append(item)
        return merged

    @staticmethod
    def _merge_unique_dict_items_by_text(*values: list[dict]) -> list[dict]:
        """dict の text キーを主キーとして先勝ちマージする。"""
        merged: list[dict] = []
        seen_texts: set[str] = set()
        for items in values:
            for item in items:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                if text:
                    if text in seen_texts:
                        continue
                    seen_texts.add(text)
                elif item in merged:
                    continue
                merged.append(item)
        return merged

    @staticmethod
    def _merge_text_ja_first(ja_text: str | None, en_text: str | None) -> str | None:
        ja_value = (ja_text or "").strip()
        en_value = (en_text or "").strip()
        if not ja_value and not en_value:
            return None
        if not ja_value:
            return en_value
        if not en_value:
            return ja_value
        if en_value in ja_value or ja_value in en_value:
            return ja_value if len(ja_value) >= len(en_value) else en_value
        return f"{ja_value}\n\n[EN補足] {en_value}"

    @staticmethod
    def _extract_section_items(
        wikitext: str, section_title: str, max_items: int = 20,
        sections: list[dict] | None = None,
    ) -> list[str]:
        body = WiktionaryScraper._extract_section_body_raw(wikitext, section_title, sections=sections)
        if not body:
            return []
        items: list[str] = []

        for col_match in re.finditer(r"\{\{(?:col|der\d?|rel\d?)\|([^}]*)\}\}", body):
            col_args = [a.strip() for a in col_match.group(1).split("|") if a.strip()]
            for arg in col_args[1:]:
                if "=" in arg or arg.startswith(":"):
                    continue
                term = WiktionaryScraper._normalize_template_term(arg)
                if term and term not in items:
                    items.append(term)
                if len(items) >= max_items:
                    return items

        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line or not line.startswith(("*", "#")):
                continue
            cleaned = re.sub(r"^[*#:\s]+", "", line).strip()
            cleaned = WiktionaryScraper._compact_wikitext(cleaned, max_chars=160)
            cleaned = re.sub(r"\s*;\s*see\s+also\b.*", "", cleaned, flags=re.IGNORECASE).strip()
            cleaned = re.sub(r"^Thesaurus:.+$", "", cleaned).strip()
            if cleaned and cleaned not in items:
                items.append(cleaned)
            if len(items) >= max_items:
                break

        return items

    @staticmethod
    def _extract_section_glosses(
        wikitext: str, section_title: str, max_items: int = 8, sections: list[dict] | None = None,
    ) -> list[str]:
        body = WiktionaryScraper._extract_section_body_raw(wikitext, section_title, sections=sections)
        if not body:
            return []
        items: list[str] = []
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                cleaned = re.sub(r"^#+\s*", "", line).strip()
            elif re.match(r"^\d+\.\s+", line):
                cleaned = re.sub(r"^\d+\.\s*", "", line).strip()
            elif line.startswith("*"):
                cleaned = re.sub(r"^\*+\s*", "", line).strip()
            else:
                continue
            compact = WiktionaryScraper._compact_wikitext(cleaned, max_chars=180)
            if compact and compact not in items:
                items.append(compact)
            if len(items) >= max_items:
                break
        return items

    @staticmethod
    def _extract_ipa(wikitext: str, sections: list[dict]) -> str | None:
        title = WiktionaryScraper._find_section_title(sections, "pronunciation", "発音")
        if not title:
            return None
        body = WiktionaryScraper._extract_section_body_raw(wikitext, title, sections=sections)
        if not body:
            return None

        for match in re.finditer(r"\{\{IPA\|([^}]*)\}\}", body, flags=re.IGNORECASE):
            params = [p.strip() for p in match.group(1).split("|") if p.strip()]
            for part in params:
                if part.lower() in {"en", "ja", "lang=en", "lang=ja"}:
                    continue
                if part.startswith("/") and part.endswith("/"):
                    return part
            if params:
                return params[0]

        slash = re.search(r"/[^/\n]{2,64}/", body)
        if slash:
            return slash.group(0)
        return None

    @staticmethod
    def _regular_verb_forms(word: str) -> dict:
        if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
            return {
                "third_person_singular": f"{word[:-1]}ies",
                "present_participle": f"{word[:-1]}ying",
                "past_tense": f"{word[:-1]}ied",
                "past_participle": f"{word[:-1]}ied",
            }
        if word.endswith("e"):
            return {
                "third_person_singular": f"{word}s",
                "present_participle": f"{word[:-1]}ing",
                "past_tense": f"{word}d",
                "past_participle": f"{word}d",
            }
        return {
            "third_person_singular": f"{word}s",
            "present_participle": f"{word}ing",
            "past_tense": f"{word}ed",
            "past_participle": f"{word}ed",
        }

    @staticmethod
    def _regular_noun_plural(word: str) -> str:
        lower = word.lower()
        if re.search(r"(s|x|z|ch|sh)$", lower):
            return f"{word}es"
        if lower.endswith("y") and len(word) > 1 and lower[-2] not in "aeiou":
            return f"{word[:-1]}ies"
        return f"{word}s"

    @staticmethod
    def _regular_adj_forms(word: str) -> tuple[str, str]:
        lower = word.lower()
        if lower.endswith("y") and len(word) > 1 and lower[-2] not in "aeiou":
            return f"{word[:-1]}ier", f"{word[:-1]}iest"
        if lower.endswith("e"):
            return f"{word}r", f"{word}st"
        return f"{word}er", f"{word}est"

    @staticmethod
    def _extract_forms(word: str, wikitext: str) -> dict:
        forms: dict[str, str | bool] = {}

        template = re.search(r"\{\{en-verb(?P<body>\|[^}]*)?\}\}", wikitext)
        if template:
            forms.update(WiktionaryScraper._regular_verb_forms(word))
            args = [x.strip() for x in (template.group("body") or "").split("|") if x.strip()]
            if len(args) >= 4:
                forms["third_person_singular"] = args[0]
                forms["present_participle"] = args[1]
                forms["past_tense"] = args[2]
                forms["past_participle"] = args[3]
            elif len(args) >= 3:
                forms["third_person_singular"] = args[0]
                forms["present_participle"] = args[1]
                forms["past_tense"] = args[2]
                forms["past_participle"] = args[2]

        noun_template = re.search(r"\{\{en-noun(?P<body>\|[^}]*)?\}\}", wikitext)
        if noun_template:
            args = [x.strip() for x in (noun_template.group("body") or "").split("|") if x.strip()]
            if args:
                if "-" in args:
                    forms["uncountable"] = True
                if "~" in args:
                    forms["uncountable"] = True

                explicit_plural = ""
                for arg in args:
                    if arg in {"-", "~", "?", "!"} or "=" in arg:
                        continue
                    if arg == "s":
                        explicit_plural = f"{word}s"
                        break
                    if arg == "es":
                        explicit_plural = f"{word}es"
                        break
                    explicit_plural = arg
                    break
                if explicit_plural:
                    forms["plural"] = explicit_plural
            else:
                forms["plural"] = WiktionaryScraper._regular_noun_plural(word)

        adj_template = re.search(r"\{\{en-adj(?P<body>\|[^}]*)?\}\}", wikitext)
        if adj_template:
            args = [x.strip() for x in (adj_template.group("body") or "").split("|") if x.strip()]
            if len(args) >= 2 and args[0] not in {"-", "?"}:
                forms["comparative"] = args[0]
                forms["superlative"] = args[1]
            elif len(args) >= 1:
                marker = args[0]
                if marker == "er":
                    comparative, superlative = WiktionaryScraper._regular_adj_forms(word)
                    forms["comparative"] = comparative
                    forms["superlative"] = superlative
                elif marker not in {"-", "?", "more", "most"}:
                    forms["comparative"] = marker
            elif re.search(r"\b(adjective|形容詞)\b", wikitext, flags=re.IGNORECASE):
                comparative, superlative = WiktionaryScraper._regular_adj_forms(word)
                forms.setdefault("comparative", comparative)
                forms.setdefault("superlative", superlative)

        compact = WiktionaryScraper._compact_wikitext(wikitext, max_chars=3200)
        patterns = {
            "third_person_singular": [
                r"third-person singular(?: simple present)?[:\s]+([A-Za-z-]+)",
                r"三単現[:\s*]+([A-Za-z-]+)",
            ],
            "present_participle": [
                r"present participle[:\s]+([A-Za-z-]+)",
                r"現在分詞[:\s*]+([A-Za-z-]+)",
            ],
            "past_tense": [
                r"simple past(?: tense)?[:\s]+([A-Za-z-]+)",
                r"過去形[:\s*]+([A-Za-z-]+)",
            ],
            "past_participle": [
                r"past participle[:\s]+([A-Za-z-]+)",
                r"過去分詞[:\s*]+([A-Za-z-]+)",
            ],
            "plural": [
                r"plural[:\s]+([A-Za-z-]+)",
                r"複数形[:\s*]+([A-Za-z-]+)",
            ],
            "comparative": [
                r"comparative[:\s]+([A-Za-z-]+)",
                r"比較級[:\s*]+([A-Za-z-]+)",
            ],
            "superlative": [
                r"superlative[:\s]+([A-Za-z-]+)",
                r"最上級[:\s*]+([A-Za-z-]+)",
            ],
        }
        for key, regexes in patterns.items():
            if key in forms:
                continue
            for regex in regexes:
                match = re.search(regex, compact, flags=re.IGNORECASE)
                if match:
                    extracted = match.group(1)
                    if extracted.strip().lower() in _FORM_NOISE_TOKENS:
                        continue
                    forms[key] = extracted
                    break
        return forms

    @staticmethod
    def _extract_english_section_raw(wikitext: str) -> str:
        english_match = re.search(r"^==\s*English\s*==\s*$", wikitext, flags=re.MULTILINE | re.IGNORECASE)
        if not english_match:
            return wikitext
        tail = wikitext[english_match.end() :]
        next_lang = re.search(r"^==\s*[^=\n]+\s*==\s*$", tail, flags=re.MULTILINE)
        if next_lang:
            tail = tail[: next_lang.start()]
        return tail

    @staticmethod
    def _extract_language_section_raw(wikitext: str, lang_heading: str) -> str:
        language_match = re.search(
            rf"^==\s*{re.escape(lang_heading)}\s*==\s*$",
            wikitext,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        if not language_match:
            return ""
        tail = wikitext[language_match.end() :]
        next_lang = re.search(r"^==\s*[^=\n]+\s*==\s*$", tail, flags=re.MULTILINE)
        if next_lang:
            tail = tail[: next_lang.start()]
        return tail

    @classmethod
    def _extract_first_usex_example(cls, text: str) -> str | None:
        for match in re.finditer(r"\{\{(?:ux|uxi)\|([^{}]*)\}\}", text, flags=re.IGNORECASE):
            args = [x.strip() for x in match.group(1).split("|") if x.strip()]
            positional = [x for x in args if "=" not in x]
            if not positional:
                continue
            sentence = positional[1] if len(positional) >= 2 else positional[0]
            sentence = sentence.replace("'''", "").replace("''", "").strip()
            compact = cls._compact_wikitext(sentence, max_chars=240)
            if compact:
                return compact
        return None

    @classmethod
    def _extract_definitions_with_examples(cls, wikitext: str, max_items: int = 12) -> list[dict]:
        english_body = cls._extract_english_section_raw(wikitext)
        heading_matches = list(
            re.finditer(r"^(=+)\s*([^=\n]+?)\s*=+\s*$", english_body, flags=re.MULTILINE)
        )
        if not heading_matches:
            return []

        definitions: list[dict] = []
        for idx, heading in enumerate(heading_matches):
            level = len(heading.group(1))
            title = heading.group(2).strip()
            pos_key = cls._POS_SECTION_MAP.get(title.lower())
            if not pos_key:
                continue

            block_end = len(english_body)
            for nxt in heading_matches[idx + 1 :]:
                if len(nxt.group(1)) <= level:
                    block_end = nxt.start()
                    break
            block = english_body[heading.end() : block_end]

            current_index: int | None = None
            for raw_line in block.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                definition_match = re.match(r"^#(?![:*#;])\s*(.+)$", line)
                if definition_match:
                    meaning_en = cls._compact_wikitext(definition_match.group(1), max_chars=260)
                    if meaning_en:
                        definitions.append(
                            {
                                "part_of_speech": pos_key,
                                "meaning_en": meaning_en,
                                "example_en": "",
                            }
                        )
                        current_index = len(definitions) - 1
                        if len(definitions) >= max_items:
                            return definitions
                    continue

                if current_index is None:
                    continue
                if not line.startswith("#:"):
                    continue
                if definitions[current_index]["example_en"]:
                    continue
                example = cls._extract_first_usex_example(line)
                if example:
                    definitions[current_index]["example_en"] = example
        return definitions

    async def _fetch_parse(self, host: str, word: str) -> dict:
        url = f"https://{host}/w/api.php"
        params = {
            "action": "parse",
            "page": word,
            "prop": "wikitext|sections",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }
        delay_429 = self._FETCH_BASE_DELAY_429
        delay_other = self._FETCH_BASE_DELAY_OTHER
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            for attempt in range(self._FETCH_MAX_RETRIES):
                try:
                    res = await client.get(url, params=params, headers=headers)
                    if res.status_code in (429, 503) and attempt < self._FETCH_MAX_RETRIES - 1:
                        base = _retry_after_seconds(res, delay_429)
                        jitter = random.uniform(0.0, min(8.0, base * 0.15))
                        wait = base + jitter
                        logger.warning(
                            "HTTP %d for %r (try %d/%d); sleep %.1fs",
                            res.status_code, word, attempt + 1, self._FETCH_MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        delay_429 = min(delay_429 * 1.65, 360.0)
                        continue
                    res.raise_for_status()
                    return res.json()
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    code = exc.response.status_code
                    if code in (429, 503) and attempt < self._FETCH_MAX_RETRIES - 1:
                        base = _retry_after_seconds(exc.response, delay_429)
                        jitter = random.uniform(0.0, min(8.0, base * 0.15))
                        wait = base + jitter
                        logger.warning(
                            "HTTP %d for %r (try %d/%d); sleep %.1fs",
                            code, word, attempt + 1, self._FETCH_MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        delay_429 = min(delay_429 * 1.65, 360.0)
                        continue
                    if code in (403, 500, 502, 504) and attempt < self._FETCH_MAX_RETRIES - 1:
                        wait = delay_other + random.uniform(0.0, 2.0)
                        logger.warning(
                            "HTTP %d for %r (try %d/%d); sleep %.1fs",
                            code, word, attempt + 1, self._FETCH_MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        delay_other = min(delay_other * 1.5, 120.0)
                        continue
                    raise
                except (httpx.TimeoutException, httpx.RequestError) as exc:
                    last_error = exc
                    if attempt < self._FETCH_MAX_RETRIES - 1:
                        wait = delay_other + random.uniform(0.0, 2.0)
                        logger.warning(
                            "%s for %r (try %d/%d); sleep %.1fs",
                            type(exc).__name__, word, attempt + 1, self._FETCH_MAX_RETRIES, wait,
                        )
                        await asyncio.sleep(wait)
                        delay_other = min(delay_other * 1.5, 120.0)
                        continue
                    raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("unexpected fetch_parse retry flow")

    async def _scrape_component_host(self, host: str, source: str, component_text: str) -> dict:
        try:
            base = component_text.strip()
            if not base:
                return {"source": source, "error": "empty component"}
            candidates = [base]
            if base.endswith("-"):
                no_dash = base[:-1].strip()
                if no_dash:
                    candidates.append(no_dash)
            else:
                candidates.append(f"{base}-")

            parsed = None
            page = None
            for candidate in candidates:
                payload = await self._fetch_parse(host, candidate)
                maybe = payload.get("parse")
                if maybe:
                    parsed = maybe
                    page = candidate
                    break
            if not parsed or not page:
                return {"source": source, "error": "parse payload not found"}

            page_url = f"https://{host}/wiki/{quote(page)}"
            wikitext = str(parsed.get("wikitext") or "")
            sections = parsed.get("sections") or []

            meaning_titles = [
                self._find_section_title(sections, "prefix", "接頭辞"),
                self._find_section_title(sections, "suffix", "接尾辞"),
                self._find_section_title(sections, "combining form", "語根"),
            ]
            meanings: list[str] = []
            for title in meaning_titles:
                if not title:
                    continue
                meanings = self._merge_unique_str_items(meanings, self._extract_section_glosses(wikitext, title, sections=sections))
            if not meanings:
                ety_titles = self._find_etymology_section_titles(sections)
                if ety_titles:
                    excerpt = self._extract_section_body(
                        wikitext, ety_titles[0], max_chars=220, sections=sections,
                    )
                    if excerpt:
                        meanings = [excerpt]

            rel_title = self._find_section_title(sections, "related terms", "関連語", "類義語")
            syn_title = self._find_section_title(sections, "synonyms", "類義語")
            related_terms = self._merge_unique_str_items(
                self._extract_section_items(wikitext, rel_title, sections=sections) if rel_title else [],
                self._extract_section_items(wikitext, syn_title, sections=sections) if syn_title else [],
            )
            derived_terms = []
            if derived_title := self._find_section_title(sections, "derived terms", "派生語"):
                derived_terms = self._extract_section_items(wikitext, derived_title, sections=sections)

            return {
                "source": source,
                "url": page_url,
                "meanings": meanings,
                "related_terms": related_terms,
                "derived_terms": derived_terms,
            }
        except Exception as exc:  # noqa: BLE001
            return {"source": source, "error": str(exc)}

    async def _scrape_host(self, host: str, source: str, word: str) -> dict:
        page_url = f"https://{host}/wiki/{quote(word)}"
        try:
            payload = await self._fetch_parse(host, word)
            parsed = payload.get("parse")
            if not parsed:
                return {"source": source, "url": page_url, "error": "parse payload not found"}

            wikitext = str(parsed.get("wikitext") or "")
            sections = parsed.get("sections") or []
            # 語源は英語セクション内の Etymology / Etymology 1… / 語源・由来 見出し配下のみ対象にする。
            # 全文探索だと Translingual 側の Etymology が先に拾われる場合がある（例: run / all）。
            english_body = self._extract_english_section_raw(wikitext)
            summary = self._compact_wikitext(english_body)
            etymology_bodies: list[str] = []
            for raw_body in self._extract_etymology_blocks_from_language_section(english_body):
                cleaned = self._strip_wiki_category_links(raw_body)
                if cleaned and cleaned not in etymology_bodies:
                    etymology_bodies.append(cleaned)
            sources = etymology_bodies
            etymology_excerpt = (
                self._compact_wikitext(etymology_bodies[0], max_chars=1200) if etymology_bodies else None
            )

            etymology_components: list[dict] = []
            language_chain: list[dict] = []
            component_meanings: list[dict] = []
            for raw in sources:
                comps = self._extract_etymology_components(raw, word)
                etymology_components = self._merge_unique_dict_items_by_text(etymology_components, comps)
                chains = self._extract_language_chain(raw)
                language_chain = self._merge_unique_dict_items(language_chain, chains)
                cm = self._extract_component_meanings(raw, comps, word)
                component_meanings = self._merge_unique_dict_items(component_meanings, cm)
            etymology_components = self._follow_same_word_etymology(
                wikitext, word, sources, etymology_components
            )
            etymology_variants = self._extract_etymology_variants(etymology_bodies or sources, word) if (etymology_bodies or sources) else []

            pronunciation_ipa = self._extract_ipa(english_body, sections)
            derived_terms: list[str] = []
            synonyms: list[str] = []
            antonyms: list[str] = []
            phrases: list[str] = []
            definitions = self._extract_definitions_with_examples(wikitext)

            if title := self._find_section_title(sections, "derived terms", "派生語"):
                derived_terms = self._extract_section_items(english_body, title, sections=sections)
            if title := self._find_section_title(sections, "synonyms", "類義語"):
                synonyms = self._extract_section_items(english_body, title, sections=sections)
            if title := self._find_section_title(sections, "antonyms", "対義語"):
                antonyms = self._extract_section_items(english_body, title, sections=sections)
            if title := self._find_section_title(sections, "phrases", "idioms", "成句"):
                phrases = self._extract_section_items(english_body, title, sections=sections)

            forms = self._extract_forms(word, english_body)

            return {
                "source": source,
                "url": page_url,
                "summary": summary,
                "etymology_excerpt": etymology_excerpt,
                "etymology_components": etymology_components,
                "language_chain": language_chain,
                "component_meanings": component_meanings,
                "etymology_variants": etymology_variants,
                "pronunciation_ipa": pronunciation_ipa,
                "forms": forms,
                "derived_terms": derived_terms,
                "synonyms": synonyms,
                "antonyms": antonyms,
                "phrases": phrases,
                "definitions": definitions,
            }
        except Exception as exc:  # noqa: BLE001
            return {"source": source, "url": page_url, "error": str(exc)}

    async def scrape(self, word: str) -> dict:
        cached = self._load_cache(word)
        if cached is not None:
            return cached

        english = await self._scrape_host("en.wiktionary.org", "wiktionary_en", word)
        japanese = await self._scrape_host("ja.wiktionary.org", "wiktionary_ja", word)
        if not english.get("error") and japanese.get("error"):
            self._save_cache(word, english)
            return english
        if english.get("error") and not japanese.get("error"):
            self._save_cache(word, japanese)
            return japanese
        if not english.get("error") and not japanese.get("error"):
            merged = dict(english)
            merged["source"] = "wiktionary_en"
            merged["fallback_source"] = "wiktionary_ja"
            for key in (
                "etymology_excerpt",
                "summary",
                "etymology_components",
                "language_chain",
                "component_meanings",
                "etymology_variants",
                "pronunciation_ipa",
                "forms",
                "derived_terms",
                "synonyms",
                "antonyms",
                "phrases",
                "definitions",
            ):
                en_value = merged.get(key)
                ja_value = japanese.get(key)
                if key in {"derived_terms", "synonyms", "antonyms", "phrases"}:
                    en_items = en_value if isinstance(en_value, list) else []
                    ja_items = ja_value if isinstance(ja_value, list) else []
                    merged[key] = self._merge_unique_str_items(ja_items, en_items)
                elif key == "definitions":
                    en_items = en_value if isinstance(en_value, list) else []
                    ja_items = ja_value if isinstance(ja_value, list) else []
                    merged[key] = self._merge_unique_dict_items(en_items, ja_items)
                elif key == "forms":
                    en_forms = en_value if isinstance(en_value, dict) else {}
                    ja_forms = ja_value if isinstance(ja_value, dict) else {}
                    combined_forms = dict(ja_forms)
                    for k, v in en_forms.items():
                        if k not in combined_forms or not combined_forms.get(k):
                            combined_forms[k] = v
                    merged[key] = combined_forms
                elif key in {"etymology_components", "language_chain", "component_meanings", "etymology_variants"}:
                    ja_items = ja_value if isinstance(ja_value, list) else []
                    en_items = en_value if isinstance(en_value, list) else []
                    if key == "etymology_components":
                        merged[key] = self._merge_unique_dict_items_by_text(ja_items, en_items)
                    else:
                        merged[key] = self._merge_unique_dict_items(ja_items, en_items)
                elif key in {"etymology_excerpt", "summary", "pronunciation_ipa"}:
                    merged[key] = self._merge_text_ja_first(
                        ja_value if isinstance(ja_value, str) else None,
                        en_value if isinstance(en_value, str) else None,
                    )
                elif not en_value and ja_value:
                    merged[key] = ja_value
            self._save_cache(word, merged)
            return merged

        error_result = {
            "source": "wiktionary_en",
            "fallback_source": "wiktionary_ja",
            "url": english.get("url"),
            "error": f"en: {english.get('error')} / ja: {japanese.get('error')}",
        }
        return error_result

    async def scrape_component_page(self, component_text: str) -> dict:
        english = await self._scrape_component_host("en.wiktionary.org", "wiktionary_en", component_text)
        japanese = await self._scrape_component_host("ja.wiktionary.org", "wiktionary_ja", component_text)

        if english.get("error") and japanese.get("error"):
            return {"meanings": [], "related_terms": [], "derived_terms": [], "source_url": None}
        if english.get("error"):
            return {
                "meanings": japanese.get("meanings", []),
                "related_terms": japanese.get("related_terms", []),
                "derived_terms": japanese.get("derived_terms", []),
                "source_url": japanese.get("url"),
            }
        if japanese.get("error"):
            return {
                "meanings": english.get("meanings", []),
                "related_terms": english.get("related_terms", []),
                "derived_terms": english.get("derived_terms", []),
                "source_url": english.get("url"),
            }

        return {
            "meanings": self._merge_unique_str_items(
                japanese.get("meanings", []),
                english.get("meanings", []),
            ),
            "related_terms": self._merge_unique_str_items(
                japanese.get("related_terms", []),
                english.get("related_terms", []),
            ),
            "derived_terms": self._merge_unique_str_items(
                japanese.get("derived_terms", []),
                english.get("derived_terms", []),
            ),
            "source_url": japanese.get("url") or english.get("url"),
        }
