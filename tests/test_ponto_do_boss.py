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
from blazesbot.bot.hh.ponto_do_boss import (
    VETOS_ANTES_DE_DESISTIR,
    PontoDoBoss,
    do_trecho,
    verificar_morte_do_boss,
)

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
# A DUPLA VALIDAÇÃO DA MORTE -- 13/09/2026
# ===========================================================================
#
# O `voltar_para_ele` saiu daqui na mesma data. Ele caminhava de volta ao ponto
# depois da luta, e o SUCESSO DESSA CAMINHADA virou o certificado de morte do
# boss -- que é o defeito medido abaixo. Ver `docs/decisoes/hh.md` §35.

# As 5 ocorrências do `Purple` no log de 11/09/2026: a batalha acabou aqui, a
# ~55 unidades do ponto (526,108), e o bot creditou o ÚLTIMO boss -- ou seja,
# saiu da cave -- sem ninguém ter morrido.
ROLLBACKS_MEDIDOS = [(470, 108), (469, 109), (471, 107), (471, 108)]


def test_a_memoria_confirmando_credita_DE_QUALQUER_LUGAR():
    """É a prova forte: responde "o boss morreu?", e não "estou no lugar
    certo?". 309 confirmações no mesmo log -- é o caminho normal."""
    for onde in [PONTO, (470, 108), None]:
        v = verificar_morte_do_boss(_alvo(), onde, memoria_confirmou=True)
        assert v.creditar is True


def test_no_ponto_e_sem_memoria_AINDA_credita():
    """A reserva, para quando a identidade não foi legível -- pacote de mobs
    sem nome, alvo por id. No ponto, sair de batalha só tem uma explicação."""
    v = verificar_morte_do_boss(_alvo(), PONTO, memoria_confirmou=False)
    assert v.creditar is True


def test_na_BORDA_da_tolerancia_credita():
    """`<=`, e não `<`: a tolerância existe porque o pathfinding para onde
    para."""
    borda = (PONTO[0] + TOL, PONTO[1])
    assert _alvo().distancia_de(borda) == TOL
    assert verificar_morte_do_boss(_alvo(), borda, False).creditar is True


def test_UMA_unidade_alem_da_tolerancia_NAO_credita():
    fora = (PONTO[0] + TOL + 1, PONTO[1])
    assert verificar_morte_do_boss(_alvo(), fora, False).creditar is False


def test_os_ROLLBACKS_MEDIDOS_deixam_de_creditar():
    """O teste de regressão propriamente dito: são as 9 falsas vitórias."""
    for onde in ROLLBACKS_MEDIDOS:
        v = verificar_morte_do_boss(_alvo(), onde, memoria_confirmou=False)
        assert v.creditar is False, f"{onde} voltou a creditar o boss"
        assert "ROLLBACK" in v.motivo


def test_o_motivo_TRAZ_OS_NUMEROS_da_decisao():
    """Um veredito sem os números não se audita no log depois."""
    v = verificar_morte_do_boss(_alvo(), (470, 108), False)

    assert "(470, 108)" in v.motivo            # onde a batalha acabou
    assert str(PONTO) in v.motivo              # onde deveria estar
    assert str(TOL) in v.motivo                # a régua aplicada


def test_SEM_leitura_de_posicao_NAO_credita():
    """O único lugar do ecossistema onde "não sei" VETA em vez de liberar.

    Esta resposta autoriza creditar um boss; errar para o lado seguro custa
    refazer um trecho, contra perder a cave inteira.
    """
    v = verificar_morte_do_boss(_alvo(), None, memoria_confirmou=False)
    assert v.creditar is False


def test_a_validacao_NAO_DEPENDE_de_qual_boss_e():
    """Regra global dos quatro trechos, e não código do último boss.

    Ela recebe um `PontoDoBoss` -- o mesmo objeto que `do_trecho` devolve para
    qualquer índice --, então vale para os quatro pelo caminho de código único
    de `_do_boss`.
    """
    import inspect

    fonte = inspect.getsource(verificar_morte_do_boss)
    for rotulo in ("Purple", "Fa-Yuan", "Dupla", "Green Robmaster"):
        assert f'"{rotulo}"' not in fonte, (
            f"a validação ficou hardcoded para o {rotulo}")

    for trecho in range(len(mapa_hh.TRECHOS_DOS_BOSSES)):
        alvo = do_trecho(trecho, TOL)
        longe = (alvo.ponto[0] + 100, alvo.ponto[1] + 100)
        assert verificar_morte_do_boss(alvo, longe, False).creditar is False
        assert verificar_morte_do_boss(alvo, alvo.ponto, False).creditar is True


def test_o_teto_de_vetos_existe_e_e_finito():
    """Insistir sem limite prenderia a run num trecho."""
    assert 1 <= VETOS_ANTES_DE_DESISTIR <= 5


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
