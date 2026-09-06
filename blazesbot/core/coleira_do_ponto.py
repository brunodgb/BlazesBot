"""A COLEIRA: um mob longe DO PERSONAGEM não vale a corrida.

*"Tem vezes que o jogo dá bug e dá target em um mob bem longe, só que com isso
acaba chamando outros mobs e provavelmente vai morrer no caminho (...) essa
limitação é muito importante para não acabar puxando vários mobs ao mesmo tempo
por andar para muito longe."* -- usuário, 04/09/2026.

=======================================================================
DUAS VERSÕES ERRADAS ANTES DESTA, E O QUE CADA UMA ENSINOU
=======================================================================

**1ª (04/09, manhã) -- media o PERSONAGEM contra a base, no meio da macro.**
Cortava a volta a cada linha em que o personagem estivesse longe do ponto,
contando que a trava de posição andasse de volta. A trava não anda em batalha, e
`_lutando()` responde "sim" para qualquer alvo vivo selecionado: travamento
PERMANENTE, o personagem parado apanhando até morrer.

**2ª (04/09, tarde) -- media o MOB contra a base, na aquisição.**
Consertou o travamento e criou outro, mais silencioso: quando o personagem está
deslocado, TODO mob perto dele está longe da base, então nada era aceitável.
Medido em 05/09: **3179 recusas**, mediana de 113 de distância, contra 52 macros
iniciadas em uma hora. O bot ficava girando TAB sem atacar, e como nenhuma volta
completava, a limpeza de bolsa entrava em rajada.

**3ª (esta) -- mede o MOB contra o PERSONAGEM.**
É a distância que o usuário sempre descreveu: **a corrida**. É ela que puxa mob
pelo caminho, e é a única que responde a mesma coisa esteja o personagem no
ponto ou deslocado.

O "não andar mais de N do ponto" continua existindo e continua sendo trabalho de
quem sempre foi dono dele: a **trava de posição** (`travar_posicao`), que devolve
o personagem ao ponto quando a luta acaba. Uma régua para cada pergunta.

=======================================================================
A VÁLVULA NÃO PODE SER INALCANÇÁVEL
=======================================================================

A 2ª versão trazia uma válvula ("recusou demais? aceite o que vier") que **nunca
disparou**: 1 aceite em 3179 recusas. O motivo é aritmético -- `TENTATIVAS_DE_TAB`
é 1, então cada rodada de aquisição fazia no máximo UMA recusa, e o contador era
zerado no começo da rodada seguinte. Um limiar de 3 nunca é alcançado somando de
um em um e zerando a cada vez.

Agora o contador é de RECUSAS SEGUIDAS, atravessa rodadas, e só zera quando
aparece um mob DE VERDADE ao alcance -- não no aceite da própria válvula, que
seria o mesmo defeito com outra roupa (recusa, recusa, recusa, aceita, zera,
recusa de novo). Com isso a válvula abre em três TABs, cerca de dois segundos, e
a promessa passa a ser verdadeira: **nada aqui pode deixar o bot sem atacar.**
"""

from __future__ import annotations

import logging

from . import diagnostico_fino
from .zones import distancia_linear

# Quão longe do PERSONAGEM um mob pode estar para valer a corrida até ele.
#
# PROVISÓRIO, E DECLARADO COMO TAL. O 12 da versão anterior era distância até a
# base; esta régua mede outra coisa, e o valor certo depende do spot -- não há
# medição dele ainda, porque o log só passou a registrar `mob->personagem` em
# 06/09/2026 (ver `diagnostico_fino`).
#
# 30 foi escolhido para ser CLARAMENTE maior que o engajamento normal e ainda
# assim recusar a anomalia: no log de 05/09, com o personagem no ponto, os mobs
# do spot apareciam entre 12 e 26 de distância, enquanto o caso que o usuário
# quer evitar ("o jogo dá target num mob bem longe") aparecia em 113 na mediana
# e 174 no p90.
#
# QUANDO HOUVER MEDIÇÃO, TROQUE ESTE NÚMERO -- e a válvula abaixo garante que,
# mesmo errado, ele não pode deixar a conta sem atacar.
MAXIMO_DE_PASSOS_ATE_O_MOB = 30

