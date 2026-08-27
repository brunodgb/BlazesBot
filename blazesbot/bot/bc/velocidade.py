"""
Skill de velocidade da montaria: +30% por 30 segundos, 6 minutos de recarga.

=========================================================================
POR QUE ELA MERECE UM MÓDULO
=========================================================================

Ela é a ÚNICA skill que funciona montado. Todo o resto -- poção, comida de pet,
invocar pet, cura, buff -- exige desmontar primeiro. Isso a torna a única coisa
que o bot pode fazer sem interromper a travessia da cave, e é justamente na
travessia que o tempo custa vida: os mobs do caminho vêm atrás e formam um trem.

E ela é CARA em tempo: 30 segundos de efeito para 6 minutos de recarga. Usar na
cidade significa não ter na cave. Usar assim que entra, antes de o personagem
sequer começar a andar, desperdiça parte dos 30 segundos parado.

=========================================================================
AS REGRAS, E DE ONDE CADA UMA VEM
=========================================================================

1. SÓ DENTRO DA CAVE. Fora dela não há pressa e não há trem de mobs.
2. SÓ MONTADO. A skill afeta a montaria; a pé ela não faz nada e a recarga
   começaria a contar do mesmo jeito.
3. SÓ DEPOIS DE COMEÇAR A ANDAR. Disparar no instante da entrada gastaria
   segundos de efeito com o personagem parado.
4. NUNCA ANTES DE A RECARGA FECHAR. Apertar a tecla na recarga não faz nada, e o
   bot não tem como perceber isso pela memória -- ele acharia que ganhou
   velocidade e calcularia os tempos limite da rota como se estivesse 30% mais
   rápido. Daí o cronômetro: o bot conta os 6 minutos, e não adivinha.

O cronômetro é por PERSONAGEM, e vive enquanto o supervisor daquela conta vive.
Ele sobrevive a runs consecutivas, que é o que importa: duas runs seguidas
costumam cabar dentro da mesma janela de recarga.
"""
from __future__ import annotations

import time

from ...config import SPEED_DURACAO_SEGUNDOS, SPEED_RECARGA_SEGUNDOS

# Quanto o personagem precisa ter andado antes de valer a pena acionar.
#
# Existe para não gastar efeito parado. Meio segundo é suficiente: o clique no
# minimapa já saiu e o personagem está acelerando.
SEGUNDOS_ANDANDO_ANTES = 0.5


class SkillDeVelocidade:
    """Cronômetro e acionamento da skill de velocidade da montaria."""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self._usada_em: float = 0.0
        self._tentativas = 0

    # -- estado ------------------------------------------------------------

    @property
    def tecla(self) -> str:
        return self.ctx.settings.keys.speed_skill or ""

    @property
    def habilitada(self) -> bool:
        return bool(self.tecla and self.ctx.settings.bc.usar_skill_de_velocidade)

    @property
    def segundos_de_recarga(self) -> float:
        """Quanto falta para poder usar de novo. Zero = disponível."""
        if not self._usada_em:
            return 0.0
        passou = time.time() - self._usada_em
        return max(0.0, SPEED_RECARGA_SEGUNDOS - passou)

    @property
    def disponivel(self) -> bool:
        return self.habilitada and self.segundos_de_recarga <= 0.0

    @property
    def ativa(self) -> bool:
        """O efeito ainda está valendo?

        Serve para o log e para os tempos limite de trajeto: com a skill ativa o
        personagem cobre o mesmo caminho em menos tempo, e saber disso evita que
        um teto calculado para a velocidade normal pareça generoso demais.
        """
        if not self._usada_em:
            return False
        return (time.time() - self._usada_em) <= SPEED_DURACAO_SEGUNDOS

    @property
    def multiplicador(self) -> float:
        """1.3 enquanto ativa, 1.0 fora. O jogo dá +30%."""
        return 1.3 if self.ativa else 1.0

    # -- acionamento -------------------------------------------------------

    def usar_se_puder(
        self,
        dentro_da_cave: bool,
        andando_desde: float | None = None,
    ) -> bool:
        """Tenta acionar. Devolve True somente se a tecla foi enviada.

        Chamado a cada volta do laço de deslocamento. Todas as condições são
        verificadas aqui, num lugar só -- espalhar essa decisão pelos estados da
        rotina foi o que fez outras habilidades serem acionadas no momento
        errado.
        """
        ctx = self.ctx
        if not self.habilitada or not dentro_da_cave:
            return False
        if self.segundos_de_recarga > 0.0:
            return False
        if self.ativa:
            return False

        # A skill afeta a montaria. A pé, a tecla é gasto puro: o efeito não
        # aparece e a recarga passa a contar.
        if not ctx.memory.is_mounted():
            return False

        if andando_desde is not None:
            if time.time() - andando_desde < SEGUNDOS_ANDANDO_ANTES:
                return False

        self._usada_em = time.time()
        self._tentativas += 1
        ctx.press(self.tecla)
        ctx.log.info(
            "Skill de velocidade acionada (+30%% por %ss; próxima em %s min)",
            SPEED_DURACAO_SEGUNDOS, SPEED_RECARGA_SEGUNDOS // 60,
        )
        return True

    def estado_para_log(self) -> str:
        if not self.habilitada:
            return "skill de velocidade: sem tecla configurada"
        if self.ativa:
            restante = SPEED_DURACAO_SEGUNDOS - (time.time() - self._usada_em)
            return f"skill de velocidade ATIVA (faltam {restante:.0f}s de efeito)"
        recarga = self.segundos_de_recarga
        if recarga > 0:
            return f"skill de velocidade em recarga ({recarga:.0f}s)"
        return "skill de velocidade disponível"
