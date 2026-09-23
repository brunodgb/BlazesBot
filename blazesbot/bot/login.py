"""
Auto-login por FASES, com verificação por sinais quando disponível.

Histórico do desenho, porque explica as escolhas:

  v1 -- sequência cega de cliques. Funcionava, mas não percebia senha errada:
        seguia adiante como se tivesse dado certo.
  v2 -- 100% guiado por reconhecimento de imagem. Percebia tudo... quando havia
        imagem. Como o PrintWindow devolve quadro preto em cliente DirectX fora
        de foco, na prática ficava parado em "tela desconhecida" sem agir.
  v3 -- este. A sequência cega volta a ser o ESQUELETO (é o que sempre
        funcionou), e a detecção entra como VERIFICAÇÃO em cima dela. Se a
        imagem existe, o bot corrige o rumo e trata erro de senha, fila e
        desconexão. Se não existe, ele ainda faz o login.

Regra de ouro: nenhuma fase depende de imagem para AVANÇAR. A imagem só serve
para descobrir que algo saiu do roteiro.
"""
from __future__ import annotations

import time
from pathlib import Path

import win32gui

from ..config import Account, BotConfig
from ..core.coords import TEMPLATE_ANCHORS, coords_for_size
from ..core.inputs import Input, sleep
from ..core.memory import Memory
from ..core.vision import TemplateLibrary, find_highlighted_row
from .login_states import (
    ESPERA_PELO_SERVIDOR_FORA_DO_AR,
    TENTATIVAS_DE_SELECAO,
    VOLTAS_NA_LISTA_DE_SERVIDORES,
    Detection,
    LoginScreen,
    LoginStateDetector,
    Phase,
)
from .watchdog import kill_client

# Recusas de usuário/senha antes de desistir da conta.
#
# Só conta o que o SERVIDOR recusou: `credential_errors` sobe dentro de
# `_handle_login_error`, que só roda quando o detector casa `state_login_error.png`
# -- a tela específica do erro. Demora, fila e tela travada não somam aqui, e
# cada uma delas tem seu próprio caminho.
#
# Cinco, e não mais: o `BadCredentials` encerra a conta na primeira vez que ele
# estoura. Contar por ciclo de relogin multiplicaria isso por cada tentativa e o
# servidor veria dezenas de senhas erradas da mesma conta.
#
# O CONTADOR ZERA EM DOIS PONTOS, e o segundo é o que importa:
#
#   1. no `__init__` -- cada `LoginSequence` nasce com zero;
#   2. quando o detector VÊ A LISTA DE SERVIDORES -- porque o servidor só a
#      mostra depois de aceitar usuário e senha, e isso é prova de credencial
#      correta. Ver o comentário longo no `SERVER_LIST` do laço principal.
#
# O ponto 2 nasceu de uma medição em 01/09/2026: numa sequência de 796 s com o
# jogo no bug de "Conexão interrompida", a conta autenticou 85 vezes e recebeu 5
# erros de credencial ESPORÁDICOS pelo caminho -- e foi desativada com a senha
# certa. Sem o reset, "cinco recusas" virava "cinco erros somados ao longo de
# horas", que é coisa diferente.
MAX_CREDENTIAL_ERRORS = 5

# Voltas na lista antes de sair pelo Cancel -- a REDE, para o que a leitura do
# status não pega (servidor reiniciando, Ok engolido, captura cega). Três, e não
# uma: clique engolido é comum nesta UI, e a seleção da linha já tenta três
# vezes pelo mesmo motivo. Conta VOLTAS À MESMA TELA, não cliques.

# NÃO EXISTE LIMITE DE TEMPO NA FILA.
#
# Fila de servidor cheio passa de três horas em dia ruim. Qualquer número que
# eu escolhesse aqui seria arbitrário e viraria bug: o bot desistiria no meio,
# reiniciaria o login e voltaria para o fim da fila -- o pior resultado
# possível. Então, enquanto o cliente está conectado ao servidor, o bot espera
# INDEFINIDAMENTE e sai dessa espera apenas por um SINAL concreto:
#
#   * entrou no mundo                     -> pronto
#   * processo ou janela do cliente morreu -> relogin
#   * aviso de erro detectado na tela      -> trata o aviso
#   * servidor desapareceu do título       -> caiu para a tela de login
#   * parada pedida pelo usuário           -> encerra
#
# Limite de tempo só existe nas telas iniciais (login e lista de servidores),
# que respondem em segundos -- ali, demora É sintoma de problema.
PRE_SERVER_TIMEOUT = 600.0    # 10 min nas telas de login/servidor

# Cadência de tentativa de entrar enquanto conectado.
ENTER_RETRY_SECONDS = 10.0
# Quantas tentativas de "Enter Game" fazer sem conseguir confirmar a entrada.
#
# Existe um limite porque, se o personagem JÁ entrou e o bot não percebeu, cada
# clique cai no chão do mundo e faz o personagem andar. Melhor parar de clicar e
# avisar alto do que passar horas arrastando o personagem pelo mapa.
MAX_BLIND_ENTER_ATTEMPTS = 4
# Depois de esgotar as tentativas às cegas, o bot NÃO desiste -- ele espaça.
#
# Três minutos é o equilíbrio: se o personagem já está no mundo, um clique a cada
# três minutos o move alguns passos, o que é recuperável. Se ele está preso na
# tela de seleção (o caso real relatado), três minutos é o pior atraso possível em
# vez de "para sempre".
ESPERA_CEGA_SEGUNDOS = 90.0
# Divergência a partir da qual a âncora é considerada suspeita. É folgada de
# propósito: pequenas diferenças entre o valor encontrado e o calculado são
# normais e o encontrado é o mais confiável. Só um desvio grande indica template
# casando no lugar errado.
MAX_ANCHOR_DEVIATION = 60
# Persistência do flag de modal para concluir que há um aviso na tela.
MODAL_CONFIRM_SECONDS = 7.5
# O mesmo, mas ANTES de conectar ao servidor. Bem menor: as telas de login e de
# servidor respondem em segundos, e ali não existe caixa de confirmação legítima
# que o bot queira manter aberta -- então modal que fica é modal que trava.
MODAL_PRE_SERVER_SECONDS = 3.5
# Espera depois de fechar "Acquiring server IP address." (servidores fora do ar).
# Dobra a cada ocorrência até o teto: servidor caído não volta em dois segundos, e
# martelar o login encheria o log de linhas iguais -- justamente o que esconderia
# o momento em que ele voltou.
ESPERA_SERVIDOR_FORA = 10.0
ESPERA_SERVIDOR_FORA_MAX = 60.0
# Cadência do aviso de "continuo esperando", só para o log não ficar mudo.
WAIT_HEARTBEAT_SECONDS = 150.0
# Tempo máximo parado na tela de usuário e senha antes de reabrir o cliente.
#
# Essa tela responde em segundos. Se o bot está ali há minutos sem avançar, o
# cliente provavelmente travou num estado do qual não sai por clique -- reabrir
# é mais rápido e mais confiável que insistir.
LOGIN_SCREEN_MAX_SECONDS = 150.0

