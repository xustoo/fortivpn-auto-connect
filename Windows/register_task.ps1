# Kurulum sirasinda BIR KEZ UAC ister ve yonetici yetkisi gereken adimlari tek
# seferde yapar:
#   1) (istege bagli) openconnect installer'ini sessiz modda calistirir
#   2) "en yuksek yetkiyle" calisan, istek uzerine (on-demand) baslatilan bir
#      Gorev Zamanlayici gorevi kaydeder. Masaustu kisayolu bu gorevi
#      `schtasks /run` ile tetikler -> UAC cikmaz.
# Parametrelerden hangisi verilirse yalnizca o adim yapilir.
param(
    [string]$PythonExe,
    [string]$ProjectDir,
    [string]$OpenConnectInstaller,
    [string]$UserName = "$env:USERDOMAIN\$env:USERNAME"
)

$TaskName = "FortiVPN-AutoConnect"

$principalId = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$principalId).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    # Tek seferlik UAC istemi: ayni betigi yonetici olarak yeniden baslat.
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -UserName `"$UserName`""
    if ($PythonExe)            { $argList += " -PythonExe `"$PythonExe`"" }
    if ($ProjectDir)           { $argList += " -ProjectDir `"$ProjectDir`"" }
    if ($OpenConnectInstaller) { $argList += " -OpenConnectInstaller `"$OpenConnectInstaller`"" }
    try {
        $p = Start-Process powershell -Verb RunAs -Wait -PassThru -ArgumentList $argList
        exit $p.ExitCode
    } catch {
        Write-Host "UAC onaylanmadi, yonetici adimlari yapilamadi." -ForegroundColor Yellow
        exit 1
    }
}

$exitCode = 0

if ($OpenConnectInstaller) {
    $ocExe = Join-Path $env:ProgramFiles "OpenConnect\openconnect.exe"
    try {
        Write-Host "openconnect kuruluyor (sessiz kurulum, wintun surucusu dahil)..."
        # Bu oturum zaten yukseltilmis oldugundan installer ikinci bir UAC sormaz.
        Start-Process -FilePath $OpenConnectInstaller -ArgumentList "/S" -Wait
        for ($i = 0; $i -lt 20 -and -not (Test-Path $ocExe); $i++) { Start-Sleep -Seconds 1 }
        if (Test-Path $ocExe) {
            Write-Host "openconnect kuruldu: $ocExe" -ForegroundColor Green
        } else {
            Write-Host "openconnect kurulumu tamamlanmadi." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "openconnect kurulamadi: $_" -ForegroundColor Red
    }
}

if ($PythonExe -and $ProjectDir) {
    try {
        $pythonw = Join-Path (Split-Path $PythonExe -Parent) "pythonw.exe"
        if (-not (Test-Path $pythonw)) { $pythonw = $PythonExe }

        $action    = New-ScheduledTaskAction -Execute $pythonw `
                        -Argument "`"$(Join-Path $ProjectDir 'main.py')`"" -WorkingDirectory $ProjectDir
        $principal = New-ScheduledTaskPrincipal -UserId $UserName -LogonType Interactive -RunLevel Highest
        # Pil ayarlari kapali olmazsa dizustunde gorev "Queued"da takilir.
        $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                        -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
                        -StartWhenAvailable

        Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal `
            -Settings $settings -Force | Out-Null
        Write-Host "Gorev kaydedildi: $TaskName" -ForegroundColor Green
    } catch {
        Write-Host "Gorev kaydedilemedi: $_" -ForegroundColor Red
        $exitCode = 1
    }
}

# Yukseltilmis pencere kapanmadan once sonucun okunabilmesi icin.
Start-Sleep -Seconds 2
exit $exitCode
