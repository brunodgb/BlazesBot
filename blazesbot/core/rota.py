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
from collections.abc import Callable
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


# ---------------------------------------------------------------------------
# Reconhecimento e retomada de rota
# ---------------------------------------------------------------------------
#
# ESTA SEÇÃO SUBIU DE `bot/bc/mapa_bc.py` EM 01/09/2026, junto com a chegada da
# HH. Ela é a parte da rota que NÃO sabe de que cave se trata: dada uma lista de
# waypoints e uma posição, onde estou e por onde continuo.
#
# O que era dado da Bewitcher Cave agora ENTRA COMO PARÂMETRO -- as áreas de
# geometria apertada, os waypoints problemáticos e a função que diz a área de uma
# coordenada. Cada mapa injeta os seus através de invólucros de uma linha
# (`mapa_bc.tolerancia_do_waypoint`, `mapa_hh.tolerancia_do_waypoint`), e é por
# isso que os nove pontos de chamada da navegação não mudaram nada.
#
# **DEPENDÊNCIA CRUZADA: mexer aqui mexe nas DUAS caves.**

# Distância máxima até um waypoint para aceitar a área dele como resposta.
# Acima disso o bot está fora da rota e dizer a área seria palpite.
RAIO_DA_AREA = 55.0

# Distância até o waypoint mais próximo abaixo da qual o personagem é considerado
# NA rota, e não fora dela. É o limite que separa "escorreguei um pouco" de
# "preciso me retomar" -- e a diferença importa: retomada dentro de área apertada
# faz o bot voltar ao começo da área.
NA_ROTA = 12.0

# Diferença de distância abaixo da qual dois waypoints VIZINHOS contam como
# "praticamente à mesma distância", e aí vale ir para o de índice maior.
EMPATE_ENTRE_VIZINHOS = 8.0


@dataclass(frozen=True)
class Retomada:
    """De onde continuar a rota depois de sair dela."""

    indice: int                 # waypoint por onde retomar
    distancia: float            # a que distância dele estamos
    motivo: str                 # texto para o log
    area: str | None            # área em que o personagem está agora


def mais_proximos(
    pos: Ponto,
    caminho: tuple[Waypoint, ...],
    n: int = 2,
) -> list[tuple[int, float]]:
    """Os `n` waypoints mais próximos da posição, como `(índice, distância)`.

    A lista volta JÁ ORDENADA porque a proximidade é a decisão: do mais perto
    para o mais longe. Mais de um, e não apenas o mais próximo, porque o mais
    próximo pode ser justamente o que já foi passado -- com vários em mãos o
    chamador escolhe a estratégia (a retomada de rota anda para frente quando
    são vizinhos; a manobra de destravamento tenta por proximidade).
    """
    distancias = sorted(
        ((i, distancia(pos, wp.pos)) for i, wp in enumerate(caminho)),
        key=lambda par: par[1],
    )
    return distancias[:n]


def vizinhos_na_rota(
    pos: Ponto,
    caminho: tuple[Waypoint, ...],
) -> tuple[int | None, int | None, int | None]:
    """Os vizinhos IMEDIATOS na rota. Devolve `(anterior, mais_proximo, seguinte)`.

    "Anterior" e "seguinte" são os índices coladinhos no mais próximo -- `base-1`
    e `base+1` --, NUNCA "o mais próximo entre os de índice maior/menor".

    ISTO JÁ FOI O CONTRÁRIO, E CUSTOU UMA RUN. A versão anterior escolhia por
    distância dentro de cada lado, e o log mostrou o resultado com o personagem
    parado em (205,31):

        51/58  (206, 41)  a 10.0   <- o anterior de verdade
        53/58  (205, 23)  a  8.0   <- o mais próximo
        54/58  (244, 23)  a 39.8   <- o seguinte de verdade
        57/58  (219, 44)  a 19.1   <- o que a versão antiga escolhia

    Ela pulava três waypoints para cair num ponto ao DOBRO da distância, e o
    jogo respondia no chat: `Failed to auto-path [Secret Altar(205,31)->Secret
    Altar(218,43)]`. A rota não é um conjunto de pontos, é um CAMINHO: cada
    trecho foi desenhado porque é andável a partir do anterior. No Secret Altar,
    que é uma pirâmide, pular waypoint é pedir para atravessar parede.

    O MAIS PRÓXIMO TAMBÉM É CANDIDATO, e é o primeiro a ser tentado: quando o
    personagem está FORA do caminho, voltar para ele é o que torna o resto
    possível. Ver a ordem em `Navigator.destravar_pelos_vizinhos`.

    A referência é a posição ATUAL, não o índice em que a rota achava que o
    personagem estava -- depois de um rollback os dois divergem, e é o índice
    que está errado.

    Qualquer um dos três pode vir `None`: no começo da rota não há anterior, no
    fim não há seguinte, e numa rota vazia não há nada.
    """
    if not caminho:
        return None, None, None

    base = min(range(len(caminho)),
               key=lambda i: distancia(pos, caminho[i].pos))
    anterior = base - 1 if base > 0 else None
    seguinte = base + 1 if base + 1 < len(caminho) else None
    return anterior, base, seguinte


