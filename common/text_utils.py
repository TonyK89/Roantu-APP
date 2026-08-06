"""
Parsovanie sekcie "Motory" a "Úrovne výbavy" z čistého textu stránky
(soup.get_text(separator="\n")).

Prečo takto a nie cez CSS selektory:
Škoda (a pravdepodobne aj ostatné značky) stránky pravidelne redizajnujú
a CSS triedy sa menia. Poradie a znenie popiskov (Prevodovka, Zrýchlenie,
Druh paliva...) je stabilnejšie než trieda <div class="ab12-xy">.
Táto vrstva je preto odolnejšia - ale STÁLE treba po nasadení overiť
na živej stránke, že popisky sedia (pozri README, sekcia "Overenie").
"""
import re
from typing import List, Optional
from common.models import Engine, Variant

# Popisky tak, ako sa objavujú na skoda-auto.sk. Pre inú značku si
# skopíruj tento slovník a uprav hodnoty na jej vlastné popisky (napr.
# VW/Audi môžu používať "Maximální rychlost" a pod.).
LABELS = {
    "Najvyššia rýchlosť": "top_speed_kmh",
    "Prevodovka": "transmission",
    "Zrýchlenie": "acceleration_0_100_s",
    "Maximálny krútiaci moment": "torque_nm",
    "Druh paliva": "fuel_type",
}

# Riadok, ktorý vypadá ako názov motorizácie, napr. "2.0 TDI 85 kW 6-stup. manuál"
ENGINE_NAME_RE = re.compile(r"^\d+[.,]\d+\s+\S+.*\d+\s*kW", re.IGNORECASE)

# Riadok, ktorý je len číslo (hodnota patriaca k predchádzajúcemu popisku),
# príp. s jednotkou pripojenou na ďalšom riadku - jednotky ignorujeme,
# berieme prvé číslo.
NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _section(text: str, start_marker: str, end_markers: List[str]) -> str:
    """
    Vytiahne časť textu medzi riadkom start_marker a najbližším riadkom,
    ktorý sa ZHODUJE (nie je len podreťazcom) s niektorým z end_markers.
    Riadkovo, aby "## Motory" neomylom "zachytilo" napr. "### Niečo"
    (to by sa stalo pri hľadaní podreťazca "## " kdekoľvek v texte).
    """
    lines = text.split("\n")
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip() == start_marker.strip():
            start_idx = i + 1
            break
    if start_idx is None:
        return ""

    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        stripped = lines[i].strip()
        for marker in end_markers:
            if stripped == marker.strip():
                end_idx = i
                break
        if end_idx != len(lines) and i == end_idx:
            break

    return "\n".join(lines[start_idx:end_idx])


def parse_engines_from_text(full_text: str) -> List[Engine]:
    """
    Očakáva text celej stránky modelu. Nájde sekciu "## Motory" a rozparsuje
    jednotlivé motorizácie. Duplicitné mená (stránka niekedy vypisuje
    zoznam dvakrát - desktop/mobile varianta) sa zlúčia do jedného záznamu.
    """
    section = _section(full_text, "## Motory", ["## Úrovne výbavy", "## Porovnanie", "Porovnanie motorov"])
    if not section:
        return []

    lines = [l.strip() for l in section.split("\n") if l.strip()]

    engines_by_name = {}
    current: Optional[Engine] = None
    pending_label: Optional[str] = None
    current_trims_line: List[str] = []

    for line in lines:
        clean = line.lstrip("#").strip()

        if ENGINE_NAME_RE.match(clean):
            current = engines_by_name.get(clean) or Engine(name=clean)
            engines_by_name[clean] = current
            pending_label = None
            continue

        if current is None:
            continue

        # riadok s výbavami motora, napr. "Essence, Selection" pod # hlavičkou
        # (na skoda-auto.sk to býva ako samostatný riadok začínajúci "####")
        if line.startswith("####"):
            trims = [t.strip() for t in clean.split(",") if t.strip()]
            for t in trims:
                if t not in current.available_trims:
                    current.available_trims.append(t)
            continue

        if clean in LABELS:
            pending_label = LABELS[clean]
            continue

        if pending_label:
            field = pending_label
            if field == "transmission":
                setattr(current, field, clean)
            elif field == "fuel_type":
                setattr(current, field, clean)
            else:
                num_match = NUMBER_RE.search(clean.replace(" ", ""))
                if num_match:
                    raw = num_match.group().replace(",", ".")
                    value = float(raw) if "." in raw else int(raw)
                    setattr(current, field, value)
            pending_label = None

    return list(engines_by_name.values())


