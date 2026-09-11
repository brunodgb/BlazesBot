"""
Leitura de memória do client.exe do Talisman Online.

Mapa de offsets herdado dos bots do T-R0XX (ver.6139) e validado como
funcional na ver.6400 -- as atualizações do jogo não deslocaram o segmento
de dados.

REGRA DE PORTABILIDADE: se um dia o HP parar de ser lido corretamente, o
jogo relocou o segmento. Nesse caso APENAS `PLAYER_BASE_RVA` precisa ser
redescoberto -- todos os offsets internos da struct (0x3B8 etc.) são
estáveis desde a ver.5135. Ver README, seção "Quando o jogo atualizar".
"""
from __future__ import annotations

import logging
import math
import re
import struct
import time

import pymem
import pymem.memory

from .cronometro import cronometrar
from .rebase import SeletorDeEndereco

# Este módulo nunca teve log, e por bom motivo: leitura de memória falha o tempo
# todo durante queda e relogin, e devolver `None` em silêncio é o contrato. O
# log existe SÓ para a escolha de endereço -- que acontece uma vez por rótulo,
# por processo, e é a única coisa aqui que alguém precisa ver acontecer.
_logger = logging.getLogger("blazes.memory")

# ---------------------------------------------------------------------------
# Mapa de memória
# ---------------------------------------------------------------------------

IMAGE_BASE = 0x00400000

# RVA do ponteiro base do objeto do jogador.
#
#   ver.5135 -> 0x00D1EB80
#   ver.6139 -> 0x00D450EC
#   ver.6400 -> 0x00D4514C   <- em uso
#
# O valor da 6400 foi descoberto com a ferramenta 7-DESCOBRIR-MEMORIA e
# confirmado em DOIS clientes simultâneos, com personagens diferentes (nível 1 e
# nível 65) e resoluções diferentes: os dois apontaram para o mesmo RVA. A
# diferença em relação à 6139 é de apenas 0x60 bytes, o que explica por que as
# leituras falhavam sem nenhum erro visível -- o endereço ainda era legível, só
# não era o objeto do jogador.
PLAYER_BASE_RVA = 0x00D4514C
PLAYER_BASE = IMAGE_BASE + PLAYER_BASE_RVA  # 0x011450EC

# Offsets dentro da struct do jogador (estáveis entre versões)
OFF_NAME = 0xBC
OFF_HP = 0x3B8
OFF_MAX_HP = 0xDC
OFF_HP_BUFF = 0xE0
OFF_HP_PLUS = 0xE4
OFF_MP = 0x3BC
OFF_MAX_MP = 0x6EC
OFF_MP_BUFF = 0x6F0
OFF_LEVEL = 0x3C4
OFF_GOLD = 0x410
OFF_X = 0x810
OFF_Y = 0x814
OFF_BATTLE = 0x854
# Quantos bytes ler de cada lado de `OFF_BATTLE` em `battle_window()`. Serve para
# achar um offset melhor caso a flag de 0x854 se prove ruim: os bytes que viram no
# instante de entrar e sair de combate são os candidatos.
JANELA_DE_COMBATE = 0x10
OFF_SIT = 0x290
OFF_MOUNT = 0x8B0
OFF_PET_ACTIVE = 0x10A8

# ===========================================================================
# O BLOCO ATRASADO EM +0x3A0 -- o passado do estado, nao uma segunda fonte
# ===========================================================================
#
# O objeto do personagem guarda uma SEGUNDA COPIA do bloco de estado, deslocada
# 0x3A0 (achada pela varredura diferencial em 01/09/2026):
#
#     hp    0x3B8  <->  0x758        xp    0x3C8  <->  0x768
#     mp    0x3BC  <->  0x75C        ouro  0x410  <->  0x7B0
#
# HIPOTESE REFUTADA -- e vale ficar escrito, porque ela era boa e era falsa.
# A primeira leitura mostrou as quatro grandezas iguais em 6 de 6 clientes, e eu
# conclui que era uma SEGUNDA FONTE do mesmo instante: a exigencia deste projeto
# de "duas fontes no mesmo instante" satisfeita de graca, dentro de uma leitura
# so, com divergencia significando "a leitura esta errada AGORA".
#
# ERRADO. A validacao em campo deu 19 divergencias em 720 comparacoes, todas no
# `hp`, todas nas contas em COMBATE. Eu culpei a minha propria janela de leitura
# e passei a ler o par num bloco unico -- e as divergencias AUMENTARAM. Foi a
# amostragem de 20 ms que fechou a questao:
#
#   * 2945 amostras em tres contas, 10 divergentes;
#   * em 19 de 19 divergencias o espelho era MAIOR, nunca menor;
#   * as 10 amostras divergentes eram UM evento so, e o espelho alcancou o
#     original em 204 ms.
#
# ENTAO O QUE ELE E: uma copia ATRASADA cerca de 200 ms. Divergencia nao quer
# dizer "a leitura esta errada" -- quer dizer "este valor MUDOU nos ultimos
# ~200 ms". Como validador de leitura ele acusaria justamente durante o combate,
# que e quando o bot mais precisa confiar no que le.
#
# E ISSO NAO E CONSOLO: o atraso vira uma capacidade que o bot nao tinha. Comparar
# as duas copias diz "o HP caiu" SEM guardar estado entre ticks e SEM depender de
# quando foi o tick anterior -- numa leitura so. Ver `hp_caiu_agora`.
ESPELHO_DELTA = 0x3A0           # atraso medido: ~204 ms
OFF_HP_ESPELHO = 0x758          # = OFF_HP        + 0x3A0
OFF_MP_ESPELHO = 0x75C          # = OFF_MP        + 0x3A0
OFF_XP_ESPELHO = 0x768          # = OFF_XP        + 0x3A0
OFF_GOLD_ESPELHO = 0x7B0        # = OFF_GOLD      + 0x3A0

# ===========================================================================
# EXPERIENCIA -- dois acumuladores, e o significado NAO fechou
# ===========================================================================
#
# Os dois sobem JUNTOS a cada morte de alvo e nunca descem. Passos medidos em
# tres contas: +126/+22, +86/+13, +137/+22.
#
# QUAL DELES E A EXPERIENCIA DO PERSONAGEM: NAO SE SABE. A barra do jogo mostra
# o percentual em texto (4.5291% na conta medida), o que e gabarito perfeito --
# e NENHUM par de DWORD do objeto (varredura de 0x0 a 0x1200) da esse numero.
# Nenhum float do objeto vale 4.5291 nem 0.045291. E o total que a hipotese
# exigiria (~1.966.483) nao existe em lugar crivel da memoria.
#
# Entao os dois entram como OBSERVACAO, nao como "a XP". Quem usar precisa saber
# que o significado exato esta em aberto. Detalhe em
# `Teste-Ponteiros/PONTEIROS.md`, secao 1.5.
OFF_XP = 0x3C8
OFF_XP_SECUNDARIA = 0x3CC

# ===========================================================================
# RELOGIO EM MILISSEGUNDOS -- candidato a detector de cliente congelado
# ===========================================================================
#
# Sobe ~1000 por segundo, medido nos SEIS clientes sem excecao: passos de 3989 a
# 4104 em intervalos de 4 s, e passo medio de 1000 a 1005 ms/s numa segunda
# corrida com intervalo de 1 s.
#
# NAO E uptime do sistema (237 h no teste) nem do processo.
#
# HIPOTESE REFUTADA: numa primeira medicao os seis clientes leram
# aproximadamente 25.484.500 concordando dentro de 250 ms, e eu conclui que era
# uma "base de tempo comum as contas". ERRADO -- as seis tinham reiniciado
# juntas, e a concordancia era disso. Medindo de novo no dia seguinte, com as
# contas em idades diferentes, os valores foram 33,8M / 33,8M / 64,0M / 59,4M /
# 33,8M / 8,7M: tempos de vida DIFERENTES.
#
# Entao ele e POR PROCESSO, e o epoch segue desconhecido -- nao casa com uptime
# do sistema nem com o tempo desde o login. O que esta medido e so a TAXA.
#
# ATENCAO: no objeto de uma ENTIDADE o mesmo offset le valores pequenos, entao o
# epoch difere. O que esta medido vale para o objeto do PERSONAGEM.
#
# PARA QUE SERVIRIA: se este numero para de andar, o laco do jogo travou -- e
# isso se descobre sem captura de tela, com a janela em segundo plano. NUNCA
# TESTADO com um cliente de fato travado, entao nenhuma decisao depende disto.
OFF_RELOGIO_MS = 0x85C

# Endereços estáticos
ADDR_MODAL = 0x012CE35C  # DC / erro de login / caixa de confirmação (contextual)
ADDR_QUEUE = 0x011BDF1C  # string da fila de login
# ATENÇÃO: `ADDR_TARGET_ID` NÃO fica aqui -- ele é definido mais abaixo, junto
# da medição que o confirmou, e o valor certo é `IMAGE_BASE + 0x00D5CB80`
# (= 0x0115CB80).
#
# Até 10/09/2026 havia AQUI uma segunda atribuição, `ADDR_TARGET_ID =
# 0x0115CB20` -- o endereço da versão 6139, que está MORTO na 6400. Ela era
# inofensiva por acidente: a definição de baixo vem depois e vence no import.
# Mas era uma armadilha de duas pontas. Quem lesse esta seção acreditaria no
# valor morto, e bastava alguém reordenar o arquivo para a produção passar a ler
# endereço morto CALADO -- o modo de falha que este projeto mais combate.
#
# A regra que sai disto: endereço mora num lugar só, ao lado da medição que o
# sustenta. Travado por `tests/test_endereco_unico.py`.
ADDR_LOOT_WINDOW = 0x0105B958
ADDR_NOTIFICATION = 0x0117097C

# ===========================================================================
# O F12 PRESO -- a metade do patcher que era conferivel SO OLHANDO A TELA
# ===========================================================================
#
# O patcher nativo tem duas metades, e ele mesmo se anuncia como
# "Pet Bug Fix & F12 Hide": os seis NOPs (conferiveis em memoria desde
# 07/09/2026) e um `PostMessage(WM_KEYDOWN, VK_F12)` SEM o KEYUP, que deixa o
# cliente achando a tecla presa para sempre.
#
# A segunda metade nao tinha conferencia objetiva: `tools/conferir_petbug`
# mandava PARAR O BOT e apertar a tecla a mao para ver o efeito. Agora tem.
#
# COMO FOI ACHADO (10/09/2026): alternancia. Com a tecla presa pelo patcher,
# mandar KEYUP solta e KEYDOWN prende de novo; cinco fotos do banco de dados da
# imagem, exigindo `f1 == f3 == f5` e `f2 == f4` e `f1 != f2`, deixaram 32
# DWORDs. Destes, DOIS sao booleanos limpos, e os dois DISCRIMINARAM em 3 de 3
# rodadas de solta/prende:
#
#     0x0115CB88  presa=1  solta=0
#     0x011636BC  presa=1  solta=0
#
# E os seis clientes leram 1 nos dois logo depois do patcher rodar.
#
# SAO DOIS DE PROPOSITO. Nao se sabe qual dos dois e "a" bandeira -- podem ser
# jogadores e pets, ou o estado da tecla e o efeito dele. Como este projeto
# cobra duas fontes no mesmo instante, a redundancia vira o proprio controle:
# discordancia devolve `None`, nao um booleano com cara de certeza.
#
# O QUE O F12 *NAO* FAZ, e isso importa: o array de entidades NAO muda (37
# entradas com a tecla presa e 37 solta, medido). Ele tira da CENA, nao do jogo
# -- e e por isso que a leitura de alvo funciona normalmente com a tecla presa.
USAR_BANDEIRA_DO_F12 = True
ADDR_F12_PRESO = 0x0115CB88
ADDR_F12_PRESO_SEGUNDA = 0x011636BC
ADDR_SYSTEM_MENU = 0x012DC1F5
# Raiz das cadeias de UI (bolsa, diálogo, arredores).
#
# ERA 0x012CE2E0, QUE É DA VERSÃO 6139 E ESTÁ MORTO NA 6400.
#
# Medido com o `10-DESCOBRIR-ALVO.bat` em NOVE execuções (cinco clientes, duas
# rodadas), e o resultado foi unânime:
#
#   [0x012ce2e0] -> +0x18 = 0x253d7325   DESALINHADO, a cadeia morre no 2º elo
#   [0x012ce340] -> +0x18 = 0x3c969698   plausível
#                          0x105ad8b8    plausível
#                          0x37ccb0e8    plausível
#                          0x15036018    plausível
#                          0x15054018    plausível
#
# +0x60 é EXATAMENTE o mesmo deslocamento que a `PLAYER_BASE` sofreu entre as
# duas versões (0x00D450EC -> 0x00D4514C). O segmento de dados inteiro andou
# junto, e este endereço tinha ficado para trás.
#
# CONSEQUÊNCIA DIRETA: `CHAIN_BAG_OPEN` nasce aqui, e `bag_open()` falhou em
# 5 de 5 runs no log de dev -- 2 segundos perdidos por run esperando uma
# confirmação que não vinha. Se a cadeia inteira responder, isso volta.
ADDR_UI_ROOT = 0x012CE340
ADDR_CAMERA = 0x0116FFF4

# O MESMO ENDEREÇO, REBASEADO -- e este responde.
#
# MEDIDO em 25/08/2026 pelo `2-DIAGNOSTICO`, escrevendo em cada campo e vendo o
# termômetro reagir:
#
#     ADDR_CAMERA      (0x0116fff4) -> NULO
#     ADDR_CAMERA+0x60 (0x01170054) -> 0x15a0f3c8
#         rotacao 0.0   -> 5.0    o valor ficou, o termômetro não mexeu
#         angulo  41.6  -> 46.6   ESCREVE E MOVE A CÂMERA  (termômetro -18.2)
#         zoom    300.0 -> 305.0  ESCREVE E MOVE A CÂMERA  (termômetro +21.9)
#
# O `+0x60` é o mesmo deslocamento medido no `TARGET_ID` (GhostBot `0x0115CB20`
# -> 6400 `0x0115CB80`): é o banco de estáticos inteiro que andou na virada
# 6139 -> 6400, e a câmera é dele.
#
# A rotação não mexer o termômetro CASA com o sintoma do usuário: o View Reset
# já resolve esquerda/direita, e o que falta é cima/baixo -- que é o `angulo`.
ADDR_CAMERA_VIVA = ADDR_CAMERA + 0x60

