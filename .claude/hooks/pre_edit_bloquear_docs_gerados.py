"""PreToolUse: bloqueia Edit/Write direto em doc GERADO -- força passar pelo gerador.

`docs/TEMPOS.md` e `docs/INTERRUPTORES.md` são `GERADO` (marcado no próprio
CLAUDE.md): nascem de `python -m blazesbot.core.indice_de_tempos`, travados por
`tests/test_indice_de_tempos.py`. Editar o `.md` à mão cria doc e código
divergentes sem nenhum teste pegando -- o teste só verifica se o gerador
concorda com o `.md`, não se alguém mexeu no `.md` por fora dele.

Arquivo em vez de comando inline pelo mesmo motivo do task_observer_hook.py:
cmd.exe (Windows) engole aspas aninhadas.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCS_GERADOS = {RAIZ / "docs" / "TEMPOS.md", RAIZ / "docs" / "INTERRUPTORES.md"}


def main() -> int:
    sys.stderr.reconfigure(encoding="utf-8")
    dado = json.load(sys.stdin)
    caminho = dado.get("tool_input", {}).get("file_path")
    if not caminho:
        return 0
    if Path(caminho).resolve() in DOCS_GERADOS:
        sys.stderr.write(
            "Este arquivo é GERADO por `python -m blazesbot.core.indice_de_tempos` "
            "-- editar direto aqui diverge do código na próxima geração. Mexa na "
            "constante/literal em blazesbot/ e rode o gerador.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
