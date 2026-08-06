# Roanty Car Feeds

Generátor XML feedov s parametrami vozidiel pre roanty.sk.

## Nová vrstva: checker + config-driven generický scraper

## Hotové configy podľa tvojho sheetu s linkami

| Config | Zdroj (z tvojho sheetu) | Stav |
|---|---|---|
| `configs/hyundai_stock.json` | `skladove.hyundai.sk` | ✅ Otestované na reálnych dátach (13 polí, presne sedí s ručne písaným scraperom) |
| `configs/audi_stock.json` | `skladove-vozidla.audi.sk` | ✅ Otestované na reálnych dátach (18 polí vrátane obrázkov, ceny, motora) |
| `configs/vw_stock.json` | `skladove-vozidla.vw.sk` | 🔶 Rovnaká platforma ako Audi (identická štruktúra, rovnaké CDN) - odporúčam spot-check na 1-2 živých vozidlách pred ostrým behom, keďže som VW detail stránku nefetchoval do rovnakej hĺbky ako Audi |

**Ďalšie kandidáty z tvojho sheetu na rovnakú platformu** (nwi-ms.com/Porsche
Informatik) - pravdepodobne stačí skopírovať `vw_stock.json` a zmeniť len
`source_url`/`base_url`/`brand`:
- SEAT (`skladove-vozidla.seat.sk`)
- Cupra (`skladove-vozidla.cupraofficial.sk`)

**Značky vyžadujúce nové fetchovanie pred configom** (mám len search snippety,
nie plný text stránky, takže by som teraz len hádal polia): Kia
(`kiaihned.sk`), Dacia (`skladove-vozidla.dacia.sk`), Peugeot
(`peugeot.skladovevozidla.sk`) - pošli povedať, s ktorou pokračovať ďalej a
stiahnem si reálny detail vozidla, nech je config rovnako overený ako
Hyundai/Audi.

Spustenie ktoréhokoľvek hotového configu:
```bash
python -m generic.config_scraper --config configs/audi_stock.json --output output
python -m generic.config_scraper --config configs/vw_stock.json --output output
```


Toto je hlavný nástroj na pridávanie NOVÝCH značiek bez písania nového
Python kódu — dvojkrokový proces:

**Krok 1 — over čitateľnosť ľubovoľnej stránky:**
```bash
python checker.py --brand "Toyota" --url "https://www.toyota.sk/skladom"
```
Výstup povie: `ČITATEĽNÉ` (dá sa scrapovať cez requests), `JS-SPA (pravdepodobne)`
(treba Playwright), `NEISTÉ` (over ručne), alebo `BLOKOVANÉ` (robots.txt
zakazuje — nescrapovať).

Ako to funguje: stiahne stránku obyčajným `requests` (bez JavaScriptu — presne
to, čo urobí aj ostrý scraper), spočíta viditeľný text a "auto-vzory" (ceny s
€, kW, km, VIN-podobné reťazce). Veľa vzorov = server-rendered dáta = dá sa
čítať. Žiadne vzory + málo textu = obsah sa dopĺňa cez JS = nedá sa čítať
takto jednoducho.

**Krok 2 — ak je ČITATEĽNÉ, priprav konfiguráciu (JSON), nie kód:**

Pozri `configs/_SCHEMA_DOCUMENTATION.json` pre **finálnu, záväznú štruktúru
feedu** (katalóg všetkých polí s vysvetlením, čitateľné slovenské názvy bez
skratiek) a `configs/hyundai_stock.json` pre funkčný, otestovaný príklad
(over si sám: `python tests/test_generic_config_scraper.py` dáva IDENTICKÉ
výsledky ako ručne písaný `scrapers/hyundai_stock.py`).

Konfigurácia popisuje:
- kde nájsť zoznam vozidiel (stránkovanie)
- ktoré polia vytiahnuť a akou metódou (`label_next_line`, `regex`,
  `regex_findall` pre zoznamy ako výbava, `image_list` pre obrázky)

**Overovanie obrázkov (dôležitá požiadavka):** Scraper po stiahnutí všetkých
vozidiel automaticky overí, že KAŽDÁ obrázková URL je verejne dostupná
(HTTP 200 + správny Content-Type) v čistej session bez cookies - presne to,
čo urobí prehliadač návštevníka tvojej stránky. Ak niektorý obrázok nie je
verejne dostupný (napr. vyžaduje prihlásenie alebo má expirovaný podpísaný
link), scraper to vypíše ako upozornenie. Túto kontrolu **nikdy nevynechávaj**
pri prvom nasadení novej značky (`--skip-image-check` je len na rýchle
testovanie počas vývoja).

