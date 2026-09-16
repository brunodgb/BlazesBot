"""A MONTAGEM DO TIME DO APP -- o líder convida, um por vez. 16/09/2026.

O desenho inteiro veio de uma sessão de perguntas com o usuário; o porquê de
cada decisão está no cabeçalho de `bot/time_do_app.py`. Aqui se travam as que,
se mudarem por acidente, quebram calado:

    SÓ O LÍDER MONTA          -- seguidor que volta sem time não faz nada
    NÃO CONVIDA ÀS CEGAS      -- quem não publica sinal de vida não entra na fila
    UM POR VEZ                -- a Block list é limpa, o alvo é sempre a linha 1
    ROTAÇÃO COM TETO          -- 4 passadas e o resto fica para o próximo ciclo
    EM BATALHA NÃO MONTA      -- abrir janela com mob batendo é apanhar parado
    NO ARRANQUE DO APP CONFERE -- o usuário abre o bot com as contas já logadas
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from blazesbot.bot import mural
from blazesbot.bot import time_do_app as mod


class _Memoria:
    def __init__(self, time_do_jogo=None):
        self._time = time_do_jogo

    def time_do_jogo(self):
        return self._time

    def tamanho_do_time(self):
        return len(self._time) if self._time is not None else None


class _Sup:
    """O supervisor cru, com só o que a montagem toca."""

    def __init__(self, lider="lider", membros=("lider", "s1", "s2"),
                 nicks=None, sou_o_lider=True):
        self.account = SimpleNamespace(login="lider" if sou_o_lider else "s1",
                                       last_char_name="Lider")
        self.config = SimpleNamespace(accounts=[])
        self.pid = 1
        self.hwnd = 1
        self.stop_event = SimpleNamespace(is_set=lambda: False)
        self.pause_event = None
        self.linhas: list[tuple[str, str]] = []
        self.log = SimpleNamespace(
            info=lambda f, *a: self.linhas.append(("INFO", f % a if a else f)),
            warning=lambda f, *a: self.linhas.append(("WARN", f % a if a else f)),
            debug=lambda *a, **k: None)
        self._membros = list(membros)
        self._nicks = nicks or {"lider": "Lider", "s1": "Um", "s2": "Dois"}
        self._lider = lider

    def _membros_do_time(self):
        return list(self._membros)

    def _nick_do_login(self, login):
        return self._nicks.get(login, "")

    def _dono_da_macro(self):
        return SimpleNamespace(login=self._lider)


@pytest.fixture(autouse=True)
def _sem_espera_de_verdade(monkeypatch):
    """A espera pela resposta é de 4 s no jogo. Aqui ela só precisa EXISTIR.

    Sem isto o arquivo leva 49 s -- quatro passadas de quatro segundos em cada
    teste que não aceita. O que se está travando é a ordem e a contagem, não o
    relógio.
    """
    monkeypatch.setattr(mod, "ESPERA_PELA_RESPOSTA", 0.01)
    monkeypatch.setattr(mod, "PASSO_DA_ESPERA_DO_TIME", 0.001)


@pytest.fixture(autouse=True)
def _mural_limpo():
    mural.zerar_o_time_para_teste()
    yield
    mural.zerar_o_time_para_teste()


def _de_pe(*logins):
    for login in logins:
        mural.publicar_estado(login, nick=login, max_hp=1000)


# ---------------------------------------------------------------------------
# QUEM FALTA
# ---------------------------------------------------------------------------

def test_time_completo_nao_falta_ninguem():
    sup = _Sup()
    memoria = _Memoria(["Lider", "Um", "Dois"])
    assert mod.falta_alguem(sup, memoria) == []


def test_time_vazio_faltam_todos_os_seguidores():
    """O líder sozinho: `time_do_jogo()` devolve só ele (ou lista vazia)."""
    sup = _Sup()
    assert mod.falta_alguem(sup, _Memoria(["Lider"])) == ["s1", "s2"]
    assert mod.falta_alguem(sup, _Memoria([])) == ["s1", "s2"]


def test_um_so_faltando():
    sup = _Sup()
    assert mod.falta_alguem(sup, _Memoria(["Lider", "Um"])) == ["s2"]


def test_SEM_leitura_do_time_nao_monta_nada():
    """"Não sei" não convida: cada convite abre a Block list no meio da macro."""
    sup = _Sup()
    assert mod.falta_alguem(sup, _Memoria(None)) is None
    assert mod.montar_o_time(sup, _Memoria(None)) is False


def test_seguidor_SEM_NICK_e_pulado_com_aviso():
    """Sem nick não há linha para adicionar na Block list."""
    sup = _Sup(nicks={"lider": "Lider", "s1": "Um", "s2": ""})
    assert mod.falta_alguem(sup, _Memoria(["Lider"])) == ["s1"]
    assert any("nunca logou" in t for _n, t in sup.linhas), sup.linhas


# ---------------------------------------------------------------------------
# SÓ O LÍDER, E SÓ COM SINAL DE VIDA
# ---------------------------------------------------------------------------

def test_SEGUIDOR_nao_monta_time(monkeypatch):
    """*"Os seguidores, caso voltem e estejam sem time, não devem fazer nada."*"""
    sup = _Sup(sou_o_lider=False)          # eu sou 's1', o líder é 'lider'
    _de_pe("s1", "s2")
    chamou = []
    monkeypatch.setattr(mod, "BotContext", lambda **k: chamou.append(1))
    assert mod.montar_o_time(sup, _Memoria(["Um"])) is False
    assert chamou == [], "o seguidor abriu a montagem"


def test_quem_NAO_publica_sinal_de_vida_fica_fora_da_fila(monkeypatch):
    """*"Se algum seguidor estiver off não vai dar para enviar o convite."*"""
    sup = _Sup()
    _de_pe("s1")                            # 's2' está fora
    convidados = []
    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _team_falso(convidados, aceita=()))

    mod.montar_o_time(sup, _Memoria(["Lider"]))
    assert [n for n in convidados] == ["Um"] * mod.TENTATIVAS_POR_MEMBRO
    assert any("sem sinal de vida" in t for _n, t in sup.linhas), sup.linhas


def test_ninguem_de_pe_NAO_abre_a_block_list(monkeypatch):
    sup = _Sup()
    abriu = []
    monkeypatch.setattr(mod, "BotContext", lambda **k: abriu.append(1))
    assert mod.montar_o_time(sup, _Memoria(["Lider"])) is False
    assert abriu == []


# ---------------------------------------------------------------------------
# O CONVITE, A ROTAÇÃO E O TETO
# ---------------------------------------------------------------------------

def _ctx_falso(**kwargs):
    return SimpleNamespace(close=lambda: None)


def _team_falso(convidados, aceita=(), memoria=None):
    """Fábrica de `TeamService` de mentira: registra quem foi convidado."""
    aceitos = set(aceita)

    class _Team:
        def __init__(self, ctx):
            self.ctx = ctx

        def _enviar_convite(self, nick):
            convidados.append(nick)
            if nick in aceitos:
                # Simula a outra ponta: anuncia o aceite no mural.
                mural.anunciar_aceite("Lider", nick)
            return True

    return _Team


def test_convida_UM_POR_VEZ_e_para_quando_todos_entram(monkeypatch):
    sup = _Sup()
    _de_pe("s1", "s2")
    convidados = []
    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _team_falso(convidados,
                                                        aceita=("Um", "Dois")))

    assert mod.montar_o_time(sup, _Memoria(["Lider"])) is True
    assert convidados == ["Um", "Dois"], convidados


def test_quem_NAO_aceita_volta_para_o_fim_da_fila(monkeypatch):
    """Rotação: tenta o próximo antes de insistir no mesmo."""
    sup = _Sup()
    _de_pe("s1", "s2")
    convidados = []
    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _team_falso(convidados,
                                                        aceita=("Dois",)))

    mod.montar_o_time(sup, _Memoria(["Lider"]))
    # 1ª passada: Um (não aceita), Dois (aceita). Depois só Um sobra.
    assert convidados[:2] == ["Um", "Dois"]
    assert set(convidados[2:]) == {"Um"}, convidados


def test_o_TETO_de_passadas_encerra_a_montagem(monkeypatch):
    """*"Limite de 4 tentativas por vez, daí tenta na próxima macro."*"""
    sup = _Sup()
    _de_pe("s1")
    convidados = []
    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _team_falso(convidados, aceita=()))

    assert mod.montar_o_time(sup, _Memoria(["Lider"])) is False
    assert len(convidados) == mod.TENTATIVAS_POR_MEMBRO, convidados
    assert any("não entraram" in t for _n, t in sup.linhas), sup.linhas


def test_a_montagem_que_EXPLODE_nao_derruba_o_APP(monkeypatch):
    sup = _Sup()
    _de_pe("s1")

    class _Explode:
        def __init__(self, ctx):
            raise RuntimeError("a Block list sumiu")

    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _Explode)
    assert mod.montar_o_time(sup, _Memoria(["Lider"])) is False
    assert any("a montagem falhou" in t for _n, t in sup.linhas), sup.linhas


# ---------------------------------------------------------------------------
# A PORTA DO LAÇO
# ---------------------------------------------------------------------------

def test_EM_BATALHA_nao_monta(monkeypatch):
    sup = _Sup()
    chamou = []
    monkeypatch.setattr(mod, "montar_o_time", lambda s, m: chamou.append(1))
    assert mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=True) is False
    assert chamou == []


def test_SEM_leitura_de_batalha_monta_do_mesmo_jeito(monkeypatch):
    """"Não sei" conta como FORA: o comportamento cego é o de sempre."""
    sup = _Sup()
    chamou = []
    monkeypatch.setattr(mod, "montar_o_time",
                        lambda s, m: chamou.append(1) or True)
    mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=None)
    assert chamou == [1]


def test_NO_ARRANQUE_a_cadencia_ja_esta_aberta(monkeypatch):
    """*"Quando eu iniciar o APP e for um líder, tem que verificar também se
    está em time, pois às vezes eu posso abrir o BlazesBot depois de estar com
    as contas logadas."* -- e foi exatamente o que falhou no teste dele."""
    sup = _Sup()
    chamou = []
    monkeypatch.setattr(mod, "montar_o_time",
                        lambda s, m: chamou.append(1) or True)
    mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=False)
    assert chamou == [1], "o arranque não conferiu o time"


