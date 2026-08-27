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
