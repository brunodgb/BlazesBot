"""Aplica o patch do `BlazesBot - PetBug.exe`: esconder jogadores + pet bug.

=============================================================================
POR QUE ISTO EXISTE, E O QUE ELE SUBSTITUI
=============================================================================

O usuário tem um programa de terceiro que faz duas coisas no cliente do jogo:

  * o **esconder jogadores** por sessão -- o mesmo efeito que o truque do F12
    tentava produzir; e
  * um **"pet bug"** que, segundo ele, ajuda a não tomar disconnect.

Ele não tem o código, então não há o que portar. Mas o programa tem uma janela
com um botão `Patch`, e o log dele diz *"Patch applied to all running clients"* --
ou seja, **um clique cobre TODOS os clientes abertos de uma vez**.

Isto SUBSTITUI o F12 preso (`esconder_jogadores.SEGURAR_ATIVADO = False`), por
decisão do usuário em 19/08/2026: *"por enquanto desativa esse click no F12, em
vez disso você vai executar esse arquivo."*

=============================================================================
O PEDIDO ERA COORDENADA FIXA -- E DEU PARA FAZER MELHOR
=============================================================================

Ele autorizou clicar num ponto fixo: *"o botão Patch é fixo, não muda, então só
clicar no lugar fixo."* Coordenada fixa funciona, e teria funcionado -- mas
inspecionando a janela apareceu algo melhor:

    hwnd=1119894  classe='TButton'  texto='Patch'
    hwnd=202164   classe='TMemo'    (o log do programa)

São **controles Win32 de verdade** (é um programa Delphi). Isso troca duas
apostas por dois fatos:

**1. O clique vai no `hwnd` do BOTÃO, por `BM_CLICK`.** Não há coordenada para
envelhecer, não há como errar o alvo, e **funciona com a janela MINIMIZADA** --
que é como ela costuma ficar. Medido: minimizada, `GetClientRect` devolve
`(0,0,0,0)`, então qualquer conta baseada em tamanho de tela falharia ali.

**2. O RESULTADO É CONFERIDO, lendo o log do próprio programa.** `WM_GETTEXT` no
`TMemo` devolve o texto que a janela mostra:

    === Starting Pet Bug Fix & F12 Hide ===
    [OK] Patch applied to all running clients.
    === Completed ===

Então "cliquei" deixa de ser a única coisa que se sabe. É a regra da casa
aplicada a um programa de terceiro: *a cada clique, conferir se o esperado
aconteceu*.

A coordenada fixa fica como RESERVA, para o caso de o botão deixar de ser um
`TButton` localizável -- nunca pior que o pedido original.

=============================================================================
AS OUTRAS DUAS REGRAS DELE
=============================================================================

**"Caso esteja aberto, não reabra; use o que tiver aberto."** Procura a janela
pelo título antes de qualquer coisa. Abrir um segundo processo do patcher não é
inofensivo: dois programas mexendo nos mesmos clientes é a receita para um
desfazer o do outro.

**"A cada vez que uma conta com Bot BC ativa cair."** O patcher age nos clientes
que estão RODANDO; uma conta que caiu volta num cliente NOVO, que não foi
patcheado. Só contas de BC, também decisão dele.

=============================================================================
CINCO CONTAS, UM CLIQUE
=============================================================================

Cinco contas caem juntas com frequência -- está medido no `CLAUDE.md`, na regra do
login. Como um clique cobre todos os clientes, cinco supervisores chamando isto
ao mesmo tempo produziriam cinco cliques idênticos e inúteis.

`INTERVALO_MINIMO` resolve: o primeiro a chegar aplica para todos, e os outros
quatro veem que acabou de ser aplicado e seguem. O estado é de MÓDULO com lock,
igual ao quadro de convites do `bot/mural.py` -- os supervisores rodam no mesmo
processo.
"""
from __future__ import annotations

import ctypes
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import win32con
import win32gui

__all__ = ["ATIVADO", "Resultado", "aplicar_patch"]

# ===========================================================================
# INTERRUPTOR
# ===========================================================================
#
# `False` = não procura, não abre, não clica. `aplicar_patch` devolve na hora.
#
# Existe porque isto CHAMA UM PROGRAMA DE TERCEIRO cujo código ninguém tem. Se
# ele mudar de layout, de título ou de comportamento, desligar aqui é mais rápido
# que descobrir o que quebrou.
ATIVADO = True

