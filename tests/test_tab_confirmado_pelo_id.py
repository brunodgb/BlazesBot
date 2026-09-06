"""O TAB da BC é confirmado pela TROCA DO ID, não por sleep cego.

O DEFEITO, MEDIDO EM 06/09/2026. O usuário relatou "stuck on corpse" no waypoint
das Gun Witch: *"mata o mob mas não identifica a morte na hora, atrasando o
TAB"*. Duas hipóteses vieram junto — o ponteiro de HP congelaria no último valor,
ou a morte desalocaria a instância. **As duas estão reprovadas por medição.**

Bancada de ponteiros (`D:\\Versoes do Bot\\Teste-Ponteiros\\RESULTADOS.md`,
01/09/2026, 600 amostras por conta, 2 contas, bot rodando):

  * quando o alvo é reconhecido, nome e vida vêm **321/321 e 361/361**;
  * o oráculo varreu 912 MB de heap nos 6 casos de falha da rota normal: o
    objeto **ainda existia em 6 de 6**, com `hp=0/100` legível no cadáver, zero
    desalocados — *"Não é desalocação: é rota faltando"*;
  * frase literal do relatório: *"a detecção de MORTE sempre funcionou. O erro
    vive só no meio da luta."*

O atraso era outro, e o log de produção mostra onde. Da linha `ALVO MORREU` até
a linha do TAB, 274 mortes:

    min 635 ms | mediana 760 ms | p90 847 ms | max 2013 ms
    204 das 274 (74%) entre 0,70 e 0,85 s

`press('tab', 0.15) + tick(0.6) = 750 ms`. A mediana **é** o sleep. Zero de
detecção — e nesses 750 ms o laço inteiro fica parado, nenhuma skill sai. Visto
de fora, é exatamente "preso no cadáver".

O APP já resolvia isso perguntando de 10 em 10 ms; o CLAUDE.md listava a peça
como promoção devida, em duplicata. Ela subiu para
`core/target_hybrid.esperar_o_alvo_trocar`.
"""
import pytest

from blazesbot.bot import combate
from blazesbot.core import target_hybrid as th

# ===========================================================================
# A PEÇA PROMOVIDA
# ===========================================================================

class _Relogio:
    def __init__(self):
        self.agora = 0.0

    def dormir(self, s):
        self.agora += s


@pytest.fixture
def relogio(monkeypatch):
    r = _Relogio()
    monkeypatch.setattr(th.time, "time", lambda: r.agora)
    return r


def test_os_numeros_da_peca():
    assert th.TETO_PARA_O_ALVO_TROCAR == 0.35
    assert th.PASSO_DA_CONFIRMACAO_DO_TAB == 0.01


def test_devolve_no_instante_em_que_o_id_muda(relogio):
    """O ponto todo: não espera o teto, espera o jogo."""
    leituras = iter([7, 7, 7, 99])
    novo = th.esperar_o_alvo_trocar(lambda: next(leituras), 7,
                                    dormir=relogio.dormir)
    assert novo == 99
    # Três passos de 10 ms, não 350 ms de teto nem 600 ms de sleep.
    assert relogio.agora == pytest.approx(0.03)


def test_id_igual_ate_o_teto_devolve_None(relogio):
    novo = th.esperar_o_alvo_trocar(lambda: 7, 7, dormir=relogio.dormir)
    assert novo is None
    assert relogio.agora >= th.TETO_PARA_O_ALVO_TROCAR


def test_leitura_ilegivel_NAO_conta_como_troca(relogio):
    """`None` é NÃO SEI. Dar por confirmado o que não foi lido é o erro."""
    leituras = iter([None, None, None, 99])
    novo = th.esperar_o_alvo_trocar(lambda: next(leituras), 7,
                                    dormir=relogio.dormir)
    assert novo == 99


