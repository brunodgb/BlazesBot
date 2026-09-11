"""O VIGIA GLOBAL: uma thread só, fora do bot, que pergunta se o cliente vive.

=========================================================================
O DEFEITO QUE ISTO CONSERTA -- e por que o vigia anterior não podia funcionar
=========================================================================

Até aqui a vigilância era COOPERATIVA: `Watchdog.check()` só rodava quando
alguém da thread do bot o chamava -- `ctx.tick()`, `_guard()`, o
`conferir_saude` entre linhas da macro. Isso funciona enquanto a thread do bot
continua andando, e é exatamente a premissa que uma queda destrói:

  1. O bot fala com o jogo por `SendMessageW` SÍNCRONO (regra permanente: a
     mensagem confere a janela e sai síncrona, com a coordenada no `lParam`).
     `SendMessageW` para uma janela TRAVADA **não tem timeout**: ela bloqueia a
     thread que enviou, indefinidamente. A thread do bot para dentro de uma
     tecla, e a conferência que perceberia a queda está DEPOIS dessa linha.
     Vigia e vigiado eram a mesma thread -- travou um, travou o outro.
  2. Mesmo sem travamento, existiam janelas cegas: a espera do backoff entre
     relogins (`_sleep_interruptible`), a conta ONLINE e ociosa (sem BC, sem HH,
     sem APP), e o login em curso. Nesses trechos ninguém chamava `check()`, e
     a conta podia ficar horas caída sem que nada perguntasse.
  3. A definição de queda não tinha o sinal do TRAVAMENTO. Processo vivo,
     janela existindo, nenhuma caixa na tela: os três sinais de `avaliar_saude`
     dizem "saudável" para um cliente congelado. Era o caso que ficava preso
     para sempre.

Este módulo é a resposta: UMA thread para o processo inteiro, acordando a cada
`CADENCIA_DO_VIGIA` segundos, perguntando pelas contas TODAS, imune ao que
qualquer thread de bot esteja fazendo -- inclusive imune a estar bloqueada.

=========================================================================
POR QUE UMA THREAD SÓ, E NÃO UMA POR CONTA
=========================================================================

A pergunta inteira é feita de syscalls que respondem em microssegundos
(`pid_exists`, `IsWindow`, `SendMessageTimeout`) mais uma captura por conta por
ciclo. Cinco contas cabem folgadamente numa volta. Uma thread por conta seria
cinco vezes o mesmo `Event.wait` para o mesmo trabalho -- e cinco lugares onde
esquecer de encerrar.

O custo em repouso é ZERO: `Event.wait(timeout)` é bloqueio no núcleo, não
espera ocupada. Entre um ciclo e outro a thread não consome CPU nenhuma.

=========================================================================
POR QUE O VIGIA NÃO ENCOSTA EM NADA DA THREAD DO BOT
=========================================================================

Esta é a parte que dá certo ou erra calada, então é regra, não cuidado:

  * NÃO lê memória do jogo. `ctx.memory` tem um handle de processo que a thread
    do bot abre e FECHA (`ctx.close()`); ler dele daqui é ler handle que pode
    ter sido fechado no meio da chamada. Todo sinal do vigia é sistema
    operacional, não jogo.
  * NÃO usa `capture_window`. O pool de GDI (`vision._pools`) é um dicionário de
    módulo sem cadeado, com um DC e um bitmap POR JANELA, e `_release()` destrói
    o pool da conta. Duas threads no mesmo bitmap dão quadro rasgado, e destruir
    o DC durante o BitBlt da outra dá handle inválido em silêncio. O vigia usa
    `capture_window_isolado`, que aloca o seu e devolve.
  * NÃO tem `TemplateLibrary` compartilhada. A dele é dele, e só a thread dele
    toca nela.
  * NÃO escreve no `BotContext`. O que ele produz é UM registro no seu próprio
    dicionário, protegido por cadeado, que a thread do bot LÊ quando volta.

O único estado que atravessa a fronteira é `Posto.queda`, escrito com o cadeado
segurado e lido com o cadeado segurado.

=========================================================================
O DESFECHO: MATAR É O QUE DEVOLVE A CONTA
=========================================================================

Confirmada a queda, o vigia NÃO tenta ser educado e NÃO tenta avisar a thread do
bot primeiro -- ela pode estar bloqueada, e é justamente esse o caso que
importa. Ele:

  1. ANUNCIA a queda no posto (com o quadro, quando houver);
  2. MATA o processo pela raiz (`kill_client`, que é `TerminateProcess`).

A ordem não é trocável. O anúncio primeiro, porque matar o processo DESBLOQUEIA
a thread do bot na mesma hora (um `SendMessageW` contra uma janela que deixou de
existir retorna imediatamente) -- e ela tem que encontrar o anúncio já lá quando
acordar, senão perde o motivo verdadeiro da queda e registra "processo" no lugar
de "travou".

Quem religa continua sendo o supervisor, pelo caminho que já existia: a thread
do bot acorda, lê o anúncio, levanta `Disconnected`, e o `run()` faz
`_encerrar_caido` -> backoff -> nova sessão -> login. O vigia não sabe o que é
login, e não precisa saber. Ver `docs/INVARIANTES.md`, seção "Login e relogin".
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..core.janelas import janela_responde
from ..core.vision import TemplateLibrary, capture_window_isolado
from .watchdog import (
    DcReason,
    avaliar_saude,
    kill_client,
    quadro_com_aviso_de_conexao,
)

# O MESMO logger de todo o bot ("blazes"): o vigia aparece no mesmo arquivo
# de log que a conta que ele derrubou, na mesma linha do tempo.
log = logging.getLogger("blazes.vigia")

# ===========================================================================
# O ORÇAMENTO DE 20 SEGUNDOS, repartido
# ===========================================================================
#
# O requisito é: da queda até o `TerminateProcess`, no MÁXIMO 20 s -- não
# importa o ecossistema, nem se o bot está ocioso.
#
# O pior caso de um sinal que precisa de N confirmações é `N * CADENCIA`: a
# queda acontece logo depois de um ciclo, o próximo marca a primeira falta, e a
# N-ésima confirma. Daí os números saírem de uma conta e não de gosto:
#
#     sinal                confirmações   pior caso
#     processo sumiu             1           6 s
#     aviso na tela              1           6 s
#     janela sumiu               2          12 s
#     janela travada             3          18 s   <- o teto do orçamento
#
# 18 s deixa 2 s de folga para o ciclo em si (as sondas de 5 contas travadas
# custam até 7,5 s de relógio, mas rodam DENTRO do ciclo, não somadas a ele).
CADENCIA_DO_VIGIA = 6.0

# ===========================================================================
# AS CONFIRMAÇÕES -- a defesa contra derrubar conta boa por causa de lag
# ===========================================================================
#
# Cada número aqui é uma resposta à pergunta "quanto de silêncio ainda é
# normal?", e ela tem resposta diferente por sinal:
#
# PROCESSO SUMIDO e AVISO NA TELA não têm falso positivo possível -- um processo
# não volta a existir, e o aviso já passa por região presa à caixa + limiar 0.92
# (margem medida de +0.559 sobre o pior falso; ver `watchdog.RECONNECT_THRESHOLD`).
# Confirmar seria só atrasar. Por isso não aparecem aqui: matam na primeira.
#
# JANELA SUMIDA é quase tão firme, mas o `hwnd` que o vigia lê vem do supervisor
# em outra thread, e existe uma fresta de um ciclo entre o supervisor trocar de
# janela e o vigia enxergar a nova. Duas voltas fecham a fresta sem custo.
STRIKES_PARA_JANELA_SUMIDA = 2

# JANELA TRAVADA é o sinal ruidoso, e é o único que precisa de defesa de
# verdade: troca de mapa, pico de disco e o Windows suspendendo janela
# minimizada produzem silêncio momentâneo. Três voltas = 18 s de laço de
# mensagens completamente parado, contra uma sonda que uma janela viva responde
# em microssegundos mesmo carregando cenário. Nenhum lag de servidor chega perto
# disso: lag de rede não para o laço de mensagens do Windows -- o cliente
# continua repintando e respondendo, só não recebe pacote.
STRIKES_PARA_JANELA_TRAVADA = 3

# ===========================================================================
# INTERRUPTOR (a convenção do projeto: caminho fora de uso não vira comentário)
# ===========================================================================
#
# Desligar isto devolve o vigia à definição de queda dos três sinais antigos: o
# cliente CONGELADO volta a ficar preso para sempre. Está aqui porque é o único
# critério de morte novo, e o único que mata uma janela que o Windows ainda
# considera viva -- se um dia ele derrubar conta boa, a volta atrás é uma linha,
# e não uma edição no meio do laço.
MATAR_JANELA_TRAVADA = True

# ===========================================================================
# O VIGIA LÊ A TELA -- religado em 11/09/2026, e o porquê do vaivém importa
# ===========================================================================
#
# ELE FOI DESLIGADO EM 09/09/2026, e a justificativa estava ERRADA num ponto
# decisivo. O que eu escrevi então: *"o aviso na tela já tinha DOIS leitores, o
# watchdog inline e o `LoginDetector`"*.
#
# O WATCHDOG INLINE SÓ EXISTE NO BC. `ctx.watchdog` é injetado num lugar só --
# `bc/routine.py`, no `__init__` da rotina. Conta de APP, de Fada e de HH sem BC
# tem `ctx.watchdog = None`, e `BotContext.check_watchdog` sai por `return` na
# primeira linha. Elas nunca tiveram o segundo leitor que eu supus.
#
# PIOR NA FADA: ela não chama `ctx.tick()` em ponto nenhum, então nem a consulta
# ao vigia acontece; e a única queda que ela percebe é `IsWindow` DEPOIS que o
# laço retorna (`fada_montagem.py`). A caixa "Connection interrupted" deixa a
# janela VIVA -- o laço nunca retorna, e a conta fica presa para sempre.
#
# MEDIDO EM 11/09/2026: três contas de APP/Fada travadas ao mesmo tempo com a
# caixa na tela, nenhuma derrubada. Os três decretos do vigia naquele dia foram
# TODOS por "processo do cliente encerrado" -- nenhum por tela, porque o
# interruptor estava aqui em `False`.
#
# E OS 48 FALSOS POSITIVOS QUE MOTIVARAM O DESLIGAMENTO? Já estavam resolvidos
# quando desliguei. Todos os 48 aconteceram nas TELAS DE LOGIN, e a suspensão do
# juízo durante o login (`SO_FATO_DO_SISTEMA_DURANTE_O_LOGIN`, do mesmo dia) é
# anterior a este interruptor. Com ela valendo, o vigia só lê a tela com a
# sessão ESTABELECIDA -- que é exatamente a população onde o limiar 0.92 foi
# medido, com margem de +0.559 sobre o pior falso. Desligar depois disso foi
# zelo em cima de causa já consertada, e custou três contas travadas.
#
# O QUE CONTINUA VERDADE do texto antigo: o vigia não é o único leitor em jogo
# -- no BC o watchdog inline vê primeiro, a cada 10 s. Aqui ele é a REDE para
# quem não tem watchdog inline nenhum, que é todo o resto.
OLHAR_A_TELA = True

# ===========================================================================
# DURANTE O LOGIN, O VIGIA SÓ RECONHECE FATO DO SISTEMA OPERACIONAL
# ===========================================================================
#
# Processo sumido e janela sumida continuam valendo: são fatos, não leitura.
# O AVISO NA TELA e o TRAVAMENTO ficam suspensos enquanto `login.run()` está no
# comando. Isto NÃO é cautela genérica -- é conserto de um defeito medido em
# 09/09/2026, com a conta `blazesgamer` em laço de relogin a cada 19 s.
#
# O QUE ACONTECEU. Dois segundos depois de "Servidor confirmado como
# selecionado", o vigia decretava "aviso de conexão interrompida na tela" e
# matava o cliente. O login, que estava entrando na fila, reportava "a janela do
# cliente desapareceu durante o login" -- a causa verdadeira se perdia, e o
# ciclo recomeçava: abrir cliente, logar, morrer, backoff, abrir cliente.
#
# POR QUE O VIGIA ERRA NESSAS TELAS, e o `LoginDetector` não. O template do
# vigia é UM só, `state_conn_prefix.png`, que casa com a palavra "Connection".
# Nas telas de login existe uma FAMÍLIA de caixas que começam com ela, e todas
# são desenhadas no MESMO lugar que o aviso de queda -- o centro. Medido em
# 18/08/2026 e registrado em `login_states.py`:
#
#     "Connection failed"           state_conn_prefix = 0.835
#     "Connecting to the server"    state_conn_prefix = 0.787
#
# O `LoginDetector` convive com isso porque tem ESCADA ORDENADA: pergunta pelos
# templates específicos primeiro (`state_conn_failed`, `state_connecting`) e só
# deixa o genérico opinar POR ÚLTIMO. O vigia não tem escada -- ele usa o
# genérico sozinho, e ainda travado na região onde essas caixas aparecem.
#
# E o limiar de 0.92 não protege: ele foi medido contra população EM JOGO (o
# aviso real de um lado, linhas de chat do outro). As telas de login nunca
# estiveram em nenhuma das duas populações. Usar limiar fora da população onde
# foi medido é exatamente o que o projeto proíbe.
#
# O TRAVAMENTO cai junto pelo mesmo princípio, com um agravante próprio: a FILA
# DE LOGIN passa de três horas, e não há medição nenhuma de como o cliente
# bombeia mensagens enquanto espera nela. Matar cliente na fila é o dano mais
# caro que este bot sabe causar.
#
# Quem lê a tela durante o login é o `LoginDetector`, que já tem o tratamento
# certo para cada uma dessas caixas (`login._handle_conn_interrupted` e
# vizinhos). Duas leituras da mesma tela divergem na primeira manutenção -- e
# esta divergiu antes mesmo da primeira.

# Pasta dos templates. A MESMA de todo mundo -- o quadro de queda é o mesmo
# arquivo, com o mesmo limiar. O que é só do vigia é a INSTÂNCIA da biblioteca.
PASTA_DOS_TEMPLATES = Path("data") / "templates"

# A chave do Histórico de Quedas para cada motivo. Mora aqui e não em `quedas`
# porque a tradução motivo->chave é do lado de quem detecta; `core/quedas.py`
# não importa nada de `bot/`.
CHAVE_NO_HISTORICO = {
    DcReason.PROCESS_GONE: "processo",
    DcReason.WINDOW_GONE: "janela",
    DcReason.RECONNECT_DIALOG: "conexao",
    DcReason.WINDOW_HUNG: "travou",
}


@dataclass
class Posto:
    """Uma conta sob vigilância. Um posto por supervisor vivo.

    `fonte` é uma função e não `(pid, hwnd)` fixos DE PROPÓSITO: os dois mudam a
    cada relogin, e guardá-los aqui faria o vigia perguntar por um processo
    morto pelo resto da execução -- que é o mesmo defeito que o `BotContext` já
    teve com pid/hwnd fixos. A função é chamada a cada ciclo e devolve o par
    ATUAL, ou `(None, None)` quando a conta não tem janela agora.
    """

    login: str
    fonte: Callable[[], tuple[int | None, int | None]]
    avisar: Callable[[str], None] | None = None
    # A CONTA JÁ ESTÁ EM SESSÃO? `None` = sim, sempre (é o padrão dos testes).
    # Ver `SO_FATO_DO_SISTEMA_DURANTE_O_LOGIN`.
    em_sessao: Callable[[], bool] | None = None

    faltas_de_janela: int = 0
    faltas_de_resposta: int = 0

    # O ANÚNCIO: `(chave_do_historico, quadro, frase)` ou `None`. É o único
    # campo que atravessa a fronteira entre as threads.
    queda: tuple[str, object, str] | None = None
    # O PID que morreu. Serve para o anúncio se apagar sozinho quando a conta
    # reabre num processo novo -- sem isso, um anúncio não consumido derrubaria
    # a sessão seguinte no primeiro `tick`.
    pid_da_queda: int | None = None
    evento: threading.Event = field(default_factory=threading.Event)

    def zerar_contagem(self) -> None:
        self.faltas_de_janela = 0
        self.faltas_de_resposta = 0


class Vigia:
    """A thread única. Registra postos, acorda, pergunta, mata, volta a dormir."""

    def __init__(self, cadencia: float = CADENCIA_DO_VIGIA) -> None:
        self.cadencia = cadencia
        self._postos: dict[str, Posto] = {}
        self._cadeado = threading.Lock()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        # A biblioteca de templates do VIGIA. Só esta thread a toca -- ver o
        # cabeçalho do módulo.
        self._templates: TemplateLibrary | None = None

    # -- registro ----------------------------------------------------------

    def vigiar(self, login: str, fonte, avisar=None, em_sessao=None) -> Posto:
        """Põe a conta sob vigilância e garante a thread de pé.

        Idempotente: registrar de novo a mesma conta substitui a fonte (o
        supervisor pode ser recriado) e NÃO reinicia a thread.
        """
        with self._cadeado:
            posto = Posto(login=login, fonte=fonte, avisar=avisar,
                          em_sessao=em_sessao)
            self._postos[login] = posto
        self.ligar()
        return posto

    def esquecer(self, login: str) -> None:
        """Tira a conta da vigilância. Chamado quando o supervisor encerra."""
        with self._cadeado:
            self._postos.pop(login, None)
            vazio = not self._postos
        if vazio:
            self.desligar()

    def limpar(self, login: str) -> None:
        """Apaga o anúncio de queda desta conta, sem tirá-la da vigilância.

        Chamado depois que o relogin foi engatado: o anúncio já cumpriu o papel,
        e deixá-lo aí derrubaria a sessão nova no primeiro `tick`.
        """
        with self._cadeado:
            posto = self._postos.get(login)
            if posto is None:
                return
            posto.queda = None
            posto.pid_da_queda = None
            posto.zerar_contagem()
            posto.evento.clear()

    def queda_anunciada(self, login: str) -> tuple[str, object, str] | None:
        """O anúncio desta conta, ou `None`. É a porta que a thread do bot usa."""
        with self._cadeado:
            posto = self._postos.get(login)
            return posto.queda if posto is not None else None

    def evento_de_queda(self, login: str) -> threading.Event | None:
        """O `Event` que acorda quem estiver esperando. `None` se não vigiada."""
        with self._cadeado:
            posto = self._postos.get(login)
            return posto.evento if posto is not None else None

    # -- a thread ----------------------------------------------------------

    def ligar(self) -> None:
        """Sobe a thread, se ela ainda não estiver de pé. Idempotente."""
        with self._cadeado:
            if self._thread is not None and self._thread.is_alive():
                return
            self._parar.clear()
            self._thread = threading.Thread(
                target=self._rodar, name="vigia-global", daemon=True)
            self._thread.start()
        log.info("Vigia global de pé: uma volta a cada %.0fs.", self.cadencia)

    def desligar(self, esperar: float = 0.0) -> None:
        """Pede o encerramento. `Event.set()` acorda a thread NA HORA."""
        self._parar.set()
        thread = self._thread
        if esperar and thread is not None and thread.is_alive():
            thread.join(timeout=esperar)
        self._thread = None

    def _rodar(self) -> None:
        """O laço. Acorda, pergunta por todos, dorme. Nunca morre por exceção.

        `Event.wait(cadencia)` é o que faz o repouso custar ZERO CPU e ainda
        assim o `desligar()` ser instantâneo -- um `sleep` daria uma das duas
        coisas, nunca as duas.
        """
        while not self._parar.is_set():
            try:
                self._uma_volta()
            except Exception:
                # UMA VOLTA RUIM NÃO PODE MATAR O VIGIA. Sem este `except`, uma
                # exceção qualquer (janela destruída no meio da captura, por
                # exemplo) encerraria a thread em silêncio -- e a ausência de
                # vigia é indistinguível de tudo estar bem.
                log.exception("Falha numa volta do vigia; a próxima segue.")
            self._parar.wait(self.cadencia)

    def _uma_volta(self) -> None:
        with self._cadeado:
            postos = list(self._postos.values())
        for posto in postos:
            try:
                self._conferir(posto)
            except Exception:
                log.exception("Falha ao conferir a conta %s", posto.login)

    # -- a escada de sinais ------------------------------------------------

    def _conferir(self, posto: Posto) -> None:
        """A ESCADA, do sinal mais barato ao mais caro. A ordem é a economia.

        Cada degrau só é pago se o anterior não respondeu, e o degrau CARO (a
        captura) só é pago quando a janela provou que responde -- ver o comentário
        no lugar.
        """
        pid, hwnd = posto.fonte()

        # SEM JANELA NÃO É QUEDA. É o estado normal de uma conta entre sessões:
        # o supervisor soltou o controle, ou ainda está abrindo o cliente. Zera a
        # contagem para a sessão nova não herdar falta da anterior.
        if not pid or not hwnd:
            posto.zerar_contagem()
            return

        # O ANÚNCIO SE APAGA SOZINHO quando a conta volta noutro processo. Sem
        # isto, um anúncio que ninguém consumiu (a thread do bot morreu por
        # outro caminho) derrubaria a sessão seguinte no primeiro `tick`.
        if posto.pid_da_queda is not None and pid != posto.pid_da_queda:
            self.limpar(posto.login)

        if posto.queda is not None:
            # Já anunciada e ainda não consumida: não reanuncia, não remata.
            return

        # DEGRAU 1 e 2 -- processo e janela. Syscalls locais, custo desprezível.
        # DEGRAU 3 é o aviso na tela, e ele é DELIBERADAMENTE pulado aqui
        # (`templates=None`): a captura tem que vir DEPOIS da sonda, senão o
        # vigia se pendura na janela travada. Ver o degrau 5.
        import win32gui

        janela_existe = bool(win32gui.IsWindow(hwnd))
        motivo, _ = avaliar_saude(pid, hwnd, janela_existe, None)

        if motivo is DcReason.PROCESS_GONE:
            # Sem confirmação: processo não ressuscita.
            self._decretar(posto, pid, DcReason.PROCESS_GONE, None)
            return

        if motivo is DcReason.WINDOW_GONE:
            posto.faltas_de_janela += 1
            if posto.faltas_de_janela >= STRIKES_PARA_JANELA_SUMIDA:
                self._decretar(posto, pid, DcReason.WINDOW_GONE, None)
            return
        posto.faltas_de_janela = 0

        # ==================================================================
        # DAQUI PARA BAIXO É JUÍZO, E DURANTE O LOGIN O JUÍZO NÃO É DO VIGIA
        # ==================================================================
        #
        # Ver `SO_FATO_DO_SISTEMA_DURANTE_O_LOGIN`. Zera a contagem de
        # travamento junto: o silêncio de uma tela de login não pode ser somado
        # ao de uma sessão que começou depois.
        if posto.em_sessao is not None and not posto.em_sessao():
            posto.faltas_de_resposta = 0
            return

        # DEGRAU 4 -- A SONDA DE TRAVAMENTO.
        #
        # Ela vem ANTES da captura por dois motivos, e os dois são obrigatórios:
        #
        #   1. É o sinal que faltava. Cliente congelado tem processo vivo, janela
        #      viva e nenhuma caixa na tela -- os outros três sinais dizem
        #      "saudável" para ele, e era assim que a conta ficava presa.
        #   2. PROTEGE O PRÓPRIO VIGIA. `PrintWindow` (o primeiro caminho da
        #      captura) manda `WM_PRINT` SÍNCRONO para a janela. Fotografar uma
        #      janela travada penduraria a thread do vigia exatamente como
        #      pendura a thread do bot -- o vigia morreria da doença que veio
        #      diagnosticar.
        if not janela_responde(hwnd):
            posto.faltas_de_resposta += 1
            if (MATAR_JANELA_TRAVADA
                    and posto.faltas_de_resposta >= STRIKES_PARA_JANELA_TRAVADA):
                self._decretar(posto, pid, DcReason.WINDOW_HUNG, None)
            return
        posto.faltas_de_resposta = 0

        # DEGRAU 5 -- O AVISO NA TELA. O único caro (captura + template), e o
        # único que produz PRINT para o Histórico de Quedas. Só chega aqui janela
        # que acabou de provar que responde, então a captura não trava.
        #
        # DESLIGADO: ver `OLHAR_A_TELA`. Quem lê esta tela é o watchdog inline e
        # o `LoginDetector` -- e eles já liam bem.
        if not OLHAR_A_TELA:
            return
        quadro = quadro_com_aviso_de_conexao(
            hwnd, self._biblioteca(), captura=capture_window_isolado)
        if quadro is not None:
            self._decretar(posto, pid, DcReason.RECONNECT_DIALOG, quadro)

    def _biblioteca(self) -> TemplateLibrary:
        """A biblioteca DESTA thread, criada na primeira necessidade."""
        if self._templates is None:
            self._templates = TemplateLibrary(PASTA_DOS_TEMPLATES)
        return self._templates

    # -- o desfecho --------------------------------------------------------

    def _decretar(self, posto: Posto, pid: int, motivo: DcReason,
                  quadro) -> None:
        """Anuncia a queda e MATA. Nesta ordem, e a ordem não é trocável.

        O anúncio primeiro porque o kill DESBLOQUEIA a thread do bot na mesma
        hora: um `SendMessageW` contra uma janela que deixou de existir retorna
        imediatamente. Ela tem que achar o anúncio já publicado quando acordar --
        senão a próxima conferência dela vê só "processo sumiu" e o Histórico de
        Quedas registra o efeito no lugar da causa.
        """
        chave = CHAVE_NO_HISTORICO.get(motivo, "travou")
        with self._cadeado:
            posto.queda = (chave, quadro, motivo.value)
            posto.pid_da_queda = pid
            posto.evento.set()

        frase = (f"VIGIA: {motivo.value} — matando o cliente da conta "
                 f"{posto.login} (PID {pid}) e engatando o relogin.")
        log.warning(frase)
        if posto.avisar is not None:
            try:
                posto.avisar(frase)
            except Exception:
                # Avisar a interface NUNCA pode impedir o kill.
                log.debug("Não consegui avisar a interface", exc_info=True)

        morreu = kill_client(pid)
        if not morreu:
            log.error(
                "VIGIA: o PID %s NÃO morreu nem com TerminateProcess nem com "
                "taskkill /F. A conta %s vai tentar reaproveitar a janela.",
                pid, posto.login)


# ===========================================================================
# A INSTÂNCIA ÚNICA -- é UM vigia por processo, não um por chamador
# ===========================================================================
#
# Módulo com estado global é coisa que se paga caro quando errado, então vale
# dizer por que aqui está certo: o objeto que se quer é literalmente único (uma
# thread para o processo), e quem o usa são threads independentes que não têm
# como passar uma referência uma para a outra -- cada supervisor nasce sozinho.
# É o mesmo arranjo de `bot/mural.py`.
SENTINELA = Vigia()

vigiar = SENTINELA.vigiar
esquecer = SENTINELA.esquecer
limpar = SENTINELA.limpar
queda_anunciada = SENTINELA.queda_anunciada
evento_de_queda = SENTINELA.evento_de_queda
ligar = SENTINELA.ligar
desligar = SENTINELA.desligar


def cobrar_a_queda(login: str) -> tuple[str, object, str] | None:
    """O anúncio desta conta, para quem vai LEVANTAR `Disconnected` agora.

    Existe com nome próprio para os três pontos de contato do sistema com o
    vigia (`BotContext.check_watchdog`, a espera do supervisor e a conferência
    do modo APP) chamarem a MESMA coisa em vez de cada um ler o dicionário do
    seu jeito. Duas leituras do mesmo estado divergem na primeira manutenção.

    NÃO apaga o anúncio: quem apaga é `limpar()`, depois que o relogin engatou.
    Enquanto o anúncio estiver de pé, TODA conferência daquela conta devolve
    queda -- é o que garante que ela não volte a agir contra a janela morta,
    mesmo que o `Disconnected` seja engolido por algum `except` no caminho.
    """
    return SENTINELA.queda_anunciada(login)
