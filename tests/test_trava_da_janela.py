"""NENHUMA TECLA SAI PARA UMA JANELA QUE NÃO É O JOGO.

Defeito relatado em 25/08/2026, durante o login:

    *"tem vezes que o clique das teclas está vazando... 'rggddwlqrjcrw' digitou
     isso no bloco de notas enquanto abria o jogo e foi sozinho... teve vezes
     que do nada no jogo começou a abrir janelas aleatórias... quando a conta
     logava parava"*

Como isso é possível com `PostMessageW`, que entrega a UMA janela só:

  1. **O Windows RECICLA HWND.** A janela do cliente morre e o mesmo número de
     handle é entregue a outra janela -- o Bloco de Notas, por exemplo. O
     `Input` guardava o `hwnd` no `__init__` e não conferia nunca mais.
  2. **`hwnd = 0xFFFF` é `HWND_BROADCAST`**, que entrega a TODAS as janelas de
     topo de uma vez -- explicaria os dois sintomas juntos.
  3. Um `hwnd` de outra conta faz uma conta digitar na janela da outra.

O login é onde mais aparece porque é onde a janela está NASCENDO, e porque a
digitação de usuário/senha é o trecho com mais teclas seguidas do bot.

O que este arquivo trava é que a conferência acontece ANTES de cada mensagem, e
que ela não bloqueia por "não sei".
"""
import time

import pytest

from blazesbot.core import inputs


def _entrada(hwnd, pid_da_janela, nome_do_processo="client.exe"):
    """Um `Input` sem construtor -- não há janela de verdade no teste."""
    e = inputs.Input.__new__(inputs.Input)
    e.hwnd = hwnd
    e._pid_da_janela = pid_da_janela
    e._nome_do_processo = nome_do_processo
    e._conferido_em = time.monotonic()
    e._bloqueadas = 0
    e._motivo_do_bloqueio = None
    e._teclas_presas = {}
    # A lista de INTOCÁVEIS -- ver `Input.segurar_para_sempre`.
    e._presas_para_sempre = set()
    e._shield = None
    return e


# ===========================================================================
# O QUE TEM QUE SER BARRADO
# ===========================================================================

def test_hwnd_zero_nao_envia(monkeypatch):
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    assert _entrada(0, 100)._motivo_para_nao_enviar() is not None


def test_HWND_BROADCAST_nao_envia(monkeypatch):
    """`0xFFFF` acerta TODA janela de topo do sistema de uma vez -- é o valor
    que transformaria um bug de handle em digitação simultânea em tudo que está
    aberto, inclusive o Bloco de Notas E o jogo."""
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    motivo = _entrada(inputs.HWND_BROADCAST, 100)._motivo_para_nao_enviar()
    assert motivo is not None
    assert "BROADCAST" in motivo


def test_janela_morta_nao_envia(monkeypatch):
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 0)
    motivo = _entrada(0x1234, 100)._motivo_para_nao_enviar()
    assert motivo is not None
    assert "não existe" in motivo


def test_handle_RECICLADO_para_outro_processo_nao_envia(monkeypatch):
    """O defeito relatado, exatamente: o handle continua VÁLIDO, mas agora é de
    outro programa. Sem o pino do PID, a senha ia para lá."""
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 777)

    motivo = _entrada(0x1234, pid_da_janela=100)._motivo_para_nao_enviar()

    assert motivo is not None
    assert "RECICLOU" in motivo


def test_processo_que_nao_e_o_jogo_nao_envia(monkeypatch):
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 100)
    monkeypatch.setattr(inputs, "_nome_do_processo", lambda _p: "notepad.exe")
    monkeypatch.setattr(inputs, "SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO", 0.0)

    motivo = _entrada(0x1234, 100)._motivo_para_nao_enviar()

    assert motivo is not None
    assert "notepad.exe" in motivo


# ===========================================================================
# O QUE NÃO PODE SER BARRADO
# ===========================================================================

def test_a_janela_certa_envia(monkeypatch):
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 100)
    assert _entrada(0x1234, 100)._motivo_para_nao_enviar() is None


def test_NAO_SEI_o_nome_do_processo_NAO_bloqueia(monkeypatch):
    """Trocar um defeito raro (tecla na janela errada) por um permanente (bot
    mudo) seria o pior negócio possível.

    O pino do PID já segura o defeito relatado. Se o `psutil` levantar
    `AccessDenied` num momento ruim, a trava continua deixando passar.
    """
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 100)
    monkeypatch.setattr(inputs, "_nome_do_processo", lambda _p: None)
    monkeypatch.setattr(inputs, "SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO", 0.0)

    entrada = _entrada(0x1234, 100, nome_do_processo=None)

    assert entrada._motivo_para_nao_enviar() is None


