"""A separação entre os ecossistemas, verificada no grafo de imports.

O BlazesBot é UM sistema com vários ecossistemas:

    blazesbot/bot/bc/    o farm de boss-rush da Bewitcher Cave
    blazesbot/bot/app/   a macro de teclado

**UM ECOSSISTEMA NUNCA IMPORTA DO OUTRO.** O que eles compartilham desce para
`blazesbot/bot/` (o sistema: supervisor, contexto, login, watchdog) e para
`blazesbot/core/` (capacidades que não sabem que ecossistema existe).

ESTE TESTE EXISTE PORQUE A REGRA É INVISÍVEL NO DIA A DIA. Um `from ..bc.combat
import ...` escrito dentro do `app/` funciona, passa em todos os outros testes e
só cobra o preço meses depois, quando mexer num ecossistema quebrar o outro.
Aqui ele reprova na hora.
"""
import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent / "blazesbot"
BC = RAIZ / "bot" / "bc"
APP = RAIZ / "bot" / "app"
CORE = RAIZ / "core"


def _modulos_importados(arquivo: pathlib.Path) -> list[str]:
    """Os módulos que este arquivo importa, com o relativo já resolvido.

    Trabalha no AST e não em texto: um import dentro de função (o projeto usa
    vários, para quebrar ciclo) conta igual, e comentário citando um módulo
    não conta.
    """
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    # Pacote deste arquivo, em partes: blazesbot.bot.bc -> [blazesbot, bot, bc]
    pacote = list(arquivo.relative_to(RAIZ.parent).parts[:-1])

    achados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            achados.extend(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom):
            if no.level:                       # relativo: sobe `level` níveis
                base = pacote[:len(pacote) - no.level + 1]
                achados.append(".".join(base + ([no.module] if no.module else [])))
            elif no.module:
                achados.append(no.module)
    return achados


def _arquivos(pasta: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in pasta.glob("*.py"))


@pytest.mark.parametrize("arquivo", _arquivos(BC), ids=lambda p: p.name)
def test_o_ecossistema_bc_nao_importa_do_app(arquivo):
    proibidos = [m for m in _modulos_importados(arquivo)
                 if "bot.app" in m or m.endswith(".app")]
    assert not proibidos, f"{arquivo.name} importa do APP: {proibidos}"


@pytest.mark.parametrize("arquivo", _arquivos(APP), ids=lambda p: p.name)
def test_o_ecossistema_app_nao_importa_do_bc(arquivo):
    proibidos = [m for m in _modulos_importados(arquivo)
                 if "bot.bc" in m or m.endswith(".bc")]
    assert not proibidos, f"{arquivo.name} importa do BC: {proibidos}"


@pytest.mark.parametrize("arquivo", _arquivos(CORE), ids=lambda p: p.name)
def test_o_core_nao_conhece_ecossistema_nenhum(arquivo):
    """`core/` é a camada de baixo: se ela importar de `bot/`, a dependência
    inverte e o `core` deixa de ser reusável fora do bot."""
    proibidos = [m for m in _modulos_importados(arquivo)
                 if m.startswith("blazesbot.bot") or ".bot." in m]
    assert not proibidos, f"core/{arquivo.name} importa de bot/: {proibidos}"


def test_as_duas_pastas_de_ecossistema_existem_e_tem_dono():
    """Se alguém apagar um `__init__.py`, a regra some junto com a explicação."""
    for pasta in (BC, APP):
        inicial = pasta / "__init__.py"
        assert inicial.exists(), f"{pasta.name}/__init__.py sumiu"
        texto = inicial.read_text(encoding="utf-8")
        assert "NUNCA IMPORTA DO OUTRO" in texto, \
            f"{pasta.name}/__init__.py perdeu a regra dos ecossistemas"


def test_o_executor_do_app_so_usa_o_core():
    """O isolamento mais apertado do projeto: o executor manda tecla e espera.

    Tudo que precisa de mais que isso (pet, barra de atalhos, deletar) chega
    como FUNÇÃO injetada pelo supervisor -- é assim que ele continua sem saber
    o que é `BotContext`.
    """
    de_fora = [m for m in _modulos_importados(APP / "executor.py")
               if m.startswith("blazesbot") and not m.startswith("blazesbot.core")]
    assert not de_fora, f"o executor passou a importar: {de_fora}"


# ===========================================================================
# A RAJADA DE CLIQUE DIREITO
# ===========================================================================


