"""Ambiente de log (dev/prod) e contexto estruturado por thread.

Dois ambientes convivem no MESMO código:

  * ``dev``  -- default. Log detalhado (DEBUG), o usuário (o dev) pode ligar e
                desligar o debug na interface, e o JSON estruturado de dev é
                gravado em ``logs/dev/``. É onde o debugging acontece.
  * ``prod`` -- para distribuição a usuários. A interface mostra INFO+ limpo
                (sem toggle de debug), os arquivos de texto ficam em INFO+, e
                ``logs/dev/`` NÃO é criado -- o detalhe de dev só existe na
                máquina de quem desenvolve, nunca na de quem usa o bot.

Quem decide é a variável de ambiente ``BLAZES_MODO`` (default ``dev``), com
``dev`` ou ``prod``. A troca na hora de distribuir é uma linha no lançador.
"""

from __future__ import annotations

import os
import threading
import uuid

# Cache da resolução -- o env não muda durante a vida do processo.
_MODO: str | None = None
_AMBIENTES_VALIDOS = ("dev", "prod")


def _resolver() -> str:
    global _MODO
    if _MODO is None:
        valor = os.environ.get("BLAZES_MODO", "dev").strip().lower()
        _MODO = valor if valor in _AMBIENTES_VALIDOS else "dev"
    return _MODO


def modo_atual() -> str:
    """``'dev'`` ou ``'prod'``, conforme ``BLAZES_MODO`` (default ``'dev'``)."""
    return _resolver()


def eh_dev() -> bool:
    """True no ambiente de desenvolvimento (default)."""
    return _resolver() == "dev"


# ---------------------------------------------------------------------------
# Contexto estruturado por thread
#
# Cada conta roda o routine na própria thread (o supervisor escala um thread
# por conta) e todo log dessa conta sai nessa thread. Guardamos aqui o estado
# atual (login, id do run, fase) num ``threading.local``; o ``LogJsonHandler``
# lê esses valores no momento do ``emit`` para enriquecer o registro SEM
# precisar passar ``extra`` em centenas de chamadas -- o routine só marca o
# contexto em pontos seguros (início de run e troca de fase).
# ---------------------------------------------------------------------------

_local = threading.local()


def contexto(*, conta: str, id_run: str) -> None:
    """Marca o início de uma nova run no contexto da thread atual."""
    dados = getattr(_local, "dados", None)
    if dados is None:
        dados = {}
        _local.dados = dados
    dados.update({"conta": conta, "id_run": id_run})


def nova_run(conta: str) -> str:
    """Começo de uma run: o contexto ganha um `id_run` NOVO, e o devolve.

    Um lugar só gera o id -- o BC e a HH o chamam na entrada da cave --, para as
    duas caves agruparem a run do mesmo jeito no JSON de dev.
    """
    id_run = uuid.uuid4().hex[:10]
    contexto(conta=conta, id_run=id_run)
    return id_run


def fase(nome: str) -> None:
    """Registra a fase corrente do routine no contexto da thread atual."""
    dados = getattr(_local, "dados", None)
    if dados is None:
        dados = {}
        _local.dados = dados
    dados["fase"] = nome


def contexto_atual() -> dict:
    """Dict plano com o contexto estruturado do thread atual (vazio se nenhum)."""
    return dict(getattr(_local, "dados", None) or {})


def limpar() -> None:
    """Zera o contexto do thread atual (fim de sessão/thread)."""
    _local.dados = {}