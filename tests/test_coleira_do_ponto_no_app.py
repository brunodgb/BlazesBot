"""A COLEIRA: um mob longe DO PERSONAGEM não vale a corrida.

*"Tem vezes que o jogo dá bug e dá target em um mob bem longe, só que com isso
acaba chamando outros mobs e provavelmente vai morrer no caminho (...) essa
limitação é muito importante para não acabar puxando vários mobs ao mesmo tempo
por andar para muito longe."* -- usuário, 04/09/2026.

DUAS VERSÕES ERRADAS ANTES DESTA
================================

**1ª** media o PERSONAGEM contra a base, no meio da macro, e cortava a volta.
A trava de posição não anda em batalha, e `_lutando()` diz "sim" para qualquer
alvo vivo selecionado: travamento permanente, o personagem parado apanhando.

**2ª** media o MOB contra a base, na aquisição. Com o personagem deslocado, TODO
mob perto dele fica longe da base -- 3179 recusas contra 52 macros iniciadas em
uma hora, o bot girando TAB sem atacar.

**Esta** mede o MOB contra o PERSONAGEM: a corrida, que é o que puxa mob pelo
caminho. O "não andar longe do ponto" voltou para a trava de posição, que é de
quem sempre foi.
"""

import logging

import pytest

import blazesbot.core.coleira_do_ponto as coleira
from blazesbot.bot.app import executor as mod
from blazesbot.bot.app.executor import ExecutorDeMacro


@pytest.fixture
def executor():
    e = ExecutorDeMacro.__new__(ExecutorDeMacro)
    e.log = logging.getLogger("teste-coleira")
    e._travar_posicao = True
    e._base_pos = (100, 100)
    e._recusas_por_distancia = 0
    # O PERSONAGEM está no ponto: assim "corrida" e "distância da base" batem, e
    # os testes falam da mesma grandeza que a régua.
    e._posicao_atual = lambda: (100, 100)
    return e


def _mob(distancia, nome="Burning Deadwood"):
    """Um mob a `distancia` unidades do personagem, na horizontal."""
    return {"nome": nome, "id": 4242, "hp": 100, "max_hp": 100,
            "pos": (100 + distancia, 100)}


# ---------------------------------------------------------------- a régua

def test_mob_ao_alcance_e_aceito(executor):
    assert executor._alvo_longe_demais(_mob(coleira.MAXIMO_DE_PASSOS_ATE_O_MOB)) is False
    assert executor._alvo_aceitavel(_mob(5)) is True


def test_mob_alem_do_teto_e_recusado(executor):
    longe = _mob(coleira.MAXIMO_DE_PASSOS_ATE_O_MOB + 1)
    assert executor._alvo_longe_demais(longe) is True
    assert executor._alvo_aceitavel(longe) is False


def test_a_regua_e_a_CORRIDA_e_nao_a_distancia_da_base(executor):
    """O conserto de 06/09/2026 em uma frase: o mesmo mob, a mesma base, o
    personagem em outro lugar -- e a resposta muda, porque quem corre é ele."""
    mob = {"nome": "x", "id": 1, "hp": 10, "max_hp": 10, "pos": (500, 100)}

    executor._posicao_atual = lambda: (100, 100)      # longe do mob
    assert executor._alvo_longe_demais(mob) is True

    executor._recusas_por_distancia = 0
    executor._posicao_atual = lambda: (495, 100)      # colado no mob
    assert executor._alvo_longe_demais(mob) is False


# ---------------------------------------------------------------- "não sei"

def test_sem_posicao_do_personagem_nao_recusa(executor):
    """Sem saber de onde a corrida começa, a pergunta não tem resposta."""
    executor._posicao_atual = None
    assert executor._alvo_longe_demais(_mob(999)) is False


def test_leitura_de_posicao_que_explode_nao_recusa(executor):
    def _explode():
        raise RuntimeError("memória sumiu")

    executor._posicao_atual = _explode
    assert executor._alvo_longe_demais(_mob(999)) is False


