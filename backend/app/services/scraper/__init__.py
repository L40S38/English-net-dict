from app.services.scraper.eijiro import EijiroScraper
from app.services.scraper.etymonline import EtymonlineScraper
from app.services.scraper.weblio import WeblioScraper
from app.services.scraper.wiktionary import WiktionaryScraper


def build_scrapers() -> list:
    return [
        EtymonlineScraper(),
        WiktionaryScraper(),
        WeblioScraper(),
        EijiroScraper(),
    ]
