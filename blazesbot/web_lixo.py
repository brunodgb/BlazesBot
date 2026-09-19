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
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .bot import deletador, nomes_do_lixo
from .config import Account, normalizar_modelos

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


def ordem_da_tela(rotulo: str) -> list:
    """A chave de ordenação da grade: alfabética, mas com NÚMERO como número.

    A ordem vinha do nome do ARQUIVO, e por isso `Belt6.png` caía depois de
    `belt56.png` -- o usuário via "Belt lvl16, lvl26, lvl36, lvl46, lvl56,
    lvl6" e tinha de procurar o menor no fim da fila.

    Ordenar pelo RÓTULO resolve as duas coisas de uma vez: itens iguais ficam
    colados (o prefixo "Armguard Fada lvl" é idêntico entre eles) e a família
    inteira aparece em sequência de nível, do menor para o maior.

    `"Belt lvl6"` vira `["belt lvl", 6, ""]`. Quebrar em pedaços alternados de
    texto e número garante que a comparação sempre encontre o mesmo tipo na
    mesma posição: onde os textos empatam, o próximo pedaço é número dos dois
    lados.
    """
    return [int(p) if p.isdigit() else p.casefold()
            for p in re.split(r"(\d+)", rotulo)]


def _embutir(png: Path) -> str:
    """O PNG como `data:` URI. String vazia se o arquivo sumiu no meio."""
    try:
        return "data:image/png;base64," + base64.b64encode(
            png.read_bytes()).decode("ascii")
    except OSError:
        return ""


def itens(conta: Account, lista: str) -> dict[str, Any]:
    """Tudo que a janela precisa para desenhar a grade.

    `apagaveis` volta junto porque a janela mostra o contador antes de o
    usuário mexer em qualquer coisa, e porque um nome escolhido cujo PNG já não
    existe NÃO aparece na grade -- mas continua guardado.
    """
    pasta, bloco = _bloco(conta, lista)
    guardados = {str(n).strip() for n in bloco.apagaveis if str(n).strip()}
    if not pasta.is_dir():
        return {"ok": False, "erro": f"A pasta {pasta} não existe.",
                "itens": [], "apagaveis": sorted(guardados), "orfaos": 0}

    achados = deletador.modelos_na_pasta(pasta)
    itens_da_tela = [{
        "arquivo": png.name,
        "rotulo": nomes_do_lixo.rotulo(png.name),
        "imagem": _embutir(png),
        # `apaga` e não `ativo`: depois da inversão de 19/09/2026 quem está na
        # lista é quem VAI SER APAGADO, e um nome ambíguo aqui vira tela
        # invertida lá.
        "apaga": png.name in guardados,
    } for png in achados]
    # A ORDEM É A DO QUE ESTÁ ESCRITO, não a do nome do arquivo -- ver
    # `ordem_da_tela`. O nome do arquivo entra só como desempate, para dois
    # rótulos iguais não trocarem de lugar entre uma abertura e outra.
    itens_da_tela.sort(key=lambda i: (ordem_da_tela(i["rotulo"]), i["arquivo"]))
    na_pasta = {png.name for png in achados}
    return {
        "ok": True,
        "erro": "",
        "lista": lista,
        "pasta": pasta.name,
        "itens": itens_da_tela,
        "apagaveis": sorted(guardados),
        # Nome escolhido cujo PNG não está mais na pasta. Fica guardado de
        # propósito: o arquivo pode voltar, e aí a escolha volta com ele.
        "orfaos": len(guardados - na_pasta),
    }


def guardar(conta: Account, lista: str, apagaveis: Any) -> dict[str, Any]:
    """Grava a seleção da conta. Devolve o que ficou guardado.

    SUBSTITUI a lista inteira -- a janela manda o estado final dela, e é isso
    que faz "desmarcar tudo" funcionar. Quem chama é que persiste em disco.
    """
    _pasta, bloco = _bloco(conta, lista)
    bloco.apagaveis = normalizar_modelos(apagaveis)
    return {"ok": True, "erro": "", "apagaveis": list(bloco.apagaveis)}


# ===========================================================================
# LEVAR A SELEÇÃO PARA OUTRA CONTA — ou para outra máquina
# ===========================================================================
#
# *"Quero que gere um arquivo json de export, pois às vezes o usuário pode
# querer compartilhar com o amigo, ou deixar salvo, então é bom conseguir
# exportar e depois ele pode importar esse arquivo em outra conta."*
#
# O ARQUIVO DIZ DE QUAL LISTA ELE É. Sem isso, importar um arquivo do APP na
# janela da HH passaria despercebido: os nomes não casariam com nada e a pessoa
# ficaria com uma seleção vazia achando que importou.
MARCA_DO_ARQUIVO = "blazesbot-itens-do-deletador"
VERSAO_DO_ARQUIVO = 1


