"""O que foi MEDIDO no jogo para a HH: templates, waypoint, câmera, venda.

Este arquivo separa o que veio de MEDIÇÃO do que veio do bot em Lua. A distinção
importa: os waypoints do Lua são medição de um bot que roda hoje em produção, mas
tudo aqui foi lido da TELA em 03/09/2026, com print guardado em
`data/templates/entrada/` como evidência de onde cada número saiu.

O que cada teste protege:

  * os TEMPLATES existem, estão na pasta de onde o código carrega, e têm o
    tamanho de um RECORTE -- não de uma tela inteira, que foi o erro do primeiro
    `link_enter_hh.png` (1029x804);
  * o WAYPOINT da porta é o lido no rótulo do print, e concorda com o do Lua;
  * a CÂMERA vai para a pose padrão antes de todo clique posicional, que é a
    mesma exigência da BC;
  * a VENDA não usa a coordenada da BC para o link, porque foi medido que ela
    não transfere.
"""
import pathlib

import cv2
import pytest

from blazesbot.bot.hh import entrada, mapa_hh, vendedor
from blazesbot.core.coords import coords_for_size

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = RAIZ / "data" / "templates"
EVIDENCIA = TEMPLATES / "entrada"


# ===========================================================================
# OS TEMPLATES
# ===========================================================================

# (arquivo, o que é, largura e altura máximas plausíveis para um recorte)
RECORTES = [
    (entrada.LINK_WEST_SUBURB, "o link West Suburb of Stone City", 300, 40),
    (entrada.LINK_ENTRAR_HH, "o link Enter Happiness Hall", 300, 40),
    (entrada.LINK_SAIR_HH, "o link Leave Happiness Hall", 300, 40),
    ("dialogo_seta_baixo.png", "a seta de rolagem do diálogo", 40, 40),
]


@pytest.mark.parametrize("arquivo,o_que,max_w,max_h", RECORTES,
                         ids=lambda v: v if isinstance(v, str) else "")
def test_o_template_existe_na_pasta_de_onde_o_codigo_carrega(
        arquivo, o_que, max_w, max_h):
    """`TemplateLibrary` aponta para `data/templates/`, não para `entrada/`.

    `entrada/` é a pasta de EVIDÊNCIA -- prints completos que provam de onde
    cada recorte saiu. Um template deixado só lá é um template que o bot não
    encontra, e a falha aparece como "a HH não entra" sem mais explicação.
    """
    assert (TEMPLATES / arquivo).exists(), (
        f"falta {arquivo} ({o_que}) em data/templates/")


@pytest.mark.parametrize("arquivo,o_que,max_w,max_h", RECORTES,
                         ids=lambda v: v if isinstance(v, str) else "")
def test_o_template_e_um_RECORTE_e_nao_uma_tela(arquivo, o_que, max_w, max_h):
    """O primeiro `link_enter_hh.png` entregue era a TELA INTEIRA (1029x804).

    Um template do tamanho da tela casa com escore alto em qualquer lugar e não
    localiza nada -- `find_template` devolveria sempre o mesmo ponto, o canto.
    O teste não sabe se o recorte está CERTO; ele sabe que uma tela inteira está
    errada, e é essa a confusão que aconteceu.
    """
    img = cv2.imread(str(TEMPLATES / arquivo))
    assert img is not None, f"{arquivo} não abre como imagem"
    h, w = img.shape[:2]
    assert w <= max_w and h <= max_h, (
        f"{arquivo} tem {w}x{h} -- isso é uma tela, não um recorte de {o_que}")


def test_a_evidencia_de_cada_recorte_esta_guardada():
    """Print completo junto do recorte. Sem ele, refazer um template daqui a
    seis meses é procurar a tela de novo no jogo."""
    for nome in ("completa1.png", "completa2.png"):
        assert (EVIDENCIA / nome).exists(), f"falta a evidência {nome}"
        img = cv2.imread(str(EVIDENCIA / nome))
        assert img.shape[1] > 900, "a evidência tem que ser a tela inteira"


def test_o_link_de_vender_AINDA_falta_e_o_bot_sabe_disso():
    """ESTE TESTE VAI FALHAR DE PROPÓSITO quando o recorte chegar.

    Quando isso acontecer, apague este teste e acrescente `link_sell_item.png`
    à lista `RECORTES` acima. O marcador existe para a ausência ser visível --
    sem ele, "a HH não vende" é um mistério.
    """
    existe = (TEMPLATES / vendedor.TEMPLATE_DO_LINK_DE_VENDER).exists()
    assert not existe, (
        f"{vendedor.TEMPLATE_DO_LINK_DE_VENDER} apareceu: mova-o para a lista "
        f"RECORTES e apague este teste")


