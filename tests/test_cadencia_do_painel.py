"""O PAINEL DE ARREDORES NÃO PISCA.

Relato do usuário em 25/08/2026:

    *"tem vezes que fica abrindo, filtrando, clicando para dar o auto path, aí
     fechando e repetindo o processo tudo bem rápido, o que não chega a
     necessariamente atrapalhar, mas pode ser MAL VISTO pelo usuário final"*

`buscar_npc` retenta até 3 vezes e cada volta refaz o ciclo inteiro. Três
quedas em sequência abrem e fecham o painel três vezes em poucos segundos.

O que este arquivo trava é que a espera é o **RESTO** do intervalo, não o
intervalo. Se ela fosse o intervalo cheio, toda run pagaria 6 segundos parados
(três usos) por um problema que só aparece na repetição.
"""
from types import SimpleNamespace

from blazesbot.bot import ui_do_jogo
from blazesbot.bot.bc import ui_service


def _servico(agora):
    """Um `UIService` sem construtor, com relógio controlado."""
    s = ui_service.UIService.__new__(ui_service.UIService)
    s.esperas: list[float] = []
    s.ctx = SimpleNamespace(
        tick=lambda seg: s.esperas.append(seg),
        log=SimpleNamespace(debug=lambda *a, **k: None,
                            info=lambda *a, **k: None,
                            warning=lambda *a, **k: None))
    s._painel_usado_em = 0.0
    return s


def test_o_primeiro_uso_NAO_espera(monkeypatch):
    """A run não pode começar pagando por um problema que ainda não houve."""
    monkeypatch.setattr(ui_do_jogo.time, "time", lambda: 1000.0)
    s = _servico(1000.0)

    s._respeitar_a_cadencia_do_painel()

    assert s.esperas == []
    assert s._painel_usado_em == 1000.0


def test_reabrir_LOGO_em_seguida_espera_o_RESTO(monkeypatch):
    """Foi o que o usuário viu: três aberturas em poucos segundos."""
    relogio = [1000.0]
    monkeypatch.setattr(ui_do_jogo.time, "time", lambda: relogio[0])
    monkeypatch.setattr(ui_do_jogo, "INTERVALO_ENTRE_USOS_DO_PAINEL", 2.0)

    s = _servico(1000.0)
    s._respeitar_a_cadencia_do_painel()          # primeiro uso

    relogio[0] = 1000.5                          # meio segundo depois
    s._respeitar_a_cadencia_do_painel()

    assert len(s.esperas) == 1
    assert abs(s.esperas[0] - 1.5) < 1e-9, s.esperas


def test_depois_de_MUITO_tempo_nao_espera_nada(monkeypatch):
    """Entre um uso e o seguinte costumam passar MINUTOS -- Fay, entrada da
    cave e vendedor são três usos por run. O caminho feliz não paga nada."""
    relogio = [1000.0]
    monkeypatch.setattr(ui_do_jogo.time, "time", lambda: relogio[0])
    monkeypatch.setattr(ui_do_jogo, "INTERVALO_ENTRE_USOS_DO_PAINEL", 2.0)

    s = _servico(1000.0)
    s._respeitar_a_cadencia_do_painel()

    relogio[0] = 1300.0                          # cinco minutos depois
    s._respeitar_a_cadencia_do_painel()

    assert s.esperas == []


def test_a_espera_usa_TICK_e_nao_sleep():
    """`time.sleep` faria o botão Parar parecer travado durante a espera.

    É a mesma regra do resto do bot: a parada acorda quem espera.
    """
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(
        ui_service.UIService._respeitar_a_cadencia_do_painel))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert "tick" in chamadas
    assert "sleep" not in chamadas


def test_abrir_surroundings_RESPEITA_a_cadencia():
    """A cadência tem que estar no caminho de quem abre o painel -- senão ela
    existe e não é usada."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(
        ui_service.UIService.abrir_surroundings))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}

    assert "_respeitar_a_cadencia_do_painel" in chamadas
