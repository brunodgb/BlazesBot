"""Toda tecla do `KeyBinds` tem que existir NA INTERFACE, nos dois sentidos.

POR QUE ESTE TESTE EXISTE
=========================

A ponte web não serializa o dataclass: ela tem uma **lista branca explícita** em
cada sentido -- um dicionário que monta o payload para a tela e uma sequência de
`st.keys.X = ...` que lê o payload de volta.

Isso significa que adicionar um campo ao `KeyBinds` e ao HTML **não basta**, e a
falha é silenciosa do pior jeito: o input aparece na tela, aceita a tecla, e o
valor nunca sai dali. Foi exatamente o que aconteceu com `hotbar_page_1` --
funcionava no disco e no core, e não gravava pela web.

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
def test_o_dist_COMPILADO_tem_o_campo(tecla: str) -> None:
    """O que roda na tela é `dist/`, não `web/` -- 04/09/2026.

    Esta é a irmã do defeito que este arquivo já pegava. Lá, o input aparecia e
    o valor não saía; aqui, o input **nem aparece**: a janela do bot abre
    `dist/index.html`, que é o Vite compilado, e mexer no `web/index.html` sem
    rodar `npm run build` não muda nada do que o usuário vê.

    Foi exatamente o que aconteceu com `revive_skill`: campo no HTML, mapeado
    no main.js, transportado pela ponte nos dois sentidos, todos os testes
    verdes -- e a aba Teclas na tela continuava sem ele.

    `dist/` é gerado e está no .gitignore, então o teste PULA quando não existe
    (clone novo, CI). Ele não cobra o build; cobra que o build feito esteja em
    dia com o HTML.
    """
    dist = RAIZ / "dist" / "index.html"
    if not dist.exists():
        pytest.skip("dist/ não foi compilado nesta cópia")
    campo = f'ed-k-{tecla.replace("_skill", "").replace("_", "-")}'
    fonte = dist.read_text(encoding="utf-8")
    origem = _ler("web/index.html")
    if campo not in origem:
        pytest.skip(f"{tecla} não usa o id {campo} no web/index.html")
    assert campo in fonte, (
        f"'{campo}' está no web/index.html e NÃO no dist/ compilado. "
        f"Rode `npm run build` -- a tela do bot lê o dist, não o web."
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
