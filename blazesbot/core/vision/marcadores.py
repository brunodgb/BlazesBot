"""
Marcadores de UI: marcador de morte e barra amarela da fase 2 do boss.

A faixa do quadro do alvo (topo central) vem daqui -- é a mesma geometria
usada por `alvo_morto_na_tela`, `marcador_de_morte` e `boss_na_segunda_fase`.
Quem precisar dela lê `_regiao_quadro_alvo(largura, altura)`.

`LARGURA_MINIMA_DA_BARRA`, `LINHAS_ENTRE_HP_E_MP`, `ALTURA_DA_BARRA` e os
dois `LIMIAR_*` são as constantes de medição -- não são ajuste fino, são
o que torna o casamento confiável ou falso. Mexer nelas é mexer no bot.
"""
from __future__ import annotations

import cv2
import numpy as np

from blazesbot.core import coords as coords_mod
from blazesbot.core.vision.templates import find_all_templates

# ===========================================================================
# QUADRO DO ALVO -- quanta vida o mob selecionado ainda tem, lido da TELA.
#
# POR QUE PELA TELA E NÃO PELA MEMÓRIA: o ponteiro de alvo mostrou-se
# instável nos testes do usuário -- "acabava bugando e não matava os mobs que
# deveria" --, e foi por isso que a fase dos guardas foi reescrita sem ele. A
# tela é a fonte que não bugou. A âncora sai da própria medição: a barra AZUL de
# mana do alvo tem largura constante (137 px) e está presente com o mob VIVO e
# MORTO; é a vermelha que esvazia. Achar a corrida azul localiza o quadro
# sozinha, sem template e sem coordenada à mão. Detalhe e medições em
# `docs/decisoes/`.
# ===========================================================================

# Largura mínima da corrida azul para ela ser a barra de mana do alvo. Não é a
# largura exata (137) porque a UI do jogo pode ter outra escala em resolução
# diferente; o que importa é ser uma faixa azul LONGA e contígua, e nada mais
# na parte de cima da tela é assim.
LARGURA_MINIMA_DA_BARRA = 100

# Distância da barra vermelha para a azul, em linhas, e altura da faixa.
LINHAS_ENTRE_HP_E_MP = 7
ALTURA_DA_BARRA = 8


def _regiao_quadro_alvo(largura: int, altura: int) -> tuple[int, int, int, int]:
    """Região (x0, y0, x1, y1) onde buscar o quadro do alvo, para a janela dada.

    Faixa horizontal 30%..70% da largura; vertical do topo até y=140 na base
    1024x768, ancorada em TOP_CENTER para escalar com a janela.
    """
    x0 = int(largura * 0.30)
    x1 = int(largura * 0.70)
    spot_y_max = coords_mod._from_base(0, 140, coords_mod.Anchor.TOP_CENTER)
    y1 = spot_y_max.at(largura, altura)[1]
    y0 = 0
    return x0, y0, x1, y1


def _corrida_mais_longa(linha: np.ndarray) -> tuple[int, int]:
    """Maior sequência contígua de True. Devolve (início, comprimento)."""
    melhor_i, melhor_n, i = 0, 0, 0
    n = len(linha)
    while i < n:
        if linha[i]:
            j = i
            while j < n and linha[j]:
                j += 1
            if j - i > melhor_n:
                melhor_i, melhor_n = i, j - i
            i = j
        else:
            i += 1
    return melhor_i, melhor_n


# Limiar do marcador de inimigo morto. Sprite pequeno (26x22) num quadro de UI,
# então é alto -- e errar para MAIS é o lado certo: falso positivo aqui declara
# morte e gasta um TAB, falso negativo só devolve o comportamento de hoje.
LIMIAR_DO_MARCADOR_DE_MORTE = 0.85


def alvo_morto_na_tela(
    frame: np.ndarray | None,
    template: np.ndarray | None,
) -> bool | None:
    """O marcador de "inimigo morto" está no quadro do alvo?

    `True` = está lá, CONFIRMAÇÃO de morte. `False` = não está, e isso **NÃO é
    confirmação de vida** -- é só ausência do marcador. `None` = não deu para
    olhar. Quem consome só pode agir no `True`; tratar `False` como "está vivo"
    reintroduziria o defeito que o `VigiaDoAlvo` existe para corrigir.

    PROCURA SÓ NA FAIXA DO QUADRO DO ALVO, a mesma que `vida_do_alvo` usa
    (topo do meio da tela). Varrer a tela inteira arriscaria confundir com o
    quadro do PRÓPRIO personagem (canto superior esquerdo, par HP+MP igual) --
    "eu morri" lido como "o mob morreu" é o pior desfecho possível.
    """
    if frame is None or frame.size == 0 or template is None:
        return None

    altura, largura = frame.shape[:2]
    x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
    regiao = (x0, y0, x1 - x0, y1 - y0)
    if regiao[2] <= 0 or regiao[3] <= 0:
        return None

    achou, _escore = marcador_de_morte(frame, template, regiao=regiao)
    return achou


