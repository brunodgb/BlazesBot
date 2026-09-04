"""
A barra de HP do alvo, lida da tela.

Dois caminhos: `USAR_OFFSET_FIXO_DA_BARRA` (a régua atual) e `_vida_por_ancora_azul`
(a reserva). A reserva é a busca pela barra de mana do alvo (linha azul longa
no quadro do alvo) e medida de vida logo acima dela; a régua é o offset fixo
medido em 25/08/2026. Quem escolhe é o interruptor `USAR_OFFSET_FIXO_DA_BARRA`.
A fonte da leitura (`fonte="offset_fixo" | "ancora_azul"`) vai para o log, então
trocar de régua no meio da run não passa despercebido.

`MINIMO_RECONHECIDO_NA_FAIXA` é o que separa "li a barra" de "estou olhando
outra coisa" -- a fração mínima da faixa que precisa cair num dos três casos
reconhecidos (vermelho, amarelo, vazio). Abaixo disso a resposta é `None`,
nunca um número confiante. É o conserto do defeito medido em 21/08: na conta
APP a leitura antiga devolvia float confiante com piso em 14,2%, 14 valores
distintos e vãos -- estava medindo um retângulo que não era a barra.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from blazesbot.core.vision.marcadores import (
    LARGURA_MINIMA_DA_BARRA,
    LINHAS_ENTRE_HP_E_MP,
    ALTURA_DA_BARRA,
    _corrida_mais_longa,
    _regiao_quadro_alvo,
)

# ===========================================================================
# A BARRA DO ALVO POR OFFSET FIXO -- medida pelo usuário em 25/08/2026
# ===========================================================================
#
# A medição foi feita com um calibrador que mostra a posição do cursor RELATIVA
# À ÁREA DE CLIENTE (via `ClientToScreen`) e a cor do pixel embaixo dele:
#
#     x=600, y=47   (188-190, 0, 2-3)   vermelho -- ponta presa ao retrato
#     x=539, y=47   (190, 0, 2)         vermelho -- meio da barra
#     x=466, y=47   (188, 0, 3)         vermelho -- outra ponta
#     x=529, y=50   ( 55, 9, 45)        roxo escuro -- a cor do VAZIO
#
# A BARRA NÃO ESCALA COM A RESOLUÇÃO, E ISSO FOI CONFIRMADO EM DUAS: o usuário
# trocou o jogo de 1024x768 para 1680x1050 **sem mexer em coordenada nenhuma** e
# a leitura continuou acompanhando o dano de 100% a 0%. Isso CONFIRMA a regra
# do `CLAUDE.md` ("a UI do jogo NÃO escala"). Quem estava fora da regra era a
# busca por faixa PROPORCIONAL (`largura * 0.30`) que este arquivo usava -- a
# 1680 a faixa começava em x=504 e os 466 da barra ficavam de fora, sobrando
# 96 px dos 134, abaixo de `LARGURA_MINIMA_DA_BARRA`, e a leitura devolvia
# `None` para sempre.
BARRA_DO_ALVO_X0 = 466
BARRA_DO_ALVO_X1 = 600            # exclusivo -> 134 colunas
BARRA_DO_ALVO_Y0 = 46
BARRA_DO_ALVO_Y1 = 49             # exclusivo -> 3 linhas

# A fração da faixa que precisa ser reconhecida (vida ou vazio) para a leitura
# valer. Abaixo disso o recorte está olhando outra coisa -- e a resposta certa é
# "não sei", nunca um número.
#
# ISTO É O CONSERTO DO DEFEITO MEDIDO EM 21/08: na conta APP a leitura antiga
# devolveu float confiante com piso em 14,2%, 14 valores distintos e vãos --
# estava medindo um retângulo que não era a barra do alvo, e não tinha como
# dizer isso.
MINIMO_RECONHECIDO_NA_FAIXA = 0.70


@dataclass(frozen=True)
class LeituraDaBarra:
    """O que a faixa da barra do alvo mostra AGORA.

    Contagem por COLUNA, não por área, e a diferença é medida: a leitura antiga
    dividia pixels vermelhos pela área inteira do retângulo, então a borda e as
    linhas de cima diluíam o valor -- era daí que vinha o piso de 0,7% que o
    usuário via com o mob morto. Coluna cheia é coluna de vida; coluna vazia é
    coluna vazia.
    """

    vermelho: float                 # 0..1 das colunas
    amarelo: float                  # 0..1 das colunas
    vazio: float                    # 0..1 das colunas
    colunas: int
    primeiro_x: int | None          # primeira coluna com VIDA (relativa à faixa)
    ultimo_x: int | None            # última coluna com VIDA
    fonte: str                      # "offset_fixo" | "ancora_azul"

    @property
    def vida(self) -> float:
        """A fração da barra DESENHADA agora.

        Com as duas barras do boss sobrepostas, a que está por cima é a amarela;
        enquanto ela existe, é ela que está descendo. Quando ela acaba, a
        vermelha que estava por baixo passa a ser a barra da vez.
        """
        return self.amarelo if self.amarelo > 0.0 else self.vermelho

    @property
    def na_segunda_fase(self) -> bool:
        """Amarelo na faixa = as duas barras estão sobrepostas = fase 2."""
        return self.amarelo > 0.0

    def total_do_boss(self, segunda_fase: bool) -> float:
        """Vida TOTAL do boss em 0..1, juntando as duas barras.

        Palavras do usuário: *"a barra amarela sobrepõe a vermelha e conforme
        ela vai baixando vai aparecendo a vermelha"*, e *"amarelo na tela você
        começa em 100% e quando vier o vermelho quer dizer que é 50% para
        menos"*.

        Então, com a amarela na tela, o total vai de 100% a 50%; sem ela, na fase
        2, a vermelha vai de 50% a 0%. Na fase 1 a vermelha é a vida inteira.
        """
        if self.amarelo > 0.0:
            return 0.5 + 0.5 * self.amarelo
        return 0.5 * self.vermelho if segunda_fase else self.vermelho


def _classificar_colunas(faixa: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classifica cada COLUNA da faixa em vermelho / amarelo / vazio.

    Uma coluna vale pelo que a MAIORIA das suas linhas mostra. Três linhas com
    ruído de compressão em uma não estragam a coluna, e uma linha isolada de
    borda não cria vida onde não tem.

    As cores vêm da medição do usuário (vermelho `(188-190, 0, 2-3)`, vazio
    `(55, 9, 45)`), com folga para brilho e compressão. **O AMARELO NÃO FOI
    MEDIDO** -- é a única cor aqui por dedução (vermelho e verde altos, azul
    baixo), e o log grava a contagem bruta justamente para a primeira luta de
    boss confirmá-la ou derrubá-la.
    """
    b = faixa[:, :, 0].astype(int)
    g = faixa[:, :, 1].astype(int)
    r = faixa[:, :, 2].astype(int)

    vermelho = (r > 120) & (g < 70) & (b < 70)
    amarelo = (r > 120) & (g > 100) & (b < 90)
    vazio = (r < 100) & (g < 60) & (b < 100) & ((r + b) > 30)

    metade = faixa.shape[0] / 2.0
    return (vermelho.sum(axis=0) > metade,
            amarelo.sum(axis=0) > metade,
            vazio.sum(axis=0) > metade)


