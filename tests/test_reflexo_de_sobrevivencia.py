"""O REFLEXO CONTRA A OCIOSIDADE SOB ATAQUE -- APP, 07/09/2026.

O buraco: morto o mob, se a flag de combate continua alta (outro mob batendo),
o TAB não acontecia -- ele só existia no ramo FORA de batalha. O ramo EM
batalha rodava a macro contra um alvo que já não existe, a volta abortava na
primeira linha, e o personagem ficava apanhando parado.

Três eixos, e cada um tem a sua seção aqui:

    EIXO 1  a régua da vida (`core/vigia_da_vida.py`) -- só QUEDA acusa;
    EIXO 2  o reflexo: TAB urgente, e o que impede o TAB infinito;
    EIXO 3  o desvio no laço: em batalha e sob ataque NÃO faz manutenção.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from blazesbot.bot.app import executor as mod
from blazesbot.core import vigia_da_vida

# ---------------------------------------------------------------------------
# EIXO 1 -- A RÉGUA DA VIDA
# ---------------------------------------------------------------------------

def test_a_primeira_leitura_so_estabelece_a_regua():
    """Sem leitura anterior não há queda: não se acusa nada."""
    v = vigia_da_vida.VigiaDaVida()
    assert v.anotar(80.0, lutando=True) is False
    assert v.ultima == 80.0


def test_QUEDA_em_batalha_acusa():
    v = vigia_da_vida.VigiaDaVida()
    v.anotar(80.0, lutando=True)
    assert v.anotar(74.0, lutando=True) is True


def test_REGENERACAO_nao_acusa():
    """A vida subindo é cura ou regeneração -- nunca agressão."""
    v = vigia_da_vida.VigiaDaVida()
    v.anotar(60.0, lutando=True)
    assert v.anotar(61.0, lutando=True) is False
    assert v.anotar(90.0, lutando=True) is False


def test_a_POCAO_move_a_regua_para_cima():
    """Sem isso, a régua velha faria o golpe seguinte parecer maior do que foi.

    E, pior: a comparação passaria a ser contra um valor que já não descreve o
    personagem.
    """
    v = vigia_da_vida.VigiaDaVida()
    v.anotar(30.0, lutando=True)
    v.anotar(90.0, lutando=True)          # bebeu
    assert v.ultima == 90.0
    assert v.anotar(89.0, lutando=True) is True, "não viu o golpe depois da cura"


def test_SEM_leitura_nao_muda_nada():
    """"Não sei" não acusa e não mexe na régua -- reagir no escuro é pior."""
    v = vigia_da_vida.VigiaDaVida()
    v.anotar(50.0, lutando=True)
    assert v.anotar(None, lutando=True) is False
    assert v.ultima == 50.0
    assert v.anotar(49.0, lutando=True) is True


def test_FORA_de_batalha_a_marca_CAI():
    """Fora de batalha não há agressão em curso; manter a marca a faria
    atravessar até a luta seguinte."""
    v = vigia_da_vida.VigiaDaVida()
    v.anotar(80.0, lutando=True)
    v.anotar(70.0, lutando=True)
    assert v.sob_ataque is True
    assert v.anotar(70.0, lutando=False) is False
    assert v.sob_ataque is False


def test_consumir_baixa_a_marca():
    """O agressor virou alvo -- ver o item 2 do reflexo."""
    v = vigia_da_vida.VigiaDaVida()
    v.anotar(80.0, lutando=True)
    v.anotar(70.0, lutando=True)
    v.consumir()
    assert v.sob_ataque is False


# ---------------------------------------------------------------------------
# EIXO 2 e 3 -- O REFLEXO NO LAÇO
# ---------------------------------------------------------------------------

class _Executor:
    """O executor cru, com só o que o ramo do reflexo toca."""

    def __init__(self, vida=(100.0, 90.0), em_batalha=True, alvo_vivo=False,
                 tab_traz_alvo=True):
        e = mod.ExecutorDeMacro.__new__(mod.ExecutorDeMacro)
        self.e = e
        self.vidas = list(vida)
        self.tab_traz_alvo = tab_traz_alvo
        self.alvo_vivo = alvo_vivo
        self.linhas: list[tuple[str, str]] = []
        self.manutencao: list[str] = []
        self.tabs: list[bool] = []
        self.teclas: list[str] = []

        e.log = SimpleNamespace(
            info=lambda f, *a: self.linhas.append(("INFO", f % a if a else f)),
            warning=lambda f, *a: self.linhas.append(("WARN", f % a if a else f)),
            debug=lambda *a, **k: None)
        e._vigia = vigia_da_vida.VigiaDaVida()
        e._ultimo_tab_do_reflexo = 0.0
        e.urgencias = 0
        e.voltas = 0
        e.voltas_abortadas = 0
        e._ultimo_corte = "início"
        e._estava_em_batalha = True
        e._lutava_na_volta_anterior = True
        e.morte = None
        e.cura = None
        e.sincronia = None
        e._cadencia_da_bolsa = SimpleNamespace(deve_limpar=lambda **k: False)

        e._vida_pct = self._vida
        e._em_batalha = lambda: em_batalha
        e._alvo_atual = self._alvo
        e._id_do_alvo = lambda: (1 if self.alvo_vivo else 0)
        e._continuar = lambda: True
        e._pausado = None
        e._esperar = lambda ms: True
        e._esperar_cego = lambda ms: True
        e.teclas_enviadas = 0
        e._mobs_por_perto = None
        e._ler_em_batalha = lambda: em_batalha
        e._a_batalha_acabou = lambda: False
        e._o_alvo_caiu_pelo_hp = lambda: False
        e._garantir_alvo = self._garantir_alvo
        e._tab_simples = lambda: True
        # A MANUTENÇÃO É ESPIONADA: o teste do desvio é sobre ela NÃO acontecer.
        e.garantir_pet = lambda: self.manutencao.append("pet")
        e.feed_pet = lambda: self.manutencao.append("comida")
        e._travar_posicao_se_preciso = lambda: self.manutencao.append("posição")
        e._limpar_a_bolsa_se_for_a_hora = lambda: self.manutencao.append("bolsa")
        e._adquirir_alvo = lambda lutando: self.manutencao.append("tab calmo")
        e.input = SimpleNamespace(key=self.teclas.append)

    def _vida(self):
        return self.vidas.pop(0) if self.vidas else (
            self.vidas[-1] if self.vidas else None)

    def _alvo(self):
        return {"id": 1, "hp": 50, "max_hp": 100} if self.alvo_vivo else None

    def _garantir_alvo(self, forcar=False, urgente=False):
        self.tabs.append(urgente)
        if self.tab_traz_alvo:
            self.alvo_vivo = True
        return self.tab_traz_alvo


@pytest.fixture
def passos():
    return [SimpleNamespace(key="1", delay_ms=0)]


def test_EM_BATALHA_sem_alvo_e_levando_dano_da_TAB_URGENTE(passos):
    """O caso que matava: mob morto, outro batendo, e o bot parado."""
    caso = _Executor(vida=(100.0, 92.0), em_batalha=True, alvo_vivo=False)
    caso.e._uma_volta_simples(passos)
    caso.e._uma_volta_simples(passos)

    assert caso.tabs == [True], f"não deu o TAB urgente: {caso.tabs}"
    assert any("REFLEXO" in t for _n, t in caso.linhas), caso.linhas


def test_o_reflexo_PULA_a_manutencao(passos):
    """*"A prioridade é a sobrevivência"* — nada de pet, comida, posição, bolsa."""
    caso = _Executor(vida=(100.0, 92.0), em_batalha=True, alvo_vivo=False)
    caso.e._uma_volta_simples(passos)
    caso.e._uma_volta_simples(passos)
    assert caso.manutencao == [], caso.manutencao


def test_COM_alvo_vivo_o_reflexo_NAO_dispara(passos):
    """Com alvo vivo o bot já faz a coisa certa: bate nele até cair."""
    caso = _Executor(vida=(100.0, 92.0), em_batalha=True, alvo_vivo=True)
    caso.e._uma_volta_simples(passos)
    caso.e._uma_volta_simples(passos)
    assert caso.tabs == [], "trocou de alvo no meio da luta"


def test_SEM_perder_vida_o_reflexo_NAO_dispara(passos):
    """Em batalha sem dano entrando não há agressor para caçar."""
    caso = _Executor(vida=(100.0, 100.0), em_batalha=True, alvo_vivo=False)
    caso.e._uma_volta_simples(passos)
    caso.e._uma_volta_simples(passos)
    assert caso.tabs == []


def test_o_alvo_adquirido_CONSOME_a_marca(passos):
    """Item 2 do anti-spin: sem consumir, o alvo novo reentraria no reflexo."""
    caso = _Executor(vida=(100.0, 92.0), em_batalha=True, alvo_vivo=False)
    caso.e._uma_volta_simples(passos)
    caso.e._uma_volta_simples(passos)
    assert caso.e._vigia.sob_ataque is False


def test_a_CADENCIA_impede_um_TAB_por_golpe(passos):
    """Um golpe por segundo seria um TAB por segundo sem o freio.

    Aqui o TAB não traz alvo (mob fora do alcance), então a marca FICA de pé --
    que é o certo -- e o que segura o laço é a cadência.
    """
    caso = _Executor(vida=(100.0, 92.0, 84.0, 76.0, 68.0),
                     em_batalha=True, alvo_vivo=False, tab_traz_alvo=False)
    for _ in range(5):
        caso.e._uma_volta_simples(passos)
    assert len(caso.tabs) == 1, f"TAB por golpe: {caso.tabs}"
    assert caso.e._vigia.sob_ataque is True, "desistiu do agressor"


def test_o_TAB_que_nao_traz_mob_ABORTA_a_volta(passos):
    """Sem alvo, rodar a macro é bater no vazio -- e a volta tem de contar."""
    caso = _Executor(vida=(100.0, 92.0), em_batalha=True, alvo_vivo=False,
                     tab_traz_alvo=False)
    caso.e._uma_volta_simples(passos)
    antes = caso.e.voltas_abortadas
    caso.e._uma_volta_simples(passos)
    assert caso.e.voltas_abortadas > antes
    assert caso.teclas == [], "rodou a macro sem alvo"


def test_FORA_de_batalha_a_manutencao_VOLTA_a_acontecer(passos):
    """O desvio é só para o caso de emergência: o ciclo calmo continua inteiro."""
    caso = _Executor(vida=(100.0, 92.0), em_batalha=False, alvo_vivo=False)
    caso.e._uma_volta_simples(passos)
    caso.e._uma_volta_simples(passos)
    assert caso.manutencao[:4] == ["pet", "comida", "posição", "bolsa"], \
        caso.manutencao
    assert caso.tabs == [], "o TAB calmo passa por `_adquirir_alvo`"
