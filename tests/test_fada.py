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
from types import SimpleNamespace

import pytest

import blazesbot.bot.fada_reviver as mod_reviver
from blazesbot.bot import fada as mod
from blazesbot.bot import fada_ociosa
from blazesbot.bot import mural, mural_da_morte


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
                 companheiros=("Aliado", "Outro"), vidas=None, alvo=0,
                 login_por_slot=None):
        self.vida = vida
        self.mana = mana
        self.batalha = batalha
        self.companheiros = list(companheiros)
        self.revives = 0
        self.ao_reviver = None
        self.vidas = vidas if vidas is not None else [
            {"nome": "Aliado", "hp": 300}, {"nome": "Outro", "hp": 1000}]
        self.alvo = alvo
        # De quem é cada retrato. Serve para o dublê simular a VÍTIMA
        # republicando a própria vida enquanto é curada -- que é o que ela faz
        # de verdade, e a fonte que a Fada usa.
        self.login_por_slot = login_por_slot or {0: "aliado", 1: "outro"}
        self.cliques: list[int] = []
        self.curas = 0
        self.sentadas = 0
        # O QUE A MEMÓRIA DIZ, que é diferente do que o bot acha. `None` = sem
        # leitura, e aí o controle interno da Fada é tudo o que há.
        self.sentado = False
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

    def reviver(self) -> None:
        self.revives += 1
        if self.ao_reviver is not None:
            self.ao_reviver()

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
        # A VÍTIMA REPUBLICA. No bot de verdade ela faz isso a cada 0,2 s
        # enquanto espera; sem simular, a vida anunciada nunca subiria e a Fada
        # desistiria de todo mundo -- um falso negativo do dublê.
        login = self.login_por_slot.get(slot)
        if login:
            atual = mural.pedido_de(login)
            if atual is not None:
                mural.pedir_cura(login, min(100.0, atual + 40.0))

    def sentar(self) -> None:
        """A tecla é INTERRUPTOR: ela ALTERNA o estado, como no jogo."""
        self.sentadas += 1
        if self.sentado is not None:
            self.sentado = not self.sentado

    def auto_selecionar(self) -> None:
        self.auto_selecoes += 1


def _fada(jogo, *, membros=("lider", "aliado"), nicks=None, parar=90.0,
          pedir=30.0, continuar=None, cuidar_do_pet=None,
          limpar_a_bolsa=None, tem_reviver=True):
    nicks = nicks or {"aliado": "Aliado", "outro": "Outro", "fada": "Fada"}
    return mod.FadaDoTime(
        log=logging.getLogger("teste.fada"),
        meu_login="fada",
        meu_nick=lambda: "Fada",
        vida_pct=lambda: jogo.vida,
        mana_pct=lambda: jogo.mana,
        em_batalha=lambda: jogo.batalha,
        esta_sentado=lambda: jogo.sentado,
        companheiros=lambda: jogo.companheiros,
        vida_do_time=lambda: jogo.vidas,
        id_do_alvo=lambda: jogo.alvo,
        clicar_no_retrato=jogo.clicar,
        apertar_cura=jogo.curar,
        apertar_reviver=(jogo.reviver if tem_reviver else None),
        apertar_sentar=jogo.sentar,
        auto_selecionar=jogo.auto_selecionar,
        mural=mural,
        membros_do_time=lambda: list(membros),
        nick_de=lambda login: nicks.get(login, ""),
        continuar=continuar or (lambda: True),
        dormir=lambda s: True,
        pedir_pct=lambda: pedir,
        parar_pct=lambda: parar,
        cuidar_do_pet=cuidar_do_pet,
        limpar_a_bolsa=limpar_a_bolsa,
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


def test_ao_curar_ela_sai_do_descanso_SEM_apertar_a_tecla():
    """SENTAR NÃO É UMA TRAVA (regra do jogo, usuário, 01/09/2026).

    Sentada, a Fada clica e cura normalmente, e o estado sai sozinho na primeira
    ação. A tecla é INTERRUPTOR: apertá-la para "levantar" a SENTARIA caso ela
    já tivesse saído do chão sozinha -- bem na hora de curar, que é o único
    momento em que ela tem pressa.

    O QUE AINDA PRECISA ACONTECER é zerar a marca `_sentada`, porque ela é a
    histerese da mana. Sem isso a Fada ficaria presa exigindo `mana_para_voltar`
    para sempre.
    """
    jogo = _Jogo()
    jogo.id_por_slot = {0: 777}
    mural.publicar_id("aliado", 777)
    f = _fada(jogo, membros=("fada", "aliado"))
    f._uma_volta()                        # fila vazia: senta
    assert f._sentada is True
    assert jogo.sentadas == 1
    mural.pedir_cura("aliado", 25.0)
    f._uma_volta()                        # chegou pedido: age sentada
    assert f._sentada is False, "a histerese da mana não foi zerada"
    assert jogo.sentadas == 1, (
        f"apertou a tecla de sentar para 'levantar': {jogo.sentadas} toques")


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


def test_em_batalha_ela_CUIDA_DE_SI_e_nao_da_fila():
    """INVERTE a decisão anterior (ela sentava e confiava na proteção do time).

    O motivo mudou: o time só protege se estiver ATACANDO, e quem está
    esperando cura não está -- a proteção com que ela contava não existia
    justamente na hora em que ela precisava. Decisão do usuário em 01/09/2026:
    *"a ideia aqui é não deixar a fada morrer de forma alguma"*.
    """
    jogo = _Jogo(batalha=True)
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert jogo.auto_selecoes == 1, "não se selecionou para se curar"
    assert jogo.curas >= 1, "não se curou"
    assert jogo.cliques == [], "foi atender a fila em vez de se defender"
    assert mural.fada_em_batalha("fada") is True, "o time não soube"


def test_o_time_sabe_NA_HORA_que_ela_entrou_em_batalha():
    """*"É importante que o resto do time saiba o quanto antes."*

    A batida leva o estado junto, e ela sai de dentro de toda espera -- então o
    aviso chega antes da primeira tecla de cura, não depois.
    """
    jogo = _Jogo(batalha=True)
    f = _fada(jogo, membros=("fada", "aliado"))
    assert mural.fada_em_batalha("fada") is False
    f._uma_volta()
    assert mural.fada_em_batalha("fada") is True


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

# ---------------------------------------------------------------------------
# A FONTE DA VIDA DA VÍTIMA -- corrigido em 01/09/2026
# ---------------------------------------------------------------------------
#
# A Fada lia a vida do aliado pela struct do time e concluía "já está com 100%"
# sem apertar a cura uma vez. Medido no log:
#
#     FADA: curando BlazesAPP1 até 90% (vida 4555 de 4555)
#     FADA: BlazesAPP1 curado (100%). Próximo.
#
# O campo lido (`+0x34`) bate com a vida MÁXIMA, não com a atual -- o par dele
# (`+0x3C`) deu o `baseMana`, e não a mana. Enquanto o offset da vida atual não
# for confirmado, quem manda é o que a VÍTIMA publica: ela lê o próprio hp e
# max_hp com precisão de inteiro.

def test_a_vida_anunciada_pela_vitima_manda():
    """Mesmo com a struct dizendo vida cheia, o que vale é o anúncio."""
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 99999}])   # struct diz "cheio"
    f = _fada(jogo, membros=("fada", "aliado"))
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 25.0)
    assert f._quanto_de_vida("aliado", "Aliado", 1000) == 25.0


