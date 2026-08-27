@echo off
setlocal
title BlazesBot - Teste de Login

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
echo   TESTE DE LOGIN
echo ============================================================
echo.
echo Faz SOMENTE o login e para:
echo   - abre o cliente do jogo
echo   - digita usuario e senha
echo   - se a senha estiver errada, fecha o aviso e tenta de novo
echo   - escolhe o servidor
echo   - se cair a conexao, fecha o aviso e refaz
echo   - se cair na fila, apenas ESPERA
echo   - quando os personagens aparecerem, clica em Enter Game
echo.
echo FECHE o jogo antes de continuar.
echo.
pause
echo.
".venv\Scripts\python.exe" main.py --login-test

echo.
pause
