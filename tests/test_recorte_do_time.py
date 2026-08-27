"""O recorte do painel de time se prova pela REPETIÇÃO, não por régua.

=============================================================================
O QUE ESTÁ SOB TESTE
=============================================================================

`bot/bc/team.py` procura `state_team_member.png` e esse arquivo nunca existiu
em disco -- então `_time_pela_imagem()` devolve `None` sempre, e somado a
`team_size()` também não responder o bot não sabe se está em time por caminho
nenhum.

A tentação ao consertar era pegar as coordenadas de um print, ou copiar as do
GhostBot ((30,200)/(30,285)/(30,365)/(30,445), do cliente e da resolução DELE).
As duas são o número escolhido no olho que o `CLAUDE.md` proíbe.

O que `recorte_do_time` faz em vez disso: um bom recorte é o que, procurado no
próprio quadro, **se acha N vezes em intervalos regulares**. Isso se testa sem
o jogo aberto -- basta desenhar um quadro que TENHA essa estrutura e outro que
não tenha.

Os quadros aqui são sintéticos de propósito. Um teste que dependesse de uma
captura real do cliente não rodaria em máquina nenhuma sem o jogo instalado,
logado e com o time formado -- e um teste que não roda não trava nada.
"""
import numpy as np
import pytest

from blazesbot.bot.recorte_do_time import (
    FOLGA_DO_ESPACAMENTO,
    MINIMO_DE_LINHAS,
    _regularidade,
    avaliar_recorte,
    melhor_recorte,
)

LARGURA, ALTURA = 1024, 768
COLUNA = 200                 # largura da faixa onde o painel de time vive
PRIMEIRA_LINHA = 200
PASSO = 80
ALTURA_DA_LINHA = 60
LARGURA_DA_LINHA = 150


def _quadro_base() -> np.ndarray:
    """Fundo escuro liso na coluna esquerda, ruído no resto (a cena 3D).

    A coluna precisa ser lisa para que a única estrutura repetida ali seja a
    que o teste desenha -- senão o ruído do fundo entraria no casamento e o
    teste passaria a medir o ruído.
    """
    gerador = np.random.default_rng(20260818)
    quadro = gerador.integers(0, 255, (ALTURA, LARGURA, 3), dtype=np.uint8)
    quadro[:, :COLUNA] = 28
    return quadro


def _desenhar_linha(quadro: np.ndarray, y: int) -> None:
    """Uma moldura de companheiro: borda clara, retrato e duas barras.

    O conteúdo é IDÊNTICO em todas as linhas -- é isso que o cliente faz, e é o
    que o algoritmo procura.
    """
    x = 6
    bloco = quadro[y:y + ALTURA_DA_LINHA, x:x + LARGURA_DA_LINHA]
    bloco[:] = 60
    bloco[0, :] = 200                     # borda de cima
    bloco[-1, :] = 200                    # borda de baixo
    bloco[:, 0] = 200                     # borda da esquerda
    bloco[8:44, 6:42] = 130               # retrato
    bloco[16:22, 50:140] = 190            # barra de vida
    bloco[26:32, 50:120] = 90             # barra de mana


def quadro_com_time(linhas: int = 4) -> np.ndarray:
    quadro = _quadro_base()
    for i in range(linhas):
        _desenhar_linha(quadro, PRIMEIRA_LINHA + i * PASSO)
    return quadro


@pytest.fixture(scope="module")
def achado_de_quatro():
    """A varredura é a parte cara (~960 recortes testados).

    Quatro testes fazem perguntas diferentes sobre O MESMO resultado, então
    calcular uma vez por módulo troca ~3 s de suíte por nada -- e mantém cada
    teste com uma asserção só.
    """
    return melhor_recorte(quadro_com_time(4))


# ---------------------------------------------------------------------------
# A regularidade
# ---------------------------------------------------------------------------

def test_regularidade_de_espacamento_uniforme():
    medio, pior = _regularidade([200, 280, 360, 440])
    assert medio == pytest.approx(80.0)
    assert pior == pytest.approx(0.0)


