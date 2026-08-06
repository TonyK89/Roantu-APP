"""
Generický scraper skladových vozidiel riadený konfiguráciou (configs/<brand>.json).

Namiesto písania novej Python triedy pre každú značku (ako scrapers/hyundai_stock.py)
stačí popísať štruktúru stránky v JSON configu - viď configs/_SCHEMA_DOCUMENTATION.json.

Použitie:
    python -m generic.config_scraper --config configs/hyundai_stock.json --output output

Podporované metódy extrakcie polí (field["method"]):
    - label_next_line: nájde riadok s presným textom labelu, vezme hodnotu
      z nasledujúceho riadku (funguje na "Popisok\\nHodnota" štýl stránok)
    - regex: aplikuje regulárny výraz na celý text; pri viacerých skupinách
      a "compute" vie spočítať odvodenú hodnotu (napr. cena = pôvodná - zľava)
    - meta_tag: vytiahne hodnotu z <meta property="..."> alebo <meta name="...">
"""
import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from common.stock_xml_builder import build_stock_cars_xml_generic
from generic.image_cache import cache_all_images

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RoantyFeedBot/1.0; +https://roanty.sk/o-nas/bot)"
}
TIMEOUT = 20
REQUEST_DELAY_S = 0.3

# Neviditeľné formátovacie znaky (LRM, RLM, zero-width space/joiner...), ktoré
# sa občas objavia v cenách/textoch (typicky z CSS/JS "smart" formátovania
# čísel) a rozbíjajú regexy, lebo NIE SÚ súčasťou \s. Odstránime ich pred
# akoukoľvek extrakciou.
_INVISIBLE_CHARS_RE = re.compile("[\u200b\u200c\u200d\u200e\u200f\ufeff]")


def clean_text(text: str) -> str:
    return _INVISIBLE_CHARS_RE.sub("", text)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch(url: str, session: requests.Session) -> BeautifulSoup:
    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def discover_detail_urls(config: dict, session: requests.Session) -> List[str]:
    listing = config["listing"]
    style = listing.get("pagination_style", "query_param")

    if style == "cumulative_size":
        return _discover_cumulative_size(config, session)
    return _discover_query_param(config, session)


def _discover_query_param(config: dict, session: requests.Session) -> List[str]:
    """Štýl 'strona=1,2,3...' (napr. Hyundai sklad)."""
    listing = config["listing"]
    base_url = listing["base_url"]
    pattern = re.compile(listing["detail_url_regex"])
    page_param = listing.get("page_param")
    page_size_param = listing.get("page_size_param")
    page_size = listing.get("page_size", 24)
    max_pages = listing.get("max_pages_safety", 60)

    urls = set()
    for page in range(listing.get("start_page", 1), max_pages + 1):
        if page_param:
            sep = "&" if "?" in base_url else "?"
            page_url = f"{base_url}{sep}{page_param}={page}"
            if page_size_param:
                page_url += f"&{page_size_param}={page_size}"
        else:
            page_url = base_url  # jednostránkový zoznam

        soup = fetch(page_url, session)
        found_this_page = set()
        for a in soup.find_all("a", href=True):
            if pattern.search(a["href"]):
                found_this_page.add(urljoin(base_url, a["href"]))

        if not found_this_page:
            break
        new_ones = found_this_page - urls
        urls |= found_this_page
        if not new_ones or not page_param:
            break
        time.sleep(REQUEST_DELAY_S)

    return sorted(urls)


def _discover_cumulative_size(config: dict, session: requests.Session) -> List[str]:
    """
    Štýl 'Načítať viac vozidiel' (napr. Audi/VW/SEAT sklad - Porsche Informatik
    platforma), kde sa vždy dotiahne PRVÝCH N vozidiel (?size=24, potom
    ?size=48, ?size=72...), nie stránka po stránke. Zastaví sa, keď sa
    počet nájdených URL medzi dvomi behmi prestane zväčšovať.
    """
    listing = config["listing"]
    base_url = listing["base_url"]
    pattern = re.compile(listing["detail_url_regex"])
    size_param = listing.get("size_param", "size")
    size_step = listing.get("size_step", 24)
    max_size = listing.get("max_size_safety", 2000)

    urls: set = set()
    previous_count = -1
    current_size = size_step

    while current_size <= max_size:
        sep = "&" if "?" in base_url else "?"
        page_url = f"{base_url}{sep}{size_param}={current_size}"
        soup = fetch(page_url, session)

        found = set()
        for a in soup.find_all("a", href=True):
            if pattern.search(a["href"]):
                found.add(urljoin(base_url, a["href"]))

        if len(found) <= previous_count:
            break  # ďalšie zväčšenie size nepridalo nové vozidlá - koniec zoznamu
        previous_count = len(found)
        urls = found
        current_size += size_step
        time.sleep(REQUEST_DELAY_S)

    return sorted(urls)


