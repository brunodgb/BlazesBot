@echo off
setlocal
title BlazesBot - Deteccao de tela

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

echo ============================================================
echo   DETECCAO DE TELA AO VIVO
echo ============================================================
echo.
echo Abra o jogo e va navegando pelas telas: login, servidor,
echo fila, selecao de personagem. Esta janela mostra o que o bot
echo reconhece em cada momento.
echo.
echo Ctrl+C para sair.
echo.
pause
echo.
".venv\Scripts\python.exe" main.py --detect

echo.
pause
