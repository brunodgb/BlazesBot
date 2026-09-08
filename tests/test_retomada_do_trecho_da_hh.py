"""O trecho da HH recomeça pelo waypoint mais próximo, não pelo primeiro.

=========================================================================
O DEFEITO MEDIDO
=========================================================================

Log de 08/09/2026, 08:13:57. A luta do Fa-Yuan terminou em (325,152), longe do
ponto do boss (272,136). `PontoDoBoss` mandou a run de volta para `ATE_O_BOSS`,
e a rotina reentrou no trecho 1/4 clicando o waypoint **1/22 -- (80,42), a 214
unidades**:

    sem progresso indo para (80, 42) (waypoint 1/22, distância 214)
    Navegação travada em (278, 124)

O clique de minimapa vai em LINHA RETA. A reta de (325,152) até (80,42) atravessa
a divisa das salas da mansão, e o personagem parou em (278,124) -- do outro lado
da parede, a 13 unidades do destino e sem caminho até ele. O jogo respondeu
`Failed to auto-path` a cada tentativa até o destravamento recuar pelos vizinhos.

Relato do usuário no mesmo dia: *"o personagem esta indo para uma direção
errada... tem uma parede que divide em salas diferentes... depois de um tempo ele
ate percebe isso e volta para a rota correta, porem nao deveria ir ali"*.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

`mapa_hh.onde_retomar` JÁ EXISTIA e nunca tinha sido ligada -- suíte verde não
prova que a peça está LIGADA. Este teste é a ligação, não a peça.

Ver `docs/decisoes/hh.md` §16.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.routine import HHRoutine

# A posição medida no log: onde a luta do primeiro boss terminou.
FIM_DA_LUTA_DO_FA_YUAN = (325, 152)


def test_a_posicao_MEDIDA_nao_retoma_pelo_primeiro_waypoint():
    caminho = mapa_hh.CAMINHO_ATE_O_BOSS_1
    onde = mapa_hh.onde_retomar(FIM_DA_LUTA_DO_FA_YUAN, caminho)

    assert onde.indice > 0, (
        f"De {FIM_DA_LUTA_DO_FA_YUAN} a rota retomou pelo waypoint 1 "
        f"({caminho[0].pos}), a {onde.distancia:.0f} unidades. É o defeito "
        f"medido: o clique atravessa as paredes da mansão.")
    assert onde.distancia < mapa_hh.rota.RAIO_DA_AREA, (
        f"O waypoint escolhido está a {onde.distancia:.0f} unidades -- longe "
        f"demais para ser 'onde eu estou na rota'.")


def test_de_onde_a_luta_acaba_o_waypoint_escolhido_e_do_FIM_do_trecho():
    caminho = mapa_hh.CAMINHO_ATE_O_BOSS_1
    onde = mapa_hh.onde_retomar(FIM_DA_LUTA_DO_FA_YUAN, caminho)

    assert onde.indice >= len(caminho) - 6, (
        f"A luta do boss acontece no FIM do trecho, então retomar dali tem "
        f"que cair nos últimos waypoints -- caiu no {onde.indice + 1} de "
        f"{len(caminho)}.")


def test_o_trecho_da_HH_passa_comecar_em():
    fonte = inspect.getsource(HHRoutine._do_ate_o_boss)

    assert "onde_retomar" in fonte, (
        "Sem `onde_retomar` o trecho sempre recomeça no waypoint 1, e a run "
        "que volta para cá está no fim dele.")
    assert "comecar_em=onde.indice" in fonte, (
        "`comecar_em` e NÃO fatia: a rota inteira preserva o waypoint "
        "anterior, que é candidato do destravamento "
        "(`Navigator.seguir_rota`).")


def test_o_indice_e_calculado_ANTES_de_seguir_a_rota():
    """Ordem, pelo AST: calcular depois de andar não teria efeito."""
    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(HHRoutine._do_ate_o_boss)))
    chamadas = [(n.lineno, getattr(n.func, "attr", getattr(n.func, "id", "")))
                for n in ast.walk(arvore) if isinstance(n, ast.Call)]
    ordem = [nome for _linha, nome in sorted(chamadas)]

    assert ordem.index("onde_retomar") < ordem.index("seguir_rota")


def test_a_rota_NAO_e_fatiada_no_trecho():
    fonte = inspect.getsource(HHRoutine._do_ate_o_boss)

    assert "caminho[onde.indice:]" not in fonte, (
        "A fatia leva embora o waypoint ANTERIOR, e foi por isso que o "
        "destravamento de (205,31) no BC não achou um candidato que estava a "
        "10 unidades. Ver `Navigator.seguir_rota`.")


def test_o_BC_continua_com_a_retomada_dele():
    """A HH ligou a sua; a do BC não foi tocada."""
    from blazesbot.bot.bc.routine import BossRushRoutine

    fonte = inspect.getsource(BossRushRoutine)
    assert "mapa_bc.onde_retomar" in fonte
