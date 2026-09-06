"""No BC não se desmonta antes do waypoint dos Gun Witch.

=========================================================================
A REGRESSÃO, MEDIDA EM 06/09/2026
=========================================================================

Regra do usuário: *"Em BC nunca deve sair da montaria até chegar no waypoint
dos Gun Witch"* -- no caminho do covil os mobs são para IGNORAR.

Em 04/09 a HH pediu o contrário (*"junto com os boss tem vários mobs que
precisam ser mortos"*), e a matança entrou direto no laço de deslocamento, que
é COMPARTILHADO. O BC herdou a decisão da HH sem ninguém pedir.

O log de 06/09, fase `ENTRAR_NO_COVIL`, conta `creubo`:

    Sem progresso indo para (242, 22) e EM BATALHA ... Matando até sair
    DESTRAVANDO (andar até (242, 22)) ...
    Desmontando antes da luta de destravar
    ...
    NAO DESTRAVEI em 60s: 9 morte(s), 8 TAB, 176 golpes

Sessenta segundos e nove mobs, a pé, num corredor que era para atravessar --
e ainda falhou.

=========================================================================
O QUE ESTE ARQUIVO TRAVA
=========================================================================

Não é "o BC não mata". É que **matar quando o TRAJETO trava** é decisão de
ecossistema, e o BC não a toma. O outro gancho -- matar quando o PORTÃO DA
MONTARIA não sobe -- continua ligado nos dois, porque ali matar é a única
saída: o jogo recusa a montaria em combate.
"""
from __future__ import annotations

import inspect

from blazesbot.bot import navegacao as nav
from blazesbot.bot.bc.routine import BossRushRoutine
from blazesbot.bot.hh.routine import HHRoutine


def _init(cls) -> str:
    return inspect.getsource(cls.__init__)


# ===========================================================================
# Os dois ganchos são DOIS
# ===========================================================================


def test_o_navegador_nasce_com_os_dois_ganchos_DESLIGADOS():
    """Quem quiser, liga. Foi por não ser assim que o BC regrediu."""
    fonte = _init(nav.Navigator)
    for gancho in ("destravar_o_combate", "matar_quando_o_trajeto_trava"):
        assert f"self.{gancho}: Callable[[str], bool] | None = None" in fonte


def test_a_parada_do_trajeto_usa_o_gancho_PROPRIO():
    """Se voltar a usar o do portão da montaria, o BC volta a desmontar."""
    fonte = inspect.getsource(nav.Navigator.follow_path)
    ramo = fonte[fonte.index("SEM_PROGRESSO_SEGUNDOS"):]
    corte = ramo.index("TETO_PRESO_NO_MESMO_PONTO")
    assert "matar_quando_o_trajeto_trava" in ramo[:corte]
    assert "self.destravar_o_combate" not in ramo[:corte], (
        "a parada do trajeto voltou a usar o gancho do portão da montaria")


def test_o_portao_da_montaria_continua_com_o_gancho_de_sempre():
    """Ali matar é a ÚNICA saída: o jogo recusa a montaria em combate.

    Foi o conserto do travamento de 24 minutos do BC em 31/08/2026, e vale
    para toda cave.
    """
    fonte = inspect.getsource(nav.Navigator._diagnosticar_o_portao)
    assert "self.destravar_o_combate" in fonte
    assert "matar_quando_o_trajeto_trava" not in fonte


# ===========================================================================
# Quem liga o quê
# ===========================================================================


def test_o_BC_NAO_mata_quando_o_trajeto_trava():
    """A regra do usuário: no caminho do covil, mob é para ignorar."""
    assert "matar_quando_o_trajeto_trava" not in _init(BossRushRoutine), (
        "o BC voltaria a desmontar no corredor do Altar Stone")


def test_a_HH_MATA_quando_o_trajeto_trava():
    """Regra do usuário: junto com os bosses há mobs que precisam morrer."""
    assert "matar_quando_o_trajeto_trava" in _init(HHRoutine)


def test_as_DUAS_caves_destravam_o_portao_da_montaria():
    """Este é universal -- não é preferência de cave, é recusa do jogo."""
    for cls in (BossRushRoutine, HHRoutine):
        assert "self.nav.destravar_o_combate" in _init(cls)
