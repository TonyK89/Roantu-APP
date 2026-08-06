"""
Register značiek. Pridanie novej značky = nový riadok tu + nový súbor
v scrapers/<brand>.py s triedou dedenou z BrandScraper.

Značky bez implementácie (VW, Audi, BMW, Seat, Hyundai...) sú vypísané
nižšie ako TODO - pilot je zatiaľ len Škoda, aby sme si overili prístup
na živých dátach skôr, než sa rozbehne práca na ďalších piatich weboch,
z ktorých každý bude mať inú štruktúru.
"""
from scrapers.skoda import SkodaScraper
from scrapers.hyundai import HyundaiScraper
from scrapers.hyundai_stock import HyundaiStockScraper
from scrapers.vw import VwScraper

BRANDS = {
    "skoda": SkodaScraper,
    "hyundai": HyundaiScraper,
    "hyundai-stock": HyundaiStockScraper,  # reálne skladové vozidlá, celá sieť predajcov
    "vw": VwScraper,
    # "audi-stock": AudiStockScraper,  # TODO - skladove-vozidla.audi.sk, rovnaký prístup, over noindex signál
    # "audi": AudiScraper,    # TODO - audi.sk je JS-SPA, potrebuje Playwright
    # "seat": SeatScraper,    # TODO
    # "bmw": BmwScraper,      # TODO
}
