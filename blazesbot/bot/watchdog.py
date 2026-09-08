"""
Watchdog: detecção de queda de conexão.

REGRA CENTRAL, e ela é deliberada: um personagem parado NÃO é um personagem
desconectado.

A versão anterior concluía "congelado" quando posição e HP ficavam iguais por
um tempo. Isso está errado neste jogo: é normal e desejável deixar um
personagem parado por horas com a loja pessoal aberta, sem mexer, sem tomar
dano, sem andar. O sinal de congelamento derrubava essas contas em loop.

Então os únicos motivos para religar são sinais INEQUÍVOCOS de que a sessão
morreu:

  1. O processo do cliente não existe mais.
  2. A janela do cliente não existe mais.
  3. O aviso "Connection interrupted..." está na tela.

Não há mais detecção por inatividade, e o flag de modal na memória não derruba
mais a conta por si só -- ele é compartilhado com caixas de confirmação
legítimas e gerava falso positivo.
"""
from __future__ import annotations

import subprocess
import time
from enum import Enum

import psutil

from ..core.coords import coords_for_size
from ..core.vision import capture_window, find_template
from .context import BotContext, GameState

# Template do aviso "Connection interrupted[, please open client again]".
# O prefixo casa nas duas variantes do texto.
RECONNECT_TEMPLATE = "state_conn_prefix.png"

# ===========================================================================
# POR QUE A BUSCA É PRESA À CAIXA, E NÃO NA TELA INTEIRA
# ===========================================================================
#
# O template é SÓ A FRASE, sem moldura -- foi recortado assim de propósito, para
# casar com as duas variantes do texto. O preço disso é que ele casa com a frase
# ONDE QUER QUE ELA APAREÇA, e ela aparece no CHAT: basta outro jogador digitar
# "connection interrupted" no canal mundial.
#
# NÃO É HIPÓTESE. Medido nos prints de `logs/quedas/`, que são o quadro que
# disparou a queda:
#
#     29/08 03:04  5 contas derrubadas   nota 0.799-0.844  em (248, 519..587)
#     01/09 02:25  5 contas derrubadas   nota 0.808-0.814  em (241, 570)
#
# Nos dois casos o personagem está VIVO na imagem, com alvo selecionado, e a
# linha de chat visível é `[world] [zmypx]: maintenance more connection
# interrupted?`. Dez relogins por causa da conversa dos outros.
#
# As quedas REAIS, nos mesmos arquivos, casam em (441, 198) com nota 0.980-0.983.
# Duas populações, nenhuma sobreposição.
#
# São DUAS defesas, e cada uma sozinha já separaria -- é de propósito, porque a
# frase no chat é um evento que o bot não controla:
#
#   REGIÃO  a caixa é centralizada e opaca; o chat fica no canto de baixo. Com o
#           raio abaixo, a melhor nota dos falsos cai de 0.844 para 0.421.
#   LIMIAR  0.92 é o meio entre 0.844 (pior falso) e 0.980 (pior queda real).
#
# Margem final medida: +0.559 (0.421 -> 0.980).
RECONNECT_THRESHOLD = 0.92

# Meio-lado da janela de busca, em volta de `coords.aviso_de_conexao`. A caixa
# variou 4 px nos 12 prints reais; 120 px é folga de trinta vezes isso e ainda
# deixa o chat (372 px abaixo) inteiramente de fora.
RAIO_DA_BUSCA_DO_AVISO = 120
# Este virou o sinal principal de queda, então roda numa cadência curta.
# Ainda assim é bem mais barato que verificar a cada tick.
VISUAL_CHECK_SECONDS = 10.0


class DcReason(str, Enum):
    NONE = "none"
    PROCESS_GONE = "processo do cliente encerrado"
    WINDOW_GONE = "janela do cliente desapareceu"
    RECONNECT_DIALOG = "aviso de conexão interrompida na tela"
    # O QUARTO SINAL, e ele NÃO nasce em `avaliar_saude` -- ver o comentário
    # "QUEDA INSTANTÂNEA x QUEDA POR CONFIRMAÇÃO" logo abaixo.
    WINDOW_HUNG = "janela do cliente travada (parou de responder)"


