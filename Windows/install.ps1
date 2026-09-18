# =============================================================================
# FortiVPN Auto-Connect - Tek Satirlik Web Kurulumu (Windows)
# Kullanim (PowerShell):
#   irm https://raw.githubusercontent.com/xustoo/fortivpn-auto-connect/main/Windows/install.ps1 | iex
# =============================================================================

$ErrorActionPreference = "Stop"

function Write-Info    { param($m) Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok      { param($m) Write-Host "[BASARILI] $m" -ForegroundColor Green }
function Write-Warn    { param($m) Write-Host "[UYARI] $m" -ForegroundColor Yellow }
function Write-Err     { param($m) Write-Host "[HATA] $m" -ForegroundColor Red }

Write-Host ""
Write-Host "====================================================" -ForegroundColor Blue
Write-Host "   FortiVPN Auto-Connect - Otomatik Kurulum Sihirbazi" -ForegroundColor Blue
Write-Host "====================================================" -ForegroundColor Blue
Write-Host ""

$RepoUrl = "https://github.com/xustoo/fortivpn-auto-connect.git"
$ZipUrl  = "https://github.com/xustoo/fortivpn-auto-connect/archive/refs/heads/main.zip"

# 1. Hedef Dizin Belirleme
# Betik "irm | iex" ile calistirilirsa $PSScriptRoot bostur (bellekten calisir).
# Betik dosyaya kaydedilip proje klasoru icinden calistirilirsa, o klasore kurulum yapilir.
$InstallDir = $null
if ($PSScriptRoot) {
    $ProjectRoot = Split-Path $PSScriptRoot -Parent
    if ((Test-Path (Join-Path $ProjectRoot "main.py")) -and (Test-Path (Join-Path $ProjectRoot "vpn_worker.py"))) {
        $InstallDir = $ProjectRoot
        Write-Info "Mevcut proje dizininde kurulum yapiliyor: $InstallDir"
    }
}

if (-not $InstallDir) {
    $Desktop = [Environment]::GetFolderPath("Desktop")
    if ($Desktop -and (Test-Path $Desktop)) {
        $InstallDir = Join-Path $Desktop "FortiVPN"
    } else {
        $InstallDir = Join-Path $env:USERPROFILE "FortiVPN"
    }
    Write-Info "Hedef kurulum dizini: $InstallDir"

    $GitCmd = Get-Command git -ErrorAction SilentlyContinue
    if (Test-Path (Join-Path $InstallDir ".git")) {
        if ($GitCmd) {
            Write-Info "Mevcut repo guncelleniyor..."
            git -C "$InstallDir" pull origin main
        } else {
            Write-Warn "Git bulunamadi, mevcut kopya guncellenemedi - oldugu gibi kullanilacak."
        }
    } elseif ($GitCmd) {
        Write-Info "Proje GitHub'dan klonlaniyor..."
        git clone $RepoUrl $InstallDir
    } else {
        Write-Warn "Git bulunamadi, proje ZIP olarak indirilecek."
        $ZipPath = Join-Path $env:TEMP "fortivpn-auto-connect.zip"
        $ExtractDir = Join-Path $env:TEMP "fortivpn-auto-connect-extract"
        if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
        if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }

        Write-Info "Indiriliyor: $ZipUrl"
        Invoke-WebRequest -UseBasicParsing -Uri $ZipUrl -OutFile $ZipPath
        Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force

        $ExtractedProject = Get-ChildItem $ExtractDir | Select-Object -First 1
        New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
        Copy-Item -Path (Join-Path $ExtractedProject.FullName "*") -Destination $InstallDir -Recurse -Force

        Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
        Remove-Item $ExtractDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Ok "Proje indirildi: $InstallDir"
    }
}

# 2. Python / bagimliliklar / openconnect / masaustu kisayolu kurulumunu
#    Windows\Kurulum.bat devraliyor (tek dogru kaynak, mantik tekrarlanmiyor).
$KurulumBat = Join-Path $InstallDir "Windows\Kurulum.bat"
if (-not (Test-Path $KurulumBat)) {
    Write-Err "Kurulum.bat bulunamadi: $KurulumBat"
    exit 1
}

Write-Info "Kurulum devam ediyor: Windows\Kurulum.bat"
Write-Host ""
& $KurulumBat

Write-Host ""
Write-Ok "Web kurulumu tamamlandi."
Write-Host "Masaustundeki 'FortiVPN_Baslat.bat' dosyasina cift tiklayarak calistirabilirsiniz." -ForegroundColor Cyan
