"""
Rotina boss-rush da Bewitcher Cave, como máquina de estados CONSCIENTE DE ONDE ESTÁ.

=========================================================================
O CICLO
=========================================================================

    SITUAR ......... olha onde o personagem está e entra no estado certo
    PREPARAR ....... pet, buffs, câmera
    ATE_A_ENTRADA .. Transport Fay -> Ghost Din Woods -> caminha até o
                     Skull Herald, na coordenada (1395,-635)
    ENTRAR ......... monta o time de reset, View Reset, e insiste em entrar
                     A CADA ~1 SEGUNDO enquanto continuar do lado de fora
    CURAR .......... sai do time e cura, se fizer falta -- já DENTRO da cave
    ATE_O_ALTAR .... 58 waypoints até o patamar do Altar Stone (218,45)
    ENTRAR_NO_COVIL  Altar Stone -> "Secret Cemetery"
    ATE_OS_GUARDAS . (187,-405) -> (104,-406)
    GUARDAS ........ desmonta, mata os quatro mobs (sem AoE) e senta 4 s
    ATE_O_BOSS ..... (80,-406)
    BOSS ........... luta, com as duas fases
    SAIR ........... (81,-398) -> Skull Herald -> "Leave Bewitcher Cave"
    MANUTENCAO ..... se a bolsa apertou (espaço livre abaixo da folga):
                     cidade, venda, recompra
    -> volta a ATE_A_ENTRADA

Ignorar todos os mobs do caminho é o ponto do desenho: nenhum mob do trajeto é
atacado, o que reduz drasticamente o tempo por run e o risco de morrer em pack.
Só morrem os quatro guardas do covil e o boss.

=========================================================================
A REGRA QUE MUDOU TUDO: NUNCA AGIR SEM SABER ONDE ESTÁ
=========================================================================

Antes, cada estado assumia que o anterior terminou onde deveria. Isso quebra na
primeira interferência -- e interferência é a regra, não a exceção: lag, rollback,
o próprio jogador clicando no mapa, um teleporte que não pegou.

Agora TODO estado começa perguntando onde o personagem está
(`RastreadorDeLocal`) e, quando a resposta não é o esperado, se corrige antes de
executar qualquer clique. Isso vale dentro e fora da cave:

  * fora da rota da cave  -> retoma pelo waypoint mais próximo (respeitando a
                             geometria apertada do Secret Altar);
  * saiu da coordenada da entrada durante as tentativas -> volta para ela;
  * está dentro da cave quando esperava estar fora -> pula direto para a
                             travessia, sem tentar entrar de novo;
  * está na cidade quando esperava estar em Ghost Din Woods -> refaz o
                             transporte.

E o mais importante: NADA disso depende de o nome do lugar ser legível. Ele já
falhou duas vezes em produção; a coordenada nunca falhou.

=========================================================================
DECISÕES DE TEMPO
=========================================================================

* A entrada é DISPUTADA. A tentativa custa ~1 s (ver `ui_service`), e não os 10
  a 14 s da versão anterior -- nesse tempo outra conta entra no seu lugar.
* A CURA acontece DEPOIS de entrar, não antes de sair. A espera para entrar
  regenera vida de graça; curar antes gastaria poção que a espera devolveria.
* O PET não é alimentado dentro da cave (exige desmontar). Se a comida está perto
  de vencer, ele é alimentado ANTES de entrar.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from enum import Enum, auto

from ...config import CAVE_BC
from ...core import (
    calibracao,
    catador,
    diario,
    esconder_jogadores,
    logmodo,
    stats_diarias,
    vision,
)
from ...core.cronometro import cronometro
from ...core.lugares import LUGAR_FORA_DA_CAVE
from ...core.quedas import frase_do_tempo
from ...core.vision import capture_window, find_template, frame_is_blank
from .. import hotbar
from ..context import BotContext, Disconnected, FarmDesligado, StopRequested
from ..mural import reseter_online, silencio_do_reseter
from ..navegacao import Navigator, PersonagemMortoNoPortao
from ..team import TeamService
from ..watchdog import DcReason, Watchdog
from . import mapa_bc
from .combat import CombatEngine
from .localizacao import RastreadorDeLocal
from .ui_service import TOLERANCIA_DO_NPC_DA_ENTRADA, UIService
from .vendor import VendorService

# Nome que o jogo mostra do lado de FORA da cave, na porta dela.
# Vem do catálogo para não existirem duas grafias do mesmo nome: é o mesmo lugar
# que `localizacao.py` força quando o X denuncia o nome preso.
LOCAL_DA_ENTRADA = LUGAR_FORA_DA_CAVE

# ===========================================================================
# O ORÇAMENTO DA DISPUTA -- seis tentativas em dez segundos
# ===========================================================================
#
#     10,00 s / 6 tentativas ............ 1,667 s por volta
#     ação mecânica medida .............. 1,060 s   (é do jogo, não encurta)
#     ----------------------------------------------
#     para reconhecer e reagir ..........   0,607 s
#
# Os dois números abaixo dividem esses 0,607 s, e a soma deles é o que não pode
# passar de 0,60. Não é preferência, é a aritmética da meta.
#
# JANELA: por quanto tempo perguntar "entrei?" depois de mandar o pedido. Meio
# segundo cobre a ida e volta do servidor com folga, e o pedido foi explícito:
# reconhecer em menos de 500 ms.
JANELA_DE_RECONHECIMENTO = 0.25

# PASSO: de quanto em quanto tempo perguntar, dentro da janela. A pergunta é uma
# leitura de memória (posição e nome do lugar), custa microssegundos -- por isso
# dá para repeti-la doze vezes por janela em vez de esperar cego.
PASSO_DO_RECONHECIMENTO = 0.04

# E O INTERVALO ENTRE TENTATIVAS quase desaparece: a janela de reconhecimento já
# é a espera, e ela termina no instante em que a resposta chega. Isto aqui é só
# uma folga mínima para o cliente respirar entre duas rajadas de cliques -- com o
# jitter de sempre, porque cadência perfeitamente regular é assinatura.
#
# Era 0,35 s, somados a outros 0,35 s dormidos dentro da tentativa depois do
# clique no link. Os dois eram cegos: entrar em 50 ms só era percebido 700 ms
# depois.
ESPERA_ENTRE_TENTATIVAS = 0.025

# Teto de tempo insistindo na entrada. Duas horas é muito de propósito: o caminho
# de volta até a porta custa teleporte, caminhada e moedas, então abandonar é
# sempre pior que insistir. O que interrompe de verdade é parar o bot, cair a
# conexão ou o personagem sair do lugar.
MAX_SEGUNDOS_ENTRADA = 1 * 60 * 60.0

# Cadência da espera pela conta de reset (ver `_esperar_o_reseter`).
#
# NÚMERO DERIVADO, não medido: quem responde é uma leitura de dicionário em
# memória, então o custo de perguntar é zero e o passo poderia ser bem menor. Um
# segundo é o suficiente porque a trava dura minutos (um relogin inteiro), não
# milissegundos -- e é `ctx.tick`, então o Parar continua sendo instantâneo.
PASSO_DA_ESPERA_DO_RESETER = 1.0

# De quanto em quanto tempo repetir o aviso enquanto a trava dura.
#
# NÚMERO COSMÉTICO, sem medição atrás. Existe porque uma linha escrita quarenta
# minutos atrás não avisa ninguém: quem olha a tela no meio da trava precisa ver
# por que a conta está parada sem ter que rolar o log para trás.
INTERVALO_DO_AVISO_DO_RESETER = 300.0

# A cada quantas tentativas o log conta como vai a disputa. Uma linha por
# tentativa a cada segundo afogaria o resto do log.
TENTATIVAS_POR_LINHA_DE_LOG = 15

# Quantas tentativas de clique no Altar Stone por CICLO, antes do vai-e-volta.
#
# O ritmo é: este número de tentativas, vai-e-volta por (231,45), este número de
# tentativas de novo, e assim por diante. O vai-e-volta é o descanso ENTRE ciclos --
# ele não substitui as tentativas, ele as reinicia.
#
# Ver a contagem em `_do_entrar_no_covil`: ela REINICIA depois de cada vai-e-volta.
# Sem reiniciar, o contador ficava acima do limite para sempre e o personagem
# passava a andar entre as duas coordenadas fazendo uma tentativa por viagem.
TENTATIVAS_ANTES_DE_DESENCALHAR = 6

# A precisão exigida no patamar mora em `mapa_bc.PRECISAO_NO_PATAMAR_DO_ALTAR`.
# Ela saiu daqui porque o `ui_service` também precisa dela: os dois lados -- quem
# ANDA até o ponto e quem CONFERE antes de clicar -- têm que ler o mesmo número
# por construção. Ver o comentário lá, e o incidente da tolerância 3.

# Orçamento do ajuste fino do patamar: quantos `goto` apertados tentamos e por
# quanto tempo cada um.
#
# MAIS TENTATIVAS, CADA UMA MAIS CURTA (era 4 x 8 s = até 32 s). O caso normal é
# andar 1 ou 2 unidades, medido em 1 a 2 segundos -- oito segundos por tentativa
# era orçamento para um trajeto que não existe. O teto novo é 18 s com 50% mais
# chances, e cada falha volta ao laço mais rápido.
TENTATIVAS_DE_ENCOSTAR_NO_ALTAR = 6
SEGUNDOS_POR_TENTATIVA_NO_ALTAR = 1.5

# Quão perto do ponto do boss conta como "estou no waypoint".
#
# É o primeiro passo da sequência que autoriza sair da cave, e ele é conferido a
# cada volta do estado BOSS -- que se repete quando a luta não fecha. Frouxo de
# propósito: o personagem se mexe durante a luta, e exigir precisão aqui faria o
# bot refazer a caminhada por dois passos de deslocamento. É o mesmo valor que o
# SITUAR usa para reconhecer o ponto do boss.
TOLERANCIA_DO_PONTO_DO_BOSS = 15

# ===========================================================================
# USO DO PACKAGE_COURAGE (pós-boss, ANTES de ativar a montaria e sair)
# ===========================================================================
#
# O boss sempre dropa esse item ao morrer. Este passo, que roda só no ramo de
# VITÓRIA do `_do_boss`, abre o inventário com a tecla JÁ configurada do usuário
# (`keys.inventory`), acha TODOS os `package_courage` na tela por template
# matching e clica com o BOTÃO DIREITO no centro de cada um -- o jogo usa o item
# e ele some da bolsa. É um COMPLEMENTO do fluxo, nunca derruba a run.
#
# Nome do template (o arquivo em `data/templates/`). Foi renomeado de
# `packege_courage` (grafia errada) para `package_courage` a pedido do usuário.
TEMPLATE_PACKAGE_COURAGE = "package_courage.png"

# Carinha amarela no fim da barra de digitação do chat. Ela SÓ existe com o chat
# aberto, e é por isso que o template é ela e não a barra inteira: ao lado do
# `say:` fica o texto digitado, que muda -- um template com texto variável
# envelhece na primeira mensagem. Ver `core/esconder_jogadores.py`.
TEMPLATE_CHAT_ABERTO = "state_chat_aberto.png"

# Botão "Pick up all" da janela de loot. É ELE que autoriza o clique esquerdo do
# catador, e é o SUMIÇO dele que diz "pegou tudo" -- palavras do usuário. Achar
# por imagem em vez de coordenada fixa é o que torna o clique seguro por
# construção: sem botão na tela, não há clique.
TEMPLATE_PICK_UP_ALL = "btn_pick_up_all.png"

# ===========================================================================
# CANDIDATOS DO `ADDR_LOOT_WINDOW`, para a calibração
# ===========================================================================
#
# O endereço em uso é herdado do GhostBot na versão **6139** do cliente e nunca
# foi confirmado nesta (6400) -- é por isso que `loot_window_open()` não decide
# nada e vai só para o log.
#
# O candidato `+0x60` é o deslocamento MEDIDO entre as duas versões
# (`core/rebase.py`), e é o mesmo padrão que já explicou três endereços
# "quebrados neste cliente".
#
# O gabarito é o botão "Pick up all" na tela, que é o único lugar do bot onde a
# resposta certa está desenhada. Ver `_provar_a_janela_de_loot`.
CANDIDATOS_DA_JANELA_DE_LOOT = (0x0105B958, 0x0105B9B8)
# Limiar do botão. 0.85 e não 0.90: é um botão de UI com texto, e o fundo atrás
# dele muda com a cena. Falso NEGATIVO aqui só faz o catador desistir; falso
# POSITIVO faria um clique esquerdo cair na cena 3D, então na dúvida o limiar
# fica do lado que erra para menos.
LIMIAR_DO_PICK_UP_ALL = 0.85
# Limiar do casamento da carinha. Alto porque ela é um ícone pequeno e fixo: no
# quadro real ela casou a 1.00 e não casou em NENHUM outro lugar da tela, mesmo
# a 0.95. Um limiar frouxo aqui é pior que um apertado -- falso positivo faria o
# bot achar que o chat está aberto e apertar Enter, ABRINDO o que estava fechado.
LIMIAR_DO_CHAT_ABERTO = 0.90

# Rodadas de "procurar -> clicar em todos -> reconferir".
#
# O CLIQUE EM LOTE É SEGURO, e isso é uma propriedade do jogo que vale registrar
# porque é fácil supor o contrário: NO INVENTÁRIO OS SLOTS NÃO SE MEXEM. Cada
# item fica onde está, e usar um não faz os outros subirem. Quem reorganiza é o
# usuário, à mão.
#
# O deslocamento de slot existe, mas na GRADE DE VENDA do NPC -- é lá que tirar
# um item faz os seguintes subirem, e é por isso que o `vendor` clica sempre na
# mesma posição. Importar aquela mecânica para cá levaria a clicar um item por
# captura, que é três vezes mais lento sem ganho nenhum.
#
# Então: uma captura, todos os cliques. Se numa rodada não achar mais nenhum
# item, para antes.
RODADAS_DE_USO_DO_PACKAGE = 5

# Se a captura do inventário vier preta/None por estas vezes seguidas, NÃO é
# "sumiu" -- é "não consegui ver". Abandona sem confirmar e segue o fluxo
# normal (Q7 do grilling).
CAPTURAS_INVALIDAS_PACKAGE = 3

# Limiar do casamento EM COR do ícone do item.
#
# Não é o limiar geral da visão (0.87), e a diferença tem medição por trás.
# Remedido com o template atual (`package_courage.png`, 27x33, recortado à mão
# pelo usuário e SEM PERDA -- antes era um .jpeg):
#
#   item VERDADEIRO com ruído e variação de brilho ..... 0.971 a 0.999
#   item de MESMA FORMA e cor diferente (matiz girado) . 0.583 a 0.878
#
# Sobra um vão limpo entre 0.88 e 0.97, e 0.92 fica no meio dele.
#
# A TROCA PARA PNG ALARGOU ESSE VÃO. O template antigo era JPEG, e o dano da
# compressão já vinha gravado nele -- o pior caso do item verdadeiro caía para
# 0.934. Com PNG no template e a captura por BitBlt (também sem perda), não há
# mais compressão em lugar nenhum do caminho, e o pior caso sobe para 0.971.
#
# EM CINZA ESSE VÃO NÃO EXISTE: os mesmos distratores marcam 0.932 a 0.989, ou
# seja, passam por qualquer limiar que ainda aceite o item verdadeiro. É por isso
# que este passo usa `load_color` + `colorido=True`.
LIMIAR_DO_PACKAGE_EM_COR = 0.92

# Quanto esperar a bolsa CONFIRMAR que abriu, lendo a memória.
#
# `bag_open()` é uma leitura de ponteiro, não de imagem: ela diz se a janela da
# bolsa está aberta sem depender de captura de tela. É a trava mais forte que
# existe aqui, porque impede o clique ANTES dele acontecer -- diferente da trava
# de posição, que só percebe o erro depois do personagem já ter dado um passo.
#
# ERA 2.0, E OS DOIS SEGUNDOS ERAM GASTOS INTEIROS, TODA RUN. Medido no log de
# dev: o aviso "não consegui confirmar pela memória que a bolsa abriu" apareceu
# em 5 de 5 runs -- `bag_open()` nunca responde True neste cliente. A trava
# continua aqui porque vale de graça SE a leitura voltar a funcionar (outro
# cliente, outra build), mas não se paga esperar por ela: as travas 2 (posição a
# cada clique) e 3 (progresso por rodada) é que seguram o passo, e nenhuma delas
# depende da memória.
SEGUNDOS_ESPERANDO_A_BOLSA = 0.2

# ===========================================================================
# OS TEMPOS DESTE PASSO -- por que são pequenos, e o que os mantém seguros
# ===========================================================================
#
# O passo estava levando 3 a 4 s por run (medido em 6 runs do log de dev), e
# quase tudo era espera fixa: a busca em si custa 33 ms. Medido:
#
#   find_all_templates EM COR, janela inteira 1024x768, template 27x33
#       ................................................. 33 ms
#   find_all_templates em cinza (para comparar) ......... 12 ms
#
# Ou seja: o reconhecimento nunca foi o custo, e por isso NADA nele foi tocado --
# continua em cor, no mesmo limiar medido, varrendo a janela inteira. O que
# encolheu foram as esperas, e cada uma delas tem agora um motivo próprio em vez
# de uma folga genérica.
#
# A REGRA QUE TORNA ISSO SEGURO: onde havia espera fixa "para dar tempo", agora
# se PERGUNTA. A bolsa não é esperada por um tempo arbitrário -- ela é
# consultada na memória até responder que abriu. Perguntar rápido é barato
# (`bag_open` é leitura de ponteiro); esperar às cegas é que era caro.

# De quanto em quanto tempo perguntar se a bolsa já abriu. Era 0,15 s, o que
# atrasava a descoberta em até 0,15 s por nada: a leitura custa microssegundos.
PASSO_DA_ESPERA_DA_BOLSA = 0.050

# Depois que a MEMÓRIA confirma a bolsa aberta, o quanto esperar o DESENHO dela.
# São coisas diferentes: o estado muda antes de a janela estar pintada, e capturar
# no meio da pintura faz o template não casar. Também é a espera antes de cada
# reconferência -- ali ela cobre o item SUMINDO da bolsa depois do uso.
ASSENTAMENTO_DA_BOLSA = 0.140

# Entre um clique direito e o seguinte. Curto porque o clique deste bot é
# SÍNCRONO (`SendMessageW`): quando a chamada volta, o cliente já processou a
# mensagem. Esta pausa não existe para "dar tempo do clique chegar" -- existe
# para não emendar dois cliques no mesmo milissegundo.
ENTRE_CLIQUES_NO_PACKAGE = 0.050

# Depois de fechar o inventário. Nada depende deste tempo -- o passo seguinte é
# montar e sair da cave --, então é só o mínimo para a tecla não emendar na
# próxima ação.
DEPOIS_DE_FECHAR_A_BOLSA = 0.050


# DUAS PERGUNTAS DIFERENTES sobre a mesma coordenada, e por isso dois números.
#
# 1. "ESTOU PERTO DA ENTRADA?" -- decide se dá para pular o transporte e ir direto
#    tentar entrar, em vez de refazer o trajeto por Stone City. É uma pergunta
#    grossa, e 12 unidades respondem bem.
TOLERANCIA_DA_ENTRADA = 12

# 2. "POSSO CLICAR NO SKULL HERALD?" -- o diálogo dele só abre de (1395,-635).
#    Aqui 12 é frouxo demais: a 12 unidades o clique já cai no chão, o personagem
#    anda, e a tentativa seguinte erra por estar ainda mais longe.
#
#    O número mora no `ui_service`, junto do clique que ele protege, e é o mesmo
#    que `garantir_coordenada_da_entrada` usa. Importar em vez de repetir: dois
#    valores para a mesma pergunta divergiriam em silêncio, e o sintoma seria o bot
#    achando que pode clicar enquanto a outra metade do código sabe que não.
LIMITE_PARA_VOLTAR = TOLERANCIA_DO_NPC_DA_ENTRADA

# As RODADAS DE LIMPEZA DOS GUARDAS saíram junto com a contagem de mortes.
#
# Elas existiam para garantir que os quatro guardas estivessem com HP ZERO antes de
# ir para a coordenada do boss -- uma rodada só podia terminar com um guarda vivo
# se a mira se perdesse. Isso pressupunha ler o endereço e o HP de cada guarda, que
# é justamente o que o fluxo por flag de combate não faz.
#
# Quem responde "acabou" agora é a flag desligar de forma confirmada. Não há mais o
# que repetir: ou a flag baixou (todos caíram) ou o prazo estourou, e nesse caso
# repetir a fase não ajudaria -- o problema seria a flag, não a mira.


class State(Enum):
    SITUAR = auto()
    PREPARAR = auto()
    ATE_A_ENTRADA = auto()
    ENTRAR = auto()
    CURAR = auto()
    ATE_O_ALTAR = auto()
    ENTRAR_NO_COVIL = auto()
    ATE_OS_GUARDAS = auto()
    GUARDAS = auto()
    ATE_O_BOSS = auto()
    BOSS = auto()
    SAIR = auto()
    MANUTENCAO = auto()
    RECUPERAR = auto()


# Estados que acontecem DENTRO da instância, com os mobs da cave vindo atrás.
# Ali o bot corre com pausas mínimas entre estados; fora da cave não há pressa e
# folga de tempo é preferível.
ESTADOS_DENTRO_DA_CAVE = frozenset({
    State.CURAR, State.ATE_O_ALTAR, State.ENTRAR_NO_COVIL,
    State.ATE_OS_GUARDAS, State.GUARDAS, State.ATE_O_BOSS, State.BOSS,
    State.SAIR,
})


# Quantas rodadas de "não vendeu ⇒ roda mais uma run de BC ⇒ tenta de novo"
# antes de desligar o BC da conta. Número do usuário (18/08/2026).
#
# A run de BC no meio não é espera: ela troca de mapa, e é a troca de mapa que
# reescreve o nome do lugar -- a leitura que fica presa na área anterior e faz o
# bot achar que não está em Stone City. Ver `bot/bc/localizacao.py`.
RODADAS_DE_VENDA_ANTES_DE_DESLIGAR = 3


class BossRushRoutine:
    """Executa ciclos de boss-rush até parada ou desconexão."""

    def __init__(self, ctx: BotContext) -> None:
        self.ctx = ctx
        self.local = RastreadorDeLocal(ctx.memory, ctx.log, ctx.account_login)
        self.nav = Navigator(ctx, mapa_bc)
        self.combat = CombatEngine(ctx, self.nav)
        # LIGA O PORTAO DA MONTARIA NO COMBATE. Em batalha o jogo recusa montar,
        # e o portao insiste sem teto -- foi assim que a run de 31/08 ficou 24
        # minutos parada no waypoint dos Gun Witch (ver o bloco "DESTRAVAMENTO"
        # no topo de `combat.py`). A rotina e quem pode fazer esta ligacao:
        # `combat` ja importa `navigation`, e o contrario faria ciclo.
        self.nav.destravar_o_combate = self.combat.limpar_o_combate
        self.vendor = VendorService(ctx, self.nav)
        # O nick do BC é o padrão do `TeamService`; passar explícito
        # deixa as duas caves simétricas e o leitor sem dúvida.
        self.team = TeamService(
            ctx, nick_do_reset=lambda: ctx.settings.bc.reset_nick)
        # Um navegador só por conta, compartilhado. Ele guarda o cronômetro da
        # tecla da montaria e a recarga da skill de velocidade; duplicá-lo faria
        # dois donos do mesmo interruptor.
        self.ui = UIService(ctx, self.nav)
        self.watchdog = Watchdog(ctx)
        # O watchdog também vive no ctx, para que `tick()` (chamado por todos os
        # laços de combate e navegação) consiga detectar quedas no meio de uma fase
        # sem depender do `_guard()` rodar no topo do laço principal.
        ctx.watchdog = self.watchdog
        self.state = State.SITUAR
        self.consecutive_failures = 0
        # Índice por onde retomar o caminho até o altar. Diferente de zero quando
        # o bot descobre que o personagem já está no meio da cave -- refazer o
        # trajeto do começo seria andar de ré por meia cave.
        self._retomar_altar_em = 0

        # A SEQUÊNCIA DO BOSS SE COMPLETOU NESTA RUN?
        #
        # É a única autorização para sair da cave, e ela registra um FATO
        # observado: o personagem estava no waypoint do boss, ENTROU em batalha e
        # SAIU de batalha. Nem coordenada nem nome de lugar substituem isso -- o
        # NPC de saída fica a oito unidades do boss, e decidir por distância ali
        # já mandou o bot embora com o boss vivo.
        #
        # Zerado ao entrar na cave: cada instância tem a sua própria sequência.
        #
        # LIMITAÇÃO HONESTA: começa em False quando o bot é ligado. Se o processo
        # for reiniciado com o personagem já dentro do covil e o boss JÁ MORTO, o
        # bot vai ao waypoint do boss e espera -- sem prazo, porque foi assim que
        # a espera foi pedida. O aviso periódico no log é o que torna isso visível.
        self._boss_derrotado = False

        # Tentativas de abrir o portal do Altar Stone nesta ida. A partir da
        # segunda, cada tentativa é precedida do vai-e-volta por (231,45).
        self._tentativas_no_altar = 0

        # Posição do personagem no clique ANTERIOR no Altar Stone. Serve para
        # saber se ele andou entre uma tentativa e outra -- e só forçar o View
        # Reset quando andou.
        self._posicao_do_ultimo_clique_no_altar: tuple[int, int] | None = None

        # Contagem de runs do gatilho de venda ("vender a cada N runs"). Guarda
        # em que run a última venda aconteceu; a diferença para `ctx.stats.runs`
        # é o que `_seguir_depois_de_sair` compara com `runs_before_selling`.
        # **Why 0**: no `run()` a base é repetida para `ctx.stats.runs` no começo
        # de cada execução, então a contagem só conta dali pra frente e volta a
        # zero quando a execução do bot BC termina (uma nova `run()` recomeça).
        self._runs_na_ultima_venda = 0
        # Rodadas de "não vendeu ⇒ mais uma run de BC ⇒ tenta de novo".
        # POR EXECUÇÃO DO BOT, como a contagem de runs do gatilho ao lado, e
        # zerada quando uma venda dá certo (ver `_do_manutencao`).
        self._rodadas_de_venda_falhas = 0

    # ==================================================================
    # Utilidades
    # ==================================================================

    def _guard(self) -> None:
        """Checa parada e saúde da sessão. Levanta se algo está errado."""
        self.ctx.raise_if_stopped()
        state = self.ctx.snapshot()
        reason = self.watchdog.check(state)
        if reason is not DcReason.NONE:
            raise Disconnected(reason.value)
        if state.dead:
            self.ctx.log.warning("Personagem morto detectado")
            self.state = State.RECUPERAR

    def _fail(self, message: str, next_state: State = State.RECUPERAR) -> None:
        self.consecutive_failures += 1
        self.ctx.log.warning("%s (falha %s)", message, self.consecutive_failures)
        self.state = next_state

    def _succeed(self, next_state: State) -> None:
        self.consecutive_failures = 0
        self.state = next_state

    def _situacao(self, marco: str | None = None):
        """Releitura de onde o personagem está, registrada no diário."""
        return self.local.atualizar(marco)

    # ==================================================================
    # SITUAR -- a inteligência que evita refazer o que já está feito
    # ==================================================================

    def _do_situar(self) -> None:
        """Olha onde o personagem está e entra no estado que faz sentido.

        Roda no começo do ciclo e sempre que algo sai do roteiro. É o que evita as
        duas bobagens mais caras:

          * REFAZER o que já está feito. Se o personagem já está em Ghost Din
            Woods na coordenada da entrada, abrir o painel de arredores e
            caminhar até o Skull Herald é gasto puro -- ele já está lá.
          * AGIR DO LUGAR ERRADO. Tentar entrar na cave estando DENTRO dela faz o
            clique cair no chão e o personagem sair andando da rota.

        A decisão é pela COORDENADA, não pelo nome do lugar: a coordenada nunca
        falhou nos logs e o nome já falhou duas vezes.
        """
        ctx = self.ctx
        s = self._situacao("situando")

        if not s.confiavel:
            ctx.log.warning(
                "Não consigo ler a posição do personagem; não dá para decidir o "
                "que fazer. Aguardando a memória."
            )
            ctx.tick(1.0)
            return

        ctx.log.info("Situando: %s", s.resumo())

        if s.dentro_da_cave:
            self._situar_dentro_da_cave(s)
            return

        self.local.esperar(LOCAL_DA_ENTRADA)

        if self.local.na_entrada_da_cave(TOLERANCIA_DA_ENTRADA):
            ctx.log.info(
                "Já estou na coordenada da entrada %s — não preciso do painel de "
                "arredores nem caminhar até o NPC. Vou direto tentar entrar.",
                mapa_bc.ENTRADA_EM_GHOST_DIN,
            )
            self._succeed(State.ENTRAR)
            return

        self._succeed(State.PREPARAR)

    def _situar_dentro_da_cave(self, s) -> None:
        """Já estou dentro: descobre em que trecho e retoma dali.

        A divisão é pela coordenada porque as duas metades da cave ficam em
        pedaços de mapa bem distantes: a travessia principal tem y entre -100 e
        180, e o covil do boss fica todo em y ≈ -400. Não há como confundir.
        """
        ctx = self.ctx
        pos = s.posicao
        ctx.log.info("Estou DENTRO da cave: %s", s.resumo())

        # -- covil do boss -------------------------------------------------
        if s.area == "Secret Cemetery" or (pos and pos[1] <= -350):
            # SÓ SAI SE O BOSS JÁ CAIU NESTA RUN.
            #
            # Esta era a segunda porta para fora da cave, e ela decidia por
            # DISTÂNCIA -- o que aqui não funciona: o NPC de saída está em
            # (81,-398) e o boss em (80,-406), a 8,06 unidades um do outro. Com um
            # raio de 8, um passo do personagem na direção do NPC bastava para o
            # bot achar que a run terminou e ir embora com o boss vivo.
            #
            # Quem responde agora é o registro do que ACONTECEU nesta run, não a
            # coordenada: a sequência waypoint -> entrar em batalha -> sair de
            # batalha.
            if (self._boss_derrotado
                    and mapa_bc.distancia(pos, mapa_bc.POSICAO_DA_SAIDA) <= 8):
                ctx.log.info("Estou no NPC de saída e o boss já caiu; saindo")
                self._succeed(State.SAIR)
                return
            if (mapa_bc.distancia(pos, mapa_bc.POSICAO_DO_BOSS)
                    <= TOLERANCIA_DO_PONTO_DO_BOSS):
                ctx.log.info("Estou na posição do boss; retomando a luta")
                self._succeed(State.BOSS)
                return
            if mapa_bc.distancia(pos, mapa_bc.POSICAO_DOS_GUARDAS) <= 15:
                ctx.log.info("Estou na posição dos guardas")
                self._succeed(State.GUARDAS)
                return
            ctx.log.info("Estou no covil, ainda no caminho até os guardas")
            self._succeed(State.ATE_OS_GUARDAS)
            return

        # -- travessia principal -------------------------------------------
        onde = mapa_bc.onde_retomar(pos, mapa_bc.CAMINHO_ATE_O_ALTAR)
        self._retomar_altar_em = onde.indice
        ctx.log.info(
            "Retomando a travessia pelo %s (de %s waypoints) — %s",
            onde.indice + 1, len(mapa_bc.CAMINHO_ATE_O_ALTAR), onde.motivo,
        )
        # Chegou ao patamar do Altar Stone: só falta o portal.
        if onde.indice >= len(mapa_bc.CAMINHO_ATE_O_ALTAR) - 1 and onde.distancia <= 10:
            self._succeed(State.ENTRAR_NO_COVIL)
            return
        self._succeed(State.ATE_O_ALTAR)

    # ==================================================================
    # PREPARAR
    # ==================================================================

    def _do_preparar(self) -> None:
        ctx = self.ctx
        ctx.log.info("Preparando personagem")

        ctx.char_name = ctx.memory.char_name()
        if ctx.start_gold is None:
            ctx.start_gold = ctx.memory.gold()
        if not ctx.stats.started_at:
            ctx.stats.begin_session()
            ctx.stats.gold_start = ctx.start_gold

        ctx.apply_camera()
        ctx.tick(0.2)

        # ==============================================================
        # A SEQUÊNCIA DE INICIALIZAÇÃO, NESTA ORDEM
        # ==============================================================
        #
        # A ordem não é preferência: cada passo depende do estado que o anterior
        # deixa. Montado, o jogo IGNORA a tecla de pet, de comida e de buff, e não
        # devolve erro nenhum -- o bot "aperta e nada acontece". E a montaria tem
        # que ser o último passo, senão os passos seguintes a desfazem.

        # 1. RESET DE ESTADO: desmontar APENAS se necessário para pet/comida.
        #
        # A montaria é toggle (duas teclas rápidas cancelam). Itens/skills são
        # ignorados enquanto montado (sem erro). Só desmonta se:
        #   - pet precisa ser invocado (summon_on_login=True E pet não ativo)
        #   - pet precisa comer (feed_on_start=True E nunca comeu / tempo passou)
        # Se nada disso for necessário, MANTÉM montado — evita ciclo desnecessário.
        # A ÚNICA COISA QUE AINDA DESMONTA FORA DA CAVE: pet inativo.
        #
        # Regra do usuário, 25/08/2026 -- *"fora da cave BC ele só vai sair da
        # mount caso o pet não esteja ativo"*. Comida e buff saíram daqui e
        # foram para o PREPARO DE ENTRADA (`_do_curar`), já dentro da cave.
        #
        # A exceção do pet é a certa: entrar sem pet significa invocar lá dentro,
        # e lá dentro parar para invocar é parar com o trem de mobs em cima.
        precisa_do_pet = (ctx.settings.pet.summon_on_login
                          and not ctx.memory.pet_active())
        if precisa_do_pet:
            ctx.log.info("Pet inativo: desmontando para invocar antes de sair")
            if ctx.memory.is_mounted():
                self.nav.ensure_dismounted()
            self.combat.ensure_pet()
        elif ctx.memory.is_mounted():
            ctx.log.info("Montaria ativa e o pet está de pé; mantendo montado")

        # A COMIDA NÃO É DADA AQUI. Mesmo com `feed_on_start`, ela espera o
        # preparo de entrada -- é lá que o personagem já está a pé por causa da
        # cura, e é lá que o desmonte é permitido.

        # 4. MONTARIA de volta, agora que nada mais exige estar a pé.
        montado = self.nav.garantir_montaria_para_andar(
            "sair para a rota depois do preparo")

        # 5. LIBERAÇÃO DO PATHING. O estado só avança aqui, e o log registra com
        #    que estado o deslocamento começa -- é a linha que explica um trajeto
        #    lento depois.
        ctx.log.info(
            "Preparo concluído | montaria=%s | pet=%s — liberando a navegação",
            montado, ctx.memory.pet_active(),
        )
        self._succeed(State.ATE_A_ENTRADA)

    # ==================================================================
    # ATE_A_ENTRADA
    # ==================================================================

    def _do_ate_a_entrada(self) -> None:
        """Vai até a coordenada da entrada da cave.

        O caminho é uma sequência de NPCs, não coordenadas:

            Transport Fay -> "Ghost Din Woods"  (teleporte, custa 7 moedas)
            Skull Herald  -> já é a entrada

        Cada etapa é PULADA se já estiver feita. Estar em Ghost Din Woods dispensa
        o transporte; estar na coordenada da entrada dispensa a caminhada. Fazer
        essas etapas por hábito custava um teleporte e uma travessia por volta.
        """
        ctx = self.ctx
        s = self._situacao("indo para a entrada")

        # Já está na porta: não há nada a fazer aqui.
        if self.local.na_entrada_da_cave(TOLERANCIA_DA_ENTRADA):
            ctx.log.info("Já estou na coordenada da entrada; pulando o trajeto")
            self._succeed(State.ENTRAR)
            return

        # A ALIMENTAÇÃO PRÉ-ENTRADA SAIU DAQUI em 25/08/2026.
        #
        # Ela existia porque "dentro da cave não dá: alimentar exige desmontar, e
        # desmontar no meio da travessia é parar com o trem de mobs em cima" -- e
        # isso continua verdade PARA A TRAVESSIA. Só que a comida não é dada no
        # meio da travessia: ela é dada no PREPARO DE ENTRADA (`_do_curar`), com
        # o personagem já dentro, ainda parado e já a pé para curar.
        #
        # Com isso o trajeto até a entrada não desmonta mais por comida --
        # cumprindo a regra de que fora da cave só se desmonta por pet inativo.
        # A cadência não escorrega: o `PetFeeder` ancora no vencimento, então
        # atrasar a refeição não empurra as seguintes.

        ja_em_ghost_din = (s.local == LOCAL_DA_ENTRADA
                           or s.local_lido == LOCAL_DA_ENTRADA)
        if not ja_em_ghost_din:
            ctx.log.info("Local atual: %r — usando o transporte",
                         s.local or "desconhecido")
            if not self.ui.viajar_para_ghost_din_woods():
                # ==================================================
                # "FALHOU" NÃO É "NÃO ESTOU EM STONE CITY" -- 25/08/2026
                # ==================================================
                #
                # Falhar aqui QUASE SEMPRE significa que o personagem não está em
                # Stone City, e o item de retorno é a recuperação certa nesse
                # caso: ele leva para a cidade de qualquer lugar do mundo.
                #
                # Só que "quase sempre" deixou passar o caso medido: dentro de
                # Stone City, o clique no NPC pegava outro alvo (o White Eagle no
                # print do usuário), o diálogo não abria, e esta recuperação
                # gastava o item -- desmontando, usando (já estava na cidade:
                # nada acontece) e remontando. O usuário viu isso e descreveu
                # certo: *"ele desce da montaria, não faz nada, fica um pouco
                # parado, volta para a montaria"*.
                #
                # A POSIÇÃO responde a pergunta que a falha do clique não
                # responde. Estando na cidade, a recuperação certa é tentar de
                # novo -- e o `_encostar_na_fay` agora resolve a causa.
                if mapa_bc.esta_em_stone_city(s.posicao, s.local):
                    ctx.log.warning(
                        "Não abri o transporte, mas ESTOU em Stone City "
                        "(posição %s). Não gasto item de retorno para ir aonde "
                        "já estou -- tentando de novo.", s.posicao)
                    self._fail("Não abri o diálogo da Fay estando em Stone City",
                               next_state=State.ATE_A_ENTRADA)
                    return

                ctx.log.warning(
                    "Não achei o transporte e a posição não é Stone City "
                    "(estou em %r, %s). Voltando para a cidade primeiro.",
                    s.local or "lugar desconhecido", s.posicao,
                )
                diario.registrar_evento(
                    ctx.account_login, "fora-do-caminho",
                    f"sem transporte disponível em {s.local!r}; "
                    "usando item de retorno",
                    s.posicao, s.local,
                )
                self.vendor.voltar_para_a_cidade()
                self._fail("Não consegui viajar para Ghost Din Woods",
                           next_state=State.SITUAR)
                return
            self._situacao("depois do transporte")
        else:
            ctx.log.info("Já estou em %s", LOCAL_DA_ENTRADA)

        self.nav.garantir_montaria_para_andar("ir até o NPC da entrada")
        if not self.ui.ir_ate_o_npc_da_cave():
            self._fail("Não cheguei no NPC da entrada da cave")
            return

        # CONFERE a chegada pela coordenada. O painel de arredores caminha até o
        # NPC, mas o trajeto pode ser interrompido -- e tentar entrar de longe faz
        # o clique cair no chão, o que só afasta mais o personagem.
        self._situacao("chegada na entrada")
        if not self.local.na_entrada_da_cave(TOLERANCIA_DA_ENTRADA):
            pos = self.local.situacao.posicao
            distancia = (mapa_bc.distancia(pos, mapa_bc.ENTRADA_EM_GHOST_DIN)
                         if pos else -1)
            ctx.log.warning(
                "O painel me deixou em %s, a %.0f unidades da entrada %s. "
                "Ajustando pelo minimapa.",
                pos, distancia, mapa_bc.ENTRADA_EM_GHOST_DIN,
            )
            if not self.nav.goto(mapa_bc.ENTRADA_EM_GHOST_DIN,
                                 tolerance=TOLERANCIA_DA_ENTRADA,
                                 max_seconds=60.0, usar_mapa=False):
                self._fail("Não alcancei a coordenada exata da entrada",
                           next_state=State.ATE_A_ENTRADA)
                return

        self._succeed(State.ENTRAR)

    # ==================================================================
    # ENTRAR
    # ==================================================================

    def _voltar_para_a_entrada(self) -> bool:
        """Traz o personagem de volta à coordenada de onde a cave pode ser aberta.

        Acontece de verdade: um clique que não pega no NPC pega no CHÃO, e clicar
        no chão faz o personagem andar. Depois de alguns desses ele está longe
        demais e todas as tentativas seguintes falham -- sem que nada no bot
        percebesse o motivo.
        """
        ctx = self.ctx
        pos = self.local.situacao.posicao
        ctx.log.warning(
            "Saí da coordenada da entrada (estou em %s, a entrada é %s). "
            "Voltando antes de tentar de novo.",
            pos, mapa_bc.ENTRADA_EM_GHOST_DIN,
        )
        diario.registrar_evento(
            ctx.account_login, "fora-da-entrada",
            f"a {mapa_bc.distancia(pos, mapa_bc.ENTRADA_EM_GHOST_DIN):.0f} "
            "unidades da porta da cave" if pos else "posição desconhecida",
            pos, self.local.situacao.local,
        )
        # VOLTA PELO PAINEL DE ARREDORES, e não caminhando pela coordenada.
        #
        # `nav.goto` chegava perto -- tolerância de 6 -- e perto não serve: o
        # diálogo do Skull Herald só abre de (1395,-635). Pior, `goto` anda por
        # clique no chão, que é exatamente o movimento que tira o personagem do
        # lugar quando erra o NPC. Corrigir o desvio com a ferramenta que o causa
        # era o que fazia a run girar em falso na porta da cave.
        #
        # O painel manda caminhar até o NPC, não até um par de números, e pousa no
        # ponto certo -- é assim que o personagem chega ali na primeira vez.
        ok = self.ui.garantir_coordenada_da_entrada()
        self.ui.preparar_entrada()
        return ok

    def _reconhecer_entrada(self, posicao_antes) -> bool:
        """Entrei? Responde em fatias curtas, sem espera fixa.

        É AQUI QUE O ORÇAMENTO DA DISPUTA SE CUMPRE. A meta de seis tentativas em
        dez segundos dá 1,667 s por volta; a ação mecânica custa 1,06 s medidos;
        sobram 0,60 s para reconhecer e reagir. Esta função é os 0,60 s.

        Antes havia uma espera fixa de 0,35 s DENTRO da tentativa (depois do clique
        no link) mais UMA leitura, e mais 0,35 s de intervalo entre tentativas.
        Duas esperas cegas somando 0,70 s, e a leitura só acontecia no fim da
        primeira -- ou seja, entrar em 50 ms era descoberto 350 ms depois.

        Agora a leitura é o relógio: `PASSO_DO_RECONHECIMENTO` de cada vez, até
        `JANELA_DE_RECONHECIMENTO`. Entrou, sai na hora; não entrou, a janela fecha
        e a próxima tentativa começa. A leitura é de memória -- posição e nome do
        lugar --, custa microssegundos, e é por isso que dá para repeti-la.
        """
        limite = time.time() + JANELA_DE_RECONHECIMENTO
        while True:
            self.ctx.raise_if_stopped()
            self.local.atualizar()
            if self.local.chegou_na_cave(posicao_antes):
                return True
            restante = limite - time.time()
            if restante <= 0:
                return False
            # DORME O QUE FALTA, não o passo inteiro. Sem esta conta a janela
            # passava do teto em até um passo -- 0,56 s em vez de 0,50 --, e com os
            # 0,05 s de intervalo o orçamento fechava em 0,61 s, acima dos 0,60
            # exigidos. Um passo de sobra é pouco por volta e muito em seis.
            self.ctx.tick(min(PASSO_DO_RECONHECIMENTO, restante))

    def _esperar_o_reseter(self) -> None:
        """Segura a entrada na cave enquanto a conta de reset não está no ar.

        =================================================================
        POR QUE ESPERAR É MELHOR QUE ENTRAR
        =================================================================

        Sem trocar de time o boss NÃO RENASCE: a instância continua com ele
        morto e a run inteira é perdida -- depois de já ter gasto o teleporte, a
        travessia e a disputa da entrada. Entrar sem reseter não é "entrar mais
        devagar", é jogar fora tudo que veio antes. Esperar, por pior que
        pareça, é sempre mais barato.

        Quem preencheu o `reset_nick` já declarou isso. Por isso não existe um
        interruptor separado para a trava: o campo em branco continua sendo o
        jeito de dizer "não uso reset de time".

        =================================================================
        ONDE ELA FICA, E POR QUE SÓ AQUI
        =================================================================

        Este é o ÚNICO ponto de trava, imediatamente antes do convite. A run em
        curso termina inteira -- boss, venda, viagem de volta -- e o personagem
        estaciona no ponto de entrada que ele já conquistou. Travar mais cedo
        (no meio do covil, por exemplo) perderia a run atual por causa de um
        problema que só afeta a PRÓXIMA, e o reseter só é necessário no instante
        da entrada.

        =================================================================
        "CAIU" E "NÃO EXISTE MAIS" SÃO ESTADOS DIFERENTES
        =================================================================

        Caiu é temporário por natureza: relogin é o comportamento padrão de toda
        conta, então ela volta sozinha e a espera tem fim. Já um reseter
        removido, desativado, desmarcado, posto para farmar ou aposentado por
        senha errada NÃO VOLTA -- esperar por ele seria uma conta parada a noite
        inteira sem nada acontecendo.

        Por isso a condição é reavaliada a cada volta e não só na entrada:
        `problema_do_reset` lê a configuração VIVA, e a configuração pode mudar
        com o bot rodando. Quando ela responde, o desfecho é o mesmo da venda
        sem tecla de retorno -- desliga o `bc_farm` desta conta e salva, o
        checkbox desmarca nas duas interfaces, e isso É o aviso.

        A espera é `ctx.tick`, nunca `time.sleep`: é o `tick` que mantém o
        watchdog DESTA conta vivo enquanto ela está parada (uma conta de BC
        também cai, e parada por horas ela ficaria cega para a própria queda) e
        é ele que dá as três saídas de graça -- Parar, desmarcar o BC farm
        (`FarmDesligado`) e ligar o modo APP.
        """
        ctx = self.ctx
        nick = ctx.settings.bc.reset_nick.strip()
        if not nick:
            return                              # esta conta não usa reset

        comecou = time.time()
        proximo_aviso = 0.0
        while True:
            ctx.raise_if_stopped()

            # Config VIVA: o reseter pode ter sido desmarcado, desativado ou
            # posto para farmar depois que a trava começou.
            problema = ctx.config.problema_do_reset(ctx.account)
            if problema is not None:
                ctx.account.bc_farm = False
                try:
                    ctx.config.save()
                except Exception as exc:
                    ctx.log.warning("Não consegui salvar a configuração: %s", exc)
                ctx.log.error(
                    "BC farm DESLIGADO nesta conta: %s. A conta continua "
                    "online e relogando; remarque o BC farm depois de "
                    "corrigir o reset de time.", problema,
                )
                # `bc_farm` acabou de virar False: o próprio `raise_if_stopped`
                # levanta `FarmDesligado` e devolve a conta ao estado "online".
                ctx.raise_if_stopped()
                return

            if reseter_online(nick):
                if proximo_aviso:               # só loga se chegou a travar
                    ctx.log.info(
                        "A conta de reset '%s' voltou. Parado %s esperando "
                        "por ela.", nick, frase_do_tempo(time.time() - comecou),
                    )
                return

            agora = time.time()
            if agora >= proximo_aviso:
                proximo_aviso = agora + INTERVALO_DO_AVISO_DO_RESETER
                silencio = silencio_do_reseter(nick)
                ctx.log.warning(
                    "Parado na porta da cave: a conta de reset '%s' não está no "
                    "ar (%s). Sem ela o boss não renasce, então não entro. "
                    "Volto sozinho quando ela reconectar — parado há %s.",
                    nick,
                    "nunca subiu nesta execução" if silencio is None
                    else f"sem responder há {silencio:.0f}s",
                    frase_do_tempo(agora - comecou),
                )
            ctx.tick(PASSO_DA_ESPERA_DO_RESETER)

    def _do_entrar(self) -> None:
        """Entra na cave, insistindo a cada ~1 segundo.

        A BC é DISPUTADA: várias contas tentam ao mesmo tempo e a vaga é de quem
        clica primeiro. Por isso a tentativa foi encurtada para cerca de um
        segundo (ver `ui_service.tentar_entrar_na_cave`) e o laço não dorme mais
        que isso entre elas.

        O TIME É MANTIDO durante todas as tentativas. Ele existe para que a
        instância criada seja NOVA -- sem trocar de time o boss não renasce -- e a
        instância é criada no instante em que a entrada dá certo. Sair do time
        antes disso desperdiçaria o reset. Só depois de confirmar que está dentro
        é que o time é desfeito, porque o boss-rush é solo.
        """
        ctx = self.ctx
        ctx.log.info("Entrando na cave")

        # Esconder jogadores ANTES de qualquer coisa da entrada. Se o truque
        # deixar o chat aberto, entrar seria perder a run em silêncio -- então
        # ele é a única coisa aqui que pode ABORTAR a entrada.
        if not self._esconder_jogadores():
            self._fail("o chat ficou aberto ao esconder jogadores")
            return

        # O cronômetro da run (RunStats.begin_run) NÃO começa aqui. A disputa
        # da entrada pode levar vários minutos (instância cheia), e o usuário
        # quer o tempo contando só a partir do momento em que o bot CONFIRMA
        # que está dentro. O begin_run foi movido para logo depois do laço,
        # junto com o sair_do_time -- ver abaixo.

        # O PORTÃO DO RESETER vem ANTES do convite, e é o único ponto do bot
        # que segura a entrada. Ver `_esperar_o_reseter`.
        self._esperar_o_reseter()

        # Chegamos na coordenada: é AQUI que o time de reset é montado, e não
        # antes. Mais cedo, o convite podia expirar durante o teleporte.
        self.team.montar_time()

        # View Reset e esquecimento das coordenadas da run anterior.
        self.ui.preparar_entrada()

        antes = ctx.memory.position()
        limite = time.time() + MAX_SEGUNDOS_ENTRADA
        tentativa = 0

        while time.time() < limite:
            ctx.raise_if_stopped()
            tentativa += 1

            # ANTES de clicar: continuo onde a cave pode ser aberta?
            s = self._situacao()
            if s.dentro_da_cave:
                # Entrou numa tentativa anterior e o bot só descobriu agora.
                ctx.log.info("Já estou dentro da cave (%s)", s.resumo())
                break
            if s.posicao is not None:
                distancia = mapa_bc.distancia(s.posicao,
                                              mapa_bc.ENTRADA_EM_GHOST_DIN)
                if distancia > LIMITE_PARA_VOLTAR:
                    self._voltar_para_a_entrada()
                    continue

            # `False` = a MECÂNICA falhou (o diálogo não abriu, o clique não
            # pegou). `True` = os dois cliques saíram e o pedido foi feito.
            cliques_sairam = self.ui.tentar_entrar_na_cave()

            if self._reconhecer_entrada(antes):
                s = self.local.situacao
                ctx.log.info(
                    "DENTRO da cave na tentativa %s (%.0fs de disputa) | %s",
                    tentativa, time.time() - (limite - MAX_SEGUNDOS_ENTRADA),
                    s.resumo(),
                )
                self.local.atualizar("entrei na cave")
                break

            # SÓ A FALHA MECÂNICA CONTA para a redescoberta. Instância cheia é a
            # razão normal de não entrar, e redescobrir por causa dela custava 5 a
            # 10 s no meio da disputa -- ver `ui_service.registrar_falha_de_entrada`.
            if not cliques_sairam:
                self.ui.registrar_falha_de_entrada()

            if tentativa % TENTATIVAS_POR_LINHA_DE_LOG == 0:
                ctx.log.info(
                    "Ainda do lado de fora depois de %s tentativas (%s).",
                    tentativa, self.local.situacao.resumo(),
                )
            ctx.tick(ESPERA_ENTRE_TENTATIVAS)
        else:
            self._fail(
                f"Não entrei na cave em {MAX_SEGUNDOS_ENTRADA / 60:.0f} min "
                f"({tentativa} tentativas)",
                next_state=State.ATE_A_ENTRADA,
            )
            return

        # A instância nova já existe: o reset está consumado e o time pode (e
        # deve) ser desfeito. Só agora -- e é por isso que sair do time é o
        # primeiro passo depois de confirmar a entrada.
        self.team.sair_do_time()

        # O CRONÔMETRO NÃO COMEÇA AQUI -- ele começa no fim do PREPARO DE
        # ENTRADA, quando o personagem monta para sair andando (`_do_curar`).
        #
        # Ordem do usuário, 25/08/2026: *"os timers de Tempo do 'estatísticas BC'
        # hoje começam a contar a partir do momento que entrou; vamos mudar,
        # vamos contar a partir do momento que terminar esse processo inicial --
        # se cura, usa as skill, dá comida ao pet e afins; aí no momento que
        # ativar a montaria novamente para andar, você começa a contagem"*.
        #
        # O que ficou de fora da conta: a disputa da entrada (que já estava) e
        # agora também curar, buffar, invocar e alimentar o pet. O tempo medido
        # passa a ser o da RUN, não o do preparo.

        # BARRA DE ATALHOS NA PÁGINA 1, agora que estamos dentro.
        #
        # A entrada é a fronteira certa: tudo o que vem daqui em diante --
        # montar, andar, descer para lutar, curar -- depende das teclas
        # apontarem para os slots da página 1, e a disputa da entrada pode ter
        # levado minutos com o usuário mexendo na janela. `forcar=True` porque
        # a recarga de 10 s não pode engolir justamente esta chamada, que é a
        # que estabelece o estado para a run inteira.
        hotbar.garantir_pagina_1(ctx, "entrada na cave", forcar=True)

        # Nova run: o contexto estruturado ganha um id próprio (correlação) para
        # o JSON de dev agrupar todos os registros desta corrida na cave.
        logmodo.contexto(
            conta=ctx.account_login,
            id_run=uuid.uuid4().hex[:10],
        )
        self._retomar_altar_em = 0
        # Instância nova, sequência nova: o boss desta instância ainda está vivo.
        self._boss_derrotado = False
        self._tentativas_no_altar = 0
        # Zoom do minimapa no PADRÃO. A navegação converte coordenada em pixel
        # por uma escala medida NAQUELE zoom; se o usuário mexeu, todo clique de
        # movimento passa do alvo sem dar erro nenhum. Custa 7 cliques por run.
        self.ui.padronizar_zoom_do_minimapa()
        # A memória do retrocesso é POR RUN, e este é o único lugar que a zera.
        # Zerá-la a cada `follow_path` (como era) anulava a trava: a própria
        # manobra chama `follow_path` por candidato, e cada volta SITUAR ->
        # ATE_O_ALTAR abria outro -- foram seis num minuto no log, e o
        # personagem andou cinco, seis waypoints de ré.
        self.nav.esquecer_retrocessos()
        self._succeed(State.CURAR)

    # ==================================================================
    # CURAR (já dentro da cave)
    # ==================================================================

    def _do_curar(self) -> None:
        """O PREPARO DE ENTRADA: tudo que exige estar a pé, num lugar só.

        =================================================================
        POR QUE TUDO AQUI, E NÃO ESPALHADO PELO CAMINHO
        =================================================================

        Regra do usuário, 25/08/2026: fora da cave o bot só desmonta se o pet
        estiver inativo; *"de resto, alimentar o PET, usar qualquer coisa que
        dependa tirar a montaria vai ser feito naquele momento que entra na
        cave, que começa se curando e vai fazendo o resto das coisas"*.

        O sintoma que isso corrige: em Stone City, indo ao vendedor e à Fay, o
        bot descia da montaria no meio do trajeto -- cada desmonte custa a
        descida, a ação e a remontagem, com o intervalo da tecla no meio.

        A ORDEM importa e é esta:

            1. CURAR    -- primeiro, porque buff em personagem que vai morrer é
                           buff desperdiçado
            2. BUFFS    -- com a vida já cheia
            3. PET      -- invocar não depende dos outros dois
            4. COMIDA   -- por último, porque o cronômetro dela começa a valer
                           daqui (ver `PetFeeder`)
            5. MONTAR   -- e é AQUI que os cronômetros da run começam

        A BARRA DE ATALHOS já foi garantida na página 1 logo depois da entrada
        (`hotbar.garantir_pagina_1(..., forcar=True)`), que é o passo
        imediatamente anterior a este estado -- não é repetida aqui para não
        pagar dois cliques por run pela mesma garantia.

        POR QUE CURAR AQUI E NÃO ANTES DE ENTRAR: entrar é disputado e pode levar
        muito tempo de tentativa. Nesse intervalo o personagem regenera de graça.
        Curar antes gastaria poção que a espera ia devolver.
        """
        ctx = self.ctx
        self._situacao("preparo de entrada (a pé)")

        # 1 e 2. VIDA E BUFFS.
        self.combat.curar_ao_entrar()
        self.combat.apply_buffs()

        # 3. PET, se a conta pedir e ele não estiver ativo. `ensure_pet` já
        #    confere antes de invocar.
        if ctx.settings.pet.summon_on_login:
            self.combat.ensure_pet()

        # 4. COMIDA DO PET. Aqui, e não antes de entrar: alimentar exige estar a
        #    pé, e a pé fora da cave é exatamente o que a regra nova proíbe. Se a
        #    hora da comida passou lá fora, ela é dada agora -- e a cadência não
        #    escorrega, porque o `PetFeeder` ancora no vencimento e não no
        #    instante em que conseguiu alimentar.
        self.combat.feed_pet()

        # 5. MONTARIA, e o começo da contagem. O portão INSISTE até confirmar
        #    (ver `Navigator.garantir_montaria_para_andar`): dentro da cave não
        #    se anda a pé, porque a pé não se chega no boss.
        self.nav.garantir_montaria_para_andar("atravessar a cave")

        # ================================================================
        # É AQUI QUE A RUN PASSA A CONTAR
        # ================================================================
        #
        # `begin_run` marca `run_started_at` e zera o cronômetro do boss -- os
        # dois tempos de "estatísticas BC". Ficam de fora: a disputa da entrada
        # e todo o preparo acima.
        #
        # COMEÇA MESMO QUE ALGO ACIMA TENHA FALHADO. Amarrar a contagem ao
        # sucesso do preparo faria a run com problema sumir das estatísticas --
        # e é justamente ela que interessa olhar. O que falhou vira linha de log.
        ctx.stats.begin_run()
        ctx.log.info("Preparo de entrada concluído — a contagem da run começa "
                     "agora | montado=%s | pet=%s",
                     ctx.memory.is_mounted(), ctx.memory.pet_active())

        ctx.apply_camera()
        self._succeed(State.ATE_O_ALTAR)

    # ==================================================================
    # ATE_O_ALTAR
    # ==================================================================

    def _do_ate_o_altar(self) -> None:
        """Atravessa a cave até o patamar do Altar Stone, o mais rápido possível.

        Aqui a velocidade é sobrevivência, não conforto: os mobs da cave vão atrás
        e formam um trem que mata o personagem se ele fica parando. Por isso o
        trajeto é um laço contínuo (ver `Navigator.follow_path`), a montaria é
        conferida antes, e a skill de velocidade entra assim que o personagem
        começa a andar.
        """
        ctx = self.ctx
        # A ROTA VAI INTEIRA, e a retomada é um ÍNDICE. Antes era uma fatia
        # (`CAMINHO_ATE_O_ALTAR[retomar:]`), e a fatia levava embora tudo o que
        # estava atrás do ponto de retomada -- inclusive o waypoint ANTERIOR,
        # que é candidato do destravamento. No log de (205,31) o anterior estava
        # a 10 unidades e não existia na lista que a manobra recebeu.
        rota = mapa_bc.CAMINHO_ATE_O_ALTAR
        s = self._situacao("travessia da cave")

        ctx.log.info(
            "Caminho até o altar: %s waypoints%s | %s",
            len(rota),
            f" (retomando do {self._retomar_altar_em + 1})"
            if self._retomar_altar_em else "",
            s.resumo(),
        )

        # Montaria primeiro: a pé o trajeto dobra de duração e o trem de mobs
        # alcança. É a única espera que vale a pena pagar antes de sair.
        self.nav.garantir_montaria_para_andar("a travessia até o altar")
        ctx.apply_camera()

        if self.nav.seguir_rota(rota, comecar_em=self._retomar_altar_em):
            self._retomar_altar_em = 0
            self._succeed(State.ENTRAR_NO_COVIL)
        else:
            # Não desiste da run: reavalia onde está e tenta retomar. Sair da
            # instância aqui jogaria fora a travessia já feita e o reset do boss.
            self._fail("Falhei na travessia até o altar", next_state=State.SITUAR)

    # ==================================================================
    # ENTRAR_NO_COVIL
    # ==================================================================

    def _desencalhar_no_altar(self) -> bool:
        """Vai-e-volta que destrava o clique no Altar Stone.

        Acontece de o personagem estar exatamente em (218,45) e o Altar Stone
        simplesmente não responder. Sair para (231,45), esperar, e voltar resolve.

        É o mesmo tipo de problema do waypoint 43 da travessia: o que trava não é a
        distância nem a coordenada, é o estado em que o cliente e o servidor
        deixaram o personagem naquele ponto. Mudar de lugar e voltar refaz esse
        estado -- e sair e voltar é mais rápido que refazer a pirâmide inteira, que
        é o que o `_fail` para SITUAR acabaria fazendo.
        """
        ctx = self.ctx
        ctx.log.info(
            "O Altar Stone não respondeu. Saindo para %s, esperando %.0fs e "
            "voltando para %s antes de tentar de novo.",
            mapa_bc.PONTO_PARA_DESENCALHAR_O_ALTAR,
            mapa_bc.SEGUNDOS_DESENCALHANDO_O_ALTAR,
            mapa_bc.ULTIMO_ANTES_DO_ALTAR,
        )

        if not self.nav.goto(mapa_bc.PONTO_PARA_DESENCALHAR_O_ALTAR,
                             tolerance=mapa_bc.tolerancia_do_altar(),
                             max_seconds=30.0, usar_mapa=False):
            ctx.log.warning("Não cheguei em %s para desencalhar",
                            mapa_bc.PONTO_PARA_DESENCALHAR_O_ALTAR)

        ctx.tick(mapa_bc.SEGUNDOS_DESENCALHANDO_O_ALTAR)

        # VOLTA PELA RETA, e não pela rota. O ponto de vai-e-volta fica a 13
        # unidades do patamar -- acima do `NA_ROTA` --, então deixar
        # `_chegar_no_patamar_do_altar` decidir mandaria refazer a pirâmide inteira
        # a cada vai-e-volta. Mas este trecho é conhecido: o personagem acabou de
        # percorrê-lo na ida, agora mesmo, e sem obstáculo.
        if self.nav.goto(mapa_bc.ULTIMO_ANTES_DO_ALTAR,
                         tolerance=mapa_bc.tolerancia_do_altar(),
                         max_seconds=30.0, usar_mapa=False):
            return True

        # A volta pela reta falhou: aí sim vale o caminho longo.
        return self._chegar_no_patamar_do_altar()

    def _chegar_no_patamar_do_altar(self) -> bool:
        """Leva o personagem a (218,45), pela LINHA RETA ou pela ROTA.

        A tolerância é a mesma que a navegação usa para chegar naquele waypoint --
        `mapa_bc.tolerancia_do_altar()`. Ela não é escolhida aqui de propósito: um
        número próprio, mais apertado que o da chegada, produz o laço em que um lado
        diz "cheguei" e o outro diz "não cheguei" sobre a mesma posição. Foi o que
        aconteceu, e está documentado na função que devolve o valor.

        DUAS FORMAS DE CHEGAR, e a segunda existe porque a primeira é cega:

          RETA -- `goto` direto. Serve quando o personagem está a poucas unidades,
                  que é o caso normal ao fim da travessia.
          ROTA -- refazer os waypoints do Secret Altar. É o que resolve o caso do
                  log: o personagem voltou para (193,43) por lag, ficou a 20
                  unidades, e a reta dali atravessa a pirâmide. `goto` não sabe
                  disso -- ele clica no minimapa e o personagem bate na parede,
                  para sempre ("destravando 1" quarenta segundos seguidos).

        A pirâmide NÃO TEM ATALHO: os waypoints dela foram medidos passo a passo por
        isso. Então longe do patamar a resposta não é insistir na reta, é voltar para
        a rota e subir de novo -- que é exatamente o que `onde_retomar` faz na área
        apertada.
        """
        ctx = self.ctx
        atual = ctx.memory.position()
        alvo = mapa_bc.ULTIMO_ANTES_DO_ALTAR
        tolerancia = mapa_bc.tolerancia_do_altar()

        if atual is None:
            return self.nav.goto(alvo, tolerance=tolerancia,
                                 max_seconds=60.0, usar_mapa=False)

        distancia = mapa_bc.distancia(atual, alvo)
        if distancia <= tolerancia:
            return True

        # LONGE demais para a reta: volta pela rota. O limite é o mesmo que separa
        # "estou na rota" de "saí dela" (`mapa_bc.NA_ROTA`), porque é essa a
        # pergunta -- dentro dele a reta é um ajuste de um passo; fora dele o
        # personagem saiu do caminho e precisa reentrar por um waypoint.
        if distancia > mapa_bc.NA_ROTA:
            ctx.log.warning(
                "Estou a %.0f unidades de %s, fora da rota (limite %s). A reta "
                "daqui atravessa a pirâmide, que não tem atalho. Voltando pelos "
                "waypoints do Secret Altar.",
                distancia, alvo, mapa_bc.NA_ROTA,
            )
            return self._voltar_ao_altar_pela_rota(atual)

        ctx.log.info(
            "Estou a %.0f unidades de %s (tolerância %s). Ajustando antes de "
            "clicar.", distancia, alvo, tolerancia,
        )
        if self.nav.goto(alvo, tolerance=tolerancia, max_seconds=30.0,
                         usar_mapa=False):
            return True

        # A reta falhou mesmo de perto: a geometria está no caminho. Mesma resposta.
        ctx.log.warning("A reta até %s não funcionou; voltando pela rota", alvo)
        return self._voltar_ao_altar_pela_rota(ctx.memory.position() or atual)

    def _voltar_ao_altar_pela_rota(self, atual: tuple[int, int]) -> bool:
        """Reentra na rota do altar e percorre o que falta até (218,45).

        É AQUI QUE O LAG E O ROLLBACK SÃO TRATADOS. `onde_retomar` responde por qual
        waypoint reentrar, e na área apertada ela RECUA até o começo da área em vez
        de tentar entrar pelo meio -- porque entrar pelo meio da pirâmide é bater na
        parede. Recuar alguns waypoints para depois subir inteiro é mais rápido que
        insistir num trecho impossível, e é o que faltava no log: o bot voltou para
        (193,43) e continuou mirando (218,45) em linha reta.

        E `seguir_rota` traz o resto de graça: detector de rollback, detector de
        personagem parado (com a manobra dos dois waypoints mais próximos) e a
        tolerância certa de cada área.
        """
        ctx = self.ctx
        onde = mapa_bc.onde_retomar(atual, mapa_bc.CAMINHO_ATE_O_ALTAR)
        ctx.log.info(
            "Reentrando na rota do altar pelo waypoint %s/%s — %s",
            onde.indice + 1, len(mapa_bc.CAMINHO_ATE_O_ALTAR), onde.motivo,
        )
        diario.registrar_evento(
            ctx.account_login, "volta-ao-altar-pela-rota",
            f"de {atual} pelo waypoint {onde.indice + 1}: {onde.motivo}",
            atual, ctx.memory.location(),
        )
        # FATIA a rota, como o `_do_ate_o_altar` faz: `seguir_rota` percorre o que
        # recebe do começo ao fim, e a fatia preserva os `Waypoint` -- ou seja, as
        # áreas e as tolerâncias de cada ponto continuam valendo.
        return self.nav.seguir_rota(
            mapa_bc.CAMINHO_ATE_O_ALTAR[onde.indice:])

    def _encostar_exato_no_patamar(self) -> bool:
        """Último passo até (218,45): encostar de VERDADE, não só a 8 unidades.

        A navegação termina a rota do altar aceitando `TRICKY_TOLERANCE` (8u) --
        o Secret Altar é apertado e exigir folga por waypoint travaria o trajeto.
        Mas o clique no Altar Stone foi medido COM o personagem exatamente em
        (218,45): chegar a 1 unidade de lado (217,45) já cai fora das coordenadas
        do `altar_npc`. Este ajuste fino dá o último passo com tolerância apertada
        (`mapa_bc.PRECISAO_NO_PATAMAR_DO_ALTAR` < 1, que no espaço de coordenadas
        inteiras só aceita a posição exata).

        Devolve True SOMENTE se a leitura final for a posição exata. Quem chama
        não clica sem isso.
        """
        ctx = self.ctx
        alvo = mapa_bc.ULTIMO_ANTES_DO_ALTAR
        precisao = mapa_bc.PRECISAO_NO_PATAMAR_DO_ALTAR

        def encostado() -> bool:
            """Está no ponto AGORA? Sempre por leitura nova, nunca por dedução."""
            p = ctx.memory.position()
            return (p is not None
                    and mapa_bc.distancia(p, alvo) <= precisao)

        atual = ctx.memory.position()
        if atual is None:
            return False
        if mapa_bc.distancia(atual, alvo) <= precisao:
            return True

        ctx.log.info(
            "Ajuste fino do patamar: a %s unidades de %s. Encostando de vez.",
            f"{mapa_bc.distancia(atual, alvo):.0f}", alvo,
        )
        for _ in range(TENTATIVAS_DE_ENCOSTAR_NO_ALTAR):
            ctx.raise_if_stopped()
            if self.nav.goto(alvo, tolerance=precisao,
                             max_seconds=SEGUNDOS_POR_TENTATIVA_NO_ALTAR,
                             usar_mapa=False):
                if encostado():
                    return True

            # O personagem pode estar ainda desacelerando -- e ele PASSA DO
            # PONTO: medido no log, o ajuste terminava em (217,45) e (216,45),
            # do outro lado do alvo, "dentro" do Altar Stone.
            #
            # `wait_until_still` NÃO decide isso. Ela devolve True em duas
            # condições, e uma delas é só "a posição parou de mudar" -- parar em
            # qualquer lugar contava como ter chegado. Era assim que o ajuste
            # dava por encostado a 1 e 2 unidades do alvo, sem avisar: nos três
            # casos do log em que o clique saiu de fora do ponto, o aviso de
            # falha não apareceu. Aqui ela serve só para ESPERAR; quem responde
            # "chegou" é a leitura de posição.
            self.nav.wait_until_still(max_seconds=1.5)
            if encostado():
                return True

        ctx.log.warning(
            "Não consegui encostar exatamente em %s (posição %s). NÃO vou "
            "clicar no Altar Stone de fora do ponto: toda entrada que abriu o "
            "diálogo aconteceu com o personagem exatamente ali.",
            alvo, ctx.memory.position(),
        )
        return False

    def _encostar_exato_na_saida(self) -> bool:
        """Último passo até (81,-398): encostar de VERDADE no ponto do Skull
        Herald da saída.

        Mesmo desenho — e mesmo motivo — de `_encostar_exato_no_patamar`: as
        coordenadas de tela do `cave_exit_npc` foram medidas COM o personagem
        exatamente ali, e o clique é na cena 3D, então a posição faz parte da
        coordenada.

        O QUE ISTO SUBSTITUI, e por que era intermitente: o portão de antes
        andava só quando `distancia > 8`, enquanto quem confere antes de clicar
        aceitava 12. O waypoint do boss fica a **8,06 unidades** daqui — os 8
        passavam 0,06 abaixo dessa distância. Parado exatamente no waypoint do
        boss o bot andava e saía; tendo derivado 1-2 unidades na luta ele não
        andava, clicava de fora, e o diálogo nunca abria. Cara ou coroa decidido
        por onde a luta terminasse. Ver `mapa_bc.PRECISAO_NO_PONTO_DA_SAIDA`.

        Devolve True SOMENTE se a leitura final for a posição exata. Quem chama
        não clica sem isso: aqui o clique perdido não custa só a tentativa —
        cai no chão e o personagem sai andando pelo covil do boss, o que piora
        a tentativa seguinte.
        """
        ctx = self.ctx
        alvo = mapa_bc.POSICAO_DA_SAIDA
        precisao = mapa_bc.PRECISAO_NO_PONTO_DA_SAIDA

        def encostado() -> bool:
            p = ctx.memory.position()
            return p is not None and mapa_bc.distancia(p, alvo) <= precisao

        atual = ctx.memory.position()
        if atual is None:
            # Sem leitura não há o que conferir, e recusar aqui travaria a saída
            # num laço sem saída. Segue e deixa o clique decidir — é o mesmo
            # tratamento que `na_posicao_de_clicar` dá.
            return True
        if encostado():
            return True

        ctx.log.info(
            "Ajuste fino da saída: a %.0f unidades de %s. Encostando de vez.",
            mapa_bc.distancia(atual, alvo), alvo,
        )
        for _ in range(mapa_bc.TENTATIVAS_DE_ENCOSTAR_NA_SAIDA):
            ctx.raise_if_stopped()
            if self.nav.goto(alvo, tolerance=precisao,
                             max_seconds=mapa_bc.SEGUNDOS_POR_TENTATIVA_NA_SAIDA,
                             usar_mapa=False) and encostado():
                return True
            # `wait_until_still` só ESPERA. Quem responde "chegou" é a leitura de
            # posição — ela devolve True também para "a posição parou de mudar",
            # e parar em qualquer lugar não é ter chegado.
            self.nav.wait_until_still(max_seconds=1.5)
            if encostado():
                return True

        ctx.log.warning(
            "Não consegui encostar exatamente em %s (posição %s). NÃO vou "
            "clicar no Skull Herald de fora do ponto: o clique cairia no chão e "
            "o personagem sairia andando pelo covil do boss.",
            alvo, ctx.memory.position(),
        )
        return False

    def _do_entrar_no_covil(self) -> None:
        """Altar Stone -> Secret Cemetery.

        PRÉ-REQUISITO conferido aqui: estar em (218,45), com a precisão de
        `mapa_bc.tolerancia_do_altar()`. As coordenadas do clique no Altar Stone
        foram medidas COM O PERSONAGEM ALI -- são cliques na cena 3D, então a
        posição faz parte da coordenada. De outro ponto da pirâmide o clique cai na
        parede, ou pior, no chão (e o personagem anda).

        O RITMO É POR CICLOS de `TENTATIVAS_ANTES_DE_DESENCALHAR`:

            6 tentativas de clique -> vai-e-volta -> 6 tentativas -> vai-e-volta ...

        O vai-e-volta é o descanso entre os ciclos, não uma alternativa a tentar.
        """
        ctx = self.ctx
        self._situacao("antes do Altar Stone")

        self._tentativas_no_altar += 1
        desencalhar = self._tentativas_no_altar > TENTATIVAS_ANTES_DE_DESENCALHAR

        if desencalhar:
            # O VAI-E-VOLTA VEM ANTES DA TENTATIVA, não em lugar dela: depois de
            # voltar, esta mesma volta ainda clica no Altar Stone.
            chegou = self._desencalhar_no_altar()

            # E A CONTAGEM REINICIA AQUI. Sem esta linha o contador ficava acima do
            # limite para sempre, e daí TODA volta seguinte virava vai-e-volta: o
            # personagem ficava indo e voltando entre (218,45) e (231,45) fazendo
            # UMA tentativa entre cada par de caminhadas, em vez das seis.
            #
            # Começa em 1, e não em 0, porque o clique desta volta já é a primeira
            # tentativa do ciclo novo -- assim cada ciclo tem exatamente
            # `TENTATIVAS_ANTES_DE_DESENCALHAR` tentativas, e não uma a mais.
            self._tentativas_no_altar = 1
        else:
            chegou = self._chegar_no_patamar_do_altar()

        ctx.log.info(
            "Altar Stone: tentativa %s de %s deste ciclo%s",
            self._tentativas_no_altar, TENTATIVAS_ANTES_DE_DESENCALHAR,
            " (ciclo novo, depois do vai-e-volta)" if desencalhar else "",
        )

        if not chegou:
            self._fail("Não alcancei o patamar do Altar Stone",
                       next_state=State.SITUAR)
            return

        # A chegada da rota vale com 8 unidades de folga, mas o clique no Altar
        # Stone só acerta de (218,45) EXATO. Garante o último passo antes de
        # clicar -- e se não conseguir, NÃO CLICA.
        #
        # Antes ele clicava assim mesmo. O log de dev mostrou por que isso não
        # se paga: das tentativas fora do ponto, ZERO abriram o diálogo; das que
        # abriram, todas tinham o personagem exatamente ali. Clicar de fora só
        # gasta a tentativa do ciclo -- e é a tentativa que faltou para o ciclo
        # acertar quando o mob saísse da frente.
        if not self._encostar_exato_no_patamar():
            self._fail("Não encostei em (218,45) para clicar no Altar Stone",
                       next_state=State.ENTRAR_NO_COVIL)
            return

        antes = ctx.memory.position()
        # View Reset forçado só quando o personagem ANDOU desde a tentativa
        # anterior. Parado, a câmera não se mexe, e o reset custa um clique mais
        # a espera dele em cada volta do ciclo -- tempo em que o mob que engoliu
        # o clique continua na frente da pedra. Quando ele andou, forçar é
        # obrigatório: a coordenada do altar_npc só vale com a câmera no padrão.
        andou = antes != self._posicao_do_ultimo_clique_no_altar
        self._posicao_do_ultimo_clique_no_altar = antes
        self.ui.entrar_no_covil_do_boss(forcar_visao=andou)

        depois = self._situacao("depois do Altar Stone")
        # O portal é um teleporte: a confirmação é o SALTO de posição para perto
        # da coordenada de chegada do covil, não a simples mudança de posição --
        # andar um passo também muda a posição.
        chegou = (
            depois.posicao is not None
            and mapa_bc.distancia(depois.posicao, mapa_bc.CHEGADA_NO_COVIL) <= 40
        )
        if chegou or (depois.area == "Secret Cemetery"):
            ctx.log.info("No covil do boss: %s (tentativa %s)",
                         depois.resumo(), self._tentativas_no_altar)
            self._tentativas_no_altar = 0
            self._succeed(State.ATE_OS_GUARDAS)
        else:
            ctx.log.warning("O portal do altar não confirmou (%s -> %s)",
                            antes, depois.posicao)
            self._fail("Não entrei no covil pelo Altar Stone",
                       next_state=State.ENTRAR_NO_COVIL)

    # ==================================================================
    # ATE_OS_GUARDAS / GUARDAS / ATE_O_BOSS
    # ==================================================================

    def _do_ate_os_guardas(self) -> None:
        self._situacao("indo até os guardas")
        self.nav.garantir_montaria_para_andar("ir até os guardas")
        if self.nav.seguir_rota(mapa_bc.CAMINHO_ATE_O_BOSS):
            self._succeed(State.GUARDAS)
        else:
            self._fail("Não cheguei na posição dos guardas",
                       next_state=State.SITUAR)

    def _do_guardas(self) -> None:
        """FASE 1 -- os quatro mobs que atacam na chegada, pela flag de combate.

        Chega no ponto, NÃO aperta TAB, espera a flag de combate ligar, gira a
        rotação configurada e para quando a flag desligar de forma confirmada. O
        descanso de exatos 4 segundos acontece dentro da fase, logo após a saída de
        combate -- é a última oportunidade da run de recuperar mana de graça,
        porque na frente do boss não dá.

        A CONTAGEM DE MORTES SAIU. Antes este estado insistia em rodadas até os
        quatro guardas estarem com HP zero, lendo o endereço e o HP de cada um. A
        run passou a não depender de ponteiro de alvo: quem responde "acabou" é a
        flag. O efeito colateral é que não existe mais o aviso "só 2 de 4" -- o que
        o log diz agora é quanto tempo a fase levou e quantos golpes saíram.
        """
        ctx = self.ctx
        self._situacao("guardas do covil")
        if not ctx.settings.bc.matar_guardas:
            ctx.log.info("Matar guardas está desligado; seguindo para o boss")
            self._succeed(State.ATE_O_BOSS)
            return

        fim = self.combat.fase_dos_guardas_por_combate()

        if not fim.saiu_de_combate:
            # NÃO trava a run. Ficar preso no covil até o tempo da instância
            # acabar é pior do que encostar no boss com guarda vivo, e o boss
            # ainda pode cair. O que não pode é isso passar despercebido.
            ctx.log.warning(
                "A fase dos guardas não fechou pela flag de combate (%s). "
                "Seguindo para o boss assim mesmo, e registrando.", fim.resumo(),
            )
            diario.registrar_evento(
                ctx.account_login, "guardas-incompletos",
                f"fase por flag de combate terminou por {fim.motivo} "
                f"({fim.segundos:.0f}s, {fim.golpes} golpes)",
                ctx.memory.position(), ctx.memory.location(),
            )
        else:
            # SAIU de batalha nos 4 mobs: é AQUI, e não na frente do boss, que o
            # top-up de HP acontece. No waypoint do boss não se bebe poção -- o
            # boss encosta e o efeito para na hora --, então a vida que faltar
            # precisa ser recuperada agora, parado, fora de combate. Só age se a
            # vida estiver abaixo de `LIMINAR_TOPUP_ANTES_DO_BOSS`; acima disso
            # não gasta nada. (Se a fase não fechou limpa, segue sem top-up: pode
            # ainda estar em combate, e 15 s parado aí é perigo.)
            self.combat.curar_antes_do_boss()

        # LARGAR A MIRA ANTES DE ANDAR -- os dois desfechos passam por aqui.
        #
        # DEPOIS do top-up e nao antes: `curar_antes_do_boss` pode SENTAR, e o
        # ESC no meio disso cancelaria o descanso que acabou de comecar.
        #
        # O cadaver do ultimo Gun Witch fica selecionavel por 7 a 13 s (medido),
        # entao chegar no waypoint do boss com `target_id != 0` e o caso NORMAL,
        # nao a excecao. Quem decide se o ESC sai e a MEMORIA, dentro de
        # `largar_a_mira`: sem alvo confirmado nada e apertado, porque ESC sem
        # mira abre o menu do jogo -- e menu aberto na frente do boss engole o
        # clique na cena 3D.
        self.combat.largar_a_mira("seguir para o waypoint do boss")

        self._succeed(State.ATE_O_BOSS)

    def _do_ate_o_boss(self) -> None:
        ctx = self.ctx
        self._situacao("indo até o boss")

        # TEMPO DE NAVEGAÇÃO: o trajeto terminou (entrada, altar, guardas) e o
        # passo final sobre a coordenada do boss ainda não aconteceu. É aqui que
        # se anota quanto a run levou para chegar -- o combate começa depois.
        ctx.stats.marcar_chegada_ao_boss()

        # A LIMPEZA DA "ROTA SEGURA" ESTÁ EM STANDBY.
        #
        # Ela mirava por nome (`acquire_target(NOME_DOS_GUARDAS)`) e chamava o
        # `fight_boss` antigo -- os dois caminhos por ponteiro de alvo que saíram do
        # fluxo. Manter isto ligado faria exatamente o que a especificação pede para
        # evitar: apertar TAB e decidir por HP de alvo no meio da run.
        #
        # Não vira perda prática: os mobs do caminho já engajam sozinhos, e o
        # combate por flag na fase 1 os inclui. Para voltar, é reativar aqui junto
        # com as funções da seção "EM STANDBY" do `combat.py`.
        #
        # if ctx.settings.route.mode == "safe":
        #     self.combat.acquire_target(NOME_DOS_GUARDAS, attempts=6)
        #     if self.combat._target_selected():
        #         self.combat.fight_boss(watchdog=self.watchdog)

        # `usar_mapa=False`: estamos dentro da instância, e o mapa-múndi não tem
        # a cave. Tentar só abriria e fecharia a tela do mapa.
        if self.nav.goto(mapa_bc.POSICAO_DO_BOSS, tolerance=6, usar_mapa=False,
                         max_seconds=60.0):
            ctx.log.info("Na posição do boss: %s", ctx.memory.position())
            self._succeed(State.BOSS)
        else:
            self._fail("Não alcancei a posição do boss", next_state=State.SITUAR)

    # ==================================================================
    # BOSS
    # ==================================================================

    def _chat_aberto(self) -> bool | None:
        """O chat de digitação está aberto? `None` quando não dá para saber.

        `None` NÃO é "fechado". Quem chama usa isso para decidir não apertar
        Enter no escuro -- Enter ALTERNA o chat, então um aperto por garantia
        tem metade de chance de ABRIR o que se queria fechar.
        """
        ctx = self.ctx
        template = ctx.templates.load(TEMPLATE_CHAT_ABERTO)
        if template is None:
            ctx.log.warning("Template %s não encontrado", TEMPLATE_CHAT_ABERTO)
            return None
        quadro = capture_window(ctx.hwnd)
        if quadro is None or frame_is_blank(quadro):
            return None
        return find_template(quadro, template,
                             threshold=LIMIAR_DO_CHAT_ABERTO) is not None

    def _esconder_jogadores(self) -> bool:
        """Faz o truque do F12 antes de entrar na cave. True = seguro seguir.

        Roda a CADA entrada, não uma vez no login: o grude vale para a sessão e
        apertar a tecla de novo o desfaz -- inclusive sem querer, com a pessoa
        usando a mesma máquina.
        """
        ctx = self.ctx
        resultado = esconder_jogadores.esconder_jogadores(
            tecla=ctx.settings.keys.hide_players,
            segurar=ctx.key_down,
            soltar=ctx.key_up,
            apertar=lambda tecla: ctx.press(tecla),
            chat_aberto=self._chat_aberto,
            esperar=ctx.tick,
            log=ctx.log,
        )
        if resultado.seguro_para_seguir:
            # Só anuncia o que ACONTECEU. Com o interruptor desligado ou sem
            # tecla configurada, uma linha por entrada seria ruído a cada run.
            if resultado.escondeu:
                ctx.log.info("Esconder jogadores: %s", resultado)
            else:
                ctx.log.debug("Esconder jogadores: %s", resultado)
            return True
        ctx.log.error(
            "NÃO vou entrar na cave: %s. Entrar com o chat aberto desvia TODA "
            "tecla do bot para o campo de texto -- a run morreria em silêncio, "
            "e um Enter depois publicaria aquilo no chat do jogo.", resultado,
        )
        return False

    def _onde_esta_o_pick_up_all(self) -> tuple[int, int] | None:
        """Onde está o botão "Pick up all", ou `None` se ele não está na tela.

        É a única coisa que autoriza um clique ESQUERDO do catador -- o único
        clique que move o personagem neste jogo. Sem botão visto, sem clique.
        """
        ctx = self.ctx
        template = ctx.templates.load(TEMPLATE_PICK_UP_ALL)
        if template is None:
            ctx.log.warning("Template %s não encontrado", TEMPLATE_PICK_UP_ALL)
            return None
        quadro = capture_window(ctx.hwnd)
        if quadro is None or frame_is_blank(quadro):
            return None
        ponto = find_template(quadro, template,
                              threshold=LIMIAR_DO_PICK_UP_ALL)

        # ==============================================================
        # A PROVA DO `ADDR_LOOT_WINDOW` PEGA CARONA AQUI
        # ==============================================================
        #
        # Este é o único lugar do bot onde existe GABARITO DE TELA para "a janela
        # de loot está aberta": o botão "Pick up all" na tela **é** a janela
        # aberta. E `ADDR_LOOT_WINDOW` é um endereço herdado do GhostBot na versão
        # 6139 que nunca foi confirmado nesta -- `loot_window_open()` vai só no
        # log justamente porque ninguém sabe se ele responde.
        #
        # A carona é de graça: a captura e o casamento já aconteceram acima, e a
        # leitura do endereço custa microssegundos. Ver `core/calibracao.py`.
        self._provar_a_janela_de_loot(ponto is not None)
        return ponto

    def _provar_a_janela_de_loot(self, botao_na_tela: bool) -> None:
        """Pontua os candidatos de `ADDR_LOOT_WINDOW` contra o botão na tela.

        COMPLEMENTO: engole tudo. Instrumentação não derruba run.
        """
        if not calibracao.ATIVADA:
            return
        try:
            ctx = self.ctx
            # Ver `calibracao.quem_esta_medindo`: o `BotContext` não tem
            # `id_run`, e pedir com default zerava a contagem de runs.
            conta, id_run = calibracao.quem_esta_medindo()
            for endereco in CANDIDATOS_DA_JANELA_DE_LOOT:
                rotulo = f"{endereco:#010x}"
                if not calibracao.deve_amostrar("janela_de_loot", rotulo):
                    continue
                calibracao.registrar(calibracao.julgar_booleano(
                    prova="janela_de_loot", candidato=rotulo,
                    lido=ctx.memory.candidato_de_endereco_booleano(endereco),
                    na_tela=botao_na_tela, conta=conta, id_run=id_run))
        except Exception as exc:
            try:
                ctx.log.debug("Prova da janela de loot falhou: %s", exc)
            except Exception:
                pass

    def _catar_o_loot(self) -> None:
        """Recolhe o loot do chão, para a conta cujo pet não tem auto pick.

        COMPLEMENTO: nunca derruba a run. Falhar em catar custa itens; levantar
        aqui custaria a run inteira, com o boss já morto e a instância gasta.

        Roda ANTES do `package_courage` porque o `package_courage` abre o
        inventário, e o que está no chão precisa entrar na bolsa antes disso.
        """
        ctx = self.ctx
        if not ctx.settings.usar_catador:
            return
        try:
            resultado = catador.catar(
                ponto_do_loot=ctx.coords.loot,
                localizar_botao=self._onde_esta_o_pick_up_all,
                clicar_direito=ctx.right_click,
                clicar_esquerdo=ctx.click,
                esperar=ctx.tick,
                log=ctx.log,
            )
            # O ponteiro NÃO decide nada -- vai junto no log só para descobrir,
            # ao longo das primeiras noites, se `ADDR_LOOT_WINDOW` responde neste
            # cliente. Ele é mais um endereço herdado do GhostBot na versão 6139
            # e nunca confirmado aqui.
            ctx.log.info("Catador: %s (loot_window_open=%s)",
                         resultado, ctx.memory.loot_window_open())
        except StopRequested:
            raise
        except Exception as exc:
            ctx.log.warning("Catador falhou (segue a run): %s", exc)

    def _usar_package_courage(self) -> None:
        """Pós-boss: abre o inventário e usa TODOS os `package_courage`.

        Roda SÓ no ramo de vitória do `_do_boss`, com o personagem ainda no
        waypoint do boss e A PÉ (a montaria ainda não foi ativada). O boss
        sempre dropa este item; o clique com botão DIREITO no centro dele usa o
        item e ele some da bolsa.

        É um COMPLEMENTO do fluxo -- nunca derruba a run.

        =================================================================
        UMA CAPTURA, TODOS OS CLIQUES
        =================================================================

        NO INVENTÁRIO OS SLOTS NÃO SE MEXEM: usar um item não faz os outros
        subirem, então as coordenadas colhidas numa captura continuam válidas
        durante a rajada inteira de cliques. Quem desloca slot é a GRADE DE
        VENDA do NPC, que é outra coisa -- ver o comentário em
        `RODADAS_DE_USO_DO_PACKAGE`.

        Por isso o laço é: captura, clica em todos, reconfere capturando de
        novo. Ainda achou (item empilhado, clique que não pegou), repete; não
        achou, acabou.

        =================================================================
        O CASAMENTO É EM COR, E ISSO É O QUE MAIS IMPORTA AQUI
        =================================================================

        O ícone é pequeno (27x33 px), e a bolsa está cheia de ícones de MESMA
        FORMA em cores diferentes: poções, pergaminhos, livros. Em cinza -- que
        é o padrão da visão deste bot -- eles marcam até 0.99 contra este
        template, ou seja, passam por qualquer limiar que ainda aceite o item
        verdadeiro. Em cor ficam em 0.88 ou menos, e o item real fica em 0.97
        para cima.

        Daí `load_color` + `colorido=True` + `LIMIAR_DO_PACKAGE_EM_COR`, que tem
        os números medidos no comentário.

        =================================================================
        TRÊS TRAVAS, DA MAIS FORTE PARA A MAIS FRACA
        =================================================================

        A busca varre a janela INTEIRA -- não há região restrita, porque a
        janela da bolsa pode ser arrastada para qualquer canto. Então um falso
        positivo é possível fora dela, e fora dela o clique direito cai na cena
        3D, que neste jogo FAZ O PERSONAGEM ANDAR. Aqui isso é caro: ele está no
        waypoint do boss, e sair dali atrapalha a saída da cave.

          1. BOLSA ABERTA, por MEMÓRIA (`bag_open`). É a mais forte porque age
             ANTES do clique: se a tecla de inventário não pegou, a tela é a
             cena 3D e todo match é falso. Não depende de captura de imagem.
             Quando a leitura não responde neste cliente, o passo segue -- mas
             avisando que segue sem confirmação.
          2. POSIÇÃO, entre um clique e o seguinte. Uma leitura de memória custa
             microssegundos, então dá para conferir a CADA clique sem pesar na
             rajada. Mudou de lugar = caiu no chão: para na hora, antes que os
             cliques restantes afastem o personagem mais ainda.
          3. PROGRESSO, por rodada. Se a contagem de matches não cai depois de
             uma rajada, aquela rajada não usou nada. Duas dessas e a função
             desiste, em vez de martelar as mesmas coordenadas até o teto.

        Nenhuma delas depende de saber onde a bolsa está na tela.

        O personagem está a pé neste ponto, então as teclas funcionam -- não
        precisa de `_preparar_para_agir`. Se o usuário não configurou tecla de
        inventário, o passo é pulado.
        """
        ctx = self.ctx
        tecla = ctx.settings.keys.inventory
        if not tecla:
            ctx.log.warning(
                "Sem tecla de inventário configurada; pulando o uso do "
                "package_courage")
            return

        # EM COR. `load` devolveria cinza, e cinza não distingue ícone de item.
        template = ctx.templates.load_color(TEMPLATE_PACKAGE_COURAGE)
        if template is None:
            ctx.log.warning(
                "Template %s não encontrado; pulando o uso do package_courage",
                TEMPLATE_PACKAGE_COURAGE)
            return

        # Verifica se o inventário JÁ está aberto ANTES de apertar a tecla.
        # Se já estiver aberto: não reabre (evita fechar sem querer), mas SEMPRE fecha no fim.
        ja_estava_aberto = ctx.memory.bag_open()
        if ja_estava_aberto:
            ctx.log.info("Inventário já está aberto; usando package_courage sem reabrir")
        else:
            ctx.log.info("Abrindo o inventário para usar o(s) package_courage")
            ctx.press(tecla)

            # -- trava 1: a bolsa abriu mesmo? --------------------------------
            #
            # `bag_open` distingue mal "fechada" de "não consegui ler" (as duas dão
            # False), então a espera é o que separa as duas na prática: se em dois
            # segundos ela nunca disser True, ou a tecla não pegou ou a leitura não
            # vale neste cliente. Nos dois casos o passo segue -- é complemento, não
            # pode derrubar a run --, mas o log diz que segue às cegas, e as travas
            # 2 e 3 continuam valendo.
            #
            # NÃO HÁ MAIS ESPERA FIXA ANTES DESTE LAÇO. Havia um `tick(0.4)` logo
            # depois da tecla, e ele era puro desperdício: este laço já trata o caso
            # de a bolsa ainda não ter aberto, e trata melhor -- ele PERGUNTA, em vez
            # de supor um tempo. Quando a bolsa abre rápido, sai na primeira volta.
            limite = time.time() + SEGUNDOS_ESPERANDO_A_BOLSA
            bolsa_confirmada = False
            while time.time() < limite:
                ctx.raise_if_stopped()
                if ctx.memory.bag_open():
                    bolsa_confirmada = True
                    break
                ctx.tick(PASSO_DA_ESPERA_DA_BOLSA)

            if not bolsa_confirmada:
                ctx.log.warning(
                    "Não consegui confirmar pela memória que a bolsa abriu em "
                    "%.0fs. Sigo, mas sem essa garantia: se a tecla de inventário "
                    "não pegou, o que está na tela é a cena 3D e qualquer match é "
                    "falso.", SEGUNDOS_ESPERANDO_A_BOLSA)

        # Posição de referência da trava 2. `None` desliga a trava em vez de
        # bloquear o passo: sem leitura de memória não dá para conferir, e o
        # item continua valendo a tentativa.
        posicao_inicial = ctx.memory.position()

        cliques = 0
        vistos_antes = None
        capturas_invalidas = 0
        rodadas_sem_progresso = 0
        rodada = 0
        motivo_final = "não achei mais nenhum"

        for rodada in range(1, RODADAS_DE_USO_DO_PACKAGE + 1):
            ctx.raise_if_stopped()
            # Assenta o DESENHO antes de olhar. Na primeira rodada é a janela da
            # bolsa terminando de pintar (a memória já confirmou que ela abriu, e
            # as duas coisas não acontecem no mesmo instante); nas seguintes é o
            # item SUMINDO depois do uso -- capturar cedo demais mostraria o item
            # que já foi usado e custaria uma rodada a mais.
            ctx.tick(ASSENTAMENTO_DA_BOLSA)
            quadro = vision.capture_window(ctx.hwnd)
            if vision.frame_is_blank(quadro):
                # Captura preta/vazia NÃO é "item não está mais lá": é "não
                # consegui ver". Só decreta sumiço com frame válido.
                capturas_invalidas += 1
                if capturas_invalidas >= CAPTURAS_INVALIDAS_PACKAGE:
                    motivo_final = (
                        f"{capturas_invalidas} capturas inválidas seguidas -- "
                        "seguindo SEM confirmar")
                    break
                continue

            capturas_invalidas = 0
            centros = vision.find_all_templates(
                quadro, template,
                threshold=LIMIAR_DO_PACKAGE_EM_COR, colorido=True)
            if not centros:
                # Frame válido e nenhum item: acabaram (ou o boss não dropou).
                break

            # -- trava 3: a rodada anterior teve efeito? -------------------
            if vistos_antes is not None and len(centros) >= vistos_antes:
                rodadas_sem_progresso += 1
                ctx.log.warning(
                    "Cliquei em %s package_courage e ainda vejo %s; rodada sem "
                    "efeito %s de 2", vistos_antes, len(centros),
                    rodadas_sem_progresso)
                if rodadas_sem_progresso >= 2:
                    motivo_final = (
                        "duas rodadas seguidas sem a contagem cair -- provável "
                        "falso positivo do template")
                    break
            else:
                rodadas_sem_progresso = 0
            vistos_antes = len(centros)

            ctx.log.info("Usando %s package_courage (rodada %s/%s)",
                         len(centros), rodada, RODADAS_DE_USO_DO_PACKAGE)

            saiu_do_lugar = False
            for alvo in centros:
                ctx.right_click(alvo)
                cliques += 1
                ctx.tick(ENTRE_CLIQUES_NO_PACKAGE)

                # -- trava 2: o personagem saiu do lugar? -------------------
                #
                # A leitura de posição custa microssegundos, então cabe entre
                # dois cliques sem pesar. Conferir AQUI, e não só no fim da
                # rajada, é o que impede os cliques restantes de empurrarem o
                # personagem mais para longe depois do primeiro erro.
                agora = ctx.memory.position()
                if (posicao_inicial is not None and agora is not None
                        and agora != posicao_inicial):
                    saiu_do_lugar = True
                    motivo_final = (
                        f"o clique em {alvo} moveu o personagem de "
                        f"{posicao_inicial} para {agora} -- caiu no CHÃO, não "
                        "num item")
                    ctx.log.error("PARANDO o uso do package_courage: %s",
                                  motivo_final)
                    diario.registrar_evento(
                        ctx.account_login, "package-clique-no-chao",
                        motivo_final, agora, ctx.memory.location())
                    break

            if saiu_do_lugar:
                break
        else:
            motivo_final = f"teto de {RODADAS_DE_USO_DO_PACKAGE} rodadas"

        ctx.log.info(
            "package_courage: %s clique(s) em %s rodada(s) (%s). Fechando o "
            "inventário.", cliques, rodada, motivo_final)
        ctx.press(tecla)
        ctx.tick(DEPOIS_DE_FECHAR_A_BOLSA)

    def _do_boss(self) -> None:
        """FASE 2 -- o boss, e a saída de combate valendo como vitória.

        Mesma mecânica da fase 1: sem TAB, espera a flag ligar, gira a rotação
        configurada (agora COM AoE), e encerra quando a flag desligar de forma
        confirmada. As duas fases do boss deixam de importar -- a transformação não
        tira o personagem do combate, então ela não precisa mais ser distinguida da
        morte.

        =================================================================
        A SAÍDA DA CAVE É PROIBIDA SEM A SEQUÊNCIA COMPLETA
        =================================================================

        A sequência é: estar no waypoint do boss -> ENTRAR em batalha -> SAIR de
        batalha. Sem os três passos o bot não tenta sair da cave.

        Antes ele saía de qualquer forma, com o raciocínio de que "dentro da
        instância com o boss vivo não há nada a ganhar". O raciocínio está errado
        na ordem dos custos: a instância já foi paga -- time montado, reset
        consumido, travessia inteira feita -- e sair joga tudo isso fora de uma vez.
        Insistir custa tempo; sair custa a run.

        E o motivo mais comum de não fechar deixou de existir: a espera pelo
        engajamento não tem mais prazo, então "o boss estava afastado e demorou"
        não produz falha nenhuma. O que sobra é flag presa, flag ilegível ou morte
        -- e para nenhuma dessas a resposta certa é abandonar a instância.
        """
        ctx = self.ctx
        s = self._situacao("luta contra o boss")

        # PRIMEIRO PASSO DA SEQUÊNCIA: estar no waypoint do boss.
        #
        # Conferido aqui porque este estado se REPETE -- quando a luta não fecha, o
        # bot volta para cá. Sem esta conferência, uma repetição depois de o
        # personagem escorregar ficaria esperando o combate começar no lugar errado,
        # e agora essa espera não tem prazo.
        if (s.posicao is None
                or mapa_bc.distancia(s.posicao, mapa_bc.POSICAO_DO_BOSS)
                > TOLERANCIA_DO_PONTO_DO_BOSS):
            ctx.log.info(
                "Não estou no waypoint do boss (%s, o ponto é %s). Vou até lá "
                "antes de esperar o combate.", s.posicao, mapa_bc.POSICAO_DO_BOSS,
            )
            self._succeed(State.ATE_O_BOSS)
            return

        fim = self.combat.fase_do_boss_por_combate()
        venceu = fim.saiu_de_combate

        if venceu:
            # A SEQUÊNCIA SE COMPLETOU. É esta linha, e só ela, que autoriza a
            # saída da cave -- de qualquer estado, inclusive pelo SITUAR.
            self._boss_derrotado = True
            ctx.stats.end_run(True)
            stats_diarias.registrar_run(
                ctx.account_login, True, ctx.stats.last_run_seconds,
                ctx.stats.boss_time_seconds)
            ctx.stats.gold_now = ctx.memory.gold()
            ctx.runs_completed += 1
            lucro = ctx.stats.profit
            extra = f", lucro acumulado {lucro}" if lucro is not None else ""
            ctx.log.info(
                "Run %s concluída em %.0fs (%s ok / %s falhas)%s",
                ctx.stats.runs, ctx.stats.last_run_seconds,
                ctx.stats.success, ctx.stats.fail, extra,
            )
            # Pós-boss, ainda no waypoint e a pé.
            #
            # A ORDEM IMPORTA: catar vem ANTES do `package_courage`, porque ele
            # abre o inventário -- e o que está no chão precisa entrar na bolsa
            # antes disso. Foi o próprio usuário que apontou a ordem.
            self._catar_o_loot()
            self._usar_package_courage()
            self._succeed(State.SAIR)
            return

        # -- não fechou: NÃO sai da cave ---------------------------------
        ctx.log.warning(
            "A luta do boss não fechou pela flag de combate (%s). NÃO vou sair da "
            "cave: a instância já foi gasta, e sair sem a sequência "
            "waypoint -> entrar em batalha -> sair de batalha desperdiça a run.",
            fim.resumo(),
        )
        diario.registrar_evento(
            ctx.account_login, "boss-nao-fechou", fim.resumo(),
            ctx.memory.position(), ctx.memory.location(),
        )

        if fim.motivo.startswith("morri") or fim.motivo == "personagem morreu":
            # Morto não há o que insistir: reviver vem primeiro, e quem revive
            # recomeça pelo SITUAR.
            ctx.stats.end_run(False)
            stats_diarias.registrar_run(
                ctx.account_login, False, ctx.stats.last_run_seconds,
                ctx.stats.boss_time_seconds)
            self._fail("Morri na luta do boss", next_state=State.RECUPERAR)
            return

        # Flag presa ou ilegível: repete a FASE, no mesmo lugar. A run continua em
        # pé, e é ela que decide o resultado -- contá-la como perdida aqui faria a
        # estatística mentir a cada repetição.
        self._fail("A luta do boss não fechou; repetindo no mesmo ponto",
                   next_state=State.BOSS)

    # ==================================================================
    # SAIR
    # ==================================================================

    def _do_sair(self) -> None:
        """Vai até (81,-398) e sai pelo Skull Herald.

        NÃO cura aqui. A cura acontece depois de entrar de novo: a disputa pela
        entrada leva tempo e regenera vida de graça.
        """
        ctx = self.ctx
        s = self._situacao("saindo da cave")

        # JÁ ESTOU FORA -- pergunta antes de agir.
        #
        # Acontecia assim: a saída pelo NPC funcionava, mas o cliente não
        # reescrevia o nome do lugar. O bot lia 'Secret Cemetery' em (1395,-629),
        # concluía que não havia saído, andava até o NPC de saída (que fica dentro
        # da cave, inalcançável dali) e clicava de novo. Para sempre.
        #
        # A pergunta não custa nada: a posição já foi lida na linha acima. E a
        # coordenada da saída fica a quase mil unidades da entrada em Ghost Din
        # Woods, então não há como confundir os dois lugares.
        if mapa_bc.posicao_esta_fora_da_cave(s.posicao):
            ctx.log.info("Já estou fora da cave: %s", s.resumo())
            self._seguir_depois_de_sair()
            return

        # A TRAVA DA SEQUÊNCIA. Este é o único lugar do bot que sai da cave, então
        # é aqui que a regra tem que valer -- não só em quem chama.
        #
        # A sequência é: estar no waypoint do boss, ENTRAR em batalha e SAIR de
        # batalha. Sem os três, sair desperdiça uma instância já paga: time
        # montado, reset consumido, travessia inteira feita.
        if not self._boss_derrotado:
            ctx.log.warning(
                "Pediram para sair da cave, mas a sequência do boss não se "
                "completou nesta run (waypoint -> entrar em batalha -> sair de "
                "batalha). Voltando para o boss em vez de sair. | %s", s.resumo(),
            )
            self._succeed(State.BOSS)
            return

        # Chega na coordenada do NPC de saída. É clique posicional: de longe ele
        # cai no chão -- e aqui isso é pior que perder a tentativa, porque o
        # personagem sai andando pelo covil do boss.
        #
        # O PORTÃO NÃO É MAIS ESCOLHIDO AQUI. Ele era `distancia > 8`, e quem
        # confere antes de clicar aceitava 12; os dois números escolhidos à parte
        # são o defeito que `mapa_bc.PRECISAO_NO_PONTO_DA_SAIDA` documenta em
        # detalhe -- o waypoint do boss fica a 8,06 unidades daqui, então os 8
        # passavam raspando e a saída virava cara ou coroa. Agora os dois lados
        # leem a MESMA constante por construção.
        if not self._encostar_exato_na_saida():
            self._fail("Não encostei no ponto da saída", next_state=State.SAIR)
            return

        antes = ctx.memory.position()
        self.ui.sair_da_cave()
        depois = self._situacao("depois de sair")

        saiu = not depois.dentro_da_cave
        if not saiu and antes and depois.posicao:
            saiu = mapa_bc.distancia(antes, depois.posicao) > 200
        if not saiu:
            ctx.log.warning("A saída pelo NPC não confirmou; tentando de novo")
            self._fail("Não saí da cave", next_state=State.SAIR)
            return

        ctx.log.info("Fora da cave: %s", depois.resumo())
        self._seguir_depois_de_sair()

    def _seguir_depois_de_sair(self) -> None:
        """Vender (por contagem de runs) ou voltar para a entrada.

        Extraído porque `_do_sair` tem duas formas de terminar fora da cave --
        saindo pelo NPC agora, ou descobrindo que já estava fora -- e as duas
        seguem para o mesmo lugar.

        GATILHO de venda é a contagem de runs desde a última venda
        (`runs_before_selling`). O gatilho antigo lia a quantidade de itens na
        bolsa e mostrou-se impreciso; por isso ele foi desativado
        (`VendorService.precisa_ir_vender`) e a venda virou por contagem.
        """
        ctx = self.ctx
        alvo = max(1, ctx.settings.vendor.runs_before_selling)
        runs = ctx.stats.runs - self._runs_na_ultima_venda
        if runs >= alvo:
            ctx.log.info(
                "Hora de vender: %s run(s) desde a última venda (meta %s). "
                "Indo para a cidade.", runs, alvo,
            )
            self._succeed(State.MANUTENCAO)
        else:
            self._succeed(State.ATE_A_ENTRADA)

    # ==================================================================
    # MANUTENCAO
    # ==================================================================

    def _do_manutencao(self) -> None:
        ctx = self.ctx
        self._situacao("antes da manutenção")
        ctx.log.info("Manutenção: cidade, venda e recompra")
        ok = self.vendor.run_maintenance()
        self._situacao("depois da manutenção")
        if ok:
            # Venda concluída: a contagem de runs do gatilho recomeça daqui, e as
            # rodadas de nova tentativa ZERAM. Sem zerar, duas falhas separadas
            # por horas de farm somariam e desligariam a conta sem motivo.
            self._runs_na_ultima_venda = ctx.stats.runs
            self._rodadas_de_venda_falhas = 0
            self._succeed(State.ATE_A_ENTRADA)
            return

        # ================================================================
        # NÃO VENDEU ⇒ MAIS UMA RUN DE BC E TENTA DE NOVO, ATÉ 3 RODADAS
        # ================================================================
        #
        # Desenho do usuário (18/08/2026): "caso não chegue em stone city depois
        # das tentativas, você executa mais uma run de bc e ao terminar tenta de
        # novo ir para stone, e vai fazendo isso até 3x".
        #
        # A RUN DE BC É A MANOBRA DE DESTRAVAMENTO, e isso é mais engenhoso do
        # que parece: a run termina passando pela saída da cave e pela Fay, que é
        # TROCA DE MAPA DE VERDADE -- e o `bot/bc/localizacao.py` registra que só
        # uma troca de mapa reescreve o campo do nome do lugar, que é justamente
        # a leitura que fica presa na área anterior.
        #
        # A RUN EXTRA NÃO CONTA PARA O GATILHO. `_runs_na_ultima_venda` NÃO é
        # atualizado aqui, então `runs >= alvo` continua verdadeiro e o bot volta
        # a tentar vender assim que a run terminar -- em vez de farmar as 8 (ou o
        # que o usuário configurou) outra vez.
        self._rodadas_de_venda_falhas += 1
        if self._rodadas_de_venda_falhas < RODADAS_DE_VENDA_ANTES_DE_DESLIGAR:
            ctx.log.warning(
                "Venda falhou (rodada %s de %s). Rodando mais uma run de BC "
                "para trocar de mapa e tentando de novo — esta run NÃO conta "
                "para o gatilho de venda.",
                self._rodadas_de_venda_falhas,
                RODADAS_DE_VENDA_ANTES_DE_DESLIGAR)
            self._fail("Manutenção incompleta; mais uma run antes de tentar de "
                       "novo", next_state=State.SITUAR)
            return

        # ================================================================
        # ESGOTOU: DESLIGA O BC DESTA CONTA
        # ================================================================
        #
        # Decisão do usuário: "caso não chegue a vender os itens, o bot deve
        # parar de funcionar, deve ser desligado". Mesmo desfecho que já existe
        # para "sem tecla de retorno" e para os 10 ciclos sem vender: a conta
        # fica ONLINE, LOGADA e com relogin ativo, e o checkbox desmarcado nas
        # duas interfaces é o sinal de que precisa de intervenção. Não fecha o
        # cliente e não para as outras contas.
        ctx.log.error(
            "Venda falhou nas %s rodadas, cada uma com uma run de BC no meio. "
            "DESLIGANDO o BC desta conta — ela fica online e logada. Confira a "
            "tecla de retorno (Guild Token / pedra) e o estoque de pedras.",
            RODADAS_DE_VENDA_ANTES_DE_DESLIGAR)
        ctx.account.bc_farm = False
        try:
            ctx.config.save()
        except Exception as exc:
            ctx.log.warning("Não consegui salvar a configuração: %s", exc)
        self._fail("Venda impossível; BC desligado nesta conta",
                   next_state=State.SITUAR)

    # ==================================================================
    # RECUPERAR
    # ==================================================================

    def _do_recuperar(self) -> None:
        """Recuperação após morte ou falhas em sequência."""
        ctx = self.ctx
        state = ctx.snapshot()
        s = self._situacao("recuperando")

        if state.dead:
            # A morte já foi registrada no diário por quem a detectou. Aqui só
            # revive e recomeça pelo começo -- morrer tira o personagem do lugar,
            # então nada do estado anterior vale mais.
            ctx.log.info("Revivendo")
            ctx.click(ctx.coords.revive_ok)
            ctx.tick(3.0)
            self.combat.ensure_pet()
            self.combat.heal_to_full()
            self._succeed(State.SITUAR)
            return

        if self.consecutive_failures >= 4:
            ctx.log.warning(
                "Quatro falhas seguidas. Reavaliando de onde estou (%s) em vez de "
                "insistir no mesmo passo.", s.resumo(),
            )
            diario.registrar_evento(
                ctx.account_login, "falhas-em-sequencia",
                f"{self.consecutive_failures} falhas; reavaliando",
                s.posicao, s.local,
            )
            self.consecutive_failures = 0
            self.state = State.SITUAR
            return

        # Uma falha isolada não justifica refazer nada: reavalia e segue.
        self.state = State.SITUAR

    # ==================================================================
    # Laço principal
    # ==================================================================

    _HANDLERS = {
        State.SITUAR: "_do_situar",
        State.PREPARAR: "_do_preparar",
        State.ATE_A_ENTRADA: "_do_ate_a_entrada",
        State.ENTRAR: "_do_entrar",
        State.CURAR: "_do_curar",
        State.ATE_O_ALTAR: "_do_ate_o_altar",
        State.ENTRAR_NO_COVIL: "_do_entrar_no_covil",
        State.ATE_OS_GUARDAS: "_do_ate_os_guardas",
        State.GUARDAS: "_do_guardas",
        State.ATE_O_BOSS: "_do_ate_o_boss",
        State.BOSS: "_do_boss",
        State.SAIR: "_do_sair",
        State.MANUTENCAO: "_do_manutencao",
        State.RECUPERAR: "_do_recuperar",
    }

    def _vender_ao_iniciar_se_estiver_na_cidade(self) -> None:
        """Começou o bot já em Stone City? Então vende ANTES de sair farmando.

        Pedido do usuário: quem para o bot na cidade quase sempre parou ali com
        a bolsa carregada, e sair para a cave sem vender é começar a execução
        com o espaço que ela vai precisar já ocupado.

        =================================================================
        POR QUE NÃO `run_maintenance()`, QUE É A VENDA DE SEMPRE
        =================================================================

        Ela é a ida COMPLETA à cidade, e começa por `voltar_para_a_cidade()` --
        o Guild Token ou a pedra de retorno. Estando já na cidade isso gastaria
        uma pedra (ou a recarga do token) para chegar onde o personagem já
        está. Pior: ela RECUSA a venda quando nenhuma tecla de retorno está
        configurada, e desliga o `bc_farm` da conta -- uma exigência que aqui
        não faz sentido nenhum, porque não há de onde voltar.

        Então o que se chama é o PAR que o `teste_venda` já validou para
        exatamente esta situação: caminhar até o Rich Man e vender. Nada do
        `VendorService` foi tocado.

        `buy_supplies()` fica de fora pelo mesmo motivo de lá: ele repõe a
        pedra gasta, e aqui não se gastou nenhuma.

        =================================================================
        COMPLEMENTO: NUNCA IMPEDE O BOT DE COMEÇAR
        =================================================================

        Falha na venda vira aviso e a execução segue para o SITUAR normal. Parar
        aqui trocaria "comecei sem vender" por "não comecei", que é pior.
        Parada e desligamento do farm continuam subindo, como em qualquer outro
        ponto do laço.
        """
        ctx = self.ctx
        # COORDENADA **OU** NOME -- e aqui os dois, ao contrário do resto da
        # rotina. A caixa de coordenada é um limite inferior (foi derivada de
        # dois pontos, e a cidade é grande), e medido em produção uma partida em
        # (237,-484) foi direto para a Fay com a bolsa cheia por ficar 6
        # unidades acima do corte. Ver `mapa_bc.esta_em_stone_city`.
        pos = ctx.memory.position()
        local = ctx.memory.location()
        if not mapa_bc.esta_em_stone_city(pos, local):
            return

        ctx.log.info(
            "Iniciando em Stone City %s: vou VENDER antes de começar o farm "
            "(não uso item de retorno — já estou na cidade).", pos)
        try:
            if not self.vendor.travel_to_vendor():
                ctx.log.warning(
                    "Não cheguei ao vendedor na venda de início. Seguindo para "
                    "o farm assim mesmo.")
                return
            vendidos = self.vendor.sell_from_slot()
            ctx.log.info("Venda de início concluída: %s item(ns).", vendidos)
        except (StopRequested, Disconnected, FarmDesligado):
            raise
        except Exception as exc:
            ctx.log.exception(
                "A venda de início falhou (%s). Seguindo para o farm.", exc)

    def run(
        self,
        max_runs: int | None = None,
        should_continue: Callable[[], bool] | None = None,
    ) -> None:
        """Executa ciclos até parada, desconexão ou limite de runs.

        `should_continue` é consultado no início de cada iteração. É assim que
        desligar o farm pela interface tem efeito imediato: a rotina devolve o
        controle num ponto seguro, entre estados, sem interromper uma ação pela
        metade.

        Não trata Disconnected: deixa subir para o supervisor, que é quem sabe
        matar o cliente, relançar e relogar.
        """
        ctx = self.ctx
        ctx.log.info(
            "Iniciando boss-rush | montaria %s%% | rota %s | venda a cada %s "
            "runs (do slot %s) | %s bolsa(s) = %s espaços | %s",
            ctx.settings.mount_speed_pct,
            ctx.settings.bc.route.mode,
            ctx.settings.bc.vendor.runs_before_selling,
            ctx.settings.bc.vendor.sell_start_slot,
            ctx.settings.bags.bolsas, ctx.settings.bags.capacidade,
            self.nav.velocidade.estado_para_log(),
        )
        # Começa SITUANDO, nunca preparando. Assim uma conta que já está no meio
        # da cave continua de onde estava, em vez de tentar entrar de novo estando
        # dentro -- o que fazia o clique cair no chão e tirar o personagem da rota.
        self.state = State.SITUAR
        # A contagem de runs do gatilho de venda recomeça a cada execução do bot
        # BC: só conta as runs dali pra frente, e terminar a execução volta o
        # contador a zero (a próxima `run()` reajusta a base aqui).
        self._runs_na_ultima_venda = ctx.stats.runs

        # Enquanto o laço roda, desligar o BC pela interface precisa cortar a
        # fase atual NO MEIO (navigation, combate, entrada, venda). `farming` é o
        # sinal para `ctx.raise_if_stopped` detonar `FarmDesligado` quando
        # `bc_farm` apagar. O `finally` garante que a flag cai mesmo em exceção
        # ou `return` -- senão o laço "online" seguinte (fora do farming)
        # re-detonaria a parada e derrubaria a sessão, o oposto do desejado.
        ctx.farming = True
        # QUEM está no ar. É o que faz a parada conferir o
        # interruptor desta cave, e não `account.farms`.
        ctx.cave_em_farm = CAVE_BC
        try:
            self._vender_ao_iniciar_se_estiver_na_cidade()

            # GARANTIR QUE O PET ESTÁ ATIVO ANTES DE COMEÇAR O FARM.
            #
            # O pet é essencial para o farm (auto-pick e dano), e sem ele a run é
            # desperdício. `ensure_pet()` também roda no PREPARAR, mas esse estado
            # só acontece quando o bot está fora da cave e precisa se preparar. Se
            # o bot começar já dentro (ou o SITUAR pular direto para estados
            # internos), o pet nunca seria verificado -- e um pet caído passaria
            # despercebido até o usuário notar que nada está sendo coletado.
            #
            # Chamada aqui: ANTES do loop, depois da venda inicial (que pode ter
            # movido o personagem), e coberta pelo `ctx.farming = True` (permite
            # que o usuário pare caso a invocação trave). Se a memória não for
            # confiável, `ensure_pet()` invoca UMA vez e segue -- o fallback é
            # melhor que travar na largada.
            if ctx.settings.pet.summon_on_login:
                self.combat.ensure_pet()

            while True:
                if should_continue is not None and not should_continue():
                    ctx.log.info("Farm desligado; devolvendo o controle")
                    return
                if max_runs is not None and ctx.runs_completed >= max_runs:
                    ctx.log.info("Limite de %s runs atingido", max_runs)
                    return

                self._guard()
                # Pet passa fome em qualquer estado, então a checagem fica no laço
                # principal. Dentro da cave ela não faz nada (alimentar exige
                # desmontar); o adiantamento antes de entrar cobre esse caso.
                #self.combat.feed_pet(
                #    dentro_da_cave=self.state in ESTADOS_DENTRO_DA_CAVE
                #)
                # Contexto estruturado do JSON de dev: registra a fase atual
                # antes de o handler rodar (o log do handler sai com esta fase).
                logmodo.fase(self.state.name)
                handler = getattr(self, self._HANDLERS[self.state])
                previous = self.state
                # Cronômetro por estado. É o número que diz ONDE o tempo da run é
                # gasto -- foi assim que apareceu que o trajeto da cave custava 8,6 s
                # por waypoint. Sem esta linha, otimizar é adivinhar.
                comecou = time.time()
                try:
                    # UM NOME POR ESTADO. O `comecou` logo acima ja mede e loga a
                    # passagem individual; o cronometro agrega a DISTRIBUICAO
                    # (n, minimo, media, maximo por estado), que e o que mostra
                    # se um estado piorou -- uma linha solta nao mostra.
                    #
                    # Custo zero de verdade aqui: o estado mais curto da rotina
                    # leva dezenas de milissegundos contra os 310 ns do
                    # cronometro. Ver o piso em `core/cronometro.py`.
                    with cronometro(f"bc.estado.{previous.name}"):
                        handler()
                except (StopRequested, Disconnected):
                    raise
                except PersonagemMortoNoPortao as exc:
                    # NAO e excecao inesperada: e o portao da montaria avisando
                    # que nao ha o que insistir. Sem este ramo ele cairia no
                    # `except Exception` abaixo e sairia com traceback no log,
                    # como se fosse defeito. O desfecho e o mesmo do `_guard()`
                    # ao ver o personagem morto -- RECUPERAR, que revive.
                    ctx.log.warning("%s. Indo para RECUPERAR.", exc)
                    self.state = State.RECUPERAR
                except FarmDesligado:
                    ctx.log.info(
                        "BC desligado no meio de %s; devolvendo o controle "
                        "(conta fica online, parada, com relogin)",
                        previous.name)
                    return
                except Exception as exc:
                    ctx.log.exception("Erro no estado %s: %s", previous.name, exc)
                    diario.registrar_evento(
                        ctx.account_login, "excecao",
                        f"{previous.name}: {type(exc).__name__}: {exc}",
                        ctx.memory.position(), ctx.memory.location(),
                    )
                    self._fail(f"exceção em {previous.name}")

                gasto = time.time() - comecou
                if self.state is not previous:
                    ctx.log.info("%s levou %.1fs -> %s | posição %s",
                                 previous.name, gasto, self.state.name,
                                 ctx.memory.position())
                elif gasto > 5.0:
                    ctx.log.info("%s levou %.1fs e continua no mesmo estado",
                                 previous.name, gasto)

                # Pausa mínima entre estados. Dentro da cave cada décimo conta: os
                # mobs do caminho continuam vindo enquanto o bot pensa.
                ctx.tick(0.06 if self.state in ESTADOS_DENTRO_DA_CAVE else 0.15)
        except FarmDesligado:
            # Rede de segurança: um `FarmDesligado` pode vir também da `ctx.tick`
            # do fim do laço (o BC apagou ENTRE fases), fora do `try` do handler.
            # Nesse caso também devolvemos o controle limpo, sem derrubar a sessão.
            ctx.log.info("BC desligado; devolvendo o controle")
            return
        finally:
            ctx.farming = False
            ctx.cave_em_farm = ""
            logmodo.limpar()
