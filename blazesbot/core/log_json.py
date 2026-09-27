"""Sink de log estruturado (JSONL) só para debug do desenvolvedor.

Gravado em ``logs/dev/blazes-dev.jsonl``, uma linha por registro, enriquecido
com o contexto do ``logmodo`` (conta, id_run, fase) + o que o próprio
``LogRecord`` carrega (arquivo, função, linha, thread, exceção). Nunca vai
para a interface -- fica por trás, para analisar/ingestar quando algo quebra.

O handler só é anexado em modo dev (``setup_logging``); em prod a pasta
``logs/dev/`` nem é criada -- o detalhe de dev só existe na máquina de quem
desenvolve.

Cada registro é UMA linha física de JSON (o ``json.dumps`` escapa quebras de
linha dentro de strings), então o teto de linhas do ``ArquivoDeLogLimitado``
conta registros corretamente e a poda mantém as últimas N runs/eventos.
"""

from __future__ import annotations

import json
import logging
import time

from . import logmodo
from .log_limitado import ArquivoDeLogLimitado

# Quantos registros o JSON dev guarda (reusa a poda por linha do arquivo).
LOG_JSON_MAXIMO = 4000

# A FOLGA É O PRÓPRIO MÁXIMO, e não os 100 dos logs de 500 linhas. Cada poda
# relê e reescreve o arquivo quente INTEIRO, dentro do `emit`, com o lock que
# as 7 contas dividem: com folga de 100 eram ~40 reescritas de 1,6 MB para
# cada 1,6 MB de dado novo (~14 GB/dia de escrita para ~180 MB de conteúdo,
# 72 s de bloqueio nas threads das contas em 12 h, pico de 1,1 s -- medido em
# 26-27/09/2026). Com folga = máximo a poda roda 40x menos e cada uma descarta
# metade do arquivo, que vai inteira para o arquivo morto. Custo: o quente
# chega a 2x o teto antes de podar (~3 MB).
FOLGA_DO_LOG_JSON = LOG_JSON_MAXIMO

# `formatException` é método do `Formatter`, não do `Handler` -- o LogJsonHandler
# estende um Handler, então usa-se um Formatter só para formatar a exceção.
_FMT_EXC = logging.Formatter()


class LogJsonHandler(ArquivoDeLogLimitado):
    """`ArquivoDeLogLimitado` que escreve JSON enriquecido em vez de texto."""

    def __init__(
        self,
        caminho,
        *,
        maximo: int = LOG_JSON_MAXIMO,
        folga: int = FOLGA_DO_LOG_JSON,
    ) -> None:
        # `arquivar=True`: ESTE é o log que alimenta a calibração, e o que a
        # poda descartava era a evidência. Ver `DIAS_DE_ARQUIVO_MORTO` em
        # `log_limitado.py` para a medição (28 minutos de cobertura).
        super().__init__(caminho, mode="a", encoding="utf-8",
                         maximo=maximo, folga=folga, arquivar=True)

    def format(self, record: logging.LogRecord) -> str:
        """Uma linha JSON com o contexto rico para debugar o sistema."""
        nome = record.name
        partes = nome.split(".", 1)
        conta_logger = partes[1] if len(partes) > 1 else ""
        ctx = logmodo.contexto_atual()

        dados = {
            # COM MILISSEGUNDOS, e isso é ferramenta de medição, não capricho.
            #
            # Sem eles o log grava `20:02:52` e não dá para medir nada abaixo de
            # um segundo -- foi o que travou a primeira análise dos tempos de
            # fora da cave: as esperas em questão são de 0,05 a 0,9 s e todas
            # apareciam como "1,00s" no log. `%f` traz microssegundos; ficam 3
            # casas, que é a resolução que importa para clique e diálogo.
            "ts": (time.strftime("%Y-%m-%d %H:%M:%S",
                                 time.localtime(record.created))
                   + f".{int(record.msecs):03d}"),
            "nivel": record.levelname,
            "conta": conta_logger or ctx.get("conta") or None,
            "id_run": ctx.get("id_run"),
            "fase": ctx.get("fase"),
            "logger": nome,
            "msg": record.getMessage(),
            "arquivo": record.pathname,
            "linha": record.lineno,
            "funcao": record.funcName,
            "thread": getattr(record, "threadName", None),
        }
        if record.exc_info:
            dados["exc"] = _FMT_EXC.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False)