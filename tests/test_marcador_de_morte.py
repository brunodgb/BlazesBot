"""`alvo_morto_na_tela`: procura SÓ no quadro do alvo, e ausência não é resposta.

=============================================================================
O QUE ESTÁ SOB TESTE
=============================================================================

`EnemyDead.png` é o marcador de inimigo morto, e ele é a CONFIRMAÇÃO FINAL da
morte do alvo -- consultado quando o veredito normal do `VigiaDoAlvo` sai
inconclusivo. A lógica do veredito é testada em `test_combat_vigia_do_alvo.py`;
aqui se testa a LEITURA.

=============================================================================
O TESTE QUE CARREGA O PESO
=============================================================================

`test_nao_procura_no_quadro_do_PROPRIO_personagem`.

O quadro do próprio personagem fica no canto superior ESQUERDO e é IGUAL ao do
alvo -- o `vision.py` já registra isso no comentário do
`FAIXA_DO_QUADRO_DE_ALVO`, e é por isso que a busca da barra de vida é
restringida. O mesmo vale aqui, e a consequência é pior: **"eu morri" lido como
"o mob morreu"** faria o bot apertar TAB enquanto o personagem está no chão.
"""
import numpy as np
import pytest

from blazesbot.core import vision

LARGURA, ALTURA = 1024, 768


def _marcador():
    """Um retalho reconhecível, com contraste -- template liso casa em todo lugar."""
    m = np.zeros((22, 26), dtype=np.uint8)
    m[2:20, 2:24] = 200
    m[8:14, 8:18] = 40
    return m


def _quadro_com(marcador, em):
    """Quadro de fundo uniforme com o marcador colado em `em` = (x, y)."""
    quadro = np.full((ALTURA, LARGURA, 3), 30, dtype=np.uint8)
    x, y = em
    altura, largura = marcador.shape
    quadro[y:y + altura, x:x + largura] = marcador[:, :, None]
    return quadro


def _no_quadro_do_alvo():
    """Um ponto dentro da faixa onde o quadro do alvo é desenhado."""
    x0, y0, x1, y1 = vision._regiao_quadro_alvo(LARGURA, ALTURA)
    return (x0 + 20, y0 + 40)


# ---------------------------------------------------------------------------
# 1. Acha onde deve
# ---------------------------------------------------------------------------

def test_acha_o_marcador_no_quadro_do_alvo():
    marcador = _marcador()
    quadro = _quadro_com(marcador, _no_quadro_do_alvo())

    assert vision.alvo_morto_na_tela(quadro, marcador) is True


def test_nao_acha_quando_o_marcador_nao_esta_na_tela():
    marcador = _marcador()
    quadro = np.full((ALTURA, LARGURA, 3), 30, dtype=np.uint8)

    assert vision.alvo_morto_na_tela(quadro, marcador) is False


# ---------------------------------------------------------------------------
# 2. O TESTE QUE CARREGA O PESO
# ---------------------------------------------------------------------------

def test_nao_procura_no_quadro_do_PROPRIO_personagem():
    """O quadro do personagem é IGUAL ao do alvo e fica no canto ESQUERDO.

    Se a busca varresse a tela inteira, o marcador desenhado ali seria lido como
    "o mob morreu" -- e o bot apertaria TAB com o personagem no chão.
    """
    marcador = _marcador()
    quadro = _quadro_com(marcador, (10, 40))       # canto superior esquerdo

    assert vision.alvo_morto_na_tela(quadro, marcador) is False, (
        "achou o marcador no quadro do PRÓPRIO personagem -- 'eu morri' viraria "
        "'o mob morreu'"
    )


def test_nao_procura_embaixo_da_tela():
    """A barra de atalhos e a janela de loot também têm ícones pequenos."""
    marcador = _marcador()
    quadro = _quadro_com(marcador, (500, ALTURA - 60))

    assert vision.alvo_morto_na_tela(quadro, marcador) is False


# ---------------------------------------------------------------------------
# 3. "Não sei" é `None`, e nunca é confundido com resposta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quadro, template", [
    (None, _marcador()),
    (np.zeros((0, 0, 3), dtype=np.uint8), _marcador()),
    (np.full((ALTURA, LARGURA, 3), 30, dtype=np.uint8), None),
    (None, None),
])
def test_sem_o_que_olhar_devolve_None(quadro, template):
    """`None` e `False` são coisas diferentes, e o consumidor age só no `True`.

    Sem quadro ou sem template não houve leitura -- devolver `False` diria "o
    marcador não está lá", que é uma afirmação que não se pode fazer.
    """
    assert vision.alvo_morto_na_tela(quadro, template) is None


def test_o_limiar_erra_para_MAIS():
    """Falso positivo declara morte e gasta um TAB; falso negativo só devolve o
    comportamento de hoje. Então o limiar é alto."""
    assert vision.LIMIAR_DO_MARCADOR_DE_MORTE >= 0.80


# ---------------------------------------------------------------------------
# 4. O template de verdade, se estiver em disco
# ---------------------------------------------------------------------------

def test_o_template_do_usuario_existe_e_tem_contraste():
    """Template liso casaria em qualquer lugar da faixa."""
    import cv2

    from blazesbot.bot.combate import TEMPLATE_INIMIGO_MORTO
    from blazesbot.core.vision import TemplateLibrary

    template = TemplateLibrary("data/templates").load(TEMPLATE_INIMIGO_MORTO)
    if template is None:
        pytest.skip(f"{TEMPLATE_INIMIGO_MORTO} não está em data/templates")

    assert float(template.std()) > 10.0, (
        "o marcador é quase liso; ele casaria em qualquer fundo uniforme"
    )

    # ================================================================
    # O TETO DE LARGURA SAIU, E FOI A MEDIÇÃO QUE O TIROU
    # ================================================================
    #
    # Este teste exigia `< 60` nas duas dimensões, porque o primeiro template era
    # um sprite de 26x22 e eu tratei aquele tamanho como se fosse a natureza do
    # marcador. Era só o recorte que existia.
    #
    # Em 19/08/2026 o usuário trocou o arquivo por um de **128x22**, e a produção
    # respondeu melhor em tudo:
    #
    #     escores em produção   0,955 a 0,971   (contra 0 casamentos em 69 leituras)
    #     custo do casamento    1,06 ms         (o de 26x22 custava 1,23 ms)
    #
    # Mais barato apesar de 5x a área, porque o `matchTemplate` troca para DFT em
    # modelo grande. Ou seja: o teto que eu escrevi reprovaria o template que
    # FUNCIONA.
    #
    # O que continua valendo é a ALTURA -- o marcador vive na faixa do quadro do
    # alvo, e um recorte mais alto que a faixa nunca casaria.
    altura, largura = template.shape[:2]
    x0, y0, x1, y1 = vision._regiao_quadro_alvo(LARGURA, ALTURA)
    assert altura <= y1 - y0, (
        f"o marcador tem {altura}px de altura e a faixa do quadro do alvo tem "
        f"{y1 - y0}px -- ele nunca casaria"
    )
    assert largura <= 409, (
        "o marcador é mais largo que a faixa de busca (30% a 70% de 1024px)"
    )
    del cv2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
