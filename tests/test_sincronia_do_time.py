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

# O VALOR REAL DO TETO, guardado no import -- antes de a fixture `_tetos_curtos`
# encurtá-lo. Sem isto não haveria como afirmar nada sobre o número de verdade.
TETO_REAL_DA_LARGADA = mod.TETO_DA_LARGADA_SEGUNDOS


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

    def _continuar(self) -> bool:
        """O laço do executor pergunta isto; a espera da linha também, para o
        botão Parar responder no meio dela."""
        return True

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


def _confirmar(login: str, alvo_sinc, volta: int | None = None) -> None:
    """Publica a confirmação que `alvo_sinc` (o líder) aceita como válida.

    A identidade da largada é `(lider, epoca, volta)` -- confirmar só com o
    número da volta era exatamente o defeito que a época veio corrigir.
    """
    mural.publicar_estado(
        login,
        volta_pronta=volta if volta is not None else alvo_sinc.volta + 1,
        largada_de=alvo_sinc.login,
        largada_epoca=alvo_sinc.epoca,
        max_hp=50,
    )


def _anunciar(lider: str, volta: int, alvo: int = 0, epoca: int = 1) -> None:
    mural.anunciar_largada(lider, epoca, volta, alvo)
    mural.publicar_estado(lider, volta_pronta=volta, largada_de=lider,
                          largada_epoca=epoca, max_hp=100)


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
    ex = _ExecutorFalso()
    s = _sinc(ex, login="lider", lider="lider", membros=("lider", "seguidor"))
    _confirmar("seguidor", s)
    assert s.esperar_a_largada() is True
    assert s.largadas_juntas == 1
    assert s.largadas_perdidas == 0


def test_o_seguidor_entra_na_largada_anunciada():
    _anunciar("lider", 7, 999)
    ex = _ExecutorFalso()
    s = _sinc(ex, login="seguidor", lider="lider", membros=("lider", "seguidor"))
    assert s.esperar_a_largada() is True
    assert s.largadas_juntas == 1
    assert s.ultima_largada == ("lider", 1, 7)


def test_o_seguidor_nao_entra_duas_vezes_na_mesma_largada():
    _anunciar("lider", 7, 0)
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
    _anunciar("lider", 1, 999)
    s = _sinc(ex, login="seguidor", lider="lider", modo="mesmo_alvo",
              membros=("lider", "seguidor"))
    ex._tab_simples = tab
    assert s.esperar_a_largada() is True
    assert ex.tabs >= 1
    assert ex.alvo == 999


def test_alinhamento_desiste_no_teto_e_a_volta_continua():
    """O mob do líder pode nem estar no ciclo de TAB desta conta."""
    ex = _ExecutorFalso(alvo=111)          # nunca vira 999
    _anunciar("lider", 1, 999)
    s = _sinc(ex, login="seguidor", lider="lider", modo="mesmo_alvo",
              membros=("lider", "seguidor"))
    assert s.esperar_a_largada() is True   # a volta NÃO é cancelada
    assert s.alinhamentos_falhos == 1


def test_o_lider_pega_alvo_antes_de_anunciar():
    """Sem isto ele anunciaria o alvo da volta ANTERIOR -- o que acabou de morrer."""
    ex = _ExecutorFalso(alvo=42)
    s = _sinc(ex, login="lider", lider="lider", modo="mesmo_alvo",
              membros=("lider", "seguidor"))
    _confirmar("seguidor", s)
    s.esperar_a_largada()
    assert ex.garantiu == 1
    # A largada foi FECHADA ao sair da espera -- ninguém entra depois.
    assert mural.largada_pendente("lider") is None
    assert s.largada_epoca == s.epoca


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
    agora = mod.time.monotonic() + mod.SEGUNDOS_SEM_MUDANCA_PARA_TAB + 0.1
    monkeypatch.setattr(mod.time, "monotonic", lambda: agora)
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

# ---------------------------------------------------------------------------
# O QUE A REVISÃO DO CODEX PEGOU (27/08/2026)
# ---------------------------------------------------------------------------

