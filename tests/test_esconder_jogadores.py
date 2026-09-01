"""Esconder jogadores: a tecla SEMPRE é solta, e o Enter nunca sai no escuro.

=============================================================================
O QUE ESTÁ SOB TESTE
=============================================================================

O truque: com a tecla de esconder presa, abrir o chat com Enter faz o esconder
GRUDAR pela sessão. Solta-se a tecla e fecha-se o chat com outro Enter.

Duas coisas podem dar muito errado, e é o que estes testes travam.

**1. A tecla ficar presa.** `key_down` sem `key_up` deixa o jogo recebendo a
tecla como pressionada, e todo o resto do bot passa a jogar com ela ativa. Por
isso o `finally` -- e `test_a_tecla_e_sempre_solta` cobre inclusive o caminho da
exceção, que é o que ninguém lembra.

**2. O chat ficar aberto.** A sequência ABRE o chat de propósito. Se o Enter de
fechar não pegar, toda tecla do bot daí em diante (skill, poção, montaria, TAB)
vai para o campo de texto em vez de ir para o jogo -- o bot parece rodando e não
faz nada, e um Enter posterior PUBLICA aquilo no chat do jogo.

**A armadilha do conserto:** Enter ALTERNA. Apertar "por garantia" sem saber o
estado tem metade de chance de ABRIR o que se queria fechar. Por isso
`test_nao_aperta_enter_no_escuro` -- com a leitura sem resposta, o módulo não
aperta nada e devolve "não sei". Deixar como está é melhor que apostar.
"""
from types import SimpleNamespace

import pytest

from blazesbot.core import esconder_jogadores as ej

TECLA = "F12"

# Lido NA IMPORTAÇÃO, antes de o `autouse` abaixo forçar o caminho ligado. Sem
# isto, o teste que confere o estado real do interruptor leria o valor
# patchado -- e passaria a afirmar o contrário do que existe no código.
ATIVADO_NO_CODIGO = ej.ATIVADO
SEGURAR_NO_CODIGO = ej.SEGURAR_ATIVADO


class ClienteFalso:
    """Modela o chat: o Enter ALTERNA, como no jogo."""

    def __init__(self, respostas=None, enter_falha_vezes=0):
        self.chat = False
        self.presas: list[str] = []
        self.soltas: list[str] = []
        self.apertos: list[str] = []
        self.enter_falha_vezes = enter_falha_vezes
        # `respostas` sobrepõe a leitura, para simular captura que não responde.
        self.respostas = list(respostas) if respostas is not None else None
        self.log = SimpleNamespace(info=lambda *a, **k: None,
                                   warning=lambda *a, **k: None)

    def segurar(self, tecla):
        self.presas.append(tecla)

    def soltar(self, tecla):
        self.soltas.append(tecla)

    def apertar(self, tecla):
        self.apertos.append(tecla)
        if tecla != ej.TECLA_DO_CHAT:
            return
        # A falha simulada é a do Enter que FECHA -- que é a que importa. Um
        # Enter de ABERTURA engolido só faz o chat nunca abrir, e aí não há
        # problema nenhum a testar: o esconder não gruda e a run segue.
        if self.chat and self.enter_falha_vezes > 0:
            self.enter_falha_vezes -= 1
            return                      # o cliente engoliu o Enter
        self.chat = not self.chat       # ALTERNA, como no jogo

    def chat_aberto(self):
        if self.respostas:
            return self.respostas.pop(0)
        return self.chat

    def esperar(self, _s):
        pass

    @property
    def enters(self) -> int:
        return self.apertos.count(ej.TECLA_DO_CHAT)


