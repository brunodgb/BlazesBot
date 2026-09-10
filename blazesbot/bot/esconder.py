"""O truque do F12 aplicado NO JOGO: esconder os outros jogadores de verdade.

===========================================================================
DEPENDÊNCIA CRUZADA -- LEIA ANTES DE MEXER
===========================================================================

Este módulo NASCEU NO BC, como `BossRushRoutine._esconder_jogadores` e
`._chat_aberto`, e subiu para `bot/` em 10/09/2026 quando o usuário pediu o
esconder ligado desde o começo em TODA cave:

> *"em HH o esconder personagem tem que ser ativo já quando começa a função,
> pois está aparecendo outros personagens e pode atrapalhar... toda cave na
> verdade tem que fazer isso, pois assim garante que outros player não irão
> atrapalhar de forma alguma"*

  * QUEM USA: `bc/routine.py` e `hh/routine.py`. Mexer aqui mexe nas duas caves.
  * DE ONDE VEIO: `bc/routine.py`, com as duas constantes de template.
  * O QUE **NÃO** SUBIU: o truque do chat em si, que já morava em
    `core/esconder_jogadores.py` e não conhece `BotContext`. Aqui só se junta o
    contexto (teclas, captura, templates, log) ao gesto que já existia.
  * MORA EM `bot/` E NÃO EM `core/` porque recebe `BotContext`. O critério é o
    que o módulo IMPORTA, não o quanto ele parece genérico.
  * NÃO FOI PARA `UIDoJogo`, que seria o vizinho natural, por um motivo
    mecânico: aquele arquivo está a 4 linhas do teto de linhas da catraca.

===========================================================================
POR QUE ISTO É SOBRE O JOGO, E NÃO SOBRE A CAVE
===========================================================================

O critério do projeto é uma pergunta: *isso é sobre o JOGO ou sobre o que este
ecossistema faz?* Esconder jogadores é sobre o cliente do Talisman -- a mesma
tecla, o mesmo truque, o mesmo perigo do chat aberto em qualquer lugar do mundo.
O que é de cave é apenas QUANDO chamar.

===========================================================================
O PERIGO, E POR QUE ELE MANDA NO DESENHO
===========================================================================

A sequência abre o chat de propósito (é o que faz o esconder grudar) e depois o
fecha. **Se o segundo Enter não pegar, o chat fica aberto** -- e daí em diante
toda tecla do bot (skill, poção, montaria, TAB) vai para o campo de texto. O bot
parece rodando e não faz nada, e um Enter posterior PUBLICA aquilo no chat.

Por isso `garantir` devolve um booleano que quem chama tem de respeitar, e por
isso a conferência do chat responde `None` quando não dá para saber: Enter
ALTERNA o chat, então apertar "por garantia" tem metade de chance de abrir o que
se queria fechar.

Ver `docs/decisoes/hh.md` §28.
"""
from __future__ import annotations

from ..core import esconder_jogadores
from ..core.vision import capture_window, find_template, frame_is_blank
from .context import BotContext

# A carinha do chat de digitação aberto.
TEMPLATE_CHAT_ABERTO = "state_chat_aberto.png"

# Limiar do casamento do chat aberto. Alto de propósito: um falso positivo aqui
# faz o bot achar que o chat está aberto e apertar Enter -- que é justamente o
# que ABRE o chat quando ele estava fechado.
LIMIAR_DO_CHAT_ABERTO = 0.90


class EsconderOsJogadores:
    """O truque do F12, com o contexto do bot em volta."""

    def __init__(self, ctx: BotContext) -> None:
        self.ctx = ctx

    def chat_aberto(self) -> bool | None:
        """O chat de digitação está aberto? `None` quando não dá para saber.

        `None` NÃO é "fechado". Quem chama usa isso para decidir não apertar
        Enter no escuro -- Enter ALTERNA o chat, então um aperto por garantia
        tem metade de chance de ABRIR o que se queria fechar.
        """
        ctx = self.ctx
        template = ctx.templates.load(TEMPLATE_CHAT_ABERTO)
        if template is None:
            ctx.log.warning("Template %s não encontrado", TEMPLATE_CHAT_ABERTO)
            return None
        quadro = capture_window(ctx.hwnd)
        if quadro is None or frame_is_blank(quadro):
            return None
        return find_template(quadro, template,
                             threshold=LIMIAR_DO_CHAT_ABERTO) is not None

    def garantir(self, o_que: str) -> bool:
        """Faz o truque do F12. `True` = seguro seguir jogando.

        `False` significa **chat possivelmente aberto**, e quem chama tem de
        parar o que ia fazer: seguir dali manda toda tecla para o campo de
        texto.

        RODA QUANTAS VEZES FOR CHAMADO, de propósito. O grude vale para a
        sessão, e apertar a tecla de novo o desfaz -- inclusive sem querer, com
        a pessoa usando a mesma máquina. Custa quatro teclas.
        """
        ctx = self.ctx
        resultado = esconder_jogadores.esconder_jogadores(
            tecla=ctx.settings.keys.hide_players,
            segurar=ctx.key_down,
            soltar=ctx.key_up,
            apertar=lambda tecla: ctx.press(tecla),
            chat_aberto=self.chat_aberto,
            esperar=ctx.tick,
            log=ctx.log,
        )
        if resultado.seguro_para_seguir:
            # Só anuncia o que ACONTECEU. Com o interruptor desligado ou sem
            # tecla configurada, uma linha por chamada seria ruído a cada run.
            if resultado.escondeu:
                ctx.log.info("Esconder jogadores (%s): %s", o_que, resultado)
            else:
                ctx.log.debug("Esconder jogadores (%s): %s", o_que, resultado)
            return True
        ctx.log.error(
            "PARANDO %s: %s. Seguir com o chat aberto desvia TODA tecla do bot "
            "para o campo de texto -- a run morreria em silêncio, e um Enter "
            "depois publicaria aquilo no chat do jogo.", o_que, resultado,
        )
        return False


__all__ = ["LIMIAR_DO_CHAT_ABERTO", "TEMPLATE_CHAT_ABERTO",
           "EsconderOsJogadores"]
