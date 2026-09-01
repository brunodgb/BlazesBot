# A cura no ecossistema APP (25/08/2026)

> **A frase que resume**, do usuário: *"a ideia é garantir que o personagem não
> morra, e sim se cure em um lugar seguro, que é onde o usuário decidiu que
> seria o ponto inicial"*.

Combinado numa sessão de grilling inteira. Cada número aqui é decisão dele, e
está anotado com a frase que o gerou — porque número sem porquê apodrece.

## O fluxo

Ao terminar **cada rotação da macro** (nunca no meio de uma):

```
vida >= 30%   -> nada acontece
vida <  30%   -> esperar SAIR DE BATALHA (até 2 s, perguntando)
                   ainda em batalha -> roda mais uma volta da macro
                   fora de batalha  -> volta ao ponto e cura
volta ao ponto -> um clique no minimapa, perguntando a posição, teto de 5 s
curar          -> com tecla de poção: bebe, espera até 15 s, repete até 90%
                                       ou até 5 poções
               -> sem tecla de poção: senta até 30 s, levanta aos 90%
entrou em batalha -> em QUALQUER ponto da cura, volta a rodar a macro
```

## Os números, e de onde vieram

| número | valor | a frase do usuário |
|---|---|---|
| gatilho | **30%** | *"em vez de 20%, vamos a 30% ... assim tem uma margem de erro maior e a probabilidade de morrer é menor"* |
| alvo | **90%** | *"até chegar nos 90%"* |
| entre poções | **15 s** | tempo de efeito da poção, medido por ele |
| teto de poções | **5** | *"normalmente em no máximo 2 deve curar, pois depende do nível da poção que o usuário comprou"* |
| volta ao ponto | **5 s** | *"em no máximo 5 segundos é para chegar no ponto inicial"* |
| sentado | **30 s** | *"ficar sentado por até 30 segundos"* |
| sair de batalha | **2 s** | *"pode verificar que em no máximo 2 segundos depois que terminou a macro já deve sair de batalha"* |

**Todos moram em `blazesbot/bot/app/cura.py`**, num bloco só. Decisão dele:
*"o ecossistema APP tem que ter suas próprias configurações, que não dependam
do bot BC; por hora vamos colocar só no arquivo .py mesmo, futuramente eu decido
como vamos melhorar isso"*. Estarem juntos é o que faz a mudança futura ser uma
mudança só.

**A margem dos 30%** não é folga à toa: entre o gatilho e a primeira poção há
uma volta de macro para terminar, até 2 s de espera de batalha e até 5 s de
caminhada. O gatilho tem que aguentar tudo isso.

## Por que fora de batalha

Medição do usuário: **a poção de fora de batalha não funciona em combate**. Os
2 s existem porque o jogo demora a baixar a flag depois que o mob morre — não é
o mob estar vivo, é o jogo se atualizando.

E é aí que o alvo entra. Desde 25/08 o bot lê `hp/max_hp` do alvo pela memória
(ver `memoria-primeiro.md`), e o usuário puxou isso para cá:

> *"caso queira melhorar, veja a vida do target, assim saberemos se matou
> realmente o mob ou não, agora que temos essa informação podemos usar ela."*

Então a espera tem **duas saídas antecipadas, e nenhuma é o relógio**:

* a flag baixou → pode curar, sai na hora;
* **o alvo ainda tem vida** → tem mob vivo batendo, e esperar a flag é esperar
  por nada. Sai na hora para rodar mais uma volta da macro.

> *"Caso não saia de batalha meio logo, é pq pode ter outro mob atacando."*

## "A poção saiu?" deixou de ser pergunta sem resposta

Acréscimo do usuário em 25/08/2026, e é o achado mais útil desta área depois do
alvo:

> *"Sobre sentar em vez de usar a poção, ela deve fazer caso, ao usar poção, não
> entre no estado de sentado pela memória, pois provavelmente acabou as poções
> do usuário."*

**Beber põe o personagem SENTADO.** Isso é observável por memória
(`Memory.is_sitting()`), e transforma uma pergunta que não tinha resposta em uma
que se responde em um segundo.

### O que acontecia antes

O bot apertava a tecla e **só descobria pela vida, quinze segundos depois**. Com
a bolsa vazia, ele repetia isso **cinco vezes** — apertando uma tecla que não
fazia nada, enquanto o personagem apanhava. No fim, avisava "poção fraca demais"
e voltava para a macro com a vida no chão. Diagnóstico errado, 75 segundos
gastos, e nenhuma cura.

### O que acontece agora

```
aperta a tecla -> sentou?  SIM  -> a poção saiu, espera o efeito
                           NÃO  -> acabaram: SENTA para não morrer
                           ?    -> não sei: segue bebendo, como antes
```

`SEGUNDOS_PARA_SENTAR_COM_A_POCAO = 1.0`, e o teto é curto de propósito: é
animação local do cliente, não ida ao servidor. A espera **pergunta** e sai no
instante em que o estado aparece — o teto só é pago quando a poção **não** saiu,
que é justamente o caso em que se quer descobrir rápido.

**"Não sei" não vira veredito.** Sem leitura de estado, concluir "acabaram as
poções" trocaria a cura boa por sentar no chão. Nesse caso segue-se bebendo,
exatamente como antes.

### Dois caminhos chegam a sentar, e o log diz qual foi

| motivo | o que o log diz |
|---|---|
| nenhuma tecla de poção configurada | *"sem tecla de poção; sentando para recuperar"* |
| a poção não saiu (bolsa vazia) | *"o personagem NÃO sentou — provavelmente acabaram as poções"* |

Nos dois casos é a mesma coisa, e a frase do usuário resume: **é o que sobra
para não morrer**.

## A poção de batalha ficou de fora, e foi decisão medida

Propus usar `battle_hp_potion` como rede para o caso "vida em 8%, mob
encadeando, macro rodando e o remédio no bolso". A resposta foi de campo:

> *"Normalmente os personagens que rodam APP só usam o fora de batalha e
> funciona muito bem. Vamos fazer o seguinte: em vez de 20%, vamos a 30%."*

Ou seja: em vez de uma segunda poção, **mais margem**. Menos peças, mesmo
efeito.

## O risco que fica de pé — e é escolha consciente

Com vida baixa e mob encadeando, o bot roda a macro volta após volta sem nunca
sair de batalha, e **pode morrer com a proteção ligada**.

Isso não é descuido: é a decisão dele, e é a certa.

> *"Se entrar em batalha e a vida começar a cair, só começar a rotacionar a
> macro, pois não adianta continuar insistindo se não está curando, pois só vai
> fazer o personagem morrer para o mob."*

Rodar a macro é o que mata o mob. O que o código faz a respeito é **avisar**
(`VOLTAS_PRESAS_PARA_AVISAR = 5`): é informação que só o usuário pode agir sobre
— ponto inicial ruim, mob demais, ou macro fraca demais.

## Detalhes que custaram pensamento

**Sentar NÃO é uma trava** — ver a seção "O bot só senta" abaixo. A tecla é
INTERRUPTOR, e é só por isso que o estado é LIDO ANTES (`is_sitting`): apertá-la
com o personagem já sentado o LEVANTA, desfazendo justamente o que se queria.

**Sem ponto, cura no lugar.** Trava de posição desligada, ou posição ilegível:
nunca se deixa de curar por falta de ponto. Sem leitura de posição, o clique usa
a **última posição conhecida** — numa volta de macro o personagem quase não
anda, então ela vale mais que não responder nada.

**O contador de poções zera a cada ciclo.** *"Cada vez que entrou em batalha e
precisou voltar para a macro, reseta a quantidade de poções usadas."* Cada volta
ao ponto é um ciclo novo.

**A vida atual é o maior limitante.** Chegou aos 90%, para — não espera o resto
dos 15 s por nada. Quem comprou poção forte não paga a segunda.

