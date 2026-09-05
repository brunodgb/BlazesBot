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
# lider -> (epoca, volta, alvo, quando). A ÉPOCA é o que distingue duas
# execuções do mesmo líder: o contador de voltas recomeça do 1 a cada
# reinício do executor, e sem ela uma confirmação da execução anterior --
# ainda válida por `ESTADO_VALIDO_SEGUNDOS` -- contava como se o seguidor já
# tivesse entrado na largada nova.
_LARGADAS: dict[str, tuple[int, int, int, float]] = {}
_ESTADOS: dict[str, tuple[dict, float]] = {}        # login -> (estado, quando)
_LOCK_TIME = threading.Lock()

# O QUADRO DO TIME USA `time.monotonic()`, e o resto deste arquivo continua com
# `time.time()`. Não é inconsistência esquecida:
#
# - o quadro do time mede TETO DE ESPERA, e teto medido em relógio de parede
#   deixa de ser teto quando o relógio anda para trás (ajuste de NTP, fuso). A
#   regra do time é que ninguém espera sem limite; `monotonic` é o que a
#   sustenta.
# - os quadros de convite/batida/aceite acima ficam como estavam porque a
#   exigência do usuário era o BC continuar EXATAMENTE como hoje, e há teste
#   que troca o relógio deles (`test_reset_de_time.py`).


# Quanto tempo uma largada anunciada continua valendo.
#
# PROVISÓRIO -- não medido. Decisão do usuário em 27/08/2026: deixar rodando
# antes de medir, para a rodada real produzir os números. Ver
# `docs/decisoes/time-do-app.md`, seção "MEDIR DEPOIS, NÃO ANTES".
#
# Ele existe para o seguidor não entrar numa largada VELHA: se ele estava
# relogando, o anúncio que encontrar ao voltar pode ser de minutos atrás, e
# entrar nele seria começar a volta sozinho achando que está junto.
#
# ELE É O MESMO NÚMERO DO TETO DE ESPERA DO LÍDER, e por isso mora aqui, num
# lugar só (`sincronia.TETO_DA_LARGADA_SEGUNDOS` importa daqui). Eram dois
# números diferentes -- 8 s de validade contra 3 s de espera -- e a diferença
# era um buraco: entre o terceiro e o oitavo segundo o seguidor "entrava" numa
# largada que o líder já tinha abandonado, e os dois se contavam como juntos
# estando cinco segundos fora de fase.
LARGADA_VALIDA_SEGUNDOS = 5.0

# Quanto tempo o estado publicado por uma conta continua valendo.
#
# PROVISÓRIO -- não medido, mesma decisão. Serve para o líder saber quem ainda
# está de pé: conta que parou de publicar não conta para a eleição nem para a
# barreira. Mais generoso que a largada porque uma volta longa da macro pode
# passar de 8 s sem publicar nada.
ESTADO_VALIDO_SEGUNDOS = 30.0


def anunciar_largada(lider: str, epoca: int, volta: int, alvo: int) -> None:
    """O líder abre a volta `volta`, com `alvo` = id do mob dele (0 = nenhum)."""
    if not lider:
        return
    with _LOCK_TIME:
        _LARGADAS[lider.strip().lower()] = (int(epoca), int(volta),
                                            int(alvo or 0), time.monotonic())


def largada_pendente(lider: str) -> tuple[int, int, int] | None:
    """A largada aberta pelo líder: `(epoca, volta, alvo)`.

    `None` quando não há, quando venceu, ou quando o líder já FECHOU a largada
    -- ele fecha assim que para de esperar. Sem esse fechamento havia uma
    janela em que o seguidor entrava numa largada que o líder já tinha
    abandonado, e os dois se contavam como juntos.
    """
    if not lider:
        return None
    chave = lider.strip().lower()
    with _LOCK_TIME:
        dados = _LARGADAS.get(chave)
        if dados is None:
            return None
        epoca, volta, alvo, quando = dados
        if time.monotonic() - quando > LARGADA_VALIDA_SEGUNDOS:
            # APAGA O VENCIDO em vez de só ignorá-lo: sem isto o quadro só
            # encolhe em saída limpa, e uma execução longa acumula anúncios de
            # contas que nem existem mais.
            _LARGADAS.pop(chave, None)
            return None
    return epoca, volta, alvo


