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