def test_confirmacao_de_outro_lider_nao_conta():
    """O número da volta sozinho não identifica largada nenhuma.

    Um líder temporário anuncia a volta 1; o titular também recomeça do 1 ao
    reiniciar. Sem o nome de quem abriu, uma confirmação valia para as duas e o
    líder largava sozinho achando que estava acompanhado.
    """
    mural.publicar_estado("seguidor", volta_pronta=1, largada_de="OUTRO",
                          largada_epoca=1, max_hp=50)
    s = _sinc(_ExecutorFalso(), login="lider", lider="lider",
              membros=("lider", "seguidor"))
    assert s.esperar_a_largada() is True
    assert s.largadas_perdidas == 1          # não contou a confirmação alheia


def test_o_seguidor_publica_de_quem_e_a_largada():
    _anunciar("lider", 5, 0, epoca=9)
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider",
              membros=("lider", "seguidor"))
    s.esperar_a_largada()
    estado = mural.estado_da_conta("seguidor")
    assert estado["largada_de"] == "lider"
    assert estado["largada_epoca"] == 9
    assert estado["volta_pronta"] == 5


def test_o_login_nao_depende_da_caixa():
    """O mural guarda em caixa baixa; a sincronia comparava em caixa original.

    A conta `Foo` não se reconhecia como o líder `foo` e esperava para sempre a
    largada que ela própria deveria anunciar.
    """
    s = _sinc(_ExecutorFalso(), login="Foo", lider="foo", membros=("Foo", "outro"))
    assert s.sou_o_lider() is True


def test_o_relogio_dos_4s_rearma_ao_disparar(monkeypatch):
    """Sem rearmar, ele pedia TAB em TODA volta seguinte -- inclusive no meio
    de um combate longo, que é justamente quando não se deve trocar de alvo."""
    ex = _ExecutorFalso(em_batalha=True)
    s = _sinc(ex)
    s.conferir_a_parada()
    agora = mod.time.monotonic() + mod.SEGUNDOS_SEM_MUDANCA_PARA_TAB + 0.1
    monkeypatch.setattr(mod.time, "monotonic", lambda: agora)
    assert s.conferir_a_parada() is True
    assert s.conferir_a_parada() is False    # rearmou


def test_a_validade_da_largada_e_o_teto_do_lider_sao_o_mesmo_numero():
    """Enquanto eram dois, havia um buraco entre eles: o seguidor entrava numa
    largada que o líder já tinha abandonado, e os dois se contavam como juntos
    estando segundos fora de fase."""
    assert TETO_REAL_DA_LARGADA == mural.LARGADA_VALIDA_SEGUNDOS

def test_confirmacao_de_execucao_ANTERIOR_do_mesmo_lider_nao_conta():
    """O contador de voltas recomeça do 1 a cada reinício do executor.

    O estado publicado sobrevive ao reinício por `ESTADO_VALIDO_SEGUNDOS`, então
    sem a ÉPOCA a confirmação da execução anterior valia para a volta 1 da nova
    -- o líder largava sozinho achando que o seguidor tinha entrado.
    """
    s = _sinc(_ExecutorFalso(), login="lider", lider="lider",
              membros=("lider", "seguidor"))
    mural.publicar_estado("seguidor", volta_pronta=1, largada_de="lider",
                          largada_epoca=s.epoca - 1, max_hp=50)   # execução velha
    assert s.esperar_a_largada() is True
    assert s.largadas_perdidas == 1


def test_largada_de_um_lider_NOVO_nao_e_recusada_pelo_numero():
    """Trocar de líder recomeça a numeração; guardar só o número recusava a
    largada 1 do líder novo por já se ter entrado na largada 1 do anterior."""
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="antigo",
              membros=("antigo", "novo", "seguidor"))
    _anunciar("antigo", 1, 0)
    s.esperar_a_largada()
    assert s.ultima_largada == ("antigo", 1, 1)

    # O antigo some; quem assume é o "novo", e ele também começa do 1.
    mural.zerar_o_time_para_teste()
    _anunciar("novo", 1, 0)
    mural.publicar_estado("novo", volta_pronta=1, largada_de="novo",
                          largada_epoca=1, max_hp=900)
    s.esperar_a_largada()
    assert s.ultima_largada == ("novo", 1, 1)
    assert s.largadas_juntas == 2