def test_a_CADENCIA_segura_a_segunda_chamada(monkeypatch):
    sup = _Sup()
    chamou = []
    monkeypatch.setattr(mod, "montar_o_time",
                        lambda s, m: chamou.append(1) or True)
    mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=False)
    mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=False)
    assert chamou == [1], "conferiu duas vezes dentro da cadência"


def test_o_interruptor_DESLIGA_a_montagem(monkeypatch):
    monkeypatch.setattr(mod, "ATIVADO", False)
    sup = _Sup()
    _de_pe("s1", "s2")
    abriu = []
    monkeypatch.setattr(mod, "BotContext", lambda **k: abriu.append(1))
    assert mod.montar_o_time(sup, _Memoria(["Lider"])) is False
    assert abriu == []


def test_o_supervisor_LIGA_a_montagem_nos_DOIS_pontos():
    """Sem isto a montagem existiria completa e desligada -- que é exatamente o
    que o usuário viu no teste de 16/09/2026: o APP foi direto para a macro."""
    import inspect

    from blazesbot.bot import supervisor

    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    assert fonte.count("_montar_time_do_app(") == 2, (
        "esperava a montagem no ARRANQUE e no gancho por volta")
    assert "executor.rodar()" in fonte
    arranque = fonte.index("_montar_time_do_app(", fonte.index("def antes_de_cada_volta"))
    assert arranque < fonte.index("executor.rodar()"), \
        "a montagem do arranque tem que vir ANTES da macro"


