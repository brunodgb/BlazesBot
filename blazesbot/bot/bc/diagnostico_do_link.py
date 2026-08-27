"""TEMPORÁRIO -- fotografa a tela em volta do clique ESQUERDO no link do NPC.

=========================================================================
A PERGUNTA QUE ISTO EXISTE PARA RESPONDER
=========================================================================

Medido no `logs/dev/blazes-dev.jsonl` de 13/08/2026 (fase ENTRAR, 26 min,
ZERO entradas na cave):

    clique direito LOGO APÓS um clique no link :  41/291 = 14% de abertura
    clique direito em qualquer outro momento   : 251/320 = 78% de abertura

Cinco vezes e meia de diferença. Não é ruído e não é recarga do NPC -- fora
daquele instante o MESMO clique, na MESMA coordenada, abre o diálogo 78% das
vezes. Ou seja: **depois do clique no link alguma coisa fica na tela** e engole
o clique direito seguinte por cerca de um segundo. E a entrada nunca acontece.

O que é essa coisa não dá para deduzir do código. Há um candidato concreto:
`coords.cave_enter_confirm` = (258,364), medido em 1024x768 (a resolução deste
cliente) e **nunca lido por código nenhum** -- enquanto o link que a descoberta
por imagem acha fica em (302,365), a UMA linha de distância. Ou existe um passo
de confirmação que alguém mediu e nunca ligou no fluxo, ou aquilo é uma medição
velha do próprio link. As duas levam a lugares opostos, e uma FOTO decide.

=========================================================================
COMO ELE NÃO ATRAPALHA O QUE ESTÁ MEDINDO
=========================================================================

  * **Bounded por construção:** `MAXIMO_DE_EPISODIOS` fotos por processo, e
    depois vira no-op silencioso. Uma run de madrugada não enche o disco nem
    paga o custo a noite inteira.
  * **Nunca derruba a run:** tudo dentro de `try/except`. É complemento; sem
    ele a entrada roda exatamente como rodava.
  * **O clique continua onde estava.** Este módulo não clica -- ele só
    fotografa antes e depois. Apagar o módulo é apagar duas linhas do
    `ui_service`, e o clique fica intacto.
  * **`time.sleep`, e não `ctx.tick`:** o tick sorteia jitter, e jitter borra
    justamente os instantes que se quer cravar. O preço é o Parar demorar até
    `INSTANTES[-1]` para responder durante um episódio.

=========================================================================
COMO APAGAR DEPOIS
=========================================================================

    blazesbot/bot/ui_service.py -- o import e as duas linhas marcadas
                                   TEMPORÁRIO em `_abrir_dialogo_e_clicar`
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...core.vision import capture_window, frame_is_blank

if TYPE_CHECKING:
    from ..context import BotContext

# Interruptor, no padrão do `USAR_TAB_NOS_GUARDAS`: desligar é trocar uma
# palavra, e o caminho normal fica intacto dos dois lados.
ATIVADO = True

# Instantes, em segundos DEPOIS do clique. Escolhidos pela medição: o bloqueio
# dura cerca de um segundo (o clique direito seguinte sai ~640 ms depois e
# falha), então a janela interessante é essa. O 0.0 pega o que aparece na hora;
# o 0.75 pega o que ainda está lá quando o bot volta a clicar.
INSTANTES = (0.0, 0.10, 0.35, 0.75)

# Episódios por processo. Doze dá para ver o padrão se repetir e ainda cabe em
# ~10 s de custo total na run inteira.
MAXIMO_DE_EPISODIOS = 12

PASTA = Path("logs") / "diagnostico-do-link"

_episodios = 0


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "link"


def _gravar(quadro: Any, caminho: Path) -> bool:
    import cv2

    PASTA.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(caminho), quadro))


def quadro_antes(ctx: BotContext) -> Any:
    """A foto de referência: o diálogo ABERTO, um instante antes do clique.

    Sem ela a comparação seria contra a memória de como o diálogo é. Com ela,
    as duas imagens saem do mesmo cliente, na mesma janela, com um clique de
    diferença -- e o que mudou salta aos olhos.
    """
    if not ATIVADO or _episodios >= MAXIMO_DE_EPISODIOS:
        return None
    try:
        return capture_window(ctx.hwnd)
    except Exception:
        return None


def registrar(ctx: BotContext, o_que: str, antes: Any = None) -> None:
    """Fotografa a sequência depois do clique no link e grava em disco."""
    global _episodios

    if not ATIVADO or _episodios >= MAXIMO_DE_EPISODIOS:
        return
    _episodios += 1
    comeco = time.perf_counter()
    carimbo = time.strftime("%H%M%S") + f".{int(time.time() * 1000) % 1000:03d}"
    base = f"{carimbo}-{_slug(o_que)}"
    salvos: list[str] = []

    try:
        if antes is not None and not frame_is_blank(antes):
            if _gravar(antes, PASTA / f"{base}-antes.png"):
                salvos.append("antes")

        alvo = comeco
        for instante in INSTANTES:
            alvo = comeco + instante
            restante = alvo - time.perf_counter()
            if restante > 0:
                time.sleep(restante)
            quadro = capture_window(ctx.hwnd)
            if quadro is None or frame_is_blank(quadro):
                salvos.append(f"t+{int(instante * 1000):03d}:vazio")
                continue
            nome = f"{base}-t+{int(instante * 1000):03d}.png"
            if _gravar(quadro, PASTA / nome):
                salvos.append(f"t+{int(instante * 1000):03d}")

        ctx.log.info(
            "DIAGNÓSTICO DO LINK (%d/%d): %s — quadros %s em %s (custou %.0f ms)",
            _episodios, MAXIMO_DE_EPISODIOS, o_que, ", ".join(salvos) or "nenhum",
            PASTA, (time.perf_counter() - comeco) * 1000,
        )
        if _episodios == MAXIMO_DE_EPISODIOS:
            ctx.log.info(
                "DIAGNÓSTICO DO LINK: teto de %d episódios atingido; não "
                "fotografo mais nesta execução.", MAXIMO_DE_EPISODIOS)
    except Exception as exc:
        # Complemento nunca derruba a run.
        ctx.log.debug("Diagnóstico do link falhou (%s); seguindo", exc)
