"""A contagem dos trechos de uma ida à cave da HH.

=========================================================================
POR QUE ESTE ARQUIVO EXISTE
=========================================================================

Eram três campos soltos em `HHRoutine` -- `_trecho`, `_trechos_feitos` e
`_run_em_andamento` --, lidos e escritos em seis lugares sem nenhum que
declarasse "a run começou" ou "acabou". A auditoria de 05/09/2026 achou dois
defeitos nascidos dessa dispersão, e o segundo derrubou o bot:

  * `_trecho == len(TRECHOS)` é o valor que "acabaram os trechos" deixa, e um
    dos leitores não sabia disso -- indexava a tupla fora do fim;
  * o progresso atravessa o desliga/liga do farm, porque a rotina é guardada em
    `supervisor._rotina_da_hh` de propósito (recriá-la a cada volta faria a run
    voltar ao primeiro boss).

Medido no log: 20:02:13 "Purple foi o último; os quatro feitos, saindo";
20:02:14 o usuário desliga; 20:02:35 religa -- e SITUAR estoura
`IndexError: tuple index out of range` ONZE vezes em dez segundos, cada uma
virando `exceção em SITUAR` -> RECUPERAR -> SITUAR.
"""
from __future__ import annotations

import pytest

from blazesbot.bot.hh.progresso import ProgressoDaCave

TOTAL = 4


def _novo() -> ProgressoDaCave:
    return ProgressoDaCave(TOTAL)


# ===========================================================================
# O portão que faltava
# ===========================================================================


@pytest.mark.parametrize("trecho,acabou", [
    (0, False),
    (3, False),
    (TOTAL, True),   # o valor que `marcar_feito_e_avancar` deixa no fim
    (99, True),      # disparatado
    (-1, True),      # negativo
])
def test_acabou_responde_por_TODOS_os_indices_invalidos(trecho, acabou):
    """Índice que não aponta para um trecho de verdade não é trecho a retomar.

    O desfecho seguro é a saída -- o único estado que funciona de qualquer
    ponto de dentro da cave.
    """
    p = _novo()
    p.pular_para(trecho)
    assert p.acabou() is acabou


def test_o_ciclo_completo_dos_quatro_trechos():
    p = _novo()
    p.entrei_na_cave()
    p.a_run_comecou()

    assert [p.marcar_feito_e_avancar() for _ in range(TOTAL)] == [1, 2, 3, None]
    assert p.acabou()
    assert p.feitos == TOTAL


# ===========================================================================
# Os três momentos do ciclo de vida
# ===========================================================================


def test_entrar_na_cave_zera_tudo():
    """Instância nova: o desfaz-refaz do time ressuscita os quatro bosses."""
    p = _novo()
    p.a_run_comecou()
    p.marcar_feito_e_avancar()

    p.entrei_na_cave()

    assert p.trecho == 0
    assert p.feitos == 0
    assert p.em_andamento is False


def test_sair_da_cave_zera_tudo():
    """O que foi feito lá dentro deixa de valer -- e é o que fecha o buraco.

    Sem isto, `trecho == total` sobrevive até a próxima leitura, que era
    exatamente o estado em que SITUAR estourava.
    """
    p = _novo()
    p.a_run_comecou()
    for _ in range(TOTAL):
        p.marcar_feito_e_avancar()
    assert p.acabou()

    p.sai_da_cave()

    assert not p.acabou()
    assert p.trecho == 0
    assert p.em_andamento is False


def test_a_run_comeca_DEPOIS_de_entrar_e_nao_junto():
    """A disputa da porta pode levar uma hora, e quem retoma no meio da cave
    (morreu e reviveu dentro) passa por `a_run_comecou` sem passar por
    `entrei_na_cave`."""
    p = _novo()
    p.entrei_na_cave()
    assert p.em_andamento is False
    p.a_run_comecou()
    assert p.em_andamento is True


# ===========================================================================
# Pular o que já foi feito
# ===========================================================================


def test_o_trecho_ja_feito_e_PULADO():
    """É o que faz a morte custar apenas o caminho de volta."""
    p = _novo()
    p.a_run_comecou()
    p.marcar_feito_e_avancar()          # fecha o 0, vai para o 1
    p.marcar_feito_e_avancar()          # fecha o 1, vai para o 2

    # morreu e a retomada devolveu ao 0, que já está feito
    p.pular_para(0)
    assert p.marcar_feito_e_avancar() == 2, "pulou para um trecho já feito"


def test_avancar_com_tudo_feito_NAO_marca_indice_invalido():
    """Chamar de novo depois do fim não pode sujar o conjunto de feitos.

    Sem esta guarda, `feitos` passaria a conter `4`, `99`... e o contador de
    quantos trechos a run fez viraria ficção.
    """
    p = _novo()
    p.a_run_comecou()
    for _ in range(TOTAL):
        p.marcar_feito_e_avancar()

    assert p.marcar_feito_e_avancar() is None
    assert p.feitos == TOTAL


# ===========================================================================
# O que este módulo NÃO é
# ===========================================================================


def test_o_progresso_NAO_e_persistente():
    """Regra do usuário, 03/09/2026: *"não precisa ser persistente, só
    verificar enquanto está com o bot aberto"*.

    Dois objetos não compartilham nada -- e é assim que duas contas rodando em
    paralelo não misturam progresso.
    """
    a, b = _novo(), _novo()
    a.a_run_comecou()
    a.marcar_feito_e_avancar()

    assert b.trecho == 0
    assert b.feitos == 0
    assert b.em_andamento is False