def test_leitura_falhada_NAO_apaga_o_que_ja_se_sabia(monkeypatch):
    """Se o nome já era conhecido e a releitura falha, o conhecido continua."""
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 100)
    monkeypatch.setattr(inputs, "_nome_do_processo", lambda _p: None)
    monkeypatch.setattr(inputs, "SEGUNDOS_ENTRE_CONFERENCIAS_DO_PROCESSO", 0.0)

    entrada = _entrada(0x1234, 100, nome_do_processo="client.exe")
    entrada._motivo_para_nao_enviar()

    assert entrada._nome_do_processo == "client.exe"


# ===========================================================================
# A TRAVA ESTÁ NO FUNIL, E COBRE TUDO
# ===========================================================================

def test_nenhuma_tecla_sai_com_a_janela_errada(monkeypatch):
    """`key`, `type_text` e `clear_field` passam todas por `_enviar_tecla`."""
    enviados = []
    monkeypatch.setattr(inputs.user32, "PostMessageW",
                        lambda *a: enviados.append(a))
    monkeypatch.setattr(inputs.user32, "SendMessageW",
                        lambda *a: enviados.append(a))
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 777)

    entrada = _entrada(0x1234, pid_da_janela=100)
    entrada.key("A")
    entrada.type_text("senha")
    entrada.clear_field(presses=3)

    assert enviados == [], f"vazou {len(enviados)} mensagens"
    assert entrada.bloqueadas() > 0


def test_nenhum_clique_sai_com_a_janela_errada(monkeypatch):
    """Os oito caminhos de clique passam por `_click`, então a trava cobre os
    oito de uma vez."""
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 777)

    chamou = []
    for nome in ("_click_sendmessage", "_click_postmessage_puro",
                 "_click_sendmessage_rapido", "_click_trox_sequence"):
        monkeypatch.setattr(inputs.Input, nome,
                            lambda *a, **k: chamou.append(1))

    entrada = _entrada(0x1234, pid_da_janela=100)
    entrada.left_click(10, 10)
    entrada.right_click(10, 10)

    assert chamou == []


def test_o_titulo_tambem_e_conferido(monkeypatch):
    """Renomear a janela de outro programa é o mesmo defeito com outra roupa."""
    renomeadas = []
    monkeypatch.setattr(inputs.user32, "SetWindowTextW",
                        lambda *a: renomeadas.append(a))
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 777)

    _entrada(0x1234, pid_da_janela=100).set_title("BlazesBot")

    assert renomeadas == []


def test_a_janela_certa_deixa_a_tecla_passar(monkeypatch):
    """A trava não pode virar um bot mudo: com a janela certa, tudo sai."""
    enviados = []
    monkeypatch.setattr(inputs.user32, "PostMessageW",
                        lambda *a: enviados.append(a))
    monkeypatch.setattr(inputs.user32, "SendMessageW",
                        lambda *a: enviados.append(a))
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 100)

    entrada = _entrada(0x1234, pid_da_janela=100)
    entrada.type_text("abc", per_char=0.0)

    # Só os `WM_CHAR`: os três `WM_KEYUP` de SHIFT/CTRL/ALT que
    # `type_string_safely` manda antes entram na lista desde
    # 09/09/2026. Ver `test_injecao_de_texto_blindada.py`.
    chars = [a for a in enviados if a[1] == inputs.WM_CHAR]
    assert len(chars) == 3
    assert entrada.bloqueadas() == 0


# ===========================================================================
# NADA ESCAPA DO FUNIL
# ===========================================================================

