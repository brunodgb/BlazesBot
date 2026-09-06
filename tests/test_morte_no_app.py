"""O CICLO DA MORTE -- do cadáver de volta ao ponto de farm.

Até 04/09/2026 o APP não tinha nenhum. `Personagem morto detectado` e
`Revivendo` só existiam no BC, e no log de 7 h de duas contas de APP não há UM
evento de morte -- não porque não morreram, mas porque ninguém perguntava. A
macro seguia apertando tecla contra um cadáver.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

import blazesbot.bot.morte as mod
from blazesbot.bot import mural


@pytest.fixture(autouse=True)
def _mural_limpo():
    mural.zerar_o_time_para_teste()
    yield
    mural.zerar_o_time_para_teste()


@pytest.fixture(autouse=True)
def _prazos_curtos(monkeypatch):
    """Os prazos reais são de minuto; aqui interessa a ORDEM, não o relógio."""
    monkeypatch.setattr(mod, "PRAZO_PARA_A_FADA", 0.3)
    monkeypatch.setattr(mod, "EXTENSAO_PELO_FEITICO", 0.6)
    monkeypatch.setattr(mod, "PASSO_DA_ESPERA", 0.01)
    monkeypatch.setattr(mod, "CADENCIA_DO_CONVITE", 0.0)
    monkeypatch.setattr(mod, "TETO_PARA_O_REVIVE_PEGAR", 0.3)
    monkeypatch.setattr(mod, "TETO_DA_REGENERACAO", 0.3)


class _Mundo:
    """O jogo do lado de fora do ciclo: vida, cliques e o que eles causam."""

    def __init__(self, *, fada="fada", convite=False, revive_no_clique=True):
        self.vida = 0.0
        self.batalha = False
        self.sentado = False
        self.fada = fada
        self.convite = convite
        self.revive_no_clique = revive_no_clique
        self.cliques_no_convite = 0
        self.cliques_no_ok = 0
        self.sentadas = 0
        self.voltou = 0
        self.volta_da_certo = True

    # -- o que o ciclo lê
    def vida_pct(self):
        return self.vida

    def em_batalha(self):
        return self.batalha

    def esta_sentado(self):
        return self.sentado

    # -- o que o ciclo faz
    def sentar(self):
        self.sentadas += 1
        self.sentado = not self.sentado

    def clicar_no_convite(self):
        self.cliques_no_convite += 1
        if self.revive_no_clique:
            self.vida = 100.0

    def clicar_no_ok(self):
        self.cliques_no_ok += 1
        if self.revive_no_clique:
            self.vida = 5.0

    def voltar(self):
        self.voltou += 1
        return self.volta_da_certo


def _ciclo(mundo, *, sou_a_fada=False, parar_pct=90.0):
    return mod.CicloDaMorte(
        log=logging.getLogger("teste.morte"),
        meu_login="vitima",
        mural=mural,
        vida_pct=mundo.vida_pct,
        em_batalha=mundo.em_batalha,
        esta_sentado=mundo.esta_sentado,
        apertar_sentar=mundo.sentar,
        fada_do_time=lambda: mundo.fada,
        sou_a_fada=lambda: sou_a_fada,
        convite_na_tela=lambda: mundo.convite,
        clicar_no_convite=mundo.clicar_no_convite,
        clicar_no_ok_da_morte=mundo.clicar_no_ok,
        voltar_ao_ponto=mundo.voltar,
        parar_pct=lambda: parar_pct,
        continuar=lambda: True,
        dormir=lambda _s: True,
        nick=lambda: "Vitima",
    )


# ---------------------------------------------------------------- a pergunta

def test_hp_zero_e_morte():
    mundo = _Mundo()
    assert _ciclo(mundo).estou_morto() is True


def test_sem_leitura_NAO_e_morte():
    """Cego não declara morte: pararia a macro de uma conta viva, que é o
    oposto do que este arquivo existe para consertar."""
    mundo = _Mundo()
    mundo.vida = None
    assert _ciclo(mundo).estou_morto() is False


# ---------------------------------------------------------------- sem Fada

def test_sem_fada_no_time_revive_NA_HORA():
    """*"Caso não tenha fada, revive na hora, não faz sentido esperar."*"""
    mundo = _Mundo(fada=None)

    assert _ciclo(mundo).resolver() is True

    assert mundo.cliques_no_ok == 1
    assert mundo.cliques_no_convite == 0
    assert mundo.voltou == 1


def test_a_PROPRIA_fada_nao_espera_por_si_mesma():
    mundo = _Mundo(fada="fada")
    _ciclo(mundo, sou_a_fada=True).resolver()
    assert mundo.cliques_no_ok == 1


# ---------------------------------------------------------------- com Fada

def test_o_convite_da_Fada_e_aceito_e_o_Ok_da_morte_NAO_e_clicado():
    """São dois "Ok" a 133 px um do outro: o da Fada teleporta para ela, o do
    jogo tira o personagem do spot e cobra mais Exp."""
    mundo = _Mundo(convite=True)

    assert _ciclo(mundo).resolver() is True

    assert mundo.cliques_no_convite == 1
    assert mundo.cliques_no_ok == 0


def test_revivido_POR_FORA_nao_clica_em_nada():
    """A Fada pode reviver sem que a janela chegue a ser vista -- e aí não há o
    que clicar."""
    mundo = _Mundo()
    ciclo = _ciclo(mundo)
    mundo.vida = 100.0                     # de pé antes de qualquer clique

    assert ciclo.resolver() is True
    assert mundo.cliques_no_ok == 0
    assert mundo.cliques_no_convite == 0


def test_vencido_o_prazo_ele_mesmo_revive():
    mundo = _Mundo()                        # Fada online, convite nunca aparece

    assert _ciclo(mundo).resolver() is True

    assert mundo.cliques_no_ok == 1


def test_o_feiticO_em_curso_ESTICA_o_prazo(monkeypatch):
    """Sem esticar, dá para a Fada começar aos 58 s e a vítima se auto-reviver
    aos 60, no meio dos 5 s de preparo: 1168 de mana fora e uma janela de
    convite para quem já está vivo."""
    mundo = _Mundo()
    esperas = []
    monkeypatch.setattr(mod, "PASSO_DA_ESPERA", 0.01)
    ciclo = _ciclo(mundo)
    ciclo._dormir = lambda s: (esperas.append(s), True)[1]
    mural.comecei_a_conjurar("vitima")

    ciclo.resolver()

    # Esticou: esperou MAIS do que o prazo original antes de clicar no Ok.
    assert len(esperas) * 0.01 > mod.PRAZO_PARA_A_FADA


def test_o_time_sabe_que_eu_morri_ENQUANTO_espero():
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)
    vistos = []
    ciclo._clicar_no_ok_da_morte = lambda: (
        vistos.append(mural.esta_morto("vitima")),
        setattr(mundo, "vida", 5.0))

    ciclo.resolver()

    assert vistos == [True], "a fila dos mortos não sabia da morte"
    assert mural.esta_morto("vitima") is False, "o aviso não foi retirado"


# ---------------------------------------------------------------- depois de pé

def test_senta_para_regenerar_antes_de_andar():
    mundo = _Mundo(fada=None)
    _ciclo(mundo).resolver()
    assert mundo.sentadas >= 1
    assert mundo.sentado is False, "levantou? tem de andar de pé"


def test_com_mob_em_cima_NAO_senta():
    """*"Com mob em cima ele anda mesmo assim: parado ali é pior."*"""
    mundo = _Mundo(fada=None)
    mundo.batalha = True

    _ciclo(mundo).resolver()

    assert mundo.sentadas == 0
    assert mundo.voltou == 1


def test_ja_sentado_nao_aperta_de_novo():
    """A tecla é interruptor -- apertar de novo levantaria. Regra geral do
    usuário: antes de sentar, verifique se já não está sentado."""
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)
    mundo.vida = 50.0
    mundo.sentado = True

    ciclo._regenerar_antes_de_andar()

    assert mundo.sentadas == 1, "só o levantar do fim"
    assert mundo.sentado is False


def test_vida_no_alvo_nem_senta():
    mundo = _Mundo(fada=None)
    mundo.vida = 95.0
    _ciclo(mundo, parar_pct=90.0)._regenerar_antes_de_andar()
    assert mundo.sentadas == 0


# ---------------------------------------------------------------- o freio

def test_tres_mortes_sem_voltar_PARAM_a_conta():
    """Sem o contador, um spot que virou armadilha vira um moedor de tentativas
    a noite toda."""
    mundo = _Mundo(fada=None)
    mundo.volta_da_certo = False
    ciclo = _ciclo(mundo)

    resultados = [ciclo.resolver() for _ in range(mod.MORTES_SEGUIDAS_PARA_PARAR)]

    assert resultados[:-1] == [True] * (mod.MORTES_SEGUIDAS_PARA_PARAR - 1)
    assert resultados[-1] is False


def test_voltar_ao_ponto_ZERA_o_contador():
    """É "seguidas", não "no total": um farm de horas morre várias vezes."""
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)
    mundo.volta_da_certo = False
    ciclo.resolver()
    assert ciclo.mortes_sem_voltar == 1

    mundo.volta_da_certo = True
    mundo.vida = 0.0
    ciclo.resolver()

    assert ciclo.mortes_sem_voltar == 0


def test_o_clique_que_NAO_poe_de_pe_conta_como_falha():
    mundo = _Mundo(fada=None, revive_no_clique=False)
    ciclo = _ciclo(mundo)

    assert ciclo.resolver() is True
    assert ciclo.mortes_sem_voltar == 1
    assert mundo.voltou == 0, "andou com o personagem ainda morto"


# ---------------------------------------------------------------- o executor

def test_o_laco_do_APP_pergunta_a_cada_linha():
    """A pergunta é de memória (`hp == 0`), do mesmo naipe do alvo zerado -- por
    isso cabe a cada linha, e não uma vez por volta."""
    import inspect

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = inspect.getsource(ExecutorDeMacro._uma_volta_simples)
    assert "self.morte.estou_morto()" in fonte


def test_morrer_no_meio_da_macro_INTERROMPE_a_volta():
    from types import SimpleNamespace

    import tests.test_laco_simples_do_app as base

    e = base._executor()
    e._id_do_alvo = lambda: 777

    class _MorteFalsa:
        def __init__(self):
            self.resolvi = 0

        def estou_morto(self):
            return self.resolvi == 0        # morto até ser resolvido

        def resolver(self):
            self.resolvi += 1
            return True

    e.morte = _MorteFalsa()
    passos = [SimpleNamespace(key="1", delay_ms=1) for _ in range(5)]

    assert e._uma_volta_simples(passos) is True
    assert e.teclas.count("1") == 0, "apertou tecla com o personagem morto"
    assert e.morte.resolvi == 1


def test_a_conta_PARA_quando_o_ciclo_desiste():
    from types import SimpleNamespace

    import tests.test_laco_simples_do_app as base

    e = base._executor()
    e._id_do_alvo = lambda: 777
    e.morte = SimpleNamespace(estou_morto=lambda: True, resolver=lambda: False)
    passos = [SimpleNamespace(key="1", delay_ms=1)]

    assert e._uma_volta_simples(passos) is False, "seguiu depois do 'pare'"


# ---------------------------------------------------------------------------
# A VOLTA AO PONTO É A PÉ -- medido em campo em 06/09/2026
# ---------------------------------------------------------------------------
#
# A conta líder ficou 33 MINUTOS e 315 tentativas presa tentando montar para
# voltar ao ponto depois de reviver. O portão da montaria insiste para sempre
# de propósito -- é regra da BC ("nunca a pé dentro da cave") -- e personagem
# de APP normalmente não TEM montaria: a tecla está configurada (é o padrão da
# conta), mas não há o que montar, então o portão nunca confirma.

def test_a_volta_do_APP_nao_exige_montaria():
    import inspect

    fonte = inspect.getsource(mod.montar_para_o_app)
    assert "exigir_montaria=False" in fonte, (
        "a volta ao ponto voltou a exigir montaria -- é o travamento de 33 min")
    assert "max_seconds=TETO_DO_RETORNO" in fonte, (
        "sem teto, a volta tenta a noite inteira em vez de contar a falha")


def test_o_portao_da_montaria_respeita_quem_aceita_ir_a_pe():
    import inspect

    from blazesbot.bot.navegacao import Navigator

    fonte = inspect.getsource(Navigator.garantir_montaria_para_andar)
    corpo = fonte.split('"""')[-1]
    assert "_exigir_montaria" in corpo, "o portão ignora o pedido de ir a pé"
    # E a INSISTÊNCIA continua sendo o padrão -- é regra da cave.
    assert inspect.signature(Navigator.__init__).parameters[
        "exigir_montaria"].default is True


