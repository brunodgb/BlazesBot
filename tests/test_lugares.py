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

# Eram os nomes reais que o log mostrou FORA do catálogo -- as salas da HH. Em
# 26/09/2026 entraram nele (`lugares.AREAS_HH`); continuam aqui como a prova de
# que a regra de cara de nome aceita nome de verdade.
SALAS_DA_HH = [
    "Happiness Hall Main Hall", "Happiness Hall Visitor Room",
    "Happiness Hall Cella", "Happiness Hall Subway",
]


@pytest.mark.parametrize("lixo", LIXO_MEDIDO)
def test_o_lixo_medido_e_RECUSADO(lixo):
    assert lugares.resolver(lixo) == (None, Resolucao.RECUSADO)


@pytest.mark.parametrize("nome", SALAS_DA_HH)
def test_as_salas_da_HH_sao_do_catalogo_e_tem_cara_de_nome(nome):
    assert lugares.resolver(nome) == (nome, Resolucao.EXATO)
    assert lugares._tem_cara_de_nome(nome)


def test_nome_fora_do_catalogo_com_cara_de_nome_passa_pelo_FORMATO():
    """Nome INVENTADO de propósito: o caso é "um mapa que ainda não
    catalogamos", e nenhum dos medidos está mais fora do catálogo."""
    assert lugares.resolver("Hall of Unknown Trials") == (
        "Hall of Unknown Trials", Resolucao.FORMATO)


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
