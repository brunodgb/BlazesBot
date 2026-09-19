"""O PONTO DE PARTIDA DO `.exe` — diretório certo, e nenhuma falha calada.

=========================================================================
1. O DIRETÓRIO
=========================================================================

O Windows lança um programa com o diretório de trabalho de QUEM lançou, não
com o do programa. Clicando no `.exe` pelo Explorer costuma dar na mesma pasta,
mas um atalho na área de trabalho, o "Executar como administrador" e a caixa
Executar dão em `C:\\Windows\\System32`.

E quase todo caminho de dado deste bot é RELATIVO (`Path("data") / "templates"`,
`data/config.json`): com o diretório errado, o bot sobe, não acha template
nenhum e não apaga, não loga e não vê nada — **calado**, que é o pior jeito de
falhar. Uma linha de `chdir` fecha isso para todos de uma vez.

=========================================================================
2. A PORTA DE ENTRADA É A MESMA DO `.bat`
=========================================================================

`web_app._main()`, e não o `run()` direto: ele confere a elevação e monta o
log ANTES de abrir a janela. São as duas coisas que fazem a diferença entre
"não funcionou" e "diz por que não funcionou".

=========================================================================
3. O ERRO PRECISA SOBREVIVER À JANELA QUE FECHA
=========================================================================

Aconteceu em 19/09/2026, na primeira entrega: este arquivo chamava um
`main` que não existe em `web_app` (o nome certo é `_main`), e o usuário viu
só *"ao executar o .exe não está abrindo"*. Elevado, o console é uma janela
NOVA: ela nasce com o processo e morre com ele, então o traceback pisca e some.

Por isso o `except` daqui grava `logs/erro-ao-abrir.txt` e ainda espera uma
tecla. Quem estiver testando consegue mandar o arquivo; sem isso, a única
informação que volta é "não abre".
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _registrar_a_queda(erro: BaseException) -> Path | None:
    """Grava o traceback ao lado do `.exe`. `None` = nem isso deu."""
    try:
        pasta = Path.cwd() / "logs"
        pasta.mkdir(exist_ok=True)
        arquivo = pasta / "erro-ao-abrir.txt"
        with arquivo.open("a", encoding="utf-8") as fh:
            fh.write(f"\n{'=' * 70}\n{datetime.now():%d/%m/%Y %H:%M:%S}\n")
            fh.write(f"executável: {sys.executable}\n")
            fh.write(f"pasta: {Path.cwd()}\n\n")
            traceback.print_exception(type(erro), erro, erro.__traceback__,
                                      file=fh)
        return arquivo
    except Exception:
        return None


def main() -> int:
    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).resolve().parent)
    try:
        from blazesbot.web_app import _main as abrir_a_interface

        abrir_a_interface()
        return 0
    except BaseException as erro:            # inclui SystemExit do require_admin
        if isinstance(erro, SystemExit):
            raise
        traceback.print_exc()
        arquivo = _registrar_a_queda(erro)
        print()
        print("=" * 70)
        print("  O BlazesBot não conseguiu abrir.")
        if arquivo is not None:
            print(f"  O que aconteceu está em: {arquivo}")
        print("=" * 70)
        if getattr(sys, "frozen", False):
            # A JANELA NÃO PODE FECHAR ANTES DE SER LIDA. Elevado, este console
            # é uma janela nova que morre junto com o processo.
            try:
                input("\nEnter para fechar. ")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
