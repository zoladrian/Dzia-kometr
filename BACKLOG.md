# Co jeszcze można dodać

Stan na 2026-10-22. Karta działki pokazuje wszystkie publiczne pola, które są w bazie. Wyjątki są wymienione niżej.

## Dane, które mamy, ale ich nie pokazujemy

| Dane | Gdzie są | Dlaczego nie ma ich w UI | Co można zrobić |
|---|---|---|---|
| Notariusz (`tworcaDokumentu`) | surowy GML w `raw_record` | dane osobowe | zostawić poza UI |
| Obrysy budynków z RCN | GML (`RCN_Budynek/geometria`, 5521) | nie są zapisywane w osobnej tabeli | warstwa budynków sprzedanych z działką |
| Punkty lokali z RCN | GML (`RCN_Lokal/georeferencja`, 1825) | jak wyżej | pinezki sprzedanych mieszkań |
| Starsze miesięczne pliki RCN (8 wersji) | katalog dane.gov.pl | import bierze najnowszy stan | historia korekt rekordów między wersjami |
| Dowód surowy rekordu | `raw_record`, `inspect --raw` | celowo tylko w CLI | podgląd dla właściciela bazy po zalogowaniu |

## Brakujące źródła na karcie (dziś „Niedostępne”)

1. Aktualne MPZP: Krajowa Integracja MPZP, `GetFeatureInfo` w punkcie działki, z datą uchwały i linkiem.
2. Uzbrojenie: GESUT, typy sieci w promieniu, bez twierdzeń o możliwości przyłączenia.
3. Zagrożenie powodziowe: ISOK / Wody Polskie, z prawdopodobieństwem (Q1%, Q0,2%).
4. Ochrona przyrody: GDOŚ WFS, nazwa i typ formy ochrony.
5. Rzeźba terenu: NMT, spadek i wysokość.
6. Drogi i sąsiedztwo: BDOT10k, odległość do drogi publicznej.
7. Ortofoto jako przełączany podkład mapy.
8. Pełna warstwa granic EGiB zamiast pobierania granic ULDK pojedynczo.

## Funkcje

1. Porównanie działki z podobnymi sprzedażami w promieniu (ta sama kategoria, rok, powierzchnia ±30%), bez wyceny.
2. Wykres cen za m² w czasie dla obrębu albo zaznaczonego obszaru.
3. Eksport karty i tabeli do CSV albo PDF.
4. Edycja etykiety „mojej działki” bez usuwania.
5. Link do karty (`?parcel=…`) z przyciskiem „Kopiuj link”.
6. Powiadomienie o nowej sprzedaży w pobliżu „moich działek” po miesięcznym imporcie.
7. Automatyczny miesięczny import z porównaniem wersji.
8. Kolejne powiaty: konfiguracja katalogu dane.gov.pl na powiat i słowniki per wersja schematu.
9. Tryb ciemny i większy kontrast.
10. Instalacja jako aplikacja na telefonie (PWA) i działanie bez sieci dla zapisanych działek.

## Znane ograniczenia danych

- 240 obserwacji bez geometrii w RCN; widoczne tylko przez wyszukiwanie.
- ULDK nie zwraca granicy dla części działek (np. `080104_2.0002.105/9`: błąd XML usługi powiatowej).
- Punkt adresowy wskazuje działkę pod punktem. Posesja może obejmować kilka działek.
- Świeżo sprzedane działki niezabudowane często nie mają punktu adresowego w PRG, choć RCN podaje adres
  (np. Kłodawa, Jesionowa 19). Wyszukiwanie po adresie zwraca wtedy „brak dokładnego punktu”;
  można dodać wyszukiwanie po adresie zapisanym w RCN.
- 5394 obserwacje mają cenę nieruchomości ≤ 0 (cena w innym miejscu aktu); oznaczone na karcie.

## Błędy z audytu 2026-10-22 — zamknięte w tej samej dobie

