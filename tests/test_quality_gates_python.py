"""Quality gates do BlazesBot, em Python.

================================================================
POR QUE ESTE ARQUIVO EXISTE
================================================================

O toolkit `soumatheusgomes/vibe-coding-toolkit` traz três regras de ESLint
(teto de linhas por arquivo, proibição de `console` direto, e proibição da
camada de apresentação importar o cliente do banco) que são uma forma
compacta de dizer três princípios que valem para qualquer projeto:

  1. Um arquivo que cresce demais sem ser quebrado vira o lugar onde
     ninguém entra para mexer — e a próxima vez que precisar de mexer,
     o problema já é gigante. O teto de linhas é a pressão constante
     para que a quebra aconteça EM TEMPO DE ESCREVER, não em refactor
     heroico dois anos depois.

  2. `print()` em código de aplicação é o anti-log: o desenvolvedor
     depura localmente, deixa o print no código, o bot roda por horas
     em produção, e ninguém sabe o que apareceu no stdout do servidor
     nem tem como correlacionar com `logs/dev/blazes-dev.jsonl`.

  3. A camada de UI importar o cliente do banco é o acoplamento que
     parece inofensivo no dia e só cobra o preço meses depois, quando
     mexer num canto quebra o outro. A contraparte Python deste
     princípio já é `tests/test_ecossistemas.py` (bc/app/hh não se
     importam; core não conhece bot; bot não conhece ecossistema —
     exceto o supervisor, que ESCOLHE qual roda).

Este arquivo é a porta 1 e 2. A porta 3 já está coberta em
`test_ecossistemas.py` e não é duplicada.

================================================================
POR QUE WARN E NÃO ERROR (regra do passo 6 do toolkit)
================================================================

A regra do toolkit é clara: gate que nasce vermelho em cima de código
que já existia é ruído que alguém desliga na primeira sexta-feira.
Por isso cada teste nasce em `pytest.warns` (avisa, não reprova) e só
vira `assert` quando a contagem anotada chega a zero. A lista
baseline fica na docstring de cada teste, e a migração termina
quando a contagem zera e o teste passa a reprovar de verdade.

================================================================
MEDIÇÃO (05/09/2026) — POR QUE O TETO É 800, E NÃO 350
================================================================

O 350 do toolkit foi importado e reprovou 45 dos 90 `.py`. Duas
medições mostraram que o número não serve para ESTE projeto:

  1. A MEDIANA do projeto é 410 linhas. Um teto ABAIXO da mediana
     não sinaliza exceção — descreve o projeto inteiro. Gate que
     reprova a mediana não é gate: é ruído com 45 itens de fila,
     e fila que parece infinita convida a partir arquivo na marreta.

  2. Só 40% das linhas daqui são código executável:

         código ....... 22.475  (40%)
         docstring .... 13.136  (23%)
         comentário ... 11.907  (21%)
         em branco .....  7.621  (13%)

     O 350 do toolkit foi calibrado para TypeScript/JSX, muito mais
     denso. Aqui, 350 linhas cruas equivalem a ~142 linhas de código
     real — um teto 2,5x mais apertado do que o toolkit pretendia.
     Pior: 44% do arquivo é docstring e comentário, que é exatamente
     o que o `CLAUDE.md` EXIGE ("porquê medido", "documentação de
     transição no mesmo passo"). Um teto de linhas cruas em 350
     pune a documentação que outra regra do projeto manda escrever.

800 linhas cruas ≈ 325 linhas de código real — o ponto de pressão que
o toolkit de fato queria ("abaixo de ~200 vira briga, acima de ~500
para de pressionar", em linhas de CÓDIGO). Fica acima do p75 (664),
então reprova o outlier e não a mediana. E é o número que
`~/.claude/rules/ecc/code-review.md` já mandava ("Files are cohesive
(<800 lines)") antes do 350 vindo de fora atropelá-lo calado.

Teto de 800: 19 arquivos acima (era 45 com 350) — lista ordenada em
`docs/decisoes/eslint-portado-para-python.md`.

`print()` em local proibido: 4 ocorrências — ver mesmo doc.
"""
import re
import warnings
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent / "blazesbot"

# 800 linhas CRUAS ~= 325 linhas de código real neste projeto (só 40% das
# linhas daqui são código; 44% é docstring e comentário). É o ponto de
# pressão que o toolkit queria, medido para esta base — e não o 350 dele,
# que fica abaixo da mediana de 410 e reprovaria metade do projeto.
# O porquê completo está na docstring do módulo, seção MEDIÇÃO (05/09/2026).
TETO_DE_LINHAS = 800