def _dialogo(salvar: bool, sugestao: str = "") -> str:
    """Diálogo nativo de arquivo, feito no Python.

    Mesmo motivo do `procurar_client_bat`: o WebView2 não devolve o caminho
    real de um `<input type=file>`. Tkinter entra só aqui dentro -- se faltar,
    devolve vazio e quem chama avisa na tela.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        raiz = tk.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        tipos = [("Itens do deletador", "*.json"), ("Todos os arquivos", "*.*")]
        if salvar:
            caminho = filedialog.asksaveasfilename(
                title="Salvar a seleção de itens", defaultextension=".json",
                initialfile=sugestao, filetypes=tipos, parent=raiz)
        else:
            caminho = filedialog.askopenfilename(
                title="Abrir uma seleção de itens", filetypes=tipos, parent=raiz)
        raiz.destroy()
        return caminho or ""
    except Exception:
        return ""


def exportar(conta: Account, lista: str, apagaveis: Any) -> dict[str, Any]:
    """Grava a seleção num `.json` escolhido pelo usuário.

    Exporta o que está NA TELA, não o que está no disco: é o que a pessoa vê e
    o que ela espera que vá para o arquivo.
    """
    pasta, _ = _bloco(conta, lista)
    nomes = normalizar_modelos(apagaveis)
    caminho = _dialogo(True, f"itens-{pasta.name}.json")
    if not caminho:
        return {"ok": False, "erro": "", "cancelado": True}
    conteudo = {
        "blazesbot": MARCA_DO_ARQUIVO,
        "versao": VERSAO_DO_ARQUIVO,
        "lista": lista,
        "pasta": pasta.name,
        "conta": (conta.last_char_name or conta.login or "").strip(),
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "apagaveis": nomes,
    }
    try:
        Path(caminho).write_text(
            json.dumps(conteudo, indent=2, ensure_ascii=False),
            encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "erro": f"Não consegui gravar: {exc}"}
    return {"ok": True, "erro": "", "arquivo": caminho, "quantos": len(nomes)}


def importar(conta: Account, lista: str) -> dict[str, Any]:
    """Lê um `.json` e devolve a seleção dele. NÃO grava nada.

    Quem aplica é a janela, no estado em edição -- então o Cancelar ainda
    desfaz. E `ausentes` conta os nomes que não existem NESTA instalação: eles
    são mantidos (o PNG pode voltar), mas a pessoa merece saber.
    """
    pasta, _ = _bloco(conta, lista)
    caminho = _dialogo(False)
    if not caminho:
        return {"ok": False, "erro": "", "cancelado": True}
    try:
        bruto = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"ok": False, "erro": f"Não consegui ler o arquivo: {exc}"}
    if not isinstance(bruto, dict) or bruto.get("blazesbot") != MARCA_DO_ARQUIVO:
        return {"ok": False, "erro": (
            "Esse arquivo não é uma seleção de itens do BlazesBot.")}
    de_qual = str(bruto.get("lista") or "")
    if de_qual and de_qual != lista:
        return {"ok": False, "erro": (
            f"Esse arquivo é da lista '{de_qual}' e esta janela é da '{lista}'. "
            "Abra a janela da outra aba para importá-lo.")}
    nomes = normalizar_modelos(bruto.get("apagaveis"))
    na_pasta = {png.name for png in deletador.modelos_na_pasta(pasta)}
    return {"ok": True, "erro": "", "apagaveis": nomes,
            "quantos": len(nomes), "de": str(bruto.get("conta") or ""),
            "ausentes": len([n for n in nomes if n not in na_pasta])}

# ===========================================================================
# O PORTÃO DO INICIAR — quem vai abrir a bolsa e não apagar nada
# ===========================================================================
#
# Depois da inversão, seleção vazia é o estado NORMAL de conta recém-criada. O
# risco disso é silencioso: a conta farma a noite inteira, a bolsa enche, e o
# usuário só descobre quando o inventário transborda -- exatamente a falha que
# o deletador existe para evitar.
#
# Por isso a conferência acontece no INICIAR, com confirmação: *"quando ele
# clicar em ok realmente começa o bot, se ele clicar em cancelar não vai
# começar o bot para aquelas contas"* (usuário, 19/09/2026).
#
# O QUE NÃO ENTRA NA LISTA, e por quê:
#
#   limpeza desligada  -- `Apagar o lixo a cada = 0`, ou "jogar o lixo fora"
#                         desmarcado na HH: o usuário já decidiu isso, e cobrar
#                         de novo em todo Iniciar transforma o aviso em OK
#                         automático.
#   sem tecla de pet   -- sem auto-pick o personagem não cata item do chão, a
#                         bolsa não enche e não há o que apagar. A regra é do
#                         jogo e já vale na Fada (`bot/fada_montagem.py`).
#   BC                 -- só APP e HH apagam item hoje.


def lista_ociosa(config: Any, conta: Account) -> str:
    """A lista que esta conta vai abrir e não usar: `"app"`, `"hh"` ou `""`."""
    funcao = config.funcao_ativa_da_conta(conta)
    if funcao not in LISTAS:
        return ""
    if not (getattr(conta.settings.keys, "pet_summon", "") or "").strip():
        return ""
    bloco = getattr(conta.settings, LISTAS[funcao][1])
    ligada = (bloco.apagar_lixo_a_cada > 0 if funcao == "app"
              else bool(bloco.deletar_lixo))
    return funcao if ligada and not bloco.apagaveis else ""


def time_do_app(config: Any, conta: Account) -> list[Account]:
    """O time do APP a que esta conta pertence: líder e seguidores.

    O TIME É ATÔMICO no desligamento, decisão do usuário: *"se o líder for
    inativado, todos do time são inativados, e se algum do time for inativado o
    contrário também deve acontecer"*. O motivo é mecânico -- o seguidor só roda
    a macro enquanto o líder está com o APP ligado, então desligar um sem o
    outro deixaria contas em estado indefinido.

    Fora de time, devolve a própria conta.
    """
    seguidores = [str(x).strip().lower()
                  for x in (conta.settings.app.time_logins or [])]
    if seguidores:
        lider = conta
    else:
        meu = (conta.login or "").strip().lower()
        lider = next((c for c in config.accounts
                      if meu in [str(x).strip().lower()
                                 for x in (c.settings.app.time_logins or [])]),
                     None)
        if lider is None:
            return [conta]
        seguidores = [str(x).strip().lower()
                      for x in (lider.settings.app.time_logins or [])]
    por_login = {(c.login or "").strip().lower(): c for c in config.accounts}
    time = [lider] + [por_login[n] for n in seguidores if n in por_login]
    vistos, saida = set(), []
    for c in time:
        if id(c) not in vistos:
            vistos.add(id(c))
            saida.append(c)
    return saida


def contas_ociosas(config: Any) -> list[dict[str, Any]]:
    """As contas ATIVAS que vão abrir a bolsa e não apagar nada."""
    saida: list[dict[str, Any]] = []
    for conta in config.enabled_accounts():
        lista = lista_ociosa(config, conta)
        if not lista:
            continue
        time = time_do_app(config, conta) if lista == "app" else [conta]
        saida.append({
            # `garantir_uid` e não `uid`: conta vinda de `config.json` editado à
            # mão pode não ter um, e uid vazio no payload viraria um botão que
            # não desliga nada -- ou, pior, que casa com todas.
            "uid": conta.garantir_uid(),
            "login": conta.login or "",
            "nick": (conta.last_char_name or "").strip(),
            "lista": lista,
            # Quem cai junto se esta conta for desligada -- o usuário precisa
            # ver isso ANTES de decidir, não descobrir depois.
            "time": [(c.login or "") for c in time if c is not conta],
        })
    return saida


def desligar_funcao(config: Any, uids: Any) -> list[str]:
    """Desliga a função das contas pedidas E dos times delas.

    Elas continuam ATIVAS -- logam e relogam normalmente, só não farmam. É o que
    o usuário pediu para poder ajustar a seleção enquanto o resto roda.
    """
    # UID VAZIO NÃO CASA COM NINGUÉM. Sem este filtro, um `""` na lista (conta
    # sem uid no arquivo) casaria com TODA conta sem uid -- e, com a regra do
    # time, desligaria a função do bot inteiro de uma vez.
    pedidos = {str(u).strip() for u in (uids or []) if str(u).strip()}
    if not pedidos:
        return []
    alvos: list[Account] = []
    for conta in config.accounts:
        if str(conta.uid or "").strip() in pedidos:
            alvos.extend(time_do_app(config, conta)
                         if config.funcao_ativa_da_conta(conta) == "app"
                         else [conta])
    desligadas: list[str] = []
    vistos: set[int] = set()
    for conta in alvos:
        if id(conta) in vistos:
            continue
        vistos.add(id(conta))
        if config.funcao_ativa_da_conta(conta):
            config.definir_funcao_da_conta(conta, "")
            desligadas.append(conta.login or "")
    return desligadas
