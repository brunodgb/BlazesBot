"""
As portas da Bewitcher Cave: quais NPCs, quais links, quais coordenadas.

A MÁQUINA de operar janela do jogo -- painel de arredores, busca, diálogo,
link, câmera -- mora em `bot/ui_do_jogo.py` e serve os dois ecossistemas. Aqui
fica só o que é DESTA cave:

    Stone City -> Ghost Din Woods      pelo Transport Fay
    a porta da cave                     pelo Skull Herald, em (1395,-635)
    o covil do boss                     pelo Altar Stone, em (218,45)
    a saída                             pelo NPC da saída, em (81,-398)

`UIService` herda de `UIDoJogo`, então tudo que a rotina da BC já chamava
continua no mesmo objeto e com o mesmo nome.
"""
from __future__ import annotations

import time

from ...core import esconder_jogadores, petbug
from ..ui_do_jogo import (
    ESPERA_ANTES_DE_CONFERIR,
    FALHAS_ANTES_DE_REDESCOBRIR,
    UIDoJogo,
)

# Nomes usados nas buscas e a confirmação esperada.
NPC_TRANSPORTE = ("Fay", "Transport Fay")
NPC_ENTRADA_BC = ("Skull", "Skull Herald")

# Links dentro dos diálogos, localizados por imagem.
LINK_GHOST_DIN_WOODS = "link_ghost_din_woods.png"
LINK_ENTRAR_BC = "link_enter_bc.png"


# ===========================================================================
# TELEPORTE DA FAY (Stone City -> Ghost Din Woods)
# ===========================================================================
#
# Era `ctx.tick(4.0)` CEGO, com o comentário "tempo do teleporte". Medido no
# log de dev de 13/08/2026:
#
#     02:52:31.422  Clicando no link em (305, 591)
#     02:52:37.547  Teleportado; local agora: Ghost Din Woods   <- 6,1 s depois
#     02:52:37.589  Abrindo o painel de arredores               <- 40 ms depois
#
# Ou seja: o painel de arredores abre IMEDIATAMENTE. O que atrasava eram os 6,1 s
# gastos antes dele -- os 4 s cegos mais o `fechar_dialogo` (que ainda paga 0,6 s
# quando acha o diálogo) mais a captura de tela de cada um.
#
# Mesma regra que já valeu para o teleporte do vendedor e para o painel de
# arredores: ONDE HAVIA ESPERA CEGA, AGORA SE PERGUNTA. O teto passou a ser 3 s
# (pedido do usuário) e o laço sai no INSTANTE em que a chegada é confirmada.
TETO_DO_TELEPORTE_DA_FAY = 2.0
PASSO_DA_ESPERA_DO_TELEPORTE = 0.08

# ===========================================================================
# O SKULL HERALD DA ENTRADA EXIGE A COORDENADA EXATA
# ===========================================================================
#
# Para o diálogo dele abrir, o personagem tem que estar em (1395,-635) de Ghost
# Din Woods. Não é "por perto": dali a poucos passos o clique já cai no chão -- e
# clicar no chão faz o personagem ANDAR, afastando mais e garantindo que a
# tentativa seguinte também erre. Foi o que aconteceu no log das 14:36: o
# personagem escorregou para (1380,-622), a 20 unidades, e as quatro tentativas
# seguintes falharam pelo mesmo motivo.
#
# E ISSO ACONTECE TODA RUN, não só por acidente: SAIR da cave devolve o
# personagem perto da entrada, mas NÃO na coordenada exata. Então conferir antes
# de clicar não é defesa contra caso raro, é parte do fluxo normal.
#
# POR QUE 2 E NÃO 0. A coordenada de jogo é um inteiro derivado de um float
# dividido por 20, e o pathfinding para onde para. Exigir igualdade exata faria o
# bot repetir a caminhada para sempre por causa de uma unidade de arredondamento.
# Duas unidades é o que "exato" significa na prática aqui -- e é seis vezes mais
# apertado que a tolerância genérica de NPC acima.
TOLERANCIA_DO_NPC_DA_ENTRADA = 2

# Quantas vezes refazer a caminhada pelo painel de arredores antes de desistir de
# acertar a coordenada. Três: a primeira resolve no caso normal, e insistir sem
# limite prenderia a run aqui.
TENTATIVAS_DE_POSICIONAR_NA_ENTRADA = 3


