"""O CONTADOR DE ERRO DE CREDENCIAL ZERA QUANDO A AUTENTICAÇÃO DÁ CERTO.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

Medido em 01/09/2026, numa `LoginSequence` de 796 s na conta `blazesofgamer`,
com o jogo no bug de "Conexão interrompida" que o usuário relatou durar semanas:

    lista de servidores alcançada (= autenticou) ... 85
    conexão interrompida ........................... 85
    tela de erro de usuário/senha .................... 5

E a ordem em que cada erro apareceu:

     5 lista de servidores -> 1 erro de usuário/senha
    13 lista de servidores -> 1 erro de usuário/senha
    17 lista de servidores -> 1 erro de usuário/senha
    11 lista de servidores -> 1 erro de usuário/senha
    39 lista de servidores -> 1 erro de usuário/senha

Cada erro veio DEPOIS de dezenas de autenticações bem-sucedidas -- e o servidor
só mostra a lista de servidores depois de ACEITAR usuário e senha. A senha estava
certa, e o bot concluiu `BadCredentials`, que em `supervisor.py` faz
`account.enabled = False` E GRAVA: a conta sai de rotação com a senha correta e
só volta com intervenção manual.

O que estes testes travam:

  * cinco recusas SEGUIDAS continuam desativando a conta -- o limite existe
    porque cada recusa real é uma tentativa registrada no servidor, e o custo de
    insistir é a conta;
  * erro ESPORÁDICO entre autenticações bem-sucedidas NÃO desativa mais;
  * o reset fica FORA do `if` da fase, porque `_do_credentials` chuta
    `Phase.SERVER` sem prova e o reset seria pulado justamente nos ciclos em que
    o palpite acerta.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from blazesbot.bot import login as lg
from blazesbot.bot.login_states import LoginScreen

# ===========================================================================
# UMA SEQUÊNCIA DE LOGIN SEM ABRIR PROCESSO NENHUM
# ===========================================================================

def _sequencia():
    seq = lg.LoginSequence.__new__(lg.LoginSequence)
    seq.credential_errors = 0
    seq.cliques: list[tuple[int, int]] = []
    seq.fases: list[object] = []
    seq.account = SimpleNamespace(login="blazesofgamer")
    seq.coords = SimpleNamespace(login_error_close=(10, 20))
    seq.log = SimpleNamespace(info=lambda *a, **k: None,
                              debug=lambda *a, **k: None,
                              warning=lambda *a, **k: None,
                              error=lambda *a, **k: None)
    # o detector diz que o aviso já fechou, para não entrar no segundo clique
    seq.detector = SimpleNamespace(
        detect=lambda: SimpleNamespace(screen=LoginScreen.LOGIN_SCREEN))
    seq._click = lambda p: seq.cliques.append(p)
    seq._set_phase = lambda f: seq.fases.append(f)
    return seq


@pytest.fixture(autouse=True)
def _sem_dormir(monkeypatch):
    """Nenhum teste desta suíte pode pagar as esperas do login de verdade."""
    monkeypatch.setattr(lg, "sleep", lambda *_a, **_k: None)


def _autenticou(seq):
    """O que a vista da LISTA DE SERVIDORES faz com o contador.

    É o efeito da linha do `SERVER_LIST` no laço principal, e está aqui num
    lugar só para o teste falar da REGRA, não da posição do código -- a posição
    tem teste próprio, por AST, no fim deste arquivo.
    """
    seq.credential_errors = 0


# ===========================================================================
# O LIMITE CONTINUA VALENDO PARA RECUSA DE VERDADE
# ===========================================================================

def test_cinco_recusas_seguidas_ainda_desativam_a_conta():
    """Senha errada nunca alcança a lista de servidores: nada zera."""
    seq = _sequencia()
    for _ in range(lg.MAX_CREDENTIAL_ERRORS - 1):
        seq._handle_login_error(None)
    assert seq.credential_errors == lg.MAX_CREDENTIAL_ERRORS - 1
    with pytest.raises(lg.BadCredentials) as e:
        seq._handle_login_error(None)
    assert "blazesofgamer" in str(e.value)


def test_a_quarta_recusa_seguida_ainda_nao_desativa():
    seq = _sequencia()
    for _ in range(4):
        seq._handle_login_error(None)      # não levanta
    assert seq.credential_errors == 4


# ===========================================================================
# ERRO ESPORÁDICO ENTRE AUTENTICAÇÕES NÃO DESATIVA MAIS
# ===========================================================================

def test_a_sequencia_medida_em_campo_nao_desativa_a_conta():
    """A corrida real: 85 autenticações e 5 erros espalhados entre elas."""
    seq = _sequencia()
    for autenticacoes in (5, 13, 17, 11, 39):
        for _ in range(autenticacoes):
            _autenticou(seq)
        seq._handle_login_error(None)      # o erro esporádico
        assert seq.credential_errors == 1
    # cinco erros no total, e nenhum BadCredentials
    assert seq.credential_errors == 1


def test_um_erro_a_cada_autenticacao_nunca_acumula():
    seq = _sequencia()
    for _ in range(50):
        _autenticou(seq)
        seq._handle_login_error(None)
        assert seq.credential_errors == 1


def test_autenticar_no_meio_de_quatro_recusas_zera_o_acumulado():
    """O caso de fronteira: quatro recusas, uma autenticação, e recomeça."""
    seq = _sequencia()
    for _ in range(4):
        seq._handle_login_error(None)
    assert seq.credential_errors == 4
    _autenticou(seq)
    assert seq.credential_errors == 0
    # e agora aguenta outras quatro sem desativar
    for _ in range(4):
        seq._handle_login_error(None)
    assert seq.credential_errors == 4


# ===========================================================================
# A POSIÇÃO DO RESET, TRAVADA POR AST
# ===========================================================================
#
# Esta é a parte sutil. `_do_credentials` faz `_set_phase(Phase.SERVER)` logo
# depois de clicar em OK, SEM PROVA de que o servidor aceitou. Se o reset ficasse
# dentro do `if self.phase is not Phase.SERVER`, ele seria pulado exatamente nos
# ciclos em que o palpite otimista já acertou a fase -- ou seja, quase sempre, e
# o defeito voltaria calado.

def _no_do_server_list():
    """O nó `if det.screen is LoginScreen.SERVER_LIST:` dentro de `run`."""
    # `getsource` devolve o metodo com a indentacao da CLASSE, e o `ast` recusa.
    fonte = textwrap.dedent(inspect.getsource(lg.LoginSequence.run))
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if not isinstance(no, ast.If):
            continue
        teste = ast.unparse(no.test)
        if "SERVER_LIST" in teste and "det.screen" in teste:
            return no
    return None


def test_o_reset_existe_no_ramo_da_lista_de_servidores():
    no = _no_do_server_list()
    assert no is not None, "não achei o ramo `det.screen is ... SERVER_LIST`"
    corpo = "\n".join(ast.unparse(x) for x in no.body)
    assert "credential_errors = 0" in corpo, (
        "o contador de credenciais tem de zerar quando o detector VÊ a lista "
        "de servidores -- é a prova de que a senha está certa")


def test_o_reset_esta_FORA_do_if_da_fase():
    """Dentro do `if self.phase is not Phase.SERVER` ele seria pulado."""
    no = _no_do_server_list()
    assert no is not None
    diretos = [x for x in no.body if not isinstance(x, ast.If)]
    texto_direto = "\n".join(ast.unparse(x) for x in diretos)
    assert "credential_errors = 0" in texto_direto, (
        "o reset está aninhado num `if` -- `_do_credentials` já chuta "
        "Phase.SERVER sem prova, então o reset seria pulado justamente nos "
        "ciclos em que o palpite acerta a fase"
    )


def test_o_contador_zera_tambem_no_inicio_de_cada_sequencia():
    """O reset do `__init__` continua existindo: uma coisa não substitui a
    outra. Sequência nova nasce sem herdar erro da anterior."""
    fonte = Path("blazesbot/bot/login.py").read_text(encoding="utf-8")
    assert "self.credential_errors = 0" in fonte
    assert fonte.count("self.credential_errors = 0") >= 2, (
        "esperado dois resets: o do `__init__` e o do `SERVER_LIST`")
