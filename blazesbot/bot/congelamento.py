"""O PERSONAGEM CONGELADO, e por que a montaria é o remédio.

===========================================================================
O RELATO E A ASSINATURA MEDIDA
===========================================================================

Usuário, 08/09/2026: *"dentro de HH tem lag e rollback muito forte, mas no caso
de HH eu percebi algumas vezes que o lag é tanto que chega a travar o
personagem, e só destrava se ele faz alguma ação e como está na montaria, a
única ação possível é sair da montaria"*. E, sobre o mecanismo: *"o ideal é
sempre mexer na montaria, seja desmontando ou montando nela de volta, nessas
tentativas obriga o servidor a pensar e com isso na maioria das vezes faz
desbugar e destravar"*.

A assinatura no log é inconfundível -- seis cliques de minimapa seguidos com a
MESMA distância, montado, sem mover um pixel:

    Montaria ativa (120% de velocidade)
    sem progresso indo para (272, 136) (distância 47) — relançando (1)
    sem progresso indo para (272, 136) (distância 47) — relançando (3)
    sem progresso indo para (272, 136) (distância 47) — relançando (3)
    Não consegui parar em (272, 136) (estou em (315, 156))

===========================================================================
CONGELAMENTO NÃO É ROLLBACK, E A DIFERENÇA DECIDE O REMÉDIO
===========================================================================

No rollback a coordenada MUDA -- medido 2 -> 2 -> 7, o personagem se afasta do
alvo. Rollback não se conserta com montaria (quem o conserta é a reancoragem de
`follow_path`), então **qualquer mudança de coordenada zera este relógio**.

E há um detalhe que o usuário observou e que confirma o desenho: *"quando está
travado ele fica em uma posição só, mas na hora que destrava, por exemplo quando
sai da montaria, vai ter um rollback"*. Ou seja, o destravamento se ANUNCIA por
um rollback -- e o rollback já é tratado dentro de `follow_path`, que espera o
servidor assentar e reancora pelo waypoint por onde o personagem acabou de
passar. Este módulo não precisa saber nada sobre isso.

===========================================================================
POR QUE O RELÓGIO É DESTE OBJETO, E NÃO DO TRAJETO
===========================================================================

O congelamento medido acontece nos trajetos CURTOS de 5 s ("voltar ao ponto do
boss"), e um relógio que nascesse zerado em cada chamada de `follow_path` nunca
chegaria aos 15 s: 5 + 5 + 5 seriam três relógios de 5. O `Navigator` guarda uma
instância deste vigia pela run inteira, então o tempo atravessa as chamadas.

===========================================================================
QUEM LIGA
===========================================================================

`ligado` NASCE DESLIGADO, e essa é a mesma disciplina dos dois ganchos de
destravamento do `Navigator`: em 04/09/2026 o BC herdou um desmonte que era da
HH e passou a lutar antes do Altar Stone.

Só a HH liga, por decisão do usuário: *"dentre todos os testes nunca aconteceu
igual... BC pode manter como está, pois já rodamos runs o suficiente para
verificar que não aconteceu esse travamento indefinido, mas em HH já aconteceu
mais de 2 vezes"*.

Ver `docs/decisoes/hh.md` §23.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from ..core import diario
from .context import BotContext

# Quanto tempo na MESMA coordenada, tentando andar, antes de mexer na montaria.
#
# NÚMERO DO USUÁRIO, e ele cabe dentro do teto de 30 s que já existia
# (`navegacao.TETO_PRESO_NO_MESMO_PONTO`, também dele): sobram 15 s para a
# manobra provar efeito antes de o trajeto ser abortado.
SEGUNDOS_PARA_CUTUCAR = 15.0

# A segunda cutucada, no MEIO do que resta até aquele teto.
#
# DERIVADO, não medido -- e derivado de propósito: mudando um dos dois números
# do usuário, este acompanha sozinho em vez de virar mentira. Fica em 22,5 s.
SEGUNDOS_PARA_A_SEGUNDA = 22.5

# Quantas cutucadas por congelamento.
#
# DUAS, e cada uma vale DOIS toques na montaria: o desmonte é este código, e a
# remontagem vem de graça na volta seguinte do laço, porque `_manter_montaria`
# aperta a tecla de montar a cada volta. São quatro mudanças de estado dentro da
# janela -- o "obriga o servidor a pensar" do usuário.
#
# E NÃO MAIS QUE DUAS: se o segundo par não destravou, o problema não é a
# montaria, e insistir num remédio que não funciona é como o bot fica horas sem
# farmar. Quem assume é o teto de 30 s, que devolve o controle para a rotina --
# ela sabe refazer o trecho e passa pelo `_guard()`.
CUTUCADAS = 2

# A MEDIÇÃO QUE DECIDE SE OS 15 S PODEM CAIR (26/09/2026). Nos 16 dias do
# `logs/eventos.log`, a PRIMEIRA cutucada destravou 87% dos congelamentos da cave
# (191 de 219) e destrava em ~2 s -- então quase todo o custo de um congelamento
# é a espera. O que falta saber é quantas paradas se resolvem SOZINHAS antes dos
# 15 s: com o limiar mais baixo, elas levariam cutucada à toa. Só log; o juiz é
# `tools/medir_o_congelamento.py`.
MEDIR_O_CONGELAMENTO = True
# Parada mais curta que isto não entra: lendo a posição ~4 vezes por segundo,
# menos que isto andando é ruído de leitura, não parada. Limiar de REGISTRO, não
# espera -- o juiz só avalia limiares a partir de 3 s.
LIMIAR_DA_PARADA_REGISTRADA = 2.0


class VigiaDoCongelamento:
    """Vê a coordenada travada e mexe na montaria. Desligado, não faz nada."""

    def __init__(self, ctx: BotContext,
                 desmontar: Callable[[], bool],
                 maximo_sem_leitura: float) -> None:
        self.ctx = ctx
        # QUEM DESMONTA É O NAVIGATOR, injetado. Este módulo decide QUANDO, e
        # não sabe apertar tecla nenhuma -- é o que o mantém testável sem jogo.
        self._desmontar = desmontar
        # O MAIOR INTERVALO LEGÍTIMO ENTRE DUAS LEITURAS. Injetado pelo
        # `Navigator`, que sabe o número (o portão da montaria) -- ver `olhar`.
        self._maximo_sem_leitura = maximo_sem_leitura
        self.ligado = False
        self._desde = 0.0
        self._visto_em = 0.0
        self._posicao: tuple[int, int] | None = None
        self._cutucadas = 0

    # -- leitura -----------------------------------------------------------

    @property
    def segundos_congelado(self) -> float:
        """Há quanto tempo a coordenada não muda. Zero = não está congelado."""
        if self._posicao is None or not self._desde:
            return 0.0
        return time.time() - self._desde

    def esquecer(self) -> None:
        """Zera o relógio. Para quem sabe que o personagem foi movido de
        propósito -- teleporte, revive, entrada de cave."""
        self._posicao = None
        self._desde = 0.0
        self._visto_em = 0.0
        self._cutucadas = 0

    def _medir_a_parada(self, agora: float) -> None:
        """Registra a parada que acabou AGORA -- a coordenada mudou.

        A parada interrompida porque o bot parou de andar (a leitura veio tarde
        demais, e o relógio foi zerado lá em cima) NÃO entra: ali não se sabe se
        o personagem destravou, e o juiz precisa do desfecho.
        """
        if not MEDIR_O_CONGELAMENTO or self._posicao is None or not self._desde:
            return
        parado = agora - self._desde
        if parado >= LIMIAR_DA_PARADA_REGISTRADA:
            self.ctx.log.debug("CONGELAMENTO/MEDIÇÃO parado=%.1fs cutucadas=%d em %s",
                               parado, self._cutucadas, self._posicao)

    # -- o gesto -----------------------------------------------------------

    def olhar(self, pos: tuple[int, int], o_que: str) -> bool:
        """Uma leitura de coordenada. Devolve se cutucou a montaria agora.

        Chamado a cada volta do laço de deslocamento, com a posição que ele
        acabou de ler -- nenhuma leitura nova é paga aqui.
        """
        if not self.ligado:
            return False

        ctx = self.ctx
        agora = time.time()

        # =================================================================
        # O RELÓGIO SÓ CORRE ENQUANTO O BOT TENTA ANDAR
        # =================================================================
        #
        # `olhar` é chamado a cada volta do laço de deslocamento, ~4 vezes por
        # segundo. Se a volta anterior foi há muito tempo, o bot NÃO ESTAVA
        # tentando andar nesse intervalo -- ele estava vendendo, apagando lixo,
        # falando com NPC. Parado de propósito não é congelado.
        #
        # SEM ISTO, TODO DESMONTE FORA DA CAVE ERA FALSO. Medido em 17-18/09:
        # as 51 cutucadas fora da cave são o MESMO caso -- personagem no ponto
        # de venda (-343,-294), mandado andar 6 unidades até a porta
        # (-342,-288), com "congelado há 15-23 s" cravado no tempo da venda
        # mais a limpeza da bolsa. Uma delas marcou **2034 s**, o ciclo inteiro
        # de uma run. A primeira leitura depois da pausa via um relógio que
        # nunca tinha sido zerado e cutucava na hora -- 1 ms depois de o
        # trajeto começar.
        #
        # E NÃO DÁ PARA USAR O ALVO como discriminador: o destravamento chama
        # `follow_path` de novo com OUTRO waypoint enquanto o personagem segue
        # congelado no mesmo lugar, e zerar ali apagaria justamente os
        # congelamentos verdadeiros de dentro da cave.
        if self._visto_em and agora - self._visto_em > self._maximo_sem_leitura:
            self._posicao = None
        self._visto_em = agora

        # QUALQUER mudança de coordenada zera -- inclusive o rollback, que é
        # outro problema e tem outro remédio.
        if self._posicao is None or pos != self._posicao:
            self._medir_a_parada(agora)
            self._posicao = pos
            self._desde = agora
            self._cutucadas = 0
            return False

        if self._cutucadas >= CUTUCADAS:
            return False
        parado = agora - self._desde
        limite = SEGUNDOS_PARA_CUTUCAR if not self._cutucadas else SEGUNDOS_PARA_A_SEGUNDA
        if parado < limite:
            return False

        # "NÃO SEI" NÃO AUTORIZA: sem leitura da montaria não há gesto certo a
        # fazer, e mandar tecla no escuro é o que este projeto não faz.
        montado = ctx.memory.is_mounted()
        if montado is None:
            return False

        self._cutucadas += 1
        if montado:
            ctx.log.warning(
                "CONGELADO em %s há %.0fs tentando %s: desmontando para o "
                "servidor reagir (cutucada %s de %s). A montaria volta na "
                "próxima volta do laço.",
                pos, parado, o_que, self._cutucadas, CUTUCADAS)
            # `permitir_em_batalha=True`, e a exceção é o ponto: o escudo da
            # montaria existe para o personagem não PARAR de andar, e aqui ele
            # não anda de jeito nenhum. Desmontado e em batalha, quem mata é o
            # gancho que já existe (`matar_quando_o_trajeto_trava`).
            self._desmontar()
        else:
            # A PÉ o remédio já está rodando: `_manter_montaria` aperta a tecla
            # de montar a cada volta deste mesmo laço, então não há gesto novo a
            # dar. Fica o registro, para o log não ficar mudo sobre um
            # congelamento que o teto de 30 s vai abortar.
            ctx.log.warning(
                "CONGELADO em %s há %.0fs tentando %s, e A PÉ: a tecla de "
                "montar já sai a cada volta. Sem gesto novo a dar.",
                pos, parado, o_que)

        # EVENTO PRÓPRIO, e não o `"travado"` que já existe -- aquele é do teto
        # de insistência, e confundir os dois apagaria a única medida que diz se
        # 15 s é o número certo e se a montaria é de fato o remédio.
        try:
            diario.registrar_evento(
                ctx.account_login, "congelado",
                f"{parado:.0f}s na mesma coordenada, "
                f"{'montado' if montado else 'a pé'}, cutucada "
                f"{self._cutucadas}/{CUTUCADAS}",
                pos, ctx.memory.location(),
            )
        except Exception as exc:                   # diário não derruba run
            ctx.log.debug("Não registrei o congelamento no diário: %s", exc)
        return True


__all__ = ["CUTUCADAS", "SEGUNDOS_PARA_A_SEGUNDA", "SEGUNDOS_PARA_CUTUCAR",
           "VigiaDoCongelamento"]
