"""O ALVO: id pela memória, vida pela tela, morte confirmada pelo marcador.

O desenho foi combinado com o usuário em 25/08/2026, e é este:

    id == 0            -> sem alvo. Não decide nada.
    id mudou           -> alvo novo.
    vida > 10%         -> vivo. NÃO procura marcador nenhum.
    vida <= 10%        -> a MESMA captura serve o `EnemyDead.png`:
         marcador bateu       -> MORREU, libera o TAB
         marcador não bateu   -> sobrou vida, continua rotacionando skill
    não deu para ler   -> "não sei". Não gasta TAB.

=============================================================================
O QUE ESTES TESTES SEGURAM, E POR QUE CADA UM EXISTE
=============================================================================

**A régua por offset fixo.** A posição da barra foi MEDIDA pelo usuário em duas
resoluções (1024x768 e 1680x1050) e não escala: x 466-600, y 46-48, contando a
partir do canto superior esquerdo da área de cliente. A busca proporcional que
existia antes (`largura * 0.30`) quebrava fora de 1024 -- a 1680 a barra começa
antes da faixa de busca.

**Contagem por COLUNA.** A leitura antiga dividia pixels vermelhos pela ÁREA do
retângulo, e as linhas de borda diluíam o valor: o mob morto lia 0,7%, e foi por
isso que o limiar precisou subir para 2%. Coluna cheia é coluna de vida.

**"Não sei" existe.** O defeito mais caro desta área foi a régua devolver float
confiante enquanto media outra coisa (conta APP: piso 14,2%, 14 valores
distintos, 96% dos ciclos sem nenhuma entidade com aquele HP). Se a faixa não
tiver as cores da barra, a resposta é `None`.

**Uma captura por leitura.** A barra e o marcador saem do mesmo quadro.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from blazesbot.bot.bc import combat
from blazesbot.bot.bc.combat import CombatEngine
from blazesbot.core import target_hybrid as th
from blazesbot.core import vision

# ---------------------------------------------------------------------------
# quadros sintéticos, na geometria MEDIDA
# ---------------------------------------------------------------------------

VERMELHO = (2, 0, 189)          # BGR -- (188-190, 0, 2-3) em RGB, medido
AMARELO = (0, 204, 231)         # BGR -- lido do `boss_2_fase.png` em disco
VAZIO = (45, 9, 55)             # BGR -- (55, 9, 45) em RGB, medido


def quadro(vermelho=1.0, amarelo=0.0, largura=1024, altura=768):
    """Uma tela com a barra do alvo desenhada onde ela realmente fica."""
    q = np.zeros((altura, largura, 3), np.uint8)
    x0, x1 = vision.BARRA_DO_ALVO_X0, vision.BARRA_DO_ALVO_X1
    y0, y1 = vision.BARRA_DO_ALVO_Y0, vision.BARRA_DO_ALVO_Y1
    colunas = x1 - x0
    q[y0:y1, x0:x1] = VAZIO
    q[y0:y1, x0:x0 + int(round(colunas * vermelho))] = VERMELHO
    if amarelo:
        q[y0:y1, x0:x0 + int(round(colunas * amarelo))] = AMARELO
    return q


# ===========================================================================
# 1. A RÉGUA
# ===========================================================================

@pytest.mark.parametrize("fracao", [1.0, 0.86, 0.52, 0.20, 0.10, 0.0])
def test_a_barra_e_lida_com_precisao_de_coluna(fracao):
    leitura = vision.ler_barra_do_alvo(quadro(fracao))
    assert leitura is not None
    assert leitura.vermelho == pytest.approx(fracao, abs=0.01)
    assert leitura.vida == pytest.approx(fracao, abs=0.01)


def test_o_DENTE_do_piso_o_mob_morto_le_ZERO():
    """O mob morto lia 0,7% na régua antiga -- por diluição de área, não por
    vida sobrando. Aqui ele lê zero cravado, e é isso que permite um dia baixar
    `LIMIAR_VIDA_TELA` de 2% para 1% com medição atrás."""
    assert vision.ler_barra_do_alvo(quadro(0.0)).vida == 0.0


def test_quadro_sem_a_barra_devolve_NAO_SEI():
    """Ausência de barra é `None`, nunca `0.0`. Zero é "vi e está vazia"."""
    assert vision.ler_barra_do_alvo(np.zeros((768, 1024, 3), np.uint8)) is None
    assert vision.ler_barra_do_alvo(None) is None


def test_a_regua_NAO_escala_com_a_resolucao():
    """A medição do usuário: a mesma coordenada vale em 1024x768 e 1680x1050.

    É o teste que a busca proporcional antiga reprovaria -- a 1680 de largura a
    faixa de 30%-70% começa em x=504, e a barra começa em 466.
    """
    for largura, altura in [(1024, 768), (1280, 800), (1680, 1050)]:
        leitura = vision.ler_barra_do_alvo(
            quadro(0.52, largura=largura, altura=altura))
        assert leitura is not None, f"perdeu a barra em {largura}x{altura}"
        assert leitura.vermelho == pytest.approx(0.52, abs=0.01)


def test_janela_menor_que_a_barra_devolve_NAO_SEI():
    """Sem espaço para o recorte não há leitura -- e não há chute."""
    assert vision.ler_barra_do_alvo(np.zeros((30, 300, 3), np.uint8)) is None


# ===========================================================================
# 2. AS DUAS BARRAS DO BOSS
# ===========================================================================

def test_a_amarela_e_reconhecida_e_marca_a_fase_2():
    leitura = vision.ler_barra_do_alvo(quadro(vermelho=1.0, amarelo=0.46))
    assert leitura.amarelo == pytest.approx(0.46, abs=0.01)
    assert leitura.vermelho == pytest.approx(0.54, abs=0.01)
    assert leitura.na_segunda_fase is True
    # A barra DA VEZ é a de cima: é a amarela que está descendo.
    assert leitura.vida == pytest.approx(0.46, abs=0.01)


def test_o_total_desce_continuo_de_100_a_0():
    """A conta do usuário: amarela = 100%->50%, vermelha = 50%->0%.

    O log tem de mostrar uma linha que só desce -- se o total subisse na virada
    das barras, a pessoa lendo concluiria que o boss se curou.
    """
    passos = [
        (1.0, 1.00, 1.000),      # amarela cheia
        (1.0, 0.50, 0.750),
        (1.0, 0.00, 0.500),      # amarela acabou, vermelha cheia
        (0.50, 0.0, 0.250),
        (0.0, 0.0, 0.000),
    ]
    anterior = 1.01
    for vermelho, amarelo, esperado in passos:
        leitura = vision.ler_barra_do_alvo(quadro(vermelho, amarelo))
        total = leitura.total_do_boss(True)
        assert total == pytest.approx(esperado, abs=0.02)
        assert total < anterior, "o total do boss SUBIU entre dois passos"
        anterior = total


def test_na_fase_1_a_vermelha_e_a_vida_inteira():
    leitura = vision.ler_barra_do_alvo(quadro(0.5))
    assert leitura.total_do_boss(False) == pytest.approx(0.5, abs=0.02)
    assert leitura.total_do_boss(True) == pytest.approx(0.25, abs=0.02)


# ===========================================================================
# 3. O VEREDITO DE MORTE
# ===========================================================================

class _Tela:
    """Conta capturas e leituras. Cegueira é ausência de leitura, e sem contador
    ela é indistinguível de "leu e não achou"."""

    def __init__(self, vida=1.0, amarelo=0.0, marcador=False, escore=0.31):
        self.vida = vida
        self.amarelo = amarelo
        self.marcador = marcador
        self.escore = escore
        self.capturas = 0
        self.leituras_do_marcador = 0

    def instalar(self, monkeypatch):
        def capturar(_h):
            self.capturas += 1
            return quadro(self.vida, self.amarelo)

        def marcador(_q, _t):
            self.leituras_do_marcador += 1
            return self.marcador, self.escore

        monkeypatch.setattr(vision, "capture_window", capturar)
        monkeypatch.setattr(vision, "frame_is_blank", lambda _q: False)
        monkeypatch.setattr(vision, "marcador_de_morte", marcador)
        monkeypatch.setattr(combat.vision, "capture_window", capturar)
        monkeypatch.setattr(combat.vision, "frame_is_blank", lambda _q: False)
        monkeypatch.setattr(combat.vision, "marcador_de_morte", marcador)


def _motor(monkeypatch, tela, alvo_id=4823):
    tela.instalar(monkeypatch)
    motor = CombatEngine.__new__(CombatEngine)
    motor.linhas: list[str] = []

    def anotar(f, *a):
        motor.linhas.append(f % a if a else f)

    motor.ctx = SimpleNamespace(
        pid=1, hwnd=2,
        templates=SimpleNamespace(load=lambda _n: "modelo"),
        log=SimpleNamespace(info=anotar, debug=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            error=lambda *a, **k: None),
    )
    motor._target_hybrid = th.TargetHybrid(logger=motor.ctx.log)
    motor._target_hybrid.id_do_alvo = lambda _pid: alvo_id
    motor._na_segunda_fase_do_boss = False
    motor._ultimo_alvo_morto_id = None
    motor._ultima_leitura_do_alvo = None
    motor._ultimo_escore_do_marcador = None
    motor._melhor_escore_do_marcador = None
    return motor


def test_vida_alta_e_VIVO_e_nem_olha_o_marcador(monkeypatch):
    """Acima de 10% o marcador não é consultado -- é custo por nada, e ele tem
    falso positivo MEDIDO com o mob vivo (0,955-0,971 contra limiar 0,85)."""
    tela = _Tela(vida=0.52, marcador=True, escore=0.97)
    motor = _motor(monkeypatch, tela)

    assert motor._alvo_morreu() is False
    assert tela.leituras_do_marcador == 0, (
        "o marcador foi consultado com o mob a 52% de vida"
    )


def test_UMA_captura_por_leitura(monkeypatch):
    """Barra e marcador saem do MESMO quadro: duas capturas em instantes
    diferentes fazem as duas fontes discordarem sobre o mesmo momento."""
    tela = _Tela(vida=0.0, marcador=True, escore=0.97)
    motor = _motor(monkeypatch, tela)

    motor._alvo_morreu()

    assert tela.capturas == 1
    assert tela.leituras_do_marcador == 1


def test_a_tela_NAO_declara_morte_sozinha(monkeypatch):
    """A TELA SÓ SABE DIZER "AINDA VIVO" -- assimetria de propósito.

    O `EnemyDead.png` tem falso positivo MEDIDO com o mob VIVO (escore
    0,955-0,971 contra limiar 0,85, com o mob em 35 de vida, 20/08/2026). O que
    o segurava era só ser consultado abaixo de 10% de barra; com a memória na
    frente esse resguardo saiu do caminho normal, e sobrou uma RESERVA capaz de
    declarar morte com um template que erra.

    É a explicação do *"vi um TAB aqui sem o mob ter morrido"*: basta a entidade
    faltar no array por um ciclo (medido: 1 em ~45) com a barra num vão de
    redesenho.

    Hoje a resposta é NÃO SEI -- e "não sei" nunca gasta TAB.
    """
    tela = _Tela(vida=0.0, marcador=True, escore=0.97)
    motor = _motor(monkeypatch, tela)

    assert motor._alvo_morreu() is None
    assert "só a memória declara morte" in motor._ultima_leitura_do_alvo.motivo


def test_com_o_interruptor_DESLIGADO_a_tela_volta_a_matar(monkeypatch):
    """O caminho antigo continua inteiro, e é ele que prova de onde vinha o TAB
    fantasma: desligado o interruptor, a mesma leitura vira morte."""
    monkeypatch.setattr(combat, "SO_A_MEMORIA_DECLARA_MORTE", False)
    tela = _Tela(vida=0.0, marcador=True, escore=0.97)
    motor = _motor(monkeypatch, tela)

    assert motor._alvo_morreu() is True


def test_barra_vazia_SEM_marcador_NAO_e_morte(monkeypatch):
    """A regra do usuário ao pé da letra: *"caso não bata com o EnemyDead.png o
    bot vai continuar rotacionando skill antes do TAB, pois provavelmente sobrou
    um pouco de vida que o TargetHybrid não identificou"*."""
    tela = _Tela(vida=0.0, marcador=False, escore=0.31)
    motor = _motor(monkeypatch, tela)

    assert motor._alvo_morreu() is False
    assert "sobrou vida" in motor._ultima_leitura_do_alvo.motivo


