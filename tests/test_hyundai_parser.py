import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.text_utils import parse_variants_from_text, parse_starting_price
from common.models import Model
from common.xml_builder import build_feed_xml

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "hyundai_i20_vybavy_sample.txt"


def test_variants():
    text = FIXTURE.read_text(encoding="utf-8")
    variants = parse_variants_from_text(text)

    assert len(variants) == 3, f"Očakávané 3 výbavy, nájdených {len(variants)}"

    comfort = variants[0]
    assert comfort.trim == "COMFORT"
    assert comfort.price_from_eur == 14240.0
    assert "Manuálna klimatizácia" in comfort.features
    assert len(comfort.features) == 5  # intro riadok skončiaci ':' sa nepočíta

    style = variants[2]
    assert style.trim == "STYLE"
    assert style.price_from_eur == 18840.0

    print(f"OK: {len(variants)} výbav s cenami rozparsovaných správne")
    for v in variants:
        print(f"  - {v.trim}: od {v.price_from_eur} € ({len(v.features)} funkcií)")


def test_xml_with_variants():
    text = FIXTURE.read_text(encoding="utf-8")
    model = Model(
        name="i20",
        url="https://www.hyundai.com/sk/sk/modely/i20.html",
        brand="hyundai",
        price_from_eur=14790.0,
    )
    model.variants = parse_variants_from_text(text)

    xml_str = build_feed_xml("hyundai", "https://www.hyundai.com/sk/sk", [model])
    assert xml_str.count("<variant>") == 3
    assert "14240.0" in xml_str
    assert "COMFORT" in xml_str

    out_path = Path(__file__).resolve().parent.parent / "output" / "hyundai_feed_SAMPLE.xml"
    out_path.write_text(xml_str, encoding="utf-8")
    print(f"OK: ukážkový feed zapísaný do {out_path}")


if __name__ == "__main__":
    test_variants()
    test_xml_with_variants()
    print("\nVšetky testy prešli.")
