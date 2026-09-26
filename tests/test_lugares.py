"""O NOME DO LUGAR LIDO DA MEMÓRIA: o que é nome, e o que é lixo.

Os conjuntos abaixo são MEDIDOS (26/09/2026, 42.770 leituras do log de dev),
não inventados: o lixo é o que o filtro de formato deixava passar, e os nomes
fora do catálogo são os que o log mostrou de verdade.
"""
import pytest

from blazesbot.core import lugares
from blazesbot.core.lugares import Resolucao

LIXO_MEDIDO = [
    "D5vl", "U" * 32, "hCKD", "PV8", "pV8V8PY", "pV8", "ase try later again.",
    "CPC", "CVC", "nCUCh", "XCkC-", "C0jC", "r 70 copper", "PgaCXC",
    "POaCHiaCB", "CZC", "HKaC", "XDYD4-", "CaC-", "C0WCh", "CHC", "jCjC-",
    "kCC", "kChjCS", "vaC", "jCjC", "PuX", "HxH", "ECxECB", "AVVTT", "UdU",
    "BBA", "THT", "ZRw", "TBHNT",
]

REAIS_FORA_DO_CATALOGO = [
    "Happiness Hall Main Hall", "Happiness Hall Visitor Room",
    "Happiness Hall Cella", "Happiness Hall Subway",
]


@pytest.mark.parametrize("lixo", LIXO_MEDIDO)
def test_o_lixo_medido_e_RECUSADO(lixo):
    assert lugares.resolver(lixo) == (None, Resolucao.RECUSADO)


@pytest.mark.parametrize("nome", REAIS_FORA_DO_CATALOGO)
def test_nome_real_fora_do_catalogo_passa_pelo_FORMATO(nome):
    assert lugares.resolver(nome) == (nome, Resolucao.FORMATO)


def test_todo_nome_do_catalogo_tem_a_cara_que_o_FORMATO_exige():
    """Se um nome de verdade não tem, a regra está apertada demais -- e um lugar
    novo com o mesmo jeito seria recusado em silêncio."""
    catalogo = set(lugares._POR_MINUSCULA.values())
    assert catalogo
    assert [n for n in catalogo if not lugares._tem_cara_de_nome(n)] == []


def test_conectivo_minusculo_no_meio_e_nome():
    assert lugares._tem_cara_de_nome("East of Simen Mountain")


def test_o_nome_cortado_do_catalogo_continua_completado():
    """A regra nova é só do FORMATO: a cauda do catálogo vem antes dela."""
    assert lugares.resolver("8tcher Cave") == ("Bewitcher Cave", Resolucao.PARCIAL)
