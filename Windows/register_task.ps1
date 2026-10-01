# Kurulum sirasinda BIR KEZ UAC ister ve "en yuksek yetkiyle" calisan, istek
# uzerine (on-demand) baslatilan bir Gorev Zamanlayici gorevi kaydeder.
# Masaustu kisayolu bu gorevi `schtasks /run` ile tetikler -> UAC cikmaz.
param(
    [Parameter(Mandatory = $true)][string]$PythonExe,
    [Parameter(Mandatory = $true)][string]$ProjectDir,
    [string]$UserName = "$env:USERDOMAIN\$env:USERNAME"
)

$TaskName = "FortiVPN-AutoConnect"

$principalId = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = ([Security.Principal.WindowsPrincipal]$principalId).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    # Tek seferlik UAC istemi: ayni betigi yonetici olarak yeniden baslat.
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" " +
               "-PythonExe `"$PythonExe`" -ProjectDir `"$ProjectDir`" -UserName `"$UserName`""
    try {
        $p = Start-Process powershell -Verb RunAs -Wait -PassThru -ArgumentList $argList
        exit $p.ExitCode
    } catch {
        Write-Host "UAC onaylanmadi, gorev kaydedilemedi." -ForegroundColor Yellow
        exit 1
    }
}

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
    exit 0
} catch {
    Write-Host "Gorev kaydedilemedi: $_" -ForegroundColor Red
    exit 1
}
