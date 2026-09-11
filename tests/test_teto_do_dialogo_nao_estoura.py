"""O teto do diálogo NÃO PODE ESTOURAR o float -- ele matava o estado SAIR.

=========================================================================
O DEFEITO, MEDIDO EM 11/09/2026
=========================================================================

`_afrouxar_o_teto` estica o teto da espera do diálogo em degraus, um a cada
`FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR` falhas consecutivas:

    degraus = self._dialogos_seguidos_sem_abrir // FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR
    return min(TETO_DO_DESESPERO, limite * FATOR_DE_AFROUXAMENTO ** degraus)

O contador **só zera quando um diálogo ABRE**. Enquanto o defeito dura ele não
tem limite -- e na saída da HH ele chegou a **5.120**, o que põe `degraus` em
1.024 e faz `2.0 ** 1024` passar do maior float:

    OverflowError: (34, 'Result too large')

No log, do lado de fora:

    04:25:30  HH: erro no estado SAIR: (34, 'Result too large')
    04:25:31  HH: erro no estado SAIR: (34, 'Result too large')
    ...                                              962 vezes em uma hora

=========================================================================
POR QUE ELE ERA ABSORVENTE, E NÃO UM ERRO QUE PASSA
=========================================================================

Quem estoura **não chega a clicar**. Sem clique nenhum diálogo abre; sem
diálogo o contador não zera; com o contador parado acima de 5.120, a tentativa
seguinte estoura igual. O estado morria e renascia para morrer de novo -- e é
literalmente o *"ficar travado"* que o usuário relatou no mesmo dia.

O maior contador que o log chegou a registrar é **5.119**: em 5.120 a função
estoura antes da linha que o imprimiria.

=========================================================================
O CONSERTO, E POR QUE ELE NÃO MUDA COMPORTAMENTO NENHUM
=========================================================================

O resultado já passava por `min(TETO_DO_DESESPERO, ...)`. Passado o degrau em
que `limite * FATOR ** degraus` alcança o teto do desespero, contar mais alto
não altera uma única espera -- só dá ao `**` a chance de estourar. O cap é
DERIVADO desse ponto, a partir do pior caso real (o teto partindo do piso), de
modo que mexer em qualquer um dos três números o reajusta sozinho.

Ver `docs/decisoes/hh.md` §33.
"""
from __future__ import annotations

import math

import pytest

from blazesbot.bot import ui_do_jogo as ui

# O contador que estourava, medido no log de produção de 11/09/2026.
CONTADOR_QUE_ESTOUROU = 5120

# O maior valor que o log chegou a imprimir -- em 5.120 já não havia log.
MAIOR_CONTADOR_LOGADO = 5119


class _Gesto:
    """O mínimo para exercitar `_afrouxar_o_teto`: só o contador."""

    def __init__(self, seguidas: int) -> None:
        self._dialogos_seguidos_sem_abrir = seguidas

    afrouxar = ui.UIDoJogo._afrouxar_o_teto


# ===========================================================================
# 1. O estouro não acontece mais
# ===========================================================================


@pytest.mark.parametrize("seguidas", [
    MAIOR_CONTADOR_LOGADO,
    CONTADOR_QUE_ESTOUROU,
    CONTADOR_QUE_ESTOUROU * 2,
    10 ** 6,
])
def test_contador_absurdo_NAO_estoura(seguidas):
    """Era `OverflowError: (34, 'Result too large')`, 962 vezes numa hora."""
    piso = ui.LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO

    teto = _Gesto(seguidas).afrouxar(piso)

    assert math.isfinite(teto)
    assert teto == ui.TETO_DO_DESESPERO


def test_o_contador_exato_que_matava_o_estado():
    """5.120 // 5 = 1.024, e `2.0 ** 1024` passa do maior float."""
    assert (CONTADOR_QUE_ESTOUROU // ui.FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR
            == 1024)
    with pytest.raises(OverflowError) as erro:
        ui.LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO * (
            ui.FATOR_DE_AFROUXAMENTO ** 1024)
    assert erro.value.args == (34, "Result too large"), (
        "a mensagem do log de produção deixou de bater com o estouro que este "
        "teste reproduz")


# ===========================================================================
# 2. E o cap não mudou nenhuma espera
# ===========================================================================


def test_o_cap_so_vale_onde_o_teto_do_desespero_ja_vencia():
    """Abaixo do cap, todo valor é idêntico ao que a fórmula antiga dava."""
    piso = ui.LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO
    for degraus in range(ui.DEGRAUS_ATE_O_DESESPERO + 1):
        seguidas = degraus * ui.FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR
        antigo = min(ui.TETO_DO_DESESPERO,
                     piso * ui.FATOR_DE_AFROUXAMENTO ** degraus)
        assert _Gesto(seguidas).afrouxar(piso) == antigo


def test_no_cap_o_pior_caso_ja_alcancou_o_desespero():
    """É a propriedade que torna o cap inócuo -- e é ela que o define."""
    alcancado = (ui.LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO
                 * ui.FATOR_DE_AFROUXAMENTO ** ui.DEGRAUS_ATE_O_DESESPERO)
    assert alcancado >= ui.TETO_DO_DESESPERO

    um_degrau_antes = (ui.LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO
                       * ui.FATOR_DE_AFROUXAMENTO
                       ** (ui.DEGRAUS_ATE_O_DESESPERO - 1))
    assert um_degrau_antes < ui.TETO_DO_DESESPERO, (
        "o cap ficou maior que o necessário -- ele deve ser o PRIMEIRO degrau "
        "em que o desespero já vence")


def test_o_cap_e_DERIVADO_e_nao_escrito_a_mao():
    """Mexer em qualquer um dos três números tem que reajustá-lo sozinho."""
    assert ui.DEGRAUS_ATE_O_DESESPERO == math.ceil(math.log(
        ui.TETO_DO_DESESPERO / ui.LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO,
        ui.FATOR_DE_AFROUXAMENTO))


def test_sem_falhas_seguidas_o_teto_fica_INTOCADO():
    """O caminho feliz não paga nada pelo conserto."""
    for seguidas in range(ui.FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR):
        assert _Gesto(seguidas).afrouxar(0.42) == 0.42
