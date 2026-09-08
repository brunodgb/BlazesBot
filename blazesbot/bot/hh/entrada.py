"""Como se chega na HH: do Stone City até dentro da Black Wind Camp Dungeon.

=========================================================================
O CAMINHO, MEDIDO NA TELA EM 01/09/2026
=========================================================================

    Stone City
      └─ NPC "Transport Fay"                    (o MESMO da Bewitcher Cave)
           └─ a lista de destinos ROLADA até o fim
                └─ link "West Suburb of Stone City"   (Need 5, nível 20)
                     └─ TP
                          └─ Arredores, aba NPC, busca "Mutual"
                               └─ "Mutual Quest Woman [-358,-288]"
                                    └─ andar até (-342,-288)
                                         └─ "Elite Axe Monk Soldier"
                                              └─ dentro da cave

O bot em Lua NÃO faz esta rota: ele clica o traço de missão em (743,251) e
assume que o personagem já está por perto -- só funciona porque o usuário
posiciona à mão antes de ligar o script. Ver `docs/decisoes/hh.md`, seção 2.

=========================================================================
NADA AQUI É MÁQUINA NOVA
=========================================================================

Cada passo acima é uma coisa que `bot/ui_do_jogo.py` já sabe fazer, porque a BC
faz o mesmo três vezes por run. Este módulo só diz QUAIS nomes:

    viajar_pelo_transporte   o Fay, o link, o ponto, como saber que chegou
    buscar_npc               "Mutual"
    ir_para_resultado         o pathfinding do jogo caminha
    encostar_no_ponto        (-342,-288), sem clicar de fora dele
    falar_com_npc            o Elite Axe Monk Soldier
    clicar_link              o link de entrar

A ÚNICA capacidade que a HH obrigou a existir é a ROLAGEM da lista do diálogo
(`rolar_o_dialogo`), porque o destino dela não cabe na primeira tela. E ela
depende de um template que ainda falta recortar --
`data/templates/dialogo_seta_baixo.png`. Sem ele a entrada RECUSA e diz isso no
log, em vez de clicar num pixel adivinhado: clique fora da janela cai na cena 3D
e faz o personagem andar, saindo da coordenada de onde o NPC responde.
"""
from __future__ import annotations

from ...core import stone_city
from ..context import BotContext
from ..navegacao import Navigator
from ..ui_do_jogo import UIDoJogo
from . import mapa_hh

# Links dentro dos diálogos, localizados por imagem.
#
# RECORTADOS PELO USUÁRIO em 03/09/2026, dos prints que ficaram em
# `data/templates/entrada/` como evidência de onde cada um saiu:
#
#   link_west_suburb.png   151x18, de `completa1.png` (diálogo do Fay em Stone
#                          City, com a lista de destinos ainda sem rolar)
#   link_enter_hh.png      126x20, de `completa2.png` (diálogo do Elite Axe
#                          Monk Soldier) -- o texto é "Enter Happiness Hall"
#
# O `link_west_suburb` veio com uma faixa da linha DE CIMA, e ela foi cortada: o
# que está acima do link na lista do Fay muda conforme a rolagem, e conteúdo
# variável dentro do template baixa o escore justamente na hora de casar.
LINK_WEST_SUBURB = "link_west_suburb.png"
LINK_ENTRAR_HH = "link_enter_hh.png"
# O link do diálogo do `Servant Child`, DENTRO da cave.
LINK_SAIR_HH = "link_leave_hh.png"

# Quantas vezes refazer a caminhada pelo painel de arredores antes de desistir
# de acertar a coordenada de conversa. Três: a primeira resolve no caso normal,
# e insistir sem limite prenderia a run na porta.
TENTATIVAS_DE_POSICIONAR = 3

# Quantas vezes reabrir o painel de arredores e reclicar no NPC da porta.
#
# Regra do usuário, 08/09/2026: o painel pode desviar, parar no meio ou não
# chegar, e a resposta é refazer -- não falhar o estado inteiro e recomeçar a
# viagem desde Stone City.
#
# TRÊS, e não "para sempre": painel que não leva a lugar nenhum não se resolve
# insistindo. Três voltas cobrem o caso normal (uma trava de pathfinding) e
# ainda devolvem o controle para a rotina em tempo de ela tentar outra coisa.
TENTATIVAS_DE_CHEGAR_PELA_MUTUAL = 3

