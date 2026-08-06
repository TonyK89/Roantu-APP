#!/usr/bin/env python3
"""
Generovanie XML feedov pre roanty.sk.

Použitie:
    python main.py --brand skoda
    python main.py --brand skoda --output /var/www/roanty-feeds
    python main.py --brand skoda --fields engines,trims
    python main.py --all

Odporúčané hodinové spúšťanie: pozri deploy/crontab.example alebo
deploy/roanty-feeds.timer (systemd).
"""
import argparse
import logging
import sys
from pathlib import Path

from config import BRANDS
from common.xml_builder import write_feed
from common.stock_xml_builder import write_stock_feed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("roanty-feeds")


def run_brand(brand: str, output_dir: Path, fields, include, exclude) -> bool:
    scraper_cls = BRANDS.get(brand)
    if not scraper_cls:
        log.error("Neznáma značka '%s'. Dostupné: %s", brand, ", ".join(BRANDS))
        return False

    scraper = scraper_cls()
    log.info("Scrapujem značku: %s (%s)", brand, scraper.base_url)

    try:
        models = scraper.scrape_all(include=include, exclude=exclude)
    except Exception:
        log.exception("Scraping značky '%s' zlyhal, feed sa nemení.", brand)
        return False

    if not models:
        log.warning("Značka '%s': nenašli sa žiadne modely, feed sa nemení (možná zmena štruktúry webu).", brand)
        return False

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{brand}_feed.xml"

    if scraper.output_kind == "stock":
        write_stock_feed(brand, scraper.base_url, models, str(output_path))
    else:
        write_feed(brand, scraper.base_url, models, str(output_path), fields=fields)

    log.info("Hotovo: %s (%d %s) -> %s", brand, len(models),
              "vozidiel" if scraper.output_kind == "stock" else "modelov", output_path)
    return True


def main():
    parser = argparse.ArgumentParser(description="Generovanie XML feedov áut pre roanty.sk")
    parser.add_argument("--brand", help="jedna značka, napr. skoda")
    parser.add_argument("--all", action="store_true", help="všetky značky z config.py")
    parser.add_argument("--output", default="output", help="výstupný adresár pre XML feedy")
    parser.add_argument("--fields", help="čiarkou oddelený zoznam: engines,trims,price_pdf,technical_pdf,configurator")
    parser.add_argument("--include", help="čiarkou oddelený zoznam modelov, ktoré zahrnúť (default: všetky)")
    parser.add_argument("--exclude", help="čiarkou oddelený zoznam modelov, ktoré vynechať")
    args = parser.parse_args()

    if not args.brand and not args.all:
        parser.error("Zadaj --brand <značka> alebo --all")

    fields = args.fields.split(",") if args.fields else None
    include = args.include.split(",") if args.include else None
    exclude = args.exclude.split(",") if args.exclude else None
    output_dir = Path(args.output)

    brands = list(BRANDS.keys()) if args.all else [args.brand]

    ok = True
    for brand in brands:
        ok = run_brand(brand, output_dir, fields, include, exclude) and ok

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