def test_sem_anuncio_cai_para_a_struct():
    """A struct é RESERVA -- some quando a vítima fala, volta quando ela cala."""
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 500}])
    f = _fada(jogo, membros=("fada", "aliado"))
    assert f._quanto_de_vida("aliado", "Aliado", 1000) == 50.0


def test_aperta_a_cura_ate_a_vida_anunciada_chegar_no_alvo():
    """O defeito era não apertar NENHUMA vez. Aqui tem de apertar."""
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 300}])
    jogo.id_por_slot = {0: 777}
    jogo.cura_sobe = 1                    # liga a republicação do dublê
    mural.publicar_id("aliado", 777)
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 20.0)      # 20% -> precisa de 2 curas para 90%
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()

    assert jogo.curas >= 2
    assert f.curas == 1

# ---------------------------------------------------------------------------
# A BATIDA NÃO PODE PARAR ENQUANTO ELA CURA -- 01/09/2026
# ---------------------------------------------------------------------------
#
# A batida ficava só no topo do laço externo, e a Fada não volta lá enquanto
# cura. Medido no log, com 6 s entre as duas linhas:
#
#     02:27:15  Pedi cura à Fada (vida 24%)
#     02:27:15  FADA: curando BlazesAPP1 até 90%
#     02:27:21  A Fada parou de responder -- vou de poção
#     02:27:21  FADA: BlazesAPP1 curado (100%)
#
# A vítima bebeu poção ENQUANTO ESTAVA SENDO CURADA. Tendo Fada de pé, ela tem
# de ser a única fonte de cura do time.

def test_toda_espera_bate_no_mural():
    """Não importa onde ela esteja: se está esperando, está viva."""
    jogo = _Jogo()
    f = _fada(jogo)
    mural.esquecer_fada("fada")
    assert mural.fada_de_pe("fada") is False
    f._dormir(0)
    assert mural.fada_de_pe("fada") is True


def test_a_batida_continua_durante_a_cura():
    """É o caso exato do log: curar demora, e a vítima não pode desistir."""
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 300}])
    jogo.id_por_slot = {0: 777}
    jogo.cura_sobe = 1
    mural.publicar_id("aliado", 777)
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 10.0)      # precisa de várias curas
    f = _fada(jogo, membros=("fada", "aliado"))

    batidas = []
    original = f._dormir_de_verdade

    def espiar(segundos):
        batidas.append(mural.fada_de_pe("fada"))
        mural.esquecer_fada("fada")       # some a cada espera...
        return original(segundos)

    f._dormir_de_verdade = espiar
    f._uma_volta()

    # ...e mesmo assim TODA espera encontrou a batida recém-dada.
    assert batidas, "a cura não esperou nenhuma vez"
    assert all(batidas), "houve espera sem batida -- a vítima desistiria"

