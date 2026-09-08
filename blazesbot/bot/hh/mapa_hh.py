"""Mapa da HH (Black Wind Camp Dungeon): waypoints, bosses e a rota de chegada.

=========================================================================
DE ONDE VIERAM ESTES NÚMEROS
=========================================================================

Do bot de terceiros em Lua/UoPilot que roda esta cave HOJE, em produção, na
máquina do usuário (`D:\\Versoes do Bot\\OutrosBots\\HH - cave full - ARVV3N`,
módulos `hh.lua` e `farmer.lua`). São 66 waypoints medidos passo a passo -- 65
nos quatro trechos dos bosses e 1 no trecho de saída --, cada um com um clique de
minimapa calibrado à mão.

**ISSO NÃO É PALPITE E NÃO É ARREDONDAMENTO.** É a medição de um bot que
funciona, e é a fonte mais forte disponível sem remedir a cave inteira. A
dissecação completa -- incluindo o que daquele bot foi REPROVADO e não passou --
está em `docs/decisoes/hh.md`.

O que veio da TELA, lido nas capturas do usuário em 01/09/2026 e não do Lua: o
nome da zona externa, o caminho de chegada (Fay -> West Suburb -> Mutual Quest
Woman -> Elite Axe Monk Soldier), a coordenada de conversa e o vendedor.

=========================================================================
POR QUE O CAMINHO MORA NO CÓDIGO E NÃO NA CONFIGURAÇÃO
=========================================================================

Mesmo motivo do `mapa_bc.py`: o caminho é PROPRIEDADE DO JOGO, não preferência
de quem usa. Um waypoint errado não deixa o bot "mais lento" -- ele faz o
personagem bater na parede até o tempo estourar. Na BC, enquanto o caminho morou
no `config.json`, uma rota antiga gravada numa execução anterior continuou sendo
usada depois de a certa ser medida, e era impossível perceber porque tudo parecia
configurado.

=========================================================================
O QUE AINDA NÃO ESTÁ MEDIDO -- LEIA ANTES DE CONFIAR NA ÁREA
=========================================================================

Os nomes de ÁREA de dentro desta cave são quase todos DESCONHECIDOS. O bot Lua
nunca lê o nome do lugar: ele decide tudo por coordenada.

DOIS FORAM MEDIDOS, nos prints do usuário de 03/09/2026, e eles provam que o
interior tem MAIS DE UMA área nomeada -- o que descarta a hipótese de tratar a
cave inteira como um nome só:

    (55, 33) .... "Happiness Hall Dungeon"      -- onde a entrada deposita
    (529, 118) .. "Happiness Hall Main Hall"    -- o ponto de saída

Fora da cave é `Black Wind Camp Dungeon`, que já estava medido.

Os outros 64 waypoints continuam com `AREA_INTERNA_NAO_MEDIDA`. É um
MARCADOR EXPLÍCITO, não uma adivinhação disfarçada de dado: enquanto ele estiver
ali, a área não serve para conferir onde o bot está, e quem depender disso tem de
tratar a ausência. Preencher exige rodar a ferramenta de medição pela rota e
registrar o que `Memory.location()` devolve em cada trecho.

Ver `docs/decisoes/hh.md`, seção 9, para a lista completa do que falta medir.
"""
from __future__ import annotations

from ...core import rota

# REEXPORTAÇÃO PROPOSITAL (a forma `X as X` é o que diz isso ao ruff): a HH
# chama estes nomes por `mapa_hh.`, igual à BC por `mapa_bc.`. A regra mora em
# `core/rota.py`; aqui ficam só os dados desta cave.
from ...core.rota import Retomada as Retomada
from ...core.rota import Waypoint as Waypoint
from ...core.rota import distancia as distancia
from ...core.rota import mais_proximos as mais_proximos
from ...core.rota import montar as _wp
from ...core.rota import vizinhos_na_rota as vizinhos_na_rota

# ---------------------------------------------------------------------------
# Nomes de lugar
# ---------------------------------------------------------------------------

# A zona de FORA da cave, lida da tela em 01/09/2026 (o rótulo do canto superior
# direito do cliente). É onde ficam o NPC de entrada e o vendedor.
LUGAR_FORA_DA_HH = "Black Wind Camp Dungeon"

# O grupo do painel de arredores naquele lugar. Serve para conferir que o painel
# abriu no lugar certo antes de confiar no resultado da busca.
GRUPO_DOS_ARREDORES = "Outside Black Wind Camp"

# O QUE "HH" SIGNIFICA: **Happiness Hall**.
#
# Lido no link do diálogo do NPC da entrada em 03/09/2026 -- "Enter Happiness
# Hall". A sigla é do usuário e do bot em Lua; o jogo escreve o nome inteiro
# nesse link, e em nenhum outro lugar.
#
# NÃO É O NOME DO LUGAR. A ZONA se chama `Black Wind Camp Dungeon` (é o que a
# memória devolve, e o que entra em `core/lugares.py`); `Happiness Hall` é o
# nome da INSTÂNCIA, que só aparece no link de entrar.
NOME_DA_INSTANCIA = "Happiness Hall"

# Marcador para a área que ainda não foi medida. Ver o cabeçalho do módulo: é
# proposital que isto seja feio e visível.
AREA_INTERNA_NAO_MEDIDA = "HH (área não medida)"

