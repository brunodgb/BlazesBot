"""VOLTAR AO PONTO INICIAL: a mecânica do `core/` e o uso pela Fada.

Pedido do usuário em 07/09/2026: *"a fada deve voltar ao ponto inicial para
evitar zonas de risco. Implemente uma rotina de verificação de distância que
opere com baixo custo computacional. Ative a rotina de retorno ao ponto de
origem para ela tambem"*.

O que estes testes travam:

1. A RÉGUA É TRI-ESTADO. `None` (não sei) não pode virar "não cheguei", senão o
   bot anda às cegas na primeira leitura que falha.
2. ANDAR EXCLUI SENTAR. A tecla de sentar interrompe a ordem de andar, e a Fada
   senta no giro seguinte por desenho -- sem a trava, ela pararia a meio
   caminho, que é o pior dos dois lugares.
3. A MARCA DURA A CADÊNCIA INTEIRA. Entre duas conferências cabem ~30 giros do
   laço; se a resposta não persistisse, o item 2 valeria só para um deles.
4. UM NÚMERO, UMA CASA. O APP e a Fada usam a MESMA tolerância.
"""

from __future__ import annotations

import logging

import pytest

from blazesbot.bot import fada as mod
from blazesbot.bot import fada_ociosa, mural
from blazesbot.bot.app import executor as executor_mod
from blazesbot.core import volta_ao_ponto

# ---------------------------------------------------------------------------
# A MECÂNICA NO `core/`
# ---------------------------------------------------------------------------

def test_cheguei_e_tri_estado():
    """`None` em qualquer entrada = `None` na saída. Não é "não cheguei"."""
    assert volta_ao_ponto.cheguei(None, (10, 10)) is None
    assert volta_ao_ponto.cheguei((10, 10), None) is None


def test_cheguei_usa_a_tolerancia():
    """A tolerância é 1 porque a coordenada oscila em ±1 sem ninguém andar."""
    assert volta_ao_ponto.cheguei((10, 10), (10, 10)) is True
    assert volta_ao_ponto.cheguei((11, 10), (10, 10)) is True
    assert volta_ao_ponto.cheguei((10, 30), (10, 10)) is False


def test_a_tolerancia_do_app_e_a_mesma_do_core():
    """Um número lido por dois lados mora num lugar só (regra do projeto)."""
    assert executor_mod.TOLERANCIA_POSICAO == volta_ao_ponto.TOLERANCIA


def test_mandar_andar_sem_centro_do_minimapa_nao_clica():
    """Sem o centro medido, clicar seria adivinhar pixel. Melhor ficar parado."""
    cliques: list[tuple[int, int]] = []
    andou = volta_ao_ponto.mandar_andar(
        (10, 10), (20, 20), None, lambda x, y: cliques.append((x, y)))
    assert andou is False
    assert cliques == []


def test_mandar_andar_clica_uma_vez():
    """UM clique: no minimapa cada clique é calculado da posição ATUAL."""
    cliques: list[tuple[int, int]] = []
    andou = volta_ao_ponto.mandar_andar(
        (10, 10), (20, 20), (500, 100), lambda x, y: cliques.append((x, y)))
    assert andou is True
    assert len(cliques) == 1


# ---------------------------------------------------------------------------
# A FADA
# ---------------------------------------------------------------------------

