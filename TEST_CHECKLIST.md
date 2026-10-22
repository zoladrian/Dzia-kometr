# Checklista testów

Przykłady na prawdziwych danych:

- `080104_2.0002.27/89`: Kłodawa, Jesionowa 19, akt z 14 września 2026, 410 000 zł, jedyna działka w akcie.
- `080104_2.0002.1235/4`: Kłodawa, próbka geometrii ULDK.

Status: `[x]` uruchomione i zaliczone, `[ ]` nie sprawdzone automatycznie, `[!]` znany problem.

## Polecenia

```powershell
$env:LANDSCOPE_CHROMIUM_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$env:TEMP = (Resolve-Path reports\tmp).Path; $env:TMP = $env:TEMP     # domyślny TEMP odrzuca zapis (WinError 5)
.venv\Scripts\python.exe -m pytest -m "not integration and not online and not e2e" -p no:cacheprovider --basetemp reports\tmp
.venv\Scripts\python.exe -m pytest --integration -p no:cacheprovider --basetemp reports\tmp
.venv\Scripts\python.exe -m pytest tests/test_online.py tests/test_reconciliation.py tests/test_e2e.py --online --real-data --e2e -p no:cacheprovider --basetemp reports\tmp
.venv\Scripts\python.exe -m landscope ui-check --parcel 080104_2.0002.27/89 --parcel 080104_2.0002.1235/4
.venv\Scripts\python.exe -m landscope card 080104_2.0002.27/89
.venv\Scripts\python.exe -m landscope address "Kłodawa, Gorzowska 40"
```

Zrzuty ekranu: `test-results/ui/`.

## 1. Dane i import

- [x] Import GML powiatu: 13670 obserwacji, 0 odrzuceń (`import-rcn`).
- [x] Ponowny import nie dubluje sprzedaży, działek ani obserwacji; dopisuje tylko nową wersję surowego dowodu (`counts` przed i po).
- [x] Cena działki z pola `cenaDzialkiEwidencyjnejBrutto`; 1550 cen w bazie (`test_card.py::test_parcel_price_field_and_details`).
- [x] Wiele adresów działki jest zachowanych (`test_card.py`).
- [x] Nazwisko notariusza (`tworcaDokumentu`) nie trafia do danych publicznych (`test_card.py`).
- [x] Zapisane rekordy Kłodawy zgadzają się z GML (`test_reconciliation.py`).
- [x] Idempotencja, wersje i odrzucenia na prawdziwym PostGIS (`test_integration.py`).

## 2. Ceny i statystyki

- [x] Cena aktu nigdy nie jest ceną działki; pakiet dostaje własną podstawę i nie wchodzi do mediany (`test_card.py::test_package_never_allocated`, `test_integration.py::test_packages_never_allocate_total`).
- [x] Cena za m² ma podaną podstawę: cena działki albo cena aktu, gdy akt obejmuje wyłącznie tę jedną działkę gruntu w całości.
- [x] Jesionowa 19: 410 000 zł / 1903 m² = 215,45 zł/m² (`card`, `ui-check`).
- [x] Statystyki rozdzielone według kategorii, pojedynczej działki lub pakietu, rynku, prawa i roku; widok startowy ma grupy z medianą (`ui-check`, panele).
- [x] Mediana jednego obszaru zgodna z SQL (`test_integration.py::test_statistics_median_matches_sql`).

## 3. API

- [x] `/api/parcel/card`, `/api/transactions/{id}/card` i 404 dla brakujących (`test_integration.py::test_card_endpoints_and_map_labels`).
- [x] `/api/map` przy zbliżeniu: jedna pozycja na działkę z numerem, etykietą i flagą „moja” (`test_integration.py`).
- [x] `/api/map` przy oddaleniu: grupy plus pinezki „moich działek” (`test_integration.py`).
- [x] `/api/address` odrzuca zbyt krótkie zapytanie (422).
- [x] Filtry, bbox, paginacja i błędne parametry (`test_contracts.py`, `test_integration.py`).

## 4. Źródła (osobno, na żywo)

- [x] RCN WFS, RCN powiatu, ULDK, punkty adresowe GUGiK (UUG): PASS (`test_online.py`).
- [x] EGiB, MPZP, GESUT, GDOŚ, ISOK, BDOT10k, ortofoto, NMT: celowo UNAVAILABLE z podanym powodem.
- [x] Adres „Kłodawa, Gorzowska 40” prowadzi do działki w gminie Kłodawa (`address`, `test_e2e.py::test_address_search_finds_parcel`).

