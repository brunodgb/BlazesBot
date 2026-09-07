"""
Executor de macro: manda tecla, espera, próxima linha, e recomeça no fim.

=========================================================================
O QUE É
=========================================================================

É o comportamento central do UoPilot, e nada além disso. Uma lista de linhas,
cada uma com uma tecla e um tempo de espera:

    1   TAB   800 ms
    2   1     800 ms
    3   1     800 ms
    4   5     500 ms
    (volta para a linha 1)

O laço percorre de cima para baixo, manda a tecla para a janela do jogo, espera
exatamente o tempo daquela linha, e passa para a seguinte. Chegando na última,
recomeça da primeira. Roda assim até o usuário interromper.

=========================================================================
CEGO DE PROPÓSITO, COM UMA EXCEÇÃO: O PET
=========================================================================

Ele não sabe se há alvo, se o personagem está vivo, onde ele está nem se a tecla
produziu algo. Não é limitação a corrigir: é o que um executor de macro é. É
também o que faz este módulo funcionar em situação onde o bot BC não funciona --
sem leitura de memória, por exemplo.

A ÚNICA COISA QUE ELE OLHA é se o pet está ativo, antes de cada volta. Pet sem
invocar simplesmente não luta, e uma macro de ataque rodando sem pet é tempo
gasto pela metade sem nada avisar.

E ISSO NÃO QUEBRA O ISOLAMENTO, o que exigiu cuidado no desenho: este arquivo
continua sem importar `blazesbot.bot` e sem importar `core.memory`. A leitura do
pet chega como FUNÇÃO, injetada por quem constrói o executor -- do mesmo jeito
que `continuar` e `pausado` já chegavam. O executor não sabe de onde vem a
resposta; ele sabe pedir e sabe o que fazer com cada uma das três.

As três respostas importam:

    True  -- pet ativo, nada a fazer
    False -- pet caído, aperta a tecla configurada
    None  -- NÃO DEU PARA LER. Não aperta nada.

O `None` é o que preserva o motivo de existir deste módulo: sem leitura de
memória o modo APP continua funcionando exatamente como antes, mandando tecla e
esperando. Tratar `None` como `False` faria a macro apertar a tecla do pet em
toda volta num cliente que não lê memória -- que é justamente o cliente para o
qual este módulo foi feito.

Se algum dia alguém quiser "melhorar" isto lendo HP ou alvo, o lugar disso é o
bot BC, que já faz. Misturar os dois foi o que existia antes e o que a separação
desfez.

=========================================================================
O TEMPO É EXATO, E ISSO É UMA EXCEÇÃO NESTE PROJETO
=========================================================================

Todo atraso do bot BC leva jitter, porque padrão perfeitamente regular é
assinatura fácil de reconhecer. Aqui NÃO: o pedido é o tempo exato de cada linha,
como no UoPilot, e é isso que está implementado. Quem quiser variação coloca
linhas com tempos diferentes.

A espera é fatiada só para o botão de parar responder na hora -- uma linha de
3000 ms não pode fazer o usuário esperar 3 segundos depois de mandar parar. O
tempo total esperado continua sendo o configurado.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Protocol

# DUAS PECAS COMPARTILHADAS COM O BC vem de `core/target_hybrid.py`, e as duas
# sao a MESMA pergunta nos dois ecossistemas, com a MESMA struct:
#
#   `MorteDoAlvo` ............... "o mob morreu?" -- mesmo cadaver de 7 a 13 s;
#   `esperar_o_alvo_trocar` ..... "o TAB pegou?" -- promovida DAQUI em 06/09/2026
#                                 (o CLAUDE.md ja a listava como duplicata).
#
# O que e de cada um e o que FAZER com a resposta: aqui o teto e o `_continuar`
# sao do APP, e o "nao trocou" vira nova tentativa.
#
# Importar do `core/` NAO quebra o isolamento deste modulo: o que ele nao pode e
# importar `blazesbot.bot` (travado por `test_o_executor_do_app_so_usa_o_core`).
from ...core import (
    cadencia_da_bolsa,
    coleira_do_ponto,
    diagnostico_fino,
    target_hybrid,
    teclado_mudo,
    vizinhanca,
    volta_ao_ponto,
)
from ...core.inputs import Input
from ...core.pet import SEGUNDOS_PARA_A_COMIDA_SER_USADA, PetFeeder
from ...core.target_hybrid import MorteDoAlvo
from ...core.zones import coord_para_pixel_do_minimapa, distancia_linear

# Fatia máxima de espera antes de conferir se é para continuar. 0,05 s dá parada
# praticamente instantânea e não custa processador.
FATIA_DE_ESPERA = 0.08

# ===========================================================================
# O LACO SIMPLES -- 26/08/2026, e ele e o laco que RODA
# ===========================================================================
#
# Decisao do usuario, depois de uma sequencia de refinamentos que foram ficando
# piores em vez de melhores:
#
#     *"Ta so piorando as coisas, vamos voltar ao simples. Deixa as funcoes que
#      fizemos ai paradas sem uso, para testar outra hora. O que vamos fazer:
#      voce vai dar TAB, deixar rodar a macro ate o final, so para a macro no
#      meio se SAIR DE BATALHA. Nao verifica mais vida, nao verifica mais nada.
#      As unicas coisas que se mantem sao as verificacoes fora de batalha e a
#      pocao de vida nos 30% de HP."*
#
# O LACO INTEIRO, e ele cabe em quatro linhas:
#
#     FORA de batalha  -> pet, comida, voltar ao ponto, TAB, roda a macro
#     EM batalha       -> roda a macro de novo, sem TAB e sem conferencia
#     saiu de batalha  -> corta a macro no meio, volta ao topo
#     vida < 30%       -> a cura, que ja era chamada entre voltas
#
# POR QUE ISSO NAO LARGA MOB VIVO -- que era o defeito que matou o personagem em
# 25/08/2026. Em batalha o bot NAO da TAB: ele so repete a macro. O TAB so sai
# quando a luta acabou, e a luta so acaba quando nao ha mais nada batendo. Nao
# existe caminho onde ele troca de alvo com o mob de pe.
#
# E O MOB DO PENHASCO SE RESOLVE SOZINHO, sem regua nenhuma: o bot TABa nele,
# roda a macro, nunca entra em batalha, chega ao fim da volta ainda fora de
# batalha -- e TABa de novo. A regra que precisou de tres versoes e uma morte
# para ficar de pe virou consequencia de nao existir.
#
# ===========================================================================
# O QUE FICOU PARADO, E POR QUE NAO FOI APAGADO
# ===========================================================================
#
# Desligar por interruptor e a regra do projeto ("interruptor, nao comentario
# nem apagar"), e aqui ela vale duplamente: cada peca abaixo tem medicao atras
# dela, e apagar jogaria fora o aprendizado junto com o codigo.
#
#   `_alvo_morreu`, `MorteDoAlvo`      morte pelo HP da memoria
#   `_olhar_a_tela`, `_vida_do_alvo`   a segunda porta (a barra desenhada)
#   `_linhas_cegas`                    o pedagio das 3 linhas
#   `_alvo_intocavel`                  a regua do mob do penhasco
#   `_alvo_aceitavel`, `_esperar_o_alvo_trocar`, `_alvo_ilegivel_demais`
#   `_observar_depois_da_morte`, `_urgir`
#
# Todas continuam testadas: `tests/test_tab_no_app.py` desliga este interruptor
# na fixture e exercita o laco antigo inteiro. Religar e trocar um `True` por
# `False` -- e o teste que ja existe volta a valer para o codigo que roda.
LACO_SIMPLES = True

# Intervalo mínimo entre dois toques na tecla do pet.
#
# O pet não aparece na hora: entre apertar e a memória acusar `pet ativo` passam
# alguns segundos. Sem este intervalo, cada volta da macro leria "pet caído" de
# novo e apertaria de novo -- e em várias classes a tecla é interruptor, então o
# segundo toque desfaria o primeiro. É a mesma armadilha da tecla de montaria,
# que já custou caro neste projeto.
INTERVALO_ENTRE_INVOCACOES = 6.0

# Espera depois de apertar a tecla do pet, antes de seguir para as teclas da
# macro. Curta de propósito: é só para o comando sair antes da rajada seguinte,
# não para esperar o pet aparecer -- quem confere isso é a volta seguinte.
ESPERA_DEPOIS_DE_INVOCAR = 1

# Constantes mantidas para compatibilidade com testes e configuração.
# O executor NÃO usa mais estas constantes para movimento (ecossistema cego).
#
# A TOLERÂNCIA MORA NO `core/` desde 07/09/2026: a Fada passou a usar a mesma
# régua, e número lido por dois lados mora num lugar só.
TOLERANCIA_POSICAO = volta_ao_ponto.TOLERANCIA

# Quanto se espera a flag de combate BAIXAR depois de o alvo cair.
#
# Decisão do usuário em 06/09/2026: *"durante esses 2 segundos tem que
# ativamente ficar verificando se saiu de batalha, para não precisar ficar esse
# tempo todo parado; de qualquer forma o sair de batalha garante que a batalha
# já terminou (...) pois garante que não tem ninguém batendo no personagem"*.
#
# ATIVO, e é isso que faz o número ser barato: sai no instante em que a flag
# baixa, e no caso comum isso leva bem menos que o teto.
#
# 2,0 -> 2,5 EM 07/09/2026: a medição de 4977 saídas deu p90 = p95 = p99 = 1,91
# com máximo 1,92 -- uma PAREDE, não uma distribuição. O teto antigo cortava a
# cauda e mandava o excedente para o lado dos "estouros". O porquê medido e o
# que o council apontou estão em `docs/decisoes/alvo-o-que-esta-medido.md`.
SEGUNDOS_PARA_CONFIRMAR_A_SAIDA = 2.5

# Passo da conferência ativa acima. É leitura de memória; 0,1 s dá 20 amostras
# dentro do teto sem pesar.
PASSO_DA_SAIDA_DE_BATALHA = 0.1

# A COLEIRA NÃO EXPORTA MAIS TETO NENHUM -- ver `core/coleira_do_ponto.py`.
# Ela virou medição em 06/09/2026, depois de a recusa por distância matar uma
# conta: recusar o primeiro alvo do TAB empurra a seleção para o mob seguinte,
# que é mais longe, e o personagem corre até lá com o spot inteiro atrás.


# Teto da espera da TRAVA DE POSIÇÃO pela chegada à base.
#
# 2,0 porque era exatamente esse o `time.sleep` cego que existia aqui -- o teto
# não pode custar mais que o gasto que ele substitui. A diferença é que agora
# ele quase nunca é pago: quem chega antes segue antes.
# ===========================================================================
# O TAB DEIXOU DE SER LINHA DA MACRO
# ===========================================================================
#
# Pedido do usuário em 25/08/2026:
#
#     *"Na macro não vai mais precisar que o usuário cadastre o TAB como
#      primeira linha; você irá dar o TAB e rodar a macro quando identificar
#      que o target é diferente de 0 pela memória."*
#
# POR QUE ISSO É MELHOR QUE A LINHA 1. O TAB como primeira linha era apertado
# TODA volta, inclusive no meio de uma luta -- e aí ele TROCAVA de alvo, largava
# o mob machucado e começava outro do zero. O usuário não tinha como saber:
# apertar TAB sem enxergar o alvo é apostar.
#
# Agora o bot LÊ (`0x0115CB80`): tem alvo, não mexe; não tem, aperta uma vez.
# É a mesma virada do combate do BC -- ver `docs/decisoes/memoria-primeiro.md`.
#
# UMA LINHA DA MACRO A MENOS também é uma linha a mais de skill, já que o
# número de passos é fixo.
SEGUNDOS_PARA_O_ALVO_APARECER = 0.35

# ===========================================================================
# O MOB MORREU: A MACRO PARA NO MEIO E VAI PARA O PRÓXIMO
# ===========================================================================
#
# Pedido do usuário em 25/08/2026:
#
#     *"Caso o mob morra antes de acabar a macro inteira, pode ir para o próximo
#      mob sem terminar a macro. Ou, caso não morra, você não aperta TAB: você
#      recomeça a macro até garantir que ele morreu, daí você passa para o
#      próximo mob."*
#
# São as DUAS metades da mesma regra, e as duas só existem porque agora o bot
# ENXERGA o alvo (`hp/max_hp` pela memória, desde 25/08):
#
#   morreu antes do fim  -> corta a rotação AQUI. Terminar de bater num cadáver
#                           é tempo puro perdido, e o mob seguinte está esperando.
#   não morreu           -> NÃO aperta TAB. Recomeça a macro no mesmo mob, até
#                           ele cair.
#
# ANTES DISSO O BOT ERA CEGO: ele rodava a sequência inteira ou nada, e o TAB da
# linha 1 trocava de alvo toda volta -- largando o mob machucado no meio.
#
# CADÁVER NÃO É ALVO. O corpo fica selecionável por 7 a 13 s (medido em
# 20/08/2026), então `id != 0` continua verdadeiro depois da morte. Quem decide
# é a VIDA: `hp == 0` é cadáver, e cadáver libera o TAB.
INTERROMPER_A_MACRO_QUANDO_O_ALVO_MORRE = True

# De quanto em quanto tempo perguntar "o alvo morreu?" DENTRO da espera de uma
# linha da macro.
#
# A leitura custa microssegundos; o que se paga é a volta do laço. O passo deixa
# o corte acontecer no meio de uma espera longa -- uma linha de 3000 ms sem isto
# faria o bot bater num cadáver por até 3 segundos.
#
# ERA 0,1 s; subiu para 0,16 s numa afinação manual do usuário (01/09/2026). O
# teto de atraso do corte sobe junto, e continua muito abaixo de uma linha.
PASSO_DA_CONFERENCIA_DO_ALVO = 0.16

# Quantos saltos da roda do TAB antes de desistir desta aquisição.
#
# ===========================================================================
# A RODA É ORDENADA POR DISTÂNCIA, E ISSO MUDA TUDO -- 26/08/2026
# ===========================================================================
#
# Informação do usuário, e ela derruba o raciocínio que sustentava o 8:
#
#     *"Ainda está se perdendo no tab. O ideal é tentar manter só no PRIMEIRO
#      tab, para evitar ficar indo em mobs muito longes, pq o tab vai primeiro
#      no mob MAIS PERTO e conforme vai clicando ele vai indo nos mobs mais
#      LONGES."*
#
# A versão anterior dizia "CICLAR É BARATO" e usava oito saltos, medindo o
# custo em MILISSEGUNDOS. O custo nunca foi tempo: **cada salto é um mob mais
# longe**, e engajar um mob longe faz o personagem atravessar o ponto de farm
# até ele -- puxando o que estiver no caminho. É o *"chamou vários mobs e
# morreu"*, e a roda de oito era o motor disso.
#
# UM. O usuário começou pedindo *"tentar manter só no primeiro tab"* e eu
# implementei DOIS, com o argumento de que o segundo servia para passar pelo
# cadáver do mob recém-morto (que fica selecionável de 7 a 13 s). Ele voltou no
# mesmo dia e cortou o argumento:
#
#     *"Eu quero que seja apenas 1 único tab por vez, pois com essa questão de
#      GARANTIR o tab, está fazendo ir em outro mob e não no mais perto."*
#
# E ele está certo sobre o que o segundo salto realmente faz. "Passar pelo
# cadáver" era o caso que eu tinha em mente; o caso que ACONTECE é o segundo
# salto cair no segundo mob mais próximo -- que é exatamente "ir em outro mob e
# não no mais perto". Insistir para GARANTIR um alvo é trocar a mira certa por
# uma mira qualquer, e é assim que o personagem atravessa o ponto de farm.
#
# O QUE ACONTECE QUANDO O ÚNICO SALTO NÃO SERVE: a volta acaba sem macro, o bot
# paga `SEGUNDOS_PARA_A_RODA_REINICIAR` e a volta seguinte tenta de novo -- de
# novo no mais perto. Nada é "garantido", e é esse o ponto: **é melhor não ter
# alvo por alguns segundos do que ter o alvo errado**.
#
# O CAMINHO DE DOIS SALTOS NÃO FOI APAGADO, virou interruptor: subir esta
# constante religa o espaçamento (`ESPERA_ENTRE_TABS`) e o resto do laço sem
# mexer em mais nada.
# MUDADO EM 30/08/2026: o usuário pediu 4 tentativas. Com o portão de
# aquisição propagando o False, é seguro — se as 4 falharem, a macro não roda.
TENTATIVAS_DE_TAB = 1

# Quanto esperar depois de uma aquisição FRACASSADA, antes da volta seguinte.
#
# É o que faz a retentativa começar do MOB MAIS PERTO em vez de continuar de
# onde a roda parou. A roda do jogo volta ao começo sozinha depois de um tempo
# sem TAB; sem esta pausa, a volta seguinte apertaria o TAB com a roda ainda
# adiantada e pegaria um mob ainda mais longe -- exatamente o que
# `TENTATIVAS_DE_TAB = 2` existe para impedir.
#
# NÚMERO SEM MEDIÇÃO ATRÁS, e está dito de propósito: ninguém mediu em quanto
# tempo a roda deste cliente reinicia. Três segundos é folga confortável para o
# comportamento típico e barata (só é paga quando NÃO houve alvo). Se um dia
# alguém medir, o número desce.
SEGUNDOS_PARA_A_RODA_REINICIAR = 1.6

# Quantas voltas SEGUIDAS sem conseguir alvo antes de pagar a pausa acima.
#
# A pausa não é paga na primeira falha: um ponto de farm normal tem momentos em
# que o TAB não acha nada vivo (o mob acabou de morrer, o próximo ainda não
# nasceu), e descansar 1,6 s a cada um deles é tempo de farm jogado fora. Só
# quando a falha VIRA PADRÃO é que faz sentido esperar a roda reiniciar.
#
# Era um literal solto no meio de `_garantir_alvo`; virou constante porque o
# teste precisa do mesmo número, e número lido por dois lados mora num lugar só.
VOLTAS_SEM_ALVO_ANTES_DE_DESCANSAR = 3

# Quantos TABs seguidos SEM O ID MUDAR antes de desistir.
#
# Separado de `TENTATIVAS_DE_TAB` porque são fracassos diferentes:
#
#   o id MUDOU e caiu noutro cadáver  -> a roda está girando; continuar é certo
#                                        e custa quase nada
#   o id NÃO MUDOU                    -> a tecla não está pegando (mal
#                                        configurada, janela sem foco de
#                                        mensagem, jogo travado). Insistir aqui
#                                        paga o teto inteiro por tentativa
#
# Sem esta separação, uma tecla que não funciona custaria
# `TENTATIVAS_DE_TAB * SEGUNDOS_PARA_O_ALVO_APARECER` por volta, para sempre.
#
# COM UM SALTO SÓ, ELE CONTA ENTRE VOLTAS E NÃO DENTRO DA RAJADA. Antes a
# rajada tinha até oito saltos e dá para contar "seguidos" ali dentro; hoje só
# sai um TAB por aquisição, e um contador local nunca chegaria a dois.
#
# Se ele não tivesse mudado de lugar, uma tecla mal configurada seria relatada
# como *"só cadáver por aqui"* para sempre -- o diagnóstico errado, e o usuário
# procurando mob onde o problema é a tecla. Os dois cortes existem justamente
# porque os dois fracassos pedem AÇÕES diferentes: um manda esperar, o outro
# manda configurar.
TABS_SEM_RESPOSTA_PARA_DESISTIR = 1


# Quantas LINHAS da macro sem o alvo perder vida antes de trocar de alvo.
#
# Pedido do usuário em 25/08/2026:
#
#     *"Caso esteja tentando bater no target e a vida dele não sair do zero,
#      passa para o próximo target -- pode acontecer de, por exemplo, estar em
#      um penhasco e dar target lá no mob de baixo, e o jogo não deixar
#      atacar."*
#
# É a régua do alvo INALCANÇÁVEL, e ela só existe porque o bot passou a ler o HP
# exato do alvo. Antes, um mob impossível de acertar prendia a conta pelo prazo
# inteiro da luta.
#
# CONTA POR LINHA, não por skill de ataque -- decisão do usuário. Duas linhas e
# nenhum ponto de vida a menos não é azar, é alcance.
#
# O CONTADOR É DO ALVO, não da volta: ele atravessa rotações e zera quando o HP
# cai ou quando o alvo troca.
#
# =========================================================================
# ELA SÓ PODE DISPARAR NUM ALVO NUNCA TOCADO -- e isso é conserto, não zelo
# =========================================================================
#
# Relato do usuário em 25/08/2026: *"eu acompanhei que trocou de target sem ter
# matado o target, agora nessa última versão, fazendo que o personagem
# morresse"*.
#
# Era esta régua. Ela troca de alvo com o mob VIVO, por desenho -- e numa macro
# de linhas curtas duas linhas podem passar em menos de um segundo, antes de o
# servidor registrar o primeiro golpe. O bot largava um mob que ESTAVA sendo
# morto, o mob largado continuava batendo, e o personagem morria.
#
# A trava é exigir `hp == max_hp`: se o alvo está INTEIRO depois de N linhas,
# não é atraso de servidor, é alcance. Machucou um ponto que seja? Então dá para
# acertar, e a régua não tem mais o que dizer.
# ===========================================================================
# ALVO INTEIRO (100/100): EXIGÊNCIA REVOGADA PELO USUÁRIO -- 26/08/2026
# ===========================================================================
#
# Este interruptor nasceu de um pedido de 25/08/2026 (*"adquiriu target novo
# com 100/100 de HP (se não, dá TAB novamente)"*) e foi REVOGADO pelo próprio
# usuário no dia seguinte:
#
#     *"anteriormente em outra sessão eu tinha falado que precisava estar com a
#      vida 100/100, mas não precisa, pode ser qualquer vida, o importante é ser
#      um alvo DIFERENTE."*
#
# POR QUE A REVOGAÇÃO É CONSERTO, E NÃO RECUO. Ligado, ele produziu o defeito
# relatado em 26/08: *"começou a ficar andando e dando tab, chamou vários mobs e
# morreu"*. O mecanismo é direto -- num ponto de farm movimentado quase todo mob
# da roda está machucado (outro jogador batendo, regeneração parcial, o próprio
# bot tendo largado antes). Com a exigência ligada, `_garantir_alvo` recusava
# TODOS, girava as `TENTATIVAS_DE_TAB` inteiras, devolvia `False`, e a volta
# seguinte recomeçava a roda. O resultado é TAB contínuo sem nunca engajar --
# e cada TAB é um mob a mais olhando para o personagem.
#
# O CRITÉRIO DE AQUISIÇÃO VOLTA A SER "ESTÁ VIVO", e o que separa um alvo novo
# do anterior é a IDENTIDADE (`_esperar_o_alvo_trocar` exige id DIFERENTE), que
# sempre foi a pergunta certa. Cadáver continua recusado -- `hp <= 0`.
#
# O interruptor fica de pé para o caso de o mapa mudar de caráter, mas ligá-lo
# de novo exige medir antes: ele já matou o personagem uma vez.
EXIGIR_ALVO_INTEIRO = False

# Quantas LINHAS da macro sem ENTRAR EM BATALHA antes de trocar de alvo.
#
# O CRITÉRIO MUDOU EM 01/09/2026 -- era "sem o alvo perder vida", virou "sem
# entrar em batalha". O nome ficou a pedido do usuário. Ver `_alvo_intocavel`
# para o porquê: a régua por dano dependia de ler a vida do alvo, que é o que
# falha justamente no caso que ela existe para pegar.
#
# QUATRO, valor que já estava configurado quando o critério mudou. É o que dá
# margem para uma primeira skill de conjuração longa sair antes de o bot
# concluir que está batendo no vazio.
LINHAS_SEM_DANO_PARA_TROCAR = 4

# ===========================================================================
# O QUE É "ABSOLUTO" NUMA CONFIRMAÇÃO DE MORTE
# ===========================================================================
#
# Pedido do usuário: *"a confirmação de HP = 0 deve ser absoluta para evitar
# que o bot pule de alvo deixando mobs vivos batendo nele."*
#
# ABSOLUTO NÃO QUER DIZER "LER VÁRIAS VEZES". Uma versão intermediária deste
# arquivo exigiu N leituras consecutivas de `hp <= 0` e ficou PIOR: o cadáver
# no início da volta deixava de ser reconhecido na primeira pergunta, e o
# portão de `_garantir_alvo` voltava a bloquear o TAB -- o defeito original,
# reintroduzido pelo próprio conserto.
#
# ABSOLUTO QUER DIZER "SÓ DECIDE QUEM TEM PROVA". A lei do projeto já é essa e
# está no `CLAUDE.md`: **`hp == 0` é morte, e ponto** -- `alvo_atual()` valida
# a struct (`0 <= hp <= max_hp`) antes de responder, então um HP legível NÃO é
# palpite. O que nunca teve prova é o `None`, e é só dele que trata a reserva
# abaixo. As três respostas, então:
#
#   HP legível e `> 0`   -> VIVO. Um ponto de vida derruba qualquer suspeita.
#   HP legível e `<= 0`  -> MORTO, na primeira leitura.
#   HP ILEGÍVEL          -> a reserva decide; sem ela, "não sei" = continua
#                           batendo.
# ===========================================================================
# A RESERVA: QUANDO O HP É ILEGÍVEL, QUEM RESPONDE É A FLAG DE COMBATE
# ===========================================================================
#
# Decisão do usuário em 26/08/2026:
#
#     *"caso não consiga identificar a vida você deve usar o `em combate =
#      False`. Caso saia do True e fique False, é pq saiu de batalha e o mob já
#      está morto. Caso não saia, ou não está morto ou tem outro mob batendo no
#      personagem."*
#
# É a saída para o estado absorvente que travou o bot por 28 minutos seguidos em
# 25/08: com o HP ilegível, `_alvo_morreu()` respondia `False` para sempre, e
# `_garantir_alvo` lia isso como "alvo vivo, não mexe" -- então o TAB nunca era
# apertado e a macro rodava contra o corpo indefinidamente.
#
# O QUE VALE É A TRANSIÇÃO, NÃO O NÍVEL. `em_batalha == False` sozinho não diz
# nada (o bot passa a maior parte do tempo fora de combate entre um mob e o
# outro). O que prova a morte é ter estado em batalha e DEIXAR de estar
# enquanto o alvo continua selecionado e ilegível.
#
# E A CONCLUSÃO É HONESTA NOS DOIS SENTIDOS: a flag NÃO baixar não prova nada,
# porque pode ser outro mob batendo -- exatamente como o usuário descreveu. Por
# isso a reserva só sabe dizer "morreu"; ela nunca diz "está vivo".
USAR_COMBATE_COMO_RESERVA_DE_MORTE = True

# Quantas VOLTAS inteiras com o alvo selecionado e o HP ilegível antes de
# trocar de alvo.
#
# É o escape do estado absorvente, e ele existe porque a reserva acima pode não
# ter o que dizer: com OUTRO mob batendo no personagem a flag de combate nunca
# baixa, então nem o HP nem a batalha respondem sobre este alvo.
#
# DUAS, e não uma: a entidade some do array por uma leitura em ~45 com o mob
# VIVO (medido em 25/08/2026), e uma volta inteira sem NENHUMA leitura boa já é
# um evento raro. Duas seguidas não é flicker, é ausência.
VOLTAS_COM_ALVO_ILEGIVEL_PARA_TROCAR = 2

# Quanto esperar antes de tentar de novo quando NÃO HÁ alvo vivo.
#
# Sem isso o laço de `rodar()` giraria sem pausa perguntando a memória, e o
# custo real de um APP parado seria uma CPU a 100%.
ESPERA_SEM_ALVO = 0.4

# Respiro ANTES do TAB -- entre a última tecla da macro e a troca de alvo.
#
# Pedido do usuário em 26/08/2026: *"e adiciona 600ms antes do tab"*.
#
# É o gêmeo do respiro de baixo, e pela mesma razão: a volta acabou de mandar a
# última linha da rotação, o cliente ainda está digerindo aquelas teclas, e o TAB
# que chega em cima se perde. A diferença é o que se perde -- ali é a primeira
# skill da luta, aqui é a PRÓPRIA AQUISIÇÃO, e um TAB engolido custa uma volta
# inteira contra o cadáver até a próxima chance.
#
# =========================================================================
# PAGO UMA VEZ POR AQUISIÇÃO, NÃO UMA VEZ POR TECLA
# =========================================================================
#
# A roda do TAB pode girar até `TENTATIVAS_DE_TAB` vezes, e cobrar 0,6 s em cada
# salto somaria ~4,8 s por volta num ponto de farm cheio de cadáveres -- sem
# comprar nada. O que este respiro resolve é a colisão com as teclas da MACRO,
# e essas só existem antes do PRIMEIRO TAB.
#
# Entre um salto e o outro já existe espaçamento de sobra: `_esperar_o_alvo_
# trocar` só devolve quando o id MUDOU, ou seja, quando o TAB anterior foi
# PROCESSADO. Um TAB nunca chega em cima de outro TAB pendente.
#
# SÓ É PAGO QUANDO UMA TECLA VAI SAIR. Alvo vivo na mira não gasta nada, igual
# ao respiro de baixo.
ESPERA_ANTES_DO_TAB = 0.4

# Respiro entre o TAB e a PRIMEIRA linha da macro.
#
# Pedido do usuário em 25/08/2026: *"dá uns 500ms depois do TAB para começar a
# rodar a macro, só para garantir que vai começar da linha 1; às vezes está
# sendo muito rápido"*. **Dobrado para um segundo inteiro em 26/08/2026**, pelo
# mesmo usuário e pelo mesmo motivo: *"após o tab em vez de 500ms pode colocar 1
# segundo inteiro"*. Meio segundo não estava assentando.
#
# É o mesmo caso do botão "Sell" na venda: a tecla seguinte chega enquanto o
# cliente ainda está digerindo a anterior, e se perde. Aqui o custo de perder é
# a primeira skill da rotação -- justamente a que abre a luta.
#
# SÓ É PAGO QUANDO UM TAB SAIU, e é isso que torna o segundo inteiro barato:
# alvo que já estava vivo não gasta nada, então o custo é uma vez por mob morto,
# não uma vez por volta da macro.
#
# NÚMERO DE OBSERVAÇÃO DE CAMPO, não de medição instrumentada -- é o usuário
# vendo a primeira linha se perder.
ESPERA_DEPOIS_DO_TAB = 0.01

SEGUNDOS_PARA_A_TRAVA_DEVOLVER = 2.0

# Piso de qualquer tempo do APP, em milissegundos. O MESMO número vive em
# `config.MINIMO_DE_ESPERA_DO_APP_MS`, e a duplicata é deliberada: o executor
# do APP NÃO importa `blazesbot.config` (travado por
# `test_o_executor_do_app_so_usa_o_core`), então ele guarda a própria cópia e
# um teste confere que as duas batem.
MINIMO_DE_ESPERA_DO_APP_MS = 100

# ===========================================================================
# A CAMINHADA DE VOLTA À BASE NÃO ACONTECE EM BATALHA
# ===========================================================================
#
# Decisão do usuário em 26/08/2026:
#
#     *"É bom ter essas delays e deixar os 2 segundos de retorno para o lugar,
#      A MENOS QUE ESTEJA EM BATALHA é claro (...) é bom ter mais cuidado para
#      não sair puxando os outros mobs e fazer ele morrer."*
#
# Os 2 s de `SEGUNDOS_PARA_A_TRAVA_DEVOLVER` FICAM -- o pedido não é andar
# menos, é não andar NA HORA ERRADA. Atravessar o ponto de farm com um mob em
# cima é a receita do puxarão: o mob acompanha, o caminho passa por outros, e o
# personagem chega na base com três em cima em vez de um.
#
# É a MESMA guarda do shuffle anti-AFK, e pelo mesmo motivo. Quando a luta
# acabar, a volta seguinte devolve o personagem ao ponto normalmente.
#
# "NÃO SEI" NÃO BLOQUEIA: sem leitura de batalha nem de alvo, anda como antes.
# Bot que não volta para o ponto é pior que bot que volta na hora errada, e a
# trava de posição é justamente o que impede a deriva pelo mapa.
ANDAR_SO_FORA_DE_BATALHA = True

# ===========================================================================
# DEPOIS DE MATAR, O BOT OBSERVA -- E O QUE ELE OBSERVA É A BATALHA
# ===========================================================================
#
# Desenho do usuário em 26/08/2026, e ele separa duas perguntas que estavam
# grudadas:
#
#     *"A vida ir a zero nós usamos para ANALISAR O MOB e saber se já matamos
#      ele. (...) Então zerou a vida, analisa por 3 segundos: se não saiu [de
#      batalha], pode dar tab e recomeçar a macro, POIS TEM ALGUÉM BATENDO. Dá
#      para conferir pela vida atual do personagem, que vai estar descendo
#      também."*
#
# AS DUAS PERGUNTAS:
#
#   "aquele mob morreu?"       -> responde o HP DELE (`hp == 0`)
#   "a luta acabou?"           -> responde a FLAG DE COMBATE
#
# São coisas diferentes e o bot tratava como uma só. Matar o alvo não quer dizer
# que a luta acabou: se OUTRO mob está batendo, a flag continua em `True` -- e
# aí o certo não é fazer o ciclo calmo (pet, comida, caminhada, respiros), é
# pegar o mob novo AGORA e voltar a bater.
#
# O TETO É AVISO, NÃO GASTO. A observação PERGUNTA a cada
# `PASSO_DA_CONFERENCIA_DO_ALVO` e sai no instante em que a flag baixa, então a
# morte limpa — que é a maioria — custa um décimo de segundo, não três.
#
# ISTO SUBSTITUIU UM RESPIRO CEGO de 1 s que existia aqui. Ele tinha sido posto
# pelo motivo certo (a flag de combate demora um instante para baixar, e a
# caminhada e a cura decidem em cima dela), mas ESPERAVA em vez de PERGUNTAR --
# pagava 1 s sempre e mesmo assim não sabia dizer se a luta tinha acabado.
SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE = 2.5

# ===========================================================================
# SAIR DE BATALHA CORTA A MACRO NO MEIO
# ===========================================================================
#
#     *"Vamos usar a flag se está em batalha para, na hora que sair de batalha,
#      poder PARAR A MACRO NO MEIO e seguir com o resto."*
#
# É a segunda fonte de "o mob caiu", e ela vale onde a primeira falha: com o HP
# do alvo ILEGÍVEL (a entidade sai do array), a flag continua respondendo. Sair
# de batalha com a macro rodando só tem uma explicação -- não há mais nada
# lutando com o personagem.
#
# O QUE VALE É A TRANSIÇÃO `True -> False`, nunca o nível: o bot passa a maior
# parte do tempo fora de combate, entre um mob e o outro.
USAR_A_SAIDA_DE_BATALHA_PARA_CORTAR = True

# ===========================================================================
# A SEGUNDA PORTA: A VIDA PELA TELA -- 26/08/2026
# ===========================================================================
#
# Decisao do usuario, depois da medicao que provou o buraco:
#
#     *"Mantem como primeira porta o HP pela memoria; caso nao ache, usa a vida
#      pela tela -- no `target_hybrid` tem uma funcao para isso tambem."*
#
# O QUE A MEDICAO MOSTROU (ver `docs/decisoes/alvo-o-que-esta-medido.md`, item
# 41): tres mobs VIVOS, `Rose Snake nv61 100/100`, existiam na memoria em
# `0x3670xxxx` e **nao eram alcancaveis** pela janela que `_procurar_entidade`
# varre. Nao e a leitura do HP que esta quebrada -- e o lugar onde se procura a
# entidade. Enquanto o array de verdade nao for achado, a barra desenhada e a
# unica fonte que responde por esses mobs.
#
# ISTO INVERTE, SÓ NO APP, A REGRA `SO_A_MEMORIA_DECLARA_MORTE` DO BC. La a tela
# nunca declara morte, por causa do falso positivo medido do `EnemyDead.png`
# (0,955-0,971 com o mob VIVO). Aqui ela pode -- e o pedagio e
# `LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA`, abaixo. O BC nao muda.
USAR_A_TELA_COMO_SEGUNDA_PORTA = True

# Quantas LINHAS da macro passam antes de a tela ser consultada pela primeira
# vez numa rotacao.
#
#     *"So vai comecar a ler a partir da segunda linha, no caso antes de comecar
#      a terceira linha."*
#
# O motivo e economia: logo depois do TAB a entidade pode simplesmente ainda nao
# ter entrado no array (medido: 1 leitura em ~45), e pagar uma captura de janela
# para descobrir isso seria caro. As primeiras linhas dao tempo de a memoria
# responder sozinha no caminho feliz.
#
# ERAM DUAS; passou a TRES numa afinacao manual do usuario (01/09/2026), ou seja
# a tela so entra a partir da QUARTA linha. Quem le este numero como "a partir
# da linha N+1" nao se engana quando ele mudar de novo.
LINHAS_ANTES_DE_OLHAR_A_TELA = 3

# Intervalo minimo entre duas capturas.
#
#     *"Depois sera a cada 500ms ou a cada linha, o que for MAIOR."*
#
# As duas condicoes valem juntas: nunca duas vezes na MESMA linha, e nunca com
# menos de meio segundo entre elas. Numa macro de linhas longas manda a linha;
# numa de linhas curtas manda o meio segundo.
#
# O NUMERO IMPORTA. A conferencia do alvo roda a cada
# `PASSO_DA_CONFERENCIA_DO_ALVO` (0,1 s) dentro da espera de cada linha -- se a
# tela entrasse ali, seriam 10 capturas por segundo POR CONTA. A cadencia visual
# do BC (`VISUAL_CHECK_SECONDS`) e de 10 s, cem vezes menos.
INTERVALO_MINIMO_DA_TELA = 0.5

# Quantas linhas o bot continua batendo DEPOIS de a tela dizer que o mob morreu.
#
#     *"Caso for pela tela, sempre deixa rodar mais 3 linhas depois de confirmar
#      a morte, caso tenha cadastrado, so para garantir por causa do falso
#      positivo da morte."*
#
# BATE CEGO, e isso e o pedido literal: nao pergunta mais nada nessas linhas. E
# seguro porque bater num cadaver custa tempo, e trocar de alvo com o mob VIVO
# custa o personagem -- foi o defeito que matou ele em 25/08/2026.
#
# "CASO TENHA CADASTRADO": se a macro acabar antes das tres linhas, acabou. O
# pedagio e o que sobrar.
#
# E SAIR DE BATALHA CORTA NA HORA, mesmo no meio das tres linhas -- ver
# `USAR_A_SAIDA_DE_BATALHA_PARA_CORTAR`. Decisao do usuario, e ela e regra
# geral: *"se saiu de batalha e garantido que matou e nao tem outro mob
# batendo"*.
LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA = 3

# Abaixo de quanto a barra desenhada conta como morte.
#
# O MESMO numero do `LIMIAR_VIDA_TELA` do `core/target_hybrid.py`, e a copia e
# deliberada pelo mesmo motivo do piso de 100 ms: este modulo nao importa o
# `target_hybrid` inteiro por escolha de isolamento, e um teste confere que os
# dois batem.
LIMIAR_DE_MORTE_NA_TELA = 0.02

# Espaçamento entre um salto da roda do TAB e o seguinte.
#
# `_esperar_o_alvo_trocar` devolve NO INSTANTE em que o id muda, então uma roda
# cheia de cadáveres era varrida em rajada: até `TENTATIVAS_DE_TAB` seleções em
# menos de meio segundo. É o que o usuário viu como *"trocando rápido demais"*.
#
# NÃO É O MESMO NÚMERO DO `ESPERA_ANTES_DO_TAB`, e não deve ser: aquele existe
# para o TAB não chegar em cima das teclas da MACRO, e é pago uma vez. Este
# existe para a varredura não ser uma rajada, e é pago entre saltos. Menor de
# propósito -- girar a roda continua sendo barato.
ESPERA_ENTRE_TABS = 0.60

# Quantas voltas seguidas COM alvo e FORA de batalha antes de trocar de alvo.
#
# Existe como rede de segurança da regra "TAB só quando falta alvo" (ver
# `_preciso_de_alvo`). Sem ela, um alvo que não dá para alcançar -- o mob do
# penhasco, o que está do outro lado da parede -- seria mantido para sempre: ele
# nunca entra em batalha, então nunca "morre", e o TAB nunca sairia.
#
# Três e não uma: uma volta fora de batalha é normal (o mob está vindo, a
# primeira skill errou o tempo). Três seguidas já é "não vai acontecer".
VOLTAS_SEM_BATALHA_PARA_TROCAR = 3

# Cadência da pergunta "já cheguei?". Leitura de posição é de microssegundos; o
# custo é o `sleep`.
PASSO_DA_ESPERA_DA_BASE = 0.1

# De quanto em quanto tempo perguntar "o alvo ja trocou?" depois do TAB.
#
# ===========================================================================
# ERA AQUI O ATRASO ENTRE O TAB E A LINHA 1 -- 26/08/2026
# ===========================================================================
#
# Relato do usuario: *"as vezes esta existindo alguma delay entre o clicar o TAB
# e comecar a macro, e NAO e a configuracao nova, pois eu testei colocando
# 100ms"*.
#
# Ele estava certo em descartar a linha 0. A confirmacao do TAB reusava
# `PASSO_DA_ESPERA_DA_BASE` (0,1 s), que e a cadencia de "ja cheguei na base?" --
# um numero pensado para CAMINHADA, onde decimos nao importam. Aqui ele custava
# ate 100 ms mortos por aquisicao: o jogo processava o TAB em alguns
# milissegundos e o bot so olhava de novo no tique seguinte.
#
# 10 ms porque a leitura do id e UM `read_int` (~1 us). Cem perguntas por
# segundo custam microssegundos de processador e devolvem o controle
# praticamente no instante em que o jogo responde.
#
# NAO E "um numero lido por dois lados" em relacao ao passo da BASE: sao duas
# perguntas diferentes ("cheguei?" e "trocou?"), com custos e urgencias
# diferentes.
#
# MAS "trocou?" agora e perguntada pelos DOIS ecossistemas, e ai a regra vale:
# o valor mora em `core/target_hybrid.py` e este nome e so o apelido local, para
# o APP continuar lendo pelo nome que ele sempre usou. Duas copias de 0,01
# divergiriam em silencio, e a que ficasse para tras perguntaria devagar.
PASSO_DA_CONFIRMACAO_DO_TAB = target_hybrid.PASSO_DA_CONFIRMACAO_DO_TAB
SHUFFLE_DEFAULT_PIXELS = 5

# Cada perna do shuffle anti-AFK (ida e volta). Era `time.sleep(1.0)` cego duas
# vezes; hoje passa por `_esperar`, que responde ao Parar e confere a morte do
# alvo dentro da espera. O número é o mesmo -- o que mudou é a natureza.
SEGUNDOS_DO_PASSO_DO_SHUFFLE = 3.0


class Passo(Protocol):
    """O que o executor precisa de uma linha: a tecla e a espera."""

    key: str
    delay_ms: int


class ExecutorDeMacro:
    """Roda a sequência de teclas em laço contínuo.

    `fonte_dos_passos` é uma função, não uma lista, de propósito: ela é chamada a
    cada volta, então editar a sequência na interface com o bot rodando passa a
    valer na volta seguinte, sem reiniciar nada.

    `continuar` também é função: devolve False quando é para encerrar (o usuário
    parou, desmarcou o modo, ou a janela do jogo fechou). É consultada entre
    teclas E dentro da espera.
    """

    def __init__(
        self,
        hwnd: int,
        fonte_dos_passos: Callable[[], Iterable[Passo]],
        continuar: Callable[[], bool],
        log,
        pausado: Callable[[], bool] | None = None,
        pet_ativo: Callable[[], bool | None] | None = None,
        tecla_do_pet: str = "",
        # Alimentação do pet -- a mesma lógica do BC, via `PetFeeder` compartilhado.
        # O executor é cego: não lê memória, mas confia no `PetFeeder` para decidir
        # quando apertar. Se a tecla estiver vazia, a alimentação é ignorada.
        tecla_do_pet_food: str = "",
        feed_every_minutes: Callable[[], int] | None = None,
        feed_on_start: bool = False,
        # A GRADE DA COMIDA, LIDA E GRAVADA NO DISCO -- conserto de 27/08/2026.
        #
        # Sem estas duas o executor nascia com `PetFeeder()` vazio e RE-ANCORAVA
        # o vencimento a cada reinício. Medido: 12 reinícios em 88 minutos, zero
        # refeições em 123 minutos, intervalo de 51. Ver `core/pet.py`.
        #
        # Chegam como FUNÇÕES pelo mesmo motivo que o pet e a barra: o executor
        # importa só `core.*` e não sabe o que é `BotConfig` nem conta. Quem
        # sabe é o `bot/supervisor`, que monta as duas.
        grade_da_comida: Callable[[], float | None] | None = None,
        gravar_grade_da_comida: Callable[[float], None] | None = None,
        antes_da_volta: Callable[[], None] | None = None,
        # CONFERIR SAÚDE -- o ecossistema de LOGIN/RELOGIN é a base de todos os
        # outros, e por isso todo ecossistema tem que perceber a queda ENQUANTO
        # roda. Aqui isso chega como FUNÇÃO injetada pelo supervisor, no mesmo
        # molde do pet e da barra de atalhos: o executor continua cego (importa
        # só `core.inputs`) e não sabe o que é `BotContext`, watchdog ou queda.
        #
        # Se ela levantar, a exceção SOBE -- ao contrário do `antes_da_volta`,
        # que é complemento e tem o `except` engolindo. Queda não é complemento:
        # engolir aqui deixaria a macro apertando teclas contra uma caixa de
        # "Connection interrupted" pelas horas seguintes, que foi exatamente o
        # que aconteceu em 18/08/2026.
        conferir_saude: Callable[[], None] | None = None,
        # DECLARAR QUEDA: o desfecho do teclado mudo, quando nem o ESC resolve.
        #
        # Chega como função pelo mesmo motivo de todo o resto: `Disconnected`
        # mora em `bot/context.py`, e este executor importa só `core.*`. Quem
        # sabe derrubar a sessão é o supervisor -- aqui só se constata que a
        # entrada morreu. `None` = ninguém ligou o desfecho, e aí o bot faz o
        # que fazia: avisa e continua. Ver `core/teclado_mudo.py`.
        declarar_queda: Callable[[str], None] | None = None,
        limpar_a_bolsa: Callable[[], None] | None = None,
        voltas_por_limpeza: Callable[[], int] | None = None,
        # Trava de posição: campos de configuração (salvos no config.json).
        # O executor NÃO move o personagem (ecossistema cego por design).
        # Os campos existem para persistência e UI.
        travar_posicao: bool = False,
        shuffle_apos_n_voltas: int = 30,
        # Posição base salva no config (X, Y). Se vier preenchida, usa ela em vez
        # de ler a posição atual na largada. Isso permite que o personagem retorne
        # ao ponto exato onde o APP foi iniciado, mesmo se a leitura de memória
        # falhar na primeira tentativa.
        base_pos: tuple[int, int] | None = None,
        # Função injetada para ler a posição atual do personagem (x, y) ou None.
        # Permite que o executor verifique se o personagem saiu da posição base
        # e volte andando pelo minimapa. Chega como função para preservar o
        # isolamento: o executor continua importando só core.inputs.
        posicao_atual: Callable[[], tuple[int, int] | None] | None = None,
        # Centro do minimapa em coordenadas de tela (client). Necessário para
        # converter coordenadas de jogo em cliques no minimapa.
        minimap_center: tuple[int, int] | None = None,
        # ==============================================================
        # CURA: vida baixa -> volta ao ponto inicial -> poção
        # ==============================================================
        #
        # Tudo por FUNÇÃO, pelo mesmo motivo do pet e da posição: o executor
        # recebe `hwnd` e o `Memory` precisa de `pid`. Quem tem o `Memory`
        # aberto daquela conta é o supervisor, e abrir um segundo handle do
        # mesmo processo aqui seria pior que injetar.
        #
        # A CURA chega como FÁBRICA, não como objeto pronto nem como import.
        #
        # Como import ela quebraria `test_o_executor_do_app_so_usa_o_core`, que
        # é o isolamento mais apertado do projeto e existe por um bom motivo: o
        # executor manda tecla e espera, e tudo além disso é injetado.
        #
        # Como objeto pronto não daria: a `CuraDoApp` precisa de
        # `distancia_da_base` e `mandar_voltar_para_base`, que são métodos DESTE
        # executor. A fábrica recebe `self` e resolve o ovo e a galinha sem
        # ninguém mexer em atributo de fora.
        #
        # `None` = sem proteção de vida, e o APP roda exatamente como antes.
        cura: Callable[[object], object] | None = None,
        # O CICLO DA MORTE (`bot/morte.py`), pela mesma fábrica da cura.
        morte: Callable[[object], object] | None = None,
        sincronia: Callable[[object], object] | None = None,
        alvo_e_aliado: Callable[[], bool] | None = None,
        # A FADA: cura o time clicando nos retratos e confirmando pelo TARGET_ID.
        # Chega como FÁBRICA pelo mesmo motivo da cura e da sincronia -- o executor
        # não conhece o módulo `fada`, só recebe a função que sabe montá-la.
        # `None` = sem Fada, e o APP roda exatamente como antes.
        fada: Callable[[object], object] | None = None,
        # O ALVO, com HP exato -- pedido do usuário em 25/08/2026: *"é
        # importante trazer os dados do target para o APP, para que também
        # saibamos a vida exata do mob que está sendo atacado"*. Serve para o
        # log e para a cura saber que ainda há mob VIVO batendo.
        alvo_atual: Callable[[], dict | None] | None = None,
        # O id do alvo (`0` = nenhum) e a tecla que troca de alvo. Com as duas,
        # o TAB sai do encargo do usuário -- ver
        # `SEGUNDOS_PARA_O_ALVO_APARECER`. Sem elas, nada muda.
        id_do_alvo: Callable[[], int | None] | None = None,
        tecla_de_alvo: Callable[[], str] | None = None,
        # A FLAG DE COMBATE -- a RESERVA de "o mob morreu?" para quando o HP do
        # alvo está ilegível. Ver `USAR_COMBATE_COMO_RESERVA_DE_MORTE`. Chega
        # como função pelo mesmo motivo de todo o resto: o executor importa só
        # `core.inputs` e não sabe abrir memória. `None` = sem reserva, e aí o
        # HP ilegível volta a significar "não sei" para sempre.
        em_batalha: Callable[[], bool | None] | None = None,
        # A VIDA DO PERSONAGEM, em %. Serve à observação de depois da morte:
        # *"dá para conferir pela vida atual do personagem, que vai estar
        # descendo também"*. É prova POSITIVA de que há outro mob batendo, e
        # chega antes do teto -- a flag só diz "ainda em batalha".
        vida_pct: Callable[[], float | None] | None = None,
        # QUANTOS MOBS VIVOS EM VOLTA -- só diagnóstico, e é o que separa "o
        # spot está vazio" de "a tecla não chega ao jogo". Ver
        # `_avisar_do_tab_mudo` e `core/vizinhanca.py`.
        mobs_por_perto: Callable[[], tuple[int, float | None]] | None = None,
        # A ESPERA DEPOIS DO TAB, agora CONFIGURÁVEL -- é a "linha 0" da macro.
        # Chega como função pelo mesmo motivo que `fonte_dos_passos` chega:
        # mudar o valor na tela com o bot rodando passa a valer na volta
        # seguinte, sem religar nada. `None` = usa `ESPERA_DEPOIS_DO_TAB`.
        espera_depois_do_tab_ms: Callable[[], int] | None = None,
        # A SEGUNDA PORTA: a barra desenhada, fração 0..1 ou `None`.
        #
        # Chega como função pelo mesmo motivo de todo o resto -- este módulo
        # importa só `core.inputs` e não sabe o que é janela, captura ou
        # `TargetHybrid`. Quem monta é o supervisor, que já tem o `hwnd` e o
        # híbrido. `None` = APP sem tela, e aí vale só a memória, como antes.
        vida_do_alvo_pela_tela: Callable[[], float | None] | None = None,
    ) -> None:
        self.input = Input(hwnd)
        self._fonte = fonte_dos_passos
        self._continuar = continuar
        self.log = log
        self._pausado = pausado
        # O pet chega como FUNÇÃO -- ver o bloco no topo do arquivo. Sem os dois
        # (leitura e tecla), o executor volta a ser exatamente o que era.
        self._pet_ativo = pet_ativo
        self._tecla_do_pet = tecla_do_pet
        # Alimentação do pet: `PetFeeder` (core) decide quando, a tecla vem daqui.
        self._tecla_do_pet_food = tecla_do_pet_food
        self._feed_every_minutes = feed_every_minutes or (lambda: 60)
        self._feed_on_start = feed_on_start
        # A ALIMENTAÇÃO INICIAL ESPERA A PRIMEIRA VOLTA. Ela era feita em
        # `rodar()`, ANTES do primeiro `antes_da_volta` -- ou seja, a única tecla
        # de comida do APP que saía com a página da barra de atalhos NÃO
        # verificada. Agora é a primeira volta que a gasta, depois da garantia.
        self._deve_alimentar_na_largada = feed_on_start
        # A GRADE VEM DO DISCO E VOLTA PARA ELE, igual ao BC. O `PetFeeder`
        # grava sozinho a cada mudança -- inclusive quando a grade só NASCE, que
        # é o caso que estava jogando o relógio fora a cada reinício.
        vence_em = None
        if grade_da_comida is not None:
            try:
                vence_em = grade_da_comida() or None
            except Exception as exc:
                log.debug("Não li a grade da comida do pet: %s", exc)
        self._pet_feeder = PetFeeder(
            vence_em=vence_em, gravar=self._montar_gravador(
                gravar_grade_da_comida))
        log.info(
            "Comida do pet: tecla=%s | grade do disco=%s | faltam %.1f min",
            tecla_do_pet_food or "-",
            "sim" if vence_em else "não (começa agora)",
            self._pet_feeder.minutos_para_alimentar(self._feed_every_minutes()),
        )
        # Chamado antes de CADA volta. Hoje é a garantia de que a barra de
        # atalhos está na página 1 -- na página errada, as MESMAS teclas da
        # sequência disparam outra coisa, e o executor não teria como perceber.
        #
        # Chega como FUNÇÃO pelo mesmo motivo que o pet: o executor importa só
        # `core.inputs` e continua assim. Quem monta o clique (ou a tecla) é o
        # supervisor, que já sabe abrir a janela do jogo.
        self._antes_da_volta = antes_da_volta
        self._conferir_saude = conferir_saude
        # Limpeza da bolsa a cada N voltas. As DUAS chegam como função, e a
        # segunda é função (e não número) pelo mesmo motivo que `fonte_dos_passos`
        # é: mudar o N na interface com o bot rodando passa a valer na volta
        # seguinte, sem religar nada.
        self._limpar_a_bolsa = limpar_a_bolsa
        self._voltas_por_limpeza = voltas_por_limpeza or (lambda: 0)
        self.limpezas = 0
        self.voltas = 0
        self.teclas_enviadas = 0
        self.invocacoes_de_pet = 0
        self.alimentacoes_de_pet = 0
        self._ultima_invocacao = 0.0
        self._avisou_pet_ilegivel = False
        # Trava de posição: campos de configuração (salvos no config.json).
        # O executor NÃO move o personagem (ecossistema cego por design).
        # Os campos existem para persistência e UI.
        self._travar_posicao = travar_posicao
        self._shuffle_apos_n_voltas = shuffle_apos_n_voltas
        self._base_pos: tuple[int, int] | None = base_pos
        # Recusas de alvo por DISTÂNCIA na rodada de aquisição em curso --
        # Recusas SEGUIDAS por distância -- ver `_alvo_longe_demais`. Zera no
        # ACEITE, e é isso que faz a válvula ser alcançável.
        self._recusas_por_distancia = 0
        # Como a volta ANTERIOR terminou. Só diagnóstico -- ver
        # `_abortar_a_volta` e `core/cadencia_da_bolsa.py`.
        self._ultimo_corte = "início"
        self._declarar_queda = declarar_queda
        # A CONTABILIDADE DO TECLADO MUDO -- ver `core/teclado_mudo.py`.
        self._teclado_mudo = teclado_mudo.TecladoMudo()
        self._cadencia_da_bolsa = cadencia_da_bolsa.CadenciaDaBolsa(self.log)
        # Função para ler posição atual (injetada pelo supervisor).
        self._posicao_atual = posicao_atual
        # Centro do minimapa para cliques de movimento.
        self._minimap_center = minimap_center
        # Estado interno da trava de posição.
        self._voltas_sem_movimento = 0
        self._ultima_posicao_conhecida: tuple[int, int] | None = None

        # A CURA. `None` quando o supervisor não montou uma -- sem leitura de
        # vida não há o que proteger, e o APP roda exatamente como antes.
        self._alvo_atual = alvo_atual
        self._id_do_alvo = id_do_alvo
        self._tecla_de_alvo = tecla_de_alvo
        self._ultimo_alvo_dito: object = object()
        self.tabs_dados = 0
        self.mortes_vistas = 0
        # A RÉGUA DO ALVO INALCANÇÁVEL. `_hp_de_referencia` é o PRIMEIRO HP
        # lido deste alvo -- é contra ele que se pergunta "tirei alguma coisa?".
        self._alvo_da_regua: int | None = None
        self._hp_de_referencia: int | None = None
        self._linhas_sem_dano = 0
        # "JÁ TIREI VIDA DESTE ALVO?" -- ver `_alvo_intocavel`. É o que
        # substituiu o portão `hp >= max_hp` e o que impede a régua de largar
        # um mob que está sendo morto.
        self._ja_tirou_vida = False
        self._alvo_sumiu_avisado = False
        self._avisou_sem_tecla_de_alvo = False
        # TECLA MORTA: contado entre VOLTAS -- ver `TABS_SEM_RESPOSTA_PARA_
        # DESISTIR`. O aviso sai uma vez por sequência, não uma por volta.
        self._tabs_sem_resposta = 0
        self._avisou_tecla_morta = False
        # De quem é o veredito guardado na reserva -- ver `_alvo_morreu`.
        self._alvo_da_reserva: int | None = None
        # O veredito da RESERVA, guardado por IDENTIDADE -- ver `_alvo_morreu`.
        self._morto_pela_reserva: int | None = None
        # O escape do alvo ILEGÍVEL -- ver `_alvo_ilegivel_demais`.
        self._alvo_ilegivel_id: int | None = None
        self._voltas_ilegiveis = 0
        # UM id (nunca uma lista) do mob que a régua largou -- ver
        # `_largar_o_alvo_inalcancavel`. Gasto na volta seguinte e apagado.
        self._inalcancavel_id: int | None = None
        # A RESERVA PELA FLAG DE COMBATE -- ver
        # `USAR_COMBATE_COMO_RESERVA_DE_MORTE`. Guarda o último estado LIDO
        # (nunca o "não sei"), que é o que permite enxergar a TRANSIÇÃO.
        self._em_batalha = em_batalha
        self._estava_em_batalha = False
        self._vida_pct = vida_pct
        self._mobs_por_perto = mobs_por_perto
        self._espera_depois_do_tab_ms = espera_depois_do_tab_ms
        # A SEGUNDA PORTA e a cadência dela -- ver `USAR_A_TELA_COMO_SEGUNDA_
        # PORTA`, `LINHAS_ANTES_DE_OLHAR_A_TELA` e `INTERVALO_MINIMO_DA_TELA`.
        self._vida_do_alvo_pela_tela = vida_do_alvo_pela_tela
        self._linha_da_rotacao = 0
        self._ultima_olhada_na_tela = 0.0
        self._linha_da_ultima_olhada = -1
        # O PEDÁGIO da morte declarada pela TELA: linhas que faltam bater cego.
        self._linhas_cegas = 0
        self.mortes_pela_tela = 0
        # URGÊNCIA: a volta seguinte pula o ciclo calmo -- ver `uma_volta`.
        self._urgencia = False
        self.urgencias = 0
        # A MORTE DO ALVO é peça COMPARTILHADA com o BC (`MorteDoAlvo`): o
        # veredito `hp <= 0` e a trava por IDENTIDADE estavam implementados aqui
        # E lá, com o mesmo nome de atributo e o mesmo comentário explicando que
        # a trava é por identidade e não por tempo. Duas cópias da mesma decisão
        # são duas chances de só uma ser corrigida.
        self._morte_do_alvo = MorteDoAlvo()
        # ABANDONOS POR INALCANÇÁVEL (o mob do penhasco). Contador próprio
        # porque ele NÃO é volta de macro e NÃO é morte -- ver `uma_volta`.
        self.alvos_inalcancaveis = 0
        self.voltas_abortadas = 0
        # A batalha da volta ANTERIOR e quantas voltas seguidas se passaram com
        # alvo e sem batalha. Os dois existem para o TAB não trocar um alvo que
        # já existe -- ver `_preciso_de_alvo`.
        self._lutava_na_volta_anterior = False
        self._voltas_com_alvo_sem_batalha = 0
        # O TAB ÚNICO e a IDEMPOTÊNCIA dele -- ver `_adquirir_alvo` e
        # `_mesmo_alvo_verificado`. `_tab_solicitado` é o PEDIDO do relógio dos
        # 4s do time (`conferir_a_parada`): o `rodar()` não aperta mais TAB
        # direto, só deixa este flag -- quem consome e aperta é a volta, como a
        # última coisa antes da linha 1 (Eixo 1). `_alvo_verificado` é o último
        # alvo VIVO confirmado `(id, hp)`, gravado no sucesso da aquisição; se o
        # alvo atual ainda é o mesmo e vivo, o TAB não sai de novo (Eixo 2).
        self._tab_solicitado = False
        self._alvo_verificado: tuple[int, int] | None = None
        self.cura = cura(self) if cura is not None else None
        self.morte = morte(self) if morte is not None else None



        # A SINCRONIA DO TIME, pela MESMA fábrica que a cura usa: ela precisa do
        # executor (dormir respeitando o Parar, ler o alvo, garantir alvo) e o
        # executor não pode conhecê-la -- ela fala com o mural, que mora em
        # `blazesbot.bot`, e este arquivo só importa `core`. `None` significa
        # "sem time", e aí o APP roda exatamente como sempre rodou.
        self.sincronia = sincronia(self) if sincronia is not None else None
        # ALVO ALIADO NÃO É ALVO. `None` = sem time, e aí a pergunta nem
        # existe. Ver `_preciso_de_alvo`.
        self._alvo_e_aliado = alvo_e_aliado

        # A FADA DO TIME: cura o time em vez de atacar.
        # Mesmo padrão da cura e da sincronia: fábrica que recebe o executor,
        # o executor não a conhece (ela fala com o mural em blazesbot.bot).
        # `None` = sem Fada, e o APP roda exatamente como antes.
        self.fada = fada(self) if fada is not None else None

    # -- espera ------------------------------------------------------------

    def _esperar(self, milissegundos: int) -> bool:
        """Espera o tempo da linha, em fatias. False = é para parar.

        CONFERE A MORTE DO ALVO DENTRO DA ESPERA, e não só entre as linhas: uma
        linha de 3000 ms sem isso faria o bot bater num cadáver por até três
        segundos. Ver `PASSO_DA_CONFERENCIA_DO_ALVO`.
        """
        restante = max(0, int(milissegundos)) / 1000.0
        desde_a_conferencia = 0.0
        while restante > 0:
            if not self._continuar():
                return False
            fatia = min(FATIA_DE_ESPERA, restante)
            time.sleep(fatia)
            restante -= fatia
            desde_a_conferencia += fatia
            if desde_a_conferencia >= PASSO_DA_CONFERENCIA_DO_ALVO:
                desde_a_conferencia = 0.0
                # A VIDA TAMBÉM SE CONFERE AQUI DENTRO -- 07/09/2026.
                #
                # Conferir só ENTRE as linhas não é vigilância: uma linha de
                # 3 s deixa 3 s de cegueira, e foi assim que um personagem foi
                # de 100% a zero em 21 s sem uma leitura no meio. Apontado pelo
                # council: *"a verificação só entre linhas não é um watchdog"*.
                #
                # O socorro NÃO corta a volta: bebe e deixa a macro seguir --
                # quem mata quem está batendo é ela. Ver `cura.socorro`.
                if self.cura is not None:
                    self.cura.socorro()
                if self._cortar_a_volta():
                    return False
        return True

    def _respiro_depois_do_tab(self) -> float:
        """O tempo da LINHA 0, em segundos. Vem da configuração.

        A tela mostra isto como a linha 0 da macro: tecla fixa (a de "próximo
        alvo", não editável) e tempo editável. Pedido do usuário em 26/08/2026:
        *"aquele 1 segundo após o tab será isso"*.

        `ESPERA_DEPOIS_DO_TAB` deixou de ser o valor e passou a ser o PADRÃO de
        quem roda sem configuração -- os testes e qualquer chamador que monte o
        executor sem a função.
        """
        if self._espera_depois_do_tab_ms is None:
            return ESPERA_DEPOIS_DO_TAB
        try:
            ms = int(self._espera_depois_do_tab_ms())
        except Exception:
            return ESPERA_DEPOIS_DO_TAB
        return max(MINIMO_DE_ESPERA_DO_APP_MS, ms) / 1000.0

    def _dormir(self, segundos: float) -> bool:
        """Espera um tempo FIXO, em fatias, respondendo ao Parar. `False` = pare.

        =================================================================
        POR QUE NÃO É `time.sleep`, E POR QUE NÃO É `_esperar`
        =================================================================

        **`time.sleep` não serve** porque a regra do projeto é que o botão de
        parar responda na hora. Os dois respiros do TAB somam 1,6 s por
        aquisição, e 1,6 s de bot mudo por mob morto é exatamente o tipo de
        espera cega que este projeto vem tirando do caminho.

        **`_esperar` também não serve**, e o motivo é sutil: ele confere a MORTE
        DO ALVO lá dentro (`_cortar_a_volta`), o que está certo no meio da macro
        e errado aqui. Durante a aquisição o alvo selecionado é justamente o
        cadáver que se está tentando largar -- `_cortar_a_volta` responderia
        `True` e o respiro devolveria "pare" no primeiro décimo de segundo.

        Então este daqui fatia e pergunta UMA coisa só: é para continuar?
        """
        restante = max(0.0, float(segundos))
        while restante > 0:
            if not self._continuar():
                return False
            fatia = min(FATIA_DE_ESPERA, restante)
            time.sleep(fatia)
            restante -= fatia
        return True

    def _esperar_cego(self, milissegundos: int) -> bool:
        """Espera o tempo da linha SEM conferir o alvo. `False` = é para parar.

        É a irmã do `_esperar`, e a diferença é o ponto: aquela pergunta "o alvo
        morreu?" a cada `PASSO_DA_CONFERENCIA_DO_ALVO`; esta não pergunta nada.
        Existe para as `LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA` — *"continua
        batendo, SEM PERGUNTAR MAIS"*.
        """
        return self._dormir(max(0, int(milissegundos)) / 1000.0)

    def _esperar_saida_da_pausa(self) -> bool:
        """Segura o laço enquanto estiver pausado. False = é para parar."""
        if self._pausado is None:
            return True
        avisou = False
        while self._pausado():
            if not self._continuar():
                return False
            if not avisou:
                avisou = True
                self.log.info("Modo APP pausado")
            time.sleep(FATIA_DE_ESPERA)
        if avisou:
            self.log.info("Modo APP retomado")
        return True

    # -- pet ---------------------------------------------------------------

    def garantir_pet(self) -> None:
        """Confere o pet ANTES dos comandos e invoca se ele tiver caído.

        Não devolve nada e nunca interrompe a macro: pet é um reforço, e não
        conseguir invocá-lo não é motivo para parar de mandar as teclas.

        As três respostas da leitura estão tratadas separadamente, e a do meio é
        a que importa -- ver o bloco no topo do arquivo. `None` significa "não
        deu para ler" e NÃO aperta nada, senão a macro apertaria a tecla do pet
        em toda volta num cliente sem leitura de memória.
        """
        if self._pet_ativo is None or not self._tecla_do_pet:
            return

        try:
            ativo = self._pet_ativo()
        except Exception:
            # Uma falha de leitura não pode derrubar a macro. O modo APP existe
            # para funcionar onde o resto não funciona.
            ativo = None

        if ativo is None:
            if not self._avisou_pet_ilegivel:
                self._avisou_pet_ilegivel = True
                self.log.info(
                    "Não consigo ler se o pet está ativo neste cliente; o modo "
                    "APP segue sem cuidar do pet."
                )
            return

        self._avisou_pet_ilegivel = False
        if ativo:
            return

        agora = time.time()
        if agora - self._ultima_invocacao < INTERVALO_ENTRE_INVOCACOES:
            # Já apertei há pouco: o pet ainda está vindo. Ver
            # `INTERVALO_ENTRE_INVOCACOES`.
            return

        self._ultima_invocacao = agora
        self.invocacoes_de_pet += 1
        self.log.info("Pet caído; invocando com a tecla %r", self._tecla_do_pet)
        self.input.key(self._tecla_do_pet)
        time.sleep(ESPERA_DEPOIS_DE_INVOCAR)

    # -- alimentação do pet ------------------------------------------------

    def _montar_gravador(
        self, gravar: Callable[[float], None] | None
    ) -> Callable[[float], None] | None:
        """Embrulha o gravador do supervisor num que NÃO LEVANTA.

        É o contrato do `PetFeeder` (ver `core/pet.py`): falha ao gravar não
        pode derrubar a macro. O pior desfecho aceitável é a grade voltar ao que
        está no disco -- que é o comportamento de antes desta mudança.
        """
        if gravar is None:
            return None

        def _seguro(vence: float) -> None:
            try:
                gravar(vence)
            except Exception as exc:
                self.log.debug("Não gravei a grade da comida do pet: %s", exc)

        return _seguro

    def feed_pet(self, force: bool = False) -> bool:
        """Alimenta o pet respeitando o intervalo configurado.

        Pet sem comida DESAPARECE sozinho -- o mesmo risco do farm da cave.
        A diferença do executor de macro é que ele é CEGO: não lê memória, não
        sabe se está montado ou em combate. A tecla de comida, apertada, é
        ignorada pelo jogo nesses casos -- e o `PetFeeder` continua contando o
        tempo normalmente. É a melhor opção disponível sem quebrar o isolamento.

        Usa o `PetFeeder` compartilhado com o BC: a decisão de QUANDO alimentar
        é idêntica, só o "como" difere (aqui é só apertar a tecla; no BC desmonta
        primeiro).
        """
        if not self._tecla_do_pet_food:
            return False

        # A LARGADA (`feed_on_start`) É COBRADA AQUI, na primeira volta que
        # chegar até este ponto -- e não em `rodar()`, antes da garantia da barra
        # de atalhos. Se a primeira volta pegar o personagem em batalha, a
        # cobrança fica para a seguinte: em combate a tecla seria ignorada.
        if self._deve_alimentar_na_largada:
            self._deve_alimentar_na_largada = False
            force = True

        intervalo = self._feed_every_minutes()
        if not self._pet_feeder.deve_alimentar(intervalo, force=force):
            return False

        self.log.info("Alimentando o pet (a cada %s min) | tecla=%s",
                      intervalo, self._tecla_do_pet_food)
        if not self.input.key(self._tecla_do_pet_food):
            # TECLA QUE O `Input` NÃO SABE TRADUZIR -- erro de configuração, não
            # situação de jogo. A grade NÃO avança: alimentar zero vezes com o
            # relógio andando é o defeito que se está consertando.
            self.log.error(
                "A tecla da comida do pet (%r) não foi reconhecida; o pet NÃO "
                "foi alimentado.", self._tecla_do_pet_food)
            return False
        # A JANELA EM QUE A AÇÃO SEGUINTE CANCELA O ITEM. Aqui a ação seguinte é
        # a primeira linha da macro, que sai em milissegundos. Ver
        # `SEGUNDOS_PARA_A_COMIDA_SER_USADA` em `core/pet.py`.
        #
        # `_dormir` E NÃO `time.sleep`: a regra do projeto é que o Parar responda
        # na hora. A grade avança DEPOIS mesmo que o Parar chegue no meio -- a
        # tecla já saiu, e não registrar transformaria um Parar em refeição
        # perdida na próxima sessão.
        self._dormir(SEGUNDOS_PARA_A_COMIDA_SER_USADA)
        # A GRADE AVANÇA a partir do vencimento, não do agora: atrasar uma
        # refeição não pode empurrar as seguintes, senão o número de refeições
        # por dia cai e o pet some por fome. O `PetFeeder` já grava no disco --
        # é o que faz a grade sobreviver ao reinício. Ver `core/pet.py`.
        self._pet_feeder.registrar_alimentacao(intervalo)
        self.alimentacoes_de_pet += 1
        return True

    # -- trava de posição ----------------------------------------------------

    def _ler_alvo(self) -> dict | None:
        """Uma leitura do alvo, protegida. `None` = sem alvo OU ilegível.

        As duas causas são separadas por quem chama, com `_ler_id_do_alvo()`:
        id `0` é "não há alvo"; id respondendo com `None` aqui é "há alvo e não
        consegui ler". Os consumidores decidem coisas OPOSTAS nos dois casos, e
        `Memory.alvo_atual()` devolve o mesmo `None` para ambos.
        """
        if self._alvo_atual is None:
            return None
        try:
            return self._alvo_atual()
        except Exception:
            return None

    def _olhar_a_tela(self) -> float | None:
        """A vida do alvo pela BARRA, respeitando a cadência. `None` = agora não.

        DUAS CONDIÇÕES, e elas valem JUNTAS -- é o *"a cada 500 ms ou a cada
        linha, o que for MAIOR"* do usuário:

          * nunca duas vezes na MESMA linha da macro;
          * nunca com menos de `INTERVALO_MINIMO_DA_TELA` entre uma e outra.

        Numa macro de linhas longas manda a linha; numa de linhas curtas manda o
        meio segundo. E antes da terceira linha da rotação ela nem é tentada --
        ver `LINHAS_ANTES_DE_OLHAR_A_TELA`.

        CADA CHAMADA QUE PASSA CUSTA UMA CAPTURA DE JANELA. É por isso que esta
        função é um portão e não um atalho.
        """
        if not USAR_A_TELA_COMO_SEGUNDA_PORTA:
            return None
        if self._vida_do_alvo_pela_tela is None:
            return None
        if self._linha_da_rotacao <= LINHAS_ANTES_DE_OLHAR_A_TELA:
            return None
        if self._linha_da_rotacao == self._linha_da_ultima_olhada:
            return None
        agora = time.time()
        if agora - self._ultima_olhada_na_tela < INTERVALO_MINIMO_DA_TELA:
            return None
        self._ultima_olhada_na_tela = agora
        self._linha_da_ultima_olhada = self._linha_da_rotacao
        try:
            return self._vida_do_alvo_pela_tela()
        except Exception:
            return None

    def _vida_do_alvo(self) -> tuple[float | None, str, dict | None]:
        """A vida do alvo em fração 0..1, e DE ONDE ela veio.

        A CASCATA, na ordem que o usuário pediu:

            1. **memória** -- exata, sem captura, e a que decide quando responde;
            2. **tela** -- a barra desenhada, quando a memória não achou a
               entidade. Ver `USAR_A_TELA_COMO_SEGUNDA_PORTA` para a medição que
               abriu esta porta;
            3. **nada** -- e aí "não sei" continua não sendo veredito.

        A FONTE VOLTA JUNTO, e não é detalhe: quem decide morte precisa saber se
        a resposta veio da tela para cobrar o pedágio das
        `LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA`.

        O `alvo` LIDO VOLTA JUNTO pelo mesmo motivo de sempre: quem chama
        precisa do nome e do id, e uma segunda leitura seria outra foto de outro
        instante respondendo à mesma pergunta.
        """
        alvo = self._ler_alvo()
        if alvo is not None:
            # `pct` JÁ VEM PRONTO de `Memory.alvo_atual()`. A conta de reserva
            # existe porque este módulo não controla quem injeta a leitura, e um
            # dicionário sem `pct` viraria "não sei" — pagando uma captura de
            # janela para descobrir o que estava na mão.
            pct = alvo.get("pct")
            if pct is None:
                hp, maximo = alvo.get("hp"), alvo.get("max_hp")
                if hp is not None and maximo:
                    pct = hp / maximo
            if pct is not None:
                return pct, "memoria", alvo
        vida = self._olhar_a_tela()
        if vida is None:
            return None, "nada", alvo
        return vida, "tela", alvo

    def _ler_em_batalha(self) -> bool | None:
        """A flag de combate, e GUARDA a última resposta que não foi "não sei".

        Guardar aqui, num lugar só, é o que faz a TRANSIÇÃO ser observável: o
        `None` de uma leitura falha não pode apagar a memória de que o
        personagem estava em batalha, senão a reserva perderia justamente o
        sinal que ela existe para ver.
        """
        if self._em_batalha is None:
            return None
        try:
            estado = self._em_batalha()
        except Exception:
            return None
        if estado is not None:
            self._estava_em_batalha = estado
        return estado

    def _zerar_a_conferencia_de_morte(self, ident: int | None) -> None:
        """Esquece o veredito da reserva quando o alvo passa a ser outro.

        O latch de `_morto_pela_reserva` vale por IDENTIDADE. Sem este reset
        ele venceria a leitura de um alvo NOVO que por acaso reusasse o id.
        """
        self._alvo_da_reserva = ident
        self._morto_pela_reserva = None

    def _alvo_morreu(self) -> bool:
        """O alvo virou cadáver? `False` também quando não deu para provar.

        =================================================================
        POR QUE ISTO DEIXOU DE SER UMA LEITURA SÓ -- 26/08/2026
        =================================================================

        CADÁVER NÃO É ALVO, e é por isso que esta pergunta nunca pôde ser
        `id == 0`: o corpo fica selecionável por 7 a 13 s depois da morte
        (medido em 20/08/2026), então o id continua respondendo. Quem decide é
        a VIDA -- e a vida vem de uma leitura que sabe faltar.

        A VERSÃO ANTERIOR PERGUNTAVA UMA VEZ E ACREDITAVA. Como
        `alvo_atual()` devolve `None` tanto para "a entidade ainda não entrou no
        array" (mob VIVO, medido: 1 em ~45) quanto para "a entidade saiu do
        array", e como `None` valia `False`, bastava uma amostra ruim para o
        bot concluir "está vivo" -- e `_garantir_alvo` lê isso como "alvo vivo,
        não mexe" e NÃO aperta o TAB. Em 25/08/2026 isso prendeu uma conta por
        28 minutos seguidos rodando a macro inteira contra o mesmo corpo, sem
        um único TAB no log.

        AGORA SÃO TRÊS CAMINHOS, e cada um responde à sua causa:

          1. **HP legível** -- `hp <= 0` é morte na primeira leitura, porque
             `alvo_atual()` já validou a struct antes de responder; `hp > 0` é
             vida, e um ponto de vida derruba qualquer suspeita anterior,
             inclusive a da reserva.
          2. **HP ilegível com alvo selecionado** -- a amostra NÃO VOTA (nem a
             favor nem contra) e a decisão passa para a RESERVA: a flag de
             combate saindo de `True` para `False` prova que a luta acabou com
             o alvo ainda selecionado, ou seja, que ele caiu. Ver
             `USAR_COMBATE_COMO_RESERVA_DE_MORTE`.
          3. **Sem alvo** (`id == 0`) -- não há morte a declarar. Quem trata é
             `_garantir_alvo`, que aperta o TAB porque não há o que largar.

        "NÃO SEI" CONTINUA VALENDO FALSE. Dizer que morreu sem prova faria o
        bot largar um mob vivo, e o mob largado continua batendo -- o defeito
        que matou o personagem. A diferença é que agora existem DUAS provas
        independentes, e "não sei" só sobrevive quando as duas faltam.
        """
        ident = self._ler_id_do_alvo()
        if ident is None:
            # SEM LEITURA DE MEMÓRIA o APP roda cego, como sempre rodou.
            return False
        if not ident:
            # Sem alvo selecionado não há cadáver para largar.
            self._zerar_a_conferencia_de_morte(None)
            return False

        if ident != self._alvo_da_reserva:
            self._zerar_a_conferencia_de_morte(ident)

        alvo = self._ler_alvo()
        if alvo is not None:
            self._alvo_sumiu_avisado = False
            hp = alvo.get("hp")
            if hp is None:
                return self._morto_pela_reserva == ident
            # O VEREDITO É DA PEÇA COMPARTILHADA (`MorteDoAlvo.veredito`), a
            # MESMA que o BC usa: `hp <= 0` é morte na primeira leitura, porque
            # `alvo_atual()` já validou a struct. Ver o bloco "O QUE É ABSOLUTO
            # NUMA CONFIRMAÇÃO DE MORTE", no topo.
            morreu = self._morte_do_alvo.veredito(alvo)
            if morreu is None:
                return self._morto_pela_reserva == ident
            if not morreu:
                # UM PONTO DE VIDA DERRUBA TODA SUSPEITA -- inclusive a da
                # reserva e o pedágio da tela. Se ele aparece vivo, ele está
                # vivo, e o que a tela ou a flag disseram antes não importa mais.
                self._morto_pela_reserva = None
                self._linhas_cegas = 0
                return False
            return True

        # ============================================================
        # A MEMÓRIA NÃO ACHOU: A TELA É A SEGUNDA PORTA
        # ============================================================
        #
        # Medição de 26/08/2026: mobs VIVOS e inteiros existem na memória e não
        # são alcançáveis pela janela varrida. Recusar alvo aqui é jogar fora mob
        # bom -- ver `USAR_A_TELA_COMO_SEGUNDA_PORTA`.
        #
        # E A TELA NÃO DECLARA MORTE NA HORA. Ela abre o pedágio das
        # `LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA`: o bot continua batendo, sem
        # perguntar mais nada, e só aceita a morte quando as linhas acabam. O
        # `EnemyDead.png` e a barra têm falso positivo MEDIDO com o mob vivo, e
        # trocar de alvo com o mob vivo foi o que matou o personagem em 25/08.
        vida = self._olhar_a_tela()
        if vida is not None and vida <= LIMIAR_DE_MORTE_NA_TELA:
            if self._linhas_cegas <= 0:
                self._linhas_cegas = LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA
                self.mortes_pela_tela += 1
                self.log.info(
                    "APP: a memória não achou a entidade e a BARRA diz que o "
                    "alvo caiu. Bato mais %s linha(s) no escuro antes de "
                    "trocar — a tela tem falso positivo medido.",
                    LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA)
            return False

        # ============================================================
        # O ALVO ESTÁ SELECIONADO E ILEGÍVEL: A RESERVA DECIDE
        # ============================================================
        #
        # O id responde, mas nenhuma entidade do array o carrega. Sem a reserva
        # este era o estado absorvente: `False` para sempre, TAB nunca, macro
        # contra o corpo até o usuário parar o bot na mão.
        if not self._alvo_sumiu_avisado:
            self._alvo_sumiu_avisado = True
            self.log.info(
                "APP: o id do alvo responde mas NENHUMA entidade do array tem "
                "esse id — o HP ficou ilegível. Passo a decidir pela flag de "
                "combate.")

        if self._morto_pela_reserva == ident:
            # LATCH POR IDENTIDADE, e ele é obrigatório: a transição
            # True -> False acontece UMA vez, e sem guardar o veredito a
            # próxima pergunta voltaria a responder "não sei" -- devolvendo o
            # bot exatamente ao estado absorvente que a reserva veio desfazer.
            return True

        if not USAR_COMBATE_COMO_RESERVA_DE_MORTE:
            return False

        estava = self._estava_em_batalha
        agora = self._ler_em_batalha()
        if estava and agora is False:
            self._morto_pela_reserva = ident
            self.log.info(
                "APP: HP do alvo ilegível, mas a batalha ACABOU com ele ainda "
                "selecionado — dou o mob por morto e vou para o próximo.")
            return True
        # A FLAG NÃO BAIXOU: não prova nada. Ou o mob está vivo, ou tem OUTRO
        # mob batendo no personagem -- e nos dois casos o certo é continuar
        # batendo. A reserva só sabe dizer "morreu"; ela nunca diz "está vivo".
        return False

    def _a_batalha_acabou(self) -> bool:
        if not USAR_A_SAIDA_DE_BATALHA_PARA_CORTAR:
            return False
        
        estava = self._estava_em_batalha
        
        # Lê estado atual SEM atualizar _estava_em_batalha da forma antiga
        try:
            estado_atual = self._em_batalha() if self._em_batalha else None
        except Exception:
            estado_atual = None

        # CORREÇÃO AQUI: Se não estava em batalha, mas AGORA está (a skill bateu), 
        # atualize a âncora para True para podermos detectar a queda futura.
        if not estava and estado_atual is True:
            self._estava_em_batalha = True
            return False
            
        if not estava:
            return False
            
        # (O resto do código segue igual)
        if estado_atual is not False:
            return False
            
        if LACO_SIMPLES:
            return True
        
        ident = self._ler_id_do_alvo()
        if ident:
            self._alvo_da_reserva = ident
            self._morto_pela_reserva = ident
        return True

    def _o_alvo_caiu_pelo_hp(self) -> bool:
        """`hp <= 0` numa leitura de MEMÓRIA. `False` = não sei ou está vivo.

        A pergunta mais barata que existe sobre o alvo, e a única que pode ser
        feita a cada linha: `alvo_atual()` já validou a struct antes de
        responder, então um `hp` legível é confiável na primeira leitura.

        ILEGÍVEL NÃO VOTA. Aqui não há cascata para a tela nem reserva: quem
        cobre o buraco é `_a_batalha_acabou`, conferida na linha acima, e é ela
        que o usuário definiu como a palavra final -- *"o sair de batalha manda
        mais, pois garante que não tem ninguém batendo no personagem"*.
        """
        alvo = self._ler_alvo()
        if alvo is None:
            return False
        hp = alvo.get("hp")
        return hp is not None and hp <= 0

    def _confirmar_a_saida_de_batalha(self) -> bool:
        """Espera a flag de combate baixar. `True` = a luta acabou mesmo.

        Chamada quando o ALVO CAI, e a pergunta que ela responde não é "o mob
        morreu?" (isso o HP já respondeu) -- é **"sobrou alguém me batendo?"**.

        ATIVA E COM TETO: devolve no instante em que a flag baixa. Estourar o
        teto não é fracasso, é o outro desfecho útil -- quer dizer que há outro
        mob em cima, e quem sabe disso não vai sentar, andar nem abrir a bolsa.
        """
        comeco = time.time()
        fim = comeco + SEGUNDOS_PARA_CONFIRMAR_A_SAIDA
        while time.time() < fim and self._continuar():
            if self._ler_em_batalha() is False:
                # QUANTO A FLAG ATRASA depois de o HP zerar. É a medida que diz
                # se os 2 s do teto são generosos ou apertados -- e o teto foi
                # posto antes de existir esta medição.
                diagnostico_fino.anotar(
                    self.log, "SAIDA DE BATALHA: a flag baixou %.2fs depois de "
                    "o alvo cair (teto %.0fs).",
                    time.time() - comeco, SEGUNDOS_PARA_CONFIRMAR_A_SAIDA)
                return True
            time.sleep(PASSO_DA_SAIDA_DE_BATALHA)
        # O ESTOURO NÃO É MAIS UM PALPITE: flag travada, leitura inválida e
        # desync caem na MESMA classe de "não baixou", e nenhuma se resolve
        # voltando a atacar. Quem separa é a tabela de entidades.
        quantos, mais_perto = vizinhanca.contar_pelo_injetado(self._mobs_por_perto)
        self.log.info(
            "APP: o alvo caiu mas continuo em batalha depois de %.1fs — %s. "
            "Volto a atacar em vez de cuidar da rotina.",
            SEGUNDOS_PARA_CONFIRMAR_A_SAIDA,
            (f"há {quantos} mob(s) vivo(s) por perto, o mais próximo a "
             f"{mais_perto:.0f}" if quantos
             else "e NÃO vejo mob vivo por perto (flag presa? leitura ruim?)"))
        return False

    def _cortar_a_volta(self) -> bool:
        """Devolve True quando a rotação deve parar AGORA porque o mob caiu.

        A MESMA MORTE NÃO SAI DUAS VEZES, e a trava é por IDENTIDADE
        (`_ultimo_alvo_morto_id`), não por tempo -- é a mesma regra do BC. O
        cadáver fica selecionável de 7 a 13 s, então uma volta que recomece em
        cima dele voltaria a contar o mesmo óbito e a repetir a mesma linha de
        log. Uma trava de RELÓGIO não serviria: curta demais conta duas vezes,
        longa demais engole a morte seguinte.

        O VEREDITO (`_alvo_morreu`) continua saindo, e é isso que importa --
        quem trava é só a CONTAGEM e o LOG. Se o veredito fosse travado junto,
        `_garantir_alvo` voltaria a ler "alvo vivo" no cadáver já contado e o
        TAB seria bloqueado de novo.
        """
        if not INTERROMPER_A_MACRO_QUANDO_O_ALVO_MORRE:
            return False
        if LACO_SIMPLES:
            # NO LAÇO SIMPLES A ÚNICA PERGUNTA É "a luta acabou?".
            # *"Só para a macro no meio se sair de batalha, não verifica mais
            # vida, não verifica mais nada."* Sem leitura de alvo, sem captura,
            # sem contagem de mortes -- a volta simplesmente termina.
            return self._a_batalha_acabou()
        # A BATALHA PRIMEIRO, porque ela responde mesmo com o HP ilegível --
        # e porque a transição é consumida na leitura.
        if not self._a_batalha_acabou() and not self._alvo_morreu():
            return False
        # A TRAVA É DA PEÇA COMPARTILHADA. `contar` devolve `False` quando esta
        # morte já saiu — e aí só o LOG e o CONTADOR calam. A volta é cortada
        # assim mesmo: bater em cadáver é tempo perdido, contado ou não.
        if not self._morte_do_alvo.contar(self._ler_id_do_alvo()):
            return True
        self.mortes_vistas += 1
        self.log.info(
            "APP: o alvo caiu no meio da macro; corto a rotação e vou para o "
            "próximo (%s morte(s) vista(s)).", self.mortes_vistas)
        return True

    def _ler_id_do_alvo(self) -> int | None:
        """O id cru, ou `None` se não deu para ler. `0` = nada selecionado."""
        if self._id_do_alvo is None:
            return None
        try:
            return self._id_do_alvo()
        except Exception:
            return None

    def _esperar_o_alvo_trocar(self, id_antes: int | None) -> int | None:
        """Espera o id ficar DIFERENTE do de antes usando polling de alta frequência.

        `None` = não trocou dentro do timeout (a tecla não pegou).
        `0` = a tecla pegou e ciclou para "nada selecionado" -- o chamador
        trata como alvo inaceitável e continua tentando.

        A PERGUNTA SUBIU PARA O `core` em 06/09/2026
        (`target_hybrid.esperar_o_alvo_trocar`) -- ela era duplicata anotada no
        CLAUDE.md, e a BC estava pagando caro por nao ter esta peca: la o TAB
        era espera cega de 750 ms. O que ficou AQUI e a politica do APP: o teto
        (`SEGUNDOS_PARA_O_ALVO_APARECER`, que e do APP e nao do core), o passo e
        o `_continuar` do laco da macro.

        Aplica um loop de verificação rápida para capturar a atualização do
        ponteiro de memória instantaneamente assim que o motor do jogo processa
        o comando de TAB.
        """
        return target_hybrid.esperar_o_alvo_trocar(
            self._ler_id_do_alvo, id_antes,
            teto=SEGUNDOS_PARA_O_ALVO_APARECER,
            passo=PASSO_DA_CONFIRMACAO_DO_TAB,
            continuar=self._continuar,
        )

    def _alvo_aceitavel(self, alvo: dict | None) -> bool:
        """Este alvo serve para COMEÇAR uma luta?

        *"Pode ser qualquer vida, o importante é ser um alvo DIFERENTE"*
        (usuário, 26/08/2026). O critério é **estar vivo**; quem garante que é
        outro mob é a IDENTIDADE, conferida em `_esperar_o_alvo_trocar`.

        O que continua recusado é o CADÁVER (`hp <= 0`), que é o único motivo
        pelo qual esta pergunta existe: o corpo entra na roda do TAB tanto
        quanto um mob vivo.

        Sem leitura de `hp`, aceita: "não sei" não pode virar recusa, senão um
        cliente com leitura ruim nunca engajaria nada -- e recusar tudo foi
        exatamente o que produziu o TAB contínuo de 26/08. Ver
        `EXIGIR_ALVO_INTEIRO` para o histórico da exigência revogada.
        """
        if alvo is None:
            return False
        hp, maximo = alvo.get("hp"), alvo.get("max_hp")
        if hp is None:
            return True
        if hp <= 0:
            return False
        # A DISTÂNCIA NÃO VETA MAIS -- HOTFIX de 06/09/2026, com conta morta.
        #
        # O TAB do jogo entrega o alvo MAIS PRÓXIMO primeiro e vai afastando a
        # cada toque. Recusar o primeiro empurrava a seleção para fora: recusa,
        # TAB, mob mais longe, recusa, TAB, mob mais longe ainda -- até o bot
        # aceitar um mob distante, correr até ele e chegar com meia dúzia de
        # outros atrás. Foi assim que a conta `BlazesAPP1` morreu.
        #
        # A régua estava brigando com a única coisa que o jogo já fazia certo. O
        # primeiro alvo vivo que o TAB traz é, por construção, o mais perto que
        # existe -- não há alvo melhor a procurar, e procurar é o próprio dano.
        #
        # A COLEIRA VIROU MEDIÇÃO: `_medir_a_corrida` continua registrando a
        # distância no log de diagnóstico, para o número sair de dado e não de
        # palpite. Ela não decide mais nada.
        self._medir_a_corrida(alvo)
        if not EXIGIR_ALVO_INTEIRO or not maximo:
            return True
        return hp >= maximo

    def _medir_a_corrida(self, alvo: dict) -> None:
        """Anota no log a que distância está o mob que acabou de ser aceito.

        SÓ MEDE. A régua já vetou alvo duas vezes neste projeto e as duas foram
        para trás -- ver `core/coleira_do_ponto.py` e o HOTFIX de 06/09/2026 em
        `_alvo_aceitavel`. O que sobrou dela é o dado: quanto o personagem
        correu, e a que distância do ponto o mob estava.
        """
        base = self._base_pos if self._travar_posicao else None
        onde_estou = None
        if self._posicao_atual is not None:
            try:
                onde_estou = self._posicao_atual()
            except Exception:
                onde_estou = None
        coleira_do_ponto.medir(alvo, base, self.log,
                               pos_do_personagem=onde_estou)

    def _comecar_a_regua(self, ident: int | None,
                         alvo: dict | None = None) -> None:
        """Fixa a referência de HP no instante em que o alvo é ADQUIRIDO.

        Se a referência só nascesse na primeira conferência, ela consumiria a
        primeira linha da macro -- e a regra do usuário (*"a vida não saiu disso
        depois da primeira e segunda linha"*) viraria três linhas na prática.
        """
        self._alvo_da_regua = ident
        self._linhas_sem_dano = 0
        self._hp_de_referencia = None
        self._ja_tirou_vida = False
        # `alvo` é a leitura QUE QUEM CHAMA JÁ TEM. Passar em vez de reler evita
        # uma volta ao processo do jogo no trecho mais sensível do laço, e evita
        # duas fotos de instantes diferentes respondendo à mesma pergunta.
        #
        # A REFERÊNCIA É GUARDADA EM FRAÇÃO (0..1), e não em pontos de vida: desde
        # 26/08/2026 a régua lê pela cascata memória → tela, e a barra desenhada
        # só sabe responder em fração. Guardar em pontos aqui e comparar com
        # fração lá faria a régua achar que o mob curou de 1,0 para 100.
        if alvo is None:
            self._hp_de_referencia = self._vida_do_alvo()[0]
            return
        pct = alvo.get("pct")
        if pct is None:
            hp, maximo = alvo.get("hp"), alvo.get("max_hp")
            pct = hp / maximo if hp is not None and maximo else None
        self._hp_de_referencia = pct

    def _alvo_intocavel(self) -> bool:
        """`LINHAS_SEM_DANO_PARA_TROCAR` linhas e o personagem NÃO entrou em
        batalha?

        =================================================================
        O CRITÉRIO MUDOU EM 01/09/2026: BATALHA, NÃO DANO
        =================================================================

        Decisão do usuário: *"em vez de ser sem dano, verifica se não entrou em
        batalha (...) se em 4 linhas não entrar na batalha, você para a macro e
        dá TAB novamente, para não ficar parado rodando a macro inteira sem ter
        entrado em batalha."*

        POR QUE É MELHOR QUE O DANO. A régua antiga comparava o HP do alvo com o
        primeiro HP lido dele, e por isso dependia de LER a vida do alvo -- que
        é justamente o que falha com o mob do penhasco, o mob longe e o alvo
        cuja entidade some do array. Ela ficava cega no caso que existia para
        pegar, e precisava de toda uma máquina em volta (`_hp_de_referencia`,
        `_ja_tirou_vida`, a régua por identidade) para não largar mob em luta
        legítima.

        A FLAG DE COMBATE responde a mesma pergunta com uma leitura só e sem
        ambiguidade: se o personagem está batendo em alguém, ele está em
        batalha. Não estar em batalha depois de quatro linhas da macro significa
        que as teclas estão indo para o vazio -- seja o mob do penhasco, seja um
        alvo fora de alcance, seja um cadáver.

        `None` NÃO LARGA. Sem leitura de combate a resposta é "não sei", e quem
        não sabe não abandona alvo -- é o mesmo contrato do resto do arquivo, e
        o que mantém o modo cego funcionando como sempre funcionou.

        O NOME FICOU, a pedido do usuário: quem lê `_alvo_intocavel` continua
        entendendo "não estou conseguindo tocar neste alvo".
        """
        if self._linha_da_rotacao < LINHAS_SEM_DANO_PARA_TROCAR:
            return False
        if self._ler_em_batalha() is not False:
            return False
        self.log.info(
            "APP: %d linhas da macro e nem entrei em batalha — as teclas estão "
            "indo para o vazio. Paro a volta e troco de alvo.",
            self._linha_da_rotacao)
        return True

    def _alvo_ilegivel_demais(self, ident: int) -> bool:
        """Este alvo está selecionado e ILEGÍVEL há voltas demais?

        =================================================================
        O ESCAPE DO ESTADO ABSORVENTE
        =================================================================

        `_alvo_morreu()` responde `False` quando não consegue provar a morte, e
        `_garantir_alvo` lê esse `False` como "alvo vivo, não mexe". Nas
        situações em que a prova NUNCA chega -- HP ilegível e a flag de combate
        presa em `True` porque OUTRO mob está batendo no personagem -- as duas
        regras se combinam num estado do qual não se sai: TAB nunca, macro
        contra o corpo para sempre.

        A saída não pode ser declarar morte (seria largar mob vivo). É declarar
        IGNORÂNCIA PERSISTENTE: passadas `VOLTAS_COM_ALVO_ILEGIVEL_PARA_TROCAR`
        voltas inteiras sem uma única leitura de HP deste alvo, o bot troca. Um
        alvo que não dá para enxergar também não dá para saber que está sendo
        morto.

        UMA LEITURA BOA ZERA TUDO. O contador só sobe quando a volta inteira
        passou sem enxergar o alvo -- flicker de uma amostra não conta.
        """
        if ident != self._alvo_ilegivel_id:
            self._alvo_ilegivel_id = ident
            self._voltas_ilegiveis = 0
        if self._ler_alvo() is not None:
            self._voltas_ilegiveis = 0
            return False
        self._voltas_ilegiveis += 1
        if self._voltas_ilegiveis < VOLTAS_COM_ALVO_ILEGIVEL_PARA_TROCAR:
            return False
        self.log.info(
            "APP: %s volta(s) com o alvo selecionado e o HP ILEGÍVEL — não dá "
            "para saber se ele está vivo. Troco de alvo.",
            self._voltas_ilegiveis)
        self._voltas_ilegiveis = 0
        return True

    def _preciso_de_alvo(self, lutando: bool) -> bool:
        """O TAB faz falta agora? `False` = já tenho alvo, não troco.

        =================================================================
        POR QUE ISTO EXISTE E FOI CORRIGIDO
        =================================================================
        O bot dava TAB desnecessário mesmo com alvo vivo selecionado, 
        pois a regra antiga dizia cegamente "se saiu de batalha, dê TAB".
        Agora ele checa a saúde do alvo antes de descartá-lo.
        """
        if lutando:
            # ZERA O CONTADOR AO ENTRAR EM BATALHA.
            self._voltas_com_alvo_sem_batalha = 0
            return False

        ident = self._ler_id_do_alvo()
        if not ident:
            return True

        # ALVO ALIADO NÃO É ALVO -- e foi a armadilha que travou o bot em campo.
        #
        # A tecla de auto-seleção deixa a conta com ELA PRÓPRIA selecionada, e
        # este método via um alvo perfeitamente válido: a conta nunca mais
        # TABava e ficava rodando a macro contra nada. Companheiro de time dá no
        # mesmo. Relatado em 01/09/2026: *"os não fadas estão se clicando e
        # rodando a macro"*.
        if self._alvo_e_aliado is not None and self._alvo_e_aliado():
            self._voltas_com_alvo_sem_batalha = 0
            return True

        # Se o alvo atual foi marcado como inalcançável (mob do penhasco), força o TAB
        if self._inalcancavel_id and ident == self._inalcancavel_id:
            return True

        # Analisa a saúde do alvo atual pela memória
        alvo = self._ler_alvo()
        alvo_confirmado_vivo = False
        alvo_confirmado_morto = False
        
        if alvo is not None:
            hp = alvo.get("hp")
            if hp is not None:
                if hp <= 0:
                    alvo_confirmado_morto = True
                else:
                    alvo_confirmado_vivo = True

        if self._lutava_na_volta_anterior:
            # O personagem acabou de sair de uma batalha.
            if alvo_confirmado_vivo:
                # O jogo auto-selecionou um mob novo (ou o atual recuperou vida/add bateu).
                # Não dou TAB, aproveito este alvo perfeitamente válido!
                self._voltas_com_alvo_sem_batalha = 0
                return False
                
            # Se for cadáver (ou se a memória falhou em ler), forçamos o TAB
            # para não ficar rodando macro contra o nada.
            return True

        # Se não lutava antes, mas o alvo atual é claramente um cadáver:
        if alvo_confirmado_morto:
            return True

        # Tenho alvo vivo (ou ilegível), mas não estou lutando.
        # Incrementa o contador de ociosidade para evitar ficar preso.
        self._voltas_com_alvo_sem_batalha += 1
        if self._voltas_com_alvo_sem_batalha >= VOLTAS_SEM_BATALHA_PARA_TROCAR:
            self.log.info(
                "APP: %d voltas com alvo e sem batalha — provavelmente não dá "
                "para alcançá-lo. Troco de alvo.",
                self._voltas_com_alvo_sem_batalha)
            self._voltas_com_alvo_sem_batalha = 0
            return True
            
        return False

    def _adquirir_alvo(self, lutando: bool) -> bool:
        """A ÚNICA função que dá TAB no laço simples -- e a última coisa antes
        da linha 1. Pet, comida, posição e limpeza da bolsa vêm TODAS antes.

        =================================================================
        O TAB DUPLO MORRE AQUI
        =================================================================

        Antes havia DUAS formas independentes de dar TAB, sem uma saber da
        outra: o relógio dos 4s do time (`conferir_a_parada`, em `rodar()`,
        com `_garantir_alvo(forcar=True)`) e o portão do começo da volta
        (`_preciso_de_alvo` -> `_tab_simples`). Quando o flag de batalha ainda
        não tinha subido na mesma volta, os dois davam TAB em fila -- ou seja,
        trocavam de alvo duas vezes, como observado no modo "copiar".

        Agora o `rodar()` só PEDE via `_tab_solicitado`; quem aperta é esta
        função, e ela decide pela memória fresca (idempotência), não por
        cronômetro cego.
        """
        # O PEDIDO DO RELÓGIO É DE UMA VOLTA. Consome ao entrar, qualquer que
        # seja o desfecho -- não pode vazar para a volta seguinte.
        solicitado = self._tab_solicitado
        self._tab_solicitado = False
        # A ABERTURA respeita o veto do "mesmo alvo": a largada acabou de
        # alinhar todo mundo no mob do líder, e um TAB aqui desfaria isso na
        # linha seguinte. O relógio NÃO é vetado -- no mesmo_alvo ele continua
        # como o `rodar()` antigo fazia, TABando quando a conta está presa há 4s.
        permitido = (self.sincronia is None
                     or self.sincronia.deve_dar_tab_na_abertura())
        # 1) FALTA ALVO: saiu de batalha, sem id, ou alvo vivo travado há 3
        #    voltas. O contador (VOLTAS_SEM_BATALHA_PARA_TROCAR) VENCE a
        #    idempotência de propósito -- é a fronteira que o usuário exigiu.
        if permitido and self._preciso_de_alvo(lutando):
            self._voltas_com_alvo_sem_batalha = 0
            return self._conseguir_o_tab()
        # 2) JÁ TENHO ALVO VIVO CONFIRMADO: 0 TAB, seja chamado uma vez ou cem.
        #    Bloqueia o TAB redundante e protege de trocar de alvo no meio da
        #    luta quando um add (segundo mob) está batendo em nós.
        if self._mesmo_alvo_verificado():
            return True
        # 3) O PEDIDO DO RELÓGIO do time (`_tab_solicitado`).
        #
        # TRAVA DE VIDA -- HOTFIX de 06/09/2026. O relógio pede TAB quando a
        # conta passa 4 s sem trocar de estado de batalha, e esse pedido chegava
        # aqui SEM conferir se já existe alvo vivo selecionado. Com um alvo bom
        # na mão, o TAB do relógio joga a seleção para o mob seguinte -- que é
        # mais longe, porque é assim que o TAB do jogo caminha.
        #
        # `_mesmo_alvo_verificado` (passo 2) deveria ter barrado isso, mas ele
        # depende de o alvo ter sido REGISTRADO na aquisição; alvo herdado de
        # outra volta, ou registrado antes de uma leitura ruim, escapava.
        # Perguntar direto ao jogo não escapa.
        if solicitado:
            if self._tenho_alvo_vivo():
                self.log.debug("APP: o relógio pediu TAB, mas há alvo vivo "
                               "selecionado. NÃO troco.")
                return True
            return self._conseguir_o_tab()
        return True

    def _tenho_alvo_vivo(self) -> bool:
        """Há alvo selecionado e vivo AGORA, pela memória? `False` = não sei.

        A pergunta mais direta que existe, e ela existe porque toda pergunta
        indireta sobre isto já falhou pelo menos uma vez: o id sozinho não
        distingue mob de cadáver (o corpo fica selecionável de 7 a 13 s), e o
        registro da aquisição não cobre alvo herdado de outra volta.

        "NÃO SEI" VALE FALSE de propósito: sem leitura, o TAB volta a ser
        permitido -- é o comportamento cego de sempre, e um TAB a mais é barato
        perto de uma macro rodando contra o vazio.
        """
        if not self._ler_id_do_alvo():
            return False
        alvo = self._ler_alvo()
        if alvo is None:
            return False
        hp = alvo.get("hp")
        return hp is None or hp > 0

    def _conseguir_o_tab(self) -> bool:
        """Aperta o TAB com a conferência certa para o caso.

        Sem as funções de alvo injetadas (APP cego), é `_tab_simples` -- o TAB
        cego de sempre, e o `False` dele significa "é para PARAR".

        Com elas, é `_garantir_alvo(forcar=True)`: um TAB que confere id+HP e,
        se o alvo atual é um vivo-travado, FORÇA a troca (preserva
        `VOLTAS_SEM_BATALHA_PARA_TROCAR`). O `False` do `_garantir_alvo` NÃO
        aborta a volta -- a docstring dele é explícita: *"esgotou as tentativas
        e não há mob vivo por perto, ele devolve False e a macro roda assim
        mesmo"*. Só o `_tab_simples` aborta, e só porque é um PARAR.
        """
        if self._alvo_atual is None or self._id_do_alvo is None:
            return self._tab_simples()          # False só para PARAR
        # PROPAGA o veredito de `_garantir_alvo`: True = alvo REAL adquirido;
        # False = sem mob vivo (só cadáver / id travado em 0). Quem chama então
        # BLOQUEIA a macro -- é o fim do vazamento que deixava a macro disparar
        # no vazio quando a aquisição falhava.
        return self._garantir_alvo(forcar=True)

    def _mesmo_alvo_verificado(self) -> bool:
        """O alvo atual ainda é o mesmo VIVO que já confirmei? `True` = não TAB.

        É a IDEMPOTÊNCIA do TAB único: impede que um segundo chamador (o
        relógio do time, que agora só PEDE) dê TAB por cima de um alvo que já
        está bom. Vive em MEMÓRIA (`_alvo_verificado`), gravado no sucesso da
        aquisição -- nada de disco, nada de `config.json`. Expira sozinho:
        quando o alvo muda ou morre, a leitura fresca deixa de bater e devolve
        `False`, liberando o TAB na hora certa.

        O alvo marcado como INALCANÇÁVEL não é protegido: é o que vamos largar
        de propósito (mob de penhasco), e bloquear seria segurar o escoamento.
        """
        if self._alvo_verificado is None:
            return False
        if (self._inalcancavel_id
                and self._alvo_verificado[0] == self._inalcancavel_id):
            return False
        alvo = self._alvo_atual() if self._alvo_atual else None
        if not self._alvo_aceitavel(alvo):
            return False                     # cadáver / sumiu -> libera o TAB
        return alvo.get("id") == self._alvo_verificado[0]

    def _tab_simples(self) -> bool:
        """Aperta a tecla de alvo. Só isso. `False` = é para parar.

        É o TAB do laço simples: **sem conferir que o id mudou, sem olhar o HP,
        sem recusar cadáver**. Quem decide se valeu é a batalha — entrou, era
        alvo; não entrou, a volta acaba fora de batalha e o TAB sai de novo.

        OS DOIS RESPIROS FICAM, e eles não são conferência: o de cima existe
        para o TAB não chegar em cima das últimas teclas da macro, e o de baixo
        é a **linha 0**, que o usuário configura na tela. Tirar os dois traria de
        volta a tecla engolida, que é defeito de campo já relatado.
        """
        tecla = ((self._tecla_de_alvo() or "").strip()
                 if self._tecla_de_alvo else "")
        if not tecla:
            if not self._avisou_sem_tecla_de_alvo:
                self._avisou_sem_tecla_de_alvo = True
                self.log.warning(
                    "APP: sem tecla de 'próximo alvo' configurada. Configure-a "
                    "em Editar conta > Teclas para o bot adquirir o alvo.")
            return True
        if not self._dormir(ESPERA_ANTES_DO_TAB):
            return False
        self.input.key(tecla)
        self.tabs_dados += 1
        return self._dormir(self._respiro_depois_do_tab())

    def _garantir_alvo(self, forcar: bool = False, urgente: bool = False) -> bool:
        """Garante um alvo VIVO antes de a macro rodar. `True` = tem alvo vivo."""
        id_antes = self._ler_id_do_alvo()
        if id_antes is None:
            return True

        if id_antes == self._inalcancavel_id and self._inalcancavel_id:
            self._inalcancavel_id = None
            forcar = True

        if id_antes and not self._alvo_morreu() and not forcar:
            if not self._alvo_ilegivel_demais(id_antes):
                # ALVO VIVO MANTIDO: zera o histórico de falhas
                self._voltas_seguidas_sem_alvo = 0
                return True

        tecla = ((self._tecla_de_alvo() or "").strip()
                 if self._tecla_de_alvo else "")
        if not tecla:
            if not self._avisou_sem_tecla_de_alvo:
                self._avisou_sem_tecla_de_alvo = True
                self.log.warning(
                    "APP: sem alvo e sem tecla de 'próximo alvo' configurada. "
                    "Configure-a em Editar conta > Teclas para o bot adquirir "
                    "o alvo sozinho.")
            return False

        if not urgente and not self._dormir(ESPERA_ANTES_DO_TAB):
            return False

        for tentativa in range(1, TENTATIVAS_DE_TAB + 1):
            if not self._continuar():
                return False
            self.input.key(tecla)
            self.tabs_dados += 1

            novo = self._esperar_o_alvo_trocar(id_antes)
            if novo is None:
                self._tabs_sem_resposta += 1
                quantos, _ = vizinhanca.contar_pelo_injetado(self._mobs_por_perto)
                self._teclado_mudo.tab_sem_resposta(time.time(),
                                                    ha_mob_por_perto=bool(quantos))
                teclado_mudo.reagir(
                    self._teclado_mudo, self.log, time.time(),
                    lambda: self.input.key("esc"), self._declarar_queda)
                if self._tabs_sem_resposta >= TABS_SEM_RESPOSTA_PARA_DESISTIR:
                    quantos, mais_perto = vizinhanca.contar_pelo_injetado(self._mobs_por_perto)
                    teclado_mudo.avisar(
                        self._teclado_mudo, self.log, time.time(), tecla,
                        self._tabs_sem_resposta, quantos, mais_perto)
                    self._avisou_tecla_morta = True
                    break 
                if not self._dormir(ESPERA_ENTRE_TABS):
                    return False
                continue

            self._tabs_sem_resposta = 0
            self._avisou_tecla_morta = False
            self._teclado_mudo.tab_respondeu()
            try:
                alvo = self._alvo_atual() if self._alvo_atual else None
            except Exception:
                alvo = None

            if not self._alvo_aceitavel(alvo):
                id_antes = novo
                if not self._dormir(ESPERA_ENTRE_TABS):
                    return False
                continue

            self._comecar_a_regua(novo, alvo)
            self.log.info("APP: alvo novo %r %s/%s — começando a macro da "
                          "linha 1.", alvo.get("nome") or "?", alvo.get("hp"),
                          alvo.get("max_hp"))
            
            self._ultimo_alvo_dito = (alvo.get("id"), alvo.get("hp"))
            self._alvo_verificado = (alvo.get("id"), alvo.get("hp"))

            # ALVO NOVO ADQUIRIDO: zera o histórico de falhas
            self._voltas_seguidas_sem_alvo = 0

            if not self._dormir(self._respiro_depois_do_tab()):
                return False
            return True

        if not self._tabs_sem_resposta:
            self.log.info(
                "APP: o TAB não trouxe mob vivo (%s salto(s)) — só cadáver por "
                "aqui. Espero a roda voltar ao começo e tento de novo NO MAIS "
                "PRÓXIMO.", tentativa)
        
        # MARGEM DE TOLERÂNCIA ANTES DO DESCANSO
        # Uso getattr para evitar crash caso a variável tenha sumido do seu __init__
        self._voltas_seguidas_sem_alvo = getattr(self, '_voltas_seguidas_sem_alvo', 0) + 1
        if self._voltas_seguidas_sem_alvo >= VOLTAS_SEM_ALVO_ANTES_DE_DESCANSAR:
            self._voltas_seguidas_sem_alvo = 0
            if not urgente:
                self._dormir(SEGUNDOS_PARA_A_RODA_REINICIAR)
                
        return False

    def _registrar_o_alvo(self) -> None:
        """Uma linha por MUDANÇA de alvo, com o HP exato da memória.

        Por mudança e não por volta: uma sessão de APP roda milhares de voltas,
        e uma linha por volta afogaria o log. Muda o alvo ou muda a vida dele,
        sai a linha.
        """
        alvo = self._ler_alvo()
        if alvo is None:
            # LEITURA ILEGÍVEL NÃO APAGA A MEMÓRIA DO QUE JÁ FOI DITO.
            #
            # Antes ela gravava `None` como "último alvo dito", e como a
            # entidade do cadáver some e volta do array, a chave alternava
            # `(id, hp) -> None -> (id, hp)` e a MESMA linha saía a cada volta.
            # No log de 25/08/2026 isso rendeu 1251 linhas idênticas de
            # "Rose Snake 0/100" contra 5 linhas de alvo novo -- o log ficou
            # ilegível justamente na sessão em que era mais preciso lê-lo.
            return
        chave = (alvo.get("id"), alvo.get("hp"))
        if chave == self._ultimo_alvo_dito:
            return
        self._ultimo_alvo_dito = chave
        hp, maximo = alvo.get("hp"), alvo.get("max_hp")
        pct = "" if not maximo or hp is None else f" ({100.0 * hp / maximo:.0f}%)"
        self.log.info("APP alvo: %s nv%s %s/%s%s",
                      alvo.get("nome") or "?", alvo.get("nivel"), hp, maximo, pct)

    def _travar_posicao_se_preciso(self) -> bool:
        """Verifica se o personagem saiu da posição base e o faz voltar andando.

        Regras:
        - Se travar_posicao está desligado, não faz nada.
        - Se não tem função de leitura de posição ou centro do minimapa, não faz
          nada (mantém o isolamento: sem memória, o APP continua cego).
        - Se a posição base não foi salva ainda, salva a posição atual como base.
        - Se o personagem está a mais de TOLERANCIA_POSICAO (1 unidade) da base,
          clica no minimapa para mandar ele voltar andando (sem montaria).
        - Após SHUFFLE_APOS_N_VOLTAS (30) voltas sem o personagem sair do lugar,
          faz um shuffle anti-AFK: move 6 pixels para o lado e volta à base.

        Devolve True se fez algum movimento (volta ou shuffle), False caso contrário.
        """
        if not self._travar_posicao:
            return False
        if self._posicao_atual is None or self._minimap_center is None:
            # Sem leitura de memória ou sem centro do minimapa: o APP continua
            # funcionando como antes (cego por design).
            return False
        if self._lutando():
            # EM BATALHA NÃO SE ANDA -- ver `ANDAR_SO_FORA_DE_BATALHA`.
            # Atravessar o ponto de farm com um mob em cima faz ele acompanhar
            # e passar por outros. Quando a luta acabar, a volta seguinte
            # devolve o personagem ao ponto.
            return False

        try:
            pos_atual = self._posicao_atual()
        except Exception:
            return False

        if pos_atual is None:
            return False

        # Se não tem posição base salva, usa a posição atual como base.
        if self._base_pos is None:
            self._base_pos = pos_atual
            self._ultima_posicao_conhecida = pos_atual
            self.log.info("Trava de posição: base inicial definida em %s", self._base_pos)
            return False

        # Calcula distância da posição base.
        dist = distancia_linear(pos_atual, self._base_pos)

        # Se o personagem moveu (mais que ruído), reseta contador de voltas sem movimento.
        if self._ultima_posicao_conhecida is not None:
            if distancia_linear(pos_atual, self._ultima_posicao_conhecida) > 1.0:
                self._voltas_sem_movimento = 0
        self._ultima_posicao_conhecida = pos_atual

        # Se está dentro da tolerância, não precisa fazer nada.
        if dist <= TOLERANCIA_POSICAO:
            self._voltas_sem_movimento += 1
            # Shuffle anti-AFK após N voltas sem movimento.
            if self._voltas_sem_movimento >= self._shuffle_apos_n_voltas:
                self._voltas_sem_movimento = 0
                return self._fazer_shuffle_anti_afk()
            return False

        # Personagem está fora da base: mandar voltar andando pelo minimapa.
        self.log.info(
            "Trava de posição: personagem em %s (distância %.1f da base %s) — "
            "mandando voltar andando",
            pos_atual, dist, self._base_pos
        )
        self._voltar_para_base(pos_atual)
        self._voltas_sem_movimento = 0
        return True

    def _voltar_para_base(self, pos_atual: tuple[int, int]) -> None:
        """Clica no minimapa para mandar o personagem andar até a base.

        Usa um clique único (repetir=False) porque no minimapa cada clique é
        uma ordem de andar calculada da posição ATUAL. Repetir perderia precisão.
        """
        if self._base_pos is None:
            return
        # A MECÂNICA MORA NO `core/` desde 07/09/2026 -- a Fada manda andar do
        # mesmo jeito, e duas cópias disto seriam duas chances de só uma ser
        # corrigida. A espera continua aqui: ela é política do APP.
        volta_ao_ponto.mandar_andar(
            pos_atual, self._base_pos, self._minimap_center,
            lambda x, y: self.input.right_click(x, y, repetir=False))
        self._esperar_chegar_na_base(SEGUNDOS_PARA_A_TRAVA_DEVOLVER)

    def _esperar_chegar_na_base(self, teto: float) -> bool:
        """Espera chegar na base PERGUNTANDO a posição. `True` = chegou.

        ERA `time.sleep(2.0)` CEGO, e isso violava a regra do projeto: onde
        havia espera cega, agora se pergunta. O gasto era fixo mesmo quando o
        personagem chegava no primeiro instante -- e, pior, o método dizia que
        tinha devolvido o personagem sem nunca ter conferido.

        O teto vira AVISO, não gasto.
        """
        fim = time.time() + teto
        while time.time() < fim and self._continuar():
            distancia = self.distancia_da_base()
            if distancia is not None and distancia <= TOLERANCIA_POSICAO:
                return True
            time.sleep(PASSO_DA_ESPERA_DA_BASE)
        return False

    def distancia_da_base(self) -> float | None:
        """A quantas unidades da base o personagem está. `None` = não sei."""
        if self._base_pos is None or self._posicao_atual is None:
            return None
        try:
            pos = self._posicao_atual()
        except Exception:
            return None
        if pos is None:
            # ÚLTIMA POSIÇÃO CONHECIDA como reserva -- decisão do usuário: numa
            # volta de macro o personagem quase não anda, então ela vale mais
            # que não responder nada.
            pos = self._ultima_posicao_conhecida
        if pos is None:
            return None
        return distancia_linear(pos, self._base_pos)

    def mandar_voltar_para_base(self) -> bool:
        """Manda o personagem andar até a base. `False` = não havia como.

        Usada pela CURA, que faz a própria espera (com teto próprio) -- por isso
        aqui só sai o clique.

        =================================================================
        QUEM JÁ ESTÁ NO PONTO NÃO RECEBE ORDEM DE ANDAR -- 26/08/2026
        =================================================================

        Defeito relatado pelo usuário: *"o primeiro uso da poção está gerando
        algum problema; ele clica na poção, CONSOME ela, mas CANCELA logo em
        seguida"*.

        Era este clique. A cura chama isto antes de beber, e ele saía **sempre**
        -- inclusive com o personagem parado em cima da base. Um clique direito
        no minimapa é uma ORDEM DE ANDAR, e uma ordem de andar pendente cancela
        a bebida no instante seguinte. O `_voltar_ao_ponto` da cura conferia a
        distância DEPOIS, via `distancia_da_base()`, e concluía *"cheguei no
        ponto inicial; vou me curar"* -- verdade, e tarde: a ordem já tinha
        saído.

        Agora a distância é conferida ANTES. Dentro da tolerância, devolve
        `True` sem clicar: **"já estou lá" é sucesso, não falha.**

        "NÃO SEI" CLICA, como sempre: sem leitura de posição não dá para provar
        que ele está no ponto, e curar longe da base é pior que um passo a mais.
        """
        if self._base_pos is None or self._minimap_center is None:
            return False

        distancia = self.distancia_da_base()
        if distancia is not None and distancia <= TOLERANCIA_POSICAO:
            return True

        pos = None
        if self._posicao_atual is not None:
            try:
                pos = self._posicao_atual()
            except Exception:
                pos = None
        pos = pos or self._ultima_posicao_conhecida
        if pos is None:
            return False
        pixel = coord_para_pixel_do_minimapa(pos, self._base_pos,
                                             self._minimap_center)
        self.input.right_click(pixel[0], pixel[1], repetir=False)
        return True

    def _lutando(self) -> bool:
        """Há luta em andamento? `False` também quando não deu para saber.

        Duas fontes, e basta UMA dizer que sim:

          * a flag de combate em `True`;
          * um alvo selecionado com vida.

        São duas porque falham em momentos diferentes -- a flag demora a subir no
        primeiro golpe, e o alvo some do array por uma leitura em ~45. Juntas,
        cobrem o buraco uma da outra.

        "NÃO SEI" VALE FALSE, e aqui isso é deliberado: quem consome esta
        resposta usa-a para SUPRIMIR uma ação (andar, dar shuffle). Se "não
        sei" suprimisse, um cliente sem leitura de memória nunca voltaria ao
        ponto e derivaria pelo mapa -- que é pior que voltar na hora errada.
        """
        if not ANDAR_SO_FORA_DE_BATALHA:
            return False
        if self._ler_em_batalha() is True:
            return True
        alvo = self._ler_alvo()
        return alvo is not None and (alvo.get("hp") or 0) > 0

    def _fazer_shuffle_anti_afk(self) -> bool:
        """Move alguns pixels para o lado e volta à base, contra o AFK.

        =================================================================
        NUNCA EM COMBATE -- conserto de 26/08/2026
        =================================================================

        Ele saía a cada `shuffle_apos_n_voltas` voltas paradas, sem perguntar o
        que estava acontecendo. Sair andando com mob em cima é o oposto do que
        se quer: o personagem larga a posição, atravessa o ponto de farm e
        chama o que estiver no caminho. Bate com o relato do usuário em 26/08 --
        *"começou a ficar andando e dando tab, chamou vários mobs e morreu"*.

        Fora de combate e sem alvo vivo, o shuffle é barato e continua valendo.

        =================================================================
        AS ESPERAS DEIXARAM DE SER CEGAS
        =================================================================

        Eram dois `time.sleep(1.0)` que não olhavam o botão de parar e não
        conferiam nada -- 2 s em que o bot ficava mudo. Agora são `_esperar`,
        que fatia, responde ao Parar e confere a morte do alvo lá dentro.
        """
        if self._base_pos is None or self._minimap_center is None:
            return False

        if self._lutando():
            return False

        self.log.info("Trava de posição: shuffle anti-AFK (volta %s)", self.voltas)

        # Um ponto deslocado no minimapa (≈ 3,5 unidades), a partir da base.
        alvo_shuffle = (self._base_pos[0] + SHUFFLE_DEFAULT_PIXELS,
                        self._base_pos[1])

        pixel_shuffle = coord_para_pixel_do_minimapa(
            self._base_pos, alvo_shuffle, self._minimap_center
        )
        self.input.right_click(pixel_shuffle[0], pixel_shuffle[1], repetir=False)
        self._esperar(int(SEGUNDOS_DO_PASSO_DO_SHUFFLE * 1000))

        pixel_base = coord_para_pixel_do_minimapa(
            alvo_shuffle, self._base_pos, self._minimap_center
        )
        self.input.right_click(pixel_base[0], pixel_base[1], repetir=False)
        self._esperar(int(SEGUNDOS_DO_PASSO_DO_SHUFFLE * 1000))

        return True

    # -- execução ----------------------------------------------------------

    def uma_volta(self) -> bool:
        """Percorre a sequência UMA vez, de cima para baixo.

        Devolve False quando foi interrompida no meio. A lista é lida uma vez por
        volta: mudança feita na interface entra na volta seguinte, e não no meio
        de uma, que deixaria a sequência pela metade.

        A ORDEM DE CADA LINHA É: manda a tecla, DEPOIS espera o tempo dela. É o
        comportamento do UoPilot e é o pedido -- usa primeiro, espera depois. A
        espera pertence à linha que acabou de ser executada, não à seguinte.

        O PET É CONFERIDO ANTES dos comandos, uma vez por volta. Uma vez por
        volta, e não uma vez só no começo: pet cai no meio da sessão, e a partir
        dali a macro rodaria sem ele até alguém perceber.

        A TRAVA DE POSIÇÃO É CONFERIDA ANTES dos comandos, uma vez por volta.
        Se o personagem saiu da base, ele é mandado de volta andando pelo minimapa.
        Após 30 voltas sem movimento, faz um shuffle anti-AFK.

        A ORDEM É: conferir pet -> alimentar -> VOLTAR AO PONTO (só se andou,
        teto de `SEGUNDOS_PARA_A_TRAVA_DEVOLVER`) -> TAB -> conferir que o id
        MUDOU -> respiro de `ESPERA_DEPOIS_DO_TAB` -> linha 1. O TAB cola na
        macro de propósito; antes ele era a primeira coisa da volta, e o bot
        adquiria o alvo para só então gastar tempo com pet e caminhada -- com o
        mob novo batendo de graça.

        ESTE É O ÚNICO LUGAR QUE ADQUIRE ALVO. A régua do inalcançável
        adquiria por conta própria de dentro do laço das linhas, e isso
        recriava exatamente o defeito acima. Hoje ela larga o mob e termina a
        volta; quem adquire é sempre o passo 4 da volta seguinte.

        SÓ O FIM NATURAL CONTA COMO VOLTA (`self.voltas`). Corte por morte e
        abandono por inalcançável vão para `voltas_abortadas`,
        `mortes_vistas` e `alvos_inalcancaveis` -- ver `_abortar_a_volta`.

        SEM ALVO VIVO A MACRO NÃO RODA. A volta devolve `False` sem mandar tecla
        nenhuma, e a seguinte tenta o TAB de novo.

        O ALVO VAI PARA O LOG, uma vez por volta e só quando MUDA. Pedido do
        usuário em 25/08/2026: *"é importante trazer os dados do target para o
        APP, para que também saibamos a vida exata do mob que está sendo
        atacado"*. Antes o APP era cego quanto a isso -- ele mandava tecla sem
        saber em que estava batendo.
        """
        passos = list(self._fonte())
        if not passos:
            return False

        if LACO_SIMPLES:
            return self._uma_volta_simples(passos)

        # ==============================================================
        # A ORDEM: CONFERE -> VOLTA AO PONTO -> TAB -> MACRO
        # ==============================================================
        #
        # O TAB COLA NA MACRO, e essa ordem é decisão do usuário em 25/08/2026:
        # *"as conferências têm que ser antes do TAB, então verifica primeiro,
        # TAB depois; o TAB tem que vir logo antes da macro"*.
        #
        # Antes o TAB era a PRIMEIRA coisa da volta, e o bot adquiria o alvo
        # para só então gastar tempo com pet e caminhada. Era o sintoma
        # relatado: mata, dá TAB, e demora para começar a bater no próximo --
        # com o mob novo batendo de graça nesse meio-tempo.
        # ==============================================================
        # URGÊNCIA: TEM OUTRO MOB BATENDO, O CICLO CALMO FICA PARA DEPOIS
        # ==============================================================
        #
        # *"Se não saiu [de batalha], pode dar tab e recomeçar a macro, pois tem
        # alguém batendo."* -- ver `_observar_depois_da_morte`.
        #
        # Pet, comida e caminhada são cuidados de quem está tranquilo. Com um mob
        # em cima eles são segundos de dano de graça, e a caminhada ainda
        # arrastaria o mob pelo ponto de farm. Nada aqui é perdido: a volta
        # seguinte, já sem urgência, faz tudo.
        # ==============================================================
        # AS CONFERÊNCIAS SÃO SÓ FORA DE BATALHA -- regra geral, 26/08/2026
        # ==============================================================
        #
        #     *"Saiu de batalha → pet → comida → voltar ao ponto → TAB → e por
        #      assim vai."*
        #
        # Antes só a caminhada era barrada em batalha. Pet e comida rodavam
        # sempre, e a comida tinha um defeito calado por causa disso: a tecla de
        # alimento é IGNORADA pelo jogo em combate (está escrito em `feed_pet`),
        # mas o `PetFeeder` registrava a refeição mesmo assim -- o pet passava
        # fome com o cronômetro dizendo que tinha comido.
        #
        # O custo é que numa luta longa o pet não é conferido até ela acabar. É
        # aceito: durante a luta o pet ou já está lá, ou não chegaria a tempo de
        # ajudar naquela luta.
        urgente = self._urgencia
        self._urgencia = False
        calmo = not urgente and not self._lutando()

        if calmo:
            self.garantir_pet()
            # Alimenta se o intervalo venceu. A ordem importa: garantir_pet
            # garante que o pet está invocado ANTES de tentar alimentar -- pet
            # caído não come alimento.
            self.feed_pet()

        # VOLTA AO PONTO INICIAL, e só se andou. Vem antes do TAB porque o
        # usuário quer o personagem parado no ponto dele antes de a luta
        # começar: *"a ideia é só que o personagem não fique andando pelo
        # mapa"*. A espera pela chegada tem teto de
        # `SEGUNDOS_PARA_A_TRAVA_DEVOLVER`, e passado ele o bot segue de
        # qualquer jeito -- *"não precisa ser perfeito"*.
        #
        # NÃO EM BATALHA (ver `ANDAR_SO_FORA_DE_BATALHA`) e não na urgência. A
        # guarda vive TAMBÉM dentro do método, de propósito: ele é a única coisa
        # aqui que MOVE o personagem, e não pode depender de quem o chama.
        if calmo:
            self._travar_posicao_se_preciso()

        # ==============================================================
        # SEM ALVO VIVO, A MACRO NÃO RODA
        # ==============================================================
        #
        # *"Caso o mob esteja morto não faz sentido rodar a macro, tem que ir
        # para o próximo MOB; só vale a pena rodar macro em mob vivo."*
        #
        # Isto REVERTE uma decisão anterior ("o TAB não bloqueia a volta"), que
        # se apoiava em macros de buff ou pesca. O usuário confirmou que a macro
        # do APP é SÓ ATAQUE -- e aí rodar sem alvo é desperdício puro, e é o
        # que produz a mensagem de "skill inválida" na tela do jogo.
        if not self._garantir_alvo(urgente=urgente):
            time.sleep(ESPERA_SEM_ALVO)
            return False
        self._registrar_o_alvo()

        self._linha_da_rotacao = 0
        for passo in passos:
            if not self._continuar():
                return False
            if not self._esperar_saida_da_pausa():
                return False
            self._linha_da_rotacao += 1

            # ==========================================================
            # O PEDÁGIO DA MORTE DECLARADA PELA TELA
            # ==========================================================
            #
            # *"Continua batendo, sem perguntar mais, só apenas bater cego até
            # as 3 próximas linhas."* Aqui a linha é gasta e nada é conferido --
            # o `_cortar_a_volta` fica de fora de propósito, porque perguntar
            # de novo é exatamente o que "bater cego" não faz.
            #
            # SAIR DE BATALHA CORTA ASSIM MESMO, e essa é a única exceção. É
            # regra geral do usuário: *"se saiu de batalha, é garantido que
            # matou e não tem outro mob batendo"* — e nesse caso as linhas que
            # sobram do pedágio não compram mais nada.
            if self._linhas_cegas > 0:
                self._linhas_cegas -= 1
                if self._a_batalha_acabou():
                    self._linhas_cegas = 0
                    self.log.info("APP: saí de batalha durante as linhas no "
                                  "escuro — o alvo caiu mesmo. Vou ao próximo.")
                    return self._abortar_a_volta(morreu=True)
                if self._linhas_cegas == 0:
                    self.log.info("APP: bati as linhas no escuro; dou o alvo "
                                  "por morto e vou ao próximo.")
                    return self._abortar_a_volta(morreu=True)
                self.input.key(passo.key)
                self.teclas_enviadas += 1
                if not self._esperar_cego(passo.delay_ms):
                    return False
                continue
            # ANTES DE CADA TECLA: se o mob caiu, a linha seguinte bateria num
            # cadáver. O `_esperar` confere de novo lá dentro.
            if self._cortar_a_volta():
                return self._abortar_a_volta(morreu=True)
            self.input.key(passo.key)
            self.teclas_enviadas += 1
            if not self._esperar(passo.delay_ms):
                # `_esperar` devolve False tanto para "é para parar" quanto para
                # "o alvo caiu". A diferença é o `continuar()`: parada de
                # verdade encerra o laço lá em cima de qualquer jeito.
                if self._continuar():
                    return self._abortar_a_volta(morreu=True)
                return False

            # A RÉGUA DO INALCANÇÁVEL, depois de CADA linha. Ver
            # `_alvo_intocavel` e `LINHAS_SEM_DANO_PARA_TROCAR`.
            #
            # ELA ABORTA, E NÃO ADQUIRE -- conserto de 26/08/2026. Antes ela
            # chamava `_garantir_alvo(forcar=True)` DAQUI, de dentro do laço
            # das linhas: o alvo novo era adquirido no meio da volta e só então
            # a volta seguinte gastava pet, comida e até 2 s de caminhada antes
            # da linha 1 -- com o mob recém-chamado batendo de graça o tempo
            # todo. É o mesmo defeito que a reordenação de 25/08 tinha
            # consertado, reintroduzido por uma porta lateral.
            #
            # Agora existe UM só lugar que adquire alvo, e ele é o passo 4 da
            # ordem da volta. Aqui a volta apenas termina.
            if self._alvo_intocavel():
                self.alvos_inalcancaveis += 1
                self._largar_o_alvo_inalcancavel()
                return self._abortar_a_volta(motivo="alvo inalcançável")

        # =================================================================
        # A ÚNICA VOLTA QUE CONTA
        # =================================================================
        #
        # `self.voltas` é rotação COMPLETA de macro no MESMO mob, e só isso.
        # Ela só é incrementada aqui, no fim natural do laço.
        #
        # Antes, TODOS os caminhos de saída incrementavam -- inclusive o corte
        # por morte e o abandono do mob do penhasco. Isso contaminava os dois
        # consumidores do contador: a limpeza de bolsa (`voltas % a_cada`) e o
        # shuffle anti-AFK, que passavam a disparar cedo demais num ponto de
        # farm com muita morte. Decisão do usuário em 26/08/2026: *"a contagem
        # de voltas não deve levar em consideração os mobs que não conseguir
        # atacar como os do penhasco"*.
        self.voltas += 1
        return True

    def _uma_volta_simples(self, passos: list) -> bool:
        """UMA volta do laço simples — ver `LACO_SIMPLES` no topo do arquivo.

        =================================================================
        O LAÇO INTEIRO
        =================================================================

            FORA de batalha  -> pet, comida, voltar ao ponto, TAB, roda a macro
            EM batalha       -> roda a macro de novo, sem TAB e sem conferência
            saiu de batalha  -> corta a macro no meio, volta ao topo
        """
        lutava_antes = self._estava_em_batalha
        # MORRI? A PERGUNTA VEM ANTES DE TUDO -- 07/09/2026.
        #
        # Ela era conferida só DENTRO do laço das linhas, e morto não consegue
        # adquirir alvo: a volta abortava na aquisição e nunca chegava às
        # linhas. Uma conta ficou 96 minutos morta, apertando TAB a cada 2 s,
        # pedindo cura e "regenerando sentada com a vida em 0%", sem o ciclo de
        # morte disparar uma vez. Detalhe em `docs/decisoes/morte-no-app.md`.
        if self.morte is not None and self.morte.estou_morto():
            if not self.morte.resolver():
                return False
            return self._abortar_a_volta(motivo="morri (prelúdio)")

        lutando = self._ler_em_batalha() is True

        if not lutando:
            self.garantir_pet()
            self.feed_pet()
            self._travar_posicao_se_preciso()
            self._limpar_a_bolsa_se_for_a_hora()
            
            permitido = (self.sincronia is None
                            or self.sincronia.deve_dar_tab_na_abertura())
            if permitido:
                # O motor nativo do bot (_garantir_alvo) já cuida de dar TAB e ciclar se precisar.
                if not self._adquirir_alvo(lutando):
                    # ISTO TAMBÉM É UMA VOLTA ABORTADA -- 06/09/2026.
                    #
                    # Era a única saída do laço que não incrementava NADA, e por
                    # isso a mais perigosa: enquanto o TAB não trazia alvo, todo
                    # contador do executor ficava congelado, e junto com ele
                    # qualquer cadência ancorada neles. Foi assim que a limpeza
                    # de bolsa entrou em rajada -- 401 dos 407 avisos daquele
                    # dia dizem exatamente `último corte: sem alvo`.
                    self._ultimo_corte = "sem alvo"
                    self.voltas_abortadas += 1
                    time.sleep(ESPERA_SEM_ALVO)
                    return False

                # ===============================================================
                # EIXO 2: O PORTÃO DE BLOQUEIO DA MACRO (Execution Gate)
                # ===============================================================
                # Aqui está a trava absoluta. Não importa se o TAB foi dado ou não,
                # a macro SÓ PODE RODAR se houver um alvo, e ele precisa estar VIVO.
                alvo = self._ler_alvo()
                if alvo is not None:
                    ident = alvo.get("id", 0)
                    hp = alvo.get("hp")
                    
                    # Se não tem ID, ou se tem HP legível e está morto (cadáver)
                    if ident == 0 or (hp is not None and hp <= 0):
                        self.log.debug("APP: Execution Gate bloqueou a macro. Alvo ausente ou morto (ID: %s, HP: %s).", ident, hp)
                        # Engana a validação dizendo que estávamos lutando para FORÇAR
                        # o bot a dar um TAB imediato no início da próxima volta.
                        self._lutava_na_volta_anterior = True
                        self._ultimo_corte = "portão: alvo ausente ou morto"
                        self.voltas_abortadas += 1
                        time.sleep(ESPERA_SEM_ALVO)
                        return False

        self._lutava_na_volta_anterior = lutando or lutava_antes
        cega = self.sincronia is not None and self.sincronia.volta_cega()
        comeco_da_volta = time.time()

        for i, passo in enumerate(passos):
            if not self._continuar():
                return False
            if not self._esperar_saida_da_pausa():
                return False
            
            # A SAÍDA DE BATALHA MANDA MAIS QUE O HP, e é por isso que ela
            # vem primeiro. Decisão do usuário em 06/09/2026: *"se ainda diz
            # 'mob vivo' mas saiu de batalha é porque a leitura está errada, e
            # o sair de batalha manda mais, pois garante que não tem ninguém
            # batendo no personagem"*.
            if self._a_batalha_acabou():
                self.log.warning(
                    "O mob morreu durante a execução da macro. Encerrando a "
                    "volta para evitar desperdício.")
                self.voltas += 1
                return self._abortar_a_volta(motivo="mob morreu")

            # O ALVO CAIU PELO HP -- fonte primária desde 06/09/2026.
            #
            # É SÓ MEMÓRIA, e isso é o ponto: `_alvo_morreu` (o veredito
            # completo, usado na aquisição) cai na cascata da TELA quando o HP
            # está ilegível, e a tela custa uma captura por consulta. Dentro da
            # volta a pergunta é a barata: *o HP legível diz zero?* A reserva
            # para o HP ilegível já está na linha acima -- é a saída de batalha,
            # que o usuário definiu como a palavra final.
            #
            # Confirmada a queda, a conferência ATIVA da saída de batalha diz o
            # que fazer a seguir -- ver `_confirmar_a_saida_de_batalha`.
            if self._o_alvo_caiu_pelo_hp():
                self.log.info("APP: o alvo caiu (HP) na linha %d — encerro a "
                              "volta.", i + 1)
                self.mortes_vistas += 1
                self.voltas += 1
                self._confirmar_a_saida_de_batalha()
                return self._abortar_a_volta(motivo="alvo caiu (HP)")
            
            if self.sincronia is not None:
                linha = self.sincronia.linha_a_enviar(i, passo.delay_ms)
                if linha is None:
                    return False
                if linha < 0:
                    return self._abortar_a_volta(motivo="time: volta vetada")
                if not (0 <= linha < len(passos)):
                    self.log.warning(
                        "Time: linha %d fora da macro (%d linhas) -- encerro a "
                        "volta em vez de repetir tecla.", linha, len(passos))
                    return self._abortar_a_volta(motivo="time: linha fora")
                passo = passos[linha]

            # ALVO ZERADO NO MEIO DA MACRO -- decisão do usuário em
            # 01/09/2026: *"a cada linha deve verificar se o target_id != 0;
            # caso for 0 ela vai ser interrompida e recomeçar"*.
            #
            # `TARGET_ID` em zero é o jogo dizendo "não há nada selecionado".
            # Acontece no meio da volta quando o mob morre e o cliente limpa o
            # alvo, quando ele some de vista, ou quando uma janela rouba a
            # seleção -- e todas as linhas que sobram sairiam para o vazio.
            #
            # É A LEITURA MAIS BARATA DO BOT (~1 µs, quatro bytes), e por isso
            # cabe a cada linha, ao contrário da régua da tela.
            #
            # `None` NÃO INTERROMPE: sem leitura a resposta é "não sei", e o
            # modo cego roda a macro inteira como sempre fez.
            # MORRI? Nada do que vem depois da linha importa -- e até
            # 04/09/2026 o APP nem perguntava: a macro seguia apertando tecla
            # contra um cadáver. O ciclo é de `bot/morte.py`; aqui só se pergunta.
            if self.morte is not None and self.morte.estou_morto():
                if not self.morte.resolver():
                    return False
                return self._abortar_a_volta(motivo="morri")

            # VIDA CRÍTICA NO MEIO DA MACRO -- 07/09/2026.
            #
            # `cura.cuidar()` roda UMA vez por rotação, e uma rotação chega a
            # 23 s. Em 07/09 um personagem saiu de 100% e morreu em 21 s, com
            # seis mobs em cima, sem uma única leitura de vida no caminho: a
            # rotação não tinha terminado.
            #
            # A pergunta custa uma leitura de memória (~1 µs), o mesmo preço do
            # `TARGET_ID` logo abaixo, e só dispara o socorro -- não interrompe
            # a volta, não anda e não senta. Ver `cura.socorro`.
            if self.cura is not None:
                self.cura.socorro()

            if self._ler_id_do_alvo() == 0:
                self.log.info("APP: fiquei sem alvo na linha %d — corto a volta "
                              "e pego outro.", i + 1)
                return self._abortar_a_volta(motivo="alvo zerado")


            self.input.key(passo.key)
            self.teclas_enviadas += 1
            
            espera = passo.delay_ms
            if self.sincronia is not None:
                espera = self.sincronia.espera_da_linha(passo.delay_ms)
                
            if not (self._esperar_cego(espera) if cega else self._esperar(espera)):
                if self._continuar():
                    self.voltas += 1
                    return self._abortar_a_volta(motivo="pausa/parada")
                return False

        self.voltas += 1
        self._ultimo_corte = "volta completa"
        diagnostico_fino.anotar(
            self.log, "VOLTA completa em %.1fs (%d linha(s)).",
            time.time() - comeco_da_volta, len(passos))
        return True

    def _abortar_a_volta(self, morreu: bool = False,
                         motivo: str = "?") -> bool:
        """A volta terminou ANTES do fim da sequência.

        Devolve `True` porque a interrupção é normal e o laço de `rodar()` deve
        seguir para a próxima -- o `False` é reservado para "é para parar".

        `morreu=True` abre a OBSERVAÇÃO: ver `_observar_depois_da_morte`.

        `motivo` NÃO muda nada: ele só fica guardado para o log da cadência da
        bolsa dizer POR QUE o contador de voltas completas não andou. Ver
        `core/cadencia_da_bolsa.py`.

        =================================================================
        QUEM CONTA COMO VOLTA NÃO SE DECIDE AQUI -- E OS DOIS LAÇOS DIFEREM
        =================================================================

        Esta função só incrementa `voltas_abortadas` (e guarda o `motivo`). `self.voltas` é problema
        de quem chama, e a regra NÃO é a mesma nos dois laços:

          `uma_volta` (complexo, `LACO_SIMPLES = False`)
              só o fim natural conta. Corte por morte e abandono por
              inalcançável ficam de fora.

          `_uma_volta_simples` (o que roda hoje)
              o corte por BATALHA ENCERRADA conta, o corte pelo TIME não.
              Decisão do usuário em 01/09/2026: *"caso entrou em batalha deve
              contar mais 1 volta"*. `_a_batalha_acabou` exige a transição
              "estava em batalha -> saiu", então esse corte é sempre um mob no
              chão -- uma volta que produziu loot. E `voltas` decide UMA coisa
              só: a hora de limpar a bolsa. Não contar a matança faria a
              limpeza atrasar justamente na conta que mata mais rápido.

        Travado por `tests/test_laco_simples_do_app.py` (as duas metades) e por
        `tests/test_tab_no_app.py` (o contrato do laço complexo).
        """
        self._ultimo_corte = motivo
        self.voltas_abortadas += 1
        diagnostico_fino.anotar(self.log, "VOLTA cortada: %s.", motivo)
        if morreu and not LACO_SIMPLES:
            self._observar_depois_da_morte()
        return True

    def _observar_depois_da_morte(self) -> bool:
        """Matei o mob. A LUTA acabou junto? `True` = não, e isso é urgência.

        =================================================================
        DUAS PERGUNTAS QUE ESTAVAM GRUDADAS
        =================================================================

        *"A vida ir a zero nós usamos para ANALISAR O MOB e saber se já matamos
        ele (...) então zerou a vida, analisa por 3 segundos: se não saiu, pode
        dar tab e recomeçar a macro, POIS TEM ALGUÉM BATENDO."*

        "Aquele mob morreu?" quem responde é o HP dele. "A luta acabou?" quem
        responde é a flag de combate. O bot tratava as duas como uma só e por
        isso ia fazer o ciclo calmo -- pet, comida, caminhada, respiros -- com um
        segundo mob batendo nas costas.

        DOIS SINAIS, E O SEGUNDO CHEGA ANTES:

          * a **flag** ainda em `True` no fim do teto — diz "ainda em batalha",
            e só isso;
          * a **vida do personagem CAINDO** — *"dá para conferir pela vida atual
            do personagem, que vai estar descendo também"*. É prova POSITIVA de
            que há dano entrando, e não precisa esperar o teto: qualquer queda
            encerra a observação na hora.

        O TETO É AVISO, NÃO GASTO: a morte limpa sai no instante em que a flag
        baixa, e custa um décimo de segundo.
        """
        vida_antes = self._ler_vida()
        fim = time.time() + SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE
        while time.time() < fim and self._continuar():
            if self._ler_em_batalha() is False:
                # A LUTA ACABOU JUNTO COM O MOB. Ciclo calmo, como sempre.
                return False
            agora = self._ler_vida()
            if (vida_antes is not None and agora is not None
                    and agora < vida_antes):
                return self._urgir(
                    "APP: matei o mob e minha vida caiu de %.0f%% para %.0f%% "
                    "— tem OUTRO mob batendo. Pego ele agora." % (
                        vida_antes, agora))
            time.sleep(PASSO_DA_CONFERENCIA_DO_ALVO)

        if self._ler_em_batalha() is False:
            return False
        if self._em_batalha is None:
            # SEM LEITURA DE BATALHA não há o que observar, e inventar urgência
            # aqui faria o bot pular pet, comida e caminhada em TODA morte.
            return False
        return self._urgir(
            "APP: matei o mob mas continuo em batalha depois de %.0fs — tem "
            "OUTRO mob batendo. Pego ele agora, sem o ciclo calmo."
            % SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE)

    def _urgir(self, mensagem: str) -> bool:
        """Marca a volta seguinte como URGENTE e diz por quê, uma vez."""
        self.urgencias += 1
        self._urgencia = True
        self.log.info("%s", mensagem)
        return True

    def _ler_vida(self) -> float | None:
        """A vida do personagem em %, protegida. `None` = não sei."""
        if self._vida_pct is None:
            return None
        try:
            return self._vida_pct()
        except Exception:
            return None

    def _largar_o_alvo_inalcancavel(self) -> None:
        """Marca ESTE alvo para o passo do TAB não o respeitar na volta seguinte.

        Sem isto o abandono seria um laço: o mob do penhasco continua VIVO e
        selecionado, então o portão de `_garantir_alvo` ("alvo vivo, não mexe")
        o aceitaria de novo, a macro rodaria outras
        `LINHAS_SEM_DANO_PARA_TROCAR` linhas contra ele, e a régua redescobriria
        o que já sabia -- para sempre.

        NÃO É UMA LISTA DE IGNORADOS, e a diferença importa. É UM id, gasto na
        primeira vez que serve e apagado em seguida -- decisão do usuário:
        *"caso volte é só identificar novamente depois da segunda linha; não
        precisa guardar nada, pois os IDs podem mudar e acabar percebendo
        errado"*. Se o TAB voltar a cair neste mesmo mob mais tarde, ele ganha
        uma avaliação nova e inteira.

        E NÃO APERTA TECLA NENHUMA DAQUI. Existe UM só lugar que adquire alvo, e
        é o passo 4 da volta -- com a conferência de que o id MUDOU, o respiro
        de `ESPERA_DEPOIS_DO_TAB` e a régua recomeçada. Apertar o TAB aqui
        entregaria à volta seguinte um alvo que ninguém conferiu.
        """
        self._inalcancavel_id = self._ler_id_do_alvo()

    def _limpar_a_bolsa_se_for_a_hora(self) -> None:
        """Manda limpar quando a cadência disser que é hora.

        A RÉGUA E O DIAGNÓSTICO MORAM EM `core/cadencia_da_bolsa.py` -- é lá que
        está escrito por que ela se repete quando a volta é cortada, e é lá que
        sai o aviso que nomeia a causa na hora.

        A limpeza chega como FUNÇÃO INJETADA, pelo mesmo motivo do pet: este
        executor importa só `core.inputs`. Ele não sabe o que é inventário,
        template ou `BotContext`.

        COMPLEMENTO QUE NUNCA DERRUBA A MACRO: qualquer falha vira aviso. O modo
        APP roda por horas sozinho, e parar por causa de uma limpeza seria
        trocar o problema pequeno (bolsa com lixo) pelo grande (macro parada).
        """
        if self._limpar_a_bolsa is None:
            return
        # A CADÊNCIA CONTA TENTATIVAS, NÃO VOLTAS COMPLETAS -- 06/09/2026.
        #
        # Ancorada só nas completas, ela congelava junto com elas: metade das
        # voltas aborta em farm normal (285 completas contra 289 abortadas numa
        # sessão medida), e quando a aquisição para de trazer alvo NENHUMA
        # completa. "A cada N voltas" virava "enquanto o contador não andar".
        #
        # Somar as abortadas é o que garante que a cadência SEMPRE anda -- e,
        # com o conserto acima, não existe mais saída do laço que não conte.
        tentativas = self.voltas + self.voltas_abortadas
        if not self._cadencia_da_bolsa.deve_limpar(
                voltas=tentativas, abortadas=self.voltas_abortadas,
                a_cada=self._voltas_por_limpeza(),
                motivo_do_corte=self._ultimo_corte):
            return
        try:
            self.limpezas += 1
            resultado = self._limpar_a_bolsa()
        except Exception as exc:
            self.log.warning("Limpeza da bolsa falhou: %s", exc)
            return

        # A BOLSA É A SEGUNDA TESTEMUNHA do teclado mudo. Um TAB sem efeito
        # pode ser circunstância do jogo; a tecla de inventário TAMBÉM sem
        # efeito, no mesmo período, é entrada inoperante. Ver
        # `core/teclado_mudo.py` -- e as 9 h 30 min de 07/09/2026.
        if resultado == teclado_mudo.BOLSA_NAO_ABRIU:
            self._teclado_mudo.bolsa_nao_abriu(time.time())
        elif resultado is not None:
            self._teclado_mudo.bolsa_abriu()

    def rodar(self) -> None:
        """Laço contínuo: volta após volta, até `continuar()` devolver False."""
        self.log.info("Modo APP iniciado -- %s", self.resumo())
        vazio_avisado = False

        # A ALIMENTAÇÃO INICIAL NÃO ACONTECE MAIS AQUI -- 27/08/2026.
        #
        # Ela era o ÚNICO aperto de tecla do APP que saía antes do primeiro
        # `antes_da_volta`, ou seja com a página da barra de atalhos não
        # verificada. Na página errada o mesmo '6' dispara outra coisa, e o
        # executor não tem como perceber.
        #
        # Agora quem a gasta é a primeira volta, DEPOIS da garantia da barra:
        # `_deve_alimentar_na_largada` sobrevive até o primeiro `feed_pet`.
        # `feed_on_start` continua significando o mesmo do BC -- alimenta na
        # largada em vez de esperar um intervalo inteiro.

        while self._continuar():
            if not list(self._fonte()):
                # Sem linha nenhuma não há o que mandar. Avisa uma vez e continua
                # conferindo: a pessoa pode estar configurando agora, e sair do
                # laço obrigaria a religar o modo.
                if not vazio_avisado:
                    vazio_avisado = True
                    self.log.warning(
                        "Modo APP ligado sem nenhuma tecla configurada; nada a "
                        "enviar. Preencha as linhas em Editar conta > APP."
                    )
                time.sleep(0.25)
                continue
            vazio_avisado = False
            # A LARGADA DO TIME -- depois da barra de atalhos e antes da volta.
            #
            # Depois da barra porque o alinhamento pode dar TAB, e TAB na página
            # errada da hotbar dispara outra coisa. Antes da volta porque é o
            # único ponto em que todas as contas do time estão no MESMO lugar da
            # sequência.
            #
            # `False` aqui é SEMPRE "é para parar" -- nunca "não consegui
            # sincronizar". Falha de sincronia deixa a conta ir sozinha, que é a
            # regra do time: ninguém fica parado esperando.
            if self.sincronia is not None:
                if not self.sincronia.esperar_a_largada():
                    break
                # 4 s sem trocar de estado de batalha: hora de TAB. NÃO apertado
                # aqui -- quem aperta é `_adquirir_alvo`, como a ÚLTIMA coisa
                # fora de batalha, logo antes da linha 1. Aqui o relógio só
                # PEDE (flag consumido por uma volta). Foi o fim do TAB duplo:
                # antes este TAB direto e o portão do começo da volta podiam dar
                # dois TABs em fila quando o flag de batalha ainda não subira.
                self._tab_solicitado = self.sincronia.conferir_a_parada()
            if self._antes_da_volta is not None:
                try:
                    self._antes_da_volta()
                except Exception as exc:
                    # COMPLEMENTO: sem ele a macro roda como sempre rodou.
                    self.log.warning("Antes da volta: %s", exc)
            self.uma_volta()
            # DEPOIS da volta, e sem `except`: se caiu, a exceção sobe e o
            # supervisor faz o relogin. Ver o parâmetro no `__init__`.
            if self._conferir_saude is not None:
                self._conferir_saude()

            # A CURA VEM AQUI, e a ordem é decisão do usuário: *"ao terminar a
            # macro você vai verificar a vida"*. Depois da conferência de saúde
            # (personagem caído não se cura) e ANTES da limpeza da bolsa — com
            # 30% de vida, apagar lixo primeiro é tempo que ele não tem.
            #
            # A CURA NÃO CONTA COMO VOLTA: `self.voltas` é rotação de macro, e
            # as cadências de limpeza e de shuffle foram pensadas em cima de
            # trabalho de macro, não de tempo parado se curando.
            if self.cura is not None:
                self.cura.cuidar()

            # A FADA VEM AQUI, depois da cura pessoal e ANTES da limpeza da bolsa.
            # A ordem é decisão do usuário (docs/fada.md): a Fada só cura quando
            # a fila não está vazia; fila vazia -> cuida da própria mana.
            if self.fada is not None:
                self.fada.cuidar()

        self.log.info(
            "Modo APP encerrado -- %s volta(s) completa(s), %s abortada(s), "
            "%s morte(s) vista(s), %s alvo(s) inalcançável(is), "
            "%s vez(es) com outro mob batendo, %s tecla(s) enviada(s), "
            "%s TAB(s), %s invocação(ões) de pet, %s alimentaç(ões) de pet",
            self.voltas, self.voltas_abortadas, self.mortes_vistas,
            self.alvos_inalcancaveis, self.urgencias, self.teclas_enviadas,
            self.tabs_dados, self.invocacoes_de_pet, self.alimentacoes_de_pet,
        )

    # -- diagnóstico -------------------------------------------------------

    def resumo(self) -> str:
        passos = list(self._fonte())
        if not passos:
            return "nenhuma tecla configurada"
        desenho = " -> ".join(f"{p.key}({p.delay_ms}ms)" for p in passos)
        total = sum(max(0, int(p.delay_ms)) for p in passos)
        linhas = f"{len(passos)} linha(s), volta de {total}ms: {desenho}"
        if self._tecla_do_pet_food:
            linhas += f", pet_a cada {self._feed_every_minutes()}min"
        if self._travar_posicao:
            linhas += ", trava de posição"
        return linhas