def test_regularidade_denuncia_conjunto_irregular():
    _, pior = _regularidade([200, 280, 500, 505])
    assert pior > FOLGA_DO_ESPACAMENTO


def test_regularidade_com_menos_de_dois_e_infinita():
    """Uma linha só não prova repetição -- e infinito reprova em qualquer
    comparação, que é o desfecho certo."""
    _, pior = _regularidade([200])
    assert pior == float("inf")


# ---------------------------------------------------------------------------
# O recorte
# ---------------------------------------------------------------------------

def test_acha_as_quatro_linhas_do_time(achado_de_quatro):
    achado = achado_de_quatro

    assert achado is not None, "não achou a estrutura repetida que foi desenhada"
    assert achado["linhas"] == 4, f"achou {achado['linhas']} linhas, esperava 4"
    assert achado["espacamento"] == pytest.approx(PASSO, abs=FOLGA_DO_ESPACAMENTO)
    assert achado["pior_desvio"] <= FOLGA_DO_ESPACAMENTO


def test_o_recorte_escolhido_cai_em_cima_de_uma_linha(achado_de_quatro):
    """Não basta achar 4 casamentos: o recorte tem que ser a MOLDURA.

    Um recorte deslocado casaria 4 vezes igual (a estrutura toda se repete),
    mas viraria um template que não é o painel -- e o consumidor
    (`_time_pela_imagem`) passaria a procurar a coisa errada.
    """
    achado = achado_de_quatro
    assert achado is not None

    _, y, _, altura = achado["regiao"]
    # O recorte tem que se sobrepor a alguma linha desenhada, não cair no vão.
    sobreposicoes = [
        min(y + altura, topo + ALTURA_DA_LINHA) - max(y, topo)
        for topo in (PRIMEIRA_LINHA + i * PASSO for i in range(4))
    ]
    assert max(sobreposicoes) >= altura * 0.5, (
        f"o recorte em y={y} h={altura} mal encosta nas linhas desenhadas"
    )


def test_duas_linhas_ja_bastam():
    achado = melhor_recorte(quadro_com_time(MINIMO_DE_LINHAS))
    assert achado is not None
    assert achado["linhas"] >= MINIMO_DE_LINHAS


def test_uma_linha_so_nao_prova_nada():
    """Com um companheiro só não há repetição, e o recorte se acharia a si
    mesmo -- o que qualquer recorte faz. A ferramenta tem que RECUSAR."""
    assert melhor_recorte(quadro_com_time(1)) is None


def test_sem_time_na_tela_nao_inventa_recorte():
    assert melhor_recorte(_quadro_base()) is None


def test_coluna_lisa_e_recusada():
    """Recorte sem conteúdo casaria em todo lugar e produziria um template
    inútil -- pior que nenhum, porque pareceria funcionar."""
    quadro = _quadro_base()
    assert avaliar_recorte(quadro, (0, 200, 120, 60)) is None


def test_estrutura_irregular_e_recusada():
    """Espaçamento irregular é coincidência, não lista. Se isso passasse, um
    pedaço qualquer da interface viraria o template do time."""
    quadro = _quadro_base()
    for y in (200, 260, 460, 470):
        _desenhar_linha(quadro, y)

    achado = melhor_recorte(quadro)
    if achado is not None:
        assert achado["pior_desvio"] <= FOLGA_DO_ESPACAMENTO, (
            "aceitou um conjunto irregular como se fosse lista de time"
        )


def test_centros_saem_ordenados_de_cima_para_baixo(achado_de_quatro):
    """A ordem importa: slot 1 é o de cima. Se vier embaralhado, a Fairy cura
    o companheiro errado -- e curar o errado não tem sintoma óbvio."""
    achado = achado_de_quatro
    assert achado is not None

    ys = [c[1] for c in achado["centros"]]
    assert ys == sorted(ys), f"centros fora de ordem: {ys}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
