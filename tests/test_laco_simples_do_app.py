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
from blazesbot.core import teclado_mudo
from blazesbot.core.target_hybrid import MorteDoAlvo


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
    # SEM TIME: alvo aliado não existe fora de um, e a pergunta
    # nem chega a ser feita (`None` = não há como ser aliado).
    e._alvo_e_aliado = None
    # O VEREDITO DE MORTE DO ALVO (`_alvo_morreu`) passou a ser conferido a
    # cada linha em 06/09/2026, e ele guarda estado por identidade.
    e._alvo_da_reserva = None
    e._morto_pela_reserva = None
    e._morte_do_alvo = MorteDoAlvo()
    # O ALVO NÃO CAI nestes testes: eles são sobre as OUTRAS saídas da volta.
    # O corte pelo HP tem os próprios, em tests/test_alvo_caiu_no_app.py.
    e._alvo_morreu = lambda: False
    e.mortes_vistas = 0
    # O AVISO DO TAB MUDO rearma por relógio e consulta a vizinhança -- ver
    # `_avisar_do_tab_mudo`. Aqui nenhum dos dois é exercitado.
    e._falei_do_tab_mudo_em = 0.0
    e._teclado_mudo = teclado_mudo.TecladoMudo()
    e._declarar_queda = None
    e._mobs_por_perto = None
    # SEM CICLO DA MORTE: o dublê não morre, e a pergunta nem é feita.
    e.morte = None
    # SEM CURA: quem tem testes de vida é tests/test_cura_do_app.py. Aqui o
    # socorro em batalha não deve nem ser consultado.
    e.cura = None
    # SEM PONTO INICIAL: `distancia_da_base` devolve None e nada que dependa
    # de distância opina. A coleira dos 12 mora na AQUISIÇÃO -- ver
    # tests/test_coleira_do_ponto_no_app.py.
    e._base_pos = None
    e._posicao_atual = None
    e._ultima_posicao_conhecida = None
    # O TAB só sai quando FALTA alvo (`_preciso_de_alvo`), e a decisão usa
    # estes dois: a batalha da volta anterior e as voltas seguidas com alvo
    # e sem batalha.
    e._lutava_na_volta_anterior = False
    e._voltas_com_alvo_sem_batalha = 0
    # `None` = SEM leitura de id, que é o modo cego: sem ela `_preciso_de_alvo`
    # responde "sim" e o TAB sai como sempre saiu.
    e._id_do_alvo = None
    # Sem leitura de alvo injetada, `_conseguir_o_tab` cai no TAB cego
    # (`_tab_simples`), que é o contrato de sempre do modo simples.
    e._alvo_atual = None
    e.voltas = e.voltas_abortadas = e.teclas_enviadas = e.tabs_dados = 0
    # O TAB ÚNICO e a IDEMPOTÊNCIA dele -- ver `_adquirir_alvo` e
    # `_mesmo_alvo_verificado`. `_tab_solicitado` é o pedido do relógio dos 4s
    # do time (só o `rodar()` seta); sem time, fica False. `_alvo_verificado`
    # é o último alvo VIVO confirmado; sem leitura de alvo injetada, nunca é
    # gravado e o guard devolve False (liberando o TAB cego de sempre).
    e._tab_solicitado = False
    e._alvo_verificado = None
    e._inalcancavel_id = None
    # A LIMPEZA DA BOLSA roda no começo da VOLTA (passo pré-TAB) desde a
    # refatoração do TAB único em 29/08/2026 — ver `_adquirir_alvo`. A fixture
    # monta o executor por `__new__`, então o atributo injetado precisa existir.
    # `None` = sem limpeza configurada: `_limpar_a_bolsa_se_for_a_hora` devolve
    # na hora e a volta não é interrompida.
    e._limpar_a_bolsa = None
    # Os contadores do TAB que o caminho INJETADO lê (`_garantir_alvo`). No modo
    # cego estes testes não os encontravam; injetar leitura de alvo (o portão
    # pré-macro) passa a tocá-los.
    e._tabs_sem_resposta = 0
    e._avisou_tecla_morta = False

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
    assert e.voltas_abortadas == 1
    # SAIR DE BATALHA É UM MOB MORTO, E MOB MORTO CONTA -- ver
    # `test_o_corte_por_batalha_CONTA_volta_e_o_corte_pelo_TIME_nao`.
    assert e.voltas == 1


def test_o_que_corta_e_a_TRANSICAO_e_nunca_o_NIVEL():
    """Fora de batalha o tempo todo é o estado normal entre um mob e outro. Se
    o nível cortasse, a macro nunca rodaria."""
    e = _executor(em_batalha=lambda: False, passos=5)

    e.uma_volta()

    assert e.teclas.count("1") == 5
    assert e.voltas == 1


