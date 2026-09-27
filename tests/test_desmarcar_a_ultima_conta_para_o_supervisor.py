"""Desmarcar ou remover uma conta com o bot rodando PARA o supervisor dela.

Achado C2 da auditoria de 27/09/2026. `_App._sincronizar` só chamava
`sync_accounts` se `manager.running()`, e `running()` é `_ativo AND haver conta
habilitada`. Desmarcar a ÚLTIMA conta ativa zerava as habilitadas ANTES da
sincronização, que então era pulada: o supervisor seguia controlando um cliente
que o usuário desligou, a tela mostrava "Parado" e o botão Parar sumia.
`remover_conta` nem sincronizava.

`sync_accounts` já se protege sozinho da parada (`stop_event`), então quem
decide "há o que sincronizar" é existir um gerenciador, e não a intenção.
"""
from types import SimpleNamespace

from blazesbot.bot.supervisor import BotManager
from blazesbot.config import Account, BotConfig
from blazesbot.web_app import _App


class _SupervisorFalso:
    def __init__(self, login: str) -> None:
        self.account = SimpleNamespace(login=login)
        self.paradas: list[str] = []

    def is_alive(self) -> bool:
        return True

    def request_stop(self, motivo: str = "") -> None:
        self.paradas.append(motivo)


def _app_rodando(*logins_ativos: str, desligadas: tuple[str, ...] = ()):
    cfg = BotConfig()
    cfg.accounts = ([Account(login=x, enabled=True) for x in logins_ativos]
                    + [Account(login=x, enabled=False) for x in desligadas])
    cfg.garantir_uids_unicos()
    cfg.save = lambda: None                     # nada vai para data/config.json
    app = _App.__new__(_App)
    app._cfg = cfg
    app.config = cfg
    app._contagem_por_conta = {}
    app._status = lambda login, mensagem: None
    app.manager = BotManager(cfg)
    app.manager._ativo = True                   # o usuário apertou Iniciar
    supervisores = {x: _SupervisorFalso(x) for x in logins_ativos}
    app.manager.supervisors = list(supervisores.values())
    uid = {c.login: c.uid for c in cfg.accounts}
    return app, supervisores, uid


def test_desmarcar_a_ULTIMA_conta_ativa_para_o_supervisor_dela():
    app, sups, uid = _app_rodando("unica")
    app.alternar(uid["unica"], False)
    assert sups["unica"].paradas, "a conta desmarcada continuou rodando"


def test_remover_uma_conta_rodando_para_o_supervisor_dela():
    app, sups, uid = _app_rodando("fica", "sai")
    app.remover_conta(uid["sai"])
    assert sups["sai"].paradas, "a conta removida continuou rodando"
    assert not sups["fica"].paradas, "a outra conta não tinha nada com isso"


def test_com_o_bot_PARADO_desmarcar_nao_sobe_nem_para_nada():
    """Depois do Parar (intenção desfeita, `stop_event` setado) nada acontece."""
    app, sups, uid = _app_rodando("a", "b")
    app.manager._ativo = False
    app.manager.stop_event.set()
    app.alternar(uid["a"], False)
    assert not sups["a"].paradas and not sups["b"].paradas


def test_gerenciador_que_NUNCA_INICIOU_nao_sobe_conta_ao_marcar(monkeypatch):
    """Um `start()` que estourou deixa o gerenciador guardado sem intenção de
    rodar: marcar uma conta não pode subir supervisor sem ninguém apertar
    Iniciar."""
    from blazesbot.bot import supervisor as mod_sup

    subidos = []
    monkeypatch.setattr(mod_sup, "AccountSupervisor",
                        lambda **kw: subidos.append(kw) or _SupervisorFalso("x"))
    app, _sups, uid = _app_rodando(desligadas=("nova",))
    app.manager._ativo = False
    app.alternar(uid["nova"], True)
    assert subidos == [], "subiu supervisor sem o Iniciar"
