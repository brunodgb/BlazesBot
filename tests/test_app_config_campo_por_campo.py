"""
Verifica que TODO campo do `AppConfig` (fora `steps`) é transportado entre
as três camadas: o dataclass, a ponte web (`web_app.py`) e a GUI
(`account_dialog.py`).

POR QUE ESTE TESTE EXISTE
=========================

O `salvar_personagem` no `web_app.py` é uma LISTA BRANCA explícita: ele recebe
um dicionário JSON da tela e atribui campo por campo. É idêntico ao padrão de
`KeyBinds` em `test_teclas_nas_interfaces.py` — e tem o mesmo risco: colocar
o campo no dataclass, na tela e no `_app_from_dict` NÃO BASTA se a ponte web
não lê o valor de volta.

Foi exatamente isso que aconteceu com `travar_posicao` e `shuffle_apos_n_voltas`:
o campo aparecia na tela, o usuário mudava, mas o `salvar_personagem` no web_app
não lia — o valor era enviado e descartado. O teste de ida-e-volta no disco
config.json pasava (o `_app_from_dict` lijia), mas a interface web não persistia.

Nenhum teste de comportamento pegaria isso: há um campo que simplesmente não é
transportado. Por isso a verificação é estrutural — varre o código fonte.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from blazesbot.config import AppConfig

RAIZ = Path(__file__).resolve().parent.parent


def _campos_app() -> list[str]:
    """Todo campo do AppConfig, menos `steps` (estrutura própria), `enabled`
    (ligado/desligado é feito pela janela principal, não pelo editor) e campos
    internos que começam com `_` (não vão para a UI)."""
    from dataclasses import fields
    ignorados = {"steps", "enabled"}
    return [f.name for f in fields(AppConfig)
            if f.name not in ignorados and not f.name.startswith("_")]


def _ler(caminho: str) -> str:
    return (RAIZ / caminho).read_text(encoding="utf-8")


@pytest.mark.parametrize("campo", _campos_app())
def test_web_recebe_o_campo_da_tela(campo: str) -> None:
    """`salvar_personagem` no web_app.py precisa ler cada campo do payload JSON."""
    fonte = _ler("blazesbot/web_app.py")
    assert f"st.app.{campo} =" in fonte, (
        f"'{campo}' não é lido de web_app.py:salvar_personagem — o input "
        f"aceita o valor e o valor morre ali."
    )


@pytest.mark.parametrize("campo", _campos_app())
def test_gui_grava_o_campo(campo: str) -> None:
    """`_salvar` no account_dialog.py precisa atribuir cada campo."""
    fonte = _ler("blazesbot/gui/account_dialog.py")
    assert f"st.app.{campo} = " in fonte, (
        f"'{campo}' não é gravado no account_dialog.py — o checkbox/input "
        f"aceita o valor e o valor morre ali."
    )


@pytest.mark.parametrize("campo", _campos_app())
def test_gui_carrega_o_campo(campo: str) -> None:
    """`_carregar` no account_dialog.py precisa ler cada campo do dataclass."""
    fonte = _ler("blazesbot/gui/account_dialog.py")
    assert f"st.app.{campo}" in fonte, (
        f"'{campo}' não é carregado no account_dialog.py — a tela mostra sempre "
        f"o default, ignorando o valor salvo."
    )



@pytest.mark.parametrize("campo", _campos_app())
def test_web_envia_o_campo_para_a_tela(campo: str) -> None:
    """conta_editor no web_app.py precisa enviar cada campo para o frontend."""
    fonte = _ler("blazesbot/web_app.py")
    assert f'"{campo}": st.app.{campo}' in fonte, (
        f"'{campo}' não é enviado pelo conta_editor em web_app.py — a tela "
        f"mostra sempre o default, ignorando o valor salvo."
    )

def test_os_campos_sao_os_esperados() -> None:
    """Âncora: se os campos do AppConfig mudarem, este teste força uma revisão."""
    campos = _campos_app()
    assert "travar_posicao" in campos
    assert "shuffle_apos_n_voltas" in campos
    assert "apagar_lixo_a_cada" in campos
    # 'enabled' é excluído pois é ligado/desligado pela janela principal.
