"""A separação entre os ecossistemas, verificada no grafo de imports.

O BlazesBot é UM sistema com vários ecossistemas:

    blazesbot/bot/bc/    o farm de boss-rush da Bewitcher Cave
    blazesbot/bot/app/   a macro de teclado
    blazesbot/bot/hh/    o farm de boss-rush da Black Wind Camp Dungeon

**UM ECOSSISTEMA NUNCA IMPORTA DO OUTRO.** O que eles compartilham desce para
`blazesbot/bot/` (o sistema: supervisor, contexto, login, watchdog, navegação)
e para `blazesbot/core/` (capacidades que não sabem que ecossistema existe).

E A DESCIDA TEM MÃO ÚNICA: `bot/` não pode depender de ecossistema (só o
supervisor, que escolhe qual roda), e `core/` não pode depender de `bot/`.
Quando a camada de baixo precisa de um dado da cave, ela RECEBE -- é o que
`Navigator(ctx, mapa)` faz.

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
HH = RAIZ / "bot" / "hh"
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


# Os ecossistemas, por nome de pasta. A matriz abaixo cruza TODOS os pares, então
# um quarto ecossistema entra aqui e ganha as verificações de graça -- em vez de
# alguém precisar lembrar de escrever mais dois testes por pasta nova.
ECOSSISTEMAS = {"bc": BC, "app": APP, "hh": HH}


def _pares():
    return [(dono, casa, outro) for dono, casa in ECOSSISTEMAS.items()
            for outro in ECOSSISTEMAS if outro != dono]


@pytest.mark.parametrize("dono,casa,outro", _pares(),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_um_ecossistema_nunca_importa_do_outro(dono, casa, outro):
    """A regra inteira, em uma verificação por par ordenado.

    Um `from ..bc.combat import ...` escrito dentro do `hh/` funciona, passa em
    todos os outros testes e só cobra o preço meses depois. Aqui reprova na hora,
    com o nome do arquivo e o import que sobrou.
    """
    falhas = {}
    for arquivo in _arquivos(casa):
        proibidos = [mod for mod in _modulos_importados(arquivo)
                     if f"bot.{outro}" in mod or mod.endswith(f".{outro}")]
        if proibidos:
            falhas[arquivo.name] = proibidos
    assert not falhas, f"{dono}/ importa do {outro.upper()}: {falhas}"


# ===========================================================================
# A CAMADA DO MEIO: `bot/` serve TODOS os ecossistemas
# ===========================================================================


@pytest.mark.parametrize("arquivo", _arquivos(RAIZ / "bot"), ids=lambda p: p.name)
def test_o_sistema_nao_depende_de_ecossistema_nenhum(arquivo):
    """`bot/` é o SISTEMA -- supervisor, contexto, login, watchdog, navegação.

    Ele serve os três ecossistemas, então não pode depender de um. Um
    `from .bc.mapa_bc import ...` dentro de `bot/navegacao.py` funcionaria hoje e
    quebraria a HH amanhã: a navegação passaria a saber o formato da rota de UMA
    cave e a exigir dela coisas que a outra não tem.

    A SAÍDA QUANDO PRECISAR DO DADO DE UMA CAVE É INJETAR, não importar. É o que
    `Navigator(ctx, mapa)` faz: quem constrói o navegador entrega o mapa, e o
    navegador só pergunta a ele a tolerância do waypoint.

    O SUPERVISOR É A EXCEÇÃO, e é a única: é ele que ESCOLHE qual ecossistema
    roda para cada conta, então conhecer os três é a função dele. Sem essa
    exceção não haveria como despachar.
    """
    if arquivo.name == "supervisor.py":
        return
    proibidos = [m for m in _modulos_importados(arquivo)
                 if any(f"bot.{nome}" in m or m.endswith(f".{nome}")
                        for nome in ECOSSISTEMAS)]
    assert not proibidos, (
        f"bot/{arquivo.name} depende de ecossistema: {proibidos}. "
        f"Injete o dado em vez de importar -- ver `Navigator(ctx, mapa)`.")


def test_o_supervisor_e_a_unica_excecao():
    """Se um segundo arquivo de `bot/` precisar conhecer ecossistema, a decisão
    tem que ser consciente -- este teste é onde ela aparece."""
    conhecem = []
    for arquivo in _arquivos(RAIZ / "bot"):
        if any(f"bot.{nome}" in m or m.endswith(f".{nome}")
               for m in _modulos_importados(arquivo) for nome in ECOSSISTEMAS):
            conhecem.append(arquivo.name)
    assert conhecem == ["supervisor.py"], (
        f"quem conhece ecossistema em bot/: {conhecem}")


@pytest.mark.parametrize("arquivo", _arquivos(CORE), ids=lambda p: p.name)
def test_o_core_nao_conhece_ecossistema_nenhum(arquivo):
    """`core/` é a camada de baixo: se ela importar de `bot/`, a dependência
    inverte e o `core` deixa de ser reusável fora do bot."""
    proibidos = [m for m in _modulos_importados(arquivo)
                 if m.startswith("blazesbot.bot") or ".bot." in m]
    assert not proibidos, f"core/{arquivo.name} importa de bot/: {proibidos}"


def test_toda_pasta_de_ecossistema_existe_e_tem_dono():
    """Se alguém apagar um `__init__.py`, a regra some junto com a explicação."""
    for pasta in ECOSSISTEMAS.values():
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

    fonte = (RAIZ / "bot" / "navegacao.py").read_text(encoding="utf-8")
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
    # O motor de combate saiu de `bc/` para `bot/` em 01/09/2026 e passou a
    # servir os dois ecossistemas de cave -- a peça compartilhada com o APP
    # continua sendo a mesma, e agora tem três usuários em vez de dois.
    motor = _fonte("blazesbot/bot/combate.py")
    app = _fonte("blazesbot/bot/app/executor.py")

    for arquivo, fonte in (("bot/combate.py", motor), ("app/executor.py", app)):
        assert "core.target_hybrid import" in fonte, arquivo
        assert "MorteDoAlvo" in fonte, arquivo
        assert "self._morte_do_alvo = MorteDoAlvo()" in fonte, arquivo


def test_NENHUM_dos_dois_reimplementa_a_trava():
    """A duplicata que esta peça desfez: os dois tinham o mesmo atributo, a
    mesma regra e o mesmo comentário explicando que a trava é por identidade."""
    for caminho in ("blazesbot/bot/combate.py",
                    "blazesbot/bot/app/executor.py"):
        fonte = _fonte(caminho)
        assert "_ultimo_alvo_morto_id: int | None = None" not in fonte, caminho


def test_o_reuso_esta_DOCUMENTADO_como_dependencia_cruzada():
    """*"Tudo o que for reaproveitado deve ser rigorosamente documentado no
    código. Explique a origem da função compartilhada e garanta que outros
    desenvolvedores saibam que se trata de uma dependência cruzada."*"""
    core = _fonte("blazesbot/core/target_hybrid.py")

    assert "DEPENDENCIA CRUZADA" in core
    assert "bot/combate.py" in core, "não diz QUEM usa"
    assert "bot/app/executor.py" in core, "não diz QUEM usa"
    assert "O que NAO subiu" in core, "não diz o que ficou de fora, e por quê"

    for caminho in ("blazesbot/bot/combate.py",
                    "blazesbot/bot/app/executor.py"):
        fonte = _fonte(caminho)
        assert "COMPARTILHAD" in fonte.upper(), caminho


