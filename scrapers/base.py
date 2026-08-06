"""
Základ pre scraper jednej značky. Nová značka = nová trieda dedená z
BrandScraper, ktorá implementuje list_model_urls() a parse_model().
Pozri scrapers/skoda.py ako referenčnú implementáciu.
"""
from abc import ABC, abstractmethod
from typing import List
import requests

from common.models import Model

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RoantyFeedBot/1.0; +https://roanty.sk/o-nas/bot)"
}
DEFAULT_TIMEOUT = 20


class BrandScraper(ABC):
    brand: str = ""
    base_url: str = ""
    output_kind: str = "catalog"  # "catalog" (Model) alebo "stock" (StockVehicle)

    def __init__(self, session: requests.Session = None):
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str) -> requests.Response:
        resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp

    @abstractmethod
    def list_model_urls(self) -> List[str]:
        """Vráti zoznam URL adries jednotlivých modelov na scrapovanie."""
        raise NotImplementedError

    @abstractmethod
    def parse_model(self, url: str) -> Model:
        """Stiahne a rozparsuje jednu stránku modelu do Model objektu."""
        raise NotImplementedError

    def scrape_all(self, include: List[str] = None, exclude: List[str] = None) -> List:
        urls = self.list_model_urls()
        items = []
        for url in urls:
            item = self.parse_model(url)
            if item is None:
                continue
            label = getattr(item, "name", None) or getattr(item, "model", None)
            if include and label not in include:
                continue
            if exclude and label in exclude:
                continue
            if not getattr(item, "brand", None):
                item.brand = self.brand
            items.append(item)
        return items
