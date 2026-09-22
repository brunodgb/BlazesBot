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
from .team import (
    ESPERA_PELA_RESPOSTA,
    PASSO_DA_ESPERA_DO_TIME,
    InviteAcceptor,
    TeamService,
)

__all__ = [
    "ATIVADO",
    "CADENCIA_DAS_CONFERENCIAS",
    "TENTATIVAS_POR_MEMBRO",
    "aceitador_do_seguidor",
    "ancora_do_lider",
    "esperar_o_lider_montar",
    "falta_alguem",
    "montar_o_time",
    "montar_se_for_a_hora",
    "pick_mode_free",
    "publicar_a_ancora",
    "publicar_que_estou_de_pe",
]

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
CADENCIA_DAS_CONFERENCIAS = 60.0


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
    """A conta publicou sinal de vida nos últimos segundos?

    DOIS CANAIS, porque são DOIS LAÇOS. A macro do APP publica `estado` a cada
    volta (`supervisor.antes_de_cada_volta`); a FADA nunca passa por lá -- ela
    bate no canal dela (`mural.bater_fada`), de dentro do laço de cura. Olhar só
    o primeiro fazia a Fada ser eternamente pulada.

    MEDIDO em 19/09/2026: quatro ciclos seguidos de *"mfaustoapp069 sem sinal de
    vida agora; fica para o próximo ciclo"* com ela rodando -- e, do lado dela,
    *"WizzOfBlazes5 não está no meu painel de time -- esperando ele aparecer"*.
    As duas contas se esperando, cada uma achando que a outra sumiu.
    """
    return (mural.estado_da_conta(login) is not None
            or mural.fada_de_pe(login))


def publicar_que_estou_de_pe(sup, memoria) -> None:
    """O sinal de vida desta conta, com o máximo de vida junto.

    O MÁXIMO VAI SEMPRE, porque `publicar_estado` SUBSTITUI o estado inteiro e
    a Fada lê a porcentagem dele -- publicar só o nick apagaria o número que ela
    precisa. Travas em `tests/test_sinal_de_vida_do_app.py`.
    """
    try:
        max_hp = memoria.max_hp() if memoria is not None else None
    except Exception:
        max_hp = None
    mural.publicar_estado(sup.account.login, max_hp=max_hp,
                          nick=(sup.account.last_char_name or "").strip())


def _convidar(team: TeamService, sup, login: str, nick: str, remetente: str,
              memoria) -> bool:
    """Um convite e a espera pela resposta. `True` = entrou no time.

    A ESPERA TEM DUAS SAÍDAS, e a segunda é a que funciona sem leitura: o
    tamanho do time pela memória, e o aceite ANUNCIADO pela outra ponta. As duas
    contas rodam neste processo, então quem aceitou avisa -- é o mesmo mecanismo
    que o BC usa desde que o convite deixou de ser por texto.
    """
    mural.consumir_aceite(remetente)      # descarta aceite de rodada anterior
    if not team._enviar_convite(nick):
        sup.log.warning("Time do APP: não consegui enviar o convite para '%s'.",
                        nick)
        return False
    # O ANÚNCIO SAI DEPOIS DO CLIQUE -- 19/09/2026.
    #
    # Antes ele saía antes, e `_enviar_convite` leva de 4 a 5 s (limpa a Block
    # list, registra o nick, abre o menu de contexto, clica em 'Team up').
    # Nesse intervalo o convidado já estava procurando uma caixa que ainda não
    # existia -- e o aceitador, que exige prova, recusava com razão. Medido:
    # anúncio às 13:11:57.7, "sem prova de caixa na tela" 58 ms depois, clique
    # no 'Team up' só às 13:12:02.3.
    mural.anunciar_convite(nick, remetente)

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


