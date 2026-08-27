"""FERRAMENTA TEMPORÁRIA -- lê os JSONL do `16-TESTAR-CORRELACAO-ALVO` e julga.

    .venv\\Scripts\\python.exe analisar_correlacao.py
    .venv\\Scripts\\python.exe analisar_correlacao.py logs/correlacao/27220-*.jsonl

Não abre processo nenhum, não lê memória, não captura tela: só arquivo. Pode
rodar com o bot de pé.

===========================================================================
POR QUE ELA EXISTE SEPARADA DA COLETA
===========================================================================

O placar impresso no fim da coleta é do jeito que a régua estava NAQUELE
momento. Duas coisas aprendidas no primeiro log de 10 minutos mudaram a régua
depois de os dados já estarem gravados:

1. **O fator 2 do boss.** A razão barra/memória do `Blaze Skull Marshal` é 1,0
   ou exatamente 2,0 -- 54 ciclos contra 43, com razões de 1,988 a 2,080. A fase
   2 tem duas barras de vida: a memória conta o total, a tela desenha a atual.
   Contar isso como erro reprova o ponteiro que está certo.
2. **Ciclo não discriminante ELEGIA.** Com a barra em ~100% em 155 dos 274
   ciclos, tudo em vida cheia "bate" -- e a série foi ganha por um PET em
   243/243.

Separar a análise da coleta é o que permite reavaliar log antigo com régua nova,
em vez de precisar de uma noite nova a cada correção de critério.

===========================================================================
O QUE ELA RESPONDE
===========================================================================

* **TETO** -- em quantos ciclos discriminantes ALGUMA entidade da mesa bate com
  a barra. É o limite superior de qualquer método: nenhum ponteiro pode acertar
  mais do que existe para acertar. Teto baixo acusa a RÉGUA, não o ponteiro.
* **Por método** -- `jogador+0x808`, `0x80C` e cada slot estático, com a coluna
  discriminante separada.
* **Por entidade** -- quem acompanhou a barra, com nome e endereço.
* **Diagnóstico da régua** -- quantos valores distintos a barra produziu e se ela
  tem vãos. Barra de vida de verdade é contínua; a do APP saltava em quatro
  blocos com piso em 14,2.
"""
from __future__ import annotations

import glob
import itertools
import json
import statistics
import sys
from collections import Counter, defaultdict

TOLERANCIA_PP = 3.0
FAIXA_DISCRIMINANTE = (5.0, 95.0)
FATORES_DA_BARRA = (1.0, 2.0)


def bate(pct: float, barra: float) -> bool:
    return any(abs(pct * f - barra) <= TOLERANCIA_PP for f in FATORES_DA_BARRA)


def carregar(caminho: str) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def diagnosticar_a_regua(regs: list[dict]) -> list[str]:
    """A barra é plausível como barra de vida? Contínua, ou salta em bloco?"""
    valores = sorted({round(r["barra_tela"], 1) for r in regs
                      if r.get("barra_tela") is not None})
    if not valores:
        return ["  REGUA: nenhum gabarito de tela neste arquivo."]
    saida = [f"  REGUA: {len(valores)} valores distintos, de {valores[0]} a "
             f"{valores[-1]}"]
    vaos = [(a, b) for a, b in itertools.pairwise(valores) if b - a > 10.0]
    if vaos:
        saida.append("  ** VAOS na barra (barra de vida de verdade e continua): "
                     + ", ".join(f"{a}->{b}" for a, b in vaos[:6]))
    if valores[0] > 5.0:
        saida.append(f"  ** PISO em {valores[0]}: a barra nunca chega perto de "
                     f"zero. Vermelho fixo no retangulo medido?")
    if len(valores) <= 20:
        saida.append(f"  ** POUCOS valores ({len(valores)}): "
                     f"{valores}")
    # geometria, quando o log a tiver (coletas a partir de 21/08/2026)
    geos = Counter()
    for r in regs:
        g = r.get("geometria") or {}
        if g.get("achou"):
            geos[(tuple(g["quadro"]), g["y_da_mana"], g["largura_da_mana"])] += 1
        elif g:
            geos[("nao achou",)] += 1
    if geos:
        saida.append("  geometria da regua (quadro, y da mana, largura):")
        for chave, n in geos.most_common(5):
            saida.append(f"    {n:5d}x  {chave}")
        if len([k for k in geos if k != ("nao achou",)]) > 1:
            saida.append("  ** A GEOMETRIA MUDOU no meio da coleta: a regua "
                         "mediu retangulos diferentes.")
    return saida