def test_alvo_sem_posicao_legivel_nao_recusa(executor):
    assert executor._alvo_longe_demais({"nome": "x", "hp": 10, "pos": None}) is False


def test_sem_base_salva_a_regua_CONTINUA_valendo(executor):
    """A base saiu da decisão: ela só entra no log, para medir o spot."""
    executor._base_pos = None
    assert executor._alvo_longe_demais(_mob(999)) is True


# ---------------------------------------------------------------- a válvula

def test_a_valvula_ABRE_e_isso_e_o_conserto(executor):
    """Na versão anterior ela abriu 1 vez em 3179 recusas, porque o contador era
    zerado a cada rodada de aquisição e `TENTATIVAS_DE_TAB` é 1 -- somando de um
    em um e zerando toda vez, um limiar de 3 nunca chega."""
    longe = _mob(coleira.MAXIMO_DE_PASSOS_ATE_O_MOB + 50)

    recusados = [executor._alvo_longe_demais(longe) for _ in range(6)]

    n = coleira.RECUSAS_ANTES_DE_ACEITAR
    assert recusados[:n] == [True] * n
    assert True not in recusados[n:], recusados


def test_as_recusas_ATRAVESSAM_a_rodada_de_aquisicao():
    """O contador não pode ser zerado no começo de `_garantir_alvo` -- era
    exatamente isso que tornava a válvula inalcançável."""
    import inspect

    fonte = inspect.getsource(ExecutorDeMacro._garantir_alvo)
    assert "_recusas_por_distancia = 0" not in fonte


def test_o_ACEITE_zera_o_contador(executor):
    """Senão, depois de três recusas o teto nunca mais valeria nada."""
    longe = _mob(coleira.MAXIMO_DE_PASSOS_ATE_O_MOB + 50)
    executor._alvo_longe_demais(longe)
    executor._alvo_longe_demais(longe)

    executor._alvo_longe_demais(_mob(1))        # aceito

    assert executor._recusas_por_distancia == 0


def test_o_cadaver_continua_recusado_mesmo_ao_lado(executor):
    """A coleira é uma régua NOVA, não um substituto."""
    corpo = _mob(1)
    corpo["hp"] = 0
    assert executor._alvo_aceitavel(corpo) is False


# ------------------------------------------------- o laço vivo não corta

def test_o_laco_vivo_NAO_corta_a_volta_por_distancia():
    """A regressão que matou personagens em campo: cortar a volta a cada linha
    longe do ponto, com a trava de posição impedida de andar por estar em
    batalha, deixava o personagem parado sem atacar até morrer."""
    import inspect

    fonte = inspect.getsource(ExecutorDeMacro._uma_volta_simples)
    assert "MAXIMO_DE_PASSOS_ATE_O_MOB" not in fonte
    assert "MAXIMO_DE_PIXELS_DO_PONTO" not in fonte
    # O corte por alvo ZERADO fica -- aquele tem quem o resolva (o TAB).
    assert "_ler_id_do_alvo() == 0" in fonte


def test_a_macro_roda_inteira_longe_do_ponto_se_ja_esta_lutando():
    """*"Em batalha o personagem precisa estar atacando e para isso a macro tem
    que rodar"* (usuário, 04/09/2026)."""
    from types import SimpleNamespace

    import tests.test_laco_simples_do_app as base

    e = base._executor()
    e._id_do_alvo = lambda: 777
    e._base_pos = (0, 0)
    e._posicao_atual = lambda: (500, 500)      # longe demais do ponto
    passos = [SimpleNamespace(key="1", delay_ms=1) for _ in range(4)]

    e._uma_volta_simples(passos)

    assert e.teclas.count("1") == 4, e.teclas


def test_o_nome_antigo_da_constante_continua_apontando_para_a_regua():
    """`docs/` e o índice de constantes citam o nome antigo."""
    assert mod.MAXIMO_DE_PIXELS_DO_PONTO == coleira.MAXIMO_DE_PASSOS_ATE_O_MOB
