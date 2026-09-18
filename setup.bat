@echo off
setlocal
cd /d "%~dp0"

echo === FortiVPN Auto-Connect setup ===

where python >nul 2>nul
if %errorlevel%==0 ( set "PYLAUNCH=python" ) else ( set "PYLAUNCH=py" )

echo.
echo --- Python bagimliliklari ---
%PYLAUNCH% -m pip install --upgrade pip
%PYLAUNCH% -m pip install -r requirements.txt

if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo .env dosyasi olusturuldu - VPN_SERVER / VPN_USER / VPN_PASS / IMAP_* alanlarini duzenleyin.
)

echo.
echo --- openconnect (VPN istemcisi) ---
where openconnect >nul 2>nul
if %errorlevel%==0 goto oc_ok
if exist "C:\Program Files\OpenConnect\openconnect.exe" goto oc_ok
if exist "C:\Program Files (x86)\OpenConnect\openconnect.exe" goto oc_ok

set "OCURL=https://gitlab.com/openconnect/openconnect/-/jobs/artifacts/v9.21/raw/openconnect-installer-MinGW64-GnuTLS.exe?job=MinGW64%%2FGnuTLS"
set "OCEXE=%TEMP%\openconnect-installer.exe"
echo openconnect kurulu degil.
echo Resmi installer indirilecek (openconnect v9.21, ~3.4 MB, wintun surucusu dahil):
echo   %OCURL%
set /p OCDL="Indirilip kurulsun mu? (Y/N): "
if /i not "%OCDL%"=="Y" goto oc_skip

echo Indiriliyor...
powershell -NoProfile -Command "try{Invoke-WebRequest -UseBasicParsing -Uri $env:OCURL -OutFile $env:OCEXE; exit 0}catch{Write-Host $_; exit 1}"
if errorlevel 1 ( echo Indirme basarisiz oldu. & goto oc_skip )
echo Installer baslatiliyor (yonetici onayi (UAC) isteyebilir, wintun surucusunu de kurar)...
"%OCEXE%" /S
timeout /t 5 /nobreak >nul
if exist "C:\Program Files\OpenConnect\openconnect.exe" ( echo openconnect kuruldu. ) else ( echo NOT: kurulum tamamlanmamis olabilir - .env icinde OPENCONNECT_EXE ile yolu belirtin. )
goto oc_done

:oc_skip
echo openconnect atlandi. Daha sonra kurup .env icinde OPENCONNECT_EXE ile yolunu belirtebilirsiniz.
goto oc_done
:oc_ok
echo openconnect zaten kurulu.
:oc_done

echo.
echo Kurulum tamamlandi. Sonraki adimlar:
echo   1) .env dosyasini VPN ve IMAP bilgilerinizle doldurun
echo   2) python main.py  (yonetici yetkisi gerekir - UAC istemine "Evet" deyin)
echo.
pause
