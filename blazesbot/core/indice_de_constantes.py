"""Índice das constantes ajustáveis do projeto -- GERADO, nunca escrito à mão.

=============================================================================
POR QUE ISTO EXISTE
=============================================================================

Este projeto decide comportamento por CONSTANTE no topo do módulo: interruptor
(`MODO_DE_CLIQUE`, `USAR_MOUSE_SHIELD`, `FONTE_DA_MORTE_DO_ALVO`) e número
medido (tolerância, limiar, teto, cadência). São quase 400 delas, espalhadas
por 44 arquivos, e cada uma tem 10-40 linhas de comentário explicando a medição
que a justifica -- que é o certo, e é o que faz `docs/decisoes/` funcionar.

O que faltava era o ÍNDICE. Sem ele:

  * achar "aquela constante do teto do clique" é grep e memória;
  * saber QUEM LÊ uma constante antes de mexer nela é grep de novo;
  * e, o pior, o valor no código passa a divergir do valor citado na
    documentação sem ninguém notar. Aconteceu: o `CLAUDE.md` afirma
    `USAR_MOUSE_SHIELD = True` em maiúsculas ("é OBRIGATÓRIO") e o código está
    em `False`. Interruptor é barato de criar e caro de manter honesto.

Escrever esse índice à mão só transfere o problema -- ele apodrece igual. Então
ele é GERADO do código, e um teste reprova quando o arquivo em disco não bate
com o que o código diz hoje. O índice não pode ficar velho: ou está certo, ou a
suíte reprova.

=============================================================================
O QUE ENTRA, E O QUE NÃO
=============================================================================

Entra: constante de módulo em MAIÚSCULAS cujo valor é literal (bool, str, int,
float) -- as que alguém muda para mudar comportamento.

NÃO entra:

  * constante de PROTOCOLO/SO (`WM_KEYDOWN`, `VK_F1`, `MK_LBUTTON`...). Elas não
    são escolha nossa: são números do Windows, e mudá-las não ajusta nada, quebra.
  * ENDEREÇO e OFFSET de memória (`ADDR_*`, `OFF_*`, `CHAIN_*`). Também não são
    ajuste: são medição do binário, moram em `memory.py` com o porquê de cada
    uma, e agora têm tratamento próprio em `core/rebase.py`.

A régua é: *"eu mexeria nisto para o bot se comportar diferente?"* Se a resposta
for não, é ruído no índice -- e índice com ruído deixa de ser lido, que é o
mesmo destino do índice velho.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

__all__ = [
    "ARQUIVO_DO_INDICE",
    "Constante",
    "extrair",
    "gerar_markdown",
]

ARQUIVO_DO_INDICE = Path("docs") / "INTERRUPTORES.md"
RAIZ_PADRAO = Path("blazesbot")

# Prefixos de constante que NÃO são ajuste nosso -- ver o cabeçalho.
PREFIXOS_IGNORADOS = (
    "WM_", "VK_", "MK_", "HT", "PW_", "SRC", "SM_", "GA_", "SW_", "WS_",
    "MEM_", "PAGE_", "PROCESS_", "TH32", "SRCCOPY", "GWL_", "HWND_",
    "ADDR_", "OFF_", "CHAIN_", "IMAGE_BASE", "PLAYER_BASE",
)

# Um interruptor é o que ESCOLHE ENTRE CAMINHOS: booleano, ou o nome de um modo.
# Eles ganham tabela própria porque são os que mudam comportamento inteiro com
# uma palavra -- e são os que já divergiram da documentação.
PREFIXOS_DE_INTERRUPTOR = ("USAR_", "MODO_", "CONFERIR_", "FONTE_", "ATIVADO",
                           "APAGAR_", "HABILITAR_")


@dataclass(frozen=True, slots=True)
class Constante:
    nome: str
    valor: object
    arquivo: str
    linha: int
    porque: str
    leitores: tuple[str, ...]

    @property
    def e_interruptor(self) -> bool:
        return isinstance(self.valor, bool) or self.nome.startswith(
            PREFIXOS_DE_INTERRUPTOR)

    @property
    def valor_formatado(self) -> str:
        return repr(self.valor)


def _ignorar(nome: str) -> bool:
    return nome.startswith(PREFIXOS_IGNORADOS) or nome.startswith("_")


def _porque(linhas: list[str], linha_da_constante: int) -> str:
    """A última frase do bloco de comentário logo ACIMA da constante.

    O comentário inteiro tem 10-40 linhas -- pôr tudo aqui faria uma tabela
    ilegível, e o porquê completo já mora no código e em `docs/decisoes/`. O
    índice serve para ACHAR e para conferir o valor; a primeira linha do
    comentário é o suficiente para reconhecer qual é qual.
    """
    bloco: list[str] = []
    i = linha_da_constante - 2          # 1-based -> 0-based, e sobe uma
    while i >= 0:
        texto = linhas[i].strip()
        if texto.startswith("#"):
            bloco.append(texto.lstrip("#").strip())
            i -= 1
            continue
        if not texto and bloco:
            break                        # linha em branco encerra o bloco
        if not texto:
            i -= 1
            continue
        break
    bloco.reverse()

    # O TÍTULO CERTO É O ÚLTIMO, NÃO O PRIMEIRO. O estilo de comentário da casa
    # separa seções com uma régua de `===`, e um bloco contíguo pode carregar
    # várias seções -- em `inputs.py` a régua do interruptor do shield vem logo
    # depois de "Tipos declarados para não truncar HWND", sem linha em branco
    # entre as duas. Pegar a primeira linha rotularia o interruptor com o
    # comentário de outra coisa, que foi exatamente o que aconteceu.
    #
    # Então: se houver régua, vale a primeira linha de conteúdo DEPOIS da última
    # régua -- a seção mais próxima da constante. Sem régua, a primeira linha.
    def e_regua(texto: str) -> bool:
        return bool(texto) and set(texto) <= set("=-<>* ")

    titulo = ""
    for i, texto in enumerate(bloco):
        if not texto or e_regua(texto):
            continue
        if not titulo:
            titulo = texto
        if i and e_regua(bloco[i - 1]):
            titulo = texto
    return titulo


# Um identificador em MAIÚSCULAS -- o formato de toda constante deste projeto.
_IDENTIFICADOR = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")


def _identificadores_por_arquivo(fontes: dict[str, str]) -> dict[str, set[str]]:
    """Índice invertido: arquivo -> nomes em maiúsculas que ele cita.

    POR QUE UM ÍNDICE, E NÃO UM REGEX POR CONSTANTE. A primeira versão compilava
    um padrão para CADA constante e varria o texto de TODOS os arquivos: 331 x 91
    varreduras de arquivo inteiro, ~7 s por extração. Como sete testes chamam a
    extração, a suíte pagava 44 s por uma tabela de documentação.

    Uma passada por arquivo transforma isso em 91 varreduras e ~30 mil consultas
    a `set`, que são O(1).
    """
    return {caminho: set(_IDENTIFICADOR.findall(texto))
            for caminho, texto in fontes.items()}


def _leitores(nome: str, definido_em: str,
              indice: dict[str, set[str]]) -> tuple[str, ...]:
    """Arquivos que CITAM esta constante, tirando o que a define.

    Responde "onde ela vai impactar" -- a parte que o grep responde hoje e que
    ninguém tem à mão na hora de decidir se pode mexer.
    """
    return tuple(sorted(
        caminho for caminho, nomes in indice.items()
        if caminho != definido_em
        # O próprio índice cita nomes de constante nos prefixos que usa para
        # classificá-las. Ele não é LEITOR de nenhuma delas, e listá-lo em toda
        # linha seria ruído em 331 linhas.
        and not caminho.endswith("indice_de_constantes.py")
        and nome in nomes
    ))


@lru_cache(maxsize=4)
def _extrair_cacheado(raiz: Path) -> tuple[Constante, ...]:
    """A varredura cruza 331 constantes contra 91 arquivos para descobrir quem
    lê o quê -- é O(n*m) de regex, ~2 s. Um cache por raiz troca sete chamadas
    numa suíte por uma, e o resultado é imutável (`frozen`), então compartilhar
    não tem risco."""
    return tuple(_extrair(raiz))


def extrair(raiz: Path = RAIZ_PADRAO) -> list[Constante]:
    """Todas as constantes ajustáveis sob `raiz`, ordenadas por arquivo e nome."""
    return list(_extrair_cacheado(raiz))


def _extrair(raiz: Path = RAIZ_PADRAO) -> list[Constante]:
    fontes: dict[str, str] = {}
    for caminho in sorted(raiz.rglob("*.py")):
        try:
            fontes[caminho.as_posix()] = caminho.read_text(encoding="utf-8")
        except OSError:
            continue

    indice = _identificadores_por_arquivo(fontes)

    saida: list[Constante] = []
    for caminho, texto in fontes.items():
        try:
            arvore = ast.parse(texto)
        except SyntaxError:
            continue
        linhas = texto.splitlines()
        for no in arvore.body:            # só o nível do MÓDULO
            if not isinstance(no, ast.Assign) or not isinstance(no.value, ast.Constant):
                continue
            if not isinstance(no.value.value, (bool, str, int, float)):
                continue
            for alvo in no.targets:
                if not isinstance(alvo, ast.Name):
                    continue
                if not alvo.id.isupper() or _ignorar(alvo.id):
                    continue
                saida.append(Constante(
                    nome=alvo.id,
                    valor=no.value.value,
                    arquivo=caminho,
                    linha=no.lineno,
                    porque=_porque(linhas, no.lineno),
                    leitores=_leitores(alvo.id, caminho, indice),
                ))
    saida.sort(key=lambda c: (c.arquivo, c.nome))
    return saida


def _linha_da_tabela(c: Constante) -> str:
    leitores = ", ".join(Path(x).name for x in c.leitores) or "—"
    porque = c.porque.replace("|", "\\|")[:110] or "—"
    return (f"| `{c.nome}` | `{c.valor_formatado}` | "
            f"[{c.arquivo}:{c.linha}]({c.arquivo}#L{c.linha}) | "
            f"{leitores} | {porque} |")


def gerar_markdown(constantes: list[Constante] | None = None) -> str:
    constantes = extrair() if constantes is None else constantes
    interruptores = [c for c in constantes if c.e_interruptor]
    numeros = [c for c in constantes if not c.e_interruptor]

    partes = [
        "# Constantes ajustáveis do BlazesBot",
        "",
        "> **ARQUIVO GERADO.** Não edite à mão -- ele é reconstruído de",
        "> `blazesbot/core/indice_de_constantes.py` e conferido por",
        "> `tests/test_indice_de_constantes.py`. Editar aqui não muda o bot;",
        "> muda o valor no arquivo indicado na coluna *onde*.",
        "",
        "Para regenerar:",
        "",
        "```",
        "./.venv/Scripts/python.exe -m blazesbot.core.indice_de_constantes",
        "```",
        "",
        "O *porquê* resumido vem do comentário logo acima da constante; o porquê",
        "COMPLETO (a medição, a alternativa que reprovou, o log de produção) mora",
        "no próprio arquivo e em `docs/decisoes/`. **Nenhum destes números é",
        "arredondamento** -- mexer sem ler a medição é repetir um experimento que",
        "já custou runs.",
        "",
        "---",
        "",
        "## Interruptores -- escolhem ENTRE CAMINHOS",
        "",
        "São os que trocam comportamento inteiro com uma palavra. Todo caminho",
        "desligado continua no código e testado, para que voltar atrás não seja",
        "ligar código não testado.",
        "",
        "| constante | valor | onde | quem lê | porquê (resumo) |",
        "|---|---|---|---|---|",
    ]
    partes += [_linha_da_tabela(c) for c in interruptores]
    partes += [
        "",
        "---",
        "",
        "## Números medidos -- tolerância, limiar, teto, cadência",
        "",
        f"{len(numeros)} constantes, agrupadas por arquivo.",
        "",
        "| constante | valor | onde | quem lê | porquê (resumo) |",
        "|---|---|---|---|---|",
    ]
    partes += [_linha_da_tabela(c) for c in numeros]
    partes.append("")
    return "\n".join(partes)


def main() -> int:
    conteudo = gerar_markdown()
    ARQUIVO_DO_INDICE.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_DO_INDICE.write_text(conteudo, encoding="utf-8")
    total = conteudo.count("\n| `")
    print(f"{ARQUIVO_DO_INDICE}: {total} constantes indexadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
