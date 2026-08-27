"""TEMPORÁRIO -- amostragem de coordenadas de CLIQUE DIREITO.

=========================================================================
PARA QUE SERVE
=========================================================================

O bot abre diálogo de NPC com clique direito numa coordenada FIXA, medida à
mão uma vez. Quando esse clique não abre o diálogo, há duas explicações e o
log não separa as duas: ou a coordenada está um pouco fora do NPC, ou o
clique se perdeu por outro motivo (mob na frente, mouse físico por cima,
cliente ocupado).

Esta ferramenta responde à PRIMEIRA por medição: varre um grid de
coordenadas em volta do alvo conhecido, e para cada uma mede

    quantas vezes o diálogo abriu   (taxa de acerto)
    em quanto tempo ele abriu       (latência mediana)

No fim ranqueia, diz onde o alvo ATUAL ficou nesse ranking, e grava tudo em
``logs/amostragem/`` além do log de dev.

=========================================================================
O QUE NÃO É AMOSTRADO, E POR QUÊ
=========================================================================

O **Altar Stone** fica DE FORA, por decisão do usuário: é o único ponto de
clique direito cercado de mobs, e um clique que erra o NPC cai no chão e FAZ
O PERSONAGEM ANDAR -- ali isso puxa mob e custa a run. Os outros quatro
pontos são seguros: cidade, entrada da cave e o Skull Herald da saída, que
fica no covil já limpo.

=========================================================================
AS TRÊS COISAS QUE ESTA FERRAMENTA PRECISA ACERTAR
=========================================================================

1. **A ÂNCORA.** As coordenadas de tela do NPC foram medidas COM O PERSONAGEM
   NUM PONTO. Alguns passos de lado giram o NPC na tela e a amostra deixa de
   significar qualquer coisa. Por isso a posição é conferida ANTES DE CADA
   AMOSTRA, e não uma vez no começo -- ver o item 2, que é o motivo de ela
   sair do lugar sozinha.

2. **CLIQUE QUE ERRA MOVE O PERSONAGEM.** É o mesmo motivo pelo qual
   `VendorService.travel_to_vendor` se recusa a clicar de fora do ponto. Numa
   varredura de dezenas de coordenadas, a MAIORIA vai errar de propósito --
   então o passeio não é acidente, é o regime normal desta ferramenta. Sem
   reancorar entre as amostras, as últimas coordenadas do grid seriam medidas
   de um lugar completamente diferente das primeiras, e o ranking seria
   ruído com cara de dado.

3. **A ORDEM DAS AMOSTRAS.** Todas as amostras de uma coordenada em seguida
   fariam a coordenada carregar a sorte do momento (lag do servidor, mob
   passando na frente). As amostras são intercaladas em RODADAS, e a ordem de
   cada rodada é embaralhada com semente fixa: toda coordenada pega um pedaço
   de cada momento, e a medição continua reproduzível.

=========================================================================
POR QUE O TETO DA ESPERA AQUI É FIXO E LARGO
=========================================================================

O bot de verdade usa um teto que APRENDE (`ui_service.limite_da_espera_do_dialogo`),
e isso é otimização de produção: lá o objetivo é não gastar tempo numa
tentativa que não vai abrir. Aqui o objetivo é o oposto -- MEDIR a
distribuição real. Um teto que aperta cortaria justamente a cauda que
interessa, e pior: ele aprenderia com cliques deliberadamente errados.

Por isso esta ferramenta:

  * usa `TETO_DA_AMOSTRA` fixo e generoso;
  * chama `ui.dialogo_esta_aberto()` num laço próprio, e NUNCA
    `ui._esperar_o_dialogo` -- é essa função que alimenta a memória de
    aberturas do bot, e envenená-la com amostras erradas de propósito
    estragaria o teto adaptativo da produção.

=========================================================================
COMO APAGAR DEPOIS
=========================================================================

Este arquivo é uma FOLHA: nada do bot importa dele. Para remover basta apagar
este módulo e os blocos marcados TEMPORÁRIO que o citam:

    blazesbot/web_app.py         -- `_App.amostrar_cliques`,
                                    `_App.cancelar_amostragem` e os dois
                                    métodos correspondentes na `Api`
    blazesbot/gui/main_window.py -- `_amostrar_cliques`, `_fim_da_amostragem`,
                                    o sinal `amostragem_pronta` e o grupo
                                    "Amostragem de cliques" na aba Diagnóstico
    web/main.js / web/index.html -- o botão `#btn-amostrar-cliques`
"""
from __future__ import annotations

import json
import logging
import random
import statistics
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ...config import Account, BotConfig
from ...core import logmodo
from ..context import BotContext, StopRequested
from ..supervisor import AccountSupervisor
from . import mapa_bc
from .navigation import Navigator
from .ui_service import UIService

