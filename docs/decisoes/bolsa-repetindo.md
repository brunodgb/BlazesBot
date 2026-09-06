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
