"""O TETO DO DIÁLOGO -- ele só sabia apertar, e isso parou uma conta por 4 h.

Da AUDITORIA FORENSE de 13 h de log da madrugada de 07/09/2026 -- o porquê
medido, com os números e o que o council apontou, está em
`docs/decisoes/madrugada-07-09-2026.md`.

O teto da espera pelo diálogo do NPC aprende com as aberturas medidas. Como a
amostra só entra quando o diálogo ABRE, ele congelou em 427 ms às 08:14 e ficou
idêntico por 3 h 51 min: 13.449 tentativas, zero entradas na cave.

A medição que levantaria o teto só podia vir do sucesso que o próprio teto
impedia. O que estes testes travam é a saída: a FALHA também informa.
"""

from __future__ import annotations

from blazesbot.bot import ui_do_jogo

# ---------------------------------------------------------------------------
# 1. O TETO QUE SÓ APRENDIA COM SUCESSO
# ---------------------------------------------------------------------------

def _ui_falsa():
    """Só o que `_afrouxar_o_teto` precisa: o contador de falhas seguidas."""
    ui = ui_do_jogo.UIDoJogo.__new__(ui_do_jogo.UIDoJogo)
    ui._dialogos_seguidos_sem_abrir = 0
    return ui


def test_sem_falhas_o_teto_nao_e_tocado():
    """O afrouxamento é para o poço. No caso comum não pode custar nada."""
    ui = _ui_falsa()
    assert ui._afrouxar_o_teto(0.427) == 0.427


def test_falhas_seguidas_AFROUXAM_o_teto():
    """A trava de 07/09/2026: 13.449 falhas com o teto parado em 427 ms.

    Com o afrouxamento, cinco falhas já dobram a espera -- e o diálogo que
    levava 500 ms passa a caber dentro dela.
    """
    ui = _ui_falsa()
    ui._dialogos_seguidos_sem_abrir = ui_do_jogo.FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR
    assert ui._afrouxar_o_teto(0.427) > 0.427


def test_o_afrouxamento_para_no_TETO_DO_DESESPERO():
    """Passado o teto duro não é lentidão: é NPC errado ou cliente preso.

    Sem este limite a conta trocaria "não entra nunca" por "tenta uma vez a
    cada dois segundos" -- e na disputa da cave isso é perder de outro jeito.
    """
    ui = _ui_falsa()
    ui._dialogos_seguidos_sem_abrir = 500
    assert ui._afrouxar_o_teto(0.427) == ui_do_jogo.TETO_DO_DESESPERO


def test_o_teto_do_desespero_passa_do_maior_teto_normal():
    """Ele tem de caber uma abertura que o aprendizado normal já rejeitaria.

    O maior teto que o aprendizado produz é `LIMITE_DA_ESPERA_DO_DIALOGO_LENTA`
    (650 ms). Um desespero abaixo disso não afrouxaria nada -- seria o mesmo
    poço com outro nome.
    """
    assert (ui_do_jogo.TETO_DO_DESESPERO
            >= 1.5 * ui_do_jogo.LIMITE_DA_ESPERA_DO_DIALOGO_LENTA)