def _fila_de_convite(sup, faltam, avisados: set[str]) -> list[str]:
    """Dos que faltam, quem dá para convidar AGORA (tem sinal de vida).

    `avisados` guarda quem já foi registrado como ausente NESTA montagem: a fila
    é refeita a cada passada, e sem isso a mesma linha sairia quatro vezes.
    """
    fila = [x for x in (faltam or []) if _esta_de_pe(x)]
    fora = [x for x in (faltam or []) if x not in fila and x not in avisados]
    if fora:
        avisados.update(fora)
        sup.log.info("Time do APP: %s sem sinal de vida agora; fica para o "
                     "próximo ciclo.", ", ".join(fora))
    return fila


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

    avisados: set[str] = set()        # quem já foi registrado como ausente
    fila = _fila_de_convite(sup, faltam, avisados)
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
    # Quem ACEITOU nesta montagem. Fica de fora da fila refeita: o aceite pode
    # chegar pelo anúncio da outra ponta antes de o jogo mostrar o time, e sem
    # isto o líder mandaria um segundo convite para quem já entrou.
    entraram: set[str] = set()
    try:
        team = TeamService(ctx)
        for _ in range(TENTATIVAS_POR_MEMBRO):
            if not fila or sup.stop_event.is_set():
                break
            # ROTAÇÃO: quem não aceita volta para o fim, e o próximo é tentado
            # antes de insistir no mesmo. Com um só na fila, isso vira a
            # insistência que o usuário pediu.
            for login in fila:
                if sup.stop_event.is_set():
                    break
                nick = (sup._nick_do_login(login) or "").strip()
                if _convidar(team, sup, login, nick, remetente, memoria):
                    entrou_alguem = True
                    entraram.add(login)
            # A FILA É REFEITA A CADA PASSADA -- 19/09/2026.
            #
            # Antes ela era calculada UMA vez, e quem não tinha sinal de vida
            # naquele instante ficava de fora da montagem inteira. Medido: no
            # arranque, o líder conferiu às 13:10:37.295 e o seguidor só
            # publicou 150 ms depois -- resultado, o time começou a macro com 2
            # de 3, e o terceiro só seria convidado 60 s depois.
            #
            # Refazendo, quem entrou sai sozinho (não está mais faltando) e quem
            # subiu no meio entra. É o que o usuário pediu: *"tem que enviar a
            # todos do time, que é entre 1 e 4 convites"*.
            faltam = [x for x in (falta_alguem(sup, memoria) or [])
                      if x not in entraram]
            fila = _fila_de_convite(sup, faltam, avisados)
        if fila:
            sup.log.warning(
                "Time do APP: %s não entraram em %s passada(s). Volto a tentar "
                "no próximo ciclo.", ", ".join(fila), TENTATIVAS_POR_MEMBRO)
        if entrou_alguem:
            # O PICK MODE É DO TIME, não da conta: ele some junto com o time, e
            # por isso é reaplicado quando o time se forma -- e só então.
            # Aplicar a cada conferência seria abrir um menu no meio da tela
            # sem motivo. Ver `pick_mode_free`.
            pick_mode_free(sup, ctx)
    except Exception as exc:
        sup.log.warning("Time do APP: a montagem falhou (o APP segue): %s", exc)
    finally:
        ctx.close()
    return entrou_alguem


def montar_se_for_a_hora(sup, memoria, em_batalha: bool | None,
                         *, no_arranque: bool = False) -> bool:
    """A porta do laço: cadência + fora de batalha. `True` = mexeu em algo.

    EM BATALHA NÃO SE MONTA TIME. Abrir a Block list com mob batendo é o
    personagem parado apanhando -- a mesma regra que já vale para pet, comida,
    caminhada e bolsa. "Não sei" (`None`) conta como fora: sem leitura, o
    comportamento cego é o de sempre.

    NO ARRANQUE DO APP A CADÊNCIA NÃO VALE (`no_arranque=True`). Foi o que o
    usuário pediu em 16/09/2026: *"quando eu iniciar o APP e for um líder, tem
    que verificar também se está em time"* -- e em 19/09 ele mostrou que não
    acontecia, porque o relógio da cadência é do SUPERVISOR e ele sobrevive ao
    ligar/desligar do modo APP. Medido no log do dia: religado 13 s depois de
    parar, nenhuma conferência; religado 2min35 depois, conferência 1,6 s
    após o arranque. Quem acabou de mexer no time religa em segundos.
    """
    if em_batalha is True:
        return False
    agora = time.monotonic()
    if not no_arranque and agora < getattr(sup, "_proxima_conferencia_do_time",
                                           0.0):
        return False
    sup._proxima_conferencia_do_time = agora + CADENCIA_DAS_CONFERENCIAS
    return montar_o_time(sup, memoria)


