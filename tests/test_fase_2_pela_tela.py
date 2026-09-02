"""A segunda fase do boss vista NA TELA: a barra amarela.

=============================================================================
O QUE O USUÁRIO DISSE
=============================================================================

*"A segunda fase do boss tem 2 barras de vida, uma amarela que é a primeira e
depois que terminar a amarela vem a barra vermelha, normal como outros mobs; aí
quando zera a barra vermelha ele morre, e fica como naquela imagem que identifica
a morte."*

E antes: *"caso encontre isso em algum momento da luta contra o boss é pq entrou
na segunda fase e é o momento de usar a Break Soul caso esteja configurada a
tecla."*

Então o amarelo só existe na fase 2, e ver amarelo É a virada de fase. É o
SEGUNDO sinal: a troca de struct continua valendo, e os dois levantam a mesma
bandeira.

=============================================================================
OS TESTES QUE CARREGAM O PESO
=============================================================================

**`test_DENTE_em_cinza_a_FASE_1_tambem_casaria`** -- o único que justifica o
`colorido=True`, e ele mede em vez de afirmar: em cinza a fase 1 marca 0,874,
acima do limiar de marcador de UI deste projeto. Em cinza a Break Soul sairia no
primeiro segundo da luta, que é o defeito que ela existe para evitar.

**`test_a_bandeira_NUNCA_baixa_quando_o_amarelo_acaba`** -- o amarelo é a
PRIMEIRA das duas vidas. Uma bandeira que baixasse no `False` tiraria a Break
Soul de rotação exatamente na metade final da fase 2, a que decide a run.

**`test_na_luta_dos_guardas_a_tela_NUNCA_e_lida`** -- o portão. Este é o mesmo
defeito que já custou uma entrega nesta feature: a Break Soul vazando para fora
da luta do boss.

**`test_a_barra_do_PROPRIO_personagem_nao_levanta_a_bandeira`** -- o quadro do
personagem é um par vida+mana igual, no canto superior esquerdo. Sem a faixa,
"a minha barra" viraria "o boss virou de fase".
"""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot.bc.combat import CombatEngine
from blazesbot.core import vision

CAMINHO_DO_MODELO = "data/templates/boss_2_fase.png"


@pytest.fixture(scope="module")
def modelo():
    """O modelo REAL em disco, em cor. Sem ele estes testes não medem nada."""
    img = cv2.imread(CAMINHO_DO_MODELO, cv2.IMREAD_COLOR)
    assert img is not None, f"{CAMINHO_DO_MODELO} não existe"
    assert img.shape[2] == 3, "o modelo precisa estar em 3 canais (sem alpha)"
    return img


def _fase_1_sintetica(modelo):
    """O MESMO recorte com a vida recolorida para o vermelho da fase 1.

    A luminância de cada linha é preservada -- é isso que torna a medição
    honesta: o que ela pergunta é "cinza separa duas barras de mesma FORMA e
    matiz diferente?", e não "estas duas imagens são diferentes?".
    """
    fase1 = modelo.copy()
    for y in range(2, 10):
        lum = cv2.cvtColor(modelo[y:y + 1], cv2.COLOR_BGR2GRAY)[0].astype(float)
        fase1[y, :, 2] = np.clip(lum / 0.299, 0, 255).astype(np.uint8)
        fase1[y, :, 1] = (lum * 0.12).astype(np.uint8)
        fase1[y, :, 0] = (lum * 0.12).astype(np.uint8)
    return fase1


def _quadro_com(barra, x=460, y=40, largura=200):
    """Uma tela 1024x768 com a barra colada no quadro do alvo."""
    quadro = np.zeros((768, 1024, 3), np.uint8)
    pedaco = cv2.resize(barra, (largura, barra.shape[0]),
                        interpolation=cv2.INTER_NEAREST)
    quadro[y:y + barra.shape[0], x:x + largura] = pedaco
    return quadro


# ---------------------------------------------------------------------------
# 1. A LEITURA
# ---------------------------------------------------------------------------

def test_acha_a_barra_amarela_no_quadro_do_alvo(modelo):
    assert vision.boss_na_segunda_fase(_quadro_com(modelo), modelo) is True


