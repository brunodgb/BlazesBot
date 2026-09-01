"""
Mapa da Bewitcher Cave: waypoints medidos no jogo, com o nome da área de cada um.

=========================================================================
POR QUE O CAMINHO MORA NO CÓDIGO E NÃO NA CONFIGURAÇÃO
=========================================================================

O caminho da cave é PROPRIEDADE DO JOGO, não preferência de quem usa. Não existe
tela para editá-lo e não faz sentido existir: um waypoint errado não deixa o bot
"mais lento", ele faz o personagem bater na parede da pirâmide do Secret Altar
até o tempo estourar.

Enquanto ele morava no `config.json`, um caminho antigo gravado numa execução
anterior continuava sendo usado depois de o caminho certo ser medido -- e era
impossível perceber, porque tudo parecia configurado. Foi o que aconteceu: o
config guardava os 38 waypoints herdados do T-R0XX, de outra época, enquanto os
57 medidos no jogo naquele momento estavam só na documentação.

Agora o código é a única fonte. Trocar de caminho é editar este arquivo, e todas
as contas passam a usar o novo na hora.

=========================================================================
O QUE A ÁREA DE CADA WAYPOINT RESOLVE
=========================================================================

A cave é dividida em áreas com nome próprio (Centipede Zone, Man-eater Tribe,
Bloodsucker Zone, Skull Tomb, Secret Altar, Secret Cemetery). Guardar a área
junto do waypoint dá três coisas que coordenada sozinha não dá:

  1. CONFERIR onde o bot está. A memória diz "Secret Altar"; o waypoint atual
     também diz "Secret Altar". Se discordarem, algo saiu do roteiro.
  2. Saber onde está SEM a memória. Quando a leitura do nome do lugar falha --
     e ela já falhou duas vezes em produção -- a coordenada ainda diz a área.
  3. Reagir a lag e rollback. Voltando a uma coordenada anterior, o bot descobre
     em que área caiu e retoma pelo waypoint certo daquela área, em vez de
     insistir num destino do outro lado da cave.

=========================================================================
O SECRET ALTAR É DIFERENTE
=========================================================================

O Secret Altar é uma pirâmide: tem escadas, e o caminho é ESTREITO. Clicar num
ponto qualquer lá dentro não produz movimento -- o jogo recusa o trajeto. Os
waypoints daquele trecho foram medidos passo a passo justamente por isso, e é
por isso que a retomada de rota dentro dele volta ao começo da área em vez de
tentar um atalho: atalho ali não existe.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...core.lugares import AREAS_BC
from ...core.rota import Waypoint, distancia
from ...core.rota import montar as _wp

# ---------------------------------------------------------------------------
# Pontos de referência
# ---------------------------------------------------------------------------

# Coordenada da ENTRADA da cave, em Ghost Din Woods, ao lado do Skull Herald.
# É o único lugar de onde a entrada pode ser tentada.
ENTRADA_EM_GHOST_DIN = (1395, -635)

# Onde o personagem aparece ao entrar na instância. Serve de confirmação: se a
# posição saltou para perto daqui, entrou -- mesmo que o nome do lugar não leia.
CHEGADA_NA_CAVE = (423, 53)

# Último waypoint antes de clicar no Altar Stone. Chegar AQUI é pré-requisito:
# o clique no Altar Stone é posicional e SÓ acerta a partir deste ponto.
#
# "Só a partir deste ponto" é literal, e a rota não garantia isso sozinha: o
# Secret Altar é área apertada, e nela `seguir_rota` aceita 8 unidades de folga
# (`TRICKY_TOLERANCE`). Chegar a 8 unidades daqui é chegar num lugar de onde o
# clique não funciona. Por isso existe a aproximação de precisão em
# `routine._do_entrar_no_covil`, com a tolerância abaixo.
ULTIMO_ANTES_DO_ALTAR = (218, 45)

# Quão perto de (220,43) o clique no Altar Stone ainda acerta.
#
# ESTE NÚMERO JÁ FOI 3, E 3 TRAVOU A RUN. O erro vale registrado porque é fácil de
# repetir: (220,43) está em `WAYPOINTS_PROBLEMATICOS` -- ou seja, está medido que o
# personagem NÃO consegue encostar nele --, e a navegação alarga a tolerância de
# chegada para `TRICKY_TOLERANCE` justamente ali. Então:
#
#     `goto((220,43), tolerance=3)`  devolvia True a 5,4 unidades
#     `na_posicao_de_clicar(..., 3)` recusava as mesmas 5,4 unidades
#
# Um lado dizia "cheguei", o outro dizia "não cheguei", sobre o mesmo ponto e o
# mesmo instante. Laço garantido, e o log mostrou seis falhas seguidas em um
# segundo. Aparece assim:
#
#     17:15:38  waypoint 1/1 alcançado | posição (213, 43)
#     17:15:38  Estou em (213, 43), a 5 unidades — longe demais para clicar
#
# A LIÇÃO: a tolerância do clique não pode ser escolhida à parte da tolerância de
# chegada do MESMO waypoint. Então ela não é escolhida -- é DERIVADA. Ver a função
# abaixo, que consulta a mesma `tolerancia_do_waypoint` que a navegação usa.
#
# E a evidência empírica está do lado da folga: com 10 a 12 unidades o portal
# abria e as runs entravam no covil. O que resolve o clique que não pega não é
# exigir precisão que a geometria não permite -- é o vai-e-volta por (231,45).
# Precisão EXIGIDA para o clique no Altar Stone acontecer.
#
# Mora AQUI, e não em quem usa, pela mesma lição da `tolerancia_do_altar()` logo
# abaixo: quem ANDA até o ponto (`routine._encostar_exato_no_patamar`) e quem
# CONFERE antes de clicar (`ui_service.entrar_no_covil_do_boss`) precisam ler o
# mesmo número por construção. Dois números escolhidos à parte foi exatamente o
# que travou a run no incidente da tolerância 3.
#
# No espaço de coordenadas INTEIRAS, qualquer valor < 1 só aceita a posição
# exata -- 1 já deixaria (217,45) passar. 0.9 é < 1 e não cola no float da
# leitura.
#
# ESTE NÚMERO É UM PORTÃO, NÃO UM CONSELHO: medido no log de dev, TODA entrada
# que abriu o diálogo aconteceu com o personagem exatamente em (218,45), e
# nenhuma das 11 tentativas fora do ponto abriu. Estar exato não BASTA (26
# falhas no ponto certo), mas fora dele não se tenta.
PRECISAO_NO_PATAMAR_DO_ALTAR = 0.7


def tolerancia_do_altar() -> int:
    """A MESMA tolerância que a navegação usa para chegar em (218,45).

    Função e não constante porque o valor depende de `TRICKY_TOLERANCE`, que mora
    no módulo de navegação -- e importar navegação aqui criaria ciclo. Resolvendo
    na chamada, os dois lados leem o mesmo número por construção.
    """
    from .navigation import TOLERANCIA_ROTA, TRICKY_TOLERANCE

    return tolerancia_do_waypoint(
        Waypoint(*ULTIMO_ANTES_DO_ALTAR, "Secret Altar"),
        TOLERANCIA_ROTA, TRICKY_TOLERANCE,
    )

# Ponto do VAI-E-VOLTA que destrava o clique no Altar Stone.
#
# Acontece de o personagem estar em (218,45) e o Altar Stone não responder ao
# clique. Sair para cá, esperar, e voltar resolve -- é o mesmo tipo de problema do
# waypoint 43 da travessia: o que trava não é a distância, é o estado em que o
# cliente/servidor deixou o personagem naquele ponto. Mudar de lugar e voltar
# refaz esse estado.
PONTO_PARA_DESENCALHAR_O_ALTAR = (231, 45)

# Quanto esperar no ponto de vai-e-volta antes de retornar.
SEGUNDOS_DESENCALHANDO_O_ALTAR = 3

# Onde o personagem aparece dentro do covil do boss.
CHEGADA_NO_COVIL = (187, -405)

# Onde os quatro mobs de guarda são mortos, antes de encostar no boss.
POSICAO_DOS_GUARDAS = (104, -406)

# Onde a luta contra o boss acontece.
POSICAO_DO_BOSS = (80, -406)

# Onde fica o Skull Herald que tira o personagem da cave.
POSICAO_DA_SAIDA = (81, -398)

# Precisão EXIGIDA no ponto da saída, e ela é UMA SÓ.
#
# TERCEIRA VEZ que este erro aparece, e as duas anteriores estão documentadas
# logo acima (`PRECISAO_NO_PATAMAR_DO_ALTAR`) e logo abaixo
# (`PRECISAO_NO_PONTO_DO_VENDEDOR`): quem ANDA até o ponto e quem CONFERE antes
# de clicar liam números DIFERENTES, escolhidos à parte.
#
#     `_do_sair` .............. andava só se `distancia > 8`
#     `na_posicao_de_clicar` .. clicava se `distancia <= 12` (o default)
#
# E o detalhe que transformou isso em falha intermitente: o waypoint do boss
# (80,-406) fica a **8,06 unidades** daqui. Os 8 do portão passavam 0,06 unidades
# ABAIXO dessa distância.
#
#   * parado exatamente no waypoint do boss -> 8,06 > 8 -> ANDA, e sai da cave;
#   * tendo derivado 1-2 unidades na luta, ex. (84,-405) -> 7,62 -> NÃO anda,
#     e 7,62 <= 12 -> CLICA assim mesmo, de um lugar de onde o clique não pega.
#
# Ou seja: funcionava ou não conforme onde a luta do boss terminasse, sem
# nenhuma mudança de código. Medido no `logs/dev/blazes-dev.jsonl` de
# 13/08/2026: personagem em (84,-405), clique direito em (616,326) repetido, o
# diálogo nunca abrindo, `Não saí da cave (falha 2168)` e subindo.
#
# < 1 para que, no espaço de coordenadas inteiras, só a célula exata passe --
# mesma escolha dos outros dois pontos, e pelo mesmo motivo: as coordenadas de
# tela do `cave_exit_npc` foram medidas COM o personagem em (81,-398).
PRECISAO_NO_PONTO_DA_SAIDA = 0.7

# Orçamento para encostar no ponto da saída. Mesmo desenho do patamar do Altar
# Stone: o passo real é de 1 a 2 unidades e leva 1 a 2 s, e o trecho aqui é
# curto (8 unidades desde o waypoint do boss).
TENTATIVAS_DE_ENCOSTAR_NA_SAIDA = 6
SEGUNDOS_POR_TENTATIVA_NA_SAIDA = 1.8

# Coordenada do NPC Transport Fay, em Stone City.
POSICAO_DA_FAY = (178, -518)

# Precisão exigida no ponto da Fay, e por que ela existe.
#
# ===========================================================================
# O DEFEITO MEDIDO, 25/08/2026 -- COM PRINT
# ===========================================================================
#
# O bot parava onde o auto-path do painel de arredores largasse (no print,
# `Stone City [180,-516]`, uns 2 passos antes) e clicava no ponto GENÉRICO de
# NPC da tela. De lá, esse ponto caía no **White Eagle** que estava no caminho:
#
#   1. o clique direito pega o White Eagle em vez da Fay -> diálogo não abre
#   2. `viajar_para_ghost_din_woods` devolve False
#   3. a rotina conclui "não estou em Stone City" e USA O ITEM DE RETORNO
#      -> desmonta, usa (já estava em Stone City: nada acontece), remonta
#   4. tenta de novo, o painel leva os 2 passos que faltavam, e aí funciona
#
# Palavras do usuário: *"não deveria existir isso, deveria ir para a coordenada
# 178,-517, que é a configurada como coordenada onde pode clicar na Fay"*.
#
# É EXATAMENTE O QUE O VENDEDOR JÁ FAZIA. `travel_to_vendor` anda até o ponto
# medido e se recusa a clicar de fora dele -- *"o clique cairia no chão e o
# personagem andaria, piorando a tentativa seguinte"*. A Fay tinha a coordenada
# (esta constante, usada só pela ferramenta de amostragem e pelos testes) e não
# tinha o passo de encostar nela.
#
# 1.5 E NÃO 0.7 COMO O VENDEDOR, e a diferença é honestidade: o ponto do
# vendedor foi remedido pelo usuário junto com as coordenadas de tela do clique,
# então lá a célula exata é conhecida. Aqui a constante diz (178,-518) e o
# usuário falou em (178,-517) -- uma unidade de diferença que ninguém mediu de
# novo. 1.5 aceita as duas células e as vizinhas imediatas; apertar antes de
# remedir seria transformar um erro de uma unidade em run travada.
#
# COMO FECHAR ISSO: o `14-INSTRUMENTAR-CLIQUE` já tem o ponto "fay", que
# fotografa em volta do clique com o personagem parado aqui. Com a amostra, esta
# precisão desce para 0.7 e o ponto de tela deixa de ser o genérico.
PRECISAO_NO_PONTO_DA_FAY = 1.5

# Quantas tentativas de encostar no ponto da Fay antes de desistir.
#
# Mesmo desenho do vendedor e do patamar do Altar Stone: o passo real é de 1 a 2
# unidades, então faltando 2 ou 3 unidades bastam duas ou três tentativas.
TENTATIVAS_DE_ENCOSTAR_NA_FAY = 6
SEGUNDOS_POR_TENTATIVA_NA_FAY = 1.8

# Coordenada de onde o personagem PARA para falar com o NPC vendedor (Rich Man),
# em Stone City. Não é onde o NPC está -- é de onde o clique nele acerta.
#
# Era (153,-492); o usuário remediu e mudou para cá. As coordenadas de tela do
# `vendor_npc` foram medidas COM O PERSONAGEM AQUI, então as duas andam juntas:
# mexer nesta sem remedir aquela põe o clique na parede.
POSICAO_DO_VENDEDOR = (158, -494)

# Precisão EXIGIDA no ponto do vendedor, e ela é UMA SÓ.
#
# Mora aqui pela mesma lição de `PRECISAO_NO_PATAMAR_DO_ALTAR`: quem ANDA até o
# ponto (`VendorService.travel_to_vendor`) e quem CONFERE antes de clicar
# (`_open_npc`) precisam ler o mesmo número por construção. Antes eram dois --
# a chegada aceitava 4 unidades e o clique aceitava 12 --, e 12 unidades de
# folga é outro lugar, com o NPC girado na tela.
#
# < 1 para que, no espaço de coordenadas inteiras, só a célula exata passe.
PRECISAO_NO_PONTO_DO_VENDEDOR = 0.7


# ---------------------------------------------------------------------------
# Waypoints
# ---------------------------------------------------------------------------

# `Waypoint` e `_wp` (o `montar`) vivem em `core/rota.py` desde 01/09/2026: a
# chegada do ecossistema HH os transformou em modelo compartilhado, e um
# ecossistema não importa do outro. Os nomes continuam disponíveis AQUI para todo
# o código da BC que já os usa -- ver o cabeçalho de `core/rota.py`.


# Da entrada da cave até o Altar Stone. Medido no jogo, waypoint por waypoint.
CAMINHO_ATE_O_ALTAR: tuple[Waypoint, ...] = _wp([
    (407, 55, "Bewitcher Cave"),
    (397, 64, "Bewitcher Cave"),
    (382, 76, "Bewitcher Cave"),
    (373, 79, "Bewitcher Cave"),
    (360, 104, "Centipede Zone"),
    (350, 115, "Centipede Zone"),
    (338, 134, "Centipede Zone"),
    (332, 156, "Centipede Zone"),
    (322, 156, "Centipede Zone"),
    (312, 178, "Bewitcher Cave"),
    (296, 164, "Bewitcher Cave"),
    (277, 164, "Bewitcher Cave"),
    (259, 164, "Bewitcher Cave"),
    (242, 164, "Bewitcher Cave"),
    (227, 165, "Bewitcher Cave"),
    (208, 164, "Bewitcher Cave"),
    (194, 164, "Bewitcher Cave"),
    (177, 163, "Bewitcher Cave"),
    (162, 168, "Bewitcher Cave"),
    (143, 161, "Bewitcher Cave"),
    (132, 147, "Bewitcher Cave"),
    (120, 132, "Man-eater Tribe"),
    (111, 116, "Man-eater Tribe"),
    (108, 98, "Man-eater Tribe"),
    (97, 81, "Man-eater Tribe"),
    (82, 65, "Bewitcher Cave"),
    (86, 50, "Bewitcher Cave"),
    (99, 40, "Bewitcher Cave"),
    (104, 25, "Bewitcher Cave"),
    (120, 11, "Bewitcher Cave"),
    (128, 0, "Bloodsucker Zone"),
    (132, -4, "Bloodsucker Zone"),
    (146, -38, "Bloodsucker Zone"),
    (160, -74, "Bloodsucker Zone"),
    (170, -89, "Bewitcher Cave"),
    (188, -98, "Bewitcher Cave"),
    (204, -99, "Bewitcher Cave"),
    (224, -92, "Bewitcher Cave"),
    (231, -66, "Bewitcher Cave"),
    (254, -44, "Bewitcher Cave"),
    (282, -74, "Bewitcher Cave"),
    # Medido depois, para contornar a geometria antes do Skull Tomb. A reta de
    # (282,-74) direto para (344,-37) bate em parede: o cliente aceita o clique,
    # o personagem não sai do lugar e o detector de travamento dispara. Isso
    # aparece em TODAS as execuções dos logs, sempre neste mesmo waypoint:
    #   "sem progresso indo para (344, -37) (waypoint 43/57, distância 71)"
    # e a chegada custava 10.6s contra 2-3s dos vizinhos. Descer para y=-83
    # primeiro muda o ÂNGULO de aproximação -- a distância continua ~71, então o
    # que resolve não é encurtar o trecho, é sair de trás do obstáculo.
    (290, -83, "Bewitcher Cave"),
    (344, -37, "Skull Tomb"),
    (353, 5, "Skull Tomb"),
    (311, 51, "Secret Altar"),
    (276, 48, "Secret Altar"),
    (258, 49, "Secret Altar"),
    (258, 80, "Secret Altar"),
    (222, 80, "Secret Altar"),
    (190, 80, "Secret Altar"),
    (188, 44, "Secret Altar"),
    (200, 46, "Secret Altar"),
    (204, 40, "Secret Altar"),
    (204, 22, "Secret Altar"),
    (242, 22, "Secret Altar"),
    (238, 44, "Secret Altar"),
    (226, 44, "Secret Altar"),
    (220, 44, "Secret Altar"),
    (218, 45, "Secret Altar"),
])

# Dentro do covil, da chegada até o boss.
CAMINHO_ATE_O_BOSS: tuple[Waypoint, ...] = _wp([
    (183, -406, "Secret Cemetery"),
    (156, -406, "Secret Cemetery"),
    (156, -406, "Secret Cemetery"),   # repetido na medição; `_wp` remove
    (125, -406, "Secret Cemetery"),
    (104, -406, "Secret Cemetery"),
])

# Do ponto dos guardas até o boss. Separado porque no meio há uma luta.
CAMINHO_DOS_GUARDAS_AO_BOSS: tuple[Waypoint, ...] = _wp([
    (74, -406, "Secret Cemetery"),
])

# Do boss até o NPC de saída.
CAMINHO_DO_BOSS_A_SAIDA: tuple[Waypoint, ...] = _wp([
    (81, -398, "Secret Cemetery"),
])


# Áreas onde a geometria é apertada e a tolerância de waypoint precisa ser
# maior. O Secret Altar é uma pirâmide com escadas: encostar é o normal ali.
AREAS_APERTADAS = frozenset({"Secret Altar", "Man-eater Tribe"})

# Waypoints onde o personagem encosta com frequência, medidos na prática.
WAYPOINTS_PROBLEMATICOS: tuple[tuple[int, int], ...] = (
    (120, 132),    # entrada da Man-eater Tribe, corredor estreito
    (224, -92),    # curva fechada antes da subida
    (190, 45),     # base da escada do Secret Altar
    (205, 26),     # degrau intermediário
    (220, 43),     # patamar do Altar Stone
)


# ---------------------------------------------------------------------------
# Reconhecimento de onde o personagem está
# ---------------------------------------------------------------------------

# `distancia` vem de `core/rota.py` (importada no topo). Nome curto usado
# internamente neste módulo.
_distancia = distancia


def _todos_os_waypoints() -> tuple[Waypoint, ...]:
    return (CAMINHO_ATE_O_ALTAR + CAMINHO_ATE_O_BOSS
            + CAMINHO_DOS_GUARDAS_AO_BOSS + CAMINHO_DO_BOSS_A_SAIDA
            + (Waypoint(*CHEGADA_NA_CAVE, "Bewitcher Cave"),
               Waypoint(*CHEGADA_NO_COVIL, "Secret Cemetery")))


TODOS_OS_WAYPOINTS: tuple[Waypoint, ...] = _todos_os_waypoints()


# Caixa que contém TODO o interior da cave, com folga.
#
# CALCULADA DOS WAYPOINTS, não digitada à mão. Antes era
# `((55, -420), (440, 195))`, escrito por medição, e isso tinha dois defeitos:
# podia divergir da rota sem ninguém notar, e mexer num waypoint não atualizava a
# caixa. Agora os waypoints são a única fonte -- eles são o próprio interior da
# cave medido passo a passo, então o retângulo que os envolve É a cave.
#
# LIMITAÇÃO HONESTA: coordenada de jogo não é única no mundo -- outras regiões
# também têm pontos aqui dentro. Esta caixa só serve para os lugares que a
# rotina pisa: Stone City (y <= -490), Ghost Din Woods (x ~ 1395) e a cave.
# Nenhum deles conflita. Não use isto como "estou na cave" absoluto; use junto
# com o nome do lugar ou com a última transição conhecida.
FOLGA_DA_CAIXA = 25


def _caixa_dos_waypoints() -> tuple[tuple[int, int], tuple[int, int]]:
    xs = [wp.x for wp in TODOS_OS_WAYPOINTS]
    ys = [wp.y for wp in TODOS_OS_WAYPOINTS]
    return ((min(xs) - FOLGA_DA_CAIXA, min(ys) - FOLGA_DA_CAIXA),
            (max(xs) + FOLGA_DA_CAIXA, max(ys) + FOLGA_DA_CAIXA))


CAIXA_DA_CAVE = _caixa_dos_waypoints()   # ((x min, y min), (x max, y max))

# O X MÁXIMO QUE PODE EXISTIR DENTRO DA CAVE.
#
# Regra dada de fora, e ela vale por si: acima de 500 em X não existe nada dentro
# da cave. O waypoint mais a leste é a chegada, em x=423, então a caixa calculada
# já para bem antes disso -- esta verificação existe para o caso de alguém
# adicionar um waypoint errado e esticar a caixa até onde ela não deveria chegar.
X_MAXIMO_DENTRO_DA_CAVE = 500
assert CAIXA_DA_CAVE[1][0] <= X_MAXIMO_DENTRO_DA_CAVE, (
    f"a caixa da cave chegou a x={CAIXA_DA_CAVE[1][0]}, além do limite de "
    f"{X_MAXIMO_DENTRO_DA_CAVE}. Algum waypoint está com a coordenada errada."
)


def posicao_esta_na_caixa_da_cave(pos: tuple[int, int] | None) -> bool:
    """A coordenada cai dentro do retângulo que envolve a cave inteira?"""
    if pos is None:
        return False
    (xmin, ymin), (xmax, ymax) = CAIXA_DA_CAVE
    return xmin <= pos[0] <= xmax and ymin <= pos[1] <= ymax


# Folga exigida para a coordenada CONTRADIZER o nome lido da memória. Estar um
# passo fora da caixa não prova nada -- a caixa já tem folga e coordenada de jogo
# tem ruído. Só um afastamento claro autoriza desmentir a memória.
MARGEM_PARA_CONTRADIZER = 40


def x_contradiz_a_cave(pos: tuple[int, int] | None) -> bool:
    """Só a REGRA DO X: acima de 500 não existe cave nenhuma.

    Separada de `posicao_esta_fora_da_cave` porque as duas respondem perguntas
    diferentes e têm consequências diferentes:

      * a caixa responde "não estou na cave", e pode ser satisfeita por Stone
        City (que sai pelo Y);
      * o X responde "não estou na cave E estou na faixa de Ghost Din Woods",
        porque é o único lugar da rotina com X nessa ordem de grandeza. É essa
        precisão a mais que autoriza FORÇAR o nome do lugar para Ghost Din Woods
        quando a memória insiste numa área da cave.

    Nunca responde True sem posição: "não sei" não é "não está".
    """
    return pos is not None and pos[0] > X_MAXIMO_DENTRO_DA_CAVE


# Y a partir do qual se está em Stone City. O número não é escolhido aqui: é o
# que este arquivo já afirmava na caixa da cave ("Stone City (y <= -490)").
Y_DE_STONE_CITY = -490


NOME_DE_STONE_CITY = "Stone City"


def nome_e_stone_city(local: str | None) -> bool:
    """O jogo está DIZENDO que o personagem está em Stone City?

    Sinal COMPLEMENTAR ao da coordenada, e não substituto -- ver
    `esta_em_stone_city`.
    """
    return bool(local) and NOME_DE_STONE_CITY.lower() in str(local).lower()


def esta_em_stone_city(pos: tuple[int, int] | None,
                       local: str | None = None) -> bool:
    """Está em Stone City? Vale a COORDENADA **ou** o NOME.

    =======================================================================
    POR QUE OS DOIS, quando o resto do projeto usa só a coordenada
    =======================================================================

    A caixa de coordenada é, por construção, um LIMITE INFERIOR: ela foi
    derivada de dois pontos medidos (o vendedor e a Fay), e Stone City é uma
    CIDADE -- tem muito mais chão que isso. Medido no log de 14/08/2026, duas
    partidas com 19 segundos de diferença:

        (205,-498) -> reconhecida, vendeu antes de sair
        (237,-484) -> NÃO reconhecida, foi direto para a Fay com a bolsa cheia

    As duas são Stone City; o jogo dizia isso nas duas. A segunda ficava 6
    unidades acima do corte de `y <= -490`.

    O NOME cobre o resto da cidade. A falha conhecida dele é FICAR PRESO num
    nome antigo -- e o caso medido é ficar preso numa área da CAVE estando fora
    dela, não o contrário. Um "Stone City" lido é sinal positivo confiável.

    E o custo de errar é assimétrico, o que autoriza ser permissivo aqui:

      * deixar de reconhecer  -> sai para a cave com a bolsa cheia, que é o que
                                 trava o bot (o defeito medido acima);
      * reconhecer por engano -> `travel_to_vendor` procura o Rich Man pelo
                                 painel de arredores, não acha, devolve False,
                                 e a rotina segue para o farm com um aviso.
    """
    return posicao_esta_em_stone_city(pos) or nome_e_stone_city(local)


def posicao_esta_em_stone_city(pos: tuple[int, int] | None) -> bool:
    """A coordenada AFIRMA que o personagem está em Stone City?

    DOIS limites, e o segundo não é redundante: Ghost Din Woods fica em
    (1395,-635), e o Y dele também passa por `Y_DE_STONE_CITY`. Quem separa os
    dois é o X -- é a mesma regra de `x_contradiz_a_cave`, e por isso lê a
    mesma constante em vez de repetir o 500.

    Confere contra os pontos medidos:

        vendedor  (158,-494)  -> True
        Fay       (178,-518)  -> True
        boss      ( 80,-406)  -> False   (y acima do corte)
        saída     ( 81,-398)  -> False
        Ghost Din (1395,-635) -> False   (x além do limite)

    Nunca responde True sem posição: "não sei" não é "está".
    """
    if pos is None:
        return False
    return pos[1] <= Y_DE_STONE_CITY and pos[0] <= X_MAXIMO_DENTRO_DA_CAVE


def posicao_esta_fora_da_cave(pos: tuple[int, int] | None) -> bool:
    """A coordenada AFIRMA que o personagem não está na instância.

    NÃO é o contrário de `posicao_esta_na_caixa_da_cave`. Ali `None` responde
    False porque "não sei" não é "não está"; aqui `None` responde False pelo
    mesmo motivo. As duas perguntas convivem, e nenhuma delas responde "sim"
    sem informação.

    A implicação vale num sentido só, e é isso que torna esta função utilizável
    como veto: estar LONGE da caixa prova que não está na cave, porque a caixa
    contém a instância inteira. Estar dentro da caixa não prova o contrário --
    coordenada de jogo se repete pelo mundo.

    Os dois lugares que a rotina pisa fora da cave passam com folga: a entrada
    em Ghost Din Woods tem x ≈ 1395, quase mil unidades além do limite, e Stone
    City tem y ≈ -500, trinta abaixo dele.
    """
    if pos is None:
        return False

    # A REGRA DO X, explícita. Ela já está contida na caixa (que termina em
    # x=448), mas fica escrita porque é o critério mais simples e mais forte que
    # existe aqui: acima de 500 em X não há cave nenhuma. É o que resolve o caso
    # de arranque -- personagem em (1392,-624) com a memória jurando 'Secret
    # Cemetery'. Deixar a regra visível vale mais que economizar duas linhas.
    if x_contradiz_a_cave(pos):
        return True

    (xmin, ymin), (xmax, ymax) = CAIXA_DA_CAVE
    m = MARGEM_PARA_CONTRADIZER
    return (pos[0] < xmin - m or pos[0] > xmax + m
            or pos[1] < ymin - m or pos[1] > ymax + m)


# Distância máxima até um waypoint para aceitar a área dele como resposta.
# Acima disso o bot está fora da rota e dizer a área seria palpite.
RAIO_DA_AREA = 55.0

# Distância até o waypoint mais próximo abaixo da qual o personagem é considerado
# NA rota, e não fora dela. É o limite que separa "escorreguei um pouco" de
# "preciso me retomar" -- e a diferença importa: retomada dentro de área apertada
# faz o bot voltar ao começo da área.
NA_ROTA = 12.0


def area_da_posicao(pos: tuple[int, int] | None) -> str | None:
    """Área da cave em que esta coordenada cai, pelo waypoint mais próximo.

    Devolve None quando nenhum waypoint está perto o bastante -- e None aqui é
    informação útil: significa "estou dentro da caixa da cave mas fora da rota",
    que é exatamente o caso em que o bot precisa se retomar.
    """
    if pos is None:
        return None
    melhor: Waypoint | None = None
    menor = float("inf")
    for wp in TODOS_OS_WAYPOINTS:
        d = _distancia(pos, wp.pos)
        if d < menor:
            menor, melhor = d, wp
    if melhor is None or menor > RAIO_DA_AREA:
        return None
    return melhor.area


# ---------------------------------------------------------------------------
# Retomada de rota
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Retomada:
    """De onde continuar a rota depois de sair dela."""

    indice: int                 # waypoint por onde retomar
    distancia: float            # a que distância dele estamos
    motivo: str                 # texto para o log
    area: str | None         # área em que o personagem está agora


def mais_proximos(
    pos: tuple[int, int],
    caminho: tuple[Waypoint, ...],
    n: int = 2,
) -> list[tuple[int, float]]:
    """Os `n` waypoints mais próximos da posição, como `(índice, distância)`.

    A lista volta JÁ ORDENADA porque a proximidade é a decisão: do mais perto
    para o mais longe. Mais de um, e não apenas o mais próximo, porque o mais
    próximo pode ser justamente o que já foi passado -- com vários em mãos o
    chamador escolhe a estratégia (a retomada de rota anda para frente quando
    são vizinhos; a manobra de destravamento tenta por proximidade).
    """
    distancias = sorted(
        ((i, _distancia(pos, wp.pos)) for i, wp in enumerate(caminho)),
        key=lambda par: par[1],
    )
    return distancias[:n]


def vizinhos_na_rota(
    pos: tuple[int, int],
    caminho: tuple[Waypoint, ...],
) -> tuple[int | None, int | None, int | None]:
    """Os vizinhos IMEDIATOS na rota. Devolve `(anterior, mais_proximo, seguinte)`.

    "Anterior" e "seguinte" são os índices coladinhos no mais próximo -- `base-1`
    e `base+1` --, NUNCA "o mais próximo entre os de índice maior/menor".

    ISTO JÁ FOI O CONTRÁRIO, E CUSTOU UMA RUN. A versão anterior escolhia por
    distância dentro de cada lado, e o log mostrou o resultado com o personagem
    parado em (205,31):

        51/58  (206, 41)  a 10.0   <- o anterior de verdade
        53/58  (205, 23)  a  8.0   <- o mais próximo
        54/58  (244, 23)  a 39.8   <- o seguinte de verdade
        57/58  (219, 44)  a 19.1   <- o que a versão antiga escolhia

    Ela pulava três waypoints para cair num ponto ao DOBRO da distância, e o
    jogo respondia no chat: `Failed to auto-path [Secret Altar(205,31)->Secret
    Altar(218,43)]`. A rota não é um conjunto de pontos, é um CAMINHO: cada
    trecho foi desenhado porque é andável a partir do anterior. No Secret Altar,
    que é uma pirâmide, pular waypoint é pedir para atravessar parede.

    O MAIS PRÓXIMO TAMBÉM É CANDIDATO, e é o primeiro a ser tentado: quando o
    personagem está FORA do caminho, voltar para ele é o que torna o resto
    possível. Ver a ordem em `Navigator.destravar_pelos_vizinhos`.

    A referência é a posição ATUAL, não o índice em que a rota achava que o
    personagem estava -- depois de um rollback os dois divergem, e é o índice
    que está errado.

    Qualquer um dos três pode vir `None`: no começo da rota não há anterior, no
    fim não há seguinte, e numa rota vazia não há nada.
    """
    if not caminho:
        return None, None, None

    base = min(range(len(caminho)),
               key=lambda i: _distancia(pos, caminho[i].pos))
    anterior = base - 1 if base > 0 else None
    seguinte = base + 1 if base + 1 < len(caminho) else None
    return anterior, base, seguinte


def onde_retomar(
    pos: tuple[int, int] | None,
    caminho: tuple[Waypoint, ...],
    indice_esperado: int = 0,
) -> Retomada:
    """Decide por qual waypoint a rota deve continuar.

    Chamado sempre que a posição não é a esperada: lag, rollback, interferência
    do usuário, ou o personagem simplesmente ficou preso e escorregou.

    As regras, em ordem:

      1. Entre os dois waypoints mais próximos, prefere o de índice MAIOR
         quando eles são vizinhos -- é o que está à frente.
      2. Se o waypoint escolhido está numa ÁREA APERTADA (a pirâmide do Secret
         Altar), volta para o primeiro waypoint daquela área. Ali não existe
         atalho: entrar pelo meio significa bater na parede.
      3. Se nada está perto (fora da rota de verdade), retoma pelo waypoint
         mais próximo mesmo assim, e o log registra a distância -- é o número
         que diz se o personagem foi arrastado ou se só escorregou.
    """
    if pos is None or not caminho:
        return Retomada(max(0, indice_esperado), float("inf"),
                        "sem posição legível", None)

    proximos = mais_proximos(pos, caminho)
    (i1, d1) = proximos[0]
    escolhido, distancia = i1, d1

    if len(proximos) > 1:
        (i2, d2) = proximos[1]
        # Vizinhos e praticamente à mesma distância: o de índice maior está à
        # frente, e ir para frente é sempre melhor que voltar.
        if abs(i1 - i2) == 1 and abs(d1 - d2) < 8.0:
            escolhido = max(i1, i2)
            distancia = d2 if escolhido == i2 else d1

    area = caminho[escolhido].area
    motivo = f"waypoint {escolhido + 1}/{len(caminho)} a {distancia:.0f} unidades"

    # O recuo até o início da área só vale para quem está FORA da rota.
    #
    # Estar em cima de um waypoint não é "sair da rota" -- é estar na rota. Sem
    # esta condição, um personagem parado exatamente no patamar do Altar Stone
    # (218,45), que é o ÚLTIMO waypoint do caminho, era mandado de volta ao começo
    # do Secret Altar e refazia a pirâmide inteira por nada. E pior: como o portal
    # do altar só é usado depois de o último waypoint ser alcançado, ele nunca
    # chegava a clicar no Altar Stone -- ficava dando voltas na pirâmide.
    if area in AREAS_APERTADAS and distancia > NA_ROTA:
        primeiro = next(i for i, wp in enumerate(caminho) if wp.area == area)
        if primeiro < escolhido:
            motivo = (f"{motivo}; {area} é apertada e estou FORA da rota, "
                      f"voltando ao início da área (waypoint {primeiro + 1})")
            escolhido = primeiro
            distancia = _distancia(pos, caminho[escolhido].pos)

    return Retomada(escolhido, distancia, motivo, area_da_posicao(pos) or area)


def houve_rollback(
    indice_atual: int,
    pos: tuple[int, int] | None,
    caminho: tuple[Waypoint, ...],
    folga: int = 1,
) -> int | None:
    """Detecta que o personagem voltou muito na rota (lag ou rollback).

    Devolve o índice para onde ele voltou, ou None se está onde deveria. A folga
    existe porque atravessar um waypoint correndo e reler a posição um instante
    depois dá uma diferença pequena e normal -- só um salto de 2+ índices para
    trás é rollback. (O usuário confirmou: o lag costuma devolver 2-3 waypoints,
    nunca mais de 5; folga=1 pega todos.)
    """
    if pos is None or not caminho:
        return None
    (i, d) = mais_proximos(pos, caminho)[0]
    if d > RAIO_DA_AREA:
        return None
    if i < indice_atual - folga:
        return i
    return None


def tolerancia_do_waypoint(wp: Waypoint, base: int, apertada: int) -> int:
    """Tolerância de chegada, maior nas áreas de geometria apertada."""
    if wp.pos in WAYPOINTS_PROBLEMATICOS or wp.area in AREAS_APERTADAS:
        return max(base, apertada)
    return base


def como_lista(caminho: tuple[Waypoint, ...]) -> list[tuple[int, int]]:
    """Só as coordenadas, para quem só precisa andar."""
    return [wp.pos for wp in caminho]


def descrever(pos: tuple[int, int] | None,
              local_lido: str | None = None) -> str:
    """Uma linha de texto dizendo onde o personagem está. Para o log.

    Junta as duas fontes de propósito: o nome lido da memória e a área deduzida
    da coordenada. Quando as duas discordam, é isso que aparece no log -- e a
    discordância é o sinal mais valioso que existe para depurar a rota.
    """
    if pos is None:
        return f"posição ilegível (memória diz {local_lido or '?'})"
    area = area_da_posicao(pos)
    partes = [f"{pos}"]
    if local_lido:
        partes.append(f"memória={local_lido!r}")
    if area:
        partes.append(f"área por coordenada={area!r}")
    elif posicao_esta_na_caixa_da_cave(pos):
        partes.append("dentro da caixa da cave, mas FORA da rota")
    if local_lido and area and local_lido != area:
        partes.append("DIVERGEM")
    return " | ".join(partes)


# Verificação de sanidade das áreas declaradas: um nome digitado errado aqui
# faria o reconhecimento por coordenada apontar para uma área que não existe no
# catálogo, e a divergência com a memória seria permanente e silenciosa.
_desconhecidas = {wp.area for wp in TODOS_OS_WAYPOINTS} - set(AREAS_BC)
if _desconhecidas:  # pragma: no cover - erro de digitação em tempo de import
    raise RuntimeError(
        f"áreas de waypoint fora do catálogo de lugares: {sorted(_desconhecidas)}"
    )

# O CAMINHO ATÉ O ALTAR TEM QUE TERMINAR EXATAMENTE EM (218,45).
#
# É o único ponto de onde o clique no Altar Stone acerta, e a rota é o que leva o
# personagem até ele. Se alguém acrescentar um waypoint depois deste, ou mexer nas
# coordenadas do último, a travessia passa a terminar num lugar de onde o portal
# não abre -- e o sintoma seria "o portal do altar não confirmou" repetido para
# sempre, sem nada apontando para a causa. Melhor não subir do que farmar assim.
if CAMINHO_ATE_O_ALTAR[-1].pos != ULTIMO_ANTES_DO_ALTAR:  # pragma: no cover
    raise RuntimeError(
        f"o último waypoint até o altar é {CAMINHO_ATE_O_ALTAR[-1].pos} e tinha "
        f"que ser {ULTIMO_ANTES_DO_ALTAR}: é o único ponto de onde o clique no "
        f"Altar Stone funciona."
    )

if CAMINHO_ATE_O_ALTAR[-1].area != "Secret Altar":  # pragma: no cover
    raise RuntimeError(
        f"o último waypoint até o altar está marcado como "
        f"{CAMINHO_ATE_O_ALTAR[-1].area!r} e tinha que ser 'Secret Altar'"
    )
