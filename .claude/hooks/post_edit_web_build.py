"""PostToolUse: alteração em `web/` (Edit/Write/MultiEdit) roda `npm run build` sozinha.

Fecha a regra 1b do CLAUDE.md (`toda alteração em web/ ⇒ npm run build no mesmo
passo`) na marra: hoje é disciplina, e já falhou uma vez -- 07/09/2026, `dist/`
40 minutos atrasado enquanto o backend seguia em frente
(`tests/test_dist_atualizado.py` conta a história). O teste continua existindo
como rede de segurança; este hook existe para o defeito nunca mais acontecer.

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
    if not caminho or not Path(caminho).resolve().is_relative_to(RAIZ / "web"):
        return 0

    resultado = subprocess.run(
        ["npm", "run", "build"],
        cwd=RAIZ,
        shell=True,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(resultado.stdout)
    sys.stderr.write(resultado.stderr)
    if resultado.returncode != 0:
        sys.stderr.write("\n[post_edit_web_build] `npm run build` falhou -- dist/ NÃO foi atualizado.\n")
        return 1
    print("[post_edit_web_build] web/ mudou -> npm run build rodou e passou.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
