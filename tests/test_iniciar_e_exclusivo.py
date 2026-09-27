"""UM DONO POR VEZ para os clientes do jogo: Iniciar e as ferramentas se excluem.

Achado C1 da auditoria de 27/09/2026. `_App.iniciar` criava um `BotManager` novo
sem olhar o anterior: um clique duplo (o botão se reabilita antes de o poll de
1,5 s mostrar "Rodando"), um Parar->Iniciar com as threads antigas saindo, ou
um Iniciar no meio de um teste punham dois remetentes de tecla no mesmo cliente,
e o manager órfão ficava fora do alcance do Parar. As ferramentas só conferiam
o sentido ferramenta->bot, e pela intenção, que cai antes de as threads saírem.
"""
from types import SimpleNamespace

from blazesbot.bot.app import afericao
from blazesbot.bot.bc import amostragem_de_cliques, teste_venda
from blazesbot.bot.supervisor import BotManager
from blazesbot.config import BotConfig
from blazesbot.web_app import _App


class _Sup:
    def __init__(self, vivo: bool) -> None:
        self.account = SimpleNamespace(login="conta")
        self._vivo = vivo

    def is_alive(self) -> bool:
        return self._vivo


def _app(quer_rodar=False, supervisor_vivo=False):
    cfg = BotConfig()
    cfg.save = lambda: None
    app = _App.__new__(_App)
    app._cfg = cfg
    app.config = cfg
    app._status = lambda login, mensagem: None
    app.manager = BotManager(cfg)
    app.manager._ativo = quer_rodar
    app.manager.supervisors = [_Sup(supervisor_vivo)]
    return app


def test_iniciar_com_o_bot_RODANDO_e_recusado_e_o_manager_nao_troca():
    app = _app(quer_rodar=True, supervisor_vivo=True)
    antes = app.manager
    r = app.iniciar()
    assert r["ok"] is False and r["erros"]
    assert app.manager is antes, "o manager antigo ficaria órfão, fora do Parar"


def test_iniciar_com_contas_AINDA_ENCERRANDO_e_recusado():
    """Parar só sinaliza: a intenção cai na hora, a thread sai depois."""
    app = _app(quer_rodar=False, supervisor_vivo=True)
    assert app.iniciar()["ok"] is False


def test_iniciar_no_meio_de_um_TESTE_e_recusado():
    app = _app()
    with teste_venda._EM_ANDAMENTO:
        r = app.iniciar()
    assert r["ok"] is False and "teste de venda" in r["erros"][0]


def test_iniciar_livre_segue_para_a_validacao():
    """Sem dono nenhum, a porta abre -- quem responde é a validação de sempre."""
    app = _app()
    problemas = app.config.validate()
    assert problemas, "config vazia deveria ter o que validar"
    assert app.iniciar() == {"ok": False, "erros": problemas}


def test_ferramenta_com_contas_ainda_encerrando_e_recusada():
    app = _app(quer_rodar=False, supervisor_vivo=True)
    r = app.testar_venda("qualquer")
    assert r["ok"] is False and "encerrando" in r["erro"]


def test_duas_FERRAMENTAS_nao_rodam_juntas():
    app = _app()
    with amostragem_de_cliques._EM_ANDAMENTO:
        r = app.conferir_modelos_de_exclusao("qualquer")
    assert r["ok"] is False and "amostragem" in r["erro"]
    with afericao._EM_ANDAMENTO:
        assert app.testar_venda("qualquer")["ok"] is False
