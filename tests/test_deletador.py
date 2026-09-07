"""O deletador de itens do ecossistema APP.

O que estes testes protegem, em ordem de importância — **deletar não tem
desfazer**:

  1. SÓ SE APAGA DENTRO DAS REGIÕES DE BOLSA. Fora delas está o equipamento em
     uso, e as bags `Expired`/`Unactivated`, que mostram itens mas não deixam
     mexer.
  2. TODOS os modelos da pasta entram, e a pasta é RELIDA a cada chamada.
  3. O TETO DE 10 s corta, e corta ENTRE exclusões — nunca no meio de uma.
  4. A FILA retoma de onde parou, senão os últimos modelos nunca são olhados.
  5. O MESMO SLOT não é clicado duas vezes.
  6. Sem a caixa de confirmação na tela, o Ok NÃO é clicado.
"""



import pytestfrom blazesbot.bot.app import deletador as dfrom blazesbot.core import teclado_mudo@pytest.fixture(autouse=True)
def _fila_limpa():
    d.esquecer_a_fila()
    yield
    d.esquecer_a_fila()


# ===========================================================================
# A peneira dos modelos
# ===========================================================================


def test_TODOS_os_modelos_da_pasta_entram():
    """Decisão do usuário: nenhuma peneira por tamanho.

    A peneira antiga (`lado >= 24`) removia 125 dos 206 — e medido, **93 deles
    eram o ÚNICO modelo daquele item**, ou seja ela removia COBERTURA e não
    redundância. Se alguém a reintroduzir, este teste reprova.
    """
    na_pasta = sorted(d.PASTA_DO_LIXO.glob("*.png"))
    assert na_pasta, "a pasta de modelos sumiu"
    assert d.modelos_na_pasta() == na_pasta


def test_a_pasta_e_RELIDA_a_cada_chamada(tmp_path, monkeypatch):
    """Acrescentar um modelo tem que valer sem reiniciar o bot.

    A versão anterior guardava a lista para sempre (precisava abrir cada
    arquivo para medir o lado). Sem a peneira, não há o que guardar.
    """
    monkeypatch.setattr(d, "PASTA_DO_LIXO", tmp_path)
    assert d.modelos_na_pasta() == []
    (tmp_path / "novo.png").write_bytes(b"x")
    assert [p.name for p in d.modelos_na_pasta()] == ["novo.png"]
    (tmp_path / "outro.png").write_bytes(b"x")
    assert len(d.modelos_na_pasta()) == 2


def test_a_lista_branca_e_a_pasta_e_so_ela():
    """O que não tem modelo na pasta NUNCA é apagado. Pôr um PNG ali é
    autorizar; tirar é revogar."""
    assert d.PASTA_DO_LIXO.name == "deletar"
    assert d.PASTA_DO_LIXO.parent.name == "templates"


# ===========================================================================
# A fila que retoma
# ===========================================================================


def test_a_fila_comeca_do_zero():
    assert d.ordem_da_fila(list("abcde"), 0) == list("abcde")


def test_a_fila_retoma_de_onde_parou():
    """O teto de 10 s pode acabar antes de todos os modelos serem verificados;
    os que sobraram vêm PRIMEIRO na chamada seguinte."""
    assert d.ordem_da_fila(list("abcde"), 3) == list("deabc")


def test_a_fila_da_a_volta_sem_estourar():
    assert d.ordem_da_fila(list("abc"), 7) == list("bca")
    assert d.ordem_da_fila([], 3) == []


def test_a_fila_cobre_todos_os_modelos_em_algumas_voltas():
    """A propriedade que importa: nenhum modelo fica para trás para sempre."""
    nomes = list("abcdefghij")
    vistos, cursor = set(), 0
    for _ in range(5):                     # 5 chamadas, 3 modelos por chamada
        ordem = d.ordem_da_fila(nomes, cursor)[:3]
        vistos.update(ordem)
        cursor += 3
    assert vistos == set(nomes)


# ===========================================================================
# O mesmo slot não é clicado duas vezes
# ===========================================================================


def test_casamentos_colados_sao_o_mesmo_item():
    """Dois modelos parecidos podem casar no mesmo slot. Clicar de novo ali
    apagaria o item que ENTROU no lugar do primeiro."""
    assert d._sao_o_mesmo_item((100, 200), (104, 203))
    assert not d._sao_o_mesmo_item((100, 200), (140, 200))