def test_o_pedido_retirado_encerra_a_cura():
    """A vítima decide quando está boa: ao chegar no alvo ela volta para a macro
    e retira o pedido.

    Medido em campo (01/09/2026): ela avisou "curado (94%)" e NOVE segundos
    depois a Fada anunciou que tinha desistido dela -- porque ficou olhando um
    pedido que não existia mais até o teto de 20 s. O sumiço do pedido É o
    aviso, e já estava ali.
    """
    jogo = _Jogo(vidas=[{"nome": "Aliado", "hp": 300}])
    jogo.id_por_slot = {0: 777}
    mural.publicar_id("aliado", 777)
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    # A vítima se dá por curada na primeira tecla de cura.
    def curar_e_sair():
        jogo.curas += 1
        mural.cancelar_pedido("aliado")
    f._apertar_cura = curar_e_sair

    f._uma_volta()

    assert f.curas == 1
    assert f.curas_sem_efeito == 0, "desistiu de quem já estava curado"


def test_fora_do_painel_avisa_UMA_vez_e_espera():
    """O laço gira a 10 Hz: sem freio, treze avisos iguais em dois segundos."""
    jogo = _Jogo(companheiros=["Outro"])
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    esperas = []
    f._dormir_de_verdade = lambda s: (esperas.append(s), True)[1]

    for _ in range(5):
        f._uma_volta()

    assert "Aliado" in f._avisei_fora_do_painel
    assert esperas, "não esperou entre as tentativas"
    assert jogo.cliques == []

# ===========================================================================
# O QUE A REVISÃO DO CODEX PEGOU -- 01/09/2026
# ===========================================================================

def test_a_confirmacao_espera_a_memoria_virar():
    """O alvo ANTERIOR ainda aparece logo depois do clique (36-123 ms medidos).

    A versão anterior condenava no primeiro olhar em que o id fosse diferente e
    não-zero -- e nesse instante ele SEMPRE é o anterior. Ou seja, ela reprovava
    toda cura em que já houvesse um alvo antes, que é o caso comum.
    """
    jogo = _Jogo(alvo=555, vidas=[{"nome": "Aliado", "hp": 300}])
    mural.publicar_id("aliado", 777)
    mural.publicar_estado("aliado", max_hp=1000)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    # O clique pega, mas a memória só mostra o alvo novo na segunda leitura.
    leituras = {"n": 0}

    def id_atrasado():
        leituras["n"] += 1
        return 555 if leituras["n"] <= 1 else 777
    f._id_do_alvo = id_atrasado

    assert f._clique_saiu_errado("aliado", "Aliado") is False


def test_quem_nao_esta_no_painel_nao_trava_a_fila():
    """Parar no primeiro deixaria TODOS os de trás sem cura -- e como a Fada
    continua batendo, eles esperariam para sempre."""
    jogo = _Jogo(companheiros=["Outro"],          # "Aliado" não está no painel
                 vidas=[{"nome": "Outro", "hp": 300}])
    jogo.id_por_slot = {0: 888}
    jogo.cura_sobe = 1
    jogo.login_por_slot = {0: "outro"}
    mural.publicar_id("outro", 888)
    mural.publicar_estado("outro", max_hp=1000)
    mural.pedir_cura("aliado", 25.0)              # chegou primeiro, mas não dá
    mural.pedir_cura("outro", 25.0)
    f = _fada(jogo, membros=("fada", "aliado", "outro"))

    f._uma_volta()

    assert f.curas == 1, "o segundo da fila ficou sem cura por causa do primeiro"


def test_sair_da_fila_zera_a_contagem_de_tentativas():
    """Um pedido cancelado e refeito não pode herdar a contagem do anterior."""
    jogo = _Jogo(alvo=555)
    jogo.id_por_slot = {0: None}
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))

    f._uma_volta()
    assert f._tentativas.get("aliado") == 1

    mural.cancelar_pedido("aliado")
    f._uma_volta()                                # fila vazia: limpa
    assert "aliado" not in f._tentativas


def test_o_aviso_de_fora_do_painel_nao_cresce_para_sempre():
    jogo = _Jogo(companheiros=["Outro"])
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"))
    f._uma_volta()
    assert f._avisei_fora_do_painel == {"Aliado"}

    mural.cancelar_pedido("aliado")
    f._uma_volta()
    assert f._avisei_fora_do_painel == set()

# ===========================================================================
# OS CUIDADOS DE OCIOSA: pet e bolsa
# ===========================================================================
#
# *"Essas verificações podem ser feitas enquanto a fada está ociosa, mas não
# deixa direto, para não ficar pesando, e param na hora se algum aliado entrar
# na fila de cura ou ela entrar em batalha."*