def esquecer_largada(lider: str) -> None:
    """FECHA a largada do líder: ninguém mais entra nela.

    Chamada em dois momentos: quando o líder termina de esperar (a largada
    passou, quem não entrou entra na próxima) e quando o modo APP encerra.
    """
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
        _ESTADOS[login.strip().lower()] = (dict(estado), time.monotonic())


def estado_da_conta(login: str) -> dict | None:
    """O último estado publicado por esta conta, ou `None` se velho demais.

    "Velho demais" e "nunca publicou" devolvem a MESMA coisa de propósito: as
    duas respostas significam "não conte com ela agora", e distinguir as duas
    faria quem pergunta escrever dois ramos para o mesmo desfecho.
    """
    if not login:
        return None
    chave = login.strip().lower()
    with _LOCK_TIME:
        dados = _ESTADOS.get(chave)
        if dados is None:
            return None
        estado, quando = dados
        if time.monotonic() - quando > ESTADO_VALIDO_SEGUNDOS:
            _ESTADOS.pop(chave, None)
            return None
    return estado


def esquecer_estado(login: str) -> None:
    """A conta saiu do time (parou, caiu, foi para o BC)."""
    if not login:
        return
    with _LOCK_TIME:
        _ESTADOS.pop(login.strip().lower(), None)

# ===========================================================================
# O RELÓGIO DE LINHA -- o líder marca cada tecla, e os outros seguem
# ===========================================================================
#
# POR QUE ISTO EXISTE. A primeira versão sincronizava só o COMEÇO de cada volta,
# e a rodada real de 28/08/2026 mostrou que não basta. Medido no log:
#
#     00:13:21  blazestpas   volta 17 largou sem gamerblazes (teto 3s)
#     00:13:34  gamerblazes  sem largada de blazestpas em 3s -- indo sozinho
#     00:13:41  blazestpas   volta 18 largou sem gamerblazes
#
# As duas contas rodavam voltas de ~20 s DEFASADAS EM ~13 s. A largada ficava
# aberta 3 s de um ciclo de 20 -- uma janela de 15% --, e quando o seguidor
# perdia, ele rodava uma volta solo inteira: a defasagem era preservada
# EXATAMENTE, volta após volta. Nada puxava ele de volta.
#
# COMO ISTO RESOLVE. O líder marca CADA linha da macro. O seguidor espera a
# marca antes de mandar a mesma tecla, e -- esta é a parte que conserta -- ele
# NÃO dorme o delay dele: quem dá o ritmo é a marca. Atrasado, ele encontra a
# marca já dada, não espera nada, e alcança. A defasagem deixa de ser estável.
#
# A COMPARAÇÃO É `>=` E A CHAVE É `(época, volta, linha)`. Assim um seguidor que
# ficou uma volta inteira para trás não trava esperando uma linha que já passou:
# a marca da volta seguinte já é "maior", ele destrava na hora e alcança.
_PASSOS: dict[str, tuple[int, int, int]] = {}      # lider -> (epoca, volta, linha)

# `Condition` e não polling: as contas são threads do MESMO processo, então o
# aviso chega em microssegundos em vez de esperar a próxima olhada. É a
# diferença entre "ao mesmo tempo" e "quase ao mesmo tempo".
_COND_DO_PASSO = threading.Condition()


def abrir_passo(lider: str, epoca: int, volta: int, linha: int) -> None:
    """O líder está mandando esta linha AGORA."""
    if not lider:
        return
    with _COND_DO_PASSO:
        _PASSOS[lider.strip().lower()] = (int(epoca), int(volta), int(linha))
        _COND_DO_PASSO.notify_all()


def passo_do_lider(lider: str) -> tuple[int, int, int] | None:
    if not lider:
        return None
    with _COND_DO_PASSO:
        return _PASSOS.get(lider.strip().lower())