# ===========================================================================
# O WAYPOINT DA PORTA
# ===========================================================================


def test_o_waypoint_da_porta_e_o_lido_no_print():
    """Medido em 03/09/2026: o rótulo de `completa2.png` diz
    `Black Wind Camp Dungeon [-342,-288]`."""
    assert mapa_hh.PONTO_DA_ENTRADA == (-342, -288)


def test_o_waypoint_medido_concorda_com_o_do_bot_em_lua():
    """`hh.lua` usa `entrance = {-342, -286}` e roda hoje em produção.

    Duas fontes independentes a 2 unidades uma da outra. É a confirmação mais
    forte disponível sem remedir -- e se alguém mexer na constante, a
    discordância aparece aqui.
    """
    assert mapa_hh.distancia(mapa_hh.PONTO_DA_ENTRADA, (-342, -286)) <= 2


def test_a_venda_acontece_no_MESMO_ponto_da_porta():
    """O print mostra o vendedor logo abaixo do personagem e o NPC da cave logo
    acima, na escada. Um waypoint serve para as duas coisas."""
    assert mapa_hh.PONTO_DA_VENDA == mapa_hh.PONTO_DA_ENTRADA


def test_os_dois_pontos_tem_NOMES_separados():
    """Se o clique no vendedor começar a cair no chão, é `PONTO_DA_VENDA` que se
    remede -- e isso não pode mexer na entrada, que já tem duas fontes."""
    fonte = (RAIZ / "blazesbot" / "bot" / "hh" / "mapa_hh.py").read_text(
        encoding="utf-8")
    assert "PONTO_DA_VENDA = PONTO_DA_ENTRADA" in fonte


def test_happiness_hall_e_o_nome_da_instancia_e_nao_do_lugar():
    """`HH` = Happiness Hall, lido no link do diálogo. A ZONA é outra coisa:
    `Black Wind Camp Dungeon`, que é o que a memória devolve."""
    assert mapa_hh.NOME_DA_INSTANCIA == "Happiness Hall"
    assert mapa_hh.LUGAR_FORA_DA_HH == "Black Wind Camp Dungeon"
    assert mapa_hh.NOME_DA_INSTANCIA != mapa_hh.LUGAR_FORA_DA_HH


# ===========================================================================
# A CÂMERA
# ===========================================================================

# (o que é, o módulo, o método) -- todo lugar que faz clique posicional
ONDE_A_CAMERA_IMPORTA = [
    ("o preparo da run", "routine", "_do_preparar"),
    ("cada trecho de waypoints", "routine", "_do_ate_o_boss"),
    ("a ida da Fada até a porta", "fada", "ir_para_a_porta"),
    ("a ida ao vendedor", "vendedor", "ir_ate_o_vendedor"),
]


@pytest.mark.parametrize("o_que,modulo,metodo", ONDE_A_CAMERA_IMPORTA,
                         ids=lambda v: v if isinstance(v, str) else "")
def test_a_camera_vai_para_a_pose_padrao_antes_do_clique(o_que, modulo, metodo):
    """A MESMA exigência da BC, e o bot em Lua também sabia disso.

    Ele chamava `setCamera(380, 0, 40)` no começo de cada run. Todo clique de
    NPC e de minimapa deste ecossistema é POSICIONAL na cena 3D: com a câmera
    fora do padrão, a coordenada certa aponta para o lugar errado.

    A diferença contra o Lua é COMO: aqui a pose é lida da memória e conferida
    (`Memory.camera_na_pose_certa`), em vez de escrita às cegas sobre um
    ponteiro resolvido no início do script -- que é o vício condenado em
    `docs/decisoes/hh.md`, item N.
    """
    import importlib
    import inspect
    import textwrap

    mod = importlib.import_module(f"blazesbot.bot.hh.{modulo}")
    dono = next(v for _n, v in vars(mod).items()
                if isinstance(v, type) and hasattr(v, metodo))
    fonte = textwrap.dedent(inspect.getsource(getattr(dono, metodo)))
    assert "apply_camera" in fonte, f"{o_que}: a câmera não é ajustada"


# ===========================================================================
# A VENDA
# ===========================================================================


def test_o_ponto_do_vendedor_da_HH_e_o_medido():
    """Medido pelo usuário em 03/09/2026, com o personagem no waypoint da porta:
    clique direito em (475,450) abre o diálogo do Roaming Apothecary."""
    c = coords_for_size(1024, 768)
    assert c.hh_vendor_npc == (475, 450)


def test_o_ponto_do_vendedor_da_HH_nao_e_o_da_BC():
    """São NPCs diferentes, em lugares diferentes. Um ponto para os dois seria
    um clique no chão em um deles -- e clique no chão faz o personagem andar."""
    c = coords_for_size(1024, 768)
    assert c.hh_vendor_npc != c.vendor_npc