# OS DOIS NOMES DE DENTRO QUE JÁ FORAM MEDIDOS -- E ELES SÃO DA **TELA**.
#
# =========================================================================
# NÃO COMPARE ESTES NOMES COM `Memory.location()`
# =========================================================================
#
# Vieram dos prints do usuário de 03/09/2026, do canto superior direito do
# cliente, onde o jogo escreve `<lugar> [x, y]`. Isso é o rótulo da ÁREA, e
# **não é o que o ponteiro devolve**.
#
# O ponteiro devolve `Black Wind Camp Dungeon` -- dentro E fora da cave. Medido
# no log de 03/09/2026: a linha que confirma a entrada diz
# *"Entrada na HH confirmado em 0 ms: (55, 33) | local Black Wind Camp
# Dungeon"*, e em 673 menções do log essa é a ÚNICA string de lugar.
#
# Quando estes dois nomes entraram aqui, em 03/09, eles foram tratados como se
# fossem leitura de ponteiro. Não são, e a diferença importa: é por isso que
# `etapa_pelo_lugar` decide "dentro ou fora" pela COORDENADA e nunca pelo nome.
#
# Para que servem, então: são o rótulo humano da área numa `Waypoint.area` --
# melhor no log que o marcador `HH (área não medida)` -- e são a prova de que o
# interior tem MAIS DE UMA área nomeada.
ROTULO_DE_TELA_DA_CHEGADA = "Happiness Hall Dungeon"
AREA_DA_SAIDA = "Happiness Hall Main Hall"


# ---------------------------------------------------------------------------
# A rota de CHEGADA -- Stone City até o NPC da entrada
# ---------------------------------------------------------------------------
#
# O bot Lua NÃO faz esta rota: ele clica o traço de missão em (743, 251) e assume
# que o personagem já está por perto -- só funciona porque o usuário posiciona o
# personagem à mão antes de ligar o script. O caminho abaixo é o que o usuário
# ditou e as capturas confirmaram.

# O MESMO NPC de transporte da BC. Par (texto de busca, nome para confirmar).
NPC_DE_TRANSPORTE = ("Fay", "Transport Fay")

# O destino no diálogo do Fay. **SÓ APARECE ROLANDO A LISTA ATÉ O FIM.**
#
# É a diferença que mais importa contra a BC: `Ghost Din Woods` (Need 7, nível
# 48) está na parte visível do diálogo, e `West Suburb of Stone City` (Need 5,
# nível 20) não está -- sem rolar, a lista mostra de `Sky Village` a `Star Town`.
# Procurar o template sem rolar nunca acha, e desistir em 3 tentativas é o
# comportamento de `clicar_link`. Logo: rolar é um PASSO, não um detalhe.
#
# E a rolagem tem de ser conferida pelo APARECIMENTO DO LINK, nunca por um número
# fixo de cliques na seta -- clique cego na seta é exatamente o vício do bot Lua
# (`miniMapMinimize`: 5 cliques de 500 ms, incondicional, toda run).
DESTINO_DO_TRANSPORTE = "West Suburb of Stone City"

# O NPC que o painel de arredores encontra depois do teleporte. Ele fica em
# (-358, -288); é o pathfinding do JOGO que caminha até lá, e é por isso que não
# existem waypoints medidos deste trecho -- não precisam existir.
NPC_PARA_BUSCAR = ("Mutual", "Mutual Quest Woman")
POSICAO_DA_MUTUAL = (-358, -288)

# A COORDENADA DE CONVERSA. Daqui o personagem fica de frente para o NPC da
# entrada.
#
# O painel de arredores caminha até PERTO (aceita folga por construção), e clicar
# de onde ele largar é o defeito já medido na BC em 25/08/2026: a 2 passos, o
# clique do NPC caiu no White Eagle que estava no caminho, o diálogo não abriu, e
# a rotina concluiu a coisa errada. Então: **não se clica de fora do ponto.**
#
# MEDIDA NA TELA em 03/09/2026, e não mais ditada de memória: o rótulo do canto
# superior direito do print da entrada (`data/templates/entrada/completa2.png`,
# com o diálogo do Elite Axe Monk Soldier aberto) diz
# `Black Wind Camp Dungeon [-342,-288]`.
#
# CONFIRMAÇÃO CRUZADA: o bot Lua usa `entrance = {-342, -286}`, a 2 unidades
# daqui. A medição da tela e o bot que roda hoje concordam.
PONTO_DA_ENTRADA = (-342, -288)

# O ponto de onde se vende, no `Roaming Apothecary`.
#
# É O MESMO DA ENTRADA, e isso não é preguiça: o print do usuário mostra o
# personagem parado ali com o vendedor logo abaixo dele e o NPC da cave acima,
# na escada. Um waypoint serve para as duas coisas.
#
# SEPARADO NUM NOME PRÓPRIO de propósito. Se o clique no vendedor começar a cair
# no chão, é ESTE número que se remede -- e mexer nele não pode mexer na
# entrada, que já está confirmada por duas fontes.
PONTO_DA_VENDA = PONTO_DA_ENTRADA

# Folga aceita para considerar que já se está no ponto de conversa.
PRECISAO_NO_PONTO_DA_ENTRADA = 1.5

# O NPC com quem se fala para entrar na cave.
NPC_DA_ENTRADA = "Elite Axe Monk Soldier"

# O vendedor, do lado de FORA da cave. Nível 30.
#
# É a venda da BC com outro NPC: a janela é a mesma (mesma moldura, mesma grade,
# mesma paginação 1/3, mesmo par Sell/Cancel), então a máquina de vender vale sem
# alteração -- muda o texto de busca e o link. Por isso isto é dado de rota, e
# não um módulo de venda novo.
NPC_VENDEDOR = ("Roaming", "Roaming Apothecary")

# Ponto de spawn DENTRO da cave, logo depois de entrar.
#
# Vem do Lua (`insidexY = {55, 33}`) e NÃO foi conferido na tela. É por ele que o
# bot reconhece "já estou dentro" sem tentar entrar de novo -- o mesmo papel do
# `SITUAR` da BC. Enquanto não for medido, quem usar isto trata como indício e
# confirma pela caixa da cave, não como igualdade exata.
CHEGADA_NA_HH = (55, 33)


# ---------------------------------------------------------------------------
# Os quatro bosses
# ---------------------------------------------------------------------------
#
# Os RÓTULOS vêm dos comentários do `hh.lua`. **Eles NÃO estão medidos**: o bot
# Lua nunca compara nome de alvo, então nenhum destes nomes foi lido do jogo. O
# usuário confirmou que são os certos, então entram como ESPERADO e a leitura de
# `TargetHybrid` confirma no primeiro contato. Divergência é log, nunca bloqueio.

