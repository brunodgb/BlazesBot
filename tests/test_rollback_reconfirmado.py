"""O rollback só é acusado DEPOIS de reconfirmado na releitura.

Achado A6 da auditoria de 27/09/2026: a espera de 0,25 s existia "para o
servidor assentar", mas o veredito não era refeito depois dela -- 410 de 505
rollbacks da creubo (26/09) já não existiam na releitura, e custaram 1.382 s de
manobra num dia, contra 74 s dos que se sustentaram. Um rollback que não se
confirma não avisa, não grava no diário e não manobra.

ESTRUTURAL, e o limite está dito: `follow_path` não tem harness que o rode
(os testes do projeto o travam pelo código-fonte, como este). A ordem é o que
se prova -- esperar, reler, decidir, e só então agir.
"""
import inspect

from blazesbot.bot import navegacao


def test_esperar_RELER_e_decidir_vem_antes_do_aviso_e_da_manobra():
    fonte = inspect.getsource(navegacao.Navigator.follow_path)
    trecho = fonte[fonte.index("voltou = houve_rollback("):]
    espera = trecho.index("ctx.tick(0.25)")
    releitura = trecho.index("atual = self.position()", espera)
    segundo_veredito = trecho.index("houve_rollback(", releitura)
    nao_confirmou = trecho.index("if voltou is None:", segundo_veredito)
    aviso = trecho.index("Voltei do waypoint")
    diario = trecho.index('"rollback"')
    manobra = trecho.index("destravar_pelos_vizinhos(")
    assert espera < releitura < segundo_veredito < nao_confirmou < aviso
    assert nao_confirmou < diario and nao_confirmou < manobra
