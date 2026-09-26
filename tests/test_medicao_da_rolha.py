"""A medição da ROLHA da venda (25/09/2026) -- só registra, não decide nada.

O que se trava: a linha que a venda grava é a que `tools/medir_a_rolha.py` lê
(produtor e consumidor JUNTOS), o juiz reconhece o erro caro (falso positivo),
e a medição desligada não custa captura nenhuma. Porquê: `leitura_do_slot.MEDIR_A_ROLHA`.
"""
from __future__ import annotations

import numpy as np

from blazesbot.bot import leitura_do_slot
from blazesbot.bot.leitura_do_slot import LeituraDoSlot
from blazesbot.tools import medir_a_rolha


class _Log:
    def __init__(self):
        self.linhas: list[str] = []

    def info(self, msg, *args):
        self.linhas.append(msg % args if args else msg)

    debug = warning = error = info



def test_a_diferenca_do_slot_e_zero_quando_nada_muda():
    a = np.full((24, 24), 40, dtype=np.uint8)
    b = a.copy()
    b[:12] = 200
    assert LeituraDoSlot.diferenca_do_slot(a, a.copy()) == 0.0
    assert LeituraDoSlot.diferenca_do_slot(a, b) > 50
    assert LeituraDoSlot.diferenca_do_slot(None, a) is None
    assert LeituraDoSlot.diferenca_do_slot(a, np.zeros((10, 10), np.uint8)) is None


def test_a_linha_que_a_venda_grava_e_a_que_o_juiz_le(monkeypatch):
    """Produtor e consumidor JUNTOS: sem isto, meses de medição viram lixo."""
    monkeypatch.setattr(leitura_do_slot, "MEDIR_A_ROLHA", True)
    log = _Log()

    class _Venda(LeituraDoSlot):
        ctx = type("Ctx", (), {"log": log,
                               "memory": type("M", (), {"bag_count": staticmethod(lambda: 50)})()})()

    cheio = np.full((24, 24), 90, np.uint8)
    outro = np.full((24, 24), 10, np.uint8)
    recortes = [cheio, outro, cheio, cheio, cheio]      # muda, muda, parou, parou
    _Venda()._registrar_a_rolha(2, recortes, antes=52, cliques=4)

    (linha,) = log.linhas
    m = medir_a_rolha.LINHA.search(linha)
    assert m, linha
    assert m.group(1) == "2" and m.group(2) == "4" and m.group(3) == "2"


def test_medicao_desligada_nao_paga_a_captura(monkeypatch):
    monkeypatch.setattr(leitura_do_slot, "MEDIR_A_ROLHA", False)

    class _Venda(LeituraDoSlot):
        def _quadro(self):
            raise AssertionError("capturou com a medição desligada")

    assert _Venda()._medir_o_slot((10, 10)) is None


def test_a_medicao_nunca_derruba_a_venda(monkeypatch):
    """Quadro que não é imagem (o dublê devolve `object()`): None, sem exceção."""
    monkeypatch.setattr(leitura_do_slot, "MEDIR_A_ROLHA", True)

    class _Venda(LeituraDoSlot):
        def _quadro(self):
            return object()

    assert _Venda()._medir_o_slot((10, 10)) is None


def _passada(difs, vendidos):
    return {"passada": 1, "cliques": len(difs), "vendidos": vendidos, "difs": difs}


def test_o_juiz_separa_os_cinco_desfechos():
    parou_no_3 = [30.0, 30.0, 0.2, 0.2, 0.2]
    c = medir_a_rolha.julgar([
        _passada(parou_no_3, 2),                 # rolha no clique 3, vendeu 2
        _passada(parou_no_3, 4),                 # vendeu MAIS: parada cedo demais
        _passada(parou_no_3, 1),                 # vendeu menos: a parada viria tarde
        _passada([30.0] * 5, 5),                 # sem rolha, vendeu tudo
        _passada([30.0] * 5, 3),                 # havia rolha e o detector não viu
    ], k=2, limiar=1.0)
    assert c == {"exato": 1, "falso_positivo": 1, "tarde": 1, "limpa": 1,
                 "perdida": 1}


def test_a_rolha_exige_k_seguidas():
    assert medir_a_rolha.primeira_rolha([0.1, 30, 0.1, 0.1], k=2, limiar=1) == 3
    assert medir_a_rolha.primeira_rolha([0.1, 30, 0.1], k=2, limiar=1) is None
    assert medir_a_rolha.primeira_rolha([None, 0.1], k=1, limiar=1) == 2


def test_a_venda_mede_cada_clique_e_registra_cada_passada():
    """A fiação: o laço de venda chama a medição -- AST, não texto."""
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.vendedor import JanelaDeVenda

    arvore = ast.parse(textwrap.dedent(inspect.getsource(JanelaDeVenda.sell_from_slot)))
    chamadas = [n.func.attr for n in ast.walk(arvore)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert chamadas.count("_medir_o_slot") == 2      # antes do 1º e depois de cada
    assert "_registrar_a_rolha" in chamadas


def test_o_juiz_le_tambem_o_arquivo_diario_do_log(tmp_path):
    """O arquivo vivo guarda poucas linhas; o excedente vai para `arquivo/`, e
    é lá que horas de venda medida vão estar. Ler só a pasta de cima dava
    "SEM DADOS" com a medição inteira gravada."""
    import gzip
    import json

    linha = json.dumps({"msg": "ROLHA/MEDIÇÃO passada=1 cliques=3 vendidos=2 "
                               "difs=[5.0, 0.1, 0.2]"}, ensure_ascii=False)
    (tmp_path / "arquivo").mkdir()
    (tmp_path / "arquivo" / "blazes-dev-2026-09-26.jsonl").write_text(
        linha + "\n", encoding="utf-8")
    with gzip.open(tmp_path / "arquivo" / "blazes-dev-2026-09-25.jsonl.gz",
                   "wt", encoding="utf-8") as f:
        f.write(linha + "\n")

    assert len(medir_a_rolha.ler_passadas(tmp_path)) == 2
