"""O laço de combate da HH: bater e trocar de alvo até `in_battle` cair.

=========================================================================
A REGRA, E O QUE ELA SUBSTITUIU
=========================================================================

Regra do usuário, 06/09/2026: *"o bot deve atacar e alternar alvos (TAB)
ininterruptamente até que o estado global confirme a saída da batalha
(`in_battle == False`)"*, e *"somente após sair oficialmente de batalha, o bot
deve invocar a montaria e retomar a navegação"*.

Os pontos de pacote da HH usavam `combate.limpar_o_combate`, cuja coreografia
é: mata um, **PARA três segundos sem bater** olhando a flag, e só então TAB.
Esses três segundos (`ESPERA_APOS_A_MORTE_ANTES_DO_TAB`) existem por medição --
**do BC**, onde o TAB imediato depois da morte puxa o mob seguinte e troca um
travamento por outro.

Na HH os mobs do ponto PRECISAM morrer: puxar o seguinte é o objetivo.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

Que a otimização da HH não volte a atravessar a fronteira. `limpar_o_combate`
não foi tocada e continua sendo o remédio do portão da montaria nas duas caves
-- ver `docs/INVARIANTES.md`, "Decisão de cave NÃO mora em código
compartilhado".
"""
from __future__ import annotations

import inspect

from blazesbot.bot import combate as motor
from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.routine import HHRoutine


def _fonte(metodo) -> str:
    return inspect.getsource(metodo)


# ===========================================================================
# Sem pausa entre a morte e o TAB
# ===========================================================================


def _chamadas(metodo) -> list[str]:
    """Os nomes CHAMADOS no corpo -- pelo AST, nunca por busca de texto.

    A docstring de `_matar_ate_sair_de_batalha` explica o que ela substituiu, e
    cita `limpar_o_combate` pelo nome. Uma busca no texto acharia a explicação
    e concluiria que a chamada continua lá.
    """
    import ast
    import textwrap

    arvore = ast.parse(textwrap.dedent(_fonte(metodo)))
    return [getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in ast.walk(arvore) if isinstance(n, ast.Call)]


def test_o_core_loop_usa_o_laco_de_ataque_e_nao_a_coreografia_com_pausa():
    chamadas = _chamadas(HHRoutine._matar_ate_sair_de_batalha)
    assert "atacar_ate_sair_de_combate" in chamadas
    assert "limpar_o_combate" not in chamadas


def test_o_TAB_por_morte_esta_LIGADO_no_core_loop():
    """`tabs_ao_morrer > 0` é o que liga o ramo "morreu -> troca de alvo"
    dentro do laço de ataque. Zero ali desligaria a troca."""
    assert "tabs_ao_morrer=mapa_hh.TABS_NO_PACOTE" in _fonte(
        HHRoutine._matar_ate_sair_de_batalha)
    assert mapa_hh.TABS_NO_PACOTE > 0


def test_o_golpe_NAO_para_durante_a_confirmacao_de_saida():
    """"Ininterrupto até `in_battle == False`" inclui a confirmação."""
    assert "atacar_na_confirmacao=True" in _fonte(
        HHRoutine._matar_ate_sair_de_batalha)


def test_os_pontos_de_PACOTE_pedem_TAB_por_morte():
    for rotulo in (mapa_hh.BOSS_1, mapa_hh.BOSS_3):
        assert mapa_hh.e_pacote_de_mobs(rotulo)
        assert mapa_hh.tabs_ao_morrer(rotulo) == mapa_hh.TABS_NO_PACOTE > 0


def test_nenhuma_luta_da_HH_chama_mais_a_coreografia_com_pausa():
    """O único uso legítimo que sobra é o PORTÃO DA MONTARIA, que é do motor."""
    import ast

    from blazesbot.bot.hh import routine as mod

    arvore = ast.parse(inspect.getsource(mod))
    # CHAMADAS, e não menções: `limpar_o_combate` aparece em docstring e em
    # comentário explicando por que saiu.
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "limpar_o_combate"]
    assert not chamadas, (
        f"a HH voltou a CHAMAR a coreografia com pausa "
        f"(linhas {[n.lineno for n in chamadas]})")

    # E o único uso que sobra é a LIGAÇÃO do portão da montaria -- uma
    # atribuição, não uma chamada.
    ligacoes = [n.lineno for n in ast.walk(arvore)
                if isinstance(n, ast.Attribute)
                and n.attr == "limpar_o_combate"]
    assert len(ligacoes) == 1, (
        f"esperava só a ligação do portão da montaria; achei {ligacoes}")


# ===========================================================================
# O BC não muda
# ===========================================================================


def test_a_coreografia_com_pausa_continua_INTACTA_no_motor():
    """Ela é a medição do BC, e o BC continua dependendo dela."""
    assert motor.ESPERA_APOS_A_MORTE_ANTES_DO_TAB == 3.0
    assert "_esperar_a_flag_baixar" in _fonte(motor.CombatEngine.limpar_o_combate)


def test_o_portao_da_montaria_das_DUAS_caves_continua_nela():
    from blazesbot.bot.bc.routine import BossRushRoutine

    for cls in (BossRushRoutine, HHRoutine):
        assert "self.nav.destravar_o_combate = self.combat.limpar_o_combate" in \
            inspect.getsource(cls.__init__)


# ===========================================================================
# A montaria volta no instante da saída
# ===========================================================================


def test_sair_do_combate_MONTA_antes_de_qualquer_outra_coisa():
    """Antes a montaria só subia no começo do trecho seguinte -- ou seja,
    depois do loot e da contabilidade, tudo a pé."""
    fonte = _fonte(HHRoutine._lutar_no_ponto)
    assert fonte.count("_montar_ao_sair_do_combate") == 2, (
        "os dois caminhos de vitória (pacote e boss) têm que montar")
    assert "garantir_montaria_para_andar" in _fonte(
        HHRoutine._montar_ao_sair_do_combate)


def test_montar_so_acontece_quando_a_luta_foi_VENCIDA():
    """Derrota vai para `_falhar`; montar ali seria montar em batalha."""
    fonte = _fonte(HHRoutine._lutar_no_ponto)
    for bloco in fonte.split("_falhar")[1:]:
        primeira = bloco.split("\n")[0]
        assert "_montar_ao_sair_do_combate" not in primeira


def test_o_core_loop_DESMONTA_antes_de_bater():
    """Montado o jogo IGNORA a tecla de skill e não devolve erro."""
    assert "ensure_dismounted" in _fonte(HHRoutine._matar_ate_sair_de_batalha)
