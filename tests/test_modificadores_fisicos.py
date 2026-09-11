"""O WM_KEYUP dos modificadores tem de ser BEM FORMADO, senão o cliente descarta.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR -- 11/09/2026
=========================================================================

Sintoma relatado: com o jogo em SEGUNDO PLANO e o usuário segurando SHIFT no
navegador, o cliente passava a ler "SHIFT + tecla do bot". O comando virava
outro e a skill não saía.

`_liberar_modificadores_fisicos` já existia e já mandava o KEYUP. Ela não
funcionava porque `_enviar_tecla` chumbava `LPARAM(0)`, e **um WM_KEYUP com
lParam zerado é malformado**: afirma que a tecla NÃO estava pressionada (bit 30
= 0) e que NÃO está havendo transição para solta (bit 31 = 0). O cliente lê um
registro que se contradiz e ignora a mensagem.

O que se trava aqui é o registro de bits inteiro -- ele não é um número mágico,
é um formato do Windows, e cada campo tem uma razão.

=========================================================================
O QUE ESTES TESTES NÃO PROVAM
=========================================================================

Que o vazamento acabou. Um KEYUP na fila conserta o estado de teclado POR
THREAD (`GetKeyState`); `GetAsyncKeyState` e RawInput leem o hardware e nenhuma
mensagem sintética os toca. Se o cliente ler o estado assíncrono, o vazamento
continua -- e a saída não é por mensagem.
"""
from __future__ import annotations

import win32api

from blazesbot.core import inputs as mod
from blazesbot.core.inputs import Input

# Os bits que fazem a mensagem ser aceita. Nomeados porque `1 << 30` no meio de
# uma asserção não diz nada a quem lê depois.
BIT_ESTADO_ANTERIOR = 30      # a tecla ESTAVA apertada
BIT_TRANSICAO = 31            # e está sendo SOLTA agora


def _entrada() -> Input:
    """Um `Input` sem `__init__`, com a trava de janela já satisfeita."""
    inp = object.__new__(Input)
    inp.hwnd = 0x1234
    inp._pid_da_janela = 100
    inp._nome_do_processo = "client.exe"
    inp._conferido_em = 1e18          # não reconfere o processo durante o teste
    inp._bloqueadas = 0
    inp._motivo_do_bloqueio = None
    inp._teclas_presas = {}
    inp._presas_para_sempre = set()
    return inp


def _capturar(monkeypatch) -> list[tuple[int, int, int]]:
    """Troca o funil por um gravador: `(mensagem, wparam, lparam)`."""
    enviadas: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        Input, "_enviar_tecla",
        lambda self, m, wp, lp=0: enviadas.append((m, wp, lp)))
    return enviadas


# ===========================================================================
# EIXO 2 -- a matemática do lParam
# ===========================================================================


def test_o_keyup_do_modificador_tem_os_bits_30_e_31_ligados(monkeypatch):
    """São ELES que fazem a mensagem ser aceita. Com zero, o cliente descarta."""
    enviadas = _capturar(monkeypatch)
    _entrada()._liberar_modificadores_fisicos()

    assert len(enviadas) == 3
    for mensagem, _vk, lparam in enviadas:
        assert mensagem == mod.WM_KEYUP
        assert (lparam >> BIT_ESTADO_ANTERIOR) & 1 == 1, (
            "bit 30 zerado: a mensagem afirma que a tecla não estava apertada")
        assert (lparam >> BIT_TRANSICAO) & 1 == 1, (
            "bit 31 zerado: a mensagem afirma que não há transição para solta")


def test_o_scan_code_e_o_REAL_do_teclado_e_nao_um_numero_fixo(monkeypatch):
    """O VK é lógico e igual em toda máquina; o scan code é físico e muda com o
    layout. Mandar o scan errado é mandar OUTRA tecla."""
    enviadas = _capturar(monkeypatch)
    _entrada()._liberar_modificadores_fisicos()

    for _msg, vk, lparam in enviadas:
        esperado = win32api.MapVirtualKey(vk, 0)
        assert (lparam >> 16) & 0xFF == esperado, (
            f"scan code errado para o vk 0x{vk:02X}")


