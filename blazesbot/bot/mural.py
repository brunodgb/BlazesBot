"""O MURAL entre as contas -- o quadro de avisos do processo.

=========================================================================
DEPENDENCIA CRUZADA -- leia antes de mexer
=========================================================================

PROMOVIDO de `bot/bc/team.py` em 27/08/2026, a pedido do usuário: *"até então o
team era só do BOT BC, mas agora o módulo APP também está precisando, então
torne global, mas tome cuidado para o BOT BC continuar funcionando como hoje."*

**QUEM USA:**

- `bot/team.py` -- `TeamService` (quem convida) e `InviteAcceptor` (quem
  aceita), o time DENTRO do jogo que reseta a Bewitcher Cave.
- `bot/bc/routine.py` -- a trava na porta da cave (`reseter_online`,
  `silencio_do_reseter`).
- o ecossistema APP, pelo supervisor, para a largada sincronizada do time do
  APP (ver `docs/decisoes/time-do-app.md`).

**POR QUE ISTO FUNCIONA:** todos os supervisores rodam NO MESMO PROCESSO. Uma
conta ANUNCIA e a outra CONSULTA -- não há leitura de tela, não há OCR e não há
IPC. É o princípio que já resolvia o convite de time e é exatamente o que a
largada do time do APP precisa.

**POR QUE MORA EM `bot/` E NÃO EM `core/`:** o mural fala de CONTAS e de NICKS,
que são conceito do sistema, não capacidade solta do jogo. E o executor do APP
não poderia importá-lo de `core/` de qualquer forma -- ele não importa nada de
`blazesbot.bot` (travado por `tests/test_ecossistemas.py`), e recebe tudo por
injeção do supervisor. `core/` não compraria nada.

**O QUE NÃO SUBIU, E POR QUÊ:** `TeamService` e `InviteAcceptor` ficaram em
`bot/team.py` porque precisam de `BotContext` (visão, clique, templates) e
carregam política do BC -- os dois leem `settings.bc.reset_nick`. O mural aqui
não sabe o que é cave, boss nem reset: só guarda quem anunciou o quê e quando.

**OS TRÊS QUADROS COMPARTILHAM UM LOCK, E ISSO É DE PROPÓSITO.** `_ACEITES` usa
`_LOCK_CONVITES`, não um lock próprio -- convite e aceite são as duas pontas da
MESMA conversa, e separar os mutexes mudaria a exclusão mútua entre elas. Foi a
razão de este arquivo ser UM módulo e não três.
"""
from __future__ import annotations

import threading
import time

# ---------------------------------------------------------------------------
# Registro de convites entre as contas desta execução
# ---------------------------------------------------------------------------
#
# A conta de reset precisa decidir se aceita um convite, e o que ela vê na tela é
# "[Nick] invite you to join the team". Ler esse nick exigiria OCR.
#
# Mas os supervisores de todas as contas rodam NO MESMO PROCESSO: a conta que
# farma pode simplesmente ANUNCIAR que acabou de convidar alguém, e a conta de
# reset consulta esse anúncio. É mais confiável que ler a tela e resolve o
# problema real -- não entrar no time de um estranho, o que quebraria o reset das
# contas de verdade.
_CONVITES: dict[str, tuple[str, float]] = {}   # alvo -> (quem convidou, quando)
_LOCK_CONVITES = threading.Lock()

# Validade do anúncio. Cobre a fila de resposta do outro cliente com folga; mais
# que isso passaria a aceitar convite antigo de um estranho por coincidência.
CONVITE_VALIDO_SEGUNDOS = 60.0


def anunciar_convite(alvo: str, remetente: str) -> None:
    """Registra que `remetente` acabou de convidar `alvo` para o time."""
    if not (alvo and remetente):
        return
    with _LOCK_CONVITES:
        _CONVITES[alvo.strip().lower()] = (remetente.strip(), time.time())


def convite_pendente(meu_nick: str) -> str | None:
    """Quem convidou este personagem há pouco, se alguma conta daqui convidou."""
    if not meu_nick:
        return None
    with _LOCK_CONVITES:
        dados = _CONVITES.get(meu_nick.strip().lower())
        if dados is None:
            return None
        remetente, quando = dados
        if time.time() - quando > CONVITE_VALIDO_SEGUNDOS:
            return None
        return remetente


def consumir_convite(meu_nick: str) -> None:
    """Descarta o anúncio depois de aceitar, para não valer duas vezes."""
    if not meu_nick:
        return
    with _LOCK_CONVITES:
        _CONVITES.pop(meu_nick.strip().lower(), None)


