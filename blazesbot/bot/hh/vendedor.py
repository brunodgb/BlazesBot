"""O vendedor da HH: o `Roaming Apothecary`, do lado de fora da cave.

A JANELA DE VENDA mora em `bot/vendedor.py` e é a mesma do jogo inteiro --
confirmado nas capturas de 01/09/2026: mesma moldura, mesma grade, mesma
paginação 1/3, mesmo par Sell/Cancel do Rich Man de Stone City.

O QUE A HH NÃO PRECISA, e a BC precisa: viagem. O Rich Man fica em Stone City, e
a rotina da BC gasta uma pedra de retorno ou a recarga do token de guilda para
chegar nele. O `Roaming Apothecary` fica a poucos passos da porta da HH -- o
painel de arredores encontra e o pathfinding do jogo caminha.

Diferença contra o bot em Lua, que também vende aqui: `farmer.sellItems()` dá
**30 cliques fixos** num slot literal (448,327), 100 ms entre eles, sem saber se
vendeu alguma coisa -- e antes disso navega por 5 cliques cegos de diálogo. Aqui
cada clique é seguido de uma leitura do slot. Ver `bot/vendedor.py`.
"""
from __future__ import annotations

from ..context import BotContext
from ..navegacao import Navigator
from ..vendedor import JanelaDeVenda
from . import mapa_hh

# Teto da caminhada até o vendedor. Ele fica ao lado da porta; acima disto o
# painel de arredores levou o personagem para o lugar errado.
MAX_SEGUNDOS_ATE_O_VENDEDOR = 90.0


class VendedorDaHH(JanelaDeVenda):
    """A janela de venda de `bot/vendedor.py` mais o Roaming Apothecary."""

    NOME_DO_VENDEDOR = mapa_hh.NPC_VENDEDOR[1]

    def __init__(self, ctx: BotContext,
                 navigator: Navigator | None = None) -> None:
        super().__init__(ctx, navigator)

    def ir_ate_o_vendedor(self) -> bool:
        """Acha o vendedor pelo painel de arredores e caminha até ele.

        SEM VIAGEM E SEM ITEM DE RETORNO: ele está no mesmo lugar que a porta da
        cave. O painel resolve, e o pathfinding do jogo atravessa a geometria que
        um clique de minimapa não atravessa.
        """
        ctx = self.ctx
        ui = self._ui_do_jogo()
        busca, confirma = mapa_hh.NPC_VENDEDOR
        busca = ctx.settings.hh.route.vendor_search_text or busca

        ctx.log.info("HH: procurando o %s", confirma)
        with ui.trajeto_pelo_painel("vendedor da HH"):
            info = ui.buscar_npc(busca, confirmar=confirma)
            if info is None:
                return False
            return ui.ir_para_resultado(
                confirma, coords=info.get("coords"),
                max_seconds=MAX_SEGUNDOS_ATE_O_VENDEDOR
                * ctx.settings.time_factor)

    def vender(self) -> int:
        """Vai até o vendedor, abre a janela e vende. Devolve quantos slots foram.

        Devolve 0 quando não conseguiu chegar ou abrir -- e isso NÃO é exceção:
        a run seguinte tenta de novo, e a bolsa continua sendo o gatilho.
        """
        if not self.ir_ate_o_vendedor():
            self.ctx.log.warning("HH: não cheguei no %s", self.NOME_DO_VENDEDOR)
            return 0
        if not self._open_npc():
            self.ctx.log.warning("HH: não abri a janela de venda")
            return 0
        return self.sell_from_slot()
