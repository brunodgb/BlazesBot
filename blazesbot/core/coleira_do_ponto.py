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
