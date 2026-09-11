"""O esconder jogadores: a tecla PRESA, e o `segurado(...)` que sobrou.

=========================================================================
O TRUQUE DO CHAT SAIU EM 10/09/2026
=========================================================================

Este arquivo tinha treze testes da sequência "segurar F12, abrir o chat com
Enter, soltar, fechar o chat" -- o truque que fazia o esconder grudar. O usuário
mandou remover: *"só funciona para o usuário, não precisa ser feito pelo bot"*.

Saíram com ele a conferência do chat aberto e o desfecho de "o chat pode ter
ficado aberto", que era o defeito mais caro daquele caminho.

O que este arquivo cobre agora:

  * `prender_a_tecla` -- KEYDOWN sem KEYUP, reafirmado a cada chamada, e a
    garantia de que **nenhum `segurado(...)` solta** o que foi preso;
  * `segurado(...)` -- o bloco que segura e solta, hoje desligado por
    interruptor, com a contagem de aninhamento que o protege.

Ver `docs/decisoes/hh.md` §31.
"""
import loggingfrom types import SimpleNamespaceimport pytestfrom blazesbot.core import esconder_jogadores as ejTECLA = "F12"

# Lido NA IMPORTAÇÃO, antes de qualquer `monkeypatch`. Sem isto, o teste que
# confere o estado real do interruptor leria o valor patchado -- e passaria a
# afirmar o contrário do que existe no código.
SEGURAR_NO_CODIGO = ej.SEGURAR_ATIVADO


@pytest.fixture(autouse=True)
def _com_o_segurar_ligado(monkeypatch):
    """Força `SEGURAR_ATIVADO` ligado para a suíte inteira.

    A fixture que fazia isto morava no bloco do truque do chat e foi embora com
    ele em 10/09/2026. Sem ela, os testes de `segurado(...)` exercitavam o
    caminho DESLIGADO e não provavam nada -- passavam por não fazer nada.

    Quem confere o estado REAL do interruptor lê `SEGURAR_NO_CODIGO`, capturado
    na importação, antes desta fixture rodar.
    """
    monkeypatch.setattr(ej, "SEGURAR_ATIVADO", True)


# ===========================================================================
# `segurado`: a tecla PRESA durante o par de cliques no NPC
# ===========================================================================
#
# O truque do chat SAIU em 10/09/2026; esta é a regra do
# usuário: *"sempre que precisar o clique no NPC fora da cave é importante que o
# F12 esteja apertado... só no par de clique, porque só atrapalha quando tenta
# clicar no NPC em si."*
#
# TODO clique de NPC do bot passa por `UIService._abrir_dialogo_e_clicar`, então
# um `with` ali cobre os quatro: link da cave, Rich, Altar Stone e saída.
#
# O TESTE QUE CARREGA O PESO é o da exceção. Tecla presa que não é solta faz o bot
# passar o RESTO DA SESSÃO jogando com ela apertada -- e as saídas por exceção
# deste trecho são muitas (`StopRequested`, `Disconnected`, `FarmDesligado`, e
# qualquer falha do clique).


class _Registro:
    def __init__(self):
        self.eventos: list[tuple[str, str]] = []
        self.log = SimpleNamespace(info=lambda *a, **k: None)

    def segurar(self, tecla):
        self.eventos.append(("down", tecla))

    def soltar(self, tecla):
        self.eventos.append(("up", tecla))

    def dentro(self):
        self.eventos.append(("clique", ""))


def _bloco(registro, tecla=TECLA):
    return ej.segurado(tecla=tecla, segurar=registro.segurar,
                       soltar=registro.soltar, log=registro.log)


def test_segura_antes_e_solta_depois():
    r = _Registro()
    with _bloco(r):
        r.dentro()

    assert r.eventos == [("down", TECLA), ("clique", ""), ("up", TECLA)]


