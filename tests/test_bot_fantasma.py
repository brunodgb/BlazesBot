"""O bot é um FANTASMA: ele fala com o HWND, nunca com o mouse do usuário.

Esta é a trava do EIXO 1 (nenhuma API global de input) e do EIXO 2 (nenhum
roubo de foco), e ela vale para o PACOTE INTEIRO -- não só para o
`inputs.py`.

POR QUE O PACOTE INTEIRO, E NÃO SÓ O `inputs.py`

O `tests/test_hook_do_mouse_nao_vive_para_sempre.py` já reprovava
`SendInput`/`mouse_event`/`SetCursorPos` -- mas só dentro de
`blazesbot/core/inputs.py`. O vazamento que se quer impedir (o mouse FÍSICO do
usuário sendo puxado pelo bot) não precisa passar por lá: bastava um
`import pyautogui` no `catador.py`, no `calibracao.py` ou numa ferramenta de
`blazesbot/tools/`. O `catador.py` inclusive nasceu da adaptação de um bot que
usava `pyautogui` -- o comentário dizendo "proibido aqui" era a única coisa
segurando isso, e comentário não reprova.

O QUE É PROIBIDO, E POR QUÊ

* injeção na fila de input do SISTEMA (`SendInput`, `mouse_event`,
  `keybd_event`, `SetCursorPos`, `pyautogui`, `pynput`): o evento sai do
  barramento do Windows, ou seja acontece com o mouse e o teclado DO USUÁRIO --
  e, com N contas em paralelo, as contas ainda disputam esse barramento entre
  si.
* roubo de foco (`SetForegroundWindow`, `SetActiveWindow`, `SetFocus`,
  `BringWindowToTop`, `AttachThreadInput`): o bot precisa clicar em janela
  MINIMIZADA e em segundo plano. Trazer a janela para a frente arranca o
  usuário do que ele está fazendo e, com várias contas, elas brigam pela frente.

O QUE CONTINUA PERMITIDO, DE PROPÓSITO

* `GetCursorPos` -- LEITURA. `blazesbot/bot/teste_do_cursor.py` a usa para
  medir onde o cursor físico está durante a medição. Ler não mexe em nada.
* `ShowWindow(SW_MINIMIZE)` -- o `supervisor.py` minimiza a janela do jogo. É o
  oposto de roubar foco.
"""
from __future__ import annotations

import ast
from pathlib import Path

import blazesbot

# Nome de função do user32 (ou de biblioteca) que MEXE no input do sistema.
INJETA_NO_SISTEMA = (
    "SendInput",
    "mouse_event",
    "keybd_event",
    "SetCursorPos",
    "pyautogui",
    "pynput",
)

# Nome de função que ARRANCA a janela para o primeiro plano.
ROUBA_O_FOCO = (
    "SetForegroundWindow",
    "SetActiveWindow",
    "SetFocus",
    "BringWindowToTop",
    "AttachThreadInput",
)

RAIZ = Path(blazesbot.__file__).parent


def _nomes_usados(caminho: Path) -> set[str]:
    """Só o CÓDIGO: identificadores do AST, sem comentário nem docstring.

    Vários arquivos CITAM as APIs proibidas para explicar por que não as usam --
    o cabeçalho do `inputs.py` é o maior exemplo. Ler o texto cru reprovaria a
    documentação; ler o AST reprova o uso.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    usados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute):
            usados.add(no.attr)
        elif isinstance(no, ast.Name):
            usados.add(no.id)
        elif isinstance(no, ast.Import):
            for alias in no.names:
                usados.add(alias.name.split(".")[0])
        elif isinstance(no, ast.ImportFrom) and no.module:
            usados.add(no.module.split(".")[0])
    return usados


def _varrer(proibidos: tuple[str, ...]) -> list[tuple[str, str]]:
    achados: list[tuple[str, str]] = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        usados = _nomes_usados(arquivo)
        for nome in proibidos:
            if nome in usados:
                achados.append((str(arquivo.relative_to(RAIZ.parent)), nome))
    return achados


def test_nenhum_modulo_injeta_input_no_sistema():
    achados = _varrer(INJETA_NO_SISTEMA)
    assert not achados, (
        "estas APIs mexem no mouse/teclado DO USUÁRIO, não na janela do jogo -- "
        "todo input do bot sai por `PostMessageW`/`SendMessageW` direto para o "
        f"HWND alvo (`blazesbot/core/inputs.py`): {achados}")


def test_nenhum_modulo_rouba_o_foco():
    achados = _varrer(ROUBA_O_FOCO)
    assert not achados, (
        "o bot clica em janela MINIMIZADA e em segundo plano; trazer a janela "
        "para a frente arranca o usuário do que ele está fazendo e faz as "
        f"contas brigarem pela frente: {achados}")
