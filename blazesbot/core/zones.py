"""
Zonas do mapa-múndi, para deslocamento de longa distância.

POR QUE ISTO EXISTE

O minimapa só alcança alguns metros ao redor do personagem. Para atravessar meia
região -- por exemplo, sair de Stone City e chegar na entrada da Bewitcher Cave,
em Ghost Din Woods -- clicar no minimapa exigiria dezenas de saltos curtos, cada
um com risco de travar em geometria.

O MAPA-MÚNDI (tecla M) resolve isso: ele mostra a região inteira, e um clique
direito nele manda o personagem caminhar até lá, com o pathing do próprio jogo.

COMO A CONVERSÃO FUNCIONA

Cada região do jogo é desenhada no mapa com uma escala própria. Para converter
uma coordenada do jogo em pixel na tela do mapa, precisamos de dois números por
região:

  centre -- a coordenada de jogo que cai no CENTRO da tela quando o mapa daquela
            região está aberto.
  scale  -- quantas unidades de coordenada cabem em 1 pixel, em X e em Y. O X é
            negativo porque o eixo do mapa é invertido em relação ao do jogo.

Com isso:

    pixel_x = largura/2  + (centre_x - alvo_x) / scale_x
    pixel_y = altura/2   + (centre_y - alvo_y) / scale_y

Os valores de centre e scale abaixo vêm do GhostBot, um bot open source de
Talisman, e foram medidos por ele região por região. As regiões e escalas são
propriedade do jogo, não do bot: valem para qualquer cliente.

COMO DESCOBRIR A REGIÃO ATUAL

A memória expõe o nome do lugar ("Ghost Din Woods", "Stone City"). Cada nome
pertence a uma região, e o mapa `LOCAL_PARA_ZONA` faz essa ligação.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Zone:
    """Uma região do mapa-múndi."""

    nome: str
    # Coordenada de jogo que cai no centro da tela do mapa.
    centre: tuple[int, int]
    # Unidades de coordenada por pixel, em X e Y. X é negativo (eixo invertido).
    scale: tuple[float, float]
    # Retângulo aproximado da região, em coordenadas de jogo. Só informativo.
    boundary: tuple[tuple[int, int], tuple[int, int]] = ((0, 0), (0, 0))


ZONAS: dict[str, Zone] = {
    "simen_mountain": Zone("simen_mountain", (1667, 1544), (-1.05, 1.2),
                           ((1270, 1800), (2030, 1280))),
    "barbarian_mountain": Zone("barbarian_mountain", (1667, 902), (-1.0, 1.2),
                               ((1281, 1280), (2050, 510))),
    "green_scarp": Zone("green_scarp", (456, 1164), (-1.05, 1.65),
                        ((280, 1500), (500, 760))),
    "sky_village": Zone("sky_village", (150, 404), (-1.5, 1.85),
                        ((250, 760), (515, 0))),
    "cloud_mountain": Zone("cloud_mountain", (257, 45), (-1.4, 1.5),
                           ((-200, 220), (760, -266))),
    "stone_city": Zone("stone_city", (217, -528), (-1.0, 1.2),
                       ((-70, -266), (490, -760))),
    "black_wind_camp": Zone("black_wind_camp", (-415, -497), (-1.0, 1.1),
                            ((-762, -270), (-60, -760))),
    "laurel_mountain": Zone("laurel_mountain", (-489, -1125), (-1.45, 1.65),
                            ((-770, -770), (-260, -1500))),
    "snow_mountain": Zone("snow_mountain", (-1009, -1012), (-0.95, 1.2),
                          ((-1270, -780), (-1075, -1275))),
    "whorl_mountain": Zone("whorl_mountain", (-1001, -1639), (-1.5, 1.5),
                           ((-1260, -1275), (-800, -2020))),
    # A região da Bewitcher Cave.
    "vast_mountain": Zone("vast_mountain", (989, -489), (-1.38, 1.38),
                          ((491, -280), (1540, -410))),
    "dais_field": Zone("dais_field", (2304, -453), (-2.05, 2.05),
                       ((1540, -20), (3070, -750))),
}

# Nome do lugar (como aparece na memória) -> região do mapa.
_LOCAIS_POR_ZONA: dict[str, tuple[str, ...]] = {
    "peace_island": ("Moon Dragon Harbor", "Black Turtle Palace",
                     "Coconut Woods", "Peace Village"),
    "simen_mountain": ("Bandit Lair", "Bandit Fort", "East of Simen Mountain",
                       "Moon Dragon Village", "Outskirt of Village",
                       "South of Simen Mountain"),
    "west_simen_mountain": ("Dry Woods", "Old Site of Village",
                            "West of Simen Mountain"),
    "green_scarp": ("Green Scarp", "Piedmont of Green Scarp",
                    "Green Scarp Secret Cave", "Back Mountain of Green Scarp"),
    "sky_village": ("Sky Village", "Sky Village Field", "Hiking Road",
                    "South Wasteland", "Sky Village North East",
                    "Sky Village South East", "Sky Village South West",
                    "South Suburb of Sky Village", "North Suburb of Sky Village",
                    "East Suburb of Sky Village", "West Suburb of Sky Village",
                    "Snake Swamp", "Snake Swamp South", "Snake Swamp North",
                    "Black Campo", "Black Campo West", "Black Heart Wasteland"),
    "cloud_mountain": ("Serene Village", "Serene Hiking", "Cacodaemon Stockade",
                       "The Wounded Camp", "Bamboo Forest of Cloud Mountain",
                       "Centipede Mountain"),
    "stone_city": ("Belvedere", "Barren Road of West Suburb", "Gangster Alley",
                   "Green Bamboo Road", "Jade Nunnery", "Leud Temple",
                   "Mushroom Village", "Stone City", "Stone City North",
                   "Stone City South"),
    "black_wind_camp": ("Wei's Village", "Outside Black Wind Camp",
                        "Black Wind Camp", "Black Wind Camp Dungeon",
                        "West Suburb of Stone City", "Arms Bear Residence",
                        "Bothy"),
    "laurel_mountain": ("Ancient Laurel Grounds", "Laurel Road", "Laurel Room",
                        "Red Flower Cave", "Fencing Room", "Red Flower Alley",
                        "Fortune Pond", "Fire Cloud Cave", "Lava Valley",
                        "Laurel Woods", "Forest Plain", "Spring of Fortune Pond",
                        "Fountain Plain"),
    "snow_mountain": ("Snow Forrest", "Snow Village", "Ghost Shadow Swamp",
                      "Ghost Wind Valley", "Trade Caravan Camp",
                      "White Mountain Shrubberies", "White Mountain Cave",
                      "Far Temple", "Outer Far Temple", "Riprap Hillock"),
    "whorl_mountain": ("Ice Prick Forest", "Live Diagram Zone",
                       "Floating Ice Area", "Hotspring Valley",
                       "Death Diagram Zone", "Skull Hollow",
                       "Throat Rift Stage", "Fiend Hall", "Arm Broken Bluff"),
    # Ghost Din Woods é o caminho para a Bewitcher Cave.
    "vast_mountain": ("White Bear Village", "Black Bear Cave", "Zhao's Palace",
                      "Vast Mountain", "Wood Demon Cave", "Tusk Ogre Lair",
                      "Ghost Din Woods"),
    "dais_field": ("Yue Mansion", "Brier Woods", "Avenue", "Ling Mansion",
                   "Star Town", "Chen's Manor", "Dai's Field",
                   "Ichthyoid Cave", "Mazy Woods", "Market of Clear Water Dam",
                   "New Field of Loo's Village", "Old Field of Loo's Village",
                   "Jail of Screw Bay"),
}

LOCAL_PARA_ZONA: dict[str, str] = {
    local: zona for zona, locais in _LOCAIS_POR_ZONA.items() for local in locais
}


# Menor pedaço de nome que ainda identifica um lugar com segurança. Abaixo disso
# há risco de "Cave" casar com meia dúzia de lugares diferentes.
_MINIMO_PARCIAL = 6


def _casar_parcial(lido: str) -> str | None:
    """Casa um nome de lugar que veio INCOMPLETO da memória.

    Isto não é firula: no log de produção a leitura devolveu `'8tcher Cave'` em
    vez de `'Bewitcher Cave'` -- o começo da string se perde às vezes. Com
    comparação exata, um nome levemente truncado faz o bot concluir "não conheço
    esta região" e desistir do mapa-múndi, que é o único jeito de atravessar uma
    região inteira.

    A comparação é por CAUDA: descarta o que vem antes da primeira letra e exige
    que algum nome conhecido termine com o que sobrou.
    """
    import re

    cauda = re.sub(r"^[^A-Za-z]*", "", lido).strip().lower()
    if len(cauda) < _MINIMO_PARCIAL:
        return None
    candidatos = {
        zona for local, zona in LOCAL_PARA_ZONA.items()
        if local.lower().endswith(cauda)
    }
    # Ambíguo é o mesmo que desconhecido: preferir errar de região seria pior.
    return candidatos.pop() if len(candidatos) == 1 else None


def zona_do_local(nome_do_local: str | None) -> Zone | None:
    """Região do mapa correspondente ao nome do lugar lido da memória."""
    if not nome_do_local:
        return None
    nome = nome_do_local.strip()
    chave = LOCAL_PARA_ZONA.get(nome) or _casar_parcial(nome)
    if chave is None:
        return None
    return ZONAS.get(chave)


def coord_para_pixel_do_mapa(
    zona: Zone,
    alvo: tuple[int, int],
    largura: int,
    altura: int,
) -> tuple[int, int]:
    """Converte coordenada de jogo em pixel na tela do mapa-múndi.

    O mapa é desenhado centrado em `zona.centre`, e cada pixel vale `zona.scale`
    unidades de coordenada. O eixo X é invertido, o que já está embutido no sinal
    negativo da escala.
    """
    dx = zona.centre[0] - alvo[0]
    dy = zona.centre[1] - alvo[1]
    return (
        int(largura / 2 + dx / zona.scale[0]),
        int(altura / 2 + dy / zona.scale[1]),
    )


# ---------------------------------------------------------------------------
# Minimapa
# ---------------------------------------------------------------------------

# Escala do minimapa: pixels por unidade de coordenada.
#
# Descoberta importante: o minimapa NÃO é 1:1. São aproximadamente 1.7 pixels
# por metro. Os bots que usam 1:1 ainda funcionam porque o movimento é
# iterativo -- clicam, releem a posição e repetem -- então um passo curto só
# significa mais iterações. Com a escala certa, cada clique acerta o alvo.
MINIMAP_SCALE = 1.7

# Deslocamento máximo, em pixels, a partir do centro do minimapa. Clique além
# disso cai fora do widget e não faz nada.
MINIMAP_MAX_PIXELS = 30

# Distância em unidades de coordenada a partir da qual vale usar o mapa-múndi
# em vez do minimapa.
MAP_DISTANCE_THRESHOLD = 50


# Até onde um único clique no minimapa consegue mandar o personagem, em unidades
# de coordenada. É o raio útil do widget dividido pela escala: ~17,6 unidades.
#
# Saber este número é o que permite andar sem parar: um alvo mais distante que
# isso NÃO é alcançado por um clique só, então o bot precisa clicar de novo antes
# de o personagem terminar o trecho -- e não depois, quando ele já parou.
ALCANCE_DO_MINIMAPA = MINIMAP_MAX_PIXELS / MINIMAP_SCALE


def coord_para_pixel_do_minimapa(
    atual: tuple[int, int],
    alvo: tuple[int, int],
    centro: tuple[int, int],
) -> tuple[int, int]:
    """Converte um destino em clique no minimapa.

    O centro do minimapa representa a posição atual do personagem. O
    deslocamento até o alvo é convertido em pixels pela escala e limitado ao
    raio útil do widget.
    """
    import math

    dx = (atual[0] - alvo[0]) * -MINIMAP_SCALE
    dy = (atual[1] - alvo[1]) * MINIMAP_SCALE

    distancia = math.hypot(dx, dy)
    if distancia > MINIMAP_MAX_PIXELS:
        razao = distancia / MINIMAP_MAX_PIXELS
        dx /= razao
        dy /= razao

    return int(centro[0] + round(dx)), int(centro[1] + round(dy))


def destino_do_clique(
    atual: tuple[int, int],
    alvo: tuple[int, int],
) -> tuple[float, float]:
    """Onde o personagem vai REALMENTE parar com um clique em direção a `alvo`.

    Se o alvo está dentro do alcance, é o próprio alvo. Se está além, é o ponto
    na mesma direção, no limite do alcance. Serve para o bot saber com
    antecedência quando precisa clicar novamente.
    """
    import math

    dx, dy = alvo[0] - atual[0], alvo[1] - atual[1]
    distancia = math.hypot(dx, dy)
    if distancia <= ALCANCE_DO_MINIMAPA or distancia == 0:
        return (float(alvo[0]), float(alvo[1]))
    razao = ALCANCE_DO_MINIMAPA / distancia
    return (atual[0] + dx * razao, atual[1] + dy * razao)


def distancia_linear(a: tuple[int, int], b: tuple[int, int]) -> float:
    import math

    return math.hypot(a[0] - b[0], a[1] - b[1])
