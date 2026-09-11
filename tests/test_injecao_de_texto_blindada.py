"""A INJEÇÃO DE TEXTO É CIRÚRGICA: destino provado, tamanho limitado, conteúdo válido.

=========================================================================
O DEFEITO QUE ESTES TESTES IMPEDEM DE VOLTAR -- 09/09/2026
=========================================================================

O usuário capturou **918 caracteres** de lixo digitados no BLOCO DE NOTAS,
crescendo ~10 por tentativa, durante um laço de relogin:

    dcgspkjpxfeublmmumyvpcbbwjvkdrqwzzxsvcfgtmgiviiuzlvsqiuekskvyoggokjodgn...

O texto ter chegado ao Bloco de Notas é a prova de onde o defeito estava.
`PostMessageW`/`SendMessageW` entregam a UM `hwnd`: para caracteres aparecerem
noutro programa, o `hwnd` que o bot usava **era** do outro programa. E o
Windows RECICLA valores de handle -- é o defeito que a trava de janela existe
para impedir, e que ela deixou passar.

A BRECHA, exata: no PINO TARDIO de `Input._motivo_para_nao_enviar`, quando o
nome do processo dono da janela não podia ser lido (`None`), o pino fechava
MESMO ASSIM e liberava o envio. Pior: `_nome_do_processo` ficava `None` para
sempre, e a conferência periódica (`is not None and !=`) nunca mais disparava.
O `Input` ficava permanentemente preso a uma janela que ninguém provou ser o
jogo.

No laço de relogin isso é o cenário exato: o cliente morre no meio do login, o
handle é reciclado, e a leitura do processo falha justamente porque tudo está
mudando ao mesmo tempo.

A correção é uma DISTINÇÃO, não uma trava nova -- e os dois lados dela são
testados aqui:

  ESTABELECER o pino com "não sei"  -> BLOQUEIA (nunca houve prova)
  MANTER um pino JÁ CONFIRMADO      -> NÃO bloqueia (o comportamento original,
                                       que impede o bot de ficar mudo)
"""
from __future__ import annotations

import pytest

from blazesbot.core import inputs as mod
from blazesbot.core.inputs import (
    LIMITE_DE_BACKSPACES,
    LIMITE_DE_CARACTERES,
    Input,
    TextoRecusado,
)

HWND_QUALQUER = 4242
PID_DO_JOGO = 111
PID_DO_BLOCO_DE_NOTAS = 222


def _input_cru() -> Input:
    """Um `Input` sem `__init__` -- só o estado que a trava e a digitação tocam."""
    inp = object.__new__(Input)
    inp.hwnd = HWND_QUALQUER
    inp._pid_da_janela = None
    inp._nome_do_processo = None
    inp._conferido_em = 0.0
    inp._bloqueadas = 0
    inp._motivo_do_bloqueio = None
    inp._teclas_presas = {}
    inp._presas_para_sempre = set()
    return inp


@pytest.fixture
def mundo(monkeypatch):
    """Dubla as três perguntas do Windows que a trava faz."""

    class _Mundo:
        def __init__(self):
            self.dono = PID_DO_JOGO
            self.nome: str | None = "client.exe"
            self.janela_existe = True
            self.enviadas: list[tuple[int, int]] = []

    m = _Mundo()
    monkeypatch.setattr(mod, "_dono_da_janela", lambda hwnd: m.dono)
    monkeypatch.setattr(mod, "_nome_do_processo", lambda pid: m.nome)

    class _User32:
        @staticmethod
        def IsWindow(h):
            return m.janela_existe

    monkeypatch.setattr(mod, "user32", _User32)
    monkeypatch.setattr(Input, "_enviar_tecla",
                        lambda self, msg, wp, lp=0: m.enviadas.append((msg, wp)))
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    return m


# ===========================================================================
# EIXO 2 -- O DESTINO. A brecha que produziu o lixo no Bloco de Notas.
# ===========================================================================


def test_processo_NAO_IDENTIFICADO_nao_fecha_o_pino_nem_libera_o_envio(mundo):
    """O caso exato do vazamento: handle reciclado + processo ilegível.

    Ficar mudo por alguns ciclos é reversível; digitar a senha na janela de
    outro programa não é.
    """
    mundo.nome = None                      # `psutil` não respondeu
    inp = _input_cru()

    assert inp._janela_confiavel() is False
    assert inp._pid_da_janela is None, (
        "o pino fechou sem prova — o `Input` fica preso a uma janela que "
        "ninguém confirmou ser o jogo, e a conferência periódica nunca mais "
        "dispara")

    inp.type_string_safely("senha-secreta", rotulo="senha")
    assert mundo.enviadas == [], "vazou tecla para janela não identificada"