def _parse_number(raw: str, type_: str):
    """
    Slovenské/európske weby používajú NIEKOĽKO rôznych formátov čísel:
      - "35 530"       (Hyundai sklad: medzera ako tisícový oddeľovač, bez desatín)
      - "33.518,99"    (Audi/VW sklad: bodka = tisícový oddeľovač, čiarka = desatinná)
      - "5,7"          (spotreba paliva: čiarka = desatinná, žiadny tisícový oddeľovač)
    Pravidlo: ak je v čísle čiarka, VŽDY je to desatinný oddeľovač (posledná
    čiarka delí celú a desatinnú časť) a všetky bodky/medzery pred ňou sú
    tisícový oddeľovač, ktorý sa odstráni. Ak čiarka nie je, bodky aj medzery
    sa berú ako tisícový oddeľovač (v tejto doméne - ceny/km/kW/cm3 - sa čísla
    bez čiarky prakticky vždy myslia ako celé, nie desatinné).
    """
    raw = raw.strip().replace("\xa0", "")
    m = re.search(r"-?[\d.,\s]+", raw)
    if not m:
        return None
    num_str = m.group().strip()

    if "," in num_str:
        int_part, _, dec_part = num_str.rpartition(",")
        int_part = int_part.replace(".", "").replace(" ", "")
        dec_part = re.sub(r"\D", "", dec_part)  # "26.900,-" -> dec_part "" (pomlčka nie je číslica)
        if not dec_part:
            dec_part = "0"
        num_str = f"{int_part}.{dec_part}"
    else:
        num_str = num_str.replace(".", "").replace(" ", "")

    try:
        val = float(num_str)
    except ValueError:
        return None
    return int(val) if type_ == "int" else val


def extract_label_next_line(full_text: str, label: str) -> Optional[str]:
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if line == label and i + 1 < len(lines):
            return lines[i + 1]
    return None


def extract_field(field_cfg: dict, full_text: str, soup: BeautifulSoup, base_url: str = "") -> Dict[str, Any]:
    method = field_cfg["method"]
    tag = field_cfg["tag"]
    type_ = field_cfg.get("type", "string")

    if method == "label_next_line":
        raw = extract_label_next_line(full_text, field_cfg["label"])
        if raw is None:
            return {tag: None}
        value = _parse_number(raw, type_) if type_ in ("int", "float") else raw
        return {tag: value}

    if method == "regex":
        m = re.search(field_cfg["pattern"], full_text)
        if not m:
            return {tag: None}
        groups = field_cfg.get("groups")
        if groups:
            values = {}
            for i, gname in enumerate(groups, start=1):
                values[gname] = _parse_number(m.group(i), "float")
            if "compute" in field_cfg:
                try:
                    result = eval(field_cfg["compute"], {}, values)  # noqa: S307 - config je dôveryhodný, nie užívateľský vstup
                except Exception:
                    result = None
                return {tag: result}
            return values
        raw = m.group(1) if m.groups() else m.group(0)
        value = _parse_number(raw, type_) if type_ in ("int", "float") else raw
        return {tag: value}

    if method == "meta_tag":
        meta = soup.find("meta", attrs={"property": field_cfg.get("property")}) or \
               soup.find("meta", attrs={"name": field_cfg.get("name")})
        return {tag: meta.get("content") if meta else None}

    if method == "regex_findall":
        # zoznamové pole, napr. položky výbavy vypísané za sebou v texte
        matches = re.findall(field_cfg["pattern"], full_text)
        seen = []
        for m in matches:
            val = m.strip() if isinstance(m, str) else m
            if val and val not in seen:
                seen.append(val)
        return {tag: seen}

    if method == "image_list":
        # nájde všetky <img> (alebo <a> s href na obrázok), zodpovedajúce vzoru v src/href,
        # zaradí len absolútne/verejné URL a odstráni duplicity
        css_selector = field_cfg.get("css_selector", "img")
        attr = field_cfg.get("attr", "src")
        src_contains = field_cfg.get("src_contains")  # napr. "/media/" - filter na relevantné obrázky

        urls = []
        for el in soup.select(css_selector):
            src = el.get(attr)
            if not src:
                continue
            if src_contains and src_contains not in src:
                continue
            absolute = urljoin(base_url, src)
            if absolute not in urls:
                urls.append(absolute)
        return {tag: urls}

    if method == "css_text":
        # presný výber elementu (napr. "h1") - spoľahlivejšie než regex, keď
        # je názov/titulok obklopený premenlivým marketingovým textom
        el = soup.select_one(field_cfg["css_selector"])
        if not el:
            return {tag: None}
        text = el.get_text(strip=True)
        return {tag: text if text else None}

    if method == "url_segment":
        # vytiahne časť ZO SAMOTNEJ URL vozidla (napr. ID na konci cesty),
        # nie z obsahu stránky
        m = re.search(field_cfg["pattern"], base_url)
        if not m:
            return {tag: None}
        return {tag: m.group(1) if m.groups() else m.group(0)}

    return {tag: None}


