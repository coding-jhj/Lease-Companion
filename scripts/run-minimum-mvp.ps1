$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$repoRoot\ai\src"
Set-Location $repoRoot
python -m uvicorn app.mvp_app:app --app-dir backend --host 127.0.0.1 --port 8000
