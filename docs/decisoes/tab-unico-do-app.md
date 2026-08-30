# TAB único do APP — porquê (29/08/2026)

A aquisição de alvo no laço simples do APP virou **UMA função só**,
`ExecutorDeMacro._adquirir_alvo`, chamada como a ÚLTIMA coisa fora de batalha,
logo antes da linha 1 da macro. Ela decide pela memória fresca (idempotente) e
concentra os DOIS pedidos de TAB que antes eram independentes.

## O defeito que motivou

Antes havia DOIS caminhos que davam TAB sem um saber do outro:

| # | Caminho | Local | Gatilho | Tipo de TAB |
|---|---------|-------|---------|-------------|
| A | Relógio do time | `rodar()` → `_garantir_alvo(forcar=True)` | `conferir_a_parada()` — 4 s sem mudar de batalha | com verificação de id+HP |
| B | Portão da volta | `_uma_volta_simples()` → `_tab_simples()` | `_preciso_de_alvo(lutando)` | cego |

`conferir_a_parada()` rearma ao disparar (sincronia.py), mas se o flag de
batalha ainda não tinha subido na mesma volta (latência da leitura), o caminho
B apertava o segundo TAB logo embaixo. **Resultado observado em campo no modo
"copiar" (2 contas): dois TABs em fila trocando o alvo duas vezes** — é exato o
que desfaz o alvo combinado do time.

## A correção

- `rodar()` NÃO TABa mais. O relógio dos 4 s só deixa uma flag
  (`_tab_solicitado = conferir_a_parada()`); quem consome e aperta é a volta.
- `_adquirir_alvo` é a ÚNICA função que aperta TAB no laço simples. Cascata:
  1. falta alvo (`_preciso_de_alvo`): saiu de batalha / sem id / alvo vivo
     travado há 3 voltas → `_conseguir_o_tab()`;
  2. já tenho alvo VIVO confirmado (`_mesmo_alvo_verificado()`) → 0 TAB;
  3. pedido do relógio (`_tab_solicitado`) → `_conseguir_o_tab()`.
- `_conseguir_o_tab` cai em `_tab_simples()` (modo cego) quando não há funções
  de alvo injetadas, senão `_garantir_alvo(forcar=True)` (conferência de id+HP).

## Duas fronteiras que a correção teve de respeitar

1. **`_garantir_alvo` devolve `False` com DOIS significados.** `_tab_simples()`
   → `False` é "é para PARAR"; `_garantir_alvo()` → `False` é "sem mob por
   perto". **MUDOU EM 30/08/2026 (o portão de aquisição):** para a macro de
   ATAQUE do laço simples, esse `False` agora PROPAGA fechado — `_conseguir_o_tab`
   devolve `self._garantir_alvo(forcar=True)`, `_adquirir_alvo` devolve `False`,
   e a volta volta ao Core Loop sem nenhuma skill sair no vazio. O defeito era
   o `target_id == 0` com a macro disparando contra o nada. O caso de buff/pesca
   sem leitura (modo cego, `_alvo_atual is None`) continua caindo no
   `_tab_simples` e não bloqueia por falta de alvo — o contrato de "macro de
   buff/pesca não para" foi preservado exatamente aí, na escolha do caminho.
2. **O alvo vivo-travado VENCE a idempotência.** `_garantir_alvo` tem o atalho
   "alvo vivo, não mexe"; se o caso fosse roteado para `forcar=False`, o
   contador `VOLTAS_SEM_BATALHA_PARA_TROCAR = 3` nunca trocaria o mob preso no
   penhasco. Por isso o TAB por contador (id existe) usa `forcar=True`.

## O guard de idempotência (em memória, nunca disco)

`_mesmo_alvo_verificado()` compara o id do alvo atual com `_alvo_verificado`,
gravado no SUCESSO da aquisição (`_garantir_alvo`, junto ao `_ultimo_alvo_dito`).
Expira sozinho: quando o alvo muda ou morre, a leitura fresca devolve `False`.
O mob marcado como INALCANÇÁVEL não é protegido (é o que se quer largar).

## O portão de aquisição (30/08/2026) no laço simples

`_uma_volta_simples` fecha com o `if not self._adquirir_alvo(lutando)`:
o veredito propago é o portão inteiro — se a aquisição falhou (id continua 0,
ou o TAB caiu num cadáver), `False` volta e a macro nem começa. Paga
`time.sleep(ESPERA_SEM_ALVO)` antes de voltar ao Core Loop para o bloqueio não
girar CPU. Decisão tomada sem gate extra de id_antes/id_depois: `_garantir_alvo`
já relê o alvo fresco e valida vivo-e-diferente; um segundo portão por cima
reimplementaria a mesma conferência pior, e os testes mostram por quê — ele
quebraria o modo cego e o alvo vivo repetido (que por desenho não TABa).

## Não é regressão

`_tab_simples`, o guard do inalcançável, `VOLTAS_SEM_BATALHA_PARA_TROCAR = 3` e
o modo cego (sem leitura de alvo) continuam intactos. A mudança está SÓ no
caminho com alvo injetado: o `False` de `_garantir_alvo` deixou de ser engolido
quando a macro é de ataque. A cura continua entre voltas (`rodar()`), não entrou
no bloco pré-TAB.
