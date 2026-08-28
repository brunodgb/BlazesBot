"""Aferir o ALVO-ALIADO: a memória descreve um alvo que é JOGADOR?

=========================================================================
POR QUE ISTO EXISTE, E POR QUE VEM ANTES DA FADA
=========================================================================

A Fada (`docs/decisoes/fada.md`) mira a cura assim: clica no retrato do
companheiro no painel de time e **confere pela memória em quem clicou**. Toda a
identificação depende de uma coisa que NINGUÉM MEDIU -- *a memória descreve um
alvo que é jogador, ou só mob?*

Há indício de que sim: `Memory.alvo_atual()` não tem filtro nenhum por tipo,
nível ou escala (a única validação é de consistência do HP). Quem exclui
jogadores é o `inimigos_proximos`, que peneira por `max_hp == ESCALA_DE_INIMIGO`.
**Indício não é medição.**

A lição é recente e cara: o `TARGET_ID` entre dois clientes ficou sem medir e
virou justamente o modo do time que não funciona (`docs/decisoes/time-do-app.md`).

=========================================================================
O QUE ELA RESPONDE, DE UMA VEZ
=========================================================================

1. **Clicar no retrato seleciona o companheiro?** (o usuário já confirmou por
   experiência; aqui fica registrado com o id antes e depois)
2. **A memória passa a descrevê-lo?** -- `id`, `nome`, `hp/max`, `pct`.
3. **Em quanto tempo?** Mede o atraso entre o clique e a memória virar. É o
   mesmo piso físico que o alinhamento de alvo do time precisa e nunca teve.
4. **As coordenadas derivadas estão certas?** O primeiro retrato foi medido em
   (28,204); os outros três saem de um passo de 80 px tirado de um print. A
   prova em PNG marca os quatro pontos para o usuário confirmar a olho.

=========================================================================
ELA NÃO MUDA NADA NO JOGO ALÉM DE SELECIONAR
=========================================================================

Clica em retrato e lê memória. **Não usa skill, não anda, não abre janela.** O
único efeito colateral é o alvo ficar trocado ao fim -- ela NÃO solta o alvo,
porque largar alvo aqui exigiria apertar ESC, e ESC neste cliente abre o menu do
jogo. Deixar o alvo selecionado é o menor dos dois males numa ferramenta que o
usuário roda com o bot parado.

A tecla de AUTO-SELEÇÃO também é testada, e por padrão: o usuário confirmou em
28/08/2026 que o jogo só tem essa -- **não existe tecla para selecionar
companheiro de time** --, e é dela que a Fada depende para a auto-cura.

Molde: `bot/app/afericao.py` -- adota a janela sem subir a thread e devolve o
PID no `finally` de TODA saída.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ...config import Account, BotConfig
from ...core import vision
from ...core.coords import (
    MAXIMO_DE_RETRATOS_DO_TIME,
    PASSO_ENTRE_RETRATOS_DO_TIME,
    PRIMEIRO_RETRATO_DO_TIME,
)
from ..context import BotContext, StopRequested
from ..supervisor import AccountSupervisor

_PARADA = threading.Event()
_EM_ANDAMENTO = threading.Lock()

PASTA_DE_PROVAS = Path("logs") / "afericao_aliado"

# Quanto esperar, no máximo, a memória refletir o alvo novo depois do clique.
#
# Generoso de propósito: o número que interessa é o MEDIDO, não o teto. Se o
# atraso real for maior que isto, o resultado sai como "não mudou" -- e isso
# também é resposta.
TETO_DA_ESPERA_DO_ALVO = 2.0

# De quanto em quanto tempo perguntar. 20 ms é fino o bastante para o número
# medido ter serventia como piso de cadência, e barato: é uma leitura de 4 bytes.
PASSO_DA_MEDICAO = 0.02

# A tecla de AUTO-SELEÇÃO. O usuário confirmou em 28/08/2026 que o jogo tem
# apenas esta -- **não existe tecla para selecionar companheiro de time**, e é
# por isso que a Fada precisa clicar no retrato.
#
# Ela é sondada mesmo assim porque a Fada depende dela para a AUTO-CURA: ao
# chegar no crítico, a Fada se seleciona e cura a si mesma. Sondar aqui prova
# duas coisas de uma vez -- que a tecla seleciona, e que a memória descreve o
# próprio personagem como alvo (o caso mais fácil do alvo-jogador).
TECLAS_SONDADAS = ("F1",)


def em_andamento() -> bool:
    return _EM_ANDAMENTO.locked()


def cancelar() -> None:
    _PARADA.set()


def _ler_alvo(ctx: BotContext) -> dict[str, Any]:
    """O que a memória diz do alvo AGORA. Nunca levanta."""
    try:
        ident = ctx.memory.id_do_alvo()
    except Exception:
        ident = None
    dados: dict[str, Any] = {"id": ident}
    try:
        alvo = ctx.memory.alvo_atual()
    except Exception:
        alvo = None
    if alvo:
        dados.update({
            "nome": alvo.get("nome"),
            "hp": alvo.get("hp"),
            "max_hp": alvo.get("max_hp"),
            "pct": alvo.get("pct"),
            "nivel": alvo.get("nivel"),
        })
    return dados


def _esperar_o_alvo_virar(ctx: BotContext, id_antes: int | None) -> tuple[dict, float]:
    """Pergunta até o id mudar. Devolve o que leu e QUANTO DEMOROU.

    O tempo é o produto principal desta ferramenta: é o piso físico de qualquer
    cadência que compare `TARGET_ID` depois de uma ação. Sem ele, quem compara
    rápido demais lê o alvo ANTERIOR e conclui "não mudou" -- errando calado.
    """
    comeco = time.monotonic()
    limite = comeco + TETO_DA_ESPERA_DO_ALVO
    while time.monotonic() < limite:
        lido = _ler_alvo(ctx)
        if lido.get("id") and lido["id"] != id_antes:
            return lido, time.monotonic() - comeco
        ctx.tick(PASSO_DA_MEDICAO)
    return _ler_alvo(ctx), time.monotonic() - comeco


def _pontos_dos_retratos(ctx: BotContext) -> list[tuple[int, int]]:
    return [getattr(ctx.coords, f"team_member_{i + 1}")
            for i in range(MAXIMO_DE_RETRATOS_DO_TIME)]


def _desenhar_a_prova(ctx: BotContext, pontos, achados) -> str:
    """O PNG com os quatro pontos marcados. Ver é mais barato que conferir número.

    Mesma receita do `deletador.conferir`: `cv2` importado LOCALMENTE (o módulo
    não pode depender dele para ser importado) e quadro nulo/em branco reprovado.
    """
    try:
        import cv2
    except Exception:
        return ""
    quadro = vision.capture_window(ctx.hwnd)
    if quadro is None or vision.frame_is_blank(quadro):
        return ""
    for i, (x, y) in enumerate(pontos):
        achado = achados[i] if i < len(achados) else {}
        acertou = bool(achado.get("depois", {}).get("nome"))
        cor = (0, 200, 0) if acertou else (0, 0, 255)
        cv2.rectangle(quadro, (x - 22, y - 22), (x + 22, y + 22), cor, 2)
        rotulo = f"{i + 1}: {achado.get('depois', {}).get('nome') or 'sem leitura'}"
        cv2.putText(quadro, rotulo, (x + 28, y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, cor, 1, cv2.LINE_AA)
    PASTA_DE_PROVAS.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_DE_PROVAS / f"retratos-{time.strftime('%Y%m%d-%H%M%S')}.png"
    try:
        cv2.imwrite(str(caminho), quadro)
    except OSError:
        return ""
    return str(caminho)


def rodar(config: BotConfig, account: Account,
          on_status: Callable[[str, str], None] | None = None,
          sondar_teclas: bool = True) -> dict[str, Any]:
    """Clica em cada retrato do painel de time e mede o que a memória vê."""
    log = logging.getLogger(f"blazes.{account.login or 'afericao_aliado'}")
    if not _EM_ANDAMENTO.acquire(blocking=False):
        return {"ok": False, "erro": "Já existe uma aferição rodando."}

    _PARADA.clear()
    supervisor = AccountSupervisor(config, account, on_status=on_status)
    ctx: BotContext | None = None
    try:
        adotada = supervisor._adotar_janela_existente()
        if adotada is None:
            return {"ok": False,
                    "erro": "Não encontrei a janela desta conta. Ela precisa "
                            "estar logada e com o time FORMADO na tela."}
        pid, hwnd, ja_logado, personagem = adotada
        supervisor.pid, supervisor.hwnd = pid, hwnd
        if not ja_logado:
            return {"ok": False, "erro": "O cliente encontrado está na tela de login."}

        ctx = BotContext(config=config, account=account, pid=pid, hwnd=hwnd,
                         stop_event=_PARADA)
        ctx.char_name = personagem

        if not ctx.memory.critical_ok():
            return {"ok": False,
                    "erro": "A memória do cliente não está legível — sem ela "
                            "esta aferição não tem o que medir."}

        eu = {"nick": personagem,
              "max_hp": _seguro(ctx.memory.max_hp),
              "mp": _seguro(ctx.memory.mp)}
        log.info("Aferição do aliado: conta %s (%s), max_hp=%s mp=%s",
                 account.login, personagem, eu["max_hp"], eu["mp"])

        pontos = _pontos_dos_retratos(ctx)
        achados = []
        for i, (x, y) in enumerate(pontos):
            antes = _ler_alvo(ctx)
            ctx.input.left_click(x, y)
            depois, demora = _esperar_o_alvo_virar(ctx, antes.get("id"))
            achados.append({"slot": i + 1, "ponto": (x, y),
                            "antes": antes, "depois": depois,
                            "segundos": round(demora, 3)})
            log.info(
                "Slot %d em (%d,%d): id %s -> %s | nome=%r hp=%s/%s nivel=%s "
                "| %.3fs",
                i + 1, x, y, antes.get("id"), depois.get("id"),
                depois.get("nome"), depois.get("hp"), depois.get("max_hp"),
                depois.get("nivel"), demora)

        teclas = []
        if sondar_teclas:
            log.info("Sondando a auto-seleção (%s).", ", ".join(TECLAS_SONDADAS))
            for tecla in TECLAS_SONDADAS:
                antes = _ler_alvo(ctx)
                ctx.press(tecla)
                depois, demora = _esperar_o_alvo_virar(ctx, antes.get("id"))
                teclas.append({"tecla": tecla, "antes": antes,
                               "depois": depois, "segundos": round(demora, 3)})
                log.info("Tecla %s: id %s -> %s | nome=%r | %.3fs",
                         tecla, antes.get("id"), depois.get("id"),
                         depois.get("nome"), demora)

        prova = _desenhar_a_prova(ctx, pontos, achados)
        resultado = {"ok": True, "erro": "", "eu": eu, "slots": achados,
                     "teclas": teclas, "prova": prova,
                     "passo": PASSO_ENTRE_RETRATOS_DO_TIME,
                     "primeiro": PRIMEIRO_RETRATO_DO_TIME}
        resultado["resumo"] = resumir(resultado)
        log.info("Aferição do aliado: %s", resultado["resumo"])
        if prova:
            log.info("Prova em %s", prova)
        return resultado

    except StopRequested:
        return {"ok": False, "erro": "Aferição interrompida."}
    except Exception as exc:
        log.exception("Aferição do aliado falhou")
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
    finally:
        # A ORDEM IMPORTA e é a do molde: sem o `_release()` o bot de verdade
        # veria a janela como de outra conta e abriria um cliente novo.
        if ctx is not None:
            ctx.close()
        supervisor._release()
        _PARADA.clear()
        _EM_ANDAMENTO.release()


def _seguro(fn) -> Any:
    try:
        return fn()
    except Exception:
        return None


def resumir(resultado: dict[str, Any]) -> str:
    """O veredito em TEXTO. O Python decide, as interfaces só exibem."""
    slots = resultado.get("slots") or []
    com_nome = [s for s in slots if (s.get("depois") or {}).get("nome")]
    trocou = [s for s in slots
              if (s.get("depois") or {}).get("id")
              and (s.get("depois") or {}).get("id") != (s.get("antes") or {}).get("id")]
    if not trocou:
        return ("REPROVOU: nenhum clique trocou o alvo. Ou o time não estava na "
                "tela, ou as coordenadas estão erradas — abra a prova em PNG.")
    if not com_nome:
        return (f"PARCIAL: {len(trocou)} de {len(slots)} cliques trocaram o alvo, "
                "mas a memória não descreveu NENHUM deles. A Fada consegue "
                "mirar, mas não consegue confirmar em quem clicou — a vítima "
                "terá de anunciar tudo.")
    demoras = [s["segundos"] for s in trocou]
    return (f"PASSOU: {len(com_nome)} de {len(slots)} aliados lidos pela memória "
            f"({', '.join(str((s.get('depois') or {}).get('nome')) for s in com_nome)}). "
            f"Atraso do clique até a memória virar: "
            f"{min(demoras):.3f}s a {max(demoras):.3f}s.")


def main() -> int:
    """Entrada do `.bat`. Recebe o login da conta como argumento opcional."""
    import sys

    def dizer(texto: str = "") -> None:
        print(texto, flush=True)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = BotConfig.load()
    contas = [c for c in config.accounts if c.enabled] or config.accounts
    if not contas:
        dizer("Nenhuma conta configurada.")
        return 1

    # A auto-seleção entra por padrão: ela é do próprio personagem, não é slot
    # de skill, e prova o caso mais fácil do alvo-jogador. `--sem-teclas` desliga.
    sondar = "--sem-teclas" not in sys.argv
    pedido = [a for a in sys.argv[1:] if not a.startswith("-")]
    if pedido:
        contas = [c for c in contas if (c.login or "").lower() == pedido[0].lower()]
        if not contas:
            dizer(f"Não achei a conta {pedido[0]!r} na configuração.")
            return 1

    dizer("O time precisa estar FORMADO e VISÍVEL na tela do cliente.")
    dizer("O bot precisa estar PARADO.")
    if sondar:
        dizer("A auto-seleção (F1) também será testada — use --sem-teclas para pular.")
    dizer()

    for conta in contas:
        dizer(f"Tentando pela conta {conta.login or '(sem login)'}...")
        r = rodar(config, conta, sondar_teclas=sondar)
        if r.get("ok"):
            dizer()
            for s in r["slots"]:
                d = s["depois"]
                dizer(f"  slot {s['slot']} em {s['ponto']}: id={d.get('id')} "
                      f"nome={d.get('nome')!r} hp={d.get('hp')}/{d.get('max_hp')} "
                      f"nivel={d.get('nivel')} ({s['segundos']}s)")
            for t in r.get("teclas") or []:
                d = t["depois"]
                dizer(f"  tecla {t['tecla']}: id={d.get('id')} "
                      f"nome={d.get('nome')!r} ({t['segundos']}s)")
            dizer()
            dizer(f"  {r['resumo']}")
            if r.get("prova"):
                dizer(f"  prova : {r['prova']}   <- ABRA E CONFIRA OS 4 PONTOS")
            return 0
        dizer(f"  {r.get('erro')}")

    dizer()
    dizer("Nenhuma conta produziu aferição.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
