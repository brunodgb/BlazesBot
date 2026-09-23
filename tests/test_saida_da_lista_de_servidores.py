"""A LISTA DE SERVIDORES TEM SAÍDA: o Cancel.

Relato do usuário (22/09/2026): *"já aconteceu do servidor reiniciar e, como
não entra, fica travado nessa tela específica de escolha de servidor"*.

Era o único ponto do login em que insistir não adiantava e sair não acontecia
sozinho:

  * servidor FORA DA LISTA -> `_do_server` levantava `LoginError` direto, e o
    supervisor voltava PARA A MESMA JANELA, que continua na lista. Mesmo erro,
    para sempre.
  * servidor OFFLINE ou reiniciando -> o Ok não faz nada. A tela continua
    `SERVER_LIST`, o laço devolve a fase para `SERVER`, e `_do_server` clica de
    novo. Para sempre.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from blazesbot.bot.login import VOLTAS_NA_LISTA_DE_SERVIDORES, LoginSequence
from blazesbot.bot.login_states import LoginStateDetector, Phase
from blazesbot.core.coords import coords_for_size


class _Detector:
    """Dublê do detector -- com o método REAL de ler o status, que é o que os
    testes do status exercitam."""

    servidor_offline = LoginStateDetector.servidor_offline
    _modelo_do_servidor = LoginStateDetector._modelo_do_servidor
    sabe_reconhecer = LoginStateDetector.sabe_reconhecer
    linha_do_servidor = LoginStateDetector.linha_do_servidor
    # Biblioteca que nunca acha nada: o status fica ILEGIVEL, que e o
    # caso cego -- os testes do Offline injetam a resposta que querem.
    templates = type("_Sem", (), {"load": staticmethod(lambda _n: None)})()

    def detect(self):
        return type("D", (), {"capture_ok": False, "frame": None})()

    def find_button(self, *a, **k):
        return None


def _login(servidor: str) -> LoginSequence:
    """Uma `LoginSequence` sem `__init__` -- só o que `_do_server` toca."""
    seq = object.__new__(LoginSequence)
    seq.coords = coords_for_size(1024, 768)
    seq.account = type("_Conta", (), {"server": servidor})()
    seq.log = __import__("logging").getLogger("teste.servidor")
    seq.detector = _Detector()
    seq.voltas_no_servidor = 0
    seq.phase = Phase.SERVER
    seq.cliques: list[tuple[int, int]] = []
    seq.fases: list[Phase] = []
    seq._click = lambda ponto: seq.cliques.append(ponto)
    seq._set_phase = lambda fase: seq.fases.append(fase)
    seq._abort_if_stopped = lambda: None
    # A espera pelo servidor fora do ar é de 30 s DE VERDADE; aqui só o
    # desfecho interessa.
    seq.esperas = []
    seq._esperar = lambda seg: seq.esperas.append(seg)
    return seq


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr("blazesbot.bot.login.sleep", lambda _s: None)


def test_servidor_FORA_DA_LISTA_sai_pelo_cancel_em_vez_de_levantar():
    """O `LoginError` seco deixava a janela parada na lista para sempre."""
    seq = _login("Servidor Que Nao Existe")
    seq._do_server()

    assert seq.cliques == [seq.coords.server_cancel], (
        "não clicou no Cancel — a conta fica presa na lista")
    assert seq.fases == [Phase.CREDENTIALS], (
        "não voltou para o login; o ciclo não recomeça")


def test_o_Ok_QUE_NAO_SAI_da_lista_acaba_no_cancel():
    """É o sintoma do servidor Offline e do que reiniciou -- o único que dá
    para medir sem template novo."""
    seq = _login("Light in the Darkness")

    for _ in range(VOLTAS_NA_LISTA_DE_SERVIDORES):
        seq._do_server()
    assert seq.coords.server_cancel not in seq.cliques, (
        "desistiu cedo demais — clique engolido é comum nesta UI")
    assert seq.fases[-1] is Phase.ENTERING

    seq._do_server()
    assert seq.cliques[-1] == seq.coords.server_cancel
    assert seq.fases[-1] is Phase.CREDENTIALS


def test_o_servidor_bom_entra_sem_passar_pelo_cancel():
    """A saída de emergência não pode atrapalhar o caminho normal."""
    seq = _login("Light in the Darkness")
    seq._do_server()

    assert seq.cliques[-1] == seq.coords.server_ok
    assert seq.coords.server_cancel not in seq.cliques
    assert seq.fases == [Phase.ENTERING]


def test_o_cancel_fica_a_direita_do_Ok_na_mesma_altura():
    """Medido no print 1:1 de 22/09/2026: Ok em x=557, Cancel em x=669.

    A folga é o próprio botão, que tem 57 px de largura
    (`data/templates/cancel.bmp`).
    """
    c = coords_for_size(1024, 768)
    assert c.server_cancel[1] == c.server_ok[1]
    assert c.server_cancel[0] - c.server_ok[0] == 112


# ===========================================================================
# O STATUS DA LINHA -- "Offline" lido por template, com a margem medida
# ===========================================================================


def test_o_template_do_offline_separa_das_linhas_ONLINE():
    """A medição que autoriza o limiar, contra o print 1:1 de 22/09/2026.

    `tests/dados/status_da_lista_de_servidores.png` é o recorte REAL da coluna
    "Server Status" das quatro linhas: três Online e, na quarta (selecionada,
    fundo azul do realce), o Offline.

    Sem esta margem o limiar seria chute, e o projeto não aceita chute.
    """
    from pathlib import Path

    import cv2

    from blazesbot.bot.login_states import LIMIAR_DO_OFFLINE, TEMPLATE_SERVIDOR_OFFLINE
    from blazesbot.core.vision import TemplateLibrary

    modelo = TemplateLibrary(Path("data") / "templates").load(
        TEMPLATE_SERVIDOR_OFFLINE)
    if modelo is None:
        # `data/` não é versionado (guarda o config.json com as senhas), então o
        # template é local como todos os outros. Onde ele existe, a medição é
        # cobrada; onde não existe, não há o que medir.
        pytest.skip("data/templates/estado/server_offline.png ausente")

    recorte = cv2.imread(str(Path("tests") / "dados"
                             / "status_da_lista_de_servidores.png"))
    assert recorte is not None
    cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)

    # O recorte começa em y=237 da área de cliente; as linhas ficam a cada 20 px
    # a partir de y=247. Índice 3 é o Offline.
    notas = []
    for indice in range(4):
        y = (247 + indice * 20) - 237
        faixa = cinza[max(0, y - 10):y + 10, :]
        r = cv2.matchTemplate(faixa, modelo, cv2.TM_CCOEFF_NORMED)
        notas.append(float(cv2.minMaxLoc(r)[1]))

    online = notas[:3]
    offline = notas[3]
    assert offline >= 0.99, f"a linha Offline caiu para {offline:.3f}"
    assert max(online) <= 0.80, (
        f"uma linha Online subiu para {max(online):.3f} — o limiar deixa de "
        f"separar")
    assert min(LIMIAR_DO_OFFLINE - max(online), offline - LIMIAR_DO_OFFLINE) > 0.05, (
        f"o limiar {LIMIAR_DO_OFFLINE} ficou colado numa das populações "
        f"(Online {max(online):.3f}, Offline {offline:.3f})")


def test_servidor_OFFLINE_sai_pelo_cancel_sem_esperar_as_voltas():
    """Offline é fato lido na tela, não sintoma: sai na primeira passada."""
    seq = _login("Light in the Darkness")
    seq.detector.servidor_offline = lambda *a, **k: True

    seq._do_server()

    assert seq.cliques[-1] == seq.coords.server_cancel
    assert seq.coords.server_ok not in seq.cliques, (
        "clicou no Ok de um servidor que já sabia estar Offline")
    assert seq.fases == [Phase.CREDENTIALS]


def test_status_ILEGIVEL_nao_cancela_sozinho():
    """Não saber não é motivo para derrubar: quem cobre o caso cego é a
    contagem de voltas."""
    seq = _login("Light in the Darkness")
    assert seq.detector.servidor_offline(None, (345, 247), 3) is False


def test_o_relogio_das_telas_iniciais_NAO_desliga_com_a_lista_na_tela():
    """A causa raiz do "nem para frente nem para trás".

    `Detection.connected` é só "o servidor está no título", e o cliente põe o
    nome no título quando a LINHA É ESCOLHIDA -- não quando se entra. O print de
    22/09/2026 mostra o título "Talisman Online | Light in the Darkness |
    ver.6401" COM a lista de servidores aberta.

    Desligar o relógio ali tirava o último prazo de uma conta parada na lista.
    """
    import inspect

    from blazesbot.bot.login import LoginSequence

    fonte = inspect.getsource(LoginSequence.run)
    assert "det.connected and not na_lista_de_servidores" in fonte, (
        "o relógio das telas iniciais voltou a desligar só por ter o servidor "
        "no título — a conta parada na lista fica sem prazo nenhum")


# ===========================================================================
# SEM PROVA DA LINHA, NÃO SE APERTA O Ok -- 22/09/2026
# ===========================================================================
#
# Relato com print: a lista mostrava TRÊS servidores e o da conta não estava
# entre eles. O bot clicou em Ok assim mesmo e ENTROU EM OUTRO SERVIDOR.
#
# `Coords.server_rows` é uma lista ESTÁTICA -- o bot nunca leu quais servidores
# a tela mostra, só conta linhas a partir do índice nela. Some um servidor e
# todos os índices abaixo deslocam: o clique cai em linha vazia, o realce não
# muda, e o Ok confirma o que já estava selecionado.
#
# `find_highlighted_row` JÁ SABIA ("está selecionado 'X' em vez de 'Y'"). O
# defeito era o desfecho: avisar e apertar o Ok mesmo assim.


class _DetectorQueEnxerga(_Detector):
    """Captura funcionando, e o realce onde o teste mandar."""

    linha_realcada = 0

    def detect(self):
        return type("D", (), {"capture_ok": True, "frame": object()})()


def _login_que_enxerga(servidor: str, linha_realcada: int) -> LoginSequence:
    seq = _login(servidor)
    seq.detector = _DetectorQueEnxerga()
    seq.detector.linha_realcada = linha_realcada
    return seq


def _det_com_quadro():
    """O `Detection` que o laço entrega ao `_do_server` -- com QUADRO.

    Desde 23/09/2026 o `_do_server` não captura mais por conta própria: ele usa
    o quadro do laço, porque a segunda captura pode falhar sozinha.
    """
    return type("D", (), {"capture_ok": True, "frame": object(),
                          "connected": False})()


def test_linha_ERRADA_realcada_cancela_em_vez_de_apertar_Ok(monkeypatch):
    """O servidor saiu da lista: os índices deslocam e o realce fica em outro."""
    seq = _login_que_enxerga("Light in the Darkness", linha_realcada=0)
    monkeypatch.setattr("blazesbot.bot.login.find_highlighted_row",
                        lambda *a, **k: 0)

    seq._do_server()

    assert seq.coords.server_ok not in seq.cliques, (
        "apertou Ok sem a linha certa realçada — entra em OUTRO servidor")
    assert seq.cliques[-1] == seq.coords.server_cancel
    assert seq.fases == [Phase.CREDENTIALS]


def test_NENHUMA_linha_realcada_tambem_cancela(monkeypatch):
    seq = _login_que_enxerga("Light in the Darkness", linha_realcada=-1)
    monkeypatch.setattr("blazesbot.bot.login.find_highlighted_row",
                        lambda *a, **k: None)

    seq._do_server()

    assert seq.coords.server_ok not in seq.cliques
    assert seq.cliques[-1] == seq.coords.server_cancel


def test_a_linha_CERTA_realcada_segue_para_o_Ok(monkeypatch):
    seq = _login_que_enxerga("Light in the Darkness", linha_realcada=4)
    monkeypatch.setattr("blazesbot.bot.login.find_highlighted_row",
                        lambda *a, **k: seq.coords.server_index(
                            "Light in the Darkness"))

    seq._do_server()

    assert seq.cliques[-1] == seq.coords.server_ok
    assert seq.coords.server_cancel not in seq.cliques


def test_SEM_CAPTURA_segue_com_o_Ok_como_sempre():
    """Cancelar por não enxergar trocaria um erro raro por um permanente: numa
    máquina sem captura a conta nunca conseguiria logar."""
    seq = _login("Light in the Darkness")   # o dublê padrão não captura
    seq._do_server()

    assert seq.cliques[-1] == seq.coords.server_ok
    assert seq.coords.server_cancel not in seq.cliques


# ===========================================================================
# A LINHA VEM DA TELA -- não do índice na lista estática (22/09/2026)
# ===========================================================================
#
# `Coords.server_rows` tem CINCO nomes; a tela mostrou quatro num print e três
# noutro. Contar linhas a partir da lista estática põe a conta em OUTRO
# servidor -- e foi o que aconteceu.
#
# As fixtures são recortes REAIS dos dois prints, com nomes e status.


def _fixture(nome: str):
    import cv2

    caminho = Path("tests") / "dados" / nome
    img = cv2.imread(str(caminho))
    assert img is not None, f"fixture {nome} sumiu"
    return img


def _detector_real():
    from pathlib import Path as _P

    from blazesbot.core.vision import TemplateLibrary

    det = object.__new__(LoginStateDetector)
    det.templates = TemplateLibrary(_P("data") / "templates")
    return det


# As fixtures começam em y=237 da área de cliente, e as linhas ficam a cada
# 20 px a partir de 247 -- então a primeira linha está em y=10 do recorte, e a
# coluna de nomes começa em x=265.
PRIMEIRA_NA_FIXTURE = (345 - 265, 247 - 237)


def _pula_sem_templates(det):
    if not det.sabe_reconhecer("White Horse [NEW]"):
        pytest.skip("recortes dos servidores ausentes (data/ não é versionado)")


def test_acha_CADA_servidor_na_linha_certa_da_lista_de_quatro():
    det = _detector_real()
    _pula_sem_templates(det)
    img = _fixture("lista_com_4_servidores.png")

    esperado = {
        "White Horse [NEW]": 0,
        "Sky Ice (GSM&BI)": 1,
        "All Stars": 2,
        "Light in the Darkness": 3,   # índice 4 na lista ESTÁTICA
    }
    for nome, linha in esperado.items():
        assert det.linha_do_servidor(img, nome, PRIMEIRA_NA_FIXTURE, 5) == linha, (
            f"'{nome}' não foi achado na linha {linha}")


def test_o_servidor_AUSENTE_da_tela_devolve_None():
    """É o caso do print: a lista caiu para três e o da conta sumiu."""
    det = _detector_real()
    _pula_sem_templates(det)
    img = _fixture("lista_com_3_servidores.png")

    assert det.linha_do_servidor(
        img, "Light in the Darkness", PRIMEIRA_NA_FIXTURE, 5) is None, (
        "achou um servidor que não está na tela — o bot entraria em outro")
    # E os que estão continuam sendo achados, cada um na sua linha.
    for nome, linha in (("White Horse [NEW]", 0), ("Sky Ice (GSM&BI)", 1),
                        ("All Stars", 2)):
        assert det.linha_do_servidor(img, nome, PRIMEIRA_NA_FIXTURE, 5) == linha


def test_o_realce_AZUL_nao_atrapalha_o_reconhecimento():
    """Em cada print há uma linha selecionada, e é justamente onde o fundo muda.

    Medido: o mesmo template casa 1.000 no fundo preto e 0.971 no azul --
    `TM_CCOEFF_NORMED` normaliza o contraste, então não é preciso binarizar.
    """
    det = _detector_real()
    _pula_sem_templates(det)

    # 4.png: "White Horse [NEW]" está SELECIONADO na linha 0.
    img = _fixture("lista_com_3_servidores.png")
    assert det.linha_do_servidor(
        img, "White Horse [NEW]", PRIMEIRA_NA_FIXTURE, 5) == 0


def test_sem_recorte_do_nome_NAO_cancela_sozinho():
    """Quem não tem recorte cai no índice estático, como antes -- não saber não
    é motivo para derrubar o login."""
    det = _detector_real()
    assert det.sabe_reconhecer("Servidor Que Nunca Foi Recortado") is False
    assert det.linha_do_servidor(
        _fixture("lista_com_3_servidores.png"),
        "Servidor Que Nunca Foi Recortado", PRIMEIRA_NA_FIXTURE, 5) is None


def test_o_CLIQUE_vai_para_a_linha_que_a_TELA_mostra(monkeypatch):
    """O defeito inteiro num teste: a lista estática diz 4, a tela diz 3.

    `Coords.server_index("Light in the Darkness")` é 4 -- mas no print de
    22/09/2026 ele está na LINHA 3, porque "Tiger Fish (WW)" saiu da tela. O
    clique tem de ir na linha da TELA.
    """
    seq = _login_que_enxerga("Light in the Darkness", linha_realcada=3)
    seq.detector.sabe_reconhecer = lambda _n: True
    seq.detector.linha_do_servidor = lambda *a, **k: 3
    monkeypatch.setattr("blazesbot.bot.login.find_highlighted_row",
                        lambda *a, **k: 3)

    assert seq.coords.server_index("Light in the Darkness") == 4, (
        "a lista estática mudou; o teste perdeu o sentido")
    seq._do_server()

    altura = seq.coords.server_row_height
    y_da_linha_3 = seq.coords.server_first_row_y + 3 * altura
    y_da_linha_4 = seq.coords.server_first_row_y + 4 * altura
    clicou_em = [p[1] for p in seq.cliques]
    assert y_da_linha_3 in clicou_em, (
        f"não clicou na linha que a tela mostra (y={y_da_linha_3})")
    assert y_da_linha_4 not in clicou_em, (
        "clicou na linha do índice ESTÁTICO — é o clique que entrava em outro "
        "servidor")


def test_nome_RECONHECIVEL_mas_ausente_da_tela_cancela(monkeypatch):
    """Sei reconhecer e não achei: o servidor não está listado."""
    seq = _login_que_enxerga("Light in the Darkness", linha_realcada=0)
    seq.detector.sabe_reconhecer = lambda _n: True
    seq.detector.linha_do_servidor = lambda *a, **k: None

    seq._do_server(_det_com_quadro())

    assert seq.cliques == [seq.coords.server_cancel]
    assert seq.fases == [Phase.CREDENTIALS]


def test_o_nome_e_reconhecido_NOS_DOIS_ESTADOS_da_linha():
    """Cada servidor tem dois estados: selecionado (fundo azul) e não.

    O usuário apontou a inconsistência -- os recortes tinham saído de estados
    diferentes -- e mandou três prints da MESMA lista, cada um com uma seleção
    diferente. A medição respondeu: o estado **não importa** (margem +0.586 do
    selecionado contra +0.581 do não selecionado, 0.005 de diferença), porque
    `TM_CCOEFF_NORMED` normaliza o contraste.

    Este teste cobra isso: o MESMO template acha o servidor esteja a linha
    realçada ou não, nas três telas.
    """
    det = _detector_real()
    _pula_sem_templates(det)

    esperado = {"White Horse [NEW]": 0, "Sky Ice (GSM&BI)": 1, "All Stars": 2}
    for linha_selecionada in range(3):
        img = _fixture(f"lista_3_selecao_linha{linha_selecionada}.png")
        for nome, linha in esperado.items():
            achou = det.linha_do_servidor(img, nome, PRIMEIRA_NA_FIXTURE, 5)
            assert achou == linha, (
                f"com a linha {linha_selecionada} selecionada, '{nome}' foi "
                f"achado em {achou} e não em {linha}")


def test_o_recorte_tem_LARGURA_FIXA_e_a_busca_e_mais_larga():
    """O segundo achado da medição: recorte ajustado ao texto de cada nome dava
    pior acerto 0.971; largura fixa deu 0.999.

    E a busca precisa ser MAIOR que o recorte -- a janela deslizou 3 px entre os
    prints, e sem folga o template não teria onde casar.
    """
    from pathlib import Path as _P

    from blazesbot.bot.login_states import MEIA_LARGURA_DO_NOME
    from blazesbot.core.vision import TemplateLibrary

    lib = TemplateLibrary(_P("data") / "templates")
    larguras = set()
    for nome in ("White Horse [NEW]", "Sky Ice (GSM&BI)", "All Stars",
                 "Light in the Darkness"):
        slug = re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_")
        modelo = lib.load(f"servidor_{slug}.png")
        if modelo is None:
            pytest.skip("recortes ausentes (data/ não é versionado)")
        larguras.add(modelo.shape[1])

    assert len(larguras) == 1, (
        f"os recortes voltaram a ter larguras diferentes: {sorted(larguras)}")
    largura = larguras.pop()
    assert largura < MEIA_LARGURA_DO_NOME * 2, (
        f"o recorte ({largura}) não cabe na busca "
        f"({MEIA_LARGURA_DO_NOME * 2}) com folga para o deslize da janela")


# ===========================================================================
# O QUADRO VEM DO LAÇO -- 23/09/2026
# ===========================================================================
#
# Os servidores voltaram e o bot NÃO reconhecia: 560 Cancel seguidos, com
# "Light in the Darkness" na tela. O reconhecimento estava certo -- medido na
# tela real do jogo, os quatro nomes casavam a 0.999/1.000 nas linhas certas.
#
# O erro era de ONDE o quadro vinha: `_do_server` chamava `detector.detect()`
# por conta própria, uma SEGUNDA captura. `Detection.frame` existe exatamente
# porque "a segunda captura pode falhar sozinha" -- o comentário está em
# `login_states.py` e nasceu de outro travamento, na seleção de personagem.
#
# Com o quadro nulo, `linha_do_servidor` devolvia `None` e o bot lia isso como
# "o servidor não está lá". Confundir "não sei olhar" com "não está" é o mesmo
# erro do pino do `Input` de 09/09/2026.


def test_a_leitura_do_nome_usa_o_QUADRO_DO_LACO():
    """O quadro da decisão vem de fora, não de uma captura nova.

    A captura de DENTRO do laço de seleção continua e é legítima: ela confere o
    realce DEPOIS do clique, então precisa de um quadro novo. O que não pode
    voltar é capturar ANTES, para a leitura do nome -- foi o defeito de
    23/09/2026.
    """
    import inspect

    params = list(inspect.signature(LoginSequence._do_server).parameters)
    assert params == ["self", "det"], (
        f"`_do_server` deixou de receber o `Detection` do laço: {params}")

    fonte = inspect.getsource(LoginSequence._do_server)
    assert "det.frame" in fonte, "a leitura não usa mais o quadro do laço"
    antes_do_laco = fonte.split("for attempt")[0]
    assert "self.detector.detect()" not in antes_do_laco, (
        "voltou a capturar por conta própria antes de ler o nome — é o defeito "
        "de 23/09/2026, que cancelou 560 vezes com o servidor na tela")


def test_SEM_QUADRO_nao_cancela_mesmo_sabendo_reconhecer():
    """"Não achei" só vale se DEU PARA OLHAR.

    Sem quadro é "não sei", e não sei nunca cancela — a mesma regra do pino do
    `Input` e do realce da linha.
    """
    seq = _login("Light in the Darkness")
    seq.detector.sabe_reconhecer = lambda _n: True
    seq.detector.linha_do_servidor = lambda *a, **k: None

    seq._do_server(None)          # o laço não tinha quadro

    assert seq.coords.server_cancel not in seq.cliques, (
        "cancelou por não enxergar — troca um erro raro por um permanente")
    assert seq.cliques[-1] == seq.coords.server_ok


def test_COM_quadro_e_nome_ausente_cancela_como_deve():
    """O outro lado: olhei, sei reconhecer, não está lá."""
    seq = _login_que_enxerga("Light in the Darkness", linha_realcada=0)
    seq.detector.sabe_reconhecer = lambda _n: True
    seq.detector.linha_do_servidor = lambda *a, **k: None

    seq._do_server(_det_com_quadro())

    assert seq.cliques == [seq.coords.server_cancel]


# ===========================================================================
# A FOLGA EM Y -- o defeito de UM PIXEL, 23/09/2026
# ===========================================================================
#
# O bot cancelava com o servidor na tela, e o diagnóstico feito de fora via os
# cinco nomes a 0.999. A diferença estava na REGIÃO da busca:
#
#   * a região tinha a ALTURA DA LINHA (20 px) e o recorte tem 17 -> o topo do
#     texto precisava cair numa janela de 4 posições;
#   * o centro real da primeira linha ficou 2 px abaixo do que a âncora calcula;
#   * medido no quadro que o PRÓPRIO BOT salvou: o texto casa a 1.000 com o topo
#     em y=320, e a região ia só até 319. Um pixel.
#
# `tests/dados/lista_como_o_bot_ve.png` é esse quadro -- capturado pelo bot, no
# momento da decisão, com a lista completa na tela.


def test_os_cinco_servidores_no_quadro_QUE_O_BOT_SALVOU():
    """A prova de campo: o quadro é do bot, não de um print preparado."""
    det = _detector_real()
    _pula_sem_templates(det)
    img = _fixture("lista_como_o_bot_ve.png")

    # O bot registrou `primeira=(342, 246)` no log daquele instante; a fixture
    # é um recorte a partir de (250, 180), então a mesma posição vira:
    primeira = (342 - 250, 246 - 180)
    esperado = {
        "White Horse [NEW]": 0,
        "Tiger Fish (WW)": 1,
        "Sky Ice (GSM&BI)": 2,
        "All Stars": 3,
        "Light in the Darkness": 4,
    }
    for nome, linha in esperado.items():
        achou = det.linha_do_servidor(img, nome, primeira, 5)
        assert achou == linha, (
            f"'{nome}' devia estar na linha {linha} e veio {achou} — é o "
            f"defeito da folga em y de 23/09/2026")


def test_a_altura_da_busca_SAI_DO_RECORTE_e_nao_da_linha():
    """Derivar da linha foi o erro: 20 px de região para 17 de recorte deixa
    4 posições, e 2 px de desvio da âncora já quebram."""
    import inspect

    from blazesbot.bot.login_states import FOLGA_EM_Y_DA_BUSCA

    assert FOLGA_EM_Y_DA_BUSCA >= 2, (
        "medido: com folga 0 são 5 erros em 5; a partir de 2 são zero")
    assert FOLGA_EM_Y_DA_BUSCA < 20, (
        "com 20 a busca alcança o texto da linha VIZINHA")

    for metodo in (LoginStateDetector.linha_do_servidor,
                   LoginStateDetector.servidor_offline):
        fonte = inspect.getsource(metodo)
        assert "modelo.shape[0] + 2 * FOLGA_EM_Y_DA_BUSCA" in fonte, (
            f"{metodo.__name__} voltou a derivar a altura da busca da LINHA")
