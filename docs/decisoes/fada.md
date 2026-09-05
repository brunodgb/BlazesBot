# A Fada — a conta que cura o time em vez de atacar

> **Pedido do usuário em 28/08/2026.** *"vamos ter uma nova flag dentro do APP
> 'Fada': caso marque, aquela conta será considerada como fada e ao adicioná-la
> em um time ela não irá atacar, mas sim curar os aliados. Tendo uma fada no
> time, não precisa mais usar poção de cura."*
>
> A regra que não pode ser violada está em `docs/INVARIANTES.md`, seção "A Fada".
> Aqui mora o **porquê** — e o que foi recusado.

## O desenho, em uma frase

A vítima **avisa** (pela memória, que ela lê de si mesma); a Fada **clica no
retrato** do aliado no painel de time, **confere pelo `TARGET_ID`** que aquele
clique de fato selecionou quem pediu, e cura até o alvo combinado. Fila por
ordem de chegada. Sem Fada de pé, a poção volta a valer.

## O que foi decidido, e o que foi RECUSADO

| decisão | o que foi recusado, e por quê |
|---|---|
| **A vítima avisa** — ela publica no mural "preciso de cura, estou em 28%". | A Fada varrer as barras de vida do painel na tela. A vítima sabe a própria vida com precisão de memória; a Fada lendo barra erraria calada. É a regra permanente do projeto: memória primeiro, imagem é reserva. |
| **Clique no retrato + confirmação pelo `TARGET_ID`.** A Fada clica no slot e compara o id lido com os ids que cada conta publicou (obtidos com F1). **A versão por `nome` foi MEDIDA e reprovada** — ver a seção da medição. | (a) **OCR** do nick ou dos números de HP do painel — o projeto nunca teve OCR e ele erra calado. (b) **Assumir que a ordem do painel é a ordem do `time_logins`** — falso: o jogo ordena por ordem de entrada no time. (c) **O usuário numerar os slots** — quebra em silêncio toda vez que alguém reentra no time. |
| **A Fada fica FORA da largada**, da macro e da sincronia. | Contar como membro. O líder espera a confirmação de todos antes de largar; a Fada nunca confirmaria e o time travaria esperando por quem não vai chegar. |
| **A flag mora na conta** (`Fada`), e só tem efeito **em time**. | Um campo no líder ("quem é a fada"). A conta é fada por natureza — classe, skills, itens —, não por escolha de um time específico. |
| **Fila por ordem de chegada, estrita.** | Menor vida primeiro. Como a vítima só entra na fila FORA de batalha e parada na base, ela não está apanhando: não morre esperando, e ordem previsível vale mais que otimizar segundos. |
| **Espera indefinida enquanto a Fada bate no mural**; sem batida, poção. | Teto de tempo como regra. O tempo de cura depende dos itens da Fada e até de crítico — um teto fixo mandaria beber poção no meio de uma cura que ia funcionar. |
| **A batida da Fada sai de DENTRO do laço que cura.** | Uma checagem externa (processo vivo, hwnd válido, memória legível). É o falso positivo já MEDIDO no reset de time: a conta passa em todas essas provas e mesmo assim não faz o que precisa. A batida não descreve a capacidade, ela a prova. |
| **Mana: senta abaixo de 10%, volta a curar aos 50%.** Fila vazia ⇒ senta indefinidamente, mesmo cheia. | Curar até a mana zerar. Ela precisa de reserva para a cura seguinte; e sem ninguém para curar não há nada melhor que ela possa estar fazendo. |
| **Bolsa e pet só com a FILA VAZIA.** A bolsa limpa quando o líder anuncia; o pet usa a config dela. | Limpar por tempo, ou limpar assim que o líder anuncia. Abrir inventário e clicar com alguém esperando cura mata o alguém. |
| **Ela apanhando: continua tentando sentar.** | Revidar (deixaria de ser Fada) ou fugir. Decisão do usuário: o time protege, e um mob que chegar nela é eliminado por um aliado. |
| **Morto continua no time, não é curado, e PARA de rodar o APP** — só em time. | Tentar curar um cadáver. A Fada ignora e vai para o próximo; sem isso, uma vítima que morre no meio trava a fila inteira. |

