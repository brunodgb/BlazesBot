"""A MONTAGEM DO TIME DO APP -- o líder convida, os seguidores aceitam.

Saiu para módulo próprio, e não para dentro do `supervisor.py`, pelo mesmo
motivo que `bot/fada_montagem.py` saiu: o supervisor é DESPACHANTE, e isto é
lógica -- fila, rotação, teto de tentativas. A catraca de tamanho já tinha
avisado uma vez.

=========================================================================
QUEM DECIDE É SÓ O LÍDER
=========================================================================

Decisão do usuário em 15/09/2026, e ela vem de uma mecânica do jogo que ele
mediu:

    *"Se apenas 1 seguidor cair não tem porque se preocupar, pois se o resto do
    time está online, quando o seguidor voltar ele JÁ VOLTA EM TIME. Por isso é
    melhor o líder verificar: se ele identificar que não tem time, ele manda já
    para todos. Os seguidores, caso voltem e estejam sem time, não devem fazer
    nada, apenas ficar rodando APP normalmente."*

Então: seguidor NUNCA monta time. Ele só aceita o que o líder mandar.

=========================================================================
E O LÍDER NÃO CONVIDA ÀS CEGAS
=========================================================================

*"É bom identificar se o líder está online, se os seguidores estão online, para
também não mandar time cegamente, pois se algum seguidor estiver off não vai dar
para enviar o convite de time."*

Quem responde isso é `mural.estado_da_conta(login)`, publicada uma vez por volta
por cada conta em modo APP (ver `supervisor.antes_de_cada_volta`). Conta que
parou de publicar some em 30 s e deixa de gastar ciclo de montagem.

=========================================================================
A FILA, A ROTAÇÃO E O TETO
=========================================================================

*"Você vai tentando e rotacionando; o ideal é não ficar muito tempo parado, mas
vai tentando novos aliados até conseguir adicionar todos. Caso sobre só 1, vai
tentando ele até conseguir, com limite de 4 tentativas por vez -- daí tenta na
próxima macro."*

Uma rodada = uma passada pela fila de quem falta. Quem não aceitou volta para o
fim da fila. Ao fim de `TENTATIVAS_POR_MEMBRO` passadas, a montagem encerra e o
resto fica para o ciclo seguinte -- o líder não fica parado por causa de uma
conta que pode estar deslogada.

=========================================================================
O CAMINHO DO CONVITE É O QUE JÁ RODA NO BC
=========================================================================

`TeamService._enviar_convite(nick)` limpa a Block list, registra o nick, clica
com o botão direito na PRIMEIRA linha e clica em "Team up". Como a lista é
limpa antes, o alvo é sempre a linha 1 -- não existe (nem precisa existir)
código que distinga linhas.

É por isso que o convite sai UM POR VEZ, e não os quatro de uma vez: decisão do
usuário em 15/09/2026, *"ser um por um deixando um pouco mais lento não tem
problema"*. Reconhecer qual linha é de quem exigiria template por nick, e errar
de linha convida a pessoa errada.
"""

from __future__ import annotations

import time

from . import mural
from .context import BotContext
from .team import ESPERA_PELA_RESPOSTA, PASSO_DA_ESPERA_DO_TIME, TeamService

__all__ = ["ATIVADO", "SEGUNDOS_ENTRE_CONFERENCIAS", "TENTATIVAS_POR_MEMBRO",
           "falta_alguem", "montar_o_time", "montar_se_for_a_hora"]

# ===========================================================================
# INTERRUPTOR
# ===========================================================================
#
# `False` = o líder não monta time nenhum, e o modo APP roda como rodava antes
# de 16/09/2026 (com o time montado à mão pelo usuário).
ATIVADO = True

# Passadas pela fila antes de desistir NESTA montagem.
#
# O número é do usuário: *"com limite de 4 tentativas por vez, daí tenta na
# próxima macro"*. Não é afinação -- é o que separa "insistir" de "ficar parado
# por causa de uma conta deslogada".
TENTATIVAS_POR_MEMBRO = 4

