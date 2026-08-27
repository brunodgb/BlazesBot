"""Testes de lógica pura da navegação na cave (`mapa_bc.py`).

Usa rotas sintéticas de `Waypoint` para `mais_proximos`/`houve_rollback` e
coordenadas reais da rota para os reconhecimentos de posição.
"""
import pytest

from blazesbot.bot.bc import mapa_bc
from blazesbot.bot.bc.mapa_bc import Waypoint


def _rota(*pares):
    return tuple(Waypoint(x, y, area) for (x, y, area) in pares)


ROTA_RETA = _rota(
    (0, 0, "A"), (10, 0, "A"), (20, 0, "A"), (30, 0, "A"), (40, 0, "A"),
)


def test_distancia():
    assert mapa_bc.distancia((0, 0), (3, 4)) == 5.0
    assert mapa_bc.distancia((0, 0), (0, 0)) == 0.0
    assert mapa_bc.distancia((10, 0), (0, 0)) == 10.0


def test_fora_da_cave_none_e_dentro():
    assert mapa_bc.posicao_esta_fora_da_cave(None) is False
    # chegada da cave (423,53) e altar (218,45) estão dentro da caixa
    assert mapa_bc.posicao_esta_fora_da_cave((423, 53)) is False
    assert mapa_bc.posicao_esta_fora_da_cave((218, 45)) is False


def test_fora_da_cave_ghost_din():
    # entrada em Ghost Din Woods: x ~1395, bem além de X_MAXIMO_DENTRO_DA_CAVE
    assert mapa_bc.posicao_esta_fora_da_cave((1395, -635)) is True


def test_x_contradiz_a_cave():
    assert mapa_bc.x_contradiz_a_cave(None) is False
    assert mapa_bc.x_contradiz_a_cave((423, 53)) is False
    assert mapa_bc.x_contradiz_a_cave((1395, -635)) is True


def test_na_caixa_da_cave():
    assert mapa_bc.posicao_esta_na_caixa_da_cave((423, 53)) is True
    assert mapa_bc.posicao_esta_na_caixa_da_cave((10000, 10000)) is False
    assert mapa_bc.posicao_esta_na_caixa_da_cave(None) is False


def test_area_da_posicao_no_waypoint():
    # (218,45) é o último waypoint do Secret Altar
    assert mapa_bc.area_da_posicao((218, 45)) == "Secret Altar"


def test_area_da_posicao_fora_da_rota():
    assert mapa_bc.area_da_posicao((10000, 10000)) is None
    assert mapa_bc.area_da_posicao(None) is None


def test_mais_proximos_ordena():
    res = mapa_bc.mais_proximos((11, 0), ROTA_RETA, n=2)
    assert res == [(1, 1.0), (2, 9.0)]


def test_mais_proximos_todos():
    res = mapa_bc.mais_proximos((11, 0), ROTA_RETA, n=5)
    assert [i for i, _ in res] == [1, 2, 0, 3, 4]


def test_houve_rollback():
    assert mapa_bc.houve_rollback(4, (0, 0), ROTA_RETA) == 0
    assert mapa_bc.houve_rollback(4, (10, 0), ROTA_RETA) == 1
    # no índice atual: não é rollback
    assert mapa_bc.houve_rollback(4, (30, 0), ROTA_RETA) is None
    # longe demais: sem posição confiável
    assert mapa_bc.houve_rollback(4, (1000, 1000), ROTA_RETA) is None
    assert mapa_bc.houve_rollback(4, None, ROTA_RETA) is None


def test_houve_rollback_folga():
    # folga=2: voltar 1 índice ainda é ruído de leitura
    assert mapa_bc.houve_rollback(4, (30, 0), ROTA_RETA, folga=2) is None
    assert mapa_bc.houve_rollback(4, (0, 0), ROTA_RETA, folga=2) == 0


def test_tolerancia_waypoint_apertada():
    base = 8
    normal = Waypoint(100, 100, "Bewitcher Cave")
    apertado = Waypoint(200, 200, "Secret Altar")
    assert mapa_bc.tolerancia_do_waypoint(normal, base, 12) == base
    assert mapa_bc.tolerancia_do_waypoint(apertado, base, 12) == 12

