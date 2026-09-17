"""Os templates moram em subpastas por FUNÇÃO, e isso não pode quebrar o load.

===========================================================================
O QUE ESTE ARQUIVO PROTEGE
===========================================================================

Mover um PNG de pasta é a alteração mais silenciosa que existe neste projeto:
`TemplateLibrary.load` devolve `None` quando não acha, e `find_template` com
`None` simplesmente não casa. **Nada levanta exceção.** O bot só passa a não
enxergar o botão, a janela, o NPC -- e isso aparece horas depois como
"o bot parou de vender".

Então a rede é aqui:

  1. todo PNG das categorias é achável pelo NOME, sem a pasta;
  2. nenhum nome existe em duas categorias (a busca pararia na primeira);
  3. os nomes que o código pede de fato resolvem;
  4. a raiz não acumula PNG sem categoria de novo.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from blazesbot.core.vision.templates import (
    SUBPASTAS_DE_CATEGORIA,
    TemplateLibrary,
)
from blazesbot.tools.reorganizar_templates import categoria_de, planejar

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "data" / "templates"


def _pngs_das_categorias() -> list[Path]:
    achados: list[Path] = []
    for sub in SUBPASTAS_DE_CATEGORIA:
        achados.extend(sorted((PASTA / sub).glob("*.png")))
    return achados


@pytest.fixture
def biblioteca() -> TemplateLibrary:
    return TemplateLibrary(PASTA)


def test_todo_template_da_categoria_e_achado_pelo_NOME(biblioteca):
    """O contrato inteiro: quem chama diz o nome, não a pasta."""
    pngs = _pngs_das_categorias()
    assert pngs, "nenhuma subpasta de categoria tem PNG -- a migração rodou?"
    for p in pngs:
        assert biblioteca.caminho_de(p.name) == p, (
            f"{p.name} está em {p.parent.name}/ e o load não o acha")


def test_nenhum_nome_existe_em_DUAS_categorias():
    """A busca para na primeira que casar -- duas com o mesmo nome é loteria.

    Não é hipótese: `boss_2_fase.png`, `dialogo_seta_baixo.png`,
    `link_enter_hh.png` e `link_west_suburb.png` já existem na raiz E em
    `entrada/`, com conteúdo diferente. `entrada/` fica FORA da busca por causa
    disso; dentro das categorias o nome tem de ser único.
    """
    vistos: dict[str, Path] = {}
    for p in _pngs_das_categorias():
        anterior = vistos.get(p.name)
        assert anterior is None, (
            f"{p.name} está em {anterior.parent.name}/ e em {p.parent.name}/")
        vistos[p.name] = p


def test_as_pastas_de_dado_do_usuario_ficam_FORA_da_busca():
    """`deletar/` tem 208 PNG que o usuário põe e tira, com nomes quaisquer.

    Se entrassem na busca por nome, um item da bolsa poderia responder por um
    template de interface. São carregados por `glob` em `bot/deletador`, e é
    assim que tem de continuar.
    """
    for proibida in ("deletar", "deletar_hh", "aprendidos", "entrada"):
        assert proibida not in SUBPASTAS_DE_CATEGORIA


def test_os_nomes_que_o_CODIGO_pede_resolvem(biblioteca):
    """Varre os literais `"*.png"` do código e exige que cada um seja achado.

    Pega o caso que mais dói: alguém move um PNG para uma categoria que não está
    em `SUBPASTAS_DE_CATEGORIA` e o `load` passa a devolver `None` calado.
    """
    literais: set[str] = set()
    for py in (RAIZ / "blazesbot").rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        texto = py.read_text(encoding="utf-8", errors="replace")
        literais.update(re.findall(r'"([A-Za-z0-9_.-]+\.png)"', texto))

    # O QUE ESTE TESTE **NÃO** COBRA, e é decisão, não esquecimento:
    # template que o código pede e que NUNCA existiu no disco. São três hoje --
    # `state_team_member.png`, `menu_leave_team.png` e `menu_team_up.png` --, e
    # eles são GRAVADOS PELO USUÁRIO (`14-RECORTAR-TIME.bat` →
    # `bot/recorte_do_time.py`). Exigir a presença deles aqui reprovaria um
    # repositório recém-clonado, que é o estado correto.
    #
    # O que se exige é o contrário e é o que pega regressão: **arquivo que
    # existe tem de ser achado**. Mover um PNG para uma pasta fora de
    # `SUBPASTAS_DE_CATEGORIA` cai exatamente aqui.
    no_disco = {
        p.name: p for sub in SUBPASTAS_DE_CATEGORIA
        for p in (PASTA / sub).glob("*.png")
    }
    no_disco.update({p.name: p for p in PASTA.glob("*.png")})

    perdidos = [
        nome for nome in sorted(literais)
        if nome in no_disco and biblioteca.caminho_de(nome) is None
    ]
    assert not perdidos, f"o arquivo existe e o load não acha: {perdidos}"


def test_a_raiz_nao_acumula_PNG_sem_categoria():
    """PNG novo solto na raiz é permitido -- some dos diretórios organizados é
    que não pode passar despercebido. O script classifica pelo prefixo; sem
    prefixo conhecido ele avisa em vez de adivinhar."""
    mudancas, _sem_categoria = planejar(PASTA)
    assert not mudancas, (
        "há PNG classificável parado na raiz: rode "
        "`python -m blazesbot.tools.reorganizar_templates`")


@pytest.mark.parametrize("nome,esperado", [
    ("state_queue.png", "estado"),
    ("link_enter_bc.png", "link"),
    ("btn_delete_item.png", "botao"),
    ("janela_fechar.png", "janela"),
    ("vendedor.png", "npc"),
    ("EnemyDead.png", "combate"),
    ("package_courage.png", "item"),
])
def test_a_classificacao_e_a_esperada(nome, esperado):
    assert categoria_de(nome) == esperado