def test_a_venda_da_HH_confere_a_POSICAO_antes_de_clicar():
    """O clique é posicional: só vale a partir de `PONTO_DA_VENDA`."""
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(
        vendedor.VendedorDaHH._no_ponto_do_vendedor))
    assert "PONTO_DA_VENDA" in fonte
    assert "position()" in fonte


def test_sem_leitura_de_posicao_a_venda_SEGUE(monkeypatch):
    """Recusar aqui travaria a venda num laço sem saída. Quem decide então é o
    diálogo abrir ou não -- e a abertura é conferida pela âncora da janela."""
    servico = object.__new__(vendedor.VendedorDaHH)

    class _Mem:
        @staticmethod
        def position():
            return None

    class _Ctx:
        memory = _Mem()

    servico.ctx = _Ctx()
    assert servico._no_ponto_do_vendedor() is True


def test_a_venda_da_HH_NAO_usa_a_coordenada_do_link_da_BC():
    """MEDIDO em 03/09/2026: o primeiro link do diálogo deste NPC fica em
    cliente (302,361), e o `vendor_sell_tab` da BC em (266,430).

    Os links ficam a ~34 px um do outro, e a posição do primeiro depende de
    quantas linhas o NPC escreve antes. O ponto da BC cai 35 px ABAIXO do
    "Sell Item" deste vendedor -- dentro da janela, então não faz o personagem
    andar, mas a venda nunca abre.
    """
    import inspect
    import textwrap

    fonte = textwrap.dedent(inspect.getsource(
        vendedor.VendedorDaHH._onde_clicar_no_link_de_vender))
    assert "vendor_sell_tab" not in fonte
    assert "find_template" in fonte


def test_sem_o_template_do_link_a_venda_RECUSA_e_diz_o_que_falta():
    """Melhor não vender do que clicar num ponto que não é o link: a bolsa
    continua cheia e o log diz exatamente o que fazer."""
    servico = object.__new__(vendedor.VendedorDaHH)
    servico._avisou_sem_template = False
    avisos = []

    class _Templates:
        @staticmethod
        def load(_nome):
            return None

    class _Log:
        @staticmethod
        def warning(msg, *args):
            avisos.append(msg % args if args else msg)

        @staticmethod
        def debug(*_a, **_k):
            pass

    class _Ctx:
        templates = _Templates()
        log = _Log()
        hwnd = 1

    servico.ctx = _Ctx()
    assert servico._onde_clicar_no_link_de_vender() is None
    assert avisos, "recusou em silêncio"
    assert vendedor.TEMPLATE_DO_LINK_DE_VENDER in avisos[0]
    assert "data/templates" in avisos[0]


def test_o_aviso_do_template_sai_UMA_vez():
    """A venda é tentada até 4 vezes por `_tentar_abrir_a_venda`; avisar em
    todas encheria o log."""
    servico = object.__new__(vendedor.VendedorDaHH)
    servico._avisou_sem_template = False
    avisos = []

    class _Ctx:
        class templates:
            @staticmethod
            def load(_n):
                return None

        class log:
            @staticmethod
            def warning(msg, *args):
                avisos.append(msg)

            @staticmethod
            def debug(*_a, **_k):
                pass

        hwnd = 1

    servico.ctx = _Ctx()
    for _ in range(5):
        servico._onde_clicar_no_link_de_vender()
    assert len(avisos) == 1


def test_a_BC_continua_usando_a_coordenada_dela():
    """A promoção do vendedor não pode ter mudado o comportamento da BC."""
    import inspect
    import textwrap

    from blazesbot.bot.vendedor import JanelaDeVenda

    fonte = textwrap.dedent(inspect.getsource(
        JanelaDeVenda._onde_clicar_no_link_de_vender))
    assert "vendor_sell_tab" in fonte


def test_o_link_None_impede_o_clique():
    """`_tentar_abrir_a_venda` tem que RECUSAR, e não clicar em `None`."""
    import inspect
    import textwrap

    from blazesbot.bot.vendedor import JanelaDeVenda

    fonte = textwrap.dedent(inspect.getsource(
        JanelaDeVenda._tentar_abrir_a_venda))
    assert "_onde_clicar_no_link_de_vender()" in fonte
    i_pergunta = fonte.index("_onde_clicar_no_link_de_vender()")
    i_clique = fonte.index("_abrir_dialogo_e_clicar")
    assert i_pergunta < i_clique, "clicou antes de saber onde é o link"
    assert "is None" in fonte


