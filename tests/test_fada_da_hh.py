"""A Fada da HH: ela ENTRA na cave, SEGUE o líder, e não decide nada da rota.

O QUE ESTE ARQUIVO PROTEGE, e é o que separa o modo HH+Fada de uma segunda
rotina de cave rodando em paralelo:

  * a Fada NÃO entra primeiro — cada entrada abre uma cópia da instância, e
    entrar antes do líder gastaria a dela numa cópia onde ele não está;
  * ela NÃO desfaz o time — quem faz é o líder, e duas contas decidindo isso é
    uma corrida cujo resultado é um time desfeito no meio da cave;
  * ela NÃO refaz os waypoints — segue pela tecla do jogo, que não tem como sair
    da rota;
  * sem a tecla configurada ela AVISA e continua viva, curando de onde está.
"""
import ast
import inspect
import textwrap

import pytest

from blazesbot.bot.hh import mapa_hh
from blazesbot.bot.hh.fada import FadaDaHH


def _fonte(metodo) -> str:
    return textwrap.dedent(inspect.getsource(metodo))


class _Log:
    def __init__(self):
        self.linhas = []

    def _guardar(self, nivel):
        def escrever(msg, *args):
            self.linhas.append((nivel, msg % args if args else msg))
        return escrever

    def __getattr__(self, nome):
        return self._guardar(nome)

    def texto(self):
        return " | ".join(linha for _n, linha in self.linhas)


class _Teclas:
    def __init__(self, follow=""):
        self.follow = follow


class _Settings:
    def __init__(self, follow=""):
        self.keys = _Teclas(follow)


class _Memoria:
    def __init__(self, pos=None, companheiros=None):
        self._pos = pos
        self._companheiros = companheiros or []

    def position(self):
        return self._pos

    def location(self):
        return "Black Wind Camp Dungeon"

    def companheiros_de_time(self):
        return self._companheiros


class _Ctx:
    def __init__(self, follow="", pos=None):
        self.log = _Log()
        self.settings = _Settings(follow)
        self.memory = _Memoria(pos)
        self.hwnd = 1
        self.account_login = "lider"
        self.teclas = []
        self.cliques = []
        self.esperas = 0.0

    def press(self, tecla, hold=0.1):
        self.teclas.append(tecla)
        return True

    def click(self, ponto):
        self.cliques.append(ponto)

    def tick(self, s=0.2):
        self.esperas += s

    def raise_if_stopped(self):
        pass

    def wait_if_paused(self):
        pass

    def check_watchdog(self):
        pass


def _fada(follow="", pos=None, selecionar=None):
    """Uma `FadaDaHH` sem construir navegador nem UI de verdade."""
    fada = object.__new__(FadaDaHH)
    fada.ctx = _Ctx(follow, pos)
    fada.lider_nick = "BlazesOfGamer"
    fada.lider_login = "lider"
    fada._selecionar_o_lider = selecionar
    fada._seguindo_desde = 0.0
    fada._avisou_sem_tecla = False
    fada._avisou_sem_slot = False
    return fada


# ===========================================================================
# A tecla de seguir
# ===========================================================================


def test_sem_a_tecla_configurada_ela_NAO_aperta_nada():
    """A tecla não tem atalho padrão no cliente. Chutar uma faria a Fada apertar
    algo que faz outra coisa -- e, dentro da cave, "outra coisa" pode ser
    qualquer coisa."""
    fada = _fada(follow="", selecionar=lambda: True)

    assert fada.seguir_o_lider() is False
    assert fada.ctx.teclas == [], "apertou uma tecla que ninguém configurou"


def test_sem_a_tecla_ela_AVISA_e_diz_onde_configurar():
    """Falha silenciosa aqui vira "a Fada não acompanha e ninguém sabe por quê"."""
    fada = _fada(follow="")
    fada.tem_tecla_de_seguir()

    texto = fada.ctx.log.texto()
    assert "SEGUIR" in texto
    assert "Teclas" in texto


def test_o_aviso_sai_UMA_vez_e_nao_a_cada_volta():
    """O laço da Fada roda várias vezes por segundo. Avisar em todas encheria o
    log e esconderia tudo o mais."""
    fada = _fada(follow="")
    for _ in range(20):
        fada.tem_tecla_de_seguir()
    assert len(fada.ctx.log.linhas) == 1


def test_com_a_tecla_ela_seleciona_o_lider_ANTES_de_apertar():
    """Apertar seguir sem alvo selecionado segue quem estiver na mira -- que
    pode ser um mob."""
    ordem = []
    fada = _fada(follow="P",
                 selecionar=lambda: (ordem.append("selecionou"), True)[1])
    original = fada.ctx.press

    def press(tecla, hold=0.1):
        ordem.append("apertou")
        return original(tecla, hold)

    fada.ctx.press = press

    assert fada.seguir_o_lider() is True
    assert ordem == ["selecionou", "apertou"]
    assert fada.ctx.teclas == ["P"]


