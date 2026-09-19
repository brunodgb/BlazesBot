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

import json
from types import SimpleNamespace

import pytest

from blazesbot import web_lixo


@pytest.fixture
def conta(tmp_path, monkeypatch):
    """Uma conta de mentira e duas pastas de verdade em disco."""
    # NOMES QUE O DICIONÁRIO NUNCA TERÁ. `rotulo()` consulta `nomes_do_lixo`,
    # que é uma tabela do USUÁRIO: usar `Bag.png` aqui amarrava o teste ao
    # rótulo que ele escreve à mão, e quebrou duas vezes quando ele renomeou um
    # PNG. Com o prefixo `Zz` o rótulo vem sempre de `humanizar`.
    app, hh = tmp_path / "deletar", tmp_path / "deletar_hh"
    for pasta, nomes in ((app, ("Zz_Bolsa.png", "Zz_Carne_de_Lobo.png")),
                         (hh, ("Zz_Armadilha.png",))):
        pasta.mkdir()
        for nome in nomes:
            # Basta ter bytes: o que se testa aqui é a embalagem.
            (pasta / nome).write_bytes(b"png-de-mentira:" + nome.encode())
    monkeypatch.setitem(web_lixo.LISTAS, "app", (app, "app"))
    monkeypatch.setitem(web_lixo.LISTAS, "hh", (hh, "hh"))
    return SimpleNamespace(
        # `last_char_name`/`login` entram no arquivo exportado: quem recebe a
        # seleção de um amigo merece saber de qual personagem ela veio.
        last_char_name="BlazesAPP1", login="conta-de-teste",
        settings=SimpleNamespace(
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
    assert por_arquivo["Zz_Carne_de_Lobo.png"]["rotulo"] == "Zz Carne de Lobo"
    assert por_arquivo["Zz_Bolsa.png"]["rotulo"] == "Zz Bolsa"


def test_o_estado_vem_da_CONTA(conta):
    conta.settings.app.desativados = ["Zz_Bolsa.png"]
    estados = {i["arquivo"]: i["ativo"] for i in web_lixo.itens(conta, "app")["itens"]}
    assert estados == {"Zz_Bolsa.png": False, "Zz_Carne_de_Lobo.png": True}


def test_a_lista_escolhe_a_pasta_E_o_campo(conta):
    conta.settings.hh.desativados = ["Zz_Armadilha.png"]
    assert [i["arquivo"] for i in web_lixo.itens(conta, "hh")["itens"]] == ["Zz_Armadilha.png"]
    assert web_lixo.itens(conta, "hh")["itens"][0]["ativo"] is False
    # A da HH não contamina a do APP.
    assert all(i["ativo"] for i in web_lixo.itens(conta, "app")["itens"])


def test_orfao_continua_guardado_e_e_contado(conta):
    """O PNG sumiu; a escolha fica esperando ele voltar."""
    conta.settings.app.desativados = ["Zz_Bolsa.png", "SumiuDaPasta.png"]
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
    web_lixo.guardar(conta, "app", ["Zz_Bolsa.png", "", "Zz_Bolsa.png", "  Outro.png  "])
    # `normalizar_desativados` ordena: o diff do config.json fica estável.
    assert conta.settings.app.desativados == ["Outro.png", "Zz_Bolsa.png"]


def test_gravar_lista_vazia_reativa_tudo(conta):
    """"Desmarcar todos" precisa chegar como lista vazia e valer."""
    conta.settings.app.desativados = ["Zz_Bolsa.png"]
    web_lixo.guardar(conta, "app", [])
    assert conta.settings.app.desativados == []
    assert all(i["ativo"] for i in web_lixo.itens(conta, "app")["itens"])


# ===========================================================================
# LEVAR A SELEÇÃO PARA OUTRA CONTA — ou para outra máquina
# ===========================================================================

def _dialogo_fixo(monkeypatch, caminho):
    monkeypatch.setattr(web_lixo, "_dialogo", lambda salvar, sugestao="": str(caminho))


def test_exportar_grava_o_arquivo_com_a_LISTA_dentro(conta, tmp_path, monkeypatch):
    """Sem dizer de qual lista é, importar um arquivo do APP na janela da HH
    passaria despercebido: os nomes não casariam com nada e a pessoa ficaria
    com a seleção vazia achando que importou."""
    alvo = tmp_path / "selecao.json"
    _dialogo_fixo(monkeypatch, alvo)

    r = web_lixo.exportar(conta, "app", ["Zz_Bolsa.png", "Zz_Bolsa.png", ""])

    assert r["ok"] and r["quantos"] == 1
    gravado = json.loads(alvo.read_text(encoding="utf-8"))
    assert gravado["blazesbot"] == web_lixo.MARCA_DO_ARQUIVO
    assert gravado["lista"] == "app"
    assert gravado["desativados"] == ["Zz_Bolsa.png"]


def test_exportar_leva_o_que_esta_na_TELA(conta, tmp_path, monkeypatch):
    """A conta tem uma coisa guardada e a janela mostra outra: vai a da janela,
    que é o que a pessoa está vendo."""
    conta.settings.app.desativados = ["Zz_Carne_de_Lobo.png"]
    alvo = tmp_path / "selecao.json"
    _dialogo_fixo(monkeypatch, alvo)

    web_lixo.exportar(conta, "app", ["Zz_Bolsa.png"])

    assert json.loads(alvo.read_text(encoding="utf-8"))["desativados"] == ["Zz_Bolsa.png"]


def test_importar_devolve_a_selecao_e_NAO_grava(conta, tmp_path, monkeypatch):
    """Quem aplica é a janela, no estado em edição -- por isso o Cancelar dela
    ainda desfaz uma importação."""
    alvo = tmp_path / "selecao.json"
    alvo.write_text(json.dumps({
        "blazesbot": web_lixo.MARCA_DO_ARQUIVO, "versao": 1, "lista": "app",
        "desativados": ["Zz_Bolsa.png"]}), encoding="utf-8")
    _dialogo_fixo(monkeypatch, alvo)

    r = web_lixo.importar(conta, "app")

    assert r["ok"] and r["desativados"] == ["Zz_Bolsa.png"]
    assert conta.settings.app.desativados == [], "importar gravou sozinho"


def test_importar_RECUSA_arquivo_da_outra_lista(conta, tmp_path, monkeypatch):
    alvo = tmp_path / "selecao.json"
    alvo.write_text(json.dumps({
        "blazesbot": web_lixo.MARCA_DO_ARQUIVO, "lista": "hh",
        "desativados": ["Zz_Armadilha.png"]}), encoding="utf-8")
    _dialogo_fixo(monkeypatch, alvo)

    r = web_lixo.importar(conta, "app")

    assert r["ok"] is False and "hh" in r["erro"]


def test_importar_RECUSA_json_que_nao_e_do_bot(conta, tmp_path, monkeypatch):
    alvo = tmp_path / "qualquer.json"
    alvo.write_text('{"algo": 1}', encoding="utf-8")
    _dialogo_fixo(monkeypatch, alvo)

    assert web_lixo.importar(conta, "app")["ok"] is False


def test_importar_CONTA_os_nomes_que_nao_existem_aqui(conta, tmp_path, monkeypatch):
    """O arquivo do amigo pode ter PNG que esta instalação não tem. Os nomes
    são mantidos -- o PNG pode voltar --, mas a pessoa merece saber."""
    alvo = tmp_path / "selecao.json"
    alvo.write_text(json.dumps({
        "blazesbot": web_lixo.MARCA_DO_ARQUIVO, "lista": "app",
        "desativados": ["Zz_Bolsa.png", "SoNoPcDoAmigo.png"]}), encoding="utf-8")
    _dialogo_fixo(monkeypatch, alvo)

    r = web_lixo.importar(conta, "app")

    assert r["quantos"] == 2 and r["ausentes"] == 1


@pytest.mark.parametrize("funcao", ["exportar", "importar"])
def test_fechar_o_dialogo_nao_e_erro(conta, monkeypatch, funcao):
    """Desistir do seletor de arquivo é desistir, não falha -- e a janela não
    pode cuspir um aviso vermelho por isso."""
    monkeypatch.setattr(web_lixo, "_dialogo", lambda salvar, sugestao="": "")
    r = (web_lixo.exportar(conta, "app", []) if funcao == "exportar"
         else web_lixo.importar(conta, "app"))
    assert r["cancelado"] is True and r["erro"] == ""


# ===========================================================================
# A ORDEM DA GRADE — pelo que está ESCRITO, com nível lido como número
# ===========================================================================

@pytest.mark.parametrize("bagunca, esperado", [
    # A queixa exata do usuário: o menor caía no fim da fila.
    (["Belt lvl16", "Belt lvl6", "Belt lvl56"],
     ["Belt lvl6", "Belt lvl16", "Belt lvl56"]),
    # A família inteira junta, e em sequência de nível.
    (["Robe Fada lvl8", "Armguard Fada lvl15", "Armguard Fada lvl8"],
     ["Armguard Fada lvl8", "Armguard Fada lvl15", "Robe Fada lvl8"]),
    # Sem número, é alfabética pura e ignora caixa.
    (["Zinc Ore", "alm Ore", "Bag"], ["alm Ore", "Bag", "Zinc Ore"]),
])
def test_a_ordem_le_o_nivel_como_NUMERO(bagunca, esperado):
    assert sorted(bagunca, key=web_lixo.ordem_da_tela) == esperado


def test_texto_e_numero_nunca_se_comparam(conta):
    """A chave alterna texto e número, então onde os textos empatam o próximo
    pedaço é número dos DOIS lados. Um `TypeError` aqui derrubaria a janela
    inteira -- e só para um par de nomes específico, o que é o pior tipo de
    defeito para achar."""
    nomes = ["Bag", "Bag2", "bag lvl3", "Belt lvl6", "Belt lvl16", "b", "",
             "12", "lvl9 Coisa", "Coisa 9 lvl9"]
    sorted(nomes, key=web_lixo.ordem_da_tela)      # não levanta


def test_a_grade_ja_chega_ordenada(conta, tmp_path, monkeypatch):
    """Ponta a ponta: o `itens` entrega na ordem da tela, e não na do disco.

    `sorted()` por nome de arquivo poria `Belt6.png` DEPOIS de `Belt16.png`.
    """
    pasta = tmp_path / "deletar"
    for nome in ("Zz_Cinto16.png", "Zz_Cinto6.png", "Zz_Anel.png"):
        (pasta / nome).write_bytes(b"png-de-mentira")
    monkeypatch.setitem(web_lixo.LISTAS, "app", (pasta, "app"))

    rotulos = [i["rotulo"] for i in web_lixo.itens(conta, "app")["itens"]]

    # Os dois da fixture entram na mesma ordenação. O que importa é `Cinto6`
    # vir ANTES de `Cinto16`: por nome de arquivo viria depois.
    assert rotulos == ["Zz Anel", "Zz Bolsa", "Zz Carne de Lobo",
                       "Zz Cinto6", "Zz Cinto16"], rotulos
