"""Janela aberta engole o clique na SAÍDA da cave, não só na entrada.

RELATO DO USUÁRIO, 07/09/2026, com print da janela `System` aberta: *"hoje na
entrada de BC é feito uma verificação se ficou alguma janela aberta, é
importante também verificar na saída, pois acabei de chegar e ver o bot parado
na saída"*.

Estava certo, e o log mostra o tamanho: **305 cliques direitos em (616, 326) que
não abriram o diálogo** na fase `SAIR`, contra 267 saídas concluídas.
`desobstruir_a_cena` existia — e era chamada em UM lugar só, a entrada.

A CAUSA TAMBÉM ESTÁ NO LOG, e é outra. Os 3 episódios de saída travada que o log
mostra por inteiro foram TODOS precedidos, ~2,5 min antes, por esta linha no
waypoint dos guardas:

    Cemetery Guard na mira (após o TAB N). Largo a mira no ESC, paro de bater...

`_travar_no_alvo_proibido` apertava ESC **às cegas**. Sem mira, o ESC deste jogo
abre o MENU DO SISTEMA — a janela do print —, e ela atravessa a luta do boss até
a saída. `largar_a_mira` já resolvia isso desde 06/09 lendo o `target_id` antes
de apertar; este chamador tinha ficado de fora, e era justamente o que aperta no
instante em que o alvo pode ter acabado de sair.

Os dois lados estão travados aqui: a causa (ESC conferido) e a defesa (o guarda
de janela no funil dos seis pares de clique de NPC).
"""
import time
from types import SimpleNamespace

import pytest

from blazesbot.bot import combate, ui_do_jogo

# ===========================================================================
# A CAUSA: o ESC do alvo proibido passa a CONFERIR
# ===========================================================================

class _CtxDoEsc:
    def __init__(self, ids):
        self._ids = list(ids)
        self.teclas = []
        self.log = SimpleNamespace(info=lambda *a, **k: None,
                                   debug=lambda *a, **k: None,
                                   warning=lambda *a, **k: None,
                                   error=lambda *a, **k: None)
        self.memory = self

    def id_do_alvo(self):
        return self._ids.pop(0) if len(self._ids) > 1 else self._ids[0]

    def press(self, key, delay=0.0):
        self.teclas.append(key)

    def tick(self, s):
        pass

    def raise_if_stopped(self):
        pass


def _motor(ids):
    m = object.__new__(combate.CombatEngine)
    m.ctx = _CtxDoEsc(ids)
    m._alvo_proibido_encontrado = False
    return m


def test_a_trava_do_guarda_larga_a_mira_PELO_caminho_conferido():
    """Com alvo na mira, o ESC sai — é o caso para o qual a trava existe."""
    m = _motor([777, 0])
    m._travar_no_alvo_proibido("Cemetery Guard", "memória")
    assert m.ctx.teclas == ["esc"]


def test_SEM_mira_a_trava_NAO_aperta_ESC():
    """ESC sem alvo abre o menu do System — a janela do print do usuário, que
    atravessa a luta do boss e engole o clique na saída."""
    m = _motor([0])
    m._travar_no_alvo_proibido("Cemetery Guard", "memória")
    assert m.ctx.teclas == [], "apertou ESC sem mira: abre o menu do jogo"


def test_leitura_ilegivel_tambem_NAO_aperta():
    """"Não sei" nunca autorizou uma tecla nesta casa."""
    m = _motor([None])
    m._travar_no_alvo_proibido("Cemetery Guard", "memória")
    assert m.ctx.teclas == []


def test_a_trava_continua_valendo_mesmo_sem_o_ESC_sair():
    """O que segura o golpe é a flag, não a tecla. Sem mira o ESC não sai, mas
    o bot ainda para de bater no guarda."""
    m = _motor([0])
    m._travar_no_alvo_proibido("Cemetery Guard", "memória")
    assert m._alvo_proibido_encontrado is True


def test_a_trava_usa_largar_a_mira_e_nao_um_press_cru():
    """Por AST e não por substring: o comentário do próprio conserto cita
    `press('esc')` para explicar o que saiu, e uma busca textual casaria com a
    explicação em vez de com o código."""
    import ast
    import inspect
    import textwrap

    arvore = ast.parse(textwrap.dedent(inspect.getsource(
        combate.CombatEngine._travar_no_alvo_proibido)))

    chamadas = [no for no in ast.walk(arvore) if isinstance(no, ast.Call)]
    nomes = {
        no.func.attr for no in chamadas
        if isinstance(no.func, ast.Attribute)
    }
    assert "largar_a_mira" in nomes

    esc_cru = [
        no for no in chamadas
        if isinstance(no.func, ast.Attribute) and no.func.attr == "press"
        and any(isinstance(a, ast.Constant) and a.value == "esc" for a in no.args)
    ]
    assert not esc_cru, "voltou o ESC cru, sem conferir se há mira"


