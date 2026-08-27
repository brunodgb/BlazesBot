"""A Break Soul só entra na rotação na SEGUNDA FASE do boss.

=============================================================================
O QUE MUDOU, E POR QUE
=============================================================================

Antes bastava a tecla existir: `_rotacao_de_ataque` acrescentava a Break Soul à
rotação SEMPRE. Ou seja, ela saía contra os quatro Gun Witch, contra qualquer
mob do caminho e contra a primeira fase do boss -- e chegava em recarga
justamente na segunda fase, que é a luta que decide a run.

É o mesmo raciocínio que já tirou o AoE da luta dos guardas, e que está escrito
no próprio `_rotacao_de_ataque`: *"mana é exatamente o que falta na segunda fase
do boss, logo depois"*.

=============================================================================
O TESTE QUE CARREGA O PESO É O DO VAZAMENTO
=============================================================================

`_na_segunda_fase_do_boss` é uma bandeira de instância, e o `CombatEngine` VIVE
ENTRE AS RUNS. Uma bandeira que sobrevive ao fim da luta faria a Break Soul sair
contra os guardas da run SEGUINTE -- o defeito que esta mudança existe para
corrigir, com o agravante de ser intermitente: some ao reiniciar o bot e só
aparece a partir da segunda run.

Por isso `fight_boss` é uma casca com `finally`, e por isso
`test_a_bandeira_nao_vaza_*` existem em três sabores: vitória, derrota e
EXCEÇÃO. A exceção é a saída que ninguém lembra de zerar na mão.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot.bc import combat
from blazesbot.bot.bc.combat import CombatEngine

BREAK_SOUL = "R"
ATAQUE_1 = "1"
AOE = "2"


def _motor(break_soul=BREAK_SOUL, aoe=AOE, use_aoe=True, mp_pct=100.0):
    motor = CombatEngine.__new__(CombatEngine)
    motor._skill_index = 0
    motor._na_segunda_fase_do_boss = False
    motor.ctx = SimpleNamespace(
        settings=SimpleNamespace(
            keys=SimpleNamespace(attack_skills=[ATAQUE_1], aoe_skill=aoe,
                                 break_soul=break_soul),
            use_aoe=use_aoe,
            bc=SimpleNamespace(aoe_until_mana_pct=30),
        ),
        log=SimpleNamespace(info=lambda *a, **k: None,
                            debug=lambda *a, **k: None,
                            warning=lambda *a, **k: None),
    )
    motor._mp_pct = mp_pct
    return motor


def _estado(mp_pct=100.0):
    return SimpleNamespace(mp_pct=mp_pct, hp_pct=100.0, max_hp=1000)


# ---------------------------------------------------------------------------
# 1. A regra
# ---------------------------------------------------------------------------

def test_fora_da_fase_2_a_break_soul_nao_entra():
    """O dente. Contra guardas, lixo e a primeira fase do boss ela fica fora."""
    motor = _motor()
    rotacao = motor._rotacao_de_ataque(_estado(), usar_aoe=True)

    assert BREAK_SOUL not in rotacao, (
        f"Break Soul saiu fora da fase 2 (rotação {rotacao}) -- ela chega em "
        "recarga na luta que decide a run"
    )


def test_na_fase_2_a_break_soul_entra():
    motor = _motor()
    motor._na_segunda_fase_do_boss = True
    rotacao = motor._rotacao_de_ataque(_estado(), usar_aoe=True)

    assert BREAK_SOUL in rotacao, f"Break Soul não entrou na fase 2: {rotacao}"


def test_ela_ACRESCENTA_a_rotacao_e_nao_substitui_ninguem():
    """Mesmo desenho do AoE: entra junto, não rouba a vez de outra skill."""
    motor = _motor()
    antes = motor._rotacao_de_ataque(_estado(), usar_aoe=True)
    motor._na_segunda_fase_do_boss = True
    depois = motor._rotacao_de_ataque(_estado(), usar_aoe=True)

    assert depois == [*antes, BREAK_SOUL]


def test_sem_tecla_configurada_nada_acontece_na_fase_2():
    motor = _motor(break_soul="")
    motor._na_segunda_fase_do_boss = True
    rotacao = motor._rotacao_de_ataque(_estado(), usar_aoe=True)

    assert rotacao == [ATAQUE_1, AOE]


def test_o_interruptor_devolve_o_comportamento_antigo(monkeypatch):
    """Reverter é trocar uma palavra, não ligar código não testado."""
    monkeypatch.setattr(combat, "USAR_BREAK_SOUL_SO_NA_FASE_2", False)

    motor = _motor()
    assert BREAK_SOUL in motor._rotacao_de_ataque(_estado(), usar_aoe=True), (
        "com o interruptor desligado ela tem que voltar a sair sempre"
    )


# ---------------------------------------------------------------------------
# 2. Quando a bandeira sobe
# ---------------------------------------------------------------------------

def test_a_bandeira_nao_sobe_na_fase_1():
    motor = _motor()
    motor._marcar_fase(1)
    assert motor._na_segunda_fase_do_boss is False


def test_a_bandeira_sobe_na_fase_2():
    motor = _motor()
    motor._marcar_fase(2)
    assert motor._na_segunda_fase_do_boss is True


def test_marcar_a_fase_duas_vezes_nao_repete_o_log():
    """As duas formas de detecção podem disparar na mesma virada; o log não pode
    sair duas vezes dizendo a mesma coisa."""
    linhas: list[str] = []
    motor = _motor()
    motor.ctx.log.info = lambda *a, **k: linhas.append(a[0] if a else "")

    motor._marcar_fase(2)
    motor._marcar_fase(2)
    motor._marcar_fase(3)

    assert len(linhas) == 1, f"log repetido: {linhas}"


# ---------------------------------------------------------------------------
# 3. A bandeira NÃO PODE VAZAR entre runs -- é o teste que carrega o peso
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 4. O CAMINHO QUE RODA DE VERDADE
# ---------------------------------------------------------------------------
#
# A primeira versão levantou a bandeira nos dois contadores `fases_vistas` de
# `fight_boss` -- e a Break Soul nunca saiu em produção, porque **`fight_boss`
# está desativado**: a chamada dele em `routine.py` é comentário, e quem luta é
# `fase_do_boss_por_combate`, que chega em `_registrar_troca_de_fase`.
#
# O usuário apontou o log exato: *"PRIMEIRA FASE MORTA: ... trocou de struct"*.
# É nessa linha que a bandeira sobe agora, e é isto que estes testes travam --
# não o contador de um caminho morto.


class _VigiaFalso:
    """Só o que `_registrar_troca_de_fase` consulta: o ID do alvo.

    A VIRADA DE FASE PASSOU A SER VISTA PELO ID em 25/08/2026. Palavras do
    usuário: *"o ponteiro 0x00D5CB80 sempre muda o valor dele quando mudar de
    target; se no waypoint do boss mudar o valor do ponteiro, é porque o boss
    entrou na segunda fase"*. E bate com o que já estava medido: a primeira fase
    some por volta de 7%, a struct é liberada e nasce OUTRO Blaze Skull Marshal
    -- alvo novo é id novo.

    O dublê não tem nome nem HP de propósito: se a produção voltar a pedir
    qualquer um dos dois, o teste quebra em vez de passar medindo outro mundo.
    """

    def __init__(self, alvo_id):
        self._id = alvo_id

    def id_do_alvo(self, _pid):
        return self._id

    def trocar_para(self, novo):
        self._id = novo


def _motor_de_boss(alvo_id=4823):
    motor = _motor()
    motor._struct_do_alvo = None
    motor._target_hybrid = _VigiaFalso(alvo_id)
    motor.ctx.pid = 1
    motor.linhas: list[str] = []
    motor.ctx.log.info = lambda *a, **k: motor.linhas.append(
        (a[0] if a else "") % a[1:] if len(a) > 1 else (a[0] if a else ""))
    return motor


def test_sem_alvo_a_bandeira_nao_sobe():
    """`id == 0` é "não há alvo", não "alvo novo"."""
    motor = _motor_de_boss(alvo_id=0)
    motor._registrar_troca_de_fase("Blaze Skull Marshal")
    motor._registrar_troca_de_fase("Blaze Skull Marshal")
    assert motor._na_segunda_fase_do_boss is False


def test_id_ilegivel_nao_levanta_a_bandeira():
    """Não conseguir ler é "não sei" -- e "não sei" não vira virada de fase."""
    motor = _motor_de_boss(alvo_id=None)
    motor._registrar_troca_de_fase("Blaze Skull Marshal")
    assert motor._na_segunda_fase_do_boss is False


def test_o_mesmo_alvo_lido_varias_vezes_nao_levanta():
    motor = _motor_de_boss()
    for _ in range(5):
        motor._registrar_troca_de_fase("Blaze Skull Marshal")
    assert motor._na_segunda_fase_do_boss is False


def test_a_troca_de_struct_do_boss_levanta_a_bandeira():
    """O caminho VIVO: é este log que o usuário vê, e é aqui que ela sobe."""
    motor = _motor_de_boss()

    motor._registrar_troca_de_fase("Blaze Skull Marshal")   # 1ª leitura
    assert motor._na_segunda_fase_do_boss is False, (
        "a primeira leitura não é troca de fase -- é só a struct inicial"
    )

    motor._target_hybrid.trocar_para(4901)
    motor._registrar_troca_de_fase("Blaze Skull Marshal")

    assert motor._na_segunda_fase_do_boss is True, (
        "a troca de struct do boss não levantou a bandeira -- a Break Soul "
        "nunca vai sair, que foi o defeito relatado"
    )
    assert any("PRIMEIRA FASE MORTA" in linha for linha in motor.linhas)


def test_depois_da_troca_a_break_soul_entra_na_rotacao():
    """O caminho inteiro, ponta a ponta: log de troca -> skill na rotação."""
    motor = _motor_de_boss()
    motor._registrar_troca_de_fase("Blaze Skull Marshal")
    motor._target_hybrid.trocar_para(4901)
    motor._registrar_troca_de_fase("Blaze Skull Marshal")

    rotacao = motor._rotacao_de_ataque(_estado(), usar_aoe=True)
    assert BREAK_SOUL in rotacao, f"rotação sem a Break Soul na fase 2: {rotacao}"


def test_a_bandeira_desce_no_comeco_de_TODA_luta():
    """Zerar só no `fight_boss` não bastava -- ele está desativado, então a
    bandeira de uma run sobreviveria para a luta dos guardas da próxima."""
    import ast
    import inspect

    from blazesbot.bot.bc.combat import CombatEngine

    fonte = inspect.getsource(CombatEngine.atacar_ate_sair_de_combate)
    zera = [
        no for no in ast.walk(ast.parse(fonte.lstrip()))
        if isinstance(no, ast.Assign)
        and any(isinstance(a, ast.Attribute)
                and a.attr == "_na_segunda_fase_do_boss" for a in no.targets)
    ]
    assert zera, (
        "`atacar_ate_sair_de_combate` não baixa a bandeira da fase 2 -- ela "
        "vazaria de uma luta para a seguinte"
    )

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
