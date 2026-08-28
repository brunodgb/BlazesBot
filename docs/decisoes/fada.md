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
retrato** do aliado no painel de time, **confere pela memória em quem clicou**, e
cura até o alvo combinado. Fila por ordem de chegada. Sem Fada de pé, a poção
volta a valer.

## O que foi decidido, e o que foi RECUSADO

| decisão | o que foi recusado, e por quê |
|---|---|
| **A vítima avisa** — ela publica no mural "preciso de cura, estou em 28%". | A Fada varrer as barras de vida do painel na tela. A vítima sabe a própria vida com precisão de memória; a Fada lendo barra erraria calada. É a regra permanente do projeto: memória primeiro, imagem é reserva. |
| **Clique no retrato + confirmação pela MEMÓRIA.** A Fada clica no slot, lê o `nome` do alvo e compara com quem pediu. Aprende o mapa slot→nick e **confere sempre**. | (a) **OCR** do nick ou dos números de HP do painel — o projeto nunca teve OCR e ele erra calado. (b) **Assumir que a ordem do painel é a ordem do `time_logins`** — falso: o jogo ordena por ordem de entrada no time. (c) **O usuário numerar os slots** — quebra em silêncio toda vez que alguém reentra no time. |
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
varredura: **quem confirma é a leitura da memória depois do clique.**

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