# ===========================================================================
# QUEDA INSTANTÂNEA x QUEDA POR CONFIRMAÇÃO -- por que são DUAS portas
# ===========================================================================
#
# `avaliar_saude` responde os três sinais que dispensam segunda opinião: o
# processo não existe, a janela não existe, o aviso está na tela com nota acima
# de 0.92 na caixa. Nenhum deles tem falso positivo possível -- por isso ela é
# SEM ESTADO, e por isso qualquer um pode chamá-la de qualquer lugar.
#
# O TRAVAMENTO é de outra natureza. "A janela não respondeu AGORA" é ruído: um
# pico de disco, uma troca de mapa, o Windows suspendendo a janela minimizada.
# Só vira queda quando se repete -- e "se repete" exige MEMÓRIA ENTRE CICLOS,
# que é precisamente o que `avaliar_saude` não tem e não pode ter.
#
# Então o travamento mora em quem tem ciclo: `bot/sentinela.py`. Isso NÃO é uma
# segunda definição de queda concorrendo com esta -- o vigia chama `avaliar_saude`
# para os três sinais e só ACRESCENTA o quarto, com a sonda de `core/janelas.py`
# e o contador de reincidência. Continua existindo uma definição por sinal.


def avaliar_saude(
    pid: int,
    hwnd: int,
    janela_existe: bool,
    templates,
):
    """A definição de QUEDA, num lugar só. Devolve `(motivo, quadro)`.

    =====================================================================
    POR QUE ISTO É FUNÇÃO SOLTA E NÃO MÉTODO DO `Watchdog`
    =====================================================================

    O ecossistema de LOGIN/RELOGIN é a BASE de todos os outros: não importa qual
    ecossistema esteja rodando, o jogo precisa estar logado e funcionando. Disso
    decorre uma obrigação para TODO ecossistema, presente e futuro -- perceber a
    queda ENQUANTO roda, e ter o mesmo desfecho: fecha a janela, relogin, e a
    conta volta para o modo em que estava.

    O `Watchdog` cumpre isso para o BC, mas ele recebe um `BotContext` -- e o
    `BotContext` carrega o estado do FARM. O modo APP não o recebe de propósito
    (ver `AccountSupervisor._rodar_modo_app`), e é isso que faz o APP funcionar
    justamente quando a memória não responde.

    Resultado, medido em 18/08/2026: o APP não tinha detecção nenhuma além de
    "a janela sumiu", e com 5 contas caindo juntas as 4 de BC relogaram e a do
    APP ficou apertando teclas contra a caixa de "Connection interrupted".

    Duplicar a regra nos dois lugares seria pior que o defeito: duas definições
    de queda divergem na primeira manutenção. Então a regra mora AQUI, recebendo
    peças (pid, hwnd, se a janela existe, biblioteca de templates) em vez de um
    contexto -- e quem tem contexto (`Watchdog`) e quem não tem (o modo APP)
    chamam a MESMA função.

    NÃO grava o histórico de quedas nem levanta exceção: quem chamou decide isso,
    porque só ele sabe em nome de que conta está perguntando.
    """
    if not psutil.pid_exists(pid):
        return DcReason.PROCESS_GONE, None
    if not janela_existe:
        return DcReason.WINDOW_GONE, None

    # O AVISO NA TELA: o cliente está morto mesmo com o processo vivo -- clicar
    # em "Ok" encerra o jogo. Devolve o QUADRO, e não um booleano, porque este é
    # o único quadro que serve de print para o histórico de quedas: ele tem o
    # aviso na imagem por construção. Uma captura nova, milissegundos depois,
    # sai preta ou não sai, já que o cliente pode fechar a qualquer instante.
    frame = quadro_com_aviso_de_conexao(hwnd, templates)
    if frame is None:
        return DcReason.NONE, None
    return DcReason.RECONNECT_DIALOG, frame


def quadro_com_aviso_de_conexao(hwnd: int, templates, captura=None):
    """O quadro com "Connection interrupted" na CAIXA, ou `None`.

    `captura` existe para o VIGIA GLOBAL, que fotografa esta janela de outra
    thread e por isso não pode usar o pool de GDI (ver
    `core.vision.capture_window_isolado`). É injeção e não um segundo módulo de
    propósito: o template, o limiar medido e a região são os MESMOS: só muda
    quem segura o bitmap.

    UMA função e não duas: `avaliar_saude` (a definição de queda, para todo
    ecossistema) e `Watchdog._quadro_com_aviso_de_conexao` (a cadência do BC)
    faziam a mesma coisa em cópias separadas. Duas cópias divergem na primeira
    manutenção -- e esta aqui é justamente a que precisou de manutenção.

    DEVOLVE O QUADRO, e não um booleano, porque este é o único quadro que serve
    de print para o histórico de quedas: ele tem o aviso na imagem por
    construção -- foi ele que o reconheceu. Uma captura nova, milissegundos
    depois, sai preta ou não sai, já que o cliente pode fechar a qualquer
    instante.

    A busca é presa à caixa e o limiar é alto: ver o bloco de comentário em
    `RECONNECT_THRESHOLD`.
    """
    template = templates.load(RECONNECT_TEMPLATE) if templates else None
    if template is None:
        return None
    frame = (captura or capture_window)(hwnd)
    if frame is None:
        return None
    if find_template(frame, template, threshold=RECONNECT_THRESHOLD,
                     region=_regiao_do_aviso(frame)) is None:
        return None
    return frame