**Sem leitura de vida a proteção é inerte**, e isso é dito uma vez em vez de
fingido. Não dá para proteger o que não se enxerga.

## Onde a cura entra no laço, e por quê

`ExecutorDeMacro.rodar()`, depois de `uma_volta()` e da conferência de saúde,
**antes** da limpeza da bolsa. Com 30% de vida, apagar lixo primeiro é tempo que
o personagem não tem.

**A cura NÃO conta como volta.** `self.voltas` é rotação de macro, e as
cadências de limpeza (`apagar_lixo_a_cada`) e de shuffle
(`shuffle_apos_n_voltas`) foram pensadas em cima de trabalho de macro, não de
tempo parado se curando.

**A cura absorve a trava de posição daquela volta**: as duas querem levar o
personagem ao mesmo ponto, e deixar as duas clicarem no minimapa seria ordem
dupla de andar.

## Por que a cura chega ao executor como FÁBRICA

`tests/test_ecossistemas.py::test_o_executor_do_app_so_usa_o_core` é o
isolamento mais apertado do projeto: o executor manda tecla e espera, e tudo
além disso é injetado. Importar `cura.py` — mesmo sendo do mesmo ecossistema —
reprova ali, e a trava está certa.

Objeto pronto também não daria: a `CuraDoApp` precisa de `distancia_da_base` e
`mandar_voltar_para_base`, que são métodos **do próprio executor**. A fábrica
recebe `self` e resolve o ovo e a galinha sem ninguém mexer em atributo de fora.

## De brinde: uma espera cega a menos

`_voltar_para_base` era um clique no minimapa seguido de `time.sleep(2.0)` —
**cego**, e o método dizia ter devolvido o personagem sem nunca ter conferido.
Virou `_esperar_chegar_na_base`, que pergunta a posição e sai no instante em que
chega. O teto (`SEGUNDOS_PARA_A_TRAVA_DEVOLVER = 2.0`) é o mesmo gasto de antes,
mas agora quase nunca é pago.

---

## O crash da primeira cura de verdade (25/08/2026)

```
AttributeError: 'PotionConfig' object has no attribute 'hp_potion'
  supervisor.py:1300  tecla_de_pocao=lambda: self.account.settings.potions.hp_potion
```

**A tecla mora em `KeyBinds`, não em `PotionConfig`.** É a distinção que o
próprio projeto já tinha: **tecla descreve o JOGO** e é compartilhada entre
ecossistemas; `PotionConfig` guarda os **limiares** do BC (`hp_pct`,
`battle_hp_pct`), que são de quem decide.

### Por que nenhum teste pegou

A leitura vive dentro de um `lambda`, e o `lambda` só é avaliado **na hora de
curar**. Compilou, importou, passou a suíte inteira — e estourou na primeira vez
que um personagem chegou a 30% de vida com o APP rodando.

É a **quarta vez** que esta família morde: `candidato_de_alvo`, `target_detail`,
`_parece_nome`, e agora `settings.potions.hp_potion`. Todas iguais — atributo que
não existe, num caminho que nenhum teste percorre.

### A trava

`tests/test_sem_chamada_orfa.py::test_nenhum_settings_ponto_grupo_ponto_campo_inexistente`
lê o AST atrás de `<algo>.settings.<grupo>.<campo>` e confere o campo contra os
`dataclasses.fields` do grupo.

**Foi verificada reintroduzindo o defeito**, e ela acusou a linha exata:

```
blazesbot/bot/supervisor.py:1305 settings.potions.hp_potion
```

Teste de guarda que ninguém viu falhar é esperança, não trava.

---

## O bot SÓ SENTA — nunca levanta (01/09/2026)

**REGRA DO JOGO, dita pelo usuário e que este arquivo errou por semanas:**

> *"Caso o personagem esteja sentado ele pode atacar e fazer qualquer coisa
> livremente. O sentar não é uma trava, é só um estado que sai com qualquer
> coisa que o personagem fizer. Não precisa de função para levantar nem nada
> disso, só precisa sentar — pois o ato de sentar aumenta a cura de vida base do
> personagem e também aumenta a cura de mana base."*

### O que estava escrito aqui antes, e era falso

> *"A cura devolve o personagem DE PÉ. Sentado, a macro inteira bate no chão —
> as teclas saem, o jogo ignora, e o bot conta voltas achando que está
> farmando."*

**Isso não acontece neste jogo.** Não houve medição por trás da afirmação; ela
nasceu de uma suposição sobre a mecânica, foi escrita em docstring, copiada para
três documentos, e daí em diante cada leitura confirmava a anterior.

### Por que levantar é ATIVAMENTE PIOR, e não apenas inútil

1. **Perde a regeneração.** O bônus de vida e mana do sentado é a única razão de
   sentar. Sair antes joga fora o efeito que se foi buscar.
2. **A tecla é interruptor, e o estado é uma corrida.** Se o personagem já saiu
   do sentado sozinho — levou dano, a macro mandou uma tecla —, o toque de
   "levantar" o **senta**, e senta bem na hora em que ele precisa reagir.

### O que ficou no lugar

`_levantar()` não existe, e com ele foram embora `_sentado_por_nos` e
`_avisou_estado_ilegivel`, que só existiam para alimentá-lo. O `finally` que
levantava a vítima ao fim da espera da Fada também saiu, pelo mesmo motivo.

Sobrou UMA leitura de `is_sitting`, e ela tem um propósito estreito: **não
apertar a tecla se o personagem já está sentado**, porque aí o toque o
levantaria. Nada mais.

**Já foi restaurado uma vez por engano** (01/09/2026): os testes de
`test_cura_do_app.py` reprovaram em doze casos depois da remoção manual, os
docstrings antigos pareciam fundamentados, e o `_levantar` voltou. Foi preciso o
usuário dizer a mecânica de novo. Se aparecer um teste exigindo `sentado is
False` ao fim da cura, ele é desta safra — a regra é a de cima.

**Mas nunca ENTRE uma poção e a outra.** A recuperação acontece com o personagem
sentado; levantar no meio cortaria justamente o efeito que se está esperando.
Travado por `test_NAO_levanta_ENTRE_uma_pocao_e_a_outra`.

## Só se anda ANTES de beber

> *"Caso use a poção não pode andar depois, só deve andar antes de usar a
> poção."*

Depois da poção o personagem está sentado, e um clique no minimapa o levanta e
**cancela a recuperação**. `_voltar_ao_ponto` roda uma vez, antes de `_curar`, e
nenhuma rotina de cura chama `voltar_para_base` — travado por um teste de AST
sobre `_curar`, `_curar_com_pocao`, `_curar_sentado` e `_levantar`.

## A conferência de batalha durante os 15 s

O pedido foi *"de 1 em 1 segundo"*. O que existe é **0,1 s** — dez vezes mais
frequente, e cada volta custa uma leitura de memória de ~1 µs. Encurtar a reação
ao mob é o ponto inteiro da cura, então a cadência ficou como estava.

---

# A VOLTA DO APP, REDESENHADA (25/08/2026)

Sessão de grilling motivada por *"não está ficando como eu quero"*. Quatro
mudanças, e uma delas **reverte uma decisão minha**.

## A ordem mudou

```
ANTES:  TAB → pet → comida → voltar ao ponto (anda!) → linha 1 → linha 2 ...
AGORA:  pet → comida → voltar ao ponto → TAB → linha 1 → linha 2 ...
```

> *"As conferências têm que ser antes do TAB, então verifica primeiro, TAB
> depois; o TAB tem que vir logo antes da macro."*

O TAB era a **primeira** coisa da volta: o bot adquiria o alvo e só então gastava
tempo com pet e caminhada — com o mob novo batendo de graça nesse meio-tempo. Era
o sintoma relatado: *"mata e demora para começar a bater no próximo"*.

## Sem alvo vivo, a macro não roda — REVERSÃO

> *"Caso o mob esteja morto não faz sentido rodar a macro, tem que ir para o
> próximo MOB; só vale a pena rodar macro em mob vivo."*

