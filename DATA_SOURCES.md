# Źródła danych — stan 2026-10-22

Diagnostyka z tej sesji: `reports/sources.json`, `reports/online/*.json`.
Rdzeń importu to GML powiatu. Płaski WFS jest sprawdzony, ale nie jest źródłem zapisu.
Pozostałe usługi mają świadomie status UNAVAILABLE: capabilities nie są danymi o działce.

## RCN GUGiK

- Dokumentacja: https://www.geoportal.gov.pl/pl/dane/rejestr-cen-nieruchomosci-rcn/
- Kandydat endpointu: https://mapy.geoportal.gov.pl/wss/service/rcn
- Oficjalny klient: https://github.com/GlownyUrzadGeodezjiIKartografii/pobierz_dane_GUGiK
- WFS 2.0, warstwa `ms:dzialki`, DescribeFeatureType i GetFeature, paginacja
  startIndex/count. Filtr `dzi_id_dzialki` z prefiksem powiatu.
- Wymagany kontrakt: `tran_przestrzen_nazw`, `tran_lokalny_id_iip`, `dok_data`,
  `dzi_id_dzialki`, `dzi_pow_ewid` oraz co najmniej jedno jawne pole ceny.
- Ceny: `tran_cena_brutto`, `nier_cena_brutto`, `dzi_cena_brutto` — odrębne zakresy.
  Brakująca cena pozostaje pusta; bez zastępowania ceną wyższego poziomu.
- Pozostałe pola kandydujące: `nier_udzial`, `nier_prawo`, `nier_rodzaj`,
  `dzi_sposob_uzyt`, `dzi_adres`, `dzi_przezn_wmpzp`, `tran_wersja_id`.
  Nazwy pól WFS są w XSD z prefiksem; porównanie bierze samą nazwę. Słowniki liczbowe
  dotyczą GML 1.5 i są w `landscope/rcn_codes.json`. Nieznany kod odrzuca rekord.
- Próbka WFS ma geometrię w EPSG:2180. Baza i GeoJSON używają długości i szerokości geograficznej.
- Dokumentacja GUGiK wskazuje bezpłatne udostępnianie danych RCN oraz pliki
  GeoPackage/GeoParquet. Nie zweryfikowano metadanych licencyjnych konkretnej paczki.
  Nie zakładamy CC0 ani uprawnień do publicznej redystrybucji.
- Test: schema + rzeczywista próbka powiatu + obowiązkowe wartości/geometria,
  następnie osobny test porównania zapisanych rekordów Kłodawy ze źródłem.
- Stan: **PASS** (2026-10-22). Schemat zawiera wymagane pola. Próbka powiatu ma datę, cenę i geometrię.
  Odpowiedź nie deklaruje jednostki powierzchni, więc pole powierzchni zostaje niedostępne i nie powstaje z niego cena/m².
  Import do bazy idzie z GML powiatowego, nie z tej warstwy.

## RCN powiatowy

- Publikacja urzędu: https://powiatgorzowski.pl/opublikowanie-danych-rcn/
- Zbiór: https://dane.gov.pl/pl/dataset/29243,rejestr-cen-nieruchomosci-rcn-powiatu-gorzowskiego
- Kandydat katalogu API: https://api.dane.gov.pl/1.4/datasets/29243/resources
- Urząd opisuje pliki GML aktualizowane w odstępach nie dłuższych niż miesiąc.
- Kontrakt potrzebny aplikacji: trwałe identyfikatory transakcji/nieruchomości/działek,
  relacje, data, ceny i powierzchnie z zakresem, układ współrzędnych.
- Bieżący plik: `https://api.dane.gov.pl/media/resources/20261016/0801.zip`, `data_date` 2026-10-14.
  Katalog `page[size]` zwraca HTTP 422; lista bez tego parametru ma 8 zasobów i mieści się na jednej stronie.
- Schemat w pliku: `https://geoportal.gov.pl/schemas/rcn/1.5`. Powierzchnie mają `uom` `ha` albo `m2` i są przeliczane na m².
  Geometria działek jest w EPSG:2176 (północ, wschód) i trafia do bazy jako EPSG:4326.
