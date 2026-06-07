$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
python scripts/clean.py
python scripts/import_neo4j.py --full
Write-Host "Done. Start API: .\scripts\start_web.ps1"
