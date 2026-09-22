"""A LISTA DE SERVIDORES TEM SAÍDA: o Cancel.

Relato do usuário (22/09/2026): *"já aconteceu do servidor reiniciar e, como
não entra, fica travado nessa tela específica de escolha de servidor"*.

Era o único ponto do login em que insistir não adiantava e sair não acontecia
sozinho:

  * servidor FORA DA LISTA -> `_do_server` levantava `LoginError` direto, e o
    supervisor voltava PARA A MESMA JANELA, que continua na lista. Mesmo erro,
    para sempre.
  * servidor OFFLINE ou reiniciando -> o Ok não faz nada. A tela continua
    `SERVER_LIST`, o laço devolve a fase para `SERVER`, e `_do_server` clica de
    novo. Para sempre.
"""
from __future__ import annotations

import pytest

from blazesbot.bot.login import VOLTAS_NA_LISTA_DE_SERVIDORES, LoginSequence
from blazesbot.bot.login_states import Phase
from blazesbot.core.coords import coords_for_size


class _Detector:
    def detect(self):
        return type("D", (), {"capture_ok": False, "frame": None})()

    def find_button(self, *a, **k):
        return None


def _login(servidor: str) -> LoginSequence:
    """Uma `LoginSequence` sem `__init__` -- só o que `_do_server` toca."""
    seq = object.__new__(LoginSequence)
    seq.coords = coords_for_size(1024, 768)
    seq.account = type("_Conta", (), {"server": servidor})()
    seq.log = __import__("logging").getLogger("teste.servidor")
    seq.detector = _Detector()
    seq.voltas_no_servidor = 0
    seq.phase = Phase.SERVER
    seq.cliques: list[tuple[int, int]] = []
    seq.fases: list[Phase] = []
    seq._click = lambda ponto: seq.cliques.append(ponto)
    seq._set_phase = lambda fase: seq.fases.append(fase)
    seq._abort_if_stopped = lambda: None
    return seq


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr("blazesbot.bot.login.sleep", lambda _s: None)


def test_servidor_FORA_DA_LISTA_sai_pelo_cancel_em_vez_de_levantar():
    """O `LoginError` seco deixava a janela parada na lista para sempre."""
    seq = _login("Servidor Que Nao Existe")
    seq._do_server()

    assert seq.cliques == [seq.coords.server_cancel], (
        "não clicou no Cancel — a conta fica presa na lista")
    assert seq.fases == [Phase.CREDENTIALS], (
        "não voltou para o login; o ciclo não recomeça")


def test_o_Ok_QUE_NAO_SAI_da_lista_acaba_no_cancel():
    """É o sintoma do servidor Offline e do que reiniciou -- o único que dá
    para medir sem template novo."""
    seq = _login("Light in the Darkness")

    for _ in range(VOLTAS_NA_LISTA_DE_SERVIDORES):
        seq._do_server()
    assert seq.coords.server_cancel not in seq.cliques, (
        "desistiu cedo demais — clique engolido é comum nesta UI")
    assert seq.fases[-1] is Phase.ENTERING

    seq._do_server()
    assert seq.cliques[-1] == seq.coords.server_cancel
    assert seq.fases[-1] is Phase.CREDENTIALS


def test_o_servidor_bom_entra_sem_passar_pelo_cancel():
    """A saída de emergência não pode atrapalhar o caminho normal."""
    seq = _login("Light in the Darkness")
    seq._do_server()

    assert seq.cliques[-1] == seq.coords.server_ok
    assert seq.coords.server_cancel not in seq.cliques
    assert seq.fases == [Phase.ENTERING]


def test_o_cancel_fica_a_direita_do_Ok_na_mesma_altura():
    """Medido no print 1:1 de 22/09/2026: Ok em x=557, Cancel em x=669.

    A folga é o próprio botão, que tem 57 px de largura
    (`data/templates/cancel.bmp`).
    """
    c = coords_for_size(1024, 768)
    assert c.server_cancel[1] == c.server_ok[1]
    assert c.server_cancel[0] - c.server_ok[0] == 112
