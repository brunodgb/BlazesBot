"""O TECLADO MUDO -- 9 h 30 min de uma conta viva sem atacar nada.

Da AUDITORIA FORENSE de 13 h de log da madrugada de 07/09/2026 -- o porquê
medido, com os números e o que o council apontou, está em
`docs/decisoes/madrugada-07-09-2026.md`.

Às 02:32 uma conta parou de responder a qualquer tecla: o TAB não trocava alvo
com seis mobs a três unidades de distância, e a tecla de inventário não abria a
bolsa. A leitura de memória funcionou o tempo todo. O bot detectou, escreveu no
log uma vez por minuto por nove horas, e nunca mudou de estratégia.

O defeito não era a detecção -- era não haver desfecho para ela.
"""

from __future__ import annotations

import logging

from blazesbot.core import teclado_mudo

# ---------------------------------------------------------------------------
# 3. O TECLADO MUDO
# ---------------------------------------------------------------------------

def test_uma_tecla_muda_sozinha_NAO_acusa_nada():
    """TAB sem efeito pode ser circunstância do jogo. Duas teclas, não uma."""
    estado = teclado_mudo.TecladoMudo()
    estado.tab_sem_resposta(0.0, ha_mob_por_perto=True)
    assert estado.mudo_desde() is None
    assert estado.o_que_fazer(10_000.0) is None


def test_spot_vazio_NAO_e_teclado_mudo():
    """Sem mob por perto, o TAB não fazer nada é o jogo funcionando.

    Relogar por isso seria trocar uma conta parada por uma conta deslogada.
    """
    estado = teclado_mudo.TecladoMudo()
    estado.bolsa_nao_abriu(0.0)
    estado.tab_sem_resposta(0.0, ha_mob_por_perto=False)
    assert estado.mudo_desde() is None


def test_as_duas_teclas_mudas_levam_ao_ESC_e_depois_a_QUEDA():
    """A escada inteira, na ordem -- e cada degrau UMA vez."""
    estado = teclado_mudo.TecladoMudo()
    estado.tab_sem_resposta(0.0, ha_mob_por_perto=True)
    estado.bolsa_nao_abriu(0.0)

    assert estado.o_que_fazer(1.0) is None, "reagiu cedo demais"
    assert estado.o_que_fazer(teclado_mudo.SEGUNDOS_ATE_O_ESC) == "esc"
    assert estado.o_que_fazer(teclado_mudo.SEGUNDOS_ATE_O_ESC + 1) is None, \
        "mandou ESC duas vezes"
    assert estado.o_que_fazer(teclado_mudo.SEGUNDOS_ATE_O_RELOGIN) == "relogar"


def test_a_tecla_que_VOLTA_a_responder_encerra_o_incidente():
    """Qualquer prova de vida derruba a escada inteira -- inclusive o ESC."""
    estado = teclado_mudo.TecladoMudo()
    estado.tab_sem_resposta(0.0, ha_mob_por_perto=True)
    estado.bolsa_nao_abriu(0.0)
    assert estado.o_que_fazer(teclado_mudo.SEGUNDOS_ATE_O_ESC) == "esc"

    estado.tab_respondeu()
    assert estado.mudo_desde() is None
    assert estado.o_que_fazer(10_000.0) is None


def test_o_relogin_NAO_vira_laco():
    """Relogin que não resolve não pode se repetir para sempre.

    Se a causa for outra (cliente quebrado, conta com problema), a conta ficaria
    relogando a noite inteira -- trocando um defeito visível por outro.
    """
    estado = teclado_mudo.TecladoMudo()
    estado.tab_sem_resposta(0.0, ha_mob_por_perto=True)
    estado.bolsa_nao_abriu(0.0)
    estado.o_que_fazer(teclado_mudo.SEGUNDOS_ATE_O_ESC)

    t = teclado_mudo.SEGUNDOS_ATE_O_RELOGIN
    relogins = 0
    for _ in range(20):
        if estado.o_que_fazer(t) == "relogar":
            relogins += 1
        t += teclado_mudo.SEGUNDOS_ENTRE_RELOGINS
    assert relogins == teclado_mudo.MAXIMO_DE_RELOGINS
    assert estado.desistiu()


def test_o_desfecho_aperta_o_ESC_e_depois_declara_a_queda():
    """A ação, não a decisão: quem chama recebe as duas peças por função."""
    estado = teclado_mudo.TecladoMudo()
    estado.tab_sem_resposta(0.0, ha_mob_por_perto=True)
    estado.bolsa_nao_abriu(0.0)
    log = logging.getLogger("teste.teclado")
    escs: list[int] = []
    quedas: list[str] = []

    teclado_mudo.reagir(estado, log, teclado_mudo.SEGUNDOS_ATE_O_ESC,
                        lambda: escs.append(1), quedas.append)
    assert escs == [1] and quedas == []

    teclado_mudo.reagir(estado, log, teclado_mudo.SEGUNDOS_ATE_O_RELOGIN,
                        lambda: escs.append(1), quedas.append)
    assert escs == [1], "apertou ESC de novo em vez de relogar"
    assert quedas == ["teclado mudo"]


def test_sem_desfecho_de_queda_o_bot_avisa_e_segue():
    """`None` = ninguém ligou o relogin. Não pode explodir por isso."""
    estado = teclado_mudo.TecladoMudo()
    estado.tab_sem_resposta(0.0, ha_mob_por_perto=True)
    estado.bolsa_nao_abriu(0.0)
    log = logging.getLogger("teste.teclado")
    teclado_mudo.reagir(estado, log, teclado_mudo.SEGUNDOS_ATE_O_ESC,
                        lambda: None, None)
    teclado_mudo.reagir(estado, log, teclado_mudo.SEGUNDOS_ATE_O_RELOGIN,
                        lambda: None, None)


def test_o_supervisor_LIGA_o_desfecho_de_queda():
    """Sem esta trava a escada existiria completa e desligada em produção."""
    import inspect

    from blazesbot.bot import supervisor
    fonte = inspect.getsource(supervisor)
    assert "declarar_queda=declarar_queda" in fonte
    assert "def declarar_queda(motivo: str) -> None:" in fonte
