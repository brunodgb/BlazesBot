"""O LAÇO SIMPLES DO APP — o que roda de verdade desde 26/08/2026.

Decisão do usuário, depois de uma sequência de refinamentos que foram ficando
piores em vez de melhores:

    *"Tá só piorando as coisas, vamos voltar ao simples. Deixa as funções que
     fizemos aí paradas sem uso, para testar outra hora. O que vamos fazer: você
     vai dar TAB, deixar rodar a macro até o final, só para a macro no meio se
     SAIR DE BATALHA. Não verifica mais vida, não verifica mais nada. As únicas
     coisas que se mantêm são as verificações fora de batalha e a poção de vida
     nos 30% de HP."*

O laço inteiro cabe em quatro linhas:

    FORA de batalha  -> pet, comida, voltar ao ponto, TAB, roda a macro
    EM batalha       -> roda a macro de novo, sem TAB e sem conferência
    saiu de batalha  -> corta a macro no meio, volta ao topo
    vida < 30%       -> a cura, que já era chamada entre voltas

O laço antigo continua testado em `test_tab_no_app.py`, que desliga o
`LACO_SIMPLES` na fixture. Este arquivo trava o que ESTÁ NO AR.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest

from blazesbot.bot.app import executor as mod


def _executor(em_batalha=None, passos=3, tecla="TAB"):
    """Um `ExecutorDeMacro` sem construtor -- não há jogo no teste."""
    e = mod.ExecutorDeMacro.__new__(mod.ExecutorDeMacro)
    e.teclas: list[str] = []
    e.linhas: list[tuple[str, str]] = []
    e.feitos: list[str] = []

    e.input = SimpleNamespace(key=e.teclas.append)
    e.log = SimpleNamespace(
        info=lambda f, *a: e.linhas.append(("INFO", f % a if a else f)),
        warning=lambda f, *a: e.linhas.append(("WARNING", f % a if a else f)),
        debug=lambda *a, **k: None)

    e._fonte = lambda: [SimpleNamespace(key="1", delay_ms=0)] * passos
    e._continuar = lambda: True
    e._pausado = None
    e._tecla_de_alvo = (lambda: tecla)
    e._em_batalha = em_batalha
    e._estava_em_batalha = False
    e._espera_depois_do_tab_ms = None
    e._avisou_sem_tecla_de_alvo = False
    # SEM TIME: estes testes montam o executor por `__new__`, então todo
    # atributo lido pelo laço tem de ser posto à mão. `None` é o valor de
    # "esta conta não está num time" -- a macro roda como sempre rodou.
    e.sincronia = None
    # O TAB só sai quando FALTA alvo (`_preciso_de_alvo`), e a decisão usa
    # estes dois: a batalha da volta anterior e as voltas seguidas com alvo
    # e sem batalha.
    e._lutava_na_volta_anterior = False
    e._voltas_com_alvo_sem_batalha = 0
    # `None` = SEM leitura de id, que é o modo cego: sem ela `_preciso_de_alvo`
    # responde "sim" e o TAB sai como sempre saiu.
    e._id_do_alvo = None
    e.voltas = e.voltas_abortadas = e.teclas_enviadas = e.tabs_dados = 0

    # As conferências viram marcas numa lista, para a ORDEM poder ser conferida.
    e.garantir_pet = lambda: e.feitos.append("pet")
    e.feed_pet = lambda force=False: e.feitos.append("comida")
    e._travar_posicao_se_preciso = lambda: e.feitos.append("andar")
    return e


@pytest.fixture(autouse=True)
def _rapido(monkeypatch):
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", 0.0)


# ===========================================================================
# O INTERRUPTOR
# ===========================================================================

def test_o_laco_simples_esta_LIGADO():
    assert mod.LACO_SIMPLES is True


def test_as_funcoes_do_laco_antigo_continuam_EXISTINDO():
    """*"Deixa as funções que fizemos aí paradas sem uso, para testar outra
    hora."* Interruptor, não apagar — é a regra do projeto, e aqui ela vale
    duplamente: cada peça tem medição atrás dela."""
    for nome in ("_alvo_morreu", "_alvo_intocavel", "_alvo_aceitavel",
                 "_olhar_a_tela", "_vida_do_alvo", "_esperar_o_alvo_trocar",
                 "_alvo_ilegivel_demais", "_observar_depois_da_morte",
                 "_garantir_alvo", "_esperar_cego"):
        assert hasattr(mod.ExecutorDeMacro, nome), nome


# ===========================================================================
# FORA DE BATALHA: CONFERE, TABA, RODA
# ===========================================================================

def test_FORA_de_batalha_confere_na_ORDEM_e_depois_TABA():
    e = _executor(em_batalha=lambda: False)

    assert e.uma_volta() is True

    assert e.feitos == ["pet", "comida", "andar"], e.feitos
    assert e.teclas == ["TAB", "1", "1", "1"], e.teclas
    assert e.voltas == 1


def test_a_macro_roda_ATE_O_FINAL():
    e = _executor(em_batalha=lambda: False, passos=7)
    e.uma_volta()
    assert e.teclas.count("1") == 7


# ===========================================================================
# EM BATALHA: NÃO TABA, NÃO CONFERE
# ===========================================================================

def test_EM_BATALHA_nao_da_TAB_e_nao_confere_nada():
    """O QUE IMPEDE O DEFEITO QUE MATOU O PERSONAGEM.

    Em batalha o bot não troca de alvo: ele repete a macro. Não existe caminho
    onde ele larga um mob de pé.
    """
    e = _executor(em_batalha=lambda: True)

    assert e.uma_volta() is True

    assert e.feitos == [], f"conferiu no meio da luta: {e.feitos}"
    assert "TAB" not in e.teclas, "trocou de alvo com a luta em andamento"
    assert e.teclas == ["1", "1", "1"]


def test_SEM_leitura_de_batalha_o_bot_roda_como_se_estivesse_FORA():
    """"Não sei" não pode travar o TAB: sem leitura de memória o modo APP
    precisa continuar mandando tecla, que é a razão de ele existir."""
    e = _executor(em_batalha=None)

    e.uma_volta()

    assert e.teclas[0] == "TAB"
    assert e.feitos == ["pet", "comida", "andar"]


# ===========================================================================
# SAIR DE BATALHA CORTA A MACRO NO MEIO
# ===========================================================================

def test_SAIR_de_batalha_corta_a_macro_no_meio():
    estados = iter([True, True, False, False, False, False])
    e = _executor(em_batalha=lambda: next(estados), passos=6)

    assert e.uma_volta() is True

    assert len(e.teclas) < 6, "rodou a macro inteira depois de sair da luta"
    assert e.voltas == 0, "volta cortada não é volta completa"
    assert e.voltas_abortadas == 1


def test_o_que_corta_e_a_TRANSICAO_e_nunca_o_NIVEL():
    """Fora de batalha o tempo todo é o estado normal entre um mob e outro. Se
    o nível cortasse, a macro nunca rodaria."""
    e = _executor(em_batalha=lambda: False, passos=5)

    e.uma_volta()

    assert e.teclas.count("1") == 5
    assert e.voltas == 1


def test_a_volta_CORTADA_nao_conta_como_volta():
    """`voltas` alimenta a limpeza de bolsa e o shuffle anti-AFK."""
    estados = iter([True, False, False, False])
    e = _executor(em_batalha=lambda: next(estados))

    e.uma_volta()

    assert (e.voltas, e.voltas_abortadas) == (0, 1)


# ===========================================================================
# O QUE O LAÇO SIMPLES NÃO FAZ
# ===========================================================================

def test_a_volta_simples_NAO_LE_O_ALVO_em_lugar_nenhum():
    """*"Não verifica mais vida, não verifica mais nada."*

    Nem HP, nem id, nem nome, nem a barra desenhada. A única pergunta é
    "estou em batalha?", e ela vem da struct do PERSONAGEM.
    """
    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._uma_volta_simples))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    for proibida in ("_ler_alvo", "_ler_id_do_alvo", "_alvo_morreu",
                     "_alvo_intocavel", "_olhar_a_tela", "_vida_do_alvo",
                     "_garantir_alvo", "_registrar_o_alvo"):
        assert proibida not in chamadas, proibida


def test_o_corte_da_macro_NAO_LE_O_ALVO():
    """`_cortar_a_volta` roda dentro da espera de CADA linha, a cada 0,1 s. Se
    ele lesse o alvo ali, a promessa de "não verifica nada" seria só do
    docstring."""
    e = _executor(em_batalha=lambda: False)
    e._ler_alvo = lambda: (_ for _ in ()).throw(
        AssertionError("leu o alvo no laço simples"))
    e._ler_id_do_alvo = lambda: (_ for _ in ()).throw(
        AssertionError("leu o id no laço simples"))

    assert e._cortar_a_volta() is False


def test_o_TAB_simples_NAO_confere_que_o_id_mudou():
    """Quem decide se o TAB valeu é a BATALHA — entrou, era alvo; não entrou, a
    volta acaba fora de batalha e o TAB sai de novo."""
    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro._tab_simples))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert "_esperar_o_alvo_trocar" not in chamadas
    assert "_alvo_aceitavel" not in chamadas


def test_o_mob_do_PENHASCO_se_resolve_sozinho():
    """A régua que precisou de três versões e uma morte para ficar de pé virou
    consequência de não existir: o bot TABa no inalcançável, roda a macro, nunca
    entra em batalha, e TABa de novo na volta seguinte."""
    e = _executor(em_batalha=lambda: False)

    e.uma_volta()
    e.uma_volta()

    assert e.teclas.count("TAB") == 2


# ===========================================================================
# O QUE SE MANTÉM
# ===========================================================================

def test_os_DOIS_RESPIROS_do_TAB_ficam(monkeypatch):
    """Eles não são conferência: o de cima impede o TAB de ser engolido pelas
    últimas teclas da macro, e o de baixo é a LINHA 0 que o usuário configura."""
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.6)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", 1.0)

    e = _executor(em_batalha=lambda: False, passos=0)
    e._tab_simples()

    assert sum(dormidas) == pytest.approx(1.6)


def test_a_LINHA_0_configurada_vale_no_laco_simples(monkeypatch):
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)

    e = _executor(em_batalha=lambda: False)
    e._espera_depois_do_tab_ms = lambda: 2500
    e._tab_simples()

    assert sum(dormidas) == pytest.approx(2.5)


def test_SEM_tecla_de_alvo_avisa_UMA_vez_e_segue():
    e = _executor(em_batalha=lambda: False, tecla="")

    e.uma_volta()
    e.uma_volta()

    avisos = [t for n, t in e.linhas if n == "WARNING"]
    assert len(avisos) == 1, avisos
    assert "próximo alvo" in avisos[0]
    assert e.teclas.count("1") == 6, "a macro parou por falta de tecla de alvo"


def test_a_CURA_continua_sendo_chamada_entre_voltas():
    """*"As únicas coisas que se mantêm são as verificações fora de batalha e a
    poção de vida nos 30% de HP."* A cura roda no `rodar()`, entre voltas, e o
    laço simples não mexeu nela."""
    fonte = textwrap.dedent(inspect.getsource(mod.ExecutorDeMacro.rodar))
    assert "self.cura.cuidar()" in fonte


def test_o_gatilho_da_cura_continua_em_30_por_cento():
    from blazesbot.bot.app import cura

    assert cura.VIDA_PARA_CURAR == 30.0
