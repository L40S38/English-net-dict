"""
成句・熟語の意味を Wiktionary → WordNet → Web → LLM の順で取得し、
日本語で1行に要約する共通サービス。
patch_phrase_meanings と patch_refresh_word_data の両方で利用する。
"""
from __future__ import annotations

import re
from openai import OpenAI

from app.config import settings
from app.services.scraper.wiktionary import WiktionaryScraper
from app.services.web_word_search import search_web_dictionary, search_web_general
from app.services.wordnet_service import get_wordnet_snapshot

_WEB_DICT_UNAVAILABLE = False
_WEB_GENERAL_UNAVAILABLE = False


def clean_line(text: str, max_len: int = 220) -> str:
    compact = " ".join(str(text).split()).strip()
    if not compact:
        return ""
    return compact[:max_len]


def needs_one_line_summary(text: str) -> bool:
    """意味が空・長文・見出し風の場合は要約が必要."""
    value = str(text or "").strip()
    if not value:
        return True
    if "\n" in value or len(value) > 120 or value.startswith("=="):
        return True
    return False


async def _meaning_from_wiktionary(scraper: WiktionaryScraper, term: str) -> str | None:
    data = await scraper.scrape(term)
    if not isinstance(data, dict) or data.get("error"):
        return None
    definitions = data.get("definitions")
    if isinstance(definitions, list):
        for item in definitions:
            if not isinstance(item, dict):
                continue
            meaning_ja = clean_line(str(item.get("meaning_ja", "")).strip())
            if meaning_ja:
                return meaning_ja
            meaning_en = clean_line(str(item.get("meaning_en", "")).strip())
            if meaning_en:
                return meaning_en
    summary = clean_line(str(data.get("summary", "")).strip())
    return summary or None


def _meaning_from_wordnet(term: str) -> str | None:
    snapshot = get_wordnet_snapshot(term)
    entries = snapshot.get("entries", [])
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        definition = clean_line(entry.get("definition", ""))
        if definition:
            return definition
    return None


def _hits_text(hits: list[dict]) -> str:
    lines: list[str] = []
    for hit in hits[:8]:
        title = clean_line(hit.get("title", ""), max_len=120)
        body = clean_line(hit.get("body", ""), max_len=220)
        href = clean_line(hit.get("href", ""), max_len=220)
        if title or body:
            lines.append(f"- title: {title}\n  body: {body}\n  url: {href}")
    return "\n".join(lines)


def _meaning_from_hits_with_gpt_ja(term: str, source: str, hits: list[dict]) -> str | None:
    """検索スニペットから GPT で日本語の短い意味を1行得る."""
    if not hits:
        return None
    if not settings.openai_api_key:
        for hit in hits:
            body = clean_line(hit.get("body", ""))
            if body:
                return body
            title = clean_line(hit.get("title", ""))
            if title:
                return title
        return None
    prompt = (
        "あなたは簡潔な辞書編集者です。\n"
        "英語表現の検索スニペットを元に、その表現の意味を日本語で1行だけ返してください。\n"
        "ルール:\n"
        "- 意味の文だけを出力（マークダウン・箇条書き・出典名は不要）\n"
        "- 最大30文字程度\n"
        "- 不明な場合は空文字を返す"
    )
    user_input = (
        f"表現: {term}\n"
        f"出典: {source}\n"
        f"スニペット:\n{_hits_text(hits)}"
    )
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
        )
        return clean_line(completion.output_text or "", max_len=220) or None
    except Exception:
        return None


def _summarize_one_line_ja(term: str, candidates: list[str]) -> str | None:
    """複数の候補（英語・日本語混在可）を GPT で日本語1行に要約する."""
    cleaned = [clean_line(x, max_len=260) for x in candidates if clean_line(x, max_len=260)]
    if not cleaned:
        return None
    if not settings.openai_api_key:
        return clean_line(cleaned[0], max_len=120) or None
    prompt = (
        "辞書の証拠を日本語で1行の意味に要約してください。\n"
        "ルール:\n"
        "- 1行のみ\n"
        "- マークダウン・箇条書き・引用符なし\n"
        "- 最大40文字程度\n"
        "- 証拠が不十分な場合は空文字を返す"
    )
    evidence = "\n".join(f"- {item}" for item in cleaned[:8])
    user_input = f"表現: {term}\n証拠:\n{evidence}"
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_input},
            ],
        )
        summarized = clean_line(completion.output_text or "", max_len=120)
        return summarized or None
    except Exception:
        return clean_line(cleaned[0], max_len=120) or None


def _meaning_from_web_dictionary(term: str) -> str | None:
    global _WEB_DICT_UNAVAILABLE
    if _WEB_DICT_UNAVAILABLE:
        return None
    result = search_web_dictionary([term], max_results_per_query=6)
    hits = result.get("hits", []) if isinstance(result, dict) else []
    if not isinstance(hits, list) or not hits:
        _WEB_DICT_UNAVAILABLE = True
        return None
    return _meaning_from_hits_with_gpt_ja(term, "dictionary", hits)


def _meaning_from_web_general(term: str) -> str | None:
    global _WEB_GENERAL_UNAVAILABLE
    if _WEB_GENERAL_UNAVAILABLE:
        return None
    result = search_web_general([f"{term} meaning"], max_results_per_query=6)
    hits = result.get("hits", []) if isinstance(result, dict) else []
    if not isinstance(hits, list) or not hits:
        _WEB_GENERAL_UNAVAILABLE = True
        return None
    return _meaning_from_hits_with_gpt_ja(term, "general", hits)


async def resolve_meaning_ja(
    term: str,
    scraper: WiktionaryScraper,
    cache: dict[str, str | None],
    seed_candidates: list[str] | None = None,
) -> str | None:
    """
    Wiktionary → WordNet → Web辞書 → Web汎用 の順で候補を集め、
    GPT で日本語1行に要約して返す。キャッシュ付き。
    """
    key = term.strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]
    candidates: list[str] = []
    for seed in seed_candidates or []:
        c = clean_line(seed, max_len=260)
        if c:
            candidates.append(c)
    wiktionary = await _meaning_from_wiktionary(scraper, term)
    if wiktionary:
        candidates.append(wiktionary)
    wordnet = _meaning_from_wordnet(term)
    if wordnet:
        candidates.append(wordnet)
    web_dict = _meaning_from_web_dictionary(term)
    if web_dict:
        candidates.append(web_dict)
    web_general = _meaning_from_web_general(term)
    if web_general:
        candidates.append(web_general)
    meaning = _summarize_one_line_ja(term, candidates)
    cache[key] = meaning
    return meaning


def resolve_meaning_ja_ddgs(
    term: str,
    cache: dict[str, str | None],
    seed_candidates: list[str] | None = None,
) -> str | None:
    """ddgs(Web辞書/汎用)由来の候補だけで日本語1行意味を返す。"""
    key = term.strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]
    candidates: list[str] = []
    for seed in seed_candidates or []:
        cleaned = clean_line(seed, max_len=260)
        if cleaned:
            candidates.append(cleaned)
    web_dict = _meaning_from_web_dictionary(term)
    if web_dict:
        candidates.append(web_dict)
    web_general = _meaning_from_web_general(term)
    if web_general:
        candidates.append(web_general)
    meaning = _summarize_one_line_ja(term, candidates)
    cache[key] = meaning
    return meaning