def esperar_passo(lider: str, alvo: tuple[int, int, int],
                  teto: float) -> tuple[int, int, int] | None:
    """Espera o líder chegar em `alvo` e DEVOLVE A MARCA que o liberou.

    Devolver a marca aqui, e não deixar quem chamou lê-la depois, fecha uma
    corrida real: entre o "pode ir" e a leitura, o líder podia virar a volta --
    e o seguidor descartava uma linha que já estava autorizada, achando que a
    volta tinha acabado. Esperar e ler é UMA operação, sob o mesmo lock.

    O `>=` é o que faz o atrasado destravar na hora em vez de esperar por uma
    linha que já foi anunciada.
    """
    if not lider:
        return None
    chave = lider.strip().lower()
    with _COND_DO_PASSO:
        if not _COND_DO_PASSO.wait_for(
                lambda: _PASSOS.get(chave, (0, 0, -1)) >= alvo, timeout=teto):
            return None
        return _PASSOS.get(chave)


def esquecer_passo(lider: str) -> None:
    if not lider:
        return
    with _COND_DO_PASSO:
        _PASSOS.pop(lider.strip().lower(), None)
        _COND_DO_PASSO.notify_all()


# ===========================================================================
# A FADA -- ids, fila de cura, batida e a limpeza de bolsa
# ===========================================================================
#
# POR QUE OS IDS ESTÃO AQUI. A Fada mira a cura clicando no retrato do
# companheiro, e precisa saber SE ACERTOU. A medição de 28/08/2026 fechou o
# caminho óbvio: `alvo_atual()` devolve `nome`/`hp` NULOS para jogador -- a
# varredura de entidades não acha gente, só mob.
#
# O que sobrou é melhor: o `TARGET_ID` responde para jogador, e a tecla de
# AUTO-SELEÇÃO põe o próprio id da conta nele. Então cada conta lê o próprio id
# uma vez e o publica aqui; a Fada clica, lê o id e COMPARA INTEIRO COM INTEIRO.
#
# E isso não é conferência de luxo: clicar num aliado LONGE não seleciona nada,
# e o alvo continua o de antes. Curar sem conferir curaria o aliado ANTERIOR --
# o pedido sairia da fila e a vítima continuaria ferida, sem erro na tela.
_IDS: dict[str, int] = {}                     # login -> id da entidade
_PEDIDOS: dict[str, tuple[float, float]] = {}  # login -> (vida_pct, quando)
# login -> (última batida, em batalha, por quanto tempo ela vale)
_FADAS: dict[str, tuple[float, bool, float]] = {}
_LIMPEZAS: dict[str, float] = {}              # lider -> quando anunciou
# login da vítima -> quando a Fada desistiu dela
#
# ISTO FECHA UM LAÇO INFINITO MEDIDO EM 04/09/2026. Quando a Fada desistia de
# alguém (teto estourado, tentativas esgotadas, sem nick), ela só apagava o
# pedido -- e a vítima, que republica a própria vida a cada 0,2 s, entrava de
# novo na fila em seguida, agora com hora NOVA. Ou seja: perdia o lugar,
# recomeçava a espera e a Fada desistia de novo, para sempre, sem que ninguém
# bebesse a poção que resolveria.
#
# Apagar o pedido diz "não está mais na fila"; ISTO diz "e não adianta voltar".
_DESISTENCIAS: dict[str, float] = {}
_LOCK_FADA = threading.Lock()

# Quanto silêncio já é "a Fada não está lá".
#
# Mesmo raciocínio (e mesmo valor) do `SILENCIO_MAXIMO` da conta de reset: a
# batida sai de dentro do laço que cura, que gira várias vezes por segundo, e 5
# s são muitas voltas dela. É o que separa "esperar a Fada" de "beber poção".
SILENCIO_DA_FADA = 5.0

# Quanto uma batida pode valer, no MÁXIMO, quando a Fada avisa que vai sumir.
#
# Existe porque a Fada tem tarefas que passam dos 5 s sem chance de bater no
# meio -- a limpeza da bolsa é a pior delas, com teto de 10 s no deletador, o
# DOBRO do silêncio que a mata. Sem isto, toda vítima que chegasse durante uma
# limpeza concluía "a Fada sumiu" e ia de poção, com a Fada viva e parada ao
# lado.
#
# É um aviso, não um cheque em branco: quem bate diz por quanto vale, e o teto
# aqui impede que uma Fada realmente morta demore uma eternidade para ser
# notada. Morrer DURANTE a tarefa longa custa esta espera a mais -- é o preço,
# e é menor que o de abandonar uma Fada viva.
TETO_DA_BATIDA_LONGA = 15.0


