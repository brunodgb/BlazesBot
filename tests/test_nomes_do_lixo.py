"""O NOME QUE O USUÁRIO LÊ na janela de itens do deletador — 18/09/2026.

Duas fontes, nesta ordem: o dicionário que o desenvolvedor preenche e, sem
entrada, o nome do arquivo normalizado. O que estes testes protegem:

    NUNCA VAZIO          -- a janela sempre mostra alguma coisa
    NÃO ADIVINHA         -- `AlmOre` não vira "Alm Ore"; só separa onde JÁ há
                            separador (pedido do usuário)
    A EXTENSÃO SAI ANTES -- senão o ponto vira espaço e tudo termina em " png"
    BUSCA TOLERANTE      -- com ou sem `.png`, ignorando maiúsculas, porque o
                            dicionário é digitado à mão
"""
from __future__ import annotations

from pathlib import Path

import pytest

from blazesbot.bot import nomes_do_lixo as n


@pytest.mark.parametrize("arquivo, esperado", [
    # Onde JÁ existe separador, ele vira espaço.
    ("Blue-bell.png", "Blue bell"),
    ("Black_Shadow_stone.png", "Black Shadow stone"),
    ("Blue_Wolf_Meat.png", "Blue Wolf Meat"),
    ("Trap-Meshwork.png", "Trap Meshwork"),
    # A MAIÚSCULA NO MEIO TAMBÉM SEPARA -- reversão de 19/09/2026. A regra
    # anterior se recusava a isso "para não estragar `BAG7` e `bag3`", e o medo
    # era infundado: o corte é entre MINÚSCULA e MAIÚSCULA, fronteira que não
    # existe nesses dois.
    ("SpinelOre.png", "Spinel Ore"),
    ("AlmOre.png", "Alm Ore"),
    ("BambShoot.png", "Bamb Shoot"),
    ("CrackBB.png", "Crack BB"),
    ("DarkSM.png", "Dark SM"),
    # E continua sem inventar quebra onde não há fronteira nenhuma.
    ("BAG7.png", "BAG7"),
    ("bag3.png", "bag3"),
    ("Amuleto39.png", "Amuleto39"),
    # A extensão sai antes da troca: senão sobra um " png" em todo item.
    ("Bag.png", "Bag"),
])
def test_o_nome_do_arquivo_virando_texto(arquivo, esperado):
    """Exercita `humanizar` DIRETO, e não `rotulo`: o dicionário hoje cobre a
    pasta inteira, então por `rotulo` estes casos testariam a tabela, não a
    regra que atende PNG novo."""
    assert n.humanizar(arquivo) == esperado


def test_separadores_repetidos_viram_UM_espaco():
    assert n.rotulo("Couro__de---Lobo.png") == "Couro de Lobo"


def test_nome_so_de_pontuacao_devolve_o_original():
    """A janela nunca mostra um cartão sem nome."""
    assert n.rotulo("___.png") == "___"


def test_o_dicionario_VENCE_o_nome_do_arquivo(monkeypatch):
    monkeypatch.setitem(n._INDICE, "blue_wolf_meat", "Carne de Lobo Azul")
    assert n.rotulo("Blue_Wolf_Meat.png") == "Carne de Lobo Azul"


@pytest.mark.parametrize("como_foi_digitado", [
    "Blue_Wolf_Meat.png", "Blue_Wolf_Meat", "blue_wolf_meat.PNG",
    "BLUE_WOLF_MEAT.png",
])
def test_a_busca_e_tolerante(monkeypatch, como_foi_digitado):
    """O dicionário é digitado à mão, uma linha por vez: exigir o nome exato,
    com extensão e maiúsculas certas, é combinar de falhar em silêncio."""
    monkeypatch.setitem(n._INDICE, "blue_wolf_meat", "Carne de Lobo Azul")
    assert n.rotulo(como_foi_digitado) == "Carne de Lobo Azul"


def test_o_indice_nasce_do_dicionario():
    """Se alguém acrescentar em `NOMES` e o índice não for regerado, o nome
    novo nunca aparece -- e ninguém descobre, porque o nome do arquivo cobre."""
    for chave, valor in n.NOMES.items():
        assert n._INDICE[Path(chave).stem.casefold()] == valor


@pytest.mark.parametrize("pasta", ["deletar", "deletar_hh"])
def test_TODO_modelo_de_verdade_tem_um_nome(pasta):
    """Integração com a pasta real: 223 arquivos, nenhum cartão sem rótulo."""
    caminho = Path(__file__).resolve().parent.parent / "data" / "templates" / pasta
    if not caminho.is_dir():
        pytest.skip(f"{pasta} não existe nesta instalação")
    for png in caminho.glob("*.png"):
        assert n.rotulo(png.name).strip(), png.name
