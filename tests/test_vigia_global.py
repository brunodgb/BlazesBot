"""O VIGIA GLOBAL: a queda é percebida em ≤20 s, em qualquer ecossistema, mesmo ocioso.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

A vigilância era COOPERATIVA: `Watchdog.check()` só rodava quando a thread do
bot o chamava. Três consequências, todas medidas em campo:

  1. `SendMessageW` síncrono contra janela TRAVADA não tem timeout -- bloqueia
     a thread que enviou, para sempre. Vigia e vigiado eram a mesma thread:
     travou um, travou o outro, e a conta ficava presa indefinidamente.
  2. Havia janelas cegas -- backoff entre relogins, conta ociosa, login em
     curso -- em que ninguém chamava `check()`.
  3. Não existia sinal de TRAVAMENTO: processo vivo + janela viva + nenhuma
     caixa na tela = "saudável" para os três sinais de `avaliar_saude`.

O que se trava aqui é o desenho que responde aos três: uma thread separada, com
confirmação por reincidência, que MATA pela raiz e deixa o relogin engatar pelo
caminho que já existia.
"""
from __future__ import annotations

import ast
import inspect
import logging
import textwrap
import threading
import time
from pathlib import Path

import pytest

from blazesbot.bot import sentinela as mod
from blazesbot.bot.watchdog import DcReason

# ===========================================================================
# O ORÇAMENTO DE TEMPO -- é o requisito, então é teste e não comentário
# ===========================================================================


def test_o_pior_caso_de_cada_sinal_cabe_em_20_segundos():
    """`N confirmações x cadência` é o atraso máximo até o kill.

    Se alguém subir a cadência ou pedir mais uma confirmação "por segurança",
    o requisito de 20 s quebra em silêncio -- a conta só ficaria presa por
    mais tempo, que é exatamente o defeito de origem.
    """
    piores = {
        "processo sumiu": 1 * mod.CADENCIA_DO_VIGIA,
        "aviso na tela": 1 * mod.CADENCIA_DO_VIGIA,
        "janela sumiu": mod.STRIKES_PARA_JANELA_SUMIDA * mod.CADENCIA_DO_VIGIA,
        "janela travada": mod.STRIKES_PARA_JANELA_TRAVADA * mod.CADENCIA_DO_VIGIA,
    }
    for sinal, segundos in piores.items():
        assert segundos <= 20.0, f"{sinal} demora {segundos}s — o teto é 20s"


def test_travamento_exige_confirmacao_e_processo_sumido_NAO():
    """A defesa contra falso positivo está onde o ruído está, e só lá.

    Lag e troca de mapa produzem silêncio momentâneo -> travamento precisa de
    reincidência. Processo que sumiu não ressuscita -> confirmar seria só
    atrasar o relogin.
    """
    assert mod.STRIKES_PARA_JANELA_TRAVADA >= 2, (
        "um único silêncio derrubaria conta boa no primeiro lag de disco")
    assert mod.STRIKES_PARA_JANELA_SUMIDA >= 1


# ===========================================================================
# O ISOLAMENTO -- a thread do vigia não pode encostar no que é da thread do bot
# ===========================================================================


def test_o_vigia_NAO_usa_o_pool_de_GDI_compartilhado():
    """`capture_window` reaproveita DC e bitmap por janela, sem cadeado.

    Fotografar do vigia com ele é quadro rasgado hoje e handle destruído
    debaixo da outra thread amanhã (`_release` chama `release_pool`).
    """
    fonte = Path(mod.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    usados = {no.id for no in ast.walk(arvore) if isinstance(no, ast.Name)}
    usados |= {no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)}
    usados |= {(a.asname or a.name).split(".")[-1]
               for a in ast.walk(arvore) if isinstance(a, ast.alias)}

    assert "capture_window_isolado" in usados
    assert "capture_window" not in usados, (
        "o vigia voltou a usar a captura com pool — corrida de GDI com a "
        "thread do bot")


