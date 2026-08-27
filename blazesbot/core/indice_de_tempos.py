"""GERA `docs/TEMPOS.md` -- o catálogo de tudo que o bot ESPERA.

    ./.venv/Scripts/python.exe -m blazesbot.core.indice_de_tempos

=============================================================================
POR QUE ESTE ÍNDICE EXISTE, SE JÁ HÁ O `INTERRUPTORES.md`
=============================================================================

O `INTERRUPTORES.md` cataloga CONSTANTES. Este cataloga **TEMPO**, e tempo tem
três coisas que constante não tem:

1. **Nem todo tempo é constante.** Metade das esperas do bot é literal no meio
   de uma função (`ctx.tick(0.5)`), e nenhum índice de constantes as enxerga.
   Elas são justamente as que mais atrapalham quem quer acelerar o bot.
2. **Tempo se ajusta na mão, e ajuste na mão dá errado.** Pedido do usuário em
   25/08/2026: *"até para se eu alterar algo manualmente e der errado, eu tenho
   o ponto original"*. Por isso existe `docs/tempos-originais.json` -- a
   fotografia dos valores de referência. O `TEMPOS.md` mostra ATUAL e ORIGINAL
   lado a lado e **marca o que mudou**.
3. **Tempo tem NATUREZA**, e ela muda tudo na hora de mexer:

   | natureza | o que significa |
   |---|---|
   | **TETO** | prazo máximo; quem responde antes não paga. Encurtar arrisca o caso lento. |
   | **PASSO** | cadência de uma pergunta em laço. Encurtar custa CPU, não relógio. |
   | **FIXO** | espera CEGA. É aqui que há tempo a ganhar de verdade. |
   | **CONFIG** | vem do `config.json`/interface; muda por conta. |

=============================================================================
COMO ELE SE MANTÉM SOZINHO
=============================================================================

É GERADO, e não escrito à mão, pelo mesmo motivo do `INTERRUPTORES.md`: número
de linha apodrece em uma semana. Quem mexer no código e não regerar reprova em
`tests/test_indice_de_tempos.py`, que compara o arquivo com o que a extração
devolve agora.

Ou seja: **acrescentar uma espera nova ao catálogo não é disciplina, é o teste
passar.**
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path

from .indice_de_constantes import _porque

ARQUIVO_DO_INDICE = Path("docs") / "TEMPOS.md"
ARQUIVO_DOS_ORIGINAIS = Path("docs") / "tempos-originais.json"
RAIZ_PADRAO = Path("blazesbot")

# O que faz um nome ser de tempo. Nome fora desta lista com valor numérico não
# entra -- `LIMIAR_DO_VENDEDOR = 0.8` é confiança de template, não segundo.
PALAVRAS_DE_TEMPO = (
    "ESPERA", "TEMPO", "SEGUNDOS", "DELAY", "INTERVALO", "TETO", "PASSO",
    "CADENCIA", "PRAZO", "TIMEOUT", "CARENCIA", "MINUTOS", "PAUSA", "FATIA",
    "ASSENTAMENTO", "RECARGA",
)

# Nomes que casam com as palavras acima mas NÃO são tempo. Sem esta lista o
# catálogo mistura pixels e tentativas com segundos, e deixa de ser útil.
NOMES_QUE_NAO_SAO_TEMPO = frozenset({
    "PASSO_DA_GRADE", "PASSO_DO_PIXEL", "TENTATIVAS_POR_LINHA_DE_LOG",
})

# As chamadas que ESPERAM. `_sleep_interruptible` é o `tick` do supervisor.
CHAMADAS_QUE_ESPERAM = ("tick", "sleep", "_sleep_interruptible", "esperar",
                        "_esperar", "wait_if_paused")

# De qual pasta cada arquivo é, para agrupar o catálogo por onde o tempo é
# gasto. A ordem importa: a primeira que casar ganha.
AREAS = (
    ("blazesbot/bot/bc/vendor.py", "FORA DA CAVE — venda em Stone City"),
    ("blazesbot/bot/bc/ui_service.py", "FORA DA CAVE — painel, diálogos, Fay"),
    ("blazesbot/bot/bc/navigation.py", "FORA DA CAVE — montaria e trajeto"),
    ("blazesbot/bot/bc/mapa_bc.py", "FORA DA CAVE — pontos exatos"),
    ("blazesbot/bot/bc/routine.py", "A RUN — passos da rotina"),
    ("blazesbot/bot/bc/combat.py", "DENTRO DA CAVE — combate"),
    ("blazesbot/bot/bc/", "DENTRO DA CAVE — outros"),
    ("blazesbot/bot/app/", "ECOSSISTEMA APP"),
    ("blazesbot/bot/login.py", "LOGIN E RELOGIN"),
    ("blazesbot/bot/", "O SISTEMA — supervisor e watchdog"),
    ("blazesbot/core/", "CORE — capacidades compartilhadas"),
    ("blazesbot/", "OUTROS"),
)


@dataclass(frozen=True)
class Tempo:
    """Uma espera. `nome` vazio = espera literal no meio de uma função."""

    arquivo: str
    linha: int
    funcao: str
    nome: str
    valor: float
    porque: str

    @property
    def chave(self) -> str:
        """Identidade estável -- NÃO usa a linha, que muda a cada edição."""
        if self.nome:
            return f"{self.arquivo}::{self.nome}"
        return f"{self.arquivo}::{self.funcao}::{self.valor}"

    @property
    def natureza(self) -> str:
        """TETO, PASSO ou FIXO. Lido do nome E do comentário.

        É o que decide se vale mexer: encurtar um TETO arrisca o caso lento,
        encurtar um PASSO gasta CPU, e encurtar um FIXO é ganho puro.

        O COMENTÁRIO PESA TANTO QUANTO O NOME, e isso é medição, não capricho:
        `ESPERA_DO_TELEPORTE` tem cara de espera fixa e o comentário dele abre
        com *"TETO da espera do teleporte -- não é mais o tempo gasto, é o
        limite"*. Classificar só pelo nome marcaria como dívida de espera cega
        justamente uma das conversões que já foram feitas.
        """
        if not self.nome:
            return "FIXO"
        alto = self.nome.upper()
        se_diz = (self.porque or "").upper()
        if any(p in alto for p in ("TETO", "LIMITE", "MAX", "PRAZO", "TIMEOUT")):
            return "TETO"
        if any(p in alto for p in ("PASSO", "FATIA", "CADENCIA")):
            return "PASSO"
        if any(p in se_diz for p in ("TETO", "É O LIMITE", "PRAZO MÁXIMO",
                                     "NÃO É MAIS O TEMPO GASTO")):
            return "TETO"
        return "FIXO"


def _e_nome_de_tempo(nome: str) -> bool:
    if nome in NOMES_QUE_NAO_SAO_TEMPO or nome.startswith("_"):
        return False
    return any(p in nome for p in PALAVRAS_DE_TEMPO)


def _funcao_por_linha(arvore: ast.Module) -> dict[int, str]:
    """Mapa linha -> função que a contém. A mais INTERNA ganha."""
    dono: dict[int, str] = {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for filho in ast.walk(no):
            linha = getattr(filho, "lineno", None)
            if linha is not None:
                dono[linha] = no.name
    return dono


def _comentario_ao_lado(linhas: list[str], linha: int) -> str:
    """O comentário na MESMA linha da chamada -- `tick(0.5)  # o servidor`."""
    if not 0 < linha <= len(linhas):
        return ""
    texto = linhas[linha - 1]
    if "#" not in texto:
        return ""
    return texto.split("#", 1)[1].strip()


def _primeira_linha_do_docstring(arvore: ast.Module, nome_da_funcao: str) -> str:
    for no in ast.walk(arvore):
        if (isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef)
                and no.name == nome_da_funcao):
            doc = ast.get_docstring(no) or ""
            return doc.strip().splitlines()[0] if doc.strip() else ""
    return ""


def _quem_le(arvore: ast.Module, nome: str) -> str:
    """As funções do arquivo que leem esta constante, em ordem de aparição.

    Responde "onde este tempo é GASTO?", que é a pergunta de quem quer
    encurtá-lo -- o valor no topo do módulo não diz nada sozinho.
    """
    donos: list[str] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for filho in ast.walk(no):
            if isinstance(filho, ast.Name) and filho.id == nome:
                if no.name not in donos:
                    donos.append(no.name)
                break
    if not donos:
        return ""
    if len(donos) > 2:
        return ", ".join(donos[:2]) + f" (+{len(donos) - 2})"
    return ", ".join(donos)


def extrair(raiz: Path = RAIZ_PADRAO) -> list[Tempo]:
    """Todas as esperas do projeto: constantes de tempo e literais em laço."""
    achados: list[Tempo] = []

    for caminho in sorted(raiz.rglob("*.py")):
        rel = caminho.as_posix()
        try:
            texto = caminho.read_text(encoding="utf-8")
            arvore = ast.parse(texto)
        except Exception:
            continue
        linhas = texto.splitlines()
        dono = _funcao_por_linha(arvore)

        # 1. CONSTANTES DE TEMPO, no topo do módulo.
        for no in arvore.body:
            if not isinstance(no, ast.Assign):
                continue
            for alvo in no.targets:
                if not isinstance(alvo, ast.Name):
                    continue
                if not _e_nome_de_tempo(alvo.id):
                    continue
                try:
                    valor = ast.literal_eval(no.value)
                except Exception:
                    continue
                if not isinstance(valor, int | float) or isinstance(valor, bool):
                    continue
                achados.append(Tempo(rel, no.lineno, _quem_le(arvore, alvo.id),
                                     alvo.id, float(valor),
                                     _porque(linhas, no.lineno)))

        # 2. ESPERAS LITERAIS, no meio das funções.
        #
        # São as que nenhum índice de constantes enxerga, e são justamente as
        # que mais atrapalham quem quer acelerar o bot -- espera cega escondida
        # dentro de uma função não aparece em lugar nenhum.
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call) or not no.args:
                continue
            alvo = getattr(no.func, "attr", getattr(no.func, "id", ""))
            if alvo not in CHAMADAS_QUE_ESPERAM:
                continue
            try:
                valor = ast.literal_eval(no.args[0])
            except Exception:
                continue
            if not isinstance(valor, int | float) or isinstance(valor, bool):
                continue
            funcao = dono.get(no.lineno, "?")
            porque = (_comentario_ao_lado(linhas, no.lineno)
                      or _primeira_linha_do_docstring(arvore, funcao))
            achados.append(Tempo(rel, no.lineno, funcao, "", float(valor),
                                 porque))

    achados.sort(key=lambda t: (t.arquivo, t.linha))
    return achados


def area_de(arquivo: str) -> str:
    for prefixo, nome in AREAS:
        if arquivo.startswith(prefixo):
            return nome
    return "OUTROS"


def carregar_originais() -> dict[str, float]:
    if not ARQUIVO_DOS_ORIGINAIS.exists():
        return {}
    try:
        return json.loads(ARQUIVO_DOS_ORIGINAIS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def gravar_originais(tempos: list[Tempo]) -> None:
    """Fotografa os valores de HOJE como referência.

    SÓ DEVE SER CHAMADO DE PROPÓSITO. Rodar isto depois de um ajuste apaga o
    ponto de restauração -- que é justamente o que o arquivo existe para
    guardar.
    """
    dados = {t.chave: t.valor for t in tempos}
    ARQUIVO_DOS_ORIGINAIS.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_DOS_ORIGINAIS.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8")


def _segundos(valor: float) -> str:
    if valor >= 60:
        return f"{valor:g} s ({valor / 60:.0f} min)"
    return f"{valor:g} s"


def _linha_da_tabela(t: Tempo, originais: dict[str, float]) -> str:
    original = originais.get(t.chave)
    if original is None:
        coluna_original = "*novo*"
    elif abs(original - t.valor) < 1e-9:
        coluna_original = "="
    else:
        coluna_original = f"**{_segundos(original)}** ⚠"

    nome = f"`{t.nome}`" if t.nome else f"*literal em* `{t.funcao}`"
    onde = f"[{t.arquivo.split('/')[-1]}:{t.linha}]({t.arquivo}#L{t.linha})"
    # Para LITERAL a coluna é a função que o contém; para CONSTANTE é quem a
    # lê. São perguntas diferentes com a mesma resposta útil: "onde isso é
    # gasto?".
    funcao = f"`{t.funcao}`" if t.funcao else ""
    porque = (t.porque or "").replace("|", "\\|")[:110]
    return (f"| {nome} | {_segundos(t.valor)} | {coluna_original} | "
            f"{t.natureza} | {onde} | {funcao} | {porque} |")


CABECALHO = """# TEMPOS — tudo que o bot ESPERA