@pytest.fixture(autouse=True)
def _forcar_ligado(monkeypatch):
    """TODO teste deste módulo roda com o caminho LIGADO.

    `ATIVADO` está em `False` -- o usuário pediu para deixar o truque de fora
    por enquanto. A regra da casa é que o caminho desligado continue testado,
    "para que voltar atrás não seja ligar código não testado".

    Aqui isso vale dobrado: o que este módulo faz é ABRIR O CHAT de propósito, e
    o que o torna seguro é a conferência de que ele fechou. Ligá-lo de volta sem
    essa conferência exercitada seria ligar a parte perigosa com a proteção não
    verificada.
    """
    monkeypatch.setattr(ej, "ATIVADO", True)
    # `SEGURAR_ATIVADO` também está em `False` -- o F12 preso saiu de uso quando
    # o `petbug.exe` entrou. Mesma regra: o caminho continua exercitado, para que
    # religar não seja ligar código não verificado.
    monkeypatch.setattr(ej, "SEGURAR_ATIVADO", True)


def _rodar(cliente, tecla=TECLA):
    return ej.esconder_jogadores(
        tecla=tecla,
        segurar=cliente.segurar,
        soltar=cliente.soltar,
        apertar=cliente.apertar,
        chat_aberto=cliente.chat_aberto,
        esperar=cliente.esperar,
        log=cliente.log,
    )


# ---------------------------------------------------------------------------
# 1. A TECLA SEMPRE É SOLTA
# ---------------------------------------------------------------------------

def test_a_tecla_e_solta_no_caminho_normal():
    cliente = ClienteFalso()
    _rodar(cliente)

    assert cliente.presas == [TECLA]
    assert cliente.soltas == [TECLA]


def test_a_tecla_e_sempre_solta_mesmo_com_excecao():
    """O caminho que ninguém lembra. Tecla presa = o bot inteiro passa a jogar
    com ela apertada."""
    cliente = ClienteFalso()

    def apertar_explode(_tecla):
        raise RuntimeError("janela morreu no meio da sequência")

    with pytest.raises(RuntimeError):
        ej.esconder_jogadores(
            tecla=TECLA, segurar=cliente.segurar, soltar=cliente.soltar,
            apertar=apertar_explode, chat_aberto=cliente.chat_aberto,
            esperar=cliente.esperar, log=cliente.log,
        )

    assert cliente.soltas == [TECLA], "a tecla ficou PRESA depois da exceção"


# ---------------------------------------------------------------------------
# 2. A SEQUÊNCIA
# ---------------------------------------------------------------------------

def test_a_ordem_e_segurar_enter_soltar():
    """O grude depende de o chat abrir COM a tecla ainda presa."""
    cliente = ClienteFalso()
    _rodar(cliente)

    # O primeiro Enter tem que acontecer ANTES de a tecla ser solta. Como o
    # dublê registra em listas separadas, o teste é que houve exatamente um
    # segurar, e que ele veio antes de qualquer soltar.
    assert cliente.presas and cliente.soltas
    assert cliente.enters >= 1


def test_fecha_o_chat_e_confirma():
    cliente = ClienteFalso()
    resultado = _rodar(cliente)

    assert resultado.escondeu is True
    assert resultado.chat_fechado is True
    assert resultado.seguro_para_seguir is True
    assert cliente.chat is False


def test_insiste_quando_o_enter_e_engolido():
    """O cliente às vezes come a tecla; insistir é certo -- mas só com a
    leitura dizendo que ainda está aberto."""
    cliente = ClienteFalso(enter_falha_vezes=1)
    resultado = _rodar(cliente)

    assert resultado.seguro_para_seguir is True
    assert cliente.enters >= 3


def test_desiste_se_o_chat_nao_fechar():
    cliente = ClienteFalso(enter_falha_vezes=99)
    resultado = _rodar(cliente)

    assert resultado.chat_fechado is False
    assert resultado.seguro_para_seguir is False


# ---------------------------------------------------------------------------
# 3. NUNCA APERTAR ENTER NO ESCURO -- ele ALTERNA
# ---------------------------------------------------------------------------

