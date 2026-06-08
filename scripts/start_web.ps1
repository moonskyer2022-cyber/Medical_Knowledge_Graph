$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "Open http://127.0.0.1:8000 in browser"
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000