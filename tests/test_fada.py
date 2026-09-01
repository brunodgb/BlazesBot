"""A Fada: a conta que, em time, cura os aliados em vez de atacar.

=========================================================================
O QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

1. CURAR O ALIADO ERRADO. É a falha mais cara e a mais silenciosa. Medido em
   28/08/2026: clicar num retrato que não dá para selecionar NÃO muda o alvo --
   ele continua sendo o de antes. Lançar a cura ali cura o aliado ANTERIOR: o
   pedido sai da fila e a vítima continua ferida, sem erro nenhum na tela.

2. O SLOT ADIVINHADO PELA CONFIGURAÇÃO. O rascunho calculava a posição do
   retrato a partir do `time_logins` do config. O jogo ordena o painel por
   ORDEM DE ENTRADA no time; o config está na ordem em que o usuário marcou as
   contas. São ordens diferentes, e usar a errada faz a Fada clicar noutro.

3. A FILA TRAVADA NUM CASO PERDIDO. Vítima morta, fora de alcance ou cura sem
   efeito: sem teto, a Fada insiste para sempre e todo mundo atrás dela morre
   esperando.

4. SENTAR NA HORA DE CURAR. A tecla de sentar é INTERRUPTOR e o bot não sabe em
   que estado está; só o par levantar/sentar pode mexer nisso.
"""
from __future__ import annotations

import logging

import pytest

from blazesbot.bot import mural
from blazesbot.bot.app import fada as mod


@pytest.fixture(autouse=True)
def _mural_limpo():
    mural.zerar_o_time_para_teste()
    yield
    mural.zerar_o_time_para_teste()


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    """Os tetos reais são de segundos e esta suíte roda a cada mudança."""
    monkeypatch.setattr(mod, "TETO_DA_CURA_SEGUNDOS", 0.3)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_CURAS", 0.01)
    monkeypatch.setattr(mod, "TETO_PARA_O_ALVO_VIRAR", 0.1)
    monkeypatch.setattr(mod, "PASSO_DA_CONFERENCIA_DO_ALVO", 0.01)


class _Jogo:
    """O cliente falso: guarda o que a Fada mandou e o que ela veria."""

    def __init__(self, *, vida=100.0, mana=100.0, batalha=False,
                 companheiros=("Aliado", "Outro"), vidas=None, alvo=0):
        self.vida = vida
        self.mana = mana
        self.batalha = batalha
        self.companheiros = list(companheiros)
        self.vidas = vidas if vidas is not None else [
            {"nome": "Aliado", "hp": 300}, {"nome": "Outro", "hp": 1000}]
        self.alvo = alvo
        self.cliques: list[int] = []
        self.curas = 0
        self.sentadas = 0
        self.auto_selecoes = 0
        # Ao clicar no slot N, o alvo passa a ser este id (None = clique nao pega)
        self.id_por_slot: dict[int, int | None] = {}
        # A cada tecla de cura, a vida do aliado sobe isto
        self.cura_sobe = 0

    def clicar(self, slot: int) -> bool:
        self.cliques.append(slot)
        novo = self.id_por_slot.get(slot, "nao-configurado")
        if novo != "nao-configurado":
            if novo is not None:
                self.alvo = novo
        return True

    def curar(self) -> None:
        """Sobe a vida de QUEM ESTÁ SELECIONADO, não de um nome fixo.

        O dublê antigo só subia a vida de "Aliado", e por isso um teste com
        outra vítima falhava por culpa do dublê -- exatamente o tipo de falso
        negativo que faz duvidar do código certo.
        """
        self.curas += 1
        if not self.cura_sobe or not self.cliques:
            return
        slot = self.cliques[-1]
        if slot >= len(self.companheiros):
            return
        alvo = self.companheiros[slot]
        for m in self.vidas:
            if m["nome"] == alvo:
                m["hp"] = (m["hp"] or 0) + self.cura_sobe

    def sentar(self) -> None:
        self.sentadas += 1

    def auto_selecionar(self) -> None:
        self.auto_selecoes += 1


