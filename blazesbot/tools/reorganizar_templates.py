"""Põe os templates de `data/templates` em subpastas por FUNÇÃO.

===========================================================================
PARA QUE ISTO EXISTE
===========================================================================

A raiz de `data/templates` tinha 47 PNG soltos. O agrupamento existia, mas só
no PREFIXO do nome (`state_`, `link_`, `btn_`) -- quem abria a pasta via uma
lista, não uma estrutura.

Este script move cada um para a pasta da sua função. **Nenhum chamador muda**:
`TemplateLibrary.caminho_de` procura na raiz e depois nas
`SUBPASTAS_DE_CATEGORIA`, então `load("state_queue.png")` continua valendo
esteja o arquivo onde estiver.

===========================================================================
O QUE ELE NÃO TOCA, E POR QUÊ
===========================================================================

    `entrada/`     é outra `TemplateLibrary` (ver `bot/supervisor`), com nomes
                   que COLIDEM com os da raiz de propósito: `boss_2_fase.png`,
                   `dialogo_seta_baixo.png`, `link_enter_hh.png` e
                   `link_west_suburb.png` existem nos dois lugares, com
                   conteúdo diferente.
    `deletar/`     208 PNG que o USUÁRIO põe e tira, lidos por `glob` em
    `deletar_hh/`  `bot/deletador`. Não são código, são a lista de itens dele --
                   e `COMECE-AQUI.md` ensina a mexer nessa pasta pelo nome.
    `aprendidos/`  recortes gravados em tempo de execução por `LearnedCrops`.

===========================================================================
COMO RODAR
===========================================================================

    python -m blazesbot.tools.reorganizar_templates --dry-run   # só mostra
    python -m blazesbot.tools.reorganizar_templates             # move

É IDEMPOTENTE: rodar de novo não faz nada, porque quem já está no lugar não
aparece na lista. Um PNG novo na raiz é classificado pelo prefixo; sem prefixo
conhecido ele FICA NA RAIZ e sai no relatório -- adivinhar a categoria de um
arquivo que ninguém classificou seria esconder a decisão.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from ..core.vision.templates import SUBPASTAS_DE_CATEGORIA

PASTA = Path("data") / "templates"

# O PREFIXO DECIDE. A convenção já existia nos nomes; aqui ela vira diretório.
POR_PREFIXO: dict[str, str] = {
    "state_": "estado",     # telas e estados do cliente (login, fila, bolsa)
    "link_": "link",        # os links azuis do diálogo de NPC
    "btn_": "botao",        # botões clicáveis da interface
    "janela_": "janela",    # moldura e fechar das janelas do jogo
}

# Os que não têm prefixo. Lista fechada e explícita: são cinco, e adivinhar a
# função de um PNG pelo pixel não é trabalho de script.
POR_NOME: dict[str, str] = {
    "dialogo_seta_baixo.png": "janela",
    "cemetery_guard.png": "npc",
    "vendedor.png": "npc",
    "EnemyDead.png": "combate",
    "boss_2_fase.png": "combate",
    "package_courage.png": "item",
}


def categoria_de(nome: str) -> str | None:
    """A pasta de destino de um template. `None` = não sei, deixa na raiz."""
    if nome in POR_NOME:
        return POR_NOME[nome]
    for prefixo, pasta in POR_PREFIXO.items():
        if nome.startswith(prefixo):
            return pasta
    return None


def planejar(pasta: Path = PASTA) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Devolve (mudanças, não classificados). Só LÊ o disco."""
    mudancas: list[tuple[Path, Path]] = []
    sem_categoria: list[Path] = []
    for png in sorted(pasta.glob("*.png")):
        destino = categoria_de(png.name)
        if destino is None:
            sem_categoria.append(png)
            continue
        mudancas.append((png, pasta / destino / png.name))
    return mudancas, sem_categoria


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ensaio = "--dry-run" in argv

    if not PASTA.is_dir():
        print(f"não achei {PASTA} -- rode da raiz do projeto")
        return 1

    mudancas, sem_categoria = planejar()
    if not mudancas:
        print("nada a mover: todo template já está na pasta da função dele")
    for origem, destino in mudancas:
        print(f"  {origem.name:<34} -> {destino.parent.name}/")
        if ensaio:
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            # Mesmo nome nos dois lugares é ambiguidade, não trabalho de script:
            # só o humano sabe qual dos dois o bot usa.
            print(f"     ! {destino} já existe -- PULADO, resolva à mão")
            continue
        shutil.move(str(origem), str(destino))

    if sem_categoria:
        print("\nSEM CATEGORIA (ficaram na raiz, e é de propósito):")
        for p in sem_categoria:
            print(f"  {p.name}")
        print("  -> classifique em POR_NOME/POR_PREFIXO e rode de novo")

    print(f"\ncategorias conhecidas: {', '.join(SUBPASTAS_DE_CATEGORIA)}")
    if ensaio:
        print("ENSAIO: nada foi movido (tire o --dry-run para valer)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