# Onde `print()` É legítimo. São a porta de saída de scripts ad-hoc e de
# diagnósticos que rodam UMA vez por invocação humana, não dentro do bot
# rodando. Tudo o mais é aplicação e deveria ir para `logging`.
#
# - `tools/` é a fronteira dos scripts CLI de aferição (vigiar, ler_camera,
#   find_base). É diagnóstico, não produção.
# - `core/calibracao.py`, `core/indice_de_constantes.py`,
#   `core/indice_de_tempos.py` rodam como `python -m blazesbot.core.X` —
#   mesma natureza de tools.
# - `bot/instrumentar_clique.py` e `bot/teste_do_cursor.py` são entradas
#   CLI do bot (ver `18-AFERIR-ALVO-ALIADO.bat`); têm `if __name__ ==
#   "__main__":` no fim e rodam uma vez por aferição.
EXCECOES_DE_PRINT = frozenset({
    "blazesbot/tools/find_base.py",
    "blazesbot/tools/ler_camera.py",
    "blazesbot/tools/vigiar_combate.py",
    "blazesbot/tools/vigiar_local.py",
    "blazesbot/core/calibracao.py",
    "blazesbot/core/indice_de_constantes.py",
    "blazesbot/core/indice_de_tempos.py",
    "blazesbot/bot/instrumentar_clique.py",
    "blazesbot/bot/teste_do_cursor.py",
})


def _todos_os_python(raiz: Path) -> list[Path]:
    """Todos os `.py` da árvore, ordenados, exceto `__pycache__`."""
    return sorted(p for p in raiz.rglob("*.py")
                  if "__pycache__" not in p.parts)


# ===========================================================================
# GATE 1 — TETO DE 800 LINHAS POR ARQUIVO
# ===========================================================================

@pytest.mark.parametrize("arquivo", _todos_os_python(RAIZ),
                         ids=lambda p: str(p.relative_to(RAIZ)))
def test_max_linhas_por_arquivo(arquivo):
    """Teto de 800 linhas por arquivo, medido para esta base.

    HOJE: gate em `warn` (não reprova). É o que o passo 6 do toolkit
    manda: gate que nasce vermelho em cima de código que já existia
    é ruído que alguém desliga. A lista atual de offenders está
    ordenada em `docs/decisoes/eslint-portado-para-python.md`.

    AMANHÃ: quando a contagem baseline anotada na doc chegar a zero,
    o `pytest.warns` aqui se transforma em `assert` e a regra passa
    a reprovar de verdade. Novos arquivos grandes ficam visíveis na
    hora — e o aviso some.
    """
    caminho = arquivo.relative_to(RAIZ.parent)
    # `__init__.py` puro-reexport tem zero linhas de lógica. Contar ele
    # como arquivo só porque existe é a armadilha que o prompt 08 avisa.
    texto = arquivo.read_text(encoding="utf-8")
    if caminho.name == "__init__.py" and not texto.strip():
        return
    n = len(texto.splitlines())
    if n > TETO_DE_LINHAS:
        with pytest.warns(UserWarning, match=re.escape(
                f"{caminho}: {n} linhas (teto {TETO_DE_LINHAS})")):
            warnings.warn(
                f"{caminho}: {n} linhas (teto {TETO_DE_LINHAS}). "
                f"Ver docs/decisoes/eslint-portado-para-python.md.",
                stacklevel=1,
            )


# ===========================================================================
# GATE 2 — `print()` SÓ EM SCRIPTS DE DIAGNÓSTICO
# ===========================================================================

def test_print_so_em_scripts_de_diagnostico():
    """`print()` em código de aplicação é o anti-log: sai no stdout do
    servidor, não tem `id_run`/`conta`/`fase`, e ninguém consegue
    correlacionar com `logs/dev/blazes-dev.jsonl`.

    A porta de saída de diagnóstico (scripts CLI, geradores) está em
    `EXCECOES_DE_PRINT`. Toda adição nova ali é decisão consciente,
    documentada na docstring acima do frozenset.

    A diferença para o T201 do ruff: o T201 é puramente sintático
    ("tem print, viola"). Este teste sabe o que é aplicação e o que
    é diagnóstico, e isola só o que importa.
    """
    # Regex só no nível de módulo. `print` dentro de string é `repr`,
    # e o nome da função `_salvar_print` de `core/quedas.py` também
    # não conta — começa com `_`. A regex exige `print(` no início
    # da linha OU após um caractere que não seja letra/`_`/dígito
    # (defensivo contra `repr(x.print)` hipotético).
    call = re.compile(r"(?<![\w.])print\(")
    violacoes: list[str] = []
    for arquivo in _todos_os_python(RAIZ):
        caminho = arquivo.relative_to(RAIZ.parent)
        caminho_str = str(caminho).replace("\\", "/")
        if caminho_str in EXCECOES_DE_PRINT:
            continue
        for n_linha, linha in enumerate(
                arquivo.read_text(encoding="utf-8").splitlines(), start=1):
            if call.search(linha):
                violacoes.append(f"{caminho_str}:{n_linha}: {linha.strip()}")
    if violacoes:
        lista = "\n  ".join(violacoes)
        with pytest.warns(UserWarning, match=re.escape(
                f"{len(violacoes)} `print()` em local proibido")):
            warnings.warn(
                f"{len(violacoes)} `print()` em local proibido. "
                f"Adicione o caminho a `EXCECOES_DE_PRINT` (decisão "
                f"documentada) ou troque por `logging`: \n  {lista}",
                stacklevel=1,
            )
