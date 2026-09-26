"""RELATÓRIO DA ROTA DA HH -- onde, par a par de waypoints, a navegação sofre.

    ./.venv/Scripts/python.exe -m blazesbot.tools.relatorio_da_rota_hh [pasta]

Decisão Q11 do grilling (25/09/2026): o relatório SÓ APONTA -- quem valida é o
usuário, no jogo. Nada aqui muda rota, tolerância ou tempo. Só leitura.

DE ONDE VEM CADA NÚMERO (log de dev, JSONL, inclusive `arquivo/` e `.gz`):

  * "waypoint N/M alcançado em X s | posição P" é uma PASSAGEM pelo par
    (waypoint N-1 -> N). O relógio da navegação zera a cada chegada, então X é
    o tempo DO PAR. Chegada que atravessou waypoints conta como passagem, mas
    fica fora do tempo -- ele cobre mais de um par.
  * "Navegação travada", "Voltei do waypoint N", "Tempo esgotado no trajeto" e a
    PRIMEIRA linha de cada "sem progresso indo para P" são PROBLEMAS, contados
    no par em que a conta estava.

A IDENTIDADE DO WAYPOINT é o par (índice, coordenada): a chegada N/M só conta
quando um trecho de `mapa_hh.TRECHOS_DOS_BOSSES` tem M waypoints e o N-ésimo
fica a até `DISTANCIA_PARA_CASAR` da posição lida. A coordenada sozinha não
basta -- o BC tem pontos a menos de 12 unidades de pontos da HH. E o `goto` de
um ponto só (`1/1`, o das manobras de destravamento) não casa com trecho
nenhum, então fica de fora sem regra especial.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..bot.hh import mapa_hh

# A tolerância da rota da cave é 7; a posição é lida depois do passo, com folga.
DISTANCIA_PARA_CASAR = 10
# Chegada mais velha que isto (segundos) já não diz em que par a conta está
# (outra run). É janela de análise, não espera: fica fora do `TEMPOS.md`.
VALIDADE_DO_PAR = 300
LINHAS_DO_RELATORIO = 15

CHEGADA = re.compile(r"waypoint (\d+)/(\d+) alcançado em ([\d.]+)s"
                     r"( \(\+\d+ atravessado)?.*\| posição \((-?\d+), (-?\d+)\)")
TRAVADA = re.compile(r"^Navegação travada em ")
VOLTEI = re.compile(r"^Voltei do waypoint (\d+) para perto do")
ESGOTADO = re.compile(r"^Tempo esgotado no trajeto: cheguei ao waypoint (\d+) de (\d+)")
SEM_PROGRESSO = re.compile(r"^sem progresso indo para \((-?\d+), (-?\d+)\) "
                           r"\(waypoint (\d+)/(\d+).*relançando \(1\)")
# Filtro barato antes do `json.loads`: só ASCII, para valer com ou sem escape.
PISTAS = ("alcan", "travada", "Voltei do", "esgotado no trajeto", "sem progresso")
PROBLEMAS = ("travada", "rollback", "sem_progresso", "esgotado")


def trechos_da_hh() -> dict[str, list[tuple[int, int]]]:
    return {nome: [(w.x, w.y) for w in caminho]
            for nome, caminho, _boss in mapa_hh.TRECHOS_DOS_BOSSES}


def casar(n: int, m: int, pos: tuple[int, int], trechos: dict) -> str | None:
    """O trecho da HH cujo waypoint N (de M) está em `pos`, ou None."""
    for nome, pontos in trechos.items():
        if (len(pontos) == m and 1 <= n <= m
                and math.dist(pontos[n - 1], pos) <= DISTANCIA_PARA_CASAR):
            return nome
    return None


def _novo_par() -> dict:
    return {"passagens": 0, "tempos": [], **dict.fromkeys(PROBLEMAS, 0)}


def analisar(registros, trechos: dict | None = None) -> tuple[dict, int]:
    """`registros`: dicts {ts, conta, msg}, em ordem. Devolve (pares, sem_par).

    A chave de um par é (trecho, índice de origem, índice de destino), com
    índices a partir de 0 e -1 para "o começo do trecho".
    """
    trechos = trechos or trechos_da_hh()
    pares: dict = defaultdict(_novo_par)
    onde: dict = {}          # conta -> (trecho, índice alcançado, ts)
    sem_par = 0

    def no_par_da_conta(r, problema, destino=None, total=None) -> None:
        nonlocal sem_par
        estado = onde.get(r["conta"])
        velho = (estado is not None and r["ts"] and estado[2]
                 and (r["ts"] - estado[2]).total_seconds() > VALIDADE_DO_PAR)
        if estado is None or velho:
            sem_par += 1
            return
        trecho, alcancado, _ = estado
        if total is not None and total != len(trechos[trecho]):
            return               # era um `goto`, não a rota da cave
        destino = alcancado + 1 if destino is None else destino
        if 0 <= destino < len(trechos[trecho]):
            pares[(trecho, destino - 1, destino)][problema] += 1
        else:
            sem_par += 1

    for r in registros:
        msg = r["msg"]
        if m := CHEGADA.search(msg):
            n, total = int(m[1]), int(m[2])
            trecho = casar(n, total, (int(m[5]), int(m[6])), trechos)
            if trecho is None:
                continue
            par = pares[(trecho, n - 2, n - 1)]
            par["passagens"] += 1
            if not m[4]:
                par["tempos"].append(float(m[3]))
            onde[r["conta"]] = (trecho, n - 1, r["ts"])
        elif TRAVADA.search(msg):
            no_par_da_conta(r, "travada")
        elif m := VOLTEI.search(msg):
            no_par_da_conta(r, "rollback", destino=int(m[1]) - 1)
        elif m := ESGOTADO.search(msg):
            no_par_da_conta(r, "esgotado", destino=int(m[1]), total=int(m[2]))
        elif m := SEM_PROGRESSO.search(msg):
            n, total = int(m[3]), int(m[4])
            trecho = casar(n, total, (int(m[1]), int(m[2])), trechos)
            if trecho is not None:
                pares[(trecho, n - 2, n - 1)]["sem_progresso"] += 1
    return dict(pares), sem_par


def ler_registros(pasta: Path):
    """Os registros do log de dev que interessam, em ordem de arquivo."""
    for arquivo in sorted(pasta.rglob("*.jsonl*")):
        abrir = gzip.open if arquivo.suffix == ".gz" else open
        with abrir(arquivo, "rt", encoding="utf-8", errors="replace") as f:
            for linha in f:
                if not any(p in linha for p in PISTAS):
                    continue
                try:
                    r = json.loads(linha)
                    ts = datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S.%f")
                except (ValueError, KeyError, TypeError):
                    continue
                yield {"ts": ts, "conta": r.get("conta") or "", "msg": r.get("msg", "")}


def _p90(tempos: list[float]) -> float:
    return statistics.quantiles(tempos, n=10)[-1] if len(tempos) >= 2 else tempos[0]


def formatar(pares: dict, sem_par: int, trechos: dict,
             linhas: int = LINHAS_DO_RELATORIO) -> list[str]:
    def ponto(trecho, i):
        return "começo" if i < 0 else f"{i + 1} {trechos[trecho][i]}"

    def peso(item):
        _chave, p = item
        return (sum(p[k] for k in PROBLEMAS), _p90(p["tempos"]) if p["tempos"] else 0)

    saida = [f"{'trecho':<16} {'par':<28} {'pass':>5} {'med':>5} {'p90':>5} "
             f"{'máx':>5} {'trav':>4} {'roll':>4} {'s/pr':>4} {'esg':>4}"]
    for (trecho, de, para), p in sorted(pares.items(), key=peso, reverse=True)[:linhas]:
        t = p["tempos"]
        tempos = (f"{statistics.median(t):>5.1f} {_p90(t):>5.1f} {max(t):>5.1f}"
                  if t else f"{'-':>5} {'-':>5} {'-':>5}")
        saida.append(
            f"{trecho:<16} {ponto(trecho, de) + ' -> ' + ponto(trecho, para):<28} "
            f"{p['passagens']:>5} {tempos} {p['travada']:>4} {p['rollback']:>4} "
            f"{p['sem_progresso']:>4} {p['esgotado']:>4}")
    saida.append(f"problemas sem par identificado (sem chegada recente): {sem_par}")
    return saida


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pasta = Path(argv[0]) if argv else Path("logs") / "dev"
    trechos = trechos_da_hh()
    pares, sem_par = analisar(ler_registros(pasta), trechos)
    passagens = sum(p["passagens"] for p in pares.values())
    print(f"{passagens} passagens em {len(pares)} pares da HH ({pasta})")
    if not passagens:
        print("SEM DADOS -- rode a HH com o log de dev ligado (BLAZES_MODO=dev).")
        return 1
    for linha in formatar(pares, sem_par, trechos):
        print(linha)
    print("Os pares do topo são os candidatos: confira cada um NO JOGO antes de "
          "mexer em rota ou tolerância.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
