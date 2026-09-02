"""A espera pelo teleporte da Fay (Stone City -> Ghost Din Woods).

A ESPERA mora em `bot/ui_do_jogo.esperar_a_chegada` desde 01/09/2026 (a HH
usa a mesma); a PERGUNTA "cheguei?" continua na BC, porque é a coordenada
dela que responde. Este teste exercita os dois juntos, que é como rodam.

Era `ctx.tick(4.0)` cego. Medido no log de dev de 13/08/2026: 6,1 s entre o
clique no link e o "Teleportado", e o painel de arredores abrindo 40 ms depois
disso — ou seja, a demora inteira era espera, não trabalho.

Relógio determinístico começando em valor NÃO-ZERO, pelo mesmo motivo dos
outros testes desta base: `0.0` é sentinela em várias variáveis e já mascarou
defeito aqui.
"""
import pytest

from blazesbot.bot import ui_do_jogo
from blazesbot.bot.bc import mapa_bc, ui_service
from blazesbot.bot.bc.ui_service import UIService

INSTANTE_INICIAL = 5_000.0

EM_STONE_CITY = (178, -518)
EM_GHOST_DIN = (1372, -417)


class _Relogio:
    def __init__(self):
        self.agora = INSTANTE_INICIAL

    def __call__(self):
        return self.agora

    def avancar(self, s):
        self.agora += s


class _Log:
    def __init__(self):
        self.linhas = []

    def _guardar(self, nivel):
        def escrever(msg, *args):
            self.linhas.append((nivel, msg % args if args else msg))
        return escrever

    def __getattr__(self, nome):
        return self._guardar(nome)


class _Ctx:
    def __init__(self, relogio, posicoes):
        """`posicoes` é uma função de segundos-decorridos -> posição."""
        self._relogio = relogio
        self._posicoes = posicoes
        self.log = _Log()
        self.hwnd = 1
        self.memory = self

    # -- memória --
    def position(self):
        return self._posicoes(self._relogio.agora - INSTANTE_INICIAL)

    def location(self):
        return "Ghost Din Woods" if self.position() == EM_GHOST_DIN \
            else "Stone City"

    # -- fluxo --
    def raise_if_stopped(self):
        pass

    def tick(self, s=0.2):
        self._relogio.avancar(s)


def _ui(monkeypatch, posicoes):
    relogio = _Relogio()
    ui = object.__new__(UIService)
    ui.ctx = _Ctx(relogio, posicoes)
    monkeypatch.setattr(ui_do_jogo.time, "time", relogio)
    return ui, relogio


def _decorrido(relogio):
    return relogio.agora - INSTANTE_INICIAL


def test_sai_no_instante_em_que_a_chegada_confirma(monkeypatch):
    """O teleporte acontece em 1,2 s: a espera tem que acabar aí, não no teto."""
    ui, relogio = _ui(
        monkeypatch,
        lambda t: EM_GHOST_DIN if t >= 1.2 else EM_STONE_CITY)

    assert ui._esperar_o_teleporte() is True
    assert 1.2 <= _decorrido(relogio) < 1.5


def test_confirma_na_primeira_leitura_se_ja_chegou(monkeypatch):
    """Teleporte instantâneo não paga nada."""
    ui, relogio = _ui(monkeypatch, lambda t: EM_GHOST_DIN)

    assert ui._esperar_o_teleporte() is True
    assert _decorrido(relogio) == 0.0


def test_o_teto_e_de_tres_segundos(monkeypatch):
    """Pedido do usuário. Sem chegar, a espera não passa disso."""
    ui, relogio = _ui(monkeypatch, lambda t: EM_STONE_CITY)

    assert ui._esperar_o_teleporte() is False
    assert _decorrido(relogio) <= ui_service.TETO_DO_TELEPORTE_DA_FAY + 0.2


def test_o_teto_estourado_AVISA_no_log(monkeypatch):
    """Se 3 s for pouco, é a linha do log que traz o número para decidir —
    em vez de o bot seguir em silêncio de dentro de Stone City."""
    ui, _ = _ui(monkeypatch, lambda t: EM_STONE_CITY)
    ui._esperar_o_teleporte()

    niveis = [n for n, _ in ui.ctx.log.linhas]
    texto = "\n".join(m for _, m in ui.ctx.log.linhas)
    assert "warning" in niveis
    assert "NÃO confirmado" in texto


def test_sem_leitura_de_posicao_nao_conta_como_chegada(monkeypatch):
    """"Não sei" não é "cheguei" — a mesma regra do resto da base."""
    ui, relogio = _ui(monkeypatch, lambda t: None)

    assert ui._esperar_o_teleporte() is False
    assert _decorrido(relogio) >= ui_service.TETO_DO_TELEPORTE_DA_FAY


def test_a_confirmacao_e_pela_coordenada_e_nao_pelo_nome(monkeypatch):
    """O campo de nome tem falha medida de ficar preso na área anterior. Aqui
    ele MENTE dizendo Stone City, e a coordenada manda."""
    ui, relogio = _ui(monkeypatch, lambda t: EM_GHOST_DIN)
    monkeypatch.setattr(type(ui.ctx), "location", lambda self: "Stone City")

    assert ui._esperar_o_teleporte() is True
    assert _decorrido(relogio) == 0.0


@pytest.mark.parametrize("pos, chegou", [
    (EM_STONE_CITY, False),
    (mapa_bc.POSICAO_DA_FAY, False),
    (mapa_bc.POSICAO_DO_VENDEDOR, False),
    (EM_GHOST_DIN, True),
    (mapa_bc.ENTRADA_EM_GHOST_DIN, True),
])
def test_o_criterio_de_chegada_separa_os_dois_mapas(pos, chegou):
    assert mapa_bc.x_contradiz_a_cave(pos) is chegou


def test_o_teto_esta_em_um_e_meio_segundo_no_codigo():
    assert ui_service.TETO_DO_TELEPORTE_DA_FAY == 2.0
