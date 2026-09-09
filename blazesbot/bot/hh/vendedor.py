"""O vendedor da HH: o `Roaming Apothecary`, do lado de fora da cave.

=========================================================================
A JANELA DE VENDA É A MESMA DO JOGO INTEIRO
=========================================================================

`bot/vendedor.py` opera a janela; confirmado nas capturas de 01 a 03/09/2026:
mesma moldura, mesma grade, mesma paginação 1/3, mesmo par Sell/Cancel do Rich
Man de Stone City. Então aqui só ficam os NOMES e o CAMINHO.

=========================================================================
E O CAMINHO É MAIS CURTO QUE O DA BC -- SÃO SEIS PASSOS
=========================================================================

O Rich Man fica em Stone City, e a rotina da BC gasta uma pedra de retorno ou a
recarga do token de guilda para chegar nele. O `Roaming Apothecary` fica A SEIS
UNIDADES da porta da HH: vende-se parado em `mapa_hh.PONTO_DA_VENDA`
(-343,-294), e entra-se de `PONTO_DA_ENTRADA` (-342,-288), logo acima, na
escada. Medido pelo usuário em 09/09/2026 -- ver `docs/decisoes/hh.md` §29.

Então **não há painel de arredores, não há busca e não há viagem**: uns passos
e um clique direito na coordenada medida abrem o diálogo. Quem anda esses
passos é `encostar_no_ponto_da_venda`, e quem VOLTA para a entrada depois é
`HHRoutine._vender_e_limpar_na_largada` -- a entrada recusa o clique de fora do
ponto dela.

O PREÇO DISSO é que o clique é POSICIONAL na cena 3D: ele só vale a partir
daquela coordenada. Por isso `_no_ponto_do_vendedor` confere a posição ANTES --
de fora do ponto o clique cai no chão, e clique no chão faz o personagem ANDAR,
tirando-o justamente do lugar de onde os cliques funcionam.

=========================================================================
CONTRA O BOT EM LUA
=========================================================================

`farmer.sellItems()` anda até o vendedor por um clique de minimapa, espera a
posição num laço de 1 s, e então dá **30 cliques fixos** num slot literal
(448,327) com 100 ms entre eles -- sem saber se vendeu alguma coisa, e sem saber
se a janela abriu. Aqui cada clique de slot é seguido de uma leitura, e a
abertura da janela é confirmada pela âncora. Ver `bot/vendedor.py`.
"""
from __future__ import annotations

from ...core.vision import capture_window, find_template
from ..context import BotContext
from ..navegacao import Navigator
from ..ui_do_jogo import ANCHOR_THRESHOLD
from ..vendedor import JanelaDeVenda
from . import mapa_hh

# O link "Sell Item" dentro do diálogo do vendedor, achado por IMAGEM.
#
# NÃO POR COORDENADA, e o motivo está medido em
# `JanelaDeVenda._onde_clicar_no_link_de_vender`: o ponto da Bewitcher Cave cai
# 35 px abaixo do link deste NPC, porque a posição dos links depende de quantas
# linhas de texto o NPC escreve antes deles.
#
# Enquanto o arquivo não existir, a venda RECUSA e diz no log o que recortar.
TEMPLATE_DO_LINK_DE_VENDER = "link_sell_item.png"


# Folga aceita para considerar que se está no ponto de clicar no vendedor.
#
# APERTADA, e pelo mesmo motivo de todo clique posicional deste projeto: alguns
# passos de distância giram o NPC na tela, o clique cai no chão e o personagem
# anda -- piorando a tentativa seguinte.
PRECISAO_NO_PONTO_DA_VENDA = 1.5

# Quantas vezes tentar encostar no ponto antes de desistir da venda.
TENTATIVAS_DE_ENCOSTAR = 4
SEGUNDOS_POR_TENTATIVA = 1.8