# ---------------------------------------------------------------------------
# O DIAGNÓSTICO FINO -- 06/09/2026
# ---------------------------------------------------------------------------
#
# *"Vamos tentar trackear todo tipo de problema com vários logs em vários pontos
# (...) pois assim vamos ter comprovações e conseguir tomar medidas mais
# precisas."*

def test_a_morte_registra_ONDE_e_COM_QUEM(caplog):
    from blazesbot.core import diagnostico_fino

    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)
    ciclo._CicloDaMorte__onde_estou = lambda: (1750, 1607)
    ciclo._CicloDaMorte__quao_longe = lambda: 42.0

    with caplog.at_level(logging.INFO):
        ciclo.resolver()

    linhas = [r.getMessage() for r in caplog.records if "DIAG:" in r.getMessage()]
    assert any("MORTE #1" in x and "(1750, 1607)" in x for x in linhas), linhas
    assert any("RETORNO ok" in x for x in linhas), linhas
    assert diagnostico_fino.LIGADO is True


def test_o_diagnostico_NUNCA_derruba_o_ciclo():
    """Log de medição que explode e leva a macro junto seria pior que não medir."""
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)

    def _explode():
        raise RuntimeError("memória sumiu")

    ciclo._CicloDaMorte__onde_estou = _explode
    ciclo._CicloDaMorte__quao_longe = _explode

    assert ciclo.resolver() is True


