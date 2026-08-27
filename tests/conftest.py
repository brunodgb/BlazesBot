"""Proteções que valem para a suíte INTEIRA.

=============================================================================
POR QUE ISTO EXISTE: A SUÍTE ESCREVEU NA PASTA `data/` DO PROJETO
=============================================================================

Aconteceu em 19/08/2026, e foi pego lendo o relatório do placar. A calibração
(`core/calibracao.py`) grava em `data/calibracao.json`, e os testes que exercitam
`_alvo_morreu()` chamam a calibração de verdade -- então o placar do projeto
encheu de amostras FABRICADAS por teste:

    alvo_hp  0x808  aprendendo   53 amostras   10 runs
    alvo_hp  0x80C  reprovado   100 amostras

Nada disso veio do jogo. E o estrago não é um arquivo sujo: o objetivo daquele
placar é decidir QUAL PONTEIRO PROMOVER a partir de evidência real. Evidência
inventada por teste misturada com evidência de produção corrompe exatamente a
decisão que ele existe para embasar -- e ninguém teria como distinguir depois.

`autouse=True` e escopo de FUNÇÃO: cada teste começa com placar limpo, num
diretório temporário que o pytest joga fora. Um teste que queira medir o placar
sobrescreve o caminho por conta própria (é o que `test_calibracao.py` faz), e aí
está medindo o placar dele, não o do projeto.
"""
import pytest

from blazesbot.core import calibracao


@pytest.fixture(autouse=True)
def _placar_de_calibracao_fora_do_projeto(tmp_path, monkeypatch):
    """Nenhum teste escreve no `data/calibracao.json` de verdade."""
    monkeypatch.setattr(calibracao, "CAMINHO_DO_PLACAR",
                        tmp_path / "calibracao-de-teste.json")
    calibracao.zerar_para_teste()