def test_solta_a_tecla_MESMO_com_excecao():
    """O caminho que ninguém lembra, e o caro.

    Sem o `finally` do context manager, uma exceção no clique deixaria F12 preso
    pelo resto da sessão -- e todo o resto do bot passaria a jogar com ela.
    """
    r = _Registro()

    with pytest.raises(RuntimeError):
        with _bloco(r):
            raise RuntimeError("a janela morreu no meio do clique")

    assert ("up", TECLA) in r.eventos, "a tecla ficou PRESA depois da exceção"


def test_nao_engole_a_excecao_de_quem_chamou():
    """Engolir aqui faria uma queda no clique do NPC virar 'deu tudo certo'."""
    r = _Registro()

    with pytest.raises(ValueError):
        with _bloco(r):
            raise ValueError("erro de quem chamou")


def test_sem_tecla_configurada_nao_toca_em_nada():
    """Esconder é conveniência. Sem tecla, o bloco roda igual."""
    r = _Registro()
    with _bloco(r, tecla=""):
        r.dentro()

    assert r.eventos == [("clique", "")], (
        "mexeu no teclado sem tecla configurada"
    )


def test_solta_UMA_vez_so():
    """Soltar duas vezes é inofensivo, mas duas linhas de log confundem quem lê."""
    r = _Registro()
    with _bloco(r):
        pass

    assert [e for e in r.eventos if e[0] == "up"] == [("up", TECLA)]


def test_o_par_de_cliques_do_NPC_esta_dentro_do_bloco():
    """Estrutural: se alguém tirar o `with` de `_abrir_dialogo_e_clicar`, os
    quatro cliques de NPC perdem a proteção de uma vez -- e nada no comportamento
    denunciaria isso."""
    import ast    import inspect    from blazesbot.bot.bc.ui_service import UIService

    fonte = inspect.getsource(UIService._abrir_dialogo_e_clicar)
    arvore = ast.parse(fonte.lstrip())
    withs = [n for n in ast.walk(arvore) if isinstance(n, ast.With)]

    assert withs, (
        "`_abrir_dialogo_e_clicar` não tem `with` nenhum -- o F12 deixou de ser "
        "segurado durante o clique no NPC"
    )


# ===========================================================================
# ANINHAMENTO: segurar dentro de segurar não solta no meio
# ===========================================================================
#
# O bot segura a MESMA tecla em blocos aninhados: o processo inteiro por fora
# (entrada na cave, venda, Fay) e o par de cliques no NPC por dentro. Sem
# contagem, o bloco INTERNO soltaria a tecla enquanto o externo ainda a queria --
# e o defeito seria invisível, porque o log das duas vezes diria "segurei".
#
# O bloco longo existe porque o curto não funcionou. Palavras do usuário:
# *"clicar só pelo tempo do clique acaba fazendo não clicar direito,
# principalmente ao entrar na cave."* Com `postmessage_puro` as mensagens da
# tecla entram na MESMA fila POSTADA do clique, encostadas nele.


_LOG = logging.getLogger("teste.esconder")


VK_DA_TECLA = 0x7B          # F12
VK_DOS_MODIFICADORES = (16, 17, 18)   # SHIFT, CTRL, ALT


def _input_falso():
    from blazesbot.core.inputs import Input

    entrada = Input.__new__(Input)
    entrada.hwnd = 1
    entrada._teclas_presas = {}
    # A lista de INTOCÁVEIS -- ver `Input.segurar_para_sempre`.
    entrada._presas_para_sempre = set()
    entrada.enviadas: list[tuple[str, int]] = []
    entrada._enviar_tecla = lambda m, vk, lp=0: entrada.enviadas.append(
        ("down" if m == 0x0100 else "up", vk))
    return entrada


def _soltas(entrada) -> list[tuple[str, int]]:
    """Os KEYUP DA TECLA DESTE TESTE, sem o ruído dos modificadores.

    `key_down` solta SHIFT/CTRL/ALT antes de cada tecla alvo -- é a mitigação de
    Input Bleed (Eixo 1) em `Input._liberar_modificadores_fisicos`, e ela não
    tem nada a ver com o aninhamento que estes testes defendem. Filtrar por
    "qualquer up" fazia estes testes reprovarem por causa DELA, escondendo se a
    regra do aninhamento continuava valendo ou não.
    """
    return [e for e in entrada.enviadas
            if e[0] == "up" and e[1] not in VK_DOS_MODIFICADORES]