def test_o_vigia_NAO_le_memoria_do_jogo():
    """`ctx.memory` tem handle que a thread do bot abre e FECHA."""
    fonte = Path(mod.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    usados = {no.attr for no in ast.walk(arvore) if isinstance(no, ast.Attribute)}
    for proibido in ("memory", "snapshot", "vida_pct", "position"):
        assert proibido not in usados, (
            f"o vigia passou a usar `{proibido}` — leitura de memória de outra "
            f"thread, com handle que pode estar fechado")


def test_a_sonda_vem_ANTES_da_captura():
    """`PrintWindow` manda `WM_PRINT` SÍNCRONO: fotografar janela travada
    penduraria a thread do vigia na doença que ele veio diagnosticar."""
    fonte = inspect.getsource(mod.Vigia._conferir)
    assert fonte.index("janela_responde(") < fonte.index(
        "quadro_com_aviso_de_conexao("), (
        "a captura passou na frente da sonda — o vigia trava junto com a janela")


def test_o_repouso_e_bloqueio_no_nucleo_e_nao_espera_ocupada():
    """`Event.wait` custa 0% de CPU e ainda deixa o `desligar()` instantâneo.

    `time.sleep` daria uma das duas coisas, nunca as duas -- e o vigia é a
    única thread do processo que roda o tempo TODO, com o bot ocioso ou não.
    """
    fonte = inspect.getsource(mod.Vigia._rodar)
    assert "_parar.wait(" in fonte
    assert "time.sleep" not in fonte


# ===========================================================================
# O COMPORTAMENTO -- com o mundo dublado
# ===========================================================================


class _Mundo:
    """Substitui as três perguntas do vigia por respostas controladas."""

    def __init__(self, *, pid=4242, hwnd=99, existe=True, responde=True,
                 aviso=None):
        self.pid, self.hwnd = pid, hwnd
        self.existe, self.responde, self.aviso = existe, responde, aviso
        self.mortos: list[int] = []

    def instalar(self, monkeypatch):
        # FORÇA O INTERRUPTOR LIGADO -- é a convenção do projeto para caminho
        # fora de uso: ele não some, e o teste continua exercitando a lógica.
        monkeypatch.setattr(mod, "OLHAR_A_TELA", True)
        monkeypatch.setattr(mod, "janela_responde",
                            lambda hwnd, *a, **k: self.responde)
        monkeypatch.setattr(mod, "quadro_com_aviso_de_conexao",
                            lambda *a, **k: self.aviso)
        monkeypatch.setattr(mod, "kill_client", self._matar)
        # `IsWindow` e `pid_exists` entram por `avaliar_saude`, que é a UMA
        # definição de queda -- o dublê a mantém no caminho.
        monkeypatch.setattr(
            mod, "avaliar_saude",
            lambda pid, hwnd, janela_existe, templates: (
                (DcReason.PROCESS_GONE, None) if pid is None
                else (DcReason.WINDOW_GONE, None) if not janela_existe
                else (DcReason.NONE, None)))
        import win32gui
        monkeypatch.setattr(win32gui, "IsWindow", lambda h: self.existe)

    def _matar(self, pid, *a, **k):
        self.mortos.append(pid)
        return True


@pytest.fixture
def vigia():
    """Um vigia SEM thread: os testes chamam `_uma_volta()` à mão.

    De propósito -- teste que depende de acordar thread mede o relógio, não o
    comportamento.
    """
    v = mod.Vigia(cadencia=999.0)
    yield v
    v.desligar()


def _por(vigia, mundo, login="conta1"):
    posto = mod.Posto(login=login, fonte=lambda: (mundo.pid, mundo.hwnd))
    vigia._postos[login] = posto
    return posto


def test_janela_travada_so_mata_na_terceira_volta(vigia, monkeypatch):
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)
    _por(vigia, mundo)

    for volta in range(1, mod.STRIKES_PARA_JANELA_TRAVADA):
        vigia._uma_volta()
        assert mundo.mortos == [], (
            f"matou na volta {volta} — um lag derrubaria conta boa")

    vigia._uma_volta()
    assert mundo.mortos == [4242]
    assert vigia.queda_anunciada("conta1")[0] == "travou"


