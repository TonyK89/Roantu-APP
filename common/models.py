"""
Spoločný dátový model pre všetky značky.
Každý brand-scraper (scrapers/*.py) musí vracať zoznam Model objektov
v tejto štruktúre, aby xml_builder vedel vyrobiť jednotný XML feed.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Engine:
    name: str                              # napr. "2.0 TDI 85 kW 6-stup. manuál"
    fuel_type: Optional[str] = None        # Benzín / Diesel / Mild Hybrid / Elektro ...
    power_kw: Optional[int] = None
    transmission: Optional[str] = None     # napr. "6-stup. manuál"
    top_speed_kmh: Optional[int] = None
    acceleration_0_100_s: Optional[float] = None
    torque_nm: Optional[int] = None
    available_trims: List[str] = field(default_factory=list)  # v ktorých výbavách je dostupný


@dataclass
class Variant:
    """Konkrétna predávaná verzia modelu = úroveň výbavy s vlastnou cenou.
    Toto je najbližšie k tomu, čo porovnávač potrebuje na zobrazenie reálnej ceny."""
    trim: str                              # napr. "COMFORT", "FAMILY", "STYLE"
    price_from_eur: Optional[float] = None
    features: List[str] = field(default_factory=list)  # výbava navyše/v základe


@dataclass
class StockVehicle:
    """
    Jedno konkrétne reálne vozidlo na sklade (nie katalógový model).
    Zodpovedá dátam z importérskych 'skladové vozidlá' portálov, ktoré
    agregujú zásoby za CELÚ sieť predajcov danej značky (napr.
    skladove.hyundai.sk, skladove-vozidla.audi.sk).
    """
    external_id: str            # ID vozidla v systéme importéra (napr. "6475")
    brand: str
    model: str                  # napr. "TUCSON"
    variant: Optional[str] = None  # napr. "TUC FL 1,6T 2WD BLACK ED MY27"
    url: str = ""
    status: Optional[str] = None      # "NOVÉ" / "PREDVÁDZACIE" ...
    is_promo: bool = False

    price_original_eur: Optional[float] = None
    discount_eur: Optional[float] = None
    price_eur: Optional[float] = None           # aktuálna cena (po zľave)
    price_lowest_30d_eur: Optional[float] = None  # povinný údaj podľa zákona o ochrane spotrebiteľa

    fuel_type: Optional[str] = None
    engine_ccm: Optional[int] = None
    power_kw: Optional[int] = None
    transmission: Optional[str] = None
    drivetrain: Optional[str] = None
    body_type: Optional[str] = None
    color: Optional[str] = None
    upholstery: Optional[str] = None
    doors_seats: Optional[str] = None
    year: Optional[int] = None
    mileage_km: Optional[int] = None
    vin: Optional[str] = None

    location_city: Optional[str] = None
    dealer_name: Optional[str] = None
    dealer_email: Optional[str] = None
    dealer_url: Optional[str] = None

    images: List[str] = field(default_factory=list)


@dataclass
class Model:
    name: str
    url: str
    brand: str = ""
    configurator_url: Optional[str] = None
    price_list_pdf: Optional[str] = None
    technical_data_pdf: Optional[str] = None
    image_url: Optional[str] = None
    trims: List[str] = field(default_factory=list)   # úrovne výbavy (Essence, Selection, ...)
    engines: List[Engine] = field(default_factory=list)
    variants: List[Variant] = field(default_factory=list)  # výbava s reálnou cenou (ak dostupné v HTML)
    price_from_eur: Optional[float] = None  # celková "od" cena modelu, ak je v HTML (napr. Hyundai)