Eu tinha decidido que o TAB **não** bloqueia a volta, argumentando que macro de
buff ou de pesca não poderia parar por falta de alvo. O usuário respondeu que a
macro do APP é **só ataque** — e com isso minha decisão estava errada.

Rodar a rotação sem alvo vivo é desperdício puro **e é o que produz a mensagem
de "skill inválida" na tela do jogo**, que era o sintoma (c) do relato.

Agora: sem alvo vivo confirmado, nenhuma tecla sai. O laço espera
`ESPERA_SEM_ALVO = 0.3` e tenta o TAB na volta seguinte — sem essa pausa o
`rodar()` giraria sem parar perguntando a memória, e um APP parado custaria uma
CPU inteira.

**O pet, a comida e a volta ao ponto continuam rodando**: eles vêm antes do TAB.

## A régua do alvo INALCANÇÁVEL — o mob do penhasco

> *"Caso esteja tentando bater no target e a vida dele não sair do zero, passa
> para o próximo target — pode acontecer de, por exemplo, estar em um penhasco e
> dar target lá no mob de baixo, e o jogo não deixar atacar."*

| | |
|---|---|
| referência | o **primeiro HP lido** do alvo, fixado na AQUISIÇÃO |
| gatilho | `LINHAS_SEM_DANO_PARA_TROCAR = 3` linhas sem o HP mudar (era 2 ate 26/08/2026) |
| conta por | **linha da macro**, não por skill de ataque (decisão do usuário) |
| atravessa rotações | sim — o contador é do ALVO |
| zera quando | o HP cai, ou o alvo troca |
| HP ilegível | não conta — "não sei" nunca larga alvo |

**A referência nasce na aquisição, não na primeira conferência.** Se nascesse na
conferência, ela consumiria a primeira linha da macro e a regra do usuário
viraria três linhas na prática.

**A troca é FORÇADA** (`_garantir_alvo(forcar=True)`): o mob está vivo, então o
atalho "alvo vivo, não mexe" impediria a troca.

**Não se guarda lista de inalcançáveis**, e a razão é do usuário: *"os IDs podem
mudar e acabar percebendo errado"*. Uma lista velha faria o bot pular mob bom; se
o mob voltar na roda, o bot descobre de novo em 2 linhas.

## Os DOIS respiros em volta do TAB

> *"Dá uns 500ms depois do TAB para começar a rodar a macro, só para garantir
> que vai começar da linha 1; às vezes está sendo muito rápido."* (25/08/2026)
>
> *"Após o tab em vez de 500ms pode colocar 1 segundo inteiro."* — *"e adiciona
> 600ms antes do tab."* (26/08/2026)

Mesmo caso do botão "Sell" na venda: a tecla seguinte chega enquanto o cliente
ainda digere a anterior, e se perde. O que muda é o que se perde de cada lado:

| respiro | constante | o que se perde sem ele |
|---|---|---|
| ANTES do TAB | `ESPERA_ANTES_DO_TAB` | a **própria aquisição** — o TAB chega em cima das últimas teclas da macro e é engolido, e aí o bot roda mais uma volta inteira contra o cadáver |
| DEPOIS do TAB | `ESPERA_DEPOIS_DO_TAB` | a **primeira skill da rotação** — a que abre a luta |

Os valores são **observação de campo, não medição instrumentada**: é o usuário
vendo a tecla se perder. O de baixo já foi de meio segundo para um segundo
inteiro por esse mesmo caminho.

**SÓ SÃO PAGOS QUANDO UMA TECLA VAI SAIR.** Alvo vivo na mira não gasta nada:
não houve tecla, não há o que assentar. É isso que torna 1,6 s barato — o custo
é uma vez por **mob morto**, não uma vez por volta da macro.

### O de cima é pago UMA VEZ por aquisição, nunca por tecla

A roda do TAB gira até `TENTATIVAS_DE_TAB` vezes. Cobrar 0,6 s em cada salto
somaria ~4,8 s por volta num ponto cheio de cadáveres — sem comprar nada.

O que este respiro resolve é a colisão com as teclas da **macro**, e essas só
existem antes do PRIMEIRO salto. Entre saltos já há espaçamento de sobra:
`_esperar_o_alvo_trocar` só devolve quando o id **mudou**, ou seja, quando o TAB
anterior foi PROCESSADO. Um TAB nunca chega em cima de outro TAB pendente.

### E eles deixaram de ser espera CEGA

Eram `time.sleep`. Com 1,6 s por aquisição isso vira bot mudo por mob morto, e a
regra do projeto é que o Parar responda na hora.

**Não dá para usar `_esperar` aqui**, e o motivo é sutil: ele confere a morte do
alvo lá dentro (`_cortar_a_volta`), o que está certo no meio da macro e errado na
aquisição — o alvo selecionado nesse instante é justamente o cadáver que se está
tentando largar, então ele devolveria "pare" no primeiro décimo de segundo. Daí
`_dormir`, que fatia e pergunta uma coisa só: é para continuar?

## O que NÃO mudou, e foi verificado

**A macro já recomeçava da linha 1.** `uma_volta()` itera os passos do começo, e
não existe índice guardado em lugar nenhum. O que dava a impressão de "continuar
de onde parou" era o tempo gasto entre o TAB e a primeira linha — pet, comida e
caminhada, que agora vêm antes.

## O que ficou EM INVESTIGAÇÃO — **RESOLVIDO em 26/08/2026**

> **Histórico.** A dúvida abaixo foi respondida: a entidade **some e volta** do
> array com o corpo ainda selecionável, e era isso que prendia o bot no cadáver.
> O conserto não foi "tratar sumiço como morte" (largaria mob vivo), e sim a
> reserva pela flag de combate mais o escape por ignorância persistente — ver
> "A revisão do Core Loop de 26/08/2026", no fim deste arquivo.

### A dúvida, como estava escrita

O sintoma (c) tem duas causas possíveis e só uma foi consertada (o TAB
confirmando pela troca do id). A outra é: **a entidade pode SAIR do array quando
o mob morre** — e aí `alvo_atual()` devolve `None`, `_alvo_morreu()` responde
`False` por precaução, e o bot bate no cadáver até o TAB.

Não dá para escolher no escuro: `None` também acontece por 1 leitura em ~45 logo
depois de selecionar (medido). Enquanto a medição não existe, a resposta segura é
`False` — dizer que morreu largaria mob vivo — e o que se faz é **deixar rastro**:
uma linha de log por ocorrência, que rearma quando a entidade volta.

Se essa linha aparecer **sempre logo depois de matar**, a hipótese está
confirmada e o conserto é tratar "sumiu do array" como morte.

---

## O DEFEITO QUE MATOU O PERSONAGEM (25/08/2026)

> *"Tem que garantir que a vida está zero, pois eu acompanhei que **trocou de
> target sem ter matado o target**, agora nessa última versão, fazendo que o
> personagem morresse."*

**Era a régua do inalcançável — peça que eu construí no dia anterior, a pedido
dele.** Ela troca de alvo **com o mob vivo**, por desenho. E numa macro de
linhas curtas, duas linhas passam em menos de um segundo — antes de o servidor
registrar o primeiro golpe.

O resultado: o bot largava um mob que **estava sendo morto**, o mob largado
continuava batendo, e o personagem morria.

### A trava: a régua só pode disparar em alvo NUNCA TOCADO

> **O CÓDIGO ABAIXO NÃO EXISTE MAIS** (26/08/2026). O portão perguntava ao
> `max_hp`, e isso deixou de servir quando o bot passou a adquirir mobs
> machucados: o mob do penhasco chega machucado e ficaria imune à régua. Hoje a
> pergunta é sobre a AQUISIÇÃO (`_ja_tirou_vida`), o que diz a mesma coisa sem o
> buraco. O parágrafo fica pelo raciocínio, que continua valendo inteiro.

