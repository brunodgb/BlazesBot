"""Campo de configuração de cave que NINGUÉM LÊ é defeito, não sobra.

=========================================================================
O DEFEITO QUE ESTE ARQUIVO IMPEDE DE VOLTAR
=========================================================================

Medido na conta do usuário em 03/09/2026. Ele pôs `hh.attack_delay = 0,1 s` na
aba da HH; as duas interfaces gravaram, o `config.json` guardou, e o bot atacava
com os **0,5 s do BC** -- porque `bot/combate.py` lia `ctx.settings.bc.attack_delay`
direto, em quatro lugares, independentemente de qual cave estava rodando.

Quatro campos do `HHConfig` estavam nesse estado: `attack_delay`,
`aoe_until_mana_pct`, `usar_skill_de_velocidade` e `limpar_mobs_a_cada`. Escritos
pela interface, lidos por ninguém.

E o pior deles não era um número: **`reset_nick`**. `TeamService.montar_time()`
lia `settings.bc.reset_nick`. O usuário configurou o campo da HH, o do BC
estava vazio, e a função devolvia `False` na primeira linha --
então a rotina caía em RECUPERAR e voltava a tentar, em laço, para sempre. A HH
nunca montava time, e sem time os bosses não renascem.

=========================================================================
POR QUE A VERIFICAÇÃO É ESTRUTURAL
=========================================================================

Não há comportamento errado para observar: a tela mostra o campo, aceita o
valor, grava no disco e relê corretamente -- `test_config_ida_e_volta.py` passa.
O que falta é ALGUÉM LER. É a mesma família do `Api.alternar_hh` que não
existia e da Fada que não curava: **suíte verde não prova que as peças estão
ligadas.**
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import fields
from pathlib import Path

import pytest

from blazesbot.config import CAVE_BC, CAVE_HH, AccountSettings, HHConfig

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "blazesbot"


def _fonte(metodo) -> str:
    return textwrap.dedent(inspect.getsource(metodo))


def _o_bot_le(nome: str) -> list[str]:
    """Os arquivos do BOT (não interface, não config) que leem aquele campo.

    Pelo AST: `getattr` textual pegaria a definição do dataclass, o payload da
    ponte web e o comentário que explica o campo.
    """
    achados = []
    for arquivo in PACOTE.rglob("*.py"):
        relativo = arquivo.relative_to(RAIZ).as_posix()
        # A INTERFACE não conta: ela grava e mostra. `config.py` não conta: é
        # onde o campo é declarado. O que interessa é quem AGE com o valor.
        if relativo in ("blazesbot/web_app.py", "blazesbot/config.py"):
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Attribute) and no.attr == nome:
                achados.append(f"{relativo}:{no.lineno}")
    return achados


# ===========================================================================
# TODO campo do HHConfig tem que ter um leitor no bot
# ===========================================================================

# Campos que NÃO são lidos pelo bot, e por quê. A exigência de o motivo estar
# escrito aqui é o que transforma "esqueci de ligar" em "decidi não ligar".
SEM_LEITOR_DECLARADO: dict[str, str] = {
    # `route` e `vendor` são sub-blocos: os campos DENTRO deles são lidos, e o
    # objeto em si não precisa ser.
    "route": "sub-bloco -- os campos dentro dele são lidos",
    "vendor": "sub-bloco -- os campos dentro dele são lidos",
}


@pytest.mark.parametrize("campo", [f.name for f in fields(HHConfig)])
def test_todo_campo_do_HHConfig_tem_leitor_no_bot(campo: str):
    """Campo que só a interface toca é campo que não faz nada.

    O usuário configura, a tela confirma, o disco guarda -- e o bot ignora. Foi
    exatamente o caso do `attack_delay` da HH.
    """
    if campo in SEM_LEITOR_DECLARADO:
        pytest.skip(f"`{campo}`: {SEM_LEITOR_DECLARADO[campo]}")
    leitores = _o_bot_le(campo)
    assert leitores, (
        f"`HHConfig.{campo}` é gravado pelas interfaces e NENHUM arquivo do bot "
        f"o lê. Ou ligue o campo em quem age, ou declare o motivo em "
        f"SEM_LEITOR_DECLARADO.")


@pytest.mark.parametrize("campo", ["sell_start_slot", "runs_before_selling"])
def test_o_vendor_da_HH_tem_leitor(campo: str):
    assert _o_bot_le(campo), f"`HHVendor.{campo}` não é lido pelo bot"


@pytest.mark.parametrize("campo", ["transport_search_text", "npc_search_text",
                                   "vendor_search_text"])
def test_a_rota_da_HH_tem_leitor(campo: str):
    assert _o_bot_le(campo), f"`HHRoute.{campo}` não é lido pelo bot"


# ===========================================================================
# OS MOTORES leem da cave que está rodando, não do BC
# ===========================================================================


def test_settings_cave_devolve_a_config_da_cave_certa():
    st = AccountSettings()
    assert st.cave(CAVE_HH) is st.hh
    assert st.cave(CAVE_BC) is st.bc
    # Nome desconhecido cai no BC: é o comportamento de antes, e a alternativa
    # seria o motor rodar sem número nenhum.
    assert st.cave("") is st.bc
    assert st.cave("qualquercoisa") is st.bc


def test_as_duas_caves_tem_os_MESMOS_nomes_para_os_campos_do_motor():
    """É isso que faz `ctx.cave` funcionar sem o motor saber qual cave é.

    Um nome diferente de um lado obrigaria um `if` por cave dentro do motor --
    e cada `if` desses é uma chance de mexer numa cave e quebrar a outra.
    """
    from blazesbot.config import BCConfig

    do_motor = {"attack_delay", "max_fight_seconds", "aoe_until_mana_pct",
                "usar_skill_de_velocidade"}
    campos_bc = {f.name for f in fields(BCConfig)}
    campos_hh = {f.name for f in fields(HHConfig)}
    faltando_bc = do_motor - campos_bc
    faltando_hh = do_motor - campos_hh
    assert not faltando_bc, f"o BC não tem: {faltando_bc}"
    assert not faltando_hh, f"a HH não tem: {faltando_hh}"


@pytest.mark.parametrize("arquivo,campo", [
    ("blazesbot/bot/combate.py", "attack_delay"),
    ("blazesbot/bot/velocidade.py", "usar_skill_de_velocidade"),
])
def test_o_motor_NAO_le_settings_bc_direto(arquivo: str, campo: str):
    """Ler `settings.bc.<campo>` num motor compartilhado é o defeito: a HH roda
    com os números do BC, e o campo dela fica morto."""
    fonte = (RAIZ / arquivo).read_text(encoding="utf-8")
    assert f"settings.bc.{campo}" not in fonte, (
        f"{arquivo} voltou a ler `settings.bc.{campo}` -- use `ctx.cave`")
    assert f"cave.{campo}" in fonte, f"{arquivo} não lê pela cave que roda"


def test_a_navegacao_le_os_waypoints_do_MAPA_e_nao_do_config():
    """`settings.route` é um atalho para `bc.route`: lê-lo na navegação traria
    os waypoints problemáticos da Bewitcher Cave para dentro da HH."""
    # PELO AST: a primeira versão comparou texto e casou com o próprio
    # comentário que explica por que `settings.route` não é lido ali.
    arvore = ast.parse((RAIZ / "blazesbot" / "bot" / "navegacao.py").read_text(
        encoding="utf-8"))
    lendo_route = [no.lineno for no in ast.walk(arvore)
                   if isinstance(no, ast.Attribute) and no.attr == "route"]
    assert not lendo_route, (
        f"a navegação lê `settings.route` nas linhas {lendo_route} -- é um "
        f"atalho para `bc.route` e traz os waypoints da BC para dentro da HH")
    # O nome chega por `getattr(self.mapa, "WAYPOINTS_PROBLEMATICOS", ())`,
    # então ele é uma STRING no AST, não um acesso a atributo -- o `getattr`
    # existe para cobrir o mapa ausente (`_SemMapa`).
    assert any(isinstance(no, ast.Constant)
               and no.value == "WAYPOINTS_PROBLEMATICOS"
               for no in ast.walk(arvore)), (
        "a navegação não pergunta os waypoints problemáticos ao mapa")


def test_os_dois_mapas_expoem_os_waypoints_problematicos():
    from blazesbot.bot.bc import mapa_bc
    from blazesbot.bot.hh import mapa_hh

    for mapa in (mapa_bc, mapa_hh):
        assert hasattr(mapa, "WAYPOINTS_PROBLEMATICOS"), mapa.__name__


# ===========================================================================
# O CRÍTICO: o time convida o reset DA CAVE QUE RODA
# ===========================================================================


def test_o_TeamService_NAO_le_o_reset_do_BC_direto_no_convite():
    """Era isto que deixava a HH sem time -- e sem time os bosses não
    renascem."""
    from blazesbot.bot.team import TeamService

    fonte = _fonte(TeamService.montar_time)
    assert "settings.bc.reset_nick" not in fonte
    assert "nick_do_reset()" in fonte


def test_A_CONTA_DE_RESET_NAO_E_MAIS_UM_CAMPO_DE_CAVE():
    """A classe do defeito acima foi FECHADA em 08/09/2026, não remendada.

    Enquanto existiam dois campos, "qual deles vale" era uma pergunta em aberto
    em todo código compartilhado -- e cada resposta errada custava uma cave sem
    time. Um campo só (`AccountSettings.reset_nick`) não tem essa pergunta.

    Este teste é a trava estrutural: reintroduzir `reset_nick` numa das caves
    reabriria os três estados impossíveis (preencher um e esquecer o outro,
    preencher os dois diferentes, e o código compartilhado sem saber qual ler).
    """
    from blazesbot.config import BCConfig, HHConfig

    assert "reset_nick" in AccountSettings.__dataclass_fields__, (
        "A conta de reset é do PERSONAGEM: uma por conta logada.")
    for classe in (BCConfig, HHConfig):
        assert "reset_nick" not in classe.__dataclass_fields__, (
            f"{classe.__name__} voltou a ter conta de reset própria.")

    # O MODO da HH continua sendo da HH: "solo ou fada" é decisão de cave.
    assert "modo_do_reset" in HHConfig.__dataclass_fields__


def test_cada_rotina_INJETA_o_nick_do_personagem():
    """A injeção CONTINUA existindo, e não é redundância.

    Ela é o que permite a uma cave futura ter reseter próprio sem mexer no
    `TeamService` -- e é o que impede o serviço de voltar a ler config direto,
    que foi a causa do defeito de 03/09/2026.
    """
    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    for rotina in (BossRushRoutine, HHRoutine):
        fonte = _fonte(rotina.__init__)
        assert "nick_do_reset=" in fonte, rotina.__name__
        assert "settings.reset_nick" in fonte, (
            f"{rotina.__name__} não injeta o campo do personagem")
        for antigo in ("settings.bc.reset_nick", "settings.hh.reset_nick"):
            assert antigo not in fonte, f"{rotina.__name__} lê {antigo}"


def test_sem_injecao_o_TeamService_usa_o_campo_do_personagem():
    """Comportamento para quem não passa nada -- ferramentas e testes."""
    from blazesbot.bot.team import TeamService

    servico = object.__new__(TeamService)
    servico._nick_do_reset = None
    servico.ctx = type("C", (), {"settings": AccountSettings()})()
    servico.ctx.settings.reset_nick = "ResetDaConta"
    assert servico.nick_do_reset() == "ResetDaConta"


def test_com_injecao_o_TeamService_usa_o_que_foi_injetado():
    from blazesbot.bot.team import TeamService

    servico = object.__new__(TeamService)
    st = AccountSettings()
    st.reset_nick = "ResetDaConta"
    servico._nick_do_reset = lambda: "OutroQualquer"
    servico.ctx = type("C", (), {"settings": st})()
    assert servico.nick_do_reset() == "OutroQualquer"


def test_o_aceitador_de_convite_le_o_campo_do_personagem():
    """Antes ele tinha que olhar as DUAS caves para não perder o reseter da HH.

    Com um campo só, a varredura é uma -- e não há como esquecer uma cave nova.
    """
    from blazesbot.bot.team import InviteAcceptor

    fonte = _fonte(InviteAcceptor._modo_estrito)
    assert "settings.reset_nick" in fonte
    assert "settings.bc.reset_nick" not in fonte
    assert "settings.hh.reset_nick" not in fonte
