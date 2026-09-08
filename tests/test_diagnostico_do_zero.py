"""Quando a limpeza da bolsa apaga ZERO, o log tem que dizer POR QUE.

=========================================================================
O RELATO QUE PEDIU ISTO
=========================================================================

08/09/2026, sobre a HH:

> *"em base a essa imagem quais seriam os itens que seriam deletados?? pois
> vendo aqui deveria deletar pelo menos uma imagem que bate com a
> Trap-Meshwork.png e nao esta deletando"*, e depois: *"mesmo eu limpando o
> inventario, não deletou o item, sendo que eu fiz o template a partir desse
> item do inventario"*.

E o log da época dizia só isto:

    HH: 0 item(ns) de lixo apagado(s) da pasta deletar_hh

=========================================================================
"ZERO" TEM TRÊS CAUSAS, E ELAS PEDEM CORREÇÕES OPOSTAS
=========================================================================

1. **não havia lixo na bolsa** — zero é a resposta certa;
2. **o item estava lá, fora de região varrida** (bolsa extra FECHADA, painel
   arrastado). É geometria: mexer no limiar não muda nada;
3. **o item estava numa região varrida e o casamento ficou abaixo do limiar** —
   e aí o número diz se falta pouco (refazer o PNG, ou medir um limiar novo) ou
   muito (o modelo não é daquele item).

Nenhuma delas aparecia no log, e as três são indistinguíveis sem medida. No caso
do usuário havia prova de que o modelo FUNCIONA -- `Trap-Meshwork` já havia sido
apagado 3 vezes -- então adivinhar o limiar teria sido mexer no lugar errado.

Este arquivo protege o instrumento que responde isso, e a regra de que ele é
**só instrumento**: quem decide apagar continua sendo o limiar.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import numpy as np

from blazesbot.bot import deletador
from blazesbot.core import vision


# ===========================================================================
# A medida
# ===========================================================================


def _quadro(cor=(40, 60, 200), tamanho=(60, 60)) -> np.ndarray:
    q = np.zeros((tamanho[0], tamanho[1], 3), dtype=np.uint8)
    q[:, :] = cor
    return q


def test_o_modelo_IDENTICO_marca_perto_de_um():
    quadro = _quadro()
    quadro[20:30, 20:30] = (10, 250, 10)
    modelo = quadro[20:30, 20:30].copy()

    valor = vision.melhor_casamento(quadro, modelo, colorido=True)
    assert valor is not None and valor > 0.99


def test_o_modelo_de_OUTRA_coisa_marca_baixo():
    """Modelo COM TEXTURA, e não de cor lisa.

    `TM_CCOEFF_NORMED` compara variação em torno da média, então um retângulo
    de cor uniforme contra um fundo uniforme marca 1,00 -- correlação
    degenerada, sem nada a correlacionar. Ícone de item tem textura, e é isso
    que o teste tem que exercitar.
    """
    quadro = _quadro()
    quadro[20:30, 20:30] = (10, 250, 10)          # o ícone que ESTÁ na tela
    quadro[20:25, 20:25] = (250, 250, 10)         # com um canto diferente

    outro = _quadro(cor=(30, 30, 30), tamanho=(10, 10))
    outro[0:5, 5:10] = (250, 10, 250)             # textura em outro lugar
    outro[5:10, 0:5] = (10, 10, 250)

    valor = vision.melhor_casamento(quadro, outro, colorido=True)
    assert valor is not None and valor < 0.9, (
        f"marcou {valor:.2f} contra um ícone que não é dele")


def test_modelo_MAIOR_que_o_recorte_devolve_None():
    """"Não deu para medir" é diferente de "marcou zero" -- e o log distingue."""
    assert vision.melhor_casamento(_quadro(tamanho=(10, 10)),
                                   _quadro(tamanho=(40, 40))) is None


def test_quadro_ou_modelo_ausente_devolve_None():
    assert vision.melhor_casamento(None, _quadro()) is None
    assert vision.melhor_casamento(_quadro(), None) is None


def test_canais_diferentes_NAO_levantam():
    """`matchTemplate` levanta com 3 canais contra 4; aqui é medida, não decisão.

    Levantar dentro de um diagnóstico transformaria "não sei medir" em "a run
    caiu".
    """
    colorido = _quadro(tamanho=(40, 40))
    cinza = np.zeros((10, 10), dtype=np.uint8)
    assert vision.melhor_casamento(colorido, cinza, colorido=True) is None


def test_a_medida_NAO_DECIDE_nada():
    """Nenhum limiar dentro dela: quem apaga é `find_all_templates`."""
    fonte = inspect.getsource(vision.melhor_casamento)
    arvore = ast.parse(textwrap.dedent(fonte))
    comparacoes = [n for n in ast.walk(arvore) if isinstance(n, ast.Compare)]

    for c in comparacoes:
        alvo = ast.unparse(c)
        assert "threshold" not in alvo and "LIMIAR" not in alvo, (
            f"a medida virou decisão: {alvo}")


# ===========================================================================
# O diagnóstico no deletador
# ===========================================================================


def test_o_diagnostico_roda_SO_quando_apagou_zero():
    fonte = inspect.getsource(deletador.deletar_lixo)
    assert "if apagados == 0:" in fonte
    assert "_explicar_o_zero" in fonte


def test_o_diagnostico_NAO_derruba_a_run():
    """Falhar num diagnóstico não pode custar a run."""
    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(deletador._explicar_o_zero)))
    handlers = [n for n in ast.walk(arvore) if isinstance(n, ast.ExceptHandler)]

    assert handlers, "o diagnóstico não tem rede de proteção"
    assert any(getattr(h.type, "id", "") == "Exception" for h in handlers)


def test_o_log_das_BOLSAS_VISIVEIS_existe():
    """Bolsa extra FECHADA não tem etiqueta na tela e não entra na varredura.

    Sem esta linha, esse estado -- o mais provável no relato do usuário -- é
    indistinguível de "não tem lixo".
    """
    fonte = inspect.getsource(deletador.deletar_lixo)
    assert "Bolsas visíveis para a limpeza" in fonte


def test_o_diagnostico_mede_DENTRO_das_regioes():
    """Medir na janela inteira daria o melhor casamento de qualquer lugar.

    Inclusive de fora da bolsa -- e o número passaria a não responder a
    pergunta que ele existe para responder.
    """
    fonte = inspect.getsource(deletador._explicar_o_zero)
    assert "vision.crop" in fonte
    assert "regioes" in fonte


def test_o_diagnostico_diz_o_LIMIAR_junto():
    """Um número solto não se interpreta: 0,87 é longe ou perto?"""
    fonte = inspect.getsource(deletador._explicar_o_zero)
    assert "LIMIAR_EM_COR" in fonte
