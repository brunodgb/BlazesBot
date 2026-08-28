"""JANELA ABERTA NA FRENTE ENGOLE O CLIQUE NA CENA 3D.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

Print do usuário em 26/08/2026: personagem parado na coordenada EXATA da entrada
da cave (1395,-635), Skull Herald já selecionado, time de reset já formado -- e o
painel "Surroundings" aberto na frente, engolindo o clique a run inteira.

Três causas somadas, e cada uma tem teste aqui:

1. `fechar_surroundings` tratava "não consigo VER o painel" como "o painel não
   está aberto" e voltava em silêncio achando que tinha fechado.

2. Ela tinha UM ponto de chamada no arquivo inteiro -- no caminho de SUCESSO de
   `ir_para_resultado`. Três outras saídas deixavam o painel aberto.

3. Não existia conferência nenhuma antes dos cliques na cena 3D: o bot clicava
   e torcia.

E um quarto defeito, achado no caminho: `ir_para_resultado` acionava o portão da
montaria com o CAMPO DE BUSCA FOCADO, e esse portão insiste SEM TETO. Cada toque
da tecla caía dentro do campo -- o `Skull00000000...` que o usuário relatou.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from blazesbot.bot.bc import ui_service
from blazesbot.core import janelas_abertas as ja
from blazesbot.core.vision import TemplateLibrary

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATES = RAIZ / "data" / "templates"


class _Log:
    def __init__(self):
        self.linhas: list[str] = []

    def _guardar(self, msg, *a, **k):
        self.linhas.append(str(msg))

    debug = info = warning = error = _guardar


# ---------------------------------------------------------------------------
# OS TEMPLATES E OS LIMIARES MEDIDOS
# ---------------------------------------------------------------------------

def test_os_dois_templates_existem_e_sao_COLORIDOS():
    """Em cinza eles não servem: a medição foi feita em cor.

    E cor é o modo certo para este alvo -- o X de fechar é VERMELHO sobre placa
    escura, e a HUD do jogo é cheia de glifos escuros do mesmo tamanho.
    """
    lib = TemplateLibrary(TEMPLATES)
    for nome in (ja.TEMPLATE_DO_X, ja.TEMPLATE_DA_MOLDURA):
        assert (TEMPLATES / nome).exists(), f"{nome} sumiu de data/templates"
        colorido = lib.load_color(nome)
        assert colorido is not None and colorido.ndim == 3, nome


def test_os_limiares_sao_os_MEDIDOS():
    """Medição de 26/08/2026, 16 quadros (11 com janela, 5 sem).

        sinal      pior COM   pior SEM   margem
        X          0.898      0.327      +0.571
        moldura    0.829      0.391      +0.438

    O X fica no 0.80 padrão do projeto (folga 0.098 acima do pior verdadeiro).
    A moldura NÃO: o pior verdadeiro dela (0.829) veio de uma cena escura dentro
    da cave, e 0.80 deixaria 0.029 de folga. 0.65 fica no MEIO do vão.
    """
    assert ja.LIMIAR_DO_X == 0.80
    assert ja.LIMIAR_DA_MOLDURA == 0.65
    assert ja.LIMIAR_DA_MOLDURA < ja.LIMIAR_DO_X, (
        "a moldura é o sinal de margem MENOR; o limiar dela não pode subir "
        "acima do limiar do X")


def test_o_casamento_e_COLORIDO_no_codigo():
    """Casar em cinza aplicaria limiares medidos em cor a outro espaço.

    Este teste lê o AST porque a diferença é invisível em revisão: `load` e
    `load_color` só diferem por uma palavra, e o resultado errado não levanta
    exceção -- ele só devolve números de outro espaço.
    """
    fonte = textwrap.dedent(inspect.getsource(ja))
    arvore = ast.parse(fonte)
    chamadas = [n for n in ast.walk(arvore) if isinstance(n, ast.Call)]

    carregamentos = [n for n in chamadas
                     if isinstance(n.func, ast.Attribute)
                     and n.func.attr.startswith("load")]
    assert carregamentos, "ninguém carrega template neste módulo"
    for n in carregamentos:
        assert n.func.attr == "load_color", (
            "template carregado em cinza; os limiares foram medidos em cor")

    buscas = [n for n in chamadas
              if isinstance(n.func, ast.Name) and n.func.id.startswith("find_")]
    assert buscas, "ninguém procura template neste módulo"
    for n in buscas:
        assert n.func.id == "find_all_templates", (
            "`find_template` converte o quadro para cinza; use "
            "`find_all_templates(colorido=True)`")
        assert any(k.arg == "colorido" and k.value.value is True
                   for k in n.keywords), "faltou colorido=True"


# ---------------------------------------------------------------------------
# A LEITURA TRI-ESTADO
# ---------------------------------------------------------------------------

def test_sem_quadro_e_NAO_SEI_nunca_LIMPO():
    """Foi tratar "não sei" como "está limpo" que produziu o defeito."""
    lib = TemplateLibrary(TEMPLATES)
    leitura = ja.ler(None, lib)
    assert leitura.tem_janela is None
    assert leitura.ponto_de_fechar is None


def test_quadro_em_CINZA_e_NAO_SEI_e_nao_erro_silencioso():
    """Quadro de um canal aqui é carga errada, não "tela desconhecida".

    Responder `False` a isso seria dizer "está limpo" sem ter olhado -- e é
    exatamente a classe de erro que este módulo existe para não cometer.
    """
    lib = TemplateLibrary(TEMPLATES)
    assert ja.ler(np.zeros((200, 200), np.uint8), lib).tem_janela is None


def test_quadro_limpo_responde_FALSE_e_nao_None():
    """Olhei e não tem: é uma resposta, não uma dúvida."""
    lib = TemplateLibrary(TEMPLATES)
    leitura = ja.ler(np.zeros((400, 400, 3), np.uint8), lib)
    assert leitura.tem_janela is False
    assert leitura.sei_fechar is False


def test_sem_templates_em_disco_e_NAO_SEI():
    """Sem os dois recortes não há como olhar -- e "não sei" não é "limpo"."""
    vazia = TemplateLibrary(RAIZ / "data" / "templates" / "nao-existe")
    assert ja.ler(np.zeros((400, 400, 3), np.uint8), vazia).tem_janela is None


# ---------------------------------------------------------------------------
# O LAÇO QUE DESOBSTRUI
# ---------------------------------------------------------------------------

def _peças(leituras):
    """Devolve (kwargs, registro). `leituras` é a fila de `Leitura` a servir."""
    registro = {"cliques": [], "esperas": [], "capturas": 0}
    fila = list(leituras)

    def capturar():
        registro["capturas"] += 1
        return "quadro"

    def clicar(ponto):
        registro["cliques"].append(ponto)

    def esperar(seg):
        registro["esperas"].append(seg)

    class _Templates:
        pass

    kwargs = dict(capturar=capturar, templates=_Templates(),
                  clicar=clicar, esperar=esperar, log=_Log())
    return kwargs, registro, fila


def test_tela_limpa_devolve_True_sem_clicar(monkeypatch):
    kwargs, registro, fila = _peças([ja.Leitura(False, None)])
    monkeypatch.setattr(ja, "ler", lambda q, t: fila.pop(0))
    assert ja.desobstruir(**kwargs) is True
    assert registro["cliques"] == []


def test_nao_sei_devolve_None_sem_clicar(monkeypatch):
    """"Não sei" NUNCA autoriza clicar: o botão de fechar fica sobre a cena 3D,
    e um clique que erra manda o personagem ANDAR."""
    kwargs, registro, fila = _peças([ja.Leitura(None, None)])
    monkeypatch.setattr(ja, "ler", lambda q, t: fila.pop(0))
    assert ja.desobstruir(**kwargs) is None
    assert registro["cliques"] == []


def test_janela_SEM_X_nao_e_fechada_as_cegas(monkeypatch):
    """Fechar às cegas é clicar num interruptor sem ver o estado -- o erro que
    já produziu o pisca-pisca do painel de arredores."""
    kwargs, registro, fila = _peças([ja.Leitura(True, None)])
    monkeypatch.setattr(ja, "ler", lambda q, t: fila.pop(0))
    assert ja.desobstruir(**kwargs) is False
    assert registro["cliques"] == []


def test_fecha_UMA_por_passada_e_RECONFERE(monkeypatch):
    """Fechar uma janela MUDA a tela.

    A de baixo pode se reposicionar e as sub-janelas somem junto com a mãe (as
    `Expand Bag` fecham com o inventário). Clicar numa leva de coordenadas
    calculadas de uma vez só significa clicar em posições obsoletas -- e cada
    clique obsoleto cai na cena 3D e manda o personagem andar.
    """
    kwargs, registro, fila = _peças([
        ja.Leitura(True, (100, 20)),
        ja.Leitura(True, (300, 40)),
        ja.Leitura(False, None),
    ])
    monkeypatch.setattr(ja, "ler", lambda q, t: fila.pop(0))

    assert ja.desobstruir(**kwargs) is True
    assert registro["cliques"] == [(100, 20), (300, 40)]
    # Uma captura por passada: a reconferência é o ponto todo.
    assert registro["capturas"] == 3


def test_teto_impede_laco_infinito(monkeypatch):
    """Se o clique de fechar não surtir efeito, isto para em vez de insistir."""
    monkeypatch.setattr(ja, "ler", lambda q, t: ja.Leitura(True, (10, 10)))
    kwargs, registro, _ = _peças([])
    assert ja.desobstruir(**kwargs, teto=3) is False
    assert len(registro["cliques"]) == 3


# ---------------------------------------------------------------------------
# `fechar_surroundings` -- o buraco original
# ---------------------------------------------------------------------------

def _servico():
    """Um `UIService` sem construtor, com as peças que estes testes tocam."""
    s = ui_service.UIService.__new__(ui_service.UIService)
    s.esperas: list[float] = []
    s.cliques: list = []
    s.ctx = SimpleNamespace(
        tick=lambda seg: s.esperas.append(seg),
        click=lambda p: s.cliques.append(p),
        raise_if_stopped=lambda: None,
        log=_Log(),
    )
    s._painel_usado_em = 0.0
    s._aberturas_do_trajeto = 0
    return s


def test_fechar_devolve_NAO_SEI_quando_nao_enxerga():
    """O defeito original: "não consigo ver" virava "já está fechado".

    Num quadro ruim -- animação, névoa, rumor passando por cima -- o template
    cai abaixo do limiar por um instante. Antes, a função voltava em silêncio e
    o painel ficava aberto para engolir o clique seguinte.
    """
    s = _servico()
    s._pontos = lambda grupo, quadro=None: None
    s._consigo_enxergar = lambda grupo: False

    assert s.fechar_surroundings() is None
    assert s.cliques == [], "não pode clicar sem enxergar"


def test_fechar_devolve_True_quando_o_painel_ja_nao_esta_la():
    """Enxergo a tela e o painel não está nela: isso é "fechado", com certeza."""
    s = _servico()
    s._pontos = lambda grupo, quadro=None: None
    s._consigo_enxergar = lambda grupo: True

    assert s.fechar_surroundings() is True
    assert s.cliques == []


def test_fechar_RELE_antes_de_desistir_de_ver():
    """O caso real é um QUADRO ruim, não cegueira permanente."""
    s = _servico()
    leituras = [None, None, {"close": (600, 195)}]
    s._pontos = lambda grupo, quadro=None: (
        leituras.pop(0) if leituras else None)
    s._consigo_enxergar = lambda grupo: True

    assert s.fechar_surroundings() is True
    assert s.cliques == [(600, 195)], "achou na terceira leitura e fechou"


def test_fechar_devolve_False_quando_o_painel_NAO_some():
    """Clicou no fechar e ele continuou lá: quem chama precisa saber."""
    s = _servico()
    s._pontos = lambda grupo, quadro=None: {"close": (600, 195)}
    s._consigo_enxergar = lambda grupo: True

    assert s.fechar_surroundings() is False


# ---------------------------------------------------------------------------
# O DONO DO PAINEL, O ORÇAMENTO E A ORDEM DA MONTARIA
# ---------------------------------------------------------------------------

def test_o_trajeto_fecha_o_painel_ATE_por_excecao():
    """Era o buraco nº 2: `fechar_surroundings` tinha UM ponto de chamada, no
    caminho de sucesso. Toda outra saída deixava o painel aberto."""
    fonte = textwrap.dedent(inspect.getsource(
        ui_service.UIService.trajeto_pelo_painel))
    arvore = ast.parse(fonte).body[0]

    finallys = [n for n in ast.walk(arvore)
                if isinstance(n, ast.Try) and n.finalbody]
    assert finallys, "o fechamento saiu do `finally`; volta a vazar por exceção"
    corpo = " ".join(ast.unparse(n) for f in finallys for n in f.finalbody)
    assert "fechar_surroundings" in corpo


def test_os_trajetos_pelo_painel_usam_o_dono():
    """Quem busca NPC e sai andando é dono do painel do começo ao fim."""
    for metodo in (ui_service.UIService._viajar_para_ghost_din_woods,
                   ui_service.UIService.ir_ate_o_npc_da_cave):
        fonte = inspect.getsource(metodo)
        assert "trajeto_pelo_painel" in fonte, metodo.__name__


def test_o_orcamento_recusa_a_quinta_abertura():
    """3 x 3 = 9 aberturas era PRODUTO de duas camadas que não se conhecem.

    Recusar dentro do `abrir_surroundings` faz os dois laços de retentativa
    pararem sozinhos, sem precisar desmontar nenhum deles.
    """
    s = _servico()
    s._aberturas_do_trajeto = ui_service.ABERTURAS_POR_TRAJETO
    assert s.abrir_surroundings() is None
    assert s.cliques == [], "recusou sem tocar no interruptor do painel"


def test_comecar_trajeto_zera_o_orcamento():
    s = _servico()
    s._aberturas_do_trajeto = 99
    s.comecar_trajeto("teste")
    assert s._aberturas_do_trajeto == 0


def test_ir_para_resultado_NAO_aciona_a_montaria():
    """O `Skull00000000...`.

    `buscar_npc` acabou de clicar no campo de busca e digitar -- o campo está
    com o FOCO. O portão da montaria INSISTE SEM TETO, então cada toque da tecla
    caía dentro do campo. E a chamada era redundante: `abrir_surroundings` já
    exige montaria ANTES de abrir, que é a ordem certa (montaria -> Surroundings).
    """
    fonte = textwrap.dedent(inspect.getsource(
        ui_service.UIService.ir_para_resultado))
    chamadas = {n.func.attr for n in ast.walk(ast.parse(fonte))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "garantir_montaria_para_andar" not in chamadas, (
        "o portão da montaria voltou para depois da abertura do painel; com o "
        "campo de busca focado, ele digita a tecla dentro da busca")


def test_a_montaria_continua_sendo_exigida_ANTES_de_abrir():
    """Tirar a chamada redundante não pode virar "anda a pé"."""
    fonte = inspect.getsource(ui_service.UIService.abrir_surroundings)
    assert "garantir_montaria_para_andar" in fonte


def test_a_cadencia_e_carimbada_no_auto_path_E_no_fechamento():
    """Carimbar só na abertura media *abrir -> abrir*, e um ciclo inteiro passa
    de 2 s -- então a trava quase nunca mordia."""
    for metodo in (ui_service.UIService.ir_para_resultado,
                   ui_service.UIService.fechar_surroundings):
        fonte = inspect.getsource(metodo)
        assert "_marcar_uso_do_painel" in fonte, metodo.__name__


# ---------------------------------------------------------------------------
# O GUARDA NO CAMINHO DOS CLIQUES DA ENTRADA
# ---------------------------------------------------------------------------

def test_o_guarda_roda_antes_da_rajada_de_entrada():
    """Daqui em diante saem dois cliques por segundo na cena 3D."""
    fonte = inspect.getsource(ui_service.UIService.preparar_entrada)
    assert "desobstruir_a_cena" in fonte


def test_o_guarda_NAO_bloqueia_quando_nao_sabe():
    """Regra permanente do projeto: "não sei" não bloqueia.

    `CONFERIR_A_JANELA_ANTES_DE_ENVIAR` já diz "bot mudo é pior que o defeito",
    e `na_posicao_de_clicar` devolve True sem leitura porque recusar travaria o
    bot num laço sem saída.
    """
    fonte = textwrap.dedent(inspect.getsource(
        ui_service.UIService.desobstruir_a_cena))
    arvore = ast.parse(fonte).body[0]
    # Nenhum `raise` e nenhum `return False` incondicional: ele informa e
    # devolve o veredito, quem chama decide.
    assert not [n for n in ast.walk(arvore) if isinstance(n, ast.Raise)], (
        "o guarda passou a levantar exceção; isso trava a run por uma leitura")


def test_o_guarda_NAO_roda_antes_do_clique_direito_da_block_list():
    """AUTO-SABOTAGEM: o clique direito da Block list precisa da lista ABERTA.

    Um guarda que exige "nenhuma janela aberta" antes dele fecharia a própria
    lista que ele vai operar. O caso do `team.py` já está coberto de outro jeito:
    `preparar_entrada` roda o guarda DEPOIS do time formado e ANTES da rajada de
    cliques da entrada.
    """
    from blazesbot.bot import team
    fonte = inspect.getsource(team.TeamService._enviar_convite)
    assert "desobstruir_a_cena" not in fonte, (
        "o guarda entrou antes do clique direito da Block list e vai fechar a "
        "lista que o menu de contexto precisa")
