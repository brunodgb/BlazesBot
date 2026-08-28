@echo off
setlocal
title BlazesBot - Aferir o alvo aliado (Fada)

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Solicitando privilegios de administrador...
    rem AS ASPAS SIMPLES SAO OBRIGATORIAS: o caminho tem espacos. Ver o mesmo
    rem bloco no 14-RECORTAR-TIME.bat, onde a falta delas fez a ferramenta
    rem "abrir e fechar sozinha".
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo.
echo  O time precisa estar FORMADO na tela, e o bot PARADO.
echo.
echo  Ela clica no rosto de cada companheiro e mede o que a memoria passa a
echo  ver. NAO usa skill, NAO anda, NAO abre janela.
echo.
echo  Ela vai LISTAR as janelas abertas e pedir para voce escolher a da
echo  FADA -- e a tela DELA que mostra os companheiros dela.
echo  Para repetir sem escolher: 18-AFERIR-ALVO-ALIADO.bat --pid 12345
echo.
.venv\Scripts\python.exe -m blazesbot.bot.app.afericao_do_aliado %*
echo.
echo  A prova em PNG fica em: logs\afericao_aliado\
pause
