import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generic.image_cache import cached_filename, cache_one_image
import requests


def test_filename_is_stable():
    url = "https://skladove.hyundai.sk/media/thumbnails/1a/foo.png"
    name1 = cached_filename(url)
    name2 = cached_filename(url)
    assert name1 == name2, "Rovnaká URL musí vždy dať rovnaký názov súboru"
    assert name1.endswith(".png")
    print(f"OK: stabilný názov súboru pre rovnakú URL: {name1}")


def test_different_urls_different_names():
    url1 = "https://a.sk/foto1.jpg"
    url2 = "https://a.sk/foto2.jpg"
    assert cached_filename(url1) != cached_filename(url2)
    print("OK: rôzne URL dávajú rôzne názvy súborov")


def test_existing_file_not_redownloaded():
    """Simuluje druhý beh scrapera - súbor už je v cache, nesmie sa sťahovať znova."""
    with tempfile.TemporaryDirectory() as tmp:
        cache_dir = Path(tmp)
        url = "https://tento-server-neexistuje-a-nikdy-nebude.invalid/foto.jpg"
        filename = cached_filename(url)

        # nasimuluj, že súbor je už stiahnutý z predchádzajúceho behu
        (cache_dir / filename).write_bytes(b"fake image content")

        session = requests.Session()
        result_filename, status = cache_one_image(url, cache_dir, session)

        # keďže súbor existuje, NESMIE sa robiť žiadny network request
        # (URL je zámerne neexistujúca doména - ak by cache_one_image
        # skúsil sťahovať, dostali by sme 'failed', nie 'existing')
        assert status == "existing", f"Očakávané 'existing', dostal som '{status}'"
        assert result_filename == filename
        print("OK: už cachovaný súbor sa znova nesťahuje (aj keď URL už neexistuje)")


if __name__ == "__main__":
    test_filename_is_stable()
    test_different_urls_different_names()
    test_existing_file_not_redownloaded()
    print("\nVšetky testy prešli.")