# ===========================================================================
# REAPLICAR O PETBUG QUANDO A ENTRADA NÃO ABRE -- 07/09/2026
# ===========================================================================
#
# O que o usuário explicou depois da auditoria: *"se não usa ele [o PetBug],
# fica outros players na frente e isso faz ele não conseguir clicar no NPC de
# entrar na cave"*.
#
# E o log dá o número: o patch foi aplicado UMA vez, às 23:27:03, e nunca mais
# em 13 h -- nem depois do relogin das 07:55, que trocou o cliente. Das 08h às
# 12h a conta clicou 13.449 vezes num NPC que tinha gente na frente. O diálogo
# não abria porque o clique direito não chegava nele.
#
# A APLICAÇÃO SÓ ACONTECIA NO LOGIN, e é lá que ela continua acontecendo. O que
# muda é que a entrada agora sabe pedir de novo: o patcher é a única coisa que
# tira os jogadores da frente, e falha mecânica em série é o sintoma exato de
# ter alguém na frente.
#
# SÓ A FALHA MECÂNICA CONTA (o diálogo não abriu). Instância cheia é a razão
# NORMAL de não entrar, os cliques saíram, e não há jogador nenhum no caminho.
FALHAS_MECANICAS_PARA_REAPLICAR_O_PETBUG = 20

# Espaço mínimo entre duas reaplicações vindas DAQUI.
#
# Maior que o `petbug.INTERVALO_MINIMO` (30 s) de propósito: aquele existe para
# cinco contas caindo juntas não produzirem cinco cliques. Este existe para uma
# conta presa não matar e reabrir um programa de terceiro a cada 30 s por horas.
# Dois minutos dá ~4 tentativas em 8 min de disputa ruim -- e se o problema for
# jogador na frente, a primeira resolve.
SEGUNDOS_ENTRE_REAPLICACOES = 120.0


