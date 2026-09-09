"""A COLEIRA: MEDIÇÃO. Ela não veta mais alvo -- e isso custou uma conta.

*"Tem vezes que o jogo dá bug e dá target em um mob bem longe, só que com isso
acaba chamando outros mobs e provavelmente vai morrer no caminho."*
-- usuário, 04/09/2026.

=======================================================================
TRÊS VERSÕES, TRÊS DEFEITOS, E A LIÇÃO QUE FICOU
=======================================================================

**1ª -- media o PERSONAGEM contra a base, no meio da macro.** Cortava a volta a
cada linha longe do ponto, contando que a trava de posição andasse de volta. A
trava não anda em batalha: travamento PERMANENTE, o personagem parado apanhando
até morrer.

**2ª -- media o MOB contra a base, na aquisição.** Com o personagem deslocado,
TODO mob perto dele fica longe da base: 3179 recusas contra 52 macros iniciadas
em uma hora, o bot girando TAB sem atacar.

**3ª -- media o MOB contra o PERSONAGEM, na aquisição.** A régua certa, e ainda
assim fatal. **O TAB do jogo entrega o mob mais PRÓXIMO primeiro e vai afastando
a cada toque.** Recusar o primeiro empurra a seleção para fora: recusa, TAB, mob
mais longe, recusa, TAB, mob mais longe ainda -- até aceitar um mob distante,
correr até ele e chegar com meia dúzia de outros atrás. Relato do usuário em
06/09/2026: *"o primeiro TAB já adquire um alvo válido e perfeitamente
posicionado, mas o código ignora e continua dando TAB (...) a conta BlazesAPP1
acabou de morrer por causa disso"*.

**A LIÇÃO:** a régua estava brigando com a única coisa que o jogo já fazia
certo. O primeiro alvo vivo que o TAB traz é, por construção, o mais perto que
existe. **Não há alvo melhor a procurar, e procurar é o próprio dano.**

O que sobrou aqui é o DADO: quanto o personagem correu, e a que distância do
ponto o mob estava. É dele que sai o número certo, se um dia houver régua de
novo -- e a régua de então não pode ser feita de recusa, porque recusa custa um
TAB e um TAB custa distância.

O *"não andar longe do ponto"* continua com quem sempre foi dono dele: a **trava
de posição**, que devolve o personagem ao ponto quando a luta acaba, sem gastar
TAB nenhum.
"""

from __future__ import annotations

import logging

from . import diagnostico_fino
from .zones import distancia_linear

# ===========================================================================
# O PERÍMETRO -- a QUARTA versão da coleira, e a primeira que anda de volta
# ===========================================================================
#
# *"Se a diferença de distância para as coordenadas do Ponto Inicial for MAIOR
# QUE 12 unidades, um alarme de perímetro é acionado (...) aborta
# IMEDIATAMENTE qualquer ataque, macro ou espera, força a caminhada de volta
# para o Ponto Inicial exato"* -- usuário, 09/09/2026.
#
# LEIA O TOPO DESTE ARQUIVO ANTES DE MEXER AQUI. A 1ª versão media exatamente
# isto -- o PERSONAGEM contra a base, no meio da macro -- e matou personagens.
# O defeito NÃO era a medição: era o CORTE SEM RETORNO. Ela cortava a volta e
# delegava a caminhada à trava de posição, que se recusa a andar em batalha --
# então o personagem ficava parado apanhando, para sempre.
#
# O QUE MUDA NESTA VERSÃO, e é tudo:
#
#   1. QUEM CORTA, ANDA. O recolhimento é a mesma rotina: corta, caminha,
#      confirma a chegada, limpa o estado e TABa. Não delega para ninguém.
#   2. ANDA EM BATALHA. É a exceção deliberada a `ANDAR_SO_FORA_DE_BATALHA`:
#      arrastar um mob de volta ao ponto é ruim, ficar a 20 unidades brigando
#      com o trem que veio junto é pior.
#   3. TEM TETO E TEM DESISTÊNCIA. Não chegou no teto, tenta de novo; não
#      chegou três vezes, PARA de tentar por um tempo e volta a lutar onde
#      está. É o que impede o travamento permanente da 1ª versão de voltar.
#
# E ELA NÃO RECUSA ALVO -- nada aqui gasta TAB para escolher mob. Foi a recusa
# que matou a 2ª e a 3ª versão.
#
# DOZE, e o número é do usuário. Não é arredondamento de medição: é o raio de
# farm que ele considera seguro no spot dele. Abaixo disso o dono é a trava de
# posição, com tolerância 1.
RAIO_DO_PERIMETRO = 12


def estourou_o_perimetro(
        pos_atual: tuple[int, int] | None,
        base: tuple[int, int] | None,
        raio: float = RAIO_DO_PERIMETRO) -> float | None:
    """A distância, se ela passou do raio. `None` = dentro, ou não sei.

    `None` PARA "NÃO SEI" é o lado seguro: sem leitura de posição não se
    interrompe macro nem se manda ninguém andar. Inventar deslocamento a partir
    de leitura falha faria o bot recolher-se para um ponto que talvez nem seja o
    lugar onde ele está.
    """
    if pos_atual is None or base is None:
        return None
    distancia = distancia_linear(pos_atual, base)
    return distancia if distancia > raio else None

# NÃO HÁ MAIS TETO, E ISSO É O CONSERTO.
#
# Os números que existiam aqui (`MAXIMO_DE_PASSOS_ATE_O_MOB`,
# `RECUSAS_ANTES_DE_ACEITAR`) foram removidos junto com a recusa que eles
# governavam. Deixá-los como "constante morta" seria convite para alguém
# religar a régua sem ler a cicatriz no topo deste arquivo.
#
# Se um dia houver régua de novo, ela NÃO pode ser feita de recusa: recusar
# custa um TAB, e cada TAB afasta a seleção. Teria de ser uma pergunta feita
# ANTES do TAB -- por exemplo, varrer `entidades_vivas()` e só TABar quando
# houver mob ao alcance.

def medir(alvo: dict, base: tuple[int, int] | None, log: logging.Logger,
          pos_do_personagem: tuple[int, int] | None = None) -> None:
    """Anota a corrida e a distância até a base. SÓ MEDE -- ver o topo.

    Ficou sendo o único trabalho deste módulo depois do HOTFIX de 06/09/2026: a
    régua vetou alvo duas vezes e as duas mataram conta. O dado continua valendo
    ouro -- é dele que sai o número certo, se um dia houver régua de novo.
    """
    pos = alvo.get("pos")
    if pos is None or pos_do_personagem is None:
        return
    corrida = distancia_linear(pos, pos_do_personagem)
    ate_a_base = None if base is None else distancia_linear(pos, base)
    diagnostico_fino.anotar(
        log, "ALVO ACEITO %r id=%s hp=%s/%s | corrida=%.0f | mob->base=%s",
        alvo.get("nome") or "?", alvo.get("id"), alvo.get("hp"),
        alvo.get("max_hp"), corrida,
        "?" if ate_a_base is None else f"{ate_a_base:.0f}")
