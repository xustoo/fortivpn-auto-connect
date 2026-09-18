@echo off
setlocal
cd /d "%~dp0"

echo === FortiVPN Auto-Connect setup ===

where python >nul 2>nul
if %errorlevel%==0 (
    set "PYLAUNCH=python"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PYLAUNCH=py"
    ) else (
        set "PYLAUNCH="
    )
)

if defined PYLAUNCH goto py_found

echo.
echo Python bulunamadi.
set /p PYDL="Otomatik kurulsun mu? (Y/N): "
if /i "%PYDL%"=="Y" call :install_python

:py_found
if not defined PYLAUNCH (
    echo.
    echo HATA: Python bulunamadi ya da otomatik kurulum basarisiz oldu.
    echo Elle kurun: https://www.python.org/downloads/
    echo Kurulum sirasinda "Add Python to PATH" kutucugunu isaretleyin, sonra bu betigi tekrar calistirin.
    echo.
    pause
    exit /b 1
)

"%PYLAUNCH%" -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul
if errorlevel 1 (
    echo.
    echo UYARI: Python 3.8+ onerilir, mevcut surum daha eski olabilir:
    "%PYLAUNCH%" --version
)

echo.
echo --- Python bagimliliklari ---
"%PYLAUNCH%" -m pip install --upgrade pip
if errorlevel 1 echo UYARI: pip guncellenemedi, devam ediliyor.

"%PYLAUNCH%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Normal kurulum basarisiz oldu, --user ile tekrar deneniyor...
    "%PYLAUNCH%" -m pip install --user -r requirements.txt
    if errorlevel 1 (
        echo.
        echo HATA: bagimliliklar kurulamadi. Yukaridaki pip hatasina bakin.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo .env dosyasi olusturuldu - VPN_SERVER / VPN_USER / VPN_PASS / IMAP_* alanlarini duzenleyin.
)

echo.
echo --- openconnect (VPN istemcisi) ---
where openconnect >nul 2>nul
if %errorlevel%==0 goto oc_ok
if exist "%ProgramFiles%\OpenConnect\openconnect.exe" goto oc_ok
if exist "%ProgramFiles(x86)%\OpenConnect\openconnect.exe" goto oc_ok

set "OCURL=https://gitlab.com/openconnect/openconnect/-/jobs/artifacts/v9.21/raw/openconnect-installer-MinGW64-GnuTLS.exe?job=MinGW64%%2FGnuTLS"
set "OCEXE=%TEMP%\openconnect-installer.exe"
echo openconnect kurulu degil.
echo Resmi installer indirilecek (openconnect v9.21, ~3.4 MB, wintun surucusu dahil):
echo   %OCURL%
set /p OCDL="Indirilip kurulsun mu? (Y/N): "
if /i not "%OCDL%"=="Y" goto oc_skip

if exist "%OCEXE%" del /f /q "%OCEXE%" >nul 2>nul
echo Indiriliyor...
powershell -NoProfile -Command "try{Invoke-WebRequest -UseBasicParsing -Uri $env:OCURL -OutFile $env:OCEXE; exit 0}catch{Write-Host $_; exit 1}"
if errorlevel 1 ( echo Indirme basarisiz oldu. & goto oc_skip )
if not exist "%OCEXE%" ( echo Indirme basarisiz oldu - dosya olusmadi. & goto oc_skip )

for %%F in ("%OCEXE%") do set "OCSIZE=%%~zF"
if %OCSIZE% LSS 100000 ( echo Indirilen dosya cok kucuk ^(%OCSIZE% byte^), bozuk olabilir. & goto oc_skip )
echo Dosya boyutu: %OCSIZE% byte

set "OCHASH="
for /f "tokens=* delims=" %%H in ('certutil -hashfile "%OCEXE%" SHA256 ^| findstr /v /i "hash certutil"') do if not defined OCHASH set "OCHASH=%%H"
if defined OCHASH (
    echo SHA256: %OCHASH%
    echo   ^(gitlab.com/openconnect/openconnect/-/pipelines uzerinden dogrulayabilirsiniz^)
)

echo Installer baslatiliyor (yonetici onayi (UAC) isteyebilir, wintun surucusunu de kurar)...
"%OCEXE%" /S
timeout /t 5 /nobreak >nul
if exist "%ProgramFiles%\OpenConnect\openconnect.exe" ( echo openconnect kuruldu. ) else ( echo NOT: kurulum tamamlanmamis olabilir - .env icinde OPENCONNECT_EXE ile yolu belirtin. )
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
exit /b 0

:install_python
where winget >nul 2>nul
if %errorlevel%==0 (
    echo winget ile Python 3.12 kuruluyor...
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    if not errorlevel 1 goto :py_refresh
    echo winget kurulumu basarisiz oldu, resmi installer denenecek...
)

set "PYURL=https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
set "PYEXE=%TEMP%\python-installer.exe"
if exist "%PYEXE%" del /f /q "%PYEXE%" >nul 2>nul
echo Python installer indiriliyor...
echo   %PYURL%
powershell -NoProfile -Command "try{Invoke-WebRequest -UseBasicParsing -Uri $env:PYURL -OutFile $env:PYEXE; exit 0}catch{Write-Host $_; exit 1}"
if errorlevel 1 ( echo Indirme basarisiz oldu. & exit /b 1 )
if not exist "%PYEXE%" ( echo Indirme basarisiz oldu - dosya olusmadi. & exit /b 1 )

for %%F in ("%PYEXE%") do set "PYSIZE=%%~zF"
if %PYSIZE% LSS 10000000 ( echo Indirilen dosya cok kucuk ^(%PYSIZE% byte^), bozuk olabilir. & exit /b 1 )

echo Kuruluyor (sessiz kurulum, birkac dakika surebilir)...
"%PYEXE%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1
if errorlevel 1 ( echo Python kurulumu basarisiz oldu. & exit /b 1 )

:py_refresh
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USERPATH=%%B"
for /f "tokens=2,*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYSPATH=%%B"
if defined SYSPATH if defined USERPATH call set "PATH=%SYSPATH%;%USERPATH%"

where python >nul 2>nul
if %errorlevel%==0 ( set "PYLAUNCH=python" & exit /b 0 )
where py >nul 2>nul
if %errorlevel%==0 ( set "PYLAUNCH=py" & exit /b 0 )

for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PYLAUNCH=%%D\python.exe"
for /d %%D in ("%ProgramFiles%\Python3*") do if exist "%%D\python.exe" set "PYLAUNCH=%%D\python.exe"
exit /b 0