## 5. Interfejs: każda wartość na swoim miejscu (`ui-check`: komputer 1440×900, telefon 390×844, mały telefon 320×568, tablet 768×1024)

- [x] Każdy wiersz karty ma tę samą etykietę, wartość i status co API, w tej samej kolejności.
- [x] Każda wartość jest widoczna i mieści się w szerokości ekranu.
- [x] Tytuł karty odpowiada etykiecie z „Moich działek” albo numerowi działki.
- [x] Działka ma na mapie podpis (numer albo „★ etykieta”).
- [x] Prawdziwe kliknięcie myszą wewnątrz działki otwiera jej kartę.
- [x] Kafelki mapy się ładują.
- [x] Brak błędów JavaScript.

## 6. Interfejs: układ i ucinanie (wzór: Deweloperuch, mapa cen transakcyjnych)

- [x] Komputer: lista kart transakcji po lewej, mapa po prawej, pasek „Gdzie? / Za ile? / Ile m²? / Filtry” nad mapą.
- [x] Komputer: karta działki zastępuje listę po lewej (szersza kolumna); „← Wróć” wraca do listy.
- [x] Telefon: mapa na cały ekran, pole „Gdzie?” u góry, dolny pasek „N transakcji”; „▲” rozwija listę.
- [x] Telefon: karta wysuwa się od dołu, przycisk powiększenia rozwija ją na cały ekran, koniec karty jest osiągalny.
- [x] „Filtry” otwierają panel (na telefonie od dołu) i zamykają się bez śladu.
- [x] Legenda: mediana ceny za m² w widoku i skala z jednostką.
- [x] Kafelki podsumowania (4) z wartością w jednej linii.
- [x] Karty listy: cena, cena za m² i „Szczegóły →” w jednej linii.
- [x] Elementy z atrybutem `hidden` są naprawdę ukryte.
- [x] Obrys działki ma realny rozmiar i kolor wypełnienia.
- [x] Kolor działki nie zmienia się przy przybliżaniu (skala dla powiatu, nie dla widoku).
- [x] Telefon: po otwarciu karty działka jest widoczna nad wysuniętym panelem.
- [x] Brak przewijania w poziomie na obu ekranach.
- [x] Brak uciętych tekstów, wielokropków i elementów poza ekranem: karta, panele, nagłówek.
- [x] Nic nie jest przykryte innym elementem; sprawdzane przez `elementFromPoint` w środku każdego tekstu.
- [x] Tablet w pionie (768×1024) i mały telefon (320×568).
- [x] Telefon: po otwarciu karty działka jest przybliżona (zoom ≥ 16) i w całości między paskiem wyszukiwania a kartą.
- [x] Duży akt (28 działek): karta się otwiera, bez poziomego scrolla dokumentu; nie sprawdzano każdej wartości z osobna.
- [ ] Tryb ciemny i powiększenie tekstu przeglądarki (200%).

## 7. Interfejs: przepływy

- [x] Wyszukiwanie po identyfikatorze działki.
- [x] Wyszukiwanie po adresie.
- [x] Z karty działki do karty całego aktu.
- [x] Filtr bez wyników pokazuje komunikat.
- [x] Rysowanie obszaru i statystyki dla zaznaczenia (`test_e2e.py::test_pagination_sort_favorite_and_draw_area`).
- [x] Dodawanie i usuwanie z „Moich działek” z poziomu UI (ten sam test).
- [x] „Wskaż działkę” na mapie (ULDK po punkcie albo komunikat o braku/niedostępności).
- [x] Paginacja i sortowanie listy w przeglądarce.
- [x] Przy niedostępnym ULDK/UUG UI pokazuje komunikat, nie pustą kartę (`test_e2e.py::test_search_shows_message_when_uldk_unavailable`).

## Pominięte lub dopisane w trakcie

Każdy błąd poniżej był widoczny na zrzucie, a pierwsza wersja kontroli go nie wykryła. Do kontroli dopisano regułę i sprawdzono, że na starej wersji zgłasza FAIL, a po poprawce PASS.