def _fada(jogo, *, membros=("lider", "aliado"), nicks=None, parar=90.0,
          pedir=30.0, continuar=None):
    nicks = nicks or {"aliado": "Aliado", "outro": "Outro", "fada": "Fada"}
    return mod.FadaDoTime(
        log=logging.getLogger("teste.fada"),
        meu_login="fada",
        meu_nick=lambda: "Fada",
        vida_pct=lambda: jogo.vida,
        mana_pct=lambda: jogo.mana,
        em_batalha=lambda: jogo.batalha,
        companheiros=lambda: jogo.companheiros,
        vida_do_time=lambda: jogo.vidas,
        id_do_alvo=lambda: jogo.alvo,
        clicar_no_retrato=jogo.clicar,
        apertar_cura=jogo.curar,
        apertar_sentar=jogo.sentar,
        auto_selecionar=jogo.auto_selecionar,
        mural=mural,
        membros_do_time=lambda: list(membros),
        nick_de=lambda login: nicks.get(login, ""),
        continuar=continuar or (lambda: True),
        dormir=lambda s: True,
        pedir_pct=lambda: pedir,
        parar_pct=lambda: parar,
    )


# ---------------------------------------------------------------------------
# ID QUE NÃO BATE NÃO CURA
# ---------------------------------------------------------------------------

def test_nao_cura_quando_o_clique_nao_seleciona():
    """Medido: clicar num retrato que não pega deixa o alvo como estava.

    Curar aí curaria o aliado ANTERIOR -- e o pedido sairia da fila com a
    vítima ainda ferida.
    """
    jogo = _Jogo(alvo=555)
    jogo.id_por_slot = {0: None}          # o clique não muda o alvo
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert jogo.cliques == [0]            # clicou
    assert jogo.curas == 0                # e NÃO curou
    assert f.cliques_errados == 1
    assert mural.fila_de_cura(["aliado"]) == ["aliado"]   # continua na fila


def test_sem_id_publicado_CONFIA_NO_SLOT_e_cura():
    """Quem identifica é o SLOT, que vem da memória -- o id é rede, não portão.

    A versão anterior exigia o id publicado e, sem ele, recusava a cura. O laço
    voltava em 100 ms e clicava de novo: medido em campo, 357 cliques no mesmo
    retrato, zero curas, e o personagem saiu andando. Um portão que falha
    fechado é pior que portão nenhum.
    """
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 300}])
    jogo.id_por_slot = {0: 777}
    jogo.cura_sobe = 400
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 25.0)      # de propósito: SEM publicar_id
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert f.curas == 1
    assert f.cliques_errados == 0


def test_cura_quando_o_id_confere():
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 300}])
    jogo.id_por_slot = {0: 777}
    jogo.cura_sobe = 400
    mural.publicar_id("aliado", 777)
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 30.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert jogo.curas >= 1
    assert f.curas == 1
    assert mural.fila_de_cura(["aliado"]) == []   # saiu da fila


# ---------------------------------------------------------------------------
# O SLOT VEM DA MEMÓRIA, NÃO DA CONFIGURAÇÃO
# ---------------------------------------------------------------------------

def test_o_slot_segue_a_ordem_da_memoria():
    """O painel é ordenado pelo JOGO (ordem de entrada), não pelo config."""
    jogo = _Jogo(companheiros=["Primeiro", "Aliado", "Terceiro"])
    f = _fada(jogo)
    assert f._slot_do_nick("Aliado") == 1
    assert f._slot_do_nick("Primeiro") == 0
    assert f._slot_do_nick("Terceiro") == 2


def test_quem_nao_esta_no_painel_nao_e_clicado():
    """Saiu do time, ainda não entrou, ou a leitura falhou -- não se chuta."""
    jogo = _Jogo(companheiros=["Outro"])
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert jogo.cliques == []
    assert jogo.curas == 0


def test_sem_leitura_do_time_nao_clica():
    """`None` é "não sei", e quem não sabe não age."""
    jogo = _Jogo()
    jogo.companheiros = None
    f = _fada(jogo)
    assert f._slot_do_nick("Aliado") is None


def test_o_nick_e_comparado_sem_caixa():
    jogo = _Jogo(companheiros=["ALIADO"])
    f = _fada(jogo)
    assert f._slot_do_nick("aliado") == 0