def test_nenhum_modulo_manda_tecla_fora_do_Input():
    """Uma tecla enviada direto por outro módulo pularia a trava inteira.

    O `petbug.py` fica de fora de propósito: ele conversa com a janela do
    `BlazesBot - PetBug.exe`, que é programa nosso, e só manda `WM_GETTEXT` e
    `BM_CLICK` -- não é o jogo e não é teclado.
    """
    import ast
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "blazesbot"
    teclado = {"WM_KEYDOWN", "WM_KEYUP", "WM_CHAR", "WM_SYSKEYDOWN",
               "WM_SYSKEYUP"}
    culpados = []

    for caminho in raiz.rglob("*.py"):
        if caminho.name in ("inputs.py", "petbug.py"):
            continue
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func.attr if isinstance(no.func, ast.Attribute) else (
                no.func.id if isinstance(no.func, ast.Name) else "")
            if alvo not in ("PostMessageW", "PostMessage", "SendMessageW",
                            "SendMessage", "SendNotifyMessageW"):
                continue
            nomes = {n.id for a in no.args for n in ast.walk(a)
                     if isinstance(n, ast.Name)}
            nomes |= {n.attr for a in no.args for n in ast.walk(a)
                      if isinstance(n, ast.Attribute)}
            if nomes & teclado:
                culpados.append(f"{caminho.name}:{no.lineno}")

    assert not culpados, (
        "mensagem de TECLADO enviada fora do `Input`, pulando a trava da "
        "janela:\n  " + "\n  ".join(culpados))


def test_o_interruptor_da_trava_esta_LIGADO():
    assert inputs.CONFERIR_A_JANELA_ANTES_DE_ENVIAR is True


def test_com_a_trava_DESLIGADA_a_mensagem_sai(monkeypatch):
    """O caminho antigo continua existindo, e é ele que prova o que a trava
    segura: com ela desligada, a mesma janela errada recebe tudo."""
    enviados = []
    monkeypatch.setattr(inputs.user32, "PostMessageW",
                        lambda *a: enviados.append(a))
    monkeypatch.setattr(inputs.user32, "SendMessageW",
                        lambda *a: enviados.append(a))
    monkeypatch.setattr(inputs, "CONFERIR_A_JANELA_ANTES_DE_ENVIAR", False)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 777)

    _entrada(0x1234, pid_da_janela=100).type_text("abc", per_char=0.0)

    # OS TRÊS `WM_KEYUP` DOS MODIFICADORES entram na conta desde 09/09/2026:
    # `type_string_safely` solta SHIFT/CTRL/ALT uma vez antes de digitar, porque
    # modificador virtualmente preso troca a tecla que chega do outro lado -- um
    # SHIFT grudado transforma o login inteiro em maiúsculas. O que este teste
    # mede é o DESTINO, então ele conta só os `WM_CHAR`.
    chars = [a for a in enviados if a[1] == inputs.WM_CHAR]
    assert len(chars) == 3


@pytest.mark.parametrize("metodo", ["_enviar_tecla", "_click", "set_title"])
def test_todo_ponto_de_saida_confere_a_janela(metodo):
    """Ponto de saída novo sem `_janela_confiavel` é um vazamento novo."""
    import ast
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(getattr(inputs.Input, metodo)))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "_janela_confiavel" in chamadas, (
        f"`{metodo}` manda mensagem sem conferir a janela")


# ===========================================================================
# O PINO TARDIO -- a trava não pode virar um bot mudo
# ===========================================================================

def test_dono_desconhecido_no_nascimento_NAO_trava_para_sempre(monkeypatch):
    """No login a janela está NASCENDO, e pode não dizer de quem é ainda.

    Fixar `None` como pino e comparar contra ele deixaria o bot mudo para
    sempre -- trocar o defeito raro pelo permanente é o pior negócio possível.
    O pino se fecha na primeira leitura que der certo.
    """
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 100)
    monkeypatch.setattr(inputs, "_nome_do_processo", lambda _p: "client.exe")

    entrada = _entrada(0x1234, pid_da_janela=None, nome_do_processo=None)

    assert entrada._motivo_para_nao_enviar() is None
    assert entrada._pid_da_janela == 100, "o pino não fechou"
    assert entrada._nome_do_processo == "client.exe"


def test_o_pino_tardio_CONFERE_a_identidade_antes_de_fechar(monkeypatch):
    """Fechar o pino em qualquer processo que aparecesse seria fechar no Bloco
    de Notas -- a trava viraria decoração."""
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: 777)
    monkeypatch.setattr(inputs, "_nome_do_processo", lambda _p: "notepad.exe")

    entrada = _entrada(0x1234, pid_da_janela=None, nome_do_processo=None)
    motivo = entrada._motivo_para_nao_enviar()

    assert motivo is not None
    assert "notepad.exe" in motivo
    assert entrada._pid_da_janela is None, "fechou o pino num processo errado"


def test_dono_ilegivel_nao_envia(monkeypatch):
    """Sem saber de quem é a janela, não dá para provar que é a certa."""
    monkeypatch.setattr(inputs.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(inputs, "_dono_da_janela", lambda _h: None)

    motivo = _entrada(0x1234, pid_da_janela=100)._motivo_para_nao_enviar()

    assert motivo is not None
