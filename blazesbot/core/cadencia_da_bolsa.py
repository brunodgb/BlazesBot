"""QUANDO LIMPAR A BOLSA -- e o diagnóstico de por que ela repete.

Saiu de `bot/app/executor.py` em 05/09/2026 para caber o diagnóstico: aquele arquivo
está no teto da catraca de tamanho, e a decisão "é hora de limpar?" é uma
política com nome próprio, não um detalhe do laço.

Mora no `core/` e não no `bot/app/` porque o executor só pode importar `core/`
(`tests/test_ecossistemas.py`) -- e ele não perde nada com isso: aqui não há
uma linha que saiba o que é bolsa, inventário ou macro. É contagem e log.

=======================================================================
O DEFEITO QUE ESTE ARQUIVO EXISTE PARA EXPOR
=======================================================================

Relato do usuário: *"tem vezes que o APP está bugando, começa a abrir e fechar
várias vezes o inventário, e no meio tempo ficar dando TAB sem começar nenhuma
macro."*

A régua é `voltas % a_cada == 0`, e ela é conferida no PRELÚDIO de cada volta.
Isso só funciona enquanto `voltas` anda. Quando a volta é cortada antes do fim,
o contador de voltas COMPLETAS não sobe -- e o resto continua zero na volta
seguinte, e na seguinte, e na seguinte. A cadência deixa de ser "a cada N
voltas" e vira "enquanto o contador não andar".

Medido no log de 05/09/2026: `gamerblazes` fez 622 limpezas, **595 delas
repetindo o mesmo número de volta**, com uma rajada de **275 limpezas
consecutivas na volta 150** -- três em cada quatro apagando ZERO itens.

ESTE ARQUIVO NÃO CONSERTA ISSO. A régua continua exatamente a que era; o que
entra é a instrumentação que nomeia a causa na hora em que ela acontece, para a
correção ser escolhida com número na mão e não por palpite.
"""

from __future__ import annotations

import time

# Interruptor do piso do conserto -- 06/09/2026.
#
# `True`: a mesma volta não abre a bolsa duas vezes. `False` devolve o
# comportamento antigo (só o diagnóstico), e existe para quem for medir a causa
# de novo poder ver a rajada acontecer. Ver `docs/decisoes/bolsa-repetindo.md`.
NAO_LIMPAR_DUAS_VEZES_NA_MESMA_VOLTA = True


class CadenciaDaBolsa:
    """Decide se é hora de limpar a bolsa, e denuncia quando se repete."""

    def __init__(self, log) -> None:
        self.log = log
        # Estado da ÚLTIMA limpeza autorizada. Serve só para o diagnóstico --
        # a decisão em si continua sendo o resto da divisão.
        self._ultima_volta: int | None = None
        self._ultimas_abortadas: int = 0
        self._quando: float = 0.0
        self._repeticoes: int = 0

    def deve_limpar(self, *, voltas: int, abortadas: int, a_cada: int,
                    motivo_do_corte: str) -> bool:
        """`True` = limpe agora. A régua é a de sempre: `voltas % a_cada == 0`.

        `motivo_do_corte` é como a volta ANTERIOR terminou. É o dado que faltava
        no log: ele diz por que o contador de voltas completas não andou.
        """
        if a_cada <= 0 or voltas == 0 or voltas % a_cada:
            return False

        agora = time.monotonic()
        repetida = self._ultima_volta == voltas
        if repetida and NAO_LIMPAR_DUAS_VEZES_NA_MESMA_VOLTA:
            # A MESMA VOLTA NÃO LIMPA DUAS VEZES -- 06/09/2026.
            #
            # É o piso do conserto, e ele NÃO resolve a causa: o contador
            # continua congelando quando a volta é cortada (401 dos 407 avisos
            # mediam `sem alvo`). O que ele resolve é o dano visível -- a bolsa
            # abrindo e fechando em rajada, até 275 vezes seguidas na mesma
            # volta -- sem mexer na semântica que o usuário configurou na tela
            # ("a cada N voltas").
            #
            # O aviso continua saindo, e é ele que segue medindo a causa.
            self._repeticoes += 1
            self.log.warning(
                "BOLSA/DIAGNÓSTICO: a volta %d já foi limpa há %.1fs e o "
                "contador não andou (%dª vez). NÃO abro a bolsa de novo. "
                "Abortadas subiram %d; último corte: %s.",
                voltas, agora - self._quando, self._repeticoes,
                abortadas - self._ultimas_abortadas, motivo_do_corte)
            self._ultimas_abortadas = abortadas
            return False
        if repetida:
            self._repeticoes += 1
            self.log.warning(
                "BOLSA/DIAGNÓSTICO: %dª limpeza seguida na MESMA volta %d "
                "(%.1fs desde a anterior). Voltas completas NÃO andaram; "
                "abortadas subiram %d no intervalo. Último corte: %s. "
                "A cadência 'a cada %d voltas' está presa no resto zero.",
                self._repeticoes + 1, voltas, agora - self._quando,
                abortadas - self._ultimas_abortadas, motivo_do_corte, a_cada)
        else:
            self._repeticoes = 0
            self.log.info(
                "Volta %s: hora de limpar a bolsa (a cada %s voltas) "
                "[abortadas até aqui: %s | último corte: %s]",
                voltas, a_cada, abortadas, motivo_do_corte)

        self._ultima_volta = voltas
        self._ultimas_abortadas = abortadas
        self._quando = agora
        return True