def test_tela_sem_a_barra_devolve_False_e_nao_None(modelo):
    """`False` = olhei e não vi. `None` = não deu para olhar. São coisas
    diferentes, e quem consome só age no `True`."""
    assert vision.boss_na_segunda_fase(np.zeros((768, 1024, 3), np.uint8),
                                       modelo) is False


def test_sem_quadro_ou_sem_modelo_devolve_None(modelo):
    assert vision.boss_na_segunda_fase(None, modelo) is None
    assert vision.boss_na_segunda_fase(_quadro_com(modelo), None) is None


def test_a_barra_do_PROPRIO_personagem_nao_levanta_a_bandeira(modelo):
    """O quadro do personagem é um par vida+mana igual, no canto SUPERIOR
    ESQUERDO -- e o painel de time também mora na esquerda.

    A faixa começa em 30% da largura justamente para deixar os dois de fora. Sem
    ela, "a minha barra" ou "a barra de um aliado" viraria "o boss virou de fase".
    """
    assert vision.boss_na_segunda_fase(_quadro_com(modelo, x=8, y=40),
                                       modelo) is False


def test_a_barra_abaixo_da_faixa_nao_conta(modelo):
    x0, y0, x1, y1 = vision._regiao_quadro_alvo(1024, 768)
    assert vision.boss_na_segunda_fase(
        _quadro_com(modelo, y=y1 + 30), modelo) is False


# ---------------------------------------------------------------------------
# 2. O DENTE DA COR
# ---------------------------------------------------------------------------

def _escore(quadro, modelo_, colorido):
    if not colorido:
        quadro = cv2.cvtColor(quadro, cv2.COLOR_BGR2GRAY)
        modelo_ = cv2.cvtColor(modelo_, cv2.COLOR_BGR2GRAY)
    return float(cv2.minMaxLoc(
        cv2.matchTemplate(quadro, modelo_, cv2.TM_CCOEFF_NORMED))[1])


def test_DENTE_em_cinza_a_FASE_1_tambem_casaria(modelo):
    """A medição que obriga o `colorido=True`.

    Em cinza a fase 1 marca ~0,874 -- acima do 0,85 que este projeto usa para
    marcador de UI. Ou seja, em cinza a Break Soul começaria a sair no primeiro
    segundo da luta do boss.

    Se alguém trocar o casamento para cinza "para ficar igual ao resto", este
    teste é o que explica por que não dá.
    """
    fase1 = _fase_1_sintetica(modelo)
    em_cinza = _escore(fase1, modelo, colorido=False)
    em_cor = _escore(fase1, modelo, colorido=True)

    assert em_cinza > 0.85, (
        f"a fase 1 marca {em_cinza:.3f} em cinza; se isso caiu abaixo de 0,85 a "
        f"premissa da medição mudou e o comentário do `LIMIAR_DA_FASE_2_DO_BOSS` "
        f"precisa ser refeito"
    )
    assert em_cor < vision.LIMIAR_DA_FASE_2_DO_BOSS, (
        f"a fase 1 marca {em_cor:.3f} EM COR, e o limiar é "
        f"{vision.LIMIAR_DA_FASE_2_DO_BOSS} -- não há mais vão"
    )
    assert em_cinza - em_cor > 0.05, (
        "cinza deixou de ser mais permissivo que cor neste par; a razão de ser "
        "do `colorido=True` era exatamente essa diferença"
    )


def test_a_FASE_1_na_tela_nao_levanta_a_bandeira(modelo):
    """O mesmo, mas pela porta que a produção usa."""
    fase1 = _quadro_com(_fase_1_sintetica(modelo))
    assert vision.boss_na_segunda_fase(fase1, modelo) is False


def test_a_fase_2_DEGRADADA_ainda_passa(modelo):
    """Do outro lado do vão: recompressão e ruído não podem derrubar o sinal."""
    ruim = cv2.imdecode(
        cv2.imencode(".jpg", modelo, [cv2.IMWRITE_JPEG_QUALITY, 70])[1],
        cv2.IMREAD_COLOR)
    ruim = np.clip(
        ruim.astype(int) + np.random.RandomState(7).randint(-8, 9, ruim.shape),
        0, 255).astype(np.uint8)
    assert vision.boss_na_segunda_fase(_quadro_com(ruim), modelo) is True

    escuro = cv2.convertScaleAbs(modelo, alpha=0.88)
    assert vision.boss_na_segunda_fase(_quadro_com(escuro), modelo) is True


