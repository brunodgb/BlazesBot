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


## A tecla de reviver — o que foi medido (04/09/2026)

O tooltip da skill no cliente (Wizard nível 70) responde sozinho quase todo o
desenho do reviver:

| campo | valor | o que decide |
|---|---|---|
| Mana | **1168** | a Fada confere a mana ANTES de tentar; sem ela, nem aperta |
| Distance | **150** | ela **não precisa chegar perto do corpo** — nada de caminhar até o morto |
| Preparing Time | **5 s** | do toque até a janela aparecer na tela da vítima passam ≥5 s; concluir "a tecla não saiu" antes disso é erro |
| Cooling Time | 1,5 s | duas tentativas seguidas não colidem |
| efeito | revive **e recupera 1168 de vida** | o revivido não levanta agonizando (o valor acompanha a força da Fada) |

A tecla é `KeyBinds.revive_skill`, na aba **Teclas → Magias de Suporte**, nas
duas interfaces. **Vazia por padrão**, como a `follow`: chutar tecla faria a
Fada apertar outra coisa em cima de um morto.


## A Fada revivendo (04/09/2026)

O segundo serviço dela, ao lado da cura — em `bot/fada_reviver.py`, fora de
`fada.py` porque aquele arquivo estava a poucas linhas do teto de 800 e porque a
costura é real: curar é apertar uma tecla até uma barra subir; reviver é apertar
**uma vez** e esperar um feitiço de 5 s pegar. A seleção pelo retrato do painel
é **chamada** de lá, não copiada.

### A prioridade

> *"O ideal é colocar o morto à frente só se estiver demorando muito (...)
> tirando isso a cura vem primeiro."*

Parece contraintuitivo e não é: um morto não apanha nem gasta poção, e tem prazo
próprio de um minuto para se reviver sozinho. Um ferido a 30% sentado esperando,
ao contrário, pode virar o próximo morto. Então a cura vem primeiro **até** o
morto passar de **40 s** (`SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA`), e aí ele fura
a fila.

Os 40 não são arredondamento: o morto se auto-revive aos 60
(`morte.PRAZO_PARA_A_FADA`) e a skill leva 5 s preparando. Com 40 a Fada tem
folga para começar, terminar e ainda avisar que começou.

### O contrato dos dois lados

| quem | faz | por quê |
|---|---|---|
| Fada | `mural.comecei_a_conjurar(vítima)` **antes** de apertar | sem isso a vítima clica no "Ok" do jogo no meio dos 5 s: a mana vai fora e o convite aparece para quem já está vivo |
| vítima | `mural.esquecer_morte` **no instante** em que fica de pé | é assim que a Fada sabe que o feitiço pegou; deixar para o fim do ciclo faria ela esperar a caminhada de volta inteira |

### O que continua valendo da cura

- **Id que não bate não revive.** O clique pode não pegar, e o feitiço iria para
  o aliado ANTERIOR — a mana inteira gasta em quem está vivo.
- **Freio de 3 tentativas** (o mesmo dos 357 cliques de 01/09/2026). Estourou,
  ela larga o morto e o prazo dele resolve.
- **Mana contada antes do toque.** O reviver custa muito mais que uma cura;
  apertar sem ter só queima a recarga.
- **Sem tecla configurada ela avisa UMA vez** e segue curando.


## Por que a Fada não estava revivendo — 06/09/2026

Na única morte da noite de 05→06/09:

```
00:09:43  blazestpas     MORRI. A macro para aqui — avisando o time.
00:09:45  mfaustoapp069  FADA: BlazesAPP1 não selecionou em 3 tentativas —
                         deixo o prazo dele correr, ele se revive sozinho.
00:10:43  blazestpas     A Fada não me reviveu no prazo — revivo sozinho.
```

**Dois segundos de tentativa; 58 segundos de prazo desperdiçados.**

A causa é a confirmação por id, herdada da cura. O usuário respondeu o que o
jogo faz: o retrato do morto **continua no painel e continua clicável**, mas o
clique **não põe o morto no `TARGET_ID`**. Ou seja, para um morto aquela
pergunta não tem resposta certa — ela recusava corretamente e reprovava a única
coisa que ia funcionar.

