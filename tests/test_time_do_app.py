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
from unittest import mock

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
                 nicks=None, sou_o_lider=True, funcao_do_lider="app",
                 lider_ligado=True, em_time=True):
        self.account = SimpleNamespace(login="lider" if sou_o_lider else "s1",
                                       last_char_name="Lider" if sou_o_lider
                                       else "Um")
        self.config = SimpleNamespace(
            accounts=[],
            funcao_ativa_da_conta=lambda conta: funcao_do_lider)
        self._lider_ligado = lider_ligado
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
        self._em_time = em_time

    def _tem_time_do_app(self):
        return self._em_time

    def _membros_do_time(self):
        return list(self._membros)

    def _nick_do_login(self, login):
        return self._nicks.get(login, "")

    def _dono_da_macro(self):
        return SimpleNamespace(login=self._lider, enabled=self._lider_ligado)


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


def test_a_FADA_bate_no_canal_dela_e_conta_como_de_pe(monkeypatch):
    """A Fada nunca passa por `publicar_estado`: o laço dela é outro.

    MEDIDO em 19/09/2026 -- quatro ciclos de *"mfaustoapp069 sem sinal de vida
    agora"* com a Fada rodando, enquanto ela reclamava que o líder não aparecia
    no painel de time dela. As duas se esperando para sempre.
    """
    sup = _Sup()
    _de_pe("s1")
    mural.bater_fada("s2")                  # a Fada, viva, no canal dela
    convidados = []
    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _team_falso(convidados, aceita=()))

    mod.montar_o_time(sup, _Memoria(["Lider"]))

    assert "Dois" in convidados, "a Fada foi pulada como se estivesse offline"


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


def test_o_anuncio_sai_DEPOIS_do_clique_no_Team_up(monkeypatch):
    """Antes ele saía antes, e enviar o convite leva de 4 a 5 s.

    Medido em 19/09/2026: anúncio às 13:11:57.7, o convidado registrando *"sem
    prova de caixa na tela"* 58 ms depois, e o clique em 'Team up' só às
    13:12:02.3. Ele procurava uma caixa que ainda não existia -- e recusava com
    razão, queimando uma das quatro tentativas.
    """
    sup = _Sup()
    _de_pe("s1")
    anunciado_no_clique = []

    class _Team:
        def __init__(self, ctx):
            self.ctx = ctx

        def _enviar_convite(self, nick):
            anunciado_no_clique.append(mural.convite_pendente(nick))
            return True

    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _Team)

    mod.montar_o_time(sup, _Memoria(["Lider"]))

    assert anunciado_no_clique, "não chegou a enviar convite nenhum"
    assert anunciado_no_clique[0] is None, (
        "o anúncio saiu ANTES do clique -- o convidado procura uma caixa que "
        "ainda não existe")
    assert mural.convite_pendente("Um") == "Lider", (
        "depois do clique o anúncio tem que estar de pé")


def test_convida_UM_POR_VEZ_e_para_quando_todos_entram(monkeypatch):
    sup = _Sup()
    _de_pe("s1", "s2")
    convidados = []
    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _team_falso(convidados,
                                                        aceita=("Um", "Dois")))

    assert mod.montar_o_time(sup, _Memoria(["Lider"])) is True
    assert convidados == ["Um", "Dois"], convidados


def test_quem_SOBE_no_meio_da_montagem_ainda_recebe_convite(monkeypatch):
    """A fila era calculada UMA vez, e quem estava 150 ms atrasado ficava fora.

    Medido em 19/09/2026: no arranque o líder conferiu às 13:10:37.295 e o
    seguidor publicou o sinal de vida logo depois -- o time começou a macro com
    2 de 3, e o terceiro só seria convidado 60 s adiante. *"Tem que enviar a
    todos do time, que é entre 1 e 4 convites."*
    """
    sup = _Sup()
    _de_pe("s1")                               # 's2' ainda não subiu
    convidados = []

    class _Team:
        def __init__(self, ctx):
            self.ctx = ctx

        def _enviar_convite(self, nick):
            convidados.append(nick)
            mural.anunciar_aceite("Lider", nick)      # sempre aceitam
            if len(convidados) == 1:
                _de_pe("s2")                   # ele sobe DURANTE o 1º convite
            return True

    monkeypatch.setattr(mod, "BotContext", _ctx_falso)
    monkeypatch.setattr(mod, "TeamService", _Team)

    mod.montar_o_time(sup, _Memoria(["Lider"]))

    assert convidados == ["Um", "Dois"], (
        "quem subiu depois da primeira passada ficou sem convite: %s"
        % convidados)


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


