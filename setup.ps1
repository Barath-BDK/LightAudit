# LightAudit setup. If scripts are blocked: Set-ExecutionPolicy -Scope Process Bypass
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) { python -m venv .venv --system-site-packages }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q -r requirements-core.txt
& $py -m pip install -q -e .
$ErrorActionPreference = "Continue"
& $py -m pip install -q -r requirements-models.txt
if ($LASTEXITCODE -ne 0) { Write-Host "Optional model packages could not be installed; the real-photo path will use fallbacks." }
& $py -m lightaudit.cli setup-check
