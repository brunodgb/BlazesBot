"""O Rich é PROCURADO na tela, e a coordenada fixa vira rede.

=============================================================================
POR QUE MUDOU
=============================================================================

`coords.vendor_npc` (284,336) foi medida com o personagem parado EXATAMENTE em
(158,-494). O comentário dela guarda a medição que mostra a fragilidade: quando
o ponto de parada mudou de (153,-492) para (158,-494) -- **cinco unidades de
mundo** --, o NPC saiu de (464,377) para (172,301) na tela. **Quase 300 px por
cinco passos.**

`PRECISAO_NO_PONTO_DO_VENDEDOR = 0.9` limita o erro, não o elimina: dentro da
tolerância o NPC ainda passeia dezenas de pixels, e o clique direito que erra o
Rich cai na cena 3D.

=============================================================================
O TESTE QUE CARREGA O PESO
=============================================================================

`test_sem_casamento_cai_na_coordenada_fixa` e as variantes de falha.

A propriedade inegociável não é "acha o Rich" -- é **nunca ficar pior que
hoje**. Template ausente, captura falhando, quadro em branco, casamento fraco:
todos têm que devolver a coordenada de sempre, que é exatamente o que o bot
fazia antes. Um caminho novo que devolvesse `None` numa dessas trocaria uma mira
imprecisa por uma venda que não acontece.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from blazesbot.bot import vendedor as janela_de_venda
from blazesbot.bot.bc import vendor as v

FIXA = (284, 336)


class _Templates:
    def __init__(self, template=None):
        self._template = template

    def load(self, _nome):
        return self._template


def _servico(template=None, quadro="padrao", achado="nao-mexer"):
    """`VendorService` sem `__init__`: só o que `_onde_clicar_no_vendedor` toca."""
    servico = v.VendorService.__new__(v.VendorService)
    servico.ctx = SimpleNamespace(
        coords=SimpleNamespace(vendor_npc=FIXA),
        templates=_Templates(template),
        hwnd=1234,
        log=SimpleNamespace(info=lambda *a, **k: None,
                            debug=lambda *a, **k: None,
                            warning=lambda *a, **k: None),
    )
    return servico


def _quadro(largura=1024, altura=768):
    gerador = np.random.default_rng(20260819)
    return gerador.integers(0, 255, (altura, largura, 3), dtype=np.uint8)


def _template_falso():
    return np.zeros((22, 21), dtype=np.uint8)


# ---------------------------------------------------------------------------
# 1. NUNCA PIOR QUE HOJE -- todo caminho de falha devolve a coordenada fixa
# ---------------------------------------------------------------------------

def test_sem_template_cai_na_coordenada_fixa(monkeypatch):
    monkeypatch.setattr(v, "capture_window", lambda _h: _quadro())
    assert _servico(template=None)._onde_clicar_no_vendedor() == FIXA


def test_sem_captura_cai_na_coordenada_fixa(monkeypatch):
    monkeypatch.setattr(v, "capture_window", lambda _h: None)
    assert _servico(template=_template_falso())._onde_clicar_no_vendedor() == FIXA


def test_quadro_em_branco_cai_na_coordenada_fixa(monkeypatch):
    monkeypatch.setattr(v, "capture_window", lambda _h: _quadro())
    monkeypatch.setattr(v, "frame_is_blank", lambda _q: True)
    assert _servico(template=_template_falso())._onde_clicar_no_vendedor() == FIXA


def test_sem_casamento_cai_na_coordenada_fixa(monkeypatch):
    """O caso comum de falha: o Rich não está onde se procurou."""
    monkeypatch.setattr(v, "capture_window", lambda _h: _quadro())
    monkeypatch.setattr(v, "frame_is_blank", lambda _q: False)
    monkeypatch.setattr(v, "find_template", lambda *a, **k: None)

    assert _servico(template=_template_falso())._onde_clicar_no_vendedor() == FIXA


def test_nunca_devolve_None():
    """`_abrir_dialogo_e_clicar` recebe isto e clica: `None` seria um clique em
    lugar nenhum, ou um `TypeError` no meio da venda."""
    for cenario in ({}, {"template": _template_falso()}):
        servico = _servico(**cenario)
        assert servico._onde_clicar_no_vendedor() is not None


# ---------------------------------------------------------------------------
# 2. Achou: usa o que achou
# ---------------------------------------------------------------------------

def test_achou_usa_a_posicao_encontrada(monkeypatch):
    encontrado = (172, 301)          # a posição REAL da medição de (153,-492)
    monkeypatch.setattr(v, "capture_window", lambda _h: _quadro())
    monkeypatch.setattr(v, "frame_is_blank", lambda _q: False)
    monkeypatch.setattr(v, "find_template", lambda *a, **k: encontrado)

    servico = _servico(template=_template_falso())
    assert servico._onde_clicar_no_vendedor() == encontrado, (
        "achou o Rich na tela e clicou na coordenada decorada mesmo assim"
    )


def test_a_busca_e_LIMITADA_a_uma_regiao_em_volta_do_esperado(monkeypatch):
    """Varrer a tela inteira acharia sprite de NPC do outro lado do cenário --
    e um clique direito lá é um clique no lugar errado."""
    regioes = []
    monkeypatch.setattr(v, "capture_window", lambda _h: _quadro())
    monkeypatch.setattr(v, "frame_is_blank", lambda _q: False)
    monkeypatch.setattr(v, "find_template",
                        lambda *a, region=None, **k: regioes.append(region))

    _servico(template=_template_falso())._onde_clicar_no_vendedor()

    assert regioes and regioes[0] is not None, "buscou na tela inteira"
    x, y, largura, altura = regioes[0]
    assert x <= FIXA[0] <= x + largura
    assert y <= FIXA[1] <= y + altura
    assert largura <= 2 * janela_de_venda.RAIO_DA_BUSCA_DO_VENDEDOR + 1


def test_a_regiao_nao_sai_do_quadro(monkeypatch):
    """Região negativa ou maior que o quadro faria o recorte devolver vazio, e
    aí a busca falharia SEMPRE -- em silêncio, caindo na coordenada fixa."""
    regioes = []
    monkeypatch.setattr(v, "capture_window", lambda _h: _quadro(300, 300))
    monkeypatch.setattr(v, "frame_is_blank", lambda _q: False)
    monkeypatch.setattr(v, "find_template",
                        lambda *a, region=None, **k: regioes.append(region))

    _servico(template=_template_falso())._onde_clicar_no_vendedor()

    x, y, largura, altura = regioes[0]
    assert x >= 0 and y >= 0
    assert x + largura <= 300 and y + altura <= 300


# ---------------------------------------------------------------------------
# 3. As constantes
# ---------------------------------------------------------------------------

def test_o_limiar_erra_para_MENOS():
    """Falso negativo cai na reserva (o comportamento de hoje); falso positivo
    manda o clique direito para o lugar errado. Na dúvida, erra para menos."""
    assert janela_de_venda.LIMIAR_DO_VENDEDOR <= 0.85


def test_o_raio_cobre_com_folga_o_erro_que_a_tolerancia_permite():
    """Régua da medição: 5 unidades de mundo ~ 300 px na tela. A tolerância de
    parada é 0,9 unidade, então ~54 px. O raio tem que cobrir isso com sobra."""
    px_por_unidade = 300 / 5
    from blazesbot.bot.bc.mapa_bc import PRECISAO_NO_PONTO_DO_VENDEDOR

    pior_erro = PRECISAO_NO_PONTO_DO_VENDEDOR * px_por_unidade
    assert janela_de_venda.RAIO_DA_BUSCA_DO_VENDEDOR >= 2 * pior_erro, (
        f"raio {janela_de_venda.RAIO_DA_BUSCA_DO_VENDEDOR} px contra erro possível de "
        f"{pior_erro:.0f} px"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
