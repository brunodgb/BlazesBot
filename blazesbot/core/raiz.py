"""ONDE MORAM OS ARQUIVOS DO BOT — e por que não dá para perguntar ao `__file__`.

=========================================================================
DUAS VIDAS, DOIS LUGARES
=========================================================================

Rodando do CÓDIGO-FONTE, `data/` e `dist/` ficam ao lado do pacote
`blazesbot/`, e `Path(__file__).parents[2]` acerta sempre.

EMPACOTADO (PyInstaller), não: o `__file__` de qualquer módulo aponta para
dentro de uma pasta temporária que o executável descompacta a cada partida
(`sys._MEIPASS`), e `data/` **não está lá** — ela não pode estar. O bot ESCREVE
nessa pasta: `config.json` com as contas, o placar de calibração, as estatísticas
do dia. Coisa escrita numa pasta temporária que some ao fechar é coisa perdida.

Então, empacotado, a referência passa a ser a pasta do próprio `.exe`, que é
onde o ZIP entregue ao usuário coloca `data/` e `dist/`.

=========================================================================
POR QUE ISSO É UMA FUNÇÃO, E NÃO UMA CONSTANTE
=========================================================================

Constante seria avaliada no import, e o `sys.frozen` já está posto nessa hora --
funcionaria. A função existe pelo outro motivo: **teste**. Uma constante
obrigaria a recarregar o módulo para simular o empacotado, e recarga de módulo
em suíte é justamente o tipo de efeito colateral que deixa um teste dependendo
do vizinho.
"""
from __future__ import annotations

import sys
from pathlib import Path


def raiz_do_bot() -> Path:
    """A pasta que tem `data/` e `dist/` ao lado. Ver o cabeçalho."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]