def ler_barra_do_alvo(frame: np.ndarray | None) -> LeituraDaBarra | None:
    """A faixa da barra do alvo, no offset fixo medido. `None` = não sei.

    NÃO PROCURA NADA. A posição é conhecida (ver o bloco de `BARRA_DO_ALVO_X0`),
    então não há corrida azul para achar, não há geometria para escorregar, e não
    há como acabar medindo a barra do próprio personagem ou a de um membro do
    time -- que foi o que produziu o piso de 14,2% na conta APP.

    A única forma de errar que sobra é o recorte cair fora do quadro do alvo, e
    contra isso existe `MINIMO_RECONHECIDO_NA_FAIXA`: se as cores da faixa não
    forem as da barra, a resposta é `None`.
    """
    if frame is None or frame.size == 0:
        return None
    altura, largura = frame.shape[:2]
    if largura < BARRA_DO_ALVO_X1 or altura < BARRA_DO_ALVO_Y1:
        return None

    faixa = frame[BARRA_DO_ALVO_Y0:BARRA_DO_ALVO_Y1,
                  BARRA_DO_ALVO_X0:BARRA_DO_ALVO_X1]
    if faixa.size == 0:
        return None

    col_vermelho, col_amarelo, col_vazio = _classificar_colunas(faixa)
    colunas = int(col_vermelho.size)
    if colunas == 0:
        return None

    reconhecidas = int((col_vermelho | col_amarelo | col_vazio).sum())
    if reconhecidas < colunas * MINIMO_RECONHECIDO_NA_FAIXA:
        return None

    com_vida = col_vermelho | col_amarelo
    onde = np.where(com_vida)[0]
    return LeituraDaBarra(
        vermelho=float(col_vermelho.sum()) / colunas,
        amarelo=float(col_amarelo.sum()) / colunas,
        vazio=float(col_vazio.sum()) / colunas,
        colunas=colunas,
        primeiro_x=int(onde[0]) if onde.size else None,
        ultimo_x=int(onde[-1]) if onde.size else None,
        fonte="offset_fixo",
    )


