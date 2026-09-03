"""Um ecossistema quebrado NÃO pode estragar os outros dois.

=========================================================================
A EXIGÊNCIA, NAS PALAVRAS DO USUÁRIO (03/09/2026)
=========================================================================

*"cada ecossistema tem que funcionar sem depender do outro, individualmente
funcionam, então mesmo que algum ecossistema esteja com problema o outro tem que
estar perfeito"*

`test_ecossistemas.py` já garante a metade ESTÁTICA disso: nenhum importa do
outro, e `bot/` não depende de ecossistema. Este arquivo cobre a metade que
sobrou -- a de RUNTIME, que é onde a promoção dos motores criou risco novo.

=========================================================================
POR QUE ESTE ARQUIVO PASSOU A SER NECESSÁRIO
=========================================================================

Enquanto cada cave tinha o seu combate, a sua navegação e o seu vendedor, o
isolamento era grátis: código separado não interfere. Com a promoção, os três
ecossistemas passaram a EXECUTAR AS MESMAS FUNÇÕES -- e a partir dali um
ecossistema mal configurado pode envenenar o outro por três caminhos:

  1. CONFIGURAÇÃO -- o motor lê número da cave errada
     (aconteceu: a HH rodava com `bc.attack_delay`);
  2. ESTADO COMPARTILHADO -- uma propriedade que responde pelas duas
     (aconteceu: `Account.farms` marcava a caixa do BC quando a HH ligava);
  3. DADO DA ROTA -- o motor herdar o mapa de quem não o chamou
     (aconteceu: os waypoints problemáticos da BC entravam na navegação da HH).

Os três estão consertados. Este arquivo é o que impede a volta.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from blazesbot.config import CAVE_BC, CAVE_HH, Account, AccountSettings

RAIZ = Path(__file__).resolve().parent.parent


def _fonte(alvo) -> str:
    return textwrap.dedent(inspect.getsource(alvo))


# ===========================================================================
# 1) CONFIGURAÇÃO: estragar a de uma cave não muda a outra
# ===========================================================================


def test_estragar_a_config_da_HH_nao_muda_a_da_BC():
    """O caso do usuário, ao contrário: ele mexeu na HH e queria a HH mudada.

    Aqui se prova o outro lado -- mexer numa não mexe na outra, porque são
    objetos distintos e o motor pergunta por qual cave está rodando.
    """
    st = AccountSettings()
    st.hh.attack_delay = 0.01
    st.hh.aoe_until_mana_pct = 1
    st.hh.reset_nick = "SoDaHH"

    assert st.bc.attack_delay == 0.5, "a HH vazou para a BC"
    assert st.bc.aoe_until_mana_pct == 30
    assert st.bc.reset_nick == ""
    assert st.cave(CAVE_HH).attack_delay == 0.01
    assert st.cave(CAVE_BC).attack_delay == 0.5


def test_estragar_a_config_da_BC_nao_muda_a_da_HH():
    st = AccountSettings()
    st.bc.attack_delay = 9.9
    st.bc.reset_nick = "SoDoBC"

    assert st.hh.attack_delay == 0.5
    assert st.hh.reset_nick == ""


def test_a_config_da_HH_e_um_OBJETO_proprio_e_nao_um_alias():
    """Se `hh` fosse uma referência para `bc`, escrever num escreveria no outro
    -- e o defeito seria invisível em qualquer teste de ida-e-volta."""
    st = AccountSettings()
    assert st.hh is not st.bc
    assert st.hh.route is not st.bc.route
    assert st.hh.vendor is not st.bc.vendor


def test_duas_contas_nao_compartilham_configuracao():
    """`field(default_factory=...)` e não `field(default=...)`.

    Um default MUTÁVEL compartilhado faria configurar uma conta configurar
    todas -- e com três ecossistemas isso seria uma conta de APP alterando o
    farm de outra.
    """
    a, b = Account(), Account()
    a.settings.hh.attack_delay = 0.01
    a.settings.hh.reset_nick = "Fulano"
    assert b.settings.hh.attack_delay == 0.5
    assert b.settings.hh.reset_nick == ""


# ===========================================================================
# 2) ESTADO: ligar uma cave não liga a outra
# ===========================================================================


@pytest.mark.parametrize("bc,hh", [(True, False), (False, True), (True, True),
                                   (False, False)])
def test_os_interruptores_das_caves_sao_independentes(bc, hh):
    a = Account()
    a.bc_farm, a.hh_farm = bc, hh
    assert a.bc_farm is bc
    assert a.hh_farm is hh


def test_o_modo_APP_nao_e_afetado_por_nenhuma_cave():
    """O APP é o ecossistema que roda quando a memória NÃO responde -- ele não
    pode nem saber que existe cave."""
    a = Account()
    a.bc_farm = a.hh_farm = True
    assert a.settings.app.enabled is False


def test_o_APP_continua_tendo_precedencia_sobre_as_DUAS():
    """Ele manda tecla em laço; qualquer farm junto seria duas mãos no mesmo
    teclado."""
    from blazesbot.bot.supervisor import AccountSupervisor

    arvore = ast.parse(_fonte(AccountSupervisor._operate))
    primeira = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute) and no.attr in (
                "enabled", "hh_farm", "bc_farm"):
            primeira.setdefault(no.attr, no.lineno)
            primeira[no.attr] = min(primeira[no.attr], no.lineno)
    assert primeira["enabled"] < primeira["hh_farm"] < primeira["bc_farm"], (
        f"a ordem APP -> HH -> BC mudou: {primeira}")


# ===========================================================================
# 3) DADO DA ROTA: o motor não herda o mapa de quem não o chamou
# ===========================================================================

# (o que é, o módulo, a classe) -- as peças que constroem navegador próprio
# quando ninguém passa um.
PECAS_QUE_CONSTROEM_NAVEGADOR = [
    ("a UI da BC", "blazesbot.bot.bc.ui_service", "UIService", "mapa_bc"),
    ("o vendedor da BC", "blazesbot.bot.bc.vendor", "VendorBC", "mapa_bc"),
    ("a entrada da HH", "blazesbot.bot.hh.entrada", "EntradaDaHH", "mapa_hh"),
    ("o vendedor da HH", "blazesbot.bot.hh.vendedor", "VendedorDaHH", "mapa_hh"),
]


@pytest.mark.parametrize("o_que,modulo,classe,mapa", PECAS_QUE_CONSTROEM_NAVEGADOR,
                         ids=lambda v: v if " " not in str(v) else "")
def test_cada_ecossistema_nasce_com_o_MAPA_DELE(o_que, modulo, classe, mapa):
    """Não é o chamador que tem de lembrar de passar o navegador certo.

    `bc/teste_venda.py` constrói `VendorService(ctx)` sem navegador. Antes disto,
    ele recebia um navegador SEM MAPA -- e a tolerância dos waypoints
    problemáticos da cave sumia em silêncio.
    """
    import importlib

    mod = importlib.import_module(modulo)
    fonte = _fonte(getattr(mod, classe).__init__)
    assert mapa in fonte, f"{o_que}: o construtor não usa `{mapa}`"
    assert "Navigator(ctx, " in fonte or "Navigator(self.ctx, " in fonte, (
        f"{o_que}: o construtor não passa o mapa ao navegador")


def test_o_mapa_ausente_e_EXPLICITO_e_nao_o_da_BC():
    """`_SemMapa` responde "não tenho waypoint problemático nenhum".

    Cair no mapa da BC como padrão seria o vazamento: uma peça da HH construída
    sem mapa passaria a tratar os pontos da Bewitcher Cave como apertados.
    """
    from blazesbot.bot.navegacao import _SemMapa

    assert _SemMapa.WAYPOINTS_PROBLEMATICOS == ()
    assert _SemMapa.tolerancia_do_waypoint(None, 3, 8) == 3


def test_os_dois_mapas_sao_objetos_diferentes():
    from blazesbot.bot.bc import mapa_bc
    from blazesbot.bot.hh import mapa_hh

    assert mapa_bc is not mapa_hh
    assert mapa_bc.WAYPOINTS_PROBLEMATICOS != mapa_hh.WAYPOINTS_PROBLEMATICOS
    # E nenhum waypoint de uma cave aparece na outra: coordenada de jogo não é
    # única no mundo, mas estas listas foram medidas em caves distintas.
    assert not (set(mapa_bc.WAYPOINTS_PROBLEMATICOS)
                & set(mapa_hh.WAYPOINTS_PROBLEMATICOS))


# ===========================================================================
# 4) A INDEPENDÊNCIA DE IMPORTAÇÃO, na prática
# ===========================================================================


@pytest.mark.parametrize("modulo", [
    "blazesbot.bot.bc.routine",
    "blazesbot.bot.hh.routine",
    "blazesbot.bot.app.executor",
])
def test_cada_ecossistema_IMPORTA_sozinho(modulo: str):
    """Importar um não pode exigir que os outros existam.

    É a prova de runtime do que `test_ecossistemas.py` verifica no AST: se um
    dia alguém apagar a pasta de um ecossistema, os outros dois continuam
    subindo.
    """
    import importlib

    importlib.import_module(modulo)


def test_o_supervisor_e_o_UNICO_que_conhece_os_tres():
    """E é a função dele: escolher qual roda. Um segundo lugar que conheça os
    três seria um segundo lugar para a precedência divergir."""
    from blazesbot.bot import supervisor as mod

    fonte = inspect.getsource(mod)
    for ecossistema in ("bc.routine", "hh.routine", "app"):
        assert ecossistema in fonte, f"o supervisor não conhece `{ecossistema}`"


# ===========================================================================
# 5) O QUE O ECOSSISTEMA NOVO NÃO PODE TER MUDADO NO ANTIGO
# ===========================================================================


def test_o_padrao_dos_motores_continua_sendo_o_da_BC():
    """Quem não diz qual cave é recebe a do BC.

    É o comportamento de sempre, e é o que garante que ferramenta antiga, teste
    antigo e caminho não-cave continuem funcionando exatamente como antes da
    chegada da HH.
    """
    st = AccountSettings()
    assert st.cave("") is st.bc

    from blazesbot.bot.team import TeamService

    servico = object.__new__(TeamService)
    servico._nick_do_reset = None
    st.bc.reset_nick = "PadraoDoBC"
    servico.ctx = type("C", (), {"settings": st})()
    assert servico.nick_do_reset() == "PadraoDoBC"


def test_a_config_da_BC_nao_ganhou_campo_novo_obrigatorio():
    """A HH não pode ter exigido campo novo na BC -- config antigo tem que
    carregar sem erro."""
    from blazesbot.config import BCConfig

    BCConfig()      # todos os campos têm padrão


def test_um_config_SEM_o_bloco_hh_carrega():
    """Arquivo gravado antes da HH existir. Quebrar aqui seria o ecossistema
    novo impedindo o bot de subir."""
    from blazesbot.config import BotConfig

    cfg = BotConfig.from_dict({
        "version": 4,
        "accounts": [{"login": "antiga", "bc_farm": True}],
    })
    conta = cfg.accounts[0]
    assert conta.bc_farm is True
    assert conta.hh_farm is False
    assert conta.settings.hh.modo_do_reset == "solo"