# ---------------------------------------------------------------------------
# A FILA NÃO TRAVA
# ---------------------------------------------------------------------------

def test_desiste_da_cura_que_nao_sobe_e_libera_a_fila():
    """Vítima morta, fora de alcance, cura sem efeito: a fila não pode parar."""
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 100}])
    jogo.id_por_slot = {0: 777}
    jogo.cura_sobe = 0                    # a vida nunca sobe
    mural.publicar_id("aliado", 777)
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 10.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert f.curas_sem_efeito == 1
    assert mural.fila_de_cura(["aliado"]) == []   # liberada para a poção


def test_a_ordem_da_fila_e_de_chegada():
    mural.pedir_cura("segundo", 20.0)
    mural.pedir_cura("primeiro", 10.0)    # mais ferido, mas chegou depois
    assert mural.fila_de_cura(["primeiro", "segundo"]) == ["segundo", "primeiro"]


def test_a_propria_fada_nao_entra_na_fila_dela():
    jogo = _Jogo()
    mural.pedir_cura("fada", 20.0)
    f = _fada(jogo, membros=("fada", "aliado"))
    f._uma_volta()
    assert jogo.cliques == []


# ---------------------------------------------------------------------------
# SENTAR, MANA E BATALHA
# ---------------------------------------------------------------------------

def test_fila_vazia_senta():
    jogo = _Jogo()
    f = _fada(jogo)
    f._uma_volta()
    assert jogo.sentadas == 1
    assert f._sentada is True


def test_sentada_nao_senta_de_novo():
    """A tecla é INTERRUPTOR: apertar sentada a faria levantar."""
    jogo = _Jogo()
    f = _fada(jogo)
    f._uma_volta()
    f._uma_volta()
    assert jogo.sentadas == 1


def test_levanta_antes_de_curar():
    jogo = _Jogo()
    jogo.id_por_slot = {0: 777}
    mural.publicar_id("aliado", 777)
    f = _fada(jogo, membros=("fada", "aliado"))
    f._uma_volta()                        # fila vazia: senta
    assert f._sentada is True
    mural.pedir_cura("aliado", 25.0)
    f._uma_volta()                        # chegou pedido: levanta
    assert f._sentada is False
    assert jogo.sentadas == 2             # sentou e levantou


def test_mana_no_chao_senta_mesmo_com_fila():
    jogo = _Jogo(mana=5.0)
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))
    f._uma_volta()
    assert jogo.cliques == []
    assert jogo.sentadas == 1


def test_so_volta_a_curar_com_mana_suficiente():
    """Dois números e não um: com um só ela sentaria e levantaria a cada ponto."""
    jogo = _Jogo(mana=5.0)
    f = _fada(jogo)
    f._sentada = True
    jogo.mana = 30.0                      # acima do piso, abaixo do teto
    assert f._tenho_mana_para_curar() is False
    jogo.mana = 60.0
    assert f._tenho_mana_para_curar() is True


def test_sem_leitura_de_mana_ela_tenta():
    """Sem o número ela não adivinha: o pior caso é uma tecla sem efeito."""
    jogo = _Jogo()
    jogo.mana = None
    f = _fada(jogo)
    assert f._tenho_mana_para_curar() is True


def test_em_batalha_nao_cura():
    """Ela não luta, mas também não cura apanhando."""
    jogo = _Jogo(batalha=True)
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))
    f._uma_volta()
    assert jogo.cliques == []
    assert jogo.curas == 0


# ---------------------------------------------------------------------------
# A AUTO-CURA
# ---------------------------------------------------------------------------

def test_a_fada_cura_a_si_mesma_antes_da_fila():
    """Ela é a única do time sem quem a cure -- e Fada morta não cura ninguém."""
    jogo = _Jogo(vida=25.0)
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 28.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert jogo.auto_selecoes == 1        # selecionou a si mesma
    assert jogo.curas >= 1
    assert jogo.cliques == []             # e não foi atender ninguém