# ===========================================================================
# A DEFESA: o guarda de janela no funil dos cliques de NPC
# ===========================================================================

class _UI:
    """Só o que `_desobstruir_se_faz_tempo` toca."""

    def __init__(self):
        self._guarda_de_janela_em = 0.0
        self.chamadas = []

    def desobstruir_a_cena(self, motivo):
        self.chamadas.append(motivo)
        return True

    _desobstruir_se_faz_tempo = ui_do_jogo.UIDoJogo._desobstruir_se_faz_tempo


@pytest.fixture
def relogio(monkeypatch):
    agora = {"t": 1000.0}
    monkeypatch.setattr(ui_do_jogo.time, "time", lambda: agora["t"])
    return agora


def test_o_clique_engolido_dispara_o_guarda(relogio):
    ui = _UI()
    assert ui._desobstruir_se_faz_tempo("sair da cave") is True
    assert len(ui.chamadas) == 1
    assert "sair da cave" in ui.chamadas[0]


def test_o_guarda_e_estrangulado(relogio):
    """Janela NÃO aparece sozinha: entre duas tentativas separadas por
    segundos nada mudou. Uma captura por tentativa custaria caro na disputa da
    entrada, que dispara dois cliques por segundo."""
    ui = _UI()
    ui._desobstruir_se_faz_tempo("entrar na cave")
    ui._desobstruir_se_faz_tempo("entrar na cave")
    ui._desobstruir_se_faz_tempo("entrar na cave")
    assert len(ui.chamadas) == 1

    relogio["t"] += ui_do_jogo.INTERVALO_DO_GUARDA_DE_JANELA + 0.1
    ui._desobstruir_se_faz_tempo("entrar na cave")
    assert len(ui.chamadas) == 2


def test_estrangulado_devolve_None_e_nao_False(relogio):
    """`None` aqui é "não perguntei", não "não sei se há janela" — quem chama
    não decide nada com isto."""
    ui = _UI()
    ui._desobstruir_se_faz_tempo("x")
    assert ui._desobstruir_se_faz_tempo("x") is None


def test_o_intervalo_e_de_3s():
    assert ui_do_jogo.INTERVALO_DO_GUARDA_DE_JANELA == 3.0


def test_o_guarda_esta_no_FUNIL_e_cobre_os_seis_pares():
    """Os seis pares de clique de NPC do bot passam por
    `_abrir_dialogo_e_clicar` — link da cave, Altar Stone, saída, Rich, HH. Um
    guarda no funil cobre todos; um guarda na saída cobriria a saída."""
    import inspect

    fonte = inspect.getsource(ui_do_jogo.UIDoJogo._clicar_no_npc_e_no_link)
    assert "_desobstruir_se_faz_tempo" in fonte


def test_o_guarda_roda_na_FALHA_e_nao_antes_do_clique():
    """No caminho feliz não custa nada. `desobstruir_a_cena` documenta que o
    guarda é POR EVENTO e não por clique — e o clique engolido é o evento."""
    import ast
    import inspect
    import textwrap

    arvore = ast.parse(textwrap.dedent(inspect.getsource(
        ui_do_jogo.UIDoJogo._clicar_no_npc_e_no_link)))

    dentro_de_if = {
        n.lineno
        for no in ast.walk(arvore) if isinstance(no, ast.If)
        for n in ast.walk(no)
        if isinstance(n, ast.Attribute) and n.attr == "_desobstruir_se_faz_tempo"
    }
    todos = {
        n.lineno for n in ast.walk(arvore)
        if isinstance(n, ast.Attribute) and n.attr == "_desobstruir_se_faz_tempo"
    }
    assert todos, "o guarda saiu do par de cliques"
    assert dentro_de_if == todos, (
        "o guarda saiu de dentro do `if aberto is False`: passaria a custar "
        "uma captura por tentativa na disputa da entrada")


def test_a_entrada_continua_com_o_guarda_de_antes_da_rajada():
    """O guarda novo é a SEGUNDA linha. O da entrada, antes da rajada de dois
    cliques por segundo, continua onde estava."""
    import inspect

    fonte = inspect.getsource(ui_do_jogo.UIDoJogo)
    assert 'desobstruir_a_cena("as tentativas de entrada na cave")' in fonte


def test_o_relogio_e_monotonico_o_bastante_para_o_estrangulamento():
    """Sanidade: o guarda usa `time.time()` do módulo, que é o mesmo relógio
    que o resto do arquivo usa para recarga (`_visao_resetada_em`)."""
    ui = _UI()
    ui._guarda_de_janela_em = time.time()
    assert ui._desobstruir_se_faz_tempo("agora") is None
