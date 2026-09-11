"""A rajada de clique direito que PERGUNTA entre um clique e o seguinte.

=========================================================================
O QUE ESTA MEDIÇÃO MOSTROU (11/09/2026, telemetria de 09 e 10/09)
=========================================================================

`Input.right_click` manda `CLIQUES_DIREITOS_POR_TENTATIVA` cliques com
`INTERVALO_ENTRE_CLIQUES_DIREITOS` entre eles, e só DEPOIS alguém pergunta se o
diálogo abriu. Com 10 cliques a 44 ms, isso é **396 ms de espaçamento pago
sempre**, mesmo quando o primeiro clique já resolveu.

Medido em `logs/latencia/latencia.jsonl`:

    Input._click_postmessage_puro ....  2,68 ms  (o clique em si)
    Input.right_click ............... 295,93 ms  (a rajada inteira)
    UIDoJogo._abrir_dialogo_e_clicar  491,26 ms  -- com MÍNIMO de 424,32 ms
    UIDoJogo.dialogo_esta_aberto .....  27,61 ms  (captura + template)

O mínimo de 424 ms é a assinatura do desperdício: NENHUMA conversa com NPC
custou menos que a rajada cega, porque a rajada cega é o piso.

E a rajada é um caminho quente de verdade: 64.076 aberturas de diálogo na
amostra, das quais 61.928 são tentativas de entrada na HH.

=========================================================================
A REGRA DA CASA, APLICADA AO MAIOR CUSTO FIXO DO CAMINHO QUENTE
=========================================================================

*"Onde havia espera cega, agora se PERGUNTA (confira o efeito, saia no
instante). Teto vira aviso, não gasto fixo."* -- `CLAUDE.md`.

Perguntar custa 27,61 ms (uma captura de 3,35 ms e um casamento de template).
Um espaçamento custa 44 ms. **Perguntar é mais barato que esperar**, e ainda
responde -- então o laço aqui clica UMA vez, pergunta, e para no instante em que
o diálogo aparece.

    caso comum (abre no 1º clique) ....  ~30 ms   contra 424 ms
    pior caso (nunca abre) ........... ~743 ms   contra ~420 ms + teto

O PIOR CASO FICOU MAIS CARO, e é aceito: ele acontece em 3,9% das rajadas
(2.473 de 64.076 na amostra), e o tempo a mais é gasto PERGUNTANDO -- que é o
que pega o diálogo que chega atrasado, em vez de dormir até o fim e perguntar
uma vez só.

=========================================================================
`CLIQUES_DIREITOS_POR_TENTATIVA` VIRA TETO, E ISSO É O PONTO
=========================================================================

Com a rajada cega, subir o número custava 44 ms por clique em TODA conversa.
Com a pergunta no meio, o número passa a ser um teto: quem abre no primeiro
clique não paga os outros nove. É a mesma conversão que o projeto já fez em
espera de diálogo, de chegada e de venda.

=========================================================================
AS TRÊS RESPOSTAS, E POR QUE ELAS SÃO AS MESMAS DE `dialogo_esta_aberto`
=========================================================================

    True  -- o diálogo ESTÁ aberto; quem chamou pode clicar no link
    False -- acabaram os cliques e ele NÃO está aberto
    None  -- não dava para perguntar (sem template, sem captura, ou o
             interruptor desligado). O resto da rajada sai CEGO, e quem chamou
             segue exatamente como seguia antes.

`None` é o caso do cliente minimizado, que é modo normal de operação deste bot:
ali `capture_window` devolve quadro preto e nenhum template casa. Recusar a
rajada nesse caso deixaria a entrada impossível -- então ela sai inteira, cega,
como sempre saiu.
"""
from __future__ import annotations

from collections.abc import Callable

from ..core.inputs import (
    CLIQUES_DIREITOS_POR_TENTATIVA,
    INTERVALO_ENTRE_CLIQUES_DIREITOS,
)

# INTERRUPTOR -- desligar devolve a rajada cega de sempre.
#
# `False` manda `ctx.right_click(ponto)` uma vez (que repete internamente) e
# devolve `None`, então quem chama volta a depender só do `_esperar_o_dialogo`
# posterior. É a forma de voltar ao comportamento de antes de 11/09/2026 sem
# apagar nada -- a regra do projeto: interruptor, não comentário.
PERGUNTAR_ENTRE_OS_CLIQUES = True


def clicar_ate_abrir(
    ctx,
    ponto: tuple[int, int],
    esta_aberto: Callable[[], bool | None],
    *,
    cliques: int | None = None,
    intervalo: float | None = None,
) -> bool | None:
    """Clica com o direito até o diálogo abrir. Ver o cabeçalho do módulo.

    `esta_aberto` é a pergunta -- normalmente `UIDoJogo.dialogo_esta_aberto`,
    com as três respostas dele. Recebe a FUNÇÃO e não o resultado: perguntar
    antes de clicar responderia sobre a tela de antes.

    O ESPAÇAMENTO SÓ ENTRE CLIQUES, nunca antes do primeiro: o primeiro é a
    ação, e adiar a ação é o que esta função existe para não fazer.
    """
    quantos = max(1, cliques if cliques is not None else CLIQUES_DIREITOS_POR_TENTATIVA)
    espaco = (intervalo if intervalo is not None
              else INTERVALO_ENTRE_CLIQUES_DIREITOS)

    if not PERGUNTAR_ENTRE_OS_CLIQUES:
        ctx.right_click(ponto)
        return None

    for i in range(quantos):
        if i:
            ctx.tick(espaco)
        # UM clique por vez: `repetir=False`. A repetição é deste laço agora, e
        # quem a controla é a RESPOSTA, não o relógio.
        ctx.right_click(ponto, repetir=False)
        resposta = esta_aberto()
        if resposta is True:
            return True
        if resposta is None:
            _rajada_cega(ctx, ponto, espaco, restantes=quantos - i - 1)
            return None
    return False


def _rajada_cega(ctx, ponto: tuple[int, int], espaco: float,
                 restantes: int) -> None:
    """O resto da rajada, sem perguntar. Só para quando não HÁ o que perguntar.

    Mantém a aposta original intacta no cliente sem captura: a rajada existe
    porque parte dos cliques se perde no cliente ocupado, e essa aposta não
    depende de imagem nenhuma.
    """
    for _ in range(max(0, restantes)):
        ctx.tick(espaco)
        ctx.right_click(ponto, repetir=False)


__all__ = ["PERGUNTAR_ENTRE_OS_CLIQUES", "clicar_ate_abrir"]
