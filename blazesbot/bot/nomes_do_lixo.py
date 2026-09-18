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
# Começa vazio de propósito: rótulo inventado é pior que nome de arquivo, e
# quem sabe o que é cada ícone é quem joga. Vai crescendo item a item.
NOMES: dict[str, str] = {
    # "Blue_Wolf_Meat.png": "Carne de Lobo Azul",
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
