"""Testes de lógica pura da amostragem de cliques (`amostragem_de_cliques.py`).

TEMPORÁRIO: some junto com o módulo. Cobre só o que não precisa do jogo --
grid, ordem das rodadas, ranking e reconhecimento do ponto pela posição.
"""
import pytest

from blazesbot.bot.bc import amostragem_de_cliques as am
from blazesbot.bot.bc import mapa_bc


def _amostra(dx, dy, abriu, ms, valida=True, andou=False):
    return {"dx": dx, "dy": dy, "alvo": [100 + dx, 200 + dy], "abriu": abriu,
            "valida": valida, "ms": ms, "andou": andou}


# -- grid -------------------------------------------------------------------


def test_grid_inclui_o_alvo_atual():
    """Sem o (0,0) não haveria contra o que comparar o vencedor."""
    assert (0, 0) in am.gerar_grid()


def test_grid_tamanho_e_simetria():
    grid = am.gerar_grid(raio=12, passo=6)
    assert len(grid) == 25
    for dx, dy in grid:
        assert (-dx, -dy) in grid


def test_grid_com_passo_que_nao_divide_o_raio_ainda_tem_o_zero():
    assert (0, 0) in am.gerar_grid(raio=10, passo=4)


def test_grid_recusa_passo_invalido():
    with pytest.raises(ValueError):
        am.gerar_grid(passo=0)


# -- ordem das amostras -----------------------------------------------------


def test_ordem_cobre_cada_coordenada_uma_vez_por_rodada():
    grid = am.gerar_grid()
    seq = am.ordem_das_rodadas(grid, rodadas=3)
    assert len(seq) == len(grid) * 3
    for inicio in (0, len(grid), 2 * len(grid)):
        rodada = seq[inicio:inicio + len(grid)]
        assert sorted(rodada) == sorted(grid)


def test_ordem_e_reproduzivel_mas_intercalada():
    """Semente fixa: duas execuções comparáveis. Rodadas embaralhadas: nenhuma
    coordenada carrega sozinha a sorte de um momento."""
    grid = am.gerar_grid()
    assert am.ordem_das_rodadas(grid) == am.ordem_das_rodadas(grid)
    seq = am.ordem_das_rodadas(grid, rodadas=2)
    assert seq[:len(grid)] != seq[len(grid):]


# -- ranking ----------------------------------------------------------------


def test_taxa_vence_latencia():
    """Abrir sempre em 400 ms é melhor que abrir metade das vezes em 200."""
    amostras = [
        _amostra(0, 0, True, 200), _amostra(0, 0, False, 1500),
        _amostra(6, 0, True, 400), _amostra(6, 0, True, 400),
    ]
    ranking = am.ranquear(amostras)
    assert (ranking[0]["dx"], ranking[0]["dy"]) == (6, 0)
    assert ranking[0]["posicao"] == 1
    assert ranking[1]["taxa"] == pytest.approx(0.5)


def test_desempate_por_mediana():
    amostras = [
        _amostra(0, 0, True, 500), _amostra(0, 0, True, 500),
        _amostra(6, 0, True, 300), _amostra(6, 0, True, 300),
    ]
    ranking = am.ranquear(amostras)
    assert (ranking[0]["dx"], ranking[0]["dy"]) == (6, 0)
    assert ranking[0]["mediana_ms"] == 300


def test_coordenada_sem_nenhuma_abertura_nao_finge_latencia_zero():
    """Mediana `None`, e não 0: 0 ordenaria como "instantâneo" e poria a pior
    coordenada no topo do desempate."""
    ranking = am.ranquear([_amostra(0, 0, False, 1500)])
    assert ranking[0]["mediana_ms"] is None
    assert ranking[0]["taxa"] == 0.0


def test_amostra_invalida_nao_conta_como_erro():
    """Sem captura não houve medição -- não é "a coordenada errou"."""
    amostras = [
        _amostra(0, 0, True, 300),
        _amostra(0, 0, False, 900, valida=False),
    ]
    ranking = am.ranquear(amostras)
    assert ranking[0]["amostras"] == 1
    assert ranking[0]["taxa"] == 1.0