# ===========================================================================
# A ÂNCORA DO TIME — o ponto inicial do líder vale para todos
# ===========================================================================
#
# *"Se o modo for Team, o comportamento individual é anulado: o líder captura a
# coordenada inicial dele e compartilha, e todos sobrescrevem o próprio ponto"*
# (usuário, 22/09/2026).
#
# O PROBLEMA QUE ISSO RESOLVE não é estético. Cada conta guarda o SEU ponto
# inicial, e a trava de distância puxa cada uma para o seu: quem ligou o bot
# dois passos para o lado volta para dois passos para o lado. Sob ataque, isso é
# um time esticado -- a Fada fora do alcance da cura, o dano longe do mob que
# está batendo no vizinho.
#
# O CANAL É O MURAL, e não arquivo. As contas são THREADS DO MESMO PROCESSO
# (uma por conta, `supervisor-<login>`), e o mural já é a memória compartilhada
# delas, com tranca -- é por onde passam a largada, o sinal de vida, o id de
# cada um e o convite. Um `team_anchor.json` acrescentaria disco, leitura em
# laço e um arquivo velho para limpar, para transportar dois inteiros entre
# threads que enxergam o mesmo dicionário.
#
# QUEM PUBLICA É SÓ O LÍDER, E UMA VEZ SÓ (no arranque do modo APP). Publicar de
# novo durante o farm moveria a âncora do time inteiro para onde o líder estiver
# -- e ele anda, porque a macro anda.
#
# A ESPERA DO SEGUIDOR TEM TETO, e o teto é `ESPERA_PELA_RESPOSTA` (4 s), já
# medido. A defasagem real entre o arranque de duas contas é de ~0,9 s (medido
# no log de 19/09/2026), então o teto é quatro vezes a distância conhecida.
# Estourado, o seguidor usa o ponto dele: começar espalhado é ruim, não começar
# é pior.


def publicar_a_ancora(sup, base: tuple[int, int] | None) -> bool:
    """O líder publica o ponto inicial do time. `True` = publicou.

    Chamada UMA VEZ, no arranque do modo APP. Fora de time não publica nada:
    conta sozinha não tem com quem compartilhar âncora.
    """
    if not ATIVADO or base is None:
        return False
    if not sup._tem_time_do_app():
        return False
    if sup._dono_da_macro().login != sup.account.login:
        return False                      # seguidor não dita âncora
    mural.publicar_ancora(sup.account.login, base)
    sup.log.info("Âncora do time: ponto inicial %s publicado para o time "
                 "inteiro.", base)
    return True


def ancora_do_lider(sup, teto: float = ESPERA_PELA_RESPOSTA
                    ) -> tuple[int, int] | None:
    """O seguidor espera a âncora do líder. `None` = usa o ponto dele mesmo.

    É a TRAVA DE ESPERA do arranque: sem ela o seguidor montaria a trava de
    distância com a posição dele e só descobriria a do líder na volta seguinte
    -- ou nunca, porque a base só é lida uma vez.
    """
    if not ATIVADO:
        return None
    lider = sup._dono_da_macro()
    if lider.login == sup.account.login:
        return None                       # o líder é a fonte, não espera nada
    if not sup._tem_time_do_app():
        return None                       # solo segue exatamente como era

    limite = time.monotonic() + max(0.0, teto)
    avisou = False
    while True:
        ponto = mural.ancora_do_time(lider.login)
        if ponto is not None:
            sup.log.info("Âncora do time: uso o ponto inicial do líder '%s' "
                         "%s no lugar do meu.", lider.login, ponto)
            return ponto
        if sup.stop_event.is_set() or time.monotonic() >= limite:
            break
        if not avisou:
            avisou = True
            sup.log.info("Âncora do time: esperando o líder '%s' publicar o "
                         "ponto inicial (teto de %.0fs).", lider.login, teto)
        time.sleep(PASSO_DA_ESPERA_DO_TIME)

    sup.log.warning("Âncora do time: o líder '%s' não publicou ponto inicial "
                    "em %.0fs — sigo com o meu.", lider.login, teto)
    return None


