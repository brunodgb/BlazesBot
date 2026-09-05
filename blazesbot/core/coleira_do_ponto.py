"""A COLEIRA DOS 12: um mob longe do ponto inicial não vale a corrida.

*"Tem vezes que o jogo dá bug e dá target em um mob bem longe, só que com isso
acaba chamando outros mobs e provavelmente vai morrer no caminho (...) essa
limitação é muito importante para não acabar puxando vários mobs ao mesmo tempo
por andar para muito longe."* -- usuário, 04/09/2026.

=======================================================================
POR QUE A REGRA MORA NA AQUISIÇÃO, E NÃO NO MEIO DA MACRO
=======================================================================

A primeira versão desta regra cortava a volta a cada linha em que o PERSONAGEM
estivesse longe do ponto, contando que a trava de posição andasse de volta no
prelúdio da volta seguinte. **Ela não anda:** `_travar_posicao_se_preciso` sai na
hora quando `_lutando()` diz que sim, e `_lutando()` diz que sim para qualquer
alvo vivo selecionado.

O resultado, medido em campo, era um travamento PERMANENTE: nenhuma tecla saía,
então o mob não podia morrer; a trava não andava, então o personagem não podia
voltar. Ele ficava parado levando dano até morrer -- exatamente o *"personagem
tem ficado parado sem atacar"* relatado no mesmo dia.

Aqui a distância medida é a do MOB até a base, e é isso que faz a regra
funcionar sem travar nada: o mob longe é recusado ANTES de o personagem correr
até ele, que é o único instante em que dá para evitar a caminhada. Depois de
engajado vale a regra do usuário, que é mais forte: *"em batalha o personagem
precisa estar atacando e para isso a macro tem que rodar"*.

Se o alvo não serve, o TAB busca outro. Se nenhum servir, a válvula aceita o que
vier -- porque bot mudo é pior que o defeito.
"""

from __future__ import annotations

import logging

from .zones import distancia_linear

# Quão longe do ponto inicial um mob pode estar para valer o engajamento.
#
# NÃO É A MESMA COISA QUE `TOLERANCIA_POSICAO` (1). Aquela é a folga do "já
# voltei" -- de quanto o personagem pode estar fora do ponto para a trava de
# posição considerar que chegou. Esta é o ALCANCE DE CAÇA em volta do ponto, e é
# maior de propósito.
#
# Medido no log de 03->04/09/2026: em 7 h de APP a trava de posição só corrigiu
# 28 vezes e a maior distância registrada foi 10,0. O teto de 12 fica ACIMA do
# que o farm normal produz -- ele recusa a anomalia, não a rotina.
MAXIMO_DE_PIXELS_DO_PONTO = 12

# Quantos mobs longe demais podem ser recusados numa MESMA rodada de aquisição
# antes de o bot aceitar o que vier.
#
# É a válvula contra o defeito que a própria coleira quase criou: se TODOS os
# mobs em volta estiverem fora do teto (o personagem foi arrastado, a base foi
# salva no lugar errado, o spot esvaziou), recusar sem limite deixaria a conta
# sem atacar nada. Passadas as recusas, o alvo longe é aceito e a volta segue
# como antes de a coleira existir: luta onde deu, e a trava de posição devolve o
# personagem quando a luta acabar.
RECUSAS_POR_DISTANCIA = 3


def longe_demais(alvo: dict, base: tuple[int, int] | None, recusas_ja_feitas: int,
                 log: logging.Logger) -> bool:
    """Este mob deve ser recusado por estar longe do ponto? `True` = recuse.

    `base` é o ponto inicial da conta, ou `None` quando não há um (trava de
    posição desligada, base ainda não salva). SEM BASE NÃO HÁ RECUSA: a pergunta
    não tem resposta, e "não sei" nunca bloqueia -- é a mesma regra da
    conferência de janela antes de enviar tecla.

    `recusas_ja_feitas` é o contador DESTA rodada de aquisição; quem chama o
    incrementa quando esta função devolve `True`.
    """
    if base is None:
        return False
    pos = alvo.get("pos")
    if pos is None:
        return False
    distancia = distancia_linear(pos, base)
    if distancia <= MAXIMO_DE_PIXELS_DO_PONTO:
        return False
    if recusas_ja_feitas >= RECUSAS_POR_DISTANCIA:
        log.info("APP: %r está a %.0f do ponto (teto %d), mas já recusei %d por "
                 "distância nesta rodada — aceito e luto onde der.",
                 alvo.get("nome") or "?", distancia, MAXIMO_DE_PIXELS_DO_PONTO,
                 recusas_ja_feitas)
        return False
    log.info("APP: recuso %r — está a %.0f do ponto inicial (teto %d). Correr "
             "até lá puxaria mob pelo caminho; procuro outro.",
             alvo.get("nome") or "?", distancia, MAXIMO_DE_PIXELS_DO_PONTO)
    return True