# ===========================================================================
# O teto de tempo
# ===========================================================================


class _Conta:
    """Só o `login`, que é a CHAVE da fila de templates.

    A fila deixou de ser um contador único do módulo e passou a ser um por
    conta (`deletador._estado_das_filas[login]`) -- sem isso, cinco contas
    rodando juntas dividiriam o mesmo cursor e cada uma pularia os templates
    que a outra tinha acabado de verificar.
    """

    login = "conta-de-teste"


class _Ctx:
    """Dublê mínimo: conta cliques e teclas, e não toca em jogo nenhum."""

    def __init__(self, relogio):
        self.cliques = []
        self.log = _Log()
        self.hwnd = 1
        self.account = _Conta()
        self._relogio = relogio

    def click(self, ponto):
        self.cliques.append(ponto)

    def press(self, tecla):
        self.cliques.append(("tecla", tecla))

    def tick(self, s=0.2):
        self._relogio[0] += s

    def raise_if_stopped(self):
        pass


class _Log:
    """Dublê que GUARDA o que foi dito.

    Ele engolia tudo (`lambda: None`), e por isso nenhum teste conseguia
    cobrar um aviso -- justamente o que faltou nas 268 falhas de bolsa de
    06/09/2026, em que o log era a única coisa capaz de mostrar o defeito.
    """

    def __init__(self):
        self.linhas = []

    def __getattr__(self, nome):
        if nome.startswith("_"):
            raise AttributeError(nome)
        return lambda f, *a, **k: self.linhas.append(
            (nome, (f % a) if a else f))


def test_o_teto_corta_entre_exclusoes_e_nao_no_meio(monkeypatch):
    """Cortar depois do clique no ícone deixaria a caixa de confirmação aberta,
    e a macro voltaria a mandar tecla por cima dela."""
    relogio = [0.0]
    monkeypatch.setattr(d.time, "perf_counter", lambda: relogio[0])

    ctx = _Ctx(relogio)
    # cada exclusão gasta 3 s de relógio falso
    def apagar(_ctx, item, icone):
        relogio[0] += 3.0
        return True

    monkeypatch.setattr(d, "_apagar_um", apagar)
    monkeypatch.setattr(d, "_carregar", lambda ctx: {f"m{i}": object()
                                                    for i in range(5)})
    monkeypatch.setattr(d, "_achar_icone", lambda ctx, q: (500, 700))
    monkeypatch.setattr(d.vision, "capture_window", lambda h: object())
    monkeypatch.setattr(d.vision, "frame_is_blank", lambda q: False)
    # Cada modelo casa num SLOT DIFERENTE — senão o dedup de "mesmo item"
    # barraria do segundo em diante e o teste mediria outra coisa.
    slot = [0]

    def casamentos(*a, **k):
        slot[0] += 1
        return [(slot[0] * 40, 100)]

    monkeypatch.setattr(d, "regioes_visiveis",
                        lambda ctx, q: [("bolsa", (0, 0, 400, 400))])
    monkeypatch.setattr(d, "_casamentos_nas_regioes",
                        lambda q, tpl, reg: casamentos())

    apagados = d.deletar_lixo(ctx, teto_segundos=10.0)

    # QUATRO, e não três — e a diferença É a regra. O teto é conferido ANTES de
    # cada exclusão, então a que começa aos 9 s tem direito de terminar (acaba
    # aos 12). É isso que significa "não cortar no meio de uma": cortar aos 10
    # deixaria a caixa de confirmação aberta na tela, e a macro voltaria a
    # mandar tecla por cima dela.
    #
    #   t=0 -> apaga (t=3) -> apaga (t=6) -> apaga (t=9) -> apaga (t=12) -> para
    assert apagados == 4
    # O estouro é de NO MÁXIMO uma exclusão além do teto.
    assert relogio[0] <= 10.0 + 3.0


def test_sem_o_icone_nao_clica_em_nada(monkeypatch):
    """Sem o ícone na tela o inventário não está aberto — e clicar às cegas
    dentro do jogo pode mover ou usar um item."""
    relogio = [0.0]
    monkeypatch.setattr(d.time, "perf_counter", lambda: relogio[0])
    ctx = _Ctx(relogio)
    monkeypatch.setattr(d.vision, "capture_window", lambda h: object())
    monkeypatch.setattr(d.vision, "frame_is_blank", lambda q: False)
    monkeypatch.setattr(d, "_achar_icone", lambda ctx, q: None)

    assert d.deletar_lixo(ctx) == 0
    assert ctx.cliques == []


