"""A venda: velocidade, e a parada quando o slot fica vazio.

O que estes testes protegem:

  1. O SLOT VAZIO ENCERRA A VENDA — mas só com `LEITURAS_VAZIAS_PARA_PARAR`
     leituras SEGUIDAS. Uma só produziria parada falsa: logo depois do clique
     os itens estão SUBINDO, e um quadro pego aí mostra o slot vazio sem ele
     estar.
  2. A CAIXA "It's precious item" é conferida a CADA clique. Com ela aberta os
     itens param de subir e a passada inteira vende zero.
  3. Parar cedo ainda CLICA EM SELL: o que já subiu tem que virar dinheiro.
"""
import inspect

import pytest

from blazesbot.bot import vendedor as janela_de_venda
from blazesbot.bot.bc import vendor as v

# Onde está a grade da janela de venda na foto de referência: slot1 em
# (452,292), célula 34x35, 6 colunas x 4 linhas. A lista de venda (vazia) fica
# 213 px abaixo, na mesma coluna.
FOTO = ("logs/diagnostico-do-link/"
        "104345.082-abrir-a-venda-do-rich-man-t+750.png")
SLOT1 = (452, 292)
CELULA = (34, 35)
LISTA_DE_VENDA_Y = 505


def _contraste(img, x, y):
    """O mesmo recorte que o `_nota_do_slot_vazio` faz."""
    import numpy as np
    meio = janela_de_venda.LADO_DO_MIOLO_DA_CELULA // 2
    return float(img[y - meio:y + meio, x - meio:x + meio]
                 .astype(np.float32).std())


def _celulas(img, y0):
    return [_contraste(img, SLOT1[0] + c * CELULA[0], y0 + l * CELULA[1])
            for l in range(4) for c in range(6)]


def test_o_corte_separa_cheio_de_vazio_na_grade_REAL():
    """A medição que autoriza o corte, refeita a cada rodada de teste.

    24 células CHEIAS e 24 VAZIAS da MESMA janela, na foto de uma venda real
    deste cliente. É esta separação que o casamento de modelo não tinha: em
    produção ele deu 0.503 no cheio e 0.708 no vazio, com o limiar em 0.70.
    """
    from pathlib import Path

    import cv2

    if not Path(FOTO).is_file():
        pytest.skip("foto de referência não está no repo")
    img = cv2.imread(FOTO, cv2.IMREAD_GRAYSCALE)

    cheios = _celulas(img, SLOT1[1])
    vazios = _celulas(img, LISTA_DE_VENDA_Y)

    assert min(cheios) > janela_de_venda.CONTRASTE_QUE_E_SLOT_VAZIO, (
        f"uma célula COM item mediu {min(cheios):.1f}, abaixo do corte "
        f"{janela_de_venda.CONTRASTE_QUE_E_SLOT_VAZIO} — a venda pararia cedo")
    assert max(vazios) < janela_de_venda.CONTRASTE_QUE_E_SLOT_VAZIO, (
        f"uma célula VAZIA mediu {max(vazios):.1f}, acima do corte — a venda "
        f"nunca pararia sozinha")
    assert min(cheios) - max(vazios) > 25, (
        f"vão de apenas {min(cheios) - max(vazios):.1f}: margem estreita é "
        f"exatamente o defeito que o casamento de modelo tinha")


def test_a_BORDA_DE_HOVER_nao_entra_no_miolo():
    """O motivo de o miolo ser 24 e não a célula inteira.

    O slot que o bot confere está SEMPRE com a borda amarela de hover, e foi
    ela que dominou o casamento de modelo. O modelo `state_slot_vazio_hover`
    é um slot VAZIO com a borda: medido no miolo de 24 ele dá 9.76 (vazio,
    certo), e no de 28 salta para 57.80 — que é a borda entrando e passando
    por item.
    """
    from pathlib import Path

    import cv2
    import numpy as np

    arq = Path("data") / "templates" / "state_slot_vazio_hover.png"
    if not arq.is_file():
        pytest.skip("modelo de referência não está no repo")
    t = cv2.imread(str(arq), cv2.IMREAD_GRAYSCALE)
    cy, cx = t.shape[0] // 2, t.shape[1] // 2
    meio = janela_de_venda.LADO_DO_MIOLO_DA_CELULA // 2
    com_hover = float(t[cy - meio:cy + meio, cx - meio:cx + meio]
                      .astype(np.float32).std())
    assert com_hover < janela_de_venda.CONTRASTE_QUE_E_SLOT_VAZIO, (
        f"o slot vazio COM hover mediu {com_hover:.1f} e passaria por cheio — "
        f"a borda voltou a entrar no recorte")

    largo = min(t.shape) // 2
    if largo > meio + 1:
        borda = float(t[cy - largo:cy + largo, cx - largo:cx + largo]
                      .astype(np.float32).std())
        assert borda > com_hover * 2, (
            "a borda deixou de importar; se for verdade, o miolo pode crescer "
            "— mas isso precisa ser MEDIDO, não presumido")