def test_a_prova_positiva_fecha_o_pino_e_libera(mundo):
    mundo.nome = "client.exe"
    inp = _input_cru()
    assert inp._janela_confiavel() is True
    assert inp._pid_da_janela == PID_DO_JOGO
    assert inp._nome_do_processo == "client.exe"


def test_pino_JA_CONFIRMADO_nao_emudece_por_leitura_que_falhou(mundo):
    """O outro lado da distinção, e ele é o comportamento ORIGINAL.

    Um `AccessDenied` passageiro não pode trocar um defeito raro (tecla na
    janela errada) por um permanente (bot mudo). Trocar isto quebra a regra
    que o projeto já pagou para aprender.
    """
    inp = _input_cru()
    assert inp._janela_confiavel() is True          # fecha o pino com prova

    mundo.nome = None                                # agora o psutil falha
    inp._conferido_em = -9999                        # força a reconferência
    assert inp._janela_confiavel() is True, (
        "leitura que falhou passou a emudecer o bot — é o defeito permanente "
        "no lugar do raro")


def test_janela_que_trocou_de_dono_bloqueia(mundo):
    inp = _input_cru()
    assert inp._janela_confiavel() is True
    mundo.dono = PID_DO_BLOCO_DE_NOTAS               # o Windows reciclou o hwnd
    assert inp._janela_confiavel() is False
    inp.type_string_safely("blazesgamer", rotulo="login")
    assert mundo.enviadas == []


def test_a_digitacao_PARA_quando_a_janela_morre_no_meio(mundo):
    """É o caso normal do relogin: o cliente cai com a senha sendo digitada.

    Antes, o `_enviar_tecla` barrava cada mensagem em silêncio e o laço seguia
    até o fim -- nenhuma parada, e o resto do texto perseguindo um handle que
    já podia ter mudado de dono.
    """
    inp = _input_cru()
    original = Input._janela_confiavel
    chamadas = {"n": 0}

    def _confiavel(self):
        chamadas["n"] += 1
        if chamadas["n"] > 4:          # morre no meio da digitação
            return False
        return original(self)

    Input._janela_confiavel = _confiavel
    try:
        saiu = inp.type_string_safely("abcdefghij", rotulo="login")
    finally:
        Input._janela_confiavel = original

    assert saiu < 10, "digitou o texto inteiro contra uma janela já perdida"
    # Os três `WM_KEYUP` dos modificadores saem antes do primeiro caractere.
    chars = [wp for msg, wp in mundo.enviadas if msg == mod.WM_CHAR]
    assert len(chars) == saiu


# ===========================================================================
# EIXO 1 -- O LIMITE. Nada que este bot digita é longo.
# ===========================================================================


def test_texto_acima_do_teto_LEVANTA_e_nao_digita_nada(mundo):
    inp = _input_cru()
    lixo = "dcgspkjpxfeublmmumyvpcbbwjvkdrqwzz" * 30     # 1020 caracteres
    with pytest.raises(TextoRecusado) as erro:
        inp.type_string_safely(lixo, rotulo="senha")
    assert "1020" in str(erro.value)
    assert mundo.enviadas == [], "digitou antes de recusar"


def test_o_teto_cabe_o_caso_legitimo_com_folga():
    """O teto existe para o defeito, não para apertar o uso normal."""
    assert LIMITE_DE_CARACTERES >= 40
    for legitimo in ("blazesgamer", "mfaustoapp069", "WizzOfBlazes4"):
        assert len(legitimo) < LIMITE_DE_CARACTERES


def test_caractere_de_controle_e_recusado(mundo):
    """Byte cru de leitura de memória chegando aqui como se fosse texto."""
    inp = _input_cru()
    with pytest.raises(TextoRecusado):
        inp.type_string_safely("blazes\x00gamer\x07", rotulo="login")
    assert mundo.enviadas == []


def test_o_que_nao_e_texto_e_recusado(mundo):
    inp = _input_cru()
    with pytest.raises(TextoRecusado):
        inp.type_string_safely(b"blazesgamer", rotulo="login")
    assert mundo.enviadas == []


def test_backspace_acima_do_teto_LEVANTA(mundo):
    """A outra suspeita: o laço de limpeza enlouquecido."""
    inp = _input_cru()
    with pytest.raises(TextoRecusado):
        inp.clear_field(5000)
    assert mundo.enviadas == []


def test_o_teto_do_backspace_cabe_o_pedido_do_login():
    """`login._do_credentials` pede 50 -- o maior pedido legítimo."""
    assert LIMITE_DE_BACKSPACES >= 50


