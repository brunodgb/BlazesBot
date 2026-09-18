"""OS ITENS QUE CADA CONTA NÃO APAGA -- 18/09/2026.

A pasta `data/templates/deletar/` continua dizendo o que PODE ser apagado, e é
uma só para o bot inteiro. A CONTA guarda as exceções dela.

O que estes testes protegem:

    A EXCEÇÃO, E NÃO A LISTA  -- PNG novo na pasta vale em todas as contas sem
                                ninguém ligar nada (o invariante "PNG autoriza")
    A PASTA ESCOLHE O CAMPO   -- `deletar/` lê o APP, `deletar_hh/` lê a HH
    A LEITURA É AGORA         -- mexer na janela vale na limpeza seguinte, sem
                                religar o bot; capturar o valor na montagem é o
                                erro que `travar_posicao` comete
    A AFERIÇÃO VÊ O MESMO     -- quem confere e quem apaga carregam pela mesma
                                porta, senão a conferência mente
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from blazesbot.bot import deletador as d


@pytest.fixture
def pastas(tmp_path):
    """Duas pastas com o NOME de verdade -- é o nome que escolhe o campo."""
    app, hh = tmp_path / "deletar", tmp_path / "deletar_hh"
    for pasta, nomes in ((app, ("Bag.png", "Zinc_Ore.png", "AlmOre.png")),
                         (hh, ("Trap.png", "Silk.png"))):
        pasta.mkdir()
        for nome in nomes:
            (pasta / nome).write_bytes(b"")
    return app, hh


def _ctx(app_desativados=(), hh_desativados=()):
    """Só o que o filtro toca: a configuração viva da conta."""
    return SimpleNamespace(
        settings=SimpleNamespace(
            app=SimpleNamespace(desativados=list(app_desativados)),
            hh=SimpleNamespace(desativados=list(hh_desativados))))


def _nomes(caminhos):
    return sorted(p.name for p in caminhos)


def test_sem_desativados_a_lista_e_a_pasta_INTEIRA(pastas):
    """O padrão não muda nada: conta que nunca abriu a janela apaga tudo."""
    app, _hh = pastas
    assert _nomes(d.modelos_ativos(_ctx(), app)) == [
        "AlmOre.png", "Bag.png", "Zinc_Ore.png"]


def test_o_desativado_SAI_da_lista(pastas):
    app, _hh = pastas
    ativos = d.modelos_ativos(_ctx(app_desativados=["Bag.png"]), app)
    assert _nomes(ativos) == ["AlmOre.png", "Zinc_Ore.png"]


def test_a_pasta_ESCOLHE_o_campo(pastas):
    """`deletar_hh/` não pode ler a lista do APP -- o que é lixo numa cave é
    mercadoria na outra, e a exclusão é irreversível."""
    app, hh = pastas
    ctx = _ctx(app_desativados=["Bag.png"], hh_desativados=["Trap.png"])

    assert _nomes(d.modelos_ativos(ctx, app)) == ["AlmOre.png", "Zinc_Ore.png"]
    assert _nomes(d.modelos_ativos(ctx, hh)) == ["Silk.png"]


def test_a_leitura_e_AGORA_e_nao_na_montagem(pastas):
    """O ganho inteiro da feature: salvar na janela vale na limpeza seguinte.

    A interface e a thread da conta compartilham o MESMO objeto de
    configuração. Se alguém guardar esta lista numa variável na montagem do
    executor, a janela passa a só valer no religar -- que é exatamente o que
    acontece com `travar_posicao` e `shuffle_apos_n_voltas`.
    """
    app, _hh = pastas
    ctx = _ctx()
    assert len(d.modelos_ativos(ctx, app)) == 3

    ctx.settings.app.desativados.append("Bag.png")      # a janela salvou AGORA

    assert _nomes(d.modelos_ativos(ctx, app)) == ["AlmOre.png", "Zinc_Ore.png"]


def test_nome_que_nao_existe_mais_na_pasta_nao_atrapalha(pastas):
    """O PNG some, a escolha fica guardada esperando ele voltar."""
    app, _hh = pastas
    ctx = _ctx(app_desativados=["ItemQueSumiu.png", "Bag.png"])
    assert _nomes(d.modelos_ativos(ctx, app)) == ["AlmOre.png", "Zinc_Ore.png"]


@pytest.mark.parametrize("sujeira", [None, "", "   ", 7, ["Bag.png"]])
def test_lista_suja_nao_derruba_a_limpeza(pastas, sujeira):
    """O `config.json` é editável à mão. Nome sujo vira item que não casa com
    arquivo nenhum -- nunca uma exceção no meio da macro."""
    app, _hh = pastas
    ctx = _ctx(app_desativados=[sujeira])
    assert len(d.modelos_ativos(ctx, app)) >= 2


def test_QUEM_CARREGA_respeita_a_lista(pastas, monkeypatch):
    """`_carregar` é a porta única: por ela passam o que APAGA e o que CONFERE.

    Se a aferição carregasse por outro caminho, ela desenharia um retângulo
    vermelho em cima de um item que a conta não apaga -- e o usuário
    preservaria o item errado por causa do desenho.
    """
    app, _hh = pastas
    ctx = _ctx(app_desativados=["Bag.png"])
    ctx.templates = SimpleNamespace(load_color=lambda chave: object())

    carregados = d._carregar(ctx, app)

    assert sorted(carregados) == ["AlmOre", "Zinc_Ore"], carregados
