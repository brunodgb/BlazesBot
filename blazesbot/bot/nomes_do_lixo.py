"""COMO CADA MODELO DE LIXO SE CHAMA PARA O USUÁRIO.

`AlmOre.png`, `bag3.png`, `Amuleto39.png` não dizem nada para quem vai decidir
se apaga ou preserva. Quem reconhece o item é o DESENHO — a miniatura — e o
nome existe para dar uma segunda pista, não para carregar a decisão sozinho.

=========================================================================
DUAS FONTES, NESTA ORDEM
=========================================================================

1. **`NOMES`**, o dicionário que o DESENVOLVEDOR preenche, um item por vez.
   Mora no código (versionado) e não em `data/`, que está no `.gitignore`: um
   arquivo de rótulos lá não sobrevive a um clone novo nem viaja entre
   máquinas.
2. **O nome do arquivo, normalizado**, quando não há entrada. `-`, `_`, `.` e
   pontuação em geral viram espaço.

O DICIONÁRIO NUNCA BLOQUEIA NADA. Sem entrada, com entrada errada ou com o PNG
renomeado, a janela continua mostrando um nome — no pior caso o do arquivo. Foi
pedido assim: *"faça de uma forma inteligente que vai funcionar e que eu possa
alterar, e por padrão puxa o nome atual da imagem"*.

NÃO SE ADIVINHA ONDE A PALAVRA QUEBRA. `AlmOre` não vira "Alm Ore" e
`Amuleto39` não vira "Amuleto 39": a regra que acertasse esses dois erraria em
`BAG7` e `bag3`. Separar só onde JÁ existe um separador é o que o usuário
pediu — *"não é para adivinhar, é só nas imagens que já têm um espaçamento"* —
e o resto é exatamente o que o dicionário existe para resolver.

=========================================================================
COMO ACRESCENTAR UM NOME
=========================================================================

Uma linha em `NOMES`, com o nome do arquivo como está no disco:

    "Blue_Wolf_Meat.png": "Carne de Lobo Azul",

A busca é tolerante de propósito: aceita o nome com ou sem `.png` e ignora
maiúsculas. Serve as DUAS listas (`deletar/` e `deletar_hh/`) — não há um único
nome repetido entre elas, conferido em 17/09/2026.
"""
from __future__ import annotations

import re
from pathlib import Path

