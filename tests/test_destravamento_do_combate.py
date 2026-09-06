"""Preso em batalha, o bot MATA MOB A MOB em vez de insistir na montaria.

O DEFEITO, MEDIDO NO LOG (31/08/2026, conta `creubo`, run `db7ebdace7`): o bot
ficou **24 minutos e 25 segundos** parado no waypoint dos Gun Witch (110,-406)
apertando a tecla da montaria. A fase dos guardas tinha encerrado LIMPA -- "Fora
de combate confirmado ... 2,6s contínuos com a flag baixa" --, o Cemetery Guard
que o ESC largou voltou a engajar, e em batalha o jogo RECUSA a montaria. O
portão insiste sem teto por desenho (`NUNCA A PÉ DENTRO DA CAVE`), então ele
insistiu contra uma condição que só um golpe resolve:

    23:28:07  GUARDAS -> ATE_O_BOSS -> "Não estou montado; montando"
              ... 453 linhas de "Não conseguiu montar em 6s" ...
    23:52:32  Montaria confirmada depois de 1465s insistindo

Ele só destravou porque a INSTÂNCIA EXPIROU e cuspiu o personagem para fora do
covil. Não foi recuperação, foi sorte.

A COREOGRAFIA, palavras do usuário em 01/09/2026: *"vai matando de 1 em 1 e
olhando se saiu de batalha ... no máximo atrasar 1 minuto ... só deve dar TAB
depois de 3 segundos que não saiu de batalha, mas nesses 3 segundos você vai
verificando se não sai de batalha antes"*.

Os interruptores são exercitados LIGADOS, como manda a regra da casa.
"""
import pytest

from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot import navegacao as navigation
from blazesbot.bot.bc import combat


class _Relogio:
    def __init__(self):
        self.agora = 0.0


class _FakeMemoria:
    def __init__(self):
        self.em_batalha = True
        self.montado = False
        self.tem_alvo = True

    def in_battle(self):
        return self.em_batalha

    def is_mounted(self):
        return self.montado

    def critical_ok(self):
        return True

    def alvo_atual(self):
        return {"id": 1} if self.tem_alvo else None

    def position(self):
        return (110, -406)

    def location(self):
        return "Secret Cemetery"


