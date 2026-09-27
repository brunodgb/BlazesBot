"""O relogin NÃO fotografa a base da trava do APP -- só o arranque do usuário.

Achado C5 da auditoria de 27/09/2026. `_rodar_modo_app` roda de novo a cada
relogin, e cada entrada regravava a base persistida com a posição daquele
instante. Em 24/09 03:05 um relogin caiu em OUTRO personagem e trocou a base
(1864, 1674) por (303, -447): ~1 h e 740 voltas abortadas, e o ponto do usuário
apagado do config.
"""
import logging
from types import SimpleNamespace

from blazesbot.bot.supervisor import AccountSupervisor


def _supervisor():
    sup = AccountSupervisor.__new__(AccountSupervisor)
    sup._base_do_app_capturada = False
    sup.gravacoes = []
    sup.config = SimpleNamespace(save=lambda: sup.gravacoes.append(1))
    return sup


def _memoria(pos):
    return SimpleNamespace(position=lambda: pos)


LOG = logging.getLogger("teste.base_do_app")


def test_o_ARRANQUE_grava_a_base():
    sup, app = _supervisor(), SimpleNamespace(_base_pos_x=0, _base_pos_y=0)
    sup._capturar_a_base_do_app(app, _memoria((1864, 1674)), LOG, "teste")
    assert (app._base_pos_x, app._base_pos_y) == (1864, 1674)
    assert sup.gravacoes == [1]


def test_o_RELOGIN_longe_do_ponto_NAO_regrava_a_base():
    sup, app = _supervisor(), SimpleNamespace(_base_pos_x=0, _base_pos_y=0)
    sup._capturar_a_base_do_app(app, _memoria((1864, 1674)), LOG, "arranque")
    sup._capturar_a_base_do_app(app, _memoria((303, -447)), LOG, "relogin")
    assert (app._base_pos_x, app._base_pos_y) == (1864, 1674)
    assert sup.gravacoes == [1], "o relogin gravou o config de novo"


def test_leitura_ruim_no_arranque_nao_gasta_a_foto():
    """Posição ilegível ou zerada não conta como foto: a próxima tenta de novo."""
    sup, app = _supervisor(), SimpleNamespace(_base_pos_x=0, _base_pos_y=0)
    sup._capturar_a_base_do_app(app, _memoria(None), LOG, "arranque")
    sup._capturar_a_base_do_app(app, _memoria((0, 0)), LOG, "arranque")
    assert sup._base_do_app_capturada is False and sup.gravacoes == []
    sup._capturar_a_base_do_app(app, _memoria((10, 20)), LOG, "arranque")
    assert (app._base_pos_x, app._base_pos_y) == (10, 20)


def test_desligar_o_APP_devolve_a_foto_ao_proximo_arranque():
    """O fim de `_rodar_modo_app` com o APP desligado zera a marca."""
    import inspect

    fonte = inspect.getsource(AccountSupervisor._rodar_modo_app)
    fim = fonte[fonte.rindex("if not app.enabled:"):]
    assert "self._base_do_app_capturada = False" in fim.split("def ")[0]
