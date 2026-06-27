#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (Test-Path -LiteralPath "dist") {
    Remove-Item -LiteralPath "dist" -Recurse -Force
}
if (Test-Path -LiteralPath "build") {
    Remove-Item -LiteralPath "build" -Recurse -Force
}

py -m PyInstaller `
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

if ($cert) {
    Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert -TimestampServer "http://timestamp.digicert.com" | Out-Null
    Write-Host "Signed $exePath"
} else {
    Write-Warning "No local code-signing certificate found; built executable is unsigned."
}

Write-Host "Built $exePath"
