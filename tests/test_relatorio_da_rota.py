"""O relatório da rota conta cada coisa no par certo -- nas duas caves."""
from datetime import datetime, timedelta

from blazesbot.tools import relatorio_da_rota as rel

# Um trecho de mentira; os testes do fim usam os de verdade.
TRECHOS = {"Teste": [(80, 42), (107, 47), (124, 49), (141, 75)]}
T0 = datetime(2026, 9, 26, 10, 0, 0)


def _r(segundos, msg, conta="a"):
    return {"ts": T0 + timedelta(seconds=segundos), "conta": conta, "msg": msg}


def _chegada(n, total, pos, segundos=2.0, extra=""):
    return f"waypoint {n}/{total} alcançado em {segundos:.1f}s{extra} | posição {pos}"


def test_passagem_tempo_e_travada_no_par_certo():
    registros = [
        _r(0, _chegada(1, 4, (79, 41), 1.5)),
        _r(3, _chegada(2, 4, (106, 46), 4.0)),
        _r(9, "Navegação travada em (110, 47). Vizinhos imediatos: ..."),
        _r(12, "Voltei do waypoint 3 para perto do 2 (posição (107, 47))."),
        _r(20, _chegada(3, 4, (124, 50), 11.0)),
    ]
    pares, sem_par = rel.analisar(registros, TRECHOS)

    assert pares[("Teste", -1, 0)]["passagens"] == 1
    assert pares[("Teste", 0, 1)]["tempos"] == [4.0]
    assert pares[("Teste", 1, 2)]["travada"] == 1
    assert pares[("Teste", 1, 2)]["rollback"] == 1
    assert pares[("Teste", 1, 2)]["tempos"] == [11.0]
    assert sem_par == 0


def test_indice_que_nao_bate_com_a_coordenada_NAO_conta():
    """O BC tem pontos a menos de 12 unidades dos da HH: sem conferir o índice
    E o tamanho do trecho, a rota do BC entraria no relatório da HH."""
    registros = [_r(0, _chegada(1, 58, (79, 41))),     # tamanho de outro trecho
                 _r(1, _chegada(3, 4, (79, 41)))]      # índice de outro ponto
    pares, _ = rel.analisar(registros, TRECHOS)
    assert pares == {}


def test_goto_de_um_ponto_nao_mexe_no_par_da_conta():
    """As manobras de destravamento andam por `goto` (1/1): o tempo esgotado
    DELAS não é problema da rota."""
    registros = [
        _r(0, _chegada(2, 4, (107, 47))),
        _r(1, _chegada(1, 1, (124, 49))),
        _r(5, "Tempo esgotado no trajeto: cheguei ao waypoint 0 de 1 em 4s"),
        _r(9, "Tempo esgotado no trajeto: cheguei ao waypoint 2 de 4 em 300s"),
    ]
    pares, _ = rel.analisar(registros, TRECHOS)
    assert pares[("Teste", 1, 2)]["esgotado"] == 1


def test_sem_progresso_conta_so_a_PRIMEIRA_linha_do_episodio():
    alvo = "sem progresso indo para (124, 49) (waypoint 3/4, distância 9) — relançando ({})"
    registros = [_r(0, alvo.format(1)), _r(1, alvo.format(2)), _r(2, alvo.format(3))]
    pares, _ = rel.analisar(registros, TRECHOS)
    assert pares[("Teste", 1, 2)]["sem_progresso"] == 1


def test_travada_sem_chegada_recente_nao_e_atribuida():
    registros = [_r(0, _chegada(2, 4, (107, 47))),
                 _r(rel.VALIDADE_DO_PAR + 1, "Navegação travada em (1, 1).")]
    pares, sem_par = rel.analisar(registros, TRECHOS)
    assert sem_par == 1
    assert ("Teste", 1, 2) not in pares


def test_chegada_que_atravessou_waypoints_fica_fora_do_tempo():
    pares, _ = rel.analisar(
        [_r(0, _chegada(3, 4, (124, 49), 9.0, " (+1 atravessado(s))"))], TRECHOS)
    assert pares[("Teste", 1, 2)]["passagens"] == 1
    assert pares[("Teste", 1, 2)]["tempos"] == []


def test_os_trechos_reais_das_DUAS_caves_carregam():
    trechos = rel.trechos_das_caves()
    assert sum(t.startswith("HH ") for t in trechos) == 4
    assert {"BC altar", "BC boss"} <= set(trechos)
    assert all(len(p) >= 2 for p in trechos.values())


def test_o_tempo_perdido_vai_para_a_causa_MAIS_GRAVE_da_passagem():
    registros = [_r(0, _chegada(1, 4, (80, 42)))]
    for i in range(5):                                   # cinco passagens normais
        registros.append(_r(10 + i, _chegada(2, 4, (107, 47), 2.0)))
    registros += [_r(30, "sem progresso indo para (107, 47) (waypoint 2/4, "
                         "distância 20) — relançando (1)"),
                  _r(31, "CONGELADO em (90, 44) há 15s tentando andar"),
                  _r(50, _chegada(2, 4, (107, 47), 20.0))]
    pares, _ = rel.analisar(registros, TRECHOS)

    perdido = rel.tempo_perdido(pares[("Teste", 0, 1)])
    assert perdido == {"congelado": 18.0}               # 20 s contra a mediana de 2


def test_o_BC_casa_pelo_trecho_dele():
    from blazesbot.bot.bc import mapa_bc

    trechos = rel.trechos_das_caves()
    x, y = mapa_bc.CAMINHO_ATE_O_ALTAR[4].pos
    total = len(mapa_bc.CAMINHO_ATE_O_ALTAR)
    pares, _ = rel.analisar([_r(0, _chegada(5, total, (x, y)))], trechos)
    assert ("BC altar", 3, 4) in pares


def test_pontos_quentes_separa_as_caves_pelo_NOME_e_ignora_as_contas_de_teste():
    from blazesbot.bot.hh import mapa_hh

    x, y = mapa_hh.TODOS_OS_WAYPOINTS[0].pos
    linhas = [
        f"2026-09-26 10:00:00 | creubo | ROLLBACK | w 2 -> 1 | pos=({x}, {y}) "
        f"| local='Happiness Hall Visitor Room'",
        f"2026-09-26 10:00:01 | simulacao | TRAVADO-NA-CAVE | v | pos=({x}, {y}) "
        f"| local='Secret Altar'",
        "2026-09-20 10:00:01 | creubo | ROLLBACK | w | pos=(1, 1) | local='Stone City'",
    ]
    quentes = rel.pontos_quentes(linhas)
    assert quentes["HH"][(0, (x, y))] == {"rollback": 1}
    assert not quentes["BC"]


def test_o_desde_corta_o_periodo(tmp_path):
    import json

    antigo = json.dumps({"ts": "2026-09-20 10:00:00.000", "conta": "a",
                         "msg": _chegada(1, 4, (80, 42))}, ensure_ascii=False)
    novo = antigo.replace("2026-09-20", "2026-09-26")
    (tmp_path / "blazes-dev.jsonl").write_text(antigo + "\n" + novo + "\n",
                                                encoding="utf-8")
    registros = list(rel.ler_registros(tmp_path, datetime(2026, 9, 25)))
    assert [r["ts"].day for r in registros] == [26]