def test_o_limiar_fica_DENTRO_do_vao_medido(modelo):
    fase1 = _escore(_fase_1_sintetica(modelo), modelo, colorido=True)
    assert fase1 < vision.LIMIAR_DA_FASE_2_DO_BOSS < 1.0
    assert vision.LIMIAR_DA_FASE_2_DO_BOSS - fase1 > 0.05, (
        "o limiar encostou na fase 1; sem margem, variação de brilho decide"
    )


# ---------------------------------------------------------------------------
# 3. A BARRA AMARELA CONFUNDE O `vida_do_alvo` -- AGORA CONSERTADO
# ---------------------------------------------------------------------------
# A validação `_barra_vermelha_e_hp_valida` rejeita a barra amarela (não é HP
# válido: não preenche da esquerda, tem cor errada). O comportamento correto é
# retornar `None` = "não achei quadro do alvo válido", não `0.0` = "achei e tá
# vazio". Isso evita o defeito do APP (piso 14.2%, vãos) e a "bomba armada" do
# boss fase 2. Ver `docs/decisoes/alvo-o-que-esta-medido.md` item 36.

def test_a_amarela_da_fase_2_e_LIDA_como_vida(modelo):
    """A barra amarela É vida, e a leitura devolve a fração dela.

    ===================================================================
    A REGRA MUDOU EM 25/08/2026, E A ANTIGA ESTÁ AQUI PARA NÃO VOLTAR
    ===================================================================

    Antes `vida_do_alvo` devolvia `None` durante a amarela, de propósito: como
    ela não passava na validação de HP, devolver `0.0` teria virado um falso
    "o mob morreu". `None` era o menos errado.

    Só que `None` é um buraco no log justamente na metade da luta do boss, e o
    usuário pediu para ACOMPANHAR a vida: *"quero poder ir vendo a cada
    alteração"*. E ele explicou a mecânica: *"a barra amarela sobrepõe a
    vermelha e conforme ela vai baixando vai aparecendo a vermelha"*.

    Então a amarela passa a ser lida como o que ela é -- a barra de cima -- e a
    proteção contra o falso "morreu" mudou de lugar: quem decide morte exige
    **amarelo ZERO e vermelho VAZIO** (ver `CombatEngine._alvo_morreu`), o que a
    fase 2 no meio da amarela nunca satisfaz.

    A COR AQUI É A DO MODELO REAL EM DISCO, não uma dedução: o
    `boss_2_fase.png` lê BGR (0, ~204, ~231) na faixa medida.
    """
    leitura = vision.ler_barra_do_alvo(_quadro_com(modelo))
    assert leitura is not None, "a amarela caiu fora da faixa medida da barra"
    assert leitura.amarelo > 0.9, "a amarela real não foi reconhecida como amarela"
    assert leitura.na_segunda_fase is True
    assert vision.vida_do_alvo(_quadro_com(modelo)) > 0.9

    # A fase 1 sintética (vermelha) no mesmo lugar lê vida CHEIA e SEM amarelo --
    # é o que separa "está na fase 2" de "está na fase 1".
    fase_1 = vision.ler_barra_do_alvo(_quadro_com(_fase_1_sintetica(modelo)))
    assert fase_1 is not None and fase_1.vermelho > 0.9
    assert fase_1.na_segunda_fase is False


def test_o_total_do_boss_junta_as_duas_barras(modelo):
    """Amarela cheia = 100% do boss; amarela vazia com a vermelha cheia = 50%.

    É a conta que o usuário descreveu: *"amarelo na tela você começa em 100% e
    quando vier o vermelho quer dizer que é 50% para menos"*.
    """
    amarela_cheia = vision.ler_barra_do_alvo(_quadro_com(modelo))
    assert amarela_cheia.total_do_boss(True) == pytest.approx(1.0, abs=0.05)

    vermelha_cheia = vision.ler_barra_do_alvo(_quadro_com(_fase_1_sintetica(modelo)))
    assert vermelha_cheia.total_do_boss(True) == pytest.approx(0.5, abs=0.05)
    # E a MESMA barra vermelha cheia na fase 1 é vida inteira, não metade.
    assert vermelha_cheia.total_do_boss(False) == pytest.approx(1.0, abs=0.05)