class _Voltar:
    """Dublê da peça injetada: conta quantas vezes foi perguntada."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.perguntas = 0

    def __call__(self) -> bool:
        self.perguntas += 1
        if not self.respostas:
            return False
        return self.respostas.pop(0)


class _FadaParada:
    """A Fada com o mínimo para o ramo OCIOSO rodar: ninguém pedindo cura."""

    def __init__(self, voltar=None, sentado=True):
        self.sentadas = 0
        self.sentado = sentado
        self.fada = mod.FadaDoTime(
            log=logging.getLogger("teste.ponto"),
            meu_login="fada",
            meu_nick=lambda: "Fada",
            vida_pct=lambda: 100.0,
            mana_pct=lambda: 100.0,
            em_batalha=lambda: False,
            esta_sentado=lambda: self.sentado,
            companheiros=lambda: ["Aliado"],
            vida_do_time=lambda: [{"nome": "Aliado", "hp": 100.0}],
            id_do_alvo=lambda: 0,
            clicar_no_retrato=lambda slot: True,
            apertar_cura=lambda: None,
            apertar_reviver=None,
            apertar_sentar=self._sentar,
            auto_selecionar=lambda: None,
            mural=mural,
            membros_do_time=lambda: ["fada", "aliado"],
            nick_de=lambda login: {"aliado": "Aliado"}.get(login, ""),
            continuar=lambda: True,
            dormir=lambda s: True,
            pedir_pct=lambda: 30.0,
            parar_pct=lambda: 90.0,
            cuidar_do_pet=None,
            limpar_a_bolsa=None,
            voltar_ao_ponto=voltar,
        )

    def _sentar(self) -> None:
        self.sentadas += 1
        self.sentado = not self.sentado


@pytest.fixture(autouse=True)
def _mural_limpo():
    mural.zerar_o_time_para_teste()
    yield
    mural.zerar_o_time_para_teste()


def test_sem_injecao_a_fada_segue_como_sempre():
    """Ninguém injetou nada = ela fica onde está, e continua sentando."""
    caso = _FadaParada(voltar=None, sentado=False)
    assert fada_ociosa.voltar_ao_ponto_se_preciso(caso.fada) is False
    caso.fada._uma_volta()
    assert caso.sentadas == 1


def test_andar_impede_sentar_na_mesma_volta():
    """A tecla de sentar interrompe a ordem de andar. Uma coisa por volta."""
    voltar = _Voltar([True])
    caso = _FadaParada(voltar=voltar, sentado=False)
    caso.fada._uma_volta()
    assert voltar.perguntas == 1
    assert caso.sentadas == 0, "sentou no meio do caminho"


def test_a_marca_de_andando_dura_a_cadencia_inteira():
    """Os ~30 giros que cabem em 3 s NÃO podem sentar nem re-perguntar.

    É o furo que este teste guarda: a conferência é barata mas tem cadência, e
    sem lembrar a resposta anterior a Fada mandaria andar e se sentaria 0,1 s
    depois -- todo giro.
    """
    voltar = _Voltar([True])
    caso = _FadaParada(voltar=voltar, sentado=False)
    for _ in range(30):
        caso.fada._uma_volta()
    assert voltar.perguntas == 1, "perguntou fora da cadência"
    assert caso.sentadas == 0, "sentou no meio do caminho"


def test_quando_ja_chegou_ela_volta_a_descansar():
    """Chegou = a rotina sai da frente e o descanso volta a acontecer."""
    voltar = _Voltar([False])
    caso = _FadaParada(voltar=voltar, sentado=False)
    caso.fada._uma_volta()
    assert voltar.perguntas == 1
    assert caso.sentadas == 1


def test_a_conferencia_respeita_a_cadencia():
    """Barato é não perguntar dez vezes por segundo o que muda a cada minuto."""
    voltar = _Voltar([False, False])
    caso = _FadaParada(voltar=voltar, sentado=True)
    for _ in range(50):
        caso.fada._uma_volta()
    assert voltar.perguntas == 1


def test_falha_na_conferencia_nao_para_a_fada():
    """"Não sei" não bloqueia: leitura ruim não pode virar Fada paralisada."""
    def explode() -> bool:
        raise RuntimeError("memória fechada")

    caso = _FadaParada(voltar=explode, sentado=False)
    assert fada_ociosa.voltar_ao_ponto_se_preciso(caso.fada) is False
    caso.fada._uma_volta()
    assert caso.sentadas == 1


def test_com_alguem_na_fila_ela_nao_anda():
    """Andar com vítima na fila é deixar a vítima morrer."""
    voltar = _Voltar([True])
    caso = _FadaParada(voltar=voltar, sentado=False)
    mural.pedir_cura("aliado", 20.0)
    caso.fada._uma_volta()
    assert voltar.perguntas == 0


def test_a_montagem_injeta_a_peca():
    """`fada_montagem` é quem sabe ler posição e clicar -- e tem de ligar isso.

    Sem esta trava, a rotina existiria completa e desligada: a Fada de produção
    receberia `None` e ficaria parada na zona de risco, com todos os testes
    acima passando.
    """
    import inspect

    from blazesbot.bot import fada_montagem
    fonte = inspect.getsource(fada_montagem.rodar_a_fada)
    assert "voltar_ao_ponto=voltar_ao_ponto" in fonte
    assert "volta_ao_ponto.mandar_andar" in fonte