def test_desligado_nao_faz_nada(monkeypatch):
    monkeypatch.setattr(d, "ATIVADO", False)
    ctx = _Ctx([0.0])
    assert d.deletar_lixo(ctx) == 0
    assert ctx.cliques == []


def test_sem_captura_nao_deleta(monkeypatch):
    ctx = _Ctx([0.0])
    monkeypatch.setattr(d.vision, "capture_window", lambda h: None)
    assert d.deletar_lixo(ctx) == 0
    assert ctx.cliques == []


def test_o_teto_de_exclusoes_segura_um_modelo_ruim(monkeypatch):
    """Um template ruim não pode esvaziar a bolsa."""
    relogio = [0.0]
    monkeypatch.setattr(d.time, "perf_counter", lambda: relogio[0])
    ctx = _Ctx(relogio)
    monkeypatch.setattr(d, "_apagar_um", lambda *a: True)
    monkeypatch.setattr(d, "_carregar", lambda ctx: {"ruim": object()})
    monkeypatch.setattr(d, "_achar_icone", lambda ctx, q: (500, 700))
    monkeypatch.setattr(d.vision, "capture_window", lambda h: object())
    monkeypatch.setattr(d.vision, "frame_is_blank", lambda q: False)
    monkeypatch.setattr(d, "regioes_visiveis",
                        lambda ctx, q: [("bolsa", (0, 0, 400, 400))])
    # 50 casamentos, bem espalhados para não caírem no dedup
    monkeypatch.setattr(d, "_casamentos_nas_regioes",
                        lambda *a: [(i * 40, 100) for i in range(50)])

    assert d.deletar_lixo(ctx, teto_segundos=999) == d.MAXIMO_DE_EXCLUSOES


def test_o_mesmo_slot_nao_e_apagado_duas_vezes(monkeypatch):
    relogio = [0.0]
    monkeypatch.setattr(d.time, "perf_counter", lambda: relogio[0])
    ctx = _Ctx(relogio)
    monkeypatch.setattr(d, "_apagar_um", lambda *a: True)
    monkeypatch.setattr(d, "_carregar",
                        lambda ctx: {"a": object(), "b": object()})
    monkeypatch.setattr(d, "_achar_icone", lambda ctx, q: (500, 700))
    monkeypatch.setattr(d.vision, "capture_window", lambda h: object())
    monkeypatch.setattr(d.vision, "frame_is_blank", lambda q: False)
    monkeypatch.setattr(d, "regioes_visiveis",
                        lambda ctx, q: [("bolsa", (0, 0, 400, 400))])
    # os dois modelos casam PRATICAMENTE no mesmo pixel: é um item só
    monkeypatch.setattr(d, "_casamentos_nas_regioes",
                        lambda *a: [(100, 100)])

    assert d.deletar_lixo(ctx, teto_segundos=999) == 1


# ===========================================================================
# A confirmação
# ===========================================================================


def test_sem_a_caixa_o_Ok_nao_e_clicado(monkeypatch):
    """Mesma lição do `_abrir_dialogo_e_clicar` do BC: clicar sem saber se a
    caixa está lá faz o clique cair dentro do inventário."""
    relogio = [0.0]
    monkeypatch.setattr(d.time, "perf_counter", lambda: relogio[0])
    ctx = _Ctx(relogio)
    monkeypatch.setattr(d, "_esperar_a_caixa", lambda ctx: None)

    assert d._apagar_um(ctx, (100, 100), (500, 700)) is False
    # clicou no item e no ícone, e PAROU: nada de Ok às cegas
    assert ctx.cliques == [(100, 100), (500, 700)]


def test_com_a_caixa_o_Ok_e_clicado_no_ponto_derivado(monkeypatch):
    relogio = [0.0]
    monkeypatch.setattr(d.time, "perf_counter", lambda: relogio[0])
    ctx = _Ctx(relogio)
    monkeypatch.setattr(d, "_esperar_a_caixa", lambda ctx: (439, 364))

    assert d._apagar_um(ctx, (100, 100), (500, 700)) is True
    assert ctx.cliques == [(100, 100), (500, 700), (439, 364)]