def parse_trims_from_text(full_text: str) -> List[str]:
    """
    Vytiahne úrovne výbavy zo sekcie '## Úrovne výbavy'.
    Berie riadky '### Meno' v tejto sekcii, okrem 'Galéria'.
    """
    section = _section(full_text, "## Úrovne výbavy", ["## Všetko pre vaše pohodlie"])
    if not section:
        return []

    trims = []
    for line in section.split("\n"):
        line = line.strip()
        if line.startswith("### "):
            name = line[4:].strip()
            if name and name.lower() != "galéria" and name not in trims:
                trims.append(name)
    return trims


# ---------------------------------------------------------------------------
# Parser pre "výbava + cena" štýl, ako ho má Hyundai (www.hyundai.com/sk/...).
# Na rozdiel od Škody tu je REÁLNA CENA priamo v texte stránky, nie len v PDF.
# ---------------------------------------------------------------------------

TRIM_PRICE_RE = re.compile(r"^Už od\s+([\d\s]+)\s*€$")
# Stránka za sebou vypisuje po každej úrovni výbavy odkazy "Konfigurátor" a
# "Skladové vozidlá" - to je náš signál "koniec zoznamu funkcií tejto výbavy".
VARIANT_STOP_MARKERS = {"Konfigurátor", "Skladové vozidlá"}

# Celková "od X €" cena modelu - na hyundai.com/sk je vždy sprevádzaná
# skrytým accessibility textom "open tooltip" hneď za sumou.
MODEL_PRICE_RE = re.compile(r"\bod\s+([\d\s]{4,8})\s*€\s*open tooltip", re.UNICODE)


def _parse_price(raw: str) -> float:
    return float(raw.replace(" ", "").replace("\xa0", ""))


def parse_variants_from_text(full_text: str) -> List[Variant]:
    """
    Očakáva text stránky "Úrovne výbavy" (soup.get_text(separator="\n")).
    Nájde riadky "Už od <cena> €" a k nim priradí:
      - meno výbavy = najbližší predchádzajúci neprázdny riadok (nadpis)
      - features = riadky po cene až po "Konfigurátor"/"Skladové vozidlá"
    """
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    variants: List[Variant] = []
    i = 0
    while i < len(lines):
        m = TRIM_PRICE_RE.match(lines[i])
        if m and i > 0:
            name = lines[i - 1]
            price = _parse_price(m.group(1))
            features = []
            j = i + 1
            while j < len(lines) and lines[j] not in VARIANT_STOP_MARKERS:
                if not lines[j].endswith(":"):  # vynechaj podnadpisy typu "Navyše k výbave COMFORT:"
                    features.append(lines[j])
                j += 1
            variants.append(Variant(trim=name, price_from_eur=price, features=features))
            i = j
        else:
            i += 1
    return variants


def parse_starting_price(full_text: str) -> Optional[float]:
    """Vytiahne celkovú 'od X €' cenu modelu (napr. z hlavičky stránky modelu)."""
    m = MODEL_PRICE_RE.search(full_text)
    if not m:
        return None
    return _parse_price(m.group(1))


# VW.sk nemá skrytý "open tooltip" text ako Hyundai - cena je len "Golf už od
# 20 990 €". Berieme PRVÝ výskyt v texte, pretože promo cena je vždy hneď
# pri nadpise modelu, skôr než akékoľvek iné sumy v pätičke/disclaimeroch.
SIMPLE_PRICE_RE = re.compile(r"\bod\s+([\d\s]{4,8})\s*€")


def parse_first_starting_price(full_text: str) -> Optional[float]:
    m = SIMPLE_PRICE_RE.search(full_text)
    if not m:
        return None
    return _parse_price(m.group(1))
