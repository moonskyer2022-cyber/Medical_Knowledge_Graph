[CmdletBinding()]
param(
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到 .venv\Scripts\python.exe，请先按 README 初始化虚拟环境。"
}

Write-Host "[1/3] 运行测试..." -ForegroundColor Cyan
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "测试失败。" }

Write-Host "[2/3] 检查 Git diff..." -ForegroundColor Cyan
& git diff --check
if ($LASTEXITCODE -ne 0) { throw "检测到空白或冲突标记问题。" }

if (-not $SkipDocker) {
    Write-Host "[3/3] 校验 Docker Compose 配置..." -ForegroundColor Cyan
    & docker compose config -q
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose 配置无效。" }
} else {
    Write-Host "[3/3] 已跳过 Docker Compose 校验。" -ForegroundColor Yellow
}

Write-Host "质量门禁通过。" -ForegroundColor Green
