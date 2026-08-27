@echo off
setlocal
title BlazesBot - Placar da Calibracao

REM Le `data/calibracao.json` e imprime o que cada ponteiro candidato acertou.
REM Nao abre processo, nao le memoria, nao captura tela: so arquivo. Pode rodar
REM com o bot de pe.
REM
REM QUEM AINDA ALIMENTA ESTE PLACAR (25/08/2026):
REM   modal          -> vendor.py, a cada caixa de dialogo do vendedor
REM   janela_de_loot -> routine.py, a cada janela de loot
REM   flag_combate   -> ja GABARITOU: 64.427 amostras, 30 runs, e e ela que
REM                     encerra as fases de combate
REM
REM As provas do ALVO (alvo_hp, alvo_presente, alvo_morto_por_hp...) NAO sao mais
REM alimentadas: a vida do alvo passou a ser lida da TELA, e nenhum ponteiro
REM precisa acerta-la. As linhas antigas delas continuam no arquivo como
REM historico -- para zerar, com o bot PARADO:
REM
REM   .venv\Scripts\python.exe -m blazesbot.core.calibracao --reabrir alvo_hp

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto SEM_VENV

".venv\Scripts\python.exe" -m blazesbot.core.calibracao
goto FIM

:SEM_VENV
echo [ERRO] Rode primeiro o 1-INSTALAR.bat

:FIM
echo.
echo Tecle qualquer coisa para fechar.
pause >nul