def test_o_corte_por_batalha_CONTA_volta_e_o_corte_pelo_TIME_nao():
    """A REGRA DO CONTADOR, decidida em 01/09/2026.

    *"Tire o `+= 1` somente nos casos onde foi abortado; caso entrou em
    batalha deve contar mais 1 volta."* (usuário)

    E é isso que o laço simples faz -- os dois cortes que contam exigem a
    TRANSIÇÃO "estava em batalha -> saiu" (`_a_batalha_acabou`), que só
    acontece depois de uma luta de verdade. Sair de batalha é o mob no chão:
    a volta produziu loot, e é justamente `voltas` que marca a hora de limpar
    a bolsa (o único lugar que DECIDE por este número -- o shuffle anti-AFK só
    o escreve no log). Não contar a matança faria a limpeza atrasar
    exatamente na conta que mata mais rápido.

    O que NÃO conta é o corte pelo TIME: ali não houve luta nenhuma, só uma
    ordem do líder para pular a volta.

    ATENÇÃO -- O LAÇO COMPLEXO (`uma_volta`, com `LACO_SIMPLES = False`) SEGUE A
    REGRA ANTIGA: lá só o fim natural conta. São contratos diferentes de
    propósito, e `tests/test_tab_no_app.py` guarda o de lá.
    """
    estados = iter([True, False, False, False])
    e = _executor(em_batalha=lambda: next(estados))

    e.uma_volta()

    assert (e.voltas, e.voltas_abortadas) == (1, 1), (
        "corte por batalha encerrada deixou de contar como volta")


def test_o_corte_pelo_TIME_nao_conta_volta():
    """A outra metade da regra -- sem ela, "toda passada conta" passaria neste
    arquivo e o contador voltaria a inflar a limpeza de bolsa.

    O líder mandou pular (`linha_a_enviar` < 0): não houve luta, não houve
    loot, não há volta.
    """
    e = _executor(em_batalha=lambda: True, passos=6)
    e.sincronia = SimpleNamespace(
        deve_dar_tab_na_abertura=lambda: False,
        volta_cega=lambda: False,
        linha_a_enviar=lambda _i, _ms: -1,
        espera_da_linha=lambda ms: ms,
    )

    assert e.uma_volta() is True

    assert e.voltas_abortadas == 1
    assert e.voltas == 0, "aborto do TIME contou como volta de macro"


# ===========================================================================
# O QUE O LAÇO SIMPLES NÃO FAZ
# ===========================================================================

def test_a_volta_simples_nao_olha_a_TELA_nem_mede_a_VIDA():
    """*"Não verifica mais vida, não verifica mais nada."*

    A PROMESSA FOI ESTREITADA EM 01/09/2026, e de propósito: o laço ganhou o
    "Execution Gate" (Eixo 2), que lê o alvo UMA vez, logo depois da aquisição,
    só para não rodar a macro inteira contra um cadáver ou contra nada. Uma
    leitura de struct por volta é barata; era a régua de VIDA e a TELA que
    custavam caro e erravam calado.

    Então o que continua proibido aqui dentro é tudo que CUSTA CAPTURA ou
    DECIDE POR APROXIMAÇÃO -- e é isso que este teste guarda. `_ler_alvo` e
    `_adquirir_alvo` saíram da lista porque hoje são o portão; o resto não.
    """
    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._uma_volta_simples))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    for proibida in ("_alvo_morreu", "_alvo_intocavel", "_olhar_a_tela",
                     "_vida_do_alvo", "_registrar_o_alvo", "_comecar_a_regua",
                     "_vida_do_alvo_pela_tela"):
        assert proibida not in chamadas, proibida


def test_o_portao_do_laco_simples_le_o_alvo_UMA_vez_so():
    """Duas leituras seriam duas fotos de instantes diferentes respondendo à
    mesma pergunta -- e é assim que nascem as decisões irreproduzíveis."""
    fonte = textwrap.dedent(
        inspect.getsource(mod.ExecutorDeMacro._uma_volta_simples))
    leituras = [n for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "_ler_alvo"]

    assert len(leituras) == 1, (
        f"o laço simples lê o alvo {len(leituras)} vezes; o portão é UM só")


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


# ===========================================================================
# O PORTÃO DE AQUISIÇÃO PRÉ-MACRO (Eixo 1): sem alvo REAL, a macro não roda
# ===========================================================================

def test_COM_alvo_REAL_a_macro_roda(monkeypatch):
    """O caso feliz não pode regredir: alvo vivo já selecionado => a macro roda
    SEM TAB (a idempotência que protege o mob vivo de ser trocado na luta)."""
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", 0.0)

    e = _executor(em_batalha=lambda: False)
    # INJETADO: um mob vivo (id 7) selecionado.
    e._id_do_alvo = lambda: 7
    e._alvo_atual = lambda: {"id": 7, "nome": "mob", "hp": 100, "max_hp": 100}
    e._mesmo_alvo_verificado = lambda: True

    assert e.uma_volta() is True
    assert e.teclas == ["1", "1", "1"], e.teclas
    assert "TAB" not in e.teclas, "trocou de alvo com o alvo vivo presente"


