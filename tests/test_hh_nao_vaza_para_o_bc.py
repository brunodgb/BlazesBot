"""Ligar uma cave NÃO pode mexer no estado da outra. Nos dois sentidos.

=========================================================================
O DEFEITO QUE ESTE ARQUIVO IMPEDE DE VOLTAR
=========================================================================

Relato do usuário em 03/09/2026: *"ao ativar o botão do BOT HH na interface, o
sistema está ativando visualmente o BOT BC."*

A causa foi alargar o significado de uma propriedade sem revisar quem a lê.
`Account.farms` significava "o BC está ligado" quando existia uma cave só;
virou `bc_farm or hh_farm`. E quatro lugares continuaram lendo com o
significado antigo:

    supervisor.py  o resumo publicava `"farm": account.farms`, a ponte web
                   repassava, e o espelho ao vivo MARCAVA a caixa do BC
    context.py     `raise_if_stopped` comparava com `farms`, então desmarcar o
                   BC com a HH ligada NÃO cortava a fase no meio
    supervisor.py  dois status diziam "BC farm" para conta só de HH
    account_dialog rótulo "BC Farm ligado" para conta só de HH

O primeiro é o sintoma visível; o SEGUNDO é o que ninguém teria visto -- a
parada do usuário deixava de responder no meio da fase e só valia na fronteira
do estado seguinte.

=========================================================================
A REGRA QUE FICOU
=========================================================================

`farms` responde ELEGIBILIDADE -- "esta conta está ocupada farmando?" -- e é
usada para validar conta de reset, recusar seguidor do time do APP e cobrar
configuração. **Quem quer saber de UMA cave lê `bc_farm` ou `hh_farm` direto.**
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from blazesbot.bot import supervisor as mod_supervisor
from blazesbot.config import CAVE_BC, CAVE_HH, Account

RAIZ = Path(__file__).resolve().parent.parent


def _fonte(metodo) -> str:
    return textwrap.dedent(inspect.getsource(metodo))


# ===========================================================================
# A propriedade
# ===========================================================================


def test_farms_responde_por_QUALQUER_cave():
    """É a pergunta de elegibilidade, e ela vale para as duas."""
    a = Account()
    assert a.farms is False
    a.bc_farm = True
    assert a.farms is True
    a.bc_farm, a.hh_farm = False, True
    assert a.farms is True


@pytest.mark.parametrize("bc,hh,esperado", [
    (False, False, ""),
    (True, False, CAVE_BC),
    (False, True, CAVE_HH),
    # AS DUAS MARCADAS RODA A HH -- é a ordem do despacho, e ela mora num lugar
    # só justamente para não haver duas respostas para "o que vai rodar".
    (True, True, CAVE_HH),
])
def test_cave_ligada_diz_QUAL_e_respeita_o_despacho(bc, hh, esperado):
    a = Account()
    a.bc_farm, a.hh_farm = bc, hh
    assert a.cave_ligada == esperado


def test_a_ordem_do_despacho_e_a_MESMA_da_propriedade():
    """Duas precedências escritas em lugares diferentes divergem na primeira
    manutenção -- e aí a interface diz uma coisa e o bot faz outra.

    Pelo AST e não por `str.index`: a primeira versão comparou posições de
    texto e casou com uma menção em comentário, dando a ordem invertida.
    """
    arvore = ast.parse(_fonte(mod_supervisor.AccountSupervisor._operate))
    # a linha de cada LEITURA de atributo, ignorando comentário e docstring
    linhas = {"hh_farm": [], "bc_farm": []}
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute) and no.attr in linhas:
            linhas[no.attr].append(no.lineno)
    assert linhas["hh_farm"] and linhas["bc_farm"], linhas
    assert min(linhas["hh_farm"]) < min(linhas["bc_farm"]), (
        f"o despacho deixou de dar precedência à HH: {linhas}")


# ===========================================================================
# O RESUMO -- a origem do vazamento visual
# ===========================================================================


def test_o_resumo_publica_UMA_CHAVE_POR_CAVE():
    """Publicar `farms` como `farm` é o vazamento inteiro: a interface espelha
    esse campo na caixa do BC."""
    fonte = inspect.getsource(mod_supervisor)
    assert '"farm": sup.account.bc_farm' in fonte
    assert '"farm_hh": sup.account.hh_farm' in fonte
    assert '"farm": sup.account.farms' not in fonte, (
        "o resumo voltou a publicar `farms` no campo do BC -- é o vazamento")


def test_a_ponte_web_le_as_DUAS_chaves_do_resumo():
    """As duas caixas têm que contar a mesma história, da mesma fonte."""
    fonte = (RAIZ / "blazesbot" / "web_app.py").read_text(encoding="utf-8")
    assert 'd.get("farm")' in fonte
    assert 'd.get("farm_hh")' in fonte


def test_nenhum_lugar_usa_farms_para_dizer_BC():
    """Varredura: `farms` só pode aparecer onde a pergunta é elegibilidade.

    A lista de usos legítimos está declarada abaixo, com o motivo. Um uso novo
    reprova aqui e obriga a decisão -- é elegibilidade, ou é uma cave só?
    """
    # (arquivo, quantos usos, por quê)
    LEGITIMOS = {
        # validação: só cobra configuração de farm de quem vai farmar
        "blazesbot/config.py": 5,
        # elegibilidade: conta ocupada não é seguidora do time do APP, não é
        # conta de reset, e recebe o petbug
        "blazesbot/bot/supervisor.py": 5,
        # o guarda da parada usa `farms` como ÚLTIMO recurso, quando ninguém
        # disse qual cave está no ar
        "blazesbot/bot/context.py": 1,
    }
    # PELO AST, e não por texto: contar linhas que contêm ".farms" pegava
    # docstring e comentário, e a primeira versão deste teste acusou o
    # `context.py` de três usos quando ele tem UM (os outros dois eram a
    # explicação escrita ali).
    achados: dict[str, int] = {}
    for arquivo in (RAIZ / "blazesbot").rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        usos = sum(1 for no in ast.walk(arvore)
                   if isinstance(no, ast.Attribute) and no.attr == "farms")
        if usos:
            achados[arquivo.relative_to(RAIZ).as_posix()] = usos

    inesperados = {k: v for k, v in achados.items() if k not in LEGITIMOS}
    assert not inesperados, (
        f"uso novo de `.farms`: {inesperados}. Decida: é ELEGIBILIDADE "
        f"(mantenha e declare aqui) ou é UMA cave (leia `bc_farm`/`hh_farm`)?")
    for arquivo, esperado in LEGITIMOS.items():
        assert achados.get(arquivo, 0) <= esperado, (
            f"{arquivo} passou a usar `.farms` mais vezes que o declarado")


# ===========================================================================
# A PARADA -- o vazamento funcional, que ninguém teria visto
# ===========================================================================


class _Conta:
    def __init__(self, bc=False, hh=False):
        self.bc_farm, self.hh_farm = bc, hh

    @property
    def farms(self):
        return bool(self.bc_farm or self.hh_farm)


def _ctx(cave: str, bc: bool, hh: bool):
    """Um `BotContext` cru, só com o que a parada lê."""
    from blazesbot.bot.context import BotContext

    ctx = object.__new__(BotContext)
    ctx.farming = True
    ctx.cave_em_farm = cave
    ctx.account = _Conta(bc, hh)
    return ctx


@pytest.mark.parametrize("cave,bc,hh,ainda_ligada", [
    # A CAVE QUE RODA É A HH: só o interruptor DELA importa.
    (CAVE_HH, False, True, True),
    (CAVE_HH, True, False, False),      # BC ligado não segura a HH
    (CAVE_HH, False, False, False),
    # E vice-versa. Este é o caso que estava QUEBRADO: com a HH ligada,
    # desmarcar o BC não cortava a fase do BC.
    (CAVE_BC, True, False, True),
    (CAVE_BC, False, True, False),
    (CAVE_BC, False, False, False),
])
def test_a_parada_confere_o_interruptor_DA_CAVE_QUE_RODA(cave, bc, hh,
                                                        ainda_ligada):
    ctx = _ctx(cave, bc, hh)
    assert ctx._a_cave_continua_ligada() is ainda_ligada


@pytest.mark.parametrize("bc,hh", [(True, False), (False, True), (True, True)])
def test_sem_saber_a_cave_cai_em_farms(bc, hh):
    """Ninguém disse qual cave é: vale o comportamento antigo, que é a direção
    segura -- errar para "continua ligado" faz a fase terminar sozinha um
    instante depois; errar para "desligou" abortaria uma fase que ninguém
    pediu para abortar."""
    ctx = _ctx("", bc, hh)
    assert ctx._a_cave_continua_ligada() is True


def test_cada_rotina_DIZ_qual_cave_e():
    """Sem isso a parada cai no último recurso e volta a errar o alvo."""
    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    for rotina, esperado in ((BossRushRoutine, "CAVE_BC"),
                             (HHRoutine, "CAVE_HH")):
        fonte = _fonte(rotina.run)
        assert f"ctx.cave_em_farm = {esperado}" in fonte, rotina.__name__


def test_a_cave_e_LIMPA_na_saida():
    """`cave_em_farm` sobrando faz a parada de um laço que não é de cave
    conferir o interruptor de uma cave."""
    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    for rotina in (BossRushRoutine, HHRoutine):
        arvore = ast.parse(_fonte(rotina.run))
        finallys = [n for n in ast.walk(arvore)
                    if isinstance(n, ast.Try) and n.finalbody]
        corpo = " ".join(ast.unparse(x) for f in finallys for x in f.finalbody)
        assert "cave_em_farm = ''" in corpo, rotina.__name__


# ===========================================================================
# OS RÓTULOS -- dizer "BC" para uma conta de HH é mentir para o usuário
# ===========================================================================


@pytest.mark.parametrize("arquivo,metodo", [
    ("supervisor", "_operate"),
])
def test_nenhum_status_diz_BC_por_causa_de_farms(arquivo, metodo):
    """O texto tem que sair da cave que está ligada."""
    fonte = inspect.getsource(mod_supervisor)
    assert '"com BC farm" if self.account.farms' not in fonte
    assert "O BC farm também está ligado" not in fonte

