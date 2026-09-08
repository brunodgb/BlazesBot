"""Lê o `latencia.jsonl` e diz ONDE o bot vive — e onde ele espera à toa.

    python -m blazesbot.core.relatorio_de_latencia

O log de latência é agregado por janela de 30 s e por conta, então uma sessão
de horas rende milhares de linhas de várias contas. Este módulo junta tudo e
responde as três perguntas que decidem um ajuste de tempo:

1. **ONDE O TEMPO VAI** (ranking por total). Otimizar o que não aparece aqui é
   trabalho sem efeito, por melhor que seja o número relativo.
2. **ONDE ESTÃO OS PICOS** (ranking por máximo). Um máximo muito acima da média
   é a assinatura de espera cega ou de bloqueio -- é onde há tempo a devolver.
3. **O QUE É INSTÁVEL** (máximo ÷ mediana). Ação que às vezes custa 50x a média
   é o que atropela o jogo, e a que precisa de teto MAIOR, não menor.

=========================================================================
POR QUE O RANKING É POR TOTAL, E NÃO POR MÉDIA
=========================================================================

Uma função de 400 ms chamada 3 vezes por run custa 1,2 s; uma de 0,4 ms chamada
20.000 vezes custa 8 s. A média premia a primeira e a segunda é que decide a
duração da run. O total é a única ordenação que não engana.

=========================================================================
ESTE RELATÓRIO NÃO AJUSTA NADA
=========================================================================

Ele produz a PROVA para um ajuste, que é coisa diferente. O projeto exige
medição para todo número novo (`CLAUDE.md`), e o catálogo de esperas vive em
`docs/TEMPOS.md` com a natureza de cada uma (TETO, PASSO ou FIXO). Cruzar as
duas coisas -- um `FIXO` de 0,6 s contra um trabalho real de 0,04 s -- é o que
transforma "parece lento" em "0,56 s são desperdício medido".
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

from .cronometro import ARQUIVO, PASTA


class _Junto:
    """O acumulado de um nome, somando todas as janelas e todas as contas."""

    __slots__ = ("contas", "maximo", "minimo", "n", "total")

    def __init__(self) -> None:
        self.n = 0
        self.total = 0.0
        self.minimo = float("inf")
        self.maximo = 0.0
        self.contas: set[str] = set()

    @property
    def media(self) -> float:
        return self.total / self.n if self.n else 0.0

    @property
    def instabilidade(self) -> float:
        """Máximo ÷ média. Alto = a mesma ação às vezes custa muito mais."""
        return self.maximo / self.media if self.media else 0.0


def _arquivos() -> list[Path]:
    achados = [ARQUIVO] if ARQUIVO.exists() else []
    morto = PASTA / "arquivo"
    if morto.is_dir():
        achados += sorted(morto.iterdir())
    return achados


def juntar() -> dict[str, _Junto]:
    """Todas as janelas de todas as contas, num acumulado por nome."""
    por_nome: dict[str, _Junto] = defaultdict(_Junto)
    for caminho in _arquivos():
        abrir = gzip.open if caminho.suffix == ".gz" else open
        try:
            with abrir(caminho, "rt", encoding="utf-8", errors="replace") as f:
                for linha in f:
                    if not linha.lstrip().startswith("{"):
                        continue
                    try:
                        d = json.loads(linha)
                    except Exception:
                        continue
                    j = por_nome[d["nome"]]
                    j.n += d["n"]
                    j.total += d["total_ms"]
                    j.minimo = min(j.minimo, d["min_ms"])
                    j.maximo = max(j.maximo, d["max_ms"])
                    if d.get("conta"):
                        j.contas.add(d["conta"])
        except OSError:
            continue
    return dict(por_nome)


def _tabela(titulo: str, linhas, chave) -> str:
    saida = [f"\n{titulo}", "-" * len(titulo)]
    saida.append(f"{'nome':<52} {'n':>9} {'total s':>9} "
                 f"{'med ms':>9} {'max ms':>9} {'max/med':>8}")
    for nome, j in linhas:
        saida.append(f"{nome[:52]:<52} {j.n:>9,} {j.total/1000:>9.1f} "
                     f"{j.media:>9.3f} {j.maximo:>9.1f} "
                     f"{j.instabilidade:>8.0f}x")
    return "\n".join(saida)


def relatorio(quantos: int = 20) -> str:
    por_nome = juntar()
    if not por_nome:
        return (f"Nenhuma medição em {PASTA}. A telemetria escreve a cada "
                f"30 s com o bot rodando — rode o bot e volte aqui.")

    itens = list(por_nome.items())
    partes = [
        f"{len(itens)} nomes medidos | "
        f"{sum(j.n for _, j in itens):,} chamadas | "
        f"{sum(j.total for _, j in itens)/1000:,.0f} s cronometrados",
        _tabela("ONDE O TEMPO VAI (por total)",
                sorted(itens, key=lambda x: -x[1].total)[:quantos], None),
        _tabela("OS PICOS (por máximo)",
                sorted(itens, key=lambda x: -x[1].maximo)[:quantos], None),
        _tabela("O QUE É INSTÁVEL (máximo ÷ média, com n >= 30)",
                sorted((i for i in itens if i[1].n >= 30),
                       key=lambda x: -x[1].instabilidade)[:quantos], None),
    ]
    partes.append(
        "\nCOMO LER: o ranking por TOTAL diz onde otimizar tem efeito. "
        "Um máximo muito acima da média é espera cega ou bloqueio — tempo a "
        "devolver. Instabilidade alta pede teto MAIOR, não menor: é a ação "
        "que às vezes atropela o jogo. Cruze com `docs/TEMPOS.md`, que diz "
        "quais esperas são TETO, PASSO ou FIXO."
    )
    return "\n".join(partes)


if __name__ == "__main__":  # pragma: no cover
    quantos = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    print(relatorio(quantos))