def test_ociosa_ela_cuida_do_pet_e_da_bolsa():
    feitos = []
    jogo = _Jogo()
    f = _fada(jogo,
              cuidar_do_pet=lambda: feitos.append("pet"),
              limpar_a_bolsa=lambda: feitos.append("bolsa"))
    f._uma_volta()
    assert feitos == ["pet", "bolsa"]


def test_os_cuidados_tem_CADENCIA_e_nao_saem_a_cada_giro():
    """Sem cadência ela gastaria o laço em manutenção em vez de ficar pronta."""
    feitos = []
    jogo = _Jogo()
    f = _fada(jogo, cuidar_do_pet=lambda: feitos.append("pet"))
    for _ in range(20):
        f._uma_volta()
    assert feitos == ["pet"], feitos


def test_com_alguem_na_fila_ela_NAO_cuida():
    """Abrir o inventário com alguém esperando cura mata o alguém."""
    feitos = []
    jogo = _Jogo()
    jogo.id_por_slot = {0: 777}
    mural.publicar_id("aliado", 777)
    mural.pedir_cura("aliado", 25.0)
    f = _fada(jogo, membros=("fada", "aliado"),
              cuidar_do_pet=lambda: feitos.append("pet"))
    f._uma_volta()
    assert feitos == []


def test_em_batalha_ela_NAO_cuida():
    feitos = []
    jogo = _Jogo(batalha=True)
    f = _fada(jogo, cuidar_do_pet=lambda: feitos.append("pet"))
    f._uma_volta()
    assert feitos == []


def test_a_bolsa_e_reconferida_ENTRE_o_pet_e_ela():
    """O pedido pode chegar no meio: a condição vale antes de CADA um dos dois,
    não só na entrada."""
    feitos = []
    jogo = _Jogo()

    def pet_que_atrasa():
        feitos.append("pet")
        mural.pedir_cura("aliado", 25.0)   # alguém entrou na fila agora

    f = _fada(jogo, membros=("fada", "aliado"),
              cuidar_do_pet=pet_que_atrasa,
              limpar_a_bolsa=lambda: feitos.append("bolsa"))
    f._uma_volta()
    assert feitos == ["pet"], "abriu a bolsa com alguém já na fila"


def test_sem_as_funcoes_injetadas_ela_nao_faz_nada():
    """Fada sem pet: quem injeta passa `None` nos dois, e ela nem tenta."""
    jogo = _Jogo()
    f = _fada(jogo)
    f._uma_volta()          # não pode explodir
    assert f._cuidar_do_pet is None

# ===========================================================================
# ANTES DE SENTAR, PERGUNTA À MEMÓRIA -- 01/09/2026
# ===========================================================================
#
# *"Verifica pela memória se a fada já está sentada; caso esteja, não precisa
# fazer ela sentar, pois senão faz ela levantar. Isso vale para tudo: sempre
# antes de sentar verifica se já não está sentado, pq se tiver é só não fazer
# nada."*
#
# O controle interno (`_sentada`) descreve o que o BOT fez, não o que
# aconteceu: um golpe levanta o personagem sem passar por aqui, e um relogin
# devolve o estado sem avisar ninguém.

def test_ja_sentada_nao_aperta_a_tecla():
    """Apertar aqui a faria LEVANTAR -- o oposto do que se queria."""
    jogo = _Jogo()
    jogo.sentado = True                   # a memória diz que já está no chão
    f = _fada(jogo)
    f._uma_volta()
    assert jogo.sentadas == 0
    assert f._sentada is True             # o controle interno se acertou


def test_algo_a_levantou_e_ela_senta_de_novo():
    """O bot achava que estava sentada, mas um golpe a levantou."""
    jogo = _Jogo()
    f = _fada(jogo)
    f._uma_volta()                        # senta
    assert jogo.sentadas == 1
    jogo.sentado = False                  # levantou por fora
    f._sentada = True                     # o bot ainda acha que está sentada
    f._uma_volta()
    assert jogo.sentadas == 2, "confiou no controle interno e ficou de pé"


def test_ja_de_pe_nao_aperta_ao_levantar():
    """O espelho da regra: apertar de pé a faria SENTAR na hora de curar."""
    jogo = _Jogo()
    jogo.sentado = False
    f = _fada(jogo)
    f._sentada = True                     # controle interno errado
    fada_ociosa.levantar(f)
    assert jogo.sentadas == 0
    assert f._sentada is False


def test_sem_leitura_usa_o_controle_interno():
    """Cega, ela volta a se guiar pelo que fez -- que é tudo o que sobra."""
    jogo = _Jogo()
    jogo.sentado = None
    f = _fada(jogo)
    f._uma_volta()
    assert jogo.sentadas == 1
    f._uma_volta()
    assert jogo.sentadas == 1, "sentou duas vezes sem leitura"


