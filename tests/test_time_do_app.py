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
