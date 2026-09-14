"""PostToolUse: alteração em `blazesbot/*.py` (Edit/Write/MultiEdit) roda `graphify update .` sozinha.

Fecha a regra 1 do CLAUDE.md (`toda alteração no código ⇒ atualizar o
graphify`) na marra: hoje é disciplina, sem rede de segurança nenhuma se
alguém esquecer -- ao contrário da regra 1b (web/), que tem
`tests/test_dist_atualizado.py` cobrindo o esquecimento.

Arquivo em vez de comando inline pelo mesmo motivo do task_observer_hook.py:
cmd.exe (Windows) engole aspas aninhadas.
"""
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    dado = json.load(sys.stdin)
    caminho = dado.get("tool_input", {}).get("file_path")
    if not caminho:
        return 0
    caminho = Path(caminho).resolve()
    if not (caminho.is_relative_to(RAIZ / "blazesbot") and caminho.suffix == ".py"):
        return 0

    resultado = subprocess.run(
        ["graphify", "update", "."],
        cwd=RAIZ,
        shell=True,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(resultado.stdout)
    sys.stderr.write(resultado.stderr)
    if resultado.returncode != 0:
        sys.stderr.write("\n[post_edit_graphify_update] `graphify update .` falhou.\n")
        return 1
    print("[post_edit_graphify_update] blazesbot/ mudou -> graphify update . rodou.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