## A INVERSÃO: o ponto inicial passa a ser o do LÍDER

Na primeira rodada do time ficou escrito, como invariante, que
`_base_pos_x/_base_pos_y` **nunca** seriam emprestados — copiar mandaria o
seguidor andar para o mapa errado.

**Isso está invertido a partir de 28/08/2026**, e por um motivo que não existia
antes: *"o ponto inicial do time sempre vai ser o mesmo, quando em time o líder
que deve mandar no ponto inicial em todos que fazem parte do time, para que
sempre estejam no mesmo lugar e nunca longe, então a fada sempre vai conseguir
curar sem problemas e sem precisar sair do lugar."*

**A trava que a inversão exige.** `_voltar_para_base` anda clicando no
**minimapa**, e `coord_para_pixel_do_minimapa` **limita ao raio útil do widget**:
um destino longe vira um clique na borda. No mesmo mapa o personagem chega, aos
poucos; **em outro mapa ele anda contra a parede indefinidamente**. Por isso o
ponto do líder só é adotado com o personagem no **mesmo mapa** — fora disso ele
mantém o próprio ponto e avisa na tela.

O caso não é hipotético: morte sem revive devolve o personagem em outro lugar. O
usuário observou que **relogin** devolve na coordenada onde caiu, o que reduz a
frequência, mas não elimina a morte.

## A geometria do painel

- O primeiro retrato de companheiro fica em **(28, 204)**, medido pelo usuário.
- O espaçamento é **fixo**, e os demais saem por derivação — um número só
  (`PRIMEIRO_RETRATO` + `PASSO_ENTRE_RETRATOS`), nunca cinco literais soltos.
- O painel **encolhe por baixo**: com menos companheiros, o slot de baixo some e
  os de cima ficam onde estavam.
- Para estar em time é preciso líder + 1, então **sempre há pelo menos um slot**.
- O próprio personagem NÃO está nessa lista: ele é o retrato grande de cima
  (`coords.own_portrait` = 44,48).

Quantos slots varrer = **membros do time − ela**. Mas a contagem só limita a
varredura: **quem confirma é o `TARGET_ID` lido depois do clique.**

### QUEM IDENTIFICA É O SLOT — corrigido em 01/09/2026

A primeira versão exigia que a vítima publicasse o próprio `TARGET_ID` e **só
curava com ele batendo**. Estava errado por dois motivos:

1. **Era redundante.** Desde que o time passou a ser lido da memória, o slot já
   É a identificação: `companheiros_de_time()` diz, em ordem, quem está em cada
   retrato. *"Se sabe qual o slot, não precisa de outra confirmação depois"* —
   e o usuário estava certo.
2. **Falhava FECHADA**, que é o pecado maior. Sem o id publicado a resposta era
   "não cure", e o laço voltava em 100 ms para clicar de novo. Medido em campo:
   **357 cliques no mesmo retrato, zero curas**, e o personagem saiu andando de
   tanto clique.

O id virou **rede, não portão**: quando a vítima publicou um e ele **não bate**,
aí sim há prova de que o clique pegou outra pessoa, e curar curaria o aliado
errado. Sem id publicado, confia-se no slot e cura-se.

E entrou um FREIO, que faltava e é o que transformou um defeito de confirmação
num personagem andando pelo mapa: no máximo
`MAXIMO_DE_TENTATIVAS_POR_VITIMA` cliques para a mesma vítima, com espera entre
eles. Passou disso, ela sai da fila e se vira com poção.

### CURAR SEM CONFERIR É CURAR O ERRADO

A medição mostrou que **clicar num aliado LONGE não seleciona nada** -- e o alvo
continua sendo o de antes. Se a Fada casse a cura logo depois do clique, sem
conferir, ela curaria **o aliado anterior** achando que curou quem pediu: o
pedido some da fila, e quem estava a 30% continua a 30%. Sem erro nenhum na
tela.

Por isso a regra é dura: **id que não bate ⇒ não cura.** A vítima volta para o
fim da fila (ou cai para a poção), e a Fada segue para o próximo.