BOSS_1 = "Fa-Yuan"
BOSS_2 = "Dupla"              # dois bosses juntos
BOSS_3 = "Green Robmaster"
BOSS_4 = "Purple"             # o último

# "Vários", quando o ponto não tem um número fixo de alvos.
#
# É o caso dos pontos de MOB RANGED: o que espera lá é um punhado deles, e a
# luta acaba quando a flag de combate baixa, não quando um alvo conhecido morre.
VARIOS = -1

# ONDE A AoE NÃO FUNCIONA, e por quê.
#
# Regra do usuário, 03/09/2026: *"no primeiro boss e no 3 (Green Robmaster) tem
# mobs ranged, então o AOE não irá funcionar, de resto pode usar o AOE sem
# problemas"*. A skill de área do bot é de curta distância; mob ranged fica
# parado longe atirando, e a área passa embaixo dele sem tocar em nada.
#
# Não é economia de tecla: girar AoE contra quem está fora do alcance é gastar
# o tempo da rotação sem dano nenhum, e a luta se arrasta até o teto.
PONTOS_SEM_AOE: frozenset[str] = frozenset({BOSS_1, BOSS_3})


# ONDE OS MOBS BLOQUEIAM A PASSAGEM.
#
# Vem do bot em Lua, e ele para nesse ponto em dois lugares diferentes:
# `travel.lua` (*"em 232,188 matando os mobs que bloqueiam"*) e `hh.lua`
# (*"ataca mobs em 232,188 até não ter alvo, depois senta"*).
#
# NÃO É O MESMO QUE `WAYPOINTS_PROBLEMATICOS`: aquele alarga a tolerância de
# chegada de pontos onde a geometria não deixa encostar. Este é sobre MOBS.
#
# A DIFERENÇA CONTRA O LUA, e ela é medida: ele mata ali sempre que está a pé,
# porque não lê a flag de combate. Nós lemos -- então só paramos se o combate
# JÁ começou, e o ponto não custa nada na volta em que está limpo, que é a
# maioria delas.
WAYPOINTS_QUE_BLOQUEIAM: tuple[tuple[int, int], ...] = ((232, 188),)


def bloqueia_a_passagem(pos: tuple[int, int]) -> bool:
    """Este waypoint é um dos que costumam ter mob barrando o caminho?"""
    return tuple(pos) in WAYPOINTS_QUE_BLOQUEIAM


def usa_aoe(rotulo: str) -> bool:
    """A skill de área serve neste ponto?"""
    return rotulo not in PONTOS_SEM_AOE


def e_pacote_de_mobs(rotulo: str) -> bool:
    """O ponto é um PACOTE de mobs, e não um boss (ou dois) conhecido?

    Muda o RITUAL da luta inteiro. Num boss vale `lutar_contra_um_boss`: espera
    o engajamento, bate, e sair de combate é a vitória. Num pacote vale
    `limpar_o_combate`: mata um, PARA e olha a flag, e só então TAB para o
    próximo -- porque o que encerra é a lista acabar, e cada morte pode ou não
    ser a última.
    """
    return ALVOS_POR_PONTO.get(rotulo, 1) == VARIOS


# QUANTOS ALVOS tem cada ponto de boss.
#
# O `hh.lua` chama o segundo de "Dupla" e o comentário diz "dupla de boss" --
# são DOIS no mesmo ponto. Isso muda o combate: matar o primeiro não encerra a
# luta, e sem um TAB depois da morte o segundo nunca é adquirido. É o mesmo
# mecanismo que a fase dos guardas da Bewitcher Cave usa
# (`combate.TABS_NOS_GUARDAS`).
#
# Um por ponto é o normal, e aí o TAB não sai -- trocar de alvo no meio da luta
# de um boss único seria perder dano.
ALVOS_POR_PONTO: dict[str, int] = {
    # MOBS RANGED, em número indeterminado -- medido pelo usuário no jogo em
    # 03/09/2026. O rótulo "Fa-Yuan" veio do comentário do bot em Lua e ficou
    # como NOME DO PONTO; o que espera lá não é um boss único.
    BOSS_1: VARIOS,
    BOSS_2: 2,
    # Idem: o "Green Robmaster" do Lua é um ponto de mobs ranged.
    BOSS_3: VARIOS,
    BOSS_4: 1,
}

# Quantos TABs dar depois de cada morte, num ponto com mais de um alvo.
#
# DOIS e não um: o primeiro pode pegar o cadáver que ainda está selecionado. É o
# mesmo motivo de `TABS_NOS_GUARDAS` ser 3 para quatro Gun Witch.
TABS_ENTRE_OS_ALVOS_DO_PONTO = 2

# Orçamento de TAB num ponto de PACOTE (número indeterminado de mobs).
#
# NÃO É TETO -- `combate.TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS` mantém a troca
# liberada enquanto a flag de combate estiver alta. Este número é o PISO que
# liga o ramo de "morreu, troca de alvo" dentro do laço de ataque; quem encerra
# a fase é a saída de combate, não a contagem.
#
# Vale o mesmo `2` da Dupla de propósito: um piso maior não compra nada (a flag
# já libera), e um piso zero desligaria a troca -- que é justamente o defeito
# que a mudança de 06/09/2026 corrigiu.
TABS_NO_PACOTE = TABS_ENTRE_OS_ALVOS_DO_PONTO


