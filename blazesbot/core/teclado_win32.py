"""O `lParam` de uma mensagem de teclado -- o registro de bits que o Windows exige.

=========================================================================
O DEFEITO QUE ISTO CONSERTA -- 11/09/2026
=========================================================================

Sintoma relatado: com o jogo em SEGUNDO PLANO e o usuário segurando SHIFT no
navegador, o cliente passava a ler "SHIFT + tecla do bot". O comando virava
outro e a skill não saía.

`Input._liberar_modificadores_fisicos` já existia e já mandava o `WM_KEYUP`.
Ela não funcionava porque `_enviar_tecla` chumbava `LPARAM(0)` -- e **um
WM_KEYUP com lParam zerado é malformado**: ele afirma que a tecla NÃO estava
pressionada (bit 30 = 0) e que NÃO está havendo transição para solta (bit 31 =
0). O cliente lê um registro que se contradiz e ignora a mensagem.

=========================================================================
A MATEMÁTICA, campo por campo
=========================================================================

    bits  0-15   contagem de repetição      -> 1
    bits 16-23   SCAN CODE da tecla         -> scan_code << 16
    bit     24   tecla estendida            -> 0
    bits 25-28   reservado                  -> 0
    bit     29   contexto (ALT apertado)    -> 0
    bit     30   ESTADO ANTERIOR            -> 1  (a tecla ESTAVA apertada)
    bit     31   ESTADO DE TRANSIÇÃO        -> 1  (está sendo SOLTA agora)

O SCAN CODE tem de ser o REAL do teclado do usuário, e é por isso que
`win32api.MapVirtualKey(vk, 0)` (MAPVK_VK_TO_VSC) entra aqui em vez de um
número fixo: **o VK é lógico e igual em toda máquina; o scan code é FÍSICO e
muda com o layout.** Mandar o scan errado é mandar outra tecla.

=========================================================================
POR QUE MÓDULO PRÓPRIO, E NÃO MAIS UM PEDAÇO DE `inputs.py`
=========================================================================

`core/inputs.py` está em 1221 linhas com teto de 1222 na catraca de tamanho do
projeto -- ou seja, ele não pode crescer, e a regra da casa é **mover conteúdo,
não comprimir texto**.

Mas o motivo de verdade não é a contagem: montar um registro de bits do Windows
**não precisa saber nada sobre o bot**. Não conhece `hwnd`, nem conta, nem o
interruptor `MODO_DE_TECLA`. É a mesma pergunta que `core/janelas.py` responde
para janelas -- sobre o WINDOWS, não sobre o farm.

=========================================================================
O QUE ISTO NÃO RESOLVE
=========================================================================

Um KEYUP na fila da janela conserta o estado de teclado **por thread**, que é o
que `GetKeyState` devolve quando o cliente processa a mensagem. Ele **não** toca
`GetAsyncKeyState` nem RawInput, que leem o hardware -- nenhuma mensagem
sintética toca. Se o cliente ler o estado assíncrono, o vazamento continua, e a
saída não existe por mensagem.
"""
from __future__ import annotations

# Bits do registro. Nomeados porque `1 << 30` solto no meio de uma expressão
# não diz nada a quem lê depois -- e é justamente o bit que estava faltando.
BIT_ESTADO_ANTERIOR = 30      # a tecla ESTAVA apertada
BIT_TRANSICAO = 31            # e está sendo SOLTA agora

# `MAPVK_VK_TO_VSC`: traduz código virtual (lógico) para scan code (físico).
MAPVK_VK_TO_VSC = 0


def scan_code_de(vk: int) -> int:
    """O scan code FÍSICO daquele código virtual, no layout atual.

    Zero quando o Windows não sabe mapear. Não é erro: o registro continua
    válido sem o scan code, porque quem faz a mensagem ser aceita são os bits
    30 e 31. Melhor uma tecla solta sem scan do que nenhuma tecla solta.
    """
    import win32api

    try:
        return int(win32api.MapVirtualKey(int(vk), MAPVK_VK_TO_VSC))
    except Exception:
        return 0


def lparam_de_keyup(vk: int) -> int:
    """O `lParam` de um `WM_KEYUP` BEM FORMADO para aquele código virtual.

    É a fórmula do cabeçalho, e ela é uma linha só de propósito -- cada termo
    é um campo do registro, e separá-los em variáveis esconderia que se trata
    de UM número.
    """
    return 1 | (scan_code_de(vk) << 16) | (1 << BIT_ESTADO_ANTERIOR) | (
        1 << BIT_TRANSICAO)
