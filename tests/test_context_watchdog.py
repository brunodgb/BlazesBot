"""O watchdog agora é checado dentro de `BotContext.tick()`, não só em `_guard()`.

Antes deste teste, a checagem do watchdog só existia em `BossRushRoutine._guard()`,
que roda uma vez por iteração do laço principal. Durante laços longos de combate
(`atacar_ate_sair_de_combate`) e navegação (`follow_path`), que podem rodar dezenas
de segundos sem voltar ao `_guard()`, uma queda (processo morre, janela some,
"Connection interrupted") não era detectada. O bot continuava enviando teclas e
cliques para um cliente morto.

O fix adiciona `check_watchdog()` ao `tick()`: todo laço que já chamava
`ctx.tick()` agora também detecta quedas. O watchdog faz rate-limiting interno
(`VISUAL_CHECK_SECONDS` para a checagem visual; processo/janela são system calls
baratos), então a checagem por fatia não carrega custo.

Três casos:
  1. Sem watchdog configurado (contas não-BC) → não levanta nada.
  2. Watchdog saudável → não levanta nada.
  3. Watchdog detecta queda → levanta `Disconnected`.
"""
import pytest

from blazesbot.bot.context import BotContext, Disconnected
from blazesbot.bot.watchdog import DcReason


class _FakeWatchdog:
    """Dublê do watchdog: responde por `check`."""

    def __init__(self, reason: DcReason = DcReason.NONE):
        self._reason = reason
        self.checks = 0

    def check(self, state=None):
        self.checks += 1
        return self._reason


class _FakeEvent:
    """`threading.Event` falso que nunca está setado."""

    def is_set(self):
        return False


class _TickingWatchdog:
    """Contador de chamadas — saudável enquanto não for para eleger uma queda."""

    def __init__(self, reason: DcReason = DcReason.NONE):
        self._reason = reason
        self.checks = 0

    def check(self, state=None):
        self.checks += 1
        return self._reason


class _FakeWatchdog:
    """Dublê do watchdog: responde por `check`."""

    def __init__(self, reason: DcReason = DcReason.NONE):
        self._reason = reason
        self.checks = 0

    def check(self, state=None):
        self.checks += 1
        return self._reason


def _ctx_sem_init(watchdog=None):
    """Cria um BotContext sem `__init__` real — só os atributos que tick() toca."""
    ctx = object.__new__(BotContext)
    ctx._watchdog = watchdog
    ctx.stop_event = _FakeEvent()
    ctx.pause_event = _FakeEvent()
    return ctx


# ===========================================================================

def test_check_watchdog_sem_watchdog_nao_faz_nada():
    """Contas sem watchdog (ex: executor APP) nunca checam — não levanta."""
    ctx = _ctx_sem_init(watchdog=None)
    ctx.check_watchdog()  # não levanta
    assert ctx._watchdog is None


def test_check_watchdog_healthy_nao_levanta():
    """Watchdog saudável devolve NONE: não levanta nada."""
    ctx = _ctx_sem_init(watchdog=_FakeWatchdog(DcReason.NONE))
    ctx.check_watchdog()
    assert ctx._watchdog.checks == 1


def test_check_watchdog_detecta_queda_e_levanta_disconnected():
    """Watchdog detecta processo morto → `Disconnected` com o motivo."""
    ctx = _ctx_sem_init(watchdog=_FakeWatchdog(DcReason.PROCESS_GONE))
    with pytest.raises(Disconnected) as exc_info:
        ctx.check_watchdog()
    assert "processo" in str(exc_info.value)


# ===========================================================================

def test_check_watchdog_detecta_todos_os_motivos():
    """Qualquer motivo que não seja NONE dispara `Disconnected`."""
    for reason in [DcReason.WINDOW_GONE, DcReason.RECONNECT_DIALOG]:
        ctx = _ctx_sem_init(watchdog=_FakeWatchdog(reason))
        with pytest.raises(Disconnected):
            ctx.check_watchdog()


def test_tick_consulta_watchdog_e_levanta_disconnected_no_meio(monkeypatch):
    """`tick()` deve consultar o watchdog; uma queda durante o wait vira
    `Disconnected` antes do tempo acabar."""
    ctx = _ctx_sem_init(watchdog=_FakeWatchdog(DcReason.NONE))

    # tick() chama jitter() e time.sleep; mocka para não bloquear.
    import blazesbot.bot.context as ctxmod
    monkeypatch.setattr(ctxmod, "jitter", lambda x: x)
    monkeypatch.setattr(ctxmod.time, "sleep", lambda x: None)

    calls = {"i": 0}

    def _counting_check():
        calls["i"] += 1
        if calls["i"] <= 2:
            pass  # saudável
        else:
            raise Disconnected("processo do cliente encerrado")
    monkeypatch.setattr(ctx, "check_watchdog", _counting_check)

    # raise_if_stopped e wait_if_paused não interessam a este teste — o foco
    # é o watchdog.
    monkeypatch.setattr(ctx, "raise_if_stopped", lambda: None)
    monkeypatch.setattr(ctx, "wait_if_paused", lambda: None)

    with pytest.raises(Disconnected):
        ctx.tick(1.0)

    # tick() chama check_watchdog no início, a cada fatia e no fim — pelo
    # menos 2 checagens antes da queda ser detectada.
    assert calls["i"] >= 3