**Voliteľná lokálna cache obrázkov** (`generic/image_cache.py`): namiesto
priamych odkazov na zdrojové URL (napr. `mbpanonska.sk/...`) môže scraper
obrázky stiahnuť raz do lokálnej cache na tvojom serveri a vo feede použiť
tvoju vlastnú URL. Výhody:
- **Spoľahlivosť** - obrázok zostane vo feede aj keď zdroj fotku zmaže/presunie
- **Výkon** - opakované hodinové behy NEsťahujú znova to, čo už majú (stabilný
  hash z URL = rovnaký súbor sa nájde v cache a preskočí)

Zapneš to v configu (pozri `configs/_SCHEMA_DOCUMENTATION.json` sekciu
`image_cache_volitelne`):
```json
"image_cache": {
  "enabled": true,
  "cache_dir": "output/images/hyundai",
  "image_base_url": "https://roanty.sk/images/hyundai"
}
```
`cache_dir` je lokálny priečinok na serveri; `image_base_url` je verejná URL,
na ktorej ten istý priečinok servuje tvoj web server (nginx/Apache alias) -
toto nastavenie webservera je jednorazová vec mimo scrapera. Otestované na
scenári "URL zdroja už neexistuje, ale súbor je v cache" - funguje bez
sieťovej chyby (`tests/test_image_cache.py`).

Spustenie:
```bash
python -m generic.config_scraper --config configs/hyundai_stock.json --output output
```

**Prečo takto:** keď mi pošleš inštrukcie pre nový feed (aké polia, aké tagy),
namiesto písania novej `scrapers/<brand>.py` triedy len napíšem
`configs/<brand>.json` — rýchlejšie, menej náchylné na chyby, a ty (alebo
ktokoľvek iný) vieš config upraviť aj bez programovania, len podľa vzoru.

**Dva typy feedov, dva rôzne zdroje dát:**
1. **Katalógové** (`skoda`, `hyundai`, `vw`) — generické modely/motorizácie
   z webu výrobcu, orientačná cena "od". Štruktúra `<feed><model>...`.
2. **Skladové** (`hyundai-stock`) — REÁLNE konkrétne vozidlá na sklade
   za CELÚ sieť predajcov danej značky, s reálnou cenou, km, VIN,
   konkrétnym predajcom. Štruktúra `<cars_feed><auto>...` (podľa
   vzoru, ktorý si mi ukázal zo standout.sk).

## hyundai-stock — nový, dôležitý feed

Zdroj: `skladove.hyundai.sk` — to je centrálny sklad Hyundai
importéra, agregovaný za všetkých predajcov na Slovensku (Žilina,
Banská Bystrica, Košice, Zvolen...), nie jeden konkrétny predajca.

```bash
python main.py --brand hyundai-stock
```

Vygeneruje `output/hyundai-stock_feed.xml` so štruktúrou:
```xml
<cars_feed znacka="hyundai" generovane="..." zdroj="..." krajina="SK">
  <auto>
    <id>6475</id>
    <title>Hyundai TUCSON TUC FL 1,6T 2WD BLACK ED MY27</title>
    <znacka>Hyundai</znacka>
    <model>TUCSON</model>
    <cena mena="EUR">28390.0</cena>
    <cena_povodna>35530.0</cena_povodna>
    <zlava>7140.0</zlava>
    <najnizsia_cena_30_dni>31630.0</najnizsia_cena_30_dni>
    <najazdene_km>10</najazdene_km>
    <palivo>Benzín</palivo>
    <objem_motoru>1598</objem_motoru>
    <vykon_kw>110</vykon_kw>
    <prevodovka>Manuálna</prevodovka>
    <typ_karoserie>SUV</typ_karoserie>
    <farba>Zelená Matná</farba>
    <vin>TMAJD81B0VJ749961</vin>
    <poloha>Žilina</poloha>
    <predajca><nazov>ALTERIA MOTOR</nazov><email>...</email></predajca>
  </auto>
  <!-- ... ~636 vozidiel -->
</cars_feed>
```

**Dôležité pred ostrým behom:**
- Celý sklad = ~27 stránok listingu + ~636 detailových requestov =
  ~660 HTTP requestov na jeden bežný feedu. Scraper má vstavané malé
  pauzy (`request_delay_s = 0.3`) — buď ohľaduplný, nespúšťaj to
  paralelne na viacerých vláknach ani častejšie než raz za hodinu.
