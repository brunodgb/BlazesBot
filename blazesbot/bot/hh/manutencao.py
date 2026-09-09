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
        # ===================================================================
        # DUAS TRAVAS "UMA VEZ POR RUN", E ELAS EXISTEM POR CAUSA DE UM LAÇO
        # ===================================================================
        #
        # MEDIDO no log de 08/09/2026, 13:36: o bot ficou girando entre
        # `PREPARAR` e `MANUTENCAO` a cada ~2 s, apagando lixo e tentando
        # vender, sem sair do lugar, até o usuário desligar a HH:
        #
        #     manutencao  Limpeza da bolsa: 0 item(ns) deletado(s)
        #     manutencao  HH: não abri a janela de venda do Roaming Apothecary
        #     manutencao  HH: manutenção feita; próxima run
        #     preparar    HH: a bolsa pede venda antes de entrar
        #     manutencao  Limpeza da bolsa: 0 item(ns) deletado(s)
        #     ...
        #
        # A MECÂNICA DO LAÇO: `_do_preparar` manda ir vender quando a bolsa
        # pede; a `MANUTENCAO` tenta, não consegue (faltava o template do link),
        # e volta para `PREPARAR` -- que pergunta a mesma coisa e recebe a mesma
        # resposta. A bolsa continua cheia, então a condição nunca muda.
        #
        # Regra do usuário: *"o deletar não deve ficar tentando varias vezes,
        # apenas 1 vez"*. E a mesma disciplina vale para a ida ao vendedor: uma
        # tentativa por run. Se ela não resolveu, insistir no mesmo instante não
        # vai resolver -- e girar é pior que entrar com a bolsa cheia, porque
        # girando a conta não farma nada.
        #
        # A CHAVE É `stats.runs`, que sobe uma vez por run (`_saiu` chama
        # `end_run`). Não é contador novo: é o mesmo que a venda por contagem
        # de runs já usava. `-1` para a primeira passada de cada sessão valer.
        self.runs_na_ultima_limpeza = -1
        # A IDA AO VENDEDOR DA LARGADA já aconteceu? Zerada por `a_hh_comecou`.
        self.ja_vendi_ao_comecar = False
        # A limpa de bolsa DESTA LARGADA já aconteceu? Zerada por
        # `a_hh_comecou`, a cada vez que o farm da HH é ligado.
        self.ja_limpei_ao_comecar = False

    # ==================================================================
    # A decisão
    # ==================================================================

    def precisa_vender(self) -> bool:
        """Já passaram runs demais desde a última venda?

        =================================================================
        UMA FONTE SÓ, E A BOLSA NÃO É ELA
        =================================================================

        Regra do usuário, 09/09/2026: *"ignore a leitura de quantidade de itens
        no inventário, pois esse valor é instável e gera falhas"*.

        E O BC JÁ TINHA CHEGADO NESSA CONCLUSÃO -- `BCVendor` diz, desde antes
        da HH existir: *"o antigo gatilho por espaço livre da bolsa (folga) foi
        REMOVIDO: a leitura de itens da bolsa mostrou ser imprecisa e o bot
        nunca acionava a venda por esse caminho"*. A HH tinha reintroduzido o
        gatilho, e com ele o problema.

        A CONTAGEM DE ITENS CONTINUA SENDO LIDA -- para o LOG (`vendedor.py`
        mostra a bolsa antes e depois da venda) e para o painel de diagnóstico.
        O que ela deixou de fazer é DECIDIR. Medir e decidir são coisas
        diferentes, e é a segunda que uma leitura instável não pode fazer.

        Ver `docs/decisoes/venda.md`, "Os dois gatilhos da venda".
        """
        ctx = self.ctx
        desde = ctx.stats.runs - self.runs_na_ultima_venda
        return desde >= ctx.settings.hh.vendor.runs_before_selling

    def precisa_descartar(self) -> bool:
        """Ainda não apaguei lixo nesta run?

        DELETAR E VENDER SÃO COISAS DIFERENTES, e o usuário foi explícito:
        *"são coisas diferentes deletar e vender"*. O descarte apaga o que o
        NPC não compra; a venda troca por ouro o que ele compra. Um não
        substitui o outro, e um não deve ser repetido porque o outro falhou.
        """
        return self.ctx.stats.runs != self.runs_na_ultima_limpeza

    def anotar_o_descarte(self) -> None:
        """Marca que o lixo desta run já foi apagado."""
        self.runs_na_ultima_limpeza = self.ctx.stats.runs

    def vender_ao_comecar(self) -> int:
        """A venda da LARGADA, na porta da cave. Uma vez por largada.

        =================================================================
        AQUI, E NÃO NO `PREPARAR`
        =================================================================

        Regra do usuário, 09/09/2026: *"ao iniciar a rotina de HH, o bot deve se
        deslocar até a coordenada próxima estipulada e executar a venda. Isso
        deve ocorrer obrigatoriamente antes de iniciar o loop de tentativas de
        entrada na instância"*.

        E É O ÚNICO LUGAR EM QUE ELA FUNCIONA: `PONTO_DA_VENDA` **é** o
        `PONTO_DA_ENTRADA` -- a mesma coordenada (-342,-288), com o vendedor
        logo abaixo do personagem e o NPC da cave acima, na escada. A venda
        precisa que o personagem esteja ALI, e quem o leva até lá é o
        `ATE_A_PORTA`. Chamada no `PREPARAR`, como estava em 08/09/2026, ela
        tentava encostar num ponto a centenas de unidades de distância.

        DIRETA, e não pelo estado `MANUTENCAO`: mandar o estado para lá e voltar
        criaria o vai-e-volta que já custou um laço (ver §22). Aqui o gesto é
        chamado e pronto -- o personagem já está no lugar certo.
        """
        if self.ja_vendi_ao_comecar:
            return 0
        self.ja_vendi_ao_comecar = True
        self.ctx.log.info(
            "HH: venda da largada, antes de tentar entrar -- a bolsa pode "
            "estar cheia de antes de o bot abrir.")
        vendidos = self.vender()
        # A COTA DE RUNS RECOMEÇA DAQUI quando a venda pôde acontecer. Impedida,
        # não conta -- ver `a_venda_esta_impedida`.
        if not self.a_venda_esta_impedida:
            self.anotar_a_venda()
        return vendidos

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
        self.ja_vendi_ao_comecar = False

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

    @property
    def a_venda_esta_impedida(self) -> bool:
        """A última venda não pôde nem ser TENTADA.

        =================================================================
        "VENDEU ZERO" E "NÃO PUDE VENDER" SÃO ESTADOS DIFERENTES
        =================================================================

        Medido no log de 08/09/2026, depois de o usuário pôr `1 run` para
        testar:

            HH: indo vender no Roaming Apothecary
            HH: não tenho o template do link de vender (link_sell_item.png)
            HH: não abri a janela de venda do Roaming Apothecary
            HH: 0 slot(s) vendido(s)
            HH: manutenção feita; próxima run

        A decisão de vender estava CERTA -- ela disparou nas três runs
        seguintes à mudança. O que faltava era o PNG do link.

        E aí vem o defeito que isto conserta: `anotar_a_venda` era chamada de
        qualquer forma, então a run passava a contar como "vendeu". Com o
        padrão de 5 runs, a tentativa seguinte só voltaria 5 runs depois -- e o
        log daria a impressão de que a venda estava acontecendo.
        """
        return bool(getattr(self.vendedor, "faltou_o_template", False))


__all__ = ["ManutencaoDaHH"]
