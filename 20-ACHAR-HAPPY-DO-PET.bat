@echo off
setlocal
title BlazesBot - Achar a felicidade do pet na memoria

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
echo   ACHAR A FELICIDADE DO PET NA MEMORIA
echo ============================================================
echo.
echo Procura uma CADEIA DE PONTEIROS que sobreviva a relogin -- um
echo endereco solto do heap (tipo 0x2DC83FDC) muda a cada login.
echo.
echo SO LE a memoria dos clientes; nunca escreve.
echo.
echo O QUE VOCE PRECISA TER EM MAOS: a felicidade ATUAL do pet em
echo pelo menos DUAS contas, com valores DIFERENTES. E isso que
echo separa o campo certo dos milhares de "98" espalhados.
echo.
echo Deixe as contas logadas e com o pet invocado.
echo.

set /p CONTA1=Titulo da janela 1 (ex: BlazesOfGamer):
set /p HAPPY1=Felicidade do pet dessa conta:
set /p CONTA2=Titulo da janela 2 (ex: WizzOfBlazes5):
set /p HAPPY2=Felicidade do pet dessa conta:
set /p CONTA3=Titulo da janela 3 (Enter para pular):
if "%CONTA3%"=="" goto :duas
set /p HAPPY3=Felicidade do pet dessa conta:
".venv\Scripts\python.exe" -m blazesbot.tools.achar_happy_do_pet "%CONTA1%=%HAPPY1%" "%CONTA2%=%HAPPY2%" "%CONTA3%=%HAPPY3%"
goto :fim

:duas
".venv\Scripts\python.exe" -m blazesbot.tools.achar_happy_do_pet "%CONTA1%=%HAPPY1%" "%CONTA2%=%HAPPY2%"

:fim
echo.
pause