def test_RELIGAR_o_APP_confere_o_time_mesmo_dentro_da_cadencia(monkeypatch):
    """O relógio da cadência é do SUPERVISOR, e ele sobrevive ao desligar.

    Medido no log de 19/09/2026: o usuário desligou o APP do líder, esvaziou o
    time e religou 13 s depois -- nenhuma conferência, a macro começou sozinha.
    Religando 2min35 depois (cadência já vencida), a conferência saiu 1,6 s
    depois do arranque. Era o relógio velho segurando justo o momento em que
    conferir mais importa: quem mexeu no time religa em segundos.
    """
    sup = _Sup()
    chamou = []
    monkeypatch.setattr(mod, "montar_o_time",
                        lambda s, m: chamou.append(1) or True)

    mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=False)   # sessão anterior
    mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=False,
                             no_arranque=True)                     # religou agora

    assert chamou == [1, 1], "o arranque respeitou a cadência da sessão passada"


def test_no_arranque_EM_BATALHA_continua_valendo(monkeypatch):
    """O arranque fura a cadência, não a regra de batalha: abrir a Block list
    com mob batendo é o personagem parado apanhando."""
    sup = _Sup()
    chamou = []
    monkeypatch.setattr(mod, "montar_o_time", lambda s, m: chamou.append(1))
    assert mod.montar_se_for_a_hora(sup, _Memoria([]), em_batalha=True,
                                    no_arranque=True) is False
    assert chamou == []


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


# ---------------------------------------------------------------------------
# A ÂNCORA DO TIME — o ponto inicial do líder vale para todos
# ---------------------------------------------------------------------------

def test_o_LIDER_publica_a_ancora_e_o_seguidor_usa_a_dele():
    """*"O líder captura a coordenada inicial e compartilha; todos sobrescrevem
    o próprio ponto"* (usuário, 22/09/2026)."""
    lider = _Sup(sou_o_lider=True)
    seguidor = _Sup(sou_o_lider=False)

    assert mod.publicar_a_ancora(lider, (1869, 1668)) is True
    assert mod.ancora_do_lider(seguidor) == (1869, 1668)


def test_SOLO_nao_publica_e_nao_espera_ninguem():
    """A trava de escopo. Conta sozinha não tem líder para procurar, e procurar
    gastaria o teto inteiro parada antes de cada farm."""
    solo = _Sup(sou_o_lider=True, em_time=False)
    assert mod.publicar_a_ancora(solo, (10, 20)) is False
    assert mural.ancora_do_time("lider") is None

    seguidor_sem_time = _Sup(sou_o_lider=False, em_time=False)
    mural.publicar_ancora("lider", (10, 20))
    assert mod.ancora_do_lider(seguidor_sem_time) is None, (
        "conta fora de time foi atrás da âncora de alguém")


def test_o_SEGUIDOR_nao_dita_ancora():
    """Só o dono da macro publica. Dois publicadores seriam duas âncoras
    disputando a mesma chave do mural."""
    seguidor = _Sup(sou_o_lider=False)
    assert mod.publicar_a_ancora(seguidor, (5, 5)) is False
    assert mural.ancora_do_time("lider") is None


def test_a_espera_SEGURA_o_seguidor_ate_a_ancora_chegar(monkeypatch):
    """A trava de concorrência: o líder publica ~0,9 s depois (medido em
    19/09/2026), e sem esperar o seguidor ancoraria no ponto dele."""
    seguidor = _Sup(sou_o_lider=False)
    tentativas = {"n": 0}
    de_verdade = mural.ancora_do_time

    def demorando(login):
        tentativas["n"] += 1
        return de_verdade(login) if tentativas["n"] >= 3 else None

    monkeypatch.setattr(mural, "ancora_do_time", demorando)
    mural.publicar_ancora("lider", (77, 88))

    assert mod.ancora_do_lider(seguidor) == (77, 88)
    assert tentativas["n"] >= 3, "voltou antes de perguntar de novo"


def test_o_TETO_solta_o_seguidor_com_o_ponto_dele():
    """Começar espalhado é ruim; não começar é pior."""
    seguidor = _Sup(sou_o_lider=False)
    assert mod.ancora_do_lider(seguidor, teto=0.01) is None
    assert any("não publicou ponto inicial" in t for _n, t in seguidor.linhas)


def test_ancora_em_ZERO_e_recusada():
    """(0,0) é o que a leitura devolve antes de o personagem entrar no mundo.
    Ancorar o time ali manda todo mundo andar para o canto do mapa."""
    lider = _Sup(sou_o_lider=True)
    mod.publicar_a_ancora(lider, (0, 0))
    assert mural.ancora_do_time("lider") is None


