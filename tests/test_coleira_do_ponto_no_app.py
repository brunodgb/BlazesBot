"""A COLEIRA NÃO VETA MAIS ALVO — e este arquivo é a cicatriz das três versões.

**1ª** media o PERSONAGEM contra a base, no meio da macro, e cortava a volta. A
trava de posição não anda em batalha: travamento permanente, o personagem parado
apanhando.

**2ª** media o MOB contra a base, na aquisição. Com o personagem deslocado, todo
mob perto dele fica longe da base: 3179 recusas contra 52 macros em uma hora.

**3ª** media o MOB contra o PERSONAGEM. Régua certa, defeito fatal: **o TAB do
jogo entrega o mob mais próximo primeiro e vai afastando a cada toque.** Recusar
o primeiro empurra a seleção para fora — e o bot acaba correndo até um mob
distante com meia dúzia de outros atrás. Matou a conta `BlazesAPP1` em
06/09/2026.

O que este arquivo trava agora é o CONTRÁRIO do que travava antes: **nada pode
recusar um alvo vivo por distância.**
"""

import logging

import pytest

import blazesbot.core.coleira_do_ponto as coleira
from blazesbot.bot.app.executor import ExecutorDeMacro


@pytest.fixture
def executor():
    e = ExecutorDeMacro.__new__(ExecutorDeMacro)
    e.log = logging.getLogger("teste-coleira")
    e._travar_posicao = True
    e._base_pos = (100, 100)
    e._posicao_atual = lambda: (100, 100)
    return e


def _mob(distancia, nome="Burning Deadwood"):
    """Um mob a `distancia` unidades do personagem, na horizontal."""
    return {"nome": nome, "id": 4242, "hp": 100, "max_hp": 100,
            "pos": (100 + distancia, 100)}


# ------------------------------------------------- o hotfix, em uma linha

def test_mob_LONGE_e_aceito(executor):
    """O primeiro alvo vivo que o TAB traz é o mais perto que existe. Recusá-lo
    só faz o TAB seguinte trazer um mais longe ainda."""
    assert executor._alvo_aceitavel(_mob(500)) is True


def test_mob_ABSURDAMENTE_longe_tambem_e_aceito(executor):
    """Não há teto: procurar alvo melhor é o próprio dano."""
    assert executor._alvo_aceitavel(_mob(50_000)) is True


def test_o_cadaver_continua_recusado(executor):
    """A única recusa que sobrou, e a razão de `_alvo_aceitavel` existir: o
    corpo entra na roda do TAB tanto quanto um mob vivo."""
    corpo = _mob(1)
    corpo["hp"] = 0
    assert executor._alvo_aceitavel(corpo) is False


def test_NENHUMA_recusa_por_distancia_no_executor():
    """Trava estrutural: se alguém devolver o veto, este teste cai."""
    import inspect

    fonte = inspect.getsource(ExecutorDeMacro._alvo_aceitavel)
    assert "longe_demais" not in fonte
    assert "_medir_a_corrida" in fonte, "a medição não pode sumir junto"


def test_o_modulo_da_coleira_so_MEDE():
    """Ele não expõe mais veredito nenhum -- só `medir`."""
    assert hasattr(coleira, "medir")
    assert not hasattr(coleira, "avaliar")
    assert not hasattr(coleira, "longe_demais")


# ------------------------------------------------- a medição continua saindo

def test_a_medicao_anota_a_corrida_e_a_base(executor, caplog):
    with caplog.at_level(logging.INFO):
        executor._alvo_aceitavel(_mob(37))

    linhas = [r.getMessage() for r in caplog.records if "DIAG:" in r.getMessage()]
    assert any("corrida=37" in x and "mob->base=37" in x for x in linhas), linhas


def test_a_medicao_NAO_derruba_a_aquisicao_se_a_posicao_falhar(executor):
    def _explode():
        raise RuntimeError("memória sumiu")

    executor._posicao_atual = _explode
    assert executor._alvo_aceitavel(_mob(10)) is True


def test_sem_posicao_do_personagem_nao_ha_o_que_medir(executor, caplog):
    executor._posicao_atual = None
    with caplog.at_level(logging.INFO):
        assert executor._alvo_aceitavel(_mob(10)) is True
    assert not [r for r in caplog.records if "corrida=" in r.getMessage()]


# ------------------------------------------------- o laço vivo não corta

def test_o_laco_vivo_NAO_corta_a_volta_por_distancia():
    """A 1ª versão, que matava por travamento: cortar a volta a cada linha longe
    do ponto, com a trava de posição impedida de andar por estar em batalha."""
    import inspect

    fonte = inspect.getsource(ExecutorDeMacro._uma_volta_simples)
    assert "MAXIMO_DE_PIXELS_DO_PONTO" not in fonte
    assert "coleira" not in fonte
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
