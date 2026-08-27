"""Toda tecla do `KeyBinds` tem que existir NAS DUAS INTERFACES, nos dois sentidos.

POR QUE ESTE TESTE EXISTE
=========================

A ponte web não serializa o dataclass: ela tem uma **lista branca explícita** em
cada sentido -- um dicionário que monta o payload para a tela e uma sequência de
`st.keys.X = ...` que lê o payload de volta. A GUI tem o mesmo par
(`set_key` / atribuição).

Isso significa que adicionar um campo ao `KeyBinds` e ao HTML **não basta**, e a
falha é silenciosa do pior jeito: o input aparece na tela, aceita a tecla, e o
valor nunca sai dali. Foi exatamente o que aconteceu com `hotbar_page_1` --
funcionava no disco, na GUI e no core, e não gravava pela web.

Nenhum teste de comportamento pegaria isso, porque não há comportamento errado:
há um campo que simplesmente não é transportado. Por isso a verificação é
estrutural.
"""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from blazesbot.config import KeyBinds

RAIZ = Path(__file__).resolve().parent.parent
TECLAS = [f.name for f in fields(KeyBinds)]


def _ler(caminho: str) -> str:
    return (RAIZ / caminho).read_text(encoding="utf-8")


@pytest.mark.parametrize("tecla", TECLAS)
def test_web_envia_a_tecla_para_a_tela(tecla: str) -> None:
    """O payload que a ponte monta precisa citar o campo."""
    fonte = _ler("blazesbot/web_app.py")
    assert f'"{tecla}": k.{tecla}' in fonte or f'"{tecla}": ' in fonte, (
        f"'{tecla}' não é enviado ao frontend em web_app.py -- o campo vai "
        f"aparecer vazio na tela por mais que esteja salvo no config.json."
    )


@pytest.mark.parametrize("tecla", TECLAS)
def test_web_recebe_a_tecla_da_tela(tecla: str) -> None:
    """E a volta: sem isto o usuário digita e nada é gravado."""
    fonte = _ler("blazesbot/web_app.py")
    assert f"st.keys.{tecla} =" in fonte, (
        f"'{tecla}' não é lido do payload em web_app.py -- o input aceita a "
        f"tecla e o valor morre ali."
    )


@pytest.mark.parametrize("tecla", TECLAS)
def test_frontend_mapeia_a_tecla(tecla: str) -> None:
    """`CAMPO_TECLA` no main.js serve aos DOIS sentidos (preenche e coleta)."""
    fonte = _ler("web/main.js")
    assert f'"{tecla}"' in fonte, (
        f"'{tecla}' não está em CAMPO_TECLA no web/main.js."
    )


@pytest.mark.parametrize("tecla", TECLAS)
def test_gui_carrega_e_grava_a_tecla(tecla: str) -> None:
    """A GUI PyQt6 tem o mesmo par, e a regra permanente exige as duas telas."""
    fonte = _ler("blazesbot/gui/account_dialog.py")
    assert f"k.{tecla})" in fonte or f"k.{tecla}]" in fonte, (
        f"'{tecla}' não é carregado no account_dialog.py (falta o set_key)."
    )
    assert f"k.{tecla} = " in fonte, (
        f"'{tecla}' não é gravado no account_dialog.py (falta a atribuição)."
    )


def test_a_tecla_da_hotbar_existe() -> None:
    """Âncora: se este campo sumir, os testes acima passariam vazios."""
    assert "hotbar_page_1" in TECLAS
    assert KeyBinds().hotbar_page_1 == "", (
        "O padrão tem que ser VAZIO: sem tecla o bot volta aos dois cliques "
        "no botão de subir, que é o comportamento medido."
    )


def test_padrao_nao_tem_tecla_repetida() -> None:
    """O jogo não aceita a mesma tecla em duas funções -- nem a config padrão."""
    assert KeyBinds().teclas_repetidas() == []
