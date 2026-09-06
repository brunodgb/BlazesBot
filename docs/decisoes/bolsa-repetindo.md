# A bolsa abrindo e fechando sem parar — instrumentação, 05/09/2026

> *"Tem vezes que o APP está bugando, começa a abrir e fechar várias vezes o
> inventário, e no meio tempo ficar dando TAB sem começar nenhuma macro."*
> — usuário

**Este documento descreve a INSTRUMENTAÇÃO, não a correção.** A régua continua
exatamente a que era; o que entrou foi o log que nomeia a causa na hora.

## O que o log de 05/09 já provava

| medida | `gamerblazes` | `blazestpas` |
|---|---|---|
| limpezas de bolsa | 622 | 277 |
| limpezas repetindo o MESMO número de volta | **595** | 244 |
| pior rajada consecutiva | **275** (volta 150) | 59 |

Três em cada quatro apagando **zero itens** — abrir e fechar por nada.

## O mecanismo

A régua é `voltas % a_cada == 0`, conferida **no prelúdio de cada volta**. Ela
pressupõe que `voltas` ande. Quando a volta é cortada antes do fim, o contador
de voltas **completas** não sobe — e o resto continua zero na volta seguinte, e
na seguinte. A cadência deixa de ser "a cada N voltas" e vira **"enquanto o
contador não andar"**.

E os cortes não são raros: no mesmo log, `blazestpas` fechou a sessão com **285
voltas completas contra 289 abortadas**.

Pior: os caminhos de aborto **não são consistentes** ao incrementar `voltas` —
o corte por batalha encerrada incrementa, o corte por alvo zerado não, o corte
por morte não, e a falha de aquisição nem passa por `_abortar_a_volta`.

## O que a instrumentação mostra

`core/cadencia_da_bolsa.py` decide e, quando a limpeza **repete na mesma
volta**, sobe de INFO para WARNING:

```
BOLSA/DIAGNÓSTICO: 4ª limpeza seguida na MESMA volta 150 (5.3s desde a
anterior). Voltas completas NÃO andaram; abortadas subiram 3 no intervalo.
Último corte: sem alvo. A cadência 'a cada 10 voltas' está presa no resto zero.
```

O campo que faltava é o **último corte**: cada saída da volta agora se rotula
(`mob morreu`, `alvo zerado`, `morri`, `alvo inalcançável`, `time: volta vetada`,
`time: linha fora`, `pausa/parada`, `sem alvo`, `portão: alvo ausente ou morto`,
`volta completa`). É ele que diz **qual** caminho está congelando o contador —
e, portanto, se a correção certa é contar aquele corte como volta, mudar a
âncora da cadência para o relógio, ou consertar a montante o que está cortando
tanto.

A linha normal de limpeza também ganhou contexto, sem virar ruído:

```
Volta 160: hora de limpar a bolsa (a cada 10 voltas)
   [abortadas até aqui: 41 | último corte: mob morreu]
```

## Por que não corrigi junto

Há pelo menos três correções plausíveis, e elas levam a comportamentos
diferentes:

1. **âncora no relógio** (limpar a cada N minutos) — imune a corte, mas muda a
   semântica que o usuário configurou na tela ("a cada N voltas");
2. **contar toda tentativa de volta**, completa ou não — mantém a semântica, mas
   passa a limpar mais cedo em sessão cheia de cortes;
3. **exigir que o contador tenha MUDADO desde a última limpeza** — o mínimo, e
   não resolve o excesso de cortes, só para de repetir.

Escolher sem o dado do "último corte" seria palpite. Com uma sessão de log
instrumentado, a escolha vira medição.

## O que pedir ao usuário

Rodar o APP como sempre e mandar `logs/dev/blazes-dev-*.jsonl`. As linhas
`BOLSA/DIAGNÓSTICO` respondem sozinhas qual dos três consertos é o certo.


## O piso do conserto — 06/09/2026

Escolhida a opção (c) das três: **a mesma volta não abre a bolsa duas vezes**
(`NAO_LIMPAR_DUAS_VEZES_NA_MESMA_VOLTA`).

Ela não conserta a causa — o contador continua congelando quando a volta é
cortada, e o log instrumentado provou de onde vem: **401 dos 407 avisos dizem
`Último corte: sem alvo`**. Conserta o dano visível (a bolsa em rajada) sem
mexer na semântica que o usuário configurou na tela ("a cada N voltas"), que é
o que as opções (a) e (b) fariam.

O aviso continua saindo a cada repetição — agora dizendo que a bolsa NÃO foi
aberta —, então a medição da causa não se perde. E o interruptor existe para
quem quiser ver a rajada acontecer de novo numa investigação.


## A raiz, atacada — 06/09/2026

> *"Se trava, então é importante ajustar; tente ajustar a raiz do problema para
> não travar nada de forma alguma."* — usuário

Duas causas, as duas removidas:

**1. Havia uma saída do laço que não incrementava NADA.** Quando `_adquirir_alvo`
falhava, `_uma_volta_simples` devolvia sem tocar em `voltas` nem em
`voltas_abortadas` — e era justamente a saída que dominava o log (401 dos 407
avisos). Enquanto o TAB não trazia alvo, todo contador do executor ficava
congelado, e com ele qualquer cadência ancorada neles. Agora **toda** saída de
fim de volta conta (as de PARADA não são fim de volta e continuam de fora).

**2. A cadência olhava só as voltas COMPLETAS.** Em farm normal metade das voltas
aborta — numa sessão medida, 285 completas contra 289 abortadas. Ancorada só nas
completas, "a cada N voltas" virava "enquanto o contador não andar". Agora ela
conta **tentativas** (`voltas + voltas_abortadas`), que sempre andam.

O piso (`NAO_LIMPAR_DUAS_VEZES_NA_MESMA_VOLTA`) fica como cinto: com a raiz
consertada ele não deve mais disparar, e se disparar é sinal de que apareceu uma
terceira saída sem contador.

E a causa a montante — a aquisição não trazer alvo — foi consertada no mesmo
dia, em `docs/decisoes/coleira-do-ponto.md`: a régua passou a medir a corrida
até o mob, e a válvula deixou de ser aritmeticamente inalcançável.
