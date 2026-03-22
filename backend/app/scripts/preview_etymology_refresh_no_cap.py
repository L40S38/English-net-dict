"""語源成分抽出の再取得結果を Markdown で確認する。

出力 Markdown には比較表に加え、語源セクションの **wikitext 原文**（`{{}}` / `[[]]`）と、
共有抽出関数 `extract_etymology_components` 相当の **抽出経路メモ**（検討用）を載せる。

実行例:
  uv run python -m app.scripts.preview_etymology_refresh_no_cap --word astound
  uv run python -m app.scripts.preview_etymology_refresh_no_cap --limit 50 --output ./tmp-etymology-preview.md
  uv run python -m app.scripts.preview_etymology_refresh_no_cap --all --output tmp-etymology-refresh-preview.md
  # 全件を100語ずつ分割（1〜100語目、101〜200語目…）。429回避用に別実行する。
  # 429 が続く場合は --delay 2.0 以上や --max-retries を増やす（Retry-After を自動で待つ）。
  uv run python -m app.scripts.preview_etymology_refresh_no_cap --all --batch 1 --output tmp-part-01.md
  uv run python -m app.scripts.preview_etymology_refresh_no_cap --all --batch 2 --output tmp-part-02.md
"""

from __future__ import annotations

import argparse
import asyncio
import random
import re
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from tqdm import tqdm

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Word
from app.services.scraper.etymology_extractors import (
    _ETY_AFTER_PLUS,
    _ETYMON_M_LANG_ALLOWLIST,
    _ETY_PLUS_RIGHT_OPERAND,
    clean_token as _clean_token,
    extract_etymology_components,
    normalize_template_arg as _normalize_template_arg,
)
from app.services.scraper.wiktionary import WiktionaryScraper
from app.utils.etymology_component_sanitize import sanitize_etymology_component_token
from app.utils.etymology_components import looks_like_morpheme


@dataclass
class PreviewRow:
    word: str
    stored_components: list[str]
    current_scrape_components: list[str]
    no_cap_components: list[str]
    added_by_no_cap: list[str]
    # 検討用: 語源セクション原文（{{}} / [[]] 付き）と、抽出ロジック上どの経路が効いたか
    etymology_raw_blocks: list[str] = field(default_factory=list)
    extraction_trace: str = ""


# トレース用に、人が読める短い説明（正規表現の意図）
_PLUS_RAW_PATTERN_DESC = (
    "平文「左 + 右」: `[^\\\\W\\\\d_][^\\\\s+]{0,31}\\\\s*+` + `_ETY_AFTER_PLUS`（LRM等） + `_ETY_PLUS_RIGHT_OPERAND`（joy / -ly）"
)
_PLUS_ASCII_PATTERN_DESC = (
    "ASCII フォールバック: `\\\\b[A-Za-z]{1,6}\\\\s*+` + `_ETY_AFTER_PLUS` + `[A-Za-z]{2,16}|ハイフン+英字`"
)


