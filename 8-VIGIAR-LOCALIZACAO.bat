@echo off
setlocal
title BlazesBot - Vigia da localizacao

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
echo   VIGIA DO PONTEIRO DE LOCALIZACAO
echo ============================================================
echo.
echo Isto NAO mexe no jogo e NAO interfere no bot.
echo Ele so fica lendo o nome do lugar a cada segundo e gravando.
echo.
echo Deixe esta janela aberta em paralelo com o bot, o dia todo.
echo Quando a localizacao quebrar, o arquivo
echo.
echo     logs\localizacao.log
echo.
echo vai ter o instante exato, a POSICAO onde estava e o valor de
echo cada elo da cadeia de ponteiros. E esse arquivo que me manda.
echo.
echo Ctrl+C para encerrar.
echo ============================================================
echo.
".venv\Scripts\python.exe" main.py --watch-location

echo.
pause
