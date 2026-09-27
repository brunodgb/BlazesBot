"""O CÍRCULO DE OFFSETS, desligado por interruptor e testado ligado.

Saiu do fluxo por decisão do usuário ("só use o cálculo dos waypoints
vizinhos"), mas pela chamada APAGADA: ficou sem chamador e sem teste, contra a
regra "caminho fora de uso vira interruptor, com teste forçando-o ligado".
Achados S07-05/T3-10 da auditoria de 27/09/2026.
"""
import inspect
import logging
from types import SimpleNamespace

from blazesbot.bot import circulo_de_offsets, navegacao


class _Nav:
    """Só o que o círculo toca no `Navigator`."""

    def __init__(self, anda_no_clique: int = 3, goto_chega: bool = True):
        self.ctx = SimpleNamespace(raise_if_stopped=lambda: None,
                                   log=logging.getLogger("teste.circulo"))
        self.mapa = SimpleNamespace(tolerancia_do_waypoint=lambda wp, a, b: 7)
        self.cliques: list[tuple] = []
        self.gotos: list[tuple] = []
        self._anda_no_clique = anda_no_clique
        self._goto_chega = goto_chega

    def position(self):
        return (100, 100)

    def _clicar_offset_e_verificar(self, centro, raio, dx, dy):
        self.cliques.append((centro, raio))
        return len(self.cliques) >= self._anda_no_clique

    def goto(self, alvo, **_kw):
        self.gotos.append(alvo)
        return self._goto_chega


ROTA = (SimpleNamespace(pos=(120, 100)),)


def test_LIGADO_o_circulo_comeca_pela_propria_posicao_e_confirma_o_waypoint():
    nav = _Nav(anda_no_clique=3)
    assert circulo_de_offsets.tentar(nav, ROTA, 0) == 0
    assert nav.cliques[0][0] == (100, 100), "Q4: o próprio personagem primeiro"
    assert nav.gotos == [(120, 100)]


def test_clique_que_nao_anda_nunca_devolve_None():
    nav = _Nav(anda_no_clique=10**9)
    assert circulo_de_offsets.tentar(nav, ROTA, 0) is None
    assert nav.gotos == []


def test_o_interruptor_esta_DESLIGADO_e_guarda_a_chamada_no_ponto_antigo():
    assert navegacao.USAR_CIRCULO_DE_OFFSETS is False
    fonte = inspect.getsource(navegacao.Navigator.follow_path)
    guarda = fonte.index("if alcancado is None and USAR_CIRCULO_DE_OFFSETS:")
    assert "circulo_de_offsets.tentar(" in fonte[guarda:guarda + 250]