def test_ranking_conta_quantas_vezes_o_personagem_andou():
    amostras = [_amostra(0, 0, False, 1500, andou=True),
                _amostra(0, 0, False, 1500, andou=False)]
    assert am.ranquear(amostras)[0]["andou"] == 1


def test_ranking_vazio_quando_nada_e_valido():
    assert am.ranquear([_amostra(0, 0, False, 900, valida=False)]) == []


# -- veredito em texto (o mesmo para as duas interfaces) --------------------


def _resultado(**extra):
    ranking = am.ranquear([
        _amostra(0, 0, True, 400), _amostra(0, 0, False, 1500),
        _amostra(6, 0, True, 380), _amostra(6, 0, True, 380),
    ])
    base = {
        "rotulo": "Rich Man (vendedor, Stone City)",
        "ancora": [158, -494],
        "ancora_exata": True,
        "melhor": ranking[0],
        "atual": next(r for r in ranking if (r["dx"], r["dy"]) == (0, 0)),
        "ranking": ranking,
        "arquivo": "",
        "parcial": "",
    }
    base.update(extra)
    return base


def test_resumo_diz_o_melhor_e_onde_ficou_o_alvo_de_hoje():
    texto = am.resumir(_resultado())
    assert "dx=+6" in texto
    assert "ALVO DE HOJE" in texto and "2º" in texto


def test_resumo_avisa_quando_a_ancora_nao_e_a_canonica():
    """Sem esse aviso, a coordenada vencedora seria adotada como se valesse do
    ponto de onde o bot clica — e ela vale de outro lugar."""
    assert "ATENÇÃO" in am.resumir(_resultado(ancora_exata=False))
    assert "ATENÇÃO" not in am.resumir(_resultado())


def test_resumo_avisa_varredura_interrompida():
    assert "interrompida" in am.resumir(_resultado(parcial="perdi a âncora"))


def test_resumo_diz_a_resolucao_de_onde_o_numero_saiu():
    """O deslocamento vencedor é portável entre resoluções (a UI não escala),
    mas quem adota precisa saber de onde ele veio."""
    assert "1024x768" in am.resumir(_resultado(janela=[1024, 768]))
    assert "clicando de" in am.resumir(_resultado())   # sem janela, não quebra


def test_resumo_curto_cabe_numa_linha():
    curto = am.resumir_curto(_resultado())
    assert "\n" not in curto
    assert "dx=+6" in curto


def test_resumo_sem_amostra_valida_nao_inventa_vencedor():
    assert am.resumir({"melhor": None}) == "Nenhuma amostra válida."
    assert am.resumir_curto({"melhor": None}) == "Nenhuma amostra válida."


# -- reconhecimento do ponto ------------------------------------------------


@pytest.mark.parametrize("chave, posicao", [
    ("vendedor", mapa_bc.POSICAO_DO_VENDEDOR),
    ("fay", mapa_bc.POSICAO_DA_FAY),
    ("entrada_da_cave", mapa_bc.ENTRADA_EM_GHOST_DIN),
    ("saida_da_cave", mapa_bc.POSICAO_DA_SAIDA),
])
def test_reconhece_cada_ponto_na_propria_coordenada(chave, posicao):
    ponto = am._ponto_da_posicao(posicao)
    assert ponto is not None and ponto.chave == chave


def test_nao_reconhece_longe_de_tudo():
    assert am._ponto_da_posicao((5000, 5000)) is None
    assert am._ponto_da_posicao(None) is None


def test_o_altar_stone_esta_fora_da_lista():
    """Decisão do usuário: é o único ponto cercado de mobs, e clique que erra
    faz o personagem andar."""
    chaves = {p.chave for p in am.PONTOS}
    assert "altar" not in chaves
    assert am._ponto_da_posicao(mapa_bc.ULTIMO_ANTES_DO_ALTAR) is None