def test_a_ancora_do_Ok_veio_da_medicao():
    """(-76,+172) foi medido no print do usuário, a partir do CENTRO do
    template — a mesma convenção do "It's precious item"."""
    from blazesbot.core.coords import TEMPLATE_ANCHORS

    nome, deslocamentos = TEMPLATE_ANCHORS["delete_confirm"]
    assert nome == "state_delete_confirm.png"
    assert deslocamentos["ok"] == (-76, 172)


def test_os_templates_de_ui_existem():
    """Sem eles o deletador não sabe onde clicar, e a conferência não desenha."""
    from pathlib import Path

    for nome in ("state_delete_confirm.png", "btn_delete_item.png"):
        assert (Path("data") / "templates" / nome).is_file(), nome


# ===========================================================================
# SÓ ABAIXO DAS ABAS — a região deletável
# ===========================================================================


class _Templates:
    """Carrega template do disco EM CINZA, como o `TemplateLibrary.load` faz.

    Em cor o `matchTemplate` rejeita: `find_template` converte o quadro para
    cinza e exige que o modelo venha no mesmo formato.
    """

    def load(self, nome):
        from pathlib import Path        import cv2

        return cv2.imread(str(Path("data") / "templates" / nome),
                          cv2.IMREAD_GRAYSCALE)


class _CtxComTela(_Ctx):
    def __init__(self):
        super().__init__([0.0])
        self.templates = _Templates()


def _print_do_inventario():
    from pathlib import Path    import cv2

    caminho = Path("data") / "templates" / "entrada" / "inventario.jpg"
    if not caminho.is_file():
        pytest.skip("print de referência do inventário não está no repo")
    return cv2.imread(str(caminho))


def test_a_regiao_fica_ABAIXO_da_linha_de_abas():
    """A regra do usuário: só apaga o que está abaixo de Item/Quest/Arrange/Ext.

    O que está ACIMA é o equipamento em uso. O jogo não deixaria apagar, mas
    tentar gasta clique e espera dentro dos 10 s — e esse tempo é item de lixo
    que ficou na bolsa.
    """
    quadro = _print_do_inventario()
    regioes = d.regioes_visiveis(_CtxComTela(), quadro)
    assert regioes, "não achei a grade da bolsa no print de referência"

    _rotulo, (x, y, larg, alt) = regioes[0]
    # A linha de abas foi medida centrada em (665,466) neste print.
    assert y > 466, "a região começou ACIMA das abas — pegaria o equipamento"
    assert 200 < larg < 320 and 130 < alt < 240, f"região estranha: {larg}x{alt}"


def test_a_regiao_exclui_a_area_do_equipamento():
    """O boneco com o equipamento fica no TOPO da janela do inventário."""
    quadro = _print_do_inventario()
    regioes = d.regioes_visiveis(_CtxComTela(), quadro)
    _rotulo, (x, y, larg, alt) = regioes[0]
    # Um ponto no meio do boneco, medido no print: (650, 300).
    assert not (x <= 650 <= x + larg and y <= 300 <= y + alt)


def test_sem_a_linha_de_abas_nao_deleta_nada(monkeypatch):
    """Sem achar a grade, o desfecho seguro é não apagar coisa nenhuma."""
    ctx = _Ctx([0.0])
    monkeypatch.setattr(d.vision, "capture_window", lambda h: object())
    monkeypatch.setattr(d.vision, "frame_is_blank", lambda q: False)
    monkeypatch.setattr(d, "_achar_icone", lambda ctx, q: (500, 700))
    monkeypatch.setattr(d, "regioes_visiveis", lambda ctx, q: [])

    assert d.deletar_lixo(ctx) == 0
    assert ctx.cliques == []


def test_casar_na_regiao_devolve_coordenada_da_JANELA():
    """O recorte é relativo; o clique tem que sair em coordenada da janela.

    Errar isso poria todo clique deslocado pelo canto da região — em cima de
    outro item.
    """
    import numpy as np

    # RUÍDO, e não preto: `TM_CCOEFF_NORMED` sobre área uniforme é indefinido,
    # e o casamento sai em lugar aleatório — o teste mediria o acaso.
    rng = np.random.default_rng(7)
    quadro = rng.integers(0, 255, (300, 300, 3), dtype=np.uint8)
    modelo = quadro[150:160, 200:210].copy()
    achados = d._casamentos_nas_regioes(
        quadro, modelo, [("r", (100, 100, 150, 150))])
    assert achados, "não achou a marca dentro da região"
    x, y = achados[0]
    assert abs(x - 205) <= 2 and abs(y - 155) <= 2, (x, y)


