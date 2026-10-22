$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)

$toolsDir = Join-Path (Get-Location) 'tools'
$exe = Join-Path $toolsDir 'cloudflared.exe'
$reportsDir = Join-Path (Get-Location) 'reports'
$log = Join-Path $reportsDir 'cloudflare-tunnel.log'
$errLog = Join-Path $reportsDir 'cloudflare-tunnel.err.log'
$urlFile = Join-Path $reportsDir 'share-url.txt'
$pidFile = Join-Path $reportsDir 'cloudflare-tunnel.pid'
$downloadUrl = 'https://github.com/cloudflare/cloudflared/releases/download/2026.10.3/cloudflared-windows-amd64.exe'
$expectedHash = '76B2805253D0D6FFACB092A7ACFBEE99E7AF6917835C0C5410E23F3EF5052DA2'

Write-Host 'Tymczasowy tunel HTTPS do lokalnego UI (http://127.0.0.1:8000).'
Write-Host ''

try {
    $null = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 5
} catch {
    Write-Host 'Aplikacja nie odpowiada na http://127.0.0.1:8000'
    Write-Host 'Najpierw: .\scripts\start.ps1'
    exit 1
}

function Read-ShareUrl {
    param([string[]]$Paths)
    foreach ($Path in $Paths) {
        if (-not (Test-Path -LiteralPath $Path)) { continue }
        $text = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
        if (-not $text) { continue }
        $m = [regex]::Match($text, 'https://[a-z0-9-]+\.trycloudflare\.com')
        if ($m.Success) { return $m.Value }
    }
    return $null
}

function Test-TunnelPid {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $raw = (Get-Content -LiteralPath $Path -ErrorAction SilentlyContinue | Select-Object -First 1)
    $oldPid = 0
    if (-not [int]::TryParse($raw, [ref]$oldPid)) { return $null }
    $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -like 'cloudflared*') { return $proc }
    return $null
}

New-Item -ItemType Directory -Force -Path $toolsDir, $reportsDir | Out-Null

$needDownload = $true
if (Test-Path -LiteralPath $exe) {
    $hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
    if ($hash -eq $expectedHash) { $needDownload = $false }
}
if ($needDownload) {
    Write-Host 'Pobieram cloudflared (jednorazowo, zostaje w tools/)...'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $exe -UseBasicParsing
    $hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
    if ($hash -ne $expectedHash) {
        Remove-Item -LiteralPath $exe -Force
        throw "Suma SHA256 cloudflared sie nie zgadza ($hash)."
    }
}

$existing = Test-TunnelPid $pidFile
$existingUrl = Read-ShareUrl @($urlFile, $log, $errLog)
if ($existing -and $existingUrl) {
    Write-Host "Link juz dziala (PID $($existing.Id)):"
    Write-Host $existingUrl
    Write-Host ''
    Write-Host 'Komputer i Docker musza byc wlaczone. Nowy URL: zatrzymaj proces i odpal skrypt ponownie.'
    exit 0
}

if ($existing) {
    Stop-Process -Id $existing.Id -Force -ErrorAction SilentlyContinue
}

Remove-Item -LiteralPath $log, $errLog, $urlFile -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath $exe -ArgumentList @('tunnel', '--url', 'http://127.0.0.1:8000', '--no-autoupdate') `
    -RedirectStandardOutput $log -RedirectStandardError $errLog -WindowStyle Hidden -PassThru -ErrorAction Stop
$proc.Id | Set-Content -LiteralPath $pidFile -Encoding ascii

$url = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    if ($proc.HasExited) {
        Write-Host 'cloudflared zakonczyl sie od razu. Log:'
        if (Test-Path -LiteralPath $errLog) { Get-Content -LiteralPath $errLog }
        elseif (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log }
        exit 1
    }
    $url = Read-ShareUrl @($errLog, $log)
    if ($url) { break }
}

if (-not $url) {
    Write-Host 'Nie pojawil sie jeszcze adres trycloudflare.com. Sprawdz reports/cloudflare-tunnel.log'
    exit 1
}

Set-Content -LiteralPath $urlFile -Value $url -Encoding ascii
Write-Host 'Adres tunelu:'
Write-Host $url
Write-Host ''
Write-Host 'URL jest tymczasowy i nie ma osobnych kont. Nie publikuj go publicznie.'
Write-Host 'Po restarcie komputera albo tego skryptu adres sie zmieni.'
Write-Host 'Zatrzymanie: Stop-Process -Id' $proc.Id
