@echo off
setlocal
title BlazesBot - Teste de captura

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
echo   TESTE DE CAPTURA DE TELA
echo ============================================================
echo.
echo Rode isto com o jogo ABERTO, em qualquer tela.
echo.
echo Ele salva em logs\ um PNG do que o bot consegue capturar.
echo Se o PNG sair PRETO, o problema e a captura e nao os
echo templates -- e o bot vai operar as cegas pelo roteiro.
echo.
pause
echo.
".venv\Scripts\python.exe" main.py --capture-test

echo.
pause
