# LandScope — instrukcja dla Codex CLI

## Cel
Zbuduj działające lokalnie MVP mapy **rzeczywistych cen transakcyjnych działek**. Początkowy obszar: **powiat gorzowski**. Priorytet: poprawny import, łączenie, weryfikacja i prezentacja danych. Na tym etapie **bez automatycznej wyceny** i bez rozbudowanego frontendu.

## Technologia i uruchamianie
- Python, FastAPI, PostgreSQL + PostGIS, Docker Compose; minimalny interfejs webowy z mapą (np. MapLibre/Leaflet).
- Pytest dla backendu i integracji; Playwright dla mapy i UI.
- Jedna udokumentowana komenda startowa i polecenia CLI do importu, testów, diagnostyki i sprawdzenia rekordów.
- Zadbaj o powtarzalne importy, logowanie błędów i konfigurację przez zmienne środowiskowe.

## Źródła — zweryfikuj rzeczywiste formaty, zakres danych i warunki użycia
| Źródło | Zastosowanie | Adres |
|---|---|---|
| RCN GUGiK | ceny, daty, nieruchomości, transakcje; WFS/pliki | https://www.geoportal.gov.pl/pl/dane/rejestr-cen-nieruchomosci-rcn/ ; https://mapy.geoportal.gov.pl/wss/service/rcn |
| RCN powiatu gorzowskiego | lokalny zbiór transakcji, potencjalnie GML | https://dane.gov.pl/pl/dataset/29243,rejestr-cen-nieruchomosci-rcn-powiatu-gorzowskiego |
| ULDK GUGiK | wyszukiwanie działek, identyfikatory, geometrie | https://uldk.gugik.gov.pl/ ; https://uldk.gugik.gov.pl/opis.html |
| EGiB / usługi powiatowe | geometrie, powierzchnie, użytki gruntowe | Geoportal/powiatowe usługi WFS/WMS — ustal aktualne adresy |
| Krajowa Integracja MPZP + gminy | przeznaczenie w planie | https://mapy.geoportal.gov.pl/wss/ext/KrajowaIntegracjaMiejscowychPlanowZagospodarowaniaPrzestrzennego |
| GESUT / Krajowa Integracja Uzbrojenia Terenu | sieci w pobliżu, bez twierdzeń o możliwości przyłączenia | https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaUzbrojeniaTerenu |
| BDOT10k, ortofoto, NMT | drogi, sąsiedztwo, rzeźba terenu | Geoportal GUGiK — ustal odpowiednie usługi |
| GDOŚ | formy ochrony przyrody | https://sdi.gdos.gov.pl/wfs |
| ISOK / Wody Polskie | zagrożenie powodziowe | https://isok.gov.pl/inspire.html |

Najpierw **RCN + ULDK**, potem MPZP. Pozostałe źródła dołączaj, gdy są dostępne i da się je rzetelnie zweryfikować. Nie zakładaj, że samo istnienie usługi oznacza dostępność kompletnych danych. Preferuj oficjalne API i pliki zamiast scrapingu.

