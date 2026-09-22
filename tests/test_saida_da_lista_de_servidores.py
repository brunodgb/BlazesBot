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

import pytest

from blazesbot.bot.login import VOLTAS_NA_LISTA_DE_SERVIDORES, LoginSequence
from blazesbot.bot.login_states import LoginStateDetector, Phase
from blazesbot.core.coords import coords_for_size


class _Detector:
    """Dublê do detector -- com o método REAL de ler o status, que é o que os
    testes do status exercitam."""

    servidor_offline = LoginStateDetector.servidor_offline
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