def validate_image_url(url: str, session: requests.Session, timeout: float = 8.0) -> Dict[str, Any]:
    """
    Overí, že obrázok je verejne dostupný BEZ prihlásenia/cookies zo session
    scrapera (nová, čistá session bez cookies scrapera) - presne to, čo urobí
    prehliadač návštevníka na roanty.sk, keď načíta feed.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "")
        ok = resp.status_code == 200 and content_type.startswith("image/")
        return {
            "url": url,
            "ok": ok,
            "status_code": resp.status_code,
            "content_type": content_type,
        }
    except requests.RequestException as e:
        return {"url": url, "ok": False, "error": str(e)}


def validate_all_images(vehicles: List[Dict[str, Any]], image_tags: List[str]) -> List[Dict[str, Any]]:
    """Prejde všetky obrázkové polia vo všetkých vozidlách a vráti zoznam problémov."""
    problems = []
    checked = set()
    for vehicle in vehicles:
        for tag in image_tags:
            urls = vehicle.get(tag) or []
            for url in urls:
                if url in checked:
                    continue
                checked.add(url)
                result = validate_image_url(url, requests.Session())
                if not result["ok"]:
                    problems.append(result)
    return problems


def parse_vehicle(url: str, config: dict, session: requests.Session) -> Dict[str, Any]:
    soup = fetch(url, session)
    full_text = clean_text(soup.get_text(separator="\n"))

    data: Dict[str, Any] = {"url": url}
    for field_cfg in config["fields"]:
        data.update(extract_field(field_cfg, full_text, soup, base_url=url))

    time.sleep(REQUEST_DELAY_S)
    return data


def run(config_path: str, output_dir: str, skip_image_check: bool = False) -> None:
    config = load_config(config_path)
    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"Objavujem URL adresy vozidiel z {config['listing']['base_url']} ...")
    urls = discover_detail_urls(config, session)
    print(f"Nájdených {len(urls)} vozidiel. Sťahujem detaily...")

    vehicles = []
    for i, url in enumerate(urls, 1):
        try:
            vehicles.append(parse_vehicle(url, config, session))
        except requests.RequestException as e:
            print(f"  [{i}/{len(urls)}] CHYBA pri {url}: {e}")
            continue
        if i % 25 == 0:
            print(f"  [{i}/{len(urls)}] spracovaných...")

    # Zoznamové polia (napr. obrázky, výbava) - vyžadujú "item_tag" v configu,
    # aby XML builder vedel, ako pomenovať jednotlivé <položky>
    list_item_tags = {
        f["tag"]: f["item_tag"] for f in config["fields"] if "item_tag" in f
    }
    image_tags = [f["tag"] for f in config["fields"] if f.get("method") == "image_list"]

    image_cache_cfg = config.get("image_cache")
    if image_tags and image_cache_cfg and image_cache_cfg.get("enabled"):
        print(f"Cachujem obrázky do {image_cache_cfg['cache_dir']} ...")
        vehicles, stats = cache_all_images(
            vehicles, image_tags,
            cache_dir=image_cache_cfg["cache_dir"],
            image_base_url=image_cache_cfg["image_base_url"],
        )
        print(f"  Cache: {stats['existing']} už existovalo, {stats['downloaded']} nových stiahnutých, "
              f"{stats['failed']} zlyhalo (nie sú vo feede).")
    elif image_tags and not skip_image_check:
        print(f"Overujem verejnú dostupnosť obrázkov ({', '.join(image_tags)})...")
        problems = validate_all_images(vehicles, image_tags)
        if problems:
            print(f"  UPOZORNENIE: {len(problems)} obrázkov nie je verejne dostupných:")
            for p in problems[:20]:
                reason = p.get("error") or f"HTTP {p.get('status_code')}, content-type={p.get('content_type')}"
                print(f"    - {p['url']}: {reason}")
            if len(problems) > 20:
                print(f"    ... a ďalších {len(problems) - 20}")
        else:
            print("  Všetky obrázky sú verejne dostupné.")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(output_dir) / f"{config['brand']}_feed.xml"
    xml_str = build_stock_cars_xml_generic(
        brand=config["brand"],
        source_url=config["source_url"],
        vehicles=vehicles,
        list_item_tags=list_item_tags,
    )
    out_path.write_text(xml_str, encoding="utf-8")
    print(f"Hotovo: {len(vehicles)} vozidiel -> {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generický config-driven scraper skladových vozidiel")
    parser.add_argument("--config", required=True, help="Cesta ku configs/<brand>.json")
    parser.add_argument("--output", default="output", help="Výstupný priečinok pre XML feed")
    parser.add_argument("--skip-image-check", action="store_true", help="Preskoč overovanie verejnej dostupnosti obrázkov (rýchlejšie, ale rizikovejšie)")
    args = parser.parse_args()
    run(args.config, args.output, skip_image_check=args.skip_image_check)
