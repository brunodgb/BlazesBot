"""O vendedor da Bewitcher Cave: o Rich Man, em Stone City.

A JANELA DE VENDA mora em `bot/vendedor.py` e serve os dois ecossistemas -- ela é
a mesma no jogo inteiro. Aqui fica o que é DESTA rota:

    como VOLTAR para a cidade    pedra de retorno ou token de guilda
    quem é o vendedor            o Rich Man, achado pelo painel de arredores
    o que comprar                os suprimentos que a run da BC consome
    quando ir                    `precisa_ir_vender`, pela bolsa

A HH não precisa de nada disso: o `Roaming Apothecary` fica do lado de fora da
cave, a poucos passos da porta.

**A CLASSE CONTINUA SE CHAMANDO `VendorService`** para quem importa daqui: a
rotina da BC e os testes já falam essa língua.
"""
from __future__ import annotations

import time

from ...core import diario
from ...core.vision import capture_window, find_template, frame_is_blank
from ..context import Disconnected
from ..vendedor import (
    CICLOS_DE_VENDA,
    ESPERA_ENTRE_TENTATIVAS_DE_RETORNO,
    LIMIAR_DO_VENDEDOR,
    RAIO_DA_BUSCA_DO_VENDEDOR,
    RECARGA_GUILD_TOKEN,
    SEGUNDOS_POR_TENTATIVA_NO_VENDEDOR,
    TEMPLATE_VENDEDOR,
    TENTATIVAS_DA_PEDRA,
    TENTATIVAS_DE_ENCOSTAR_NO_VENDEDOR,
    TENTATIVAS_DO_TOKEN,
    TOLERANCIA_DA_CAMINHADA_ATE_O_VENDEDOR,
    JanelaDeVenda,
)


