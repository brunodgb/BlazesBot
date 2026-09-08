"""
Supervisor: o ciclo de vida completo de uma conta.

Este módulo é a peça que os bots de referência NÃO têm. Neles, o auto-login
e o bot de farm são dois programas separados: o bot detecta a queda e apenas
mata o processo, e alguém precisa reabrir o login manualmente.

Aqui é um laço único e fechado:

    lançar Client.bat -> descobrir PID -> achar janela -> logar
      -> ativar pet -> rodar boss-rush
      -> se cair: matar cliente, backoff, voltar ao começo

A descoberta de PID por diferença (snapshot antes/depois do lançamento) é o
que permite operar várias contas em paralelo sem confundir instâncias.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import psutil
import win32gui
import win32process

from ..config import CAVE_BC, CAVE_HH, MODO_FADA_DA_HH, Account, BotConfig
from ..core import cronometro as cronometro_mod
from ..core import instrumentacao, logmodo, quedas, vizinhanca
from ..core.coords import coords_for_window
from ..core.memory import Memory
from ..core.target_hybrid import TargetHybrid
from ..core.vision import TemplateLibrary
from . import mural
from .app import ExecutorDeMacro
from .app.sincronia import SincroniaDoTime
from .bc.routine import BossRushRoutine
from .context import BotContext, Disconnected, StopRequested
from .hh.routine import HHRoutine
from .login import (
    BadCredentials,
    ClientClosed,
    LoginError,
    LoginSequence,
    StopDuringLogin,
)
from .team import InviteAcceptor
from .watchdog import (
    VISUAL_CHECK_SECONDS,
    DcReason,
    Watchdog,
    avaliar_saude,
    backoff_delay,
    client_pids,
    kill_client,
)

StatusCallback = Callable[[str, str], None]  # (login, mensagem)

# Quem é o dono de cada cliente nesta execução. Duas contas disputando a mesma
# janela era a causa de o bot abrir vários clientes ao mesmo tempo.
_PIDS_CLAIMADOS: dict[int, str] = {}
_LOCK_JANELAS = threading.Lock()


# Teto de uma fatia dentro de `_AnyEvent.wait`. É REDE, não o caminho normal --
# ver o docstring do `wait`. Com o fan-out de `BotManager.stop()` a espera acorda
# no instante do `set()` e esta fatia nunca chega ao fim.
TETO_DA_FATIA_DE_ESPERA = 0.25

# Quanto uma vítima espera pela Fada antes de voltar para a poção.
#
# NÃO É O TEMPO DE UMA CURA -- uma cura leva segundos. É a rede para o caso
# medido em 04/09/2026: Fada VIVA e INCAPAZ (vítima fora do painel do time, cura
# que não pega), em que ela batia, a vítima esperava, e nenhum dos dois tinha
# como sair. Sessenta segundos é muito mais que qualquer cura e muito menos que
# uma noite parado.
TETO_DA_ESPERA_PELA_FADA = 60.0

# Do CENTRO do template do convite até o "Ok" dele.
#
# `find_template` devolve o centro do casamento; o template é a fileira dos dois
# botões (recortada de `data/templates/entrada/reviveu.png`), e o "Ok" fica à
# esquerda do centro dela. Medido no recorte: template de 240x30, "Ok" centrado
# em (50, 14) dentro dele, centro em (120, 15).
DO_CENTRO_ATE_O_OK = (-70, -1)

# Limiar do casamento do convite. Mais exigente que o limiar geral de telas
# (0.85 é o do login) porque o custo do falso positivo aqui é um clique numa
# janela que talvez seja a OUTRA -- e a outra tira o personagem do spot.
LIMIAR_DO_CONVITE = 0.9


class _AnyEvent:
    """Visão de "qualquer um destes eventos foi acionado".

    O resto do código só chama `is_set()` e `set()`, então basta imitar essa
    parte da interface de threading.Event. Assim os módulos do bot não precisam
    saber que existem duas formas de parar.
    """

    def __init__(self, *eventos: threading.Event) -> None:
        self._eventos = eventos

    def is_set(self) -> bool:
        return any(e.is_set() for e in self._eventos)

    def set(self) -> None:
        # Aciona o último (o próprio), preservando o global para os outros.
        self._eventos[-1].set()

    def clear(self) -> None:
        for e in self._eventos:
            e.clear()

    def wait(self, timeout: float | None = None) -> bool:
        """Espera até QUALQUER um dos eventos ser acionado.

        =================================================================
        ELE ESPERAVA NO EVENTO ERRADO, E ISSO CUSTAVA CPU EM TODO LUGAR
        =================================================================

        Era `return self._eventos[-1].wait(timeout)` -- só o evento PRÓPRIO.
        Acionar o stop GLOBAL (que é o que o botão Parar faz, em
        `BotManager.stop`) não acordava ninguém: quem estivesse dormindo aqui
        dormia o timeout inteiro.

        A consequência não ficava neste arquivo. O `BotContext.tick()` não podia
        confiar neste `wait`, então cumpria toda espera em FATIAS de 0,025 s de
        `time.sleep`, conferindo a flag entre elas -- 40 acordadas por segundo,
        por conta, o tempo todo. Era o preço de um `wait` que não acorda.

        Duas correções, e as duas precisam existir:

        1. `BotManager.stop()` faz FAN-OUT: além do global, aciona o `own_stop`
           de cada supervisor. A propagação vai no ESCRITOR (parar é raro) e não
           no leitor (esperar é o caminho quente).
        2. Aqui, a espera é fatiada por `TETO_DA_FATIA_DE_ESPERA` como REDE: se
           algum dia alguém acionar o evento global sem passar pelo fan-out -- as
           ferramentas temporárias passam um evento próprio como global --, a
           parada degrada para "notada em até um quarto de segundo" em vez de
           "nunca notada". Rede não é o caminho normal: com o fan-out, o
           `wait` do evento próprio devolve NO INSTANTE do `set()`.
        """
        if self.is_set():
            return True
        proprio = self._eventos[-1]
        if timeout is None:
            while not self.is_set():
                if proprio.wait(TETO_DA_FATIA_DE_ESPERA):
                    return True
            return True
        fim = time.monotonic() + timeout
        while True:
            if self.is_set():
                return True
            restante = fim - time.monotonic()
            if restante <= 0:
                return self.is_set()
            if proprio.wait(min(TETO_DA_FATIA_DE_ESPERA, restante)):
                return True


class AccountSupervisor(threading.Thread):
    """Mantém uma conta rodando indefinidamente, relogando quando cai.

    Um supervisor por conta, cada um em sua thread. Os logins acontecem em
    PARALELO: só o trecho de "lançar o cliente e descobrir o PID novo" é
    serializado, porque a descoberta é feita por diferença entre os PIDs de
    client.exe antes e depois -- se dois lançamentos acontecerem juntos, um
    supervisor pode adotar o processo do outro.
    """

    # Protege apenas lançar + descobrir PID. Tudo o mais roda concorrente.
    _launch_lock = threading.Lock()

    def __init__(
        self,
        config: BotConfig,
        account: Account,
        stop_event: threading.Event | None = None,
        pause_event: threading.Event | None = None,
        on_status: StatusCallback | None = None,
        max_runs: int | None = None,
    ) -> None:
        super().__init__(daemon=True, name=f"supervisor-{account.login}")
        self.config = config
        self.account = account
        # Dois eventos de parada: o GLOBAL, que encerra tudo, e o PRÓPRIO, que
        # encerra só esta conta. O próprio é usado quando a conta é desativada
        # na interface com o bot rodando -- as outras seguem intactas.
        self.global_stop = stop_event or threading.Event()
        self.own_stop = threading.Event()
        self.stop_event = _AnyEvent(self.global_stop, self.own_stop)
        self.pause_event = pause_event or threading.Event()
        self.on_status = on_status
        self.max_runs = max_runs

        self.log = logging.getLogger(f"blazes.{account.login}")
        # Template do convite de reviver, carregado UMA vez (ver
        # `achar_o_convite_de_reviver`).
        self._tpl_convite = None
        self.pid: int | None = None
        self.hwnd: int | None = None
        self.relogin_count = 0
        # TENTATIVAS DE LOGIN SEGUIDAS QUE FALHARAM. Alimenta o backoff, e o
        # importante é QUANDO ele volta a zero: no login CONCLUÍDO, dentro de
        # `_run_session`.
        #
        # Era uma variável local de `run()`, zerada num `else:` do `try` que
        # NUNCA executava -- o corpo do `try` termina em `return`, então o
        # `else` do `try/except` é inalcançável, e aquele era o único `= 0`
        # depois da inicialização. O contador só crescia pela vida inteira da
        # thread: uma conta que caiu nove vezes numa madrugada passava a esperar
        # os 300 s do teto ANTES DE CADA RELOGIN, para sempre, mesmo com horas
        # de sessão saudável entre uma queda e outra.
        #
        # Como atributo, quem sabe que o login deu certo é quem zera -- e o
        # backoff volta a significar o que ele deveria significar: espaçar
        # tentativas de login que estão FALHANDO, não punir uma conta por ter
        # caído no passado.
        self.tentativas_de_login = 0
        self.total_runs = 0
        self.stats = None
        # A adoção de um cliente "livre" na tela de login só vale na primeira
        # sessão. Depois de uma queda, adotar às cegas faria o supervisor roubar
        # o cliente que outra conta acabou de abrir.
        self._primeira_sessao = True

    # -- utilidades --------------------------------------------------------

    def request_stop(self, motivo: str = "") -> None:
        """Encerra SOMENTE esta conta, sem tocar nas outras."""
        if motivo:
            self._status(f"Encerrando: {motivo}")
        self.own_stop.set()

    def _aplicar_petbug(self) -> None:
        """Esconde os jogadores e aplica o pet bug -- NESTA conta, por conta.

        =================================================================
        POR CONTA, E ESSE É O PONTO -- 07/09/2026
        =================================================================

        Isto era um clique no `BlazesBot - PetBug.exe`. Decisão do usuário
        depois de o programa ser lido por dentro:

            *"O ideal é ou usar o 'BlazesBot - PetBug.exe' ou fazer por dentro
            do bot; os 2 ao mesmo tempo não faz sentido (...) ele executa isso
            em TODOS os 'client.exe' SEM DISTINÇÃO, até por isso queria trazer
            para dentro do bot, juntamente com o fato de que, como o bot é meu,
            eu não queria executar algo de terceiro."*

        O programa não sabia distinguir conta: um clique patchava tudo que
        estivesse aberto, inclusive as contas de APP, que o usuário decidiu não
        tocar. Daqui de dentro o alvo é `self.pid` e mais nada -- e quem chega
        aqui já passou pelo `if self.account.farms:` (só BC e HH).

        Duas metades, e as duas vieram da engenharia reversa
        (`docs/decisoes/pet-bug-engenharia-reversa.md`):

          ESCONDER ... `WM_KEYDOWN` da tecla de esconder, sem `WM_KEYUP`;
          PET BUG .... dois `mov` de seis bytes NOPados no `client.exe`.

        NUNCA DERRUBA A SESSÃO: uma conta logada e pronta para farmar não pode
        ser perdida porque um patch não pegou. Falha vira aviso.
        """
        from ..core import esconder_jogadores, patch_do_cliente, petbug
        from ..core.inputs import Input as _Input

        # ESCONDER JOGADORES: a tecla PRESA, e nunca solta -- 07/09/2026.
        #
        # Relato do usuário depois de reabrir o bot: *"não desapareceu com
        # todos, é importante desaparecer com todo mundo assim que começa a
        # executar; realmente é sobre deixar a tecla F12 down sempre clicado,
        # nunca soltar"*.
        #
        # É exatamente o que o patcher faz, e agora o bot faz sozinho -- sem
        # depender de o programa de terceiro ter achado a janela certa. Ver
        # `core/esconder_jogadores.prender_a_tecla`.
        try:
            tecla = getattr(self.account.settings.keys, "hide_players", "")
            if esconder_jogadores.prender_a_tecla(
                    tecla, _Input(self.hwnd).segurar_para_sempre, self.log):
                self.log.info(
                    "Esconder jogadores: tecla %r PRESA (KEYDOWN sem KEYUP) — "
                    "os outros personagens somem e ficam sumidos.", tecla)
        except Exception as exc:
            self.log.warning("Esconder jogadores: não deu para prender a "
                             "tecla (a sessão segue): %s", exc)

        try:
            nativo = patch_do_cliente.aplicar(self.pid, self.log)
            if nativo.ok:
                self.log.info("PET BUG (nativo): %s", nativo)
            else:
                self.log.warning("PET BUG (nativo): %s", nativo)
        except Exception as exc:
            self.log.warning("PET BUG (nativo) falhou (a sessão segue): %s", exc)

        # O PROGRAMA DE TERCEIRO É A RESERVA, e está DESLIGADO
        # (`petbug.ATIVADO`). Ele continua aqui porque desligar não é apagar:
        # se o nativo precisar ser desligado um dia, religar este é uma linha.
        try:
            resultado = petbug.aplicar_patch(log=self.log)
        except Exception as exc:
            self.log.warning("PetBug falhou (a sessão segue): %s", exc)
            return
        if resultado.aplicou and resultado.confirmado_no_log:
            self.log.info("PetBug: %s", resultado)
        elif resultado.aplicou:
            self.log.warning("PetBug: %s", resultado)
        else:
            self.log.debug("PetBug: %s", resultado)

    def _status(self, message: str) -> None:
        self.log.info(message)
        if self.on_status:
            try:
                self.on_status(self.account.login, message)
            except Exception:
                pass

    def _sleep_interruptible(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            if self.stop_event.is_set():
                raise StopRequested()
            time.sleep(0.125)

    # -- identidade da janela ----------------------------------------------

    def _gravar_personagem(self, nome: str) -> None:
        """Guarda o nick desta conta NO ARQUIVO de configuração.

        Sem esta gravação o nick só existia em memória: bastava fechar o bot para
        a pista se perder, e na volta ele abria um cliente NOVO para uma conta
        que já estava logada -- de volta para a fila de três horas. O nick é o que
        identifica a janela, então ele precisa sobreviver ao fechamento do bot.

        Escreve só quando há novidade: o login acontece muitas vezes por sessão.
        """
        if not self.account.remember_char_name(nome):
            return
        try:
            destino = self.config.save()
        except Exception as exc:
            # Falhar aqui não pode derrubar a sessão: o bot está logado e
            # farmando. O custo é só reconhecer a janela na próxima execução.
            self._status(
                f"Personagem '{nome}' identificado, mas NÃO consegui gravar a "
                f"configuração: {exc}. O bot continua normal; na próxima "
                "execução ele pode não reconhecer esta janela."
            )
            return
        self._status(
            f"Personagem '{nome}' guardado em {destino} — na próxima execução "
            "eu reconheço esta janela sem passar pela fila"
        )

    def _gravar_grade_da_comida_do_app(self, vence: float) -> None:
        """Grava no `config.json` quando a próxima refeição do pet vence.

        É o gêmeo de `CombatEngine._gravar_grade_da_comida`: MESMO campo, MESMO
        arquivo. O que muda é só quem chama -- aqui é o executor do APP, que não
        conhece `BotConfig` e recebe esta função pronta.

        POR QUE ISTO EXISTE (medido em 27/08/2026): sem ela o APP nascia com o
        relógio da comida em branco a cada reinício, RE-ANCORAVA o vencimento em
        `agora + intervalo` e nunca chegava a vencer -- 12 reinícios em 88
        minutos, zero refeições em 123. Ver `core/pet.py`.

        COMPLEMENTO: engole tudo. Falha ao gravar não pode derrubar a macro; o
        pior desfecho é a grade voltar ao que está no disco.
        """
        try:
            self.account.settings.pet.proxima_comida_em = float(vence)
            self.config.save()
        except Exception as exc:
            self.log.debug("não gravei a grade da comida do pet: %s", exc)

    def _batizar_janela(self, nome: str) -> None:
        """Põe o nick no título da janela.

        O cliente dá o MESMO título a todas as instâncias, então o título é a
        única forma de distinguir as janelas de fora do processo. Manter o título
        igual ao nick também é o que permite reconhecer a conta quando a leitura
        de memória falha.
        """
        if not (self.hwnd and nome):
            return
        try:
            atual = (win32gui.GetWindowText(self.hwnd) or "").strip()
            if atual == nome:
                return
            win32gui.SetWindowText(self.hwnd, nome)
            self.log.debug("janela renomeada de %r para %r", atual, nome)
        except Exception as exc:
            self.log.debug("não consegui renomear a janela: %s", exc)

    # -- lançamento --------------------------------------------------------

    def _launch_client(self) -> int:
        """Lança o Client.bat e devolve o PID da nova instância.

        Precisa lançar o .BAT e não o .exe: o .bat faz `cd` para a pasta do
        jogo e se auto-eleva. Chamar client.exe direto de outro diretório
        quebra o cliente.
        """
        with self._launch_lock:
            before = client_pids()
            self._status("Lançando o cliente")
            os.startfile(self.config.client_bat)

            deadline = time.time() + max(25.0, self.config.launch_delay * 3)
            while time.time() < deadline:
                self._sleep_interruptible(1.0)
                novos = client_pids() - before
                if novos:
                    pid = sorted(novos)[0]
                    # Registra o dono NA HORA. Sem isso, outro supervisor podia
                    # adotar este cliente recém-aberto como "livre na tela de
                    # login" -- e o resultado era uma cascata de clientes.
                    with _LOCK_JANELAS:
                        _PIDS_CLAIMADOS[pid] = self.account.login
                    self._status(f"Cliente iniciado (PID {pid})")
                    return pid
            raise RuntimeError("nenhuma instância nova de client.exe apareceu")

    def _find_window(self, pid: int, timeout: float = 60.0) -> int:
        """Localiza a janela de nível superior pertencente ao PID."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._sleep_interruptible(1.0)
            found: list[int] = []

            def callback(hwnd: int, _extra) -> bool:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                try:
                    _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                except Exception:
                    return True
                if window_pid == pid:
                    found.append(hwnd)
                return True

            try:
                win32gui.EnumWindows(callback, None)
            except Exception:
                pass

            if found:
                hwnd = found[0]
                self._status(f"Janela localizada (hwnd {hwnd})")
                return hwnd
        raise RuntimeError(f"janela do PID {pid} não encontrada")

    def _release(self) -> None:
        """Solta as referências SEM tocar no cliente.

        Usado quando o usuário manda parar: o jogo fica aberto exatamente como
        estava, só o bot deixa de agir.

        (A explicação acima estava DEPOIS do primeiro comando, então não era
        docstring nenhuma -- era um literal solto, e `_release.__doc__` valia
        None. Justo no método que o `CLAUDE.md` manda entender antes de mexer em
        janela adotada.)

        =================================================================
        LIBERA O POOL DE GDI, E ESTE É O ÚNICO LUGAR QUE PODE FAZER ISSO
        =================================================================

        `vision._pools` guarda um DC de janela + um bitmap por hwnd, para a
        captura não realocar a cada quadro. Quem liberava era só
        `BotContext.close()`.

        Mas o LOGIN captura a tela antes de existir um `BotContext`
        (`login_states` fotografa para reconhecer a tela). Se o login falhar --
        `LoginError`, `BadCredentials`, exceção qualquer -- o `BotContext` nunca
        é criado, `close()` nunca roda, e o pool daquela janela fica para sempre:
        um DC mais um bitmap de largura x altura x 32bpp (~3 MB a 1024x768) POR
        RELOGIN FALHO.

        Em 24 h com dezenas de relogins isso aproxima o processo do limite de
        10 000 handles GDI -- e quando ele estoura, NENHUMA alocação GDI do
        processo funciona mais, incluindo a pintura da janela PyQt6. É um dos
        caminhos para "a interface travou e o bot continua rodando".

        E tem um segundo efeito, de correção: o Windows RECICLA valores de hwnd.
        Um pool obsoleto deixado no dicionário é devolvido por `get_pool` para a
        janela NOVA que herdou o número, e o `ensure()` dele aprova o cache
        (mesmo tamanho, mesmo modo, bitmap não nulo) -- passando a fazer BitBlt
        do DC de uma janela destruída.

        Fica aqui, e não em `_encerrar_caido`, porque `_release` é chamado em
        TODOS os caminhos de morte de janela (são cinco), e porque tem de ser
        ANTES de `self.hwnd = None` -- perdido o hwnd, não há mais chave.
        """
        if self.pid:
            _PIDS_CLAIMADOS.pop(self.pid, None)
        if self.hwnd:
            try:
                from ..core.vision import release_pool
                release_pool(self.hwnd)
            except Exception:
                # Liberar recurso nunca pode derrubar o encerramento.
                pass
            try:
                # Mesma história, outro dicionário por hwnd: a lição "o leitor de
                # arredores não responde nesta janela" não pode ser herdada por
                # uma janela nova que reciclou o número.
                from .bc.ui_service import esquecer_janela
                esquecer_janela(self.hwnd)
            except Exception:
                pass
        # O ID PUBLICADO MORRE COM A SESSÃO. `mural._IDS` é dicionário de
        # módulo e sobrevive ao relogin; o id da entidade, não. Ver
        # `mural.esquecer_id`: id velho faz a Fada recusar a vítima certa.
        try:
            mural.esquecer_id(self.account.login)
        except Exception:
            pass
        self.pid = None
        self.hwnd = None

    # -- reaproveitar janelas já abertas ------------------------------------

    def _janelas_de(self, pid: int) -> list[int]:
        janelas: list[int] = []

        def callback(handle, _extra):
            if not win32gui.IsWindowVisible(handle):
                return True
            try:
                _, dono = win32process.GetWindowThreadProcessId(handle)
            except Exception:
                return True
            if dono == pid:
                janelas.append(handle)
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass
        return janelas

    def _titulos_esperados(self) -> set[str]:
        """Títulos de janela que pertencem a esta conta.

        O nick é o título que o bot usa hoje. As variantes com o LOGIN existem
        para janelas batizadas por versões anteriores (e pelo caminho em que a
        memória não abriu na hora do login): reconhecê-las evita abrir um cliente
        novo só porque o bot mudou de critério entre uma execução e outra.
        """
        nomes = {self.account.login, f"{self.account.login} [BlazesBot]"}
        if self.account.last_char_name:
            nomes.add(self.account.last_char_name)
            nomes.add(f"{self.account.last_char_name} [BlazesBot]")
        return {n for n in nomes if n}

    # -- pino da janela (hwnd, pid) -----------------------------------------

    @staticmethod
    def _titulo_do_jogo_e(titulo: str, esperados: set[str]) -> bool:
        """Se o título parece ser de uma janela deste jogo / desta conta.

        O cliente com título genérico (sem nick, ainda no meio do login) começa
        com "Talisman Online". Os títulos que o bot grava ao batizar a janela
        (nick ou login, com ou sem "[BlazesBot]") vêm no conjunto `esperados`.
        Os dois contam na validação do pino: a janela pode estar em qualquer um
        dos estados e ainda assim ser a nossa.
        """
        titulo = (titulo or "").strip()
        return titulo.startswith("Talisman Online") or titulo in esperados

    def _validar_hwnd_salvo(self) -> int | None:
        """Valida o pino salvo (hwnd, pid) e devolve o PID confirmado, ou None.

        O Windows RECICLA valores de hwnd: quando a janela do jogo fecha, o
        número pode ser herdado por outro aplicativo. Então o pino só vale se
        TODAS as checagens passarem:

          1. a janela ainda existe — `IsWindow`, que aceita minimizada
             (diferente de `IsWindowVisible`; o bot minimiza os clientes);
          2. o hwnd pertence ao MESMO pid que salvamos (pega hwnd reciclado);
          3. esse pid é um cliente do jogo vivo, na lista `client_pids()`;
          4. o título parece ser deste jogo (ou foi batizado por nós).

        Qualquer falha = janela morta/reciclada: quem chama apaga o pino.
        """
        hwnd = int(self.account.last_hwnd or 0)
        pid = int(self.account.last_pid or 0)
        if hwnd <= 0 or pid <= 0:
            return None
        if not win32gui.IsWindow(hwnd):
            return None
        try:
            _, dono = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return None
        if dono != pid or pid not in client_pids():
            return None
        try:
            titulo = (win32gui.GetWindowText(hwnd) or "").strip()
        except Exception:
            return None
        if not self._titulo_do_jogo_e(titulo, self._titulos_esperados()):
            return None
        return pid

    def _gravar_janela(self, hwnd: int, pid: int) -> None:
        """Guarda o pino (hwnd, pid) desta conta e persiste só se mudou.

        Falhar aqui não pode derrubar a sessão: o custo é só reconhecer a
        janela com menos certeza na próxima execução.
        """
        if not self.account.remember_window(hwnd, pid):
            return
        try:
            self.config.save()
        except Exception as exc:
            self._status(
                f"Não consegui gravar o pino da janela (hwnd {hwnd}): {exc}"
            )

    def _esquecer_janela(self) -> bool:
        """Apaga o pino salvo (hwnd, pid) e persiste se havia algo a apagar."""
        if not self.account.forget_window():
            return False
        try:
            self.config.save()
        except Exception as exc:
            self._status(f"Não consegui apagar o pino da janela: {exc}")
        return True

    @staticmethod
    def _personagem_de(pid: int) -> str | None:
        """Nome do personagem logado num cliente, lido da memória.

        É a forma mais confiável de saber QUEM é cada janela: não depende de o
        bot ter renomeado a janela antes, nem de a configuração já ter o nome
        guardado. Devolve None se o cliente não estiver no mundo.
        """
        try:
            memoria = Memory(pid)
        except Exception:
            return None
        try:
            if not memoria.critical_ok():
                return None
            return memoria.char_name()
        except Exception:
            return None
        finally:
            memoria.close()

    @staticmethod
    def _na_tela_de_login(titulo: str) -> bool:
        """Título sem nome de servidor = ainda não entrou em servidor nenhum."""
        if not titulo.startswith("Talisman Online") or "|" not in titulo:
            return False
        partes = [x.strip() for x in titulo.split("|")]
        return len(partes) < 3 or partes[1].lower().startswith("ver.")

    def _adotar_janela_existente(
        self,
    ) -> tuple[int, int, bool, str | None] | None:
        """Procura uma janela já aberta que pertença a esta conta.

        Reaproveitar não é conveniência: com fila de três horas, fechar e reabrir
        um cliente para trocar de versão do bot custa uma tarde.

        A identificação segue esta ordem, da mais forte para a mais fraca:

          0. PINO SALVO (hwnd, pid) da última janela desta conta. É a ÚNICA que
             identifica a janela no MEIO do login, sem nick na memória e com
             título genérico. Como o hwnd pode ser reciclado pelo Windows, o
             par é validado antes (ver `_validar_hwnd_salvo`); se a janela não
             corresponder mais, o pino é apagado aqui. Roda em QUALQUER sessão,
             ignorando `_primeira_sessao` -- a identificação é precisa, então
             não há risco de roubar a janela recém-aberta de outra conta.
          1. NICK DO PERSONAGEM lido da memória, comparado com o nick guardado na
             conta. É impossível confundir contas -- e é por isso que o nick é
             gravado no config.json a cada login.
          2. Título da janela -- o bot renomeia ao logar, então uma janela nossa
             de execução anterior se identifica sozinha. Vale também para janelas
             batizadas com o login por versões antigas; nesse caso o nick lido da
             memória é aproveitado para preencher o que faltava na configuração.
          3. Cliente parado na TELA DE LOGIN, e só na PRIMEIRA sessão deste
             supervisor. Aí não há personagem para confundir. Restringir à
             primeira sessão evita que, depois de uma queda, o supervisor roube
             o cliente recém-aberto de outra conta.

        Devolve (pid, hwnd, ja_logado, personagem_na_memoria) ou None.
        """
        esperados = self._titulos_esperados()
        alvo_personagem = (self.account.last_char_name or "").strip().lower()
        candidatos_login: list[tuple[int, int]] = []

        with _LOCK_JANELAS:
            # 0. PINO SALVO (hwnd, pid) — a âncora mais forte e a ÚNICA que
            #    identifica a janela no MEIO do login (sem nick legível e com
            #    título genérico). Roda em qualquer sessão, sem a restrição de
            #    `_primeira_sessao`: é o hwnd EXATO desta conta, então não há
            #    risco de roubar o cliente recém-aberto de outra. Conta com
            #    pino salvo também não cai no caminho genérico "cliente livre
            #    na tela de login" — ou usa o pino, ou abre janela própria.
            tem_pino = bool(self.account.last_hwnd and self.account.last_pid)
            pid_salvo = self._validar_hwnd_salvo() if tem_pino else None
            if tem_pino and pid_salvo is None:
                # O pino existia mas não resistiu à validação: janela fechada
                # ou hwnd reciclado pelo Windows. Apaga para não reconhecer
                # uma janela que não é mais a nossa.
                self._status(
                    "Pino de janela salvo, mas a janela não corresponde mais "
                    "(fechada ou hwnd reciclado) — apagando o pino"
                )
                if self._esquecer_janela():
                    self._status("pino de janela apagado")
            elif pid_salvo is not None:
                hwnd_salvo = int(self.account.last_hwnd or 0)
                dono = _PIDS_CLAIMADOS.get(pid_salvo)
                if dono and dono != self.account.login:
                    # Mesmo pino em duas contas (erro de config): quem chegou
                    # primeiro fica com a janela. Perdemos a disputa — apaga o
                    # pino e deixa o fluxo abrir uma janela NOVA para nós, em
                    # vez de duas contas controlando o mesmo cliente.
                    self._status(
                        f"O cliente (PID {pid_salvo}) já é de '{dono}'. O pino "
                        "desta conta apontava para ele; apagando o pino para "
                        "abrir uma janela própria."
                    )
                    if self._esquecer_janela():
                        self._status("pino de janela apagado")
                else:
                    personagem = self._personagem_de(pid_salvo)
                    alvo = (self.account.last_char_name or "").strip().lower()
                    if personagem and alvo and personagem.strip().lower() != alvo:
                        # A memória diz que é OUTRO personagem. Não roubar a
                        # janela (pode ter sido logada à mão com outra conta):
                        # apaga o pino e cai no fluxo normal por nick/título.
                        self._status(
                            f"Janela do pino está logada como '{personagem}', "
                            f"não como '{self.account.last_char_name}' — não é "
                            "desta conta; apagando o pino"
                        )
                        if self._esquecer_janela():
                            self._status("pino de janela apagado")
                    else:
                        _PIDS_CLAIMADOS[pid_salvo] = self.account.login
                        if personagem:
                            self._status(
                                f"Reconheci a janela desta conta pelo pino "
                                f"(PID {pid_salvo}, hwnd {hwnd_salvo}) logada "
                                f"como '{personagem}' — assumindo sem passar "
                                "pela fila"
                            )
                            return pid_salvo, hwnd_salvo, True, personagem
                        self._status(
                            f"Reconheci a janela desta conta pelo pino "
                            f"(PID {pid_salvo}) no meio do login — assumindo"
                        )
                        return pid_salvo, hwnd_salvo, False, None

            abertos = sorted(client_pids())
            self._status(
                f"clientes abertos: {abertos or 'nenhum'} | "
                f"já reivindicados: {dict(_PIDS_CLAIMADOS) or 'nenhum'} | "
                f"títulos que reconheço: {sorted(esperados)}"
            )
            for pid in abertos:
                if pid in _PIDS_CLAIMADOS:
                    self._status(
                        f"  PID {pid}: já é de '{_PIDS_CLAIMADOS[pid]}', pulando"
                    )
                    continue
                janelas = self._janelas_de(pid)
                if not janelas:
                    self._status(f"  PID {pid}: sem janela visível, pulando")
                    continue
                hwnd = janelas[0]
                titulo = (win32gui.GetWindowText(hwnd) or "").strip()

                # 1. Nome do personagem na memória.
                personagem = self._personagem_de(pid)
                self._status(
                    f"  PID {pid}: título={titulo!r} | "
                    f"personagem na memória={personagem!r} | "
                    f"tela de login={self._na_tela_de_login(titulo)}"
                )
                if personagem and alvo_personagem:
                    if personagem.strip().lower() == alvo_personagem:
                        _PIDS_CLAIMADOS[pid] = self.account.login
                        self._status(
                            f"Reconheci '{personagem}' pela memória no PID {pid}"
                            " — assumindo sem passar pela fila"
                        )
                        return pid, hwnd, True, personagem

                # 2. Título da janela.
                if titulo in esperados:
                    _PIDS_CLAIMADOS[pid] = self.account.login
                    self._status(
                        f"Reconheci a janela '{titulo}' (PID {pid})"
                        " — assumindo sem passar pela fila"
                    )
                    return pid, hwnd, True, personagem

                # 3. Guarda para o caso de nenhuma correspondência direta.
                #    Só entra em jogo se a opção estiver ligada E for a primeira
                #    sessão -- adotar cliente alheio depois de uma queda era o
                #    que fazia o bot roubar a janela recém-aberta de outra conta.
                if (self.config.reuse_login_screen_clients
                        and self._primeira_sessao
                        and self._na_tela_de_login(titulo)):
                    candidatos_login.append((pid, hwnd))

            if not candidatos_login:
                extra = ""
                if not self.config.reuse_login_screen_clients:
                    extra = (" (aproveitar cliente livre na tela de login está "
                             "DESLIGADO — vou abrir uma janela nova)")
                elif not self._primeira_sessao:
                    extra = " (aproveitar cliente livre só vale na 1ª sessão)"
                self._status("nenhuma janela reconhecida para esta conta" + extra)
            if candidatos_login:
                pid, hwnd = candidatos_login[0]
                _PIDS_CLAIMADOS[pid] = self.account.login
                self._status(
                    f"Aproveitando um cliente parado na tela de login (PID {pid})"
                )
                return pid, hwnd, False, None

        return None

    def _teardown(self) -> None:
        """Solta o controle. NUNCA fecha o jogo.

        A regra geral do bot é não encerrar o cliente. O motivo é prático e pesa
        mais que qualquer conveniência: a fila de login passa de três horas em dia
        cheio, então fechar um cliente que está logado ou na fila custa uma tarde.
        Se algo der errado, é melhor o bot avisar e tentar de novo na mesma janela.

        A ÚNICA exceção é a desconexão CONFIRMADA -- ver `_encerrar_caido`.
        """
        if self.pid:
            self._status("Soltando o controle (o jogo continua aberto)")
        self._release()

    def _encerrar_caido(self, motivo: str) -> None:
        """Encerra o cliente DESTA conta porque a sessão dele morreu.

        =================================================================
        A ÚNICA SITUAÇÃO EM QUE O BOT FECHA O JOGO
        =================================================================

        Uma janela que caiu não volta sozinha. Com o aviso "Connection
        interrupted" na tela, o cliente está morto mesmo que o processo continue
        vivo: não há sessão, não há personagem, e clicar em Ok encerra o jogo de
        qualquer forma. Manter essa janela aberta não preserva nada -- ela não
        está na fila, não está logada, e ainda impede o supervisor de abrir uma
        nova.

        O que a regra "nunca fechar o cliente" protege é a janela LOGADA ou NA
        FILA, que custa horas para recuperar. Uma janela caída não é nem uma nem
        outra.

        Só esta conta é afetada. As outras janelas continuam intactas -- por isso
        o encerramento é pelo PID desta, e nunca uma varredura de client.exe.
        """
        pid = self.pid
        if not pid:
            if self._esquecer_janela():
                self._status("pino de janela apagado")
            self._release()
            return
        self._status(
            f"{motivo} — encerrando SOMENTE o cliente desta conta (PID {pid}) "
            "para poder abrir uma janela nova. As outras contas não são tocadas."
        )
        if kill_client(pid):
            self._status(f"cliente PID {pid} encerrado")
        else:
            self._status(
                f"não consegui encerrar o PID {pid}. A próxima tentativa vai "
                "reaproveitar a janela se ela ainda existir."
            )
        # O cliente foi morto: o pino dele deixou de valer. Apagar agora evita
        # reconhecer, na próxima run, uma janela morta — ou reciclada pelo
        # Windows para outro aplicativo.
        if self._esquecer_janela():
            self._status("pino de janela apagado (cliente encerrado)")
        self._release()

    # -- sessão ------------------------------------------------------------

    def _run_session(self) -> None:
        """Uma sessão: obter uma janela, logar se preciso, e operar."""
        self._status("procurando uma janela do jogo para esta conta")
        ja_logado = False
        personagem_adotado: str | None = None
        adotada = self._adotar_janela_existente()
        if adotada is not None:
            self.pid, self.hwnd, ja_logado, personagem_adotado = adotada
        else:
            # Trava contra abrir mais de um cliente para a mesma conta: se ainda
            # há um processo vivo registrado para nós, ele é reaproveitado.
            if self.pid and psutil.pid_exists(self.pid):
                self._status(f"reusando o cliente já aberto (PID {self.pid})")
                self.hwnd = self._find_window(self.pid)
            else:
                self._status(
                    "nenhuma janela reconhecida para esta conta — vou abrir uma"
                )
                self.pid = self._launch_client()
                self._sleep_interruptible(self.config.launch_delay)
                self.hwnd = self._find_window(self.pid)
        # Guarda o pino (hwnd, pid) desta janela, nos TRÊS caminhos de aquisição
        # (adotou existente, reutilizou o cliente aberto, ou lançou um novo).
        # Persistir agora é o que permite reconhecer a MESMA janela lá na
        # frente — inclusive no meio do login — depois de o bot ser fechado.
        if self.hwnd and self.pid:
            self._gravar_janela(self.hwnd, self.pid)

        self._primeira_sessao = False

        if ja_logado:
            # O que a MEMÓRIA diz vale mais que o nick guardado: se o personagem
            # desta conta mudou, é ele que está no mundo agora. Gravar aqui
            # também é o que preenche a configuração de quem só tinha o título
            # antigo (batizado com o login) para se identificar.
            char_name = (personagem_adotado
                         or self.account.last_char_name
                         or self.account.login)
            if personagem_adotado:
                self._gravar_personagem(personagem_adotado)
                self._batizar_janela(personagem_adotado)
            self._status(f"Janela já logada como '{char_name}'; pulando o login")
        else:
            login = LoginSequence(
                self.config, self.pid, self.hwnd, self.account,
                self.log,
                stop_check=self.stop_event.is_set,
                pause_check=self.pause_event.is_set,
            )
            try:
                char_name = login.run()
                nome_confirmado = login.char_confirmado
            finally:
                login.close()
            # Só grava o que veio da MEMÓRIA. Se o nome foi deduzido (login da
            # conta, porque a memória não abriu ainda), gravar sobrescreveria o
            # nick bom por um palpite -- e o palpite não reconhece janela nenhuma.
            if nome_confirmado:
                self._gravar_personagem(char_name)

        # LOGIN CONCLUÍDO -- os dois caminhos acima chegam aqui, tanto a janela
        # adotada já logada quanto a sequência de login inteira. É o único sinal
        # honesto de que o backoff cumpriu o papel dele, então é aqui que ele
        # volta a zero. Ver `self.tentativas_de_login` no `__init__`.
        self.tentativas_de_login = 0

        farm = {
            CAVE_HH: "com a HH ligada",
            CAVE_BC: "com BC farm",
        }.get(self.account.cave_ligada, "só online")
        self._status(f"Logado como '{char_name}' ({farm})")

        # PETBUG: esconder jogadores + pet bug, num programa de terceiro.
        #
        # AQUI porque este ponto é alcançado no começo de TODA sessão -- a
        # primeira e cada uma depois de um relogin. O gatilho que o usuário pediu
        # é *"a cada vez que uma conta com Bot BC ativa cair"*, e uma conta que
        # caiu volta exatamente por aqui, num cliente NOVO que o patcher anterior
        # não alcançou.
        #
        # SÓ CONTAS DE FARM DE CAVE, também decisão dele -- e vale para as
        # DUAS: a HH esconde jogadores e sofre o bug do pet pelo mesmo motivo
        # que o BC. `farms` aqui é a pergunta certa ("está ocupada farmando?"),
        # e não um resquício de quando existia uma cave só.
        #
        # E um clique cobre TODOS os clientes abertos, então `petbug` tem
        # intervalo próprio: cinco contas caindo juntas produzem UMA aplicação,
        # não cinco.
        if self.account.farms:
            self._aplicar_petbug()

        # Espera a memória ficar legível. O mundo pode estar carregando ainda: a
        # detecção de "no mundo" também aceita o HUD por imagem, que aparece
        # antes de o objeto do jogador estar populado.
        from .context import BotContext as _Ctx  # noqa: F401  (só para clareza)
        espera = time.time() + 30.0
        memoria = Memory(self.pid)
        try:
            while time.time() < espera:
                if memoria.critical_ok():
                    self._status(
                        f"Memória legível: HP {memoria.hp()}/{memoria.max_hp()}, "
                        f"posição {memoria.position()}"
                    )
                    # SEGUNDA CHANCE de descobrir o nick. No fim do login o mundo
                    # às vezes ainda está carregando e a string do nome não lê --
                    # aí o título ficou com o login e a conta ficaria sem nick
                    # guardado para sempre. Agora que a memória abriu, é a hora.
                    lido = (memoria.char_name() or "").strip()
                    if lido:
                        char_name = lido
                        # Renomear é incondicional (e não faz nada se o título já
                        # está certo): assim uma janela batizada com o login por
                        # uma versão antiga passa a se identificar pelo nick.
                        self._batizar_janela(lido)
                        self._gravar_personagem(lido)
                    break
                self._sleep_interruptible(1.5)
            else:
                self._status(
                    "Não consegui ler HP e posição na memória em 30s. O login "
                    "está feito e a conta fica online; o farm só começa quando "
                    "a leitura funcionar."
                )
        finally:
            memoria.close()

        if self.config.minimize_clients:
            import win32con
            win32gui.ShowWindow(self.hwnd, win32con.SW_MINIMIZE)

        ctx = BotContext(
            config=self.config,
            account=self.account,
            pid=self.pid,
            hwnd=self.hwnd,
            stop_event=self.stop_event,
            pause_event=self.pause_event,
        )
        ctx.char_name = char_name

        # GUARDA A REFERÊNCIA para o modo APP poder anotar a queda no MESMO
        # contexto que o `_run_session` lê depois. Não é o APP passando a
        # depender do estado do farm: ele toca um campo só, `ultima_queda`, e o
        # dono do objeto continua sendo este método. Sem isso, queda percebida
        # dentro do APP não entraria no Histórico de Quedas -- e era justamente
        # por isso que nenhuma conta de APP aparecia nos registros.
        self._ctx_atual = ctx

        try:
            self._operate(ctx)
        except (Disconnected, ClientClosed):
            # AQUI, e não no `except` lá de cima, por UMA razão: este é o
            # último ponto em que `ctx` ainda existe e o cliente ainda está
            # VIVO. Quem trata a exceção acima chama `_encerrar_caido`, que
            # MATA a janela -- depois disso não há mais o que fotografar nem
            # memória para consultar.
            self._registrar_queda(ctx)
            raise
        finally:
            self.total_runs += ctx.runs_completed
            ctx.close()

    # -- a Fada da HH ------------------------------------------------------

    def _lider_da_hh(self) -> Account | None:
        """A conta que está farmando a HH e me escolheu como Fada, se houver.

        DUAS CONDIÇÕES, e as duas são obrigatórias:

          1. a outra conta tem a HH ligada E o modo `fada`;
          2. o `reset_nick` dela é o NICK desta conta.

        A segunda é o que impede uma conta virar Fada de um time que não é o
        dela. E é por NICK e não por login porque é o nick que aparece no painel
        do time -- é o mesmo vocabulário que a Fada vai usar para clicar.
        """
        meu_nick = (self.account.last_char_name or "").strip().lower()
        if not meu_nick:
            return None
        for conta in self.config.accounts:
            if conta is self.account or not conta.enabled:
                continue
            hh = conta.settings.hh
            if not conta.hh_farm or hh.modo_do_reset != MODO_FADA_DA_HH:
                continue
            if (hh.reset_nick or "").strip().lower() == meu_nick:
                return conta
        return None

    def _rodar_fada_da_hh(self, ctx: BotContext,
                          lider: Account) -> None:
        """Acompanha o líder pela HH: porta, entrada, follow.

        A CURA CONTINUA SENDO DA `FadaDoTime`, que é chamada por
        `_rodar_fada()` -- este laço cuida só de a Fada estar PERTO o bastante
        para a cura funcionar. Duas responsabilidades, dois lugares: quem cura
        não precisa saber andar, e quem anda não precisa saber curar.

        NÃO TRATA `Disconnected`: sobe para `_run_session`, que mata a janela e
        reloga. Login e relogin são a fundação de todo ecossistema.
        """
        from .hh.fada import FadaDaHH

        def selecionar_o_lider() -> bool:
            """Clica no retrato do líder no painel do time.

            O slot é descoberto pelo NICK, com o mesmo mecanismo que a Fada do
            APP usa -- ver `_slot_do_nick_no_painel`.
            """
            slot = self._slot_do_nick_no_painel(ctx, lider.last_char_name)
            if slot is None:
                return False
            ponto = getattr(ctx.coords, f"team_member_{slot + 1}", None)
            if ponto is None:
                return False
            ctx.click(ponto)
            return True

        fada = FadaDaHH(
            ctx,
            lider_nick=(lider.last_char_name or "").strip(),
            lider_login=lider.login,
            selecionar_o_lider=selecionar_o_lider,
        )

        # A CURA VEM DA MESMA `FadaDoTime` DO TIME DO APP.
        #
        # Não é uma segunda curandeira: é a mesma peça, e é por isso que ela foi
        # promovida para `bot/fada.py`. Aqui se pega UM GIRO dela
        # (`_uma_volta`), que o `FadaDaHH.acompanhar` chama a cada volta do laço
        # de seguir -- as duas coisas na mesma volta, porque dois laços na mesma
        # conta seriam duas mãos no mesmo teclado.
        curandeira = self._montar_a_fada(ctx)

        ctx.log.info("%s", fada.resumo())
        fada.rodar(
            continuar=lambda: (
                not self.stop_event.is_set()
                and self._lider_da_hh() is not None
                and ctx.memory.critical_ok()
            ),
            curar_uma_volta=(curandeira._uma_volta if curandeira is not None
                             else None),
        )

    def _slot_do_nick_no_painel(self, ctx: BotContext,
                                nick: str) -> int | None:
        """Em que slot do painel do time aquele nick está (0-based).

        A ordem do painel é a ordem que a memória devolve em
        `companheiros_de_time` -- é a MESMA fonte que a Fada do APP usa, e ter
        duas leituras da mesma lista seria ter duas ordens possíveis para o
        mesmo painel.
        """
        alvo = (nick or "").strip().lower()
        if not alvo:
            return None
        try:
            companheiros = ctx.memory.companheiros_de_time() or []
        except Exception:
            return None
        for i, quem in enumerate(companheiros):
            if (quem or "").strip().lower() == alvo:
                return i
        return None

    def _rotina_da_hh(self, ctx: BotContext) -> HHRoutine:
        """A rotina da HH desta conta, criada na primeira vez que alguém pede.

        GUARDADA, e não recriada a cada volta: o estado dela diz em que trecho
        dos quatro bosses a run está, e recriar significaria voltar ao primeiro
        boss cada vez que o laço externo dá uma volta.
        """
        if self._hh is None:
            self._hh = HHRoutine(ctx)
        return self._hh

    def _registrar_queda(self, ctx: BotContext) -> None:
        """Grava a queda no histórico que a interface mostra.

        SÓ QUEDA DE VERDADE DO JOGO. `Disconnected` também é levantada por
        leitura de memória ruim ("posição ilegível em goto()"), e isso não é
        queda -- por isso o gatilho é `ctx.ultima_queda`, que só o watchdog
        escreve, e não o tipo da exceção.

        A fase vem do `logmodo`, que a rotina atualiza a cada volta do laço. O
        contexto é thread-local e esta é a MESMA thread da rotina, então o valor
        ainda é o da fase em que a queda aconteceu.

        Nunca levanta: falhar em gravar o histórico não pode atrapalhar o
        relogin, que é o que devolve a conta ao ar.
        """
        try:
            queda = ctx.ultima_queda
            if not queda:
                return
            ctx.ultima_queda = None
            chave, quadro = queda
            rodando = (time.time() - ctx.stats.started_at
                       if ctx.stats.started_at else None)
            quedas.registrar(
                conta=self.account.login,
                personagem=ctx.char_name or self.account.char_name,
                motivo=chave,
                fase=logmodo.contexto_atual().get("fase"),
                posicao=ctx.memory.position(),
                local=ctx.memory.location(),
                run=ctx.stats.runs,
                segundos_rodando=rodando,
                relogin=self.relogin_count + 1,
                pid=self.pid,
                quadro=quadro,
            )
        except Exception:
            self.log.debug("Não consegui registrar a queda no histórico",
                           exc_info=True)

    def _operate(self, ctx: BotContext) -> None:
        """Opera a conta logada, respeitando o farm ligado/desligado ao vivo.

        Login e relogin são padrão para toda conta. O farm da cave é opcional e
        pode ser ligado ou desligado pela interface COM O BOT RODANDO: este laço
        consulta `self.account.bc_farm` a cada volta, e a rotina devolve o
        controle num ponto seguro quando a caixa é desmarcada.
        """
        routine = BossRushRoutine(ctx)
        # A rotina da HH é criada PREGUIÇOSAMENTE, e não junto da BC.
        #
        # Ela monta navegador, combate, UI, vendedor e serviço de time -- e a
        # esmagadora maioria das contas nunca liga a HH. Construir sempre seria
        # pagar isso em toda sessão para nada. `_rotina_da_hh` cria na primeira
        # vez que alguém pede e guarda: o estado dela (em que trecho a run está)
        # tem que sobreviver entre voltas do laço.
        self._hh: HHRoutine | None = None
        watchdog = Watchdog(ctx)
        aceitador = InviteAcceptor(ctx)
        anunciado: str | None = None
        self.stats = ctx.stats

        if ctx.settings.accept_team_invites:
            self._status("Conta de reset: aceitando convites de time")

        avisou_memoria = False

        while not self.stop_event.is_set():
            ctx.raise_if_stopped()

            # MODO APP: sistema separado, e o primeiro a ser consultado.
            #
            # Ligar a caixa "Ativar o modo APP nesta conta" é o comando para rodar
            # a macro, e ela vale NA HORA -- interface e bot compartilham o mesmo
            # objeto de configuração. Fica no topo porque APP e farm da cave
            # disputariam o teclado se rodassem juntos.
            # A SEGUNDA PORTA: convocado pelo time. A caixa "Ativar Modo APP"
            # desta conta pode estar desmarcada -- quem manda é o líder.
            if (self.account.settings.app.enabled
                    or self._lider_do_time() is not None):
                anunciado = None      # ao voltar, o estado é anunciado de novo
                # A FADA NÃO RODA MACRO. Ela é convocada pela mesma porta (o
                # líder ligou o APP), mas o laço dela é outro: curar e sentar.
                if self._sou_a_fada():
                    self._rodar_fada()
                else:
                    self._rodar_modo_app()
                continue

            # Aceitar convites é a função da conta de reset e não depende de
            # mais nada estar ligado. Fica no topo do laço, antes de qualquer
            # decisão sobre farm.
            if ctx.settings.accept_team_invites:
                aceitador.check_and_accept()

            # A FADA DA HH VEM ANTES DE TUDO -- ela é CONVOCADA.
            #
            # Terceira porta do sistema, ao lado do modo APP e do time do APP: a
            # conta pode não ter farm nenhum ligado, e ainda assim ter trabalho a
            # fazer porque OUTRA conta a escolheu como curandeira. Quem manda é
            # quem escolheu, não a caixa desta conta.
            #
            # Fica no topo pelo mesmo motivo do APP: se ela também tivesse farm
            # ligado, as duas coisas disputariam o teclado.
            lider_da_hh = self._lider_da_hh()
            if lider_da_hh is not None:
                if anunciado != "fada-hh":
                    anunciado = "fada-hh"
                    self._status(
                        f"Fada da HH de {lider_da_hh.login}: acompanho e curo")
                if not ctx.memory.critical_ok():
                    # A Fada precisa saber quem está no time, onde cada um está
                    # no painel e quanta vida tem. Sem memória ela clicaria às
                    # cegas -- e clique às cegas cura o aliado errado.
                    ctx.tick(2.5)
                    continue
                self._rodar_fada_da_hh(ctx, lider_da_hh)
                continue

            # A HH VEM ANTES DA BC, e a ordem é escolha, não acidente.
            #
            # As duas são farm de cave e disputariam o teclado se rodassem
            # juntas. Com uma ordem fixa a escolha é PREVISÍVEL -- ligar as duas
            # roda a HH, e o log diz isso -- em vez de depender de qual laço
            # chegou primeiro. Quem quer a BC desliga a HH.
            if self.account.hh_farm:
                if not ctx.memory.critical_ok():
                    if not avisou_memoria:
                        avisou_memoria = True
                        self._status(
                            "HH pedida, mas NÃO consigo ler a memória do "
                            "cliente. Sem isso o bot não sabe se andou, se "
                            "montou ou se o alvo caiu -- e farmar às cegas só "
                            "gera ação repetida no vazio. Mantendo a conta "
                            "online e verificando.")
                    ctx.tick(2.5)
                    continue
                if avisou_memoria:
                    avisou_memoria = False
                    self._status("Memória legível novamente; retomando a HH")
                if anunciado != "hh":
                    anunciado = "hh"
                    if self.account.bc_farm:
                        self._status(
                            "HH e BC estão as DUAS ligadas nesta conta: rodando "
                            "a HH. Desligue a HH para o BC voltar a rodar.")
                    else:
                        self._status("HH LIGADA")
                self._rotina_da_hh(ctx).run(
                    max_runs=self.max_runs,
                    should_continue=lambda: (
                        self.account.hh_farm
                        and not self.stop_event.is_set()
                        # Ligar o modo APP com a HH rodando devolve o controle
                        # no próximo ponto seguro, em vez de os dois disputarem
                        # o teclado.
                        and not self.account.settings.app.enabled
                        and ctx.memory.critical_ok()
                    ),
                )
                if (self.max_runs is not None
                        and ctx.runs_completed >= self.max_runs):
                    return
                continue

            quer_farmar = self.account.bc_farm
            memoria_ok = ctx.memory.critical_ok()

            # PORTÃO DE MEMÓRIA. O farm da cave lê HP, posição e alvo da memória
            # em cada decisão. Sem essas leituras o bot não sabe se montou, se o
            # pet apareceu, se andou -- e passa a repetir ações no vazio, que foi
            # exatamente o comportamento errático observado: invocar pet sete
            # vezes, montar e desmontar, abrir NPC sem motivo.
            #
            # Então: sem memória, não farma. Fica online e continua verificando,
            # porque a memória costuma ficar legível alguns segundos depois de o
            # mundo carregar.
            if quer_farmar and not memoria_ok:
                if not avisou_memoria:
                    avisou_memoria = True
                    self._status(
                        "BC farm pedido, mas NÃO consigo ler a memória do "
                        "cliente (HP e posição). Sem isso o bot não tem como "
                        "saber o que está acontecendo, e farmar às cegas só "
                        "gera ação repetida no vazio. Mantendo a conta online e "
                        "verificando a cada 5s. Rode o 2-DIAGNOSTICO.bat."
                    )
                estado_desejado = "aguardando memória"
            elif quer_farmar:
                estado_desejado = "farmando"
            else:
                estado_desejado = "online"

            if estado_desejado != anunciado:
                anunciado = estado_desejado
                if estado_desejado == "farmando":
                    self._status("BC farm LIGADO")
                elif estado_desejado == "online":
                    self._status("Online, sem farmar")

            if estado_desejado == "farmando":
                if avisou_memoria:
                    avisou_memoria = False
                    self._status("Memória legível novamente; retomando o farm")
                routine.run(
                    max_runs=self.max_runs,
                    should_continue=lambda: (
                        self.account.bc_farm
                        and not self.stop_event.is_set()
                        # Ligar a HH com o BC rodando devolve o controle no
                        # próximo ponto seguro -- a HH tem precedência.
                        and not self.account.hh_farm
                        # Ligar o modo APP com o farm rodando devolve o controle
                        # no próximo ponto seguro da rotina, em vez de os dois
                        # disputarem o teclado.
                        and not self.account.settings.app.enabled
                        and ctx.memory.critical_ok()
                    ),
                )
                if self.max_runs is not None and ctx.runs_completed >= self.max_runs:
                    return
            else:
                estado = ctx.snapshot()
                reason = watchdog.check(estado)
                if reason is not DcReason.NONE:
                    raise Disconnected(reason.value)
                # A CONTA DE RESET precisa de cadência curta.
                #
                # Ela existe para clicar no Ok do convite, e a outra conta espera
                # essa resposta parada na porta da cave -- cada segundo aqui é um
                # segundo em que ninguém está tentando entrar. Um segundo de laço
                # dá o "clique dois segundos depois" que o convite pede, contando
                # o tempo de a caixa aparecer.
                if ctx.settings.accept_team_invites:
                    ctx.tick(0.5)
                else:
                    ctx.tick(2.5 if estado_desejado == "aguardando memória" else 1.5)

    # -- time do APP -------------------------------------------------------

    def _lider_do_time(self) -> Account | None:
        """A conta que CONVOCA esta para o time do APP, ou `None`.

        Convocação é o que faz um seguidor rodar o modo APP com a caixa
        "Ativar Modo APP" DELE desmarcada -- pedido do usuário em 27/08/2026:
        *"quando o líder ligar o modo APP ou se já estiver ligado, as contas que
        fazem parte do time devem rodar APP, mesmo que a flag dele esteja como
        false, mas é só em caso de time."*

        Ela vale enquanto TRÊS coisas forem verdade ao mesmo tempo, e some
        sozinha quando qualquer uma cair -- por isso este método é consultado a
        cada volta, e não uma vez na largada:

        1. alguém tem esta conta no `time_logins` dele;
        2. esse alguém está com o modo APP LIGADO (líder desligou, time acabou);
        3. nem o líder nem esta conta estão farmando a Bewitcher Cave. BC e APP
           nunca rodam juntos: convocar uma conta no meio de uma run perderia a
           run (teleporte gasto, travessia feita, boss vivo).

        Ver `docs/INVARIANTES.md`, seção "Time do APP".
        """
        login = self.config.lider_do_time_do_app(self.account.login)
        if not login or self.account.farms:
            return None
        lider = next((c for c in self.config.accounts if c.login == login), None)
        if lider is None or lider.farms or not lider.settings.app.enabled:
            return None
        return lider

    def _fada_do_meu_time(self) -> str:
        """O login da Fada do meu time, ou "".

        Uma só: se houver mais de uma conta marcada, a primeira da lista de
        membros manda. Duas Fadas curando a mesma fila é desperdício, não erro,
        então não vale complicar -- mas a ordem precisa ser determinística para
        todo mundo chamar a MESMA.
        """
        por_login = {c.login: c for c in self.config.accounts}
        for login in self._membros_do_time():
            conta = por_login.get(login)
            if conta is not None and conta.settings.app.fada:
                return login
        return ""

    def _sou_a_fada(self) -> bool:
        """Esta conta é a Fada de um time que está de pé?

        As DUAS condições são obrigatórias. A flag sozinha não faz nada -- é o
        que permite marcar a conta uma vez e ela se comportar conforme o
        contexto: sozinha ela roda a macro dela como qualquer outra.
        """
        if not self.account.settings.app.fada:
            return False
        return self._tem_time_do_app()

    def _nick_do_login(self, login: str) -> str:
        """O nick do personagem daquela conta, ou "".

        A ponte entre os dois vocabulários do sistema: o mural e a configuração
        falam LOGIN, e a memória do jogo fala NICK. A Fada precisa dos dois --
        recebe o pedido por login e clica no retrato por nick.
        """
        alvo = (login or "").strip().lower()
        for conta in self.config.accounts:
            if (conta.login or "").strip().lower() == alvo:
                return (conta.last_char_name or "").strip()
        return ""

    def _dono_da_macro(self) -> Account:
        """De quem é a macro que esta conta roda: do líder, ou dela mesma."""
        lider = self._lider_do_time()
        return lider if lider is not None else self.account

    def _membros_do_time(self) -> list[str]:
        """Os logins que participam da largada, começando pelo líder.

        Conta farmando a cave é filtrada AQUI, e não só na tela: a tela impede
        de escolher, mas o farm pode ser ligado depois, com o time já rodando. O
        login continua gravado no `config.json` -- ela volta ao time sozinha
        quando o farm for desligado.
        """
        dono = self._dono_da_macro()
        logins = [dono.login, *dono.settings.app.time_logins]
        por_login = {c.login: c for c in self.config.accounts}
        vistos: list[str] = []
        for x in logins:
            conta = por_login.get(x)
            if not x or x in vistos or conta is None or conta.farms:
                continue
            vistos.append(x)
        return vistos

    def _tem_time_do_app(self) -> bool:
        """Esta conta participa de um time -- como líder ou como seguidora."""
        if self._lider_do_time() is not None:
            return True
        return bool(self.account.settings.app.time_logins) and len(
            self._membros_do_time()) > 1

    # -- a Fada ------------------------------------------------------------

    def _time_desfeito_no_jogo(self) -> bool:
        """O jogo diz que NÃO estou em party? `False` também quando não sei.

        O jogo desfaz a party sozinho quando todos os membros morrem, e nada no
        bot é avisado: a configuração continua listando o time, o mural continua
        com a Fada batendo, e a vítima esperaria uma cura em grupo que não tem
        como sair -- a Fada não teria retrato para clicar.

        A LEITURA É `tamanho_do_time()` (o ponteiro rebaseado, `ADDR_TEAM`), e
        ela CONTA o próprio personagem: `1` significa "só eu", ou seja, sem
        party. `0` é o mesmo caso pelo outro lado.

        "NÃO SEI" NÃO DESLIGA A FADA. `None` é leitura que não respondeu, e
        tratá-la como "sem time" tiraria a cura em grupo de todo mundo no
        primeiro soluço de memória -- é a mesma regra da conferência de janela
        antes de enviar tecla. Só o ponteiro CONFIRMANDO derruba a dependência.
        """
        memoria = getattr(self, "_memoria_do_app", None)
        if memoria is None:
            return False
        try:
            quantos = memoria.tamanho_do_time()
        except Exception:
            return False
        return quantos is not None and quantos <= 1

    def achar_o_convite_de_reviver(self) -> tuple[int, int] | None:
        """Onde clicar para ACEITAR o reviver da Fada, ou `None` se não há convite.

        ESTA É A ÚNICA LEITURA DE TELA DO CICLO DA MORTE, e ela existe porque as
        duas janelas ficam a 133 px uma da outra: a de trás ("revive at birth
        place") tira o personagem do spot e cobra mais Exp. Clique cego ali é
        caro demais; o template é o que separa uma da outra.

        O ponto devolvido é o do "Ok" do convite, calculado a partir de ONDE o
        template casou -- e não de uma coordenada fixa. Assim o clique acompanha
        a janela em vez de depender da aritmética de quem recortou o print.
        """
        from ..core.vision import capture_window, find_template

        if self._tpl_convite is None:
            biblioteca = TemplateLibrary(Path("data") / "templates" / "entrada")
            self._tpl_convite = biblioteca.load("convite_reviver.png")
            if self._tpl_convite is None:
                self.log.warning(
                    "Sem o template do convite de reviver — não vou clicar às "
                    "cegas numa tela com dois Ok.")
                return None
        quadro = capture_window(self.hwnd)
        if quadro is None:
            return None
        centro = find_template(quadro, self._tpl_convite,
                               threshold=LIMIAR_DO_CONVITE)
        if centro is None:
            return None
        return (centro[0] + DO_CENTRO_ATE_O_OK[0],
                centro[1] + DO_CENTRO_ATE_O_OK[1])

    def abrir_a_bolsa_e_apagar(self, tecla: str) -> int:
        """Abre a bolsa e apaga o lixo. UMA receita, dois chamadores.

        O modo APP e a Fada montavam este mesmo `BotContext` cada um por si --
        duas cópias do mesmo bloco, e duas chances de só uma ser corrigida.

        Mora AQUI e não na montagem da Fada por causa da fronteira de
        ecossistemas: o deletador é do `bot/app/`, e o supervisor é o único
        arquivo de `bot/` que pode conhecer ecossistema
        (`tests/test_ecossistemas.py`).

        NÃO ENGOLE EXCEÇÃO -- quem chama decide. O modo APP deixa subir; a Fada
        avisa e segue, porque bolsa cheia não pode derrubar a cura do time.
        """
        from .app import deletador

        ctx = BotContext(
            config=self.config, account=self.account,
            pid=self.pid, hwnd=self.hwnd,
            stop_event=self.stop_event, pause_event=self.pause_event)
        try:
            # DEVOLVE O QUE O DELETADOR DISSE. `deletador.BOLSA_NAO_ABRIU` é a
            # segunda testemunha do teclado mudo -- ver `core/teclado_mudo.py`.
            return deletador.limpar_a_bolsa(ctx, tecla)
        finally:
            ctx.close()

    def _rodar_fada(self, so_montar: bool = False):
        """Roda o laço da Fada enquanto o time estiver de pé.

        A MONTAGEM MORA EM `bot/fada_montagem.py` -- ver o cabeçalho de lá para
        o porquê do isolamento e por que a memória não é opcional aqui.
        """
        from .fada_montagem import rodar_a_fada

        return rodar_a_fada(self, so_montar=so_montar)
    def _montar_a_fada(self, ctx: BotContext):
        """A MESMA `FadaDoTime` do time do APP, montada para outro chamador.

        A HH+Fada precisa de UM GIRO do laço de cura para chamar dentro do laço
        de seguir (ver `bot/hh/fada.py`). Montar aqui, em vez de dentro do
        `_rodar_fada_da_hh`, é o que garante que existe UMA Fada: uma segunda
        montagem teria outros pontos de clique e outras barras de cura, e as
        duas divergiriam na primeira manutenção.

        Devolve `None` quando não deu para montar -- e aí a Fada da HH avisa e
        acompanha sem curar, em vez de derrubar a conta.
        """
        try:
            return self._rodar_fada(so_montar=True)
        except Disconnected:
            # QUEDA NÃO É "NÃO CONSEGUI MONTAR": ela sobe até o laço de sessão
            # para virar relogin. Engolir aqui deixava a Fada da HH acompanhando
            # com a janela morta.
            raise
        except Exception as exc:
            ctx.log.warning("Não consegui montar a Fada (%s)", exc)
            return None

    def _publicar_o_proprio_id(self, memoria, entrada, log) -> None:
        """Aperta a auto-seleção, lê o `TARGET_ID` e publica no mural.

        É a peça que a medição de 28/08/2026 revelou: a memória NÃO descreve um
        alvo que é jogador (nome e vida vêm nulos), mas o `TARGET_ID` responde,
        e a tecla de auto-seleção põe o id da própria conta nele.

        Sem isso a Fada não tem como confirmar em quem clicou -- e o invariante
        é que id que não bate não cura. Ou seja: sem publicar, esta conta
        simplesmente não é curável.
        """
        from . import mural

        tecla = (getattr(self.account.settings.keys, "self_target", "") or "").strip()
        if not tecla:
            log.warning("Sem tecla de auto-seleção configurada: esta conta não "
                        "poderá ser curada pela Fada (não há como confirmar o "
                        "clique). Configure-a em Editar conta > Teclas.")
            return
        try:
            entrada.key(tecla)
            time.sleep(0.3)                        # o alvo leva ~0,1 s para virar
            ident = memoria.id_do_alvo()
        except Exception as exc:
            log.warning("Não consegui ler o próprio id: %s", exc)
            return
        if not ident:
            log.warning("A auto-seleção não trouxe id nenhum.")
            return
        mural.publicar_id(self.account.login, ident)
        log.info("Meu id no time é %s (publicado no mural).", ident)

        # SOLTAR A SI MESMO, SEMPRE. A auto-seleção deixa a conta com ELA
        # PRÓPRIA como alvo -- e alvo próprio é um alvo válido para a regra
        # "TAB só quando falta alvo". A conta ficava com alvo, nunca mais
        # TABava, e travava batendo em nada: relatado em campo em 01/09/2026,
        # *"os não fadas estão se clicando e rodando a macro (...) tem que
        # forçar um TAB depois de apertar F1"*.
        #
        # O TAB aqui não é conferido nem repetido: ele existe só para desfazer o
        # que a linha acima fez. Quem escolhe alvo de verdade é a macro, na
        # primeira volta.
        tab = (getattr(self.account.settings.keys, "next_target", "") or "").strip()
        if tab:
            entrada.key(tab)
            log.info("TAB depois da auto-seleção, para não ficar preso em mim "
                     "mesmo.")
        else:
            log.warning("Sem tecla de 'próximo alvo': a conta fica selecionando "
                        "a si mesma depois de publicar o id.")

    # -- modo APP ----------------------------------------------------------

    def _rodar_modo_app(self) -> None:
        """Roda a macro de teclado enquanto o modo APP estiver ligado.

        ISOLAMENTO. Este método não recebe o `BotContext` de propósito. O executor
        precisa de quatro coisas -- a janela, a lista de linhas, uma condição de
        parada e um log -- e nada disso é estado do bot da cave. Nenhum objeto do
        farm (rotina, navegação, combate, vigia) participa daqui, e o executor não
        importa nada de `blazesbot.bot`.

        Também NÃO existe portão de memória aqui, ao contrário do farm. A macro é
        cega: ela manda tecla e espera. Isso é o que faz o modo APP funcionar
        justamente quando a leitura de memória não funciona.

        O PET É A ÚNICA COISA QUE ELE OLHA, e a leitura é injetada daqui em vez
        de o executor abrir memória por conta própria. Assim o isolamento fica
        igual: `modo_app` continua importando só `core.inputs`, e quem sabe abrir
        o processo do jogo é este arquivo, que já sabia. Se a memória não abrir,
        a função devolve `None` e o executor não faz nada -- o modo APP continua
        funcionando como antes.
        """
        app = self.account.settings.app
        log = logging.getLogger(f"blazes.{self.account.login}")

        # Memória própria, aberta e fechada AQUI. O modo APP roda fora do
        # `BotContext` de propósito (é ele que carrega o estado do farm), então
        # não há de quem pegar emprestado.
        try:
            memoria_do_pet = Memory(self.pid)
        except Exception:
            memoria_do_pet = None

        # O PRÓPRIO ID, PUBLICADO TAMBÉM POR QUEM RODA A MACRO.
        #
        # Sem isto a Fada NUNCA consegue confirmar em quem clicou, e o portão
        # "id que não bate não cura" trava tudo. Medido em campo: 357 cliques
        # em cima do mesmo retrato, dez por segundo, porque a vítima nunca
        # publicava -- e o personagem saiu andando de tanto clique.
        #
        # Só em time: fora dele ninguém pergunta este id, e apertar a tecla de
        # auto-seleção à toa trocaria o alvo de quem está lutando.
        if memoria_do_pet is not None and self._tem_time_do_app():
            from ..core.inputs import Input as _InputDoId
            try:
                self._publicar_o_proprio_id(
                    memoria_do_pet, _InputDoId(self.hwnd), log)
            except Exception as exc:
                log.warning("Não consegui publicar o próprio id: %s", exc)

        # TRAVA DE POSIÇÃO: salva a posição base IMEDIATAMENTE ao iniciar o APP,
        # usando a mesma leitura do diagnóstico (Memory.position()). Isso garante
        # que a posição seja salva no config mesmo se o resto da inicialização
        # falhar ou o processo for morto.
        if app.travar_posicao and memoria_do_pet is not None:
            try:
                pos_inicial = memoria_do_pet.position()
                if pos_inicial is not None:
                    x, y = pos_inicial
                    if x != 0 or y != 0:
                        app._base_pos_x = x
                        app._base_pos_y = y
                        self.config.save()
                        log.info("Trava de posição: base inicial salva no config %s (diagnóstico direto)", pos_inicial)
            except Exception as exc:
                log.warning("Trava de posição: falha ao salvar base inicial (diagnóstico): %s", exc)

        def pet_ativo() -> bool | None:
            """True/False/None -- e o `None` é o que preserva o modo cego."""
            if memoria_do_pet is None:
                return None
            try:
                if not memoria_do_pet.critical_ok():
                    return None
                return memoria_do_pet.pet_active()
            except Exception:
                return None

        # BARRA DE ATALHOS NA PÁGINA 1 -- na largada e antes de CADA volta.
        #
        # As teclas do APP apontam para os slots da página 1 tanto quanto as do
        # farm; na página errada elas disparam outra coisa, e nem o executor nem
        # o usuário percebem. Uma vez na largada não bastava: a sequência roda em
        # laço por horas, e basta um clique do usuário na barra para todas as
        # voltas seguintes saírem erradas.
        #
        # Montado AQUI e não dentro do executor para preservar o isolamento dele:
        # `modo_app` importa só `core.inputs` e continua assim. Este arquivo já
        # sabia abrir a janela do jogo, então é ele quem monta o clique.
        #
        # A regra vem de `core/hotbar`, NÃO de `bc/hotbar`: ela é sobre o JOGO, e
        # este caminho é o do APP. Enquanto morava só no `bc/`, o import daqui
        # apontava para `bot/` e falhava calado -- 44 voltas do APP rodaram com a
        # barra na página que estivesse (log de 31/08 a 01/09/2026).
        #
        # Entrada compartilhada: barra de atalhos + trava de posição. Criada
        # fora do try do hotbar para estar disponível mesmo se a garantia da
        # página 1 falhar.
        entrada = None
        largura: int = 0
        altura: int = 0
        garantir_barra: Callable[[], None] | None = None
        try:
            from ..core import hotbar
            from ..core.coords import coords_for_size
            from ..core.inputs import Input as _Input

            entrada = _Input(self.hwnd)
            largura, altura = entrada.client_size()
            ponto = coords_for_size(largura, altura).hotbar_page_up
            tecla = getattr(
                self.account.settings.keys, "hotbar_page_1", "") or ""

            def garantir_barra() -> None:
                hotbar.ir_para_a_pagina_1(
                    lambda p: entrada.left_click(p[0], p[1]), ponto,
                    apertar=entrada.key, tecla=tecla)

            garantir_barra()
        except Exception as exc:
            # Complemento: se não der para clicar, a macro roda como sempre rodou.
            garantir_barra = None
            log.warning("Não consegui garantir a página 1 da barra: %s", exc)

        # LIMPEZA DA BOLSA a cada N voltas (`AppConfig.apagar_lixo_a_cada`).
        #
        # Montada AQUI pelo mesmo motivo da barra de atalhos: o executor importa
        # só `core.inputs` e não sabe o que é `BotContext`, inventário ou
        # template. Quem sabe é este arquivo, que já cria o contexto para o BC.
        #
        # A tecla do inventário é a da aba TECLAS (`KeyBinds.inventory`), a mesma
        # que o BC usa no `package_courage`: teclas descrevem o JOGO, não o
        # ecossistema, e são a única coisa que os dois compartilham.
        limpar_a_bolsa: Callable[[], None] | None = None
        try:
            from .app import deletador

            tecla_do_inventario = (
                getattr(self.account.settings.keys, "inventory", "") or "")
            if deletador.ATIVADO and tecla_do_inventario:
                def limpar_a_bolsa() -> int:
                    return self.abrir_a_bolsa_e_apagar(tecla_do_inventario)
            elif not tecla_do_inventario:
                log.info(
                    "Limpeza da bolsa desligada: a tecla de Inventário não está "
                    "configurada na aba Teclas.")
        except Exception as exc:
            limpar_a_bolsa = None
            log.warning("Não consegui preparar a limpeza da bolsa: %s", exc)

        # Trava de posição: salvamos a posição inicial no config.json para persistência
        # entre execuções. O executor AGORA move o personagem de volta andando pelo
        # minimapa se ele sair da base. A base é salva no config a cada início do APP
        # (ou restaurada do config se já existe), permitindo que o usuário mude o
        # ponto base apenas parando e reiniciando o APP.
        base_pos: tuple[int, int] | None = None
        if app.travar_posicao:
            x = getattr(app, "_base_pos_x", 0)
            y = getattr(app, "_base_pos_y", 0)
            if x != 0 or y != 0:
                base_pos = (x, y)
                log.info("Trava de posição: base restaurada do config em %s", base_pos)
            else:
                log.info("Trava de posição: base ainda não salva no config (primeira execução)")
        else:
            log.info("Trava de posição: desligada por configuração.")

        # Centro do minimapa para cliques de movimento (trava de posição).
        minimap_center: tuple[int, int] | None = None
        if app.travar_posicao and memoria_do_pet is not None:
            try:
                coords = coords_for_window(self.hwnd)
                if coords is not None:
                    minimap_center = coords.minimap_center
                    log.info("Trava de posição: centro do minimapa obtido %s", minimap_center)
                else:
                    log.warning("Trava de posição: não consegui obter coordenadas da janela")
            except Exception as exc:
                log.warning("Trava de posição: falha ao obter centro do minimapa: %s", exc)

        # Função para ler a posição atual do personagem (injetada no executor).
        def posicao_atual() -> tuple[int, int] | None:
            if memoria_do_pet is None:
                return None
            try:
                if not memoria_do_pet.critical_ok():
                    return None
                return memoria_do_pet.position()
            except Exception:
                return None

        # ==============================================================
        # A CURA DO APP -- as leituras, e a fábrica
        # ==============================================================
        #
        # Todas pela MESMA `memoria_do_pet` que o resto do modo APP já usa: um
        # `Memory` por conta, aberto uma vez. `None` em qualquer leitura é
        # "não sei", e a `CuraDoApp` sabe tratar -- ver `bot/app/cura.py`.
        #
        # `Memory` é COMPARTILHADO entre ecossistemas de propósito: "quanta vida
        # eu tenho" é pergunta sobre o JOGO, e o BC faz a mesma. Ver
        # `docs/decisoes/memoria-primeiro.md`, seção "Compartilhado e
        # específico".
        def _ler(funcao, *args):
            if memoria_do_pet is None:
                return None
            try:
                if not memoria_do_pet.critical_ok():
                    return None
                return funcao(*args)
            except Exception:
                return None

        def _ler_simples(funcao, *args):
            """Leitura sem o portão critical_ok() -- para flags que não dependem
            do estado do personagem (hp, posição). A flag de combate (in_battle)
            é um byte direto no struct do jogador; não faz sentido vetar a leitura
            porque a posição falhou."""
            if memoria_do_pet is None:
                return None
            try:
                return funcao(*args)
            except Exception:
                return None

        # A MESMA memória, guardada para quem pergunta de fora do closure --
        # hoje `_time_desfeito_no_jogo`. Um handle só por conta, como sempre.
        self._memoria_do_app = memoria_do_pet

        def vida_pct() -> float | None:
            return _ler(memoria_do_pet.vida_pct) if memoria_do_pet else None

        def em_batalha() -> bool | None:
            return _ler_simples(memoria_do_pet.in_battle) if memoria_do_pet else None

        def esta_sentado() -> bool | None:
            return _ler(memoria_do_pet.is_sitting) if memoria_do_pet else None

        # ==============================================================
        # O ALVO VEM PELO MESMO CAMINHO DO BC -- conserto de 26/08/2026
        # ==============================================================
        #
        # Pergunta do usuário: *"sobre o HP do target, está sendo analisado como
        # fazemos no Gun Witch? Pois lá funciona perfeitamente a análise do HP,
        # nome, level e todas as informações do mob."*
        #
        # NÃO ESTAVA, e a diferença era séria. O BC lê o alvo pelo `TargetHybrid`
        # (`core/target_hybrid.py`), que chama `Memory.alvo_atual()` DIRETO. O
        # APP passava as mesmas leituras pelo `_ler` daqui, e o `_ler` tem um
        # portão: `critical_ok()`.
        #
        # `critical_ok()` exige que `hp()`, `max_hp()` E `position()` DO
        # PERSONAGEM respondam. Nenhuma das três tem relação com o alvo -- e a
        # `position()` é uma cadeia de ponteiros que falha de vez em quando.
        # Uma leitura ruim da POSIÇÃO DO PERSONAGEM vetava a leitura do ALVO, e
        # o executor recebia `None`: o mesmo `None` de "a entidade sumiu do
        # array". Daí o APP cair na reserva e no escape de "alvo ilegível" em
        # situações em que o BC lia o mob inteiro sem hesitar.
        #
        # DE BRINDE, o `TargetHybrid` REABRE o processo quando o PID muda --
        # relogin troca o PID, e um handle guardado vira leitura de processo
        # morto, em silêncio.
        #
        # O portão continua valendo para o que ele foi feito: as leituras do
        # PERSONAGEM (vida, batalha, sentado, posição, pet).
        alvo_hibrido = TargetHybrid(logger=log)

        def alvo_atual() -> dict | None:
            """Nome, HP exato, nível e posição -- a MESMA leitura do BC."""
            try:
                return alvo_hibrido.entidade_do_alvo(self.pid)
            except Exception:
                return None

        def id_do_alvo() -> int | None:
            """`0` = sem alvo. É a leitura mais barata do bot (~1 µs)."""
            try:
                return alvo_hibrido.id_do_alvo(self.pid)
            except Exception:
                return None

        teclas = self.account.settings.keys

        def chamar_a_fada(vida: float) -> bool:
            """Pede cura à Fada do time e espera. `False` = não há Fada, beba poção.

            A ESPERA SEGUE ENQUANTO A FADA BATE, e isso é decisão do usuário:
            o tempo de uma cura depende dos itens dela e até de crítico, então
            um teto curto mandaria beber poção no meio de uma cura que ia
            funcionar.

            MAS ELA DEIXOU DE SER INDEFINIDA em 04/09/2026. Fada VIVA e INCAPAZ
            era espera eterna: se a vítima não estivesse no painel do time (ou a
            cura simplesmente não pegasse), a Fada continuava batendo, a vítima
            continuava sentada, e nenhum dos dois tinha como sair. São três as
            saídas novas, todas medidas naquele levantamento:

              * a Fada AVISA que desistiu (`fada_desistiu_de`) -- antes ela só
                apagava o pedido, e a vítima republicava em 0,2 s, perdendo o
                lugar na fila e recomeçando o mesmo ciclo para sempre;
              * o TETO (`TETO_DA_ESPERA_PELA_FADA`) fecha o caso em que nem o
                aviso chega;
              * entrar em BATALHA sentada devolve a vítima à macro, pela regra
                do usuário: *"em batalha o personagem precisa estar atacando"*.
                Sentado apanhando é como um ferido vira um morto.

            Quem chega aqui já saiu de batalha e já voltou ao ponto inicial: é o
            `CuraDoApp` que garante os dois antes de chamar.
            """
            from . import mural

            fada_login = self._fada_do_meu_time()
            if not fada_login or not mural.fada_de_pe(fada_login):
                return False

            # O TIME DESFEITO NO JOGO -- 07/09/2026.
            #
            # Quando TODOS caem, o jogo desfaz a party sozinho. O mural continua
            # dizendo que existe uma Fada configurada e ela continua batendo (do
            # lado dela nada mudou), mas a cura em grupo depende da party: sem
            # ela, a Fada não tem retrato para clicar e a vítima esperaria o
            # teto inteiro por uma cura que não pode acontecer.
            #
            # A recriação automática do time não existe ainda; até existir, a
            # contingência é esta: confirmado o desfazimento, a conta se cura
            # sozinha com poção.
            if self._time_desfeito_no_jogo():
                log.warning(
                    "O time foi DESFEITO no jogo (o ponteiro diz que não há "
                    "party). A Fada %s não tem como curar em grupo — vou de "
                    "poção até o time voltar.", fada_login)
                return False

            # O MÁXIMO VAI JUNTO. A memória do time entrega o HP ATUAL de cada
            # companheiro, não o máximo -- quem sabe o próprio máximo é esta
            # conta, e sem ele a Fada não tem como calcular porcentagem.
            mural.publicar_estado(
                self.account.login,
                max_hp=_seguro_max_hp(),
                nick=(self.account.last_char_name or "").strip(),
            )
            mural.pedir_cura(self.account.login, vida)
            alvo = float(self._dono_da_macro().settings.app.cura_parar_pct)
            log.info("Pedi cura à Fada %s (vida %.0f%%, alvo %.0f%%).",
                     fada_login, vida, alvo)

            venci_em = time.monotonic() + TETO_DA_ESPERA_PELA_FADA
            try:
                while not self.stop_event.is_set():
                    if mural.fada_desistiu_de(self.account.login):
                        mural.esquecer_desistencia(self.account.login)
                        log.warning("A Fada %s desistiu de mim — vou de poção.",
                                    fada_login)
                        return False
                    if time.monotonic() >= venci_em:
                        log.warning(
                            "Esperei %.0fs pela Fada %s e a vida não chegou ao "
                            "alvo — vou de poção.",
                            TETO_DA_ESPERA_PELA_FADA, fada_login)
                        return False
                    if em_batalha() is True:
                        # APANHANDO SENTADO: volto para a macro.
                        #
                        # `True` e não `False`: não é desistir da cura, é parar
                        # de apanhar de graça. No fim da volta seguinte eu peço
                        # de novo, e a poção continua reservada para quando não
                        # há Fada.
                        log.info("Entrei em batalha esperando a Fada — volto a "
                                 "atacar em vez de apanhar sentado.")
                        return True
                    if not mural.fada_de_pe(fada_login):
                        log.warning("A Fada %s parou de responder — vou de poção.",
                                    fada_login)
                        return False
                    if mural.fada_em_batalha(fada_login):
                        # A FADA ESTÁ APANHANDO: volto a atacar.
                        #
                        # Não é desistir da cura -- é a forma mais rápida de
                        # consegui-la. Parado, eu não ajudo; atacando, eu mato o
                        # que está batendo nela, e ela volta a curar. Decisão do
                        # usuário em 01/09/2026.
                        #
                        # `True` e NÃO `False`: `False` mandaria beber poção, e
                        # a poção continua reservada para quando não há Fada. Eu
                        # volto para a macro ainda ferido, e no fim da volta
                        # seguinte peço de novo -- se ela já tiver saído da
                        # briga, sou atendido.
                        log.info("A Fada %s entrou em batalha — volto a atacar "
                                 "para ajudá-la.", fada_login)
                        return True
                    atual = vida_pct()
                    if atual is not None:
                        # A VÍTIMA REPUBLICA A PRÓPRIA VIDA enquanto espera.
                        #
                        # É ela quem sabe: lê `hp` e `max_hp` do próprio
                        # personagem, com precisão de inteiro. A Fada lendo a
                        # vida do aliado pela struct do time depende de um
                        # offset que ainda não está confirmado -- e a primeira
                        # tentativa saiu errada (o campo lido era o MÁXIMO, e a
                        # Fada concluía "já está com 100%" sem curar nada).
                        #
                        # `pedir_cura` preserva a hora do primeiro pedido, então
                        # republicar NÃO manda a vítima para o fim da fila.
                        mural.pedir_cura(self.account.login, atual)
                        if atual >= alvo:
                            log.info("Curado pela Fada (%.0f%%). Voltando à "
                                     "macro.", atual)
                            return True
                    time.sleep(0.2)
            finally:
                mural.cancelar_pedido(self.account.login)
            return True

        def _seguro_max_hp():
            try:
                return memoria_do_pet.max_hp() if memoria_do_pet else None
            except Exception:
                return None

        def montar_cura(executor_do_app):
            """A fábrica. Recebe o executor porque a cura precisa dos métodos
            dele para voltar ao ponto inicial -- ver o parâmetro `cura` do
            `ExecutorDeMacro` para o porquê de ser fábrica e não objeto."""
            from .app.cura import CuraDoApp

            return CuraDoApp(
                log=log,
                vida_pct=vida_pct,
                em_batalha=em_batalha,
                alvo_atual=alvo_atual,
                distancia_da_base=executor_do_app.distancia_da_base,
                voltar_para_base=executor_do_app.mandar_voltar_para_base,
                apertar=executor_do_app.input.key,
                esta_sentado=esta_sentado,
                # A FADA TEM PREFERÊNCIA SOBRE A POÇÃO -- e só existe em time.
                fada=chamar_a_fada if self._tem_time_do_app() else None,
                # A BARRA DA TELA MANDA no gatilho -- e em time é a do líder.
                pedir_pct=lambda: float(
                    self._dono_da_macro().settings.app.cura_pedir_pct),
                parar_pct=lambda: float(
                    self._dono_da_macro().settings.app.cura_parar_pct),
                # A TECLA DE POÇÃO É A DE FORA DE BATALHA. Medição do usuário:
                # personagens que rodam APP usam só essa, e ela NÃO funciona em
                # combate -- por isso a cura espera sair de batalha.
                #
                # `keys`, e NÃO `potions`: tecla descreve o JOGO e mora com as
                # outras teclas; `PotionConfig` guarda os LIMIARES (`hp_pct`,
                # `battle_hp_pct`). Foi essa troca que estourou em produção --
                # e só na hora da cura, porque o `lambda` só é avaliado ali.
                tecla_de_pocao=lambda: teclas.hp_potion,
                # A tecla de sentar é GLOBAL de propósito: descreve o JOGO, não
                # o ecossistema, como o resto das teclas.
                tecla_de_sentar=lambda: teclas.sit,
                continuar=lambda: not self.stop_event.is_set(),
            )

        self._status("Modo APP LIGADO (macro de teclado)")
        cave = self.account.cave_ligada
        if cave:
            self._status(
                f"O farm da {cave.upper()} também está ligado nesta conta. Os "
                "dois disputariam o teclado, então o modo APP tem preferência e "
                "o farm fica parado enquanto ele estiver ligado."
            )

        # ================================================================
        # CONFERIR SAÚDE NO MODO APP — o login/relogin é a BASE de todos os
        # ecossistemas, então todo ecossistema tem que perceber a queda
        # ENQUANTO roda.
        # ================================================================
        #
        # O DEFEITO QUE ISTO CONSERTA (18/08/2026): o modo APP é despachado no
        # topo do laço de `_operate` com `continue`, então o `watchdog.check()`
        # daquele laço NUNCA era alcançado enquanto o APP rodava. A única
        # conferência era `IsWindow` DEPOIS de `executor.rodar()` retornar --
        # ou seja, só pegava janela que já tinha morrido.
        #
        # Resultado medido: com 5 contas caindo juntas, as 4 de BC fecharam e
        # relogaram; a do APP ficou com a caixa "Connection interrupted" na
        # tela, apertando teclas contra ela. Corroboração nos dados: dos 19
        # prints em `logs/quedas/`, NENHUM é de conta APP.
        #
        # O template nunca foi o problema -- medido, ele casa a 0.973 na captura
        # daquela janela. O problema era ninguém olhar.
        #
        # É FUNÇÃO INJETADA e não `BotContext` no executor: o isolamento do
        # ecossistema (travado por `tests/test_ecossistemas.py`) exige que o
        # executor importe só `core.inputs`. Quem sabe o que é queda é o
        # supervisor, que já tem o `ctx` e já é quem decide qual ecossistema
        # roda.
        #
        # A CADÊNCIA é a mesma do BC (`VISUAL_CHECK_SECONDS`), e o teto vive
        # DENTRO do próprio `Watchdog`: chamar a cada volta não custa captura a
        # cada volta -- volta curta não fotografa, volta longa fotografa na
        # primeira oportunidade.
        # `avaliar_saude` e NÃO `Watchdog`: o watchdog recebe um `BotContext`, e
        # o modo APP não tem um de propósito (ver o docstring deste método). A
        # função recebe peças, então os dois caminhos usam a MESMA definição de
        # queda sem o APP passar a depender do estado do farm.
        templates_do_app = TemplateLibrary(Path("data") / "templates")
        ultima_olhada = [0.0]

        def _grade_da_comida_do_app() -> float | None:
            return getattr(
                self.account.settings.pet, "proxima_comida_em", 0.0) or None

        def conferir_saude() -> None:
            agora = time.time()
            na_hora = agora - ultima_olhada[0] >= VISUAL_CHECK_SECONDS
            if na_hora:
                ultima_olhada[0] = agora
            motivo, quadro = avaliar_saude(
                self.pid, self.hwnd, bool(win32gui.IsWindow(self.hwnd)),
                templates_do_app if na_hora else None,
            )
            if motivo is DcReason.NONE:
                return
            # O HISTÓRICO DE QUEDAS TAMBÉM PASSA A VALER PARA O APP. Antes
            # nenhuma conta de APP aparecia nos registros -- não porque não
            # caíssem, mas porque ninguém percebia.
            chave = {DcReason.PROCESS_GONE: "processo",
                     DcReason.WINDOW_GONE: "janela",
                     DcReason.RECONNECT_DIALOG: "conexao"}.get(motivo)
            if chave:
                ctx_do_historico = getattr(self, "_ctx_atual", None)
                if ctx_do_historico is not None:
                    # O MESMO objeto que o `_run_session` lê -- ver onde ele é
                    # guardado. É o que faz a queda do APP virar cartão no
                    # Histórico de Quedas.
                    ctx_do_historico.ultima_queda = (chave, quadro)
            raise Disconnected(motivo.value)

        def declarar_queda(motivo: str) -> None:
            """O executor constatou que a entrada morreu. Vira queda de verdade.

            MESMO DESFECHO DE UMA JANELA FECHADA, e de propósito: a conta
            reloga e VOLTA SOZINHA para o modo em que estava (regra de login e
            relogin). Uma conta que não recebe tecla produz exatamente o mesmo
            que uma conta deslogada -- nada --, com a diferença de que a
            deslogada tem conserto automático.

            Ver `core/teclado_mudo.py`: só se chega aqui depois de duas teclas
            independentes mudas por 5 min, com mob vivo por perto, e depois de
            o ESC não ter resolvido.
            """
            ctx_do_historico = getattr(self, "_ctx_atual", None)
            if ctx_do_historico is not None:
                ctx_do_historico.ultima_queda = (motivo, None)
            raise Disconnected(motivo)

        def max_hp_do_time() -> int | None:
            """A vida MÁXIMA desta conta -- o critério de quem assume o time.

            Vida máxima e não vida atual: a atual oscila a cada golpe, e o time
            trocaria de líder no meio de uma luta. Sem memória devolve `None` e
            a eleição cai no desempate por ordem de login.
            """
            if memoria_do_pet is None:
                return None
            try:
                return memoria_do_pet.max_hp()
            except Exception:
                return None

        def alvo_e_aliado() -> bool:
            """O alvo atual é gente do meu time (inclusive eu)?

            A auto-seleção deixa a conta com ela própria selecionada, e alvo
            próprio passava por alvo válido -- a conta nunca mais TABava. Esta
            pergunta é o que desfaz isso de forma geral, e não só logo depois do
            F1: vale também se um clique ou um acidente puser um companheiro no
            alvo.
            """
            from . import mural

            try:
                return bool(mural.quem_e_o_id(id_do_alvo()))
            except Exception:
                return False

        def montar_sincronia(ex):
            """Fábrica: o executor recebe o objeto pronto e não conhece o mural.

            É SEMPRE injetada, mesmo sem time. Quem decide se há largada é a
            própria sincronia, a cada volta -- assim montar ou desfazer um time
            com o bot rodando passa a valer sem religar nada.
            """
            dono = self._dono_da_macro()
            return SincroniaDoTime(
                ex,
                login=self.account.login,
                lider=dono.login,
                # O MODO É DO LÍDER: é ele quem monta o time, e um seguidor com
                # modo próprio faria duas contas do mesmo time discordarem
                # sobre o que "sincronizado" significa.
                modo=dono.settings.app.time_modo,
                membros=self._membros_do_time,
                max_hp=max_hp_do_time,
                log=log,
            )

        def montar_o_ciclo_da_morte(executor_do_app):
            """As peças do `CicloDaMorte`. Fábrica, como a cura e a Fada.

            A MONTAGEM MORA EM `bot/morte.py`, ao lado do ciclo que ela serve --
            este arquivo está no teto da catraca de tamanho, e a montagem não
            precisa de nada que só o supervisor saiba além do próprio `self`.
            """
            from .morte import montar_para_o_app

            return montar_para_o_app(
                self, executor_do_app, entrada,
                vida_pct=vida_pct, em_batalha=em_batalha,
                esta_sentado=esta_sentado, tecla_de_sentar=teclas.sit)

        executor = ExecutorDeMacro(
            hwnd=self.hwnd,
            # A MACRO PODE SER EMPRESTADA. Num time, o seguidor roda as linhas
            # do LÍDER -- e a leitura é feita a cada volta, então editar a
            # macro do líder com o time rodando vale na largada seguinte, o
            # mesmo contrato que `app.enabled` já tem.
            fonte_dos_passos=lambda: self._dono_da_macro().settings.app.passos_ativos,
            continuar=lambda: (
                not self.stop_event.is_set()
                # Ou a caixa desta conta, OU a convocação do líder. É isto que
                # faz o seguidor parar quando o líder desliga o modo APP.
                and (app.enabled or self._lider_do_time() is not None)
                # Janela fechada: parar de mandar tecla para um destino que não
                # existe mais. Quem decide reabrir o cliente é o laço de vida,
                # como em qualquer outra queda.
                and bool(win32gui.IsWindow(self.hwnd))
            ),
            log=log,
            pausado=lambda: self.pause_event.is_set(),
            pet_ativo=pet_ativo,
            tecla_do_pet=self.account.settings.keys.pet_summon,
            # Alimentação do pet: a mesma configuração do BC, via PetFeeder
            # compartilhado. O executor é cego e só aperta a tecla quando o
            # intervalo vence; se a tecla estiver vazia, ignora silenciosamente.
            tecla_do_pet_food=getattr(
                self.account.settings.keys, "pet_food", "") or "",
            feed_every_minutes=lambda: (
                getattr(self.account.settings.pet, "feed_every_minutes", 60)),
            feed_on_start=getattr(
                self.account.settings.pet, "feed_on_start", False),
            # A GRADE DA COMIDA SOBREVIVE A REINÍCIO -- conserto de 27/08/2026.
            #
            # O APP era reconstruído a cada relogin e a cada religar do modo, e
            # nascia sem grade: medido no log, 12 reinícios em 88 minutos e ZERO
            # refeições em 123 minutos com intervalo de 51. O BC nunca teve o
            # problema porque já lia e gravava `proxima_comida_em`; agora os dois
            # ecossistemas usam o MESMO destino, pela mesma função do `core`.
            #
            # As funções moram aqui porque `bot/` é quem conhece `BotConfig` --
            # o executor continua cego, importando só `core.*`.
            grade_da_comida=_grade_da_comida_do_app,
            gravar_grade_da_comida=self._gravar_grade_da_comida_do_app,
            antes_da_volta=garantir_barra,
            conferir_saude=conferir_saude,
            declarar_queda=declarar_queda,
            limpar_a_bolsa=limpar_a_bolsa,
            # FUNÇÃO, e não número: mudar o "a cada N voltas" na interface com o
            # bot rodando passa a valer na volta seguinte, sem religar nada.
            voltas_por_limpeza=lambda: int(
                getattr(app, "apagar_lixo_a_cada", 0) or 0),
            # Trava de posição: função para ler posição e centro do minimapa.
            posicao_atual=posicao_atual if app.travar_posicao else None,
            minimap_center=minimap_center if app.travar_posicao else None,
            # Posição base salva no config (pode ser None na primeira execução).
            base_pos=base_pos,
            travar_posicao=app.travar_posicao,
            shuffle_apos_n_voltas=app.shuffle_apos_n_voltas,
            # A CURA e o ALVO. Sem memória legível a cura fica inerte e o APP
            # roda exatamente como antes -- é o mesmo contrato do pet.
            cura=montar_cura if memoria_do_pet is not None else None,
            # O CICLO DA MORTE. Sem memória não há como saber que morreu, e aí
            # o APP roda cego como sempre rodou -- mesmo contrato da cura.
            morte=(montar_o_ciclo_da_morte
                   if memoria_do_pet is not None else None),
            alvo_atual=alvo_atual if memoria_do_pet is not None else None,
            # O TAB DEIXOU DE SER LINHA DA MACRO: o bot lê o id do alvo e só
            # aperta quando não há nenhum. Ver `_garantir_alvo` no executor.
            id_do_alvo=id_do_alvo if memoria_do_pet is not None else None,
            tecla_de_alvo=lambda: teclas.next_target,
            # A FLAG DE COMBATE -- a RESERVA de "o mob morreu?" para quando o
            # HP do alvo fica ILEGÍVEL (a entidade sai do array e o id continua
            # respondendo). É a MESMA leitura que a cura já usa: um `Memory`
            # por conta, aberto uma vez. Ver
            # `USAR_COMBATE_COMO_RESERVA_DE_MORTE` no executor.
            em_batalha=em_batalha if memoria_do_pet is not None else None,
            # A VIDA DO PERSONAGEM -- a observação de depois da morte usa a
            # QUEDA dela como prova positiva de que há outro mob batendo. A
            # MESMA leitura que a cura já usa.
            vida_pct=vida_pct if memoria_do_pet is not None else None,
            # A VIZINHANÇA -- só diagnóstico. É ela que separa "o spot esvaziou"
            # de "a tecla não chega ao jogo" quando o TAB para de responder.
            mobs_por_perto=(
                (lambda: vizinhanca.contar(memoria_do_pet))
                if memoria_do_pet is not None else None),
            # A LINHA 0 DA MACRO: o tempo depois do TAB. Função e não número,
            # pelo mesmo motivo de `fonte_dos_passos` -- mudar na tela com o bot
            # rodando passa a valer na volta seguinte.
            # A LARGADA DO TIME. Ver `bot/app/sincronia.py`.
            sincronia=montar_sincronia,
            # ALVO ALIADO NÃO É ALVO. Quem responde é o mural: se o id do alvo
            # atual pertence a alguém que publicou o próprio id, é gente do
            # time -- eu mesmo (depois da auto-seleção) ou um companheiro.
            #
            # `None` fora de time: sem time ninguém publica id, a pergunta não
            # tem como ser respondida, e o executor nem a faz.
            alvo_e_aliado=alvo_e_aliado if self._tem_time_do_app() else None,
            espera_depois_do_tab_ms=lambda: (
                self._dono_da_macro().settings.app.espera_depois_do_tab_ms),
            # ==========================================================
            # A SEGUNDA PORTA: A VIDA DO ALVO PELA TELA
            # ==========================================================
            #
            # Medição de 26/08/2026: mobs VIVOS e inteiros existem na memória
            # e NÃO são alcançáveis pela janela que `_procurar_entidade` varre
            # (ver `docs/decisoes/alvo-o-que-esta-medido.md`, item 41).
            # Enquanto o array de verdade não for achado, a barra desenhada é
            # a única fonte que responde por esses mobs.
            #
            # `TargetHybrid.vida_pela_tela` e não o `ler()`: aquele guarda
            # estado (`_ultimo_id`) para saber que o alvo trocou, e chamá-lo
            # de novo só pela barra estragaria esse estado.
            #
            # QUEM CONTROLA A CADÊNCIA É O EXECUTOR (`INTERVALO_MINIMO_DA_TELA`
            # e `LINHAS_ANTES_DE_OLHAR_A_TELA`): aqui só se entrega a função.
            vida_do_alvo_pela_tela=(
                (lambda: alvo_hibrido.vida_pela_tela(self.hwnd))
                if memoria_do_pet is not None else None),
        )

        # Se não temos posição base salva no config e travar_posicao está ligado,
        # lê da memória AGORA e persiste imediatamente. Assim, mesmo se o processo
        # for morto, a posição inicial fica salva para a próxima execução.
        # O executor também salva a base se vier None, mas fazemos aqui também
        # para garantir que o config seja atualizado antes do executor rodar.
        if app.travar_posicao and base_pos is None and memoria_do_pet is not None:
            try:
                pos_inicial = memoria_do_pet.position()
                if pos_inicial is not None:
                    x, y = pos_inicial
                    if x != 0 or y != 0:
                        app._base_pos_x = x
                        app._base_pos_y = y
                        self.config.save()
                        log.info("Trava de posição: base inicial salva no config %s", pos_inicial)
            except Exception as exc:
                log.warning("Trava de posição: falha ao salvar base inicial: %s", exc)

        try:
            executor.rodar()
        finally:
            # SAIR DO MURAL. Sem isto a conta que parou continuaria publicada
            # por `ESTADO_VALIDO_SEGUNDOS`, e nesse intervalo o time esperaria
            # a largada de quem não está mais lá -- exatamente o "esperar por
            # quem não vai chegar" que a regra do teto existe para evitar.
            mural.esquecer_estado(self.account.login)
            if executor.sincronia is not None:
                log.info("Modo APP encerrado -- %s", executor.sincronia.resumo())
                if executor.sincronia.sou_o_lider():
                    mural.esquecer_largada(self.account.login)
                    mural.esquecer_passo(self.account.login)
            # Fecha o handle do processo em qualquer saída. Sem o `finally`, uma
            # exceção no laço deixaria um handle aberto por sessão de modo APP --
            # e o modo APP é reiniciado a cada volta do laço de vida.
            if memoria_do_pet is not None:
                try:
                    memoria_do_pet.close()
                except Exception:
                    pass
            # O PONTEIRO GUARDADO MORRE COM O HANDLE. Deixá-lo apontando para
            # uma memória fechada faria `_time_desfeito_no_jogo` ler lixo -- e
            # lixo aqui desligaria a Fada do time inteiro.
            self._memoria_do_app = None
            # O `TargetHybrid` abre o PRÓPRIO handle (o mesmo arranjo do BC, que
            # tem o `ctx.memory` de um lado e o híbrido do outro). Fechar aqui,
            # no mesmo `finally`, pelo mesmo motivo.
            try:
                alvo_hibrido.fechar()
            except Exception:
                pass

        if not win32gui.IsWindow(self.hwnd):
            raise Disconnected("janela do cliente fechada durante o modo APP")
        if not app.enabled:
            self._status("Modo APP desligado")

    # -- laço de vida ------------------------------------------------------

    def run(self) -> None:
        # Primeira coisa: registrar que a thread realmente começou. Sem esta
        # linha, uma falha antes do primeiro log deixava o bot silencioso e sem
        # pista nenhuma do que aconteceu.
        self._status("supervisor iniciado")
        # TELEMETRIA. Aqui e nao no `main`, porque este e o unico ponto por onde
        # TODO ecossistema passa -- e a thread ja e a da conta, entao o carimbo
        # sai certo sem ninguem precisar passar o login adiante.
        cronometro_mod.ligar()
        cronometro_mod.marcar_a_conta(self.account.login)
        # E O PACOTE INTEIRO, uma vez por processo. Aqui e nao no import porque
        # 56 arquivos de teste leem `inspect.getsource` de metodos reais -- um
        # wrapper no lugar do metodo quebraria os 56 de uma vez. Ver
        # `core/instrumentacao.py`. Idempotente: o segundo supervisor a subir
        # nao embrulha nada de novo.
        instrumentacao.instrumentar_tudo()
        self.tentativas_de_login = 0
        stopped = False
        try:
            while not self.stop_event.is_set():
                try:
                    self._run_session()
                    self._status("Rotina concluída")
                    return

                except (StopRequested, StopDuringLogin):
                    # Parada pedida pelo usuário: NÃO encerra o cliente.
                    stopped = True
                    self._status("Parada solicitada — o jogo continua aberto")
                    return

                except BadCredentials as exc:
                    # SENHA ERRADA É A ÚNICA FALHA DE LOGIN QUE MAIS TENTATIVAS
                    # NÃO RESOLVEM -- e cada recusa é uma tentativa registrada
                    # NO SERVIDOR, que é o caminho para a conta bloqueada. Aqui
                    # o custo de insistir não é tempo, é a conta.
                    #
                    # DESATIVA A CONTA E GRAVA. Antes o supervisor só encerrava:
                    # a thread morria e a conta sumia da execução sem que nada
                    # na tela dissesse que ela tinha morrido -- e na execução
                    # seguinte ela voltava a queimar as mesmas cinco recusas.
                    #
                    # Com `enabled = False` persistido, a conta DESMARCADA na
                    # interface É o aviso: ela não tenta mais sozinha, e
                    # reativar é o mesmo clique com que você confere a senha.
                    self.account.enabled = False
                    try:
                        self.config.save()
                    except Exception as erro:
                        self.log.warning(
                            "Não consegui salvar a configuração: %s", erro)
                    self._status(
                        f"CONTA DESATIVADA: {exc} Corrija a senha na edição da "
                        "conta e marque 'ativa' de novo para voltar a tentar."
                    )
                    self._teardown()
                    return

                except ClientClosed as exc:
                    # A janela morreu (pelo jogo ou porque você fechou). Libera o
                    # registro para que a próxima volta abra UM cliente novo, e
                    # apenas um: o PID antigo é esquecido aqui.
                    # O próprio JOGO se fechou -- não fomos nós. É o único caso
                    # em que relançar é necessário, porque não há mais janela
                    # com que trabalhar.
                    self.tentativas_de_login += 1
                    self.relogin_count += 1
                    self._status(f"{exc}. Relogin #{self.relogin_count}")
                    self._release()  # o processo já morreu, nada a matar
                    delay = backoff_delay(self.tentativas_de_login,
                                          self.config.relogin_backoff_cap)
                    self._status(f"Reabrindo em {delay:.0f}s")
                    self._sleep_interruptible(delay)

                except Disconnected as exc:
                    self.tentativas_de_login += 1
                    self.relogin_count += 1
                    self._status(f"Desconexão detectada: {exc}. "
                                 f"Relogin #{self.relogin_count}")
                    # AQUI o cliente é encerrado, e só aqui. A sessão morreu: a
                    # janela não está logada nem na fila, então ela não vale nada
                    # e ainda atrapalha -- o supervisor a reconheceria como "sua"
                    # na volta seguinte e ficaria preso nela. Ver `_encerrar_caido`.
                    self._encerrar_caido("Sessão caída")
                    delay = backoff_delay(self.tentativas_de_login,
                                          self.config.relogin_backoff_cap)
                    self._status(f"Aguardando {delay:.0f}s antes de religar")
                    self._sleep_interruptible(delay)

                except LoginError as exc:
                    self.tentativas_de_login += 1
                    self._status(f"Falha de login: {exc}")
                    if self.stop_event.is_set():
                        stopped = True
                        return
                    self._teardown()
                    delay = backoff_delay(self.tentativas_de_login,
                                          self.config.relogin_backoff_cap)
                    self._status(f"Nova tentativa em {delay:.0f}s")
                    self._sleep_interruptible(delay)

                except Exception as exc:
                    self.tentativas_de_login += 1
                    self.log.exception("Erro inesperado na sessão: %s", exc)
                    if self.stop_event.is_set():
                        stopped = True
                        return
                    self._teardown()
                    delay = backoff_delay(self.tentativas_de_login,
                                          self.config.relogin_backoff_cap)
                    self._sleep_interruptible(delay)

                # NÃO EXISTE MAIS UM `else:` AQUI. Ele zerava o contador e era
                # código morto: o `try` acima termina em `return`, então o `else`
                # do `try/except` nunca era alcançado. Quem zera agora é
                # `_run_session`, no instante em que o login conclui.

        except (StopRequested, StopDuringLogin):
            stopped = True
            self._status("Parada solicitada — o jogo continua aberto")

        # A REDE DE BAIXO. Sem ela, uma exceção que escapasse do laço matava a
        # thread SEM UMA LINHA DE LOG -- o supervisor sumia e a interface só
        # mostrava que a conta parou de andar. É a assinatura de "fechou sozinho
        # sem erro claro".
        #
        # O laço acima já trata quase tudo, mas há dois caminhos que passavam por
        # fora dele: uma exceção levantada DENTRO de um `except` (por exemplo
        # `_teardown()` falhando durante a recuperação de um erro) e qualquer
        # `BaseException` que não seja `Exception`.
        except BaseException as exc:
            try:
                self.log.exception(
                    "Falha fatal no supervisor, fora do laço de sessão: %s", exc)
                self._status(f"PARANDO por falha inesperada: {exc}")
            except Exception:
                pass
        finally:
            # CADA PASSO DE ENCERRAMENTO NO SEU PRÓPRIO `try`. Antes, uma falha
            # aqui -- `_teardown` numa janela que já morreu, por exemplo --
            # substituía o encerramento inteiro e a última linha nunca era
            # escrita. Encerrar é justamente o que não pode falhar em silêncio.
            try:
                if stopped or self.stop_event.is_set():
                    # Solta o controle sem tocar no cliente.
                    self._release()
                else:
                    self._teardown()
            except Exception:
                self.log.exception("Falha ao encerrar o supervisor")
            try:
                self._status(
                    f"Encerrado. Runs: {self.total_runs}, "
                    f"relogins: {self.relogin_count}")
            except Exception:
                pass