### O que mudou

| antes | agora |
|---|---|
| id tinha de bater | **o SLOT manda**; o id vira log, não veto |
| 3 tentativas a 0,2 s (2 s) | **janela de 10 s**, no máximo 3 toques |
| desistiu ⇒ tirava o morto da fila | **o morto CONTINUA na fila**; ela volta a tentar enquanto o prazo dele correr |

O slot vem da memória (`companheiros`), na ordem do painel — e é a mesma regra
que o usuário já tinha dado para a cura: *"se sabe qual o slot, não precisa de
outra confirmação depois"*.

**O teto de 3 toques não é sobre tempo**: é cinto de segurança contra o defeito
de 01/09/2026, quando a espera devolveu na hora e o laço clicou 357 vezes no
mesmo retrato, fazendo o personagem sair andando. Com 5 s de preparo, três
toques é tudo o que cabe em 10 s de qualquer forma.

### A confirmação por id CONTINUA valendo na cura

Lá o alvo está vivo, o clique seleciona, e o id é o que impede curar o aliado
errado — o defeito de 26/08 que produziu a regra. Não é o mesmo caso.


## Time desfeito no jogo: a contingência da poção — 07/09/2026

> *"Quando todos os personagens do time APP caem, o jogo desfaz a party
> automaticamente. Sem a party, a fada não consegue aplicar a cura em grupo.
> Como a recriação automática do time não está implementada, precisamos de uma
> medida de contingência quando os personagens reconectarem."* — usuário

### O que acontecia

**Nada no bot era avisado.** A configuração continua listando o time, o mural
continua com a Fada batendo (do lado dela não mudou nada mesmo), e a vítima
esperava o teto inteiro por uma cura que **não tinha como sair**: sem party não
há painel de time, e sem painel a Fada não tem retrato para clicar.

O resultado era a pior combinação possível: a conta parada, sentada, esperando —
com a poção na bolsa e a regra dizendo "não beba, tem Fada".

### A leitura que decide

`Memory.tamanho_do_time()`, o ponteiro rebaseado (`ADDR_TEAM`), que **conta o
próprio personagem**:

| leitura | significado | o que a vítima faz |
|---|---|---|
| ≥ 2 | há party | espera a Fada, como sempre |
| **1** | só eu | **poção** |
| **0** | sem time | **poção** |
| `None` | não deu para ler | espera a Fada (não sei não desliga nada) |

O `None` é a parte que mais importa: tratá-lo como "sem time" tiraria a cura em
grupo de todo mundo no primeiro soluço de memória. É a mesma regra da
conferência de janela antes de enviar tecla — **só o ponteiro CONFIRMANDO
derruba a dependência**.

### Onde o portão fica, e por quê

**Antes de publicar o pedido no mural.** Pedir cura e desistir depois deixaria a
vítima na fila da Fada por nada, e a Fada gastaria tentativas num aliado que não
está no painel dela.

### O que isto NÃO faz

**Não recria o time.** É contingência, não conserto: a conta volta a se curar
sozinha e segue farmando até o time existir de novo. Recriar a party
automaticamente continua sendo trabalho pendente — e quando existir, este portão
passa a ser o gatilho natural dele (é o único lugar do código que sabe, com
prova, que a party caiu).

## A Fada volta ao ponto inicial — 07/09/2026

*"A fada deve voltar ao ponto inicial para evitar zonas de risco. Implemente uma
rotina de verificação de distância que opere com baixo custo computacional.
Ative a rotina de retorno ao ponto de origem para ela tambem"* — usuário.

**Ela não anda sozinha, e ainda assim sai do lugar.** Não há nada no laço dela
que ande: o que a move é o jogo. A cura em grupo tem alcance, o time avança
matando, e a Fada acaba puxada atrás — até parar num lugar que ninguém escolheu.
Era o único modo do bot sem trava de posição, e o APP já tinha a dele desde o
início.

