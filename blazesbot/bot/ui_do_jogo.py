"""
As JANELAS DO JOGO: painel de arredores, diálogos de NPC, câmera e minimapa.

=========================================================================
O QUE ESTE MÓDULO É, E O QUE ELE NÃO É
=========================================================================

Aqui mora COMO se opera a interface do Talisman Online -- e nada sobre PARA QUÊ.
Abrir o painel de arredores, trocar para a aba NPC, digitar uma busca, conferir
o resultado lido da memória, caminhar até ele, clicar com o botão direito no NPC,
esperar o diálogo abrir, achar um link pelo texto e clicar nele. Isso é do JOGO.

QUAIS npcs, QUAIS links e QUAIS coordenadas é do ECOSSISTEMA, e mora lá:

    bot/bc/ui_service.py   o Transport Fay para Ghost Din Woods, o Skull Herald
                           da entrada, o Altar Stone, a saída da Bewitcher Cave
    bot/hh/entrada.py      o mesmo Fay para West Suburb of Stone City, a Mutual
                           Quest Woman e o Elite Axe Monk Soldier da HH

**DEPENDÊNCIA CRUZADA: mexer aqui mexe nos dois ecossistemas.** Subiu de
`bot/bc/ui_service.py` em 01/09/2026, quando a HH mostrou que a rota dela é a
MESMA máquina com outros nomes.

=========================================================================
COMO SE CHEGA NUMA CAVE, DE VERDADE
=========================================================================

O caminho não é uma coordenada nem uma lista de waypoints. É uma sequência de
NPCs, e cada etapa é uma janela do jogo. Na Bewitcher Cave:

  1. Painel Surroundings, aba NPC, buscar "Fay"
     -> aparece "Transport Fay [178,-518]" (em Stone City)
  2. Clicar no resultado -> o personagem caminha até o NPC
  3. Clique DIREITO no NPC -> abre a janela Dialogue
  4. Na lista "Transport to", clicar no destino -> teleporta
  5. Painel Surroundings de novo, buscar o NPC da porta
  6. Clicar no resultado -> caminha até ele
  7. Clique DIREITO -> Dialogue -> clicar no link de entrar

A HH percorre exatamente estes sete passos com outros nomes -- e com um oitavo
que a BC nunca precisou: **ROLAR a lista do diálogo**, porque o destino dela
(`West Suburb of Stone City`) não cabe na primeira tela.

DETALHES QUE IMPORTAM

* A lista abre na aba **Player**. Os NPCs só aparecem depois de clicar na aba
  **NPC** -- sem isso a busca não acha nada.
* A interação com NPC é com o botão **DIREITO**.
* O primeiro resultado da busca pode ser lido da memória, com nome e
  coordenadas -- dá para conferir que a busca achou o certo antes de clicar.
* **View Reset** antes de qualquer clique posicional. Ele recentra a câmera; sem
  isso, clique em NPC é loteria.

=========================================================================
A ENTRADA É DISPUTADA: A TENTATIVA TEM QUE CUSTAR ~1 SEGUNDO
=========================================================================

Várias contas tentam entrar na mesma hora e a vaga é de quem clica primeiro. A
versão anterior levava 10 a 14 segundos por tentativa -- não porque clicava
devagar, mas porque REDESCOBRIA tudo em cada volta:

    procurar a janela de diálogo por imagem (até 4 x 1,3 s)
    procurar o link por imagem            (até 3 x 0,8 s)
    fechar o diálogo                      (0,6 s)
    esperar a instância carregar          (3,0 s)
    esperar entre tentativas              (5,0 s)

Nesse tempo outra conta entra no lugar.

A correção é lembrar. Na PRIMEIRA tentativa o bot localiza o NPC e o link por
imagem e GUARDA as duas coordenadas. Da segunda em diante ele só repete os dois
cliques e confere a localização: clique direito, confere o diálogo, clique no
link, olhar o resultado -- cerca de 1 segundo por volta. A redescoberta só volta a
acontecer se três tentativas seguidas falharem, o que indica que a câmera ou a
posição mudaram.

DUAS CONFERÊNCIAS QUE A TENTATIVA RÁPIDA NÃO PODE DISPENSAR

Rápido não quer dizer cego. Antes de clicar, a POSIÇÃO; entre os dois cliques, o
DIÁLOGO. As duas existem pelo mesmo motivo: o clique no link é posicional na cena
3D, e quando ele erra, ele erra no chão -- e clicar no chão faz o personagem
ANDAR, saindo justamente da coordenada de onde os cliques funcionam. Uma tentativa
perdida custa um segundo; um clique no chão condena todas as seguintes.
"""
from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from contextlib import contextmanager

from ..core import esconder_jogadores, halo, janelas_abertas
from ..core.coords import TEMPLATE_ANCHORS
from ..core.rota import distancia
from ..core.vision import capture_window, find_template
from ..core.zones import distancia_linear
from .context import BotContext, StopRequested
from .navegacao import Navigator

ANCHOR_THRESHOLD = 0.80

# O ponto do link do diálogo: coordenada fixa, ou uma função que a descobre
# com o diálogo JÁ ABERTO -- ver `_abrir_dialogo_e_clicar`.
PontoDoLink = tuple[int, int] | Callable[[], tuple[int, int] | None]


# Falhas seguidas na tentativa rápida antes de redescobrir tudo por imagem.
FALHAS_ANTES_DE_REDESCOBRIR = 5

# ===========================================================================
# O ORÇAMENTO DA DISPUTA PELA VAGA NA INSTÂNCIA
# ===========================================================================
#
# A meta é SEIS tentativas em dez segundos, e ela vira uma conta fechada:
#
#     10,00 s / 6 tentativas ........ 1,667 s por volta
#     ação mecânica medida .......... 1,060 s   (clique + confirmação; é do jogo)
#     ------------------------------------------
#     sobra para reconhecer e reagir .. 0,607 s
#
# Então o intervalo entre "a tentativa terminou" e "a próxima começou" não pode
# passar de 0,60 s. É orçamento, não preferência: acima disso a meta não fecha
# por aritmética.
#
# ONDE ESTAVAM OS SEGUNDOS PERDIDOS. Medindo 4 tentativas em 15 s (3,75 s por
# volta) sobrava 2,69 s de gordura por volta, e ela não estava nas esperas desta
# seção -- estava na REDESCOBERTA. A cada três tentativas sem entrar, o bot
# refazia tudo por imagem: `falar_com_npc` dá até quatro cliques direitos com
# 1,3 s fixos entre eles, mais `clicar_link` com 0,8 a 1,5 s por volta. Uma
# tentativa dessas custa 5 a 10 s. Está no log:
#
#     14:36:04  Clique direito no NPC em (482, 305)
#     14:36:06  Clique direito no NPC em (482, 305)
#     14:36:07  Clique direito no NPC em (482, 305)
#     14:36:09  Clique direito no NPC em (482, 305)
#     14:36:10  Não abri o diálogo do Skull Herald
#
# Seis segundos numa única tentativa. E ela era disparada pelo contador errado --
# ver `registrar_falha_de_entrada`.
#
# A REGRA GERAL QUE SUBSTITUI AS ESPERAS FIXAS: esperar EVENTO, com teto. O teto
# preserva o pior caso; o evento devolve o caso comum em uma ou duas leituras.

# Diálogo do NPC aparecer. Era 0,30 s fixos, gastos inteiros mesmo quando o
# diálogo abria em 60 ms. Cada volta custa uma captura de tela, por isso o passo
# não é menor que isto.
PASSO_DA_ESPERA_DO_DIALOGO = 0.08
# ZOOM DO MINIMAPA -- cinco níveis, o padrão no meio.
#
# Do padrão até um extremo são 2 cliques; de um extremo ao outro, 4. Os botões
# PARAM no batente, e é isso que permite padronizar sem ler o estado atual.
#
# CINCO cliques até o batente e não quatro: quatro bastam vindo de qualquer
# nível, e o quinto é a folga para um clique engolido pelo cliente. Custa 0,05 s
# e a alternativa é ficar um nível fora do padrão sem ninguém perceber.
CLIQUES_ATE_O_BATENTE = 5
CLIQUES_DO_BATENTE_ATE_O_PADRAO = 2
ENTRE_CLIQUES_DE_ZOOM = 0.025

# ===========================================================================
# TETO DA ESPERA DO DIÁLOGO -- ajustado pelo que foi MEDIDO, não chutado
# ===========================================================================
#
# O PROBLEMA, medido no `logs/dev/blazes-dev.jsonl` da entrada na cave:
#
#     cliques DIREITOS       272
#       não abriram diálogo  167   (61%)
#     cliques ESQUERDOS      105
#
# Sessenta e um por cento das tentativas eram jogadas fora. Havia duas
# explicações possíveis e o log não separava as duas: ou o clique errou o NPC
# (nada a fazer), ou o diálogo ABRIU e o teto de 0,35 s expirou antes -- e aí a
# tentativa foi desperdiçada por impaciência.
#
# POR QUE UM TETO FIXO NÃO RESOLVE NENHUM DOS DOIS LADOS: curto demais joga
# fora tentativa boa; longo demais paga o teto inteiro em toda tentativa que
# nunca ia abrir. E o valor certo depende da máquina e de quantos clientes estão
# abertos -- não existe número universal para cravar aqui.
#
# ENTÃO O TETO APRENDE. Começa PERMISSIVO (não se joga fora tentativa por causa
# de um palpite) e vai apertando conforme as aberturas de verdade são
# cronometradas: fica um pouco acima da pior abertura já vista. Se o diálogo
# sempre abre em 120 ms, o teto desce sozinho e as falhas ficam baratas; se de
# vez em quando ele demora 700 ms, o teto sobe e essas tentativas param de ser
# desperdiçadas.
LIMITE_INICIAL_DA_ESPERA_DO_DIALOGO = 0.65

# Piso: o valor que valia antes. Abaixo disto não se aperta nem com evidência --
# a medição é por captura de tela, que tem granularidade própria.
LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO = 0.180

# Teto do teto. Passado disto, o diálogo não vai abrir mesmo, e insistir só
# atrasa a tentativa seguinte -- que na disputa da cave é o que importa.
LIMITE_MAXIMO_DA_ESPERA_DO_DIALOGO = 0.60

# Folga sobre a pior abertura observada. 1,6 dá espaço para uma variação sem
# reabrir a porta para o teto inteiro.
FOLGA_SOBRE_O_PIOR_DIALOGO = 2.0

# Quantas aberturas guardar. Poucas de propósito: o que interessa é a condição
# ATUAL da máquina (quantos clientes abertos, quanto o servidor está demorando),
# não a média histórica.
MEMORIA_DE_ABERTURAS_DO_DIALOGO = 12

_ABERTURAS_DO_DIALOGO: deque[float] = deque(maxlen=MEMORIA_DE_ABERTURAS_DO_DIALOGO)

# ===========================================================================
# O TETO TAMBÉM APRENDE COM A FALHA -- 07/09/2026
# ===========================================================================
#
# MEDIDO NO LOG DE PRODUÇÃO (13 h, conta `creubo`):
#
#     08:14:05  o teto congela em 427 ms
#     08h  427ms x 2733   | entradas na cave: 0
#     09h  427ms x 3574   | entradas na cave: 0
#     10h  427ms x 3573   | entradas na cave: 0
#     11h  427ms x 3569   | entradas na cave: 0
#     12:05:07  um diálogo abre  ->  DENTRO da cave 25 s depois
#
# Nas horas saudáveis o teto varia o tempo todo (180, 286, 327, 650...) porque
# cada abertura entra na amostra. A partir das 08:14 ele fica IDÊNTICO por
# 3 h 51 min e 13.449 tentativas seguidas -- e teto adaptativo que não se mexe é
# a assinatura de uma realimentação que morreu.
#
# A CAUSA É ESTRUTURAL, não é o número: a amostra só entra quando o diálogo
# ABRE. Se a latência real sobe acima do teto, toda tentativa é reprovada, e
# uma tentativa reprovada não produz amostra. **A medição que levantaria o teto
# só pode ser feita pelo sucesso que o próprio teto impede.** A conta ficou
# quatro horas presa num laço que se alimentava sozinho, e só saiu quando uma
# abertura por acaso veio abaixo dos 427 ms.
#
# ENTÃO A FALHA TAMBÉM PASSA A INFORMAR. Falhas CONSECUTIVAS afrouxam o teto,
# em degraus, até um limite de desespero; qualquer abertura zera a contagem e
# devolve o teto aprendido. É a única saída que não depende de sorte.
#
# POR QUE 5 FALHAS: é o mesmo número de `FALHAS_ANTES_DE_REDESCOBRIR`, e pela
# mesma razão -- abaixo disso é ruído normal de disputa (o clique erra o NPC, o
# servidor engasga), acima disso é padrão. Nas horas saudáveis nunca houve 5
# falhas seguidas sem uma abertura no meio.
FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR = 5

# Quanto o teto dobra a cada degrau de falhas.
FATOR_DE_AFROUXAMENTO = 2.0