def test_a_auto_cura_para_no_alvo():
    jogo = _Jogo(vida=25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    class _Sobe:
        def __init__(self):
            self.n = 0

        def __call__(self):
            self.n += 1
            jogo.vida = 95.0 if self.n >= 2 else 25.0

    f._apertar_cura = _Sobe()
    f._uma_volta()
    assert jogo.vida >= 90.0


# ---------------------------------------------------------------------------
# A BATIDA
# ---------------------------------------------------------------------------

def test_a_batida_sai_de_dentro_do_laco():
    """Fora dele, uma Fada presa numa janela passaria por "de pé" sem curar."""
    jogo = _Jogo()
    passos = {"n": 0}

    def continuar():
        passos["n"] += 1
        return passos["n"] <= 2

    f = _fada(jogo, continuar=continuar)
    assert mural.fada_de_pe("fada") is False
    f.rodar()
    # Terminou: o `finally` limpa a batida, e sem batida a vítima bebe poção.
    assert mural.fada_de_pe("fada") is False


def test_a_batida_existe_enquanto_ela_gira():
    jogo = _Jogo()
    f = _fada(jogo)
    f.mural.bater_fada(f.meu_login)
    assert mural.fada_de_pe("fada") is True

# ---------------------------------------------------------------------------
# O FREIO -- medido em campo em 01/09/2026
# ---------------------------------------------------------------------------
#
# Com a confirmação falhando (a vítima não publicava o próprio id), o laço
# clicou no MESMO retrato 357 vezes, dez por segundo, e o personagem saiu
# ANDANDO de tanto clique. Insistir para sempre não cura ninguém e ainda
# estraga o que estava funcionando.

def test_desiste_da_vitima_depois_de_N_tentativas():
    jogo = _Jogo(alvo=555)
    jogo.id_por_slot = {0: None}          # o clique nunca pega: fica no 555
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    for _ in range(mod.MAXIMO_DE_TENTATIVAS_POR_VITIMA):
        f._uma_volta()

    assert mural.fila_de_cura(["aliado"]) == []      # saiu da fila
    assert len(jogo.cliques) == mod.MAXIMO_DE_TENTATIVAS_POR_VITIMA


def test_nunca_clica_mais_que_o_teto_na_mesma_vitima():
    """O laço gira a cada 100 ms: sem teto, isto vira centenas de cliques."""
    jogo = _Jogo(alvo=555)
    jogo.id_por_slot = {0: None}
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    for _ in range(50):                   # muito além do teto
        f._uma_volta()

    assert len(jogo.cliques) <= mod.MAXIMO_DE_TENTATIVAS_POR_VITIMA


def test_uma_vitima_perdida_nao_impede_a_seguinte():
    """A contagem é POR VÍTIMA: quem não dá para curar não derruba as outras."""
    jogo = _Jogo(companheiros=["Aliado", "Outro"], alvo=555,
                 vidas=[{"nome": "Outro", "hp": 300}])
    jogo.id_por_slot = {0: None, 1: 888}  # o primeiro nunca pega, o segundo sim
    jogo.cura_sobe = 400
    mural.publicar_id("aliado", 777)
    mural.publicar_id("outro", 888)
    mural.publicar_estado("outro", max_hp=1000)
    mural.pedir_cura("aliado", 25.0)
    mural.pedir_cura("outro", 25.0)
    f = _fada(jogo, membros=("fada", "aliado", "outro"))

    for _ in range(mod.MAXIMO_DE_TENTATIVAS_POR_VITIMA + 2):
        f._uma_volta()

    assert f.curas == 1                   # o segundo foi curado
    assert mural.fila_de_cura(["aliado", "outro"]) == []


def test_a_tentativa_bem_sucedida_zera_a_contagem():
    """Uma falha ocasional não pode condenar quem depois seleciona."""
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 300}], alvo=555)
    jogo.id_por_slot = {0: None}
    jogo.cura_sobe = 400
    mural.publicar_id("aliado", 777)
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()                        # falha 1
    assert f._tentativas.get("aliado") == 1
    jogo.id_por_slot = {0: 777}           # agora pega
    f._uma_volta()
    assert f._tentativas.get("aliado") is None
    assert f.curas == 1