> **GERADO. Não edite à mão.**
> `./.venv/Scripts/python.exe -m blazesbot.core.indice_de_tempos`
> Travado por `tests/test_indice_de_tempos.py`: mexeu num tempo e não regerou,
> a suíte reprova.

## REGRA PERMANENTE

**Todo tempo novo — constante OU literal no meio de uma função — entra aqui.**
Não por disciplina: a extração acha sozinha, e o teste reprova se o arquivo
estiver velho. Basta regerar.

O que NÃO se faz sozinho é o **ponto de restauração**. Ver a seção
"Se você mudou um tempo e deu errado", no fim.

## Como ler a coluna NATUREZA

| natureza | o que é | mexer nele significa |
|---|---|---|
| **TETO** | prazo máximo; quem responde antes não paga | encurtar arrisca **o caso lento**, não o comum |
| **PASSO** | cadência de uma pergunta em laço | encurtar gasta **CPU**, não relógio |
| **FIXO** | espera **CEGA**: paga sempre, inteira | é **aqui** que há tempo a ganhar |

A regra do projeto é *"onde havia espera cega, agora se PERGUNTA"*. Cada **FIXO**
desta lista é ou uma exceção justificada, ou dívida que ninguém converteu ainda.

## A coluna ORIGINAL

`=` significa que o valor está como o de referência. **`⚠` significa que alguém
mudou** — e a coluna mostra de quanto era. É o ponto de restauração.

