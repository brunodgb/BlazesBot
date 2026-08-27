"""O catador de loot: clica no botão até ele SUMIR, e só onde ele foi visto.

=============================================================================
O QUE ESTÁ SOB TESTE
=============================================================================

O catador substitui a skill de auto pick do pet, para a conta cujo pet não a
tem. Ele junta duas implementações de outros bots:

* do **T-R0XX** o anel de cliques direitos por mensagem de janela (sem mouse
  físico) -- mas ele é CEGO: gasta os oito cliques mais 3 s toda vez, ache ou
  não ache, e clica no "Pick Up" numa coordenada fixa;
* do **AutoFarmBot** a localização do botão POR IMAGEM e a conferência depois de
  cada clique -- mas ele usa `pyautogui`, que move o mouse físico.

=============================================================================
OS DOIS TESTES QUE CARREGAM O PESO
=============================================================================

**1. `test_nunca_clica_esquerdo_sem_ter_visto_o_botao`.**

O instinto diz que o perigo é o anel, porque o `CLAUDE.md` persegue em cinco
lugares o clique que cai na cena 3D e faz o personagem ANDAR. **É o contrário:**
neste jogo quem move é o botão ESQUERDO. Então o anel de direitos é livre, e o
clique perigoso é o do botão -- que sem o botão na tela cai na cena 3D e manda o
personagem andar a segundos da saída da cave.

Achar o botão por IMAGEM em vez de coordenada fixa torna isso seguro por
construção: sem botão visto, não há coordenada para clicar.

**2. `test_clica_ate_o_botao_sumir`.**

O critério de parada é do usuário: *"até ele sumir deve ficar clicando nele...
quando sumir o botão aí de fato pode abrir o inventário"*. Parar antes deixa
item no chão sem nenhum sintoma visível -- o tipo de defeito que só aparece
comparando o ouro do dia com o esperado.
"""
from types import SimpleNamespace

import pytest

from blazesbot.core import catador

LOOT = (505, 390)
BOTAO = (447, 479)


class ClienteFalso:
    """Modela o botão "Pick up all": aparece com o clique CERTO e some ao ser
    clicado N vezes.

    `ponto_que_abre = None` significa "não há loot no chão" -- nenhum clique faz
    o botão aparecer.
    """

    def __init__(self, ponto_que_abre=None, ja_visivel=False,
                 cliques_para_sumir=1, onde_o_botao_aparece=BOTAO):
        self.ponto_que_abre = ponto_que_abre
        self.visivel = ja_visivel
        self.cliques_para_sumir = cliques_para_sumir
        self.onde = onde_o_botao_aparece
        self.direitos: list[tuple[int, int]] = []
        self.esquerdos: list[tuple[int, int]] = []
        self.log = SimpleNamespace(info=lambda *a, **k: None,
                                   warning=lambda *a, **k: None,
                                   debug=lambda *a, **k: None)

    def clicar_direito(self, ponto):
        self.direitos.append(ponto)
        if ponto == self.ponto_que_abre:
            self.visivel = True

    def clicar_esquerdo(self, ponto):
        self.esquerdos.append(ponto)
        if not self.visivel:
            return                      # caiu na cena 3D: nada acontece aqui
        self.cliques_para_sumir -= 1
        if self.cliques_para_sumir <= 0:
            self.visivel = False

    def localizar_botao(self):
        return self.onde if self.visivel else None

    def esperar(self, _s):
        pass


def _catar(cliente):
    return catador.catar(
        ponto_do_loot=LOOT,
        localizar_botao=cliente.localizar_botao,
        clicar_direito=cliente.clicar_direito,
        clicar_esquerdo=cliente.clicar_esquerdo,
        esperar=cliente.esperar,
        log=cliente.log,
    )


# ---------------------------------------------------------------------------
# 1. A REGRA DURA: o clique esquerdo
# ---------------------------------------------------------------------------

def test_nunca_clica_esquerdo_sem_ter_visto_o_botao():
    """Sem loot no chão, NENHUM clique esquerdo pode acontecer.

    É o único clique que move o personagem. Um "clica no Pick Up por garantia"
    mandaria o personagem andar a segundos da saída da cave.
    """
    cliente = ClienteFalso(ponto_que_abre=None)
    resultado = _catar(cliente)

    assert cliente.esquerdos == [], (
        f"clicou com o botão esquerdo {len(cliente.esquerdos)}x sem o botão na "
        "tela -- é assim que o personagem sai andando"
    )
    assert resultado.pegou is False


def test_clica_exatamente_ONDE_o_botao_foi_visto():
    """Coordenada fixa envelhece; a posição vista não. E clicar onde o botão
    ESTÁ é o que torna o clique seguro por construção."""
    outro_lugar = (123, 456)
    primeiro = (LOOT[0] + catador.RAIOS_DO_ANEL[0], LOOT[1])
    cliente = ClienteFalso(ponto_que_abre=primeiro,
                           onde_o_botao_aparece=outro_lugar)
    _catar(cliente)

    assert cliente.esquerdos == [outro_lugar], (
        f"clicou em {cliente.esquerdos}, mas o botão estava em {outro_lugar}"
    )


def test_o_anel_inteiro_e_gasto_antes_de_desistir():
    cliente = ClienteFalso(ponto_que_abre=None)
    _catar(cliente)

    assert len(cliente.direitos) == 4 * len(catador.RAIOS_DO_ANEL)