def test_uma_resposta_no_meio_ZERA_a_contagem(vigia, monkeypatch):
    """É o que separa lag de travamento: silêncio INTERROMPIDO não é queda."""
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)
    _por(vigia, mundo)

    vigia._uma_volta()
    vigia._uma_volta()
    mundo.responde = True
    vigia._uma_volta()          # respondeu: a contagem morre aqui
    mundo.responde = False
    for _ in range(mod.STRIKES_PARA_JANELA_TRAVADA - 1):
        vigia._uma_volta()
    assert mundo.mortos == [], "a contagem não zerou — lag vira queda"


def test_processo_sumido_mata_na_PRIMEIRA_volta(vigia, monkeypatch):
    mundo = _Mundo(pid=None)
    mundo.instalar(monkeypatch)
    posto = mod.Posto(login="c", fonte=lambda: (4242, 99))
    vigia._postos["c"] = posto
    monkeypatch.setattr(mod, "avaliar_saude",
                        lambda *a, **k: (DcReason.PROCESS_GONE, None))
    vigia._uma_volta()
    assert mundo.mortos == [4242]
    assert vigia.queda_anunciada("c")[0] == "processo"


def test_o_anuncio_vem_ANTES_do_kill(vigia, monkeypatch):
    """Matar DESBLOQUEIA a thread do bot na mesma hora.

    Se o anúncio saísse depois, ela acordaria, veria só "processo sumiu" e o
    Histórico de Quedas registraria o efeito no lugar da causa.
    """
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)
    visto: list = []
    monkeypatch.setattr(mod, "kill_client",
                        lambda pid, *a, **k: visto.append(
                            vigia.queda_anunciada("conta1")) or True)
    _por(vigia, mundo)
    for _ in range(mod.STRIKES_PARA_JANELA_TRAVADA):
        vigia._uma_volta()
    assert visto and visto[0] is not None, (
        "o kill aconteceu antes do anúncio — o motivo verdadeiro se perde")


def test_conta_sem_janela_nao_e_queda(vigia, monkeypatch):
    """É o estado normal entre sessões: o supervisor soltou, ou está abrindo."""
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)
    mod_posto = mod.Posto(login="c", fonte=lambda: (None, None))
    vigia._postos["c"] = mod_posto
    for _ in range(10):
        vigia._uma_volta()
    assert mundo.mortos == []
    assert vigia.queda_anunciada("c") is None


def test_o_anuncio_se_apaga_sozinho_quando_a_conta_volta_noutro_processo(
        vigia, monkeypatch):
    """Anúncio não consumido derrubaria a sessão NOVA no primeiro tick."""
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)
    _por(vigia, mundo)
    for _ in range(mod.STRIKES_PARA_JANELA_TRAVADA):
        vigia._uma_volta()
    assert vigia.queda_anunciada("conta1") is not None

    mundo.pid = 777           # relogin: processo novo
    mundo.responde = True
    vigia._uma_volta()
    assert vigia.queda_anunciada("conta1") is None


def test_uma_conta_com_defeito_nao_cega_as_outras(vigia, monkeypatch):
    """A volta é por conta: exceção numa não pode calar o vigia inteiro."""
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)

    def _explode():
        raise RuntimeError("fonte quebrada")

    vigia._postos["ruim"] = mod.Posto(login="ruim", fonte=_explode)
    _por(vigia, mundo, login="boa")
    for _ in range(mod.STRIKES_PARA_JANELA_TRAVADA):
        vigia._uma_volta()
    assert mundo.mortos == [4242]


def test_o_interruptor_desliga_a_morte_por_travamento(vigia, monkeypatch):
    """A convenção do projeto: caminho fora de uso vira `X = False`, não some.

    É o único critério de morte que mata janela que o Windows ainda considera
    viva -- a volta atrás tem que ser uma linha.
    """
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)
    monkeypatch.setattr(mod, "MATAR_JANELA_TRAVADA", False)
    _por(vigia, mundo)
    for _ in range(mod.STRIKES_PARA_JANELA_TRAVADA + 3):
        vigia._uma_volta()
    assert mundo.mortos == []


