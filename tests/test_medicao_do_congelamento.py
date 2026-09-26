"""A medição do congelamento: o vigia grava, o juiz lê -- e decide com critério."""
import json

from blazesbot.bot import congelamento as mod
from blazesbot.bot.congelamento import VigiaDoCongelamento
from blazesbot.tools import medir_o_congelamento as juiz


class _Log:
    def __init__(self):
        self.debug_linhas: list[str] = []

    def debug(self, m, *a):
        self.debug_linhas.append(m % a if a else m)

    def warning(self, *a, **k):
        pass

    info = warning


class _Ctx:
    def __init__(self):
        self.log = _Log()
        self.account_login = "teste"
        self.memory = type("M", (), {"is_mounted": staticmethod(lambda: True),
                                     "location": staticmethod(lambda: "x")})()


def _vigia():
    v = VigiaDoCongelamento(_Ctx(), lambda: True, maximo_sem_leitura=6.0)
    v.ligado = True
    return v


def test_a_linha_que_o_vigia_grava_e_a_que_o_juiz_le():
    """Produtor e consumidor JUNTOS: sem isto, horas de medição viram lixo."""
    v = _vigia()
    v.olhar((10, 10), "andar")
    v._desde -= 7.5                      # ficou 7,5 s na mesma coordenada
    v._visto_em = v._desde + 7.4         # e o laço continuou lendo
    v.olhar((11, 10), "andar")           # mexeu: a parada acabou

    (linha,) = v.ctx.log.debug_linhas
    m = juiz.LINHA.search(linha)
    assert m, linha
    assert 7.4 <= float(m[1]) <= 7.7 and m[2] == "0"


def test_parada_curta_nao_entra(monkeypatch):
    v = _vigia()
    v.olhar((10, 10), "andar")
    v.olhar((11, 10), "andar")
    assert v.ctx.log.debug_linhas == []


def test_desligada_nao_grava(monkeypatch):
    monkeypatch.setattr(mod, "MEDIR_O_CONGELAMENTO", False)
    v = _vigia()
    v.olhar((10, 10), "andar")
    v._desde -= 9
    v._visto_em = v._desde + 8.9
    v.olhar((11, 10), "andar")
    assert v.ctx.log.debug_linhas == []


def test_o_juiz_conta_falsas_e_ganho():
    paradas = [(16.0, 1), (17.0, 1), (4.5, 0), (2.5, 0), (9.0, 0)]
    j = juiz.julgar(paradas, 5.0)
    assert j["reais"] == 2
    assert j["falsas"] == 1                       # só a de 9 s passa de 5
    assert j["ganho_s"] == 2 * (juiz.SEGUNDOS_PARA_CUTUCAR - 5.0)


def test_o_juiz_le_tambem_o_arquivo_diario(tmp_path):
    linha = json.dumps({"msg": "CONGELAMENTO/MEDIÇÃO parado=16.2s cutucadas=1 em (1, 2)"},
                       ensure_ascii=False)
    (tmp_path / "arquivo").mkdir()
    (tmp_path / "arquivo" / "blazes-dev-2026-09-26.jsonl").write_text(
        linha + "\n", encoding="utf-8")
    assert juiz.ler_paradas(tmp_path) == [(16.2, 1)]