def onde_retomar(
    pos: Ponto | None,
    caminho: tuple[Waypoint, ...],
    indice_esperado: int = 0,
    *,
    areas_apertadas: frozenset[str] = frozenset(),
    area_da_posicao: Callable[[Ponto | None], str | None] | None = None,
) -> Retomada:
    """Decide por qual waypoint a rota deve continuar.

    Chamado sempre que a posição não é a esperada: lag, rollback, interferência
    do usuário, ou o personagem simplesmente ficou preso e escorregou.

    As regras, em ordem:

      1. Entre os dois waypoints mais próximos, prefere o de índice MAIOR
         quando eles são vizinhos -- é o que está à frente.
      2. Se o waypoint escolhido está numa ÁREA APERTADA (a pirâmide do Secret
         Altar), volta para o primeiro waypoint daquela área. Ali não existe
         atalho: entrar pelo meio significa bater na parede.
      3. Se nada está perto (fora da rota de verdade), retoma pelo waypoint
         mais próximo mesmo assim, e o log registra a distância -- é o número
         que diz se o personagem foi arrastado ou se só escorregou.

    `areas_apertadas` e `area_da_posicao` são os dados da cave, injetados por
    quem chama. Sem eles a regra 2 não dispara e a área devolvida é a do
    waypoint escolhido -- que é o comportamento CORRETO para uma cave cujas
    áreas ainda não foram medidas, como a HH: sem nome de área confiável, mandar
    o bot "voltar ao início da área" seria agir sobre um dado que não existe.
    """
    if pos is None or not caminho:
        return Retomada(max(0, indice_esperado), float("inf"),
                        "sem posição legível", None)

    proximos = mais_proximos(pos, caminho)
    (i1, d1) = proximos[0]
    escolhido, dist = i1, d1

    if len(proximos) > 1:
        (i2, d2) = proximos[1]
        # Vizinhos e praticamente à mesma distância: o de índice maior está à
        # frente, e ir para frente é sempre melhor que voltar.
        if abs(i1 - i2) == 1 and abs(d1 - d2) < EMPATE_ENTRE_VIZINHOS:
            escolhido = max(i1, i2)
            dist = d2 if escolhido == i2 else d1

    area = caminho[escolhido].area
    motivo = f"waypoint {escolhido + 1}/{len(caminho)} a {dist:.0f} unidades"

    # O recuo até o início da área só vale para quem está FORA da rota.
    #
    # Estar em cima de um waypoint não é "sair da rota" -- é estar na rota. Sem
    # esta condição, um personagem parado exatamente no patamar do Altar Stone
    # (218,45), que é o ÚLTIMO waypoint do caminho, era mandado de volta ao começo
    # do Secret Altar e refazia a pirâmide inteira por nada. E pior: como o portal
    # do altar só é usado depois de o último waypoint ser alcançado, ele nunca
    # chegava a clicar no Altar Stone -- ficava dando voltas na pirâmide.
    if area in areas_apertadas and dist > NA_ROTA:
        primeiro = next(i for i, wp in enumerate(caminho) if wp.area == area)
        if primeiro < escolhido:
            motivo = (f"{motivo}; {area} é apertada e estou FORA da rota, "
                      f"voltando ao início da área (waypoint {primeiro + 1})")
            escolhido = primeiro
            dist = distancia(pos, caminho[escolhido].pos)

    agora = area_da_posicao(pos) if area_da_posicao is not None else None
    return Retomada(escolhido, dist, motivo, agora or area)


def houve_rollback(
    indice_atual: int,
    pos: Ponto | None,
    caminho: tuple[Waypoint, ...],
    folga: int = 1,
) -> int | None:
    """Detecta que o personagem voltou muito na rota (lag ou rollback).

    Devolve o índice para onde ele voltou, ou None se está onde deveria. A folga
    existe porque atravessar um waypoint correndo e reler a posição um instante
    depois dá uma diferença pequena e normal -- só um salto de 2+ índices para
    trás é rollback. (O usuário confirmou: o lag costuma devolver 2-3 waypoints,
    nunca mais de 5; folga=1 pega todos.)
    """
    if pos is None or not caminho:
        return None
    (i, d) = mais_proximos(pos, caminho)[0]
    if d > RAIO_DA_AREA:
        return None
    if i < indice_atual - folga:
        return i
    return None


def tolerancia_do_waypoint(
    wp: Waypoint,
    base: int,
    apertada: int,
    *,
    areas_apertadas: frozenset[str] = frozenset(),
    problematicos: tuple[Ponto, ...] = (),
) -> int:
    """Tolerância de chegada, maior nas áreas de geometria apertada."""
    if wp.pos in problematicos or wp.area in areas_apertadas:
        return max(base, apertada)
    return base


def area_pelo_waypoint_mais_proximo(
    pos: Ponto | None,
    waypoints: tuple[Waypoint, ...],
    raio: float = RAIO_DA_AREA,
) -> str | None:
    """Área em que esta coordenada cai, pelo waypoint mais próximo.

    Devolve None quando nenhum waypoint está perto o bastante -- e None aqui é
    informação útil: significa "estou dentro da caixa da cave mas fora da rota",
    que é exatamente o caso em que o bot precisa se retomar.
    """
    if pos is None:
        return None
    melhor: Waypoint | None = None
    menor = float("inf")
    for wp in waypoints:
        d = distancia(pos, wp.pos)
        if d < menor:
            menor, melhor = d, wp
    if melhor is None or menor > raio:
        return None
    return melhor.area


def como_lista(caminho: tuple[Waypoint, ...]) -> list[Ponto]:
    """Só as coordenadas, para quem só precisa andar."""
    return [wp.pos for wp in caminho]
