"""O `_release` apaga a lição por hwnd da janela que morreu.

O Windows RECICLA hwnd: uma janela nova que receba o número de uma morta não
pode herdar dela o "o leitor de arredores não responde aqui"
(`ui_do_jogo._BUSCAS_SEM_LEITURA`), senão nasce com a conferência da busca
desligada sem ter medido nada.

Achado C8 da auditoria de 27/09/2026: o `_release` importava `esquecer_janela`
de `bc/ui_service`, que deixou de ter a função quando a UI do jogo subiu para
`bot/` (cd2ef2b, 02/09). O `except Exception: pass` engolia o ImportError, e a
limpeza não rodou em nenhuma morte de janela desde então.
"""
from types import SimpleNamespace

from blazesbot.bot import ui_do_jogo
from blazesbot.bot.supervisor import AccountSupervisor


def test_o_release_esquece_a_licao_da_janela_que_morreu():
    hwnd = 0x7FFF0C08  # número de teste: nenhuma janela real é tocada
    ui_do_jogo._BUSCAS_SEM_LEITURA[hwnd] = 3
    sup = AccountSupervisor.__new__(AccountSupervisor)
    sup.pid = None
    sup.hwnd = hwnd
    sup.account = SimpleNamespace(login="conta-do-teste")
    try:
        sup._release()
        assert hwnd not in ui_do_jogo._BUSCAS_SEM_LEITURA
    finally:
        ui_do_jogo._BUSCAS_SEM_LEITURA.pop(hwnd, None)
