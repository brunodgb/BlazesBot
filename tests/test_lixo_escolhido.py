"""O QUE CADA CONTA APAGA -- a inversão de 19/09/2026.

Antes a pasta era a lista e a conta guardava as EXCEÇÕES: tudo era apagado
menos o que o usuário marcasse. Agora é o contrário -- **a conta escolhe, e
vazio não apaga nada**.

O QUE MOTIVOU, medido: comparar os 213 modelos custa 1,68 s por limpeza; vinte
custam 147 ms. Cada rota dropa coisas diferentes, então varrer a lista inteira
é pagar por 190 comparações que nunca vão casar.

O que estes testes protegem:

    VAZIO NÃO APAGA NADA      -- é o padrão, e o lado seguro de uma inversão
    SÓ O ESCOLHIDO É CARREGADO -- é daí que vem o ganho de tempo
    A PASTA ESCOLHE O CAMPO   -- `deletar/` lê o APP, `deletar_hh/` lê a HH
    A LEITURA É AGORA         -- a janela vale na limpeza seguinte, sem religar
    SEM ESCOLHA, SEM TECLA    -- não se abre a bolsa para não fazer nada
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


def _ctx(app_apagaveis=(), hh_apagaveis=()):
    """Só o que o filtro toca: a configuração viva da conta."""
    return SimpleNamespace(
        settings=SimpleNamespace(
            app=SimpleNamespace(apagaveis=list(app_apagaveis)),
            hh=SimpleNamespace(apagaveis=list(hh_apagaveis))))


def _nomes(caminhos):
    return sorted(p.name for p in caminhos)


def test_sem_escolha_NAO_APAGA_NADA(pastas):
    """O padrão depois da inversão, e o lado seguro dela: conta que nunca abriu
    a janela não apaga item nenhum. Apagar não tem desfazer."""
    app, _hh = pastas
    assert d.modelos_ativos(_ctx(), app) == []


def test_SO_o_escolhido_entra(pastas):
    """É daqui que vem o ganho: a varredura compara vinte, não duzentos."""
    app, _hh = pastas
    ativos = d.modelos_ativos(_ctx(app_apagaveis=["Bag.png"]), app)
    assert _nomes(ativos) == ["Bag.png"]


def test_a_pasta_ESCOLHE_o_campo(pastas):
    """`deletar_hh/` não pode ler a lista do APP -- o que é lixo numa cave é
    mercadoria na outra, e a exclusão é irreversível."""
    app, hh = pastas
    ctx = _ctx(app_apagaveis=["Bag.png"], hh_apagaveis=["Trap.png"])

    assert _nomes(d.modelos_ativos(ctx, app)) == ["Bag.png"]
    assert _nomes(d.modelos_ativos(ctx, hh)) == ["Trap.png"]


def test_a_leitura_e_AGORA_e_nao_na_montagem(pastas):
    """O ganho inteiro da janela: salvar vale na limpeza seguinte.

    A interface e a thread da conta compartilham o MESMO objeto de
    configuração. Se alguém guardar esta lista numa variável na montagem do
    executor, a janela passa a só valer no religar -- que é exatamente o que
    acontece com `travar_posicao` e `shuffle_apos_n_voltas`.
    """
    app, _hh = pastas
    ctx = _ctx()
    assert d.modelos_ativos(ctx, app) == []

    ctx.settings.app.apagaveis.append("Bag.png")      # a janela salvou AGORA

    assert _nomes(d.modelos_ativos(ctx, app)) == ["Bag.png"]


def test_nome_que_nao_existe_na_pasta_nao_atrapalha(pastas):
    """Escolha importada de outra máquina pode citar PNG que aqui não existe."""
    app, _hh = pastas
    ctx = _ctx(app_apagaveis=["SoNoPcDoAmigo.png", "Bag.png"])
    assert _nomes(d.modelos_ativos(ctx, app)) == ["Bag.png"]


@pytest.mark.parametrize("sujeira", [None, "", "   ", 7])
def test_lista_suja_nao_derruba_a_limpeza(pastas, sujeira):
    """O `config.json` é editável à mão. Nome sujo vira item que não casa com
    arquivo nenhum -- nunca uma exceção no meio da macro."""
    app, _hh = pastas
    ctx = _ctx(app_apagaveis=[sujeira, "Bag.png"])
    assert _nomes(d.modelos_ativos(ctx, app)) == ["Bag.png"]


def test_QUEM_CARREGA_respeita_a_escolha(pastas):
    """`_carregar` é a porta única: por ela passam o que APAGA e o que CONFERE.

    Se a aferição carregasse por outro caminho, ela desenharia um retângulo
    vermelho em cima de um item que a conta não apaga -- e o usuário
    preservaria o item errado por causa do desenho.
    """
    app, _hh = pastas
    ctx = _ctx(app_apagaveis=["Bag.png"])
    ctx.templates = SimpleNamespace(load_color=lambda chave: object())

    assert sorted(d._carregar(ctx, app)) == ["Bag"]


# ---------------------------------------------------------------------------
# O ATALHO -- não se abre a bolsa para não fazer nada
# ---------------------------------------------------------------------------

class _CtxDaTecla:
    """Registra tecla e captura: o teste é sobre NENHUMA das duas acontecer."""

    def __init__(self, apagaveis=()):
        self.teclas: list[str] = []
        self.capturas = 0
        self.settings = SimpleNamespace(
            app=SimpleNamespace(apagaveis=list(apagaveis)),
            hh=SimpleNamespace(apagaveis=[]))
        self.hwnd = 1
        self.log = SimpleNamespace(debug=lambda *a, **k: None,
                                   info=lambda *a, **k: None,
                                   warning=lambda *a, **k: None)

    def press(self, tecla):
        self.teclas.append(tecla)

    def tick(self, s=0.2):
        pass


def test_sem_escolha_a_limpeza_NAO_TOCA_NA_TECLA(monkeypatch):
    """Conta recém-configurada nasce com a seleção vazia -- é o estado NORMAL.

    Abrir a bolsa para não apagar nada custa o personagem parado com o
    inventário na frente, e a tecla é INTERRUPTOR: numa bolsa que o usuário
    deixou aberta, ela FECHA. Sem escolha, o certo é não chegar nem a olhar.
    """
    ctx = _CtxDaTecla(apagaveis=[])
    monkeypatch.setattr(d, "inventario_esta_aberto",
                        lambda c: pytest.fail("olhou a tela sem precisar"))

    assert d.limpar_a_bolsa(ctx, "I") == 0
    assert ctx.teclas == [], "apertou a tecla do inventário à toa"


def test_COM_escolha_a_limpeza_segue_o_caminho_normal(monkeypatch):
    """A contraprova: com um item escolhido, ela volta a olhar a tela."""
    ctx = _CtxDaTecla(apagaveis=["Bag.png"])
    olhou = []
    monkeypatch.setattr(d, "inventario_esta_aberto",
                        lambda c: olhou.append(1) or True)
    monkeypatch.setattr(
        d, "deletar_lixo",
        lambda c, teto=None, pasta=None, continuar=None: 3)

    assert d.limpar_a_bolsa(ctx, "I") == 3
    assert olhou, "não chegou a olhar a tela"