# O DICIONÁRIO. Nome do arquivo -> como o usuário lê.
#
# VEM COM A LISTA INTEIRA, e cada valor começa sendo o próprio nome do arquivo
# já normalizado -- é exatamente o que a janela mostrava antes de este arquivo
# existir, então nada muda de aparência até alguém editar. Foi pedido assim em
# 19/09/2026: *"coloca pra mim toda a lista, pois assim eu consigo editar com
# mais facilidade"*. Trocar um nome é trocar UM valor; não há nada para
# acrescentar, remover ou manter em ordem.
#
# A ORDEM É A DA JANELA (alfabética ignorando maiúsculas), para achar o item
# aqui ser olhar para a mesma sequência da tela.
#
# APAGAR UMA LINHA NÃO QUEBRA NADA: sem entrada, o nome do arquivo normalizado
# volta a valer. E PNG novo na pasta também aparece sem passar por aqui.
NOMES: dict[str, str] = {
    # ---------------------------------------------------------------
    # LISTA DO APP -- data/templates/deletar (208 modelos)
    # ---------------------------------------------------------------
    "AlmOre.png": "AlmOre",
    "Amuleto39.png": "Amuleto39",
    "Amuleto48.png": "Amuleto48",
    "AnFur.png": "AnFur",
    "ApoCharm.png": "ApoCharm",
    "Armor_Piece.png": "Armor Piece",
    "Bag.png": "Bag",
    "bag3.png": "bag3",
    "bag4.png": "bag4",
    "bag5.png": "bag5",
    "BAG7.png": "BAG7",
    "BambShoot.png": "BambShoot",
    "BariteOre.png": "BariteOre",
    "Beast_Blood.png": "Beast Blood",
    "BeastHorn.png": "BeastHorn",
    "Belt16.png": "Belt16",
    "Belt26.png": "Belt26",
    "Belt36.png": "Belt36",
    "belt46.png": "belt46",
    "belt56.png": "belt56",
    "Belt6.png": "Belt6",
    "Bife.png": "Bife",
    "Bjewel.png": "Bjewel",
    "Black_Evil.png": "Black Evil",
    "Black_Shadow_stone.png": "Black Shadow stone",
    "Blue-bell.png": "Blue bell",
    "Blue_Wolf_Meat.png": "Blue Wolf Meat",
    "Bronze_Bell.png": "Bronze Bell",
    "brtpil.png": "brtpil",
    "charm.png": "charm",
    "CIronShot.png": "CIronShot",
    "Cowb.png": "Cowb",
    "CrackBB.png": "CrackBB",
    "Crista_Bot.png": "Crista Bot",
    "Cuff12.png": "Cuff12",
    "Cuff22.png": "Cuff22",
    "Cuff32.png": "Cuff32",
    "Cuff42.png": "Cuff42",
    "cuff52.png": "cuff52",
    "DarkBed.png": "DarkBed",
    "DarkSM.png": "DarkSM",
    "DfrmtJos.png": "DfrmtJos",
    "dip.png": "dip",
    "Durmarst.png": "Durmarst",
    "Echo_Stone.png": "Echo Stone",
    "EvilPith.png": "EvilPith",
    "ExoChip.png": "ExoChip",
    "Fada15.png": "Fada15",
    "Fada23.png": "Fada23",
    "Fada33.png": "Fada33",
    "Fada35.png": "Fada35",
    "Fada38.png": "Fada38",
    "Fada43.png": "Fada43",
    "Fada45.png": "Fada45",
    "Fada48.png": "Fada48",
    "Fada53.png": "Fada53",
    "Fada55.png": "Fada55",
    "Fada58.png": "Fada58",
    "Fada63.png": "Fada63",
    "Fada8.png": "Fada8",
    "Fairy13.png": "Fairy13",
    "Fairy18.png": "Fairy18",
    "Fairy3.png": "Fairy3",
    "Fairy5.png": "Fairy5",
    "FAIRY65.png": "FAIRY65",
    "Fairy68.png": "Fairy68",
    "Fig.png": "Fig",
    "FireSneakMeat.png": "FireSneakMeat",
    "FlameOre.png": "FlameOre",
    "FlyingSnake.png": "FlyingSnake",
    "Fog-Amu.png": "Fog Amu",
    "FrMush.png": "FrMush",
    "FTMC.png": "FTMC",
    "GlosBead.png": "GlosBead",
    "Gold_T.png": "Gold T",
    "Golden-bell.png": "Golden bell",
    "greenid.png": "greenid",
    "GrosM.png": "GrosM",
    "Hex_Necklace.png": "Hex Necklace",
    "HoneW.png": "HoneW",
    "HoneyS.png": "HoneyS",
    "Hot_Stone.png": "Hot Stone",
    "IceRime.png": "IceRime",
    "Knee14.png": "Knee14",
    "Knee24.png": "Knee24",
    "Knee34.png": "Knee34",
    "Knee4.png": "Knee4",
    "Knee44.png": "Knee44",
    "Knee54.png": "Knee54",
    "LascToken.png": "LascToken",
    "Lion_Meat.png": "Lion Meat",
    "MagOre.png": "MagOre",
    "MDeearMeat.png": "MDeearMeat",
    "Monk13.png": "Monk13",
    "Monk15.png": "Monk15",
    "Monk18.png": "Monk18",
    "Monk23.png": "Monk23",
    "monk28.png": "monk28",
    "Monk3.png": "Monk3",
    "Monk33.png": "Monk33",
    "Monk35.png": "Monk35",
    "Monk38.png": "Monk38",
    "Monk43.png": "Monk43",
    "Monk45.png": "Monk45",
    "Monk48.png": "Monk48",
    "Monk53.png": "Monk53",
    "Monk55.png": "Monk55",
    "Monk58.png": "Monk58",
    "Monk63.png": "Monk63",
    "MONK65.png": "MONK65",
    "Monk68.png": "Monk68",
    "Monk8.png": "Monk8",
    "MysSkel.png": "MysSkel",
    "Myth_Wood.png": "Myth Wood",
    "Nimbuz.png": "Nimbuz",
    "Note.png": "Note",
    "OgrePaw.png": "OgrePaw",
    "PechOil.png": "PechOil",
    "PetFood1.png": "PetFood1",
    "PhMet.png": "PhMet",
    "PoisonCup.png": "PoisonCup",
    "Polygonum.png": "Polygonum",
    "Pork.png": "Pork",
    "PurBeastMeat.png": "PurBeastMeat",
    "Purple-bell.png": "Purple bell",
    "Purple_Beast.png": "Purple Beast",
    "Rainnbow_Stone.png": "Rainnbow Stone",
    "Red-bell.png": "Red bell",
    "Ring27.png": "Ring27",
    "Ring37.png": "Ring37",
    "ring47.png": "ring47",
    "Ring67.png": "Ring67",
    "RottedSeed.png": "RottedSeed",
    "ScarpPill.png": "ScarpPill",
    "Secret_silver.png": "Secret silver",
    "SF.png": "SF",
    "Silver-bell.png": "Silver bell",
    "Silver_Ore.png": "Silver Ore",
    "Sin13.png": "Sin13",
    "Sin15.png": "Sin15",
    "Sin18.png": "Sin18",
    "Sin23.png": "Sin23",
    "sin28.png": "sin28",
    "Sin3.png": "Sin3",
    "Sin33.png": "Sin33",
    "Sin35.png": "Sin35",
    "Sin38.png": "Sin38",
    "Sin43.png": "Sin43",
    "Sin45.png": "Sin45",
    "Sin48.png": "Sin48",
    "Sin53.png": "Sin53",
    "Sin55.png": "Sin55",
    "Sin58.png": "Sin58",
    "Sin63.png": "Sin63",
    "SIN65.png": "SIN65",
    "Sin68.png": "Sin68",
    "Sin8.png": "Sin8",
    "SpinelOre.png": "SpinelOre",
    "StonOr.png": "StonOr",
    "SweetFruit.png": "SweetFruit",
    "Tamer13.png": "Tamer13",
    "Tamer15.png": "Tamer15",
    "Tamer18.png": "Tamer18",
    "Tamer23.png": "Tamer23",
    "tamer28.png": "tamer28",
    "Tamer3.png": "Tamer3",
    "Tamer33.png": "Tamer33",
    "Tamer35.png": "Tamer35",
    "Tamer38.png": "Tamer38",
    "Tamer43.png": "Tamer43",
    "Tamer45.png": "Tamer45",
    "Tamer48.png": "Tamer48",
    "Tamer53.png": "Tamer53",
    "Tamer55.png": "Tamer55",
    "Tamer58.png": "Tamer58",
    "Tamer63.png": "Tamer63",
    "TAMER65.png": "TAMER65",
    "Tamer68.png": "Tamer68",
    "Tamer8.png": "Tamer8",
    "TcoldJade.png": "TcoldJade",
    "ThornLizard.png": "ThornLizard",
    "Thyme.png": "Thyme",
    "TigrMet.png": "TigrMet",
    "ToughTusk.png": "ToughTusk",
    "VultureMeat.png": "VultureMeat",
    "WDHead.png": "WDHead",
    "Wind_Amulet.png": "Wind Amulet",
    "Wizz13.png": "Wizz13",
    "Wizz15.png": "Wizz15",
    "Wizz18.png": "Wizz18",
    "Wizz23.png": "Wizz23",
    "wizz28.png": "wizz28",
    "Wizz3.png": "Wizz3",
    "Wizz33.png": "Wizz33",
    "Wizz35.png": "Wizz35",
    "Wizz38.png": "Wizz38",
    "Wizz43.png": "Wizz43",
    "Wizz45.png": "Wizz45",
    "wizz48.png": "wizz48",
    "Wizz53.png": "Wizz53",
    "Wizz55.png": "Wizz55",
    "Wizz58.png": "Wizz58",
    "Wizz63.png": "Wizz63",
    "WIZZ65.png": "WIZZ65",
    "Wizz68.png": "Wizz68",
    "Wizz8.png": "Wizz8",
    "Wolf_Meat.png": "Wolf Meat",
    "Wood_Demon_Head.png": "Wood Demon Head",

    # ---------------------------------------------------------------
    # LISTA DA HH -- data/templates/deletar_hh (16 modelos)
    # ---------------------------------------------------------------
    "Biddha-Bone.png": "Biddha Bone",
    "Diamond-Sutra.png": "Diamond Sutra",
    "Dragon-Roc.png": "Dragon Roc",
    "Hasty-Shoes.png": "Hasty Shoes",
    "Heart-Lotus.png": "Heart Lotus",
    "Ice-Shield.png": "Ice Shield",
    "Jade-Vessel.png": "Jade Vessel",
    "Longbrow-Needle.png": "Longbrow Needle",
    "Pet-Bell.png": "Pet Bell",
    "Purple-Cowry.png": "Purple Cowry",
    "Tao-Symbol.png": "Tao Symbol",
    "Theurgy-Bell.png": "Theurgy Bell",
    "Trap-Meshwork.png": "Trap Meshwork",
    "Treasure-Leaf.png": "Treasure Leaf",
    "Warm-Jade.png": "Warm Jade",
    "Wonder-Needle.png": "Wonder Needle",
}

# Índice tolerante, montado uma vez: nome sem extensão e em minúsculas.
_INDICE = {Path(chave).stem.casefold(): valor for chave, valor in NOMES.items()}


def humanizar(nome_do_arquivo: str) -> str:
    """O nome do arquivo virando texto legível, SEM adivinhar palavra.

    `Blue-bell.png` -> "Blue bell"; `Black_Shadow_stone.png` -> "Black Shadow
    stone"; `AlmOre.png` -> "AlmOre" (não se inventa a quebra).

    A extensão sai ANTES: senão o ponto vira espaço e todo item termina com
    " png".
    """
    stem = Path(nome_do_arquivo).stem
    limpo = re.sub(r"[\W_]+", " ", stem).strip()
    # Nome só de pontuação devolve o original: a janela nunca mostra vazio.
    return limpo or stem


def rotulo(nome_do_arquivo: str) -> str:
    """Como este modelo se chama na tela. Nunca devolve vazio."""
    return _INDICE.get(Path(nome_do_arquivo).stem.casefold(),
                       humanizar(nome_do_arquivo))