# ===========================================================================
# A POSE DE REFERÊNCIA -- E O INTERRUPTOR É ELA MESMA
# ===========================================================================
#
# `(zoom, rotacao, angulo)` lidos da struct com a câmera na pose em que os
# cliques da cena 3D foram medidos.
#
# MEDIDA pelo usuário em 25/08/2026 com o `17-LER-CAMERA`, na pose em que os
# cliques funcionam:
#
#     ADDR_CAMERA+0x60   rotacao=0.000000  angulo=40.000000  zoom=300.000000
#
# O ÂNGULO 40 SEMPRE ESTEVE CERTO. O que estava errado era o **zoom**: a config
# trazia 380, e a 6400 usa 300. Como a escrita caía no `ADDR_CAMERA` morto,
# nunca deu para saber -- o número errado nunca chegou a ser aplicado.
#
# ===========================================================================
# É AQUI QUE SE MEXE. UM LUGAR SÓ.
# ===========================================================================
#
# Precisou de outra pose? Troque a tupla abaixo e pronto -- não há chave em
# `config.json`, não há campo na interface, não há nada para sincronizar.
#
# Já houve: a pose passou por `BotConfig.camera` e pelo `data/config.json`. Deu
# o problema clássico de valor em dois lugares -- o arquivo salvo trazia
# `[380.0, 0.0, 40.0]` e GANHAVA do padrão, então corrigir o código não chegava
# em quem já tinha config gravado. Um lugar só é mais fácil de mexer E não tem
# como divergir.
#
# A pose em uso vai para o LOG uma vez por sessão, para testar sem palpite.
#
# O termômetro lia 761.813538 neste instante, e NÃO 956.720459 -- mais uma razão
# para ele ter saído da decisão. Ver `ADDR_ANGULO_DA_CAMERA`.
#
# POR QUE O `(380, 0, 40)` HERDADO NÃO SERVIA:
#
#   * o `write_camera` do GhostBot é chamado de LUGAR NENHUM -- a única
#     ocorrência está num bloco de teste do `main()`, duas vezes comentada:
#     `# #p.write_camera(10000, 0, 50)`, com zoom 10000;
#   * o que o GhostBot faz de verdade é `reset_camera()`, que é um CLIQUE no
#     botão View Reset -- não toca em memória;
#   * o T-R0XX "[New Server]" não tem código de câmera nenhum.
#
# Ou seja: `(380, 0, 40)` não veio de bot que funcionasse. Era número sem
# procedência -- e metade dele estava errada.
#
# COMO REMEDIR: `17-LER-CAMERA.bat`, pôr a câmera na pose certa, copiar a última
# linha. Ela já sai no formato desta tupla.
POSE_DA_CAMERA: tuple[float, float, float] = (450.0, 0.0, 36.0)

# Quanto cada campo da pose pode variar e ainda contar como certo.
#
# Os três campos são ENTRADA, não valor derivado -- medido em 25/08: escritos,
# eles FICAM onde foram postos, ao contrário do termômetro, que o jogo desfaz.
# Entrada não deriva sozinha, então a folga só precisa cobrir ruído de float.
# PROVISÓRIO: vira medição quando o log do `17-LER-CAMERA` mostrar quanto os
# três oscilam de fato entre uma run e outra.
TOLERANCIA_DA_POSE = 0.001

# ===========================================================================
# O TERMÔMETRO DA CÂMERA -- LEITURA, NUNCA ESCRITA
# ===========================================================================
#
# `client.exe + 0xD6339C`, achado pelo usuário no Cheat Engine em 25/08/2026.
# Float, ESTÁTICO, e ele acompanha o ângulo da câmera: mexer para a esquerda ou
# para baixo diminui o valor; para a direita ou para cima, aumenta.
#
# ESCREVER NELE NÃO FUNCIONA, e isso é medição do usuário, não suposição:
#
#     *"eu testei setar manualmente pelo Cheat Engine, mas não aceita, ele volta
#      para o valor anterior e não muda nada na tela"*
#
# É a assinatura de um valor DERIVADO -- recalculado todo quadro a partir da
# fonte real.
#
# ELE NÃO É MAIS A RÉGUA DO BOT (25/08/2026). Serviu para o que precisava
# servir: foi ESCREVENDO na struct e vendo este número reagir que o
# `ADDR_CAMERA_VIVA` ficou provado. Mas como régua ele tem dois problemas:
#
#   1. **Não é só ângulo.** Escrever no `zoom` também o move. Um número que
#      responde a dois eixos não diz em qual deles a câmera está torta.
#   2. **Pode ser do LUGAR, não do jogo.** Dois diagnósticos do MESMO
#      personagem, câmera intocada, leram `1220.339355` e `756.339355` --
#      464,000000 cravados de diferença, com a fração idêntica.
#
# Quem responde "a câmera está na pose certa?" agora é `camera_na_pose_certa`,
# lendo os TRÊS campos da struct -- que são ENTRADA, ficam onde são postos, e
# não dependem de onde o personagem está. O termômetro fica no DIAGNÓSTICO.
ADDR_ANGULO_DA_CAMERA = IMAGE_BASE + 0x00D6339C

# O ângulo em que os cliques na cena 3D foram medidos.
#
# Medido pelo usuário: é o valor em que o jogo põe a câmera quando se marca o
# **Lock the View** nas opções de Gráficos e se dá OK. Andando ele oscila para
# 956,7199707 e volta sozinho ao parar -- 0,0005 de variação, que é ruído de
# interpolação e não desvio de pose.
#
# CONSTANTE DO PROJETO, não configuração por conta: é propriedade do JOGO, como
# os waypoints da cave. Se cada conta pudesse ter um ângulo, os pontos de tela
# medidos deixariam de valer para todas.
ANGULO_DA_CAMERA = 956.720459

# Quanto o ângulo pode variar e ainda contar como certo.
#
# 0,001 e não 0,0005 (a variação observada andando): o dobro do ruído medido,
# ainda ordens de grandeza abaixo de qualquer desvio real de arrasto.
TOLERANCIA_DO_ANGULO = 0.001

# Quanto o diagnóstico soma ao ângulo para PROVAR que a escrita move a câmera.
#
# Grande o bastante para o termômetro não confundir com ruído (0,0005 andando) e
# pequeno o bastante para a câmera mal piscar antes de o valor ser restaurado.
PROVA_DA_CAMERA = 5.0

# Teto da espera pelo termômetro depois de uma escrita na câmera.
#
# NÃO É UM CUSTO: a prova PERGUNTA ao termômetro a cada `PASSO_DA_PROVA_DA_
# CAMERA` e sai no instante em que ele mexe. O teto só existe para o caso em que
# ele nunca mexe -- e aí ele É a resposta.
#
# Por que existir: o termômetro é recalculado pelo jogo A CADA QUADRO. A primeira
# versão desta prova releu o termômetro na MESMA instrução da escrita, antes de
# o jogo ter desenhado um quadro sequer, e concluiu "não é a câmera" para um
# candidato que aceitou a escrita. Era o relógio, não o endereço.
TETO_DA_PROVA_DA_CAMERA = 1.0
PASSO_DA_PROVA_DA_CAMERA = 0.05
# Tamanho do time. ATENÇÃO: precisa do offset 0x3D8 -- ler o endereço direto
# devolve outra coisa. Descoberto no GhostBot.
ADDR_TEAM_SIZE = 0x0106D328

# ===========================================================================
# O TIME, PELO PONTEIRO REBASEADO -- medido em 31/08/2026
# ===========================================================================
#
# `ADDR_TEAM_SIZE` acima NUNCA RESPONDEU, e o preço está medido em
# `bot/team.py`: onze aceites falsos seguidos para um único convite, porque a
# confirmação dependia dele.
#
# O motivo era o de sempre, e o `CLAUDE.md` manda testá-lo antes de descartar
# endereço herdado: **o rebase +0x60 da virada 6139 -> 6400**. Ele foi aplicado
# ao `TARGET_ID` e esquecido aqui.
#
#     0x0106D388 - 0x0106D328 = 0x60
#
# A prova é a saída do `read_client_direct.py` do usuário, lida em SEIS clientes
# ao mesmo tempo (`_loop_all_clients.log`): `teamSize` bate com o time real e os
# nomes saem na MESMA ORDEM lidos de clientes diferentes -- o que é justamente o
# que a Fada precisa para saber qual retrato é de quem.
ADDR_TEAM = ADDR_TEAM_SIZE + 0x60

# Dentro da struct do time. Os nomes são uma tabela de passo UNIFORME: as
# medições deram 0x144, 0x1CC, 0x254, 0x2DC -- diferença constante de 0x88.
# Por isso o passo é UM número e não quatro offsets soltos.
OFF_TAMANHO_DO_TIME = 0x3D8
OFF_PRIMEIRO_MEMBRO = 0x144
PASSO_ENTRE_MEMBROS = 0x88

# O time do Talisman vai a cinco (o personagem mais quatro), mas a tabela lida
# tem quatro entradas. `teamSize` CONTA O PRÓPRIO PERSONAGEM: com 3 no time, os
# nomes 1..3 são válidos e o 4 vem lixo -- foi assim em todos os clientes do
# log, e é por isso que a leitura se guia pelo tamanho e não pelo lixo.
MAXIMO_DE_MEMBROS_LIDOS = 4

# Dentro do bloco de CADA membro (relativo ao começo dele, onde está o nome).
#
# MEDIDO em 31/08/2026 por cruzamento: lendo o cliente da `Tsuki69`, o bloco do
# membro que É ela trouxe `+0x034 = 2758` e `+0x03C = 5534` -- exatamente o
# `hp = 2758` e o `baseMana = 5534` que o mesmo cliente já entregava por outro
# caminho. Dois valores independentes batendo no mesmo instante é o que separa
# leitura de coincidência.
#
# ATENÇÃO -- ESTE CAMPO PARECE SER O MÁXIMO, NÃO A VIDA ATUAL.
#
# O cruzamento que o identificou foi feito com a `Tsuki69` de vida CHEIA, e ali
# `hp` e `baseHp` valiam o mesmo (2758): o campo batia com os dois. O par dele,
# `+0x3C`, deu 5534 -- que é o `baseMana`, e NÃO a mana atual (5327). Dois
# máximos lado a lado.
#
# Confirmado em campo em 01/09/2026: a Fada lia "vida 4555 de 4555" de um aliado
# ferido e concluía "já está com 100%" sem apertar a cura uma vez.
#
# POR ISSO ESTA LEITURA É RESERVA, não fonte. Quem manda é a própria vítima, que
# lê o próprio `hp`/`max_hp` e publica no mural. A vida ATUAL do companheiro
# ainda precisa ser achada -- use `read_client_direct.py --dump-team` com um
# aliado FERIDO, que é a condição que separa os dois campos.
OFF_MEMBRO_HP = 0x34
OFF_MEMBRO_MANA_MAXIMA = 0x3C
# NIVEL do companheiro, dentro do bloco dele. Achado por busca EXAUSTIVA nos
# 0x88 bytes -- todo offset, inclusive DESALINHADO, em int32/uint32/int16/
# uint16/byte/float, mais as formas derivadas da grandeza. Ele esta num offset
# desalinhado, e por isso uma busca por int32 alinhado nunca o acharia.
#
# CONFIRMADO em 4 membros distintos, 16 casamentos, contra o nivel que cada
# conta le do proprio objeto no mesmo instante.
OFF_MEMBRO_NIVEL = 0x42
OFF_TEAM_SIZE = 0x3D8
# Primeiro resultado do painel "Surroundings". A string tem o formato
#   ... text="Nome [x,y]" ...
# e traz NOME e COORDENADAS do destino -- dá para conferir se a busca achou o
# lugar certo antes de clicar, e saber exatamente onde o personagem vai parar.
ADDR_SURROUNDINGS = 0x012CE2DC
CHAIN_SURROUNDINGS = [0x18, 0x8C, 0x3C]
OFF_SURROUNDINGS_TEXT = 0x64
# Quantidade de buffs ativos.
ADDR_BUFF_COUNT_RVA = 0x00C20980
OFF_BUFF_COUNT = 0xCBC
# Quantos slots do array de entidades varrer. 512 cobre com folga o que o
# cliente carrega em volta do personagem; passar disso é ler lixo.
LIMITE_DE_ENTIDADES = 512
ADDR_ENTITY_SCAN_BASE = 0x0107C6B0

# ===========================================================================
# REGIÕES QUENTES -- a rota que fecha os 38% que o array de entidades perde
# ===========================================================================
#
# INTERRUPTOR, não comentário: desligar volta o comportamento exato de antes
# (só o array), e `tests/test_regioes_quentes.py` força este valor ligado.
#
# MEDIDO em 01/09/2026: o array acerta 62%; com esta rota atrás dele, 2.481 de
# 2.481 leituras resolveram, com nome, HP e id conferindo em todas. Porquê e
# alternativas reprovadas em `docs/decisoes/combate.md`.
USAR_REGIOES_QUENTES = True

# Tamanho do bloco lido por vez na varredura das regiões quentes. 1 MB é o
# ponto onde a leitura deixa de ser dominada pelo custo por chamada sem passar
# a alocar buffer grande à toa -- as regiões medidas têm 224 a 508 KB, então
# quase sempre cabe uma região por bloco.
PEDACO_DA_VARREDURA = 1024 * 1024

# Constantes do `VirtualQueryEx`, para separar região legível de armadilha.
# `MEM_PRIVATE` exclui a imagem e os arquivos mapeados: entidade mora no heap
# privado, e varrer o resto seria pagar por onde ela nunca está.
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100

# ===========================================================================
# O ALVO: O ID É CHAVE ESTRANGEIRA PARA A TABELA DE ENTIDADES
# ===========================================================================
#
# `ADDR_TARGET_ID` guarda o **ID da entidade selecionada**, e cada entidade
# guarda esse mesmo id em `+OFF_ENTITY_ID`. Achar o alvo é um JOIN.
#
# O PROJETO TINHA AS DUAS TABELAS E NÃO TINHA A CHAVE. `0x0115CB80` era
# descrito como *"só responde identidade, e não se sabe o que o valor É"*, e o
# array de entidades já era varrido com o HP certo -- o item 37 mediu 87,5% de
# acerto contra a barra POR ENTIDADE e 1,0% por ponteiro (`jogador+0x808`). O
# que faltava era saber DE QUEM era cada HP.
#
# A chave veio do `search_id()` do GhostBot, que roda na 6139:
#
#     targetid = read_int(0x115CB20)          # = ADDR_TARGET_ID - 0x60
#     base     = 0x0107C6B0                   # = ADDR_ENTITY_SCAN_BASE
#     while ...:
#         a = read_int(base)
#         if read_int(a + 0x8) == targetid:   # <<< a chave
#             pointer = a; break
#         base += 0x4
#     x = read_float(pointer + 0x810) / 20    # = OFF_X / 20
#
# Três coincidências que não são coincidência: a MESMA base do array, os MESMOS
# `OFF_X`/`OFF_Y` com a MESMA divisão por 20, e `0x115CB20 + 0x60`.
#
# CONFIRMADO NA 6400 em 25/08/2026, pelo `18-CASAR-ALVO`, numa luta inteira:
#
#     id=0x01340a01 obj=0x2f35a450 'Rose Snake' nv61 hp=100/100  barra=100.0%
#     id=0x01340a01 obj=0x2f35a450 'Rose Snake' nv61 hp=47/100   barra=47.0%
#     id=0x01340a01 obj=0x2f35a450 'Rose Snake' nv61 hp=6/100    barra=23.1%
#     id=0x01340a01 obj=0x2f35a450 'Rose Snake' nv61 hp=0/100    barra=0.0%
#
# A única divergência foi a TELA atrasada (23,1% quando a memória já lia 6%) --
# a memória estava certa. É o argumento que inverteu as fontes: quem decide
# passou a ser a memória, e a tela virou reserva.
#
# ESTA É A ÚNICA DEFINIÇÃO. O `0x0115CB20` da 6139 aparece acima só como
# registro do que foi removido em 10/09/2026, e no exemplo do GhostBot.
ADDR_TARGET_ID = IMAGE_BASE + 0x00D5CB80

# Onde a entidade guarda o próprio id. Vem do `b = a + 0x8` do `search_id()`.
OFF_ENTITY_ID = 0x8