# Quanto esperar nas fases iniciais antes de repetir a ação.
PHASE_TIMEOUT = {
    Phase.CREDENTIALS: 12.5,
    Phase.SERVER: 15.0,
    Phase.ENTERING: None,     # sem limite: ver comentário acima
}

# Deslocamento do botão "Ok" em relação ao ponto onde o texto do aviso casa.
# Medidos em prints reais do cliente ver.6400 em 1024x768.
OK_OFFSET_LOGIN_ERROR = (21, 133)
OK_OFFSET_CONN_INTERRUPTED = (54, 132)

# "Connecting to the server, please wait a moment." -- espera LEGÍTIMA, com
# prazo. 6 s é número do usuário, medido por ele na prática: abaixo disso a tela
# some sozinha e fechá-la jogaria fora um login que ia dar certo; acima, o
# servidor do jogo travou e insistir não resolve.
SEGUNDOS_CONECTANDO = 6.0

# Fatia da espera do login. A espera é cumprida em pedaços para que Parar e
# Pausar valham NA HORA -- é a mesma ideia do `BotContext.tick`, que o
# `LoginSequence` não pode usar porque ele roda ANTES de existir contexto.
FATIA_DA_ESPERA_DO_LOGIN = 0.05

# O botão desta caixa é **Cancel**, não Ok -- e NÃO fica onde o Ok fica. Foi
# justamente por clicar no deslocamento do Ok que a tela de falha de conexão
# ficava travada (ver `login_states._SIGNATURES`).
#
# MEDIDO em `data/templates/entrada/login-connecting.png`: o template casa
# (centro) em (495,222) e o centro do Cancel está em (511,364). O deslocamento
# é a diferença, e é imune ao tamanho da janela porque os dois pontos vêm do
# MESMO diálogo -- a barra de título da captura cancela na subtração.
CANCEL_OFFSET_CONNECTING = (16, 142)
# "Acquiring server IP address." O dy é o MESMO do erro de senha (133 contra 134),
# porque é o mesmo quadro de mensagem do cliente. Uma medição confirma a outra.
OK_OFFSET_ACQUIRING_IP = (33, 134)


class LoginError(RuntimeError):
    pass


class BadCredentials(LoginError):
    """Usuário ou senha rejeitados pelo servidor."""


class ClientClosed(LoginError):
    """O cliente fechou durante o login -- precisa relançar.

    Acontece no aviso "Connection interrupted, please open client again": ao
    clicar em Ok o próprio jogo se encerra.
    """


class StopDuringLogin(LoginError):
    """Parada pedida pelo usuário. NÃO deve encerrar o cliente."""


