from urllib.parse import quote

from core.services.scraper.base import BaseScraper


class EijiroScraper(BaseScraper):
    source_name = "eijiro"

    async def scrape(self, word: str) -> dict:
        url = f"https://eow.alc.co.jp/search?q={quote(word)}"
        try:
            html = await self.fetch_html(url)
            return {"source": self.source_name, "url": url, "summary": self.compact_text(html)}
        except Exception as exc:  # noqa: BLE001
            return {"source": self.source_name, "url": url, "error": str(exc)}
