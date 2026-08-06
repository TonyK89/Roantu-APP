"""
Scraper pre www.hyundai.com/sk/sk/ (Hyundai Slovensko).

Na rozdiel od Škody tu má KAŽDÁ úroveň výbavy svoju REÁLNU cenu priamo
v HTML (stránka .../modely/<model>/vybavy.html), nie len v PDF. To robí
z Hyundai lepšieho kandidáta na feed s cenami ako Škodu/Audi.

DÔLEŽITÉ - over pred prvým ostrým behom:
Ceny a mená výbav som overil na fixture z reálnej stránky i20 (pozri
fixtures/hyundai_i20_vybavy_sample.txt a tests/test_hyundai_parser.py).
Fixture je ale ručne vyčistená verzia HTML->text konverzie, ktorú som
dostal cez fetch nástroj - skutočný `soup.get_text()` z živého requests
behu sa môže v drobnostiach (medzery, poradie) líšiť. Over prvý výstup
na 2-3 modeloch manuálne (skontroluj cenu voči tomu, čo vidíš v
prehliadači) skôr, než sa na feed spolieha produkcia.
"""
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.models import Model
from common.text_utils import parse_variants_from_text, parse_starting_price
from scrapers.base import BrandScraper

OVERVIEW_URL = "https://www.hyundai.com/sk/sk/modely.html"

# Kategórie/rozbočovače, ktoré nie sú konkrétny model a treba ich vynechať
NON_MODEL_SLUGS = {
    "male-kompaktne", "suv", "hybridne", "elektricke", "sportove",
    "vsetky-modely", "e-mobilita",
}


class HyundaiScraper(BrandScraper):
    brand = "hyundai"
    base_url = "https://www.hyundai.com"

    def list_model_urls(self) -> List[str]:
        resp = self.get(OVERVIEW_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/sk/sk/modely/" not in href or not href.endswith(".html"):
                continue
            slug = href.rstrip("/").split("/")[-1].replace(".html", "")
            if slug in NON_MODEL_SLUGS:
                continue
            urls.add(urljoin(self.base_url, href))
        return sorted(urls)

    def parse_model(self, url: str) -> Model:
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        full_text = soup.get_text(separator="\n")

        h1 = soup.find("h1")
        name = h1.get_text(strip=True).rstrip(".") if h1 else url.rstrip("/").split("/")[-1]

        model = Model(name=name, url=url, brand=self.brand)
        model.price_from_eur = parse_starting_price(full_text)

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            model.image_url = og_image["content"]

        # Konfigurátor
        conf = soup.find("a", string=re.compile("Konfigurátor", re.I))
        if conf and conf.get("href"):
            model.configurator_url = urljoin(self.base_url, conf["href"])

        # Nájdi link na podstránku "Úrovne výbavy" a stiahni z nej varianty s cenou
        vybavy_link = soup.find("a", string=re.compile(r"^\s*Úrovne výbavy\s*$", re.I))
        if vybavy_link and vybavy_link.get("href"):
            vybavy_url = urljoin(self.base_url, vybavy_link["href"])
            vybavy_resp = self.get(vybavy_url)
            vybavy_soup = BeautifulSoup(vybavy_resp.text, "html.parser")
            model.variants = parse_variants_from_text(vybavy_soup.get_text(separator="\n"))

        # Link na cenníky a katalógy (PDF), ak existuje - doplnkový zdroj
        doc_link = soup.find("a", string=re.compile(r"Cenníky a katal[óo]gy", re.I))
        if doc_link and doc_link.get("href"):
            model.price_list_pdf = urljoin(self.base_url, doc_link["href"])  # odkaz na stránku, nie priamo PDF

        return model