- Import 2026-10-22: 7908 obiektów transakcji w pliku, 7907 sprzedaży z działką, 13670 obserwacji,
  8626 działek, 0 odrzuceń, 240 obserwacji bez geometrii. Daty dokumentów: 2006-11-09 – 2026-10-09.
- Stan: **PASS**. To jest źródło zapisu w bazie.

## ULDK

- Endpoint: https://uldk.gugik.gov.pl/
- Specyfikacja: https://uldk.gugik.gov.pl/opis.html
- Operacje: GetParcelById, GetParcelByIdOrNr, GetParcelByXY.
- Żądane pola: id,commune,region,parcel,geom_wkt,datasource; srid=4326.
- Kontrakt: kod odpowiedzi, zgodne pełne ID, gmina/obręb, prawidłowy
  Polygon/MultiPolygon, położenie w Polsce, jawny układ. Nazwa obrębu może dawać
  wiele dopasowań — użytkownik wybiera wynik, bez zgadywania.
- Zapytanie „Kłodawa 1” jest niejednoznaczne i zwraca też Kłodawę poza powiatem 0801.
  Sprawdzenie używa identyfikatora z próbki: `080104_2.0002.1235/4`.
- WKT jest interpretowany w kolejności X,Y. Geometria opisuje stan pobrania,
  nie granice w dniu historycznej sprzedaży.
- Stan: **PASS** dla `080104_2.0002.1235/4` (gmina Kłodawa, obręb Kłodawa, Polygon, EPSG:4326, źródło „powiat gorzowski (wfs)”).
  Z pięciu wylosowanych działek Kłodawy (ziarno 8012026) granice zapisano dla czterech.
  `080104_2.0002.105/9` dostało z ULDK `-1` i komunikat o błędnym XML usługi powiatowej. To nie jest granica działki.

## Źródła dodatkowe

Poniższe pozycje mają osobne uruchamiane sprawdzenie i wymagania. Są kandydatami,
**nie gotowymi adapterami danych o działce**. W przypadku poprawnego capabilities
wynik nadal jest UNAVAILABLE, dopóki nie ma zweryfikowanego kontraktu wymaganych danych.
Nie wolno traktować samego obrazu WMS ani pustego wyniku jako dowodu braku ograniczeń.

| Źródło | Endpoint/strona kandydująca | Potrzebne dane | Wynik 2026-10-22 |
|---|---|---|---|
| EGiB | https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza | ID i granica działki, CRS | UNAVAILABLE — capabilities bez kontraktu działki |
| MPZP | https://mapy.geoportal.gov.pl/wss/ext/KrajowaIntegracjaMiejscowychPlanowZagospodarowaniaPrzestrzennego | przeznaczenie, geometria, dokument i aktualność | UNAVAILABLE — capabilities bez kontraktu działki |
| GESUT | https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaUzbrojeniaTerenu | typ i geometria sieci | UNAVAILABLE — capabilities bez kontraktu działki |
| GDOŚ | https://sdi.gdos.gov.pl/wfs | geometria, nazwa i typ ochrony | UNAVAILABLE — capabilities bez kontraktu działki |
| ISOK | https://isok.gov.pl/inspire.html | scenariusz/prawdopodobieństwo i geometria | UNAVAILABLE — strona informacyjna |
| BDOT10k | https://www.geoportal.gov.pl/pl/dane/baza-danych-obiektow-topograficznych-bdot10k/ | wektor i typ obiektu | UNAVAILABLE — strona informacyjna |
| Ortofoto | https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution | obraz, data wykonania, pokrycie | UNAVAILABLE — capabilities bez kontraktu działki |
| NMT | https://www.geoportal.gov.pl/pl/dane/numeryczny-model-terenu-nmt/ | wysokości, układ pionowy, rozdzielczość | UNAVAILABLE — strona informacyjna |

Bieżące adresy końcowe, warstwy, warunki licencyjne i użyteczne próbki dodatkowych źródeł
pozostają do weryfikacji po uzyskaniu dostępu do sieci. GESUT nie dowodzi możliwości przyłączenia.

