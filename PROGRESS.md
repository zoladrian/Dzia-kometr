# Postęp — 2026-10-22

## Stan odbioru

Lokalne MVP powiatu gorzowskiego działa. Interfejs: http://127.0.0.1:8000
(w LAN na porcie 8000, baza tylko `127.0.0.1:15432`). Uruchomienie: Docker Desktop
+ `scripts/start.ps1` (Windows) albo `scripts/start.sh` (macOS); potem `import-rcn`.
Zdalny dostęp: `.\scripts\share-link.ps1` (tunel HTTPS). Nie wystawiaj portu 8000 ani 15432 na routerze.
AUD-01–07 z audytu CLI są zamknięte — [poprawki po audycie](#poprawki-po-audycie--2026-10-22).
W UI, pod logo, wybiera się powiaty trzymane lokalnie (380 kodów TERYT). Domyślnie
zaznaczony jest gorzowski; na górze listy są gorzowski i miński (Arynów).

Import pochodzi z GML powiatu (dane.gov.pl), stan na 2026-10-14, plik
`https://api.dane.gov.pl/media/resources/20261016/0801.zip`.

| Miara | Wartość |
|---|---|
| Obiekty transakcji w pliku | 7908 |
| Sprzedaże w bazie | 7907 |
| Nieruchomości (po scaleniu AUD-02) | 10575 |
| Obserwacje działek | 13670 |
| Unikalne działki | 8627 |
| Odrzucenia | 0 |
| Obserwacje bez geometrii | 240 |
| Daty dokumentów | 2006-11-09 – 2026-10-09 |
| Cena nieruchomości ≤ 0, oznaczona, niewliczona do ceny/m² | 5394 |

Jedna transakcja z pliku nie ma powiązanej działki, dlatego sprzedaży jest 7907.
Cena aktu nie jest zapisywana jako cena działki. Cena/m² powstaje tylko z ceny tej działki,
dodatniej powierzchni, pełnego udziału i rozpoznanej kategorii.

Próbka Kłodawy, ziarno 8012026, 5 działek z 367 dopasowań. ULDK zapisał granice czterech.
`080104_2.0002.105/9` wróciło z ULDK jako błąd XML usługi powiatowej. Sprawdzona w mapie
działka `080104_2.0002.1235/4`: gmina Kłodawa, sprzedaż 2022-09-30 za 335000 zł całego aktu,
karta mówi, że to nie jest cena pojedynczej działki.

Aktualne MPZP, uzbrojenie, powódź i ochrona przyrody są na karcie jako niedostępne.
W pliku RCN jest tylko przeznaczenie zapisane przy sprzedaży.

## Testy tej sesji

| Polecenie | Wynik |
|---|---|
| pytest --integration, TEMP=reports/tmp | **46 PASS**, 14 SKIP (online i e2e wymagają osobnych flag) |
| pytest tests/test_online.py tests/test_reconciliation.py tests/test_e2e.py --online --real-data --e2e | **14 PASS** |
| Mapa w przeglądarce | klastrowanie, wyszukanie działki, karta transakcji, filtr bez wyników |
| pytest tests/test_powiaty.py tests/test_counties_api.py | **14 PASS**; katalog: 0801 i 1412 na górze, nazwy TERYT z polskimi znakami |
| Wybór powiatów w UI | gorzowski zaznaczony, miński (Arynów) na górze, wyszukanie „arynow”, zapis dwóch powiatów |

Źródła: `rcn`, `rcn_county` i `uldk` mają PASS. Osiem pozostałych ma UNAVAILABLE,
bo capabilities albo strona informacyjna nie są kontraktem danych działki.
Raport: `reports/sources.json`.

Domyślny katalog tymczasowy Pythona na tym koncie odrzuca zapis (`WinError 5`).
Testy importu uruchomiono z `TEMP` i `--basetemp` wskazującymi `reports/tmp`.

## Karta działki i interfejs — 2026-10-22, później

- Naprawiono gubienie cen działek: schemat 1.5 używa `cenaDzialkiEwidencyjnejBrutto`. Po ponownym imporcie jest 1550 cen.
  Liczby sprzedaży, działek i obserwacji się nie zmieniły.
- Import zapisuje też budynki, lokale, VAT, opisy, wszystkie adresy działki i rodzaje stron (bez notariusza).
- Cena za m² ma podaną podstawę; akt obejmujący wyłącznie jedną działkę gruntu w całości daje cenę za m² tej działki.
- Karta (`/api/parcel/card`, `landscope card`) to jedna lista wierszy wspólna dla API, UI, CLI i testów.
- Nowe źródło: punkty adresowe GUGiK (UUG). Diagnostyka używa adresu `Kłodawa, Gorzowska 40`.
- UI: na komputerze trzy kolumny; na telefonie mapa, zakładki na dole i karta wysuwana od dołu.
  Działki mają numery od przybliżenia 16, „moje działki” mają etykietę ze ★, klik w działkę otwiera kartę.
- Testy: bez sieci 45 PASS; PostGIS 51 PASS; online, porównanie z GML i e2e 17 PASS
  (źródła rcn, rcn_county, uldk i uug mają PASS).
  `ui-check`: 2 działki × 4 ekrany, 30 i 64 wartości na kartę, 0 błędów. Szczegóły: TEST_CHECKLIST.md.

## Wygląd jak Deweloperuch — 2026-10-22, później

Wzorowane na https://deweloperuch.pl/ceny-transakcyjne/polska/mapa (powiat gorzowski),
ale etykiety i lista dotyczą działek, nie mieszkań i domów.

- Paleta `#47317f`, Poppins, biała lista kart 76 px, pasek „Gdzie? / Za ile? / Ile m²? / Filtry”.
- Na mapie etykiety cen: zł/m² gdy jest uzasadniona, w przeciwnym razie kwota aktu (`410k` / `1,2 mln`); przy przybliżeniu 15+ obrys działki i numer.
- `ui-check` 2 działki × 4 ekrany: **PASS**, 40 i 75 wartości na kartę. Zrzuty: `test-results/ui-restyle-check/`.

## Poza tym MVP

Pełna warstwa granic EGiB, bieżące MPZP, GESUT, GDOŚ, powódź, BDOT10k, ortofoto i NMT
nie są adapterami karty działki. Wyceny nie ma. Starszych miesięcznych ZIP-ów nie importowano:
to poprzednie stany tego samego rejestru.

## Audyt CLI na zlecenie użytkownika — 2026-10-22

**To jest historyczny raport audytu (bez zmian w kodzie).** AUD-01–07 zamknięto
w tej samej dobie — [poprawki po audycie](#poprawki-po-audycie--2026-10-22),
[BACKLOG.md](BACKLOG.md#błędy-z-audytu-2026-10-22--zamknięte-w-tej-samej-dobie).

### Faktycznie wykonane testy

| Zakres | Wynik bieżącego uruchomienia | Dowód |
|---|---|---|
| Offline: domena, geometria, kontrakty, karta, przepływ importu | **45 PASS**, 23 deselected | `reports/audit-20261022-offline.xml` |
| Integracje na rzeczywistym PostGIS, w izolowanych schematach | **6 PASS** | `reports/audit-20261022-postgis.xml` |
| Diagnostyka 12 źródeł przez pytest | **12 FAIL testów**, każde źródło **UNAVAILABLE**, WinError 10013 | `reports/audit-20261022-online.xml`, `reports/online/*.json` |
| Porównanie 5 zapisanych rekordów Kłodawy z lokalnym oryginałem GML | **1 PASS**; bez świeżego pobrania z internetu | ten sam raport `online.xml`, test reconciliation |
| Istniejący zestaw Playwright, jawnie online + real-data + e2e | **4 FAIL** | `reports/audit-20261022-e2e.xml` |
| Ponowny import 28 prawdziwych rekordów jednego aktu, izolowany schemat | **PASS**; brak przyrostu transakcji, działek, obserwacji, nieruchomości i surowych rekordów; nowy wpis import_run | `reports/audit-20261022-county-idempotence.json` |
| Porównanie statystyk API z niezależnym grupowaniem rekordów odczytanych SQL | **185 grup zgodnych**: liczności, wykluczenia, mediana, min, max; sumy histogramów zgodne | `reports/audit-20261022-data.json`, `reports/audit-20261022-review.json` |
| Rachunek cen działki / powierzchnia, zaokrąglenie do groszy | **1106 sprawdzonych, 0 rozbieżności** | `reports/audit-20261022-data.json` |
| Rzeczywiste HTTP API: walidacja, filtry, sortowanie, strony, bbox, trzy skale mapy, karty, 404 i brak publicznego endpointu raw | Wykonane; błędne polygon → 503 i ulubione poza bbox potwierdzone | `reports/audit-20261022-api.json`, `reports/audit-20261022-validation.json` |
| Dodatkowy Playwright używający obecnych kontrolek UI | Wyniki poniżej; nie zastępuje czerwonego zestawu pytest | `reports/audit-20261022-ui-extra.json`, `reports/audit-20261022-ui-followup.json` |
| Docker / odtworzenie środowiska Compose | **UNAVAILABLE**: odmowa dostępu do konfiguracji Dockera i named pipe silnika | CLI `docker compose ps`, `docker compose exec -T app ...` |

Łącznie istniejące testy pytest: **68 wykonanych, 52 PASS, 16 FAIL**.
W tej sumie 12 porażek wynika z blokady połączeń zewnętrznych, a 4 z zestawu E2E.
Nie oznacza to 16 niezależnych błędów aplikacji. Nie użyto mocków do zaliczenia
integracji źródeł. Brak dostępu do Dockera nie oznacza, że kontenery są wyłączone:
działająca aplikacja i baza były osiągalne przez lokalne porty 8000 i 55432.

### Stan rzeczywistych danych sprawdzony w bazie

- 7907 transakcji, 13 670 aktywnych obserwacji, 8626 działek z obserwacją RCN.
- Tabela `parcel` ma 8627 rekordów, bo obejmuje również działkę bez sprzedaży RCN.
- 1550 niepustych cen działek; 1106 obserwacji z podstawą `parcel_price` spełnia warunki ceny/m².
- 41 010 surowych rekordów, 3 wcześniejsze importy, 0 odrzuceń.
- 240 obserwacji bez lokalizacji; 0 niepoprawnych zapisanych geometrii, 0 błędnych SRID,
  0 obserwacji spoza kodu powiatu 0801. Daty: 2006-11-09–2026-10-09.
- Przy bbox `14,49,25,55` dostępnych przestrzennie jest 7780 transakcji. To nie jest
  pełna liczba 7907, ponieważ nie każda transakcja ma lokalizację.
- Dla bbox `15,52.3,15.8,53.1` API i niezależne SQL zwróciły po 5063 transakcje.
- W chwili audytu: 1969 grup powielonej tożsamości nieruchomości (13 670 wierszy
  `property` / 10 575 `source_id`). Po AUD-02: 10 575 nieruchomości, 0 duplikatów.

### Dodatkowa kontrola obecnego interfejsu

Z CLI uruchomiono Playwright bez dopisywania kodu do repozytorium. Potwierdzono:
20 rzeczywistych pozycji na pierwszej stronie, sortowanie ceny, przejście na
stronę `21–40 z 1135`, filtr bez wyników, wyszukiwanie pełnego ID i
`Kłodawa 27/89`, kartę `080104_2.0002.27/89` (75 wierszy zgodnych z API),
przejście do całego aktu oraz narysowanie wielokąta kliknięciami myszy
(HTTP 200, 39 grup statystyk). Długi akt z 28 działkami otworzył kartę z 1708
wierszami bez poziomego przewijania dokumentu. To sprawdzenie nie potwierdza
poprawności każdej z 1708 wartości ani ergonomii całej karty.

Na szerokościach 390, 320 i 768 px nie stwierdzono poziomego przewijania całego
dokumentu; nie jest to równoważne pełnemu zaliczeniu wszystkich kontrolek.
W dodatkowym przebiegu nie wystąpiły błędy `pageerror`. Zasymulowane w przeglądarce
HTTP 503 wyszukiwania pokazało komunikat zamiast pustej karty; jest to **test
obsługi błędu UI**, a nie test dostępności ULDK. Kafelki OSM: 0 załadowanych,
niezaliczone. Po odznaczeniu wszystkich kategorii pozostały stare statystyki
i mediana `85 zł`, mimo 0 transakcji — potwierdzony błąd.

Zrzuty: `test-results/audit-20261022-desktop.png`, `*-phone.png`,
`*-small-phone.png`, `*-tablet.png`, `*-long-card.png`.

### Ograniczenia i rzetelność wyników

- W trakcie audytu inne działania zmieniły `landscope/uicheck.py` i
  `landscope/static/style.css`; agent audytujący ich nie edytował. Na początku
  serwer podawał inny CSS niż plik lokalny, w późniejszym porównaniu pliki
  HTML/JS/CSS były już zgodne. Manifest początkowy:
  `reports/audit-20261022-code-hashes.json`. Nie jest to test jednego zamrożonego wydania.
- Pierwszy raport E2E obejmuje m.in. stare selektory, widoczne elementy `hidden`,
  obrysy 1–2 px i nieskuteczny klik działki na komputerze. Należy odróżnić ten
  wynik od późniejszych sprawdzeń po zewnętrznej zmianie CSS.
- Raport eksploracyjny API zawiera też alarmy samego skryptu kontrolnego:
  arbitralny próg liczby transakcji dla częściowego bbox, uszkodzone polskie
  znaki w potoku PowerShell i ponowne użycie połączenia zamkniętego po błędzie
  polygon. Powtórzenia wyjaśniające są w `reports/audit-20261022-review.json`.
  NaN zwraca poprawne 422 przy osobnym połączeniu; cena 215,45 zł/m² jest poprawna.
  Błąd wywołania `wait_for_function` w dodatkowym skrypcie paginacji poprawiono
  wyłącznie w poleceniu kontrolnym; ponowienie przeszło. To nie były usterki aplikacji.
- Nie odtworzono od zera obrazu, wolumenu ani importu całego powiatu z sieci.
  Nie wykonano testu przerwania rzeczywistego pobierania ZIP, pełnego audytu
  danych osobowych wszystkich pól opisowych, powiększenia tekstu 200% ani trybu ciemnego.
  Żadnego z tych sprawdzeń nie zaliczono domyślnie.
- Schemat testu ponownego importu został usunięty w `finally`. Dane testowe nie
  zostały dołączone do produkcyjnych tabel. Wyszukiwanie UI może odświeżyć cache ULDK.

### Polecenia odtworzenia głównych testów

Uruchomić z katalogu projektu; aplikacja i PostGIS muszą już działać.
Jeśli katalog `--basetemp` pochodzi z innej sesji, wskazać nową nazwę.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:LANDSCOPE_CHROMIUM_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:TEMP = Join-Path (Get-Location) 'reports/audit-20261022-browser-tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

.\.venv\Scripts\python.exe -m pytest -m 'not integration and not online and not e2e' -p no:cacheprovider --basetemp=reports/audit-20261022-rerun-tmp --junitxml=reports/audit-rerun-offline.xml
.\.venv\Scripts\python.exe -m pytest tests/test_integration.py --integration -p no:cacheprovider --junitxml=reports/audit-rerun-postgis.xml
.\.venv\Scripts\python.exe -m pytest tests/test_online.py tests/test_reconciliation.py --online --real-data -p no:cacheprovider --junitxml=reports/audit-rerun-online.xml
.\.venv\Scripts\python.exe -m pytest tests/test_e2e.py --online --real-data --e2e -p no:cacheprovider --junitxml=reports/audit-rerun-e2e.xml
.\.venv\Scripts\python.exe -m landscope ui-check --parcel 080104_2.0002.27/89 --parcel 080104_2.0002.1235/4 --out test-results/audit-rerun-ui
```

Testy sieciowe należy powtórzyć w sesji z dozwolonymi połączeniami. W tej sesji
odmowa gniazd sieciowych uniemożliwiła potwierdzenie bieżącego stanu źródeł.

### Końcowe ponowienie UI po zmianach zewnętrznych

`landscope ui-check --parcel 080104_2.0002.27/89 --parcel 080104_2.0002.1235/4
--out test-results/audit-20261022-ui-final`: **FAIL (8 błędów)**, wszystkie
dotyczą niezaładowanych kafelków OSM (2 działki × 4 ekrany). Kontrole wartości,
obrysów w rzeczywistym rozmiarze, podpisów, kliknięć, widoczności elementów
`hidden`, panelu filtrów i układu nie zgłosiły już pozostałych błędów.
Raport: `reports/audit-20261022-ui-final.txt`; zrzuty w podanym katalogu.
Nie należy przenosić wcześniejszych błędów układu do listy nadal odtwarzalnych
usterek tej późniejszej wersji. Pełne E2E pozostaje niezaliczone z powodu kafelków.

Końcowe porównanie SHA-256 wykazało zmiany zewnętrzne również w
`repository.py`, `static/app.js`, `static/index.html`, `tests/test_e2e.py`
i `tests/test_integration.py`, oprócz wcześniej zauważonych CSS/uicheck.
W testach E2E pojawiły się już poprawione selektory. Manifest:
`reports/audit-20261022-final-manifest.json`. Agent audytujący dopisywał tylko
dokumentację; wyniki pierwszego pełnego zestawu pozostają zachowane i opisują
stan w chwili jego uruchomienia. Zastany dodatkowy schemat `landscope_test_*`
nie został usunięty, ponieważ mógł należeć do równoległego procesu testowego;
własny schemat `landscope_audit_*` został usunięty.

Po zauważeniu nowych selektorów wykonano ponownie trzy testy E2E
(`-k 'not example_parcels'`): **2 PASS, 1 FAIL, 1 deselected**. Wyszukiwanie
rzeczywistej działki/historii/granicy oraz adresu domu przeszło. Test filtra
dochodzi już do poprawnego pustego wyniku i upada wyłącznie na 0 kafelków.
Dowód: `reports/audit-20261022-e2e-final-subset.xml`. Pełną kontrolę kart
reprezentuje oddzielny końcowy `ui-check` opisany powyżej, nie pominięty test pytest.
Końcowe HTTP ponownie potwierdziło 200 health, 503 dla `polygon={}` oraz
2 ulubione poza bbox (`reports/audit-20261022-final-smoke.json`).

## Poprawki po audycie — 2026-10-22

Kod i testy po AUD-01–07. Obraz Dockera przebudowany (`docker compose up -d --build app`).

| ID | Zmiana |
|---|---|
| AUD-01 | Skala i mediana mapy: jedna kategoria (domyślnie niezabudowane), tylko akt z jedną działką. Inne kategorie na mapie są szare. |
| AUD-02 | GML: jedna nieruchomość na `(sale, source_id)`. `initialize()` scala stare kopie zestawem SQL SHA-256. |
| AUD-03 | E2E pod obecne kontrolki UI; 6 PASS. |
| AUD-04 | Polygon bez `type` / `null` / tablica → 422, nie 503. |
| AUD-05 | Ulubione i działki bez RCN tylko w bbox/polygon. |
| AUD-06 | Odznaczenie kategorii czyści listę, legendę i statystyki. |
| AUD-07 | `python -m landscope test` przekazuje argv do pytest. |

Baza po scaleniu: 7907 transakcji, 10575 nieruchomości (było 13670), 8627 działek, 13670 obserwacji, 0 duplikatów `confirmed (sale_id, source_id)`. Akt 28 działek ma 1 nieruchomość.

Testy tej sesji: offline 46 PASS, integracje 11 PASS, E2E 6 PASS, `landscope test -m unit` 25 PASS. Live: skala `unbuilt` 1970 / 46,57 zł/m²; polygon `{}` 422; ulubione poza bbox 20–21°: 0.

Pozostało poza MVP: tryb ciemny, powiększenie 200%, MPZP/GESUT/powódź/przyroda.

## działkometr — przebudowa UI/UX, 2026-10-22

Zakres tej sesji: tylko frontend i jego weryfikacja. Pobrano wskazany skill Anthropic
`frontend-design` do `skills/frontend-design/SKILL.md` (wersja pliku z GitHub,
SHA `a5333457c414d20d625f307df945842c0952ecc3`). Zastosowano go bez instalacji globalnej.

- Nazwa i identyfikacja „działkometr”, własny znak działki i favicon, zielona oprawa,
  czytelna lista i karta, skróty do zapisanych działek/statystyk. Starsze transakcje
  mają etykietę wieku zamiast wyszarzonych cen. Brak zależności od Google Fonts.
- Filtry: stały pasek zatwierdzania, walidacja zakresów, widoczny komunikat błędu,
  pułapka fokusu, przywracanie fokusu, Escape zamykający tylko dialog, tło `inert`.
- Telefon: krótkie podpowiedzi pól, przyciski z nazwami dostępnymi dla czytników,
  zwijanie karty do mapy i ponowne otwieranie, przewijanie karty przy niskim oknie,
  uwzględnienie safe area i preferencji ograniczonego ruchu.
- `interface.css` zawiera oprawę UI. Porównanie z kopią sprzed zmian potwierdziło
  identyczny `style.css` i niezmienione funkcje rysowania mapy, skali kolorów,
  legendy, pozycjonowania geometrii i inicjalizacji mapy. Bez zmian backendu/importu.

Weryfikacja wykonana z CLI na działającej aplikacji `http://127.0.0.1:8000`,
na bazie z 7907 transakcjami, 8627 działkami i 13670 obserwacjami:

| Sprawdzenie | Wynik i dowód |
|---|---|
| Offline backend/regresje | **47 PASS**, `reports/ui-offline.xml` |
| UI na rzeczywistych lokalnych danych, bez mocków | **14 PASS**, `reports/ui-design-final.xml` |
| Powtórzenie kontroli kart po końcowych zmianach etykiet | **4 PASS**, `reports/ui-mobile-final.xml` |
| Rozmiary UI | 1440×900, 1280×720, 1024×768, 900×700, 768×1024, 390×844, 320×568, 844×390, 720×450; brak przycięć/zasłonięć sprawdzanych paneli |
| Karty dwóch rzeczywistych działek na 4 ekranach | **460 wierszy zgodnych z API**, bez błędów układu; `reports/ui-design-cards.json` |
| Pełne `ui-check` | **189/197 kontroli PASS; 8 FAIL wyłącznie na braku kafelków mapy**, po jednej kontroli kafelków na każdą kartę/ekran |
| Dotychczasowe E2E | Wyszukiwanie adresu i komunikat niedostępności ULDK PASS (`reports/ui-existing-e2e.xml`); historia/granica PASS po poprawie oczekiwania na asynchroniczny rysunek (`reports/ui-history-final.xml`) |
| Składnia JS | `node --check landscope/static/app.js` PASS |

Obejrzano zrzuty komputera, telefonu 390 px, małego telefonu 320 px, wąskiego
komputera 900 px oraz filtrów i kart. Poprawiono za długie podpowiedzi pól,
widoczność walidacji i przewijanie karty na niskim ekranie. Zrzuty końcowe:
`test-results/design/`, `test-results/ui-final/`. Polecenia odtworzenia są w README.

Ograniczenie: przeglądarka testowa nie pobrała zewnętrznych kafelków OSM.
Pełnych testów mapy nie zaliczono i nie podstawiano kafelków ani danych demonstracyjnych.
Źródła danych nie były w tej sesji ponownie diagnozowane — zadanie dotyczyło UI.
Nie uruchamiano istniejącego testu modyfikującego ulubione użytkownika.
Pierwsze wywołanie CLI `ui-check` zakończyło drukowanie raportu błędem kodowania cp1250;
ponowiono kontrolę z `PYTHONIOENCODING=utf-8` i zapisano pełny raport JSON wskazany powyżej.
