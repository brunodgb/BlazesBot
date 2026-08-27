"""Histórico diário de runs, por conta, retendo os últimos 7 dias.

Complementa o `RunStats` em memória (`blazesbot/bot/context.py`), que zera ao
fechar o bot. Aqui cada run completa é gravada num arquivo `data/stats_diarias.json`,
agregada por dia (`YYYY-MM-DD`) e por conta (`login`), para a interface mostrar
"quantas vezes rodou hoje, ontem…" e o tempo médio por run — mesmo entre sessões.

Formato do arquivo:
{
    "<login>": {
        "2026-08-07": {
            "runs": 3, "success": 2, "fail": 1,
            "total_run_seconds": 450.0, "total_boss_seconds": 300.0,
            "last_boss_seconds": 120.0
        },
        "2026-08-06": {
            "runs": 5, "success": 4, "fail": 1,
            "total_run_seconds": 700.0, "total_boss_seconds": 480.0,
            "last_boss_seconds": 95.0
        }
    }
}

`total_run_seconds` acumula a duração inteira de cada run; `total_boss_seconds`
acumula só o trecho de navegação até a frente do boss (o combate fica de fora).
`last_boss_seconds` é o `total_boss_seconds` da ÚLTIMA run do dia -- não acumula,
é substituído a cada run nova, para a interface mostrar "quanto foi até o boss na
última vez" mesmo depois de fechar o bot.

A gravação segue o mesmo cuidado do `config.py`: escrita atômica (`os.replace`)
sob `_LOCK_ARQUIVO`, porque a interface e os supervisores gravam do mesmo
processo em threads diferentes — sem isso uma escrita interrompida deixaria o
arquivo pela metade (e stats pela metade é histórico de run mentindo).
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Mesmo lugar relativo do config, já que `main.py` roda com a raiz como cwd.
ARQUIVO = Path("data") / "stats_diarias.json"

# Quantos dias de histórico manter (hoje + os 6 anteriores = uma semana).
DIAS_RETIDOS = 7

_LOCK_ARQUIVO = threading.Lock()

# Cache em memória: carregado no primeiro acesso, atualizado a cada gravação.
# Estrutura: { login: { data_iso: {runs, success, fail, total_run_seconds,
#                                 total_boss_seconds, last_boss_seconds} } }
_dados: dict[str, dict[str, dict[str, Any]]] | None = None


def caminho() -> Path:
    return ARQUIVO


def registrar_run(login: str, ok: bool, duracao: float,
                  duracao_ate_o_boss: float = 0.0) -> None:
    """Acrescenta uma run completa ao dia de hoje da conta e grava no disco.

    `duracao` é o tempo inteiro da run; `duracao_ate_o_boss` é só a navegação
    até a frente do boss (combate fora). Chamado uma vez por run (frequência
    baixa), então gravar a cada chamada quer dizer: se o bot for fechado no
    meio, não se perde a contagem.
    """
    login = (login or "").strip()
    if not login:
        return

    dados = _carregar()
    hoje = date.today().isoformat()
    alvo = dados.setdefault(login, {}).setdefault(hoje, _dia_vazio())
    alvo["runs"] += 1
    # `.get` porque o arquivo pode ter sido gravado por uma versão anterior,
    # sem a chave nova; sem isso um dia já existente estouraria KeyError.
    alvo["total_run_seconds"] = (
        alvo.get("total_run_seconds", 0.0) + max(0.0, duracao))
    alvo["total_boss_seconds"] = (
        alvo.get("total_boss_seconds", 0.0) + max(0.0, duracao_ate_o_boss))
    # Só a última importa: substitui a cada run, não acumula.
    alvo["last_boss_seconds"] = max(0.0, duracao_ate_o_boss)
    if ok:
        alvo["success"] += 1
    else:
        alvo["fail"] += 1

    _gravar()


def ultimos_dias(login: str, n: int = DIAS_RETIDOS) -> list[tuple[str, dict[str, Any]]]:
    """Lista `(data_iso, dia)` dos últimos n dias da conta, mais recente primeiro.

    Dias sem registro aparecem com zero (runs=0 etc.), para a interface
    mostrar "0" em vez de um buraco no meio da semana.
    """
    login = (login or "").strip()
    dados = _carregar().get(login, {})
    hoje = date.today()
    return [
        (dia.isoformat(), dados.get(dia.isoformat(), _dia_vazio()))
        for dia in (hoje - timedelta(days=delta) for delta in range(n))
    ]


def conhece(login: str) -> bool:
    """Se há histórico salvo para esta conta (qualquer dia retido)."""
    login = (login or "").strip()
    return bool(_carregar().get(login))


# ------------------------------------------------------------ helpers internos


def _carregar() -> dict[str, dict[str, dict[str, Any]]]:
    """Lê o arquivo uma vez e guarda em memória. Ausência = histórico vazio."""
    global _dados
    if _dados is None:
        if ARQUIVO.exists():
            with ARQUIVO.open(encoding="utf-8") as fh:
                _dados = json.load(fh)
        else:
            _dados = {}
    return _dados


def _gravar() -> None:
    """Grava o cache em disco de forma atômica, podando dias antigos."""
    global _dados
    limite = date.today() - timedelta(days=DIAS_RETIDOS - 1)

    # Podagem: só mantém `DIAS_RETIDOS` dias por conta (do mais antigo ao hoje).
    podado: dict[str, dict[str, dict[str, Any]]] = {}
    for login, dias in _carregar().items():
        filtrados = {
            dia: valor for dia, valor in dias.items()
            if _parse_dia(dia) is not None and _parse_dia(dia) >= limite
        }
        if filtrados:
            podado[login] = filtrados
    _dados = podado

    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK_ARQUIVO:
        temporario = ARQUIVO.with_name(ARQUIVO.name + ".tmp")
        with temporario.open("w", encoding="utf-8") as fh:
            json.dump(_dados, fh, indent=2, ensure_ascii=False)
        os.replace(temporario, ARQUIVO)


def _parse_dia(texto: str) -> date | None:
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _dia_vazio() -> dict[str, Any]:
    return {"runs": 0, "success": 0, "fail": 0,
            "total_run_seconds": 0.0, "total_boss_seconds": 0.0,
            "last_boss_seconds": 0.0}