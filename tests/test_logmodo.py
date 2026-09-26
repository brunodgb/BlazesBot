"""Testes de lógica pura do ambiente de log (`logmodo.py`).

A resolução dev/prod tem cache único no processo (`_MODO`); cada teste zera o
cache via a fixture autouse para medir a resolução a partir do env.
"""
import os

import pytest

from blazesbot.core import logmodo


@pytest.fixture(autouse=True)
def _reseta_modo(monkeypatch):
    monkeypatch.delenv("BLAZES_MODO", raising=False)
    logmodo._MODO = None
    yield
    logmodo._MODO = None


def test_default_dev():
    assert logmodo.modo_atual() == "dev"
    assert logmodo.eh_dev() is True


def test_prod():
    os.environ["BLAZES_MODO"] = "prod"
    assert logmodo.modo_atual() == "prod"
    assert logmodo.eh_dev() is False


def test_case_insensitive():
    os.environ["BLAZES_MODO"] = "PROD"
    assert logmodo.modo_atual() == "prod"


def test_invalido_cai_em_dev():
    os.environ["BLAZES_MODO"] = "banana"
    assert logmodo.modo_atual() == "dev"


def test_espacos_strip():
    os.environ["BLAZES_MODO"] = " prod "
    assert logmodo.modo_atual() == "prod"


def test_cache_unico_segura_primeiro_valor(monkeypatch):
    os.environ["BLAZES_MODO"] = "prod"
    assert logmodo.modo_atual() == "prod"
    # muda o env depois da primeira resolução: o cache segura o valor inicial
    monkeypatch.setenv("BLAZES_MODO", "dev")
    assert logmodo.modo_atual() == "prod"


def test_contexto_por_thread():
    logmodo.limpar()
    assert logmodo.contexto_atual() == {}
    logmodo.contexto(conta="alice", id_run="abc123")
    logmodo.fase("NAVEGANDO")
    ctx = logmodo.contexto_atual()
    assert ctx["conta"] == "alice"
    assert ctx["id_run"] == "abc123"
    assert ctx["fase"] == "NAVEGANDO"
    logmodo.limpar()
    assert logmodo.contexto_atual() == {}


def test_nova_run_da_um_id_novo_a_cada_run():
    logmodo.limpar()
    primeiro = logmodo.nova_run("alice")
    segundo = logmodo.nova_run("alice")

    assert primeiro != segundo
    assert len(segundo) == 10 and int(segundo, 16) >= 0
    assert logmodo.contexto_atual() == {"conta": "alice", "id_run": segundo}
    logmodo.limpar()


def test_as_DUAS_caves_abrem_a_run_pelo_mesmo_gerador():
    """A HH saía com `id_run` nulo em todo registro: só o BC abria a run."""
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    for metodo in (BossRushRoutine._do_entrar, HHRoutine._entrou):
        arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
        chamadas = {getattr(n.func, "attr", "") for n in ast.walk(arvore)
                    if isinstance(n, ast.Call)}
        assert "nova_run" in chamadas, metodo.__qualname__