# ---------------------------------------------------------------------------
# OS BURACOS DE SILÊNCIO -- a Fada VIVA que o time dava por morta (04/09/2026)
# ---------------------------------------------------------------------------
#
# Relato do usuário: *"se a fada cai, muitas vezes o bot não reconhece"*. O
# levantamento achou os dois lados da mesma moeda: a queda que ninguém via
# (consertada em `fada_montagem`) e o INVERSO -- a Fada viva que passa mais de
# `SILENCIO_DA_FADA` sem bater, e aí o time inteiro conclui que ela sumiu e vai
# de poção com ela parada ao lado.


def test_a_limpeza_da_bolsa_AVISA_que_vai_sumir():
    """O deletador tem teto de 10 s, o DOBRO do silêncio que mata a batida.

    Sem o aviso, quem entra na fila durante uma limpeza bebe poção -- e essa
    era a janela mais larga de todas.
    """
    jogo = _Jogo()
    validades = []

    def limpar():
        # No meio da limpeza, é isto que o time enxerga.
        validades.append(mural._FADAS["fada"][2])

    f = _fada(jogo, cuidar_do_pet=lambda: None, limpar_a_bolsa=limpar)
    fada_ociosa.cuidados(f)

    assert validades, "a bolsa nem foi limpa"
    assert validades[0] > mural.SILENCIO_DA_FADA, validades
    assert validades[0] <= mural.TETO_DA_BATIDA_LONGA


def test_a_validade_longa_NAO_SOBRA_depois_da_limpeza():
    """Terminada a tarefa, uma morte tem de voltar a aparecer nos 5 s de
    sempre -- senão o aviso vira desculpa permanente."""
    jogo = _Jogo()
    f = _fada(jogo, cuidar_do_pet=lambda: None, limpar_a_bolsa=lambda: None)
    fada_ociosa.cuidados(f)

    assert mural._FADAS["fada"][2] == mural.SILENCIO_DA_FADA


def test_o_aviso_tem_TETO():
    """Uma Fada que morre DURANTE a tarefa longa custa a espera a mais -- por
    isso o quanto ela pode pedir é limitado."""
    mural.bater_fada("fada", vale_por=10_000)
    assert mural._FADAS["fada"][2] == mural.TETO_DA_BATIDA_LONGA


def test_o_aviso_nunca_ENCURTA_o_silencio_padrao():
    mural.bater_fada("fada", vale_por=0.1)
    assert mural._FADAS["fada"][2] == mural.SILENCIO_DA_FADA


def test_a_batida_sai_de_UMA_VOLTA_e_nao_so_do_rodar():
    """A Fada da HH chama `_uma_volta` de dentro do laço de acompanhar o líder
    -- o `rodar()`, que era o único lugar que batia, nunca entra ali. Com a fila
    vazia o giro voltava sem passar por espera nenhuma, e a batida só saía por
    acaso."""
    jogo = _Jogo()
    f = _fada(jogo)
    mural.esquecer_fada("fada")

    f._uma_volta()

    assert mural.fada_de_pe("fada") is True


def test_em_batalha_a_batida_de_UMA_VOLTA_leva_o_estado_junto():
    jogo = _Jogo()
    jogo.batalha = True
    f = _fada(jogo)
    f._uma_volta()
    assert mural.fada_em_batalha("fada") is True


# ---------------------------------------------------------------------------
# A DESISTÊNCIA PRECISA CHEGAR NA VÍTIMA -- laço infinito medido em 04/09/2026
# ---------------------------------------------------------------------------
#
# A Fada desistia (teto estourado, tentativas esgotadas, sem nick) e só apagava
# o pedido. A vítima, que republica a própria vida a cada 0,2 s enquanto espera,
# voltava para a fila em seguida -- com hora NOVA, portanto no fim dela. A Fada
# desistia de novo. E de novo. Ninguém bebia a poção que resolveria.


def test_desistir_AVISA_a_vitima_e_nao_so_tira_da_fila():
    mural.pedir_cura("aliado", 30.0)

    mural.desistir_da_vitima("aliado")

    assert mural.pedido_de("aliado") is None
    assert mural.fada_desistiu_de("aliado") is True


def test_republicar_o_pedido_NAO_apaga_a_desistencia():
    """É exatamente o que fechava o laço: a vítima republica em 0,2 s, e se isso
    limpasse o recado ela nunca o leria."""
    mural.pedir_cura("aliado", 30.0)
    mural.desistir_da_vitima("aliado")

    mural.pedir_cura("aliado", 29.0)          # a republicação de sempre

    assert mural.fada_desistiu_de("aliado") is True


def test_a_vitima_LE_o_recado_e_ele_some():
    mural.desistir_da_vitima("aliado")
    mural.esquecer_desistencia("aliado")
    assert mural.fada_desistiu_de("aliado") is False


def test_a_marca_VENCE_sozinha():
    """Ela é um recado, não um banimento: depois de beber a poção e voltar a
    ficar ferido, insistir é barato -- a Fada pode ter saído da briga, a vítima
    pode ter voltado ao painel. Por isso a validade é curta."""
    assert 0 < mural.VALIDADE_DA_DESISTENCIA <= 60

    mural.desistir_da_vitima("aliado")
    mural._DESISTENCIAS["aliado"] -= mural.VALIDADE_DA_DESISTENCIA + 1

    assert mural.fada_desistiu_de("aliado") is False


