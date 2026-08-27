"""Testes de lógica pura do histórico diário de runs (`stats_diarias.py`).

A esse arquivo aponta o global `ARQUIVO`; cada teste o redireciona para um
arquivo em `tmp_path` e zera o cache `_dados`, para não tocar `data/` real.
"""
from datetime import date

import pytest

from blazesbot.core import stats_diarias


@pytest.fixture
def arquivo_tmp(tmp_path, monkeypatch):
    alvo = tmp_path / "stats.json"
    monkeypatch.setattr(stats_diarias, "ARQUIVO", alvo)
    stats_diarias._dados = None
    yield alvo
    stats_diarias._dados = None


def test_dia_vazio():
    assert stats_diarias._dia_vazio() == {
        "runs": 0, "success": 0, "fail": 0,
        "total_run_seconds": 0.0, "total_boss_seconds": 0.0,
        "last_boss_seconds": 0.0,
    }


def test_parse_dia_valido():
    assert stats_diarias._parse_dia("2026-08-07") == date(2026, 8, 7)


def test_parse_dia_invalido():
    assert stats_diarias._parse_dia("lixo") is None


def test_registrar_run_soma(arquivo_tmp):
    stats_diarias.registrar_run("alice", True, 120.0, 60.0)
    stats_diarias.registrar_run("alice", False, 80.0, 40.0)
    dia = stats_diarias._carregar()["alice"][date.today().isoformat()]
    assert dia["runs"] == 2
    assert dia["success"] == 1
    assert dia["fail"] == 1
    assert dia["total_run_seconds"] == 200.0
    assert dia["total_boss_seconds"] == 100.0
    # só a última importa: substitui, não acumula
    assert dia["last_boss_seconds"] == 40.0


def test_duracao_negativa_clampada(arquivo_tmp):
    stats_diarias.registrar_run("bob", True, -5.0, -3.0)
    dia = stats_diarias._carregar()["bob"][date.today().isoformat()]
    assert dia["total_run_seconds"] == 0.0
    assert dia["total_boss_seconds"] == 0.0


def test_login_vazio_ignorado(arquivo_tmp):
    stats_diarias.registrar_run("", True, 10.0)
    assert stats_diarias._carregar() == {}


def test_ultimos_dias_mais_recente_primeiro(arquivo_tmp):
    stats_diarias.registrar_run("carol", True, 50.0)
    dias = stats_diarias.ultimos_dias("carol", n=3)
    assert len(dias) == 3
    assert dias[0][0] == date.today().isoformat()
    assert dias[0][1]["runs"] == 1
    # dias sem registro viram zero, para não dar buraco na semana
    assert dias[1][1]["runs"] == 0
    assert dias[2][1]["runs"] == 0


def test_ultimos_dias_login_desconhecido(arquivo_tmp):
    dias = stats_diarias.ultimos_dias("ninguem", n=2)
    assert len(dias) == 2
    assert all(d["runs"] == 0 for _, d in dias)


def test_conhece(arquivo_tmp):
    assert stats_diarias.conhece("dave") is False
    stats_diarias.registrar_run("dave", True, 10.0)
    assert stats_diarias.conhece("dave") is True
    assert stats_diarias.conhece("outro") is False


def test_grava_e_rele_do_disco(arquivo_tmp):
    stats_diarias.registrar_run("eve", True, 10.0)
    assert arquivo_tmp.exists()
    # zera o cache: a releitura tem que vir do disco
    stats_diarias._dados = None
    dados = stats_diarias._carregar()
    assert dados["eve"][date.today().isoformat()]["runs"] == 1