def _o_lider_vai_rodar(sup, lider) -> bool:
    """O líder está ligado E com o APP como função ativa?

    Esperar por um líder que não vai rodar é ficar parado para sempre -- e é o
    caso normal de quem liga uma conta sozinha para testar.
    """
    try:
        return (bool(getattr(lider, "enabled", False))
                and sup.config.funcao_ativa_da_conta(lider) == "app")
    except Exception:
        return False


def esperar_o_lider_montar(sup, memoria, aceitar=None,
                           em_batalha: bool | None = None) -> bool:
    """O seguidor NÃO se mexe antes de o time estar de pé. `True` = entrou.

    *"Quando eu starto a função APP por um líder, a primeira coisa que deve ser
    vista, antes de executar qualquer outra coisa, de qualquer um se mexer, é
    verificar e montar o team"* -- usuário, 19/09/2026.

    Sem isto o seguidor larga na frente, e não por acaso: cada conta tem o seu
    supervisor, e as threads arrancam juntas. No log daquele dia a macro do
    seguidor começou 0,9 s ANTES de o líder sequer conferir o time.

    ELE SE PUBLICA ENQUANTO ESPERA, e essa linha não é enfeite: o líder só
    convida quem tem sinal de vida (`_esta_de_pe`), e quem está parado aqui
    ainda não rodou uma volta -- sem publicar, os dois se esperariam.

    O TETO É DERIVADO, não inventado: é o pior caso da montagem do líder
    (`ESPERA_PELA_RESPOSTA` x `TENTATIVAS_POR_MEMBRO` x membros). Estourado, a
    macro começa assim mesmo -- o convite continua sendo aceito lá dentro
    (`aceitador_do_seguidor`), e ficar parado esperando um líder que não vem é
    pior do que farmar sozinho.
    """
    if not ATIVADO or memoria is None:
        return False
    lider = sup._dono_da_macro()
    if lider.login == sup.account.login:
        return False                      # o líder não espera por si mesmo
    if em_batalha is True:
        # APANHANDO, NÃO. Ficar parado sob ataque é a única coisa pior que
        # começar antes do time -- e lá dentro o convite continua sendo aceito.
        return False
    if not _o_lider_vai_rodar(sup, lider):
        return False
    nick_do_lider = (sup._nick_do_login(lider.login) or "").strip().lower()
    if not nick_do_lider:
        return False

    membros = [x for x in sup._membros_do_time() if x != lider.login]
    teto = ESPERA_PELA_RESPOSTA * TENTATIVAS_POR_MEMBRO * max(1, len(membros))
    sup.log.info("Time do APP: espero o líder '%s' montar o time antes de "
                 "começar a macro (teto de %.0fs).", lider.login, teto)

    limite = time.monotonic() + teto
    while time.monotonic() < limite:
        if sup.stop_event.is_set():
            return False
        publicar_que_estou_de_pe(sup, memoria)
        presentes = _nicks_no_time(memoria)
        if presentes is not None and nick_do_lider in presentes:
            sup.log.info("Time do APP: estou no time do '%s' — começando a "
                         "macro.", lider.login)
            return True
        if aceitar is not None:
            aceitar()
        time.sleep(PASSO_DA_ESPERA_DO_TIME)

    sup.log.warning("Time do APP: o líder '%s' não me pôs no time em %.0fs — "
                    "começo a macro assim mesmo e sigo aceitando convite lá "
                    "dentro.", lider.login, teto)
    return False


