param([switch]$Online,[switch]$E2E,[switch]$RealData)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$testArgs = @('-m','pytest','--integration','--junitxml=reports/tests.xml')
if ($Online) { $testArgs += '--online' }
if ($E2E) { $testArgs += '--e2e' }
if ($RealData) { $testArgs += '--real-data' }
& ./.venv/Scripts/python.exe @testArgs
exit $LASTEXITCODE