def test_a_largada_e_fechada_quando_o_lider_para_de_esperar():
    """Depois disso a macro do líder começa: entrar seria contar-se como junto
    estando segundos atrás."""
    s = _sinc(_ExecutorFalso(), login="lider", lider="lider",
              membros=("lider", "sumido"))
    s.esperar_a_largada()
    assert mural.largada_pendente("lider") is None

# ---------------------------------------------------------------------------
# LINHA A LINHA -- a correção de 28/08/2026
# ---------------------------------------------------------------------------
#
# O QUE ESTES TESTES IMPEDEM DE VOLTAR: a defasagem ESTÁVEL. Medido no log
# real, duas contas rodavam voltas de ~20 s defasadas em ~13 s, volta após
# volta, porque o seguidor atrasado dormia o próprio delay ALÉM de esperar o
# líder -- nunca corria mais rápido, então nunca alcançava.

def _linha(s, i):
    return s.antes_da_linha(i)


def test_o_lider_marca_cada_linha():
    s = _sinc(_ExecutorFalso(), login="lider", lider="lider",
              membros=("lider", "seguidor"))
    s.esperar_a_largada()
    assert _linha(s, 3) is True
    assert mural.passo_do_lider("lider") == (s.epoca, s.volta_do_time, 3)


def test_o_seguidor_espera_a_marca_da_linha():
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider",
              membros=("lider", "seguidor"))
    _anunciar("lider", 1, 0)
    s.esperar_a_largada()
    mural.abrir_passo("lider", 1, 1, 5)          # o líder já está na linha 5
    assert _linha(s, 5) is True
    assert s.linhas_juntas >= 1


def test_o_seguidor_ATRASADO_nao_espera_nada():
    """O coração da correção: marca já dada não faz esperar.

    Sem isto o atrasado esperava a linha que já passou, gastava o teto e
    continuava exatamente com o mesmo atraso na linha seguinte.
    """
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider",
              membros=("lider", "seguidor"))
    _anunciar("lider", 1, 0)
    s.esperar_a_largada()
    mural.abrir_passo("lider", 1, 1, 18)         # o líder está MUITO à frente
    comeco = mod.time.monotonic()
    assert _linha(s, 2) is True                  # linha antiga: não espera
    assert mod.time.monotonic() - comeco < 0.05


def test_uma_volta_inteira_atras_tambem_destrava():
    """A marca da volta seguinte é 'maior' que qualquer linha da anterior."""
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider",
              membros=("lider", "seguidor"))
    _anunciar("lider", 4, 0)
    s.esperar_a_largada()
    mural.abrir_passo("lider", 1, 5, 0)          # já é a volta seguinte
    comeco = mod.time.monotonic()
    assert _linha(s, 19) is True
    assert mod.time.monotonic() - comeco < 0.05


def test_o_seguidor_so_dorme_o_piso():
    """Dormir o delay próprio ALÉM da marca é o que preservava a defasagem."""
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider",
              membros=("lider", "seguidor"))
    assert s.espera_da_linha(3000) == mod.MINIMO_DE_ESPERA_DO_APP_MS


def test_o_lider_dorme_o_delay_da_macro():
    """É ele quem dita o ritmo do time -- se ele acelerar, todos aceleram."""
    s = _sinc(_ExecutorFalso(), login="lider", lider="lider",
              membros=("lider", "seguidor"))
    assert s.espera_da_linha(3000) == 3000


def test_sem_time_a_macro_nao_e_gatilhada():
    s = _sinc(_ExecutorFalso(), membros=("eu",))
    assert _linha(s, 7) is True
    assert mural.passo_do_lider("eu") is None
    assert s.espera_da_linha(3000) == 3000


