import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from generic.config_scraper import load_config, extract_field, clean_text

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "audi_stock_a1_detail_sample.html"
CONFIG = Path(__file__).resolve().parent.parent / "configs" / "audi_stock.json"
VEHICLE_URL = "https://skladove-vozidla.audi.sk/search/car/A-2025-0753383-SK"


def test_audi_config_extraction():
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    full_text = clean_text(soup.get_text(separator="\n"))
    config = load_config(str(CONFIG))

    result = {}
    for field_cfg in config["fields"]:
        result.update(extract_field(field_cfg, full_text, soup, base_url=VEHICLE_URL))

    print("Výsledok extrakcie Audi:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    assert result["id"] == "A-2025-0753383-SK"
    assert result["title"] == "A1 Sportback 25 TFSI STR"
    assert result["stav"] == "Nové vozidlá"
    assert result["cena_povodna"] == 33518.99
    assert result["cena"] == 26900.0
    assert result["najazdene_km"] == 10
    assert result["palivo"] == "Benzín"
    assert result["vykon_kw"] == 70
    assert result["objem_l"] == 1.0
    assert result["spotreba_l_100km"] == 5.7
    assert result["pohon"] == "Predný pohon"
    assert result["prevodovka"] == "S tronic 7-st."
    assert result["co2_g_km"] == 129
    assert result["farba_karoserie"] == "modrá navarra metalíza"
    assert result["farba_interieru"] == "granitgrau"
    assert result["calunenie"] == "Látka"

    # 3 obrázky z /model/ (fallback logo vyfiltrovaný cez src_contains)
    assert len(result["obrazky"]) == 3
    assert all("/model/" in u for u in result["obrazky"])
    assert not any("fallback" in u for u in result["obrazky"])

    print("\nOK: všetky polia Audi configu extrahované správne")


if __name__ == "__main__":
    test_audi_config_extraction()
    print("\nVšetky testy prešli.")
