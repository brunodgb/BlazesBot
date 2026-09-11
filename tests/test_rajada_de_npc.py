"""A rajada de clique direito que pergunta entre os cliques.

=============================================================================
O QUE ESTE ARQUIVO TRAVA
=============================================================================

A rajada cega era o PISO de toda conversa com NPC: 10 cliques a 44 ms = 396 ms
pagos sempre, e `UIDoJogo._abrir_dialogo_e_clicar` tinha mínimo medido de
424,32 ms em 64.076 aberturas (telemetria de 09 e 10/09/2026). Perguntar custa
27,61 ms e responde; esperar custa 44 ms e não responde.

As quatro propriedades inegociáveis:

  1. **Abriu, para.** Clicar depois do diálogo aberto é clicar DENTRO dele.
  2. **Sem imagem, a rajada sai inteira.** Cliente minimizado é modo normal de
     operação; recusar ali deixaria a entrada na cave impossível.
  3. **O espaçamento é só ENTRE cliques.** Adiar o primeiro é adiar a ação.
  4. **O interruptor devolve o comportamento antigo**, inteiro.
"""
from __future__ import annotations

import pytest

from blazesbot.bot import rajada_de_npc as r
from blazesbot.core.inputs import (
    CLIQUES_DIREITOS_POR_TENTATIVA,
    INTERVALO_ENTRE_CLIQUES_DIREITOS,
)

PONTO = (467, 377)


class _Ctx:
    """Anota o que a rajada fez: cliques (com `repetir`), esperas e Paradas.

    `raise_if_stopped` está aqui porque o orquestrador (`core/espera.py`)
    pergunta por ela a cada volta -- é ela que faz o Parar do usuário valer
    dentro de uma rajada de dez cliques.
    """

    def __init__(self) -> None:
        self.cliques: list[tuple[tuple[int, int], bool]] = []
        self.esperas: list[float] = []
        self.paradas = 0

    def right_click(self, ponto, repetir=True):
        self.cliques.append((ponto, repetir))

    def tick(self, segundos):
        self.esperas.append(segundos)

    def raise_if_stopped(self):
        self.paradas += 1


def _respostas(*valores):
    """Uma pergunta que devolve os valores em ordem, e o último para sempre."""
    fila = list(valores)

    def perguntar():
        return fila.pop(0) if len(fila) > 1 else fila[0]

    return perguntar


@pytest.fixture(autouse=True)
def _com_o_interruptor_ligado(monkeypatch):
    """O estado real do interruptor é conferido por
    `test_o_interruptor_esta_LIGADO`, que lê o módulo."""
    monkeypatch.setattr(r, "PERGUNTAR_ENTRE_OS_CLIQUES", True)


def test_o_interruptor_esta_LIGADO():
    """Lido do MÓDULO, não da fixture -- senão o teste provaria a fixture."""
    import importlib

    assert importlib.import_module(
        "blazesbot.bot.rajada_de_npc").PERGUNTAR_ENTRE_OS_CLIQUES is True


def test_abriu_no_primeiro_clique_NAO_clica_de_novo():
    """O caso comum, e o motivo de tudo: um clique e a conversa começa."""
    ctx = _Ctx()
    assert r.clicar_ate_abrir(ctx, PONTO, _respostas(True)) is True
    assert ctx.cliques == [(PONTO, False)]
    assert ctx.esperas == [], "esperou depois de já ter aberto"


def test_o_espacamento_e_so_ENTRE_os_cliques():
    """Nenhuma espera antes do primeiro clique: ele é a ação."""
    ctx = _Ctx()
    r.clicar_ate_abrir(ctx, PONTO, _respostas(False, False, True))
    assert len(ctx.cliques) == 3
    assert ctx.esperas == [INTERVALO_ENTRE_CLIQUES_DIREITOS] * 2


def test_nunca_abriu_devolve_False_no_TETO_de_cliques():
    ctx = _Ctx()
    assert r.clicar_ate_abrir(ctx, PONTO, _respostas(False)) is False
    assert len(ctx.cliques) == CLIQUES_DIREITOS_POR_TENTATIVA
    assert len(ctx.esperas) == CLIQUES_DIREITOS_POR_TENTATIVA - 1


def test_sem_imagem_a_rajada_sai_INTEIRA_e_devolve_None():
    """Cliente minimizado: não há o que perguntar, e a aposta antiga continua."""
    ctx = _Ctx()
    assert r.clicar_ate_abrir(ctx, PONTO, _respostas(None)) is None
    assert len(ctx.cliques) == CLIQUES_DIREITOS_POR_TENTATIVA, (
        "a rajada encurtou justamente onde não há conferência nenhuma")
    assert all(repetir is False for _, repetir in ctx.cliques), (
        "um clique que repete por dentro faria a contagem mentir")


def test_a_imagem_que_some_no_meio_completa_a_rajada():
    """Respondeu False, depois None: o resto sai cego, sem perder cliques."""
    ctx = _Ctx()
    assert r.clicar_ate_abrir(ctx, PONTO, _respostas(False, None)) is None
    assert len(ctx.cliques) == CLIQUES_DIREITOS_POR_TENTATIVA


def test_o_teto_de_cliques_pode_ser_reduzido_por_quem_chama():
    ctx = _Ctx()
    assert r.clicar_ate_abrir(ctx, PONTO, _respostas(False), cliques=3) is False
    assert len(ctx.cliques) == 3


def test_o_PARAR_e_perguntado_a_cada_volta():
    """Rajada de dez cliques sem olhar o Parar seria meio segundo de bot surdo."""
    ctx = _Ctx()
    r.clicar_ate_abrir(ctx, PONTO, _respostas(False))
    assert ctx.paradas == CLIQUES_DIREITOS_POR_TENTATIVA


def test_DESLIGADO_volta_a_rajada_cega_de_sempre(monkeypatch):
    """Um `right_click` que repete por dentro, e nenhuma pergunta."""
    monkeypatch.setattr(r, "PERGUNTAR_ENTRE_OS_CLIQUES", False)
    ctx = _Ctx()
    perguntas = []

    def perguntar():
        perguntas.append(1)
        return True

    assert r.clicar_ate_abrir(ctx, PONTO, perguntar) is None
    assert ctx.cliques == [(PONTO, True)], "deixou de ser a rajada de sempre"
    assert perguntas == [], "perguntou com o interruptor desligado"


def test_a_UI_usa_a_rajada_e_so_espera_quando_ela_NAO_abriu():
    """A integração: `_clicar_no_npc_e_no_link` não pode voltar a clicar cego."""
    import inspect
    import textwrap

    from blazesbot.bot.ui_do_jogo import UIDoJogo

    fonte = textwrap.dedent(
        inspect.getsource(UIDoJogo._clicar_no_npc_e_no_link))
    assert "rajada_de_npc.clicar_ate_abrir" in fonte
    assert "ctx.right_click(ponto_npc)" not in fonte, (
        "a rajada cega voltou ao caminho quente")
    assert fonte.index("clicar_ate_abrir") < fonte.index("_esperar_o_dialogo"), (
        "a espera do diálogo passou a acontecer ANTES dos cliques")