def _arvore_do_metodo(metodo):
    """AST do método, pronto para andar.

    `dedent` porque `getsource` de um método vem indentado, e assinatura de
    várias linhas não compila solta.
    """
    import ast
    import inspect
    import textwrap
    return ast.parse(textwrap.dedent(inspect.getsource(metodo))).body[0]


def _chamadas(no):
    import ast
    return {n.func.attr for n in ast.walk(no)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}


def test_o_boss_nao_gasta_TAB_com_veredito_de_morte():
    """O que mantém a bomba desarmada, lido no AST.

    A luta do boss não passa `tabs_ao_morrer`, então vale o default ZERO -- e é
    esse zero que faz `_alvo_morreu()` nunca ser consultado ali. Dar um valor
    positivo ao boss faria a barra amarela declarar morte a cada leitura.

    Duas metades, porque o zero pode se perder de dois jeitos: mudando o default
    da função, ou passando um valor na chamada do boss.
    """
    import ast
    import inspect

    assinatura = inspect.signature(CombatEngine.atacar_ate_sair_de_combate)
    assert assinatura.parameters["tabs_ao_morrer"].default == 0, (
        "o default de tabs_ao_morrer deixou de ser 0, e a luta do boss depende "
        "dele -- leia o aviso em vision.boss_na_segunda_fase"
    )

    for chamada in ast.walk(_arvore_do_metodo(
            CombatEngine.fase_do_boss_por_combate)):
        if not isinstance(chamada, ast.Call):
            continue
        for kw in chamada.keywords:
            assert kw.arg != "tabs_ao_morrer", (
                "a luta do boss passou a pedir TAB ao morrer; com a barra "
                "amarela lendo 0.0 de vida, isso declara morte a cada leitura"
            )


# ---------------------------------------------------------------------------
# 4. O GATILHO NA LUTA
# ---------------------------------------------------------------------------

class _Templates:
    def __init__(self, modelo):
        self._modelo = modelo
        self.pedidos_em_cor: list[str] = []
        self.pedidos_em_cinza: list[str] = []

    def load_color(self, nome):
        self.pedidos_em_cor.append(nome)
        return self._modelo

    def load(self, nome):
        self.pedidos_em_cinza.append(nome)
        return cv2.cvtColor(self._modelo, cv2.COLOR_BGR2GRAY)


def _motor(monkeypatch, modelo, quadro, break_soul="4"):
    ctx = SimpleNamespace(
        hwnd=1234,
        templates=_Templates(modelo),
        settings=SimpleNamespace(keys=SimpleNamespace(break_soul=break_soul)),
        log=SimpleNamespace(info=lambda *a, **k: None,
                            debug=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            error=lambda *a, **k: None),
    )
    monkeypatch.setattr(motor_de_combate.vision, "capture_window", lambda _h: quadro)
    monkeypatch.setattr(motor_de_combate.vision, "frame_is_blank", lambda _q: False)

    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = ctx
    motor._na_segunda_fase_do_boss = False
    return motor


def test_a_barra_amarela_levanta_a_bandeira_SEM_troca_de_struct(monkeypatch,
                                                               modelo):
    """O ponto do pedido: nada de memória participa desta decisão.

    O sinal por struct depende de a memória responder E de o nome do boss ser
    legível no instante da troca. Este depende só da tela -- e é isso que faz os
    dois valerem juntos.
    """
    motor = _motor(monkeypatch, modelo, _quadro_com(modelo))
    motor._conferir_fase_2_na_tela()

    assert motor._na_segunda_fase_do_boss is True


def test_tela_sem_amarelo_deixa_a_bandeira_BAIXA(monkeypatch, modelo):
    motor = _motor(monkeypatch, modelo, np.zeros((768, 1024, 3), np.uint8))
    motor._conferir_fase_2_na_tela()

    assert motor._na_segunda_fase_do_boss is False


