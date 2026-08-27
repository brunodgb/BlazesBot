"""
Envio de teclado e mouse para a janela do cliente via mensagens do Windows.

Por que SendMessage e não SendInput: o cliente do Talisman Online processa
a fila de mensagens da janela, então dá para controlá-lo SEM foco e SEM
mover o cursor real. Isso permite N contas minimizadas em paralelo.

CLIQUE SÍNCRONO (SendMessageW): todos os cliques do mouse (e o WM_MOUSEMOVE
que o precede) vão direto ao WndProc via SendMessageW, com a coordenada alvo
no lParam. O cursor físico nunca é movido. Foi o comportamento original do bot
(BlazesBot18-22), e é o que funciona — voltamos a ele depois de experimentar
PostMessage e um "segundo mouse virtual" por hook que só atrapalharam.

ATENÇÃO -- UIPI: o jogo roda elevado. Um processo de integridade média não
consegue enviar mensagens para janela de processo elevado; as mensagens são
descartadas silenciosamente, sem erro. O BlazesBot PRECISA rodar como
administrador.

NOTA HISTÓRICA: chegamos a testar um "segundo mouse virtual" via inline hook
no user32 (DLL injeta no processo do jogo e intercepta GetCursorPos/SetCursorPos)
e também o PostMessage. Ambos se mostraram problemáticos em produção e foram
ABANDONADOS: o clique voltou a ser SendMessageW síncrono com a coordenada no
lParam, protegido pelo Mouse Shield (hook externo WH_MOUSE_LL). Documentado em
`docs/decisoes/dll-cursor-hook.md`.

MOUSE SHIELD: Hook externo WH_MOUSE_LL que bloqueia eventos de mouse físico de
interferir nos cliques do bot. Não injeta DLL no jogo — roda no processo do bot.
Ativado por interruptor USAR_MOUSE_SHIELD.
"""
from __future__ import annotations

import ctypes
import logging
import random
import time
from ctypes.wintypes import DWORD, HWND, LPARAM, RECT, WPARAM

try:
    from .mouse_shield import MouseShield
    MOUSE_SHIELD_DISPONIVEL = True
except Exception:
    MOUSE_SHIELD_DISPONIVEL = False
    MouseShield = None  # type: ignore


_logger = logging.getLogger("blazes.inputs")

user32 = ctypes.windll.user32

# Tipos declarados para não truncar HWND/coordenadas em builds 64 bits.
# ===========================================================================
# INTERRUPTOR DO MOUSE SHIELD
# ===========================================================================
#
# True  = Ativa o hook externo que bloqueia mouse físico sobre a janela do jogo
#         durante cliques do bot. Hook WH_MOUSE_LL (não injeta DLL).
# False = Desligado (comportamento original, mouse físico interfere)
#
# DESLIGADO com `postmessage_puro` (18/08/2026, decisão do usuário depois de
# testar as duas configurações em produção).
#
# O MOTIVO É DE MECANISMO, e é o que ele observou: *"por ser assíncrono ele não
# funciona como quando usa o SendMessage"*.
#
# No caminho SÍNCRONO o shield protege um intervalo CONHECIDO: do prime ao up, e
# o retorno do `SendMessageW` prova quando acabou -- por isso o `liberar()` no
# `finally` reduz os 80 ms de teto para ~5 ms de gasto real.
#
# No caminho POSTADO não há esse intervalo. As mensagens ficam na fila até o jogo
# bombear, e não existe sinal de quando isso aconteceu. O bloqueio vira um chute
# de 80 ms que pode terminar antes ou depois da hora -- e enquanto isso o mouse
# do usuário fica preso os 80 ms INTEIROS dentro da janela, sem o desconto que o
# caminho síncrono tem.
#
# Ou seja: com PostMessage o shield cobra o preço cheio e não entrega a
# proteção precisa. Desligado, o mouse do usuário fica inteiramente livre e não
# existe hook global nenhum no processo.
#
# A FIAÇÃO CONTINUA NO LUGAR (`_click_postmessage_puro` chama
# `block_momentarily` sob `if self._shield`), no padrão de interruptor do
# projeto: religar é trocar esta palavra, sem código morto e sem código novo.
#
# O shield existia para impedir que um `WM_MOUSEMOVE` FÍSICO furasse a ordem das
# nossas mensagens. Com `postmessage_puro` esse mecanismo DEIXA DE EXISTIR: as
# quatro mensagens são POSTADAS na fila, saem em FIFO, e um move físico que
# chegue no meio entra na fila ATRÁS delas -- não fura nada.
#
# Medido com o mouse do usuário em movimento sobre a janela:
#
#     PostMessage, mouse LIVRE (sem bloqueio)   40/40, 0 andadas do personagem
#     SendMessage + shield (o padrão anterior)  16/20, 4 andadas
#     SendMessage sem shield                     6/20, 14 andadas
#
# (As 40 amostras vêm das duas fases de PostMessage da corrida: `block_momentarily`
# só é chamado dentro de `_click_sendmessage_rapido`, então mesmo a fase rotulada
# "com shield" rodou com o mouse físico inteiramente livre. As duas eram o mesmo
# teste, e somam.)
#
# COM ISTO DESLIGADO NÃO EXISTE HOOK GLOBAL NENHUM: o `MouseShield` nem é criado,
# e o mouse do usuário para de pagar a travessia do `WH_MOUSE_LL` a cada evento.
#
# FICA EM ABERTO, e não vale fingir que não: rodando com PostMessage sem shield
# o usuário observou que *"ainda tem vezes que acaba não clicando todas as vezes
# se eu mexo o mouse na janela do jogo"*. Melhor que SendMessage, não perfeito.
# O shield foi testado como resposta a isso e não compensou (acima). A causa
# dessas perdas residuais NÃO está explicada -- e não será chutada aqui.
#
# ATENÇÃO AO REVERTER PARA `sendmessage_rapido`: ele PRECISA deste interruptor em
# `True` (sem shield deu 6/20), e custa MUITO mais caro do que se supunha.
#
# MEDIDO em 19/08/2026 (`instrumentar_clique.py`), com o mouse do usuário em
# movimento: `SendMessageW` prende a thread do bot por **112 ms POR CLIQUE**, não
# pelos ~5 ms que este arquivo estimava -- ele espera a thread do jogo, que está
# ocupada com a enxurrada de eventos do mouse. Na venda, onde os cliques saem a
# cada 65 ms, isso faria a sequência inteira rodar a um terço da velocidade.
#
# De ponta a ponta o PostMessage é MAIS RÁPIDO (105,8 ms contra 129,5 ms) e ainda
# acerta mais (39/40 contra 37/40).
USAR_MOUSE_SHIELD = False

# TETO do bloqueio do mouse físico, em milissegundos -- e TETO, não gasto: o
# clique solta o bloqueio no `finally`, então na prática ele dura o tempo REAL
# do clique (~5 ms). O teto só é pago quando a thread do bot é preemptada no
# meio do clique (GIL, N contas em paralelo), que é exatamente quando ele
# precisa existir.
#
# 80 e não 15: o 15 foi CALCULADO ("o clique dura ~5 ms, 3x de margem basta") e
# reprovou na prática -- o movimento físico passava por baixo. Quem mediu foi o
# usuário, na mão. O número calculado perdeu para o medido.
TETO_DO_BLOQUEIO_MS = 80.0

