"""JULGA A MEDIÇÃO DA ROLHA: com que limiar o detector acertaria -- e se erraria caro.

Lê as linhas `ROLHA/MEDIÇÃO` que a venda grava com `leitura_do_slot.MEDIR_A_ROLHA`
ligado: por passada, a mudança do miolo do slot N a cada clique (`difs`) e quanto
a bolsa baixou no Sell (`vendidos` -- a VERDADE, lida da memória).

O DETECTOR JULGADO: a rolha começa no primeiro clique de `k` mudanças seguidas
abaixo de `limiar`. Rolha no clique p quer dizer que a passada venderia p - 1.

    vendeu MAIS que p - 1  -> FALSO POSITIVO: a parada teria encerrado a venda com
                              item vendável na grade. É o erro CARO -- um basta.
    vendeu p - 1           -> EXATO
    vendeu MENOS que p - 1 -> TARDE: a parada teria vindo depois; custa cliques,
                              não item
    sem rolha e a passada vendeu todos os cliques -> LIMPA

O CRITÉRIO PARA LIGAR A PARADA (combinado com o usuário em 25/09/2026): no mínimo
`VENDAS_MINIMAS` vendas medidas, ZERO falso positivo e a posição exata em pelo
menos `EXATIDAO_MINIMA` das passadas com rolha. Só leitura: nada aqui muda o bot.

    python -m blazesbot.tools.medir_a_rolha [pasta dos logs]
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

VENDAS_MINIMAS = 30
EXATIDAO_MINIMA = 0.95
KS = (1, 2, 3, 4)
LIMIARES = (0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0)

LINHA = re.compile(
    r"ROLHA/MEDIÇÃO passada=(\d+) cliques=(\d+) vendidos=(-?\d+|None) difs=(\[.*\])")


def primeira_rolha(difs: list[float | None], k: int, limiar: float) -> int | None:
    """Clique (contado de 1) em que começam `k` mudanças seguidas abaixo do limiar."""
    seguidas = 0
    for clique, d in enumerate(difs, start=1):
        seguidas = seguidas + 1 if d is not None and d < limiar else 0
        if seguidas == k:
            return clique - k + 1
    return None


def julgar(passadas: list[dict], k: int, limiar: float) -> dict:
    conta = {"falso_positivo": 0, "exato": 0, "tarde": 0, "perdida": 0, "limpa": 0}
    for p in passadas:
        rolha = primeira_rolha(p["difs"], k, limiar)
        vendidos, cliques = p["vendidos"], p["cliques"]
        if rolha is None:
            conta["limpa" if vendidos >= cliques else "perdida"] += 1
        elif vendidos > rolha - 1:
            conta["falso_positivo"] += 1
        elif vendidos == rolha - 1:
            conta["exato"] += 1
        else:
            conta["tarde"] += 1
    return conta


def ler_passadas(pasta: Path) -> list[dict]:
    passadas = []
    # `rglob`, não `glob`: o log de dev guarda poucas linhas no arquivo vivo e
    # despeja o resto em `arquivo/` (o do dia, depois `.gz`) -- é lá que a
    # medição de horas de venda vai estar.
    for arquivo in sorted(pasta.rglob("*.jsonl*")):
        abrir = gzip.open if arquivo.suffix == ".gz" else open
        with abrir(arquivo, "rt", encoding="utf-8", errors="replace") as f:
            for linha in f:
                if "ROLHA/MEDI" not in linha:
                    continue
                try:
                    msg = json.loads(linha).get("msg", "")
                except ValueError:
                    continue
                m = LINHA.search(msg)
                if not m or m.group(3) == "None":
                    continue
                passadas.append({"passada": int(m.group(1)), "cliques": int(m.group(2)),
                                 "vendidos": int(m.group(3)), "difs": json.loads(m.group(4))})
    return passadas


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pasta = Path(argv[0]) if argv else Path("logs") / "dev"
    passadas = ler_passadas(pasta)
    vendas = sum(1 for p in passadas if p["passada"] == 1)
    print(f"{len(passadas)} passadas medidas em {vendas} vendas ({pasta})")
    if not passadas:
        print("VEREDITO: SEM DADOS -- rode a HH com MEDIR_A_ROLHA ligado.")
        return 1
    melhor = None
    print(f"{'k':>2} {'limiar':>6} {'falso+':>7} {'exato':>6} {'tarde':>6} "
          f"{'perdida':>8} {'limpa':>6}")
    for k in KS:
        for limiar in LIMIARES:
            c = julgar(passadas, k, limiar)
            print(f"{k:>2} {limiar:>6} {c['falso_positivo']:>7} {c['exato']:>6} "
                  f"{c['tarde']:>6} {c['perdida']:>8} {c['limpa']:>6}")
            com_rolha = c["exato"] + c["tarde"] + c["perdida"]
            exatidao = c["exato"] / com_rolha if com_rolha else 0.0
            if c["falso_positivo"] == 0 and (melhor is None or exatidao > melhor[0]):
                melhor = (exatidao, k, limiar)
    if vendas < VENDAS_MINIMAS:
        print(f"VEREDITO: INSUFICIENTE -- {vendas} vendas, o mínimo é {VENDAS_MINIMAS}.")
        return 1
    if melhor is None or melhor[0] < EXATIDAO_MINIMA:
        print("VEREDITO: REPROVADO -- nenhum (k, limiar) sem falso positivo chega a "
              f"{EXATIDAO_MINIMA:.0%} de exatidão. A parada NÃO pode ser ligada.")
        return 1
    print(f"VEREDITO: APROVADO -- k={melhor[1]}, limiar={melhor[2]}: zero falso "
          f"positivo, {melhor[0]:.0%} exato. Escolha com MARGEM, não o limite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