# ===========================================================================
# A BATIDA DA CONTA DE RESET -- ela prova que pode aceitar, não afirma
# ===========================================================================
#
# POR QUE ISTO EXISTE. A conta que farma precisa saber se o reseter está no ar
# ANTES de tentar entrar na cave. Sem reset o boss não renasce e a run inteira é
# perdida, então entrar sem ele é pior que esperar por ele.
#
# A ARMADILHA QUE ESTE DESENHO EVITA. A pergunta parece ser "a conta de reset
# está logada e saudável?", e responder isso com uma checagem (processo vivo,
# hwnd válido, memória legível) produz FALSO POSITIVO medido: uma conta em modo
# APP passa em todas essas provas e mesmo assim NUNCA aceita convite nenhum --
# o `_operate` testa `app.enabled` primeiro e dá `continue` antes de chegar no
# aceitador. Login, relogin e farm da cave têm o mesmo problema por caminhos
# diferentes.
#
# Então a batida não DESCREVE a capacidade, ela a PROVA: `bater()` é a primeira
# linha de `InviteAcceptor.check_and_accept`, antes até do cooldown. Se a linha
# não executou, a conta não tem como clicar no Ok -- e a batida não sai. Modo
# APP, login, relogin, farm e conta parada caem fora sozinhos, sem uma regra
# escrita para cada um deles.
#
# Isto só funciona porque todas as contas rodam NO MESMO PROCESSO, que é a mesma
# base do registro de convites logo acima.
_BATIDAS: dict[str, float] = {}                       # nick -> última batida
_LOCK_BATIDAS = threading.Lock()

# Quanto silêncio já é "caiu".
#
# NÚMERO DERIVADO, não medido: o laço da conta de reset gira a `tick(0.5)`
# (ver `AccountSupervisor._operate`), então ela bate ~2x por segundo e 5 s são
# DEZ voltas dela. Folga suficiente para uma volta lenta não ser confundida com
# queda, e ainda assim a queda aparece para quem farma em ~5 s.
SILENCIO_MAXIMO = 5.0


def bater(nick: str) -> None:
    """Registra que este personagem acabou de passar pelo ponto onde aceita."""
    if not nick:
        return
    with _LOCK_BATIDAS:
        _BATIDAS[nick.strip().lower()] = time.time()


def silencio_do_reseter(nick: str) -> float | None:
    """Há quanto tempo este nick não bate. `None` = nunca bateu nesta execução."""
    if not nick:
        return None
    with _LOCK_BATIDAS:
        quando = _BATIDAS.get(nick.strip().lower())
    return None if quando is None else time.time() - quando


def reseter_online(nick: str) -> bool:
    """Este nick está em condição de aceitar um convite AGORA?

    Nunca ter batido conta como offline: a conta de reset bate duas vezes por
    segundo desde que sobe, então "nenhuma batida" significa que ela ainda não
    chegou lá -- está logando, relogando, em modo APP ou não subiu.
    """
    silencio = silencio_do_reseter(nick)
    return silencio is not None and silencio <= SILENCIO_MAXIMO


# ===========================================================================
# O ACEITE TAMBÉM É ANUNCIADO -- as duas pontas rodam aqui dentro
# ===========================================================================
#
# POR QUE ISTO EXISTE. O bot convida por uma conta e aceita pela outra, no MESMO
# processo. Ele sabe que enviou o convite e sabe que clicou no Ok -- as duas
# pontas são dele. Ainda assim, a confirmação dependia de `memory.team_size()`,
# e essa leitura não funciona neste cliente. O resultado, medido em log real:
#
#   02:17:22  [creubo]      Clicando em 'Team up'
#   02:17:22  [blazesgamer] Convite de time ACEITO (1 no total)
#   02:17:24  [blazesgamer] Convite de time ACEITO (2 no total)
#   ...                     (mais nove vezes)
#   02:17:33  [creubo]      'WizzOfBlazes4' não entrou no time em 8s
#
# O time formou no primeiro segundo. Quem convidou esperou 8 s, tentou de novo,
# esperou mais 8 s e desistiu -- 23 segundos por run, com o time já pronto. E
# quem aceitou ficou clicando onze vezes, porque o anúncio só era descartado
# quando `team_size()` respondesse, e ele nunca respondia.
#
# O aceite anunciado de volta fecha o circuito sem depender de leitura nenhuma.
_ACEITES: dict[str, tuple[str, float]] = {}   # quem convidou -> (quem aceitou, quando)

# Validade do aceite. Curta de propósito: ele confirma UM convite recém-enviado,
# e um aceite velho no dicionário faria a run seguinte achar que já tem time.
ACEITE_VALIDO_SEGUNDOS = 15.0



def anunciar_aceite(quem_convidou: str, quem_aceitou: str) -> None:
    """Registra que `quem_aceitou` acabou de clicar no Ok do convite."""
    if not (quem_convidou and quem_aceitou):
        return
    with _LOCK_CONVITES:
        _ACEITES[quem_convidou.strip().lower()] = (quem_aceitou.strip(),
                                                   time.time())


def aceite_pendente(meu_nick: str) -> str | None:
    """Quem aceitou o convite que este personagem enviou há pouco."""
    if not meu_nick:
        return None
    with _LOCK_CONVITES:
        dados = _ACEITES.get(meu_nick.strip().lower())
        if dados is None:
            return None
        quem, quando = dados
        if time.time() - quando > ACEITE_VALIDO_SEGUNDOS:
            return None
        return quem


