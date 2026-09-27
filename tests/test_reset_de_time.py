"""A conta de reset: lista fechada, batida, e a trava na porta da cave.

=========================================================================
O QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

1. ENTRAR SEM RESETER. Sem trocar de time o boss NÃO renasce: a instância
   continua com ele morto e a run inteira é perdida -- depois de já ter gasto o
   teleporte, a travessia e a disputa da entrada. O bot chamava `montar_time()`
   e IGNORAVA o retorno, então uma conta de reset caída virava run perdida atrás
   de run perdida, em silêncio.

2. UM RESETER QUE O BOT NÃO CONSEGUE OBSERVAR. O campo era texto livre: o nick
   digitado podia apontar para uma conta de outra máquina, para um personagem
   que não existe, ou para uma conta que farma. Em nenhum desses casos o bot
   tem como saber que o reseter caiu -- e sem saber, não há trava possível.

3. A BATIDA QUE DESCREVE EM VEZ DE PROVAR. Responder "o reseter está no ar?" com
   uma checagem (processo vivo, hwnd válido, memória legível) tem falso positivo
   MEDIDO: uma conta em modo APP passa em todas essas provas e mesmo assim nunca
   aceita convite nenhum, porque `_operate` testa `app.enabled` primeiro e dá
   `continue` antes de chegar no aceitador.

4. ESPERAR PARA SEMPRE POR QUEM NÃO VOLTA. "Caiu" e "não existe mais" são
   estados diferentes: o primeiro se resolve sozinho pelo relogin, o segundo é
   uma conta parada a noite inteira.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

from blazesbot.bot import mural as mod_mural
from blazesbot.bot import team as mod_team
from blazesbot.bot.bc import routine as mod_routine
from blazesbot.config import Account, BotConfig

RAIZ = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _conta(login: str, nick: str, **kw) -> Account:
    c = Account(login=login, last_char_name=nick, password_enc="x")
    c.enabled = kw.pop("enabled", True)
    c.bc_farm = kw.pop("bc_farm", False)
    c.settings.accept_team_invites = kw.pop("aceita", False)
    c.settings.app.enabled = kw.pop("app", False)
    c.settings.reset_nick = kw.pop("reset_nick", "")
    # A tecla da lista de amigos é pré-requisito do convite; sem ela todo
    # `problema_do_reset` responderia isso e os outros ramos nunca seriam
    # exercitados.
    c.settings.keys.friend_list = kw.pop("friend_list", "F")
    assert not kw, kw
    return c


def _cfg(*contas: Account) -> BotConfig:
    cfg = BotConfig()
    cfg.accounts = list(contas)
    return cfg


# ---------------------------------------------------------------------------
# A BATIDA
# ---------------------------------------------------------------------------

def test_nunca_ter_batido_conta_como_offline():
    """A conta de reset bate duas vezes por segundo desde que sobe.

    Então "nenhuma batida" não é dúvida: é que ela ainda não chegou lá --
    está logando, relogando, em modo APP, ou não subiu. Tratar isso como
    "provavelmente está ok" devolveria exatamente a run perdida que a trava
    existe para evitar.
    """
    assert mod_mural.silencio_do_reseter("NinguemBateuAinda") is None
    assert mod_mural.reseter_online("NinguemBateuAinda") is False


def test_bater_poe_o_nick_online_e_o_silencio_o_derruba(monkeypatch):
    agora = [1000.0]
    monkeypatch.setattr(mod_mural.time, "time", lambda: agora[0])

    mod_mural.bater("Reseter")
    assert mod_mural.reseter_online("Reseter") is True

    # Dentro da janela: continua no ar.
    agora[0] += mod_mural.SILENCIO_MAXIMO - 0.5
    assert mod_mural.reseter_online("Reseter") is True

    # Passou do limite: caiu.
    agora[0] += 1.0
    assert mod_mural.reseter_online("Reseter") is False
    assert mod_mural.silencio_do_reseter("Reseter") > mod_mural.SILENCIO_MAXIMO


def test_a_batida_ignora_caixa_e_espaco():
    """O nick vem da memória de um lado e da configuração do outro."""
    mod_mural.bater("  WizzOfBlazes5  ")
    assert mod_mural.reseter_online("wizzofblazes5") is True


def test_nick_vazio_nunca_fica_online():
    """`reset_nick` vazio significa "não uso reset de time".

    Se string vazia pudesse ficar online, uma conta sem nick lido ainda bateria
    e todo mundo que não usa reset apareceria como reseter no ar.
    """
    mod_mural.bater("")
    assert mod_mural.reseter_online("") is False


def test_a_batida_e_a_PRIMEIRA_linha_do_aceitador():
    """A posição É a regra: ela prova a capacidade em vez de descrevê-la.

    `check_and_accept` só é alcançado por uma conta logada, fora do modo APP,
    fora do farm e dentro do laço de operação. Batendo ali, "posso aceitar um
    convite agora" deixa de ser uma afirmação sobre a conta e passa a ser uma
    consequência de o código ter chegado no ponto.

    E ANTES DO COOLDOWN: o cooldown é sobre CLICAR (não vale capturar a tela
    cinco vezes por segundo), não sobre estar disponível. Batendo depois dele, a
    disponibilidade herdaria a cadência do clique sem motivo nenhum.
    """
    fonte = inspect.getsource(mod_team.InviteAcceptor.check_and_accept)
    corpo = ast.parse(textwrap.dedent(fonte)).body[0].body

    # Pula a docstring, se houver.
    primeiro = corpo[0]
    if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
        primeiro = corpo[1]

    assert isinstance(primeiro, ast.Expr), ast.dump(primeiro)
    chamada = primeiro.value
    assert isinstance(chamada, ast.Call), ast.dump(primeiro)
    assert getattr(chamada.func, "id", None) == "bater", (
        "a batida deixou de ser a primeira linha de check_and_accept; "
        "com isso ela volta a descrever a conta em vez de provar a capacidade")


# ---------------------------------------------------------------------------
# O VEREDITO POR CONTA
# ---------------------------------------------------------------------------

def test_campo_vazio_nao_e_problema():
    a = _conta("a", "Farmer", reset_nick="")
    assert _cfg(a).problema_do_reset(a) is None


def test_reseter_valido_nao_e_problema():
    a = _conta("a", "Farmer", bc_farm=True, reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=True)
    assert _cfg(a, r).problema_do_reset(a) is None


def test_nick_que_nao_e_conta_deste_bot_e_problema():
    """O arranjo de duas máquinas deixou de ser suportado, e de propósito.

    Um reseter fora deste processo é invisível daqui: não há batida, não há
    trava, e o bot voltaria a entrar sem reset sem ter como saber.
    """
    a = _conta("a", "Farmer", reset_nick="AlguemDeOutroPC")
    problema = _cfg(a).problema_do_reset(a)
    assert problema and "não é nenhuma conta deste bot" in problema


def test_reseter_sem_a_flag_e_problema():
    a = _conta("a", "Farmer", reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=False)
    problema = _cfg(a, r).problema_do_reset(a)
    assert problema and "aceitar convites" in problema


def test_reseter_desativado_e_problema():
    a = _conta("a", "Farmer", reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=True, enabled=False)
    problema = _cfg(a, r).problema_do_reset(a)
    assert problema and "desativada" in problema


def test_reseter_que_farma_e_problema():
    """Reseter fica parado esperando o convite; farmando, ele não está lá.

    Pior: farmando, o supervisor dele entra em `routine.run()` e não volta ao
    topo do laço por minutos -- a batida envelhece e ele PARECE caído estando
    online. São dois defeitos pela mesma porta.
    """
    a = _conta("a", "Farmer", reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=True, bc_farm=True)
    problema = _cfg(a, r).problema_do_reset(a)
    assert problema and "farm de cave" in problema


def test_reseter_em_modo_APP_e_problema():
    """Logado, saudável e inútil como reseter: `_operate` nunca chega no aceitador."""
    a = _conta("a", "Farmer", reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=True, app=True)
    problema = _cfg(a, r).problema_do_reset(a)
    assert problema and "modo APP" in problema


def test_conta_nao_reseta_a_si_mesma():
    a = _conta("a", "Farmer", aceita=True, reset_nick="Farmer")
    problema = _cfg(a).problema_do_reset(a)
    assert problema and "a si mesma" in problema


def test_sem_tecla_da_lista_de_amigos_e_problema_DESTA_CONTA():
    """A regra saiu do `validate()` global: ela reprovava a execução inteira.

    Uma conta mal configurada não pode derrubar as outras quatro. Agora ela veta
    só o BC dela, e o `validate()` não pode voltar a cobrar isso.
    """
    a = _conta("a", "Farmer", reset_nick="Reseter", friend_list="")
    r = _conta("r", "Reseter", aceita=True)
    cfg = _cfg(a, r)
    problema = cfg.problema_do_reset(a)
    assert problema and "lista de amigos" in problema
    assert not any("lista de amigos" in p for p in a.settings.validate())


# ---------------------------------------------------------------------------
# QUEM DEPENDE DE QUEM
# ---------------------------------------------------------------------------

def test_accounts_reset_by_encontra_o_dependente():
    a = _conta("a", "Farmer", bc_farm=True, reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=True)
    assert _cfg(a, r).accounts_reset_by(r) == [a]


def test_dependente_DESATIVADO_nao_bloqueia_nada():
    """Conta desativada não roda, então ela não fica órfã de nada hoje.

    Barrar a exclusão por causa dela criaria trabalho para o usuário por um
    problema que não existe -- e se ela for reativada depois,
    `problema_do_reset` a pega com a mensagem certa.
    """
    a = _conta("a", "Farmer", enabled=False, reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=True)
    assert _cfg(a, r).accounts_reset_by(r) == []


def test_reset_accounts_lista_so_marcadas_e_ativas():
    marcada = _conta("m", "Marcada", aceita=True)
    desmarcada = _conta("d", "Desmarcada", aceita=False)
    inativa = _conta("i", "Inativa", aceita=True, enabled=False)
    lista = _cfg(marcada, desmarcada, inativa).reset_accounts()
    assert lista == [marcada]


# ---------------------------------------------------------------------------
# A MIGRAÇÃO DO CAMPO DE TEXTO LIVRE
# ---------------------------------------------------------------------------

def _ida_e_volta(cfg: BotConfig) -> BotConfig:
    return BotConfig.from_dict(cfg.to_dict())


def test_migracao_liga_a_flag_na_conta_limpa_que_o_nick_ja_apontava():
    """Ligar a flag não inventa intenção: o nick já era a mesma declaração.

    Sem isto, todo arquivo em que o nick foi digitado à mão com a flag
    desmarcada viraria um reset órfão na primeira abertura, e o usuário teria
    que refazer à mão o que já tinha feito.
    """
    a = _conta("a", "Farmer", bc_farm=True, reset_nick="Reseter")
    r = _conta("r", "Reseter", aceita=False)
    recarregado = _ida_e_volta(_cfg(a, r))
    assert recarregado.accounts[1].settings.accept_team_invites is True


def test_migracao_NAO_mexe_em_conta_que_farma():
    """Aí ligar a flag seria eu decidindo que ela deve parar de farmar.

    Essa decisão não é minha: o caso cai em `problema_do_reset`, que veta o BC
    da conta dependente com a mensagem exata e deixa a escolha com quem
    configura.
    """
    a = _conta("a", "Farmer", reset_nick="Ocupado")
    r = _conta("r", "Ocupado", aceita=False, bc_farm=True)
    recarregado = _ida_e_volta(_cfg(a, r))
    assert recarregado.accounts[1].settings.accept_team_invites is False
    # E o caso NÃO passa em silêncio: a conta dependente fica vetada, com o
    # nome do reseter na mensagem, para o usuário decidir o que fazer.
    veto = recarregado.problema_do_reset(recarregado.accounts[0])
    assert veto and "Ocupado" in veto


def test_migracao_NAO_mexe_em_conta_em_modo_APP():
    a = _conta("a", "Farmer", reset_nick="Macro")
    r = _conta("r", "Macro", aceita=False, app=True)
    recarregado = _ida_e_volta(_cfg(a, r))
    assert recarregado.accounts[1].settings.accept_team_invites is False


def test_migracao_nao_inventa_quando_o_nick_nao_bate_com_ninguem():
    a = _conta("a", "Farmer", reset_nick="Fantasma")
    r = _conta("r", "Outro", aceita=False)
    recarregado = _ida_e_volta(_cfg(a, r))
    assert recarregado.accounts[1].settings.accept_team_invites is False


# ---------------------------------------------------------------------------
# O PORTÃO NA ROTINA
# ---------------------------------------------------------------------------

def test_o_portao_vem_ANTES_do_convite_NAS_DUAS_CAVES():
    """Ordem invertida = convite enviado para quem não está lá.

    O portão existe para não gastar a entrada da cave sem reset; depois do
    `montar_time()` ele já teria falhado.

    AS DUAS CAVES desde 08/09/2026: a trava subiu para
    `bot/espera_do_reseter.py` e a HH chama no `_garantir_o_time`, que é o
    ponto imediatamente anterior ao convite dela.
    """
    from blazesbot.bot.hh.routine import HHRoutine

    for metodo in (mod_routine.BossRushRoutine._do_entrar,
                   HHRoutine._garantir_o_time):
        fonte = inspect.getsource(metodo)
        i_portao = fonte.index("esperar_o_reseter(")
        i_convite = fonte.index("montar_time()")
        assert i_portao < i_convite, (
            f"em {metodo.__qualname__} o portão foi parar depois do convite")


def test_A_TRAVA_E_A_MESMA_NAS_DUAS_CAVES():
    """Uma cópia por cave divergiria, e a que ficasse para trás perderia runs.

    A distinção entre "o reseter caiu" (espera, ele volta) e "o reseter não
    existe mais" (desliga o farm e avisa) é caríssima de acertar duas vezes --
    é a razão de a trava ter subido para `bot/` em vez de ser clonada.
    """
    import ast
    import textwrap

    from blazesbot.bot import espera_do_reseter
    from blazesbot.bot.hh.routine import HHRoutine

    for metodo in (mod_routine.BossRushRoutine._do_entrar,
                   HHRoutine._garantir_o_time):
        arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
        chamadas = {ast.unparse(n.func) for n in ast.walk(arvore)
                    if isinstance(n, ast.Call)}
        assert "esperar_o_reseter" in chamadas, metodo.__qualname__

    # E NENHUMA das duas tem laço de espera próprio.
    for modulo, nome in ((mod_routine, "bc"), (HHRoutine, "hh")):
        fonte = inspect.getsource(modulo)
        assert "reseter_online" not in fonte, (
            f"{nome} voltou a ter a própria régua de reseter online")

    assert callable(espera_do_reseter.esperar_o_reseter)


def test_a_espera_usa_ctx_tick_e_nunca_time_sleep():
    """É o `tick` que mantém o watchdog DESTA conta vivo enquanto ela espera.

    Uma conta de cave também cai, e parada por horas num `time.sleep` ela
    ficaria cega para a própria queda. E como cada conta roda na thread dela, a
    espera nunca toca a thread da interface. O `tick` também dá as três saídas
    de graça: Parar, desmarcar o farm da cave (`FarmDesligado`) e ligar o APP.
    """
    from blazesbot.bot.espera_do_reseter import esperar_o_reseter
    fonte = inspect.getsource(esperar_o_reseter)
    arvore = ast.parse(textwrap.dedent(fonte))

    # PELO AST, não por texto: a própria docstring do método explica que ele NÃO
    # usa `time.sleep`, então uma busca por substring reprovaria a explicação.
    chamadas = {
        ast.unparse(n.func) for n in ast.walk(arvore) if isinstance(n, ast.Call)
    }
    assert "ctx.tick" in chamadas, chamadas
    assert not {c for c in chamadas if c.endswith("sleep")}, (
        "a espera do reseter voltou a dormir cega; o watchdog desta conta "
        "para de rodar durante a trava")


def test_a_espera_reavalia_a_configuracao_a_cada_volta():
    """"Caiu" e "não existe mais" são estados diferentes.

    A configuração pode mudar com o bot rodando -- o reseter pode ser
    desmarcado, desativado ou posto para farmar DEPOIS que a trava começou. Sem
    reavaliar, a conta esperaria para sempre por alguém que o próprio bot já
    aposentou.
    """
    from blazesbot.bot.espera_do_reseter import esperar_o_reseter
    fonte = inspect.getsource(esperar_o_reseter)
    arvore = ast.parse(textwrap.dedent(fonte)).body[0]
    lacos = [n for n in ast.walk(arvore) if isinstance(n, ast.While)]
    assert lacos, "a espera deixou de ser um laço"
    dentro = ast.dump(lacos[0])
    assert "problema_do_reset" in dentro, (
        "a conferência de configuração saiu de dentro do laço")
    assert "desligar_o_farm_desta_cave" in dentro, (
        "o desfecho de 'não existe mais' saiu de dentro do laço")


def test_conta_sem_reset_nick_nao_espera_nada(monkeypatch):
    """Quem não usa reset de time não pode pagar nem um `tick` por isto."""
    chamadas = []

    from blazesbot.bot.espera_do_reseter import esperar_o_reseter

    class _Ctx:
        def __init__(self):
            self.settings = type("S", (), {"reset_nick": "  "})()

        def tick(self, s):
            chamadas.append(s)

        def raise_if_stopped(self):
            chamadas.append("check")

    esperar_o_reseter(_Ctx(), onde="em teste")
    assert chamadas == []


# ---------------------------------------------------------------------------
# AS DUAS INTERFACES
# ---------------------------------------------------------------------------

def test_a_WEB_oferece_LISTA_e_nao_texto_livre():
    html = (RAIZ / "web/index.html").read_text(encoding="utf-8")
    assert '<select id="ed-reset-nick"' in html, (
        "o seletor de reseter voltou a ser texto livre na interface web")
    assert '<input id="ed-reset-nick"' not in html


def test_a_interface_impede_tirar_um_reseter_do_ar():
    """Sem o reseter, quem depende dele não reseta a cave, o boss não renasce e a
    run é perdida -- e o sintoma aparece horas depois sem apontar para cá.
    """
    web = (RAIZ / "blazesbot/web_app.py").read_text(encoding="utf-8")
    assert "bloqueio_de_reseter" in web
    assert "accounts_reset_by" in web


def test_o_aceitador_para_de_clicar_pela_leitura_QUE_RESPONDE():
    """`team_size()` nunca respondeu neste cliente -- ver `core/memory.py`.

    Com ela, a parada caía SEMPRE no teto de cliques, mesmo com o convite já
    aceito no primeiro. No modo APP cada clique esquerdo perdido é o personagem
    andando, então a troca para `tamanho_do_time()` (o ponteiro rebaseado,
    provado ao vivo em seis clientes) vem ANTES do time do APP.
    """
    import inspect

    from blazesbot.bot.team import InviteAcceptor

    fonte = inspect.getsource(InviteAcceptor.check_and_accept)
    assert "memory.tamanho_do_time()" in fonte
    assert "memory.team_size()" not in fonte


# ===========================================================================
# O CONVITE QUE FICAVA ABERTO SEM NINGUÉM ACEITAR -- 25/09/2026
# ===========================================================================
#
# Relato do usuário: *"o aceitar do personagem reset nem sempre funciona,
# principalmente depois que as contas caem, na primeira vez que envia o team
# para ele, fica aberto o convite na janela do personagem reset, mas fica sem
# aceitar... sempre que o personagem que estiver fazendo cave, seja BC ou HH,
# tem que aceitar 100% das vezes"*.
#
# MEDIDO em 23/09/2026 às 23:51, um dos 2 convites (de 361) sem prova de time:
#
#     23:51:07.204 [creubo]    Convidando 'Igni001' (tentativa 1)
#     23:51:07.745 [ignition0] Tentando aceitar -- clique 1
#     23:51:08.323 [creubo]    Block list: 'Igni001' difere do registrado
#                              '(nenhum)'; forçando re-registro
#     23:51:11.937 [ignition0] Tentando aceitar -- clique 5, o último
#     23:51:11.423 [creubo]    Abrindo o menu de contexto de 'Igni001'
#
# O anúncio sai ANTES do clique em "Team up". Depois de uma queda a Block list
# está vazia, reconstruí-la leva ~4 s, e a caixa só aparece DEPOIS de os cinco
# cliques terem sido gastos no vazio.


class _MemFalsa:
    def __init__(self, tamanho):
        self._tamanho = tamanho
        self.leituras = 0

    def tamanho_do_time(self):
        self.leituras += 1
        return self._tamanho() if callable(self._tamanho) else self._tamanho

    def team_size(self):
        return None

    def modal_open(self):
        return True


def _aceitador(tamanho, exigir_caixa=False):
    from types import SimpleNamespace

    from blazesbot.bot.team import InviteAcceptor

    cliques = []
    ctx = SimpleNamespace(
        char_name="Reseter", hwnd=1,
        coords=SimpleNamespace(confirm_ok=(437, 335)),
        config=SimpleNamespace(farming_accounts=lambda: []),
        templates=SimpleNamespace(load=lambda nome: None),
        memory=_MemFalsa(tamanho),
        click=lambda p: cliques.append(p),
        tick=lambda s: None,
        log=SimpleNamespace(info=lambda *a, **k: None,
                            warning=lambda *a, **k: None,
                            debug=lambda *a, **k: None),
    )
    a = InviteAcceptor(ctx, cooldown=0.0, exigir_caixa=exigir_caixa)
    a.cliques = cliques
    return a


def test_a_conta_de_reset_NAO_desiste_no_quinto_clique():
    """Era isto que deixava a caixa aberta: a caixa aparecia no sexto."""
    from blazesbot.bot import mural
    from blazesbot.bot.team import MAX_CLIQUES_DE_ACEITE

    mural.consumir_convite("Reseter")
    a = _aceitador(tamanho=1)                      # sem time ainda
    mural.anunciar_convite("Reseter", "Lider")

    for _ in range(MAX_CLIQUES_DE_ACEITE + 4):
        a.check_and_accept()

    assert len(a.cliques) == MAX_CLIQUES_DE_ACEITE + 4, (
        "o aceitador parou de clicar antes de o time formar")
    assert mural.convite_pendente("Reseter") == "Lider", (
        "o anúncio foi consumido sem o time ter formado")
    mural.consumir_convite("Reseter")


def test_e_para_no_INSTANTE_em_que_o_time_forma():
    """Sem teto não pode virar clique eterno: quem encerra é a memória."""
    from blazesbot.bot import mural

    mural.consumir_convite("Reseter")
    estado = {"n": 1}
    a = _aceitador(tamanho=lambda: estado["n"])
    mural.anunciar_convite("Reseter", "Lider")

    a.check_and_accept()
    a.check_and_accept()
    estado["n"] = 2                                 # a caixa foi aceita
    a.check_and_accept()
    antes = len(a.cliques)
    a.check_and_accept()

    assert mural.convite_pendente("Reseter") is None, (
        "o anúncio não foi consumido com o time formado")
    assert len(a.cliques) == antes, "continuou clicando com o time formado"


def test_MEMORIA_MUDA_mantem_o_teto_de_cliques():
    """Sem como confirmar, o teto volta a ser o que encerra -- é o
    comportamento antigo, e ele continua valendo onde ainda é a única regra."""
    from blazesbot.bot import mural
    from blazesbot.bot.team import MAX_CLIQUES_DE_ACEITE

    mural.consumir_convite("Reseter")
    a = _aceitador(tamanho=None)
    mural.anunciar_convite("Reseter", "Lider")

    for _ in range(MAX_CLIQUES_DE_ACEITE + 3):
        a.check_and_accept()

    assert len(a.cliques) == MAX_CLIQUES_DE_ACEITE
    assert mural.convite_pendente("Reseter") is None


def test_o_modo_APP_mantem_o_teto():
    """Lá o Ok é clique ESQUERDO -- cada um perdido move o personagem."""
    from blazesbot.bot import mural
    from blazesbot.bot.team import MAX_CLIQUES_DE_ACEITE

    mural.consumir_convite("Reseter")
    a = _aceitador(tamanho=1, exigir_caixa=True)
    mural.anunciar_convite("Reseter", "Lider")

    for _ in range(MAX_CLIQUES_DE_ACEITE + 3):
        a.check_and_accept()

    assert len(a.cliques) == MAX_CLIQUES_DE_ACEITE
    mural.consumir_convite("Reseter")


# ===========================================================================
# QUEM CONVIDA CONFIRMA PELA MEMÓRIA -- e o aviso interno é reserva
# ===========================================================================


def test_o_tamanho_do_time_e_lido_pelo_ponteiro_REBASEADO():
    """`memory.team_size()` nunca respondeu neste cliente; `tamanho_do_time()`
    respondeu em 356 dos 361 convites medidos."""
    import inspect

    from blazesbot.bot.team import TeamService

    fonte = inspect.getsource(TeamService.team_size)
    assert "tamanho_do_time()" in fonte
    assert fonte.index("tamanho_do_time()") < fonte.index("memory.team_size()"), (
        "a leitura antiga voltou a ser a primeira")


def test_a_antiga_continua_como_RESERVA():
    """Ela não sai: num cliente onde só ela responde, é o que sobra."""
    import inspect

    from blazesbot.bot.team import TeamService

    assert "memory.team_size()" in inspect.getsource(TeamService.team_size)


def test_o_aviso_interno_so_vale_com_a_memoria_MUDA():
    """Ele diz "cliquei no Ok", não "o time formou".

    PELO AST: a chamada a `aceite_pendente` tem que estar DENTRO de um `if` que
    testa a leitura de time, e não solta no laço.
    """
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.team import TeamService

    arvore = ast.parse(textwrap.dedent(inspect.getsource(TeamService.montar_time)))
    dentro = [
        n for n in ast.walk(arvore)
        if isinstance(n, ast.If) and "team_size()" in ast.unparse(n.test)
        and "aceite_pendente" in ast.unparse(n)
    ]
    assert dentro, (
        "`aceite_pendente` voltou a valer sem antes perguntar à memória")


def test_AS_DUAS_CAVES_so_entram_com_time():
    """Sem time novo a instância não reseta e o boss não renasce.

    A HH já honrava a resposta de `montar_time`; o BC descartava e entrava de
    qualquer jeito. Pedido do usuário em 25/09/2026: *"é muito importante o
    reset, então conseguir verificar é o melhor jeito de, em todas as caves, ao
    entrar estar em um time"*.

    PELO AST: as duas rotinas citam `montar_time` em comentário, e uma busca
    textual acharia a menção em vez da decisão.
    """
    import ast
    import inspect
    import textwrap

    from blazesbot.bot.bc.routine import BossRushRoutine
    from blazesbot.bot.hh.routine import HHRoutine

    # A HH decide num auxiliar (`_garantir_o_time`), o BC no próprio estado.
    # O que o teste trava é a DECISÃO existir, não onde ela mora.
    for rotina, metodo in ((BossRushRoutine, "_do_entrar"),
                           (HHRoutine, "_garantir_o_time")):
        fonte = textwrap.dedent(inspect.getsource(getattr(rotina, metodo)))
        arvore = ast.parse(fonte)
        testes = [
            n for n in ast.walk(arvore)
            if isinstance(n, ast.If) and "montar_time" in ast.unparse(n.test)
        ]
        assert testes, (
            f"{rotina.__name__}.{metodo} descarta a resposta de `montar_time` "
            f"e entra na cave sem time")


# ===========================================================================
# A RESPOSTA DE `montar_time` TEM QUE SER A VERDADE (achado C3, 27/09/2026)
# ===========================================================================
#
# O teste acima trava que as rotinas PERGUNTAM; ele não olha o que
# `montar_time` RESPONDE. E ela respondia `True` com o time NÃO formado -- um
# resto de fb776800 (03/09), anterior à decisão de 25/09. Medido em 25/09: a
# HH seguiu para a porta sem time e ficou 60 min lá (9.935 tentativas), num
# covil sem boss para renascer. Aqui é COMPORTAMENTO: o convite sai, ninguém
# aceita, e a resposta tem que ser `False`.


def _servico_com_o_reseter_calado(tmp_path, monkeypatch, nick="NickDoTesteC3"):
    import logging
    from types import SimpleNamespace

    monkeypatch.setattr(mod_team, "ESPERA_PELA_RESPOSTA", 0.0)
    monkeypatch.setattr(mod_mural, "_CONVITES", {})
    monkeypatch.setattr(mod_mural, "_ACEITES", {})
    ctx = SimpleNamespace(
        templates=SimpleNamespace(folder=tmp_path),
        log=logging.getLogger("teste.reset_de_time"),
        char_name="QuemConvida", account=SimpleNamespace(login="conta-c3"),
        account_login="conta-c3",
        raise_if_stopped=lambda: None, tick=lambda segundos: None,
        memory=SimpleNamespace(tamanho_do_time=lambda: 1, team_size=lambda: None,
                               position=lambda: (0, 0), location=lambda: "teste"),
    )
    servico = mod_team.TeamService(ctx, nick_do_reset=lambda: nick)
    monkeypatch.setattr(servico, "_enviar_convite", lambda _nick: True)
    fechou = []
    monkeypatch.setattr(servico, "_fechar_janelas", lambda: fechou.append(1) or True)
    servico.fechou = fechou
    return servico


def test_convite_que_NINGUEM_ACEITOU_responde_que_nao_ha_time(tmp_path, monkeypatch):
    servico = _servico_com_o_reseter_calado(tmp_path, monkeypatch)
    assert servico.montar_time() is False


def test_sem_time_a_lista_de_amigos_fecha_antes_de_voltar(tmp_path, monkeypatch):
    """A lista aberta tapa o NPC da tentativa seguinte."""
    servico = _servico_com_o_reseter_calado(tmp_path, monkeypatch)
    servico.montar_time()
    assert servico.fechou, "a saída sem time não fechou as janelas do convite"
