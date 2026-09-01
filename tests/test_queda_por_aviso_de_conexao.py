"""A frase no CHAT não é uma queda.

=========================================================================
O DEFEITO QUE ESTE TESTE TRAVA
=========================================================================

O template que decide "esta conta caiu" (`state_conn_prefix.png`) é só a frase
"Connection interrup", sem moldura -- recortada assim de propósito, para casar
com as duas variantes do aviso. O preço é que ela casa ONDE QUER QUE APAREÇA.

E ela aparece no chat. Em 29/08 e 01/09/2026 outro jogador digitou `[world]
[zmypx]: maintenance more connection interrupted?` no canal mundial, e o bot
derrubou e relogou DEZ contas vivas -- personagem em pé, com alvo selecionado,
jogando. Os prints estão em `logs/quedas/`, e são o quadro que disparou a queda.

Duas populações, medidas nesses mesmos arquivos:

    queda real     nota 0.980-0.983   em (441, 198)   a caixa modal
    chat dos outros nota 0.799-0.844  em (241, 570)   o rodapé esquerdo

O conserto tem duas defesas independentes -- REGIÃO presa à caixa e LIMIAR em
0.92 -- porque a frase no chat é um evento que o bot não controla e não pode
custar a run de cinco contas.
"""
import pathlib

import cv2
import pytest

from blazesbot.bot import watchdog
from blazesbot.core.coords import coords_for_size

RAIZ = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = RAIZ / "data" / "templates" / "state_conn_prefix.png"
QUEDAS = RAIZ / "logs" / "quedas"

# Verdade de campo, conferida a olho nos prints: nestes a caixa "Connection
# interrupted, please open client again." ESTÁ na tela.
QUEDAS_REAIS = {
    "20260831-130420-creubo.jpg", "20260831-130427-gamerblazes.jpg",
    "20260831-130429-blazestpas.jpg", "20260831-130510-mfaustoapp069.jpg",
    "20260831-130534-blazesofgamer.jpg", "20260831-161005-blazestpas.jpg",
    "20260831-161009-mfaustoapp069.jpg", "20260901-024026-blazesofgamer.jpg",
    "20260901-024027-blazesgamer.jpg", "20260901-024029-creubo.jpg",
    "20260901-024037-gamerblazes.jpg", "20260901-024041-blazestpas.jpg",
}

# Nestes NÃO há caixa nenhuma: o personagem está vivo e a frase está no chat.
FALSOS_POSITIVOS = {
    "20260829-030455-blazesofgamer.jpg", "20260829-030455-blazestpas.jpg",
    "20260829-030459-mfaustoapp069.jpg", "20260829-030521-creubo.jpg",
    "20260829-030549-blazesgamer.jpg", "20260901-022514-blazesgamer.jpg",
    "20260901-022514-blazesofgamer.jpg", "20260901-022514-creubo.jpg",
    "20260901-022515-gamerblazes.jpg", "20260901-022526-blazestpas.jpg",
}


def _nota(nome: str) -> float:
    """A nota do template DENTRO da região que o watchdog olha."""
    quadro = cv2.imread(str(QUEDAS / nome))
    if quadro is None:
        pytest.skip(f"print de queda ausente: {nome}")
    template = cv2.imread(str(TEMPLATE), cv2.IMREAD_GRAYSCALE)
    cinza = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
    x, y, largura, altura = watchdog._regiao_do_aviso(quadro)
    recorte = cinza[y:y + altura, x:x + largura]
    if recorte.shape[0] < template.shape[0] or recorte.shape[1] < template.shape[1]:
        return 0.0
    return cv2.minMaxLoc(
        cv2.matchTemplate(recorte, template, cv2.TM_CCOEFF_NORMED))[1]


@pytest.mark.parametrize("nome", sorted(FALSOS_POSITIVOS))
def test_a_frase_no_chat_nao_derruba_a_conta(nome):
    nota = _nota(nome)
    assert nota < watchdog.RECONNECT_THRESHOLD, (
        f"{nome}: o personagem está VIVO neste print e o watchdog o derrubaria "
        f"({nota:.3f} >= {watchdog.RECONNECT_THRESHOLD}). A frase está no chat, "
        "não na caixa.")


@pytest.mark.parametrize("nome", sorted(QUEDAS_REAIS))
def test_a_caixa_de_verdade_continua_derrubando(nome):
    """O conserto não pode custar a detecção -- ficar preso na caixa é pior."""
    nota = _nota(nome)
    assert nota >= watchdog.RECONNECT_THRESHOLD, (
        f"{nome}: a caixa ESTÁ na tela e o watchdog não veria "
        f"({nota:.3f} < {watchdog.RECONNECT_THRESHOLD}). Sem isto a conta fica "
        "apertando teclas contra um cliente morto.")


def test_a_margem_entre_as_duas_populacoes_continua_grande():
    """Um limiar sem margem é um defeito esperando a próxima build do jogo."""
    pior_falso = max(_nota(n) for n in FALSOS_POSITIVOS)
    pior_queda = min(_nota(n) for n in QUEDAS_REAIS)
    assert pior_queda - pior_falso > 0.30, (
        f"margem caiu para {pior_queda - pior_falso:+.3f} "
        f"(pior falso {pior_falso:.3f}, pior queda {pior_queda:.3f}). "
        "Era +0.559 quando foi medida.")


def test_a_regiao_acompanha_a_resolucao():
    """A UI do jogo NÃO escala: a caixa é centralizada, então o ponto anda."""
    import numpy as np
    for largura, altura in ((1024, 768), (1280, 1024), (1920, 1080)):
        quadro = np.zeros((altura, largura, 3), dtype=np.uint8)
        x, y, w, h = watchdog._regiao_do_aviso(quadro)
        cx, cy = coords_for_size(largura, altura).aviso_de_conexao
        assert x <= cx <= x + w and y <= cy <= y + h, (
            f"{largura}x{altura}: a região {(x, y, w, h)} não contém o ponto "
            f"da caixa {(cx, cy)}")
        assert 0 <= x and 0 <= y and x + w <= largura and y + h <= altura


def test_o_limiar_nao_pode_voltar_para_o_valor_que_derrubava():
    """0.80 ficava ABAIXO do ruído do chat (0.844). Não é opinião, é medição."""
    assert watchdog.RECONNECT_THRESHOLD >= 0.90