# Onde o programa mora -- junto do bot, na raiz do projeto.
#
# DOIS NOMES porque o usuário renomeou o arquivo de "RaaskiBot" para "BlazesBot"
# em 19/08/2026. Aceitar os dois custa uma linha e evita que trocar o nome de
# volta (ou copiar o bot para outra máquina com o arquivo antigo) quebre a
# abertura -- o primeiro que existir é o usado.
NOMES_DO_PATCHER = ("BlazesBot - PetBug.exe", "RaaskiBot - PetBug.exe")

# A JANELA É PROCURADA PELO PEDAÇO COMUM, e é isso que permite renomeá-la.
#
# O programa abre com o título "RaaskiBot - PetBug" e o bot o renomeia para
# "BlazesBot - PetBug" (pedido do usuário). Se a busca fosse pelo título INTEIRO,
# a primeira execução acharia e a segunda não -- o rename quebraria o próprio
# mecanismo que o encontrou.
#
# "PetBug" está nos dois nomes, então uma busca só cobre antes e depois. É a mesma
# ideia do `state_conn_prefix` do login: casar pelo que NÃO muda.
PEDACO_DO_TITULO = "PetBug"

# ---------------------------------------------------------------------------
# RENOMEAR A JANELA NÃO FUNCIONA -- MEDIDO, NÃO SUPOSTO
# ---------------------------------------------------------------------------
#
# O usuário pediu para renomear a janela para "BlazesBot - PetBug". Foi tentado
# contra a janela real, e ela RECUSA:
#
#     WM_GETTEXT              -> 'RaaskiBot - PetBug'
#     SetWindowText(...)      -> sem erro
#     SendMessage(WM_SETTEXT) -> devolveu 0   (recusado)
#     WM_GETTEXT depois       -> 'RaaskiBot - PetBug'   (não mudou)
#
# É um formulário Delphi (VCL), e o `Caption` dele não aceita ser trocado de
# fora. O código de rename foi REMOVIDO em vez de ficar como tentativa: função
# que provadamente não faz nada é peso morto, e a próxima pessoa gastaria o mesmo
# tempo descobrindo o mesmo.
#
# O USUÁRIO RESOLVEU A PARTE QUE DAVA: renomeou o ARQUIVO para "BlazesBot -
# PetBug.exe". O título da janela continua vindo de dentro do programa.
#
# E a busca por `PEDACO_DO_TITULO` cobre os dois casos de qualquer forma -- foi
# escolhida para sobreviver a um rename que acabou não acontecendo, e vale igual.

# Como o botão é reconhecido: classe e texto, medidos na janela real.
CLASSE_DO_BOTAO = "TButton"
TEXTO_DO_BOTAO = "Patch"
# O log do programa.
CLASSE_DO_LOG = "TMemo"

# Confirmação no log. Casa a linha `[OK] Patch applied to all running clients.`
# sem depender da pontuação nem do resto da frase.
SINAL_DE_SUCESSO = re.compile(r"patch\s+applied", re.IGNORECASE)

# RESERVA, e só isso: coordenada do centro do botão na área de cliente, derivada
# do print do usuário (janela 383x401, botão de y=310 a y=347, menos ~31 px de
# barra de título). Usada apenas se o `TButton` não for localizável.
PONTO_FIXO_DO_PATCH = (190, 297)

BM_CLICK = 0x00F5

# ---------------------------------------------------------------------------
# Tempos
# ---------------------------------------------------------------------------
#
# Intervalo mínimo entre duas aplicações. Cinco contas caem juntas, e um clique
# cobre todos os clientes. 30 s é folgado para uma queda em grupo e curto para
# não perder um relogin solitário que venha logo depois.
INTERVALO_MINIMO = 30.0

# Espera pela janela aparecer depois de lançar o programa.
SEGUNDOS_PARA_A_JANELA_ABRIR = 10.0
# Espera pela confirmação no log depois do clique.
SEGUNDOS_PARA_O_LOG_CONFIRMAR = 5.0
FATIA_DA_ESPERA = 0.25


_LOCK = threading.Lock()
_ULTIMA_APLICACAO = 0.0


@dataclass(frozen=True, slots=True)
class Resultado:
    aplicou: bool
    confirmado_no_log: bool
    lancou_o_programa: bool
    motivo: str

    def __str__(self) -> str:
        return self.motivo


# ===========================================================================
# Win32 -- as peças, isoladas para o teste poder substituí-las
# ===========================================================================