# Entre uma tentativa do painel e a seguinte. Curto: o custo da volta é o
# trajeto que o jogo faz, não esta espera.
ENTRE_TENTATIVAS_DA_MUTUAL = 1.0

# Quanto tempo dar a cada tentativa de encostar no ponto exato.
SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR = 1.8

# Teto da espera pela troca de mapa depois de clicar no link de entrar.
#
# Mesmo valor do teleporte da Fay na BC, e pelo mesmo motivo: estourar o teto
# vira AVISO e a rotina segue -- quem descobre que não entrou é a leitura de
# posição do passo seguinte, que já existe e não custa nada.
# A CONFIRMAÇÃO DE UMA TENTATIVA DE ENTRADA -- os dois números são do BC.
#
# Eram 2,0 s de teto com passo de 0,08 s, e isso custava a disputa: enquanto o
# bot esperava dois segundos para descobrir que a instância estava cheia,
# ninguém estava tentando de novo. A vaga é disputada com outros jogadores.
#
# Os valores abaixo vêm da aritmética medida da BC (`bc/routine.py`, o bloco do
# orçamento da disputa): um quarto de segundo cobre a ida e volta do servidor
# com folga, e perguntar é uma leitura de MEMÓRIA -- posição --, que custa
# microssegundos. Por isso dá para perguntar seis vezes por janela em vez de
# esperar cego.
#
# Entrou, sai na hora. Não entrou, a janela fecha e a tentativa seguinte começa.
TETO_DA_ENTRADA = 0.25
PASSO_DA_ESPERA_DA_ENTRADA = 0.04

# A CONFIRMAÇÃO DA SAÍDA é mais generosa que a da entrada, e de propósito.
#
# A entrada é DISPUTADA: esperar ali é tempo em que ninguém está tentando de
# novo, e por isso a janela é de 0,25 s. A saída não disputa nada -- acontece
# uma vez por run, com a cave vazia --, e o que ela paga é a troca de mapa
# inteira. Repetir o diálogo antes de o servidor responder gastaria dois
# cliques na cena 3D com a tela ainda carregando.
TETO_DA_SAIDA = 3.0

# Teto da espera pelo teleporte do Fay.
TETO_DO_TELEPORTE = 2.0
PASSO_DA_ESPERA_DO_TELEPORTE = 0.08


