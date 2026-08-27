@echo off
setlocal
title BlazesBot - Descobrir ponteiro base

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
echo   DESCOBRIR O PONTEIRO BASE DA MEMORIA
echo ============================================================
echo.
echo Use isto quando o 2-DIAGNOSTICO.bat mostrar FALHA em
echo HP, posicao ou nome do personagem.
echo.
echo O jogo precisa estar ABERTO e voce LOGADO no mundo.
echo.
set /p CHARNAME=Digite o nome EXATO do personagem logado: 
echo.
".venv\Scripts\python.exe" main.py --find-base --char "%CHARNAME%"

echo.
pause
