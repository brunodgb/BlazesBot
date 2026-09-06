"""O ALVO CAIU: o HP manda dentro da volta, a saída de batalha manda no fim.

Decisão do usuário em 06/09/2026, depois de ver os logs:

> *"Pelo que pude ver, a identificação do HP do target está muito funcional (...)
> tendo essa confirmação podemos usar isso no APP para saber quando o mob morreu
> e esse ser a base de troca, mas claro, as verificações ainda só devem
> acontecer fora de batalha, que deve acontecer em no máximo 2 segundos após
> matar o mob; caso não saia é pq ainda tem algum mob atacando."*

E, sobre o conflito entre as duas fontes:

> *"Se ainda diz 'mob vivo' mas saiu de batalha, é pq a leitura está errada e o
> sair de batalha manda mais, pois garante que não tem ninguém batendo no
> personagem."*

Daí a ORDEM que estes testes travam: primeiro a saída de batalha, depois o HP.
"""
from __future__ import annotations

import ast
import inspect
import logging
import textwrap
from types import SimpleNamespace

import pytest

from blazesbot.bot.app import executor as mod


@pytest.fixture
def executor():
    e = mod.ExecutorDeMacro.__new__(mod.ExecutorDeMacro)
    e.log = logging.getLogger("teste.alvo-caiu")
    e._alvo_atual = None
    return e


def _com_alvo(executor, alvo):
    executor._alvo_atual = lambda: alvo
    return executor


# ---------------------------------------------------------------- a pergunta

def test_hp_zerado_e_queda(executor):
    assert _com_alvo(executor, {"id": 7, "hp": 0, "max_hp": 100})._o_alvo_caiu_pelo_hp() is True


def test_um_ponto_de_vida_NAO_e_queda(executor):
    assert _com_alvo(executor, {"id": 7, "hp": 1, "max_hp": 100})._o_alvo_caiu_pelo_hp() is False


def test_ilegivel_NAO_VOTA(executor):
    """Sem HP não há veredito aqui -- quem cobre esse buraco é a saída de
    batalha, conferida na linha acima."""
    assert _com_alvo(executor, {"id": 7, "hp": None})._o_alvo_caiu_pelo_hp() is False
    assert _com_alvo(executor, None)._o_alvo_caiu_pelo_hp() is False


def test_sem_leitura_de_alvo_o_APP_continua_cego(executor):
    executor._alvo_atual = None
    assert executor._o_alvo_caiu_pelo_hp() is False


def test_leitura_que_explode_nao_derruba_a_macro(executor):
    def _explode():
        raise RuntimeError("processo sumiu")

    executor._alvo_atual = _explode
    assert executor._o_alvo_caiu_pelo_hp() is False


# ------------------------------------------------- a pergunta é BARATA

def test_a_pergunta_da_volta_NAO_encosta_na_TELA():
    """`_alvo_morreu` (o veredito completo, da aquisição) cai na cascata da tela
    quando o HP está ilegível, e a tela custa uma captura por consulta. Dentro
    da volta só cabe a leitura de memória."""
    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._o_alvo_caiu_pelo_hp))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert chamadas == {"_ler_alvo", "get"}, chamadas


def test_a_ORDEM_e_batalha_depois_HP():
    """*"O sair de batalha manda mais."* Se a ordem inverter, uma leitura de HP
    ruim passa a decidir na frente da prova forte."""
    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._uma_volta_simples))
    assert fonte.index("_a_batalha_acabou") < fonte.index("_o_alvo_caiu_pelo_hp")


# ------------------------------------------- a conferência ativa da saída

def _executor_de_batalha(respostas):
    e = mod.ExecutorDeMacro.__new__(mod.ExecutorDeMacro)
    e.log = logging.getLogger("teste.saida")
    fila = list(respostas)
    e._ler_em_batalha = lambda: fila.pop(0) if fila else fila_final
    e._continuar = lambda: True
    return e


def test_sai_no_instante_em_que_a_flag_baixa(monkeypatch, executor):
    """ATIVA, e é isso que faz o teto ser barato: no caso comum ela devolve
    muito antes dos 2 s."""
    monkeypatch.setattr(mod, "PASSO_DA_SAIDA_DE_BATALHA", 0.0)
    lidas = []
    executor._continuar = lambda: True
    executor._ler_em_batalha = lambda: (lidas.append(1), False)[1]

    assert executor._confirmar_a_saida_de_batalha() is True
    assert len(lidas) == 1, "leu mais de uma vez para uma resposta imediata"


def test_o_teto_estourado_diz_que_TEM_OUTRO_MOB(monkeypatch, executor, caplog):
    monkeypatch.setattr(mod, "PASSO_DA_SAIDA_DE_BATALHA", 0.0)
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_CONFIRMAR_A_SAIDA", 0.05)
    executor._continuar = lambda: True
    executor._ler_em_batalha = lambda: True          # nunca sai

    with caplog.at_level(logging.INFO):
        assert executor._confirmar_a_saida_de_batalha() is False

    assert any("outro mob batendo" in r.getMessage() for r in caplog.records)


def test_ilegivel_NAO_conta_como_saida(monkeypatch, executor):
    """`None` é "não sei", e não sei não libera a rotina fora de batalha."""
    monkeypatch.setattr(mod, "PASSO_DA_SAIDA_DE_BATALHA", 0.0)
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_CONFIRMAR_A_SAIDA", 0.05)
    executor._continuar = lambda: True
    executor._ler_em_batalha = lambda: None

    assert executor._confirmar_a_saida_de_batalha() is False


def test_o_pedido_de_PARAR_interrompe_a_espera(monkeypatch, executor):
    monkeypatch.setattr(mod, "PASSO_DA_SAIDA_DE_BATALHA", 0.0)
    executor._continuar = lambda: False
    executor._ler_em_batalha = lambda: True

    assert executor._confirmar_a_saida_de_batalha() is False


def test_o_teto_de_confirmacao_e_o_combinado():
    assert mod.SEGUNDOS_PARA_CONFIRMAR_A_SAIDA == 2.0


# ------------------------------------------------- o corte, no laço vivo

def test_o_alvo_caido_CORTA_a_volta_e_conta_como_volta():
    import tests.test_laco_simples_do_app as base

    e = base._executor()
    e._id_do_alvo = lambda: 777
    e._alvo_morreu = lambda: False
    e._o_alvo_caiu_pelo_hp = lambda: True
    e._confirmar_a_saida_de_batalha = lambda: True
    passos = [SimpleNamespace(key="1", delay_ms=1) for _ in range(4)]

    assert e._uma_volta_simples(passos) is True
    assert e.teclas.count("1") == 0, "bateu no cadáver"
    assert e.voltas == 1, "a volta que MATOU o mob tem de contar"


def test_o_corte_pelo_HP_CONFIRMA_a_saida_de_batalha():
    """A confirmação é o que diz se a rotina fora de batalha pode rodar. Sem
    ela, o bot ia sentar e abrir a bolsa com outro mob em cima."""
    import tests.test_laco_simples_do_app as base

    e = base._executor()
    e._id_do_alvo = lambda: 777
    e._alvo_morreu = lambda: False
    e._o_alvo_caiu_pelo_hp = lambda: True
    chamou = []
    e._confirmar_a_saida_de_batalha = lambda: chamou.append(1) or True

    e._uma_volta_simples([SimpleNamespace(key="1", delay_ms=1)])

    assert chamou == [1]