class EntradaDaHH(UIDoJogo):
    """As portas da Black Wind Camp Dungeon.

    Herda de `UIDoJogo` exatamente como `bc.ui_service.UIService`: a máquina de
    operar janela do jogo é a mesma, e aqui ficam só os nomes desta cave.
    """

    def __init__(self, ctx: BotContext,
                 navigator: Navigator | None = None) -> None:
        # O navegador nasce com o MAPA DA HH quando não vem pronto -- ver o
        # construtor equivalente de `bc/ui_service.py`.
        super().__init__(ctx, navigator or Navigator(ctx, mapa_hh))
        # Coordenadas aprendidas na primeira tentativa de entrada, para as
        # seguintes custarem dois cliques em vez de duas buscas por imagem. Ver
        # `UIDoJogo.preparar_entrada` para o porquê de serem esquecidas.
        self._ponto_npc_entrada = None
        self._ponto_link_entrada = None
        self._falhas_rapidas = 0

    # ==================================================================
    # Stone City -> West Suburb of Stone City
    # ==================================================================

    def viajar_para_a_hh(self) -> bool:
        """Vai até o Fay e teleporta para `West Suburb of Stone City`.

        `rolar=True` é a diferença contra a BC, e é obrigatória: sem rolar, a
        lista do Fay mostra de `Sky Village` a `Star Town` e o destino da HH não
        está lá. Ver `UIDoJogo.rolar_o_dialogo`.
        """
        ctx = self.ctx
        busca, confirma = stone_city.NPC_DE_TRANSPORTE
        busca = ctx.settings.hh.route.transport_search_text or busca

        return self.viajar_pelo_transporte(
            busca=busca,
            confirma=confirma,
            link=LINK_WEST_SUBURB,
            # O Fay é o MESMO NPC da BC, no MESMO ponto de Stone City: o
            # número mora num lugar só. Ver `stone_city.POSICAO_DA_FAY`.
            ponto_do_npc=stone_city.POSICAO_DA_FAY,
            precisao=stone_city.PRECISAO_NO_PONTO_DA_FAY,
            tentativas=stone_city.TENTATIVAS_DE_ENCOSTAR_NA_FAY,
            segundos_por_tentativa=stone_city.SEGUNDOS_POR_TENTATIVA_NA_FAY,
            chegou=self._chegou_no_west_suburb,
            teto_do_teleporte=TETO_DO_TELEPORTE,
            passo_da_espera=PASSO_DA_ESPERA_DO_TELEPORTE,
            rolar=True,
        )

    def _chegou_no_west_suburb(self) -> bool:
        """Cheguei no destino do teleporte?

        A PERGUNTA É PELA COORDENADA, não pelo nome do lugar -- o campo de nome
        tem falha medida de ficar preso na área anterior (ver `core/lugares.py`).

        E a coordenada que responde é a da entrada: chegar em `West Suburb` põe o
        personagem na região da porta da HH, onde X e Y são negativos e da ordem
        de -300. Em Stone City o Y é abaixo de -490
        (`core.stone_city.Y_DE_STONE_CITY`), então sair de lá já é resposta
        suficiente.
        """
        pos = self.ctx.memory.position()
        if pos is None:
            return False
        return not stone_city.posicao_esta_em_stone_city(pos)

    # ==================================================================
    # West Suburb -> a coordenada de conversa
    # ==================================================================

    def ir_ate_o_npc_da_hh(self) -> bool:
        """Do teleporte até (-342,-288), de frente para o Elite Axe Monk Soldier.

        =================================================================
        TRÊS PASSOS, E CADA UM EXISTE POR UM MOTIVO DIFERENTE
        =================================================================

        1. MINIMAPA até `PONTO_PARA_ABRIR_OS_ARREDORES` (-268,-488). O teleporte
           da Fay espalha o ponto de chegada, e o painel de arredores é clique
           POSICIONAL: abrir de onde o teleporte largou dá resultado diferente a
           cada run. Andar até um ponto fixo torna a busca repetível.

        2. PAINEL DE ARREDORES até PERTO da `Mutual Quest Woman` -- é o
           pathfinding do próprio jogo, que atravessa a geometria que um clique
           de minimapa não atravessa.

        3. MINIMAPA no último trecho (`garantir_coordenada_da_entrada`), porque
           o painel aceita folga por construção e clicar de onde ele largar é o
           defeito medido na BC em 25/08/2026.

        =================================================================
        O PASSO 2 NÃO É UMA TENTATIVA SÓ
        =================================================================

        Regra do usuário, 08/09/2026: *"se o bot desviar, parar no meio do
        caminho ou não chegar na porta de HH, o sistema deve abortar a espera,
        reabrir o Surroundings, clicar em Mutual novamente"*.

        Antes disto `ir_para_resultado` devolvia `False` e a rotina falhava o
        estado inteiro -- ou seja, voltava para `RECUPERAR`, se situava e refazia
        a viagem desde Stone City. O laço abaixo refaz só o que falhou.

        A CADA VOLTA O PAINEL É FECHADO ANTES DE REABRIR. Painel aberto por cima
        engole o clique seguinte, e o sintoma é uma busca que "não encontra" o
        NPC que está na lista.

        Separado de `tentar_entrar_na_hh` de propósito, igual à BC: o time de
        reset é montado SÓ ao chegar aqui, e repetir a tentativa de entrada não
        deve refazer a caminhada inteira.
        """
        ctx = self.ctx

        if not self._ir_ao_ponto_de_abrir_os_arredores():
            return False

        if not self._chegar_perto_da_mutual():
            return False

        if not self.garantir_coordenada_da_entrada():
            return False

        ctx.log.info("Na porta da HH, posição %s | montado: %s",
                     ctx.memory.position(), ctx.memory.is_mounted())
        return True

    def _ir_ao_ponto_de_abrir_os_arredores(self) -> bool:
        """Anda pelo minimapa até o ponto fixo de onde o painel é aberto.

        ESPERA A TROCA DE MAPA ANTES DE CLICAR. O teleporte tem tela de
        carregamento, e clique no minimapa durante ela é clique perdido -- o
        `viajar_para_a_hh` já confirma a saída de Stone County por coordenada,
        mas a confirmação é da POSIÇÃO, não do fim do desenho. Reconfirmar aqui
        que a leitura responde é o que separa "cheguei" de "posso clicar".
        """
        ctx = self.ctx
        if not self.esperar_a_chegada(
                chegou=lambda: ctx.memory.position() is not None,
                teto=TETO_DO_TELEPORTE,
                passo=PASSO_DA_ESPERA_DO_TELEPORTE,
                o_que="leitura de posição depois do teleporte"):
            ctx.log.warning(
                "Sem leitura de posição depois do teleporte; sigo mesmo assim "
                "-- o painel de arredores ainda pode funcionar daqui.")

        return self.encostar_no_ponto(
            alvo=mapa_hh.PONTO_PARA_ABRIR_OS_ARREDORES,
            precisao=mapa_hh.PRECISAO_PARA_ABRIR_OS_ARREDORES,
            tentativas=TENTATIVAS_DE_POSICIONAR,
            segundos_por_tentativa=SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR,
            o_que="abrir o painel de arredores",
        )

    def _chegar_perto_da_mutual(self) -> bool:
        """Painel de arredores até a porta, INSISTINDO enquanto não chegar.

        Devolve `False` só quando as tentativas acabam -- e aí a rotina falha o
        estado, que é o certo: painel que não leva a lugar nenhum não se resolve
        insistindo para sempre.
        """
        ctx = self.ctx
        busca, confirma = mapa_hh.NPC_PARA_BUSCAR
        busca = ctx.settings.hh.route.npc_search_text or busca

        for tentativa in range(1, TENTATIVAS_DE_CHEGAR_PELA_MUTUAL + 1):
            self._guardar()
            ctx.log.info("Procurando a %s (porta da HH) -- tentativa %s de %s",
                         confirma, tentativa, TENTATIVAS_DE_CHEGAR_PELA_MUTUAL)

            # PAINEL LIMPO ANTES DE ABRIR. Da segunda volta em diante pode
            # haver painel meio aberto da volta anterior, e ele engole o clique.
            if tentativa > 1:
                self.fechar_dialogo()

            with self.trajeto_pelo_painel("NPC da porta da HH"):
                info = self.buscar_npc(busca, confirmar=confirma)
                if info is not None:
                    destino = info.get("coords") or mapa_hh.POSICAO_DA_MUTUAL
                    self.ir_para_resultado(
                        confirma, coords=destino,
                        max_seconds=180.0 * ctx.settings.time_factor)

            # QUEM DECIDE É A DISTÂNCIA, não o que o painel devolveu. O painel
            # pode dizer que levou e largar o personagem no meio do caminho --
            # é o "desviar ou parar no meio" do relato.
            pos = ctx.memory.position()
            if pos is not None and mapa_hh.distancia(
                    pos, mapa_hh.PONTO_DA_ENTRADA) <= mapa_hh.RAIO_DA_PORTA:
                ctx.log.info("Cheguei na região da porta (%s)", pos)
                return True

            ctx.log.warning(
                "O painel não me levou à porta (estou em %s, a porta é %s). "
                "Fechando os painéis e tentando de novo.",
                pos, mapa_hh.PONTO_DA_ENTRADA)
            ctx.tick(ENTRE_TENTATIVAS_DA_MUTUAL)

        ctx.log.error(
            "Não cheguei na porta da HH pelo painel de arredores em %s "
            "tentativas.", TENTATIVAS_DE_CHEGAR_PELA_MUTUAL)
        return False

    def _guardar(self) -> None:
        """Parada e queda respondem ENTRE as tentativas do painel."""
        self.ctx.raise_if_stopped()
        self.ctx.check_watchdog()

    def garantir_coordenada_da_entrada(self) -> bool:
        """Põe o personagem em (-342,-288) ANTES de qualquer clique no NPC.

        Conferido SEMPRE, e não só quando algo deu errado: SAIR da cave devolve o
        personagem perto da porta, mas não na coordenada exata, então "quase lá"
        é o estado normal a partir da segunda run.
        """
        return self.encostar_no_ponto(
            alvo=mapa_hh.PONTO_DA_ENTRADA,
            precisao=mapa_hh.PRECISAO_NO_PONTO_DA_ENTRADA,
            tentativas=TENTATIVAS_DE_POSICIONAR,
            segundos_por_tentativa=SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR,
            o_que=f"falar com o {mapa_hh.NPC_DA_ENTRADA}",
        )

    # ==================================================================
    # A porta
    # ==================================================================

    def tentar_entrar_na_hh(self) -> bool:
        """Uma tentativa de entrar. Devolve se o clique no link saiu.

        NÃO CONFIRMA A ENTRADA, e é deliberado: quem confirma é o laço da rotina,
        lendo a posição em fatias curtas. É o mesmo desenho da BC, e ele existe
        porque a vaga na instância é disputada -- dormir aqui esperando a troca
        de mapa é tempo em que ninguém está tentando de novo.
        """
        if not self.na_posicao_de_clicar(
                mapa_hh.PONTO_DA_ENTRADA,
                tolerancia=mapa_hh.PRECISAO_NO_PONTO_DA_ENTRADA,
                o_que="entrar na HH"):
            return False

        if (self._ponto_npc_entrada is not None
                and self._ponto_link_entrada is not None
                and self._falhas_rapidas < 5):
            return self._entrar_rapido()
        return self._entrar_descobrindo()

    def _entrar_descobrindo(self) -> bool:
        """A primeira tentativa: acha o NPC e o link por imagem e GUARDA os dois."""
        ctx = self.ctx
        ponto_npc = self._ponto_padrao_do_npc()
        if self.falar_com_npc(ponto_npc) is None:
            ctx.log.warning("Não abri o diálogo do %s", mapa_hh.NPC_DA_ENTRADA)
            return False

        if not self._ainda_estou_fora():
            self.fechar_dialogo()
            return False

        ponto_link = self.clicar_link(LINK_ENTRAR_HH)
        if ponto_link is None:
            self.fechar_dialogo()
            return False

        self._ponto_npc_entrada = ponto_npc
        self._ponto_link_entrada = ponto_link
        self._falhas_rapidas = 0
        return True

    def _entrar_rapido(self) -> bool:
        """As seguintes: repete os dois cliques guardados, com o diálogo conferido.

        Cerca de 1 segundo por volta, contra 10 a 14 da redescoberta. Ver
        `bot/ui_do_jogo.py` para a conta inteira.
        """
        return self._abrir_dialogo_e_clicar(
            self._ponto_npc_entrada, self._ponto_link_entrada,
            "entrar na HH", esperar_depois=0.0,
            ainda_vale=self._ainda_estou_fora)

    def _ainda_estou_fora(self) -> bool:
        """Continuo do lado de fora da cave? Chamado ENTRE os dois cliques.

        =================================================================
        O BOT ENTRAVA E SAÍA NA MESMA VOLTA
        =================================================================

        Regra do usuário, 03/09/2026: *"se for Black Wind Camp Dungeon e X acima
        de 0 entrou na cave e precisa parar as tentativas na hora, pois no mesmo
        ângulo que entra, ele sai"*.

        O par de cliques não é atômico -- entre o direito e o do link há a
        espera do diálogo. Quando uma tentativa acertava, o personagem entrava,
        e a tentativa seguinte clicava com direito no mesmo ângulo: dentro da
        cave aquele ângulo é o NPC de SAÍDA. O diálogo abria (a conferência
        dizia "pode clicar") e o clique no link caía em "Leave Happiness Hall".

        A leitura é de MEMÓRIA -- uma coordenada -- e custa microssegundos. É o
        que torna barato perguntar entre dois cliques.

        SEM LEITURA, SEGUE. `esta_dentro_da_hh(None)` é False, e "não sei" não
        pode bloquear a entrada: bot mudo na porta é pior que o defeito.
        """
        if mapa_hh.esta_dentro_da_hh(self.ctx.memory.position()):
            self.ctx.log.info(
                "Entrei na cave entre os dois cliques -- PARO a tentativa aqui. "
                "Clicar no link agora seria clicar em sair.")
            return False
        return True

    def registrar_falha_de_entrada(self) -> None:
        """Uma tentativa rápida não entrou. Cinco seguidas mandam redescobrir."""
        self._falhas_rapidas += 1

    def esquecer_entrada(self) -> None:
        """Apaga as coordenadas aprendidas.

        Chamado quando o personagem SAI do lugar: a posição mudou, e um ponto de
        NPC velho aponta para o chão -- clicar no chão faz o personagem andar,
        saindo justamente da coordenada de onde a cave pode ser aberta.
        """
        self._ponto_npc_entrada = None
        self._ponto_link_entrada = None
        self._falhas_rapidas = 0

    # ==================================================================
    # A saída
    # ==================================================================

    def garantir_coordenada_da_saida(self) -> bool:
        """Põe o personagem em (527,124) ANTES de qualquer clique no NPC.

        Espelho de `garantir_coordenada_da_entrada`, e existe pelo mesmo motivo
        -- com uma consequência pior. Medido pelo usuário em 04/09/2026: há
        **outro NPC por perto**, e o clique de longe abre o diálogo DELE. O
        personagem então caminha até esse outro NPC, saindo do único ponto de
        onde o `Servant Child` é alcançável, e a saída deixa de acontecer.
        """
        return self.encostar_no_ponto(
            alvo=mapa_hh.PONTO_DA_SAIDA,
            precisao=mapa_hh.PRECISAO_NO_PONTO_DA_SAIDA,
            tentativas=TENTATIVAS_DE_POSICIONAR,
            segundos_por_tentativa=SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR,
            o_que=f"falar com o {mapa_hh.NPC_DA_SAIDA}",
        )

    def tentar_sair_da_hh(self) -> bool:
        """Uma tentativa de sair pelo NPC. Devolve se o clique no link saiu.

        =================================================================
        É O MESMO PADRÃO DA ENTRADA, E ISSO É O PONTO
        =================================================================

        Clique direito no NPC, diálogo conferido por imagem, link achado por
        TEMPLATE e clicado. Quem confirma a saída é o laço da rotina, lendo a
        posição -- igual à entrada.

        O bot em Lua faz diferente porque não sabe ler a tela: `farmer.exitCave`
        dá TRÊS cliques direitos às cegas em alturas diferentes (526,298 /
        524,325 / 529,361) e depois clica num ponto fixo do diálogo. Um clique
        que erra o NPC cai no chão -- e clique no chão faz o personagem ANDAR,
        saindo do ponto de onde o NPC é alcançável.

        NÃO GUARDA OS PONTOS entre tentativas, diferente da entrada. Lá a rajada
        é disputada e vale 1 s contra 10; aqui a saída acontece uma vez por run,
        com a cave vazia, e a economia não pagaria o risco de repetir um ponto
        que ficou velho.
        """
        ctx = self.ctx
        # NÃO SE CLICA DE FORA DO PONTO. É a mesma regra da entrada, e aqui ela
        # protege de um erro pior: o clique de longe pega OUTRO NPC.
        if not self.na_posicao_de_clicar(
                mapa_hh.PONTO_DA_SAIDA,
                tolerancia=mapa_hh.PRECISAO_NO_PONTO_DA_SAIDA,
                o_que="sair da HH"):
            return False

        if self.falar_com_npc(ctx.coords.hh_exit_npc) is None:
            ctx.log.warning("Não abri o diálogo do %s", mapa_hh.NPC_DA_SAIDA)
            return False

        if self.clicar_link(LINK_SAIR_HH) is None:
            ctx.log.warning(
                "O diálogo do %s abriu mas não achei o link %r",
                mapa_hh.NPC_DA_SAIDA, LINK_SAIR_HH)
            self.fechar_dialogo()
            return False
        return True

    def esperar_sair(self) -> bool:
        """Espera a troca de mapa depois do clique no link.

        A régua é a POSIÇÃO virar a de fora da cave, e não o nome do lugar: o
        Lua usa o mesmo par (`farmer.exitCave`), e a coordenada é a leitura que
        nunca falhou nos logs.
        """
        return self.esperar_a_chegada(
            chegou=lambda: not mapa_hh.esta_dentro_da_hh(
                self.ctx.memory.position()),
            teto=TETO_DA_SAIDA,
            passo=PASSO_DA_ESPERA_DA_ENTRADA,
            o_que="Saída da HH",
        )

    def esperar_entrar(self) -> bool:
        """Espera a troca de mapa depois do clique. Sai no instante em que entra."""
        return self.esperar_a_chegada(
            chegou=lambda: mapa_hh.esta_dentro_da_hh(self.ctx.memory.position()),
            teto=TETO_DA_ENTRADA,
            passo=PASSO_DA_ESPERA_DA_ENTRADA,
            o_que="Entrada na HH",
        )
