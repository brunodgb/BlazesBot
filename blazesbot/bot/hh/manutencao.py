"""O que a HH faz FORA da cave, entre uma run e a seguinte.

=========================================================================
POR QUE ISTO É UM MÓDULO
=========================================================================

São três decisões independentes que só têm em comum o MOMENTO -- depois de a
saída da cave ser confirmada, com a bolsa cheia e o personagem em segurança:

  * jogar o lixo fora (o que o NPC da HH não compra);
  * vender o resto;
  * decidir se a bolsa pede venda agora.

Nenhuma delas fala com a máquina de estados, e nenhuma precisa saber em que
trecho a run parou. Ficavam soltas em `HHRoutine` porque foram nascendo lá.

=========================================================================
A ORDEM É DELETAR E DEPOIS VENDER
=========================================================================

O lixo da HH não é comprado pelo NPC: levá-lo para a janela de venda gasta
cliques na grade em item que não sai, e ele volta ocupando o mesmo slot. Apagar
primeiro deixa a bolsa com só o que tem preço -- e a venda, que começa de um
slot configurado, passa a encontrar mercadoria onde antes achava lixo.
"""
from __future__ import annotations

from .. import deletador
from ..context import BotContext, StopRequested


class ManutencaoDaHH:
    """Descarte e venda entre runs. Recebe as peças; não as constrói."""

    def __init__(self, ctx: BotContext, vendedor) -> None:
        self.ctx = ctx
        self.vendedor = vendedor
        # Em que número de run foi a última venda. Zero = nunca vendeu nesta
        # sessão, e aí o teto por contagem já vale na primeira volta.
        self.runs_na_ultima_venda = 0
        # A limpa de bolsa DESTA LARGADA já aconteceu? Zerada por
        # `a_hh_comecou`, a cada vez que o farm da HH é ligado.
        self.ja_limpei_ao_comecar = False

    # ==================================================================
    # A decisão
    # ==================================================================

    def precisa_vender(self) -> bool:
        """A bolsa está cheia, ou já passaram runs demais desde a última venda?

        DUAS FONTES, e a segunda é rede: a leitura de bolsa pode falhar, e um
        teto por contagem de runs garante que a venda acontece de qualquer jeito.
        """
        ctx = self.ctx
        # `precisa_vender` devolve False quando a contagem não pôde ser lida --
        # vender sem saber quantos itens existem levaria o bot a viajar sem
        # motivo e a clicar na grade de uma janela talvez vazia.
        if ctx.settings.bags.precisa_vender(ctx.memory.bag_count()):
            return True

        desde = ctx.stats.runs - self.runs_na_ultima_venda
        return desde >= ctx.settings.hh.vendor.runs_before_selling

    def anotar_a_venda(self) -> None:
        """Marca que a venda aconteceu nesta run."""
        self.runs_na_ultima_venda = self.ctx.stats.runs

    # ==================================================================
    # O descarte
    # ==================================================================

    def descartar_o_lixo(self) -> int:
        """Apaga da bolsa o lixo que o NPC da HH não compra.

        =================================================================
        DUAS TRAVAS, E AS DUAS SÃO DELIBERADAS
        =================================================================

        A FLAG DA CONTA (`hh.deletar_lixo`) nasce DESLIGADA. Apagar é
        irreversível, e o usuário disse em 08/09/2026 que pode não querer --
        *"o usuário pode não querer jogar os itens fora, apenas vender os itens
        vendíveis na loja"*. Ligar é ato explícito de quem já conferiu o que
        tem naquela pasta.

        A PASTA É SÓ DA HH (`deletador.PASTA_DO_LIXO_DA_HH`). A lista global
        (`deletar/`) serve o APP e a BC, e o que é lixo numa cave é mercadoria
        na outra -- uma lista só apagaria em todo lugar.

        NUNCA DERRUBA A RUN. `limpar_a_bolsa` não levanta e tem teto próprio;
        aqui o `except` cobre o resto, porque perder a run por causa de uma
        limpeza de bolsa seria trocar o certo pelo acessório.
        """
        ctx = self.ctx
        if not ctx.settings.hh.deletar_lixo:
            return 0

        tecla = ctx.settings.keys.inventory
        if not tecla:
            ctx.log.warning(
                "HH: descarte de lixo ligado, mas a tecla do inventário está "
                "vazia. Sem ela não há bolsa para abrir.")
            return 0

        try:
            apagados = deletador.limpar_a_bolsa(
                ctx, tecla, pasta=deletador.PASTA_DO_LIXO_DA_HH)
        except StopRequested:
            raise
        except Exception as exc:
            ctx.log.warning("HH: descarte de lixo falhou (segue a run): %s", exc)
            return 0

        ctx.log.info("HH: %s item(ns) de lixo apagado(s) da pasta %s",
                     apagados, deletador.PASTA_DO_LIXO_DA_HH.name)
        return apagados or 0

    def a_hh_comecou(self) -> None:
        """O farm da HH foi LIGADO. A limpa da largada volta a valer.

        POR QUE ISSO PRECISA DE UM GESTO EXPLÍCITO: a rotina da HH é criada uma
        vez e GUARDADA pelo supervisor (`_rotina_da_hh`), porque o estado dela
        diz em que trecho a run está. Ela sobrevive a desligar e ligar o farm --
        e com ela sobrevivia a memória de que a limpa já tinha acontecido.

        Medido pelo usuário em 08/09/2026: *"estou testando desativar HH e
        ativar de volta para ver se esta limpando corretamente o inventario com
        o delete, mas nao esta executando sempre"*. A primeira largada limpava;
        as seguintes, não.
        """
        self.ja_limpei_ao_comecar = False

    def descartar_o_lixo_ao_comecar(self) -> int:
        """A limpa da LARGADA, na porta da cave. Uma vez por largada.

        Regra do usuário, 08/09/2026: *"quando começa o bot, ao chegar na
        posição de entrar em HH voce faz a primeira limpa, para caso o usuario
        ja esteja com o inventario cheio"*, e no mesmo dia: *"ajusta para
        sempre que eu der inicio ao bot HH ele abrir o inventario e tentar
        fazer a limpa"*.

        POR QUE NA PORTA E NÃO DENTRO. Bolsa cheia na largada não é lixo desta
        run -- é o que estava lá antes de o bot abrir, e pode ser o suficiente
        para a run inteira não ter onde guardar drop. Limpar já dentro da cave
        seria descobrir o problema depois de ele custar.

        UMA VEZ POR LARGADA, e não por run: o descarte de cada run acontece na
        `MANUTENCAO`, logo depois de sair. Repetir aqui abriria a bolsa de novo
        a cada volta para nada.

        A memória é do objeto e morre com o bot -- o usuário pediu assim em
        04/09/2026: *"não precisa ser persistente, só verificar enquanto esta
        com o bot aberto"*. Quem a zera a cada largada é `a_hh_comecou`.
        """
        if self.ja_limpei_ao_comecar:
            return 0
        self.ja_limpei_ao_comecar = True
        self.ctx.log.info("HH: primeira limpa da bolsa antes de entrar.")
        return self.descartar_o_lixo()

    # ==================================================================
    # A venda
    # ==================================================================

    def vender(self) -> int:
        """A venda no `Roaming Apothecary`, do lado de fora da cave."""
        ctx = self.ctx
        ctx.log.info("HH: indo vender no %s", self.vendedor.NOME_DO_VENDEDOR)
        vendidos = self.vendedor.vender()
        ctx.log.info("HH: %s slot(s) vendido(s)", vendidos)
        return vendidos


__all__ = ["ManutencaoDaHH"]
