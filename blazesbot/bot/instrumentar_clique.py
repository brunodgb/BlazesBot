"""TEMPORÁRIO -- o que o jogo REALMENTE recebe, e QUANDO ele processa.

=========================================================================
A PERGUNTA QUE FICOU EM ABERTO
=========================================================================

Com `postmessage_puro` e sem shield, o clique ainda se perde de vez em quando
quando o usuário mexe o mouse sobre a janela do jogo. Melhor que SendMessage,
não perfeito. E o que já se sabe é o que NÃO é:

  * não é ordem entre as NOSSAS mensagens -- as quatro são postadas e saem em
    FIFO;
  * não é `GetCursorPos` -- medido (20/20 com o cursor parado a 780 px do alvo);
  * o shield não resolve -- testado, e com PostMessage ele ainda cobra 80 ms
    cheios porque não há sinal de quando o jogo processou.

A hipótese que sobra é o jogo processar um `WM_MOUSEMOVE` FÍSICO da fila entre o
nosso move e o nosso botão. Mas se fosse só isso, o shield teria ajudado.

**Chega de testar variante às cegas.** Três já foram testadas assim nesta
investigação e duas custaram dias (o PostMessage híbrido e a DLL de cursor). Esta
ferramenta MEDE em vez de adivinhar.

=========================================================================
O QUE ELA MEDE, E POR QUE ISSO É NOVO
=========================================================================

1. **QUANDO O JOGO PROCESSA.** Depois de postar, o minimapa é fotografado a cada
   `PASSO_DA_SONDA` até mudar. Isso dá a latência POST -> EFEITO, que é
   exatamente o intervalo desconhecido que transformou o shield num chute de
   80 ms. Com a distribuição na mão, ou se dimensiona o bloqueio de verdade, ou
   se descarta a ideia com número.

2. **QUANDO O MOUSE FÍSICO SE MEXE.** Um `WH_MOUSE_LL` é instalado como SENSOR:
   ele NUNCA bloqueia nada (devolve sempre `CallNextHookEx`), só anota o instante
   e a posição de cada evento. É o mesmo mecanismo do `MouseShield`, com o sinal
   trocado -- observar em vez de impedir.

3. **A CORRELAÇÃO.** Para cada clique: houve evento físico entre o post e o
   efeito? Em que instante relativo? E o clique deu certo?

Se as falhas se concentrarem numa janela de tempo específica, ela aparece aqui --
e aí o conserto deixa de ser palpite. Se NÃO houver correlação, isso também é
resposta: a causa não é o mouse físico, e a investigação vira para outro lado em
vez de gastar mais dias no mesmo.

=========================================================================
POR QUE DÁ PARA RODAR COM O BOT LIGADO
=========================================================================

Pedido do usuário: testar sem parar o farm das outras contas. Esta ferramenta:

  * roda em PROCESSO PRÓPRIO (`python -m`), então não divide estado com o bot;
  * **não grava configuração nenhuma** -- não usa o supervisor, não reivindica
    PID, não mexe no pino de janela;
  * deixa VOCÊ escolher a janela.

O que ela NÃO pode evitar: se você escolher uma janela que o bot está dirigindo,
os dois disputam a janela e o número não vale nada. Escolha uma conta parada, ou
a do APP. A ferramenta avisa quando a posição do personagem muda sozinha entre
cliques, que é o sinal de que alguém mais está mexendo ali.

=========================================================================
COMO APAGAR DEPOIS
=========================================================================

Arquivo FOLHA: nada do bot importa dele. Apagar este arquivo e o
`14-INSTRUMENTAR-CLIQUE.bat` remove a instrumentação inteira.
"""
from __future__ import annotations

import ctypes
import json
import logging
import statistics
import sys
import threading
import time
from ctypes import POINTER, c_int, c_void_p, windll
from ctypes.wintypes import DWORD, HWND, LONG, LPARAM, MSG, POINT, WPARAM
from datetime import datetime
from pathlib import Path

