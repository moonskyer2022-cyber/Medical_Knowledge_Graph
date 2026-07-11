$ErrorActionPreference = "Stop"

$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker Desktop is required. Install and start Docker Desktop, then rerun this script."
}

Write-Host "Starting Neo4j, importing demo data, and launching the API..."
docker compose up --build --wait

try {
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 10
  Write-Host "Demo is ready: http://127.0.0.1:8000"
  Write-Host "Swagger UI:    http://127.0.0.1:8000/docs"
  Write-Host "Neo4j Browser: http://127.0.0.1:7474"
  Write-Host "API health:    $($health.status)"
} catch {
  docker compose ps
  throw "Services started but the API health check failed. Review 'docker compose logs api graph-init'."
}