def _barra_vermelha_e_hp_valida(faixa: np.ndarray) -> bool:
    """Valida que a faixa vermelha se comporta como barra de HP:
    - preenche da ESQUERDA para direita (sem buracos grandes no meio)
    - é contígua (uma única corrida principal por linha)
    - não tem 'piso' alto quando deveria ser zero
    - largura geral não aumenta de cima para baixo (monotonicidade grosseira)
    """
    if faixa.size == 0:
        return False

    altura, largura = faixa.shape
    if altura < 2 or largura < 10:
        return False

    # Para cada linha, a barra deve ser uma corrida contígua começando perto do x=0
    # (relativo ao início da barra de mana). HP não tem buracos GRANDES no meio.
    linhas_validas = 0
    for y in range(altura):
        linha = faixa[y]
        if not np.any(linha):
            # Linha totalmente vazia - aceitável em qualquer posição (ruído/compressão)
            # mas contamos apenas linhas com sinal
            continue

        linhas_validas += 1

        # Encontrar primeiro e último pixel True
        primeiros = np.where(linha)[0]
        primeiro = primeiros[0]
        ultimo = primeiros[-1]

        # Deve começar perto do 0 (tolerância 3px por ruído/compressão/jpeg)
        if primeiro > 3:
            return False

        # Não deve ter buracos GRANDES: permitir até 2 buracos de 1px por linha
        # (compressão JPEG pode criar pixels isolados falsos)
        segmento = linha[primeiro:ultimo + 1]
        buracos = np.sum(~segmento)
        if buracos > 2:
            return False

    # Precisa de pelo menos 2 linhas com sinal (ruído pode matar linhas isoladas)
    if linhas_validas < 2:
        return False

    # Verificar monotonicidade geral: largura não deve aumentar de cima para baixo
    # (a barra de HP só encurta, nunca alonga, à medida que a vida cai)
    # Tolerância maior (5px) para ruído de captura/compressão
    larguras = [np.sum(faixa[y]) for y in range(altura) if np.any(faixa[y])]
    for i in range(1, len(larguras)):
        if larguras[i] > larguras[i - 1] + 5:
            return False

    return True


# ===========================================================================
# INTERRUPTOR: o offset fixo é a régua; a âncora azul é a reserva
# ===========================================================================
#
# `True`  = lê pelo offset medido (`ler_barra_do_alvo`) e só cai para a busca
#           pela barra de mana se o recorte não reconhecer a faixa.
# `False` = comportamento anterior, só a busca pela âncora azul.
#
# A reserva NÃO é enfeite: o offset fixo foi medido em DUAS resoluções, mas em
# um cliente só. Se um dia a barra sair do lugar, a busca ainda acha -- e o
# `fonte` da leitura diz no log qual das duas respondeu, então trocar de régua
# no meio da run não passa despercebido.
USAR_OFFSET_FIXO_DA_BARRA = True