## MEDIDO EM 28/08/2026 — e o resultado muda o desenho

Rodado pelo usuário na janela da conta `Tsuki69` (pid 64456), com o time
formado. Saída bruta em `logs/afericao_aliado/`.

```
Slot 1 em (28,204): mudou     | id 1075052834 -> 1076037143 | nome=None | 0.036s
Slot 2 em (28,284): mudou     | id 1076037143 -> 1097926420 | nome=None | 0.123s
Slot 3 em (28,364): nao_mudou | id 1097926420 -> 1097926420 | nome=None | 2.015s
Slot 4 em (28,444): nao_mudou | id 1097926420 -> 1097926420 | nome=None | 2.002s
Tecla F1:           mudou     | id 1097926420 -> 1075052834 | nome=None | 0.120s
```

### 1. O clique seleciona, e o atraso é de 36 a 123 ms

É o **piso físico** que faltava: quanto tempo depois de uma ação a memória
reflete o alvo novo. Vale para o clique e, pelo mesmo caminho, informa a
cadência do TAB do time -- o provisório de 400 ms do alinhamento está ~3× acima
do pior caso medido, ou seja, seguro e folgado.

### 2. A memória NÃO descreve jogador — nem o próprio personagem

`nome=None`, `hp=None`, `nivel=None` em **todos** os casos, inclusive no F1, que
seleciona a si mesmo. O array que `_procurar_entidade` varre só contém mobs. Não
é filtro do `alvo_atual()` (ele não tem nenhum): é a varredura que não acha a
entidade.

**Consequência:** o desenho original -- "clica, lê o nome, confere" -- está
MORTO. A Fada não consegue saber por `alvo_atual()` em quem clicou.

### 3. Mas o `TARGET_ID` responde para jogador, e isso salva a identificação

O alvo ANTES do primeiro clique era `1075052834`, e o `F1` voltou EXATAMENTE
para `1075052834`. Ou seja: **`F1` põe o próprio id da conta no `TARGET_ID`.**

Daí sai o caminho novo, todo por memória e sem nome nenhum:

1. cada conta aperta **F1** uma vez ao iniciar o APP, lê o próprio `TARGET_ID` e
   **publica esse id no mural** ("eu sou o 1075052834");
2. a Fada clica no slot N e lê o `TARGET_ID`;
3. compara com os ids publicados. Bateu, é aquela conta.

É **mais confiável** que o desenho original: compara inteiro com inteiro, sem
depender de nome, de OCR ou de a varredura de entidades achar alguém.

O que ele custa: um F1 por conta no início (e de novo depois de cada relogin, já
que o id é da sessão), e o alvo daquela conta fica trocado por um instante --
resolvido pelo TAB seguinte, que ela daria de qualquer forma.

### 4. Os slots 3 e 4 estavam VAZIOS, não longe

Foi o que ficou escrito aqui antes, e estava errado. A leitura do time
(31/08/2026) mostra `tamanho=3` — ou seja, DOIS companheiros. O painel
**encolhe por baixo**, então os slots 3 e 4 não tinham ninguém, e clicar em
retrato vazio não trocar o alvo é o comportamento certo, não uma falha.

Confirmado na rodada de 01/09/2026, com o mesmo time de 3: os slots 1 e 2
selecionaram (`BlazesAPP1` e `WizzOfBlazes5`), o 3 e o 4 não. A ferramenta
passou a **cruzar cada slot com o nome que a memória diz que está ali** e a só
cobrar os slots ocupados — antes ela reprovava por causa de retrato vazio, e um
instrumento que reprova o certo é pior que instrumento nenhum.

Isso não enfraquece o ponto inicial compartilhado: a Fada precisa de todos por
perto. Mas o motivo é outro — é o alcance da SKILL, que não foi medido, e não a
seleção.

### 5. Os ids MUDAM a cada sessão

Medido comparando as duas rodadas: em 28/08 o id da `Tsuki69` era
`1075052834`; em 01/09, `1084491547`. São ids de sessão.