**O ponto é onde ela estava quando começou**, guardado na primeira leitura de
posição. Não é coordenada configurada, e por três motivos: é o mesmo critério
que o APP já usa, o usuário posiciona a Fada onde quer antes de ligar, e fora da
cave não existem waypoints (decisão dele em 06/09/2026: *"como no caso do APP
não vão existir waypoints, vai ter que usar o ponto inicial como base"*).

**A mecânica foi PROMOVIDA, não copiada.** `core/volta_ao_ponto.py` tem as duas
coisas que o APP já fazia — a régua do "já cheguei" e o clique direito único no
minimapa — e agora os dois ecossistemas leem o mesmo `TOLERANCIA = 1`. O que
NÃO subiu é a política, porque ali eles são diferentes: o APP não anda em
batalha, a Fada não anda com alguém na fila de cura.

### O que quase virou defeito: sentar cancela a caminhada

A Fada senta a cada giro do laço por desenho (sentada ela regenera, e é a única
coisa útil que tem para fazer). A primeira versão desta rotina mandava andar e
devolvia o controle — e o giro seguinte, 0,1 s depois, apertava a tecla de
sentar e cancelava a ordem. Ela ficaria a meio caminho: fora do ponto seguro e
sem chegar em lugar nenhum.

Por isso `voltar_ao_ponto_se_preciso` devolve **`True` enquanto está indo**, e o
ramo ocioso sai na hora quando ele diz isso — sem sentar, sem pet e sem bolsa. E
a marca **dura a cadência inteira** (3 s, ~30 giros), senão a proteção valeria
para um giro só. Está travado em `tests/test_volta_ao_ponto.py`.

### O custo: medido, porque a pergunta foi feita

*"E hoje o bot fica olhando direto se está ou não sentado a fada, isso não
consome muito? Não seria melhor otimizar e deixar de forma que opere com baixo
custo computacional"* — usuário, 07/09/2026.

**Medido nesta máquina no mesmo dia:**

| operação | custo | quantas vezes é um `is_sitting` |
|---|---|---|
| `ReadProcessMemory` (uma leitura) | **0,86 µs** | — |
| `is_sitting` (duas leituras: o ponteiro do jogador + o byte) | **1,71 µs** | 1x |
| `capture_window` (uma captura de janela) | **22,2 ms** | **12 985x** |

A 10 Hz, que é a cadência do laço da Fada, `is_sitting` custa **0,017 ms por
segundo — 0,0017% de um núcleo**. Não há o que otimizar ali: a conta é quatro
ordens de grandeza menor que qualquer coisa que a tela custe, e a leitura não é
enfeite — ela é o que impede o erro do INTERRUPTOR (apertar a tecla sem saber o
estado sentaria a Fada bem na hora de curar, que é o único momento em que ela
tem pressa).

**Onde o custo realmente mora, se um dia importar, é no giro do laço** (10 Hz), e
não em qualquer leitura individual dele: baixar a cadência da Fada corta TODAS
as leituras dela de uma vez. Não foi feito porque não há sintoma — e porque
reagir mais devagar a um pedido de cura tem custo em vida, que é caro de
verdade.

**A conferência do ponto, por outro lado, TEM cadência (3 s).** Não por causa do
custo da leitura — pelo mesmo motivo que o pet e a bolsa têm: perguntar dez
vezes por segundo uma coisa que só muda quando o time anda é gastar sem chance
de resposta diferente.

## A AMBULÂNCIA — emergência fura a própria defesa (23/09/2026)

Pedido do usuário: *"se um Damage apanha muito, ele morre e perde experiência,
pois a Fada segue seu loop normal ou aguarda o fim do combate"*. O alvo é zero
morte no time.

### O limiar é DERIVADO, não é campo novo na tela

    limiar_critico = max(20, "pedir cura abaixo de" / 2)

    pedir 80%  ->  crítico 40%        pedir 30%  ->  crítico 20%  (o piso segura)
    pedir 50%  ->  crítico 25%        pedir 20%  ->  crítico 20%

O piso existe porque abaixo dele não há tempo: numa rota em que o dano toma 15%
por golpe, um crítico de 10% é uma emergência declarada depois da morte.

Ele mora em `fada.hp_critico(pedir_pct)`, **função de módulo e não só método**,
porque os DOIS lados precisam da mesma conta: a Fada, para decidir se larga a
defesa, e o dano, para decidir se avisa. Duplicar a fórmula seria deixar os dois
discordarem no dia em que alguém mexesse num deles. E ela é lida A CADA CHAMADA:
a barra é do líder e o usuário mexe nela com o bot rodando.

### O buraco que a modelagem encontrou: a fila estava VAZIA na luta

O pedido dizia "adicione um polling do HP da equipe no laço de batalha da Fada".
Não havia o que pollar.

- **A memória não serve.** `vida_do_time()` existe, mas o `hp` dela parece ser o
  MÁXIMO e não a vida atual (`core/memory.py`) — decidir emergência com esse
  número é decidir com o número errado. Quem sabe a vida de uma conta é ela
  mesma, e ela publica no mural.
- **E o dano não publicava em batalha.** `cura.socorro` é o ÚNICO caminho de vida
  baixa durante a luta, e ele só bebia poção. O pedido de cura nasce em
  `chamar_a_fada`, que só roda FORA de batalha. Ou seja: exatamente no cenário do
  relato — o dano apanhando —, a fila da Fada ficava vazia.

Então a feature precisou de duas metades. Só a da Fada seria decorativa.

### Metade 1 — o dano AVISA, e não espera

Em `socorro`, antes da porta da poção: se há Fada de pé no time, publica a
própria vida quando cruza o crítico, e RETIRA o pedido quando volta para a faixa
segura (senão a Fada iria clicar no retrato de alguém com vida cheia).

O aviso **não espera nada** — é uma escrita em dicionário. Em batalha quem mata
quem está batendo é a macro, e parar para esperar cura foi o que matou três
personagens em 07/09/2026.

Ele vem ANTES da cadência da poção (`SEGUNDOS_ENTRE_SOCORROS`) de propósito: a
poção tem ritmo próprio e não pode calar a Fada.

### Metade 2 — e ela NÃO larga a própria defesa em batalha

A primeira versão largava: em batalha, um companheiro crítico ganhava dela,
desde que ela mesma não estivesse crítica. Durou algumas horas. O usuário
desfez, e o argumento dele fecha sozinho: *"se ela está em batalha tem algum mob
batendo nela, e a prioridade é ela se manter viva"*.

**E havia um buraco técnico que a exceção não cobria**, encontrado ao responder
a pergunta dele: a checagem "eu estou crítica?" acontecia UMA VEZ, antes de
começar. `_curar` fica até `TETO_DA_CURA_SEGUNDOS` (20 s) batendo a cura no
aliado e conferindo a vida DELE — nunca a dela. Entrar em 45% com mob batendo e
sair morta nos 20 s seguintes era um caminho aberto, e a proteção que eu tinha
escrito valia só para o instante da decisão.

Em batalha, portanto, a regra de 01/09/2026 continua inteira: ela cuida de si.

### A emergência vive FORA de batalha: o crítico fura a fila

Lá ninguém está batendo nela, e parar de sentar para atender quem está morrendo
não custa nada. `_critico_primeiro` põe os críticos na frente **preservando a
ordem de chegada dentro de cada grupo**: entre dois críticos atende quem pediu
primeiro, e o mesmo entre dois feridos. O que muda é que quem está morrendo não
espera atrás de quem está em 70%.

O contador `emergencias` conta quantas vezes isso aconteceu, e aparece no
`resumo()` — se ele estiver alto, a rota está pesada demais para o time.

### O anti-spam já existia, e por isso não foi escrito de novo

A emergência chama `_atender`, o mesmo caminho da fila normal: ele confere o
alvo pelo id depois do clique, conta tentativas por vítima
(`MAXIMO_DE_TENTATIVAS_POR_VITIMA`), espera `ESPERA_DEPOIS_DE_ERRAR` entre elas
e desiste da vítima quando não adianta. Um segundo cooldown ao lado desse seria
duas travas discordando sobre a mesma coisa.

### A volta ao normal não precisou de código

`_uma_volta` é um giro: ao fim da emergência o laço reavalia tudo do zero — se
ainda há batalha e ninguém crítico, ela volta a se defender; se a luta acabou,
cai na fila normal, nos mortos e depois na ociosidade. O estado que existe é o
contador `emergencias`, que aparece no `resumo()` para dizer se a ambulância
está sendo chamada.