def test_segurar_aninhado_manda_UM_keydown_so():
    entrada = _input_falso()

    entrada.key_down(TECLA)
    entrada.key_down(TECLA)

    assert [e for e in entrada.enviadas if e[0] == "down"] == [("down", 0x7B)]


def test_o_bloco_INTERNO_nao_solta_a_tecla():
    """O dente do aninhamento.

    Se o interno soltasse, o clique do NPC rodaria protegido e o RESTO do
    processo -- a caminhada, a conferência de coordenada, as outras tentativas --
    rodaria sem proteção. E nada no log diria isso.
    """
    entrada = _input_falso()

    entrada.key_down(TECLA)          # bloco externo: o processo
    entrada.key_down(TECLA)          # bloco interno: o par de cliques
    entrada.key_up(TECLA)            # o interno termina

    assert not _soltas(entrada), (
        "o bloco interno soltou a tecla; o resto do processo ficou desprotegido"
    )
    assert entrada.teclas_presas() == {TECLA: 1}


def test_o_bloco_EXTERNO_solta():
    entrada = _input_falso()

    entrada.key_down(TECLA)
    entrada.key_down(TECLA)
    entrada.key_up(TECLA)
    entrada.key_up(TECLA)

    assert _soltas(entrada) == [("up", VK_DA_TECLA)]
    assert entrada.teclas_presas() == {}


def test_o_contador_e_POR_TECLA():
    entrada = _input_falso()

    entrada.key_down("F12")
    entrada.key_down("F11")
    entrada.key_up("F11")

    assert entrada.teclas_presas() == {"F12": 1}


def test_soltar_a_mais_e_REDE_e_nao_erro():
    """KEYUP de tecla não apertada é ignorado pelo jogo. Se o contador sair de
    sincronia, soltar por engano é o lado SEGURO do erro."""
    entrada = _input_falso()

    entrada.key_up(TECLA)

    assert entrada.teclas_presas() == {}
    assert entrada.enviadas == [("up", 0x7B)]


def test_os_tres_processos_seguram_a_tecla():
    """Estrutural: os três momentos que o usuário nomeou têm o `with`.

    Se alguém tirar um deles, aquele processo volta a rodar com os outros
    jogadores na tela -- e o sintoma seria "às vezes o clique não pega", que é
    exatamente o que já custou uma rodada de investigação.
    """
    import ast    import inspect    from blazesbot.bot.bc.ui_service import UIService    from blazesbot.bot.bc.vendor import VendorService    from blazesbot.bot.ui_do_jogo import UIDoJogo

    # `viajar_pelo_transporte` subiu para `UIDoJogo` em 01/09/2026: a viagem pelo
    # NPC de transporte é a mesma nas duas caves, então segurar o F12 durante
    # ela passou a valer para as duas de uma vez.
    for dono, nome in ((UIService, "tentar_entrar_na_cave"),
                       (UIDoJogo, "viajar_pelo_transporte"),
                       (VendorService, "_open_npc")):
        fonte = inspect.getsource(getattr(dono, nome))
        withs = [n for n in ast.walk(ast.parse(fonte.lstrip()))
                 if isinstance(n, ast.With)]
        assert withs, f"{dono.__name__}.{nome} não segura a tecla de esconder"


def test_o_F12_preso_esta_DESLIGADO_hoje():
    """Registra o estado atual: o `petbug.exe` assumiu o esconder.

    Não é opinião sobre o valor certo -- é o mesmo papel dos testes de constante
    medida, para uma mudança acidental aparecer no diff.
    """
    assert SEGURAR_NO_CODIGO is False