def consumir_aceite(meu_nick: str) -> None:
    """Descarta o aceite depois de usá-lo, para não valer na run seguinte."""
    if not meu_nick:
        return
    with _LOCK_CONVITES:
        _ACEITES.pop(meu_nick.strip().lower(), None)

# ===========================================================================
# O TIME DO APP -- a largada, o alvo e o estado de cada conta
# ===========================================================================
#
# POR QUE ISTO EXISTE. O time do APP precisa que várias contas comecem cada
# volta da macro no MESMO instante, e (no modo "mesmo_alvo") no MESMO mob. As
# contas são threads do mesmo processo, então isso não pede rede, nem arquivo,
# nem leitura de tela: o líder ANUNCIA e os seguidores CONSULTAM -- o mesmo
# princípio que já resolvia o convite de time logo acima.
#
# O QUADRO É POR LÍDER. A chave de tudo é o login do líder, e não um "time
# global": duas pessoas podem montar dois times na mesma execução, e cada um
# tem a sua largada.
_LARGADAS: dict[str, tuple[int, int, float]] = {}   # lider -> (volta, alvo, quando)
_ESTADOS: dict[str, tuple[dict, float]] = {}        # login -> (estado, quando)
_LOCK_TIME = threading.Lock()

# Quanto tempo uma largada anunciada continua valendo.
#
# PROVISÓRIO -- não medido. Decisão do usuário em 27/08/2026: deixar rodando
# antes de medir, para a rodada real produzir os números. Ver
# `docs/decisoes/time-do-app.md`, seção "MEDIR DEPOIS, NÃO ANTES".
#
# Ele existe para o seguidor não entrar numa largada VELHA: se ele estava
# relogando, o anúncio que encontrar ao voltar pode ser de minutos atrás, e
# entrar nele seria começar a volta sozinho achando que está junto.
LARGADA_VALIDA_SEGUNDOS = 8.0

# Quanto tempo o estado publicado por uma conta continua valendo.
#
# PROVISÓRIO -- não medido, mesma decisão. Serve para o líder saber quem ainda
# está de pé: conta que parou de publicar não conta para a eleição nem para a
# barreira. Mais generoso que a largada porque uma volta longa da macro pode
# passar de 8 s sem publicar nada.
ESTADO_VALIDO_SEGUNDOS = 30.0


def anunciar_largada(lider: str, volta: int, alvo: int) -> None:
    """O líder abre a volta `volta`, com `alvo` = id do mob dele (0 = nenhum)."""
    if not lider:
        return
    with _LOCK_TIME:
        _LARGADAS[lider.strip().lower()] = (int(volta), int(alvo or 0), time.time())


def largada_pendente(lider: str) -> tuple[int, int] | None:
    """A largada aberta pelo líder, ou `None` se não houver ou já vencida."""
    if not lider:
        return None
    with _LOCK_TIME:
        dados = _LARGADAS.get(lider.strip().lower())
    if dados is None:
        return None
    volta, alvo, quando = dados
    if time.time() - quando > LARGADA_VALIDA_SEGUNDOS:
        return None
    return volta, alvo


def esquecer_largada(lider: str) -> None:
    """Apaga a largada do líder. Usado quando o time para."""
    if not lider:
        return
    with _LOCK_TIME:
        _LARGADAS.pop(lider.strip().lower(), None)


def publicar_estado(login: str, **estado: object) -> None:
    """Cada conta do time publica o que sabe de si: vida, alvo, batalha.

    É PUBLICADO UMA VEZ POR VOLTA, e não continuamente: a volta é a unidade de
    decisão do time, e publicar mais rápido só gastaria lock sem mudar nenhuma
    decisão.
    """
    if not login:
        return
    with _LOCK_TIME:
        _ESTADOS[login.strip().lower()] = (dict(estado), time.time())


def estado_da_conta(login: str) -> dict | None:
    """O último estado publicado por esta conta, ou `None` se velho demais.

    "Velho demais" e "nunca publicou" devolvem a MESMA coisa de propósito: as
    duas respostas significam "não conte com ela agora", e distinguir as duas
    faria quem pergunta escrever dois ramos para o mesmo desfecho.
    """
    if not login:
        return None
    with _LOCK_TIME:
        dados = _ESTADOS.get(login.strip().lower())
    if dados is None:
        return None
    estado, quando = dados
    if time.time() - quando > ESTADO_VALIDO_SEGUNDOS:
        return None
    return estado


def esquecer_estado(login: str) -> None:
    """A conta saiu do time (parou, caiu, foi para o BC)."""
    if not login:
        return
    with _LOCK_TIME:
        _ESTADOS.pop(login.strip().lower(), None)

def zerar_o_time_para_teste() -> None:
    """Esvazia o quadro do time. SÓ para teste.

    Existe pelo mesmo motivo de `core.calibracao.zerar_para_teste`: o quadro é
    estado global de módulo e a suíte não tem fixture que o limpe, então um
    teste que anuncia uma largada contamina o seguinte -- e o sintoma seria um
    teste passando por causa do vizinho, que é pior que um teste falhando.
    """
    with _LOCK_TIME:
        _LARGADAS.clear()
        _ESTADOS.clear()