Audyt nie zmieniał kodu. Poprawki i ponowne testy: [PROGRESS.md](PROGRESS.md#poprawki-po-audycie--2026-10-22).
Poniższe AUD-01–07 są **zamknięte**. Opis odtworzenia zostaje jako historia.

### AUD-01 · P1 · Mediana i kolory mapy mieszają nieporównywalne transakcje

- **Odtworzenie:** `GET /api/map?bbox=14,49,25,55&zoom=8` oraz `zoom=13`.
  `scale` jest wspólny dla kategorii `built` i `unbuilt`; grupowanie klastrów
  również nie rozdziela kategorii, roku, rynku ani prawa. SQL na prawdziwej
  bazie wykazał 1033 obserwacje z ceną działki z aktów wielodziałkowych w puli
  używanej do skali mapy. `price_scale` filtruje podstawę ceny, ale nie pełny
  zakres aktu; klaster używa maksimum ceny/m² obserwacji danego aktu.
- **Skutek:** legenda opisuje tę pulę jako sprzedaże pojedynczej działki;
  użytkownik widzi medianę i kolor, które nie odpowiadają regułom osobnych
  statystyk. Przykład aktu wielodziałkowego w tej puli:
  `e88f358e2c648c7118c9a25013d10252f650616beda777d4d30b34402c207326`,
  działka `080105_2.0014.246/7`, kategoria `built`, 3719,14 zł/m².
- **Do poprawy:** ustalić wspólne reguły zakresu i grupowania dla legendy,
  klastrów, listy oraz `/api/statistics`; nie prezentować wspólnej mediany
  jako porównania podobnych gruntów. Zachować osobny zakres cen pakietowych.
- **Warunek zamknięcia:** test rzeczywistych danych oraz test mieszanej próbki
  potwierdza brak mieszania kategorii i pakietów. Poprawny endpoint statystyk
  (185 zgodnych grup) nie jest dowodem poprawności legendy.
- **Zamknięte:** skala i klaster używają jednej kategorii (domyślnie niezabudowane)
  oraz tylko aktów z jedną działką. Live mediana niezabudowanych: 46,57 zł/m²
  z 1970 obserwacji. Testy: `test_map_scale_keeps_unbuilt_when_categories_mix`,
  `test_map_scale_excludes_multi_parcel_acts`.

### AUD-02 · P1 · Potwierdzona nieruchomość powielana dla każdej działki

- **Odtworzenie SQL:**
  ```sql
  SELECT sale_id, source_id, count(*) AS copies
  FROM property WHERE identity_status = 'confirmed'
  GROUP BY sale_id, source_id HAVING count(*) > 1
  ORDER BY copies DESC;
  ```
- **Wynik:** 1969 takich grup; tabela ma 13 670 wierszy dla 10 575 różnych
  identyfikatorów źródłowych. `RCN_N_42957` w akcie
  `6e8a795fe5d74fa0edbc89090a5452b4658b349107d806f577ae8a8896d44686`
  jest zapisane 28 razy. `save_batch` buduje ID nieruchomości z ID obserwacji
  nawet przy potwierdzonym identyfikatorze GML.
- **Skutek:** model nie odwzorowuje jednej nieruchomości z wieloma działkami;
  liczność nieruchomości i ewentualne agregowanie ich cen/powierzchni są mylące.
- **Do poprawy:** dla GML zachować wspólną tożsamość nieruchomości i powiązać
  z nią wiele obserwacji; odrębnie traktować WFS bez potwierdzonego klucza.
- **Warunek zamknięcia:** jedna nieruchomość dla powyższego aktu, 28 powiązanych
  działek, zachowane dowody i relacje po migracji oraz idempotentny reimport.
  Obecny reimport 28 oryginalnych rekordów jest idempotentny, ale odtwarza
  ten sam wadliwy model: `property=28`.
- **Zamknięte:** import GML używa `stable_id("property", sale, source_id)`;
  `initialize()` scala stare kopie SQL-em SHA-256. Live: `property=10575`,
  0 grup `HAVING count(*)>1`, akt 28 działek ma 1 nieruchomość.

### AUD-03 · P1 · Zestaw E2E nie odpowiada obecnemu UI

- **Odtworzenie:** `python -m pytest tests/test_e2e.py --online --real-data --e2e`.
- **Wynik:** 4 FAIL. Test filtra wypełnia pole w zamkniętym panelu; test historii
  szuka nieistniejącego `#parcel-query` zamiast obecnego `#q`; test adresu
  szuka usuniętego przełącznika `input[value=address]`. Przycisk filtra obecnie
  nazywa się „Pokaż wyniki”, a test oczekuje „Zastosuj filtry”. Kontrola kart
  zgłosiła również błędy układu i brak kafelków.
- **Do poprawy:** dostosować testy do rzeczywistych działań użytkownika,
  zachować kontrole danych i geometrii; nie usuwać asercji, by uzyskać zielony wynik.
- **Warunek zamknięcia:** wszystkie cztery testy przechodzą dla ustalonej wersji
  aplikacji; co najmniej jeden rzeczywisty przepływ zawiera mapę, granicę,
  wyszukiwanie i kartę. Sieć dla OSM/źródeł musi być dostępna lub wynik
  jawnie oznaczony jako niezaliczony.
- **Zamknięte:** `pytest tests/test_e2e.py --e2e --online --real-data` → 6 PASS.

### AUD-04 · P2 · Nieprawidłowy polygon zwraca awarię usługi zamiast błędu wejścia

- **Odtworzenie:**
  `GET /api/transactions?bbox=14,49,25,55&polygon=%7B%7D`;
  to samo dla `/api/map` i `/api/statistics`, również `polygon=null` i `polygon=[]`.
- **Wynik:** 503 `UNAVAILABLE` z sugestią niedostępnej bazy; `/api/health`
  w tym czasie zwraca 200. Potwierdzono 9 takich odpowiedzi.
- **Do poprawy:** walidować typ i strukturę GeoJSON przed `shapely.shape`;
  wszystkie błędy danych wejściowych mapować na 422 bez utraty połączenia.
- **Warunek zamknięcia:** 422 dla obiektu bez `type`, null i tablicy w każdym
  z trzech endpointów; kolejne poprawne żądanie działa na tym samym kliencie.
- **Zamknięte:** walidacja GeoJSON przed shapely; live i `test_api_contract_validation`.

### AUD-05 · P2 · Ulubione działki są zwracane poza bbox

- **Odtworzenie:** `/api/map?bbox=20,50,21,51&zoom=8`, następnie `zoom=13`.
- **Wynik:** 2 `favorite_point` z okolic Kłodawy (długość ok. 15,22°),
  mimo bbox o długości 20–21°. Przy `zoom=17` ten sam obszar jest pusty.
- **Do poprawy:** zastosować bbox i jasno ustalone reguły polygon do dodatkowej
  warstwy ulubionych; jeżeli mają być globalną warstwą, oddzielić ją od
  kontraktu „dane tylko dla bieżącego widoku” i jasno opisać zachowanie.
- **Warunek zamknięcia:** wszystkie zwracane geometrie należą do żądanego
  zakresu przy każdej skali, także dla działek bez historii RCN.
- **Zamknięte:** warstwa ulubionych filtruje bbox i polygon; bbox 20–21° pusty.

### AUD-06 · P2 · Wyłączenie kategorii pozostawia nieaktualne statystyki

- **Odtworzenie UI:** otworzyć mapę z wynikami, odznaczyć wszystkie trzy
  kategorie w legendzie.
- **Wynik Playwright:** `#total = 0`, ale `#stats` zachowuje poprzednią treść,
  a `#legend-median` nadal pokazuje `85 zł`. `renderEmpty()` czyści mapę i listę,
  lecz nie statystyki ani legendę.
- **Do poprawy:** wyczyścić lub jawnie oznaczyć jako nieaktualne wszystkie
  zależne wartości, również po nieudanym odświeżeniu.
- **Warunek zamknięcia:** brak mediany/histogramu niepasujących do pustego
  zestawu; po ponownym włączeniu kategorii wyświetlane są nowe wyniki.
- **Zamknięte:** `renderEmpty()` czyści listę, `#legend-median=brak` i statystyki.

### AUD-07 · P2 · Udokumentowana komenda testowa CLI nie działa

- **Odtworzenie:** `.\.venv\Scripts\python.exe -m landscope test -m unit`.
- **Wynik:** argparse: `unrecognized arguments: -m`, kod 2.
- **Do poprawy:** poprawić przekazywanie argumentów pytest lub podać działającą
  składnię w dokumentacji i przetestować ją z CLI. Do czasu poprawki działa
  bezpośrednie `.\.venv\Scripts\python.exe -m pytest -m unit`.
- **Warunek zamknięcia:** dokładnie skopiowana komenda z README uruchamia testy
  i przenosi ich kod zakończenia.
- **Zamknięte:** `python -m landscope test -m unit` → 25 PASS.

### Weryfikacja układu po zmianach równoległych — nie zamykać na podstawie starego raportu

Pierwszy E2E zgłosił na komputerze widoczne `filter-count`, `finish-area`,
`clear-area` mimo `hidden`, miniaturowe obrysy działek (1–2 px) i brak otwarcia
karty po kliknięciu; na małym telefonie elementy daty poza ekranem.
Podczas audytu inny proces zmienił CSS i `uicheck.py`. Późniejszy zrzut pokazał
już prawidłowy duży obrys. Te obserwacje nie powinny być automatycznie traktowane
jako nadal obecne ani zamknięte bez wyniku ponowienia `ui-check` dla tej samej wersji.

### Blokady odbioru i luki kontroli

- [ ] Powtórzyć diagnostykę 12 źródeł w osobnej sesji, jeśli sieć była zablokowana.
  Wcześniejsze PASS: rcn, rcn_county, uldk, uug. Pozostałe celowo UNAVAILABLE.
- [x] Docker Compose: `docker compose up -d --build app` — kontenery healthy,
  `/api/health` 200, import 7907 transakcji.
- [x] Testy po poprawkach na jednej wersji HTML/CSS/JS/backendu: 46+11+6 PASS.
- [ ] Lokalne wyszukiwanie `Kłodawa 27/89` z `online=false` nadal puste;
  `q=27/89&commune=Kłodawa` i UI z ULDK działają.
- [ ] Powiększenie 200% i tryb ciemny. Długi akt 28 działek otwiera się bez
  poziomego scrolla; nie sprawdzano każdej wartości z osobna.
- [ ] Oddzielić wynik dostępności źródła od zaliczenia testu oczekującego
  UNAVAILABLE. Zielony test niezaimplementowanych adapterów nie oznacza
  działających integracji.

### Uzupełnienie po końcowym ponowieniu UI

Po zewnętrznych zmianach CSS/uicheck kontrola dwóch działek na czterech ekranach
zgłosiła już **tylko 8 braków kafelków OSM**. Obrysy, kliknięcia, ukrywanie
przycisków i układ panelu przeszły; wcześniejszych błędów układu nie traktować
jako nadal potwierdzonych. Dowód: `reports/audit-20261022-ui-final.txt`.
Pod koniec audytu poza działaniami agenta zmieniły się także testy E2E
(w tym selektory z AUD-03), integracje i pliki aplikacji. AUD-03 opisuje więc
potwierdzoną porażkę pierwszego przebiegu i wymaga oceny według wyniku ponowienia,
nie ponownego wprowadzania tej samej poprawki. Pozostałe ustalenia mają dowody
z konkretnego przebiegu; całość należy ostatecznie odebrać na jednej wersji.

**AUD-03, wynik ponowienia:** poprawkę selektorów wykonaną poza audytem
potwierdzono: 2 testy E2E PASS (historia/granica oraz adres), test filtra
przechodzi obsługę kontrolek i kończy się FAIL wyłącznie za brak kafelków.
Nie ma potrzeby ponownej poprawki tych selektorów. Pełny zestaw E2E po poprawkach:
6 PASS (`--e2e --online --real-data`). `reports/audit-20261022-e2e-final-subset.xml`
opisuje stan audytu, nie bieżący.