def publicar_id(login: str, ident: int | None) -> None:
    """"Eu sou o <id>" -- lido do `TARGET_ID` depois da auto-seleção."""
    if not login or not ident:
        return
    with _LOCK_FADA:
        _IDS[login.strip().lower()] = int(ident)


def esquecer_id(login: str) -> None:
    """A entidade desta conta morreu com a sessão -- o id não vale mais nada.

    ID VELHO É PIOR QUE ID NENHUM, e isto foi medido em 04/09/2026: `_IDS` é
    dicionário de módulo, então sobrevive ao relogin inteiro. A Fada clica no
    retrato, lê o id NOVO do jogo, compara com o VELHO daqui, e conclui que
    clicou na pessoa errada -- descartando a vítima certa depois de três
    tentativas. Sem id publicado ela confia no slot do painel, que é o que o
    usuário mandou fazer: *"se sabe qual o slot, não precisa de outra
    confirmação depois"*.
    """
    if not login:
        return
    with _LOCK_FADA:
        _IDS.pop(login.strip().lower(), None)


def id_publicado(login: str) -> int | None:
    if not login:
        return None
    with _LOCK_FADA:
        return _IDS.get(login.strip().lower())


def quem_e_o_id(ident: int | None) -> str:
    """De quem é este id, ou "". É a pergunta que a Fada faz depois do clique."""
    if not ident:
        return ""
    with _LOCK_FADA:
        for login, publicado in _IDS.items():
            if publicado == int(ident):
                return login
    return ""


def pedir_cura(login: str, vida_pct: float) -> None:
    """A vítima entra na fila. Repetir não a manda para o fim.

    A ordem é de CHEGADA e ela é preservada de propósito: quem pediu primeiro é
    atendido primeiro, e um pedido repetido (a vida continua baixa) não pode
    empurrar a própria vítima para trás dos que chegaram depois.
    """
    if not login:
        return
    chave = login.strip().lower()
    with _LOCK_FADA:
        anterior = _PEDIDOS.get(chave)
        quando = anterior[1] if anterior else time.monotonic()
        _PEDIDOS[chave] = (float(vida_pct), quando)
        # A DESISTÊNCIA NÃO É APAGADA AQUI, e isso é deliberado: `desistir_da_vitima`
        # já tirou o pedido, então a republicação da vítima (a cada 0,2 s, enquanto
        # ela espera) chega aqui indistinguível de um pedido novo. Apagar a marca
        # neste ponto reabriria exatamente o laço que ela existe para fechar.
        #
        # Quem apaga é a VÍTIMA, ao ler o recado (`esquecer_desistencia`), ou o
        # relógio (`VALIDADE_DA_DESISTENCIA`).


# Por quanto tempo a desistência da Fada continua valendo.
#
# Curto de propósito: é para a vítima ENXERGAR a desistência antes de voltar
# para a fila, não para bani-la. Passado isso, a próxima vez que ela ficar
# ferida é um caso novo -- a Fada pode ter saído da briga, a vítima pode ter
# voltado para o painel, e insistir de novo é barato.
VALIDADE_DA_DESISTENCIA = 20.0


def desistir_da_vitima(login: str) -> None:
    """A Fada desiste desta vítima: tira da fila E avisa que desistiu."""
    if not login:
        return
    chave = login.strip().lower()
    with _LOCK_FADA:
        _PEDIDOS.pop(chave, None)
        _DESISTENCIAS[chave] = time.monotonic()


def fada_desistiu_de(login: str) -> bool:
    """A Fada desistiu de mim há pouco? `True` ⇒ pare de esperar, beba poção."""
    if not login:
        return False
    chave = login.strip().lower()
    with _LOCK_FADA:
        quando = _DESISTENCIAS.get(chave)
    return quando is not None and (time.monotonic() - quando) <= VALIDADE_DA_DESISTENCIA


