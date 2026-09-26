"""A suíte não grava nos diários do projeto (`logs/*.log`) -- ver `conftest.py`."""
from pathlib import Path

from blazesbot.core import diario


def test_o_evento_de_teste_vai_para_a_pasta_temporaria(tmp_path):
    diario.registrar_evento("simulacao", "TRAVADO-NA-CAVE", "teste", (203, 30),
                            "Secret Altar")

    assert diario.PASTA == tmp_path / "logs"
    assert "simulacao" in (tmp_path / "logs" / "eventos.log").read_text(encoding="utf-8")


def test_o_diario_de_verdade_continua_em_logs():
    """Fora do teste o caminho é o de sempre -- o conftest só o desvia aqui."""
    import importlib

    import blazesbot.core.diario as mod

    fonte = Path(importlib.util.find_spec(mod.__name__).origin).read_text(encoding="utf-8")
    assert 'PASTA = Path("logs")' in fonte
