"""O motor de combate da HH: o de `bot/combate.py` que SABE ONDE FICA A CAVE.

===========================================================================
POR QUE ESTE ARQUIVO EXISTE
===========================================================================

`CombatEngine._preparar_para_agir` tem um veto desde 25/08/2026 -- regra do
usuário: *"fora da cave BC ele só vai sair da mount caso o pet não esteja
ativo; de resto, alimentar o PET, usar qualquer coisa que dependa tirar a
montaria vai ser feito naquele momento que entra na cave"*.

Esse veto pergunta `self._esta_fora_da_cave()`, e o motor responde `False`
("não sei") de propósito: **cada cave responde com a caixa dela**. A BC
respondia desde sempre (`bc/combat.CombateBC`). **A HH nunca respondeu** -- ela
usava o motor cru, então em toda a rotina de fora da cave o veto perguntava,
ouvia "não sei", e deixava passar.

Consequência medida no log de 11/09/2026: 17 desmontes na porta da cave, todos
logo depois da venda, cada um custando descer, invocar e subir de novo.

Relato do usuário em 13/09/2026:

> *"ao lado de fora da cave HH tem vezes que está saindo da montaria, mas no
> geral não deve sair, eu tenho notado principalmente depois de vender os itens
> acaba sendo pressionado o botão da montaria e ele desce... nem 3/4 segundos
> depois é ativo a montaria novamente"*

Os 3 a 4 segundos são exatamente o que o log mede: desmonte às 08:47:36,2 e
`Pet ativo` às 08:47:40,4.

===========================================================================
DEPENDÊNCIA CRUZADA
===========================================================================

  * QUEM USA: `hh/routine.py`, no lugar do `CombatEngine` cru.
  * ESPELHO de `bc/combat.py`, que faz a mesma coisa com a caixa da BC. As duas
    caves respondem a mesma pergunta com o mapa delas, e é só isso que este
    arquivo acrescenta ao motor.
  * O QUE **NÃO** SUBIU: nada. A regra do veto já mora no motor; o que faltava
    aqui era a HH dizer onde fica a cave dela.
"""
from __future__ import annotations

from ..combate import CombatEngine

# ===========================================================================
# A PROVA DE ESTAR FORA DA HH
# ===========================================================================
#
# É o outro lado de `mapa_hh.esta_dentro_da_hh`, e a regra é a mesma -- a do
# SINAL DA COORDENADA, que o bot em Lua usa em três lugares do `farmer.lua`:
# dentro da cave X e Y são positivos; fora (a porta em (-342,-288), o vendedor
# em (-343,-294)) os dois são negativos.
#
# MAS NÃO É A NEGAÇÃO DELA, e a diferença é o ponto: `not esta_dentro_da_hh(pos)`
# devolve True para `pos is None`, ou seja transformaria "não consegui ler" em
# "provei que está fora". Aqui `None` responde False, porque "não sei" não é
# "não está" -- exatamente como `mapa_bc.posicao_esta_fora_da_cave` documenta.
#
# E A DIREÇÃO DO ERRO É ESCOLHIDA: sem leitura o veto não se aplica e a ação
# passa. Um desmonte a mais fora da cave custa segundos; um buff que não sai
# dentro dela custa a run.
#
# MORA AQUI E NÃO EM `mapa_hh` porque tem UM leitor só, o método abaixo -- e
# `mapa_hh` está encostado na catraca de tamanho.


def posicao_esta_fora_da_hh(pos: tuple[int, int] | None) -> bool:
    """A coordenada AFIRMA que o personagem não está na instância da HH."""
    if pos is None:
        return False
    return pos[0] < 0 and pos[1] < 0


class CombateHH(CombatEngine):
    """O motor de `bot/combate.py` mais a caixa desta cave."""

    def _esta_fora_da_cave(self) -> bool:
        """A coordenada da HH responde. Ver o motor para o padrão."""
        return posicao_esta_fora_da_hh(self.ctx.memory.position())


__all__ = ["CombateHH", "posicao_esta_fora_da_hh"]
