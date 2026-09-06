"""Ficar parado sem progresso tem prazo -- e, se for combate, tem remédio.

=========================================================================
O DEFEITO, MEDIDO EM 04/09/2026
=========================================================================

O usuário mandou o print do jogo com o chat repetindo

    Failed to auto-path [Happiness Hall Visitor Room(282,139)->...(282,139)]

e o personagem cercado de mobs. O log mostrou o resto: **4 minutos e 10
segundos**, ~180 voltas, o bot tentando alcançar o waypoint 22 em (271,137)
estando em (282,139), em combate.

DUAS COISAS FALTAVAM, e são as duas travadas aqui:

  1. A NAVEGAÇÃO NÃO SABIA DE COMBATE. O remédio existia -- o gancho
     `destravar_o_combate`, que mata mob a mob até a flag baixar --, mas só o
     PORTÃO DA MONTARIA o chamava. E o portão só entra quando se vai montar;
     ali o personagem já estava montado e andando.
  2. NÃO HAVIA PRAZO. Enquanto a navegação insistia, `_do_ate_o_boss` não
     devolvia o controle -- e sem isso o `_guard()` da rotina não roda, então o
     Parar e o watchdog ficam sem resposta. Só terminou porque o usuário
     desligou a HH na mão.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot import navegacao as nav


def _ramo_da_parada() -> str:
    """O corpo do `elif` que trata 'sem progresso' dentro de `follow_path`."""
    fonte = textwrap.dedent(inspect.getsource(nav.Navigator.follow_path))
    return fonte[fonte.index("SEM_PROGRESSO_SEGUNDOS"):]


def test_o_teto_de_ficar_preso_e_o_numero_do_usuario():
    """*"30 segundos sem fazer nada já é bastante tempo parado"* (04/09/2026)."""
    assert nav.TETO_PRESO_NO_MESMO_PONTO == 30.0


def test_sem_progresso_e_EM_BATALHA_o_bot_MATA():
    """Insistir no clique de minimapa contra um combate não anda um passo."""
    ramo = _ramo_da_parada()
    # O GANCHO É PRÓPRIO da parada de trajeto desde 06/09/2026 -- ver
    # `tests/test_montaria_do_bc_no_caminho.py`. Era o do portão da montaria, e
    # isso fez o BC desmontar no corredor do Altar Stone.
    assert "matar_quando_o_trajeto_trava" in ramo
    assert "in_battle() is True" in ramo, (
        "ilegível não pode autorizar sair batendo")


def test_matar_vem_ANTES_do_teto_e_ANTES_da_manobra():
    """Matar é progresso; o teto é para insistência inútil.

    Se o teto disparasse primeiro, o bot desistiria do trecho em vez de limpar
    os mobs -- e a regra do usuário é o contrário: *"arranjar uma forma de
    continuar a cave, mas sem pular a morte dos boss"*.
    """
    ramo = _ramo_da_parada()
    assert ramo.index("matar_quando_o_trajeto_trava") < ramo.index(
        "TETO_PRESO_NO_MESMO_PONTO")
    assert ramo.index("matar_quando_o_trajeto_trava") < ramo.index(
        "destravar_pelos_vizinhos")


def test_matar_ZERA_o_relogio_de_preso():
    """Matar mob é trabalho útil mesmo com o personagem parado no lugar."""
    ramo = _ramo_da_parada()
    depois_de_matar = ramo[ramo.index("matar_quando_o_trajeto_trava"):]
    corte = depois_de_matar.index("TETO_PRESO_NO_MESMO_PONTO")
    assert "preso_desde = 0.0" in depois_de_matar[:corte]


def test_o_teto_DEVOLVE_o_controle_em_vez_de_insistir():
    """Quem decide é a rotina: ela sabe refazer o trecho, matar ou falhar.

    E, ao contrário deste laço, ela passa pelo `_guard()` -- que é o que
    responde ao Parar e ao watchdog.
    """
    ramo = _ramo_da_parada()
    trecho = ramo[ramo.index("TETO_PRESO_NO_MESMO_PONTO"):]
    assert "return False" in trecho[:trecho.index("destravar_pelos_vizinhos")]


def test_o_relogio_de_preso_recomeca_quando_a_rota_ANDA():
    """Senão o teto de 30 s valeria para o trajeto inteiro, e não por ponto."""
    fonte = textwrap.dedent(inspect.getsource(nav.Navigator.follow_path))
    arvore = ast.parse(fonte)
    zeragens = [n.lineno for n in ast.walk(arvore)
                if isinstance(n, ast.Assign)
                and any(getattr(a, "id", "") == "preso_desde" for a in n.targets)
                and isinstance(n.value, ast.Constant) and n.value.value == 0.0]
    # a inicialização, o zerar depois de matar, e o zerar no avanço de índice
    assert len(zeragens) >= 3, (
        f"o relógio de 'preso' é zerado em {len(zeragens)} lugar(es); "
        "faltou o avanço da rota ou a limpeza de combate")