# ---------------------------------------------------------------------------
# 2. Clica ATÉ SUMIR -- o critério do usuário
# ---------------------------------------------------------------------------

def test_clica_ate_o_botao_sumir():
    """"Até ele sumir deve ficar clicando nele" -- palavras do usuário.

    Parar antes deixa item no chão sem sintoma nenhum.
    """
    primeiro = (LOOT[0] + catador.RAIOS_DO_ANEL[0], LOOT[1])
    cliente = ClienteFalso(ponto_que_abre=primeiro, cliques_para_sumir=4)
    resultado = _catar(cliente)

    assert resultado.pegou is True
    assert len(cliente.esquerdos) == 4, (
        f"parou em {len(cliente.esquerdos)} cliques com o botão ainda na tela"
    )
    assert cliente.visivel is False


def test_um_clique_costuma_bastar():
    primeiro = (LOOT[0] + catador.RAIOS_DO_ANEL[0], LOOT[1])
    cliente = ClienteFalso(ponto_que_abre=primeiro, cliques_para_sumir=1)
    resultado = _catar(cliente)

    assert resultado.cliques_no_botao == 1
    assert cliente.esquerdos == [BOTAO]


def test_desiste_no_teto_se_o_botao_nao_sumir():
    """Rede de segurança: janela travada não pode prender a run com o boss já
    morto e a instância gasta."""
    primeiro = (LOOT[0] + catador.RAIOS_DO_ANEL[0], LOOT[1])
    cliente = ClienteFalso(ponto_que_abre=primeiro, cliques_para_sumir=999)
    resultado = _catar(cliente)

    assert resultado.pegou is False
    assert len(cliente.esquerdos) == catador.TETO_DE_CLIQUES


def test_o_pior_caso_e_LIMITADO():
    """A propriedade é haver TETO, não o valor exato dele.

    A primeira versão deste teste cravava `<= 25 s`, que era a aritmética do
    momento (10 x 2 s). O usuário ajustou a espera para 4 s e o teste reprovou
    sem nada estar errado -- ele media a MINHA suposição, não uma propriedade do
    sistema. Número que o usuário ajusta não vira asserção de igualdade.

    O que precisa continuar verdadeiro: o pior caso existe e cabe numa run que
    já acabou. Ele só é alcançado com uma janela travada, boss morto e instância
    gasta -- no caminho normal o laço sai no primeiro ou segundo clique.
    """
    pior_caso = catador.TETO_DE_CLIQUES * catador.ESPERA_APOS_PEGAR
    assert 0 < pior_caso <= 60.0, (
        f"pior caso de {pior_caso}s. Espera e teto se MULTIPLICAM: subindo um, "
        "o outro desce, senão a rede custa mais que o problema que evita."
    )


def test_a_espera_da_tempo_de_o_jogo_recolher():
    """PISO, não valor exato -- a espera é ajustável pelo usuário.

    Ele pediu "uns 2 segundos" e ajustou para 4; quanto o jogo leva depende de
    quantos itens caíram. O que não pode é encolher para menos que o pedido:
    conferir antes de o jogo recolher gasta os cliques do teto contra um
    recolhimento em andamento, e o loot fica no chão.
    """
    assert catador.ESPERA_APOS_PEGAR >= 2.0


# ---------------------------------------------------------------------------
# 3. Sai no primeiro sucesso -- o ganho sobre o T-R0XX
# ---------------------------------------------------------------------------

def test_para_no_clique_que_fez_o_botao_aparecer():
    """O T-R0XX gasta os oito cliques sempre. Aqui o laço sai no primeiro."""
    primeiro = (LOOT[0] + catador.RAIOS_DO_ANEL[0], LOOT[1])
    cliente = ClienteFalso(ponto_que_abre=primeiro)
    resultado = _catar(cliente)

    assert len(cliente.direitos) == 1, (
        f"gastou {len(cliente.direitos)} cliques depois de já ter achado"
    )
    assert resultado.cliques_ate_achar == 1


def test_o_raio_menor_vem_primeiro():
    """O cadáver cai perto do centro; começar de longe gastaria cliques à toa."""
    pontos = catador._pontos_do_anel(LOOT)
    distancias = [max(abs(x - LOOT[0]), abs(y - LOOT[1])) for x, y in pontos]

    assert distancias == sorted(distancias), f"anel fora de ordem: {distancias}"
    assert distancias[0] == min(catador.RAIOS_DO_ANEL)


def test_botao_ja_na_tela_pula_o_anel_inteiro():
    """Pode estar lá pelo auto-pick de um companheiro. Procurar antes custa uma
    captura e economiza oito cliques."""
    cliente = ClienteFalso(ja_visivel=True)
    resultado = _catar(cliente)

    assert cliente.direitos == []
    assert resultado.pegou is True
    assert resultado.cliques_ate_achar == 0


# ---------------------------------------------------------------------------
# 4. O resultado conta a história
# ---------------------------------------------------------------------------

def test_o_resultado_diz_o_que_aconteceu():
    assert "nada recolhido" in str(_catar(ClienteFalso(ponto_que_abre=None)))

    primeiro = (LOOT[0] + catador.RAIOS_DO_ANEL[0], LOOT[1])
    ok = ClienteFalso(ponto_que_abre=primeiro)
    assert "loot recolhido" in str(_catar(ok))


def test_nao_levanta_nunca():
    """COMPLEMENTO: falhar em catar custa itens; levantar custaria a run."""
    assert _catar(ClienteFalso(ponto_que_abre=None)) is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