def test_zero_E_troca_legitima(relogio):
    """O TAB pode ciclar para "nada selecionado" — isso é troca, não falha."""
    leituras = iter([7, 0])
    assert th.esperar_o_alvo_trocar(lambda: next(leituras), 7,
                                    dormir=relogio.dormir) == 0


def test_o_parar_do_usuario_atravessa(relogio):
    novo = th.esperar_o_alvo_trocar(lambda: 7, 7, dormir=relogio.dormir,
                                    continuar=lambda: False)
    assert novo is None
    assert relogio.agora == 0.0


# ===========================================================================
# O TAB DA BC
# ===========================================================================

class _FakeCtx:
    def __init__(self, relogio, ids):
        self._relogio = relogio
        self._ids = list(ids)
        self.teclas = []
        self.log = self
        self.memory = self
        self.settings = type("S", (), {
            "keys": type("K", (), {"next_target": "tab"})()})()

    def id_do_alvo(self):
        return self._ids.pop(0) if len(self._ids) > 1 else self._ids[0]

    def press(self, key, delay=0.0):
        self.teclas.append(key)
        self._relogio.agora += delay

    def tick(self, s):
        self._relogio.agora += s

    def raise_if_stopped(self):
        pass

    def info(self, *a, **kw):
        pass

    def debug(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass

    def error(self, *a, **kw):
        pass


def _motor(monkeypatch, ids):
    r = _Relogio()
    ctx = _FakeCtx(r, ids)
    m = object.__new__(combate.CombatEngine)
    m.ctx = ctx
    m._ultima_leitura_do_alvo = "sobra da leitura anterior"
    monkeypatch.setattr(th.time, "time", lambda: r.agora)
    return m, ctx, r


def test_o_TAB_confirmado_custa_dezenas_de_ms_e_nao_750(monkeypatch):
    """A medição que motivou o conserto, virada em teste.

    Antes: `press(0.15)` + `tick(0.6)` = 750 ms fixos, sempre.
    Agora: 150 ms de tecla + o tempo REAL até o jogo trocar o id.
    """
    m, ctx, r = _motor(monkeypatch, [7, 7, 99])

    assert m._trocar_de_alvo() is True
    assert ctx.teclas == ["tab"]
    # 150 ms de `press` + um passo de 10 ms. O sleep de 600 ms sumiu.
    assert r.agora == pytest.approx(0.16)
    assert r.agora < 0.75, "voltou a espera cega"


def test_a_leitura_anterior_morre_com_o_alvo_anterior(monkeypatch):
    m, _, _ = _motor(monkeypatch, [7, 99])
    m._trocar_de_alvo()
    assert m._ultima_leitura_do_alvo is None


def test_id_que_nao_troca_devolve_False_sem_martelar(monkeypatch):
    """Uma tecla só. Insistir é decisão de quem chama, não daqui."""
    m, ctx, r = _motor(monkeypatch, [7])

    assert m._trocar_de_alvo() is False
    assert ctx.teclas.count("tab") == 1
    assert r.agora <= 0.15 + th.TETO_PARA_O_ALVO_TROCAR + 0.02


# ===========================================================================
# A CARÊNCIA -- o que de fato produzia "preso no cadáver"
# ===========================================================================

def test_a_carencia_so_vale_quando_a_troca_NAO_foi_confirmada():
    """`CARENCIA_APOS_O_TAB = 2,4 s` era aplicada SEMPRE.

    Ela nasceu de um problema de TELA ("o quadro do alvo novo leva um instante
    para desenhar"). Com a leitura vindo da MEMÓRIA e o id JÁ confirmado como
    diferente, esperar 2,4 s para reler é 2,4 s de cadáver na mira sem ninguém
    perguntar — o "stuck on corpse" relatado.

    E ela nunca protegeu de bater no cadáver: não olhar não é proteger. Quem
    protege é a trava por IDENTIDADE de `MorteDoAlvo`.
    """
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(
        combate.CombatEngine.atacar_ate_sair_de_combate))
    arvore = ast.parse(fonte)

    # A atribuição de `proxima_leitura` que usa a carência tem de ser
    # CONDICIONAL ao resultado da troca.
    condicionais = [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Assign)
        and any(isinstance(a, ast.Name) and a.id == "proxima_leitura"
                for a in no.targets)
        # O `if/else` pode estar aninhado numa soma (`agora + (a if x else b)`),
        # então a busca é pelo IfExp em qualquer profundidade do valor.
        and any(isinstance(n, ast.IfExp) for n in ast.walk(no.value))
        and "CARENCIA_APOS_O_TAB" in ast.dump(no.value)
        and "CADENCIA_DA_LEITURA_DO_ALVO" in ast.dump(no.value)
    ]
    assert condicionais, (
        "a carência voltou a ser incondicional: com a troca do id já "
        "confirmada, 2,4 s sem reler é cadáver na mira")


