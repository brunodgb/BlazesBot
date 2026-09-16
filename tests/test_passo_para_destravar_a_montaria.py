"""O jogo cancela a montaria sozinho — e andar destrava.

RELATO DO USUÁRIO, 06/09/2026: *"às vezes ao tentar ativar a montaria o jogo
ficava cancelando sozinho, e é claramente um bug do jogo. Se em 10 segundos
depois da primeira tentativa o bot não identificar que ativou a montaria, anda
6px — o fato de andar desbuga esse problema."*

O LOG CONFIRMA. 26 episódios de "Montaria confirmada depois de Ns insistindo",
mediana de 40 s. Separados por causa:

    23 casos  COM combate  -> já tratados por `limpar_o_combate`
     3 casos  SEM combate  -> 9 s, 13 s e 35 s

O de 35 s é o retrato do bug: `creubo` parado em (423, 53), dentro da cave, FORA
de combate, 35 segundos de tecla sem efeito — e então a montaria sobe sozinha,
sem nada ter mudado. Insistir mais não resolveria: a tecla já saía a cada
`INTERVALO_REMONTAR`. O que faltava era mudar o ESTADO do personagem.

E é por isso que o passo é minúsculo: 6 unidades contra ~17,6 de um clique de
minimapa e 7 de tolerância de waypoint. O passo cabe DENTRO da tolerância — ele
muda o estado sem tirar o personagem do ponto.
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot import navegacao


class _Relogio:
    def __init__(self):
        self.agora = 0.0


def _nav(monkeypatch, *, em_batalha=False, morto=False, posicao=(423, 53)):
    r = _Relogio()
    passos = []

    nav = object.__new__(navegacao.Navigator)
    nav._ultimo_passo_de_destrave = 0.0
    nav._direcao_do_passo_de_destrave = 0
    nav.destravar_o_combate = None
    nav.ctx = SimpleNamespace(
        log=SimpleNamespace(info=lambda *a, **k: None,
                            debug=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            error=lambda *a, **k: None),
        snapshot=lambda: SimpleNamespace(dead=morto),
        memory=SimpleNamespace(in_battle=lambda: em_batalha),
    )
    nav.position = lambda: posicao

    def _clicar(centro, raio, dx, dy):
        passos.append((centro, raio, round(dx, 3), round(dy, 3)))
        return True
    nav._clicar_offset_e_verificar = _clicar

    monkeypatch.setattr(navegacao.time, "time", lambda: r.agora)
    return nav, passos, r


# ---------------------------------------------------------------------------
# os números são os do usuário
# ---------------------------------------------------------------------------

def test_os_numeros_sao_os_do_usuario():
    assert navegacao.SEGUNDOS_ANTES_DE_CUTUCAR == 10.0
    assert navegacao.PASSO_PARA_DESTRAVAR == 6


def test_o_passo_cabe_dentro_da_tolerancia_do_waypoint():
    """Ele muda o estado sem tirar o personagem do ponto."""
    assert (navegacao.PASSO_PARA_DESTRAVAR
            < navegacao.DEFAULT_TOLERANCE * 3)


# ---------------------------------------------------------------------------
# O MESMO PASSO, AGORA TAMBÉM PREVENTIVO -- 16/09/2026
# ---------------------------------------------------------------------------
#
# Regra do usuário: *"o bug do jogo sempre que acontece ele atrapalha tudo, seja
# usar a montaria, seja se curar, seja fazer qualquer ação, então é melhor dar
# uma pequena caminhada assim que entra na cave para que o jogo desbugue antes
# de fazer qualquer ação"*.
#
# O passo de resgate continua igual; o que mudou é que ele ganhou um segundo
# chamador, na largada das DUAS caves.


def test_as_DUAS_caves_destravam_ao_entrar():
    """E antes de qualquer ação -- o preparo inteiro depende do jogo responder."""
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    for rotina, preparo in ((BossRushRoutine, "_do_curar"),
                            (HHRoutine, "_do_preparar_dentro")):
        metodo = getattr(rotina, preparo)
        arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
        chamadas = [(n.lineno, getattr(n.func, "attr", ""))
                    for n in ast.walk(arvore) if isinstance(n, ast.Call)]

        destrave = [ln for ln, nome in chamadas if nome == "destravar_ao_entrar"]
        # `garantir_montaria_para_andar` fica FORA da lista de propósito: na HH
        # ele também aparece no ramo de "retomando no meio da cave", que não é
        # uma ENTRADA e por isso não destrava -- ali o preparo inteiro é pulado.
        acoes = [ln for ln, nome in chamadas
                 if nome in ("curar_ao_entrar", "apply_buffs", "ensure_pet",
                             "feed_pet")]

        assert destrave, f"{rotina.__name__}.{preparo} não destrava ao entrar"
        assert acoes, f"{rotina.__name__}.{preparo} perdeu o preparo"
        assert min(destrave) < min(acoes), (
            f"{rotina.__name__} age antes de destravar")


def test_o_preventivo_NAO_espera_os_10s_do_resgate():
    """No resgate os 10 s evitam remédio no saudável; na entrada não há o que
    esperar -- o passo é a primeira coisa que acontece."""
    import inspect

    fonte = inspect.getsource(navegacao.Navigator.destravar_ao_entrar)
    assert "_ultimo_passo_de_destrave = 0.0" in fonte, (
        "a trava de cadência do resgate voltaria a engolir o passo da entrada")


def test_o_preventivo_REUSA_o_passo_do_resgate():
    """Mesma mecânica, mesmo número, mesma bússola -- duas cópias seriam duas
    chances de só uma ser corrigida."""
    import inspect

    fonte = inspect.getsource(navegacao.Navigator.destravar_ao_entrar)
    assert "_passo_para_destravar_a_montaria(" in fonte
    assert "_clicar_offset_e_verificar" not in fonte


# ---------------------------------------------------------------------------
# 1. quando anda
# ---------------------------------------------------------------------------

def test_anda_depois_dos_10s_fora_de_combate(monkeypatch):
    nav, passos, r = _nav(monkeypatch, em_batalha=False)
    r.agora = 100.0

    nav._diagnosticar_o_portao("a travessia até o altar", ciclo=2, gasto=11.0)

    assert len(passos) == 1
    centro, raio, dx, dy = passos[0]
    assert centro == (423, 53)
    assert raio == navegacao.PASSO_PARA_DESTRAVAR


def test_NAO_anda_antes_dos_10s(monkeypatch):
    """A montagem normal leva de 1 a 3 s. Andar aí seria remédio no saudável."""
    nav, passos, r = _nav(monkeypatch, em_batalha=False)
    r.agora = 100.0

    nav._diagnosticar_o_portao("atravessar a cave", ciclo=1, gasto=6.0)

    assert passos == []


def test_um_passo_por_intervalo_e_nao_um_por_ciclo(monkeypatch):
    """Passo demais tira o personagem do ponto — o remédio viraria o problema."""
    nav, passos, r = _nav(monkeypatch, em_batalha=False)
    r.agora = 100.0

    nav._diagnosticar_o_portao("x", ciclo=2, gasto=11.0)
    r.agora += 6.0                       # um ciclo do portão depois
    nav._diagnosticar_o_portao("x", ciclo=3, gasto=17.0)

    assert len(passos) == 1, "andou duas vezes dentro do mesmo intervalo"

    r.agora += 6.0                       # agora sim passou dos 10 s
    nav._diagnosticar_o_portao("x", ciclo=4, gasto=23.0)
    assert len(passos) == 2


def test_a_direcao_GIRA_a_cada_passo(monkeypatch):
    """Sempre para o mesmo lado, uma parede faria todo passo falhar calado."""
    nav, passos, r = _nav(monkeypatch, em_batalha=False)
    r.agora = 100.0

    for i in range(3):
        nav._diagnosticar_o_portao("x", ciclo=2 + i, gasto=11.0 + i)
        r.agora += navegacao.SEGUNDOS_ANTES_DE_CUTUCAR + 0.1

    direcoes = [(dx, dy) for _, _, dx, dy in passos]
    assert len(direcoes) == 3
    assert len(set(direcoes)) == 3, f"repetiu direção: {direcoes}"


# ---------------------------------------------------------------------------
# 2. quando NÃO anda -- e aqui é onde o cuidado mora
# ---------------------------------------------------------------------------

def test_EM_BATALHA_nao_anda(monkeypatch):
    """Andar em combate puxa mob, e não é o combate que trava a montaria de
    propósito — quem resolve ali é o golpe (`limpar_o_combate`)."""
    nav, passos, r = _nav(monkeypatch, em_batalha=True)
    r.agora = 100.0

    nav._diagnosticar_o_portao("x", ciclo=2, gasto=30.0)

    assert passos == []


def test_NAO_SEI_se_estou_em_batalha_nao_anda(monkeypatch):
    """`is False` e não `is not True`: andar tem custo, então exige confirmação
    POSITIVA. "Não sei" mantém o comportamento antigo, que é insistir na tecla.
    """
    nav, passos, r = _nav(monkeypatch, em_batalha=None)
    r.agora = 100.0

    nav._diagnosticar_o_portao("x", ciclo=2, gasto=30.0)

    assert passos == []


def test_sem_leitura_de_posicao_nao_anda(monkeypatch):
    """O offset do minimapa é calculado a partir da posição atual."""
    nav, passos, r = _nav(monkeypatch, em_batalha=False)
    nav.position = lambda: None
    r.agora = 100.0

    nav._diagnosticar_o_portao("x", ciclo=2, gasto=30.0)

    assert passos == []


def test_personagem_morto_levanta_antes_de_qualquer_passo(monkeypatch):
    """Cadáver não monta e não anda."""
    nav, passos, r = _nav(monkeypatch, em_batalha=False, morto=True)
    r.agora = 100.0

    with pytest.raises(navegacao.PersonagemMortoNoPortao):
        nav._diagnosticar_o_portao("x", ciclo=2, gasto=30.0)
    assert passos == []


def test_o_passo_e_conferido_e_nao_clique_no_escuro(monkeypatch):
    """`_clicar_offset_e_verificar` mede a posição antes e depois; o método
    devolve o que ela disse."""
    nav, _, r = _nav(monkeypatch, em_batalha=False)
    nav._clicar_offset_e_verificar = lambda *a: False
    r.agora = 100.0

    assert nav._passo_para_destravar_a_montaria("x", gasto=11.0) is False
