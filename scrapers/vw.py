"""
Scraper pre www.vw.sk (Volkswagen Slovensko, importér Porsche Slovakia s.r.o.).

Na rozdiel od Audi/SEAT (rovnaký koncern, ale JS-SPA konfigurátor cez
groupcms-services-api.porsche-holding.com) je hlavná stránka modelu na
vw.sk SERVER-RENDERED a obsahuje úvodnú cenu priamo v texte
("Golf už od 20 990 €"). Technické parametre motorov sú ale na
samostatnej podstránke /<model>/<model>/motory, ktorú som NEOVERIL
štruktúrou (na rozdiel od Škody) - preto ju scraper skúša naparsovať
rovnakým "label→value" parserom ako Škoda, ale ak sa nič nenájde,
jednoducho vráti prázdny zoznam motorov bez zlyhania.

DÔLEŽITÉ - over pred prvým ostrým behom:
1) Skontroluj cenu 1-2 modelov voči tomu, čo vidíš v prehliadači.
2) Skontroluj, či /motory podstránka vôbec obsahuje parsovateľné
   "Prevodovka"/"Druh paliva" popisky - ak nie, uprav
   common/text_utils.py::LABELS alebo napíš VW-špecifický parser.
"""
import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.models import Model
from common.text_utils import parse_engines_from_text, parse_first_starting_price
from scrapers.base import BrandScraper

OVERVIEW_URL = "https://www.vw.sk/modely"


class VwScraper(BrandScraper):
    brand = "vw"
    base_url = "https://www.vw.sk"

    def list_model_urls(self) -> List[str]:
        resp = self.get(OVERVIEW_URL)
        soup = BeautifulSoup(resp.text, "html.parser")

        urls = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Modelové stránky majú tvar /<model>/<model>, napr. /golf/golf
            parts = href.strip("/").split("/")
            if len(parts) == 2 and parts[0] == parts[1] and href.startswith("/"):
                urls.add(urljoin(self.base_url, href))
        return sorted(urls)

    def parse_model(self, url: str) -> Model:
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        full_text = soup.get_text(separator="\n")

        h1 = soup.find("h1")
        name = h1.get_text(strip=True) if h1 else url.rstrip("/").split("/")[-1]

        model = Model(name=name, url=url, brand=self.brand)
        model.price_from_eur = parse_first_starting_price(full_text)

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            model.image_url = og_image["content"]

        conf = soup.find("a", string=re.compile("Konfigurátor", re.I))
        if conf and conf.get("href"):
            model.configurator_url = conf["href"]

        cenniky = soup.find("a", string=re.compile(r"Cenn[íi]ky a katal[óo]gy", re.I))
        if cenniky and cenniky.get("href"):
            model.price_list_pdf = urljoin(self.base_url, cenniky["href"])  # stránka s PDF, nie priamo PDF

        # Skús podstránku /motory - NEVERIFIKOVANÉ, môže vrátiť prázdno
        motory_link = soup.find("a", string=re.compile(r"^\s*Motory\s*$", re.I))
        if motory_link and motory_link.get("href"):
            try:
                motory_url = urljoin(self.base_url, motory_link["href"])
                motory_resp = self.get(motory_url)
                motory_soup = BeautifulSoup(motory_resp.text, "html.parser")
                model.engines = parse_engines_from_text(motory_soup.get_text(separator="\n"))
            except Exception:
                model.engines = []  # nezlyhaj celý model pre jednu podstránku

        return model
