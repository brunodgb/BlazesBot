"""Janelas do Windows por PID -- o que é comum a quem precisa NOMEAR um cliente.

=========================================================================
PECA PROMOVIDA -- DEPENDENCIA CRUZADA
=========================================================================

**De onde veio:** era uma função aninhada dentro de `run_check()`, no
`main.py` (o `2-DIAGNOSTICO`). Nasceu específica, como quase tudo, e virou
geral no dia em que uma segunda ferramenta precisou da mesma coisa.

**Quem usa hoje:** `main.py` (`run_check`) e
`blazesbot/tools/vigiar_combate.py` (o `9-VIGIAR-COMBATE`). Mexer aqui mexe
nos dois.

**Por que subiu para o `core/`:** o critério do projeto é uma pergunta só --
*isso é sobre o JOGO/o sistema ou sobre o que este ecossistema faz?*. "Qual é o
título da janela deste PID" não é sobre farm nem sobre macro: é sobre o
Windows. Copiar a função para a ferramenta nova seria duas cópias da mesma
varredura, e duas chances de só uma ser corrigida.

**Por que não em `bot/`:** `core/` nunca importa de `bot/`, e o caminho
contrário seria possível -- mas isto aqui não sabe o que é conta, ecossistema
ou supervisor. Nada em `bot/` precisaria ser conhecido para escrever esta
função, e é esse o teste de onde ela mora.

NÃO CONFUNDIR COM `watchdog.client_pids()`, que responde *quais* PIDs existem.
Aquilo continua em `bot/watchdog.py`, porque a definição de "cliente do jogo"
anda junto com a de queda. Aqui a pergunta é outra: *como se chama a janela
deste PID*.
"""
from __future__ import annotations

# O TÍTULO DE QUEM NÃO TEM JANELA. Texto, e não `None`, porque todo chamador
# deste módulo põe o resultado numa linha para uma pessoa ler -- e `None` numa
# lista vira `"None"`, que é pior que dizer o que aconteceu.
SEM_JANELA = "(sem janela)"


def janelas_do_pid(pid: int) -> list[tuple[int, str]]:
    """Todas as janelas VISÍVEIS daquele processo: `(hwnd, título)`.

    É A PRIMITIVA -- as outras duas funções deste módulo são conveniências em
    cima dela. Antes de existir, esta mesma varredura estava escrita **três
    vezes** dentro do `main.py`, cada uma com um recorte diferente do resultado
    (uma queria o título, outra o handle, a terceira as duas coisas de todas as
    janelas). Três cópias da mesma varredura são três chances de só uma ser
    corrigida.

    NUNCA LEVANTA: a janela pode estar sendo criada ou destruída neste exato
    instante, e uma ferramenta de diagnóstico que explode ao montar o cabeçalho
    é pior que uma que devolve lista vazia.
    """
    import win32gui
    import win32process

    achadas: list[tuple[int, str]] = []

    def _visitar(handle: int, _extra: object) -> bool:
        if not win32gui.IsWindowVisible(handle):
            return True
        try:
            _, dono = win32process.GetWindowThreadProcessId(handle)
        except Exception:
            return True
        if dono == pid:
            achadas.append((handle, (win32gui.GetWindowText(handle) or "").strip()))
        return True

    try:
        win32gui.EnumWindows(_visitar, None)
    except Exception:
        return []
    return achadas


def janela_do_pid(pid: int) -> tuple[int, str]:
    """A primeira janela visível daquele PID. `(0, "")` se não houver.

    A PRIMEIRA, e não todas: o cliente do jogo abre janelas auxiliares, e quem
    chama isto quer *a* janela para mandar mensagem ou medir tamanho.
    """
    achadas = janelas_do_pid(pid)
    return achadas[0] if achadas else (0, "")


