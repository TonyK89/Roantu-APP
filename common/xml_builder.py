"""
Vyrobí XML feed z listu Model objektov. Štruktúra je spoločná pre všetky
značky, aby sa dali na roanty.sk parsovať jedným univerzálnym importérom.

Príklad výstupu - pozri README.md.
"""
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, ElementTree
from xml.dom import minidom
from typing import List

from common.models import Model


def _set_text(parent: Element, tag: str, value) -> None:
    if value is None:
        return
    el = SubElement(parent, tag)
    el.text = str(value)


def build_feed_xml(brand: str, source_url: str, models: List[Model], fields: List[str] = None) -> str:
    """
    fields: voliteľný filter, ktoré sekcie zahrnúť do feedu, napr.
            ["engines", "trims", "price_pdf", "technical_pdf"].
            Ak None, zahrnie sa všetko dostupné (default: "všetky parametre").
    """
    all_fields = {"engines", "trims", "variants", "price_pdf", "technical_pdf", "configurator"}
    fields = set(fields) if fields else all_fields

    root = Element("feed", {
        "brand": brand,
        "source": source_url,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })

    for m in models:
        model_el = SubElement(root, "model")
        _set_text(model_el, "name", m.name)
        _set_text(model_el, "url", m.url)
        _set_text(model_el, "image_url", m.image_url)

        if "configurator" in fields:
            _set_text(model_el, "configurator_url", m.configurator_url)

        if "price_pdf" in fields:
            _set_text(model_el, "price_list_pdf", m.price_list_pdf)
        _set_text(model_el, "price_from_eur", m.price_from_eur)

        if "variants" in fields and m.variants:
            variants_el = SubElement(model_el, "variants")
            for v in m.variants:
                variant_el = SubElement(variants_el, "variant")
                _set_text(variant_el, "trim", v.trim)
                _set_text(variant_el, "price_from_eur", v.price_from_eur)
                if v.features:
                    features_el = SubElement(variant_el, "features")
                    for feat in v.features:
                        _set_text(features_el, "feature", feat)

        if "technical_pdf" in fields:
            _set_text(model_el, "technical_data_pdf", m.technical_data_pdf)

        if "trims" in fields and m.trims:
            trims_el = SubElement(model_el, "trims")
            for t in m.trims:
                _set_text(trims_el, "trim", t)

        if "engines" in fields and m.engines:
            engines_el = SubElement(model_el, "engines")
            for e in m.engines:
                engine_el = SubElement(engines_el, "engine")
                _set_text(engine_el, "name", e.name)
                _set_text(engine_el, "fuel_type", e.fuel_type)
                _set_text(engine_el, "power_kw", e.power_kw)
                _set_text(engine_el, "transmission", e.transmission)
                _set_text(engine_el, "top_speed_kmh", e.top_speed_kmh)
                _set_text(engine_el, "acceleration_0_100_s", e.acceleration_0_100_s)
                _set_text(engine_el, "torque_nm", e.torque_nm)
                if e.available_trims:
                    trims_el2 = SubElement(engine_el, "available_trims")
                    for t in e.available_trims:
                        _set_text(trims_el2, "trim", t)

    rough = ElementTree(root)
    xml_bytes = _tostring(root)
    return xml_bytes


def _tostring(root: Element) -> str:
    from xml.etree.ElementTree import tostring
    raw = tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")
    # odstráň prázdne riadky, ktoré toprettyxml rado generuje
    return "\n".join(line for line in pretty.split("\n") if line.strip())


def write_feed(brand: str, source_url: str, models: List[Model], output_path: str, fields: List[str] = None) -> None:
    xml_str = build_feed_xml(brand, source_url, models, fields)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_str)