def test_modo_copiar_nao_marca_nem_espera():
    s = _sinc(_ExecutorFalso(), login="lider", lider="lider", modo="copiar",
              membros=("lider", "seguidor"))
    assert _linha(s, 2) is True
    assert mural.passo_do_lider("lider") is None
    assert s.espera_da_linha(3000) == 3000


def test_lider_parado_nao_prende_o_seguidor(monkeypatch):
    """Passado o teto da linha, manda sozinho -- ninguém fica parado."""
    monkeypatch.setattr(mod, "TETO_DA_LINHA_SEGUNDOS", 0.1)
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider",
              membros=("lider", "seguidor"))
    _anunciar("lider", 1, 0)
    s.esperar_a_largada()
    mural.esquecer_passo("lider")
    assert _linha(s, 9) is True                  # não trava
    assert s.linhas_sem_marca == 1


def test_parar_interrompe_a_espera_da_linha(monkeypatch):
    monkeypatch.setattr(mod, "TETO_DA_LINHA_SEGUNDOS", 5.0)
    ex = _ExecutorFalso()
    ex._continuar = lambda: False
    s = _sinc(ex, login="seguidor", lider="lider", membros=("lider", "seguidor"))
    _anunciar("lider", 1, 0)
    s.esperar_a_largada()
    mural.esquecer_passo("lider")
    assert _linha(s, 9) is False

# ---------------------------------------------------------------------------
# A SEQUÊNCIA DO "MESMO ALVO", conferida contra a descrição do usuário
# ---------------------------------------------------------------------------
#
#   *"o líder dar tab primeiro para pegar o target_id; aí depois que tiver o id,
#    os outros dão tab; e quando todos estão com o mesmo target_id todos
#    começam juntos a macro."*

def test_o_alinhamento_cabe_dentro_da_espera_do_lider():
    """Eram dois números soltos e a conta não fechava.

    Com alinhamento de 4 s e espera de 3 s, o líder desistia ANTES de o
    seguidor terminar de alinhar -- e "todos começam juntos no mesmo alvo",
    que é a razão de o modo existir, nunca acontecia quando o alinhamento
    demorava.
    """
    assert mod.TETO_DO_ALINHAMENTO_SEGUNDOS < TETO_REAL_DA_LARGADA


def test_no_mesmo_alvo_o_prelud1o_da_volta_NAO_da_tab():
    """O TAB de cortesia do começo da volta desfaria o alinhamento.

    A largada acabou de pôr as contas todas no mob do líder; esse TAB trocaria
    o alvo logo antes da primeira linha da macro.
    """
    s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider",
              modo="mesmo_alvo", membros=("lider", "seguidor"))
    assert s.deve_dar_tab_na_abertura() is False


def test_nos_outros_modos_o_tab_de_abertura_continua():
    """Lá ninguém combinou alvo: o TAB é o que dá mob para a macro bater."""
    for modo in ("largada", "copiar"):
        s = _sinc(_ExecutorFalso(), login="seguidor", lider="lider", modo=modo,
                  membros=("lider", "seguidor"))
        assert s.deve_dar_tab_na_abertura() is True, modo


def test_sozinha_o_tab_de_abertura_continua():
    s = _sinc(_ExecutorFalso(), modo="mesmo_alvo", membros=("eu",))
    assert s.deve_dar_tab_na_abertura() is True


def test_o_seguidor_so_confirma_DEPOIS_de_alinhar():
    """A ordem é o que faz o líder esperar pelo alinhamento, e não só pela
    presença: a confirmação é publicada no fim de `esperar_a_largada`, depois
    do TAB de alinhamento."""
    ex = _ExecutorFalso(alvo=111)
    tentativas = {"n": 0}

    def tab():
        tentativas["n"] += 1
        ex.alvo = 999
        return True
    ex._tab_simples = tab
    _anunciar("lider", 1, 999)
    s = _sinc(ex, login="seguidor", lider="lider", modo="mesmo_alvo",
              membros=("lider", "seguidor"))
    s.esperar_a_largada()
    assert tentativas["n"] >= 1
    estado = mural.estado_da_conta("seguidor")
    assert estado["alvo"] == 999          # confirmou JÁ no alvo do líder
