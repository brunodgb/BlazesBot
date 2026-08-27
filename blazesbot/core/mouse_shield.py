"""Shield de Mouse Físico — hook externo (`SetWindowsHookEx`, `WH_MOUSE_LL`).

Impede o mouse FÍSICO do usuário de derrubar os cliques do bot, sem injetar
DLL nenhuma no processo do jogo.

=========================================================================
O QUE ELE CONSERTA — MEDIDO EM 18/08/2026
=========================================================================

O `blazesbot/bot/teste_do_cursor.py` mediu 20 cliques por condição, na janela
real, com o alvo a 760-980 px do cursor físico. Com o cursor EM MOVIMENTO sobre
a janela, que é o caso que interessa:

    sem shield   1/20 ( 5%)   personagem ANDOU em 14 dos 20 cliques
    com shield  20/20 (100%)  personagem andou em NENHUM

Ou seja: **sem o shield o bot é inutilizável enquanto o usuário mexe o mouse
sobre a janela do jogo.** Não é "melhora a taxa" -- é a diferença entre
funcionar e não funcionar. Com o cursor PARADO, as duas condições dão 20/20.

Duas conclusões:

1. **NÃO é `GetCursorPos`.** Com o cursor PARADO a 780 px do alvo, os 20
   cliques acertaram. Se o jogo lesse a posição do cursor, os 20 teriam caído
   onde o mouse estava. Foi a afirmação contrária -- que este arquivo sustentava
   sem nunca ter medido -- que motivou a DLL do TESTE 4
   (`docs/decisoes/dll-cursor-hook.md`): ela hookeava **a função errada**, e é
   por isso que "funcionou em laboratório e falhou em produção".

   *(Os dados NÃO separam "o jogo honra o lParam do botão" de "o jogo honra a
   posição que o `_prime_cursor` acabou de escrever" -- com o mouse parado as
   duas dão o mesmo resultado. A distinção não muda decisão nenhuma, e afirmá-la
   sem medir seria repetir o erro que custou a DLL.)*

2. **O que derruba o clique é o MOVIMENTO físico durante o clique.** O jogo usa
   a posição que ele mesmo rastreia pelas mensagens `WM_MOUSEMOVE`; um
   movimento físico no meio a sobrescreve, e o clique sai onde o mouse do
   usuário está. Com o mouse parado não há evento físico -- por isso parado
   sempre funcionou.

**E o desfecho ruim não é "o clique se perde": é o PERSONAGEM ANDAR.** O clique
que cai na cena 3D tira o personagem do lugar, o problema perseguido em cinco
pontos do `CLAUDE.md`.

Isso quase passou batido: a primeira medição deu 19-20/20 SEM shield, porque a
métrica automática perguntava "o minimapa mudou?" -- e o personagem andando
também muda o minimapa. **O clique errado era contado como acerto.** Quem viu o
defeito foi o usuário, na tela; a ferramenta passou a conferir a POSIÇÃO a cada
clique e a taxa real caiu de 95% para 5%. Uma métrica que confunde "mudou" com
"mudou pelo motivo certo" mede o próprio defeito como sucesso.

=========================================================================
O QUE NÃO FUNCIONA (medido, não deduzido)
=========================================================================

Reafirmar a coordenada entre o down e o up parece a correção óbvia e é PIOR
que não fazer nada: **12/20 (60%)** contra 19/20 sem tratamento. O motivo é que
esse `WM_MOUSEMOVE` extra vai com `MK_LBUTTON` no `wParam` -- "o mouse moveu
com o botão apertado", que É um arrasto. Em vez de impedir, fabrica um em todo
clique; na medição o jogo travou nesse estado por seis cliques seguidos, com
diferença de imagem 0,00.

Vale para os dois caminhos que fazem isso: `sendmessage_repetido` e
`sendmessage_rapido_reafirmado`, ambos em `inputs.py`. Estão marcados lá.

=========================================================================
COMO O CUSTO É MANTIDO PERTO DE ZERO
=========================================================================

Um hook `WH_MOUSE_LL` roda no caminho crítico de TODO evento de mouse do
sistema -- inclusive com o usuário trabalhando em outro programa. Se o callback
demora, o Windows atrasa o cursor de todo mundo (e acima de ~300 ms
`LowLevelHooksTimeout` simplesmente DESINSTALA o hook, em silêncio). Era esse o
"micro-stutter" aceito como tradeoff.

Três decisões o tiram do caminho:

  1. **A primeira pergunta é a mais barata que existe:** uma comparação de
     float contra `_ATE_QUANDO`, o instante em que o bloqueio mais longo
     termina. Fora de um clique do bot -- que é a esmagadora maioria do tempo --
     o callback devolve aqui, sem chamada Win32 nenhuma e sem lock.
  2. **Nenhum lock no callback.** A versão anterior pegava o MESMO `cls._lock`
     que a instalação segurava enquanto dormia até 1 s esperando o hook subir:
     todo evento de mouse do sistema ficava parado nessa fila, justamente o que
     estoura o `LowLevelHooksTimeout`. Aqui o callback só LÊ, e leitura de
     `dict`/float é atômica no CPython -- no pior caso lê o valor de um
     microssegundo atrás, que é inofensivo.
  3. **Retângulo em cache, não `WindowFromPoint`.** A versão anterior chamava
     `WindowFromPoint` (chamada entre processos) a cada evento. O retângulo da
     janela é capturado no `block_momentarily`, que roda na thread do BOT --
     fora do caminho crítico. De quebra some um defeito: `WindowFromPoint`
     devolve a janela-FILHA sob o cursor, que num cliente que renderiza em
     child window nunca bateria com o hwnd de topo guardado aqui.

E só o MOVIMENTO é engolido. Clique e roda do usuário passam sempre: eles não
mexem a posição, então não sobrescrevem a posição rastreada -- bloqueá-los
tirava do usuário a capacidade de usar a janela do jogo sem ganhar nada.

Por fim, o bloqueio é SOLTO no fim do clique (`liberar()`, chamado no `finally`
do `_click_sendmessage_rapido`). Os 80 ms viram TETO em vez de gasto: medido,
o mouse do usuário fica preso ~5 ms em vez de 80. Ver `liberar()`.
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import POINTER, c_int, c_void_p, windll
from ctypes.wintypes import DWORD, HWND, LONG, LPARAM, MSG, POINT, RECT, WPARAM

log = logging.getLogger("blazes.mouse_shield")

# ===========================================================================
# Constantes Win32
# ===========================================================================

WH_MOUSE_LL = 14

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205

HC_ACTION = 0

# Quanto tempo o retângulo da janela vale antes de ser relido. A janela do jogo
# não se move sozinha; relê-lo a cada clique seria trabalho à toa.
VALIDADE_DO_RETANGULO = 2.0


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", POINTER(ctypes.c_ulong)),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(LONG, c_int, WPARAM, LPARAM)

user32 = windll.user32

user32.SetWindowsHookExW.argtypes = [c_int, HOOKPROC, c_void_p, DWORD]
user32.SetWindowsHookExW.restype = c_void_p
user32.CallNextHookEx.argtypes = [c_void_p, c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LONG
user32.UnhookWindowsHookEx.argtypes = [c_void_p]
user32.UnhookWindowsHookEx.restype = ctypes.c_bool
user32.GetMessageW.argtypes = [POINTER(MSG), HWND, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = ctypes.c_bool
user32.GetWindowRect.argtypes = [HWND, POINTER(RECT)]
user32.GetWindowRect.restype = ctypes.c_bool

# ===========================================================================
# Estado lido pelo callback — de propósito em módulo, e de propósito sem lock
# ===========================================================================
#
# `_ATE_QUANDO` é a porta de entrada: enquanto `time.time()` for maior que ele,
# NENHUM bloqueio está ativo e o callback devolve na primeira linha. Ele se
# limpa sozinho pela passagem do tempo -- não há o que zerar nem quem zere.
_ATE_QUANDO: float = 0.0

# hwnd -> (instante_final, retangulo, instante_inicial) da janela bloqueada.
# O instante inicial existe só para o `liberar()` conseguir dizer quanto tempo o
# mouse do usuário ficou de fato preso -- é o número que diz se o teto está
# sendo pago à toa.
_BLOQUEIOS: dict[int, tuple[float, tuple[int, int, int, int], float]] = {}


def _retangulo(hwnd: int) -> tuple[int, int, int, int]:
    r = RECT()
    user32.GetWindowRect(HWND(hwnd), ctypes.byref(r))
    return int(r.left), int(r.top), int(r.right), int(r.bottom)


class MouseShield:
    """Shield de mouse físico para uma janela do jogo.

        shield = MouseShield(hwnd)
        shield.block_momentarily(duration_ms=80.0)   # antes do clique do bot
        input.left_click(x, y)

    O hook `WH_MOUSE_LL` é UM só, global ao processo do bot, compartilhado por
    todas as instâncias -- instalar um por conta multiplicaria por N o custo em
    cada evento de mouse do sistema. O que é por janela é o BLOQUEIO.
    """

    _hook_handle = None
    _hook_thread = None
    _hook_installed = False
    _callback = None
    _lock = threading.Lock()      # protege a INSTALAÇÃO, nunca o callback

    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        self._rect: tuple[int, int, int, int] | None = None
        self._rect_lido_em = 0.0
        self._ensure_hook_installed()

    # -- instalação ------------------------------------------------------
    @classmethod
    def _ensure_hook_installed(cls) -> None:
        """Sobe o hook uma vez. NADA aqui bloqueia o callback."""
        with cls._lock:
            if cls._hook_installed or cls._hook_thread is not None:
                return
            cls._callback = HOOKPROC(_mouse_proc)
            cls._hook_thread = threading.Thread(
                target=cls._loop_do_hook, daemon=True,
                name="MouseShieldHook")
            cls._hook_thread.start()
        # A ESPERA FICA FORA DO LOCK. Dentro dele, um evento de mouse que
        # chegasse durante a instalação ficaria parado até 1 s -- e é o próprio
        # atraso que faz o Windows desinstalar o hook por timeout.
        for _ in range(20):
            if cls._hook_handle:
                cls._hook_installed = True
                return
            time.sleep(0.05)
        log.warning("MouseShield: o hook não subiu em 1 s; seguindo sem ele")

    @classmethod
    def _loop_do_hook(cls) -> None:
        cls._hook_handle = user32.SetWindowsHookExW(
            WH_MOUSE_LL, cls._callback, None, 0)
        if not cls._hook_handle:
            log.error("MouseShield: SetWindowsHookExW falhou (erro %s)",
                      ctypes.get_last_error())
            return
        log.info("MouseShield: hook instalado")
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
            pass

    # -- uso -------------------------------------------------------------
    def block_momentarily(self, duration_ms: float = 80.0) -> None:
        """Engole o MOVIMENTO físico sobre esta janela pelos próximos X ms.

        Roda na thread do BOT, e é aqui que fica todo o trabalho: ler o
        retângulo da janela (com validade, porque ela não anda sozinha) e
        publicar o instante final. O callback só compara números.

        80 ms é o valor do usuário, medido por ele na mão: 15 ms era curto
        demais e o movimento físico passava por baixo. O clique síncrono em si
        leva ~5 ms -- a margem existe porque o hook tem 1-2 ms de latência para
        reagir e o movimento pode chegar antes.
        """
        global _ATE_QUANDO
        agora = time.time()
        if self._rect is None or agora - self._rect_lido_em > VALIDADE_DO_RETANGULO:
            self._rect = _retangulo(self.hwnd)
            self._rect_lido_em = agora
        ate = agora + (duration_ms / 1000.0)
        _BLOQUEIOS[self.hwnd] = (ate, self._rect, agora)
        if ate > _ATE_QUANDO:
            _ATE_QUANDO = ate

    def liberar(self) -> float:
        """Encerra o bloqueio desta janela AGORA. Devolve quanto durou, em ms.

        =====================================================================
        POR QUE ISTO EXISTE (e por que 80 ms podia ser encurtado sem risco)
        =====================================================================

        Os 80 ms nunca foram "o tempo do clique" -- o clique síncrono inteiro
        (prime + down + 2 ms + up) termina em ~5 ms. Eles são margem para o
        ATRASO DE AGENDAMENTO: entre marcar o bloqueio e mandar o `up`, a
        thread do bot pode ser preemptada (GIL, N contas em paralelo), e um
        teto curto expiraria NO MEIO do clique. Foi por isso que o 15 ms
        calculado reprovou na prática.

        Mas margem para o atraso não precisa ser paga quando o atraso NÃO
        acontece. Soltando o bloqueio logo depois do `up`, o mouse do usuário
        fica preso pelo tempo REAL do clique (~5 ms) em vez dos 80 ms de teto,
        e o teto passa a valer só para o caso em que a thread de fato atrasou
        -- que é exatamente quando ele é necessário.

        Não muda nada para o bot: o intervalo protegido continua sendo o mesmo,
        do prime ao up. O que encolhe é o rabo inútil depois do clique.
        """
        global _ATE_QUANDO
        marca = _BLOQUEIOS.pop(self.hwnd, None)
        # `_ATE_QUANDO` é o máximo entre as janelas: com N contas, soltar uma
        # não pode liberar as outras. Recalcular custa N comparações, na thread
        # do bot -- fora do caminho crítico do callback.
        _ATE_QUANDO = max((ate for ate, _r, _i in _BLOQUEIOS.values()),
                          default=0.0)
        if marca is None:
            return 0.0
        return max(0.0, (time.time() - marca[2]) * 1000.0)

    def is_blocked(self) -> bool:
        marca = _BLOQUEIOS.get(self.hwnd)
        return bool(marca and time.time() < marca[0])

    @classmethod
    def uninstall_hook(cls) -> None:
        """Remove o hook global. DEIXA O ESTADO PRONTO PARA REINSTALAR.

        A versão anterior zerava `_hook_handle` e `_hook_installed` mas deixava
        `_hook_thread` preenchido -- e `_ensure_hook_installed` começa com
        `if cls._hook_installed or cls._hook_thread is not None: return`. Depois
        de um `uninstall_hook`, todo `MouseShield` novo (um por relogin, porque
        cada `Input` cria o seu) retornava de imediato e seguia SEM HOOK, em
        silêncio: aquele `return` não loga nada.

        O custo disso está medido no topo deste arquivo: sem o shield, com o
        mouse do usuário em movimento sobre a janela, o bot cai de 20/20 para
        1/20 e o personagem ANDA em 14 dos 20 cliques. O bot ficaria inutilizável
        sem uma linha de aviso.
        """
        with cls._lock:
            if cls._hook_handle:
                user32.UnhookWindowsHookEx(cls._hook_handle)
                log.info("MouseShield: hook removido")
            cls._hook_handle = None
            cls._hook_installed = False
            # A THREAD TAMBÉM É ESQUECIDA. Ela fica presa em `GetMessageW` sem
            # hook para servir, mas é daemon e morre com o processo; o que não
            # pode é ela bloquear a reinstalação para sempre.
            cls._hook_thread = None
            _BLOQUEIOS.clear()


def _mouse_proc(nCode: int, wParam: int, lParam: int) -> int:
    """Callback do hook. Devolve 1 para engolir o evento.

    FUNÇÃO DE MÓDULO, e não um closure dentro do `_ensure_hook_installed`: o
    callback tem que sobreviver enquanto o hook existir, e um closure preso a
    um método de classe é fácil de perder de vista na hora de mexer.

    A ORDEM DAS PERGUNTAS É O DESENHO. Da mais barata para a mais cara, para o
    caso comum (nenhum clique do bot acontecendo) sair na primeira linha.
    """
    if nCode == HC_ACTION and wParam == WM_MOUSEMOVE:
        agora = time.time()
        if agora < _ATE_QUANDO:          # <- caminho comum sai ANTES daqui
            pt = ctypes.cast(lParam, POINTER(MSLLHOOKSTRUCT)).contents.pt
            x, y = pt.x, pt.y
            for ate, (esq, topo, dir_, baixo), _inicio in list(
                    _BLOQUEIOS.values()):
                if agora < ate and esq <= x <= dir_ and topo <= y <= baixo:
                    return 1
    # Clique e roda do usuário NUNCA são engolidos: não mexem a posição, então
    # não criam o arrasto que derruba o clique do bot.
    return user32.CallNextHookEx(None, nCode, wParam, lParam)