# ---------------------------------------------------------------------------
# O SEGUIDOR ACEITANDO DENTRO DA MACRO
# ---------------------------------------------------------------------------

def test_o_aceitador_do_seguidor_EXIGE_a_caixa():
    """*"É importante que só clique depois que aparecer a mensagem de aceitar,
    mesmo que isso atrase um pouco."*

    O Ok é clique ESQUERDO -- o mesmo que faz o personagem andar. O aceitador da
    conta de reset clica antes de a caixa existir DE PROPÓSITO (ela é parada num
    canto); no APP isso tira a conta do ponto de farm.
    """
    import inspect

    fonte = inspect.getsource(mod.aceitador_do_seguidor)
    assert "exigir_caixa=True" in fonte


def _fabrica_de_ctx(criados):
    def _fabricar(**kwargs):
        ctx = _ctx_falso(**kwargs)
        criados.append(ctx)
        return ctx
    return _fabricar


def test_o_contexto_do_aceitador_SABE_QUEM_E(monkeypatch):
    """O DEFEITO DE 16/09/2026 -- o seguidor NUNCA aceitava dentro da macro.

    `BotContext` nasce com `char_name = None` (quem preenche é a sessão do
    supervisor, no contexto DELA), e o `InviteAcceptor` reconhece o convite por
    `convite_pendente(meu_nick)`. Com o nick vazio o dicionário nunca bate: o
    caminho do anúncio -- o único que funciona sem imagem -- nem começa.

    MEDIDO: o líder convidou 'WizzOfBlazes5' quatro vezes, esperou 4 s por cada
    e desistiu; o seguidor girava a 2 Hz e não clicou nenhuma. A caixa ficou na
    tela seis horas.

    OS TESTES DAQUI NÃO PEGARAM porque o dublê tinha nome (`char_name="Um"`) e o
    objeto de verdade não -- por isso este exercita a FÁBRICA, não o aceitador.
    """
    sup = _Sup()
    criados = []
    monkeypatch.setattr(mod, "BotContext", _fabrica_de_ctx(criados))

    aceitar, fechar = mod.aceitador_do_seguidor(sup)

    assert aceitar is not None and fechar is not None
    assert criados[0].char_name == "Lider", "o aceitador não sabe quem ele é"


