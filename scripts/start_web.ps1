$ErrorActionPreference = "Stop"

$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot

$pythonCandidates = @(
  (Join-Path $projectRoot ".venv\\Scripts\\python.exe"),
  (Join-Path $projectRoot "venv\\Scripts\\python.exe"),
  "py",
  "python"
)

$pythonCommand = $null
foreach ($candidate in $pythonCandidates) {
  if ($candidate -like "*.exe" -and (Test-Path $candidate)) {
    $pythonCommand = $candidate
    break
  }

  if ($candidate -in @("py", "python")) {
    try {
      Get-Command $candidate -ErrorAction Stop | Out-Null
      $pythonCommand = $candidate
      break
    } catch {
    }
  }
}

if (-not $pythonCommand) {
  throw "No Python runtime found. Create .venv first or install Python/py launcher."
}

Write-Host "Using Python: $pythonCommand"
Write-Host "Open http://127.0.0.1:8000 in browser"

if ($pythonCommand -eq "py") {
  & py -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
} else {
  & $pythonCommand -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
}