def _regiao_do_aviso(frame) -> tuple[int, int, int, int]:
    """A janela de busca em volta da caixa, na resolução DESTE quadro.

    Sai de `coords`, e não de literal, porque a UI do jogo não escala: a caixa
    é centralizada na área de cliente, então o ponto acompanha o centro.
    """
    altura, largura = frame.shape[:2]
    cx, cy = coords_for_size(largura, altura).aviso_de_conexao
    raio = RAIO_DA_BUSCA_DO_AVISO
    x0 = max(0, cx - raio)
    y0 = max(0, cy - raio)
    return (x0, y0, min(largura - x0, raio * 2), min(altura - y0, raio * 2))


class Watchdog:
    """Avalia a saúde da sessão a cada snapshot."""

    def __init__(self, ctx: BotContext) -> None:
        self.ctx = ctx
        self._last_visual_check: float = 0.0

    # Não existe `combat_grace`. Existia para suspender a detecção de inatividade
    # durante uma luta; a detecção foi removida (personagem parado NÃO é queda), e
    # o método virou um no-op que só sobrevivia por compatibilidade. Código morto
    # com nome de conceito removido engana quem lê depois.

    def check(self, state: GameState | None = None) -> DcReason:
        """Avalia a saúde da sessão.

        Só devolve motivo de queda para sinais inequívocos. Personagem parado,
        HP estável e memória parcialmente ilegível NÃO derrubam a conta.
        """
        now = time.time()

        # ANOTA A QUEDA NO CONTEXTO, para o "Histórico de Quedas".
        #
        # Vai no `ctx` e não no watchdog porque existem DOIS watchdogs por conta
        # -- um no supervisor e outro na rotina --, e quem grava o histórico não
        # sabe qual dos dois percebeu. O `ctx` é o mesmo para os dois.
        #
        # Nos dois primeiros casos a janela JÁ MORREU quando a queda é
        # percebida: não há o que fotografar, e forçar uma captura aqui só
        # produziria quadro preto. O cartão sai sem print.
        # AS TRÊS CONFERÊNCIAS MORAM EM `avaliar_saude`, função solta neste
        # módulo, para o modo APP -- que não tem `BotContext` -- usar a MESMA
        # definição de queda. Ver o docstring dela.
        #
        # Aqui fica só o que é DESTE contexto: a cadência da conferência visual
        # (a captura é o custo, então ela não sai a cada chamada) e a anotação
        # para o Histórico de Quedas.
        na_hora_de_olhar = now - self._last_visual_check >= VISUAL_CHECK_SECONDS
        if na_hora_de_olhar:
            self._last_visual_check = now

        motivo, quadro = avaliar_saude(
            self.ctx.pid,
            self.ctx.hwnd,
            self.ctx.input.window_exists(),
            self.ctx.templates if na_hora_de_olhar else None,
        )

        MOTIVO_PARA_HISTORICO = {
            DcReason.PROCESS_GONE: "processo",
            DcReason.WINDOW_GONE: "janela",
            DcReason.RECONNECT_DIALOG: "conexao",
        }
        if motivo in MOTIVO_PARA_HISTORICO:
            self.ctx.ultima_queda = (MOTIVO_PARA_HISTORICO[motivo], quadro)
        return motivo

    def _reconnect_dialog_visible(self) -> bool:
        """Compatibilidade: responde só se o aviso está na tela."""
        return self._quadro_com_aviso_de_conexao() is not None

    def _quadro_com_aviso_de_conexao(self):
        """O quadro COM o aviso de conexão interrompida, ou None.

        Quando o aviso aparece, o cliente está morto mesmo que o processo
        continue vivo: clicar em "Ok" encerra o jogo. Encontrar isso é gatilho
        direto de relogin. Sem captura disponível, devolve None e a detecção
        fica por conta dos outros sinais.

        DEVOLVE O QUADRO, e não um booleano, porque este é o único quadro que
        serve de print para o histórico de quedas: ele tem o aviso na imagem
        por construção -- foi ele que o reconheceu. Uma captura nova, tirada
        milissegundos depois, sai preta ou não sai, já que o cliente pode
        fechar a qualquer instante -- e isso aconteceria justamente no ÚNICO
        tipo de queda em que o print é possível.
        """
        return quadro_com_aviso_de_conexao(self.ctx.hwnd, self.ctx.templates)

    def reset(self) -> None:
        self._last_visual_check = 0.0


