"""SINCRONIZA `bot/nomes_do_lixo.py` COM A PASTA — renomeou PNG, rode isto.

    python -m blazesbot.tools.sincronizar_nomes_do_lixo

O dicionário de rótulos é digitado à mão, mas a LISTA de chaves é a pasta. Toda
vez que um PNG entra, sai ou muda de nome, os dois saem de sincronia -- e o
sintoma é mudo: o item aparece na janela com o nome cru do arquivo, como se
ninguém tivesse dado nome a ele.

=========================================================================
O QUE ELE PRESERVA, E O QUE ELE GERA
=========================================================================

**Rótulo que já existe NÃO é tocado.** Quem escreveu "Carne de Lobo Azul" na
mão não perde isso porque um vizinho mudou de nome.

**Chave nova ganha o rótulo padrão**, que é a convenção acumulada com o usuário:

    separador e maiúscula do meio viram espaço     SpinelOre -> Spinel Ore
    o dígito FINAL diz a peça                      Sin13     -> Armguard Sin
    a classe sai do próprio nome do arquivo        Wizz68    -> Robe Wizz
    o número final é o nível                       Cuff12    -> Cuff lvl12

**Chave órfã sai.** Se o PNG não existe mais, a linha não descreve nada.

=========================================================================
O QUE ELE NÃO FAZ
=========================================================================

Não adivinha classe onde o nome não diz. `Cuff12`, `Belt16`, `Knee4` e `Ring27`
saem como "Cuff lvl12", "Belt lvl16"... sem classe: o arquivo não informa qual
é, e rótulo errado num item que o usuário decide apagar OLHANDO é pior que
rótulo genérico.

E não existe teste exigindo que dicionário e pasta estejam em sincronia: ele
reprovaria na máquina de quem tem outros PNG, e `data/` não é versionado. A
sincronia é uma AÇÃO, não uma trava.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..bot import deletador
from ..bot.nomes_do_lixo import NOMES, humanizar

ARQUIVO = Path("blazesbot") / "bot" / "nomes_do_lixo.py"

# O dígito FINAL do nome diz a peça do equipamento (medido pelo usuário em
# 19/09/2026, item por item na tela).
PECA_POR_FINAL = {"2": "Cuff", "3": "Armguard", "4": "Kneedpad",
                  "5": "Boots", "6": "Belt", "8": "Robe"}

# As cinco classes do jogo, como aparecem nos nomes de arquivo.
#
# `FAIRY` E `FADA` SÃO A MESMA CLASSE, e as duas caem em "Fairy" -- o nome da
# classe vai em INGLÊS, como as outras quatro (pedido do usuário em
# 19/09/2026: *"padroniza os nomes em inglês... no caso só os nomes das
# classes"*). Os ARQUIVOS também foram renomeados: `Fada23.png` virou
# `Fairy23.png`.
#
# A unificação em si veio antes, e por outro motivo: deixar cada grafia como
# estava partia a família na grade -- "Armguard Fada lvl23..63" de um lado e
# "Armguard Fairy lvl3, lvl13" do outro.
#
# `Sin`, `Wizz`, `Monk` e `Tamer` já estão em inglês e ficam como estão: são a
# abreviação que a comunidade usa, e foi assim que o usuário nomeou os
# arquivos. Expandir para "Assassin"/"Wizard" é trocar estas duas linhas e
# rodar a sincronia.
CLASSES = {"sin": "Sin", "wizz": "Wizz", "monk": "Monk",
           "tamer": "Tamer", "fada": "Fairy", "fairy": "Fairy"}

# Nomes em que a PEÇA já está escrita e a classe não aparece.
PECAS_NO_NOME = {"cuff", "belt", "knee", "ring"}

# Nome que o JOGO dá ao item, com o nível no meio. `bag7` não é "BAG lvl7": a
# caixa de informação do cliente diz **"Level 7 Primary Gem Bag"**, e é esse o
# nome que o usuário reconhece na bolsa (print de 19/09/2026). O `{}` recebe o
# número.
NOMES_DO_JOGO = {"bag": "Level {} Primary Gem Bag"}


def rotulo_padrao(arquivo: str) -> str:
    """O rótulo que um PNG novo ganha. Nunca devolve vazio."""
    base = humanizar(arquivo)
    achado = re.match(r"^([A-Za-z]+?)(\d+)$", Path(arquivo).stem)
    if achado:
        palavra, numero = achado.group(1).lower(), achado.group(2)
        peca = PECA_POR_FINAL.get(numero[-1])
        # O NOME DO JOGO VENCE TODO O RESTO -- inclusive a regra do dígito
        # final, que aqui leria `bag3` como Armguard.
        if palavra in NOMES_DO_JOGO:
            return NOMES_DO_JOGO[palavra].format(numero)
        if palavra in CLASSES and peca:
            base = f"{peca} {CLASSES[palavra]} {numero}"
        elif palavra in PECAS_NO_NOME:
            base = f"{peca or achado.group(1).title()} {numero}"
    # O NÚMERO DO FIM É O NÍVEL -- "Cuff 12" vira "Cuff lvl12".
    return re.sub(r"\s*(\d+)$", r" lvl\1", base)


def converter_para_png(pasta: Path) -> tuple[list[str], list[str]]:
    """Todo JPG da pasta vira PNG, e o JPG sai. Devolve (convertidos, recusados).

    POR QUE ISTO MORA AQUI. O deletador varre `*.png` -- um JPG naquela pasta é
    um arquivo que o bot NUNCA enxerga. Não dá erro, não entra na janela, não
    apaga item nenhum: é uma falha muda, do mesmo feitio da que custou sete
    horas em 16/09/2026.

    A conversão é do que o decodificador entregou: o JPEG já perdeu o que tinha
    de perder quando foi salvo, e o PNG guarda exatamente os pixels que o
    `matchTemplate` vai comparar.

    NÃO SOBRESCREVE. PNG de mesmo nome já existente é motivo para RECUSAR e
    avisar -- apagar template é irreversível e `data/` não é versionado.
    """
    import cv2

    convertidos: list[str] = []
    recusados: list[str] = []
    for jpg in sorted(pasta.glob("*.jp*g"), key=lambda p: p.name.casefold()):
        destino = jpg.with_suffix(".png")
        if destino.exists():
            recusados.append(f"{jpg.name} (já existe {destino.name})")
            continue
        imagem = cv2.imread(str(jpg), cv2.IMREAD_UNCHANGED)
        if imagem is None:
            recusados.append(f"{jpg.name} (não consegui ler)")
            continue
        if not cv2.imwrite(str(destino), imagem):
            recusados.append(f"{jpg.name} (não consegui gravar o PNG)")
            continue
        jpg.unlink()
        convertidos.append(f"{jpg.name} -> {destino.name}")
    return convertidos, recusados


def _pngs(pasta: Path) -> list[str]:
    return sorted((p.name for p in pasta.glob("*.png")), key=str.casefold)


def planejar(atuais: dict[str, str] | None = None) -> dict:
    """O que mudaria, sem gravar nada."""
    atuais = NOMES if atuais is None else atuais
    app = _pngs(deletador.PASTA_DO_LIXO)
    hh = _pngs(deletador.PASTA_DO_LIXO_DA_HH)
    no_disco = set(app) | set(hh)
    return {
        "app": app,
        "hh": hh,
        "novos": {n: rotulo_padrao(n)
                  for n in sorted(no_disco - set(atuais), key=str.casefold)},
        "orfaos": {n: atuais[n]
                   for n in sorted(set(atuais) - no_disco, key=str.casefold)},
    }


# ===========================================================================
# EM QUE GRUPO CADA LINHA CAI -- e por que o arquivo não é mais alfabético
# ===========================================================================
#
# A ordem era a da pasta (alfabética), e isso era bom para CONFERIR: a mesma
# sequência da tela. Mas quem edita este arquivo não confere, ele ACERTA UM
# NOME -- e nessa tarefa o alfabeto espalha: "Fairy25" longe de "Fairy28",
# os 105 equipamentos (que ninguém precisa tocar) misturados com os dez itens
# que estão esperando alguém descobrir como se chamam.
#
# Pedido do usuário em 19/09/2026: *"deixe melhor organizado para ser de fácil
# entendimento para eu como desenvolvedor ajustar"*.
#
# Os grupos 1, 2 e 3 saem do NOME DO ARQUIVO, nunca de lista escrita à mão --
# uma lista dessas precisaria de manutenção a cada PNG novo e envelheceria
# calada.
#
# O GRUPO 4 PRECISOU DE UMA LISTA, e a tentativa de deduzi-lo é que mostrou por
# quê: "rótulo igual ao nome do arquivo" parecia significar "ninguém deu nome",
# e pegou 42 modelos -- porque `Hot_Stone.png` se chama "Hot Stone" mesmo. O
# que separa `SF` de `Hot Stone` não está no texto: é saber que um deles não é
# nome de nada. Isso se descobre olhando o item, então mora numa lista.
#
# A lista só MARCA o suspeito; quem confirma é a regra derivada ao lado dela
# (`humanizar(arquivo) == rotulo`). Escreveu o nome de verdade, o item sai do
# grupo sozinho -- a linha aqui pode ficar, que ela não faz mais efeito.
SEM_NOME_AINDA = {
    "SF.png",            # "Sacking Frock"? a lista de outro bot tem o item
    "charm.png",         # "Return Charm"? há três "Charm" diferentes no jogo
    "Bife.png",          # "Red Bull Steak"? "bife" é bife em português
    "DarkSM.png",        # "Dark Sm" também no outro bot -- os dois herdaram
    "Purple_Beast.png",  # é a fera ou o "Purple Beast Meat", que já existe?
}
GRUPOS = {
    1: ("EQUIPAMENTO, POR CLASSE",
        "A unidade do número é a PEÇA (2 Cuff, 3 Armguard, 4 Kneedpad, "
        "5 Boots,\n    # 6 Belt, 8 Robe) e a dezena é o TIER. Não há o que "
        "ajustar aqui:\n    # a sincronia gera todos, e o padrão nunca "
        "falha."),
    2: ("PEÇA SEM CLASSE E BOLSA",
        "O arquivo não diz a classe, então o rótulo não inventa uma."),
    3: ("ITEM COM NOME",
        "Nome conferido no site oficial, na lista de outro bot ou no jogo.\n"
        "    # É aqui que se corrige um nome errado."),
    4: ("AINDA SEM NOME -- É AQUI QUE VOCÊ ENTRA",
        "O rótulo é o próprio nome do arquivo, porque ninguém sabe o nome de\n"
        "    # verdade ainda. Viu o item no jogo? Escreva o nome aqui e ele "
        "sai\n    # desta seção sozinho na próxima sincronia."),
}


def familia(arquivo: str, rotulo: str) -> tuple[int, str, int]:
    """(grupo, chave, nível) de uma linha. Ver `GRUPOS`."""
    base = Path(arquivo).stem
    achado = re.match(r"^([A-Za-z]+?)[\s_-]*(\d+)$", base)
    if achado:
        prefixo, nivel = achado.group(1).lower(), int(achado.group(2))
        if prefixo in CLASSES:
            return (1, CLASSES[prefixo], nivel)
        if prefixo in PECAS_NO_NOME | set(NOMES_DO_JOGO) | {"amuleto"}:
            return (2, prefixo, nivel)
    if arquivo in SEM_NOME_AINDA and humanizar(arquivo) == rotulo:
        return (4, base.casefold(), 0)
    return (3, (rotulo or base).casefold(), 0)


def bloco_do_dicionario(plano: dict, atuais: dict[str, str]) -> str:
    """O texto do `NOMES` inteiro, em grupos. Ver `GRUPOS`."""
    def rotulo_de(arquivo: str) -> str:
        return atuais.get(arquivo) or plano["novos"][arquivo]

    risca = "    # " + "-" * 70
    partes = ["NOMES: dict[str, str] = {"]

    for numero in sorted(GRUPOS):
        titulo, explicacao = GRUPOS[numero]
        nomes = [n for n in plano["app"]
                 if familia(n, rotulo_de(n))[0] == numero]
        if not nomes:
            continue
        nomes.sort(key=lambda n: familia(n, rotulo_de(n))[1:])
        partes += [
            risca,
            f"    # APP / {titulo} -- {len(nomes)} modelos",
            risca,
            f"    # {explicacao}",
            *[f'    "{n}": "{rotulo_de(n)}",' for n in nomes],
            "",
        ]

    partes += [
        risca,
        f"    # LISTA DA HH -- data/templates/deletar_hh ({len(plano['hh'])} modelos)",
        risca,
        "    # Os talismãs assistentes que caem na Happiness Hall. Lista à "
        "parte porque\n    # o que é lixo numa cave é mercadoria na outra.",
        *[f'    "{n}": "{rotulo_de(n)}",' for n in plano["hh"]],
        "}",
        "",
    ]
    return "\n".join(partes)


def main() -> int:
    # O FORMATO VEM ANTES DA LISTA: o JPG convertido é uma chave nova, e o
    # plano precisa enxergá-lo já como PNG.
    for pasta in (deletador.PASTA_DO_LIXO, deletador.PASTA_DO_LIXO_DA_HH):
        convertidos, recusados = converter_para_png(pasta)
        for linha in convertidos:
            print(f"  ~ {linha}")
        for linha in recusados:
            print(f"  ! NÃO convertido: {linha}")

    plano = planejar()
    fonte = open(ARQUIVO, encoding="utf-8", newline="").read()
    inicio = fonte.index("NOMES: dict[str, str] = {")
    fim = fonte.index("\n}\n", inicio) + 3
    bloco = bloco_do_dicionario(plano, NOMES)

    # A COMPARAÇÃO É COM O TEXTO GERADO, e não só com a lista de chaves. As
    # duas coisas saem de sincronia por caminhos diferentes: a chave, quando um
    # PNG entra ou sai; a ORGANIZAÇÃO, quando alguém muda um grupo aqui neste
    # arquivo. Olhando só as chaves, a segunda nunca chegava ao dicionário.
    if not plano["novos"] and not plano["orfaos"] and fonte[inicio:fim] == bloco:
        print("Dicionário e pasta já estão em sincronia.")
        return 0

    for nome, rotulo in plano["novos"].items():
        print(f"  + {nome:<28} {rotulo}")
    for nome, rotulo in plano["orfaos"].items():
        print(f"  - {nome:<28} {rotulo}   (PNG não existe mais)")

    open(ARQUIVO, "w", encoding="utf-8", newline="").write(
        fonte[:inicio] + bloco + fonte[fim:])
    if plano["novos"] or plano["orfaos"]:
        print(f"\n{ARQUIVO}: {len(plano['novos'])} entrada(s) nova(s), "
              f"{len(plano['orfaos'])} removida(s).")
    else:
        print(f"\n{ARQUIVO}: mesmas chaves, organização regravada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
