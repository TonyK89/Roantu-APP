"""
Parsovanie detailu skladového vozidla z importérskych portálov typu
skladove.hyundai.sk. Na rozdiel od common/text_utils.py (katalógové
modely výrobcu) tu ide o REÁLNE kusy na sklade s cenou, km, VIN,
konkrétnym predajcom.
"""
import re
from typing import Optional, Dict

# Popisky tak, ako sa objavujú v sekcii "Technické Špecifikácie" na
# skladove.hyundai.sk. Iný importér = iné popisky, uprav pri ďalšej značke.
STOCK_LABELS = {
    "Objem": "engine_ccm",
    "Rok výroby": "year",
    "Najazdené km": "mileage_km",
    "Výkon": "power_kw",
    "Karoséria": "body_type",
    "Druh paliva": "fuel_type",
    "Farba karosérie": "color",
    "Čalúnenie": "upholstery",
    "Počet dverí/miest": "doors_seats",
    "Prevodovka": "transmission",
    "VIN": "vin",
}

NUMERIC_FIELDS = {"engine_ccm", "year", "mileage_km", "power_kw"}

NUMBER_RE = re.compile(r"[\d\s]+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# "35 530 € -7 140 €"  →  pôvodná cena a zľava
PRICE_DISCOUNT_RE = re.compile(r"([\d\s]{4,8})\s*€\s*-\s*([\d\s]{1,6})\s*€")
LOWEST_30D_RE = re.compile(r"najnižšia cena ponuky za posledných 30 dní\s*([\d\s]{4,8})\s*€", re.IGNORECASE)
POLOHA_RE = re.compile(r"^Poloha$")
DEALER_RE = re.compile(r"^Predajca\s+(.+)$")


def _num(raw: str) -> float:
    return float(raw.replace(" ", "").replace("\xa0", ""))


def parse_stock_specs(full_text: str) -> Dict[str, object]:
    """Vytiahne label→value dvojice zo sekcie Technické Špecifikácie."""
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    data: Dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if line in STOCK_LABELS and i + 1 < len(lines):
            field_name = STOCK_LABELS[line]
            raw_value = lines[i + 1]
            if field_name in NUMERIC_FIELDS:
                m = NUMBER_RE.search(raw_value)
                data[field_name] = int(m.group().replace(" ", "")) if m else None
            else:
                data[field_name] = raw_value
            i += 2
            continue
        i += 1
    return data


def parse_stock_price(full_text: str) -> Dict[str, Optional[float]]:
    """
    Vypočíta cenové údaje. Aktuálnu cenu odvodzujeme aritmeticky
    (pôvodná - zľava), nie parsovaním zvýrazneného textu, ktorý je
    v HTML náchylnejší na zmenu formátovania než čisté čísla.
    """
    result: Dict[str, Optional[float]] = {
        "price_original_eur": None,
        "discount_eur": None,
        "price_eur": None,
        "price_lowest_30d_eur": None,
    }
    m = PRICE_DISCOUNT_RE.search(full_text)
    if m:
        result["price_original_eur"] = _num(m.group(1))
        result["discount_eur"] = _num(m.group(2))
        result["price_eur"] = result["price_original_eur"] - result["discount_eur"]

    m2 = LOWEST_30D_RE.search(full_text)
    if m2:
        result["price_lowest_30d_eur"] = _num(m2.group(1))

    return result


def parse_location(full_text: str) -> Optional[str]:
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if POLOHA_RE.match(line) and i + 1 < len(lines):
            return lines[i + 1]
    return None


def parse_dealer_name(full_text: str) -> Optional[str]:
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    for line in lines:
        m = DEALER_RE.match(line)
        if m:
            return m.group(1).strip()
    return None


def parse_dealer_email(full_text: str) -> Optional[str]:
    m = EMAIL_RE.search(full_text)
    return m.group() if m else None
