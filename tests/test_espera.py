"""O orquestrador da espera: `core/espera.ate`.

=============================================================================
POR QUE ESTE ARQUIVO É CURTO E MESMO ASSIM PESA
=============================================================================

Toda espera do bot que TEM o que perguntar passa a viver aqui dentro. Um defeito
neste laço não aparece como exceção — aparece como bot lento (passo dormido
inteiro na última volta), bot surdo (Parar ignorado no meio de uma rajada) ou
telemetria mentindo (desfecho contado errado).

As seis propriedades que o resto do projeto passa a poder assumir:

  1. **Pergunta ANTES de esperar.** Confirmar em zero é o caso comum — nove em
     dez entradas na HH confirmam assim.
  2. **Sai no instante da resposta**, sem dormir o resto do passo.
  3. **`None` encerra na hora**: "não dá para saber" não é "não aconteceu", e
     insistir na leitura não faz a captura voltar a funcionar.
  4. **Dois tetos, e pelo menos um é obrigatório**: tempo e voltas. Espera sem
     teto nenhum é laço infinito com outro nome.
  5. **O passo nunca passa do que falta** para o teto.
  6. **O Parar é perguntado a cada volta.**
"""
from __future__ import annotations

import pytest

from blazesbot.core import cronometro, espera


class _Ctx:
    def __init__(self, parar_em: int | None = None) -> None:
        self.esperas: list[float] = []
        self.paradas = 0
        self.parar_em = parar_em

    def tick(self, segundos: float) -> None:
        self.esperas.append(segundos)

    def raise_if_stopped(self) -> None:
        self.paradas += 1
        if self.parar_em is not None and self.paradas >= self.parar_em:
            raise KeyboardInterrupt("Parar")


def _respostas(*valores):
    fila = list(valores)

    def perguntar():
        return fila.pop(0) if len(fila) > 1 else fila[0]

    return perguntar


# ===========================================================================
# O laço
# ===========================================================================

def test_pergunta_ANTES_de_esperar():
    """Confirmar em zero é o caso comum, e é ele que paga o orquestrador."""
    ctx = _Ctx()
    fim = espera.ate(_respostas(True), ctx=ctx, teto=10.0, passo=1.0, o_que="t")
    assert fim and fim.motivo == espera.CONFIRMADO
    assert fim.voltas == 1
    assert ctx.esperas == [], "dormiu antes de perguntar"


def test_sai_no_instante_da_resposta():
    ctx = _Ctx()
    fim = espera.ate(_respostas(False, False, True), ctx=ctx, teto=10.0,
                     passo=0.01, o_que="t")
    assert fim.voltas == 3
    assert len(ctx.esperas) == 2, "esperou depois de a condição acontecer"


def test_NAO_SEI_encerra_na_hora_e_nao_e_False():
    """Cliente minimizado: insistir não faz a captura voltar."""
    ctx = _Ctx()
    fim = espera.ate(_respostas(None), ctx=ctx, teto=10.0, passo=1.0, o_que="t")
    assert fim.confirmado is None
    assert fim.motivo == espera.NAO_SEI
    assert not fim, "`None` não pode contar como condição satisfeita"
    assert ctx.esperas == []


def test_o_teto_de_TEMPO_encerra():
    ctx = _Ctx()
    fim = espera.ate(_respostas(False), ctx=ctx, teto=0.05, passo=0.01,
                     o_que="t")
    assert fim.motivo == espera.TETO
    assert fim.confirmado is False
    # 1 µs de TOLERÂNCIA, e ela tem medida: `time.time()` vale ~1,8e9, onde o
    # passo do float64 é ~2,4e-7 s -- `(comeco + 0.05) - comeco` pode sair
    # 0.04999988. Oscilou na suíte inteira em 25/09/2026 (3 de 3 verdes isolado).
    assert fim.segundos >= 0.05 - 1e-6