# ===========================================================================
# A LIGAÇÃO COM O RELOGIN -- o vigia não religa; ele devolve a conta ao caminho
# ===========================================================================


def test_a_thread_do_bot_levanta_Disconnected_ao_ler_o_anuncio():
    """`BotContext.check_watchdog` é a porta, e ela vale para TODA conta.

    Inclusive as que não têm `Watchdog` configurado (tudo que não é BC) -- elas
    saíam por `return` na primeira linha e nunca percebiam queda por aqui.
    """
    from blazesbot.bot import context as mod_ctx

    fonte = inspect.getsource(mod_ctx.BotContext.check_watchdog)
    assert "cobrar_a_queda" in fonte
    assert fonte.index("cobrar_a_queda") < fonte.index("self._watchdog is None"), (
        "o vigia é consultado depois do `return` das contas sem watchdog — "
        "elas voltam a ficar cegas")


def test_a_espera_do_BACKOFF_NAO_levanta_Disconnected():
    """O defeito de 09/09/2026, e ele matava a thread da conta.

    As quatro chamadas de backoff do `run()` estão DENTRO de blocos `except`.
    Exceção levantada ali não é pega pelos `except` do mesmo `try`: sobe para o
    `except BaseException` de baixo, que ENCERRA o supervisor. Em campo:

        ClientClosed: o cliente foi encerrado pelo aviso de conexão interrompida
        During handling of the above exception, another exception occurred:
        Disconnected: aviso de conexão interrompida na tela
        PARANDO por falha inesperada

    Nada se perdeu com a remoção: durante o backoff a conta não tem cliente
    (`_release` zerou pid e hwnd), então o único anúncio possível ali é o velho.
    """
    from blazesbot.bot import supervisor as mod_sup

    corpo = inspect.getsource(mod_sup.AccountSupervisor._sleep_interruptible)
    arvore = ast.parse(textwrap.dedent(corpo))
    levantados = {ast.unparse(no.exc.func) if isinstance(no.exc, ast.Call)
                  else ast.unparse(no.exc)
                  for no in ast.walk(arvore)
                  if isinstance(no, ast.Raise) and no.exc is not None}
    assert "Disconnected" not in levantados, (
        "a espera do backoff voltou a levantar Disconnected de dentro de um "
        "`except` — isso mata a thread da conta")
    assert "StopRequested" in levantados, "a parada do usuário continua valendo"


def test_o_anuncio_morre_junto_com_o_controle_da_janela():
    """`_release` é o ponto por onde os CINCO caminhos de morte passam.

    Foi por faltar isto que a queda tratada pelo LOGIN (`ClientClosed`) deixava
    o anúncio de pé -- e um anúncio vivo derruba a sessão SEGUINTE no primeiro
    `tick`, antes mesmo de ela ter janela.
    """
    from blazesbot.bot import supervisor as mod_sup

    fonte = inspect.getsource(mod_sup.AccountSupervisor._release)
    assert "sentinela.limpar(" in fonte, (
        "soltar o controle não apaga mais o anúncio — relogin em laço")


def test_soltar_o_controle_apaga_o_anuncio_de_verdade():
    """O mesmo, no comportamento: dublê mínimo, `_release` real."""
    from blazesbot.bot import supervisor as mod_sup

    sup = object.__new__(mod_sup.AccountSupervisor)
    sup.pid, sup.hwnd = None, None
    sup.account = type("_Conta", (), {"login": "conta-que-caiu"})()

    posto = mod.SENTINELA.vigiar("conta-que-caiu", fonte=lambda: (None, None))
    try:
        posto.queda = ("conexao", None, "aviso de conexão interrompida na tela")
        mod_sup.AccountSupervisor._release(sup)
        assert mod.SENTINELA.queda_anunciada("conta-que-caiu") is None
    finally:
        mod.SENTINELA.esquecer("conta-que-caiu")


