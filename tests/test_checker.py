import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checker import analyze_html, verdict

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_js_spa_detected():
    html = (FIXTURES / "checker_js_spa_sample.html").read_text(encoding="utf-8")
    analysis = analyze_html(html)
    v = verdict(analysis)
    print(f"JS-SPA fixture: text_len={analysis['visible_text_len']}, signals={analysis['total_signals']}, verdikt={v}")
    assert v == "JS-SPA (pravdepodobne)", f"Očakávané JS-SPA, dostal som: {v}"
    print("OK: JS-SPA stránka správne rozpoznaná")


def test_readable_detected():
    html = (FIXTURES / "checker_readable_sample.html").read_text(encoding="utf-8")
    analysis = analyze_html(html)
    v = verdict(analysis)
    print(f"Readable fixture: text_len={analysis['visible_text_len']}, signals={analysis['total_signals']}, verdikt={v}")
    assert v == "ČITATEĽNÉ", f"Očakávané ČITATEĽNÉ, dostal som: {v}"
    print("OK: čitateľná stránka správne rozpoznaná")


if __name__ == "__main__":
    test_js_spa_detected()
    test_readable_detected()
    print("\nVšetky testy prešli.")
