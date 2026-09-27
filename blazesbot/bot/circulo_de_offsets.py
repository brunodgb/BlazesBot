"""CÍRCULO DE OFFSETS -- a antiga "última carta" da manobra de destravamento.

=============================================================================
DESLIGADO, E POR INTERRUPTOR (`navegacao.USAR_CIRCULO_DE_OFFSETS`)
=============================================================================

O círculo saiu do fluxo por decisão do usuário (*"só use o cálculo dos
waypoints vizinhos"*, docs/decisoes/navegacao.md) -- mas o jeito foi apagar a
chamada, e o código ficou sem chamador e sem teste, contra a regra do projeto
("caminho fora de uso vira interruptor, com teste forçando-o ligado"). Em
27/09/2026 (achados S07-05/T3-10 da auditoria) ele veio para cá, sem mudança de
lógica, e a chamada voltou ao ponto de onde saiu (depois de
`destravar_pelos_vizinhos` não alcançar nada), guardada pelo interruptor
desligado. Morar fora do `navegacao.py` é o que devolveu ao arquivo a folga da
catraca de tamanho.

O CLIQUE COM CONFERÊNCIA NÃO VEIO JUNTO: `Navigator._clicar_offset_e_verificar`
é usado também pelo passo de destrave da montaria, que está VIVO -- o achado
dizia que era código morto, e não era.

O QUE ELE FAZ. Quando nenhum waypoint é alcançado, o culpado costuma ser o
ÂNGULO em que o personagem parou -- principalmente na pirâmide do Secret Altar,
onde a escada tem ponto que é cenário e bloqueia a rota exata do waypoint.
Clicar num ponto LIGEIRAMENTE deslocado do destino faz o pathfinding achar uma
rota que o ângulo não bloqueia. E se nem ao redor do waypoint, ao redor da
PRÓPRIA posição, para trocar o ângulo de saída.

São 8 direções de bússola x raios crescentes (1, 2, 3, 5). Cada ponto é um
clique curto + janela de movimento (~2 s) -- NÃO um goto completo por ponto,
senão o trem de mobs encosta. Andou? Confirma o waypoint com um goto. A ordem
da varredura é uma constante para poder trocar no teste: por raio ou por
direção de bússola.
"""
from __future__ import annotations

import time

from .navegacao import (
    BUSSOLA,
    SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR,
    TOLERANCIA_ROTA,
    TRICKY_TOLERANCE,
)

CIRCULO_RAIOS = (1, 2, 3, 5)
# True = raio por raio (1,2,3,5; em cada raio os 8 pontos); False = bússola por
# bússola (N, NE, ...; em cada direção os 4 raios). Constante de teste.
CIRCULO_POR_RAIO = True
# Teto de tempo TOTAL do círculo antes de desistir e devolver o controle. É a
# última carta -- não pode virar mais uma forma de nunca parar (trem de mobs).
CIRCULO_TETO_SEGUNDOS = 6.5


def tentar(nav, rota: tuple, alvo_idx: int) -> int | None:
    """Clica levemente fora do alvo. Devolve `alvo_idx` se chegou, ou `None`.

    `alvo_idx` é o waypoint que não foi alcançado. Cada ponto é um clique curto
    + janela de movimento (`Navigator._clicar_offset_e_verificar`), não um goto
    completo. Andou? Só então confirma com um `goto` no waypoint real. Teto
    total de `CIRCULO_TETO_SEGUNDOS` para não virar outra forma de nunca
    desistir (o trem de mobs encosta a cada segundo).
    """
    ctx = nav.ctx
    alvo = rota[alvo_idx].pos
    tolerancia = nav.mapa.tolerancia_do_waypoint(
        rota[alvo_idx], TOLERANCIA_ROTA, TRICKY_TOLERANCE)
    # Q4: o PRÓPRIO personagem primeiro (quebrar o bolsão), o waypoint
    # depois. Quando o alvo está a dezenas de unidades, offsets de 1-5u ao
    # redor dele não trocam o ÂNGULO DE SAÍDA, que é o que destrava.
    centros = []
    atual = nav.position()
    if atual:
        centros.append(atual)
    centros.append(alvo)

    inicio = time.time()
    for centro, raio, (dx, dy) in _pontos_do_circulo(centros):
        ctx.raise_if_stopped()
        if time.time() - inicio > CIRCULO_TETO_SEGUNDOS:
            ctx.log.warning(
                "Círculo de offsets estourou o teto de %.0fs; devolvendo o "
                "controle", CIRCULO_TETO_SEGUNDOS)
            return None
        if nav._clicar_offset_e_verificar(centro, raio, dx, dy):
            if time.time() - inicio > CIRCULO_TETO_SEGUNDOS:
                return None
            ctx.log.info(
                "Offset (%d,%d) a %d unidades andou o personagem; confirmando "
                "o waypoint %s/%s", dx, dy, raio, alvo_idx + 1, len(rota))
            if nav.goto(alvo, tolerance=tolerancia,
                        max_seconds=SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR,
                        usar_mapa=False):
                return alvo_idx
    return None


def _pontos_do_circulo(
    centros: list[tuple[int, int]],
) -> list[tuple[tuple[int, int], int, tuple[int, int]]]:
    """Gera (centro, raio, direção) conforme `CIRCULO_POR_RAIO`.

    `True` -> raio por raio (1,2,3,5; em cada raio as 8 direções).
    `False` -> bússola por bússola (N, NE, ...; em cada direção os 4 raios).
    """
    pontos = []
    for centro in centros:
        if CIRCULO_POR_RAIO:
            for raio in CIRCULO_RAIOS:
                for diret in BUSSOLA:
                    pontos.append((centro, raio, diret))
        else:
            for diret in BUSSOLA:
                for raio in CIRCULO_RAIOS:
                    pontos.append((centro, raio, diret))
    return pontos
