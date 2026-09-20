"""O Sell é confirmado pela BOLSA, e reclicado quando não vende.

O DEFEITO, MEDIDO EM 20/09/2026 sobre 129 vendas do log: **7 saíram com ZERO
itens** (5,4%) — bolsa 55->55, 57->57, 32->32, 28->28, 31->31, 33->33, 55->55.

A distribuição é **bimodal**: ou sai ~20 itens, ou sai nenhum. Nunca parcial. É
isso que aponta o culpado: os 24 cliques montam a lista e o Sell é o **commit**.
Perder o commit não perde metade — perde a passada inteira.

O QUE FOI DESCARTADO POR MEDIÇÃO, e não por opinião:

  * **janela ausente ou deslocada** — em 6 dos 7 casos a âncora FOI casada por
    imagem (`janela localizada`), e `_ponto_do_slot` já devolve `None` sem
    âncora, então o bot não clica no vazio;
  * **o guarda de janela fechando a venda** — ele disparou em 44 das 122 vendas
    BOAS também; não separa os grupos;
  * **tempo** — `ESPERA_ANTES_DO_SELL` já tinha sido adicionada por causa de um
    defeito idêntico ("um Sell engolido marca a passada como vendida sem ter
    vendido nada"), e o defeito voltou em 5,4%. Tempo não fecha isso.

O que sobrou: `ctx.click(botao_vender)` saía **uma vez, cego**, e a única
conferência era `antes - depois` no FIM da venda inteira — tarde demais para
agir. Ela só servia para registrar o prejuízo.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot import vendedor


class _Ctx:
    def __init__(self, contagens, relogio):
        # O RELÓGIO É COMPARTILHADO com o `time.time` mockado: `tick` tem de
        # FAZER O TEMPO ANDAR, senão o teto de `_esperar_a_bolsa_baixar` nunca
        # vence e o teste roda para sempre. Foi o que aconteceu na primeira
        # versão deste arquivo.
        self._relogio = relogio
        self._contagens = list(contagens)
        self.cliques = []
        self.dormiu = 0.0
        self.log = SimpleNamespace(info=lambda *a, **k: None,
                                   debug=lambda *a, **k: None,
                                   warning=lambda *a, **k: None,
                                   error=lambda *a, **k: None)
        self.memory = SimpleNamespace(bag_count=self._bag)

    def _bag(self):
        return (self._contagens.pop(0) if len(self._contagens) > 1
                else self._contagens[0])

    def click(self, ponto):
        self.cliques.append(ponto)

    def tick(self, s):
        self.dormiu += s
        self._relogio["t"] += s

    def raise_if_stopped(self):
        pass


def _vendedor(contagens, relogio, caixas=0):
    v = object.__new__(vendedor.JanelaDeVenda)
    v.ctx = _Ctx(contagens, relogio)
    v._caixas_fechadas = 0

    def _dismiss():
        v._caixas_fechadas += 1
        return v._caixas_fechadas <= caixas
    v._dismiss_confirm = _dismiss
    return v


@pytest.fixture
def relogio(monkeypatch):
    """O relógio que importa é o de `core/espera`.

    A conferência da bolsa passou a ser `espera.ate` em 20/09/2026 — a peça
    compartilhada que o projeto usa para toda espera com teto —, então
    `vendedor.py` nem importa mais `time`.
    """
    from blazesbot.core import espera

    agora = {"t": 0.0}
    monkeypatch.setattr(espera.time, "time", lambda: agora["t"])
    return agora


# ---------------------------------------------------------------------------
# 1. o caminho feliz -- e ele tem de sair CEDO
# ---------------------------------------------------------------------------

def test_bolsa_baixou_no_primeiro_clique(relogio):
    v = _vendedor([58, 36], relogio)

    assert v._vender_a_lista((100, 200), antes=58) is True
    assert v.ctx.cliques == [(100, 200)]


def test_venda_boa_NAO_paga_o_teto_inteiro(relogio):
    """A espera de 0,60 s virou PERGUNTA: sai no instante em que a bolsa baixa.

    Era gasto fixo em toda passada, três passadas por venda.
    """
    v = _vendedor([58, 36], relogio)
    v._vender_a_lista((1, 1), antes=58)

    assert v.ctx.dormiu < vendedor.ESPERA_DEPOIS_DO_SELL


# ---------------------------------------------------------------------------
# 2. o defeito: o Sell engolido
# ---------------------------------------------------------------------------

def test_sell_engolido_e_RECLICADO(relogio):
    """O primeiro clique não move a bolsa; o SEGUNDO move.

    A bolsa reage ao Nº DE CLIQUES, e não a um número de leituras: assim o
    teste não depende da aritmética entre o teto e o passo da conferência.
    """
    v = _vendedor([58], relogio)
    v.ctx.memory.bag_count = lambda: 36 if len(v.ctx.cliques) >= 2 else 58

    assert v._vender_a_lista((1, 1), antes=58) is True
    assert len(v.ctx.cliques) == 2


def test_tres_falhas_devolvem_False_e_nao_martelam(relogio):
    v = _vendedor([58], relogio)

    assert v._vender_a_lista((1, 1), antes=58) is False
    assert len(v.ctx.cliques) == vendedor.TENTATIVAS_NO_SELL


def test_entre_as_tentativas_a_caixa_e_fechada(relogio):
    """Uma caixa aberta engole o Sell — é a causa que dá para tratar aqui."""
    v = _vendedor([58], relogio)
    v._vender_a_lista((1, 1), antes=58)

    assert v._caixas_fechadas >= vendedor.TENTATIVAS_NO_SELL


def test_NENHUM_clique_no_slot_entre_as_tentativas(relogio):
    """É o que torna o reclique seguro: a lista já está montada, então o Sell
    repetido concretiza A MESMA venda. Um clique novo no slot entre eles
    montaria outra lista."""
    v = _vendedor([58], relogio)
    v._vender_a_lista((7, 7), antes=58)

    assert set(v.ctx.cliques) == {(7, 7)}, (
        "clicou em outro ponto entre as tentativas; o reclique deixa de ser a "
        "mesma venda")


# ---------------------------------------------------------------------------
# 3. sem leitura de bolsa -- volta ao comportamento antigo
# ---------------------------------------------------------------------------

def test_sem_bag_count_clica_UMA_vez_e_segue(relogio):
    """`None` não é falha, é "não dá para perguntar". Recusar aqui deixaria a
    venda impossível numa conta cuja memória não responde, e bolsa cheia trava
    a run inteira."""
    v = _vendedor([None], relogio)

    assert v._vender_a_lista((1, 1), antes=None) is None
    assert len(v.ctx.cliques) == 1
    assert v.ctx.dormiu == pytest.approx(vendedor.ESPERA_DEPOIS_DO_SELL)


def test_bolsa_que_para_de_responder_no_meio_nao_trava(relogio):
    """Leitura vira `None` depois do clique: o teto encerra a pergunta."""
    v = _vendedor([58, None], relogio)

    assert v._vender_a_lista((1, 1), antes=58) is False
    assert relogio["t"] >= vendedor.ESPERA_DEPOIS_DO_SELL


# ---------------------------------------------------------------------------
# 4. a integração no laço, e o alcance nos dois ecossistemas
# ---------------------------------------------------------------------------

def test_o_laco_da_venda_usa_o_sell_conferido():
    import inspect

    fonte = inspect.getsource(vendedor.JanelaDeVenda.sell_from_slot)
    assert "_vender_a_lista" in fonte
    assert "ctx.click(botao_vender)" not in fonte, "voltou o Sell cego"


def test_o_Sell_falhado_NAO_encerra_a_venda():
    """O `break` foi TENTADO e REPROVADO em 20/09/2026.

    Parecia certo ("commit quebrado, não adianta seguir"), e
    `tests/test_venda_rearranjo.py` o derrubou na hora: com a grade vendendo
    normalmente e a bolsa do dublê parada, ele encerrava a venda na primeira
    passada — 24 itens de 66. `bag_count` pode simplesmente atrasar além do
    teto, e aí parar mata uma venda que estava funcionando.

    O reclique fica; a decisão de abandonar a ida, não.
    """
    import inspect

    fonte = inspect.getsource(vendedor.JanelaDeVenda.sell_from_slot)
    assert "if vendeu is False:" not in fonte, (
        "voltou o break: uma bolsa lenta passa a matar venda boa")


@pytest.mark.parametrize("modulo", [
    "blazesbot.bot.bc.vendor",
    "blazesbot.bot.hh.vendedor",
])
def test_os_DOIS_ecossistemas_herdam_o_mesmo_conserto(modulo):
    """`sell_from_slot` é UMA, em `bot/vendedor.py`. BC e HH já a chamam —
    injetar o conserto em dois lugares seria a duplicata que o projeto proíbe."""
    import importlib

    mod = importlib.import_module(modulo)
    classe = next(
        obj for nome, obj in vars(mod).items()
        if isinstance(obj, type) and issubclass(obj, vendedor.JanelaDeVenda)
        and obj is not vendedor.JanelaDeVenda)
    assert classe.sell_from_slot is vendedor.JanelaDeVenda.sell_from_slot
    assert classe._vender_a_lista is vendedor.JanelaDeVenda._vender_a_lista
