@echo off
setlocal
title BlazesBot - Vigiar combate ao vivo

net session >nul 2>&1
if %errorLevel% NEQ 0 goto PRECISA_ADMIN

cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto SEM_AMBIENTE

echo ============================================================
echo   VIGIAR COMBATE AO VIVO  (SO LE - nao escreve nada no jogo)
echo ============================================================
echo.
echo Mostra o alvo correndo na tela, do jeito que o BOT o enxerga:
echo nome, nivel, HP exato e a barra desenhada.
echo.
echo   ALVO Gun Witch   52.2%%  [#####-----]  (52/100, nv50)  -34%%
echo            personagem: vida 88%%  EM BATALHA
echo.
echo E A MESMA LEITURA QUE O BOT USA (target_hybrid), nao uma copia.
echo Se o que aparece aqui estiver errado, o bot esta errado igual.
echo.
echo COMO USAR:
echo.
echo   1. Deixe esta janela aberta ao lado do jogo.
echo   2. Escolha o NUMERO do cliente na lista que vai aparecer.
echo   3. Lute. Cada mudanca vira uma linha aqui.
echo.
echo Fecha sozinha em 15 minutos. Ctrl+C para encerrar antes.
echo ============================================================
echo.

".venv\Scripts\python.exe" main.py --watch-combat
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
