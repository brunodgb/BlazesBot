@echo off
setlocal
title BlazesBot - gerar o .exe para entregar

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente nao instalado. Rode o 1-INSTALAR.bat primeiro.
    pause
    exit /b 1
)

rem O PyInstaller NAO entra no requirements.txt: ele so serve para empacotar, e
rem sao ~40 MB que nenhuma maquina que apenas RODA o bot precisa baixar.
".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Instalando o PyInstaller ^(so da primeira vez^)...
    ".venv\Scripts\python.exe" -m pip install pyinstaller
)

rem A TELA COMPILADA VAI DENTRO DO PACOTE. Quem recebe nao tem npm, entao o
rem dist/ precisa estar atualizado ANTES -- rode `npm run build` se mexeu em web/.
if not exist "dist\index.html" (
    echo [ERRO] Nao existe dist\index.html. Rode: npm run build
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m blazesbot.tools.empacotar

echo.
pause
