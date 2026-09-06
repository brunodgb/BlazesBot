"""O hook global de mouse não pode viver com o bot parado.

=========================================================================
O QUE ESTES TESTES PROTEGEM
=========================================================================

O `MouseShield` instala UM hook `WH_MOUSE_LL` na criação do primeiro `Input` e
NADA o desinstalava: ele vivia até o processo morrer, inclusive com o bot parado.
O usuário fechava o bot na interface, ia usar o computador, e cada evento de
mouse do sistema continuava sendo entregue ao nosso processo.

Mesmo com o callback em 0,6 µs (medido), um hook de baixo nível obriga o Windows
a marshalar CADA evento para o processo que hookeou e aguardar a resposta. Com o
bot parado esse custo não compra nada -- não há clique para proteger.

E a desinstalação tem que ser ADIADA: `stop()` só sinaliza, e as threads das
contas podem estar no meio de um clique. Arrancar o hook ali deixaria esse clique
sem proteção, e sem shield a medição diz 1/20 com o personagem ANDANDO em 14 dos
20 cliques.
"""
from __future__ import annotations

import inspect

from blazesbot.bot import supervisor as mod_supervisor
from blazesbot.core.mouse_shield import MouseShield


def test_o_stop_solta_o_mouse_do_usuario():
    fonte = inspect.getsource(mod_supervisor.BotManager.stop)
    assert "_soltar_o_mouse_do_usuario" in fonte, (
        "o bot para e o hook global continua instalado — o mouse do usuário "
        "paga a travessia do hook sem nada em troca")


def test_a_desinstalacao_ESPERA_as_contas_terminarem():
    """Arrancar o hook em `stop()` deixaria o clique em voo sem proteção."""
    fonte = inspect.getsource(mod_supervisor.BotManager._soltar_o_mouse_do_usuario)
    assert "join" in fonte, (
        "o hook é desinstalado sem esperar as threads — um clique em voo perde "
        "a proteção justamente na parada")
    assert "uninstall_hook" in fonte
    assert "daemon=True" in fonte, (
        "a espera roda na thread do chamador e travaria a interface no clique "
        "de Parar")


def test_uninstall_deixa_o_estado_PRONTO_para_reinstalar():
    """Reinstalar tem que ser automático no `Iniciar` seguinte.

    `_ensure_hook_installed` começa com `if _hook_installed or _hook_thread is
    not None: return`. Se o uninstall deixasse a thread preenchida, todo shield
    criado depois seguiria SEM HOOK, em silêncio.
    """
    MouseShield(1)
    assert MouseShield._hook_installed is True
    MouseShield.uninstall_hook()
    assert MouseShield._hook_handle is None
    assert MouseShield._hook_installed is False
    assert MouseShield._hook_thread is None, (
        "a thread ficou preenchida; `_ensure_hook_installed` vai retornar de "
        "imediato para sempre e o shield nunca volta")
    MouseShield(2)
    assert MouseShield._hook_installed is True, "o hook não voltou"


def test_o_callback_sai_na_PRIMEIRA_pergunta_quando_nada_bloqueia():
    """A garantia de custo para o mouse do usuário fora de um clique do bot.

    A ordem das perguntas é o desenho: uma comparação de float antes de qualquer
    chamada Win32 ou desempacotamento de struct. Se `CallNextHookEx` passar a ser
    alcançado por outro caminho mais caro, o custo por evento volta a subir.
    """
    fonte = inspect.getsource(
        __import__("blazesbot.core.mouse_shield", fromlist=["_mouse_proc"])
        ._mouse_proc)
    i_relogio = fonte.find("_ATE_QUANDO")
    i_struct = fonte.find("MSLLHOOKSTRUCT")
    assert i_relogio != -1 and i_struct != -1
    assert i_relogio < i_struct, (
        "o callback desempacota a struct do evento ANTES de conferir se há "
        "bloqueio ativo — isso é trabalho em todo movimento do mouse do usuário")


# A TRAVA DA INJEÇÃO MUDOU DE ARQUIVO -- e de ESCOPO.
#
# Aqui vivia `test_nao_existe_injecao_na_fila_do_SO`, que reprovava
# `SendInput`/`mouse_event`/`SetCursorPos` **dentro de `inputs.py`**. O
# vazamento que ela existe para impedir (o mouse FÍSICO do usuário sendo puxado
# pelo bot) nunca precisou passar por lá: um `import pyautogui` no `catador.py`
# ou numa ferramenta de `tools/` faria o mesmo estrago sem tocar neste módulo.
#
# A mesma trava agora varre o PACOTE INTEIRO, e ganhou de companhia a do roubo
# de foco: `tests/test_bot_fantasma.py`. Não foi apagada -- foi promovida.


# =====================================================================
# O shield no caminho do PostMessage
# =====================================================================

def test_o_postmessage_ENGAJA_o_shield():
    """Ligar `USAR_MOUSE_SHIELD` não basta: o caminho tem que CHAMAR o shield.

    Foi assim que a medição de 18/08/2026 mediu nada: as fases "PostMessage +
    shield" e "PostMessage SEM shield" deram 20/20 cada porque
    `_click_postmessage_puro` não chamava `block_momentarily` -- o hook estava
    instalado e nunca engolia evento nenhum. As duas eram o MESMO teste.
    """
    import ast
    import textwrap

    from blazesbot.core import inputs as mod

    src = textwrap.dedent(
        inspect.getsource(mod.Input._click_postmessage_puro))
    chamadas = [n.func.attr for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)]
    assert "block_momentarily" in chamadas, (
        "o caminho do PostMessage não engaja o shield — ligar o interruptor "
        "instalaria o hook sem bloquear nada")


def test_o_postmessage_NAO_solta_o_bloqueio_no_fim():
    """E isso é do mecanismo, não descuido.

    No caminho síncrono, `liberar()` é possível porque o retorno do
    `SendMessageW` PROVA que o WndProc rodou. Com PostMessage não existe essa
    prova: as mensagens ficam na fila até o jogo bombear. Soltar logo depois de
    postar liberaria o mouse físico ANTES de o jogo processar o que acabamos de
    enfileirar — e um move físico nessa janela é processado antes do nosso botão,
    que é exatamente a falha que o shield existe para impedir.
    """
    import ast
    import textwrap

    from blazesbot.core import inputs as mod

    src = textwrap.dedent(
        inspect.getsource(mod.Input._click_postmessage_puro))
    chamadas = [n.func.attr for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)]
    assert "liberar" not in chamadas, (
        "o bloqueio é solto logo após postar — o mouse físico volta antes de o "
        "jogo processar a fila, e o shield deixa de proteger justamente a "
        "janela que importa")
    assert "SendMessageW" not in chamadas, (
        "voltou a misturar SendMessage no caminho PostMessage — isso FURA A "
        "FILA e reintroduz a inversão que reprovou os dois híbridos de agosto")