def test_SEM_alvo_REAL_depois_do_TAB_a_macro_NAO_roda(monkeypatch):
    """O portão do Eixo 1: TAB apertado mas o id permanece 0 (nada selecionado)
    => `_garantir_alvo` devolve False, `_adquirir_alvo` devolve False, e
    NENHUMA tecla de ataque sai. A volta volta ao Core Loop."""
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_SEM_ALVO", 0.0)

    e = _executor(em_batalha=lambda: False)
    # INJETADO: o TAB não consegue selecionar mob vivo -- id permanece 0.
    e._id_do_alvo = lambda: 0
    e._alvo_atual = lambda: {"id": 0, "nome": "", "hp": 0, "max_hp": 100}

    assert e.uma_volta() is False
    # Nenhuma linha da macro: só o TAB de aquisição (que falhou em pegar alvo).
    assert all(t == "TAB" for t in e.teclas), e.teclas
    assert "1" not in e.teclas, "a macro disparou no vazio sem alvo real"


def test_TAB_que_cai_no_CADAVER_nao_roda_a_macro(monkeypatch):
    """O outro fracasso de aquisição: o TAB move o id MAS para um cadáver
    (hp <= 0). `_alvo_aceitavel` recusa, as tentativas esgotam e a macro não
    roda com o corpo selecionado."""
    monkeypatch.setattr(mod, "ESPERA_ANTES_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_DEPOIS_DO_TAB", 0.0)
    monkeypatch.setattr(mod, "ESPERA_SEM_ALVO", 0.0)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_TABS", 0.0)
    monkeypatch.setattr(mod, "SEGUNDOS_PARA_A_RODA_REINICIAR", 0.0)
    dormidas: list[float] = []
    monkeypatch.setattr(mod.time, "sleep", dormidas.append)

    e = _executor(em_batalha=lambda: False)
    # INJETADO: id 0 antes; o TAB troca para o corpo (id 8, hp 0).
    estado = {"id": 0}
    e._id_do_alvo = lambda: estado["id"]
    e._alvo_atual = lambda: {
        "id": estado["id"], "nome": "corpo", "hp": 0, "max_hp": 100}
    # A espera que trocaria de id devolve o corpo imediatamente.
    e._esperar_o_alvo_trocar = lambda id_antes: 8
    # O TAB muda o estado para o corpo.
    def apertar(t):
        e.teclas.append(t)
        if t == "TAB":
            estado["id"] = 8
    e.input = SimpleNamespace(key=apertar)

    assert e.uma_volta() is False
    assert "1" not in e.teclas, "a macro disparou com o cadáver selecionado"

# ===========================================================================
# ALVO ZERADO NO MEIO DA MACRO -- 01/09/2026
# ===========================================================================
#
# *"A cada linha deve verificar se o target_id != 0; caso for 0 ela vai ser
# interrompida e recomeçar."*
#
# `TARGET_ID` em zero é o jogo dizendo "não há nada selecionado": o mob morreu e
# o cliente limpou o alvo, ele sumiu de vista, ou uma janela roubou a seleção.
# Todas as linhas que sobram sairiam para o vazio.


def test_alvo_zerado_no_meio_CORTA_a_volta():
    e = _executor()
    e._id_do_alvo = lambda: 0
    passos = [SimpleNamespace(key="1", delay_ms=1) for _ in range(5)]

    assert e._uma_volta_simples(passos) is True     # aborto normal, não parada
    # O TAB do prelúdio sai (não há alvo, então ele é a coisa certa a fazer).
    # O que NÃO pode sair é linha de macro.
    assert e.teclas == ["TAB"], e.teclas
    assert e.voltas == 0, "contou como volta completa"


def test_alvo_que_zera_no_MEIO_corta_ali():
    e = _executor()
    # O alvo some DEPOIS de duas linhas. Amarrado às teclas enviadas, e não a
    # uma contagem de chamadas: o prelúdio também lê o id, e contar chamadas
    # faria o teste medir a implementação em vez do comportamento.
    e._id_do_alvo = lambda: 0 if e.teclas.count("1") >= 2 else 777
    passos = [SimpleNamespace(key="1", delay_ms=1) for _ in range(6)]

    e._uma_volta_simples(passos)
    assert e.teclas.count("1") == 2, e.teclas


def test_SEM_leitura_de_id_a_macro_roda_inteira():
    """Cego é o modo em que o APP foi feito para funcionar: `None` não corta."""
    e = _executor()
    e._id_do_alvo = None
    passos = [SimpleNamespace(key="1", delay_ms=1) for _ in range(4)]

    e._uma_volta_simples(passos)
    assert e.teclas.count("1") == 4, e.teclas