def test_o_clique_direito_repete_e_o_esquerdo_nao():
    """A repetição vale SÓ para o botão direito.

    No esquerdo o risco é outro e maior: ele tem efeito POR CLIQUE. Quatro
    cliques num item da grade de venda gastariam quatro da contagem que o
    usuário configurou; quatro no link de um NPC repetiriam o pedido.
    """
    from blazesbot.core import inputs

    class _Contador(inputs.Input):
        def __init__(self):
            self.hwnd = 0
            self.envios = []

        def _click(self, down, wparam, up, x, y):
            self.envios.append(down)

    i = _Contador()
    i.right_click(10, 20)
    assert len(i.envios) == inputs.CLIQUES_DIREITOS_POR_TENTATIVA
    assert set(i.envios) == {inputs.WM_RBUTTONDOWN}

    i.envios.clear()
    i.left_click(10, 20)
    assert len(i.envios) == 1, "o clique esquerdo NÃO pode repetir"


def test_a_rajada_usa_sempre_a_MESMA_coordenada():
    """Repetir em pontos diferentes seria varrer, não insistir."""
    from blazesbot.core import inputs

    class _Pontos(inputs.Input):
        def __init__(self):
            self.hwnd = 0
            self.pontos = []

        def _click(self, down, wparam, up, x, y):
            self.pontos.append((x, y))

    i = _Pontos()
    i.right_click(123, 456)
    assert set(i.pontos) == {(123, 456)}


def test_voltar_ao_comportamento_antigo_e_UMA_constante(monkeypatch):
    """`1` devolve exatamente o clique de sempre — é a saída do experimento."""
    from blazesbot.core import inputs

    monkeypatch.setattr(inputs, "CLIQUES_DIREITOS_POR_TENTATIVA", 1)

    class _Contador(inputs.Input):
        def __init__(self):
            self.hwnd = 0
            self.n = 0

        def _click(self, *a):
            self.n += 1

    i = _Contador()
    i.right_click(1, 2)
    assert i.n == 1


def test_valor_invalido_nao_zera_o_clique(monkeypatch):
    """`0` ou negativo por engano não pode fazer o bot parar de clicar."""
    from blazesbot.core import inputs

    class _Contador(inputs.Input):
        def __init__(self):
            self.hwnd = 0
            self.n = 0

        def _click(self, *a):
            self.n += 1

    for valor in (0, -3):
        monkeypatch.setattr(inputs, "CLIQUES_DIREITOS_POR_TENTATIVA", valor)
        i = _Contador()
        i.right_click(1, 2)
        assert i.n == 1, f"com {valor} o bot deixou de clicar"


def test_o_minimapa_clica_UMA_vez_so():
    """No minimapa cada clique é uma ORDEM DE ANDAR.

    A rajada ali não é insistência, é imprecisão: o ponto foi calculado a
    partir da posição ATUAL, e entre um clique e o seguinte o personagem já
    saiu do lugar — o 2º, 3º e 4º apontam para um destino deslocado.
    """
    from blazesbot.core import inputs

    class _Contador(inputs.Input):
        def __init__(self):
            self.hwnd = 0
            self.n = 0

        def _click(self, *a):
            self.n += 1

    i = _Contador()
    i.right_click(10, 20, repetir=False)
    assert i.n == 1

    i.n = 0
    i.right_click(10, 20)          # o padrão continua sendo a rajada
    assert i.n == inputs.CLIQUES_DIREITOS_POR_TENTATIVA


def test_os_cliques_de_ANDAR_do_minimapa_passam_repetir_False():
    """Trava os DOIS pontos por leitura do código-fonte.

    Um `ctx.right_click(ponto)` novo no laço de movimento voltaria a
    desalinhar o trajeto sem erro nenhum aparecer — o personagem só andaria
    para o lugar errado. Aqui isso reprova.
    """
    import re

    fonte = (RAIZ / "bot" / "bc" / "navigation.py").read_text(encoding="utf-8")
    chamadas = re.findall(r"ctx\.right_click\(([^\n]*)", fonte)
    do_minimapa = [c for c in chamadas if "pixel" in c or "ponto" in c]
    assert do_minimapa, "as chamadas do minimapa sumiram do navigation"
    sem_excecao = [c for c in do_minimapa
                   if "repetir=False" not in c and "pixel[0] - 30" not in c]
    # O que sobra tem que ser só o clique do MAPA-MÚNDI (linha 436), que é
    # deliberado e espaçado por `tick(2.0)`.
    assert len(sem_excecao) <= 1, sem_excecao


