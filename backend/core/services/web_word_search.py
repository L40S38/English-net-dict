"""Web search via DuckDuckGo (ddgs).

Provides two interfaces for the chat tool system:
  - search_web_dictionary: dictionary/etymology-focused searches
  - search_web_general:    broad web searches
"""

from __future__ import annotations

import logging
from typing import Any

from ddgs import DDGS

logger = logging.getLogger(__name__)

_REFERENCE_SITES: list[dict[str, str]] = [
    {"name": "OneLook", "url": "https://onelook.com/?w=*{q}*"},
    {"name": "Wiktionary", "url": "https://en.wiktionary.org/w/index.php?search={q}"},
    {"name": "Merriam-Webster", "url": "https://www.merriam-webster.com/dictionary/{q}"},
    {"name": "Dictionary.com", "url": "https://www.dictionary.com/browse/{q}"},
    {"name": "Cambridge Dictionary", "url": "https://dictionary.cambridge.org/search/english/?q={q}"},
    {"name": "WordHippo", "url": "https://www.wordhippo.com/what-is/the-meaning-of-the-word/{q}.html"},
    {"name": "Vocabulary.com", "url": "https://www.vocabulary.com/dictionary/{q}"},
    {"name": "TheFreeDictionary", "url": "https://www.thefreedictionary.com/{q}"},
    {"name": "Collins", "url": "https://www.collinsdictionary.com/search/?dictCode=english&q={q}"},
    {"name": "Datamuse", "url": "https://api.datamuse.com/words?sp=*{q}*&max=30"},
]


def _build_reference_urls(query: str) -> list[dict[str, str]]:
    q = query.strip().replace(" ", "+")
    return [{"name": s["name"], "url": s["url"].format(q=q)} for s in _REFERENCE_SITES]


def _run_ddgs(query: str, max_results: int = 8) -> list[dict[str, str]]:
    try:
        ddgs = DDGS()
        raw = ddgs.text(query, max_results=max_results)
        return [
            {"title": r.get("title", ""), "body": r.get("body", ""), "href": r.get("href", "")}
            for r in raw
        ]
    except Exception:
        logger.warning("DuckDuckGo query failed: %s", query, exc_info=True)
        return []


def search_web_dictionary(
    queries: list[str],
    max_results_per_query: int = 8,
) -> list[dict[str, Any]]:
    """Dictionary / etymology focused web search.

    Appends dictionary-site keywords to each query for better results.
    Returns a list of search result dicts with title, body, href, and reference_urls.
    """
    all_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for query in queries[:3]:
        dict_query = f"{query} English dictionary etymology meaning"
        hits = _run_ddgs(dict_query, max_results=max_results_per_query)
        for hit in hits:
            url = hit.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(hit)

    first_query = queries[0] if queries else ""
    return {
        "hits": all_results[:20],
        "reference_urls": _build_reference_urls(first_query),
        "query_count": len(queries),
    }


def search_web_general(
    queries: list[str],
    max_results_per_query: int = 8,
) -> list[dict[str, Any]]:
    """Broad web search via DuckDuckGo.

    Queries are used as-is without modification.
    """
    all_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for query in queries[:3]:
        hits = _run_ddgs(query, max_results=max_results_per_query)
        for hit in hits:
            url = hit.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(hit)

    return {
        "hits": all_results[:20],
        "query_count": len(queries),
    }
