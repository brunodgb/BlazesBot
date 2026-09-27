"""A vizinhança conta MOB VIVO, não toda entidade -- pet e companheiro não são mob.

Achado A4 da auditoria de 27/09/2026. `contar` usava `entidades_vivas()`, que
aceita vida máxima de 1 a 5.000.000 e vida zero: o próprio pet, os jogadores
do time e os cadáveres contavam como "mob vivo". Com 4 contas APP empilhadas no
mesmo ponto, 221 de 246 ERROR "TAB sem resposta... HÁ N mob(s) vivo(s)" em 40 h
tinham o "mob" a 1 unidade -- o companheiro. O ERROR mentia e a guarda "spot
vazio não conta" do teclado mudo nunca atuava.

`resumo` NÃO muda: ele descreve a vizinhança no log da morte e lista tudo de
propósito (docs/decisoes/sistema.md).
"""
import pytest

from blazesbot.core import vizinhanca


class _Memoria:
    def __init__(self, entidades):
        self._entidades = entidades

    def position(self):
        return (100, 100)

    def entidades_vivas(self):
        return self._entidades


PET = {"pos": (101, 100), "hp": 243, "max_hp": 243, "nome": "o pet"}
COMPANHEIRO = {"pos": (100, 101), "hp": 729, "max_hp": 729, "nome": "Wizz"}
CADAVER = {"pos": (102, 100), "hp": 0, "max_hp": 100, "nome": "Guly morto"}
MOB = {"pos": (110, 100), "hp": 60, "max_hp": 100, "nome": "Guly Horn Horse"}


def test_pet_companheiro_e_cadaver_NAO_sao_mob():
    assert vizinhanca.contar(_Memoria([PET, COMPANHEIRO, CADAVER])) == (0, None)


def test_mob_vivo_conta_e_da_a_distancia_certa():
    quantos, perto = vizinhanca.contar(_Memoria([PET, COMPANHEIRO, CADAVER, MOB]))
    assert quantos == 1
    assert perto == pytest.approx(10.0)


def test_o_resumo_da_morte_continua_listando_todo_mundo():
    texto = vizinhanca.resumo(_Memoria([PET, MOB]))
    assert "o pet" in texto and "Guly Horn Horse" in texto
