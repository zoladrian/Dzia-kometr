$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$ui = 'http://127.0.0.1:8000'

function Show-Fix {
    param([string]$Problem, [string[]]$Steps)
    Write-Host ''
    Write-Host 'NIE UDALO SIE URUCHOMIC dzialkometru.'
    Write-Host "Przyczyna: $Problem"
    Write-Host ''
    Write-Host 'Co zrobic, krok po kroku:'
    $n = 1
    foreach ($step in $Steps) {
        Write-Host ("  {0}. {1}" -f $n, $step)
        $n++
    }
    Write-Host ''
    Write-Host 'Gdy to zrobisz, z katalogu projektu odpal ponownie:'
    Write-Host '  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1'
    Write-Host ''
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Show-Fix 'Brak polecenia docker w PATH.' @(
        'Zainstaluj Docker Desktop: https://www.docker.com/products/docker-desktop/',
        'W instalatorze zaznacz Linux containers (domyslnie).',
        'Zrestartuj komputer, jesli instalator o to poprosi.',
        'Otworz Docker Desktop z menu Start i poczekaj, az ikona wieloryba przestanie mrugac.',
        'Zamknij ten terminal i otworz nowy PowerShell w katalogu projektu.'
    )
}

$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$dockerInfo = & docker info --format '{{.OSType}}' 2>&1
$dockerExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousPreference
if ($dockerExitCode -ne 0) {
    Write-Host ($dockerInfo | Out-String)
    Show-Fix 'Docker jest zainstalowany, ale silnik nie odpowiada.' @(
        'Otworz Docker Desktop z menu Start.',
        'Poczekaj, az w prawym dolnym rogu pojawi sie "Engine running" / ikona wieloryba bedzie spokojna.',
        'Jesli Docker prosi o wlaczenie WSL 2 albo Hyper-V, zatwierdz i zrestartuj Windows.',
        'Jesli nadal nie wstaje: Docker Desktop -> Troubleshoot -> Restart.',
        'Potem w nowym PowerShellu odpal skrypt startu jeszcze raz.'
    )
}
if (-not ($dockerInfo -contains 'linux')) {
    Show-Fix 'Docker dziala w trybie kontenerow Windows, a projekt wymaga Linux.' @(
        'W zasobniku systemowym kliknij ikone Docker prawym przyciskiem.',
        'Wybierz Switch to Linux containers.',
        'Poczekaj na przelaczenie i odpal skrypt ponownie.'
    )
}

Write-Host 'Buduje i uruchamiam kontenery (pierwszy raz moze potrwac kilka minut)...'
$ErrorActionPreference = 'Continue'
& docker compose up -d --build --wait
$composeExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if ($composeExit -ne 0) {
    Write-Host ''
    Write-Host 'Ostatnie logi kontenerow:'
    $ErrorActionPreference = 'Continue'
    & docker compose logs --tail 80
    $ErrorActionPreference = 'Stop'
    $busy8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    $busyDb = Get-NetTCPConnection -LocalPort 15432 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    $steps = @(
        'Upewnij sie, ze Docker Desktop nadal dziala.',
        'Z katalogu projektu: docker compose logs --tail 100',
        'Jesli build pada na sieci: sprawdz internet i odpal skrypt ponownie (obrazy PostGIS i Python sa pobierane raz).',
        'Gdy baza nie wstaje: docker compose down -v   UWAGA: kasuje lokalne dane bazy, potem nowy import.',
        'Gdy apka nie wstaje: docker compose ps   i sprawdz kolumne STATUS.'
    )
    if ($busy8000) {
        $steps = @("Port 8000 jest zajety (PID $($busy8000.OwningProcess)). Zamknij ten program albo: docker compose down") + $steps
    }
    if ($busyDb) {
        $steps = @("Port 15432 jest zajety (PID $($busyDb.OwningProcess)). To port bazy dzialkometru.") + $steps
    }
    Show-Fix 'docker compose up nie doprowadzil uslug do stanu healthy.' $steps
}

$healthy = $false
foreach ($i in 1..20) {
    try {
        $health = Invoke-WebRequest -Uri "$ui/api/health" -UseBasicParsing -TimeoutSec 3
        if ($health.StatusCode -eq 200) { $healthy = $true; break }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $healthy) {
    Show-Fix "Kontenery dzialaja, ale UI nie odpowiada na $ui/api/health." @(
        'Otworz recznie: ' + $ui,
        'Jesli przegladarka nic nie pokazuje: docker compose ps',
        'Logi aplikacji: docker compose logs app --tail 80',
        'Logi bazy: docker compose logs db --tail 40',
        'Pelny restart: docker compose down ; potem ten skrypt jeszcze raz.'
    )
}

Write-Host "dzialkometr: $ui"
$lan = Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' } |
    Select-Object -First 1 -ExpandProperty IPAddress
if ($lan) { Write-Host "W sieci lokalnej: http://${lan}:8000" }

$ErrorActionPreference = 'Continue'
$sales = & docker compose exec -T app python -c "from landscope.db import counts; print(counts()['sale'])" 2>$null
$ErrorActionPreference = 'Stop'
if ("$sales".Trim() -eq '0') {
    Write-Host 'Baza jest pusta, mapa otworzy sie bez transakcji. Import RCN powiatu:'
    Write-Host '  docker compose exec app python -m landscope import-rcn --county 0801'
} elseif ("$sales".Trim() -match '^\d+$') {
    Write-Host "Sprzedazy w bazie: $($sales.Trim())"
}

try {
    Start-Process $ui | Out-Null
    Write-Host 'Otwieram interfejs w przegladarce.'
} catch {
    Write-Host "Serwer dziala. Otworz recznie: $ui"
}
exit 0
