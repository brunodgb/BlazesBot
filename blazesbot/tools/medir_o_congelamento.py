"""JULGA A MEDIÇÃO DO CONGELAMENTO: até quanto os 15 s da 1ª cutucada podem cair.

Lê as linhas `CONGELAMENTO/MEDIÇÃO parado=…s cutucadas=…` que o vigia
(`bot/congelamento.py`, com `MEDIR_O_CONGELAMENTO` ligado) grava quando uma
parada de pelo menos 2 s ACABA -- a coordenada mudou.

    cutucadas = 0  -> a parada se resolveu SOZINHA
    cutucadas >= 1 -> congelamento de verdade: chegou aos 15 s e levou cutucada

PARA CADA LIMIAR T CANDIDATO:

    falsas = paradas que se resolveram sozinhas e duraram >= T: com o limiar em
             T, elas levariam uma cutucada à toa (desmonta e remonta);
    ganho  = (SEGUNDOS_PARA_CUTUCAR - T) por congelamento de verdade.

O CRITÉRIO (proposta de 26/09/2026, para o usuário confirmar): no mínimo
`CONGELAMENTOS_MINIMOS` congelamentos medidos e, no limiar escolhido, as falsas
em no máximo `FALSAS_TOLERADAS` das cutucadas que ele daria. Só leitura: nada
aqui muda o bot.

    python -m blazesbot.tools.medir_o_congelamento [pasta dos logs]
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

from ..bot.congelamento import SEGUNDOS_PARA_CUTUCAR

CONGELAMENTOS_MINIMOS = 30
FALSAS_TOLERADAS = 0.10
LIMIARES = (3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0)

LINHA = re.compile(r"CONGELAMENTO/MEDIÇÃO parado=([\d.]+)s cutucadas=(\d+)")


def julgar(paradas: list[tuple[float, int]], limiar: float) -> dict:
    """`paradas` = [(segundos parado, cutucadas)]. Contagens para o limiar."""
    reais = sum(1 for _s, c in paradas if c >= 1)
    falsas = sum(1 for s, c in paradas if c == 0 and s >= limiar)
    daria = reais + falsas
    return {"reais": reais, "falsas": falsas,
            "fracao_falsa": falsas / daria if daria else 0.0,
            "ganho_s": reais * max(0.0, SEGUNDOS_PARA_CUTUCAR - limiar)}


def ler_paradas(pasta: Path) -> list[tuple[float, int]]:
    paradas = []
    # `rglob`: o excedente do log de dev vai para `arquivo/`.
    for arquivo in sorted(pasta.rglob("*.jsonl*")):
        abrir = gzip.open if arquivo.suffix == ".gz" else open
        with abrir(arquivo, "rt", encoding="utf-8", errors="replace") as f:
            for linha in f:
                if "CONGELAMENTO/MEDI" not in linha:
                    continue
                try:
                    m = LINHA.search(json.loads(linha).get("msg", ""))
                except ValueError:
                    continue
                if m:
                    paradas.append((float(m[1]), int(m[2])))
    return paradas


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pasta = Path(argv[0]) if argv else Path("logs") / "dev"
    paradas = ler_paradas(pasta)
    reais = sum(1 for _s, c in paradas if c >= 1)
    print(f"{len(paradas)} paradas medidas, {reais} congelamentos de verdade ({pasta})")
    if not paradas:
        print("VEREDITO: SEM DADOS -- rode a HH com MEDIR_O_CONGELAMENTO ligado.")
        return 1
    print(f"{'limiar':>6} {'falsas':>7} {'% falsas':>9} {'ganho total':>12}")
    aprovado = None
    for limiar in LIMIARES:
        j = julgar(paradas, limiar)
        print(f"{limiar:>5.0f}s {j['falsas']:>7} {j['fracao_falsa']:>9.0%} "
              f"{j['ganho_s'] / 60:>9.1f} min")
        if aprovado is None and j["fracao_falsa"] <= FALSAS_TOLERADAS:
            aprovado = limiar
    if reais < CONGELAMENTOS_MINIMOS:
        print(f"VEREDITO: INSUFICIENTE -- {reais} congelamentos, o mínimo é "
              f"{CONGELAMENTOS_MINIMOS}.")
        return 1
    if aprovado is None:
        print(f"VEREDITO: REPROVADO -- nenhum limiar fica com no máximo "
              f"{FALSAS_TOLERADAS:.0%} de cutucadas à toa. Os 15 s ficam.")
        return 1
    print(f"VEREDITO: APROVADO -- a 1ª cutucada pode vir em {aprovado:.0f}s "
          f"(hoje {SEGUNDOS_PARA_CUTUCAR:.0f}s). Escolha com MARGEM, não o limite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