# ===========================================================================
# O GRID
# ===========================================================================

# Raio e passo, em PIXELS da janela do cliente. 12/6 dá 5 valores por eixo
# (-12,-6,0,+6,+12) = 25 coordenadas. O passo não é menor porque o alvo é um
# NPC de dezenas de pixels: diferença de 1 ou 2 px não é o que decide se o
# clique pega, e multiplicaria o tempo da varredura sem trazer sinal.
RAIO_DO_GRID = 12
PASSO_DO_GRID = 6

# Quantas vezes cada coordenada é testada. Três é o mínimo que separa "abriu
# sempre" de "abriu por sorte" sem estourar o tempo: 25 x 3 = 75 amostras, e
# cada amostra custa de 0,7 s (abriu rápido) a 2,3 s (não abriu).
AMOSTRAS_POR_COORDENADA = 3

# Semente do embaralhamento das rodadas. Fixa DE PROPÓSITO: a ordem precisa
# variar entre coordenadas (para nenhuma carregar a sorte de um momento) e ser
# a mesma entre execuções (para duas amostragens serem comparáveis).
SEMENTE_DA_ORDEM = 20260812

# ===========================================================================
# TEMPOS
# ===========================================================================

# Teto da medição. Largo de propósito -- ver o cabeçalho. As aberturas reais
# já medidas em produção foram de 283 a 458 ms; 1,5 s dá espaço para a cauda
# aparecer em vez de virar "não abriu".
TETO_DA_AMOSTRA = 1.5

# Passo do laço que pergunta se o diálogo abriu. Cada volta custa uma captura
# de tela mais um casamento de template (~11 ms medidos), então o passo é o
# piso prático da resolução da medida.
PASSO_DA_MEDICAO = 0.03

# Assentamento depois da amostra, antes de reler a posição. É o tempo de o
# personagem COMEÇAR a andar quando o clique caiu no chão: lendo na hora, a
# posição ainda seria a antiga e o `andou` sairia falso.
ASSENTAMENTO_APOS_O_CLIQUE = 0.125

# Espera depois de cada ESC, antes de reconferir se o diálogo fechou.
ESPERA_APOS_O_ESC = 0.075

# ===========================================================================
# ÂNCORA (a posição de onde se clica)
# ===========================================================================

# Precisão aceita nos pontos que o próprio bot não exige exatos (Fay, entrada
# e saída da cave). < 2 aceita 1 unidade de folga no espaço inteiro -- o
# bastante para o `goto` conseguir parar, apertado o bastante para o NPC não
# girar na tela.
ANCORA_PADRAO = 1.9

# Tentativas de encostar na âncora, e o orçamento de cada uma. Mesmo desenho
# do patamar do Altar Stone: passo real de 1 a 2 unidades, medido em 1 a 2 s.
TENTATIVAS_DE_ANCORAR = 6
SEGUNDOS_POR_TENTATIVA_DE_ANCORAR = 3.0

# Quão perto o personagem precisa estar para a ferramenta RECONHECER o ponto.
# Longe disso não se tenta adivinhar: a ferramenta não viaja, ela amostra onde
# o personagem já está (ver `_ponto_da_posicao`).
RAIO_PARA_RECONHECER = 45.0

# ===========================================================================
# TRAVAS
# ===========================================================================

# ESCs seguidos sem o diálogo fechar. Passado isto, algo está engolindo o
# teclado (menu do jogo aberto?) e as amostras seguintes seriam todas lixo.
TENTATIVAS_DE_FECHAR = 4

# Amostras seguidas SEM o diálogo abrir em NENHUMA coordenada. Numa varredura
# saudável isso não acontece: o grid passa pelo alvo bom a cada rodada. Uma
# sequência longa significa que o ponto de partida está errado, que um mob
# está na frente ou que a janela deixou de responder -- e insistir só gasta
# tempo do usuário produzindo um ranking de zeros.
FALHAS_SEGUIDAS_PARA_ABORTAR = 20

# Amostras inválidas (captura preta / sem template) seguidas. A ferramenta
# MEDE PELA TELA: sem imagem não há o que medir, e insistir não faz a captura
# voltar a funcionar.
INVALIDAS_SEGUIDAS_PARA_ABORTAR = 6

PASTA_DOS_RESULTADOS = Path("logs") / "amostragem"


# ===========================================================================
# OS PONTOS
# ===========================================================================


