"""UM ENDEREÇO MORA NUM LUGAR SÓ.

=========================================================================
O DEFEITO QUE ORIGINOU ESTE ARQUIVO — 10/09/2026
=========================================================================

`core/memory.py` tinha **duas** atribuições de módulo para `ADDR_TARGET_ID`:

    linha 166:  ADDR_TARGET_ID = 0x0115CB20          <- a 6139, MORTA na 6400
    linha 522:  ADDR_TARGET_ID = IMAGE_BASE + 0x00D5CB80

Era inofensivo **por acidente**: a de baixo vem depois e vence no import, então
a produção lia o endereço certo. Mas a armadilha tinha duas pontas:

1. quem lesse a seção de cima acreditaria no valor morto;
2. bastava alguém **reordenar o arquivo** — mover um bloco, extrair uma seção —
   para a produção passar a ler endereço morto **CALADO**.

O segundo é o modo de falha que este projeto mais combate: errar sem avisar.
E o defeito não apareceu numa revisão de código; apareceu porque uma medição
de outra coisa passou perto e os dois valores não fecharam.

=========================================================================
O QUE ESTE ARQUIVO TRAVA
=========================================================================

Nenhuma constante de módulo de `core/memory.py` pode ser atribuída duas vezes.
A regra é mais ampla que o caso que a originou de propósito: endereço, offset,
valor medido e interruptor têm de ter um lugar só, ao lado da medição que os
sustenta. Duas atribuições são duas chances de só uma ser corrigida.

Vale para o arquivo inteiro, não só para os `ADDR_*`: um `OFF_*` duplicado
esconde exatamente o mesmo defeito.
"""
from __future__ import annotations

import ast
import pathlib
from collections import Counter

MODULOS = [
    "blazesbot/core/memory.py",
    "blazesbot/core/target_hybrid.py",
    "blazesbot/core/patch_do_cliente.py",
]


def _atribuicoes_de_modulo(caminho: str) -> Counter[str]:
    """Conta quantas vezes cada nome é atribuído NO NÍVEL DO MÓDULO.

    Só o nível do módulo importa: dentro de função, reatribuir é normal. E só
    atribuição simples (`NOME = ...`), porque é essa que define constante.
    """
    raiz = pathlib.Path(__file__).resolve().parents[1]
    arvore = ast.parse((raiz / caminho).read_text(encoding="utf-8"))
    contagem: Counter[str] = Counter()
    for no in arvore.body:                    # body = só o nível do módulo
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name):
                    contagem[alvo.id] += 1
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            if no.value is not None:
                contagem[no.target.id] += 1
    return contagem


def test_nenhuma_constante_e_atribuida_duas_vezes():
    """O teste geral: a duplicata some, em qualquer nome."""
    problemas = []
    for caminho in MODULOS:
        for nome, vezes in _atribuicoes_de_modulo(caminho).items():
            if vezes > 1 and nome.isupper():
                problemas.append("%s: %s atribuído %d vezes"
                                 % (caminho, nome, vezes))
    assert not problemas, (
        "constante de módulo atribuída mais de uma vez — a última vence no "
        "import, então a primeira é uma mentira esperando alguém reordenar o "
        "arquivo:\n  " + "\n  ".join(problemas))


def test_ADDR_TARGET_ID_e_o_vivo_da_6400():
    """O caso concreto: o valor que sobrou tem de ser o da 6400, não o da 6139.

    `0x0115CB20` é o da 6139 e lê ZERO nos seis clientes; `0x0115CB80` é o vivo,
    e a diferença é exatamente o rebase `+0x60` do banco de estáticos.
    """
    from blazesbot.core import memory as mem

    assert mem.ADDR_TARGET_ID == 0x0115CB80
    assert mem.ADDR_TARGET_ID - 0x60 == 0x0115CB20


def test_o_valor_MORTO_nao_volta_como_atribuicao():
    """Ele pode aparecer em comentário — é registro histórico e vale. O que não
    pode é voltar a ser código."""
    raiz = pathlib.Path(__file__).resolve().parents[1]
    fonte = (raiz / "blazesbot/core/memory.py").read_text(encoding="utf-8")
    for linha in fonte.splitlines():
        nua = linha.strip()
        if nua.startswith("#"):
            continue
        assert "ADDR_TARGET_ID = 0x0115CB20" not in nua, (
            "o endereço da 6139 voltou como atribuição: %r" % linha)


def test_o_reexport_do_target_hybrid_segue_o_banco():
    """`target_hybrid.TARGET_ID_ADDR` é reexportação, não cópia — se alguém
    trocar por um literal, ele para de acompanhar o banco de endereços."""
    from blazesbot.core import memory as mem
    from blazesbot.core import target_hybrid as th

    assert th.TARGET_ID_ADDR == mem.ADDR_TARGET_ID
    raiz = pathlib.Path(__file__).resolve().parents[1]
    fonte = (raiz / "blazesbot/core/target_hybrid.py").read_text(
        encoding="utf-8")
    assert "TARGET_ID_ADDR = ADDR_TARGET_ID" in fonte, (
        "o reexport virou cópia: ele tem de apontar para o banco, não repetir "
        "o número")
