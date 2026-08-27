"""
Diários separados: arquivos de log dedicados a um assunto só.

=========================================================================
POR QUE NÃO BASTA O LOG PRINCIPAL
=========================================================================

O `logs\\sessao-atual.log` recebe TUDO de TODAS as contas em nível DEBUG. Com
quatro contas rodando ele cresce muito rápido, e procurar nele o momento exato
em que a localização parou de ser lida é procurar agulha em palheiro -- foi
exatamente essa a dificuldade nas duas ocorrências do bug.

Um diário é um arquivo com um assunto só, uma linha por evento, sempre no mesmo
formato. Ele é pequeno o bastante para ser lido inteiro, e é o arquivo que se
manda quando algo dá errado.

Diários existentes:

  logs\\localizacao.log   -- toda mudança e toda falha de leitura do nome do
                            lugar, com a posição e o rastro da cadeia de
                            ponteiros. É o arquivo do bug do ponteiro.
  logs\\eventos.log       -- o que não deveria ter acontecido: morte,
                            travamento na rota, ação sem efeito, rollback,
                            divergência entre memória e coordenada.

Os dois são acumulativos de propósito. O problema aparece com frequência mas não
sempre; apagar a cada execução jogaria fora justamente o histórico que permite
ver o padrão.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .log_limitado import ArquivoDeLogLimitado

# Teto de linhas por diário. Generoso de propósito -- o diário existe para ser
# consultado depois de dias, ao contrário do log de sessão -- mas FINITO.
LINHAS_MAXIMAS_DO_DIARIO = 20000

PASTA = Path("logs")

# Formato próprio, com data completa. Diferente do log principal (que usa só a
# hora) porque estes arquivos atravessam dias e "23:41" sem data é inútil quando
# se quer saber se o problema é sempre depois de N horas de farm.
_FORMATO = logging.Formatter(
    "%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S"
)

_criados: dict[str, logging.Logger] = {}


def _diario(nome: str, arquivo: str) -> logging.Logger:
    """Devolve (criando na primeira vez) um logger que grava só no seu arquivo.

    `propagate = False` é essencial: sem isso cada linha do diário apareceria
    também no log principal e na interface, o que anularia o motivo de existir
    um arquivo separado.
    """
    if nome in _criados:
        return _criados[nome]

    log = logging.getLogger(f"blazes_diario.{nome}")
    log.setLevel(logging.DEBUG)
    log.propagate = False

    try:
        PASTA.mkdir(exist_ok=True)
        # `ArquivoDeLogLimitado`, e NÃO `FileHandler` cru: os diários eram os
        # únicos arquivos de log do projeto SEM TETO NENHUM.
        #
        # `diario.localizacao()` grava em toda mudança de lugar E em toda FALHA de
        # leitura do nome, com o rastro da cadeia de ponteiros (são oito pontos de
        # chamada em `bot/bc/localizacao.py`). Numa máquina onde o leitor não
        # responde -- caso documentado em `_BUSCAS_SEM_LEITURA` -- isso é uma
        # linha por tentativa, por conta, por run, indefinidamente: o
        # `logs/localizacao.log` deste repositório já está em 4,8 MB.
        #
        # Cada `emit` é escrita SÍNCRONA na thread do farm, então o arquivo
        # crescendo também encarece a gravação com o tempo.
        #
        # O teto NÃO muda a intenção do diário (acumular ENTRE sessões, ao
        # contrário do log de sessão): a poda tira as linhas mais antigas e
        # preserva as recentes, que são as que se consulta.
        handler = ArquivoDeLogLimitado(PASTA / arquivo, encoding="utf-8",
                                       maximo=LINHAS_MAXIMAS_DO_DIARIO)
        handler.setFormatter(_FORMATO)
        log.addHandler(handler)
    except Exception:
        # Sem arquivo o bot continua: um diário que não abre não pode derrubar
        # o farm. As linhas simplesmente não são gravadas.
        log.addHandler(logging.NullHandler())

    _criados[nome] = log
    return log


def localizacao() -> logging.Logger:
    """Diário do nome do lugar e da posição."""
    return _diario("localizacao", "localizacao.log")


def combate() -> logging.Logger:
    """Diário da flag de combate e do quadro do alvo.

    Existe para uma pergunta específica: quando o mob morre, o que acontece com o
    HP do alvo e com a flag de combate? Ver `blazesbot/tools/vigiar_combate.py`.
    """
    return _diario("combate", "combate.log")


def eventos() -> logging.Logger:
    """Diário do que saiu do roteiro."""
    return _diario("eventos", "eventos.log")


def registrar_evento(
    conta: str,
    tipo: str,
    mensagem: str,
    posicao: tuple[int, int] | None = None,
    local: str | None = None,
) -> None:
    """Grava uma linha no diário de eventos, sempre no mesmo formato.

    O formato fixo é o que permite abrir o arquivo e varrer com o olho:

        2026-08-04 21:03:11 | creubo | MORTE | ... | pos=(80,-406) local='Secret Cemetery'
    """
    partes = [conta or "?", tipo.upper(), mensagem]
    if posicao is not None:
        partes.append(f"pos={posicao}")
    if local:
        partes.append(f"local={local!r}")
    eventos().info(" | ".join(partes))
