"""O PORTÃO DE COMMIT: os testes de portão rodam sobre O QUE VAI SER COMMITADO.

=========================================================================
POR QUE EXISTE
=========================================================================

Entre 20 e 25/09/2026, 22 commits entraram por cima de uma suíte vermelha
(`vendedor.py` acima do teto da catraca de tamanho). A regra "rode a suíte
inteira" estava escrita; faltava o que a torna impossível de pular.

=========================================================================
POR QUE O ÍNDICE, E NÃO A ÁRVORE DE TRABALHO
=========================================================================

Várias sessões editam esta árvore ao mesmo tempo (`CLAUDE.md`, regra 0b). Um
portão que rodasse na árvore de trabalho reprovaria o commit de uma sessão pela
edição NÃO PREPARADA da vizinha -- medido em 25/09/2026: sete arquivos de outra
sessão desatualizaram o `docs/TEMPOS.md` enquanto esta trabalhava.

Então o portão exporta o ÍNDICE para uma pasta temporária e roda os testes LÁ.
`git checkout-index` respeita o `GIT_INDEX_FILE` que o próprio git monta num
`git commit -- <caminhos>`: o que é testado é exatamente o que vai ser gravado.

=========================================================================
USO
=========================================================================

    python -m blazesbot.tools.portao_de_commit
        O hook (`.githooks/pre-commit`). Sai com o código do pytest.

    python -m blazesbot.tools.portao_de_commit --regenerar <arquivos...>
        Regenera os índices GERADOS (`docs/TEMPOS.md`, `docs/INTERRUPTORES.md`)
        sobre HEAD + os seus arquivos -- sem a edição da vizinha -- e copia o
        resultado para a árvore. Commite os dois junto com os seus arquivos.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Os testes ESTÁTICOS da suíte: leem código e documentos, não o jogo. São eles
# que pegam o que já entrou quebrado aqui -- arquivo acima do teto, ecossistema
# importando o outro, espera cega nova, índice velho, `self.x` sem `x`.
TESTES_DO_PORTAO = (
    "tests/test_quality_gates_python.py",
    "tests/test_ecossistemas.py",
    "tests/test_catraca_da_espera_cega.py",
    "tests/test_claude_md_tamanho.py",
    "tests/test_indice_de_tempos.py",
    "tests/test_indice_de_constantes.py",
    "tests/test_sem_chamada_orfa.py",
    "tests/test_travas_citadas_existem.py",
)

# O portão inteiro leva ~20 s (421 testes, medido em 27/09/2026).
# Eram ~75 s enquanto a catraca refazia a varredura por caso. O teto é a
# garantia de que um teste preso não segura o commit para sempre -- a lição
# do pytest que rodou 119 h.
TETO_DO_PORTAO_DE_COMMIT = 300

INDICES_GERADOS = ("docs/TEMPOS.md", "docs/INTERRUPTORES.md")
GERADORES = ("blazesbot.core.indice_de_tempos", "blazesbot.core.indice_de_constantes")


def exportar(destino: Path, *, repositorio: Path = RAIZ,
             env: dict[str, str] | None = None) -> None:
    """Grava em `destino` o conteúdo do ÍNDICE (o que vai ser commitado)."""
    subprocess.run(
        ["git", "checkout-index", "--all", f"--prefix={destino.as_posix()}/"],
        cwd=repositorio, env=env, check=True)


def rodar_o_portao() -> int:
    with tempfile.TemporaryDirectory(prefix="portao-") as pasta:
        exportar(Path(pasta))
        print(f"portão: {len(TESTES_DO_PORTAO)} arquivos de teste sobre o "
              "índice (o que vai ser commitado)...", flush=True)
        try:
            feito = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 *TESTES_DO_PORTAO],
                cwd=pasta, timeout=TETO_DO_PORTAO_DE_COMMIT)
        except subprocess.TimeoutExpired:
            print(f"portão: passou de {TETO_DO_PORTAO_DE_COMMIT} s -- reprovado.")
            return 1
    if feito.returncode:
        print("portão: REPROVADO. O commit não foi feito; conserte o que os "
              "testes acima apontam. (Índice velho? `python -m "
              "blazesbot.tools.portao_de_commit --regenerar <seus arquivos>`.)")
    return feito.returncode


def regenerar(arquivos: list[str]) -> int:
    """Índices gerados sobre HEAD + `arquivos`, sem a edição de mais ninguém."""
    with tempfile.TemporaryDirectory(prefix="indices-") as pasta:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(pasta) / "indice")}
        subprocess.run(["git", "read-tree", "HEAD"], cwd=RAIZ, env=env, check=True)
        if arquivos:
            subprocess.run(["git", "add", "-A", "--", *arquivos],
                           cwd=RAIZ, env=env, check=True)
        arvore = Path(pasta) / "arvore"
        exportar(arvore, env=env)
        for gerador in GERADORES:
            subprocess.run([sys.executable, "-m", gerador], cwd=arvore,
                           check=True, stdout=subprocess.DEVNULL)
        for indice in INDICES_GERADOS:
            shutil.copyfile(arvore / indice, RAIZ / indice)
    print("regenerados sobre HEAD + os seus arquivos:", ", ".join(INDICES_GERADOS))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--regenerar", nargs="*", metavar="ARQUIVO",
                        help="regenera os índices gerados sobre HEAD + ARQUIVOs")
    args = parser.parse_args(argv)
    if args.regenerar is not None:
        return regenerar(args.regenerar)
    return rodar_o_portao()


if __name__ == "__main__":
    raise SystemExit(main())
