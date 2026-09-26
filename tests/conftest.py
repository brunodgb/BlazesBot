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

from blazesbot.core import calibracao, diario


@pytest.fixture(autouse=True)
def _placar_de_calibracao_fora_do_projeto(tmp_path, monkeypatch):
    """Nenhum teste escreve no `data/calibracao.json` de verdade."""
    monkeypatch.setattr(calibracao, "CAMINHO_DO_PLACAR",
                        tmp_path / "calibracao-de-teste.json")
    calibracao.zerar_para_teste()


def _soltar_os_diarios() -> None:
    """Fecha e esquece os loggers de diário já abertos (eles guardam o arquivo)."""
    for log in diario._criados.values():
        for handler in list(log.handlers):
            log.removeHandler(handler)
            handler.close()
    diario._criados.clear()


@pytest.fixture(autouse=True)
def _diarios_fora_do_projeto(tmp_path, monkeypatch):
    """Nenhum teste escreve em `logs/eventos.log` nem nos outros diários.

    O MESMO DEFEITO DA CALIBRAÇÃO, medido em 26/09/2026: 3.566 das 20.058 linhas
    do `logs/eventos.log` eram de teste (contas `simulacao` e `conta`), e uma
    "travada" sintética em (203,30) virou o maior ponto quente do BC. E o dano
    passa do barulho: o diário tem teto de linhas e poda as antigas, então cada
    linha de teste EMPURROU PARA FORA um evento real.
    """
    _soltar_os_diarios()
    monkeypatch.setattr(diario, "PASTA", tmp_path / "logs")
    yield
    _soltar_os_diarios()
