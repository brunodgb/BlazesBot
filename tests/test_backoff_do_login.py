"""O relogin nunca desiste — e o backoff não pode virar castigo permanente.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

O laço de sessão sempre foi infinito e isso está certo: conta ativa tem que
estar logada, custe o tempo que custar. O que estava errado era o BACKOFF.

`attempt` era uma variável local de `run()`, incrementada em cada `except` e
zerada num `else:` do `try` que NUNCA EXECUTAVA -- o corpo do `try` termina em
`return`, então o `else` do `try/except` é inalcançável, e aquele era o único
`= 0` depois da inicialização.

Consequência medida no código: o contador só crescia pela vida inteira da
thread. `backoff_delay(attempt, 300)` é `min(2 ** (attempt - 1), 300)`, então a
partir da nona queda a conta passava a esperar OS 300 s DO TETO antes de cada
relogin -- para sempre, mesmo com horas de sessão saudável entre uma queda e
outra. Uma conta que caiu de madrugada acordava o dia inteiro esperando cinco
minutos por relogin.

O sinal honesto de que o backoff cumpriu o papel é o LOGIN TER CONCLUÍDO. É lá
que ele zera agora.

=========================================================================
E A ÚNICA EXCEÇÃO A "NUNCA DESISTIR"
=========================================================================

Senha errada. Mais tentativas não resolvem, e cada recusa é uma tentativa
registrada NO SERVIDOR -- o caminho para a conta bloqueada. Aqui o custo de
insistir não é tempo, é a conta. Então a conta é DESATIVADA e isso é gravado:
ela desmarcada na interface É o aviso, ela não tenta mais sozinha na execução
seguinte, e reativar é o mesmo clique com que se confere a senha.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot import login as mod_login
from blazesbot.bot import supervisor as mod_supervisor
from blazesbot.bot.watchdog import backoff_delay

# ---------------------------------------------------------------------------
# O BACKOFF
# ---------------------------------------------------------------------------

def test_backoff_cresce_e_para_no_teto():
    assert backoff_delay(1, 300) == 1.0
    assert backoff_delay(2, 300) == 2.0
    assert backoff_delay(4, 300) == 8.0
    assert backoff_delay(9, 300) == 256.0
    assert backoff_delay(10, 300) == 300.0
    assert backoff_delay(99, 300) == 300.0


def test_o_contador_de_login_e_estado_do_supervisor():
    """Como local de `run()` ele não tinha como ser zerado de fora.

    E era exatamente isso: quem sabe que o login deu certo é `_run_session`, e
    ele não alcançava uma variável local do método de cima.
    """
    assert "tentativas_de_login" in inspect.getsource(
        mod_supervisor.AccountSupervisor.__init__)


def test_run_nao_tem_mais_o_else_inalcancavel():
    """O `else:` de um `try` cujo corpo termina em `return` nunca executa.

    Era ali que o contador zerava — ou seja, não zerava nunca. Este teste
    reprova a volta do padrão inteiro, não só daquela linha.
    """
    fonte = textwrap.dedent(inspect.getsource(mod_supervisor.AccountSupervisor.run))
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, ast.Try) and no.orelse:
            corpo_termina_em_return = isinstance(no.body[-1], ast.Return)
            assert not corpo_termina_em_return, (
                "voltou um `try/except/else` cujo corpo termina em `return`: "
                "o `else` é código morto e o que estiver nele nunca roda")


def test_o_contador_zera_quando_o_login_CONCLUI():
    """No `_run_session`, e nos dois caminhos: janela adotada e login inteiro."""
    fonte = inspect.getsource(mod_supervisor.AccountSupervisor._run_session)
    assert "self.tentativas_de_login = 0" in fonte, (
        "o contador deixou de zerar no login concluído; o backoff volta a "
        "crescer para sempre")


def test_o_backoff_recomeca_do_zero_depois_de_uma_sessao_que_viveu(monkeypatch):
    """O comportamento, não só a estrutura.

    Simula o laço de vida: três quedas seguidas (o backoff escala), depois uma
    sessão que LOGOU (zera, como `_run_session` faz) e caiu de novo -- e a
    espera tem que voltar a ser de um segundo, não os 300 s do teto.
    """
    sup = object.__new__(mod_supervisor.AccountSupervisor)
    sup.tentativas_de_login = 0
    esperas: list[float] = []

    # O laço real chama `backoff_delay(self.tentativas_de_login, cap)` em cada
    # `except`; aqui reproduzimos só essa contabilidade.
    def caiu(logou_antes: bool) -> None:
        if logou_antes:
            sup.tentativas_de_login = 0        # o que `_run_session` faz
        sup.tentativas_de_login += 1
        esperas.append(backoff_delay(sup.tentativas_de_login, 300))

    for _ in range(3):
        caiu(logou_antes=False)
    assert esperas == [1.0, 2.0, 4.0]

    caiu(logou_antes=True)
    assert esperas[-1] == 1.0, (
        "uma sessão que logou e depois caiu voltou a herdar o backoff antigo")


# ---------------------------------------------------------------------------
# SENHA ERRADA
# ---------------------------------------------------------------------------

def test_cinco_recusas_no_total():
    """Cinco, e são cinco NO TOTAL, não cinco por ciclo de relogin.

    `credential_errors` nasce zerado a cada `LoginSequence` e o `BadCredentials`
    encerra a conta na primeira vez que o limite estoura. Contar por ciclo
    multiplicaria isso por cada tentativa, e o servidor veria dezenas de senhas
    erradas da mesma conta -- que é justamente o dano que o limite evita.
    """
    assert mod_login.MAX_CREDENTIAL_ERRORS == 5


def test_so_a_TELA_DE_ERRO_conta_uma_recusa():
    """Demora, fila e tela travada não somam aqui — cada uma tem seu caminho.

    Quem incrementa é `_handle_login_error`, e ele só roda quando o detector
    casa a assinatura de `LoginScreen.LOGIN_ERROR`.
    """
    fonte = inspect.getsource(mod_login)
    assert fonte.count("self.credential_errors += 1") == 1, (
        "o contador de recusa passou a subir em mais de um lugar")
    assert "self.credential_errors += 1" in inspect.getsource(
        mod_login.LoginSequence._handle_login_error)
    assert any(
        tela is mod_login.LoginScreen.LOGIN_ERROR
        for tela, _ in __import__(
            "blazesbot.bot.login_states", fromlist=["_SIGNATURES"]
        )._SIGNATURES
    ), "a tela de erro de login saiu das assinaturas do detector"


def test_senha_errada_DESATIVA_a_conta_e_grava():
    """Sem gravar, a execução seguinte queima as mesmas cinco recusas.

    E sem desativar, a thread apenas morria: a conta sumia da execução sem que
    nada na tela dissesse que ela tinha morrido.
    """
    fonte = textwrap.dedent(inspect.getsource(mod_supervisor.AccountSupervisor.run))
    arvore = ast.parse(fonte)

    tratadores = [
        h for no in ast.walk(arvore) if isinstance(no, ast.Try)
        for h in no.handlers
        if h.type is not None and "BadCredentials" in ast.unparse(h.type)
    ]
    assert len(tratadores) == 1, "o tratamento de senha errada sumiu ou duplicou"
    corpo = ast.unparse(ast.Module(body=tratadores[0].body, type_ignores=[]))
    assert "self.account.enabled = False" in corpo, (
        "senha errada parou de desativar a conta")
    assert "self.config.save()" in corpo, (
        "a desativação por senha errada não é mais persistida; na execução "
        "seguinte a conta volta a queimar recusas no servidor")


def test_conta_desativada_nao_volta_a_subir():
    """`sync_accounts` alinha os supervisores com `enabled_accounts()`.

    É o que faz `enabled = False` significar "não tenta mais" de verdade, em vez
    de só encerrar a thread atual.
    """
    fonte = inspect.getsource(mod_supervisor.BotManager.sync_accounts)
    assert "enabled_accounts()" in fonte

def test_o_TETO_do_backoff_e_120s_e_a_escada_chega_la_em_oito_falhas():
    """Decisão do usuário em 22/09/2026, e o porquê importa mais que o número.

    *"Quanto mais tentativas melhor, e ficar parado pode perder uma janela
    importante de entrar no servidor."*

    O backoff NÃO foi removido: o caso que ele protege é real -- cliente que
    abre quebrado faria o bot relançar em laço fechado, e cada tentativa
    recusada é registrada NO SERVIDOR (o mesmo motivo de
    `MAX_CREDENTIAL_ERRORS`). O que mudou é o preço do pior caso: a janela
    perdida cai de 5 min para 2.

    E a escada só chega lá em falhas CONSECUTIVAS -- um login que conclui zera
    o contador (ver `_run_session`).
    """
    from blazesbot.config import BotConfig

    cap = BotConfig().relogin_backoff_cap
    assert cap == 120, (
        "o teto do backoff mudou; se foi de propósito, atualize aqui com o "
        "porquê -- ele é o tempo máximo que uma conta fica parada sem tentar")

    escada = [backoff_delay(i, cap) for i in range(1, 9)]
    assert escada == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 120.0]
    assert sum(escada) < 300, (
        "oito falhas seguidas passaram a custar mais de 5 minutos somados")