class VendorBC(JanelaDeVenda):
    """A janela de venda de `bot/vendedor.py` mais o Rich Man."""

    NOME_DO_VENDEDOR = "Rich Man"

    def __init__(self, ctx, navigator=None) -> None:
        """O navegador nasce com o MAPA DA BEWITCHER CAVE quando não vem pronto.

        Sem isto, quem constrói sem passar o navegador (a ferramenta "Testar
        Venda", por exemplo) recebia um navegador SEM MAPA -- e a tolerância dos
        waypoints problemáticos da cave sumia em silêncio.

        Não é o chamador que tem de lembrar: é o ecossistema que sabe o mapa
        dele. Mesmo princípio de um ecossistema funcionar sozinho.
        """
        from ..navegacao import Navigator
        from . import mapa_bc

        super().__init__(ctx, navigator or Navigator(ctx, mapa_bc))

    def _ui_do_jogo(self):
        """A UI da BC, e não a genérica: a venda inicial acontece em Stone City,
        de onde a rotina também pode precisar viajar para a cave."""
        from .ui_service import UIService

        return UIService(self.ctx, self.nav)

    @property
    def guild_token_disponivel(self) -> bool:
        if not self.ctx.settings.keys.guild_token:
            return False
        if not self._guild_token_usado_em:
            return True
        return (time.time() - self._guild_token_usado_em) >= RECARGA_GUILD_TOKEN

    @property
    def minutos_de_recarga_do_token(self) -> float:
        if not self._guild_token_usado_em:
            return 0.0
        falta = RECARGA_GUILD_TOKEN - (time.time() - self._guild_token_usado_em)
        return max(0.0, falta) / 60.0

    def voltar_para_a_cidade(self) -> bool:
        """Teleporta para Stone City. Guild Token primeiro, pedra depois.

        Os dois são ITENS, e item exige estar A PÉ: montado o jogo simplesmente
        ignora a tecla, sem avisar. Era assim que o bot "usava" a pedra e
        continuava no mesmo lugar.

        Não confundir com o teleporte por NPC (Transport Fay), que funciona montado
        -- ali é diálogo, não item.
        """
        ctx = self.ctx
        k = ctx.settings.keys

        from . import mapa_bc

        if not self.nav.ensure_dismounted(timeout=6.0):
            ctx.log.warning("Não desmontei; o item de retorno seria ignorado")

        if not k.guild_token and not k.stone_charm:
            ctx.log.warning(
                "Nenhuma tecla de retorno configurada (Guild Token nem pedra); "
                "não há como chegar a Stone City.")
            return False

        # =================================================================
        # O DESTINO É CONFERIDO, NÃO PRESUMIDO
        # =================================================================
        #
        # A versão anterior confirmava o teleporte pelo SALTO DE POSIÇÃO e
        # devolvia True para qualquer salto -- inclusive um que caísse em outro
        # lugar. E o retorno era IGNORADO pelo chamador (`self.voltar_para_a_
        # cidade()` sem `if`). Fora de Stone City o `travel_to_vendor` procurava
        # o Rich pelo painel de arredores, não achava, e o personagem ficava
        # andando em laço -- o sintoma relatado em 18/08/2026.
        #
        # Agora quem decide é `mapa_bc.esta_em_stone_city`, conferida DEPOIS DE
        # CADA USO do item.
        #
        # RESSALVA REGISTRADA A PEDIDO: essa função é COORDENADA **OU** NOME, e
        # o nome é a leitura com oito episódios de travamento registrados em
        # `bot/bc/localizacao.py` (o cliente às vezes não reescreve o campo ao
        # sair da instância). Reutilizá-la aqui foi decisão do usuário, e é
        # defensável -- o teleporte é troca de mapa de verdade, que é justamente
        # o que reescreve o campo. Mas se o laço voltar, é o PRIMEIRO lugar a
        # olhar.
        def chegou() -> bool:
            pos = ctx.memory.position()
            nome = ctx.memory.location()
            if mapa_bc.esta_em_stone_city(pos, nome):
                ctx.log.info("Cheguei em Stone City (posição %s, nome %r)",
                             pos, nome)
                return True
            return False

        if chegou():
            return True

        # Token PRIMEIRO e SEM consultar a recarga interna. Decisão do usuário:
        # "não deve esperar pois às vezes pode ter ocorrido uma falha na
        # contagem". Apertar na recarga não faz nada além de gastar o tempo da
        # tentativa, e o item não é consumido -- então tentar é barato.
        tentativas = []
        if k.guild_token:
            tentativas += [("Guild Token", k.guild_token)] * TENTATIVAS_DO_TOKEN
        if k.stone_charm:
            tentativas += [("pedra de retorno", k.stone_charm)] * TENTATIVAS_DA_PEDRA

        usou_a_pedra = False
        for numero, (nome_do_item, tecla) in enumerate(tentativas, 1):
            ctx.raise_if_stopped()
            if nome_do_item == "Guild Token":
                self._guild_token_usado_em = time.time()
            else:
                self._pedras_gastas += 1
                usou_a_pedra = True
            ctx.log.info("Retorno %s/%s: usando o %s",
                         numero, len(tentativas), nome_do_item)
            ctx.press(tecla)
            ctx.tick(ESPERA_ENTRE_TENTATIVAS_DE_RETORNO)
            if chegou():
                return True

        # =================================================================
        # A PEDRA FALHOU ⇒ É DIAGNÓSTICO, NÃO AZAR
        # =================================================================
        #
        # Palavra do usuário: a pedra NÃO tem recarga e é garantida, basta ter
        # sido comprada. Então usá-la e não chegar em Stone City só tem duas
        # explicações -- estoque zerado ou TECLA CONFIGURADA ERRADA --, e as duas
        # exigem intervenção. Repetir em silêncio esconderia um erro de
        # configuração.
        pos, nome = ctx.memory.position(), ctx.memory.location()
        if usou_a_pedra:
            ctx.log.error(
                "Usei a pedra de retorno %s vez(es) e NÃO cheguei em Stone City "
                "(posição %s, nome %r). A pedra não tem recarga: provável TECLA "
                "DE RETORNO CONFIGURADA ERRADA, ou estoque zerado. Confira a aba "
                "Teclas desta conta.", TENTATIVAS_DA_PEDRA, pos, nome)
        else:
            ctx.log.error(
                "Esgotei as %s tentativas de retorno e não cheguei em Stone City "
                "(posição %s, nome %r).", len(tentativas), pos, nome)
        diario.registrar_evento(
            ctx.account_login, "acao-sem-efeito",
            f"retorno para Stone City falhou em {len(tentativas)} tentativas"
            + ("; pedra usada (suspeita de tecla errada)" if usou_a_pedra else ""),
            pos, nome,
        )
        return False

    # ==================================================================
    # Deslocamento até o NPC
    # ==================================================================

    def travel_to_vendor(self) -> bool:
        """Vai até o NPC vendedor e para EXATAMENTE no ponto medido.

        Confirmar a posição por memória antes de interagir é essencial: clicar no
        NPC sem estar no lugar certo abre outra janela (ou nada), e a partir daí
        toda a sequência de cliques cai no vazio. Pior: um clique que cai no chão
        faz o personagem ANDAR, afastando-o ainda mais.

        DUAS ETAPAS, e a segunda é nova. O painel de arredores caminha até perto
        (ele aceita folga por construção), e depois o último passo é dado com a
        precisão exata -- mesmo desenho do patamar do Altar Stone, e pelo mesmo
        motivo: as coordenadas de tela do NPC foram medidas COM o personagem no
        ponto, e alguns passos de distância giram o NPC na tela.
        """
        from . import mapa_bc

        ctx = self.ctx

        # =============================================================
        # PORTÃO DE LOCAL: o Rich só existe em Stone City
        # =============================================================
        #
        # Sem isto, fora da cidade o painel de arredores é aberto, o filtro por
        # "Rich" não acha nada, e o personagem fica ANDANDO EM LAÇO -- o sintoma
        # relatado em 18/08/2026. E o laço era pago 10 vezes, uma por ciclo de
        # venda.
        #
        # O portão fica AQUI e não no `run_maintenance` para os TRÊS chamadores
        # ganharem a proteção: a manutenção, o "vender ao iniciar em Stone City"
        # e o botão TEMPORÁRIO "Testar Venda" -- que hoje também entraria no laço
        # se fosse rodado fora da cidade.
        #
        # A divisão de responsabilidade que isso cria: `voltar_para_a_cidade`
        # cuida de CHEGAR, e esta função de NÃO TENTAR de onde não dá.
        pos = ctx.memory.position()
        nome = ctx.memory.location()
        if not mapa_bc.esta_em_stone_city(pos, nome):
            ctx.log.warning(
                "Não estou em Stone City (posição %s, nome %r); o Rich não "
                "existe aqui e procurá-lo pelo painel de arredores só faria o "
                "personagem andar em laço. Recusando a ida ao vendedor.",
                pos, nome)
            return False
        st = ctx.settings.vendor
        alvo = tuple(st.vendor_position)

        ctx.log.info("Indo ao vendedor em %s", alvo)
        self.nav.travel_via_surroundings(
            st.vendor_search_text, expected=alvo,
            tolerance=TOLERANCIA_DA_CAMINHADA_ATE_O_VENDEDOR)

        # Último passo, apertado. Já estando no ponto, o `goto` devolve na hora.
        precisao = mapa_bc.PRECISAO_NO_PONTO_DO_VENDEDOR
        for _ in range(TENTATIVAS_DE_ENCOSTAR_NO_VENDEDOR):
            ctx.raise_if_stopped()
            if self._no_ponto_do_vendedor():
                return True
            self.nav.goto(alvo, tolerance=precisao,
                          max_seconds=SEGUNDOS_POR_TENTATIVA_NO_VENDEDOR,
                          usar_mapa=False)

        ctx.log.warning(
            "Não consegui parar exatamente em %s (estou em %s). NÃO vou clicar "
            "no NPC de fora do ponto: o clique cairia no chão e o personagem "
            "andaria, piorando a tentativa seguinte.",
            alvo, ctx.memory.position())
        return False

    def _no_ponto_do_vendedor(self) -> bool:
        """A LEITURA de posição diz que está no ponto exato do vendedor?

        Um número só para andar e para conferir (`mapa_bc`). Dois números
        escolhidos à parte foi o que travou a run no incidente da tolerância 3:
        um lado dizia "cheguei" e o outro "longe demais", sobre o mesmo instante.
        """
        from . import mapa_bc

        atual = self.ctx.memory.position()
        if atual is None:
            # Sem leitura não há o que conferir, e recusar aqui travaria a venda
            # num laço sem saída. Segue e deixa o diálogo decidir.
            return True
        return (mapa_bc.distancia(atual, tuple(self.ctx.settings.vendor.vendor_position))
                <= mapa_bc.PRECISAO_NO_PONTO_DO_VENDEDOR)

    def _onde_clicar_no_vendedor(self) -> tuple[int, int]:
        """Onde está o Rich na tela. Cai na coordenada fixa se não achar.

        POR QUE PROCURAR EM VEZ DE DECORAR: ver `TEMPLATE_VENDEDOR` no topo. O
        resumo é que cinco unidades de mundo moveram o NPC quase 300 px na tela,
        e a tolerância de parada permite uma fração disso -- suficiente para o
        clique direito errar o Rich e cair na cena 3D.

        NUNCA DEVOLVE `None`: sem template, sem captura ou sem casamento, devolve
        a coordenada de sempre. O caminho novo só pode melhorar a mira; se ele
        não responder, o comportamento é exatamente o de antes.
        """
        ctx = self.ctx
        reserva = ctx.coords.vendor_npc

        template = ctx.templates.load(TEMPLATE_VENDEDOR)
        if template is None:
            ctx.log.debug("Template %s não encontrado; clico na coordenada fixa",
                          TEMPLATE_VENDEDOR)
            return reserva

        quadro = capture_window(ctx.hwnd)
        if quadro is None or frame_is_blank(quadro):
            return reserva

        altura, largura = quadro.shape[:2]
        raio = RAIO_DA_BUSCA_DO_VENDEDOR
        x0 = max(0, reserva[0] - raio)
        y0 = max(0, reserva[1] - raio)
        regiao = (x0, y0,
                  min(largura - x0, raio * 2), min(altura - y0, raio * 2))

        achado = find_template(quadro, template,
                               threshold=LIMIAR_DO_VENDEDOR, region=regiao)
        if achado is None:
            ctx.log.info("Não achei o Rich na tela; clico na coordenada fixa %s",
                         reserva)
            return reserva

        ctx.log.info("Rich achado em %s (a coordenada fixa é %s, %s px de "
                     "diferença)", achado, reserva,
                     round(((achado[0] - reserva[0]) ** 2
                            + (achado[1] - reserva[1]) ** 2) ** 0.5))
        return achado

    # ==================================================================
    # Venda
    # ==================================================================

    def buy_supplies(self) -> bool:
        """Compra a Pedra de Retorno gasta, no mesmo NPC da venda.

        Compra SÓ o que foi gasto: usou uma, compra uma. Sem pedra gasta não há
        nada a comprar, e abrir a aba de compra por nada custaria cliques.

        POÇÃO DE HP NÃO É COMPRADA PELO BOT, de propósito. Poções têm níveis, e
        cada cidade vende só até um certo nível -- comprar automaticamente traria
        a poção fraca da cidade onde o bot estiver, que cura menos. Quem joga
        abastece com a poção do nível que quiser, e a proteção dos slots iniciais
        na venda existe justamente para que essas poções não sejam vendidas por
        engano.

        Poção de mana também não: o pet gera regeneração suficiente.
        """
        ctx = self.ctx
        cfg = ctx.settings.vendor
        if not cfg.buy_return_charm:
            return True
        if self._pedras_gastas <= 0:
            ctx.log.debug("Nenhuma pedra de retorno gasta; nada a comprar")
            return True

        quantidade = self._pedras_gastas
        ctx.log.info("Comprando %s pedra(s) de retorno (uma por uso)", quantidade)
        if not self._open_npc():
            return False

        ctx.click(ctx.coords.vendor_purchase_tab)
        ctx.tick(0.4)
        ctx.click(ctx.coords.vendor_buy_slot)
        ctx.tick(0.25)
        for _ in range(quantidade * max(1, cfg.buy_quantity_clicks)):
            ctx.raise_if_stopped()
            ctx.click(ctx.coords.vendor_buy_button)
            ctx.tick(0.3)
            self._dismiss_confirm()

        self._pedras_gastas = 0
        ctx.click(ctx.coords.npc_leave)
        ctx.tick(0.35)
        return True

    # ==================================================================
    # Ciclo completo
    # ==================================================================

    def precisa_ir_vender(self) -> str | None:
        """Vale a viagem até a cidade? Devolve o motivo, ou None.

        DESATIVADO. O gatilho original lia a quantidade de itens na bolsa
        (`bag_count`) e comparava com a folga configurada (`BagConfig`); essa
        leitura se mostrou IMPRECISA, então o bot nunca entrava na venda por
        esse caminho. O gatilho atual é por contagem de runs
        (`BCVendor.runs_before_selling`), decidido em
        `BossRushRoutine._seguir_depois_de_sair` -- não aqui.
        """
        # GATILHO ANTIGO, DESATIVADO (leitura de bolsa imprecisa):
        # ctx = self.ctx
        # bolsas = ctx.settings.bags
        # itens = ctx.memory.bag_count()
        # if bolsas.precisa_vender(itens):
        #     livre = bolsas.espaco_livre(itens)
        #     return (f"só {livre} espaço(s) livre(s) de {bolsas.capacidade} "
        #             f"({itens} itens) — abaixo da folga de {bolsas.folga_minima}")
        return None

    def run_maintenance(self) -> bool:
        """Ida completa à cidade: teleportar, viajar, vender, comprar."""
        ctx = self.ctx
        state = ctx.snapshot()
        if not state.alive:
            raise Disconnected("memória ilegível antes da manutenção")

        # Sem tecla de retorno configurada (nem Guild Token, nem pedra) não há
        # como voltar da cave para a cidade -- e sem voltar, não há venda. Em
        # vez de insistir, para a conta: desliga o BC farm dela (a interface
        # desmarca o checkbox) e encerra a execução.
        k = ctx.settings.keys
        if not k.guild_token and not k.stone_charm:
            ctx.account.bc_farm = False
            try:
                ctx.config.save()
            except Exception as exc:
                ctx.log.warning("Não consegui salvar a configuração: %s", exc)
            ctx.log.warning(
                "Venda cancelada: Guild Token e Pedra de Retorno sem tecla "
                "configurada. Não dá para voltar à cidade. Desligando o BC "
                "farm desta conta."
            )
            return False

        gold_before = ctx.memory.gold()
        itens_antes = state.bag_count

        # Teleporte para a cidade. Se não der, ainda vale tentar chegar pelo
        # painel de arredores -- o vendedor tem nome e o painel caminha até ele.
        # O RETORNO PASSA A SER CONFERIDO. Antes era `self.voltar_para_a_cidade()`
        # sem `if`: qualquer salto de posição contava como chegada, e fora de
        # Stone City os 10 ciclos abaixo viravam 10 voltas de laço.
        if not self.voltar_para_a_cidade():
            ctx.log.error(
                "Não cheguei em Stone City; não há como vender daqui. Quem "
                "chamou decide se roda mais uma run de BC e tenta de novo.")
            return False

        # ================================================================
        # INSISTIR ATÉ VENDER
        # ================================================================
        #
        # Não vender não pode ser um desfecho silencioso: a bolsa enche, o bot
        # trava e o usuário perde item. Então são até `CICLOS_DE_VENDA` ciclos
        # completos -- reposicionar, abrir o diálogo, vender --, e cada ciclo já
        # traz as próprias repetições por dentro (o ajuste no ponto tenta 6
        # vezes, o abrir-diálogo tenta 4).
        vendeu = False
        for ciclo in range(1, CICLOS_DE_VENDA + 1):
            ctx.raise_if_stopped()
            if not self.travel_to_vendor():
                ctx.log.warning("Ciclo %s/%s: não parei no ponto do vendedor",
                                ciclo, CICLOS_DE_VENDA)
                continue

            # NÃO desmonta para vender. Interação com NPC -- abrir diálogo,
            # vender, comprar -- funciona montado; só ITEM e SKILL exigem estar a
            # pé. A desmontagem que havia aqui era gasto puro: custava o tempo de
            # descer e obrigava o portão da montaria a remontar em seguida, para
            # o trajeto de volta à cave.
            ctx.tick(0.2)

            vendidos = self.sell_from_slot()
            if vendidos > 0 or not itens_antes:
                vendeu = True
                break
            # Bolsa tinha itens mas a venda não produziu nenhum: a janela de
            # venda provavelmente não abriu. Insiste no próximo ciclo em vez de
            # seguir para a cave com a bolsa cheia.
            ctx.log.warning(
                "Ciclo %s/%s: bolsa com %s item(ns) mas 0 foram vendidos "
                "(janela de venda não abriu). Insistindo.",
                ciclo, CICLOS_DE_VENDA, itens_antes)
            ctx.tick(0.5)

        if not vendeu:
            # Dez ciclos sem conseguir sequer começar a vender. DESLIGA o BC farm
            # desta conta e salva: a conta fica online, logada, com o relogin
            # ativo, e o checkbox desmarca na interface -- que é o sinal
            # de que precisa de você. Não fecha o cliente, não para o bot inteiro,
            # e não volta a tentar vender (sem o farm, a rotina não roda).
            ctx.account.bc_farm = False
            try:
                ctx.config.save()
            except Exception as exc:
                ctx.log.warning("Não consegui salvar a configuração: %s", exc)
            ctx.log.error(
                "Não consegui vender em %s ciclos. Desligando o BC farm desta "
                "conta -- ela fica online com o relogin ativo. Com a bolsa "
                "cheia, seguir farmando faria perder item.", CICLOS_DE_VENDA)
            diario.registrar_evento(
                ctx.account_login, "venda-falhou",
                f"{CICLOS_DE_VENDA} ciclos sem vender; BC farm desligado",
                ctx.memory.position(), ctx.memory.location(),
            )
            return False

        self.buy_supplies()

        gold_after = ctx.memory.gold()
        if gold_before is not None and gold_after is not None:
            delta = gold_after - gold_before
            ctx.log.info("Saldo após manutenção: %s (variação %+d)",
                         gold_after, delta)
        ctx.log.info("Bolsa: %s -> %s item(ns) | capacidade %s",
                     itens_antes, ctx.memory.bag_count(),
                     ctx.settings.bags.capacidade)
        return True


# O nome pelo qual a rotina e os testes da BC já conhecem a peça.
VendorService = VendorBC
