"""F1 + TAB para abrir a luta, e F1 + TAB de novo quando o alvo não apanha.

=========================================================================
A REGRA
=========================================================================

Usuário, 08/09/2026: *"dentro de HH tem vezes que o personagem acaba se auto
selecionando ou seleciona o pet e quando isso acontece, ele nao seleciona
automaticamente outro mob automaticamente"*, e a solução que ele mesmo indicou:
*"pressionar F1 que é a tecla de auto seleçao e depois dar TAB, assim garante
que vai selecionar o mob mais perto"*. Depois, sobre o começo da luta:
*"apertar F1 e depois dar o primeiro TAB vai ser o mais eficiente para atacar
os mobs corretos"*.

=========================================================================
O QUE ESTE ARQUIVO PROTEGE
=========================================================================

1. O gesto é DOIS toques na ordem certa -- só o TAB é cíclico e pode voltar
   para o pet.
2. Conta sem a tecla de auto-seleção continua funcionando (TAB sozinho).
3. A ABERTURA de toda luta da HH é esse gesto, sem condição.
4. O detector de meio de luta é OPT-IN -- é assim que a BC não muda.

Ver `docs/decisoes/hh.md` §14.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

from blazesbot.bot import combate as motor
from blazesbot.bot.hh.routine import HHRoutine


def _chamadas(metodo) -> list[str]:
    """Os nomes CHAMADOS no corpo, na ORDEM das linhas -- pelo AST.

    `ast.walk` é em LARGURA, então a ordem de visita não é a ordem do arquivo:
    o `sorted` por `lineno` é o que faz este teste falar sobre ordem.
    """
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    nos = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)]
    return [getattr(n.func, "attr", getattr(n.func, "id", ""))
            for n in sorted(nos, key=lambda n: (n.lineno, n.col_offset))]


# ===========================================================================
# O gesto
# ===========================================================================


class _Teclas:
    def __init__(self, self_target: str = "f1"):
        self.self_target = self_target
        self.tab = "tab"


class _Log:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def debug(self, *a, **k): pass


class _Ctx:
    """O mínimo que `reancorar_o_alvo` toca. Registra o que foi apertado."""

    def __init__(self, self_target: str = "f1"):
        self.apertadas: list[str] = []
        self.log = _Log()

        class _S:
            keys = _Teclas(self_target)
        self.settings = _S()

    def press(self, tecla, *a, **k):
        self.apertadas.append(tecla)

    def tick(self, *a, **k): pass


def _motor_de_mentira(self_target: str = "f1"):
    """Um `Combat` com o `ctx` de mentira, sem passar pelo `__init__`."""
    combate = object.__new__(motor.CombatEngine)
    combate.ctx = _Ctx(self_target)
    return combate


def test_o_gesto_e_a_tecla_de_auto_selecao_e_DEPOIS_o_TAB():
    combate = _motor_de_mentira("f1")
    combate._trocar_de_alvo = lambda *a, **k: combate.ctx.press("tab")

    combate.reancorar_o_alvo("teste")

    assert combate.ctx.apertadas == ["f1", "tab"], (
        "A ordem é F1 e depois TAB. Só o TAB é cíclico: da mira presa no pet "
        "ele avança para 'o seguinte naquele ciclo', que pode ser o pet de "
        "novo -- que é exatamente o sintoma relatado.")


def test_sem_a_tecla_de_auto_selecao_o_TAB_sai_sozinho():
    for vazia in ("", "   ", None):
        combate = _motor_de_mentira(vazia)
        combate._trocar_de_alvo = lambda *a, **k: combate.ctx.press("tab")

        combate.reancorar_o_alvo("teste")

        assert combate.ctx.apertadas == ["tab"], (
            f"Com `self_target`={vazia!r} o bot tem que continuar tentando: um "
            f"TAB ainda pode acertar o mob. Pior, mas funcionando.")


# ===========================================================================
# A abertura de toda luta da HH
# ===========================================================================


def test_o_core_loop_MIRA_antes_de_qualquer_outra_coisa():
    chamadas = _chamadas(HHRoutine._matar_ate_sair_de_batalha)

    assert "_mirar_o_primeiro_mob" in chamadas, (
        "A luta da HH abre com F1 + TAB. Sem isso a rotação gira contra o "
        "próprio personagem ou contra o pet, e o bot bate em nada.")
    assert chamadas.index("_mirar_o_primeiro_mob") < chamadas.index(
        "atacar_ate_sair_de_combate"), (
        "Mirar DEPOIS de começar a bater é bater no alvo errado primeiro.")


def test_a_abertura_NAO_TEM_CONDICAO():
    """Nenhum `if` antes do gesto: perguntar custa leitura e acerta menos."""
    corpo = textwrap.dedent(inspect.getsource(HHRoutine._mirar_o_primeiro_mob))
    arvore = ast.parse(corpo)
    metodo = arvore.body[0]

    assert not [n for n in ast.walk(metodo) if isinstance(n, ast.If)], (
        "O gesto é barato (duas teclas) e o resultado é sempre o mesmo -- o "
        "mob mais perto. Conferir cada caso possível antes é o que a regra do "
        "usuário substituiu.")


def test_a_HH_liga_o_detector_de_MEIO_de_luta():
    fonte = inspect.getsource(HHRoutine._matar_ate_sair_de_batalha)

    assert "reancorar_alvo_travado=self.combat.reancorar_o_alvo" in fonte, (
        "A outra metade do sintoma é o alvo que não apanha no MEIO da luta -- "
        "o pet de nível baixo passa pela abertura e só o HP parado o pega.")


# ===========================================================================
# A BC não muda
# ===========================================================================


def test_o_detector_do_motor_e_OPT_IN():
    assinatura = inspect.signature(motor.CombatEngine.atacar_ate_sair_de_combate)
    parametro = assinatura.parameters["reancorar_alvo_travado"]

    assert parametro.default is None, (
        "Padrão `None` é o que garante que a BC não muda: ela não passa "
        "gancho nenhum, e sem gancho o detector nem roda.")


def test_a_BC_nao_reancora_alvo():
    from blazesbot.bot.bc.routine import BossRushRoutine

    fonte = inspect.getsource(BossRushRoutine)
    assert "reancorar_alvo_travado" not in fonte, (
        "Decisão de cave não mora em código compartilhado, e esta é da HH: "
        "no BC o alvo travado tem outra causa e outro remédio.")


def test_o_numero_de_leituras_sem_dano_e_generoso():
    """Apertar isso reancoraria no meio de uma luta legítima."""
    ciclos = (motor.LEITURAS_SEM_DANO_ANTES_DE_REANCORAR
              * motor.CADENCIA_DA_LEITURA_DO_ALVO)

    assert ciclos >= 2.0, (
        f"{ciclos:.1f}s de HP parado é pouco: um mob com muito HP e um golpe "
        f"que erra dariam leituras iguais, e trocar de alvo ali jogaria a luta "
        f"fora.")