# ===========================================================================
# INTERRUPTOR DO MODO DE CLIQUE
# ===========================================================================
#
# "sendmessage"           -- o de SEMPRE, e o padrão. Único com histórico de
#                            funcionar em produção.
# "sendmessage_repetido"  -- MEDIDO E REPROVADO (18/08/2026). Reafirma o
#                            WM_MOUSEMOVE colado ao botão. O move extra vai com
#                            MK_LBUTTON, ou seja "moveu com o botão apertado" =
#                            ARRASTO: fabrica em todo clique exatamente o que
#                            derrubava os cliques. Medido no gêmeo
#                            `sendmessage_rapido_reafirmado`: 60% contra 95% de
#                            não fazer nada. NÃO LIGAR.
# "postmessage_hibrido"   -- REPROVADO, e a CAUSA foi identificada em 18/08/2026:
#                            ele posta o MOVE e manda os BOTÕES por SendMessage.
#                            SendMessage FURA A FILA e chega ANTES do move
#                            postado -- o docstring dele dizia que os botões
#                            síncronos "garantem ordem correta" e era o oposto.
#                            Ele GARANTIA a inversão. NÃO LIGAR.
# "postmessage_com_delay" -- REPROVADO pelo MESMO defeito: os botões também são
#                            SendMessage, só com um sleep antes. A conclusão que
#                            estes dois produziram ("PostMessage é instável com
#                            este jogo") era falsa: nenhum dos dois testou
#                            PostMessage no clique. NÃO LIGAR.
# "sendmessage_rapido"    -- EXPERIMENTO (2026-08-14 TESTE 2): Mantém SendMessage
#                            (síncrono, funciona sempre) mas reduz sleep de 15ms
#                            para 1ms. Reduz 93% do bloqueio mantendo estabilidade.
# "postmessage_puro"      -- MEDIDO E APROVADO (18/08/2026). AS QUATRO mensagens
#                            por PostMessageW, nenhuma síncrona. Com o mouse do
#                            usuário em movimento sobre a janela:
#                              PostMessage + shield  20/20, 0 andadas
#                              PostMessage SEM shield 20/20, 0 andadas
#                              SendMessage + shield  16/20, 4 andadas  <- o padrão
#                            Controle negativo na mesma corrida (reafirmado):
#                            9/20, 11 andadas -- a medição sabia detectar falha.
# "trox_sequence"         -- EXPERIMENTO (2026-08-15): Sequência exata do T-R0XX bot
#                            (SetCursor com lParam específico ANTES do clique).
#                            Hipótese: sincroniza posição interna do jogo antes do clique.
#
# Interruptor e não código comentado, no mesmo padrão do `USAR_TAB_NOS_GUARDAS`:
# os dois caminhos ficam vivos, voltar é trocar uma palavra, e nada apodrece
# comentado. Pedido explícito do usuário ao abrir esta investigação.
# EM TESTE desde 18/08/2026 (decisão do usuário: "já que funcionou sem o shield,
# vamos fazer um primeiro teste sem ele direto no bot"). O padrão anterior era
# `"sendmessage_rapido"`, e voltar é trocar esta palavra E religar o shield.
#
# O QUE OBSERVAR NESTA PRIMEIRA NOITE: a TAXA DE ENTRADA NA CAVE. É o ponto que
# mais depende de clique DIREITO abrindo diálogo, e a medição que aprovou o
# PostMessage usou só clique ESQUERDO num botão de UI -- então é ali que uma
# regressão apareceria primeiro. O log de dev já registra cada abertura e o teto
# adaptativo (`Diálogo abriu em N ms`).
#
# O que a medição NÃO cobriu, e por isso isto é um TESTE e não uma conclusão:
# clique direito (inclusive a rajada de 2 com 22 ms), abertura de diálogo, e o
# comportamento com várias contas em paralelo.
MODO_DE_CLIQUE = "postmessage_puro"

# ===========================================================================
# INTERRUPTOR DO TECLADO -- "sendmessage" | "postmessage"
# ===========================================================================
#
# O CLIQUE migrou para `PostMessageW` em 18/08/2026; a TECLA ficou para trás, e
# ficou para trás justamente onde dói mais.
#
# O PRÊMIO DO PostMessage NUNCA FOI O STUTTERING. Está escrito em
# `docs/decisoes/stuttering-mouse.md`, na seção "O prêmio maior não é o
# stuttering": `SendMessageW` NÃO TEM TIMEOUT. Um cliente que para de bombear a
# fila de mensagens -- que é exatamente o cenário do "Connection interrupted",
# o que este bot existe para detectar -- prende a thread daquela conta PARA
# SEMPRE. O `watchdog.check()` que dispararia o relogin nunca é alcançado, e a
# conta morre em silêncio dizendo "Rodando".
#
# COM A TECLA EM `SendMessageW`, ESSE DEFEITO CONTINUAVA INTEIRO:
#
#   * o ecossistema APP é uma macro de TECLADO -- 100% do trabalho dele passa
#     por aqui, e nenhum clique o socorre;
#   * o BC aperta tecla o tempo todo (skills, poção, montaria, TAB), então a
#     mesma trava alcança o farm;
#   * o LOGIN digita usuário e senha por `type_text` e limpa campo por
#     `clear_field` -- travar ali é travar na tela de credenciais, que é onde o
#     cliente mais costuma parar de responder.
#
# O QUE MUDA, E O QUE NÃO MUDA. Mensagens POSTADAS na mesma fila saem em FIFO,
# então down e up chegam na ordem em que foram mandados. O `hold` entre eles
# fica: postadas as duas de uma vez, o jogo poderia processá-las na MESMA
# passada do laço dele -- uma tecla de duração zero, que algumas UIs recusam.
# É a mesma razão dos 2 ms do `_click_postmessage_puro`.
#
# O QUE SE PERDE: a confirmação implícita. `SendMessageW` só retorna depois de o
# WndProc rodar; `PostMessageW` retorna assim que enfileira. O projeto já não
# confia nessa confirmação (a regra é conferir o efeito e repetir), e é o mesmo
# custo que já foi aceito no clique.
#
# O `lParam` SEGUE EM ZERO, DE PROPÓSITO. Teclado real carrega scan code e, no
# KEYUP, os bits 30/31 de transição. Este cliente aceita zero -- é o que sempre
# foi mandado por `SendMessageW`. Mudar o mecanismo E o conteúdo da mensagem no
# mesmo passo tornaria impossível saber a qual dos dois creditar uma regressão.
#
# REVERTER: `"sendmessage"` aqui, e nada mais.
MODO_DE_TECLA = "postmessage"

user32.SendMessageW.argtypes = [HWND, ctypes.c_uint, WPARAM, LPARAM]
user32.PostMessageW.argtypes = [HWND, ctypes.c_uint, WPARAM, LPARAM]

# Mensagens de teclado
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102

# Mensagens de mouse
WM_SETCURSOR = 0x0020
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205

HTCLIENT = 1
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002

