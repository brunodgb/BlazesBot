"""O ANEL DE TENTATIVA do clique direito, e o que ele não pode violar.

=============================================================================
O QUE ESTE ARQUIVO TRAVA
=============================================================================

O anel existe porque o clique de NPC é posicional e o personagem para dentro de
uma FOLGA (1,5 unidades de mundo), não no ponto exato -- e dentro dela o NPC
passeia dezenas de pixels na tela. Relato do usuário, 09/09/2026: a saída da HH
*"às vezes falha, acredito que por uma pequena diferença de posicionamento"*.

As três propriedades inegociáveis:

  1. **A mira medida é sempre a primeira.** No caminho feliz, nada muda -- nem
     custo, nem comportamento.
  2. **Acertou, para.** Um anel que continuasse clicando depois do diálogo
     aberto clicaria DENTRO do diálogo, e ali cada ponto é um botão.
  3. **Andou, para.** Clique que erra cai no chão e faz o personagem ANDAR. Daí
     em diante todo vizinho vale para um enquadramento que não existe mais, e
     insistir empurra o personagem para longe do NPC.
"""
from __future__ import annotations

import inspect
import textwrap
from types import SimpleNamespace

from blazesbot.bot.hh.entrada import EntradaDaHH
from blazesbot.bot.ui_do_jogo import UIDoJogo
from blazesbot.core import halo

MIRA = (626, 526)


# ===========================================================================
# A geometria
# ===========================================================================

def test_a_mira_medida_e_sempre_a_primeira():
    assert halo.pontos_em_volta(MIRA)[0] == MIRA


def test_os_lados_vem_antes_das_quinas():
    """As quinas estão √2 vezes mais longe: tentar antes é tentar pior."""
    pontos = halo.pontos_em_volta(MIRA, passo=10)
    lados = pontos[1:5]
    quinas = pontos[5:9]
    assert all(MIRA[0] == x or MIRA[1] == y for x, y in lados)
    assert all(MIRA[0] != x and MIRA[1] != y for x, y in quinas)


def test_a_volta_inteira_cabe_na_janela_do_passo():
    """Uma volta varre 2*passo por 2*passo em torno da mira, e nada além."""
    passo = halo.PASSO_DO_HALO
    for x, y in halo.pontos_em_volta(MIRA):
        assert abs(x - MIRA[0]) <= passo and abs(y - MIRA[1]) <= passo


def test_o_passo_e_curto_de_proposito():
    """Anel grande deixa de ser correção de mira e vira clique às cegas -- que é
    exatamente o que o bot em Lua faz e este projeto recusa."""
    assert 0 < halo.PASSO_DO_HALO <= 25


def test_passo_zero_DESLIGA_o_anel_sem_caminho_especial():
    assert halo.pontos_em_volta(MIRA, passo=0) == [MIRA]


def test_nenhum_ponto_se_repete():
    pontos = halo.pontos_em_volta(MIRA, voltas=2)
    assert len(pontos) == len(set(pontos))


# ===========================================================================
# O uso: a saída da HH
# ===========================================================================

def _ui(monkeypatch, *, dialogo_em, posicoes):
    """Um `UIDoJogo` com o mundo dublado: só o ponto `dialogo_em` abre diálogo."""
    cliques: list[tuple[int, int]] = []
    estado = {"posicoes": list(posicoes)}

    ui = UIDoJogo.__new__(UIDoJogo)

    def position():
        return (estado["posicoes"].pop(0) if len(estado["posicoes"]) > 1
                else estado["posicoes"][0])

    ui.ctx = SimpleNamespace(
        log=SimpleNamespace(info=lambda *a, **k: None,
                            debug=lambda *a, **k: None,
                            warning=lambda *a, **k: None),
        memory=SimpleNamespace(position=position),
        raise_if_stopped=lambda: None,
        tick=lambda _s: None,
        right_click=cliques.append,
    )
    ui.nav = SimpleNamespace(
        garantir_montaria_para_andar=lambda _o: True)
    monkeypatch.setattr(ui, "_pontos", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ui, "_ponto_padrao_do_npc",
                        lambda **k: (482, 353), raising=False)
    monkeypatch.setattr(
        ui, "_esperar_o_dialogo",
        lambda _limite: cliques[-1] == dialogo_em, raising=False)
    return ui, cliques


def test_o_anel_para_no_ponto_que_ABRIU_o_dialogo(monkeypatch):
    """Continuar clicando depois do diálogo aberto seria clicar em botão dele."""
    vizinho = halo.pontos_em_volta(MIRA)[2]
    ui, cliques = _ui(monkeypatch, dialogo_em=vizinho, posicoes=[(55, 33)])

    assert ui.falar_com_npc(MIRA, halo_px=halo.PASSO_DO_HALO) == vizinho
    assert cliques == halo.pontos_em_volta(MIRA)[:3], cliques


def test_sem_halo_o_comportamento_e_o_DE_ANTES(monkeypatch):
    """Quem não pede anel continua com a mira e o ponto genérico, e mais nada."""
    ui, cliques = _ui(monkeypatch, dialogo_em=None, posicoes=[(55, 33)])

    assert ui.falar_com_npc(MIRA) is None
    assert set(cliques) == {MIRA, (482, 353)}


def test_o_anel_PARA_quando_o_personagem_ANDA(monkeypatch):
    """A propriedade que protege o resto da rotina: clique no chão move o
    personagem, e o vizinho seguinte já não vale."""
    # A primeira leitura é a de PARTIDA; da segunda em diante o personagem já
    # está em outro lugar -- é o clique da mira tendo caído no chão.
    ui, cliques = _ui(monkeypatch, dialogo_em=None,
                      posicoes=[(55, 33), (57, 35)])

    assert ui.falar_com_npc(MIRA, halo_px=halo.PASSO_DO_HALO) is None
    assert len(cliques) == 1, (
        f"clicou {len(cliques)} vezes depois de o personagem andar: {cliques}")


def test_a_SAIDA_da_HH_usa_o_anel():
    fonte = textwrap.dedent(inspect.getsource(EntradaDaHH.tentar_sair_da_hh))
    assert "halo_px=" in fonte, "a saída deixou de pedir o anel de tentativa"
    assert "hh_exit_npc" in fonte


def test_a_ENTRADA_da_HH_nao_usa_o_anel():
    """A rajada é centenas de tentativas por minuto: o anel ali multiplicaria o
    trabalho de um caminho que já funciona."""
    for metodo in (EntradaDaHH._entrar_descobrindo, EntradaDaHH._entrar_rapido):
        assert "halo_px" not in textwrap.dedent(inspect.getsource(metodo))
