#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repoRoot "work\build-venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"
Set-Location $repoRoot

if (Test-Path -LiteralPath $venvPath) {
    Remove-Item -LiteralPath $venvPath -Recurse -Force
}

py -m venv $venvPath
& $pythonPath -m pip install --requirement requirements.txt

if (Test-Path -LiteralPath "dist") {
    Remove-Item -LiteralPath "dist" -Recurse -Force
}
if (Test-Path -LiteralPath "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}

& $pythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name AppList `
    --runtime-hook tools/runtime_hook_mp.py `
    --collect-data customtkinter `
    AppList.py

$exePath = Join-Path $repoRoot "dist\AppList.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Build finished without dist\AppList.exe"
}

$cert = $null
try {
    $cert = Get-ChildItem Cert:\CurrentUser\My -ErrorAction SilentlyContinue |
        Where-Object {
            $_.HasPrivateKey -and (
                $_.EnhancedKeyUsageList.FriendlyName -contains "Code Signing" -or
                $_.EnhancedKeyUsageList.ObjectId -contains "1.3.6.1.5.5.7.3.3"
            )
        } |
        Select-Object -First 1
} catch {
    $cert = $null
}

$signatureStatus = "unsigned"
if ($cert) {
    Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert -TimestampServer "http://timestamp.digicert.com" | Out-Null
    $signatureStatus = "signed"
    Write-Host "Signed $exePath"
} else {
    Write-Warning "No local code-signing certificate found; built executable is unsigned."
}

$sha256 = (Get-FileHash -LiteralPath $exePath -Algorithm SHA256).Hash
$pyVersion = & $pythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
$pyiVersion = & $pythonPath -c "import PyInstaller; print(PyInstaller.__version__)"
$appVersion = & $pythonPath -c "from applist import APP_VERSION; print(APP_VERSION)"
$depFreeze = & $pythonPath -m pip freeze 2>$null

$manifestPath = Join-Path $repoRoot "dist\release-manifest.json"
$manifest = @{
    artifact    = "AppList.exe"
    version     = $appVersion
    sha256      = $sha256.ToLower()
    signature   = $signatureStatus
    python      = $pyVersion
    pyinstaller = $pyiVersion
    built       = (Get-Date -Format "o")
    dependencies = @($depFreeze -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $manifestPath -Encoding utf8
Write-Host "Release manifest: $manifestPath"

$checksumPath = Join-Path $repoRoot "dist\AppList.exe.sha256"
"$($sha256.ToLower())  AppList.exe" | Set-Content -LiteralPath $checksumPath -Encoding utf8
Write-Host "Checksum: $checksumPath"

Write-Host "Built $exePath"