import numpy as np

from ..config import BotConfig
from ..core import inputs as mod_inputs
from ..core.vision import capture_window
from .context import BotContext
from .teste_do_cursor import (
    _cursor_fisico,
    _mudou,
    _para_cliente,
    _regiao_do_minimapa,
    _retangulo_da_janela,
    janelas_do_jogo,
)

log = logging.getLogger("blazes.instrumentar")
user32 = windll.user32

# Quantos cliques por modo. 40 e não 20: aqui não se está separando "funciona" de
# "não funciona" (isso já foi medido), e sim caçando uma correlação que aparece em
# poucos por cento dos cliques. Amostra pequena não acha evento raro.
CLIQUES_POR_MODO = 40

# De quanto em quanto tempo a sonda fotografa o minimapa esperando o efeito.
# É ISTO que dá a resolução da latência POST -> EFEITO; abaixo do custo de uma
# captura (~11 ms) não adianta pedir mais.
PASSO_DA_SONDA = 0.012

# Teto da espera pelo efeito. Passou disso, o clique é dado como PERDIDO.
TETO_DA_SONDA = 1.2

# Descanso entre cliques, para o jogo assentar e a próxima medida começar limpa.
ENTRE_CLIQUES = 0.25

DIFERENCA_QUE_E_EFEITO = 3.0
DISTANCIA_MINIMA_DO_ALVO = 120

PASTA = Path("logs") / "instrumentacao"

# ===========================================================================
# O SENSOR — o mesmo WH_MOUSE_LL do shield, com o sinal trocado
# ===========================================================================

WH_MOUSE_LL = 14
HC_ACTION = 0
WM_MOUSEMOVE = 0x0200

_NOME_DO_EVENTO = {
    0x0200: "move", 0x0201: "L-down", 0x0202: "L-up",
    0x0204: "R-down", 0x0205: "R-up", 0x020A: "roda",
}


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", DWORD), ("flags", DWORD),
                ("time", DWORD), ("dwExtraInfo", POINTER(ctypes.c_ulong))]


