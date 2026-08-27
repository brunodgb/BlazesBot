"""O canal de log da interface web não pode reenviar o histórico inteiro.

=========================================================================
A CAUSA MEDIDA DO CONGELAMENTO DA INTERFACE
=========================================================================

Sintoma relatado: o bot continua rodando -- as rotinas de background seguem
farmando -- e só a INTERFACE trava, depois de muito tempo de execução.

A causa: `Api.puxar_log` comparava um cursor ABSOLUTO (`_total`, que só cresce)
com `len(self._historico)`, uma `deque` com `maxlen=MAX_LINHAS_GUARDADAS`:

    corte = desde_i if 0 <= desde_i <= len(self._historico) else 0

Enquanto o total era menor que o teto os dois coincidiam. Na linha
`MAX_LINHAS_GUARDADAS + 1` isso quebra PARA SEMPRE: `desde_i` continua subindo,
`len(_historico)` fica preso no teto, a condição é sempre falsa e `corte` vira 0
-- o histórico INTEIRO volta em cada poll de 300 ms, indefinidamente.

Por que isso mata a janela e não o bot: todo retorno de método `js_api` do
pywebview é embutido num literal JS e executado por `evaluate_js`, que chama
`webview.Invoke(...)`. São ~2 MB de script na THREAD DE UI do WebView2, 3,3
vezes por segundo. As threads do bot não passam por esse canal.

O agravante: o backoff do frontend nunca liga, porque com linhas voltando sempre
ele conclui que há novidade sempre.
"""
from __future__ import annotations

import pytest

from blazesbot import web_app


@pytest.fixture
def api(monkeypatch):
    """Uma `Api` sem tocar em config, bot nem janela."""
    app = web_app._App.__new__(web_app._App)
    from collections import deque
    app._fila_log = deque(maxlen=40000)
    app._historico = deque(maxlen=web_app.MAX_LINHAS_GUARDADAS)
    app._contagem_por_conta = {}
    app._total = 0
    objeto = web_app.Api.__new__(web_app.Api)
    # `puxar_log` vive na Api ou no _App dependendo da versão; devolve o que
    # tiver o método, para o teste não depender dessa escolha.
    return app if hasattr(app, "puxar_log") else objeto


def _encher(app, quantas: int) -> None:
    """Numera as linhas CONTINUAMENTE entre chamadas.

    Reiniciar em 0 a cada chamada faria "linha 0" aparecer várias vezes e os
    testes de conteúdo mentiriam sobre qual linha voltou.

    O contador vive NO OBJETO, não num dicionário por `id()`: o CPython
    reaproveita ids de objetos coletados, então um dicionário global fazia o
    estado vazar entre testes -- passavam isolados e falhavam na suíte.
    """
    inicio = getattr(app, "_proxima_linha_do_teste", 0)
    for i in range(inicio, inicio + quantas):
        app._fila_log.append(("creubo", f"linha {i}"))
    app._proxima_linha_do_teste = inicio + quantas


def test_poll_ocioso_nao_devolve_nada(api):
    _encher(api, 10)
    r = api.puxar_log(0)
    assert len(r["linhas"]) == 10
    assert api.puxar_log(r["total"])["linhas"] == []


def test_devolve_SO_as_novas_antes_do_teto(api):
    _encher(api, 100)
    cursor = api.puxar_log(0)["total"]
    _encher(api, 5)
    r = api.puxar_log(cursor)
    assert len(r["linhas"]) == 5
    assert r["linhas"][0]["linha"] == "linha 100"


def test_PASSADO_O_TETO_continua_devolvendo_so_as_novas(api):
    """O defeito. Antes daqui a interface recebia o histórico inteiro por poll.

    É o teste que separa "funciona por algumas horas" de "funciona por dias".
    """
    teto = web_app.MAX_LINHAS_GUARDADAS
    _encher(api, teto + 500)
    cursor = api.puxar_log(0)["total"]
    assert cursor == teto + 500

    _encher(api, 7)
    r = api.puxar_log(cursor)
    assert len(r["linhas"]) == 7, (
        f"recebeu {len(r['linhas'])} linhas em vez de 7 — o histórico inteiro "
        f"está sendo reenviado, e é isso que congela a janela")
    assert r["linhas"][0]["linha"] == f"linha {teto + 500}"


def test_o_poll_ocioso_DEPOIS_do_teto_tambem_devolve_vazio(api):
    """O caso que roda 3,3 vezes por segundo a noite inteira.

    Um poll ocioso que devolvesse o histórico seria o mesmo defeito com outro
    nome: o custo não depende de haver linha nova, depende do que atravessa a
    ponte.
    """
    _encher(api, web_app.MAX_LINHAS_GUARDADAS + 1000)
    cursor = api.puxar_log(0)["total"]
    for _ in range(5):
        assert api.puxar_log(cursor)["linhas"] == []


def test_frontend_ATRASADO_recebe_a_janela_e_nao_o_impossivel(api):
    """Cursor mais antigo que o descarte: aquelas linhas não existem mais.

    O certo é entregar a janela que ainda existe -- não `0` linhas (o frontend
    ficaria em branco para sempre) nem estourar índice.
    """
    _encher(api, web_app.MAX_LINHAS_GUARDADAS + 2000)
    r = api.puxar_log(5)          # pediu de uma linha já descartada
    assert len(r["linhas"]) == web_app.MAX_LINHAS_GUARDADAS
    assert r["total"] == web_app.MAX_LINHAS_GUARDADAS + 2000


def test_cursor_a_FRENTE_do_total_nao_estoura(api):
    """Total zerado por `limpar_log` em outra aba, cursor antigo no frontend."""
    _encher(api, 50)
    api.puxar_log(0)
    assert api.puxar_log(999999)["linhas"] == []


def test_o_custo_por_poll_e_LIMITADO(api):
    """A garantia que interessa para 24 h de execução.

    Não importa quanto o bot logou: um poll devolve no máximo as linhas novas.
    Sem isto, o volume por poll cresce até o teto e fica lá.
    """
    _encher(api, web_app.MAX_LINHAS_GUARDADAS * 2)
    cursor = api.puxar_log(0)["total"]
    maior = 0
    for _ in range(20):
        _encher(api, 3)
        maior = max(maior, len(api.puxar_log(cursor)["linhas"]))
        cursor = api._total
    assert maior <= 3, (
        f"um poll devolveu {maior} linhas para 3 novas — o canal voltou a "
        f"reenviar histórico")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
