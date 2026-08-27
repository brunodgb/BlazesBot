"""TEMPORÁRIO -- o cursor físico decide o clique, ou não?

=========================================================================
A PERGUNTA QUE ESTA FERRAMENTA RESPONDE
=========================================================================

O `docs/decisoes/stuttering-mouse.md` afirma que o jogo lê a posição do cursor
por `GetCursorPos()`. **Os números registrados lá contradizem essa afirmação.**

Se fosse `GetCursorPos`, o cursor PARADO sobre a janela seria o pior caso
possível: a posição não muda, então todo clique cairia nela, sempre. A medição
registrada diz o contrário -- parado 100%, em movimento 95-98%.

Isso só fecha se o jogo rastreia o cursor pelo FLUXO DE MENSAGENS, e a falha é
uma CORRIDA: o `_prime_cursor` manda `WM_MOUSEMOVE` com a coordenada certa e um
`WM_MOUSEMOVE` FÍSICO chega entre esse prime e o botão, reescrevendo o que o
jogo guardou.

A diferença não é acadêmica -- ela decide o conserto:

  * `GetCursorPos`   -> bloquear evento não resolve com o cursor parado; só
                        resolveria hookando a função (a DLL, já reprovada).
  * corrida de msg   -> bloquear evento durante o clique resolve, E existe
                        caminho SEM hook global nenhum (reafirmar a coordenada
                        colada ao botão), ou seja zero impacto no mouse do
                        usuário.

Foi por não ter essa resposta que a DLL do TESTE 4 foi escrita: ela hookeava
`GetCursorPos`, e falhou "sem explicação". A explicação provável é que ela
hookeava a função errada.

=========================================================================
COMO A MEDIÇÃO FUNCIONA
=========================================================================

O alvo é o botão de ZOOM DO MINIMAPA, escolhido por três motivos:

  1. o efeito é uma mudança GRANDE de pixels numa região FIXA -- dá para medir
     por imagem, sem depender de leitura de memória;
  2. é seguro: clique ESQUERDO, e o esquerdo não faz o personagem andar (quem
     anda é o direito). Errar o alvo não move ninguém;
  3. é reversível, e o bot já padroniza esse zoom no começo de cada run.

O teste alterna zoom-in e zoom-out para nunca bater no batente -- no batente o
clique CERTO também não muda nada, e isso viraria falso negativo.

O cursor FÍSICO tem que estar parado sobre a janela do jogo e LONGE dos botões
de zoom. A ferramenta confere e recusa rodar se não estiver: com o cursor em
cima do alvo os dois mecanismos dariam o mesmo resultado e o teste não separaria
nada.

VEREDITO:

  * fase SEM shield, cursor parado, taxa ALTA  -> não é `GetCursorPos`; a
    coordenada do `lParam` é respeitada, e o conserto certo é contra a corrida.
  * fase SEM shield, cursor parado, taxa BAIXA -> é leitura de posição; o
    shield é obrigatório e bloquear evento é o único caminho sem DLL.

=========================================================================
COMO APAGAR DEPOIS
=========================================================================

Arquivo FOLHA: nada do bot importa dele. Apagar este arquivo e o
`13-TESTAR-CURSOR.bat` remove o teste inteiro.
"""
from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time
from ctypes.wintypes import POINT, RECT

import numpy as np
import win32gui
import win32process

from ..config import BotConfig
from ..core import inputs as mod_inputs
from ..core.vision import capture_window
from .context import BotContext
from .watchdog import client_pids

log = logging.getLogger("blazes.teste_do_cursor")
user32 = ctypes.windll.user32

# Quantos cliques por fase. 20 dá resolução de 5 pontos percentuais -- suficiente
# para separar "funciona" (>=90%) de "não funciona" (<=50%), que é a única
# distinção que interessa aqui.
CLIQUES_POR_FASE = 20

# Quanto o minimapa precisa mudar para o clique contar como surtido efeito. O
# zoom redesenha o minimapa inteiro; ruído de animação fica MUITO abaixo disso.
DIFERENCA_QUE_E_EFEITO = 3.0

# Distância mínima entre o cursor físico e o alvo, em pixels do cliente.
DISTANCIA_MINIMA_DO_ALVO = 120

ESPERA_DEPOIS_DO_CLIQUE = 0.35


def _cursor_fisico() -> tuple[int, int]:
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return int(p.x), int(p.y)


