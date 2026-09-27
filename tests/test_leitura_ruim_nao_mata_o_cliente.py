"""Leitura de memória ilegível com o cliente vivo NÃO fecha o jogo.

Achado A2 da auditoria de 27/09/2026. Seis pontos levantam `Disconnected` numa
única leitura `None` da posição (navegação, venda, combate), e o `run()` tratava
todo `Disconnected` matando o cliente -- contra a regra de que só desconexão
CONFIRMADA fecha o jogo, com a fila de login custando horas em dia cheio.
"""
import inspect
from types import SimpleNamespace

from blazesbot.bot import supervisor as mod
from blazesbot.bot.supervisor import AccountSupervisor
from blazesbot.bot.watchdog import DcReason


def _sup(confirmada=False, pid=123, hwnd=456):
    sup = AccountSupervisor.__new__(AccountSupervisor)
    sup._queda_confirmada = confirmada
    sup.pid, sup.hwnd = pid, hwnd
    return sup


def _saude(monkeypatch, motivo):
    monkeypatch.setattr(mod.win32gui, "IsWindow", lambda _h: True)
    monkeypatch.setattr(mod, "avaliar_saude", lambda *_a: (motivo, None))


def test_leitura_ruim_com_o_cliente_SAO_nao_e_queda(monkeypatch):
    _saude(monkeypatch, DcReason.NONE)
    assert _sup()._a_queda_esta_confirmada() is False


def test_a_queda_ANOTADA_pelo_watchdog_ou_vigia_e_queda(monkeypatch):
    _saude(monkeypatch, DcReason.NONE)
    assert _sup(confirmada=True)._a_queda_esta_confirmada() is True


def test_processo_ou_janela_SUMIDOS_ou_caixa_de_conexao_e_queda(monkeypatch):
    for motivo in (DcReason.PROCESS_GONE, DcReason.WINDOW_GONE,
                   DcReason.RECONNECT_DIALOG):
        _saude(monkeypatch, motivo)
        assert _sup()._a_queda_esta_confirmada() is True, motivo


def test_NAO_SEI_nao_mata(monkeypatch):
    def _estoura(*_a):
        raise OSError("sem acesso ao processo")

    monkeypatch.setattr(mod.win32gui, "IsWindow", lambda _h: True)
    monkeypatch.setattr(mod, "avaliar_saude", _estoura)
    assert _sup()._a_queda_esta_confirmada() is False


def test_o_funil_do_historico_diz_se_houve_queda(monkeypatch):
    sup = _sup()
    sup.account = SimpleNamespace(login="conta")
    monkeypatch.setattr(mod.sentinela, "cobrar_a_queda", lambda _login: None)
    ctx = SimpleNamespace(ultima_queda=None)
    assert sup._registrar_queda(ctx) is False, "leitura ruim virou queda"


def test_o_run_so_encerra_o_cliente_com_a_queda_confirmada():
    fonte = inspect.getsource(AccountSupervisor.run)
    bloco = fonte[fonte.index("except Disconnected as exc:"):]
    bloco = bloco[:bloco.index("except LoginError")]
    assert bloco.index("_a_queda_esta_confirmada()") < bloco.index("_encerrar_caido(")
    assert "self._teardown()" in bloco
