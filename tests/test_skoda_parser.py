"""
Overuje common/text_utils.py na reálnom texte zo stránky Octavia
(fixtures/skoda_octavia_sample.txt), bez potreby internetu.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.text_utils import parse_engines_from_text, parse_trims_from_text
from common.models import Model
from common.xml_builder import build_feed_xml

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "skoda_octavia_sample.txt"


def test_engines():
    text = FIXTURE.read_text(encoding="utf-8")
    engines = parse_engines_from_text(text)

    assert len(engines) == 7, f"Očakávaných 7 unikátnych motorizácií, nájdených {len(engines)}"

    tdi_85 = next(e for e in engines if e.name == "2.0 TDI 85 kW 6-stup. manuál")
    assert tdi_85.fuel_type == "Diesel"
    assert tdi_85.transmission == "6-stup. manuál"
    assert tdi_85.top_speed_kmh == 212
    assert tdi_85.acceleration_0_100_s == 10
    assert tdi_85.torque_nm == 300
    assert set(tdi_85.available_trims) == {"Essence", "Selection"}

    tsi_150 = next(e for e in engines if "150 kW" in e.name)
    assert tsi_150.fuel_type == "Benzín"
    assert tsi_150.torque_nm == 320
    assert tsi_150.available_trims == ["Selection"]

    print(f"OK: {len(engines)} motorizácií rozparsovaných správne")


def test_trims():
    text = FIXTURE.read_text(encoding="utf-8")
    trims = parse_trims_from_text(text)
    assert trims == ["Essence", "Selection"], trims
    print(f"OK: výbavy = {trims}")


def test_full_xml_generation():
    text = FIXTURE.read_text(encoding="utf-8")
    model = Model(
        name="Octavia",
        url="https://www.skoda-auto.sk/modely/octavia/octavia",
        brand="skoda",
        price_list_pdf="https://webapps.skoda-auto.sk/Cenniky-a-katalogy/cenniky/Skoda_Octavia-FL_cennik.pdf",
        technical_data_pdf="https://webapps.skoda-auto.sk/Cenniky-a-katalogy/techdata/Skoda_Octavia-FL_technickeudaje.pdf",
    )
    model.engines = parse_engines_from_text(text)
    model.trims = parse_trims_from_text(text)

    xml_str = build_feed_xml("skoda", "https://www.skoda-auto.sk", [model])
    assert "<engine>" in xml_str
    assert "2.0 TDI 85 kW 6-stup. manuál" in xml_str
    assert xml_str.count("<engine>") == 7

    out_path = Path(__file__).resolve().parent.parent / "output" / "skoda_feed_SAMPLE.xml"
    out_path.write_text(xml_str, encoding="utf-8")
    print(f"OK: ukážkový feed zapísaný do {out_path}")


if __name__ == "__main__":
    test_engines()
    test_trims()
    test_full_xml_generation()
    print("\nVšetky testy prešli.")