"""

RODAPE = """
---

## Se você mudou um tempo e deu errado

1. Ache a linha aqui pelo nome (ou pelo arquivo).
2. A coluna **ORIGINAL** com `⚠` traz o valor de referência.
3. Volte para ele no arquivo apontado pela coluna ONDE.

O ponto de restauração vive em `docs/tempos-originais.json`.

**Ele NÃO é atualizado sozinho, e isso é de propósito**: se toda geração
refotografasse os valores, o "original" seria sempre o de agora e o arquivo não
serviria para nada. Refotografar é ato deliberado:

```python
from blazesbot.core.indice_de_tempos import extrair, gravar_originais
gravar_originais(extrair())
```

Faça isso **só** quando um valor novo já estiver provado em produção e você
quiser que ele passe a ser a referência.

## O que este catálogo NÃO cobre

* **Tempo que vem da configuração** (`attack_delay`, `max_fight_seconds`,
  `launch_delay`, `time_factor`, os `delay_ms` da macro do APP): muda por conta,
  na interface, e não tem "valor original" único. Está em `blazesbot/config.py`.
* **Tempo que o JOGO impõe** (animação de montar, teleporte, efeito de poção):
  não é nosso, e o bot só pode medir.
* **Esperas calculadas** (`tick(resto)`, `tick(segundos * fator)`): o valor não
  é literal, então não há número para catalogar. Elas aparecem indiretamente,
  pelas constantes que as alimentam.
