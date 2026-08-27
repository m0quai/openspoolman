param(
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$now = Get-Date
$buildNumber = $now.ToString("yyyyMMdd.HHmmss")
$env:BUILD_NUMBER = $buildNumber
Write-Host "Building OpenSpoolMan with BUILD_NUMBER=$buildNumber"

docker compose build --no-cache --build-arg "BUILD_NUMBER=$buildNumber" openspoolman
if (-not $NoStart) {
    docker compose up -d openspoolman
}
