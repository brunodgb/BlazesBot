"""
Navegação: como o bot faz o personagem andar.

=========================================================================
TRÊS FORMAS DE SE MOVER, e cada uma serve para uma distância
=========================================================================

1. MAPA-MÚNDI (tecla M) -- longas distâncias, acima de ~50 unidades.

   O mapa mostra a região inteira. Um clique direito nele manda o personagem
   caminhar até lá usando o pathfinding do próprio jogo, que desvia de
   obstáculos sozinho. É o que permite sair da cidade e chegar na entrada da
   cave sem uma lista de waypoints.

   A conversão de coordenada de jogo para pixel do mapa está em
   `core/zones.py`. Cada região tem um `centre` (a coordenada que cai no meio
   da tela) e uma `scale` (unidades por pixel).

2. MINIMAPA -- curtas distâncias, ajuste fino.

   O centro do minimapa representa a posição atual. Clicar deslocado do centro
   manda andar naquela direção. São ~1.7 pixels por unidade de coordenada, e o
   clique não pode passar de ~30 px do centro, senão cai fora do widget.

3. PAINEL "SURROUNDINGS" -- teleporte por nome.

   Digita um fragmento do nome de um lugar ou NPC e clica no primeiro
   resultado; o jogo caminha até lá. É o mais robusto para destinos que têm
   nome, porque não depende de coordenada nenhuma. A memória expõe o primeiro
   resultado (nome + coordenadas), então dá para CONFERIR que a busca achou o
   lugar certo antes de clicar.

=========================================================================
ONDE MEXER NAS COORDENADAS
=========================================================================

  core/zones.py ......... regiões do mapa, escalas, conversões
  config.py, BCRoute .... a rota da cave: entrada, waypoints, posição do boss
  core/coords.py ........ pontos de tela (minimapa, botões, NPC)

Para gravar um waypoint novo: entre no jogo, vá até o ponto desejado e leia a
posição no canto superior direito da tela, ou rode `2-DIAGNOSTICO.bat`, que
imprime a posição atual. Anote o par (x, y) e coloque na lista.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from ..core import diario
from ..core.rota import distancia, houve_rollback, vizinhos_na_rota
from ..core.zones import (
    MAP_DISTANCE_THRESHOLD,
    coord_para_pixel_do_mapa,
    coord_para_pixel_do_minimapa,
    destino_do_clique,
    distancia_linear,
    zona_do_local,
)
from . import hotbar
from .context import BotContext, Disconnected
from .velocidade import SkillDeVelocidade

DEFAULT_TOLERANCE = 3
TRICKY_TOLERANCE = 8

# ===========================================================================
# MOVIMENTO CONTÍNUO -- por que estes números são assim
# ===========================================================================
#
# Medido no log de produção: o caminho dentro da cave gastava 8,6 SEGUNDOS por
# waypoint, para saltos de ~40 unidades que a montaria cobre em ~3 s. Os mobs
# vêm atrás e chegaram a matar o personagem.
#
# O tempo não estava sendo gasto andando; estava sendo gasto ESPERANDO. O ciclo
# antigo era:
#
#   clica no minimapa -> anda ~17 unidades (o clique não alcança mais que isso)
#     -> PARA -> espera 3 leituras iguais para concluir que parou (1,5 s)
#     -> clica de novo -> anda -> para -> espera 1,5 s -> ...
#
# Três esperas de 1,5 s mais o intervalo de leitura de 0,5 s explicam os 8,6 s.
#
# A correção é não deixar o personagem parar: RE-CLICAR no minimapa antes de ele
# chegar ao fim do trecho anterior. Cada clique reposiciona o destino ~17
# unidades à frente, e o personagem corre sem interrupção. Como o clique vai por
# SendMessage (não move o cursor real e custa ~30 ms), a cadência é barata.
#
# O RECONHECIMENTO da chegada também ficou rápido: leitura de memória custa
# microssegundos, então não há motivo para esperar meio segundo entre elas.

# Intervalo MÁXIMO entre cliques enquanto anda. Não é a cadência normal -- o
# clique normal sai quando o personagem está terminando o trecho anterior. Este
# valor é só a rede de segurança para o caso de um clique ter sido engolido pelo
# cliente, e é menor que o tempo de um trecho inteiro (~1,5 s montado).
INTERVALO_RECLIQUE = 1.1
# Distância do fim do trecho já clicado em que o próximo clique é disparado.
#
# Clicar ANTES de chegar é o ponto todo: se o bot esperasse a chegada, o
# personagem frearia entre trechos, e são 70+ trechos num caminho de cave.
MARGEM_RECLIQUE = 2.0
# Intervalo de leitura de posição. É o que define quanto tempo o personagem fica
# parado depois de chegar, antes de o bot mandar ele para o próximo ponto.
POLL_MOVIMENTO = 0.22
# Tolerância dos waypoints de rota. Waypoint de rota não é destino: é só uma
# indicação de por onde passar, e exigir 3 unidades custava um ciclo de correção
# inteiro em cada um. Destino de verdade (o boss) continua com tolerância curta.
TOLERANCIA_ROTA = 7
# Sem aproximar-se do alvo por este tempo, considera travado.
SEM_PROGRESSO_SEGUNDOS = 1.2

# TETO PARA FICAR PRESO NO MESMO WAYPOINT, sem conseguir manobra nenhuma.
#
# Número do usuário, 04/09/2026: *"o ideal é não ficar muito tempo parado, 30
# segundos sem fazer nada já é bastante tempo parado"*.
#
# Ele conta só o tempo INÚTIL: matar mob zera o relógio, porque matar é
# progresso mesmo que o personagem não saia do lugar. O que este teto corta é o
# bot insistindo numa manobra que não muda nada -- o laço de 4 min 10 s medido
# no log de 04/09, em que o destravamento "chegava" num waypoint onde o
# personagem já estava, ~180 vezes seguidas.
#
# Estourado, `follow_path` devolve False e QUEM DECIDE É A ROTINA: ela sabe
# refazer o trecho, matar, ou falhar a run -- e, ao contrário deste laço, ela
# passa pelo `_guard()`, que responde ao Parar e ao watchdog.
TETO_PRESO_NO_MESMO_PONTO = 30.0

# Folga do detector de rollback: voltar ATÉ 1 índice é ruído normal de leitura;
# voltar 2+ índices é lag/rollback e relança a navegação. (Pedido do usuário: o
# lag costuma devolver 2-3 waypoints, nunca mais de 5 -- e a folga=1 pega todos.)
FOLGA_ROLLBACK = 1

# ===========================================================================
# PERSONAGEM COMPLETAMENTE PARADO DENTRO DA CAVE
# ===========================================================================
#
# "Parado" e "sem progresso" NÃO são a mesma coisa, e é essa diferença que este
# bloco existe para tratar:
#
#   SEM PROGRESSO .. está se movendo, mas não se aproximando do waypoint. Dá a
#                    volta num obstáculo, escorrega na escada, contorna. No
#                    pedido do usuário não há mais passo lateral: relança SÓ
#                    pelos waypoints mais próximos (o círculo de cliques ficou
#                    DESLIGADO -- o código segue definido para reuso futuro).
#   PARADO ......... a POSIÇÃO não muda. O clique não pegou, ou pegou num lugar
#                    que o servidor recusou. Mexer no mesmo lugar não resolve --
#                    o personagem não está indo a lugar nenhum.
#
# Para o segundo caso a resposta é ir para um waypoint CONHECIDO da rota, e
# reentrar nela por lá.
#
# Quanto tempo com a posição idêntica caracteriza parado. Curto: o personagem em
# trajeto muda de posição a cada leitura, então dois segundos parado já são
# anormais. Longo o bastante para não confundir com a fração de segundo entre
# terminar um trecho e o clique seguinte sair.
SEGUNDOS_PARADO_DE_VERDADE = 1.5

# Quanto a posição pode variar e ainda contar como "não saiu do lugar". Uma
# unidade cobre o ruído do arredondamento da coordenada (o jogo guarda float e o
# bot divide por 20), sem deixar passar movimento real.
RUIDO_DA_POSICAO = 1.0

# Prazo para alcançar CADA candidato da manobra de destravamento.
#
# QUATRO SEGUNDOS, e o número tem medição. No log de dev, dos 18 candidatos
# alcançados com sucesso, 16 chegaram em <= 4 s (a maioria em 0 s: já estavam
# dentro da tolerância). Os 5 que falharam gastaram o orçamento INTEIRO, 16 a
# 20 s cada -- ou seja, o prazo largo só servia para ficar parado. Cortar para 4 s
# preserva 17 das 18 chegadas e devolve o resto do tempo para a run.
#
# Ficar parado dentro da cave é o que mata o personagem e custa a run inteira;
# esse é o custo que este número existe para cortar.
#
# RESTAURADO PARA 4,0 EM 18/08/2026. O valor tinha ido para 1,5 s no halvamento
# geral de tempos, e ele é um número MEDIDO -- a própria regra daquele passe
# excluía thresholds medidos, mas este escapou (não consta no
# `alteracao_tempo.md`). O comentário acima continuava descrevendo 4 s enquanto
# o código fazia 1,5.
#
# O corte foi a causa provável do laço relatado pelo usuário: no log de 03:21,
# cada tentativa durou ~1,7 s e TODAS falharam, com a manobra inteira em 5 s.
# Candidato que chegaria em 2-4 s era abandonado antes de chegar, nada
# funcionava, e quem chama recomeçava para sempre.
SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR = 4.0

# Quantas voltas a manobra dá sobre os dois candidatos: frente, trás, frente, trás.
#
# Duas, e não uma, para cada waypoint ter mais de uma chance. E não é repetir o
# mesmo clique: entre a primeira e a segunda tentativa no MESMO waypoint o
# personagem tentou o outro candidato, então mudou de lugar e de ângulo. Repetir
# na hora, do mesmo ponto, seria reclicar o que já não pegou.
#
# Teto total: 3 candidatos x 2 passadas x 4 s = 24 s (era 3 x 20 s = 60 s).
# RESTAURADO PARA 2 EM 18/08/2026, pelo mesmo motivo do valor acima: o
# comentário descrevia 2 e o código fazia 1.
PASSADAS_DO_DESTRAVAMENTO = 2

# ATÉ ONDE A MANOBRA SE AFASTA NA ROTA quando os vizinhos imediatos falham.
#
# Pedido do usuário em 18/08/2026: "já que aquele não está funcionando é
# importante testar os outros para ver se destrava e volta para o caminho".
# O jogo respondia `Failed to auto-path [Secret Altar(203,30)->Secret
# Altar(216,43)]` dezenas de vezes para o MESMO destino.
#
# A EXPANSÃO É PELA ORDEM DA ROTA, nunca por proximidade: base+1, base-1,
# base+2, base-2... Isso preserva a regra que custou uma run -- "a rota é um
# CAMINHO, e pular waypoint é atravessar parede" -- porque cada candidato
# continua sendo um waypoint da rota, tentado do mais perto para o mais longe NA
# LISTA. O que muda é só até onde ela vai depois de os imediatos falharem.
#
# TENSÃO ASSUMIDA, e vale registrar: afastar-se DOES pular waypoint intermediário.
# A diferença para o incidente antigo é a ordem dos fatos -- lá o waypoint
# distante era escolhido DE PRIMEIRA, por estar mais perto em linha reta; aqui
# ele só é tentado depois de o imediato ter falhado de verdade, o que é
# informação que o bot não tinha antes.
ALCANCE_DA_EXPANSAO = 4

# Tolerância para VOLTAR ao caminho, no candidato mais próximo da manobra.
#
# Apertada de propósito, e por um motivo medido: a tolerância da rota no Secret
# Altar é 8, e com ela o personagem parado a 8,0 unidades de (205,23) era dado
# como "alcançado" sem ter andado -- o alvo seguinte virava (244,23), a 40
# unidades atravessando a pirâmide, e o jogo respondia `Failed to auto-path`.
#
# Aqui o ponto do candidato não é "estou perto o bastante", é "voltei para o
# caminho". Não é o incidente da tolerância 3: lá o problema era um número para
# andar e OUTRO para conferir, sobre o mesmo ponto. Aqui há um número só, e
# falhar nele apenas passa a vez para o candidato seguinte.
TOLERANCIA_DE_VOLTA_AO_CAMINHO = 2

# Quantas vezes a manobra pode rodar no mesmo trajeto.
#
# Existe teto porque a manobra tem um jeito de girar em falso: se o personagem
# estiver num lugar de onde NENHUM waypoint é alcançável, ela vai para o mais
# próximo, falha, vai para o outro, falha, e recomeça. Três voltas dão margem para
# os casos que se resolvem e ainda deixam o trajeto estourar o prazo dele e devolver
# o controle para a rotina, que se resitua -- em vez de o bot ficar preso aqui.
MANOBRAS_DE_PARADO = 2

# ===========================================================================
# CÍRCULO DE OFFSETS (última carta da manobra de destravamento)
# ===========================================================================
#
# Quando nenhum waypoint é alcançado, o culpado costuma ser o ÂNGULO em que o
# personagem parou -- principalmente na pirâmide do Secret Altar, onde a escada
# tem ponto que é cenário e bloqueia a rota exata do waypoint. Clicar num ponto
# LIGEIRAMENTE deslocado do destino faz o pathfinding achar uma rota que o ângulo
# não bloqueia. E se nem ao redor do waypoint, ao redor da PRÓPRIA posição, para
# trocar o ângulo de saída.
#
# São 8 direções de bússola x raios crescentes (1, 2, 3, 5). Cada ponto é um
# clique curto + janela de movimento (~2 s) -- NÃO um goto completo por ponto,
# senão o trem de mobs encosta. Andou? Confirma o waypoint com um goto. A ordem
# da varredura é uma constante para poder trocar no teste: por raio ou por
# direção de bússola.
BUSSOLA = (
    (0.0, -1.0), (0.707, -0.707), (1.0, 0.0), (0.707, 0.707),
    (0.0, 1.0), (-0.707, 0.707), (-1.0, 0.0), (-0.707, -0.707),
)
CIRCULO_RAIOS = (1, 2, 3, 5)
# True = raio por raio (1,2,3,5; em cada raio os 8 pontos); False = bússola por
# bússola (N, NE, ...; em cada direção os 4 raios). Constante de teste.
CIRCULO_POR_RAIO = True
# Teto de tempo TOTAL do círculo antes de desistir e devolver o controle. É a
# última carta -- não pode virar mais uma forma de nunca parar (trem de mobs).
CIRCULO_TETO_SEGUNDOS = 6.5
# Janela por ponto do círculo para saber se o clique fez o personagem andar.
SEGUNDOS_POR_CLIQUE_CIRCULO = 1.0
# Cadência da manutenção durante o deslocamento (poção).
INTERVALO_MANUTENCAO = 0.6

# ===========================================================================
# A MONTARIA É PRÉ-REQUISITO DE ANDAR, NÃO UMA OTIMIZAÇÃO
# ===========================================================================
#
# Tudo que este bot sabe sobre andar foi medido MONTADO: o orçamento de tempo de
# cada trecho, as tolerâncias dos waypoints, o alcance de um clique no minimapa
# (~17,6 unidades por clique) e a skill de velocidade, que afeta a montaria e não
# o personagem. A pé, o trajeto passa do dobro da duração -- e dentro da cave
# dobrar a duração é o trem de mobs alcançando.
#
# Por isso a montaria não é conferida "onde alguém lembrou de chamar
# ensure_mounted". Ela é conferida em DOIS lugares estruturais:
#
#   * no PORTÃO de toda função que produz movimento -- `garantir_montaria_para_andar`
#   * a cada volta do laço de deslocamento -- `_manter_montaria`
#
# Espalhar a checagem pelos estados da rotina garantia apenas os trechos lembrados:
# a volta da venda, o ajuste fino depois de um teleporte, o retorno para a porta
# da cave e a caminhada até os NPCs andavam a pé sem ninguém notar.
#
# Intervalo MÍNIMO entre dois toques na tecla da montaria. A tecla é um
# INTERRUPTOR: apertá-la de novo antes de o cliente confirmar desmonta justamente
# quem acabou de montar. Tem que ser maior que o tempo de confirmação do jogo e
# menor que o custo de seguir a pé até a checagem seguinte.
#
# ERA 1,50 s, E ISSO ERA MENOS QUE O TEMPO DE MONTAR. Medição do usuário em
# 25/08/2026: *"subir na montaria pode levar 1 a 3 segundos, porque depende da
# montaria; se não tiver montaria depois de 3 segundos clica de novo"*.
#
# Com 1,50 s o segundo toque caía DENTRO da subida da montaria mais lenta -- e a
# tecla é interruptor, então ele desmontava quem estava montando. O sintoma é
# indistinguível de "a montaria não funcionou": o bot aperta, aperta de novo, e
# continua a pé. O próprio comentário acima já advertia contra isso; o número é
# que não acompanhava.
INTERVALO_REMONTAR = 3.0

# Depois de quanto tempo a pé, no meio de um trajeto, o log passa a dizer isso em
# voz alta.
#
# Não muda comportamento nenhum: a remontagem já está sendo tentada a cada
# `INTERVALO_REMONTAR`. Existe para que "o trecho demorou o dobro" apareça com o
# motivo, em vez de virar um tempo estranho sem explicação no log.
AVISAR_A_PE_NO_TRAJETO = 4.0

# ===========================================================================
# A ORDEM DO PORTÃO: CONFERIR -> ATIVAR -> CONFIRMAR -> ANDAR
# ===========================================================================
#
# O portão não "tenta montar e segue": ele NÃO LIBERA o movimento até a memória
# confirmar a montaria ativa.
#
# E não consulta flag de batalha nenhuma. A flag de combate foi removida de toda
# decisão do bot: ela fica ligada com qualquer mob por perto, demora a baixar
# depois do último golpe e já foi vista presa. O único juiz aqui é o resultado --
# aciona a tecla e confere a memória.
#
# Teto do acionamento: quanto o portão insiste antes de liberar o movimento a pé.
# Existe porque a alternativa a "andar a pé" não é "andar montado", é FICAR
# PARADO -- e parado com o trem de mobs da cave em cima o personagem morre. O
# objetivo é nunca chegar neste teto; chegar aqui gera WARNING e registro no
# diário, porque significa que algo está errado com a montaria do personagem.
TETO_DO_PORTAO = 6.0

# Quantos ciclos do portão sem montar antes de o log passar a GRITAR.
#
# O portão não desiste (ver `garantir_montaria_para_andar`), então este número
# não muda comportamento -- ele decide quando o problema deixa de ser silencioso.
#
# 5 ciclos de `TETO_DO_PORTAO` são ~30 s. A montaria sobe em 1 a 3 s (medição do
# usuário), então meio minuto tentando não é lentidão: é sinal de que a tecla
# está errada, o personagem está numa condição que impede montar, ou o cliente
# parou de responder. Antes disso, insistir calado é o certo -- gritar a cada
# hipótese encheria o log de falso alarme.
CICLOS_ANTES_DE_GRITAR = 5

# Quantos ciclos o portão insiste antes de aceitar ir A PÉ.
#
# Decisão do usuário em 06/09/2026: *"caso tentou mais de 20 vezes ativar a
# montaria e não foi, vai a pé mesmo"*. Vinte ciclos de `TETO_DO_PORTAO` são
# ~2 minutos -- tempo de sobra para qualquer causa passageira (recarga, mob em
# cima, barra na página errada) e muito menos que os 33 minutos parados que
# esta regra existe para nunca mais acontecer.
#
# NÃO VALE DENTRO DA CAVE: lá "a pé" já foi medido como run perdida com atraso
# (*"a pé ele não chega no boss"*). Decisão do usuário em 06/09/2026 quando
# perguntado sobre o conflito: *"mas isso é dentro da cave, APP não é cave e
# nunca será cave"* -- ou seja, a regra nova é para fora da cave, e a de dentro
# fica como estava. Quem separa as duas é `Navigator._dentro_da_cave`.
CICLOS_ANTES_DE_IR_A_PE = 20

# ===========================================================================
# O JOGO CANCELA A MONTARIA SOZINHO -- E ANDAR DESTRAVA
# ===========================================================================
#
# Relato do usuario em 06/09/2026: *"as vezes ao tentar ativar a montaria o jogo
# ficava cancelando sozinho, e claramente um bug do jogo ... o fato de andar
# desbuga esse problema"*.
#
# O LOG CONFIRMA que o episodio existe e nao e raro: 26 casos de "Montaria
# confirmada depois de Ns insistindo", mediana de 40 s. Separando por causa:
#
#     23 casos  COM combate  -> ja tratados por `limpar_o_combate`
#      3 casos  SEM combate  -> 9 s, 13 s e 35 s
#
# O de 35 s e o retrato do bug: personagem parado em (423, 53), dentro da cave,
# FORA de combate, 35 segundos de tecla sem efeito -- e entao a montaria sobe
# sozinha, sem nada ter mudado. Nao ha o que "insistir mais" resolva: a tecla ja
# estava sendo apertada a cada `INTERVALO_REMONTAR`.
#
# POR QUE ANDAR E DIFERENTE DE APERTAR DE NOVO: a tecla e um interruptor e o
# cliente estava recusando o pedido; andar muda o ESTADO do personagem, e e o
# estado que estava preso. E a mesma familia de conserto do "clique que nao
# produz movimento" logo abaixo (`DESVIOS_DO_MAPA`).

# Quanto esperar, desde a PRIMEIRA tentativa, antes de andar um passo. Numero do
# usuario: *"se em 10 segundos depois da primeira tentativa o bot nao
# identificar que ativou a montaria, anda 6px"*.
#
# Dez segundos e folgado sobre a montagem normal (1 a 3 s medidos, 25/08) e
# abaixo do menor episodio SEM combate do log (9 s) -- ou seja, pega os tres
# casos medidos sem disparar no caso comum.
SEGUNDOS_ANTES_DE_CUTUCAR = 10.0

# O tamanho do passo, em unidades de posicao. Numero do usuario ("6px").
#
# Deliberadamente MINUSCULO: o objetivo e mudar o estado do personagem, nao
# viajar. Um clique de minimapa alcanca ~17,6 unidades, entao 6 e menos de meio
# clique -- e a tolerancia dos waypoints da rota e 7, entao o passo cabe DENTRO
# da tolerancia e nao tira o personagem do ponto.
PASSO_PARA_DESTRAVAR_A_MONTARIA = 6

# Depois de quantos ciclos sem montar o portao para de insistir MUDO e vai
# PROCURAR A CAUSA -- e, quando a causa tem tratamento, tira ela do caminho.
#
# MEDIDO EM 31/08/2026 (run `db7ebdace7`, conta `creubo`): 1465 segundos, 62
# ciclos e 453 toques na tecla sem UMA leitura que dissesse se o personagem
# estava em batalha, morto ou com vida. "Continuo insistindo" 62 vezes nao e
# diagnostico -- e a mesma frase 62 vezes.
#
# DOIS ciclos, e o numero nao e arredondamento: um ciclo ja e `TETO_DO_PORTAO`
# = 6 s, que e o DOBRO da montagem mais lenta medida (1 a 3 s, usuario,
# 25/08/2026). Um ciclo perdido ja significa que algo esta errado; dois dao a
# margem de um caso raro sem chegar perto do minuto que o usuario aceitou
# perder. Na pratica o diagnostico sai em ~13 s contra os 24 minutos do log.
CICLOS_ANTES_DE_DESTRAVAR = 2


class PersonagemMortoNoPortao(RuntimeError):
    """O personagem morreu esperando a montaria. Nao ha o que insistir.

    O portao da montaria insiste SEM TETO por desenho (`NUNCA A PE DENTRO DA
    CAVE`), e essa decisao continua valendo -- mas ela pressupoe um personagem
    VIVO. Com o personagem morto o laco aperta a tecla da montaria num cadaver
    para sempre: `_guard()` so roda no topo do laco principal da rotina, e o
    portao nunca devolve o controle para ele.

    Levantar daqui e o unico jeito de a morte chegar ao `RECUPERAR`, que e quem
    sabe reviver. NAO e "desistir da montaria": e reconhecer que nao ha
    montaria possivel para quem esta morto.
    """

# Quantos waypoints à frente podem ser aproveitados de uma vez.
#
# Deliberadamente pequeno: a rota da cave se cruza consigo mesma, e uma janela
# grande faria o bot "cortar caminho" pulando uma passagem obrigatória. Dois
# pontos bastam para absorver o waypoint que o personagem atravessa correndo.
JANELA_ADIANTE = 2

# Deslocamentos tentados quando o clique no mapa não produz movimento.
#
# Acontece quando outro jogador está exatamente no ponto de destino: o jogo
# recusa o caminho em vez de parar ao lado. Tentar alguns pontos vizinhos
# resolve, e depois o minimapa faz o ajuste fino.
DESVIOS_DO_MAPA = (
    (0, 0), (20, 0), (-20, 0), (20, 20), (-20, 20),
    (-20, -20), (0, -20), (20, -20), (0, 20),
)


# Recarga da PARADA para tomar poção durante o trajeto.
#
# Poção não funciona montado -- o jogo ignora a tecla sem devolver erro. Ou seja,
# a poção "em movimento" da versão anterior nunca curou nada: ela só enchia o
# log. Curar de verdade exige desmontar, usar e remontar, e isso custa ~4 s
# parado com o trem de mobs em cima.
#
# Por isso a parada não é livre: só acontece quando o HP realmente pede, e no
# máximo uma vez a cada 10 s. Abaixo do limiar de emergência o trajeto é abortado
# em vez de tratado aqui -- ali o certo é sair, não insistir.
INTERVALO_PARADA_POCAO = 10.0


class _SemMapa:
    """O mapa ausente. Responde a tolerância base, sem folga extra em lugar nenhum.

    Existe para o `Navigator` não precisar de `if self.mapa is None` espalhado --
    e para deixar explícito que "sem mapa" é uma resposta, não um erro.
    """

    # Nenhum waypoint problemático conhecido. EXPLÍCITO em vez de deixar o
    # `getattr` do chamador decidir: assim o contrato do mapa aparece aqui, e
    # não espalhado em cada leitor.
    WAYPOINTS_PROBLEMATICOS: tuple = ()

    @staticmethod
    def tolerancia_do_waypoint(wp, base: int, apertada: int) -> int:
        return base


class Navigator:
    def __init__(self, ctx: BotContext, mapa=None,
                 exigir_montaria: bool = True) -> None:
        self.ctx = ctx
        # PODE ANDAR A PÉ? -- 06/09/2026.
        #
        # `True` (padrão) é a regra da BC: *"nunca deve seguir a pé dentro da
        # cave"*, e por isso o portão da montaria INSISTE para sempre.
        #
        # `False` existe para o APP. Personagem de macro normalmente NÃO TEM
        # montaria -- a tecla está configurada (é o padrão da conta), mas não há
        # o que montar, então o portão nunca confirma. Medido em campo em
        # 06/09/2026: a conta líder ficou **33 minutos e 315 tentativas** presa
        # tentando montar para voltar ao ponto depois de reviver, sem andar um
        # passo. Decisão do usuário: *"só volta montado se tiver a tecla
        # configurada, pois normalmente os personagens que rodam APP não vão ter
        # montaria"*.
        self._exigir_montaria = exigir_montaria
        # Um aviso só por navegador -- ver `garantir_montaria_para_andar`.
        self._avisou_a_pe = False
        # O MAPA DA CAVE, INJETADO. É a única coisa que este navegador precisa
        # saber sobre qual ecossistema o está usando.
        #
        # Ele responde uma pergunta só: `tolerancia_do_waypoint(wp, base,
        # apertada)` -- quanta folga aceitar para dar um waypoint por alcançado.
        # A BC responde com as áreas apertadas da pirâmide do Secret Altar; a HH,
        # com o ponto onde os mobs seguram o personagem. Todo o RESTO da rota
        # (vizinhos, rollback, distância) é função pura e vem de `core/rota.py`.
        #
        # `None` = a tolerância base vale em todo waypoint. É o comportamento
        # correto para quem não tem geometria apertada mapeada, e não um caso
        # degradado: sem dado, não se inventa folga.
        self.mapa = mapa if mapa is not None else _SemMapa()
        self._mapa_aberto = False
        # A skill de velocidade vive no navegador porque é ele que sabe quando o
        # personagem está andando -- e ela só vale a pena andando, montado e
        # dentro da cave. O cronômetro de recarga precisa sobreviver entre
        # trajetos, então é criado uma vez por conta.
        self.velocidade = SkillDeVelocidade(ctx)
        # `self._dentro_da_cave = False` SAIU DAQUI em 06/09/2026, e não é
        # limpeza de estilo: existe um MÉTODO com este nome, e o atributo da
        # instância o sombreava. `self._dentro_da_cave()` virava `False()` --
        # `TypeError: 'bool' object is not callable`, 55 vezes no log, sempre no
        # ciclo de `CICLOS_ANTES_DE_IR_A_PE`, derrubando `CURAR` e `ATE_O_ALTAR`
        # para `RECUPERAR`. O atributo era escrito e nunca lido: código morto
        # que só servia para apagar um método. Travado por
        # `tests/test_init_nao_sombreia_metodo.py`.
        # Quando a tecla da montaria foi tocada pela última vez. Vive na
        # instância, e não em cada laço, porque QUATRO lugares diferentes tocam
        # nela (portão, laço, parada para poção) e ela é um
        # interruptor: dois toques próximos se cancelam. Com cronômetros
        # separados, o bot remontava e desmontava em seguida.
        self._ultimo_toque_na_montaria = 0.0
        # Quando o portao andou um passo para destravar a montaria, e para que
        # lado. A direcao gira a cada passo: se houver parede de um lado, o
        # passo seguinte tenta outro. Ver `SEGUNDOS_ANTES_DE_CUTUCAR`.
        self._ultimo_passo_de_destrave = 0.0
        self._direcao_do_passo_de_destrave = 0
        # DEPENDENCIA CRUZADA, injetada pela rotina (`BossRushRoutine.__init__`).
        #
        # O portao da montaria precisa de COMBATE para se destravar: em batalha
        # o jogo recusa montar, e so um golpe resolve. Mas `combat.py` ja importa
        # `navegacao.py` (o `CombatEngine` recebe o `Navigator`), entao importar
        # de volta faria ciclo -- quem tem os dois na mao e a rotina, e e ela que
        # liga um no outro.
        #
        # Quem usa: `_diagnosticar_o_portao`. O que NAO subiu para ca: o COMO
        # matar, que e todo do `CombatEngine.limpar_o_combate`. Daqui sai so o
        # QUANDO. Mexer neste contrato mexe nos dois arquivos.
        # ==============================================================
        # DOIS GANCHOS, PORQUE SAO DUAS DECISOES DIFERENTES
        # ==============================================================
        #
        # Os dois chamam a MESMA funcao (`combate.limpar_o_combate`), e mesmo
        # assim precisam ser separados -- porque a PERGUNTA que cada um responde
        # e outra, e as caves respondem diferente:
        #
        #   `destravar_o_combate`  "nao consigo MONTAR porque estou em batalha"
        #                          Matar e a unica saida: o jogo recusa a
        #                          montaria em combate, e insistir na tecla nao
        #                          resolve nunca. Vale para TODA cave -- foi o
        #                          conserto do travamento de 24 minutos do BC em
        #                          31/08/2026.
        #
        #   `matar_quando_o_trajeto_trava`  "estou montado, andando, e sem
        #                          progresso". Aqui matar e ESCOLHA, e a
        #                          resposta muda por cave:
        #
        #                            HH  -- SIM. Regra do usuario, 04/09/2026:
        #                                   junto com os bosses ha varios mobs
        #                                   que PRECISAM ser mortos.
        #                            BC  -- NAO. Regra do usuario: nunca sair da
        #                                   montaria ate o waypoint dos Gun
        #                                   Witch. No caminho do covil os mobs
        #                                   sao para IGNORAR.
        #
        # NASCE DESLIGADO. Quem quiser, liga -- e foi por nao ser assim que o BC
        # regrediu: em 04/09 a matanca entrou direto no laco compartilhado e o
        # personagem passou a desmontar no corredor do Altar Stone. Medido no
        # log de 06/09/2026, fase ENTRAR_NO_COVIL: "Desmontando antes da luta de
        # destravar (andar ate (242,22))", e sessenta segundos depois
        # "NAO DESTRAVEI em 60s: 9 morte(s), 8 TAB, 176 golpes".
        self.destravar_o_combate: Callable[[str], bool] | None = None
        self.matar_quando_o_trajeto_trava: Callable[[str], bool] | None = None
        # Desde quando está a pé, e quanto tempo do trajeto atual foi a pé. É o
        # número que diz se a exigência de andar montado está sendo cumprida de
        # verdade -- sem ele, "andou a pé metade da cave" não aparece em log nenhum.
        self._a_pe_desde = 0.0
        self._tempo_a_pe = 0.0
        self._avisou_sem_tecla = False
        self._avisou_a_pe_no_trajeto = False
        # Desde quando o pet está inativo no meio do trajeto, e se isso já foi
        # avisado. O pet NÃO é reinvocado aqui -- ver `_manter_pet`.
        self._pet_caiu_em = 0.0
        self._avisou_pet_caido = False
        # Memória do retrocesso, POR TRAJETO (zerada no início do `follow_path`).
        # Voltar na rota é permitido, mas não em série: sem isso o destravamento
        # anda de ré waypoint a waypoint, e andar de ré na cave é o que deixa o
        # trem de mobs alcançar. Ver `destravar_pelos_vizinhos`.
        self._retrocessos_feitos: set[int] = set()
        # Candidatos que a manobra JÁ TENTOU E NÃO ALCANÇOU neste episódio de
        # travamento. Sem isto, cada nova chamada recomeçava com os MESMOS três
        # vizinhos -- a posição não mudou, então a escolha não muda -- e o bot
        # ficava pedindo ao jogo o mesmo trajeto que ele já tinha recusado
        # dezenas de vezes (`Failed to auto-path`, relatado em 18/08/2026).
        #
        # É zerado quando a rota AVANÇA de verdade (`esquecer_falhas_do_episodio`),
        # não a cada chamada: zerar a cada chamada seria não ter memória nenhuma.
        self._candidatos_que_falharam: set[int] = set()
        self._retrocesso_bloqueado = False
        self._indice_do_retrocesso = -1

    # ==================================================================
    # Leitura de estado
    # ==================================================================

    def position(self) -> tuple[int, int] | None:
        return self.ctx.memory.position()

    def location_name(self) -> str | None:
        return self.ctx.memory.location()

    def wait_until_still(self, max_seconds: float = 20.0,
                         destino: tuple[int, int] | None = None,
                         proximidade: int = 40) -> bool:
        """Espera o personagem parar de andar.

        Duas condições de saída: a posição parou de mudar, ou chegamos perto o
        bastante do destino. A segunda evita esperar o fim de um trajeto longo
        quando o objetivo já foi alcançado -- e evita passar do ponto.
        """
        limite = time.time() + max_seconds
        anterior: tuple[int, int] | None = None
        parado = 0

        while time.time() < limite:
            self.ctx.tick(0.25)
            atual = self.position()
            if atual is None:
                raise Disconnected("posição ilegível durante deslocamento")

            if destino is not None and distancia_linear(atual, destino) < proximidade:
                return True

            if atual == anterior:
                parado += 1
                if parado >= 3:
                    return True
            else:
                parado = 0
            anterior = atual
        return False

    # ==================================================================
    # Mapa-múndi
    # ==================================================================

    def _abrir_mapa(self) -> None:
        if not self._mapa_aberto:
            self.ctx.press("M")
            self.ctx.tick(0.5)
            self._mapa_aberto = True

    def _fechar_mapa(self) -> None:
        if self._mapa_aberto:
            self.ctx.press("M")
            self.ctx.tick(0.3)
            self._mapa_aberto = False

    def _mover_pelo_mapa(self, alvo: tuple[int, int]) -> bool:
        """Anda até `alvo` usando o mapa-múndi.

        Depende de saber em que região estamos, o que vem do nome do lugar na
        memória. Sem esse nome não há como converter coordenada em pixel, e a
        função recusa em vez de clicar em lugar errado.
        """
        ctx = self.ctx
        local = self.location_name()
        zona = zona_do_local(local)
        if zona is None:
            ctx.log.debug(
                "Sem região conhecida para o local %r; usando só o minimapa",
                local,
            )
            return False

        largura, altura = ctx.input.client_size()
        pixel = coord_para_pixel_do_mapa(zona, alvo, largura, altura)
        ctx.log.info(
            "Mapa: %s -> alvo %s = pixel %s (região %s)",
            local, alvo, pixel, zona.nome,
        )

        # Montaria antes do clique: daqui o personagem atravessa a região inteira
        # sozinho, com o pathfinding do jogo, e o teto de 180 s lá embaixo foi
        # calculado montado. A pé, uma travessia dessas estoura o teto.
        self.garantir_montaria_para_andar(f"atravessar o mapa até {alvo}")

        inicial = self.position()
        self._abrir_mapa()
        try:
            # Clique fora do alvo primeiro, para desfazer qualquer seleção que
            # possa capturar o clique seguinte.
            ctx.right_click((pixel[0] - 30, pixel[1] - 30))
            ctx.tick(0.2)

            for desvio in DESVIOS_DO_MAPA:
                ctx.raise_if_stopped()
                ponto = (pixel[0] + desvio[0], pixel[1] + desvio[1])
                ctx.right_click(ponto)
                ctx.tick(1.0)
                agora = self.position()
                if inicial and agora and distancia_linear(inicial, agora) > 1:
                    if desvio != (0, 0):
                        ctx.log.debug("Caminho aceito com desvio %s", desvio)
                    break
            else:
                ctx.log.warning("Nenhum clique no mapa produziu movimento")
                return False
        finally:
            self._fechar_mapa()

        self.wait_until_still(max_seconds=180.0 * ctx.settings.time_factor,
                             destino=alvo)
        return True

    # ==================================================================
    # Minimapa
    # ==================================================================
    #
    # Não existe mais um "passo de minimapa" isolado. Ele era clicar, esperar o
    # personagem PARAR e só então avaliar -- e essa parada, repetida a cada ~17
    # unidades, era o que fazia o trajeto da cave levar 8,6 s por waypoint. O
    # clique no minimapa agora acontece dentro do laço contínuo de
    # `follow_path`, que reposiciona o destino antes de o personagem frear.

    # ==================================================================
    # Deslocamento principal
    # ==================================================================

    def esquecer_falhas_do_episodio(self) -> None:
        """O episódio de travamento acabou: a lista de candidatos ruins morre.

        Chamado quando o personagem CHEGA em algum waypoint -- ou seja, quando
        a informação "este candidato não funciona" deixa de valer, porque ela
        era sobre uma posição em que ele não está mais.
        """
        self._candidatos_que_falharam = set()

    def esquecer_retrocessos(self) -> None:
        """Zera a memória do retrocesso. Chamada UMA vez por run.

        A memória é presa ao PROGRESSO, não a quem chamou -- e essa distinção é
        o conserto de um defeito que anulava a trava inteira. Ela ficava sendo
        zerada no início do `follow_path`, e duas coisas passavam por ali:

          * a própria manobra, que chama `follow_path` para cada candidato --
            ou seja, cada tentativa apagava a trava que a manobra tinha acabado
            de gravar;
          * cada volta SITUAR -> ATE_O_ALTAR, e o log registrou SEIS delas em um
            minuto.

        O resultado foi o personagem voltando cinco, seis waypoints em sequência
        dentro da cave. A trava existia e nunca chegou a valer uma vez.
        """
        self._retrocessos_feitos = set()
        self._retrocesso_bloqueado = False
        self._indice_do_retrocesso = -1

    def _tolerancia_do_candidato(self, rota: tuple, i: int,
                                 base: int | None) -> int:
        """Com que precisão é preciso chegar neste candidato do destravamento.

        O mais próximo (`base`) é o "voltar para o caminho": ali chegar de
        verdade é o ponto, e a régua é apertada. Os outros usam a tolerância da
        área, que é a mesma da rota.

        VIROU FUNÇÃO em 04/09/2026 porque agora há DOIS lugares que precisam da
        mesma resposta: o laço que tenta e o filtro que descarta o candidato
        onde o personagem já está. Duas cópias dessa conta divergiriam em
        silêncio, e o sintoma seria um candidato descartado com uma régua e
        tentado com outra.
        """
        if i == base:
            return TOLERANCIA_DE_VOLTA_AO_CAMINHO
        return self.mapa.tolerancia_do_waypoint(
            rota[i], TOLERANCIA_ROTA, TRICKY_TOLERANCE)

    def destravar_pelos_vizinhos(
        self,
        rota: tuple,
        tras_primeiro: bool = False,
    ) -> int | None:
        """Personagem travado na cave: reentra na rota por um waypoint vizinho.

        Devolve o índice do waypoint ALCANÇADO, para a rota continuar dele em
        diante, ou `None` se nenhum deu.

        =================================================================
        TRÊS CANDIDATOS, E TODOS COLADOS NO MAIS PRÓXIMO
        =================================================================

        `core.rota.vizinhos_na_rota` devolve o MAIS PRÓXIMO e os dois IMEDIATOS ao
        lado dele na ordem da lista. A ordem em que são tentados é:

            1. o MAIS PRÓXIMO   -- voltar para o caminho
            2. o SEGUINTE       -- seguir por ele
            3. o ANTERIOR       -- última saída

        O mais próximo vem primeiro porque, quando o personagem está FORA do
        caminho, andar pelo caminho é impossível antes de voltar a ele. Foi o
        caso do log: parado em (205,31), o jogo recusava tudo
        (`Failed to auto-path`) enquanto o waypoint a 8 unidades, na mesma
        coluna de X, resolvia.

        O MAIS PRÓXIMO EXIGE CHEGAR DE VERDADE (`TOLERANCIA_DE_VOLTA_AO_CAMINHO`,
        bem menor que a da rota). Sem isso ele seria um "cheguei" instantâneo: a
        tolerância da área é 8, o personagem estava a 8,0 do waypoint, e a rota
        já o dava por alcançado -- era exatamente esse "alcançado sem ir" que
        fazia o alvo seguinte ficar a 40 unidades do outro lado da pirâmide.

        =================================================================
        QUANDO VOLTAR É PROIBIDO
        =================================================================

        Duas regras, e elas cobrem coisas diferentes:

          * ESTANDO NA ROTA, só frente. Se o personagem está dentro da tolerância
            de um waypoint, ele não está perdido -- está no caminho, e o que
            falta é andar. Voltar dali é o que produzia a série de cinco, seis
            waypoints de ré que o usuário viu;
          * DEPOIS DE UM RETROCESSO, só frente até a rota AVANÇAR além do ponto
            para onde voltou. Esta vale quando ele está fora da rota, onde a
            primeira não se aplica.

        Mais a de sempre: nunca retroceder duas vezes para o mesmo waypoint.

        `tras_primeiro=True` (rollback) troca a ordem entre seguinte e anterior;
        o mais próximo continua em primeiro, porque no rollback ele é justamente
        onde o lag largou o personagem.
        """
        ctx = self.ctx
        atual = self.position()
        if atual is None or not rota:
            return None

        anterior, base, seguinte = vizinhos_na_rota(atual, rota)
        if base is None:
            return None

        # "Estou na rota?" pela tolerância do próprio waypoint mais próximo.
        tol_base = self.mapa.tolerancia_do_waypoint(
            rota[base], TOLERANCIA_ROTA, TRICKY_TOLERANCE)
        na_rota = distancia(atual, rota[base].pos) <= tol_base

        motivo_sem_tras = ""
        if anterior is not None:
            if na_rota:
                anterior, motivo_sem_tras = None, "estou na rota; só frente"
            elif self._retrocesso_bloqueado:
                anterior, motivo_sem_tras = None, "já retrocedi neste episódio"
            elif anterior in self._retrocessos_feitos:
                anterior, motivo_sem_tras = None, "já retrocedi para este waypoint"

        depois = [seguinte, anterior] if not tras_primeiro else [anterior, seguinte]
        candidatos = [i for i in ([base] + depois) if i is not None]

        # EXPANSÃO PELA ORDEM DA ROTA. Os imediatos vêm primeiro; se eles já
        # falharam neste episódio, a manobra se afasta de um em um NA LISTA --
        # base+2, base-2, base+3... Nunca por proximidade em linha reta, que é a
        # regra que custou uma run ("a rota é um CAMINHO, pular waypoint é
        # atravessar parede"): aqui todo candidato continua sendo waypoint da
        # rota, e a ordem de tentativa continua sendo do mais perto ao mais
        # longe DENTRO DELA.
        for salto in range(2, ALCANCE_DA_EXPANSAO + 1):
            for i in (base + salto, base - salto):
                if 0 <= i < len(rota) and i not in candidatos:
                    candidatos.append(i)

        # O QUE JÁ FALHOU NESTE EPISÓDIO NÃO É TENTADO DE NOVO. É isto que
        # quebra o laço: sem a memória, a posição não muda, a escolha não muda,
        # e o bot repete o mesmo pedido que o jogo já recusou.
        restantes = [i for i in candidatos if i not in self._candidatos_que_falharam]
        if not restantes:
            # Todos já falharam: a memória morre e a manobra recomeça do zero,
            # em vez de devolver `None` para sempre. O personagem pode ter se
            # mexido no meio das tentativas, e um trajeto recusado antes pode
            # passar agora.
            ctx.log.warning(
                "Todos os %s candidatos já falharam neste episódio; "
                "esquecendo e recomeçando", len(candidatos))
            self.esquecer_falhas_do_episodio()
            restantes = candidatos
        candidatos = restantes

        # ===============================================================
        # CANDIDATO ONDE O PERSONAGEM JÁ ESTÁ NÃO É CANDIDATO
        # ===============================================================
        #
        # Andar até um ponto que já foi alcançado dá certo SEMPRE -- em zero
        # segundo, com qualquer tolerância -- e não muda nada. Pior: a manobra
        # declara sucesso, quem chamou zera o contador de travas, e a situação
        # volta idêntica. É um laço que nunca fecha.
        #
        # Medido no log de 04/09/2026: parado em (282,139), com o waypoint 21
        # exatamente em (282,139), o bot deu **~180 voltas em 4 minutos e 10
        # segundos** -- "Destravando pelo waypoint 21 (tolerância 2)",
        # "alcançado em 0.0s", "a rota continua do 22", e de novo. Só parou
        # porque o usuário desligou a HH.
        #
        # A docstring acima já previa metade disso ("o mais próximo exige chegar
        # DE VERDADE"), e a tolerância apertada resolve o "quase lá". O que ela
        # não cobria era o "já estou lá": distância ZERO passa em qualquer
        # tolerância.
        #
        # A MESMA RÉGUA DA TENTATIVA decide o filtro (`_tolerancia_do_candidato`)
        # -- é o que garante que "seria alcançado na hora" e "é descartado"
        # sejam exatamente o mesmo conjunto.
        ja_alcancados = [
            i for i in candidatos
            if distancia(atual, rota[i].pos)
            <= self._tolerancia_do_candidato(rota, i, base)
        ]
        if ja_alcancados:
            ctx.log.info(
                "Destravamento: descartando o(s) waypoint(s) %s -- o personagem "
                "já está neles, e andar zero unidade não destrava nada.",
                [i + 1 for i in ja_alcancados])
            candidatos = [i for i in candidatos if i not in ja_alcancados]

        if not candidatos:
            # NÃO HÁ O QUE OFERECER, e dizer isso é o ganho: quem chamou devolve
            # o controle para a rotina, que sabe matar, refazer o trecho ou
            # falhar. Fingir sucesso aqui era o laço de 4 minutos.
            ctx.log.warning(
                "Destravamento em %s: todos os vizinhos são pontos em que o "
                "personagem JÁ está. Não tenho manobra -- devolvendo o controle.",
                atual)
            return None

        ctx.log.warning(
            "Navegação travada em %s. Vizinhos imediatos: %s%s",
            atual,
            " -> ".join(
                f"{i + 1} em {rota[i].pos} a "
                f"{distancia(atual, rota[i].pos):.0f}"
                for i in candidatos),
            f" (sem candidato atrás: {motivo_sem_tras})" if motivo_sem_tras else "",
        )
        diario.registrar_evento(
            ctx.account_login, "travado-na-cave",
            f"vizinhos {[i + 1 for i in candidatos]}",
            atual, ctx.memory.location(),
        )

        for passada in range(1, PASSADAS_DO_DESTRAVAMENTO + 1):
            for i in candidatos:
                ctx.raise_if_stopped()
                alvo = rota[i].pos
                tolerancia = self._tolerancia_do_candidato(rota, i, base)
                ctx.log.info(
                    "Destravando pelo waypoint %s/%s em %s (tolerância %s, "
                    "passada %s de %s)",
                    i + 1, len(rota), alvo, tolerancia, passada,
                    PASSADAS_DO_DESTRAVAMENTO,
                )
                # `follow_path` direto, e não `goto`: o `goto` tem piso de 5 s no
                # orçamento, e aqui o prazo é curto de propósito. Um waypoint só,
                # sem `rota=` -- passar a rota faria os gatilhos de travamento
                # deste laço dispararem DENTRO da manobra, recursivamente.
                if self.follow_path(
                        [alvo], tolerance=tolerancia,
                        max_seconds=SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR):
                    if i == anterior:
                        self._retrocessos_feitos.add(i)
                        self._retrocesso_bloqueado = True
                        self._indice_do_retrocesso = i
                    ctx.log.info(
                        "Cheguei no waypoint %s/%s; a rota continua do %s",
                        i + 1, len(rota), min(i + 2, len(rota)),
                    )
                    # CHEGOU: o episódio acabou e a lista de candidatos ruins
                    # perde a validade -- ela era sobre uma posição em que o
                    # personagem não está mais.
                    self.esquecer_falhas_do_episodio()
                    return i
                # ANOTA A FALHA. Na próxima chamada este candidato sai da lista,
                # e a manobra tenta OUTRO em vez de repetir o mesmo pedido.
                self._candidatos_que_falharam.add(i)
                ctx.log.warning("Não cheguei no waypoint %s/%s", i + 1, len(rota))

        ctx.log.warning(
            "Nenhum dos vizinhos (%s) foi alcançado de %s em %s passada(s)",
            [i + 1 for i in candidatos], atual, PASSADAS_DO_DESTRAVAMENTO)
        return None

    def _tentar_circulo(self, rota: tuple, alvo_idx: int) -> int | None:
        """Círculo de offsets (última carta): clica levemente fora do alvo.

        `alvo_idx` é o waypoint que não foi alcançado. O ângulo em que o
        personagem parou pode bloquear a rota exata; clicar num ponto LIGEIRAMENTE
        deslocado do centro (primeiro ao redor do waypoint, depois ao redor da
        própria posição) faz o pathfinding achar uma abertura.

        Cada ponto é um clique curto + janela de movimento
        (`_clicar_offset_e_verificar`), não um goto completo. Andou? Só então
        confirma com um `goto` no waypoint real. Teto total de
        `CIRCULO_TETO_SEGUNDOS` para não virar outra forma de nunca desistir (o
        trem de mobs encosta a cada segundo).

        Devolve `alvo_idx` se o waypoint foi alcançado, ou `None`.
        """
        ctx = self.ctx
        alvo = rota[alvo_idx].pos
        tolerancia = self.mapa.tolerancia_do_waypoint(
            rota[alvo_idx], TOLERANCIA_ROTA, TRICKY_TOLERANCE)
        # Q4: o PRÓPRIO personagem primeiro (quebrar o bolsão), o waypoint
        # depois. Quando o alvo está a dezenas de unidades, offsets de 1-5u ao
        # redor dele não trocam o ÂNGULO DE SAÍDA, que é o que destrava.
        centros = []
        atual = self.position()
        if atual:
            centros.append(atual)
        centros.append(alvo)

        inicio = time.time()
        for centro, raio, (dx, dy) in self._pontos_do_circulo(centros):
            ctx.raise_if_stopped()
            if time.time() - inicio > CIRCULO_TETO_SEGUNDOS:
                ctx.log.warning(
                    "Círculo de offsets estourou o teto de %.0fs; devolvendo o "
                    "controle", CIRCULO_TETO_SEGUNDOS)
                return None
            if self._clicar_offset_e_verificar(centro, raio, dx, dy):
                if time.time() - inicio > CIRCULO_TETO_SEGUNDOS:
                    return None
                ctx.log.info(
                    "Offset (%d,%d) a %d unidades andou o personagem; confirmando "
                    "o waypoint %s/%s", dx, dy, raio, alvo_idx + 1, len(rota))
                if self.goto(alvo, tolerance=tolerancia,
                             max_seconds=SEGUNDOS_POR_TENTATIVA_DE_DESTRAVAR,
                             usar_mapa=False):
                    return alvo_idx
        return None

    def _clicar_offset_e_verificar(
        self, centro: tuple[int, int], raio: int, dx: float, dy: float,
    ) -> bool:
        """Clique curto num offset e medição: o personagem andou?

        `centro` pode ser o waypoint-alvo (desvio pequeno) ou a própria posição.
        O offset é `centro + (round(dx*raio), round(dy*raio))`, clicado no
        minimapa. Espera `SEGUNDOS_POR_CLIQUE_CIRCULO`; se a posição mudou mais
        que o ruído, o clique pegou -- devolve True.
        """
        ctx = self.ctx
        antes = self.position()
        if antes is None:
            return False
        offset = (centro[0] + round(dx * raio), centro[1] + round(dy * raio))
        pixel = coord_para_pixel_do_minimapa(
            antes, offset, ctx.coords.minimap_center)
        # UM clique só: no minimapa cada clique é uma ORDEM DE ANDAR, e a
        # rajada calcularia os seguintes de uma posição que o personagem já
        # deixou. Ver `inputs.right_click`.
        ctx.right_click(pixel, repetir=False)
        fim = time.time() + SEGUNDOS_POR_CLIQUE_CIRCULO
        while time.time() < fim:
            ctx.raise_if_stopped()
            ctx.tick(0.1)
            agora = self.position()
            if agora is None:
                continue
            if distancia_linear(antes, agora) > RUIDO_DA_POSICAO:
                return True
        return False

    def _pontos_do_circulo(
        self, centros: list[tuple[int, int]],
    ) -> list[tuple[tuple[int, int], int, tuple[int, int]]]:
        """Gera (centro, raio, direção) conforme `CIRCULO_POR_RAIO`.

        `True` -> raio por raio (1,2,3,5; em cada raio as 8 direções).
        `False` -> bússola por bússola (N, NE, ...; em cada direção os 4 raios).
        """
        pontos = []
        for centro in centros:
            if CIRCULO_POR_RAIO:
                for raio in CIRCULO_RAIOS:
                    for diret in BUSSOLA:
                        pontos.append((centro, raio, diret))
            else:
                for diret in BUSSOLA:
                    for raio in CIRCULO_RAIOS:
                        pontos.append((centro, raio, diret))
        return pontos

    def goto(
        self,
        alvo: tuple[int, int],
        tolerance: int = DEFAULT_TOLERANCE,
        max_seconds: float | None = None,
        usar_mapa: bool = True,
    ) -> bool:
        """Anda até uma coordenada.

        Escolhe o meio de transporte pela distância: mapa-múndi para longe,
        minimapa para perto. O trecho de minimapa usa o mesmo laço contínuo do
        `follow_path`, com um waypoint só -- não existe motivo para o
        deslocamento curto ser mais lento que o caminho da cave.

        `usar_mapa=False` para DENTRO de instância: o mapa-múndi não serve ali
        (a cave não é uma região do mapa), e tentar custa abrir e fechar a tela.
        """
        ctx = self.ctx
        if max_seconds is None:
            max_seconds = 180.0 * ctx.settings.time_factor
        limite = time.time() + max_seconds

        atual = self.position()
        if atual is None:
            raise Disconnected("posição ilegível em goto()")
        if distancia_linear(atual, alvo) <= tolerance:
            return True

        # O portão da montaria NÃO fica aqui. Ele fica dentro de `_mover_pelo_mapa`
        # e de `follow_path`, que são quem realmente clica -- assim vale para
        # qualquer chamador futuro, e não duplica a linha de log em cada trecho.
        if usar_mapa and distancia_linear(atual, alvo) > MAP_DISTANCE_THRESHOLD:
            # Sem mapa disponível, o laço do minimapa ainda chega lá.
            self._mover_pelo_mapa(alvo)

        return self.follow_path(
            [alvo],
            tolerance=tolerance,
            max_seconds=max(5.0, limite - time.time()),
        )

    # ==================================================================
    # Movimento contínuo por waypoints
    # ==================================================================

    def _parada_para_pocao(self, pct: float) -> None:
        """Desmonta, toma poção e remonta. É a ÚNICA forma que funciona.

        A versão anterior apertava a tecla da poção sem desmontar, e o jogo
        simplesmente IGNORA itens com o personagem montado -- sem erro nenhum. Ou
        seja: o log dizia "Poção em movimento (HP 40%)" e nada acontecia. O
        personagem seguia sangrando até o limiar de emergência abortar o trajeto.

        Custa uns 4 segundos parado, e é por isso que a parada tem recarga longa
        e só acontece quando o HP realmente pede.
        """
        ctx = self.ctx
        k = ctx.settings.keys
        tecla = k.battle_hp_potion or k.hp_potion
        if not tecla:
            return

        ctx.log.info("Parando para tomar poção (HP %.0f%%) — montado o jogo "
                     "ignora o item", pct)
        estava_montado = ctx.memory.is_mounted()
        if estava_montado and not self.ensure_dismounted(timeout=4.0):
            ctx.log.warning("Não desmontei; a poção não faria efeito")
            return

        ctx.press(tecla)
        ctx.tick(0.25)

        if estava_montado:
            # Remonta na hora: a pé o trajeto dobra de duração e o trem de mobs
            # alcança. Não espera confirmação aqui -- `_manter_montaria`, no laço,
            # cobre o caso de a primeira tentativa falhar.
            #
            # Vai por `_tocar_na_montaria` para que o laço SAIBA deste toque. Antes
            # os dois cronômetros eram independentes, e o laço apertava a tecla de
            # novo pouco depois -- desmontando quem tinha acabado de montar.
            self._tocar_na_montaria()
            ctx.tick(0.2)

        depois = ctx.snapshot()
        if depois.max_hp and depois.hp_pct <= pct + 1:
            diario.registrar_evento(
                ctx.account_login, "acao-sem-efeito",
                f"tomei poção a {pct:.0f}% e a vida não subiu "
                f"({depois.hp_pct:.0f}%); confira a tecla {tecla!r} e o estoque",
                depois.position, depois.location,
            )

    def _manutencao_em_movimento(self, quando: dict) -> str | None:
        """Cuidados durante o trajeto. Devolve um motivo de aborto, ou None.

        Deliberadamente não usa `CombatEngine.maintain`: aquele pode disparar
        skill de cura, e skill tem tempo de conjuração -- o personagem para para
        conjurar, que é exatamente o que não se pode fazer com meia cave
        correndo atrás.
        """
        ctx = self.ctx
        p = ctx.settings.potions
        m = ctx.memory
        agora = time.time()

        # A CONTA MORA NO `core` (`Memory.vida_pct`), e não aqui: "quanta vida
        # eu tenho" é pergunta sobre o JOGO, e o ecossistema APP faz a mesma.
        pct = m.vida_pct()
        if pct is not None:
            if pct <= p.emergency_pct:
                return f"HP crítico ({pct:.0f}%) durante o deslocamento"
            # Usa o limiar de BATALHA, e não o normal, porque atravessar a cave
            # com o trem de mobs atrás É estar em luta. Isso é uma escolha de
            # LIMIAR (um número da configuração), não uma leitura da flag de
            # combate -- ela não existe mais em decisão nenhuma do bot.
            if pct <= p.battle_hp_pct and agora - quando["pocao"] >= INTERVALO_PARADA_POCAO:
                quando["pocao"] = agora
                self._parada_para_pocao(pct)

        # A MONTARIA NÃO É TRATADA AQUI. Ela saiu desta função de propósito: com a
        # checagem presa à cadência de 1,2 s da manutenção, mais o intervalo de
        # remontagem somado por cima, o personagem podia andar mais de quatro
        # segundos a pé sem que nada fosse tentado. Agora é `_manter_montaria`,
        # chamado a cada volta do laço de deslocamento.
        return None

    def _avancar_indice(
        self,
        atual: tuple[int, int],
        caminho: list[tuple[int, int]],
        indice: int,
        tolerancias: list[int],
    ) -> int:
        """Consome os waypoints já alcançados, inclusive os atravessados correndo.

        Correndo a 190% de velocidade o personagem passa POR CIMA de um waypoint
        entre duas leituras. Sem esta janela, o bot mandaria ele voltar -- e
        voltar é o que faz o trem de mobs alcançar.
        """
        while indice < len(caminho):
            if distancia_linear(atual, caminho[indice]) <= tolerancias[indice]:
                indice += 1
                continue
            # O waypoint seguinte já está mais perto que o atual? Então o atual
            # ficou para trás e insistir nele é andar de ré.
            adiante = range(indice + 1, min(indice + 1 + JANELA_ADIANTE,
                                            len(caminho)))
            pulou = False
            for j in adiante:
                if distancia_linear(atual, caminho[j]) <= tolerancias[j]:
                    indice = j + 1
                    pulou = True
                    break
            if not pulou:
                break
        return indice

    def seguir_rota(
        self,
        rota: tuple,
        max_seconds: float | None = None,
        comecar_em: int = 0,
        ao_chegar: Callable[[tuple[int, int]], None] | None = None,
    ) -> bool:
        """Percorre uma rota de um mapa de cave, com tudo que ela sabe.

        `comecar_em` é POR ONDE COMEÇAR, e a rota vai INTEIRA. Antes quem retomava
        no meio passava uma FATIA (`CAMINHO_ATE_O_ALTAR[retomar:]`), e a fatia
        levava embora tudo o que estava atrás -- inclusive o waypoint anterior,
        que é candidato do destravamento. No log de (205,31) o anterior estava a
        10 unidades e simplesmente não existia na lista que a manobra viu.

        Com a rota inteira há uma noção só de "onde estou nela". Duas noções
        (índice na fatia e índice real) foi o que apagou aquele candidato.

        Diferente de `follow_path`, que só recebe coordenadas, aqui cada waypoint
        traz a ÁREA a que pertence. Isso liga três comportamentos que coordenada
        sozinha não permite:

          * tolerância maior nas áreas de geometria apertada (a pirâmide do
            Secret Altar), onde encostar é o normal e exigir 7 unidades nunca é
            satisfeito;
          * RETOMADA DE ROTA: fora do caminho por lag, rollback ou interferência,
            o bot escolhe por qual waypoint continuar em vez de insistir num
            destino que ficou para trás;
          * a skill de velocidade da montaria, acionada só aqui dentro.
        """
        return self.follow_path(
            [wp.pos for wp in rota],
            max_seconds=max_seconds,
            rota=rota,
            dentro_da_cave=True,
            comecar_em=comecar_em,
            ao_chegar=ao_chegar,
        )

    def follow_path(
        self,
        caminho: list[tuple[int, int]],
        tolerance: int = TOLERANCIA_ROTA,
        max_seconds: float | None = None,
        rota: tuple | None = None,
        dentro_da_cave: bool = False,
        comecar_em: int = 0,
        ao_chegar: Callable[[tuple[int, int]], None] | None = None,
    ) -> bool:
        """Percorre waypoints em ordem, SEM parar entre eles.

        `ao_chegar` é chamado uma vez por waypoint ALCANÇADO, com a coordenada
        dele, e existe para o punhado de pontos onde a rota precisa PARAR e
        fazer algo -- na HH, o (232,188), onde os mobs bloqueiam a passagem
        (`travel.lua`: *"em 232,188 matando os mobs que bloqueiam"*).

        Sem gancho o comportamento é exatamente o de antes, e é por isso que a
        BC não muda: o parâmetro é opcional e o padrão é `None`.

        É CHAMADO PARA TODOS OS ATRAVESSADOS, e não só para o último: o laço
        pode cruzar dois ou três waypoints numa leitura, e um ponto que exige
        parada não pode ser pulado por causa da velocidade da montaria.

        O laço é único para o caminho inteiro, em vez de um `goto` por waypoint.
        É essa diferença que dá fluidez: quando o personagem alcança um ponto, o
        clique do ponto seguinte sai na leitura seguinte (~0,12 s) e ele nem
        chega a frear. Antes, cada waypoint pagava ~1,5 s para confirmar "parou"
        mais outra espera para o clique seguinte.

        Waypoints marcados como problemáticos na configuração recebem tolerância
        maior: são pontos onde a geometria faz o personagem encostar e a
        distância curta nunca é satisfeita.
        """
        ctx = self.ctx
        caminho = [tuple(p) for p in caminho]
        if not caminho:
            return True

        # PORTÃO DA MONTARIA. Aqui e não em quem chama: este laço é por onde todo
        # trajeto do bot passa, então garantir aqui é garantir em todos -- inclusive
        # nos que ninguém lembrou de cobrir (volta da venda, ajuste depois de
        # teleporte, retorno para a porta da cave).
        #
        # Também é aqui que o cronômetro de tempo a pé zera: ele mede ESTE trajeto.
        self._tempo_a_pe = 0.0
        self._a_pe_desde = 0.0
        # A MEMÓRIA DO RETROCESSO NÃO É ZERADA AQUI. Ver
        # `esquecer_retrocessos`: zerá-la a cada `follow_path` anulava a trava,
        # porque a própria manobra chama `follow_path` para cada candidato.
        montado = self.garantir_montaria_para_andar(
            f"percorrer {len(caminho)} waypoint(s)")

        if rota is not None:
            # A rota conhece a área de cada waypoint, e a área é o que define a
            # tolerância: no Secret Altar o personagem encosta na escada e nunca
            # satisfaz uma distância curta.
            tolerancias = [
                self.mapa.tolerancia_do_waypoint(wp, tolerance, TRICKY_TOLERANCE)
                for wp in rota
            ]
        else:
            # DO MAPA INJETADO, e não de `settings.route` -- que é um atalho
            # para `bc.route` e traria os waypoints problemáticos da Bewitcher
            # Cave para dentro da navegação da HH. Os dois mapas expõem o mesmo
            # nome, e `getattr` cobre o mapa ausente (`_SemMapa`).
            problematicos = {
                tuple(p)
                for p in getattr(self.mapa, "WAYPOINTS_PROBLEMATICOS", ())
            }
            tolerancias = [
                max(tolerance, TRICKY_TOLERANCE) if w in problematicos else tolerance
                for w in caminho
            ]
        total = len(caminho)
        if max_seconds is None:
            # Orçamento pelo COMPRIMENTO do caminho, não pela contagem de
            # waypoints: dois pontos distantes levam mais tempo que dez pontos
            # colados, e um teto por contagem estoura num caso e é frouxo no
            # outro. A velocidade assumida é conservadora de propósito -- ela é o
            # limite de segurança, não a expectativa.
            atual = self.position()
            # Só o que FALTA percorrer: com `comecar_em` a lista vai inteira,
            # mas o trecho já feito não pode entrar no orçamento.
            partida = min(comecar_em, total - 1)
            comprimento = distancia_linear(atual, caminho[partida]) if atual else 0.0
            comprimento += sum(
                distancia_linear(caminho[i], caminho[i + 1])
                for i in range(partida, total - 1)
            )
            velocidade = 4.0 * ctx.settings.mount_multiplier
            max_seconds = 20.0 + comprimento / velocidade

        inicio = time.time()
        limite = inicio + max_seconds
        indice = max(0, min(comecar_em, total - 1))
        travas = 0
        alvo_anterior: tuple[int, int] | None = None
        destino_clicado: tuple[float, float] | None = None
        ultimo_clique = 0.0
        melhor_distancia = float("inf")
        ultimo_progresso = time.time()
        quando = {"pocao": 0.0}
        ultima_manutencao = 0.0
        marco = time.time()
        andando_desde = time.time()
        area_anterior: str | None = None
        # Detector de personagem PARADO (posição idêntica), separado do detector de
        # "sem progresso" (que se move sem se aproximar). Ver o bloco de
        # `SEGUNDOS_PARADO_DE_VERDADE`.
        ultima_posicao: tuple[int, int] | None = None
        parado_desde = 0.0
        manobras_de_parado = 0
        # Desde quando estou preso no MESMO waypoint sem manobra que resolva.
        # Zerado por avanço de índice e por qualquer trabalho útil (matar mob).
        preso_desde = 0.0

        ctx.log.info("Percorrendo %s waypoints (tolerância %s, teto %.0fs)%s%s",
                     total, tolerance, max_seconds,
                     "" if montado else " | COMEÇANDO A PÉ (montaria indisponível)",
                     f" | {self.velocidade.estado_para_log()}"
                     if dentro_da_cave else "")

        while time.time() < limite:
            ctx.raise_if_stopped()
            atual = self.position()
            if atual is None:
                raise Disconnected("posição ilegível durante o trajeto")

            # MONTARIA primeiro, e a cada volta. Tomar dano derruba a montaria, e
            # a partir daí cada segundo a pé é um segundo de trem de mobs
            # encostando. Vem antes da skill de velocidade de propósito: a skill
            # afeta a montaria, então a pé ela seria recarga jogada fora.
            self._manter_montaria()

            # PET, na mesma volta. Só vigia e registra -- reinvocar exigiria
            # desmontar no meio do corredor. Ver `_manter_pet`.
            self._manter_pet()

            # A ÚNICA skill que funciona montado. Fica aqui, no laço de
            # deslocamento, porque é o único lugar do bot que sabe que o
            # personagem está andando -- e ela só vale a pena andando.
            if dentro_da_cave:
                self.velocidade.usar_se_puder(True, andando_desde)

            # ROLLBACK / LAG. O personagem voltou muito na rota sem o bot pedir:
            # servidor engasgou, internet oscilou, ou alguém interferiu. Insistir
            # no waypoint antigo mandaria ele atravessar de novo o trecho que
            # acabou de perder, pela frente errada.
            if rota is not None and indice > 0:
                voltou = houve_rollback(
                    indice, atual, rota, FOLGA_ROLLBACK)
                if voltou is not None:
                    ctx.log.warning(
                        "Voltei do waypoint %s para perto do %s (posição %s). "
                        "Parece lag ou rollback; relançando a navegação.",
                        indice + 1, voltou + 1, atual,
                    )
                    diario.registrar_evento(
                        ctx.account_login, "rollback",
                        f"waypoint {indice + 1} -> {voltou + 1}",
                        atual, ctx.memory.location(),
                    )
                    # A leitura pode ter pego o personagem NO MEIO do "pulo" do
                    # lag -- a posição ainda se move. Reconfirmar ~0,5 s antes
                    # de relançar evita apontar para onde ele já não está.
                    # (A rotina relê a posição sozinha; o tick é só para o
                    # servidor assentar.)
                    ctx.tick(0.25)
                    # `tras_primeiro=True`: no rollback o personagem acabou de
                    # PERDER terreno, e o chão por onde ele passou há instantes é
                    # o comprovadamente andável. Nos outros gatilhos a frente vem
                    # primeiro.
                    alcancado = self.destravar_pelos_vizinhos(
                        rota, tras_primeiro=True)
                    if alcancado is not None:
                        indice = alcancado
                        travas = 0
                    else:
                        indice = voltou
                    melhor_distancia = float("inf")
                    ultimo_progresso = time.time()
                    alvo_anterior = None
                    destino_clicado = None

            # ==========================================================
            # PERSONAGEM COMPLETAMENTE PARADO
            # ==========================================================
            #
            # A posição não muda: o clique não pegou, ou pegou num destino que o
            # servidor recusou. Não há passo lateral a dar -- o problema não é a
            # orientação, é que o personagem não está indo a lugar nenhum. A
            # resposta é ir para um waypoint CONHECIDO e reentrar na rota por lá.
            #
            # Só dentro da cave, e só quando existe rota: fora dela não há
            # waypoints para escolher.
            if rota is not None:
                if (ultima_posicao is not None
                        and distancia_linear(atual, ultima_posicao)
                        <= RUIDO_DA_POSICAO):
                    if parado_desde == 0.0:
                        parado_desde = time.time()
                    elif (time.time() - parado_desde >= SEGUNDOS_PARADO_DE_VERDADE
                            and manobras_de_parado < MANOBRAS_DE_PARADO):
                        manobras_de_parado += 1
                        alcancado = self.destravar_pelos_vizinhos(rota)
                        parado_desde = 0.0
                        ultima_posicao = None
                        if alcancado is None:
                            # MESMO DESFECHO DOS OUTROS GATILHOS. Antes este
                            # continuava no laço e só o prazo do trajeto cortava;
                            # o de "sem progresso" abortava. A diferença era
                            # acidente, não decisão. Se dois waypoints oficiais
                            # colados no personagem não foram alcançados em
                            # quatro tentativas, o problema não é escolha de
                            # destino -- é o personagem não estar indo a lugar
                            # nenhum, e quem sabe tratar isso é o SITUAR, que
                            # relê posição, área e memória.
                            ctx.log.warning(
                                "Parado em %s no waypoint %s/%s; os vizinhos não "
                                "resolveram. Devolvendo o controle.",
                                atual, indice + 1, total,
                            )
                            diario.registrar_evento(
                                ctx.account_login, "travado",
                                f"parado no waypoint {indice + 1}/{total}",
                                atual, ctx.memory.location(),
                            )
                            return False
                        # A rota continua DO WAYPOINT ALCANÇADO. Apontar o
                        # índice para ele basta: o personagem já está lá, então
                        # `_avancar_indice` passa para o seguinte na próxima
                        # volta -- é isso que faz "cheguei no 38, sigo para o
                        # 39" sem nenhuma conta extra.
                        indice = alcancado
                        travas = 0
                        melhor_distancia = float("inf")
                        ultimo_progresso = time.time()
                        alvo_anterior = None
                        destino_clicado = None
                        continue
                else:
                    ultima_posicao = atual
                    parado_desde = 0.0

            novo = self._avancar_indice(atual, caminho, indice, tolerancias)
            if novo != indice:
                agora = time.time()
                ctx.log.debug(
                    "waypoint %s/%s alcançado em %.1fs%s | posição %s",
                    novo, total, agora - marco,
                    f" (+{novo - indice - 1} atravessado(s))" if novo - indice > 1 else "",
                    atual,
                )
                # A ROTA ANDOU: o relógio de "preso" recomeça do zero.
                preso_desde = 0.0

                if ao_chegar is not None:
                    for alcancado in caminho[indice:novo]:
                        ao_chegar(alcancado)
                    # OS CRONÔMETROS RECOMEÇAM DEPOIS DO GANCHO. Ele pode ter
                    # ficado um minuto matando mob, e sem isto esse minuto
                    # contaria como "parado sem progresso" -- o laço concluiria
                    # que o personagem travou e dispararia o destravamento.
                    agora = time.time()

                marco = agora
                indice = novo
                melhor_distancia = float("inf")
                ultimo_progresso = agora
                parado_desde = 0.0
                ultima_posicao = None
                # A rota AVANÇOU de verdade: o retrocesso volta a ser permitido.
                # Sem esta liberação a trava valeria para o trajeto inteiro, e um
                # retrocesso legítimo mais adiante (outro ponto, outro problema)
                # ficaria proibido por causa de um que aconteceu lá atrás.
                if (self._retrocesso_bloqueado
                        and indice > self._indice_do_retrocesso):
                    self._retrocesso_bloqueado = False
                # Troca de área da cave: uma linha por área, não por waypoint.
                # É o registro que diz onde a run estava quando algo deu errado,
                # sem precisar ler 58 linhas de waypoint.
                if rota is not None and indice < total:
                    area = rota[indice].area
                    if area != area_anterior:
                        area_anterior = area
                        ctx.log.info("Entrando em %s (waypoint %s/%s, posição %s)",
                                     area, indice + 1, total, atual)
                if indice >= total:
                    ctx.log.info(
                        "Caminho concluído: %s waypoints em %.1fs "
                        "(%.1fs por ponto)%s",
                        total, agora - inicio, (agora - inicio) / total,
                        self._resumo_da_montaria(),
                    )
                    return True

            alvo = caminho[indice]
            distancia = distancia_linear(atual, alvo)
            agora = time.time()

            # RE-CLIQUE ANTES DE PARAR.
            #
            # Um clique só alcança ~17,6 unidades. O clique seguinte tem que sair
            # enquanto o personagem ainda está correndo o trecho anterior -- é
            # isso que elimina a parada. Clica quando:
            #
            #   * o waypoint mudou (destino novo, sai na hora);
            #   * o personagem está chegando no fim do trecho já clicado;
            #   * passou o intervalo de segurança sem clique nenhum (cobre o caso
            #     de o clique ter sido engolido pelo cliente).
            fim_do_trecho = (
                destino_clicado is not None
                and distancia_linear(atual, destino_clicado) <= MARGEM_RECLIQUE
            )
            if (alvo != alvo_anterior or fim_do_trecho
                    or agora - ultimo_clique >= INTERVALO_RECLIQUE):
                ponto = coord_para_pixel_do_minimapa(
                    atual, alvo, ctx.coords.minimap_center
                )
                # UM clique só. Este é o clique de andar da rota inteira: a
                # rajada aqui move o destino a cada repetição, porque o ponto
                # foi calculado a partir de `atual` e o personagem sai do lugar
                # entre um clique e o seguinte.
                ctx.right_click(ponto, repetir=False)
                destino_clicado = destino_do_clique(atual, alvo)
                ultimo_clique = agora
                alvo_anterior = alvo

            # Progresso: aproximar-se conta, o resto é trava.
            if distancia < melhor_distancia - 1.0:
                melhor_distancia = distancia
                ultimo_progresso = agora
                travas = 0
            elif agora - ultimo_progresso > SEM_PROGRESSO_SEGUNDOS:
                travas += 1
                if not preso_desde:
                    preso_desde = agora
                ctx.log.debug(
                    "sem progresso indo para %s (waypoint %s/%s, distância "
                    "%.0f) — relançando (%s)", alvo, indice + 1, total,
                    distancia, travas,
                )

                # =======================================================
                # EM BATALHA NÃO SE ANDA -- SE ESTA CAVE QUISER MATAR
                # =======================================================
                #
                # O jogo prende o personagem em combate, e insistir no clique de
                # minimapa contra isso é o que o log de 04/09 mostra: `Failed to
                # auto-path` repetido enquanto os mobs batiam.
                #
                # QUEM DECIDE É O ECOSSISTEMA, e o gancho é PRÓPRIO -- não o do
                # portão da montaria. Ver o bloco dos dois ganchos no
                # `__init__`: na HH os mobs do caminho precisam morrer; no BC
                # eles são para ignorar, e desmontar aqui viola a regra de nunca
                # sair da montaria antes do waypoint dos Gun Witch.
                #
                # MATAR ZERA O RELÓGIO DE "PRESO": é trabalho útil, mesmo que o
                # personagem não saia do lugar. O teto existe para insistência
                # inútil, não para luta.
                #
                # `is True` e não `not ...`: leitura ilegível não autoriza sair
                # batendo -- puxaria mob por causa de uma leitura que falhou.
                if (self.matar_quando_o_trajeto_trava is not None
                        and ctx.memory.in_battle() is True):
                    ctx.log.info(
                        "Sem progresso indo para %s e EM BATALHA: o jogo prende "
                        "o personagem em combate. Matando até sair, antes de "
                        "tentar andar de novo.", alvo)
                    self.matar_quando_o_trajeto_trava(f"andar até {alvo}")
                    preso_desde = 0.0
                    ultimo_progresso = time.time()
                    travas = 0
                    continue

                # TETO DA INSISTÊNCIA INÚTIL. Ver `TETO_PRESO_NO_MESMO_PONTO`.
                if agora - preso_desde > TETO_PRESO_NO_MESMO_PONTO:
                    ctx.log.warning(
                        "Preso no waypoint %s/%s (%s) há %.0fs sem manobra que "
                        "resolva, a %.0f unidades. Devolvendo o controle para a "
                        "rotina decidir.", indice + 1, total, alvo,
                        agora - preso_desde, distancia,
                    )
                    diario.registrar_evento(
                        ctx.account_login, "preso",
                        f"waypoint {indice + 1}/{total} alvo {alvo} "
                        f"a {distancia:.0f} unidades por "
                        f"{agora - preso_desde:.0f}s",
                        atual, ctx.memory.location(),
                    )
                    return False

                if rota is not None:
                    # IR DIRETO para o relançar, SEM passo lateral (pedido do
                    # usuário): o destravar antigo mexia o personagem 1-2u no
                    # lugar -- e era exatamente isso que impedia o relançar de
                    # disparar (o gatilho pedia posição estática, e o destravar
                    # nunca deixava ela ficar parada): eram 190 s de destravar
                    # em vão no Secret Altar. Agora, sem progresso é SÓ clique
                    # nos waypoints mais próximos (a retomada de rota e o
                    # círculo de offsets ficaram DESLIGADOS por decisão do
                    # usuário; o código continua no repo para reuso futuro).
                    # O deadlock que o `precisa_avancar` evitava (chegar num
                    # waypoint de trás, a rota re-apontar para o mesmo alvo
                    # intransponível, para sempre) agora é barrado pela TRAVA DO
                    # RETROCESSO dentro da manobra: volta-se uma vez, e depois só
                    # a frente é tentada até a rota avançar de verdade. Proibir o
                    # retrocesso por completo custava caro -- de 20 chegadas
                    # bem-sucedidas no log, 6 eram descartadas por serem de trás.
                    alcancado = self.destravar_pelos_vizinhos(rota)
                    if alcancado is not None:
                        indice = alcancado
                        travas = 0
                        melhor_distancia = float("inf")
                        ultimo_progresso = time.time()
                        alvo_anterior = None
                        destino_clicado = None
                        continue

                    ctx.log.warning(
                        "Travado no waypoint %s/%s (%s), a %.0f unidades. "
                        "Posição %s", indice + 1, total, alvo, distancia, atual,
                    )
                    diario.registrar_evento(
                        ctx.account_login, "travado",
                        f"waypoint {indice + 1}/{total} alvo {alvo} "
                        f"a {distancia:.0f} unidades",
                        atual, ctx.memory.location(),
                    )
                    return False
                else:
                    # Fora da cave (sem rota): não há waypoints para relançar
                    # nem círculo de offsets (ambos dependem da rota). O passo
                    # lateral foi removido (o usuário pediu só cliques). Resta
                    # o próprio laço reclicar o alvo e o teto de desistência.
                    if travas > 6:
                        ctx.log.warning(
                            "Travado no waypoint %s/%s (%s), a %.0f unidades. "
                            "Posição %s", indice + 1, total, alvo, distancia, atual,
                        )
                        diario.registrar_evento(
                            ctx.account_login, "travado",
                            f"waypoint {indice + 1}/{total} alvo {alvo} "
                            f"a {distancia:.0f} unidades",
                            atual, ctx.memory.location(),
                        )
                        return False

                # NÃO zera `melhor_distancia`. Zerar aqui fazia o contador de
                # travas NUNCA crescer, e com isso o teto nunca disparava:
                #
                #   `melhor_distancia = inf`  ->  próxima leitura: distancia < inf
                #   ->  conta como progresso  ->  `travas = 0`
                #
                # O log mostrava o resultado: "sem progresso ... destravando 1"
                # repetido de 5 em 5 segundos, quarenta segundos seguidos, sempre
                # 1. O bot insistia para sempre em vez de concluir que estava
                # travado de verdade e devolver o controle.
                #
                # Zerar é certo quando o ALVO muda (rollback, retomada) -- ali a
                # distância anterior não vale mais. Aqui o alvo é o mesmo, então o
                # que vale é a distância de agora: progresso passa a significar
                # "ficou mais perto do que já estava".
                melhor_distancia = distancia
                ultimo_progresso = time.time()
                # Força clique novo ao voltar: o relançar (ou o círculo) mexeu na
                # posição, e o trecho que estava clicado não vale mais.
                alvo_anterior = None
                destino_clicado = None

            if agora - ultima_manutencao >= INTERVALO_MANUTENCAO:
                ultima_manutencao = agora
                antes_da_manutencao = time.time()
                motivo = self._manutencao_em_movimento(quando)
                if motivo:
                    ctx.log.warning("Abortando o trajeto: %s", motivo)
                    return False
                # A PARADA PARA POÇÃO É DE PROPÓSITO, e o detector de "parado" não
                # pode confundi-la com trava: ela para o personagem por segundos.
                # Qualquer manutenção que tenha custado tempo real zera o
                # cronômetro, senão a volta seguinte veria a posição idêntica e
                # dispararia a manobra dos dois waypoints por nada.
                if time.time() - antes_da_manutencao > 1.0:
                    parado_desde = 0.0
                    ultima_posicao = None

            ctx.tick(POLL_MOVIMENTO)

        ctx.log.warning(
            "Tempo esgotado no trajeto: cheguei ao waypoint %s de %s em %.0fs%s",
            indice, total, time.time() - inicio, self._resumo_da_montaria(),
        )
        return False

    # ==================================================================
    # Surroundings
    # ==================================================================

    def travel_via_surroundings(
        self,
        texto: str,
        expected: tuple[int, int] | None = None,
        tolerance: int = 4,
        attempts: int = 4,
        confirmar_nome: str | None = None,
    ) -> bool:
        """Usa o painel Surroundings como teleporte por nome.

        Muito mais robusto que waypoints para trechos longos: digita um fragmento
        do nome, clica no primeiro resultado e o jogo faz o trajeto inteiro.

        Quando a memória permite, o primeiro resultado é CONFERIDO antes do
        clique -- nome e coordenadas. Sem essa conferência, uma busca que traga
        outro lugar de nome parecido levaria o personagem para o lugar errado sem
        ninguém perceber.
        """
        ctx = self.ctx
        c = ctx.coords

        # O painel também é MOVIMENTO: clicar no resultado faz o personagem
        # caminhar até lá com o pathfinding do jogo. A pé essa caminhada custa mais
        # que o dobro, e era um dos trechos que passavam sem montaria porque
        # ninguém pensa nele como "andar".
        self.garantir_montaria_para_andar(f"caminhar até {texto!r} pelos arredores")

        for tentativa in range(1, attempts + 1):
            ctx.raise_if_stopped()
            ctx.log.info("Surroundings: buscando %r (tentativa %s)", texto, tentativa)

            ctx.click(c.surroundings_button)
            ctx.tick(0.5)
            ctx.click(c.surroundings_input)
            ctx.tick(0.2)
            ctx.input.clear_field(16)
            ctx.tick(0.15)
            ctx.input.type_text(texto)
            ctx.tick(0.4)

            # Confere o primeiro resultado antes de clicar nele.
            info = ctx.memory.surroundings_first()
            if info:
                ctx.log.info("Surroundings encontrou %r em %s",
                             info["nome"], info["coords"])
                if confirmar_nome and confirmar_nome.lower() not in str(info["nome"]).lower():
                    ctx.log.warning(
                        "O resultado %r não corresponde a %r; não vou clicar",
                        info["nome"], confirmar_nome,
                    )
                    ctx.click(c.surroundings_button)
                    ctx.tick(0.25)
                    continue
                if expected is None:
                    expected = tuple(info["coords"])  # type: ignore[arg-type]

            ctx.click(c.surroundings_first_link)
            ctx.tick(0.5)
            ctx.click(c.surroundings_button)   # fecha o painel
            ctx.tick(0.25)

            self.wait_until_still(
                max_seconds=180.0 * ctx.settings.time_factor,
                destino=expected,
                proximidade=max(tolerance, 10),
            )

            if expected is None:
                return True

            atual = self.position()
            if atual is None:
                raise Disconnected("posição ilegível após Surroundings")
            if distancia_linear(atual, expected) <= tolerance:
                return True

            # Chegou perto: o minimapa fecha a diferença.
            ctx.log.debug("Chegou em %s, esperado %s; ajustando", atual, expected)
            if self.goto(expected, tolerance=tolerance, max_seconds=60.0):
                return True

        return False

    # ==================================================================
    # Montaria
    # ==================================================================
    #
    # Ler o bloco "A MONTARIA É PRÉ-REQUISITO DE ANDAR" no topo do arquivo antes
    # de mexer em qualquer coisa aqui.

    def _tocar_na_montaria(self) -> None:
        """Aciona a tecla da montaria e ANOTA quando.

        Todo mundo que aperta essa tecla passa por aqui, de propósito. Ela é um
        interruptor, e antes cada lugar tinha o seu próprio cronômetro: a parada
        para poção remontava, o laço de deslocamento não sabia disso e apertava de
        novo dois segundos depois -- desmontando o personagem exatamente no trecho
        onde a montaria mais importa.
        """
        self.ctx.press(self.ctx.settings.keys.mount)
        self._ultimo_toque_na_montaria = time.time()

    def _pode_tocar_na_montaria(self) -> bool:
        return (time.time() - self._ultimo_toque_na_montaria) >= INTERVALO_REMONTAR

    def _dentro_da_cave(self) -> bool:
        """Estou numa instância? Aí o portão da montaria NÃO desiste.

        O DISCRIMINADOR JÁ EXISTIA e não precisou de nada novo: instância não é
        região do mapa-múndi, então `zona_do_local` devolve `None` para ela e um
        nome de região para qualquer lugar aberto. É a mesma pergunta que
        `_mover_pelo_mapa` faz para decidir se pode clicar no mapa.

        SEM LEITURA, RESPONDE "SIM" -- e isso é deliberado: sem saber onde está,
        o certo é manter o comportamento antigo (insistir), não estrear o novo.
        """
        try:
            return zona_do_local(self.location_name()) is None
        except Exception:
            return True

    def _sem_tecla_de_montaria(self, motivo: str) -> bool:
        """Verdadeiro (e avisa UMA vez) quando a tecla não está configurada.

        A validação da conta já exige essa tecla, então chegar aqui significa
        configuração fora do padrão. O aviso é ERRO e não warning porque não é um
        detalhe de conforto: sem montaria os orçamentos de tempo do trajeto estão
        todos errados e a run vai falhar por tempo esgotado, num ponto qualquer,
        sem deixar pista do motivo real.
        """
        if self.ctx.settings.keys.mount:
            return False
        if not self._avisou_sem_tecla:
            self._avisou_sem_tecla = True
            self.ctx.log.error(
                "A tecla da montaria não está configurada, e a montaria é "
                "PRÉ-REQUISITO para andar (%s). Toda a rota da BC foi medida "
                "montado. Configure em Editar conta > Teclas > Montaria.",
                motivo,
            )
            diario.registrar_evento(
                self.ctx.account_login, "sem-montaria",
                "tecla da montaria não configurada; o bot da BC depende dela "
                "para qualquer movimentação",
                self.ctx.memory.position(), self.ctx.memory.location(),
            )
        return True

    def garantir_montaria_para_andar(self, motivo: str,
                                     timeout: float = TETO_DO_PORTAO) -> bool:
        """PORTÃO obrigatório antes de qualquer deslocamento.

        A ORDEM É ESTRITA e é o ponto todo desta função:

            1. CONFERIR   -- a memória diz se a montaria está ativa
            2. ATIVAR     -- se não está, aciona a tecla
            3. CONFIRMAR  -- espera a memória confirmar que ficou ativa
            4. só então o movimento sai

        Não é "aciona e segue". Enquanto o passo 3 não confirma, o portão não
        libera -- porque um clique de movimento dado antes da confirmação faz o
        personagem sair andando a pé, e é justamente isso que se quer evitar.

        NÃO existe checagem de "em batalha" aqui, e isso é decisão firme: a flag
        de combate da memória fica ligada com qualquer mob por perto, demora a
        baixar depois do último golpe e já foi vista presa. Consultá-la só fazia o
        bot deixar de acionar a tecla em situações em que ela funcionaria. Agora o
        único juiz é o resultado: aciona e confere a memória.

        Fica no navegador, e não nos estados da rotina, porque é o navegador que
        produz movimento: é o único ponto por onde todo trajeto passa
        necessariamente.

        =================================================================
        NUNCA A PÉ DENTRO DA CAVE -- regra do usuário, 25/08/2026
        =================================================================

        *"Nunca deve seguir a pé dentro da cave, é algo que precisa estar
        documentado inclusive, pois ir até o last boss depende de ter a montaria
        e estar usando ela."*

        Este método FAZIA o contrário: estourado o teto, ele devolvia `False` e
        os três trechos de dentro da cave (`atravessar a cave`, `travessia até o
        altar`, `ir até os guardas`) seguiam a pé ignorando o retorno.

        O raciocínio antigo -- *"a alternativa a andar a pé é ficar parado, e
        parado com o trem de mobs o personagem morre"* -- parecia certo e estava
        incompleto: a pé ele **não chega no boss**. Então andar a pé não é "mais
        devagar", é perder a run mais tarde, depois de gastar a travessia inteira.

        Agora o portão INSISTE. Não há teto para desistir; o que existe é um
        grito: a partir de `CICLOS_ANTES_DE_GRITAR` ciclos sem montar, sai `ERROR`
        por ciclo com o tempo acumulado. O laço continua interrompível pelo Parar
        e pelo watchdog -- e na prática ele quase nunca dá uma volta, porque a
        montaria sobe em 1 a 3 s.

        Devolve False num caso só: **SEM A TECLA CONFIGURADA**. Aí não há o que
        acionar, insistir seria clicar no nada para sempre, e é erro de
        configuração -- não situação de jogo.
        """
        ctx = self.ctx
        if not self._exigir_montaria:
            # TRAJETO QUE ACEITA IR A PÉ. Não insiste, não grita: devolve
            # "não montei" e quem chamou segue andando. Ver `_exigir_montaria`.
            if not self._avisou_a_pe:
                self._avisou_a_pe = True
                ctx.log.info("Vou a pé (%s): este trajeto não exige montaria.",
                             motivo)
            return False
        if self._sem_tecla_de_montaria(motivo):
            return False

        # 1. CONFERIR. O caso comum: já está montado e nada precisa ser feito.
        if ctx.memory.is_mounted():
            return True

        ctx.log.debug("Não estou montado; montando antes de %s", motivo)

        # Barra de atalhos na página 1 antes de acionar a tecla da montaria.
        # DEPOIS do "já está montado" acima, de propósito: no caso comum não há
        # tecla a apertar, e clicar ali seria custo em todo trajeto. A recarga do
        # `hotbar` ainda segura a rajada da manobra de destravamento, que abre
        # vários trajetos curtos seguidos.
        hotbar.garantir_pagina_1(ctx, f"montar para {motivo}")

        # 2 e 3. ATIVAR e CONFIRMAR, INSISTINDO. `ensure_mounted` aciona a tecla
        #        e só devolve depois de a memória confirmar -- ou de esgotar o
        #        prazo. Estourou o prazo, tenta de novo: ver o bloco "NUNCA A PÉ
        #        DENTRO DA CAVE" acima.
        comeco = time.time()
        ciclo = 0
        while True:
            ctx.raise_if_stopped()
            if self.ensure_mounted(timeout=timeout):
                if ciclo:
                    ctx.log.info(
                        "Montaria confirmada depois de %.0fs insistindo (%s)",
                        time.time() - comeco, motivo)
                else:
                    ctx.log.debug(
                        "Montaria confirmada; liberando o movimento (%s)", motivo)
                return True

            ciclo += 1
            gasto = time.time() - comeco
            if ciclo >= CICLOS_ANTES_DE_IR_A_PE and not self._dentro_da_cave():
                # DESISTE E VAI A PÉ. Parado é pior que devagar -- foi medido em
                # 06/09/2026, com a conta líder do time 33 min sem andar um
                # passo. Ver `CICLOS_ANTES_DE_IR_A_PE`.
                ctx.log.error(
                    "Não montei em %d tentativas (%.0fs) antes de %s. VOU A PÉ "
                    "-- parado é pior. Se esta conta deveria ter montaria, "
                    "confira a tecla e o item.", ciclo, gasto, motivo)
                diario.registrar_evento(
                    ctx.account_login, "sem-montaria",
                    f"desisti de montar antes de {motivo} depois de {ciclo} "
                    f"tentativas ({gasto:.0f}s); seguindo a pé",
                    ctx.memory.position(), ctx.memory.location(),
                )
                return False
            # POR QUE nao monto -- e, quando da, TIRA A CAUSA do caminho. Isto
            # vem ANTES do grito de proposito: gritar sem diagnostico foi o que
            # produziu as 453 linhas identicas do log de 31/08.
            self._diagnosticar_o_portao(motivo, ciclo, gasto)
            if ciclo == CICLOS_ANTES_DE_GRITAR:
                # UMA vez no diário, no ciclo em que o silêncio deixa de ser
                # aceitável. Registrar a cada ciclo encheria o histórico com o
                # mesmo problema.
                diario.registrar_evento(
                    ctx.account_login, "sem-montaria",
                    f"não consigo montar antes de {motivo} há {gasto:.0f}s; "
                    "continuo insistindo -- a pé não se chega no boss",
                    ctx.memory.position(), ctx.memory.location(),
                )
            if ciclo >= CICLOS_ANTES_DE_GRITAR:
                ctx.log.error(
                    "NÃO CONSIGO MONTAR antes de %s há %.0fs (%s tentativas). "
                    "Continuo insistindo: a pé o personagem não chega no boss. "
                    "Confira a tecla da montaria e se o personagem está em "
                    "condição de montar.",
                    motivo, gasto, ciclo,
                )

    def _diagnosticar_o_portao(self, motivo: str, ciclo: int,
                               gasto: float) -> None:
        """POR QUE nao monta -- e, quando da, tira a causa do caminho.

        Duas causas tem tratamento, e sao justamente as duas que insistir na
        tecla nunca resolveria:

          * MORTO -- cadaver nao monta. Levanta `PersonagemMortoNoPortao`, que a
            rotina converte em `RECUPERAR` (revive e recomeca).
          * EM BATALHA -- o jogo RECUSA montar em combate. Chama o
            destravamento, que mata mob a mob ate a flag baixar. Ver
            `combat.limpar_o_combate` e o log dos 24 minutos citado la.

        Qualquer outra causa (tecla errada, condicao do personagem que o bot nao
        conhece) continua com o comportamento antigo: o portao insiste e grita.
        O que muda e que agora o log diz O QUE FOI LIDO, em vez de repetir
        "continuo insistindo" ate a instancia expirar.
        """
        ctx = self.ctx

        state = ctx.snapshot()
        if state.dead:
            raise PersonagemMortoNoPortao(
                f"o personagem morreu esperando a montaria para {motivo} "
                f"({gasto:.0f}s, {ciclo} tentativas)"
            )

        em_batalha = ctx.memory.in_battle()

        # FORA DE COMBATE, o jogo as vezes CANCELA a montaria sozinho -- e andar
        # destrava. Ver `SEGUNDOS_ANTES_DE_CUTUCAR` para o log que mediu.
        #
        # `is False` e nao `is not True`: andar tem custo (puxa mob), entao
        # exige confirmacao POSITIVA de que nao ha combate. "Nao sei" mantem o
        # comportamento antigo, que e insistir na tecla.
        if em_batalha is False:
            self._passo_para_destravar_a_montaria(motivo, gasto)
            return

        if ciclo < CICLOS_ANTES_DE_DESTRAVAR:
            return

        # `is not True`: ilegivel (`None`) NAO autoriza sair batendo. Nao saber
        # se esta em combate e motivo para continuar insistindo na tecla, nunca
        # para gastar um minuto puxando mob -- ver `MEMORIA PRIMEIRO`, e a regra
        # de que "nao sei" nao decide nada.
        if em_batalha is not True:
            return

        if self.destravar_o_combate is None:
            # Sem o destravamento ligado, dizer a causa ja e o ganho: antes o
            # log nao trazia nem isso.
            ctx.log.warning(
                "Nao monto para %s ha %.0fs e estou EM BATALHA -- o jogo recusa "
                "a montaria em combate. Nao tenho destravamento ligado; sigo "
                "insistindo.", motivo, gasto,
            )
            return

        ctx.log.warning(
            "Nao monto para %s ha %.0fs porque estou EM BATALHA. Insistir na "
            "tecla nao resolve isso -- vou limpar o combate antes.",
            motivo, gasto,
        )
        self.destravar_o_combate(motivo)

    def _passo_para_destravar_a_montaria(self, motivo: str,
                                         gasto: float) -> bool:
        """Anda um passo curto. Andar destrava a montaria que o jogo cancelou.

        So depois de `SEGUNDOS_ANTES_DE_CUTUCAR` desde a primeira tentativa, e
        no maximo um passo por esse mesmo intervalo -- passo demais tira o
        personagem do ponto, e o remedio viraria o problema.

        A DIRECAO GIRA a cada passo (`BUSSOLA`). Sempre para o mesmo lado, uma
        parede faria todos os passos falharem em silencio; girando, o segundo
        tenta outro lado. Quem diz se andou e `_clicar_offset_e_verificar`, que
        mede a posicao antes e depois -- nao e clique no escuro.

        Devolve se o personagem realmente se moveu.
        """
        ctx = self.ctx
        agora = time.time()
        if gasto < SEGUNDOS_ANTES_DE_CUTUCAR:
            return False
        if agora - self._ultimo_passo_de_destrave < SEGUNDOS_ANTES_DE_CUTUCAR:
            return False

        onde = self.position()
        if onde is None:
            # Sem saber onde esta nao da para calcular o offset do minimapa.
            return False

        self._ultimo_passo_de_destrave = agora
        dx, dy = BUSSOLA[self._direcao_do_passo_de_destrave % len(BUSSOLA)]
        self._direcao_do_passo_de_destrave += 1

        andou = self._clicar_offset_e_verificar(
            onde, PASSO_PARA_DESTRAVAR_A_MONTARIA, dx, dy)
        ctx.log.info(
            "Nao monto para %s ha %.0fs e NAO estou em batalha: o jogo deve ter "
            "cancelado a montaria sozinho. Andei %s unidades de %s (%s) -- "
            "andar destrava esse bug.",
            motivo, gasto, PASSO_PARA_DESTRAVAR_A_MONTARIA, onde,
            "o personagem se moveu" if andou else "NAO saiu do lugar",
        )
        return andou

    def _manter_montaria(self) -> None:
        """Repõe a montaria DURANTE o trajeto. Chamado a cada volta do laço.

        Antes esta checagem morava na manutenção geral, que roda a cada 1,2 s, e o
        intervalo de remontagem se somava a ela: dava para andar mais de quatro
        segundos a pé sem que nada fosse tentado. Dentro da cave são quatro
        segundos de trem de mobs encostando.

        Agora a LEITURA é por volta (~0,12 s -- ler memória custa microssegundos)
        e só o TOQUE na tecla respeita intervalo, porque a tecla é um interruptor.
        """
        ctx = self.ctx
        if not ctx.settings.keys.mount:
            return

        if ctx.memory.is_mounted():
            if self._a_pe_desde:
                gasto = time.time() - self._a_pe_desde
                self._tempo_a_pe += gasto
                self._a_pe_desde = 0.0
                if gasto >= 3.0:
                    ctx.log.info("De volta à montaria depois de %.1fs a pé", gasto)
            return

        agora = time.time()
        if not self._a_pe_desde:
            self._a_pe_desde = agora
            self._avisou_a_pe_no_trajeto = False
            ctx.log.debug("A montaria caiu no meio do trajeto; remontando")

        # Sem checagem de batalha: aciona a tecla e deixa o jogo decidir. Se ele
        # recusar, o custo é um toque -- e o toque seguinte sai 2,5 s depois. Antes
        # havia uma checagem de combate aqui, e como a flag fica ligada quase toda
        # a travessia da cave, ela impedia justamente as remontagens que
        # importavam.
        if self._pode_tocar_na_montaria():
            self._tocar_na_montaria()

        # O trajeto seguir a pé por muito tempo tem que aparecer no log, senão
        # vira "demorou e não sei por quê".
        if (not self._avisou_a_pe_no_trajeto
                and agora - self._a_pe_desde >= AVISAR_A_PE_NO_TRAJETO):
            self._avisou_a_pe_no_trajeto = True
            ctx.log.info(
                "Já são %.0fs a pé no meio do trajeto, acionando a montaria a "
                "cada %.1fs sem sucesso. O trecho vai custar mais que o dobro.",
                agora - self._a_pe_desde, INTERVALO_REMONTAR,
            )

    def _manter_pet(self) -> None:
        """Vigia o pet a cada volta do laço. NÃO o reinvoca no meio do trajeto.

        A verificação é aqui porque é barata: uma leitura de ponteiro por volta,
        microssegundos. Detectar o pet caído no instante em que cai é o que permite
        explicar depois por que uma run rendeu menos.

        MAS A CORREÇÃO NÃO PODE SER AQUI, e isso é deliberado. Invocar o pet exige
        DESMONTAR -- montado o jogo ignora a tecla e não devolve erro. Desmontar no
        meio da cave é parar com o trem de mobs em cima, que é justamente o que a
        regra "não pare no meio da cave para alimentar o pet" evita. Trocar um pet
        caído por uma parada no corredor é um mau negócio.

        Então: avisa aqui, conserta no próximo ponto seguro (o preparo da run
        seguinte, ou antes de entrar na cave). Ler e não agir é a decisão certa
        quando agir custa mais que o problema.
        """
        ctx = self.ctx
        if not ctx.settings.keys.pet_summon:
            return

        if ctx.memory.pet_active():
            if self._pet_caiu_em:
                fora = time.time() - self._pet_caiu_em
                self._pet_caiu_em = 0.0
                self._avisou_pet_caido = False
                ctx.log.info("O pet voltou sozinho depois de %.1fs fora", fora)
            return

        if not self._pet_caiu_em:
            self._pet_caiu_em = time.time()
        if not self._avisou_pet_caido:
            self._avisou_pet_caido = True
            ctx.log.warning(
                "O PET CAIU no meio do trajeto. Não vou reinvocar aqui: invocar "
                "exige desmontar, e desmontar na cave é parar com os mobs em cima. "
                "Fica para o próximo ponto seguro."
            )

    def conferir_estado(self) -> tuple[tuple[int, int] | None, bool, bool]:
        """Uma leitura só de posição, montaria e pet. Para o monitor contínuo.

        Devolve `(posição, montado, pet_ativo)`. Existe para que quem precisa dos
        três não faça três travessias separadas de cadeia de ponteiro -- e para que
        o custo do monitor seja UM número medível em vez de uma suposição.

        NÃO BLOQUEIA e não aciona tecla nenhuma: é leitura pura. Quem decide agir é
        `_manter_montaria` / `_manter_pet`.
        """
        m = self.ctx.memory
        return (m.position(), m.is_mounted(), m.pet_active())

    def _resumo_da_montaria(self) -> str:
        """Quanto do trajeto foi a pé. Vazio quando foi tudo montado.

        Entra na linha de conclusão do trajeto porque é o indicador direto da
        exigência: trajeto com tempo a pé é trajeto que custou mais do que devia,
        e o número diz de quanto foi o prejuízo.
        """
        a_pe = self._tempo_a_pe
        if self._a_pe_desde:
            a_pe += time.time() - self._a_pe_desde
        return f" | {a_pe:.0f}s a pé" if a_pe >= 0.5 else ""

    def ensure_mounted(self, timeout: float = 12.0) -> bool:
        ctx = self.ctx
        if self._sem_tecla_de_montaria("montar"):
            # Antes devolvia True aqui -- "não tem tecla, então está tudo certo".
            # Não está: mentir neste ponto fazia o bot atravessar a cave a pé sem
            # nenhuma linha de log explicando por quê.
            return False
        if not ctx.memory.critical_ok():
            ctx.log.warning(
                "Sem memória para confirmar a montaria; acionando uma vez e "
                "seguindo, em vez de alternar montar/desmontar."
            )
            self._tocar_na_montaria()
            ctx.tick(1.0)
            return False
        if ctx.memory.is_mounted():
            return True

        limite = time.time() + timeout
        while time.time() < limite:
            # Respeita o intervalo entre toques: se alguém acabou de acionar a
            # tecla, apertar agora DESMONTARIA o personagem em vez de montar.
            if self._pode_tocar_na_montaria():
                self._tocar_na_montaria()
            ctx.tick(1.0)
            if ctx.memory.is_mounted():
                ctx.log.debug("Montaria ativa (%s%% de velocidade)",
                              ctx.settings.mount_speed_pct)
                return True
        ctx.log.warning("Não conseguiu montar em %.0fs", timeout)
        return False

    def ensure_dismounted(self, timeout: float = 10.0,
                          permitir_em_batalha: bool = False) -> bool:
        ctx = self.ctx
        # Sem tecla não há montaria para descer: aqui devolver True é correto.
        if not ctx.settings.keys.mount:
            return True
        if not ctx.memory.critical_ok():
            return False
        if not ctx.memory.is_mounted():
            return True

        # =================================================================
        # BLOQUEIO: não desmontar se estiver em batalha.
        #
        # `permitir_em_batalha=True` é a exceção pedida pelo usuário, e só os
        # DOIS pontos de luta ligam: o waypoint dos 4 mobs antes do boss e o
        # waypoint do boss. Neles desmontar em combate é o OBJETIVO -- montado
        # o jogo ignora a tecla de skill, e são os únicos 2 momentos em que o
        # personagem precisa atacar. Todo o resto (poção, curar, preparo)
        # continua segurando o desmonte enquanto a flag de combate estiver
        # ligada.
        # =================================================================
        if ctx.memory.in_battle() and not permitir_em_batalha:
            ctx.log.info("Em combate: ignorando o pedido para desmontar.")
            return False
        # =================================================================
            
        limite = time.time() + timeout
        primeiro = True
        while time.time() < limite:
            # No PRIMEIRO toque não há ambiguidade: a memória confirma montado, e
            # um toque nessa situação só pode descer. O intervalo vale para as
            # repetições, onde o toque anterior pode ainda estar sendo processado.
            #
            # Isso importa porque quem desmonta costuma ter pressa e prazo curto
            # -- a parada para poção dá 4 s, e gastar 2,5 desses esperando o
            # intervalo faria a poção não ser tomada com o HP baixo.
            if primeiro or self._pode_tocar_na_montaria():
                self._tocar_na_montaria()
                primeiro = False
            ctx.tick(0.75)
            if not ctx.memory.is_mounted():
                return True
        return False
