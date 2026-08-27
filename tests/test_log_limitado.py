"""Testes de lógica pura do arquivo de log com teto (`log_limitado.py`).

Cada teste cria o handler num arquivo próprio de `tmp_path`; o handler é
fechado no fim para soltar o stream.
"""
import logging

from blazesbot.core.log_limitado import ArquivoDeLogLimitado


def _record(texto: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="blazes.teste", level=logging.INFO,
        pathname=__file__, lineno=1, msg=texto, args=(), exc_info=None,
    )


def _handler(caminho, maximo=10, folga=5):
    h = ArquivoDeLogLimitado(caminho, maximo=maximo, folga=folga)
    h.setFormatter(logging.Formatter("%(message)s"))
    return h


def test_contar_arquivo_existente(tmp_path):
    arq = tmp_path / "log.txt"
    arq.write_text("a\nb\nc\nd\n", encoding="utf-8")
    h = ArquivoDeLogLimitado(arq)
    assert h._contar() == 4
    h.close()


def test_poda_mantem_ultimas_linhas(tmp_path):
    arq = tmp_path / "log.txt"
    h = _handler(arq, maximo=3, folga=2)
    for i in range(6):
        h.emit(_record(f"linha {i}"))
    h.close()
    assert arq.read_text(encoding="utf-8").splitlines() == [
        "linha 3", "linha 4", "linha 5",
    ]


def test_sem_poda_abaixo_do_limite(tmp_path):
    arq = tmp_path / "log.txt"
    h = _handler(arq, maximo=10, folga=5)
    for i in range(3):
        h.emit(_record(f"linha {i}"))
    h.close()
    assert len(arq.read_text(encoding="utf-8").splitlines()) == 3


def test_registro_multilinha_conta_linhas(tmp_path):
    arq = tmp_path / "log.txt"
    h = _handler(arq, maximo=100, folga=10)
    h.emit(_record("primeira\nsegunda\nterceira"))
    h.close()
    assert len(arq.read_text(encoding="utf-8").splitlines()) == 3
    assert h._linhas == 3


def test_maximo_minimo_1(tmp_path):
    h = ArquivoDeLogLimitado(tmp_path / "x.log", maximo=0, folga=0)
    assert h.maximo == 1
    assert h.folga == 1
    h.close()