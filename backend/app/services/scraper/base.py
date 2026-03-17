from __future__ import annotations

from abc import ABC, abstractmethod

import httpx
from bs4 import BeautifulSoup


class BaseScraper(ABC):
    source_name: str = "base"

    async def fetch_html(self, url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            return res.text

    @staticmethod
    def compact_text(html: str, max_chars: int = 1400) -> str:
        soup = BeautifulSoup(html, "html.parser")
        text = " ".join(soup.get_text(" ", strip=True).split())
        return text[:max_chars]

    @abstractmethod
    async def scrape(self, word: str) -> dict:
        raise NotImplementedError
