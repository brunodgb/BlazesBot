"""A barra de atalhos tem que estar na PÁGINA 1.

=========================================================================
POR QUE ISTO EXISTE
=========================================================================

O jogo tem três páginas de barra de atalhos, e uma bola verde no meio do
rodapé mostra em qual está: 1, 2 ou 3. As teclas que o usuário configurou no
bot (skills, montaria, pet, poções, inventário) apontam para os slots da
PÁGINA 1. Com a barra em outra página a MESMA tecla dispara outra coisa -- e o
bot não tem como perceber, porque ele aperta a tecla e segue.

=========================================================================
POR QUE CLICAR EM VEZ DE LER
=========================================================================

Dá para LER a página: a bola tem o dígito, e medindo os prints do usuário a
máscara da tinta (os pixels azuis sobre o verde) separa 1, 2 e 3 com folga
grande -- margem de 0,60 a 0,77. Casar a bola INTEIRA não serve: a moldura
dourada domina a correlação e a margem cai para 0,037, que é o mesmo tipo de
margem que produziu falso positivo no `package_courage`.

Mas ler não se paga aqui, e o motivo é uma propriedade do botão: ele SOBE e
PARA no 1. De 3 vai 3→2→1; de 2 vai 2→1→1; no 1 fica no 1. Clicar duas vezes
leva para a página 1 de qualquer lugar, inclusive já estando nela, sem efeito
colateral. Com isso a leitura só serviria para economizar dois cliques -- e
não existiria reconhecimento que pudesse errar.

São dois cliques (~60 ms) contra ~11 ms de leitura, mais três templates, uma
regra de cor e uma margem para dar errado.

O QUE SE PERDE, e vale saber: o log não diz em que página a barra ESTAVA, só
que o bot corrigiu. Se um dia interessar medir a frequência do problema, é só
ler o dígito antes de clicar -- as medições estão aqui em cima.

=========================================================================
DUAS PORTAS, PORQUE O MÓDULO APP É ISOLADO
=========================================================================

O modo APP não recebe `BotContext` de propósito -- é isso que o faz funcionar
justamente quando a leitura de memória não funciona. Então a regra mora em
`subir_para_a_pagina_1`, que só precisa de "uma forma de clicar" e "um ponto":

    garantir_pagina_1(ctx, ...)              -- o farm da cave, com recarga
    ir_para_a_pagina_1(clicar, ponto, ...)   -- qualquer um, inclusive o APP

As duas ASSENTAM antes de devolver (`ASSENTAR_A_PAGINA`), porque quem chama
aperta um slot em seguida -- e a barra troca no quadro seguinte, não no
WndProc.

Assim os dois módulos usam a MESMA regra sem que o APP importe estado do farm.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from ..context import BotContext

# Três páginas: do pior caso (página 3) até a 1 são dois cliques para cima.
CLIQUES_PARA_VOLTAR_A_PAGINA_1 = 2

# Entre um clique e o outro. Curto porque o clique deste bot é SÍNCRONO
# (`SendMessageW`): quando a chamada volta, o cliente já processou a mensagem.
ENTRE_CLIQUES = 0.025

# ===========================================================================
# DEPOIS DE CHEGAR NA PÁGINA 1, ANTES DE DEVOLVER
# ===========================================================================
#
# "O cliente processou a mensagem" NÃO É "a barra já está desenhada na página
# 1". A mensagem é tratada no WndProc; a barra troca no quadro seguinte. Quem
# apertava um slot no mesmo instante apertava contra a página velha.
#
# MEDIDO NO LOG EM 27/08/2026 (`logs/dev/blazes-dev.jsonl`, conta `creubo`, três
# ocorrências idênticas):
#
#     -0.0s  Barra de atalhos na página 1 por tecla (invocar o pet)
#     +0.0s  Alimentando o pet (a cada 56 min)     <- '6' no mesmo instante
#
# Zero milissegundo entre a troca de página e o slot. Os outros consumidores
# sobrevivem a isso porque INSISTEM e CONFEREM (a montaria repete a tecla até a
# memória confirmar, a poção até o HP subir); os dois que apertam UMA vez e
# acreditam -- comida do pet e buffs -- comiam a corrida em silêncio.
#
# O NÚMERO NÃO É MEDIDO AINDA. É o menor valor que ainda é maior que um quadro
# em qualquer máquina razoável (60 fps = 16,7 ms), e é pago no MOMENTO-CHAVE, não
# no laço: `garantir_pagina_1` roda algumas vezes por run.
#
# COMO MEDIR: aperte a página 3, chame `ir_para_a_pagina_1` e leia o dígito da
# bola (o cabeçalho deste módulo tem as máscaras) baixando este valor até o
# dígito voltar a sair errado.
ASSENTAR_A_PAGINA = 0.08

# Recarga do caminho com `ctx`. Os momentos-chave acontecem em rajada -- o portão
# da montaria é chamado uma vez por trajeto, e a manobra de destravamento abre
# até seis trajetos curtos seguidos. Sem recarga isso viraria doze cliques em
# poucos segundos, para um estado que não muda sozinho.
#
# Mesmo desenho (e mesmo valor) do `UIService.resetar_visao`, pela mesma razão.
RECARGA = 5.0

_ultimo_reset: dict[int, float] = {}


def ir_para_a_pagina_1(
    clicar: Callable[[tuple[int, int]], None],
    ponto: tuple[int, int],
    esperar: Callable[[float], None] | None = None,
    apertar: Callable[[str], None] | None = None,
    tecla: str = "",
) -> str:
    """Leva a barra para a página 1. Devolve `"tecla"` ou `"clique"`, para o log.

    DOIS CAMINHOS, e o de tecla é melhor por ir DIRETO ao destino. O clique
    precisa de dois toques justamente porque só sabe subir um degrau por vez
    (3→2→1); a tecla da página 1 é um toque, sempre, de onde quer que esteja.

    O clique continua sendo o padrão porque não depende de configuração: quem
    não tiver a tecla configurada segue com o comportamento medido de sempre.

    Recebe FUNÇÕES em vez de um contexto para poder ser usada pelo modo APP,
    que roda fora do `BotContext` -- é isso que o faz funcionar justamente
    quando a leitura de memória não funciona.
    """
    def _esperar(segundos: float) -> None:
        if esperar is not None:
            esperar(segundos)
        else:
            time.sleep(segundos)

    if tecla and apertar is not None:
        apertar(tecla)
        # ASSENTA ANTES DE DEVOLVER -- ver `ASSENTAR_A_PAGINA`. Sem isto quem
        # aperta um slot logo depois aperta contra a página velha.
        _esperar(ASSENTAR_A_PAGINA)
        return "tecla"

    for i in range(CLIQUES_PARA_VOLTAR_A_PAGINA_1):
        clicar(ponto)
        if i + 1 < CLIQUES_PARA_VOLTAR_A_PAGINA_1:
            _esperar(ENTRE_CLIQUES)
    _esperar(ASSENTAR_A_PAGINA)
    return "clique"


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
