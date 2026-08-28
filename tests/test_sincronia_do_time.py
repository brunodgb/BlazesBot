"""A largada sincronizada do time do APP.

=========================================================================
O QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

1. UM PERSONAGEM PARADO ESPERANDO. É a regra que manda no arquivo inteiro, e a
   mais fácil de perder numa correção futura: toda espera tem teto, e estourar
   o teto NUNCA cancela a volta. Personagem parado num farm morre, e três
   contas paradas por causa de uma que está curando é o oposto do que o time
   existe para fazer.

2. DOIS LÍDERES ANUNCIANDO AO MESMO TEMPO. Cada conta decide sozinha, na sua
   thread, quem assume quando o líder cai. Um sorteio faria duas contas
   chegarem a respostas diferentes -- e duas largadas concorrentes são piores
   que nenhuma. A escolha tem de ser DETERMINÍSTICA.

3. O SEGUIDOR ENTRANDO DUAS VEZES NA MESMA LARGADA. Sem a trava por número de
   volta, um seguidor rápido consumiria o mesmo anúncio em voltas seguidas e
   ficaria uma volta à frente do time -- sincronizado no papel, fora de fase na
   prática.

4. SINCRONIA DERRUBANDO A MACRO. `esperar_a_largada` devolve `False` só quando
   é para PARAR. "Não consegui sincronizar" é sempre "vai assim mesmo".

5. CONVOCAÇÃO SEM FREIO. O seguidor roda o APP com a caixa dele desmarcada --
   mas só enquanto o líder está com o APP ligado, e nunca quando qualquer um
   dos dois está farmando a cave.
"""
from __future__ import annotations

import pytest

from blazesbot.bot import mural
from blazesbot.bot.app import sincronia as mod
from blazesbot.bot.supervisor import AccountSupervisor
from blazesbot.config import Account, BotConfig


@pytest.fixture(autouse=True)
def _tetos_curtos(monkeypatch):
    """Os tetos de verdade são de segundos, e esta suíte roda a cada mudança.

    O que os testes provam é que a espera TERMINA e que estourar não cancela a
    volta -- e isso não depende de o teto ser 3 s ou 0,2 s. Deixar os valores
    reais custava ~13 s de espera pura em toda rodada. Cada teste que fala do
    valor em si o declara explicitamente.
    """
    monkeypatch.setattr(mod, "TETO_DA_LARGADA_SEGUNDOS", 0.2)
    monkeypatch.setattr(mod, "TETO_DO_ALINHAMENTO_SEGUNDOS", 0.2)
    monkeypatch.setattr(mod, "ESPERA_ENTRE_TABS_DO_ALINHAMENTO", 0.01)


@pytest.fixture(autouse=True)
def _mural_limpo():
    """O quadro é estado global de módulo: sem isto um teste contamina o outro."""
    mural.zerar_o_time_para_teste()
    yield
    mural.zerar_o_time_para_teste()


class _ExecutorFalso:
    """O mínimo que a sincronia usa do executor."""

    def __init__(self, alvo: int = 0, em_batalha: bool | None = None,
                 parar_em: int | None = None) -> None:
        self.alvo = alvo
        self.em_batalha = em_batalha
        self.tabs = 0
        self.garantiu = 0
        self.dormiu = 0.0
        # Depois de N dormidas, devolve False -- é como o botão Parar chega aqui.
        self._parar_em = parar_em
        self._dormidas = 0

    def _dormir(self, segundos: float) -> bool:
        self.dormiu += segundos
        self._dormidas += 1
        if self._parar_em is not None and self._dormidas >= self._parar_em:
            return False
        return True

    def _ler_id_do_alvo(self) -> int | None:
        return self.alvo

    def _ler_em_batalha(self) -> bool | None:
        return self.em_batalha

    def _tab_simples(self) -> bool:
        self.tabs += 1
        return True

    def _garantir_alvo(self, forcar: bool = False, urgente: bool = False) -> bool:
        self.garantiu += 1
        return True


