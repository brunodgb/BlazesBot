"""Rolar a lista do diálogo — a capacidade que a HH precisa e a BC nunca precisou.

`clicar_link` procura o template do link na tela e desiste em três tentativas.
Isso basta para `Ghost Din Woods` (Need 7, nível 48), que está na parte visível
da lista do Transport Fay. NÃO basta para `West Suburb of Stone City` (Need 5,
nível 20): sem rolar, o diálogo mostra de `Sky Village` a `Star Town`, e o
template nunca vai aparecer por mais que se insista.

O QUE ESTE TESTE PROTEGE, e é a parte perigosa: a seta é achada por TEMPLATE, e
sem o template o bot NÃO CLICA. Um deslocamento chutado a partir da moldura do
diálogo erra por alguns pixels, o clique cai fora da janela — na cena 3D — e o
personagem ANDA, saindo da coordenada de onde o NPC responde. Falhar de forma
visível é barato; clicar no lugar errado leva a run junto.
"""
import pytest

from blazesbot.bot import ui_do_jogo
from blazesbot.bot.ui_do_jogo import UIDoJogo


class _Log:
    def __init__(self):
        self.linhas = []

    def _guardar(self, nivel):
        def escrever(msg, *args):
            self.linhas.append((nivel, msg % args if args else msg))
        return escrever

    def __getattr__(self, nome):
        return self._guardar(nome)

    def texto(self):
        return " | ".join(linha for _, linha in self.linhas)


class _Templates:
    def __init__(self, existentes):
        self._existentes = existentes

    def load(self, nome):
        return f"tpl:{nome}" if nome in self._existentes else None


class _Ctx:
    def __init__(self, templates):
        self.log = _Log()
        self.hwnd = 1
        self.templates = templates
        self.cliques = []
        self.ticks = 0.0

    def click(self, ponto):
        self.cliques.append(ponto)

    def tick(self, s=0.2):
        self.ticks += s

    def raise_if_stopped(self):
        pass


def _ui(monkeypatch, *, tem_seta=True, link_no_passo=None, seta_some_no=None):
    """Um `UIDoJogo` com a tela dublada.

    `link_no_passo` é em qual rolagem o link aparece (None = nunca).
    `seta_some_no` é em qual passo a seta some (fim da lista).
    """
    existentes = {ui_do_jogo.TEMPLATE_DA_SETA_DE_ROLAGEM} if tem_seta else set()
    ui = object.__new__(UIDoJogo)
    ui.ctx = _Ctx(_Templates(existentes))

    estado = {"passo": 0}

    def achar_link(_template):
        return (300, 400) if (link_no_passo is not None
                              and estado["passo"] >= link_no_passo) else None

    monkeypatch.setattr(ui, "_achar_link", achar_link, raising=False)
    monkeypatch.setattr(ui_do_jogo, "capture_window", lambda _h: "quadro")

    def find_template(_quadro, _tpl, threshold=None):
        if seta_some_no is not None and estado["passo"] >= seta_some_no:
            return None
        return (480, 650)

    monkeypatch.setattr(ui_do_jogo, "find_template", find_template)

    original = ui.ctx.click

    def clicar(ponto):
        estado["passo"] += 1
        original(ponto)

    ui.ctx.click = clicar
    return ui


# ===========================================================================
# O caminho feliz
# ===========================================================================


def test_o_link_ja_visivel_NAO_rola_nada(monkeypatch):
    """Rolar sem precisar mexeria a lista e poderia esconder o que já estava lá."""
    ui = _ui(monkeypatch, link_no_passo=0)

    assert ui.rolar_o_dialogo("link_qualquer.png") == (300, 400)
    assert ui.ctx.cliques == [], "rolou com o link já na tela"


def test_para_no_INSTANTE_em_que_o_link_aparece(monkeypatch):
    """`passos` é TETO, não gasto. Rolar um número fixo seria espera cega."""
    ui = _ui(monkeypatch, link_no_passo=3)

    assert ui.rolar_o_dialogo("link_qualquer.png") == (300, 400)
    assert len(ui.ctx.cliques) == 3, "não parou assim que o link apareceu"