class LoginSequence:
    def __init__(
        self,
        config: BotConfig,
        pid: int,
        hwnd: int,
        account: Account,
        logger,
        stop_check=lambda: False,
        pause_check=lambda: False,
    ) -> None:
        self.config = config
        self.pid = pid
        self.hwnd = hwnd
        self.account = account
        self.log = logger
        self.stop_check = stop_check
        self.pause_check = pause_check

        self.input = Input(hwnd)
        # Coordenadas derivadas do tamanho REAL da janela, não do que está
        # escolhido na interface. Se os dois divergirem, o que vale é a janela.
        largura, altura = self.input.client_size()
        self.coords = coords_for_size(largura, altura)
        logger.info(
            "Área de cliente da janela: %sx%s%s",
            largura, altura,
            "" if self.coords.is_validated
            else "  (fora de 1024x768: coordenadas derivadas por ancoragem)",
        )
        self.memory = Memory(pid)
        self.templates = TemplateLibrary(Path("data") / "templates")
        self.detector = LoginStateDetector(hwnd, self.memory, self.templates)

        self.phase = Phase.CREDENTIALS
        self.phase_since = time.time()
        self.credential_errors = 0
        # Voltas à lista de servidores sem conseguir sair dela. Ver
        # `VOLTAS_NA_LISTA_DE_SERVIDORES`.
        self.voltas_no_servidor = 0
        self.last_enter_attempt = 0.0
        self.last_heartbeat = 0.0
        self.connected_since: float | None = None
        self.enter_attempts = 0
        self.blind_warned = False
        self._anchor_warned = False
        self.modal_since = 0.0
        # Persistência do modal antes de conectar, e quantas vezes os servidores
        # apareceram fora do ar. O contador cresce a espera entre tentativas.
        self.pre_server_modal_since = 0.0
        self.server_down_hits = 0
        self.connecting_since = 0.0
        self.login_screen_since = 0.0
        self._last_log: str | None = None
        self._queue_logged = False
        self._capture_warned = False
        # O nome do personagem foi lido da MEMÓRIA (e não deduzido)? Só nesse
        # caso o supervisor sobrescreve o nick guardado na conta.
        self.char_confirmado = False

    # -- âncoras por template ----------------------------------------------

    def _anchored(
        self,
        grupo: str,
        nome: str,
        fallback: tuple[int, int],
        frame=None,
    ) -> tuple[int, int]:
        """Resolve uma coordenada a partir de um elemento LOCALIZADO na tela.

        Como a interface do jogo tem tamanho fixo em pixels, o deslocamento
        entre dois elementos da mesma janela é constante em qualquer resolução.
        Então localizar um elemento por imagem e somar o deslocamento é mais
        confiável que confiar em coordenada absoluta -- e é o que faz o bot
        funcionar fora de 1024x768.

        Se o template não casar, usa a coordenada derivada por âncora de tela.
        """
        entrada = TEMPLATE_ANCHORS.get(grupo)
        if entrada is None:
            return fallback
        template, deslocamentos = entrada
        delta = deslocamentos.get(nome)
        if delta is None:
            return fallback
        ponto = self.detector.find_button(template, frame=frame)
        if ponto is None:
            return fallback

        resultado = (ponto[0] + delta[0], ponto[1] + delta[1])

        # REDE DE SEGURANÇA, válida em QUALQUER resolução.
        #
        # O `fallback` é calculado a partir do tamanho real da janela, então os
        # dois caminhos -- localizar por imagem e derivar por âncora de tela --
        # devem concordar. Medi essa concordância em duas resoluções: a diferença
        # entre eles ficou em 3 px. Uma divergência grande indica problema na
        # captura, e um erro de poucos pixels aqui é destrutivo, porque os campos
        # de usuário e senha ficam a 30 px um do outro.
        #
        # NOTA HISTÓRICA: esta checagem já causou um bug ao comparar com as
        # coordenadas de 1024x768 enquanto o jogo rodava em 1280x960 -- ela
        # descartava a posição CORRETA achada por imagem. Por isso o `fallback`
        # tem que vir sempre do tamanho medido da janela, nunca da configuração.
        desvio = max(abs(resultado[0] - fallback[0]),
                     abs(resultado[1] - fallback[1]))
        if desvio > MAX_ANCHOR_DEVIATION:
            if not self._anchor_warned:
                self._anchor_warned = True
                self.log.warning(
                    "A posição de '%s' achada por imagem (%s) está %s px longe "
                    "da calculada para esta janela (%s). Usando a calculada.",
                    nome, resultado, desvio, fallback,
                )
            return fallback
        return resultado

    # -- utilidades --------------------------------------------------------

    def _abort_if_stopped(self) -> None:
        """Verifica parada E pausa.

        A pausa é verificada aqui e também antes de cada clique, porque o login
        é uma sequência longa de ações e antes disso clicar em Pausar não tinha
        efeito nenhum até a sequência terminar.
        """
        if self.stop_check():
            raise StopDuringLogin("parada solicitada durante o login")
        while self.pause_check():
            if self.stop_check():
                raise StopDuringLogin("parada solicitada durante a pausa")
            time.sleep(0.075)

    def _esperar(self, segundos: float) -> None:
        """Dorme respeitando parada e pausa. O `tick()` do login.

        CRASH DE 25/08/2026: aqui estava `self.tick(0.5)`, e `LoginSequence`
        nunca teve `tick` -- é método do `BotContext`, que no login ainda não
        existe. As duas chamadas ficaram no ramo do *"Connecting to the
        server"*, então só estouravam quando o servidor engasgava: justo o
        momento em que o relogin precisa funcionar.

        Cumprida em FATIAS pelo mesmo motivo do `BotContext.tick`: espera de
        meio segundo em uma chamada só faz o botão Parar parecer travado.
        """
        fim = time.time() + segundos
        while True:
            self._abort_if_stopped()
            restante = fim - time.time()
            if restante <= 0:
                return
            time.sleep(min(FATIA_DA_ESPERA_DO_LOGIN, restante))

    def _set_phase(self, phase: Phase) -> None:
        if phase != self.phase:
            self.log.info("Fase do login: %s", phase.value)
        self.phase = phase
        self.phase_since = time.time()

    def _phase_expired(self) -> bool:
        limit = PHASE_TIMEOUT[self.phase]
        if limit is None:
            return False
        return (time.time() - self.phase_since) > limit

    def _log_once(self, message: str) -> None:
        if message != self._last_log:
            self.log.info(message)
            self._last_log = message

    def _window_alive(self) -> bool:
        return self.input.window_exists()

    def _click(self, ponto: tuple[int, int]) -> None:
        """Clique que respeita pausa e parada.

        Chama `self.input.left_click`, NÃO `self._click`. Uma substituição
        automática mal feita trocou a chamada interna pela própria função e
        produziu recursão infinita: o login quebrava com RecursionError no
        primeiro clique.
        """
        self._abort_if_stopped()
        self.input.left_click(*ponto)

    def _type(self, texto: str, rotulo: str = "texto") -> int:
        """Digita pela funcao BLINDADA, e diz quantos caracteres sairam.

        `type_string_safely` e nao `type_text`: o login e o unico lugar do bot
        que digita SEGREDO, e e onde o vazamento de 09/09/2026 aconteceu. O
        `rotulo` existe para o log dizer O QUE estava sendo digitado sem nunca
        dizer O QUE ERA -- senha em arquivo de log e senha vazada.

        NAO ENGOLE `TextoRecusado`: texto recusado significa que o que ia ser
        digitado nao era o login nem a senha desta conta, e seguir o login com
        credencial errada queima tentativa no servidor -- o caminho para a
        conta bloqueada.
        """
        self._abort_if_stopped()
        return self.input.type_string_safely(texto, rotulo=rotulo)

    def _clear(self, vezes: int = 16) -> None:
        self._abort_if_stopped()
        self.input.clear_field(vezes)

    # -- ações de fase -----------------------------------------------------

    def _do_credentials(self) -> None:
        c = self.coords
        self.log.info("Preenchendo credenciais de '%s'", self.account.login)
        # O ciclo recomeçou: as voltas na lista de servidores voltam a zero.
        self.voltas_no_servidor = 0

        campo_conta = self._anchored("login", "login_account", c.login_account)
        campo_senha = self._anchored("login", "login_password", c.login_password)
        botao_ok = self._anchored("login", "login_ok", c.login_ok)

        self._click(campo_conta)
        sleep(0.35)
        self._clear(50)
        sleep(0.15)
        # CONFERE QUE SAIU INTEIRO. A digitacao para sozinha quando a janela
        # deixa de ser confiavel no meio -- e login pela metade nao e login: e
        # uma tentativa queimada no servidor, com a senha certa indo para um
        # campo que ja tem lixo. Abortar aqui devolve a conta ao backoff.
        saiu = self._type(self.account.login, rotulo="login")
        if saiu != len(self.account.login):
            raise LoginError(
                f"o login saiu pela metade ({saiu} de "
                f"{len(self.account.login)} caracteres): a janela deixou de ser "
                "confiavel no meio da digitacao")
        sleep(0.3)

        self._click(campo_senha)
        sleep(0.25)
        # Poucos BACKSPACE de propósito. O campo de senha começa vazio num
        # cliente recém-aberto, e se por algum motivo o foco NÃO tiver mudado,
        # 50 backspaces apagariam o usuário que acabou de ser digitado --
        # exatamente o laço infinito que isso já causou uma vez.
        self._clear(16)
        sleep(0.15)
        senha = self.account.get_password()
        saiu = self._type(senha, rotulo="senha")
        if saiu != len(senha):
            raise LoginError(
                f"a senha saiu pela metade ({saiu} de {len(senha)} "
                "caracteres): a janela deixou de ser confiavel no meio da "
                "digitacao")
        sleep(0.3)

        self._click(botao_ok)
        sleep(1.25)
        self._set_phase(Phase.SERVER)

    def _do_server(self, det: Detection | None = None) -> None:
        """Seleciona o servidor da conta e confirma.

        A lista abre com uma linha JÁ selecionada: clica e CONFIRMA o realce
        antes do Ok.
        """
        c = self.coords
        wanted = c.normalize_server(self.account.server)
        if c.server_point(wanted) is None:
            # Configuração: o nome nem está em `server_rows`. Cancel e não
            # `LoginError` -- o erro seco deixava a janela parada na lista.
            self._sair_da_lista_de_servidores(
                f"servidor '{self.account.server}' não está na lista atual "
                f"(opções: {', '.join(c.server_rows)})")
            return
        if wanted != self.account.server:
            self.log.info("Servidor '%s' virou '%s' na lista atual",
                          self.account.server, wanted)

        # A LINHA VEM DA TELA (a estática põe a conta em OUTRO servidor) e o
        # QUADRO VEM DO LAÇO: capturar de novo foi o defeito de 23/09/2026 -- a
        # segunda captura pode falhar sozinha (ver `Detection.frame`), e com
        # quadro nulo o bot cancelou 560 vezes com o servidor na tela.
        quadro = det.frame if det is not None else None
        primeira = self._anchored("server", "server_first_row",
                                  (c.server_row_x, c.server_first_row_y),
                                  frame=quadro)
        lida = self.detector.linha_do_servidor(
            quadro, wanted, primeira, len(c.server_rows))
        # "Não achei" só vale se DEU PARA OLHAR: sem quadro é "não sei".
        if (lida is None and quadro is not None
                and self.detector.sabe_reconhecer(wanted)):
            self._sair_da_lista_de_servidores(
                f"o servidor '{wanted}' NÃO está na lista (fora do ar?)",
                esperar=ESPERA_PELO_SERVIDOR_FORA_DO_AR)
            return
        # Sem recorte do nome, o índice estático é a reserva.
        indice = lida if lida is not None else c.server_index(wanted)
        ultimo_quadro = quadro
        # `None` = sem captura; `False` = olhei e a linha certa NÃO realçou.
        confirmou_a_linha = None
        for attempt in range(1, TENTATIVAS_DE_SELECAO + 1):
            alvo = (primeira[0], primeira[1] + indice * c.server_row_height)
            self.log.info("Selecionando servidor '%s' em %s (tentativa %s)",
                          wanted, alvo, attempt)
            self._click(alvo)
            sleep(0.4)

            det = self.detector.detect()
            if not det.capture_ok:
                # Sem imagem não há como confirmar; segue em frente.
                self.log.debug("Sem imagem para confirmar a seleção")
                break
            ultimo_quadro = det.frame

            selecionado = find_highlighted_row(
                det.frame, primeira[1], c.server_row_height,
                len(c.server_rows),
                center_x=primeira[0],
            )
            esperado = indice
            confirmou_a_linha = selecionado == esperado
            if confirmou_a_linha:
                self.log.info("Servidor '%s' confirmado como selecionado", wanted)
                break
            if selecionado is None:
                self.log.warning("Nenhuma linha realçada; clicando de novo")
            else:
                self.log.warning(
                    "Está selecionado '%s' em vez de '%s'; clicando de novo",
                    c.server_rows[selecionado], wanted,
                )
        else:
            self.log.warning("Não confirmei a seleção de '%s'", wanted)

        # SEM PROVA DA LINHA, NÃO SE APERTA O Ok -- a rede de quando o nome
        # não foi reconhecido e o índice estático errou. `None` (sem captura)
        # segue: "não sei" não bloqueia. Ver `docs/decisoes/login-e-relogin.md`.
        if confirmou_a_linha is False:
            self._sair_da_lista_de_servidores(
                f"a linha de '{wanted}' não ficou realçada em "
                f"{TENTATIVAS_DE_SELECAO} tentativas -- o servidor saiu da "
                f"lista ou ela mudou de ordem, e apertar Ok entraria em OUTRO "
                f"servidor")
            return

        # O STATUS ANTES DE GASTAR O Ok, e fora do laço: dentro dele só
        # valeria com o realce confirmado.
        if self.detector.servidor_offline(ultimo_quadro, primeira, indice):
            self._sair_da_lista_de_servidores(
                f"o servidor '{wanted}' está OFFLINE na lista",
                esperar=ESPERA_PELO_SERVIDOR_FORA_DO_AR)
            return

        # CHEGAR AQUI DE NOVO = o Ok anterior não saiu da lista. Conta VOLTAS
        # à mesma tela, não cliques: a fase só volta para `SERVER` com a imagem
        # mostrando a lista.
        self.voltas_no_servidor += 1
        if self.voltas_no_servidor > VOLTAS_NA_LISTA_DE_SERVIDORES:
            self._sair_da_lista_de_servidores(
                f"o Ok não tirou a conta da lista em "
                f"{VOLTAS_NA_LISTA_DE_SERVIDORES} voltas (servidor '{wanted}' "
                f"Offline ou reiniciando?)")
            return

        ok_servidor = self._anchored("server", "server_ok", c.server_ok)
        self._click(ok_servidor)
        sleep(1.75)
        self._set_phase(Phase.ENTERING)

    def _sair_da_lista_de_servidores(self, motivo: str,
                                     esperar: float = 0.0) -> None:
        """Sai da lista pelo CANCEL e recomeça o login. A única saída que existe.

        O Cancel volta ao login e o ciclo recomeça com a lista RELIDA. Não
        levanta: sair pela porta é caminho normal. Relato em `docs/decisoes`.
        """
        self.log.warning("%s — saindo da lista pelo Cancel.", motivo)
        cancel = self._anchored("server", "server_cancel",
                                self.coords.server_cancel)
        self._click(cancel)
        self._set_phase(Phase.CREDENTIALS)
        if esperar:
            # Espera LEGÍTIMA: renova o relógio das telas, senão o
            # `PRE_SERVER_TIMEOUT` mata o ciclo que faz a coisa certa.
            self._prazo_das_telas = time.time() + PRE_SERVER_TIMEOUT
            self.log.info("Tentando de novo em %.0fs.", esperar)
            self._esperar(esperar)

    def _try_enter_world(self, det: Detection) -> None:
        """Seleciona o personagem e entra. Chamado a cada 20 s.

        NUNCA sai sem clicar. A versão anterior desistia quando não conseguia
        localizar o botão "Enter Game" na imagem -- e como a captura falha de
        forma intermitente, isso travava o bot para sempre na tela de seleção,
        vendo os personagens e não fazendo nada.

        Clicar aqui é sempre seguro: a fila é tratada em outro caminho
        (`_handle_queue`), e as coordenadas da plaquinha (y=640) e do Enter Game
        (y=735) ficam bem abaixo do único botão da caixa de fila, o "Cancel"
        (y=443). Então, se ainda estiver na fila, o clique não faz nada; quando
        os personagens aparecerem, ele entra.
        """
        c = self.coords
        position = self.account.position
        plate = c.char_slots.get(position)
        if plate is None:
            raise LoginError(f"posição de personagem inválida: '{position}'")

        # A plaquinha fica a um deslocamento fixo do botão Enter Game. Derivar
        # dele é o que faz isto funcionar em qualquer resolução.
        chave = {"Left": "char_left", "Center": "char_center",
                 "Right": "char_right"}[position]
        plate = self._anchored("char", chave, plate, frame=det.frame)

        self.enter_attempts += 1
        self.log.info("Clicando na plaquinha do personagem (%s) em %s", position, plate)
        self._click(plate)
        sleep(0.6)

        # Reaproveita o quadro já capturado; se o botão for localizado, clica
        # exatamente nele. Se não, usa a coordenada conhecida.
        found = self.detector.find_button("btn_enter_game.png", frame=det.frame)
        target = found or c.enter_game
        origem = "localizado na imagem" if found else "coordenada padrão"
        self.log.info("Clicando em Enter Game em %s (%s)", target, origem)
        self._click(target)
        sleep(1.5)

    # -- ações de exceção --------------------------------------------------

    def _handle_login_error(self, point: tuple[int, int] | None) -> None:
        self.credential_errors += 1
        self.log.warning("Erro de usuário/senha (%s de %s)",
                         self.credential_errors, MAX_CREDENTIAL_ERRORS)

        ok_point = self.coords.login_error_close
        if point is not None:
            dx, dy = OK_OFFSET_LOGIN_ERROR
            ok_point = (point[0] + dx, point[1] + dy)
        self._click(ok_point)
        sleep(0.6)

        # Se não fechou, tenta a coordenada fixa conhecida.
        if self.detector.detect().screen is LoginScreen.LOGIN_ERROR:
            self._click(self.coords.login_error_close)
            sleep(0.6)

        if self.credential_errors >= MAX_CREDENTIAL_ERRORS:
            raise BadCredentials(
                f"o servidor recusou a conta '{self.account.login}' "
                f"{self.credential_errors} vezes. Confira usuário e senha."
            )
        self._set_phase(Phase.CREDENTIALS)

    def _handle_conn_interrupted(self, point: tuple[int, int] | None) -> None:
        """Fecha o aviso de conexão interrompida.

        Dois avisos diferentes usam este caminho:
          "Connection interrupted."                          -> volta ao login
          "Connection interrupted, please open client again." -> FECHA o jogo
        Não é preciso distinguir: clica em Ok e observa o que acontece. Se o
        cliente morreu, levanta ClientClosed e o supervisor relança essa conta.
        """
        self.log.warning("Conexão interrompida; fechando o aviso")

        ok_point = self.coords.confirm_ok
        if point is not None:
            dx, dy = OK_OFFSET_CONN_INTERRUPTED
            ok_point = (point[0] + dx, point[1] + dy)
        self._click(ok_point)
        sleep(1.0)

        if not self._window_alive() or not self.memory.alive():
            raise ClientClosed(
                "o cliente foi encerrado pelo aviso de conexão interrompida"
            )

        # Sobreviveu: normalmente o jogo volta para a tela de login.
        self.log.info("Cliente sobreviveu; recomeçando o login")
        self.enter_attempts = 0
        self.blind_warned = False
        self._set_phase(Phase.CREDENTIALS)

    def _handle_login_busy(self, point: tuple[int, int] | None) -> None:
        """Fecha o aviso "Login server is busy now, please try again."

        Não é erro de credencial nem queda: o servidor de login está
        sobrecarregado. A ação certa é fechar e tentar de novo, sem contar como
        senha errada -- contar levaria o bot a desistir de uma conta boa.
        """
        self.log.info("Servidor de login ocupado; fechando o aviso e repetindo")
        ok = self._anchored("login_busy", "ok", self.coords.login_error_close)
        self._click(ok)
        sleep(0.75)
        self._set_phase(Phase.CREDENTIALS)

    def _handle_connecting(self, point: tuple[int, int] | None) -> None:
        """"Connecting to the server, please wait a moment." — espera COM PRAZO.

        =================================================================
        POR QUE ESTA TELA NÃO É ERRO, MAS PRECISA DE PRAZO
        =================================================================

        Ela é o cliente tentando conectar, e na maior parte das vezes some
        sozinha em segundos -- fechá-la de imediato jogaria fora um login que ia
        dar certo. Mas quando o servidor do jogo trava, ela FICA, e o login para
        ali sem nada no log dizendo por quê: não é erro, não tem botão Ok, e o
        detector antes deste nem tinha um nome para ela.

        Pior: ela marcava **0.787** contra o `state_conn_prefix` (a palavra
        "Connection"), a 0.013 do limiar de 0.80. Numa renderização um pouco
        diferente ela seria classificada como "conexão interrompida" e o bot
        clicaria no deslocamento do botão **Ok** -- e esta caixa tem **Cancel**,
        em outro lugar.

        O prazo é `SEGUNDOS_CONECTANDO`, número do usuário: "é uma espera legítima, mas
        caso leve mais de 6 segundos pode clicar em Cancel, pois deve ter travado
        por causa do servidor do jogo". Estourado, clica em Cancel e a sequência
        recomeça -- sem matar a janela, que é caro e aqui não é preciso.
        """
        agora = time.time()
        if self.connecting_since == 0.0:
            self.connecting_since = agora
            self._log_once("Conectando ao servidor; aguardando")
            self._esperar(0.5)
            return
        if agora - self.connecting_since <= SEGUNDOS_CONECTANDO:
            self._esperar(0.5)
            return

        self.connecting_since = 0.0
        self.log.warning(
            "Preso em 'Connecting to the server' por mais de %.0f s — o "
            "servidor travou. Clicando em Cancel para recomeçar.",
            SEGUNDOS_CONECTANDO)
        if point is not None:
            dx, dy = CANCEL_OFFSET_CONNECTING
            self._click((point[0] + dx, point[1] + dy))
        self._set_phase(Phase.CREDENTIALS)

    def _handle_acquiring_ip(self, point: tuple[int, int] | None) -> None:
        """Fecha o aviso "Acquiring server IP address." e volta a tentar.

        =================================================================
        O QUE ESTE AVISO SIGNIFICA
        =================================================================

        Os SERVIDORES ESTÃO FORA DO AR. O cliente não conseguiu nem descobrir o
        endereço do servidor, ou seja, não é problema de conta, de senha nem de
        fila -- não há nada errado do nosso lado e não há nada a corrigir.

        A ação certa é clicar em Ok e continuar tentando. Duas coisas que NÃO
        podem acontecer:

          * contar como erro de credencial. Três "erros" e o supervisor
            desistiria de uma conta perfeitamente boa;
          * desistir. Quando os servidores voltam, quem já está tentando entra
            primeiro -- e a fila que vem depois de uma queda é a pior do dia.

        A espera CRESCE entre tentativas (20 s, 40 s, 80 s, até 2 min). Servidor
        fora do ar não volta em dois segundos, e martelar o login a cada volta só
        encheria o log de milhares de linhas iguais -- que é justamente o que
        esconderia o momento em que ele voltou.
        """
        self.server_down_hits += 1
        espera = min(
            ESPERA_SERVIDOR_FORA * (2 ** (self.server_down_hits - 1)),
            ESPERA_SERVIDOR_FORA_MAX,
        )

        ok_point = self.coords.server_ip_ok
        if point is not None:
            dx, dy = OK_OFFSET_ACQUIRING_IP
            ok_point = (point[0] + dx, point[1] + dy)

        self.log.warning(
            "SERVIDORES FORA DO AR (\"Acquiring server IP address\", ocorrência "
            "%s). Não é erro de conta nem senha. Fechando o aviso e tentando de "
            "novo em %.0fs.",
            self.server_down_hits, espera,
        )
        self._click(ok_point)
        sleep(0.6)

        # O aviso pode reaparecer sozinho enquanto os servidores não voltam. Isso
        # é esperado: a próxima volta do laço o fecha de novo.
        self._abort_if_stopped()
        sleep(espera, spread=0.05)
        self._set_phase(Phase.CREDENTIALS)

    def _modal_travando_antes_do_servidor(self) -> bool:
        """Aviso na tela ANTES de conectar, reconhecido só pela memória.

        =================================================================
        POR QUE ISTO EXISTE, E POR QUE NÃO DEPENDE DE IMAGEM
        =================================================================

        O cliente reaproveita o MESMO quadro de mensagem para vários avisos, e
        cada aviso novo que aparecer vai cair aqui antes de alguém recortar um
        template para ele. Foi o caso do "Acquiring server IP address.": um aviso
        que nunca tinha aparecido, com Ok no mesmo lugar dos outros, e que travava
        o login em silêncio -- o bot ficava preenchendo usuário e senha atrás de
        uma caixa modal que engolia tudo.

        A flag de modal na memória não diz QUAL aviso é, mas diz que existe um. E
        antes de conectar isso já basta para decidir: nas telas de login e de
        servidor não existe caixa de confirmação legítima que o bot queira manter
        aberta. Se há modal e ele persiste, o certo é fechar e repetir.

        A persistência é obrigatória. A flag é compartilhada com caixas legítimas
        de passagem, e fechar na primeira leitura clicaria em cima de coisas que
        se resolvem sozinhas.

        Devolve True se fechou algo.
        """
        agora = time.time()
        if not self.memory.modal_open():
            self.pre_server_modal_since = 0.0
            return False

        if self.pre_server_modal_since == 0.0:
            self.pre_server_modal_since = agora
            return False
        if agora - self.pre_server_modal_since < MODAL_PRE_SERVER_SECONDS:
            return False

        self.pre_server_modal_since = 0.0
        self.log.warning(
            "Há um aviso na tela há mais de %.0fs e ainda não conectei. Não sei "
            "qual é (sem imagem para reconhecer), mas antes do servidor nenhum "
            "aviso deve ficar aberto: clicando no Ok. Se isto se repetir, é "
            "provavelmente \"Acquiring server IP address\" — servidores fora do "
            "ar.",
            MODAL_PRE_SERVER_SECONDS,
        )
        # Os dois pontos são praticamente o mesmo lugar -- é o mesmo quadro de
        # mensagem. Clicar nos dois cobre a variação de poucos pixels entre eles
        # sem custo nenhum: um clique fora de botão na tela de login não faz nada.
        self._click(self.coords.server_ip_ok)
        sleep(0.3)
        self._click(self.coords.login_error_close)
        sleep(0.5)
        self._set_phase(Phase.CREDENTIALS)
        return True

    def _handle_conn_failed(self, point: tuple[int, int] | None) -> None:
        """Fecha o aviso "Connection failed, please try again later."

        Detalhe que importa: esta caixa tem botão **Cancel**, não Ok. Clicar na
        posição do Ok das outras caixas não fecharia nada.
        """
        self.log.warning("Falha de conexão; fechando o aviso e repetindo")
        cancel = self._anchored("conn_failed", "cancel", self.coords.login_error_close)
        self._click(cancel)
        sleep(0.75)
        if not self._window_alive() or not self.memory.alive():
            raise ClientClosed("o cliente encerrou após a falha de conexão")
        self._set_phase(Phase.CREDENTIALS)

    def _handle_queue(self) -> None:
        """Na fila, apenas esperar.

        O único botão da tela de fila é o "Cancel" -- clicar em qualquer coisa
        ali só teria como efeito sair da fila. E a fila NÃO conta como falha:
        servidor cheio chega a centenas de posições e pode levar muito tempo.
        """
        if not self._queue_logged:
            self.log.info("Na fila de login. Aguardando, sem clicar em nada.")
            self._queue_logged = True
        sleep(5.0, spread=0.05)

    def _finish(self) -> str:
        """Confirma a entrada no mundo e batiza a janela.

        NUNCA falha por não conseguir ler o nome do personagem. O login já deu
        certo neste ponto -- o personagem está no mundo. Tratar uma leitura de
        string malsucedida como "falha de login" fazia o supervisor MATAR um
        cliente que estava perfeitamente logado e começar tudo de novo.

        O nome batiza a janela, e o título da janela é como o bot reconhece esta
        conta numa próxima execução. Por isso a ordem de preferência importa:
        memória > nick já guardado na conta > login. Cair direto no login
        APAGARIA do título a única pista que dispensa a fila de três horas.

        `char_confirmado` diz se o nome veio da memória. Só o que vem da memória
        é confiável o bastante para sobrescrever o nick guardado.
        """
        char_name = self.memory.char_name()
        position = self.memory.position()
        self.char_confirmado = bool(char_name)

        if char_name:
            self.log.info("No mundo como '%s' em %s", char_name, position)
            titulo = char_name
        elif self.account.last_char_name:
            char_name = self.account.last_char_name
            titulo = char_name
            self.log.warning(
                "No mundo (posição %s), mas não consegui ler o nome do "
                "personagem agora. Usando o nick já guardado ('%s') para "
                "batizar a janela — assim o reconhecimento continua valendo na "
                "próxima execução.",
                position, char_name,
            )
        else:
            char_name = self.account.login
            titulo = f"{self.account.login} [BlazesBot]"
            self.log.warning(
                "No mundo (posição %s), mas não consegui ler o nome do "
                "personagem na memória e esta conta ainda não tem nick "
                "guardado. Usando o login para batizar a janela. Isso não "
                "impede o login nem o farm; o nick é gravado assim que a "
                "memória ficar legível.",
                position,
            )

        # Renomear a janela é o que permite identificar cada instância quando
        # há várias contas abertas -- o cliente dá o mesmo título a todas.
        try:
            win32gui.SetWindowText(self.hwnd, titulo)
            sleep(0.25)
        except Exception as exc:
            self.log.debug("Não foi possível renomear a janela: %s", exc)
        return char_name

    # -- laço principal ----------------------------------------------------

    def _advance_phase(self, det: Detection) -> None:
        """Executa a fase atual quando nada excepcional foi detectado."""
        if self.phase is Phase.CREDENTIALS:
            # Se o título já traz servidor, o login passou -- pula para frente.
            if det.connected:
                self.log.info("Servidor '%s' já no título; aguardando entrar",
                              det.server_in_title)
                self._set_phase(Phase.ENTERING)
                return
            if self._phase_expired():
                self._set_phase(Phase.CREDENTIALS)
            self._do_credentials()

        elif self.phase is Phase.SERVER:
            if det.connected:
                self._set_phase(Phase.ENTERING)
                return
            self._do_server(det)

        elif self.phase is Phase.ENTERING:
            # Perdeu o servidor do título: caiu de volta para o login.
            if not det.connected and det.screen in (
                LoginScreen.LOGIN_SCREEN, LoginScreen.PRE_SERVER
            ):
                self.log.info("Voltou para antes do servidor; refazendo o login")
                self._set_phase(Phase.CREDENTIALS)
                return

            now = time.time()
            if self.connected_since is None:
                self.connected_since = now

            # Aviso periódico de que continua vivo. Sem isso, uma fila de três
            # horas deixaria o log mudo e pareceria travamento.
            if now - self.last_heartbeat >= WAIT_HEARTBEAT_SECONDS:
                self.last_heartbeat = now
                waited = int(now - self.connected_since)
                # Os campos entre colchetes são diagnóstico: servem para
                # descobrir quais sinais existem durante a fila quando a
                # captura de imagem não está disponível. Se o texto da fila
                # muda a cada aviso, ele é um bom indicador de "ainda vivo".
                self.log.info(
                    "Aguardando entrar há %dmin. Sem limite de tempo: só saio "
                    "daqui se entrar, se aparecer erro na tela ou se o cliente "
                    "cair. [captura=%s | modal=%s | fila=%r]",
                    waited // 60,
                    "sim" if det.capture_ok else "nao",
                    self.memory.modal_open(),
                    self.memory.queue_text(),
                )

            # Aviso na tela (conexão interrompida, erro) detectado pela
            # memória, sem depender de imagem. O flag é compartilhado com
            # caixas de confirmação legítimas, por isso exige persistência.
            if self.memory.modal_open():
                if self.modal_since == 0.0:
                    self.modal_since = now
                elif now - self.modal_since >= MODAL_CONFIRM_SECONDS:
                    self.modal_since = 0.0
                    self.log.warning(
                        "Aviso persistente na tela (flag de modal). Fechando com Ok."
                    )
                    self._handle_conn_interrupted(None)
                    return
            else:
                self.modal_since = 0.0

            if now - self.last_enter_attempt >= ENTER_RETRY_SECONDS:
                # Se o bot já tentou várias vezes ÀS CEGAS e não conseguiu
                # confirmar a entrada, ele espaça as tentativas. Clicar em Enter
                # Game com o personagem já dentro do jogo o faz andar pelo mapa,
                # e ele não tem como saber que já entrou se não lê a memória nem
                # captura a tela.
                #
                # O contador é zerado sempre que a IMAGEM confirma a tela de
                # seleção (ver o laço principal): ali não há dúvida nenhuma, e o
                # limite não se aplica.
                #
                # E ele não desliga mais o clique para sempre. A versão anterior
                # parava de vez, e uma conta que só tinha tido azar (captura
                # intermitente, clique engolido) ficava horas na tela de seleção.
                # Agora ele passa a tentar de forma espaçada -- raro o bastante
                # para não arrastar o personagem, frequente o bastante para
                # destravar sozinho.
                cego = self.enter_attempts >= MAX_BLIND_ENTER_ATTEMPTS
                if cego and now - self.last_enter_attempt < ESPERA_CEGA_SEGUNDOS:
                    if not self.blind_warned:
                        self.blind_warned = True
                        self.log.error(
                            "Cliquei em Enter Game %s vezes e não consigo CONFIRMAR "
                            "que entrei no mundo. Vou continuar tentando, mas a "
                            "cada %.0f min, para não arrastar o personagem pelo "
                            "mapa caso ele já esteja dentro. Provável causa: não "
                            "estou conseguindo ler a memória do cliente nem "
                            "capturar a tela. Rode 2-DIAGNOSTICO.bat e "
                            "6-TESTE-CAPTURA.bat e me mande a saída.",
                            self.enter_attempts, ESPERA_CEGA_SEGUNDOS / 60,
                        )
                    sleep(2.5)
                    return
                if cego:
                    self.log.warning(
                        "Nova tentativa espaçada de Enter Game (%sª), depois de "
                        "%.0f min sem confirmar a entrada.",
                        self.enter_attempts + 1, ESPERA_CEGA_SEGUNDOS / 60,
                    )
                self.last_enter_attempt = now
                self._try_enter_world(det)
            else:
                sleep(1.0)

    def run(self) -> str:
        missing = self.detector.missing_templates()
        if missing:
            self.log.warning("Templates ausentes em data/templates: %s",
                             ", ".join(missing))
        opcionais = self.detector.optional_missing()
        if opcionais:
            self.log.info(
                "Templates opcionais ausentes (%s). Não impedem nada: há um "
                "caminho alternativo para cada um. Recortá-los só deixa o "
                "reconhecimento imediato.", ", ".join(opcionais),
            )

        self._set_phase(Phase.CREDENTIALS)
        self._prazo_das_telas = time.time() + PRE_SERVER_TIMEOUT

        while True:
            self._abort_if_stopped()

            if not self._window_alive():
                raise ClientClosed("a janela do cliente desapareceu durante o login")

            det = self.detector.detect()

            # O relógio das telas iniciais só corre enquanto NÃO estamos
            # conectados. Ao conectar, ele é desligado de vez -- é isso que
            # permite esperar a fila pelo tempo que ela levar.
            # `connected` é só O SERVIDOR NO TÍTULO, e o cliente põe o nome
            # lá quando a LINHA É ESCOLHIDA -- não quando se entra. Medido no
            # print de 22/09/2026: título "…| Light in the Darkness |…" COM a
            # lista aberta. Desligar o relógio ali tirava o último prazo de uma
            # conta parada na lista. Ver `docs/decisoes/login-e-relogin.md`.
            na_lista_de_servidores = det.screen is LoginScreen.SERVER_LIST
            if det.connected and not na_lista_de_servidores:
                self._prazo_das_telas = float("inf")
            elif self._prazo_das_telas == float("inf"):
                # Caiu de volta para antes do servidor: religa o relógio.
                self._prazo_das_telas = time.time() + PRE_SERVER_TIMEOUT
                self.connected_since = None
                self.last_heartbeat = 0.0

            if time.time() > self._prazo_das_telas:
                raise LoginError(
                    "as telas de login/servidor não avançaram em "
                    f"{PRE_SERVER_TIMEOUT / 60:.0f} minutos. Confira resolução "
                    "1024x768, modo janela e se o bot está como administrador."
                )

            # Avisa uma única vez se a captura não está disponível, para o log
            # explicar por que o bot está operando às cegas.
            if not det.capture_ok and not self._capture_warned:
                self._capture_warned = True
                self.log.warning(
                    "Sem captura de imagem desta janela (PrintWindow devolveu "
                    "quadro vazio). O login vai seguir pelo roteiro, guiado pelo "
                    "título da janela e pela memória."
                )

            self._log_once(f"Tela: {det.screen.value}"
                           + (f" | servidor: {det.server_in_title}" if det.server_in_title else ""))

            # 1. Chegou ao destino.
            if det.screen is LoginScreen.IN_WORLD:
                return self._finish()

            # 2. Situações que exigem tratamento específico, se detectadas.
            if det.screen is LoginScreen.LOGIN_BUSY:
                self._handle_login_busy(det.point)
                continue
            if det.screen is LoginScreen.CONN_FAILED:
                self._handle_conn_failed(det.point)
                continue
            if det.screen is LoginScreen.CONNECTING:
                self._handle_connecting(det.point)
                continue
            if det.screen is LoginScreen.LOGIN_ERROR:
                self._handle_login_error(det.point)
                continue
            if det.screen is LoginScreen.CONN_INTERRUPTED:
                self._handle_conn_interrupted(det.point)
                continue
            if det.screen is LoginScreen.SERVER_IP:
                self._handle_acquiring_ip(det.point)
                continue
            if det.screen is LoginScreen.QUEUE:
                self._handle_queue()
                continue

            # 2b. Aviso NÃO reconhecido travando o login, visto pela memória.
            #
            # Rede de segurança para avisos que ainda não têm template -- e sempre
            # vai aparecer um novo. Só vale antes de conectar: depois disso o
            # tratamento é o de `_advance_phase`, que sabe distinguir fila de
            # desconexão.
            if not det.connected and self._modal_travando_antes_do_servidor():
                continue

            # 3. Telas conhecidas que confirmam a fase esperada.
            if det.screen is LoginScreen.LOGIN_SCREEN:
                # Cronômetro da tela de usuário e senha. Essa tela responde em
                # segundos; se o bot está nela há minutos sem avançar, o cliente
                # travou num estado do qual não sai por clique -- reabrir é mais
                # rápido e mais confiável que insistir.
                agora = time.time()
                if self.login_screen_since == 0.0:
                    self.login_screen_since = agora
                elif agora - self.login_screen_since > LOGIN_SCREEN_MAX_SECONDS:
                    # MATA A JANELA E REABRE. Isto REVERTE a decisão anterior
                    # ("não fecha o jogo, perder a janela custa horas de fila"),
                    # por escolha do usuário em 18/08/2026, com o custo aceito:
                    # se a fila estiver longa, reabrir pode custar horas.
                    #
                    # O que mudou o veredito: recomeçar a sequência na MESMA
                    # janela não tirava o cliente do estado travado -- ele fica
                    # parado na tela de usuário e senha indefinidamente, e a
                    # conta simplesmente não volta. Uma conta parada a noite
                    # inteira custa mais que a fila.
                    #
                    # ESTE É O ÚNICO MOTIVO PARA MATAR UMA JANELA DE JOGO. E só
                    # aqui: o cronômetro conta apenas na PRIMEIRA tela (usuário
                    # e senha) e é zerado assim que o login avança para a lista
                    # de servidores ou para a seleção de personagem -- ver o
                    # `else` logo abaixo, que faz `login_screen_since = 0.0`.
                    self.log.warning(
                        "Parado na tela de usuário e senha por mais de %.1f "
                        "minutos sem avançar. Fechando o cliente e reabrindo — "
                        "é o único caso em que o bot mata uma janela do jogo.",
                        LOGIN_SCREEN_MAX_SECONDS / 60,
                    )
                    kill_client(self.pid)
                    raise ClientClosed(
                        "cliente travado na tela de login; janela encerrada "
                        "para reabrir")
                if self.phase is not Phase.CREDENTIALS:
                    self.log.info("Voltou para a tela de login; refazendo credenciais")
                    self._set_phase(Phase.CREDENTIALS)
            else:
                self.login_screen_since = 0.0

                if det.screen is LoginScreen.SERVER_LIST:
                    # E ZERA O CONTADOR DE ERRO DE CREDENCIAL.
                    #
                    # O servidor SÓ mostra a lista de servidores DEPOIS de
                    # aceitar usuário e senha. Então chegar aqui é PROVA de que
                    # as credenciais estão certas, e qualquer erro de credencial
                    # contado antes disto era instabilidade, não recusa.
                    #
                    # ===============================================
                    # O DEFEITO QUE ISTO CONSERTA, MEDIDO
                    # ===============================================
                    #
                    # Medido em 01/09/2026, uma `LoginSequence` de 796 s na
                    # conta `blazesofgamer`, com o jogo no bug de "Conexão
                    # interrompida" que o usuário relatou durar semanas:
                    #
                    #     lista de servidores alcançada (= autenticou) ... 85
                    #     conexão interrompida ........................... 85
                    #     tela de erro de usuário/senha .................... 5
                    #
                    # E a ordem em que cada erro apareceu:
                    #
                    #      5 lista de servidores -> 1 erro de usuário/senha
                    #     13 lista de servidores -> 1 erro de usuário/senha
                    #     17 lista de servidores -> 1 erro de usuário/senha
                    #     11 lista de servidores -> 1 erro de usuário/senha
                    #     39 lista de servidores -> 1 erro de usuário/senha
                    #
                    # Cada erro veio DEPOIS de dezenas de autenticações
                    # bem-sucedidas. A senha estava certa, e o bot concluiu
                    # `BadCredentials` -- que em `supervisor.py` faz
                    # `account.enabled = False` E GRAVA. A conta sai de rotação
                    # com a senha correta, e só volta com intervenção manual.
                    #
                    # Antes deste reset o contador zerava só no `__init__`. Isso
                    # é verdade e estava documentado, mas UMA sequência dura
                    # horas e dezenas de ciclos de login: dentro dela o contador
                    # nunca zerava, mesmo tendo autenticado 85 vezes.
                    #
                    # O LIMITE DE CINCO CONTINUA INTEIRO. Senha realmente errada
                    # nunca alcança a lista de servidores, então nada zera e a
                    # conta é desativada na quinta recusa, como antes -- que é o
                    # comportamento certo, porque cada recusa real é uma
                    # tentativa registrada no servidor.
                    #
                    # FORA DO `if` DA FASE, DE PROPÓSITO: `_do_credentials`
                    # chuta `_set_phase(Phase.SERVER)` logo depois de clicar em
                    # OK, sem prova nenhuma. Se o reset ficasse dentro do
                    # `if self.phase is not Phase.SERVER`, ele seria pulado
                    # exatamente nos ciclos em que o palpite otimista acertou a
                    # fase -- ou seja, quase sempre.
                    self.credential_errors = 0
                    if self.phase is not Phase.SERVER:
                        self._set_phase(Phase.SERVER)
                elif det.screen is LoginScreen.CHAR_SELECT:
                    if self.phase is not Phase.ENTERING:
                        self._set_phase(Phase.ENTERING)
                    # Personagens na tela: não espera os 20 s, entra agora.
                    self.last_enter_attempt = 0.0
                    # E ZERA O CONTADOR DE TENTATIVAS ÀS CEGAS.
                    #
                    # Este era o bug do "ficou parado na tela de seleção de
                    # personagem". O limite de 4 tentativas existe para o caso
                    # CEGO -- sem imagem e sem memória, clicar em Enter Game com o
                    # personagem já dentro do jogo o faz andar pelo mapa. Mas aqui
                    # a imagem CONFIRMA que a tela de seleção está aberta: o
                    # personagem definitivamente não está no mundo, e clicar é
                    # exatamente o que tem de ser feito.
                    #
                    # Sem este zeramento, quatro tentativas malsucedidas (captura
                    # intermitente, clique engolido, servidor lento) desligavam o
                    # clique PARA SEMPRE, e a conta ficava olhando os personagens
                    # até alguém perceber.
                    if self.enter_attempts:
                        self.log.info(
                            "Tela de seleção confirmada na imagem; zerando as %s "
                            "tentativas anteriores — aqui clicar é seguro.",
                            self.enter_attempts,
                        )
                    self.enter_attempts = 0
                    self.blind_warned = False

            # 4. Executa a fase. Nunca depende de imagem para avançar.
            self._advance_phase(det)
            self._queue_logged = False

    def close(self) -> None:
        self.memory.close()
