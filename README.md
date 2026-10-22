# działkometr

Lokalny projekt analizy sprzedaży działek: FastAPI, PostgreSQL/PostGIS, Leaflet.
Obszar pierwszego importu: powiat gorzowski (0801), bez miasta Gorzów Wielkopolski.
Docelowy model identyfikatorów obejmuje całą Polskę. Bez automatycznej wyceny.

**Stan: lokalne MVP powiatu gorzowskiego działa.** W bazie jest import GML z 14.10.2026:
7907 sprzedaży, 13670 obserwacji działek, daty dokumentów od 2006-11-09 do 2026-10-09.
Cena aktu nie jest ceną działki. Aktualne MPZP, uzbrojenie, powódź i ochrona przyrody
pozostają niedostępne. Szczegóły: [PROGRESS.md](PROGRESS.md), [DATA_SOURCES.md](DATA_SOURCES.md).

## Start (Windows i macOS)

To nie jest statyczna strona. Serwer to Docker: FastAPI + PostGIS. Ten sam zestaw
działa na Windowsie i na Macu, bo kontenery są Linuxowe. Nie instaluj osobno
Pythona ani PostgreSQL.

Wymagania: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(kontenery Linux), internet przy pierwszym starcie i imporcie. Porty 8000 i 15432
muszą być wolne (Windows często rezerwuje 55432, stąd 15432).

Sklonuj i wejdź do katalogu:

```bash
git clone https://github.com/zoladrian/Dzia-kometr.git
cd Dzia-kometr
```

**Windows** (PowerShell):

```powershell
.\scripts\start.ps1
```

**macOS / Linux:**

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

Skrypt buduje kontenery, czeka aż API odpowie i otwiera http://127.0.0.1:8000
w przeglądarce. Gdy coś nie wstanie, wypisuje przyczynę i konkretne kroki.

W UI, pod logo, wybierasz powiaty trzymane lokalnie. Na górze listy są
**powiat gorzowski** i **powiat miński** (Arynów koło Mińska Mazowieckiego).
Zaznaczenie bez danych w bazie można od razu pobrać z RCN (GML dla 0801, WFS
dla pozostałych). Import całego powiatu może potrwać.

Odpowiednik: `docker compose up -d --build --wait`.
Interfejs: http://localhost:8000; API: http://localhost:8000/docs.
Aplikacja na porcie 8000. Baza tylko na `127.0.0.1:15432`.
Hasło w Compose służy wyłącznie temu lokalnemu środowisku.

Klon katalogu nie zawiera bazy: wolumen Dockera jest lokalny, więc po starcie
trzeba zaimportować RCN. Pierwszy import jest jawną operacją; aplikacja nie
wstawia danych demonstracyjnych. To samo polecenie na Windowsie i Macu:

```text
docker compose exec app python -m landscope import-rcn --county 0801
docker compose exec app python -m landscope counts
```

Opcjonalnie diagnostyka źródeł i próbka Kłodawy:

```text
docker compose exec app python -m landscope diagnose --source rcn --source uldk
docker compose exec app python -m landscope sample --place Kłodawa --seed 8012026
```

Diagnostyka kończy się kodem 1 dla FAIL lub UNAVAILABLE. Po imporcie sprawdź raport jakości.
Brak transakcji nie oznacza braku sprzedaży w historii działki.

Jeżeli Windows zgłasza blokadę skryptów:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

Najpierw otwórz Docker Desktop i poczekaj na silnik. Skrypt sprawdzi tryb Linux.

## Zdalny dostęp

Tymczasowy tunel HTTPS do lokalnego UI: `.\scripts\share-link.ps1`
(Cloudflare Quick Tunnel). Nie wystawiaj portu 8000 ani 15432 na routerze.

## CLI

Poniższe polecenia poprzedź `docker compose exec app` albo wykonaj w lokalnym venv:

```text
python -m landscope init
python -m landscope status
python -m landscope diagnose
python -m landscope diagnose --source rcn --source uldk --parcel PEŁNY_IDENTYFIKATOR
python -m landscope import-rcn --county 0801
python -m landscope import-rcn --county 0801 --resume ID_POBIERANIA
python -m landscope import-file ścieżka/do/odpowiedzi-wfs.gml --county 0801
python -m landscope counts
python -m landscope quality
python -m landscope parcel "Kłodawa 1"
python -m landscope transactions --bbox 15.15,52.74,15.30,52.84
python -m landscope inspect ID_TRANSAKCJI
python -m landscope inspect ID_OBSERWACJI --raw
python -m landscope sample --place Kłodawa --count 5 --seed 8012026
python -m landscope address "Kłodawa, Gorzowska 40"            # punkt adresowy GUGiK -> działka ULDK
python -m landscope card 080104_2.0002.27/89                   # pełna karta (te same wiersze co w UI); --json
python -m landscope card ID_TRANSAKCJI --transaction
python -m landscope favorite 080104_2.0002.27/89 --label "Do porównania"   # --remove usuwa
python -m landscope ui-check --parcel 080104_2.0002.27/89 --parcel 080104_2.0002.1235/4
python -m landscope test -m unit
```