def test_a_MESMA_morte_nao_sai_duas_vezes(monkeypatch):
    """O cadáver fica selecionável por 7 a 13 s (medido em 20/08/2026). Sem esta
    trava ele gastaria um TAB por leitura enquanto estivesse ali.

    Pela TELA, com o interruptor desligado -- ver
    `test_a_tela_NAO_declara_morte_sozinha`. O mesmo pela MEMÓRIA está em
    `tests/test_alvo_pela_memoria.py`."""
    monkeypatch.setattr(combat, "SO_A_MEMORIA_DECLARA_MORTE", False)
    tela = _Tela(vida=0.0, marcador=True, escore=0.97)
    motor = _motor(monkeypatch, tela)

    assert motor._alvo_morreu() is True
    assert motor._alvo_morreu() is False
    assert motor._alvo_morreu() is False


def test_alvo_NOVO_pode_morrer_de_novo(monkeypatch):
    """A trava é por IDENTIDADE, não por tempo -- senão o segundo mob da fase
    nunca poderia ser declarado morto.

    Pela TELA, com o interruptor desligado."""
    monkeypatch.setattr(combat, "SO_A_MEMORIA_DECLARA_MORTE", False)
    tela = _Tela(vida=0.0, marcador=True, escore=0.97)
    motor = _motor(monkeypatch, tela)
    assert motor._alvo_morreu() is True

    motor._target_hybrid.id_do_alvo = lambda _pid: 4901
    assert motor._alvo_morreu() is True


