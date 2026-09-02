"""A cura por skill: laço fora de batalha, e NUNCA F1 dentro dela.

=============================================================================
AS DUAS REGRAS QUE ESTES TESTES TRAVAM
=============================================================================

**1. Em batalha o personagem não se cura.** Skill em si mesmo precisa de alvo, e
o alvo é o próprio personagem -- daí o F1 antes. Só que F1 no meio da luta LARGA
o alvo, e o `CLAUDE.md` diz que o engajamento do boss depende de quem está
selecionado ("TAB sozinho não engaja, quem engaja é o golpe").

Isso era bomba armada, não defeito ativo: sem tecla de cura configurada o
`maintain` em batalha só bebia poção, e poção não precisa de alvo. **O F1
passaria a sair no meio da luta do boss no dia em que alguém configurasse a
tecla de cura da Fairy.** `test_em_batalha_nunca_*` são o dente disso.

A única coisa consumível em batalha é a POÇÃO DE BATALHA, e ela é reserva:
`battle_hp_pct` passou de 90% para 15%.

**2. Apertar e conferir têm cadências diferentes.** A cura tem 1,6 s de
conjuração. Apertar a cada 0,1 s seriam dezesseis apertos por conjuração -- caro,
e possivelmente reiniciando o cast a cada aperto, o que faria o laço nunca curar
parecendo trabalhar. Então aperta uma vez por conjuração e CONFERE a cada 0,1 s,
saindo no instante em que a vida sobe.

O `ClienteFalso` abaixo modela a conjuração de verdade: o aperto só levanta a
vida N ticks depois. Sem isso os testes de cadência não provariam nada.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot.bc.combat import CombatEngine

TECLA_DE_CURA = "E"
TECLA_DE_POCAO = "9"
TECLA_DE_POCAO_DE_BATALHA = "0"


class ClienteFalso:
    """Um cliente de mentira que respeita o TEMPO DE CONJURAÇÃO.

    `ticks_ate_curar` é quantas conferências de 0,1 s se passam entre o aperto e
    a vida subir. `None` = a cura nunca sai (recarga ou sem mana).
    """

    def __init__(self, hp_pct=50.0, cura_por_conjuracao=15.0,
                 ticks_ate_curar=16, teclas=None, potions=None):
        self.hp_pct = float(hp_pct)
        self.cura_por_conjuracao = cura_por_conjuracao
        self.ticks_ate_curar = ticks_ate_curar
        self.apertos: list[str] = []
        self.ticks = 0
        self._cura_pendente_em: int | None = None

        self.settings = SimpleNamespace(
            keys=teclas or SimpleNamespace(
                heal_skill=TECLA_DE_CURA,
                hp_potion=TECLA_DE_POCAO,
                battle_hp_potion=TECLA_DE_POCAO_DE_BATALHA,
                super_skill="",
                sit="X",
            ),
            potions=potions or SimpleNamespace(
                hp_pct=85, battle_hp_pct=15, emergency_pct=25,
                max_heal_seconds=120,
            ),
        )
        self.log = SimpleNamespace(
            info=lambda *a, **k: None, debug=lambda *a, **k: None,
            warning=lambda *a, **k: None, error=lambda *a, **k: None,
        )

    # -- o que o CombatEngine chama ---------------------------------------

    def press(self, tecla):
        self.apertos.append(tecla)
        if tecla == TECLA_DE_CURA and self.ticks_ate_curar is not None:
            self._cura_pendente_em = self.ticks + self.ticks_ate_curar

    def tick(self, _segundos=0.0):
        self.ticks += 1
        if self._cura_pendente_em is not None and self.ticks >= self._cura_pendente_em:
            self.hp_pct = min(100.0, self.hp_pct + self.cura_por_conjuracao)
            self._cura_pendente_em = None

    def snapshot(self):
        return SimpleNamespace(hp_pct=self.hp_pct, max_hp=1000, alive=True)

    def raise_if_stopped(self):
        return None

    # -- conveniências do teste -------------------------------------------

    @property
    def curas(self) -> int:
        return self.apertos.count(TECLA_DE_CURA)

    @property
    def efes1(self) -> int:
        return self.apertos.count(motor_de_combate.TECLA_AUTO_SELECAO)


def _motor(cliente) -> CombatEngine:
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = cliente
    return motor


def _estado(hp_pct):
    return SimpleNamespace(hp_pct=hp_pct, max_hp=1000, alive=True)


# ---------------------------------------------------------------------------
# 1. EM BATALHA O PERSONAGEM NÃO SE CURA
# ---------------------------------------------------------------------------

def test_em_batalha_nunca_aperta_a_skill_de_cura():
    """O dente da regra. Com a tecla de cura configurada e a vida no chão."""
    cliente = ClienteFalso(hp_pct=10.0)
    _motor(cliente).maintain(_estado(10.0), em_luta=True)

    assert TECLA_DE_CURA not in cliente.apertos, (
        "a skill de cura saiu em batalha; o F1 que ela exige larga o alvo do boss"
    )


def test_em_batalha_nunca_aperta_F1():
    cliente = ClienteFalso(hp_pct=10.0)
    _motor(cliente).maintain(_estado(10.0), em_luta=True)

    assert motor_de_combate.TECLA_AUTO_SELECAO not in cliente.apertos, (
        "F1 em batalha troca o alvo para o próprio personagem e o bot bate no vazio"
    )


def test_em_batalha_usa_a_pocao_de_batalha_abaixo_do_limiar():
    cliente = ClienteFalso(hp_pct=10.0)
    _motor(cliente).maintain(_estado(10.0), em_luta=True)

    assert cliente.apertos == [TECLA_DE_POCAO_DE_BATALHA], (
        f"esperava só a poção de batalha, veio {cliente.apertos}"
    )


def test_em_batalha_nao_bebe_acima_do_limiar():
    """15% e não 90%: a poção de batalha é reserva, não manutenção."""
    cliente = ClienteFalso(hp_pct=40.0)
    _motor(cliente).maintain(_estado(40.0), em_luta=True)

    assert cliente.apertos == []


def test_em_batalha_sem_tecla_de_pocao_de_batalha_nao_faz_nada():
    """Nunca cai para a poção NORMAL em batalha -- ela é outro item."""
    teclas = SimpleNamespace(heal_skill=TECLA_DE_CURA, hp_potion=TECLA_DE_POCAO,
                             battle_hp_potion="", super_skill="", sit="X")
    cliente = ClienteFalso(hp_pct=5.0, teclas=teclas)
    _motor(cliente).maintain(_estado(5.0), em_luta=True)

    assert cliente.apertos == []


# ---------------------------------------------------------------------------
# 2. FORA DE BATALHA
# ---------------------------------------------------------------------------

def test_fora_de_batalha_a_tecla_de_cura_manda():
    """Quem tem tecla de cura tem cura -- a configuração é a declaração."""
    cliente = ClienteFalso(hp_pct=50.0)
    _motor(cliente).maintain(_estado(50.0), em_luta=False)

    assert TECLA_DE_CURA in cliente.apertos
    assert TECLA_DE_POCAO not in cliente.apertos, "gastou poção tendo cura"


def test_fora_de_batalha_sem_cura_usa_pocao():
    teclas = SimpleNamespace(heal_skill="", hp_potion=TECLA_DE_POCAO,
                             battle_hp_potion=TECLA_DE_POCAO_DE_BATALHA,
                             super_skill="", sit="X")
    cliente = ClienteFalso(hp_pct=50.0, teclas=teclas)
    _motor(cliente).maintain(_estado(50.0), em_luta=False)

    assert cliente.apertos == [TECLA_DE_POCAO]


def test_fora_de_batalha_com_vida_cheia_nao_faz_nada():
    cliente = ClienteFalso(hp_pct=95.0)
    _motor(cliente).maintain(_estado(95.0), em_luta=False)

    assert cliente.apertos == []


# ---------------------------------------------------------------------------
# 3. O LAÇO: cadência, saída antecipada e desistência
# ---------------------------------------------------------------------------

def test_aperta_uma_vez_por_conjuracao_e_nao_dezesseis():
    """O ganho central. 50% -> 85% com 15% por cura são TRÊS conjurações.

    Se a cadência do aperto fosse a da conferência (0,1 s), seriam ~48.
    """
    cliente = ClienteFalso(hp_pct=50.0, cura_por_conjuracao=15.0,
                           ticks_ate_curar=16)
    assert _motor(cliente).curar_com_skill(85.0) is True

    assert cliente.curas == 3, (
        f"{cliente.curas} apertos para 3 conjurações -- a cadência do aperto "
        "escapou para a da conferência"
    )


def test_o_F1_sai_uma_vez_so():
    """Fora de combate a seleção não muda sozinha; repetir seria mensagem à toa."""
    cliente = ClienteFalso(hp_pct=50.0)
    _motor(cliente).curar_com_skill(85.0)

    assert cliente.efes1 == 1, f"F1 saiu {cliente.efes1} vezes"


def test_sai_no_instante_em_que_a_vida_sobe():
    """Conjuração que termina cedo não paga a espera que faltava para o teto."""
    rapido = ClienteFalso(hp_pct=50.0, cura_por_conjuracao=40.0, ticks_ate_curar=3)
    _motor(rapido).curar_com_skill(85.0)

    lento = ClienteFalso(hp_pct=50.0, cura_por_conjuracao=40.0, ticks_ate_curar=16)
    _motor(lento).curar_com_skill(85.0)

    assert rapido.ticks < lento.ticks, (
        "a cura rápida gastou o mesmo tanto que a lenta -- a espera é cega"
    )


def test_desiste_depois_de_tres_conjuracoes_sem_efeito():
    """Sem mana ou em recarga, descobre em ~7 s em vez de gastar os 120 s."""
    cliente = ClienteFalso(hp_pct=50.0, ticks_ate_curar=None)
    assert _motor(cliente).curar_com_skill(85.0) is False

    assert cliente.curas == motor_de_combate.TENTATIVAS_SEM_EFEITO, (
        f"apertou {cliente.curas} vezes, o teto é {motor_de_combate.TENTATIVAS_SEM_EFEITO}"
    )


def test_uma_conjuracao_que_sai_rearma_o_contador():
    """Uma cura no meio de falhas não pode contar como progresso perdido."""
    cliente = ClienteFalso(hp_pct=50.0, cura_por_conjuracao=40.0, ticks_ate_curar=16)
    assert _motor(cliente).curar_com_skill(85.0) is True
    assert cliente.curas == 1


def test_devolve_true_sem_apertar_nada_com_a_vida_ja_no_alvo():
    cliente = ClienteFalso(hp_pct=90.0)
    assert _motor(cliente).curar_com_skill(85.0) is True
    assert cliente.apertos == []


def test_sem_tecla_de_cura_devolve_false_sem_apertar():
    teclas = SimpleNamespace(heal_skill="", hp_potion=TECLA_DE_POCAO,
                             battle_hp_potion="", super_skill="", sit="X")
    cliente = ClienteFalso(hp_pct=50.0, teclas=teclas)
    assert _motor(cliente).curar_com_skill(85.0) is False
    assert cliente.apertos == []


def test_sem_leitura_de_hp_devolve_false():
    """`None` é "não sei", e não autoriza apertar tecla no escuro."""
    cliente = ClienteFalso(hp_pct=50.0)
    cliente.snapshot = lambda: SimpleNamespace(hp_pct=None, max_hp=None, alive=True)
    assert _motor(cliente).curar_com_skill(85.0) is False
    assert cliente.apertos == []


# ---------------------------------------------------------------------------
# 4. O interruptor: o caminho antigo continua inteiro
# ---------------------------------------------------------------------------

def test_modo_pocao_devolve_o_comportamento_antigo(monkeypatch):
    """Reverter tem que ser trocar uma palavra, não ligar código não testado."""
    monkeypatch.setattr(motor_de_combate, "MODO_DE_CURA", "pocao")

    cliente = ClienteFalso(hp_pct=10.0)
    _motor(cliente).maintain(_estado(10.0), em_luta=True)

    assert cliente.apertos, "o caminho antigo não fez nada -- apodreceu"
    assert TECLA_DE_CURA in cliente.apertos, (
        "o caminho antigo usava a skill de cura em batalha; se não usa mais, "
        "ele não é mais o caminho antigo"
    )


def test_modo_pocao_desliga_o_laco(monkeypatch):
    monkeypatch.setattr(motor_de_combate, "MODO_DE_CURA", "pocao")

    cliente = ClienteFalso(hp_pct=50.0)
    assert _motor(cliente).curar_com_skill(85.0) is False
    assert cliente.apertos == []


# ---------------------------------------------------------------------------
# 5. As constantes
# ---------------------------------------------------------------------------

def test_a_conjuracao_e_a_informada_pelo_usuario():
    """1,6 s veio do usuário em 19/08/2026. Mudar sem medir de novo desfaz a
    única coisa medida deste conjunto."""
    assert motor_de_combate.SEGUNDOS_DE_CONJURACAO_DA_CURA == 1.6


def test_conferir_e_mais_rapido_que_conjurar():
    """Se a conferência ficasse maior que a conjuração, a saída antecipada
    deixaria de existir e o laço voltaria a ser espera cega."""
    assert motor_de_combate.INTERVALO_DE_CONFERENCIA < motor_de_combate.SEGUNDOS_DE_CONJURACAO_DA_CURA


def test_a_margem_da_conjuracao_e_positiva():
    assert motor_de_combate.MARGEM_DA_CONJURACAO > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
