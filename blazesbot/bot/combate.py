"""
Combate, cura e cuidado do personagem.

O foco do BlazesBot é boss-rush: ignorar os mobs do caminho e matar apenas o que
precisa morrer -- os quatro guardas do covil e o Blaze Skull Marshal. Por isso o
combate aqui é deliberadamente simples: alvo único, rotação de skills, poção por
limiar. Não há kite, pull nem escolha entre vários alvos.

=========================================================================
DUAS REGRAS DO JOGO QUE MANDAM NESTE ARQUIVO
=========================================================================

1. MONTADO NÃO SE FAZ NADA. Poção, comida de pet, invocar pet, cura, buff, sentar
   -- tudo exige estar a pé. A única exceção é a skill de velocidade da montaria
   (ver `velocidade.py`). Apertar a tecla montado não dá erro: simplesmente não
   acontece nada, e o bot achava que tinha usado. Daí a função
   `_preparar_para_agir()`, chamada antes de qualquer item ou skill fora de
   combate.

2. SKILL EM SI MESMO PRECISA DE ALVO -- E O ALVO É VOCÊ. A tecla F1 seleciona o
   próprio personagem. Sem ela, a skill de cura e os buffs saem no alvo que
   estiver selecionado (um mob, o pet) ou não saem. Um F1 antes resolve, e é
   barato.

=========================================================================
O BOSS TEM SEGUNDA FASE
=========================================================================

Blaze Skull Marshal e Blue Fire Whip Skeleton se TRANSFORMAM quando o HP chega a
zero. Portanto "HP do alvo == 0" NÃO é vitória -- é, na melhor das hipóteses, a
transformação.

A vitória é reconhecida por AUSÊNCIA DE ALVO VIVO, confirmada de três formas
independentes (ver as constantes `CONFIRMACOES_DE_MORTE`,
`SEGUNDOS_SEM_ALVO_PARA_MORTE` e `TABS_PARA_REFUTAR_A_MORTE`): muitas buscas com
TAB sem achar nada, tempo contínuo sem nada vivo, e uma varredura final que TENTA
achar algo vivo antes de o bot ir embora.

Antes a vitória era "o personagem saiu do estado de batalha". Essa leitura foi
removida do bot inteiro: a flag de combate fica ligada com qualquer mob por perto,
demora a baixar e já foi vista presa.

A segunda fase troca o alvo sozinha, então ali o TAB é desnecessário -- e apertar
TAB no meio da troca é como o bot perdia o boss para selecionar o pet.

=========================================================================
MORTE É BUG
=========================================================================

Uma conta só é marcada para fazer BC quando ela dá conta da cave sem morrer. Se o
personagem morre, algo no bot está errado -- rota, cura, limiar ou alvo. Por isso
toda morte vai para `logs\\eventos.log` com HP, posição, local e o que estava
acontecendo. É o registro que permite descobrir o padrão depois.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..core import diario, vision
from ..core.pet import SEGUNDOS_PARA_A_COMIDA_SER_USADA, PetFeeder
from ..core.target_hybrid import MorteDoAlvo, TargetHybrid
from . import hotbar
from .context import BotContext, Disconnected
from .navegacao import Navigator

# Tecla que seleciona o PRÓPRIO personagem. É padrão do cliente e não é
# configurável de propósito: não é preferência, é como o jogo funciona.
TECLA_AUTO_SELECAO = "F1"
#
# Quatro segundos sentado recuperam vida e mana de graça, e é o único momento da
# run em que dá: dentro da cave o trem de mobs não deixa, e na frente do boss é a
# luta que decide a run. Sentar aqui é o que evita começar a segunda fase sem mana.
SEGUNDOS_SENTADO_APOS_GUARDAS = 4.0

# ===========================================================================
# A POÇÃO DE VIDA LEVA 15 SEGUNDOS, E ANDAR CANCELA
# ===========================================================================
#
# É mecânica do jogo, não preferência -- por isso mora aqui e não na configuração.
# A poção não devolve vida de uma vez: ela cura ao longo de 15 segundos, e
# qualquer movimento interrompe o efeito.
#
# A consequência é que "apertar a poção" e "ter usado a poção" são coisas
# diferentes. Disparar e sair andando gasta o item e recebe uma fração do efeito,
# que era exatamente o que a cura fazia antes: apertava, esperava 0,3 s e
# liberava a travessia.
#
# Por isso a espera é a DURAÇÃO do efeito, e o personagem fica parado nela.
SEGUNDOS_DA_POCAO_DE_VIDA = 15.0

# Respiro depois da Super Skill de cura. Ela é instantânea; isto é só o tempo de
# o servidor aplicar e a memória refletir, para a leitura seguinte já valer.
SEGUNDOS_DEPOIS_DA_SUPER_SKILL = 12.0

# ===========================================================================
# TOP-UP PRÉ-BOSS ESTÁ FORA DE COMBATE, NÃO NA ESPERA DO BOSS
# ===========================================================================
#
# Limiar de HP que decide se vale/não o top-up no waypoint dos 4 mobs, DEPOIS de
# matá-los e SAIR de combate, ANTES de encostar no boss. Recuperar na frente do
# boss é desperdício: o boss encosta e a poção para de curar na hora. Por isso a
# cura preventiva mora aqui (no meio dos guardas), e na espera do boss o bot NÃO
# gasta item -- senta/sem beber, ver `esperar_entrar_em_combate`.
#
# O VALOR É ESTRATÉGIA, não mecânica: abaixo disso o personagem provavelmente
# não aguenta a fase 2. 40% é o pedido do usuário ("só necessário se a vida
# estiver abaixo de 40%"). Não é editável na tela por enquanto, como
# `max_heal_seconds` -- é o mesmo espírito: rede de segurança, não estratégia
# que convém à interface.
LIMINAR_TOPUP_ANTES_DO_BOSS = 50.0

# Espera depois de UM TAB, para a seleção chegar da rede antes de conferir.
ESPERA_DEPOIS_DO_TAB = 0.6

# ===========================================================================
# TOP-UP ANTES DO BOSS: ATÉ 100%, SENTADO, E OS 15 s INTEIROS
# ===========================================================================
#
# Três defeitos relatados pelo usuário em 19/08/2026, e os três estavam no
# mesmo trecho:
#
# 1. **NÃO SENTAVA.** O código apertava a poção e esperava. `k.sit` não era
#    tocado. Quem senta é o `heal_to_full`, que roda FORA da instância.
#
# 2. **A ESPERA SAÍA CURTA.** `ctx.tick(15.0)` passa o valor por
#    `jitter(base, 0.15)`, ou seja **12,75 s a 17,25 s**. Nas vezes em que
#    sorteava baixo faltavam 2,25 s do temporizador da poção. O jitter existe
#    para o bot não ter delays perfeitamente fixos -- mas estava sendo aplicado
#    a uma DURAÇÃO QUE O JOGO EXIGE, não a uma cadência nossa. Agora o prazo é
#    por RELÓGIO: as fatias podem jitterar à vontade, o total não encurta.
#
# 3. **NÃO CONFERIA NADA.** Logava a vida resultante e seguia para o boss com
#    qualquer valor. Uma poção num personagem a 20% não chega perto de cheio, e
#    o gatilho só dispara abaixo de 50%.
#
# A REGRA NOVA, palavra do usuário: *"é importante ficar até o final e conferir
# se está com a vida cheia para matar, pois quem precisou da poção vai precisar
# se curar -- normalmente é um personagem mais fraco, que depende de estar full
# vida para começar a luta contra o boss."*
ALVO_DO_TOPUP_ANTES_DO_BOSS = 100.0

# Fatia da espera da poção. O TOTAL é medido por relógio (ver acima), então esta
# fatia só governa de quanto em quanto tempo se pergunta se a vida já chegou --
# e perguntar é leitura de memória, que não fala com o jogo.
FATIA_DA_ESPERA_DA_POCAO = 0.5

# NÃO EXISTE "SENTAR NO TOP-UP", e a ausência é deliberada.
#
# A primeira versão sentava antes de beber, e o usuário mandou tirar em
# 19/08/2026: *"antes de usar a poção de cura não precisa sentar... a poção já faz
# sentar. O sentar pode ser usado em outros momentos caso necessário."*
#
# E é bom que tenha saído, porque `sit` é INTERRUPTOR: cada aperto desnecessário
# é uma chance de o personagem terminar no estado ERRADO. Com a poção sentando
# sozinha, apertar a tecla antes só acrescenta um caminho para dar errado -- e o
# `heal_to_full`, fora da instância, continua sentando onde faz falta.
#
# Não ficou interruptor porque o caminho nunca esteve em uso: a regra da casa
# (`X = False` no topo) existe para preservar comportamento MEDIDO que sai de
# operação, não para guardar código que o usuário recusou antes de rodar.

# ===========================================================================
# CURA POR SKILL -- interruptor e cadência
# ===========================================================================
#
# `"skill_em_laco"` = quem tem tecla de cura repete a SKILL até a vida bastar,
#                     em vez de gastar poção. É o padrão.
# `"pocao"`         = comportamento anterior: a skill sai UMA vez e o resto é
#                     poção. Reverter é trocar esta palavra.
#
# ---------------------------------------------------------------------------
# A REGRA QUE MANDA EM TUDO: F1 NUNCA SAI EM BATALHA
# ---------------------------------------------------------------------------
#
# Skill em si mesmo precisa de alvo, e o alvo é o próprio personagem -- por isso
# `auto_selecionar()` (F1) antes da cura. Só que **F1 no meio da luta LARGA o
# alvo**, e o `CLAUDE.md` diz que o engajamento do boss depende de quem está
# selecionado: *"TAB sozinho não engaja, quem engaja é o golpe"*.
#
# Isto era uma bomba armada, não um defeito ativo. Sem tecla de cura configurada,
# o `maintain` em batalha só bebia poção -- e poção não precisa de alvo, então
# nada acontecia com a seleção. **O F1 passaria a sair no meio da luta do boss no
# dia em que alguém configurasse a tecla de cura da Fairy.**
#
# Decisão do usuário, e ela é mais estrita que "tire o F1": **em batalha o
# personagem nunca tenta se curar**. Durante a luta o bot só luta. A cura mora
# nos intervalos, que é onde o bot já parava para se curar.
#
# ---------------------------------------------------------------------------
# APERTAR E CONFERIR TÊM CADÊNCIAS DIFERENTES, E É AÍ QUE ESTÁ O GANHO
# ---------------------------------------------------------------------------
#
# O pedido original era apertar a cura a cada 0,1 s até bastar. A cura tem
# **1,6 s de conjuração** (informado pelo usuário), então 0,1 s são DEZESSEIS
# apertos por conjuração -- e os dois modos de falha são reais:
#
#   * custo: dezesseis mensagens onde uma bastava, e o usuário já levantou o
#     risco de lag;
#   * pior: se o cliente REINICIA a conjuração ao receber a tecla de novo, o laço
#     nunca completa uma cura -- e parece estar trabalhando o tempo todo. Isso
#     não foi medido, e não vou deixar em pé um caminho que depende de não ser
#     verdade.
#
# APERTAR e CONFERIR têm custos opostos: apertar fala com o jogo; conferir é uma
# leitura de memória, que não toca nele. Então cada um tem a sua cadência:
#
#     aperta ....... uma vez por conjuração (1,6 s + margem)
#     confere ...... a cada 0,1 s, e o instante em que a vida SOBE encerra a
#                    espera -- sem esperar o relógio fechar
#
# É a regra da casa: *"onde havia espera cega, agora se PERGUNTA"*. Conjuração
# que termina em 1,4 s não paga 0,2 s de espera à toa, e conjuração interrompida
# é descoberta em 0,1 s em vez de 1,6 s.
#
# ---------------------------------------------------------------------------
# O TETO É POR TENTATIVA SEM EFEITO, NÃO POR RELÓGIO
# ---------------------------------------------------------------------------
#
# `max_heal_seconds = 120` foi dimensionado PARA POÇÃO -- o comentário dele diz
# "cada poção leva 15 s, então isto dá oito". Para skill esse número não quer
# dizer nada, e um teto por relógio faria uma conta sem mana passar dois minutos
# apertando tecla à toa.
#
# A pergunta certa não é "já passaram 120 s?", é "a vida subiu?". Três
# conjurações seguidas sem a vida subir significam que a cura não está saindo
# (recarga, mana ou interrupção): cai para poção se houver tecla, senão avisa e
# segue. Custa ~7 s descobrir, contra 120 s.
#
# NENHUM DESTES NÚMEROS FOI MEDIDO AQUI, tirando o 1,6 s que o usuário informou.
# O log registra cada cura -- vida antes, vida depois, quantos apertos, por que
# parou -- e é dele que sai o ajuste depois da primeira noite de operação.
MODO_DE_CURA = "skill_em_laco"

# Conjuração da skill de cura. Informado pelo usuário em 19/08/2026.
SEGUNDOS_DE_CONJURACAO_DA_CURA = 1.6
# Folga sobre a conjuração: latência da mensagem mais o jogo processar e a
# memória refletir. Sem ela, uma cura que saiu seria contada como falha.
MARGEM_DA_CONJURACAO = 0.6
# De quanto em quanto tempo perguntar se a vida subiu. É leitura de memória --
# não fala com o jogo, então pode ser curto.
INTERVALO_DE_CONFERENCIA = 0.1
# Conjurações seguidas sem a vida subir antes de concluir que a cura não sai.
TENTATIVAS_SEM_EFEITO = 3
# Quanto a vida precisa subir para a conjuração contar como bem-sucedida. Um
# ponto percentual: menos que isso é ruído de leitura ou regeneração natural, e
# contá-lo como sucesso faria o laço girar para sempre achando que progride.
SUBIDA_MINIMA_PARA_CONTAR = 1.0

# ===========================================================================
# BREAK SOUL -- SÓ NA SEGUNDA FASE DO BOSS
# ===========================================================================
#
# `True`  = a Break Soul entra na rotação APENAS na fase 2 do boss.
# `False` = comportamento anterior: entrava em toda rotação, sempre que a tecla
#           estivesse configurada.
#
# ANTES ELA SAÍA EM TUDO. Bastava a tecla existir e ela era acrescentada à
# rotação em `_rotacao_de_ataque` -- ou seja, contra os quatro Gun Witch, contra
# qualquer mob do caminho e contra a primeira fase do boss.
#
# É onde ela NÃO serve. Decisão do usuário em 19/08/2026: a Break Soul é útil na
# **segunda fase do `Blaze Skull Marshal`**, e só ali. Gastá-la antes é chegar na
# fase que decide a run com a skill em recarga -- o mesmo raciocínio que já tirou
# o AoE da luta dos guardas, e que está escrito no `_rotacao_de_ataque`: *"mana é
# exatamente o que falta na segunda fase do boss, logo depois"*.
#
# COMO A FASE É SABIDA. `fight_boss` conta `fases_vistas`, e a virada é detectada
# por duas formas independentes (entidade nova, e HP restaurado no mesmo
# endereço). Quando o contador chega a 2, o motor levanta a bandeira
# `_na_segunda_fase_do_boss`, e é ela que a rotação lê.
#
# A BANDEIRA É POR LUTA, e isso não é detalhe: ela nasce baixa no começo de
# `fight_boss` e é baixada no `finally`. Bandeira que sobrevive à luta faria a
# Break Soul sair contra os guardas da run seguinte -- exatamente o defeito que
# esta mudança existe para corrigir, com o agravante de ser intermitente.
USAR_BREAK_SOUL_SO_NA_FASE_2 = True



# ===========================================================================
# CONFIRMAÇÃO DA MORTE DO BOSS -- três exigências, e cada uma cobre uma falha
# ===========================================================================
#
# Sair da luta achando que venceu, com o boss vivo, é o erro mais caro do bot: ele
# vai embora, a instância se perde e a run inteira é desperdiçada. Cada número
# abaixo entrou porque uma simulação produziu exatamente esse erro sem ele.
#
# 1. CONTAGEM -- buscas ATIVAS com TAB sem achar nada vivo.
CONFIRMACOES_DE_MORTE = 6
# 2. TEMPO -- segundos contínuos sem nada vivo selecionado. Dá lastro à contagem:
#    sem ele, seis leituras rápidas fechavam em ~2,5 s e uma deseleção momentânea
#    de 4 s virava "vitória".
SEGUNDOS_SEM_ALVO_PARA_MORTE = 3.0
# 3. REFUTAÇÃO ATIVA -- antes de declarar vitória, o bot TENTA achar algo vivo.
#    Só passivamente contar leituras tem um limite: uma deseleção mais longa que a
#    janela sempre engana. Tentar selecionar é diferente de esperar não ver.
#
#    Usa `selecionar_qualquer_alvo` e não `acquire_target(boss)` de propósito: a
#    segunda forma do boss pode ter OUTRO nome, e comparar nome faria a refutação
#    falhar justamente com o boss vivo na frente. No covil não sobra mais nada além
#    dele -- os quatro guardas morreram antes -- então "qualquer coisa viva" é ele.
TABS_PARA_REFUTAR_A_MORTE = 4

# ===========================================================================
# O FLUXO DA RUN PASSOU A SER DECIDIDO PELA FLAG DE COMBATE
# ===========================================================================
#
# INVERSÃO DELIBERADA de uma decisão anterior deste arquivo. Até agora a flag de
# combate estava proibida de decidir qualquer coisa, e o combate era conduzido
# pelos ponteiros de alvo: mirar, ler o HP, esperar zerar, dar TAB no próximo.
# Agora é o contrário -- a flag manda, e os ponteiros de alvo saem do caminho.
#
# COMO O NOVO FLUXO FUNCIONA, nas duas fases:
#
#   1. Chega no waypoint. NÃO aperta TAB.
#   2. Espera a flag LIGAR (os mobs atacam sozinhos; quem ataca vira o alvo).
#   3. Com a flag ligada, gira a rotação de skills configurada.
#   4. Espera a flag DESLIGAR. Nos guardas isso significa "os quatro caíram";
#      no boss significa "o boss caiu".
#   5. Guardas: senta exatamente 4 s e vai para o boss. Boss: sai da cave.
#
# AS TRÊS RESSALVAS QUE MOTIVARAM A PROIBIÇÃO ANTIGA CONTINUAM VALENDO, e cada
# uma delas tem um contrapeso explícito aqui. Elas não são teoria: são o que foi
# medido nesta flag, neste cliente.
#
#   (a) "FICA LIGADA QUASE TODA A TRAVESSIA DA CAVE" -- os mobs do caminho vêm
#       atrás. No fluxo novo isso não atrapalha, ajuda: chegar no waypoint já em
#       combate só faz o passo 2 terminar na hora. E a espera pela flag só começa
#       DEPOIS de a navegação terminar, então a travessia não é afetada.
#
#   (b) "DEMORA A BAIXAR DEPOIS DO ÚLTIMO GOLPE" -- também ajuda. O risco real do
#       fluxo novo é o oposto: a flag PISCAR para falso entre um guarda e o
#       seguinte, encerrando a fase 1 com três guardas vivos. Por isso a saída de
#       combate precisa de CONFIRMAÇÃO CONTÍNUA (`CONFIRMACAO_DE_SAIDA_DE_COMBATE`)
#       em vez de valer na primeira leitura falsa.
#
#   (c) "JÁ FOI VISTA PRESA" -- esta é a que pode travar a run, e é a única sem
#       contrapeso possível na própria flag: presa em ligado, a fase nunca
#       termina. Contra isso só existe prazo (`LIMITE_DA_FASE_*`). Estourar o
#       prazo NÃO é vitória -- é falha registrada, para o log dizer que a flag
#       travou em vez de o bot sair achando que matou.
#
# E O QUE A FLAG NÃO DECIDE:
#
#   POÇÃO DE BATALHA x NORMAL ..... continua vindo de QUEM CHAMA
#                                   (`maintain(..., em_luta=)`). Nas fases novas o
#                                   chamador sabe: está atacando, logo está em
#                                   luta. Ler a flag para isso seria trocar uma
#                                   certeza por uma leitura.
#   MONTARIA ...................... nada. Aciona a tecla e confere a memória
#                                   (ver `navigation.garantir_montaria_para_andar`).
#   MORTE DO PERSONAGEM ........... o HP do PRÓPRIO personagem. Morrer também tira
#                                   o personagem do combate, então sem esta
#                                   checagem "saiu do combate" no boss seria lido
#                                   como vitória justamente quando a run se perdeu.
#
# Os caminhos antigos (`lutar_contra_guardas`, `fight_boss`, `_mirar_em_um_mob`,
# `_mirar_no_boss`) FICARAM NO ARQUIVO, isolados e sem chamador na run de BC. Ver
# o bloco "EM STANDBY" antes deles.


# ---------------------------------------------------------------------------
# Números do fluxo por flag de combate
# ---------------------------------------------------------------------------

# Passo da vigia da flag. É o que "não bloqueante" significa na prática: o laço
# nunca dorme mais do que isto sem reler o estado, então a reação a entrar ou sair
# de combate acontece dentro de um décimo de segundo.
#
# Custo: a leitura é uma cadeia curta de ponteiro mais UM byte. Medida em 0,3 µs
# na mesma bancada que mediu `conferir_estado`. Dez leituras por segundo por conta
# é ruído, mesmo com quatro clientes.
PASSO_DA_VIGIA_DE_COMBATE = 0.05

# Quanto esperar a flag LIGAR depois de chegar no waypoint.
#
# Não é o tempo da luta -- é só o tempo até os mobs encostarem. Se estourar, é
# porque não havia ninguém para atacar (covil já limpo, ou o personagem parou
# longe do ponto).
ESPERA_PARA_ENTRAR_EM_COMBATE = 5.0

# Prazo curto para os GUARDAS (os 4 mobs no waypoint antes do boss).
#
# Os guardas atacam na chegada -- se não vierem em 2.5 s, o personagem está longe
# demais do ponto ou o covil já foi limpo nesta run. Nesse caso, continuar para
# o boss é sempre melhor que bloquear a run por 30 s. O fluxo já trata o caso de
# "ninguém atacou": `FimDeCombate` com `saiu_de_combate=False` segue para
# `State.ATE_O_BOSS` (ver `_do_guardas`).
ESPERA_ENTRAR_EM_COMBATE_GUARDAS = 5.0

# NO BOSS A ESPERA NÃO TEM PRAZO.
#
# O boss pode estar afastado do waypoint e demorar a engajar. Desistir por tempo
# ali é o pior desfecho possível: a instância já foi gasta -- time montado, reset
# consumido, travessia inteira feita -- e sair sem matar joga a run fora. Esperar
# não custa nada em comparação.
#
# Isto NÃO é um laço cego. Ele continua saindo por parada do usuário e por morte
# do personagem, que são as duas coisas que tornam a espera inútil. O que não
# existe é limite de tempo.
SEM_PRAZO = None

# Cadência do aviso enquanto espera sem prazo. Uma espera sem limite PRECISA
# aparecer no log: sem esta linha, "esperando o boss chegar" e "travado" ficam
# indistinguíveis para quem lê.
AVISO_DA_ESPERA_SEM_PRAZO = 10

# Por quanto tempo CONTÍNUO a flag precisa ficar em falso para a saída valer.
#
# É o contrapeso da ressalva (b). Quatro guardas morrendo um a um dão janelas de
# não-combate entre eles; sem esta confirmação a fase 1 terminaria no primeiro.
# Um segundo e meio é maior que qualquer piscada observada entre mobs e muito
# menor que o intervalo entre as duas fases da run.
CONFIRMACAO_DE_SAIDA_DE_COMBATE = 2.5

# ===========================================================================
# NO BOSS, O GOLPE NÃO PARA DURANTE A CONFIRMAÇÃO DE SAÍDA
# ===========================================================================
#
# O DEFEITO, MEDIDO NO LOG DE 19/08/2026, conta 'creubo':
#
#     16:38:39  Em combate (boss) depois de 0.0s esperando
#     16:39:01  A flag de combate baixou em boss (22s de luta, 98 golpes).
#               Confirmando por 2.5s antes de encerrar.
#     16:39:03  Fora de combate confirmado: 2.5s contínuos com a flag baixa
#     16:39:03  Sai de combate no boss -- considerando o Blaze Skull Marshal
#               derrotado
#     16:39:04  package_courage ... -> SAIR -> Skull Herald
#
# O usuário viu isso na tela: *"eu vi acontecer visualmente, de entender que foi
# para a segunda fase e ele tentar usar o auto pick, daí abriu o inventário e foi
# para o Skull Herald para sair da cave; só não saiu pq eu desativei o bot."*
#
# O BOSS ESTAVA VIVO. O docstring de `fase_do_boss_por_combate` listava esse caso
# como *"flag baixando com o boss vivo e o personagem vivo -- NÃO FOI
# OBSERVADO"*. Agora foi.
#
# ---------------------------------------------------------------------------
# O MECANISMO: o bot fica PASSIVO justamente na virada de fase
# ---------------------------------------------------------------------------
#
# A troca de fase tira o personagem do combate por um instante. O bloco do golpe
# tinha `if not (falso_desde and ja_entrou)`, ou seja **para de bater no momento
# em que a flag baixa** -- e quem engaja a fase seguinte é o GOLPE ("a fase 2 pega
# o alvo sozinha assim que ataca"). Parado, ninguém reengaja; a flag fica baixa os
# 2,5 s inteiros e a saída é confirmada com o boss de pé.
#
# Bater durante a confirmação inverte isso: o boss em transformação volta a
# engajar, a flag sobe, `falso_desde` zera e a luta continua. Boss morto de
# verdade não reage a golpe nenhum, a flag fica baixa e a vitória sai igual.
#
# **A REGRA DA VITÓRIA NÃO MUDA, e é ordem do usuário:** *"o boss derrotado só
# deve ser considerado quando sai de batalha."* Não há confirmação por imagem nem
# por ponteiro aqui -- o que muda é só o bot deixar de ficar passivo enquanto
# confirma.
#
# ---------------------------------------------------------------------------
# SÓ NO BOSS, e a razão é o motivo pelo qual o golpe parava
# ---------------------------------------------------------------------------
#
# Parar de bater foi correção de um defeito REAL: *"o bot batendo por segundos
# depois de a luta acabar -- que é como se convida o mob seguinte."* Isso vale nos
# GUARDAS, onde há mais mobs no covil. Na sala do boss não há mob seguinte para
# convidar, e depois dele o bot vai embora.
#
# Então os guardas continuam parando o golpe na hora, e só o boss insiste.
ATACAR_DURANTE_A_CONFIRMACAO_NO_BOSS = True

# ===========================================================================
# NOS GUARDAS, O PORTÃO DE NOME NÃO ENCERRA A FASE -- ELE SÓ PARA O GOLPE
# ===========================================================================
#
# Pedido do usuário em 19/08/2026, na sequência do defeito do boss: *"no waypoint
# do Gun Witch, também só deve considerar os 4 Gun Witch mortos quando sair de
# batalha, para garantir 100%, pois não pode chegar no waypoint do boss já estando
# em batalha."*
#
# ---------------------------------------------------------------------------
# POR QUE CHEGAR NO BOSS EM COMBATE PERDE A RUN
# ---------------------------------------------------------------------------
#
# `fase_do_boss_por_combate` começa com `esperar_entrar_em_combate("boss")`. Com a
# flag JÁ ALTA ela devolve na hora, o bot entra na rotação contra o que estava
# batendo nele, e quando ISSO morre a flag baixa -- e a flag baixando é o que
# declara o boss derrotado. A run vai para o loot e para o Skull Herald sem o boss
# ter sido tocado.
#
# É o MESMO desfecho do defeito da virada de fase (ver
# `ATACAR_DURANTE_A_CONFIRMACAO_NO_BOSS`), por outra porta. Por isso o pedido é
# "para garantir 100%".
#
# ---------------------------------------------------------------------------
# O QUE MUDA, E O QUE NÃO MUDA
# ---------------------------------------------------------------------------
#
# O portão de nome continua existindo e continua PARANDO O GOLPE na primeira
# leitura -- a regra de não bater no que sobrou é anterior e tem medição própria:
# *"bater no que sobrou puxaria mob que não precisava vir e gastaria tempo de run
# -- foi assim que a run das 11:33 saiu da rota."*
#
# O que ele deixa de fazer é ENCERRAR a fase. Em vez de devolver vitória com a
# flag alta, o bot para de bater e de dar TAB e ESPERA a saída de combate, que é
# quem sempre decidiu o fim da fase.
#
# O mecanismo já existia no arquivo, e é o do Cemetery Guard: `pode_bater = False`
# e segue no laço até a flag baixar. Este bloco só faz o portão de nome usar a
# mesma porta -- não inventa caminho novo.
#
# ---------------------------------------------------------------------------
# O CUSTO, DITO INTEIRO
# ---------------------------------------------------------------------------
#
# Parado e ainda em combate, nada mata o que está batendo. Se a flag não baixar, a
# fase estoura `LIMITE_DA_FASE_DOS_GUARDAS` e devolve **derrota** -- a run falha em
# vez de seguir. É de propósito, e é a troca que o usuário pediu: run que falha o
# supervisor repete; run que chega no boss em combate mata o boss no papel e vai
# embora sem ele.
#
# A alternativa seria continuar batendo até sair de combate, e ela contradiz a
# medição da run das 11:33. Se o log passar a mostrar fases estourando o prazo
# aqui, é ela que está esperando na fila.
#
# `maintain` continua rodando na espera, então a poção de batalha ainda sai abaixo
# de `battle_hp_pct`, e a morte do personagem continua sendo detectada e devolvendo
# derrota.
EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS = True

# ===========================================================================
# A ALTERNATIVA QUE ESTAVA NA FILA ENTROU -- 26/08/2026
# ===========================================================================
#
# O bloco acima terminava assim: *"A alternativa seria continuar batendo até
# sair de combate, e ela contradiz a medição da run das 11:33. Se o log passar a
# mostrar fases estourando o prazo aqui, é ela que está esperando na fila."*
#
# O log passou. Pedido do usuário, com a run observada: *"no waypoint dos Gun
# Witch em BC, tem que continuar atacando até sair de batalha, só deve continuar
# se saiu de batalha; a única trava é se der TAB no Cemetery Guard, que já
# existe. Eu vi em uma das runs acontecer de sobrar 1 Gun Witch e não estar mais
# atacando -- então rotaciona skill até sair de batalha ou até identificar o
# Cemetery Guard como target."*
#
# ---------------------------------------------------------------------------
# O QUE FAZIA SOBRAR UM GUN WITCH DE PÉ
# ---------------------------------------------------------------------------
#
# O portão de nome dava `acabaram` para QUALQUER nome que não fosse `Gun Witch`
# -- e a partir daí `acabaram_os_alvos` segurava o golpe E o TAB até o fim da
# fase. Bastava UMA leitura pegar outra entidade na mira (o cadáver do anterior
# some da seleção, o TAB passa por um Cemetery Guard de passagem, a entidade
# demora um ciclo a aparecer no array) para o bot parar de bater com um guarda
# vivo em cima dele. Daí só havia dois desfechos, ambos ruins: o Gun Witch
# restante mata o personagem, ou a fase estoura `LIMITE_DA_FASE_DOS_GUARDAS` e
# devolve derrota.
#
# ---------------------------------------------------------------------------
# O QUE MUDA
# ---------------------------------------------------------------------------
#
#     antes:  nome != 'Gun Witch'        -> para o golpe e o TAB
#     agora:  nome == 'Cemetery Guard'   -> para o golpe (e larga a mira no ESC)
#             qualquer outro nome        -> CONTINUA batendo; quem encerra a
#                                           fase é a flag de combate, e só ela
#
# A TRAVA NÃO SUMIU, ELA FICOU ESPECÍFICA. O mob que não pode ser puxado tem
# nome, e agora o nome é lido: a razão original ("bater no que sobrou puxaria
# mob que não precisava vir -- foi assim que a run das 11:33 saiu da rota")
# continua atendida contra o Cemetery Guard, que é justamente quem foi medido
# no covil ao lado dos guardas. O que ela deixou de fazer é parar a luta por um
# nome qualquer.
#
# O CUSTO, DITO INTEIRO: se algo que NÃO é Cemetery Guard entrar na mira e o
# personagem continuar em combate, o bot bate nele. É a troca que o usuário
# pediu, e ela é o oposto da anterior -- lá o bot ficava parado apanhando, aqui
# ele pode puxar um vizinho. Sair de combate continua sendo o único jeito de a
# fase seguir para o boss, então o defeito de chegar no boss em batalha
# (`EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS`, acima) continua fechado.
#
# Interruptor, não apagar: `False` devolve o comportamento antigo inteiro.
SO_O_ALVO_PROIBIDO_PARA_O_GOLPE = True

# O TETO DE TAB DEIXA DE BARRAR A TROCA ENQUANTO A FLAG ESTIVER ALTA.
#
# A segunda porta do mesmo defeito: `TABS_NOS_GUARDAS` é 3 (quatro mobs, o
# primeiro vira alvo sozinho), e uma passada de AoE que derruba dois de uma vez
# faz o TAB cair em cadáver e gastar orçamento à toa. Esgotado o teto, o alvo
# morto FICA na mira por 7 a 13 s e a rotação sai contra um cadáver -- de fora
# parece exatamente "sobrou um Gun Witch e o bot não está mais atacando".
#
# Com este interruptor o teto vira o que ele sempre disse ser no comentário do
# `TABS_NOS_GUARDAS` -- um TETO do caminho normal, não um limite da luta: com a
# flag de combate ALTA e o alvo MORTO, o TAB continua saindo até achar quem
# ainda está de pé. Não é rajada: cada TAB paga `CARENCIA_APOS_O_TAB` (2,4 s) e
# `LIMITE_DA_FASE_DOS_GUARDAS` (40 s) continua sendo o teto de tudo. E cada TAB
# passa pelo `pos_tab_callback`, que é onde o Cemetery Guard é conferido -- ou
# seja, mais TAB não afrouxa a trava, ele a exercita mais vezes.
TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS = True

# Prazo total de cada fase. Contrapeso da ressalva (c): flag presa em ligado.
#
# Estourar significa "a flag não desligou", não "terminei". Os guardas caem em 6 a
# 8 s cada, então 120 s é folga de quatro vezes. O boss usa o prazo configurado
# pelo usuário (`bc.max_fight_seconds`), que é o número que ele já ajusta.
LIMITE_DA_FASE_DOS_GUARDAS = 40.0

# A flag ILEGÍVEL (`None`) não conta como "fora de combate".
#
# `in_battle` devolve três estados de propósito, e confundir `None` com `False`
# faria uma falha de leitura virar "acabou a luta" -- exatamente o erro que custa
# a run. Enquanto a leitura não voltar, o bot CONTINUA atacando; se não voltar por
# este tempo, desiste com falha registrada em vez de com vitória.
LIMITE_SEM_LER_A_FLAG = 5.0


# ===========================================================================
#  >>>  INTERRUPTOR DO EXPERIMENTO -- TROCA DE ALVO POR TAB NOS GUARDAS  <<<
# ===========================================================================
#
#   True  = fase dos guardas COM TAB, olhando a barra de vida do alvo na tela
#   False = fase dos guardas como sempre foi (sem TAB, só pela flag de combate)
#
# O caminho antigo está INTACTO em `_fase_dos_guardas_sem_tab` -- ele não foi
# alterado nem uma linha. Voltar para ele é trocar o True abaixo por False, e
# mais nada.
#
# O QUE O EXPERIMENTO TENTA GANHAR: a fase leva 33 a 43 s hoje (6 runs medidas
# no log de dev). Se o bot perceber que o Gun Witch morreu e trocar de alvo na
# hora, em vez de bater até o jogo trocar sozinho, a fase encurta.
USAR_TAB_NOS_GUARDAS = True
# ===========================================================================

# ===========================================================================
# QUEM PODE SER ATACADO EM CADA PONTO DE LUTA
# ===========================================================================
#
# Bater no mob errado não é só golpe perdido: PUXA MOB QUE NÃO PRECISAVA vir, e
# no covil isso vira trem de mobs em cima do personagem.
#
# MEDIDO com o `10-DESCOBRIR-ALVO` no covil, com o personagem ao lado deles:
#
#     Gun Witch ........... 4 structs, nome INLINE em +0xBC, todas legíveis
#     Cemetery Guard ...... 5 structs, nome inline     <- NÃO é para atacar
#     Skull Herald ........ nome inline                <- o NPC da saída
#     Blaze Skull Marshal . nome por PONTEIRO em +0xBC <- o boss
#
# O covil tem, portanto, pelo menos três coisas com nome além do que interessa.


# A FALHA CONTINUA ABERTA, mas agora com espera: ver `CARENCIA_SEM_LER_O_NOME`.
#
# A direção do erro é escolhida. Recusar para sempre por não conseguir ler
# significaria perder a fase sempre que o ponteiro de nome falhasse -- e o nome
# vem por ponteiro em algumas entidades, a forma mais frágil das duas. Mas
# atacar NA HORA também estava errado: quase sempre a luta acaba dentro desses
# três segundos, e aí não há mais ninguém para atacar.

# Quantos TAB gastar tentando SAIR de um alvo errado, por luta.
#
# Diferente do TAB de troca-ao-morrer: ali o alvo morreu, aqui ele está vivo e é
# o errado. Seis dá a volta na roda de alvos próximos; esgotado o orçamento o bot
# volta a bater no que estiver na mira, porque ficar sem atacar na frente do boss
# perde a run -- e esse é o pior dos dois erros.
# Quanto o bot SEGURA o golpe quando não consegue ler o nome do alvo.
#
# O golpe não é recusado para sempre por falha de leitura -- isso perderia a fase
# sempre que o ponteiro de nome falhasse. Mas também não sai na hora: durante
# estes segundos o bot espera a leitura voltar, e se a luta ACABAR nesse meio
# tempo não há mais ninguém para atacar e a fase termina sozinha. Só continuando
# em combate depois deles é que ele bate sem saber em quem.
CARENCIA_SEM_LER_O_NOME = 3.0

# Quantos TAB no máximo. São 4 mobs e o primeiro vira alvo sozinho quando ataca,
# então sobram 3 trocas. É TETO, não meta: classes que batem em vários mobs de
# uma vez (Tamer, por exemplo) matam mais de um por vez e não precisam de todos.
# Sair de combate antes de gastar os três é o caso normal delas, e a fase termina
# igual -- quem decide o fim continua sendo a flag.
TABS_NOS_GUARDAS = 3

# Limiar para detecção do Cemetery Guard (guarda do cemitério) na tela.
# Se este mob aparecer após o 2º TAB nos guardas, a fase deve encerrar imediatamente:
# não atacar mais, não dar mais TAB. Medido nos prints do covil: o Cemetery Guard
# tem sprite distinto dos Gun Witch e aparece quando os 4 Gun Witch já morreram.
LIMIAR_CEMETERY_GUARD = 0.85

# ===========================================================================
# DESTRAVAMENTO: MATAR MOB A MOB PARA SAIR DE BATALHA
# ===========================================================================
#
# MEDIDO EM 31/08/2026, conta `creubo`, run `db7ebdace7`: o bot ficou **24
# minutos e 25 segundos** parado no waypoint dos Gun Witch (110,-406) apertando
# a tecla da montaria sem parar. A fase dos guardas tinha encerrado LIMPA, e
# mesmo assim o portao da montaria nunca liberou:
#
#     23:27:58  Cemetery Guard na mira (TAB 4) -> ESC, paro de bater, aguardo
#     23:28:07  Fora de combate confirmado (2,6s)   <- a saida foi um PISCO
#     23:28:07  GUARDAS -> ATE_O_BOSS -> "Nao estou montado; montando"
#               ... 453 linhas de "Nao conseguiu montar em 6s" ...
#     23:52:32  Montaria confirmada depois de 1465s insistindo
#     23:52:32  ... posicao (426, 53) = Bewitcher Cave, FORA do covil
#
# Ele so destravou porque a INSTANCIA EXPIROU e cuspiu o personagem para fora do
# covil. Nao foi recuperacao, foi sorte -- e a run ja estava perdida.
#
# O QUE SEGURAVA: o Cemetery Guard que o ESC largou voltou a engajar logo depois
# da confirmacao. Em batalha o jogo RECUSA a montaria, e o portao -- que insiste
# sem teto por desenho, ver `navigation.garantir_montaria_para_andar` -- insistia
# contra uma condicao que so um GOLPE resolve. Esperar mais nao ia resolver
# nunca: a espera E o defeito.
#
# A SAIDA, combinada com o usuario em 01/09/2026: *"vai matando de 1 em 1 e
# olhando se saiu de batalha ... no maximo atrasar 1 minuto ... so deve dar TAB
# depois de 3 segundos que nao saiu de batalha, mas nesses 3 segundos voce vai
# verificando se nao sai de batalha antes"*.
#
# ISTO NAO E UMA FASE DA RUN. E um RESGATE, chamado de fora pelo portao da
# montaria (`Navigator.destravar_o_combate`), e por isso nao mora em
# `atacar_ate_sair_de_combate`: la "saiu de combate" significa VITORIA e o
# desfecho alimenta a estatistica da run; aqui significa apenas "da para andar
# de novo". O que ele reaproveita sao as PECAS -- `_ler_flag_de_combate`,
# `_alvo_morreu`, `_proxima_skill`, `maintain`, `_e_o_alvo_proibido` --, nunca
# o desfecho.

# Teto de UMA rodada de destravamento. Palavra do usuario: *"no maximo atrasar 1
# minuto"*.
#
# NAO e teto para insistir na montaria -- esse continua nao existindo, e
# `NUNCA A PE DENTRO DA CAVE` continua inteiro. Estourado este teto o portao
# volta a insistir e chama o destravamento outra vez; o que o numero limita e
# quanto tempo o bot passa BATENDO antes de reavaliar.
TETO_DO_DESTRAVAMENTO = 60.0

# Quanto esperar PARADO, sem bater, depois de cada morte, antes de gastar o TAB
# seguinte. Numero do usuario.
#
# Nao e conforto: aqui nao existe nome esperado, entao o TAB imediato depois da
# morte faz o bot atacar o mob seguinte e PUXAR quem nao estava em combate --
# o mesmo travamento com outro nome, agora em bola de neve. Estes tres segundos
# parado sao o que deixa a flag baixar sozinha quando aquele era o ultimo.
#
# A espera SAI ANTES no instante em que a saida se confirma, e ela se ESTENDE
# quando a flag baixa perto do fim: baixou, o que vale e completar
# `CONFIRMACAO_DE_SAIDA_DE_COMBATE` -- cortar a confirmacao pela metade gastaria
# um TAB justamente na hora em que a luta estava acabando.
ESPERA_APOS_A_MORTE_ANTES_DO_TAB = 3.0

# Teto para UM mob dentro do destravamento.
#
# Medido no mesmo log: os quatro Gun Witch cairam em 3, 3, 4 e 4 segundos. Vinte
# segundos dao folga de 5x para um mob mais duro (o Cemetery Guard tem a mesma
# escala de HP do covil) sem deixar o destravamento inteiro preso num alvo que
# nao morre -- alvo imortal na mira e caso de TROCAR de alvo, nao de insistir.
LIMITE_POR_MOB_NO_DESTRAVAMENTO = 20.0

# O DESTRAVAMENTO BATE NO CEMETERY GUARD? Decisao do usuario, 01/09/2026.
#
# FORA do destravamento a trava continua INTEIRA: Cemetery Guard na mira => ESC,
# para o golpe, espera a saida (`_travar_no_alvo_proibido`). Aquela regra existe
# para EVITAR puxa-lo, e ela nao muda.
#
# Aqui ela JA FALHOU. Se o destravamento esta rodando e porque o ESC e a espera
# nao bastaram e o personagem esta preso em batalha ha mais de um minuto -- que
# e exatamente o log dos 24 minutos. Palavras do usuario: *"mantem o ESC, mas
# caso passe os segundos maximos de espera ... voce deve ir matando de 1 em 1
# ate sair de batalha, justamente para nao ficar esses 24 minutos"*.
#
# `False` devolve o comportamento anterior: o destravamento pula o Cemetery
# Guard, gasta um TAB e tenta o alvo seguinte.
DESTRAVAMENTO_BATE_NO_ALVO_PROIBIDO = True
#
# A FAIXA cobre a struct do personagem. Os offsets conhecidos vão até
# `OFF_PET_ACTIVE = 0x10A8`, então 0x1800 dá folga de meia struct para cima --
# sem virar varredura de processo, que devolveria endereço em vez de offset.
# Prefixo do rótulo dos candidatos que a varredura promove. Existe como constante
# porque DOIS lados dependem dele: quem promove escreve, quem amostra lê de volta
# para recuperar o offset. Duas cópias do literal divergiriam em silêncio, e o
# sintoma seria o promovido nunca ser medido.
PREFIXO_DA_VARREDURA = "varredura:"
# tem `target_name`, e o `TargetHybrid` responde identidade (`id`) e vida, não
# nome.
#
# O QUE ELE VIROU, MEDIDO nas 14 lutas de 24-25/08/2026:
#
#     14 de 14 lutas:  "NOME guardas veredito=ilegivel lido=nada"
#     14 de 14 lutas:  WARNING "vou bater SEM LER o nome do alvo"
#      0 decisões tomadas
#
# Ou seja: um aviso por luta e nenhuma decisão. Quem detecta alvo errado agora é
# o `cemetery_guard.png` (`_verificar_cemetery_guard`), que olha a TELA e
# identifica exatamente o mob que importa -- decisão do usuário em 25/08.
#
# ===========================================================================
# RELIGADO EM 25/08/2026 -- O NOME VOLTOU
# ===========================================================================
#
# A previsão acima se cumpriu: a investigação do `0x0115CB80` achou o que o
# valor significa. Ele é o **ID da entidade selecionada**, e a entidade carrega
# esse id em `+0x8` -- chave estrangeira para o array que o bot já varria. Ver
# `core/memory.ADDR_TARGET_ID` para a medição, e o item 39 de
# `docs/decisoes/alvo-o-que-esta-medido.md` para de onde a chave saiu.
#
# Com a entidade na mão, o nome vem junto -- e junto vêm nível, HP exato e
# posição. Confirmado no `18-CASAR-ALVO` numa luta inteira:
#
#     'Gun Witch' nv50 hp=8/100 ... 'Blaze Skull Marshal' nv50 ... nv51
#
# NÃO É MAIS LEITURA DE TELA. O veredito do nome agora custa ~3 leituras de 4
# bytes, contra uma captura de janela inteira -- e não tem falso positivo.
USAR_PORTAO_DE_NOME = True

# ===========================================================================
# SÓ A MEMÓRIA DECLARA MORTE. A TELA SÓ SABE DIZER "AINDA VIVO".
# ===========================================================================
#
# Assimetria de propósito, e ela vem de uma medição antiga: o `EnemyDead.png`
# tem **falso positivo medido com o mob VIVO** -- escore 0,955-0,971 contra
# limiar 0,85, com o mob em 35 de vida, em 20/08/2026. Ele nunca foi confiável
# sozinho; o que o segurava era só ser consultado abaixo de 10% de barra.
#
# Com a memória na frente, esse resguardo sumiu do caminho normal -- e o que
# sobrou foi um caminho de RESERVA capaz de declarar morte com um template que
# erra. É a explicação para *"vi um TAB aqui sem o mob ter morrido"*: basta a
# entidade faltar no array por um ciclo (medido: 1 em ~45, no instante em que um
# alvo novo é selecionado) com a barra num vão de redesenho, e o marcador
# confirma uma morte que não houve.
#
# A regra passa a ser:
#
#     memória diz `hp == 0`  -> MORREU, dá TAB
#     memória diz `hp > 0`   -> vivo
#     memória não respondeu  -> a tela decide entre "vivo" e "NÃO SEI"
#                               -- e "não sei" NUNCA gasta TAB
#
# NÃO SE PERDE NADA COM ISSO. A reserva existe para um vão de um ciclo: no
# seguinte a memória responde e o TAB sai 0,15 s depois. E se a memória
# estivesse permanentemente muda, o bot já não funcionaria de qualquer jeito --
# posição, HP e flag de combate saem todos dela.
#
# Interruptor, não apagado: desligar devolve à tela o direito de declarar morte,
# e é o que o teste usa para provar que era ela a fonte do TAB fantasma.
SO_A_MEMORIA_DECLARA_MORTE = True
# Nome do template do marcador. Veio do usuário em 19/08/2026.
TEMPLATE_INIMIGO_MORTO = "EnemyDead.png"

# ===========================================================================
# A SEGUNDA FASE DO BOSS TAMBÉM É VISTA NA TELA
# ===========================================================================
#
# A fase 2 tem DUAS barras de vida: uma AMARELA primeiro e a vermelha de sempre
# depois. O amarelo só existe na fase 2, então ver amarelo É a virada de fase --
# pedido do usuário em 19/08/2026: *"caso encontre isso em algum momento da luta
# contra o boss é pq entrou na segunda fase e é o momento de usar a Break Soul."*
#
# É O SEGUNDO SINAL, NÃO O SUBSTITUTO. A troca de struct
# (`_registrar_troca_de_fase`) continua valendo e continua sendo a primeira a
# falar. Os dois levantam a MESMA bandeira por `_marcar_fase`, e ela é LATCH:
# nenhum dos dois a baixa, e o que chegar primeiro resolve.
#
# Por que vale ter dois: o sinal por struct depende de a memória responder E de
# o nome do boss ser legível no instante da troca; este depende só da tela. Eles
# falham por motivos diferentes, que é a única coisa que faz redundância valer
# algo.
USAR_IMAGEM_DA_FASE_2 = True

# O recorte é o PEDAÇO DO MEIO do par vida+mana do quadro do alvo, com a vida
# amarela. Casado EM COR -- ver `vision.LIMIAR_DA_FASE_2_DO_BOSS` para a medição
# que diz por que em cinza isto casaria com a fase 1.
TEMPLATE_FASE_2_DO_BOSS = "boss_2_fase.png"

# De quanto em quanto tempo olhar a barra do alvo durante a luta.
#
# Cada leitura é uma captura (~10 ms) mais a varredura da faixa. Esta cadência é
# o ATRASO MÁXIMO entre o mob morrer e o TAB sair; com 3 trocas por fase, o
# desperdício total é ~3x ela.
CADENCIA_DA_LEITURA_DO_ALVO = 0.15

# Depois de apertar TAB, quanto tempo ignorar a leitura.
#
# O quadro leva um instante para redesenhar com o alvo novo, e ler nesse vão
# mostraria a barra do alvo ANTIGO (vazia) -- o bot concluiria "morreu de novo"
# e queimaria os três TAB em menos de um segundo. Um segundo e meio é o piso
# dado pelo usuário: nenhuma classe mata um Gun Witch em menos que isso, então
# nenhuma morte real é perdida por esta carência.
CARENCIA_APOS_O_TAB = 2.4
SEGUNDOS_ANTES_DO_TAB_NO_BOSS = 4.0

# Depois de forçar o TAB no boss, quanto tempo a flag tem para subir.
#
# Existe porque forçar troca a natureza da espera: sem o TAB o bot esperava SEM
# PRAZO, e essa espera era segura justamente por não fazer nada. Atacando, o
# risco muda -- se o TAB não pegou o boss, o bot gira a rotação contra o nada
# até o prazo da luta (minutos). Este teto devolve o controle para o SITUAR em
# vez de gastar a run batendo no ar.
LIMITE_PARA_A_LUTA_COMECAR = 10.0


@dataclass(frozen=True)
class FimDeCombate:
    """Como uma fase de combate terminou.

    `saiu_de_combate` é a única coisa que o chamador precisa consultar para
    decidir o passo seguinte -- e é a pergunta certa: no boss ela é "venceu?".
    O resto existe para o log poder dizer POR QUE terminou, que é a diferença
    entre "a luta acabou" e "a flag travou e eu desisti".
    """

    saiu_de_combate: bool
    motivo: str
    segundos: float
    golpes: int

    def resumo(self) -> str:
        return (f"{self.motivo} | {self.segundos:.0f}s | {self.golpes} golpes")


@dataclass(frozen=True)
class LeituraDoAlvo:
    """O veredito de uma observação do alvo, com o porquê para o log."""

    morreu: bool | None      # True morreu | False vivo | None NÃO SEI
    fonte: str               # memoria | tela | ausencia | nada
    motivo: str

    def resumo(self) -> str:
        rotulo = {True: "MORREU", False: "vivo", None: "nao-sei"}[self.morreu]
        return f"fonte={self.fonte} veredito={rotulo} ({self.motivo})"

    @property
    def chave(self) -> str:
        """A SITUAÇÃO, sem os números — é o que decide se o log repete.

        Deliberadamente NÃO inclui o `motivo`: ele carrega o HP, que muda a
        cada golpe, e usar o texto inteiro como chave fazia toda leitura contar
        como "mudou". Medido na simulação: uma luta de 40 s rendia ~130 linhas,
        num arquivo de texto que guarda 500 no total.

        Com a chave assim, a descida normal de vida rende UMA linha ao entrar em
        `memoria/vivo` e depois só os ecos periódicos -- que continuam trazendo
        o HP do momento, porque quem lê quer ver o número andando.
        """
        return f"{self.fonte}/{self.morreu}"


# ===========================================================================
# FORA DA CAVE, SÓ DESMONTA SE O PET NÃO ESTIVER ATIVO
# ===========================================================================
#
# Regra do usuário, 25/08/2026. Ver `CombatEngine._preparar_para_agir` para o
# porquê e para a fronteira ("fora" = a coordenada PROVA que não está na
# instância; sem leitura, a ação passa).
#
# `False` devolve o comportamento anterior: desmonta em qualquer lugar, para
# qualquer motivo.
DESMONTAR_FORA_DA_CAVE_SO_SEM_PET = True

class CombatEngine:

    # ==================================================================
    # O ROTEIRO DA CAVE -- o que cada ecossistema preenche
    # ==================================================================
    #
    # O motor sabe LUTAR; ele não sabe em que cave está. Estes quatro pontos são
    # tudo o que ele precisa perguntar, e todos têm resposta neutra: um motor sem
    # roteiro luta normalmente, só não tem alvo proibido nem segunda fase.
    #
    # É de propósito que sejam ATRIBUTOS e MÉTODOS VAZIOS, e não parâmetros de
    # construtor: o `CombatEngine` é montado por `__new__` em dezenas de testes
    # desta suíte, e exigir argumento novo cobraria de todos eles um conserto que
    # não é deles.

    # O mob que NÃO se pode puxar neste lugar. `None` = não existe nenhum.
    #
    # Na Bewitcher Cave é o Cemetery Guard: puxá-lo tira a run da rota. A HH não
    # tem equivalente conhecido -- e "não tem" é resposta, não lacuna.
    NOME_DO_ALVO_PROIBIDO: str | None = None

    def _registrar_troca_de_fase(self, esperado: str) -> None:
        """A luta trocou de fase. Padrão: esta cave não tem fases.

        Sobrescrito pela Bewitcher Cave, onde o boss não zera -- ele some por
        volta de 7%, a struct é liberada e nasce outro de nível 51.
        """

    def _conferir_fase_2_na_tela(self) -> None:
        """Um SEGUNDO sinal da troca de fase, pela tela. Padrão: não há."""

    def _esta_fora_da_cave(self) -> bool:
        """A coordenada PROVA que o personagem está fora da instância?

        Padrão `False` = "não sei", e não sei NÃO BLOQUEIA. É a direção segura:
        não curar dentro da cave mata o personagem, e um desmonte a mais fora
        dela custa alguns segundos.

        Cada cave responde com a caixa dela -- ver `mapa_bc.posicao_esta_fora_da_cave`.
        """
        return False

    def __init__(self, ctx: BotContext, navigator: Navigator | None = None) -> None:
        self.ctx = ctx
        self.nav = navigator or Navigator(ctx)
        self._skill_index = 0
        # Bandeira POR LUTA: `fight_boss` a levanta quando `fases_vistas` chega a
        # 2 e a baixa no `finally`. Ver `USAR_BREAK_SOUL_SO_NA_FASE_2`.
        self._na_segunda_fase_do_boss = False
        # INSTRUMENTAÇÃO do marcador de morte. Não decide nada -- ver o bloco
        # do escore em `_alvo_morreu`. Existe porque 69 leituras seguidas sem
        # achar o marcador não diziam se faltou 0,01 no limiar ou se o sprite
        # está fora da faixa.
        self._melhor_escore_do_marcador = None
        self._ultimo_escore_do_marcador = None
        self._escore_em_cor_do_marcador = None
        self._vermelho_onde_o_marcador_casou = None
        self._avisou_falha_da_prova = False
        # A CREDENCIAL DA MEMÓRIA é resolvida uma vez POR LUTA. `None` = ainda
        # não perguntei ao placar. Ver `_memoria_pode_votar`.
        self._credencial_da_memoria: bool | None = None
        self._proxima_varredura = 0.0
        # Levantada quando a peneira promove. A partir daí a prova normal assume,
        # e varrer de novo seria trabalho para reconfirmar o já respondido.
        self._varredura_concluida = False
        self._hp_da_entidade_concluido = False
        self._selecao_concluida = False
        # A foto anterior, para exigir ESTABILIDADE entre TABs. Ver
        # `_desqualificar_quem_tremula` -- sem isto o critério da identidade fica
        # pela metade e um campo que tremula gabaritaria sendo lixo.
        self._foto_anterior: dict[int, int] = {}
        # Bebeu poção no top-up antes do boss. Se o personagem MORRER depois
        # disso, a conta é parada -- ver `_registrar_morte`.
        self._precisou_de_pocao_antes_do_boss = False
        # Gerenciador de alimentação do pet (lógica compartilhada com o APP).
        #
        # A GRADE VEM DO DISCO. `proxima_comida_em` sobrevive a reinício; sem
        # isso a cadência recomeça a cada restart e o pet perde refeições do dia.
        # A GRAVAÇÃO TAMBÉM MORA NO `PetFeeder` AGORA (27/08/2026): ele grava a
        # cada mudança da grade, inclusive quando ela apenas NASCE -- e é essa
        # segunda gravação que o APP não tinha. Ver `core/pet.py`.
        self._pet_feeder = PetFeeder(
            vence_em=(ctx.settings.pet.proxima_comida_em or None),
            gravar=self._gravar_grade_da_comida)
        # O VIGIA DO ALVO: id pela memória, vida pela tela.
        #
        # SEM `pid` E `hwnd` NO CONSTRUTOR, e isso é conserto de defeito: eles
        # eram fixados aqui, e depois de um relogin a janela e o processo mudam
        # -- o objeto continuava lendo processo morto e capturando janela que já
        # não existe, em silêncio. Agora cada leitura recebe os atuais.
        self._target_hybrid = TargetHybrid(logger=ctx.log)
        # Último alvo cuja morte já foi contada. O cadáver fica selecionável por
        # 7 a 13 s (medido em 20/08/2026); sem esta trava ele gastaria um TAB por
        # leitura enquanto estivesse ali.
        # A MORTE DO ALVO é peca COMPARTILHADA (`core/target_hybrid.py`), e não
        # uma regra deste arquivo: o APP faz a MESMA pergunta com a MESMA
        # struct. Ver `MorteDoAlvo` para o porquê de ela morar no `core/` e para
        # o que NÃO subiu (a reserva pela tela continua aqui, porque o APP não
        # captura tela). O nome antigo virou propriedade, abaixo, para os testes
        # e o resto do arquivo continuarem enxergando o mesmo id.
        self._morte_do_alvo = MorteDoAlvo()
        # Aviso de "sem tecla de ataque" sai UMA vez por conta. Ele mora no laço
        # da luta, que roda duas vezes por segundo -- repetir encheria o log.
        self._avisou_sem_ataque = False

    # ==================================================================
    # Pré-requisitos de qualquer ação
    # ==================================================================

    def _memoria_confiavel(self) -> bool:
        """Sem leitura de memória não há como confirmar nada.

        Insistir sem confirmação foi o que produziu o comportamento errático
        observado: sete tentativas de invocar pet, montar e desmontar em
        sequência, abrir NPC sem motivo. Melhor recusar a ação e avisar.
        """
        return self.ctx.memory.critical_ok()

    def _preparar_para_agir(self, motivo: str) -> bool:
        """Deixa o personagem em condição de usar item ou skill: A PÉ.

        Montado, o jogo IGNORA a tecla e não devolve erro nenhum -- o bot
        acreditava ter usado a poção, ter invocado o pet e ter aplicado o buff.
        Era a explicação para "o bot aperta e nada acontece".

        Devolve False quando não conseguiu desmontar; quem chama decide se
        insiste ou registra.

        =================================================================
        FORA DA CAVE, SÓ DESMONTA SE O PET NÃO ESTIVER ATIVO
        =================================================================

        Regra do usuário, 25/08/2026: *"fora da cave BC ele só vai sair da mount
        caso o pet não esteja ativo; de resto, alimentar o PET, usar qualquer
        coisa que dependa tirar a montaria vai ser feito naquele momento que
        entra na cave"*.

        O sintoma que ela corrige: em Stone City, indo ao vendedor e à Fay, o bot
        descia da montaria no meio do caminho para curar, aplicar buff ou dar
        comida -- e cada desmonte é remontar depois, com o intervalo da tecla
        inteiro no meio.

        Invocar o pet é a ÚNICA exceção, e é a exceção certa: pet inativo fora da
        cave significa entrar sem pet, e lá dentro invocar custa parar no trem de
        mobs.

        "NÃO SEI ONDE ESTOU" NÃO BLOQUEIA. `posicao_esta_fora_da_cave` só afirma
        `True` quando a coordenada PROVA que está fora; sem leitura ela responde
        `False` e a ação passa. É a direção segura: não curar dentro da cave mata
        o personagem, e um desmonte a mais fora dela custa alguns segundos.
        """
        ctx = self.ctx
        if not ctx.memory.is_mounted():
            return True
        if (DESMONTAR_FORA_DA_CAVE_SO_SEM_PET
                and self._esta_fora_da_cave()
                and ctx.memory.pet_active()):
            ctx.log.info(
                "NÃO desmonto para %s: estou fora da cave e o pet está ativo. "
                "Isso fica para o preparo dentro da cave.", motivo)
            return False
        ctx.log.debug("Desmontando para %s (montado o jogo ignora a tecla)", motivo)
        if self.nav.ensure_dismounted():
            return True
        ctx.log.warning("Não consegui desmontar para %s", motivo)
        diario.registrar_evento(
            ctx.account_login, "acao-sem-efeito",
            f"não desmontei para {motivo}; a tecla seria ignorada",
            ctx.memory.position(), ctx.memory.location(),
        )
        return False

    def auto_selecionar(self) -> None:
        """Seleciona o próprio personagem (F1), para skill em si mesmo."""
        self.ctx.press(TECLA_AUTO_SELECAO)
        self.ctx.tick(0.125)

    # ==================================================================
    # Alvo
    # ==================================================================

    def _nome_da_entidade(self, obj: int) -> str | None:
        """Equivalente a ctx.memory.nome_da_entidade() usando a tabela de entidades."""
        # Validação rápida: None ou ponteiro inválido
        if obj is None or not isinstance(obj, int) or obj < 0x10000 or obj > 0x7FFFFFFF:
            return None

        # Tenta tabela de entidades (produção)
        try:
            entidades = self.ctx.memory.entidades_vivas()
            for ent in entidades:
                if ent["obj"] == obj:
                    return ent.get("nome")
        except Exception:
            pass
        # Fallback para mocks de teste / código antigo: usa método direto da memória
        try:
            return self.ctx.memory.nome_da_entidade(obj)
        except Exception:
            pass
        return None

    # ======================================================================
    # NÃO EXISTE MAIS CONFERÊNCIA DO ALVO POR NOME
    # ======================================================================
    #
    # Havia aqui um `_conferir_o_guarda_na_mira`, que dava TAB para longe quando o
    # nome do alvo não era `Gun Witch`. A medição no covil (`logs/combate.log`)
    # mostrou que aquilo estava ERRADO de duas formas.
    #
    # 1. O NOME DO MOB NÃO É CONFIÁVEL. Dos três Gun Witch mortos naquela sessão,
    #    dois leram nome ilegível:
    #
    #        19:27:09  hp=100/100 'Gun Witch'   @0x337ff688
    #        19:27:23  hp= 67/100 'm93@\x1a'    @0x337fe580
    #        19:28:06  hp=100/100 'p?@\x1a'     @0x337fd478
    #
    #    E não é lixo aleatório: `'p?@\x1a'` são os bytes de `0x1A403F70`, um
    #    endereço de heap. O campo `+0xBC` guarda TEXTO em algumas entidades e
    #    PONTEIRO em outras. O mesmo endereço `@0x337fe580` leu 'Altar Guard',
    #    depois 'm93@\x1a', depois 'Fireball' -- slot reaproveitado.
    #
    #    Ou seja: a conferência daria TAB para longe de Gun Witches de verdade.
    #
    # 2. O MOTIVO DELA NÃO EXISTIA. Ela foi escrita para evitar bater no PET, mas
    #    neste servidor o TAB não cicla por pet, jogador nem NPC -- o PvP é
    #    desligado. O que o TAB pega É mob.
    #
    # O que ficou no lugar: TAB é o seletor, e a MORTE é reconhecida pelo HP do
    # alvo chegando a zero, que a mesma medição mostrou ser estável (o corpo fica
    # no chão com HP 0 por vários segundos, e o HP nunca voltou a subir).

    # ==================================================================
    # Sustentação durante a luta
    # ==================================================================

    def maintain(self, state, em_luta: bool = False) -> None:
        """Poções e cura, escolhendo o item certo para a situação.

        O jogo tem DOIS conjuntos de poções: as normais e as "de batalha", que
        são itens separados com recarga própria. Usar a de batalha fora do
        combate desperdiça um item caro, e usar a normal em combate pode não
        funcionar. Por isso o limiar e a tecla mudam conforme o estado.

        `em_luta` vem de QUEM CHAMA, e não da flag de combate da memória. O
        chamador sabe com certeza: `fight_boss` e `lutar_contra_guardas` são luta,
        `heal_to_full` não é. Ler a flag era adivinhar uma coisa já conhecida --
        com o agravante de que ela fica ligada quase toda a travessia da cave e já
        foi vista presa, o que fazia o bot gastar poção de batalha (item caro)
        fora de luta.

        ATENÇÃO AO HISTÓRICO: esta função lia `settings.combat` e
        `settings.profile`, que deixaram de existir quando a configuração foi
        separada em três níveis e a seleção de classe foi removida. O resultado
        era um AttributeError na PRIMEIRA volta da luta contra o boss -- ou seja,
        a luta nunca acontecia, e a rotina só registrava "exceção em KILL_BOSS".
        Os limiares vivem em `settings.potions`; não há perfil de classe.

        Não desmonta aqui: em combate o personagem já está a pé, e tentar
        desmontar no meio da luta gastaria tempo sem motivo.
        """
        ctx = self.ctx
        st = ctx.settings
        k = st.keys
        p = st.potions

        # Sem perfil de classe: quem tem tecla de cura tem cura. A configuração é
        # a declaração.
        #
        # POÇÃO DE MANA SAIU DO BOT. Não é que a opção ficou escondida -- as
        # teclas e os limiares foram removidos da configuração inteira. O que
        # continua olhando mana é a rotação de ataque, que tira o AoE abaixo do
        # limite configurado; isso é economia de recurso, não consumo de item.
        if MODO_DE_CURA != "skill_em_laco":
            self._manter_vida_caminho_antigo(state, em_luta)
            return

        tem_cura = bool(k.heal_skill)

        # ================================================================
        # EM BATALHA: SÓ A POÇÃO DE BATALHA, E SÓ BEM BAIXO
        # ================================================================
        #
        # A SKILL DE CURA NÃO ENTRA AQUI, e o motivo é o F1: skill em si mesmo
        # precisa de alvo, o alvo é o próprio personagem, e **F1 no meio da luta
        # LARGA o alvo**. O `CLAUDE.md` diz que o engajamento do boss depende de
        # quem está selecionado -- "TAB sozinho não engaja, quem engaja é o
        # golpe" --, então um F1 aqui deixaria o bot batendo no vazio.
        #
        # ISTO ERA BOMBA ARMADA, NÃO DEFEITO ATIVO. Sem tecla de cura
        # configurada, este trecho só bebia poção, e poção não precisa de alvo.
        # O F1 passaria a sair no meio da luta do boss no dia em que alguém
        # configurasse a tecla de cura da Fairy.
        #
        # A POÇÃO DE BATALHA FICA porque ela não tem esse defeito: é a única
        # coisa consumível em combate e não mexe na seleção. Mas ela é RESERVA,
        # não manutenção -- só abaixo de `battle_hp_pct`, cujo padrão passou de
        # 90% para 15% junto com esta decisão. Durante a luta o bot luta.
        if em_luta:
            if not k.battle_hp_potion:
                return
            if bool(state.max_hp) and state.hp_pct <= p.battle_hp_pct:
                ctx.log.info("Vida %.0f%% em batalha -- poção de batalha",
                             state.hp_pct)
                ctx.press(k.battle_hp_potion)
                ctx.tick(0.15)
            return

        # ================================================================
        # FORA DE BATALHA
        # ================================================================
        #
        # Sem perfil de classe: quem tem tecla de cura tem cura, e a configuração
        # é a declaração -- é por isso que o `prefer_heal_skill` deixou de
        # existir. Ele era um segundo lugar para dizer a mesma coisa, e dois
        # lugares dizendo a mesma coisa acabam discordando.
        #
        # UM aperto, não o laço. O laço (`curar_com_skill`) é chamado
        # explicitamente pelos três pontos onde o bot PARA para se curar; aqui a
        # manutenção é de passagem.
        hp_baixo = bool(state.max_hp) and state.hp_pct <= p.hp_pct
        if not hp_baixo:
            return

        if tem_cura:
            self.auto_selecionar()
            ctx.press(k.heal_skill)
            ctx.tick(0.2)
            return

        if k.hp_potion:
            ctx.press(k.hp_potion)
            ctx.tick(0.15)

    def _manter_vida_caminho_antigo(self, state, em_luta: bool) -> None:
        """O comportamento anterior a 19/08/2026, inteiro.

        Fica aqui para que `MODO_DE_CURA = "pocao"` seja uma reversão de verdade
        e não "ligar código não testado" -- a regra da casa para todo interruptor.

        ATENÇÃO: este caminho USA a skill de cura em batalha, com F1, e é
        exatamente o que a decisão do usuário de 19/08/2026 tirou. Ligá-lo
        reintroduz o F1 no meio da luta do boss.

        `prefer_heal_skill` não existe mais na configuração; aqui ele é lido do
        atributo se sobrar algum, e vale `False` por padrão -- que era o valor de
        fábrica.
        """
        ctx = self.ctx
        k = ctx.settings.keys
        p = ctx.settings.potions
        prefere_skill = bool(getattr(p, "prefer_heal_skill", False))
        tem_cura = bool(k.heal_skill)

        hp_baixo = bool(state.max_hp) and state.hp_pct <= (
            p.battle_hp_pct if em_luta else p.hp_pct
        )

        curou_com_skill = False
        if hp_baixo and tem_cura and prefere_skill:
            self.auto_selecionar()
            ctx.press(k.heal_skill)
            ctx.tick(0.2)
            curou_com_skill = True

        if hp_baixo and not curou_com_skill:
            hp_key = (k.battle_hp_potion or k.hp_potion) if em_luta else k.hp_potion
            if hp_key:
                ctx.press(hp_key)
                ctx.tick(0.15)

        if hp_baixo and not prefere_skill and tem_cura:
            self.auto_selecionar()
            ctx.press(k.heal_skill)
            ctx.tick(0.15)


    # ==================================================================
    # Cura por skill -- o laço
    # ==================================================================

    def _a_cura_subiu(self, antes: float) -> bool:
        """Espera a conjuração e responde se a vida SUBIU. Não espera cega.

        Confere a cada `INTERVALO_DE_CONFERENCIA` e devolve NO INSTANTE em que a
        vida sobe -- uma conjuração que termina em 1,4 s não paga os 0,2 s que
        faltariam para o relógio fechar. E uma conjuração interrompida é
        descoberta em 0,1 s em vez de 2,2 s.

        A conferência é `ctx.snapshot()`, leitura de memória: não fala com o
        jogo, então repeti-la é barato. Quem é caro é o APERTO, e ele acontece
        uma vez por conjuração. Ver o bloco `MODO_DE_CURA` no topo do arquivo.
        """
        ctx = self.ctx
        teto = SEGUNDOS_DE_CONJURACAO_DA_CURA + MARGEM_DA_CONJURACAO
        gasto = 0.0
        while gasto < teto:
            ctx.tick(INTERVALO_DE_CONFERENCIA)
            gasto += INTERVALO_DE_CONFERENCIA
            estado = ctx.snapshot()
            if not estado.max_hp:
                return False
            if estado.hp_pct >= antes + SUBIDA_MINIMA_PARA_CONTAR:
                return True
        return False

    def curar_com_skill(self, alvo_pct: float) -> bool:
        """Repete a skill de cura até a vida chegar em `alvo_pct`.

        `True` = chegou no alvo. `False` = a cura não está saindo (recarga, mana
        ou interrupção), e quem chamou decide se cai para poção.

        ==================================================================
        NUNCA CHAMAR EM BATALHA
        ==================================================================

        O F1 do começo LARGA o alvo, e o engajamento do boss depende de quem está
        selecionado. Esta função mora nos INTERVALOS -- ao entrar na cave, no
        top-up depois dos guardas, e na recuperação fora da instância. Em batalha
        o bot só luta.

        O F1 sai UMA vez, não a cada conjuração: fora de combate a seleção não
        muda sozinha, e repeti-lo seria mensagem à toa a cada 2 s.
        """
        ctx = self.ctx
        k = ctx.settings.keys
        if MODO_DE_CURA != "skill_em_laco" or not k.heal_skill:
            return False

        estado = ctx.snapshot()
        if not estado.max_hp:
            ctx.log.debug("Sem leitura de HP; não há como conduzir a cura")
            return False
        if estado.hp_pct >= alvo_pct:
            return True

        inicial = estado.hp_pct
        self.auto_selecionar()

        # `max_heal_seconds` é rede de segurança, não estratégia -- o que decide
        # de verdade é `TENTATIVAS_SEM_EFEITO`. Ele existe para o caso em que
        # cada conjuração cura um tico e o alvo está longe demais.
        limite = time.time() + ctx.settings.potions.max_heal_seconds
        sem_efeito = 0
        apertos = 0

        while sem_efeito < TENTATIVAS_SEM_EFEITO and time.time() < limite:
            ctx.raise_if_stopped()
            estado = ctx.snapshot()
            if not estado.max_hp:
                return False
            if estado.hp_pct >= alvo_pct:
                ctx.log.info(
                    "Cura por skill: %.0f%% -> %.0f%% (alvo %s%%) em %s aperto(s)",
                    inicial, estado.hp_pct, alvo_pct, apertos,
                )
                return True

            antes = estado.hp_pct
            ctx.press(k.heal_skill)
            apertos += 1
            if self._a_cura_subiu(antes):
                sem_efeito = 0
            else:
                sem_efeito += 1

        final = ctx.snapshot().hp_pct
        motivo = ("a cura não subiu a vida em "
                  f"{TENTATIVAS_SEM_EFEITO} conjurações seguidas -- recarga, "
                  "mana ou interrupção"
                  if sem_efeito >= TENTATIVAS_SEM_EFEITO
                  else f"estourou o teto de {ctx.settings.potions.max_heal_seconds}s")
        ctx.log.info(
            "Cura por skill parou em %.0f%% (era %.0f%%, alvo %s%%) após %s "
            "aperto(s): %s", final or inicial, inicial, alvo_pct, apertos, motivo,
        )
        return False

    def _rotacao_de_ataque(self, state, usar_aoe: bool) -> list[str]:
        """As teclas do bloco "Ataque", na ordem em que aparecem na tela.

        É uma rotação circular: aperta uma, na próxima investida aperta a
        seguinte, e ao chegar no fim volta ao começo. NÃO existe controle de
        recarga aqui, de propósito -- skill em recarga simplesmente não sai, e o
        personagem continua atacando com as outras. Rastrear recarga de cada
        skill de cada classe seria muito trabalho para evitar um custo que é zero.

        O AoE ENTRA NA ROTAÇÃO, não substitui ninguém. Com Ataque 1 e AoE
        configurados -- que é o caso mais comum -- a sequência fica
        `1, AoE, 1, AoE, ...`: intercalado, como pedido.

        ANTES ELE NÃO ERA INTERCALADO. O AoE era um substituto disparado por
        `_skill_index % 4 == 0`, então com um ataque só a sequência real era
        `1, 1, 1, AoE` -- o AoE saía em um quarto das investidas em vez de na
        metade, e com vários ataques configurados ele ainda ROUBAVA a vez de um
        deles, deixando a rotação irregular.

        Duas coisas tiram o AoE da rotação:

          * `usar_aoe=False`, usado nos GUARDAS. Eles vêm um de cada vez, então
            área não acerta mais ninguém -- é mana caríssima gasta sem ganho, e
            mana é exatamente o que falta na segunda fase do boss, logo depois.
          * a mana ter caído abaixo do limite configurado
            (`aoe_until_mana_pct`). Aqui a rotação encurta e volta a ser só os
            ataques comuns, sem parar de atacar em nenhum momento.

        A BREAK SOUL SÓ ENTRA NA SEGUNDA FASE DO BOSS, e é a terceira coisa
        que mexe nesta rotação. Ela já teve dois estados errados: primeiro nunca
        era apertada (a tecla existia na tela e nenhuma linha do bot a usava),
        depois passou a sair SEMPRE -- contra guardas, lixo e a fase 1 do boss,
        chegando em recarga na luta que decide a run. Hoje ela entra pela mesma
        porta do AoE, acrescentando à rotação, mas só com a bandeira
        `_na_segunda_fase_do_boss` levantada. Ver `USAR_BREAK_SOUL_SO_NA_FASE_2`.
        """
        st = self.ctx.settings
        k = st.keys

        rotacao = [tecla for tecla in k.attack_skills if tecla]

        if (usar_aoe and st.use_aoe and k.aoe_skill
                and state.mp_pct >= st.bc.aoe_until_mana_pct):
            rotacao.append(k.aoe_skill)

        # A BREAK SOUL SÓ NA FASE 2 DO BOSS. Ver `USAR_BREAK_SOUL_SO_NA_FASE_2`
        # no topo do arquivo para o porquê inteiro. Ela entra ACRESCENTANDO à
        # rotação, não substituindo ninguém -- mesmo desenho do AoE.
        if k.break_soul and (not USAR_BREAK_SOUL_SO_NA_FASE_2
                             or self._na_segunda_fase_do_boss):
            rotacao.append(k.break_soul)

        return rotacao

    def _atacar_uma_vez(self, state, usar_aoe: bool = True) -> None:
        """Uma investida: UMA tecla da rotação, e o intervalo até a próxima.

        Uma por chamada, não uma rajada. Quem decide quantas vezes atacar é o laço
        de quem chamou, que entre as investidas relê a memória -- é assim que a
        morte do alvo é notada dentro de meio segundo em vez de no fim de uma
        sequência longa.

        `usar_aoe=False` para os GUARDAS. Ver `_rotacao_de_ataque`, que é quem
        monta a ordem das teclas e decide se o AoE entra.

        O MODO APP NÃO ENTRA AQUI. Ele era consultado nesta função e substituía a
        rotação; hoje é um sistema separado (`blazesbot/modo_app/`), que roda por
        conta própria e não conhece o combate da cave. Os dois não se misturam
        mais: mexer na rotação daqui não muda o APP, e ligar o APP não muda nada
        aqui.
        """
        key = self._proxima_skill(state, usar_aoe)
        if key is not None:
            self.ctx.press(key)
        # Espera o intervalo mesmo sem rotação: sem isso o laço da luta giraria
        # sem pausa nenhuma, queimando CPU de todas as contas ao mesmo tempo.
        self.ctx.tick(self.ctx.cave.attack_delay)

    def _proxima_skill(self, state, usar_aoe: bool) -> str | None:
        """A próxima tecla da rotação, já avançando o índice. `None` se não há.

        Separado de `_atacar_uma_vez` porque o fluxo por flag de combate precisa
        APERTAR sem DORMIR: ele mesmo controla o tempo, em fatias de
        `PASSO_DA_VIGIA_DE_COMBATE`, para reler a flag dez vezes por segundo em vez
        de ficar meio segundo cego entre dois golpes. Era o `ctx.tick` de dentro
        desta função que impedia isso.
        """
        ctx = self.ctx
        rotacao = self._rotacao_de_ataque(state, usar_aoe)
        if not rotacao:
            # A validação da conta já barra "nenhum ataque configurado", então
            # chegar aqui é sinal de configuração trocada com o bot rodando.
            if not self._avisou_sem_ataque:
                self._avisou_sem_ataque = True
                ctx.log.error(
                    "Nenhuma tecla de ataque configurada -- o personagem não vai "
                    "revidar. Configure em Editar conta > Teclas > Ataque."
                )
            return None

        key = rotacao[self._skill_index % len(rotacao)]
        self._skill_index += 1
        return key

    # ==================================================================
    # O FLUXO POR FLAG DE COMBATE -- é este que a run de BC usa
    # ==================================================================

    def _ler_flag_de_combate(self) -> bool | None:
        """A flag de combate, com os TRÊS estados preservados.

        `None` é "não consegui ler", e existe um método inteiro de cuidado nisso:
        tratar `None` como `False` transformaria uma falha de leitura em "a luta
        acabou", que no boss significa cantar vitória com ele vivo. Ver
        `LIMITE_SEM_LER_A_FLAG`.
        """
        return self.ctx.memory.in_battle()

    def _esperar_exato(self, segundos: float) -> None:
        """Espera o tempo EXATO pedido, sem o jitter de `ctx.tick`.

        `ctx.tick` sorteia ±15% de propósito, porque padrão perfeitamente regular é
        assinatura. O descanso entre as fases é uma exceção pedida explicitamente
        ("sentar por exatos 4 segundos"), do mesmo tipo que o modo APP.

        Continua em fatias curtas para que Parar e Pausar respondam na hora -- e o
        tempo pausado não conta, que é o comportamento certo: pausar não deveria
        encurtar o descanso.
        """
        fim = time.time() + segundos
        while True:
            self.ctx.wait_if_paused()
            self.ctx.raise_if_stopped()
            restante = fim - time.time()
            if restante <= 0:
                return
            time.sleep(min(0.05, restante))

    def _descer_para_lutar(self, o_que: str) -> bool:
        """Desmonta ao chegar no ponto de luta. MONTADO O PERSONAGEM NÃO ATACA.

        O jogo simplesmente ignora a tecla de skill com a montaria ativa, e não
        devolve erro nenhum -- do lado de fora parece que o bot está atacando e
        nada acontece. É a mesma armadilha silenciosa do pet e dos buffs no
        preparo, que já tem o mesmo tratamento lá.

        Chega montado por construção: a navegação exige montaria para andar, e os
        dois pontos de luta são o fim de um trajeto. Então este passo não é
        defensivo, é parte do fluxo.

        Vem ANTES de esperar o combate, não depois: assim, quando a flag ligar, o
        personagem já está a pé e o primeiro golpe sai na hora. Desmontar depois
        gastaria os primeiros segundos da luta apertando skill à toa.
        """
        ctx = self.ctx
        # Barra de atalhos na página 1 antes de qualquer skill. `forcar=True`:
        # nos dois pontos de luta uma tecla na página errada custa a run, então
        # aqui não se economiza clique pela recarga.
        hotbar.garantir_pagina_1(ctx, f"luta de {o_que}", forcar=True)
        if not ctx.memory.is_mounted():
            return True

        ctx.log.info("Desmontando antes da luta de %s -- montado o personagem "
                     "não ataca", o_que)
        # `permitir_em_batalha=True`: este é UM dos DOIS pontos de luta (os
        # 4 mobs antes do boss, ou o boss). Mesmo que a flag de combate já
        # esteja ligada ao chegar montado, é aqui que o personagem PRECISA
        # descer para atacar -- os únicos 2 momentos em que desmontar em
        # batalha é o objetivo, e não um risco. Ver `ensure_dismounted`.
        if self.nav.ensure_dismounted(permitir_em_batalha=True):
            return True

        # Não interrompe a fase: o prazo dela já cuida do caso de nada funcionar,
        # e registrar é o que permite distinguir "não desci" de "bati e não matei".
        ctx.log.error(
            "NÃO consegui desmontar para a luta de %s. As skills vão sair sem "
            "efeito enquanto a montaria estiver ativa.", o_que,
        )
        return False

    def esperar_entrar_em_combate(
        self,
        o_que: str,
        limite: float | None = ESPERA_PARA_ENTRAR_EM_COMBATE,
        pocao_na_espera: bool = True,
    ) -> bool:
        """Espera a flag de combate LIGAR. NÃO aperta TAB, não mira nada.

        Quem coloca o personagem em combate são os próprios mobs: eles atacam na
        chegada, e no jogo quem ataca passa a ser o alvo selecionado sem ninguém
        apertar nada. É por isso que o TAB não é necessário aqui -- e não apertá-lo
        elimina de uma vez o erro clássico de mirar o próprio pet.

        `limite=SEM_PRAZO` espera INDEFINIDAMENTE, e é como o boss chama. Ver a
        justificativa em `SEM_PRAZO`.

        `pocao_na_espera=False` é a ESPERA DO BOSS: lá não se bebe poção -- o boss
        encosta e a poção para de curar na hora, então o item se perde. Em vez de
        beber, o bot SENTA para regenerar de graça enquanto espera (ver
        `LIMINAR_TOPUP_ANTES_DO_BOSS`). Nos GUARDAS o comportamento é o antigo:
        poção vale, porque eles chegam batendo e a poção ainda tem efeito antes
        do corpo a corpo.

        Nos GUARDAS o `limite` padrão (30 s) é REDUZIDO a 5 s
        (`ESPERA_ENTRAR_EM_COMBATE_GUARDAS`): os 4 mobs atacam na chegada. Se em
        5 s ninguém veio, o covil já foi limpo ou o personagem parou longe -- e
        continuar para o boss é sempre melhor que bloquear a run por 30 s.

        Devolve False quando desiste, e há duas formas de desistir:

          * o prazo estourou (só quando existe prazo) -- "não havia ninguém para
            atacar": covil já limpo, ou personagem parado longe do ponto;
          * o personagem MORREU. Isto vale inclusive sem prazo: esperar combate
            começar estando morto é esperar para sempre por nada.
        """
        ctx = self.ctx
        k = ctx.settings.keys
        inicio = time.time()
        proxima_manutencao = 0.0
        proximo_aviso = inicio + AVISO_DA_ESPERA_SEM_PRAZO
        avisou_ilegivel = False

        while True:
            ctx.raise_if_stopped()
            agora = time.time()
            flag = self._ler_flag_de_combate()

            if flag:
                ctx.log.info("Em combate (%s) depois de %.1fs esperando",
                             o_que, agora - inicio)
                return True

            if flag is None and not avisou_ilegivel:
                avisou_ilegivel = True
                ctx.log.warning(
                    "A flag de combate não está sendo lida enquanto espero o "
                    "combate de %s começar. Continuo esperando -- ilegível não é "
                    "'fora de combate'.", o_que,
                )

            if limite is not None and agora - inicio >= limite:
                ctx.log.warning(
                    "Passaram %.0fs no ponto de %s e a flag de combate não ligou. "
                    "Ninguém veio atacar.", limite, o_que,
                )
                return False

            # Manutenção durante a espera, mas não a cada fatia: enquanto os mobs
            # se aproximam eles já batem, e vale beber poção. Uma vez por segundo
            # basta, e evita montar um retrato inteiro dez vezes por segundo.
            if agora >= proxima_manutencao:
                proxima_manutencao = agora + 1.0
                state = ctx.snapshot()

                # MORRER É A ÚNICA SAÍDA que uma espera sem prazo ainda tem além
                # da parada do usuário. Sem esta checagem, um personagem morto no
                # ponto do boss esperaria o combate começar para sempre.
                if state.dead:
                    ctx.log.error(
                        "Morri esperando o combate de %s começar (%.0fs)",
                        o_que, agora - inicio,
                    )
                    return False

                if pocao_na_espera:
                    self.maintain(state, em_luta=False)
                else:
                    # ESPERA DO BOSS: sem poção -- senta para regenerar de graça.
                    # O boss que encosta cancela a poção na hora, então beber aqui
                    # é gastar o item à toa. Só senta se ainda não estiver sentado
                    # e a vida estiver abaixo do limiar: regeneração com o tempo
                    # custa nada, e o combate que vier derruba o sentado sozinho.
                    if (k.sit and not state.sitting
                            and state.max_hp
                            and state.hp_pct < LIMINAR_TOPUP_ANTES_DO_BOSS):
                        ctx.log.info("Vida %.0f%% na espera do boss; sentando para "
                                     "regenerar em vez de beber poção.",
                                     state.hp_pct)
                        ctx.press(k.sit)
                        ctx.tick(0.2)

            # O AVISO PERIÓDICO. Sem prazo, o log é a única forma de distinguir
            # "esperando o boss se aproximar" de "travado".
            if agora >= proximo_aviso:
                proximo_aviso = agora + AVISO_DA_ESPERA_SEM_PRAZO
                ctx.log.info(
                    "Esperando o combate de %s começar há %.0fs%s. Parado no "
                    "ponto, sem apertar TAB.",
                    o_que, agora - inicio,
                    "" if limite is None else f" (prazo {limite:.0f}s)",
                )

            ctx.tick(PASSO_DA_VIGIA_DE_COMBATE)

    def _nomes_do_alvo(self) -> list[str | None]:
        """O nome do alvo, da MEMÓRIA. Lista vazia = não deu para ler.

        Este método foi escrito vazio, como o LUGAR da resposta, com a previsão
        de que *"quem descobrir uma fonte de nome muda só este método"*. Foi
        exatamente o que aconteceu em 25/08/2026: o `0x0115CB80` é o ID da
        entidade selecionada e a entidade guarda esse id em `+0x8`, então o
        nome está a três leituras de distância.

        LISTA, e não string, porque o `_veredito_do_alvo` foi feito para
        comparar VÁRIAS leituras (a seleção e o oponente) -- hoje a memória
        responde com uma fonte só, e uma lista de um item atravessa o mesmo
        caminho sem reescrever nada.

        Lista vazia continua sendo a resposta honesta quando a entidade não
        aparece: inventar nome aqui seria o mesmo defeito que o `hp` calculado
        tinha.
        """
        entidade = self._target_hybrid.entidade_do_alvo(self.ctx.pid)
        if entidade is None:
            return []
        nome = entidade.get("nome")
        return [nome] if nome else []

    def _veredito_do_alvo(self, esperado: str) -> str:
        """O que está na mira: `bate`, `acabaram` ou `ilegivel`.

        Olha a SELEÇÃO e o OPONENTE, e basta um dos dois trazer o nome esperado
        -- ver `alvo_e_oponente` para a razão (a segunda fase do boss deixa a
        seleção para trás).

        `acabaram` é o nome certo do desfecho, e não "alvo errado": no waypoint
        dos guardas os quatro Gun Witch são SEMPRE os primeiros alvos do TAB,
        então ler qualquer outro nome não é um problema a resolver -- é o aviso
        de que morreram e a fase pode seguir para o boss.
        """
        # ==================================================================
        # A FONTE DE NOME É A ENTIDADE -- desde 25/08/2026
        # ==================================================================
        #
        # `ilegivel` deixou de ser o único veredito possível. Ele continua
        # existindo e continua significando a mesma coisa: NÃO SEI. Quem
        # consome não pode tratar "não sei" como "alvo errado" -- parar de
        # bater por causa de uma leitura que falhou custa a luta inteira.
        legiveis = [n for n in self._nomes_do_alvo() if n]
        # Guarda o que ESTE veredito viu, para o log poder mostrar a mesma
        # fonte que decidiu. Imprimir `target_name()` ao lado do veredito era
        # enganoso: são leituras diferentes, e o log chegava a dizer
        # "veredito=ilegivel lido='Gun Witch'" na mesma linha.
        self._ultimos_nomes_do_alvo = legiveis
        if not legiveis:
            return "ilegivel"
        if any(esperado.lower() in n.lower() for n in legiveis):
            return "bate"
        return "acabaram"

    def _e_o_alvo_proibido(self, nomes: list[str] | None = None) -> bool:
        """O que está na mira é o Cemetery Guard? SÓ leitura, sem captura.

        Recebe os nomes de fora por padrão (`None` = os do último veredito) para
        NÃO fazer uma segunda leitura: quem pergunta acabou de ler, e duas
        leituras no mesmo instante já produziram o log enganoso
        "veredito=ilegivel lido='Gun Witch'" na mesma linha.
        """
        nomes = self._ultimos_nomes_do_alvo if nomes is None else nomes
        procurado = self.NOME_DO_ALVO_PROIBIDO.lower()
        return any(procurado in (n or "").lower() for n in (nomes or ()))

    def _travar_no_alvo_proibido(self, quem: str, fonte: str) -> None:
        """A ÚNICA trava do waypoint dos guardas -- UMA porta, duas fontes.

        A MEMÓRIA (nome da entidade selecionada, no portão de nome) e a TELA (o
        `cemetery_guard.png`, depois de cada TAB) chegam aqui, e não cada uma
        com o seu jeito de parar: o ESC que larga a mira e a flag que segura o
        golpe moram num lugar só.

        NÃO ENCERRA A FASE. Igual ao resto daqui, quem encerra é a flag de
        combate -- ver `EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS`.

        Idempotente de propósito: as duas fontes podem apontar o mesmo guarda no
        mesmo segundo, e ESC repetido fecha janela do jogo que ninguém pediu
        para fechar.
        """
        if getattr(self, "_alvo_proibido_encontrado", False):
            return
        self._alvo_proibido_encontrado = True
        ctx = self.ctx
        ctx.log.info(
            "Cemetery Guard na mira (%s: %s). Largo a mira no ESC, paro de "
            "bater e AGUARDO a saída de combate -- puxar o guarda tira a run "
            "da rota.", fonte, quem,
        )
        ctx.tick(0.28)
        ctx.press('esc', 0.16)

    @property
    def _morte(self) -> MorteDoAlvo:
        """A peça compartilhada, criada na primeira vez que alguém pergunta.

        PREGUIÇOSA DE PROPÓSITO, e não por descuido: vários testes desta suíte
        constroem o `CombatEngine` sem passar pelo `__init__` (`__new__` mais os
        atributos que o teste precisa), e é assim que eles conseguem exercitar
        uma regra sem montar um jogo inteiro. Exigir a construção completa só
        porque uma peça mudou de casa seria cobrar dos testes o preço de um
        conserto que não é deles.
        """
        morte = getattr(self, "_morte_do_alvo", None)
        if morte is None:
            morte = MorteDoAlvo()
            self._morte_do_alvo = morte
        return morte

    @property
    def _ultimo_alvo_morto_id(self) -> int | None:
        """O id do último alvo dado por morto. MORA NA PECA COMPARTILHADA.

        Continua exposto com o nome antigo de propósito: o caminho da TELA, o
        reset por luta e os testes já falam essa língua, e trocar o nome deles
        seria mexer em código estável para nenhum ganho. O que mudou é ONDE o
        valor vive -- ver `core/target_hybrid.MorteDoAlvo`, compartilhada com o
        modo APP.
        """
        return self._morte._ultimo_morto

    @_ultimo_alvo_morto_id.setter
    def _ultimo_alvo_morto_id(self, ident: int | None) -> None:
        if ident is None:
            self._morte.esquecer()
        else:
            self._morte.contar(ident)

    def _alvo_morreu(self) -> bool | None:
        """O alvo morreu? UMA leitura, UMA captura, e o log da vida sai daqui.

        =================================================================
        O FLUXO, COMBINADO COM O USUÁRIO EM 25/08/2026
        =================================================================

            id == 0            -> sem alvo. Não decide nada.
            id mudou           -> alvo novo. O vigia zera o que sabia dele.
            vida > 10%         -> vivo. NÃO procura marcador nenhum.
            vida <= 10%        -> a MESMA captura serve o `EnemyDead.png`:
                 marcador bateu       -> MORREU, libera o TAB
                 marcador não bateu   -> sobrou vida, continua batendo
            não deu para ler   -> "não sei". Não gasta TAB.

        =================================================================
        POR QUE O MARCADOR SÓ ABAIXO DE 10%
        =================================================================

        Palavras do usuário: *"a ideia do EnemyDead é só ser usado quando o
        ler_alvo identificar que a % da vida está abaixo dos 10%"*. Acima disso
        o mob está vivo e casar template é custo por nada -- e o `EnemyDead.png`
        tem falso positivo MEDIDO com o mob vivo (escore 0,955-0,971 contra
        limiar 0,85, com o mob em 35 de vida, em 20/08/2026). Consultá-lo só na
        faixa em que a barra já concorda com ele é o que tira o falso positivo
        do caminho.

        =================================================================
        UMA CAPTURA
        =================================================================

        A barra e o marcador saem do MESMO quadro. Duas capturas em instantes
        diferentes fazem as duas fontes discordarem sobre o mesmo momento -- é a
        lição que o `10-DESCOBRIR-ALVO` já pagou.
        """
        info = self._target_hybrid.ler(self.ctx.pid, self.ctx.hwnd)

        # O LOG DA VIDA SAI AQUI, antes de qualquer decisão -- é o que o usuário
        # pediu para acompanhar na tela do bot, e ele tem de aparecer mesmo
        # quando o veredito é "não sei".
        self._target_hybrid.registrar(
            info, segunda_fase=self._na_segunda_fase_do_boss)

        if info.mudou:
            self._ultimo_escore_do_marcador = None

        if not info.tem_alvo:
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=False, fonte="memoria", motivo="sem alvo")
            return False

        # ===================================================================
        # CAMINHO PRINCIPAL: A MEMÓRIA
        # ===================================================================
        if info.pela_memoria:
            return self._morte_pela_memoria(info)

        # ===================================================================
        # RESERVA: A TELA
        # ===================================================================
        #
        # Só quando a memória não achou a entidade -- medido em 25/08/2026,
        # acontece no instante em que um alvo novo é selecionado e a entidade
        # ainda não entrou no array (1 leitura em ~45 numa luta de boss). É
        # curto, mas cair para "não sei" ali gastaria uma volta do laço à toa.
        if info.barra is None:
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=None, fonte="tela", motivo="nao consegui ler a barra")
            return None

        vida = info.barra.vida
        if not info.vale_olhar_o_marcador:
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=False, fonte="tela", motivo=f"vida={vida * 100:.1f}%")
            return False

        # -- abaixo de 10%: o mesmo quadro responde pelo marcador -------------
        morto_na_tela, escore = self._marcador_no_quadro(info.quadro)
        self._ultimo_escore_do_marcador = escore
        if escore is not None and (self._melhor_escore_do_marcador is None
                                   or escore > self._melhor_escore_do_marcador):
            self._melhor_escore_do_marcador = escore

        visto = "?" if escore is None else f"{escore:.3f}"
        detalhe = f"vida={vida * 100:.1f}% escore={visto}"
        if morto_na_tela is None:
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=None, fonte="imagem",
                motivo=f"{detalhe}; nao deu para olhar o marcador")
            return None

        if not morto_na_tela:
            # A BARRA ZEROU E O MARCADOR NÃO APARECEU. Pela regra combinada, é
            # vida que sobrou e a barra não mostrou -- continua rotacionando.
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=False, fonte="imagem",
                motivo=f"{detalhe}; sem marcador, sobrou vida")
            return False

        if self._ultimo_alvo_morto_id == info.target_id:
            # MORTE JÁ CONTADA para ESTE alvo. O cadáver fica selecionável por
            # segundos (7 a 13 s, medido em 20/08/2026), e sem esta trava ele
            # gastaria um TAB por leitura enquanto estivesse ali.
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=False, fonte="imagem",
                motivo=f"{detalhe}; morte deste alvo ja foi contada")
            return False

        if SO_A_MEMORIA_DECLARA_MORTE:
            # A TELA NÃO MATA NINGUÉM. Ver o bloco
            # `SÓ A MEMÓRIA DECLARA MORTE`, no topo: o marcador tem falso
            # positivo MEDIDO com o mob vivo, e um TAB gasto à toa larga um mob
            # com vida para trás. "Não sei" é a resposta honesta -- e no ciclo
            # seguinte a memória responde.
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=None, fonte="imagem",
                motivo=f"{detalhe}; a tela acha que morreu, mas só a memória "
                       f"declara morte")
            return None

        self._ultimo_alvo_morto_id = info.target_id
        self._ultima_leitura_do_alvo = LeituraDoAlvo(
            morreu=True, fonte="imagem", motivo=detalhe)
        self.ctx.log.info("ALVO #%s MORREU  (%s)", info.target_id, detalhe)
        return True

    def _morte_pela_memoria(self, info) -> bool | None:
        """O alvo morreu, pelo HP da struct. Sem captura, sem template.

        =================================================================
        POR QUE A MEMÓRIA PASSOU NA FRENTE (25/08/2026)
        =================================================================

        O `18-CASAR-ALVO` confirmou que `0x0115CB80` é o ID da entidade
        selecionada e que a entidade carrega esse id em `+0x8`. Numa luta
        inteira, memória e tela casaram em quase todos os ciclos -- e nos que
        não casaram, **a errada era a tela**:

            'Gun Witch'  hp=6/100  (6.0%)   barra=23.1%   <- a tela atrasou
            'Blaze Skull Marshal' fase 2  hp=75/100  barra=50.0%  <- barra amarela

        A barra desenhada tem uma coleção de modos de falha que um inteiro
        vindo da struct simplesmente não tem: o piso de 0,7% com o mob morto, a
        amarela sobreposta à vermelha na fase 2, o marcador `EnemyDead.png` com
        falso positivo medido (0,955-0,971 com o mob VIVO), e a régua que
        devolvia float confiante medindo outra coisa. Todos eles erravam
        CALADOS.

        =================================================================
        `hp == 0` É MORTE -- MENOS NA FASE 1 DO BOSS
        =================================================================

        Medido: mob comum zera ('Gun Witch' 8 -> 0, 'Rose Snake' 6 -> 0) e o
        cadáver fica selecionável em 0 por vários segundos. **A fase 1 do boss
        NÃO zera** -- ela para em `hp=1` e some, nascendo a fase 2 como
        ENTIDADE NOVA (id novo, endereço novo, e nível 50 -> 51).

        Isso não é um caso a tratar aqui: o boss nunca foi dado por morto por
        HP. A regra do projeto -- *"boss só é dado por morto quando SAI DE
        BATALHA"* -- já cobria isso, e agora tem o porquê medido.
        """
        entidade = info.entidade
        hp, maximo = entidade["hp"], entidade["max_hp"]
        quem = entidade["nome"] or f"#{info.target_id}"
        detalhe = f"{quem} hp={hp}/{maximo} ({100.0 * hp / maximo:.1f}%)"

        # O VEREDITO E A TRAVA vêm da peça compartilhada com o modo APP --
        # `core/target_hybrid.MorteDoAlvo`. O que continua sendo daqui é o LOG e
        # a reserva pela tela, logo acima.
        if self._morte.veredito(entidade) is not True:
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=False, fonte="memoria", motivo=detalhe)
            return False

        if not self._morte.contar(info.target_id):
            # MORTE JÁ CONTADA para ESTE alvo. O cadáver fica selecionável por
            # segundos (medido: 7 a 13 s), e sem esta trava ele gastaria um TAB
            # por leitura enquanto estivesse ali. A trava é por IDENTIDADE, não
            # por tempo.
            self._ultima_leitura_do_alvo = LeituraDoAlvo(
                morreu=False, fonte="memoria",
                motivo=f"{detalhe}; morte deste alvo ja foi contada")
            return False
        self._ultima_leitura_do_alvo = LeituraDoAlvo(
            morreu=True, fonte="memoria", motivo=detalhe)
        self.ctx.log.info("ALVO MORREU: %s", detalhe)
        return True

    def _marcador_no_quadro(self, quadro) -> tuple[bool | None, float | None]:
        """O `EnemyDead.png` está no quadro do alvo? `None` = não deu para olhar.

        COMPLEMENTO: engole tudo. Falha de template no meio da luta viraria "não
        sei" de qualquer jeito, e subindo ela derrubaria a run.
        """
        if quadro is None:
            return None, None
        try:
            template = self.ctx.templates.load(TEMPLATE_INIMIGO_MORTO)
            if template is None:
                return None, None
            return vision.marcador_de_morte(quadro, template)
        except Exception as exc:
            self.ctx.log.debug("Falha ao olhar o marcador de morte: %s", exc)
            return None, None

    def atacar_ate_sair_de_combate(
        self,
        o_que: str,
        usar_aoe: bool,
        limite: float,
        tabs_ao_morrer: int = 0,
        exige_ter_entrado: bool = False,
        alvo_esperado: str | None = None,
        registrar_troca_de_fase: str | None = None,
        # SÓ O BOSS PASSA `True`. Ver `ATACAR_DURANTE_A_CONFIRMACAO_NO_BOSS`:
        # nos guardas continuar batendo convida o mob seguinte, na sala do boss
        # não há mob seguinte para convidar.
        atacar_na_confirmacao: bool = False,
        pos_tab_callback: callable | None = None,
    ) -> FimDeCombate:
        """Gira a rotação de skills até a flag de combate DESLIGAR.

        O laço é único e roda no passo da vigia (um décimo de segundo), não no
        intervalo do ataque. Os dois tempos convivem: a tecla sai a cada
        `bc.attack_delay`, e a flag é lida dez vezes por segundo. Era o contrário
        antes -- meio segundo dormindo entre golpes, cego para a mudança de estado.

        A SAÍDA DE COMBATE EXIGE CONFIRMAÇÃO CONTÍNUA. Um único `False` não
        encerra: com quatro guardas caindo um a um, a flag pisca entre eles, e
        encerrar na primeira leitura falsa terminaria a fase com três vivos.

        NÃO aperta TAB em momento nenhum, e não lê ponteiro de alvo nenhum.
        """
        ctx = self.ctx
        inicio = time.time()
        proximo_ataque = 0.0
        proxima_manutencao = 0.0
        falso_desde = 0.0
        ilegivel_desde = 0.0
        golpes = 0

        # Troca de alvo por TAB, guiada pela barra de vida na tela. A carência
        # começa valendo JÁ no início da luta, e não só depois do primeiro TAB:
        # no primeiro instante o alvo automático ainda não foi adquirido, e ler
        # ali veria "sem quadro" e gastaria uma troca à toa.
        tabs_dados = 0
        proxima_leitura = inicio + CARENCIA_APOS_O_TAB
        ja_entrou = False
        # O vigia é POR LUTA: o portão "já tive alvo" não pode atravessar de uma
        # luta para a outra, senão a segunda começaria com ele ligado e a
        # ausência do primeiro instante voltaria a valer como morte.
        self._ultima_leitura_do_alvo = None
        # Contra o que é esta luta. Só o log e a investigação usam.
        self._luta_atual = o_que
        # POR LUTA: a morte de um alvo contada numa luta não pode barrar o
        # mesmo id numa luta seguinte -- o cliente reaproveita valores.
        self._ultimo_alvo_morto_id = None
        # Flags para controle do Cemetery Guard (guards phase)
        self._alvo_proibido_encontrado = False
        self._logou_aguardando_saida_combate = False
        # Para o aviso "TAB segurado": o que foi dito na leitura anterior,
        # para detectar mudança de alvo.
        ultimo_dito = ""
        ultimo_veredito_do_nome = ""
        # O último nome que o portão viu e decidiu IGNORAR, para o aviso de
        # "continuo batendo" sair uma vez por nome novo e não a cada golpe.
        ultimo_quem_ignorado = ""
        # Orçamento POR LUTA de TAB para sair de alvo errado. Zerado aqui e não
        # na instância: cada luta merece as próprias tentativas.
        # Desde quando o nome do alvo não lê (0.0 = está lendo). Ver
        # `CARENCIA_SEM_LER_O_NOME`.
        sem_ler_desde = 0.0
        # Só para o aviso de "bati sem ler o nome" sair UMA vez por episódio.
        avisou_sem_ler = False
        # Idem para o aviso de "continuo batendo enquanto confirmo": uma linha
        # por LUTA, não uma por volta do laço.
        avisou_insistindo = False
        # O portão de NOME já disse que acabaram? Então o golpe e o TAB param, e
        # o laço só espera a saída de combate. POR LUTA, como todo o resto daqui.
        # Ver `EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS`.
        acabaram_os_alvos = False
        # Último ID de alvo visto, para registrar a troca de fase do
        # boss (ver `_registrar_troca_de_fase`).
        self._struct_do_alvo = None
        # A INSTRUMENTAÇÃO DO MARCADOR É POR LUTA, e zera aqui pelo mesmo
        # motivo de tudo o mais nesta vizinhança: "o melhor escore desta luta"
        # só responde à pergunta se for desta luta. Guardado na instância e
        # nunca zerado, o número da primeira fase contaminaria a leitura da run
        # inteira -- e é justamente por medição que o limiar vai ser ajustado.
        self._melhor_escore_do_marcador = None
        self._ultimo_escore_do_marcador = None
        self._escore_em_cor_do_marcador = None
        self._vermelho_onde_o_marcador_casou = None
        self._avisou_falha_da_prova = False
        # A CREDENCIAL DA MEMÓRIA é POR LUTA: o placar pode ter mudado entre uma
        # e outra (as amostras da luta anterior entraram nele), e uma credencial
        # que muda no meio da luta faria o log daquela luta descrever dois bots.
        self._credencial_da_memoria = None
        # A PENEIRA NÃO É ZERADA AQUI, ao contrário de tudo o mais nesta
        # vizinhança -- ela vive no `__init__` e ATRAVESSA lutas de propósito.
        # Ela precisa de três passadas com vida DIFERENTE, e uma luta de guardas
        # dura 8 s: zerar por luta jogaria fora toda a convergência, luta após
        # luta, e a peneira nunca fecharia.
        # E a bandeira da fase 2 desce AQUI, junto com ela, porque é aqui que
        # uma luta começa -- qualquer luta. Zerar no `fight_boss` não bastava:
        # aquele caminho está desativado, então a bandeira de uma run
        # sobreviveria para a próxima e a Break Soul sairia contra os guardas.
        self._na_segunda_fase_do_boss = False

        while True:
            ctx.raise_if_stopped()
            agora = time.time()
            decorrido = agora - inicio
            flag = self._ler_flag_de_combate()
            if flag:
                if not ja_entrou:
                    # Primeira vez que a flag sobe: ATACA IMEDIATAMENTE.
                    # Não espera as outras checagens (prova, manutenção, etc.)
                    ja_entrou = True
                    state = ctx.snapshot()
                    if not state.dead:
                        key = self._proxima_skill(state, usar_aoe)
                        if key is not None:
                            ctx.press(key)
                            golpes += 1
                            proximo_ataque = agora + ctx.cave.attack_delay
                else:
                    ja_entrou = True

            # AS PROVAS DE CALIBRAÇÃO SAÍRAM DAQUI em 25/08/2026, e elas
            # rodavam a cada `CADENCIA_DA_PROVA` com CAPTURA PRÓPRIA -- uma
            # segunda captura por meio segundo, em cinco contas, além da do
            # veredito.
            #
            # Elas mediam os candidatos a ponteiro do alvo (`0x808` e vizinhos),
            # e esses offsets já não existem em `Memory`. O que sobrava era o
            # aviso `'Memory' object has no attribute 'candidato_de_alvo'`
            # estourando toda luta (28 vezes nas 14 lutas de 24-25/08), engolido
            # pelo `try` e sem produzir amostra nenhuma.
            #
            # A investigação continua, FORA do caminho quente: o
            # `16-TESTAR-CORRELACAO-ALVO` faz o censo e o `logs/target_id/`
            # guarda o comportamento do `0x0115CB80`. Ferramenta temporária é o
            # lugar de investigação; o laço da luta não é.

            # -- morte do personagem ---------------------------------------
            #
            # Morrer também tira o personagem do combate. Sem esta checagem a
            # flag caindo por morte seria lida como "acabou a luta" -- e no boss
            # isso viraria vitória exatamente na run que se perdeu.
            if agora >= proxima_manutencao:
                proxima_manutencao = agora + 1.0
                state = ctx.snapshot()
                if state.dead:
                    ctx.log.error("Morri durante a luta de %s depois de %.0fs",
                                  o_que, decorrido)
                    # Registra aqui, e NÃO por `_registrar_morte`: aquela função
                    # lê nome e HP do ALVO, e chamá-la traria de volta o ponteiro
                    # de alvo justamente ao caminho que ficou livre dele. O `o_que`
                    # já diz contra o que a luta era, que é a informação útil.
                    diario.registrar_evento(
                        ctx.account_login, "morte",
                        f"morri na luta de {o_que} depois de {decorrido:.0f}s "
                        f"e {golpes} golpes",
                        state.position, state.location,
                    )
                    return FimDeCombate(False, "personagem morreu", decorrido,
                                        golpes)
                self.maintain(state, em_luta=True)
                # SÓ LOG, e no boss. O portão do alvo saiu daqui, então este
                # registro passou a ser o único jeito de o log contar que a
                # primeira fase caiu -- sem ele, "o HP subiu de 7 para 11"
                # parece defeito de leitura.
                if registrar_troca_de_fase:
                    self._registrar_troca_de_fase(registrar_troca_de_fase)
                    # E o SEGUNDO sinal da virada de fase, pela tela. Aqui
                    # dentro, e não fora, porque este `if` é o que garante "só
                    # na luta do boss"; e nesta cadência de 1 s, que é folgada
                    # para um sinal que dura uma barra de vida inteira.
                    self._conferir_fase_2_na_tela()
            else:
                state = None

            # -- a flag ----------------------------------------------------
            if flag is None:
                # Ilegível não é "fora de combate". Zera a confirmação de saída e
                # continua batendo: parar de atacar por falha de leitura é o pior
                # dos dois erros possíveis aqui.
                falso_desde = 0.0
                if ilegivel_desde == 0.0:
                    ilegivel_desde = agora
                elif agora - ilegivel_desde >= LIMITE_SEM_LER_A_FLAG:
                    ctx.log.error(
                        "A flag de combate está ilegível há %.0fs na luta de %s. "
                        "Desistindo SEM declarar vitória.",
                        agora - ilegivel_desde, o_que,
                    )
                    return FimDeCombate(False, "flag ilegível", decorrido, golpes)
            else:
                ilegivel_desde = 0.0
                if flag:
                    falso_desde = 0.0
                else:
                    if falso_desde == 0.0:
                        falso_desde = agora
                        ctx.log.info(
                            "A flag de combate baixou em %s (%.0fs de luta, %s "
                            "golpes). Confirmando por %.1fs antes de encerrar.",
                            o_que, decorrido, golpes,
                            CONFIRMACAO_DE_SAIDA_DE_COMBATE,
                        )
                    elif (agora - falso_desde >= CONFIRMACAO_DE_SAIDA_DE_COMBATE
                            and (ja_entrou or not exige_ter_entrado)):
                        ctx.log.info(
                            "Fora de combate confirmado em %s: %.1fs contínuos "
                            "com a flag baixa (%.0fs de luta, %s golpes)",
                            o_que, agora - falso_desde, decorrido, golpes,
                        )
                        return FimDeCombate(True, "saiu de combate", decorrido,
                                            golpes)

            # -- a luta forçada precisa COMEÇAR ----------------------------
            #
            # `exige_ter_entrado` vem do boss quando o engajamento foi forçado
            # por TAB. Sem este portão, a rotação começaria com a flag ainda
            # baixa e a confirmação de saída declararia VITÓRIA em 1,5s, sem
            # luta nenhuma -- na fase que decide a run.
            if exige_ter_entrado and not ja_entrou:
                if decorrido >= LIMITE_PARA_A_LUTA_COMECAR:
                    ctx.log.warning(
                        "Forcei o alvo com TAB em %s e a flag de combate não "
                        "subiu em %.0fs. O TAB não pegou o alvo certo; "
                        "devolvendo o controle SEM declarar vitória.",
                        o_que, LIMITE_PARA_A_LUTA_COMECAR,
                    )
                    return FimDeCombate(False, "a luta forçada não começou",
                                        decorrido, golpes)

            # -- prazo -----------------------------------------------------
            if decorrido >= limite:
                ctx.log.warning(
                    "A luta de %s passou de %.0fs e a flag de combate não "
                    "desligou (%s golpes). Encerrando SEM declarar vitória -- "
                    "provável flag presa em ligado.",
                    o_que, limite, golpes,
                )
                return FimDeCombate(False, "prazo estourado", decorrido, golpes)

            # -- o alvo morreu? troca com TAB ------------------------------
            #
            # Só quando quem chamou pediu (`tabs_ao_morrer > 0`) e ainda há
            # troca no orçamento. Sem isso o laço é exatamente o de sempre.
            # `not acabaram_os_alvos`: depois de o portão de nome dizer que
            # acabaram, TAB só serviria para adquirir mob que não precisava vir.
            # O TETO DO TAB NÃO BARRA A TROCA ENQUANTO A FLAG ESTIVER ALTA
            # -- ver `TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS`. `flag is True` e não
            # `flag`: ilegível (`None`) não autoriza gastar TAB, pela mesma
            # razão de sempre (não sei != acabou).
            tem_orcamento_de_tab = (
                tabs_dados < tabs_ao_morrer
                or (TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS and flag is True))
            if (tabs_ao_morrer and not acabaram_os_alvos
                    and not getattr(self, "_alvo_proibido_encontrado", False)
                    and tem_orcamento_de_tab
                    and agora >= proxima_leitura):
                proxima_leitura = agora + CADENCIA_DA_LEITURA_DO_ALVO
                morreu = self._alvo_morreu()
                leitura = self._ultima_leitura_do_alvo

                # `mudou` detecta troca de alvo — usado pelo aviso "TAB segurado"
                # abaixo. O log ALVO foi removido; o ponteiro segue relatado via
                # `texto_do_ponteiro` (testado isoladamente) quando necessário.
                mudou = False
                if leitura is not None:
                    mudou = leitura.chave != ultimo_dito
                    ultimo_dito = leitura.chave

                if morreu:
                    tabs_dados += 1
                    # UM lugar só para "aperta o TAB e espera o jogo redesenhar"
                    # -- `_trocar_de_alvo`. Estas três linhas viviam soltas aqui
                    # e o destravamento precisava das mesmas: duas cópias do
                    # mesmo gesto divergiriam em silêncio, e a que ficasse para
                    # trás leria a barra do alvo ANTIGO.
                    self._trocar_de_alvo()
                    # Carência: o quadro do alvo novo leva um instante para
                    # desenhar, e ler nesse vão veria a barra do alvo ANTIGO.
                    proxima_leitura = agora + CARENCIA_APOS_O_TAB
                    ctx.log.info(
                        "Alvo caiu em %s: TAB %s de %s (%.0fs de luta, %s "
                        "golpes) — %s",
                        o_que, tabs_dados, tabs_ao_morrer, decorrido, golpes,
                        leitura.resumo() if leitura else "sem leitura",
                    )
                    # Callback pós-TAB: permite lógica customizada após cada troca de alvo.
                    # Se retornar True, encerra a fase de combate imediatamente.
                    if pos_tab_callback is not None:
                        try:
                            if pos_tab_callback(tabs_dados):
                                ctx.log.info(
                                    "Callback pós-TAB pediu encerramento da fase em %s "
                                    "(TAB %s de %s)", o_que, tabs_dados, tabs_ao_morrer
                                )
                                return FimDeCombate(
                                    True, "callback pos-tab encerrou fase",
                                    decorrido, golpes
                                )
                        except Exception as e:
                            ctx.log.warning(
                                "Erro no callback pós-TAB em %s: %s", o_que, e
                            )
                elif mudou and morreu is None and leitura is not None:
                    # TAB SEGURADO: "não sei" não gasta TAB. Uma linha por
                    # episódio (não por leitura) para não afogar o log.
                    ctx.log.info("TAB segurado em %s (%.0fs): %s",
                                 o_que, decorrido, leitura.motivo)

            # -- o golpe ---------------------------------------------------
            #
            # A FLAG JÁ BAIXOU DEPOIS DE A LUTA TER COMEÇADO? Então não sai mais
            # golpe, mesmo com a saída ainda em confirmação. O bloco do golpe não
            # olhava para `falso_desde`, e o resultado era o bot batendo por
            # segundos DEPOIS de a luta acabar -- que é como se convida o mob
            # seguinte. Confirmar vira só "tenho certeza que acabou".
            #
            # O `ja_entrou` é o que separa "a luta ACABOU" de "a luta ainda NÃO
            # COMEÇOU", e sem ele o engajamento forçado do boss morre: lá o bot
            # dá o TAB dos 5s com a flag ainda baixa e entra na rotação
            # justamente para PUXAR o boss -- TAB sozinho não engaja, quem engaja
            # é o golpe. Com a flag baixa contando como "acabou", ele giraria o
            # laço sem soltar skill nenhuma até o prazo de `LIMITE_PARA_A_LUTA
            # _COMECAR`, e a run se perderia parada na frente do boss.
            # NO BOSS O GOLPE NÃO PARA durante a confirmação -- ver
            # `ATACAR_DURANTE_A_CONFIRMACAO_NO_BOSS` para o log que mediu o
            # defeito. Quem reengaja a fase seguinte é o golpe, e ficar passivo
            # aqui é o que fazia a virada de fase virar "vitória".
            insistir = (atacar_na_confirmacao
                        and ATACAR_DURANTE_A_CONFIRMACAO_NO_BOSS)
            if falso_desde and ja_entrou and insistir and not avisou_insistindo:
                avisou_insistindo = True
                ctx.log.info(
                    "A flag baixou em %s, mas continuo batendo enquanto "
                    "confirmo: se for virada de fase, o golpe reengaja e a luta "
                    "segue; se estiver morto, nada reage e a saída confirma.",
                    o_que,
                )
            if (not (falso_desde and ja_entrou and not insistir)
                    and agora >= proximo_ataque):
                if state is None:
                    state = ctx.snapshot()
                proximo_ataque = agora + ctx.cave.attack_delay

                # PORTÃO DO ALVO. Só os guardas o usam. No BOSS ele NÃO existe:
                # entrou em combate, ataca -- lá o TAB no meio da luta trocava o
                # alvo justamente na virada de fase, e o que resolve a virada é
                # continuar batendo (a fase 2 pega o alvo sozinha ao atacar).
                pode_bater = True

                # ACABARAM OS ALVOS: o golpe fica parado e o laço só espera a
                # flag baixar. Mesma porta do Cemetery Guard, logo abaixo.
                if acabaram_os_alvos:
                    pode_bater = False

                # Se Cemetery Guard foi detectado, para de atacar mas continua
                # no loop aguardando a flag de combate baixar
                if getattr(self, "_alvo_proibido_encontrado", False):
                    pode_bater = False
                    # Log periódico para saber que está esperando
                    if not getattr(self, "_logou_aguardando_saida_combate", False):
                        ctx.log.info(
                            "Cemetery Guard detectado anteriormente; aguardando "
                            "saída de combate (flag ainda alta) para prosseguir."
                        )
                        self._logou_aguardando_saida_combate = True

                if alvo_esperado and USAR_PORTAO_DE_NOME:
                    veredito = self._veredito_do_alvo(alvo_esperado)
                    # LOG DETALHADO do portão do nome: só na MUDANÇA, porque
                    # este bloco roda a cada `attack_delay`. É o segundo elo da
                    # cadeia que produzia "atacando mob que não é Gun Witch" —
                    # sem ele não dá para ver, no log, o instante em que o alvo
                    # deixou de bater com o esperado.
                    if veredito != ultimo_veredito_do_nome:
                        ultimo_veredito_do_nome = veredito
                        ctx.log.debug(
                            "NOME %s t=%.1fs veredito=%s esperado=%r "
                            "lido=%s (seleção e oponente)",
                            o_que, decorrido, veredito, alvo_esperado,
                            self._ultimos_nomes_do_alvo or "nada",
                        )
                    if veredito == "acabaram" and not acabaram_os_alvos:
                        # QUEM está na mira sai dos NOMES que o veredito acabou
                        # de ler -- é a mesma leitura que decidiu, e não uma
                        # segunda. O log já dizia "veredito=ilegivel
                        # lido='Gun Witch'" na mesma linha por causa disso.
                        quem = ", ".join(self._ultimos_nomes_do_alvo) or "?"
                        # NOME QUE NÃO É O CEMETERY GUARD NÃO PARA MAIS A LUTA.
                        # Ver `SO_O_ALVO_PROIBIDO_PARA_O_GOLPE`:
                        # era esta porta que deixava um Gun Witch vivo em cima
                        # do personagem com o bot parado. A trava continua
                        # inteira contra quem ela foi medida para barrar.
                        if SO_O_ALVO_PROIBIDO_PARA_O_GOLPE:
                            if self._e_o_alvo_proibido():
                                self._travar_no_alvo_proibido(quem, "memória")
                                pode_bater = False
                            elif quem != ultimo_quem_ignorado:
                                # Uma linha por NOME NOVO, não por golpe: este
                                # bloco roda a cada `attack_delay`.
                                ultimo_quem_ignorado = quem
                                ctx.log.info(
                                    "O alvo em %s agora é %s (não é %r nem %r) "
                                    "-- CONTINUO batendo: ainda estou em "
                                    "combate, e só a saída de combate encerra "
                                    "esta fase.",
                                    o_que, quem, alvo_esperado,
                                    self.NOME_DO_ALVO_PROIBIDO)
                        # A FASE NÃO ENCERRA AQUI. Ver
                        # `EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS`: devolver vitória
                        # com a flag alta levava o bot ao waypoint do boss EM
                        # COMBATE, e lá a flag alta faz a luta do boss começar
                        # sem o boss -- quando o que estava batendo morre, a flag
                        # baixa e o boss é declarado derrotado sem ser tocado.
                        elif EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS:
                            acabaram_os_alvos = True
                            pode_bater = False
                            ctx.log.info(
                                "Acabaram os %s: o alvo agora é %s "
                                "(%s mortes contadas, %.0fs de luta, %s "
                                "golpes). Paro de bater e de dar TAB, mas "
                                "AGUARDO a saída de combate antes de seguir -- "
                                "chegar no boss em batalha perde a run.",
                                alvo_esperado, quem, tabs_dados, decorrido,
                                golpes)
                        else:
                            ctx.log.info(
                                "Acabaram os %s: o alvo agora é %s "
                                "(%s mortes contadas, %.0fs de luta, %s golpes). "
                                "Não ataco mais nada aqui -- sigo para o boss.",
                                alvo_esperado, quem, tabs_dados, decorrido,
                                golpes)
                            return FimDeCombate(
                                True, f"acabaram os {alvo_esperado}",
                                decorrido, golpes)
                    if veredito == "ilegivel":
                        # Segura o golpe enquanto o nome não lê. Quase sempre a
                        # luta acaba dentro da carência -- e aí não havia mesmo
                        # ninguém para atacar.
                        if sem_ler_desde == 0.0:
                            sem_ler_desde = agora
                        pode_bater = (agora - sem_ler_desde
                                      >= CARENCIA_SEM_LER_O_NOME)
                        if pode_bater and not avisou_sem_ler:
                            # Bater sem saber em quem é decisão consciente (ver
                            # `CARENCIA_SEM_LER_O_NOME`), mas até agora não
                            # aparecia no log — e é exatamente o que o usuário vê
                            # como "atacando mob que não deveria". Agora aparece.
                            #
                            # A flag é SÓ para não repetir o aviso a cada golpe.
                            # Mexer em `sem_ler_desde` aqui reiniciaria a
                            # carência e o bot passaria a bater de 3 em 3
                            # segundos — mudança de comportamento disfarçada de
                            # log.
                            avisou_sem_ler = True
                            ctx.log.warning(
                                "Vou bater SEM LER o nome do alvo em %s: %.1fs "
                                "sem leitura (carência %.1fs). Esperado %r.",
                                o_que, agora - sem_ler_desde,
                                CARENCIA_SEM_LER_O_NOME, alvo_esperado,
                            )
                    else:
                        sem_ler_desde = 0.0
                        avisou_sem_ler = False

                if pode_bater:
                    key = self._proxima_skill(state, usar_aoe)
                    if key is not None:
                        ctx.press(key)
                        golpes += 1

            ctx.tick(PASSO_DA_VIGIA_DE_COMBATE)

    # ==================================================================
    # DESTRAVAMENTO -- ver o bloco "DESTRAVAMENTO: MATAR MOB A MOB PARA SAIR
    # DE BATALHA" no topo do arquivo para o log que mediu o defeito.
    # ==================================================================

    def limpar_o_combate(self, motivo: str) -> bool:
        """Mata mob a mob ate SAIR DE BATALHA. Ultimo recurso, nao fase da run.

        Chamado de FORA, pelo portao da montaria, quando ele conclui que nao
        monta PORQUE esta em batalha. Devolve True quando a saida de combate se
        confirma, False quando o teto estoura -- e False nao encerra nada: o
        portao continua insistindo e chama de novo.

        A COREOGRAFIA E A DO USUARIO, e cada passo dela tem motivo:

            1. um alvo por vez, SEM AoE  -- area puxa quem estava de fora
            2. bate ate ele cair         -- `_bater_ate_o_alvo_cair`
            3. PARA e olha a flag por 3s -- `_esperar_a_flag_baixar`
            4. so entao UM TAB, e volta ao 2

        O passo 3 e o que impede a bola de neve. Sem ele o TAB imediato depois
        da morte mira o mob seguinte, o golpe o puxa, e o bot troca um
        travamento por outro -- gastando a run em vez de um minuto.
        """
        ctx = self.ctx
        inicio = time.time()

        # `is False` e nao `not`: ilegivel (`None`) NAO e "fora de combate".
        # Quem chamou esta travado ha mais de um minuto, e desistir por nao
        # conseguir ler devolveria o bot para o mesmo laco mudo do log.
        if self._ler_flag_de_combate() is False:
            ctx.log.debug("Destravamento (%s): ja estou fora de batalha", motivo)
            return True

        ctx.log.warning(
            "DESTRAVANDO (%s): estou preso em batalha, e e por isso que a "
            "montaria nao sobe. Vou matar UM DE CADA VEZ ate a flag baixar, "
            "com teto de %.0fs.", motivo, TETO_DO_DESTRAVAMENTO,
        )

        # Montado o personagem NAO ataca -- o jogo ignora a tecla de skill e nao
        # devolve erro nenhum. Chegar aqui montado e improvavel (em batalha nao
        # se monta), mas o passo e barato e a alternativa e girar a rotacao sem
        # dano nenhum, que e a armadilha silenciosa de sempre.
        self._descer_para_lutar("destravar (%s)" % motivo)

        # POR EPISODIO, pelo mesmo motivo que sao por luta em
        # `atacar_ate_sair_de_combate`: um id ja contado barraria o TAB do mesmo
        # id agora, e o cliente reaproveita valores.
        self._morte.esquecer()
        self._ultima_leitura_do_alvo = None
        self._alvo_proibido_encontrado = False
        self._avisou_o_guarda_no_destravamento = False

        mortes = tabs = golpes = 0
        while time.time() - inicio < TETO_DO_DESTRAVAMENTO:
            ctx.raise_if_stopped()

            # Sem ninguem na mira, UM TAB -- e um so. Varios TAB seguidos varrem
            # a vizinhanca e acabam mirando quem esta FORA do combate, que e
            # exatamente como se puxa mob novo.
            if not self._tem_alvo():
                tabs += 1
                self._trocar_de_alvo()

            # O prazo do mob NUNCA passa do que sobra do teto. Sem isto uma
            # rodada iniciada em 59 s rodaria mais 23 s, e o "no maximo atrasar
            # 1 minuto" que o usuario pediu viraria um minuto e meio.
            restante = TETO_DO_DESTRAVAMENTO - (time.time() - inicio)
            caiu, novos = self._bater_ate_o_alvo_cair(
                motivo, min(LIMITE_POR_MOB_NO_DESTRAVAMENTO, restante))
            golpes += novos
            if caiu:
                mortes += 1

            # A PAUSA. Parado, sem bater, olhando a flag. Sai no instante em que
            # a saida confirma; so depois dela e que o TAB seguinte e gasto.
            if self._esperar_a_flag_baixar(
                    ESPERA_APOS_A_MORTE_ANTES_DO_TAB, motivo):
                gasto = time.time() - inicio
                ctx.log.info(
                    "DESTRAVADO (%s) em %.0fs: %s morte(s), %s TAB, %s golpes. "
                    "Liberando o portao da montaria.",
                    motivo, gasto, mortes, tabs, golpes,
                )
                diario.registrar_evento(
                    ctx.account_login, "destravamento",
                    "sai de batalha matando mob a mob antes de %s: %s morte(s), "
                    "%s TAB, %s golpes em %.0fs"
                    % (motivo, mortes, tabs, golpes, gasto),
                    ctx.memory.position(), ctx.memory.location(),
                )
                return True

            # Continua em batalha depois dos 3 s: o proximo alvo. So gasta o
            # TAB se ainda houver rodada pela frente -- mirar alguem novo na
            # saida seria entregar um alvo a ninguem.
            if time.time() - inicio < TETO_DO_DESTRAVAMENTO:
                tabs += 1
                self._trocar_de_alvo()

        ctx.log.error(
            "NAO DESTRAVEI (%s) em %.0fs: %s morte(s), %s TAB, %s golpes e "
            "continuo em batalha. O portao da montaria vai insistir e me chamar "
            "de novo.", motivo, TETO_DO_DESTRAVAMENTO, mortes, tabs, golpes,
        )
        diario.registrar_evento(
            ctx.account_login, "destravamento-falhou",
            "nao sai de batalha antes de %s em %.0fs (%s morte(s), %s golpes)"
            % (motivo, TETO_DO_DESTRAVAMENTO, mortes, golpes),
            ctx.memory.position(), ctx.memory.location(),
        )
        return False

    def _trocar_de_alvo(self) -> None:
        """UM TAB, com a espera que o jogo precisa para redesenhar o quadro.

        A leitura do alvo e zerada junto: sem isso a primeira leitura depois do
        TAB veria o alvo ANTIGO (morto) e o log contaria uma morte que ja foi
        contada.
        """
        ctx = self.ctx
        ctx.press(ctx.settings.keys.next_target, 0.15)
        ctx.tick(ESPERA_DEPOIS_DO_TAB)
        self._ultima_leitura_do_alvo = None

    def _tem_alvo(self) -> bool:
        """Ha alguem na mira AGORA? So memoria, sem captura.

        "Nao sei" conta como NAO TEM, de proposito: o custo de errar para este
        lado e um TAB; o de errar para o outro e o bot girando a rotacao contra
        o nada ate o teto do mob.
        """
        try:
            return self.ctx.memory.alvo_atual() is not None
        except Exception as exc:
            self.ctx.log.debug("Nao li o alvo no destravamento: %s", exc)
            return False

    def _esperar_a_flag_baixar(self, prazo: float, motivo: str) -> bool:
        """Espera a flag baixar E CONFIRMAR, sem bater em nada.

        `prazo` conta para a flag COMECAR a baixar. Depois que ela baixa, a
        confirmacao vai ate o fim mesmo passando do prazo: cortar a confirmacao
        pela metade para gastar um TAB e justamente o que puxa mob novo.

        A regua da confirmacao e a mesma de `atacar_ate_sair_de_combate`
        (`CONFIRMACAO_DE_SAIDA_DE_COMBATE`), e pelo mesmo motivo -- um unico
        `False` nao encerra nada: com mobs caindo um a um a flag pisca entre
        eles, e foi um pisco de 2,6 s que mandou o bot para o portao travado.
        """
        ctx = self.ctx
        limite = time.time() + prazo
        # Teto absoluto: a flag pode ficar num vaivem de baixa e alta, e sem isto
        # nem a confirmacao fecharia nem o prazo venceria.
        teto = limite + CONFIRMACAO_DE_SAIDA_DE_COMBATE + 1.0
        baixa_desde = 0.0
        while True:
            ctx.raise_if_stopped()
            agora = time.time()
            if self._ler_flag_de_combate() is False:
                if baixa_desde == 0.0:
                    baixa_desde = agora
                elif agora - baixa_desde >= CONFIRMACAO_DE_SAIDA_DE_COMBATE:
                    ctx.log.info(
                        "Fora de combate confirmado no destravamento (%s): "
                        "%.1fs continuos com a flag baixa",
                        motivo, agora - baixa_desde,
                    )
                    return True
            else:
                # Alta OU ilegivel: a confirmacao recomeca. "Nao sei" nunca vale
                # como "saiu" -- ver `_ler_flag_de_combate`.
                baixa_desde = 0.0
            if agora >= (teto if baixa_desde else limite):
                return False
            ctx.tick(PASSO_DA_VIGIA_DE_COMBATE)

    def _bater_ate_o_alvo_cair(self, motivo: str,
                               prazo: float) -> tuple[bool, int]:
        """Gira a rotacao contra UM alvo ate ele cair. Devolve (caiu, golpes).

        SEM AoE, e isso e o ponto: area acerta quem esta em volta e PUXA mob que
        nao estava em combate -- o oposto do que o destravamento quer. Um de cada
        vez foi como o usuario pediu, e e tambem o unico jeito de a pausa depois
        da morte significar alguma coisa.

        Sai ANTES da hora em tres casos, e nenhum deles e "o alvo morreu": a
        flag baixou (quem confirma e o chamador), o personagem morreu, ou o
        prazo deste mob estourou.
        """
        ctx = self.ctx
        fim = time.time() + prazo
        golpes = 0
        proximo_ataque = 0.0
        proxima_manutencao = 0.0
        # A carencia vale JA no comeco: o quadro do alvo novo leva um instante
        # para desenhar, e ler nesse vao veria a barra do alvo ANTIGO.
        proxima_leitura = time.time() + CARENCIA_APOS_O_TAB
        while time.time() < fim:
            ctx.raise_if_stopped()
            agora = time.time()

            if self._ler_flag_de_combate() is False:
                # A flag baixou no meio da luta deste mob. Sai JA -- continuar
                # batendo depois de a luta acabar e como se convida o seguinte.
                return False, golpes

            state = None
            if agora >= proxima_manutencao:
                proxima_manutencao = agora + 1.0
                state = ctx.snapshot()
                if state.dead:
                    ctx.log.error("Morri destravando (%s) depois de %s golpes",
                                  motivo, golpes)
                    return False, golpes
                # POCAO E CURA ENTRAM AQUI. O portao da montaria nao tinha
                # manutencao nenhuma -- foi assim que o log passou 1465 s sem
                # uma unica leitura de vida, com um guarda batendo.
                self.maintain(state, em_luta=True)

            if agora >= proxima_leitura:
                proxima_leitura = agora + CADENCIA_DA_LEITURA_DO_ALVO
                if self._alvo_morreu():
                    return True, golpes

            if agora >= proximo_ataque:
                proximo_ataque = agora + ctx.cave.attack_delay
                if self._pode_bater_no_destravamento():
                    if state is None:
                        state = ctx.snapshot()
                    key = self._proxima_skill(state, usar_aoe=False)
                    if key is not None:
                        ctx.press(key)
                        golpes += 1

            ctx.tick(PASSO_DA_VIGIA_DE_COMBATE)
        return False, golpes

    def _pode_bater_no_destravamento(self) -> bool:
        """O alvo da mira pode apanhar? So o Cemetery Guard levanta a pergunta.

        Ver `DESTRAVAMENTO_BATE_NO_ALVO_PROIBIDO` para a decisao e o porque.
        Com o interruptor ligado a resposta e sempre sim -- e o aviso sai UMA vez
        por episodio, porque este metodo roda a cada `attack_delay`.
        """
        ctx = self.ctx
        if not USAR_PORTAO_DE_NOME:
            return True
        # Popula `_ultimos_nomes_do_alvo` -- a MESMA leitura que
        # `_e_o_alvo_proibido` consulta logo abaixo, e nao uma segunda.
        self._veredito_do_alvo(self.NOME_DO_ALVO_PROIBIDO)
        if not self._e_o_alvo_proibido():
            return True

        if not DESTRAVAMENTO_BATE_NO_ALVO_PROIBIDO:
            self._travar_no_alvo_proibido(
                self.NOME_DO_ALVO_PROIBIDO, "destravamento")
            return False

        if not getattr(self, "_avisou_o_guarda_no_destravamento", False):
            self._avisou_o_guarda_no_destravamento = True
            ctx.log.warning(
                "O que me segura em batalha e o %s. Fora do destravamento eu "
                "largaria a mira no ESC -- mas o ESC e a espera JA falharam, e "
                "foi assim que a run de 31/08 ficou 24 minutos parada. VOU "
                "MATA-LO.", self.NOME_DO_ALVO_PROIBIDO,
            )
            diario.registrar_evento(
                ctx.account_login, "destravamento-guarda",
                "matando o %s para sair de batalha -- o ESC e a espera nao "
                "bastaram" % self.NOME_DO_ALVO_PROIBIDO,
                ctx.memory.position(), ctx.memory.location(),
            )
        return True

    def sentar_para_recuperar(
        self,
        segundos: float = SEGUNDOS_SENTADO_APOS_GUARDAS,
        exato: bool = False,
    ) -> bool:
        """Senta alguns segundos para recuperar vida e mana, e levanta.

        SEM CHAMADOR HOJE. O único era a fase dos guardas, e o descanso saiu de lá
        por medição: quatro segundos parado não recuperavam o suficiente para
        mudar a luta do boss, e eram quatro segundos por run. Fica no arquivo
        porque é o único lugar do bot que sabe sentar e levantar conferindo a
        memória -- a tecla é interruptor, e apertá-la de pé faz sentar na hora de
        andar.

        `exato=True` desliga o jitter de `ctx.tick` e cumpre o tempo pedido ao pé
        da letra. É como a fase dos guardas chama, porque o descanso entre as fases
        foi especificado como "exatos 4 segundos" -- exceção explícita à regra de
        variar todos os tempos, do mesmo tipo que o modo APP.

        Chamado DEPOIS dos guardas e ANTES de encostar no boss. É o único momento da
        run em que dá para sentar: no trajeto da cave o trem de mobs não deixa, e na
        frente do boss é a luta que decide a run.

        Levanta explicitamente no fim. Sentado o personagem não monta nem anda, e o
        passo seguinte é justamente ir até o boss.
        """
        ctx = self.ctx
        tecla = ctx.settings.keys.sit
        if not tecla:
            return False

        antes = ctx.snapshot()
        ctx.log.info("Sentando %s%.0fs antes do boss (vida %.0f%%, mana %.0f%%)",
                     "exatos " if exato else "", segundos,
                     antes.hp_pct, antes.mp_pct)
        ctx.press(tecla)
        if exato:
            self._esperar_exato(segundos)
        else:
            ctx.tick(segundos)

        depois = ctx.snapshot()
        ctx.log.info("Depois de sentar: vida %.0f%%, mana %.0f%%",
                     depois.hp_pct, depois.mp_pct)

        # Levanta. Confere pela memória em vez de apertar e assumir: a tecla
        # alterna, e apertá-la já de pé faria o personagem SENTAR na hora de andar.
        if ctx.memory.is_sitting():
            ctx.press(tecla)
            ctx.tick(0.25)
        return True

    # ==================================================================
    # Boss
    # ==================================================================

    def precisa_curar(self, hp_pct: float) -> bool:
        """Falta vida para o mínimo de iniciar a cave?

        UM LIMIAR SÓ. Antes eram três, e a decisão saía de comparar dois deles
        entre si -- "não curar acima de" contra "só Super Skill acima de" --, o
        que dava para configurar de um jeito em que a poção nunca era usada.

        Agora é uma pergunta direta: a vida está abaixo do mínimo para começar?
        Se está, cura; se não está, sai andando.
        """
        if hp_pct <= 0:
            return False
        return hp_pct < self.ctx.settings.potions.hp_pct

    def curar_ao_entrar(self) -> bool:
        """Cura até o MÍNIMO PARA INICIAR, e só então libera a travessia.

        POR QUE AQUI, e não depois de matar o boss: entrar na cave é disputado e
        pode levar muito tempo de tentativa. Nesse intervalo o personagem
        regenera sozinho, de graça. Curar antes de sair gastaria poção que a
        espera ia devolver -- e sentar do lado de fora não acelera a entrada.

        =================================================================
        A POÇÃO LEVA 15 SEGUNDOS, E ANDAR CANCELA
        =================================================================

        Esta é a mecânica que dá forma à função. A poção não devolve vida de uma
        vez: ela cura ao longo de 15 segundos, e qualquer movimento interrompe.
        Então disparar a poção e sair andando -- que era o que esta função fazia
        -- é gastar o item e receber uma fração do efeito.

        Por isso o desenho é um LAÇO com espera parada:

            Super Skill (uma vez, se houver)
            enquanto faltar vida:
                poção -> ficar parado 15 s -> reler a vida

        A ORDEM: Super Skill primeiro porque ela é instantânea e não é item
        comprado. Se ela já fechar a diferença, nenhuma poção é gasta. Sem Super
        Skill configurada, o laço vira só poção -- que é o caso de várias classes.
        """
        ctx = self.ctx
        k = ctx.settings.keys
        alvo = ctx.settings.potions.hp_pct
        estado = ctx.snapshot()
        if not estado.max_hp:
            ctx.log.debug("Sem leitura de HP; não há como decidir a cura")
            return False

        if not self.precisa_curar(estado.hp_pct):
            ctx.log.info(
                "Entrei com %.0f%% de vida, o mínimo para começar é %s%% — sigo "
                "direto", estado.hp_pct, alvo,
            )
            return False

        ctx.log.info("Entrei com %.0f%% de vida; o mínimo para começar é %s%%. "
                     "Curando antes de andar.", estado.hp_pct, alvo)
        if not self._preparar_para_agir("curar depois de entrar"):
            return False

        # F1 antes: a Super Skill e a skill de cura precisam de alvo, e o alvo é
        # o próprio personagem. Sem isso a skill sai no que estiver selecionado.
        self.auto_selecionar()

        inicial = estado.hp_pct

        # -- Super Skill, UMA vez ------------------------------------------
        #
        # Uma só porque ela tem recarga longa: repetir a cada volta do laço
        # apertaria uma tecla que não sai. Se ela bastar, o laço abaixo nem roda.
        if k.super_skill:
            ctx.log.info("Usando a Super Skill de cura")
            ctx.press(k.super_skill)
            ctx.tick(SEGUNDOS_DEPOIS_DA_SUPER_SKILL)
        elif k.heal_skill and MODO_DE_CURA != "skill_em_laco":
            ctx.log.info("Usando a skill de cura")
            ctx.press(k.heal_skill)
            ctx.tick(SEGUNDOS_DEPOIS_DA_SUPER_SKILL)

        # A SKILL DE CURA VIROU UM LAÇO, não um aperto.
        #
        # Antes ela saía UMA vez e todo o resto era poção -- o que desperdiça a
        # skill: uma conjuração raramente leva a vida ao alvo sozinha, e a partir
        # da segunda o bot gastava item comprado tendo mana na barra.
        #
        # NÃO devolve daqui de propósito. O laço de poções logo abaixo já começa
        # perguntando se a vida chegou no alvo -- se a cura bastou, ele sai sem
        # apertar nada. Um `return` aqui duplicaria essa decisão em dois lugares.
        if k.heal_skill:
            self.curar_com_skill(alvo)

        # -- poções, uma de cada vez, esperando o efeito inteiro -----------
        pocoes = 0
        limite = time.time() + ctx.settings.potions.max_heal_seconds
        while True:
            ctx.raise_if_stopped()
            atual = ctx.snapshot()
            if not atual.max_hp:
                break
            if atual.hp_pct >= alvo:
                break
            if not k.hp_potion:
                ctx.log.warning(
                    "Faltam %.0f pontos percentuais para o mínimo de %s%%, mas "
                    "não há tecla de poção de HP configurada.",
                    alvo - atual.hp_pct, alvo,
                )
                break
            if time.time() >= limite:
                ctx.log.warning(
                    "Passaram %ss curando e a vida parou em %.0f%% (mínimo %s%%). "
                    "Provável falta de poção na bolsa. Sigo assim mesmo.",
                    ctx.settings.potions.max_heal_seconds, atual.hp_pct, alvo,
                )
                break

            pocoes += 1
            ctx.log.info(
                "Poção de HP %s: %.0f%% de %s%%. Vou ficar parado %.0fs -- andar "
                "cancela o efeito.",
                pocoes, atual.hp_pct, alvo, SEGUNDOS_DA_POCAO_DE_VIDA,
            )
            ctx.press(k.hp_potion)
            # PARADO O TEMPO INTEIRO. É o ponto da mudança: a espera não é
            # cadência, é a duração do efeito.
            ctx.tick(SEGUNDOS_DA_POCAO_DE_VIDA)

        depois = ctx.snapshot()
        ctx.log.info("Vida depois da cura: %.0f%% (era %.0f%%, mínimo %s%%, "
                     "%s poção(ões))", depois.hp_pct, inicial, alvo, pocoes)
        # Cura que não mexeu na vida é ação sem efeito -- registra para análise.
        if depois.hp_pct <= inicial + 1:
            diario.registrar_evento(
                ctx.account_login, "acao-sem-efeito",
                f"curei com {pocoes} poção(ões) e a vida não subiu "
                f"({inicial:.0f}% -> {depois.hp_pct:.0f}%); "
                "confira as teclas de Super Skill e poção",
                depois.position, depois.location,
            )
        return True

    def _beber_ate_encher(self, tecla_da_pocao: str, antes: float) -> None:
        """Poção por poção até `ALVO_DO_TOPUP_ANTES_DO_BOSS`, sentado.

        UMA DE CADA VEZ, e é decisão do usuário: cada poção rende o efeito
        completo, e disparar várias juntas desperdiça item comprado. Mesmo
        desenho do laço de `curar_ao_entrar`.

        SAI NO INSTANTE EM QUE ENCHE -- também pedido dele: *"caso atinja os
        100% pode continuar, sem ter que esperar os 15 segundos totais"*. Quem
        confere é a memória, a cada `FATIA_DA_ESPERA_DA_POCAO`.

        O TETO É `max_heal_seconds`, e ele existe porque insistir sem poção na
        bolsa prenderia a run com o boss esperando. Estourar não é erro: é aviso,
        e a run segue.
        """
        ctx = self.ctx
        alvo = ALVO_DO_TOPUP_ANTES_DO_BOSS
        limite = time.time() + ctx.settings.potions.max_heal_seconds
        pocoes = 0

        try:
            while time.time() < limite:
                ctx.raise_if_stopped()
                estado = ctx.snapshot()
                if not estado.max_hp:
                    ctx.log.debug("Sem leitura de HP; encerro o top-up")
                    break
                if estado.hp_pct >= alvo:
                    break

                ctx.log.info(
                    "Poção de HP %s (vida %.0f%%, alvo %s%%) -- até %.0fs parado",
                    pocoes + 1, estado.hp_pct, alvo, SEGUNDOS_DA_POCAO_DE_VIDA)
                ctx.press(tecla_da_pocao)
                pocoes += 1
                if self._esperar_o_efeito_da_pocao(alvo):
                    break
        finally:
            depois = ctx.snapshot()
            atual = depois.hp_pct if depois.max_hp else None
            if atual is not None and atual >= alvo:
                ctx.log.info(
                    "Top-up completo: %.0f%% -> %.0f%% com %s poção(ões)",
                    antes, atual, pocoes)
            else:
                ctx.log.warning(
                    "Top-up NÃO encheu a vida: %.0f%% -> %s (alvo %s%%) com %s "
                    "poção(ões). Provável falta de poção na bolsa. Sigo ao boss "
                    "assim mesmo.",
                    antes, f"{atual:.0f}%" if atual is not None else "ilegível",
                    alvo, pocoes)
            # NENHUMA TECLA DE POSTURA AQUI, nem sentar nem levantar. A poção
            # senta sozinha, e qualquer movimentação levanta -- as duas
            # confirmadas pelo usuário. `sit` é interruptor: mexer nele por
            # garantia é a forma mais fácil de terminar de pé quando se queria
            # sentado, ou o contrário.

    def _esperar_o_efeito_da_pocao(self, alvo: float) -> bool:
        """Cumpre os 15 s da poção, saindo cedo se a vida chegar no alvo.

        O PRAZO É POR RELÓGIO, não por `ctx.tick(15.0)`. O `tick` sorteia jitter
        sobre o valor inteiro, e 15 s viravam 12,75 s a 17,25 s -- o defeito
        relatado. Aqui as fatias podem jitterar à vontade: quem manda é
        `time.time()`, então o total nunca sai curto.

        Devolve `True` se a vida chegou no alvo antes do prazo.
        """
        ctx = self.ctx
        fim = time.time() + SEGUNDOS_DA_POCAO_DE_VIDA
        while time.time() < fim:
            ctx.tick(FATIA_DA_ESPERA_DA_POCAO)
            estado = ctx.snapshot()
            if estado.max_hp and estado.hp_pct >= alvo:
                ctx.log.info("Vida chegou em %.0f%% -- não espero o resto",
                             estado.hp_pct)
                return True
        return False

    def heal_to_full(self) -> bool:
        """Recuperação longa, com poção, Super Skill e sentar.

        Usada FORA da instância, quando há tempo: depois de reviver ou antes de
        uma volta à cidade. Dentro da cave quem cura é `curar_ao_entrar`, que é
        uma rajada curta e não senta.

        A ORDEM IMPORTA, e vem da prática: poção, depois Super Skill, depois
        sentar -- as três em sequência rápida. Disparadas assim, a poção e a
        Super Skill correm ao mesmo tempo em vez de uma esperar a outra, e sentar
        por cima amplifica a regeneração de HP e de mana. Sentar sozinho é lento;
        poção sozinha não recupera mana.
        """
        ctx = self.ctx
        st = ctx.settings
        k = st.keys
        alvo = st.potions.hp_pct
        limite = time.time() + st.potions.max_heal_seconds

        ctx.log.info("Recuperando até %s%%", alvo)
        if not self._preparar_para_agir("recuperar vida e mana"):
            return False

        # F1 em vez de TAB. O TAB daqui selecionava o PRÓXIMO alvo -- que num
        # lugar movimentado é um mob, e aí a Super Skill e a cura saíam nele.
        self.auto_selecionar()

        # Rajada inicial: poção, Super Skill e sentar, uma atrás da outra.
        if k.hp_potion:
            ctx.press(k.hp_potion)
            ctx.tick(0.125)
        if k.super_skill:
            ctx.press(k.super_skill)
            ctx.tick(0.125)
        elif k.heal_skill:
            ctx.press(k.heal_skill)
            ctx.tick(0.125)
        if k.sit:
            ctx.press(k.sit)
            ctx.tick(0.3)

        # O LAÇO DA CURA VEM DEPOIS DE SENTAR, não na rajada.
        #
        # Sentar amplifica a regeneração e não custa nada esperar, então gastar
        # conjuração antes de estar sentado seria desperdício. E este é o lugar
        # onde a cura por skill vale mais: fora da instância há tempo, não há
        # mob, e quem acabou de reviver costuma estar SEM poção.
        if k.heal_skill:
            self.curar_com_skill(alvo)

        # Maior vida já vista nesta recuperação. Serve para detectar dano recebido
        # sem consultar flag de combate: recuperando, a vida só sobe.
        melhor_hp = ctx.snapshot().hp_pct

        while time.time() < limite:
            ctx.raise_if_stopped()
            estado = ctx.snapshot()
            if not estado.alive:
                raise Disconnected("memória ilegível durante a recuperação")
            if estado.dead:
                self._registrar_morte("recuperando vida", estado)
                return False

            if estado.hp_pct >= alvo and estado.mp_pct >= alvo:
                ctx.log.info("Recuperado (%.0f%% HP, %.0f%% MP)",
                             estado.hp_pct, estado.mp_pct)
                if estado.sitting and k.sit:
                    ctx.press(k.sit)
                    ctx.tick(0.25)
                return True

            # Levar dano derruba quem está sentado, e a checagem de batalha que
            # existia aqui foi removida. O sinal direto é melhor de qualquer forma:
            # se a vida CAIU em vez de subir, alguém está batendo -- levanta e
            # deixa o laço tratar, sem depender de flag nenhuma.
            if estado.hp_pct < melhor_hp - 1.0:
                ctx.log.info("A vida caiu de %.0f%% para %.0f%% enquanto recuperava; "
                             "algo está batendo", melhor_hp, estado.hp_pct)
                if estado.sitting and k.sit:
                    ctx.press(k.sit)
                melhor_hp = estado.hp_pct
                ctx.tick(0.6)
                continue
            melhor_hp = max(melhor_hp, estado.hp_pct)

            # Reforço enquanto espera: mais poção e mais Super Skill quando o HP
            # ainda está baixo, sem sair de sentado.
            if estado.hp_pct < st.potions.hp_pct:
                if k.hp_potion:
                    ctx.press(k.hp_potion)
                    ctx.tick(0.15)
                if k.super_skill:
                    self.auto_selecionar()
                    ctx.press(k.super_skill)
                    ctx.tick(0.15)

            if k.sit and not estado.sitting:
                ctx.press(k.sit)
                ctx.tick(0.4)

            ctx.tick(0.5)

        ctx.log.warning("Tempo de recuperação esgotado")
        return False

    # ==================================================================
    # Pet e buffs
    # ==================================================================

    def ensure_pet(self, timeout: float = 10.0) -> bool:
        """Garante que o pet está invocado.

        Roda obrigatoriamente após todo login: o pet é essencial (auto-pick e
        dano), e sem ele a run é desperdício.

        Desmonta antes. Montado, a tecla de invocar não faz nada -- era por isso
        que o bot "invocava" sete vezes sem o pet aparecer.
        """
        ctx = self.ctx
        if not ctx.settings.keys.pet_summon:
            return True
        hotbar.garantir_pagina_1(ctx, "invocar o pet")
        if not self._memoria_confiavel():
            ctx.log.warning(
                "Não consigo confirmar o pet pela memória; invocando UMA vez e "
                "seguindo, em vez de repetir sem saber o resultado."
            )
            ctx.press(ctx.settings.keys.pet_summon)
            ctx.tick(1.5)
            return False
        if ctx.memory.pet_active():
            return True

        if not self._preparar_para_agir("invocar o pet"):
            return False

        deadline = time.time() + timeout
        while time.time() < deadline:
            ctx.raise_if_stopped()
            ctx.log.info("Invocando pet")
            ctx.press(ctx.settings.keys.pet_summon)
            ctx.tick(1.5)
            if ctx.memory.pet_active():
                ctx.log.info("Pet ativo")
                return True
        ctx.log.warning("Pet não ficou ativo")
        diario.registrar_evento(
            ctx.account_login, "acao-sem-efeito",
            "invoquei o pet e ele não apareceu",
            ctx.memory.position(), ctx.memory.location(),
        )
        return False

    def apply_buffs(self) -> None:
        """Aplica os buffs configurados, em si mesmo.

        F1 antes de cada um: buff é skill, skill precisa de alvo, e o alvo é o
        próprio personagem. Sem o F1 o buff ia para o que estivesse selecionado.
        """
        ctx = self.ctx
        teclas = [k for k in ctx.settings.keys.buffs if k]
        if not teclas:
            return
        if not self._preparar_para_agir("aplicar buffs"):
            return
        self.auto_selecionar()
        for key in teclas:
            ctx.press(key)
            ctx.tick(0.6)

    # -- comida de pet -----------------------------------------------------

    @property
    def minutos_para_alimentar(self) -> float:
        """Quanto falta para a comida do pet vencer. Negativo = já venceu.

        Delega para o `PetFeeder` compartilhado.
        """
        return self._pet_feeder.minutos_para_alimentar(
            self.ctx.settings.pet.feed_every_minutes
        )

    def vale_alimentar_antes_de_entrar(self, folga_minutos: float = 4.0) -> bool:
        """Está perto de vencer o bastante para alimentar ANTES de entrar?

        Alimentar exige desmontar, e desmontar no meio da cave é parar com o trem
        de mobs em cima. Se falta pouco, é melhor adiantar aqui fora: a run leva
        alguns minutos e o pet venceria no pior lugar possível.
        """
        if not self.ctx.settings.keys.pet_food:
            return False
        return self.minutos_para_alimentar <= folga_minutos

    def _gravar_grade_da_comida(self, vence: float) -> None:
        """Guarda no `config.json` quando a próxima refeição vence.

        É o `gravar` do `PetFeeder` (ver `core/pet.py`), chamado por ele a cada
        mudança da grade -- e não mais só depois de alimentar.

        COMPLEMENTO: engole tudo. Falha ao gravar não pode derrubar a run -- o
        pior desfecho é a grade voltar ao que estava no disco, que é o
        comportamento de antes desta mudança. É também o contrato que o
        `PetFeeder` exige de quem passa a função.
        """
        try:
            self.ctx.settings.pet.proxima_comida_em = float(vence)
            self.ctx.config.save()
        except Exception as exc:
            self.ctx.log.debug("Não gravei a grade da comida do pet: %s", exc)

    def feed_pet(self, force: bool = False, dentro_da_cave: bool = False) -> bool:
        """Alimenta o pet respeitando o intervalo configurado.

        Pet sem comida DESAPARECE sozinho, e um pet que sumiu no meio da cave
        estraga a run sem avisar. Por isso a alimentação é por tempo decorrido,
        não por evento: o bot conta os minutos desde a última vez.

        ONDE ELA ACONTECE MUDOU EM 25/08/2026. Antes era "dentro da cave nunca,
        e adianta antes de entrar" -- porque alimentar exige desmontar e
        desmontar no meio da travessia é parar com meia cave correndo atrás.

        Agora é no PREPARO DE ENTRADA (`RotinaBC._do_curar`): já dentro, ainda
        parado, e já a pé por causa da cura. Isso resolve os dois lados -- não
        desmonta fora da cave (regra do usuário) e não para no meio da travessia
        (a razão da regra antiga).

        O que continua proibido é alimentar DEPOIS que a travessia começou, e
        quem garante isso é `dentro_da_cave=True`, passado por quem chama de
        dentro do trajeto.

        Usa o `PetFeeder` compartilhado para decidir QUANDO alimentar, com grade
        FIXA: atrasar uma refeição não empurra as seguintes.
        """
        ctx = self.ctx
        tecla = ctx.settings.keys.pet_food
        if not tecla:
            return False

        # Delega a DECISÃO para o PetFeeder (lógica compartilhada).
        if not self._pet_feeder.deve_alimentar(
            ctx.settings.pet.feed_every_minutes, force=force
        ):
            return False

        if dentro_da_cave and not force:
            ctx.log.debug(
                "Comida do pet vencida, mas estou dentro da cave: alimentar aqui "
                "exigiria desmontar. Fica para a saída."
            )
            return False

        if not self._preparar_para_agir("alimentar o pet"):
            return False

        # ==============================================================
        # EM BATALHA A TECLA DE ALIMENTO É IGNORADA -- e a grade NÃO avança
        # ==============================================================
        #
        # O APP já sabia disso e barrava a comida em combate (ver o laço em
        # `bot/app/executor`); o BC não barrava, e `_do_curar` roda logo depois
        # de entrar na cave, onde o aggro é a regra e não a exceção. Sem esta
        # guarda o desfecho é o pior possível: a tecla é engolida pelo jogo, a
        # grade avança e o pet fica 56 minutos sem comer com o relógio dizendo
        # que comeu.
        #
        # "NÃO SEI" NÃO BLOQUEIA (`in_battle()` é tri-estado): só `True` barra.
        if ctx.memory.in_battle() is True and not force:
            ctx.log.info(
                "Comida do pet vencida, mas estou EM BATALHA: a tecla seria "
                "ignorada pelo jogo. A grade NÃO avança -- fica para a próxima."
            )
            return False

        # A BARRA DE ATALHOS, GARANTIDA POR ESTA FUNÇÃO E NÃO PELA ANTERIOR.
        #
        # Antes `feed_pet` não pedia a página 1: ela vinha de carona do
        # `ensure_pet` imediatamente anterior -- e só quando `summon_on_login`
        # estava ligado. Com ele desligado, a tecla da comida saía com a página
        # NÃO VERIFICADA, e na página errada o mesmo '6' dispara outra coisa sem
        # que o bot tenha como perceber.
        #
        # A recarga de `hotbar` (5 s) impede que isto vire clique a mais quando
        # o `ensure_pet` acabou de garantir; e `garantir_pagina_1` agora ASSENTA
        # antes de devolver (ver `hotbar.ASSENTAR_A_PAGINA`), então a tecla da
        # comida não corre com a troca de página.
        hotbar.garantir_pagina_1(ctx, "alimentar o pet")

        # O ESTADO VAI PARA O LOG JUNTO. Não há confirmação por memória para
        # "o item foi consumido" (não existe ponteiro de fome mapeado), então o
        # que sobra é registrar, no instante do aperto, tudo que sabidamente
        # engole a tecla. É esta linha que transforma "não funciona" em "não
        # funciona QUANDO".
        ctx.log.info(
            "Alimentando o pet (a cada %s min) | tecla=%s montado=%s "
            "batalha=%s sentado=%s pet=%s",
            ctx.settings.pet.feed_every_minutes, tecla,
            ctx.memory.is_mounted(), ctx.memory.in_battle(),
            ctx.memory.is_sitting(), ctx.memory.pet_active(),
        )
        if not ctx.press(tecla):
            # A TECLA NÃO SAIU. `Input.key` só recusa tecla que ele não sabe
            # traduzir -- é erro de configuração, não situação de jogo. A grade
            # não avança: alimentar zero vezes com o relógio andando é
            # exatamente o defeito que se está consertando.
            ctx.log.error(
                "A tecla da comida do pet (%r) não foi reconhecida; o pet NÃO "
                "foi alimentado. Confira a tecla em Editar conta.", tecla)
            diario.registrar_evento(
                ctx.account_login, "acao-sem-efeito",
                f"tecla de comida do pet inválida: {tecla!r}",
                ctx.memory.position(), ctx.memory.location(),
            )
            return False

        # A JANELA EM QUE A AÇÃO SEGUINTE CANCELA O ITEM.
        #
        # Era `tick(0.5)`, e `_do_curar` monta logo depois: medido no log, a
        # tecla da montaria saía 600 ms depois da comida e cancelava o uso. Ver
        # `SEGUNDOS_PARA_A_COMIDA_SER_USADA` em `core/pet.py`.
        ctx.tick(SEGUNDOS_PARA_A_COMIDA_SER_USADA)

        # A GRADE AVANÇA a partir do vencimento, não do agora -- é o que mantém
        # o número de refeições por dia. O `PetFeeder` já grava no disco. Ver
        # `core/pet.py`.
        self._pet_feeder.registrar_alimentacao(
            ctx.settings.pet.feed_every_minutes)
        return True

    # ==================================================================
    # Registro de morte
    # ==================================================================

    def _registrar_morte(self, contexto: str, state) -> None:
        """Morte é bug: registra tudo que ajuda a descobrir o porquê.

        Uma conta só é marcada para BC quando dá conta da cave sem morrer. Então
        morrer significa que alguma coisa aqui está errada -- limiar de poção
        alto, tecla que não sai, alvo perdido, rota que passou por um pack. O
        diário de eventos guarda o suficiente para reconstituir o caso.
        """
        ctx = self.ctx
        st = ctx.settings
        ctx.log.error(
            "PERSONAGEM MORREU %s | HP %s/%s | MP %s/%s | posição %s | local %s",
            contexto, state.hp, state.max_hp, state.mp, state.max_mp,
            state.position, state.location,
        )
        diario.registrar_evento(
            ctx.account_login, "morte",
            f"{contexto} | hp={state.hp}/{state.max_hp} "
            f"mp={state.mp}/{state.max_mp} "
            f"alvo={state.target_name!r} hp_alvo={state.target_hp} "
            f"limiar_batalha={st.potions.battle_hp_pct}% "
            f"limiar_emergencia={st.potions.emergency_pct}% "
            f"pocao_batalha={st.keys.battle_hp_potion or '-'} "
            f"pocao={st.keys.hp_potion or '-'} "
            f"ataques={','.join(k for k in st.keys.attack_skills if k) or '-'} "
            f"aoe={st.keys.aoe_skill or '-'}",
            state.position, state.location,
        )
        self._parar_a_conta_se_precisou_de_pocao()

    def _parar_a_conta_se_precisou_de_pocao(self) -> None:
        """Morreu DEPOIS de ter precisado de poção antes do boss? Para a conta.

        Regra do usuário, 19/08/2026: *"caso ele precisou se curar e depois
        aconteça do personagem morrer, você deve parar o bot BC daquela conta,
        pois deve estar com falta de item essencial para rodar o bot."*

        O raciocínio é bom e vale escrever: chegar no boss abaixo de 50% já é
        sinal de que a run está apertada; morrer depois disso, tendo gasto poção,
        aponta para **estoque acabando** -- e uma conta sem poção não termina run
        nenhuma. Insistir a noite inteira gasta a instância, o item que ainda
        resta e o tempo, sem nunca fechar um boss.

        A CONTA FICA ONLINE. Só o `bc_farm` é desligado, o checkbox desmarca nas
        duas interfaces, e o relogin continua valendo -- é o mesmo desfecho que a
        venda usa quando não há tecla de retorno.
        """
        if not self._precisou_de_pocao_antes_do_boss:
            return
        ctx = self.ctx
        ctx.account.bc_farm = False
        try:
            ctx.config.save()
        except Exception as exc:
            ctx.log.warning("Não consegui salvar a configuração: %s", exc)
        ctx.log.error(
            "BC DESLIGADO para esta conta: o personagem precisou de poção antes "
            "do boss e MORREU depois. Isso aponta para falta de item essencial "
            "-- reponha as poções e marque o BC de novo."
        )
        diario.registrar_evento(
            ctx.account_login, "bc-desligado-por-morte",
            "precisou de poção no top-up antes do boss e morreu depois; "
            "provável falta de item essencial",
            ctx.memory.position(), ctx.memory.location(),
        )
