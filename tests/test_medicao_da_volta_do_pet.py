"""A medição da VOLTA DO PET depois da troca de mapa (25/09/2026) -- só registra.

O que se trava: a linha que o `core/pet` grava é a que
`tools/medir_a_volta_do_pet.py` lê, e sem contexto não há thread nenhuma.
Porquê: `core/pet.MEDIR_A_VOLTA_DO_PET`.
"""
from __future__ import annotations

import json
import threading
import time

from blazesbot.core import pet
from blazesbot.tools import medir_a_volta_do_pet


class _Log:
    def __init__(self):
        self.linhas: list[str] = []

    def info(self, msg, *args):
        self.linhas.append(msg % args if args else msg)

    debug = warning = error = info


def test_os_trechos_juntam_iguais_seguidos():
    leituras = [(0.0, False), (0.25, False), (0.5, True), (0.75, True), (1.0, None)]
    assert pet.trechos_da_volta(leituras) == [
        [False, 0.0, 0.25], [True, 0.5, 0.75], [None, 1.0, 1.0]]


def test_sem_contexto_nao_mede():
    antes = threading.active_count()
    pet.trocou_de_mapa(4242)
    assert threading.active_count() == antes


def test_a_linha_que_o_pet_grava_e_a_que_o_juiz_le(monkeypatch):
    monkeypatch.setattr(pet, "SEGUNDOS_DE_AMOSTRA_DA_VOLTA", 0.08)
    monkeypatch.setattr(pet, "PASSO_DA_AMOSTRA_DA_VOLTA", 0.01)
    respostas = iter([False, False, True])
    log = _Log()
    ctx = type("Ctx", (), {"log": log, "account_login": "teste",
                           "memory": type("M", (), {"pet_active": staticmethod(
                               lambda: next(respostas, True))})()})()

    pet.trocou_de_mapa(4243, ctx)
    limite = time.monotonic() + 2
    while not log.linhas and time.monotonic() < limite:
        time.sleep(0.01)

    (linha,) = log.linhas
    m = medir_a_volta_do_pet.LINHA.search(linha)
    assert m, linha
    tipo, volta = medir_a_volta_do_pet.classificar(json.loads(m.group(3)))
    assert tipo == "some_e_volta" and volta is not None


def test_o_juiz_do_pet_separa_os_desfechos():
    classificar = medir_a_volta_do_pet.classificar
    assert classificar([[False, 0.0, 3.0], [True, 3.25, 30.0]]) == ("some_e_volta", 3.25)
    assert classificar([[True, 0.0, 30.0]]) == ("sempre_true", None)
    assert classificar([[False, 0.0, 30.0]]) == ("nao_voltou", None)
    assert classificar([[None, 0.0, 30.0]]) == ("ilegivel", None)


def test_o_juiz_do_pet_le_tambem_o_arquivo_diario_do_log(tmp_path):
    """O excedente do log de dev vai para `arquivo/`: ler só a pasta de cima
    dava "SEM DADOS" com a medição inteira gravada."""
    linha = json.dumps({"msg": "PET/MEDIÇÃO conta=teste leituras=3 "
                               "trechos=[[false, 0.0, 3.0], [true, 3.25, 30.0]]"},
                       ensure_ascii=False)
    (tmp_path / "arquivo").mkdir()
    (tmp_path / "arquivo" / "blazes-dev-2026-09-26.jsonl").write_text(
        linha + "\n", encoding="utf-8")

    assert len(medir_a_volta_do_pet.ler_trocas(tmp_path)) == 1
