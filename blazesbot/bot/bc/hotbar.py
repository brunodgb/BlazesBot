"""A barra de atalhos na PÁGINA 1, do lado do farm da cave.

A REGRA em si mora em `core/hotbar.py` -- ela é sobre o JOGO, e o modo APP
precisa dela tanto quanto o farm. Aqui fica só o que depende de `BotContext`:
a recarga e a leitura da tecla configurada.

=========================================================================
DUAS PORTAS, PORQUE O MÓDULO APP É ISOLADO
=========================================================================

O modo APP não recebe `BotContext` de propósito -- é isso que o faz funcionar
justamente quando a leitura de memória não funciona. Então a regra só precisa
de "uma forma de clicar" e "um ponto":

    garantir_pagina_1(ctx, ...)              -- o farm da cave, com recarga
    core.hotbar.ir_para_a_pagina_1(...)      -- qualquer um, inclusive o APP

As duas ASSENTAM antes de devolver (`ASSENTAR_A_PAGINA`), porque quem chama
aperta um slot em seguida -- e a barra troca no quadro seguinte, não no
WndProc.

Assim os dois módulos usam a MESMA regra sem que o APP importe estado do farm.
Os nomes do `core` continuam visíveis por aqui (`hotbar.ASSENTAR_A_PAGINA`,
`hotbar.ir_para_a_pagina_1`) porque `combat.py` e os testes já citavam este
módulo -- a mudança de casa não é razão para quebrar quem chama.
"""
from __future__ import annotations

import time

from ...core.hotbar import (
    ASSENTAR_A_PAGINA,
    CLIQUES_PARA_VOLTAR_A_PAGINA_1,
    ENTRE_CLIQUES,
    ir_para_a_pagina_1,
)
from ..context import BotContext

__all__ = [
    "ASSENTAR_A_PAGINA",
    "CLIQUES_PARA_VOLTAR_A_PAGINA_1",
    "ENTRE_CLIQUES",
    "RECARGA",
    "garantir_pagina_1",
    "ir_para_a_pagina_1",
]

# Recarga do caminho com `ctx`. Os momentos-chave acontecem em rajada -- o portão
# da montaria é chamado uma vez por trajeto, e a manobra de destravamento abre
# até seis trajetos curtos seguidos. Sem recarga isso viraria doze cliques em
# poucos segundos, para um estado que não muda sozinho.
#
# Fica AQUI e não no `core` porque é estado do farm: o APP chama a regra uma vez
# por volta, não em rajada, e não tem `hwnd` de contexto para indexar.
#
# Mesmo desenho (e mesmo valor) do `UIService.resetar_visao`, pela mesma razão.
RECARGA = 5.0

_ultimo_reset: dict[int, float] = {}


def garantir_pagina_1(ctx: BotContext, motivo: str = "",
                      forcar: bool = False) -> None:
    """Leva a barra de atalhos para a página 1. Nunca falha, nunca bloqueia.

    `forcar=True` ignora a recarga, e é o que os dois pontos de LUTA usam: ali
    uma tecla na página errada custa a run, então não se economiza clique.

    Não devolve nada de propósito. Não há o que decidir com o resultado: o
    clique é seguro em qualquer página, e o passo seguinte acontece de todo
    jeito.
    """
    tecla = getattr(ctx.settings.keys, "hotbar_page_1", "") or ""

    # A RECARGA SÓ VALE PARA O CLIQUE. Ela existe porque os momentos-chave
    # acontecem em rajada e dois cliques repetidos custam tempo e ruído. Um
    # toque de tecla não tem esse custo -- e pagar por ele com o risco de a
    # barra ficar na página errada seria trocar o barato pelo caro.
    if not tecla:
        agora = time.time()
        if not forcar and agora - _ultimo_reset.get(ctx.hwnd, 0.0) < RECARGA:
            return
        _ultimo_reset[ctx.hwnd] = agora

    como = ir_para_a_pagina_1(
        ctx.click, ctx.coords.hotbar_page_up, ctx.tick, ctx.press, tecla)
    ctx.log.debug("Barra de atalhos na página 1 por %s (%s)",
                  como, motivo or "rotina")
