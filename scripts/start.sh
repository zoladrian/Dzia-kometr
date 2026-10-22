#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
UI='http://127.0.0.1:8000'

fail() {
  local problem=$1
  shift
  echo
  echo 'NIE UDALO SIE URUCHOMIC dzialkometru.'
  echo "Przyczyna: $problem"
  echo
  echo 'Co zrobic, krok po kroku:'
  local n=1
  local step
  for step in "$@"; do
    echo "  $n. $step"
    n=$((n + 1))
  done
  echo
  echo 'Gdy to zrobisz, z katalogu projektu odpal ponownie:'
  echo '  ./scripts/start.sh'
  echo
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  fail 'Brak polecenia docker w PATH.' \
    'Zainstaluj Docker Desktop: https://www.docker.com/products/docker-desktop/' \
    'Na macOS przeciagnij Docker do folderu Aplikacje i uruchom go.' \
    'Poczekaj, az ikona wieloryba na pasku przestanie animowac.' \
    'Zamknij ten terminal i otworz nowy w katalogu projektu.'
fi

os=''
if ! os=$(docker info --format '{{.OSType}}' 2>/dev/null); then
  fail 'Docker jest zainstalowany, ale silnik nie odpowiada.' \
    'Otworz Docker Desktop (macOS: Aplikacje / pasek menu).' \
    'Poczekaj, az status to Engine running.' \
    'Jesli Docker prosi o uprawnienia, zatwierdz je.' \
    'Potem w nowym terminalu odpal skrypt jeszcze raz.'
fi
if [[ "$os" != 'linux' ]]; then
  fail 'Docker nie dziala w trybie kontenerow Linux.' \
    'W Docker Desktop wlaczy Linux containers.' \
    'Poczekaj na przelaczenie i odpal skrypt ponownie.'
fi

echo 'Buduje i uruchamiam kontenery (pierwszy raz moze potrwac kilka minut)...'
if ! docker compose up -d --build --wait; then
  echo
  echo 'Ostatnie logi kontenerow:'
  docker compose logs --tail 80 || true
  if command -v lsof >/dev/null 2>&1; then
    p8=$(lsof -nP -iTCP:8000 -sTCP:LISTEN -t 2>/dev/null | head -n1 || true)
    pdb=$(lsof -nP -iTCP:15432 -sTCP:LISTEN -t 2>/dev/null | head -n1 || true)
    [[ -n "${p8:-}" ]] && echo "Port 8000 jest zajety (PID $p8). Zamknij ten program albo: docker compose down"
    [[ -n "${pdb:-}" ]] && echo "Port 15432 jest zajety (PID $pdb). To port bazy dzialkometru."
  fi
  fail 'docker compose up nie doprowadzil uslug do stanu healthy.' \
    'Upewnij sie, ze Docker Desktop nadal dziala.' \
    'Z katalogu projektu: docker compose logs --tail 100' \
    'Jesli build pada na sieci: sprawdz internet i odpal skrypt ponownie.' \
    'Gdy baza nie wstaje: docker compose down -v   UWAGA: kasuje lokalne dane bazy.' \
    'Gdy apka nie wstaje: docker compose ps'
fi

healthy=0
for _ in $(seq 1 20); do
  if curl -fsS "$UI/api/health" >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done
if [[ "$healthy" -ne 1 ]]; then
  fail "Kontenery dzialaja, ale UI nie odpowiada na $UI/api/health." \
    "Otworz recznie: $UI" \
    'Jesli przegladarka nic nie pokazuje: docker compose ps' \
    'Logi aplikacji: docker compose logs app --tail 80' \
    'Pelny restart: docker compose down ; potem ten skrypt jeszcze raz.'
fi

echo "dzialkometr: $UI"
if command -v ipconfig >/dev/null 2>&1; then
  lan=$(ipconfig getifaddr en0 2>/dev/null || true)
  [[ -n "${lan:-}" ]] && echo "W sieci lokalnej: http://${lan}:8000"
fi

sales=$(docker compose exec -T app python -c "from landscope.db import counts; print(counts()['sale'])" 2>/dev/null || echo '?')
if [[ "$sales" == '0' ]]; then
  echo 'Baza jest pusta, mapa otworzy sie bez transakcji. Import RCN powiatu:'
  echo '  docker compose exec app python -m landscope import-rcn --county 0801'
elif [[ "$sales" =~ ^[0-9]+$ ]]; then
  echo "Sprzedazy w bazie: $sales"
fi

if command -v open >/dev/null 2>&1; then
  open "$UI" && echo 'Otwieram interfejs w przegladarce.'
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$UI" >/dev/null 2>&1 && echo 'Otwieram interfejs w przegladarce.'
else
  echo "Serwer dziala. Otworz recznie: $UI"
fi