def _sinc(ex, *, login="eu", lider="eu", modo="largada", membros=("eu", "outro"),
          max_hp=100):
    return mod.SincroniaDoTime(
        ex, login=login, lider=lider, modo=modo,
        membros=lambda: list(membros), max_hp=lambda: max_hp,
        log=__import__("logging").getLogger("teste.time"))


# ---------------------------------------------------------------------------
# NINGUÉM FICA PARADO
# ---------------------------------------------------------------------------

def test_sozinha_nao_espera_nada():
    """Uma conta sem time roda como sempre rodou -- sem tocar no mural."""
    ex = _ExecutorFalso()
    s = _sinc(ex, membros=("eu",))
    assert s.esperar_a_largada() is True
    assert ex.dormiu == 0.0


def test_modo_copiar_nunca_espera():
    ex = _ExecutorFalso()
    s = _sinc(ex, modo="copiar")
    assert s.esperar_a_largada() is True
    assert ex.dormiu == 0.0


def test_o_lider_larga_sem_o_seguidor_que_nao_chegou():
    """Teto estourado NÃO cancela a volta -- devolve True e segue.

    O teto é encurtado aqui porque a espera é de relógio de parede: o executor
    falso não dorme de verdade, então medir "quanto ele dormiu" contaria as
    voltas do laço, não o tempo. O que precisa ser provado é que a espera
    TERMINA e devolve True.
    """
    ex = _ExecutorFalso()
    s = _sinc(ex, login="lider", lider="lider", membros=("lider", "atrasado"))
    comeco = mod.time.time()
    assert s.esperar_a_largada() is True
    assert s.largadas_perdidas == 1
    assert mod.time.time() - comeco < 2.0


def test_o_seguidor_sem_largada_vai_sozinho():
    ex = _ExecutorFalso()
    s = _sinc(ex, login="seguidor", lider="lider", membros=("lider", "seguidor"))
    assert s.esperar_a_largada() is True
    assert s.largadas_perdidas == 1


def test_o_lider_larga_na_hora_quando_todos_confirmam():
    mural.publicar_estado("seguidor", volta_pronta=1, max_hp=50)
    ex = _ExecutorFalso()
    s = _sinc(ex, login="lider", lider="lider", membros=("lider", "seguidor"))
    assert s.esperar_a_largada() is True
    assert s.largadas_juntas == 1
    assert s.largadas_perdidas == 0


def test_o_seguidor_entra_na_largada_anunciada():
    mural.anunciar_largada("lider", 7, 999)
    ex = _ExecutorFalso()
    s = _sinc(ex, login="seguidor", lider="lider", membros=("lider", "seguidor"))
    mural.publicar_estado("lider", volta_pronta=7, max_hp=100)
    assert s.esperar_a_largada() is True
    assert s.largadas_juntas == 1
    assert s.ultima_largada == 7


def test_o_seguidor_nao_entra_duas_vezes_na_mesma_largada():
    mural.anunciar_largada("lider", 7, 0)
    mural.publicar_estado("lider", volta_pronta=7, max_hp=100)
    ex = _ExecutorFalso()
    s = _sinc(ex, login="seguidor", lider="lider", membros=("lider", "seguidor"))
    s.esperar_a_largada()
    assert s.largadas_juntas == 1
    # Sem largada nova, a volta seguinte é solo -- e NÃO reaproveita a de número 7.
    s.esperar_a_largada()
    assert s.largadas_juntas == 1
    assert s.largadas_perdidas == 1


def test_parar_interrompe_a_espera():
    """`False` só existe para o botão Parar."""
    ex = _ExecutorFalso(parar_em=2)
    s = _sinc(ex, login="lider", lider="lider", membros=("lider", "atrasado"))
    assert s.esperar_a_largada() is False


# ---------------------------------------------------------------------------
# O MESMO ALVO
# ---------------------------------------------------------------------------