# De quanto em quanto tempo o líder confere se o time está completo.
#
# NÃO É AFINAÇÃO, é a natureza do evento: o time só se desfaz quando TODOS caem
# (o jogo recoloca no time quem volta enquanto alguém ficou). Isso é raro, e
# perguntar mais que isso seria abrir uma leitura por nada -- ainda que a
# leitura em si seja de memória.
#
# A conferência é barata; a MONTAGEM é que custa (Block list aberta, digitação,
# cliques), e ela só acontece quando falta alguém de verdade.
SEGUNDOS_ENTRE_CONFERENCIAS = 60.0


def _nicks_no_time(memoria) -> list[str] | None:
    """Os nicks que o JOGO diz estarem no time. `None` = não deu para ler.

    `time_do_jogo()` inclui o próprio personagem e devolve na ordem do painel --
    ver `core/memory.py`. Aqui só interessa o conjunto.
    """
    try:
        nomes = memoria.time_do_jogo()
    except Exception:
        return None
    if nomes is None:
        return None
    return [(n or "").strip().lower() for n in nomes if (n or "").strip()]


def falta_alguem(sup, memoria) -> list[str] | None:
    """Os LOGINS esperados que ainda não estão no time. `None` = não sei.

    "NÃO SEI" NÃO MONTA NADA. Sem leitura do time, convidar seria convidar quem
    talvez já esteja dentro -- e cada convite custa a Block list aberta no meio
    da macro.
    """
    presentes = _nicks_no_time(memoria)
    if presentes is None:
        return None

    faltam: list[str] = []
    for login in sup._membros_do_time():
        if login == sup.account.login:
            continue                      # o líder é ele mesmo
        nick = (sup._nick_do_login(login) or "").strip()
        if not nick:
            # SEM NICK NÃO HÁ LINHA PARA ADICIONAR na Block list. Só acontece
            # com conta que nunca logou pelo bot -- o usuário confirmou que na
            # prática sempre há registro, porque logar uma vez basta.
            sup.log.info("Time do APP: '%s' ainda não tem personagem conhecido "
                         "(nunca logou por aqui); não dá para convidar.", login)
            continue
        if nick.lower() not in presentes:
            faltam.append(login)
    return faltam


def _esta_de_pe(login: str) -> bool:
    """A conta publicou sinal de vida nos últimos segundos?"""
    return mural.estado_da_conta(login) is not None


def _convidar(team: TeamService, sup, login: str, nick: str, remetente: str,
              memoria) -> bool:
    """Um convite e a espera pela resposta. `True` = entrou no time.

    A ESPERA TEM DUAS SAÍDAS, e a segunda é a que funciona sem leitura: o
    tamanho do time pela memória, e o aceite ANUNCIADO pela outra ponta. As duas
    contas rodam neste processo, então quem aceitou avisa -- é o mesmo mecanismo
    que o BC usa desde que o convite deixou de ser por texto.
    """
    mural.consumir_aceite(remetente)      # descarta aceite de rodada anterior
    mural.anunciar_convite(nick, remetente)
    if not team._enviar_convite(nick):
        sup.log.warning("Time do APP: não consegui enviar o convite para '%s'.",
                        nick)
        return False

    limite = time.time() + ESPERA_PELA_RESPOSTA
    while time.time() < limite:
        if sup.stop_event.is_set():
            return False
        try:
            tamanho = memoria.tamanho_do_time()
        except Exception:
            tamanho = None
        presentes = _nicks_no_time(memoria)
        if presentes is not None and nick.lower() in presentes:
            sup.log.info("Time do APP: '%s' entrou (time com %s).", nick,
                         tamanho if tamanho is not None else "?")
            mural.consumir_aceite(remetente)
            return True
        if mural.aceite_pendente(remetente) is not None:
            sup.log.info("Time do APP: '%s' avisou que aceitou.", nick)
            mural.consumir_aceite(remetente)
            return True
        time.sleep(PASSO_DA_ESPERA_DO_TIME)

    sup.log.warning("Time do APP: '%s' não aceitou em %.0fs.", nick,
                    ESPERA_PELA_RESPOSTA)
    return False


