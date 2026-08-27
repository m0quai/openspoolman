param(
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$now = Get-Date
$buildNumber = $now.ToString("yyyyMMdd.HHmmss")
$buildCommit = (git rev-parse --short HEAD).Trim()
$env:BUILD_NUMBER = $buildNumber
Write-Host "Building OpenSpoolMan with BUILD_NUMBER=$buildNumber BUILD_COMMIT=$buildCommit"

docker compose build --no-cache --build-arg "BUILD_NUMBER=$buildNumber" --build-arg "BUILD_COMMIT=$buildCommit" openspoolman
if (-not $NoStart) {
    docker compose up -d openspoolman
}