```python
if not maximo or hp < maximo:
    return False        # já machucou => dá para acertar => a régua cala
```

Se o alvo está **inteiro** depois de N linhas, não é atraso de servidor — é
alcance, e é o mob do penhasco. Machucou um ponto que seja? Então dá para
acertar, e o que está acontecendo é outra coisa (recarga, resistência, atraso).

A regra do usuário continua funcionando para o caso que ela existe para
resolver, e **não pode mais largar um mob em luta**.

### De brinde: a régua lia a memória DUAS vezes por linha

A primeira versão lia o alvo e depois chamava `_alvo_esta_inteiro()`, que lia de
novo. Duas fotos de instantes diferentes respondendo à mesma pergunta é como
nascem as decisões que ninguém consegue reproduzir. Agora ela usa o alvo que já
leu.

## Só se engaja alvo INTEIRO (100/100) — **REVOGADO em 26/08/2026**

> **Esta seção é histórica.** O usuário revogou a exigência no dia seguinte, e
> o porquê medido está no fim deste arquivo, em "A revisão do Core Loop de
> 26/08/2026". `EXIGIR_ALVO_INTEIRO` hoje é `False`.

> *"TAB → adquiriu target novo com 100/100 de HP (se não, dá TAB novamente) →
> 500ms → linha 1."*

`EXIGIR_ALVO_INTEIRO = True`. O critério de aceitação de um alvo **novo** deixou
de ser "está vivo" e passou a ser "está inteiro". Mob a 60/100 ou é luta de
outro jogador, ou é cadáver de daqui a pouco — **entrar numa luta pela metade é
herdar o aggro sem herdar o progresso**.

**Vale só para AQUISIÇÃO.** O alvo que já está na mira e machucado **não** é
largado por isso — largar mob no meio da luta é exatamente o defeito acima.

O interruptor existe porque a regra tem custo: num mapa onde os mobs regeneram
devagar, um mob a 99/100 seria recusado para sempre.

## O ciclo completo, como ficou (atualizado em 26/08/2026)

```
SAIU DE BATALHA?  não → pula pet, comida e caminhada (conferência é só fora)
    → pet → comida → voltar ao ponto (só se andou, teto 2 s)
    → 600 ms  (só se um TAB vai sair, e UMA vez por aquisição)
    → TAB → o id MUDOU e o alvo está VIVO?
              não → 350 ms → TAB de novo, e SÓ MAIS UM (a roda é por distância)
              nem no segundo → espera 3 s a roda reiniciar e tenta de novo
                               na volta seguinte, DO MAIS PERTO
    → a LINHA 0 da macro (padrão 1 s, editável na tela)
    → linha 1 → linha 2 → ...
         a cada linha: o alvo morreu?
              HP legível <= 0            → sim, na primeira leitura
              HP ilegível + batalha caiu → sim, pela reserva
              sim → corta a volta e recomeça o ciclo (NÃO conta como volta)
         a cada linha: 3 linhas sem tirar vida desde a AQUISIÇÃO?
              sim → inalcançável: marca o id, termina a volta, e quem
                    adquire é o passo do TAB da volta seguinte
    → morreu? 1 s de respiro antes do ciclo seguinte (a flag de combate
              precisa de um instante para baixar)
    → e a conferência dos 30% de vida roda ao fim de cada volta
```

---

# A revisão do Core Loop de 26/08/2026 — o porquê medido

Esta seção é o **porquê**; a especificação está em `docs/REGRAS.md`
§ "O laço do APP depois de 26/08/2026", e a regra resumida no `CLAUDE.md`.

## O que o usuário relatou, e o que o log provou

Dois sintomas em dias seguidos:

* **25/08** — o bot bate em cadáver e não sai mais dele.
* **26/08** — *"começou a ficar andando e dando tab, chamou vários mobs e
  morreu, aí eu parei o bot do APP"*.

O usuário avisou que o log **não deve ser levado em consideração como retrato do
comportamento atual**, e está certo: o segundo sintoma é de uma versão posterior
à que produziu aquele arquivo. Mas o log continua valendo como **prova de um
mecanismo**, e é nesse papel que ele foi usado aqui.

### Como o defeito foi localizado — o método vale mais que o caso

Não foi lendo o log cronologicamente; 1,5 MB não revela nada assim. Foi em duas
linhas de shell:

1. **agregar por frequência** (extrair só a mensagem, `sort | uniq -c | sort -rn`)
   para achar o que domina;
2. **procurar pares contraditórios** de mensagens na mesma sessão.

A primeira deu a razão `1251 : 5` entre "alvo com 0/100" e "alvo novo, começando
a macro da linha 1" — o defeito se nomeou sozinho. A segunda expôs um **segundo
defeito que ninguém procurava**: 4 avisos de "acabaram as poções" na mesma
sessão de 3 curas bem-sucedidas com 2 poções cada.

Só depois disso a janela cronológica foi aberta, e ela mediu a **cadência**: uma
linha a cada ~21 s de 13:42:51 a 14:10:01, com a macro configurada em 14 linhas
/ 13000 ms. Cadência de metrônomo é laço; cadência irregular seria reação a
evento externo.

**O princípio:** num log de laço, a distribuição de frequências é o diagnóstico
e a ordem cronológica é a confirmação. Duas mensagens que se contradizem na
mesma sessão provam que o código chegou a duas conclusões opostas sobre o mesmo
estado — a assinatura de uma leitura não-determinística.

## Defeito 1: o estado absorvente do cadáver

`_alvo_morreu()` respondia `False` quando `alvo_atual()` devolvia `None`, e
`_garantir_alvo` lia esse `False` como "alvo vivo, não mexe" — saindo **sem
apertar o TAB e sem logar nada**.

A prova de que era ESSE portão: em 28 minutos, **zero** linhas de "a tecla não
pega", **zero** de "sem tecla configurada", **uma** de "girei a roda". O TAB
nunca foi tentado, e esse é o único caminho de saída silencioso.

A prova do não-determinismo: na MESMA volta, `_alvo_morreu()` lia `None` e
milissegundos depois `_registrar_o_alvo()` lia a entidade com `hp=0` e imprimia
a linha. Duas chamadas consecutivas de `alvo_atual()` sobre o mesmo estado, duas
respostas diferentes — a entidade do cadáver some e volta do array enquanto o
corpo continua selecionável.

### Por que "confirmar por N amostras" foi a solução ERRADA

A primeira tentativa exigiu `hp <= 0` em N leituras consecutivas. Ficou pior: o
cadáver deixava de ser reconhecido **na primeira pergunta do início da volta**, e
o portão de `_garantir_alvo` voltava a bloquear o TAB. O conserto reintroduziu o
defeito.

**"Absoluto" não quer dizer "ler várias vezes".** `alvo_atual()` já valida
`0 <= hp <= max_hp` antes de responder, então um HP legível não é palpite — a lei
do projeto (`hp == 0` é morte, e ponto) já era a regra certa. O que nunca teve
prova é o `None`.

### A reserva: quem decide o `None` é a flag de combate

Decisão do usuário:

> *"caso não consiga identificar a vida você deve usar o `em combate = False`.
> Caso saia do True e fique False, é pq saiu de batalha e o mob já está morto.
> Caso não saia, ou não está morto ou tem outro mob batendo no personagem."*

É uma regra sobre **transição**, não sobre nível — `em_batalha == False` sozinho
não diz nada, porque o bot passa a maior parte do tempo fora de combate entre um
mob e o outro. E ela é honesta nos dois sentidos: a flag não baixar não prova
nada. **A reserva só sabe dizer "morreu"; ela nunca diz "está vivo".**

Duas consequências de desenho que não são óbvias:

* **o veredito precisa de latch por identidade.** A transição acontece UMA vez;
  sem guardá-la, a pergunta seguinte voltaria a "não sei" e devolveria o bot ao
  mesmo estado absorvente;
