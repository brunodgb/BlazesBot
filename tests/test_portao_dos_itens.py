"""O PORTÃO DO INICIAR — quem vai abrir a bolsa e não apagar nada. 19/09/2026.

Depois da inversão, seleção vazia é o estado NORMAL de conta recém-criada, e o
risco disso é silencioso: a conta farma a noite inteira, a bolsa enche, e o
usuário só descobre quando o inventário transborda. Por isso a conferência
acontece no Iniciar, com confirmação.

O que estes testes protegem:

    QUEM ENTRA NA LISTA   -- só APP e HH, só com a limpeza LIGADA, só com tecla
                             de pet (sem auto-pick não cata item, logo a bolsa
                             não enche)
    QUEM NÃO ENTRA        -- limpeza desligada é decisão do usuário, e cobrá-la
                             em todo Iniciar transforma o aviso em OK automático
    O TIME É ATÔMICO      -- desligar um membro desliga o time inteiro, porque o
                             seguidor só roda enquanto o líder está ligado
    DESLIGAR NÃO DESATIVA -- a conta continua logando e relogando; ela só para
                             de farmar, para o usuário ajustar com o bot no ar
"""
from __future__ import annotations

import pytest

from blazesbot import web_lixo
from blazesbot.config import Account, BotConfig


def _conta(login, funcao="app", *, pet="6", limpar=5, apagaveis=(),
           hh_deletar=True, time=()):
    conta = Account(login=login)
    conta.settings.keys.pet_summon = pet
    conta.settings.app.apagar_lixo_a_cada = limpar
    conta.settings.app.apagaveis = list(apagaveis)
    conta.settings.app.time_logins = list(time)
    conta.settings.hh.deletar_lixo = hh_deletar
    conta.settings.hh.apagaveis = list(apagaveis)
    BotConfig().definir_funcao_da_conta(conta, funcao)
    return conta


def _config(*contas):
    cfg = BotConfig()
    cfg.accounts.extend(contas)
    for conta in cfg.accounts:
        conta.garantir_uid()      # como na leitura do arquivo de verdade
    return cfg


def _logins(pendentes):
    return sorted(c["login"] for c in pendentes)


# ---------------------------------------------------------------------------
# QUEM ENTRA
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("funcao", ["app", "hh"])
def test_limpeza_ligada_e_selecao_vazia_ENTRA(funcao):
    cfg = _config(_conta("sozinha", funcao))
    assert _logins(web_lixo.contas_ociosas(cfg)) == ["sozinha"]


def test_com_itens_escolhidos_NAO_entra():
    cfg = _config(_conta("escolheu", "app", apagaveis=["Bag.png"]))
    assert web_lixo.contas_ociosas(cfg) == []


def test_limpeza_DESLIGADA_nao_entra():
    """`Apagar o lixo a cada = 0` é decisão do usuário. Cobrar isso em todo
    Iniciar vira OK automático -- e aí, no dia em que o aviso estiver certo,
    ele é clicado sem ser lido."""
    cfg = _config(_conta("desligou", "app", limpar=0))
    assert web_lixo.contas_ociosas(cfg) == []


def test_hh_com_jogar_lixo_fora_desmarcado_nao_entra():
    cfg = _config(_conta("hh_sem_lixo", "hh", hh_deletar=False))
    assert web_lixo.contas_ociosas(cfg) == []


def test_SEM_TECLA_DE_PET_nao_entra():
    """Sem auto-pick o personagem não cata item do chão: a bolsa não enche e
    não há o que apagar. A regra é do jogo e já vale na Fada."""
    cfg = _config(_conta("sem_pet", "app", pet=""))
    assert web_lixo.contas_ociosas(cfg) == []


def test_o_BC_nao_entra():
    """Só APP e HH apagam item hoje."""
    cfg = _config(_conta("cave", "bc"))
    assert web_lixo.contas_ociosas(cfg) == []


def test_conta_INATIVA_nao_entra():
    conta = _conta("parada", "app")
    conta.enabled = False
    assert web_lixo.contas_ociosas(_config(conta)) == []


# ---------------------------------------------------------------------------
# O TIME É ATÔMICO
# ---------------------------------------------------------------------------

def test_o_time_do_LIDER_vem_junto_no_aviso():
    """O usuário precisa ver quem cai junto ANTES de decidir, não depois."""
    cfg = _config(_conta("lider", "app", time=["seg1", "seg2"]),
                  _conta("seg1", "app", apagaveis=["Bag.png"]),
                  _conta("seg2", "app", apagaveis=["Bag.png"]))

    pendentes = web_lixo.contas_ociosas(cfg)

    assert _logins(pendentes) == ["lider"]
    assert sorted(pendentes[0]["time"]) == ["seg1", "seg2"]


def test_desligar_o_LIDER_desliga_os_seguidores():
    """O seguidor só roda a macro enquanto o líder está com o APP ligado --
    desligar um sem o outro deixaria contas em estado indefinido."""
    cfg = _config(_conta("lider", "app", time=["seg1"]),
                  _conta("seg1", "app", apagaveis=["Bag.png"]))
    uid = cfg.accounts[0].uid

    desligadas = web_lixo.desligar_funcao(cfg, [uid])

    assert sorted(desligadas) == ["lider", "seg1"]
    assert [cfg.funcao_ativa_da_conta(c) for c in cfg.accounts] == ["", ""]


def test_desligar_um_SEGUIDOR_desliga_o_time_inteiro():
    """*"Se algum do time for inativado, o contrário também deve acontecer."*"""
    cfg = _config(_conta("lider", "app", time=["seg1", "seg2"],
                         apagaveis=["Bag.png"]),
                  _conta("seg1", "app"),
                  _conta("seg2", "app", apagaveis=["Bag.png"]))
    uid_do_seguidor = cfg.accounts[1].uid

    desligadas = web_lixo.desligar_funcao(cfg, [uid_do_seguidor])

    assert sorted(desligadas) == ["lider", "seg1", "seg2"]


def test_quem_esta_fora_de_time_desliga_sozinha():
    cfg = _config(_conta("sozinha", "app"), _conta("outra", "app"))

    desligadas = web_lixo.desligar_funcao(cfg, [cfg.accounts[0].uid])

    assert desligadas == ["sozinha"]
    assert cfg.funcao_ativa_da_conta(cfg.accounts[1]) == "app"


def test_desligar_NAO_desativa_a_conta():
    """Ela continua logando e relogando -- é o que permite ajustar a seleção
    com o bot no ar, que foi o pedido."""
    cfg = _config(_conta("sozinha", "app"))

    web_lixo.desligar_funcao(cfg, [cfg.accounts[0].uid])

    assert cfg.accounts[0].enabled is True
    assert cfg.funcao_ativa_da_conta(cfg.accounts[0]) == ""


def test_desligar_lista_vazia_nao_mexe_em_nada():
    cfg = _config(_conta("sozinha", "app"))
    assert web_lixo.desligar_funcao(cfg, []) == []
    assert cfg.funcao_ativa_da_conta(cfg.accounts[0]) == "app"


def test_uid_vazio_nao_desliga_o_bot_inteiro():
    """A armadilha que o teste acima descobriu: `uid` só nasce em
    `garantir_uid`, e um `""` na lista casaria com TODA conta sem uid -- que,
    com a regra do time, é a função do bot inteiro de uma vez."""
    cfg = BotConfig()
    cfg.accounts.extend([_conta("a", "app"), _conta("b", "app")])

    assert web_lixo.desligar_funcao(cfg, [""]) == []
    assert [cfg.funcao_ativa_da_conta(c) for c in cfg.accounts] == ["app", "app"]
