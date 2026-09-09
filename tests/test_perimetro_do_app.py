"""O PERÍMETRO DE 12 -- a coleira que ANDA DE VOLTA. APP, 09/09/2026.

*"Se a diferença de distância para o Ponto Inicial for MAIOR QUE 12 unidades,
um alarme de perímetro é acionado (...) aborta IMEDIATAMENTE qualquer ataque,
macro ou espera, força a caminhada de volta para o Ponto Inicial exato, ao
chegar aperta F1, e engata um novo TAB"* -- usuário.

=========================================================================
POR QUE ESTE ARQUIVO EXISTE COM ESTE TAMANHO
=========================================================================

Esta é a QUARTA versão da coleira. As três primeiras estão documentadas no topo
de `core/coleira_do_ponto.py`, e duas delas mataram contas. A primeira media
exatamente o que esta mede -- o personagem contra a base, no meio da macro -- e
o defeito não era a medição: era **cortar sem andar de volta**.

Então o que estes testes guardam, acima de tudo, são as três propriedades que
faltavam:

    1. QUEM CORTA, ANDA           -- o recolhimento é a mesma rotina
    2. ANDA EM BATALHA            -- exceção deliberada, e é o conserto
    3. SABE DESISTIR              -- senão o travamento permanente volta
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from blazesbot.bot.app import executor as mod
from blazesbot.core import coleira_do_ponto, vigia_da_vida, volta_ao_ponto

BASE = (1000, 1000)


# ---------------------------------------------------------------------------
# EIXO 1 -- A RÉGUA
# ---------------------------------------------------------------------------

def test_dentro_do_raio_nao_acusa():
    assert coleira_do_ponto.estourou_o_perimetro((1000, 1012), BASE) is None
    assert coleira_do_ponto.estourou_o_perimetro((1000, 1000), BASE) is None


def test_passou_de_12_acusa_e_devolve_a_distancia():
    d = coleira_do_ponto.estourou_o_perimetro((1000, 1013), BASE)
    assert d is not None and d > 12


def test_SEM_leitura_nao_acusa():
    """"Não sei" não interrompe macro nem manda ninguém andar."""
    assert coleira_do_ponto.estourou_o_perimetro(None, BASE) is None
    assert coleira_do_ponto.estourou_o_perimetro((1, 1), None) is None


def test_o_raio_e_DOZE():
    """Número do usuário, não arredondamento de medição."""
    assert coleira_do_ponto.RAIO_DO_PERIMETRO == 12


# ---------------------------------------------------------------------------
# O EXECUTOR
# ---------------------------------------------------------------------------

class _Caso:
    """O executor cru, com só o que o perímetro toca."""

    def __init__(self, posicoes, chega=True, base=BASE, ligado=True):
        e = mod.ExecutorDeMacro.__new__(mod.ExecutorDeMacro)
        self.e = e
        self.posicoes = list(posicoes)
        self.chega = chega
        self.linhas: list[tuple[str, str]] = []
        self.teclas: list[str] = []
        self.cliques: list[tuple[int, int]] = []
        self.tabs = 0
        self.dormidas: list[float] = []

        e.log = SimpleNamespace(
            info=lambda f, *a: self.linhas.append(("INFO", f % a if a else f)),
            warning=lambda f, *a: self.linhas.append(("WARN", f % a if a else f)),
            error=lambda f, *a: self.linhas.append(("ERRO", f % a if a else f)),
            debug=lambda *a, **k: None)
        e._travar_posicao = ligado
        e._base_pos = base
        e._minimap_center = (500, 100)
        e._posicao_atual = self._pos
        e._ultima_posicao_conhecida = None
        e._recolhimentos_falhos = 0
        e._perimetro_desistido_ate = 0.0
        e._continuar = lambda: True
        e.input = SimpleNamespace(
            key=self.teclas.append,
            right_click=lambda x, y, repetir=False: self.cliques.append((x, y)))
        e._dormir = self._dormir
        e._conseguir_o_tab = self._tab
        e._vigia = vigia_da_vida.VigiaDaVida()

    def _pos(self):
        if not self.posicoes:
            return BASE if self.chega else (1000, 1030)
        return self.posicoes.pop(0)

    def _dormir(self, s):
        self.dormidas.append(s)
        return True

    def _tab(self):
        self.tabs += 1
        return True


def test_o_perimetro_DESLIGADO_com_a_trava_de_posicao_desligada():
    """Sem trava de posição não há ponto para prender ninguém."""
    caso = _Caso(posicoes=[(1000, 1040)], ligado=False)
    assert caso.e._estourei_o_perimetro() is None


def test_o_perimetro_acusa_e_devolve_a_distancia():
    caso = _Caso(posicoes=[(1000, 1040)])
    assert caso.e._estourei_o_perimetro() == pytest.approx(40, abs=1)


def test_o_recolhimento_ANDA_confirma_a_chegada_e_faz_F1_e_TAB():
    """Os eixos 2 e 3 inteiros, na ordem."""
    caso = _Caso(posicoes=[(1000, 1040), BASE])
    assert caso.e._recolher_ao_ponto(40.0) is True

    assert caso.cliques, "não mandou andar"
    assert caso.teclas == [mod.TECLA_DE_LIMPEZA_DO_PERIMETRO], caso.teclas
    assert caso.dormidas == [mod.ESPERA_DEPOIS_DA_LIMPEZA]
    assert caso.tabs == 1, "não engatou o TAB"


def test_o_F1_so_sai_DEPOIS_de_chegar():
    """Apertar a tecla de limpeza no meio do caminho não limparia nada."""
    caso = _Caso(posicoes=[(1000, 1040)], chega=False)
    caso.e._esperar_chegar_na_base = lambda teto: False
    caso.e._recolher_ao_ponto(40.0)
    assert caso.teclas == [], "apertou F1 sem ter chegado"
    assert caso.tabs == 0


def test_TRES_recolhimentos_sem_chegar_e_o_perimetro_DESISTE():
    """A saída de emergência que faltou na 1ª versão.

    Personagem preso em parede não chega nunca. Sem isto, o perímetro cortaria
    toda volta para sempre e o bot nunca mais lutaria -- que é exatamente o
    travamento que matou contas em 04/09/2026.
    """
    caso = _Caso(posicoes=[], chega=False)
    caso.e._esperar_chegar_na_base = lambda teto: False

    for _ in range(mod.RECOLHIMENTOS_SEGUIDOS_PARA_DESISTIR):
        caso.e._recolher_ao_ponto(40.0)

    assert caso.e._perimetro_desistido_ate > 0, "não desistiu"
    assert caso.e._estourei_o_perimetro() is None, \
        "continuou cortando depois de desistir"
    assert any("PERÍMETRO" in t and "parede" in t for _n, t in caso.linhas), \
        caso.linhas


def test_chegar_ZERA_a_contagem_de_falhas():
    """Uma caminhada difícil não pode aproximar a desistência da seguinte."""
    caso = _Caso(posicoes=[], chega=True)
    caso.e._esperar_chegar_na_base = lambda teto: False
    caso.e._recolher_ao_ponto(40.0)
    assert caso.e._recolhimentos_falhos == 1

    caso.e._esperar_chegar_na_base = lambda teto: True
    caso.e._recolher_ao_ponto(40.0)
    assert caso.e._recolhimentos_falhos == 0


def test_sem_como_andar_NAO_conta_como_falha_de_caminhada():
    """Sem base ou sem centro do minimapa o problema é outro, e desistir da
    caminhada por causa dele esconderia a causa real."""
    caso = _Caso(posicoes=[(1000, 1040)])
    caso.e._minimap_center = None
    assert caso.e._recolher_ao_ponto(40.0) is True
    assert caso.e._recolhimentos_falhos == 0
    assert caso.cliques == []


# ---------------------------------------------------------------------------
# EIXO 2 -- O CORTE, NOS TRÊS LUGARES
# ---------------------------------------------------------------------------

def test_o_corte_acontece_no_TOPO_da_volta_no_MEIO_da_macro_e_na_ESPERA():
    """*"Aborta IMEDIATAMENTE qualquer ataque, macro ou espera"*.

    Três pontos de detecção e UM de ação: o topo da volta é quem anda. Ter dois
    lugares andando seria ter duas caminhadas concorrentes para o mesmo ponto.
    """
    import inspect

    laco = inspect.getsource(mod.ExecutorDeMacro._uma_volta_simples)
    espera = inspect.getsource(mod.ExecutorDeMacro._esperar)

    assert laco.count("_estourei_o_perimetro()") == 2, \
        "faltou o corte no topo da volta ou no meio da macro"
    assert "_recolher_ao_ponto" in laco, "detecta e não age"
    assert "_estourei_o_perimetro()" in espera, "a espera não é cortada"
    assert "_recolher_ao_ponto" not in espera, \
        "a espera também anda -- duas caminhadas concorrentes"


def test_o_teto_da_caminhada_e_o_MESMO_da_cura():
    """Um número lido por dois lados mora num lugar só."""
    from blazesbot.bot.app import cura

    assert volta_ao_ponto.SEGUNDOS_PARA_CHEGAR == cura.SEGUNDOS_PARA_VOLTAR_AO_PONTO