def test_desistir_por_TENTATIVAS_avisa():
    """O freio dos 3 cliques: a vítima tem de saber que caiu por ele."""
    jogo = _Jogo(alvo=555)                     # o clique nunca seleciona
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo)
    mural.pedir_cura("aliado", 30.0)

    for _ in range(mod.MAXIMO_DE_TENTATIVAS_POR_VITIMA):
        f._atender("aliado")

    assert mural.fada_desistiu_de("aliado") is True


# ---------------------------------------------------------------------------
# O LADO DA VÍTIMA -- `chamar_a_fada` é fechadura dentro do supervisor
# ---------------------------------------------------------------------------
#
# Ela não dá para instanciar sem uma conta e uma janela de jogo, então o que se
# trava aqui é a PRESENÇA das três saídas. Sem elas, a espera volta a ser
# eterna -- que foi o estado medido.

def test_a_espera_da_vitima_tem_as_tres_saidas():
    import inspect

    from blazesbot.bot import supervisor as mod_sup

    fonte = inspect.getsource(mod_sup.AccountSupervisor._rodar_modo_app)
    laco = fonte.split("def chamar_a_fada")[1]

    assert "fada_desistiu_de" in laco, "a vítima não lê a desistência da Fada"
    assert "TETO_DA_ESPERA_PELA_FADA" in laco, "a espera voltou a ser sem teto"
    assert "em_batalha() is True" in laco, ("sentada apanhando, a vítima tem de "
                                            "voltar a rodar a macro")


def test_o_teto_da_espera_e_MUITO_maior_que_uma_cura():
    from blazesbot.bot import supervisor as mod_sup

    assert mod_sup.TETO_DA_ESPERA_PELA_FADA >= 10 * mod.ESPERA_ENTRE_CURAS


# ---------------------------------------------------------------------------
# ID VELHO É PIOR QUE ID NENHUM -- 04/09/2026
# ---------------------------------------------------------------------------
#
# `mural._IDS` é dicionário de módulo: sobrevive ao relogin inteiro. O id da
# ENTIDADE, não -- ela morre com a sessão. A Fada clicava no retrato, lia o id
# novo, comparava com o velho daqui e concluía que tinha clicado na pessoa
# errada, descartando a vítima certa depois de três tentativas.


def test_esquecer_id_apaga_a_publicacao():
    mural.publicar_id("aliado", 4242)
    mural.esquecer_id("aliado")
    assert mural.id_publicado("aliado") is None


def test_sem_id_a_Fada_volta_a_CONFIAR_NO_SLOT():
    """É o desfecho que torna esquecer melhor que manter: sem id publicado ela
    usa o slot do painel, que é o que o usuário mandou fazer."""
    jogo = _Jogo(alvo=999)                 # id do jogo != qualquer publicado
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo)
    mural.publicar_id("aliado", 111)       # id VELHO, de outra sessão
    mural.pedir_cura("aliado", 30.0)

    assert f._atender("aliado") == (False, True), "id velho curou alguém"

    mural.esquecer_id("aliado")
    assert f._atender("aliado")[0] is True


def test_toda_morte_de_janela_esquece_o_id():
    """`_release` é o caminho por onde passam os cinco jeitos de uma janela
    morrer -- é por isso que o esquecimento mora lá, e não em `_encerrar_caido`."""
    import inspect

    from blazesbot.bot import supervisor as mod_sup

    assert "esquecer_id" in inspect.getsource(mod_sup.AccountSupervisor._release)


# ---------------------------------------------------------------------------
# A FADA REVIVENDO -- 04/09/2026
# ---------------------------------------------------------------------------
#
# *"Vamos fazer a fada reviver ele; vai ter que adicionar uma tecla para isso."*
# A prioridade é do usuário: a cura vem primeiro, EXCETO para quem já está caído
# há muito tempo -- um morto não apanha nem gasta poção, e tem prazo próprio
# para se reviver sozinho; um ferido sentado esperando pode virar o próximo
# morto.




@pytest.fixture(autouse=True)
def _feitico_rapido(monkeypatch):
    """O teto real é de 12 s (os 5 s de preparo mais folga). Aqui interessa o
    que ela FAZ, não o relógio."""
    monkeypatch.setattr(mod_reviver, "TETO_DO_FEITICO", 0.05)
    monkeypatch.setattr(mod_reviver, "PASSO_DA_ESPERA", 0.01)


def _envelhecer_a_morte(login, segundos):
    quando, nick = mural_da_morte._MORTOS[login]
    mural_da_morte._MORTOS[login] = (quando - segundos, nick)