`ui-check` otwiera aplikację w Playwright na czterech ekranach: komputer, telefon, mały telefon i tablet.
Dla każdej działki porównuje z API każdy wiersz karty (etykietę, wartość, status, kolejność).
Sprawdza też podpis i kliknięcie działki na mapie, ucięte i przykryte elementy oraz układ.
Zrzuty trafiają do `test-results/ui/`. Lista kontroli: [TEST_CHECKLIST.md](TEST_CHECKLIST.md).
Dalsze pomysły: [BACKLOG.md](BACKLOG.md).

Interfejs **działkometr** ma zielony nagłówek, listę rzeczywistych transakcji po lewej i mapę po prawej.
Skróty „Moje działki” i „Statystyki” prowadzą do odpowiednich sekcji bez przewijania całej listy.
Nad mapą jest wyszukiwanie miejscowości, adresu lub działki oraz filtry ceny i powierzchni.
Panel filtrów ma zawsze widoczny przycisk zatwierdzania, kontrolę zakresów i obsługę klawiatury (Tab, Shift+Tab, Escape).
W średnim przybliżeniu na mapie widać etykiety cen (zł/ar albo kwota aktu).
Kliknięcie otwiera kartę działki w miejscu listy: kafelki, transakcje, medianę ceny za m² w obrębie według lat i wszystkie dane.
Na telefonie mapa zajmuje cały ekran. Lista i karta wysuwają się od dołu, a filtry otwierają się w panelu.
„Zobacz na mapie” zwija kartę do dolnego paska; strzałka ponownie ją rozwija.
Warstwa wyglądu interfejsu jest w `landscope/static/interface.css`; styl mapy pozostaje w `style.css`.
Interfejs nie potrzebuje zewnętrznego serwera fontów. Nazwy pakietu Python i polecenia CLI pozostają `landscope`.
Działki są barwione według ceny za m² (skala dla powiatu przy bieżących filtrach). Szare nie mają uzasadnionej ceny za m².
Przy oddaleniu widać grupy, w średnim przybliżeniu punkty, a od przybliżenia 15 obrysy, od 16 z numerami.
„Moje działki” mają zawsze etykietę ze ★.
Pole „Gdzie?” rozpoznaje identyfikator działki, adres (punkt GUGiK), obręb z numerem i nazwę miejscowości.

`import-file` obsługuje obecnie **płaską odpowiedź WFS GUGiK**, a nie dowolny powiatowy GML.
Nie jest traktowany jako pełny obraz powiatu. Nie należy podawać prywatnych plików aktów.
`inspect --raw` jest dostępne wyłącznie w CLI; HTTP nie udostępnia surowych rekordów.

Przerwane pobieranie zapisuje identyfikator i strony w `data/imports/<ID>/manifest.json`.
Wznowienie wymaga tego samego powiatu i rozmiaru strony. Powtarzające się obiekty,
zmiana liczby wyników i konflikt wersji przerywają import. WFS nie daje izolowanego
snapshotu; identyczna liczba wyników nie wyklucza zmian danych w trakcie pobierania.
Po podejrzeniu zmiany źródła rozpocznij nowy import.

## Reguły danych i obliczeń

- Oddzielne tabele: transakcja, nieruchomość, działka, obserwacja, surowa wersja, import, odrzucenia.
- Płaski WFS nie dostarcza potwierdzonego klucza nieruchomości: przechowujemy obserwacje
  nieruchomości z `identity_status=unavailable`. Nie łączymy ich po identycznych cenach.
- Cena transakcji nie jest ceną działki. Cena/m² wymaga pełnego udziału, dodatniej powierzchni
  i rozpoznanej kategorii. Podstawą jest cena tej działki z RCN (`cenaDzialkiEwidencyjnejBrutto`)
  albo cena aktu, gdy akt obejmuje wyłącznie tę jedną działkę gruntu w całości.
  Podstawa jest podana na karcie. Akty z wieloma działkami dostają cenę pakietu i nie wchodzą do median.
- Obliczenia wykorzystują Decimal; wartości pieniężne API są tekstem dziesiętnym.
- Statystyki rozdzielają kategorię, pojedynczą działkę/pakiet, rynek, prawo i rok.
  Pakiety oraz niepewne mianowniki nie trafiają do mediany. Nie korygujemy inflacji.
- Filtr ceny dotyczy ceny transakcji; filtr powierzchni dotyczy obserwowanej działki.
  Jeśli cena transakcji nie występuje w źródle, filtr ceny ją wyklucza.
- Mapa pobiera wyłącznie bbox/polygon bieżącego widoku. Przy oddaleniu agreguje transakcje;
  przy zbliżeniu limit to 2000 obiektów z jawną informacją o obcięciu.
- Granice to aktualne pobrane geometrie ULDK. Geometrie RCN pozostają oznaczone jako
  przybliżone lokalizacje, nawet gdy źródło zwróci wielokąt.
- Baza przechowuje dane bez geometrii i flagi jakości. Takie rekordy można znaleźć przez
  działkę/CLI, ale nie da się wiarygodnie umieścić ich na mapie.