def test_vizinhos_na_rota_sao_os_imediatos():
    """Anterior e seguinte são `base-1` e `base+1`, NUNCA "o mais próximo do lado"."""
    rota = tuple(mapa_bc.Waypoint(i * 10, 0, "T") for i in range(10))
    assert mapa_bc.vizinhos_na_rota((45, 0), rota) == (3, 4, 5)
    # Começo da rota: não há anterior. Fim: não há seguinte.
    assert mapa_bc.vizinhos_na_rota((0, 0), rota) == (None, 0, 1)
    assert mapa_bc.vizinhos_na_rota((92, 0), rota) == (8, 9, None)


def test_vizinhos_na_rota_nao_pula_waypoint():
    """Na rota REAL, os candidatos nunca pulam um waypoint.

    Este teste nasceu do caso de (205,31), onde a versão antiga escolhia o
    waypoint a 19 unidades e PULAVA três -- o jogo respondia
    `Failed to auto-path`. A rota não é um conjunto de pontos, é um CAMINHO:
    cada trecho foi desenhado porque é andável a partir do anterior, e pular é
    atravessar parede.

    Ele afirma a PROPRIEDADE e não as coordenadas de propósito: a rota é
    editada de tempos em tempos (foi em 12/08/2026), e um teste que crava
    `(206,41)` quebra na edição sem que nada de errado tenha acontecido --
    escondendo a regressão de verdade no meio do falso alarme.
    """
    import math

    rota = mapa_bc.CAMINHO_ATE_O_ALTAR
    assert len(rota) > 3

    # Varre a rota inteira, e também pontos FORA dela (deslocados), que é a
    # situação real de quem travou.
    pontos = [w.pos for w in rota]
    pontos += [(w.pos[0] + 8, w.pos[1] - 8) for w in rota]

    for ponto in pontos:
        anterior, base, seguinte = mapa_bc.vizinhos_na_rota(ponto, rota)

        # `base` é mesmo o mais próximo do ponto.
        mais_perto = min(
            range(len(rota)),
            key=lambda i: math.dist(ponto, rota[i].pos))
        assert base == mais_perto, ponto

        # E os outros dois são os IMEDIATOS na ordem da lista -- nunca "o mais
        # próximo entre os de índice maior", que é o que pulava.
        assert anterior == (base - 1 if base > 0 else None), ponto
        assert seguinte == (base + 1 if base + 1 < len(rota) else None), ponto


def test_vizinhos_na_rota_ignora_coordenada_e_segue_a_ordem():
    """O caminho volta sobre si: só a ORDEM diz o que já foi percorrido."""
    rota = tuple(mapa_bc.Waypoint(x, 0, "T") for x in (0, 30, 60, 30, 0))
    # Perto do índice 2 (x=60): anterior é o 1 e seguinte é o 3 -- os dois com
    # x=30, e a coordenada sozinha não saberia dizer qual é qual.
    assert mapa_bc.vizinhos_na_rota((58, 0), rota) == (1, 2, 3)


def test_vizinhos_na_rota_vazia():
    assert mapa_bc.vizinhos_na_rota((0, 0), ()) == (None, None, None)


# ---------------------------------------------------------------------------
# Precisão nos pontos de clique posicional
# ---------------------------------------------------------------------------


def test_boss_e_saida_ficam_a_8_virgula_06_unidades():
    """O número que transformou a saída da cave em cara ou coroa.

    O portão antigo do `_do_sair` andava só quando `distancia > 8`, e o waypoint
    do boss cai a 8,06 daqui — 0,06 acima do corte. Parado exatamente no
    waypoint o bot andava; derivando 1-2 unidades na luta, não andava mais e
    clicava de fora. Se este número mudar, o portão precisa ser reexaminado.
    """
    d = mapa_bc.distancia(mapa_bc.POSICAO_DO_BOSS, mapa_bc.POSICAO_DA_SAIDA)
    assert round(d, 2) == 8.06


def test_posicao_real_da_luta_caia_do_lado_errado_do_portao_antigo():
    """Medido no log de dev de 13/08/2026: o personagem parava em (84,-405)."""
    d = mapa_bc.distancia((84, -405), mapa_bc.POSICAO_DA_SAIDA)
    assert d < 8      # não andava
    assert d < 12     # e ainda assim clicava (o default de `na_posicao_de_clicar`)
    assert d > mapa_bc.PRECISAO_NO_PONTO_DA_SAIDA   # hoje é recusado