"""


def gerar_markdown(tempos: list[Tempo] | None = None) -> str:
    tempos = extrair() if tempos is None else tempos
    originais = carregar_originais()

    por_area: dict[str, list[Tempo]] = {}
    for t in tempos:
        por_area.setdefault(area_de(t.arquivo), []).append(t)

    mudados = [t for t in tempos
               if t.chave in originais
               and abs(originais[t.chave] - t.valor) > 1e-9]
    fixos = [t for t in tempos if t.natureza == "FIXO"]

    partes = [CABECALHO]
    partes.append(
        f"**{len(tempos)} tempos catalogados** — {len(fixos)} FIXOS (espera "
        f"cega), {len(tempos) - len(fixos)} entre TETO e PASSO.\n")
    if mudados:
        partes.append(f"\n**{len(mudados)} estão diferentes do original:** "
                      + ", ".join(f"`{t.nome or t.funcao}`" for t in mudados)
                      + "\n")

    for _prefixo, area in AREAS:
        if area not in por_area:
            continue
        lista = por_area.pop(area)
        partes.append(f"\n## {area}\n")
        partes.append("| tempo | atual | original | natureza | onde | função | para que serve |")
        partes.append("|---|---|---|---|---|---|---|")
        partes += [_linha_da_tabela(t, originais) for t in lista]
        partes.append("")

    partes.append(RODAPE)
    return "\n".join(partes) + "\n"


def main() -> int:
    tempos = extrair()
    if not ARQUIVO_DOS_ORIGINAIS.exists():
        # PRIMEIRA VEZ: fotografa o estado de hoje como referência. Depois disto
        # o arquivo só muda por ato deliberado -- ver `gravar_originais`.
        gravar_originais(tempos)
        print(f"{ARQUIVO_DOS_ORIGINAIS}: referência criada com "
              f"{len(tempos)} tempos.")
    conteudo = gerar_markdown(tempos)
    ARQUIVO_DO_INDICE.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_DO_INDICE.write_text(conteudo, encoding="utf-8")
    print(f"{ARQUIVO_DO_INDICE}: {len(tempos)} tempos catalogados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