def test_sem_base_nao_publica_nada():
    lider = _Sup(sou_o_lider=True)
    assert mod.publicar_a_ancora(lider, None) is False


def test_o_supervisor_PUBLICA_e_CONSOME_antes_de_montar_o_executor():
    """Depois do executor montado seria tarde: a base entra nele por parâmetro
    e só é lida uma vez."""
    import inspect

    from blazesbot.bot import supervisor

    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    assert "_publicar_a_ancora(self, base_pos)" in fonte
    assert "_ancora_do_lider(self)" in fonte
    assert fonte.index("_ancora_do_lider(self)") < fonte.index("base_pos=base_pos"), (
        "a âncora chegou depois de a base já ter ido para o executor")
    assert "esquecer_ancora" in fonte, (
        "a âncora sobreviveria ao líder, e o próximo religar ancoraria numa "
        "sessão que acabou")


def test_a_FADA_tambem_nasce_ancorada_no_lider():
    """Ela é a que mais sofre: fica parada curando, e a cura tem alcance."""
    import inspect

    from blazesbot.bot import fada_montagem

    fonte = inspect.getsource(fada_montagem.rodar_a_fada)
    assert "ancora_do_lider(sup)" in fonte
    assert "ponto_inicial[0] = ancora" in fonte
    assert fonte.index("ponto_inicial[0] = ancora") < fonte.index("fada.rodar()"), (
        "semear depois do laço não adianta: `voltar_ao_ponto` já teria guardado "
        "a posição dela na primeira volta")


# ---------------------------------------------------------------------------
# NINGUÉM SE MEXE ANTES DO TIME
# ---------------------------------------------------------------------------

def test_o_SEGUIDOR_espera_entrar_no_time_antes_de_comecar():
    """*"A primeira coisa, antes de qualquer um se mexer, é montar o team."*

    Cada conta tem o seu supervisor e as threads arrancam juntas -- no log de
    19/09/2026 a macro do seguidor começou 0,9 s ANTES de o líder sequer
    conferir o time.
    """
    sup = _Sup(sou_o_lider=False)
    entrou = {"n": 0}

    class _MemoriaQueEntra:
        def time_do_jogo(self):
            entrou["n"] += 1
            return ["Um"] if entrou["n"] < 3 else ["Um", "Lider"]

        def tamanho_do_time(self):
            return 2

    assert mod.esperar_o_lider_montar(sup, _MemoriaQueEntra()) is True
    assert entrou["n"] >= 3, "voltou antes de conferir o time de novo"


def test_o_LIDER_nao_espera_por_si_mesmo():
    sup = _Sup(sou_o_lider=True)
    assert mod.esperar_o_lider_montar(sup, _Memoria(["Lider"])) is False


def test_nao_espera_um_lider_DESLIGADO():
    """Ficar parado esperando quem não vai rodar é o caso de quem liga uma
    conta sozinha para testar."""
    sup = _Sup(sou_o_lider=False, lider_ligado=False)
    assert mod.esperar_o_lider_montar(sup, _Memoria(["Um"])) is False


def test_nao_espera_um_lider_que_nao_esta_no_APP():
    sup = _Sup(sou_o_lider=False, funcao_do_lider="bc")
    assert mod.esperar_o_lider_montar(sup, _Memoria(["Um"])) is False


def test_APANHANDO_nao_espera():
    """Parado sob ataque é a única coisa pior que começar antes do time."""
    sup = _Sup(sou_o_lider=False)
    assert mod.esperar_o_lider_montar(sup, _Memoria(["Um"]),
                                      em_batalha=True) is False


def test_quem_espera_PUBLICA_sinal_de_vida(monkeypatch):
    """Sem isto os dois se esperam: o líder só convida quem está de pé, e quem
    está parado aqui ainda não rodou uma volta."""
    monkeypatch.setattr(mod, "TENTATIVAS_POR_MEMBRO", 1)
    sup = _Sup(sou_o_lider=False)
    assert mural.estado_da_conta("s1") is None

    mod.esperar_o_lider_montar(sup, _Memoria(["Um"]))   # nunca entra; estoura

    assert mural.estado_da_conta("s1") is not None, (
        "o seguidor esperou calado -- o líder nunca saberia que ele existe")


def test_o_TETO_solta_a_macro_e_avisa(monkeypatch):
    """Estourado, farmar sozinho é melhor que ficar parado -- e o convite
    continua sendo aceito dentro da macro."""
    monkeypatch.setattr(mod, "TENTATIVAS_POR_MEMBRO", 1)
    sup = _Sup(sou_o_lider=False)

    assert mod.esperar_o_lider_montar(sup, _Memoria(["Um"])) is False
    assert any("não me pôs no time" in t for _n, t in sup.linhas), sup.linhas


