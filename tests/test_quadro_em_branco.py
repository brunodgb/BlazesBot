"""`frame_is_blank`: o mesmo veredito, sem alocar 18 MB por chamada.

=============================================================================
A QUEDA DE 20/08/2026
=============================================================================

O bot morreu de madrugada, e o log guardou a frase exata:

    Erro inesperado na sessão: Unable to allocate 18.0 MiB for an array with
    shape (768, 1024, 3) and data type float64

seguida, no terminal, de:

    OpenBLAS error: Memory allocation still failed after 10 retries, giving up.

`np.std` sobre `uint8` aloca um temporário **float64 do tamanho do array**. Num
quadro de 768x1024x3 isso é 18 MB -- por chamada, e `frame_is_blank` é chamado a
CADA captura.

Ficou visível quando a calibração multiplicou por ~10 a frequência de captura:
cinco contas x ~2 capturas/s x 18 MB é ~180 MB/s de rotatividade em blocos
grandes, e o heap deixa de ter bloco contíguo para entregar.

=============================================================================
POR QUE AMOSTRAR RESOLVE SEM PERDER NADA
=============================================================================

A pergunta é "este quadro está preto?", não "qual é o desvio exato". Medido em
quadros reais:

    quadro real 1     std completo 46,67   amostrado 45,41
    quadro real 2     std completo 53,42   amostrado 53,42
    quadro real 3     std completo 35,84   amostrado 36,21
    preto puro                     0,00              0,00

Os dois lados do limiar de 3,0 continuam do mesmo lado, com folga enorme. E o
ganho é duplo: **52x menos memória e 65x mais rápido** (8-10 ms -> 0,13 ms).

Os 8-10 ms eram pagos a cada captura, em toda conta -- ou seja, este "teste
barato" custava mais que o casamento de template que ele existe para proteger.
"""
import tracemalloc

import numpy as np
import pytest

from blazesbot.core import vision

ALTURA, LARGURA = 768, 1024


def _quadro(valor=None):
    if valor is None:      # cena, com variação de verdade
        return np.random.RandomState(3).randint(
            0, 255, (ALTURA, LARGURA, 3), dtype=np.uint8)
    return np.full((ALTURA, LARGURA, 3), valor, np.uint8)


# ---------------------------------------------------------------------------
# 1. O VEREDITO NÃO MUDOU
# ---------------------------------------------------------------------------

def test_preto_e_branco():
    assert vision.frame_is_blank(_quadro(0)) is True


def test_uniforme_de_qualquer_cor_e_branco():
    """Não é só preto: `PrintWindow` devolve sucesso com quadro uniforme, e
    qualquer cor chapada é igualmente inútil."""
    for valor in (0, 7, 128, 255):
        assert vision.frame_is_blank(_quadro(valor)) is True, valor


def test_cena_de_verdade_NAO_e_branco():
    assert vision.frame_is_blank(_quadro()) is False


def test_nada_e_branco():
    assert vision.frame_is_blank(None) is True
    assert vision.frame_is_blank(np.zeros((0, 0, 3), np.uint8)) is True


def test_quadro_pequeno_ainda_funciona():
    """A amostragem de 8 em 8 num quadro de 20 px deixa 3 px por eixo -- pouco,
    mas ainda decide. Um `frame_is_blank` que devolvesse lixo em quadro pequeno
    quebraria o recorte de templates, que trabalha em regiões minúsculas."""
    assert vision.frame_is_blank(np.zeros((20, 20, 3), np.uint8)) is True
    ruido = np.random.RandomState(1).randint(0, 255, (20, 20, 3), dtype=np.uint8)
    assert vision.frame_is_blank(ruido) is False


# ---------------------------------------------------------------------------
# 2. O CONSERTO -- e é ele que impede a queda voltar
# ---------------------------------------------------------------------------

def test_NAO_aloca_o_quadro_inteiro_em_float64():
    """O teste que carrega o peso.

    Um `frame.std()` direto alocaria ~18 MB. O teto aqui é 2 MB: passa folgado
    com a amostragem e reprova na hora se alguém voltar ao `std()` do quadro
    inteiro -- inclusive por "simplificação".
    """
    quadro = _quadro()
    vision.frame_is_blank(quadro)          # aquece, para não medir import

    tracemalloc.start()
    tracemalloc.reset_peak()
    vision.frame_is_blank(quadro)
    _atual, pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert pico < 2_000_000, (
        f"frame_is_blank alocou {pico / 1e6:.1f} MB; o quadro inteiro em float64 "
        f"são ~18 MB, e foi isso que derrubou o bot em 20/08/2026"
    )


def test_o_passo_da_amostragem_e_sano():
    """Passo 1 é o comportamento antigo (18 MB) disfarçado de constante."""
    assert vision.PASSO_DA_AMOSTRAGEM_DO_QUADRO >= 2
    assert vision.PASSO_DA_AMOSTRAGEM_DO_QUADRO <= 16


def test_e_MAIS_RAPIDO_que_o_quadro_inteiro():
    """8-10 ms por captura, em cinco contas, a duas capturas por segundo: o teste
    de "está preto?" custava mais que o casamento de template que ele protege."""
    import time
    quadro = _quadro()

    ini = time.perf_counter()
    for _ in range(10):
        vision.frame_is_blank(quadro)
    amostrado = time.perf_counter() - ini

    ini = time.perf_counter()
    for _ in range(10):
        float(quadro.std())
    inteiro = time.perf_counter() - ini

    assert amostrado < inteiro / 5, (
        f"amostrado {amostrado * 100:.2f} ms/chamada contra "
        f"{inteiro * 100:.2f} ms do quadro inteiro -- a economia sumiu"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
