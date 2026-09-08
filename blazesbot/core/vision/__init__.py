"""
Visão computacional: captura da janela do cliente e template matching.

Usada apenas onde a memória não alcança -- basicamente elementos de UI que
não têm flag mapeada (fila de login, ícone de fase do boss, botões).

A captura usa PrintWindow com PW_RENDERFULLCONTENT, que funciona com janela
em background e, na maioria dos casos, minimizada. Se voltar quadro preto,
o cliente precisa estar visível (ver README).

================================================================
POR QUE ESTE ARQUIVO É UM PACOTE
================================================================

Antes era um `core/vision.py` de 1548 linhas com 4 subdomínios (captura,
templates, marcadores, barra). A quebra aconteceu em 04/09/2026 com o
prompt 09 do toolkit, e a regra de cada subdomínio ficou explícita:

  * `core/vision/captura.py`     -- PrintWindow, GdiPool, frame_is_blank
  * `core/vision/templates.py`   -- TemplateLibrary, find_template, realce
  * `core/vision/marcadores.py`  -- marcador de morte, fase 2 do boss
  * `core/vision/barra.py`       -- leitura da barra de HP do alvo

Os 33 importadores do antigo `vision.py` (`from blazesbot.core import vision`
e `from blazesbot.core.vision import X`) continuam funcionando sem mexer em
uma linha, porque o `__init__.py` abaixo re-exporta os mesmos símbolos.

A escolha de quebrar por SUBMÓDULO e não por responsabilidade-classe foi
proposital: o arquivo era uma coleção de utilidades, não uma classe monolítica
de DI. Cada subdomínio tem sua própria natureza e roda junto -- um caller que
usa `find_template` provavelmente também usa `capture_window`, e separá-los
em submódulos só para ficarem "isolados" seria separar por cerimônia, não
por uso.
"""
from blazesbot.core.vision.barra import (
    BARRA_DO_ALVO_X0,
    BARRA_DO_ALVO_X1,
    BARRA_DO_ALVO_Y0,
    BARRA_DO_ALVO_Y1,
    MINIMO_RECONHECIDO_NA_FAIXA,
    USAR_OFFSET_FIXO_DA_BARRA,
    LeituraDaBarra,
    _barra_vermelha_e_hp_valida,  # noqa: F401  re-export: tests/test_marcador_de_morte
    _classificar_colunas,  # noqa: F401  re-export: tests/test_fase_2_pela_tela
    _vida_por_ancora_azul,  # noqa: F401  re-export: reserva do vida_do_alvo
    ler_barra_do_alvo,
    vida_do_alvo,
)
from blazesbot.core.vision.captura import (
    PASSO_DA_AMOSTRAGEM_DO_QUADRO,
    PW_RENDERFULLCONTENT,
    GdiPool,
    _capture_with_pool,  # noqa: F401  re-export: tests testam o pool
    _raw_capture,  # noqa: F401  re-export: tests testam o fallback
    capture_available,
    capture_window,
    client_offset,
    frame_is_blank,
    get_pool,
    release_pool,
)
from blazesbot.core.vision.marcadores import (
    ALTURA_DA_BARRA,
    LARGURA_MINIMA_DA_BARRA,
    LIMIAR_DA_FASE_2_DO_BOSS,
    LIMIAR_DO_MARCADOR_DE_MORTE,
    LINHAS_ENTRE_HP_E_MP,
    _corrida_mais_longa,  # noqa: F401  re-export: tests/test_fase_2_pela_tela
    _regiao_quadro_alvo,  # noqa: F401  re-export: tests/test_marcador_de_morte
    alvo_morto_na_tela,
    boss_na_segunda_fase,
    marcador_de_morte,
    marcador_de_morte_em_cor,
)
from blazesbot.core.vision.templates import (
    DEFAULT_THRESHOLD,
    HIGHLIGHT_BGR,
    LearnedCrops,
    TemplateLibrary,
    crop,
    find_all_templates,
    find_highlighted_row,
    find_template,
    highlight_ratio,
    melhor_casamento,
    region_is_uniform,
    template_present,
)

__all__ = [
    "ALTURA_DA_BARRA",
    "BARRA_DO_ALVO_X0",
    "BARRA_DO_ALVO_X1",
    "BARRA_DO_ALVO_Y0",
    "BARRA_DO_ALVO_Y1",
    "DEFAULT_THRESHOLD",
    "HIGHLIGHT_BGR",
    "LARGURA_MINIMA_DA_BARRA",
    "LIMIAR_DA_FASE_2_DO_BOSS",
    "LIMIAR_DO_MARCADOR_DE_MORTE",
    "LINHAS_ENTRE_HP_E_MP",
    "MINIMO_RECONHECIDO_NA_FAIXA",
    "PASSO_DA_AMOSTRAGEM_DO_QUADRO",
    "PW_RENDERFULLCONTENT",
    "USAR_OFFSET_FIXO_DA_BARRA",
    "GdiPool",
    "LearnedCrops",
    "LeituraDaBarra",
    "TemplateLibrary",
    "alvo_morto_na_tela",
    "boss_na_segunda_fase",
    "capture_available",
    "capture_window",
    "client_offset",
    "crop",
    "find_all_templates",
    "find_highlighted_row",
    "find_template",
    "frame_is_blank",
    "get_pool",
    "highlight_ratio",
    "ler_barra_do_alvo",
    "marcador_de_morte",
    "marcador_de_morte_em_cor",
    "melhor_casamento",
    "region_is_uniform",
    "release_pool",
    "template_present",
    "vida_do_alvo",
]