def test_a_CURA_vem_antes_do_morto_recente():
    jogo = _Jogo()
    jogo.companheiros = ["Aliado", "Outro"]
    f = _fada(jogo, membros=("aliado", "outro"),
              nicks={"aliado": "Aliado", "outro": "Outro"})
    mural.pedir_cura("aliado", 30.0)
    mural.morri("outro", nick="Outro")      # morreu agora, não é urgente

    f._uma_volta()

    assert jogo.curas >= 1, "curou ninguém"
    assert jogo.revives == 0, "reviveu na frente de um ferido"


def test_o_morto_ANTIGO_fura_a_fila():
    jogo = _Jogo()
    jogo.companheiros = ["Aliado", "Outro"]
    f = _fada(jogo, membros=("aliado", "outro"),
              nicks={"aliado": "Aliado", "outro": "Outro"})
    mural.pedir_cura("aliado", 30.0)
    mural.morri("outro", nick="Outro")
    _envelhecer_a_morte("outro",
                        mural.SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA + 1)
    jogo.ao_reviver = lambda: mural.esquecer_morte("outro")

    f._uma_volta()

    assert jogo.revives == 1, "o morto antigo continuou esperando"


def test_com_a_fila_de_cura_VAZIA_o_morto_e_atendido_na_hora():
    jogo = _Jogo()
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo)
    mural.morri("aliado", nick="Aliado")
    # De pé, a VÍTIMA sai da fila -- é ela quem lê o próprio hp.
    jogo.ao_reviver = lambda: mural.esquecer_morte("aliado")

    f._uma_volta()

    assert jogo.revives == 1


def test_sem_tecla_configurada_ela_nao_tenta_e_avisa_UMA_vez(caplog):
    jogo = _Jogo()
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo, tem_reviver=False)
    mural.morri("aliado", nick="Aliado")

    with caplog.at_level("WARNING"):
        f._uma_volta()
        f._uma_volta()

    assert jogo.revives == 0
    avisos = [r for r in caplog.records if "tecla de reviver" in r.getMessage()]
    assert len(avisos) == 1, "avisou mais de uma vez"


def test_o_id_que_nao_bate_NAO_impede_o_reviver():
    """AQUI A REGRA É O CONTRÁRIO DA CURA, e foi medido em 06/09/2026.

    O retrato do morto continua clicável, mas o clique NÃO põe o id dele no
    `TARGET_ID` -- então exigir que batesse reprovava a única coisa que ia
    funcionar. Em campo: a Fada desistiu em 2 s e a vítima esperou 58 s de prazo
    à toa. Quem manda no reviver é o SLOT do painel, que vem da memória.
    """
    jogo = _Jogo(alvo=555)                  # o id nunca bate
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo)
    mural.publicar_id("aliado", 4242)
    mural.morri("aliado", nick="Aliado")
    jogo.ao_reviver = lambda: mural.esquecer_morte("aliado")

    f._uma_volta()

    assert jogo.revives == 1, "o id voltou a vetar o reviver"


def test_o_morto_que_nao_levanta_CONTINUA_na_fila(monkeypatch):
    """Ela passa adiante, mas não larga: o prazo do morto é de 60 s, e a janela
    dela é de 10. Largar no primeiro ciclo desperdiça 50 s que ainda existiam --
    foi o que aconteceu na medição de campo."""
    monkeypatch.setattr(mod_reviver, "JANELA_DE_TENTATIVAS", 0.05)
    jogo = _Jogo()
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo)
    mural.morri("aliado", nick="Aliado")   # ninguém tira o pedido: não levanta

    f._uma_volta()

    assert jogo.revives >= 1, "nem tentou"
    assert mural.esta_morto("aliado") is True, "largou o morto cedo demais"


def test_o_numero_de_TOQUES_na_janela_tem_teto(monkeypatch):
    """Cinto de segurança do defeito de 01/09/2026: com a espera devolvendo na
    hora, o laço clicou 357 vezes no mesmo retrato e o personagem saiu ANDANDO.
    """
    jogo = _Jogo()
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo)
    mural.morri("aliado", nick="Aliado")

    f._uma_volta()

    assert jogo.revives == mod_reviver.MAXIMO_DE_TOQUES, jogo.revives


def test_ela_AVISA_que_comecou_a_conjurar():
    """Sem o aviso, a vítima clica no Ok do jogo no meio dos 5 s de preparo: a
    mana da Fada vai fora e a janela de convite aparece para quem já está
    vivo."""
    jogo = _Jogo()
    jogo.companheiros = ["Aliado"]
    f = _fada(jogo)
    mural.morri("aliado", nick="Aliado")
    avisou = []

    def de_pe():
        avisou.append(mural.fada_conjurando_em("aliado"))
        mural.esquecer_morte("aliado")     # de pé, ela sai da fila

    jogo.ao_reviver = de_pe

    f._uma_volta()

    assert avisou == [True], "apertou a tecla sem avisar o time"


def test_sem_mana_ela_nem_aperta():
    """O reviver custa muito mais que uma cura (1168 na medição) -- apertar sem
    ter só queima a recarga."""
    jogo = _Jogo()
    jogo.companheiros = ["Aliado"]
    jogo.mana = 1.0
    f = _fada(jogo)
    mural.morri("aliado", nick="Aliado")

    f._uma_volta()

    assert jogo.revives == 0