HOOKPROC = ctypes.WINFUNCTYPE(LONG, c_int, WPARAM, LPARAM)
user32.SetWindowsHookExW.argtypes = [c_int, HOOKPROC, c_void_p, DWORD]
user32.SetWindowsHookExW.restype = c_void_p
user32.CallNextHookEx.argtypes = [c_void_p, c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LONG
user32.UnhookWindowsHookEx.argtypes = [c_void_p]
user32.GetMessageW.argtypes = [POINTER(MSG), HWND, ctypes.c_uint, ctypes.c_uint]

# Lista compartilhada com o callback. `deque` seria mais elegante, mas `list.append`
# é atômico no CPython e o callback tem que ser o mais barato possível -- ele roda
# em TODO evento de mouse do sistema.
_EVENTOS: list[tuple[float, int, int, int]] = []
_SENSOR_LIGADO = False


def _sensor_proc(nCode: int, wParam: int, lParam: int) -> int:
    """Anota e DEIXA PASSAR. Nunca devolve 1 -- este hook não bloqueia nada."""
    if nCode == HC_ACTION and _SENSOR_LIGADO:
        try:
            pt = ctypes.cast(lParam, POINTER(MSLLHOOKSTRUCT)).contents.pt
            _EVENTOS.append((time.perf_counter(), int(wParam), pt.x, pt.y))
        except Exception:
            pass
    return user32.CallNextHookEx(None, nCode, wParam, lParam)


_CALLBACK = HOOKPROC(_sensor_proc)
_HANDLE = None


def ligar_o_sensor() -> bool:
    """Sobe o hook numa thread com laço de mensagens. Devolve se conseguiu."""
    global _SENSOR_LIGADO
    pronto = threading.Event()

    def laco() -> None:
        global _HANDLE
        _HANDLE = user32.SetWindowsHookExW(WH_MOUSE_LL, _CALLBACK, None, 0)
        pronto.set()
        if not _HANDLE:
            return
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
            pass

    threading.Thread(target=laco, daemon=True, name="SensorDeMouse").start()
    pronto.wait(timeout=2.0)
    _SENSOR_LIGADO = bool(_HANDLE)
    return _SENSOR_LIGADO


# ===========================================================================
# A medida
# ===========================================================================

def _sondar_ate_mudar(hwnd: int, antes: np.ndarray) -> tuple[float | None, float]:
    """Fotografa até o minimapa mudar. Devolve (latência em ms, diferença).

    É esta função que responde a pergunta que faltava: QUANDO o jogo processou.
    Com `SendMessageW` a resposta é "durante a chamada"; com `PostMessageW` era
    desconhecida, e é por não saber isso que o bloqueio do shield virou um chute
    de 80 ms.
    """
    inicio = time.perf_counter()
    while time.perf_counter() - inicio < TETO_DA_SONDA:
        quadro = capture_window(hwnd)
        if quadro is not None:
            d = _mudou(antes, _regiao_do_minimapa(quadro))
            if d >= DIFERENCA_QUE_E_EFEITO:
                return (time.perf_counter() - inicio) * 1000.0, d
        time.sleep(PASSO_DA_SONDA)
    return None, 0.0


def _um_modo(ctx: BotContext, hwnd: int, alvos: list, modo: str,
             com_shield: bool) -> dict:
    """`CLIQUES_POR_MODO` cliques instrumentados num modo de clique."""
    mod_inputs.MODO_DE_CLIQUE = modo
    mod_inputs.USAR_MOUSE_SHIELD = com_shield
    teclado = mod_inputs.Input(hwnd)

    nome = f"{modo}{' + shield' if com_shield else ''}"
    log.info("")
    log.info("=== %s ===", nome)

    registros = []
    nivel = 0
    for i in range(CLIQUES_POR_MODO):
        alvo = alvos[1] if nivel else alvos[0]
        pos_antes = ctx.memory.position()
        quadro = capture_window(hwnd)
        if quadro is None:
            continue
        antes = _regiao_do_minimapa(quadro)

        _EVENTOS.clear()
        t0 = time.perf_counter()
        teclado.left_click(alvo[0], alvo[1])
        t_post = (time.perf_counter() - t0) * 1000.0

        latencia, diff = _sondar_ate_mudar(hwnd, antes)
        pos_depois = ctx.memory.position()

        # Os eventos FÍSICOS que caíram na janela entre postar e o efeito. É a
        # correlação que a investigação precisa: a falha coincide com um evento
        # físico, e em que instante relativo?
        fisicos = [
            {"ms": round((t - t0) * 1000.0, 1),
             "tipo": _NOME_DO_EVENTO.get(w, hex(w)), "x": x, "y": y}
            for t, w, x, y in list(_EVENTOS) if t >= t0
        ]
        moves = [e for e in fisicos if e["tipo"] == "move"]

        andou = (pos_antes is not None and pos_depois is not None
                 and pos_antes != pos_depois)
        ok = latencia is not None and not andou
        if ok:
            nivel = 1 - nivel

        # A TAXA, E NÃO A CONTAGEM CRUA -- correção de uma armadilha da primeira
        # corrida (18/08/2026). Nos cliques PERDIDOS a sonda roda o teto inteiro
        # (1,2 s) e nos bons ela para no efeito (~0,1 s), então a contagem bruta
        # de eventos físicos é ~10x maior nos perdidos SÓ POR ISSO. O número
        # parecia acusar o mouse e não acusava nada: normalizada, a taxa é a
        # mesma (~2,4 eventos/ms nos dois).
        janela_ms = latencia if latencia is not None else TETO_DA_SONDA * 1000.0
        taxa_de_moves = len(moves) / janela_ms if janela_ms else 0.0

        registros.append({
            "n": i + 1, "alvo": list(alvo), "ok": ok, "andou": andou,
            "moves_por_ms": round(taxa_de_moves, 3),
            "janela_ms": round(janela_ms, 1),
            "ms_para_postar": round(t_post, 2),
            "ms_ate_o_efeito": None if latencia is None else round(latencia, 1),
            "diferenca": round(diff, 2),
            "moves_fisicos": len(moves),
            "primeiro_move_ms": moves[0]["ms"] if moves else None,
            "eventos": fisicos[:12],
        })
        log.info(
            "%2d/%d %-7s post=%6.2fms efeito=%s moves=%.2f/ms %s",
            i + 1, CLIQUES_POR_MODO, "OK" if ok else "PERDIDO",
            t_post,
            "-------" if latencia is None else f"{latencia:6.1f}ms",
            taxa_de_moves,
            f"(1o em {moves[0]['ms']:.1f}ms)" if moves else "(sem move)",
        )
        time.sleep(ENTRE_CLIQUES)

    return {"modo": nome, "registros": registros}


def _analisar(resultado: dict) -> dict:
    """O que os números dizem. Separado da coleta, de propósito."""
    regs = resultado["registros"]
    ok = [r for r in regs if r["ok"]]
    perdidos = [r for r in regs if not r["ok"]]
    lat = [r["ms_ate_o_efeito"] for r in ok if r["ms_ate_o_efeito"] is not None]

    def com_move(rs):
        return [r for r in rs if r["moves_fisicos"] > 0]

    def taxa_mediana(rs):
        vals = [r["moves_por_ms"] for r in rs if "moves_por_ms" in r]
        return round(statistics.median(vals), 3) if vals else None

    analise = {
        "modo": resultado["modo"],
        "cliques": len(regs),
        "acertos": len(ok),
        "taxa": len(ok) / len(regs) if regs else 0.0,
        "andou": sum(1 for r in regs if r["andou"]),
        "latencia_ms": {
            "min": round(min(lat), 1) if lat else None,
            "mediana": round(statistics.median(lat), 1) if lat else None,
            "max": round(max(lat), 1) if lat else None,
        },
        "ms_para_postar_mediana": round(statistics.median(
            [r["ms_para_postar"] for r in regs]), 2) if regs else None,
        # A CORRELAÇÃO. Se a falha depende do mouse físico, estas duas taxas
        # divergem; se forem iguais, a causa é outra e a investigação muda de
        # direção -- o que também é resposta.
        "cliques_com_move_fisico": len(com_move(regs)),
        # COMPARE ESTAS DUAS, não as contagens cruas. Se a atividade do mouse
        # causasse a falha, a taxa nos perdidos seria maior que nos acertos.
        "moves_por_ms_nos_ACERTOS": taxa_mediana(ok),
        "moves_por_ms_nos_PERDIDOS": taxa_mediana(perdidos),
        "taxa_quando_HOUVE_move": (
            round(len(com_move(ok)) / len(com_move(regs)), 3)
            if com_move(regs) else None),
        "taxa_quando_NAO_houve_move": (
            round(len([r for r in ok if r["moves_fisicos"] == 0])
                  / len([r for r in regs if r["moves_fisicos"] == 0]), 3)
            if [r for r in regs if r["moves_fisicos"] == 0] else None),
        "instante_do_1o_move_nos_perdidos": sorted(
            r["primeiro_move_ms"] for r in perdidos
            if r["primeiro_move_ms"] is not None),
    }
    return analise


def rodar(config: BotConfig, account, hwnd: int, pid: int,
          modos: list[tuple[str, bool]]) -> dict:
    parada = threading.Event()
    ctx = None
    modo_original = mod_inputs.MODO_DE_CLIQUE
    shield_original = mod_inputs.USAR_MOUSE_SHIELD
    try:
        ctx = BotContext(config=config, account=account, pid=pid, hwnd=hwnd,
                         stop_event=parada)
        if ctx.memory.position() is None:
            return {"ok": False, "erro": (
                "Não leio a posição do personagem nesta janela — ela precisa "
                "estar NO MUNDO (o alvo é o minimapa).")}

        alvos = [ctx.coords.minimap_zoom_in, ctx.coords.minimap_zoom_out]
        cx, cy = _cursor_fisico()
        esq, topo, dir_, baixo = _retangulo_da_janela(hwnd)
        if not (esq <= cx <= dir_ and topo <= cy <= baixo):
            return {"ok": False, "erro": (
                f"O cursor físico está FORA da janela ({cx},{cy}). A medição só "
                f"faz sentido com ele DENTRO — é a interferência que se quer "
                f"caçar.")}
        cli = _para_cliente(hwnd, cx, cy)
        perto = min(abs(cli[0] - a[0]) + abs(cli[1] - a[1]) for a in alvos)
        if perto < DISTANCIA_MINIMA_DO_ALVO:
            return {"ok": False, "erro": (
                f"Cursor a {perto}px dos botões de zoom. Com ele em cima do "
                f"alvo, acertar não prova nada.")}

        if not ligar_o_sensor():
            return {"ok": False, "erro": "Não consegui instalar o sensor."}

        # AUTOVERIFICAÇÃO DO SENSOR -- e ela não é zelo excessivo.
        #
        # Um sensor instalado que não recebe nada mede ZERO eventos físicos em
        # todos os cliques, e o relatório sairia dizendo "nenhuma correlação com
        # o mouse" com a maior naturalidade. Seria a mesma armadilha que fez uma
        # medição deste projeto reportar 95% para o que era 5%: a métrica não
        # sabia distinguir "não aconteceu" de "não observei".
        #
        # Então: antes de medir qualquer coisa, o sensor tem que PROVAR que vê o
        # mouse. Sem prova, a ferramenta recusa em vez de produzir número falso.
        log.info("Sensor ligado. Conferindo se ele vê o seu mouse — "
                 "MEXA O MOUSE agora...")
        _EVENTOS.clear()
        prazo = time.perf_counter() + 4.0
        while time.perf_counter() < prazo and len(_EVENTOS) < 5:
            time.sleep(0.05)
        if len(_EVENTOS) < 5:
            return {"ok": False, "erro": (
                "O sensor não viu o seu mouse em 4 s. Ou você não mexeu, ou o "
                "hook não está recebendo evento (outro programa com hook de "
                "baixo nível pode tê-lo derrubado). Medir assim produziria "
                "'nenhuma correlação com o mouse' sem ter observado nada.")}
        log.info("Sensor conferido: %s eventos em menos de 4 s.", len(_EVENTOS))

        saida = []
        for modo, com_shield in modos:
            saida.append(_um_modo(ctx, hwnd, alvos, modo, com_shield))
        return {"ok": True, "modos": saida,
                "analises": [_analisar(m) for m in saida]}
    except Exception as exc:
        log.exception("instrumentação falhou")
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
    finally:
        mod_inputs.MODO_DE_CLIQUE = modo_original
        mod_inputs.USAR_MOUSE_SHIELD = shield_original
        if ctx is not None:
            ctx.close()


def _relatorio(analises: list[dict]) -> str:
    linhas = ["", "=" * 74, "RELATÓRIO", "=" * 74, ""]
    linhas.append(f"{'modo':<28}{'acertos':>9}{'latência (min/med/max)':>26}")
    linhas.append("-" * 74)
    for a in analises:
        lat = a["latencia_ms"]
        txt = ("----" if lat["mediana"] is None
               else f"{lat['min']}/{lat['mediana']}/{lat['max']} ms")
        linhas.append(f"{a['modo']:<28}{a['acertos']:>4}/{a['cliques']:<4}"
                      f"{txt:>26}")
    linhas += ["", "CORRELAÇÃO COM O MOUSE FÍSICO", "-" * 74]
    for a in analises:
        linhas.append(
            f"{a['modo']:<28} taxa c/ move: {a['taxa_quando_HOUVE_move']}   "
            f"s/ move: {a['taxa_quando_NAO_houve_move']}")
        linhas.append(
            f"{'':28} moves/ms  acertos: {a['moves_por_ms_nos_ACERTOS']}   "
            f"perdidos: {a['moves_por_ms_nos_PERDIDOS']}")
        if a["instante_do_1o_move_nos_perdidos"]:
            linhas.append(
                f"{'':28} 1o move nos PERDIDOS (ms): "
                f"{a['instante_do_1o_move_nos_perdidos'][:10]}")
    linhas += ["", "COMO LER", "-" * 74,
               "* moves/ms NOS PERDIDOS maior que NOS ACERTOS => o mouse causa.",
               "  Compare a TAXA, nunca a contagem crua: o clique perdido mede",
               "  1,2 s e o bom mede ~0,1 s, então a contagem bruta engana.",
               "* 'com move' MUITO menor que 'sem move' => a falha É o mouse",
               "  físico, e o instante do 1o move diz QUAL janela proteger.",
               "* as duas parecidas => a causa NÃO é o mouse físico. A",
               "  investigação muda de direção, e isso também é resposta.",
               "* a latência é o intervalo que o shield precisaria cobrir com",
               "  PostMessage — hoje ele chuta 80 ms sem esse número."]
    return "\n".join(linhas)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        stream=sys.stdout, force=True)
    from main import require_admin
    require_admin()

    config = BotConfig.load()
    contas = [c for c in config.accounts if c.enabled] or config.accounts
    janelas = janelas_do_jogo()
    if not janelas or not contas:
        print("Nenhuma janela de jogo (ou nenhuma conta configurada).")
        return 1

    print("\nJanelas de jogo abertas:\n")
    for i, j in enumerate(janelas, 1):
        print(f"  [{i}] hwnd={j['hwnd']}  pid={j['pid']}  "
              f"{j['tamanho'][0]}x{j['tamanho'][1]}  {j['titulo'][:44]}")
    print("\nESCOLHA UMA CONTA QUE NÃO ESTEJA COM O BOT DIRIGINDO ELA —")
    print("se o bot estiver navegando na mesma janela, os dois disputam e o")
    print("número não vale nada. As outras contas podem seguir farmando.\n")
    try:
        n = int(input(f"Qual janela? [1-{len(janelas)}]: "))
        escolhida = janelas[n - 1]
    except (ValueError, IndexError, EOFError):
        print("Escolha inválida.")
        return 1

    conta = next((c for c in contas if c.last_pid == escolhida["pid"]),
                 contas[0])
    MODOS = [
        ("postmessage_puro", False),
        ("postmessage_puro", True),
        ("sendmessage_rapido", True),
    ]
    print(f"\nJanela hwnd={escolhida['hwnd']}  |  {len(MODOS)} modos x "
          f"{CLIQUES_POR_MODO} cliques")
    print("\n  MEXA O MOUSE sobre essa janela o tempo todo, sem parar.")
    print("  É a interferência que se quer caçar: sem ela, não há o que medir.")
    print("\nComeçando em 8 s...")
    time.sleep(8)

    r = rodar(config, conta, escolhida["hwnd"], escolhida["pid"], MODOS)
    if not r.get("ok"):
        print("\nFALHOU:", r.get("erro"))
        return 1

    print(_relatorio(r["analises"]))
    PASTA.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA / f"{datetime.now():%Y%m%d-%H%M%S}-instrumentacao.json"
    arquivo.write_text(json.dumps(r, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(f"\nDados completos (evento a evento) em: {arquivo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