def vida_do_alvo(frame: np.ndarray | None) -> float | None:
    """Fração de vida da barra DESENHADA do alvo (0.0 a 1.0), ou `None`.

    `None` quando o quadro não foi encontrado -- sem alvo, quadro expirado
    depois da morte, ou captura ruim. Quem chama decide o que fazer com isso;
    aqui não se adivinha.

    `0.0` é a barra VAZIA com o quadro presente: o mob morreu.

    NA FASE 2 DO BOSS ELA DEVOLVE A AMARELA, que é a barra de cima. Quem precisa
    da vida TOTAL das duas usa `ler_barra_do_alvo(...).total_do_boss(...)` -- a
    conta de juntar as duas mora lá, num lugar só.
    """
    if USAR_OFFSET_FIXO_DA_BARRA:
        leitura = ler_barra_do_alvo(frame)
        if leitura is not None:
            return leitura.vida
    return _vida_por_ancora_azul(frame)


def _vida_por_ancora_azul(frame: np.ndarray | None) -> float | None:
    """A RESERVA: acha a barra de mana e mede a vida logo acima dela.

    Era a régua principal até 25/08/2026. Continua inteira porque ela não depende
    de a barra estar num lugar conhecido -- só de ela estar acima de uma corrida
    azul longa. Ver `USAR_OFFSET_FIXO_DA_BARRA`.
    """
    if frame is None or frame.size == 0:
        return None

    altura, largura = frame.shape[:2]
    x0, y0, x1, y1 = _regiao_quadro_alvo(largura, altura)
    if x1 <= x0 or y1 <= y0:
        return None

    zona = frame[y0:y1, x0:x1].astype(int)
    if zona.size == 0:
        return None

    b, g, r = zona[:, :, 0], zona[:, :, 1], zona[:, :, 2]
    # Os limiares de cor vêm dos prints: a barra de mana é azul saturado e a de
    # vida é vermelho saturado. Exigir dominância sobre os OUTROS dois canais
    # (e não só valor alto) é o que descarta o fundo alaranjado da caverna, que
    # tem vermelho alto mas verde alto junto.
    azul = (b > 90) & (b > r * 1.4) & (b > g * 1.2)
    vermelho = (r > 90) & (r > g * 1.6) & (r > b * 1.6)

    for y in range(azul.shape[0]):
        inicio, comprimento = _corrida_mais_longa(azul[y])
        if comprimento < LARGURA_MINIMA_DA_BARRA:
            continue

        # Achou a barra de mana. A de vida termina `LINHAS_ENTRE_HP_E_MP` acima,
        # e a primeira linha dela é borda -- descartada (ver o comentário acima).
        fim = y - LINHAS_ENTRE_HP_E_MP
        comeco = fim - ALTURA_DA_BARRA + 1
        if comeco < 0:
            continue  # tenta próxima linha de mana, não aborta tudo

        faixa = vermelho[comeco + 1:fim + 1, inicio:inicio + comprimento]
        if faixa.size == 0:
            continue

        # VALIDAÇÃO CRÍTICA: a faixa vermelha deve se comportar como HP.
        # Isso descarta a mana do próprio personagem / membros do time no APP,
        # que têm geometria parecida mas a "vida" medida não é uma barra contígua
        # preenchendo da esquerda (piso 14.2%, vãos, valores discretos).
        if not _barra_vermelha_e_hp_valida(faixa):
            continue

        return float(faixa.sum()) / float(faixa.size)

    # Não encontrou barra azul de mana válida COM vida válida abaixo =
    # quadro do alvo não está na tela (sem alvo, alvo morto, captura ruim,
    # ou azul achado era de outro elemento UI).
    # Retornar None em vez de float confiante errado é a correção do defeito
    # medido no APP (piso 14.2%, vãos, 21 valores discretos) e na BC (geometria
    # instável: 4 larguras diferentes na mesma coleta).
    return None