def marcador_de_morte(
    frame: np.ndarray | None,
    template: np.ndarray | None,
    regiao: tuple[int, int, int, int] | None = None,
) -> tuple[bool | None, float | None]:
    """O mesmo que `alvo_morto_na_tela`, mas devolve o ESCORE junto.

    ==================================================================
    POR QUE O ESCORE PRECISA SAIR DAQUI
    ==================================================================

    Medido em produção em 19/08/2026: **69 leituras seguidas, nenhuma achou o
    marcador**, e o bot ficou 38 s batendo num cadáver sem dar TAB. Com só
    `True`/`False` na mão não há como saber QUAL das três coisas está errada:

      * o limiar (`LIMIAR_DO_MARCADOR_DE_MORTE`) está alto demais;
      * a faixa (`FAIXA_DO_QUADRO_DE_ALVO`) não contém o marcador;
      * ou o marcador simplesmente não está na tela nesse estado.

    Um `False` não distingue "casou 0,84 e faltou 0,01" de "casou 0,12". Então o
    escore vai para o LOG -- não para a decisão -- e a próxima run responde por
    medição. É o mesmo desenho do `loot_window_open()`: quem não decide, informa.

    `escore` é `None` só quando não deu para olhar.
    """
    if frame is None or frame.size == 0 or template is None:
        return None, None

    if regiao is None:
        altura, largura = frame.shape[:2]
        x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
        regiao = (x0, y0, x1 - x0, y1 - y0)

    rx, ry, rw, rh = regiao
    if rw <= 0 or rh <= 0:
        return None, None

    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)[ry:ry + rh, rx:rx + rw]
    if (cinza.shape[0] < template.shape[0]
            or cinza.shape[1] < template.shape[1]):
        return None, None

    escore = float(cv2.minMaxLoc(
        cv2.matchTemplate(cinza, template, cv2.TM_CCOEFF_NORMED))[1])
    return escore >= LIMIAR_DO_MARCADOR_DE_MORTE, escore


def marcador_de_morte_em_cor(
    frame: np.ndarray | None,
    template_colorido: np.ndarray | None,
    regiao: tuple[int, int, int, int] | None = None,
) -> tuple[float | None, float | None]:
    """O mesmo marcador, casado em COR, e a fração de VERMELHO onde ele casou.

    ==================================================================
    POR QUE EM COR, E POR QUE ISTO AINDA NÃO DECIDE
    ==================================================================

    Medido em 20/08/2026, com o bot dando três TAB em nove segundos num mob de
    35 de vida, fonte única `marcador de morte na tela`, escore **0,971**:

        EnemyDead.png    128 x 22
        em CINZA         min 2, max 98, média 39,7, desvio 23,3
                         a linha do meio é 27 chapado
        em COR           B 61,4   G 36,4   R 37,9      -- AZULADO
        vermelhos        161 de 2816 pixels = **5,7%**

    Uma barra VIVA a 35% tem ~35% de vermelho. Em cinza, com
    `TM_CCOEFF_NORMED` -- que normaliza brilho e contraste --, vermelho médio e
    cinza escuro ficam parecidos; **em cor não ficam.**

    É o MESMO defeito já medido no `boss_2_fase.png`: em cinza a fase 1 marcava
    0,874 e teria disparado a Break Soul no primeiro segundo; em cor caiu para
    0,792 contra 0,985 da fase 2, e o vão apareceu. Mesma classe, mesma cura.

    **DEVOLVE NÚMERO, NÃO VEREDITO**, e é decisão: o limiar em cor não está
    medido, e escolher um "no olho" é o que este projeto proíbe. Os dois valores
    vão para o LOG ao lado do escore em cinza; quando houver runs suficientes, o
    vão entre morto e vivo aparece e aí o limiar entra com medição atrás.

    A fração de vermelho é calculada com o MESMO teste de `vida_do_alvo` -- um
    número lido por dois lados mora num lugar só.
    """
    if frame is None or frame.size == 0 or template_colorido is None:
        return None, None
    if template_colorido.ndim != 3:
        return None, None

    if regiao is None:
        altura, largura = frame.shape[:2]
        x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
        regiao = (x0, y0, x1 - x0, y1 - y0)

    rx, ry, rw, rh = regiao
    if rw <= 0 or rh <= 0:
        return None, None

    zona = frame[ry:ry + rh, rx:rx + rw]
    th, tw = template_colorido.shape[:2]
    if zona.shape[0] < th or zona.shape[1] < tw:
        return None, None

    mapa = cv2.matchTemplate(zona, template_colorido, cv2.TM_CCOEFF_NORMED)
    _minv, escore, _minl, local = cv2.minMaxLoc(mapa)
    recorte = zona[local[1]:local[1] + th, local[0]:local[0] + tw].astype(int)
    b, g, r = recorte[:, :, 0], recorte[:, :, 1], recorte[:, :, 2]
    vermelho = (r > 90) & (r > g * 1.6) & (r > b * 1.6)
    return float(escore), float(vermelho.mean())


