"""A INJEÇÃO DE TEXTO BLINDADA: tamanho, conteúdo e destino, conferidos.

=========================================================================
DE ONDE ISTO VEIO -- o vazamento de teclas de 09/09/2026
=========================================================================

O usuário capturou **918 caracteres** de lixo digitados no **Bloco de Notas**,
crescendo ~10 por tentativa durante um laço de relogin.

O texto ter chegado ao Bloco de Notas é a prova de onde estava o defeito.
`PostMessageW` e `SendMessageW` entregam a UM `hwnd`: para caracteres
aparecerem em outro programa, o `hwnd` que o bot usava **era** do outro
programa. O Windows recicla valores de handle -- é o defeito que a trava de
janela (`inputs._motivo_para_nao_enviar`) existe para impedir, e que ela
deixou passar pelo PINO TARDIO.

Aquela brecha está fechada lá. Este módulo é a SEGUNDA linha, e existe porque
a trava da janela confere DESTINO e aqui se confere CONTEÚDO -- defeitos
diferentes pedem defesas diferentes.

=========================================================================
POR QUE MÓDULO PRÓPRIO, E NÃO MAIS UM PEDAÇO DE `inputs.py`
=========================================================================

`core/inputs.py` já passava de 1200 linhas quando isto nasceu, e a catraca de
tamanho do projeto reprovou o crescimento -- corretamente. Mas o motivo de
verdade não é a contagem: é que **isto não precisa saber como uma mensagem sai**.

As funções daqui recebem a `entrada` e usam três coisas dela -- conferir a
janela, soltar os modificadores, mandar uma mensagem. Nada mais. É por isso que
elas são funções soltas e não métodos: quem valida texto não precisa conhecer
`ctypes`, `HWND`, `lParam` nem o interruptor `MODO_DE_TECLA`.

`Input.type_string_safely` e `Input.clear_field` continuam existindo e delegam
para cá. A API que o resto do bot usa não mudou.
"""
from __future__ import annotations

import logging
import time

_logger = logging.getLogger("blazes.inputs")

# ===========================================================================
# OS TETOS -- trava de segurança, não configuração
# ===========================================================================
#
# Os quatro chamadores de digitação do bot são todos curtos:
#
#     login da conta        `bot/login.py`        ~10-20 caracteres
#     senha da conta        `bot/login.py`        ~8-20 caracteres
#     nick de um aliado     `bot/team.py`         ~12 (limite do jogo)
#     nome de lugar/item    `bot/navegacao.py`, `bot/ui_do_jogo.py`
#
# 50 é folga de mais de duas vezes sobre o maior. O teto NÃO existe para caber
# o caso legítimo: existe para que um texto que ninguém escreveu à mão -- lixo
# de leitura de memória, laço enlouquecido, valor cifrado vazando no lugar do
# decifrado -- seja RECUSADO ALTO em vez de sair tecla por tecla.
#
# RECUSA, não trunca. Truncar mandaria 50 caracteres de lixo e esconderia o
# defeito; a exceção aborta a ação e o log guarda a prova.
LIMITE_DE_CARACTERES = 50

# O mesmo para o BACKSPACE. `login._do_credentials` pede 50 -- o maior pedido
# legítimo do bot --, e o teto fica logo acima dele. Um laço de limpeza que
# enlouquecesse bate aqui em vez de martelar a janela para sempre.
LIMITE_DE_BACKSPACES = 64


class TextoRecusado(ValueError):
    """A injeção foi RECUSADA antes de sair uma única tecla.

    Levantada, e não engolida, de propósito: quem pediu para digitar algo
    inválido está com um defeito, e defeito que segue em silêncio é o que
    produziu 918 caracteres de lixo na janela de outro programa.
    """


def _e_caractere_de_controle(ch: str) -> bool:
    """Caractere que NUNCA faz parte de login, senha ou nick.

    É justamente a assinatura de um texto que veio de onde não devia -- bytes
    crus lidos da memória do jogo, por exemplo, chegando aqui como se fossem
    texto.
    """
    return ord(ch) < 0x20 or ord(ch) == 0x7F