@pytest.mark.parametrize("constante", [
    "PRECISAO_NO_PATAMAR_DO_ALTAR",
    "PRECISAO_NO_PONTO_DO_VENDEDOR",
    "PRECISAO_NO_PONTO_DA_SAIDA",
])
def test_precisao_de_clique_posicional_exige_a_celula_exata(constante):
    """Os três pontos de clique na cena 3D usam < 1: no espaço de coordenadas
    inteiras, só a posição exata passa. 1 já deixaria a célula vizinha entrar."""
    assert 0 < getattr(mapa_bc, constante) < 1


# ---------------------------------------------------------------------------
# Reconhecer Stone City (venda ao iniciar o bot)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome, pos", [
    ("vendedor", mapa_bc.POSICAO_DO_VENDEDOR),
    ("Transport Fay", mapa_bc.POSICAO_DA_FAY),
])
def test_stone_city_reconhece_os_pontos_medidos_da_cidade(nome, pos):
    assert mapa_bc.posicao_esta_em_stone_city(pos), nome


@pytest.mark.parametrize("nome, pos", [
    ("boss", mapa_bc.POSICAO_DO_BOSS),
    ("saída da cave", mapa_bc.POSICAO_DA_SAIDA),
    ("guardas", mapa_bc.POSICAO_DOS_GUARDAS),
    ("chegada no covil", mapa_bc.CHEGADA_NO_COVIL),
    ("chegada na cave", mapa_bc.CHEGADA_NA_CAVE),
    ("patamar do altar", mapa_bc.ULTIMO_ANTES_DO_ALTAR),
])
def test_stone_city_nao_confunde_com_a_cave(nome, pos):
    assert not mapa_bc.posicao_esta_em_stone_city(pos), nome


def test_stone_city_nao_confunde_com_ghost_din_woods():
    """O Y de Ghost Din (-635) TAMBÉM passa pelo corte da cidade. Quem separa é
    o X — sem ele, iniciar o bot na entrada da cave dispararia a venda."""
    ghost = mapa_bc.ENTRADA_EM_GHOST_DIN
    assert ghost[1] <= mapa_bc.Y_DE_STONE_CITY          # o Y não separa...
    assert not mapa_bc.posicao_esta_em_stone_city(ghost)  # ...e o X separa


def test_stone_city_sem_posicao_nao_afirma_nada():
    assert mapa_bc.posicao_esta_em_stone_city(None) is False


def test_stone_city_reconhece_pelo_NOME_quando_a_coordenada_nao_alcanca():
    """O defeito medido em 14/08/2026, duas partidas com 19 s de diferença:

        (205,-498) -> reconhecida, vendeu antes de sair
        (237,-484) -> NÃO reconhecida, foi direto para a Fay com a bolsa cheia

    As duas são Stone City, e o jogo dizia isso nas duas. A caixa de coordenada
    é um limite inferior — foi derivada de dois pontos, e a cidade é grande.
    """
    fora_da_caixa = (237, -484)
    assert not mapa_bc.posicao_esta_em_stone_city(fora_da_caixa)
    assert mapa_bc.esta_em_stone_city(fora_da_caixa, "Stone City")


def test_stone_city_ainda_vale_so_pela_coordenada():
    """Sem leitura de nome, a caixa continua respondendo."""
    assert mapa_bc.esta_em_stone_city(mapa_bc.POSICAO_DO_VENDEDOR, None)
    assert mapa_bc.esta_em_stone_city(mapa_bc.POSICAO_DA_FAY, "")


@pytest.mark.parametrize("pos, local", [
    (mapa_bc.ENTRADA_EM_GHOST_DIN, "Ghost Din Woods"),
    (mapa_bc.POSICAO_DO_BOSS, "Secret Cemetery"),
    (mapa_bc.CHEGADA_NA_CAVE, "Bewitcher Cave"),
    (None, None),
])
def test_fora_da_cidade_continua_fora(pos, local):
    assert not mapa_bc.esta_em_stone_city(pos, local)


def test_o_nome_sozinho_nao_confunde_outra_cidade():
    assert not mapa_bc.nome_e_stone_city("Ghost Din Woods")
    assert not mapa_bc.nome_e_stone_city(None)
    assert mapa_bc.nome_e_stone_city("stone city")     # sem depender de caixa
