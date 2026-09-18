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

**ELE MUDOU DE FORMA em 11/09/2026.** Rodava só quando a passada apagava ZERO --
e isso deixava invisível o caso mais comum: um modelo que nunca casa enquanto os
outros casam. O relato foi sobre o `Trap-Meshwork`, que nunca apagou nenhuma vez
enquanto treze irmãos apagavam. Agora o relatório sai em TODA passada, e de
graça: o valor vem do `matchTemplate` que já rodava.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import numpy as np

from blazesbot.bot import afericao_do_lixo, deletador
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


def test_o_relatorio_roda_em_TODA_passada():
    """Era só quando a passada apagava ZERO -- e isso deixava invisível o caso
    do usuário em 11/09/2026: o `Trap-Meshwork` nunca apagava, mas os outros
    apagavam, então a passada nunca dava zero e o diagnóstico nunca rodava.
    """
    fonte = inspect.getsource(deletador.deletar_lixo)

    assert "_quem_nao_casou(" in fonte
    assert "if apagados == 0:" not in fonte, (
        "o relatório voltou a depender de a passada não apagar nada")


def test_o_relatorio_NAO_paga_uma_segunda_varredura():
    """O valor vem do `matchTemplate` que já rodava, por `placar`.

    A primeira versão (09/09/2026) refazia o casamento de cada modelo só para
    medir. Custava ~90 ms por passada e, pior, media DEPOIS -- com a bolsa já
    diferente daquela em que a decisão foi tomada.
    """
    fonte = inspect.getsource(deletador)

    assert "melhor_casamento" not in fonte, (
        "o deletador voltou a refazer o casamento só para medir")
    assert "placar=pontuacoes" in fonte


def test_o_placar_vem_do_matchTemplate_que_ja_rodava():
    from blazesbot.core.vision import find_all_templates

    # PELO AST: a docstring da função cita `matchTemplate` para explicar de
    # onde o número vem, e contar no texto acharia a explicação também.
    arvore = ast.parse(textwrap.dedent(inspect.getsource(find_all_templates)))
    casamentos = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                  and ast.unparse(n.func) == "cv2.matchTemplate"]
    placares = [n.lineno for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and ast.unparse(n.func) == "placar.append"]

    assert len(casamentos) == 1, (
        f"{len(casamentos)} matchTemplate -- o placar deixou de ser de graça")
    assert placares and casamentos[0].lineno < placares[0], (
        "o placar deixou de ser lido do resultado que já existia")


def test_o_relatorio_NAO_derruba_a_run():
    """Falhar num diagnóstico não pode custar a run."""
    fonte = inspect.getsource(deletador._quem_nao_casou)

    assert "if not placar:" in fonte, (
        "sem placar o relatório tem que sair calado, não estourar")


def test_o_relatorio_diz_o_LIMIAR_e_como_LER_o_numero():
    """Um número solto não se interpreta: 0,87 é longe ou perto?

    E as duas faixas pedem correções OPOSTAS -- recortar de novo o PNG, ou não
    mexer em nada porque o item simplesmente não está na tela.
    """
    fonte = inspect.getsource(deletador._quem_nao_casou)

    assert "LIMIAR_EM_COR" in fonte
    assert "0,80" in fonte and "0,60" in fonte, (
        "o relatório deixou de dizer como interpretar o número")


def test_o_log_das_BOLSAS_VISIVEIS_existe():
    """Bolsa extra FECHADA não tem etiqueta na tela e não entra na varredura.

    Sem esta linha, esse estado -- o mais provável no relato do usuário -- é
    indistinguível de "não tem lixo".
    """
    fonte = inspect.getsource(deletador.deletar_lixo)
    assert "Bolsas visíveis para a limpeza" in fonte


# ===========================================================================
# O limiar, e o vão que o justifica
# ===========================================================================
#
# Remedido em 11/09/2026 com 3456 pontuações de não-casamento do log de
# produção. Ver `docs/decisoes/deletador.md`, "O limiar em cor, REMEDIDO".

# O maior distrator medido em TODO o conjunto de lixo (`Biddha-Bone`).
MAIOR_DISTRATOR_MEDIDO = 0.70

# O casamento verdadeiro que o limiar antigo rejeitava (`Trap-Meshwork`, em 48
# relatórios seguidos, sempre o mesmo valor).
VERDADEIRO_QUE_FALHAVA = 0.90


def test_o_limiar_fica_DENTRO_do_vao_medido():
    """0,71 a 0,89 está vazio: nenhuma das 3456 amostras cai ali.

    Abaixo do maior distrator, o bot apagaria item que não é lixo -- e apagar é
    irreversível. Acima do verdadeiro, volta o defeito que o usuário relatou:
    o item na bolsa e o bot nunca o apagando.
    """
    assert MAIOR_DISTRATOR_MEDIDO < deletador.LIMIAR_EM_COR, (
        f"o limiar {deletador.LIMIAR_EM_COR} está ABAIXO do maior distrator "
        f"medido ({MAIOR_DISTRATOR_MEDIDO}) -- o bot passa a apagar o que não "
        f"é lixo")
    assert deletador.LIMIAR_EM_COR < VERDADEIRO_QUE_FALHAVA, (
        f"o limiar {deletador.LIMIAR_EM_COR} está ACIMA do casamento "
        f"verdadeiro medido ({VERDADEIRO_QUE_FALHAVA}) -- volta o defeito de "
        f"11/09/2026, com o item na bolsa e o bot nunca apagando")


def test_a_margem_para_o_distrator_e_maior_que_para_o_verdadeiro():
    """O erro barato é não apagar; o caro é apagar o que não devia.

    Por isso a folga para baixo (contra falso positivo) tem de ser a maior das
    duas -- e é: 0,15 contra 0,05.
    """
    folga_abaixo = deletador.LIMIAR_EM_COR - MAIOR_DISTRATOR_MEDIDO
    folga_acima = VERDADEIRO_QUE_FALHAVA - deletador.LIMIAR_EM_COR

    assert folga_abaixo > folga_acima, (
        f"a folga contra falso positivo ({folga_abaixo:.2f}) ficou menor que a "
        f"folga contra falso negativo ({folga_acima:.2f}) -- e apagar é "
        f"irreversível")


def test_a_conferencia_sem_apagar_continua_existindo():
    """A única proteção que não depende de palpite.

    MUDOU DE CASA em 18/09/2026, não de existência: o `deletador.py` bateu em
    799 linhas de um teto de 800, e a aferição — que só desenha — saiu inteira
    para `bot/afericao_do_lixo.py`. O que este teste protege é ela EXISTIR.
    """
    assert callable(afericao_do_lixo.conferir)
