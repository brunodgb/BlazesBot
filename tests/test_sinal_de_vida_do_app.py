"""O SINAL DE VIDA do seguidor do APP -- 15/09/2026.

O líder não convida às cegas: antes de abrir a Block list ele pergunta quem
está de pé. Decisão do usuário: *"é bom identificar se o líder está online, se
os seguidores estão online, para também não mandar time cegamente, pois se
algum seguidor estiver off não vai dar para enviar o convite de time"*.

`mural.publicar_estado` já existia e a docstring dela já dizia "uma vez por
volta" -- o que faltava era alguém publicar. Os dois caminhos que chamavam eram
o modo de sincronia (desligado) e o pedido de cura à Fada.
"""

from __future__ import annotations

import inspect

from blazesbot.bot import mural, supervisor


def test_o_gancho_por_volta_PUBLICA_o_estado():
    """Sem isso, uma conta rodando macro normalmente não existe para o líder."""
    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    assert "def antes_de_cada_volta()" in fonte
    assert "mural.publicar_estado(" in fonte
    assert "antes_da_volta=antes_de_cada_volta" in fonte, \
        "o gancho existe mas não foi ligado no executor"


def test_o_gancho_leva_o_MAX_HP_junto():
    """`publicar_estado` SUBSTITUI o estado inteiro.

    A Fada lê `max_hp` daqui para calcular a porcentagem da vítima. Publicar sem
    ele apagaria, uma vez por volta, a informação que ela usa para curar.
    """
    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    trecho = fonte[fonte.index("def antes_de_cada_volta()"):]
    trecho = trecho[:trecho.index("def montar_cura")]
    assert "max_hp=" in trecho, "a Fada perderia o máximo da vítima"
    assert "nick=" in trecho, "o líder casa o time do jogo por NICK"


def test_o_gancho_NAO_abandonou_a_barra_de_atalhos():
    """Era o que este gancho fazia antes; ele é o único ponto por volta."""
    fonte = inspect.getsource(supervisor.AccountSupervisor._rodar_modo_app)
    trecho = fonte[fonte.index("def antes_de_cada_volta()"):]
    trecho = trecho[:trecho.index("def montar_cura")]
    assert "garantir_barra()" in trecho


def test_conta_que_para_de_publicar_SOME():
    """É o que faz "está online" significar alguma coisa."""
    mural.publicar_estado("seguidor1", max_hp=5000, nick="Fulano")
    assert mural.estado_da_conta("seguidor1") is not None
    mural.esquecer_estado("seguidor1")
    assert mural.estado_da_conta("seguidor1") is None
