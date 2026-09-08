"""O tema claro: a barra de título acompanha, e nenhuma cor fica presa.

=========================================================================
O QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

1. A BARRA DE TÍTULO NO TEMA ERRADO. `--color-cab` não era redefinido em
   `:root[data-tema="claro"]`, então a barra ficava no #150807 do tema escuro
   sobre uma interface clara. Os botões dela usam `--color-ink`, que no claro é
   ESCURO -- minimizar e fechar viravam texto escuro sobre fundo escuro e
   DESAPARECIAM. Visto na tela pelo usuário.

2. COR FIXA NO NOME. O "BlazesBot" da barra era `text-white`: no tema claro
   sumia. O ÍCONE ao lado não muda de propósito -- ele é a identidade e tem
   contraste próprio nos dois temas.

3. COR PRESA NO TEMA ANTERIOR. Quando a cor vem de `var(--color-ink)` e essa
   variável troca no `:root`, o Blink NÃO reavalia uma propriedade que está na
   lista de transições: a transição não dispara e o valor ANTIGO fica. Medido na
   troca para o claro: ✕ e — presos em #f7f5f5 sobre a barra clara, e mais de
   200 outros elementos na mesma situação (`nav-item`, `bt`, `cel-texto`,
   `cel-opt`). A assinatura do defeito é que `transition: none` no mesmo
   elemento faz o valor certo aparecer na hora.

   O conserto é UM, no ponto da troca: as transições saem por um quadro. Tirar
   `color` de cada regra seria o mesmo conserto repetido em dezenas de lugares,
   e a próxima regra nova nasceria com o defeito.

Ver `docs/decisoes/interface.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CSS = (RAIZ / "web" / "style.css").read_text(encoding="utf-8")
JS = (RAIZ / "web" / "main.js").read_text(encoding="utf-8")
HTML = (RAIZ / "web" / "index.html").read_text(encoding="utf-8")


def _bloco_do_tema_claro() -> str:
    return CSS.split(':root[data-tema="claro"] {')[1].split("}")[0]


def test_o_tema_claro_redefine_a_barra_de_titulo():
    assert "--color-cab:" in _bloco_do_tema_claro(), (
        "sem `--color-cab` a barra fica no tom do tema escuro")


def test_todo_token_de_FUNDO_tem_versao_clara():
    """Um fundo sem versão clara é uma área da tela que fica no tema errado --
    e o defeito é silencioso: nada avisa, só se vê."""
    claro = _bloco_do_tema_claro()
    for token in ("--color-cab", "--color-deep", "--color-surface",
                  "--color-panel", "--color-panel2"):
        assert f"{token}:" in claro, f"{token} não tem versão clara"


def test_o_nome_na_barra_NAO_tem_cor_fixa():
    barra = HTML.split('class="titlebar')[1].split("</header>")[0]
    nome = [linha for linha in barra.splitlines() if "BlazesBot</span>" in linha]
    assert nome, "o nome saiu da barra"
    assert "text-white" not in nome[0], "cor fixa: o nome sumia no tema claro"
    assert "text-ink" in nome[0]


def test_a_troca_de_tema_DESLIGA_as_transicoes():
    assert ":root.trocando-tema *," in CSS
    bloco = CSS.split(":root.trocando-tema *::after {")[1].split("}")[0]
    assert "transition: none !important" in bloco

    handler = JS.split('$("#btn-tema").addEventListener("click"')[1]
    # SEM OS COMENTÁRIOS: o que explica o conserto CITA `requestAnimationFrame`,
    # e contar as ocorrências no texto todo somaria a documentação.
    handler = "\n".join(l for l in handler.split("});")[0].splitlines()
                        if not l.lstrip().startswith("//"))
    assert 'classList.add("trocando-tema")' in handler
    assert 'classList.remove("trocando-tema")' in handler
    # DOIS quadros: no primeiro o tema acabou de mudar, e tirar a classe ali
    # devolveria a transição para o mesmo quadro da troca.
    assert handler.count("requestAnimationFrame") == 2, (
        "um `requestAnimationFrame` só não atravessa o quadro da troca")
    assert handler.index('classList.add("trocando-tema")') < handler.index(
        "raiz.dataset.tema ="), "a classe tem de entrar ANTES da troca"


def test_a_classe_sai_do_HTML_e_nao_fica_grudada():
    """Classe esquecida no `<html>` mata TODA transição da interface -- e isso
    não dá erro nenhum, a tela só fica seca."""
    assert 'classList.add("trocando-tema")' in JS
    assert JS.count('classList.remove("trocando-tema")') >= JS.count(
        'classList.add("trocando-tema")')
    assert "trocando-tema" not in re.sub(r"<!--.*?-->", "", HTML, flags=re.S), (
        "a classe é de tempo de execução, nunca do markup")