- Dane stron umowy i notariusza nie przechodzą do publicznego DTO. Surowe odpowiedzi
  pozostają lokalnymi dowodami w bazie i `data/raw`; nie są serwowane przez aplikację.

## Testy

Instalacja lokalnego środowiska (Python 3.12+; na tym komputerze 3.13):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe scripts/fetch_assets.py
.venv\Scripts\python.exe -m playwright install chromium
```

Zależności geometrii są obowiązkowe również w testach offline.
Brak zależności powoduje błąd testów, nie ukryte zaliczenie.

```powershell
# Jednostkowe, kontraktowe, jakość i regresje offline
.venv\Scripts\python.exe -m pytest -m "not integration and not online and not e2e" --junitxml=reports/offline-full.xml

# Rzeczywista baza; testy tworzą i usuwają tylko własny izolowany schemat landscope_test_*
docker compose exec app python -m pytest --integration --junitxml=reports/backend.xml

# Każde źródło osobno; brak danych lub sieci NIE zalicza testu
.venv\Scripts\python.exe -m landscope diagnose
.venv\Scripts\python.exe -m pytest tests/test_online.py --online --junitxml=reports/online.xml

# Przeglądarka; aplikacja musi już działać, kafelki wymagają internetu
.venv\Scripts\python.exe -m pytest tests/test_e2e.py --e2e --junitxml=reports/e2e.xml

# Prawdziwa Kłodawa: porównanie ze źródłem oraz mapa/wyszukiwanie/historia
.venv\Scripts\python.exe -m pytest tests/test_reconciliation.py tests/test_e2e.py --online --real-data --e2e --junitxml=reports/real-data.xml
```

Domyślny pytest pomija testy wymagające jawnych flag. Pominięcie jest opisane jako
NIE URUCHOMIONO. Offline symulacje HTTP/bazy znajdują się w testach kontraktowych
i przepływu importu; nie zastępują testów rzeczywistych usług ani PostGIS.

CI uruchamia backend i rzeczywisty PostGIS. Ręczne `workflow_dispatch` z `online=true`
uruchamia diagnostykę i testy źródeł. Rozszerzone źródła pozostają czerwone/UNAVAILABLE,
dopóki ich adaptery i kontrakty nie zostaną zweryfikowane; nie jest to gotowy zestaw integracji.

## Konfiguracja i ograniczenia

Zmienne: `DATABASE_URL`, `LANDSCOPE_DATA_DIR`, `LANDSCOPE_COUNTY`,
`LANDSCOPE_HTTP_TIMEOUT`. Compose odczytuje `.env`; lokalny Python odczytuje zmienne
procesu. Przykład w `.env.example`. CLI domyślnie importuje 0801, inny kod podaj przez
`--county`. `LANDSCOPE_TEST_URL` zmienia adres testowanego serwera;
`LANDSCOPE_CHROMIUM_PATH` pozwala jawnie użyć istniejącej przeglądarki Chromium.

Kontrola nowego UI na rzeczywistych danych lokalnej aplikacji (bez mocków):

```powershell
$env:PYTHONIOENCODING = 'utf-8'
# Jeśli przeglądarka pobrana dla bieżącej wersji Playwright nie jest dostępna:
$env:LANDSCOPE_CHROMIUM_PATH = 'C:\Users\Gigabyte\AppData\Local\ms-playwright\chromium-1234\chrome-win64\chrome.exe'
.venv\Scripts\python.exe -m pytest tests/test_ui_design.py --e2e --real-data --junitxml=reports/ui-design-final.xml
.venv\Scripts\python.exe -m landscope ui-check --parcel 080104_2.0002.27/89 --parcel 080104_2.0002.1235/4
```

Testy UI obejmują dziewięć rozmiarów okna, przycięcia i zasłonięcia, filtry, fokus klawiatury,
zwijanie i rozwijanie karty oraz przewijanie przy niskim oknie. Zrzuty: `test-results/design/`.
`ui-check` dodatkowo porównuje wiersze kart z API i sprawdza mapę; brak kafelków jest raportowany jako błąd.
Wskazany przez użytkownika [skill frontend-design](https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md)
zapisano lokalnie w `skills/frontend-design/SKILL.md` i zastosowano do tej wersji interfejsu.

Aktualne MPZP, GESUT, GDOŚ, powódź, BDOT10k i NMT nie są jeszcze wzbogaceniami kart
działek. Są zarejestrowane do diagnostyki, a UI pokazuje brak potwierdzonej informacji.
Nie ma pełnego pokrycia granic EGiB: rysowane są pobrane i zapisane granice ULDK.
Nie ma automatycznej wyceny, modeli czasowych cen ani historii podziałów działek.

Audyt CLI 2026-10-22 zgłosił AUD-01–07 (skala mapy, model nieruchomości, E2E,
polygon 503, ulubione poza widokiem, stale statystyki, CLI `test -m`).
Poprawki i ponowne testy: [PROGRESS.md](PROGRESS.md#poprawki-po-audycie--2026-10-22),
[TEST_CHECKLIST.md](TEST_CHECKLIST.md). `python -m landscope test -m unit` działa.
