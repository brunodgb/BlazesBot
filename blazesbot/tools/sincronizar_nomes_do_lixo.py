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

# As cinco classes do jogo, como aparecem nos nomes de arquivo. `Fada` e
# `Fairy` são a mesma classe em dois idiomas -- cada uma fica como está
# escrita, porque trocar uma pela outra seria eu decidindo o vocabulário do
# usuário.
CLASSES = {"sin": "Sin", "wizz": "Wizz", "monk": "Monk",
           "tamer": "Tamer", "fada": "Fada", "fairy": "Fairy"}

# Nomes em que a PEÇA já está escrita e a classe não aparece.
PECAS_NO_NOME = {"cuff", "belt", "knee", "ring"}


def rotulo_padrao(arquivo: str) -> str:
    """O rótulo que um PNG novo ganha. Nunca devolve vazio."""
    base = humanizar(arquivo)
    achado = re.match(r"^([A-Za-z]+?)(\d+)$", Path(arquivo).stem)
    if achado:
        palavra, numero = achado.group(1).lower(), achado.group(2)
        peca = PECA_POR_FINAL.get(numero[-1])
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


def bloco_do_dicionario(plano: dict, atuais: dict[str, str]) -> str:
    """O texto do `NOMES` inteiro, na ordem da pasta."""
    def linhas(nomes: list[str]) -> list[str]:
        return [f'    "{n}": "{atuais.get(n) or plano["novos"][n]}",'
                for n in nomes]

    risca = "    # ---------------------------------------------------------------"
    partes = [
        "NOMES: dict[str, str] = {",
        risca,
        f"    # LISTA DO APP -- data/templates/deletar ({len(plano['app'])} modelos)",
        risca,
        *linhas(plano["app"]),
        "",
        risca,
        f"    # LISTA DA HH -- data/templates/deletar_hh ({len(plano['hh'])} modelos)",
        risca,
        *linhas(plano["hh"]),
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
    if not plano["novos"] and not plano["orfaos"]:
        print("Dicionário e pasta já estão em sincronia.")
        return 0

    for nome, rotulo in plano["novos"].items():
        print(f"  + {nome:<28} {rotulo}")
    for nome, rotulo in plano["orfaos"].items():
        print(f"  - {nome:<28} {rotulo}   (PNG não existe mais)")

    fonte = open(ARQUIVO, encoding="utf-8", newline="").read()
    inicio = fonte.index("NOMES: dict[str, str] = {")
    fim = fonte.index("\n}\n", inicio) + 3
    novo = fonte[:inicio] + bloco_do_dicionario(plano, NOMES) + fonte[fim:]
    open(ARQUIVO, "w", encoding="utf-8", newline="").write(novo)
    print(f"\n{ARQUIVO}: {len(plano['novos'])} entrada(s) nova(s), "
          f"{len(plano['orfaos'])} removida(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
