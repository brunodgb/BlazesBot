"""O PONTO DE PARTIDA DO `.exe` — só troca o diretório e chama a interface web.

Existe por UMA razão, e ela é fácil de não enxergar: o Windows lança um
programa com o diretório de trabalho de QUEM lançou, não com o do programa.
Clicando no `.exe` pelo Explorer costuma dar na mesma pasta, mas um atalho na
área de trabalho, o "Executar como administrador" e a caixa Executar dão em
`C:\\Windows\\System32`.

E quase todo caminho de dado deste bot é RELATIVO (`Path("data") / "templates"`,
`data/config.json`): com o diretório errado, o bot sobe, não acha template
nenhum e não apaga, não loga e não vê nada — **calado**, que é o pior jeito de
falhar. Uma linha de `chdir` fecha isso para todos de uma vez.

Fora do empacotamento este arquivo não faz nada: quem roda do código-fonte usa
o `3-INICIAR-WEB.bat`, que já entra na pasta certa (`cd /d "%~dp0"`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).resolve().parent)
    from blazesbot.web_app import main as abrir_a_interface

    return abrir_a_interface() or 0


if __name__ == "__main__":
    raise SystemExit(main())