def test_a_limpeza_usa_VK_BACK_e_nao_letras(mundo):
    """Um laço de limpeza mapeado na tecla errada digitaria letras em vez de
    apagar -- era a primeira suspeita do lixo."""
    inp = _input_cru()
    inp.clear_field(3)
    assert mod.VK_CODES["BACKSPACE"] == 0x08

    # SÓ BACKSPACE como tecla alvo. Os `WM_KEYUP` de SHIFT/CTRL/ALT que o
    # `key_down` manda antes são outra coisa -- e é justamente o que NÃO pode
    # aparecer aqui que o teste persegue: código de LETRA.
    alvos = [wp for msg, wp in mundo.enviadas if msg == mod.WM_KEYDOWN]
    assert alvos == [0x08] * 3, alvos
    letras = [wp for _m, wp in mundo.enviadas if 0x41 <= wp <= 0x5A]
    assert letras == [], (
        f"a limpeza mandou código de letra ({letras}) — é o laço mapeado na "
        f"tecla errada, a primeira suspeita do lixo")


# ===========================================================================
# EIXO 3 -- FILA LIMPA. Modificador preso troca a tecla do outro lado.
# ===========================================================================


def test_solta_os_modificadores_ANTES_de_digitar(mundo):
    """Um SHIFT grudado transforma o login inteiro em maiúsculas."""
    inp = _input_cru()
    inp.type_string_safely("ab", rotulo="login")

    mods = {mod.VK_CODES[m] for m in ("SHIFT", "CTRL", "ALT")}
    primeiros = [wp for msg, wp in mundo.enviadas[:3]]
    assert set(primeiros) == mods, (
        "a digitação começou sem soltar os modificadores")
    assert all(msg == mod.WM_KEYUP for msg, _ in mundo.enviadas[:3])


def test_uma_liberacao_por_injecao_e_nao_por_caractere(mundo):
    """Três mensagens a mais por texto é barato; por caractere, não."""
    inp = _input_cru()
    inp.type_string_safely("abcdefghij", rotulo="login")
    keyups = [wp for msg, wp in mundo.enviadas if msg == mod.WM_KEYUP]
    assert len(keyups) == 3


# ===========================================================================
# O LOGIN -- usa a blindada, com rótulo, e não engole a recusa
# ===========================================================================


def test_o_login_usa_a_funcao_BLINDADA():
    import inspect

    from blazesbot.bot.login import LoginSequence

    fonte = inspect.getsource(LoginSequence._type)
    assert "type_string_safely" in fonte, (
        "o login voltou para o caminho sem trava")

    credenciais = inspect.getsource(LoginSequence._do_credentials)
    assert 'rotulo="login"' in credenciais
    assert 'rotulo="senha"' in credenciais, (
        "sem rótulo, o log não diz O QUE estava sendo digitado quando falhou")


def test_o_login_ABORTA_quando_a_digitacao_sai_pela_metade():
    """Login pela metade não é login: é tentativa queimada no servidor, e
    tentativa queimada é o caminho para a conta bloqueada."""
    import inspect

    from blazesbot.bot.login import LoginSequence

    fonte = inspect.getsource(LoginSequence._do_credentials)
    assert fonte.count("LoginError(") >= 2, (
        "a digitação parcial segue em frente — o servidor recebe credencial "
        "truncada e conta uma recusa")


def test_a_senha_NUNCA_vai_para_o_log():
    """`rotulo` diz O QUE era e o número diz O TAMANHO; o texto, nunca.

    LÊ O AST, e não o texto: a primeira versão deste teste reprovava por causa
    de `len(text)`, que é justamente a forma CERTA de falar do texto sem
    mostrá-lo. Procurar substring aqui reprova o acerto junto com o erro.
    """
    import ast
    import inspect
    import textwrap

    from blazesbot.core.inputs import Input

    arvore = ast.parse(textwrap.dedent(inspect.getsource(Input.type_string_safely)))
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
            continue
        if not (isinstance(no.func.value, ast.Name)
                and no.func.value.id == "_logger"):
            continue
        for arg in no.args:
            # `text` ou `ch` CRUS num argumento de log põem o segredo no
            # arquivo. `len(text)` é um número e pode.
            assert not (isinstance(arg, ast.Name) and arg.id in ("text", "ch")), (
                "o texto digitado chegou cru a uma chamada de log")


def test_o_login_nunca_manda_a_senha_para_o_log():
    """A mesma regra no chamador: o `LoginError` da senha fala de TAMANHO."""
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.login import LoginSequence

    fonte = textwrap.dedent(inspect.getsource(LoginSequence._do_credentials))
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if not isinstance(no, ast.JoinedStr):
            continue
        for parte in no.values:
            if not isinstance(parte, ast.FormattedValue):
                continue
            assert not (isinstance(parte.value, ast.Name)
                        and parte.value.id == "senha"), (
                "a senha entrou numa mensagem de erro")