def test_a_venda_da_HH_nao_gasta_item_de_retorno():
    """O Roaming Apothecary fica NO ponto da porta. A BC gasta pedra ou token
    para chegar no Rich Man; aqui isso seria desperdício."""
    import inspect

    fonte = inspect.getsource(vendedor)
    for proibido in ("voltar_para_a_cidade", "guild_token", "stone_charm"):
        assert proibido not in fonte, f"a venda da HH usa `{proibido}`"


def test_a_venda_da_HH_nao_abre_o_painel_de_arredores():
    """Não precisa: o vendedor está no waypoint. Abrir o painel para nada é a
    reclamação de 25/08/2026 sobre o Surroundings piscando na tela."""
    import inspect

    fonte = inspect.getsource(vendedor)
    assert "buscar_npc" not in fonte
    assert "trajeto_pelo_painel" not in fonte


# ===========================================================================
# A SAÍDA -- medida no print de 03/09/2026
# ===========================================================================


def test_o_NPC_da_saida_e_o_do_print():
    """O diálogo do ponto de saída se chama `Servant Child`.

    O texto é *"Don't beat me. I'm just a servant of here, if you want to leave
    here, I can help you..."*, e o link verde é "Leave Happiness Hall".
    """
    assert mapa_hh.NPC_DA_SAIDA == "Servant Child"


def test_o_ponto_de_saida_foi_REMEDIDO_para_a_montaria_nao_atrapalhar():
    """Era (529,119), o do bot em Lua. Passou a (527,124) em 04/09/2026.

    Motivo do usuário: dali a MONTARIA do personagem não fica na frente do NPC.
    O clique é posicional na cena 3D, então o ponto e o clique andam juntos --
    os dois foram remedidos no mesmo dia (ver `coords.hh_exit_npc`).
    """
    assert mapa_hh.PONTO_DA_SAIDA == (527, 124)
    assert [(w.x, w.y) for w in mapa_hh.CAMINHO_ATE_A_SAIDA] == [(527, 124)]


def test_sair_devolve_o_personagem_para_a_PORTA():
    """É o que faz a run seguinte começar sem viagem.

    O Lua confere pelo mesmo par (`farmer.exitCave`: `outside = {-342, -288}`).
    """
    assert mapa_hh.PONTO_FORA_DA_HH == mapa_hh.PONTO_DA_ENTRADA == (-342, -288)


def test_o_clique_no_NPC_da_saida_e_o_medido():
    """(626,526) na base 1024x768, remedido pelo usuário em 04/09/2026.

    Era (708,300), do ponto (529,119). Mudou junto com o ponto: com a montaria
    ativa o corpo dela entrava na frente do NPC naquele ângulo.
    """
    assert coords_for_size(1024, 768).hh_exit_npc == (626, 526)


def test_a_saida_NAO_clica_de_fora_do_ponto():
    """Clicar de longe abre o diálogo de OUTRO NPC que fica por perto.

    O personagem então caminha até ele, saindo do único ponto de onde o
    `Servant Child` é alcançável. Medido pelo usuário em 04/09/2026.
    """
    import inspect

    fonte = inspect.getsource(entrada.EntradaDaHH.tentar_sair_da_hh)
    assert "na_posicao_de_clicar" in fonte
    assert fonte.index("na_posicao_de_clicar") < fonte.index("falar_com_npc")


def test_a_precisao_da_saida_e_a_MESMA_da_porta():
    """Mesma pergunta, mesma régua -- e uma régua só evita divergência muda."""
    assert (mapa_hh.PRECISAO_NO_PONTO_DA_SAIDA
            == mapa_hh.PRECISAO_NO_PONTO_DA_ENTRADA)


def test_o_NPC_da_saida_nao_e_o_da_entrada_nem_o_do_vendedor():
    """Três NPCs, três pontos: um dentro da cave e dois do lado de fora."""
    c = coords_for_size(1024, 768)
    assert len({c.hh_exit_npc, c.hh_vendor_npc, c.npc_padrao}) == 3


def test_a_saida_usa_o_PADRAO_do_projeto_e_nao_os_tres_cliques_cegos():
    """O Lua dá três cliques direitos às cegas em alturas diferentes.

    Ele faz assim porque não sabe ler a tela (`farmer.exitCave`: 526,298 /
    524,325 / 529,361, depois um clique fixo em 301,382). Nós achamos o link
    por template -- e um clique que erra o NPC cai no chão, o que faz o
    personagem ANDAR para fora do ponto onde o NPC é alcançável.
    """
    import inspect

    fonte = inspect.getsource(entrada.EntradaDaHH.tentar_sair_da_hh)
    assert "clicar_link(LINK_SAIR_HH)" in fonte
    assert "hh_exit_npc" in fonte
    for cego in ("526, 298", "524, 325", "529, 361", "301, 382"):
        assert cego not in fonte