def esquecer_desistencia(login: str) -> None:
    """Li o recado e vou de poção -- a marca já cumpriu o papel dela."""
    if not login:
        return
    with _LOCK_FADA:
        _DESISTENCIAS.pop(login.strip().lower(), None)


def cancelar_pedido(login: str) -> None:
    if not login:
        return
    with _LOCK_FADA:
        _PEDIDOS.pop(login.strip().lower(), None)


def pedido_de(login: str) -> float | None:
    """A vida com que esta conta pediu cura, ou `None` se não há pedido."""
    if not login:
        return None
    with _LOCK_FADA:
        dados = _PEDIDOS.get(login.strip().lower())
    return dados[0] if dados else None


def fila_de_cura(logins) -> list[str]:
    """Quem está esperando, em ORDEM DE CHEGADA, restrito a estes logins.

    O filtro por `logins` é o que impede a Fada de atender alguém de outro time
    que por acaso esteja rodando no mesmo processo.
    """
    permitidos = {str(x).strip().lower() for x in logins if x}
    with _LOCK_FADA:
        itens = [(quando, login) for login, (_, quando) in _PEDIDOS.items()
                 if login in permitidos]
    itens.sort()
    return [login for _, login in itens]


def bater_fada(login: str, em_batalha: bool = False,
               vale_por: float = SILENCIO_DA_FADA) -> None:
    """A Fada prova que está de pé. Chamada de DENTRO do laço que cura.

    De dentro, e não de fora: uma Fada logada mas presa numa janela aberta passa
    em qualquer checagem externa (processo vivo, hwnd válido, memória legível) e
    não cura ninguém. É o falso positivo já medido na conta de reset.
    """
    if not login:
        return
    with _LOCK_FADA:
        _FADAS[login.strip().lower()] = (
            time.monotonic(), bool(em_batalha),
            min(max(float(vale_por), SILENCIO_DA_FADA), TETO_DA_BATIDA_LONGA))


def fada_de_pe(login: str) -> bool:
    """Dá para contar com esta Fada agora? `False` ⇒ a vítima bebe poção."""
    if not login:
        return False
    with _LOCK_FADA:
        dados = _FADAS.get(login.strip().lower())
    if dados is None:
        return False
    return (time.monotonic() - dados[0]) <= dados[2]


def fada_em_batalha(login: str) -> bool:
    """A Fada está apanhando agora?

    Enquanto estiver, ela cuida de SI -- e quem esperava cura volta a rodar a
    macro. Não é abandono: atacando, o time mata o que está batendo nela, que é
    a forma mais rápida de ela voltar a curar. Decisão do usuário em
    01/09/2026: *"a ideia aqui é não deixar a fada morrer de forma alguma"*.

    Batida velha responde `False`: quem não está de pé não está em batalha, está
    ausente -- e ausente é assunto do `fada_de_pe`.
    """
    if not login:
        return False
    with _LOCK_FADA:
        dados = _FADAS.get(login.strip().lower())
    if dados is None:
        return False
    quando, em_batalha, vale_por = dados
    if (time.monotonic() - quando) > vale_por:
        return False
    return em_batalha


def esquecer_fada(login: str) -> None:
    if not login:
        return
    with _LOCK_FADA:
        _FADAS.pop(login.strip().lower(), None)


def anunciar_limpeza(lider: str) -> None:
    """O líder limpou a bolsa. A Fada limpa quando tiver folga."""
    if not lider:
        return
    with _LOCK_FADA:
        _LIMPEZAS[lider.strip().lower()] = time.monotonic()


def limpeza_pendente(lider: str, desde: float) -> bool:
    """O líder anunciou limpeza depois de `desde`?

    O anúncio FICA PENDURADO: a Fada só limpa com a fila vazia, e perder o
    anúncio porque chegou um pedido de cura no meio faria a bolsa dela encher.
    """
    if not lider:
        return False
    with _LOCK_FADA:
        quando = _LIMPEZAS.get(lider.strip().lower())
    return quando is not None and quando > desde


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
    with _COND_DO_PASSO:
        _PASSOS.clear()
    with _LOCK_FADA:
        _IDS.clear()
        _PEDIDOS.clear()
        _FADAS.clear()
        _LIMPEZAS.clear()
