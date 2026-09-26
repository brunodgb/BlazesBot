"""TEMPORÁRIO -- teste isolado do módulo de venda.

=========================================================================
PARA QUE SERVE
=========================================================================

Validar a venda SEM rodar o farm inteiro. O personagem já está em Stone City,
logado, com a bolsa cheia; o botão "Testar Venda" faz só o pedaço que interessa:

    ir até o Rich (painel de arredores)  ->  vender  ->  PARAR

E nada além disso. Em particular, NÃO faz:

  * voltar para a cidade (Guild Token / Pedra de Retorno) -- o personagem já
    está lá, e validar o retorno é outro teste;
  * recomprar a pedra gasta (`buy_supplies`) -- não houve pedra gasta;
  * entrar na cave, lutar, ou qualquer coisa da rotina.

=========================================================================
COMO APAGAR DEPOIS
=========================================================================

Este arquivo é uma FOLHA: nada do bot importa dele. Para remover o teste basta
apagar este módulo e os blocos marcados TEMPORÁRIO que o citam:

    blazesbot/web_app.py         -- `_App.testar_venda`, `_App.cancelar_teste_venda`
                                    e os dois métodos correspondentes na `Api`
    web/main.js / web/index.html -- o botão `#btn-testar-venda`
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from ...config import Account, BotConfig
from ..context import BotContext, StopRequested
from ..supervisor import AccountSupervisor
from .vendor import VendorService

# Parada do teste. Fica no módulo (e não num objeto) porque o teste é único: a
# interface não deixa rodar dois, e o botão Parar precisa alcançá-lo de fora.
_PARADA = threading.Event()
_EM_ANDAMENTO = threading.Lock()


def em_andamento() -> bool:
    """True enquanto um teste estiver rodando."""
    return _EM_ANDAMENTO.locked()


def cancelar() -> None:
    """Interrompe o teste em andamento (ligado ao botão Parar das interfaces)."""
    _PARADA.set()


def rodar(
    config: BotConfig,
    account: Account,
    on_status: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    """Executa a venda na janela JÁ ABERTA desta conta. Bloqueia até terminar.

    Devolve `{"ok": bool, "erro": str, "vendidos": int}`.

    Roda na thread de quem chamou -- no pywebview, cada chamada do frontend já
    vem em sua própria thread, então bloquear aqui não trava a interface.
    """
    log = logging.getLogger(f"blazes.{account.login or 'teste'}")

    if not _EM_ANDAMENTO.acquire(blocking=False):
        return {"ok": False, "erro": "Já existe um teste de venda rodando."}

    _PARADA.clear()
    # O supervisor não é INICIADO (a thread nunca roda): é usado só pelo que ele
    # já sabe fazer -- achar a janela desta conta entre os clientes abertos e
    # soltar a reivindicação depois. Reescrever essa busca aqui duplicaria a
    # regra de "qual janela é de quem", que é justamente onde dá para errar.
    supervisor = AccountSupervisor(config, account, on_status=on_status)
    ctx: BotContext | None = None
    try:
        log.info("=== TESTE DE VENDA (isolado) — procurando a janela do jogo ===")
        adotada = supervisor._adotar_janela_existente()
        if not adotada:
            return {"ok": False, "erro": (
                "Não encontrei a janela desta conta. Abra o jogo, entre com o "
                "personagem e deixe-o em Stone City antes de testar.")}

        pid, hwnd, ja_logado, personagem = adotada
        supervisor.pid, supervisor.hwnd = pid, hwnd
        if not ja_logado:
            return {"ok": False, "erro": (
                "O cliente encontrado está na tela de login. O teste de venda "
                "exige o personagem já dentro do jogo.")}

        ctx = BotContext(config=config, account=account, pid=pid, hwnd=hwnd,
                         stop_event=_PARADA)
        ctx.char_name = personagem
        if not ctx.memory.critical_ok():
            return {"ok": False, "erro": (
                "A memória do cliente não está legível (personagem ainda "
                "carregando?). Espere entrar no mundo e tente de novo.")}

        log.info("Teste de venda: '%s' em %s, posição %s | ouro %s",
                 personagem or account.login, ctx.memory.location(),
                 ctx.memory.position(), ctx.memory.gold())

        ouro_antes = ctx.memory.gold()
        vendor = VendorService(ctx)

        # NÃO se chama `voltar_para_a_cidade()`: o teste parte do princípio de
        # que o personagem JÁ está em Stone City, e usar o item de retorno
        # gastaria uma pedra (ou a recarga do token) à toa.
        if not vendor.travel_to_vendor():
            return {"ok": False, "erro": (
                f"Não cheguei ao vendedor. Estou em {ctx.memory.position()} "
                f"({ctx.memory.location()}). Confira a posição e o texto de "
                f"busca do vendedor na aba Bewitcher Cave.")}

        ctx.tick(0.2)
        vendidos = vendor.sell_from_slot()

        # `buy_supplies()` fica de fora de propósito: só compraria pedra de
        # retorno se o teste tivesse gasto uma, e ele não gasta.
        ouro_depois = ctx.memory.gold()
        if ouro_antes is not None and ouro_depois is not None:
            log.info("Teste de venda: ouro %s -> %s (%+d)",
                     ouro_antes, ouro_depois, ouro_depois - ouro_antes)
        log.info("=== TESTE DE VENDA CONCLUÍDO: %s item(ns) vendido(s) ===",
                 vendidos)
        return {"ok": True, "erro": "", "vendidos": vendidos}

    except StopRequested:
        log.info("Teste de venda interrompido pelo usuário.")
        return {"ok": False, "erro": "Teste interrompido."}
    except Exception as exc:
        log.exception("Teste de venda falhou: %s", exc)
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
    finally:
        if ctx is not None:
            ctx.close()
        # Devolve o PID: sem isso o bot de verdade acharia que a janela é de
        # outra conta e abriria um cliente novo (fila de três horas).
        supervisor._release()
        _PARADA.clear()
        _EM_ANDAMENTO.release()
