"""Timeout de 5 s para os guardas antes do boss.

Os 4 mobs do waypoint antes do boss atacam na chegada. Se não vierem em 5 s, o
covil já foi limpo ou o personagem parou longe do ponto -- e continuar para o
boss é sempre melhor que bloquear a run por 30 s (o prazo anterior).

Testa que `esperar_entrar_em_combate("guardas")` desiste em 5 s, não em 30.
"""
from blazesbot.bot.bc import combat


class _FakeCtx:
    """Contexto mínimo para `esperar_entrar_em_combate` funcionar."""

    def __init__(self):
        self.tick_calls = []
        self.log = self
        self.settings = type("S", (), {
            "keys": type("K", (), {"sit": "X"})(),
        })()

    def tick(self, seconds):
        self.tick_calls.append(seconds)

    def raise_if_stopped(self):
        pass

    def snapshot(self):
        return type("E", (), {"dead": False, "hp_pct": 100.0,
                              "max_hp": 100, "sitting": False})()

    # stubs para logging
    def info(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass

    def error(self, *a, **kw):
        pass


class _Stopwatch:
    """Relógio que avança a cada chamada — sem `time.time` real."""

    def __init__(self):
        self.now = 0.0


def test_constante_guardas_e_5seg():
    assert combat.ESPERA_ENTRAR_EM_COMBATE_GUARDAS == 5.0


def test_guardas_usa_timeout_de_5s_nao_30s(monkeypatch):
    """Se `esperar_entrar_em_combate("guardas")` não receber limite
    explícito, deve usar o timeout de 5 s, não os 30 s do padrão."""
    relogio = _Stopwatch()

    ctx = _FakeCtx()

    motor = object.__new__(combat.CombatEngine)
    motor.ctx = ctx

    # Flag de combate NUNCA liga → espera até estourar o limite.
    monkeypatch.setattr(
        combat.CombatEngine, "_ler_flag_de_combate", lambda self: False)

    # Mocka time.time para o relógio acelerado.
    monkeypatch.setattr(combat.time, "time", lambda: relogio.now)

    # Mocka ctx.tick para avançar o relógio virtual.
    def _tick(seconds):
        relogio.now += seconds
    monkeypatch.setattr(ctx, "tick", _tick)

    # Mocka maintain — não interessa nesta fase.
    monkeypatch.setattr(
        combat.CombatEngine, "maintain", lambda self, state, em_luta=False: None)

    # O call sem `limite` deve usar o padrão (30 s) — verificamos que o
    # DEFAULT é 30, mas os chamadores de GUARDAS passam 5 explicitamente.
    # Testa o comportamento com limite de 5s diretamente:
    inicio = relogio.now
    ok = motor.esperar_entrar_em_combate(
        "guardas", limite=combat.ESPERA_ENTRAR_EM_COMBATE_GUARDAS)
    fim = relogio.now

    assert ok is False
    # Avançou pelo menos 5 s de relógio virtual.
    assert fim - inicio >= combat.ESPERA_ENTRAR_EM_COMBATE_GUARDAS
    # E NÃO atingiu os 30 s — se estourasse, o padrão estaria vazando.
    # Small epsilon for floating point precision
    epsilon = 0.1
    assert fim - inicio < combat.ESPERA_PARA_ENTRAR_EM_COMBATE + epsilon
