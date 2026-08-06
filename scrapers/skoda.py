"""
Scraper pre www.skoda-auto.sk.

Zdroj zoznamu modelov: https://www.skoda-auto.sk/modely/prehlad
Každý model má vlastnú stránku s HTML-natívnymi technickými parametrami
(sekcia "Motory") a linkami na PDF cenník / technické údaje.

DÔLEŽITÉ - over pred prvým ostrým behom:
Táto stránka je server-rendered (nie SPA za JS), takže `requests` by mal
stačiť bez potreby Playwright/Selenium. Ak sa po nasadení ukáže, že
`soup.get_text()` nevracia očakávané labely (Najvyššia rýchlosť,
Prevodovka...), stránka mohla zmeniť štruktúru - over si to manuálne
cez "View Page Source" a uprav common/text_utils.py::LABELS.
"""
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.models import Model
from common.text_utils import parse_engines_from_text, parse_trims_from_text
from scrapers.base import BrandScraper

OVERVIEW_URL = "https://www.skoda-auto.sk/modely/prehlad"


class SkodaScraper(BrandScraper):
    brand = "skoda"
    base_url = "https://www.skoda-auto.sk"

    def list_model_urls(self) -> List[str]:
        resp = self.get(OVERVIEW_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/modely/" in href and href.rstrip("/").count("/") >= 3:
                if href.endswith("/prehlad"):
                    continue
                urls.add(urljoin(self.base_url, href))
        return sorted(urls)

    def parse_model(self, url: str) -> Model:
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        h1 = soup.find("h1")
        name = h1.get_text(strip=True) if h1 else url.rstrip("/").split("/")[-1]

        model = Model(name=name, url=url, brand=self.brand)

        # PDF linky (cenník / technické údaje)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf"):
                low = href.lower()
                if "cennik" in low and not model.price_list_pdf:
                    model.price_list_pdf = href
                elif ("technicke" in low or "udaje" in low) and not model.technical_data_pdf:
                    model.technical_data_pdf = href

        # Konfigurátor
        conf = soup.find("a", string=re.compile("Konfigurátor", re.I))
        if conf and conf.get("href"):
            model.configurator_url = conf["href"]

        # OG image ako náhľadový obrázok modelu
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            model.image_url = og_image["content"]

        full_text = soup.get_text(separator="\n")
        model.engines = parse_engines_from_text(full_text)
        model.trims = parse_trims_from_text(full_text)

        return model
