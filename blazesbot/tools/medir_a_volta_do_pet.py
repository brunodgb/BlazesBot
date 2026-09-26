"""JULGA A MEDIÇÃO DA VOLTA DO PET: o `pet_active()` marca a volta depois da troca de mapa?

Lê as linhas `PET/MEDIÇÃO` que o `core/pet.MEDIR_A_VOLTA_DO_PET` grava: por troca
de mapa, os trechos de `pet_active()` nos segundos seguintes.

    SOME E VOLTA -- False logo depois da troca e True em seguida: o sinal ENXERGA a
                    recriação do pet, e o tempo até a volta, medido, pode trocar
                    os 30 s fixos por uma espera curta por esse sinal.
    SEMPRE TRUE  -- a leitura não enxerga a recriação: os 30 s ficam como estão.

O CRITÉRIO: no mínimo `TROCAS_MINIMAS` trocas medidas, e o mesmo desfecho em pelo
menos `CONSISTENCIA_MINIMA` delas. Só leitura: nada aqui muda o bot.

    python -m blazesbot.tools.medir_a_volta_do_pet [pasta dos logs]
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

TROCAS_MINIMAS = 30
CONSISTENCIA_MINIMA = 0.8

LINHA = re.compile(r"PET/MEDIÇÃO conta=(\S+) leituras=(\d+) trechos=(\[.*\])")


def classificar(trechos: list[list]) -> tuple[str, float | None]:
    """`("some_e_volta", t)`, `("sempre_true", None)`, `("nao_voltou", None)` ou
    `("ilegivel", None)` -- `t` é o segundo em que o True começou."""
    valores = [v for v, _ini, _fim in trechos]
    if not valores or all(v is None for v in valores):
        return "ilegivel", None
    if all(v is True for v in valores if v is not None):
        return "sempre_true", None
    sumiu = False
    for valor, inicio, _fim in trechos:
        if valor is False:
            sumiu = True
        elif valor is True and sumiu:
            return "some_e_volta", inicio
    return "nao_voltou", None


def ler_trocas(pasta: Path) -> list[list[list]]:
    trocas = []
    # `rglob`, não `glob`: o excedente do log de dev vai para `arquivo/`.
    for arquivo in sorted(pasta.rglob("*.jsonl*")):
        abrir = gzip.open if arquivo.suffix == ".gz" else open
        with abrir(arquivo, "rt", encoding="utf-8", errors="replace") as f:
            for linha in f:
                if "PET/MEDI" not in linha:
                    continue
                try:
                    m = LINHA.search(json.loads(linha).get("msg", ""))
                except ValueError:
                    continue
                if m:
                    trocas.append(json.loads(m.group(3)))
    return trocas


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    pasta = Path(argv[0]) if argv else Path("logs") / "dev"
    trocas = ler_trocas(pasta)
    if not trocas:
        print(f"VEREDITO: SEM DADOS em {pasta} -- rode com MEDIR_A_VOLTA_DO_PET ligado.")
        return 1
    desfechos: dict[str, int] = {}
    voltas: list[float] = []
    for trechos in trocas:
        tipo, t = classificar(trechos)
        desfechos[tipo] = desfechos.get(tipo, 0) + 1
        if t is not None:
            voltas.append(t)
    print(f"{len(trocas)} trocas de mapa medidas: {desfechos}")
    if voltas:
        voltas.sort()
        print(f"tempo até a volta: p50 {voltas[len(voltas) // 2]:.2f} s | "
              f"p90 {voltas[int(len(voltas) * 0.9)]:.2f} s | máx {voltas[-1]:.2f} s")
    if len(trocas) < TROCAS_MINIMAS:
        print(f"VEREDITO: INSUFICIENTE -- {len(trocas)} trocas, o mínimo é {TROCAS_MINIMAS}.")
        return 1
    fracao = {tipo: n / len(trocas) for tipo, n in desfechos.items()}
    if fracao.get("some_e_volta", 0) >= CONSISTENCIA_MINIMA:
        print(f"VEREDITO: SINAL ÚTIL -- espere o pet_active() voltar, com teto na "
              f"cauda medida ({voltas[-1]:.1f} s) e margem, em vez dos 30 s fixos.")
        return 0
    if fracao.get("sempre_true", 0) >= CONSISTENCIA_MINIMA:
        print("VEREDITO: SINAL INÚTIL -- a leitura não enxerga a recriação do pet. "
              "Os 30 s ficam.")
        return 0
    print("VEREDITO: INCONCLUSIVO -- desfechos misturados; nada muda.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