def test_o_teto_de_passos_e_respeitado(monkeypatch):
    """Link que não existe na lista não pode virar laço infinito."""
    ui = _ui(monkeypatch, link_no_passo=None)

    assert ui.rolar_o_dialogo("link_qualquer.png", passos=4) is None
    assert len(ui.ctx.cliques) == 4


# ===========================================================================
# A recusa que protege a run
# ===========================================================================


def test_SEM_O_TEMPLATE_DA_SETA_NAO_CLICA(monkeypatch):
    """O teste mais importante do arquivo.

    Sem o template, o único jeito de rolar seria chutar um deslocamento a partir
    da moldura -- e errar por alguns pixels põe o clique na cena 3D, o que faz o
    personagem ANDAR e sair da coordenada de onde o NPC responde.
    """
    ui = _ui(monkeypatch, tem_seta=False, link_no_passo=2)

    assert ui.rolar_o_dialogo("link_qualquer.png") is None
    assert ui.ctx.cliques == [], "clicou sem saber onde a seta está"


def test_a_recusa_DIZ_o_que_recortar(monkeypatch):
    """Falha silenciosa vira 'a HH não entra e ninguém sabe por quê'."""
    ui = _ui(monkeypatch, tem_seta=False)
    ui.rolar_o_dialogo("link_qualquer.png")

    texto = ui.ctx.log.texto()
    assert ui_do_jogo.TEMPLATE_DA_SETA_DE_ROLAGEM in texto
    assert "data/templates" in texto
    assert "recorte" in texto.lower()


def test_a_seta_sumir_significa_FIM_DA_LISTA(monkeypatch):
    """O jogo esconde a seta no fim. Insistir ali é clicar onde não há botão."""
    ui = _ui(monkeypatch, link_no_passo=None, seta_some_no=2)

    assert ui.rolar_o_dialogo("link_qualquer.png") is None
    assert len(ui.ctx.cliques) == 2
    assert "fim" in ui.ctx.log.texto().lower()


def test_sem_imagem_nao_chuta(monkeypatch):
    """Cliente minimizado ou captura falhando: não se clica no escuro."""
    ui = _ui(monkeypatch, link_no_passo=None)
    monkeypatch.setattr(ui_do_jogo, "capture_window", lambda _h: None)

    assert ui.rolar_o_dialogo("link_qualquer.png") is None
    assert ui.ctx.cliques == []


# ===========================================================================
# A ligação com a HH
# ===========================================================================


def test_a_viagem_da_HH_pede_rolagem_e_a_da_BC_nao():
    """O destino da BC está na parte visível da lista; o da HH, não.

    Se alguém ligar `rolar` na BC, a viagem passa a pagar uma procura de
    template a mais por run sem motivo; se DESligar na HH, o bot nunca acha
    `West Suburb of Stone City` e a cave fica inalcançável.
    """
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.bc.ui_service import UIService

    # Pelo ARGUMENTO da chamada, não pelo texto do arquivo: a docstring do
    # método explica a rolagem justamente para dizer por que a BC não usa, e
    # procurar a palavra encontraria a explicação em vez do comportamento.
    fonte = textwrap.dedent(inspect.getsource(
        UIService.viajar_para_ghost_din_woods))
    chamadas = [n for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call)
                and any(k.arg == "rolar" for k in n.keywords)]
    assert not chamadas, "a BC não precisa rolar a lista do Fay"


@pytest.mark.parametrize("nome", ["TEMPLATE_DA_SETA_DE_ROLAGEM",
                                  "PASSOS_DE_ROLAGEM", "ESPERA_DA_ROLAGEM"])
def test_as_constantes_da_rolagem_moram_no_modulo_compartilhado(nome):
    """Elas descrevem o JOGO (o diálogo do NPC), não uma cave."""
    assert hasattr(ui_do_jogo, nome)