# ===========================================================================
# AS BAGS EXTRAS — só as acessíveis
# ===========================================================================


def _print(nome):
    from pathlib import Path    import cv2

    caminho = Path("data") / "templates" / "entrada" / nome
    if not caminho.is_file():
        pytest.skip(f"{nome} não está no repo")
    return cv2.imread(str(caminho))


def test_duas_bags_Permanent_dao_DUAS_regioes():
    """A MESMA etiqueta aparece em mais de uma bag ao mesmo tempo.

    Com `find_template` (só o melhor) apenas uma seria varrida, e a outra nunca
    seria limpa. Este teste existe porque foi exatamente esse o defeito.
    """
    quadro = _print("bags_permanent.png")
    regioes = d.regioes_visiveis(_CtxComTela(), quadro)
    permanentes = [r for r in regioes if "Permanent" in r[0]]
    assert len(permanentes) == 2, [r[0] for r in regioes]


def test_a_bag_EXPIRED_fica_de_FORA_mesmo_cheia_de_itens():
    """O caso que decide a regra.

    No print, a Expand Bag 1 está `Expired` e MESMO ASSIM mostra os itens. Sem
    olhar a etiqueta, o bot gastaria clique e espera numa bag onde nada
    acontece — dentro de um teto de 10 s.
    """
    quadro = _print("bags_expired.png")
    regioes = d.regioes_visiveis(_CtxComTela(), quadro)
    rotulos = [r[0] for r in regioes]
    assert any("Limited" in r for r in rotulos), rotulos
    assert not any("Permanent" in r for r in rotulos), rotulos

    # A Expired foi medida centrada em (737,430); a grade dela desce dali.
    for _rot, (x, y, larg, alt) in regioes:
        assert not (y <= 470 <= y + alt and x <= 700 <= x + larg), (
            f"a região {_rot} invadiu a bag Expired")


def test_so_as_etiquetas_BOAS_sao_procuradas():
    """Procurar as boas (e não reconhecer a ruim) faz o padrão ser PRESERVAR.

    `Unactivated` e qualquer etiqueta que o jogo invente amanhã ficam de fora
    sozinhas. Reconhecer `Expired` para excluir teria a falha oposta: o que não
    estivesse na lista de exclusão seria varrido.
    """
    procurados = {r.template for r in d.REGIOES_DA_BOLSA}
    assert "state_bag_permanent.png" in procurados
    assert "state_bag_limited.png" in procurados
    assert not any("expired" in t.lower() or "unactiv" in t.lower()
                   for t in procurados)


def test_as_regioes_funcionam_em_OUTRA_resolucao():
    """A prova de que os templates não escalam com a resolução.

    Os outros prints são 1022x79x; este é **1439x1073**, e as mesmas âncoras
    acham as mesmas coisas. É a descoberta que abre o `core/coords.py` --
    a UI do jogo tem tamanho fixo em pixels, e mais resolução dá mais cenário,
    não elementos maiores. Se um dia isso deixar de valer, é aqui que aparece.

    Sobre a `Unactivated`: ela não precisa de teste próprio. A garantia é
    ESTRUTURAL -- só as etiquetas boas são procuradas (ver o teste acima), então
    nenhuma etiqueta desconhecida vira região, hoje ou amanhã.
    """
    quadro = _print("bag_unactivated.jpeg")
    assert quadro.shape[1] > 1400, "o print de outra resolução mudou"
    regioes = d.regioes_visiveis(_CtxComTela(), quadro)
    rotulos = [r[0] for r in regioes]
    assert any("principal" in r for r in rotulos), rotulos
    assert any("Limited" in r for r in rotulos), rotulos


# ===========================================================================
# ABRIR E FECHAR A BOLSA — a tecla é um INTERRUPTOR
# ===========================================================================


class _CtxTecla(_Ctx):
    """Dublê que registra teclas e finge um inventário que abre/fecha."""

    def __init__(self, aberto_no_inicio):
        super().__init__([0.0])
        self.aberto = aberto_no_inicio
        self.teclas = []

    def press(self, tecla):
        self.teclas.append(tecla)
        self.aberto = not self.aberto      # interruptor, como no jogo


def _preparar(monkeypatch, ctx):
    """Liga `inventario_esta_aberto` ao estado do dublê e neutraliza o resto."""
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: c.aberto)
    monkeypatch.setattr(d, "deletar_lixo", lambda c, teto=None: 7)


