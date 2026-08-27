---
name: log-hp-tela-masks-None
description: ALVO log removed entirely; hp_tela=0.0% and ptr=ptr= issues resolved by elimination
metadata:
  type: project
---

### Problema original
Em `combat.py`, o log da linha `ALVO` mostrava `hp_tela=0.0%` quando `hp_pct` era `None` (barra de HP não extraída do quadro). Isso fazia parecer que o HP caiu a 0%, quando na verdade a barra não foi lida (ex.: cadáver, ou região fora da faixa). Também mostrava `ptr=ptr=0x...` (duplicado).

### Resolução
O log `ALVO` foi **removido integralmente**. Isso resolveu ambos os problemas ao eliminá-los — não há mais linha para mascarar `None` ou duplicar `ptr=`. A remoção abrangiu:
- Bloco `ctx.log.debug("ALVO %s ...")` e sua infraestrutura (`selecao`/`_oponente` try/except, `info_alvo`/`hp_tela_str`)
- Método `VigiaDoAlvo.instrumentar()` (existia só para o log)
- Constante `SEGUNDOS_ENTRE_ECOS_DO_ALVO` e variável `ultimo_eco`
- Prints debug no `_alvo_morreu()` e no loop de combate

### O que foi mantido
- `texto_do_ponteiro()` — **usado** por `tests/test_cegueira_no_instante_da_mortal.py` (testado isoladamente, não depende do log ALVO)
- `_anotar_ponteiro()` — chamado de `observar()`, ainda usado no fluxo normal
- `candidato_de_enderreco_booleano()` em `memory.py` — chamado por `vendor.py` e `routine.py`

**Why:** O log ALVO era poluição — o ponteiro segue relatado via `texto_do_ponteiro()` quando necessário (testado isoladamente), e a morte do alvo é confirmada pelo consenso de `VigiaDoAlvo`, não por logs.

**How to apply:** Qualquer future ALVO-style logging deve passar por `texto_do_ponteiro()`, nunca mais inline no loop de combate. O `ptr=` não deve aparecer duas vezes. Não reintroduzir `instrumentar()`.
