"""RELATÓRIO DA ROTA -- onde, par a par de waypoints, a navegação perde tempo.

    ./.venv/Scripts/python.exe -m blazesbot.tools.relatorio_da_rota [pasta] [--desde AAAA-MM-DD]

AS DUAS CAVES (HH e BC). Decisão Q11 do grilling (25/09/2026): o relatório SÓ
APONTA; quem valida é o usuário, no jogo. Nada aqui muda rota, tolerância ou
tempo. O `--desde` é o que fecha o laço de aprender: mexeu na rota, compare o
antes e o depois pela data.

DE ONDE VEM CADA NÚMERO (log de dev, JSONL, inclusive `arquivo/` e `.gz`):

  * "waypoint N/M alcançado em X s | posição P" é uma PASSAGEM pelo par
    (waypoint N-1 -> N). O relógio da navegação zera a cada chegada, então X é
    o tempo DO PAR. Chegada que atravessou waypoints fica fora do tempo.
  * TEMPO PERDIDO de um par = soma do que cada passagem gastou ACIMA da
    mediana dele. A CAUSA é o problema mais grave visto na passagem (congelado,
    rollback, travada, "sem progresso", tempo esgotado); sem nenhum, "outro"
    (luta no caminho, que a HH tem de fazer).
  * Travada, rollback, congelado etc. também são CONTADOS no par em que a conta
    estava: do último waypoint alcançado para o seguinte.

A IDENTIDADE DO WAYPOINT é o par (índice, coordenada): a chegada N/M só conta
quando um trecho de uma das caves tem M waypoints e o N-ésimo fica a até
`DISTANCIA_PARA_CASAR` da posição lida. A coordenada sozinha não basta -- as
duas caves têm pontos a menos de 12 unidades um do outro. E o `goto` de um ponto
só (`1/1`, o das manobras de destravamento) não casa com trecho nenhum.

PONTOS QUENTES: o `logs/eventos.log` guarda semanas de travada, rollback e
congelado com posição; cada evento vai para o waypoint mais próximo da cave
certa, decidida pelo NOME da área (as coordenadas se sobrepõem).
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..bot.bc import mapa_bc
from ..bot.hh import mapa_hh
from ..core import lugares

# A tolerância da rota da cave é 7; a posição é lida depois do passo, com folga.
DISTANCIA_PARA_CASAR = 10
# Chegada mais velha que isto (segundos) já não diz em que par a conta está
# (outra run). É janela de análise, não espera: fica fora do `TEMPOS.md`.
VALIDADE_DO_PAR = 300
LINHAS_DO_RELATORIO = 12
# Evento a mais que isto do waypoint mais próximo não é de rota nenhuma.
RAIO_DO_PONTO_QUENTE = 25
# As contas de TESTE que gravaram no diário real até 26/09/2026 (ver
# `tests/conftest.py`). As linhas velhas saem sozinhas com a poda do diário.
CONTAS_DE_TESTE = frozenset({"simulacao", "conta"})

CHEGADA = re.compile(r"waypoint (\d+)/(\d+) alcançado em ([\d.]+)s"
                     r"( \(\+\d+ atravessado)?.*\| posição \((-?\d+), (-?\d+)\)")
TRAVADA = re.compile(r"^Navegação travada em ")
VOLTEI = re.compile(r"^Voltei do waypoint (\d+) para perto do")
ESGOTADO = re.compile(r"^Tempo esgotado no trajeto: cheguei ao waypoint (\d+) de (\d+)")
SEM_PROGRESSO = re.compile(r"^sem progresso indo para \((-?\d+), (-?\d+)\) "
                           r"\(waypoint (\d+)/(\d+).*relançando \(1\)")
CONGELADO = re.compile(r"^CONGELADO em ")
EVENTO = re.compile(r"^(\S+) \S+ \| (\S+) \| (TRAVADO-NA-CAVE|ROLLBACK|CONGELADO) \| "
                    r".*? \| pos=\((-?\d+), (-?\d+)\) \| local='([^']*)'")
# Filtro barato antes do `json.loads`: só ASCII, para valer com ou sem escape.
PISTAS = ("alcan", "travada", "Voltei do", "esgotado no trajeto", "sem progresso",
          "CONGELADO")
PROBLEMAS = ("travada", "rollback", "sem_progresso", "esgotado", "congelado")
# Da causa mais grave para a menos grave: é a que leva o tempo perdido.
GRAVIDADE = ("congelado", "rollback", "travada", "sem_progresso", "esgotado")


def trechos_das_caves() -> dict[str, list[tuple[int, int]]]:
    trechos = {f"HH {nome}": [(w.x, w.y) for w in caminho]
               for nome, caminho, _boss in mapa_hh.TRECHOS_DOS_BOSSES}
    # Os de UM ponto só ficam de fora: não se separam das manobras (`1/1`).
    for nome, caminho in (("BC altar", mapa_bc.CAMINHO_ATE_O_ALTAR),
                          ("BC boss", mapa_bc.CAMINHO_ATE_O_BOSS)):
        trechos[nome] = [(w.x, w.y) for w in caminho]
    return trechos


def casar(n: int, m: int, pos: tuple[int, int], trechos: dict) -> str | None:
    """O trecho cujo waypoint N (de M) está em `pos`, ou None."""
    for nome, pontos in trechos.items():
        if (len(pontos) == m and 1 <= n <= m
                and math.dist(pontos[n - 1], pos) <= DISTANCIA_PARA_CASAR):
            return nome
    return None


def _novo_par() -> dict:
    return {"passagens": 0, "tempos": [], "causas": [],
            **dict.fromkeys(PROBLEMAS, 0)}


def analisar(registros, trechos: dict | None = None) -> tuple[dict, int]:
    """`registros`: dicts {ts, conta, msg}, em ordem. Devolve (pares, sem_par).

    A chave de um par é (trecho, índice de origem, índice de destino), com
    índices a partir de 0 e -1 para "o começo do trecho".
    """
    trechos = trechos or trechos_das_caves()
    pares: dict = defaultdict(_novo_par)
    onde: dict = {}          # conta -> (trecho, índice alcançado, ts)
    vistos: dict = defaultdict(set)   # conta -> problemas desde a última chegada
    sem_par = 0

    def no_par_da_conta(r, problema, destino=None, total=None) -> None:
        nonlocal sem_par
        vistos[r["conta"]].add(problema)
        estado = onde.get(r["conta"])
        velho = (estado is not None and r["ts"] and estado[2]
                 and (r["ts"] - estado[2]).total_seconds() > VALIDADE_DO_PAR)
        if estado is None or velho:
            sem_par += 1
            return
        trecho, alcancado, _ = estado
        if total is not None and total != len(trechos[trecho]):
            vistos[r["conta"]].discard(problema)
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
                causa = next((c for c in GRAVIDADE if c in vistos[r["conta"]]), "outro")
                par["causas"].append(causa)
            vistos[r["conta"]].clear()
            onde[r["conta"]] = (trecho, n - 1, r["ts"])
        elif TRAVADA.search(msg):
            no_par_da_conta(r, "travada")
        elif CONGELADO.search(msg):
            no_par_da_conta(r, "congelado")
        elif m := VOLTEI.search(msg):
            no_par_da_conta(r, "rollback", destino=int(m[1]) - 1)
        elif m := ESGOTADO.search(msg):
            no_par_da_conta(r, "esgotado", destino=int(m[1]), total=int(m[2]))
        elif m := SEM_PROGRESSO.search(msg):
            n, total = int(m[3]), int(m[4])
            trecho = casar(n, total, (int(m[1]), int(m[2])), trechos)
            if trecho is not None:
                pares[(trecho, n - 2, n - 1)]["sem_progresso"] += 1
                vistos[r["conta"]].add("sem_progresso")
    return dict(pares), sem_par


def tempo_perdido(par: dict) -> collections.Counter:
    """Segundos ACIMA da mediana do par, por causa."""
    if not par["tempos"]:
        return collections.Counter()
    mediana = statistics.median(par["tempos"])
    perdido: collections.Counter = collections.Counter()
    for tempo, causa in zip(par["tempos"], par["causas"], strict=True):
        if tempo > mediana:
            perdido[causa] += tempo - mediana
    return perdido


def ler_registros(pasta: Path, desde: datetime | None = None):
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
                if desde is None or ts >= desde:
                    yield {"ts": ts, "conta": r.get("conta") or "",
                           "msg": r.get("msg", "")}


def _cave_da_area(local: str) -> str | None:
    if local.startswith(mapa_hh.NOME_DA_INSTANCIA) or local == mapa_hh.LUGAR_FORA_DA_HH:
        return "HH"
    return "BC" if local in lugares.AREAS_BC else None


def pontos_quentes(linhas, desde: datetime | None = None) -> dict:
    """{cave: Counter[(índice, ponto) -> {tipo: n}]} a partir do `eventos.log`."""
    pontos = {"HH": [(w.x, w.y) for w in mapa_hh.TODOS_OS_WAYPOINTS],
              "BC": [(w.x, w.y) for w in mapa_bc.TODOS_OS_WAYPOINTS]}
    quentes: dict = {"HH": defaultdict(collections.Counter),
                     "BC": defaultdict(collections.Counter)}
    for linha in linhas:
        m = EVENTO.match(linha)
        if not m or m[2] in CONTAS_DE_TESTE:
            continue
        if desde is not None and m[1] < desde.strftime("%Y-%m-%d"):
            continue
        cave = _cave_da_area(m[6])
        if cave is None:
            continue
        pos = (int(m[4]), int(m[5]))
        i, ponto = min(enumerate(pontos[cave]), key=lambda ip: math.dist(ip[1], pos))
        if math.dist(ponto, pos) <= RAIO_DO_PONTO_QUENTE:
            quentes[cave][(i, ponto)][m[3].lower()] += 1
    return quentes


def formatar(pares: dict, sem_par: int, trechos: dict, cave: str,
             linhas: int = LINHAS_DO_RELATORIO) -> list[str]:
    da_cave = {k: p for k, p in pares.items() if k[0].startswith(cave)}
    passagens = sum(p["passagens"] for p in da_cave.values())
    if not passagens:
        return [f"== {cave}: SEM DADOS no período"]
    primeiro = next(iter(t for t in trechos if t.startswith(cave)))
    runs = max(1, da_cave.get((primeiro, -1, 0), {}).get("passagens", 0))
    perdas = {k: tempo_perdido(p) for k, p in da_cave.items()}
    total = collections.Counter()
    for perdido in perdas.values():
        total.update(perdido)
    soma = sum(total.values())
    saida = [f"== {cave}: {passagens} passagens, ~{runs} runs; tempo perdido "
             f"{soma / 60:.0f} min = {soma / runs:.1f} s por run",
             "   por causa: " + ", ".join(f"{c} {s / 60:.1f} min"
                                          for c, s in total.most_common()),
             f"   {'trecho':<20}{'par':<26}{'pass':>5}{'med':>6}{'perd.':>7}"
             f"{'s/run':>6}  causas"]

    def ponto(trecho, i):
        return "começo" if i < 0 else f"{i + 1} {trechos[trecho][i]}"

    ordem = sorted(da_cave, key=lambda k: -sum(perdas[k].values()))
    for trecho, de, para in ordem[:linhas]:
        p, perdido = da_cave[(trecho, de, para)], perdas[(trecho, de, para)]
        med = statistics.median(p["tempos"]) if p["tempos"] else 0.0
        saida.append(
            f"   {trecho:<20}{ponto(trecho, de) + ' -> ' + ponto(trecho, para):<26}"
            f"{p['passagens']:>5}{med:>6.1f}{sum(perdido.values()) / 60:>6.1f}m"
            f"{sum(perdido.values()) / runs:>6.2f}  "
            + ", ".join(f"{c} {s / 60:.1f}m" for c, s in perdido.most_common(2)))
    saida.append(f"   problemas sem par identificado (sem chegada recente): {sem_par}")
    return saida


def formatar_pontos_quentes(quentes: dict, cave: str, linhas: int = 8) -> list[str]:
    itens = sorted(quentes[cave].items(), key=lambda kv: -sum(kv[1].values()))
    if not itens:
        return [f"   pontos quentes ({cave}): nenhum evento no período"]
    saida = [f"   pontos quentes ({cave}, eventos.log):"]
    for (i, ponto), tipos in itens[:linhas]:
        saida.append(f"     wp {i + 1:3d} {ponto!s:<12} {sum(tipos.values()):5d}  "
                     + ", ".join(f"{t} {n}" for t, n in tipos.most_common()))
    return saida


def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("pasta", nargs="?", default=str(Path("logs") / "dev"))
    args.add_argument("--desde", help="só a partir desta data (AAAA-MM-DD)")
    opcoes = args.parse_args(argv)
    desde = datetime.strptime(opcoes.desde, "%Y-%m-%d") if opcoes.desde else None
    trechos = trechos_das_caves()
    pares, sem_par = analisar(ler_registros(Path(opcoes.pasta), desde), trechos)
    eventos = Path("logs") / "eventos.log"
    quentes = pontos_quentes(eventos.open(encoding="utf-8", errors="replace")
                             if eventos.exists() else [], desde)
    for cave in ("HH", "BC"):
        for linha in formatar(pares, sem_par, trechos, cave) \
                + formatar_pontos_quentes(quentes, cave):
            print(linha)
    print("Os pares do topo são os candidatos: confira cada um NO JOGO antes de "
          "mexer em rota ou tolerância.")
    return 0 if pares else 1


if __name__ == "__main__":
    raise SystemExit(main())