def test_enquanto_espera_ele_ACEITA_o_convite(monkeypatch):
    """A macro ainda não começou, então o gancho de dentro dela não existe:
    quem clica no Ok neste intervalo é esta chamada."""
    monkeypatch.setattr(mod, "TENTATIVAS_POR_MEMBRO", 1)
    sup = _Sup(sou_o_lider=False)
    aceites = []

    mod.esperar_o_lider_montar(sup, _Memoria(["Um"]),
                               lambda: aceites.append(1))

    assert aceites, "esperou o convite sem nunca clicar no Ok"


def test_o_supervisor_ESPERA_o_time_antes_da_macro():
    import inspect

    from blazesbot.bot import supervisor

    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    assert "_esperar_o_lider_montar(" in fonte, (
        "o seguidor voltou a largar antes do time")
    assert fonte.index("_esperar_o_lider_montar(") < fonte.rindex(
        "executor.rodar()"), "a espera tem que vir ANTES da macro"


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
    # A DO ARRANQUE é a ÚLTIMA das duas no arquivo -- a outra mora dentro de
    # `antes_de_cada_volta`, que é definida antes e chamada a cada volta.
    ultima = fonte.rindex("_montar_time_do_app(")
    assert "no_arranque=True" in fonte[ultima:ultima + 200], (
        "o arranque voltou a respeitar a cadência da sessão anterior -- "
        "religar dentro de 60 s não confere o time")


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
    assert "self._pulso_do_time()" in fonte


def test_o_executor_chama_o_aceite_TAMBEM_na_espera_CEGA():
    """A volta cega é a REGRA no time, não a exceção.

    `sincronia.volta_cega` é verdadeira em todo modo que não seja `mesmo_alvo`
    -- e o padrão é `copiar`. Com o gancho só no `_esperar`, o seguidor passava
    a volta inteira surdo: medido em 19/09/2026, quatro convites em 23 s e o
    aceite saindo 16 ms depois de a macro ser DESLIGADA, pelo aceitador do
    supervisor.
    """
    import inspect

    from blazesbot.bot.app import executor

    fonte = inspect.getsource(executor.ExecutorDeMacro._dormir)
    assert "self._pulso_do_time()" in fonte, (
        "a espera cega voltou a ser surda a convite de time")
    assert "_esperar_cego" in inspect.getsource(
        executor.ExecutorDeMacro._esperar_cego), "a espera cega mudou de nome"
    assert "self._dormir(" in inspect.getsource(
        executor.ExecutorDeMacro._esperar_cego), (
        "a espera cega parou de passar pelo `_dormir` -- o aceite ficou de fora")


def test_sem_convite_anunciado_o_aceitador_do_APP_NAO_captura_a_tela():
    """O que torna possível perguntar a cada fatia da espera.

    A captura custa ~15 ms e vinha antes de qualquer pergunta. Chamada dentro
    da linha, ela entraria só nesta conta e desalinharia o time -- que é
    justamente o que a volta cega existe para evitar.
    """
    from blazesbot.bot import team as mod_team
    from blazesbot.bot.team import InviteAcceptor

    capturas = []
    ctx = SimpleNamespace(
        char_name="Um",
        hwnd=1,
        coords=SimpleNamespace(confirm_ok=(437, 335)),
        config=SimpleNamespace(farming_accounts=lambda: []),
        templates=SimpleNamespace(load=lambda nome: None),
        memory=SimpleNamespace(modal_open=lambda: True, team_size=lambda: None,
                               tamanho_do_time=lambda: 2),
        click=lambda p: None,
        tick=lambda s: None,
        log=SimpleNamespace(info=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            debug=lambda *a, **k: None),
    )
    aceitador = InviteAcceptor(ctx, cooldown=0.0, exigir_caixa=True)

    with mock.patch.object(mod_team, "capture_window",
                           lambda h: capturas.append(h)):
        aceitador.check_and_accept()                   # sem convite nenhum
        assert capturas == [], "capturou a tela sem ter convite para aceitar"

        mural.anunciar_convite("Um", "Lider")
        aceitador.check_and_accept()
        assert capturas == [1], "com convite anunciado, a imagem volta a valer"


def test_o_supervisor_INJETA_o_aceite_no_executor():
    import inspect

    from blazesbot.bot import supervisor

    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    assert "_aceitador_do_seguidor(self)" in fonte
    assert "pulso_do_time=pulso_do_time" in fonte


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