def test_falhar_em_selecionar_NAO_aperta_a_tecla():
    fada = _fada(follow="P", selecionar=lambda: False)

    assert fada.seguir_o_lider() is False
    assert fada.ctx.teclas == []


def test_sem_receber_como_selecionar_ela_avisa_e_nao_quebra():
    """`selecionar_o_lider` é injeção do supervisor. Faltar é bug de ligação --
    e bug de ligação não pode derrubar a conta."""
    fada = _fada(follow="P", selecionar=None)

    assert fada.seguir_o_lider() is False
    assert "selecionar o líder" in fada.ctx.log.texto()


def test_selecionar_que_LEVANTA_nao_derruba_a_conta():
    """Falhar em selecionar custa um follow; levantar aqui custaria a conta."""
    def explode():
        raise RuntimeError("o painel não estava aberto")

    fada = _fada(follow="P", selecionar=explode)
    assert fada.seguir_o_lider() is False


# ===========================================================================
# A ORDEM DE ENTRADA -- a Fada não entra primeiro
# ===========================================================================


def test_ela_espera_o_lider_ANTES_de_entrar():
    """Cada entrada abre uma cópia da instância. Entrar antes dele gastaria a
    dela numa cópia onde ele não está, e aí ninguém cura ninguém."""
    chamadas = [n.func.attr for n in ast.walk(ast.parse(_fonte(FadaDaHH.rodar)))
                if isinstance(n, ast.Call) and hasattr(n.func, "attr")]
    assert chamadas.index("esperar_o_lider_entrar") < chamadas.index("entrar")


def test_o_sinal_do_lider_vem_do_MURAL_e_nao_de_leitura_da_tela():
    """O líder publica que entrou; a Fada lê. É a mesma via que o time do APP já
    usa para tudo -- e ter um segundo canal de coordenação seria ter duas
    verdades sobre onde cada conta está."""
    fonte = _fonte(FadaDaHH.esperar_o_lider_entrar)
    assert "mural" in fonte
    assert "dentro_da_hh" in fonte


def test_a_espera_pelo_lider_tem_TETO_e_segue_de_qualquer_forma():
    """Ficar na porta para sempre é pior que entrar sozinha: sozinha ela pelo
    menos volta para o ciclo, e o líder a convida de novo."""
    fonte = _fonte(FadaDaHH.esperar_o_lider_entrar)
    assert "TETO_ESPERANDO_O_LIDER" in fonte
    assert "return False" in fonte

    from blazesbot.bot.hh import fada as mod

    assert mod.TETO_ESPERANDO_O_LIDER > 0


def test_ja_estando_dentro_ela_NAO_tenta_entrar_de_novo():
    """O bot pode ser ligado com a run em andamento, ou a Fada morreu e reviveu
    lá. O clique de entrar cairia no chão e a tiraria do lugar."""
    fonte = _fonte(FadaDaHH.rodar)
    i_dentro = fonte.index("esta_dentro_da_hh")
    i_porta = fonte.index("ir_para_a_porta")
    assert i_dentro < i_porta


# ===========================================================================
# O que ela NÃO faz
# ===========================================================================


def test_ela_NAO_desfaz_o_time():
    """Quem desfaz e refaz é a rotina do líder, no MANUTENCAO, depois de sair.

    Duas contas decidindo desfazer o mesmo time é uma corrida, e o resultado
    dela é um time desfeito no meio da cave.
    """
    from blazesbot.bot.hh import fada as mod

    fonte = inspect.getsource(mod)
    for proibido in ("sair_do_time", "montar_time", "dismiss"):
        assert proibido not in fonte, (
            f"a Fada chama `{proibido}` -- o ciclo de time é do líder")


def test_ela_NAO_percorre_os_waypoints_dos_bosses():
    """Seguir pela tecla do jogo não tem como sair da rota. Refazer os
    waypoints faria os dois personagens se atravessarem no corredor, e cada
    detector de travamento acordaria por causa do outro."""
    from blazesbot.bot.hh import fada as mod

    fonte = inspect.getsource(mod)
    assert "seguir_rota" not in fonte
    assert "TRECHOS_DOS_BOSSES" not in fonte


def test_ela_NAO_luta():
    from blazesbot.bot.hh import fada as mod

    fonte = inspect.getsource(mod)
    for proibido in ("CombatEngine", "atacar_ate_sair_de_combate", "combate"):
        assert proibido not in fonte, f"a Fada faz `{proibido}`"


# ===========================================================================
# O acompanhamento
# ===========================================================================