def injetar_texto(entrada, text: str, per_char: float = 0.04,
                  rotulo: str = "texto") -> int:
    """Digita `text` via `WM_CHAR`. Devolve QUANTOS caracteres saíram.

    Levanta `TextoRecusado` quando o pedido é inválido -- antes da primeira
    tecla. As três conferências:

      TAMANHO   nada que este bot digita passa de `LIMITE_DE_CARACTERES`.
                Um pedido de 1000 caracteres não é um pedido grande: é defeito.
      CONTEÚDO  caractere de controle não existe em credencial nem em nick.
      DESTINO   a janela é reconferida A CADA CARACTERE, e o envio PARA quando
                ela deixa de ser confiável. Antes, `_enviar_tecla` barrava
                mensagem por mensagem em silêncio e o laço ia até o fim --
                nenhuma parada, e o resto do texto perseguindo um handle que já
                podia ter trocado de dono.

    O LOG NUNCA MOSTRA O TEXTO. `rotulo` diz O QUE estava sendo digitado
    ("login", "senha") e o número diz O TAMANHO. Senha em arquivo de log é
    senha vazada.
    """
    # Import tardio: `inputs` importa este módulo, e o caminho contrário no topo
    # fecharia o ciclo. São dois nomes, e o `sys.modules` já resolveu o custo.
    from .inputs import WM_CHAR, jitter

    if not isinstance(text, str):
        raise TextoRecusado(
            f"{rotulo}: esperava texto e veio {type(text).__name__} -- quem "
            "chamou está passando a coisa errada")
    if not text:
        return 0
    if len(text) > LIMITE_DE_CARACTERES:
        raise TextoRecusado(
            f"{rotulo}: {len(text)} caracteres, acima do teto de "
            f"{LIMITE_DE_CARACTERES}. Nada foi digitado. Texto deste tamanho "
            "não vem de configuração -- vem de defeito.")
    ruins = {ch for ch in text if _e_caractere_de_controle(ch)}
    if ruins:
        raise TextoRecusado(
            f"{rotulo}: {len(ruins)} caractere(s) de controle no texto "
            f"(códigos {sorted(ord(c) for c in ruins)}). Nada foi digitado.")

    # O DESTINO, ANTES DA PRIMEIRA TECLA e alto. Sem isto a recusa sairia como
    # um bloqueio por mensagem, lá dentro, sem ninguém saber que a ação inteira
    # não aconteceu.
    if not entrada._janela_confiavel():
        _logger.error("%s: NÃO digitei nada -- a janela não é confiável.",
                      rotulo)
        return 0

    # Modificador virtualmente preso troca a tecla que chega do outro lado: um
    # SHIFT grudado transforma o login inteiro em maiúsculas. Uma vez por
    # injeção, e não por caractere -- são três mensagens a mais, não tres por letra.
    entrada._liberar_modificadores_fisicos()

    enviados = 0
    for ch in text:
        # A JANELA PODE MORRER NO MEIO, e no relogin esse é o caso normal: o
        # cliente cai com a senha sendo digitada.
        if not entrada._janela_confiavel():
            _logger.error(
                "%s: interrompido no caractere %s de %s -- a janela deixou de "
                "ser confiável no meio da digitação.",
                rotulo, enviados + 1, len(text))
            break
        entrada._enviar_tecla(WM_CHAR, ord(ch))
        enviados += 1
        time.sleep(jitter(per_char, 0.4))
    return enviados


def limpar_campo(entrada, presses: int = 50) -> None:
    """Apaga um campo com BACKSPACE repetido, com teto e com parada.

    O teto é trava, não configuração: um laço de limpeza enlouquecido foi uma
    das suspeitas do lixo, e aqui ele bate no teto em vez de martelar a janela.

    Pára quando a janela deixa de ser confiável -- 50 teclas perseguindo um
    handle reciclado são 50 teclas no programa errado.
    """
    if presses > LIMITE_DE_BACKSPACES:
        raise TextoRecusado(
            f"limpeza de campo pediu {presses} BACKSPACE, acima do teto de "
            f"{LIMITE_DE_BACKSPACES}. Nada foi apagado.")
    for _ in range(max(0, presses)):
        if not entrada._janela_confiavel():
            _logger.error("limpeza de campo interrompida: janela não confiável.")
            return
        # BACKSPACE pelo NOME, resolvido em `VK_CODES` (0x08) -- nunca por
        # literal. Era a outra suspeita do lixo: um laço de limpeza mapeado na
        # tecla errada digitaria letras em vez de apagar.
        entrada.key("BACKSPACE", hold=0.01)