class UIService(UIDoJogo):
    """As portas da Bewitcher Cave. A máquina de janela vem de `UIDoJogo`."""

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

    def viajar_para_ghost_din_woods(self) -> bool:
        """Stone City -> Ghost Din Woods, pelo NPC Transport Fay.

        A SEQUÊNCIA inteira mora em `UIDoJogo.viajar_pelo_transporte` desde
        01/09/2026 -- a HH faz exatamente os mesmos passos com outros nomes.
        Aqui ficam só os nomes: qual NPC, qual link, qual ponto e como saber que
        chegou.

        `rolar` fica de fora porque `Ghost Din Woods` está na parte visível da
        lista do Fay. O destino da HH não está, e é lá que a rolagem entra.
        """
        from . import mapa_bc

        ctx = self.ctx
        busca, confirma = NPC_TRANSPORTE
        busca = ctx.settings.route.transport_search_text or busca

        # A CONFIRMAÇÃO É PELA COORDENADA, não pelo nome do lugar: Ghost Din
        # Woods é o único ponto da rotina com X acima de 500, e o campo de nome
        # tem falha medida de ficar preso na área anterior.
        return self.viajar_pelo_transporte(
            busca=busca,
            confirma=confirma,
            link=LINK_GHOST_DIN_WOODS,
            ponto_do_npc=mapa_bc.POSICAO_DA_FAY,
            precisao=mapa_bc.PRECISAO_NO_PONTO_DA_FAY,
            tentativas=mapa_bc.TENTATIVAS_DE_ENCOSTAR_NA_FAY,
            segundos_por_tentativa=mapa_bc.SEGUNDOS_POR_TENTATIVA_NA_FAY,
            chegou=lambda: mapa_bc.x_contradiz_a_cave(ctx.memory.position()),
            # o mesmo predicado de `_esperar_o_teleporte`; ver o porquê lá
            teto_do_teleporte=TETO_DO_TELEPORTE_DA_FAY,
            passo_da_espera=PASSO_DA_ESPERA_DO_TELEPORTE,
        )

    def _encostar_na_fay(self) -> bool:
        """Anda os últimos passos até o ponto exato da Fay.

        A REGRA -- não clicar de fora do ponto -- mora em
        `UIDoJogo.encostar_no_ponto` e vale para os dois ecossistemas. Aqui fica
        o que é da BC: qual ponto, qual precisão, quantas tentativas.

        Existe como método com nome próprio, e não como três argumentos soltos
        na viagem, porque é assim que ele é EXERCITADO: os testes do defeito de
        25/08/2026 (o clique que pegou o White Eagle) chamam esta função pelo
        nome. Um valor da Fay escrito no teste seria uma segunda fonte para o
        mesmo número.
        """
        from . import mapa_bc

        return self.encostar_no_ponto(
            alvo=mapa_bc.POSICAO_DA_FAY,
            precisao=mapa_bc.PRECISAO_NO_PONTO_DA_FAY,
            tentativas=mapa_bc.TENTATIVAS_DE_ENCOSTAR_NA_FAY,
            segundos_por_tentativa=mapa_bc.SEGUNDOS_POR_TENTATIVA_NA_FAY,
            o_que="falar com a Fay",
        )

    def _esperar_o_teleporte(self) -> bool:
        """Espera a chegada em Ghost Din Woods. Sai no instante em que confirma.

        A ESPERA em si é `UIDoJogo.esperar_a_chegada`; o que é da BC é a
        PERGUNTA. E ela é pela COORDENADA, não pelo nome do lugar: Ghost Din
        Woods é o único ponto da rotina com X acima de 500
        (`x_contradiz_a_cave`), e o campo de nome tem falha medida de ficar
        preso na área anterior.

        Não muda o valor de retorno de quem chama -- ver `esperar_a_chegada`
        para o porquê de estourar o teto ser aviso e não falha.
        """
        from . import mapa_bc

        return self.esperar_a_chegada(
            chegou=lambda: mapa_bc.x_contradiz_a_cave(self.ctx.memory.position()),
            teto=TETO_DO_TELEPORTE_DA_FAY,
            passo=PASSO_DA_ESPERA_DO_TELEPORTE,
            o_que="Teleporte",
        )

    def ir_ate_o_npc_da_cave(self) -> bool:
        """Caminha até o Skull Herald, na coordenada da entrada da cave.

        Separado de `tentar_entrar_na_cave` de propósito. Duas coisas dependem
        disso:

          * O time de reset é montado SÓ ao chegar aqui, não antes. Mexer na lista
            no meio do caminho não adianta e o convite podia expirar durante o
            teleporte.
          * A BC é disputada e uma tentativa pode não pegar. Com as etapas
            separadas, repetir a tentativa não refaz a caminhada inteira.
        """
        ctx = self.ctx
        busca, confirma = NPC_ENTRADA_BC
        busca = ctx.settings.route.cave_search_text or busca

        ctx.log.info("Procurando o NPC da entrada da cave")
        with self.trajeto_pelo_painel("NPC da entrada da cave"):
            info = self.buscar_npc(busca, confirmar=confirma)
            if info is None:
                return False
            destino = (info.get("coords")
                       or tuple(ctx.settings.route.cave_entrance))
            if not self.ir_para_resultado(
                    confirma, coords=destino,
                    max_seconds=180.0 * ctx.settings.time_factor):
                return False
        ctx.log.info("Na entrada da cave, posição %s | montado: %s",
                     ctx.memory.position(), ctx.memory.is_mounted())
        return True

    def garantir_coordenada_da_entrada(self) -> bool:
        """Põe o personagem em (1395,-635) ANTES de qualquer clique no NPC.

        Esta é a pré-condição do Skull Herald da entrada, e ela é conferida SEMPRE
        -- não só quando algo deu errado. Sair da cave devolve o personagem perto
        da porta, mas não na coordenada exata, então "quase lá" é o estado normal
        no começo de toda run a partir da segunda.

        A CORREÇÃO É PELO PAINEL DE ARREDORES, e não caminhando pela coordenada.
        Duas razões:

          * é a mesma forma que já leva o personagem até ali na primeira vez, e
            ela comprovadamente pousa no ponto certo -- o painel manda caminhar
            até o NPC, não até um par de números;
          * caminhar por coordenada usa clique no chão, que é justamente o que
            desloca o personagem quando erra. Corrigir um desvio com a ferramenta
            que causa desvios é pedir para girar em falso.

        Devolve se a coordenada foi alcançada. FALSE IMPEDE O CLIQUE, e esta é uma
        decisão revista: antes o bot clicava assim mesmo, com o argumento de que
        uma tentativa que talvez funcione vale mais que nenhuma.

        O argumento estava incompleto porque só olhava o lado bom. Clicar no NPC de
        longe não é uma tentativa que falha em silêncio: o clique cai no CHÃO, e
        clicar no chão faz o personagem ANDAR -- para longe do ponto, tornando a
        próxima tentativa pior que esta. É o mecanismo que transforma "estou um
        pouco fora do lugar" em "o bot se perdeu andando", relatado três vezes
        depois de runs completas.

        Não clicar custa uma tentativa. Clicar de longe custa a posição.
        """
        ctx = self.ctx
        alvo = tuple(ctx.settings.route.cave_entrance)

        from . import mapa_bc

        for tentativa in range(1, TENTATIVAS_DE_POSICIONAR_NA_ENTRADA + 1):
            ctx.raise_if_stopped()
            atual = ctx.memory.position()

            # Sem leitura de posição não há como conferir nem como corrigir.
            # Deixa seguir: recusar aqui travaria a run por uma falha de leitura.
            if atual is None:
                ctx.log.warning(
                    "Não consigo ler a posição para conferir a coordenada da "
                    "entrada; vou tentar clicar assim mesmo."
                )
                return True

            distancia = mapa_bc.distancia(atual, alvo)
            if distancia <= TOLERANCIA_DO_NPC_DA_ENTRADA:
                if tentativa > 1:
                    ctx.log.info("Na coordenada da entrada %s (a %.0f unidades)",
                                 alvo, distancia)
                return True

            ctx.log.info(
                "Estou em %s, a %.0f unidades de %s — o diálogo do Skull Herald "
                "só abre da coordenada exata. Indo até lá pelo painel de "
                "arredores (tentativa %s de %s).",
                atual, distancia, alvo, tentativa,
                TENTATIVAS_DE_POSICIONAR_NA_ENTRADA,
            )

            # NÃO esquece as coordenadas de clique aprendidas.
            #
            # Elas foram medidas com o personagem parado EXATAMENTE em
            # (1395,-635) -- que é para onde esta função está voltando. Restaurar
            # a posição restaura a validade delas. Esquecer aqui forçaria a
            # descoberta por imagem em TODA run (porque sair da cave sempre deixa
            # o personagem fora do ponto), trocando ~1 s por ~10 s justamente na
            # disputa pela vaga da instância.
            #
            # E se elas estiverem erradas assim mesmo, o caminho rápido falha,
            # `_falhas_rapidas` conta, e depois de três a redescoberta acontece
            # sozinha. O conserto já existe; antecipá-lo custa caro e não protege
            # de nada.
            if not self.ir_ate_o_npc_da_cave():
                ctx.log.warning(
                    "A ida até o NPC pelo painel de arredores não completou."
                )

        atual = ctx.memory.position()
        ctx.log.warning(
            "Depois de %s tentativas ainda estou em %s, e a entrada é %s. NÃO vou "
            "clicar no NPC daqui: o clique cairia no chão e o personagem sairia "
            "andando, o que piora a posição em vez de gastar só uma tentativa.",
            TENTATIVAS_DE_POSICIONAR_NA_ENTRADA, atual, alvo,
        )
        # As coordenadas guardadas apontam para o lugar errado a partir daqui.
        self.esquecer_entrada()
        return False

    def tentar_entrar_na_cave(self) -> bool:
        """UMA tentativa de entrar, com o F12 preso do começo ao fim.

        Devolve se os cliques saíram, não se a entrada aconteceu -- confirmar a
        entrada é por localização e posição, e quem chama é que decide se tenta
        de novo.

        Dois caminhos:

          DESCOBERTA (primeira volta, ou depois de três falhas seguidas):
            localiza o NPC e o link por imagem e guarda as duas coordenadas.
            Custa alguns segundos, uma vez.

          RÁPIDO (as outras voltas): repete os dois cliques guardados. ~1 s.
            É o que permite disputar a vaga com as outras contas.

        ANTES DOS DOIS: garante a COORDENADA EXATA. Fica aqui, e não só em quem
        chama, porque é aqui que os cliques saem -- a proteção precisa viajar junto
        com a ação, não depender de o chamador ter lembrado.

        Antes isto só CONFERIA e desistia da tentativa quando estava fora do lugar,
        deixando a correção para o chamador. Agora corrige na hora, pelo painel de
        arredores: o Skull Herald exige (1395,-635), e sair da cave devolve o
        personagem perto mas não exatamente ali -- ou seja, estar fora do ponto é o
        caso NORMAL no começo de cada run, não a exceção.

        E SE A CORREÇÃO NÃO DER CERTO, a tentativa termina aqui, sem clicar. Ver
        `garantir_coordenada_da_entrada`: clicar de longe não é uma tentativa
        barata, é o que faz o personagem andar para longe.
        """
        # ============================================================
        # F12 PRESO DURANTE O PROCESSO INTEIRO, não só em volta do clique
        # ============================================================
        #
        # A primeira versão segurava só no par de cliques, e o usuário observou
        # que não presta: *"clicar só pelo tempo do clique acaba fazendo não
        # clicar direito, principalmente ao entrar na cave."*
        #
        # O mecanismo é a FILA. Com `MODO_DE_CLIQUE = "postmessage_puro"` as
        # quatro mensagens do clique são POSTADAS, e o KEYDOWN/KEYUP do F12 entram
        # na MESMA fila, encostados nelas -- o cliente processa a tecla no meio do
        # clique. Bloco longo tira a tecla de perto das mensagens do clique.
        #
        # `segurado` CONTA aninhamento (ver `Input.key_down`), então o `with` que
        # já existe dentro de `_abrir_dialogo_e_clicar` não solta a tecla aqui.
        with esconder_jogadores.segurado(
                tecla=self.ctx.settings.keys.hide_players,
                segurar=self.ctx.key_down, soltar=self.ctx.key_up,
                log=self.ctx.log):
            if not self.garantir_coordenada_da_entrada():
                return False

            if (self._ponto_npc_entrada is None
                    or self._ponto_link_entrada is None
                    or self._falhas_rapidas >= FALHAS_ANTES_DE_REDESCOBRIR):
                saiu = self._entrar_descobrindo()
            else:
                saiu = self._entrar_rapido()
            if saiu:
                # OS CLIQUES SAÍRAM: não há jogador no caminho. O que vier
                # depois é o servidor, e o PetBug não tem nada com isso.
                self._falhas_mecanicas_seguidas = 0
            return saiu

    def _entrar_descobrindo(self) -> bool:
        """Tentativa completa, por imagem, que APRENDE as coordenadas."""
        ctx = self.ctx
        _, confirma = NPC_ENTRADA_BC

        if self._falhas_rapidas >= FALHAS_ANTES_DE_REDESCOBRIR:
            ctx.log.info(
                "%s tentativas rápidas sem entrar; redescobrindo o NPC e o link "
                "por imagem", self._falhas_rapidas,
            )
            self._falhas_rapidas = 0
            self.resetar_visao(forcar=True)

        ponto_npc = self.falar_com_npc(self._ponto_npc_entrada, alturaDif=-48)
        #ctx.log.warning("Ponto do NPC: %s", ponto_npc)
        if ponto_npc is None:
            ctx.log.warning("Não abri o diálogo do %s", confirma)
            return False

        ponto_link = self.clicar_link(LINK_ENTRAR_BC)
        if ponto_link is None:
            self.fechar_dialogo()
            return False

        # Aprendeu: as próximas tentativas custam ~1 s em vez de 10.
        self._ponto_npc_entrada = ponto_npc
        self._ponto_link_entrada = ponto_link
        ctx.log.info(
            "Guardei as coordenadas da entrada: NPC em %s, link em %s — as "
            "próximas tentativas levam cerca de 1 segundo",
            ponto_npc, ponto_link,
        )
        ctx.tick(ESPERA_ANTES_DE_CONFERIR)
        return True

    def _entrar_rapido(self) -> bool:
        """Tentativa de ~1 segundo, com as coordenadas já conhecidas.

        NÃO fecha o diálogo e NÃO procura o link por imagem. Se o clique no link
        não pegar, o diálogo continua aberto e o clique direito da volta seguinte
        o reabre no mesmo lugar -- fechar seria mais um clique e mais uma espera
        por volta, e a volta inteira tem que caber em um segundo.

        O que ela SIM confere é se o diálogo abriu, entre os dois cliques. Custa
        uma captura (algumas dezenas de milissegundos, dentro do orçamento de um
        segundo) e evita o pior caso do laço: um clique no chão que tira o
        personagem da coordenada e condena todas as tentativas seguintes.

        E NÃO DORME depois do clique no link. Quem observa o resultado é o laço da
        rotina, que fica lendo a posição em fatias de menos de 100 ms -- essa
        leitura já É a espera, e ela termina no instante em que a entrada acontece.
        Os 0,35 s que havia aqui atrasavam justamente o reconhecimento.
        """
        return self._abrir_dialogo_e_clicar(
            self._ponto_npc_entrada,    # type: ignore[arg-type]
            self._ponto_link_entrada,   # type: ignore[arg-type]
            "entrar na cave",
            esperar_depois=0.0,
        )

    def _reaplicar_o_petbug_se_preciso(self) -> None:
        """Falha mecânica em série = provavelmente tem jogador na frente do NPC.

        NUNCA DERRUBA NADA: o patcher é programa de terceiro, e a disputa da
        cave não pode parar porque ele não respondeu. Falha vira aviso.
        """
        seguidas = getattr(self, "_falhas_mecanicas_seguidas", 0)
        if seguidas < FALHAS_MECANICAS_PARA_REAPLICAR_O_PETBUG:
            return
        agora = time.monotonic()
        ultima = getattr(self, "_petbug_reaplicado_em", 0.0)
        if ultima and agora - ultima < SEGUNDOS_ENTRE_REAPLICACOES:
            return
        self._petbug_reaplicado_em = agora
        self.ctx.log.warning(
            "Entrada na cave: %s falhas mecânicas seguidas (o diálogo não "
            "abre). Provavelmente há jogador na frente do NPC — reaplicando o "
            "PetBug, que é o que os esconde.", seguidas)
        try:
            resultado = petbug.aplicar_patch(log=self.ctx.log)
        except Exception as exc:
            self.ctx.log.warning("PetBug falhou (a entrada segue): %s", exc)
            return
        self.ctx.log.info("PetBug (pela entrada): %s", resultado)

    def registrar_falha_de_entrada(self) -> None:
        """Contabiliza uma tentativa cuja MECÂNICA falhou.

        Três seguidas fazem a próxima tentativa redescobrir tudo por imagem: se as
        coordenadas guardadas pararam de funcionar, é porque a câmera girou ou o
        personagem saiu do lugar -- e insistir nos mesmos dois cliques nunca
        resolveria.

        ESTE CONTADOR ESTAVA MEDINDO A COISA ERRADA, e era o gargalo da disputa.
        Ele contava "não entrei", que junta duas falhas de natureza oposta:

          MECÂNICA ..... o diálogo não abriu, o clique não pegou. As coordenadas
                         são suspeitas, e redescobrir é a resposta certa.
          SERVIDOR ..... os dois cliques saíram, o pedido foi feito, e a vaga foi
                         de outro. Não há nada de errado com as coordenadas --
                         redescobrir aqui é jogar 5 a 10 segundos fora no meio
                         exato da disputa, e é o que produzia 4 tentativas em 15 s.

        E a segunda é o caso COMUM: instância cheia é a razão normal de não entrar.
        Agora só a primeira conta, e quem sabe distinguir é `tentar_entrar_na_cave`,
        que devolve False quando a mecânica falhou e True quando os cliques saíram.
        """
        self._falhas_rapidas += 1
        # CONTADOR SEPARADO, e é por isso que ele existe: `_falhas_rapidas`
        # ZERA a cada redescoberta (de cinco em cinco), então ele nunca chegaria
        # a vinte. Este só zera quando os cliques SAEM.
        self._falhas_mecanicas_seguidas = (
            getattr(self, "_falhas_mecanicas_seguidas", 0) + 1)
        self._reaplicar_o_petbug_se_preciso()

    def esquecer_entrada(self) -> None:
        """Descarta as coordenadas aprendidas (o personagem saiu do lugar)."""
        self._ponto_npc_entrada = None
        self._ponto_link_entrada = None
        self._falhas_rapidas = 0

    # ==================================================================
    # Altar Stone -> covil do boss
    # ==================================================================

    def entrar_no_covil_do_boss(self, forcar_visao: bool = True) -> bool:
        """Altar Stone -> "Secret Cemetery", que é a sala do boss.

        PRÉ-REQUISITO: estar no waypoint (218,45) do Secret Altar, EXATO. As duas
        coordenadas abaixo foram medidas COM O PERSONAGEM ALI. São cliques na
        cena 3D, então a posição do personagem faz parte da coordenada -- de
        outro ponto da pirâmide o clique cai na parede ou no chão.

        `forcar_visao=False` quando o personagem não andou desde a tentativa
        anterior: a câmera não se mexe sozinha, e o View Reset custa um clique
        mais a espera dele em cada volta.
        """
        ctx = self.ctx
        c = ctx.coords
        ctx.log.info("Usando o Altar Stone para entrar no covil")

        from . import mapa_bc

        # A posição faz parte da coordenada: estas foram medidas no waypoint
        # (218,45) EXATO.
        #
        # A tolerância aqui é a MESMA que `routine._encostar_exato_no_patamar`
        # usa para andar até o ponto -- as duas leem
        # `mapa_bc.PRECISAO_NO_PATAMAR_DO_ALTAR`. Ter dois números escolhidos à
        # parte, um para andar e outro para conferir, foi o que travou a run no
        # incidente da tolerância 3 ("cheguei" de um lado, "não cheguei" do
        # outro, sobre o mesmo instante).
        #
        # E ela é EXATA, não a folga de 8 da rota: medido no log de dev, das 11
        # tentativas com o personagem fora do ponto, nenhuma abriu o diálogo.
        if not self.na_posicao_de_clicar(
                mapa_bc.ULTIMO_ANTES_DO_ALTAR,
                tolerancia=mapa_bc.PRECISAO_NO_PATAMAR_DO_ALTAR,
                o_que="clicar no Altar Stone"):
            return False

        self.resetar_visao(forcar=forcar_visao)
        if not self._abrir_dialogo_e_clicar(c.altar_npc, c.altar_enter,
                                            "entrar no covil pelo Altar Stone"):
            return False
        # O portal é teleporte: dá tempo de o servidor mover o personagem antes de
        # quem chamou conferir a posição.
        ctx.tick(1.5)
        return True

    # ==================================================================
    # Saída da cave
    # ==================================================================

    def sair_da_cave(self) -> bool:
        """Skull Herald do covil -> "Leave Bewitcher Cave".

        É o MESMO NPC e o MESMO nome da entrada: o jogo usa o Skull Herald para as
        duas coisas. Este fica na posição (81,-398), logo depois do boss, e as
        coordenadas de tela abaixo valem estando ali.
        """
        ctx = self.ctx
        c = ctx.coords
        ctx.log.info("Saindo da cave pelo Skull Herald")

        from . import mapa_bc

        # Medidas em (81,-398). De longe o clique cai no chão -- e aqui isso é pior
        # que perder a tentativa: o personagem sai andando pelo covil do boss.
        #
        # A TOLERÂNCIA É PASSADA, e não o default de 12 unidades. Doze de folga é
        # outro lugar, com o NPC girado na tela -- e era o outro lado do defeito
        # que `mapa_bc.PRECISAO_NO_PONTO_DA_SAIDA` documenta: quem anda usava 8,
        # quem clica usava 12, e o waypoint do boss cai bem no meio dos dois.
        # Agora os dois leem a MESMA constante por construção.
        if not self.na_posicao_de_clicar(mapa_bc.POSICAO_DA_SAIDA,
                                         tolerancia=mapa_bc.PRECISAO_NO_PONTO_DA_SAIDA,
                                         o_que="clicar no Skull Herald da saída"):
            return False

        self.resetar_visao(forcar=True)
        if not self._abrir_dialogo_e_clicar(c.cave_exit_npc, c.cave_exit_link,
                                            "sair da cave"):
            return False
        ctx.tick(1.5)
        return True