def test_o_supervisor_registra_a_conta_para_a_EXECUCAO_e_nao_para_a_sessao():
    """A conta passa o tempo ruim FORA de uma sessão -- backoff, login, ociosa.

    Registrar em `_run_session` deixaria justamente esses trechos sem vigia.
    """
    from blazesbot.bot import supervisor as mod_sup

    assert "sentinela.vigiar(" in inspect.getsource(mod_sup.AccountSupervisor.run)
    assert "sentinela.vigiar(" not in inspect.getsource(
        mod_sup.AccountSupervisor._run_session)
    assert "sentinela.esquecer(" in inspect.getsource(mod_sup.AccountSupervisor.run), (
        "sem sair da vigilância, o vigia mataria o cliente que o usuário "
        "acabou de assumir na mão")


def test_o_kill_e_impiedoso_e_nao_pede_educadamente():
    """Cinco segundos de cerimônia com processo morto é um quarto do orçamento."""
    from blazesbot.bot import watchdog as mod_wd

    fonte = inspect.getsource(mod_wd.kill_client)
    assert "taskkill" in fonte

    # LÊ O AST, NÃO O TEXTO -- o docstring EXPLICA o `terminate()` que saiu, e
    # a explicação é justamente o que não pode se perder. Mesma lição de
    # `tests/test_saude_em_todo_ecossistema.py`: comentário citando não conta.
    chamados = {no.func.attr
                for no in ast.walk(ast.parse(textwrap.dedent(fonte)))
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)}
    assert "kill" in chamados
    assert "terminate" not in chamados, (
        "voltou o pedido educado — ele é gasto puro contra cliente travado")


def test_a_thread_e_daemon_e_uma_so():
    """Uma thread por processo, e ela não pode segurar o encerramento do bot."""
    v = mod.Vigia(cadencia=0.05)
    try:
        v.ligar()
        v.ligar()          # idempotente
        time.sleep(0.15)
        vivas = [t for t in threading.enumerate() if t.name == "vigia-global"]
        assert len(vivas) == 1
        assert vivas[0].daemon
    finally:
        v.desligar(esperar=1.0)


def test_o_laco_de_vida_SOBREVIVE_a_queda_tratada_pelo_login(monkeypatch):
    """O defeito de campo, ponta a ponta -- 09/09/2026, 00:56.

    O login viu o aviso de conexão interrompida, encerrou o cliente e levantou
    `ClientClosed`. O vigia tinha visto o MESMO aviso e deixado o anúncio de pé.
    O `except ClientClosed` chamou o backoff, o backoff levantou `Disconnected`
    de dentro do `except`, e a thread da conta morreu com "PARANDO por falha
    inesperada" -- a conta ficou fora do ar até alguém olhar.

    O teste dirige o `run()` DE VERDADE: uma sessão que morre por `ClientClosed`
    com anúncio vivo, e depois uma parada limpa. Sobreviver é chegar na parada.
    """
    from blazesbot.bot import supervisor as mod_sup
    from blazesbot.bot.login import ClientClosed

    monkeypatch.setattr(mod_sup.instrumentacao, "instrumentar_tudo", lambda: None)
    monkeypatch.setattr(mod_sup.cronometro_mod, "ligar", lambda: None)
    monkeypatch.setattr(mod_sup.cronometro_mod, "marcar_a_conta", lambda _: None)

    sup = object.__new__(mod_sup.AccountSupervisor)
    sup.account = type("_Conta", (), {"login": "conta-de-campo"})()
    sup.config = type("_Cfg", (), {"relogin_backoff_cap": 300})()
    sup.log = logging.getLogger("teste.vigia")
    sup.on_status = None
    sup.stop_event = threading.Event()
    sup.pid, sup.hwnd = 4242, 99
    sup.tentativas_de_login = 0
    sup.relogin_count = 0
    sup.total_runs = 0
    sup.max_runs = None

    falas: list[str] = []
    monkeypatch.setattr(type(sup), "_status",
                        lambda self, msg: falas.append(msg))
    monkeypatch.setattr(type(sup), "_teardown", lambda self: None)
    monkeypatch.setattr(type(sup), "_sleep_interruptible",
                        mod_sup.AccountSupervisor._sleep_interruptible)

    sessoes = []

    def _sessao(self):
        sessoes.append(1)
        if len(sessoes) == 1:
            # O VIGIA VIU O MESMO AVISO e anunciou -- é a peça que envenenava o
            # backoff. Anunciado AQUI e não antes do `run()`: o próprio `run()`
            # registra o posto, e um anúncio posto antes seria varrido por esse
            # registro (foi o que fez a primeira versão deste teste passar
            # mesmo com o defeito de pé).
            mod.SENTINELA._postos["conta-de-campo"].queda = (
                "conexao", None, "aviso de conexão interrompida na tela")
            raise ClientClosed(
                "o cliente foi encerrado pelo aviso de conexão interrompida")
        self.stop_event.set()
        raise mod_sup.StopRequested()

    monkeypatch.setattr(type(sup), "_run_session", _sessao)
    # Backoff curto, e NÃO zero: com zero o `while` de `_sleep_interruptible`
    # não dá uma volta sequer, e o teste passaria mesmo com o defeito de pé --
    # foi o que aconteceu na primeira versão dele.
    monkeypatch.setattr(mod_sup, "backoff_delay", lambda *a, **k: 0.3)

    try:
        sup.run()
    finally:
        mod.SENTINELA.esquecer("conta-de-campo")

    assert not any("falha inesperada" in f for f in falas), (
        "a thread da conta morreu de novo — exceção levantada de dentro de um "
        f"`except`. Falas: {falas}")
    assert len(sessoes) == 2, (
        "o laço não chegou à segunda sessão: a conta ficaria fora do ar")