def _trace_etymology_extraction(raw: str, word: str) -> list[str]:
    """語源本文に対し、抽出ロジックがどのパターンを辿るか検討用の箇条書きを返す（本文と同じ順序）。"""
    lines: list[str] = []
    raw = raw or ""
    raw = re.sub(r"<ref[^>]*>.*?</ref>", "", raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r"<ref[^>]*/\s*>", "", raw, flags=re.IGNORECASE)
    if not raw.strip():
        lines.append("- （空の語源ブロック）")
        return lines

    # --- 原文に現れる {{...}} / [[...]]（検討材料）---
    templates = []
    for m in re.finditer(r"\{\{[^{}]*\}\}", raw):
        t = m.group(0)
        if t not in templates:
            templates.append(t)
    if templates:
        show = templates[:18]
        tail = f" …（他 {len(templates) - len(show)} 件）" if len(templates) > len(show) else ""
        lines.append(
            "- **本文中のテンプレ `{{...}}`（先頭・重複除く）**: "
            + " · ".join(f"`{x}`" for x in show)
            + tail
        )
    link_labels = re.findall(r"\[\[([^\]]+)\]\]", raw)
    if link_labels:
        short = [x.replace("\n", " ")[:80] for x in link_labels[:14]]
        extra = f" …（他 {len(link_labels) - len(short)} 件）" if len(link_labels) > len(short) else ""
        lines.append("- **`[[...]]` リンク先頭**: " + ", ".join(f"`[[{s}]]`" for s in short) + extra)

    # --- 経路（extract_etymology_components と同じ分岐順）---
    components: list[dict[str, str]] = []

    def add_component(text: str, meaning: str, comp_type: str) -> None:
        token = _clean_token(text)
        if not token:
            return
        sanitized = sanitize_etymology_component_token(token)
        if not sanitized:
            return
        comp = {"text": sanitized, "meaning": meaning, "type": comp_type}
        if comp not in components:
            components.append(comp)

    for match in re.finditer(
        r"\{\{(?:suf|suffix)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        full = match.group(0)
        args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if len(args) >= 1 and re.fullmatch(r"[a-z]{2,3}", args[0].lower()):
            args = args[1:]
        if len(args) < 2:
            lines.append(f"- **経路: suf|suffix**（形はあるが引数不足でスキップ）: `{full}`")
            continue
        stem = _normalize_template_arg(args[0])
        suf_raw = _normalize_template_arg(args[1])
        if not stem or not suf_raw or "=" in stem or "=" in suf_raw:
            lines.append(f"- **経路: suf|suffix**（stem/suf 不正でスキップ）: `{full}`")
            continue
        if not looks_like_morpheme(stem):
            lines.append(f"- **経路: suf|suffix**（stem が morpheme 判定で除外）: `{full}`")
            continue
        suf_text = suf_raw if suf_raw.startswith("-") else f"-{suf_raw}"
        if not looks_like_morpheme(suf_text.lstrip("-")):
            lines.append(f"- **経路: suf|suffix**（接尾辞が morpheme 判定で除外）: `{full}`")
            continue
        add_component(stem, "語根要素", "root")
        add_component(suf_text, "接尾辞要素", "suffix")
        lines.append(
            f"- **経路: suf|suffix** → stem `{stem}` + `{suf_text}` : `{full}`"
        )

    for match in re.finditer(
        r"\{\{(?:surf|surface analysis)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        full = match.group(0)
        args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if not args:
            continue
        if len(args) >= 1 and re.fullmatch(r"[a-z]{2,3}", args[0].lower()):
            args = args[1:]
        if not args:
            continue
        morpheme_parts: list[str] = []
        for part in args[:3]:
            text = _normalize_template_arg(part)
            if not text or "=" in text:
                continue
            if not looks_like_morpheme(text.lstrip("-").rstrip("-")):
                continue
            morpheme_parts.append(text)
        if not morpheme_parts:
            lines.append(f"- **経路: surf|surface analysis**（morpheme なし）: `{full}`")
            continue
        for text in morpheme_parts:
            if text.startswith("-"):
                add_component(text, "接尾辞要素", "suffix")
            elif text.endswith("-"):
                add_component(text, "接頭要素", "prefix")
            else:
                add_component(text, "語根要素", "root")
        lines.append(
            f"- **経路: surf|surface analysis** → "
            + " / ".join(f"`{p}`" for p in morpheme_parts)
            + f" : `{full}`"
        )

    for match in re.finditer(
        r"\{\{(?:af|affix|prefix|pre)\|([^}]*)\}\}",
        raw,
        flags=re.IGNORECASE,
    ):
        full = match.group(0)
        args = [x.strip() for x in match.group(1).split("|") if x.strip()]
        if not args:
            continue
        if len(args) >= 1 and re.fullmatch(r"[a-z]{2,3}", args[0].lower()):
            args = args[1:]
        if len(args) < 2:
            lines.append(f"- **経路: af|affix|prefix|pre**（引数不足）: `{full}`")
            continue
        morpheme_parts: list[str] = []
        for part in args[:3]:
            text = _normalize_template_arg(part)
            if not text or "=" in text:
                continue
            if not looks_like_morpheme(text):
                continue
            morpheme_parts.append(text)
        if not morpheme_parts:
            lines.append(f"- **経路: af|affix|prefix|pre**（morpheme なし）: `{full}`")
            continue
        for idx, text in enumerate(morpheme_parts):
            add_component(
                text,
                "接頭要素" if idx == 0 else "語根要素",
                "prefix" if idx == 0 else "root",
            )
        lines.append(
            f"- **経路: af|affix|prefix|pre** → " + " / ".join(f"`{p}`" for p in morpheme_parts) + f" : `{full}`"
        )

    if not components:
        der_hit = False
        for match in re.finditer(r"\{\{der\+?\|([^}]*)\}\}", raw, flags=re.IGNORECASE):
            full = match.group(0)
            args = [x.strip() for x in match.group(1).split("|")]
            if len(args) < 3:
                continue
            ety_text = args[2]
            links = [x.strip() for x in re.findall(r"\[\[([^\]|]+)", ety_text) if x.strip()]
            if "a" in links and "bandon" in links:
                components.clear()
                add_component("a", "〜へ、〜の方へ", "prefix")
                add_component("bandon", "支配、権限", "root")
                lines.append(f"- **経路: der（特例 abandon）** : `{full}`")
                der_hit = True
                break
            if "a" in links and "ban" in links:
                components.clear()
                add_component("a", "〜へ、〜の方へ", "prefix")
                add_component("ban", "布告、支配", "root")
                lines.append(f"- **経路: der（特例 abandon 短）** : `{full}`")
                der_hit = True
                break
            if len(links) >= 2:
                components.clear()
                add_component(links[-2], "語源要素", "prefix")
                add_component(links[-1], "語源要素", "root")
                lines.append(
                    f"- **経路: der** → `[[{links[-2]}]]` + `[[{links[-1]}]]` : `{full}`"
                )
                der_hit = True
                break
        if not der_hit:
            lines.append("- **経路: der** … 該当なし（またはリンク不足）")

    if not components:
        plus_match = re.search(
            r"([^\W\d_][^\s+]{0,31})\s*\+"
            + _ETY_AFTER_PLUS
            + "("
            + _ETY_PLUS_RIGHT_OPERAND
            + ")",
            raw,
            flags=re.UNICODE,
        )
        if plus_match:
            left = _clean_token(plus_match.group(1))
            right = _clean_token(plus_match.group(2))
            if left and right:
                components.clear()
                add_component(left, "接頭要素", "prefix")
                add_component(right, "語根要素", "root")
                lines.append(
                    f"- **経路: 平文 `+`（語源本文直読み）** → `{left}` + `{right}` · {_PLUS_RAW_PATTERN_DESC}"
                )
            else:
                lines.append("- **経路: 平文 `+`（本文）** … マッチしたが clean/sanitize で空")
        else:
            lines.append("- **経路: 平文 `+`（語源本文直読み）** … マッチなし")

    if not components:
        compact = WiktionaryScraper._compact_wikitext(raw, max_chars=1200)
        plus_match_compact = re.search(
            r"([^\W\d_][^\s+]{0,31})\s*\+"
            + _ETY_AFTER_PLUS
            + "("
            + _ETY_PLUS_RIGHT_OPERAND
            + ")",
            compact,
            flags=re.UNICODE,
        )
        if plus_match_compact:
            left = _clean_token(plus_match_compact.group(1))
            right = _clean_token(plus_match_compact.group(2))
            if left and right:
                components.clear()
                add_component(left, "接頭要素", "prefix")
                add_component(right, "語根要素", "root")
                snippet = compact[:280] + ("…" if len(compact) > 280 else "")
                lines.append(
                    f"- **経路: 平文 `+`（_compact_wikitext 後）** → `{left}` + `{right}` · 参考: `{snippet}`"
                )
            else:
                lines.append("- **経路: 平文 `+`（compact 後）** … トークン空")
        else:
            lines.append(
                "- **経路: 平文 `+`（_compact_wikitext 後）** … マッチなし"
            )

    if not components:
        plain_der = re.search(
            r"\{\{(?:der|inh|bor|uder|lbor|ubor)\+?\|[^|}]+\|[^|}]+\|([^|}\s]+)",
            raw,
            flags=re.IGNORECASE,
        )
        if plain_der:
            term = _clean_token(plain_der.group(1))
            if term:
                components.clear()
                add_component(term, "語源要素", "root")
                lines.append(f"- **経路: plain `{{{{der|…|term}}}}` 単独** → `{term}`")
            else:
                lines.append("- **経路: plain der** … term 空")
        else:
            lines.append("- **経路: plain der（単一項）** … マッチなし")

    if not components:
        plus_match = re.search(
            r"\b([A-Za-z]{1,6})\s*\+"
            + _ETY_AFTER_PLUS
            + r"([A-Za-z]{2,16}|[-–—\u2010][A-Za-z]{1,15})\b",
            raw,
        )
        if plus_match:
            components.clear()
            add_component(plus_match.group(1), "接頭要素", "prefix")
            add_component(plus_match.group(2), "語根要素", "root")
            lines.append(
                f"- **経路: ASCII `+` フォールバック** → `{plus_match.group(1)}` + `{plus_match.group(2)}` · {_PLUS_ASCII_PATTERN_DESC}"
            )
        else:
            lines.append("- **経路: ASCII `+` フォールバック** … マッチなし")

    candidate_terms: list[str] = []
    if len(components) <= 1:
        for m in re.finditer(r"\{\{root\|[^|}]+\|[^|}]+\|([^|}]+)", raw, flags=re.IGNORECASE):
            candidate_terms.append(_clean_token(m.group(1)))
        for m in re.finditer(
            r"\{\{(?:der|inh|bor|uder|lbor|ubor)\+?\|[^|}]+\|[^|}]+\|([^|}]+)",
            raw,
            flags=re.IGNORECASE,
        ):
            candidate_terms.append(_clean_token(m.group(1)))
        for m in re.finditer(r"\{\{m\|([^|}]+)\|([^|}]+)(?:\|([^|}]+))?", raw, flags=re.IGNORECASE):
            lang = (m.group(1) or "").strip().lower()
            if lang not in _ETYMON_M_LANG_ALLOWLIST:
                continue
            candidate_terms.append(_clean_token(m.group(2)))

        base = word.lower().strip()
        unique_terms: list[str] = []
        for term in candidate_terms:
            if not term:
                continue
            normalized = term.lower().strip("-")
            if normalized == base:
                continue
            if term not in unique_terms:
                unique_terms.append(term)

        if unique_terms:
            components.clear()
            for idx, term in enumerate(unique_terms):
                if term.startswith("*"):
                    add_component(term, "印欧祖語などの祖語形", "proto_root")
                elif idx == 0:
                    add_component(term, "語源要素", "prefix")
                else:
                    add_component(term, "語源要素", "root")
            lines.append(
                "- **経路: 候補語列（root / der|inh|bor / m）から再構成** → "
                + ", ".join(f"`{t}`" for t in unique_terms)
            )
        elif len(components) <= 1:
            lines.append(
                "- **経路: 候補語列フォールバック** … 利用可能な候補なし（`len(components)<=1` だが unique_terms 空）"
            )

    final = extract_etymology_components(raw, word, WiktionaryScraper._compact_wikitext)
    if final:
        lines.append(
            "- **no_cap 最終成分**: "
            + " · ".join(f"`{c['text']}` ({c.get('type', '')})" for c in final)
        )
    else:
        lines.append("- **no_cap 最終成分**: （なし）")

    return lines


def _etymology_sources_from_payload(scraper: WiktionaryScraper, payload: dict) -> list[str]:
    """WiktionaryScraper._scrape_host と同じ手順で語源セクション本文を列挙する。"""
    parsed = payload.get("parse") or {}
    wikitext = str(parsed.get("wikitext") or "")
    english_body = scraper._extract_english_section_raw(wikitext)
    sources: list[str] = []
    for raw_body in scraper._extract_etymology_blocks_from_language_section(english_body):
        cleaned = scraper._strip_wiki_category_links(raw_body)
        if cleaned and cleaned not in sources:
            sources.append(cleaned)
    return sources


def _retry_after_seconds(response: httpx.Response, fallback: float) -> float:
    """429/503 応答の Retry-After（秒数または HTTP-date）を解釈する。無ければ fallback を使う。"""
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


async def _fetch_parse_retry(
    scraper: WiktionaryScraper,
    word: str,
    *,
    max_retries: int = 20,
) -> dict:
    # 429: Retry-After を最優先し、指数バックオフは補助。上限を緩めて長時間レート制限に耐える。
    delay_429 = 5.0
    delay_other = 3.0
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await scraper._fetch_parse("en.wiktionary.org", word)
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            code = exc.response.status_code
            if code in (429, 503) and attempt < max_retries - 1:
                base = _retry_after_seconds(exc.response, delay_429)
                jitter = random.uniform(0.0, min(8.0, base * 0.15))
                wait = base + jitter
                print(
                    f"[warn] HTTP {code} for {word!r} (try {attempt + 1}/{max_retries}); "
                    f"sleep {wait:.1f}s (Retry-After / backoff)...",
                    flush=True,
                )
                await asyncio.sleep(wait)
                delay_429 = min(delay_429 * 1.65, 360.0)
                continue
            raise
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = delay_other + random.uniform(0.0, 2.0)
                print(
                    f"[warn] {type(exc).__name__} for {word!r} (try {attempt + 1}/{max_retries}); "
                    f"sleep {wait:.1f}s...",
                    flush=True,
                )
                await asyncio.sleep(wait)
                delay_other = min(delay_other * 1.5, 120.0)
                continue
            raise
    raise RuntimeError(f"fetch failed after retries: {last_exc!r}")


async def _current_and_no_cap_from_en_wiktionary(
    scraper: WiktionaryScraper,
    word: str,
    *,
    max_retries: int = 20,
) -> tuple[list[str], list[str], list[str]]:
    """EN Wiktionary を1回だけ取得し、成分テキスト2種と語源セクション原文（wikitext）を返す。"""
    payload = await _fetch_parse_retry(scraper, word, max_retries=max_retries)
    sources = _etymology_sources_from_payload(scraper, payload)
    if not sources:
        return [], [], []
    parsed = payload.get("parse") or {}
    wikitext = str(parsed.get("wikitext") or "")

    etymology_components: list[dict] = []
    for raw in sources:
        comps = scraper._extract_etymology_components(raw, word)
        etymology_components = scraper._merge_unique_dict_items_by_text(etymology_components, comps)
    etymology_components = scraper._follow_same_word_etymology(
        wikitext, word, sources, etymology_components
    )
    current_texts = [
        str(item.get("text", "")).strip() for item in etymology_components if str(item.get("text", "")).strip()
    ]

    merged_no_cap: list[dict[str, str]] = []
    for raw in sources:
        components = extract_etymology_components(raw, word, WiktionaryScraper._compact_wikitext)
        merged_no_cap = scraper._merge_unique_dict_items_by_text(merged_no_cap, components)
    merged_no_cap = scraper._follow_same_word_etymology(
        wikitext, word, sources, merged_no_cap
    )
    no_cap_texts = [
        str(item.get("text", "")).strip() for item in merged_no_cap if str(item.get("text", "")).strip()
    ]
    return current_texts, no_cap_texts, sources


def _format_etymology_raw_for_md(blocks: list[str]) -> str:
    """語源セクションの wikitext を Markdown コードブロックに収める。"""
    if not blocks:
        return "_（語源セクションなし／未取得）_\n"
    out: list[str] = []
    for i, block in enumerate(blocks):
        out.append(f"###### Etymology ブロック {i + 1}\n")
        body = block.rstrip("\n")
        if len(body) > 12000:
            body = body[:12000] + "\n…（12000文字で打ち切り）"
        out.append("```wikitext\n")
        out.append(body + "\n")
        out.append("```\n")
    return "".join(out)


def _format_extraction_trace_for_md(sources: list[str], word: str) -> str:
    """抽出ロジックの検討用トレース（箇条書き）。"""
    if not sources:
        return "_（語源なし）_\n"
    parts: list[str] = []
    for i, src in enumerate(sources):
        parts.append(f"###### Etymology ブロック {i + 1} — パターン・経路\n\n")
        for line in _trace_etymology_extraction(src, word):
            parts.append(line + "\n")
        parts.append("\n")
    return "".join(parts)


def _get_target_words(db: Session, words: list[str], limit: int | None) -> list[Word]:
    if words:
        lowered = {w.strip().lower() for w in words if w.strip()}
        result: list[Word] = []
        for word in db.scalars(select(Word).order_by(Word.id.asc())):
            if word.word.lower() in lowered:
                result.append(word)
        return result
    stmt = select(Word).order_by(Word.id.asc())
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def _build_markdown(rows: list[PreviewRow], *, mode_note: str | None = None) -> str:
    lines: list[str] = []
    lines.append("# Etymology Refresh Preview")
    lines.append("")
    if mode_note:
        lines.append(f"- {mode_note}")
    lines.append(f"- Compared words: **{len(rows)}**")
    lines.append("- `current_scrape_components`: 現行の `WiktionaryScraper._extract_etymology_components`")
    lines.append("- `no_cap_components`: 共有 `extract_etymology_components` を直接呼んだ比較列")
    lines.append(
        "- 取得は **英語版 Wiktionary の API を単語あたり1回**（レート制限対策）。"
        "`scrape()` の en+ja マージ結果とは一致しない場合があります。"
    )
    lines.append(
        "- 下部 **「語源原文（wikitext）」** に `{{}}` / `[[]]` を含むセクション本文、"
        "**「抽出トレース」** に共有 `extract_etymology_components` と同順の経路メモを載せる（検討用）。"
    )
    lines.append("")
    lines.append("| word | stored_components | current_scrape_components | no_cap_components | added_by_no_cap |")
    lines.append("|---|---|---|---|---|")
    for row in rows:
        lines.append(
            "| "
            + row.word
            + " | "
            + ", ".join(row.stored_components or ["-"])
            + " | "
            + ", ".join(row.current_scrape_components or ["-"])
            + " | "
            + ", ".join(row.no_cap_components or ["-"])
            + " | "
            + ", ".join(row.added_by_no_cap or ["-"])
            + " |"
        )
    lines.append("")
    lines.append("## 語源原文（wikitext）と抽出トレース")
    lines.append("")
    lines.append(
        "英語版の **Etymology セクション本文**（API から取得した wikitext。`{{}}`・`[[]]` 付き）と、"
        " `extract_etymology_components` と同じ順序で辿る **パターン経路**（`suf` / 平文 `A + B` 等）のメモ。"
    )
    lines.append("")
    for row in rows:
        lines.append(f"### `{row.word}`")
        lines.append("")
        lines.append("#### 語源原文（wikitext）")
        lines.append("")
        lines.append(_format_etymology_raw_for_md(row.etymology_raw_blocks))
        lines.append("")
        lines.append("#### 抽出トレース")
        lines.append("")
        lines.append(row.extraction_trace or "_（なし）_\n")
        lines.append("")
    lines.append("## Notes")
    lines.append("- このスクリプトはDBを書き換えません（比較のみ）。")
    lines.append("- `added_by_no_cap` は `no_cap_components` にのみ存在する成分です（通常は空の想定）。")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Preview etymology refresh result when removing [:3] cap.")
    parser.add_argument("--word", action="append", default=[], help="Target word (repeatable).")
    parser.add_argument(
        "--all",
        action="store_true",
        help="DB内の全単語を対象にする（--limit を無視。--batch 指定時はその範囲のみ）。",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=None,
        metavar="N",
        help="--all と併用。1始まりのバッチ番号。例: --batch-size 100 のとき batch 1=1〜100語目、2=101〜200語目。",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        metavar="K",
        help="--batch 1語あたりの件数（既定: 100）。--batch 未指定時は無視。",
    )
    parser.add_argument("--limit", type=int, default=30, help="Max words when neither --word nor --all is set.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tmp-etymology-refresh-preview.md"),
        help="Output markdown path.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="各単語の処理後に待つ秒数（未指定時: --all なら 1.2、それ以外は 0）。429 が続くときは 2.0 以上推奨。",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=20,
        metavar="N",
        help="API 取得の最大再試行回数（429/503 時は Retry-After と指数バックオフ）。既定: 20。",
    )
    args = parser.parse_args()

    delay_between_words = args.delay if args.delay is not None else (1.2 if args.all else 0.0)

    if args.word and args.all:
        parser.error("--word と --all は同時に指定できません。")
    if args.batch is not None and not args.all:
        parser.error("--batch は --all と併用してください。")
    if args.batch is not None and args.batch < 1:
        parser.error("--batch は 1 以上である必要があります。")
    if args.batch is not None and args.batch_size < 1:
        parser.error("--batch-size は 1 以上である必要があります。")
    if args.max_retries < 1:
        parser.error("--max-retries は 1 以上である必要があります。")

    db = SessionLocal()
    scraper = WiktionaryScraper()
    try:
        if args.word:
            targets = _get_target_words(db, args.word, None)
        elif args.all:
            all_targets = _get_target_words(db, [], None)
            if args.batch is not None:
                start_idx = (args.batch - 1) * args.batch_size
                end_idx = start_idx + args.batch_size
                targets = all_targets[start_idx:end_idx]
                if targets:
                    hi = start_idx + len(targets)
                    print(
                        f"[info] --batch {args.batch} (--batch-size {args.batch_size}): "
                        f"words {start_idx + 1}–{hi} of {len(all_targets)} total",
                        flush=True,
                    )
                else:
                    print(
                        f"[warn] --batch {args.batch}: empty range "
                        f"(DB has {len(all_targets)} word(s); slice starts at index {start_idx}).",
                        flush=True,
                    )
            else:
                targets = all_targets
        else:
            targets = _get_target_words(db, [], args.limit)

        print(f"[info] processing {len(targets)} word(s)...", flush=True)
        print(f"[info] max API retries per word: {args.max_retries}", flush=True)
        if delay_between_words > 0:
            print(f"[info] delay between words: {delay_between_words}s", flush=True)
        rows: list[PreviewRow] = []
        for idx, word in tqdm(enumerate(targets)):
            if idx > 0 and delay_between_words > 0:
                await asyncio.sleep(delay_between_words)
            if args.all and idx > 0 and idx % 100 == 0:
                print(f"[progress] {idx}/{len(targets)} words...", flush=True)
            current_components, no_cap_components, etym_sources = await _current_and_no_cap_from_en_wiktionary(
                scraper,
                word.word,
                max_retries=args.max_retries,
            )
            stored_components = []
            if word.etymology:
                stored_components = [
                    str(item.component_text).strip()
                    for item in (word.etymology.component_items or [])
                    if str(item.component_text).strip()
                ]
            added_by_no_cap = [term for term in no_cap_components if term not in current_components]
            trace_md = _format_extraction_trace_for_md(etym_sources, word.word)
            rows.append(
                PreviewRow(
                    word=word.word,
                    stored_components=stored_components,
                    current_scrape_components=current_components,
                    no_cap_components=no_cap_components,
                    added_by_no_cap=added_by_no_cap,
                    etymology_raw_blocks=etym_sources,
                    extraction_trace=trace_md,
                )
            )

        mode_note = None
        if args.all:
            mode_note = "Mode: **`--all`** (DB内の全単語)"
            if args.batch is not None:
                mode_note += f" — **`--batch {args.batch}`** / **`--batch-size {args.batch_size}`**（部分実行）"
            if delay_between_words > 0:
                mode_note += f" — 単語間待機 **{delay_between_words}s**"
        elif args.word:
            mode_note = f"Mode: **`--word`** ({len(args.word)} 件指定)"
        else:
            mode_note = f"Mode: **`--limit {args.limit}`**"
        markdown = _build_markdown(rows, mode_note=mode_note)
        args.output.write_text(markdown, encoding="utf-8")
        print(f"[ok] wrote markdown: {args.output}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
