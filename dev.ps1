# 用法:.\dev.ps1 install | backend | test | lint
param([string]$cmd = "help")
switch ($cmd) {
    "install" { Push-Location backend; pip install -e ".[dev]"; Pop-Location }
    "backend" { Push-Location backend; uvicorn src.main:app --reload --host 127.0.0.1 --port 8000; Pop-Location }
    "test"    { Push-Location backend; pytest -v; Pop-Location }
    "lint"    { Push-Location backend; ruff check src tests; mypy src; Pop-Location }
    default   { Write-Host "用法: .\dev.ps1 [install|backend|test|lint]" }
}