# ===========================================================================
# REUSO E PROMOÇÃO — diretiva permanente do usuário (26/08/2026)
# ===========================================================================
#
# *"A duplicação de funções é inaceitável. (...) Se você identificar que uma
# função restrita a um ecossistema possui utilidade geral, é sua OBRIGAÇÃO
# refatorá-la, abstrair suas dependências locais e promovê-la para o Core
# Global. (...) Ao trabalhar com fluxos do TARGET, aplique esta regra com rigor
# máximo."*

def _fonte(caminho: str) -> str:
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    return (raiz / caminho).read_text(encoding="utf-8")


def test_o_veredito_de_morte_do_alvo_MORA_NO_CORE():
    """"O mob morreu?" é sobre o JOGO, não sobre o ecossistema: mesma struct,
    mesmo cadáver de 7 a 13 s, mesmo significado de `hp == 0`."""
    from blazesbot.core.target_hybrid import MorteDoAlvo

    assert MorteDoAlvo.veredito({"hp": 0, "max_hp": 100}) is True
    assert MorteDoAlvo.veredito({"hp": 1, "max_hp": 100}) is False
    assert MorteDoAlvo.veredito({"hp": None}) is None
    assert MorteDoAlvo.veredito(None) is None


def test_a_trava_por_IDENTIDADE_e_uma_so_para_os_dois():
    from blazesbot.core.target_hybrid import MorteDoAlvo

    morte = MorteDoAlvo()
    assert morte.contar(0x111) is True, "a primeira morte tem que contar"
    assert morte.contar(0x111) is False, "contou o mesmo óbito duas vezes"
    assert morte.contar(0x222) is True, "engoliu a morte seguinte"

    morte.esquecer()
    assert morte.contar(0x222) is True, "o reset por luta não valeu"


def test_os_DOIS_ecossistemas_usam_a_MESMA_peca():
    """O teste que a diretiva pede: rastreabilidade entre os dois ambientes."""
    bc = _fonte("blazesbot/bot/bc/combat.py")
    app = _fonte("blazesbot/bot/app/executor.py")

    for arquivo, fonte in (("bc/combat.py", bc), ("app/executor.py", app)):
        assert "from ...core.target_hybrid import" in fonte, arquivo
        assert "MorteDoAlvo" in fonte, arquivo
        assert "self._morte_do_alvo = MorteDoAlvo()" in fonte, arquivo


def test_NENHUM_dos_dois_reimplementa_a_trava():
    """A duplicata que esta peça desfez: os dois tinham o mesmo atributo, a
    mesma regra e o mesmo comentário explicando que a trava é por identidade."""
    for caminho in ("blazesbot/bot/bc/combat.py",
                    "blazesbot/bot/app/executor.py"):
        fonte = _fonte(caminho)
        assert "_ultimo_alvo_morto_id: int | None = None" not in fonte, caminho


def test_o_reuso_esta_DOCUMENTADO_como_dependencia_cruzada():
    """*"Tudo o que for reaproveitado deve ser rigorosamente documentado no
    código. Explique a origem da função compartilhada e garanta que outros
    desenvolvedores saibam que se trata de uma dependência cruzada."*"""
    core = _fonte("blazesbot/core/target_hybrid.py")

    assert "DEPENDENCIA CRUZADA" in core
    assert "bot/bc/combat.py" in core, "não diz QUEM usa"
    assert "bot/app/executor.py" in core, "não diz QUEM usa"
    assert "O que NAO subiu" in core, "não diz o que ficou de fora, e por quê"

    for caminho in ("blazesbot/bot/bc/combat.py",
                    "blazesbot/bot/app/executor.py"):
        fonte = _fonte(caminho)
        assert "COMPARTILHAD" in fonte.upper(), caminho


def test_a_peca_compartilhada_NAO_arrasta_dependencia_do_ecossistema():
    """*"Abstrair suas dependências locais"* — a peça promovida não pode
    conhecer nem o BC nem o APP, senão ela não é core, é acoplamento com outro
    nome."""
    import ast
    import inspect

    from blazesbot.core import target_hybrid

    arvore = ast.parse(inspect.getsource(target_hybrid))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module)
        elif isinstance(no, ast.Import):
            importados.update(a.name for a in no.names)

    assert not any("bot" in m.split(".") for m in importados), importados
