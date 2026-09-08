"""Traduções centralizadas da interface.

PT-BR é a fonte (toda chave tem PT-BR); EN e ES cobrem por cima e podem ficar
incompletos sem quebrar nada -- ver `traduzir`. Usado pelas duas interfaces
(GUI PyQt6 e Web), por isso mora em `core/`: não sabe que ecossistema existe, e
nenhuma chave aqui descreve o jogo -- descreve a interface. Contrato completo em
`docs/SKILLS.md`, seção "i18n".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

IDIOMA_PADRAO = "pt-br"
IDIOMAS_SUPORTADOS = ("pt-br", "en", "es")

_ARQUIVO = Path(__file__).resolve().parent.parent / "locales" / "traducoes.json"


def _tabela() -> dict[str, dict[str, str]]:
    with _ARQUIVO.open(encoding="utf-8") as fh:
        return json.load(fh)


def traduzir(chave: str, idioma: str, tabela: dict[str, Any] | None = None) -> str:
    """Resolve uma chave para o idioma pedido.

    Idioma fora de `IDIOMAS_SUPORTADOS`, ou chave sem entrada nesse idioma ->
    cai para PT-BR. Chave ausente da tabela inteira -> devolve a própria chave
    entre colchetes: nunca lança, para uma tela com uma chave nova ainda sem
    tradução aparecer (visivelmente) em vez de quebrar a interface.
    """
    entradas = (tabela if tabela is not None else _tabela()).get(chave)
    if entradas is None:
        return f"[{chave}]"
    idioma = idioma if idioma in IDIOMAS_SUPORTADOS else IDIOMA_PADRAO
    return entradas.get(idioma) or entradas.get(IDIOMA_PADRAO) or f"[{chave}]"


def resolver_idioma(idioma: str) -> dict[str, str]:
    """O dicionário inteiro já resolvido para um idioma -- pronto para a UI.

    A Web recebe isto uma vez por idioma suportado (`_App.constantes()`) e troca
    de idioma sem round-trip: o fallback já foi decidido aqui, o JS só lê.
    """
    tabela = _tabela()
    return {chave: traduzir(chave, idioma, tabela) for chave in tabela}


# ---------------------------------------------------------------------------
# Log: só o que é GERADO A PARTIR DA TROCA, nunca o que já foi escrito.
# ---------------------------------------------------------------------------
#
# Diferente do dicionário da UI: aqui não existe "chave" -- o call site (um dos
# ~775 espalhados por bot/bc/app/hh/core) continua chamando `log.info("texto em
# português %s", valor)` exatamente como sempre chamou. O PRÓPRIO TEXTO-FONTE é
# a chave; catalogar uma mensagem nova é só adicionar uma entrada aqui, nunca
# tocar o call site. Ver `docs/SKILLS.md`, seção "i18n", para o porquê deste
# desenho e o tamanho real do catálogo pendente (775 chamadas, ~90-140
# famílias -- isto cobre uma fração, não o todo).

_ARQUIVO_LOGS = Path(__file__).resolve().parent.parent / "locales" / "logs.json"

# Estado do PROCESSO, não da interface: os ~775 call sites de log rodam nas
# threads dos supervisores, sem acesso a `BotConfig`. `_App` (Web) ajusta isto
# no load do config e a cada troca de idioma; ver `web_app.py`.
_idioma_do_log = IDIOMA_PADRAO


def definir_idioma_do_log(idioma: str) -> None:
    global _idioma_do_log
    _idioma_do_log = idioma if idioma in IDIOMAS_SUPORTADOS else IDIOMA_PADRAO


def idioma_atual_do_log() -> str:
    return _idioma_do_log


def _tabela_logs() -> dict[str, dict[str, str]]:
    with _ARQUIVO_LOGS.open(encoding="utf-8") as fh:
        return json.load(fh)


def traduzir_mensagem_de_log(template: str) -> str:
    """Traduz o TEMPLATE de uma mensagem de log (antes do `%`-args) para
    `idioma_atual_do_log()`.

    Sem entrada no catálogo, ou catálogo sem esse idioma -> devolve o próprio
    `template`, sem alteração -- é assim que a maioria das ~775 mensagens
    (ainda não catalogadas) continua saindo em PT-BR sem quebrar nada. Chamado
    só pelo handler de log da Web (`web_app._LogHandler`); nunca lança.
    """
    if _idioma_do_log == IDIOMA_PADRAO:
        return template
    try:
        entradas = _tabela_logs().get(template)
    except (OSError, json.JSONDecodeError):
        return template
    if not entradas:
        return template
    return entradas.get(_idioma_do_log) or template
