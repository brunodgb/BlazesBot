@echo off
setlocal
title BlazesBot - Leitor da camera

net session >nul 2>&1
if %errorLevel% NEQ 0 goto PRECISA_ADMIN

cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto SEM_AMBIENTE

echo ============================================================
echo   LEITOR DA CAMERA  (SO LE - nao escreve nada no jogo)
echo ============================================================
echo.
echo Serve para descobrir QUAIS sao os tres numeros da camera
echo quando ela esta na pose CERTA.
echo.
echo COMO USAR:
echo.
echo   1. Deixe esta janela aberta ao lado do jogo.
echo   2. Mexa a camera com o botao direito, de View Reset,
echo      marque o Lock the View nas opcoes de Graficos.
echo   3. Cada mudanca vira uma linha aqui.
echo   4. Quando a camera estiver na pose em que os cliques
echo      funcionam, PARE. A ultima linha e a pose de referencia.
echo.
echo Fecha sozinho em 5 minutos. Ctrl+C para encerrar antes.
echo ============================================================
echo.

set PID=
set /p PID=Digite o PID do client.exe, ou so Enter para todos: 
echo.

if "%PID%"=="" goto SEM_PID
".venv\Scripts\python.exe" main.py --ler-camera --pid %PID%
goto FIM

:SEM_PID
".venv\Scripts\python.exe" main.py --ler-camera
goto FIM

:SEM_AMBIENTE
echo ============================================================
echo   [ERRO] Ambiente nao instalado.
echo ============================================================
echo.
echo Rode primeiro o arquivo 1-INSTALAR.bat
echo.
pause
exit /b 1

:PRECISA_ADMIN
echo Solicitando privilegios de administrador...
powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
exit /b

:FIM
echo.
pause