def tabs_ao_morrer(rotulo: str) -> int:
    """Quantos TABs dar depois de uma morte, neste ponto de boss.

    =====================================================================
    O ZERO É DECISÃO, E O NÃO-ZERO TAMBÉM
    =====================================================================

    `0` para ponto de UM ALVO SÓ: TAB no meio da luta de um boss único troca o
    alvo e perde dano. Não há para quem trocar.

    `TABS_ENTRE_OS_ALVOS_DO_PONTO` para o ponto de DOIS (a "Dupla"): sem ele o
    segundo boss nunca é adquirido.

    `TABS_NO_PACOTE` para ponto de VÁRIOS (os pontos de mob ranged). Aqui era
    `0` até 06/09/2026, porque quem dava o TAB era `limpar_o_combate` -- que
    PARA três segundos depois de cada morte antes de trocar.

    Essa parada saiu (ver `HHRoutine._matar_ate_sair_de_batalha`): a regra do
    usuário para a HH é bater e trocar de alvo ININTERRUPTAMENTE até a flag de
    combate cair. Com o TAB de volta ao laço de ataque, a morte dispara a troca
    na leitura seguinte -- sem pausa, e sem parar de bater.

    O ORÇAMENTO NÃO É TETO enquanto a flag estiver alta: ver
    `combate.TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS`. Ele é o piso que LIGA o ramo
    de troca por morte; quem encerra é a saída de combate.
    """
    alvos = ALVOS_POR_PONTO.get(rotulo, 1)
    if alvos == VARIOS:
        return TABS_NO_PACOTE
    return TABS_ENTRE_OS_ALVOS_DO_PONTO if alvos > 1 else 0

# ONDE O BOT PARA PARA LUTAR: o último waypoint do trecho correspondente.
#
# Não confundir com a coordenada do BOSS. Nos comentários do `hh.lua` o autor
# anotou "Boss 1: Fa-Yuan (273, 138)" e "Boss 2: Dupla (410, 135)", mas os
# trechos terminam 2,24 unidades antes -- em (271, 137) e (408, 136). Nos bosses
# 3 e 4 os dois valores coincidem.
#
# QUEM MANDA É O WAYPOINT, e a diferença tem explicação simples: a anotação é
# onde o boss ESTÁ, e o waypoint é de onde se bate nele. Usar a anotação como
# destino mandaria o bot tentar entrar dentro do boss, que é o tipo de clique
# que não produz movimento e acorda o detector de travamento sem haver trava.

# A anotação do bot Lua, guardada porque é a única pista de onde o boss está de
# verdade -- útil no dia em que a leitura de entidades por perto entrar na HH.
COORDENADA_ANOTADA_NO_LUA = {
    BOSS_1: (273, 138),
    BOSS_2: (410, 135),
    BOSS_3: (551, 192),
    BOSS_4: (527, 108),
}

# Depois de matar o boss 1, o bot volta a este ponto antes de seguir.
#
# NÃO É ATALHO, e o comentário do Lua explica por quê: *"a cave e sinuosa, o
# atalho direto pra 274,139 caia na parede e travava o char"* (`hh.lua:283`).
PONTO_DEPOIS_DO_BOSS_1 = (274, 139)

# Onde a Fada estaciona durante a luta do boss, no modo HH+Fada.
# Adicionado na V1.2 do bot Lua ("Adicionado posição fixa da fada no boss").
POSICAO_DA_FADA_NO_BOSS = (185, 133)


# ---------------------------------------------------------------------------
# Os waypoints
# ---------------------------------------------------------------------------
#
# Cada linha é `(x, y, área, clique_calibrado)`. O quarto item é o `via` do Lua:
# RESERVA, para quando o motor de navegação desistir. Ver `core/rota.py`.

_A = AREA_INTERNA_NAO_MEDIDA

# Da chegada dentro da cave até o boss 1 (Fa-Yuan).
CAMINHO_ATE_O_BOSS_1: tuple[Waypoint, ...] = _wp([
    (80, 42, _A, (943, 104)),
    (107, 47, _A, (945, 110)),
    (124, 49, _A, (935, 115)),
    (137, 69, _A, (931, 96)),
    (148, 83, _A, (930, 102)),
    (169, 83, _A, (939, 115)),
    (188, 104, _A, (937, 95)),
    (184, 138, _A, (915, 82)),
    (187, 171, _A, (922, 83)),
    (209, 182, _A, (940, 104)),
    (207, 186, _A, (924, 109)),
    (232, 188, _A, (941, 109)),
    (273, 191, _A, (958, 112)),
    (275, 172, _A, (921, 133)),
    (299, 174, _A, (942, 113)),
    (298, 204, _A, (918, 86)),
    (316, 205, _A, (936, 114)),
    (321, 165, _A, (924, 153)),
    (315, 140, _A, (913, 139)),
    (301, 142, _A, (906, 113)),
    (282, 139, _A, (901, 118)),
    (272, 136, _A, (908, 117)),
])

# Do boss 1 até o boss 2 (a dupla). Cliques calibrados manualmente.
CAMINHO_ATE_O_BOSS_2: tuple[Waypoint, ...] = _wp([
    (288, 139, _A, (930, 113)),
    (306, 140, _A, (936, 114)),
    (316, 142, _A, (929, 113)),
    (326, 136, _A, (929, 121)),
    (339, 130, _A, (931, 121)),
    (354, 134, _A, (933, 111)),
    (367, 136, _A, (931, 113)),
    (368, 154, _A, (920, 98)),
    (367, 173, _A, (918, 97)),
    (369, 189, _A, (921, 100)),
    (379, 190, _A, (929, 114)),
    (393, 184, _A, (932, 121)),
    (392, 164, _A, (918, 134)),
    (394, 150, _A, (921, 128)),
    (409, 150, _A, (933, 115)),
    (408, 131, _A, (918, 129)),
])

# Do boss 2 até o boss 3 (Green Robmaster).
CAMINHO_ATE_O_BOSS_3: tuple[Waypoint, ...] = _wp([
    (420, 136, _A, (929, 113)),
    (426, 138, _A, (935, 114)),
    (429, 152, _A, (921, 100)),
    (456, 152, _A, (955, 115)),
    (463, 170, _A, (915, 98)),
    (447, 172, _A, (904, 113)),
    (448, 204, _A, (920, 84)),
    (452, 221, _A, (923, 99)),
    (485, 219, _A, (951, 117)),
    (515, 212, _A, (948, 122)),
    (544, 196, _A, (947, 130)),
    (560, 183, _A, (934, 127)),
    (551, 192, _A, (910, 106)),
])

