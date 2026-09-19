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
3. SEM CONSOLE — e o que isso obriga
=========================================================================

*"Preferia que fosse só o bot aberto"* (usuário, 19/09/2026). O pacote é
`--windowed`, então **não existe terminal**. E num programa empacotado sem
console o Python põe `sys.stdout` e `sys.stderr` em `None`: o
`StreamHandler(sys.stdout)` que o `setup_logging` cria passaria a falhar em
toda linha de log, e o traceback de uma queda não teria para onde ir.

As duas coisas que isso obriga, e que estão aqui embaixo:

* **A saída vai para `logs/console.txt`.** Não é só evitar o erro: é o mesmo
  texto que aparecia no terminal, agora num arquivo que dá para mandar.
* **A queda vira uma CAIXA DE MENSAGEM.** Sem console não há onde piscar um
  traceback, e "não abriu" sem mais nada foi exatamente o que aconteceu na
  primeira entrega -- este arquivo chamava um `main` que não existe em
  `web_app` (o nome certo é `_main`), e o ImportError morreu antes de qualquer
  log. A caixa diz onde está o arquivo com o detalhe.
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _redirecionar_a_saida() -> None:
    """Sem console, `sys.stdout` é `None`. Aponta os dois para um arquivo.

    ANTES DE QUALQUER IMPORT DO BOT: `setup_logging` guarda `sys.stdout` no
    handler, então trocar depois não teria efeito nenhum.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        pasta = Path.cwd() / "logs"
        pasta.mkdir(exist_ok=True)
        saida = (pasta / "console.txt").open("a", encoding="utf-8",
                                             buffering=1)
        saida.write(f"\n{'=' * 70}\n{datetime.now():%d/%m/%Y %H:%M:%S}  "
                    f"BlazesBot iniciando\n")
        sys.stdout = sys.stderr = saida
    except Exception:
        pass                     # sem log é ruim; não abrir por causa disso é pior


def _avisar_na_tela(texto: str) -> None:
    """Uma caixa do Windows. É o que sobra quando não há console."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, texto, "BlazesBot", 0x10)
    except Exception:
        pass


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
    empacotado = getattr(sys, "frozen", False)
    if empacotado:
        os.chdir(Path(sys.executable).resolve().parent)
        _redirecionar_a_saida()
    try:
        from blazesbot.web_app import _main as abrir_a_interface

        abrir_a_interface()
        return 0
    except SystemExit as saida:
        # `require_admin` sai por aqui quando falta elevação. Empacotado isso
        # seria um clique sem NADA na tela -- o `.exe` traz o manifesto de
        # administrador, então só acontece se alguém tirar o manifesto.
        if empacotado and (saida.code or 0) != 0:
            _avisar_na_tela(
                "O BlazesBot fechou logo ao abrir.\n\n"
                "Quase sempre é falta de permissão: clique com o botão "
                "direito e escolha 'Executar como administrador'.\n\n"
                f"O detalhe fica em:\n{Path.cwd() / 'logs' / 'console.txt'}")
        raise
    except BaseException as erro:
        traceback.print_exc()
        arquivo = _registrar_a_queda(erro)
        print("\n" + "=" * 70)
        print("  O BlazesBot não conseguiu abrir.")
        if arquivo is not None:
            print(f"  O que aconteceu está em: {arquivo}")
        print("=" * 70)
        if empacotado:
            _avisar_na_tela(
                "O BlazesBot não conseguiu abrir.\n\n"
                f"{type(erro).__name__}: {erro}\n\n"
                "O detalhe completo (com o traceback) está em:\n"
                f"{arquivo or (Path.cwd() / 'logs')}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