* **o `None` da leitura da flag não pode apagar a memória de que o personagem
  estava em batalha**, senão a reserva perde justamente o sinal que ela existe
  para ver.

### E quando nem a reserva tem o que dizer

Com outro mob batendo, a flag nunca baixa. Aí não há prova nenhuma, e a saída não
pode ser declarar morte (seria largar mob vivo). É declarar **ignorância
persistente**: `VOLTAS_COM_ALVO_ILEGIVEL_PARA_TROCAR = 2` voltas inteiras sem uma
única leitura boa deste alvo e o bot troca. **Um alvo que não dá para enxergar
também não dá para saber que está sendo morto.** Uma leitura boa zera o contador
— a entidade some do array por 1 leitura em ~45 com o mob VIVO.

## Defeito 2: o TAB contínuo, e a exigência de alvo inteiro

> *"anteriormente em outra sessão eu tinha falado que precisava estar com a vida
> 100/100, mas não precisa, pode ser qualquer vida, o importante é ser um alvo
> DIFERENTE."*

`EXIGIR_ALVO_INTEIRO` foi de `True` para `False`. O mecanismo do sintoma é
direto: num ponto de farm movimentado quase todo mob da roda está machucado
(outro jogador batendo, regeneração parcial, o próprio bot tendo largado antes).
Com a exigência ligada, `_garantir_alvo` recusava **todos**, girava as
`TENTATIVAS_DE_TAB` inteiras, devolvia `False`, e a volta seguinte recomeçava a
roda. TAB contínuo sem nunca engajar — **e cada TAB é um mob a mais olhando para
o personagem**.

Somado ao shuffle anti-AFK saindo andando sem perguntar se havia combate, dá
exatamente *"ficar andando e dando tab, chamou vários mobs e morreu"*.

## O portão `hp >= max_hp` da régua, e o que o substituiu

O portão exigia o alvo INTEIRO para a régua poder largá-lo. Ele era a trava
contra o defeito que **matou o personagem** em 25/08: duas linhas curtas passam
antes de o servidor registrar o primeiro golpe, e o bot largava um mob que estava
sendo morto.

**Ele não pôde ficar.** Com mobs machucados sendo adquiridos, o mob do penhasco
chega machucado — e o portão o tornaria imune à régua, que é justamente quem ela
existe para largar.

O substituto é `_ja_tirou_vida`, e diz a MESMA coisa ancorada na **aquisição** em
vez do máximo:

| situação | veredito |
|---|---|
| adquirido a 100, ainda 100 após 3 linhas | LARGA |
| adquirido a 60, ainda 60 após 3 linhas | LARGA |
| adquirido a 100, ferido para 97, parado em 97 | CALA para sempre |
| HP ilegível | não conta, nem a favor nem contra |

Mais a terceira linha (`LINHAS_SEM_DANO_PARA_TROCAR` de 2 para 3), que o usuário
pediu para alargar a margem.

**A régua também parou de adquirir.** Ela chamava `_garantir_alvo(forcar=True)`
de dentro do laço das linhas: o alvo novo era adquirido no meio da volta, e só
então a volta seguinte gastava pet, comida e até 2 s de caminhada antes da linha
1 — com o mob recém-chamado batendo de graça o tempo todo. É o mesmo defeito que
a reordenação de 25/08 tinha consertado, reintroduzido por uma porta lateral.

Hoje ela **marca UM id** e termina a volta. A marca é gasta na volta seguinte e
apagada — nunca uma lista de ignorados, porque *"os IDs podem mudar e acabar
percebendo errado"*.

## Defeito 3: `is_sitting()` não sabia dizer "não sei"

O contrato tri-estado estava documentado com todo cuidado no **consumidor**
(`_a_pocao_saiu`, com um bloco inteiro explicando que `None` não é "não saiu"). A
**fonte** devolvia `bool` puro: falha de leitura virava `False`.

Resultado: o ramo `ilegivel` era código inalcançável, e toda leitura falha
produzia o veredito "acabaram as poções" — 4 vezes numa sessão em que as poções
demonstravelmente existiam.

Nenhum teste pegou porque os testes do consumidor injetam a leitura por `lambda`.
**A lição, que vale para qualquer leitura externa:** contrato de tri-estado
documentado no consumidor é *expectativa*; a prova mora na fonte.

Dois consertos vieram junto:

* **da segunda poção em diante a prova não vale.** Ele já está sentado pela
  primeira, então "está sentado" não prova que a tecla saiu — seria dar por boa
  uma tecla apertada contra a bolsa vazia. O estado é lido ANTES de apertar e a
  prova só é aceita quando ele estava de pé;
* **com a leitura ilegível (`None`), senta assim mesmo — uma vez.** O erro é
  barato e assimétrico: de pé, o toque senta e ganha-se a regeneração; já
  sentado, o toque levanta e perde-se ela, mas nada trava. O que não pode é
  apertar duas vezes e voltar à estaca zero. (A reserva `_sentado_por_nos` que
  existia aqui era do `_levantar()`, e saiu com ele.)

## Os contadores

`self.voltas` alimenta a limpeza de bolsa (`voltas % a_cada`) e o shuffle
anti-AFK. Antes, **todos** os caminhos de saída de `uma_volta()` o incrementavam,
inclusive o corte por morte e o abandono do mob do penhasco — e num ponto de farm
com muita morte os dois consumidores disparavam cedo demais.

> *"A contagem de voltas não deve levar em consideração os mobs que não conseguir
> atacar como os do penhasco."*

Hoje `voltas` só é incrementado no fim natural do laço; os abortos vão para
`voltas_abortadas`, `mortes_vistas` (com trava por identidade, porque o cadáver
fica selecionável 7 a 13 s) e `alvos_inalcancaveis`.

A trava da morte é por **identidade e não por relógio**: curta demais conta duas
vezes, longa demais engole a morte seguinte. E ela trava só a CONTAGEM — travar o
veredito faria `_garantir_alvo` reler "alvo vivo" no cadáver já contado e
bloquear o TAB de novo.

---

# O refino de 26/08/2026 — "o funcionamento está bom, só precisamos refinar"

Três pedidos do usuário na mesma conversa, todos sobre a **mesma coisa**: o bot
estava puxando mobs demais e se colocando em risco.

## 1. A roda do TAB é ordenada por DISTÂNCIA

> *"Ainda está se perdendo no tab. O ideal é tentar manter só no PRIMEIRO tab,
> para evitar ficar indo em mobs muito longes, pq o tab vai primeiro no mob MAIS
> PERTO e conforme vai clicando ele vai indo nos mobs mais LONGES."*

**Este é o achado que derruba o desenho anterior**, e vale mais que o número que
saiu dele. `TENTATIVAS_DE_TAB` era 8, com o seguinte raciocínio escrito no
código:

> *"CICLAR É BARATO. Cada salto que TROCA o alvo sai na hora — a espera devolve
> no instante em que o id muda. Oito saltos por cadáveres custam milissegundos."*

O raciocínio está correto e **mede a coisa errada**. O custo de um salto nunca
foi o tempo dele: é **para onde ele leva**. Cada salto é um mob mais longe, e
engajar um mob longe faz o personagem atravessar o ponto de farm até ele —
puxando o que estiver no caminho. A roda de oito era o motor do *"chamou vários
mobs e morreu"*.

**A lição de método:** quando uma constante é justificada por um custo, vale
perguntar se aquele é o custo que importa. Aqui havia uma justificativa
quantificada, plausível e escrita com cuidado — apontando para a métrica errada.

### Por que dois, e não um

O ideal do usuário é um salto só. O obstáculo é concreto: **o cadáver do mob que
o bot acabou de matar está encostado nele**, logo é o PRIMEIRO da roda, e fica
selecionável de 7 a 13 s (medido em 20/08/2026). Com um salto só, toda aquisição
depois de uma morte falharia até o corpo sumir.

