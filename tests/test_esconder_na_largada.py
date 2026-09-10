"""O F12 é PRESO na largada de cada cave, e nunca solto.

=========================================================================
A REGRA
=========================================================================

Usuário, 10/09/2026:

> *"a regra é apenas dar um key_down no F12 apenas, sem o key_up... ao ativar,
> no momento que eu clicar em BC ou HH, antes de começar a andar já faz isso"*

E, sobre o que existia antes: *"o truque do F12 (segurar a tecla, abrir o chat
com Enter, soltar, fechar o chat) só funciona para o usuário, não precisa ser
feito pelo bot, então pode remover esse truque que ensinei"*.

=========================================================================
O QUE ESTAVA ERRADO
=========================================================================

O supervisor já prendia a tecla ao PREPARAR O CLIENTE, no login -- e isso está
certo. Mas a cave é ligada depois, às vezes muito depois, e nenhuma das duas
rotinas reafirmava o F12 ao começar.

Pior: o que cada cave fazia era o TRUQUE DO CHAT, que estava desligado por
interruptor desde 19/08/2026. Ou seja, as chamadas do dia 10/09 pela manhã não
faziam nada em produção -- e o truque, se ligado, carregava o risco de deixar o
chat aberto e desviar toda tecla do bot para o campo de texto.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

1. As duas caves prendem o F12 na largada, antes de andar.
2. É KEYDOWN sem KEYUP -- e a tecla entra na lista de intocáveis, para que
   nenhum `segurado(...)` a solte depois.
3. Reafirmar é o comportamento correto, e acontece também antes de entrar.
4. O truque do chat não voltou.

Ver `docs/decisoes/hh.md` §28.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot.bc.routine import BossRushRoutine
from blazesbot.bot.esconder import EsconderOsJogadores
from blazesbot.bot.hh.routine import HHRoutine
from blazesbot.core import esconder_jogadores as nucleo

# ===========================================================================
# 1. As duas caves prendem na largada
# ===========================================================================


def test_as_DUAS_caves_prendem_o_F12_na_largada():
    for rotina in (BossRushRoutine, HHRoutine):
        fonte = inspect.getsource(rotina.run)
        assert "esconder.prender(" in fonte, (
            f"{rotina.__name__}.run não prende o F12 na largada")


def test_a_largada_prende_ANTES_do_laco_de_estados():
    """De nada serve esconder depois de já ter clicado em NPC.

    PELO AST, e não por posição de texto: a docstring do `run` das duas caves
    fala de `farming`, e a busca textual encontrava a explicação antes do
    código.
    """
    for rotina in (BossRushRoutine, HHRoutine):
        arvore = ast.parse(textwrap.dedent(inspect.getsource(rotina.run)))
        metodo = arvore.body[0]

        prende = [n.lineno for n in ast.walk(metodo)
                  if isinstance(n, ast.Call)
                  and getattr(n.func, "attr", "") == "prender"]
        lacos = [n.lineno for n in ast.walk(metodo)
                 if isinstance(n, (ast.While, ast.For))]

        assert prende, f"{rotina.__name__}.run não prende o F12"
        assert lacos, f"{rotina.__name__}.run deixou de ter laço de estados"
        assert min(prende) < min(lacos), (
            f"{rotina.__name__} entra no laço de estados antes de prender")


def test_o_supervisor_continua_prendendo_ao_preparar_o_cliente():
    """A largada REAFIRMA; não substitui o que já acontece no login."""
    from blazesbot.bot import supervisor

    fonte = inspect.getsource(supervisor)
    assert "prender_a_tecla(" in fonte


# ===========================================================================
# 2. KEYDOWN sem KEYUP
# ===========================================================================


class _Log:
    def __init__(self): self.linhas: list[str] = []
    def info(self, m, *a): self.linhas.append(m % a if a else m)
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass


def _gesto(tecla: str = "F12"):
    g = object.__new__(EsconderOsJogadores)
    presas: list[str] = []

    class _Ctx:
        log = _Log()
        settings = type("S", (), {"keys": type("K", (), {
            "hide_players": tecla})()})()

        @staticmethod
        def segurar_para_sempre(k):
            presas.append(k)
            return True

    g.ctx = _Ctx()
    g.presas = presas
    return g


def test_prender_manda_a_tecla_e_nada_mais():
    g = _gesto()

    assert g.prender("teste") is True
    assert g.presas == ["F12"]
    assert any("PRESA" in linha for linha in g.ctx.log.linhas)


def test_o_gesto_usa_segurar_para_sempre_e_NAO_key_down():
    """`key_down` conta aninhamento e um `key_up` posterior solta.

    `segurar_para_sempre` põe a tecla na lista de intocáveis, e é isso que faz
    "nunca soltar" ser verdade mesmo com um `segurado(...)` terminando depois.
    """
    fonte = inspect.getsource(EsconderOsJogadores.prender)

    assert "segurar_para_sempre" in fonte
    assert "key_down" not in fonte
    assert "key_up" not in fonte


def test_sem_tecla_configurada_devolve_False_e_ninguem_aborta():
    """`False` aqui é "não havia o que fazer", não "deu erro"."""
    g = _gesto(tecla="")
    assert g.prender("teste") is False
    assert g.presas == []

    for rotina in (BossRushRoutine, HHRoutine):
        arvore = ast.parse(textwrap.dedent(inspect.getsource(rotina.run)))
        ramos = [n for n in ast.walk(arvore) if isinstance(n, ast.If)
                 and "prender" in ast.unparse(n.test)]
        assert not ramos, (
            f"{rotina.__name__} passou a decidir algo com a resposta do "
            f"esconder -- e ela não é veredito")


def test_a_tecla_presa_NAO_e_solta_por_um_bloco_segurado():
    """A garantia é do `Input`, e este teste é a costura entre os dois."""
    from blazesbot.core.inputs import Input

    fonte = inspect.getsource(Input.segurar_para_sempre)
    assert "_presas_para_sempre" in fonte
    assert "key_up" in fonte, (
        "a documentação da lista de intocáveis saiu, e é ela que explica por "
        "que um `segurado(...)` não desfaz o que foi preso")


# ===========================================================================
# 3. Reafirmar também antes de entrar
# ===========================================================================


def test_as_duas_caves_REAFIRMAM_antes_de_entrar():
    """Uma tecla fisicamente presa repete sozinha; reenviar imita isso, e é o
    que recupera o estado quando o cliente o perde -- num relogin, por
    exemplo, em que a janela é outra."""
    for rotina in (BossRushRoutine, HHRoutine):
        fonte = inspect.getsource(rotina._do_entrar)
        assert "esconder.prender(" in fonte, (
            f"{rotina.__name__}._do_entrar deixou de reafirmar o F12")


def test_o_BC_NAO_aborta_mais_a_entrada_por_causa_do_esconder():
    """Prender a tecla não abre chat nenhum -- o risco que justificava abortar
    era do truque, e ele saiu."""
    fonte = inspect.getsource(BossRushRoutine._do_entrar)
    assert "o chat ficou aberto" not in fonte


# ===========================================================================
# 4. O truque não voltou
# ===========================================================================


def test_o_truque_do_chat_NAO_EXISTE_mais():
    for nome in ("esconder_jogadores", "Resultado", "TECLA_DO_CHAT",
                 "ATIVADO"):
        assert not hasattr(nucleo, nome), (
            f"o truque do chat voltou: `{nome}` reapareceu em "
            f"core/esconder_jogadores.py")


def test_o_que_SOBROU_no_nucleo():
    """Duas coisas: prender a tecla, e o bloco que segura (hoje desligado)."""
    assert callable(nucleo.prender_a_tecla)
    assert callable(nucleo.segurado)
    assert nucleo.PRENDER_A_TECLA is True


def test_nenhuma_cave_procura_o_chat_aberto():
    """O template `state_chat_aberto.png` existia só para proteger do truque."""
    for rotina in (BossRushRoutine, HHRoutine):
        fonte = inspect.getsource(inspect.getmodule(rotina))
        assert "state_chat_aberto" not in fonte
        assert "chat_aberto" not in fonte


def test_o_modulo_do_gesto_nao_confere_chat():
    fonte = inspect.getsource(inspect.getmodule(EsconderOsJogadores))
    assert "chat_aberto" not in fonte.split('"""')[2], (
        "a conferência do chat voltou ao código do gesto")
