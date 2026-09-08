"""Quando a HH joga o lixo fora, e quantas vezes.

=========================================================================
A CADÊNCIA, PEDIDA PELO USUÁRIO EM 08/09/2026
=========================================================================

> *"sobre jogar o lixo fora de HH, deve ser feito toda vez que termina a run de
> HH, pois pode ocupar muito espaço, entao assim que sai de HH voce ja faz o
> ato de deletar, e quando começa o bot, ao chegar na posição de entrar em HH
> voce faz a primeira limpa, para caso o usuario ja esteja com o inventario
> cheio"*

São DOIS momentos com naturezas diferentes:

| momento | quantas vezes | por quê |
|---|---|---|
| **na porta**, na largada | uma vez por LARGADA da HH | bolsa cheia ali não é lixo desta run -- é o que estava lá antes, e sem espaço a run inteira não guarda drop |
| **ao sair**, no `MANUTENCAO` | TODA run | o drop de uma run já ocupa muito espaço |

E o descarte continua atrás das duas travas que já existiam: a flag da conta
(`hh.deletar_lixo`, que nasce DESLIGADA porque apagar é irreversível) e a pasta
só da HH.

Ver `docs/decisoes/hh.md` §18.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot.hh.manutencao import ManutencaoDaHH
from blazesbot.bot.hh.routine import HHRoutine


class _Log:
    def __init__(self): self.linhas: list[str] = []
    def info(self, m, *a): self.linhas.append(m % a if a else m)
    def warning(self, m, *a): self.linhas.append(m % a if a else m)
    def debug(self, *a, **k): pass


class _Ctx:
    def __init__(self):
        self.log = _Log()
        self.stats = type("S", (), {"runs": 0})()

        class _HH:
            deletar_lixo = True

        class _Teclas:
            inventory = "i"

        self.settings = type("Cfg", (), {"hh": _HH(), "keys": _Teclas()})()


def _manutencao():
    m = ManutencaoDaHH(_Ctx(), vendedor=None)
    m.chamadas = 0

    def _apagar():
        m.chamadas += 1
        return 3

    m.descartar_o_lixo = _apagar
    return m


# ===========================================================================
# Na porta: uma vez por sessão
# ===========================================================================


def test_a_primeira_limpa_acontece():
    m = _manutencao()

    assert m.descartar_o_lixo_ao_comecar() == 3
    assert m.chamadas == 1


def test_a_primeira_limpa_NAO_se_repete():
    m = _manutencao()
    m.descartar_o_lixo_ao_comecar()

    for _ in range(5):
        assert m.descartar_o_lixo_ao_comecar() == 0

    assert m.chamadas == 1, (
        "Uma vez por SESSÃO, não por run: o descarte de cada run é o do "
        "`MANUTENCAO`. Repetir na porta abriria a bolsa a cada volta para "
        "nada.")


def test_LIGAR_a_HH_de_novo_devolve_o_direito_a_limpa():
    """O defeito medido em 08/09/2026, e o motivo dele.

    A rotina da HH é criada uma vez e GUARDADA pelo supervisor
    (`_rotina_da_hh`), porque o estado dela diz em que trecho a run está. Ela
    sobrevive a desligar e ligar o farm -- e com ela sobrevivia a memória de
    que a limpa já tinha acontecido:

    > *"estou testando desativar HH e ativar de volta para ver se esta limpando
    > corretamente o inventario com o delete, mas nao esta executando sempre"*
    """
    m = _manutencao()
    m.descartar_o_lixo_ao_comecar()
    assert m.descartar_o_lixo_ao_comecar() == 0

    m.a_hh_comecou()

    assert m.descartar_o_lixo_ao_comecar() == 3, (
        "Ligar a HH de novo é uma largada nova, e toda largada tem direito à "
        "sua limpa.")
    assert m.chamadas == 2


def test_a_memoria_da_limpa_e_do_OBJETO():
    """Nada de arquivo: o usuário pediu 'só enquanto está com o bot aberto'."""
    primeira, segunda = _manutencao(), _manutencao()
    primeira.descartar_o_lixo_ao_comecar()

    assert segunda.descartar_o_lixo_ao_comecar() == 3, (
        "Conta nova (ou bot reaberto) tem direito à limpa dela.")


def test_o_INICIO_da_rotina_zera_a_limpa():
    """E é no `run`, não num estado: desligar/ligar não passa pelos estados."""
    fonte = inspect.getsource(HHRoutine.run)

    assert "self.manutencao.a_hh_comecou()" in fonte, (
        "Sem isto, só a PRIMEIRA largada da sessão limpa a bolsa -- que é o "
        "defeito medido.")


# ===========================================================================
# Os dois pontos de chamada na rotina
# ===========================================================================


def _chamadas(metodo) -> list[str]:
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    return [getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in ast.walk(arvore) if isinstance(n, ast.Call)]


def test_TODO_caminho_da_porta_para_o_ENTRAR_passa_pela_primeira_limpa():
    """São dois: já estar na porta, e chegar nela pela viagem.

    O caminho curto ("já estou na porta") é o NORMAL a partir da segunda run --
    e é justamente o que o bot pega quando abre com o personagem parado ali.
    """
    fonte = textwrap.dedent(inspect.getsource(HHRoutine._do_ate_a_porta))
    arvore = ast.parse(fonte)

    idas = [n for n in ast.walk(arvore)
            if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "_ir_para"]
    limpas = [n.lineno for n in ast.walk(arvore)
              if isinstance(n, ast.Call)
              and getattr(n.func, "attr", "") == "descartar_o_lixo_ao_comecar"]

    assert len(idas) == len(limpas) == 2, (
        f"{len(idas)} saída(s) para o ENTRAR e {len(limpas)} limpa(s). Toda "
        f"saída tem que ter a sua -- a que ficar de fora é a que roda com a "
        f"bolsa cheia.")
    for ida in idas:
        assert any(linha < ida.lineno for linha in limpas), (
            "A limpa vem ANTES de entrar: dentro da cave já é tarde.")


def test_o_MANUTENCAO_descarta_UMA_VEZ_POR_RUN():
    """Uma vez, e o `if` é a trava -- não um filtro de configuração.

    ERA SEM `if` NENHUM, e isso custou um laço: em 08/09/2026 o bot girou entre
    `PREPARAR` e `MANUTENCAO` a cada ~2 s, apagando lixo e tentando vender sem
    sair do lugar, porque a bolsa cheia mantinha a condição verdadeira.

    Regra do usuário: *"o deletar não deve ficar tentando varias vezes, apenas
    1 vez"*. A chave é `stats.runs`, que sobe uma vez por run.
    """
    fonte = textwrap.dedent(inspect.getsource(HHRoutine._do_manutencao))
    arvore = ast.parse(fonte)
    metodo = arvore.body[0]

    for no in ast.walk(metodo):
        if (isinstance(no, ast.Call)
                and getattr(no.func, "attr", "") == "descartar_o_lixo"):
            break
    else:
        raise AssertionError("O `MANUTENCAO` deixou de descartar o lixo.")

    # A TRAVA É POR RUN, e não por configuração: o drop de UMA run já ocupa
    # muito espaço, então o descarte não espera N runs como a venda.
    fonte = textwrap.dedent(inspect.getsource(HHRoutine._do_manutencao))
    assert "precisa_descartar()" in fonte, (
        "o descarte voltou a rodar em toda passada da MANUTENCAO, e a "
        "MANUTENCAO pode ser visitada várias vezes na mesma run")
    assert "anotar_o_descarte()" in fonte, (
        "sem anotar, a trava não fecha e o laço volta")

    from blazesbot.bot.hh.manutencao import ManutencaoDaHH
    trava = inspect.getsource(ManutencaoDaHH.precisa_descartar)
    assert "stats.runs" in trava, (
        "a trava do descarte deixou de ser POR RUN")


def test_a_ORDEM_no_MANUTENCAO_e_apagar_e_depois_vender():
    ordem = _chamadas(HHRoutine._do_manutencao)

    assert ordem.index("descartar_o_lixo") < ordem.index("vender"), (
        "O lixo da HH não é comprado pelo NPC: levá-lo para a janela de venda "
        "gasta cliques em item que não sai.")


# ===========================================================================
# As travas continuam de pé
# ===========================================================================


def test_a_primeira_limpa_respeita_a_flag_desligada():
    from blazesbot.config import HHConfig

    assert HHConfig().deletar_lixo is False, (
        "Apagar é irreversível; a flag nasce desligada e ligar é ato "
        "explícito de quem já conferiu a pasta.")

    ctx = _Ctx()
    ctx.settings.hh.deletar_lixo = False
    m = ManutencaoDaHH(ctx, vendedor=None)

    assert m.descartar_o_lixo_ao_comecar() == 0, (
        "A primeira limpa não pode ser uma porta dos fundos para a flag.")


def test_a_primeira_limpa_usa_a_pasta_SO_da_HH():
    fonte = inspect.getsource(ManutencaoDaHH.descartar_o_lixo)

    assert "PASTA_DO_LIXO_DA_HH" in fonte, (
        "A lista global serve o APP e a BC, e o que é lixo numa cave é "
        "mercadoria na outra.")