def test_alinha_dando_tab_ate_o_id_bater():
    ex = _ExecutorFalso(alvo=111)

    def tab():
        ex.tabs += 1
        ex.alvo = 999            # o terceiro TAB acha o alvo do líder
        return True
    mural.anunciar_largada("lider", 1, 999)
    mural.publicar_estado("lider", volta_pronta=1, max_hp=100)
    s = _sinc(ex, login="seguidor", lider="lider", modo="mesmo_alvo",
              membros=("lider", "seguidor"))
    ex._tab_simples = tab
    assert s.esperar_a_largada() is True
    assert ex.tabs >= 1
    assert ex.alvo == 999


def test_alinhamento_desiste_no_teto_e_a_volta_continua():
    """O mob do líder pode nem estar no ciclo de TAB desta conta."""
    ex = _ExecutorFalso(alvo=111)          # nunca vira 999
    mural.anunciar_largada("lider", 1, 999)
    mural.publicar_estado("lider", volta_pronta=1, max_hp=100)
    s = _sinc(ex, login="seguidor", lider="lider", modo="mesmo_alvo",
              membros=("lider", "seguidor"))
    assert s.esperar_a_largada() is True   # a volta NÃO é cancelada
    assert s.alinhamentos_falhos == 1


def test_o_lider_pega_alvo_antes_de_anunciar():
    """Sem isto ele anunciaria o alvo da volta ANTERIOR -- o que acabou de morrer."""
    ex = _ExecutorFalso(alvo=42)
    mural.publicar_estado("seguidor", volta_pronta=1, max_hp=50)
    s = _sinc(ex, login="lider", lider="lider", modo="mesmo_alvo",
              membros=("lider", "seguidor"))
    s.esperar_a_largada()
    assert ex.garantiu == 1
    assert mural.largada_pendente("lider") == (1, 42)


# ---------------------------------------------------------------------------
# QUEM ASSUME QUANDO O LÍDER CAI
# ---------------------------------------------------------------------------

def test_o_lider_declarado_manda_enquanto_publica():
    mural.publicar_estado("lider", volta_pronta=1, max_hp=10)
    mural.publicar_estado("gordo", volta_pronta=1, max_hp=9999)
    s = _sinc(_ExecutorFalso(), login="gordo", lider="lider",
              membros=("lider", "gordo"))
    assert s.sou_o_lider() is False


def test_com_o_lider_calado_assume_quem_tem_mais_vida_maxima():
    mural.publicar_estado("magro", volta_pronta=1, max_hp=100)
    mural.publicar_estado("gordo", volta_pronta=1, max_hp=900)
    s = _sinc(_ExecutorFalso(), login="gordo", lider="lider",
              membros=("lider", "magro", "gordo"))
    assert s.sou_o_lider() is True


def test_a_eleicao_e_deterministica_para_todas_as_contas():
    """Todas as contas do time têm de chegar ao MESMO nome.

    É a diferença entre um líder temporário e dois líderes anunciando largadas
    concorrentes. Empate de vida cai na ordem do login, e não num sorteio.
    """
    mural.publicar_estado("bbb", volta_pronta=1, max_hp=500)
    mural.publicar_estado("aaa", volta_pronta=1, max_hp=500)
    membros = ("lider", "bbb", "aaa")
    escolhas = {
        _sinc(_ExecutorFalso(), login=quem, lider="lider",
              membros=membros)._lider_efetivo()
        for quem in ("bbb", "aaa")
    }
    assert len(escolhas) == 1, f"contas discordaram sobre o líder: {escolhas}"


def test_sem_ninguem_publicando_o_lider_declarado_continua():
    """Na primeira volta ninguém publicou ainda -- não pode haver golpe."""
    s = _sinc(_ExecutorFalso(), login="outro", lider="lider",
              membros=("lider", "outro"))
    assert s._lider_efetivo() == "lider"


# ---------------------------------------------------------------------------
# OS 4 SEGUNDOS
# ---------------------------------------------------------------------------