def test_a_constante_da_carencia_continua_existindo():
    """Ela NÃO foi apagada — vale quando a troca não foi confirmada."""
    assert combate.CARENCIA_APOS_O_TAB == 2.4


# ===========================================================================
# A PROMOÇÃO -- fim da duplicata
# ===========================================================================

def test_o_APP_delega_para_a_peca_do_core():
    """O CLAUDE.md listava esta função como promoção devida, em duplicata."""
    import inspect

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = inspect.getsource(ExecutorDeMacro._esperar_o_alvo_trocar)
    assert "target_hybrid.esperar_o_alvo_trocar" in fonte
    assert "while time.time()" not in fonte, "a duplicata voltou"


def test_o_APP_mantem_o_proprio_teto():
    """O que NÃO subiu: a POLÍTICA. O teto do APP é do APP.

    Ele entra no orçamento de tentativas do APP
    (`TENTATIVAS_DE_TAB * SEGUNDOS_PARA_O_ALVO_APARECER`) e é monkeypatchado
    pelos testes de lá — é decisão daquele ecossistema, não do core, mesmo que
    hoje os dois valham 0,35.
    """
    import inspect

    from blazesbot.bot.app import executor

    fonte = inspect.getsource(executor.ExecutorDeMacro._esperar_o_alvo_trocar)
    assert "teto=SEGUNDOS_PARA_O_ALVO_APARECER" in fonte, (
        "o APP passou a usar o teto do core; o orçamento de tentativas dele "
        "deixaria de mandar no próprio tempo")


def test_o_PASSO_mora_num_lugar_so():
    """`PASSO_DA_CONFIRMACAO_DO_TAB` é a MESMA pergunta nos dois — um valor só.

    Ao contrário do teto, este não é política: é quanto custa perguntar, e
    custa o mesmo em qualquer ecossistema. Duas cópias de 0,01 divergiriam em
    silêncio, e a que ficasse para trás perguntaria devagar.
    """
    from blazesbot.bot.app import executor

    assert (executor.PASSO_DA_CONFIRMACAO_DO_TAB
            is th.PASSO_DA_CONFIRMACAO_DO_TAB)


def test_a_espera_da_BC_responde_ao_Parar(monkeypatch):
    """`ctx.tick` e não `time.sleep`: é a fatia que o Parar atravessa."""
    import inspect

    fonte = inspect.getsource(combate.CombatEngine._trocar_de_alvo)
    assert "dormir=ctx.tick" in fonte, (
        "com `time.sleep` o Parar do usuário não corta a espera do TAB")


def test_a_peca_promovida_recebe_PECAS_e_nao_contexto():
    """Mesmo desenho de `watchdog.avaliar_saude`: o APP a chama sem depender
    do farm, e a BC sem depender do executor."""
    import inspect

    parametros = list(inspect.signature(th.esperar_o_alvo_trocar).parameters)
    assert parametros[:2] == ["ler_id", "id_antes"]
    assert "ctx" not in parametros
