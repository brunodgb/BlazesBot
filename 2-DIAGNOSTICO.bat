@echo off
setlocal
title BlazesBot - Diagnostico

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Solicitando privilegios de administrador...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ============================================================
    echo   [ERRO] Ambiente nao instalado.
    echo ============================================================
    echo.
    echo Rode primeiro o arquivo 1-INSTALAR.bat
    echo.
    pause
    exit /b 1
)

echo IMPORTANTE: o jogo precisa estar ABERTO e voce LOGADO
echo com um personagem antes de continuar.
echo.
pause
echo.
".venv\Scripts\python.exe" main.py --check

echo.
pause