# ===========================================================================
# QUANTOS CLIQUES DIREITOS POR TENTATIVA
# ===========================================================================
#
# Vale para TODO clique direito do bot -- NPC, Altar Stone, saída da cave,
# movimento pelo mapa. `1` devolve o comportamento de sempre; a explicação
# completa (o porquê, o custo e o risco) está em `Input.right_click`.
#
# NÃO se aplica ao clique ESQUERDO. Lá o risco é outro e maior: o clique
# esquerdo em link de diálogo e em item de bolsa tem efeito por clique -- quatro
# cliques num item da grade de venda gastariam quatro da contagem do usuário, e
# quatro no link de um NPC repetiriam o pedido.
CLIQUES_DIREITOS_POR_TENTATIVA = 10

# Espaço entre um clique e o seguinte. Curto de propósito: a aposta é que a
# rajada chegue dentro da mesma "janela" em que o cliente estava ocupado.
INTERVALO_ENTRE_CLIQUES_DIREITOS = 0.044

VK_CODES: dict[str, int] = {
    **{str(i): 0x30 + i for i in range(10)},           # 0-9
    **{chr(c): c for c in range(0x41, 0x5A + 1)},      # A-Z
    **{f"F{i}": 0x6F + i for i in range(1, 13)},       # F1-F12
    **{f"NUM{i}": 0x60 + i for i in range(10)},        # Numpad 0-9
    "ALT": 0x12,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "ENTER": 0x0D,
    "BACKSPACE": 0x08,
    "SPACE": 0x20,
    "TAB": 0x09,
    "ESC": 0x1B,
    "DELETE": 0x2E,
    "INSERT": 0x2D,
    "HOME": 0x24,
    "END": 0x23,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
}


# ===========================================================================
# NENHUMA MENSAGEM SAI PARA UMA JANELA QUE NÃO É O JOGO
# ===========================================================================
#
# DEFEITO RELATADO EM 25/08/2026, no login:
#
#     *"tem vezes que o clique das teclas está vazando... 'rggddwlqrjcrw'
#      digitou isso no bloco de notas enquanto abria o jogo e foi sozinho...
#      teve vezes que do nada no jogo começou a abrir janelas aleatórias...
#      quando a conta logava parava"*
#
# COMO ISSO É POSSÍVEL com `PostMessageW`, que entrega a UMA janela só:
#
#   1. **O Windows RECICLA HWND.** A janela do cliente morre (queda, relogin,
#      cliente fechado) e o mesmo número de handle é entregue a OUTRA janela --
#      o Bloco de Notas, o navegador, outro cliente. O `Input` guardava o `hwnd`
#      no `__init__` e não conferia nunca mais.
#   2. **`hwnd = 0xFFFF` é `HWND_BROADCAST`** e entrega a TODAS as janelas de
#      topo de uma vez. Explicaria os dois sintomas ao mesmo tempo: texto no
#      Bloco de Notas E painéis abrindo no jogo.
#   3. **Um `hwnd` de outra conta** faz uma conta digitar na janela da outra.
#
# O login é onde isso mais aparece porque é onde a janela está NASCENDO: o
# supervisor pode ter o handle de antes, e a digitação de usuário/senha é o
# trecho com mais teclas seguidas do bot inteiro. *"Quando a conta logava
# parava"* -- porque a digitação acabou.
#
# A TRAVA: toda mensagem confere, ANTES de sair, que o `hwnd`
#
#   * não é zero, não é `HWND_BROADCAST`, não é negativo;
#   * ainda é uma janela viva (`IsWindow`);
#   * **ainda pertence ao MESMO processo** de quando o `Input` foi criado;
#   * e esse processo, quando dá para saber, é um `client.exe`.
#
# Falhou qualquer uma, a mensagem NÃO SAI e o motivo vai para o log. Bloquear é
# o lado seguro do erro: uma tecla perdida custa uma repetição, uma tecla na
# janela errada custa senha vazada em arquivo de texto alheio.
#
# "NÃO SEI" NÃO É "NÃO É O JOGO". Se o nome do processo não puder ser lido
# (`AccessDenied` do `psutil`, processo morrendo no meio), a trava CONTINUA
# deixando passar, confiando no pino do PID -- que já segura o defeito relatado.
# Bloquear por leitura falhada trocaria um defeito raro por um permanente: o bot
# mudo. É a mesma regra da régua da barra de vida, que também sabe dizer
# "não sei" sem que isso vire veredito.
NOME_DO_PROCESSO_DO_JOGO = "client.exe"

# `HWND_BROADCAST`. Mandar mensagem para cá acerta TODA janela de topo do
# sistema -- é o valor que transformaria um bug de handle em digitação
# simultânea em tudo que está aberto.
HWND_BROADCAST = 0xFFFF

# INTERRUPTOR. Desligar volta ao comportamento anterior (mandar sem conferir), e
# existe só para o teste poder provar que a trava é o que segura o vazamento.
# NÃO DESLIGAR EM PRODUÇÃO.
CONFERIR_A_JANELA_ANTES_DE_ENVIAR = True

# De quanto em quanto tempo o NOME do processo é reconferido.
#
# O dono da janela (o PID) é conferido a CADA mensagem, porque custa uma syscall.
# O nome do processo custa mais, e só muda se o PID for reciclado -- que é raro e
# lento. Reconferir de dois em dois segundos fecha esse buraco sem pesar.
SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO = 2.0


def _dono_da_janela(hwnd: int) -> int | None:
    """O PID dono de uma janela, ou `None` se não deu para saber."""
    try:
        pid = DWORD(0)
        user32.GetWindowThreadProcessId(HWND(hwnd), ctypes.byref(pid))
        return int(pid.value) or None
    except Exception:
        return None


def _nome_do_processo(pid: int | None) -> str | None:
    """O nome do executável de um PID. `None` = **não consegui saber**.

    `None` NÃO É "não é o jogo", e a diferença é o que separa uma trava de um
    tiro no pé. Se `psutil` levantar `AccessDenied` num momento ruim e isso
    valesse "não é o jogo", a trava bloquearia o bot inteiro -- trocando um
    defeito raro (tecla na janela errada) por um permanente (bot mudo).

    Quem chama trata os três casos separadamente. Ver `_motivo_para_nao_enviar`.
    """
    if not pid:
        return None
    try:
        import psutil

        return psutil.Process(pid).name().lower()
    except Exception:
        return None


def jitter(base: float, spread: float = 0.15) -> float:
    """Aplica variação aleatória a um delay.

    Delays perfeitamente fixos (0.5, 1.0, 2.0...) são assinatura óbvia de
    automação. Todo sleep do bot passa por aqui.
    """
    return max(0.01, base * (1.0 + random.uniform(-spread, spread)))


def sleep(base: float, spread: float = 0.15) -> None:
    time.sleep(jitter(base, spread))


def _lparam(x: int, y: int) -> LPARAM:
    return LPARAM((y << 16) | (x & 0xFFFF))


