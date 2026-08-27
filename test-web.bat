@echo off
setlocal

rem ============================================================
rem  BlazesBot Web - Test Helper (agent-browser + CDP)
rem  Wrapper .bat para o test-web.ps1
rem ============================================================

set "PROJECT_ROOT=%~dp0"
set "POWERSHELL=powershell.exe -NoProfile -ExecutionPolicy Bypass -File"

cd /d "%PROJECT_ROOT%"

if "%1"=="-stop" (
    "%POWERSHELL%" "%PROJECT_ROOT%test-web.ps1" -Stop
    goto :eof
)

if "%1"=="-build" (
    "%POWERSHELL%" "%PROJECT_ROOT%test-web.ps1" -Build %2 %3 %4
    goto :eof
)

if "%1"=="-dist" (
    "%POWERSHELL%" "%PROJECT_ROOT%test-web.ps1" -Dist %2 %3 %4
    goto :eof
)

"%POWERSHELL%" "%PROJECT_ROOT%test-web.ps1" %*