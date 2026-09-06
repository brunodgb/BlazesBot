# A coleira dos 12: por que ela mora na AQUISIÇÃO

**04/09/2026.** Regra pedida pelo usuário e implementada duas vezes no mesmo dia
— a primeira versão matou personagens em campo. Este documento é o porquê
medido, para ninguém "melhorar" de volta.

## O pedido

> *"No APP, você deve impedir do personagem andar mais de 12 pixels do ponto
> inicial, pois tem vezes que o jogo dá bug e dá target em um mob bem longe, só
> que com isso acaba chamando outros mobs e provavelmente vai morrer no caminho
> (...) essa limitação é muito importante para não acabar puxando vários mobs ao
> mesmo tempo por andar para muito longe."*

## A primeira versão, e por que ela travava o bot

Conferia a distância do **personagem** até a base a cada linha da macro e
cortava a volta quando passava de 12, contando que o prelúdio da volta seguinte
(`_travar_posicao_se_preciso`) andasse de volta.

A trava **não anda em batalha** — e não é bug, é invariante medida
(`ANDAR_SO_FORA_DE_BATALHA`): atravessar o spot com um mob em cima faz ele
acompanhar e passar por outros. Pior: `_lutando()` responde `True` para
**qualquer alvo vivo selecionado**, não só para a flag de combate. Durante a
macro quase sempre há um alvo vivo selecionado.

O ciclo que sobrou:

```
linha 1 → distância > 12 → corta a volta
prelúdio → está "lutando" → NÃO anda
TAB? não: `_preciso_de_alvo(lutando=True)` devolve False, o alvo continua
linha 1 → distância > 12 → corta a volta
...
```

Nenhuma tecla sai, então o mob não pode morrer; a trava não anda, então o
personagem não pode voltar. **Travamento permanente, apanhando até morrer.**
Relato do usuário no mesmo dia: *"começou a morrer muito (...) o personagem tem
ficado parado sem atacar"*.

## A versão que ficou

A distância medida passa a ser a do **MOB até a base**, dentro de
`_alvo_aceitavel` — ou seja, **na aquisição**, antes de o personagem correr até
ele. É o único instante em que dá para evitar a caminhada, e recusar não trava
nada: se o alvo não serve, o TAB busca outro.

Depois de engajado vale a regra do usuário, que é mais forte: *"em batalha o
personagem precisa estar atacando e para isso a macro tem que rodar"*. Quem
devolve o personagem ao ponto depois da luta continua sendo a trava de posição,
como sempre foi.

## A válvula

`RECUSAS_POR_DISTANCIA = 3` por rodada de aquisição. Se todos os mobs em volta
estiverem fora do teto (personagem arrastado, base salva no lugar errado, spot
vazio), recusar sem limite deixaria a conta sem atacar nada — a mesma morte por
outro caminho. Passadas as três, o alvo longe é aceito e o comportamento degrada
para o de antes da coleira.

## Os 12 são medidos?

O número é do usuário; o que foi medido é que ele **não atrapalha a rotina**. No
log de 03→04/09/2026, 7 h de APP em duas contas (`blazestpas`, `gamerblazes`):

| medida | valor |
|---|---|
| correções da trava de posição | 28 em 7 h |
| maior distância registrada da base | **10,0** |
| distâncias típicas | 1,4 / 2,0 / 4,5 |
| mobs mortos | ~2.500 por conta (um a cada 6–8 s) |

O teto de 12 fica **acima** do que o farm normal produz: ele recusa a anomalia,
não a rotina.

## O que o log NÃO explica, e continua aberto

No mesmo período cada conta do APP sofreu **2 quedas de conexão**, e cada uma
custou **11 a 16 minutos** presa no laço de relogin: login → servidor → "conexão
interrompida" → fecha → login, a cada ~8,5 s, sem backoff. Enquanto isso o
personagem fica no mundo como fantasma. É um segundo suspeito de morte,
independente da coleira — ver `docs/decisoes/login-e-relogin.md`.


## A terceira versão: a régua é a CORRIDA — 06/09/2026

A 2ª versão (mob contra a base) consertou o travamento e criou outro, mais
silencioso. Medido no log de 05/09, numa hora de farm:

| medida | valor |
|---|---|
| recusas da coleira | **3179** |
| distância mediana do mob recusado (até a BASE) | 113 |
| macros iniciadas no mesmo período | **52** |
| aceites pela válvula | **1** |

O bot passou a hora girando TAB. E como nenhuma volta completava, o contador de
voltas congelava — foi de lá que veio a rajada de limpeza de bolsa (401 dos 407
avisos `BOLSA/DIAGNÓSTICO` dizem `último corte: sem alvo`).

### Por que a base era a régua errada

Ela não distingue **"o mob está longe de mim"** de **"eu estou longe da base"**.
Com o personagem deslocado — o que acontece: às 15:03 ele estava a 188,5 da
base — *todo* mob ao lado dele fica longe da base, e nada é aceitável.

A distância que o usuário sempre descreveu é a **corrida**: *"correr até lá
puxaria mob pelo caminho"*. Ela responde a mesma coisa esteja o personagem no
ponto ou deslocado, e é a única que corresponde ao dano que se quer evitar.

O *"não andar mais de N do ponto"* não sumiu: voltou para quem sempre foi dono
dele, a **trava de posição**, que devolve o personagem ao ponto quando a luta
acaba.

### A válvula era aritmeticamente inalcançável

`TENTATIVAS_DE_TAB = 1`, e o contador de recusas era zerado no começo de cada
rodada de aquisição. Somando de um em um e zerando toda vez, um limiar de 3
nunca chega — daí **1 aceite em 3179 recusas**.

Agora ele é de **recusas seguidas**, atravessa rodadas, e zera **só quando
aparece um mob de verdade ao alcance**. Zerar também no aceite da própria
válvula seria o mesmo defeito com outra roupa: recusa, recusa, recusa, aceita,
zera, recusa de novo — um mob longe aceito a cada quatro tentativas, com três
TABs girando à toa entre eles. É por isso que o veredito tem **três** valores,
e não dois.

### O 30 é PROVISÓRIO, e está declarado como tal

O 12 antigo media distância até a base; esta régua mede outra coisa, e o valor
certo depende do spot. Não há medição dele ainda — o log só passou a registrar
`corrida=` em 06/09/2026. O 30 foi escolhido para ficar claramente acima do
engajamento normal (12 a 26 no spot atual) e ainda recusar a anomalia (113 na
mediana, 174 no p90).

**E a válvula é o que torna esse chute seguro:** mesmo com o número errado, ela
abre em três TABs e a conta volta a atacar.