# O teto do desespero. Passado daqui não é mais latência: é NPC errado, cliente
# preso ou tecla que não chega -- e nenhum deles se resolve esperando.
#
# 1,2 s, e o número é do council (06/09/2026): *"teto duro de 1,0-1,2 s, não
# 2 s, para um NPC competitivo"*. Bate com o medido -- o maior teto que o
# aprendizado já produziu foi 650 ms (o `LIMITE_INICIAL`), então o dobro disso
# cobre qualquer abertura legítima com folga. Passado daí não é lentidão, e
# esperar 2 s só faz a conta perder a disputa duas vezes.
TETO_DO_DESESPERO = 1.2


def limite_da_espera_do_dialogo() -> float:
    """O teto de agora, derivado das aberturas já cronometradas."""
    if not _ABERTURAS_DO_DIALOGO:
        return LIMITE_INICIAL_DA_ESPERA_DO_DIALOGO
    alvo = max(_ABERTURAS_DO_DIALOGO) * FOLGA_SOBRE_O_PIOR_DIALOGO
    return min(LIMITE_MAXIMO_DA_ESPERA_DO_DIALOGO,
               max(LIMITE_MINIMO_DA_ESPERA_DO_DIALOGO, alvo))

# Diálogo aparecer na REDESCOBERTA, depois de cada clique direito. Era `tick(1.3)`
# fixo, quatro vezes -- 5,2 s por tentativa no pior caso. O teto continua largo
# porque ali o clique pode ter errado o NPC de verdade, mas quando acerta a volta
# termina na primeira leitura.
LIMITE_DA_ESPERA_DO_DIALOGO_LENTA = 0.65

# Folga da REDESCOBERTA sobre o teto normal. Ali o clique pode ter errado o NPC
# de verdade, então cabe esperar mais -- mas não um valor fixo e cego.
#
# Medido no log: `Diálogo NÃO abriu em 1300 ms (teto)` e, no clique seguinte, no
# MESMO ponto, `Diálogo abriu em 314 ms`. Os 1300 ms não compraram nada: o
# diálogo daquele clique não ia abrir. Como é o mesmo diálogo e o mesmo cliente,
# a latência real já está medida -- basta dar folga sobre ela.
FOLGA_DA_REDESCOBERTA = 1.5


def limite_da_espera_do_dialogo_lenta() -> float:
    """Teto da redescoberta: o teto normal com folga, limitado ao valor antigo."""
    return min(LIMITE_DA_ESPERA_DO_DIALOGO_LENTA,
               limite_da_espera_do_dialogo() * FOLGA_DA_REDESCOBERTA)

# Servidor processar o pedido de entrada. Zero na disputa: quem confirma a entrada
# é o laço da rotina, que já fica lendo a posição em fatias curtas -- essa leitura
# É a espera, e ela termina no instante em que a entrada acontece. O valor abaixo
# vale para os outros pares de clique de NPC (Altar Stone, saída), onde não há
# ninguém observando o resultado em fatias.
ESPERA_DEPOIS_DO_LINK = 0.200

# ===========================================================================
# CLIQUE ENGOLIDO = JANELA NA FRENTE. E O GUARDA VALE PARA A SAIDA TAMBEM
# ===========================================================================
#
# Relato do usuario em 07/09/2026, com print: *"hoje na entrada de BC e feito
# uma verificacao se ficou alguma janela aberta, e importante tambem verificar
# na saida, pois acabei de chegar e ver o bot parado na saida, pois a janela
# System estava aberta"*.
#
# Estava certo, e o log mostra o tamanho: **305 cliques direitos em (616, 326)
# que nao abriram o dialogo** na fase SAIR, contra 267 saidas concluidas.
# `desobstruir_a_cena` existia e era chamada em UM lugar so -- a entrada.
#
# E A CAUSA TAMBEM ESTA NO LOG. Os 3 episodios de saida travada que o log
# mostra por inteiro foram TODOS precedidos, ~2,5 min antes, por
# `_travar_no_alvo_proibido` apertando ESC as cegas no waypoint dos guardas.
# Sem mira, ESC abre o MENU DO SISTEMA -- e ele atravessa a luta do boss.
# Aquela causa foi consertada em `combate._travar_no_alvo_proibido`; este bloco
# e a segunda linha de defesa, porque a proxima janela vai vir de outro lugar.
#
# POR QUE NO FUNIL, E NA FALHA: os SEIS pares de clique de NPC do bot passam
# por `_abrir_dialogo_e_clicar` (link da cave, Altar Stone, saida, Rich, HH).
# Um guarda aqui cobre todos; um guarda na saida cobriria a saida.
#
# E POR QUE NA FALHA, e nao antes do clique: `desobstruir_a_cena` documenta que
# o guarda e POR EVENTO e nao por clique, porque a disputa da entrada dispara
# dois cliques por segundo e uma captura por tentativa custaria caro no unico
# trecho onde o projeto cortou espera para caber. O clique ENGOLIDO e o evento:
# no caminho feliz nao custa nada, e quando falha a tentativa seguinte encontra
# a tela limpa.
#
# Estrangulado porque janela NAO aparece sozinha: entre duas tentativas
# separadas por segundos nada mudou, a menos que alguma acao tenha aberto algo.
# Uma captura (~10 ms) a cada 3 s e 0,3% do trecho, contra uma por tentativa.
INTERVALO_DO_GUARDA_DE_JANELA = 3.0

# ===========================================================================
# BUSCA NO PAINEL DE ARREDORES -- rápida porque agora existe conferência
# ===========================================================================
#
# Estes números só puderam encolher depois que o resultado passou a ser LIDO da
# memória e comparado com o que se procurava. Enquanto a busca era às cegas, a
# lentidão era o único seguro contra caractere perdido; com a conferência, um erro
# de digitação reprova e a tentativa seguinte redigita.
# ===========================================================================
# O QUE AINDA ESTAVA LENTO, E POR QUE
# ===========================================================================
#
# Depois da primeira rodada de ajustes a busca continuou parecendo lenta na tela, e
# o motivo não eram os números da digitação -- eram TRÊS esperas que não tinham
# como saber quando parar:
#
#   1. ABRIR O PAINEL ..... 1,2 s fixos depois de clicar no botão. O painel abre
#                           muito antes disso na maioria das vezes, e quando não
#                           abre o bot esperava o tempo todo para depois falhar.
#                           Virou espera POR EVENTO: pergunta se o painel apareceu
#                           a cada 0,08 s e segue no instante em que ele aparece.
#   2. TROCAR DE ABA ...... 0,7 s fixos. A âncora do painel não se move ao trocar
#                           de aba, e o campo de busca existe nas duas -- não havia
#                           nada para esperar além de a aba ser processada.
#   3. O RESULTADO ........ 1,5 s de teto. Se a leitura de arredores por memória
#                           NÃO funcionar neste cliente, esse teto era gasto
#                           INTEIRO em toda busca, três vezes por run. É quase
#                           certo que era isso que aparecia como "fica alguns
#                           segundos ali parado". Agora o bot aprende: depois de
#                           duas buscas em que a leitura nunca respondeu, ele para
#                           de esperar por ela.
#
# Somadas, eram cerca de 3,4 s por busca que não dependiam do jogo.

# Passo e teto da espera pelo painel aparecer. Cada volta custa uma captura de
# tela mais um casamento de template, por isso o passo não é menor que isto.
PASSO_DA_ESPERA_DO_PAINEL = 0.08
# O teto é EXATAMENTE a espera fixa que havia antes (1,2 s), e isso é de propósito:
# assim a mudança transforma um CUSTO em um LIMITE. No caminho comum o painel abre
# em duas leituras; no pior caso gasta o mesmo que gastava antes. Com um teto maior
# o caminho de falha ficaria mais lento que o original, porque `abrir_surroundings`
# tenta três vezes -- 3 x 2,0 s seria pior que os 3 x 1,2 s de antes.
LIMITE_DA_ESPERA_DO_PAINEL = 0.80

# Assentar depois de clicar na aba NPC. Não é "esperar a aba renderizar": é só dar
# ao cliente uma volta de laço para processar o clique antes do próximo.
ESPERA_DA_TROCA_DE_ABA = 0.05

# ENTRE CLICAR NO CAMPO E DIGITAR NÃO HÁ ESPERA, e isso não é otimismo: o input
# deste bot é `SendMessage`, que é SÍNCRONO -- quando `click` retorna, o cliente já
# processou a mensagem e o foco já está no campo. Os 0,15 s que havia aqui eram
# perda pura. Se algum dia isso se mostrar errado, a conferência do resultado
# reprova a busca e a tentativa seguinte redigita.

# Quantos BACKSPACE para limpar o campo. O texto buscado é curto ("Fay", "Skull",
# "Rich"), então 8 cobre com folga -- e cada tecla custa um ida-e-volta de mensagem.
LIMPEZA_DO_CAMPO = 8

# Intervalo entre caracteres. 40 ms davam meio segundo só para digitar
# "Transport Fay".
DIGITACAO_POR_CARACTERE = 0.01

# De quanto em quanto tempo perguntar à memória se o resultado apareceu, e por
# quanto tempo insistir. Substitui uma espera fixa de 0,9 s.
PASSO_DA_ESPERA_DO_RESULTADO = 0.08
LIMITE_DA_ESPERA_DO_RESULTADO = 0.80

# Quando a leitura de arredores por memória não funciona neste cliente, a lista
# ainda precisa de um instante para filtrar depois da digitação -- clicar no
# primeiro resultado antes disso pegaria a linha ANTIGA e mandaria o personagem
# para o NPC errado. Esta é a única espera que sobra nesse caso.
#
# ESTE NÚMERO JÁ FOI 0,35 s, E ERA CHUTE MEU. O valor original do bot era 0,9 s
# fixos, e encurtá-lo só é seguro quando existe CONFERÊNCIA -- que é justamente o
# que não existe neste caminho. Sem conferência, clicar cedo demais clica na linha
# que ainda está na tela, o personagem caminha até o NPC errado e a run se perde
# andando. Meio segundo economizado não paga uma run.
#
# Volta a ser o valor conservador. O caminho rápido continua rápido: quando a
# memória lê, a espera termina na primeira leitura (~0,1 s) e esta constante nem é
# usada.
# Tempo de a LISTA FILTRAR depois de digitar, quando não há leitura para
# conferir. Era 0,9 s escolhido no escuro.
#
# Foi reduzido porque agora existe uma REDE: `ir_para_resultado` confere se o
# personagem saiu do lugar depois do clique. Se esta espera ficar curta demais e
# o clique cair antes de a lista filtrar, o personagem não anda -- e isso aparece
# no log em vez de virar viagem para o lugar errado em silêncio.
#
# Encurtar sem essa rede seria trocar tempo por risco: clicar numa lista que
# ainda mostra o resultado ANTERIOR manda o personagem para outro lugar.
ESPERA_CEGA_DO_RESULTADO = 0.300

# Quantas buscas seguidas sem a memória responder antes de desistir dela. Duas, e
# não uma, porque uma busca pode estourar o teto por lentidão momentânea da lista;
# duas seguidas significam que o leitor não vale neste cliente.
BUSCAS_ANTES_DE_DESISTIR_DA_LEITURA = 3

# O QUE JÁ SE SABE SOBRE ESTE CLIENTE, por hwnd e válido pelo PROCESSO INTEIRO.
#
# Medido no log da run com milissegundos: `surroundings_first()` NÃO responde
# neste cliente -- aparece "A leitura de arredores por memória não respondeu em
# 2 buscas seguidas". O bot aprende isso e para de esperar... mas o contador
# vivia na instância do `UIService`, que nasce de novo a cada run. Resultado: a
# mesma lição era paga OUTRA VEZ toda run, 1,5 s por busca até reaprender.
#
# Guardando por hwnd no módulo, a lição atravessa as runs: aprende uma vez por
# cliente e nunca mais. Uma leitura boa a qualquer momento zera a contagem --
# se o leitor voltar a funcionar, a conferência volta com ele.
_BUSCAS_SEM_LEITURA: dict[int, int] = {}


def esquecer_janela(hwnd: int) -> None:
    """Apaga a lição aprendida sobre ESTA janela. Chamado quando ela morre.

    Sem isto o dicionário cresce uma entrada por relogin e nunca encolhe -- mas o
    problema pior não é memória, é CORREÇÃO: o Windows RECICLA valores de hwnd.
    Uma janela nova que receba um número já usado herdaria o contador de "buscas
    sem leitura" da janela anterior e desligaria a conferência do leitor de
    arredores desde o primeiro instante, sem ter medido nada nesta janela.

    A lição existe para atravessar RUNS da mesma janela (era isso que a versão
    por instância errava), não para atravessar JANELAS.
    """
    _BUSCAS_SEM_LEITURA.pop(hwnd, None)

