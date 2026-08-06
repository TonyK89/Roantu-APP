"""
Scraper pre skladove.hyundai.sk - centrálny sklad AGREGOVANÝ za celú
sieť predajcov Hyundai na Slovensku (nie katalóg výrobcu, nie jeden
predajca). Každé vozidlo má konkrétnu cenu, km, VIN a konkrétneho
predajcu.

Toto je SAMOSTATNÝ scraper od scrapers/hyundai.py (katalógový) -
obidva zostávajú k dispozícii, pretože reprezentujú iný typ dát.

Postup:
1) list_model_urls() prejde stránkovanie /ponuky?strona=N&na-strone=24
   a vyzbiera URL adresy detailu KAŽDÉHO vozidla.
2) parse_model(url) stiahne detail a vráti StockVehicle so všetkými
   dostupnými poľami.

DÔLEŽITÉ - over pred prvým ostrým behom:
- Celý sklad má aktuálne cca 636-648 vozidiel = cca 27 strán listingu +
  636 detailových requestov = cca 660 HTTP requestov na jeden bežný.
  Pri hodinovom behu to znamená byť ohľaduplný (throttling), nie
  spúšťať to paralelne na desiatkach vlákien.
- Over cenu/km na 2-3 vozidlách voči tomu, čo vidíš v prehliadači.
"""
import re
import time
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.models import StockVehicle
from common.stock_text_utils import (
    parse_stock_specs, parse_stock_price, parse_location,
    parse_dealer_name, parse_dealer_email,
)
from scrapers.base import BrandScraper

LISTING_URL = "https://skladove.hyundai.sk/ponuky"
PAGE_SIZE = 24
MAX_PAGES_SAFETY = 60  # poistka proti nekonečnej slučke, ak by sa počet zmenil

# /ponuka/hyundai-<model-slug>/<id>
DETAIL_URL_RE = re.compile(r"/ponuka/hyundai-[a-z0-9-]+/(\d+)")


class HyundaiStockScraper(BrandScraper):
    brand = "hyundai"
    base_url = "https://skladove.hyundai.sk"
    output_kind = "stock"

    # Buď ohľaduplný k cudziemu serveru - malá pauza medzi requestami
    request_delay_s = 0.3

    def list_model_urls(self) -> List[str]:
        urls = set()
        for page in range(1, MAX_PAGES_SAFETY + 1):
            page_url = f"{LISTING_URL}?strona={page}&na-strone={PAGE_SIZE}"
            resp = self.get(page_url)
            soup = BeautifulSoup(resp.text, "html.parser")

            found_this_page = set()
            for a in soup.find_all("a", href=True):
                if DETAIL_URL_RE.search(a["href"]):
                    found_this_page.add(urljoin(self.base_url, a["href"]))

            if not found_this_page:
                break  # posledná strana bola prázdna, koniec

            new_ones = found_this_page - urls
            urls |= found_this_page
            if not new_ones:
                break  # stránkovanie sa začalo opakovať, koniec

            time.sleep(self.request_delay_s)

        return sorted(urls)

    def parse_model(self, url: str) -> Optional[StockVehicle]:
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        full_text = soup.get_text(separator="\n")

        m = DETAIL_URL_RE.search(url)
        external_id = m.group(1) if m else url.rstrip("/").split("/")[-1]

        h1 = soup.find("h1")
        model_name = h1.get_text(strip=True) if h1 else ""
        model_name = re.sub(r"^Hyundai\s+", "", model_name, flags=re.I).strip()

        h2 = soup.find("h2")
        variant = h2.get_text(strip=True) if h2 else None

        status = "NOVÉ" if "NOVÉ" in full_text else None
        is_promo = "Akciová ponuka" in full_text

        specs = parse_stock_specs(full_text)
        price = parse_stock_price(full_text)

        images = []
        for img in soup.select("img[src*='/media/']"):
            src = img.get("src")
            if src and src not in images:
                images.append(urljoin(self.base_url, src))

        vehicle = StockVehicle(
            external_id=external_id,
            brand=self.brand,
            model=model_name,
            variant=variant,
            url=url,
            status=status,
            is_promo=is_promo,
            location_city=parse_location(full_text),
            dealer_name=parse_dealer_name(full_text),
            dealer_email=parse_dealer_email(full_text),
            images=images,
            **specs,
            **price,
        )
        time.sleep(self.request_delay_s)
        return vehicle