O segundo salto existe para passar por esse corpo, **não para varrer o ponto de
farm**. Se um dia o cadáver deixar de entrar na roda, o número certo passa a ser
1 e a mudança é de um dígito.

### Quando dois não bastam

Não se insiste mais longe. A volta acaba, o bot paga
`SEGUNDOS_PARA_A_RODA_REINICIAR` e a volta seguinte recomeça a aquisição **do mob
mais perto**. É a pausa que devolve a roda ao começo — sem ela, a volta seguinte
apertaria o TAB com a roda ainda adiantada e pegaria um mob ainda mais longe,
que é exatamente o que os dois saltos existem para impedir.

**O 3,0 s não tem medição atrás**, e isso está dito no próprio código: ninguém
mediu em quanto tempo a roda deste cliente reinicia. É folga confortável e
barata — só é paga quando não houve alvo.

## 2. Em batalha o personagem não anda

> *"É bom ter essas delays e deixar os 2 segundos de retorno para o lugar, A
> MENOS QUE ESTEJA EM BATALHA é claro."*

`SEGUNDOS_PARA_A_TRAVA_DEVOLVER` **continua em 2,0 s**. O pedido não é andar
menos, é não andar na hora errada: atravessar o ponto de farm com um mob em cima
faz ele acompanhar e passar por outros, e o personagem chega na base com três em
cima em vez de um.

A guarda cobre as **duas** ações que tiram o personagem do lugar — a caminhada de
volta e o shuffle anti-AFK — pelo mesmo `_lutando()`. Se cada uma tivesse a
própria régua, uma delas ficaria para trás no conserto seguinte.

Ele pergunta a duas fontes e basta UMA dizer que há luta, porque elas falham em
momentos diferentes: a flag de combate demora a subir no primeiro golpe, e o alvo
some do array por uma leitura em ~45.

**"Não sei" vale FALSE**, e aqui isso é deliberado — o oposto da regra usual
deste projeto. A resposta serve para SUPRIMIR uma ação; se "não sei" suprimisse,
um cliente sem leitura de memória nunca voltaria ao ponto e derivaria pelo mapa,
que é pior que voltar na hora errada. **A pergunta certa não é "qual é o padrão
do projeto", é "qual erro custa mais neste ponto".**

## 3. O respiro depois da morte

> *"Está trocando de alvo rápido demais, aí acaba colocando o personagem em
> risco."*

`ESPERA_DEPOIS_DA_MORTE = 1.0`, pago só quando um mob caiu.

Ele entrou como cautela e **acabou tendo trabalho técnico**, o que é o melhor
argumento a favor dele: no instante seguinte ao golpe que mata, a flag de combate
ainda está em `True` — o jogo leva um momento para baixar. Neste laço, duas
decisões dependem dessa flag:

* a caminhada de volta ao ponto, que agora não sai em batalha;
* o portão da cura, que espera sair de batalha para beber.

Sem o respiro, as duas leem "ainda em batalha" logo depois de uma morte limpa: a
caminhada é suprimida sem motivo e a cura adia sem motivo. O respiro que o
usuário pediu por instinto é o mesmo que o código precisava por leitura de
estado.

## 4. E os saltos deixaram de sair em rajada

`ESPERA_ENTRE_TABS = 0.35`, entre um salto e o outro.
`_esperar_o_alvo_trocar` devolve no instante em que o id muda, então dois saltos
podiam sair em menos de um décimo de segundo.

É **menor** que `ESPERA_ANTES_DO_TAB` de propósito, e não pode crescer muito: se
passar do tempo de reinício da roda do jogo, o segundo salto voltaria ao primeiro
mob em vez de avançar — e a aquisição depois de uma morte pararia no próprio
cadáver.

## O que NÃO mudou, e por quê

