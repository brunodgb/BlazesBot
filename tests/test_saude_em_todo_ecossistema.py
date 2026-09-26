"""LOGIN/RELOGIN é o ecossistema BASE: todo ecossistema tem que ver a queda.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

Medido em 18/08/2026, relato do usuário: cinco contas caíram ao mesmo tempo. As
quatro de BC fecharam a janela e relogaram; a do APP ficou na tela com a caixa
"Connection interrupted, please open client again.", apertando teclas contra
ela.

A causa não era o template -- ele casa a **0.973** na captura daquela janela
(`data/templates/entrada/queda-app.png`). A causa era ninguém olhar: o modo APP
é despachado no topo do laço de `_operate` com `continue`, então o
`watchdog.check()` daquele laço nunca era alcançado. A única conferência era
`IsWindow` DEPOIS de `executor.rodar()` retornar -- ou seja, só pegava janela
que já tinha morrido.

Corroboração nos dados de produção: dos 19 prints em `logs/quedas/`, NENHUM era
de conta APP.

A regra que ficou, e que vale para qualquer ecossistema futuro: **detectar a
queda ENQUANTO roda, e com a MESMA definição de queda.** Duas definições
divergem na primeira manutenção.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

from blazesbot.bot import supervisor as mod_supervisor
from blazesbot.bot import watchdog as mod_watchdog
from blazesbot.bot.app import executor as mod_executor


def test_existe_UMA_definicao_de_queda_e_ela_nao_pede_contexto():
    """`avaliar_saude` recebe PEÇAS, não `BotContext`.

    É o que permite o modo APP usar a mesma regra sem passar a depender do
    estado do farm -- o `BotContext` carrega esse estado, e é por isso que o
    `_rodar_modo_app` não o recebe.
    """
    assert hasattr(mod_watchdog, "avaliar_saude")
    params = list(inspect.signature(mod_watchdog.avaliar_saude).parameters)
    assert params == ["pid", "hwnd", "janela_existe", "templates"], params


def test_o_watchdog_do_BC_delega_para_ela_em_vez_de_repetir():
    """Se o `check` voltar a fazer as conferências na mão, as duas definições
    divergem -- e a do APP fica para trás em silêncio, como já ficou."""
    fonte = inspect.getsource(mod_watchdog.Watchdog.check)
    assert "avaliar_saude(" in fonte, (
        "o Watchdog parou de delegar; a regra de queda foi duplicada")
    assert "psutil.pid_exists" not in fonte, (
        "a conferência de processo voltou para dentro do check")


def test_o_modo_APP_confere_saude_e_usa_a_MESMA_funcao():
    fonte = inspect.getsource(mod_supervisor.AccountSupervisor._rodar_modo_app)
    assert "avaliar_saude(" in fonte, (
        "o modo APP não confere saúde — foi assim que a conta ficou apertando "
        "teclas contra a caixa de conexão interrompida")
    assert "conferir_saude=" in fonte, (
        "a conferência não é entregue ao executor, então não roda DURANTE a "
        "macro — e `executor.rodar()` leva horas")


def test_o_executor_chama_a_conferencia_e_NAO_engole_a_excecao():
    """Queda não é complemento.

    O `antes_da_volta` tem `except` de propósito: se a barra de atalhos falhar,
    a macro segue. Queda é o oposto -- engolir deixaria a macro apertando teclas
    contra uma caixa de erro pelas horas seguintes.
    """
    fonte = inspect.getsource(mod_executor.ExecutorDeMacro.rodar)
    assert "_conferir_saude()" in fonte
    arvore = ast.parse(inspect.getsource(mod_executor.ExecutorDeMacro))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Try):
            continue
        chamadas = [n for n in ast.walk(no)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "_conferir_saude"]
        assert not chamadas, (
            "a conferência de saúde está dentro de um try/except — a queda "
            "seria engolida e a macro seguiria contra a caixa de erro")


def test_o_executor_continua_cego():
    """O isolamento não pode ter sido pago por esta correção.

    O executor recebe a conferência como FUNÇÃO justamente para continuar sem
    saber o que é `BotContext`, watchdog ou queda.

    LÊ O AST, NÃO O TEXTO -- mesma lição que `tests/test_ecossistemas.py` já
    registra: comentário citando um módulo não conta. A primeira versão deste
    teste reprovava por causa dos COMENTÁRIOS que explicam o isolamento, o que é
    o oposto do que se quer travar.
    """
    fonte = Path(mod_executor.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    usados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name):
            usados.add(no.id)
        elif isinstance(no, ast.Attribute):
            usados.add(no.attr)
        elif isinstance(no, ast.alias):
            usados.add((no.asname or no.name).split(".")[-1])

    for proibido in ("BotContext", "Watchdog", "avaliar_saude", "DcReason"):
        assert proibido not in usados, (
            f"o executor passou a USAR `{proibido}` — o isolamento do "
            f"ecossistema APP foi quebrado")


def test_a_queda_do_APP_entra_no_historico_de_quedas():
    """Antes, nenhuma conta de APP aparecia nos registros de queda.

    Não porque não caíssem: porque ninguém percebia. Corrigida a detecção, o
    cartão tem que ser gravado também -- no MESMO contexto que o `_run_session`
    lê depois.
    """
    fonte = inspect.getsource(mod_supervisor.AccountSupervisor._rodar_modo_app)
    assert "ultima_queda" in fonte, (
        "a queda no APP não é anotada; ela não vira cartão no histórico")


# ===========================================================================
# O TERCEIRO ECOSSISTEMA -- a HH, desde 02/09/2026
# ===========================================================================
#
# A regra do `CLAUDE.md` é explícita: *"todo ecossistema -- presente e futuro --
# é obrigado a perceber a queda ENQUANTO roda, usar a MESMA definição de queda,
# ter o mesmo desfecho, e gravar no Histórico de Quedas."*
#
# A HH cumpre isso pelo mesmo caminho da BC, e não por um mecanismo próprio: ela
# não trata `Disconnected`, deixa subir para o supervisor, e o `_guard` de cada
# volta chama `ctx.check_watchdog()`. Estes testes travam justamente isso -- o
# dia em que alguém "resolver" a queda dentro da rotina, as duas definições
# divergem, e a da HH fica para trás em silêncio.


def test_a_HH_confere_a_saude_ENTRE_estados():
    """`_guard` roda a cada volta do laço, antes do handler do estado.

    É o equivalente do `check_watchdog` do BC -- e é o que faltava no modo APP
    no defeito de 18/08/2026, quando a conta ficou apertando teclas contra a
    caixa de "Connection interrupted".
    """
    from blazesbot.bot.hh import routine as mod_hh

    fonte = inspect.getsource(mod_hh.HHRoutine._guard)
    assert "check_watchdog" in fonte, (
        "a HH não confere a saúde entre estados -- é o defeito do APP de novo")

    laco = inspect.getsource(mod_hh.HHRoutine.run)
    assert "_guard()" in laco, "o `_guard` não é chamado no laço"


def test_a_HH_NAO_ENGOLE_Disconnected():
    """Quem sabe matar o cliente, relançar e relogar é o supervisor.

    Uma rotina que engolisse `Disconnected` deixaria a conta presa numa janela
    morta -- e o relogin, que é a fundação de todo ecossistema, nunca
    aconteceria.

    =================================================================
    O TESTE PEDIA A COISA ERRADA, E ISSO IMPORTA
    =================================================================

    Ele exigia que `Disconnected` **não aparecesse** em nenhum `except` da HH.
    Parecia a mesma coisa e não é: quando a HH ganhou um `except Exception`
    para não derrubar a sessão por defeito de um estado, esse `except Exception`
    passou a engolir `Disconnected` junto -- e a forma de impedir isso é
    justamente CAPTURÁ-LO antes e relançar, que era o que o teste proibia.

    Então o que se trava aqui é o comportamento: capturar pode; **engolir, não**.
    Todo `except` que nomeia `Disconnected` tem de ser um `raise` puro. É o
    mesmo desenho da BC (`bc/routine.py`).
    """
    from blazesbot.bot import rotina_de_cave
    from blazesbot.bot.hh import routine as mod_hh

    # O laço da HH é o comum das caves desde 26/09/2026: o `except` que mais
    # importa mora lá, e varrer só o módulo da HH passaria vazio.
    engolidos = []
    for modulo in (mod_hh, rotina_de_cave):
        for no in ast.walk(ast.parse(inspect.getsource(modulo))):
            if not isinstance(no, ast.ExceptHandler) or no.type is None:
                continue
            if "Disconnected" not in ast.unparse(no.type):
                continue
            # O corpo tem de ser um `raise` seco -- nada antes, nada depois.
            corpo = [c for c in no.body
                     if not (isinstance(c, ast.Expr)
                             and isinstance(c.value, ast.Constant))]
            if not (len(corpo) == 1 and isinstance(corpo[0], ast.Raise)
                    and corpo[0].exc is None):
                engolidos.append(f"{modulo.__name__}:{no.lineno}")
    assert not engolidos, (
        f"a HH captura Disconnected nas linhas {engolidos} sem relançar; ela "
        f"tem que subir para o supervisor")


def test_o_except_geral_da_HH_vem_DEPOIS_dos_especificos():
    """Ordem de `except` é semântica, não estilo.

    `except Exception` primeiro engoliria `Disconnected`, `StopRequested` e
    `FarmDesligado` -- os três sinais que NÃO são defeito e que precisam chegar
    a quem sabe tratá-los.
    """
    import textwrap

    from blazesbot.bot.hh import routine as mod_hh

    arvore = ast.parse(
        textwrap.dedent(inspect.getsource(mod_hh.HHRoutine.run)))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Try):
            continue
        nomes = [ast.unparse(h.type) if h.type else "BARE" for h in no.handlers]
        if "Exception" not in nomes:
            continue
        geral = nomes.index("Exception")
        for sinal in ("Disconnected", "StopRequested", "FarmDesligado"):
            posicoes = [i for i, n in enumerate(nomes) if sinal in n]
            assert posicoes and min(posicoes) < geral, (
                f"{sinal} tem que ser tratado ANTES do `except Exception` "
                f"(handlers: {nomes})")


def test_a_queda_na_HH_entra_no_historico_pelo_MESMO_caminho():
    """`_registrar_queda` é do supervisor e serve os três ecossistemas.

    O gatilho é `ctx.ultima_queda`, que só o watchdog escreve -- então a HH não
    precisa de nada além de deixar a exceção subir.
    """
    fonte = inspect.getsource(mod_supervisor.AccountSupervisor._run_session)
    assert "_registrar_queda" in fonte

    # E o registro NÃO é por ecossistema: um `if` por cave aqui seria a terceira
    # definição de "o que gravar quando cai".
    registro = inspect.getsource(mod_supervisor.AccountSupervisor._registrar_queda)
    for nome in ("bc_farm", "hh_farm", "app.enabled"):
        assert nome not in registro, (
            f"o registro da queda passou a olhar `{nome}` -- ele tem que ser "
            f"igual para todo ecossistema")


def test_os_TRES_ecossistemas_aparecem_no_despacho():
    """Um ecossistema que não é despachado não roda -- e não cai, porque nunca
    subiu. O teste existe para o quarto não ser esquecido."""
    fonte = inspect.getsource(mod_supervisor.AccountSupervisor._operate)
    for gatilho in ("app.enabled", "hh_farm", "bc_farm"):
        assert gatilho in fonte, f"o despacho não consulta `{gatilho}`"


def test_a_parada_do_usuario_vale_na_HH_como_nas_outras():
    """`raise_if_stopped` no `_guard`, e `farming` protegido por `finally`.

    Sem o `finally` o laço "online" seguinte re-detonaria a parada e derrubaria
    a sessão -- o oposto do que o botão Parar deve fazer.
    """
    from blazesbot.bot.hh import routine as mod_hh

    assert "raise_if_stopped" in inspect.getsource(mod_hh.HHRoutine._guard)

    import textwrap

    arvore = ast.parse(textwrap.dedent(inspect.getsource(mod_hh.HHRoutine.run)))
    finallys = [n for n in ast.walk(arvore)
                if isinstance(n, ast.Try) and n.finalbody]
    corpo = " ".join(ast.unparse(x) for f in finallys for x in f.finalbody)
    assert "farming = False" in corpo

# ===========================================================================
# A FADA ERA A ÚNICA QUE NÃO VIA A PRÓPRIA QUEDA -- 04/09/2026
# ===========================================================================
#
# Relato do usuário: *"se a fada cai, muitas vezes o bot não reconhece"*. E não
# reconhecia mesmo: `rodar()` termina sozinho quando o `continuar` vê a janela
# morta pelo `IsWindow`, e o `_operate` simplesmente chamava `_rodar_fada` de
# novo -- sem matar o cliente, sem relogin, sem Histórico de Quedas. O modo APP
# já tinha exatamente esta linha no fim de `_rodar_modo_app` desde 18/08/2026;
# a Fada nasceu depois e não a herdou.


def _fonte_da(nome):
    """A montagem da Fada saiu do supervisor em 04/09/2026 -- ver
    `bot/fada_montagem.py`. `_montar_a_fada` ficou no supervisor."""
    from blazesbot.bot import fada_montagem as mod_fada

    for dono in (mod_fada, mod_supervisor.AccountSupervisor):
        alvo = getattr(dono, nome, None)
        if alvo is not None:
            return inspect.getsource(alvo)
    raise AssertionError(nome)


def test_a_FADA_percebe_a_propria_queda_como_o_modo_APP():
    fonte = _fonte_da("rodar_a_fada")
    arvore = ast.parse(textwrap.dedent(fonte))

    levantam = [no for no in ast.walk(arvore)
                if isinstance(no, ast.Raise)
                and no.exc is not None
                and "Disconnected" in ast.unparse(no.exc)]

    assert levantam, ("`_rodar_fada` não levanta `Disconnected` em lugar nenhum "
                      "-- a queda da Fada volta a passar despercebida.")
    assert "IsWindow" in fonte, ("a queda tem de ser decidida pela MESMA "
                                 "pergunta do modo APP: a janela ainda existe?")


def test_a_queda_da_FADA_e_conferida_DEPOIS_do_laco_dela():
    """O `continuar` da Fada só ENCERRA o laço quando a janela morre; quem
    transforma isso em queda é a conferência no fim, no mesmo lugar em que
    `_rodar_modo_app` faz a dele."""
    fonte = _fonte_da("rodar_a_fada")
    depois_do_laco = fonte.split("fada.rodar()")[-1]

    assert "IsWindow" in depois_do_laco and "Disconnected" in depois_do_laco


def test_montar_a_FADA_NAO_ENGOLE_a_queda():
    """`_montar_a_fada` tem um `except Exception` para não derrubar a sessão
    quando a montagem falha -- e ele engolia `Disconnected` junto, deixando a
    Fada da HH acompanhando com a janela morta. Capturar pode; engolir, não."""
    fonte = textwrap.dedent(_fonte_da("_montar_a_fada"))
    arvore = ast.parse(fonte)

    handlers = [no for no in ast.walk(arvore) if isinstance(no, ast.ExceptHandler)]
    nomeiam = [h for h in handlers
               if h.type is not None and "Disconnected" in ast.unparse(h.type)]

    assert nomeiam, "`_montar_a_fada` não trata `Disconnected` -- ele é engolido."
    for h in nomeiam:
        assert all(isinstance(c, ast.Raise) and c.exc is None for c in h.body), (
            "o `except Disconnected` tem de ser um `raise` seco")
    # E ele precisa vir ANTES do `except Exception`, senão nunca é alcançado.
    ordem = [ast.unparse(h.type) if h.type is not None else "*" for h in handlers]
    assert ordem.index("Disconnected") < ordem.index("Exception"), ordem


def test_a_FADA_sem_memoria_nao_gira_em_laco_quente():
    """Memória que não abre devolvia na hora, e `_operate` chamava de novo na
    hora: a conta girava sem dormir, sem curar e sem cair. O respiro é o que
    impede isso -- e antes dele vem a pergunta se a janela morreu, porque
    memória fechada quase sempre é janela morta."""
    fonte = _fonte_da("rodar_a_fada")
    trecho = fonte.split("não consegui abrir a memória")[0]

    assert "IsWindow" in trecho, ("antes de desistir por falta de memória, "
                                  "conferir se não é queda")
    depois = fonte.split("não consegui abrir a memória")[1].split("return")[0]
    assert "SEGUNDOS_ENTRE_TENTATIVAS" in depois
