"""Todo método que o JavaScript chama tem que existir na classe `Api`.

=========================================================================
O DEFEITO QUE ESTE ARQUIVO IMPEDE DE VOLTAR
=========================================================================

`web_app.py` tem DUAS camadas:

    _App    a lógica -- mexe na configuração, fala com o gerenciador
    Api     o que o pywebview expõe ao JavaScript, e que só DELEGA para `_App`

Em 03/09/2026 a HH não ligava: clicar na caixa não fazia nada e ela voltava a
desmarcar na hora. A causa era `alternar_hh` existir no `_App` e **não no
`Api`** -- eu escrevi a lógica e esqueci a ponte.

=========================================================================
E A FALHA ERA INVISÍVEL, O QUE É O PIOR DELA
=========================================================================

Do lado do JavaScript, `chamar()` faz isto:

    const fn = api ? api[nome] : null;
    if (typeof fn !== "function") return Promise.resolve(null);

Ou seja: **método inexistente resolve `null` em silêncio.** Então o `.then()`
rodava normalmente, o `toast()` dizia "HH ligada", e o `carregarContas()`
recarregava a lista -- que vinha do disco com o valor ANTIGO. A caixa voltava a
desmarcar, `hh_farm` nunca virava `True`, e o supervisor nunca via a HH ligada.

Um sintoma, três camadas de distância da causa. E nenhum teste de comportamento
pegaria: a lógica do `_App.alternar_hh` estava correta e testável; o que faltava
era ela ser ALCANÇÁVEL.

=========================================================================
POR QUE A VERIFICAÇÃO É ESTRUTURAL
=========================================================================

Igual a `test_teclas_nas_interfaces.py`: não há comportamento errado para
observar, há uma ligação que não existe. O único jeito de pegar é comparar as
duas pontas -- o que o JS chama contra o que a `Api` expõe.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FONTE_PY = (RAIZ / "blazesbot" / "web_app.py").read_text(encoding="utf-8")
FONTE_JS = (RAIZ / "web" / "main.js").read_text(encoding="utf-8")


def _metodos_publicos(classe: str) -> set[str]:
    """Os métodos públicos daquela classe, pelo AST."""
    arvore = ast.parse(FONTE_PY)
    alvo = next((n for n in arvore.body
                 if isinstance(n, ast.ClassDef) and n.name == classe), None)
    assert alvo is not None, f"a classe {classe} desapareceu de web_app.py"
    return {m.name for m in alvo.body
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not m.name.startswith("_")}


EXPOSTOS = _metodos_publicos("Api")

# Todo `chamar("nome", ...)` do frontend.
CHAMADOS = sorted(set(re.findall(
    r"""chamar\(\s*["']([A-Za-z_][A-Za-z0-9_]*)["']""", FONTE_JS)))


def test_o_frontend_chama_alguma_coisa():
    """Se o regex parar de casar, os testes abaixo passariam vazios -- e um
    teste que não verifica nada é pior que nenhum."""
    assert len(CHAMADOS) > 20, (
        f"só achei {len(CHAMADOS)} chamadas de `chamar(...)` no main.js; o "
        f"padrão de chamada mudou e este arquivo precisa acompanhar")


@pytest.mark.parametrize("nome", CHAMADOS)
def test_o_metodo_que_o_JS_chama_esta_exposto_na_Api(nome: str):
    """`chamar` resolve `null` em silêncio para método inexistente.

    Então esquecer a ponte não dá erro em lugar nenhum: o frontend age como se
    a chamada tivesse funcionado e recarrega o valor antigo do disco.
    """
    assert nome in EXPOSTOS, (
        f"o JavaScript chama `{nome}` e a classe `Api` não expõe. "
        f"`chamar()` vai resolver null EM SILÊNCIO -- o frontend vai parecer "
        f"funcionar e o valor nunca será gravado. Acrescente o método a `Api` "
        f"delegando para `_App.{nome}`.")


# Os métodos da `Api` que NÃO delegam, e por quê. Cada um opera algo que não é
# do `_App`, e a exigência de o motivo estar escrito aqui é o que faz a exceção
# ser decisão em vez de esquecimento.
NAO_DELEGAM = {
    # A JANELA da webview é da `Api`: `_JANELA` é dela, e o `_App` não conhece
    # (nem deve) a existência de uma janela -- é o que permite testar a lógica
    # sem abrir tela nenhuma.
    "minimizar_janela",
    "fechar_janela",
    # O LOGGER é global do processo, não estado do `_App`.
    "definir_nivel_log",
    # Abrir uma pasta no Explorer é do sistema operacional.
    "abrir_pasta_logs",
    # O seletor nativo de arquivo: o WebView2 não consegue ler o caminho de um
    # `<input type=file>`, então a janela do Tk é aberta AQUI.
    "procurar_client_bat",
}


@pytest.mark.parametrize("nome", CHAMADOS)
def test_a_Api_delega_para_a_logica_e_nao_reimplementa(nome: str):
    """A `Api` é ponte, não lugar de regra.

    Regra escrita ali não é testável pelos testes de lógica (que constroem
    `_App`) e vira uma segunda verdade sobre o mesmo assunto.

    As exceções estão em `NAO_DELEGAM`, e cada uma tem o motivo escrito.
    """
    if nome in NAO_DELEGAM:
        pytest.skip(f"`{nome}` não é do `_App` por desenho -- ver NAO_DELEGAM")
    arvore = ast.parse(FONTE_PY)
    api = next(n for n in arvore.body
               if isinstance(n, ast.ClassDef) and n.name == "Api")
    metodo = next(m for m in api.body
                  if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and m.name == nome)
    corpo = ast.unparse(metodo)
    assert "self._app" in corpo, (
        f"`Api.{nome}` não chama `self._app` -- ou ela reimplementou a regra, "
        f"ou a delegação quebrou")


# ===========================================================================
# O ESPELHO AO VIVO -- a outra metade da mesma armadilha
# ===========================================================================


def _payload_do_estado() -> set[str]:
    """As chaves de cada conta dentro de `_App.estado()`."""
    arvore = ast.parse(FONTE_PY)
    app = next(n for n in arvore.body
               if isinstance(n, ast.ClassDef) and n.name == "_App")
    estado = next(m for m in app.body
                  if isinstance(m, ast.FunctionDef) and m.name == "estado")
    chaves: set[str] = set()
    for no in ast.walk(estado):
        if isinstance(no, ast.Dict):
            chaves |= {c.value for c in no.keys
                       if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return chaves


# As chaves que o espelho ao vivo lê de `est.contas`. Cada uma tem que existir
# no payload -- `!!undefined` é `False`, então uma chave ausente DESMARCA a
# caixa a cada volta do polling em vez de não fazer nada.
CHAVES_DO_ESPELHO = ["farm", "farm_hh"]


@pytest.mark.parametrize("chave", CHAVES_DO_ESPELHO)
def test_o_espelho_ao_vivo_recebe_a_chave_que_le(chave: str):
    """Chave ausente no payload não é "não mexe": é `false`.

    O espelho compara `chk.checked !== !!c.<chave>` e corrige. Com a chave
    ausente, `!!undefined` é False -- ou seja, a cada volta do polling ele
    DESMARCA a caixa que o usuário acabou de marcar.
    """
    assert f'"{chave}"' in FONTE_JS or f"'{chave}'" in FONTE_JS or \
        f".{chave}" in FONTE_JS, f"o frontend não lê `{chave}`"
    assert chave in _payload_do_estado(), (
        f"`_App.estado()` não manda `{chave}`, e o espelho ao vivo lê. "
        f"`!!undefined` é False: a caixa vai desmarcar sozinha a cada polling.")


def test_o_espelho_usa_a_MESMA_variavel_da_linha():
    """O primeiro espelho da HH usava `linha.querySelector` num laço cuja
    variável se chama `tr` -- um `ReferenceError` a cada volta do polling, que
    matava o resto de `atualizarEstado` em silêncio (o `catch` de `chamar`
    engole)."""
    inicio = FONTE_JS.index("const chkBC = tr.querySelector")
    trecho = FONTE_JS[inicio:]
    trecho = trecho[:trecho.index("});")]
    assert "linha.querySelector" not in trecho, (
        "o espelho usa `linha`, e a variável do laço é `tr`")
    assert trecho.count("tr.querySelector") == 2, (
        "as duas caixas (BC e HH) têm que sair da MESMA linha da tabela")


# ===========================================================================
# PARIDADE: o que existe na lógica e é acionável tem que ter ponte
# ===========================================================================

# (o que é, o método do `_App`, o nome exposto na `Api`).
#
# OS DOIS NOMES, porque eles não são obrigatoriamente iguais: a conta usa
# `_App.alternar` e `Api.ativar_conta`. Exigir o mesmo nome forçaria um rename
# em código estável para o teste ficar bonito.
LIGA_DESLIGA = [
    ("o BC", "alternar_farm", "alternar_farm"),
    ("a HH", "alternar_hh", "alternar_hh"),
    ("o modo APP", "alternar_app", "alternar_app"),
    ("a conta", "alternar", "ativar_conta"),
]


@pytest.mark.parametrize("o_que,na_logica,na_ponte", LIGA_DESLIGA,
                         ids=lambda v: v if " " not in str(v) else "")
def test_o_liga_desliga_tem_as_TRES_pontas(o_que: str, na_logica: str,
                                           na_ponte: str):
    """Lógica, ponte e chamada no frontend. Faltando qualquer uma, a caixa
    parece funcionar e não grava nada -- foi o que aconteceu com a HH."""
    assert na_logica in _metodos_publicos("_App"), f"{o_que}: falta a lógica"
    assert na_ponte in EXPOSTOS, f"{o_que}: falta a ponte na `Api`"
    assert na_ponte in CHAMADOS, f"{o_que}: o frontend não chama"
