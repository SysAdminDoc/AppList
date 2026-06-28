#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot "work\release-dependency-venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

Set-Location $repoRoot

if (Test-Path -LiteralPath $venvPath) {
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

py -m venv $venvPath
& $pythonPath -m pip install --requirement requirements.txt
& $pythonPath -m pip_audit --requirement requirements.txt
& $pythonPath -m unittest discover -s tests
& $pythonPath -c "import customtkinter as ctk; from applist import APP_VERSION; import applist.ui; assert ctk.__version__ == '5.2.2'; print(f'AppList v{APP_VERSION} verified with customtkinter {ctk.__version__}')"

Write-Host "Release dependency verification passed."
