@echo off
setlocal
title BlazesBot - Conferir o pet bug

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Solicitando privilegios de administrador...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Rode primeiro o 1-INSTALAR.bat
    pause
    exit /b 1
)

echo ============================================================
echo   O PET BUG ESTA APLICADO AGORA?
echo ============================================================
echo.
echo Le os dois sitios do client.exe e diz o que esta la NESTE
echo instante. SO LE -- nunca escreve.
echo.
echo Ele lista os clientes abertos com o nome do personagem: digite
echo o numero (ou o PID) da conta que voce quer conferir, ou Enter
echo para conferir todas.
echo.
echo Lembre: o patch e aplicado no LOGIN, e so em conta com farm
echo de cave (BC ou HH) ligado. Conta em modo APP nao recebe.
echo.
".venv\Scripts\python.exe" -m blazesbot.tools.conferir_petbug

echo.
pause
