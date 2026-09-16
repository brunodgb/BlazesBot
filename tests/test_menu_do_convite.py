"""O MENU DE CONTEXTO DO CONVITE MUDA DE TAMANHO -- 16/09/2026.

Perto do convidado o cliente acrescenta as opções que só existem com o
personagem à vista (Follow, View Equipment, Trade, Duel...), e "Team up" desce
três linhas. O BC convida a conta de reset, que está do outro lado do mapa; o
APP convida quem está ao lado. Com um deslocamento só, um dos dois erra.

Qual menu veio se mede pela ALTURA da caixa que apareceu, e a medida erra
SEMPRE para o curto: "View Equipment" abre uma janela que fecha em seguida,
enquanto o item na altura do "Team up" longo, no menu curto, é "Recruit
Apprentice" -- um pedido de aprendiz para a outra conta.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pytest

from blazesbot.bot import team
from blazesbot.core.vision import altura_da_mudanca

# Onde o clique direito cai. Valor qualquer: o deslocamento é relativo a ele.
LINHA = (300, 200)
LARGURA_DA_CAIXA = 116          # o menu medido no print do usuário


def _cena() -> np.ndarray:
    return np.zeros((768, 1024, 3), dtype=np.uint8)


def _com_menu(altura: int) -> np.ndarray:
    """A cena com uma caixa opaca de `altura` px nascendo no ponto do clique."""
    quadro = _cena()
    x, y = LINHA
    quadro[y:y + altura, x:x + LARGURA_DA_CAIXA] = 200
    return quadro


def _servico(monkeypatch, depois, template=None, achado=None):
    svc = team.TeamService.__new__(team.TeamService)
    svc.ctx = SimpleNamespace(
        hwnd=1, templates=SimpleNamespace(load=lambda _n: template))
    monkeypatch.setattr(team, "capture_window", lambda _hwnd: depois)
    monkeypatch.setattr(team, "find_template", lambda *a, **k: achado)
    return svc


# ---------------------------------------------------------------------------
# A RÉGUA
# ---------------------------------------------------------------------------

def test_a_regua_para_na_primeira_linha_que_nao_mudou():
    """SEGUIDAS, e não "quantas mudaram": a cena se mexendo mais abaixo não
    pode esticar a caixa."""
    antes, depois = _cena(), _com_menu(150)
    x, y = LINHA
    depois[y + 400:y + 450, x:x + LARGURA_DA_CAIXA] = 200   # mob passando longe
    assert altura_da_mudanca(antes, depois, x + 32, y, 40, 300) == 150


def test_sem_quadro_a_regua_da_zero():
    assert altura_da_mudanca(None, _com_menu(150), 300, 200, 40, 300) == 0


def test_recorte_fora_da_tela_da_zero():
    """Fora da tela não há comparação -- e "não sei" não pode virar menu longo."""
    antes, depois = _cena(), _com_menu(150)
    assert altura_da_mudanca(antes, depois, 1000, 200, 40, 300) == 0


# ---------------------------------------------------------------------------
# ONDE CLICAR
# ---------------------------------------------------------------------------

def test_menu_CURTO_clica_no_quarto_item(monkeypatch):
    """Longe do convidado: 7 itens, "Team up" em +75. É o caso do BC."""
    svc = _servico(monkeypatch, _com_menu(150))
    x, y = LINHA
    alvo, origem = svc._achar_team_up(LINHA, _cena())
    assert alvo == (x + 32, y + 75), origem
    assert "perto" not in origem


def test_menu_LONGO_desce_tres_linhas(monkeypatch):
    """Perto: 12 itens, "Team up" três linhas abaixo. É o caso do APP."""
    svc = _servico(monkeypatch, _com_menu(255))
    x, y = LINHA
    alvo, origem = svc._achar_team_up(LINHA, _cena())
    assert alvo == (x + 32, y + 75 + 3 * 21), origem
    assert "perto" in origem


def test_SEM_captura_fica_no_curto(monkeypatch):
    """Sem quadro não há régua, e o curto é o lado barato de errar."""
    svc = _servico(monkeypatch, None)
    x, y = LINHA
    alvo, _ = svc._achar_team_up(LINHA, _cena())
    assert alvo == (x + 32, y + 75)


def test_a_regua_que_NUNCA_para_fica_no_curto(monkeypatch):
    """Tudo mudou = a tela inteira virou outra coisa (troca de mapa, cena se
    mexendo). Isso não é um menu, e tomar por menu longo clicaria em "Recruit
    Apprentice" se o menu fosse o curto."""
    svc = _servico(monkeypatch, np.full((768, 1024, 3), 200, dtype=np.uint8))
    x, y = LINHA
    alvo, _ = svc._achar_team_up(LINHA, _cena())
    assert alvo == (x + 32, y + 75)


def test_o_template_do_item_vence_a_regua(monkeypatch):
    """Se um dia existir recorte do "Team up" em disco, ele decide -- achar o
    item é mais forte que contar a altura da caixa."""
    svc = _servico(monkeypatch, _com_menu(255), template=object(),
                   achado=(11, 22))
    alvo, origem = svc._achar_team_up(LINHA, _cena())
    assert alvo == (11, 22)
    assert "template" in origem


def test_o_quadro_de_ANTES_e_capturado_antes_do_clique_direito():
    """AUTO-SABOTAGEM: capturar depois do clique compararia o menu com ele
    mesmo, a régua daria zero e todo menu pareceria curto -- o APP voltaria a
    clicar em "View Equipment" sem nenhum sintoma novo."""
    fonte = inspect.getsource(team.TeamService._enviar_convite)
    assert fonte.index("antes = capture_window") < fonte.index("ctx.right_click"), (
        "o quadro de antes passou a ser capturado depois do clique direito")


@pytest.mark.parametrize("altura,perto", [(150, False), (255, True)])
def test_os_dois_menus_medidos_caem_de_lados_opostos_do_limiar(
        monkeypatch, altura, perto):
    """As duas alturas medidas ficam a ~50 px do limiar, cada uma de um lado."""
    svc = _servico(monkeypatch, _com_menu(altura))
    _x, y = LINHA
    alvo, _ = svc._achar_team_up(LINHA, _cena())
    assert (alvo[1] - y > 75) is perto
