"""O esconder jogadores liga na LARGADA, e em toda cave.

=========================================================================
A REGRA
=========================================================================

Usuário, 10/09/2026:

> *"em HH o esconder personagem tem que ser ativo já quando começa a função,
> pois está aparecendo outros personagens e pode atrapalhar, a função já existe
> e está tudo certo, só deve ser ativo de início, toda cave na verdade tem que
> fazer isso, pois assim garante que outros player não irão atrapalhar de forma
> alguma"*

=========================================================================
O QUE ESTAVA ERRADO, E ERA DIFERENTE EM CADA CAVE
=========================================================================

O truque do F12 (segurar a tecla, abrir o chat com Enter, soltar, fechar o chat)
é o que faz o esconder GRUDAR pela sessão. Antes desta mudança:

* **BC** fazia o truque, mas só em `_do_entrar` -- ou seja, a travessia inteira,
  os cliques de NPC e a coordenada da porta aconteciam com os outros
  personagens na tela;
* **HH** nunca fazia o truque. Ela apenas SEGURAVA a tecla durante a rajada da
  porta (`esconder_jogadores.segurado`), então fora daquele instante o esconder
  simplesmente não valia.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

1. As duas caves escondem na **largada**, e não só antes de entrar.
2. As duas continuam escondendo **antes de cada entrada** -- o grude vale para a
   sessão e apertar a tecla de novo o desfaz, inclusive sem querer.
3. O gesto é UM (`bot/esconder.py`), promovido do BC. Duas cópias divergiriam,
   e a que ficasse para trás deixaria uma cave sem esconder.
4. O perigo do chat aberto continua respeitado: `False` significa "não siga".

Ver `docs/decisoes/hh.md` §28.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot.bc.routine import BossRushRoutine
from blazesbot.bot.esconder import EsconderOsJogadores
from blazesbot.bot.hh.routine import HHRoutine


def _chamadas(metodo) -> list[tuple[int, str]]:
    """(linha, nome) de cada chamada do corpo, ordenado pela linha."""
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    nos = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)]
    return sorted((n.lineno, getattr(n.func, "attr", getattr(n.func, "id", "")))
                  for n in nos)


# ===========================================================================
# 1. As duas caves escondem na largada
# ===========================================================================


def test_as_DUAS_caves_escondem_na_largada():
    for rotina in (BossRushRoutine, HHRoutine):
        fonte = inspect.getsource(rotina.run)
        assert "esconder.garantir(" in fonte, (
            f"{rotina.__name__}.run não esconde os jogadores na largada")


def test_a_largada_esconde_ANTES_do_laco_de_estados():
    """De nada serve esconder depois de já ter clicado em NPC.

    PELO AST, e não por posição de texto: a docstring do `run` das duas caves
    fala de `farming`, e a busca textual encontrava a explicação antes do
    código.
    """
    for rotina in (BossRushRoutine, HHRoutine):
        arvore = ast.parse(textwrap.dedent(inspect.getsource(rotina.run)))
        metodo = arvore.body[0]

        esconde = [n.lineno for n in ast.walk(metodo)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "attr", "") == "garantir"]
        lacos = [n.lineno for n in ast.walk(metodo)
                 if isinstance(n, (ast.While, ast.For))]

        assert esconde, f"{rotina.__name__}.run não esconde"
        assert lacos, f"{rotina.__name__}.run deixou de ter laço de estados"
        assert min(esconde) < min(lacos), (
            f"{rotina.__name__} entra no laço de estados antes de esconder")


# ===========================================================================
# 2. E continuam escondendo antes de cada entrada
# ===========================================================================


def test_o_BC_continua_escondendo_antes_de_entrar():
    """O grude vale para a sessão, e a pessoa pode desfazê-lo sem querer."""
    fonte = inspect.getsource(BossRushRoutine._do_entrar)
    assert "esconder.garantir(" in fonte


def test_o_BC_ABORTA_a_entrada_se_o_chat_pode_estar_aberto():
    """Entrar com o chat aberto desvia toda tecla para o campo de texto."""
    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(BossRushRoutine._do_entrar)))
    ramos = [n for n in ast.walk(arvore) if isinstance(n, ast.If)
             and "esconder.garantir" in ast.unparse(n.test)]

    assert ramos, "o BC deixou de conferir o resultado do esconder"
    assert "not " in ast.unparse(ramos[0].test), (
        "a conferência inverteu de sentido")


def test_a_HH_tambem_esconde_antes_da_rajada():
    fonte = inspect.getsource(HHRoutine._do_entrar)
    assert "esconder.garantir(" in fonte, (
        "a HH voltou a entrar sem fazer o grude -- antes ela só segurava a "
        "tecla durante a rajada, e fora dali o esconder não valia")


def test_a_HH_NAO_aborta_a_entrada_por_causa_do_esconder():
    """A porta da HH é disputa por vaga: desistir dela custaria a run.

    A diferença com o BC é deliberada e é decisão de cave. O `False` já foi
    para o log como erro.
    """
    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(HHRoutine._do_entrar)))
    ramos = [n for n in ast.walk(arvore) if isinstance(n, ast.If)
             and "esconder.garantir" in ast.unparse(n.test)]

    assert not ramos, (
        "a HH passou a abortar a entrada por causa do esconder, e a porta dela "
        "é disputa por vaga")


def test_a_HH_ainda_SEGURA_a_tecla_na_rajada():
    """São coisas diferentes: o grude vale pela sessão, o segurar protege o
    par de cliques de NPC da própria fila de mensagens."""
    fonte = inspect.getsource(HHRoutine._do_entrar)
    assert "esconder_jogadores.segurado(" in fonte


# ===========================================================================
# 3. Um gesto só
# ===========================================================================


def test_o_gesto_MORA_em_bot_e_serve_as_duas():
    assert EsconderOsJogadores.__module__ == "blazesbot.bot.esconder"
    for rotina in (BossRushRoutine, HHRoutine):
        assert "EsconderOsJogadores(ctx)" in inspect.getsource(rotina.__init__)


def test_NENHUMA_cave_tem_o_truque_proprio():
    """Duas cópias divergiriam, e a que ficasse para trás perderia o esconder."""
    for rotina in (BossRushRoutine, HHRoutine):
        fonte = inspect.getsource(inspect.getmodule(rotina))
        assert "esconder_jogadores.esconder_jogadores(" not in fonte, (
            f"{rotina.__name__} voltou a chamar o truque direto")
        assert "state_chat_aberto" not in fonte, (
            f"{rotina.__name__} voltou a ter o template do chat")


def test_a_documentacao_de_transicao_esta_no_modulo():
    """Quem promove escreve no código que aquilo é dependência cruzada."""
    doc = inspect.getmodule(EsconderOsJogadores).__doc__ or ""
    assert "DEPENDÊNCIA CRUZADA" in doc
    assert "QUEM USA" in doc
    assert "DE ONDE VEIO" in doc


# ===========================================================================
# 4. O perigo do chat aberto
# ===========================================================================


class _Log:
    def __init__(self): self.erros: list[str] = []
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, m, *a): self.erros.append(m % a if a else m)


def _gesto(seguro: bool, escondeu: bool = True):
    from blazesbot.core import esconder_jogadores as nucleo

    g = object.__new__(EsconderOsJogadores)
    g.ctx = type("C", (), {
        "log": _Log(),
        "settings": type("S", (), {"keys": type("K", (), {
            "hide_players": "f12"})()})(),
        "key_down": lambda *a: None,
        "key_up": lambda *a: None,
        "press": lambda *a: None,
        "tick": lambda *a: None,
    })()
    g.chat_aberto = lambda: None
    resultado = nucleo.Resultado(
        **{campo: False for campo in nucleo.Resultado.__dataclass_fields__})
    return g, resultado


def test_INSEGURO_devolve_False_e_grita_no_log():
    """O `False` é o contrato: quem chama tem de parar o que ia fazer."""
    fonte = inspect.getsource(EsconderOsJogadores.garantir)

    assert "return False" in fonte
    assert "log.error" in fonte
    assert "campo de texto" in fonte, (
        "a mensagem deixou de explicar o que acontece com o chat aberto")


def test_chat_ILEGIVEL_devolve_None_e_nao_False():
    """`None` não é "fechado": Enter ALTERNA o chat, e apertar por garantia tem
    metade de chance de ABRIR o que se queria fechar."""
    g = object.__new__(EsconderOsJogadores)

    class _Ctx:
        log = _Log()
        templates = type("T", (), {"load": staticmethod(lambda n: None)})()
        hwnd = 0

    g.ctx = _Ctx()
    assert g.chat_aberto() is None