# Depois de clicar no resultado o personagem já saiu andando -- o pathfinding do
# jogo assumiu. Não há motivo para segurar a rotina aqui; era 1,0 s.
# Depois de clicar no resultado, o personagem COMEÇA A ANDAR -- e isso é
# observável na memória, de graça. Então não se espera um tempo: pergunta-se se
# ele saiu do lugar. `PASSO` é o intervalo entre leituras (posição vem da
# memória, custa microssegundos); `LIMITE` é o teto para o caso de o clique ter
# caído no vazio, e nesse caso a espera cega antiga teria seguido em frente sem
# ninguém saber.
PASSO_DA_ESPERA_DO_ANDAR = 0.04
LIMITE_DA_ESPERA_DO_ANDAR = 0.40
ESPERA_DEPOIS_DE_CLICAR_NO_RESULTADO = 0.150

# ===========================================================================
# O AUTO-PATH DO SURROUNDINGS É CONFIRMADO POR COORDENADA
# ===========================================================================
#
# Relato do usuário em 25/08/2026, sobre a ida até a Fay: ele está "clicando
# fora e indo para o lugar levemente errado, sendo que se deixa o auto path do
# Surroundings ele já para no lugar correto".
#
# O clique no resultado é ESQUERDO, e clique esquerdo fora do painel é ANDAR. O
# ponto vem de `_pontos("surroundings")`, que acha o template do painel (limiar
# 0,80, e `find_template` devolve o CENTRO do match) e soma um deslocamento fixo
# de (-97, +99). A 99 px de distância, um match alguns pixels deslocado põe o
# clique fora da linha do resultado -- e o personagem caminha para aquele ponto
# da tela em vez de para o NPC.
#
# E a confirmação de então NÃO PEGAVA ISSO: ela esperava a POSIÇÃO MUDAR. Clique
# errado no chão também muda a posição. A verificação não sabia distinguir
# auto-path de clique perdido.
#
# Agora a confirmação é a coordenada que o próprio painel informou (o texto vem
# no formato `Nome [x,y]`): chegou perto dela, deu certo. Ficou longe E PARADO,
# o clique errou.
PROXIMIDADE_DO_DESTINO = 8

# Quantas leituras iguais seguidas contam como PARADO.
#
# Andando não se reabre nada -- regra do usuário: se está andando, provavelmente
# está indo para o lugar correto; se parou, é porque não vai mais andar. Três
# leituras evitam confundir um quadro de latência com parada de verdade.
LEITURAS_PARA_CONSIDERAR_PARADO = 3

# ===========================================================================
# INTERRUPTOR: a coordenada do painel CONFIRMA a chegada?
# ===========================================================================
#
# `False` = ela só MEDE (vai para o log) e quem decide é "parou de andar".
# `True`  = parar longe do destino reabre o painel e tenta de novo.
#
# DESLIGADO POR MEDIÇÃO EM PRODUÇÃO, 25/08/2026. Ligado por algumas horas, o
# usuário relatou: *"as aberturas do Surroundings começaram a ser constantes,
# principalmente na hora de ir para a Fay, aí fica entrando em loop e andando
# para lugar errado."*
#
# A causa provável está em `Memory._coord`: a posição do personagem é lida e
# DIVIDIDA POR 20, enquanto o `[x,y]` do painel vem do texto da interface.
# Ninguém provou que os dois vivem no mesmo espaço -- e se não vivem, a
# distância nunca fecha, toda chegada vira "longe", e cada reabertura é mais um
# clique com chance de cair fora do painel e mandar o personagem andar.
#
# COMO LIGAR COM SEGURANÇA: a linha `Auto-path até ...` grava, a cada chegada, a
# posição em que o personagem parou e a coordenada que o painel prometeu. Se em
# algumas runs a distância aparecer consistentemente pequena, os dois espaços
# são o mesmo e este interruptor pode ir para `True`. Ligar antes disso é
# reintroduzir o loop.
CONFIRMAR_CHEGADA_POR_COORDENADA = False

# ===========================================================================
# CADÊNCIA MÍNIMA ENTRE UM USO DO PAINEL DE ARREDORES E O SEGUINTE
# ===========================================================================
#
# Relato do usuário em 25/08/2026:
#
#     *"tem vezes que fica abrindo, filtrando, clicando para dar o auto path,
#      aí fechando e repetindo o processo tudo bem rápido, o que não chega a
#      necessariamente atrapalhar, mas pode ser MAL VISTO pelo usuário final"*
#
# `buscar_npc` retenta até 3 vezes, e cada volta refaz o ciclo inteiro. Quando
# as três caem em sequência, o painel abre e fecha três vezes em poucos
# segundos -- e isso não parece alguém jogando.
#
# NÃO É UM PROBLEMA DE CORREÇÃO, e por isso não vale pagar por ele no caminho
# feliz. A espera é o RESTO do intervalo, não o intervalo: entre um uso e o
# seguinte costumam passar minutos (Fay, entrada da cave, vendedor -- três usos
# por run), e nesses casos o resto é negativo e ninguém espera nada. Só a
# REPETIÇÃO rápida paga.
#
# NÚMERO COSMÉTICO, e é honesto dizer: não há medição atrás dele porque a
# pergunta que ele responde não é técnica ("com que rapidez o painel pode
# reabrir?") e sim de aparência ("a partir de quanto isso parece um robô?").
# É para o usuário ajustar se achar pouco ou muito.
INTERVALO_ENTRE_USOS_DO_PAINEL = 2.0

# Teto de aberturas do painel por TRAJETO.
#
# POR QUE UM ORÇAMENTO, E NÃO SÓ A CADÊNCIA ACIMA. As tentativas eram ANINHADAS:
# `garantir_coordenada_da_entrada` retenta 3x, e cada volta chama
# `ir_ate_o_npc_da_cave` -> `buscar_npc`, que retenta outras 3x. Nove aberturas
# no pior caso, e ninguém escolheu esse nove -- ele é o PRODUTO de duas camadas
# que não sabem uma da outra. Espaçar isso com a cadência só transformaria um
# sintoma visual em 18 segundos parado na porta de uma BC disputada.
#
# NÚMERO DERIVADO, não medido: 1 (caso normal) + os 3 modos de falha que este
# arquivo já documenta -- painel que abre depois do teto da espera, busca que
# veio com nome errado, e resultado que não apareceu.
#
# Contado num lugar só (`_aberturas_do_trajeto`) e zerado por quem INICIA um
# trajeto. Estourado, `abrir_surroundings` devolve None -- e aí os laços de
# retentativa que já existem param sozinhos, sem precisar desmontá-los.
ABERTURAS_POR_TRAJETO = 4


# Passo da leitura de posição enquanto se espera a chegada. Ler memória custa
# microssegundos; o que se paga aqui é o `tick`, e é ele que faz a parada do
# usuário responder na hora.
PASSO_DA_ESPERA_DA_CHEGADA = 0.25

# Fechar o painel. Era 0,6 s.
# Fechar o painel também é observável: `_pontos("surroundings")` devolve None
# quando ele sumiu da tela. O teto existe porque a leitura é por imagem e pode
# não estar disponível (cliente sem captura) -- aí vale a espera de antes.
# Quantas vezes reler a tela antes de aceitar "não consigo ver o painel".
#
# EXISTE POR UM DEFEITO MEDIDO. `fechar_surroundings` tratava "não consigo VER o
# painel" como "o painel não está aberto" e voltava em silêncio achando que
# tinha fechado. Print do usuário em 26/08/2026: personagem na coordenada exata
# da entrada (1395,-635), alvo selecionado, time formado -- e o Surroundings
# aberto na frente, engolindo o clique a run inteira.
#
# O caso real é um QUADRO ruim (animação, névoa, rumor no chat passando por
# cima), não cegueira permanente: reler três vezes custa ~0,1 s e resolve.
LEITURAS_ANTES_DE_DESISTIR_DE_VER = 3

PASSO_DA_ESPERA_DO_FECHAMENTO = 0.04
LIMITE_DA_ESPERA_DO_FECHAMENTO = 0.40
ESPERA_DEPOIS_DE_FECHAR = 0.20

ESPERA_ANTES_DE_CONFERIR = 0.15  # a localização mudar


# ===========================================================================
# ROLAR A LISTA DO DIÁLOGO
# ===========================================================================
#
# A Bewitcher Cave nunca precisou: `Ghost Din Woods` está na parte visível da
# lista do Transport Fay. A HH precisa, porque `West Suburb of Stone City` só
# aparece rolando -- ver `rolar_o_dialogo`.

# A seta de rolagem PARA BAIXO do diálogo, achada por template como os links.
#
# NÃO EXISTE DESLOCAMENTO FIXO PARA ELA, e isso é decisão, não preguiça: um
# deslocamento chutado a partir da moldura erra por alguns pixels, o clique cai
# fora da janela -- na cena 3D -- e o personagem ANDA, saindo da coordenada de
# onde o NPC responde. Sem o template, `rolar_o_dialogo` recusa e diz no log o
# que recortar.
TEMPLATE_DA_SETA_DE_ROLAGEM = "dialogo_seta_baixo.png"

# Quantas rolagens no máximo antes de aceitar que o link não está na lista.
#
# TETO, NÃO GASTO: cada passo é seguido de uma procura pelo link, e assim que ele
# aparece o laço para. O número cobre a lista inteira do Fay com folga -- e ela
# muda de tamanho conforme o nível do personagem, que é justamente por que
# contar rolagens fixas não serviria.
PASSOS_DE_ROLAGEM = 12

# A lista redesenhar depois do clique na seta. Uma volta de laço do cliente, não
# uma animação: `SendMessage` é síncrono, então quando o clique retorna a
# mensagem já foi processada.
ESPERA_DA_ROLAGEM = 0.08

# ===========================================================================
# NUNCA CLICAR NO LINK SEM O DIÁLOGO ABERTO
# ===========================================================================
#
# Toda interação com NPC aqui é um par: clique DIREITO no NPC, clique ESQUERDO no
# link do diálogo. E o segundo clique é perigoso, porque ele é POSICIONAL na cena
# 3D: se o diálogo não abriu, esse clique cai no CHÃO -- e clicar no chão faz o
# personagem ANDAR.
#
# O estrago é maior que perder uma tentativa. Saindo da coordenada medida, o NPC
# deixa de estar onde a coordenada diz, e daí TODAS as tentativas seguintes falham
# pelo mesmo motivo, cada uma afastando o personagem um pouco mais. Era um laço que
# se alimentava do próprio erro.
#
# Por isso o diálogo é CONFERIDO entre os dois cliques (`_abrir_dialogo_e_clicar`).
# Vale para os três pares de cliques deste arquivo: entrar na cave, falar com o
# Altar Stone e sair pelo Skull Herald.
#
# Quanto o personagem pode estar longe da coordenada medida e o clique ainda
# acertar. As coordenadas de NPC foram medidas com o personagem PARADO num ponto
# exato; alguns passos de distância já giram o NPC na tela.
TOLERANCIA_DA_POSICAO = 4



