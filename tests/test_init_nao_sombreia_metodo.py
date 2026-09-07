"""Atributo com nome de método vira bool — e o método some sem avisar.

O DEFEITO, MEDIDO EM 06/09/2026: `Navigator.__init__` guardava
`self._dentro_da_cave = False`, e depois nasceu um MÉTODO com o mesmo nome. O
atributo da instância sombreia o método da classe, então
`self._dentro_da_cave()` virou `False()`:

    TypeError: 'bool' object is not callable
      navegacao.py, linha 1985, em garantir_montaria_para_andar
        if ciclo >= CICLOS_ANTES_DE_IR_A_PE and not self._dentro_da_cave():

**55 ocorrências no log**, nas fases `CURAR` e `ATE_O_ALTAR` — o portão da
montaria estourava toda vez que chegava no ciclo da desistência, derrubando o
estado inteiro para `RECUPERAR`. E o atributo era **escrito e nunca lido**: era
código morto que só servia para apagar um método.

Nada nesse par gritava. O `__init__` é válido, o método é válido, e o único
lugar onde os dois se encontram é em tempo de execução, no ciclo 20 de um
portão que quase nunca chega lá.
"""
import ast
import inspect
import textwrap

import pytest

from blazesbot.bot.navegacao import Navigator

# As classes que este teste vigia. Não é a lista de todas as classes do projeto
# de propósito: são as que têm `__init__` gordo E muitos métodos privados, que é
# onde a colisão acontece sem ninguém ver.
CLASSES = [Navigator]


def _atribuidos_no_init(classe) -> set[str]:
    """Os `self.X = ...` do `__init__`, por AST."""
    fonte = textwrap.dedent(inspect.getsource(classe.__init__))
    arvore = ast.parse(fonte)
    nomes = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if (isinstance(alvo, ast.Attribute)
                    and isinstance(alvo.value, ast.Name)
                    and alvo.value.id == "self"):
                nomes.add(alvo.attr)
    return nomes


@pytest.mark.parametrize("classe", CLASSES, ids=lambda c: c.__name__)
def test_o_init_nao_sombreia_metodo_nenhum(classe):
    metodos = {
        nome for nome, valor in vars(classe).items()
        if callable(valor) and not isinstance(valor, (property, staticmethod))
    }
    colisoes = sorted(_atribuidos_no_init(classe) & metodos)
    assert not colisoes, (
        f"{classe.__name__}.__init__ atribui {colisoes}, e a classe tem método "
        f"com o mesmo nome. O atributo VENCE, o método some, e chamar vira "
        f"`TypeError: '<tipo>' object is not callable` — em tempo de execução, "
        f"no caminho que menos roda."
    )


def test_dentro_da_cave_continua_sendo_CHAMAVEL():
    """O caso concreto que derrubou 55 estados.

    `object.__new__` de propósito: é o `__init__` que criava o atributo, e o
    teste tem de provar que a instância recém-nascida também responde.
    """
    nav = object.__new__(Navigator)
    assert callable(nav._dentro_da_cave), (
        "`_dentro_da_cave` deixou de ser chamável — o portão da montaria "
        "estoura no ciclo de `CICLOS_ANTES_DE_IR_A_PE`")
