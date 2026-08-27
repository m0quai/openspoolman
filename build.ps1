param(
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$sequencePath = Join-Path $PSScriptRoot ".build-sequence"
$now = Get-Date
$weekday = [int]$now.DayOfWeek
$dateKey = $now.ToString("yyyyMMdd")
$counter = 1

if (Test-Path -LiteralPath $sequencePath) {
    $parts = (Get-Content -LiteralPath $sequencePath -Raw).Trim().Split("|")
    if ($parts.Count -ge 2 -and $parts[0] -eq [string]$weekday) {
        $counter = ([int]$parts[1]) + 1
    }
}

$buildNumber = "{0}.{1:D2}" -f $dateKey, $counter
Set-Content -LiteralPath $sequencePath -Value "$weekday|$counter" -NoNewline
$env:BUILD_NUMBER = $buildNumber
Write-Host "Building OpenSpoolMan with BUILD_NUMBER=$buildNumber"

docker compose build openspoolman
if (-not $NoStart) {
    docker compose up -d openspoolman
}