# Do boss 3 até o boss 4 (Purple). ANDA PARA TRÁS no começo: o trecho volta
# sobre o caminho do boss 3 antes de subir. Não é erro de medição.
CAMINHO_ATE_O_BOSS_4: tuple[Waypoint, ...] = _wp([
    (524, 207, _A, (893, 101)),
    (494, 215, _A, (890, 107)),
    (469, 220, _A, (895, 110)),
    (449, 214, _A, (900, 121)),
    (448, 174, _A, (918, 153)),
    (467, 171, _A, (937, 118)),
    (467, 152, _A, (919, 133)),
    (448, 146, _A, (901, 121)),
    (448, 131, _A, (919, 129)),
    (460, 108, _A, (930, 136)),
    (470, 108, _A, (930, 136)),
    (478, 108, _A, (936, 118)),
    (508, 108, _A, (948, 114)),
    (526, 108, _A, (936, 101)),
])

# Do boss 4 até o ponto de onde se sai da cave pelo NPC.
# O NPC QUE TIRA DA CAVE, e o que ele responde.
#
# MEDIDO pelo usuário em 03/09/2026, no print do ponto de saída: o diálogo se
# chama "Servant Child" e o texto é *"Don't beat me. I'm just a servant of here,
# if you want to leave here, I can help you..."*, com o link verde
# "Leave Happiness Hall".
#
# O bot em Lua não tem o nome: ele dá TRÊS cliques direitos às cegas em alturas
# diferentes (`farmer.exitCave`) porque não sabe ler a tela. Nós lemos.
NPC_DA_SAIDA = "Servant Child"

# DE ONDE SE FALA COM ELE. Remedido pelo usuário em 04/09/2026: era (529,119),
# passou a (527,124) porque dali a MONTARIA do personagem não fica na frente do
# NPC. O clique é posicional na cena 3D, então mover o ponto move o clique --
# os dois foram remedidos juntos (ver `coords.hh_exit_npc`).
PONTO_DA_SAIDA = (527, 124)

# COM QUE PRECISÃO É PRECISO ESTAR NELE ANTES DE CLICAR.
#
# A MESMA da porta da cave, e pelo mesmo motivo medido: clique posicional só
# vale a partir da coordenada. Aqui a consequência é pior que errar o clique --
# o usuário mediu em 04/09/2026 que **existe OUTRO NPC por perto**, e clicar de
# longe abre o diálogo dele; o personagem então caminha até esse outro NPC,
# saindo do ponto de onde o `Servant Child` é alcançável.
PRECISAO_NO_PONTO_DA_SAIDA = PRECISAO_NO_PONTO_DA_ENTRADA

# ONDE O PERSONAGEM APARECE DEPOIS DE SAIR.
#
# É o mesmo ponto da porta -- sair devolve o personagem para a frente da cave,
# que é o que faz a run seguinte começar sem viagem. O Lua confirma pelo mesmo
# par (`farmer.exitCave`: `local outside = {-342, -288}`).
PONTO_FORA_DA_HH = PONTO_DA_ENTRADA


CAMINHO_ATE_A_SAIDA: tuple[Waypoint, ...] = _wp([
    # ÚNICO WAYPOINT COM ÁREA MEDIDA: o print do usuário mostra
    # `Happiness Hall Main Hall` com o personagem aqui. O par exato mudou de
    # (529,119) para (527,124) em 04/09/2026 -- ver `PONTO_DA_SAIDA`.
    (*PONTO_DA_SAIDA, AREA_DA_SAIDA, (921, 104)),
])

# Os quatro trechos na ordem em que são percorridos, com o rótulo do boss que
# fecha cada um. É esta tupla que a rotina percorre -- e é ela que garante que
# adicionar um quinto boss é uma linha aqui, não um `if` novo na máquina de
# estados.
# O PONTO DE LUTA DE CADA TRECHO É O ÚLTIMO WAYPOINT DELE, e agora isso é
# DERIVADO em vez de declarado duas vezes.
#
# POR QUE DERIVADO, E NÃO DECLARADO (04 e 07/09/2026)
#
# Havia `POSICAO_DO_BOSS_1..4` escritos à mão, separados dos caminhos. Eles
# divergiram DUAS vezes quando o usuário ajustou waypoints no jogo:
#
#   04/09  um waypoint comentado deixou o ponto do trecho 1 apontando para uma
#          coordenada que já não existia na rota;
#   07/09  os ajustes de (271,137)->(272,136), (408,136)->(408,131) e
#          (527,108)->(526,108) deixaram três pontos 1,4 / 5,0 / 1,0 unidades
#          atrás do fim do caminho.
#
# NENHUMA DAS DUAS APARECEU COMO ERRO -- as diferenças cabiam na tolerância de
# chegada, então o sintoma era comportamento estranho no jogo, não exceção.
#
# Um número lido por dois lados mora num lugar só. O lugar é o CAMINHO: ele é o
# que o usuário edita quando remede a rota no jogo.
def _fim_do_caminho(caminho: tuple[Waypoint, ...]) -> tuple[int, int]:
    """O ponto de luta de um trecho: o último waypoint dele."""
    return caminho[-1].pos


TRECHOS_DOS_BOSSES: tuple[tuple[str, tuple[Waypoint, ...], tuple[int, int]], ...] = (
    (BOSS_1, CAMINHO_ATE_O_BOSS_1,
     _fim_do_caminho(CAMINHO_ATE_O_BOSS_1)),
    (BOSS_2, CAMINHO_ATE_O_BOSS_2,
     _fim_do_caminho(CAMINHO_ATE_O_BOSS_2)),
    (BOSS_3, CAMINHO_ATE_O_BOSS_3,
     _fim_do_caminho(CAMINHO_ATE_O_BOSS_3)),
    (BOSS_4, CAMINHO_ATE_O_BOSS_4,
     _fim_do_caminho(CAMINHO_ATE_O_BOSS_4)),
)


