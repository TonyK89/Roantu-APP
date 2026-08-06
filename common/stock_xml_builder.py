"""
Generuje XML feed reálnych skladových vozidiel v štruktúre podobnej
štandardu, ktorý používajú importérske/predajcovské feedy na SK trhu
(napr. cars_feed/auto/cena/najazdene_km/vin...).

Odlišné od common/xml_builder.py, ktorý je pre katalógové dáta výrobcu
(generické modely bez konkrétneho kusu, km, VIN).
"""
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from typing import List

from common.models import StockVehicle


def _set_text(parent: Element, tag: str, value) -> None:
    if value is None:
        return
    el = SubElement(parent, tag)
    el.text = str(value)


def build_stock_cars_xml_generic(brand: str, source_url: str, vehicles: list, list_item_tags: dict = None) -> str:
    """
    Rovnaké ako build_stock_cars_xml, ale vstup je zoznam obyčajných dict
    (tag_name -> hodnota) namiesto StockVehicle objektov - presne to, čo
    produkuje generic/config_scraper.py. Kľúč "url" sa vždy zapíše ako prvý.

    list_item_tags: {"obrazky": "obrazok", "vystroj": "polozka"} - hovorí, že
    hodnota pod kľúčom "obrazky" je Python list a každá položka sa má zapísať
    ako samostatný <obrazok> element vo vnútri <obrazky>...</obrazky>.
    """
    list_item_tags = list_item_tags or {}

    root = Element("cars_feed", {
        "znacka": brand,
        "generovane": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "zdroj": source_url,
        "krajina": "SK",
    })

    for vehicle_dict in vehicles:
        auto = SubElement(root, "auto")
        if "url" in vehicle_dict:
            _set_text(auto, "url", vehicle_dict["url"])
        for key, value in vehicle_dict.items():
            if key == "url":
                continue
            if isinstance(value, list):
                if not value:
                    continue  # prázdny zoznam - nezapisuj prázdny wrapper tag
                item_tag = list_item_tags.get(key, "polozka")
                wrapper = SubElement(auto, key)
                for item in value:
                    _set_text(wrapper, item_tag, item)
            else:
                _set_text(auto, key, value)

    raw = tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.split("\n") if line.strip())


def build_stock_cars_xml(brand: str, source_url: str, vehicles: List[StockVehicle]) -> str:
    root = Element("cars_feed", {
        "znacka": brand,
        "generovane": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "zdroj": source_url,
        "krajina": "SK",
    })

    for v in vehicles:
        auto = SubElement(root, "auto")
        _set_text(auto, "id", v.external_id)
        title = f"{v.brand.capitalize()} {v.model}" + (f" {v.variant}" if v.variant else "")
        _set_text(auto, "title", title.strip())
        _set_text(auto, "znacka", v.brand.capitalize())
        _set_text(auto, "model", v.model)
        _set_text(auto, "varianta", v.variant)
        _set_text(auto, "url", v.url)
        _set_text(auto, "stav", v.status)
        _set_text(auto, "akciova_ponuka", "true" if v.is_promo else "false")
        _set_text(auto, "rok_vyroby", v.year)

        cena = SubElement(auto, "cena", {"mena": "EUR"})
        cena.text = str(v.price_eur) if v.price_eur is not None else None
        if v.price_original_eur is not None:
            _set_text(auto, "cena_povodna", v.price_original_eur)
        if v.discount_eur is not None:
            _set_text(auto, "zlava", v.discount_eur)
        if v.price_lowest_30d_eur is not None:
            # povinný údaj podľa zákona o ochrane spotrebiteľa (108/2024 Z.z.)
            _set_text(auto, "najnizsia_cena_30_dni", v.price_lowest_30d_eur)

        _set_text(auto, "najazdene_km", v.mileage_km)
        _set_text(auto, "palivo", v.fuel_type)
        _set_text(auto, "objem_motoru", v.engine_ccm)
        _set_text(auto, "vykon_kw", v.power_kw)
        _set_text(auto, "prevodovka", v.transmission)
        _set_text(auto, "pohon", v.drivetrain)
        _set_text(auto, "typ_karoserie", v.body_type)
        _set_text(auto, "pocet_dveri_miest", v.doors_seats)
        _set_text(auto, "farba", v.color)
        _set_text(auto, "calunenie", v.upholstery)
        _set_text(auto, "vin", v.vin)

        _set_text(auto, "poloha", v.location_city)
        if v.dealer_name or v.dealer_email:
            predajca = SubElement(auto, "predajca")
            _set_text(predajca, "nazov", v.dealer_name)
            _set_text(predajca, "email", v.dealer_email)
            _set_text(predajca, "url", v.dealer_url)

        if v.images:
            obrazky = SubElement(auto, "obrazky")
            for img in v.images:
                _set_text(obrazky, "obrazok", img)

    raw = tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.split("\n") if line.strip())


def write_stock_feed(brand: str, source_url: str, vehicles: List[StockVehicle], output_path: str) -> None:
    xml_str = build_stock_cars_xml(brand, source_url, vehicles)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
