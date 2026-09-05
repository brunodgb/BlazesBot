"""Os nomes de verdade dos bosses da HH, como a MEMÓRIA os devolve.

`mapa_hh.BOSS_1..BOSS_4` são os RÓTULOS do bot em Lua -- comentários do autor
original, nunca conferidos no jogo. Estes aqui foram medidos no log de produção
de 05/09/2026, e fecham a pendência que `docs/decisoes/hh.md` §9 listava desde
01/09 ("os nomes exatos dos 4 bosses").

O porquê medido, com a tabela de mortos por trecho, está em
`docs/decisoes/hh.md` §14.

=========================================================================
ISTO É EVIDÊNCIA POSITIVA, NUNCA PORTÃO
=========================================================================

O motor mede (`combate.py`, "NÃO EXISTE MAIS CONFERÊNCIA DO ALVO POR NOME") que
o nome não pode BARRAR nada: o campo guarda texto em algumas entidades e
ponteiro em outras. Na HH o lixo foi ~2,6% (`'#994199914'`).

Serve para AFIRMAR ("vi o Fa-Yuan cair, o trecho está feito") e não para NEGAR
("não vi, logo não morreu"). Quem consulta precisa de um caminho alternativo --
na rotina ele é o contrato de POSIÇÃO (`ponto_do_boss.py`).
"""
from __future__ import annotations

from . import mapa_hh

# Nome do rótulo do Lua -> nomes que a memória devolve naquele ponto.
#
# O TRECHO 4 NÃO FOI ALCANÇADO no log, então `Purple` continua só rótulo e não
# entra aqui. A ausência é a decisão: nome não medido viraria portão contra um
# nome que ninguém viu.
NOMES_DOS_BOSSES: dict[str, tuple[str, ...]] = {
    mapa_hh.BOSS_1: ("Fa-Yuan",),
    # A "Dupla" do Lua é literalmente DOIS bosses com nome, o que confirma
    # `ALVOS_POR_PONTO[BOSS_2] = 2`.
    mapa_hh.BOSS_2: ("Zaton", "Callet Head Young"),
    # O rótulo do Lua erra o espaço: "Green Robmaster".
    mapa_hh.BOSS_3: ("Green Robe Master",),
}


def nomes_do_boss(rotulo: str) -> tuple[str, ...]:
    """Os nomes que a memória devolve para o boss deste ponto.

    Tupla vazia = NÃO MEDIDO, e quem chama tem de tratar isso como "não sei",
    nunca como "não é ele".
    """
    return NOMES_DOS_BOSSES.get(rotulo, ())


def medido(rotulo: str) -> bool:
    """Este ponto já teve o nome do boss medido no jogo?"""
    return bool(nomes_do_boss(rotulo))


__all__ = ["NOMES_DOS_BOSSES", "medido", "nomes_do_boss"]
