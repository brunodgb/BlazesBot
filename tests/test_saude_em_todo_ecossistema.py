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


def test_a_HH_NAO_trata_Disconnected():
    """Quem sabe matar o cliente, relançar e relogar é o supervisor.

    Uma rotina que engolisse `Disconnected` deixaria a conta presa numa janela
    morta -- e o relogin, que é a fundação de todo ecossistema, nunca
    aconteceria.
    """
    from blazesbot.bot.hh import routine as mod_hh

    fonte = inspect.getsource(mod_hh)
    arvore = ast.parse(fonte)
    capturas = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.ExceptHandler) and no.type is not None:
            nomes = ast.unparse(no.type)
            if "Disconnected" in nomes:
                capturas.append(no.lineno)
    assert not capturas, (
        f"a HH captura Disconnected nas linhas {capturas}; ela tem que subir "
        f"para o supervisor")


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