| Błąd | Gdzie | Nowa kontrola | Poprawka |
|---|---|---|---|
| Przyciski +/− i stopka mapy na panelach Szukaj i Filtry | telefony, tablet | „nic nie jest przykryte” (`elementFromPoint`) | panele nad warstwą sterowania mapy |
| Data i cena łamane na dwie linie („2026-/09-18”) | lista na telefonie | „tabela: data i cena w jednej linii” (liczy linie tekstu, nie wysokość komórki) | `white-space: nowrap` dla tych kolumn |
| Mapa oddalała się do grup, działka pod kartą | mały telefon | „działka przybliżona i w całości nad kartą” | odstęp liczony z położenia karty; karta zostawia ≥ 220 px mapy |
| Nagłówek łamany na dwie linie | mały telefon | „nagłówek w jednej linii” | krótszy tekst stanu bazy |
| Dwa przyciski „Szukaj” (formularz i pasek) | telefon | — (test wskazuje przycisk formularza) | do rozważenia: inna nazwa zakładki |
| Sprawdzenie źródła UUG na adresie bez punktu PRG (Jesionowa 19) | `test_online.py` | — | adres z punktem PRG: Kłodawa, Gorzowska 40 |
| Przyciski „Zakończ obszar” i „Usuń obszar” widoczne mimo `hidden` | komputer | „elementy z atrybutem hidden są ukryte” | `[hidden]{display:none!important}` |
| Obrysy działek niewidoczne, klik w działkę nie działał | wszystkie | „obrys działki narysowany w realnym rozmiarze” | reguła CSS dla ikon `svg` zmniejszała warstwę SVG mapy do 18 px |
| Ta sama działka turkusowa na komputerze, czerwona na telefonie | wszystkie | „kolor działki nie zmienia się po oddaleniu” | skala kolorów dla powiatu, mediana w legendzie dla widoku |
| Pole daty wychodzi poza panel filtrów | mały telefon | „panel filtrów: nic nie jest ucięte” | `fieldset{min-width:0}`, kolumny `minmax(0,1fr)` |
| Mini-logo „LS” w pionie | telefon | — (widoczne tylko na zrzucie) | `display:flex` |
| Ikona obok ceny za m² liczona jako druga linia | lista | fałszywy alarm | liczone są tylko linie tekstu |

Fałszywe alarmy usunięte z kontroli:

- treść przewinięta poza panel (brana jest tylko widoczna część kontenera);
- ukryte przyciski radiowe (`opacity: 0`);
- zawartość zwiniętego `<details>`, której nowszy Chrome zostawia wymiary;
- wysoki koniec karty (sprawdzany jest ostatni wiersz po przewinięciu do końca).

Jeszcze nie sprawdzane automatycznie: tryb ciemny i powiększenie tekstu 200%.

## Poprawki po audycie CLI — 2026-10-22, później

Audyt zostawił AUD-01–07 bez zmian w kodzie. Poniżej wynik tej samej listy po poprawkach
i ponownym uruchomieniu testów (nie zastępuje historycznego raportu audytu w PROGRESS.md).

| ID | Status | Dowód |
|---|---|---|
| AUD-01 skala/mediana mapy | naprawione | skala tylko `unbuilt` (albo jedna zaznaczona kategoria), wyłącznie jedna działka w akcie; live `/api/map` count=1970, mediana 46,57 zł/m²; `test_map_scale_*` |
| AUD-02 powielona nieruchomość | naprawione | `property` 13 670 → 10 575, 0 grup duplikatów; akt 28 działek ma 1 nieruchomość; `test_confirmed_gml_property_*`, `test_initialize_merges_*` |
| AUD-03 E2E vs UI | naprawione | `tests/test_e2e.py --e2e --online --real-data`: **6 PASS** |
| AUD-04 polygon 503 | naprawione | `{}` / `null` / `[]` / `1` → 422 na transactions/map/statistics; `test_api_contract_validation` |
| AUD-05 ulubione poza bbox | naprawione | `/api/map?bbox=20,50,21,51&zoom=8` bez pinezek spoza zakresu; `test_card_endpoints_and_map_labels` |
| AUD-06 puste kategorie | naprawione | odznaczenie trzech kategorii czyści listę, medianę (`brak`) i statystyki |
| AUD-07 CLI `test -m unit` | naprawione | `python -m landscope test -m unit`: 25 PASS |

Bieżący pytest (ta sesja):

- offline: **46 PASS** (`not integration and not online and not e2e`)
- integracje PostGIS: **11 PASS**
- E2E + ui-check: **6 PASS** (2 działki × 4 ekrany w `test_example_parcels_every_value_desktop_and_phone`)

Nadal otwarte: tryb ciemny, powiększenie 200%, pełna diagnostyka 12 źródeł w tej sesji
(wcześniej RCN/ULDK/UUG: PASS; MPZP/GESUT/…: UNAVAILABLE z powodu).