class VendedorDaHH(JanelaDeVenda):
    """A janela de venda de `bot/vendedor.py` mais o Roaming Apothecary."""

    NOME_DO_VENDEDOR = mapa_hh.NPC_VENDEDOR[1]

    def _config_da_venda(self):
        """O slot inicial e o teto de passadas SÃO OS DA HH, não os da BC.

        =================================================================
        ESTE GANCHO CONSERTA UMA VENDA QUE OBEDECIA A OUTRA CAVE
        =================================================================

        A base lia `ctx.settings.vendor`, e essa propriedade devolve
        `bc.vendor` SEMPRE (`AccountSettings.vendor`). As duas interfaces
        gravam `hh.vendor.sell_start_slot` desde que a HH existe, o usuário via
        o campo na tela -- e a venda da HH usava o número da Bewitcher Cave.

        MEDIDO em `data/config.json`, 09/09/2026: `gamerblazes` tem BC=1 e
        HH=3, então a venda da HH começaria no slot 1, que é EQUIPAMENTO.
        `creubo` (4 nos dois) escondia o defeito por coincidência.
        """
        return self.ctx.settings.hh.vendor

    def __init__(self, ctx: BotContext,
                 navigator: Navigator | None = None) -> None:
        # O navegador nasce com o MAPA DA HH quando não vem pronto -- ver o
        # construtor equivalente de `bc/vendor.py`.
        super().__init__(ctx, navigator or Navigator(ctx, mapa_hh))
        self._avisou_sem_template = False
        # A VENDA ESTÁ IMPEDIDA? (não "deu zero" -- IMPEDIDA de tentar.)
        #
        # Sem o template do link, o bot não chega nem a abrir a janela. Quem
        # decide se a venda conta como FEITA precisa saber a diferença: uma
        # venda que vendeu zero porque não havia nada vendável cumpriu o seu
        # papel; uma que não pôde nem tentar, não -- e marcá-la como feita
        # empurra a próxima tentativa para dentro de mais N runs.
        self.faltou_o_template = False

    # ==================================================================
    # Os três ganchos que a janela de venda pergunta
    # ==================================================================

    def _no_ponto_do_vendedor(self) -> bool:
        """Estou de onde o clique no vendedor funciona?

        SEM LEITURA DE POSIÇÃO DEVOLVE True: não há como conferir, e recusar
        aqui travaria a venda num laço sem saída. Quem decide então é o diálogo
        abrir ou não -- e `_tentar_abrir_a_venda` já confere isso pela âncora da
        janela.
        """
        atual = self.ctx.memory.position()
        if atual is None:
            return True
        return (mapa_hh.distancia(atual, mapa_hh.PONTO_DA_VENDA)
                <= PRECISAO_NO_PONTO_DA_VENDA)

    def _onde_clicar_no_vendedor(self) -> tuple[int, int]:
        """A coordenada MEDIDA do Roaming Apothecary.

        Não é o ponto genérico de NPC da cena: ele fica ABAIXO do personagem, e
        o genérico aponta para a frente. Ver `coords.hh_vendor_npc`.
        """
        return self.ctx.coords.hh_vendor_npc

    def _onde_clicar_no_link_de_vender(self) -> tuple[int, int] | None:
        """Acha o "Sell Item" por imagem. Ver o gancho na classe base.

        Devolve `None` quando o template não existe -- e aí a venda não
        acontece, o que é melhor que clicar num ponto que não é o link: a bolsa
        continua cheia e o log diz exatamente o que falta, em vez de a venda
        "não funcionar" sem motivo aparente.
        """
        ctx = self.ctx
        tpl = ctx.templates.load(TEMPLATE_DO_LINK_DE_VENDER)
        if tpl is None:
            self.faltou_o_template = True
            if not self._avisou_sem_template:
                self._avisou_sem_template = True
                ctx.log.error(
                    "HH: não tenho o template do link de vender (%s). Recorte o "
                    "texto \"Sell Item\" do diálogo do %s e salve em "
                    "data/templates/ com esse nome. NÃO vou clicar na "
                    "coordenada da Bewitcher Cave: ela cai 35 px abaixo deste "
                    "link, porque a posição depende do texto do NPC.",
                    TEMPLATE_DO_LINK_DE_VENDER, self.NOME_DO_VENDEDOR)
            return None

        # O TEMPLATE APARECEU: a marca cai, e o aviso volta a valer se ele
        # sumir. O usuário pode recortar o PNG com o bot rodando, e nesse caso a
        # venda tem que voltar a funcionar sem reiniciar nada.
        self.faltou_o_template = False
        self._avisou_sem_template = False

        quadro = capture_window(ctx.hwnd)
        if quadro is None:
            ctx.log.debug("HH: sem imagem para achar o link de vender")
            return None
        return find_template(quadro, tpl, threshold=ANCHOR_THRESHOLD)

    def ir_ate_o_vendedor(self) -> bool:
        """Encosta no ponto de venda. Sem viagem: ele fica na porta da cave.

        A CÂMERA VAI NA POSE PADRÃO ANTES, e é a mesma exigência da BC: o clique
        é posicional na cena 3D, e com a câmera fora do padrão ele cai no chão
        por mais que a coordenada esteja certa.
        """
        ctx = self.ctx
        ctx.apply_camera()
        return self.encostar_no_ponto_da_venda()

    def encostar_no_ponto_da_venda(self) -> bool:
        """Anda os últimos passos até `PONTO_DA_VENDA`.

        Reusa `UIDoJogo.encostar_no_ponto` -- a regra de não clicar de fora do
        ponto é a mesma do Fay, do Skull Herald e do Rich Man.
        """
        return self._ui_do_jogo().encostar_no_ponto(
            alvo=mapa_hh.PONTO_DA_VENDA,
            precisao=PRECISAO_NO_PONTO_DA_VENDA,
            tentativas=TENTATIVAS_DE_ENCOSTAR,
            segundos_por_tentativa=SEGUNDOS_POR_TENTATIVA,
            o_que=f"vender no {self.NOME_DO_VENDEDOR}",
        )

    # ==================================================================
    # A venda
    # ==================================================================

    def vender(self) -> int:
        """Encosta no ponto, abre a janela e vende. Devolve quantos slots foram.

        Devolve 0 quando não conseguiu chegar ou abrir -- e isso NÃO é exceção:
        quem decide quando vender é a COTA DE RUNS (`ManutencaoDaHH`), e a run
        seguinte tenta de novo. A bolsa deixou de ser gatilho em 09/09/2026;
        ver `docs/decisoes/hh.md` §27.
        """
        ctx = self.ctx
        if not self.ir_ate_o_vendedor():
            ctx.log.warning("HH: não encostei no ponto de venda %s (estou em %s)",
                            mapa_hh.PONTO_DA_VENDA, ctx.memory.position())
            return 0
        if not self._open_npc():
            ctx.log.warning("HH: não abri a janela de venda do %s",
                            self.NOME_DO_VENDEDOR)
            return 0
        return self.sell_from_slot()
