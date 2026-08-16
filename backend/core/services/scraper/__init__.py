from core.services.scraper.eijiro import EijiroScraper
from core.services.scraper.etymonline import EtymonlineScraper
from core.services.scraper.weblio import WeblioScraper
from core.services.scraper.wiktionary import WiktionaryScraper


def build_scrapers() -> list:
    return [
        EtymonlineScraper(),
        WiktionaryScraper(),
        WeblioScraper(),
        EijiroScraper(),
    ]
