"""O time do APP: quem lidera, quem segue, e o que nunca entra no campo.

=========================================================================
O QUE ESTES TESTES IMPEDEM DE VOLTAR
=========================================================================

1. O LÍDER VENDO O PRÓPRIO TIME COMO VAZIO. `lider_do_time_do_app` responde
   "quem já puxa esta conta". A tela do editor faz essa pergunta sobre cada
   candidata para saber quais desabilitar -- e, sem dispensar a conta que está
   sendo editada, a pergunta se responde sozinha: os seguidores do próprio
   líder voltavam "já no time de <ele mesmo>", desmarcados e travados. O
   usuário abria o time que ele mesmo montou e via um time vazio.

   Foi encontrado olhando a tela, não rodando a suíte: o valor ia e voltava
   certo no `config.json`, e o defeito estava só na pergunta que a tela faz.

2. UMA CONTA SEGUINDO DOIS LÍDERES. Se A e B puxam a mesma conta, não existe
   resposta certa para "de quem é a macro". A trava é esta pergunta.

3. LIXO NO CAMPO. Login vazio guardado deixa uma vaga do time apontando para
   lugar nenhum -- e o time espera a largada de quem nunca vai chegar. Modo
   desconhecido faz quem lê o modo cair calado no ramo "não é nenhum dos três",
   e o time não faz nada, sem erro.
"""
from __future__ import annotations

from blazesbot.config import (
    MAXIMO_DE_SEGUIDORES_DO_TIME,
    MODO_PADRAO_DO_TIME,
    MODOS_DO_TIME,
    Account,
    BotConfig,
    normalizar_time_logins,
    normalizar_time_modo,
)


def _conta(login: str, *, segue: list[str] | None = None) -> Account:
    c = Account(login=login, last_char_name=login.title(), password_enc="x")
    c.enabled = True
    c.settings.app.time_logins = list(segue or [])
    return c


def _cfg(*contas: Account) -> BotConfig:
    cfg = BotConfig()
    cfg.accounts = list(contas)
    return cfg


# ---------------------------------------------------------------------------
# QUEM LIDERA QUEM
# ---------------------------------------------------------------------------

def test_conta_livre_nao_tem_lider():
    cfg = _cfg(_conta("um"), _conta("dois"))
    assert cfg.lider_do_time_do_app("dois") == ""


def test_quem_esta_na_lista_de_outro_tem_lider():
    cfg = _cfg(_conta("um", segue=["dois"]), _conta("dois"))
    assert cfg.lider_do_time_do_app("dois") == "um"


def test_o_lider_dispensado_nao_conta():
    """A pergunta da tela: 'além de MIM, alguém já puxa esta conta?'

    Sem o `ignorar`, o editor do próprio líder mostrava o time dele vazio.
    """
    cfg = _cfg(_conta("um", segue=["dois"]), _conta("dois"))
    assert cfg.lider_do_time_do_app("dois", ignorar="um") == ""


def test_dispensar_um_lider_nao_esconde_o_outro():
    """Dispensar não pode virar um jeito de a conta seguir dois líderes."""
    cfg = _cfg(_conta("um", segue=["tres"]),
               _conta("dois", segue=["tres"]),
               _conta("tres"))
    assert cfg.lider_do_time_do_app("tres", ignorar="um") == "dois"


def test_a_conta_nao_lidera_a_si_mesma():
    """Um `time_logins` que contenha o próprio login é ignorado.

    Sem isto a conta apareceria como seguidora dela mesma e sairia da lista de
    escolha da tela -- desligando o time por um dado que não faz sentido em vez
    de simplesmente não valer.
    """
    cfg = _cfg(_conta("um", segue=["um"]))
    assert cfg.lider_do_time_do_app("um") == ""


def test_conta_desativada_continua_dona_da_vaga():
    """Varre TODAS as contas, inclusive as desligadas.

    Mostrar a vaga como livre faria o usuário montar um time que muda sozinho
    quando ele religasse a outra conta.
    """
    lider = _conta("um", segue=["dois"])
    lider.enabled = False
    cfg = _cfg(lider, _conta("dois"))
    assert cfg.lider_do_time_do_app("dois") == "um"


def test_login_vazio_nunca_tem_lider():
    cfg = _cfg(_conta("um", segue=[""]), _conta("dois"))
    assert cfg.lider_do_time_do_app("") == ""
    assert cfg.lider_do_time_do_app("   ") == ""


# ---------------------------------------------------------------------------
# O QUE ENTRA NO CAMPO
# ---------------------------------------------------------------------------

def test_a_lista_perde_vazio_e_repetido():
    assert normalizar_time_logins(["um", "", "um", "  ", "dois"]) == ["um", "dois"]


def test_a_lista_respeita_o_teto():
    demais = [f"conta{i}" for i in range(MAXIMO_DE_SEGUIDORES_DO_TIME + 3)]
    assert len(normalizar_time_logins(demais)) == MAXIMO_DE_SEGUIDORES_DO_TIME


def test_a_lista_apara_o_espaco():
    assert normalizar_time_logins(["  um  "]) == ["um"]


def test_o_que_nao_e_lista_vira_lista_vazia():
    """O JavaScript pode mandar qualquer coisa, e o config.json pode ter sido
    editado à mão. Nenhum dos dois pode derrubar a abertura do bot."""
    for lixo in (None, "um", 7, {"a": 1}):
        assert normalizar_time_logins(lixo) == []