def _todos_os_waypoints() -> tuple[Waypoint, ...]:
    return (CAMINHO_ATE_O_BOSS_1 + CAMINHO_ATE_O_BOSS_2
            + CAMINHO_ATE_O_BOSS_3 + CAMINHO_ATE_O_BOSS_4
            + CAMINHO_ATE_A_SAIDA)


TODOS_OS_WAYPOINTS: tuple[Waypoint, ...] = _todos_os_waypoints()


# ---------------------------------------------------------------------------
# Os limites úteis do minimapa, e os dois cliques que fogem deles
# ---------------------------------------------------------------------------
#
# `travel.lua:37` recusa clique fora de 895..965 em X e 75..158 em Y, encurtando
# o passo pela metade até caber. Mas esse corte vale só para o clique CALCULADO:
# os `via` são calibrados à mão e passam por fora dele.
#
# DOIS dos 66 fogem da caixa, ambos no começo do trecho do boss 4 -- (893, 101) e
# (890, 107), os dois com X abaixo de 895. Não são erro de digitação: aquele
# trecho anda PARA TRÁS sobre o caminho do boss 3, e um passo para trás no
# minimapa cai à esquerda do centro.
#
# CONSEQUÊNCIA PRÁTICA: se algum dia o `via` for passado pelo mesmo corte do
# clique calculado, esses dois serão encurtados e deixarão de apontar para onde
# foram calibrados. O corte é para o cálculo; o `via` vai cru.
LIMITES_DO_MINIMAPA = ((895, 965), (75, 158))

VIA_FORA_DOS_LIMITES: tuple[tuple[int, int], ...] = (
    (893, 101),
    (890, 107),
)


# Waypoints onde o caminho fica bloqueado por mob, medidos na prática.
#
# (232, 188) é tratado como caso especial em DOIS lugares do bot Lua
# (`hh.lua:280` e `travel.lua:91`): é onde os mobs seguram o personagem e ele
# fica parado sem conseguir andar. O Lua resolve matando o que estiver ali.
WAYPOINTS_PROBLEMATICOS: tuple[tuple[int, int], ...] = (
    (232, 188),
)


# ---------------------------------------------------------------------------
# A caixa que envolve o interior da cave
# ---------------------------------------------------------------------------
#
# CALCULADA DOS WAYPOINTS, nunca digitada à mão -- mesma regra do `mapa_bc`:
# waypoint e caixa não podem divergir sem ninguém notar.

FOLGA_DA_CAIXA = 25


def _caixa_dos_waypoints() -> tuple[tuple[int, int], tuple[int, int]]:
    xs = [wp.x for wp in TODOS_OS_WAYPOINTS]
    ys = [wp.y for wp in TODOS_OS_WAYPOINTS]
    return ((min(xs) - FOLGA_DA_CAIXA, min(ys) - FOLGA_DA_CAIXA),
            (max(xs) + FOLGA_DA_CAIXA, max(ys) + FOLGA_DA_CAIXA))


CAIXA_DA_HH = _caixa_dos_waypoints()   # ((x min, y min), (x max, y max))


def posicao_esta_na_caixa_da_hh(pos: tuple[int, int] | None) -> bool:
    """A coordenada cai dentro do retângulo que envolve a cave inteira?"""
    if pos is None:
        return False
    (xmin, ymin), (xmax, ymax) = CAIXA_DA_HH
    return xmin <= pos[0] <= xmax and ymin <= pos[1] <= ymax


# QUÃO PERTO DE (55,33) AINDA CONTA COMO "ACABEI DE ENTRAR".
#
# A entrada sempre deposita no mesmo par -- é padrão do jogo, confirmado pelo
# usuário em 03/09/2026 -- e o log leu (55,34) um segundo depois. O primeiro
# waypoint da rota fica a 26 unidades (80,42), então qualquer régua abaixo disso
# separa "acabei de entrar" de "já estou andando pela cave".
#
# `rota.NA_ROTA` é a régua que o `core/rota.py` já usa para separar "escorreguei
# um pouco" de "saí da rota". É a mesma pergunta, e uma régua só evita
# divergência muda. Número novo, nenhum.
TOLERANCIA_DA_CHEGADA = rota.NA_ROTA


# ONDE A FAY DEPOSITA. Medido pelo usuário em 04/09/2026.
#
# NÃO É PORTÃO DE DECISÃO, e é por isso que fica só documentado: o usuário foi
# explícito -- *"é importante que se eu já tiver nessa localização você faça o
# dali pra frente, MESMO QUE O X E Y NÃO ESTEJA CERTO"*. Quem decide a etapa
# ali é o NOME do lugar; a coordenada varia porque o teleporte espalha.
CHEGADA_DA_FAY = (-255, -484)

# O CAMINHO ATÉ DE ONDE SE ABRE O PAINEL DE ARREDORES, depois do teleporte.
#
# Medido pelo usuário em 08/09/2026, e ele acrescentou o segundo ponto no mesmo
# dia: *"apos isso voce vai para as coordenadas X: -292, Y: -496, ai sim voce
# ira usar o Surroundings e filtrar pelo Mutual"*.
#
# POR QUE UM CAMINHO, E NÃO UM PONTO: o teleporte ESPALHA a chegada, e o painel
# de arredores é clique POSICIONAL -- abrir de onde o teleporte largou dá
# resultado diferente a cada run. E são DOIS porque um clique de minimapa
# alcança ~17,6 unidades (`zones.ALCANCE_DO_MINIMAPA`) e daqui até (-292,-496)
# há 25,3: trajeto longo em linha reta é onde o personagem encosta na geometria.
#
# LISTA ORDENADA de propósito: um terceiro ponto é uma linha de DADO aqui.
CAMINHO_ATE_OS_ARREDORES: tuple[tuple[int, int], ...] = (
    (-268, -488),
    (-292, -496),
)