@dataclass(frozen=True)
class PontoDeAmostragem:
    """Um lugar de onde o bot dá clique direito para abrir diálogo."""

    chave: str
    rotulo: str
    # Callables, e não valores, porque dois dos quatro alvos dependem do
    # tamanho da janela (são calculados em runtime) e a posição do vendedor é
    # configurável por conta. Resolver na chamada garante que a ferramenta leia
    # exatamente o mesmo número que o bot leria.
    posicao: Callable[[BotContext], tuple[int, int]]
    precisao: float
    alvo: Callable[[BotContext, UIService], tuple[int, int]]
    onde: str


# O Altar Stone NÃO está aqui, e a ausência é a decisão -- ver o cabeçalho.
PONTOS: tuple[PontoDeAmostragem, ...] = (
    PontoDeAmostragem(
        chave="vendedor",
        rotulo="Rich Man (vendedor, Stone City)",
        posicao=lambda ctx: tuple(ctx.settings.vendor.vendor_position),
        # O único ponto com precisão EXATA, e não por escolha desta ferramenta:
        # é o mesmo número que `travel_to_vendor` e `_open_npc` já leem, e as
        # coordenadas de tela do NPC foram medidas com o personagem nele.
        precisao=mapa_bc.PRECISAO_NO_PONTO_DO_VENDEDOR,
        alvo=lambda ctx, ui: ctx.coords.vendor_npc,
        onde="Stone City, no ponto exato de onde o bot fala com o Rich Man.",
    ),
    PontoDeAmostragem(
        chave="fay",
        rotulo="Transport Fay (transporte, Stone City)",
        posicao=lambda ctx: mapa_bc.POSICAO_DA_FAY,
        precisao=ANCORA_PADRAO,
        # O bot não usa coordenada fixa aqui: calcula o ponto a partir do
        # tamanho da janela (`falar_com_npc` sem argumento). A amostragem tem
        # que centrar no MESMO cálculo, senão mede outra coisa.
        alvo=lambda ctx, ui: ui._ponto_padrao_do_npc(),
        onde="Stone City, ao lado da Transport Fay.",
    ),
    PontoDeAmostragem(
        chave="entrada_da_cave",
        rotulo="Skull Herald da ENTRADA (Ghost Din Woods)",
        posicao=lambda ctx: mapa_bc.ENTRADA_EM_GHOST_DIN,
        precisao=ANCORA_PADRAO,
        # `entrar_na_cave` chama `falar_com_npc(..., alturaDif=-48)`; o -48 faz
        # parte do alvo e tem que entrar no centro do grid.
        alvo=lambda ctx, ui: ui._ponto_padrao_do_npc(alturaDif=-48),
        onde="Ghost Din Woods, no ponto de onde o bot entra na cave.",
    ),
    PontoDeAmostragem(
        chave="saida_da_cave",
        rotulo="Skull Herald da SAÍDA (dentro do covil)",
        posicao=lambda ctx: mapa_bc.POSICAO_DA_SAIDA,
        precisao=ANCORA_PADRAO,
        alvo=lambda ctx, ui: ctx.coords.cave_exit_npc,
        onde="Dentro do covil, no Skull Herald que tira o personagem da cave.",
    ),
)

# ===========================================================================
# ESTADO DO TESTE (mesmo desenho de `teste_venda`)
# ===========================================================================

_PARADA = threading.Event()
_EM_ANDAMENTO = threading.Lock()


def em_andamento() -> bool:
    """True enquanto uma amostragem estiver rodando."""
    return _EM_ANDAMENTO.locked()


def cancelar() -> None:
    """Interrompe a amostragem (ligado ao botão que vira cancelar)."""
    _PARADA.set()


def pontos_disponiveis() -> list[dict[str, str]]:
    """Descrição dos pontos, para as interfaces mostrarem ao usuário."""
    return [{"chave": p.chave, "rotulo": p.rotulo, "onde": p.onde}
            for p in PONTOS]


# ===========================================================================
# GRID E RANKING (lógica pura -- é o que os testes cobrem)
# ===========================================================================


def gerar_grid(raio: int = RAIO_DO_GRID,
               passo: int = PASSO_DO_GRID) -> list[tuple[int, int]]:
    """Os deslocamentos do grid, em pixels, em volta do alvo conhecido.

    O (0,0) -- o alvo que o bot usa hoje -- está sempre presente: sem ele não
    haveria contra o que comparar o vencedor.
    """
    if passo <= 0:
        raise ValueError("passo do grid tem que ser positivo")
    eixo = list(range(-raio, raio + 1, passo))
    if 0 not in eixo:
        eixo.append(0)
        eixo.sort()
    return [(dx, dy) for dy in eixo for dx in eixo]