- Over cenu/km/VIN na 2-3 vozidlách voči tomu, čo vidíš v prehliadači,
  než to nasadíš na produkciu.
- `title`/`znacka`/`model` sa parsujú z `<h1>`/`<h2>` stránky — over,
  že to sedí aj pri iných modeloch než Tucson (rôzne modely môžu mať
  drobne inú štruktúru nadpisov).

**Ďalší kandidát na rovnaký prístup: Audi.** `skladove-vozidla.audi.sk`
je tiež server-rendered centrálny sklad za celú sieť Audi predajcov
(Autonovo, Araver, Moris, Audi Centrum...), s ešte bohatšími dátami
(cena rozpísaná po jednotlivých kusoch príplatkovej výbavy,
financovanie). Jediné upozornenie: detail vozidla má
`meta-robots: noindex, nofollow` — nie technický zákaz, ale signál
neindexovať/nekrawlovať do hĺbky, takže by to chcelo byť extra
ohľaduplné (nižšia frekvencia). VW má naopak `robots.txt`, ktoré
automatizovaný prístup explicitne zakazuje — to sa nescrapuje.

## Prehľad značiek na slovenskom trhu — stav a odporúčaný postup

Na Slovensku sa v roku 2026 predáva približne 30+ značiek nových áut
(vrátane rastúceho počtu čínskych ako BYD, MG, Chery, Omoda, Jaecoo,
GWM). Plnohodnotné, overené scrapery pre všetky naraz nie je realistické
odovzdať v jednom kole práce — každá značka má inú štruktúru webu a
nasadenie neoverenej logiky na produkčný porovnávač s reálnymi cenami
je riziko (zlá cena je horšia než chýbajúca cena). Preto postupujeme
po vlnách, podľa toho, čo som stihol technicky preveriť:

| Značka / zdroj | Typ | Stav | Poznámka |
|---|---|---|---|
| **Hyundai sklad** (`skladove.hyundai.sk`) | Stock | Hotovo | Reálne vozidlá, celá sieť predajcov, server-rendered |
| **Škoda** (katalóg) | Catalog | Hotovo | Motor/výkon v HTML, cena len PDF |
| **Hyundai** (katalóg) | Catalog | Hotovo | Cena AJ parametre v HTML (výbava+cena) |
| **Volkswagen** (katalóg) | Catalog | Hotovo (čiastočne overené) | Úvodná cena v HTML, `/motory` podstránka neoverená do detailu |
| Audi sklad (`skladove-vozidla.audi.sk`) | Stock | Preverené, nepostavené | Server-rendered, bohaté dáta, over noindex signál |
| Kia (katalóg) | Catalog | Preverené, nepostavené | Rovnaký vzor ako Škoda (PDF cenník) |
| Audi/SEAT/Cupra (katalóg) | Catalog | JS-SPA | `audi.sk` je React/Vue SPA, potrebuje Playwright |
| VW sklad (`stockcars.porscheinformatik.com`) | Stock | Zakázané | robots.txt explicitne zakazuje automatizovaný prístup |
| Škoda sklad (`webapps.skoda-auto.sk/stock-cars`) | Stock | JS-SPA | Potrebuje Playwright |
| BMW, Mercedes-Benz, Toyota, Ford, Renault, Dacia, Peugeot, Citroën, Opel, Mazda, Suzuki, Nissan, Volvo, Mitsubishi, Honda | ? | Nepreverené | Treba individuálne overiť typ webu aj to, či majú "skladové vozidlá" agregát |
| ~20 čínskych značiek | ? | Nepreverené | Mnohé sú na trhu len krátko, weby sa menia rýchlo |

**Odporúčaný postup:** over si `hyundai-stock` feed na produkčných
dátach (porovnaj 3-5 vozidiel s tým, čo vidíš v prehliadači). Keď
sedí, dám ti vedieť a pokračujeme — buď na Audi sklad (rovnaký
prístup, over noindex), alebo katalógové feedy pre ďalšie značky.

## Čo katalógový feed obsahuje

Pre každý model: názov, URL, konfigurátor, úrovne výbavy, zoznam
motorizácií (výkon, palivo, prevodovka, max. rýchlosť, zrýchlenie,
krútiaci moment) a — kde je dostupné v HTML — **reálnu cenu**.

**Škoda**: cena vozidla NIE JE priamo v XML ako číslo — Škoda publikuje
ceny len ako PDF cenníky. Feed obsahuje link na aktuálny PDF
(`price_list_pdf`). Technické parametre (motor, výkon...) SÚ v HTML.