def montar_o_time(sup, memoria) -> bool:
    """O líder convida quem falta. `True` = mexeu em alguma coisa.

    NUNCA LEVANTA: quem chama está no meio de um farm de horas, e uma montagem
    que derruba a sessão é pior que um time que não se formou.
    """
    if not ATIVADO:
        return False
    # SÓ O LÍDER. `_dono_da_macro` devolve o líder quando esta conta é seguidora.
    if sup._dono_da_macro().login != sup.account.login:
        return False
    if memoria is None:
        return False

    faltam = falta_alguem(sup, memoria)
    if not faltam:
        return False

    fila = [x for x in faltam if _esta_de_pe(x)]
    fora = [x for x in faltam if x not in fila]
    if fora:
        sup.log.info("Time do APP: %s sem sinal de vida agora; fica para o "
                     "próximo ciclo.", ", ".join(fora))
    if not fila:
        return False

    remetente = (sup.account.last_char_name or sup.account.login).strip()
    sup.log.info("Time do APP: faltam %s no time. Convidando um por vez.",
                 ", ".join(fila))

    ctx = BotContext(
        config=sup.config, account=sup.account,
        pid=sup.pid, hwnd=sup.hwnd,
        stop_event=sup.stop_event, pause_event=sup.pause_event)
    entrou_alguem = False
    try:
        team = TeamService(ctx)
        for _ in range(TENTATIVAS_POR_MEMBRO):
            if not fila or sup.stop_event.is_set():
                break
            # ROTAÇÃO: quem não aceita volta para o fim, e o próximo é tentado
            # antes de insistir no mesmo. Com um só na fila, isso vira a
            # insistência que o usuário pediu.
            restantes: list[str] = []
            for login in fila:
                if sup.stop_event.is_set():
                    break
                nick = (sup._nick_do_login(login) or "").strip()
                if _convidar(team, sup, login, nick, remetente, memoria):
                    entrou_alguem = True
                else:
                    restantes.append(login)
            fila = restantes
        if fila:
            sup.log.warning(
                "Time do APP: %s não entraram em %s passada(s). Volto a tentar "
                "no próximo ciclo.", ", ".join(fila), TENTATIVAS_POR_MEMBRO)
    except Exception as exc:
        sup.log.warning("Time do APP: a montagem falhou (o APP segue): %s", exc)
    finally:
        ctx.close()
    return entrou_alguem


def montar_se_for_a_hora(sup, memoria, em_batalha: bool | None) -> bool:
    """A porta do laço: cadência + fora de batalha. `True` = mexeu em algo.

    EM BATALHA NÃO SE MONTA TIME. Abrir a Block list com mob batendo é o
    personagem parado apanhando -- a mesma regra que já vale para pet, comida,
    caminhada e bolsa. "Não sei" (`None`) conta como fora: sem leitura, o
    comportamento cego é o de sempre.

    NO ARRANQUE DO APP a cadência está zerada, então a primeira chamada passa
    direto. Foi o que o usuário pediu em 16/09/2026: *"quando eu iniciar o APP e
    for um líder, tem que verificar também se está em time, pois às vezes eu
    posso abrir o BlazesBot depois de estar com as contas logadas"*.
    """
    if em_batalha is True:
        return False
    agora = time.monotonic()
    if agora < getattr(sup, "_proxima_conferencia_do_time", 0.0):
        return False
    sup._proxima_conferencia_do_time = agora + SEGUNDOS_ENTRE_CONFERENCIAS
    return montar_o_time(sup, memoria)
