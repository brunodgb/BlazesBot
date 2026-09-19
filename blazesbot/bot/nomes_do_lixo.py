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
    # LISTA DO APP -- data/templates/deletar (213 modelos)
    # ---------------------------------------------------------------
    "AlmOre.png": "Alm Ore",
    "Amuleto19.png": "Amuleto lvl19",
    "Amuleto29.png": "Amuleto lvl29",
    "Amuleto39.png": "Amuleto lvl39",
    "Amuleto49.png": "Amuleto lvl49",
    "Amuleto59.png": "Amuleto lvl59",
    "Amuleto69.png": "Amuleto lvl69",
    "Amuleto9.png": "Amuleto lvl9",
    "AnFur.png": "An Fur",
    "ApoCharm.png": "Apo Charm",
    "Armor_Piece.png": "Armor Piece",
    "Bag.png": "Level 1 Primary Gem Bag",
    "bag3.png": "Level 3 Primary Gem Bag",
    "bag4.png": "Level 4 Primary Gem Bag",
    "bag5.png": "Level 5 Primary Gem Bag",
    "BambShoot.png": "Bamb Shoot",
    "BariteOre.png": "Barite Ore",
    "Beast_Blood.png": "Beast Blood",
    "BeastHorn.png": "Beast Horn",
    "Belt16.png": "Belt lvl16",
    "Belt26.png": "Belt lvl26",
    "Belt36.png": "Belt lvl36",
    "belt46.png": "Belt lvl46",
    "belt56.png": "Belt lvl56",
    "Belt6.png": "Belt lvl6",
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
    "Cuff12.png": "Cuff lvl12",
    "Cuff22.png": "Cuff lvl22",
    "Cuff32.png": "Cuff lvl32",
    "Cuff42.png": "Cuff lvl42",
    "cuff52.png": "Cuff lvl52",
    "DarkBed.png": "Dark Bed",
    "DarkSM.png": "Dark SM",
    "DfrmtJos.png": "Dfrmt Jos",
    "dip.png": "dip",
    "Durmarst.png": "Durmarst",
    "Echo_Stone.png": "Echo Stone",
    "EvilPith.png": "Evil Pith",
    "ExoChip.png": "Exo Chip",
    "Fairy13.png": "Armguard Fairy lvl13",
    "Fairy15.png": "Boots Fairy lvl15",
    "Fairy18.png": "Robe Fairy lvl18",
    "Fairy23.png": "Armguard Fairy lvl23",
    "Fairy3.png": "Armguard Fairy lvl3",
    "Fairy33.png": "Armguard Fairy lvl33",
    "Fairy35.png": "Boots Fairy lvl35",
    "Fairy38.png": "Robe Fairy lvl38",
    "Fairy43.png": "Armguard Fairy lvl43",
    "Fairy45.png": "Boots Fairy lvl45",
    "Fairy48.png": "Robe Fairy lvl48",
    "Fairy5.png": "Boots Fairy lvl5",
    "Fairy53.png": "Armguard Fairy lvl53",
    "Fairy55.png": "Boots Fairy lvl55",
    "Fairy58.png": "Robe Fairy lvl58",
    "Fairy63.png": "Armguard Fairy lvl63",
    "Fairy65.png": "Boots Fairy lvl65",
    "Fairy68.png": "Robe Fairy lvl68",
    "Fairy8.png": "Robe Fairy lvl8",
    "Fig.png": "Fig",
    "FireSneakMeat.png": "Fire Sneak Meat",
    "FlameOre.png": "Flame Ore",
    "FlyingSnake.png": "Flying Snake",
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
    "Knee14.png": "Kneedpad lvl14",
    "Knee24.png": "Kneedpad lvl24",
    "Knee34.png": "Kneedpad lvl34",
    "Knee4.png": "Kneedpad lvl4",
    "Knee44.png": "Kneedpad lvl44",
    "Knee54.png": "Kneedpad lvl54",
    "LascToken.png": "Lasc Token",
    "Lion_Meat.png": "Lion Meat",
    "MagOre.png": "Mag Ore",
    "MDeearMeat.png": "MDeear Meat",
    "Monk13.png": "Armguard Monk lvl13",
    "Monk15.png": "Boots Monk lvl15",
    "Monk18.png": "Robe Monk lvl18",
    "Monk23.png": "Armguard Monk lvl23",
    "monk28.png": "Robe Monk lvl28",
    "Monk3.png": "Armguard Monk lvl3",
    "Monk33.png": "Armguard Monk lvl33",
    "Monk35.png": "Boots Monk lvl35",
    "Monk38.png": "Robe Monk lvl38",
    "Monk43.png": "Armguard Monk lvl43",
    "Monk45.png": "Boots Monk lvl45",
    "Monk48.png": "Robe Monk lvl48",
    "Monk53.png": "Armguard Monk lvl53",
    "Monk55.png": "Boots Monk lvl55",
    "Monk58.png": "Robe Monk lvl58",
    "Monk63.png": "Armguard Monk lvl63",
    "MONK65.png": "Boots Monk lvl65",
    "Monk68.png": "Robe Monk lvl68",
    "Monk8.png": "Robe Monk lvl8",
    "MysSkel.png": "Mys Skel",
    "Myth_Wood.png": "Myth Wood",
    "Nimbuz.png": "Nimbuz",
    "Note.png": "Note",
    "OgrePaw.png": "Ogre Paw",
    "PechOil.png": "Pech Oil",
    "PetFood1.png": "Pet Food 1",
    "PhMet.png": "Ph Met",
    "PoisonCup.png": "Poison Cup",
    "Polygonum.png": "Polygonum",
    "Pork.png": "Pork",
    "PurBeastMeat.png": "Pur Beast Meat",
    "Purple-bell.png": "Purple bell",
    "Purple_Beast.png": "Purple Beast",
    "Rainnbow_Stone.png": "Rainnbow Stone",
    "Red-bell.png": "Red bell",
    "Ring17.png": "Ring lvl17",
    "Ring27.png": "Ring lvl27",
    "Ring37.png": "Ring lvl37",
    "Ring47.png": "Ring lvl47",
    "Ring57.png": "Ring lvl57",
    "Ring67.png": "Ring lvl67",
    "Ring7.png": "Ring lvl7",
    "RottedSeed.png": "Rotted Seed",
    "ScarpPill.png": "Scarp Pill",
    "Secret_silver.png": "Secret silver",
    "SF.png": "SF",
    "Silver-bell.png": "Silver bell",
    "Silver_Ore.png": "Silver Ore",
    "Sin13.png": "Armguard Sin lvl13",
    "Sin15.png": "Boots Sin lvl15",
    "Sin18.png": "Robe Sin lvl18",
    "Sin23.png": "Armguard Sin lvl23",
    "sin28.png": "Robe Sin lvl28",
    "Sin3.png": "Armguard Sin lvl3",
    "Sin33.png": "Armguard Sin lvl33",
    "Sin35.png": "Boots Sin lvl35",
    "Sin38.png": "Robe Sin lvl38",
    "Sin43.png": "Armguard Sin lvl43",
    "Sin45.png": "Boots Sin lvl45",
    "Sin48.png": "Robe Sin lvl48",
    "Sin53.png": "Armguard Sin lvl53",
    "Sin55.png": "Boots Sin lvl55",
    "Sin58.png": "Robe Sin lvl58",
    "Sin63.png": "Armguard Sin lvl63",
    "SIN65.png": "Boots Sin lvl65",
    "Sin68.png": "Robe Sin lvl68",
    "Sin8.png": "Robe Sin lvl8",
    "SpinelOre.png": "Spinel Ore",
    "StonOr.png": "Ston Or",
    "SweetFruit.png": "Sweet Fruit",
    "Tamer13.png": "Armguard Tamer lvl13",
    "Tamer15.png": "Boots Tamer lvl15",
    "Tamer18.png": "Robe Tamer lvl18",
    "Tamer23.png": "Armguard Tamer lvl23",
    "tamer28.png": "Robe Tamer lvl28",
    "Tamer3.png": "Armguard Tamer lvl3",
    "Tamer33.png": "Armguard Tamer lvl33",
    "Tamer35.png": "Boots Tamer lvl35",
    "Tamer38.png": "Robe Tamer lvl38",
    "Tamer43.png": "Armguard Tamer lvl43",
    "Tamer45.png": "Boots Tamer lvl45",
    "Tamer48.png": "Robe Tamer lvl48",
    "Tamer53.png": "Armguard Tamer lvl53",
    "Tamer55.png": "Boots Tamer lvl55",
    "Tamer58.png": "Robe Tamer lvl58",
    "Tamer63.png": "Armguard Tamer lvl63",
    "TAMER65.png": "Boots Tamer lvl65",
    "Tamer68.png": "Robe Tamer lvl68",
    "Tamer8.png": "Robe Tamer lvl8",
    "TcoldJade.png": "Tcold Jade",
    "ThornLizard.png": "Thorn Lizard",
    "Thyme.png": "Thyme",
    "TigrMet.png": "Tigr Met",
    "ToughTusk.png": "Tough Tusk",
    "VultureMeat.png": "Vulture Meat",
    "WDHead.png": "WDHead",
    "Wizz13.png": "Armguard Wizz lvl13",
    "Wizz15.png": "Boots Wizz lvl15",
    "Wizz18.png": "Robe Wizz lvl18",
    "Wizz23.png": "Armguard Wizz lvl23",
    "wizz28.png": "Robe Wizz lvl28",
    "Wizz3.png": "Armguard Wizz lvl3",
    "Wizz33.png": "Armguard Wizz lvl33",
    "Wizz35.png": "Boots Wizz lvl35",
    "Wizz38.png": "Robe Wizz lvl38",
    "Wizz43.png": "Armguard Wizz lvl43",
    "Wizz45.png": "Boots Wizz lvl45",
    "wizz48.png": "Robe Wizz lvl48",
    "Wizz53.png": "Armguard Wizz lvl53",
    "Wizz55.png": "Boots Wizz lvl55",
    "Wizz58.png": "Robe Wizz lvl58",
    "Wizz63.png": "Armguard Wizz lvl63",
    "WIZZ65.png": "Boots Wizz lvl65",
    "Wizz68.png": "Robe Wizz lvl68",
    "Wizz8.png": "Robe Wizz lvl8",
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