def _retangulo_da_janela(hwnd: int) -> tuple[int, int, int, int]:
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return int(r.left), int(r.top), int(r.right), int(r.bottom)


def _para_cliente(hwnd: int, x: int, y: int) -> tuple[int, int]:
    p = POINT(x, y)
    user32.ScreenToClient(hwnd, ctypes.byref(p))
    return int(p.x), int(p.y)


def _regiao_do_minimapa(quadro: np.ndarray) -> np.ndarray:
    """O canto superior direito, onde o minimapa vive."""
    alt, larg = quadro.shape[:2]
    return quadro[0:int(alt * 0.30), int(larg * 0.68):larg]


def _mudou(antes: np.ndarray | None, depois: np.ndarray | None) -> float:
    if antes is None or depois is None or antes.shape != depois.shape:
        return 0.0
    return float(np.abs(antes.astype(np.float32)
                        - depois.astype(np.float32)).mean())


def _uma_fase(ctx: BotContext, teclado, alvos: list, nome: str) -> dict:
    """`CLIQUES_POR_FASE` cliques, mantendo o zoom LONGE dos batentes.

    A DIREÇÃO SAI DO NÍVEL, NÃO DO ÍNDICE, e isso conserta um viés que a
    primeira medição tinha: alternar in/out cegamente só se mantém equilibrado
    enquanto NENHUM clique se perde. Perdido um, a alternância desanda, o zoom
    caminha para um dos batentes -- e no batente o clique CERTO também não muda
    nada. Foi o que apareceu na corrida com o mouse em movimento: as duas
    falhas foram as duas no zoom-out, com diferença de 1,6 (não zero), o que
    tem cara de batente e não de clique perdido.

    Amarrando a direção ao nível alcançado, o zoom fica em dois degraus
    vizinhos e nunca chega ao batente. Aí "não mudou nada" só pode ser uma
    coisa: o clique se perdeu. Que é exatamente o que se quer contar.
    """
    acertos = 0
    movimentos = 0
    andou_total = 0
    detalhes = []
    nivel = 0                    # 0 ou 1: dois degraus vizinhos, longe do fim
    for _ in range(CLIQUES_POR_FASE):
        alvo = alvos[1] if nivel else alvos[0]   # nivel 1 -> volta com out
        cursor_antes = _cursor_fisico()
        pos_antes = ctx.memory.position()
        quadro_antes = capture_window(ctx.hwnd)
        if quadro_antes is None:
            log.warning("captura falhou; pulando este clique")
            continue
        antes = _regiao_do_minimapa(quadro_antes)

        teclado.left_click(alvo[0], alvo[1])
        time.sleep(ESPERA_DEPOIS_DO_CLIQUE)

        quadro_depois = capture_window(ctx.hwnd)
        depois = (_regiao_do_minimapa(quadro_depois)
                  if quadro_depois is not None else None)
        cursor_depois = _cursor_fisico()

        pos_depois = ctx.memory.position()
        d = _mudou(antes, depois)

        # O PERSONAGEM ANDOU ⇒ O CLIQUE CAIU NA CENA 3D, não no botão. E isso
        # MUDA O MINIMAPA (o marcador anda, o mapa rola), então sem esta
        # conferência o clique errado era contado como acerto -- foi o que
        # inflou as fases sem shield na medição de 18/08/2026, e quem viu foi o
        # usuário na tela, não o número.
        andou = (pos_antes is not None and pos_depois is not None
                 and pos_antes != pos_depois)
        andou_total += andou
        surtiu = (d >= DIFERENCA_QUE_E_EFEITO) and not andou
        acertos += surtiu
        if surtiu:
            nivel = 1 - nivel        # só anda o nível quando o zoom mudou
        mexeu = cursor_antes != cursor_depois
        movimentos += mexeu
        detalhes.append((alvo, round(d, 2), bool(surtiu), bool(mexeu),
                         bool(andou)))
        if andou:
            veredito = f"ERROU O ALVO (personagem andou {pos_antes}->{pos_depois})"
        elif surtiu:
            veredito = "EFEITO"
        else:
            veredito = "CLIQUE PERDIDO"
        log.info("[%s] %2d/%d alvo=%s diferenca=%.2f -> %s%s",
                 nome, len(detalhes), CLIQUES_POR_FASE, alvo, d, veredito,
                 "  (cursor mexeu)" if mexeu else "")

    return {
        "fase": nome,
        "cliques": len(detalhes),
        "acertos": acertos,
        "taxa": (acertos / len(detalhes)) if detalhes else 0.0,
        "com_cursor_em_movimento": movimentos,
        "personagem_andou": andou_total,
        "detalhes": detalhes,
    }