**Hyundai (katalóg)**: cena JE priamo v HTML, rozpísaná po jednotlivých
úrovniach výbavy (`<variants><variant><trim>COMFORT</trim>
<price_from_eur>14240.0</price_from_eur>...`).

**Volkswagen**: úvodná "od X €" cena je priamo v HTML na hlavnej
stránke modelu. Detailné motorizácie sú na podstránke `/motory`,
ktorú scraper skúša naparsovať rovnakým parserom ako Škoda — over
výsledok pred nasadením.

## Rýchly start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python main.py --brand skoda
python main.py --brand hyundai
python main.py --brand hyundai-stock
python main.py --brand vw

python main.py --all --output /var/www/roanty-feeds
```

## Test bez internetu

Každý parser má test na reálnej fixture (skutočný text zo stránky),
takže vieš, že logika funguje ešte pred nasadením:

```bash
python tests/test_skoda_parser.py
python tests/test_hyundai_parser.py
python tests/test_hyundai_stock_parser.py
```

## Nasadenie cez GitHub (bez servera) — odporúčané, ak nemáš VPS

Namiesto vlastného servera môže **GitHub Actions** spúšťať scraper
každú hodinu zadarmo, a **GitHub Pages** zverejní výsledné XML na
stabilnej URL. Žiadny cron, žiadna nginx konfigurácia, žiadna údržba
servera.

**Krok za krokom:**

1. Vytvor si účet na [github.com](https://github.com), ak ho nemáš.
2. Vytvor nový **verejný** repozitár (napr. `roanty-car-feeds`) —
   GitHub Pages je zadarmo len pre verejné repozitáre (alebo platený
   GitHub Pro pre súkromné).
3. Nahraj do neho obsah tohto priečinka (buď cez webové rozhranie
   "Upload files" — jednoducho potiahneš celý rozbalený priečinok,
   alebo cez `git`, ak ho poznáš).
4. V repozitári klikni na záložku **Settings → Pages**. Pri "Source"
   vyber **"Deploy from a branch"**, branch **`gh-pages`**, priečinok
   **`/ (root)`**. (Branch `gh-pages` sa objaví v zozname až po prvom
   úspešnom behu workflow — pozri krok 5.)
5. Klikni na záložku **Actions**. Mal by tam byť workflow "Aktualizácia
   XML feedov" (je v `.github/workflows/update-feeds.yml`, ktorý som
   pripravil). Klikni na neho a potom na **"Run workflow"** — spustí sa
   ručne prvýkrát, aby si nemusel čakať na celú hodinu.
6. Po cca 2-5 minútach (behu scrapera) sa v Settings → Pages objaví
   zelená URL adresa typu `https://<tvoj-github-username>.github.io/roanty-car-feeds/`.
   Feed pre jednu značku bude na
   `https://<tvoj-github-username>.github.io/roanty-car-feeds/hyundai-stock_feed.xml`
7. Odteraz sa workflow spustí **automaticky každú hodinu** sám —
   nemusíš nič robiť. Feed sa priebežne aktualizuje na tej istej URL.

**Čo môže pokaziť tento postup:**
- Ak sa scraper na niektorej značke rozbije (web sa zmenil), workflow
  môže zlyhať pre všetky značky naraz, ak `--all` skončí s chybou. Ak
  to nastane, over záložku "Actions" — uvidíš tam presný chybový výpis.

## Alternatíva: vlastný VPS server

Ak by si namiesto GitHubu chcel vlastný server, pozri
`deploy/crontab.example` a `deploy/roanty-feeds.service` + `.timer`
(systemd) — postup je v komentároch tých súborov.

## Právna poznámka (dôležité, nezabudni)

Väčšina automobilových stránok má v podmienkach používania obmedzenia
na automatizované sťahovanie dát a niektoré majú anti-bot ochranu.
Feed sa preto môže kedykoľvek "rozbiť" a treba počítať s priebežnou
údržbou. Odporúčam:

- Overiť, či niektorý importér/značka neponúka oficiálny B2B dátový
  feed pre porovnávače (stabilnejšie a bez právneho rizika).
- Rešpektovať `robots.txt` a signály typu `meta-robots: noindex` —
  ak stránka explicitne zakazuje automatizovaný prístup (ako VW sklad),
  nescrapovať ju, nech je akokoľvek lákavá.
- Nepreťažovať cieľové servery — hodinový interval je v poriadku,
  nespúšťať scraper paralelne na desiatkach vlákien.