def test_a_bandeira_NUNCA_baixa_quando_o_amarelo_acaba(monkeypatch, modelo):
    """O amarelo é a PRIMEIRA das duas vidas da fase 2: ele ACABA, e depois vem o
    vermelho normal. Uma bandeira que baixasse no `False` tiraria a Break Soul de
    rotação exatamente na metade final da fase 2 -- a que decide a run."""
    motor = _motor(monkeypatch, modelo, _quadro_com(modelo))
    motor._conferir_fase_2_na_tela()
    assert motor._na_segunda_fase_do_boss is True

    # o amarelo terminou; agora a tela é a barra vermelha de sempre
    monkeypatch.setattr(motor_de_combate.vision, "capture_window",
                        lambda _h: _quadro_com(_fase_1_sintetica(modelo)))
    motor._conferir_fase_2_na_tela()

    assert motor._na_segunda_fase_do_boss is True, "a bandeira baixou"


def test_com_a_bandeira_LEVANTADA_nem_captura_a_tela(monkeypatch, modelo):
    """A saída antecipada é o que torna o custo aceitável: depois de levantada
    não há mais nada a descobrir, e a captura para de acontecer."""
    capturas = []
    motor = _motor(monkeypatch, modelo, _quadro_com(modelo))
    monkeypatch.setattr(motor_de_combate.vision, "capture_window",
                        lambda h: capturas.append(h) or _quadro_com(modelo))
    motor._na_segunda_fase_do_boss = True

    motor._conferir_fase_2_na_tela()

    assert capturas == [], "capturou a tela com a bandeira já levantada"


def test_pede_o_modelo_EM_COR_e_nunca_em_cinza(monkeypatch, modelo):
    """`load` em vez de `load_color` faria a fase 1 casar a 0,874 -- e o
    `find_all_templates` levantaria `ValueError` por `ndim`, que é o desenho
    certo: gritar em vez de devolver "não tem"."""
    motor = _motor(monkeypatch, modelo, _quadro_com(modelo))
    motor._conferir_fase_2_na_tela()

    assert motor.ctx.templates.pedidos_em_cor == [motor_de_combate.TEMPLATE_FASE_2_DO_BOSS]
    assert motor.ctx.templates.pedidos_em_cinza == []


def test_captura_que_falha_nao_derruba_a_luta(monkeypatch, modelo):
    motor = _motor(monkeypatch, modelo, _quadro_com(modelo))
    monkeypatch.setattr(motor_de_combate.vision, "capture_window",
                        lambda _h: (_ for _ in ()).throw(RuntimeError("boom")))

    motor._conferir_fase_2_na_tela()          # não levanta

    assert motor._na_segunda_fase_do_boss is False


def test_desligado_nao_le_a_tela(monkeypatch, modelo):
    monkeypatch.setattr(motor_de_combate, "USAR_IMAGEM_DA_FASE_2", False)
    capturas = []
    motor = _motor(monkeypatch, modelo, _quadro_com(modelo))
    monkeypatch.setattr(motor_de_combate.vision, "capture_window",
                        lambda h: capturas.append(h) or _quadro_com(modelo))

    motor._conferir_fase_2_na_tela()

    assert capturas == [] and motor._na_segunda_fase_do_boss is False


# ---------------------------------------------------------------------------
# 5. O PORTÃO: só na luta do boss
# ---------------------------------------------------------------------------

def test_na_luta_dos_guardas_a_tela_NUNCA_e_lida():
    """A chamada tem que estar DENTRO do `if registrar_troca_de_fase`.

    Esse `if` é o que garante "só na luta do boss" -- `registrar_troca_de_fase`
    é passado por um único chamador. Fora dele, a barra amarela poderia levantar
    a bandeira na luta dos guardas e a Break Soul vazaria para lá, que é o
    defeito inteiro que `USAR_BREAK_SOUL_SO_NA_FASE_2` existe para fechar.

    Lido no AST, e não por texto: comentário citando o nome não conta.
    """
    import ast

    arvore = _arvore_do_metodo(CombatEngine.atacar_ate_sair_de_combate)

    protegidas = set()
    for no in ast.walk(arvore):
        if (isinstance(no, ast.If) and isinstance(no.test, ast.Name)
                and no.test.id == "registrar_troca_de_fase"):
            protegidas |= _chamadas(no)

    assert "_conferir_fase_2_na_tela" in protegidas, (
        "a leitura da fase 2 pela tela saiu de dentro do "
        "`if registrar_troca_de_fase` -- a Break Soul pode vazar para os guardas"
    )
    assert "_conferir_fase_2_na_tela" not in (
        _chamadas(arvore) - protegidas
    ), "há uma segunda chamada, fora do portão"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