# ===========================================================================
# SELEÇÃO VISUAL: PONTEIROS ESTÁTICOS (descobertos em 21/08/2026)
# ===========================================================================
#
# O `10-DESCOBRIR-ALVO` MODO 3 testou TODOS os RVAs do pointer scan contra o
# gabarito da tela (barra de HP).
#
# DESCOBERTA CHAVE: o jogo mantém uma **TABELA DE SLOTS ESTÁTICOS** para o
# alvo visual. A cada seleção (clique/TAB), o jogo escreve o endereço da
# entidade num slot diferente. Devemos ler TODOS os slots e pegar o que
# validar como entidade viva.
#
# RVAs descobertos (slots da tabela de seleção visual):
#   - 0x00C7C714  -> 0x0107C714
#   - 0x00C7C79C  -> 0x0107C79C
#   - 0x00C7C8FC  -> 0x0107C8FC
#   - 0x00C7C71C  -> 0x0107C71C (pointer scan anterior)
#   - 0x00C7C948  -> 0x0107C948 (pointer scan anterior)
#   - 0x00C7C758  -> 0x0107C758 (primeiro scan)
#   - 0x00C7C998  -> 0x0107C998 (primeiro scan)
#
# CONCLUSÃO: a seleção visual é guardada em MÚLTIPLOS endereços estáticos
# Cadeias de ponteiro em uso
CHAIN_BAG_OPEN = [0x18, 0x5C4, 0x0, 0xC, 0x1F8, 0x42C, 0xBA0]
CHAIN_BAG_1 = [0x838, 0xC4, 0x0, 0x8, 0x10]
CHAIN_BAG_2 = [0x838, 0xC4, 0x4, 0x8, 0x10]
# Terceira bolsa. O jogo tem até três (base + duas Expand Bag).
CHAIN_BAG_3 = [0x838, 0xC4, 0x8, 0x8, 0x10]
CHAIN_LOCATION = [0x7F8, 0xF4]
# Deslocamento do texto do nome do lugar dentro do objeto ao qual a cadeia
# acima chega. Fica nomeado porque é lido por três interpretações diferentes em
# `location_candidates` -- ver o comentário longo lá.
OFF_LOCATION_TEXT = 0x44C

# ===========================================================================
# LEITURAS DE UI POR MEMÓRIA -- vindas da auditoria do GhostBot
# ===========================================================================
#
# POR QUE ISTO VALE MUITO AQUI. O bot lê a interface por template matching, e a
# captura tem um problema conhecido: `PrintWindow` devolve QUADRO PRETO em cliente
# DirectX que não está em primeiro plano. Daí toda a distinção entre "conferi e não
# tem" e "não consegui conferir" espalhada pelo `ui_service`. Lendo da memória essa
# ambiguidade some -- e some para as janelas MINIMIZADAS, que é como o bot roda
# várias contas.
#
# PRIMEIRO RESULTADO DO PAINEL DE ARREDORES. O texto tem o formato
# `text="Nome [x,y]"`, com NOME E COORDENADA juntos. Isso é melhor do que o bot
# tem hoje: ele clica no primeiro resultado sem saber o que ele é.
ADDR_SUR_ROOT = 0x012CE2DC
CHAIN_SUR_FIRST = [0x18, 0x8C, 0x3C]
OFF_SUR_TEXT = 0x64

# CAIXA DE DIÁLOGO DE NPC ABERTA. É exatamente a pergunta que o bot faz antes de
# clicar no link "Bewitcher Cave" -- hoje respondida por template.
# A RAIZ ESTAVA MORTA SO POR CAUSA DO REBASE +0x60 (medido em 02/09/2026).
#
# `dialog_open()` devolvia "nao sei" em 600 de 600 leituras, e a conclusao facil
# era que a cadeia herdada de sete niveis tinha morrido na virada 6139 -> 6400.
# Estava tudo certo MENOS o primeiro DWORD: a raiz herdada le ZERO nos seis
# clientes, e a raiz + 0x60 resolve a cadeia INTEIRA nos seis.
#
# E a cadeia herdada e boa: os enderecos do meio DIFEREM entre processos (passam
# o teste de natureza) e o nivel `+0x1F8` volta para o mesmo no do `+0x4`, que e
# o vaivem tipico de pai/filho de no de UI.
#
# O VALOR: 16774 fechado, 16775 aberto -- o mesmo padrao N/N+1 da bolsa
# (902/903), e o 16775 e exatamente a constante herdada. Confirmado com o BC
# rodando: a conta em farm leu 16775 no instante em que a bandeira independente
# de painel tambem acusou dialogo. Qualquer OUTRO valor devolve `None`, porque
# nunca foi visto.
ADDR_DIALOG_ROOT = 0x0117B2DC
CHAIN_DIALOG = [0x70, 0x56C, 0xC, 0x4, 0x42C, 0x1F8, 0x240]
DIALOGO_ABERTO_VALOR = 16775
DIALOGO_FECHADO_VALOR = 16774

# NENHUM DOS DOIS FOI VERIFICADO NESTE CLIENTE. Vieram do GhostBot, que roda no
# mesmo jogo mas cujos ponteiros de alvo NÃO funcionaram aqui -- prova de que
# offset dele não é garantia. Por isso os dois leitores devolvem `None` em vez de
# adivinhar, e aparecem no `2-DIAGNOSTICO.bat` para serem conferidos ANTES de
# qualquer decisão do bot passar a depender deles.

# ===========================================================================
# ESTADO DE PAINEL DE UI POR MEMÓRIA -- o que sobreviveu ao campo
# ===========================================================================
#
# INTERRUPTOR: desligado, tudo volta ao comportamento de antes. Travado ligado
# por `tests/test_paineis_por_memoria.py`.
USAR_PAINEL_POR_MEMORIA = True

# O DISCRIMINADOR DO QUEST. Este é o achado sólido: `0` fechado, `1` aberto, e
# `0` com os outros CINCO painéis abertos (Item, Skill, Attribute, Guild,
# System), em 3 de 3 rodadas. Controle negativo: `0` em 5 de 5 contas que não
# tinham o Quest aberto, lidas no MESMO instante.
ADDR_QUEST_ABERTO = 0x012D0C78

# A BANDEIRA DE DIÁLOGO. Vale `0` ou um ponteiro de heap, e alterna com a tecla
# de qualquer um dos seis painéis testados.
#
# ELA É SINAL DE UMA VIA, E ISSO É MEDIÇÃO, NÃO CAUTELA:
#
#   ponteiro  ->  há um diálogo de UI na frente          (confiável)
#   zero      ->  NÃO PROVA que não há nada aberto       (refutado em campo)
#
# O contraexemplo, medido em 02/09/2026 lendo os valores crus junto com a cadeia
# de bolsa já validada (`CHAIN_BAG_OPEN`, 902 fechada / 903 aberta):
#
#     bandeira | segunda | cadeia | vezes
#     ---------+---------+--------+------
#        != 0  |   != 0  |   902  |  12    painel aberto, bolsa fechada
#        != 0  |   != 0  |   903  |  11    bolsa ABERTA, e `segunda` != 0
#        == 0  |   != 0  |   903  |   7    bolsa aberta com a bandeira em ZERO
#        == 0  |   == 0  |   902  |   6    nada aberto
#
# A terceira linha é a que importa: a bolsa estava aberta e a bandeira valia
# zero. Uma versão anterior deste patch chamava `bandeira == 0` de "o não com
# certeza" e classificava a bolsa por `segunda == 0` -- as duas coisas caíram, e
# caíram porque a validação em campo comparava com uma SEGUNDA FONTE. Sem essa
# comparação, o erro teria ido para produção parecendo certo.
#
# O QUE ELA AINDA SERVE PARA: quando vale um ponteiro, há diálogo na frente --
# e a §20 mediu que ela vê isso em 270 de 600 leituras nas quais `modal_open`,
# `dialog_open`, `loot_window_open` e `system_menu_open` TODOS diziam nada, com
# zero contradições no sentido inverso.
ADDR_PAINEL_ABERTO = 0x012CE3D8

# A "segunda fenda", vizinha da bandeira. Fica registrada porque aparece no
# diagnóstico ao lado dela, e porque foi a hipótese reprovada acima -- quem
# tentar de novo precisa saber que já foi tentado, e por que não deu.
ADDR_PAINEL_SEGUNDA_FENDA = 0x012CE3E0

# CUIDADO -- POR QUE ISTO **NÃO** SUBSTITUI `modal_open()`:
#
# `ADDR_MODAL` existe para dizer "há uma CAIXA DE CONFIRMAÇÃO, erro de login ou
# DC na frente", e o watchdog conclui DC pela PERSISTÊNCIA desse sinal. A
# bandeira acima é outra coisa: ela acende com a BOLSA e com o QUEST LOG, que
# não são modais. Trocar um pelo outro faria o watchdog ver "modal" toda vez que
# a bolsa abrisse -- trocaria um defeito conhecido por um pior.

# Valores sentinela observados no cliente
SIT_VALUE = 200
BAG_OPEN_VALUE = 903
# Valor da bolsa FECHADA. Medido em 02/09/2026 alternando a tecla `I` e lido em
# campo em seis contas: a cadeia vai de 902 para 903 e volta. O comentário
# herdado dizia "0 or 903", e o 0 nunca apareceu -- fechada é 902.
BAG_CLOSED_VALUE = 902
SYSTEM_MENU_VALUE = 1610612736

# HP máximo padrão de inimigos do covil (Gun Witch, Cemetery Guard, etc.)
# Usado para distinguir inimigos (100) de jogador/pet (243, 729, etc.)
ESCALA_DE_INIMIGO = 100


class MemoryError_(RuntimeError):
    """Falha ao acessar a memória do cliente."""