def test_tres_leituras_e_nao_uma_nem_duas():
    """A leitura sai ~30 ms depois do clique, com os itens ainda subindo.

    Uma só encerraria a venda no meio do rearranjo. SÃO SEIS — mas o número
    sozinho NÃO resolve: medido em produção (14/08/2026, 22 dos 66 cliques com
    a grade cheia), seis leituras espaçadas caem em múltiplos vãos de rearranjo.
    O que separa uma coisa da outra é o ESPAÇAMENTO entre elas, provado em
    `test_venda_rearranjo.py`. Valor alterado para 6 em 21/08/2026.
    """
    assert janela_de_venda.LEITURAS_VAZIAS_PARA_PARAR == 6


def test_a_conferencia_e_no_slot_CLICADO_e_nao_na_tela_toda():
    """A grade tem outros slots vazios (os de baixo, que nunca tiveram item).

    Procurar na janela inteira acharia qualquer um deles e encerraria a venda
    com item ainda no slot que interessa. O recorte é em volta do ponto de
    clique — e o ponto é o mesmo que o `ctx.click` recebe.
    """
    import inspect

    # O RECORTE MORA EM `_miolo_do_slot` desde 25/09/2026: um recorte serve às
    # duas leituras (o vazio e a medição da rolha). A nota tem de passar por ele.
    nota = inspect.getsource(v.VendorService._nota_do_slot_vazio)
    assert "self._miolo_do_slot(quadro, ponto)" in nota, (
        "a nota deixou de usar o recorte centrado no ponto clicado")
    fonte = inspect.getsource(v.VendorService._miolo_do_slot)
    assert "crop(" in fonte, "deixou de recortar: passaria a olhar a tela toda"
    assert "ponto[0]" in fonte and "ponto[1]" in fonte, (
        "o recorte deixou de ser centrado no ponto de clique")

    clique = inspect.getsource(v.VendorService._clicar_no_slot)
    assert "ctx.click(alvo)" in clique
    assert "_nota_do_slot_vazio(self._quadro(), alvo)" in clique, (
        "o ponto conferido deixou de ser o MESMO que foi clicado")


def test_a_espera_entre_cliques_encolheu_mas_nao_zerou():
    """Zero arriscaria clicar durante o rearranjo; 200 ms era o gargalo."""
    assert 0 < janela_de_venda.ESPERA_ENTRE_CLIQUES_DA_VENDA <= 0.1


def test_os_modelos_de_slot_vazio_sairam_da_DECISAO():
    """Os dois PNGs continuam no repo; o que saiu foi o casamento deles.

    Medido em produção (12:11 de 14/08/2026): slot CHEIO 0.503, slot vazio
    0.708, limiar 0.70 — margem de 0.008. A borda de hover existe nos dois
    estados e dominava o recorte, então o casamento media a borda, não o
    conteúdo. Quem decide agora é o contraste do miolo, onde a borda não entra.
    """
    assert not hasattr(v, "LIMIAR_DO_SLOT_VAZIO"), (
        "o limiar de casamento voltou — ele foi medido como ruído")
    assert not hasattr(v, "TEMPLATES_DE_SLOT_VAZIO"), (
        "o casamento por modelo voltou à decisão")
    fonte = inspect.getsource(v.VendorService._nota_do_slot_vazio)
    assert "matchTemplate" not in fonte, (
        "a decisão voltou a casar modelo no slot")


def test_o_que_saiu_saiu_de_verdade():
    """Os quatro mecanismos indiretos foram removidos, não desligados.

    Eles respondiam por tentativa e erro a pergunta que o slot vazio agora
    responde direto. Deixá-los seria pagar duas vezes pela mesma informação —
    e `TENTATIVAS_POR_SLOT` era o que fazia cada clique custar até três.
    """
    for nome in ("TENTATIVAS_POR_SLOT", "TETO_DE_CLIQUES_FISICOS",
                 "MUDANCA_MINIMA_NO_SLOT", "LADO_DA_AMOSTRA_DO_SLOT"):
        assert not hasattr(v, nome), f"{nome} voltou"


def test_o_servico_nao_guarda_mais_cauda_vazia():
    assert "_cauda_vazia" not in v.VendorService.__init__.__code__.co_names
