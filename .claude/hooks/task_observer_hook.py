"""Lembrete de SessionStart: invocar a skill `task-observer`.

Existe como ARQUIVO e não como `python -c "..."` na configuração porque o
comando do hook é executado pelo shell do Windows (cmd.exe), e aspas aninhadas
não sobrevivem à passagem -- medido: o mesmo comando funcionava no Git Bash e
saía com código 1 no cmd. Sem aspas no comando, não há o que quebrar.

O texto mora no .txt ao lado para poder ser editado sem mexer em código.
"""
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")
print((Path(__file__).with_name("task-observer.txt")).read_text(encoding="utf-8"))
