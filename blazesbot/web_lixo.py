"""OS ITENS DO DELETADOR, PRONTOS PARA A TELA — miniatura, nome e estado.

A janela de seleção precisa de três coisas por modelo: a MINIATURA (é o desenho
que o usuário reconhece), o NOME que ele lê, e se aquela conta apaga ou
preserva. Este módulo monta isso; `web_app.py` só delega.

=========================================================================
A MINIATURA VIAJA EMBUTIDA — NÃO É ESCOLHA
=========================================================================

A página roda em `file://` e o WebView2 RECUSA `<img src>` apontando para outro
arquivo local. A imagem tem de ir como `data:` URI, exatamente como as
miniaturas das quedas (`core/quedas.imagem_embutida`).

MEDIDO em 17/09/2026, para não virar medo: as 208 do APP dão **349 KB e
15,6 ms** para ler e codificar tudo; a HH, 26 KB e 1,2 ms. Por isso a grade vai
num payload só, sem cache, sem carga sob demanda e sem paginação. O aviso de
custo que existe em `quedas.py` é sobre PRINTS de tela — imagens dezenas de
vezes maiores.

WEBP FOI RECUSADO, e o motivo não é o tamanho: a miniatura na tela é a PROVA do
que o bot vai apagar. Reencodar faria o usuário decidir olhando um arquivo e o
bot decidir comparando outro — e num ícone de 20 px qualquer diferença de
encodagem é a diferença entre reconhecer e não reconhecer.

=========================================================================
DUAS LISTAS, MESMA ESTRUTURA
=========================================================================

`"app"` é a pasta global (`deletar/`), que o APP e a BC usam; `"hh"` é a da
Black Wind Camp (`deletar_hh/`). O que é lixo numa cave é mercadoria na outra,
e por isso cada uma tem a sua lista de exceções na conta.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .bot import deletador, nomes_do_lixo
from .config import Account, normalizar_desativados

# A lista pedida -> (pasta no disco, atributo em `AccountSettings`).
LISTAS: dict[str, tuple[Path, str]] = {
    "app": (deletador.PASTA_DO_LIXO, "app"),
    "hh": (deletador.PASTA_DO_LIXO_DA_HH, "hh"),
}


def _bloco(conta: Account, lista: str):
    """(pasta, o bloco de configuração) ou erro se a lista não existe."""
    if lista not in LISTAS:
        raise ValueError(f"lista desconhecida: {lista!r}")
    pasta, atributo = LISTAS[lista]
    return pasta, getattr(conta.settings, atributo)


def _embutir(png: Path) -> str:
    """O PNG como `data:` URI. String vazia se o arquivo sumiu no meio."""
    try:
        return "data:image/png;base64," + base64.b64encode(
            png.read_bytes()).decode("ascii")
    except OSError:
        return ""


def itens(conta: Account, lista: str) -> dict[str, Any]:
    """Tudo que a janela precisa para desenhar a grade.

    `desativados` volta junto porque a janela mostra o contador antes de o
    usuário mexer em qualquer coisa, e porque um nome guardado cujo PNG já não
    existe NÃO aparece na grade -- mas continua guardado.
    """
    pasta, bloco = _bloco(conta, lista)
    guardados = {str(n).strip() for n in bloco.desativados if str(n).strip()}
    if not pasta.is_dir():
        return {"ok": False, "erro": f"A pasta {pasta} não existe.",
                "itens": [], "desativados": sorted(guardados), "orfaos": 0}

    achados = deletador.modelos_na_pasta(pasta)
    itens_da_tela = [{
        "arquivo": png.name,
        "rotulo": nomes_do_lixo.rotulo(png.name),
        "imagem": _embutir(png),
        "ativo": png.name not in guardados,
    } for png in achados]
    na_pasta = {png.name for png in achados}
    return {
        "ok": True,
        "erro": "",
        "lista": lista,
        "pasta": pasta.name,
        "itens": itens_da_tela,
        "desativados": sorted(guardados),
        # Nome guardado cujo PNG não está mais na pasta. Fica guardado de
        # propósito: apagar a entrada faria o item voltar a ser deletado no dia
        # em que o PNG voltasse -- justo o item que a pessoa quis preservar.
        "orfaos": len(guardados - na_pasta),
    }


def guardar(conta: Account, lista: str, desativados: Any) -> dict[str, Any]:
    """Grava a seleção da conta. Devolve o que ficou guardado.

    SUBSTITUI a lista inteira -- a janela manda o estado final dela, e é isso
    que faz "desmarcar tudo" funcionar. Quem chama é que persiste em disco.
    """
    _pasta, bloco = _bloco(conta, lista)
    bloco.desativados = normalizar_desativados(desativados)
    return {"ok": True, "erro": "", "desativados": list(bloco.desativados)}
