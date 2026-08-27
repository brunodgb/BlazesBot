"""TEMPORÁRIO -- recorta o template do painel de membro do time.

Módulo FOLHA: nada do bot importa isto. Mora em `bot/` e não em `bc/` nem em
`app/` porque o painel de time serve os DOIS ecossistemas -- o reset do boss lê
o time, e a Fairy vai ler as mesmas linhas.

=========================================================================
POR QUE ISTO EXISTE
=========================================================================

`bot/bc/team.py` carrega `TEAM_MEMBER_TEMPLATE = "state_team_member.png"` para
responder "estou em time?" quando a memória não responde. **Esse arquivo nunca
existiu em `data/templates/`.** `templates.load()` devolve `None`,
`_time_pela_imagem()` devolve `None`, e `estado_do_time` devolve `None` sempre.

Somado a `team_size()` também não responder, o resultado é que **hoje o bot não
sabe se está em time por caminho nenhum** -- e o preço está medido no próprio
`team.py`: onze aceites falsos seguidos para um único convite.

=========================================================================
COMO ELE ACHA O RECORTE SEM NINGUÉM MEDIR NADA
=========================================================================

A tentação era tirar as coordenadas de um print ou copiar as do GhostBot
((30,200)/(30,285)/(30,365)/(30,445), da resolução e do cliente DELE). As duas
são o "número escolhido no olho" que o `CLAUDE.md` proíbe.

O caminho honesto usa o fato de que **o painel se REPETE**: cada companheiro
desenha a mesma moldura, uma abaixo da outra, com espaçamento uniforme. Então
um bom recorte é aquele que, procurado no próprio quadro, **se acha N vezes em
intervalos regulares**. Isso é verificável sem régua:

  1. varre recortes candidatos numa faixa da coluna esquerda;
  2. procura cada candidato no quadro inteiro com `find_all_templates` -- a
     MESMA função que vai consumir o template depois;
  3. pontua por: quantos achou (>= 2), quão REGULAR é o espaçamento vertical,
     e quão alinhados em X estão;
  4. recusa recorte LISO (`region_is_uniform`), que casaria em todo lugar;
  5. fica com o melhor, DESENHA o que encontrou num JPEG e salva o PNG.

O critério de aceite é o mesmo que o consumidor usa. Um template que passa aqui
é um template que funciona lá -- não "parece certo na imagem".

**NÃO CLICA EM NADA.** Só captura.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..config import Account, BotConfig
from ..core.vision import (
    capture_window,
    crop,
    find_all_templates,
    frame_is_blank,
    region_is_uniform,
)
from .supervisor import AccountSupervisor

_PARADA = threading.Event()
_EM_ANDAMENTO = threading.Lock()

# Nome que `bot/bc/team.py` procura. Mudar aqui sem mudar lá deixa o arquivo
# gravado e o consumidor cego -- que é exatamente o defeito de hoje.
NOME_DO_TEMPLATE = "state_team_member.png"
PASTA_DE_TEMPLATES = Path("data") / "templates"
PASTA_DE_PROVAS = Path("logs") / "recorte_do_time"

# -- faixa onde o painel de time pode estar ---------------------------------
#
# NÃO são as coordenadas do painel: são os LIMITES DA BUSCA, e por isso podem
# ser generosos. O painel fica na coluna esquerda, abaixo do retrato do próprio
# personagem (`coords.own_portrait` = 44,48). A faixa cobre do fim do retrato
# até bem abaixo do quarto companheiro, com folga para outras resoluções --
# quem decide onde ele está de fato é a repetição, não este retângulo.
FAIXA_X = (0, 200)
FAIXA_Y = (120, 620)

# Alturas de linha a experimentar, em pixels. A moldura de um companheiro é
# menor que a do próprio personagem; a varredura cobre dos ~28 px aos ~76 px.
ALTURAS = (28, 34, 40, 46, 52, 60, 68, 76)
PASSO_VERTICAL = 4          # de quantos em quantos pixels tentar um recorte novo
LARGURA_DO_RECORTE = 120    # cobre retrato + nick + barras, sem sair da coluna

# Um casamento fraco não conta. 0.90 é o mesmo patamar que o deletador usa para
# item de bolsa, e aqui a moldura é ainda mais repetível que um ícone.
LIMIAR = 0.90

# Menos de dois casamentos não prova repetição -- prova que o recorte se achou a
# si mesmo, o que qualquer recorte faz.
MINIMO_DE_LINHAS = 2

# Espaçamento vertical: desvio máximo aceito entre os intervalos, em pixels. As
# linhas são desenhadas pelo cliente com passo fixo; 6 px de folga cobre ruído
# de compressão sem aceitar um conjunto irregular (que seria coincidência, não
# estrutura).
FOLGA_DO_ESPACAMENTO = 6.0

# Recorte liso casa em todo lugar. `region_is_uniform` já é o teste que o
# projeto usa para "esta linha está vazia?", e serve igual aqui.
DESVIO_MINIMO = 12.0


def em_andamento() -> bool:
    return _EM_ANDAMENTO.locked()


def cancelar() -> None:
    _PARADA.set()


# ===========================================================================
# A busca -- lógica PURA, recebe o quadro e devolve o que achou
# ===========================================================================

def _candidatos(quadro: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Recortes a experimentar, como (x, y, largura, altura)."""
    altura_do_quadro, largura_do_quadro = quadro.shape[:2]
    x = max(0, FAIXA_X[0])
    largura = min(LARGURA_DO_RECORTE, largura_do_quadro - x)
    if largura <= 0:
        return []

    saida: list[tuple[int, int, int, int]] = []
    for altura in ALTURAS:
        y = FAIXA_Y[0]
        while y + altura <= min(FAIXA_Y[1], altura_do_quadro):
            saida.append((x, y, largura, altura))
            y += PASSO_VERTICAL
    return saida


