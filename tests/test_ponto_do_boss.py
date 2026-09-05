"""O contrato de POSIÇÃO de um ponto de luta da HH.

=========================================================================
O DEFEITO QUE ELE FECHA — MEDIDO EM 05/09/2026
=========================================================================

A rotina aceitava "saí de batalha" como "limpei este ponto", e as duas coisas
não são a mesma. O log do primeiro boss:

    DESTRAVADO (o pacote do Fa-Yuan) em 39s: 6 morte(s), 6 TAB, 91 golpes
    ALVO MORREU: Elite Blackshirt Bandit                     (x6)
    HH: andei atrás dos mobs do Fa-Yuan (de (275,138) para (317,149))
    Não consegui parar em (275,138) ... (estou em (317,149))
    a run continua no trecho do Dupla (1 de 4 já feitos)

O personagem limpou um pacote **46 unidades fora** do ponto (271,137) e a run
creditou o boss. O Fa-Yuan nunca engajou.
"""
from __future__ import annotations

import pytest

from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.ponto_do_boss import PontoDoBoss, do_trecho

PONTO = (271, 137)
TOL = 15


def _alvo() -> PontoDoBoss:
    return PontoDoBoss("Fa-Yuan", PONTO, TOL)


class _Log:
    def __init__(self): self.linhas = []
    def info(self, *a, **k): self.linhas.append(a)


# ===========================================================================
# Estar no ponto
# ===========================================================================


@pytest.mark.parametrize("pos,esperado", [
    (PONTO, True),
    ((275, 138), True),      # a âncora errada do log: 4 unidades, dentro
    ((317, 149), False),     # onde o personagem realmente estava: 46 unidades
    (None, False),
])
def test_estou_nele(pos, esperado):
    assert _alvo().estou_nele(pos) is esperado


def test_sem_leitura_responde_NAO():
    """É o oposto do resto do bot, e de propósito.

    Esta resposta autoriza CREDITAR um boss. Creditar sem saber onde o
    personagem está é o defeito que o módulo existe para fechar; errar para o
    lado seguro custa refazer um trecho.
    """
    assert _alvo().estou_nele(None) is False
    assert _alvo().distancia_de(None) is None


# ===========================================================================
# Voltar para ele
# ===========================================================================


def test_ja_estar_nele_e_sucesso_SEM_clique():
    """Um clique de minimapa é barato, mas não é de graça em toda run."""
    cliques = []
    ok = _alvo().voltar_para_ele(
        PONTO, lambda **kw: cliques.append(kw) or True, _Log(), 1.8)
    assert ok is True
    assert cliques == []


def test_longe_do_ponto_CLICA_e_devolve_o_resultado():
    chamadas = []

    def encostar(**kw):
        chamadas.append(kw)
        return False        # o jogo recusou -- é o caso do log

    ok = _alvo().voltar_para_ele((317, 149), encostar, _Log(), 1.8)
    assert ok is False, "a falha do retorno não pode virar sucesso"
    assert chamadas[0]["alvo"] == PONTO
    assert chamadas[0]["precisao"] == TOL


def test_o_alvo_do_retorno_e_o_PONTO_DO_MAPA():
    """Nunca uma leitura de posição: leitura é onde o personagem ESTÁ, e o
    contrato é sobre onde ele DEVERIA estar."""
    chamadas = []
    _alvo().voltar_para_ele((317, 149),
                            lambda **kw: chamadas.append(kw) or True, _Log(), 1.8)
    assert chamadas[0]["alvo"] == PONTO


# ===========================================================================
# O ponto vem do mapa, inteiro
# ===========================================================================


def test_do_trecho_le_rotulo_e_ponto_da_MESMA_linha():
    """Separá-los é como o ponto do boss e o fim do caminho divergiram em
    04/09/2026 -- um waypoint comentado e o ponto apontando para ele."""
    for i, (rotulo, caminho, ponto) in enumerate(mapa_hh.TRECHOS_DOS_BOSSES):
        alvo = do_trecho(i, TOL)
        assert alvo.rotulo == rotulo
        assert alvo.ponto == ponto == caminho[-1].pos