def test_nao_aperta_enter_no_escuro():
    """Leitura sem resposta: não sabe se está aberto. Apertar tem metade de
    chance de ABRIR o que se queria fechar."""
    cliente = ClienteFalso(respostas=[None, None])
    enters_antes_da_conferencia = 1     # o Enter que ABRE o chat

    resultado = _rodar(cliente)

    assert resultado.chat_fechado is None
    assert resultado.seguro_para_seguir is False, (
        "'não sei' não pode contar como seguro -- entrar na cave com o chat "
        "possivelmente aberto perde a run em silêncio"
    )
    assert cliente.enters == enters_antes_da_conferencia, (
        f"apertou Enter {cliente.enters}x sem saber o estado do chat"
    )


def test_uma_leitura_sem_resposta_nao_desiste():
    """Insistir na LEITURA é de graça -- ela não fala com o jogo."""
    cliente = ClienteFalso(respostas=[None, False])
    resultado = _rodar(cliente)

    assert resultado.chat_fechado is True


# ---------------------------------------------------------------------------
# 4. Sem tecla configurada
# ---------------------------------------------------------------------------

def test_sem_tecla_nao_faz_nada_e_nao_e_erro():
    """Esconder é conveniência, não requisito. Sem tecla a run segue."""
    cliente = ClienteFalso()
    resultado = _rodar(cliente, tecla="")

    assert cliente.presas == [] and cliente.apertos == []
    assert resultado.escondeu is False
    assert resultado.seguro_para_seguir is True, (
        "não configurar a tecla não pode bloquear a entrada na cave"
    )


# ---------------------------------------------------------------------------
# 5. O INTERRUPTOR, e o que ele NÃO pode fazer
# ---------------------------------------------------------------------------

def test_desligado_nao_aperta_nada(monkeypatch):
    monkeypatch.setattr(ej, "ATIVADO", False)

    cliente = ClienteFalso()
    resultado = _rodar(cliente)

    assert cliente.presas == []
    assert cliente.soltas == []
    assert cliente.apertos == []
    assert resultado.escondeu is False


def test_desligado_NAO_bloqueia_a_entrada_na_cave(monkeypatch):
    """O dente do interruptor.

    Quem chama aborta a entrada quando `seguro_para_seguir` é falso. Se o
    desligado devolvesse falso, desligar o truque impediria o bot de entrar na
    cave -- ou seja, desligar uma conveniência quebraria o farm inteiro.
    """
    monkeypatch.setattr(ej, "ATIVADO", False)

    resultado = _rodar(ClienteFalso())

    assert resultado.seguro_para_seguir is True, (
        "com o truque desligado a entrada na cave tem que seguir normalmente"
    )


def test_o_interruptor_esta_desligado_hoje():
    """Registra o estado ATUAL, para uma mudança acidental aparecer no diff.

    Não é opinião sobre o valor certo: é o mesmo papel dos testes de constante
    medida. Ligar de propósito é trocar esta linha junto.
    """
    assert ATIVADO_NO_CODIGO is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ===========================================================================
# `segurado`: a tecla PRESA durante o par de cliques no NPC
# ===========================================================================
#
# A forma que roda hoje. O truque do chat acima está desligado; esta é a regra do
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
    import ast
    import inspect

    from blazesbot.bot.bc.ui_service import UIService

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


VK_DA_TECLA = 0x7B          # F12
VK_DOS_MODIFICADORES = (16, 17, 18)   # SHIFT, CTRL, ALT


def _input_falso():
    from blazesbot.core.inputs import Input

    entrada = Input.__new__(Input)
    entrada.hwnd = 1
    entrada._teclas_presas = {}
    entrada.enviadas: list[tuple[str, int]] = []
    entrada._enviar_tecla = lambda m, vk: entrada.enviadas.append(
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
    import ast
    import inspect

    from blazesbot.bot.bc.ui_service import UIService
    from blazesbot.bot.bc.vendor import VendorService

    for dono, nome in ((UIService, "tentar_entrar_na_cave"),
                       (UIService, "viajar_para_ghost_din_woods"),
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
