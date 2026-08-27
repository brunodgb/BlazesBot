"""As telas modais do login, medidas contra CAPTURAS REAIS do cliente.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

Medido em 18/08/2026, com as quatro capturas em `data/templates/entrada/`:

    login-conn-failed.png   state_conn_prefix = 0.835   <- casava, e era o 1o
                            state_conn_failed = 0.994   <- certo, mas era o 4o

`state_conn_prefix` casa com a palavra "Connection", comum a "Connection
interrupted" E a "Connection failed". Com ele em primeiro na `_SIGNATURES`, a
tela de FALHA DE CONEXÃO era classificada como CONEXÃO INTERROMPIDA.

E o estrago não é o rótulo: `_handle_conn_interrupted` clica no deslocamento do
botão **Ok**, mas essa caixa tem **Cancel**, em outro lugar. O clique cai no
vazio e o login fica parado indefinidamente -- o sintoma que o usuário relatou
como "não reconhece o erro".

A tela "Connecting to the server" marcava 0.787 no mesmo template genérico, a
**0.013** do limiar: estava a um fio do mesmo desfecho.

Por isso a regra travada aqui é ORDEM POR ESPECIFICIDADE: o template que casa
por prefixo tem que ser o ÚLTIMO a opinar entre os modais.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from blazesbot.bot.login_states import _SIGNATURES, THRESHOLD, LoginScreen

ENTRADA = Path("data") / "templates" / "entrada"
TEMPLATES = Path("data") / "templates"

# captura real -> tela que ela DEVE produzir
CASOS = [
    ("login-conn-failed.png", LoginScreen.CONN_FAILED),
    ("login-connecting.png", LoginScreen.CONNECTING),
    ("login-ip-address.png", LoginScreen.SERVER_IP),
    ("queda-app.png", LoginScreen.CONN_INTERRUPTED),
]


def _classificar(imagem):
    """A MESMA varredura do detector: primeira assinatura que casar vence."""
    for tela, nomes in _SIGNATURES:
        for nome in nomes:
            tpl = cv2.imread(str(TEMPLATES / nome), cv2.IMREAD_GRAYSCALE)
            if tpl is None:
                continue
            if (tpl.shape[0] > imagem.shape[0]
                    or tpl.shape[1] > imagem.shape[1]):
                continue
            _, nota, _, _ = cv2.minMaxLoc(
                cv2.matchTemplate(imagem, tpl, cv2.TM_CCOEFF_NORMED))
            if nota >= THRESHOLD:
                return tela, nome, nota
    return None, None, 0.0


@pytest.mark.parametrize("arquivo,esperada", CASOS)
def test_a_captura_real_produz_a_tela_certa(arquivo, esperada):
    caminho = ENTRADA / arquivo
    if not caminho.is_file():
        pytest.skip(f"{arquivo} não está no repo")
    img = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
    tela, nome, nota = _classificar(img)
    assert tela is esperada, (
        f"{arquivo} foi classificada como {tela} por '{nome}' ({nota:.3f}); "
        f"o certo é {esperada}. Se voltou a ser CONN_INTERRUPTED numa tela que "
        f"não é, o template de prefixo subiu na ordem outra vez.")


def test_o_template_de_PREFIXO_e_o_ultimo_dos_modais():
    """A regra em si, e não só o efeito dela.

    Um template que casa por PREFIXO opina sobre telas que não são dele. Ele
    pode existir -- cobre as duas variantes de "Connection interrupted." -- mas
    tem que ser o último a falar entre os avisos modais.
    """
    ordem = [tela for tela, _ in _SIGNATURES]
    i_prefixo = ordem.index(LoginScreen.CONN_INTERRUPTED)
    for especifica in (LoginScreen.CONN_FAILED, LoginScreen.CONNECTING,
                       LoginScreen.LOGIN_ERROR, LoginScreen.LOGIN_BUSY):
        assert ordem.index(especifica) < i_prefixo, (
            f"{especifica} é verificada DEPOIS do prefixo genérico — a tela "
            f"dela vai ser confundida com 'conexão interrompida'")


def test_DENTE_com_o_prefixo_em_primeiro_a_falha_de_conexao_se_disfarca():
    """Reintroduz o defeito e exige que ele seja reproduzível.

    Se um dia este teste parar de reprovar com o prefixo em primeiro, é porque
    o template genérico deixou de casar na tela errada — e aí a regra de ordem
    perdeu o motivo. Melhor descobrir aqui do que num login parado a noite toda.
    """
    caminho = ENTRADA / "login-conn-failed.png"
    if not caminho.is_file():
        pytest.skip("captura de referência não está no repo")
    img = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
    prefixo = cv2.imread(str(TEMPLATES / "state_conn_prefix.png"),
                         cv2.IMREAD_GRAYSCALE)
    _, nota, _, _ = cv2.minMaxLoc(
        cv2.matchTemplate(img, prefixo, cv2.TM_CCOEFF_NORMED))
    assert nota >= THRESHOLD, (
        f"o prefixo marca {nota:.3f} na tela de FALHA e não casa mais; a regra "
        f"de ordem deixou de ser necessária — reveja o motivo antes de mexer")


def test_o_vao_de_cada_template_especifico():
    """Cada template só pode casar na PRÓPRIA tela.

    É o que separa "ordem certa" de "sorte": com vão apertado, uma renderização
    um pouco diferente troca a classificação de novo.
    """
    especificos = {
        "state_conn_failed.png": "login-conn-failed.png",
        "state_connecting.png": "login-connecting.png",
        "state_acquiring_ip.png": "login-ip-address.png",
    }
    for nome, dono in especificos.items():
        tpl = cv2.imread(str(TEMPLATES / nome), cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            pytest.skip(f"{nome} não está no repo")
        notas = {}
        for arquivo, _ in CASOS:
            caminho = ENTRADA / arquivo
            if not caminho.is_file():
                continue
            img = cv2.imread(str(caminho), cv2.IMREAD_GRAYSCALE)
            _, nota, _, _ = cv2.minMaxLoc(
                cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED))
            notas[arquivo] = nota
        if dono not in notas:
            continue
        alheias = max(v for k, v in notas.items() if k != dono)
        assert notas[dono] >= 0.95, (
            f"{nome} marca só {notas[dono]:.3f} na própria tela")
        assert notas[dono] - alheias > 0.25, (
            f"{nome}: vão de apenas {notas[dono] - alheias:.3f} entre a tela "
            f"dele e a mais parecida — apertado demais para confiar")