# ===========================================================================
# DURANTE O LOGIN O VIGIA SÓ RECONHECE FATO DO SISTEMA -- 09/09/2026
# ===========================================================================
#
# Laço de relogin a cada 19 s na conta `blazesgamer`: dois segundos depois de
# "Servidor confirmado como selecionado", o vigia decretava "aviso de conexão
# interrompida na tela" e matava o cliente que estava ENTRANDO NA FILA.
#
# O template do vigia é UM só, `state_conn_prefix.png`, que casa com a palavra
# "Connection" -- e nas telas de login existe uma família de caixas que começam
# com ela, desenhadas no MESMO centro. Medido em 18/08/2026 e registrado em
# `login_states.py`: "Connection failed" = 0.835, "Connecting to the server" =
# 0.787. O `LoginDetector` convive com isso porque tem ESCADA ORDENADA e deixa o
# genérico opinar por último. O vigia usa o genérico sozinho.


def test_o_aviso_na_tela_NAO_mata_enquanto_o_login_esta_no_comando(
        vigia, monkeypatch):
    mundo = _Mundo(aviso="quadro-com-a-caixa")
    mundo.instalar(monkeypatch)
    posto = _por(vigia, mundo)
    posto.em_sessao = lambda: False

    for _ in range(10):
        vigia._uma_volta()
    assert mundo.mortos == [], (
        "o vigia matou o cliente durante o login — é o laço de relogin de "
        "09/09/2026 de volta")
    assert vigia.queda_anunciada("conta1") is None


def test_o_travamento_NAO_mata_durante_o_login(vigia, monkeypatch):
    """A FILA DE LOGIN passa de três horas, e não há medição de como o cliente
    bombeia mensagens enquanto espera nela. Matar cliente na fila é o dano mais
    caro que este bot sabe causar."""
    mundo = _Mundo(responde=False)
    mundo.instalar(monkeypatch)
    posto = _por(vigia, mundo)
    posto.em_sessao = lambda: False

    for _ in range(mod.STRIKES_PARA_JANELA_TRAVADA + 5):
        vigia._uma_volta()
    assert mundo.mortos == []