class Input:
    """Fachada de input para uma janela específica."""

    def __init__(self, hwnd: int) -> None:
        self.hwnd = hwnd
        # O DONO DA JANELA NO INSTANTE DA CRIAÇÃO. É contra ele que toda
        # mensagem posterior é conferida -- ver `_janela_confiavel`. Guardar o
        # PID e não só o HWND é o que sobrevive à reciclagem de handle: o
        # Windows entrega o mesmo número de janela para outro processo, mas não
        # entrega o mesmo processo.
        self._pid_da_janela = _dono_da_janela(hwnd)
        self._nome_do_processo = _nome_do_processo(self._pid_da_janela)
        self._conferido_em = time.monotonic()
        self._bloqueadas = 0
        self._motivo_do_bloqueio: str | None = None

        if CONFERIR_A_JANELA_ANTES_DE_ENVIAR:
            if self._pid_da_janela is None:
                # A janela ainda não diz de quem é. Acontece no login, em que
                # ela está nascendo. O pino se fecha na primeira mensagem que
                # conseguir ler o dono -- ver `_motivo_para_nao_enviar`.
                _logger.debug(
                    "Input em hwnd=%s: dono ainda desconhecido; o pino fecha "
                    "no primeiro envio.", hwnd)
            elif self._nome_do_processo is None:
                # NÃO BLOQUEIA. O pino do PID já segura o defeito relatado (o
                # Windows reciclando o handle), e bloquear por uma leitura que
                # falhou deixaria o bot mudo por um problema do `psutil`.
                _logger.warning(
                    "Input em hwnd=%s (pid=%s): não consegui ler o nome do "
                    "processo. Sigo, mas confiando só no pino do PID.",
                    hwnd, self._pid_da_janela)
            elif self._nome_do_processo != NOME_DO_PROCESSO_DO_JOGO:
                _logger.error(
                    "Input criado para hwnd=%s, que é do processo %r e NÃO de "
                    "%s (pid=%s). Nenhuma tecla ou clique vai sair daqui.",
                    hwnd, self._nome_do_processo, NOME_DO_PROCESSO_DO_JOGO,
                    self._pid_da_janela)
        # Teclas SEGURADAS e quantos blocos aninhados querem cada uma. Ver
        # `key_down`. Por `Input`, ou seja por janela: uma conta não solta a
        # tecla da outra.
        self._teclas_presas: dict[str, int] = {}

        _logger.info(f"Input.__init__ chamado (hwnd={hwnd})")

        # Mouse shield: bloqueia mouse físico durante cliques (hook externo)
        self._shield = None
        if USAR_MOUSE_SHIELD and MOUSE_SHIELD_DISPONIVEL and MouseShield:
            try:
                self._shield = MouseShield(hwnd)
            except Exception as e:
                _logger.warning(f"Falha ao criar MouseShield: {e}")
                self._shield = None

    # -- a trava da janela -------------------------------------------------

    def _janela_confiavel(self) -> bool:
        """A `self.hwnd` ainda é A janela do jogo para a qual este `Input` nasceu?

        Conferido ANTES de cada mensagem. Ver o bloco
        `NENHUMA MENSAGEM SAI PARA UMA JANELA QUE NÃO É O JOGO`, no topo, para o
        defeito que isto impede.

        Barato: `IsWindow` e `GetWindowThreadProcessId` são syscalls de
        microssegundos. O nome do processo, que custa mais, é reconferido a cada
        `SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO`.
        """
        if not CONFERIR_A_JANELA_ANTES_DE_ENVIAR:
            return True

        motivo = self._motivo_para_nao_enviar()
        if motivo is None:
            self._motivo_do_bloqueio = None
            return True

        self._bloqueadas += 1
        # O MOTIVO SAI UMA VEZ POR MOTIVO, não por mensagem. `type_text` manda
        # uma mensagem por caractere: sem isto, uma senha vira 13 linhas iguais
        # de log e o resto da sessão fica ilegível.
        if motivo != self._motivo_do_bloqueio:
            self._motivo_do_bloqueio = motivo
            _logger.error(
                "MENSAGEM BLOQUEADA para hwnd=%s: %s. Nada foi enviado "
                "(%s bloqueadas neste Input).",
                self.hwnd, motivo, self._bloqueadas)
        return False

    def _motivo_para_nao_enviar(self) -> str | None:
        """`None` = pode enviar. Texto = o motivo de não poder."""
        hwnd = self.hwnd
        if not hwnd or hwnd < 0:
            return f"hwnd inválido ({hwnd})"
        if hwnd == HWND_BROADCAST:
            return ("hwnd é HWND_BROADCAST -- isto acertaria TODA janela aberta "
                    "no sistema")
        if not user32.IsWindow(HWND(hwnd)):
            return "a janela não existe mais"

        dono = _dono_da_janela(hwnd)
        if dono is None:
            return "não consegui saber de quem é a janela"

        if self._pid_da_janela is None:
            # PINO TARDIO. O `Input` pode nascer no instante em que a janela
            # ainda não responde quem é o dono -- no login ela está literalmente
            # nascendo. Fixar `None` como pino e comparar contra ele deixaria o
            # bot MUDO para sempre: seria trocar o defeito raro pelo permanente.
            #
            # Então o pino se fecha na primeira leitura que der certo, e a
            # identidade é conferida ANTES de fixar.
            nome = _nome_do_processo(dono)
            if nome is not None and nome != NOME_DO_PROCESSO_DO_JOGO:
                return (f"a janela é do processo {nome!r}, não de "
                        f"{NOME_DO_PROCESSO_DO_JOGO}")
            self._pid_da_janela = dono
            self._nome_do_processo = nome
            self._conferido_em = time.monotonic()
            _logger.info("Input hwnd=%s: pino fechado no pid %s (%s)",
                         hwnd, dono, nome or "processo não identificado")
            return None

        if dono != self._pid_da_janela:
            return (f"a janela trocou de dono: era do pid {self._pid_da_janela}, "
                    f"agora é do pid {dono} (o Windows RECICLOU o handle)")

        # O NOME DO PROCESSO, de tempos em tempos. Fecha o caso raro de o PID
        # também ter sido reciclado -- só o pino do PID não pegaria isso.
        agora = time.monotonic()
        if agora - self._conferido_em >= SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO:
            self._conferido_em = agora
            lido = _nome_do_processo(dono)
            # `None` = não consegui ler: MANTÉM o que já se sabia. Trocar um
            # conhecimento bom por uma falha de leitura é como o bot ficaria
            # mudo por um `AccessDenied` passageiro.
            if lido is not None:
                self._nome_do_processo = lido

        if (self._nome_do_processo is not None
                and self._nome_do_processo != NOME_DO_PROCESSO_DO_JOGO):
            return (f"o pid {dono} é do processo {self._nome_do_processo!r}, "
                    f"não é um {NOME_DO_PROCESSO_DO_JOGO}")
        return None

    def bloqueadas(self) -> int:
        """Quantas mensagens a trava barrou. Para log e diagnóstico."""
        return self._bloqueadas

    # -- teclado -----------------------------------------------------------

    def _enviar_tecla(self, mensagem: int, wparam: int) -> None:
        """Uma mensagem de teclado, pelo caminho que `MODO_DE_TECLA` escolher.

        PONTO ÚNICO por onde toda tecla passa: `key`, `type_text` e
        `clear_field` chegam aqui. Trocar o interruptor troca as três de uma vez,
        e nenhuma delas precisa saber qual mecanismo está em uso -- que é o que
        impede o par de caminhos de divergir em um lugar e não no outro.
        """
        if not self._janela_confiavel():
            return
        if MODO_DE_TECLA == "sendmessage":
            user32.SendMessageW(HWND(self.hwnd), mensagem, WPARAM(wparam),
                                LPARAM(0))
            return
        user32.PostMessageW(HWND(self.hwnd), mensagem, WPARAM(wparam),
                            LPARAM(0))

    def key_down(self, name: str) -> bool:
        """SEGURA a tecla, sem soltar. Quem chama É RESPONSÁVEL pelo `key_up`.

        Existe para o esconder jogadores (`core/esconder_jogadores.py`), que
        precisa da tecla mantida apertada durante um trecho inteiro.

        =================================================================
        CONTAGEM: SEGURAR DENTRO DE SEGURAR NÃO SOLTA NO MEIO
        =================================================================

        O bot segura a MESMA tecla em blocos ANINHADOS -- o processo inteiro da
        entrada na cave por fora, e o par de cliques no NPC por dentro. Sem
        contagem, o `key_up` do bloco interno soltaria a tecla enquanto o externo
        ainda a queria presa, e o defeito seria invisível: a tecla "esteve
        apertada" no log das duas vezes.

        Então cada tecla tem um contador. O `WM_KEYDOWN` sai só na primeira
        chamada e o `WM_KEYUP` só quando o contador volta a zero.

        O contador é POR `Input`, ou seja por janela: cinco contas em paralelo
        têm cinco contadores, e uma não solta a tecla da outra.

        PERIGO QUE CONTINUA: tecla presa que não é solta segue presa, e o bot
        inteiro passa a jogar com ela. Todo uso vai por
        `esconder_jogadores.segurado`, que é context manager.
        """
        vk = VK_CODES.get(str(name).upper())
        if vk is None:
            return False
        chave = str(name).upper()
        atual = self._teclas_presas.get(chave, 0)
        self._teclas_presas[chave] = atual + 1
        if atual == 0:
            self._enviar_tecla(WM_KEYDOWN, vk)
        return True

    def key_up(self, name: str) -> bool:
        """Solta a tecla quando o ÚLTIMO `key_down` aninhado for desfeito.

        Chamar SEM `key_down` correspondente manda um `WM_KEYUP` solto -- e isso
        é de propósito, não descuido. Um KEYUP de tecla que não está apertada é
        ignorado pelo jogo, e serve de REDE: se o contador algum dia sair de
        sincronia, soltar por engano é o lado seguro do erro. O contador nunca
        vai abaixo de zero.
        """
        vk = VK_CODES.get(str(name).upper())
        if vk is None:
            return False
        chave = str(name).upper()
        atual = self._teclas_presas.get(chave, 0)
        if atual <= 1:
            self._teclas_presas.pop(chave, None)
            self._enviar_tecla(WM_KEYUP, vk)
            return True
        self._teclas_presas[chave] = atual - 1
        return True

    def teclas_presas(self) -> dict[str, int]:
        """Cópia do contador. Para log e diagnóstico -- ninguém decide por ela."""
        return dict(self._teclas_presas)

    def key(self, name: str, hold: float = 0.05) -> bool:
        """Pressiona e solta uma tecla. Aceita '1', 'F5', 'NUM3', 'TAB'..."""
        if not self.key_down(name):
            return False
        time.sleep(jitter(hold, 0.3))
        self.key_up(name)
        return True

    def type_text(self, text: str, per_char: float = 0.04) -> None:
        """Digita texto caractere por caractere via WM_CHAR."""
        for ch in text:
            self._enviar_tecla(WM_CHAR, ord(ch))
            time.sleep(jitter(per_char, 0.4))

    def clear_field(self, presses: int = 50) -> None:
        """Limpa um campo de texto com BACKSPACE repetido."""
        for _ in range(presses):
            self.key("BACKSPACE", hold=0.01)

    # -- mouse -------------------------------------------------------------

    def _prime_cursor(self, x: int, y: int) -> None:
        """WM_SETCURSOR + WM_MOUSEMOVE antes do clique.

        Sem isso o cliente ignora parte dos cliques. Descoberto no código do
        T-R0XX; mantido porque funciona. O WM_MOUSEMOVE sai via SendMessageW com
        a coordenada no lParam.
        """
        user32.SendMessageW(
            HWND(self.hwnd), WM_SETCURSOR,
            WPARAM(self.hwnd), LPARAM(HTCLIENT | (WM_MOUSEMOVE << 16)),
        )
        user32.SendMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(0), _lparam(x, y))

    def _click(self, down: int, down_wparam: int, up: int,
               x: int, y: int) -> None:
        """Um clique (down ... up) em (x, y) em coordenadas de client.

        Escolhe o caminho pelo interruptor `MODO_DE_CLIQUE`, no topo do arquivo.
        O caminho `"sendmessage"` é o de sempre e continua sendo o padrão.

        FUNIL DO CLIQUE: os oito caminhos passam por aqui, então a trava da
        janela cobre todos de uma vez -- é o mesmo motivo pelo qual
        `_enviar_tecla` existe para as teclas.
        """
        if not self._janela_confiavel():
            return
        if MODO_DE_CLIQUE == "sendmessage_repetido":
            self._click_sendmessage_repetido(down, down_wparam, up, x, y)
            return
        if MODO_DE_CLIQUE == "postmessage_hibrido":
            self._click_postmessage_hibrido(down, down_wparam, up, x, y)
            return
        if MODO_DE_CLIQUE == "postmessage_com_delay":
            self._click_postmessage_com_delay(down, down_wparam, up, x, y)
            return
        if MODO_DE_CLIQUE == "sendmessage_rapido":
            self._click_sendmessage_rapido(down, down_wparam, up, x, y)
            return
        if MODO_DE_CLIQUE == "sendmessage_rapido_reafirmado":
            self._click_rapido_reafirmado(down, down_wparam, up, x, y)
            return
        if MODO_DE_CLIQUE == "postmessage_puro":
            self._click_postmessage_puro(down, down_wparam, up, x, y)
            return
        if MODO_DE_CLIQUE == "trox_sequence":
            self._click_trox_sequence(down, down_wparam, up, x, y)
            return
        self._click_sendmessage(down, down_wparam, up, x, y)

    def _click_sendmessage(self, down: int, down_wparam: int, up: int,
                           x: int, y: int) -> None:
        """O CAMINHO DE SEMPRE. Tudo via SendMessageW síncrono, coordenada no
        lParam. O cursor físico nunca é tocado.

        NÃO MEXER sem interruptor: é o único caminho com histórico de funcionar
        em produção. PostMessage e o hook em `GetCursorPos` já foram tentados e
        voltaram atrás -- ver a NOTA HISTÓRICA no `CLAUDE.md`.
        """
        self._prime_cursor(x, y)
        user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam), _lparam(x, y))
        time.sleep(jitter(0.015, 0.4))
        user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def _click_sendmessage_repetido(self, down: int, down_wparam: int, up: int,
                                    x: int, y: int) -> None:
        """EXPERIMENTO: reafirma a posição do mouse ANTES e DEPOIS do down.

        A hipótese vem de uma observação do usuário: com o cursor FÍSICO sobre a
        janela, o clique acontece ONDE O CURSOR ESTÁ, não na coordenada enviada.
        Isso quer dizer que o cliente lê a posição de outro lugar que não o
        `lParam` do botão -- provavelmente a posição que ele mesmo guardou do
        último `WM_MOUSEMOVE`, que o mouse real acabou de sobrescrever.

        Se for isso, reafirmar o `WM_MOUSEMOVE` colado ao `down` reduz a janela
        em que o mouse real pode se meter no meio. NÃO resolve o caso do jogo ler
        `GetCursorPos` direto -- para esse só o detour resolveria, e ele está
        descartado.

        É experimento: não está ligado, e ligar é trocar uma palavra.
        """
        self._prime_cursor(x, y)
        user32.SendMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(down_wparam),
                            _lparam(x, y))
        user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam), _lparam(x, y))
        time.sleep(jitter(0.015, 0.4))
        user32.SendMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(down_wparam),
                            _lparam(x, y))
        user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def _click_postmessage_hibrido(self, down: int, down_wparam: int, up: int,
                                   x: int, y: int) -> None:
        """EXPERIMENTO (2026-08-14): PostMessage para WM_MOUSEMOVE, SendMessage
        para botões.

        PROBLEMA IDENTIFICADO: SendMessageW é BLOQUEANTE -- bloqueia a thread do
        bot até o WndProc do jogo responder. Com milhares de cliques/segundo (BC
        farm intenso), o message loop do Windows fica CONGESTIONADO, causando:
          - Stuttering do cursor físico do usuário
          - "Teleportes" de poucos pixels (eventos de mouse perdidos)
          - Pior em outras janelas (não sobre o jogo)

        SOLUÇÃO: PostMessageW é ASSÍNCRONO -- enfileira a mensagem e retorna
        imediatamente, liberando o message loop do Windows para processar o cursor
        físico do usuário sem atraso.

        HÍBRIDO: Apenas WM_SETCURSOR e WM_MOUSEMOVE usam PostMessage (não precisam
        de confirmação imediata). Os BOTÕES (down/up) continuam com SendMessage
        para garantir processamento síncrono e ordem correta.

        RISCO: PostMessage pode ter mensagens reordenadas ou perdidas se a fila do
        jogo encher. Os botões síncronos minimizam isso -- se o down chegar, o
        jogo já processou os WM_MOUSEMOVE anteriores.

        TESTE: Rodar 1 conta BC por 10-15 min enquanto mexe o cursor físico em
        outras janelas. Stuttering deve desaparecer sem perder funcionalidade do
        bot.
        """
        # WM_SETCURSOR e primeiro WM_MOUSEMOVE: assíncronos
        user32.PostMessageW(
            HWND(self.hwnd), WM_SETCURSOR,
            WPARAM(self.hwnd), LPARAM(HTCLIENT | (WM_MOUSEMOVE << 16)),
        )
        user32.PostMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(0), _lparam(x, y))

        # Botões: síncronos (garantem processamento e ordem)
        user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam), _lparam(x, y))
        time.sleep(jitter(0.015, 0.4))
        user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def _click_postmessage_com_delay(self, down: int, down_wparam: int, up: int,
                                     x: int, y: int) -> None:
        """TESTE 1 (2026-08-14 FALHOU): PostMessage + Delay de 5ms antes dos botões.

        RESULTADO: "Às vezes funciona, mas ainda é ruim" — 5ms não foi suficiente
        para garantir que o WM_MOUSEMOVE fosse processado antes do botão.

        CONCLUSÃO: PostMessage é instável com este jogo. Descartado.
        """
        # WM_SETCURSOR e WM_MOUSEMOVE: assíncronos (não bloqueiam)
        user32.PostMessageW(
            HWND(self.hwnd), WM_SETCURSOR,
            WPARAM(self.hwnd), LPARAM(HTCLIENT | (WM_MOUSEMOVE << 16)),
        )
        user32.PostMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(0), _lparam(x, y))

        # DELAY: aguarda o jogo processar o WM_MOUSEMOVE antes do botão
        time.sleep(0.015)  # 5ms (insuficiente)

        # Botões: síncronos (garantem processamento)
        user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam), _lparam(x, y))
        time.sleep(jitter(0.015, 0.4))
        user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def _click_trox_sequence(self, down: int, down_wparam: int, up: int,
                            x: int, y: int) -> None:
        """TESTE 5 (2026-08-15): Sequência EXATA do bot T-R0XX.

        DESCOBERTA: Outro bot de Talisman (T-R0XX) usa SendMessageW com lParam,
        igual ao BlazesBot, mas com sequência diferente:

        T-R0XX:
          1. WM_SETCURSOR com lParam=HTCLIENT|(WM_MOUSEMOVE<<16)
          2. WM_MOUSEMOVE com lParam=(x,y)
          3. WM_LBUTTONDOWN com wParam=MK_LBUTTON
          4. WM_LBUTTONUP com wParam=0

        BlazesBot (antes):
          1. WM_SETCURSOR (em _prime_cursor)
          2. WM_MOUSEMOVE (em _prime_cursor)
          3. WM_LBUTTONDOWN
          4. sleep(1ms)
          5. WM_LBUTTONUP

        HIPÓTESE: O WM_SETCURSOR com lParam específico (0x02000001) pode estar
        "sincronizando" a posição interna do jogo ANTES do clique processar.
        Isso explicaria por que o T-R0XX não precisa de DLL ou MouseShield.

        TESTE: Implementar a sequência exata do T-R0XX (sem sleep entre down/up,
        sem DLL, sem shield) e verificar se resolve o problema do cursor físico.
        """
        # Sequência EXATA do T-R0XX: SetCursor → Move → Down → Up
        user32.SendMessageW(
            HWND(self.hwnd), WM_SETCURSOR,
            WPARAM(self.hwnd), LPARAM(HTCLIENT | (WM_MOUSEMOVE << 16)),
        )
        user32.SendMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(0), _lparam(x, y))
        user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam), _lparam(x, y))
        user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def _click_sendmessage_rapido(self, down: int, down_wparam: int, up: int,
                                  x: int, y: int) -> None:
        """TESTE 2 (2026-08-14): SendMessage com sleep reduzido de 15ms → 1ms.

        ESTRATÉGIA CONSERVADORA: Mantém SendMessage (síncrono, funciona sempre)
        mas reduz drasticamente o tempo de bloqueio.

        MUDANÇA: time.sleep(jitter(0.015, 0.4)) → time.sleep(0.001)
          - ANTES: 15ms ±40% = 10-21ms de bloqueio entre down/up
          - AGORA: 1ms fixo (sem jitter — queremos velocidade máxima)

        BENEFÍCIO ESPERADO:
          - Cliques funcionam 100% (SendMessage garante)
          - Bloqueio reduz 93% (1ms vs 15ms)
          - Menos bloqueio = menos stuttering

        RISCO: 1ms pode ser insuficiente para o jogo registrar o clique.
        Se falhar: aumentamos para 5ms ou 10ms (ainda 66-83% mais rápido).

        MOUSE SHIELD: bloqueio de 80 ms, e é o valor do USUÁRIO, ajustado por
        ele na mão depois de testar. 15 ms tinha sido calculado ("o clique dura
        ~5 ms, 3x de margem basta") e na prática era curto demais: o movimento
        físico passava por baixo e o clique se perdia. O número calculado
        perdeu para o número medido -- e o texto que dizia 15 ms ficou meses
        descrevendo um comportamento que o código já não tinha.

        O preço é assumido e foi conferido pelo usuário: durante esses 80 ms o
        mouse dele para de responder DENTRO da janela do jogo. Fora dela, nada
        muda. Ver `mouse_shield.py` para o custo por evento.

        """
        # Mouse shield (hook externo, menos invasivo)
        if self._shield:
            # O `finally` é o que encurta o incômodo: os 80 ms viram TETO, não
            # gasto. O intervalo que precisa de proteção é do prime ao up
            # (~5 ms); o teto existe só para o caso de a thread ser preemptada
            # no meio dele. Sem o `liberar()`, o mouse do usuário ficava preso
            # os 80 ms inteiros TODA vez, inclusive quando nada atrasou.
            self._shield.block_momentarily(duration_ms=TETO_DO_BLOQUEIO_MS)
            try:
                self._prime_cursor(x, y)
                user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam),
                                    _lparam(x, y))
                time.sleep(0.002)
                user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0),
                                    _lparam(x, y))
            finally:
                self._shield.liberar()

        # Fallback: sem proteção (modo original)
        else:
            self._prime_cursor(x, y)
            user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam), _lparam(x, y))
            time.sleep(0.002)
            user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def _click_rapido_reafirmado(self, down: int, down_wparam: int, up: int,
                                 x: int, y: int) -> None:
        """O rápido, mais a coordenada REAFIRMADA entre o down e o up.

        =====================================================================
        POR QUE ESTE MODO EXISTE (medido em 18/08/2026, `teste_do_cursor.py`)
        =====================================================================

        O diagnóstico antigo dizia que o jogo lê a posição por `GetCursorPos`.
        **Medido, é falso.** Com o cursor físico PARADO a 756 px do alvo, 20 de
        20 cliques acertaram o alvo. O jogo HONRA a coordenada do `lParam` --
        e foi por hookear `GetCursorPos` que a DLL do TESTE 4 falhou: ela
        hookeava a função errada.

        O que a mesma medição mostrou com o cursor EM MOVIMENTO sobre a janela:
        18 de 20 sem o shield, 20 de 20 com ele. Ou seja, o problema não é a
        posição do clique -- é o `WM_MOUSEMOVE` FÍSICO que cai ENTRE o nosso
        down e o nosso up. O jogo fecha o clique no UP, e um movimento no meio
        faz o par virar arrasto em vez de clique: o botão é solto num lugar
        diferente de onde foi pressionado, e a ação não dispara.

        Se é isso, reafirmar a coordenada colada ao `up` desfaz o estrago sem
        hook nenhum -- o up volta a cair onde o down caiu. É a diferença entre
        proibir o mouse do usuário de existir e simplesmente não se importar
        com ele.

        Difere do `sendmessage_repetido` em UMA coisa que a medição diz ser a
        que importa: a espera entre down e up. Lá é `jitter(0.015, 0.4)`, de 9
        a 21 ms -- janela larga para o jogo bombear um movimento físico da fila.
        Aqui são os mesmos 2 ms do modo rápido.

        =====================================================================
        MEDIDO E REPROVADO NO MESMO DIA -- NÃO LIGAR
        =====================================================================

        A hipótese acima está ERRADA, e o número é claro: **12/20 (60%)** contra
        **19/20 (95%)** de não fazer nada, com o mouse em movimento.

        O motivo é o `wParam` deste `WM_MOUSEMOVE` extra: ele vai com
        `MK_LBUTTON`, que significa "o mouse moveu COM O BOTÃO APERTADO" -- a
        definição de arrasto. Em vez de impedir o arrasto, reafirmar FABRICA um
        em todo clique. Na medição o jogo travou nesse estado por seis cliques
        seguidos, com diferença de imagem 0,00 (nada aconteceu na tela).

        Fica no código pelo mesmo motivo que os outros caminhos reprovados
        ficam: para a próxima pessoa que tiver esta ideia -- ela é natural --
        encontrar a medição junto, em vez de gastar a mesma tarde.

        O que resolve é o `MouseShield`, medido 20/20 na mesma corrida.
        """
        self._prime_cursor(x, y)
        user32.SendMessageW(HWND(self.hwnd), down, WPARAM(down_wparam),
                            _lparam(x, y))
        time.sleep(0.002)
        # A REAFIRMAÇÃO. Sem ela, um movimento físico no meio dos 2 ms faz o up
        # ser entregue com a posição do mouse do usuário.
        user32.SendMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(down_wparam),
                            _lparam(x, y))
        user32.SendMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def _click_postmessage_puro(self, down: int, down_wparam: int, up: int,
                                x: int, y: int) -> None:
        """AS QUATRO mensagens por `PostMessageW`. Nenhuma síncrona.

        =====================================================================
        POR QUE ISTO NÃO É "TENTAR POSTMESSAGE DE NOVO"
        =====================================================================

        O `inputs.py` registra dois experimentos de PostMessage como REPROVADOS
        (`postmessage_hibrido` e `postmessage_com_delay`, 14/08/2026), com a
        conclusão *"PostMessage é instável com este jogo. Descartado."*

        **Os dois mandavam os BOTÕES por `SendMessageW`.** E isso não é um
        detalhe de implementação: é a garantia da falha.

            PostMessageW(WM_MOUSEMOVE)  -> vai para a FILA, processado quando o
                                           jogo bombeia mensagens
            SendMessageW(down)          -> FURA A FILA, chama o WndProc na hora

        O botão chegava ANTES do move. O sintoma registrado -- *"o clique
        acontece na posição antiga"* -- é exatamente essa inversão, e o
        `postmessage_hibrido` a produzia enquanto o próprio docstring dele dizia
        que os botões síncronos "garantem ordem correta".

        Ou seja: **PostMessage puro nunca foi testado.** O que foi testado, e
        reprovou, foi misturar os dois mecanismos -- que é a única combinação
        que não pode funcionar.

        =====================================================================
        POR QUE AGORA PODE DAR CERTO
        =====================================================================

        Mensagens POSTADAS na mesma fila saem em FIFO. Com as quatro postadas e
        nenhuma furando a fila, a ordem que o jogo vê é a que se mandou.

        E o que sobra de risco -- uma mensagem do mouse FÍSICO entrando no meio
        -- é justamente o que o Mouse Shield remove. Em agosto o shield não
        estava nem medido nem correto; hoje está (20/20 com o mouse em
        movimento, contra 1/20 sem ele).

        =====================================================================
        O PRÊMIO, QUE É MAIOR QUE O STUTTERING
        =====================================================================

        `PostMessageW` NÃO BLOQUEIA. Isso elimina um defeito que está aberto e
        documentado: `SendMessageW` não tem timeout, então um cliente que para de
        bombear mensagens -- o cenário do "Connection interrupted" -- prende a
        thread daquela conta PARA SEMPRE. O `finally` do shield não roda, o
        `watchdog.check()` que dispararia o relogin nunca é alcançado, e a conta
        morre em silêncio dizendo "Rodando".

        O preço aceito (decisão do usuário): perde-se a confirmação implícita do
        clique -- `SendMessageW` só retorna depois de o WndProc rodar. O projeto
        já não confia nela: a regra é conferir o efeito por imagem e repetir.

        =====================================================================
        O SHIELD AQUI NÃO É SOLTO NO FIM -- E ISSO É DO MECANISMO
        =====================================================================

        No caminho síncrono, `_click_sendmessage_rapido` chama `liberar()` no
        `finally`, e pode: `SendMessageW` só retorna DEPOIS de o WndProc rodar,
        então o retorno é PROVA de que a mensagem foi processada e o bloqueio já
        não serve para nada.

        Aqui não existe essa prova. `PostMessageW` devolve na hora e as quatro
        mensagens ficam na FILA até o jogo bombear. Soltar o bloqueio logo depois
        de postar liberaria o mouse físico **antes** de o jogo processar o que
        acabamos de enfileirar -- e um `WM_MOUSEMOVE` físico que entre nessa
        janela é processado ANTES do nosso botão, que é exatamente a falha que se
        quer impedir.

        Então aqui o bloqueio EXPIRA sozinho, por `TETO_DO_BLOQUEIO_MS`. Ele
        deixa de ser teto e volta a ser gasto -- é o preço de não ter
        confirmação, e o usuário paga em milissegundos de mouse preso dentro da
        janela do jogo.

        POR QUE ISTO EXISTE (18/08/2026): a medição do `teste_do_cursor` deu
        40/40 para PostMessage, mas ela rodou com o shield NUNCA ENGAJADO -- este
        método não o chamava, então as duas fases ("com" e "sem" shield) eram o
        mesmo teste. Em produção o usuário observou o que o teste não podia
        mostrar: *"ainda tem vezes que acaba não clicando todas as vezes se eu
        mexo o mouse na janela do jogo"*. Observação de produção supera medição
        de laboratório com escopo menor.

        EXPERIMENTO. Ligar é trocar `MODO_DE_CLIQUE`.
        """
        # Bloqueia ANTES de postar, e NÃO solta: ver o docstring.
        if self._shield:
            self._shield.block_momentarily(duration_ms=TETO_DO_BLOQUEIO_MS)
        user32.PostMessageW(
            HWND(self.hwnd), WM_SETCURSOR,
            WPARAM(self.hwnd), LPARAM(HTCLIENT | (WM_MOUSEMOVE << 16)),
        )
        user32.PostMessageW(HWND(self.hwnd), WM_MOUSEMOVE, WPARAM(0),
                            _lparam(x, y))
        user32.PostMessageW(HWND(self.hwnd), down, WPARAM(down_wparam),
                            _lparam(x, y))
        # A PAUSA FICA (decisão do usuário). Postadas as quatro de uma vez, o
        # jogo poderia processá-las na MESMA passada do laço dele -- um clique de
        # duração zero, que algumas UIs recusam. 2 ms custam quase nada e cobrem
        # esse modo de falha; sem eles, uma falha de duração seria creditada ao
        # PostMessage.
        time.sleep(0.002)
        user32.PostMessageW(HWND(self.hwnd), up, WPARAM(0), _lparam(x, y))

    def left_click(self, x: int, y: int) -> None:
        self._click(WM_LBUTTONDOWN, MK_LBUTTON, WM_LBUTTONUP, int(x), int(y))

    def right_click(self, x: int, y: int, repetir: bool = True) -> None:
        """Clique direito, REPETIDO `CLIQUES_DIREITOS_POR_TENTATIVA` vezes.

        `repetir=False` manda UM só, e existe para o MOVIMENTO PELO MINIMAPA.
        Ali a repetição não é insistência, é imprecisão: cada clique no
        minimapa é uma ORDEM DE ANDAR, e entre um e outro o personagem já saiu
        do lugar -- então o 2º, 3º e 4º são calculados a partir de uma posição
        que não é mais a atual, e o destino sai deslocado. Medido pelo usuário
        como "perda de precisão de andar pelo mapa".
        `repetir=True` (o padrão) é para clique que ABRE alguma coisa: NPC,
        Altar Stone, saída da cave. Ali repetir só melhora a chance de o
        cliente registrar, porque o efeito não se acumula -- o diálogo abre uma
        vez.

        ===================================================================
        POR QUE REPETIR
        ===================================================================

        Medido no log de dev de 13/08/2026, na disputa pela entrada da cave:
        o MESMO clique, na MESMA coordenada, abre o diálogo **78% das vezes**
        fora do instante ruim -- ou seja, um em cada cinco se perde sem que
        nada esteja errado com a coordenada. Repetir rápido é a aposta de que
        parte desses 22% é o cliente engolindo a mensagem, e não o clique
        errando o alvo.

        É EXPERIMENTO, no mesmo molde do `MODO_DE_CLIQUE`: voltar ao
        comportamento de sempre é pôr `1` na constante, e nada mais.

        ===================================================================
        O QUE ISSO CUSTA, E ONDE PODE DOER
        ===================================================================

        Custo: ~3x o tempo de um clique (cada um é `SendMessageW` SÍNCRONO,
        então são quatro idas e voltas até o cliente). Na ordem de 150 ms por
        clique direito -- perto dos 368 ms de mediana da abertura do diálogo,
        cabe.

        O RISCO É CLIQUE QUE ALTERNA ESTADO. Um menu que ABRE no primeiro
        clique e FECHA no segundo termina FECHADO com um número par de
        cliques. O caso a vigiar é `team.py`, que clica no próprio retrato para
        abrir o menu de sair do time -- e é esse menu que reseta o boss. Se ele
        parar de funcionar, é aqui que se olha primeiro.
        """
        vezes = max(1, CLIQUES_DIREITOS_POR_TENTATIVA) if repetir else 1
        for i in range(vezes):
            if i:
                time.sleep(INTERVALO_ENTRE_CLIQUES_DIREITOS)
            self._click(WM_RBUTTONDOWN, MK_RBUTTON, WM_RBUTTONUP, int(x), int(y))

    # -- janela ------------------------------------------------------------

    def window_exists(self) -> bool:
        return bool(user32.IsWindow(HWND(self.hwnd)))

    def client_size(self) -> tuple[int, int]:
        """Tamanho da área de cliente da janela, em pixels.

        Usa `win32gui.GetClientRect`, que é a mesma chamada do diagnóstico de
        captura -- ali ela reportou 1280x960 corretamente. A versão anterior
        chamava `user32.GetClientRect` via ctypes sem declarar `argtypes`, e o
        valor podia sair errado sem levantar exceção. Como TODAS as coordenadas
        derivam deste número, um erro aqui contamina o bot inteiro em silêncio.
        """
        try:
            import win32gui

            left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
            largura, altura = right - left, bottom - top
            if largura > 0 and altura > 0:
                return largura, altura
        except Exception:
            pass

        # Reserva: ctypes, com os tipos declarados.
        rect = RECT()
        user32.GetClientRect.argtypes = [HWND, ctypes.POINTER(RECT)]
        user32.GetClientRect(HWND(self.hwnd), ctypes.byref(rect))
        return rect.right - rect.left, rect.bottom - rect.top

    def set_title(self, title: str) -> None:
        """Renomeia a janela. TAMBÉM CONFERE -- renomear a janela de outro
        programa é o mesmo defeito com outra roupa."""
        if not self._janela_confiavel():
            return
        user32.SetWindowTextW(HWND(self.hwnd), title)
