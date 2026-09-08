"""No waypoint dos Gun Witch, só o Cemetery Guard para o golpe.

Pedido do usuário em 26/08/2026, com uma run observada: *"tem que continuar
atacando até sair de batalha, só deve continuar se saiu de batalha; a única
trava é se der TAB no Cemetery Guard, que já existe. Eu vi acontecer de sobrar
1 Gun Witch e não estar mais atacando -- então rotaciona skill até sair de
batalha ou até identificar o Cemetery Guard como target."*

O defeito tinha duas portas, e as duas estão travadas aqui:

  1. o portão de nome dava `acabaram` para QUALQUER nome != `Gun Witch` e
     segurava o golpe até o fim da fase (`_alvo_proibido_encontrado` era só
     uma das formas de chegar lá);
  2. o teto de `TABS_NOS_GUARDAS` barrava a troca de alvo mesmo com a flag de
     combate ALTA e o alvo MORTO -- a rotação saía contra um cadáver.

Os interruptores são exercitados LIGADOS, como manda a regra da casa: o
caminho antigo continua no arquivo e voltar é trocar um `True` por `False`.
"""
from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot.bc import combat


class _Relogio:
    def __init__(self):
        self.agora = 0.0


class _FakeCtx:
    """O mínimo que `atacar_ate_sair_de_combate` toca."""

    def __init__(self, relogio):
        self._relogio = relogio
        self.teclas = []
        self.log = self
        self.settings = type("S", (), {
            "bc": type("B", (), {"attack_delay": 0.5})(),
            "keys": type("K", (), {"next_target": "tab"})(),
        })()
        # A CAVE QUE ESTÁ RODANDO. Os motores compartilhados leem número
        # de cave por aqui desde 03/09/2026 (`ctx.cave`), em vez de
        # `settings.bc` direto -- era o que fazia a HH rodar com os
        # números do BC. Aqui aponta para o `bc` deste dublê, que é a
        # cave que estes testes exercitam.
        self.cave = self.settings.bc
        # O TAB PASSOU A SER CONFIRMADO PELA TROCA DO ID (06/09/2026,
        # `core/target_hybrid.esperar_o_alvo_trocar`), então `_trocar_de_alvo`
        # lê a memória antes e depois de apertar. O dublê modela o jogo: cada
        # TAB entrega um alvo diferente. Sem isso a troca nunca confirmaria e
        # cada TAB pagaria o teto inteiro.
        self.memory = self
        self._id = 1

    def id_do_alvo(self):
        return self._id

    # -- contexto --------------------------------------------------------
    def tick(self, seconds):
        self._relogio.agora += seconds

    def raise_if_stopped(self):
        pass

    def press(self, key, delay=0.0):
        self.teclas.append(key)
        if key == self.settings.keys.next_target:
            # O TAB entrega outro alvo -- e e a TROCA DO ID que
            # `_trocar_de_alvo` espera para dar a tecla por confirmada.
            self._id += 1
        elif key == "esc":
            # ESC LARGA A MIRA, e o dublê precisa dizer isso desde 07/09/2026:
            # `_travar_no_alvo_proibido` passou a apertar por `largar_a_mira`,
            # que LÊ o `target_id` e insiste se ele não zerou. Um dublê onde o
            # id nunca cai faria a trava parecer que aperta duas vezes.
            self._id = 0

    def snapshot(self):
        return type("E", (), {"dead": False, "hp_pct": 100.0, "max_hp": 100,
                              "sitting": False, "position": (0, 0),
                              "location": "covil"})()

    # -- log -------------------------------------------------------------
    def info(self, *a, **kw):
        pass

    def debug(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass

    def error(self, *a, **kw):
        pass


def _motor(monkeypatch, relogio, *, flag, nomes, morreu=False):
    """Motor de combate com as leituras do jogo trocadas por funções."""
    ctx = _FakeCtx(relogio)
    motor = object.__new__(combat.CombatEngine)
    motor.ctx = ctx
    motor._ultimos_nomes_do_alvo = []

    monkeypatch.setattr(motor_de_combate.time, "time", lambda: relogio.agora)
    monkeypatch.setattr(combat.CombatEngine, "_ler_flag_de_combate",
                        lambda self: flag(relogio.agora))
    monkeypatch.setattr(combat.CombatEngine, "maintain",
                        lambda self, state, em_luta=False: None)
    monkeypatch.setattr(combat.CombatEngine, "_proxima_skill",
                        lambda self, state, usar_aoe: "1")
    monkeypatch.setattr(combat.CombatEngine, "_alvo_morreu",
                        lambda self: morreu)

    def _veredito(self, esperado):
        self._ultimos_nomes_do_alvo = list(nomes)
        if any(esperado.lower() in n.lower() for n in nomes):
            return "bate"
        return "acabaram" if nomes else "ilegivel"
    monkeypatch.setattr(combat.CombatEngine, "_veredito_do_alvo", _veredito)

    return motor, ctx


# ---------------------------------------------------------------------------
# os interruptores
# ---------------------------------------------------------------------------

def test_os_interruptores_estao_ligados():
    assert motor_de_combate.SO_O_ALVO_PROIBIDO_PARA_O_GOLPE is True
    assert motor_de_combate.TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS is True
    assert combat.NOME_DO_CEMETERY_GUARD == "Cemetery Guard"


# ---------------------------------------------------------------------------
# 1. nome que não é o Cemetery Guard NÃO para o golpe
# ---------------------------------------------------------------------------

def test_nome_estranho_nao_para_o_golpe(monkeypatch):
    """Era esta porta que deixava um Gun Witch vivo com o bot parado."""
    relogio = _Relogio()
    motor, ctx = _motor(monkeypatch, relogio,
                        flag=lambda t: t < 10.0,
                        nomes=["Evil Centipede"])

    fim = motor.atacar_ate_sair_de_combate(
        "guardas", usar_aoe=True, limite=40.0,
        alvo_esperado=combat.NOME_DOS_GUARDAS)

    assert fim.saiu_de_combate is True
    # Bateu o tempo todo em que esteve em combate: ~10 s a cada 0,5 s.
    assert ctx.teclas.count("1") >= 15
    assert "esc" not in ctx.teclas


# ---------------------------------------------------------------------------
# 2. o Cemetery Guard, e SÓ ele, para o golpe -- e larga a mira no ESC
# ---------------------------------------------------------------------------

def test_cemetery_guard_para_o_golpe_e_aperta_esc_uma_vez(monkeypatch):
    relogio = _Relogio()
    motor, ctx = _motor(monkeypatch, relogio,
                        flag=lambda t: t < 10.0,
                        nomes=["Cemetery Guard"])

    fim = motor.atacar_ate_sair_de_combate(
        "guardas", usar_aoe=True, limite=40.0,
        alvo_esperado=combat.NOME_DOS_GUARDAS)

    # A fase NÃO encerra na trava: quem encerra é a saída de combate.
    assert fim.saiu_de_combate is True
    # ESC UMA vez -- repetido, ele fecha janela do jogo que ninguém pediu.
    assert ctx.teclas.count("esc") == 1
    # E depois do ESC não sai mais skill: o primeiro golpe é o da entrada em
    # combate, que acontece antes de qualquer leitura de nome.
    assert ctx.teclas.index("esc") == len(ctx.teclas) - 1
    assert ctx.teclas.count("1") <= 1


def test_a_trava_do_cemetery_guard_e_uma_porta_so(monkeypatch):
    """Tela e memória chegam no MESMO `_travar_no_alvo_proibido`."""
    relogio = _Relogio()
    motor, ctx = _motor(monkeypatch, relogio, flag=lambda t: True, nomes=[])

    motor._travar_no_alvo_proibido("Cemetery Guard", "memória")
    motor._travar_no_alvo_proibido("tela, match em (10, 20)", "após o TAB 2")

    assert motor._alvo_proibido_encontrado is True
    assert ctx.teclas.count("esc") == 1


# ---------------------------------------------------------------------------
# 3. o teto de TAB não barra a troca com a flag alta e o alvo morto
# ---------------------------------------------------------------------------

def test_tab_continua_depois_do_teto_enquanto_a_flag_estiver_alta(monkeypatch):
    relogio = _Relogio()
    motor, ctx = _motor(monkeypatch, relogio,
                        flag=lambda t: True, nomes=[combat.NOME_DOS_GUARDAS],
                        morreu=True)

    fim = motor.atacar_ate_sair_de_combate(
        "guardas", usar_aoe=True, limite=20.0,
        tabs_ao_morrer=motor_de_combate.TABS_NOS_GUARDAS,
        alvo_esperado=combat.NOME_DOS_GUARDAS)

    # A flag nunca baixou: a fase estoura o prazo e devolve DERROTA -- o que
    # não pode acontecer é o bot ter parado de trocar de alvo no teto.
    assert fim.saiu_de_combate is False
    assert ctx.teclas.count("tab") > motor_de_combate.TABS_NOS_GUARDAS


def test_flag_ilegivel_nao_autoriza_tab_alem_do_teto(monkeypatch):
    """`None` é NÃO SEI, e não sei nunca gastou TAB nesta casa.

    O QUE ESTE TESTE MEDE, e a distinção importa: TAB gasto DEPOIS que a flag
    fica ilegível. Com a flag legivelmente ALTA (t < 3 s) o orçamento é
    ilimitado de propósito -- é o `TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS`, que
    existe justamente para o teto não barrar a troca com a luta em curso.

    Ele conferia o TOTAL até 06/09/2026, e passava por acidente: quem segurava
    a contagem era a carência de 2,4 s aplicada a cada TAB, não o orçamento.
    Com a carência valendo só quando a troca NÃO se confirma, o total durante a
    flag alta subiu (12 no dublê, que tem `morreu=True` preso) -- e isso é o
    comportamento pedido, não o defeito que este teste vigia.
    """
    relogio = _Relogio()
    motor, ctx = _motor(monkeypatch, relogio,
                        flag=lambda t: True if t < 3.0 else None,
                        nomes=[combat.NOME_DOS_GUARDAS], morreu=True)

    marca = []
    press_original = ctx.press

    def _press(key, delay=0.0):
        press_original(key, delay)
        if key == "tab":
            marca.append(relogio.agora)
    ctx.press = _press

    motor.atacar_ate_sair_de_combate(
        "guardas", usar_aoe=True, limite=20.0,
        tabs_ao_morrer=motor_de_combate.TABS_NOS_GUARDAS,
        alvo_esperado=combat.NOME_DOS_GUARDAS)

    depois_de_ilegivel = [t for t in marca if t >= 3.0]
    assert not depois_de_ilegivel, (
        f"gastou TAB com a flag ilegível, em t={depois_de_ilegivel}")
