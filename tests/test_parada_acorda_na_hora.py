"""A parada tem que ACORDAR quem espera, não ser descoberta por polling.

=============================================================================
O DEFEITO QUE ESTES TESTES TRAVAM
=============================================================================

`_AnyEvent` compõe dois eventos -- o stop GLOBAL (compartilhado por todas as
contas) e o `own_stop` (só desta conta). Mas o `wait` era:

    return self._eventos[-1].wait(timeout)

...só o evento PRÓPRIO. Acionar o global -- que é exatamente o que o botão
Parar faz, em `BotManager.stop()` -- não acordava ninguém. Quem estivesse
dormindo aqui dormia o timeout inteiro.

O estrago não ficava em `supervisor.py`. Como este `wait` não era confiável,
`BotContext.tick()` cumpria TODA espera em fatias de 0,025 s de `time.sleep`,
conferindo a flag entre elas: 40 acordadas por segundo, por conta, o tempo
todo, para quase sempre não encontrar nada. O polling era a compensação de um
`wait` que não acordava.

A correção tem duas metades, e as duas precisam de dente próprio:

  1. FAN-OUT no escritor: `BotManager.stop()` aciona o `own_stop` de cada
     supervisor além do global. Travado por `test_stop_faz_fan_out_*`.
  2. REDE no leitor: `_AnyEvent.wait` fatia por `TETO_DA_FATIA_DE_ESPERA`, para
     que um global acionado SEM fan-out (as ferramentas temporárias passam um
     evento próprio como global) degrade para "notado em 0,25 s" e não para
     "nunca notado". Travado por `test_wait_acorda_pelo_global_sem_fan_out`.

MARGEM DOS PRAZOS: cada teste espera um desfecho instantâneo (ou em 0,25 s)
contra um defeito que levaria 5-10 s. A folga é de uma ordem de grandeza, então
lentidão de máquina não reprova o teste -- só o defeito reprova.
"""
import threading
import time

import pytest

from blazesbot.bot.supervisor import (
    TETO_DA_FATIA_DE_ESPERA,
    AccountSupervisor,
    BotManager,
    _AnyEvent,
)

# ---------------------------------------------------------------------------
# Dublês
# ---------------------------------------------------------------------------

class _LogMudo:
    def info(self, *a, **k) -> None: ...
    def debug(self, *a, **k) -> None: ...
    def warning(self, *a, **k) -> None: ...
    def error(self, *a, **k) -> None: ...


class _SupervisorFalso:
    """Só o que `BotManager.stop` toca: o evento próprio."""

    def __init__(self) -> None:
        self.own_stop = threading.Event()


class _SupervisorQuebrado:
    """Um supervisor em estado estranho não pode impedir a parada dos outros."""

    @property
    def own_stop(self):
        raise RuntimeError("supervisor em estado inválido")


class _GerenteFalso:
    """`BotManager` sem `__init__`: só os campos que `stop()` usa.

    Construir o gerente de verdade puxaria configuração, interfaces e threads --
    e o que está sob teste é o CONTRATO do `stop`, não a construção dele.
    """

    def __init__(self, supervisores) -> None:
        self.stop_event = threading.Event()
        self.supervisors = supervisores
        self._ativo = True
        self.soltou_o_mouse = False

    def _soltar_o_mouse_do_usuario(self) -> None:
        self.soltou_o_mouse = True


def _parar(gerente) -> None:
    """Chama o `stop` DE VERDADE sobre o dublê, sem instanciar o gerente."""
    BotManager.stop(gerente)


def _quanto_demora(funcao) -> float:
    inicio = time.monotonic()
    funcao()
    return time.monotonic() - inicio


# ---------------------------------------------------------------------------
# 1. O fan-out do escritor
# ---------------------------------------------------------------------------

def test_stop_aciona_o_evento_global():
    gerente = _GerenteFalso([])
    _parar(gerente)
    assert gerente.stop_event.is_set()


def test_stop_faz_fan_out_para_todo_supervisor():
    """Sem isto, quem espera no evento próprio não é acordado pelo Parar."""
    supervisores = [_SupervisorFalso() for _ in range(5)]
    gerente = _GerenteFalso(supervisores)

    _parar(gerente)

    assert all(s.own_stop.is_set() for s in supervisores), (
        "BotManager.stop() precisa acionar o own_stop de CADA supervisor; sem "
        "o fan-out, _AnyEvent.wait dorme o timeout inteiro"
    )


def test_stop_sobrevive_a_um_supervisor_quebrado():
    bons = [_SupervisorFalso(), _SupervisorFalso()]
    gerente = _GerenteFalso([bons[0], _SupervisorQuebrado(), bons[1]])

    _parar(gerente)

    assert gerente.stop_event.is_set()
    assert all(s.own_stop.is_set() for s in bons)
    assert gerente.soltou_o_mouse


def test_stop_desativa_e_solta_o_mouse():
    gerente = _GerenteFalso([_SupervisorFalso()])
    _parar(gerente)
    assert gerente._ativo is False
    assert gerente.soltou_o_mouse