def aceitador_do_seguidor(sup):
    """(aceitar, fechar) para o seguidor usar DENTRO da macro. `(None, None)`
    quando não dá para montar.

    =====================================================================
    POR QUE ISTO PRECISOU EXISTIR
    =====================================================================

    O `InviteAcceptor` já existe e é bom -- mas ele vive num ramo do laço do
    supervisor que o modo APP NUNCA alcança: quem entra em `_rodar_modo_app`
    dá `continue` antes, e fica lá por horas. Uma conta rodando macro nunca
    aceitaria convite nenhum.

    A CADÊNCIA É A DO EXECUTOR, e não a da volta: o líder espera
    `ESPERA_PELA_RESPOSTA` por cada convite, e uma volta de macro pode passar
    disso sozinha. Por isso a chamada entra na espera fatiada da linha, junto do
    socorro e do perímetro -- ver `executor._esperar`.

    `exigir_caixa=True` é o que separa isto do aceitador da conta de reset:
    nenhum clique esquerdo sai sem prova de que há caixa na tela.
    """
    try:
        ctx = BotContext(
            config=sup.config, account=sup.account,
            pid=sup.pid, hwnd=sup.hwnd,
            stop_event=sup.stop_event, pause_event=sup.pause_event)
    except Exception as exc:
        sup.log.warning("Time do APP: não consegui montar o aceitador (%s). "
                        "Convite de time não será aceito nesta sessão.", exc)
        return None, None

    # QUEM EU SOU -- sem isto o aceitador não aceita nada.
    #
    # `BotContext` nasce com `char_name = None`, e quem preenche é a sessão do
    # supervisor, no contexto DELA; este aqui é outro. O `InviteAcceptor`
    # reconhece o convite pelo anúncio interno (`convite_pendente(meu_nick)`), e
    # com o nick vazio o dicionário nunca bate: o caminho do anúncio -- o único
    # que funciona sem imagem -- nem começa.
    #
    # MEDIDO em 16/09/2026: o líder convidou 'WizzOfBlazes5' quatro vezes,
    # esperou 4 s por cada uma e desistiu; o seguidor estava na macro e não
    # clicou nenhuma. A caixa ficou na tela SEIS HORAS, até o aceitador do
    # supervisor pegá-la num religar do bot.
    #
    # O NOME CONFIRMADO NO LOGIN vem primeiro -- é o que a memória leu. O do
    # config é reserva, e é com ele que o líder anuncia.
    confirmado = getattr(getattr(sup, "_ctx_atual", None), "char_name", "")
    ctx.char_name = (confirmado or sup.account.last_char_name or "").strip()

    aceitador = InviteAcceptor(ctx, exigir_caixa=True)

    def aceitar() -> None:
        try:
            aceitador.check_and_accept()
        except Exception as exc:
            sup.log.debug("Time do APP: aceite falhou (%s).", exc)

    return aceitar, ctx.close


# ===========================================================================
# PICK MODE: FREE -- o submenu que só abre com o mouse por cima
# ===========================================================================
#
# *"O líder deve clicar com o botão direito em si, como é feito com o 'Leave the
# team', mas tem que passar o mouse em cima do 'Pick Mode:' (pois o clique fecha
# o menu) e selecionar a opção 'Free', pois por padrão vem como 'Dice', o que
# não é interessante para os APP."* -- usuário, 15/09/2026.
#
# *"Estar como Free é primordial, pois senão os itens que caírem dos mobs não
# vão ser recolhidos."*
#
# O CLIQUE FECHA, O HOVER ABRE -- medido pelo usuário na mão. O bot nunca move o
# cursor físico, então o hover é `WM_MOUSEMOVE` sintético
# (`Input.passar_o_mouse`), o mesmo movimento que `_prime_cursor` já mandava
# antes de cada clique. Se o cliente ignorar o movimento sintético para abrir
# submenu, não há atalho: sem submenu não há "Free", e o bot desiste e registra.
#
# COMO SE SABE QUE O SUBMENU ABRIU, sem template: ele não existe em disco --
# `menu_leave_team.png` e `menu_team_up.png` são carregados pelo código e também
# não existem, e é por isso que aquelas coordenadas medidas são o mecanismo de
# verdade. Aqui a prova é a REGIÃO MUDAR entre o quadro de antes e o de depois
# do hover (`vision.regiao_mudou`): uma caixa opaca aparecendo sobre a cena 3D
# muda a região inteira.
#
# SEM PROVA, NENHUM CLIQUE. Clicar às cegas no meio da tela é o pior lugar para
# isso -- e errar a linha do submenu selecionaria "Dice" ou "Teamlead".

# Onde fica "Pick Mode:" no menu do próprio personagem.
#
# MESMA COLUNA do "Leave the team" (`coords.menu_leave_team`, x=82) -- os dois
# são linhas do mesmo menu. A diferença é só a altura, e ela vem do print do
# usuário: "Leave the team" é a 2ª linha e "Pick Mode:" é a 4ª, 24 px abaixo.
DESLOCAMENTO_DO_PICK_MODE = (0, 24)