## Podkład mapy i biblioteka

Podkład: https://tile.openstreetmap.org/{z}/{x}/{y}.png, z widoczną atrybucją OSM.
To tło mapy, nie źródło cen ani dowód granic. Nie pobieramy kafelków masowo.
Biblioteka Leaflet 1.9.4 jest pobierana podczas budowy obrazu. Mapa w przeglądarce pokazała kafelki, grupy transakcji i granicę ULDK.

## Ponowne sprawdzenie przez CLI — audyt 2026-10-22

Poniższa tabela opisuje **nowe próby w ograniczonej sesji testowej**. Wcześniejsze
PASS w tym pliku są wynikami wcześniejszych uruchomień i nie potwierdzają
bieżącego dostępu z tej sesji. Wykonano wszystkie 12 przypadków
`tests/test_online.py --online`; każdy zakończył się błędem dostępu do gniazda
`WinError 10013`, przed pobraniem i walidacją odpowiedzi. Nie jest to stwierdzenie,
że usługi urzędowe nie działają. Ponowienie wymaga dozwolonego dostępu do sieci.

| Źródło | Nowa próba UTC 2026-10-22 | Wynik źródła | Przyczyna |
|---|---|---|---|
| RCN GUGiK | 06:53:59 | UNAVAILABLE | WinError 10013; brak nowej próbki WFS |
| RCN powiatu | 06:54:06 | UNAVAILABLE | WinError 10013; brak nowego katalogu/ZIP |
| ULDK | 06:54:10 | UNAVAILABLE | WinError 10013; brak nowej odpowiedzi granicy |
| UUG / PRG | 06:54:15 | UNAVAILABLE | WinError 10013; brak nowego punktu adresowego |
| EGiB | patrz raport JSON | UNAVAILABLE | WinError 10013; nie zweryfikowano capabilities ani danych |
| MPZP | patrz raport JSON | UNAVAILABLE | WinError 10013; nie zweryfikowano capabilities ani planu |
| GESUT | patrz raport JSON | UNAVAILABLE | WinError 10013; nie zweryfikowano capabilities ani sieci |
| GDOŚ | patrz raport JSON | UNAVAILABLE | WinError 10013; nie zweryfikowano capabilities ani obiektów |
| ISOK | patrz raport JSON | UNAVAILABLE | WinError 10013; nie pobrano strony |
| BDOT10k | patrz raport JSON | UNAVAILABLE | WinError 10013; nie pobrano strony |
| Ortofoto | patrz raport JSON | UNAVAILABLE | WinError 10013; nie zweryfikowano capabilities ani obrazu |
| NMT | patrz raport JSON | UNAVAILABLE | WinError 10013; nie pobrano strony |

Dokładne `checked_at`, endpointy i przyczyny: `reports/online/<source>.json`;
wynik pytest: `reports/audit-20261022-online.xml` (**12 FAIL + 1 PASS reconciliation**).
Nie wykonywano zastępczej walidacji z mocków. `/api/sources` korzysta z osobnego
`reports/sources.json`, więc może nadal pokazywać wcześniejsze czasy i PASS;
uruchomienie samego pytest nie aktualizuje tego pliku.

Lokalny oryginał ZIP ze stanem 2026-10-14 pozostaje dostępny: porównanie 5
zapisanych rekordów Kłodawy z GML przeszło. Ponowny zapis 28 prawdziwych rekordów
jednego aktu w izolowanym schemacie także był idempotentny. Te wyniki dotyczą
archiwum, nie nowego pobrania z dane.gov.pl. Sprawdzenie bazowych geometrii:
0 nieprawidłowych, SRID 4326, 240 obserwacji bez lokalizacji.

Podkład OSM w przeglądarce testowej: **UNAVAILABLE / niezaliczony**, 0 elementów
`.leaflet-tile-loaded`; widoczne były wektorowe geometrie oraz rzeczywiste dane
aplikacji. Poprawne granice i karta z lokalnej bazy nie dowodzą dostępności kafelków.