def test_bolsa_JA_ABERTA_nao_mexe_na_tecla(monkeypatch):
    """O pedido do usuário: já aberto, não abre nem fecha.

    Apertar aqui FECHARIA a bolsa, e aí não haveria o que apagar.
    """
    ctx = _CtxTecla(aberto_no_inicio=True)
    _preparar(monkeypatch, ctx)

    assert d.limpar_a_bolsa(ctx, "I") == 7
    assert ctx.teclas == [], "mexeu na tecla com a bolsa já aberta"
    assert ctx.aberto is True, "deixou a bolsa em outro estado"


def test_bolsa_FECHADA_abre_apaga_e_fecha(monkeypatch):
    ctx = _CtxTecla(aberto_no_inicio=False)
    _preparar(monkeypatch, ctx)

    assert d.limpar_a_bolsa(ctx, "I") == 7
    assert ctx.teclas == ["I", "I"], ctx.teclas
    assert ctx.aberto is False, "não devolveu a bolsa ao estado fechado"


def test_o_fechamento_e_CONFERIDO_e_insiste(monkeypatch):
    """Um 'fechar' que não pegou custa a noite inteira da macro: com a bolsa
    aberta, toda tecla do APP é engolida."""
    ctx = _CtxTecla(aberto_no_inicio=False)
    monkeypatch.setattr(d, "deletar_lixo", lambda c, teto=None: 0)

    # A primeira tentativa de fechar não pega; a segunda sim.
    #
    # A SEQUÊNCIA GANHOU DUAS LEITURAS EM 07/09/2026: o abrir passou a
    # PERGUNTAR pelo ícone em laço (`_esperar_a_bolsa_abrir`) e o `finally` só
    # fecha o que está observadamente aberto. São: (1) o estado inicial,
    # (2) a confirmação de que abriu, (3) a conferência do `finally`,
    # (4) o fechar que não pegou, (5) o fechar que pegou.
    estados = iter([False, True, True, True, False])
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: next(estados))

    d.limpar_a_bolsa(ctx, "I")
    assert ctx.teclas.count("I") == 3, ("abriu 1 + fechou 2", ctx.teclas)


def test_sem_leitura_da_tela_abre_e_fecha_como_antes(monkeypatch):
    """`None` não é "está aberto". Sem conferência, o desfecho seguro é o
    comportamento que existia antes de haver conferência nenhuma."""
    ctx = _CtxTecla(aberto_no_inicio=False)
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: None)
    monkeypatch.setattr(d, "deletar_lixo", lambda c, teto=None: 0)

    d.limpar_a_bolsa(ctx, "I")
    assert ctx.teclas, "sem leitura, não tentou nem abrir"


def test_sem_tecla_configurada_nao_faz_nada(monkeypatch):
    ctx = _CtxTecla(aberto_no_inicio=False)
    _preparar(monkeypatch, ctx)
    assert d.limpar_a_bolsa(ctx, "") == 0
    assert ctx.teclas == []


def test_falha_ao_apagar_ainda_FECHA_a_bolsa(monkeypatch):
    """O `finally` existe para isto: bolsa aberta esquecida mata a macro."""
    ctx = _CtxTecla(aberto_no_inicio=False)
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: c.aberto)

    def explode(c, teto=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(d, "deletar_lixo", explode)

    with pytest.raises(RuntimeError):
        d.limpar_a_bolsa(ctx, "I")
    assert ctx.aberto is False, "deixou a bolsa aberta depois de falhar"


# ---------------------------------------------------------------------------
# A BOLSA QUE NÃO ABRE -- 268 falhas seguidas em campo, 07/09/2026
# ---------------------------------------------------------------------------
#
# A espera era CEGA (0,58 s). Quando a tela demorava mais que isso, o ícone não
# era achado, a limpeza era descartada e o `finally` apertava a tecla de novo.
# Como a tecla é interruptor, os toques se anulavam em pares: duas contas
# passaram horas abrindo e fechando a bolsa sem apagar UM item.

def test_a_bolsa_que_demora_a_pintar_AINDA_e_limpa(monkeypatch):
    """O conserto em uma linha: pergunta em vez de esperar cego."""
    ctx = _CtxTecla(aberto_no_inicio=False)
    apagados = []
    monkeypatch.setattr(d, "deletar_lixo",
                        lambda c, teto=None: apagados.append(1) or 3)
    # Fechada, fechada, fechada... e só na quarta leitura ela aparece.
    estados = iter([False, False, False, True, True, False])
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: next(estados))

    assert d.limpar_a_bolsa(ctx, "I") == 3
    assert apagados == [1], "desistiu de uma bolsa que abriu atrasada"