def janelas_do_jogo() -> list[dict]:
    """Toda janela visível do cliente, sem passar pelo supervisor.

    NÃO usa `AccountSupervisor._adotar_janela_existente()`, ao contrário do
    `teste_venda` e da `amostragem_de_cliques` -- e a diferença tem motivo. Lá a
    ferramenta roda DENTRO do processo do bot, então adotar/soltar é o que
    impede o bot de verdade de abrir um cliente novo. Aqui a ferramenta roda em
    processo PRÓPRIO (`python -m`), onde a lista de PIDs reivindicados do bot
    nem existe -- adotar não protegeria nada, e o caminho da adoção ainda ESCREVE
    no `config.json` (pode apagar o pino da janela). Enumerar e escolher é mais
    seguro: esta ferramenta não grava configuração nenhuma.
    """
    achadas: list[dict] = []
    # Filtra pelo PROCESSO, e não pelo título: o bot RENOMEIA a janela com o
    # nome do personagem ao logar, então "começa com Talisman Online" deixaria
    # de fora justamente as janelas que já estão em uso -- que são as que
    # interessam aqui. `client_pids()` é a mesma fonte que o supervisor usa.
    do_jogo = client_pids()

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True
        if pid not in do_jogo:
            return True
        esq, topo, dir_, baixo = win32gui.GetClientRect(hwnd)
        larg, alt = dir_ - esq, baixo - topo
        if larg < 640 or alt < 480:
            return True          # janelas-fantasma do mesmo processo
        achadas.append({"hwnd": hwnd, "pid": pid,
                        "titulo": win32gui.GetWindowText(hwnd) or "",
                        "tamanho": (larg, alt)})
        return True

    win32gui.EnumWindows(callback, None)
    return achadas


def rodar(config: BotConfig, account, hwnd: int, pid: int) -> dict:
    """Mede as duas fases na janela escolhida. Exige o bot PARADO."""
    parada = threading.Event()
    ctx = None
    try:
        ctx = BotContext(config=config, account=account, pid=pid, hwnd=hwnd,
                         stop_event=parada)

        # QUEM DECIDE SE ESTÁ NO JOGO É A LEITURA DE POSIÇÃO, não a flag
        # `ja_logado` do supervisor: reconhecida pelo PINO, a janela vem com
        # `ja_logado=False` mesmo com o personagem no mundo (o pino existe
        # justamente para identificar a janela no MEIO do login). E a distinção
        # importa muito aqui: na tela de login o clique no zoom não muda nada, as
        # duas fases dariam 0% e o veredito sairia INVERTIDO -- diria "o jogo lê
        # a posição de outro lugar" quando o que houve foi não haver minimapa.
        posicao = ctx.memory.position()
        if posicao is None:
            return {"ok": False, "erro": (
                "Não consigo ler a posição do personagem nesta janela — ou o "
                "cliente está na tela de login / seleção de personagem, ou a "
                "leitura de memória não respondeu. O teste precisa do "
                "personagem NO MUNDO, porque o alvo é o minimapa.")}
        log.info("Personagem no mundo em %s", posicao)

        alvos = [ctx.coords.minimap_zoom_in, ctx.coords.minimap_zoom_out]

        cx, cy = _cursor_fisico()
        esq, topo, dir_, baixo = _retangulo_da_janela(hwnd)
        if not (esq <= cx <= dir_ and topo <= cy <= baixo):
            return {"ok": False, "erro": (
                f"O cursor físico está FORA da janela do jogo ({cx},{cy}); a "
                f"janela vai de ({esq},{topo}) a ({dir_},{baixo}). Ponha o "
                f"mouse em cima do jogo, PARADO — é justamente essa situação "
                f"que se quer medir.")}

        cli = _para_cliente(hwnd, cx, cy)
        perto = min(abs(cli[0] - a[0]) + abs(cli[1] - a[1]) for a in alvos)
        if perto < DISTANCIA_MINIMA_DO_ALVO:
            return {"ok": False, "erro": (
                f"O cursor físico está a {perto}px dos botões de zoom (cliente "
                f"{cli}). Com o cursor em cima do alvo os dois mecanismos dão o "
                f"MESMO resultado e o teste não separa nada. Ponha o mouse no "
                f"meio da tela do jogo.")}

        log.info("=== TESTE DO CURSOR ===")
        log.info("Janela %s (pid %s) | cursor físico %s (cliente %s)",
                 hwnd, pid, (cx, cy), cli)
        log.info("Alvos: zoom_in=%s zoom_out=%s | cursor a %spx deles",
                 alvos[0], alvos[1], perto)

        # ================================================================
        # AS CINCO FASES
        # ================================================================
        #
        # A ordem é deliberada: as duas primeiras são a linha de base e a BARRA
        # (o que roda hoje). A terceira é CONTROLE NEGATIVO -- já medida como
        # ruim, ela existe para provar, numa corrida em que tudo der alto, que a
        # medição ainda sabe detectar falha. As duas últimas são o que se quer
        # descobrir.
        FASES = [
            ("SEM shield", False, "sendmessage_rapido"),
            ("COM shield (padrão)", True, "sendmessage_rapido"),
            ("REAFIRMADO (controle-)", False, "sendmessage_rapido_reafirmado"),
            ("PostMessage + shield", True, "postmessage_puro"),
            ("PostMessage SEM shield", False, "postmessage_puro"),
        ]

        shield_original = mod_inputs.USAR_MOUSE_SHIELD
        modo_original = mod_inputs.MODO_DE_CLIQUE
        resultados = []
        try:
            for nome, com_shield, modo in FASES:
                mod_inputs.USAR_MOUSE_SHIELD = com_shield
                mod_inputs.MODO_DE_CLIQUE = modo
                # `Input` NOVO por fase: o shield é decidido no `__init__`, então
                # reaproveitar o objeto carregaria o shield da fase anterior.
                resultados.append(
                    _uma_fase(ctx, mod_inputs.Input(hwnd), alvos, nome))
        finally:
            mod_inputs.USAR_MOUSE_SHIELD = shield_original
            mod_inputs.MODO_DE_CLIQUE = modo_original

        return {"ok": True,
                "fases": resultados,
                "cursor": {"tela": (cx, cy), "cliente": cli,
                           "distancia": perto},
                "resumo": _resumir(resultados)}
    except Exception as exc:
        log.exception("teste falhou")
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
    finally:
        if ctx is not None:
            ctx.close()


