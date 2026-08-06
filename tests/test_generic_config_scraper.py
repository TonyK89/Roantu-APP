import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup
from generic.config_scraper import load_config, extract_field

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "hyundai_stock_tucson_detail_sample.txt"
CONFIG = Path(__file__).resolve().parent.parent / "configs" / "hyundai_stock.json"


def test_config_matches_hand_written_parser():
    full_text = FIXTURE.read_text(encoding="utf-8")
    soup = BeautifulSoup("<html></html>", "html.parser")  # meta_tag sa tu nepoužíva
    config = load_config(str(CONFIG))

    result = {}
    for field_cfg in config["fields"]:
        result.update(extract_field(field_cfg, full_text, soup))

    print("Výsledok config-driven extrakcie:", result)

    # Rovnaké hodnoty, aké dal ručne napísaný common/stock_text_utils.py parser
    assert result["objem_motoru"] == 1598
    assert result["rok_vyroby"] == 2026
    assert result["najazdene_km"] == 10
    assert result["vykon_kw"] == 110
    assert result["typ_karoserie"] == "SUV"
    assert result["palivo"] == "Benzín"
    assert result["farba"] == "Zelená Matná"
    assert result["calunenie"] == "Textil/Koža Čierna"
    assert result["pocet_dveri_miest"] == "5/5"
    assert result["prevodovka"] == "Manuálna"
    assert result["vin"] == "TMAJD81B0VJ749961"
    assert result["cena"] == 28390.0
    assert result["najnizsia_cena_30_dni"] == 31630.0

    print("OK: config-driven extrakcia dáva IDENTICKÉ výsledky ako ručne napísaný parser")


if __name__ == "__main__":
    test_config_matches_hand_written_parser()
    print("\nVšetky testy prešli.")