# Do item "Pick Mode:" para dentro do submenu.
#
# SÓ EM X, e isso não é economia: no print do usuário o submenu abre ALINHADO
# com a linha, e "Free" é o PRIMEIRO item -- na mesma altura do hover. Deduzir
# a altura do "Free" seria um segundo palpite, e errá-lo selecionaria "Dice".
# Mantendo o Y do hover, o único número medido é o quanto andar para a direita.
DESLOCAMENTO_DO_FREE = (150, 0)

# A região onde o submenu aparece, relativa ao ponto do hover.
# (dx, dy, largura, altura) -- cobre a caixa inteira com folga.
REGIAO_DO_SUBMENU = (100, -10, 110, 60)

# TETO da espera pelo menu e pelo submenu aparecerem. TETO, não gasto: quem
# espera PERGUNTA (`espera.ate`) e sai no instante em que a região muda.
TETO_DO_MENU = 0.8
PASSO_DO_MENU = 0.06

# Tentativas de abrir o submenu antes de desistir nesta montagem.
TENTATIVAS_DO_PICK_MODE = 2


def _ponto(base: tuple[int, int], desloc: tuple[int, int]) -> tuple[int, int]:
    return (base[0] + desloc[0], base[1] + desloc[1])


def pick_mode_free(sup, ctx) -> bool:
    """Põe o modo de pick do time em Free. `True` = cliquei no Free.

    NUNCA LEVANTA e nunca clica sem prova. Falhar aqui custa o loot dividido no
    dado; clicar errado custa o modo trocado para pior.
    """
    from ..core import espera
    from ..core.vision import capture_window, regiao_mudou

    item = _ponto(ctx.coords.menu_leave_team, DESLOCAMENTO_DO_PICK_MODE)
    alvo = _ponto(item, DESLOCAMENTO_DO_FREE)
    regiao = (item[0] + REGIAO_DO_SUBMENU[0], item[1] + REGIAO_DO_SUBMENU[1],
              REGIAO_DO_SUBMENU[2], REGIAO_DO_SUBMENU[3])

    def _apareceu(antes, onde) -> bool:
        """A região MUDOU desde `antes`? É a pergunta que substitui a espera.

        Sem template para o menu de contexto (nenhum existe em disco), a prova
        de que algo abriu é a região deixar de ser o que era.
        """
        return regiao_mudou(antes, capture_window(ctx.hwnd), onde)

    regiao_do_menu = (ctx.coords.own_portrait[0], ctx.coords.own_portrait[1],
                      160, 120)

    for tentativa in range(1, TENTATIVAS_DO_PICK_MODE + 1):
        if sup.stop_event.is_set():
            return False
        try:
            sem_menu = capture_window(ctx.hwnd)
            ctx.right_click(ctx.coords.own_portrait)
            if not espera.ate(lambda: _apareceu(sem_menu, regiao_do_menu),
                              ctx=ctx, teto=TETO_DO_MENU, passo=PASSO_DO_MENU,
                              o_que="o menu do próprio personagem abrir"):
                sup.log.info("Pick Mode: o menu não abriu (tentativa %s de %s).",
                             tentativa, TENTATIVAS_DO_PICK_MODE)
                continue

            antes = capture_window(ctx.hwnd)
            if not ctx.input.passar_o_mouse(item[0], item[1]):
                sup.log.info("Pick Mode: a janela recusou o movimento do mouse.")
                return False

            if not espera.ate(lambda: _apareceu(antes, regiao),
                              ctx=ctx, teto=TETO_DO_MENU, passo=PASSO_DO_MENU,
                              o_que="o submenu do Pick Mode abrir"):
                sup.log.info(
                    "Pick Mode: o submenu não abriu com o mouse por cima "
                    "(tentativa %s de %s).", tentativa, TENTATIVAS_DO_PICK_MODE)
                ctx.press("ESC")
                continue

            sup.log.info("Pick Mode: submenu aberto; clicando em 'Free' em %s.",
                         alvo)
            ctx.click(alvo)
            ctx.press("ESC")
            return True
        except Exception as exc:
            sup.log.warning("Pick Mode: falhou (%s).", exc)
            return False

    sup.log.warning(
        "Pick Mode: desisti depois de %s tentativas. O time fica no modo que "
        "estiver -- se for 'Dice', o loot dos mobs não é recolhido.",
        TENTATIVAS_DO_PICK_MODE)
    return False
