"""
Contexto de execução de uma conta e snapshot do estado do jogo.

O BotContext é o objeto que todos os módulos recebem: memória, input,
coordenadas, configuração, log e sinalização de parada. Ter um único ponto
de acesso evita passar seis parâmetros em cada função.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

from ..config import Account, AccountSettings, BotConfig
from ..core.coords import Coords, coords_for_size
from ..core.inputs import Input, jitter
from ..core.memory import POSE_DA_CAMERA, Memory
from ..core.target_hybrid import TargetHybrid
from ..core.vision import TemplateLibrary

if TYPE_CHECKING:
    from .watchdog import Watchdog


@dataclass
class GameState:
    """Fotografia do estado do jogo em um instante."""

    alive: bool = False
    hp: int | None = None
    max_hp: int | None = None
    mp: int | None = None
    max_mp: int | None = None
    position: tuple[int, int] | None = None
    # NÃO existe `in_battle` neste retrato, e a ausência continua deliberada -- mas
    # a razão mudou. A flag PASSOU A COMANDAR o fluxo de combate da run de BC (ver
    # o bloco no topo de `bot/combat.py`), e justamente por isso ela não entra aqui:
    #
    #   * quem decide por ela precisa dos TRÊS estados, e `GameState` normaliza
    #     tudo para bool -- `None` viraria `False`, que é o erro que transforma
    #     falha de leitura em "a luta acabou";
    #   * o laço de combate a lê dez vezes por segundo, e montar um retrato inteiro
    #     nessa cadência custaria muito mais que a leitura de um byte.
    #
    # O laço chama `memory.in_battle()` direto, por `_ler_flag_de_combate`. Quem
    # precisa saber se está numa luta para escolher POÇÃO continua informando
    # explicitamente (ver `combat.maintain(..., em_luta=)`).
    mounted: bool = False
    # `None` = não deu para ler -- ver `Memory.is_sitting`.
    sitting: bool | None = False
    # `None` = não deu para ler -- ver `Memory.pet_active`. Falso em contexto
    # booleano, como `False`, mas distinguível para quem sabe perguntar.
    pet_active: bool | None = False
    bag_count: int | None = None
    target_name: str | None = None
    target_hp: int | None = None
    target_selected: bool = False
    modal_open: bool = False
    location: str | None = None
    timestamp: float = 0.0

    @property
    def hp_pct(self) -> float:
        if not self.hp or not self.max_hp:
            return 0.0
        return 100.0 * self.hp / self.max_hp

    @property
    def mp_pct(self) -> float:
        if not self.mp or not self.max_mp:
            return 0.0
        return 100.0 * self.mp / self.max_mp

    @property
    def dead(self) -> bool:
        return self.hp == 0

    @property
    def full_hp(self) -> bool:
        return bool(self.hp and self.max_hp and self.hp >= self.max_hp)


@dataclass
class RunStats:
    """Contadores de execução, por conta.

    Separar sucesso de falha importa: uma run que termina sem matar o boss
    (morreu, travou, tempo esgotado) não é a mesma coisa que uma run completa,
    e a proporção entre as duas é o melhor indicador de que a configuração está
    boa ou de que a rota precisa de ajuste.
    """

    runs: int = 0
    success: int = 0
    fail: int = 0
    started_at: float = 0.0
    run_started_at: float = 0.0
    last_run_seconds: float = 0.0
    total_run_seconds: float = 0.0
    boss_time_seconds: float = 0.0
    gold_start: int | None = None
    gold_now: int | None = None

    def begin_session(self) -> None:
        self.started_at = time.time()

    def begin_run(self) -> None:
        """Marca o início da run — chamado no instante em que o bot CONFIRMA
        que está dentro da cave (ver `routine._do_entrar`), não no começo da
        disputa de entrada. É daqui que os cronômetros ao vivo partem.
        """
        self.run_started_at = time.time()
        self.boss_time_seconds = 0.0

    def marcar_chegada_ao_boss(self) -> None:
        """Anota quanto a run levou para chegar na frente do boss.

        Chamado no instante em que a navegação termina e o passo final sobre a
        coordenada do boss ainda não aconteceu -- ou seja, o trajeto inteiro
        (entrada da cave, altar, guardas) sem contar o combate. Se a run nem
        chegou lá (morreu no caminho), o valor fica em 0.0.
        """
        if self.run_started_at:
            self.boss_time_seconds = time.time() - self.run_started_at

    def end_run(self, ok: bool) -> None:
        if self.run_started_at:
            duracao = time.time() - self.run_started_at
            self.last_run_seconds = duracao
            self.total_run_seconds += duracao
            self.run_started_at = 0.0
        self.runs += 1
        if ok:
            self.success += 1
        else:
            self.fail += 1

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.started_at if self.started_at else 0.0

    @property
    def run_now_seconds(self) -> float:
        """Tempo decorrido da run em andamento, ao vivo; 0.0 se entre runs.

        `run_started_at` só é não-zero DURANTE a run (zera no `end_run`), então
        este valor é o cronômetro da run atual. A interface o usa para mostrar
        o tempo correndo em tempo real, em vez de esperar a run terminar.
        """
        if not self.run_started_at:
            return 0.0
        return time.time() - self.run_started_at

    @property
    def boss_now_seconds(self) -> float:
        """Tempo do trajeto até o boss, ao vivo; 0.0 se entre runs.

        Conta igual ao `run_now_seconds` enquanto o personagem ainda vai, e
        CONGELA no valor da chegada no instante em que o boss é alcançado
        (`marcar_chegada_ao_boss`) -- exatamente o "tempo até o boss" da run
        atual. A interface mostra este contador correndo em vez de esperar a
        run terminar.
        """
        if not self.run_started_at:
            return 0.0
        if self.boss_time_seconds:
            return self.boss_time_seconds
        return time.time() - self.run_started_at

    @property
    def boss_atingido(self) -> bool:
        """True quando o personagem já chegou na frente do boss nesta run."""
        return bool(self.boss_time_seconds)

    @property
    def profit(self) -> int | None:
        if self.gold_start is None or self.gold_now is None:
            return None
        return self.gold_now - self.gold_start

    def reset(self) -> None:
        self.runs = self.success = self.fail = 0
        self.last_run_seconds = self.total_run_seconds = 0.0
        self.boss_time_seconds = 0.0
        self.run_started_at = 0.0


# Fatia máxima de sono dentro de um `tick`.
#
# O QUE ESTE NÚMERO SIGNIFICA MUDOU. Ele era o tempo que o Parar podia demorar
# para ser notado, porque a espera era `time.sleep` e a flag só era conferida
# ENTRE as fatias -- daí precisar ser minúsculo, ao custo de 40 acordadas por
# segundo por conta, o tempo todo, para quase sempre não encontrar nada.
#
# Agora a espera é `stop_event.wait(fatia)`, que devolve NO INSTANTE do `set()`.
# A latência do Parar passou a ser ZERO e deixou de depender deste número. O que
# ele governa hoje é só a CADÊNCIA DO WATCHDOG dentro de esperas longas: de
# quanto em quanto tempo o `tick` pergunta se o cliente ainda está vivo.
#
# 0,25 s e não 0,025: o watchdog já faz rate-limiting interno (a checagem visual
# roda a cada 20 s; processo e janela são syscalls baratos), então perceber uma
# queda em até um quarto de segundo em vez de um quadragésimo não muda desfecho
# nenhum -- o bot para de mandar input igual. O que muda é o custo: 4 acordadas
# por segundo em vez de 40, por conta, com 5 contas em paralelo.
#
# `_esperar_fatia` é quem faz a espera; ver o porquê do `hasattr` lá.
FATIA_DA_ESPERA = 0.25


class StopRequested(Exception):
    """Levantada quando o usuário pede parada; sobe até o supervisor."""


class FarmDesligado(Exception):
    """Levantada quando o usuário DESLIGA o BC no meio de uma fase.

    É uma parada mais fraca que a `StopRequested`: a conta volta ao estado
    "online" -- parada, logada, com o relogin ativo, pronta para o usuário
    assumir -- em vez de o bot inteiro desligar a sessão. Quem a vê do lado
    de fora não pode tratá-la como fim de sessão.

    Levantada por `BotContext.raise_if_stopped` quando a flag `farming` está
    ativa e `account.farms` apagou; capturada pelo `routine.run`, que devolve
    o controle limpo.
    """


class Disconnected(Exception):
    """Levantada quando o watchdog confirma queda; dispara o relogin."""


# Quantas vezes insistir para a câmera ficar no ângulo certo.
#
# 3, e é decisão do usuário em 25/08/2026: *"se não conseguir arrumar a câmera,
# tenta até 3x e segue a run, ainda mais que por hora estamos apenas testando"*.
#
# Cada tentativa custa uma escrita (microssegundos) mais uma leitura do
# termômetro. Não há espera no meio: se a escrita funciona, ela funciona na
# primeira; se não funciona, três tentativas provam isso sem custo perceptível.
TENTATIVAS_DE_AJUSTE_DA_CAMERA = 3


class BotContext:
    """Tudo que um ciclo de bot precisa para operar uma conta."""

    def __init__(
        self,
        config: BotConfig,
        account: Account,
        pid: int,
        hwnd: int,
        stop_event: threading.Event,
        pause_event: threading.Event | None = None,
    ) -> None:
        # `config` é o que pertence à máquina; `account.settings` é o que
        # pertence ao personagem. Manter os dois separados evita que ajustar
        # uma conta mexa nas outras.
        self.config = config
        self.account = account
        self.pid = pid
        self.hwnd = hwnd
        self.account_login = account.login
        self.stop_event = stop_event
        self.pause_event = pause_event or threading.Event()
        # True APENAS durante o `BossRushRoutine.run`: é o sinal que faz
        # `raise_if_stopped` detonar `FarmDesligado` quando `bc_farm` apagar no
        # meio de uma fase. Fora do farming a flag fica False, então a checagem
        # nunca alcança movimento/login/conta de reset que não é BC.
        self.farming = False

        self.log = logging.getLogger(f"blazes.{account.login}")

        self.input = Input(hwnd)
        # Tamanho real da janela manda; a resolução da interface é só um palpite.
        largura, altura = self.input.client_size()
        self.coords: Coords = coords_for_size(largura, altura)
        self.memory = Memory(pid)
        # SEM `pid`/`hwnd` FIXOS: eles mudam no relogin, e guardá-los aqui era
        # ler processo morto e capturar janela inexistente em silêncio. Cada
        # leitura recebe os atuais.
        self.target_hybrid = TargetHybrid(logger=self.log)
        self.templates = TemplateLibrary(Path("data") / "templates")

        # A ÚLTIMA QUEDA QUE O WATCHDOG RECONHECEU: `(chave, quadro)`.
        #
        # Mora aqui, e não no watchdog, porque existem DOIS watchdogs por conta
        # (um no supervisor, outro na rotina) e quem grava o histórico não sabe
        # qual dos dois percebeu -- mas o `ctx` é o mesmo para os dois.
        #
        # É também o FILTRO do que entra no histórico: `Disconnected` também é
        # levantada por leitura de memória ruim ("posição ilegível em goto()"),
        # que não é queda do jogo. Só o que o watchdog anotou aqui conta.
        self.ultima_queda: tuple[str, object] | None = None
        self.char_name: str | None = None
        self.runs_completed = 0
        self.start_gold: int | None = None
        self.stats = RunStats()

        # Watchdog injetado pela rotina: `None` até alguém configurar. Quem não
        # tem watchdog (ex: executor APP) nunca faz a checagem.
        self._watchdog: Watchdog | None = None

    @property
    def watchdog(self) -> Watchdog | None:
        """O watchdog configurado para esta conta, ou `None`."""
        return self._watchdog

    @watchdog.setter
    def watchdog(self, value: Watchdog | None) -> None:
        self._watchdog = value

    @property
    def settings(self) -> AccountSettings:
        """Configuração do personagem desta conta."""
        return self.account.settings

    # -- estado ------------------------------------------------------------

    def snapshot(self) -> GameState:
        """Lê o estado atual do jogo em uma passada."""
        m = self.memory
        state = GameState(timestamp=time.time())
        state.alive = m.alive()
        if not state.alive:
            return state
        state.hp = m.hp()
        state.max_hp = m.max_hp()
        state.mp = m.mp()
        state.max_mp = m.max_mp()
        state.position = m.position()
        state.mounted = m.is_mounted()
        state.sitting = m.is_sitting()
        state.pet_active = m.pet_active()
        state.bag_count = m.bag_count()
        # ==================================================================
        # O SNAPSHOT NÃO CAPTURA TELA -- decisão do usuário em 25/08/2026
        # ==================================================================
        #
        # Ele lia o alvo com `ler_alvo_snapshot()`, que **captura a janela**. E
        # `snapshot()` roda em alta frequência, em todas as contas, inclusive
        # fora de combate: navegando, vendendo, montando, no login. Ou seja, o
        # bot inteiro pagava captura para alimentar UMA linha de log (a de
        # registrar a morte do personagem).
        #
        # Palavras do usuário: *"quero que seja verificado a vida somente nos
        # pontos certos, então não deixe ficar capturando imagem toda hora"*.
        #
        # Fica o ID, que é leitura de memória (~1 µs) e responde "tem alvo?" e
        # "trocou?". A VIDA do alvo é lida onde ela decide algo: dentro do laço
        # de luta, em `CombatEngine._alvo_morreu`.
        target_id = self.target_hybrid.id_do_alvo(self.pid)
        state.target_name = f"ID:{target_id}" if target_id else None
        state.target_hp = None
        state.target_selected = target_id not in (0, None)
        state.modal_open = m.modal_open()
        state.location = m.location()
        return state

    # -- controle de fluxo -------------------------------------------------

    def tick(self, seconds: float = 0.2) -> None:
        """Dorme respeitando parada, pausa e saúde da sessão.

        Todo laço do bot chama tick() em vez de time.sleep(), para que
        parar e pausar funcionem de imediato em qualquer ponto.

        =================================================================
        "DE IMEDIATO" NÃO ERA VERDADE PARA ESPERAS LONGAS
        =================================================================

        A implementação anterior era `sleep(seconds)` -- UMA chamada só -- e o
        `raise_if_stopped` vinha DEPOIS dela. Numa espera curta isso não aparece,
        mas o bot tem esperas longas de propósito: 15 s por poção de vida, 3 s no
        vai-e-volta do altar, 4 s de teleporte. Nesses trechos, clicar em Parar
        não fazia nada até a espera terminar -- da tela, um congelamento.

        Agora o tempo é cumprido em FATIAS, conferindo a parada entre elas.

        =================================================================
        PORQUE O WATCHDOG ESTÁ AQUI
        =================================================================

        Antes desta checagem, o watchdog só era acionado em `_guard()` -- uma vez
        por iteração do laço principal da rotina. Durante combate
        (`atacar_ate_sair_de_combate`) e navegação (`follow_path`), laços que
        podem rodar dezenas de segundos sem voltar ao `_guard()`, uma queda
        (processo morre, janela some, "Connection interrupted" aparece) não era
        detectada. O bot continuava tentando enviar teclas e cliques para um
        cliente que já não existia.

        O watchdog faz sua própria rate-limiting interno (`VISUAL_CHECK_SECONDS`
        para a checagem visual; processo/janela são system calls baratos), então
        ligar a checagem em tick() é seguro: a cada fatia (0,05 s) o processo e a
        janela são verificados instantaneamente, e o template visual roda a cada
        20 s independentemente de com que frequência tick() é chamado.
        """
        self.wait_if_paused()
        self.check_watchdog()

        # Um sorteio, para o tempo todo -- exatamente como `sleep()` fazia.
        total = jitter(seconds)
        fim = monotonic() + total
        while True:
            self.raise_if_stopped()
            self.check_watchdog()
            restante = fim - monotonic()
            if restante <= 0:
                break
            self._esperar_fatia(min(FATIA_DA_ESPERA, restante))
        self.raise_if_stopped()
        self.check_watchdog()

    def _esperar_fatia(self, segundos: float) -> None:
        """Dorme uma fatia, acordando NO INSTANTE em que a parada for acionada.

        `Event.wait` devolve no `set()` e não custa nada enquanto espera; o
        `time.sleep` que estava aqui só descobria a parada no fim da fatia, e era
        por isso que a fatia precisava ser minúscula. Ver `FATIA_DA_ESPERA`.

        O `hasattr` não é defensividade solta: nem todo evento que chega até aqui
        é um `threading.Event`. Os testes injetam dublês que implementam apenas
        `is_set()` (ver `tests/test_context_watchdog.py`), e sem esta queda o
        dublê levantaria `AttributeError` no meio do laço -- o teste passaria a
        medir a espera em vez do watchdog que ele quer medir.
        """
        esperar = getattr(self.stop_event, "wait", None)
        if callable(esperar):
            esperar(segundos)
            return
        time.sleep(segundos)

    def check_watchdog(self) -> None:
        """Verifica saúde da sessão; levanta `Disconnected` se cair.

        Sem watchdog configurado (contas que não rodam BC), não faz nada.
        """
        if self._watchdog is None:
            return
        from .watchdog import DcReason
        reason = self._watchdog.check(None)
        if reason is not DcReason.NONE:
            raise Disconnected(reason.value)

    def raise_if_stopped(self) -> None:
        # Desligar o BC pela interface é uma parada, mas SÓ dentro do farming:
        # a conta volta a "online" (parada, logada, com relogin) em vez de parar
        # o bot inteiro. A flag `farming` só é True durante o `routine.run`, então
        # este braço nunca dispara em movimento não-BC, login ou conta de reset.
        if self.farming and not self.account.farms:
            raise FarmDesligado()
        if self.stop_event.is_set():
            raise StopRequested()

    def wait_if_paused(self) -> None:
        """Bloqueia enquanto a pausa estiver ativa.

        Chamada no ponto onde o input é ENVIADO, não só nos laços. A versão
        anterior só verificava a pausa em tick(), e como as sequências disparam
        vários cliques e teclas entre um tick e outro -- o login inteiro, por
        exemplo, não passava por tick nenhum -- clicar em Pausar não impedia o
        bot de continuar agindo. Verificar aqui garante que pausado significa
        "nenhuma tecla e nenhum clique saem".
        """
        while self.pause_event.is_set():
            if self.stop_event.is_set():
                raise StopRequested()
            time.sleep(0.075)
        self.raise_if_stopped()

    # -- atalhos de ação ---------------------------------------------------

    @property
    def keys(self):
        return self.account.settings.keys

    def press(self, key: str, hold: float = 0.10) -> bool:
        if not key:
            return False
        self.wait_if_paused()
        return self.input.key(key, hold=hold)

    def key_down(self, key: str) -> bool:
        """Segura uma tecla. SEMPRE com `key_up` num `finally`."""
        if not key:
            return False
        self.wait_if_paused()
        return self.input.key_down(key)

    def key_up(self, key: str) -> bool:
        if not key:
            return False
        return self.input.key_up(key)

    def click(self, point: tuple[int, int]) -> None:
        self.wait_if_paused()
        self.input.left_click(point[0], point[1])

    def right_click(self, point: tuple[int, int],
                    repetir: bool = True) -> None:
        """Clique direito. `repetir=False` para MOVIMENTO pelo minimapa.

        Ver `Input.right_click`: ali cada clique é uma ordem de andar, e a
        rajada calcula os cliques 2 a 4 de uma posição que o personagem já
        deixou -- o destino sai deslocado.
        """
        self.wait_if_paused()
        self.input.right_click(point[0], point[1], repetir=repetir)

    def park_cursor(self) -> None:
        """Devolve o cursor a um ponto neutro.

        Evita que o cursor fique sobre um elemento de UI e dispare tooltip
        ou hover que atrapalhe o próximo template matching.
        """
        self.click(self.coords.mouse_park)

    def apply_camera(self) -> None:
        """Põe a câmera na pose de referência E CONFERE se pegou.

        Sem câmera fixa, qualquer clique posicional na cena 3D vira loteria.

        =================================================================
        O QUE SE DESCOBRIU EM 25/08/2026
        =================================================================

        Esta escrita existe desde sempre e NUNCA tinha sido verificada.
        `ADDR_CAMERA` é herança do T-R0XX/GhostBot da versão **6139** e, na
        6400, ele resolve **NULO** -- ou seja, escreveu em lugar nenhum esse
        tempo todo, sem uma linha de log.

        O sintoma que o usuário relatou encaixa exatamente: *"o View Reset já
        quase deixa correto, mas só referente a esquerda e direita; cima e
        baixo ele não ajusta"*. O botão é do jogo e funciona; a parte que seria
        desta escrita, não.

        `ADDR_CAMERA_VIVA` (o mesmo endereço `+0x60`) responde, e escrever no
        `angulo` MOVE A CÂMERA -- medido. Cima/baixo tem conserto por memória,
        sem arrastar o mouse e sem abrir tela nenhuma.

        =================================================================
        A POSE, MEDIDA
        =================================================================

        `POSE_DA_CAMERA = (300.0, 0.0, 40.0)`, medida pelo usuário com o
        `17-LER-CAMERA` na pose em que os cliques funcionam. O **ângulo 40
        sempre esteve certo**; era o zoom que estava errado (380 na config
        herdada, 300 no jogo) -- e como a escrita caía no endereço morto, o
        número errado nunca chegou a ser aplicado.

        A pose é constante de MÓDULO, não configuração: mexe-se em
        `core/memory.py` e acabou. Ela é propriedade do JOGO, como os waypoints
        da cave -- conta nenhuma tem uma câmera diferente da outra.

        Escreve, confere lendo a struct de volta, e insiste até
        `TENTATIVAS_DE_AJUSTE_DA_CAMERA`. Depois disso vira AVISO e a run segue:
        câmera errada já era o estado normal de quem usa o bot hoje, e travar a
        run por ela seria trocar um incômodo por uma parada.

        NÃO ARRASTA O MOUSE. Ordem do usuário e regra do projeto.
        """
        alvo = POSE_DA_CAMERA
        z, r, a = alvo

        # A POSE EM USO APARECE NO LOG, uma vez por sessão. É o que torna a
        # constante TESTÁVEL sem depender de ninguém: trocou `POSE_DA_CAMERA`,
        # a primeira linha da sessão mostra o que pegou. Sem isso, testar uma
        # pose nova é palpite -- o mesmo buraco que deixou o zoom 380
        # sobreviver anos escrevendo num endereço morto.
        if getattr(self, "_pose_da_camera_logada", None) != alvo:
            self._pose_da_camera_logada = alvo
            self.log.info(
                "Câmera: pose alvo (zoom=%s, rotacao=%s, angulo=%s) — muda em "
                "blazesbot/core/memory.py, POSE_DA_CAMERA", z, r, a)

        for tentativa in range(1, TENTATIVAS_DE_AJUSTE_DA_CAMERA + 1):
            self.memory.set_camera(z, r, a)
            certo = self.memory.camera_na_pose_certa(alvo)
            if certo is None:
                # "Não sei": a struct não respondeu. Insistir às cegas mexeria
                # na câmera de quem estava certo.
                return
            if certo:
                if tentativa > 1:
                    self.log.info("Câmera na pose certa na tentativa %s",
                                  tentativa)
                return

        self.log.warning(
            "A CÂMERA NÃO FICOU NA POSE CERTA depois de %s tentativas: "
            "pose %s, esperada %s. Os cliques na cena 3D foram medidos na pose "
            "esperada, então eles podem errar. A run segue.",
            TENTATIVAS_DE_AJUSTE_DA_CAMERA, self.memory.camera_pose(), alvo,
        )

    def close(self) -> None:
        from ..core.vision import release_pool
        self.memory.close()
        release_pool(self.hwnd)