def test_o_mural_promovido_esta_DOCUMENTADO_como_dependencia_cruzada():
    """A mesma exigência do teste acima, para a promoção de 27/08/2026.

    `bot/mural.py` saiu de `bot/bc/team.py` porque o ecossistema APP passou a
    precisar do mesmo quadro de avisos entre contas. Promoção sem esta
    documentação é a armadilha que a diretiva descreve: quem mexer no mural
    mexe em DOIS ecossistemas e não tem como saber disso lendo o arquivo.
    """
    mural = _fonte("blazesbot/bot/mural.py")

    assert "DEPENDENCIA CRUZADA" in mural
    assert "bot/team.py" in mural, "não diz QUEM usa"
    assert "APP" in mural, "não diz que o APP passou a usar"
    assert "NÃO SUBIU" in mural.upper(), "não diz o que ficou de fora, e por quê"

    # E o mural não pode conhecer ecossistema nenhum: ele é o pedaço que os dois
    # compartilham, então uma menção a `bc.` ou `app.` em import seria o
    # acoplamento voltando pela porta dos fundos.
    import ast
    arvore = ast.parse(mural)
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom):
            assert not (no.module or "").startswith(("blazesbot.bot.bc",
                                                     "blazesbot.bot.app")), no.module
        elif isinstance(no, ast.Import):
            for alias in no.names:
                assert not alias.name.startswith(("blazesbot.bot.bc",
                                                  "blazesbot.bot.app")), alias.name


def test_o_mural_nao_ficou_duplicado_no_bc():
    """O quadro de avisos existe em UM lugar só.

    A tentação, ao promover, é deixar o original de pé "para o BC continuar
    funcionando". Seriam DOIS dicionários de batidas: o reseter bate num e o
    farm consulta o outro, e a conta espera para sempre na porta da cave sem
    erro nenhum -- nenhum teste pegaria, porque cada um importaria um módulo.
    """
    from pathlib import Path
    assert not (RAIZ / "blazesbot/bot/bc/team.py").exists(), (
        "bc/team.py voltou a existir: o mural precisa morar em um lugar só."
    )
    assert not (RAIZ / "blazesbot/bot/bc/mural.py").exists()
    for caminho in Path(RAIZ / "blazesbot/bot/bc").glob("*.py"):
        fonte = caminho.read_text(encoding="utf-8")
        assert "_LOCK_BATIDAS" not in fonte, caminho
        assert "_BATIDAS: dict" not in fonte, caminho


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