def ordem_das_rodadas(
    grid: list[tuple[int, int]],
    rodadas: int = AMOSTRAS_POR_COORDENADA,
    semente: int = SEMENTE_DA_ORDEM,
) -> list[tuple[int, int]]:
    """A sequência completa de amostras, intercalada por rodada.

    Cada rodada passa por TODAS as coordenadas, em ordem embaralhada. É o que
    impede uma coordenada de carregar sozinha a sorte de um momento (lag,
    mob na frente) -- ver o item 3 do cabeçalho.
    """
    rng = random.Random(semente)
    sequencia: list[tuple[int, int]] = []
    for _ in range(rodadas):
        rodada = list(grid)
        rng.shuffle(rodada)
        sequencia.extend(rodada)
    return sequencia


def ranquear(
    amostras: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Agrupa as amostras por coordenada e ordena da melhor para a pior.

    A ordem é `(-taxa, mediana)`: **taxa primeiro**. Uma coordenada que abre
    em 200 ms metade das vezes é pior que uma que abre em 400 ms sempre --
    tentativa perdida custa um ciclo inteiro da disputa, os 200 ms de
    diferença não custam nada perto disso.

    Amostras inválidas (sem captura) ficam de fora da conta: elas não dizem
    que a coordenada errou, dizem que não houve medição.
    """
    por_coord: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for a in amostras:
        if a.get("valida") is False:
            continue
        por_coord.setdefault((a["dx"], a["dy"]), []).append(a)

    linhas: list[dict[str, Any]] = []
    for (dx, dy), grupo in por_coord.items():
        aberturas = [a["ms"] for a in grupo if a["abriu"]]
        n = len(grupo)
        linhas.append({
            "dx": dx,
            "dy": dy,
            "alvo": grupo[0]["alvo"],
            "amostras": n,
            "aberturas": len(aberturas),
            "taxa": len(aberturas) / n if n else 0.0,
            # Sem nenhuma abertura não existe latência a reportar. `None` (e
            # não 0) porque 0 ordenaria como "instantâneo" e poria a pior
            # coordenada no topo do desempate.
            "mediana_ms": statistics.median(aberturas) if aberturas else None,
            "melhor_ms": min(aberturas) if aberturas else None,
            "andou": sum(1 for a in grupo if a.get("andou")),
        })

    linhas.sort(key=lambda r: (-r["taxa"],
                               r["mediana_ms"] if r["mediana_ms"] is not None
                               else float("inf")))
    for posicao, linha in enumerate(linhas, start=1):
        linha["posicao"] = posicao
    return linhas


# ===========================================================================
# EXECUÇÃO (precisa do jogo aberto)
# ===========================================================================


def resumir(resultado: dict[str, Any]) -> str:
    """O veredito em texto, para as duas interfaces mostrarem.

    Mora AQUI, e não em cada interface, pela regra do projeto: o Python decide
    e o JavaScript só exibe. Duas formatações separadas contariam a mesma
    medição de dois jeitos, e uma delas ficaria para trás.
    """
    melhor = resultado.get("melhor") or {}
    atual = resultado.get("atual")
    if not melhor:
        return "Nenhuma amostra válida."

    janela = resultado.get("janela") or []
    linhas = [
        f"{resultado.get('rotulo', '')} — clicando de "
        f"{tuple(resultado.get('ancora') or ())}"
        # A RESOLUÇÃO faz parte do resultado, não é enfeite. O deslocamento
        # vencedor é PORTÁVEL entre resoluções (a UI não escala: elemento de
        # tamanho fixo, deslocamento de tamanho fixo, tudo ancorado ao centro),
        # mas quem for adotar o número precisa saber de onde ele veio -- e se
        # algum dia uma amostragem contradisser outra feita em resolução
        # diferente, é este campo que denuncia a causa.
        + (f" a {janela[0]}x{janela[1]}" if len(janela) == 2 else ""),
        f"MELHOR: dx={melhor['dx']:+d} dy={melhor['dy']:+d} → "
        f"({melhor['alvo'][0]},{melhor['alvo'][1]}) | "
        f"abriu {melhor['aberturas']}/{melhor['amostras']} "
        f"({melhor['taxa'] * 100:.0f}%)"
        + (f" | mediana {melhor['mediana_ms']:.0f} ms"
           if melhor.get("mediana_ms") is not None else ""),
    ]
    if atual:
        linhas.append(
            f"ALVO DE HOJE (0,0): {atual['posicao']}º de "
            f"{len(resultado.get('ranking') or [])} | abriu "
            f"{atual['aberturas']}/{atual['amostras']} "
            f"({atual['taxa'] * 100:.0f}%)"
            + (f" | mediana {atual['mediana_ms']:.0f} ms"
               if atual.get("mediana_ms") is not None else ""))
    if not resultado.get("ancora_exata", True):
        linhas.append("ATENÇÃO: não encostei no ponto canônico — o ranking "
                      "vale só para a posição acima.")
    if resultado.get("parcial"):
        linhas.append(f"Varredura interrompida: {resultado['parcial']}")
    if resultado.get("arquivo"):
        linhas.append(f"Detalhe completo: {resultado['arquivo']}")
    return "\n".join(linhas)


def resumir_curto(resultado: dict[str, Any]) -> str:
    """Uma linha só, para o toast da web.

    O toast é uma pilha arredondada de uma linha que some sozinha -- um
    relatório de cinco linhas ali seria ilegível e efêmero. O detalhe fica no
    log (a interface mostra as linhas `RANKING ...`) e no arquivo.
    """
    melhor = resultado.get("melhor") or {}
    if not melhor:
        return "Nenhuma amostra válida."
    atual = resultado.get("atual")
    parte = (f"Melhor: dx={melhor['dx']:+d} dy={melhor['dy']:+d} "
             f"({melhor['taxa'] * 100:.0f}% de abertura)")
    if atual:
        parte += f" — o alvo de hoje ficou em {atual['posicao']}º"
    return parte + ". Detalhe no log."


def _ponto_da_posicao(pos: tuple[int, int] | None) -> PontoDeAmostragem | None:
    """Qual ponto de amostragem corresponde a onde o personagem está.

    Reconhecer em vez de perguntar: os quatro pontos estão a centenas de
    unidades uns dos outros (duas cidades, um bosque e uma instância), então
    não há ambiguidade a resolver -- e um seletor a mais na interface seria
    uma chance a mais de amostrar o ponto errado.

    A posição canônica do vendedor é configurável por conta, mas o
    reconhecimento usa a constante: a diferença entre as duas é de poucas
    unidades e o raio é de 45.
    """
    if pos is None:
        return None
    fixas = {
        "vendedor": mapa_bc.POSICAO_DO_VENDEDOR,
        "fay": mapa_bc.POSICAO_DA_FAY,
        "entrada_da_cave": mapa_bc.ENTRADA_EM_GHOST_DIN,
        "saida_da_cave": mapa_bc.POSICAO_DA_SAIDA,
    }
    melhor: tuple[float, PontoDeAmostragem] | None = None
    for ponto in PONTOS:
        d = mapa_bc.distancia(pos, fixas[ponto.chave])
        if d <= RAIO_PARA_RECONHECER and (melhor is None or d < melhor[0]):
            melhor = (d, ponto)
    return melhor[1] if melhor else None


class _Amostrador:
    """Roda a varredura de um ponto. Um objeto por execução."""

    def __init__(self, ctx: BotContext, ponto: PontoDeAmostragem) -> None:
        self.ctx = ctx
        self.ponto = ponto
        self.nav = Navigator(ctx)
        self.ui = UIService(ctx, navigator=self.nav)
        self.ancora = ponto.posicao(ctx)
        self.ancora_exata = True
        self.amostras: list[dict[str, Any]] = []
        self._falhas_seguidas = 0
        self._invalidas_seguidas = 0

    # -- âncora ------------------------------------------------------------

    def _no_ponto(self) -> bool:
        atual = self.ctx.memory.position()
        if atual is None:
            # Sem leitura de posição não há o que conferir. Recusar aqui
            # travaria a amostragem inteira; seguir só arrisca uma amostra.
            return True
        return mapa_bc.distancia(atual, self.ancora) <= self.ponto.precisao

    def ancorar(self, primeira_vez: bool = False) -> bool:
        """Leva o personagem à âncora e devolve se conseguiu.

        Na PRIMEIRA vez, não conseguir não é fatal: a âncora passa a ser onde
        o personagem realmente parou, e o resultado sai marcado
        `ancora_exata: false`. Isso é honesto e continua útil -- o ranking vale
        para AQUELA posição, e a posição vai gravada no arquivo. Abortar aqui
        entregaria nada em vez de entregar um dado com ressalva.
        """
        ctx = self.ctx
        alvo = self.ancora
        for _ in range(TENTATIVAS_DE_ANCORAR):
            ctx.raise_if_stopped()
            if self._no_ponto():
                return True
            self.nav.goto(alvo, tolerance=self.ponto.precisao,
                          max_seconds=SEGUNDOS_POR_TENTATIVA_DE_ANCORAR,
                          usar_mapa=False)

        atual = ctx.memory.position()
        if primeira_vez and atual is not None:
            self.ancora = atual
            self.ancora_exata = False
            ctx.log.warning(
                "Não encostei em %s; vou amostrar de %s. O ranking vale para "
                "ESTA posição -- se o bot clica de %s, remeça a amostragem "
                "de lá antes de adotar qualquer coordenada.",
                alvo, atual, alvo)
            return True

        ctx.log.warning(
            "Perdi a âncora %s (estou em %s) e não consegui voltar. As "
            "amostras seguintes seriam medidas de outro lugar.", alvo, atual)
        return False

    # -- diálogo -----------------------------------------------------------

    def fechar_dialogo(self) -> bool:
        """ESC até o diálogo fechar, CONFERINDO entre um e outro.

        O ESC é apertado só com o diálogo lido como aberto, nunca às cegas:
        com nada na tela o ESC abre o menu do sistema do jogo, e um menu
        aberto engole todo clique seguinte -- a varredura inteira viraria
        zeros sem ninguém perceber.
        """
        ctx = self.ctx
        for _ in range(TENTATIVAS_DE_FECHAR):
            ctx.raise_if_stopped()
            aberto = self.ui.dialogo_esta_aberto()
            if aberto is False:
                return True
            if aberto is None:
                # Sem imagem não se aperta NADA -- seria ESC no escuro. Mas
                # também não se desiste na hora: quadro preto costuma ser um
                # solavanco de captura, e a volta seguinte já lê. Só espera.
                ctx.tick(ESPERA_APOS_O_ESC)
                continue
            ctx.press("ESC")
            ctx.tick(ESPERA_APOS_O_ESC)
        ctx.log.warning("O diálogo não fechou depois de %d ESCs.",
                        TENTATIVAS_DE_FECHAR)
        return False

    # -- uma amostra -------------------------------------------------------

    def amostrar(self, dx: int, dy: int) -> dict[str, Any] | None:
        """Um clique direito em (alvo + deslocamento), cronometrado."""
        ctx = self.ctx
        base = self.ponto.alvo(ctx, self.ui)
        alvo = (base[0] + dx, base[1] + dy)

        if not self.fechar_dialogo():
            return None

        pos_antes = ctx.memory.position()
        comeco = time.perf_counter()
        ctx.right_click(alvo)

        abriu: bool | None = False
        ms = TETO_DA_AMOSTRA * 1000.0
        while True:
            ctx.raise_if_stopped()
            resposta = self.ui.dialogo_esta_aberto()
            decorrido = time.perf_counter() - comeco
            if resposta is True:
                abriu, ms = True, decorrido * 1000.0
                break
            if resposta is None:
                abriu, ms = None, decorrido * 1000.0
                break
            if decorrido >= TETO_DA_AMOSTRA:
                break
            ctx.tick(PASSO_DA_MEDICAO)

        # Fecha ANTES de reler a posição: com o diálogo na tela o personagem
        # não anda, e o que interessa medir é se o clique o pôs em movimento.
        if abriu is True:
            self.fechar_dialogo()
        ctx.tick(ASSENTAMENTO_APOS_O_CLIQUE)
        pos_depois = ctx.memory.position()
        andou = bool(pos_antes and pos_depois and pos_antes != pos_depois)

        amostra = {
            "dx": dx,
            "dy": dy,
            "alvo": list(alvo),
            "abriu": abriu is True,
            "valida": abriu is not None,
            "ms": round(ms, 1),
            "andou": andou,
            "posicao": list(pos_depois) if pos_depois else None,
        }
        # UMA LINHA POR AMOSTRA, em formato parseável. O JSON de dev não copia
        # campos de `extra`, só a mensagem -- então o dado tem que estar nela
        # para o log servir de fonte independente do arquivo de resultados.
        ctx.log.info(
            "AMOSTRA ponto=%s dx=%+d dy=%+d alvo=(%d,%d) abriu=%s ms=%.0f "
            "andou=%d", self.ponto.chave, dx, dy, alvo[0], alvo[1],
            "1" if abriu is True else ("?" if abriu is None else "0"),
            ms, int(andou))
        return amostra

    # -- a varredura -------------------------------------------------------

    def rodar(self) -> str:
        """Varre o grid inteiro. Devolve "" ou o motivo de ter parado antes."""
        ctx = self.ctx
        grid = gerar_grid()
        sequencia = ordem_das_rodadas(grid)

        ctx.log.info(
            "AMOSTRAGEM iniciada: ponto=%s âncora=%s exata=%s grid=%d "
            "coordenadas x %d amostras = %d cliques",
            self.ponto.chave, self.ancora, self.ancora_exata, len(grid),
            AMOSTRAS_POR_COORDENADA, len(sequencia))

        # A câmera é parte da coordenada: com ela girada o NPC não está onde a
        # medida diz. Forçado uma vez aqui, e de novo sempre que o personagem
        # andar (é o `resetar_visao` do `ancorar`, abaixo).
        self.ui.resetar_visao(forcar=True)

        for i, (dx, dy) in enumerate(sequencia, start=1):
            ctx.raise_if_stopped()

            if not self._no_ponto():
                if not self.ancorar():
                    return "perdi a âncora e não consegui voltar"
                # Andou ⇒ a câmera pode ter girado no caminho.
                self.ui.resetar_visao(forcar=True)

            amostra = self.amostrar(dx, dy)
            if amostra is None:
                return "não consegui fechar o diálogo (menu do jogo aberto?)"
            self.amostras.append(amostra)

            if not amostra["valida"]:
                self._invalidas_seguidas += 1
                if self._invalidas_seguidas >= INVALIDAS_SEGUIDAS_PARA_ABORTAR:
                    return ("a captura de tela parou de responder -- a "
                            "amostragem mede pela tela")
            else:
                self._invalidas_seguidas = 0

            if amostra["abriu"]:
                self._falhas_seguidas = 0
            else:
                self._falhas_seguidas += 1
                if self._falhas_seguidas >= FALHAS_SEGUIDAS_PARA_ABORTAR:
                    return (f"{FALHAS_SEGUIDAS_PARA_ABORTAR} cliques seguidos "
                            "sem abrir o diálogo em coordenada nenhuma")

            if i % len(grid) == 0:
                ctx.log.info("AMOSTRAGEM: rodada %d de %d concluída",
                             i // len(grid), AMOSTRAS_POR_COORDENADA)
        return ""


def _gravar(ponto: PontoDeAmostragem, dados: dict[str, Any]) -> str:
    """Grava o resultado completo e devolve o caminho (ou "" se não deu)."""
    try:
        PASTA_DOS_RESULTADOS.mkdir(parents=True, exist_ok=True)
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        caminho = PASTA_DOS_RESULTADOS / f"{ponto.chave}-{carimbo}.json"
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        return str(caminho)
    except OSError:
        # O arquivo é conveniência: o log de dev já tem uma linha por amostra.
        return ""


def _relatar(log: logging.Logger, ranking: list[dict[str, Any]]) -> None:
    """Despeja o ranking no log, do melhor para o pior."""
    log.info("=== RANKING DAS COORDENADAS (taxa primeiro, depois latência) ===")
    for linha in ranking:
        mediana = ("%.0f ms" % linha["mediana_ms"]
                   if linha["mediana_ms"] is not None else "-")
        log.info(
            "RANKING %2d. dx=%+3d dy=%+3d alvo=(%d,%d) taxa=%3.0f%% (%d/%d) "
            "mediana=%s andou=%d",
            linha["posicao"], linha["dx"], linha["dy"],
            linha["alvo"][0], linha["alvo"][1], linha["taxa"] * 100,
            linha["aberturas"], linha["amostras"], mediana, linha["andou"])


def rodar(
    config: BotConfig,
    account: Account,
    on_status: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Amostra o ponto de clique direito onde o personagem ESTÁ. Bloqueia.

    Devolve `{"ok", "erro", "ponto", "rotulo", "ancora", "ancora_exata",
    "melhor", "atual", "ranking", "arquivo", "parcial"}`.

    Roda na thread de quem chamou -- mesmo desenho de `teste_venda.rodar`.
    """
    log = logging.getLogger(f"blazes.{account.login or 'amostragem'}")

    if not _EM_ANDAMENTO.acquire(blocking=False):
        return {"ok": False, "erro": "Já existe uma amostragem rodando."}

    _PARADA.clear()
    # O supervisor não é INICIADO (a thread nunca roda): serve só para achar a
    # janela desta conta e soltar a reivindicação depois. Reescrever essa busca
    # aqui duplicaria a regra de "qual janela é de quem".
    supervisor = AccountSupervisor(config, account, on_status=on_status)
    ctx: BotContext | None = None
    try:
        log.info("=== AMOSTRAGEM DE CLIQUES — procurando a janela do jogo ===")
        adotada = supervisor._adotar_janela_existente()
        if not adotada:
            return {"ok": False, "erro": (
                "Não encontrei a janela desta conta. Abra o jogo e entre com o "
                "personagem. (Se o teste de venda estiver rodando, ele já está "
                "com a janela — pare-o antes.)")}

        pid, hwnd, ja_logado, personagem = adotada
        supervisor.pid, supervisor.hwnd = pid, hwnd
        if not ja_logado:
            return {"ok": False, "erro": (
                "O cliente encontrado está na tela de login. A amostragem "
                "exige o personagem já dentro do jogo.")}

        ctx = BotContext(config=config, account=account, pid=pid, hwnd=hwnd,
                         stop_event=_PARADA)
        ctx.char_name = personagem
        if not ctx.memory.critical_ok():
            return {"ok": False, "erro": (
                "A memória do cliente não está legível (personagem ainda "
                "carregando?). Espere entrar no mundo e tente de novo.")}

        # Contexto estruturado: dá um id para filtrar a amostragem inteira no
        # `logs/dev/blazes-dev.jsonl`, do mesmo jeito que uma run.
        logmodo.contexto(conta=account.login or "amostragem",
                         id_run=uuid.uuid4().hex[:10])
        logmodo.fase("AMOSTRAGEM")

        posicao = ctx.memory.position()
        ponto = _ponto_da_posicao(posicao)
        if ponto is None:
            lugares = "; ".join(f"{p.rotulo}: {p.onde}" for p in PONTOS)
            return {"ok": False, "erro": (
                f"Estou em {posicao} ({ctx.memory.location()}), que não é "
                f"nenhum ponto de clique direito conhecido. Leve o personagem "
                f"até um destes e tente de novo — {lugares}")}

        amostrador = _Amostrador(ctx, ponto)

        # A ferramenta MEDE PELA TELA. Sem captura ou sem o template do
        # diálogo não há medição possível, e descobrir isso depois de 75
        # cliques seria descobrir tarde.
        if amostrador.ui.dialogo_esta_aberto() is None:
            return {"ok": False, "erro": (
                "Não consigo LER a tela deste cliente (captura preta ou "
                "template state_dialogue.png ausente). A amostragem mede o "
                "diálogo pela imagem — sem ela não há o que medir.")}

        log.info("Amostragem: '%s' em %s (%s) — ponto reconhecido: %s",
                 personagem or account.login, posicao, ctx.memory.location(),
                 ponto.rotulo)
        if not amostrador.ancorar(primeira_vez=True):
            return {"ok": False, "erro": (
                f"Não consegui posicionar o personagem em {ponto.rotulo}.")}

        motivo = amostrador.rodar()
        ranking = ranquear(amostrador.amostras)
        if not ranking:
            return {"ok": False,
                    "erro": f"Nenhuma amostra válida ({motivo or 'sem dados'})."}

        _relatar(log, ranking)
        atual = next((r for r in ranking if r["dx"] == 0 and r["dy"] == 0), None)
        melhor = ranking[0]

        dados = {
            "ponto": ponto.chave,
            "rotulo": ponto.rotulo,
            "conta": account.login,
            "personagem": personagem,
            "quando": datetime.now().isoformat(timespec="seconds"),
            "ancora": list(amostrador.ancora),
            "ancora_exata": amostrador.ancora_exata,
            "montado": ctx.memory.is_mounted(),
            "janela": list(ctx.input.client_size()),
            "teto_ms": TETO_DA_AMOSTRA * 1000,
            "interrompida": motivo,
            "ranking": ranking,
            "amostras": amostrador.amostras,
        }
        arquivo = _gravar(ponto, dados)

        log.info(
            "=== AMOSTRAGEM CONCLUÍDA (%s) === melhor dx=%+d dy=%+d "
            "alvo=(%d,%d) taxa=%.0f%%; o alvo atual do bot ficou em %s",
            ponto.rotulo, melhor["dx"], melhor["dy"], melhor["alvo"][0],
            melhor["alvo"][1], melhor["taxa"] * 100,
            f"{atual['posicao']}º de {len(ranking)}" if atual else "—")
        if arquivo:
            log.info("Resultado completo em %s", arquivo)
        if motivo:
            log.warning("A varredura parou antes do fim: %s", motivo)

        resultado = {
            "ok": True,
            "erro": "",
            "ponto": ponto.chave,
            "rotulo": ponto.rotulo,
            "ancora": list(amostrador.ancora),
            "ancora_exata": amostrador.ancora_exata,
            "janela": dados["janela"],
            "melhor": melhor,
            "atual": atual,
            "ranking": ranking,
            "arquivo": arquivo,
            "parcial": motivo,
        }
        resultado["resumo"] = resumir(resultado)
        resultado["resumo_curto"] = resumir_curto(resultado)
        return resultado

    except StopRequested:
        log.info("Amostragem interrompida pelo usuário.")
        return {"ok": False, "erro": "Amostragem interrompida."}
    except Exception as exc:
        log.exception("Amostragem falhou: %s", exc)
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
    finally:
        logmodo.limpar()
        if ctx is not None:
            ctx.close()
        # Devolve o PID: sem isso o bot de verdade acharia que a janela é de
        # outra conta e abriria um cliente novo (fila de três horas).
        supervisor._release()
        _PARADA.clear()
        _EM_ANDAMENTO.release()