def test_a_bolsa_que_NAO_abre_no_teto_nao_aperta_de_novo(monkeypatch):
    """O furo que o council apontou: o `finally` apertava a tecla
    incondicionalmente. Sem o ícone na tela, o que se SABE é que ela não está
    aberta -- e o que não está aberto não precisa ser fechado."""
    ctx = _CtxTecla(aberto_no_inicio=False)
    monkeypatch.setattr(d, "deletar_lixo", lambda c, teto=None: 0)
    monkeypatch.setattr(d, "TETO_DA_BOLSA_ABRIR", 0.05)
    monkeypatch.setattr(d, "PASSO_DA_BOLSA_ABRIR", 0.0)
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: False)

    # `BOLSA_NAO_ABRIU` e não `0` -- 07/09/2026. Os dois eram zero, e o zero
    # calado deixou a tecla de inventário sem poder depor como SEGUNDA
    # testemunha do teclado mudo (ver `core/teclado_mudo.py`).
    assert d.limpar_a_bolsa(ctx, "I") == teclado_mudo.BOLSA_NAO_ABRIU

    assert ctx.teclas.count("I") == 1, ("apertou de novo numa bolsa que a tela "
                                        f"diz estar fechada: {ctx.teclas}")
    assert any("abrir atrasada" in t for _n, t in ctx.log.linhas), ctx.log.linhas


def test_a_bolsa_que_abre_DEPOIS_do_teto_ainda_e_fechada(monkeypatch):
    """Achado do Codex em 07/09/2026: zerar `eu_abri` no teto jogava fora o
    mecanismo que resolve o caso restante. A tecla SAIU; se a bolsa aparecer
    atrasada, ela ficaria aberta atrapalhando as voltas seguintes.

    Intenção não fecha bolsa; observação fecha.
    """
    ctx = _CtxTecla(aberto_no_inicio=False)
    monkeypatch.setattr(d, "deletar_lixo", lambda c, teto=None: 0)
    aberta = {"v": False}
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: aberta["v"])

    def esperar_e_abrir_atrasado(_ctx):
        """Estourou o teto -- e a bolsa aparece um instante DEPOIS."""
        aberta["v"] = True
        return False

    monkeypatch.setattr(d, "_esperar_a_bolsa_abrir", esperar_e_abrir_atrasado)

    d.limpar_a_bolsa(ctx, "I")

    # 1 para abrir + ao menos 1 para fechar. (O dublê nunca diz "fechou", então
    # `_fechar_a_bolsa` insiste até o limite dele -- e é isso que se quer: a
    # bolsa aberta atrapalha as voltas seguintes.)
    assert ctx.teclas.count("I") >= 2, ("abriu 1 e tinha de FECHAR a que abriu "
                                        f"atrasada: {ctx.teclas}")


def test_o_finally_NAO_fecha_o_que_a_tela_diz_estar_fechado(monkeypatch):
    """`eu_abri` diz o que eu tentei; a tela diz o que É. Entre os dois, manda a
    tela -- senão o "fechar" vira um "abrir"."""
    ctx = _CtxTecla(aberto_no_inicio=False)
    monkeypatch.setattr(d, "deletar_lixo", lambda c, teto=None: 0)
    # abriu (True na confirmação), mas na hora de fechar já está fechada.
    estados = iter([False, True, False])
    monkeypatch.setattr(d, "inventario_esta_aberto", lambda c: next(estados))

    d.limpar_a_bolsa(ctx, "I")

    assert ctx.teclas.count("I") == 1, ("abriu 1 e NÃO devia fechar: "
                                        f"{ctx.teclas}")


def test_a_espera_do_abrir_deixou_de_ser_CEGA():
    """Trava estrutural: se alguém devolver o `tick` fixo no caminho do abrir,
    o defeito das 268 falhas volta."""
    import inspect

    fonte = inspect.getsource(d.limpar_a_bolsa)
    assert "_esperar_a_bolsa_abrir" in fonte
    assert "ESPERA_DA_BOLSA_ABRIR" not in fonte