# Com que precisão é preciso estar em cada um deles.
#
# FOLGADA de propósito, e diferente da precisão da porta (1,5): aqui o ponto não
# protege um clique na CENA 3D -- protege a abertura de um PAINEL, que não
# depende de onde exatamente o personagem está, só de ele estar na região certa
# do mapa. Apertar aqui custaria tentativas de reposicionamento por nada.
PRECISAO_PARA_ABRIR_OS_ARREDORES = 12


# ===========================================================================
# EM QUE ETAPA DA VIAGEM O PERSONAGEM ESTÁ
# ===========================================================================
#
# A pergunta é "de onde eu continuo", e ela tem de ser respondida por NOME E
# COORDENADA juntos -- regra do usuário, 04/09/2026: *"é importante verificar a
# localização por ponteiro e a coordenada por ponteiro, fazer a verificação
# dupla para saber onde está e de onde deve começar o bot, pois tem coisas que
# não fazem sentido dependendo da localização"*.
#
# POR QUE NENHUM DOS DOIS BASTA SOZINHO:
#
#   * O NOME NÃO SEPARA DENTRO DE FORA. Medido no log de 03/09/2026:
#     `Memory.location()` devolve `Black Wind Camp Dungeon` tanto em (-343,-288)
#     quanto em (55,33). Em 673 menções do log é a única string. Os nomes
#     `Happiness Hall Dungeon` e `Happiness Hall Main Hall` que aparecem no
#     canto da TELA não são o que o ponteiro devolve.
#   * A COORDENADA NÃO SEPARA AS ETAPAS DE FORA. West Suburb e a vizinhança da
#     cave são regiões distintas do mundo, e o teleporte da Fay espalha o ponto
#     de chegada -- por isso o usuário mandou decidir por nome ali.
#
# A DIVISÃO DE TRABALHO, então: a COORDENADA responde "dentro ou fora" (é a
# leitura que nunca falhou em nenhum log, inclusive nos episódios de nome
# preso), e o NOME responde "quão longe da cave eu estou, do lado de fora".

ETAPA_DENTRO = "dentro da cave"
ETAPA_NA_PORTA = "na porta da cave"
ETAPA_NA_VIZINHANCA = "já passei do teleporte"
ETAPA_LONGE = "longe, viagem completa"

# Os lugares de onde NÃO é preciso usar a Fay -- o personagem já está do outro
# lado do teleporte e o painel de arredores alcança a cave.
#
# `West Suburb of Stone City` é onde a Fay deposita; `Outside Black Wind Camp`
# fica mais perto ainda. Os dois levam à MESMA ação (arredores → NPC da porta),
# e é por isso que são uma lista e não dois ramos.
LUGARES_DEPOIS_DO_TELEPORTE: frozenset[str] = frozenset({
    DESTINO_DO_TRANSPORTE,   # "West Suburb of Stone City"
    GRUPO_DOS_ARREDORES,     # "Outside Black Wind Camp"
})

# Quão perto da porta ainda conta como "estou nela".
#
# Generoso de propósito, e diferente de `PRECISAO_NO_PONTO_DA_ENTRADA` (1,5):
# esta régua responde *"preciso viajar?"* e aquela responde *"posso clicar?"*.
# Sair da cave devolve o personagem PERTO da porta, não nela -- então 30
# unidades evitam uma viagem inteira, e o ajuste fino de coordenada fica com
# `garantir_coordenada_da_entrada`, que é quem clica.
RAIO_DA_PORTA = 30


def etapa_pelo_lugar(nome: str | None,
                     pos: tuple[int, int] | None) -> str:
    """De onde o bot continua, lendo NOME e COORDENADA juntos.

    A ORDEM DAS PERGUNTAS É A DECISÃO. A coordenada vem primeiro porque a
    implicação é lógica, não estatística: estar na caixa da instância PROVA que
    o personagem está dentro, e nenhum nome desmente isso.

    `ETAPA_LONGE` é o padrão, e é o desfecho seguro: manda fazer a viagem
    inteira, que funciona de qualquer lugar. Um nome desconhecido (`Wei's
    Village`, `Bothy`, um mapa novo) cai aqui, e "não sei" custa uma viagem --
    nunca um clique no lugar errado.
    """
    if posicao_esta_na_caixa_da_hh(pos):
        return ETAPA_DENTRO

    if pos is not None and distancia(pos, PONTO_DA_ENTRADA) <= RAIO_DA_PORTA:
        return ETAPA_NA_PORTA

    # DAQUI PARA BAIXO QUEM DECIDE É O NOME. A coordenada já provou que o
    # personagem não está dentro nem na porta; o que falta é saber se ele já
    # passou do teleporte -- e isso a coordenada não diz, porque a Fay espalha
    # o ponto de chegada.
    if nome in LUGARES_DEPOIS_DO_TELEPORTE:
        return ETAPA_NA_VIZINHANCA

    return ETAPA_LONGE


def acabei_de_entrar(pos: tuple[int, int] | None) -> bool:
    """O personagem está no ponto onde a entrada deposita?

    É o portão do PREPARO COMPLETO. Regra do usuário, 04/09/2026: *"as
    verificações são somente na entrada da cave, se tiver no meio da cave não
    deve ser verificado nada, então só naquele waypoint inicial você faz as
    verificações e usa os buffs"*.
    """
    if pos is None:
        return False
    return distancia(pos, CHEGADA_NA_HH) <= TOLERANCIA_DA_CHEGADA


def esta_dentro_da_hh(pos: tuple[int, int] | None) -> bool:
    """Dentro da cave, pelo SINAL DA COORDENADA.

    É a mesma regra que o bot Lua usa, e ela é forte aqui: fora da cave o X e o Y
    são NEGATIVOS (a entrada é (-342, -288), o vendedor fica por ali); dentro,
    ambos são positivos. `if ptr.getX() > 0 and ptr.getY() > 0` aparece em três
    lugares do `farmer.lua` e é como ele reconhece que reviveu dentro da cave e
    não deve tentar entrar de novo.

    NÃO É "estou na HH" absoluto -- coordenada de jogo não é única no mundo.
    Serve para os lugares que esta rotina pisa, e sempre junto com o nome do
    lugar ou com a última transição conhecida.
    """
    if pos is None:
        return False
    return pos[0] > 0 and pos[1] > 0


