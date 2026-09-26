@echo off
setlocal
title BlazesBot - Instalacao
cd /d "%~dp0"

echo ============================================================
echo   BlazesBot - Instalacao
echo ============================================================
echo.
echo Este passo NAO precisa de administrador.
echo Ele cria um Python isolado nesta pasta (.venv), garantindo
echo que as bibliotecas fiquem exatamente onde o bot procura.
echo.

set BASEPY=
py -3 --version >nul 2>&1 && set BASEPY=py -3
if not defined BASEPY (python --version >nul 2>&1 && set BASEPY=python)

if not defined BASEPY (
    echo [ERRO] Python nao encontrado no sistema.
    echo.
    echo   1. Acesse https://www.python.org/downloads/
    echo   2. Baixe a versao 3.12 ou 3.13
    echo   3. NA PRIMEIRA TELA MARQUE:  [x] Add python.exe to PATH
    echo   4. Install Now
    echo   5. REINICIE o computador e rode este arquivo de novo
    echo.
    pause
    exit /b 1
)

echo Python base encontrado:
%BASEPY% --version
echo.

if exist ".venv\Scripts\python.exe" (
    echo Ambiente .venv ja existe, reaproveitando.
) else (
    echo Criando ambiente isolado .venv ...
    %BASEPY% -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente.
        echo Se a pasta estiver no OneDrive ou em local protegido,
        echo mova tudo para C:\BlazesBot e tente de novo.
        pause
        exit /b 1
    )
)
echo.

echo Atualizando o pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
echo.
echo Instalando bibliotecas (cerca de 150 MB, 2 a 10 minutos) ...
echo.
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERRO] Alguma biblioteca falhou. Veja a mensagem acima.
    echo Causa mais comum: versao do Python muito nova.
    echo Nesse caso instale o Python 3.12, APAGUE a pasta .venv
    echo e rode este arquivo novamente.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   VERIFICANDO
echo ============================================================
".venv\Scripts\python.exe" verificar.py
if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo   INSTALACAO CONCLUIDA
echo ============================================================
echo.
echo Proximos passos, nesta ordem:
echo   1. Abra o jogo, entre com um personagem
echo   2. Rode 2-DIAGNOSTICO.bat
echo   3. Rode 3-INICIAR-WEB.bat e configure contas e teclas
echo   4. Rode 4-TESTE-LOGIN.bat
echo.
pause