def analisar(caminho: str) -> None:
    regs = carregar(caminho)
    disc = [r for r in regs
            if r.get("barra_tela") is not None
            and FAIXA_DISCRIMINANTE[0] < r["barra_tela"] < FAIXA_DISCRIMINANTE[1]]
    print("=" * 100)
    print(f"{caminho}")
    print(f"  {len(regs)} ciclos | {sum(1 for r in regs if r.get('barra_tela') is not None)}"
          f" com gabarito | {len(disc)} discriminantes")
    for linha in diagnosticar_a_regua(regs):
        print(linha)
    if not disc:
        print("  Sem ciclo discriminante: nada a julgar (barra sempre em extremo).")
        return

    entidades_por_ciclo = [r["n_entidades"] for r in regs]
    print(f"  entidades por ciclo: min={min(entidades_por_ciclo)} "
          f"mediana={int(statistics.median(entidades_por_ciclo))} "
          f"max={max(entidades_por_ciclo)}")

    # -- TETO -------------------------------------------------------------
    cobertos = 0
    for r in disc:
        if any(e.get("pct") is not None and bate(e["pct"], r["barra_tela"])
               for e in r["entidades"]):
            cobertos += 1
    print(f"\n  TETO: alguma entidade da mesa bate com a barra em "
          f"{cobertos}/{len(disc)} = {cobertos / len(disc) * 100:.1f}% dos ciclos")
    if cobertos / len(disc) < 0.9:
        print("  ** TETO BAIXO acusa a REGUA, nao o ponteiro: se ninguem na mesa "
              "tem aquele HP,\n     a barra nao esta medindo a vida de quem esta "
              "selecionado.")

    # -- por método -------------------------------------------------------
    metodos: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in disc:
        por_obj = {e["obj"]: e for e in r["entidades"]}
        for nome, dado in (r.get("suspeitos") or {}).items():
            obj = dado.get("obj")
            e = por_obj.get(obj) if obj else None
            if not e or e.get("pct") is None:
                continue
            metodos[nome][0] += 1
            if bate(e["pct"], r["barra_tela"]):
                metodos[nome][1] += 1
    if metodos:
        print(f"\n  {'metodo':26s} {'respondeu':>9s} {'acerto discriminante':>21s}")
        print("  " + "-" * 58)
        for nome, (n, a) in sorted(metodos.items(),
                                   key=lambda kv: -kv[1][1] / max(kv[1][0], 1)):
            print(f"  {nome:26s} {n:9d} {a / n * 100 if n else 0:20.1f}%")

    # -- por entidade -----------------------------------------------------
    acertos: Counter = Counter()
    presencas: Counter = Counter()
    nomes: dict[int, str] = {}
    for r in disc:
        for e in r["entidades"]:
            if e.get("pct") is None:
                continue
            presencas[e["obj"]] += 1
            if e.get("nome"):
                nomes.setdefault(e["obj"], e["nome"])
            if bate(e["pct"], r["barra_tela"]):
                acertos[e["obj"]] += 1
    ranking = sorted(((acertos[o], presencas[o], o) for o in presencas),
                     reverse=True)
    print("\n  ENTIDADES QUE MAIS ACOMPANHARAM A BARRA:")
    for a, n, o in ranking[:5]:
        if not a:
            break
        print(f"    {a:4d}/{n:<4d} ciclos ({a / n * 100:5.1f}%)  @{o:#x}  "
              f"{nomes.get(o, '?')!r}")
    if ranking and not ranking[0][0]:
        print("    nenhuma entidade bateu com a barra em ciclo discriminante "
              "nenhum.")


def main(argv: list[str]) -> int:
    padroes = argv[1:] or ["logs/correlacao/*.jsonl"]
    arquivos: list[str] = []
    for padrao in padroes:
        arquivos.extend(sorted(glob.glob(padrao)))
    if not arquivos:
        print(f"Nenhum arquivo casou com {padroes}.")
        return 1
    for caminho in arquivos:
        try:
            analisar(caminho)
        except Exception as exc:                      # um arquivo ruim não para o resto
            print(f"{caminho}: FALHOU ({exc!r})")
    print("=" * 100)
    print("CRITERIO: o ponteiro so pode ser promovido com acerto discriminante")
    print("acima de 99%. E o TETO tem de estar alto -- teto baixo significa que a")
    print("regua (a barra da tela) e que precisa de conserto primeiro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