def _resumir(fases: list[dict]) -> str:
    """A tabela e o veredito. Exige as DUAS colunas, não só a taxa.

    Só a taxa já enganou uma vez nesta investigação: a métrica "o minimapa
    mudou?" é cega para o pior desfecho, que é o personagem ANDAR. Um clique que
    cai na cena 3D também muda o minimapa. Por isso "andou" tem coluna própria e
    entra no critério.
    """
    linhas = [
        f"{'fase':<26} {'acertos':>9}   {'andou':>5}   {'mexeu':>5}",
        "-" * 56,
    ]
    for r in fases:
        linhas.append(
            f"{r['fase']:<26} {r['acertos']:>3}/{r['cliques']:<3} "
            f"({r['taxa']:>4.0%})   {r['personagem_andou']:>5}   "
            f"{r['com_cursor_em_movimento']:>5}")
    linhas.append("")

    por_nome = {r["fase"]: r for r in fases}
    barra = por_nome.get("COM shield (padrão)")
    controle = por_nome.get("REAFIRMADO (controle-)")
    mexeu = barra and barra["com_cursor_em_movimento"] >= barra["cliques"] // 2

    if not mexeu:
        linhas.append(
            "MOUSE PARADO nesta corrida: sem disputa, quase tudo acerta e as "
            "fases não se separam. Rode de novo MEXENDO o mouse sobre a janela "
            "o tempo todo — é lá que a diferença aparece.")
        return chr(10).join(linhas)

    # CONTROLE NEGATIVO. Numa corrida em que tudo dá alto, é ele que prova que a
    # medição ainda sabe detectar falha. Sem essa checagem, "tudo passou" pode
    # significar "a medição parou de medir".
    if controle and controle["taxa"] >= 0.90:
        linhas.append(
            "ATENÇÃO: o CONTROLE NEGATIVO passou. A fase 'REAFIRMADO' está "
            "medida como ruim (fabrica arrasto); se ela acerta, a medição não "
            "está separando nada nesta corrida e NENHUM número abaixo vale.")
        return chr(10).join(linhas)

    def bom(r):
        return r and r["taxa"] >= 0.95 and r["personagem_andou"] == 0

    pm_com = por_nome.get("PostMessage + shield")
    pm_sem = por_nome.get("PostMessage SEM shield")

    if bom(pm_sem):
        linhas.append(
            "VEREDITO: PostMessage puro funciona SEM O SHIELD. É o melhor "
            "desfecho possível — o hook global sai de vez e o mouse do usuário "
            "deixa de pagar qualquer coisa, e o clique deixa de bloquear a "
            "thread (some o defeito do cliente travado pendurar a conta).")
    elif bom(pm_com):
        linhas.append(
            "VEREDITO: PostMessage puro empata com o padrão, mas PRECISA do "
            "shield. Vale a troca mesmo assim: o clique deixa de bloquear, o "
            "que elimina o cliente travado pendurando a thread da conta para "
            "sempre. O hook fica.")
    else:
        linhas.append(
            "VEREDITO: PostMessage puro NÃO empatou com o padrão "
            f"(shield+SendMessage: {barra['acertos']}/{barra['cliques']}, "
            f"andou {barra['personagem_andou']}). O padrão fica. Trocar "
            f"confiabilidade por não-bloqueio seria trocar um problema raro "
            f"(cliente travado) por um constante (clique perdido).")
    return chr(10).join(linhas)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s",
                        stream=sys.stdout, force=True)

    # SEM ADMIN NÃO DÁ PARA MEDIR NADA -- e o modo de falha é traiçoeiro. O
    # cliente roda elevado, e o Windows (UIPI) DESCARTA EM SILÊNCIO as mensagens
    # de janela vindas de processo não elevado: nenhum erro, o clique
    # simplesmente não acontece. As duas fases dariam 0% e o veredito sairia
    # INVERTIDO -- acusaria o jogo de ler a posição de outro lugar quando o que
    # houve foi o clique nunca ter chegado. Mesmo motivo da trava da posição.
    from main import require_admin
    require_admin()

    config = BotConfig.load()
    contas = [c for c in config.accounts if c.enabled] or config.accounts
    if not contas:
        print("Nenhuma conta configurada.")
        return 1
    janelas = janelas_do_jogo()
    if not janelas:
        print("Nenhuma janela de jogo encontrada. Abra o cliente e entre com "
              "o personagem.")
        return 1

    # A janela é ESCOLHIDA, não adivinhada. O reconhecimento automático do
    # supervisor errou aqui: reconheceu pelo pino e devolveu `ja_logado=False`
    # com o personagem no mundo, o que abortava o teste.
    escolhida = None
    argumento = [a for a in sys.argv[1:] if a.isdigit()]
    if argumento:
        alvo_hwnd = int(argumento[0])
        escolhida = next((j for j in janelas if j["hwnd"] == alvo_hwnd), None)
        if escolhida is None:
            print(f"A janela {alvo_hwnd} não está na lista.")
    if escolhida is None:
        print("\nJanelas de jogo abertas:\n")
        for i, j in enumerate(janelas, 1):
            print(f"  [{i}] hwnd={j['hwnd']}  pid={j['pid']}  "
                  f"{j['tamanho'][0]}x{j['tamanho'][1]}  {j['titulo'][:44]}")
        if len(janelas) == 1:
            escolhida = janelas[0]
            print("\nSó há uma; usando essa.")
        else:
            try:
                n = int(input(f"\nQual janela testar? [1-{len(janelas)}]: "))
            except (ValueError, EOFError):
                print("Escolha inválida.")
                return 1
            if not 1 <= n <= len(janelas):
                print("Escolha fora da lista.")
                return 1
            escolhida = janelas[n - 1]

    conta = next((c for c in contas if c.last_pid == escolhida["pid"]),
                 contas[0])
    print(f"\nJanela hwnd={escolhida['hwnd']} pid={escolhida['pid']}")
    print(f"Conta usada para a configuração: {conta.login or '(sem login)'}")
    print("\nPonha o mouse SOBRE essa janela, no MEIO da tela, e NÃO MEXA.")
    print("O teste leva cerca de 30 s. Começando em 8 s...")
    time.sleep(8)
    resultado = rodar(config, conta, escolhida["hwnd"], escolhida["pid"])
    print()
    if not resultado.get("ok"):
        print("FALHOU:", resultado.get("erro"))
        return 1
    print(resultado["resumo"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
