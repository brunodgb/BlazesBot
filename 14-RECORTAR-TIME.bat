@echo off
setlocal
title BlazesBot - Recortar o painel de time

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Solicitando privilegios de administrador...
    rem AS ASPAS SIMPLES SAO OBRIGATORIAS. O caminho tem espacos
    rem ("Versoes do Bot", "BlazesBot22 - Copia"); sem elas o Start-Process le
    rem -FilePath como "D:\Versoes" e o resto como argumentos soltos, falha, e o
    rem exit /b abaixo fecha a janela -- o script nunca roda e nao sobra saida
    rem nenhuma. Era o unico .bat do projeto sem as aspas, e foi por isso que
    rem esta ferramenta "abria e fechava sozinha" em tres tentativas.
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo.
echo  O time precisa estar FORMADO na tela, e o bot PARADO.
echo.
.venv\Scripts\python.exe -m blazesbot.bot.recorte_do_time %*
echo.
echo  Saida completa tambem em: logs\recorte_do_time\recorte.log
pause