# ===========================================================================
# A SEGUNDA FASE DO BOSS, LIDA NA TELA.
#
# Limiar EM COR por necessidade medida, não por gosto. Modelo contra si
# mesmo cinza 1.000 / cor 1.000; modelo contra a fase 1 (sintética, faixa
# recolorida para o vermelho saturado que `vida_do_alvo` procura, luminância
# preservada) cinza 0.874 / cor 0.792; fase 2 degradada (jpeg 70+ruído)
# cor 0.985; fase 2 com 12% menos brilho cor 1.000. Em cinza a fase 1
# marcaria 0,874, acima do 0,85 de marcador de UI -- a Break Soul começaria
# a sair no primeiro segundo da luta do boss, que é exatamente o defeito que
# ela existe para evitar. Em cor sobra um vão limpo entre 0,792 e 0,985;
# 0.92 fica no meio dele (mesmo valor de `package_courage` em cor).
# ===========================================================================
LIMIAR_DA_FASE_2_DO_BOSS = 0.92


def boss_na_segunda_fase(
    frame: np.ndarray | None,
    template: np.ndarray | None,
) -> bool | None:
    """A barra AMARELA -- a primeira das duas vidas da fase 2 -- está na tela?

    A segunda fase do boss tem DUAS barras de vida, e a amarela é a primeira
    (palavras do usuário): *"uma amarela que é a primeira e depois que terminar
    a amarela vem a barra vermelha, normal como outros mobs; aí quando zera a
    barra vermelha ele morre."*. O amarelo é portanto um SINAL COM PRAZO: ele
    existe só no primeiro trecho da fase 2, no MESMO lugar da barra de vida.

    Duas consequências de projeto. (1) A bandeira que ele levanta é LATCH --
    nunca baixa. Se pudesse baixar num `False`, a Break Soul sairia de rotação
    exatamente na metade final da fase 2 -- a que decide a run. (2) Ausência
    de amarelo não é fase 1 (pode ser fase 2 já no vermelho); `False` é só
    ausência de sinal, não veredito.

    `True` = está lá, CONFIRMAÇÃO de que a segunda fase começou. `False` = não
    está, e **NÃO é prova de que a luta está na fase 1** -- é só ausência do
    sinal (barra fora da faixa, alvo trocado, captura ruim). `None` = não deu
    para olhar. Quem consome só age no `True`; mesma regra do
    `alvo_morto_na_tela` -- "não sei" valendo como resposta é o defeito que o
    `VigiaDoAlvo` existe para corrigir.

    O RECORTE é o par HP+MP do quadro do alvo (mesma faixa do `vida_do_alvo` e
    do `alvo_morto_na_tela`, topo central). Rodando os testes de cor do
    `vida_do_alvo` sobre o modelo: linhas 15-20 100% "azul" (mana), linhas 2-9
    0% "vermelho" (vida AMARELA), linha 1 100% "vermelho" (borda). A geometria
    fecha com `fim = 15 - LINHAS_ENTRE_HP_E_MP = 8` e `comeco = 1`, então a
    faixa `[2:9]` casa exatamente as linhas amarelas -- o amarelo ocupa a
    MESMA fatia de tela que a vermelha nas outras lutas, confirmando que é a
    primeira vida da fase 2 e não um enfeite ao lado. A faixa NÃO pode ser a
    tela inteira: o quadro do PRÓPRIO personagem (canto superior esquerdo) e o
    painel de time (esquerda) são pares HP+MP iguais -- a faixa começa em 30%
    da largura e os deixa de fora.

    BOMBA ARMADA registrada: enquanto a primeira vida da fase 2 está na tela
    ela é AMARELA, falha no teste `r > g * 1.6`, e `vida_do_alvo` devolve
    `0.0` (= "mob morreu"). Não é defeito ativo: o veredito de morte só é
    consultado quando quem chama pede TAB (`if tabs_ao_morrer and ...`), e a
    luta do boss usa `tabs_ao_morrer=0` -- quem encerra o boss é SAIR DE
    BATALHA. Alargar o teste de vermelho para aceitar amarelo mexeria no
    número que descarta o FUNDO ALARANJADO DA CAVERNA (vermelho alto com
    verde alto junto) -- amarelo é exatamente isso. Trocaria um defeito
    dormente por um falso positivo na leitura de vida dos guardas. Ver
    `docs/decisoes/combate.md`.
    """
    if frame is None or frame.size == 0 or template is None:
        return None

    altura, largura = frame.shape[:2]
    x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
    regiao = (x0, y0, x1 - x0, y1 - y0)
    if regiao[2] <= 0 or regiao[3] <= 0:
        return None

    # `find_all_templates` e não `find_template` porque só ele sabe comparar em
    # COR -- o `find_template` converte para cinza sempre, e em cinza a fase 1
    # marca 0,874. O custo do NMS sobre uma região de ~409x140 é irrelevante, e
    # de brinde vem o guarda de `ndim` que grita quando a carga do modelo erra o
    # modo, em vez de devolver "não tem" silenciosamente.
    return bool(find_all_templates(frame, template,
                                   threshold=LIMIAR_DA_FASE_2_DO_BOSS,
                                   region=regiao, colorido=True))
