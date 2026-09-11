"""O ORQUESTRADOR DA ESPERA: aja, PERGUNTE, siga no instante da resposta.

=========================================================================
POR QUE ISTO EXISTE -- E POR QUE NÃO É UM FRAMEWORK NOVO
=========================================================================

O projeto já tinha a forma certa em quatro lugares diferentes:

    UIDoJogo.esperar_a_chegada .......... troca de mapa, pergunta a posição
    UIDoJogo._esperar_o_dialogo ......... o diálogo do NPC, teto adaptativo
    rajada_de_npc.clicar_ate_abrir ...... clica, pergunta, para quando abre
    Memory._esperar_o_termometro ........ escreve, espera o campo MEXER

Quatro implementações da MESMA ideia, cada uma com o seu laço, o seu
`time.time()`, o seu teto e o seu jeito de dizer "desisti". Isso é o que este
módulo termina: **uma** peça com o laço, o teto, o passo, o Parar e a
telemetria, e as quatro passando a declarar só o que é delas -- a pergunta.

**NÃO É UM AGENDADOR, NÃO É UMA MÁQUINA DE ESTADOS.** As máquinas de estado do
bot continuam onde estão (`bc/routine.py`, `hh/routine.py`, `app/executor.py`).
O que sobe para cá é a espera -- o pedaço que estava espalhado e que, quando é
cego, é onde o relógio come o APM.

=========================================================================
A REGRA QUE ISTO IMPÕE: TEMPO É TETO, NUNCA GASTO
=========================================================================

*"Onde havia espera cega, agora se PERGUNTA (confira o efeito, saia no
instante). Teto vira aviso, não gasto fixo."* -- `CLAUDE.md`.

Aqui isso vira assinatura de função. Não existe `ate(...)` sem `pergunta`: quem
não tem o que perguntar não usa este módulo -- usa `ctx.tick`, e assume por
escrito que está esperando cego.

=========================================================================
AS TRÊS RESPOSTAS DA PERGUNTA, E POR QUE SÃO TRÊS
=========================================================================

    True  -- a condição aconteceu; segue AGORA
    False -- ainda não; pergunta de novo depois de `passo`
    None  -- NÃO DÁ PARA SABER (sem captura, sem template, memória ilegível)

`None` não é "não aconteceu", e tratar os dois igual é um defeito que este
projeto já pagou duas vezes: o cliente minimizado devolve quadro preto, nenhum
template casa, e uma espera que lesse isso como "não" ficaria até o teto em
TODA volta. Quem recebe `None` decide -- normalmente seguindo, porque insistir
na leitura não faz a captura voltar a funcionar.

=========================================================================
A TELEMETRIA VEM DE GRAÇA, E É O PONTO
=========================================================================

Toda espera que passa por aqui é cronometrada (`espera.<o_que>`) e CONTADA POR
DESFECHO (`cronometro.marcar`). Sem isso, "quanto tempo o bot passa esperando"
continuaria sendo uma pergunta que só se responde contando string em prosa no
log -- que foi como a auditoria de 10/09/2026 teve que descobrir as 61.928
tentativas de entrada que estouraram o teto.

Com isso, `python -m blazesbot.core.relatorio_de_latencia` passa a responder,
por espera: quantas confirmaram, quantas morreram no teto, e o que cada uma
custou.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from . import cronometro

# Os motivos de uma espera terminar. São chave de contador -- curtos e fixos.
CONFIRMADO = "confirmado"
TETO = "teto"
VOLTAS = "voltas"
NAO_SEI = "nao_sei"


@dataclass(frozen=True)
class Desfecho:
    """Como a espera terminou, quanto custou e em quantas voltas.

    `bool(desfecho)` é `True` só quando a condição foi CONFIRMADA -- `None` e
    teto são ambos falsos aqui, e quem precisa distinguir lê `motivo`.
    """

    confirmado: bool | None
    motivo: str
    voltas: int
    segundos: float

    def __bool__(self) -> bool:
        return self.confirmado is True

    @property
    def ms(self) -> float:
        return self.segundos * 1000


def ate(
    pergunta: Callable[[], bool | None],
    *,
    ctx,
    teto: float | None,
    passo: float,
    o_que: str,
    agir: Callable[[], None] | None = None,
    voltas_maximas: int | None = None,
) -> Desfecho:
    """Repete [ação e] pergunta até a resposta, o teto de tempo ou o de voltas.

    A ORDEM DENTRO DA VOLTA É AÇÃO -> PERGUNTA, e não o contrário: perguntar
    antes de agir responderia sobre a tela de antes. Sem `agir`, a primeira
    pergunta acontece ANTES de qualquer espera -- é o que permite confirmar em
    zero milissegundo, e nove em dez entradas na HH confirmam assim.

    `voltas_maximas` é o teto em AÇÕES, para quem conta cliques em vez de
    segundos (a rajada de NPC). Vale junto com `teto`: o primeiro que estourar
    encerra, e `teto=None` diz que quem limita são as voltas. **Um dos dois é
    obrigatório** -- espera sem teto nenhum é laço infinito com outro nome.

    O PASSO NUNCA PASSA DO QUE FALTA para o teto: dormir o passo inteiro na
    última volta é o jeito clássico de um teto de 0,12 s custar 0,16 s.
    """
    if teto is None and voltas_maximas is None:
        raise ValueError(
            f"espera.ate({o_que!r}) sem teto: passe `teto` ou `voltas_maximas`")
    comeco = time.time()
    limite = comeco + teto if teto is not None else None
    voltas = 0
    motivo = TETO
    confirmado: bool | None = False

    while True:
        ctx.raise_if_stopped()
        if agir is not None:
            agir()
        voltas += 1

        resposta = pergunta()
        if resposta is True:
            confirmado, motivo = True, CONFIRMADO
            break
        if resposta is None:
            confirmado, motivo = None, NAO_SEI
            break
        if voltas_maximas is not None and voltas >= voltas_maximas:
            motivo = VOLTAS
            break
        if limite is None:
            ctx.tick(passo)
            continue
        restante = limite - time.time()
        if restante <= 0:
            break
        ctx.tick(min(passo, restante))

    gasto = time.time() - comeco
    cronometro.anotar(f"espera.{o_que}", gasto)
    cronometro.marcar(f"espera.{o_que}", motivo)
    return Desfecho(confirmado=confirmado, motivo=motivo, voltas=voltas,
                    segundos=gasto)


__all__ = ["CONFIRMADO", "NAO_SEI", "TETO", "VOLTAS", "Desfecho", "ate"]
