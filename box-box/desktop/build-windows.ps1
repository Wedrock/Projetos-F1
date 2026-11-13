# Gera o Box Box para Windows: dist\BoxBox\BoxBox.exe e o instalador
# dist\BoxBox-Setup-<versão>.exe.
#
# Precisa de: Python 3.11 (64 bits), Node.js 20 e, para o instalador,
# Inno Setup 6 (https://jrsoftware.org/isinfo.php).
#
# Uso (PowerShell, dentro de box-box\desktop):
#   .\build-windows.ps1                 # versão padrão
#   .\build-windows.ps1 -Version 2.6.0
param(
    [string]$Version = "2.5.1",
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
$Desktop = $PSScriptRoot
$Root = Split-Path $Desktop -Parent

Write-Host "==> Compilando o frontend" -ForegroundColor Cyan
Push-Location "$Root\frontend"
npm ci
if ($LASTEXITCODE) { throw "npm ci falhou" }
npm run build
if ($LASTEXITCODE) { throw "npm run build falhou" }
Pop-Location

Write-Host "==> Preparando o Python" -ForegroundColor Cyan
$Venv = "$Desktop\.venv"
if (-not (Test-Path "$Venv\Scripts\python.exe")) { py -3.11 -m venv $Venv }
$Py = "$Venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r "$Root\backend\requirements.txt" -r "$Desktop\requirements.txt"
if ($LASTEXITCODE) { throw "pip install falhou" }

Write-Host "==> Empacotando com PyInstaller" -ForegroundColor Cyan
Push-Location $Desktop
& $Py -m PyInstaller --noconfirm --clean boxbox.spec
if ($LASTEXITCODE) { throw "PyInstaller falhou" }

if (-not $SkipInstaller) {
    $Iscc = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($Iscc) {
        Write-Host "==> Gerando o instalador" -ForegroundColor Cyan
        & $Iscc "/DAppVersion=$Version" installer.iss
        if ($LASTEXITCODE) { throw "Inno Setup falhou" }
    } else {
        Write-Warning "Inno Setup 6 não encontrado: pulei o instalador. O app está em dist\BoxBox."
    }
}
Pop-Location

Write-Host "Pronto! Veja box-box\desktop\dist" -ForegroundColor Green
