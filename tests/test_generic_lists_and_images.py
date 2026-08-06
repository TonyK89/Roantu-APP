import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from generic.config_scraper import extract_field
from common.stock_xml_builder import build_stock_cars_xml_generic

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "checker_images_equipment_sample.html"
BASE_URL = "https://skladove.hyundai.sk/ponuka/hyundai-tucson/6475"


def test_image_list_extraction():
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    field_cfg = {
        "tag": "obrazky",
        "method": "image_list",
        "css_selector": "img",
        "attr": "src",
        "src_contains": "/media/",
        "item_tag": "obrazok",
    }
    result = extract_field(field_cfg, "", soup, base_url=BASE_URL)
    urls = result["obrazky"]

    print("Nájdené obrázky:", urls)
    # 2 unikátne (duplicita odfiltrovaná), logo vylúčené cez src_contains filter
    assert len(urls) == 2
    assert all(u.startswith("https://skladove.hyundai.sk/media/") for u in urls)
    assert "logo-header" not in str(urls)
    print("OK: image_list - správne absolutizované, deduplikované, vyfiltrované")


def test_regex_findall_equipment():
    html = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(separator="\n")

    field_cfg = {
        "tag": "vystroj",
        "method": "regex_findall",
        "pattern": r"Vybavenie:\s*(.+)",
        "item_tag": "polozka",
    }
    result = extract_field(field_cfg, full_text, soup)
    items = result["vystroj"]

    print("Nájdená výbava:", items)
    assert items == ["Klimatizácia", "LED svetlá", "Parkovacia kamera"]  # duplicita odfiltrovaná
    print("OK: regex_findall - správne nájdené a deduplikované")


def test_xml_with_list_fields():
    vehicle = {
        "url": BASE_URL,
        "cena": 28390.0,
        "obrazky": [
            "https://skladove.hyundai.sk/media/thumbnails/1a/x.png",
            "https://skladove.hyundai.sk/media/thumbnails/52/y.png",
        ],
        "vystroj": ["Klimatizácia", "LED svetlá"],
    }
    xml_str = build_stock_cars_xml_generic(
        "hyundai", "https://skladove.hyundai.sk", [vehicle],
        list_item_tags={"obrazky": "obrazok", "vystroj": "polozka"},
    )
    print(xml_str)
    assert "<obrazky>" in xml_str and "<obrazok>" in xml_str
    assert "<vystroj>" in xml_str and "<polozka>Klimatizácia</polozka>" in xml_str
    assert xml_str.count("<obrazok>") == 2
    print("OK: XML so zoznamovými poľami vygenerované správne")


if __name__ == "__main__":
    test_image_list_extraction()
    test_regex_findall_equipment()
    test_xml_with_list_fields()
    print("\nVšetky testy prešli.")