class UIDoJogo:
    """Opera o painel de arredores, os diálogos de NPC, a câmera e o minimapa.

    Não sabe de cave nenhuma. Quem sabe é quem herda -- `bc.ui_service.UIService`
    e a entrada da HH.
    """

    def __init__(self, ctx: BotContext,
                 navigator: Navigator | None = None) -> None:
        self.ctx = ctx
        # RECEBE o navegador da rotina em vez de criar um só seu. Dois navegadores
        # na mesma conta são dois cronômetros paralelos da mesma tecla de montaria
        # e da mesma recarga da skill de velocidade -- e cronômetro duplicado de
        # uma tecla que é interruptor significa montar e desmontar em seguida.
        self.nav = navigator or Navigator(ctx)
        # Coordenadas aprendidas na primeira tentativa bem-sucedida. São o que
        # permite a tentativa rápida: sem elas, cada volta gastaria segundos
        # procurando as mesmas duas coisas por imagem.
        self._ponto_npc_entrada: tuple[int, int] | None = None
        self._ponto_link_entrada: tuple[int, int] | None = None
        # Quando o painel de arredores foi usado pela última vez. Ver
        # `INTERVALO_ENTRE_USOS_DO_PAINEL`: é o que impede o pisca-pisca de
        # três aberturas seguidas quando a busca precisa retentar.
        self._painel_usado_em = 0.0
        # Aberturas do painel neste trajeto. Ver `ABERTURAS_POR_TRAJETO`.
        self._aberturas_do_trajeto = 0
        self._falhas_rapidas = 0
        # Diálogos seguidos que não abriram. Ver `TETO_DO_DESESPERO`: é o que
        # tira o teto adaptativo do poço em que ele caiu por 4 h em 07/09/2026.
        # POR INSTÂNCIA, e não global como a amostra de aberturas: com duas
        # contas rodando, uma saudável zeraria a contagem da travada.
        self._dialogos_seguidos_sem_abrir = 0
        self._visao_resetada_em = 0.0
        # Quando o guarda de janela rodou pela última vez. Estrangulado porque
        # janela não aparece sozinha -- ver `INTERVALO_DO_GUARDA_DE_JANELA`.
        self._guarda_de_janela_em = 0.0
        # Buscas seguidas em que a leitura de arredores por memória não respondeu.
        # Chegando no limite, o bot para de esperar por ela -- ver
        # `_esperar_resultado_da_busca`.

    # ==================================================================
    # Câmera
    # ==================================================================

    def padronizar_zoom_do_minimapa(self) -> None:
        """Leva o zoom do minimapa ao PADRÃO, venha de onde vier.

        =================================================================
        POR QUE ISTO IMPORTA MAIS DO QUE PARECE
        =================================================================

        O bot move o personagem clicando DENTRO do minimapa, e converte
        coordenada de jogo em pixel por `zones.MINIMAP_SCALE` (1,7 px por
        unidade). Esse número foi MEDIDO com o jogo no zoom em que ele abre --
        o padrão --, porque estes botões nunca tinham sido usados.

        Se o usuário mexer no zoom, a escala real deixa de ser 1,7 e todo
        clique de movimento passa do alvo (ou fica curto). Não dá erro, não
        aparece no log: o personagem simplesmente para de chegar onde deveria.

        =================================================================
        COMO SE CHEGA AO PADRÃO SEM SABER DE ONDE SE ESTÁ
        =================================================================

        São cinco níveis, o padrão no meio, e os botões PARAM no extremo. Então
        não é preciso ler o zoom atual: basta ir até o batente e voltar o que se
        sabe. `CLIQUES_ATE_O_BATENTE` afasta até o máximo de onde quer que
        esteja, e `CLIQUES_DO_BATENTE_ATE_O_PADRAO` traz de volta ao meio.

        É a mesma ideia do botão da barra de atalhos: quando o controle tem
        batente, não se precisa reconhecer o estado -- basta encostar nele.
        """
        ctx = self.ctx
        for _ in range(CLIQUES_ATE_O_BATENTE):
            ctx.click(ctx.coords.minimap_zoom_out)
            ctx.tick(ENTRE_CLIQUES_DE_ZOOM)
        for _ in range(CLIQUES_DO_BATENTE_ATE_O_PADRAO):
            ctx.click(ctx.coords.minimap_zoom_in)
            ctx.tick(ENTRE_CLIQUES_DE_ZOOM)
        ctx.log.debug("Zoom do minimapa padronizado")

    def resetar_visao(self, forcar: bool = False) -> None:
        """Aperta o View Reset para recentrar a câmera.

        Obrigatório ANTES de qualquer sequência de cliques posicionais na cena 3D
        -- entrar na cave, falar com o Altar Stone, sair pelo Skull Herald. Com a
        câmera girada ou com zoom diferente, o NPC não está onde a coordenada
        medida diz que está, e o clique cai no chão (o que faz o personagem
        andar, piorando a situação).

        Tem recarga própria de 10 s: apertar a cada tentativa de entrada custaria
        um clique inútil por volta, e a câmera não se mexe sozinha entre elas.
        """
        ctx = self.ctx
        agora = time.time()
        if not forcar and agora - self._visao_resetada_em < 10.0:
            return
        self._visao_resetada_em = agora
        #ctx.log.debug("View Reset (recentrando a câmera)")
        ctx.click(ctx.coords.reset_view)
        ctx.tick(0.175)
        # A câmera fixada por memória complementa o View Reset: o botão recentra,
        # os valores de zoom/ângulo garantem que ela fique igual em toda run.
        ctx.apply_camera()

    # ==================================================================
    # Localização de janelas
    # ==================================================================

    def _pontos(self, grupo: str, quadro=None) -> dict[str, tuple[int, int]] | None:
        nome_template, deslocamentos = TEMPLATE_ANCHORS[grupo]
        template = self.ctx.templates.load(nome_template)
        if template is None:
            return None
        if quadro is None:
            quadro = capture_window(self.ctx.hwnd)
        if quadro is None:
            return None
        base = find_template(quadro, template, threshold=ANCHOR_THRESHOLD)
        if base is None:
            return None
        return {n: (base[0] + dx, base[1] + dy)
                for n, (dx, dy) in deslocamentos.items()}

    def _achar_link(self, template: str) -> tuple[int, int] | None:
        """Localiza um link dentro do diálogo pelo texto dele."""
        tpl = self.ctx.templates.load(template)
        if tpl is None:
            return None
        quadro = capture_window(self.ctx.hwnd)
        if quadro is None:
            return None
        return find_template(quadro, tpl, threshold=ANCHOR_THRESHOLD)

    # ==================================================================
    # Painel de arredores
    # ==================================================================

    def desobstruir_a_cena(self, motivo: str) -> bool | None:
        """Tira janela da frente ANTES de um clique na cena 3D. Tri-estado.

            True  -> a tela está limpa (conferido por imagem)
            False -> ainda tem janela na frente
            None  -> não sei (sem captura ou sem os templates)

        =================================================================
        POR QUE ESTE GUARDA EXISTE
        =================================================================

        Toda coordenada de NPC deste arquivo foi medida com o personagem parado
        num ponto exato, e são cliques na CENA 3D. Uma janela aberta na frente
        engole o clique -- e o clique engolido não falha de graça: ele cai no
        chão, e clicar no chão faz o personagem ANDAR para longe da coordenada,
        tornando a tentativa seguinte pior que esta.

        =================================================================
        POR EVENTO, NÃO POR CLIQUE
        =================================================================

        O caminho rápido da entrada dispara dois cliques por segundo disputando
        a vaga. Conferir antes de cada um seria uma captura por tentativa no
        único trecho onde o projeto inteiro cortou espera para caber.

        E não precisa: janela não aparece sozinha. Ela aparece porque o BOT
        abriu, ou porque o jogo mostrou uma caixa. Então o guarda roda ao ENTRAR
        numa sequência de cliques e depois de qualquer coisa que possa ter
        aberto janela -- não em laço.

        "NÃO SEI" NÃO BLOQUEIA. É a mesma regra de `CONFERIR_A_JANELA_ANTES_DE_
        ENVIAR` ("bot mudo é pior que o defeito") e de `na_posicao_de_clicar`,
        que devolve True sem leitura porque recusar travaria o bot num laço sem
        saída. Quem chama decide -- e a decisão do BC é seguir.
        """
        ctx = self.ctx
        veredito = janelas_abertas.desobstruir(
            capturar=lambda: capture_window(ctx.hwnd),
            templates=ctx.templates,
            clicar=ctx.click,
            esperar=ctx.tick,
            log=ctx.log,
        )
        if veredito is False:
            ctx.log.warning(
                "Tem janela na frente e eu não consegui tirá-la antes de %s. "
                "O clique pode ser engolido.", motivo)
        elif veredito is None:
            ctx.log.debug("Não sei dizer se há janela na frente antes de %s", motivo)
        return veredito

    def _desobstruir_se_faz_tempo(self, o_que: str) -> bool | None:
        """Tira janela da frente, no máximo uma vez por
        `INTERVALO_DO_GUARDA_DE_JANELA`.

        `None` quando o estrangulamento barrou -- não é "não sei se há janela",
        é "não perguntei". Quem chama não decide nada com isto; o guarda existe
        para a tentativa SEGUINTE.
        """
        agora = time.time()
        if agora - self._guarda_de_janela_em < INTERVALO_DO_GUARDA_DE_JANELA:
            return None
        self._guarda_de_janela_em = agora
        return self.desobstruir_a_cena(f"a tentativa seguinte de {o_que}")

    def comecar_trajeto(self, motivo: str = "") -> None:
        """Zera o orçamento de aberturas do painel. Chamado por quem INICIA um
        trajeto -- ir até o NPC da cave, viajar para Ghost Din Woods, acertar a
        coordenada da entrada.

        Fica separado do `abrir_surroundings` de propósito: quem abre não sabe
        se está começando algo novo ou insistindo no mesmo. Só quem começa sabe.
        """
        if self._aberturas_do_trajeto and motivo:
            self.ctx.log.debug(
                "Novo trajeto (%s); zerando as %s abertura(s) do anterior",
                motivo, self._aberturas_do_trajeto)
        self._aberturas_do_trajeto = 0

    def _marcar_uso_do_painel(self) -> None:
        """Carimba AGORA como o último uso do painel.

        =================================================================
        O CARIMBO ESTAVA NO LUGAR ERRADO E A TRAVA QUASE NUNCA MORDIA
        =================================================================

        Ele era gravado só na ABERTURA, então o intervalo media *abrir → abrir*.
        Um ciclo inteiro (abre, filtra, clica, espera parar, fecha) leva bem mais
        que os 2 s, então a reabertura seguinte não pagava nada -- e o usuário
        continuava vendo o painel piscar em sequência.

        Agora o carimbo sai em TRÊS pontos e vale o MAIS RECENTE: ao abrir, ao
        clicar no auto-path e ao fechar. Assim toda interação com o painel
        reinicia a contagem, inclusive a tentativa que abre e nem chega a clicar
        -- que é justamente a que repetia rápido. O caminho feliz continua não
        pagando nada: entre a Fay, a entrada e o vendedor passam minutos.
        """
        self._painel_usado_em = time.time()

    def _respeitar_a_cadencia_do_painel(self) -> None:
        """Espera o RESTO do intervalo desde o último uso do painel.

        O resto, não o intervalo: entre um uso e o seguinte costumam passar
        minutos, e aí não se espera nada. Quem paga é só a REPETIÇÃO rápida, que
        é justamente o que fica feio de ver. Ver
        `INTERVALO_ENTRE_USOS_DO_PAINEL`.

        Usa `ctx.tick`, e não `time.sleep`: o Parar tem que continuar sendo
        imediato dentro da espera.
        """
        if not self._painel_usado_em:
            self._marcar_uso_do_painel()
            return

        resto = (self._painel_usado_em + INTERVALO_ENTRE_USOS_DO_PAINEL
                 - time.time())
        if resto > 0:
            self.ctx.log.debug(
                "Painel de arredores foi usado há pouco; esperando %.1fs para "
                "reabrir (cadência).", resto)
            self.ctx.tick(resto)
        self._marcar_uso_do_painel()

    def abrir_surroundings(self) -> dict | None:
        """Abre o painel de arredores e garante que está na aba NPC.

        SEM PARÂMETRO DE TENTATIVAS -- ele existia e valia 3, e era ele que produzia
        o pisca-pisca descrito abaixo. Repetir o clique num interruptor não é
        insistir, é alternar.

        O PORTÃO DA MONTARIA FICA AQUI, e não em quem clica no resultado.

        Abrir este painel já FAZ PARTE de andar: ele existe só para o bot viajar,
        e o passo seguinte é sempre um clique que manda o personagem caminhar. O
        portão estava depois, no clique do resultado, e a consequência aparecia no
        início de toda sessão: o `PREPARAR` invoca o pet e aplica buffs (as duas
        coisas exigem estar a pé, então desmontam), e o bot abria o painel, buscava
        o NPC e digitava o nome AINDA A PÉ -- só pensava na montaria vários cliques
        depois.

        Aqui é o estrangulamento certo: nada relacionado a viajar acontece antes de
        a memória confirmar a montaria ativa.

        O BOTÃO DO PAINEL É INTERRUPTOR, e é por isso que este método clica NELE UMA
        VEZ SÓ por chamada.

        O laço anterior clicava a cada volta, e isso produzia o sintoma "abre o
        Surroundings, não digita nada e fecha": quando a âncora não casa mas o
        painel ESTÁ aberto -- diálogo de NPC por cima, quadro capturado no meio de
        uma animação, template abaixo do limiar -- o primeiro clique FECHA, o
        segundo REABRE, e o terceiro fecha de novo. O bot pisca o painel e não
        chega a digitar nada.

        Clicar num interruptor sem enxergar o estado dele é jogar cara ou coroa. Só
        existem dois desfechos honestos aqui: ou a âncora aparece e o painel é
        operável, ou este método desiste e devolve None.
        """
        ctx = self.ctx
        # ORÇAMENTO DO TRAJETO. Ver `ABERTURAS_POR_TRAJETO`: as retentativas
        # eram aninhadas (3 x 3), e recusar AQUI faz os dois laços pararem
        # sozinhos, sem precisar desmontar nenhum deles.
        if self._aberturas_do_trajeto >= ABERTURAS_POR_TRAJETO:
            ctx.log.warning(
                "Já abri o painel de arredores %s vezes neste trajeto; não "
                "abro de novo. Insistir aqui é o pisca-pisca que o usuário vê "
                "-- e cada volta custa segundos parado na porta.",
                self._aberturas_do_trajeto)
            return None
        self._aberturas_do_trajeto += 1

        self._respeitar_a_cadencia_do_painel()
        self.nav.garantir_montaria_para_andar(
            "abrir o painel de arredores (é o começo de um trajeto)")

        # Já aberto? Então nem toca no interruptor.
        pontos = self._pontos("surroundings")

        if pontos is None:
            # NÃO CONSIGO ENXERGAR é diferente de NÃO ESTÁ ABERTO, e a diferença
            # decide se vale clicar. Sem captura ou sem template, tudo o que viria
            # depois (campo de busca, aba, primeiro resultado) também não teria
            # coordenada -- clicar só serviria para mexer no interruptor às cegas.
            if not self._consigo_enxergar("surroundings"):
                ctx.log.warning(
                    "Não consigo enxergar a tela para localizar o painel de "
                    "arredores. NÃO vou clicar no botão dele: é interruptor, e "
                    "clicar sem ver o estado abre e fecha sem digitar nada."
                )
                return None

            ctx.log.debug("Abrindo o painel de arredores")
            ctx.click(ctx.coords.surroundings_button)
            pontos = self._esperar_o_painel()

        if pontos is None:
            ctx.log.warning(
                "Cliquei no botão do painel de arredores e ele não apareceu em "
                "%.1fs. Não vou clicar de novo nesta chamada -- o botão é "
                "interruptor e o segundo clique fecharia o que o primeiro abriu.",
                LIMITE_DA_ESPERA_DO_PAINEL,
            )
            return None

        # A lista abre em "Player"; os NPCs estão na outra aba. Não é preciso
        # relocalizar a âncora depois: ela é a moldura do painel, que não se
        # move ao trocar de aba, e o campo de busca existe nas duas.
        ctx.click(pontos["tab_npc"])
        ctx.tick(ESPERA_DA_TROCA_DE_ABA)
        return pontos

    def _consigo_enxergar(self, grupo: str) -> bool:
        """Dá para CAPTURAR a tela e carregar o template deste grupo?

        Separa "não vi o painel" de "não consigo ver nada". A primeira resposta
        autoriza clicar no botão; a segunda não autoriza clicar em coisa nenhuma.
        """
        nome_template, _ = TEMPLATE_ANCHORS[grupo]
        if self.ctx.templates.load(nome_template) is None:
            return False
        return capture_window(self.ctx.hwnd) is not None

    def _esperar_o_painel(self) -> dict[str, tuple[int, int]] | None:
        """Espera o painel APARECER, em vez de esperar um tempo fixo.

        Devolve os pontos no instante em que a âncora é encontrada. No caso comum
        resolve na primeira ou segunda leitura -- os 1,2 s fixos que havia aqui
        eram gastos por inteiro tanto quando o painel abria rápido quanto quando
        ele não abria de jeito nenhum.
        """
        ctx = self.ctx
        limite = time.time() + LIMITE_DA_ESPERA_DO_PAINEL
        while time.time() < limite:
            ctx.raise_if_stopped()
            pontos = self._pontos("surroundings")
            if pontos is not None:
                return pontos
            ctx.tick(PASSO_DA_ESPERA_DO_PAINEL)
        return None

    def fechar_surroundings(self) -> bool | None:
        """Fecha o painel e CONFERE que ele sumiu. Resposta TRI-ESTADO.

            True  -> fechei e conferi que sumiu
            False -> cliquei no fechar e ele continuava lá no fim da espera
            None  -> NÃO SEI (não consigo enxergar a tela)

        =================================================================
        O `None` É A CORREÇÃO, E ELE VEIO DE UM DEFEITO MEDIDO
        =================================================================

        Esta função devolvia `None` sempre e começava assim:

            pontos = self._pontos("surroundings")
            if not pontos:
                return          # <- "não consigo VER" tratado como "não está aberto"

        `abrir_surroundings` faz essa distinção com todo cuidado -- tem até um
        método só para isso, `_consigo_enxergar`, com o comentário "NÃO CONSIGO
        ENXERGAR é diferente de NÃO ESTÁ ABERTO". Aqui a distinção não existia.

        Num quadro ruim -- animação, névoa, rumor passando por cima -- o template
        cai abaixo do limiar por um instante e a função voltava EM SILÊNCIO
        achando que tinha fechado. Print do usuário em 26/08/2026: personagem na
        coordenada exata da entrada (1395,-635), Skull Herald selecionado, time
        de reset formado, e o painel aberto na frente engolindo o clique.

        Por isso agora ela RELÊ antes de desistir de ver
        (`LEITURAS_ANTES_DE_DESISTIR_DE_VER`) e devolve um veredito que quem
        chama pode usar. Custo do caso comum: zero -- a primeira leitura acha.
        """
        ctx = self.ctx

        pontos = None
        for _ in range(LEITURAS_ANTES_DE_DESISTIR_DE_VER):
            ctx.raise_if_stopped()
            pontos = self._pontos("surroundings")
            if pontos is not None:
                break
            if not self._consigo_enxergar("surroundings"):
                # Cegueira real (sem captura ou sem template): reler não ajuda.
                ctx.log.debug(
                    "Não consigo enxergar a tela para conferir o painel de "
                    "arredores; não sei se ele está aberto.")
                self._marcar_uso_do_painel()
                return None
            ctx.tick(PASSO_DA_ESPERA_DO_FECHAMENTO)

        if pontos is None:
            # Enxergo a tela e o painel não está nela: já estava fechado.
            return True

        ctx.click(pontos["close"])
        # A CADÊNCIA CONTA A PARTIR DAQUI TAMBÉM -- ver `_marcar_uso_do_painel`.
        self._marcar_uso_do_painel()

        limite = time.time() + LIMITE_DA_ESPERA_DO_FECHAMENTO
        while time.time() < limite:
            ctx.raise_if_stopped()
            if self._pontos("surroundings") is None:
                return True                  # sumiu: não há o que esperar
            ctx.tick(PASSO_DA_ESPERA_DO_FECHAMENTO)

        ctx.log.warning(
            "Cliquei no fechar do painel de arredores e ele continuava na tela "
            "depois de %.1fs. Uma janela aberta engole os cliques na cena 3D.",
            LIMITE_DA_ESPERA_DO_FECHAMENTO)
        return False

    @contextmanager
    def trajeto_pelo_painel(self, motivo: str):
        """O trajeto é o DONO do painel: ele zera o orçamento e fecha na saída.

        =================================================================
        POR QUE O DONO É O TRAJETO, E NÃO A ABERTURA
        =================================================================

        `buscar_npc` termina com o painel ABERTO de propósito -- quem chamou
        ainda vai clicar no `first_result` para disparar o auto-path. Então a
        unidade de trabalho não é "abrir e fechar", é *buscar o NPC e sair
        andando até ele*. Quem sabe onde isso começa e termina é o trajeto.

        =================================================================
        O QUE ISTO CONSERTA
        =================================================================

        `fechar_surroundings` tinha UM ponto de chamada no arquivo inteiro -- no
        caminho de SUCESSO de `ir_para_resultado`. Todas as outras saídas
        deixavam o painel aberto:

          * `ir_para_resultado` devolvendo False por não localizar o painel;
          * `buscar_npc` devolvendo None depois das três tentativas;
          * `abrir_surroundings` que CLICOU no botão e não viu o painel a tempo
            -- abriu, e ninguém fechava.

        E painel aberto engole o clique na cena 3D. Pior: o clique que erra cai
        no chão, e clicar no chão faz o personagem ANDAR para longe da
        coordenada. Foi assim que o usuário achou o personagem parado em
        (1395,-635), com alvo e time prontos, e o painel na frente.

        Chamar `fechar_surroundings()` à mão em cada `return` que falta seria só
        criar um quarto lugar para esquecer no próximo `return` que alguém
        escrever. Aqui o fechamento é consequência de SAIR DO BLOCO -- inclusive
        por exceção -- e a regra fica visível na indentação.
        """
        self.comecar_trajeto(motivo)
        try:
            yield
        finally:
            # NUNCA deixa o fechamento matar o fluxo: quem estava no bloco pode
            # estar subindo uma exceção que importa mais (parada, queda).
            try:
                self.fechar_surroundings()
            except StopRequested:
                raise
            except Exception:
                self.ctx.log.debug(
                    "Falha ao fechar o painel de arredores", exc_info=True)

    def buscar_npc(
        self,
        texto: str,
        confirmar: str | None = None,
        tentativas: int = 3,
    ) -> dict[str, object] | None:
        """Busca um NPC e devolve o primeiro resultado, conferido.

        Devolve `{"nome": str, "coords": (x, y)}` ou None. A conferência pela
        memória evita clicar num resultado parecido e viajar para o lugar errado
        sem ninguém perceber.
        """
        ctx = self.ctx
        for tentativa in range(1, tentativas + 1):
            ctx.raise_if_stopped()
            pontos = self.abrir_surroundings()
            if pontos is None:
                # RETENTA em vez de desistir da busca inteira.
                #
                # `abrir_surroundings` clica no botão UMA vez por chamada, então um
                # painel que demora mais que o teto da espera não é visto naquela
                # chamada -- e antes isso reprovava a busca toda. A volta seguinte
                # resolve: se o clique abriu o painel (só que devagar), ela o
                # encontra ABERTO e nem toca no botão.
                #
                # Isto só é seguro porque o clique virou um por chamada. Com o laço
                # antigo, retentar era o próprio pisca-pisca.
                ctx.log.debug("Painel de arredores não apareceu na tentativa %s",
                              tentativa)
                continue

            # ==========================================================
            # A BUSCA ERA LENTA POR ESPERAR SEM MOTIVO
            # ==========================================================
            #
            # Aqui havia 1,5 s de esperas fixas (0,4 + 0,2 + 0,9) mais a digitação
            # a 40 ms por caractere -- uns 2,2 s parados no painel a cada busca,
            # três vezes por run.
            #
            # As esperas fixas viraram uma ESPERA POR RESULTADO: o bot pergunta à
            # memória se o resultado apareceu, a cada 0,1 s, e segue no instante em
            # que ele aparece. O caso comum resolve em uma ou duas leituras.
            #
            # E a digitação ficou mais rápida porque agora existe CONFERÊNCIA: o
            # resultado é lido e comparado com o que se procurava. Se um caractere
            # cair, a comparação reprova e a tentativa seguinte redigita -- antes
            # não havia como saber, e a lentidão era o único seguro.
            # CLICAR E DIGITAR, sem nada no meio. `SendMessage` é síncrono: quando
            # `click` retorna o cliente já processou o clique e o campo já tem o
            # foco. Não há estado a aguardar.
            ctx.click(pontos["search_field"])
            ctx.input.clear_field(LIMPEZA_DO_CAMPO)
            ctx.input.type_text(texto, per_char=DIGITACAO_POR_CARACTERE)

            info = self._esperar_resultado_da_busca()
            if info:
                nome = str(info["nome"])
                ctx.log.info("Arredores: %r em %s", nome, info["coords"])
                if confirmar and confirmar.lower() not in nome.lower():
                    ctx.log.warning(
                        "Esperava %r mas veio %r; tentando de novo",
                        confirmar, nome,
                    )
                    ctx.click(pontos["refresh"])
                    ctx.tick(0.5)
                    continue
                return info

            # Sem leitura de memória, segue às cegas com o que foi digitado.
            ctx.log.debug("Sem leitura do resultado; seguindo pelo texto buscado")
            return {"nome": texto, "coords": None}
        return None

    def _esperar_resultado_da_busca(self) -> dict[str, object] | None:
        """Espera o resultado APARECER, em vez de esperar um tempo fixo.

        Devolve o primeiro resultado assim que a memória o entrega, ou None depois
        do limite. No caso comum resolve em uma ou duas leituras -- muito antes dos
        0,9 s fixos que havia aqui.

        E APRENDE QUANDO NÃO VALE ESPERAR. Se a leitura de arredores não funcionar
        neste cliente, o teto de 1,5 s era gasto INTEIRO em toda busca, três vezes
        por run -- espera pura, sem chance de sucesso. Depois de
        `BUSCAS_ANTES_DE_DESISTIR_DA_LEITURA` buscas em que a memória nunca
        respondeu, esta função troca a espera longa por
        `ESPERA_CEGA_DO_RESULTADO`, que é só o tempo de a lista filtrar.

        Uma leitura boa a qualquer momento zera essa contagem: se o leitor voltar a
        funcionar, a conferência volta com ele.
        """
        ctx = self.ctx

        sem_leitura = _BUSCAS_SEM_LEITURA.get(ctx.hwnd, 0)
        if sem_leitura >= BUSCAS_ANTES_DE_DESISTIR_DA_LEITURA:
            # Sem conferência possível: espera só a lista filtrar e segue às
            # cegas, exatamente como o bot fazia antes de existir esta leitura.
            ctx.tick(ESPERA_CEGA_DO_RESULTADO)
            return None

        limite = time.time() + LIMITE_DA_ESPERA_DO_RESULTADO
        while time.time() < limite:
            ctx.raise_if_stopped()
            info = ctx.memory.surroundings_first()
            if info:
                _BUSCAS_SEM_LEITURA[ctx.hwnd] = 0
                return info
            ctx.tick(PASSO_DA_ESPERA_DO_RESULTADO)

        sem_leitura += 1
        _BUSCAS_SEM_LEITURA[ctx.hwnd] = sem_leitura
        if sem_leitura == BUSCAS_ANTES_DE_DESISTIR_DA_LEITURA:
            ctx.log.info(
                "A leitura de arredores por memória não respondeu em %s buscas "
                "seguidas; paro de esperar por ela e sigo pelo texto digitado. "
                "As buscas ficam %.1fs mais rápidas, sem conferência.",
                sem_leitura, LIMITE_DA_ESPERA_DO_RESULTADO
                - ESPERA_CEGA_DO_RESULTADO,
            )
        return None

    def ir_para_resultado(self, destino: str = "o resultado da busca",
                          coords: tuple[int, int] | None = None,
                          max_seconds: float = 120.0) -> bool:
        """Clica no primeiro resultado e espera o auto-path do jogo trabalhar.

        É MOVIMENTO, mesmo sendo um clique em painel: o pathfinding do jogo assume
        e o personagem atravessa o mapa. Por isso a montaria é exigida aqui também
        -- este era um dos trechos que andavam a pé, porque "clicar num painel" não
        se parece com "andar".

        =================================================================
        UM CLIQUE, E SÓ. O QUE A COORDENADA FAZ AQUI É MEDIR
        =================================================================

        Em 25/08/2026 esta função passou a REABRIR o painel quando o personagem
        parava longe da coordenada do resultado. Deu errado em produção, e o
        usuário relatou na hora: *"as aberturas do Surroundings começaram a ser
        constantes, principalmente na hora de ir para a Fay, aí fica entrando em
        loop e andando para lugar errado; nesse sentido as verificações estavam
        melhor antes."*

        A causa: **as duas coordenadas podem não estar na mesma escala.**
        `Memory.position()` devolve a leitura dividida por 20
        (`_coord`: `raw / 20.0`), e o `[x,y]` do painel vem do TEXTO da interface.
        Ninguém nunca provou que os dois números vivem no mesmo espaço -- e se
        não vivem, a distância nunca fecha, toda chegada é julgada "longe", e
        cada reabertura é mais um clique com chance de cair fora do painel.

        O código anterior a isso nunca tropeçou porque usava a coordenada só como
        ATALHO ("cheguei perto, paro de esperar"), nunca como veredito. É essa
        semântica que volta aqui.

        A COORDENADA CONTINUA SENDO LIDA, e vira LOG: a cada chegada sai a
        distância entre onde o personagem parou e o que o painel prometeu. Se em
        algumas runs ela convergir para perto de zero, os dois espaços são o
        mesmo e `CONFIRMAR_CHEGADA_POR_COORDENADA` pode ser ligado com medição
        atrás. Enquanto isso, ninguém decide nada com ela.
        """
        ctx = self.ctx
        pontos = self._pontos("surroundings")
        if pontos is None:
            return False

        # =================================================================
        # O PORTÃO DA MONTARIA NÃO FICA AQUI -- ele já rodou, ANTES de abrir
        # =================================================================
        #
        # Havia um `garantir_montaria_para_andar` nesta linha, e ele produzia um
        # defeito medido. Relato do usuário em 26/08/2026: o bot digitava
        # `Skull` no campo de busca e o campo virava `Skull00000000...`.
        #
        # O mecanismo: `buscar_npc` acabou de CLICAR no campo de busca e digitar
        # -- o campo está com o FOCO. O portão da montaria não é "aciona e
        # segue": ele INSISTE SEM TETO (ver `navigation`, "NUNCA A PÉ DENTRO DA
        # CAVE"), apertando a tecla ciclo após ciclo enquanto a memória não
        # confirmar. Com o foco no campo, cada toque da tecla `0` caía DENTRO do
        # campo. Um laço infinito digitando na busca.
        #
        # E a chamada era REDUNDANTE: quem chega aqui passou por
        # `abrir_surroundings`, que já exige montaria ANTES de abrir o painel --
        # que é a ordem certa, porque o clique no resultado JÁ É o começo do
        # trajeto. Ordem determinada pelo usuário: montaria -> Surroundings.
        #
        # Se a montaria cair no intervalo entre abrir e clicar, o auto-path é
        # pathfinding do JOGO (não caminhada por clique) e `_manter_montaria`
        # repõe a montaria durante o trajeto.
        antes = ctx.memory.position()
        ctx.click(pontos["first_result"])
        # A CADÊNCIA CONTA A PARTIR DO AUTO-PATH -- ver `_marcar_uso_do_painel`.
        self._marcar_uso_do_painel()

        if not self._saiu_do_lugar(antes):
            # Não é falha fatal -- o painel fecha e quem chamou segue. Mas vira
            # log: antes o clique podia cair no vazio e ninguém saberia.
            ctx.log.debug(
                "Cliquei no resultado e o personagem não saiu do lugar em %.0f ms",
                LIMITE_DA_ESPERA_DO_ANDAR * 1000)
        self.fechar_surroundings()

        chegou, motivo, distancia = self._esperar_chegar(
            coords, time.time() + max_seconds)

        # A MEDIÇÃO, sem decisão. É esta linha que vai dizer, ao longo de umas
        # poucas runs, se a coordenada do painel serve para confirmar chegada.
        if coords is not None:
            ctx.log.info(
                "Auto-path até %s: %s | parei em %s | o painel prometia %s%s",
                destino, motivo, ctx.memory.position(), coords,
                "" if distancia is None else f" | distância {distancia:.0f}")

        if CONFIRMAR_CHEGADA_POR_COORDENADA and coords is not None and not chegou:
            ctx.log.warning(
                "Não confirmei a chegada em %s (%s). Reabrindo o painel de "
                "arredores.", destino, motivo)
            return self.abrir_surroundings() is not None and self.ir_para_resultado(
                destino, coords=coords, max_seconds=max_seconds)

        return True

    def _saiu_do_lugar(self, antes: tuple[int, int] | None) -> bool:
        """O clique pôs o personagem em movimento?

        ESPERA POR EVENTO, e não `tick` fixo. O clique no resultado põe o
        pathfinding do jogo para trabalhar, e isso muda a posição na memória --
        leitura de microssegundos. A espera fixa daqui era gasta inteira mesmo
        quando ele saía no primeiro quadro.
        """
        ctx = self.ctx
        limite = time.time() + LIMITE_DA_ESPERA_DO_ANDAR
        while time.time() < limite:
            ctx.raise_if_stopped()
            agora = ctx.memory.position()
            if antes is None or agora is None:
                ctx.tick(ESPERA_DEPOIS_DE_CLICAR_NO_RESULTADO)
                return True          # sem leitura: volta ao comportamento antigo
            if agora != antes:
                return True
            ctx.tick(PASSO_DA_ESPERA_DO_ANDAR)
        return False

    def _esperar_chegar(self, destino: tuple[int, int] | None,
                        limite: float) -> tuple[bool, str, float | None]:
        """Espera o personagem PARAR. Devolve `(chegou, motivo, distância)`.

        SAI POR "PAROU", que é o critério que sempre funcionou -- e é o único que
        não depende de as duas coordenadas estarem na mesma escala (ver
        `ir_para_resultado`). Chegar perto do destino é um ATALHO para não
        esperar o fim de um trajeto longo, não o veredito.

        A distância volta junto para quem quiser LOGAR. Ninguém decide com ela
        enquanto `CONFIRMAR_CHEGADA_POR_COORDENADA` estiver desligado.
        """
        ctx = self.ctx
        anterior: tuple[int, int] | None = None
        parado = 0
        distancia = None

        while time.time() < limite:
            ctx.raise_if_stopped()
            atual = ctx.memory.position()
            if atual is None:
                ctx.tick(PASSO_DA_ESPERA_DA_CHEGADA)
                continue

            if destino is not None:
                distancia = distancia_linear(atual, destino)
                if distancia < PROXIMIDADE_DO_DESTINO:
                    return True, "cheguei perto do destino", distancia

            if atual == anterior:
                parado += 1
                if parado >= LEITURAS_PARA_CONSIDERAR_PARADO:
                    return True, "parei de andar", distancia
            else:
                parado = 0
            anterior = atual
            ctx.tick(PASSO_DA_ESPERA_DA_CHEGADA)

        return False, "estourou o prazo", distancia

    # ==================================================================
    # Diálogo de NPC
    # ==================================================================

    def _ponto_padrao_do_npc(self, larguraDif: int = 0,
                             alturaDif: int = 0) -> tuple[int, int]:
        """Onde o NPC costuma aparecer depois do caminhar automático.

        Logo acima do centro da tela. Com a câmera no padrão (View Reset + os
        valores fixados por memória), o personagem para de frente para o NPC e
        ele cai nesta faixa.

        O ponto vem de `coords.npc_padrao`, e não de uma conta feita aqui: é lá
        que mora o ÚNICO modelo de resolução do projeto (âncora + deslocamento
        fixo). A versão anterior calculava X ancorado no centro e Y como fração
        da altura -- dois modelos no mesmo cálculo, e o segundo contradiz a
        descoberta de que a UI não escala. Ver o comentário de `npc_padrao`:
        a 1024x768 o número é idêntico, nas outras resoluções o antigo errava.

        Os dois deslocamentos continuam em PIXELS, e isso está certo: elemento
        de tamanho fixo, deslocamento de tamanho fixo.
        """
        x_base, y_base = self.ctx.coords.npc_padrao
        return (x_base + larguraDif, y_base + alturaDif)

    def falar_com_npc(self, ponto_npc: tuple[int, int] | None = None,
                      tentativas: int = 4, larguraDif: int = 0, alturaDif: int = 0,
                      halo_px: int = 0) -> tuple[int, int] | None:
        """Abre o diálogo do NPC à frente. Devolve o ponto que FUNCIONOU.

        `halo_px > 0` tenta também os VIZINHOS de `ponto_npc`, do mais perto
        para o mais longe -- o porquê e o tamanho do passo estão em
        `core/halo.py`. O anel PARA assim que a posição muda: clique que caiu no
        chão fez o personagem andar, e daí em diante todo vizinho vale para um
        enquadramento que não existe mais.
        """
        ctx = self.ctx
        self.nav.garantir_montaria_para_andar("interagir com o NPC")

        # Aqui você repassa os parâmetros recebidos para a função que calcula o ponto
        ponto_calculado = self._ponto_padrao_do_npc(larguraDif=larguraDif, alturaDif=alturaDif)
        miras = (halo.pontos_em_volta(ponto_npc, halo_px)
                 if ponto_npc and halo_px > 0 else [ponto_npc])
        candidatos = [p for p in (*miras, ponto_calculado) if p]
        partida = ctx.memory.position() if halo_px > 0 else None

        for volta in range(max(tentativas, len(candidatos) if halo_px > 0 else 0)):
            ctx.raise_if_stopped()
            if partida is not None and volta and ctx.memory.position() != partida:
                ctx.log.info(
                    "O clique anterior tirou o personagem de %s; paro o anel de "
                    "tentativas em vez de empurrá-lo para mais longe.", partida)
                return None
            if self._pontos("dialogue"):
                return candidatos[0]
            alvo = candidatos[min(volta, len(candidatos) - 1)]
            #ctx.log.debug("Clique direito no NPC em %s", alvo)
            ctx.right_click(alvo)
            # ESPERA POR EVENTO, e não `tick(1.3)` fixo.
            #
            # Eram 1,3 s gastos por inteiro depois de CADA clique, quatro vezes --
            # 5,2 s numa tentativa, e é isso que aparece no log das 14:36:04 a
            # 14:36:10. O diálogo, quando abre, abre em uma fração disso; o teto
            # largo continua valendo para quando o clique errou o NPC de verdade.
            resposta = self._esperar_o_dialogo(limite_da_espera_do_dialogo_lenta())
            if resposta is True:
                return alvo
            if resposta is None:
                # Sem imagem não há o que conferir, e insistir na leitura não faz a
                # captura passar a funcionar. Dá o tempo do diálogo chegar e segue
                # com este ponto -- é o mesmo tratamento de `None` que
                # `_abrir_dialogo_e_clicar` já dá, e recusar aqui deixaria a
                # descoberta impossível em cliente sem captura.
                ctx.tick(limite_da_espera_do_dialogo())
                return alvo
        return None

    def dialogo_esta_aberto(self) -> bool | None:
        """O diálogo de NPC está na tela?

        TRÊS respostas, e a terceira é o ponto:

            True  -- está aberto, pode clicar no link
            False -- NÃO está; clicar no link agora cairia no chão
            None  -- não há como saber (sem template ou sem captura)

        Distinguir False de None é o que impede duas falhas opostas. Tratar None
        como False deixaria a entrada impossível em cliente minimizado, onde o
        `PrintWindow` devolve quadro preto e nenhum template casa -- que é o modo
        normal de operação deste bot. Tratar False como None é o bug que esta
        função existe para evitar: clicar no link sem diálogo faz o personagem
        andar e sair da coordenada de onde a cave pode ser aberta.
        """
        ctx = self.ctx
        nome_template, _ = TEMPLATE_ANCHORS["dialogue"]
        if ctx.templates.load(nome_template) is None:
            return None
        quadro = capture_window(ctx.hwnd)
        if quadro is None:
            return None
        return self._pontos("dialogue", quadro=quadro) is not None

    def _afrouxar_o_teto(self, limite: float) -> float:
        """O teto de agora, esticado pelas falhas seguidas. Ver `TETO_DO_DESESPERO`.

        Devolve `limite` intocado enquanto a coisa está normal -- o afrouxamento
        só existe para o poço, e no caso comum ele não custa nada.
        """
        degraus = self._dialogos_seguidos_sem_abrir // FALHAS_SEGUIDAS_ANTES_DE_AFROUXAR
        if degraus <= 0:
            return limite
        return min(TETO_DO_DESESPERO, limite * FATOR_DE_AFROUXAMENTO ** degraus)

    def _esperar_o_dialogo(self, limite: float) -> bool | None:
        """Espera o diálogo APARECER, preservando as três respostas.

        Devolve no instante em que ele abre, em vez de gastar uma espera fixa. As
        três respostas de `dialogo_esta_aberto` continuam valendo, e a do meio é a
        que exige cuidado:

            True  -- abriu; pode clicar no link
            False -- o teto passou e não abriu
            None  -- não há como saber (sem template ou sem captura), e isso NÃO
                     é "não abriu". Devolve na hora: insistir na leitura não faria
                     a captura passar a funcionar, e em cliente minimizado ela
                     nunca funciona -- que é o modo normal deste bot.
        """
        ctx = self.ctx
        # O TETO DE AGORA JÁ VEM ESTICADO PELAS FALHAS SEGUIDAS. Sem isto, o
        # teto só sabia apertar: ver `TETO_DO_DESESPERO` e as 13.449 tentativas
        # de 07/09/2026.
        esticado = self._afrouxar_o_teto(limite)
        if esticado > limite:
            ctx.log.info(
                "Diálogo: %s falhas seguidas — afrouxando o teto de %.0f para "
                "%.0f ms nesta tentativa.", self._dialogos_seguidos_sem_abrir,
                limite * 1000, esticado * 1000)
        limite = esticado
        comeco = time.time()
        limite_em = comeco + limite
        while True:
            ctx.raise_if_stopped()
            aberto = self.dialogo_esta_aberto()
            if aberto is not False:
                if aberto is True:
                    # CRONOMETRA a abertura. É esta medição que faz o teto se
                    # ajustar (ver `limite_da_espera_do_dialogo`) -- sem ela o
                    # valor seria um palpite fixo, e um palpite curto joga fora
                    # tentativa boa enquanto um longo paga o teto inteiro em toda
                    # tentativa que nunca ia abrir.
                    demora = time.time() - comeco
                    _ABERTURAS_DO_DIALOGO.append(demora)
                    # ABRIU: a realimentação está viva de novo.
                    self._dialogos_seguidos_sem_abrir = 0
                    # ctx.log.debug(
                    #     "Diálogo abriu em %.0f ms (teto era %.0f ms; próximo "
                    #     "teto %.0f ms)", demora * 1000, limite * 1000,
                    #     limite_da_espera_do_dialogo() * 1000)
                return aberto            # True ou None: os dois saem daqui
            restante = limite_em - time.time()
            if restante <= 0:
                self._dialogos_seguidos_sem_abrir += 1
                ctx.log.debug(
                    "Diálogo NÃO abriu em %.0f ms (teto). Tentativa perdida. "
                    "(%s seguida(s))", limite * 1000,
                    self._dialogos_seguidos_sem_abrir)
                return False
            # Dorme o que falta, não o passo inteiro: passar do teto em até um
            # passo, numa volta que se repete seis vezes por dez segundos, sai do
            # orçamento da disputa.
            ctx.tick(min(PASSO_DA_ESPERA_DO_DIALOGO, restante))

    def _abrir_dialogo_e_clicar(
        self,
        ponto_npc: tuple[int, int],
        ponto_link: PontoDoLink,
        o_que: str,
        esperar_depois: float = ESPERA_DEPOIS_DO_LINK,
        ainda_vale: Callable[[], bool] | None = None,
    ) -> bool:
        """O par de cliques de NPC, com o diálogo CONFERIDO no meio.

        Clique direito no NPC, confere que o diálogo abriu, e só então o clique
        esquerdo no link. É o único jeito seguro de fazer esse par: o clique no
        link é posicional na cena 3D, e sem diálogo ele cai no chão e o personagem
        sai andando -- levando consigo a coordenada de onde os cliques funcionam.

        `esperar_depois=0` para quem observa o resultado por conta própria: na
        disputa pela cave é o laço da rotina que fica lendo a posição em fatias
        curtas, e dormir aqui só atrasaria a leitura dele.

        =================================================================
        `ainda_vale` -- O MUNDO PODE TER MUDADO ENTRE OS DOIS CLIQUES
        =================================================================

        O par não é atômico: entre o clique direito e o clique no link há a
        espera do diálogo (centenas de milissegundos). Se o mundo mudou nesse
        vão, o segundo clique vai para um diálogo que não é o que se pediu.

        Medido na HH em 03/09/2026, e o desfecho era o pior possível: uma
        tentativa de entrada acertava, o personagem entrava na cave, e a
        tentativa SEGUINTE clicava com direito no mesmo ângulo -- que dentro da
        cave abre o diálogo do NPC de SAÍDA. O diálogo abria (então a
        conferência dizia "pode clicar"), e o clique no link caía em "Leave
        Happiness Hall". O bot entrava e saía na mesma volta.

        `ainda_vale` é chamado DEPOIS de o diálogo abrir e ANTES do clique no
        link. Devolvendo False, o diálogo é fechado e nada mais é clicado.
        Sem o gancho o comportamento é o de antes -- por isso a BC não muda.

        =================================================================
        `ponto_link` PODE SER UMA FUNÇÃO, E ISSO CONSERTA A VENDA DA HH
        =================================================================

        Coordenada fixa serve para quem sabe onde o link fica antes de abrir o
        diálogo -- é o caso da BC (`coords.vendor_sell_tab`). Mas quem acha o
        link POR IMAGEM não pode: o texto do link só existe na tela DEPOIS do
        clique direito, e procurá-lo antes é procurar o que não foi desenhado.

        Foi exatamente esse o defeito da venda da HH, medido em 09/09/2026: a
        tentativa morria em ~200 ms, sem clique nenhum, porque
        `_onde_clicar_no_link_de_vender` era chamada antes do diálogo e devolvia
        `None` para sempre. O log dizia "não abri a janela de venda" e mais
        nada.

        Passando uma FUNÇÃO, ela é chamada com o diálogo já aberto. Devolvendo
        `None`, o diálogo é fechado e nada é clicado -- o mesmo desfecho de
        `ainda_vale` recusando, e pelo mesmo motivo: clique de link sem link cai
        na cena 3D e o personagem sai andando da coordenada onde a venda
        funciona.

        Devolve se o clique no link saiu.
        """
        ctx = self.ctx

        # F12 PRESO DURANTE O PAR DE CLIQUES, e é a regra do usuário: *"sempre
        # que precisar o clique no NPC fora da cave é importante que o F12 esteja
        # apertado... só no par de clique, porque só atrapalha quando tenta
        # clicar no NPC em si."*
        #
        # AQUI E NÃO EM TRÊS LUGARES: todo clique de NPC do bot passa por esta
        # função -- o link da cave, o Rich, o Altar Stone e a saída. Um `with`
        # cobre os quatro, e nenhum futuro esquece de se proteger.
        #
        # O `with` solta a tecla em QUALQUER saída, inclusive exceção. Tecla presa
        # que não é solta faz o bot passar o resto da sessão jogando com ela
        # apertada.
        with esconder_jogadores.segurado(
                tecla=ctx.settings.keys.hide_players,
                segurar=ctx.key_down, soltar=ctx.key_up, log=ctx.log):
            return self._clicar_no_npc_e_no_link(
                ponto_npc, ponto_link, o_que, esperar_depois, ainda_vale)

    def _clicar_no_npc_e_no_link(
        self,
        ponto_npc: tuple[int, int],
        ponto_link: PontoDoLink,
        o_que: str,
        esperar_depois: float,
        ainda_vale: Callable[[], bool] | None = None,
    ) -> bool:
        """O par de cliques em si. Separado só para o `with` acima ficar legível."""
        ctx = self.ctx
        #ctx.log.info("Clique DIREITO no NPC em %s (%s)", ponto_npc, o_que)
        ctx.right_click(ponto_npc)

        aberto = self._esperar_o_dialogo(limite_da_espera_do_dialogo())
        if aberto is False:
            ctx.log.info(
                "O clique direito em %s não abriu o diálogo (%s). NÃO vou clicar "
                "no link: esse clique cairia no chão e o personagem sairia "
                "andando da coordenada certa.", ponto_npc, o_que,
            )
            # O CLIQUE ENGOLIDO É O EVENTO. Ver o bloco
            # `INTERVALO_DO_GUARDA_DE_JANELA`: a tentativa seguinte encontra a
            # tela limpa, e no caminho feliz isto não custa nada.
            self._desobstruir_se_faz_tempo(o_que)
            return False
        if aberto is None:
            # Sem imagem não há o que conferir. Segue, porque recusar aqui
            # deixaria a entrada impossível em cliente minimizado -- e a conferência
            # por POSIÇÃO, feita por quem chama, ainda pega o clique perdido.
            ctx.log.debug("Sem imagem para conferir o diálogo de %s; seguindo",
                          o_que)

        # O MUNDO AINDA É O MESMO? Última conferência antes do clique no link.
        # Ver o bloco `ainda_vale` na docstring de `_abrir_dialogo_e_clicar`.
        if ainda_vale is not None and not ainda_vale():
            ctx.log.info(
                "O diálogo abriu, mas o estado mudou entre os dois cliques "
                "(%s). NÃO vou clicar no link -- ele agora pertence a outra "
                "conversa.", o_que)
            self.fechar_dialogo()
            return False

        # O LINK, RESOLVIDO AGORA -- com o diálogo na tela. Ver a docstring de
        # `_abrir_dialogo_e_clicar`: quem acha o link por imagem só consegue
        # aqui, e coordenada fixa passa direto sem mudar nada.
        alvo = ponto_link() if callable(ponto_link) else ponto_link
        if alvo is None:
            ctx.log.warning(
                "O diálogo de %s abriu, mas não achei o link na tela. NÃO vou "
                "clicar no escuro -- o clique cairia na cena 3D e o personagem "
                "sairia andando da coordenada certa.", o_que)
            self.fechar_dialogo()
            return False

        #ctx.log.info("Clique ESQUERDO no link %s (%s)", alvo, o_que)
        ctx.click(alvo)
        if esperar_depois > 0:
            ctx.tick(esperar_depois)
        return True

    def fechar_dialogo(self) -> None:
        pontos = self._pontos("dialogue")
        if pontos:
            self.ctx.click(pontos["close"])
            self.ctx.tick(0.3)

    def clicar_link(self, template: str,
                    tentativas: int = 3) -> tuple[int, int] | None:
        """Clica num link do diálogo, localizado pelo texto. Devolve o ponto.

        Os links do diálogo mudam de posição conforme o texto do NPC, por isso
        são localizados por imagem e não por deslocamento fixo. O ponto devolvido
        é guardado por quem chama: para o MESMO NPC com o MESMO texto ele não
        muda, e repetir a busca por imagem em cada tentativa é o que fazia a
        entrada na cave custar mais de 10 segundos.
        """
        ctx = self.ctx
        for _ in range(tentativas):
            ctx.raise_if_stopped()
            ponto = self._achar_link(template)
            if ponto is not None:
                ctx.log.info("Clicando no link em %s", ponto)
                ctx.click(ponto)
                ctx.tick(0.75)
                return ponto
            ctx.tick(0.4)
        ctx.log.warning("Link %s não encontrado no diálogo", template)
        return None

    # ==================================================================
    # Stone City -> Ghost Din Woods
    # ==================================================================

    def preparar_entrada(self) -> None:
        """Deixa tudo pronto para a rajada de tentativas de entrada.

        Chamado UMA vez antes do laço: recentra a câmera e esquece as coordenadas
        aprendidas na run anterior. Esquecer é importante -- a posição do
        personagem mudou desde então, e um ponto de NPC velho apontaria para o
        chão. Clicar no chão faz o personagem ANDAR, ou seja, sair da coordenada
        de onde a cave pode ser aberta.
        """
        self._ponto_npc_entrada = None
        self._ponto_link_entrada = None
        self._falhas_rapidas = 0

        # O GUARDA DE JANELA, UMA VEZ, ANTES DA RAJADA. Daqui em diante saem
        # dois cliques por segundo na cena 3D disputando a vaga, e uma janela
        # aberta engole todos eles -- foi exatamente o que o print de 26/08/2026
        # mostrou. Aqui, e não dentro do laço: janela não aparece sozinha, e uma
        # captura por tentativa custaria caro justamente no trecho onde o
        # projeto cortou espera para caber. Ver `desobstruir_a_cena`.
        self.desobstruir_a_cena("as tentativas de entrada na cave")

        self.resetar_visao(forcar=True)

    def na_posicao_de_clicar(self, esperada: tuple[int, int],
                             tolerancia: float = TOLERANCIA_DA_POSICAO,
                             o_que: str = "clicar") -> bool:
        """O personagem está onde as coordenadas de clique foram medidas?

        Toda coordenada de NPC deste arquivo foi medida com o personagem PARADO
        num ponto exato. São cliques na cena 3D: a posição do personagem faz parte
        da coordenada. Alguns passos de distância giram o NPC na tela, o clique cai
        no chão, e o personagem anda -- afastando-se mais e garantindo que a
        tentativa seguinte também falhe.

        Sem leitura de posição devolve True: não há como conferir, e recusar
        travaria o bot num laço sem saída.
        """
        ctx = self.ctx
        atual = ctx.memory.position()
        if atual is None:
            return True

        # `distancia` VEM DO CORE (`core.rota`, importada no topo deste arquivo).
        #
        # Aqui havia `from . import mapa_bc` -- um import que sobreviveu a mudanca
        # de `bc/ui_service.py` para `bot/ui_do_jogo.py` (cd2ef2b) e passou a
        # apontar para `blazesbot/bot/mapa_bc`, que nao existe. Como o import era
        # LOCAL, nada quebrou no arranque: ele so estourava quando alguem chegava
        # no ponto e ia clicar num NPC.
        #
        # MEDIDO em 02/09/2026: 42 `cannot import name 'mapa_bc'` seguidos na fase
        # ENTRAR_NO_COVIL. O log dizia "Usando o Altar Stone para entrar no covil"
        # e um MILISSEGUNDO depois estourava -- o clique direito nunca saia. De
        # fora era "o dialogo do Altar Stone nao abre mais e o bot fica em loop".
        # `sair_da_cave` e a entrada da HH chamam esta mesma funcao e estavam com
        # o mesmo defeito, ainda nao observado.
        #
        # E o conserto NAO e reapontar para `bc/mapa_bc`: este arquivo serve TODOS
        # os ecossistemas, e `mapa_bc.distancia` ja era so um reexport de
        # `core.rota.distancia` (ver `mapa_bc.py`, "distancia vem de core/rota.py").
        quanto = distancia(atual, esperada)
        if quanto <= tolerancia:
            return True
        ctx.log.warning(
            "Estou em %s, a %.0f unidades de %s — longe demais para %s. As "
            "coordenadas de clique valem só a partir dali.",
            atual, quanto, esperada, o_que,
        )
        return False

    # ==================================================================
    # Encostar num ponto antes de clicar
    # ==================================================================

    def encostar_no_ponto(
        self,
        alvo: tuple[int, int],
        precisao: float,
        tentativas: int,
        segundos_por_tentativa: float,
        o_que: str,
    ) -> bool:
        """Anda os últimos passos até um ponto exato. NÃO CLICA DE FORA DELE.

        O painel de arredores caminha até PERTO -- ele aceita folga por
        construção. Clicar de onde ele largar foi o defeito medido em
        25/08/2026, na ida até a Fay: a 2 passos de distância o ponto genérico de
        NPC caía no White Eagle que estava no caminho, o diálogo não abria, e a
        rotina concluía "não estou em Stone City" e gastava o item de retorno.

        A mesma regra que `travel_to_vendor` já aplicava ao Rich Man: *"o clique
        cairia no chão e o personagem andaria, piorando a tentativa seguinte"*.

        Devolve False quando não conseguiu encostar; quem chama trata isso como
        "não consegui chegar", e insistir de longe é sempre pior.

        SEM LEITURA DE POSIÇÃO DEVOLVE True. Não há como conferir, e recusar aqui
        travaria a viagem num laço sem saída -- é o mesmo tratamento que
        `_no_ponto_do_vendedor` dá. Quem decide então é o diálogo abrir ou não.
        """
        ctx = self.ctx
        for _ in range(tentativas):
            ctx.raise_if_stopped()
            atual = ctx.memory.position()
            if atual is None:
                return True
            if distancia(atual, alvo) <= precisao:
                return True
            self.nav.goto(alvo, tolerance=precisao,
                          max_seconds=segundos_por_tentativa,
                          usar_mapa=False)

        ctx.log.warning(
            "Não consegui parar em %s para %s (estou em %s). NÃO vou clicar de "
            "fora do ponto: o clique pega outro alvo e o personagem anda, "
            "piorando a tentativa seguinte.",
            alvo, o_que, ctx.memory.position())
        return False

    # ==================================================================
    # Esperar uma troca de mapa
    # ==================================================================

    def esperar_a_chegada(
        self,
        chegou,
        teto: float,
        passo: float,
        o_que: str,
    ) -> bool:
        """Espera uma troca de mapa. Sai no INSTANTE em que `chegou()` confirma.

        `chegou` é um predicado sem argumentos -- normalmente uma leitura de
        posição, porque o campo de nome do lugar tem falha medida de ficar preso
        na área anterior.

        ESTOURAR O TETO NÃO É FALHA FATAL, e isso é deliberado. Quando a viagem
        devolve False, quem chamou costuma concluir "não estou onde deveria" e
        gastar um item de retorno -- uma pedra, ou a recarga do token. Um
        teleporte que demorasse meio segundo a mais viraria item gasto à toa.

        Então estourar vira AVISO no log e a vida segue; quem descobre que não
        saiu do lugar é a leitura de posição do passo seguinte, que já existe e
        não custa nada. Se o aviso aparecer com frequência, o teto é que está
        curto -- e a linha do log traz o número para decidir, em vez de palpite.
        """
        ctx = self.ctx
        comeco = time.time()
        limite = comeco + teto
        while True:
            ctx.raise_if_stopped()
            if chegou():
                ctx.log.info("%s confirmado em %.0f ms: %s | local %s", o_que,
                             (time.time() - comeco) * 1000,
                             ctx.memory.position(), ctx.memory.location())
                return True
            if time.time() >= limite:
                ctx.log.warning(
                    "%s NÃO confirmado em %.0f ms (teto): ainda em %s | local "
                    "%s. Seguindo -- o passo seguinte relê a posição.",
                    o_que, teto * 1000, ctx.memory.position(),
                    ctx.memory.location())
                return False
            ctx.tick(passo)

    # ==================================================================
    # Rolar a lista do diálogo
    # ==================================================================

    def rolar_o_dialogo(self, ate_ver: str,
                        passos: int = PASSOS_DE_ROLAGEM) -> tuple[int, int] | None:
        """Rola a lista do diálogo até o link aparecer. Devolve onde ele está.

        =================================================================
        POR QUE ISTO PRECISA EXISTIR
        =================================================================

        `clicar_link` procura o template do link na tela e desiste em três
        tentativas. Isso basta quando o link está na parte visível da lista -- e
        `Ghost Din Woods` (Need 7, nível 48) está, que é por que a Bewitcher Cave
        nunca precisou disto.

        `West Suburb of Stone City` (Need 5, nível 20) NÃO está: sem rolar, o
        diálogo do Transport Fay mostra de `Sky Village` a `Star Town`, e o
        template nunca vai aparecer por mais que se insista.

        =================================================================
        A SETA É ACHADA POR TEMPLATE, NÃO POR DESLOCAMENTO
        =================================================================

        E é a mesma decisão que vale para os links: *"os links do diálogo mudam
        de posição conforme o texto do NPC, por isso são localizados por imagem e
        não por deslocamento fixo"*.

        Aqui o motivo é ainda mais forte. Um deslocamento chutado a partir da
        moldura do diálogo erra por alguns pixels e o clique cai FORA da janela
        -- ou seja, na cena 3D --, e clique na cena faz o personagem ANDAR,
        saindo da coordenada de onde o NPC responde. É o estrago que este arquivo
        inteiro existe para evitar, e não vale a pena arriscá-lo para poupar um
        recorte de template.

        SEM O TEMPLATE, NÃO ROLA. Devolve None e diz no log exatamente o que
        recortar. Um bot que não rola falha de forma visível; um bot que clica no
        lugar errado sai andando e leva a run junto.

        =================================================================
        QUEM MANDA PARAR É O LINK, NÃO A CONTAGEM
        =================================================================

        Cada passo de rolagem é seguido de uma procura pelo link. `passos` é
        TETO, não gasto: assim que o link aparece, para. Rolar um número fixo de
        vezes seria a espera cega de sempre, e ainda por cima erraria quando a
        lista mudasse de tamanho (ela muda: os destinos dependem do nível do
        personagem).
        """
        ctx = self.ctx

        ponto = self._achar_link(ate_ver)
        if ponto is not None:
            return ponto

        seta = ctx.templates.load(TEMPLATE_DA_SETA_DE_ROLAGEM)
        if seta is None:
            ctx.log.warning(
                "Preciso rolar a lista do diálogo para achar %s, mas não tenho "
                "o template da seta (%s). Recorte a seta de rolagem PARA BAIXO "
                "do diálogo e salve em data/templates/ com esse nome -- sem "
                "ela eu não clico, porque um clique fora da janela cai na cena "
                "e faz o personagem andar.",
                ate_ver, TEMPLATE_DA_SETA_DE_ROLAGEM)
            return None

        for passo in range(1, passos + 1):
            ctx.raise_if_stopped()
            quadro = capture_window(ctx.hwnd)
            if quadro is None:
                ctx.log.debug("Sem imagem para achar a seta de rolagem")
                return None
            onde = find_template(quadro, seta, threshold=ANCHOR_THRESHOLD)
            if onde is None:
                ctx.log.info(
                    "A seta de rolagem sumiu no passo %s -- a lista chegou ao "
                    "fim e %s não estava nela.", passo, ate_ver)
                return None

            ctx.click(onde)
            ctx.tick(ESPERA_DA_ROLAGEM)

            ponto = self._achar_link(ate_ver)
            if ponto is not None:
                ctx.log.info("Link %s apareceu depois de %s rolagem(ns)",
                             ate_ver, passo)
                return ponto

        ctx.log.warning("Rolei %s vezes e %s não apareceu no diálogo",
                        passos, ate_ver)
        return None

    # ==================================================================
    # A viagem pelo NPC de transporte
    # ==================================================================

    def viajar_pelo_transporte(
        self,
        busca: str,
        confirma: str,
        link: str,
        ponto_do_npc: tuple[int, int],
        precisao: float,
        tentativas: int,
        segundos_por_tentativa: float,
        chegou,
        teto_do_teleporte: float,
        passo_da_espera: float,
        rolar: bool = False,
    ) -> bool:
        """Vai até um NPC de transporte e viaja por um dos destinos dele.

        É a sequência inteira, e ela é a mesma nas duas caves: procura o NPC no
        painel de arredores, deixa o pathfinding do jogo caminhar até perto,
        encosta no ponto exato, abre o diálogo, clica no destino e espera a troca
        de mapa. Só os NOMES mudam.

        `rolar=True` quando o destino não cabe na primeira tela da lista -- ver
        `rolar_o_dialogo`. A Bewitcher Cave não precisa; a HH precisa.

        F12 PRESO DO COMEÇO AO FIM. Não só em volta do clique: durante toda a
        sequência há cliques na cena 3D, e um jogador parado na frente do NPC
        engole qualquer um deles. O `with` solta a tecla em QUALQUER saída,
        inclusive por exceção -- tecla presa que não é solta faz o bot passar o
        resto da sessão jogando com ela apertada.
        """
        ctx = self.ctx
        with esconder_jogadores.segurado(
                tecla=ctx.settings.keys.hide_players,
                segurar=ctx.key_down, soltar=ctx.key_up, log=ctx.log):
            return self._viajar_pelo_transporte(
                busca, confirma, link, ponto_do_npc, precisao, tentativas,
                segundos_por_tentativa, chegou, teto_do_teleporte,
                passo_da_espera, rolar)

    def _viajar_pelo_transporte(
        self, busca, confirma, link, ponto_do_npc, precisao, tentativas,
        segundos_por_tentativa, chegou, teto_do_teleporte, passo_da_espera,
        rolar,
    ) -> bool:
        ctx = self.ctx

        ctx.log.info("Procurando o NPC de transporte (%s)", confirma)
        self.resetar_visao()
        # O TRAJETO É O DONO DO PAINEL: ele zera o orçamento de aberturas e
        # garante o fechamento em qualquer saída deste bloco, inclusive por
        # exceção. Ver `trajeto_pelo_painel`.
        with self.trajeto_pelo_painel("NPC de transporte"):
            info = self.buscar_npc(busca, confirmar=confirma)
            if info is None:
                return False
            if not self.ir_para_resultado(
                    confirma, coords=info.get("coords"),
                    max_seconds=120.0 * ctx.settings.time_factor):
                return False

        # O ÚLTIMO PASSO, APERTADO -- igual ao vendedor. Ver `encostar_no_ponto`.
        if not self.encostar_no_ponto(ponto_do_npc, precisao, tentativas,
                                      segundos_por_tentativa,
                                      f"falar com o {confirma}"):
            return False

        self.resetar_visao(forcar=True)
        if self.falar_com_npc() is None:
            ctx.log.warning("Não abri o diálogo do %s", confirma)
            return False

        if rolar and self.rolar_o_dialogo(link) is None:
            self.fechar_dialogo()
            return False

        ok = self.clicar_link(link) is not None
        if ok:
            self.esperar_a_chegada(chegou, teto_do_teleporte, passo_da_espera,
                                   "Teleporte")
        # DEPOIS da espera, e não antes: a troca de mapa fecha o diálogo
        # sozinha, então no caminho feliz `_pontos` não acha nada e isto custa
        # só uma captura -- o `tick` de dentro nem chega a rodar.
        self.fechar_dialogo()
        return ok