**É por isso que cada conta publica o próprio id ao INICIAR o APP, e nada é
guardado em disco.** Um id gravado no `config.json` apontaria para outra pessoa
na sessão seguinte — e o invariante "id que não bate não cura" viraria "id que
bate por acaso cura o errado".

### 6. As coordenadas derivadas estão certas

O usuário gerou três provas, com 2, 3 e 4 companheiros: *"os quadrados ficaram
perfeitos na foto de cada aliado"*. O passo de 80 px derivado do print está
confirmado, e o painel encolhendo por baixo também.

## O que ainda NÃO foi medido — e bloqueia o resto

**A memória lê `nome` e `hp` de um alvo que é JOGADOR?** Todo alvo medido neste
projeto foi mob. O usuário confirmou por experiência que **clicar no retrato
seleciona o aliado**; o que ninguém sabe é se a memória passa a descrever esse
alvo.

- **Se ler**: a Fada confirma em quem clicou e vê a vida do aliado direto — a
  vítima nem precisa anunciar que ficou cheia.
- **Se não ler**: a Fada clica às cegas, e a confirmação de quem é quem cai.
  Nesse caso a vítima anuncia os dois eventos (vida baixa e vida cheia), e a
  identificação precisa de outro caminho.

Por isso o **primeiro passo é uma ferramenta de aferição**, no molde do
`bot/app/afericao.py`: ela clica cada retrato, loga o que a memória passou a ver
(`id`, `nome`, `hp/max`) e salva o print anotado mostrando onde clicou. Ela
responde de uma vez as duas dúvidas — a leitura do alvo-jogador e se as
coordenadas derivadas estão certas.

**É a lição do `TARGET_ID` entre clientes**, que ficou sem medir e virou
justamente o modo do time que não funciona (ver `time-do-app.md`).

## Estacionado, com o porquê

**O revive.** A Fada tem skill de reviver, e o revivido nasce na coordenada
dela. Mas o morto precisa clicar no **OK da janela dela**, que aparece depois do
OK original — e não há print dessa janela ainda. Sem o print não há template nem
coordenada, então o revive fica de fora desta entrega. O que entra agora é o
comportamento sem revive: morto para de rodar o APP e a Fada o ignora.

**A leitura direta da vida do aliado.** Só se a aferição passar. Até lá, quem
diz "estou cheio" é a vítima.


## A queda da Fada — 04/09/2026

> *"Por sinal, se a fada cai, muitas vezes o bot não reconhece; tem que analisar
> isso, provavelmente é algo que não está sendo feito."* — usuário.

Era isso mesmo: **a Fada era o único modo que não percebia a própria queda.**

`FadaDoTime.rodar()` termina sozinho quando o `continuar` vê a janela morta
(`IsWindow`). Só que ninguém traduzia isso em queda: `_operate` simplesmente
chamava a montagem de novo na volta seguinte. Sem `Disconnected`, não há
`_encerrar_caido`, não há relogin, não há print em `logs/quedas/` e não há linha
no Histórico. A conta ficava girando contra uma janela morta.

O modo APP tem exatamente esta conferência no fim de `_rodar_modo_app` desde
18/08/2026, e a regra do `CLAUDE.md` é explícita: *todo ecossistema percebe a
queda ENQUANTO roda, com a MESMA definição, e tem o MESMO desfecho*. A Fada
nasceu depois e não herdou a linha.

### O que mudou

| onde | antes | agora |
|---|---|---|
| fim de `rodar_a_fada` | devolvia calado | `IsWindow` falso ⇒ `Disconnected` |
| memória que não abre | `return` seco (e `_operate` chamando de novo na hora) | confere a janela primeiro; se está viva, avisa e **dorme** `SEGUNDOS_ENTRE_TENTATIVAS` |
| `_montar_a_fada` (HH) | `except Exception` engolia a queda junto | `except Disconnected: raise` **antes** do geral |

O terceiro é o mais traiçoeiro: o `except Exception` existe para a HH não
derrubar a sessão quando a montagem falha, e ele engolia a queda no mesmo laço —
a Fada da HH seguia acompanhando o líder com a janela fechada.

### O que este conserto NÃO resolve