def test_o_teto_de_VOLTAS_encerra_e_e_distinguivel():
    """A rajada conta cliques, não segundos -- e o log precisa saber qual foi."""
    ctx = _Ctx()
    fim = espera.ate(_respostas(False), ctx=ctx, teto=None, passo=0.0,
                     o_que="t", voltas_maximas=4)
    assert fim.motivo == espera.VOLTAS
    assert fim.voltas == 4
    assert len(ctx.esperas) == 3, "esperou depois da última volta"


def test_sem_teto_nenhum_RECUSA():
    """Laço infinito com outro nome. Melhor explodir na primeira chamada."""
    with pytest.raises(ValueError, match="sem teto"):
        espera.ate(_respostas(False), ctx=_Ctx(), teto=None, passo=0.1,
                   o_que="t")


def test_o_passo_nunca_passa_do_que_FALTA():
    """Um teto de 0,12 s com passo de 0,04 s não pode custar 0,16 s."""
    ctx = _Ctx()
    espera.ate(_respostas(False), ctx=ctx, teto=0.1, passo=1.0, o_que="t")
    assert ctx.esperas, "não esperou nada dentro do teto"
    assert all(e <= 0.1 for e in ctx.esperas), ctx.esperas


def test_o_PARAR_e_perguntado_a_cada_volta():
    ctx = _Ctx(parar_em=3)
    with pytest.raises(KeyboardInterrupt):
        espera.ate(_respostas(False), ctx=ctx, teto=100.0, passo=0.0,
                   o_que="t")
    assert ctx.paradas == 3


def test_a_acao_acontece_ANTES_da_pergunta():
    """Perguntar antes de agir responderia sobre a tela de antes."""
    ordem: list[str] = []
    ctx = _Ctx()
    espera.ate(lambda: (ordem.append("pergunta"), True)[1], ctx=ctx,
               teto=1.0, passo=0.01, o_que="t",
               agir=lambda: ordem.append("acao"))
    assert ordem == ["acao", "pergunta"]


# ===========================================================================
# A telemetria, que é metade do motivo de o módulo existir
# ===========================================================================

def test_toda_espera_e_cronometrada_e_CONTADA_por_desfecho(monkeypatch):
    medidos: list[tuple[str, float]] = []
    marcados: list[tuple[str, str]] = []
    monkeypatch.setattr(cronometro, "anotar",
                        lambda nome, gasto: medidos.append((nome, gasto)))
    monkeypatch.setattr(cronometro, "marcar",
                        lambda nome, desfecho: marcados.append((nome, desfecho)))

    espera.ate(_respostas(True), ctx=_Ctx(), teto=1.0, passo=0.01,
               o_que="entrada_na_hh")

    assert medidos and medidos[0][0] == "espera.entrada_na_hh"
    assert marcados == [("espera.entrada_na_hh", espera.CONFIRMADO)]


def test_o_desfecho_do_TETO_tambem_e_contado(monkeypatch):
    """Sem isto, "quantas esperas morreram no teto" volta a ser grep em prosa."""
    marcados: list[tuple[str, str]] = []
    monkeypatch.setattr(cronometro, "marcar",
                        lambda nome, desfecho: marcados.append((nome, desfecho)))

    espera.ate(_respostas(False), ctx=_Ctx(), teto=0.01, passo=0.005,
               o_que="x")
    assert marcados == [("espera.x", espera.TETO)]


def test_o_contador_do_cronometro_agrega_por_desfecho():
    """O caminho quente de verdade: sem relógio, e uma linha por nome."""
    cronometro.zerar_para_teste()
    cronometro.marcar("espera.x", "confirmado")
    cronometro.marcar("espera.x", "confirmado")
    cronometro.marcar("espera.x", "teto")

    from blazesbot.core.cronometro import _meu_balde

    assert _meu_balde().desfechos == {
        "espera.x": {"confirmado": 2, "teto": 1}}
    cronometro.zerar_para_teste()