def test_desligar_o_interruptor_CALA_as_linhas_de_medicao(monkeypatch, caplog):
    from blazesbot.core import diagnostico_fino

    monkeypatch.setattr(diagnostico_fino, "LIGADO", False)
    mundo = _Mundo(fada=None)

    with caplog.at_level(logging.INFO):
        _ciclo(mundo).resolver()

    assert not [r for r in caplog.records if "DIAG:" in r.getMessage()]


def test_leitura_de_batalha_que_explode_no_diagnostico_nao_derruba():
    """Achado do Codex em 06/09/2026: o diagnóstico da morte chamava
    `_em_batalha()` cru. Uma leitura que falhasse ali interromperia o ciclo
    ANTES de avisar o time -- ou seja, o log de medição derrubaria justamente a
    recuperação que ele existe para medir."""
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)

    def _explode():
        raise RuntimeError("memória sumiu")

    ciclo._em_batalha = _explode

    assert ciclo.resolver() is True


# ---------------------------------------------------------------------------
# QUEM ESTAVA EM CIMA -- a pergunta que fecha "morri por causa do spot?"
# ---------------------------------------------------------------------------

def test_a_morte_lista_os_mobs_em_volta(caplog):
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)
    ciclo._CicloDaMorte__vizinhanca = lambda: "mobs vivos a até 40: 4 [A@3, B@9]"

    with caplog.at_level(logging.INFO):
        ciclo.resolver()

    assert any("mobs vivos a até 40: 4" in r.getMessage()
               for r in caplog.records), [r.getMessage() for r in caplog.records]


