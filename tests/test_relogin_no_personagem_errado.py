"""Relogin que entra em OUTRO personagem não grava nada e deixa a conta parada.

Achado C4 da auditoria de 27/09/2026. O login clica na plaquinha pela posição
e aperta Enter sem conferir o realce; em 24/09 03:05 entrou em WizzOfBlazes2 no
lugar de WizzOfBlazes4, o supervisor gravou o nick errado como o da conta e o
APP gravou a base no lugar errado (~1 h improdutiva). Decisão com o council:
não gravar, avisar com ERRO, ficar online PARADA -- não matar o cliente.
"""
import logging
from types import SimpleNamespace

from blazesbot.bot.supervisor import AccountSupervisor


def _supervisor(nick_salvo):
    sup = AccountSupervisor.__new__(AccountSupervisor)
    sup.account = SimpleNamespace(login="blazesgamer", last_char_name=nick_salvo)
    sup.log = logging.getLogger("teste.personagem_errado")
    sup.on_status = None
    sup._personagem_errado = None
    sup.gravados, sup.batizados = [], []
    sup._gravar_personagem = sup.gravados.append
    sup._batizar_janela = sup.batizados.append
    return sup


def test_OUTRO_personagem_nao_grava_nada_e_marca_a_sessao():
    sup = _supervisor("WizzOfBlazes4")
    assert sup._aceitar_o_personagem_lido("WizzOfBlazes2", renomear=True) is False
    assert sup.gravados == [] and sup.batizados == []
    assert sup._personagem_errado == "WizzOfBlazes2"


def test_o_personagem_CERTO_grava_como_sempre_sem_olhar_maiuscula():
    sup = _supervisor("WizzOfBlazes4")
    assert sup._aceitar_o_personagem_lido("wizzofblazes4 ", renomear=True) is True
    assert sup.gravados == ["wizzofblazes4"] and sup.batizados == ["wizzofblazes4"]
    assert sup._personagem_errado is None


def test_conta_NOVA_sem_nick_salvo_grava_o_que_leu():
    """Sem nick guardado não há o que comparar: é o primeiro login da conta."""
    sup = _supervisor("")
    assert sup._aceitar_o_personagem_lido("Igni001") is True
    assert sup.gravados == ["Igni001"]


def test_o_erro_sai_no_nivel_ERROR(caplog):
    sup = _supervisor("WizzOfBlazes4")
    with caplog.at_level(logging.ERROR, logger="teste.personagem_errado"):
        sup._aceitar_o_personagem_lido("WizzOfBlazes2")
    assert any(r.levelno == logging.ERROR and "WizzOfBlazes2" in r.getMessage()
               for r in caplog.records)