class Memory:
    """Wrapper de leitura/escrita da memória de uma instância do client.exe.

    Todas as leituras devolvem ``None`` em caso de falha em vez de levantar
    exceção, porque durante um desconecte ou fechamento do cliente é normal
    que ponteiros fiquem inválidos por alguns instantes. Quem consome decide
    o que fazer com o ``None``.
    """

    def __init__(self, pid: int) -> None:
        self.pid = pid
        # O endereço da entidade do alvo, guardado entre leituras. Ver
        # `alvo_atual` -- o SLOT do array muda durante a luta, o endereço não.
        self._obj_do_alvo: int | None = None
        # Regiões de heap onde entidade já apareceu, e o mapa de regiões do
        # processo. Os dois são POR PROCESSO: relogin troca o PID, e o `Memory`
        # antigo morre com o cache dentro -- é justamente o que se quer.
        self._regioes_quentes: dict[tuple[int, int], int] = {}
        self._regioes_cache: list[tuple[int, int]] | None = None
        self._semeou = False
        self.pm = pymem.Pymem()
        try:
            self.pm.open_process_from_id(pid)
        except Exception as exc:
            raise MemoryError_(
                f"Não foi possível abrir o processo {pid}. "
                "O BlazesBot precisa rodar COMO ADMINISTRADOR."
            ) from exc

        # Escolha entre o endereço da versão 6139 (herdado do GhostBot) e o
        # candidato +0x60 da 6400. Decide na primeira leitura de cada rótulo e
        # guarda. Vive e morre com esta instância -- uma por processo do
        # cliente --, então não sobra entrada apontando para um PID reciclado.
        # Ver `core/rebase.py` para o porquê inteiro.
        self._seletor = SeletorDeEndereco(registrar=_logger.info)

    # -- primitivas ---------------------------------------------------------

    def alive(self) -> bool:
        """True se ainda conseguimos ler a memória do processo."""
        return self.read_int(PLAYER_BASE) is not None

    def read_int(self, address: int) -> int | None:
        try:
            return self.pm.read_int(address)
        except Exception:
            return None

    def read_uint(self, address: int) -> int | None:
        """O mesmo valor de `read_int`, mas SEM sinal. Use para PONTEIRO.

        `pymem.read_int` devolve inteiro de 32 bits COM SINAL. Um valor com o bit
        mais alto ligado volta negativo, e aí duas coisas ruins acontecem:

          * `resolve` calcula `valor + offset` e produz um endereço negativo, que
            nunca lê -- a cadeia morre com aparência de "objeto liberado";
          * o diagnóstico imprime coisas como `0x-44C172F1`, que não é endereço
            nenhum e não ajuda ninguém a entender o que aconteceu. Foi exatamente
            o que apareceu no rastro do alvo em produção.

        Endereço é grandeza sem sinal. Ler ponteiro com sinal é um erro de tipo que
        só não aparece enquanto todos os ponteiros ficam abaixo de 0x80000000.
        """
        valor = self.read_int(address)
        return None if valor is None else valor & 0xFFFFFFFF

    def read_byte(self, address: int) -> int | None:
        try:
            return self.pm.read_bytes(address, 1)[0]
        except Exception:
            return None

    def read_float(self, address: int) -> float | None:
        try:
            return self.pm.read_float(address)
        except Exception:
            return None

    def write_float(self, address: int, value: float) -> bool:
        try:
            self.pm.write_float(address, float(value))
            return True
        except Exception:
            return False

    def resolve(self, base: int, offsets: list[int]) -> int | None:
        """Percorre uma cadeia de ponteiros e devolve o endereço final.

        Usa `read_uint`: cada elo é PONTEIRO, e ponteiro não tem sinal. Com
        `read_int` um elo acima de 0x7FFFFFFF virava negativo e a cadeia morria
        num endereço negativo, indistinguível de objeto liberado.

        Um elo nulo ou fora da faixa de usuário encerra a cadeia aqui mesmo, em vez
        de somar offset em cima de lixo e devolver um endereço que "lê" algo sem
        significado -- ler lixo com sucesso é pior que não ler.
        """
        addr = base
        for off in offsets:
            val = self.read_uint(addr)
            if val is None or val < 0x10000:
                return None
            addr = val + off
        return addr

    def read_string(self, pointer: int, offset: int = 0, length: int = 50) -> str | None:
        """Lê uma string seguindo um ponteiro.

        Detalhes que importam, aprendidos na prática:
          * 50 bytes, não 64. Ler além do necessário pode cruzar o fim de uma
            página de memória e a leitura inteira falha.
          * Se o tamanho pedido falhar, tenta tamanhos menores antes de desistir.
          * Sem filtro de "é ASCII?": esse filtro descartava nomes válidos e
            fazia a leitura do personagem devolver None com o jogo logado.
        """
        try:
            base = self.pm.read_int(pointer)
        except Exception:
            return None
        for size in (length, 32, 20, 12):
            try:
                raw = self.pm.read_bytes(base + offset, size)
            except Exception:
                continue
            text = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
            if text:
                return text
        return None

    def read_string_direct(self, address: int, length: int = 50) -> str | None:
        """Lê uma string diretamente de um endereço, sem seguir ponteiro."""
        for size in (length, 32, 20, 12):
            try:
                raw = self.pm.read_bytes(address, size)
            except Exception:
                continue
            text = raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
            if text:
                return text
        return None

    # -- personagem --------------------------------------------------------

    def _player_field(self, offset: int) -> int | None:
        return self.resolve(PLAYER_BASE, [offset])

    def char_name(self) -> str | None:
        """Nome do personagem. Tenta quatro caminhos antes de desistir.

        Vale a insistência: o nome é usado para renomear a janela, que é como
        cada instância fica identificável quando há várias contas abertas.
        """
        # 1. String logo após o objeto do jogador.
        name = self.read_string(PLAYER_BASE, offset=OFF_NAME)
        if name and re.match(r"^[\w'\- ]+$", name):
            return name

        # 2. O campo como ponteiro para a string.
        ptr = self._player_field(OFF_NAME)
        if ptr:
            second = self.read_string(ptr)
            if second and re.match(r"^[\w'\- ]+$", second):
                return second

        # 3. Endereço direto (alguns builds guardam a string no próprio campo).
        if ptr:
            third = self.read_string_direct(ptr)
            if third and re.match(r"^[\w'\- ]+$", third):
                return third

        # 4. Último recurso: aceita o que veio, mesmo sem passar no filtro.
        return name or None

    def hp(self) -> int | None:
        addr = self._player_field(OFF_HP)
        return self.read_int(addr) if addr else None

    def max_hp(self) -> int | None:
        """HP máximo real, somando buff e o bônus percentual do cliente."""
        base_addr = self._player_field(OFF_MAX_HP)
        buff_addr = self._player_field(OFF_HP_BUFF)
        plus_addr = self._player_field(OFF_HP_PLUS)
        if not (base_addr and buff_addr and plus_addr):
            return None
        base = self.read_int(base_addr)
        buff = self.read_int(buff_addr)
        plus = self.read_byte(plus_addr)
        if base is None or buff is None or plus is None:
            return None
        if plus >= 100:
            plus -= 100
        total = base + buff
        if plus == 1:
            return base
        return math.floor(((total * plus) / 100) + total)

    def bloco_atrasado(self) -> dict[str, tuple[int, int]] | None:
        """Cada grandeza como `(agora, ha ~200 ms)`. `None` = nao deu para ler.

        Le o original e a copia de `+0x3A0` num BLOCO UNICO -- isso e requisito,
        nao economia: em duas chamadas separadas o proprio intervalo entre elas
        entra na diferenca, e a diferenca e justamente o que se quer medir.

        NAO E VALIDADOR DE LEITURA. Ver o comentario de `ESPELHO_DELTA`: a copia
        esta atrasada ~204 ms, entao divergir significa "mudou agora", nao
        "errou". Medido em 2945 amostras de 20 ms em tres contas.
        """
        base = self.read_uint(PLAYER_BASE)
        if not base:
            return None
        fim = max(OFF_HP_ESPELHO, OFF_MP_ESPELHO,
                  OFF_XP_ESPELHO, OFF_GOLD_ESPELHO) + 4
        inicio = min(OFF_HP, OFF_MP, OFF_XP, OFF_GOLD)
        try:
            cru = self.pm.read_bytes(base + inicio, fim - inicio)
        except Exception:
            return None
        if cru is None or len(cru) < fim - inicio:
            return None

        def ler(off: int) -> int:
            return struct.unpack_from("<i", cru, off - inicio)[0]

        return {
            nome: (ler(off), ler(off_atrasado))
            for nome, off, off_atrasado in (
                ("hp", OFF_HP, OFF_HP_ESPELHO),
                ("mp", OFF_MP, OFF_MP_ESPELHO),
                ("xp", OFF_XP, OFF_XP_ESPELHO),
                ("ouro", OFF_GOLD, OFF_GOLD_ESPELHO))
        }

    def hp_caiu_agora(self) -> int | None:
        """Quanto o HP caiu nos ultimos ~200 ms. `0` = nao caiu. `None` = ilegivel.

        O valor e `atrasado - agora` quando positivo. Em 19 de 19 divergencias
        medidas o atrasado era MAIOR, nunca menor -- ou seja, o que aparece aqui
        e queda.

        A DIRECAO DE SUBIDA NAO FOI MEDIDA, e nao por falta de tentativa: nas
        contas livres o HP e o MP estavam CHEIOS (regeneracao nao mexe em nada) e
        nenhuma das nove teclas da barra gastou mana fora de batalha. Entao o
        `max(0, ...)` aqui nao e detalhe de implementacao -- e a unica coisa
        honesta a fazer com um caso que ninguem observou.

        POR QUE ISSO E DIFERENTE DE COMPARAR COM O TICK ANTERIOR: nao guarda
        estado, nao depende de quando foi o tick anterior, e nao mede o intervalo
        do bot -- mede o intervalo do JOGO, sempre o mesmo ~200 ms, numa leitura
        so. E responde com a janela em segundo plano.

        Nada no bot decide por isto ainda: e capacidade e diagnostico. Antes de
        alguem depender dela falta medir o caso da CURA e o do dano maior que a
        janela (dois golpes dentro dos mesmos 200 ms contam como um).
        """
        bloco = self.bloco_atrasado()
        if bloco is None:
            return None
        agora, atrasado = bloco["hp"]
        return max(0, atrasado - agora)

    def experiencia(self) -> tuple[int | None, int | None]:
        """Os dois acumuladores de progresso. `(0x3C8, 0x3CC)`.

        Sobem juntos a cada morte e nunca descem. QUAL DELES e a experiencia do
        personagem NAO ESTA DETERMINADO -- a barra do jogo mostra o percentual em
        texto e nenhum par de DWORD do objeto reproduz esse numero. Ver
        `OFF_XP` para a medicao completa.
        """
        a = self._player_field(OFF_XP)
        b = self._player_field(OFF_XP_SECUNDARIA)
        return (self.read_int(a) if a else None,
                self.read_int(b) if b else None)

    def relogio_ms(self) -> int | None:
        """Contador em milissegundos do objeto do personagem.

        Sobe ~1000/s nos seis clientes medidos. Origem do epoch NAO confirmada.
        Candidato a detector de cliente congelado -- nunca testado com um
        cliente de fato travado, entao nada decide por ele.
        """
        addr = self._player_field(OFF_RELOGIO_MS)
        return self.read_int(addr) if addr else None

    def mp(self) -> int | None:
        addr = self._player_field(OFF_MP)
        return self.read_int(addr) if addr else None

    def max_mp(self) -> int | None:
        base_addr = self._player_field(OFF_MAX_MP)
        buff_addr = self._player_field(OFF_MP_BUFF)
        if not (base_addr and buff_addr):
            return None
        base = self.read_int(base_addr)
        buff = self.read_int(buff_addr)
        if base is None or buff is None:
            return None
        return base + buff

    def level(self) -> int | None:
        addr = self._player_field(OFF_LEVEL)
        return self.read_byte(addr) if addr else None

    def gold(self) -> int | None:
        addr = self._player_field(OFF_GOLD)
        return self.read_int(addr) if addr else None

    def _coord(self, offset: int) -> int | None:
        addr = self._player_field(offset)
        if addr is None:
            return None
        raw = self.read_float(addr)
        if raw is None:
            return None
        value = raw / 20.0
        return math.floor(value) if value > 0 else math.ceil(value)

    def x(self) -> int | None:
        return self._coord(OFF_X)

    def y(self) -> int | None:
        return self._coord(OFF_Y)

    def position(self) -> tuple[int, int] | None:
        px, py = self.x(), self.y()
        return (px, py) if px is not None and py is not None else None

    # ======================================================================
    # A FLAG DE COMBATE: LEITURA, NUNCA DECISÃO (por enquanto)
    # ======================================================================
    #
    # Este leitor já foi REMOVIDO uma vez, junto com todos os usos, porque a flag
    # ficava ligada com qualquer mob por perto, demorava a baixar depois do último
    # golpe e já foi vista PRESA em ligado. Decisão em cima dela é decisão que
    # oscila sem o jogo ter mudado.
    #
    # Ele volta agora com uma finalidade diferente e um limite explícito: MEDIR.
    # A pergunta que interessa é "o alvo morreu?", e existe a suspeita de que o
    # quadro do alvo fica PARADO depois da morte do mob -- foi visto no jogo o
    # quadro exibindo 'Gun Witch' enquanto a tela escrevia "Invalid target." a cada
    # tecla e "Leave Battle" em verde. Se for isso, o HP do alvo não serve de
    # sinal de morte, e a transição desta flag serve.
    #
    # A ORDEM ACIMA FOI CUMPRIDA, e a decisão mudou: a flag AGORA MANDA no fluxo da
    # run de BC. As duas fases de combate (guardas e boss) começam quando ela liga e
    # terminam quando ela desliga; nenhum ponteiro de alvo participa mais. As três
    # ressalvas continuam valendo e cada uma tem contrapeso explícito -- confirmação
    # contínua para a piscada, prazo para a flag presa, HP próprio para a morte. O
    # desenho inteiro está no bloco no topo de `bot/combat.py`.
    #
    # A ferramenta `9-VIGIAR-COMBATE.bat` continua útil, e agora mais: ela grava as
    # transições da flag que passaram a comandar a run.
    #
    # Devolve TRÊS estados de propósito: `None` é "não consegui ler", que não é a
    # mesma coisa que "não está em combate".

    def in_battle(self) -> bool | None:
        """A flag de combate. `None` = não deu para ler.

        ATENÇÃO: esta flag PASSOU A DECIDIR o fluxo da run de BC. O comentário
        acima descrevia o desenho anterior, em que ela era só observada; hoje as
        duas fases de combate começam e terminam por ela (ver o bloco no topo de
        `bot/combat.py`).

        Os três estados continuam sendo devolvidos de propósito, e agora isso vale
        MAIS do que antes: quem decide em cima disto precisa saber a diferença
        entre "não está em combate" e "não consegui ler", porque confundir os dois
        faz uma falha de leitura virar "a luta acabou".
        """
        addr = self._player_field(OFF_BATTLE)
        if addr is None:
            return None
        valor = self.read_byte(addr)
        return None if valor is None else bool(valor)

    def battle_window(self) -> dict[int, int]:
        """Bytes em volta de `OFF_BATTLE`, para achar um candidato melhor.

        Se a flag de 0x854 se provar ruim, o que resolve é saber QUAL byte da
        estrutura do personagem vira no instante de entrar e sair de combate. Esta
        janela é lida nas transições pela ferramenta de vigia; comparando duas
        leituras seguidas, os offsets que mudaram são os candidatos.

        Sem isto, descobrir um offset novo custaria outra rodada inteira de
        medição no jogo.
        """
        saida: dict[int, int] = {}
        for delta in range(-JANELA_DE_COMBATE, JANELA_DE_COMBATE + 1):
            offset = OFF_BATTLE + delta
            addr = self._player_field(offset)
            if addr is None:
                continue
            valor = self.read_byte(addr)
            if valor is not None:
                saida[offset] = valor
        return saida

    def is_sitting(self) -> bool | None:
        """O personagem está SENTADO? `None` = não deu para ler.

        =================================================================
        TRI-ESTADO, E ISSO FOI CONSERTO -- 26/08/2026
        =================================================================

        Ela devolvia `bool` puro: falha de leitura virava `False`, ou seja
        "está de pé". Isso matou o mecanismo que usa esta leitura como PROVA
        de que a poção saiu (`bot/app/cura.py`), porque lá "não sentou" quer
        dizer "acabaram as poções" -- e uma leitura falha passou a produzir
        esse veredito sozinha.

        MEDIDO NO LOG DE PRODUÇÃO de 25/08/2026: 4 avisos de "acabaram as
        poções" na MESMA sessão em que houve 3 curas bem-sucedidas com 2
        poções cada. As poções existiam; a leitura é que dizia `False` sem
        saber.

        Pior: a tecla de sentar é INTERRUPTOR e o estado é lido ANTES de
        apertá-la. Com o personagem sentado pela poção e a leitura falhando,
        o `False` fazia o bot apertar a tecla e PÔR DE PÉ quem estava se
        recuperando.

        OS CONSUMIDORES DO BC NÃO MUDAM DE COMPORTAMENTO: os quatro usam a
        leitura em contexto booleano (`not estado.sitting`, `estado.sitting
        and k.sit`), e `None` é falso exatamente como `False` era. O ganho é
        só para quem sabe perguntar a diferença.
        """
        addr = self._player_field(OFF_SIT)
        if addr is None:
            return None
        valor = self.read_byte(addr)
        return None if valor is None else valor == SIT_VALUE

    def is_mounted(self) -> bool:
        addr = self._player_field(OFF_MOUNT)
        return bool(self.read_int(addr)) if addr else False

    def esconder_jogadores_ativo(self) -> bool | None:
        """O F12 esta preso, escondendo jogadores e pets? `None` = nao sei.

        `True` = as duas bandeiras dizem que sim. `False` = as duas dizem que
        nao. `None` = interruptor desligado, leitura falhou, ou **as duas
        discordaram** -- e discordancia e resposta honesta, nao defeito.

        Substitui a conferencia visual: `tools/conferir_petbug` mandava parar o
        bot e apertar a tecla a mao, porque com ela presa nao ha pet na tela,
        patcheado ou nao. Agora a resposta sai sem tela e sem parar nada.

        Medicao completa no comentario de `ADDR_F12_PRESO`. Em resumo:
        discriminou em 3 de 3 rodadas de solta/prende, e os seis clientes leram
        `True` logo depois do patcher nativo rodar.

        NAO decide nada no bot ainda -- e capacidade e diagnostico.
        """
        if not USAR_BANDEIRA_DO_F12:
            return None
        a = self.read_int(ADDR_F12_PRESO)
        b = self.read_int(ADDR_F12_PRESO_SEGUNDA)
        if a is None or b is None:
            return None
        if a not in (0, 1) or b not in (0, 1):
            return None            # valor nunca visto nao vira booleano
        if a != b:
            return None            # as duas fontes discordam: nao sei
        return a == 1

    def pet_active(self) -> bool | None:
        """O pet está invocado? `None` = não deu para ler.

        TRI-ESTADO pelo MESMO motivo de `is_sitting()`, e consertada no mesmo
        dia (26/08/2026): ela devolvia `False` quando a leitura falhava, e o
        modo APP usa esta resposta para decidir se aperta a tecla de invocar.

        O executor do APP já documentava as três respostas com todo cuidado
        (ver o topo de `bot/app/executor.py`) e explicava por que tratar `None`
        como `False` seria ruim: *"faria a macro apertar a tecla do pet em toda
        volta num cliente que não lê memória -- que é justamente o cliente para
        o qual este módulo foi feito"*. Em várias classes a tecla é
        INTERRUPTOR, então o toque a mais desinvoca o pet que acabou de vir.

        O contrato existia no consumidor; a fonte é que não o cumpria.

        OS CONSUMIDORES DO BC NÃO MUDAM: os seis usam a leitura em contexto
        booleano, e `None` é falso exatamente como `False` era.
        """
        addr = self._player_field(OFF_PET_ACTIVE)
        if addr is None:
            return None
        valor = self.read_byte(addr)
        return None if valor is None else bool(valor)

    # -- nome do lugar -----------------------------------------------------
    #
    # ESTA É A LEITURA MAIS FRÁGIL DO MAPA e o histórico explica o cuidado:
    # duas vezes em produção ela passou a devolver None no personagem que
    # rodava a BC, e só voltou depois de reabrir o jogo. Reabrir custa horas de
    # fila, então o objetivo aqui é NUNCA depender de um único caminho e NUNCA
    # descartar uma leitura em silêncio.
    #
    # A cadeia é longa -- [PLAYER_BASE] -> +0x7F8 -> +0xF4 -> +0x44C -- e cada
    # elo pode ser um ponteiro ou o próprio texto, dependendo do build. Em vez
    # de apostar em uma interpretação, o bot tenta as três que fazem sentido e
    # deixa `core.lugares` escolher a melhor. Tentar todas custa três leituras
    # de memória, ou seja, microssegundos.

    def location_candidates(self) -> list[tuple[str, str | None]]:
        """Todas as leituras plausíveis do nome do lugar, com a origem de cada.

        Devolve pares `(origem, string bruta)` SEM filtrar nada -- o filtro é
        do chamador. Preservar o bruto é o que permite ao log dizer "a memória
        devolveu isto e eu não reconheci" em vez de só "None", que era
        indistinguível de "não consegui ler".
        """
        candidatos: list[tuple[str, str | None]] = []

        ptr = self.resolve(PLAYER_BASE, CHAIN_LOCATION)
        if ptr is None:
            return candidatos

        # 1. O campo é um PONTEIRO e o texto está em [ptr] + 0x44C.
        #    É a interpretação que sempre funcionou; fica em primeiro.
        candidatos.append(
            ("ponteiro+0x44C", self.read_string(ptr, offset=OFF_LOCATION_TEXT,
                                                length=64))
        )
        # 2. O texto está INLINE, em ptr + 0x44C, sem derreferência.
        candidatos.append(
            ("inline+0x44C", self.read_string_direct(ptr + OFF_LOCATION_TEXT,
                                                     length=64))
        )
        # 3. Há mais uma derreferência: [ptr] + 0x44C guarda um char*.
        base = self.read_int(ptr)
        if base is not None:
            candidatos.append(
                ("ponteiro duplo", self.read_string(base + OFF_LOCATION_TEXT,
                                                    length=64))
            )
        return candidatos

    def location_trace(self) -> list[tuple[str, int | None]]:
        """Valor de CADA elo da cadeia do nome do lugar.

        É a informação que faltava nas duas ocorrências do bug: saber que o
        resultado final foi None não diz nada, mas saber que o elo `+0x7F8` virou
        0 (ou virou um endereço absurdo) aponta exatamente o que aconteceu --
        objeto liberado, cadeia trocada ou ponteiro sobrescrito.

        Devolve pares `(rótulo, valor)` na ordem em que são percorridos.
        """
        rastro: list[tuple[str, int | None]] = []
        base = self.read_int(PLAYER_BASE)
        rastro.append(("[PLAYER_BASE]", base))
        if base is None:
            return rastro
        addr = base
        for offset in CHAIN_LOCATION:
            valor = self.read_int(addr + offset)
            rastro.append((f"[0x{addr + offset:08X}] (+0x{offset:X})", valor))
            if valor is None:
                return rastro
            addr = valor
        rastro.append((f"texto em 0x{addr + OFF_LOCATION_TEXT:08X}", None))
        return rastro

    def location_detail(self) -> dict[str, object]:
        """Nome do lugar MAIS o rastro de como ele foi obtido.

        Existe para o log e para a ferramenta de diagnóstico: quando a leitura
        falha, é este dicionário que diz em qual elo ela falhou. Sem isso, o
        diagnóstico de "localização = None" virava adivinhação -- foi
        exatamente o que aconteceu nas duas ocorrências em produção.
        """
        from .lugares import Resolucao, limpar, melhor_candidato

        detalhe: dict[str, object] = {
            "nome": None,
            "reconhecimento": Resolucao.RECUSADO,
            "origem": "",
            "ponteiro": None,
            "brutos": {},
        }

        ptr = self.resolve(PLAYER_BASE, CHAIN_LOCATION)
        detalhe["ponteiro"] = hex(ptr) if ptr else None
        if ptr is None:
            detalhe["reconhecimento"] = "cadeia quebrada"
            return detalhe

        candidatos = self.location_candidates()
        detalhe["brutos"] = {
            origem: limpar(bruto) or repr(bruto)
            for origem, bruto in candidatos
        }
        nome, como, origem = melhor_candidato(candidatos)
        detalhe["nome"] = nome
        detalhe["reconhecimento"] = como
        detalhe["origem"] = origem
        return detalhe

    def location(self) -> str | None:
        """Nome do lugar, ou None se nenhuma leitura foi reconhecível.

        Diferente da versão anterior, uma string com hífen ("Man-eater Tribe")
        ou truncada ("8tcher Cave") NÃO é mais descartada: a primeira é aceita
        porque o filtro passou a admitir pontuação, e a segunda é completada
        pelo casamento por cauda contra o catálogo de nomes conhecidos.
        """
        from .lugares import melhor_candidato

        nome, _como, _origem = melhor_candidato(self.location_candidates())
        return nome

    # -- inventário / UI ---------------------------------------------------

    # -- UI lida por memória (auditoria do GhostBot) -----------------------

    # ======================================================================
    # A TABELA DE ENTIDADES -- o caminho que NÃO depende de `jogador + 0x80C`
    # ======================================================================
    #
    # `ADDR_ENTITY_SCAN_BASE` (0x0107C6B0) é um ARRAY DE PONTEIROS para as
    # entidades carregadas. Isso ficou provado juntando três medições: os ponteiros
    # estáticos encontrados para o boss e para dois mobs de campo caem TODOS dentro
    # dele --
    #
    #     0x0107C71C = base + 0x006C   ->  boss  @0x34FF2288
    #     0x0107C77C = base + 0x00CC   ->  boss  @0x34FF2288
    #     0x0107CE2C = base + 0x077C   ->  Mountain Demon
    #     0x0107CE70 = base + 0x07C0   ->  Snake Captor
    #
    # POR QUE ISTO IMPORTA MAIS QUE O `0x80C`. Com o boss SELECIONADO e sendo
    # ferido (HP caindo de 69 para 61), a varredura da struct inteira do personagem
    # não achou UM ÚNICO campo apontando para ele -- e `jogador + 0x80C` apontava
    # para outra entidade (nível 20, 243/243, na posição do personagem, quase certo
    # o pet). Ou seja: aquele campo não é "alvo atual", pelo menos não no covil.
    #
    # A tabela não tem esse problema: ela lista o que está carregado, e cada
    # entidade traz HP, HP máximo, nível, posição e nome nos MESMOS offsets do
    # personagem.

    def mana_maxima(self) -> int | None:
        """Mana máxima (`OFF_MAX_MP`). O par do `mp()`, que já existia sozinho."""
        addr = self._player_field(OFF_MAX_MP)
        if not addr:
            return None
        valor = self.read_int(addr)
        return valor if valor and valor > 0 else None

    def mana_pct(self) -> float | None:
        """Mana em porcentagem, ou `None` se não deu para ler.

        A Fada decide sentar e voltar a curar por este número; sem ele, ela não
        adivinha -- fica de pé e cura enquanto conseguir.
        """
        atual, maximo = self.mp(), self.mana_maxima()
        if atual is None or maximo is None or maximo <= 0:
            return None
        return max(0.0, min(100.0, atual * 100.0 / maximo))

    def vida_pct(self) -> float | None:
        """A vida do PERSONAGEM em porcentagem (0..100), ou `None`.

        =================================================================
        COMPARTILHADA ENTRE ECOSSISTEMAS, DE PROPÓSITO
        =================================================================

        "Quanta vida eu tenho" é pergunta sobre o JOGO, não sobre o BC nem sobre
        o APP -- como as teclas, como os offsets. Todo ecossistema presente e
        futuro pergunta a mesma coisa, e por isso a resposta mora aqui, no
        `core`, e não em nenhum dos dois.

        Antes desta função o cálculo estava escrito inline em `bot/navegacao.py`,
        e o APP ia escrever um terceiro. Ver `docs/decisoes/memoria-primeiro.md`,
        seção "Compartilhado e específico".

        NÃO CONFUNDIR COM `EstadoDoJogo.hp_pct`: aquela formata valores que o
        `snapshot()` JÁ leu, e não toca na memória. Esta LÊ. As duas devolvem o
        mesmo número quando o snapshot é do mesmo instante -- e a diferença
        importa em laço apertado, onde reler é o que se quer evitar.

        `None` é NÃO SEI, e é diferente de zero. Quem consome não pode tratar
        "não consegui ler" como "estou morrendo".
        """
        atual, maximo = self.hp(), self.max_hp()
        if atual is None or not maximo:
            return None
        return 100.0 * atual / maximo

    def id_do_alvo(self) -> int | None:
        """O id da entidade selecionada. `0` = sem alvo, `None` = não leu.

        ~1 µs, sem tocar na tela. Vale FORA da luta: dá para saber que existe
        alvo e que ele trocou sem pagar captura nenhuma.
        """
        return self.read_int(ADDR_TARGET_ID)

    def _procurar_entidade(self, alvo_id: int) -> int | None:
        """A entidade que tem este id em `+0x8`. Duas rotas, nesta ordem.

        =================================================================
        POR QUE O ARRAY NÃO BASTA -- E ISSO É MEDIÇÃO
        =================================================================

        `ADDR_ENTITY_SCAN_BASE` acerta **62%** das vezes (600 amostras por conta,
        01/09/2026). O resto NÃO é mob morto: uma varredura de força bruta dos
        912 MB de heap achou o objeto VIVO, com nome certo e HP caindo, em
        **6 de 6** casos em que o array falhou.

        E a varredura de quem aponta para um objeto que o array perde deu
        `0 na IMAGEM, 24 no heap`: **nenhuma referência estática**. Logo o array
        não é o container de entidades, é uma tabela TRANSITÓRIA -- alargar de
        512 para mais slots não resolve, porque o objeto não está em endereço
        estático nenhum quando o array falha.

        O desmonte de `client.exe+411A70` / `+4110A0` confirma pelo outro lado:
        o container do jogo é uma ÁRVORE rubro-negra (`_Left/_Parent/_Right`,
        chave em `+0x0C`, `_Isnil` em `+0x15`), e não um array. Mas a árvore
        daquele lookup NÃO guarda o ponteiro da entidade em `nó+0x10` -- 23
        referências ao objeto do alvo, zero em nó de árvore -- então descer por
        ela ainda não é caminho.

        =================================================================
        ROTA 2: AS REGIÕES QUENTES
        =================================================================

        O que resolveu foi observar ONDE as entidades moram. Elas ficam em
        POUCAS regiões do heap -- medido: 3 regiões, 960 KB de 914 MB (**0,1%**).
        Varrer só essas custa **0,25 ms**, contra 3,2 ms do array e 741 ms da
        varredura total.

        As regiões são aprendidas: toda entidade encontrada marca a sua. E a
        unidade é REGIÃO DO `VirtualQueryEx`, não intervalo `min..max` -- a
        primeira tentativa usou intervalo e degradou para 6,6 ms quando dois
        grupos distantes entraram nele (as entidades NÃO ficam num pool
        contíguo: foram vistas em `0x2C8Axxxx`, `0x315Axxxx` e `0x3184Bxxxx`).

        RESULTADO: **2.481 de 2.481 leituras** (100%), nome e HP em todas, id
        conferindo em todas, zero divergência. Detalhe em
        `Teste-Ponteiros/RESULTADOS.md` seção 13.
        """
        vistos: set[int] = set()
        for i in range(LIMITE_DE_ENTIDADES):
            obj = self.read_uint(ADDR_ENTITY_SCAN_BASE + i * 4)
            if obj is None or obj < 0x10000 or obj % 4 or obj in vistos:
                continue
            vistos.add(obj)
            if self.read_int(obj + OFF_ENTITY_ID) == alvo_id:
                self._marcar_regiao_quente(obj)
                return obj
        if not USAR_REGIOES_QUENTES:
            return None
        # Semeia na PRIMEIRA falha do array, não no construtor: quem nunca
        # perde uma entidade não paga nada por esta rota.
        if not self._semeou:
            self._semeou = True
            self.semear_regioes_quentes()
        return self._procurar_nas_regioes_quentes(alvo_id)

    # -- regiões quentes: a rota que fecha os 38% que o array perde --------

    def _regioes_do_heap(self) -> list[tuple[int, int]]:
        """As regiões de heap comprometidas, do `VirtualQueryEx`. Uma vez só.

        Não é cache de conveniência: enumerar 900 MB de regiões custa dezenas de
        ms, e o mapa de regiões de um processo em regime não muda a ponto de
        importar aqui. Quem precisa de frescor é a CONFERÊNCIA do id, e essa
        roda a cada leitura.
        """
        if self._regioes_cache is not None:
            return self._regioes_cache
        regioes: list[tuple[int, int]] = []
        addr = 0
        try:
            while addr < 0x7FFF0000:
                mbi = pymem.memory.virtual_query(self.pm.process_handle, addr)
                if mbi is None:
                    break
                base = int(mbi.BaseAddress)
                tamanho = int(mbi.RegionSize)
                if tamanho <= 0:
                    break
                comprometida = (mbi.State == MEM_COMMIT
                                and not (mbi.Protect & PAGE_NOACCESS)
                                and not (mbi.Protect & PAGE_GUARD)
                                and mbi.Type == MEM_PRIVATE)
                if comprometida:
                    regioes.append((base, base + tamanho))
                addr = base + tamanho
        except Exception:
            # Enumeração é otimização, nunca requisito: sem ela a rota 2 apenas
            # não responde, e o bot segue com o array.
            pass
        self._regioes_cache = regioes
        return regioes

    def _marcar_regiao_quente(self, obj: int) -> None:
        """Aprende que entidade mora na região deste endereço."""
        if not USAR_REGIOES_QUENTES:
            return
        for ini, fim in self._regioes_do_heap():
            if ini <= obj < fim:
                self._regioes_quentes[(ini, fim)] = (
                    self._regioes_quentes.get((ini, fim), 0) + 1)
                return

    def semear_regioes_quentes(self) -> int:
        """Aprende as regiões a partir de TODAS as entidades do array.

        Resolve o ARRANQUE A FRIO. Medido: numa bateria de 700 amostras, o
        ÚNICO caso em que nenhuma rota barata respondeu foi a amostra 0 -- sem
        região aprendida, a rota 2 não tem onde varrer, e só a força bruta
        (741 ms) respondeu. Semeando, a bateria seguinte fechou 492/492 sem
        nunca precisar da força bruta.

        Não espera pelo ALVO: qualquer entidade do array serve para aprender a
        região, e o array quase sempre tem várias (medido: 24 em 5,16 ms).
        """
        if not USAR_REGIOES_QUENTES:
            return 0
        achadas = 0
        vistos: set[int] = set()
        for i in range(LIMITE_DE_ENTIDADES):
            obj = self.read_uint(ADDR_ENTITY_SCAN_BASE + i * 4)
            if obj is None or obj < 0x10000 or obj % 4 or obj in vistos:
                continue
            vistos.add(obj)
            ident = self.read_int(obj + OFF_ENTITY_ID)
            if ident is None or ident == 0:
                continue
            nivel = self.read_byte(obj + OFF_LEVEL)
            if nivel is None or not (1 <= nivel <= 250):
                continue
            self._marcar_regiao_quente(obj)
            achadas += 1
        return achadas

    def _procurar_nas_regioes_quentes(self, alvo_id: int) -> int | None:
        """Varre só as regiões onde entidade já apareceu, as mais povoadas antes.

        Entidade nova quase sempre nasce onde as outras já estão, e é por isso
        que a ordem é por povoamento.
        """
        if not self._regioes_quentes:
            return None
        agulha = struct.pack("<i", alvo_id)
        ordem = sorted(self._regioes_quentes.items(), key=lambda kv: -kv[1])
        for (ini, fim), _quantas in ordem:
            pos = ini
            while pos < fim:
                tamanho = min(PEDACO_DA_VARREDURA, fim - pos)
                try:
                    dados = self.pm.read_bytes(pos, tamanho)
                except Exception:
                    pos += tamanho
                    continue
                de = 0
                while True:
                    i = dados.find(agulha, de)
                    if i < 0:
                        break
                    de = i + 1
                    if i % 4 or i < OFF_ENTITY_ID:
                        continue
                    obj = pos + i - OFF_ENTITY_ID
                    # A conferência é o que impede devolver lixo: o id tem de
                    # bater de novo na leitura direta, e o nível tem de ser de
                    # nível.
                    if self.read_int(obj + OFF_ENTITY_ID) != alvo_id:
                        continue
                    nivel = self.read_byte(obj + OFF_LEVEL)
                    if nivel is None or not (1 <= nivel <= 250):
                        continue
                    return obj
                # sobreposição: o id não pode ser cortado na fronteira do pedaço
                pos += (tamanho - OFF_ENTITY_ID - 4
                        if tamanho == PEDACO_DA_VARREDURA else tamanho)
        return None

    @cronometrar("memoria.alvo_atual")
    def alvo_atual(self) -> dict | None:
        """O ALVO, inteiro, da memória. `None` = sem alvo ou não achei.

        Devolve `obj`, `id`, `nome`, `nivel`, `hp`, `max_hp`, `pct` e `pos`.

        =================================================================
        ISTO SUBSTITUI A TELA, E ISSO É MEDIÇÃO
        =================================================================

        A barra desenhada erra e **erra calada** -- foi o defeito mais caro
        desta área. No log de confirmação, o único ciclo em que memória e tela
        discordaram foi a TELA lendo 23,1% enquanto a memória já lia 6%. A tela
        atrasa; a memória não.

        Aqui não existe "0,7% com o mob morto", não existe barra amarela
        sobreposta à vermelha para desentortar, não existe marcador com falso
        positivo, e não existe captura. `hp == 0` é morte, e ponto.

        =================================================================
        O ATALHO DO PONTEIRO
        =================================================================

        O SLOT do array muda durante a luta (medido: 30 -> 29 -> 28 na mesma
        luta, conforme entidades em volta somem), mas o ENDEREÇO da entidade
        não. Então o caminho normal é UMA leitura para conferir que o `obj`
        guardado ainda responde por este id -- a varredura de
        `LIMITE_DE_ENTIDADES` slots só roda quando o alvo troca.
        """
        alvo_id = self.id_do_alvo()
        if not alvo_id:
            self._obj_do_alvo = None
            return None

        obj = self._obj_do_alvo
        if obj is None or self.read_int(obj + OFF_ENTITY_ID) != alvo_id:
            obj = self._procurar_entidade(alvo_id)
            self._obj_do_alvo = obj
        if obj is None:
            return None

        hp = self.read_int(obj + OFF_HP)
        maximo = self.read_int(obj + OFF_MAX_HP)
        if hp is None or maximo is None or maximo <= 0 or hp < 0 or hp > maximo:
            # Struct inconsistente: melhor "não sei" do que um HP inventado.
            # É a mesma regra da régua da barra, que também sabe dizer isso.
            return None

        bx = self.read_float(obj + OFF_X)
        by = self.read_float(obj + OFF_Y)
        pos = None if bx is None or by is None else (
            math.floor(bx / 20.0) if bx > 0 else math.ceil(bx / 20.0),
            math.floor(by / 20.0) if by > 0 else math.ceil(by / 20.0))

        return {
            "obj": obj,
            "id": alvo_id,
            "nome": self._nome_da_entidade(obj),
            "nivel": self.read_byte(obj + OFF_LEVEL),
            "hp": hp,
            "max_hp": maximo,
            "pct": hp / maximo,
            "pos": pos,
        }

    def entidades_vivas(self, limite: int = LIMITE_DE_ENTIDADES) -> list[dict]:
        """Entidades carregadas e vivas, lidas da tabela do cliente.

        Devolve dicionários com `obj`, `hp`, `max_hp`, `nivel`, `pos` e `nome`,
        ordenados por distância do personagem -- que é a ordem em que o bot
        pergunta "quem está na minha frente?".

        Cada entrada da tabela é um ponteiro. Slots vazios e lixo são descartados
        pela mesma validação usada na descoberta: nível entre 1 e 200, HP máximo
        plausível, HP não maior que o máximo, e coordenada diferente de (0,0).
        """
        eu = self.position()
        achados: list[dict] = []
        vistos: set[int] = set()

        for i in range(limite):
            obj = self.read_uint(ADDR_ENTITY_SCAN_BASE + i * 4)
            if obj is None or obj < 0x10000 or obj % 4 or obj in vistos:
                continue
            vistos.add(obj)

            nivel = self.read_byte(obj + OFF_LEVEL)
            if nivel is None or not 1 <= nivel <= 200:
                continue
            maximo = self.read_int(obj + OFF_MAX_HP)
            if maximo is None or not 1 <= maximo <= 5_000_000:
                continue
            hp = self.read_int(obj + OFF_HP)
            if hp is None or hp < 0 or hp > maximo:
                continue

            bx = self.read_float(obj + OFF_X)
            by = self.read_float(obj + OFF_Y)
            if bx is None or by is None:
                continue
            pos = (math.floor(bx / 20.0) if bx > 0 else math.ceil(bx / 20.0),
                   math.floor(by / 20.0) if by > 0 else math.ceil(by / 20.0))
            if pos == (0, 0):
                continue

            achados.append({
                "obj": obj,
                "hp": hp,
                "max_hp": maximo,
                "nivel": nivel,
                "pos": pos,
                "nome": self._nome_da_entidade(obj),
                "distancia": (math.hypot(pos[0] - eu[0], pos[1] - eu[1])
                              if eu else float("inf")),
            })

        achados.sort(key=lambda e: e["distancia"])
        return achados

    def inimigos_proximos(self, raio: float = 60.0) -> list[dict]:
        """Entidades em escala de INIMIGO, ordenadas por distância.

        O FILTRO É O HP MÁXIMO IGUAL A 100, e ele sai direto da medição: todo mob
        lido até agora tem HP máximo 100, porque o cliente entrega o HP do inimigo
        já em PORCENTAGEM, não em pontos de vida --

            Gun Witch ......... 100/100, depois 3/100, depois 0/100
            Mountain Demon .... 100/100 e 33/100
            Poison Mushroom ... 28/100
            Snake Captor ...... 66/100
            Blaze Skull Marshal 69/100 e 61/100   <- o BOSS, mesma escala

        Quem NÃO está nessa escala não é inimigo: jogadores e pets aparecem com
        243/243 e 729/729, e havia um de 48/48. Foi justamente uma entidade de
        243/243 que `jogador + 0x80C` apontou durante a luta inteira do boss.

        O raio existe porque a tabela lista o que está carregado na instância
        inteira, não só o que está na frente do personagem.

        ATENÇÃO: o filtro deixa passar NPC. `Skull Herald` (100/100) e
        `Cemetery Guard` (100/100) também estão nessa escala. Para o covil isso não
        atrapalha -- o Skull Herald fica longe do ponto dos guardas -- mas quem
        precisar da diferença tem o nome, que agora lê nas duas formas de `+0xBC`.
        """
        return [e for e in self.entidades_vivas()
                if e["max_hp"] == ESCALA_DE_INIMIGO and e["distancia"] <= raio]

    # Caracteres que aparecem em nome de personagem e de mob do Talisman.
    # Fora daqui é lixo binário que o `decode(errors="ignore")` deixou passar.
    _LETRAS_DE_NOME = frozenset(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    _CARACTERES_DE_NOME = _LETRAS_DE_NOME | frozenset("0123456789 '-._")

    # Limites do nome. 2 porque existe mob de nome curto; 31 porque o campo
    # `+0xBC` é lido em 32 bytes e o último é o terminador.
    _MINIMO_DO_NOME = 2
    _MAXIMO_DO_NOME = 31

    @staticmethod
    def _parece_nome(texto: str) -> bool:
        """O texto lido de `+0xBC` é um NOME, ou é lixo binário?

        `read_string_direct` decodifica com `errors="ignore"`, então qualquer
        endereço devolve *alguma* string. Sem este filtro, `entidades_vivas`
        batiza entidade com resto de struct e o censo vira ficção.

        REESCRITO em 25/08/2026: o original foi levado junto na limpeza da
        leitura de alvo por ponteiro, e `entidades_vivas` passou a estourar
        `AttributeError` no meio do `2-DIAGNOSTICO`. O critério é o mesmo de
        sempre -- ASCII de nome, tamanho de nome, e pelo menos duas letras --
        e nenhuma decisão do bot depende dele: o nome só aparece em
        diagnóstico e log. Ver `docs/decisoes/combate.md`.
        """
        if not texto:
            return False
        texto = texto.strip()
        if not (Memory._MINIMO_DO_NOME <= len(texto) <= Memory._MAXIMO_DO_NOME):
            return False
        if any(c not in Memory._CARACTERES_DE_NOME for c in texto):
            return False
        # Duas letras, não uma: "1 " passa em tudo acima e não é nome.
        return sum(c in Memory._LETRAS_DE_NOME for c in texto) >= 2

    def _nome_da_entidade(self, obj: int) -> str | None:
        """Nome de UMA entidade, tentando as duas formas de `+0xBC`.

        Inline em umas, PONTEIRO em outras -- o boss é do segundo tipo, e foi por
        isso que a busca por string não o encontrava.

        =================================================================
        O PONTEIRO VEM PRIMEIRO, E ISSO É MEDIÇÃO
        =================================================================

        A ordem já foi a inversa, e o nome saía ERRADO em 79% das leituras.
        Medido em 01/09/2026, 38 amostras do mesmo mob:

            'Burning Deadwood'   8 vezes   (certo)
            'o1Shaman'  '1Shaman'  30 vezes   (lixo)

        Os bytes explicam. `+0xBC` guarda um PONTEIRO, e logo depois dele há
        um buffer com resto de OUTRA entidade:

            +0x0B8  FF FF FF FF | D8 6F 82 31 | 53 68 61 6D 61 6E 00
                                  ^ ponteiro    ^ buffer velho: "Shaman"

        Ler inline devolve os bytes do próprio ponteiro seguidos do buffer:
        `D8 6F 82 31` + `Shaman` = `.o.1` + `Shaman` = **'o1Shaman'**. É a
        origem de toda a família (`'X1Shaman'`, `'71Shaman'`, `'L4Shaman'`,
        `'6P4Shaman'`...): o prefixo varia porque o PONTEIRO varia.

        E `_parece_nome` APROVA esse lixo -- `_CARACTERES_DE_NOME` aceita
        dígito, e tem de aceitar: `Tsuki69` e `WizzOfBlazes4` são nomes de
        jogador legítimos. Então não há régua que separe os dois casos, e a
        única correção certa é a ORDEM.

        AS DUAS VIAS CONTINUAM NECESSÁRIAS. Na medição, ~80% dos nomes saíram
        pelo ponteiro e ~20% legitimamente inline. Tirar o ramo inline
        quebraria essas.

        PRECISÃO MEDIDA: 21% -> 100% (2.481 leituras, 5 baterias).
        Detalhe em `Teste-Ponteiros/RESULTADOS.md`, seções 11.3 e 13.6.

        POR QUE ISSO NÃO ERA COSMÉTICO: `combat.py` tem
        `USAR_PORTAO_DE_NOME = True`, e o nome alimenta `_veredito_do_alvo`
        (o portão que existe para evitar "atacando mob que não é o esperado")
        e `_e_o_alvo_proibido`. Nome errado em 79% das leituras estava
        decidindo combate.
        """
        ponteiro = self.read_uint(obj + OFF_NAME)
        if ponteiro is not None and 0x10000 <= ponteiro < 0x8000_0000:
            pelo_ponteiro = self.read_string_direct(ponteiro, length=32)
            if pelo_ponteiro and self._parece_nome(pelo_ponteiro):
                return pelo_ponteiro
        direto = self.read_string_direct(obj + OFF_NAME, length=32)
        if direto and self._parece_nome(direto):
            return direto
        return None

    def dialog_open(self) -> bool | None:
        """A caixa de diálogo de NPC está aberta? None = não deu para ler.

        É a mesma pergunta que `ui_service.dialogo_esta_aberto()` responde por
        template -- e por memória ela não depende de captura de tela, então
        responde também com o cliente minimizado.

        VIVO desde 02/09/2026, e o que faltava era o rebase `+0x60` da raiz --
        ver o comentário de `ADDR_DIALOG_ROOT`. A cadeia resolve nos seis
        clientes, e os dois únicos valores vistos são 16774 (fechado) e 16775
        (aberto), o mesmo padrão N/N+1 da bolsa.

        QUEM DECIDE AINDA É O TEMPLATE. Foi observado UM evento de abertura
        (numa conta em farm, concordando com a bandeira independente no mesmo
        instante) -- o suficiente para o leitor deixar de mentir "não sei", não o
        suficiente para o bot passar a decidir por ele. Enquanto o contador de
        eventos não crescer, este valor entra no diagnóstico ao lado do template.

        Qualquer valor fora de {16774, 16775} devolve `None`: um valor nunca
        visto não vira `False` calado.
        """
        addr = self.resolve(ADDR_DIALOG_ROOT, CHAIN_DIALOG)
        if addr is None:
            return None
        valor = self.read_int(addr)
        if valor == DIALOGO_ABERTO_VALOR:
            return True
        if valor == DIALOGO_FECHADO_VALOR:
            return False
        return None

    def algum_painel_aberto(self) -> bool:
        """Tem alguma janela do jogo aberta por cima? SINAL DE UMA VIA.

        `True` = tem, com certeza. `False` = nenhum dos sinais acusou, o que NÃO
        prova tela limpa.

        POR QUE O BC PRECISA: com uma janela aberta dentro do jogo, o clique vai
        para ela em vez de ir para o mundo, e isso chega a impedir o diálogo de
        NPC de abrir. Hoje o bot não olha, e a varredura de 02/09/2026 pegou
        contas FARMANDO com bolsa e quest log abertos.

        A união é de sinais POSITIVOS medidos, cada um validado à parte:

          * a bandeira de painel -- sobe para 8 teclas de painel diferentes
            (C, T, M, I, K, L, G, F) e para o menu do ESC;
          * o discriminador do quest log;
          * a cadeia da bolsa (902 fechada / 903 aberta);
          * a cadeia do diálogo de NPC (16774 / 16775).

        Cada um sozinho já foi visto perder um caso, e é por isso que isto é uma
        UNIÃO e não um leitor só: o zero da bandeira foi refutado em campo (bolsa
        aberta com a bandeira em zero, 7 vezes), então quem cobre esse caso é a
        cadeia da bolsa.

        ================== A ARMADILHA DO ESC, MEDIDA ==================

        O ESC ALTERNA. Com painel aberto ele fecha; com a tela LIMPA ele ABRE o
        menu do sistema -- medido seis vezes seguidas, sempre o mesmo nó
        (`0` <-> `0x15142AB0`), e o `system_menu_open()` NÃO vê esse menu (diz
        `False` nas duas metades).

        Então quem for fechar painel PERGUNTA depois de cada tecla e para no
        instante em que este método devolver `False`. Uma quantidade fixa de ESC
        deixa o jogo pior do que achou.
        """
        if self.dialogo_de_ui_a_frente():
            return True
        if self.quest_aberto():
            return True
        if self.bag_open():
            return True
        return self.dialog_open() is True

    def bag_open(self) -> bool:
        addr = self.resolve(ADDR_UI_ROOT, CHAIN_BAG_OPEN)
        return self.read_int(addr) == BAG_OPEN_VALUE if addr else False

    def bag_count(self) -> int | None:
        """Total de itens nas bolsas, somando as três se existirem.

        A terceira bolsa só conta se estiver ativa; quando a Expand Bag está
        "Expired" a leitura tende a falhar ou vir zerada, e nesse caso ela é
        simplesmente ignorada.
        """
        total = 0
        encontrou = False
        for cadeia in (CHAIN_BAG_1, CHAIN_BAG_2, CHAIN_BAG_3):
            addr = self.resolve(PLAYER_BASE, cadeia)
            if addr is None:
                continue
            valor = self.read_int(addr)
            if valor is None or valor < 0 or valor > 200:
                continue
            total += valor
            encontrou = True
        return total if encontrou else None

    # -- escolha de endereço entre versões do cliente -----------------------
    #
    # Os três blocos abaixo (`team_size`, `modal_open`, `surroundings_first`)
    # são os que o projeto documenta como QUEBRADOS neste cliente, e os três
    # nascem de endereço herdado do GhostBot, que é da versão 6139. Cada um
    # passa pelo `SeletorDeEndereco`: mede o atual e o candidato +0x60 uma vez,
    # e só troca quando o candidato responde E o atual não. Ver `core/rebase.py`.

    def enderecos_decididos(self) -> dict[str, object]:
        """O que o seletor já decidiu -- para o log e para o diagnóstico."""
        return self._seletor.decisoes()

    def _valor_team_size(self, base: int) -> int | None:
        """Tamanho do time a partir de UM endereço base -- sem escolher nada."""
        addr = self.resolve(base, [OFF_TEAM_SIZE])
        return self.read_int(addr) if addr else None

    @staticmethod
    def _team_size_plausivel(valor: object) -> bool:
        """Time no Talisman vai de 0 a 5 (o personagem mais quatro).

        O peso do teste não está na faixa -- 0 cabe nela e é fácil de ler por
        acidente. Está em `resolve`: com o endereço errado a cadeia morre no
        primeiro elo e o valor vem `None`, que já reprova antes daqui.
        """
        return isinstance(valor, int) and 0 <= valor <= 5

    def tamanho_do_time(self) -> int | None:
        """Quantos estão no time, CONTANDO o próprio personagem. `0` = sem time.

        Leitura NOVA (31/08/2026), pelo ponteiro rebaseado -- ver `ADDR_TEAM`.
        A antiga (`team_size`) fica onde está porque o BC depende do
        comportamento dela; esta não mexe em nada do que já roda.
        """
        base = self.read_int(ADDR_TEAM)
        if not base:
            return None
        valor = self.read_int(base + OFF_TAMANHO_DO_TIME)
        if valor is None or not (0 <= valor <= 8):
            return None
        return valor

    def time_do_jogo(self) -> list[str] | None:
        """Os nomes do time, NA ORDEM DO JOGO. `[]` = não está em time.

        É a peça que a Fada precisa: ela diz qual retrato do painel é de quem,
        sem OCR, sem template e sem clicar para descobrir.

        A ORDEM É A MESMA EM TODOS OS CLIENTES -- medido lendo seis clientes ao
        mesmo tempo. E o PRÓPRIO personagem está na lista, enquanto o painel da
        tela o mostra separado, no retrato grande de cima. Então os retratos dos
        companheiros são esta lista MENOS ele, na mesma ordem.

        Devolve `None` quando não deu para ler -- que é diferente de `[]`, e a
        diferença importa: `None` é "não sei", e quem não sabe não age.
        """
        base = self.read_int(ADDR_TEAM)
        if not base:
            return None
        tamanho = self.read_int(base + OFF_TAMANHO_DO_TIME)
        if tamanho is None or not (0 <= tamanho <= 8):
            return None
        if tamanho == 0:
            return []
        nomes: list[str] = []
        for i in range(min(tamanho, MAXIMO_DE_MEMBROS_LIDOS)):
            endereco = base + OFF_PRIMEIRO_MEMBRO + i * PASSO_ENTRE_MEMBROS
            nome = (self.read_string_direct(endereco) or "").strip()
            # NOME VAZIO ENCERRA A LISTA. Passado o tamanho real a tabela traz
            # lixo (medido: o 4º nome com `teamSize=3` veio ilegível), e um
            # nome inventado aqui viraria um retrato clicado à toa.
            if not nome or not re.match(r"^[\w'\- ]+$", nome):
                break
            nomes.append(nome)
        return nomes

    def vida_do_time(self) -> list[dict] | None:
        """Nome e vida de cada membro, na ordem do jogo. **Ver o aviso abaixo.**

        O `hp` daqui parece ser o MÁXIMO, e não a vida atual -- ver
        `OFF_MEMBRO_HP`. Enquanto isso não for remedido, trate-o como reserva:
        a fonte boa da vida de um companheiro é o que ele publica no mural.

        É o que deixa a Fada ver a cura fazer efeito em vez de esperar a vítima
        avisar. A vida MÁXIMA não vive neste bloco (procurada, não achada), e
        por isso não vem aqui: quem sabe o próprio máximo é cada conta, que o
        publica no mural.

        `None` = não deu para ler. `[]` = fora de time.
        """
        base = self.read_int(ADDR_TEAM)
        if not base:
            return None
        tamanho = self.read_int(base + OFF_TAMANHO_DO_TIME)
        if tamanho is None or not (0 <= tamanho <= 8):
            return None
        if tamanho == 0:
            return []
        membros: list[dict] = []
        for i in range(min(tamanho, MAXIMO_DE_MEMBROS_LIDOS)):
            inicio = base + OFF_PRIMEIRO_MEMBRO + i * PASSO_ENTRE_MEMBROS
            nome = (self.read_string_direct(inicio) or "").strip()
            if not nome or not re.match(r"^[\w'\- ]+$", nome):
                break
            hp = self.read_int(inicio + OFF_MEMBRO_HP)
            # HP fora de faixa é struct inconsistente, e "não sei" é melhor que
            # um número inventado -- a Fada decide curar em cima disto.
            if hp is not None and not (0 <= hp <= 10_000_000):
                hp = None
            membros.append({"nome": nome, "hp": hp})
        return membros

    def companheiros_de_time(self, meu_nome: str | None = None) -> list[str] | None:
        """O time MENOS eu, na ordem -- é a ordem dos retratos na tela.

        O painel desenha o próprio personagem no retrato grande de cima e os
        companheiros abaixo dele; a lista da memória inclui todo mundo. Tirar-se
        da lista é o que faz o índice bater com o slot clicável.
        """
        nomes = self.time_do_jogo()
        if nomes is None:
            return None
        eu = (meu_nome or self.char_name() or "").strip().lower()
        return [n for n in nomes if n.strip().lower() != eu]

    def team_size(self) -> int | None:
        """Quantidade de membros no time.

        ESTA LEITURA NUNCA RESPONDEU neste cliente, e o preço está medido em
        `bot/team.py`: a confirmação do convite dependia dela, e o log real
        registrou ONZE aceites falsos seguidos para um único convite. O
        `_time_pela_imagem()` foi escrito como segunda via por causa disso --
        e essa segunda via também está morta, porque o template
        `state_team_member.png` que ela carrega não existe em disco.

        RESOLVIDO EM 31/08/2026, e era o +0x60 mesmo: use
        `tamanho_do_time()` e `time_do_jogo()`, que leem pelo `ADDR_TEAM`
        rebaseado e foram provados ao vivo em seis clientes. Esta função fica
        de pé só porque o BC depende do comportamento dela (ela devolve
        `None`, e o BC trata `None` como "não sei"); trocá-la mudaria o farm
        sem ninguém ter pedido.
        """
        base = self._seletor.escolher(
            "team_size", ADDR_TEAM_SIZE,
            self._valor_team_size, self._team_size_plausivel,
        )
        return self._valor_team_size(base)

    def buff_count(self) -> int | None:
        """Quantidade de buffs ativos."""
        addr = self.resolve(IMAGE_BASE + ADDR_BUFF_COUNT_RVA, [OFF_BUFF_COUNT])
        return self.read_int(addr) if addr else None

    def surroundings_first(self) -> dict[str, object] | None:
        """Primeiro resultado do painel Surroundings: nome e coordenadas.

        Serve para CONFERIR a busca antes de clicar. Sem isso o bot digita um
        fragmento de texto e clica no primeiro item às cegas -- se a busca
        trouxer outro lugar com nome parecido, ele viaja para o lugar errado sem
        perceber.

        DUAS INTERPRETAÇÕES DO MESMO ENDEREÇO, e é por isso que existem as duas.
        A auditoria do GhostBot mostrou que ele lê este campo DEREFERENCIANDO o
        ponteiro (`*(ptr) + 0x64`), enquanto aqui a leitura era DIRETA
        (`ptr + 0x64`). São coisas diferentes, e nenhuma das duas foi confirmada
        neste cliente -- a leitura direta nunca apareceu funcionando em log
        nenhum.

        Em vez de escolher no palpite, tenta as duas e fica com a que produzir um
        texto no formato esperado. É o mesmo tratamento que o nome do lugar já
        recebe, e pelo mesmo motivo: quando não se sabe qual interpretação vale,
        testar é mais barato do que apostar.

        ENDEREÇO TAMBÉM É HIPÓTESE, e é a mais provável das duas. A raiz
        `0x012CE2DC` é da versão 6139 do cliente, herdada do GhostBot, e o
        `ADDR_UI_ROOT` do mesmo banco já precisou andar +0x60 para a 6400.
        `0x012CE2DC + 0x60 = 0x012CE33C`, que é `ADDR_UI_ROOT - 4` -- nas duas
        versões este campo fica um DWORD abaixo da raiz de UI. O seletor mede as
        duas raízes e fica com a que produzir texto no formato certo.

        NADA É DECIDIDO COM O PAINEL FECHADO: sem painel não há texto, e as duas
        raízes falham igual. Esse caso é INCONCLUSIVO por desenho, não é
        guardado, e a pergunta se repete na próxima vez -- que é quando o painel
        pode estar aberto.
        """
        base = self._seletor.escolher(
            "surroundings", ADDR_SURROUNDINGS,
            self._valor_arredores, lambda v: isinstance(v, dict),
        )
        return self._valor_arredores(base)

    def _valor_arredores(self, base: int) -> dict[str, object] | None:
        """Arredores a partir de UMA raiz -- sem escolher nada."""
        ptr = self.resolve(base, CHAIN_SURROUNDINGS)
        if ptr is None:
            return None

        leituras = (
            ("direta", self.read_string_direct(ptr + OFF_SURROUNDINGS_TEXT,
                                               length=120)),
            ("por ponteiro", self.read_string(ptr, offset=OFF_SURROUNDINGS_TEXT,
                                              length=120)),
        )
        for origem, texto in leituras:
            if not texto:
                continue
            achado = re.search(r'text="([^"]+?)\s*\[(-?\d+),\s*(-?\d+)\]"', texto)
            if achado:
                return {
                    "nome": achado.group(1).strip(),
                    "coords": (int(achado.group(2)), int(achado.group(3))),
                    "origem": origem,
                }
        return None

    def candidato_de_endereco_booleano(self, endereco: int) -> bool | None:
        """Lê UM candidato de endereço e devolve seu valor booleano, sem escolher nada.

        ESTE MÉTODO É O PRIMITIVO DA CALIBRAÇÃO, e vive do lado de fora do
        `SeletorDeEndereco`. Enquanto `modal_open()` e `loot_window_open()` esperam o
        seletor decidir um único endereço e depois leem `== 1`, este método é chamado
        com CADA candidato (o endereço herdado do GhostBot e o +0x60 da 6400) para que
        `calibracao.julgar_booleano` os pontue um por um contra a prova de tela.

        O que distingue este método de `modal_open()`:

          * NÃO usa `_seletor.escolher` -- o seletor decide uma vez e vive com a
            escolha; a calibração precisa testar os dois independentemente, e só
            promove quando o candidato responde E o atual não (ver `core/rebase.py`).
          * Devolve `None` em vez de `False` quando a leitura falha. Isso é carregado:
            `None` faz com que `julgar_booleano` saia `acertou=None`, que a rotina de
            registro conta como SILENCIO (não como erro) -- e acumula em
            `sem_leitura`. Trinta tentativas sem leitura encerram o candidato como
            `sem_resposta`, e é o fim correto para um offset que não existe nesta
            struct. Um `False` mentiroso seria contado como amostra errada e
            atrasaria o encerramento.
          * Usa `bool(valor)` em vez de `valor == 1`. A calibração compara
            `bool(lido) == bool(na_tela)`, e a flag do cliente é "0 = ausente,
            1 = presente" -- qualquer valor não-zero é True. `== 1` é mais rígido e
            pode rejeitar um candidato que leu, por exemplo, 2 por algum bit de
            padding que ainda carrega sinal -- o que confundiria "offset errado" com
            "leitura sujeira" no placar.
        """
        valor = self.read_int(endereco)
        return None if valor is None else bool(valor)

    def modal_open(self) -> bool:
        """Flag genérico de modal na tela.

        O MESMO endereço serve para três coisas no cliente: caixa de
        confirmação, erro de login e desconexão. A interpretação é sempre
        contextual -- por isso o watchdog exige persistência antes de
        concluir que é um DC.
        """
        base = self._seletor.escolher(
            "modal", ADDR_MODAL, self.read_int, self._modal_plausivel,
        )
        return self.read_int(base) == 1

    @staticmethod
    def _modal_plausivel(valor: object) -> bool:
        """O campo é uma FLAG: 0 ou 1, nunca um ponteiro.

        Este é o discriminador mais forte dos três, e vem do próprio
        `CLAUDE.md`: *"ADDR_MODAL está errado (guarda ponteiro, modal_open() é
        sempre False)"*. Endereço de heap não cabe em 0..1 por acidente -- lido
        como inteiro com sinal ele sai gigante ou negativo, e reprova.
        """
        return isinstance(valor, int) and 0 <= valor <= 1

    # -- estado de painel de UI, por memória -----------------------------

    def quest_aberto(self) -> bool | None:
        """O painel de Quest está aberto? `None` = não deu para ler.

        O único discriminador de painel que passou no teste completo: vale `1`
        só com o Quest aberto, `0` com os outros cinco painéis abertos, em 3 de
        3 rodadas -- e `0` em 5 de 5 contas que não tinham o Quest, lidas no
        mesmo instante.
        """
        if not USAR_PAINEL_POR_MEMORIA:
            return None
        v = self.read_int(ADDR_QUEST_ABERTO)
        if v is None:
            return None
        return v == 1

    def dialogo_de_ui_a_frente(self) -> bool | None:
        """Há um diálogo de UI na frente? **SINAL DE UMA VIA.**

        `True` é confiável: quando a bandeira vale um ponteiro, há diálogo.

        `False` **NÃO PROVA** que não há nada aberto -- foi medido o contrário:
        a bolsa estava aberta (cadeia em 903) com a bandeira em ZERO, 7 vezes.
        Ver a tabela junto de `ADDR_PAINEL_ABERTO`.

        Então: use o `True` para decidir; NÃO use o `False` para concluir que a
        tela está livre. Para isso, quem responde é a cadeia da bolsa
        (`bag_open`) e o template, como antes.

        `None` = não deu para ler, que é diferente de `False`.
        """
        if not USAR_PAINEL_POR_MEMORIA:
            return None
        v = self.read_uint(ADDR_PAINEL_ABERTO)
        if v is None:
            return None
        return bool(v)

    def loot_window_open(self) -> bool:
        return self.read_int(ADDR_LOOT_WINDOW) == 1

    def system_menu_open(self) -> bool:
        return self.read_int(ADDR_SYSTEM_MENU) == SYSTEM_MENU_VALUE

    def queue_text(self) -> str | None:
        try:
            raw = self.pm.read_bytes(ADDR_QUEUE, 50)
            return raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")
        except Exception:
            return None

    # -- câmera ------------------------------------------------------------

    def set_camera(self, zoom: float, rotation: float, angle: float) -> None:
        """Fixa a câmera.

        Essencial: sem câmera fixa, qualquer clique posicional na cena 3D
        vira loteria. O T-R0XX usa (380, 0, 40) na BC.

        ESCREVE EM `ADDR_CAMERA_VIVA`, não em `ADDR_CAMERA` -- este último
        resolve NULO na 6400 (medido em 25/08/2026), e era para lá que TODA
        escrita de câmera ia desde o transplante do GhostBot. Ele sobrevive
        como referência do diagnóstico, e só.
        """
        base = ADDR_CAMERA_VIVA
        for offset, value in ((0x64, zoom), (0x5C, rotation), (0x60, angle)):
            addr = self.resolve(base, [offset])
            if addr is not None:
                self.write_float(addr, value)

    def camera_angulo(self) -> float | None:
        """O ângulo atual da câmera, ou `None` se não deu para ler.

        É o TERMÔMETRO: só lê. Ver `ADDR_ANGULO_DA_CAMERA` para a medição que
        prova que escrever nele não faz nada.
        """
        return self.read_float(ADDR_ANGULO_DA_CAMERA)

    def camera_pose(self) -> tuple[float, float, float] | None:
        """`(zoom, rotacao, angulo)` lidos da struct, ou `None`.

        São os campos de ENTRADA da câmera -- ficam onde são postos (medido),
        ao contrário do termômetro, que o jogo recalcula todo quadro.
        """
        valores = []
        for offset in (0x64, 0x5C, 0x60):
            endereco = self.resolve(ADDR_CAMERA_VIVA, [offset])
            if endereco is None:
                return None
            valor = self.read_float(endereco)
            if valor is None:
                return None
            valores.append(valor)
        return (valores[0], valores[1], valores[2])

    def camera_na_pose_certa(
            self, alvo: tuple[float, float, float] | None = None) -> bool | None:
        """A câmera está na pose pedida? `None` = NÃO SEI.

        `alvo` é a pose que se QUER, na ordem `(zoom, rotacao, angulo)`; sem
        ela, `POSE_DA_CAMERA`.

        CONFERE CONTRA O QUE FOI ESCRITO, não contra a constante. Quem
        sobrescreve a pose na config espera que a verificação siga a
        sobrescrita -- conferir contra outra coisa faria o bot brigar consigo
        mesmo, insistindo três vezes e avisando que não conseguiu.

        `None` é diferente de `False`: quem consome não pode tratar "não sei"
        como "está errada", porque corrigir às cegas mexe na câmera de quem
        estava certo. É a mesma regra da régua da barra de vida, que também
        sabe dizer "não sei".
        """
        atual = self.camera_pose()
        if atual is None:
            return None
        return all(abs(a - b) <= TOLERANCIA_DA_POSE
                   for a, b in zip(atual, alvo or POSE_DA_CAMERA, strict=True))

    def _esperar_o_termometro(self, antes: float | None) -> tuple[float | None, float]:
        """Pergunta ao termômetro até ele mexer, ou até o teto.

        Devolve `(valor, segundos)`. Sai no INSTANTE em que muda -- o teto é
        aviso, não gasto.
        """
        comeco = time.monotonic()
        atual = self.camera_angulo()
        while time.monotonic() - comeco < TETO_DA_PROVA_DA_CAMERA:
            atual = self.camera_angulo()
            if (antes is not None and atual is not None
                    and abs(atual - antes) > TOLERANCIA_DO_ANGULO):
                break
            time.sleep(PASSO_DA_PROVA_DA_CAMERA)
        return atual, time.monotonic() - comeco

    def _provar_campo_da_camera(self, nome: str, endereco: int,
                                original: float) -> dict[str, object]:
        """Escreve num campo, espera o jogo desenhar, e conta o que aconteceu.

        Três perguntas, não uma:

        1. **A escrita ficou na hora?** Se não, a memória é protegida ou o
           endereço não é o que se pensa.
        2. **O JOGO DESFEZ depois de alguns quadros?** Essa é a assinatura de
           campo DERIVADO -- é o que o usuário viu no Cheat Engine com o próprio
           termômetro. Campo de ENTRADA fica onde foi posto.
        3. **O termômetro mexeu junto?** Só isso prova que o campo é a CÂMERA, e
           não uma struct qualquer que aceita float.

        ESCREVE E DESFAZ: `finally` restaura o valor original.
        """
        prova: dict[str, object] = {
            "campo": nome, "endereco": endereco, "original": original,
            "escrito": original + PROVA_DA_CAMERA,
        }
        antes = self.camera_angulo()
        prova["termometro_antes"] = antes
        try:
            self.write_float(endereco, original + PROVA_DA_CAMERA)
            na_hora = self.read_float(endereco)
            prova["releu_na_hora"] = na_hora
            prova["a_escrita_ficou"] = (
                na_hora is not None
                and abs(na_hora - (original + PROVA_DA_CAMERA)) < 0.5)

            depois, segundos = self._esperar_o_termometro(antes)
            prova["termometro_depois"] = depois
            prova["segundos"] = segundos
            prova["moveu_o_termometro"] = (
                antes is not None and depois is not None
                and abs(depois - antes) > TOLERANCIA_DO_ANGULO)

            # Depois de o jogo ter desenhado: o valor CONTINUA lá?
            releu = self.read_float(endereco)
            prova["releu_depois"] = releu
            prova["o_jogo_manteve"] = (
                releu is not None
                and abs(releu - (original + PROVA_DA_CAMERA)) < 0.5)
        except Exception as exc:
            prova["situacao"] = f"a escrita levantou: {exc!r}"
            return prova
        finally:
            try:
                self.write_float(endereco, original)
            except Exception:
                pass

        if prova.get("moveu_o_termometro"):
            prova["situacao"] = "ESCREVE E MOVE A CÂMERA"
        elif not prova.get("a_escrita_ficou"):
            prova["situacao"] = "a escrita nem chegou a ficar"
        elif not prova.get("o_jogo_manteve"):
            prova["situacao"] = ("o jogo DESFEZ depois de alguns quadros -- "
                                 "campo derivado, como o termômetro")
        else:
            prova["situacao"] = ("o valor FICOU, mas o termômetro não mexeu -- "
                                 "ou não é a câmera, ou o termômetro não mede "
                                 "este eixo")
        return prova

    def diagnostico_da_camera(self) -> dict[str, object]:
        """A struct da câmera responde? E ESCREVER NELA move o termômetro?

        =================================================================
        A PERGUNTA QUE NUNCA FOI FEITA
        =================================================================

        `set_camera` escreve zoom/rotação/ângulo em `resolve(ADDR_CAMERA, ...)` e
        roda depois de todo View Reset. Só que:

          * `ADDR_CAMERA = 0x0116FFF4` é herança do T-R0XX/GhostBot, da versão
            **6139**;
          * os estáticos daquele banco precisaram de **+0x60** para a 6400 -- e
            isso agora é MEDIDO, não suposto: o `TARGET_ID` do GhostBot é
            `0x0115CB20` e o que responde na 6400 é `0x0115CB80`, exatamente
            `+0x60`;
          * a câmera **não está** na lista do `core/rebase.py`;
          * e a câmera **nunca apareceu no diagnóstico**.

        Ou seja: `set_camera` pode estar escrevendo em lugar nenhum desde
        sempre, e ninguém teria como saber.

        =================================================================
        A PROVA É O TERMÔMETRO SE MEXER -- DEPOIS DE UM QUADRO
        =================================================================

        Resolver o ponteiro e ler três floats prova só que há memória legível
        ali. O que prova que é A CÂMERA é escrever e ver
        `ADDR_ANGULO_DA_CAMERA` mudar junto -- **depois de o jogo desenhar**.
        Ver `TETO_DA_PROVA_DA_CAMERA`.

        Os TRÊS campos são provados um a um. Testar só o ângulo respondia por um
        eixo e calava sobre os outros dois.

        SÓ LÊ E RESTAURA -- nenhuma decisão do bot depende desta função.
        """
        relatorio: dict[str, object] = {
            "termometro_endereco": ADDR_ANGULO_DA_CAMERA,
            "termometro": self.camera_angulo(),
            "esperado": ANGULO_DA_CAMERA,
            "candidatos": [],
        }

        # OS DOIS CANDIDATOS: o endereço herdado e o mesmo com o +0x60 que a
        # virada 6139 -> 6400 exigiu dos outros estáticos deste banco.
        for rotulo, base in (("ADDR_CAMERA", ADDR_CAMERA),
                             ("ADDR_CAMERA+0x60", ADDR_CAMERA + 0x60)):
            candidato: dict[str, object] = {"rotulo": rotulo, "base": base,
                                            "provas": []}
            relatorio["candidatos"].append(candidato)

            ponteiro = self.read_uint(base)
            candidato["ponteiro"] = ponteiro
            if ponteiro is None or ponteiro < 0x10000:
                candidato["situacao"] = "ponteiro nulo ou fora da faixa"
                continue

            campos = {}
            for nome, offset in (("rotacao", 0x5C), ("angulo", 0x60),
                                 ("zoom", 0x64)):
                addr = self.resolve(base, [offset])
                campos[nome] = {
                    "endereco": addr,
                    "valor": self.read_float(addr) if addr is not None else None,
                }
            candidato["campos"] = campos

            for nome, campo in campos.items():
                endereco, original = campo["endereco"], campo["valor"]
                if endereco is None or original is None:
                    candidato["provas"].append(
                        {"campo": nome, "situacao": "não consegui ler o campo"})
                    continue
                candidato["provas"].append(
                    self._provar_campo_da_camera(nome, endereco, original))

            moveram = [p["campo"] for p in candidato["provas"]
                       if p.get("moveu_o_termometro")]
            ficaram = [p["campo"] for p in candidato["provas"]
                       if p.get("o_jogo_manteve")]
            if moveram:
                candidato["situacao"] = ("ESCREVE E MOVE A CÂMERA pelo(s) campo(s) "
                                         + ", ".join(moveram))
            elif ficaram:
                candidato["situacao"] = (
                    "o jogo MANTEVE o(s) campo(s) " + ", ".join(ficaram)
                    + " (campo de ENTRADA, não derivado), mas o termômetro não "
                      "mexeu -- olhe a TELA para desempatar")
            else:
                candidato["situacao"] = ("o jogo desfez tudo -- struct derivada, "
                                         "não é entrada de câmera")

        return relatorio

    # -- diagnóstico -------------------------------------------------------

    def probe(self) -> dict[str, tuple[object, bool]]:
        """Lê todos os campos e diz quais REALMENTE funcionaram.

        Importa distinguir "a leitura falhou" de "o valor é False". Getters como
        `is_sitting()` devolvem False nos dois casos, e o diagnóstico anterior
        contava esses False como sucesso -- então um cliente com a memória
        totalmente ilegível aparecia como parcialmente saudável.

        O campo "em combate" NÃO decide nada no bot (ver o bloco em cima de
        `in_battle`): ele é observado, não obedecido. Aqui serve para duas coisas --
        conferir que a estrutura do personagem está legível, e ser lido JUNTO dos
        campos do alvo, que é o que permite dizer se o quadro do alvo está parado.
        """
        def ler_bool(offset: int, esperado: int) -> tuple[object, bool]:
            addr = self._player_field(offset)
            if addr is None:
                return None, False
            valor = self.read_byte(addr)
            if valor is None:
                return None, False
            return valor == esperado, True

        base = self.read_int(PLAYER_BASE)
        obj_ok = base is not None and base > 0x10000

        campos: dict[str, tuple[object, bool]] = {
            "ponteiro base": (hex(base) if base else None, obj_ok),
            "nome do personagem": (self.char_name(), self.char_name() is not None),
            "nível": (self.level(), self.level() is not None),
            "HP": (self.hp(), self.hp() is not None),
            "HP máximo": (self.max_hp(), self.max_hp() is not None),
            "MP": (self.mp(), self.mp() is not None),
            "MP máximo": (self.max_mp(), self.max_mp() is not None),
            "posição (X, Y)": (self.position(), self.position() is not None),
            "ouro": (self.gold(), self.gold() is not None),
            "localização": (self.location(), self.location() is not None),
            "itens nas bolsas": (self.bag_count(), self.bag_count() is not None),
        }
        campos["em combate"] = ler_bool(OFF_BATTLE, 1)
        campos["montado"] = (
            (bool(self.read_int(self._player_field(OFF_MOUNT) or 0)), True)
            if self._player_field(OFF_MOUNT) is not None else (None, False)
        )
        campos["sentado"] = ler_bool(OFF_SIT, SIT_VALUE)
        campos["pet ativo"] = ler_bool(OFF_PET_ACTIVE, 1)

        # CAMPOS DO ALVO REMOVIDOS: o sistema híbrido (TargetHybrid) agora cuida
        # do alvo (ID da memória 0x0115CB80 + HP% da tela via vision.vida_do_alvo()).
        # Este debug_dump foca no Player. Para info do alvo, use TargetHybrid.ler_alvo().
        campos["modal aberto"] = (
            (self.read_int(ADDR_MODAL) == 1, True)
            if self.read_int(ADDR_MODAL) is not None else (None, False)
        )

        # Painel de UI por memória. Entra no diagnóstico AO LADO do
        # `modal aberto` de propósito: é lado a lado que se vê o `modal aberto`
        # respondendo False em quase tudo enquanto a bandeira responde.
        quest = self.quest_aberto()
        campos["quest aberto"] = (quest, quest is not None)
        dialogo = self.dialogo_de_ui_a_frente()
        campos["dialogo de UI a frente"] = (dialogo, dialogo is not None)
        # Os valores CRUS, porque a bandeira é sinal de uma via: quem for
        # investigar precisa dos números, não do booleano.
        bandeira = self.read_uint(ADDR_PAINEL_ABERTO)
        campos["bandeira (cru)"] = (bandeira, bandeira is not None)
        segunda = self.read_uint(ADDR_PAINEL_SEGUNDA_FENDA)
        campos["2a fenda (cru)"] = (segunda, segunda is not None)
        # Capacidades medidas que ainda nao decidem nada -- entram no
        # diagnostico para poderem ser conferidas em campo antes de decidir.
        atrasado = self.bloco_atrasado()
        if atrasado is not None:
            mudando = [k for k, (a, b) in atrasado.items() if a != b]
            campos["bloco +0x3A0 (atraso ~200 ms)"] = (
                ("assentado" if not mudando
                 else "mudando: %s" % ",".join(mudando)),
                True,          # mudar e normal, nao e defeito
            )
            campos["hp caiu nos ultimos ~200 ms"] = (self.hp_caiu_agora(), True)
        xp1, xp2 = self.experiencia()
        campos["xp (0x3C8, 0x3CC)"] = ((xp1, xp2),
                                       xp1 is not None and xp2 is not None)
        relogio = self.relogio_ms()
        campos["relogio ms (0x85C)"] = (relogio, relogio is not None)

        campos["F12 preso (esconde jogadores)"] = (
            self.esconder_jogadores_ativo(), True)

        campos["algum painel aberto (uma via)"] = (
            self.algum_painel_aberto(), True)

        endereco_bolsa = self.resolve(ADDR_UI_ROOT, CHAIN_BAG_OPEN)
        valor_bolsa = (self.read_int(endereco_bolsa)
                       if endereco_bolsa is not None else None)
        campos["bolsa (cru: 902 fechada, 903 aberta)"] = (
            valor_bolsa, valor_bolsa is not None)

        return campos

    def critical_ok(self) -> bool:
        """Os campos sem os quais o bot de cave não consegue operar."""
        return (self.hp() is not None
                and self.position() is not None
                and self.max_hp() is not None)

    def close(self) -> None:
        try:
            self.pm.close_process()
        except Exception:
            pass
