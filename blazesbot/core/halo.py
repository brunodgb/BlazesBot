"""O ANEL DE TENTATIVA em volta de um ponto de clique.

=========================================================================
POR QUE ISTO EXISTE
=========================================================================

Todo clique de NPC deste bot é POSICIONAL na cena 3D: a coordenada de tela foi
medida com o personagem parado num ponto do mundo, e só vale a partir dele. Mas
o bot não para no ponto EXATO -- ele para dentro de uma folga (1,5 unidades de
mundo na entrada e na saída da HH), porque exigir a casa decimal travaria a
rotina num laço sem saída.

E a folga tem preço na tela. Medido na BC em 25/08/2026: cinco unidades de mundo
moveram o Rich Man quase 300 px. Dentro de 1,5 unidades o NPC ainda passeia
dezenas de pixels -- e a mira, que é um ponto só, às vezes cai ao lado dele.

Relato do usuário, 09/09/2026, sobre a saída da HH: *"às vezes o botão direito
falha, acredito que por uma pequena diferença de posicionamento... seria
interessante pegar como base onde está o clique direito atualmente e criar uma
pequena área em volta de tentativa"*.

=========================================================================
A ORDEM É DO MAIS PERTO PARA O MAIS LONGE
=========================================================================

O primeiro ponto é SEMPRE a mira medida, sem deslocamento: no caminho feliz
nada muda, nem em custo nem em comportamento. Só quando ela falha é que os
vizinhos entram, e os quatro lados vêm antes das quatro diagonais -- que estão
√2 vezes mais longe.

=========================================================================
QUEM USA ISTO PRECISA PARAR NO PRIMEIRO SINAL DE QUE ANDOU
=========================================================================

Clique que erra o NPC cai no chão, e clique no chão FAZ O PERSONAGEM ANDAR. Se
ele andou, a cena inteira se reprojetou e todo vizinho seguinte foi calculado
para um enquadramento que não existe mais -- insistir ali é empurrar o
personagem para longe do ponto de onde o NPC é alcançável.

Por isso `UIDoJogo.falar_com_npc` compara a posição da memória a cada volta e
abandona o anel assim que ela muda. Quem chama reposiciona e tenta de novo, que
é o que a saída da HH já fazia por conta (`_falar_com_o_npc_da_saida`).
"""
from __future__ import annotations

# Quanto anda o anel a cada volta, em pixels da tela.
#
# NÚMERO DE OBSERVAÇÃO DE CAMPO, não de medição instrumentada -- a mesma
# natureza de `ESPERA_ANTES_DO_SELL` em `bot/vendedor.py`. Não há como medir "de
# quanto a mira erra" sem uma sessão de amostragem com o NPC na tela; o que se
# sabe é a ordem de grandeza: erro de alguns pixels, não de centenas (erro
# grande não seria "às vezes", seria sempre).
#
# ESCOLHIDO PARA COBRIR SEM ATRAVESSAR: 14 px é menor que a metade de um sprite
# de NPC deste cliente, então o vizinho ainda cai sobre o NPC quando a mira
# errou por pouco -- e uma volta inteira varre uma janela de 28x28 px em volta
# da mira. Se a saída continuar falhando, é ESTE número que se mexe, e o teste
# `test_halo_do_clique_no_npc.py` diz o que ele não pode violar.
PASSO_DO_HALO = 14


def pontos_em_volta(base: tuple[int, int], passo: int = PASSO_DO_HALO,
                    voltas: int = 1) -> list[tuple[int, int]]:
    """A mira, e depois os vizinhos dela -- do mais perto para o mais longe.

    `passo <= 0` ou `voltas <= 0` devolvem só a mira: desligar o anel não pode
    exigir um caminho de código diferente de quem chama.
    """
    x, y = base
    pontos = [base]
    if passo <= 0:
        return pontos
    for volta in range(1, voltas + 1):
        r = passo * volta
        pontos.extend([
            (x, y - r), (x, y + r), (x - r, y), (x + r, y),          # os lados
            (x - r, y - r), (x + r, y - r),                          # as quinas
            (x - r, y + r), (x + r, y + r),
        ])
    return pontos


__all__ = ["PASSO_DO_HALO", "pontos_em_volta"]
