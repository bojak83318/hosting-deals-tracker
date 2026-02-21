$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$testPaths = @(
  'tests/test_let_api_fetcher.py',
  'tests/test_db_manager.py',
  'tests/test_discord.py',
  'tests/test_web.py'
)

Write-Host '==> Windows compatibility test helper'
Write-Host "Python: $(python --version)"

Write-Host '==> Upgrading pip'
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
  throw "pip upgrade failed with exit code $LASTEXITCODE"
}

Write-Host '==> Installing test dependencies'
python -m pip install pytest requests beautifulsoup4 flask
if ($LASTEXITCODE -ne 0) {
  throw "dependency install failed with exit code $LASTEXITCODE"
}

Write-Host '==> Running targeted pytest subset'
Write-Host "Targets: $($testPaths -join ', ')"
python -m pytest -q @testPaths
if ($LASTEXITCODE -ne 0) {
  throw "pytest failed with exit code $LASTEXITCODE"
}

Write-Host '==> Windows compatibility tests passed'
