"""O PORTÃO DO RESETER: segura a entrada da cave enquanto ele não está no ar.

===========================================================================
DEPENDÊNCIA CRUZADA -- LEIA ANTES DE MEXER
===========================================================================

Este módulo NASCEU NO BC, como `BossRushRoutine._esperar_o_reseter`, e subiu
para `bot/` em 08/09/2026 quando a HH passou a precisar da mesma trava.

  * QUEM USA: `bc/routine.py` (no `_do_entrar`, antes do convite) e
    `hh/routine.py` (no `_garantir_o_time`, antes do convite). Mexer aqui mexe
    nas duas caves.
  * DE ONDE VEIO: `bc/routine.py`. As constantes de cadência vinham de lá e
    vieram inteiras -- o `docs/TEMPOS.md` mostra os dois nomes neste arquivo.
  * O QUE **NÃO** SUBIU, E POR QUÊ: **onde** a trava fica. Cada cave tem um
    ponto de não-retorno diferente (a BC trava depois de conquistar a
    coordenada de entrada; a HH, no portão do time) e essa é decisão de cave --
    ver `docs/INVARIANTES.md`, "Decisão de cave NÃO mora em código
    compartilhado". Este módulo responde "posso entrar?"; QUANDO perguntar é de
    quem chama.
  * MORA EM `bot/` E NÃO EM `core/` porque recebe `BotContext`. O critério é o
    que o módulo IMPORTA, não o quanto ele parece genérico.

===========================================================================
POR QUE ESPERAR É MELHOR QUE ENTRAR
===========================================================================

Sem trocar de time o boss NÃO RENASCE: a instância continua com ele morto e a
run inteira é perdida -- depois de já ter gasto o teleporte, a travessia e a
disputa da entrada. Entrar sem reseter não é "entrar mais devagar", é jogar
fora tudo que veio antes. Esperar, por pior que pareça, é sempre mais barato.

Quem preencheu o `reset_nick` já declarou isso. Por isso não existe um
interruptor separado para a trava: o campo em branco continua sendo o jeito de
dizer "não uso reset de time".

===========================================================================
"CAIU" E "NÃO EXISTE MAIS" SÃO ESTADOS DIFERENTES
===========================================================================

Caiu é temporário por natureza: relogin é o comportamento padrão de toda conta,
então ela volta sozinha e a espera tem fim. Já um reseter removido, desativado,
desmarcado, posto para farmar ou aposentado por senha errada NÃO VOLTA --
esperar por ele seria uma conta parada a noite inteira sem nada acontecendo.

Por isso a condição é reavaliada a cada volta e não só na entrada:
`problema_do_reset` lê a configuração VIVA, e a configuração pode mudar com o
bot rodando. Quando ela responde, o desfecho é o mesmo da venda sem tecla de
retorno -- desliga o farm DESTA cave nesta conta e salva, o checkbox desmarca
na interface, e isso É o aviso.

===========================================================================
A ESPERA NÃO CONGELA NADA
===========================================================================

É `ctx.tick`, nunca `time.sleep`, e a diferença é grande:

  * cada conta roda na THREAD DELA (`AccountSupervisor`), então nenhuma espera
    aqui toca a thread da interface (a webview);
  * é o `tick` que mantém o WATCHDOG desta conta vivo enquanto ela está parada
    (uma conta de cave também cai, e parada por horas ela ficaria cega para a
    própria queda);
  * é ele que dá as três saídas de graça -- Parar, desmarcar o farm da cave
    (`FarmDesligado`) e ligar o modo APP.
"""
from __future__ import annotations

import time

from ..core.quedas import frase_do_tempo
from .context import BotContext
from .mural import reseter_online, silencio_do_reseter

# Cadência da espera pela conta de reset.
#
# NÚMERO DERIVADO, não medido: quem responde é uma leitura de dicionário em
# memória, então o custo de perguntar é zero e o passo poderia ser bem menor. Um
# segundo é o suficiente porque a trava dura minutos (um relogin inteiro), não
# milissegundos -- e é `ctx.tick`, então o Parar continua sendo instantâneo.
PASSO_DA_ESPERA_DO_RESETER = 1.0

# De quanto em quanto tempo repetir o aviso enquanto a trava dura.
#
# NÚMERO COSMÉTICO, sem medição atrás. Existe porque uma linha escrita quarenta
# minutos atrás não avisa ninguém: quem olha a tela no meio da trava precisa ver
# por que a conta está parada sem ter que rolar o log para trás.
INTERVALO_DO_AVISO_DO_RESETER = 300.0


def esperar_o_reseter(ctx: BotContext, onde: str) -> None:
    """Bloqueia até a conta de reset estar em condição de aceitar o convite.

    `onde` é só para o log -- é o lugar em que a conta está parada ("na porta da
    cave", "no portão do time"), e é o que faz a linha de aviso dizer algo para
    quem olha a tela no meio da trava.

    Volta sem fazer nada quando esta conta não usa reset (campo em branco), e
    volta DESLIGANDO o farm da cave quando o reseter não existe mais.
    """
    nick = ctx.settings.reset_nick.strip()
    if not nick:
        return                                  # esta conta não usa reset

    comecou = time.time()
    proximo_aviso = 0.0
    while True:
        ctx.raise_if_stopped()

        # Config VIVA: o reseter pode ter sido desmarcado, desativado ou
        # posto para farmar depois que a trava começou.
        problema = ctx.config.problema_do_reset(ctx.account)
        if problema is not None:
            cave = ctx.desligar_o_farm_desta_cave()
            try:
                ctx.config.save()
            except Exception as exc:
                ctx.log.warning("Não consegui salvar a configuração: %s", exc)
            ctx.log.error(
                "Farm de %s DESLIGADO nesta conta: %s. A conta continua "
                "online e relogando; remarque o farm depois de corrigir o "
                "reset de time.", cave.upper() or "cave", problema,
            )
            # O interruptor acabou de virar False: o próprio
            # `raise_if_stopped` levanta `FarmDesligado` e devolve a conta ao
            # estado "online".
            ctx.raise_if_stopped()
            return

        if reseter_online(nick):
            if proximo_aviso:                   # só loga se chegou a travar
                ctx.log.info(
                    "A conta de reset '%s' voltou. Parado %s esperando "
                    "por ela.", nick, frase_do_tempo(time.time() - comecou),
                )
            return

        agora = time.time()
        if agora >= proximo_aviso:
            proximo_aviso = agora + INTERVALO_DO_AVISO_DO_RESETER
            silencio = silencio_do_reseter(nick)
            ctx.log.warning(
                "Parado %s: a conta de reset '%s' não está no ar (%s). Sem "
                "ela o boss não renasce, então não entro. Volto sozinho "
                "quando ela reconectar — parado há %s.",
                onde, nick,
                "nunca subiu nesta execução" if silencio is None
                else f"sem responder há {silencio:.0f}s",
                frase_do_tempo(agora - comecou),
            )
        ctx.tick(PASSO_DA_ESPERA_DO_RESETER)