def test_o_nome_CONFIRMADO_no_login_vence_o_do_config(monkeypatch):
    """A memória leu quem realmente está logado; o config pode estar velho."""
    sup = _Sup()
    sup._ctx_atual = SimpleNamespace(char_name="OQueOJogoDiz")
    criados = []
    monkeypatch.setattr(mod, "BotContext", _fabrica_de_ctx(criados))

    mod.aceitador_do_seguidor(sup)

    assert criados[0].char_name == "OQueOJogoDiz"


def test_a_recusa_SEM_PROVA_deixa_rastro_UMA_vez():
    """Recusar calado foi o que escondeu o defeito por um dia inteiro.

    O líder registra "não aceitou em 4s"; deste lado não havia nada. E uma vez
    só: o aceitador roda a cada 0,5 s, e repetir a linha encheria o log.
    """
    from blazesbot.bot.team import InviteAcceptor

    linhas: list[str] = []
    ctx = SimpleNamespace(
        char_name="SemProva",
        hwnd=1,
        coords=SimpleNamespace(confirm_ok=(437, 335)),
        config=SimpleNamespace(farming_accounts=lambda: []),
        templates=SimpleNamespace(load=lambda nome: None),
        memory=SimpleNamespace(modal_open=lambda: False, team_size=lambda: None,
                               tamanho_do_time=lambda: None),
        click=lambda p: None,
        tick=lambda s: None,
        log=SimpleNamespace(info=lambda f, *a: linhas.append(f % a if a else f),
                            warning=lambda *a, **k: None,
                            debug=lambda *a, **k: None),
    )
    aceitador = InviteAcceptor(ctx, cooldown=0.0, exigir_caixa=True)
    mural.anunciar_convite("SemProva", "Lider")

    for _ in range(5):
        assert aceitador.check_and_accept() is False

    avisos = [t for t in linhas if "sem prova de caixa" in t]
    assert len(avisos) == 1, f"esperava um aviso só: {linhas}"
    assert "Lider" in avisos[0]


def test_sem_caixa_e_sem_imagem_o_aceitador_NAO_clica():
    """O portão de verdade, exercitando o `InviteAcceptor`."""
    from blazesbot.bot.team import InviteAcceptor

    cliques = []
    ctx = SimpleNamespace(
        char_name="Um",
        hwnd=1,
        coords=SimpleNamespace(confirm_ok=(437, 335)),
        config=SimpleNamespace(farming_accounts=lambda: []),
        templates=SimpleNamespace(load=lambda nome: None),
        memory=SimpleNamespace(modal_open=lambda: False, team_size=lambda: None,
                               tamanho_do_time=lambda: None),
        click=lambda p: cliques.append(p),
        tick=lambda s: None,
        log=SimpleNamespace(info=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            debug=lambda *a, **k: None),
    )
    aceitador = InviteAcceptor(ctx, cooldown=0.0, exigir_caixa=True)
    mural.anunciar_convite("Um", "Lider")

    assert aceitador.check_and_accept() is False
    assert cliques == [], "clicou sem prova de que a caixa existe"