def titulo_do_pid(pid: int) -> str:
    """O título da primeira janela VISÍVEL daquele processo.

    Serve para NOMEAR um cliente numa lista que uma pessoa vai ler: todos os
    processos se chamam `client.exe`, então o PID sozinho não diz qual é qual.

    NUNCA LEVANTA. Uma ferramenta de diagnóstico que explode ao montar o
    cabeçalho é pior que uma que diz `(sem janela)` -- e a janela pode estar
    sendo criada, destruída ou pertencer a outra sessão neste exato instante.

    A PRIMEIRA VISÍVEL, e não todas: o cliente do jogo abre janelas auxiliares
    invisíveis, e listar as três não ajuda quem só quer escolher um número.
    """
    _, titulo = janela_do_pid(pid)
    return titulo or SEM_JANELA


# ===========================================================================
# A SONDA DE TRAVAMENTO -- "Não Está Respondendo", medido em vez de suposto
# ===========================================================================
#
# Quanto tempo esperar a janela responder a uma mensagem VAZIA. Não é o tempo
# que o jogo leva para fazer alguma coisa: `WM_NULL` não faz nada, então o único
# custo é a viagem até o laço de mensagens do cliente e a volta. Uma janela viva
# responde em microssegundos, mesmo carregando mapa -- o carregamento acontece
# DEPOIS da mensagem sair da fila.
#
# 1,5 s é folga de milhares de vezes sobre o normal, e ainda assim mantém o
# ciclo do vigia curto: com 5 contas e todas travadas, o pior caso de uma volta
# é 7,5 s, que cabe no orçamento de detecção.
TIMEOUT_DA_SONDA_MS = 1500

# `SendMessageTimeout`: desiste na hora se o Windows JÁ classificou a janela
# como travada, em vez de esperar o timeout inteiro.
_SMTO_ABORTIFHUNG = 0x0002
_WM_NULL = 0x0000


def janela_responde(hwnd: int, timeout_ms: int = TIMEOUT_DA_SONDA_MS) -> bool:
    """A janela ainda BOMBEIA MENSAGENS? É o "Não Está Respondendo" do Windows.

    =====================================================================
    POR QUE ESTA PERGUNTA EXISTE
    =====================================================================

    A definição de queda de `bot/watchdog.avaliar_saude` cobre três sinais:
    processo morto, janela sumida e o aviso de conexão na tela. Nenhum deles
    responde pelo cliente que **trava**: o processo continua vivo, a janela
    continua existindo, e não há caixa nenhuma para fotografar -- a captura
    devolve o último quadro pintado, congelado, e o template não casa.

    Pior: o bot fala com o jogo por `SendMessageW` SÍNCRONO (a regra permanente
    "nenhuma mensagem sai para uma janela que não é o jogo" exige a conferência
    e o envio síncrono). Mandar `SendMessageW` para uma janela travada **bloqueia
    a thread que enviou, sem timeout, para sempre**. É exatamente por aí que a
    conta ficava presa: não é que o vigia não visse a queda, é que a thread que
    faria a conferência estava parada dentro da mesma chamada.

    Esta função é o `SendMessageW` com CRONÔMETRO. Zero custo quando a janela
    está viva, resposta garantida quando não está -- e é a única pergunta desta
    escada que pode ser feita com segurança de OUTRA thread, porque ela não
    depende de nenhum recurso compartilhado com a thread do bot.

    NUNCA LEVANTA e nunca bloqueia além de `timeout_ms`.

    Devolve `True` também quando não dá para perguntar (hwnd inválido, ctypes
    indisponível): quem decide se a janela ainda existe é `IsWindow`, e "não sei"
    NÃO pode virar motivo para matar o cliente de alguém.
    """
    if not hwnd:
        return True
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        resposta = ctypes.c_size_t()
        retorno = user32.SendMessageTimeoutW(
            wintypes.HWND(int(hwnd)),
            _WM_NULL,
            wintypes.WPARAM(0),
            wintypes.LPARAM(0),
            _SMTO_ABORTIFHUNG,
            ctypes.c_uint(int(timeout_ms)),
            ctypes.byref(resposta),
        )
    except Exception:
        return True
    return bool(retorno)
