"""A COMIDA DO PET, DE PONTA A PONTA -- conserto de 27/08/2026.

O usuário relatou duas coisas no mesmo dia, e elas tinham causas diferentes:

    *"Sobre o BOT BC eu estou acompanhando pela quantidade de pet food que eu
     tenho e não está baixando, eu estou a horas com a quantidade 20."*

    *"No módulo APP tem que melhorar para também fazer que nem o BOT BC
     `PetFeeder(vence_em=ctx.settings.pet.proxima_comida_em or None)` para
     garantir sempre a comida do pet."*

=========================================================================
OS DEFEITOS, MEDIDOS NO `logs/dev/blazes-dev.jsonl`
=========================================================================

**APP -- a grade amnésica.** O executor nascia com `PetFeeder()` sem grade. Cada
reinício caía no braço "grade não iniciada" e RE-ANCORAVA o vencimento em
`agora + intervalo`. A conta `blazestpas` (51 min) reiniciou 12 vezes em 88
minutos; nenhuma sessão viveu 51. Resultado: **zero refeições em 123 minutos**,
com o relógio sempre parecendo correto.

**BC -- o aperto que a ação seguinte cancela.** O log tem três alimentações com
a mesma forma: comida em `+0.0s`, tecla da montaria em `+0.7s`. A espera de
dentro do `feed_pet` era `tick(0.5)`, e montar interrompe o uso do item -- o log
dizia que alimentou e a bolsa dizia que não.

**BC -- a corrida com a barra de atalhos.** A troca de página (`P`) e a tecla do
slot (`6`) saíam no MESMO instante, três vezes de três. Os outros consumidores
sobrevivem porque insistem e conferem; a comida apertava uma vez e acreditava.

**BC -- em batalha a tecla é engolida e a grade avançava.** O APP já barrava a
comida em combate; o BC não, e `_do_preparar_dentro` roda logo depois de entrar na cave.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
import time
from types import SimpleNamespace

import pytest

from blazesbot import config
from blazesbot.bot import combate as motor_de_combate
from blazesbot.bot import hotbar
from blazesbot.bot.app import executor as app_mod
from blazesbot.bot.bc.combat import CombatEngine
from blazesbot.core import pet as pet_mod
from blazesbot.core.pet import PetFeeder

# ===========================================================================
# 1. O `PetFeeder` GRAVA A GRADE -- nos DOIS momentos em que ela muda
# ===========================================================================

def test_grava_ao_registrar_a_refeicao(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    gravado: list[float] = []
    feeder = PetFeeder(vence_em=1000.0, gravar=gravado.append)

    feeder.registrar_alimentacao(50)

    assert gravado == [pytest.approx(1000.0 + 50 * 60)]


def test_grava_TAMBEM_quando_a_grade_apenas_NASCE(monkeypatch):
    """O conserto do APP mora aqui.

    Sem esta gravação, uma sessão mais curta que o intervalo joga fora o relógio
    que ela mesma acabou de criar -- e a próxima sessão cria outro.
    """
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    gravado: list[float] = []
    feeder = PetFeeder(gravar=gravado.append)

    assert feeder.deve_alimentar(50) is False, "não devia gastar ração na largada"
    assert gravado == [pytest.approx(1000.0 + 50 * 60)], (
        "a grade nasceu e não foi para o disco: é o defeito do APP de volta")


def test_sem_gravador_nada_quebra(monkeypatch):
    """`gravar=None` continua válido -- é como o `PetFeeder` é usado em teste e
    em qualquer chamador que não persista."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    feeder = PetFeeder(vence_em=1000.0)
    feeder.registrar_alimentacao(50)
    assert feeder.vence_em == pytest.approx(1000.0 + 50 * 60)


# ===========================================================================
# 2. A REGRESSÃO MEDIDA: 12 REINÍCIOS CURTOS
# ===========================================================================