def test_COM_o_modal_aberto_o_aceitador_clica():
    """A memória é a via que responde com o cliente fora de primeiro plano."""
    from blazesbot.bot.team import InviteAcceptor

    cliques = []
    ctx = SimpleNamespace(
        char_name="Um",
        hwnd=1,
        coords=SimpleNamespace(confirm_ok=(437, 335)),
        config=SimpleNamespace(farming_accounts=lambda: []),
        templates=SimpleNamespace(load=lambda nome: None),
        memory=SimpleNamespace(modal_open=lambda: True, team_size=lambda: None,
                               tamanho_do_time=lambda: 2),
        click=lambda p: cliques.append(p),
        tick=lambda s: None,
        log=SimpleNamespace(info=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            debug=lambda *a, **k: None),
    )
    aceitador = InviteAcceptor(ctx, cooldown=0.0, exigir_caixa=True)
    mural.anunciar_convite("Um", "Lider")

    assert aceitador.check_and_accept() is True
    assert cliques == [(437, 335)]
    assert mural.aceite_pendente("Lider") == "Um", "não avisou quem convidou"


def test_a_conta_de_RESET_continua_clicando_sem_a_caixa():
    """O padrão é o comportamento de hoje -- um farm que roda não muda sozinho."""
    from blazesbot.bot.team import InviteAcceptor

    cliques = []
    ctx = SimpleNamespace(
        char_name="Reseter",
        hwnd=1,
        coords=SimpleNamespace(confirm_ok=(437, 335)),
        config=SimpleNamespace(farming_accounts=lambda: []),
        templates=SimpleNamespace(load=lambda nome: None),
        memory=SimpleNamespace(modal_open=lambda: False, team_size=lambda: None,
                               tamanho_do_time=lambda: None),
        click=lambda p: cliques.append(p),
        tick=lambda s: None,
        log=SimpleNamespace(info=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            debug=lambda *a, **k: None),
    )
    aceitador = InviteAcceptor(ctx, cooldown=0.0)      # sem `exigir_caixa`
    mural.anunciar_convite("Reseter", "Lider")

    assert aceitador.check_and_accept() is True
    assert cliques == [(437, 335)]


def test_o_executor_CHAMA_o_aceite_na_espera_fatiada():
    """Entre voltas seria tarde: o líder desiste antes de a volta terminar."""
    import inspect

    from blazesbot.bot.app import executor

    fonte = inspect.getsource(executor.ExecutorDeMacro._esperar)
    assert "self._aceitar_convite()" in fonte


def test_o_supervisor_INJETA_o_aceite_no_executor():
    import inspect

    from blazesbot.bot import supervisor

    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    assert "_aceitador_do_seguidor(self)" in fonte
    assert "aceitar_convite=_aceitar_convite" in fonte


# ---------------------------------------------------------------------------
# PICK MODE: FREE
# ---------------------------------------------------------------------------

