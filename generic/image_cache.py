"""
Lokálna cache obrázkov pre generic/config_scraper.py.

Prečo: scraper beží každú hodinu. Bez cache by sa tie isté fotky sťahovali
znova a znova (zbytočná záťaž), a ak zdroj (napr. mbpanonska.sk) fotku
zmaže alebo presunie, feed by mal odrazu rozbitý obrázok.

Ako to funguje:
1) Pre každú zdrojovú URL sa spočíta stabilný hash -> vždy rovnaký názov súboru
   pre tú istú URL, naprieč behmi scrapera.
2) Ak súbor s tým názvom UŽ existuje v cache priečinku, nesťahuje sa znova.
3) Ak nie, stiahne sa, over sa, že je to naozaj obrázok (Content-Type image/*),
   a uloží sa.
4) URL vo feede sa prepíše na `image_base_url + názov_súboru` - to je URL,
   ktorú si nastavíš tak, aby ukazovala na tento cache priečinok na tvojom
   vlastnom serveri (napr. https://roanty.sk/images/hyundai/).

Dôležité: TENTO priečinok (cache_dir) treba pravidelne servovať/synchronizovať
na tvoj web server, aby image_base_url naozaj fungovala navonok - to je mimo
tohto skriptu (napr. nginx `location /images/ { alias /cesta/k/cache_dir; }`).
"""
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RoantyFeedBot/1.0; +https://roanty.sk/o-nas/bot)"
}
TIMEOUT = 15


def cached_filename(url: str) -> str:
    """Stabilný názov súboru pre danú URL - rovnaká URL = vždy rovnaký názov."""
    ext = Path(urlparse(url).path).suffix
    if not ext or len(ext) > 5:  # ochrana pred divným/chýbajúcim suffixom
        ext = ".jpg"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return f"{digest}{ext}"


def cache_one_image(url: str, cache_dir: Path, session: requests.Session) -> Tuple[Optional[str], str]:
    """
    Vráti (názov_súboru_alebo_None, stav), kde stav je jeden z:
    'existing' (už bolo v cache), 'downloaded' (nové), 'failed' (chyba/nie je obrázok)
    """
    filename = cached_filename(url)
    local_path = cache_dir / filename

    if local_path.exists():
        return filename, "existing"

    try:
        resp = session.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            return None, "failed"

        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = local_path.with_suffix(local_path.suffix + ".tmp")
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        tmp_path.rename(local_path)  # atomické premenovanie - žiadne polovičné súbory pri páde
        return filename, "downloaded"
    except requests.RequestException:
        return None, "failed"


def cache_all_images(
    vehicles: List[Dict],
    image_tags: List[str],
    cache_dir: str,
    image_base_url: str,
) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Pre každé vozidlo a každé obrázkové pole stiahne (alebo znovu použije z
    cache) každý obrázok a PREPÍŠE URL v dátach na image_base_url + lokálny
    súbor. Vracia upravené vozidlá a štatistiky (existing/downloaded/failed).
    """
    cache_path = Path(cache_dir)
    session = requests.Session()
    stats = {"existing": 0, "downloaded": 0, "failed": 0}

    for vehicle in vehicles:
        for tag in image_tags:
            original_urls = vehicle.get(tag) or []
            new_urls = []
            for url in original_urls:
                filename, status = cache_one_image(url, cache_path, session)
                stats[status] += 1
                if filename:
                    new_urls.append(image_base_url.rstrip("/") + "/" + filename)
            vehicle[tag] = new_urls

    return vehicles, stats
