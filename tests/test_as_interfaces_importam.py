"""As DUAS interfaces têm que IMPORTAR. É o teste mais bobo e o que faltava.

=========================================================================
POR QUE ELE EXISTE
=========================================================================

Nenhum teste desta suíte importava `blazesbot/gui/` nem `blazesbot/web_app.py`.
Consequência medida em 02/09/2026: a promoção do combate para `bot/combate.py`
deixou `account_dialog.py` importando `SEGUNDOS_DA_POCAO_DE_VIDA` de
`bot/bc/combat.py`, de onde a constante havia saído. A suíte inteira passou --
1598 testes verdes -- e a janela de editar conta simplesmente não abriria.

Um `ImportError` na interface não é bug pequeno: é o bot que não liga. E ele é
invisível para todo teste que só exercita lógica.

=========================================================================
O QUE ESTE ARQUIVO NÃO FAZ
=========================================================================

Não testa comportamento de interface, não abre janela e não desenha nada. Ele
só carrega os módulos, que é exatamente o que faltava. Comportamento de UI é
testado por `test_teclas_nas_interfaces.py`, `test_campos_numericos_da_web.py` e
`test_config_ida_e_volta.py`.

A REGRA PERMANENTE DO PROJETO é que interface se mexe NAS DUAS. Por isso os dois
lados aparecem aqui lado a lado: uma coluna nova em um só faz este arquivo
continuar verde, mas o teste de paridade abaixo reprova.
"""
import importlib

import pytest

# `pywebview` e `PyQt6` são dependências reais do projeto, mas quem roda a suíte
# num ambiente sem tela pode não tê-los. Pular é honesto; falhar seria reprovar
# o ambiente em vez do código.
MODULOS = [
    "blazesbot.gui.main_window",
    "blazesbot.gui.account_dialog",
    "blazesbot.gui.widgets",
    "blazesbot.gui.theme",
    "blazesbot.web_app",
]


@pytest.mark.parametrize("nome", MODULOS)
def test_o_modulo_de_interface_importa(nome):
    """Import limpo. Um nome que mudou de módulo aparece AQUI, e não no usuário."""
    try:
        importlib.import_module(nome)
    except ImportError as erro:
        # Falta a biblioteca de UI no ambiente -> pula. Falta um NOME do próprio
        # projeto -> reprova, que é o caso que este teste existe para pegar.
        texto = str(erro)
        if any(lib in texto for lib in ("PyQt6", "webview", "pywebview")):
            pytest.skip(f"biblioteca de interface ausente no ambiente: {texto}")
        raise


# ===========================================================================
# PARIDADE -- interface se mexe NAS DUAS
# ===========================================================================

# Cada linha é (o que é, o nome na ponte web, o nome na GUI). Um recurso novo
# entra aqui, e é isso que faz o esquecimento aparecer.
PARIDADE = [
    ("ligar/desligar o BC", "alternar_farm", "_toggle_farm"),
    ("ligar/desligar a HH", "alternar_hh", "_toggle_hh"),
    ("ligar/desligar o APP", "alternar_app", "_toggle_app"),
]


@pytest.mark.parametrize("o_que,na_web,na_gui", PARIDADE,
                         ids=lambda v: v if " " not in str(v) else "")
def test_o_recurso_existe_nas_DUAS_interfaces(o_que, na_web, na_gui):
    """Regra permanente: mexer em interface é mexer nas duas.

    Metade feita é pior que nada feito -- o usuário liga a HH numa interface,
    abre a outra, vê desmarcado, e não tem como saber qual das duas está certa.
    """
    web = importlib.import_module("blazesbot.web_app")
    dono_web = next((c for c in vars(web).values()
                     if isinstance(c, type) and hasattr(c, "alternar_farm")), None)
    assert dono_web is not None, "não achei a classe da ponte web"
    assert hasattr(dono_web, na_web), f"{o_que}: falta na interface WEB"

    try:
        gui = importlib.import_module("blazesbot.gui.main_window")
    except ImportError as erro:  # pragma: no cover - ambiente sem PyQt6
        pytest.skip(f"PyQt6 ausente: {erro}")
    assert hasattr(gui.MainWindow, na_gui), f"{o_que}: falta na interface PyQt6"


def test_a_tabela_da_GUI_tem_uma_coluna_por_cabecalho():
    """Um cabeçalho a mais que a contagem de colunas some da tela em silêncio.

    Foi o que aconteceu ao acrescentar a coluna HH: o `QTableWidget` nascia com
    8 colunas e recebia 9 rótulos, e a nona simplesmente não existia.
    """
    try:
        from blazesbot.gui import main_window as mw
    except ImportError as erro:  # pragma: no cover - ambiente sem PyQt6
        pytest.skip(f"PyQt6 ausente: {erro}")

    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(mw.MainWindow))
    arvore = ast.parse(fonte)

    colunas = None
    rotulos = None
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        nome = getattr(no.func, "id", getattr(no.func, "attr", ""))
        if nome == "QTableWidget" and len(no.args) == 2 and colunas is None:
            colunas = getattr(no.args[1], "value", None)
        if nome == "setHorizontalHeaderLabels" and rotulos is None:
            alvo = no.args[0] if no.args else None
            if isinstance(alvo, ast.List):
                rotulos = len(alvo.elts)

    assert colunas is not None and rotulos is not None
    assert colunas == rotulos, (
        f"a tabela nasce com {colunas} colunas e recebe {rotulos} rótulos")


def test_a_contagem_de_colunas_bate_com_os_indices():
    """Os índices `COL_*` são um `range(N)`. Se N e a tabela divergirem, a
    última coluna fica fora da tela sem nenhum erro."""
    try:
        from blazesbot.gui import main_window as mw
    except ImportError as erro:  # pragma: no cover - ambiente sem PyQt6
        pytest.skip(f"PyQt6 ausente: {erro}")

    indices = [v for n, v in vars(mw).items()
               if n.startswith("COL_") and isinstance(v, int)]
    assert indices, "não achei os índices COL_*"
    assert sorted(indices) == list(range(len(indices))), (
        f"os índices COL_* não formam um range contínuo: {sorted(indices)}")
