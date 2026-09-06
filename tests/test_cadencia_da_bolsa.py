"""A CADÊNCIA DA BOLSA -- e o diagnóstico de por que ela se repete.

Relato do usuário em 05/09/2026: *"tem vezes que o APP está bugando, começa a
abrir e fechar várias vezes o inventário, e no meio tempo ficar dando TAB sem
começar nenhuma macro."*

Medido no log do mesmo dia: `gamerblazes` fez 622 limpezas, **595 repetindo o
mesmo número de volta**, com rajada de **275 limpezas consecutivas na volta
150** -- três em cada quatro apagando ZERO itens.

Estes testes travam o COMPORTAMENTO ATUAL (que ainda é o defeituoso) e o
diagnóstico que o denuncia. A régua não mudou: quem decidir consertá-la vai ter
de mexer nestes testes de propósito, e é assim que se sabe que a correção foi
uma escolha e não um efeito colateral.
"""
from __future__ import annotations

import logging

import pytest

from blazesbot.core.cadencia_da_bolsa import CadenciaDaBolsa


@pytest.fixture
def cadencia():
    return CadenciaDaBolsa(logging.getLogger("teste.bolsa"))


def _perguntar(c, voltas, abortadas=0, a_cada=10, motivo="volta completa"):
    return c.deve_limpar(voltas=voltas, abortadas=abortadas, a_cada=a_cada,
                         motivo_do_corte=motivo)


# ---------------------------------------------------------------- a régua

def test_limpa_no_multiplo():
    assert _perguntar(CadenciaDaBolsa(logging.getLogger("t")), 10) is True


def test_nao_limpa_fora_do_multiplo(cadencia):
    assert _perguntar(cadencia, 11) is False


def test_volta_zero_nao_limpa(cadencia):
    """`0 % 10` é zero, e limpar antes da primeira volta seria abrir a bolsa
    assim que o modo liga."""
    assert _perguntar(cadencia, 0) is False


def test_cadencia_desligada_nao_limpa(cadencia):
    assert _perguntar(cadencia, 10, a_cada=0) is False


# ------------------------------------------------- o defeito, exposto

def test_a_MESMA_volta_NAO_limpa_de_novo(cadencia):
    """O piso do conserto, 06/09/2026.

    A régua olha o RESTO, não a mudança: enquanto o contador de voltas completas
    não andar, o resto continua zero e a bolsa era aberta a cada giro do laço --
    275 vezes seguidas na volta 150, na medição de campo.

    Isto NÃO conserta a causa (o contador continua congelando quando a volta é
    cortada). Conserta o dano visível, sem mexer na semântica que o usuário
    configurou na tela.
    """
    assert _perguntar(cadencia, 150) is True
    assert _perguntar(cadencia, 150) is False
    assert _perguntar(cadencia, 150) is False


def test_a_volta_seguinte_no_multiplo_limpa_normalmente(cadencia):
    """O bloqueio é da volta REPETIDA, não da cadência."""
    assert _perguntar(cadencia, 150) is True
    assert _perguntar(cadencia, 160) is True


def test_a_repeticao_vira_AVISO_com_a_causa(cadencia, caplog):
    """O log tem de dizer POR QUE o contador não andou -- sem isso a rajada
    aparece como 'hora de limpar' repetida e ninguém sabe de onde vem."""
    with caplog.at_level(logging.WARNING):
        _perguntar(cadencia, 150, abortadas=40)
        _perguntar(cadencia, 150, abortadas=41, motivo="sem alvo")

    avisos = [r.getMessage() for r in caplog.records
              if r.levelno >= logging.WARNING]
    assert len(avisos) == 1, avisos
    assert "volta 150" in avisos[0]
    assert "NÃO abro a bolsa" in avisos[0]
    assert "sem alvo" in avisos[0], "o aviso não nomeia o motivo do corte"
    assert "Abortadas subiram 1" in avisos[0]


def test_a_primeira_limpeza_NAO_e_aviso(cadencia, caplog):
    """Rajada é anomalia; a limpeza normal é rotina e não pode virar ruído."""
    with caplog.at_level(logging.INFO):
        _perguntar(cadencia, 10)

    assert [r.levelno for r in caplog.records] == [logging.INFO]
    assert "hora de limpar a bolsa" in caplog.records[0].getMessage()


