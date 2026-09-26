"""O portão de commit testa O QUE VAI SER COMMITADO -- e só isso.

A razão de existir está em `blazesbot/tools/portao_de_commit.py`: 22 commits
entraram por cima de uma suíte vermelha, e várias sessões editam a mesma árvore.
O que se trava aqui é o que tornaria o portão inútil ou injusto se regredisse.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from blazesbot.tools import portao_de_commit as portao

RAIZ = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_exporta_o_INDICE_e_nao_a_edicao_nao_preparada(tmp_path):
    """A edição da vizinha, não preparada, NÃO entra no que é testado."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("preparado", encoding="utf-8")
    _git(repo, "add", "a.txt")
    (repo / "a.txt").write_text("edição da vizinha", encoding="utf-8")

    destino = tmp_path / "exportado"
    portao.exportar(destino, repositorio=repo)

    assert (destino / "a.txt").read_text(encoding="utf-8") == "preparado"


def test_todo_teste_do_portao_existe():
    """Teste renomeado sairia do portão calado -- a lição da observação #14."""
    faltam = [t for t in portao.TESTES_DO_PORTAO if not (RAIZ / t).is_file()]
    assert not faltam, f"o portão aponta para testes que não existem: {faltam}"


def test_o_hook_chama_o_portao():
    hook = (RAIZ / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    assert "blazesbot.tools.portao_de_commit" in hook


def test_o_portao_tem_teto():
    assert 0 < portao.TETO_DO_PORTAO_DE_COMMIT <= 600
