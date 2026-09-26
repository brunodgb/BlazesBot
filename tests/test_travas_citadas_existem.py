"""Documento que cita um teste tem de citar um teste que EXISTE.

Observação #39 do `task-observer` (25/09/2026). A ata de 17/09 dizia "travado por
`tests/test_comida_do_pet.py`", e o arquivo não tinha a trava: a guarda foi para
produção sem teste. A varredura deste arquivo, na primeira vez em que rodou,
achou mais cinco citações quebradas -- três testes que NUNCA entraram no git
(inclusive "16 testes" e "a simulação da luta inteira") e um renomeado sem a ata
acompanhar.

Afirmação de enforcement em documentação é código que não roda: apodrece calada.

O QUE ISTO NÃO PROVA: que o teste citado guarda o que a frase diz. Prova só que
ele existe (e, citado como `arquivo::teste` ou `arquivo.teste`, que o teste
existe dentro dele). O resto é de quem escreve a frase.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GERADOS = {"TEMPOS.md", "INTERRUPTORES.md"}
CITACAO = re.compile(r"`(tests/[\w/]+?\.py)(?:(?:::|\.)(\w+))?`")

# A varredura que encolhe continua verde sem proteger nada (observação #14).
# 130 citações em 25/09/2026; tirou citações de propósito, baixe no mesmo commit.
PISO_DE_CITACOES = 120


def _documentos() -> list[Path]:
    docs = [RAIZ / "CLAUDE.md", *sorted((RAIZ / "docs").rglob("*.md"))]
    return [d for d in docs if d.name not in GERADOS]


def _nomes_no_arquivo(arquivo: Path) -> set[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(arvore)
            if isinstance(n, ast.FunctionDef | ast.ClassDef)}


def test_todo_teste_citado_nos_documentos_existe():
    quebradas: list[str] = []
    total = 0
    for doc in _documentos():
        for m in CITACAO.finditer(doc.read_text(encoding="utf-8")):
            total += 1
            arquivo, nome = RAIZ / m.group(1), m.group(2)
            if not arquivo.is_file():
                quebradas.append(f"{doc.relative_to(RAIZ)}: {m.group(0)} -- o arquivo não existe")
            elif nome and nome.startswith("test") and nome not in _nomes_no_arquivo(arquivo):
                quebradas.append(f"{doc.relative_to(RAIZ)}: {m.group(0)} -- o teste não existe")
    assert not quebradas, (
        "documento citando trava que não existe:\n  " + "\n  ".join(quebradas)
        + "\nCorrija o lado errado: escreva o teste, ou diga na ata que ele não existe.")
    assert total >= PISO_DE_CITACOES, (
        f"a varredura achou {total} citações, contra {PISO_DE_CITACOES} em "
        f"25/09/2026 -- se saíram de propósito, baixe o piso neste arquivo.")
