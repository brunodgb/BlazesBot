"""O bot não chega no waypoint do boss com alvo selecionado.

O cadáver do último Gun Witch fica selecionável por 7 a 13 segundos depois da
morte (medido; é o que a trava por identidade de `core/target_hybrid.MorteDoAlvo`
existe para absorver). Então `target_id != 0` na saída da fase dos guardas é o
caso NORMAL, não a exceção — e a mira segue grudada até o waypoint do boss.

O ESC não é invenção deste conserto: `_travar_no_alvo_proibido` já o usa desde
26/08/2026 para largar o Cemetery Guard. O que faltava era CONFERIR — aquele ESC
sai e ninguém lê o `target_id` depois.

O QUE ESTES TESTES TRAVAM, e é o lado perigoso:

    ESC SEM MIRA ABRE O MENU DO JOGO.

Então o disparo é condicionado à memória, e "não sei" (`id_do_alvo() is None`)
NÃO aperta nada — mesma regra de sempre: não saber não decide. Menu aberto na
frente do boss engole o clique na cena 3D
(`docs/decisoes/janela-na-frente.md`), o que é bem pior do que chegar lá com um
cadáver na mira.
"""
from blazesbot.bot import combate


class _Relogio:
    def __init__(self):
        self.agora = 0.0


class _FakeCtx:
    def __init__(self, relogio, leituras):
        """`leituras` é a sequência que `id_do_alvo()` devolve, uma por chamada.

        A última se repete para sempre — assim um teste que quer "nunca zera"
        não precisa contar quantas leituras o laço vai fazer.
        """
        self._relogio = relogio
        self._leituras = list(leituras)
        self.teclas = []
        self.log = self
        self.memory = self

    # -- memória ---------------------------------------------------------
    def id_do_alvo(self):
        return (self._leituras.pop(0) if len(self._leituras) > 1
                else self._leituras[0])

    # -- contexto --------------------------------------------------------
    def tick(self, seconds):
        self._relogio.agora += seconds

    def raise_if_stopped(self):
        pass

    def press(self, key, delay=0.0):
        self.teclas.append(key)

    # -- log -------------------------------------------------------------
    def info(self, *a, **kw):
        pass

    def debug(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass

    def error(self, *a, **kw):
        pass


def _motor(monkeypatch, leituras):
    relogio = _Relogio()
    ctx = _FakeCtx(relogio, leituras)
    motor = object.__new__(combate.CombatEngine)
    motor.ctx = ctx
    monkeypatch.setattr(combate.time, "time", lambda: relogio.agora)
    return motor, ctx, relogio


# ---------------------------------------------------------------------------
# os números
# ---------------------------------------------------------------------------

def test_os_numeros_do_protocolo():
    assert combate.TENTATIVAS_DE_LARGAR_A_MIRA == 2
    # Mesmo teto medido da ação de UI do cliente — ver `ui_do_jogo.py`.
    assert combate.TETO_PARA_A_MIRA_CAIR == 0.60


# ---------------------------------------------------------------------------
# 1. o lado perigoso: ESC que não pode sair
# ---------------------------------------------------------------------------

def test_sem_alvo_NAO_aperta_ESC(monkeypatch):
    """`target_id == 0` já é o estado desejado. ESC aqui abriria o menu."""
    motor, ctx, _ = _motor(monkeypatch, [0])

    assert motor.largar_a_mira("ir para o boss") is True
    assert ctx.teclas == []


def test_leitura_ilegivel_NAO_aperta_ESC(monkeypatch):
    """`None` é NÃO SEI, e não sei não decide nada.

    Errar para este lado custa um cadáver na mira — o estado de hoje. Errar
    para o outro custa um menu aberto na frente do boss.
    """
    motor, ctx, _ = _motor(monkeypatch, [None])

    assert motor.largar_a_mira("ir para o boss") is None
    assert ctx.teclas == []


def test_o_ESC_nao_e_martelado(monkeypatch):
    """Teto de 2. O ESC deste jogo também fecha janela aberta."""
    motor, ctx, _ = _motor(monkeypatch, [777])          # nunca zera

    assert motor.largar_a_mira("ir para o boss") is False
    assert ctx.teclas.count("esc") == combate.TENTATIVAS_DE_LARGAR_A_MIRA


# ---------------------------------------------------------------------------
# 2. o caso normal: cadáver na mira, ESC, confirmado pela memória
# ---------------------------------------------------------------------------

def test_alvo_grudado_sai_no_primeiro_ESC(monkeypatch):
    # antes=777 | _esperar_a_mira_cair lê 0 na primeira leitura
    motor, ctx, relogio = _motor(monkeypatch, [777, 0])

    assert motor.largar_a_mira("ir para o boss") is True
    assert ctx.teclas == ["esc"]
    # Sai no instante em que o id cai: não gastou o teto.
    assert relogio.agora < combate.TETO_PARA_A_MIRA_CAIR


def test_o_segundo_ESC_resolve_o_que_o_primeiro_nao(monkeypatch):
    # antes=777 | teto do 1º ESC todo em 777 | o 2º zera
    espera = int(combate.TETO_PARA_A_MIRA_CAIR
                 / combate.PASSO_DA_VIGIA_DE_COMBATE) + 3
    motor, ctx, _ = _motor(monkeypatch, [777] * espera + [0])

    assert motor.largar_a_mira("ir para o boss") is True
    assert ctx.teclas.count("esc") == 2


def test_a_espera_tem_teto(monkeypatch):
    """Id que não cai não gira o laço para sempre."""
    motor, _, relogio = _motor(monkeypatch, [777])

    motor.largar_a_mira("ir para o boss")
    teto_total = (combate.TETO_PARA_A_MIRA_CAIR
                  * combate.TENTATIVAS_DE_LARGAR_A_MIRA)
    assert relogio.agora <= teto_total + combate.PASSO_DA_VIGIA_DE_COMBATE * 2


def test_ilegivel_DEPOIS_do_ESC_para_de_insistir(monkeypatch):
    """A leitura caiu no meio: apertar de novo seria apertar no escuro."""
    motor, ctx, _ = _motor(monkeypatch, [777, None])

    assert motor.largar_a_mira("ir para o boss") is None
    assert ctx.teclas.count("esc") == 1


# ---------------------------------------------------------------------------
# 3. a chamada existe no ponto certo da transição
# ---------------------------------------------------------------------------

def test_a_rotina_larga_a_mira_ANTES_de_ir_para_o_boss():
    """Sem esta linha o protocolo existe e nunca roda.

    E a ORDEM importa: depois de `curar_antes_do_boss`, que pode SENTAR — um
    ESC no meio do descanso cancelaria o descanso.
    """
    import inspect

    from blazesbot.bot.bc import routine

    fonte = inspect.getsource(routine.BossRushRoutine._do_guardas)
    assert "largar_a_mira" in fonte, "a transição não larga a mira"
    # `rindex` no estado: `State.ATE_O_BOSS` aparece DUAS vezes na função — a
    # primeira é o atalho de `matar_guardas` desligado, que sai antes de haver
    # luta (e por isso antes de haver cadáver na mira). A transição de verdade
    # é a última.
    assert (fonte.index("curar_antes_do_boss")
            < fonte.index("largar_a_mira")
            < fonte.rindex("State.ATE_O_BOSS")), (
        "a ordem é: top-up -> largar a mira -> mudar de estado")


def test_o_desfecho_sujo_tambem_larga_a_mira():
    """A fase que NÃO fechou pela flag é a que mais tem chance de mira presa.

    A chamada fica fora do `if/else`, depois dos dois braços — este teste é o
    que impede alguém de empurrá-la para dentro do braço limpo.
    """
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.bc import routine

    arvore = ast.parse(textwrap.dedent(
        inspect.getsource(routine.BossRushRoutine._do_guardas)))

    dentro_de_if = {
        n.lineno
        for no in ast.walk(arvore) if isinstance(no, ast.If)
        for n in ast.walk(no)
        if isinstance(n, ast.Attribute) and n.attr == "largar_a_mira"
    }
    assert not dentro_de_if, (
        "largar_a_mira está dentro de um `if`: o desfecho que não fechou pela "
        "flag ficaria sem ela, e é justamente o que chega em combate")