def test_a_contagem_de_repeticao_e_um(monkeypatch):
    """Bits 0-15. Zero descreve "nenhuma repetição", que num KEYUP real não
    acontece."""
    enviadas = _capturar(monkeypatch)
    _entrada()._liberar_modificadores_fisicos()
    for _msg, _vk, lparam in enviadas:
        assert lparam & 0xFFFF == 1


def test_o_lparam_inteiro_bate_com_a_formula(monkeypatch):
    """O registro completo, e não só os bits que importam isoladamente."""
    enviadas = _capturar(monkeypatch)
    _entrada()._liberar_modificadores_fisicos()

    for _msg, vk, lparam in enviadas:
        scan = win32api.MapVirtualKey(vk, 0)
        assert lparam == 1 | (scan << 16) | (1 << 30) | (1 << 31)


def test_sao_os_TRES_modificadores_e_nessa_ordem(monkeypatch):
    enviadas = _capturar(monkeypatch)
    _entrada()._liberar_modificadores_fisicos()
    vks = [vk for _m, vk, _lp in enviadas]
    assert vks == [mod.VK_CODES["SHIFT"], mod.VK_CODES["CTRL"],
                   mod.VK_CODES["ALT"]]


# ===========================================================================
# EIXO 1 -- a assinatura, e o que ela NÃO pode ter mudado
# ===========================================================================


def test_o_lparam_e_opcional_e_o_padrao_continua_ZERO():
    """Só o KEYUP precisa do registro montado.

    Trocar o padrão obrigaria as dezenas de chamadas de KEYDOWN e WM_CHAR a
    montar um `lParam` que elas não precisam -- e o cliente aceita as duas com
    zero. Quem precisa, passa.
    """
    import inspect

    params = inspect.signature(Input._enviar_tecla).parameters
    assert list(params) == ["self", "mensagem", "wparam", "lparam"]
    assert params["lparam"].default == 0


def test_o_keydown_continua_saindo_com_lparam_zero(monkeypatch):
    """A alteração é cirúrgica: só o KEYUP dos modificadores mudou."""
    enviadas = _capturar(monkeypatch)
    entrada = _entrada()
    entrada.key_down("1")

    keydowns = [(vk, lp) for m, vk, lp in enviadas if m == mod.WM_KEYDOWN]
    assert keydowns, "o KEYDOWN não saiu"
    assert all(lp == 0 for _vk, lp in keydowns)


def test_o_lparam_chega_INTEIRO_na_chamada_do_Windows(monkeypatch):
    """O funil é o único ponto de saída -- se ele descartar o `lparam`, toda a
    matemática acima vira enfeite."""
    saidas = []
    monkeypatch.setattr(mod.user32, "PostMessageW",
                        lambda *a: saidas.append(a))
    monkeypatch.setattr(mod.user32, "SendMessageW",
                        lambda *a: saidas.append(a))
    monkeypatch.setattr(mod.user32, "IsWindow", lambda _h: 1)
    monkeypatch.setattr(mod, "_dono_da_janela", lambda _h: 100)

    _entrada()._enviar_tecla(mod.WM_KEYUP, 0x10, 0xC02A0001)

    assert len(saidas) == 1
    assert saidas[0][3].value == 0xC02A0001, (
        "o `lparam` foi descartado no caminho para o Windows")


# ===========================================================================
# EIXO 3 -- a contenção: nada de mouse foi tocado
# ===========================================================================


def test_o_hotfix_NAO_encostou_no_mouse():
    """Regra de ferro do pedido, e ela vale como teste: o clique tem histórico
    próprio de experimentos reprovados (ver o cabeçalho de `inputs.py`)."""
    import inspect

    for nome in ("_click", "_prime_cursor", "left_click", "right_click"):
        fonte = inspect.getsource(getattr(Input, nome))
        assert "MapVirtualKey" not in fonte
        assert "lparam_up" not in fonte

    # `_lparam(x, y)` empacota COORDENADA, não estado de tecla. Um não tem nada
    # a ver com o outro, e confundi-los manda o clique para outro lugar.
    assert "MapVirtualKey" not in inspect.getsource(mod._lparam)
