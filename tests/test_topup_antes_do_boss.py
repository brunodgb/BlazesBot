"""O top-up antes do boss: sentado, os 15 s inteiros, e até a vida ENCHER.

=============================================================================
OS TRÊS DEFEITOS RELATADOS
=============================================================================

O usuário reportou em 19/08/2026: *"ao usar a poção de vida antes do boss, ele
não está ficando os 15 segundos parado sentado; é importante ficar até o final e
conferir se está com a vida cheia para matar, pois quem precisou da poção vai
precisar se curar -- normalmente é um personagem mais fraco, que depende de
estar full vida para começar a luta."*

Eram três coisas, todas no mesmo trecho:

1. **NÃO SENTAVA.** `k.sit` não era tocado ali. Quem senta é o `heal_to_full`,
   que roda fora da instância.
2. **A ESPERA SAÍA CURTA.** `ctx.tick(15.0)` passa por `jitter(base, 0.15)` =
   12,75 s a 17,25 s. Nas vezes baixas faltavam 2,25 s do temporizador da poção.
   Jitter numa DURAÇÃO QUE O JOGO EXIGE encurta o efeito; agora o prazo é por
   RELÓGIO e o total nunca sai curto.
3. **NÃO CONFERIA NADA.** Logava o resultado e seguia para o boss com qualquer
   vida.

E uma regra nova: **quem precisou de poção e depois morreu tem o BC desligado**,
porque isso aponta falta de item essencial.

=============================================================================
O TESTE QUE CARREGA O PESO
=============================================================================

`test_a_espera_nunca_sai_CURTA`. Ele é o único que pega o defeito 2, e o defeito
2 é o invisível dos três: nada no log dizia que faltaram 2 s, e o efeito era só
"a poção rendeu menos do que devia" -- que ninguém atribui a um sorteio.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot.bc.combat import CombatEngine

TECLA_DA_POCAO = "9"
TECLA_DE_SENTAR = "X"


class _Relogio:
    """Relógio determinístico. `tick` do dublê avança ele."""

    def __init__(self, inicio=10_000.0):
        self.agora = inicio

    def __call__(self):
        return self.agora

    def avancar(self, s):
        self.agora += s


class ClienteFalso:
    """Modela vida que sobe por poção, e conta o que foi apertado quando."""

    def __init__(self, relogio, hp_inicial=30.0, cura_por_pocao=40.0,
                 sentando=False, tecla_de_sentar=TECLA_DE_SENTAR,
                 max_heal_seconds=120):
        self._relogio = relogio
        self.hp_pct = float(hp_inicial)
        self.cura_por_pocao = cura_por_pocao
        self.apertos: list[tuple[float, str]] = []
        self._sentando = sentando
        self.settings = SimpleNamespace(
            keys=SimpleNamespace(hp_potion=TECLA_DA_POCAO,
                                 sit=tecla_de_sentar),
            potions=SimpleNamespace(max_heal_seconds=max_heal_seconds),
        )
        self.log = SimpleNamespace(info=lambda *a, **k: None,
                                   debug=lambda *a, **k: None,
                                   warning=lambda *a, **k: None,
                                   error=lambda *a, **k: None)
        self.memory = SimpleNamespace(is_sitting=lambda: self._sentando)

    def press(self, tecla, hold=0.10):
        self.apertos.append((round(self._relogio.agora, 2), tecla))
        if tecla == TECLA_DA_POCAO:
            self.hp_pct = min(100.0, self.hp_pct + self.cura_por_pocao)
        if tecla == TECLA_DE_SENTAR:
            self._sentando = not self._sentando
        return True

    def tick(self, s=0.2):
        """Avança o relógio pelo PIOR SORTEIO do jitter, não pelo valor pedido.

        SEM ISTO O TESTE DA ESPERA CURTA NÃO PEGA NADA. A produção passa por
        `jitter(base, 0.15)`, ou seja o `tick(15.0)` do código antigo avançava
        entre 12,75 s e 17,25 s. Um dublê que avançasse exatamente 15 s faria a
        versão defeituosa PASSAR -- e um teste que não pode falhar no defeito que
        nomeia é pior que teste nenhum.

        Modelar o pior caso (0,85x) é o certo: é o sorteio que encurta a poção, e
        um teste determinístico tem que ser o adversário, não a média.
        """
        self._relogio.avancar(s * 0.85)

    def snapshot(self):
        return SimpleNamespace(hp_pct=self.hp_pct, max_hp=1000)

    def raise_if_stopped(self):
        pass

    # -- conveniências ----------------------------------------------------

    @property
    def pocoes(self) -> list[float]:
        return [t for t, k in self.apertos if k == TECLA_DA_POCAO]

    @property
    def sentadas(self) -> list[float]:
        return [t for t, k in self.apertos if k == TECLA_DE_SENTAR]


def _motor(monkeypatch, cliente, relogio):
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = cliente
    motor._precisou_de_pocao_antes_do_boss = False
    monkeypatch.setattr(motor_de_combate.time, "time", relogio)
    return motor


def _beber(monkeypatch, **kw):
    relogio = _Relogio()
    cliente = ClienteFalso(relogio, **kw)
    motor = _motor(monkeypatch, cliente, relogio)
    motor._beber_ate_encher(TECLA_DA_POCAO, cliente.hp_pct)
    return cliente, relogio


# ---------------------------------------------------------------------------
# 1. A ESPERA NUNCA SAI CURTA -- o defeito invisível
# ---------------------------------------------------------------------------

def test_a_espera_nunca_sai_CURTA(monkeypatch):
    """O prazo é por RELÓGIO, não por `ctx.tick(15.0)`.

    Com `tick` sorteando jitter sobre o valor inteiro, 15 s viravam 12,75 s no
    pior sorteio -- e a poção do jogo dura 15 s. Faltavam 2,25 s de efeito, sem
    nada no log dizendo isso.

    Aqui a vida NÃO chega ao alvo, então o laço tem que cumprir o prazo cheio de
    cada poção.
    """
    cliente, relogio = _beber(monkeypatch, hp_inicial=10.0,
                              cura_por_pocao=1.0, max_heal_seconds=40)

    assert len(cliente.pocoes) >= 2, "precisa de mais de uma poção no cenário"
    entre_pocoes = [b - a for a, b in zip(cliente.pocoes, cliente.pocoes[1:])]
    for gasto in entre_pocoes:
        assert gasto >= motor_de_combate.SEGUNDOS_DA_POCAO_DE_VIDA, (
            f"esperou {gasto:.2f}s entre poções, e a poção dura "
            f"{motor_de_combate.SEGUNDOS_DA_POCAO_DE_VIDA}s -- a espera saiu curta"
        )


def test_sai_CEDO_quando_a_vida_enche(monkeypatch):
    """"Caso atinja os 100% pode continuar, sem ter que esperar os 15 segundos
    totais" -- palavras do usuário. Uma poção que enche não paga o resto."""
    relogio = _Relogio()
    cliente = ClienteFalso(relogio, hp_inicial=90.0, cura_por_pocao=40.0)
    motor = _motor(monkeypatch, cliente, relogio)

    inicio = relogio.agora
    motor._beber_ate_encher(TECLA_DA_POCAO, 90.0)
    gasto = relogio.agora - inicio

    assert cliente.hp_pct == 100.0
    assert gasto < motor_de_combate.SEGUNDOS_DA_POCAO_DE_VIDA, (
        f"gastou {gasto:.2f}s depois de a vida encher; devia sair na hora"
    )


