param(
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$now = Get-Date
$buildNumber = $now.ToString("yyyyMMdd.HHmmss")
$env:BUILD_NUMBER = $buildNumber
Write-Host "Building OpenSpoolMan with BUILD_NUMBER=$buildNumber"

docker compose build openspoolman
if (-not $NoStart) {
    docker compose up -d openspoolman
}
