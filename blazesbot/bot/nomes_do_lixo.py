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
    "AlmOre.png": "Alm Ore",
    "Amuleto39.png": "Amuleto39",
    "Amuleto48.png": "Amuleto48",
    "AnFur.png": "An Fur",
    "ApoCharm.png": "Apo Charm",
    "Armor_Piece.png": "Armor Piece",
    "Bag.png": "Bag",
    "bag3.png": "bag3",
    "bag4.png": "bag4",
    "bag5.png": "bag5",
    "BAG7.png": "BAG7",
    "BambShoot.png": "Bamb Shoot",
    "BariteOre.png": "Barite Ore",
    "Beast_Blood.png": "Beast Blood",
    "BeastHorn.png": "Beast Horn",
    "Belt16.png": "Belt 16",
    "Belt26.png": "Belt 26",
    "Belt36.png": "Belt 36",
    "belt46.png": "Belt 46",
    "belt56.png": "Belt 56",
    "Belt6.png": "Belt 6",
    "Bife.png": "Bife",
    "Bjewel.png": "Bjewel",
    "Black_Evil.png": "Black Evil",
    "Black_Shadow_stone.png": "Black Shadow stone",
    "Blue-bell.png": "Blue bell",
    "Blue_Wolf_Meat.png": "Blue Wolf Meat",
    "Bronze_Bell.png": "Bronze Bell",
    "brtpil.png": "brtpil",
    "charm.png": "charm",
    "CIronShot.png": "CIron Shot",
    "Cowb.png": "Cowb",
    "CrackBB.png": "Crack BB",
    "Crista_Bot.png": "Crista Bot",
    "Cuff12.png": "Cuff 12",
    "Cuff22.png": "Cuff 22",
    "Cuff32.png": "Cuff 32",
    "Cuff42.png": "Cuff 42",
    "cuff52.png": "Cuff 52",
    "DarkBed.png": "Dark Bed",
    "DarkSM.png": "Dark SM",
    "DfrmtJos.png": "Dfrmt Jos",
    "dip.png": "dip",
    "Durmarst.png": "Durmarst",
    "Echo_Stone.png": "Echo Stone",
    "EvilPith.png": "Evil Pith",
    "ExoChip.png": "Exo Chip",
    "Fada15.png": "Boots Fada 15",
    "Fada23.png": "Armguard Fada 23",
    "Fada33.png": "Armguard Fada 33",
    "Fada35.png": "Boots Fada 35",
    "Fada38.png": "Robe Fada 38",
    "Fada43.png": "Armguard Fada 43",
    "Fada45.png": "Boots Fada 45",
    "Fada48.png": "Robe Fada 48",
    "Fada53.png": "Armguard Fada 53",
    "Fada55.png": "Boots Fada 55",
    "Fada58.png": "Robe Fada 58",
    "Fada63.png": "Armguard Fada 63",
    "Fada8.png": "Robe Fada 8",
    "Fairy13.png": "Armguard Fairy 13",
    "Fairy18.png": "Robe Fairy 18",
    "Fairy3.png": "Armguard Fairy 3",
    "Fairy5.png": "Boots Fairy 5",
    "FAIRY65.png": "Boots Fairy 65",
    "Fairy68.png": "Robe Fairy 68",
    "Fig.png": "Fig",
    "FireSneakMeat.png": "Fire Sneak Meat",
    "FlameOre.png": "Flame Ore",
    "FlyingSnake.png": "Flying Snake",
    "Fog-Amu.png": "Fog Amu",
    "FrMush.png": "Fr Mush",
    "FTMC.png": "FTMC",
    "GlosBead.png": "Glos Bead",
    "Gold_T.png": "Gold T",
    "Golden-bell.png": "Golden bell",
    "greenid.png": "greenid",
    "GrosM.png": "Gros M",
    "Hex_Necklace.png": "Hex Necklace",
    "HoneW.png": "Hone W",
    "HoneyS.png": "Honey S",
    "Hot_Stone.png": "Hot Stone",
    "IceRime.png": "Ice Rime",
    "Knee14.png": "Kneedpad 14",
    "Knee24.png": "Kneedpad 24",
    "Knee34.png": "Kneedpad 34",
    "Knee4.png": "Kneedpad 4",
    "Knee44.png": "Kneedpad 44",
    "Knee54.png": "Kneedpad 54",
    "LascToken.png": "Lasc Token",
    "Lion_Meat.png": "Lion Meat",
    "MagOre.png": "Mag Ore",
    "MDeearMeat.png": "MDeear Meat",
    "Monk13.png": "Armguard Monk 13",
    "Monk15.png": "Boots Monk 15",
    "Monk18.png": "Robe Monk 18",
    "Monk23.png": "Armguard Monk 23",
    "monk28.png": "Robe Monk 28",
    "Monk3.png": "Armguard Monk 3",
    "Monk33.png": "Armguard Monk 33",
    "Monk35.png": "Boots Monk 35",
    "Monk38.png": "Robe Monk 38",
    "Monk43.png": "Armguard Monk 43",
    "Monk45.png": "Boots Monk 45",
    "Monk48.png": "Robe Monk 48",
    "Monk53.png": "Armguard Monk 53",
    "Monk55.png": "Boots Monk 55",
    "Monk58.png": "Robe Monk 58",
    "Monk63.png": "Armguard Monk 63",
    "MONK65.png": "Boots Monk 65",
    "Monk68.png": "Robe Monk 68",
    "Monk8.png": "Robe Monk 8",
    "MysSkel.png": "Mys Skel",
    "Myth_Wood.png": "Myth Wood",
    "Nimbuz.png": "Nimbuz",
    "Note.png": "Note",
    "OgrePaw.png": "Ogre Paw",
    "PechOil.png": "Pech Oil",
    "PetFood1.png": "Pet Food1",
    "PhMet.png": "Ph Met",
    "PoisonCup.png": "Poison Cup",
    "Polygonum.png": "Polygonum",
    "Pork.png": "Pork",
    "PurBeastMeat.png": "Pur Beast Meat",
    "Purple-bell.png": "Purple bell",
    "Purple_Beast.png": "Purple Beast",
    "Rainnbow_Stone.png": "Rainnbow Stone",
    "Red-bell.png": "Red bell",
    "Ring27.png": "Ring 27",
    "Ring37.png": "Ring 37",
    "ring47.png": "Ring 47",
    "Ring67.png": "Ring 67",
    "RottedSeed.png": "Rotted Seed",
    "ScarpPill.png": "Scarp Pill",
    "Secret_silver.png": "Secret silver",
    "SF.png": "SF",
    "Silver-bell.png": "Silver bell",
    "Silver_Ore.png": "Silver Ore",
    "Sin13.png": "Armguard Sin 13",
    "Sin15.png": "Boots Sin 15",
    "Sin18.png": "Robe Sin 18",
    "Sin23.png": "Armguard Sin 23",
    "sin28.png": "Robe Sin 28",
    "Sin3.png": "Armguard Sin 3",
    "Sin33.png": "Armguard Sin 33",
    "Sin35.png": "Boots Sin 35",
    "Sin38.png": "Robe Sin 38",
    "Sin43.png": "Armguard Sin 43",
    "Sin45.png": "Boots Sin 45",
    "Sin48.png": "Robe Sin 48",
    "Sin53.png": "Armguard Sin 53",
    "Sin55.png": "Boots Sin 55",
    "Sin58.png": "Robe Sin 58",
    "Sin63.png": "Armguard Sin 63",
    "SIN65.png": "Boots Sin 65",
    "Sin68.png": "Robe Sin 68",
    "Sin8.png": "Robe Sin 8",
    "SpinelOre.png": "Spinel Ore",
    "StonOr.png": "Ston Or",
    "SweetFruit.png": "Sweet Fruit",
    "Tamer13.png": "Armguard Tamer 13",
    "Tamer15.png": "Boots Tamer 15",
    "Tamer18.png": "Robe Tamer 18",
    "Tamer23.png": "Armguard Tamer 23",
    "tamer28.png": "Robe Tamer 28",
    "Tamer3.png": "Armguard Tamer 3",
    "Tamer33.png": "Armguard Tamer 33",
    "Tamer35.png": "Boots Tamer 35",
    "Tamer38.png": "Robe Tamer 38",
    "Tamer43.png": "Armguard Tamer 43",
    "Tamer45.png": "Boots Tamer 45",
    "Tamer48.png": "Robe Tamer 48",
    "Tamer53.png": "Armguard Tamer 53",
    "Tamer55.png": "Boots Tamer 55",
    "Tamer58.png": "Robe Tamer 58",
    "Tamer63.png": "Armguard Tamer 63",
    "TAMER65.png": "Boots Tamer 65",
    "Tamer68.png": "Robe Tamer 68",
    "Tamer8.png": "Robe Tamer 8",
    "TcoldJade.png": "Tcold Jade",
    "ThornLizard.png": "Thorn Lizard",
    "Thyme.png": "Thyme",
    "TigrMet.png": "Tigr Met",
    "ToughTusk.png": "Tough Tusk",
    "VultureMeat.png": "Vulture Meat",
    "WDHead.png": "WDHead",
    "Wind_Amulet.png": "Wind Amulet",
    "Wizz13.png": "Armguard Wizz 13",
    "Wizz15.png": "Boots Wizz 15",
    "Wizz18.png": "Robe Wizz 18",
    "Wizz23.png": "Armguard Wizz 23",
    "wizz28.png": "Robe Wizz 28",
    "Wizz3.png": "Armguard Wizz 3",
    "Wizz33.png": "Armguard Wizz 33",
    "Wizz35.png": "Boots Wizz 35",
    "Wizz38.png": "Robe Wizz 38",
    "Wizz43.png": "Armguard Wizz 43",
    "Wizz45.png": "Boots Wizz 45",
    "wizz48.png": "Robe Wizz 48",
    "Wizz53.png": "Armguard Wizz 53",
    "Wizz55.png": "Boots Wizz 55",
    "Wizz58.png": "Robe Wizz 58",
    "Wizz63.png": "Armguard Wizz 63",
    "WIZZ65.png": "Boots Wizz 65",
    "Wizz68.png": "Robe Wizz 68",
    "Wizz8.png": "Robe Wizz 8",
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
    """O nome do arquivo virando texto legível.

    `Blue-bell.png` -> "Blue bell"; `Black_Shadow_stone.png` -> "Black Shadow
    stone"; `SpinelOre.png` -> "Spinel Ore".

    A MAIÚSCULA NO MEIO TAMBÉM SEPARA -- reversão de 19/09/2026, pedida pelo
    usuário: *"os que tiverem uma letra maiúscula no nome, você pode criar um
    espaço antes"*. A versão anterior se recusava a isso com medo de estragar
    `BAG7` e `bag3`, e o medo era infundado: o corte só acontece entre uma
    MINÚSCULA e uma MAIÚSCULA, e nesses dois não existe essa fronteira.
    `CrackBB` vira "Crack BB" e `DarkSM` vira "Dark SM", que é o certo.

    A extensão sai ANTES: senão o ponto vira espaço e todo item termina com
    " png".
    """
    stem = Path(nome_do_arquivo).stem
    limpo = re.sub(r"[\W_]+", " ", stem)
    limpo = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", limpo).strip()
    # Nome só de pontuação devolve o original: a janela nunca mostra vazio.
    return limpo or stem


def rotulo(nome_do_arquivo: str) -> str:
    """Como este modelo se chama na tela. Nunca devolve vazio."""
    return _INDICE.get(Path(nome_do_arquivo).stem.casefold(),
                       humanizar(nome_do_arquivo))
