#!/usr/bin/env python3
"""
Kontrola čitateľnosti stránky so skladovými vozidlami.

Použitie:
    python checker.py --brand "Škoda" --url "https://skoda-auto.sk/apps/stock/..."
    python checker.py --brand "VW" --url "https://skladove-vozidla.vw.sk/search?stock-cars=true"

Čo robí:
1) Skontroluje robots.txt danej domény - ak explicitne zakazuje prístup, hneď
   vráti BLOKOVANÉ a nič ďalej nesťahuje.
2) Stiahne cieľovú URL cez obyčajný `requests` (bez JavaScriptu - presne to,
   čo bude robiť aj samotný scraper na produkcii).
3) Vytiahne viditeľný text (bez <script>/<style>) a zmeria:
   - dĺžku viditeľného textu
   - počet nálezov typických áut-vzorov (€, kW, km, VIN-like reťazce)
4) Na základe toho vyhlási verdikt:
   - ČITATEĽNÉ: dosť textu aj auto-vzorov → dá sa scrapovať cez requests
   - JS-SPA (pravdepodobne): veľmi málo textu → obsah sa dopĺňa cez JavaScript,
     treba Playwright/headless prehliadač
   - NEISTÉ: text je, ale chýbajú typické auto-vzory → over ručne
   - BLOKOVANÉ: robots.txt zakazuje prístup

Tento nástroj nehovorí nič o tom, AKÉ polia sa dajú vytiahnuť - len ČI sa
dá stránka vôbec čítať bez prehliadača. Skutočné mapovanie polí rieši
generic/config_scraper.py podľa configs/<brand>.json.
"""
import argparse
import re
import sys
from urllib.parse import urlparse, urljoin
from urllib import robotparser

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RoantyFeedChecker/1.0; +https://roanty.sk/o-nas/bot)"
}
TIMEOUT = 20

# Prahové hodnoty - empiricky odladené na známych príkladoch (Škoda apps/stock
# ako JS-SPA s 0 signálmi, VW/Audi/Hyundai sklady ako čitateľné s desiatkami
# signálov). Počet auto-vzorov (€/kW/km/VIN) je silnejší signál než čistá
# dĺžka textu - krátka stránka s 5 autami môže mať menej textu než dlhá
# marketingová stránka bez jediného auta.
MIN_TEXT_LEN_SANITY = 300      # pod týmto je stránka prakticky prázdna
MIN_TEXT_LEN_READABLE = 800    # nad týmto už čakáme dosť obsahu na rozhodnutie
MIN_CAR_SIGNALS = 3

CAR_SIGNAL_PATTERNS = [
    re.compile(r"\d[\d\s]*€"),                      # cena, napr. "28 390 €"
    re.compile(r"\d+\s*kW", re.IGNORECASE),         # výkon
    re.compile(r"\d+\s*km\b", re.IGNORECASE),       # najazdené km
    re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),          # VIN (17 znakov, bez I/O/Q)
]


def check_robots(url: str) -> tuple[bool, str]:
    """Vráti (je_povolené, poznámka)."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as e:
        return True, f"robots.txt sa nepodarilo prečítať ({e}) - pokračujem opatrne"
    allowed = rp.can_fetch(HEADERS["User-Agent"], url)
    if not allowed:
        return False, f"robots.txt na {robots_url} explicitne zakazuje prístup na tento path"
    return True, f"robots.txt povoľuje ({robots_url})"


def analyze_html(html: str) -> dict:
    """Čistá analýza HTML textu - žiadny network, testovateľné na fixture."""
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    visible_text = soup.get_text(separator=" ", strip=True)
    text_len = len(visible_text)

    signal_counts = {}
    total_signals = 0
    for pattern in CAR_SIGNAL_PATTERNS:
        matches = pattern.findall(visible_text)
        signal_counts[pattern.pattern] = len(matches)
        total_signals += len(matches)

    return {
        "html_bytes": len(html),
        "visible_text_len": text_len,
        "signal_counts": signal_counts,
        "total_signals": total_signals,
        "sample_text": visible_text[:300],
    }


def analyze_page(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    result = analyze_html(resp.text)
    result["status_code"] = resp.status_code
    return result


def verdict(analysis: dict) -> str:
    text_len = analysis["visible_text_len"]
    signals = analysis["total_signals"]

    if text_len < MIN_TEXT_LEN_SANITY:
        return "JS-SPA (pravdepodobne)"
    if signals >= MIN_CAR_SIGNALS:
        return "ČITATEĽNÉ"
    if text_len >= MIN_TEXT_LEN_READABLE:
        return "NEISTÉ - žiadne auto-vzory v texte, over ručne"
    return "JS-SPA (pravdepodobne)"


def run_check(brand: str, url: str) -> dict:
    result = {"brand": brand, "url": url}

    allowed, robots_note = check_robots(url)
    result["robots_allowed"] = allowed
    result["robots_note"] = robots_note

    if not allowed:
        result["verdict"] = "BLOKOVANÉ"
        return result

    try:
        analysis = analyze_page(url)
    except requests.RequestException as e:
        result["verdict"] = "CHYBA"
        result["error"] = str(e)
        return result

    result.update(analysis)
    result["verdict"] = verdict(analysis)
    return result


def print_report(result: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"Značka:  {result['brand']}")
    print(f"URL:     {result['url']}")
    print(f"{'=' * 60}")
    print(f"robots.txt: {'POVOLENÉ' if result['robots_allowed'] else 'ZAKÁZANÉ'} - {result['robots_note']}")

    if result["verdict"] == "BLOKOVANÉ":
        print(f"\n>>> VERDIKT: {result['verdict']}")
        print("Táto stránka NEBUDE scrapovaná - robots.txt to explicitne zakazuje.")
        return

    if result["verdict"] == "CHYBA":
        print(f"\n>>> VERDIKT: CHYBA pri sťahovaní - {result.get('error')}")
        return

    print(f"Veľkosť HTML:        {result['html_bytes']:,} bajtov")
    print(f"Viditeľný text:      {result['visible_text_len']:,} znakov")
    print(f"Auto-vzory nájdené:  {result['total_signals']} (cena €, kW, km, VIN)")
    for pattern, count in result["signal_counts"].items():
        print(f"  - {pattern}: {count}")
    print(f"\nUkážka textu: {result['sample_text']}...")
    print(f"\n>>> VERDIKT: {result['verdict']}")

    if result["verdict"] == "ČITATEĽNÉ":
        print("Táto stránka sa dá scrapovať obyčajným requests+BeautifulSoup.")
        print("Ďalší krok: priprav configs/<brand>.json pre generic/config_scraper.py")
    elif "JS-SPA" in result["verdict"]:
        print("Obsah sa pravdepodobne dopĺňa cez JavaScript po načítaní stránky.")
        print("Obyčajný requests scraper tu nebude fungovať - potrebný Playwright.")
    else:
        print("Stránka má text, ale nenašli sa typické auto-údaje.")
        print("Over ručne v prehliadači, či je to naozaj stránka so zoznamom vozidiel.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kontrola čitateľnosti stránky so skladovými vozidlami")
    parser.add_argument("--brand", required=True, help="Názov značky, napr. 'Škoda'")
    parser.add_argument("--url", required=True, help="URL stránky so zoznamom skladových vozidiel")
    parser.add_argument("--json", action="store_true", help="Vypísať výsledok ako JSON namiesto textovej správy")
    args = parser.parse_args()

    result = run_check(args.brand, args.url)

    if args.json:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(result)

    sys.exit(0 if result["verdict"] in ("ČITATEĽNÉ",) else 1)