def test_a_vizinhanca_que_falha_vira_texto_e_nao_excecao():
    """Diagnóstico que derruba o ciclo da morte é pior que diagnóstico nenhum."""
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)

    def _explode():
        raise RuntimeError("processo sumiu")

    ciclo._CicloDaMorte__vizinhanca = _explode

    assert ciclo.resolver() is True
    assert "vizinhança=?" in ciclo._quem_estava_em_cima()


def test_sem_leitura_de_vizinhanca_o_ciclo_segue():
    mundo = _Mundo(fada=None)
    ciclo = _ciclo(mundo)          # a fixture não injeta `vizinhanca`
    assert ciclo._quem_estava_em_cima() == "vizinhança=?"
    assert ciclo.resolver() is True


def test_a_leitura_da_vizinhanca_FECHA_o_handle(monkeypatch):
    """Um handle por morte é aceitável; um handle vazado por morte, não."""
    from blazesbot.bot import morte as mod_morte

    fechou = []

    class _MemoriaFalsa:
        def __init__(self, pid):
            pass

        def position(self):
            return (10, 10)

        def entidades_vivas(self):
            return [{"nome": "Mob", "pos": (12, 10)},
                    {"nome": "Longe", "pos": (900, 900)}]

        def close(self):
            fechou.append(True)

    import blazesbot.core.memory as mod_mem
    monkeypatch.setattr(mod_mem, "Memory", _MemoriaFalsa)

    texto = mod_morte._vizinhanca(SimpleNamespace(pid=1))

    assert "1 [Mob@2]" in texto, texto
    assert fechou == [True]