class _FakeCtx:
    """O mínimo que o destravamento e o portão da montaria tocam."""

    def __init__(self, relogio):
        self._relogio = relogio
        self.teclas = []
        self.morto = False
        self.log = self
        self.memory = _FakeMemoria()
        self.account_login = "conta"
        self.settings = type("S", (), {
            "bc": type("B", (), {"attack_delay": 0.5})(),
            "keys": type("K", (), {"next_target": "tab", "mount": "z"})(),
            "mount_speed_pct": 120,
        })()
        # A CAVE QUE ESTÁ RODANDO. Os motores compartilhados leem número
        # de cave por aqui desde 03/09/2026 (`ctx.cave`), em vez de
        # `settings.bc` direto -- era o que fazia a HH rodar com os
        # números do BC. Aqui aponta para o `bc` deste dublê, que é a
        # cave que estes testes exercitam.
        self.cave = self.settings.bc

    def tick(self, seconds):
        self._relogio.agora += seconds

    def raise_if_stopped(self):
        pass

    def press(self, key, delay=0.0):
        self.teclas.append(key)

    def snapshot(self):
        return type("E", (), {"dead": self.morto, "hp_pct": 100.0,
                              "max_hp": 100, "sitting": False,
                              "position": (110, -406),
                              "location": "Secret Cemetery"})()

    def info(self, *a, **kw):
        pass

    def debug(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass

    def error(self, *a, **kw):
        pass


class _Mundo:
    """Um covil de mentira: mobs que morrem em N golpes e uma flag que segue.

    A flag fica ALTA enquanto sobrar mob vivo e baixa `atraso_da_flag` segundos
    depois da última morte -- que é o comportamento observado no jogo e o que
    torna a pausa de três segundos uma decisão de verdade e não enfeite.
    """

    def __init__(self, relogio, golpes_por_mob, atraso_da_flag=0.5):
        self.relogio = relogio
        self.restantes = list(golpes_por_mob)
        self.atraso_da_flag = atraso_da_flag
        self.golpes_no_alvo = 0
        self.morte_contada = False
        self.morreu_em = None
        self.aoe_pedido = []

    # -- o que o motor de combate lê -------------------------------------
    def flag(self):
        if self.restantes:
            return True
        if self.morreu_em is None:
            return True
        return (self.relogio.agora - self.morreu_em) < self.atraso_da_flag

    def alvo_morreu(self):
        if not self.restantes or self.morte_contada:
            return False
        if self.golpes_no_alvo < self.restantes[0]:
            return False
        self.morte_contada = True
        self.restantes.pop(0)
        self.morreu_em = self.relogio.agora
        return True

    # -- o que o motor de combate faz ------------------------------------
    def bateu(self):
        self.golpes_no_alvo += 1

    def tabulou(self):
        # TAB pega o mob seguinte: os golpes recomeçam do zero.
        self.golpes_no_alvo = 0
        self.morte_contada = False


def _motor(monkeypatch, relogio, mundo, *, nomes=("Gun Witch",)):
    ctx = _FakeCtx(relogio)
    motor = object.__new__(combat.CombatEngine)
    motor.ctx = ctx
    motor._ultimos_nomes_do_alvo = []

    monkeypatch.setattr(motor_de_combate.time, "time", lambda: relogio.agora)
    monkeypatch.setattr(motor_de_combate.diario, "registrar_evento",
                        lambda *a, **kw: None)
    monkeypatch.setattr(combat.CombatEngine, "_descer_para_lutar",
                        lambda self, o_que: True)
    monkeypatch.setattr(combat.CombatEngine, "maintain",
                        lambda self, state, em_luta=False: None)
    monkeypatch.setattr(combat.CombatEngine, "_ler_flag_de_combate",
                        lambda self: mundo.flag())
    monkeypatch.setattr(combat.CombatEngine, "_alvo_morreu",
                        lambda self: mundo.alvo_morreu())

    def _skill(self, state, usar_aoe):
        mundo.aoe_pedido.append(usar_aoe)
        mundo.bateu()
        return "1"
    monkeypatch.setattr(combat.CombatEngine, "_proxima_skill", _skill)

    def _veredito(self, esperado):
        self._ultimos_nomes_do_alvo = list(nomes)
        if any(esperado.lower() in n.lower() for n in nomes):
            return "bate"
        return "acabaram" if nomes else "ilegivel"
    monkeypatch.setattr(combat.CombatEngine, "_veredito_do_alvo", _veredito)

    # O TAB de verdade passa por `ctx.press`; o mundo precisa saber dele.
    press_original = ctx.press

    def _press(key, delay=0.0):
        press_original(key, delay)
        if key == "tab":
            mundo.tabulou()
    ctx.press = _press

    return motor, ctx


# ---------------------------------------------------------------------------
# os interruptores
# ---------------------------------------------------------------------------

def test_os_interruptores_estao_ligados():
    assert motor_de_combate.DESTRAVAMENTO_BATE_NO_ALVO_PROIBIDO is True
    assert motor_de_combate.TETO_DO_DESTRAVAMENTO == 60.0
    assert motor_de_combate.ESPERA_APOS_A_MORTE_ANTES_DO_TAB == 3.0
    assert navigation.CICLOS_ANTES_DE_DESTRAVAR == 2


# ---------------------------------------------------------------------------
# 1. fora de batalha não faz nada
# ---------------------------------------------------------------------------

def test_fora_de_batalha_devolve_na_hora_sem_bater(monkeypatch):
    relogio = _Relogio()
    mundo = _Mundo(relogio, [])
    mundo.morreu_em = -99.0          # a flag já está baixa
    motor, ctx = _motor(monkeypatch, relogio, mundo)

    assert motor.limpar_o_combate("ir até o boss") is True
    assert ctx.teclas == []
    assert relogio.agora == 0.0


def test_flag_ilegivel_nao_conta_como_fora_de_batalha(monkeypatch):
    """`None` é NÃO SEI. Quem chamou está travado -- desistir aqui devolveria
    o bot para o mesmo laço mudo que produziu os 24 minutos do log."""
    relogio = _Relogio()
    mundo = _Mundo(relogio, [1])
    motor, ctx = _motor(monkeypatch, relogio, mundo)
    monkeypatch.setattr(combat.CombatEngine, "_ler_flag_de_combate",
                        lambda self: None)

    assert motor.limpar_o_combate("ir até o boss") is False
    assert relogio.agora >= motor_de_combate.TETO_DO_DESTRAVAMENTO


# ---------------------------------------------------------------------------
# 2. a coreografia: matar, PARAR, olhar a flag, e só então o TAB
# ---------------------------------------------------------------------------

def test_um_mob_so_nao_gasta_nenhum_TAB(monkeypatch):
    """Morreu o último: a flag baixa DENTRO da pausa e o TAB não sai.

    É este o caso que impede a bola de neve: o TAB imediato depois da morte
    miraria o mob seguinte, o golpe o puxaria, e o bot trocaria um travamento
    por outro.
    """
    relogio = _Relogio()
    mundo = _Mundo(relogio, [3], atraso_da_flag=0.5)
    motor, ctx = _motor(monkeypatch, relogio, mundo)

    assert motor.limpar_o_combate("ir até o boss") is True
    assert ctx.teclas.count("tab") == 0


def test_ainda_em_batalha_depois_dos_3s_gasta_UM_TAB_e_segue(monkeypatch):
    """Dois mobs: o primeiro cai, a flag continua alta, sai UM TAB."""
    relogio = _Relogio()
    # A flag só baixa quando os DOIS morrerem (a lista esvazia).
    mundo = _Mundo(relogio, [2, 2], atraso_da_flag=0.5)
    motor, ctx = _motor(monkeypatch, relogio, mundo)

    assert motor.limpar_o_combate("ir até o boss") is True
    assert ctx.teclas.count("tab") == 1


def test_a_pausa_nao_gasta_TAB_antes_dos_3_segundos(monkeypatch):
    """A pausa é de 3 s NO MÁXIMO, e nada é apertado durante ela."""
    relogio = _Relogio()
    mundo = _Mundo(relogio, [1], atraso_da_flag=0.0)
    motor, ctx = _motor(monkeypatch, relogio, mundo)

    momento_da_morte = []
    morreu_original = mundo.alvo_morreu

    def _espia():
        caiu = morreu_original()
        if caiu:
            momento_da_morte.append(relogio.agora)
        return caiu
    mundo.alvo_morreu = _espia

    assert motor.limpar_o_combate("ir até o boss") is True
    # Saiu pela confirmação (2,5 s), não pelo prazo da pausa (3,0 s), e sem TAB.
    gasto = relogio.agora - momento_da_morte[0]
    assert motor_de_combate.CONFIRMACAO_DE_SAIDA_DE_COMBATE <= gasto < (
        motor_de_combate.ESPERA_APOS_A_MORTE_ANTES_DO_TAB
        + motor_de_combate.CONFIRMACAO_DE_SAIDA_DE_COMBATE)
    assert ctx.teclas.count("tab") == 0


# ---------------------------------------------------------------------------
# 3. um de cada vez -- NUNCA em área
# ---------------------------------------------------------------------------

def test_o_destravamento_nunca_usa_AoE(monkeypatch):
    """Área acerta quem está em volta e PUXA mob que não estava em combate."""
    relogio = _Relogio()
    mundo = _Mundo(relogio, [2, 2])
    motor, _ = _motor(monkeypatch, relogio, mundo)

    motor.limpar_o_combate("ir até o boss")
    assert mundo.aoe_pedido, "não bateu em ninguém"
    assert not any(mundo.aoe_pedido)


def test_sem_alvo_na_mira_o_primeiro_TAB_sai(monkeypatch):
    relogio = _Relogio()
    mundo = _Mundo(relogio, [2])
    motor, ctx = _motor(monkeypatch, relogio, mundo)
    ctx.memory.tem_alvo = False

    motor.limpar_o_combate("ir até o boss")
    assert ctx.teclas.count("tab") >= 1


# ---------------------------------------------------------------------------
# 4. o Cemetery Guard -- a trava é suspensa AQUI, e só aqui
# ---------------------------------------------------------------------------

def test_o_destravamento_bate_no_cemetery_guard(monkeypatch):
    """Fora do destravamento a trava é inteira; aqui ela já falhou.

    Se o destravamento está rodando é porque o ESC e a espera não bastaram --
    e foi essa espera que produziu os 24 minutos.
    """
    relogio = _Relogio()
    mundo = _Mundo(relogio, [2])
    motor, _ = _motor(monkeypatch, relogio, mundo,
                      nomes=(combat.NOME_DO_CEMETERY_GUARD,))
    motor._avisou_o_guarda_no_destravamento = False
    motor._alvo_proibido_encontrado = False

    assert motor._pode_bater_no_destravamento() is True


def test_com_o_interruptor_desligado_o_guarda_continua_intocado(monkeypatch):
    relogio = _Relogio()
    mundo = _Mundo(relogio, [2])
    motor, ctx = _motor(monkeypatch, relogio, mundo,
                        nomes=(combat.NOME_DO_CEMETERY_GUARD,))
    motor._alvo_proibido_encontrado = False
    monkeypatch.setattr(motor_de_combate, "DESTRAVAMENTO_BATE_NO_ALVO_PROIBIDO", False)

    assert motor._pode_bater_no_destravamento() is False
    assert "esc" in ctx.teclas


def test_gun_witch_na_mira_apanha_sem_pergunta(monkeypatch):
    relogio = _Relogio()
    mundo = _Mundo(relogio, [2])
    motor, _ = _motor(monkeypatch, relogio, mundo, nomes=("Gun Witch",))
    motor._alvo_proibido_encontrado = False

    assert motor._pode_bater_no_destravamento() is True


# ---------------------------------------------------------------------------
# 5. o teto -- um minuto, não vinte e quatro
# ---------------------------------------------------------------------------

def test_o_teto_e_de_um_minuto_e_devolve_False(monkeypatch):
    """Nada morre e a flag não baixa: devolve o controle em ~1 min.

    False NÃO encerra nada -- o portão da montaria continua insistindo e chama
    de novo. O que o teto limita é quanto tempo o bot passa BATENDO antes de
    reavaliar.
    """
    relogio = _Relogio()
    mundo = _Mundo(relogio, [999])       # ninguém cai
    motor, _ = _motor(monkeypatch, relogio, mundo)

    assert motor.limpar_o_combate("ir até o boss") is False
    assert relogio.agora >= motor_de_combate.TETO_DO_DESTRAVAMENTO
    # "No máximo atrasar 1 minuto": o teto vale de verdade, e o que passa dele
    # é só a última pausa. Medido nesta simulação: 63,1 s. Contra 1465 s no log.
    assert relogio.agora < motor_de_combate.TETO_DO_DESTRAVAMENTO + 10.0


def test_morrer_no_meio_do_destravamento_encerra_a_rodada(monkeypatch):
    relogio = _Relogio()
    mundo = _Mundo(relogio, [999])
    motor, ctx = _motor(monkeypatch, relogio, mundo)
    ctx.morto = True

    assert motor.limpar_o_combate("ir até o boss") is False
    # Não ficou girando a rotação contra o nada com o personagem morto: cada
    # rodada sai na primeira manutenção.
    assert relogio.agora < 2 * motor_de_combate.TETO_DO_DESTRAVAMENTO


# ===========================================================================
# O PORTÃO DA MONTARIA -- quem chama o destravamento
# ===========================================================================

def _navegador(monkeypatch, relogio, ctx, *, montagens):
    """Um `Navigator` cru com o `ensure_mounted` roteirizado.

    `montagens` é a sequência de respostas: `[False, False, True]` significa
    "falhou duas vezes e montou na terceira".
    """
    nav = object.__new__(navigation.Navigator)
    nav.ctx = ctx
    nav._avisou_sem_tecla = False
    nav._exigir_montaria = True           # a BC nunca anda a pé; ver Navigator
    nav._avisou_a_pe = False
    nav._ultimo_toque_na_montaria = 0.0
    nav.destravar_o_combate = None

    respostas = list(montagens)

    def _ensure(self, timeout=0.0):
        ctx.tick(navigation.TETO_DO_PORTAO)
        return respostas.pop(0) if respostas else True
    monkeypatch.setattr(navigation.Navigator, "ensure_mounted", _ensure)
    monkeypatch.setattr(navigation.time, "time", lambda: relogio.agora)
    monkeypatch.setattr(navigation.diario, "registrar_evento",
                        lambda *a, **kw: None)
    monkeypatch.setattr(navigation.hotbar, "garantir_pagina_1",
                        lambda ctx_, motivo: True)
    return nav


def test_o_portao_chama_o_destravamento_quando_esta_em_batalha(monkeypatch):
    """A causa é lida, e a causa é TRATADA -- não repetida no log 62 vezes."""
    relogio = _Relogio()
    ctx = _FakeCtx(relogio)
    ctx.memory.em_batalha = True
    nav = _navegador(monkeypatch, relogio, ctx,
                     montagens=[False, False, True])

    chamados = []

    def _destravar(motivo):
        chamados.append(motivo)
        ctx.memory.em_batalha = False
        return True
    nav.destravar_o_combate = _destravar

    assert nav.garantir_montaria_para_andar("ir até o boss") is True
    assert chamados == ["ir até o boss"]


def test_o_portao_nao_destrava_no_primeiro_ciclo(monkeypatch):
    """Um ciclo é `TETO_DO_PORTAO` = 6 s, o dobro da montagem mais lenta
    medida. Sair batendo no primeiro tropeço custaria mais do que espera."""
    relogio = _Relogio()
    ctx = _FakeCtx(relogio)
    ctx.memory.em_batalha = True
    nav = _navegador(monkeypatch, relogio, ctx, montagens=[False, True])

    chamados = []
    nav.destravar_o_combate = lambda motivo: chamados.append(motivo)

    assert nav.garantir_montaria_para_andar("ir até o boss") is True
    assert chamados == []


def test_flag_ilegivel_no_portao_nao_manda_o_bot_bater(monkeypatch):
    """"Não sei" nunca autoriza gastar um minuto puxando mob."""
    relogio = _Relogio()
    ctx = _FakeCtx(relogio)
    ctx.memory.em_batalha = None
    nav = _navegador(monkeypatch, relogio, ctx,
                     montagens=[False, False, False, True])

    chamados = []
    nav.destravar_o_combate = lambda motivo: chamados.append(motivo)

    assert nav.garantir_montaria_para_andar("ir até o boss") is True
    assert chamados == []


def test_personagem_morto_no_portao_levanta_em_vez_de_insistir(monkeypatch):
    """Cadáver não monta. Antes o laço apertava a tecla para sempre."""
    relogio = _Relogio()
    ctx = _FakeCtx(relogio)
    ctx.morto = True
    nav = _navegador(monkeypatch, relogio, ctx,
                     montagens=[False, False, False, True])

    with pytest.raises(navigation.PersonagemMortoNoPortao):
        nav.garantir_montaria_para_andar("ir até o boss")


def test_o_portao_continua_insistindo_quando_o_destravamento_falha(monkeypatch):
    """`NUNCA A PÉ DENTRO DA CAVE` continua inteiro: não há teto para desistir.

    O que mudou é que agora ele age entre as tentativas em vez de ficar mudo.
    """
    relogio = _Relogio()
    ctx = _FakeCtx(relogio)
    ctx.memory.em_batalha = True
    nav = _navegador(monkeypatch, relogio, ctx,
                     montagens=[False, False, False, False, True])

    chamados = []
    nav.destravar_o_combate = lambda motivo: chamados.append(motivo) or False

    assert nav.garantir_montaria_para_andar("ir até o boss") is True
    assert len(chamados) == 3


# ---------------------------------------------------------------------------
# 6. a ligação existe de verdade na rotina
# ---------------------------------------------------------------------------

def test_a_rotina_liga_o_portao_no_combate():
    """Sem esta linha o destravamento existe e nunca é chamado."""
    import inspect

    from blazesbot.bot.bc import routine

    fonte = inspect.getsource(routine.BossRushRoutine.__init__)
    assert "self.nav.destravar_o_combate = self.combat.limpar_o_combate" in fonte
