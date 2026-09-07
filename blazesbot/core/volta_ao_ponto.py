"""VOLTAR AO PONTO: a ordem de andar pelo minimapa, e a régua do "já cheguei".

Promovido para o `core/` em 07/09/2026, quando a **Fada** passou a precisar da
mesma coisa que o APP já fazia: *"a fada deve voltar ao ponto inicial para
evitar zonas de risco"* (usuário).

O que mora aqui é só a MECÂNICA, e ela é a mesma para quem quer que ande:
converter a coordenada do destino em pixel do minimapa a partir de onde o
personagem está, e mandar UM clique direito. A POLÍTICA -- de quanto em quanto
tempo perguntar, quando é seguro andar, o que fazer se não chegar -- fica com
quem chama, porque ali ela é diferente: o APP não anda em batalha, a Fada não
anda com alguém na fila de cura.

CLIQUE ÚNICO, e isso não é economia: no minimapa cada clique é uma ordem
calculada da posição ATUAL. Repetir com o pixel velho manda o personagem para um
lugar que já não é o destino.
"""

from __future__ import annotations

from .zones import coord_para_pixel_do_minimapa, distancia_linear

# Quanto o personagem pode estar fora do ponto e ainda contar como "chegou".
#
# É o número que o APP já usava (`executor.TOLERANCIA_POSICAO`, medido em campo:
# 28 correções em 7 h de farm, nenhuma com o personagem parado no lugar certo).
# Ele mora aqui agora porque passou a ser lido por dois lados -- e número lido
# por dois lados mora num lugar só.
#
# UM, e não zero: a coordenada do jogo oscila em ±1 sem o personagem andar, e
# com tolerância zero a trava mandaria clique a cada leitura.
TOLERANCIA = 1


def cheguei(pos_atual: tuple[int, int] | None,
            destino: tuple[int, int] | None,
            tolerancia: int = TOLERANCIA) -> bool | None:
    """`True` = estou no ponto. `None` = não dá para saber.

    As três respostas são distintas de propósito: quem chama usa `None` para
    NÃO agir, e tratá-lo como `False` faria o bot andar às cegas.
    """
    if pos_atual is None or destino is None:
        return None
    return distancia_linear(pos_atual, destino) <= tolerancia


def mandar_andar(pos_atual: tuple[int, int] | None,
                 destino: tuple[int, int] | None,
                 centro_do_minimapa: tuple[int, int] | None,
                 clicar_direito) -> bool:
    """Manda o personagem andar até `destino`. `False` = não havia como.

    `clicar_direito(x, y)` é injetado -- este módulo não sabe o que é janela nem
    o que é `Input`, e continua assim.
    """
    if pos_atual is None or destino is None or centro_do_minimapa is None:
        return False
    pixel = coord_para_pixel_do_minimapa(pos_atual, destino, centro_do_minimapa)
    clicar_direito(pixel[0], pixel[1])
    return True
