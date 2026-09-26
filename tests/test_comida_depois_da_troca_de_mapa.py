"""A COMIDA NÃO SAI NOS 30 s DEPOIS DE UMA TROCA DE MAPA -- e toda troca é marcada.

A ata de 17/09/2026 (`docs/decisoes/comida-do-pet.md`) dizia que isto estava
"travado por teste" e não estava: nenhum arquivo de teste citava a guarda. E ela
dizia que `UIDoJogo.esperar_a_chegada` era "o único ponto por onde passam
entrada, saída e teleporte" -- falso para o BC até 25/09/2026, que tinha a
entrada num laço próprio e a saída num `tick(1.5)` cego. O pet é recriado a
cada troca de mapa; comida dada nesse intervalo é consumida e perdida.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
import time

import pytest

from blazesbot.bot.ui_do_jogo import UIDoJogo
from blazesbot.core import pet
from blazesbot.core.pet import PetFeeder


@pytest.fixture(autouse=True)
def _sem_medicao(monkeypatch):
    # A medição da volta do pet abre uma thread por troca de mapa; aqui só se
    # testa a guarda.
    monkeypatch.setattr(pet, "MEDIR_A_VOLTA_DO_PET", False)


class _Log:
    def __init__(self):
        self.linhas: list[str] = []

    def info(self, msg, *args):
        self.linhas.append(msg % args if args else msg)

    debug = warning = error = info


class _Ctx:
    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.log = _Log()
        self.memory = self
        self.account_login = "teste"

    def position(self):
        return (0, 0)

    def location(self):
        return "lugar"

    def raise_if_stopped(self):
        pass

    def tick(self, s):
        pass


def _vencida() -> PetFeeder:
    return PetFeeder(vence_em=time.time() - 1)


# ===========================================================================
# 1. A GUARDA
# ===========================================================================

def test_logo_depois_da_troca_de_mapa_RECUSA_e_a_grade_NAO_avanca():
    ctx = _Ctx(hwnd=9001)
    feeder = _vencida()
    vence = feeder.vence_em
    pet.trocou_de_mapa(ctx.hwnd)

    assert feeder.deve_alimentar(50, ctx=ctx) is False
    assert feeder.vence_em == vence, "a grade avançou com a comida recusada"


def test_passados_os_30_s_ALIMENTA():
    ctx = _Ctx(hwnd=9002)
    pet._ENTROU_NO_MAPA_EM[ctx.hwnd] = (
        time.monotonic() - pet.SEGUNDOS_NO_MAPA_ANTES_DE_ALIMENTAR - 1)
    assert _vencida().deve_alimentar(50, ctx=ctx) is True


def test_FORCE_fura_a_guarda():
    """`feed_on_start` é decisão explícita do usuário."""
    ctx = _Ctx(hwnd=9003)
    pet.trocou_de_mapa(ctx.hwnd)
    assert _vencida().deve_alimentar(50, force=True, ctx=ctx) is True


def test_janela_que_NUNCA_trocou_de_mapa_NAO_bloqueia():
    """"Não sei" não é "acabou de trocar"."""
    assert pet.segundos_no_mapa(987_654) is None
    assert _vencida().deve_alimentar(50, ctx=_Ctx(hwnd=987_654)) is True


# ===========================================================================
# 2. QUEM MARCA: a chegada CONFIRMADA, e só ela
# ===========================================================================

def _ui(hwnd: int) -> UIDoJogo:
    ui = object.__new__(UIDoJogo)
    ui.ctx = _Ctx(hwnd)
    return ui


def test_a_chegada_confirmada_MARCA_a_troca():
    ui = _ui(9101)
    assert ui.esperar_a_chegada(lambda: True, teto=0.1, passo=0.01, o_que="X")
    assert pet.segundos_no_mapa(9101) < 1.0


def test_o_teto_estourado_NAO_marca():
    ui = _ui(9102)
    assert not ui.esperar_a_chegada(lambda: False, teto=0.02, passo=0.01, o_que="X")
    assert pet.segundos_no_mapa(9102) is None


# ===========================================================================
# 3. O BC PASSA PELO PONTO COMUM -- entrada E saída
# ===========================================================================

def test_a_entrada_do_BC_marca_a_troca_de_mapa():
    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.bc.ui_service import UIService

    rotina = object.__new__(BossRushRoutine)
    rotina.ctx = _Ctx(hwnd=9201)
    rotina.local = type("Local", (), {
        "atualizar": lambda self, *a: None,
        "chegou_na_cave": lambda self, antes: True})()
    rotina.ui = object.__new__(UIService)
    rotina.ui.ctx = rotina.ctx

    assert rotina._reconhecer_entrada((0, 0)) is True
    assert pet.segundos_no_mapa(9201) < 1.0


def _chamadas(funcao) -> list[ast.Call]:
    arvore = ast.parse(textwrap.dedent(inspect.getsource(funcao)))
    return [n for n in ast.walk(arvore) if isinstance(n, ast.Call)]


def test_a_saida_do_BC_pergunta_pelo_ponto_comum_e_nao_dorme_cego():
    from blazesbot.bot.bc.ui_service import UIService

    chamadas = _chamadas(UIService.sair_da_cave)
    nomes = [getattr(c.func, "attr", "") for c in chamadas]
    assert "esperar_a_chegada" in nomes
    ticks = [c for c in chamadas if getattr(c.func, "attr", "") == "tick"]
    assert not ticks, "voltou a espera cega depois do clique na saída"


# ===========================================================================
# 4. A 2ª CHANCE: no ponto do boss, nos DOIS ecossistemas de cave
# ===========================================================================

def test_o_ponto_do_boss_alimenta_na_HH_e_no_BC():
    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    for rotina in (HHRoutine, BossRushRoutine):
        nomes = [getattr(c.func, "attr", "") for c in _chamadas(rotina._do_boss)]
        assert "feed_pet" in nomes, f"{rotina.__name__}._do_boss sem a 2ª chance"


def test_no_BC_a_comida_vem_DEPOIS_do_pacote_e_ANTES_de_montar():
    """Regra do usuário: a ação antes de ativar a montaria (a saída monta)."""
    from blazesbot.bot.bc.routine import BossRushRoutine

    fonte = inspect.getsource(BossRushRoutine._do_boss)
    pacote = fonte.index("self._usar_package_courage()")
    comida = fonte.index("self.combat.feed_pet()")
    saida = fonte.index("self._succeed(State.SAIR)")
    assert pacote < comida < saida