# ---------------------------------------------------------------------------
# 2. NENHUMA TECLA DE POSTURA -- nem sentar, nem levantar
# ---------------------------------------------------------------------------

def test_nao_mexe_na_postura(monkeypatch):
    """A poção senta sozinha, e qualquer movimentação levanta -- as duas
    confirmadas pelo usuário.

    `sit` é INTERRUPTOR. Apertá-lo "por garantia" é a forma mais fácil de
    terminar de pé quando se queria sentado, ou o contrário -- e a primeira
    versão deste código sentava antes de beber, o que o usuário mandou tirar.
    """
    cliente, _ = _beber(monkeypatch, hp_inicial=10.0, cura_por_pocao=1.0,
                        max_heal_seconds=60)

    assert cliente.pocoes, "não bebeu nada no cenário"
    assert cliente.sentadas == [], (
        f"apertou a tecla de postura {len(cliente.sentadas)}x -- a poção já "
        "senta, e `sit` é interruptor"
    )


def test_so_a_pocao_e_apertada(monkeypatch):
    """Nada além da poção sai deste laço."""
    cliente, _ = _beber(monkeypatch, hp_inicial=30.0)

    teclas = {k for _t, k in cliente.apertos}
    assert teclas == {TECLA_DA_POCAO}, f"apertou também: {teclas - {TECLA_DA_POCAO}}"


# ---------------------------------------------------------------------------
# 3. BEBE ATÉ ENCHER, uma de cada vez
# ---------------------------------------------------------------------------

def test_bebe_ate_100_por_cento(monkeypatch):
    """30% com 40 por poção = três poções para chegar a 100%."""
    cliente, _ = _beber(monkeypatch, hp_inicial=30.0, cura_por_pocao=40.0)

    assert cliente.hp_pct == 100.0
    assert len(cliente.pocoes) == 2, f"{len(cliente.pocoes)} poções para 30->100"


