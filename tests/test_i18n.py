"""i18n: PT-BR nunca falta, EN/ES podem, e o sistema não pode quebrar por isso.

`diag_dpapi_indisponivel` no `traducoes.json` foi deixado SEM "es" de propósito
-- é a prova de que o fallback funciona de verdade, não só na intenção.
"""
from blazesbot.config import BotConfig
from blazesbot.core import i18n


def test_idioma_sobrevive_ida_e_volta(tmp_path):
    """A escolha de idioma tem que aguentar fechar e reabrir o bot."""
    caminho = tmp_path / "config.json"
    cfg = BotConfig()
    cfg.idioma = "en"
    cfg.save(caminho)
    assert BotConfig.load(caminho).idioma == "en"


def test_idioma_default_e_pt_br():
    assert BotConfig().idioma == "pt-br"


def test_pt_br_e_a_fonte():
    assert i18n.traduzir("nav_contas", "pt-br") == "Contas"


def test_idioma_suportado_traduz():
    assert i18n.traduzir("nav_contas", "en") == "Accounts"
    assert i18n.traduzir("nav_contas", "es") == "Cuentas"


def test_chave_sem_es_cai_para_pt_br():
    """A chave existe, tem PT-BR e EN, mas não tem ES -- pedir ES não quebra."""
    assert i18n.traduzir("diag_dpapi_indisponivel", "es") == \
        i18n.traduzir("diag_dpapi_indisponivel", "pt-br")


def test_idioma_desconhecido_cai_para_pt_br():
    assert i18n.traduzir("nav_contas", "klingon") == \
        i18n.traduzir("nav_contas", "pt-br")


def test_chave_inexistente_nao_lanca():
    assert i18n.traduzir("chave_que_nao_existe", "pt-br") == \
        "[chave_que_nao_existe]"


def test_resolver_idioma_cobre_toda_a_tabela_sem_lacuna():
    """Toda chave, em todo idioma suportado, sempre resolve para algo -- nunca None."""
    for idioma in i18n.IDIOMAS_SUPORTADOS:
        resolvido = i18n.resolver_idioma(idioma)
        assert resolvido, "tabela não pode resolver vazia"
        assert all(isinstance(v, str) and v for v in resolvido.values())


def test_resolver_idioma_es_usa_fallback_na_chave_incompleta():
    resolvido = i18n.resolver_idioma("es")
    assert resolvido["diag_dpapi_indisponivel"] == \
        i18n.traduzir("diag_dpapi_indisponivel", "pt-br")
