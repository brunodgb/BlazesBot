"""Conferir os modelos de exclusão — fotografa e DESENHA, sem apagar nada.

Ecossistema **APP**. Molde do `teste_venda`/`amostragem_de_cliques`: adota a
janela com `AccountSupervisor._adotar_janela_existente()` **sem iniciar a
thread** e devolve o PID com `_release()` no `finally` de TODA saída -- sem
isso o bot de verdade veria a janela como de outra conta e abriria um cliente
novo (fila de três horas).

=========================================================================
POR QUE ISTO EXISTE
=========================================================================

Os 81 modelos de item vieram do T-R0XX (ver.6139 de OUTRO bot) e **nunca foram
medidos contra o nosso cliente**. Deletar é irreversível: descobrir um falso
positivo apagando custa um item que não volta.

Esta ferramenta responde à pergunta certa ANTES: *o que seria apagado se eu
ligasse isso agora?* Ela abre o inventário, fotografa, desenha um retângulo
vermelho em cada casamento com o nome do modelo, um círculo verde no ícone de
deletar, salva o PNG e abre. **Não clica em item nenhum e não manda a tecla de
apagar.**

Ver *onde* casou importa mais que ver *quanto*: um falso positivo aparece como
retângulo em cima do item errado, e isso salta aos olhos numa imagem — numa
lista de notas, não.
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from ...config import Account, BotConfig
from .. import afericao_do_lixo
from ..context import BotContext, StopRequested
from ..supervisor import AccountSupervisor
from . import deletador

_PARADA = threading.Event()
_EM_ANDAMENTO = threading.Lock()


def em_andamento() -> bool:
    return _EM_ANDAMENTO.locked()


def cancelar() -> None:
    _PARADA.set()


def rodar(
    config: BotConfig,
    account: Account,
    on_status: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Fotografa a bolsa e marca o que os modelos reconheceriam.

    Devolve `{"ok", "erro", "achados", "arquivo", "resumo"}`. Bloqueia até
    terminar (é rápido: uma captura e ~2,6 s de casamento).
    """
    log = logging.getLogger(f"blazes.{account.login or 'afericao'}")

    if not _EM_ANDAMENTO.acquire(blocking=False):
        return {"ok": False, "erro": "Já existe uma conferência rodando."}

    _PARADA.clear()
    supervisor = AccountSupervisor(config, account, on_status=on_status)
    ctx: BotContext | None = None
    try:
        log.info("=== CONFERINDO OS MODELOS DE EXCLUSÃO ===")
        adotada = supervisor._adotar_janela_existente()
        if not adotada:
            return {"ok": False, "erro": (
                "Não encontrei a janela desta conta. Abra o jogo e entre com o "
                "personagem.")}

        pid, hwnd, ja_logado, personagem = adotada
        supervisor.pid, supervisor.hwnd = pid, hwnd
        if not ja_logado:
            return {"ok": False, "erro": (
                "O cliente encontrado está na tela de login.")}

        ctx = BotContext(config=config, account=account, pid=pid, hwnd=hwnd,
                         stop_event=_PARADA)
        ctx.char_name = personagem

        # Abre o inventário com a MESMA tecla que o deletador usa. Sem ela não
        # há bolsa na tela e a conferência não diria nada.
        tecla = getattr(ctx.settings.keys, "inventory", "") or ""
        if not tecla:
            return {"ok": False, "erro": (
                "A tecla de Inventário não está configurada na aba Teclas — "
                "sem ela não dá para abrir a bolsa.")}
        # MESMA REGRA DO DELETADOR: só mexe na tecla se precisar, e devolve a
        # tela como encontrou. A tecla é um interruptor — apertá-la numa bolsa
        # já aberta a FECHA, e aí a conferência não teria o que fotografar.
        eu_abri = False
        if deletador.inventario_esta_aberto(ctx) is not True:
            ctx.press(tecla)
            eu_abri = True
            ctx.tick(deletador.ESPERA_DA_BOLSA_ABRIR)

        resultado = afericao_do_lixo.conferir(ctx)

        if eu_abri:
            try:
                deletador._fechar_a_bolsa(ctx, tecla)
            except Exception:
                pass

        if resultado.get("ok"):
            resultado["resumo"] = resumir(resultado)
            log.info("Conferência: %s", resultado["resumo"])
            log.info("Imagem em %s", resultado.get("arquivo"))
        return resultado

    except StopRequested:
        return {"ok": False, "erro": "Conferência interrompida."}
    except Exception as exc:
        log.exception("Conferência falhou: %s", exc)
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
    finally:
        if ctx is not None:
            ctx.close()
        supervisor._release()
        _PARADA.clear()
        _EM_ANDAMENTO.release()


def resumir(resultado: dict[str, Any]) -> str:
    """O veredito em texto, montado no Python — as duas interfaces só exibem."""
    achados = resultado.get("achados") or []
    if not achados:
        return (f"Nenhum item da sua bolsa casou com os "
                f"{resultado.get('modelos', 0)} modelos. Nada seria apagado.")
    modelos = sorted({a["modelo"] for a in achados})
    return (f"{len(achados)} item(ns) seriam apagados, de {len(modelos)} "
            f"modelo(s): {', '.join(modelos[:6])}"
            + (" e outros" if len(modelos) > 6 else "")
            + ". ABRA A IMAGEM e confira cada retângulo antes de confiar.")