def test_sem_alvo_nao_e_morte(monkeypatch):
    tela = _Tela(vida=0.0, marcador=True)
    motor = _motor(monkeypatch, tela, alvo_id=0)
    assert motor._alvo_morreu() is False
    assert tela.capturas == 0, "capturou a tela sem ter alvo"


def test_barra_ilegivel_e_NAO_SEI_e_nao_gasta_TAB(monkeypatch):
    tela = _Tela()
    motor = _motor(monkeypatch, tela)
    monkeypatch.setattr(combat.vision, "capture_window",
                        lambda _h: np.zeros((768, 1024, 3), np.uint8))

    assert motor._alvo_morreu() is None


def test_marcador_ilegivel_e_NAO_SEI(monkeypatch):
    """Falha ao olhar o marcador não é "não morreu" -- é "não sei"."""
    tela = _Tela(vida=0.0)
    motor = _motor(monkeypatch, tela)
    monkeypatch.setattr(combat.vision, "marcador_de_morte",
                        lambda _q, _t: (None, None))

    assert motor._alvo_morreu() is None


# ===========================================================================
# 4. O LOG DA VIDA -- é ele que o usuário lê na tela do bot
# ===========================================================================

def test_a_vida_aparece_no_log_a_cada_mudanca(monkeypatch):
    tela = _Tela(vida=1.0)
    motor = _motor(monkeypatch, tela)

    for vida in (1.0, 0.86, 0.52, 0.20):
        tela.vida = vida
        motor._alvo_morreu()

    do_alvo = [linha for linha in motor.linhas if linha.startswith("ALVO #")]
    assert len(do_alvo) == 4, do_alvo
    assert "100.0%" in do_alvo[0] and "alvo novo" in do_alvo[0]
    assert "85.8%" in do_alvo[1]
    assert "52.2%" in do_alvo[2]
    assert "20.1%" in do_alvo[3]