def _regularidade(ys: list[int]) -> tuple[float, float]:
    """(espaçamento médio, pior desvio) de uma lista de alturas ordenada."""
    if len(ys) < 2:
        return 0.0, float("inf")
    intervalos = [b - a for a, b in pairwise(ys)]
    medio = sum(intervalos) / len(intervalos)
    if medio <= 0:
        return 0.0, float("inf")
    pior = max(abs(i - medio) for i in intervalos)
    return medio, pior


def avaliar_recorte(
    quadro: np.ndarray,
    regiao: tuple[int, int, int, int],
    cinza: np.ndarray | None = None,
) -> dict[str, Any] | None:
    """Pontua um recorte candidato. `None` quando ele não serve.

    A pontuação é deliberadamente simples e explicável: quantas linhas achou,
    depois quão regular ficou o espaçamento. Um número composto que ninguém
    consegue interpretar seria pior que nenhum -- quando desse errado, ninguém
    saberia por quê.
    """
    if region_is_uniform(quadro, regiao, max_std=DESVIO_MINIMO):
        return None                      # liso: casaria em todo lugar

    modelo = crop(quadro, regiao)
    if modelo is None or modelo.size == 0:
        return None

    modelo_cinza = (cv2.cvtColor(modelo, cv2.COLOR_BGR2GRAY)
                    if modelo.ndim == 3 else modelo)

    # DUAS OTIMIZAÇÕES, e as duas mudam ordem de grandeza -- a varredura testa
    # ~960 recortes, então tudo que roda por recorte custa 960x.
    #
    # 1. `cinza` chega PRONTO de `melhor_recorte`. Sem isso, `find_all_templates`
    #    converteria o quadro inteiro (1024x768) a cada candidato.
    #    `colorido=True` com quadro E template já em cinza é o que diz "não
    #    converta de novo": a checagem de dimensão da função compara `ndim`, e
    #    aqui os dois têm 2.
    # 2. `region` limita o casamento à coluna esquerda. O `matchTemplate` passa
    #    de 1024x768 para ~200x500 -- 7% da área. Os centros continuam vindo em
    #    coordenada do quadro original, porque a função soma o deslocamento.
    #
    # Medido: 41 s -> 2 s na suíte de teste, com o mesmo resultado.
    if cinza is None:
        cinza = (cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
                 if quadro.ndim == 3 else quadro)

    faixa = (FAIXA_X[0], FAIXA_Y[0],
             min(FAIXA_X[1], cinza.shape[1]) - FAIXA_X[0],
             min(FAIXA_Y[1], cinza.shape[0]) - FAIXA_Y[0])

    centros = find_all_templates(cinza, modelo_cinza, threshold=LIMIAR,
                                 region=faixa, colorido=True)
    if len(centros) < MINIMO_DE_LINHAS:
        return None

    # Só interessam os que estão na coluna esquerda: um casamento solto no meio
    # da cena 3D é ruído, e entraria no cálculo do espaçamento estragando tudo.
    na_coluna = [c for c in centros if FAIXA_X[0] <= c[0] <= FAIXA_X[1]]
    if len(na_coluna) < MINIMO_DE_LINHAS:
        return None

    # Alinhamento horizontal: linhas de uma lista começam todas na mesma coluna.
    xs = [c[0] for c in na_coluna]
    if max(xs) - min(xs) > FOLGA_DO_ESPACAMENTO:
        return None

    ys = sorted(c[1] for c in na_coluna)
    espacamento, pior_desvio = _regularidade(ys)
    if pior_desvio > FOLGA_DO_ESPACAMENTO:
        return None

    return {
        "regiao": regiao,
        "linhas": len(na_coluna),
        "espacamento": espacamento,
        "pior_desvio": pior_desvio,
        "centros": sorted(na_coluna, key=lambda c: c[1]),
    }