**As delays de 600 ms e 1 s ficaram** — o usuário confirmou (*"é bom ter essas
delays"*).

**A régua do inalcançável continua em 3 linhas e continua largando o mob do
penhasco.** Ela é o oposto de puxar: ela SOLTA um alvo. Mexer nela por causa
deste refino teria sido confundir dois problemas com sinais contrários.

---

# A linha 0 e o piso de 100 ms — 26/08/2026

## O pedido, e o que ele NÃO é

> *"Como a macro 0, mas sem poder editar o botão e não pode colocar em outro
> lugar, sempre será a primeira, e o tempo sim será editável; aquele 1 segundo
> após o tab será isso."*

Levantado antes de implementar, e vale registrar porque era o risco real da
conversa: **isto não devolve o TAB para dentro da macro**. O TAB como linha 1 era
apertado toda volta, inclusive no meio da luta, e largava o mob machucado — foi
o defeito que a virada de 25/08/2026 consertou.

A linha 0 dá duas coisas que faltavam: **visibilidade** (ver na tela que o TAB
acontece, e onde) e **controle do tempo**. Quem decide *quando* apertá-lo
continua sendo o bot, lendo a memória.

## Por que ela não é um `AppStep`

Perguntei e a resposta foi *"indiferente, faça da forma que for melhor para o
sistema"*. Ficou fora da lista `steps`, e o motivo é concreto: como linha de
verdade ela obrigaria quatro lugares a conhecer uma exceção —
`passos_ativos` (que a filtraria), `uma_volta` (que pularia a tecla dela), a
régua do inalcançável (que conta **linhas da macro** e passaria a contar uma que
não bate em ninguém) e a prévia da tela.

O critério que decidiu: o usuário disse que ela **não é editável e não é
movível**. Ou seja, ela já não se comporta como linha — "parece linha" é
requisito de tela, "é linha" seria requisito de execução.

Na web isso vira uma coisa só: a linha 0 **não tem a classe `app-linha`**, e os
dois seletores que montam `steps` e a prévia filtram por essa classe. Um teste
confere que não sobrou nenhum seletor pegando todas as linhas — se um sobrasse,
o TAB voltaria a ser enviado no meio da rotação.

## A tecla é espelho, não cópia

`KeyBinds.next_target` já existia e já era configurável na aba Teclas desde
sempre — compartilhada com o BC, porque **tecla descreve o JOGO, não o
ecossistema**. A linha 0 mostra essa tecla desabilitada.

Escrever `TAB` fixo na tela era a alternativa óbvia e é a errada: quem trocou a
tecla veria a tela dizer uma coisa e o bot apertar outra. Este projeto já pagou
caro por telas que mentem em silêncio.

## O piso de 100 ms

> *"O mínimo vai ser 100ms em todos os campos do APP."*

Zero deixava duas teclas saírem no mesmo instante, e o cliente engole a segunda —
é o mesmo defeito do botão "Sell" da venda, espalhado pela sequência inteira.

Ele é aplicado em **três camadas**, e a repetição é deliberada:

| camada | o que ela cobre |
|---|---|
| `AppStep.__post_init__` | qualquer linha construída em qualquer lugar |
| `_app_from_dict` e a ponte web | arquivo salvo por versão antiga sobe corrigido |
| os campos das duas telas | o usuário não consegue nem digitar abaixo |

A ponte reaplica o piso de propósito: *"a tela impõe"* não é garantia, é boa
vontade — o JavaScript pode mandar qualquer número.

**O executor guarda a própria cópia do 100**, porque ele não importa
`blazesbot.config` (isolamento travado por `test_o_executor_do_app_so_usa_o_core`).
Um teste confere que as duas cópias batem — é o único jeito de a duplicata não
apodrecer.

## De 16 para 20 linhas

> *"Pode colocar de 1..20 agora, para padronizar em 20 linhas no total."*

`PASSOS_DO_APP = 20`. `_app_from_dict` já normalizava a lista para o número da
constante, então configurações antigas de 16 linhas sobem com quatro linhas
vazias no fim, sem perder nada. A web lê o número da ponte
(`constantes.passos_app`) — o literal no JavaScript é só fallback, e um teste
garante que ele não fica preso no valor velho.

## O que a urgência não paga, e por quê

Perguntado: na urgência (matou e continua em batalha), o tempo da linha 0
continua sendo pago? Resposta: *"continua sendo pago sim, para garantir que não
irá bugar, mas daí não faz as verificações, pois verificação é só fora de
batalha."*

Ficou assim:

| tempo | urgência paga? | por quê |
|---|---|---|
| linha 0 (depois do TAB) | **sim** | é o que impede a primeira skill da rotação de se perder; perder a abertura da luta com um mob em cima é pior que gastar o tempo |
| 600 ms antes do TAB | não | existe para o TAB não chegar em cima das teclas da macro, e na urgência a macro foi cortada e a observação já gastou até 3 s |
| 3 s de reinício da roda | não | é otimização de MIRA (voltar ao mob mais perto); com um mob batendo, tentar de novo vale mais que tentar melhor |
| pet, comida, caminhada | não | são cuidados de quem está tranquilo |

E o teto de dois saltos do TAB **não muda na urgência**: *"a ideia não é ter 2
alvos, é ter sempre 1 por vez"*. A urgência mexe na espera entre tentativas,
nunca em quantos mobs o bot chama.

---

# Um único TAB por aquisição — 26/08/2026

> *"Eu quero que seja apenas 1 único tab por vez, pois com essa questão de
> GARANTIR o tab, está fazendo ir em outro mob e não no mais perto."*

`TENTATIVAS_DE_TAB` foi de **8 → 2 → 1** no mesmo dia, e as duas quedas têm
causas diferentes.

## A primeira queda (8 → 2): o custo medido era o errado

O código dizia, com todas as letras:

> *"CICLAR É BARATO. Cada salto que TROCA o alvo sai na hora — a espera devolve
> no instante em que o id muda. Oito saltos por cadáveres custam
> milissegundos."*

Correto, e mede a coisa errada. O custo de um salto não é o tempo dele: é **para
onde ele leva**. A roda é ordenada por distância, então cada salto é um mob mais
longe, e engajar longe faz o personagem atravessar o ponto de farm até lá,
puxando o que estiver no caminho.

## A segunda queda (2 → 1): o meio-termo era o próprio defeito

Eu defendi o segundo salto com um caso concreto: o cadáver do mob recém-morto
está encostado no personagem, é o primeiro da roda, e fica selecionável de 7 a
13 s — sem o segundo salto, toda aquisição depois de uma morte falharia até o
corpo sumir.

O usuário respondeu com o caso que **acontece**, não com o que eu imaginei: o
segundo salto cai no **segundo mob mais próximo**, e isso é literalmente "ir em
outro mob e não no mais perto". O cadáver era a justificativa; o mob distante era
o resultado.

**A lição:** ao defender um passo extra por causa de um caso ruim, vale perguntar
com que frequência o passo cai nesse caso — e com que frequência ele cai em todos
os outros. Eu tinha o caso certo na cabeça e o efeito errado no código.

## O que substitui a garantia

Nada. E é esse o ponto.

Não trouxe mob vivo? A volta acaba sem macro, o bot paga
`SEGUNDOS_PARA_A_RODA_REINICIAR` e tenta de novo na volta seguinte — de novo no
mais perto. **É melhor ficar sem alvo por alguns segundos do que ter o alvo
errado**, porque o alvo errado não custa segundos: custa a travessia do ponto de
farm e os mobs que ela chama.

O caminho de vários saltos ficou como **interruptor**, não foi apagado: subir a
constante religa o espaçamento entre saltos e o resto do laço sem mexer em mais
nada. É a regra do projeto — *"interruptor, não comentário nem apagar"*.

## O efeito colateral no diagnóstico, e o conserto

`TABS_SEM_RESPOSTA_PARA_DESISTIR = 2` contava TABs sem resposta **dentro da
rajada**. Com um salto por aquisição, esse contador nunca chegaria a dois — e
uma tecla mal configurada seria relatada como *"só cadáver por aqui"* para
sempre, mandando o usuário procurar mob onde o problema é a tecla.

O contador passou a viver no objeto, atravessando voltas. E enquanto o veredito
da tecla morta ainda não existe (faltam voltas para confirmar), **o log cala** em
vez de arriscar o diagnóstico errado.

É a mesma regra que atravessa este arquivo inteiro, aplicada ao log em vez de à
decisão: **"não sei" não vira veredito.**


---

# Dois defeitos de campo — 26/08/2026

## 1. A poção que era consumida e cancelada

> *"O primeiro uso da poção está gerando algum problema; ele clica na poção,
> CONSOME ela, mas CANCELA logo em seguida. Não sei exatamente o que está
> acontecendo, mas está funcionando assim."*

Era `mandar_voltar_para_base()`, e o defeito estava escondido atrás de uma linha
de log que dizia a verdade.

A cura chama esse método antes de beber. Ele **clicava sempre** — inclusive com
o personagem parado em cima da base. Um clique direito no minimapa é uma **ordem
de andar**, e uma ordem pendente cancela a bebida no instante seguinte.

O `_voltar_ao_ponto` conferia a distância **depois** e concluía *"cheguei no
ponto inicial; vou me curar"*. Verdade, e tarde: a ordem já tinha saído. No log
de 25/08 essa linha aparece 23 vezes, e nenhuma delas parecia defeito.

A distância passou a ser conferida **antes**: dentro da tolerância, devolve
`True` sem clicar. **"Já estou lá" é sucesso, não falha** — e essa é a parte que
a versão anterior errava, porque `False` ali significa "não havia como voltar" e
faria a cura avisar que vai curar no lugar errado.

`"Não sei"` continua clicando: sem leitura de posição não dá para provar que ele
está no ponto, e curar longe da base é pior que um passo a mais.

**A lição:** um log que afirma o resultado certo pode estar escondendo a ordem
errada. A pergunta não era *"ele chegou?"* — era *"eu mandei ele andar sem
precisar?"*.

## 2. O atraso entre o TAB e a linha 1

> *"Às vezes está existindo alguma delay entre o clicar o TAB e começar a macro,
> e NÃO é a configuração nova que fizemos para o usuário, pois eu testei
> colocando 100ms. O ideal é só dar tab na hora que for para rodar a macro; se
> tiver fazendo alguma verificação, não dê TAB ainda — nós desenhamos a ordem
> para o TAB ser o ÚLTIMO e logo em seguida rodar a macro."*

Ele estava certo em descartar a linha 0. Eram duas causas somadas:

**A cadência da confirmação.** `_esperar_o_alvo_trocar` reusava
`PASSO_DA_ESPERA_DA_BASE` (0,1 s) — a cadência de *"já cheguei na base?"*, um
número pensado para **caminhada**, onde décimos não importam. Aqui custava até
100 ms mortos por aquisição: o jogo processava o TAB em alguns milissegundos e o
bot só olhava de novo no tique seguinte. Virou `PASSO_DA_CONFIRMACAO_DO_TAB =
0.01` — a leitura do id é um `read_int` (~1 µs), então cem perguntas por segundo
não custam nada.

Não é o mesmo número lido por dois lados: são **duas perguntas diferentes**
(*"cheguei?"* e *"trocou?"*), com custos e urgências diferentes.

**A ordem interna da aquisição.** A régua do dano e a linha de log ficavam
**depois** do respiro — ou seja, entre o fim da espera e a primeira tecla. São
baratas, mas o log escreve em disco, e qualquer coisa ali contraria o desenho
que o usuário descreveu. Agora o respiro é a **última** coisa que acontece na
aquisição, e ele encosta na linha 1.

De brinde, duas economias no trecho mais sensível do laço: a régua recebe o
`alvo` que quem chamou já tinha (uma leitura a menos, e sem duas fotos de
instantes diferentes), e a linha *"APP alvo: ..."* deixou de sair duplicada logo
depois de *"alvo novo ..."* — mesma informação, duas escritas em disco.

## 3. E a janela de observação virou 2 s

> *"Após notar a morte do mob ficando com 0 de HP, dá 2 segundos para sair de
> batalha. Como eu falei, TUDO deve ser feito só após sair de batalha."*

`SEGUNDOS_OBSERVANDO_DEPOIS_DA_MORTE = 2.0` (começou em 3). Continua sendo teto,
não gasto: a morte limpa sai no instante em que a flag baixa.


---

# O alvo do APP passou a vir pelo mesmo caminho do BC — 26/08/2026

> *"Sobre o HP do target, está sendo analisado como fazemos no Gun Witch? Pois
> lá funciona perfeitamente a análise do HP, nome, level e todas as informações
> do mob."*

**Não estava.** As duas leituras terminam em `Memory.alvo_atual()`, mas o
caminho até lá era diferente — e a diferença era um portão.

| | BC | APP (antes) |
|---|---|---|
| caminho | `TargetHybrid.entidade_do_alvo(pid)` | `_ler(memoria_do_pet.alvo_atual)` |
| portão | nenhum | **`critical_ok()`** |
| reabre no relogin | sim (`_processo` compara o PID) | não |

## O portão que não tinha nada a ver com o alvo

`_ler` é o embrulho que o supervisor usa para todas as leituras do modo APP:

```python
def _ler(funcao, *args):
    if memoria_do_pet is None:
        return None
    try:
        if not memoria_do_pet.critical_ok():
            return None
        return funcao(*args)
    except Exception:
        return None
```

E `critical_ok()` exige três coisas **do personagem**:

```python
return (self.hp() is not None
        and self.position() is not None
        and self.max_hp() is not None)
```

Nenhuma delas tem relação com o alvo. E `position()` é uma cadeia de ponteiros —
a leitura mais frágil desta família. **Uma leitura ruim da posição do personagem
vetava a leitura do mob**, e o executor recebia `None`: exatamente o mesmo
`None` de *"a entidade sumiu do array"*.

Ou seja, o APP caía na reserva pela flag de combate e no escape de "alvo
ilegível" em situações onde o BC lia nome, HP, nível e posição sem hesitar. Os
mecanismos estavam certos; a fonte é que estava sendo vetada por uma pergunta de
outra área.

## O que o `TargetHybrid` traz de brinde

**Ele reabre o processo quando o PID muda.** Relogin troca o PID, e um handle
guardado vira leitura de processo morto — em silêncio, que é o pior modo. O
`Memory` do modo APP é aberto uma vez no começo de `_rodar_modo_app` e nunca
mais; o híbrido compara o PID a cada leitura.

Ele abre o **próprio** handle, o que é o mesmo arranjo que o BC já usa
(`ctx.memory` de um lado, o híbrido do outro), e é fechado no mesmo `finally`.

## O que NÃO mudou

O portão continua valendo para o que ele foi feito: as leituras do
**personagem** — vida, batalha, sentado, posição, pet. Ali `critical_ok()` é uma
sanidade legítima, porque são campos da mesma struct.

E o APP continua **sem a reserva da tela**: `TargetHybrid.ler()` (com barra e
`EnemyDead.png`) não é usado aqui, só `entidade_do_alvo` e `id_do_alvo`, que são
memória pura. Isso é de propósito — o modo APP existe para funcionar sem
captura.

## A lição

As duas pontas usavam a "mesma leitura" e produziam resultados diferentes. O
defeito não estava na função lida nem em quem lia: estava no **embrulho** que
alguém tinha posto no meio, por um bom motivo, para outra pergunta.

Quando dois caminhos deveriam concordar e não concordam, vale comparar o
caminho INTEIRO — não só o destino.

---

# A volta ao simples — 26/08/2026

> *"Tá só piorando as coisas, vamos voltar ao simples. Deixa as funções que
> fizemos aí paradas sem uso, para testar outra hora. O que vamos fazer: você
> vai dar TAB, deixar rodar a macro até o final, só para a macro no meio se SAIR
> DE BATALHA. Não verifica mais vida, não verifica mais nada. As únicas coisas
> que se mantêm são as verificações fora de batalha e a poção de vida nos 30%
> de HP."*

## O laço, inteiro

```
FORA de batalha  -> pet, comida, voltar ao ponto, TAB, roda a macro
EM batalha       -> roda a macro de novo, sem TAB e sem conferência
saiu de batalha  -> corta a macro no meio, volta ao topo
vida < 30%       -> a cura, entre voltas (inalterada)
```

Uma pergunta só: **"estou em batalha?"** — e ela vem da struct do PERSONAGEM,
que foi a única leitura que não falhou uma vez sequer em nenhuma das medições de
25 e 26/08.

## Por que ele é mais seguro que o laço que substituiu

**Em batalha o bot não dá TAB.** Não existe caminho onde ele larga um mob de pé
— e esse era o defeito que matou o personagem em 25/08, o mesmo que voltou por
uma porta lateral (a régua adquirindo de dentro do laço das linhas) e que exigiu
três consertos separados.

Aqui ele não é *impedido*: ele é **impossível**. A única coisa que autoriza o
TAB é a luta ter acabado.

**E o mob do penhasco se resolve sozinho.** O bot TABa nele, roda a macro, nunca
entra em batalha, chega ao fim da volta ainda fora de batalha — e TABa de novo.
A régua que precisou de três versões, um portão `hp >= max_hp`, uma âncora na
aquisição e uma morte de personagem para ficar de pé virou **consequência de não
existir**.

## O que isso custou

Honestamente: o bot deixou de saber **em que** está batendo. O log não traz mais
nome, nível e HP do alvo, e a estatística de mortes não existe no laço simples.

Foi decisão consciente do usuário, e ela tem um argumento forte atrás: a leitura
do alvo só responde por um subconjunto dos mobs (item 41), e um bot que **acha**
que sabe do alvo decide errado com mais confiança do que um que não pergunta.

## O que ficou parado, e por que não foi apagado

`LACO_SIMPLES = True` no topo do executor. As peças abaixo continuam no arquivo,
inteiras:

| peça | o que ela resolvia |
|---|---|
| `_alvo_morreu` + `MorteDoAlvo` | morte pelo HP da memória |
| `_olhar_a_tela`, `_vida_do_alvo` | a segunda porta (barra desenhada) |
| `_linhas_cegas`, `_esperar_cego` | o pedágio das 3 linhas |
| `_alvo_intocavel` | a régua do mob do penhasco |
| `_alvo_aceitavel`, `_esperar_o_alvo_trocar` | a conferência do TAB pelo id |
| `_alvo_ilegivel_demais` | o escape do "não sei" persistente |
| `_observar_depois_da_morte`, `_urgir` | a urgência do segundo mob |

**Interruptor, não comentário nem apagar** — é a regra do projeto, e aqui ela
vale duplamente: cada uma dessas peças custou uma medição, e várias custaram um
personagem. Apagar jogaria fora o aprendizado junto com o código.

`tests/test_tab_no_app.py` desliga o interruptor na fixture e continua
exercitando o laço antigo inteiro. **Religar é trocar um `True` por um `False`,
e 134 testes voltam a valer para o código que roda** — cada um citando a medição
que o justificou.

## A lição desta sequência inteira

Entre 25 e 26/08 este laço ganhou: confirmação de morte por amostras (revertida),
exigência de alvo inteiro (revogada), reserva pela flag de combate, escape de
"não sei", urgência, segunda porta pela tela, pedágio de 3 linhas cegas. Cada uma
consertava um defeito real e media o que prometia medir.

**E o conjunto ficou pior que a soma.** O usuário viu isso antes de mim, e o
sinal foi o mais confiável que existe: *"tá só piorando as coisas"* — dito por
quem estava olhando o bot rodar, não o código.

Quando cada conserto é defensável e o resultado piora, o problema não está em
nenhum deles: está em quantos são. A resposta não é escolher qual remover — é
recomeçar do laço que cabe na cabeça e devolver as peças **uma de cada vez, com
medição**, se e quando a falta delas aparecer.
