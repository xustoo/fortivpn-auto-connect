@echo off
chcp 65001 >nul
title FortiVPN Auto-Connect - Kurulum Sihirbazi
cls

echo ====================================================
echo    FortiVPN Auto-Connect - Windows Kurulum Araci
echo ====================================================
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [INFO] Python kontrol ediliyor...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python sisteme yuklu degil veya PATH'e eklenmemis.
    echo Lutfen https://www.python.org adresinden Python 3 kurup 'Add Python to PATH' secenegini isaretleyin.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PY_VER=%%i
echo [BASARILI] %PY_VER% tespit edildi.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Izole Python sanal ortami olusturuluyor (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [HATA] Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
)

echo [INFO] Bagimliliklar yukleniyor...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
if exist "requirements.txt" (
    .venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
)
echo [BASARILI] Python bagimliliklari kuruldu.

if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [INFO] Varsayilan .env yapilandirma dosyasi olusturuldu.
    )
) else (
    echo [BASARILI] Mevcut .env dosyasi korundu.
)

set CLI_PATH="C:\Program Files (x86)\Fortinet\SslvpnClient\FortiSSLVPNcli.exe"
if not exist %CLI_PATH% (
    echo [UYARI] FortiClient SSL VPN CLI bulunamadi: %CLI_PATH%
    echo Windows uzerinde FortiClient SSL VPN Client kurulu olmalidir.
) else (
    echo [BASARILI] FortiSSLVPNcli.exe tespit edildi.
)

:: Masaustu Baslatici Olusturma
set SHORTCUT_BAT="%USERPROFILE%\Desktop\FortiVPN_Baslat.bat"
(
echo @echo off
echo cd /d "%SCRIPT_DIR%"
echo start "" .venv\Scripts\pythonw.exe main.py
) > %SHORTCUT_BAT%

echo [BASARILI] Masaustu kisayolu hazirlandi: %SHORTCUT_BAT%
echo.
echo ====================================================
echo    Kurulum Basariyla Tamamlandi!
echo ====================================================
echo.
echo Masaustundeki 'FortiVPN_Baslat.bat' dosyasina tiklayarak calistirabilirsiniz.
echo.
pause
