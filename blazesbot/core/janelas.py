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
