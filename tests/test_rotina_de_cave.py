"""O LAÇO COMUM DAS CAVES -- `bot/rotina_de_cave.py`.

As duas rotinas (BC e HH) herdam o MESMO laço desde 26/09/2026. Aqui se trava:

  * o CONTRATO: toda cave declara o que o laço pergunta, e todo estado tem o seu
    `_do_<estado>` -- o despacho é por essa convenção, e um estado sem handler
    derruba a rotina na PRIMEIRA vez que ela cai nele;
  * que NENHUMA cave volta a ter laço próprio -- era assim que as duas
    divergiam;
  * o destino da FASE do log: fica numa queda (o Histórico de Quedas a lê depois
    que a exceção sai do laço) e sai numa saída limpa.
"""
from __future__ import annotations

import logging
from enum import Enum, auto
from types import SimpleNamespace

import pytest

from blazesbot.bot import rotina_de_cave
from blazesbot.bot.bc.routine import BossRushRoutine
from blazesbot.bot.bc.routine import State as EstadoDoBC
from blazesbot.bot.context import Disconnected, FarmDesligado
from blazesbot.bot.hh.routine import HHRoutine
from blazesbot.bot.hh.routine import State as EstadoDaHH
from blazesbot.bot.rotina_de_cave import RotinaDeCave
from blazesbot.core import logmodo

CAVES = [(BossRushRoutine, EstadoDoBC, "BC"), (HHRoutine, EstadoDaHH, "HH")]


@pytest.mark.parametrize(("rotina", "estados", "nome"), CAVES,
                         ids=lambda v: getattr(v, "__name__", str(v)))
def test_todo_estado_tem_o_seu_handler(rotina, estados, nome):
    faltando = [e.name for e in estados
                if not callable(getattr(rotina, f"_do_{e.name.lower()}", None))]
    assert not faltando, f"{nome}: estado sem `_do_<estado>`: {faltando}"


@pytest.mark.parametrize(("rotina", "estados", "nome"), CAVES,
                         ids=lambda v: getattr(v, "__name__", str(v)))
def test_cada_cave_declara_o_que_o_laco_pergunta(rotina, estados, nome):
    assert rotina.NOME == nome  # a telemetria continua `bc.estado.<ESTADO>`
    assert rotina.CAVE and rotina.LARGADA
    assert 0 < rotina.PASSO_DENTRO < rotina.PASSO_FORA
    # Começa SITUANDO, nunca preparando: quem já está no meio da cave continua.
    assert rotina.ESTADO_INICIAL is estados.SITUAR
    assert rotina.ESTADO_DE_RECUPERAR is estados.RECUPERAR
    assert rotina.ESTADOS_DENTRO_DA_CAVE
    assert rotina.ESTADOS_DENTRO_DA_CAVE <= set(estados)


def test_nenhuma_cave_tem_laco_proprio():
    assert BossRushRoutine.run is RotinaDeCave.run
    assert HHRoutine.run is RotinaDeCave.run


# ===========================================================================
# O laço, rodado de verdade sobre uma cave de mentira
# ===========================================================================

class _Estado(Enum):
    UM = auto()
    DOIS = auto()


class _Cave(RotinaDeCave):
    """UM faz o que o teste mandar; DOIS fecha uma run."""

    NOME = "XX"
    CAVE = "xx"
    LARGADA = "largada de teste"
    PASSO_DENTRO = 0.0
    PASSO_FORA = 0.0
    ESTADO_INICIAL = _Estado.UM
    ESTADO_DE_RECUPERAR = _Estado.DOIS
    ESTADOS_DENTRO_DA_CAVE = frozenset({_Estado.DOIS})

    def __init__(self, acao_do_um):
        self.ctx = SimpleNamespace(
            log=logging.getLogger("teste.rotina_de_cave"),
            farming=False, cave_em_farm="", runs_completed=0,
            account_login="conta",
            memory=SimpleNamespace(position=lambda: (0, 0),
                                   location=lambda: "lugar"),
            tick=lambda _segundos: None)
        self.esconder = SimpleNamespace(prender=lambda _motivo: None)
        self.combat = SimpleNamespace(cuidar_da_comida_no_laco=lambda **_: None)
        self.falhas: list[str] = []
        self._acao_do_um = acao_do_um

    def _guard(self):
        pass

    def _falhar(self, mensagem):
        self.falhas.append(mensagem)
        self.state = _Estado.DOIS

    def _do_um(self):
        self._acao_do_um()
        self.state = _Estado.DOIS

    def _do_dois(self):
        self.ctx.runs_completed += 1
        self.state = _Estado.UM


@pytest.fixture(autouse=True)
def _contexto_do_log_limpo(monkeypatch):
    # O diário grava em disco; aqui só interessa que o laço o chame.
    monkeypatch.setattr(rotina_de_cave.diario, "registrar_evento",
                        lambda *a, **k: None)
    logmodo.limpar()
    yield
    logmodo.limpar()


def _cair():
    raise Disconnected("conexao")


def _desligar():
    raise FarmDesligado()


def _quebrar():
    raise ValueError("defeito")


def test_numa_QUEDA_a_fase_fica_para_o_historico():
    """O BC limpava no `finally`, e toda queda dele ia sem fase para o
    Histórico -- o supervisor só a lê depois que a exceção sai do laço."""
    cave = _Cave(_cair)

    with pytest.raises(Disconnected):
        cave.run()

    assert logmodo.contexto_atual().get("fase") == "um"
    assert cave.ctx.farming is False
    assert cave.ctx.cave_em_farm == ""


def test_na_saida_LIMPA_a_fase_sai_do_log():
    cave = _Cave(lambda: None)

    cave.run(max_runs=1)

    assert cave.ctx.runs_completed == 1
    assert "fase" not in logmodo.contexto_atual()
    assert cave.ctx.farming is False


def test_desligar_no_meio_do_estado_devolve_o_controle_limpo():
    cave = _Cave(_desligar)

    cave.run()  # não sobe: desligar a cave não é defeito

    assert "fase" not in logmodo.contexto_atual()
    assert cave.ctx.farming is False


def test_o_should_continue_devolve_o_controle_antes_de_agir():
    cave = _Cave(_cair)  # se UM rodasse, subiria

    cave.run(should_continue=lambda: False)

    assert cave.ctx.runs_completed == 0


def test_erro_no_estado_vira_falha_e_o_laco_segue():
    cave = _Cave(_quebrar)

    cave.run(max_runs=1)

    assert cave.falhas == ["exceção em UM"]
    assert cave.ctx.runs_completed == 1
