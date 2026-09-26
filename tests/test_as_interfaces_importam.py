"""As portas de entrada têm que IMPORTAR. É o teste mais bobo e o que faltava.

=========================================================================
POR QUE ELE EXISTE
=========================================================================

Nenhum teste desta suíte importava as interfaces. Consequência medida em
02/09/2026: a promoção do combate para `bot/combate.py` deixou a janela de
editar conta importando `SEGUNDOS_DA_POCAO_DE_VIDA` de `bot/bc/combat.py`, de
onde a constante havia saído. A suíte inteira passou -- 1598 testes verdes -- e
a janela simplesmente não abriria.

Um `ImportError` na porta de entrada não é bug pequeno: é o bot que não liga. E
ele é invisível para todo teste que só exercita lógica.

=========================================================================
UMA INTERFACE SÓ, DESDE 25/09/2026
=========================================================================

A PyQt6 saiu em definitivo (decisão do usuário): a interface é a web
(`blazesbot/web_app.py`, aberta pelo `3-INICIAR-WEB.bat`). A outra porta que
sobra é o CLI das ferramentas, `main.py`, que acabou de perder o `run_gui` --
exatamente o tipo de mudança que deixa um nome órfão no import.

A paridade "mexeu numa interface, mexe na outra" e os testes da tabela da PyQt
saíram com ela: três deles se PULAVAM calados sem a biblioteca, e teriam ficado
pulados para sempre.
"""
import importlib

import pytest

# `pywebview` é dependência real do projeto, mas quem roda a suíte num ambiente
# sem tela pode não tê-lo. Pular é honesto; falhar seria reprovar o ambiente.
MODULOS = [
    "blazesbot.web_app",
    "main",
]


@pytest.mark.parametrize("nome", MODULOS)
def test_a_porta_de_entrada_importa(nome):
    """Import limpo. Um nome que mudou de módulo aparece AQUI, e não no usuário."""
    try:
        importlib.import_module(nome)
    except ImportError as erro:
        # Falta a biblioteca de UI no ambiente -> pula. Falta um NOME do próprio
        # projeto -> reprova, que é o caso que este teste existe para pegar.
        texto = str(erro)
        if any(lib in texto for lib in ("webview", "pywebview")):
            pytest.skip(f"biblioteca de interface ausente no ambiente: {texto}")
        raise


def test_nenhum_modulo_do_projeto_importa_a_PyQt6():
    """A PyQt6 saiu do `requirements.txt`: um import dela é crash no próximo clone."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    fontes = [*sorted((raiz / "blazesbot").rglob("*.py")), raiz / "main.py"]
    culpados = [str(f.relative_to(raiz)) for f in fontes
                if any(linha.lstrip().startswith(("import PyQt6", "from PyQt6"))
                       for linha in f.read_text(encoding="utf-8").splitlines())]
    assert not culpados, f"ainda importam PyQt6: {culpados}"
