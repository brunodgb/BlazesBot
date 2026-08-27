"""Testes de lógica pura do módulo de coordenadas ancoradas (`coords.py`).

Só funções determinísticas, sem dependência de jogo/win32. `win32gui` é
importado apenas dentro de `coords_for_window`, que não testamos aqui.
"""
import pytest

from blazesbot.core import coords


def test_parse_resolution_padrao():
    assert coords.parse_resolution("1280x720") == (1280, 720)


def test_parse_resolution_asterisco():
    assert coords.parse_resolution("1280*720") == (1280, 720)


def test_parse_resolution_espacos():
    assert coords.parse_resolution("1280 x 720") == (1280, 720)


def test_parse_resolution_invalida_levanta():
    with pytest.raises(ValueError):
        coords.parse_resolution("banana")


def test_coords_for_size():
    c = coords.coords_for_size(1920, 1080)
    assert (c.width, c.height) == (1920, 1080)
    assert c.resolution == "1920x1080"


def test_coords_for_size_zerado_cai_na_base():
    # janela sendo criada/destruída devolve 0x0 -> cai para 1024x768
    c = coords.coords_for_size(0, 0)
    assert (c.width, c.height) == (coords.BASE_W, coords.BASE_H)
    c2 = coords.coords_for_size(-5, 0)
    assert (c2.width, c2.height) == (coords.BASE_W, coords.BASE_H)


def test_spot_anchor_center():
    spot = coords.Spot(coords.Anchor.CENTER, dx=10, dy=-5)
    assert spot.at(200, 100) == (110, 45)


def test_from_base_roundtrip_na_base():
    # medido em 1024x768: `_from_base` devolve o mesmo ponto ao aplicar na base
    spot = coords._from_base(44, 48, coords.Anchor.TOP_LEFT)
    assert spot.at(coords.BASE_W, coords.BASE_H) == (44, 48)


def test_point_minimap_na_base():
    c = coords.Coords()
    assert c.point("minimap_center") == (919, 115)


def test_npc_padrao_na_base_e_identico_a_formula_antiga():
    """Trava a NÃO-REGRESSÃO: o `_ponto_padrao_do_npc` calculava
    `(largura//2 - 30, int(altura*0.46))`. Na resolução validada os dois têm que
    dar o mesmo número, senão a troca mexeu no que já funciona."""
    c = coords.Coords()
    antigo = (coords.BASE_W // 2 - 30, int(coords.BASE_H * 0.46))
    assert c.npc_padrao == antigo == (482, 353)


@pytest.mark.parametrize("largura, altura", [
    (800, 600), (1280, 1024), (1366, 768), (1920, 1080),
])
def test_npc_padrao_e_ancorado_e_nao_proporcional(largura, altura):
    """Fora da base, o ponto segue o modelo do arquivo: deslocamento FIXO do
    centro. A fração da altura (o cálculo antigo) contradizia a descoberta de
    que a UI não escala, e divergia mais quanto maior a tela."""
    c = coords.coords_for_size(largura, altura)
    assert c.npc_padrao == (largura // 2 - 30, altura // 2 - 31)


def test_npc_padrao_a_1920x1080_divergia_13px_do_calculo_antigo():
    """A medida do estrago que o cálculo proporcional fazia na maior resolução
    suportada — registrada para o número não voltar sem alguém perceber."""
    c = coords.coords_for_size(1920, 1080)
    proporcional = int(1080 * 0.46)
    assert c.npc_padrao[1] - proporcional == 13


def test_point_desconhecido_levanta():
    c = coords.Coords()
    with pytest.raises(KeyError):
        c.point("nao_existe")


def test_getattr_de_ponto():
    c = coords.Coords()
    assert c.enter_game == c.point("enter_game")


def test_char_slots():
    c = coords.Coords()
    assert set(c.char_slots) == {"Left", "Center", "Right"}


def test_is_validated():
    assert coords.Coords().is_validated is True
    assert coords.coords_for_size(1920, 1080).is_validated is False


def test_get_coords_resolucao_invalida_cai_base():
    c = coords.get_coords("lixo")
    assert c.resolution == coords.VALIDATED_RESOLUTION
    assert (c.width, c.height) == (coords.BASE_W, coords.BASE_H)


def test_server_index_normaliza_alias():
    c = coords.Coords()
    assert c.server_index("Sky Ice") == 2   # alias de "Sky Ice (GSM&BI)"
    assert c.server_index("Tiger Fish") == 1


def test_server_index_desconhecido():
    c = coords.Coords()
    assert c.server_index("Servidor Fantasma") == -1


def test_server_point_primeira_linha_na_base():
    c = coords.Coords()
    assert c.server_point("White Horse [NEW]") == (345, 247)


def test_sell_slot_xy_primeria():
    c = coords.Coords()
    x, y = c.sell_slot_xy(1)
    assert x == c.sell_grid.origin_x
    assert y == c.sell_grid.origin_y