# Quanto tempo esperar o Windows realmente derrubar o processo depois do
# `TerminateProcess`. NÃO é espera por educação -- o pedido já foi dado e é
# irrecusável; isto é só o tempo de o núcleo desmontar o processo, que é
# submilissegundo no caso normal. O teto existe para o caso patológico (driver
# gráfico segurando um handle) e para a resposta ser um SIM ou NÃO honesto.
ESPERA_PELA_MORTE = 2.0

# Passo entre as conferências de "já morreu?". Fatia curta porque a resposta
# quase sempre chega na primeira.
PASSO_DA_CONFIRMACAO_DA_MORTE = 0.05


def kill_client(pid: int, timeout: float = ESPERA_PELA_MORTE) -> bool:
    """MATA o client.exe pela raiz. Sem pedir, sem esperar, sem negociar.

    =====================================================================
    POR QUE NÃO EXISTE MAIS O PEDIDO EDUCADO
    =====================================================================

    A versão anterior chamava `proc.terminate()` (que no Windows é
    `TerminateProcess` para processo sem console, mas o `psutil` tenta o caminho
    gentil primeiro) e ESPERAVA metade do timeout -- cinco segundos -- antes de
    partir para o `kill()`. Isso está errado nas duas pontas:

      * QUEM chamamos já está morto. Esta função só roda quando a queda foi
        confirmada: ou o processo não responde, ou a sessão dele acabou. Pedir
        educadamente para um cliente TRAVADO fechar é pedir para quem não está
        ouvindo -- os cinco segundos são gastos por inteiro, sempre.
      * O TEMPO É O RECURSO. O orçamento inteiro de detecção-até-relogin é de
        20 s. Cinco deles em cerimônia com um processo morto é um quarto do
        orçamento.

    E há um efeito que não é secundário: **o kill é o que DESBLOQUEIA a thread
    do bot.** Se ela estiver parada dentro de um `SendMessageW` síncrono contra
    a janela travada -- que é o modo típico de a conta ficar presa para sempre
    --, a chamada só retorna quando a janela deixa de existir. Matar o processo
    é, literalmente, a operação que devolve a thread para o laço de sessão.

    Devolve se o processo REALMENTE morreu; nunca levanta.
    """
    if not pid:
        return True
    if not psutil.pid_exists(pid):
        return True

    # PRIMEIRO CAMINHO: `psutil.Process.kill()` é `TerminateProcess` no Windows.
    try:
        psutil.Process(pid).kill()
    except psutil.NoSuchProcess:
        return True
    except Exception:
        # AccessDenied acontece quando o bot não está como administrador, ou
        # quando o processo está em estado de encerramento. O `taskkill` abaixo
        # é a segunda tentativa, e ele fala com o SCM em vez do handle.
        pass

    if _morreu(pid, timeout):
        return True

    # SEGUNDO CAMINHO: `taskkill /F /T`, que também derruba filhos. Sem console,
    # sem janela, sem herdar as pipes do bot.
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(int(pid))],
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except Exception:
        pass
    return _morreu(pid, timeout)


def _morreu(pid: int, teto: float) -> bool:
    """Espera o processo sumir da tabela, até `teto`. Devolve se sumiu."""
    fim = time.monotonic() + max(0.0, teto)
    while True:
        if not psutil.pid_exists(pid):
            return True
        if time.monotonic() >= fim:
            return False
        time.sleep(PASSO_DA_CONFIRMACAO_DA_MORTE)


def client_pids() -> set[int]:
    """PIDs de todas as instâncias de client.exe em execução."""
    found: set[int] = set()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name == "client.exe":
                found.add(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def backoff_delay(attempt: int, cap: int) -> float:
    """Backoff exponencial: 1, 2, 4, 8... limitado por `cap`."""
    return float(min(2 ** max(0, attempt - 1), cap))
