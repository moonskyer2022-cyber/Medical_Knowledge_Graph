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

Write-Host "[1/4] 运行测试..." -ForegroundColor Cyan
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "测试失败。" }

Write-Host "[2/4] 检查 UTF-8 编码..." -ForegroundColor Cyan
& $python scripts/check_encoding.py
if ($LASTEXITCODE -ne 0) { throw "存在非 UTF-8 文本文件。" }

Write-Host "[3/4] 检查 Git diff..." -ForegroundColor Cyan
& git diff --check
if ($LASTEXITCODE -ne 0) { throw "检测到空白或冲突标记问题。" }

if (-not $SkipDocker) {
    Write-Host "[4/4] 校验 Docker Compose 配置..." -ForegroundColor Cyan
    & docker compose config -q
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose 配置无效。" }
} else {
    Write-Host "[4/4] 已跳过 Docker Compose 校验。" -ForegroundColor Yellow
}

Write-Host "质量门禁通过。" -ForegroundColor Green