def test_desligado_o_bloco_roda_sem_tocar_no_teclado(monkeypatch):
    monkeypatch.setattr(ej, "SEGURAR_ATIVADO", False)

    r = _Registro()
    with _bloco(r):
        r.dentro()

    assert r.eventos == [("clique", "")], (
        "com o F12 preso desligado, o bloco não pode mexer no teclado"
    )


# ===========================================================================
# A TECLA PRESA PARA SEMPRE -- o caminho do patcher, 07/09/2026
# ===========================================================================

def test_prender_a_tecla_manda_KEYDOWN_e_nenhum_KEYUP():
    """*"É sobre deixar a tecla F12 down sempre clicado, nunca soltar"* —
    usuário, 07/09/2026, depois de os jogadores não sumirem.

    É o que o `BlazesBot - PetBug.exe` faz, lido por dentro: `WM_KEYDOWN` e
    nunca o `WM_KEYUP`. A tecla esconde ENQUANTO está apertada, então nunca
    soltar é esconder para sempre.
    """
    from blazesbot.core import esconder_jogadores as mod

    entrada = _input_falso()
    assert mod.prender_a_tecla("F12", entrada.segurar_para_sempre, _LOG)
    assert entrada.enviadas == [("down", 0x7B)], entrada.enviadas


def test_a_tecla_presa_e_REAFIRMADA_a_cada_chamada():
    """Tecla fisicamente presa repete sozinha -- reafirmar é imitar isso.

    E é o que devolve o esconder depois de um relogin, quando a janela é outra.
    `key_down` faz o contrário de propósito: conta aninhamento e manda UMA vez.
    """
    from blazesbot.core import esconder_jogadores as mod

    entrada = _input_falso()
    for _ in range(3):
        mod.prender_a_tecla("F12", entrada.segurar_para_sempre, _LOG)
    assert entrada.enviadas == [("down", 0x7B)] * 3, entrada.enviadas


def test_a_tecla_presa_NAO_e_solta_por_um_bloco_segurado():
    """O furo que a lista de intocáveis fecha.

    Qualquer `segurado(...)` da MESMA tecla soltaria no fim do bloco justamente
    o que se quer permanente -- e o efeito só apareceria na tela, sem uma linha
    no log.
    """
    from blazesbot.core import esconder_jogadores as mod

    entrada = _input_falso()
    mod.prender_a_tecla("F12", entrada.segurar_para_sempre, _LOG)
    entrada.enviadas.clear()

    entrada.key_down("F12")
    entrada.key_up("F12")
    entrada.key_up("F12")          # até soltar a mais não pode soltar

    assert ("up", 0x7B) not in entrada.enviadas, entrada.enviadas


def test_soltar_de_vez_desfaz_a_tecla_presa():
    """Tem de haver um caminho de volta -- senão o estado é uma armadilha."""
    from blazesbot.core import esconder_jogadores as mod

    entrada = _input_falso()
    mod.prender_a_tecla("F12", entrada.segurar_para_sempre, _LOG)
    entrada.enviadas.clear()

    assert entrada.soltar_de_vez("F12")
    assert entrada.enviadas == [("up", 0x7B)]
    entrada.enviadas.clear()
    entrada.key_down("F12")
    entrada.key_up("F12")
    assert ("up", 0x7B) in entrada.enviadas, "continuou intocável"


def test_o_interruptor_DESLIGA_a_tecla_presa(monkeypatch):
    from blazesbot.core import esconder_jogadores as mod

    monkeypatch.setattr(mod, "PRENDER_A_TECLA", False)
    entrada = _input_falso()
    assert mod.prender_a_tecla("F12", entrada.segurar_para_sempre, _LOG) is False
    assert entrada.enviadas == []


def test_sem_tecla_configurada_nao_aperta_nada():
    """Quem não configurou o esconder simplesmente não usa. Não é erro."""
    from blazesbot.core import esconder_jogadores as mod

    entrada = _input_falso()
    assert mod.prender_a_tecla("", entrada.segurar_para_sempre, _LOG) is False
    assert mod.prender_a_tecla("   ", entrada.segurar_para_sempre, _LOG) is False
    assert entrada.enviadas == []