Continuam abertos os buracos de **silêncio** do batimento (a Fada viva que passa
mais de `SILENCIO_DA_FADA` sem bater, e o time conclui que ela sumiu) e a
**espera sem teto** da vítima. São outro assunto, outro commit.


## Os buracos de silêncio — a Fada viva dada por morta (04/09/2026)

A queda que ninguém via tinha um irmão gêmeo do lado oposto: **a Fada viva que
para de bater.** Como `fada_de_pe` é a ÚNICA coisa que faz a vítima desistir e
beber poção, todo intervalo em que a Fada existe mas não bate é um intervalo em
que o time a dá por morta.

Dois buracos medidos:

| buraco | tamanho | por quê |
|---|---|---|
| limpeza da bolsa da ociosa | até **10 s** (`deletador.TETO_DE_SEGUNDOS`) | `_cuidados_de_ociosa` chamava `_limpar_a_bolsa()` direto, sem passar por `_dormir` -- e é o `_dormir` que bate |
| modo **HH+Fada** | o giro inteiro | a batida morava só no `rodar()`, e a HH chama `_uma_volta` de dentro do laço de acompanhar o líder; com a fila vazia o giro voltava sem espera nenhuma |

### O remédio: a batida passa a ter VALIDADE

`bater_fada(login, em_batalha, vale_por)`. Quem vai sumir por uma tarefa longa
avisa antes por quanto tempo; `fada_de_pe` compara com a validade gravada, e não
mais com a constante. Com dois limites:

- **nunca encurta** o silêncio padrão de 5 s (pedir menos não adianta nada);
- **nunca passa de `TETO_DA_BATIDA_LONGA` (15 s)** — morrer *durante* a tarefa
  longa custa essa espera a mais, e é o preço aceito; sem teto, uma Fada morta
  demoraria uma eternidade para ser notada.

Ao terminar a limpeza ela **bate de novo com a validade normal**, para o aviso
não sobrar: dali em diante ela está pronta, e uma morte tem de aparecer nos 5 s
de sempre.

O buraco da HH se resolve sem validade nenhuma: a batida passou a sair também do
topo de `_uma_volta`, que é o único ponto por onde os dois chamadores passam.


## A espera da vítima deixou de ser eterna (04/09/2026)

O levantamento achou dois casos em que a vítima ficava sentada para sempre com a
Fada VIVA:

**1. Fada viva e incapaz.** Se a vítima não estivesse no painel do time,
`_atender` devolvia `(False, True)` e a Fada seguia batendo. O próprio código já
admitia: *"como a Fada continua batendo, eles esperariam para sempre achando que
há Fada disponível"*. Como `fada_de_pe` era a ÚNICA coisa capaz de fazer a
vítima desistir, não havia saída.

**2. O laço desistir/re-pedir.** Quando a Fada desistia (teto estourado,
tentativas esgotadas, sem nick), ela só apagava o pedido. A vítima republica a
própria vida a cada 0,2 s enquanto espera — então voltava para a fila em
seguida, agora com hora NOVA, portanto no fim dela. A Fada desistia de novo. E
de novo. Ninguém bebia a poção que resolveria.

### As três saídas novas

| saída | quando | o que faz |
|---|---|---|
| `fada_desistiu_de` | a Fada desistiu desta vítima | poção |
| `TETO_DA_ESPERA_PELA_FADA` (60 s) | nem o aviso chegou | poção |
| entrou em batalha | um mob atacou quem estava sentado | **volta à macro** (não é poção) |

A terceira é a regra do usuário aplicada aqui: *"em batalha o personagem precisa
estar atacando"*. Sentado apanhando é como um ferido vira um morto.

### A marca da desistência não é apagada por um pedido

`desistir_da_vitima` tira o pedido E grava a marca. A tentação era limpá-la no
`pedir_cura` "quando o pedido for novo" — mas, como a desistência já apagou o
pedido, a republicação da vítima chega lá **indistinguível de um pedido novo**,
e limpar ali reabriria exatamente o laço que a marca fecha. Quem limpa é a
vítima, ao LER o recado, ou o relógio (`VALIDADE_DA_DESISTENCIA`, 20 s) — curto
de propósito, porque a marca é recado, não banimento.