def test_a_contagem_de_repeticoes_ZERA_quando_a_volta_anda(cadencia, caplog):
    _perguntar(cadencia, 150)
    _perguntar(cadencia, 150)
    caplog.clear()                      # só interessa o que vem DEPOIS
    with caplog.at_level(logging.INFO):
        _perguntar(cadencia, 160)

    assert all(r.levelno == logging.INFO for r in caplog.records)


# ------------------------------------------------- o executor pergunta

def test_o_executor_passa_o_MOTIVO_do_ultimo_corte():
    """Sem o motivo, o aviso não serve para nada: ele existe para dizer qual
    caminho de aborto está congelando o contador."""
    import inspect

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = inspect.getsource(ExecutorDeMacro._limpar_a_bolsa_se_for_a_hora)
    assert "motivo_do_corte=self._ultimo_corte" in fonte


def test_todo_corte_da_volta_TEM_rotulo():
    """Cada saída da volta precisa dizer quem é -- um rótulo faltando vira um
    '?' no diagnóstico bem na hora em que ele importa."""
    import inspect
    import re

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = inspect.getsource(ExecutorDeMacro._uma_volta_simples)
    abortos = re.findall(r"_abortar_a_volta\(([^)]*)\)", fonte)
    assert abortos, "nenhum aborto encontrado -- o teste perdeu o alvo"
    sem_rotulo = [a for a in abortos if "motivo=" not in a]
    assert not sem_rotulo, f"{len(sem_rotulo)} aborto(s) sem motivo"


def test_o_caminho_SEM_ALVO_tambem_se_rotula():
    """Ele não passa por `_abortar_a_volta` -- e é justamente o corte que mais
    aparece na rajada medida em campo."""
    import inspect

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = inspect.getsource(ExecutorDeMacro._uma_volta_simples)
    assert '_ultimo_corte = "sem alvo"' in fonte


# ---------------------------------------------------------------------------
# A RAIZ: nenhum contador pode congelar -- 06/09/2026
# ---------------------------------------------------------------------------
#
# *"Se trava, então é importante ajustar; tente ajustar a raiz do problema para
# não travar nada de forma alguma."* -- usuário.
#
# A cadência ancorada só nas voltas COMPLETAS congelava junto com elas. Em farm
# normal metade das voltas aborta (285 completas contra 289 abortadas, numa
# sessão medida), e quando a aquisição para de trazer alvo, NENHUMA completa.

def test_a_cadencia_conta_TENTATIVAS_e_nao_so_voltas_completas():
    import inspect

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = inspect.getsource(ExecutorDeMacro._limpar_a_bolsa_se_for_a_hora)
    assert "self.voltas + self.voltas_abortadas" in fonte


def test_TODA_saida_do_laco_incrementa_algum_contador():
    """A saída "sem alvo" era a única que não incrementava nada -- e era
    justamente a que dominava o log (401 dos 407 avisos)."""
    import inspect
    import re

    from blazesbot.bot.app.executor import ExecutorDeMacro

    fonte = inspect.getsource(ExecutorDeMacro._uma_volta_simples)
    # Cada `return False` que representa "esta volta acabou sem completar" tem
    # de vir depois de um incremento; os únicos isentos são os de PARADA
    # (`_continuar`/`_esperar_saida_da_pausa`), que não são fim de volta.
    for trecho, esperado in (("sem alvo", "self.voltas_abortadas += 1"),
                             ("portão: alvo ausente ou morto",
                              "self.voltas_abortadas += 1")):
        i = fonte.index(trecho)
        depois = fonte[i:i + 400]
        assert esperado in depois, trecho


def test_a_bolsa_volta_a_limpar_mesmo_com_a_aquisicao_falhando(cadencia):
    """O desfecho prático: com a aquisição falhando, o contador de tentativas
    continua andando, então a cadência anda -- e a bolsa é limpa na hora certa
    em vez de em rajada ou nunca."""
    # 12 tentativas, todas abortadas por falta de alvo.
    resultados = [_perguntar(cadencia, voltas=n, abortadas=n, a_cada=12,
                             motivo="sem alvo")
                  for n in range(1, 25)]

    assert resultados.count(True) == 2, "deveria limpar em 12 e em 24"
