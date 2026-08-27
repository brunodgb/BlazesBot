@echo off
setlocal
title BlazesBot (Interface Web)

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

rem Confere se o pywebview foi instalado (vem no requirements.txt).
".venv\Scripts\python.exe" -c "import webview" >nul 2>&1
if %errorLevel% NEQ 0 (
    echo ============================================================
    echo   [ERRO] Pacote "pywebview" nao encontrado.
    echo ============================================================
    echo.
    echo   Instale com:
    echo     ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

rem ============================================================
rem  Roda a interface WEB (pywebview + WebView2) sem tocar no main.py.
rem  E a GUI PyQt6 original: use o 3-INICIAR.bat.
rem ============================================================
".venv\Scripts\python.exe" -m blazesbot.web_app

echo.
pause