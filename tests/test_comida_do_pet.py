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
comida em combate; o BC não, e `_do_curar` roda logo depois de entrar na cave.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
import time
from types import SimpleNamespace

import pytest

from blazesbot.bot.app import executor as app_mod
from blazesbot.bot.bc import combat as combat_mod
from blazesbot.bot.bc import hotbar
from blazesbot.bot.bc.combat import CombatEngine
from blazesbot.core.pet import SEGUNDOS_PARA_A_COMIDA_SER_USADA, PetFeeder

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
    motor._preparar_para_agir = lambda _motivo: True
    return motor


@pytest.fixture
def _hotbar_falsa(monkeypatch):
    """A barra é conferida em outro teste; aqui ela só registra o motivo."""
    chamadas: list[str] = []
    monkeypatch.setattr(
        combat_mod.hotbar, "garantir_pagina_1",
        lambda _ctx, motivo="", forcar=False: chamadas.append(motivo))
    return chamadas


def test_o_BC_NAO_alimenta_em_batalha_e_a_grade_NAO_avanca(
        monkeypatch, _hotbar_falsa):
    """A tecla de alimento é ignorada pelo jogo em combate -- o APP já sabia
    disso, o BC não. E `_do_curar` roda logo depois de entrar na cave."""
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


def test_o_BC_espera_a_comida_SER_USADA_antes_de_devolver(
        monkeypatch, _hotbar_falsa):
    """Medido: `_do_curar` monta 600 ms depois da comida, e montar cancela o
    item. A espera de dentro do `feed_pet` é o que separa os dois."""
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc()

    assert motor.feed_pet() is True
    assert motor.esperas == [pytest.approx(SEGUNDOS_PARA_A_COMIDA_SER_USADA)]
    assert SEGUNDOS_PARA_A_COMIDA_SER_USADA > 0.5, (
        "0,5 s era o valor que a tecla da montaria atropelava")


def test_tecla_recusada_pelo_input_NAO_avanca_a_grade_no_BC(
        monkeypatch, _hotbar_falsa):
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    motor = _motor_bc()
    motor.ctx.press = lambda _k: False
    monkeypatch.setattr(combat_mod.diario, "registrar_evento",
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
