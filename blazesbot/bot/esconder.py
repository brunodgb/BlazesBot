"""Prender o F12 quando a cave começa. Um gesto, nenhuma cerimônia.

===========================================================================
A REGRA, E ELA É CURTA
===========================================================================

Usuário, 10/09/2026: *"a regra é apenas dar um key_down no F12 apenas, sem o
key_up... ao ativar, no momento que eu clicar em BC ou HH, antes de começar a
andar já faz isso"*.

A tecla esconde **enquanto está apertada**, então o bot a aperta e não solta.
`Input.segurar_para_sempre` põe a tecla numa lista de intocáveis, e a partir daí
nenhum `key_up` a solta -- inclusive o de um `segurado(...)` que termine.

===========================================================================
POR QUE ISTO EXISTE, SE O SUPERVISOR JÁ PRENDE A TECLA
===========================================================================

O supervisor prende quando PREPARA O CLIENTE (junto do patch e do pet bug), o
que acontece no login. Mas o usuário liga a cave DEPOIS, e às vezes muito
depois: *"no momento que eu clicar em BC ou HH, antes de começar a andar"*.

E reafirmar é o comportamento correto, não redundância -- é o que a própria
`prender_a_tecla` documenta: uma tecla fisicamente presa repete sozinha, e
reenviar é o que recupera o estado quando o cliente o perdeu (num relogin, por
exemplo, em que a janela é outra).

===========================================================================
O QUE ESTE MÓDULO NÃO FAZ MAIS
===========================================================================

Ele foi criado em 10/09/2026 para promover o TRUQUE DO CHAT do BC (segurar,
abrir o chat com Enter, soltar, fechar) -- e no mesmo dia o usuário mandou
remover o truque: *"só funciona para o usuário, não precisa ser feito pelo bot"*.

Com o truque foram embora a conferência do chat aberto e o template
`state_chat_aberto.png`, que existiam só para proteger dele. Prender a tecla não
abre chat nenhum, então não há o que conferir e não há como o bot passar a
digitar em vez de jogar.

===========================================================================
DEPENDÊNCIA CRUZADA
===========================================================================

  * QUEM USA: `bc/routine.py` e `hh/routine.py`, na largada de cada uma.
  * MORA EM `bot/` porque recebe `BotContext`. O critério é o que o módulo
    IMPORTA, não o quanto ele parece genérico.
  * O QUE **NÃO** SUBIU: nada de cave. Prender o F12 é sobre o cliente do
    Talisman, e QUANDO prender é de quem chama.

Ver `docs/decisoes/hh.md` §31.
"""
from __future__ import annotations

from ..core import esconder_jogadores
from .context import BotContext


class EsconderOsJogadores:
    """A tecla de esconder, presa. Devolve se a tecla chegou a ser mandada."""

    def __init__(self, ctx: BotContext) -> None:
        self.ctx = ctx

    def prender(self, o_que: str) -> bool:
        """KEYDOWN no F12, sem KEYUP. `False` = não havia o que fazer.

        `False` NÃO é falha a tratar: significa interruptor desligado ou tecla
        não configurada, e quem não configurou o esconder simplesmente não usa.
        Por isso ninguém aborta nada por causa desta resposta -- diferente do
        truque antigo, em que `False` queria dizer "o chat pode estar aberto".
        """
        ctx = self.ctx
        preso = esconder_jogadores.prender_a_tecla(
            ctx.settings.keys.hide_players,
            ctx.segurar_para_sempre,
            ctx.log,
        )
        if preso:
            ctx.log.info(
                "Esconder jogadores (%s): tecla %r PRESA (KEYDOWN sem KEYUP) "
                "-- os outros personagens somem e ficam sumidos.",
                o_que, ctx.settings.keys.hide_players)
        return preso


__all__ = ["EsconderOsJogadores"]
