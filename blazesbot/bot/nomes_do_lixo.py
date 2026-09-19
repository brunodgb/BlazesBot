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
# mais facilidade"*. Trocar um nome é trocar UM valor.
#
# =========================================================================
# EM QUATRO GRUPOS, E NÃO EM ORDEM ALFABÉTICA
# =========================================================================
#
# Era alfabético -- a ordem da janela --, e isso era bom para CONFERIR. Mas
# quem abre este arquivo não confere, ACERTA UM NOME, e nessa tarefa o alfabeto
# espalha: "Fairy25" longe de "Fairy28", e os 105 equipamentos (que ninguém
# precisa tocar) no meio dos poucos que estão esperando alguém descobrir como
# se chamam. Pedido do usuário em 19/09/2026.
#
#   1. EQUIPAMENTO, POR CLASSE  gerado, regular, quase nunca se mexe
#   2. PEÇA SEM CLASSE E BOLSA  idem, sem a classe porque o arquivo não diz
#   3. ITEM COM NOME            nome conferido -- é aqui que se CORRIGE
#   4. AINDA SEM NOME           o que falta descobrir -- é aqui que se ESCREVE
#
# QUEM MONTA OS GRUPOS É `tools/sincronizar_nomes_do_lixo.py`, não a mão: este
# bloco é REGRAVADO inteiro a cada sincronia. Mudar a organização se faz lá
# (`GRUPOS`, `familia`), senão a próxima execução desfaz. Escreveu o nome de um
# item do grupo 4? Ele muda de grupo sozinho na próxima vez.
#
# APAGAR UMA LINHA NÃO QUEBRA NADA: sem entrada, o nome do arquivo normalizado
# volta a valer. E PNG novo na pasta também aparece sem passar por aqui.
#
# OS NOMES NÃO SÃO CHUTE -- vieram de duas fontes, nesta ordem (19/09/2026):
#
# 1. **O SITE OFICIAL.** A página do Magicstone lista com o nome exato os dez
#    materiais que caem de monstro: é de lá que saem "Bandit Jewel" (`Bjewel`),
#    "Cracked Buddha Bone" (`CrackBB`) e "Dark Bead" (`DarkBed` -- o arquivo é
#    que tem erro de digitação). Ver `docs/referencia-do-site-oficial.md`.
# 2. **A LISTA DE OUTRO BOT**, trazida pelo usuário, que resolveu as
#    abreviações que o site não tinha: `AlmOre` é Aluminum Ore, `GrosM` é
#    Grosvenor Mormodica, `Crista_Bot` é Crystal Bottle, `FTMC` é Far Temple
#    Map Chip. Trinta e um de uma vez. O que ela mostrou que FALTA na pasta
#    está em `docs/decisoes/deletador.md`.
#
# ONDE AS DUAS DISCORDAM, O SITE VENCE: `RottedSeed` fica "Rotted Seed" (site)
# e não "Rotten Seed" (lista). Um é a fonte do jogo; o outro é outro bot.
NOMES: dict[str, str] = {
    # ----------------------------------------------------------------------
    # APP / EQUIPAMENTO, POR CLASSE -- 105 modelos
    # ----------------------------------------------------------------------
    # A unidade do número é a PEÇA (2 Cuff, 3 Armguard, 4 Kneepad, 5 Boots,
    # 6 Belt, 8 Robe) e a dezena é o TIER. Não há o que ajustar aqui:
    # a sincronia gera todos, e o padrão nunca falha.
    "Fairy3.png": "Armguard Fairy lvl3",
    "Fairy5.png": "Boots Fairy lvl5",
    "Fairy8.png": "Robe Fairy lvl8",
    "Fairy13.png": "Armguard Fairy lvl13",
    "Fairy15.png": "Boots Fairy lvl15",
    "Fairy18.png": "Robe Fairy lvl18",
    "Fairy23.png": "Armguard Fairy lvl23",
    "Fairy25.png": "Boots Fairy lvl25",
    "Fairy28.png": "Robe Fairy lvl28",
    "Fairy33.png": "Armguard Fairy lvl33",
    "Fairy35.png": "Boots Fairy lvl35",
    "Fairy38.png": "Robe Fairy lvl38",
    "Fairy43.png": "Armguard Fairy lvl43",
    "Fairy45.png": "Boots Fairy lvl45",
    "Fairy48.png": "Robe Fairy lvl48",
    "Fairy53.png": "Armguard Fairy lvl53",
    "Fairy55.png": "Boots Fairy lvl55",
    "Fairy58.png": "Robe Fairy lvl58",
    "Fairy63.png": "Armguard Fairy lvl63",
    "Fairy65.png": "Boots Fairy lvl65",
    "Fairy68.png": "Robe Fairy lvl68",
    "Monk3.png": "Armguard Monk lvl3",
    "Monk5.png": "Boots Monk lvl5",
    "Monk8.png": "Robe Monk lvl8",
    "Monk13.png": "Armguard Monk lvl13",
    "Monk15.png": "Boots Monk lvl15",
    "Monk18.png": "Robe Monk lvl18",
    "Monk23.png": "Armguard Monk lvl23",
    "Monk25.png": "Boots Monk lvl25",
    "monk28.png": "Robe Monk lvl28",
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
    "Sin3.png": "Armguard Sin lvl3",
    "Sin5.png": "Boots Sin lvl5",
    "Sin8.png": "Robe Sin lvl8",
    "Sin13.png": "Armguard Sin lvl13",
    "Sin15.png": "Boots Sin lvl15",
    "Sin18.png": "Robe Sin lvl18",
    "Sin23.png": "Armguard Sin lvl23",
    "Sin25.png": "Boots Sin lvl25",
    "sin28.png": "Robe Sin lvl28",
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
    "Tamer3.png": "Armguard Tamer lvl3",
    "Tamer5.png": "Boots Tamer lvl5",
    "Tamer8.png": "Robe Tamer lvl8",
    "Tamer13.png": "Armguard Tamer lvl13",
    "Tamer15.png": "Boots Tamer lvl15",
    "Tamer18.png": "Robe Tamer lvl18",
    "Tamer23.png": "Armguard Tamer lvl23",
    "Tamer25.png": "Boots Tamer lvl25",
    "tamer28.png": "Robe Tamer lvl28",
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
    "Wizz3.png": "Armguard Wizz lvl3",
    "Wizz5.png": "Boots Wizz lvl5",
    "Wizz8.png": "Robe Wizz lvl8",
    "Wizz13.png": "Armguard Wizz lvl13",
    "Wizz15.png": "Boots Wizz lvl15",
    "Wizz18.png": "Robe Wizz lvl18",
    "Wizz23.png": "Armguard Wizz lvl23",
    "Wizz25.png": "Boots Wizz lvl25",
    "wizz28.png": "Robe Wizz lvl28",
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

    # ----------------------------------------------------------------------
    # APP / PEÇA SEM CLASSE E BOLSA -- 40 modelos
    # ----------------------------------------------------------------------
    # O arquivo não diz a classe, então o rótulo não inventa uma.
    # E do tier 7 em diante ela NÃO EXISTE: o set do 70/79 e o do 80
    # são padrão nas cinco classes, com o ÍCONE exatamente igual, então
    # há um modelo só para cada peça (usuário, 19/09/2026). Não há
    # família para completar aqui.
    "Amuleto9.png": "Amuleto lvl9",
    "Amuleto19.png": "Amuleto lvl19",
    "Amuleto29.png": "Amuleto lvl29",
    "Amuleto39.png": "Amuleto lvl39",
    "Amuleto49.png": "Amuleto lvl49",
    "Amuleto59.png": "Amuleto lvl59",
    "Amuleto69.png": "Amuleto lvl69",
    "Amuleto79.png": "Amuleto lvl79",
    "bag3.png": "Level 3 Gem Bag",
    "bag4.png": "Level 4 Gem Bag",
    "bag5.png": "Level 5 Gem Bag",
    "BAG7.png": "Level 7 Primary Gem Bag",
    "Belt6.png": "Belt lvl6",
    "Belt16.png": "Belt lvl16",
    "Belt26.png": "Belt lvl26",
    "Belt36.png": "Belt lvl36",
    "belt46.png": "Belt lvl46",
    "belt56.png": "Belt lvl56/66",
    "Belt76.png": "Belt lvl76",
    "Cuff12.png": "Cuff lvl12",
    "Cuff22.png": "Cuff lvl22",
    "Cuff32.png": "Cuff lvl32",
    "Cuff42.png": "Cuff lvl42",
    "cuff52.png": "Cuff lvl52/62",
    "Cuff72.png": "Cuff lvl72",
    "Cuff80.png": "Cuff lvl80",
    "Knee4.png": "Kneepad lvl4",
    "Knee14.png": "Kneepad lvl14",
    "Knee24.png": "Kneepad lvl24",
    "Knee34.png": "Kneepad lvl34",
    "Knee44.png": "Kneepad lvl44",
    "Knee54.png": "Kneepad lvl54/64",
    "Ring7.png": "Ring lvl7",
    "Ring17.png": "Ring lvl17",
    "Ring27.png": "Ring lvl27",
    "Ring37.png": "Ring lvl37",
    "Ring47.png": "Ring lvl47",
    "Ring57.png": "Ring lvl57",
    "Ring67.png": "Ring lvl67",
    "Ring77.png": "Ring lvl77",

    # ----------------------------------------------------------------------
    # APP / ITEM COM NOME -- 109 modelos
    # ----------------------------------------------------------------------
    # Nome conferido no site oficial, na lista de outro bot ou no jogo.
    # É aqui que se corrige um nome errado.
    "AlmOre.png": "Aluminum Ore",
    "AnFur.png": "Animal Fur",
    "Aphothecary-Pill.png": "Apothecary Pill",
    "ApoCharm.png": "Apotropaion Charm",
    "Armguard73.png": "Armguard lvl73",
    "Armguard81.png": "Armguard lvl81",
    "Armor78.png": "Armor lvl78",
    "Armor_Piece.png": "Armor Piece",
    "BambShoot.png": "Bamboo Shoot",
    "Bjewel.png": "Bandit Jewel",
    "BariteOre.png": "Barite Ore",
    "Beast_Blood.png": "Beast Blood",
    "BeastHorn.png": "Beast Horn",
    "Black_Evil.png": "Black Evil Crystal",
    "Black_Shadow_stone.png": "Black Shadow Stone",
    "Blue-bell.png": "Blue Bell",
    "Blue-Id-Gem.png": "Blue Id Gem",
    "Blue_Wolf_Meat.png": "Blue Wolf Meat",
    "Blueness-Stone.png": "Blueness Stone",
    "Boots75.png": "Boots lvl75",
    "brtpil.png": "Breath Pill",
    "Bronze_Bell.png": "Bronze Bell",
    "Cowb.png": "Cowbane",
    "CrackBB.png": "Cracked Buddha Bone",
    "Crista_Bot.png": "Crystal Bottle",
    "CIronShot.png": "Cursed Iron Shot",
    "Cuttle-Bone.png": "Cuttle Bone",
    "DarkBed.png": "Dark Bead",
    "DfrmtJos.png": "Deformity Joss",
    "Demon-Medal.png": "Demon Medal",
    "Devil-Token.png": "Devil Token",
    "dip.png": "Dipterocarp",
    "Durmarst.png": "Durmast",
    "Echo_Stone.png": "Echo Stone",
    "EvilPith.png": "Evil Pith",
    "ExoChip.png": "Exorcism Chip",
    "FTMC.png": "Far Temple Map Chip",
    "Fig.png": "Fig",
    "Fighting-Healing-Potion.png": "Fighting Healing Potion",
    "Fighting-Mana-Potion.png": "Fighting Mana Potion",
    "FireSneakMeat.png": "Fire Snake Meat",
    "FlameOre.png": "Flame Ore",
    "FlyingSnake.png": "Flying Snake",
    "FrMush.png": "Fresh Mushroom",
    "GlosBead.png": "Glossy Bead",
    "Gold_T.png": "Gold Thread",
    "Golden-bell.png": "Golden Bell",
    "Golden-Id-Gem.png": "Golden Id Gem",
    "Golden-Light-Pill.png": "Golden Light Pill",
    "greenid.png": "Green Id Gem",
    "ScarpPill.png": "Green Scarp Pill",
    "Grinderstone-of-Phoenix.png": "Grinderstone of Phoenix",
    "GrosM.png": "Grosvenor Mormodica",
    "Hex_Necklace.png": "Hex Necklace",
    "HoneW.png": "Honewort",
    "HoneyS.png": "Honeysuckle",
    "Hot_Stone.png": "Hot Stone",
    "IceRime.png": "Ice Rime",
    "Jackstraw.png": "Jackstraw",
    "Kneepad74.png": "Kneepad lvl74",
    "LascToken.png": "Lascivious Token",
    "Lion_Meat.png": "Lion Meat",
    "Lizard-Meat.png": "Lizard Meat",
    "Lygodium.png": "Lygodium",
    "MagOre.png": "Magnesium Ore",
    "Medium-Emerald.png": "Medium Emerald",
    "Medium-Ruby.png": "Medium Ruby",
    "MDeearMeat.png": "Musk Deer Meat",
    "MysSkel.png": "Mystic Skeleton",
    "Myth_Wood.png": "Myth Sea Wood",
    "Nimbuz.png": "Nimbus Quartz",
    "Note.png": "Note",
    "Occult-Berry.png": "Occult Berry",
    "OgrePaw.png": "Ogre Paw",
    "Package-of-Courage-Badge.png": "Package of Courage Badge",
    "PechOil.png": "Peach Oil",
    "PetFood1.png": "Pet Food",
    "PhMet.png": "Ph Meat",
    "Pith-of-Energy-Stone.png": "Pith of Energy Stone",
    "PoisonCup.png": "Poison Cup",
    "Polygonum.png": "Polygonum",
    "Polypody.png": "Polypody",
    "Pork.png": "Pork",
    "PurBeastMeat.png": "Purple Beast Meat",
    "Purple-bell.png": "Purple Bell",
    "Rainnbow_Stone.png": "Rainbow Stone",
    "Red-bell.png": "Red Bell",
    "Red-Bull-Steak.png": "Red Bull Steak",
    "Return-Charm.png": "Return Charm",
    "RottedSeed.png": "Rotted Seed",
    "Sacking-Frock.png": "Sacking Frock",
    "Secret_silver.png": "Secret Silver Necklace",
    "Silver-bell.png": "Silver Bell",
    "Silver_Ore.png": "Silver Ore",
    "Small-Emerald.png": "Small Emerald",
    "Small-Ruby.png": "Small Ruby",
    "SpinelOre.png": "Spinel Ore",
    "StonOr.png": "Stone Orchid",
    "SweetFruit.png": "Sweet Fruit",
    "Tablet-of-Cold-Jade.png": "Tablet of Cold Jade",
    "Teleport-Stone.png": "Teleport Stone",
    "ThornLizard.png": "Thorn Lizard",
    "Thyme.png": "Thyme",
    "TigrMet.png": "Tiger Meat",
    "ToughTusk.png": "Tough Tusk",
    "Treasure-Box.png": "Treasure Box",
    "VultureMeat.png": "Vulture Meat",
    "Wolf_Meat.png": "Wolf Meat",
    "Wood_Demon_Head.png": "Wood Demon Head",

    # ----------------------------------------------------------------------
    # APP / AINDA SEM NOME -- É AQUI QUE VOCÊ ENTRA -- 4 modelos
    # ----------------------------------------------------------------------
    # O rótulo é o próprio nome do arquivo, porque ninguém sabe o nome de
    # verdade ainda. Viu o item no jogo? Escreva o nome aqui e ele sai
    # desta seção sozinho na próxima sincronia.
    "Bife.png": "Bife",
    "charm.png": "charm",
    "DarkSM.png": "Dark SM",
    "Purple_Beast.png": "Purple Beast",

    # ----------------------------------------------------------------------
    # LISTA DA HH -- data/templates/deletar_hh (16 modelos)
    # ----------------------------------------------------------------------
    # Os talismãs assistentes que caem na Happiness Hall. Lista à parte porque
    # o que é lixo numa cave é mercadoria na outra.
    "Biddha-Bone.png": "Buddha Bone",
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