def test_mas_FATO_DO_SISTEMA_continua_valendo_no_login(vigia, monkeypatch):
    """Processo sumido não é leitura de tela: é fato, e não admite interpretação."""
    mundo = _Mundo()
    mundo.instalar(monkeypatch)
    monkeypatch.setattr(mod, "avaliar_saude",
                        lambda *a, **k: (DcReason.PROCESS_GONE, None))
    posto = _por(vigia, mundo)
    posto.em_sessao = lambda: False

    vigia._uma_volta()
    assert mundo.mortos == [4242], (
        "a suspensão do login engoliu até o fato do sistema — a conta ficaria "
        "presa num processo morto")


def test_o_juizo_volta_QUANDO_o_login_conclui(vigia, monkeypatch):
    """E volta no ponto honesto: o mesmo em que o backoff zera."""
    mundo = _Mundo(aviso="quadro-com-a-caixa")
    mundo.instalar(monkeypatch)
    posto = _por(vigia, mundo)
    logando = [True]
    posto.em_sessao = lambda: not logando[0]

    vigia._uma_volta()
    assert mundo.mortos == []
    logando[0] = False
    vigia._uma_volta()
    assert mundo.mortos == [4242]
    assert vigia.queda_anunciada("conta1")[0] == "conexao"


def test_o_supervisor_diz_ao_vigia_quando_esta_logando():
    """A trava é do supervisor: só ele sabe se `login.run()` está no comando."""
    from blazesbot.bot import supervisor as mod_sup

    assert "em_sessao=" in inspect.getsource(mod_sup.AccountSupervisor.run)
    sessao = inspect.getsource(mod_sup.AccountSupervisor._run_session)
    assert "self._login_em_curso = True" in sessao, (
        "a sessão não marca mais que está logando — o vigia volta a opinar "
        "sobre a tela de login")
    assert "self._login_em_curso = False" in sessao, (
        "o vigia nunca mais voltaria a olhar a tela: a queda em jogo ficaria "
        "sem o sinal principal")
    # O ponto de virada é o MESMO do backoff -- o único sinal honesto de que o
    # login concluiu, e ele serve aos dois caminhos (janela adotada e login
    # inteiro).
    assert (sessao.index("self.tentativas_de_login = 0")
            < sessao.index("self._login_em_curso = False")
            < sessao.index("Logado como")), (
        "a virada saiu do ponto em que o login CONCLUI")


def test_o_vigia_vem_DE_FABRICA_sem_ler_a_tela():
    """48 decretos na primeira noite, todos por leitura de tela, todos errados.

    O aviso "Connection interrupted" tem DOIS leitores que já funcionavam: o
    watchdog inline (na thread da conta, a cada 10 s) e o `LoginDetector`. O
    vigia foi o terceiro, e não somou cobertura -- somou uma chance de errar
    sozinho, num contexto onde o limiar dele nunca foi medido.

    O que faltava (a conta em LIMBO) é thread parada dentro de um `SendMessageW`
    síncrono, e isso os outros três sinais respondem sem ver a tela.
    """
    assert mod.OLHAR_A_TELA is False, (
        "o vigia voltou a ler a tela por padrão — sem antes medir o "
        "`state_conn_prefix` contra as telas de login com a região travada")


def test_desligado_ele_nao_MATA_nem_CAPTURA(monkeypatch):
    """Não basta não matar: com o interruptor desligado ele nem fotografa.

    A captura é o degrau caro e o único que disputa GDI com a thread da conta.
    """
    v = mod.Vigia(cadencia=999.0)
    try:
        mundo = _Mundo(aviso="quadro-com-a-caixa")
        mundo.instalar(monkeypatch)
        monkeypatch.setattr(mod, "OLHAR_A_TELA", False)
        fotos = []
        monkeypatch.setattr(mod, "quadro_com_aviso_de_conexao",
                            lambda *a, **k: fotos.append(1) or mundo.aviso)
        _por(v, mundo)
        for _ in range(5):
            v._uma_volta()
        assert mundo.mortos == []
        assert fotos == [], "capturou mesmo com o interruptor desligado"
    finally:
        v.desligar()
