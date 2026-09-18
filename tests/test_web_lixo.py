"""OS ITENS DO DELETADOR CHEGANDO NA TELA — 18/09/2026.

O que estes testes protegem:

    MINIATURA EMBUTIDA   -- o WebView2 recusa `<img src>` para arquivo local;
                            a imagem tem de ir como `data:` URI ou a grade
                            aparece vazia, sem erro nenhum
    O ESTADO É DA CONTA  -- a mesma pasta, duas contas, estados diferentes
    A LISTA ESCOLHE      -- "app" lê a pasta global, "hh" lê a da Black Wind
    ÓRFÃO NÃO SOME       -- nome guardado cujo PNG saiu da pasta continua
                            guardado, e é contado à parte
    GRAVAR SUBSTITUI     -- a janela manda o estado final dela; é o que faz
                            "desmarcar tudo" funcionar
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from blazesbot import web_lixo


@pytest.fixture
def conta(tmp_path, monkeypatch):
    """Uma conta de mentira e duas pastas de verdade em disco."""
    app, hh = tmp_path / "deletar", tmp_path / "deletar_hh"
    for pasta, nomes in ((app, ("Bag.png", "Blue_Wolf_Meat.png")),
                         (hh, ("Trap.png",))):
        pasta.mkdir()
        for nome in nomes:
            # Basta ter bytes: o que se testa aqui é a embalagem.
            (pasta / nome).write_bytes(b"png-de-mentira:" + nome.encode())
    monkeypatch.setitem(web_lixo.LISTAS, "app", (app, "app"))
    monkeypatch.setitem(web_lixo.LISTAS, "hh", (hh, "hh"))
    return SimpleNamespace(settings=SimpleNamespace(
        app=SimpleNamespace(desativados=[]),
        hh=SimpleNamespace(desativados=[])))


def test_a_miniatura_vai_EMBUTIDA(conta):
    """`file://` + WebView2 = `<img src>` para arquivo local não carrega."""
    itens = web_lixo.itens(conta, "app")["itens"]
    assert itens, "a grade veio vazia"
    for item in itens:
        assert item["imagem"].startswith("data:image/png;base64,"), item


def test_cada_item_leva_nome_de_arquivo_E_rotulo(conta):
    por_arquivo = {i["arquivo"]: i for i in web_lixo.itens(conta, "app")["itens"]}
    assert por_arquivo["Blue_Wolf_Meat.png"]["rotulo"] == "Blue Wolf Meat"
    assert por_arquivo["Bag.png"]["rotulo"] == "Bag"


def test_o_estado_vem_da_CONTA(conta):
    conta.settings.app.desativados = ["Bag.png"]
    estados = {i["arquivo"]: i["ativo"] for i in web_lixo.itens(conta, "app")["itens"]}
    assert estados == {"Bag.png": False, "Blue_Wolf_Meat.png": True}


def test_a_lista_escolhe_a_pasta_E_o_campo(conta):
    conta.settings.hh.desativados = ["Trap.png"]
    assert [i["arquivo"] for i in web_lixo.itens(conta, "hh")["itens"]] == ["Trap.png"]
    assert web_lixo.itens(conta, "hh")["itens"][0]["ativo"] is False
    # A da HH não contamina a do APP.
    assert all(i["ativo"] for i in web_lixo.itens(conta, "app")["itens"])


def test_orfao_continua_guardado_e_e_contado(conta):
    """O PNG sumiu; a escolha fica esperando ele voltar."""
    conta.settings.app.desativados = ["Bag.png", "SumiuDaPasta.png"]
    saida = web_lixo.itens(conta, "app")

    assert saida["orfaos"] == 1
    assert "SumiuDaPasta.png" in saida["desativados"]
    assert "SumiuDaPasta.png" not in [i["arquivo"] for i in saida["itens"]]


def test_lista_desconhecida_nao_levanta(conta):
    with pytest.raises(ValueError):
        web_lixo.itens(conta, "inventada")


def test_pasta_que_nao_existe_devolve_erro_legivel(conta, tmp_path, monkeypatch):
    monkeypatch.setitem(web_lixo.LISTAS, "app", (tmp_path / "nao_existe", "app"))
    saida = web_lixo.itens(conta, "app")
    assert saida["ok"] is False and saida["itens"] == []


def test_gravar_SUBSTITUI_e_normaliza(conta):
    conta.settings.app.desativados = ["Velho.png"]
    web_lixo.guardar(conta, "app", ["Bag.png", "", "Bag.png", "  Outro.png  "])
    assert conta.settings.app.desativados == ["Bag.png", "Outro.png"]


def test_gravar_lista_vazia_reativa_tudo(conta):
    """"Desmarcar todos" precisa chegar como lista vazia e valer."""
    conta.settings.app.desativados = ["Bag.png"]
    web_lixo.guardar(conta, "app", [])
    assert conta.settings.app.desativados == []
    assert all(i["ativo"] for i in web_lixo.itens(conta, "app")["itens"])