def test_a_propria_Fada_nao_entra_na_fila_dos_mortos():
    jogo = _Jogo()
    f = _fada(jogo)
    mural.morri("fada", nick="Fada")

    f._uma_volta()

    assert jogo.revives == 0


def test_o_pedido_de_PARAR_sobe_de_dentro_do_reviver():
    """Achado do Codex em 06/09/2026: `_esperar_levantar` devolve `False` tanto
    para "o feitiço não pegou" quanto para "mandaram parar", e o laço tratava os
    dois como "passo adiante" -- a Fada seguia mais uma volta depois da ordem de
    parada."""
    jogo = _Jogo()
    jogo.companheiros = ["Aliado"]
    parar = {"agora": False}
    f = _fada(jogo, continuar=lambda: not parar["agora"])
    mural.morri("aliado", nick="Aliado")

    def ao_apertar():
        parar["agora"] = True          # o usuário mandou parar no meio da espera

    jogo.ao_reviver = ao_apertar

    assert mod_reviver.reviver(f, "aliado") is False


# ---------------------------------------------------------------------------
# TIME DESFEITO NO JOGO -- contingência de 07/09/2026
# ---------------------------------------------------------------------------
#
# *"Quando todos os personagens do time APP caem, o jogo desfaz a party
# automaticamente. Sem a party, a fada não consegue aplicar a cura em grupo.
# Como a recriação automática do time não está implementada, precisamos de uma
# medida de contingência quando os personagens reconectarem."* -- usuário.
#
# Nada no bot era avisado: a configuração continuava listando o time, o mural
# continuava com a Fada batendo, e a vítima esperava o teto inteiro por uma cura
# que não tinha como sair -- a Fada não teria retrato para clicar.

def _supervisor_falso(quantos):
    """Um supervisor com só o que `_time_desfeito_no_jogo` precisa."""
    from blazesbot.bot.supervisor import AccountSupervisor

    sup = AccountSupervisor.__new__(AccountSupervisor)
    sup._memoria_do_app = SimpleNamespace(tamanho_do_time=lambda: quantos)
    return sup


def test_time_com_gente_NAO_e_desfeito():
    from blazesbot.bot.supervisor import AccountSupervisor

    sup = _supervisor_falso(3)
    assert AccountSupervisor._time_desfeito_no_jogo(sup) is False


def test_SO_EU_no_time_e_time_desfeito():
    """`tamanho_do_time` CONTA o próprio personagem: 1 é "só eu"."""
    from blazesbot.bot.supervisor import AccountSupervisor

    assert AccountSupervisor._time_desfeito_no_jogo(_supervisor_falso(1)) is True
    assert AccountSupervisor._time_desfeito_no_jogo(_supervisor_falso(0)) is True


def test_leitura_que_NAO_RESPONDE_nao_desliga_a_fada():
    """`None` é "não sei", e tratá-lo como "sem time" tiraria a cura em grupo de
    todo mundo no primeiro soluço de memória. Só o ponteiro CONFIRMANDO derruba
    a dependência."""
    from blazesbot.bot.supervisor import AccountSupervisor

    assert AccountSupervisor._time_desfeito_no_jogo(_supervisor_falso(None)) is False


def test_leitura_que_EXPLODE_nao_desliga_a_fada():
    from blazesbot.bot.supervisor import AccountSupervisor

    sup = AccountSupervisor.__new__(AccountSupervisor)

    def _explode():
        raise RuntimeError("processo sumiu")

    sup._memoria_do_app = SimpleNamespace(tamanho_do_time=_explode)
    assert AccountSupervisor._time_desfeito_no_jogo(sup) is False


def test_sem_memoria_do_app_nao_desliga_a_fada():
    from blazesbot.bot.supervisor import AccountSupervisor

    sup = AccountSupervisor.__new__(AccountSupervisor)
    assert AccountSupervisor._time_desfeito_no_jogo(sup) is False


def test_a_vitima_CONSULTA_o_time_antes_de_esperar_a_fada():
    """Trava estrutural: se o portão sair, a vítima volta a esperar o teto
    inteiro por uma cura que a party desfeita não permite."""
    import inspect

    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = inspect.getsource(AccountSupervisor._rodar_modo_app)
    laco = fonte.split("def chamar_a_fada")[1]
    assert "_time_desfeito_no_jogo" in laco
    # E ANTES de publicar o pedido: pedir e depois desistir deixaria a vítima na
    # fila da Fada por nada.
    assert laco.index("_time_desfeito_no_jogo") < laco.index("mural.pedir_cura")


def test_o_ponteiro_guardado_MORRE_com_o_handle():
    """Apontar para uma memória fechada faria a leitura devolver lixo -- e lixo
    aqui desligaria a Fada do time inteiro."""
    import inspect

    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = inspect.getsource(AccountSupervisor._rodar_modo_app)
    assert "self._memoria_do_app = None" in fonte