# Recusas SEGUIDAS antes de a válvula abrir e aceitar o que vier.
#
# SEGUIDAS, e não "por rodada": ver o bloco sobre a válvula no topo. Zera quando
# um alvo é aceito, não quando a rodada acaba. Três recusas são três TABs, cerca
# de dois segundos -- rápido o bastante para não custar farm e lento o bastante
# para o teto ainda significar alguma coisa.
RECUSAS_ANTES_DE_ACEITAR = 3

# Nome antigo, mantido porque o índice de constantes e a documentação o citam.
MAXIMO_DE_PIXELS_DO_PONTO = MAXIMO_DE_PASSOS_ATE_O_MOB
RECUSAS_POR_DISTANCIA = RECUSAS_ANTES_DE_ACEITAR


# Os três vereditos. São três e não dois porque "aceito" tem duas causas com
# consequências opostas no contador de recusas -- ver `avaliar`.
PERTO = "perto"                 # dentro do teto (ou sem como medir)
RECUSAR = "recusar"             # longe, e ainda vale procurar outro
PELA_VALVULA = "pela_valvula"   # longe, mas já recusei demais: aceito


def avaliar(alvo: dict, base: tuple[int, int] | None, recusas_seguidas: int,
            log: logging.Logger,
            pos_do_personagem: tuple[int, int] | None = None) -> str:
    """`PERTO`, `RECUSAR` ou `PELA_VALVULA`.

    POR QUE TRÊS RESPOSTAS E NÃO DUAS
    =================================

    A primeira versão desta válvula devolvia só "aceite" e o contador zerava em
    qualquer aceite -- inclusive no da própria válvula. Resultado: recusa,
    recusa, recusa, aceita, **zera**, recusa de novo. Um mob longe era aceito a
    cada quatro tentativas, e nas outras três o bot ficava girando TAB.

    Separando as duas causas, o contador só zera quando aparece um mob DE
    VERDADE ao alcance -- que é a única evidência de que a régua voltou a fazer
    sentido naquele lugar.

    `pos_do_personagem` é de onde a corrida começaria. **Sem ela não há recusa**:
    a pergunta não tem resposta, e "não sei" nunca bloqueia -- é a mesma regra da
    conferência de janela antes de enviar tecla.

    `base` entra só no LOG, para a medição do spot continuar saindo (é ela que
    diz se o personagem está deslocado). Ela não decide mais nada aqui.

    `recusas_seguidas` é o contador que atravessa rodadas; quem chama o
    incrementa em `RECUSAR` e o zera em `PERTO` -- nunca em `PELA_VALVULA`.
    """
    pos = alvo.get("pos")
    if pos is None or pos_do_personagem is None:
        return PERTO

    corrida = distancia_linear(pos, pos_do_personagem)
    ate_a_base = None if base is None else distancia_linear(pos, base)
    diagnostico_fino.anotar(
        log, "ALVO %r id=%s hp=%s/%s | corrida=%.0f (teto %d) | mob->base=%s | "
        "recusas seguidas=%d",
        alvo.get("nome") or "?", alvo.get("id"), alvo.get("hp"),
        alvo.get("max_hp"), corrida, MAXIMO_DE_PASSOS_ATE_O_MOB,
        "?" if ate_a_base is None else f"{ate_a_base:.0f}", recusas_seguidas)

    if corrida <= MAXIMO_DE_PASSOS_ATE_O_MOB:
        return PERTO
    if recusas_seguidas >= RECUSAS_ANTES_DE_ACEITAR:
        log.info(
            "APP: %r está a %.0f de mim (teto %d), mas já recusei %d seguidos "
            "— aceito e luto onde der.",
            alvo.get("nome") or "?", corrida, MAXIMO_DE_PASSOS_ATE_O_MOB,
            recusas_seguidas)
        return PELA_VALVULA
    log.info(
        "APP: recuso %r — está a %.0f de mim (teto %d). Correr até lá puxaria "
        "mob pelo caminho; procuro outro.",
        alvo.get("nome") or "?", corrida, MAXIMO_DE_PASSOS_ATE_O_MOB)
    return RECUSAR