# ---------------------------------------------------------------------------
# 2. O `wait` que acorda
# ---------------------------------------------------------------------------

def test_wait_devolve_na_hora_com_o_proprio_acionado():
    global_stop, own_stop = threading.Event(), threading.Event()
    evento = _AnyEvent(global_stop, own_stop)
    own_stop.set()

    gasto = _quanto_demora(lambda: evento.wait(10.0))

    assert gasto < 0.1, f"devolveu em {gasto:.3f}s, devia ser imediato"


def test_wait_devolve_na_hora_com_o_global_ja_acionado():
    """O caminho curto: já acionado antes de dormir, nem chega a esperar."""
    global_stop, own_stop = threading.Event(), threading.Event()
    evento = _AnyEvent(global_stop, own_stop)
    global_stop.set()

    gasto = _quanto_demora(lambda: evento.wait(10.0))

    assert gasto < 0.1, f"devolveu em {gasto:.3f}s, devia ser imediato"


def test_wait_acorda_quando_o_proprio_e_acionado_durante_a_espera():
    """O caminho normal, com o fan-out: acorda NO INSTANTE do set()."""
    global_stop, own_stop = threading.Event(), threading.Event()
    evento = _AnyEvent(global_stop, own_stop)

    threading.Timer(0.05, own_stop.set).start()
    gasto = _quanto_demora(lambda: evento.wait(10.0))

    assert gasto < 0.5, (
        f"devolveu em {gasto:.3f}s; com o evento próprio acionado o wait tem "
        "que devolver no instante, não no fim do timeout"
    )


def test_wait_acorda_pelo_global_sem_fan_out():
    """A REDE: global acionado por quem não faz fan-out.

    É o caso das ferramentas temporárias, que passam um evento próprio como
    `stop_event` do supervisor. A implementação antiga dormiria os 5 s inteiros.
    """
    global_stop, own_stop = threading.Event(), threading.Event()
    evento = _AnyEvent(global_stop, own_stop)

    threading.Timer(0.05, global_stop.set).start()
    gasto = _quanto_demora(lambda: evento.wait(5.0))

    assert gasto < 1.0, (
        f"devolveu em {gasto:.3f}s; a fatia de rede é "
        f"{TETO_DA_FATIA_DE_ESPERA}s, então o global sem fan-out tem que ser "
        "notado nessa ordem de grandeza -- não no fim do timeout"
    )
    assert evento.is_set()


def test_wait_respeita_o_timeout_quando_nada_acontece():
    evento = _AnyEvent(threading.Event(), threading.Event())

    inicio = time.monotonic()
    resultado = evento.wait(0.3)
    gasto = time.monotonic() - inicio

    assert resultado is False, "nada foi acionado; wait tem que devolver False"
    assert gasto >= 0.3, f"devolveu cedo demais ({gasto:.3f}s)"
    assert gasto < 2.0, f"a fatia de rede virou espera longa ({gasto:.3f}s)"


def test_request_stop_nao_derruba_as_outras_contas():
    """Parar UMA conta continua sem tocar no global -- o fan-out é só do Parar geral."""
    global_stop = threading.Event()
    supervisor = AccountSupervisor.__new__(AccountSupervisor)
    supervisor.global_stop = global_stop
    supervisor.own_stop = threading.Event()
    supervisor.stop_event = _AnyEvent(global_stop, supervisor.own_stop)
    supervisor.on_status = None
    supervisor.log = _LogMudo()

    AccountSupervisor.request_stop(supervisor, "teste")

    assert supervisor.own_stop.is_set()
    assert not global_stop.is_set(), (
        "request_stop acionou o stop GLOBAL: parar uma conta derrubaria as outras"
    )


# ---------------------------------------------------------------------------
# 3. O `tick` não pode quebrar com dublê que só tem `is_set`
# ---------------------------------------------------------------------------

class _EventoSoIsSet:
    """O dublê que os testes de watchdog já injetam: sem `wait`."""

    def is_set(self) -> bool:
        return False


def test_esperar_fatia_usa_wait_quando_existe():
    from blazesbot.bot.context import BotContext

    ctx = BotContext.__new__(BotContext)
    ctx.stop_event = threading.Event()

    threading.Timer(0.05, ctx.stop_event.set).start()
    gasto = _quanto_demora(lambda: BotContext._esperar_fatia(ctx, 5.0))

    assert gasto < 1.0, (
        f"esperou {gasto:.3f}s; com wait disponível a fatia tem que ser "
        "interrompida pelo set()"
    )


def test_esperar_fatia_cai_para_sleep_com_duble_sem_wait():
    """Sem esta queda, os dublês dos testes existentes levantariam AttributeError."""
    from blazesbot.bot.context import BotContext

    ctx = BotContext.__new__(BotContext)
    ctx.stop_event = _EventoSoIsSet()

    inicio = time.monotonic()
    BotContext._esperar_fatia(ctx, 0.05)
    gasto = time.monotonic() - inicio

    assert gasto >= 0.05, f"não dormiu a fatia ({gasto:.3f}s)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