def _doze_sessoes(monkeypatch, *, com_disco: bool) -> tuple[int, float]:
    """Doze sessões de 7 min seguidas, intervalo de 51 -- a forma do log.

    Devolve (refeições, tempo total). A única coisa que pode atravessar o
    reinício é o disco.
    """
    agora = [0.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    disco: dict[str, float] = {}
    refeicoes = 0

    for _ in range(12):
        feeder = PetFeeder(
            vence_em=disco.get("vence") if com_disco else None,
            gravar=(lambda v: disco.__setitem__("vence", v)) if com_disco
            else None,
        )
        fim = agora[0] + 7 * 60
        while agora[0] < fim:                      # o laço da macro
            if feeder.deve_alimentar(51):
                feeder.registrar_alimentacao(51)
                refeicoes += 1
            agora[0] += 20.0                       # uma volta de macro
    return refeicoes, agora[0]


def test_doze_reinicios_curtos_SEM_disco_NUNCA_alimentam(monkeypatch):
    """O defeito, reproduzido. Se este teste um dia passar a alimentar, a
    simulação parou de simular o que aconteceu -- não é boa notícia."""
    refeicoes, total = _doze_sessoes(monkeypatch, com_disco=False)

    assert total >= 84 * 60, "a simulação tem que passar de um intervalo"
    assert refeicoes == 0, "o defeito medido não se reproduziu"


def test_os_MESMOS_reinicios_COM_disco_alimentam(monkeypatch):
    """O conserto: a grade atravessa o reinício e vence dentro de uma sessão."""
    refeicoes, total = _doze_sessoes(monkeypatch, com_disco=True)

    assert refeicoes == 1, (
        f"{total / 60:.0f} min de sessões com intervalo de 51 tinham que dar "
        f"1 refeição, deram {refeicoes}")


# ===========================================================================
# 3. O APP LÊ E GRAVA A GRADE -- a fiação, não só a lógica
# ===========================================================================

def _executor_do_app(**kw):
    """Um `ExecutorDeMacro` de verdade, com o mínimo para o pet funcionar."""
    linhas: list[str] = []
    log = SimpleNamespace(
        info=lambda f, *a: linhas.append(f % a if a else f),
        warning=lambda f, *a: linhas.append(f % a if a else f),
        error=lambda f, *a: linhas.append("ERRO " + (f % a if a else f)),
        debug=lambda *a, **k: None)
    padrao = dict(
        hwnd=1, fonte_dos_passos=lambda: [], continuar=lambda: False, log=log,
        tecla_do_pet_food="6", feed_every_minutes=lambda: 51,
        em_batalha=lambda: False)
    padrao.update(kw)
    e = app_mod.ExecutorDeMacro(**padrao)
    e.linhas_do_log = linhas
    return e


def test_o_executor_do_APP_aceita_e_USA_a_grade_do_disco(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    e = _executor_do_app(grade_da_comida=lambda: 9000.0)

    assert e._pet_feeder.vence_em == pytest.approx(9000.0)
    assert e.feed_pet() is False, "a grade do disco ainda não venceu"


def test_o_executor_do_APP_GRAVA_a_grade(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    gravado: list[float] = []
    e = _executor_do_app(grade_da_comida=lambda: None,
                         gravar_grade_da_comida=gravado.append)

    # A primeira pergunta faz a grade NASCER, e ela vai para o disco na hora.
    assert e.feed_pet() is False
    assert gravado == [pytest.approx(1000.0 + 51 * 60)]


def test_um_gravador_que_LEVANTA_nao_derruba_a_macro(monkeypatch):
    """Contrato do `PetFeeder`: quem grava não levanta. O executor embrulha."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)

    def explodir(_vence):
        raise OSError("disco cheio")

    e = _executor_do_app(gravar_grade_da_comida=explodir)
    assert e.feed_pet() is False          # a grade nasce, a gravação falha
    assert e._pet_feeder.vence_em is not None


def test_uma_leitura_da_grade_que_LEVANTA_nao_derruba_o_construtor(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)

    def explodir():
        raise OSError("config ilegível")

    e = _executor_do_app(grade_da_comida=explodir)
    assert e._pet_feeder.vence_em is None


# ===========================================================================
# 4. A ALIMENTAÇÃO DE LARGADA ESPERA A GARANTIA DA BARRA DE ATALHOS
# ===========================================================================

def test_rodar_NAO_alimenta_antes_do_primeiro_antes_da_volta():
    """Era o único aperto de tecla do APP com a página da barra não verificada.

    O teste é no CÓDIGO e não no comportamento de propósito: `rodar()` é um laço
    e o que se quer travar é a AUSÊNCIA da chamada.
    """
    arvore = ast.parse(
        textwrap.dedent(inspect.getsource(app_mod.ExecutorDeMacro.rodar)))
    chamadas = [n.func.attr for n in ast.walk(arvore)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert "feed_pet" not in chamadas, (
        "`rodar()` voltou a alimentar antes da garantia da barra de atalhos")


def test_feed_on_start_alimenta_na_PRIMEIRA_volta(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    monkeypatch.setattr(app_mod, "SEGUNDOS_PARA_A_COMIDA_SER_USADA", 0.0)
    teclas: list[str] = []
    e = _executor_do_app(feed_on_start=True)
    e.input = SimpleNamespace(key=lambda k: teclas.append(k) or True)

    assert e.feed_pet() is True, "a largada não foi cobrada"
    assert teclas == ["6"]
    assert e.feed_pet() is False, "cobrou a largada duas vezes"


def test_sem_feed_on_start_a_largada_NAO_gasta_racao(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    e = _executor_do_app(feed_on_start=False)
    assert e.feed_pet() is False


def test_tecla_que_o_input_recusa_NAO_avanca_a_grade(monkeypatch):
    """Alimentar zero vezes com o relógio andando é o defeito que se consertou."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    e = _executor_do_app(feed_on_start=True)
    e.input = SimpleNamespace(key=lambda _k: False)

    assert e.feed_pet() is False
    assert e.alimentacoes_de_pet == 0
    assert e._pet_feeder.vence_em is None, "a grade avançou sem a tecla sair"


# ===========================================================================
# 5. O BC: EM BATALHA A GRADE NÃO AVANÇA
# ===========================================================================

def _motor_bc(*, em_batalha=False, montado=False, tecla="6", intervalo=50,
              vence_em=1000.0):
    linhas: list[str] = []
    motor = CombatEngine.__new__(CombatEngine)
    motor.teclas: list[str] = []
    motor.esperas: list[float] = []
    motor.ctx = SimpleNamespace(
        account_login="teste",
        # A BARREIRA DA COMIDA É POR JANELA (`core/pet._COMIDA_EM`): sem `hwnd`
        # o motor não tem onde marcar que a tecla saiu.
        hwnd=4321,
        settings=SimpleNamespace(
            keys=SimpleNamespace(pet_food=tecla),
            pet=SimpleNamespace(feed_every_minutes=intervalo)),
        log=SimpleNamespace(
            info=lambda f, *a: linhas.append(f % a if a else f),
            error=lambda f, *a: linhas.append("ERRO " + (f % a if a else f)),
            warning=lambda f, *a: linhas.append(f % a if a else f),
            debug=lambda *a, **k: None),
        memory=SimpleNamespace(
            is_mounted=lambda: montado, in_battle=lambda: em_batalha,
            is_sitting=lambda: False, pet_active=lambda: True,
            position=lambda: (200, 40), location=lambda: "Cave"),
        press=lambda k: motor.teclas.append(k) or True,
        tick=lambda s=0.2: motor.esperas.append(s),
    )
    motor.linhas = linhas
    motor._pet_feeder = PetFeeder(vence_em=vence_em)
    motor._preparar_para_agir = (
        lambda _motivo, mesmo_fora_da_cave=False: True)
    return motor


@pytest.fixture
def _hotbar_falsa(monkeypatch):
    """A barra é conferida em outro teste; aqui ela só registra o motivo."""
    chamadas: list[str] = []
    monkeypatch.setattr(
        motor_de_combate.hotbar, "garantir_pagina_1",
        lambda _ctx, motivo="", forcar=False: chamadas.append(motivo))
    return chamadas


def test_o_BC_NAO_alimenta_em_batalha_e_a_grade_NAO_avanca(
        monkeypatch, _hotbar_falsa):
    """A tecla de alimento é ignorada pelo jogo em combate -- o APP já sabia
    disso, o BC não. E `_do_preparar_dentro` roda logo depois de entrar na cave."""
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc(em_batalha=True)

    assert motor.feed_pet() is False
    assert motor.teclas == [], "apertou a tecla em batalha"
    assert motor._pet_feeder.vence_em == pytest.approx(1000.0), (
        "a grade avançou com a tecla engolida pelo jogo")


def test_em_batalha_com_FORCE_alimenta(monkeypatch, _hotbar_falsa):
    """`force` é o pedido explícito de quem chama; ele continua mandando."""
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc(em_batalha=True)
    assert motor.feed_pet(force=True) is True
    assert motor.teclas == ["6"]


def test_batalha_ILEGIVEL_nao_bloqueia(monkeypatch, _hotbar_falsa):
    """"Não sei" não bloqueia -- bot mudo é pior que o defeito."""
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc(em_batalha=None)
    assert motor.feed_pet() is True


def test_o_BC_garante_a_pagina_1_ANTES_de_apertar(monkeypatch, _hotbar_falsa):
    """Antes ela vinha de carona do `ensure_pet`, e só com `summon_on_login`
    ligado. Desligado, a tecla saía com a página NÃO verificada."""
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc()

    assert motor.feed_pet() is True
    assert _hotbar_falsa == ["alimentar o pet"]


def test_o_BC_MARCA_a_comida_em_vez_de_dormir(monkeypatch, _hotbar_falsa):
    """16/09/2026: dormir aqui dentro NUNCA poderia resolver.

    Quem cancela o item é a ação seguinte -- montar --, e ela mora em outro
    arquivo. Com `tick(1,5)` aqui, a montaria saía aos 1,65 s: 150 ms fora da
    janela, cancelando a comida em TODA refeição (felicidade de 94 para 45 em
    20 h, com as 26 refeições acontecendo na hora certa).

    Agora `feed_pet` MARCA o instante e quem paga é o portão da montaria, que
    espera só o que falta. Run que não se move não paga nada.
    """
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc()
    pet_mod._COMIDA_EM.clear()

    assert motor.feed_pet() is True
    assert motor.esperas == [], "voltou a dormir dentro do feed_pet"
    assert pet_mod.falta_da_comida(motor.ctx.hwnd) > 0, (
        "a comida não ficou marcada; o portão da montaria não tem o que esperar")


def test_a_barreira_da_comida_e_MAIOR_que_o_atraso_da_montaria():
    """A montaria foi acionada 1,65 s depois da comida no log de 16/09/2026.

    Qualquer valor abaixo disso repete o defeito -- e o custo de ser generoso é
    4 s por refeição, uma vez a cada 50 min.
    """
    assert pet_mod.SEGUNDOS_PARA_A_COMIDA_SER_USADA >= 2.0, (
        "1,65 s é o atraso MEDIDO da montaria; a barreira tem que cobri-lo")


def test_o_PORTAO_DA_MONTARIA_espera_a_comida():
    """A barreira mora onde todo deslocamento passa, e não em quem alimenta."""
    import inspect
    import textwrap

    from blazesbot.bot.navegacao import Navigator

    fonte = textwrap.dedent(
        inspect.getsource(Navigator.garantir_montaria_para_andar))
    assert "esperar_a_comida" in fonte, (
        "o portão da montaria parou de esperar a comida -- montar cancela o item")


def test_tecla_recusada_pelo_input_NAO_avanca_a_grade_no_BC(
        monkeypatch, _hotbar_falsa):
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc()
    motor.ctx.press = lambda _k: False
    monkeypatch.setattr(motor_de_combate.diario, "registrar_evento",
                        lambda *a, **k: None)

    assert motor.feed_pet() is False
    assert motor._pet_feeder.vence_em == pytest.approx(1000.0)


def test_o_BC_grava_a_grade_pelo_PetFeeder():
    """A gravação deixou de ser uma chamada solta depois de alimentar: agora é o
    `gravar` do `PetFeeder`, que cobre TODA mudança da grade."""
    assert "gravar=self._gravar_grade_da_comida" in inspect.getsource(
        CombatEngine.__init__)
    assert "_gravar_grade_da_comida()" not in inspect.getsource(
        CombatEngine.feed_pet), (
        "voltou a gravar à mão; a grade que só NASCE ficaria de fora")


# ===========================================================================
# 6. A BARRA DE ATALHOS ASSENTA ANTES DE DEVOLVER
# ===========================================================================

def test_o_caminho_da_TECLA_assenta():
    """Medido: `P` e `6` saíam no MESMO instante, três vezes de três."""
    esperas: list[float] = []
    hotbar.ir_para_a_pagina_1(
        clicar=lambda _p: None, ponto=(0, 0), esperar=esperas.append,
        apertar=lambda _t: None, tecla="P")
    assert esperas == [pytest.approx(hotbar.ASSENTAR_A_PAGINA)]


def test_o_caminho_do_CLIQUE_assenta_depois_do_ULTIMO_clique():
    cliques: list[tuple[int, int]] = []
    esperas: list[float] = []
    hotbar.ir_para_a_pagina_1(
        clicar=cliques.append, ponto=(5, 6), esperar=esperas.append)

    assert len(cliques) == hotbar.CLIQUES_PARA_VOLTAR_A_PAGINA_1
    assert esperas[-1] == pytest.approx(hotbar.ASSENTAR_A_PAGINA)
    assert esperas[:-1] == [pytest.approx(hotbar.ENTRE_CLIQUES)] * (
        hotbar.CLIQUES_PARA_VOLTAR_A_PAGINA_1 - 1)


def test_o_assentamento_e_maior_que_um_quadro():
    """60 fps = 16,7 ms. Abaixo disso a barra pode não ter trocado ainda."""
    assert hotbar.ASSENTAR_A_PAGINA > 1 / 60


# ===========================================================================
# 7. A ESPERA PELO LUGAR CERTO TEM PRAZO -- 13/09/2026
# ===========================================================================
#
# O incidente: conta `creubo`, HH, intervalo de 50 min. Em 13/09/2026 o bot
# ficou 46 minutos em `ATE_A_PORTA` (das 14:06:22 às 14:52:42), a refeição
# venceu às 14:27 dentro dessa janela, e a comida só saiu às 14:54:28 -- 77
# minutos depois da anterior. O pet quase sumiu.
#
# A causa não era a grade (ela segurou a refeição certinho, e a seguinte veio 26
# min depois, recuperando a cadência). Era a LATÊNCIA: o único ponto de
# alimentação era o preparo de entrada, e a espera por ele não tinha teto.


def _feeder_atrasado(monkeypatch, minutos_de_atraso: float, intervalo=50):
    """Um `PetFeeder` cuja refeição venceu há N minutos."""
    agora = 100_000.0
    monkeypatch.setattr(time, "time", lambda: agora)
    return PetFeeder(vence_em=agora - minutos_de_atraso * 60)


def test_a_fome_e_urgente_so_DEPOIS_do_limite(monkeypatch):
    limite = pet_mod.LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS
    assert _feeder_atrasado(monkeypatch, limite - 0.1).a_fome_e_urgente(50) is False
    assert _feeder_atrasado(monkeypatch, limite + 0.1).a_fome_e_urgente(50) is True


def test_o_limite_fica_ACIMA_da_cauda_normal_e_ABAIXO_de_um_intervalo():
    """Os dois lados do número, e os dois são medidos.

    ACIMA da p90 das janelas de alimentação (10,8 min medidos em 128 janelas da
    HH), senão dispara em operação saudável e o bot desmonta à toa.

    ABAIXO do menor intervalo configurável, senão a refeição chega ao ponto em
    que `registrar_alimentacao` RE-ANCORA a grade -- e aí a refeição do dia é
    perdida de verdade. É esta metade que sustenta a conta de 28,8 refeições/dia.
    """
    limite = pet_mod.LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS
    assert limite > 10.8, "dispararia na cauda NORMAL das janelas medidas"
    assert limite < config.PET_FEED_MINUTOS_MIN, (
        "atraso de um intervalo inteiro re-ancora a grade e perde a refeição")


def test_as_leituras_de_fome_NAO_MUTAM_a_grade(monkeypatch):
    """São chamadas a cada volta de um laço de 20 voltas/s. Se mutassem ou
    gravassem, a conferência viraria escrita em disco em rajada."""
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    gravado: list[float] = []
    f = PetFeeder(gravar=gravado.append)

    assert f.esta_com_fome(50) is False
    assert f.atraso_minutos(50) == 0.0
    assert f.a_fome_e_urgente(50) is False

    assert f.vence_em is None, "a leitura fez a grade nascer"
    assert gravado == [], "a leitura gravou no disco"


def test_a_fome_e_DERIVADA_da_grade_e_fica_LATCHED(monkeypatch):
    """Não existe `pet_needs_food` guardado, e não precisa existir: a fome
    continua verdadeira volta após volta até alguém alimentar."""
    agora = [1000.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    f = PetFeeder(vence_em=1000.0)

    for _ in range(5):
        agora[0] += 60
        assert f.esta_com_fome(50) is True, "a fome apagou sozinha"

    f.registrar_alimentacao(50)
    assert f.esta_com_fome(50) is False, "alimentou e a fome continuou"


def test_a_cadencia_segura_a_RAJADA_de_tentativas(monkeypatch):
    """O laço da HH roda a cada 0,05 s. Sem cadência, uma recusa de desmonte
    viraria 20 tentativas por segundo."""
    agora = [1000.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    f = PetFeeder(vence_em=0.0)

    assert f.tentativa_liberada() is True
    liberadas = 0
    for _ in range(400):                      # 20 s de laço a 0,05 s
        agora[0] += 0.05
        if f.tentativa_liberada():
            liberadas += 1
    assert liberadas == 0, f"{liberadas} tentativas em 20 s de laço"

    agora[0] += pet_mod.CADENCIA_DAS_TENTATIVAS_DE_COMIDA
    assert f.tentativa_liberada() is True


# ===========================================================================
# 8. A REDE DE SEGURANÇA NO LAÇO (HH e BC)
# ===========================================================================

def test_a_rede_NAO_age_enquanto_o_atraso_esta_dentro_do_prazo(
        monkeypatch, _hotbar_falsa):
    """O caminho normal continua sendo o preparo de entrada. A rede fica quieta
    -- e QUIETA é literal: nem tecla, nem log."""
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc(vence_em=1999.0)             # venceu há 1 segundo

    assert motor.cuidar_da_comida_no_laco(em_transito=False) is False
    assert motor.teclas == []
    assert motor.linhas == [], "falou sem agir; num laço de 20 voltas/s isso inunda o log"


def test_a_rede_ALIMENTA_quando_o_atraso_passa_do_prazo(monkeypatch, _hotbar_falsa):
    """O caso `creubo`: 46 min preso fora da cave com a refeição vencida."""
    agora = 2000.0
    monkeypatch.setattr(time, "time", lambda: agora)
    atraso = pet_mod.LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS + 1
    motor = _motor_bc(vence_em=agora - atraso * 60)

    assert motor.cuidar_da_comida_no_laco(em_transito=False) is True
    assert motor.teclas == ["6"]


def test_atrasada_ela_fura_o_veto_de_NAO_DESMONTAR_fora_da_cave(
        monkeypatch, _hotbar_falsa):
    """A regra de 25/08/2026 é preferência, não dogma: pet sem comida some.

    Este teste usa o `_preparar_para_agir` DE VERDADE, porque é justamente ele
    que continha o veto.
    """
    agora = 2000.0
    monkeypatch.setattr(time, "time", lambda: agora)
    atraso = pet_mod.LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS + 1
    motor = _motor_bc(montado=True, vence_em=agora - atraso * 60)
    del motor._preparar_para_agir                  # o do motor, não o dublê
    motor._esta_fora_da_cave = lambda: True        # fora da cave
    motor.desmontou = False

    def desmontar():
        motor.desmontou = True
        return True

    motor.nav = SimpleNamespace(ensure_dismounted=desmontar)

    assert motor.cuidar_da_comida_no_laco(em_transito=False) is True
    assert motor.desmontou is True, "o veto barrou uma refeição já atrasada"
    assert motor.teclas == ["6"]


def test_NO_PRAZO_o_veto_de_fora_da_cave_CONTINUA_valendo(monkeypatch, _hotbar_falsa):
    """A saída de emergência não pode virar a regra: sem atraso, nada muda."""
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc(montado=True, vence_em=1999.0)
    del motor._preparar_para_agir
    motor._esta_fora_da_cave = lambda: True
    motor.desmontou = False
    motor.nav = SimpleNamespace(
        ensure_dismounted=lambda: motor.__setattr__("desmontou", True) or True)

    assert motor.feed_pet() is False
    assert motor.desmontou is False, "desmontou fora da cave sem urgência"


def test_a_rede_NUNCA_alimenta_em_batalha(monkeypatch, _hotbar_falsa):
    """A batalha não cede nem com urgência: a tecla é engolida pelo jogo, e
    registrar a refeição assim seria fome com o relógio dizendo que comeu."""
    agora = 2000.0
    monkeypatch.setattr(time, "time", lambda: agora)
    atraso = pet_mod.LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS + 10
    motor = _motor_bc(em_batalha=True, vence_em=agora - atraso * 60)

    assert motor.cuidar_da_comida_no_laco(em_transito=False) is False
    assert motor.teclas == []
    assert motor.linhas == [], "a recusa em batalha falou no laço"
    assert motor._pet_feeder.vence_em == pytest.approx(agora - atraso * 60), (
        "a grade avançou com a tecla engolida")


def test_EM_TRANSITO_espera_o_prazo_mas_nao_espera_para_sempre(
        monkeypatch, _hotbar_falsa):
    """Dentro da cave, parar é parar com o trem de mobs em cima -- então a
    travessia tem preferência. Até a refeição ficar velha demais."""
    agora = [2000.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    motor = _motor_bc(vence_em=1999.0)

    assert motor.feed_pet(em_transito=True) is False, "parou no meio da travessia"
    assert motor.teclas == []

    agora[0] += (pet_mod.LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS + 1) * 60
    assert motor.feed_pet(em_transito=True) is True, "esperou além do prazo"


# ===========================================================================
# 9. OS TRÊS ECOSSISTEMAS CHAMAM A REDE -- a fiação
# ===========================================================================

def _chamadas(funcao) -> list[str]:
    arvore = ast.parse(textwrap.dedent(inspect.getsource(funcao)))
    return [n.func.attr for n in ast.walk(arvore)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]


def test_o_laco_da_HH_confere_a_comida_a_cada_volta():
    from blazesbot.bot.hh.routine import HHRoutine
    assert "cuidar_da_comida_no_laco" in _chamadas(HHRoutine.run)


def test_o_laco_da_BC_confere_a_comida_a_cada_volta():
    from blazesbot.bot.bc.routine import BossRushRoutine
    assert "cuidar_da_comida_no_laco" in _chamadas(BossRushRoutine.run)


def test_o_laco_do_APP_acusa_a_comida_presa_pela_batalha():
    """O APP não tem veto de cave para furar -- o bloqueio dele é a mecânica do
    jogo, que não se fura. Então ele ACUSA em vez de forçar."""
    assert "_avisar_se_a_comida_esta_presa" in _chamadas(
        app_mod.ExecutorDeMacro._uma_volta_simples)


def test_o_aviso_do_APP_sai_UMA_vez_por_luta_longa(monkeypatch):
    """Sem cadência, uma luta de 10 min escreveria a mesma linha centenas de
    vezes -- e log que inunda é log que ninguém lê."""
    agora = [1000.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    e = _executor_do_app(grade_da_comida=lambda: 1.0)   # vencida em 1970

    def avisos() -> list[str]:
        return [l for l in e.linhas_do_log if "não sai de batalha" in l]

    e._avisar_se_a_comida_esta_presa()
    assert len(avisos()) == 1
    for _ in range(50):
        agora[0] += 5
        e._avisar_se_a_comida_esta_presa()
    assert len(avisos()) == 1, "o aviso repetiu dentro da cadência"

    agora[0] += app_mod.CADENCIA_DO_AVISO_DE_COMIDA
    e._avisar_se_a_comida_esta_presa()
    assert len(avisos()) == 2


def test_o_APP_nao_avisa_quando_a_comida_esta_em_dia(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    e = _executor_do_app(grade_da_comida=lambda: 9_000.0)
    e.linhas_do_log.clear()
    e._avisar_se_a_comida_esta_presa()
    assert e.linhas_do_log == []


# ===========================================================================
# 10. A COTA DIÁRIA, QUE É O PEDIDO DO USUÁRIO
# ===========================================================================

def test_a_cota_de_28_refeicoes_por_dia_FECHA_com_a_rede(monkeypatch):
    """*"Se o usuário configura o petfood para cada 50 minutos, a rotina DEVE
    ser executada 28 vezes em 24 horas (com uma sobra final de 40 minutos)."*

    Simula 24 h com a janela de alimentação aparecendo de forma HOSTIL: a cada
    46 minutos, que é a duração do travamento medido em 13/09/2026. Sem prazo, a
    refeição só sai quando a janela aparece e a grade re-ancora; com prazo, a
    rede alimenta no meio e a grade nunca escorrega.
    """
    agora = [0.0]
    monkeypatch.setattr(time, "time", lambda: agora[0])
    intervalo = 50
    f = PetFeeder(vence_em=intervalo * 60.0)
    refeicoes = 0

    while agora[0] < 24 * 3600:
        agora[0] += 30.0                       # uma volta do laço
        if not f.esta_com_fome(intervalo):
            continue
        # A JANELA BOA (preparo de entrada) só aparece a cada 46 min...
        janela_boa = int(agora[0]) % (46 * 60) < 30
        if janela_boa or f.a_fome_e_urgente(intervalo):
            f.registrar_alimentacao(intervalo)
            refeicoes += 1

    assert refeicoes == 28, (
        f"{refeicoes} refeições em 24 h; o usuário exige 28 com intervalo de 50")
