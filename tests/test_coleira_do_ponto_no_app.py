"""A COLEIRA DOS 12: UM MOB LONGE DO PONTO NÃO VALE A CORRIDA.

*"Tem vezes que o jogo dá bug e dá target em um mob bem longe, só que com isso
acaba chamando outros mobs e provavelmente vai morrer no caminho (...) essa
limitação é muito importante para não acabar puxando vários mobs ao mesmo tempo
por andar para muito longe."* -- usuário, 04/09/2026.

POR QUE A REGRA MORA NA AQUISIÇÃO, E NÃO NO MEIO DA MACRO
=========================================================

A primeira versão cortava a volta a cada linha em que o personagem estivesse
longe do ponto, contando que a trava de posição andasse de volta no prelúdio da
volta seguinte. Ela não anda: `_travar_posicao_se_preciso` sai na hora quando
`_lutando()` diz que sim, e `_lutando()` diz que sim para qualquer alvo vivo
selecionado. Em campo isso deu um travamento PERMANENTE -- nenhuma tecla saía,
então o mob não morria; a trava não andava, então o personagem não voltava. Ele
ficava parado levando dano até morrer.

Recusar o mob ANTES de correr até ele resolve a causa e não pode travar nada: se
o alvo não serve, o TAB busca outro; se nenhum servir, a válvula
(`RECUSAS_POR_DISTANCIA`) aceita o que vier -- porque bot mudo é pior que o
defeito.
"""

import logging
from types import SimpleNamespace

import pytest

import blazesbot.bot.app.executor as mod
from blazesbot.bot.app.executor import ExecutorDeMacro


@pytest.fixture
def executor():
    e = ExecutorDeMacro.__new__(ExecutorDeMacro)
    e.log = logging.getLogger("teste-coleira")
    e._travar_posicao = True
    e._base_pos = (100, 100)
    e._recusas_por_distancia = 0
    # SEM LEITURA DE POSIÇÃO: a medição do "mob->personagem" que o log tirou
    # em 06/09/2026 é diagnóstico; ela não pode mudar quem é recusado.
    e._posicao_atual = None
    return e


def _mob(distancia, nome="Burning Deadwood"):
    """Um mob a `distancia` unidades da base, na horizontal."""
    return {"nome": nome, "id": 4242, "hp": 100, "max_hp": 100,
            "pos": (100 + distancia, 100)}


# ---------------------------------------------------------------- a régua

def test_mob_dentro_do_teto_e_aceito(executor):
    assert executor._alvo_longe_demais(_mob(mod.MAXIMO_DE_PIXELS_DO_PONTO)) is False
    assert executor._alvo_aceitavel(_mob(5)) is True


def test_mob_alem_do_teto_e_recusado(executor):
    longe = _mob(mod.MAXIMO_DE_PIXELS_DO_PONTO + 1)
    assert executor._alvo_longe_demais(longe) is True
    assert executor._alvo_aceitavel(longe) is False


def test_o_teto_de_caca_e_MAIOR_que_a_tolerancia_da_trava():
    """São perguntas diferentes: a tolerância é a folga do "já voltei"; o teto é
    o alcance de caça em volta do ponto."""
    assert mod.MAXIMO_DE_PIXELS_DO_PONTO > mod.TOLERANCIA_POSICAO


# ---------------------------------------------------------------- "não sei"

def test_sem_base_salva_nao_recusa(executor):
    executor._base_pos = None
    assert executor._alvo_longe_demais(_mob(999)) is False


def test_com_a_trava_desligada_nao_recusa(executor):
    """Sem trava de posição não há ponto inicial de verdade -- e o APP cego
    continua engajando como sempre fez."""
    executor._travar_posicao = False
    assert executor._alvo_longe_demais(_mob(999)) is False


def test_alvo_sem_posicao_legivel_nao_recusa(executor):
    assert executor._alvo_longe_demais({"nome": "x", "hp": 10, "pos": None}) is False


# ---------------------------------------------------------------- a válvula

def test_a_recusa_TEM_FIM(executor):
    """Se todo mob em volta estiver longe, o bot NÃO pode ficar sem atacar --
    era essa a morte que a primeira versão da coleira causava."""
    longe = _mob(mod.MAXIMO_DE_PIXELS_DO_PONTO + 50)

    recusados = [executor._alvo_longe_demais(longe) for _ in range(6)]

    assert recusados[:mod.RECUSAS_POR_DISTANCIA] == [True] * mod.RECUSAS_POR_DISTANCIA
    assert True not in recusados[mod.RECUSAS_POR_DISTANCIA:], recusados
    assert executor._alvo_aceitavel(longe) is True


def test_o_cadaver_continua_recusado_mesmo_ao_lado(executor):
    """A coleira é uma régua NOVA, não um substituto: o motivo original de
    `_alvo_aceitavel` existir continua valendo."""
    corpo = _mob(1)
    corpo["hp"] = 0
    assert executor._alvo_aceitavel(corpo) is False


# ------------------------------------------------- a rodada de aquisição

def test_cada_rodada_de_aquisicao_recomeca_a_contagem():
    """As recusas são de UMA rodada. Se vazassem, a primeira sequência de mobs
    longes gastaria a válvula e a conta nunca mais recusaria nada."""
    import inspect
    fonte = inspect.getsource(ExecutorDeMacro._garantir_alvo)
    assert "self._recusas_por_distancia = 0" in fonte


def test_o_laco_vivo_NAO_corta_mais_a_volta_por_distancia():
    """A regressão que matou personagens em campo: cortar a volta a cada linha
    longe do ponto, com a trava de posição impedida de andar por estar em
    batalha, deixava o personagem parado sem atacar até morrer."""
    import inspect
    fonte = inspect.getsource(ExecutorDeMacro._uma_volta_simples)
    assert "MAXIMO_DE_PIXELS_DO_PONTO" not in fonte
    # O corte por alvo ZERADO fica -- aquele tem quem o resolva (o TAB).
    assert "_ler_id_do_alvo() == 0" in fonte


def test_a_macro_roda_inteira_longe_do_ponto_se_ja_esta_lutando():
    """*"Em batalha o personagem precisa estar atacando e para isso a macro tem
    que rodar"* (usuário, 04/09/2026)."""
    import tests.test_laco_simples_do_app as base
    e = base._executor()
    e._id_do_alvo = lambda: 777
    e._base_pos = (0, 0)
    e._posicao_atual = lambda: (500, 500)      # longe demais do ponto
    passos = [SimpleNamespace(key="1", delay_ms=1) for _ in range(4)]

    e._uma_volta_simples(passos)

    assert e.teclas.count("1") == 4, e.teclas
