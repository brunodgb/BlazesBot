"""A HH também segura a entrada quando a conta de reset está offline.

=========================================================================
A REGRA
=========================================================================

Pedido do usuário em 08/09/2026:

> *"O ecossistema HH precisa da mesma trava já existente no BC. Antes de rodar
> a cave, o HH deve checar se a Conta Reset global configurada está
> online/conectada. Se estiver offline, o bot HH DEVE pausar a rota, entrar em
> modo de espera e aguardar a reconexão."*

=========================================================================
PROMOVIDA, NÃO CLONADA
=========================================================================

O pedido dizia "clonando a lógica validada do BC". Ela foi **promovida** para
`bot/espera_do_reseter.py`, o que é mais forte e é o que o `CLAUDE.md` exige:

> *"REUSO PRIMÁRIO. Duplicação é inaceitável. Duas funções iguais em lugares
> diferentes são duas chances de só uma ser corrigida."*

E aqui isso não é preciosismo. A parte difícil da trava não é esperar -- é
distinguir **"o reseter caiu"** (temporário: relogin é o padrão de toda conta,
então ele volta e a espera tem fim) de **"o reseter não existe mais"**
(removido, desativado, desmarcado, posto para farmar: esperar seria uma conta
parada a noite inteira). Uma cópia que errasse essa distinção perderia runs ou
travaria para sempre, e o sintoma apareceria horas depois.

O que NÃO subiu: **onde** cada cave trava. Isso é decisão de cave.

Ver `docs/decisoes/reset-de-time.md`.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot import espera_do_reseter as trava
from blazesbot.bot.bc.routine import BossRushRoutine
from blazesbot.bot.hh.routine import HHRoutine
from blazesbot.config import CAVE_BC, CAVE_HH, Account


def _chamadas(metodo) -> list[str]:
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    return [ast.unparse(n.func) for n in ast.walk(arvore)
            if isinstance(n, ast.Call)]


# ===========================================================================
# A HH trava, e trava no lugar certo
# ===========================================================================


def test_a_HH_chama_a_trava():
    assert "esperar_o_reseter" in _chamadas(HHRoutine._garantir_o_time)


def test_a_trava_da_HH_vem_ANTES_do_convite():
    """Depois do `montar_time()` ela já teria falhado."""
    fonte = inspect.getsource(HHRoutine._garantir_o_time)
    assert fonte.index("esperar_o_reseter(") < fonte.index("montar_time()")


def test_a_trava_da_HH_vem_DEPOIS_de_conferir_o_time():
    """Quem já está em time não precisa de convite -- nem de esperar por quem
    convidar."""
    fonte = inspect.getsource(HHRoutine._garantir_o_time)
    assert fonte.index("estado_do_time") < fonte.index("esperar_o_reseter(")


def test_conta_SEM_reset_nao_trava_nem_um_tick():
    """Campo vazio é o jeito de dizer "não uso reset de time"."""
    passos = []

    class _Ctx:
        settings = type("S", (), {"reset_nick": ""})()

        def tick(self, s):
            passos.append(s)

        def raise_if_stopped(self):
            passos.append("check")

    trava.esperar_o_reseter(_Ctx(), onde="teste")
    assert passos == []


# ===========================================================================
# A espera não congela a interface
# ===========================================================================


def test_a_espera_usa_ctx_tick_e_NUNCA_time_sleep():
    """Cada conta roda na thread dela, então a espera não toca a UI.

    E o `tick` é o que mantém o watchdog DESTA conta vivo enquanto ela está
    parada -- uma conta de cave também cai, e parada por horas num `time.sleep`
    ela ficaria cega para a própria queda. Ele também dá as três saídas de
    graça: Parar, desmarcar o farm da cave e ligar o modo APP.
    """
    chamadas = set(_chamadas(trava.esperar_o_reseter))

    assert "ctx.tick" in chamadas, chamadas
    assert not {c for c in chamadas if c.endswith("sleep")}, (
        "a espera do reseter voltou a dormir cega")


def test_a_espera_LOGA_o_que_esta_esperando():
    """"Aguardando conta reset conectar" tem que aparecer no log.

    Sem isso, uma conta parada na porta parece uma conta travada -- e o usuário
    não tem como saber a diferença sem ler o código.
    """
    fonte = inspect.getsource(trava.esperar_o_reseter)
    assert "log.warning" in fonte
    assert "não está no ar" in fonte
    assert "Volto sozinho" in fonte, (
        "o aviso tem que dizer que a espera termina sozinha")


def test_a_espera_reavalia_a_CONFIGURACAO_a_cada_volta():
    """"Caiu" e "não existe mais" são estados diferentes."""
    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(trava.esperar_o_reseter))).body[0]
    lacos = [n for n in ast.walk(arvore) if isinstance(n, ast.While)]

    assert lacos, "a espera deixou de ser um laço"
    dentro = ast.dump(lacos[0])
    assert "problema_do_reset" in dentro, (
        "a conferência de configuração saiu de dentro do laço, e a conta "
        "passaria a esperar para sempre por um reseter que o bot aposentou")
    assert "desligar_o_farm_desta_cave" in dentro


# ===========================================================================
# O desfecho desliga o farm DA CAVE CERTA
# ===========================================================================


def _contexto_falso(cave: str) -> object:
    conta = Account(login="a", last_char_name="Farmer", password_enc="x")
    conta.bc_farm = True
    conta.hh_farm = True

    from blazesbot.bot.context import BotContext
    ctx = object.__new__(BotContext)
    ctx.account = conta
    ctx.cave_em_farm = cave
    return ctx


def test_desligar_o_farm_da_HH_nao_toca_no_BC():
    ctx = _contexto_falso(CAVE_HH)
    assert ctx.desligar_o_farm_desta_cave() == CAVE_HH
    assert ctx.account.hh_farm is False
    assert ctx.account.bc_farm is True, (
        "vetar a HH não pode desligar o BC desta conta")


def test_desligar_o_farm_do_BC_nao_toca_na_HH():
    ctx = _contexto_falso(CAVE_BC)
    assert ctx.desligar_o_farm_desta_cave() == CAVE_BC
    assert ctx.account.bc_farm is False
    assert ctx.account.hh_farm is True


def test_sem_saber_a_cave_desliga_AS_DUAS():
    """Direção segura: quem chega aqui já concluiu que o farm não segue.

    Deixar um interruptor ligado por falta de informação faria a conta voltar a
    farmar exatamente o que acabou de ser vetado.
    """
    ctx = _contexto_falso("")
    ctx.desligar_o_farm_desta_cave()
    assert ctx.account.bc_farm is False
    assert ctx.account.hh_farm is False


# ===========================================================================
# Nenhuma cave tem régua própria
# ===========================================================================


def test_NENHUMA_cave_tem_a_propria_regua_de_reseter_online():
    """Uma cópia por cave divergiria, e a que ficasse para trás perderia runs."""
    for modulo in (BossRushRoutine, HHRoutine):
        fonte = inspect.getsource(inspect.getmodule(modulo))
        assert "reseter_online" not in fonte, (
            f"{modulo.__name__} voltou a ter a própria régua")
        assert "silencio_do_reseter" not in fonte


def test_a_trava_mora_em_bot_e_nao_em_core():
    """O critério é o que o módulo IMPORTA: ele recebe `BotContext`."""
    assert trava.__name__ == "blazesbot.bot.espera_do_reseter"
    assert "BotContext" in inspect.getsource(trava)


def test_a_documentacao_de_transicao_esta_no_modulo():
    """Quem promove escreve no código que aquilo é dependência cruzada.

    Regra permanente do projeto (`CLAUDE.md`, REUSO E PROMOÇÃO, item 4): quem
    usa, de onde veio, o que NÃO subiu e por quê. Mexer ali mexe em todos.
    """
    doc = trava.__doc__ or ""
    assert "DEPENDÊNCIA CRUZADA" in doc
    assert "QUEM USA" in doc
    assert "DE ONDE VEIO" in doc
    assert "NÃO** SUBIU" in doc or "NÃO SUBIU" in doc
