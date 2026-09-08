"""Todo ponto de luta da HH desmonta DE VERDADE.

=========================================================================
O DEFEITO, RELATADO EM 07/09/2026
=========================================================================

Regra do usuário: *"é importante sempre que for luta contra boss estar fora da
montaria"*. Ele viu o personagem **montado** em alguns pontos de boss.

`Navigator.ensure_dismounted` RECUSA descer enquanto a flag de combate estiver
alta -- "Em combate: ignorando o pedido para desmontar" --, e a recusa está
certa em quase todo lugar: desmontar sob ataque é ficar lento no meio do trem
de mobs. A exceção são os PONTOS DE LUTA, onde descer é o objetivo, porque
**montado o jogo IGNORA a tecla de skill e não devolve erro**.

O `_matar_ate_sair_de_batalha` (o Core Loop da HH, de 06/09) chamava a versão
SEM a exceção. E chegar no ponto já em combate é o NORMAL na HH: os mobs ranged
atiram durante o trajeto.

Resultado: nos pontos de PACOTE -- bosses 1 e 3 -- o personagem lutava montado,
com dano ZERO. Os bosses 2 e 4 passavam porque `lutar_contra_um_boss` usa
`_descer_para_lutar`, que já passa a exceção. É exatamente o "em alguns desses
waypoints" do relato.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot import combate as motor
from blazesbot.bot import navegacao as nav
from blazesbot.bot.hh.routine import HHRoutine


def _chamadas_com_argumentos(metodo):
    """Cada chamada do corpo como (nome, {argumentos nomeados})."""
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    saida = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        nome = getattr(no.func, "attr", getattr(no.func, "id", ""))
        nomeados = {k.arg: ast.unparse(k.value) for k in no.keywords if k.arg}
        saida.append((nome, nomeados))
    return saida


# ===========================================================================
# A recusa existe, e é certa
# ===========================================================================


def test_desmontar_em_batalha_e_RECUSADO_por_padrao():
    """O padrão protege quem não está num ponto de luta."""
    assert inspect.signature(
        nav.Navigator.ensure_dismounted
    ).parameters["permitir_em_batalha"].default is False


# ===========================================================================
# Os pontos de luta pedem a exceção
# ===========================================================================


def test_o_core_loop_da_HH_usa_o_MESMO_gesto_do_ritual_de_boss():
    """`_descer_para_lutar` também força a barra de atalhos na página 1.

    Num ponto de luta isso é a diferença entre bater e apertar tecla vazia --
    e duas cópias do gesto divergiriam, com a atrasada lutando com a página
    errada.
    """
    nomes = [n for n, _ in _chamadas_com_argumentos(
        HHRoutine._matar_ate_sair_de_batalha)]
    assert "_descer_para_lutar" in nomes
    assert "ensure_dismounted" not in nomes, (
        "voltou a usar a versão que RECUSA descer em batalha")


def test_o_ritual_de_boss_do_motor_permite_descer_em_batalha():
    """É de onde o Core Loop da HH herda o comportamento certo."""
    for nome, args in _chamadas_com_argumentos(motor.CombatEngine._descer_para_lutar):
        if nome == "ensure_dismounted":
            assert args.get("permitir_em_batalha") == "True"
            return
    raise AssertionError("`_descer_para_lutar` não desmonta mais")


def test_chegar_no_ponto_do_boss_desmonta_mesmo_em_batalha():
    """`_do_ate_o_boss` termina no ponto de luta -- e chegar em combate é o
    normal na HH."""
    for nome, args in _chamadas_com_argumentos(HHRoutine._do_ate_o_boss):
        if nome == "ensure_dismounted":
            assert args.get("permitir_em_batalha") == "True"
            return
    raise AssertionError("`_do_ate_o_boss` deixou de desmontar")


def test_os_QUATRO_pontos_terminam_a_pe():
    """Pacote e boss usam caminhos diferentes; os dois têm de desmontar.

    Bosses 1 e 3 vão pelo Core Loop; 2 e 4 pelo ritual do motor.
    """
    from blazesbot.bot.hh import mapa_hh

    pacotes = [r for r, _c, _p in mapa_hh.TRECHOS_DOS_BOSSES
               if mapa_hh.e_pacote_de_mobs(r)]
    bosses = [r for r, _c, _p in mapa_hh.TRECHOS_DOS_BOSSES
              if not mapa_hh.e_pacote_de_mobs(r)]
    assert pacotes and bosses, "a divisão pacote/boss desapareceu"

    caminho_do_pacote = [n for n, _ in _chamadas_com_argumentos(
        HHRoutine._matar_ate_sair_de_batalha)]
    caminho_do_boss = [n for n, _ in _chamadas_com_argumentos(
        motor.CombatEngine.lutar_contra_um_boss)]
    assert "_descer_para_lutar" in caminho_do_pacote
    assert "_descer_para_lutar" in caminho_do_boss