def test_uma_de_cada_vez(monkeypatch):
    """Disparar várias juntas desperdiçaria item comprado."""
    cliente, _ = _beber(monkeypatch, hp_inicial=10.0, cura_por_pocao=1.0,
                        max_heal_seconds=40)

    for a, b in zip(cliente.pocoes, cliente.pocoes[1:]):
        assert b - a >= motor_de_combate.SEGUNDOS_DA_POCAO_DE_VIDA


def test_o_teto_impede_prender_a_run(monkeypatch):
    """Sem poção na bolsa a vida não sobe. Insistir prenderia a run com o boss
    esperando -- estourar o teto é aviso, e a run segue."""
    relogio = _Relogio()
    cliente = ClienteFalso(relogio, hp_inicial=20.0, cura_por_pocao=0.0,
                           max_heal_seconds=45)
    motor = _motor(monkeypatch, cliente, relogio)

    inicio = relogio.agora
    motor._beber_ate_encher(TECLA_DA_POCAO, 20.0)
    gasto = relogio.agora - inicio

    assert gasto < 45 + motor_de_combate.SEGUNDOS_DA_POCAO_DE_VIDA + 5
    assert cliente.hp_pct == 20.0


def test_vida_ja_cheia_nao_gasta_pocao(monkeypatch):
    cliente, _ = _beber(monkeypatch, hp_inicial=100.0)
    assert cliente.pocoes == []


def test_sem_leitura_de_hp_nao_bebe_no_escuro(monkeypatch):
    relogio = _Relogio()
    cliente = ClienteFalso(relogio, hp_inicial=30.0)
    cliente.snapshot = lambda: SimpleNamespace(hp_pct=None, max_hp=None)
    motor = _motor(monkeypatch, cliente, relogio)

    motor._beber_ate_encher(TECLA_DA_POCAO, 30.0)

    assert cliente.pocoes == []


# ---------------------------------------------------------------------------
# 4. Precisou de poção e MORREU -> para o BC daquela conta
# ---------------------------------------------------------------------------

class _Conta:
    def __init__(self):
        self.bc_farm = True
        self.login = "teste"


def _motor_com_conta(precisou):
    motor = CombatEngine.__new__(CombatEngine)
    motor._precisou_de_pocao_antes_do_boss = precisou
    conta = _Conta()
    salvou = []
    motor.ctx = SimpleNamespace(
        account=conta,
        account_login="teste",
        config=SimpleNamespace(save=lambda: salvou.append(True)),
        memory=SimpleNamespace(position=lambda: (0, 0), location=lambda: "cave"),
        log=SimpleNamespace(error=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            info=lambda *a, **k: None),
    )
    return motor, conta, salvou


def test_precisou_de_pocao_e_morreu_DESLIGA_o_bc(monkeypatch):
    """Regra do usuário: morrer depois de ter precisado de poção aponta falta de
    item essencial, e uma conta sem poção não termina run nenhuma."""
    monkeypatch.setattr(motor_de_combate.diario, "registrar_evento",
                        lambda *a, **k: None)
    motor, conta, salvou = _motor_com_conta(precisou=True)

    motor._parar_a_conta_se_precisou_de_pocao()

    assert conta.bc_farm is False
    assert salvou, "desligou e não salvou -- volta ligado na próxima abertura"


def test_morreu_SEM_ter_precisado_de_pocao_nao_desliga(monkeypatch):
    """Morte pode ter mil causas. Só a que aponta ESTOQUE para a conta."""
    monkeypatch.setattr(motor_de_combate.diario, "registrar_evento",
                        lambda *a, **k: None)
    motor, conta, salvou = _motor_com_conta(precisou=False)

    motor._parar_a_conta_se_precisou_de_pocao()

    assert conta.bc_farm is True
    assert salvou == []


def test_falha_ao_salvar_nao_derruba_a_parada(monkeypatch):
    monkeypatch.setattr(motor_de_combate.diario, "registrar_evento",
                        lambda *a, **k: None)
    motor, conta, _ = _motor_com_conta(precisou=True)
    motor.ctx.config.save = lambda: (_ for _ in ()).throw(OSError("disco"))

    motor._parar_a_conta_se_precisou_de_pocao()

    assert conta.bc_farm is False


def test_o_alvo_e_vida_CHEIA():
    """100%, e é decisão do usuário: "depende de estar full vida para começar a
    luta contra o boss"."""
    assert motor_de_combate.ALVO_DO_TOPUP_ANTES_DO_BOSS == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
