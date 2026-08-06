import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.stock_text_utils import (
    parse_stock_specs, parse_stock_price, parse_location,
    parse_dealer_name, parse_dealer_email,
)

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "hyundai_stock_tucson_detail_sample.txt"


def test_specs():
    text = FIXTURE.read_text(encoding="utf-8")
    specs = parse_stock_specs(text)

    assert specs["engine_ccm"] == 1598
    assert specs["year"] == 2026
    assert specs["mileage_km"] == 10
    assert specs["power_kw"] == 110
    assert specs["body_type"] == "SUV"
    assert specs["fuel_type"] == "Benzín"
    assert specs["color"] == "Zelená Matná"
    assert specs["upholstery"] == "Textil/Koža Čierna"
    assert specs["doors_seats"] == "5/5"
    assert specs["transmission"] == "Manuálna"
    assert specs["vin"] == "TMAJD81B0VJ749961"
    print("OK: technické špecifikácie rozparsované správne:", specs)


def test_price():
    text = FIXTURE.read_text(encoding="utf-8")
    price = parse_stock_price(text)

    assert price["price_original_eur"] == 35530.0
    assert price["discount_eur"] == 7140.0
    assert price["price_eur"] == 28390.0
    assert price["price_lowest_30d_eur"] == 31630.0
    print("OK: cena rozparsovaná správne:", price)


def test_location_and_dealer():
    text = FIXTURE.read_text(encoding="utf-8")
    assert parse_location(text) == "Žilina"
    assert parse_dealer_name(text) == "ALTERIA MOTOR"
    assert parse_dealer_email(text) == "bohynik@alteria.sk"
    print("OK: poloha a predajca rozparsovaní správne")


def test_full_stock_xml():
    from common.models import StockVehicle
    from common.stock_xml_builder import build_stock_cars_xml

    text = FIXTURE.read_text(encoding="utf-8")
    specs = parse_stock_specs(text)
    price = parse_stock_price(text)

    v = StockVehicle(
        external_id="6475",
        brand="hyundai",
        model="TUCSON",
        variant="TUC FL 1,6T 2WD BLACK ED MY27",
        url="https://skladove.hyundai.sk/ponuka/hyundai-tucson/6475",
        status="NOVÉ",
        is_promo=False,
        location_city=parse_location(text),
        dealer_name=parse_dealer_name(text),
        dealer_email=parse_dealer_email(text),
        **specs,
        **price,
    )

    xml_str = build_stock_cars_xml("hyundai", "https://skladove.hyundai.sk", [v])
    assert "<vin>TMAJD81B0VJ749961</vin>" in xml_str
    assert "<cena mena=\"EUR\">28390.0</cena>" in xml_str
    assert "<najnizsia_cena_30_dni>31630.0</najnizsia_cena_30_dni>" in xml_str
    assert "<nazov>ALTERIA MOTOR</nazov>" in xml_str

    out_path = Path(__file__).resolve().parent.parent / "output" / "hyundai_stock_feed_SAMPLE.xml"
    out_path.write_text(xml_str, encoding="utf-8")
    print(f"OK: ukážkový stock feed zapísaný do {out_path}")


if __name__ == "__main__":
    test_specs()
    test_price()
    test_location_and_dealer()
    test_full_stock_xml()
    print("\nVšetky testy prešli.")
