from urllib.parse import quote

from core.services.scraper.base import BaseScraper


class WeblioScraper(BaseScraper):
    source_name = "weblio"

    async def scrape(self, word: str) -> dict:
        url = f"https://ejje.weblio.jp/content/{quote(word)}"
        try:
            html = await self.fetch_html(url)
            return {"source": self.source_name, "url": url, "summary": self.compact_text(html)}
        except Exception as exc:  # noqa: BLE001
            return {"source": self.source_name, "url": url, "error": str(exc)}