## Wymagane funkcje MVP
1. Import rzeczywistych transakcji powiatu gorzowskiego, zachowanie surowego rekordu, źródła, daty aktualizacji i identyfikatorów; ponowny import bez duplikatów.
2. Rozdziel transakcję, nieruchomość i działkę. Obsłuż sprzedaż wielu działek za jedną cenę; **nie przypisuj ceny całej transakcji pojedynczej działce**. Cena/m² tylko z poprawnym mianownikiem i przy jasno opisanym zakresie.
3. Wyszukiwanie po pełnym identyfikatorze działki albo numerze + obrębie/gminie; połączenie z geometrią ULDK, jeżeli możliwe.
4. Mapa powiatu gorzowskiego: granice działek w dostępnej skali, rzeczywiste transakcje, ceny/ceny za m², szczegóły po kliknięciu; wyraźnie odróżniaj geometrię działki od przybliżonej lokalizacji transakcji.
5. Filtry: data sprzedaży, cena, powierzchnia, typ gruntu, miejscowość/obszar. Pobieraj dane tylko dla aktualnego widoku mapy i stosuj klastrowanie/agregację przy oddaleniu.
6. Karta działki/transakcji: identyfikator, obręb/gmina, powierzchnia, data, cena, cena/m² (jeśli uzasadniona), typ, powiązane działki, potwierdzone informacje planistyczne/środowiskowe/uzbrojenie, źródła, stan aktualności.
7. Tabela transakcji z sortowaniem oraz statystyki zaznaczonego obszaru: liczba, mediana cen/m², minimum, maksimum, rozkład. Nie mieszaj gruntów zabudowanych, niezabudowanych i cen pakietowych w jednych statystykach.
8. API i polecenia CLI: health/status źródeł, import/odświeżenie, liczby rekordów, wyszukiwanie działki, pobieranie transakcji dla obszaru, inspekcja rekordu i uruchamianie testów.
9. Przy polach rozróżniaj: potwierdzone źródłem, wywnioskowane/niepewne, niedostępne. Nie wymyślaj danych ani nie pokazuj danych osobowych stron umów.

## Testowanie — obowiązkowe, wykonywane przez agenta z CLI
- **Dla każdego źródła** napisz osobny test integracyjny/sprawdzenie diagnostyczne: osiągalność, poprawność odpowiedzi/formatu, wymagane pola, geometria/układ współrzędnych, próbka prawdziwych rekordów. Raportuj `PASS`, `FAIL` albo `UNAVAILABLE` z przyczyną i datą; awaria sieci ≠ działające źródło.
- Testy integracyjne online oddziel od testów jednostkowych/offline; nie ukrywaj awarii przez mocki. Sprawdzenia sieciowe mają być uruchamiane jawnie z CLI, również w CI jeśli środowisko ma internet.
- Import: idempotencja, duplikaty, brakujące pola, nietypowe ceny, wiele działek w jednej transakcji, błędna geometria, ponowienie po przerwaniu i porównanie wybranych zapisanych rekordów z oryginałem RCN.
- API: filtry, wyszukiwanie, paginacja, zakres mapy, brak wyników, obsługa błędów, dokładność ceny/m².
- Playwright: otwarcie mapy, kafelki/granice/transakcje, wyszukiwanie działki, filtry, karta szczegółów; co najmniej jeden test end-to-end na prawdziwych danych, osobno oznaczony jako zależny od dostępności źródeł.
- Nie zaliczaj testu, którego faktycznie nie uruchomiono. Jeśli brakuje internetu/uprawnień, zapisz blokadę i nie udawaj, że integracja działa.

## Dokumentacja i kryteria odbioru
Utrzymuj `README.md` (jedna komenda startowa, CLI), `DATA_SOURCES.md` (zweryfikowane endpointy, pola, licencje/ograniczenia, stan testów), `PROGRESS.md` (stan, blokady, wyniki testów). Nie generuj zbędnej dokumentacji.

MVP jest gotowe, gdy serwer i baza startują, rzeczywiste rekordy RCN są zaimportowane i możliwe do sprawdzenia względem źródła, działkę można wyszukać, mapa i filtry działają, szczegóły oraz statystyki są poprawne, a testy backendu i Playwright przeszły. Nie zastępuj brakujących funkcji danymi demonstracyjnymi bez wyraźnego oznaczenia.

## Tryb pracy Codexa
Samodzielnie podejmuj rutynowe decyzje. Najpierw sprawdź realną dostępność i schemat RCN/ULDK, następnie implementuj małymi etapami, uruchamiaj aplikację i testy po każdym etapie, poprawiaj błędy. W końcowym raporcie podaj: co działa, liczby realnych rekordów, wyniki testów każdego źródła, ograniczenia i dokładne komendy do odtworzenia. Jeśli połączenie z usługą wymaga dostępu do sieci, poproś o potrzebne uprawnienia zamiast podstawiać fikcyjne dane.