def test_a_troca_de_estado_de_batalha_zera_o_relogio():
    ex = _ExecutorFalso(em_batalha=False)
    s = _sinc(ex)
    assert s.conferir_a_parada() is False        # primeira leitura: só registra
    ex.em_batalha = True
    assert s.conferir_a_parada() is False        # mudou: zera


def test_sem_leitura_de_batalha_nunca_dispara():
    """Cego não é 'parado': o APP roda de propósito sem memória."""
    s = _sinc(_ExecutorFalso(em_batalha=None))
    assert s.conferir_a_parada() is False


def test_passado_o_tempo_sem_mudanca_pede_tab(monkeypatch):
    ex = _ExecutorFalso(em_batalha=False)
    s = _sinc(ex)
    s.conferir_a_parada()
    agora = mod.time.time() + mod.SEGUNDOS_SEM_MUDANCA_PARA_TAB + 0.1
    monkeypatch.setattr(mod.time, "time", lambda: agora)
    assert s.conferir_a_parada() is True


# ---------------------------------------------------------------------------
# A CONVOCAÇÃO (supervisor)
# ---------------------------------------------------------------------------

def _conta(login, *, app=False, farm=False, segue=()):
    c = Account(login=login, last_char_name=login.title(), password_enc="x")
    c.enabled = True
    c.bc_farm = farm
    c.settings.app.enabled = app
    c.settings.app.time_logins = list(segue)
    return c


def _sup(conta, *contas):
    s = AccountSupervisor.__new__(AccountSupervisor)
    s.account = conta
    cfg = BotConfig()
    cfg.accounts = [conta, *contas]
    s.config = cfg
    return s


def test_o_seguidor_e_convocado_com_a_flag_dele_desligada():
    lider = _conta("lider", app=True, segue=["seguidor"])
    seguidor = _conta("seguidor", app=False)
    sup = _sup(seguidor, lider)
    assert sup._lider_do_time() is lider


def test_lider_com_o_app_desligado_nao_convoca_ninguem():
    lider = _conta("lider", app=False, segue=["seguidor"])
    seguidor = _conta("seguidor", app=False)
    assert _sup(seguidor, lider)._lider_do_time() is None


def test_conta_farmando_a_cave_nunca_e_convocada():
    lider = _conta("lider", app=True, segue=["seguidor"])
    seguidor = _conta("seguidor", app=False, farm=True)
    assert _sup(seguidor, lider)._lider_do_time() is None


def test_lider_farmando_a_cave_nao_convoca():
    lider = _conta("lider", app=True, farm=True, segue=["seguidor"])
    seguidor = _conta("seguidor", app=False)
    assert _sup(seguidor, lider)._lider_do_time() is None


def test_o_seguidor_roda_a_macro_do_lider():
    lider = _conta("lider", app=True, segue=["seguidor"])
    lider.settings.app.steps[0].key = "F1"
    seguidor = _conta("seguidor", app=False)
    seguidor.settings.app.steps[0].key = "F9"
    sup = _sup(seguidor, lider)
    assert sup._dono_da_macro() is lider
    assert sup._dono_da_macro().settings.app.passos_ativos[0].key == "F1"


def test_sozinha_a_conta_roda_a_propria_macro():
    sozinha = _conta("sozinha", app=True)
    assert _sup(sozinha)._dono_da_macro() is sozinha


def test_o_membro_que_ligou_o_farm_sai_do_time_sem_ser_apagado():
    lider = _conta("lider", app=True, segue=["a", "b"])
    a = _conta("a")
    b = _conta("b", farm=True)
    sup = _sup(lider, a, b)
    assert sup._membros_do_time() == ["lider", "a"]
    # O login NÃO some da configuração: desligar o farm devolve a conta ao time.
    assert lider.settings.app.time_logins == ["a", "b"]


def test_o_lider_encabeca_a_lista_de_membros():
    """A ordem importa: o desempate da eleição é por ela."""
    lider = _conta("lider", app=True, segue=["a"])
    sup = _sup(lider, _conta("a"))
    assert sup._membros_do_time()[0] == "lider"