class _CtxMenu:
    """O `ctx` do menu de contexto, com o quadro trocando (ou não) no hover."""

    def __init__(self, submenu_abre=True, hover_aceito=True):
        import numpy as np

        self.cliques: list[tuple[int, int]] = []
        self.direitos: list[tuple[int, int]] = []
        self.teclas: list[str] = []
        self.hovers: list[tuple[int, int]] = []
        self._submenu_abre = submenu_abre
        self._hover_aceito = hover_aceito
        self._np = np
        self._quadro = np.zeros((300, 400, 3), dtype=np.uint8)
        self.hwnd = 1
        self.coords = SimpleNamespace(own_portrait=(44, 48),
                                      menu_leave_team=(82, 97))
        self.input = SimpleNamespace(passar_o_mouse=self._hover)

    def _hover(self, x, y):
        self.hovers.append((x, y))
        if self._hover_aceito and self._submenu_abre:
            # A caixa opaca aparecendo sobre a cena.
            self._quadro = self._np.full((300, 400, 3), 180, dtype=self._np.uint8)
        return self._hover_aceito

    def capturar(self, _hwnd):
        return self._quadro.copy()

    def right_click(self, p, **k):
        self.direitos.append(p)
        # O menu desenhando: a região do retrato deixa de ser o que era.
        self._quadro = self._np.full((300, 400, 3), 90, dtype=self._np.uint8)

    def click(self, p):
        self.cliques.append(p)

    def press(self, tecla, **k):
        self.teclas.append(tecla)

    def tick(self, s):
        pass

    def raise_if_stopped(self):
        """`espera.ate` pergunta isto a cada volta -- o botão Parar responde."""
        pass


def _com_captura(monkeypatch, ctx):
    from blazesbot.core import vision

    monkeypatch.setattr(vision, "capture_window", ctx.capturar)


def test_o_pick_mode_passa_o_mouse_e_clica_no_Free(monkeypatch):
    """*"Tem que passar o mouse em cima do 'Pick Mode:' (pois o clique fecha o
    menu) e selecionar a opção 'Free'."*"""
    sup = _Sup()
    ctx = _CtxMenu(submenu_abre=True)
    _com_captura(monkeypatch, ctx)

    assert mod.pick_mode_free(sup, ctx) is True
    assert ctx.direitos == [(44, 48)], "não abriu o menu do próprio personagem"
    assert ctx.hovers, "não passou o mouse"
    assert ctx.cliques, "não clicou no Free"


def test_o_Free_fica_na_MESMA_altura_do_hover():
    """O submenu abre alinhado com a linha, e Free é o PRIMEIRO item.

    Deduzir a altura do Free seria um segundo palpite -- e errá-lo selecionaria
    'Dice' ou 'Teamlead', que é pior que não fazer nada.
    """
    assert mod.DESLOCAMENTO_DO_FREE[1] == 0


def test_o_pick_mode_usa_a_MESMA_coluna_do_Leave_the_team():
    """As duas são linhas do mesmo menu; só a altura muda."""
    assert mod.DESLOCAMENTO_DO_PICK_MODE[0] == 0


def test_SUBMENU_que_nao_abre_NAO_clica_em_nada(monkeypatch):
    """Sem prova de que o submenu está na tela, nenhum clique sai.

    É o pior lugar da tela para clicar no escuro: errar a linha troca o modo
    para 'Dice' ou 'Teamlead'.
    """
    sup = _Sup()
    ctx = _CtxMenu(submenu_abre=False)
    _com_captura(monkeypatch, ctx)

    assert mod.pick_mode_free(sup, ctx) is False
    assert ctx.cliques == [], "clicou sem o submenu ter aberto"
    assert ctx.teclas.count("ESC") >= 1, "deixou o menu aberto"
    assert any("não abriu" in t for _n, t in sup.linhas), sup.linhas


def test_janela_que_RECUSA_o_movimento_desiste_na_hora(monkeypatch):
    sup = _Sup()
    ctx = _CtxMenu(hover_aceito=False)
    _com_captura(monkeypatch, ctx)

    assert mod.pick_mode_free(sup, ctx) is False
    assert ctx.cliques == []


def test_o_pick_mode_so_roda_quando_ALGUEM_ENTROU(monkeypatch):
    """Ele é propriedade do TIME: some com o time, volta quando o time volta.

    Aplicar a cada conferência seria abrir um menu no meio da tela sem motivo.
    """
    sup = _Sup()
    _de_pe("s1")
    chamou = []
    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _team_falso([], aceita=()))
    monkeypatch.setattr(mod, "pick_mode_free",
                        lambda s, c: chamou.append(1) or True)

    mod.montar_o_time(sup, _Memoria(["Lider"]))     # ninguém entrou
    assert chamou == []

    monkeypatch.setattr(mod, "TeamService", _team_falso([], aceita=("Um",)))
    mod.montar_o_time(sup, _Memoria(["Lider"]))     # 'Um' entrou
    assert chamou == [1]