def test_modo_desconhecido_cai_no_padrao():
    for lixo in (None, "", "sincronizado", 7, "LARGADA"):
        assert normalizar_time_modo(lixo) == MODO_PADRAO_DO_TIME


def test_os_tres_modos_passam_inteiros():
    for modo in MODOS_DO_TIME:
        assert normalizar_time_modo(modo) == modo


def test_o_padrao_e_um_dos_modos():
    """Âncora: renomear um modo e esquecer o padrão deixaria o default fora da
    própria lista, e toda conta nova nasceria com um modo inválido."""
    assert MODO_PADRAO_DO_TIME in MODOS_DO_TIME


# ---------------------------------------------------------------------------
# A LISTA QUE A TELA MOSTRA
#
# 4. LISTA QUE SÓ CRESCE. Inelegível ia na lista desabilitada e com o motivo,
#    para o usuário não procurar uma conta que ele sabe que cadastrou. Com
#    muitas contas o resultado foi o contrário: o que dá para escolher fica
#    escondido no meio do que não dá. Pedido do usuário em 07/09/2026 -- e
#    `docs/INVARIANTES.md` sempre disse que conta farmando a cave "não aparece
#    na escolha do time"; era o código que divergia.
#
# 5. O TIME PERDENDO UM LOGIN AO SALVAR. Quem já está no time aparece SEMPRE, e
#    habilitado. Esconder o que está gravado faria a tela salvar sem ele, e
#    `time_logins` perderia o login por causa de um clique em BC que é
#    reversível ("sair do time por `bc_farm` não apaga o login").
# ---------------------------------------------------------------------------

def _ponte(cfg: BotConfig):
    from blazesbot.web_app import _App
    p = _App.__new__(_App)
    p.config, p.manager = cfg, None
    return p


def _candidatas(cfg: BotConfig, login: str) -> tuple[dict[str, str], int]:
    lider = next(c for c in cfg.accounts if c.login == login)
    d = _ponte(cfg)._candidatas_do_time(lider)
    return ({c["login"]: c["motivo"] for c in d["contas_do_time"]},
            d["contas_do_time_ocultas"])


def test_conta_livre_aparece_sem_motivo():
    vis, fora = _candidatas(_cfg(_conta("um"), _conta("dois")), "um")
    assert vis == {"dois": ""}
    assert fora == 0


def test_conta_INATIVA_nao_aparece():
    cfg = _cfg(_conta("um"), _conta("dois"))
    cfg.accounts[1].enabled = False
    vis, fora = _candidatas(cfg, "um")
    assert vis == {}
    assert fora == 1


def test_conta_com_OUTRA_FUNCAO_nao_aparece():
    """Farmar a cave e rodar o APP são excludentes: convocar arrancaria a conta
    do meio de uma run (teleporte gasto, boss vivo)."""
    for funcao in ("bc", "hh"):
        cfg = _cfg(_conta("um"), _conta("dois"))
        cfg.definir_funcao_da_conta(cfg.accounts[1], funcao)
        vis, fora = _candidatas(cfg, "um")
        assert vis == {}, funcao
        assert fora == 1, funcao


def test_conta_em_OUTRO_TIME_nao_aparece():
    cfg = _cfg(_conta("um"), _conta("dois", segue=["tres"]), _conta("tres"))
    vis, fora = _candidatas(cfg, "um")
    assert vis == {"dois": ""}, "quem lidera outro time continua convocável"
    assert fora == 1, "a seguidora de 'dois' não pode ser puxada por 'um'"


def test_o_PROPRIO_time_aparece_marcavel():
    """Sem dispensar o líder editado, os seguidores dele voltavam como 'já no
    time de <ele mesmo>' e o usuário abria o time que montou e via vazio."""
    cfg = _cfg(_conta("um", segue=["dois"]), _conta("dois"))
    vis, fora = _candidatas(cfg, "um")
    assert vis == {"dois": ""}
    assert fora == 0


def test_quem_JA_ESTA_no_time_aparece_mesmo_inelegivel():
    """Com o motivo à vista, e nunca escondido: a tela salva o que está
    marcado, e esconder apagaria o login de `time_logins`."""
    cfg = _cfg(_conta("um", segue=["dois", "tres"]), _conta("dois"),
               _conta("tres"))
    cfg.definir_funcao_da_conta(cfg.accounts[1], "bc")
    cfg.accounts[2].enabled = False
    vis, fora = _candidatas(cfg, "um")
    assert vis == {"dois": "farmando a cave", "tres": "inativa"}
    assert fora == 0


def test_a_conta_editada_nunca_aparece_na_propria_lista():
    vis, _ = _candidatas(_cfg(_conta("um"), _conta("dois")), "um")
    assert "um" not in vis


def test_conta_SEM_LOGIN_nao_aparece():
    """Login vazio no time deixa uma vaga apontando para lugar nenhum."""
    cfg = _cfg(_conta("um"), Account(login="", enabled=True))
    vis, fora = _candidatas(cfg, "um")
    assert vis == {}
    assert fora == 0, "conta sem login não é 'conta escondida', é linha em branco"