def test_o_follow_e_REAFIRMADO_de_tempo_em_tempo():
    """O jogo LARGA o follow: o líder sai do alcance, a Fada toma dano, uma
    janela abre. Sem reafirmar, ela fica parada num corredor enquanto o líder
    mata o boss 4."""
    fonte = _fonte(FadaDaHH.acompanhar)
    assert "INTERVALO_DE_REAFIRMAR_O_FOLLOW" in fonte
    assert "seguir_o_lider" in fonte


def test_o_acompanhamento_responde_a_parada_e_a_queda():
    """Mesma exigência de todo laço longo do projeto."""
    fonte = _fonte(FadaDaHH.acompanhar)
    for peca in ("raise_if_stopped", "wait_if_paused", "check_watchdog",
                 "continuar()"):
        assert peca in fonte, f"o laço não chama `{peca}`"


def test_sair_da_cave_encerra_o_acompanhamento():
    """A run acabou; o que vem é o líder desfazendo e refazendo o time."""
    fonte = _fonte(FadaDaHH.acompanhar)
    assert "esta_dentro_da_hh" in fonte
    assert "return" in fonte


def test_ela_usa_o_MESMO_mapa_e_a_MESMA_entrada_do_lider():
    """Duas noções de "onde é a porta da HH" seria a Fada indo para um lugar e o
    líder para outro."""
    from blazesbot.bot.hh import fada as mod

    fonte = inspect.getsource(mod)
    assert "from .entrada import EntradaDaHH" in fonte
    assert "from . import mapa_hh" in fonte


# ===========================================================================
# O supervisor convoca
# ===========================================================================


def test_a_fada_da_HH_e_CONVOCADA_e_nao_se_oferece():
    """A conta pode não ter farm nenhum ligado e ainda ter trabalho: outra
    conta a escolheu. Quem manda é quem escolheu."""
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._lider_da_hh)
    assert "hh_farm" in fonte
    assert "MODO_FADA_DA_HH" in fonte
    assert "reset_nick" in fonte


def test_a_convocacao_exige_o_NICK_desta_conta():
    """Sem isso, uma conta viraria Fada de um time que não é o dela."""
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._lider_da_hh)
    assert "last_char_name" in fonte
    assert "meu_nick" in fonte


def test_a_fada_da_HH_vem_ANTES_do_farm_no_despacho():
    """Se ela também tivesse farm ligado, as duas coisas disputariam o teclado.

    Mesmo motivo do modo APP estar no topo.
    """
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._operate)
    i_fada = fonte.index("_lider_da_hh()")
    i_hh = fonte.index("if self.account.hh_farm")
    i_bc = fonte.index("quer_farmar = self.account.bc_farm")
    assert i_fada < i_hh < i_bc


def test_a_fada_da_HH_nao_age_sem_memoria():
    """Ela precisa saber quem está no time, onde cada um está no painel e quanta
    vida tem. Clique às cegas cura o aliado errado."""
    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = _fonte(AccountSupervisor._operate)
    # Marcador distinto de propósito: "DA HH VEM ANTES" contém
    # "A HH VEM ANTES", e a primeira versão deste teste cortou o trecho errado.
    inicio = fonte.index("lider_da_hh = self._lider_da_hh()")
    fim = fonte.index("if self.account.hh_farm")
    trecho = fonte[inicio:fim]
    assert "critical_ok" in trecho


# ===========================================================================
# A tecla existe nas duas interfaces (a rede que pegou isso na hora)
# ===========================================================================


@pytest.mark.parametrize("arquivo,esperado", [
    ("blazesbot/web_app.py", '"follow": k.follow'),
    ("blazesbot/web_app.py", "st.keys.follow ="),
    ("web/main.js", '"follow"'),
    ("web/index.html", 'id="ed-k-follow"'),
    ("blazesbot/gui/account_dialog.py", "k_follow"),
])
def test_a_tecla_de_seguir_esta_ligada_de_ponta_a_ponta(arquivo, esperado):
    """`test_teclas_nas_interfaces.py` já exige isto para TODA tecla -- aqui
    fica explícito para a de seguir, que é a que a HH+Fada precisa."""
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parent.parent
    assert esperado in (raiz / arquivo).read_text(encoding="utf-8")


def test_a_tecla_nasce_VAZIA():
    """Vazia significa "não configurada", e é o que faz a Fada avisar em vez de
    apertar algo errado. Um padrão chutado aqui seria pior que a ausência."""
    from blazesbot.config import KeyBinds

    assert KeyBinds().follow == ""


def test_o_ponto_de_entrada_da_fada_e_o_MESMO_do_lider():
    """Uma coordenada de porta por conta seria duas portas."""
    fonte = _fonte(FadaDaHH.ir_para_a_porta)
    assert "PONTO_DA_ENTRADA" in fonte
    assert mapa_hh.PONTO_DA_ENTRADA == (-343, -289)