def achar_janela(titulo: str = PEDACO_DO_TITULO) -> int | None:
    """`hwnd` da janela do patcher, ou `None`. Acha minimizada também."""
    achadas: list[int] = []

    def visitar(hwnd: int, _) -> bool:
        try:
            if titulo in (win32gui.GetWindowText(hwnd) or ""):
                achadas.append(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(visitar, None)
    except Exception:
        return None
    return achadas[0] if achadas else None


def _filhos(janela: int) -> list[tuple[int, str, str]]:
    """(hwnd, classe, texto) de cada controle da janela."""
    saida: list[tuple[int, str, str]] = []

    def visitar(hwnd: int, _) -> bool:
        try:
            saida.append((hwnd, win32gui.GetClassName(hwnd) or "",
                          win32gui.GetWindowText(hwnd) or ""))
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(janela, visitar, None)
    except Exception:
        pass
    return saida


def achar_botao(janela: int) -> int | None:
    """`hwnd` do botão `Patch`. `None` se ele não for localizável."""
    for hwnd, classe, texto in _filhos(janela):
        if classe == CLASSE_DO_BOTAO and texto.strip() == TEXTO_DO_BOTAO:
            return hwnd
    return None


def achar_log(janela: int) -> int | None:
    for hwnd, classe, _texto in _filhos(janela):
        if classe == CLASSE_DO_LOG:
            return hwnd
    return None


def ler_texto(controle: int) -> str:
    """Texto de um controle de OUTRO processo, por `WM_GETTEXT`.

    `GetWindowText` devolve vazio para controle de outro processo; `WM_GETTEXT`
    funciona. Medido nesta janela: `GetWindowText` deu `''` e o `WM_GETTEXT`
    devolveu as três linhas do log.
    """
    try:
        n = win32gui.SendMessage(controle, win32con.WM_GETTEXTLENGTH, 0, 0)
        if not n:
            return ""
        buffer = ctypes.create_unicode_buffer(n + 1)
        win32gui.SendMessage(controle, win32con.WM_GETTEXT, n + 1, buffer)
        return buffer.value
    except Exception:
        return ""


def clicar_no_botao(botao: int) -> bool:
    """`BM_CLICK` no botão. Sem coordenada, e funciona minimizado."""
    try:
        win32gui.SendMessage(botao, BM_CLICK, 0, 0)
        return True
    except Exception:
        return False


def clicar_por_coordenada(janela: int, ponto: tuple[int, int]) -> bool:
    """RESERVA: clique posicional na janela, como o usuário autorizou."""
    x, y = ponto
    lparam = (y << 16) | (x & 0xFFFF)
    try:
        win32gui.SendMessage(janela, win32con.WM_LBUTTONDOWN, 1, lparam)
        win32gui.SendMessage(janela, win32con.WM_LBUTTONUP, 0, lparam)
        return True
    except Exception:
        return False


# ===========================================================================
# A aplicação
# ===========================================================================

def aplicar_patch(
    *,
    log,
    raiz: Path | None = None,
    forcar: bool = False,
    janelas=None,
) -> Resultado:
    """Encontra (ou abre) o patcher, clica em `Patch` e CONFERE no log dele.

    `janelas` substitui as funções Win32 num teste -- qualquer objeto com
    `achar_janela`, `achar_botao`, `achar_log`, `ler_texto`, `clicar_no_botao`,
    `clicar_por_coordenada`, `esperar` e `abrir`.

    `forcar=True` ignora o `INTERVALO_MINIMO`. Serve para um botão de
    diagnóstico; o caminho normal respeita o intervalo.
    """
    global _ULTIMA_APLICACAO

    if not ATIVADO:
        return Resultado(False, False, False,
                         "PetBug DESLIGADO (petbug.ATIVADO)")

    j = janelas if janelas is not None else _Win32()

    with _LOCK:
        desde = time.monotonic() - _ULTIMA_APLICACAO
        if not forcar and _ULTIMA_APLICACAO and desde < INTERVALO_MINIMO:
            return Resultado(
                False, False, False,
                f"patch aplicado há {desde:.0f}s (por esta conta ou por outra); "
                "um clique cobre todos os clientes")
        # Reserva o intervalo ANTES de agir: sem isto, duas contas passariam pela
        # janela de tempo enquanto a primeira ainda está clicando.
        _ULTIMA_APLICACAO = time.monotonic()

    janela = j.achar_janela(PEDACO_DO_TITULO)
    lancou = False
    if janela is None:
        resultado_ou_janela = _abrir_o_programa(j, log, raiz)
        if isinstance(resultado_ou_janela, Resultado):
            return resultado_ou_janela
        janela, lancou = resultado_ou_janela, True
    else:
        log.info("PetBug: usando a janela que já está aberta")

    controle_do_log = j.achar_log(janela)
    antes = j.ler_texto(controle_do_log) if controle_do_log else ""

    if not _clicar(j, janela, log):
        return Resultado(False, False, lancou,
                         "não consegui clicar em Patch")

    confirmado, texto = _esperar_a_confirmacao(j, controle_do_log, antes)
    if confirmado:
        return Resultado(True, True, lancou,
                         "patch aplicado e CONFIRMADO no log do programa")
    if controle_do_log is None:
        return Resultado(True, False, lancou,
                         "cliquei em Patch; não achei o log do programa para "
                         "conferir")
    return Resultado(True, False, lancou,
                     "cliquei em Patch e o log NÃO confirmou em "
                     f"{SEGUNDOS_PARA_O_LOG_CONFIRMAR:.0f}s "
                     f"(última linha: {texto.strip().splitlines()[-1:] or ['vazio']})")


def _abrir_o_programa(j, log, raiz: Path | None):
    """Abre o patcher e espera a janela. Devolve o `hwnd` ou um `Resultado`."""
    base = raiz or Path(".")
    caminho = next((base / nome for nome in NOMES_DO_PATCHER
                    if (base / nome).is_file()), None)
    if caminho is None:
        return Resultado(False, False, False,
                         f"não achei o programa em {base} "
                         f"(procurei por {' ou '.join(NOMES_DO_PATCHER)})")

    log.info("PetBug: o programa não está aberto; abrindo %s", caminho)
    try:
        j.abrir(caminho)
    except OSError as exc:
        return Resultado(False, False, False,
                         f"não consegui abrir o programa: {exc}")

    gasto = 0.0
    while gasto < SEGUNDOS_PARA_A_JANELA_ABRIR:
        j.esperar(FATIA_DA_ESPERA)
        gasto += FATIA_DA_ESPERA
        janela = j.achar_janela(PEDACO_DO_TITULO)
        if janela is not None:
            return janela
    return Resultado(False, False, True,
                     "abri o programa e a janela não apareceu em "
                     f"{SEGUNDOS_PARA_A_JANELA_ABRIR:.0f}s")


def _clicar(j, janela: int, log) -> bool:
    """`BM_CLICK` no botão; coordenada fixa como reserva."""
    botao = j.achar_botao(janela)
    if botao is not None:
        log.info("PetBug: clicando no botão Patch (hwnd %s)", botao)
        if j.clicar_no_botao(botao):
            return True
        log.warning("PetBug: o BM_CLICK falhou; caio na coordenada fixa")

    log.info("PetBug: botão não localizável; clique na coordenada fixa %s",
             PONTO_FIXO_DO_PATCH)
    return j.clicar_por_coordenada(janela, PONTO_FIXO_DO_PATCH)


def _esperar_a_confirmacao(j, controle_do_log: int | None,
                           antes: str) -> tuple[bool, str]:
    """Espera o log dizer que aplicou.

    ACEITA O TEXTO IGUAL AO DE ANTES. O programa reescreve as mesmas três linhas
    a cada Patch, então exigir que o texto MUDE reprovaria uma aplicação
    bem-sucedida -- só porque ela produziu a mesma saída da anterior. O que se
    exige é o texto DIZER que aplicou.
    """
    if controle_do_log is None:
        return False, antes

    gasto = 0.0
    texto = antes
    while gasto < SEGUNDOS_PARA_O_LOG_CONFIRMAR:
        texto = j.ler_texto(controle_do_log)
        if SINAL_DE_SUCESSO.search(texto):
            return True, texto
        j.esperar(FATIA_DA_ESPERA)
        gasto += FATIA_DA_ESPERA
    return False, texto


class _Win32:
    """As peças de verdade. Substituída por um dublê nos testes."""

    achar_janela = staticmethod(achar_janela)
    achar_botao = staticmethod(achar_botao)
    achar_log = staticmethod(achar_log)
    ler_texto = staticmethod(ler_texto)
    clicar_no_botao = staticmethod(clicar_no_botao)
    clicar_por_coordenada = staticmethod(clicar_por_coordenada)

    @staticmethod
    def esperar(segundos: float) -> None:
        time.sleep(segundos)

    @staticmethod
    def abrir(caminho: Path) -> None:
        subprocess.Popen([str(caminho)], cwd=str(caminho.parent))
