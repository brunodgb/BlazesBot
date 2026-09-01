"""O modelo de ROTA: waypoint, montagem da lista e distância.

=========================================================================
POR QUE ISTO SUBIU PARA O `core/`
=========================================================================

Nasceu dentro de `bot/bc/mapa_bc.py`, onde era a única rota que existia. Com a
chegada do ecossistema HH (`bot/hh/mapa_hh.py`) passou a ser lido por DOIS
ecossistemas -- e um ecossistema nunca importa do outro.

**DEPENDÊNCIA CRUZADA: mexer aqui mexe na Bewitcher Cave E na Black Wind Camp
Dungeon.** `mapa_bc` reexporta `Waypoint`, `montar` (com o nome antigo `_wp`) e
`distancia`, então todo o código da BC continua chamando pelos nomes de sempre.

O que subiu é só o MODELO e a geometria: o que é um waypoint, como montar a
lista sem repetição e a distância entre dois pontos. O que NÃO subiu, e por quê:

  * as ROTAS em si (`CAMINHO_ATE_O_ALTAR`, os quatro trechos da HH). São dados
    medidos de duas caves diferentes; não há nada em comum entre eles.
  * o reconhecimento de LUGAR (`area_da_posicao`, `esta_em_stone_city`,
    `x_contradiz_a_cave`, a caixa da cave). Ainda é específico da BC porque
    depende dos waypoints DELA -- ver `docs/decisoes/hh.md`, seção 9: os nomes
    de área de dentro da HH não estão medidos, e sem eles não existe o
    equivalente para a HH.
  * a RETOMADA de rota (`onde_retomar`, `vizinhos_na_rota`, `houve_rollback`).
    Sobe junto com a navegação, não antes: promover a retomada sem o motor que a
    usa deixaria duas metades da mesma decisão em camadas diferentes.

=========================================================================
O `via`: O CLIQUE CALIBRADO, QUE É RESERVA E NÃO VIA PRINCIPAL
=========================================================================

O campo `via` guarda um clique de minimapa medido à mão para aquele waypoint.
Ele veio do bot em Lua da HH, onde cada um dos 65 waypoints traz o seu.

**É RESERVA.** Quem anda é o motor de navegação, que calcula o clique a partir
da posição ATUAL e sabe detectar travamento, destravar pelos vizinhos e retomar
a rota. Um clique fixo não sabe nada disso: ele foi calibrado numa posição, e
usado de outra aponta para o lugar errado.

O `via` entra quando o motor medido desiste -- e aí ele vale ouro, porque é a
prova de que aquele trecho tem uma passagem que o cálculo não encontra sozinho.
Guardar é de graça; usar como primeira opção seria trocar um motor medido por
uma constante.

A BC não tem `via` em nenhum waypoint, e o padrão `None` é isso: ausência de
clique calibrado, não erro.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

Ponto = tuple[int, int]


@dataclass(frozen=True)
class Waypoint:
    """Um ponto da rota, com a área a que pertence.

    A ÁREA não é enfeite. Ela dá três coisas que coordenada sozinha não dá:

      1. CONFERIR onde o bot está -- a memória diz uma área, o waypoint diz
         outra, e a divergência denuncia que algo saiu do roteiro.
      2. Saber onde está SEM a memória, quando a leitura do nome do lugar falha.
      3. Reagir a lag e rollback: voltando a uma coordenada anterior, o bot
         descobre em que área caiu e retoma pelo waypoint certo daquela área.

    `via` é o clique de minimapa calibrado à mão, quando existe. Ver o cabeçalho
    do módulo: ele é RESERVA.
    """

    x: int
    y: int
    area: str
    via: Ponto | None = None

    @property
    def pos(self) -> Ponto:
        return (self.x, self.y)


def montar(pares: list[tuple]) -> tuple[Waypoint, ...]:
    """Monta a lista de waypoints removendo repetições consecutivas.

    Aceita `(x, y, area)` ou `(x, y, area, via)`.

    A medição no jogo produziu `[156,-406]` duas vezes seguidas. Waypoint
    repetido não é inofensivo: o bot considera o primeiro alcançado, clica no
    segundo (que é o mesmo ponto), não há movimento nenhum para observar e o
    detector de travamento dispara sem haver trava.

    A comparação é só por COORDENADA. Dois waypoints no mesmo ponto com áreas
    diferentes continuam sendo o mesmo ponto para quem anda -- e o segundo
    continuaria produzindo o falso travamento.
    """
    saida: list[Waypoint] = []
    for par in pares:
        x, y, area = par[0], par[1], par[2]
        via = par[3] if len(par) > 3 else None
        if saida and saida[-1].x == x and saida[-1].y == y:
            continue
        saida.append(Waypoint(x, y, area, via))
    return tuple(saida)


def distancia(a: Ponto, b: Ponto) -> float:
    """Distância em linha reta entre duas coordenadas de jogo."""
    return math.hypot(a[0] - b[0], a[1] - b[1])