def _janela_viva(hwnd: int | None) -> bool:
    """O handle em cache ainda aponta para uma janela? Barato e tolerante.

    O `hwnd` guardado no supervisor sobrevive à morte da janela até o laço
    perceber, e nessa fresta a interface pintava a conta de VERDE com o
    personagem fora do jogo (achado na revisão). `IsWindow` é syscall local; uma
    por conta a cada 1,5 s não aparece em medição nenhuma.

    Erro aqui NUNCA pode derrubar o resumo -- ele alimenta a tela inteira. Sem
    resposta, responde o que o handle diz.
    """
    if not hwnd:
        return False
    try:
        from ctypes.wintypes import HWND

        from ..core.inputs import user32
        return bool(user32.IsWindow(HWND(int(hwnd))))
    except Exception:
        return True


class BotManager:
    """Coordena um supervisor por conta habilitada."""

    def __init__(self, config: BotConfig, on_status: StatusCallback | None = None) -> None:
        self.config = config
        self.on_status = on_status
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.supervisors: list[AccountSupervisor] = []
        self.max_runs: int | None = None
        # "Rodando" espelha a INTENÇÃO do usuário, não a saúde das threads:
        # True desde o start() até o stop() (ou até não sobrar conta habilitada).
        self._ativo = False

    def start(self, max_runs: int | None = None) -> list[str]:
        log = logging.getLogger("blazes.gerenciador")
        log.info("=" * 60)
        log.info("INICIANDO — %s conta(s) na configuração", len(self.config.accounts))
        for conta in self.config.accounts:
            log.info(
                "  conta '%s': ativa=%s | BC farm=%s | servidor=%s | "
                "posição=%s | senha=%s | último personagem=%r",
                conta.login or "(sem login)", conta.enabled, conta.bc_farm,
                conta.server, conta.position,
                "definida" if conta.password_enc else "VAZIA",
                conta.last_char_name,
            )
        log.info("Client.bat: %s", self.config.client_bat)

        problemas = self.config.validate()
        if problemas:
            log.error("Configuração recusada — %s problema(s):", len(problemas))
            for p in problemas:
                log.error("   • %s", p)
            return problemas

        log.info("Configuração validada sem problemas")
        self.stop_event.clear()
        self.pause_event.clear()
        # A partir daqui o bot está "ativo" (o usuário clicou em Iniciar), mesmo
        # que os supervisores ainda estejam logando/relogando ou esperando memória.
        self._ativo = True
        self.supervisors = []
        self.max_runs = max_runs
        iniciadas = self.sync_accounts()
        if not iniciadas:
            log.error(
                "NENHUM supervisor foi iniciado. Isso não deveria acontecer com "
                "a configuração validada — veja as linhas de 'sincronizando' "
                "acima para entender qual conta foi descartada e por quê."
            )
        return []

    # -- contas em tempo real ---------------------------------------------

    def sync_accounts(self) -> list[str]:
        """Alinha os supervisores em execução com as contas ativas.

        Chamado sempre que a lista de contas muda na interface. É o que permite
        cadastrar uma conta com o bot já rodando: basta marcá-la como ativa e
        ela entra no ar, sem parar as demais.

        Conta ativada -> ganha supervisor e faz login.
        Conta desativada -> só o supervisor dela é encerrado.
        """
        log = logging.getLogger("blazes.gerenciador")
        if self.stop_event.is_set():
            log.info("sincronizando: parada já solicitada, nada a fazer")
            return []

        iniciadas: list[str] = []
        todas = self.config.accounts
        # SEM TETO DE CONTAS SIMULTÂNEAS. Quantas contas rodam é decidido por
        # quantas o usuário marcou como ATIVAS -- não havia por que ter as duas
        # coisas, e o antigo `max_clients` cortava contas ativas em silêncio.
        ativas = self.config.enabled_accounts()
        logins_ativos = {a.login for a in ativas}

        log.info(
            "sincronizando: %s conta(s) no total, %s ativa(s) -> %s",
            len(todas), len(ativas), sorted(logins_ativos) or "nenhuma",
        )
        for conta in todas:
            if conta not in ativas:
                motivo = ("sem login" if not conta.login
                          else "desmarcada" if not conta.enabled
                          else "acima do limite de contas simultâneas")
                log.info("   descartada '%s': %s",
                         conta.login or "(sem login)", motivo)

        # Encerra os supervisores de contas que saíram ou foram desativadas.
        for sup in list(self.supervisors):
            if sup.account.login not in logins_ativos and sup.is_alive():
                sup.request_stop("conta desativada na interface")
            if not sup.is_alive():
                self.supervisors.remove(sup)

        vivos = {s.account.login for s in self.supervisors if s.is_alive()}

        log.info("supervisores vivos agora: %s", sorted(vivos) or "nenhum")

        # Sobe supervisor para cada conta ativa que ainda não tem um.
        for conta in ativas:
            if conta.login in vivos:
                log.info("   '%s' já tem supervisor rodando", conta.login)
                continue
            sup = AccountSupervisor(
                config=self.config,
                account=conta,
                stop_event=self.stop_event,
                pause_event=self.pause_event,
                on_status=self.on_status,
                max_runs=self.max_runs,
            )
            self.supervisors.append(sup)
            log.info("   subindo supervisor de '%s'", conta.login)
            sup.start()
            iniciadas.append(conta.login)
        if iniciadas:
            log.info("supervisores iniciados: %s", iniciadas)
        return iniciadas

    def stop(self) -> None:
        self.stop_event.set()
        # FAN-OUT: aciona também o evento PRÓPRIO de cada supervisor.
        #
        # Sem isto, quem estivesse dormindo em `_AnyEvent.wait` (que espera no
        # evento próprio) só descobriria a parada quando o timeout vencesse. A
        # propagação mora aqui, no ESCRITOR, porque parar é raro e esperar é o
        # caminho quente -- pagar no lado raro é o que deixa o lado quente ser
        # uma espera de custo zero.
        #
        # `request_stop` continua acionando SÓ o próprio: parar uma conta segue
        # sem tocar nas outras.
        for sup in list(self.supervisors):
            try:
                sup.own_stop.set()
            except Exception:
                # Um supervisor em estado estranho não pode impedir a parada dos
                # demais -- o global já foi acionado acima.
                pass
        # O usuário pediu parada: desativa "Rodando" imediatamente (antes que as
        # threads terminem), para a UI voltar ao estado Parado no mesmo clique.
        self._ativo = False
        self._soltar_o_mouse_do_usuario()

    def _soltar_o_mouse_do_usuario(self) -> None:
        """Desinstala o hook global de mouse quando o bot para.

        =================================================================
        POR QUE ISTO EXISTE
        =================================================================

        O `MouseShield` instala UM hook `WH_MOUSE_LL` na criação do primeiro
        `Input` -- e NADA o desinstalava. Ele vivia até o processo morrer,
        **inclusive com o bot parado**: o usuário fechava o bot na interface, ia
        usar o computador, e cada evento de mouse do sistema continuava sendo
        entregue ao nosso processo e esperando o callback voltar.

        Mesmo com o callback em 0,6 µs (medido; ver `core/mouse_shield.py`), um
        hook de baixo nível obriga o Windows a marshalar CADA evento para o
        processo que hookeou e aguardar a resposta. Isso é custo por evento no
        caminho crítico do mouse de TODO o sistema, e com o bot parado ele não
        compra nada -- não há clique para proteger.

        A DESINSTALAÇÃO É ADIADA, e isso não é detalhe: `stop()` só SINALIZA a
        parada, e as threads das contas ainda podem estar no meio de um clique.
        Arrancar o hook ali deixaria justamente esse clique sem proteção -- e sem
        shield, com o mouse do usuário em movimento sobre a janela, a medição diz
        1/20 e o personagem ANDANDO em 14 dos 20 cliques. Então quem desinstala
        é uma thread que ESPERA as contas terminarem.

        Reinstalar é automático: o `Iniciar` seguinte cria `Input` novo, que cria
        `MouseShield`, que sobe o hook de novo (`uninstall_hook` deixa o estado
        pronto para isso -- foi corrigido junto).
        """
        supervisores = list(self.supervisors)

        def esperar_e_soltar() -> None:
            for sup in supervisores:
                try:
                    sup.join(timeout=20.0)
                except Exception:
                    pass
            try:
                from ..core.inputs import MOUSE_SHIELD_DISPONIVEL, MouseShield
                if MOUSE_SHIELD_DISPONIVEL and MouseShield is not None:
                    MouseShield.uninstall_hook()
            except Exception:
                # Soltar recurso nunca pode derrubar a parada.
                pass

        threading.Thread(target=esperar_e_soltar, daemon=True,
                         name="SoltarMouseShield").start()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    @property
    def paused(self) -> bool:
        return self.pause_event.is_set()

    def running(self) -> bool:
        # "Rodando" = o usuário clicou em Iniciar (intenção) e ainda há conta
        # habilitada. Não depende de thread viva: uma conta no meio do login,
        # relogin ou esperando memória (oline) NÃO deve piscar o estado para
        # "Parado" — antes isto era `any(s.is_alive() ...)`, frágil a erro no
        # meio do login. Só desativa ao parar (stop()) ou sem conta ativa.
        return self._ativo and bool(self.config.enabled_accounts())

    def join(self, timeout: float | None = None) -> None:
        for supervisor in self.supervisors:
            supervisor.join(timeout=timeout)

    def summary(self) -> dict[str, dict]:
        resultado: dict[str, dict] = {}
        for sup in self.supervisors:
            dados = {
                "runs": sup.total_runs,
                "success": 0,
                "fail": 0,
                "relogins": sup.relogin_count,
                # UMA CHAVE POR CAVE, e não `account.farms` nas duas.
                #
                # `farms` é "farma alguma cave": publicá-la como `farm` fazia o
                # espelho ao vivo da interface MARCAR a caixa do BC quando o
                # usuário ligava a HH. Ver `Account.farms`.
                "farm": sup.account.bc_farm,
                "farm_hh": sup.account.hh_farm,
                # A FUNÇÃO ATIVA, resolvida aqui. As duas chaves acima ficam
                # para quem ainda lê booleano, mas quem manda é esta: as três
                # funções são MUTUAMENTE EXCLUSIVAS, e mandar booleanos soltos
                # deixava a tela marcar duas ao mesmo tempo no espelho ao vivo.
                "funcao": ("app" if sup.account.settings.app.enabled
                           else "hh" if sup.account.hh_farm
                           else "bc" if sup.account.bc_farm else ""),
                # CONECTADA = tem JANELA VIVA agora, CONFERIDA.
                #
                # Não existia sinal de "no ar" nenhum: a interface só sabia que a
                # conta estava na lista do resumo, e estar na lista não quer dizer
                # estar conectada -- a conta que caiu continua aqui, tentando
                # religar, por minutos.
                #
                # `bool(sup.hwnd)` SOZINHO não bastava, e foi achado na revisão:
                # entre a janela morrer e o laço perceber, o handle continua em
                # cache e a tela ficava VERDE com o personagem fora do jogo. O
                # `IsWindow` fecha essa janela de mentira e é barato -- syscall
                # local, uma por conta a cada 1,5 s.
                "conectada": _janela_viva(sup.hwnd),
                # RECONECTANDO -- e só se o bot NÃO estiver parando.
                #
                # `tentativas_de_login` só zera quando o login CONCLUI, e o Parar
                # também mata a janela: sem olhar o `stop_event`, apertar Parar
                # pintava "Caiu — reconectando" em toda conta que já tinha tentado
                # logar alguma vez. Encerrar de propósito não é queda.
                "relogando": bool(not sup.hwnd
                                  and sup.tentativas_de_login
                                  and not sup.stop_event.is_set()),
                "last_run": 0.0,
                "total_run": 0.0,
                "uptime": 0.0,
                "profit": None,
                "run_now": 0.0,
                "boss_now": 0.0,
                "boss_atingido": False,
            }
            st = sup.stats
            if st is not None:
                dados.update({
                    "runs": st.runs or sup.total_runs,
                    "success": st.success,
                    "fail": st.fail,
                    "last_run": st.last_run_seconds,
                    "total_run": st.total_run_seconds,
                    "uptime": st.uptime_seconds,
                    "profit": st.profit,
                    "run_now": st.run_now_seconds,
                    "boss_now": st.boss_now_seconds,
                    "boss_atingido": st.boss_atingido,
                })
            resultado[sup.account.login] = dados
        return resultado