def melhor_recorte(quadro: np.ndarray) -> dict[str, Any] | None:
    """O recorte que melhor se repete na coluna esquerda do quadro.

    Ordem de preferência: mais linhas primeiro (achar os 4 companheiros vale
    mais que achar 2), depois o espaçamento mais regular. Empate em ambos, o
    recorte mais alto -- mais pixels de moldura, menos chance de casar por
    acaso num pedaço de barra de vida.
    """
    cinza = (cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
             if quadro.ndim == 3 else quadro)
    achados = [a for a in (avaliar_recorte(quadro, r, cinza)
                           for r in _candidatos(quadro))
               if a is not None]
    if not achados:
        return None
    achados.sort(key=lambda a: (-a["linhas"], a["pior_desvio"], -a["regiao"][3]))
    return achados[0]


# ===========================================================================
# A prova visual
# ===========================================================================

def desenhar_prova(quadro: np.ndarray, achado: dict[str, Any]) -> np.ndarray:
    """Marca no quadro o que foi encontrado, para conferência humana.

    Ver ONDE casou importa mais que ver QUANTO: uma linha marcada em cima de
    algo que não é companheiro salta aos olhos numa imagem, e numa lista de
    notas não. Mesma lição da `afericao`.
    """
    prova = quadro.copy()
    _, _, largura, altura = achado["regiao"]

    for ordem, (cx, cy) in enumerate(achado["centros"], start=1):
        x1, y1 = cx - largura // 2, cy - altura // 2
        cv2.rectangle(prova, (x1, y1), (x1 + largura, y1 + altura),
                      (0, 0, 255), 2)
        cv2.putText(prova, f"membro {ordem}", (x1 + 4, max(12, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1,
                    cv2.LINE_AA)

    # O recorte que virou template, em verde, para separar "o modelo" de "onde
    # ele casou".
    rx, ry, rw, rh = achado["regiao"]
    cv2.rectangle(prova, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 1)
    cv2.putText(prova,
                f"{achado['linhas']} linhas, passo {achado['espacamento']:.1f}px, "
                f"desvio {achado['pior_desvio']:.1f}px",
                (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1,
                cv2.LINE_AA)
    return prova


# ===========================================================================
# A ferramenta
# ===========================================================================

def rodar(
    config: BotConfig,
    account: Account,
    on_status: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Fotografa a tela com o time formado e recorta o template do membro.

    Devolve `{"ok", "erro", "arquivo", "prova", "linhas", "espacamento"}`.
    Exige o **bot parado** e o time **já formado** na tela.
    """
    log = logging.getLogger(f"blazes.{account.login or 'recorte_do_time'}")

    if not _EM_ANDAMENTO.acquire(blocking=False):
        return {"ok": False, "erro": "Já existe um recorte rodando."}

    _PARADA.clear()
    supervisor = AccountSupervisor(config, account, on_status=on_status)
    try:
        log.info("=== RECORTANDO O TEMPLATE DO PAINEL DE TIME ===")
        adotada = supervisor._adotar_janela_existente()
        if not adotada:
            return {"ok": False, "erro": (
                "Não encontrei a janela desta conta. Abra o jogo e entre com o "
                "personagem.")}

        pid, hwnd, ja_logado, personagem = adotada
        supervisor.pid, supervisor.hwnd = pid, hwnd
        if not ja_logado:
            return {"ok": False, "erro": (
                "O cliente encontrado está na tela de login.")}
        log.info("Janela adotada: %s (pid %s)", personagem, pid)

        quadro = capture_window(hwnd)
        if quadro is None or frame_is_blank(quadro):
            return {"ok": False, "erro": (
                "A captura veio em branco. A janela pode ter acabado de abrir.")}

        achado = melhor_recorte(quadro)
        if achado is None:
            return {"ok": False, "erro": (
                "Não achei nenhuma estrutura que se repita na coluna esquerda. "
                "O time está formado na tela? A ferramenta precisa de PELO "
                f"MENOS {MINIMO_DE_LINHAS} companheiros visíveis para provar "
                "que achou uma lista, e não um pedaço qualquer da interface.")}

        PASTA_DE_TEMPLATES.mkdir(parents=True, exist_ok=True)
        PASTA_DE_PROVAS.mkdir(parents=True, exist_ok=True)

        modelo = crop(quadro, achado["regiao"])
        destino = PASTA_DE_TEMPLATES / NOME_DO_TEMPLATE
        cv2.imwrite(str(destino), modelo)

        prova = PASTA_DE_PROVAS / f"time-{personagem or pid}.jpg"
        cv2.imwrite(str(prova), desenhar_prova(quadro, achado),
                    [int(cv2.IMWRITE_JPEG_QUALITY), 88])

        log.info("Template gravado em %s (%sx%s)", destino,
                 achado["regiao"][2], achado["regiao"][3])
        log.info("%s linhas, passo %.1f px, pior desvio %.1f px",
                 achado["linhas"], achado["espacamento"], achado["pior_desvio"])
        log.info("Prova visual em %s -- CONFIRA antes de confiar", prova)

        return {
            "ok": True,
            "arquivo": str(destino),
            "prova": str(prova),
            "linhas": achado["linhas"],
            "espacamento": round(achado["espacamento"], 1),
            "regiao": achado["regiao"],
        }

    except Exception as exc:
        log.exception("Recorte falhou: %s", exc)
        return {"ok": False, "erro": str(exc)}
    finally:
        # SEM ISTO o bot de verdade veria a janela como de outra conta e abriria
        # um cliente novo -- fila de três horas. Mesma regra das outras
        # ferramentas temporárias.
        try:
            supervisor._release()
        except Exception:
            pass
        _EM_ANDAMENTO.release()


# ===========================================================================
# Linha de comando -- `14-RECORTAR-TIME.bat`
# ===========================================================================

def main() -> int:
    import sys

    # ==================================================================
    # A SAÍDA VAI PARA ARQUIVO TAMBÉM, E ISSO É CORREÇÃO DE DEFEITO
    # ==================================================================
    #
    # Esta ferramenta só escrevia em `sys.stdout`. O `.bat` se reeleva com
    # `Start-Process -Verb RunAs`, que abre uma janela NOVA e fecha a original --
    # então qualquer falha antes do `pause` morria com a janela, sem deixar
    # rastro em lugar nenhum.
    #
    # Foi exatamente o que aconteceu em 19/08/2026: três execuções, nenhum
    # template, nenhuma prova, nenhuma linha em log nenhum, e o usuário relatando
    # *"abre e fecha sozinho, não consigo copiar nada"*. A causa real era uma
    # falta de aspas no `.bat` -- e o diagnóstico levou três tentativas porque a
    # ferramenta de diagnóstico não deixava diagnóstico.
    #
    # Ferramenta cuja única saída é um console que fecha não serve para
    # investigar nada. O arquivo é sobrescrito a cada execução de propósito: o
    # que interessa é a ÚLTIMA tentativa, e um histórico aqui só cresceria sem
    # ninguém ler.
    PASTA_DE_PROVAS.mkdir(parents=True, exist_ok=True)
    destino_do_log = PASTA_DE_PROVAS / "recorte.log"
    logging.basicConfig(
        level=logging.INFO, format="%(message)s", force=True,
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(destino_do_log, mode="w",
                                      encoding="utf-8")])

    # E TODA mensagem passa a sair por `dizer`, não por `print`.
    #
    # Sombrear `print` dentro da função era a tentação óbvia, e é defeito: o
    # `def print` local torna o nome local em TODA a função, então o
    # `_print_original = print` da linha anterior levanta `UnboundLocalError`
    # antes de qualquer coisa rodar. O ruff pegou (`F823`).
    #
    # `dizer` resolve sem truque: o `logging` já tem os DOIS destinos ligados,
    # então uma chamada escreve no console e no arquivo.
    def dizer(*partes) -> None:
        logging.getLogger(__name__).info(
            " ".join(str(p) for p in partes))

    # Mesma razão das outras ferramentas: o cliente roda elevado, e o Windows
    # (UIPI) descarta em silêncio o que vem de processo não elevado. Aqui só se
    # captura, mas a adoção da janela mexe com o processo do jogo.
    from main import require_admin
    require_admin()

    config = BotConfig.load()
    contas = [c for c in config.accounts if c.enabled] or config.accounts
    if not contas:
        dizer("Nenhuma conta configurada.")
        return 1

    pedido = [a for a in sys.argv[1:] if not a.startswith("-")]
    if pedido:
        contas = [c for c in contas if (c.login or "").lower() == pedido[0].lower()]
        if not contas:
            dizer(f"Não achei a conta {pedido[0]!r} na configuração.")
            return 1

    dizer("O time precisa estar FORMADO e VISÍVEL na tela do cliente.")
    dizer("O bot precisa estar PARADO.")
    dizer()

    for conta in contas:
        dizer(f"Tentando pela conta {conta.login or '(sem login)'}...")
        resultado = rodar(config, conta)
        if resultado.get("ok"):
            dizer()
            dizer(f"  template : {resultado['arquivo']}")
            dizer(f"  prova    : {resultado['prova']}   <- ABRA E CONFIRA")
            dizer(f"  achou    : {resultado['linhas']} linhas, "
                  f"passo {resultado['espacamento']} px")
            dizer()
            dizer("Se a prova marcou algo que NÃO é companheiro de time, apague")
            dizer("o template e rode de novo com o time realmente na tela --")
            dizer("template errado é pior que template nenhum.")
            return 0
        dizer(f"  {resultado.get('erro')}")

    dizer()
    dizer("Nenhuma conta produziu recorte.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
