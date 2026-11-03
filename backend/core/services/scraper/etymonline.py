from urllib.parse import quote

from core.services.scraper.base import BaseScraper


class EtymonlineScraper(BaseScraper):
    source_name = "etymonline"

    async def scrape(self, word: str) -> dict:
        url = f"https://www.etymonline.com/word/{quote(word)}"
        try:
            html = await self.fetch_html(url)
            return {"source": self.source_name, "url": url, "summary": self.compact_text(html)}
        except Exception as exc:  # noqa: BLE001
            return {"source": self.source_name, "url": url, "error": str(exc)}