# ---------------------------------------------------------------------------
# Retomada de rota -- a REGRA mora em `core/rota.py`; aqui só os dados da HH
# ---------------------------------------------------------------------------
#
# O par abaixo é o espelho de `mapa_bc.onde_retomar` / `tolerancia_do_waypoint`, e
# é assim que a HH usa o mesmo motor de rota da BC sem importar nada dela.
#
# A DIFERENÇA CONTRA A BC, E ELA É DE PROPÓSITO: aqui NÃO se passa
# `areas_apertadas` nem `area_da_posicao`. As áreas internas desta cave não foram
# medidas (ver o cabeçalho do módulo), e o recuo "volte ao início da área" só faz
# sentido quando se sabe onde a área começa. Sem esse dado, a retomada volta ao
# waypoint mais próximo -- que é o comportamento certo -- em vez de agir sobre um
# nome que é marcador.
#
# Quando a área for medida, é aqui que ela entra, e o motor não muda.


def onde_retomar(
    pos: tuple[int, int] | None,
    caminho: tuple[Waypoint, ...],
    indice_esperado: int = 0,
) -> Retomada:
    """Por qual waypoint a rota deve continuar. Ver `core.rota.onde_retomar`."""
    return rota.onde_retomar(pos, caminho, indice_esperado)


def houve_rollback(
    indice_atual: int,
    pos: tuple[int, int] | None,
    caminho: tuple[Waypoint, ...],
    folga: int = 1,
) -> int | None:
    """O personagem voltou muito na rota? Ver `core.rota.houve_rollback`."""
    return rota.houve_rollback(indice_atual, pos, caminho, folga)


def tolerancia_do_waypoint(wp: Waypoint, base: int, apertada: int) -> int:
    """Tolerância de chegada, maior nos waypoints onde os mobs seguram o char.

    A HH não tem área apertada declarada -- tem o ponto (232, 188), onde o bot
    Lua trata bloqueio de mob em dois lugares distintos.
    """
    return rota.tolerancia_do_waypoint(
        wp, base, apertada, problematicos=WAYPOINTS_PROBLEMATICOS)


def como_lista(caminho: tuple[Waypoint, ...]) -> list[tuple[int, int]]:
    """Só as coordenadas, para quem não precisa da área."""
    return rota.como_lista(caminho)


def area_medida() -> bool:
    """TODAS as áreas internas já foram medidas?

    Existe para que quem depende da área PERGUNTE em vez de descobrir na hora
    errada. Enquanto isto devolver False, a `Waypoint.area` da HH é um marcador
    na maioria dos pontos -- ver o cabeçalho do módulo.

    RESPONDE PELO CONJUNTO, e não ponto a ponto, porque é assim que ela é usada:
    o recuo "volte ao começo da área" só faz sentido quando se sabe onde CADA
    área começa. Um nome medido no meio de 64 marcadores não muda isso.
    """
    return all(wp.area != AREA_INTERNA_NAO_MEDIDA for wp in TODOS_OS_WAYPOINTS)


def areas_medidas() -> dict[tuple[int, int], str]:
    """Os waypoints cuja área foi MEDIDA, e o nome de cada um.

    É o inventário do que já se sabe, para o teste travar e para quem for medir
    o resto saber por onde continuar.
    """
    return {wp.pos: wp.area for wp in TODOS_OS_WAYPOINTS
            if wp.area != AREA_INTERNA_NAO_MEDIDA}


__all__ = [
    "AREA_DA_SAIDA",
    "AREA_INTERNA_NAO_MEDIDA",
    "BOSS_1",
    "BOSS_2",
    "BOSS_3",
    "BOSS_4",
    "CAIXA_DA_HH",
    "CAMINHO_ATE_A_SAIDA",
    "CAMINHO_ATE_OS_ARREDORES",
    "CAMINHO_ATE_O_BOSS_1",
    "CAMINHO_ATE_O_BOSS_2",
    "CAMINHO_ATE_O_BOSS_3",
    "CAMINHO_ATE_O_BOSS_4",
    "CHEGADA_DA_FAY",
    "CHEGADA_NA_HH",
    "COORDENADA_ANOTADA_NO_LUA",
    "DESTINO_DO_TRANSPORTE",
    "ETAPA_DENTRO",
    "ETAPA_LONGE",
    "ETAPA_NA_PORTA",
    "ETAPA_NA_VIZINHANCA",
    "FOLGA_DA_CAIXA",
    "GRUPO_DOS_ARREDORES",
    "LIMITES_DO_MINIMAPA",
    "LUGARES_DEPOIS_DO_TELEPORTE",
    "LUGAR_FORA_DA_HH",
    "NPC_DA_ENTRADA",
    "NPC_DA_SAIDA",
    "NPC_DE_TRANSPORTE",
    "NPC_PARA_BUSCAR",
    "NPC_VENDEDOR",
    "PONTO_DA_ENTRADA",
    "PONTO_DEPOIS_DO_BOSS_1",
    "PONTO_FORA_DA_HH",
    "POSICAO_DA_FADA_NO_BOSS",
    "POSICAO_DA_MUTUAL",
    "PRECISAO_NO_PONTO_DA_ENTRADA",
    "PRECISAO_PARA_ABRIR_OS_ARREDORES",
    "RAIO_DA_PORTA",
    "ROTULO_DE_TELA_DA_CHEGADA",
    "TODOS_OS_WAYPOINTS",
    "TRECHOS_DOS_BOSSES",
    "VIA_FORA_DOS_LIMITES",
    "WAYPOINTS_PROBLEMATICOS",
    "Waypoint",
    "acabei_de_entrar",
    "area_medida",
    "areas_medidas",
    "como_lista",
    "distancia",
    "esta_dentro_da_hh",
    "etapa_pelo_lugar",
    "posicao_esta_na_caixa_da_hh",
]