def test_o_log_nao_repete_a_mesma_vida(monkeypatch):
    """Por MUDANÇA, não por leitura: a leitura roda a cada 0,15 s e uma luta
    renderia ~250 linhas, num arquivo que guarda 500 no total."""
    tela = _Tela(vida=0.52)
    motor = _motor(monkeypatch, tela)

    for _ in range(10):
        motor._alvo_morreu()

    do_alvo = [linha for linha in motor.linhas if linha.startswith("ALVO #")]
    assert len(do_alvo) == 1, do_alvo


def test_o_log_mostra_o_ESCORE_do_marcador(monkeypatch):
    """Pedido do usuário: *"vamos também colocar um log para eu ir acompanhando,
    pois caso continue a falhar eu irei substituir a imagem"*.

    O escore continua indo para o log mesmo quando a tela não pode declarar
    morte -- é ele que diz se o template ainda serve."""
    monkeypatch.setattr(combat, "SO_A_MEMORIA_DECLARA_MORTE", False)
    tela = _Tela(vida=0.0, marcador=True, escore=0.97)
    motor = _motor(monkeypatch, tela)

    motor._alvo_morreu()

    assert any("escore=0.97" in linha for linha in motor.linhas), motor.linhas


def test_o_log_avisa_quando_nao_consegue_ler_a_barra(monkeypatch):
    """Ausência de barra é dita em voz alta. Sem isso, "não consegui ler" e "o
    mob está cheio" ficam iguais no log -- e foi essa confusão que escondeu a
    régua quebrada por semanas."""
    tela = _Tela()
    motor = _motor(monkeypatch, tela)
    monkeypatch.setattr(combat.vision, "capture_window",
                        lambda _h: np.zeros((768, 1024, 3), np.uint8))

    motor._alvo_morreu()
    motor._alvo_morreu()

    avisos = [linha for linha in motor.linhas if "não consegui ler a barra" in linha]
    assert len(avisos) == 1, "o aviso tem de sair UMA vez por alvo"


