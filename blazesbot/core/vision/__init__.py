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
from blazesbot.core.vision.captura import (
    PASSO_DA_AMOSTRAGEM_DO_QUADRO,
    PW_RENDERFULLCONTENT,
    GdiPool,
    _capture_with_pool,
    _raw_capture,
    capture_available,
    capture_window,
    client_offset,
    frame_is_blank,
    get_pool,
    release_pool,
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
    region_is_uniform,
    template_present,
)
from blazesbot.core.vision.marcadores import (
    ALTURA_DA_BARRA,
    LARGURA_MINIMA_DA_BARRA,
    LIMIAR_DA_FASE_2_DO_BOSS,
    LIMIAR_DO_MARCADOR_DE_MORTE,
    LINHAS_ENTRE_HP_E_MP,
    _corrida_mais_longa,
    _regiao_quadro_alvo,
    alvo_morto_na_tela,
    boss_na_segunda_fase,
    marcador_de_morte,
    marcador_de_morte_em_cor,
)
from blazesbot.core.vision.barra import (
    BARRA_DO_ALVO_X0,
    BARRA_DO_ALVO_X1,
    BARRA_DO_ALVO_Y0,
    BARRA_DO_ALVO_Y1,
    LeituraDaBarra,
    MINIMO_RECONHECIDO_NA_FAIXA,
    USAR_OFFSET_FIXO_DA_BARRA,
    _barra_vermelha_e_hp_valida,
    _classificar_colunas,
    _vida_por_ancora_azul,
    ler_barra_do_alvo,
    vida_do_alvo,
)

__all__ = [
    # captura
    "PASSO_DA_AMOSTRAGEM_DO_QUADRO",
    "PW_RENDERFULLCONTENT",
    "GdiPool",
    "capture_window",
    "capture_available",
    "frame_is_blank",
    "client_offset",
    "get_pool",
    "release_pool",
    # templates
    "DEFAULT_THRESHOLD",
    "HIGHLIGHT_BGR",
    "TemplateLibrary",
    "LearnedCrops",
    "crop",
    "region_is_uniform",
    "find_template",
    "find_all_templates",
    "highlight_ratio",
    "find_highlighted_row",
    "template_present",
    # marcadores
    "LARGURA_MINIMA_DA_BARRA",
    "LINHAS_ENTRE_HP_E_MP",
    "ALTURA_DA_BARRA",
    "LIMIAR_DO_MARCADOR_DE_MORTE",
    "LIMIAR_DA_FASE_2_DO_BOSS",
    "alvo_morto_na_tela",
    "marcador_de_morte",
    "marcador_de_morte_em_cor",
    "boss_na_segunda_fase",
    # barra
    "BARRA_DO_ALVO_X0",
    "BARRA_DO_ALVO_X1",
    "BARRA_DO_ALVO_Y0",
    "BARRA_DO_ALVO_Y1",
    "MINIMO_RECONHECIDO_NA_FAIXA",
    "USAR_OFFSET_FIXO_DA_BARRA",
    "LeituraDaBarra",
    "ler_barra_do_alvo",
    "vida_do_alvo",
]
