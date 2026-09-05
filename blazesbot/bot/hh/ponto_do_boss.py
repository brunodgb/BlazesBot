"""O contrato de POSIÇÃO de um ponto de luta da HH.

=========================================================================
POR QUE ISTO EXISTE
=========================================================================

Auditoria de 05/09/2026, defeito #2. A rotina aceitava "saí de batalha" como
"limpei este ponto" -- e as duas coisas não são a mesma.

O que o log mostrou, no primeiro boss:

    DESTRAVADO (o pacote do Fa-Yuan) em 39s: 6 morte(s), 6 TAB, 91 golpes
    ALVO MORREU: Elite Blackshirt Bandit                     (x6)
    HH: andei atrás dos mobs do Fa-Yuan (de (275,138) para (317,149))
    Não consegui parar em (275,138) ... (estou em (317,149))
    ...
    a run continua no trecho do Dupla (1 de 4 já feitos)

O personagem perseguiu mobs, limpou um pacote **46 unidades fora** do ponto do
boss (271,137), e a run creditou o Fa-Yuan. O boss nunca engajou.

Três defeitos encadeados produziram isso, e este módulo fecha os três:

  1. A ÂNCORA ERA UMA POSIÇÃO CAPTURADA, e não o waypoint do mapa. Sob rollback
     ela guarda onde o rollback largou o personagem -- no log, (275,138) em vez
     de (271,137).
  2. A VITÓRIA NÃO CONFERIA ONDE ACONTECEU. `limpar_o_combate` responde "a flag
     baixou", nunca "o ponto está limpo".
  3. A FALHA DO RETORNO ERA DESCARTADA: `_voltar_ao_ponto` era `-> None` e
     jogava fora o booleano de `encostar_no_ponto`.

=========================================================================
O QUE ESTE MÓDULO NÃO DECIDE
=========================================================================

Ele não sabe lutar, nem quando desistir. Responde duas perguntas -- *"estou
nele?"* e *"consegue me levar de volta?"* -- e quem age é a rotina.
"""
from __future__ import annotations

from collections.abc import Callable

from . import mapa_hh


class PontoDoBoss:
    """O waypoint que fecha um trecho, e a régua de estar nele.

    `ponto` vem SEMPRE do mapa (`TRECHOS_DOS_BOSSES[...][2]`, que é o último
    waypoint do trecho). Nunca de uma leitura de posição: leitura é onde o
    personagem está, e o contrato é sobre onde ele DEVERIA estar.
    """

    def __init__(self, rotulo: str, ponto: tuple[int, int],
                 tolerancia: int) -> None:
        self.rotulo = rotulo
        self.ponto = ponto
        self.tolerancia = tolerancia

    def distancia_de(self, pos: tuple[int, int] | None) -> float | None:
        """Quão longe do ponto. `None` quando não há leitura."""
        if pos is None:
            return None
        return mapa_hh.distancia(pos, self.ponto)

    def estou_nele(self, pos: tuple[int, int] | None) -> bool:
        """O personagem está no ponto, dentro da tolerância?

        SEM LEITURA, RESPONDE `False`. É o oposto do resto do bot, onde "não
        sei" costuma liberar -- e aqui é de propósito: esta resposta autoriza
        CREDITAR um boss. Creditar sem saber onde o personagem está é
        exatamente o defeito que o módulo existe para fechar; o custo de errar
        para o lado seguro é refazer um trecho.
        """
        distancia = self.distancia_de(pos)
        return distancia is not None and distancia <= self.tolerancia

    def voltar_para_ele(
        self,
        pos: tuple[int, int] | None,
        encostar: Callable[..., bool],
        log,
        segundos_por_tentativa: float,
        tentativas: int = 2,
    ) -> bool:
        """Traz o personagem de volta ao ponto. Devolve se CONSEGUIU.

        Mob ranged não vem até o personagem -- é o personagem que anda até ele
        quando a rotação mira longe. O bot em Lua faz o mesmo retorno
        (`hh.killAtPosition`, *"Char andou pra atacar o mob, voltando pra ..."*).

        JÁ ESTAR NELE É SUCESSO, e sem clique nenhum: um clique de minimapa é
        barato, mas não é de graça em toda run.
        """
        if self.estou_nele(pos):
            return True

        log.info(
            "HH: andei atrás dos mobs do %s (estou em %s, o ponto é %s); "
            "voltando ao ponto", self.rotulo, pos, self.ponto)
        return bool(encostar(
            alvo=self.ponto,
            precisao=self.tolerancia,
            tentativas=tentativas,
            segundos_por_tentativa=segundos_por_tentativa,
            o_que=f"voltar ao ponto do {self.rotulo}",
        ))


def do_trecho(trecho: int, tolerancia: int) -> PontoDoBoss:
    """O ponto do trecho `trecho`, lido do mapa.

    Existe para que ninguém monte o par (rótulo, ponto) na mão: os dois vêm da
    MESMA linha de `TRECHOS_DOS_BOSSES`, e separá-los é como o ponto do boss e
    o fim do caminho divergiram em 04/09/2026.
    """
    rotulo, _caminho, ponto = mapa_hh.TRECHOS_DOS_BOSSES[trecho]
    return PontoDoBoss(rotulo, ponto, tolerancia)


__all__ = ["PontoDoBoss", "do_trecho"]