# ===========================================================================
# 5. O VIGIA NÃO GUARDA JANELA
# ===========================================================================

def test_o_vigia_nao_guarda_pid_nem_hwnd():
    """Eles mudam no relogin. Guardá-los era ler processo morto e capturar
    janela inexistente, em silêncio, para sempre."""
    import inspect
    parametros = set(inspect.signature(th.TargetHybrid.__init__).parameters)
    assert "pid" not in parametros and "hwnd" not in parametros
    for metodo in (th.TargetHybrid.ler, th.TargetHybrid.id_do_alvo):
        assert "pid" in inspect.signature(metodo).parameters


def test_o_handle_e_reaberto_quando_o_pid_muda(monkeypatch):
    """RELOGIN TROCA O PID. Guardar o handle era ler a memória de um processo
    morto para sempre, em silêncio."""
    abertos = []

    class _Memoria:
        def __init__(self, pid):
            abertos.append(pid)

        def id_do_alvo(self):
            return 7

        def alvo_atual(self):
            return None

        def close(self):
            pass

    monkeypatch.setattr(th, "Memory", _Memoria)
    vigia = th.TargetHybrid()

    vigia.id_do_alvo(100)
    vigia.id_do_alvo(100)
    vigia.id_do_alvo(200)

    assert abertos == [100, 200], f"reabriu à toa ou não reabriu: {abertos}"


def test_o_vigia_usa_UM_Memory_e_nao_um_pymem_cru():
    """A leitura do alvo por memória mora em `Memory.alvo_atual`.

    Ter um `pymem` cru aqui era ter DOIS mapas de offsets para manter em
    sincronia -- e o segundo mapa nunca é o que alguém lembra de atualizar.
    """
    import ast
    import inspect

    fonte = ast.parse(inspect.getsource(th))
    importados = {n.name for no in ast.walk(fonte)
                  if isinstance(no, ast.Import) for n in no.names}
    assert "pymem" not in importados


def test_o_snapshot_do_contexto_nao_captura_tela():
    """`snapshot()` roda em alta frequência, em todas as contas, inclusive fora
    de combate. A vida do alvo é lida onde ela decide algo: no laço da luta."""
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.context import BotContext

    arvore = ast.parse(textwrap.dedent(inspect.getsource(BotContext.snapshot)))
    chamadas = {no.func.attr for no in ast.walk(arvore)
                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)}
    assert "capture_window" not in chamadas
    assert "ler" not in chamadas, "o snapshot voltou a ler a tela do alvo"
    assert "id_do_alvo" in chamadas
