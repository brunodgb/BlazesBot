"""Log NOVO sai traduzido a partir da troca de idioma; o que já foi escrito
não muda, e nenhum outro handler no mesmo `record` pode ver a alteração --
`_LogHandler._formatar` nunca pode mutar `record.msg`/`record.args`.
"""
import logging
from collections import deque

import pytest

from blazesbot.core import i18n
from blazesbot.web_app import _LogHandler


@pytest.fixture(autouse=True)
def _idioma_de_log_limpo():
    """Estado global -- cada teste começa e termina em PT-BR."""
    i18n.definir_idioma_do_log("pt-br")
    yield
    i18n.definir_idioma_do_log("pt-br")


def _registro(template: str, *args) -> logging.LogRecord:
    return logging.LogRecord(
        name="blazes.conta1", level=logging.INFO, pathname=__file__,
        lineno=1, msg=template, args=args or None, exc_info=None,
    )


def test_pt_br_e_identico_ao_formato_de_sempre():
    handler = _LogHandler(deque())
    registro = _registro("Revivendo")
    assert handler._formatar(registro) == handler.format(registro)


def test_troca_de_idioma_traduz_template_catalogado():
    handler = _LogHandler(deque())
    i18n.definir_idioma_do_log("en")
    registro = _registro("Revivendo")
    assert handler._formatar(registro).endswith("Reviving")


def test_template_com_args_substitui_certo():
    handler = _LogHandler(deque())
    i18n.definir_idioma_do_log("es")
    registro = _registro("Não consegui salvar a configuração: %s", "disco cheio")
    linha = handler._formatar(registro)
    assert "No se pudo guardar la configuración: disco cheio" in linha


def test_template_nao_catalogado_cai_para_pt_br_sem_quebrar():
    handler = _LogHandler(deque())
    i18n.definir_idioma_do_log("en")
    registro = _registro("Uma mensagem qualquer que ninguém catalogou ainda")
    assert "Uma mensagem qualquer que ninguém catalogou ainda" in \
        handler._formatar(registro)


def test_formatar_NUNCA_muta_o_record():
    """Outro handler no MESMO logger (o log de dev) recebe o mesmo objeto
    `record` -- se `_formatar` mutasse `msg`/`args`, o dev veria o texto
    traduzido em vez do original."""
    handler = _LogHandler(deque())
    i18n.definir_idioma_do_log("en")
    registro = _registro("Não consegui salvar a configuração: %s", "disco cheio")
    msg_antes, args_antes = registro.msg, registro.args
    handler._formatar(registro)
    assert registro.msg == msg_antes
    assert registro.args == args_antes


def test_idioma_do_log_e_pt_br_por_padrao_e_ignora_valor_invalido():
    i18n.definir_idioma_do_log("klingon")
    assert i18n.idioma_atual_do_log() == "pt-br"


def test_fila_recebe_a_linha_traduzida_de_ponta_a_ponta():
    """O caminho real: um `logging.Logger` de verdade, não um LogRecord à mão."""
    fila: deque[tuple[str, str]] = deque()
    handler = _LogHandler(fila)
    logger = logging.getLogger("blazes.conta_de_teste")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        i18n.definir_idioma_do_log("en")
        logger.info("Revivendo")
        assert len(fila) == 1
        conta, linha = fila[0]
        assert conta == "conta_de_teste"
        assert linha.endswith("Reviving")
    finally:
        logger.removeHandler(handler)
