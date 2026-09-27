---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
---

# Systematic Debugging

Portado de `github.com/obra/superpowers` (skill `systematic-debugging`, plugin
desligado neste projeto — auditoria em `docs/SKILLS.md`, seção "plugins e
agentes do projeto"). Adaptado: as referências a outras skills do superpowers
que não foram trazidas apontam agora para os equivalentes deste projeto.

## Overview

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- The user wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read the logs first** — regra permanente deste projeto (`CLAUDE.md`):
   `logs/dev/blazes-dev.jsonl` é enriquecido por `id_run`/`conta`/`fase`.
   Não pule pro código antes de ler o que já foi registrado.

   **Como ler, nesta ordem:**
   - **Frequência antes de cronologia.** Extraia só o texto das mensagens e
     agregue (`Counter`, ou `sort | uniq -c | sort -rn`). A mensagem que
     domina nomeia o defeito; **duas mensagens que se contradizem na mesma
     sessão** provam uma leitura não-determinística.
   - **Reconstrua UM incidente de ponta a ponta** (filtre por `id_run`,
     suprima a linha repetida) e responda duas perguntas: o que ENCERROU o
     travamento? (se foi algo externo, o código não tem saída nenhuma) e o que
     o laço LEU enquanto estava preso? (se nada, a correção é diagnóstico +
     remediação, não um teto menor).
   - **O intervalo entre duas linhas vizinhas é evidência.** Menor que a
     operação mais barata entre elas, ele prova que o trabalho não rodou: a
     falha está no prólogo da função (ex.: import preguiçoso que aponta para
     um nome que não existe mais).
   - **Campo posicional tem o significado que o REGISTRADOR deu, não o
     óbvio.** Antes de agregar por coordenada/posição, leia o código que
     grava esse campo: é origem, destino ou alvo? Um evento de rollback
     gravado no ponto de CHEGADA aponta o destino (às vezes um ponto fixo do
     servidor) como culpado, quando o problema começou em outro lugar.

2. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - They often contain the exact solution
   - Read stack traces completely
   - Note line numbers, file paths, error codes

3. **Reproduce Consistently**
   - Can you trigger it reliably?
   - What are the exact steps?
   - Does it happen every time?
   - If not reproducible → gather more data, don't guess

4. **Check Recent Changes**
   - What changed that could cause this?
   - Git diff, recent commits
   - New dependencies, config changes
   - Environmental differences

5. **Gather Evidence in Multi-Component Systems**

   **WHEN system has multiple components (ex.: captura de tela → template
   match → clique; ou leitura de memória → cálculo → decisão de combate):**

   **BEFORE proposing fixes, add diagnostic instrumentation:**
   ```
   For EACH component boundary:
     - Log what data enters component
     - Log what data exits component
     - Verify environment/config propagation
     - Check state at each layer

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify failing component
   THEN investigate that specific component
   ```

   **O instrumento faz parte da cadeia.** Anomalia vista por um script de
   diagnóstico só vira defeito do sistema depois de reproduzida pelo CAMINHO
   do sistema — mesmas entradas, mesma ordem, mesmos filtros. Até lá, escreva
   "minha ferramenta viu X", nunca "o código de produção faz X".

   **Dado fora do seu alcance: peça.** "Não dá para medir" costuma ser "eu
   não tenho o dado" — o usuário tem o jogo aberto, capturas e logs. Peça a
   amostra ANTES de recomendar uma heurística. E evidência bruta só se apaga
   depois de reproduzida pelo código de PRODUÇÃO: conversão de cor, escala ou
   encoding muda o número sem mudar o código.

6. **Trace Data Flow**

   **WHEN error is deep in call stack:**

   See `root-cause-tracing.md` in this directory for the complete backward
   tracing technique (exemplos em TypeScript, mas a técnica é agnóstica de
   linguagem).

   **Quick version:**
   - Where does bad value originate?
   - What called this with bad value?
   - Keep tracing up until you find the source
   - Fix at source, not at symptom

7. **Quando quem falha é um TESTE, depois de mudança manual**

   Um teste que falha é um desacordo entre dois artefatos, não defeito de um
   deles. Antes de editar qualquer lado, descubra com qual o resto do sistema
   concorda. Por falha, em ordem:
   - (a) o dublê ainda bate com o contrato do produtor REAL? Não → conserte
     o dublê, e a asserção costuma passar sem mudar;
   - (b) o código contradiz a PRÓPRIA docstring, comentário ou texto de log?
     → é defeito do código: não edite o teste;
   - (c) `git log -S <símbolo>` mostra que o que o teste guarda foi APAGADO,
     e não redesenhado? → defeito do código;
   - (d) quais caminhos chegam à linha mudada?

   Depois de adaptar, varra a região mexida atrás de prosa que contradiz o
   código — número no comentário diferente da constante ao lado, referência a
   símbolo apagado, log anunciando ação que não acontece mais — e conserte no
   mesmo passo: é o mapa pelo qual o próximo leitor vai se guiar.

### Phase 2: Pattern Analysis

**Find the pattern before fixing:**

1. **Consulte o graphify primeiro** — `graphify query "<pergunta>"` /
   `graphify path "<A>" "<B>"` antes de grep bruto (regra de ouro do
   `CLAUDE.md`). Ele já indica onde a função equivalente/similar mora.

2. **Find Working Examples**
   - Locate similar working code in same codebase
   - What works that's similar to what's broken?

3. **Compare Against References**
   - If implementing pattern, read reference implementation COMPLETELY
   - Don't skim - read every line
   - Understand the pattern fully before applying

4. **Identify Differences**
   - What's different between working and broken?
   - List every difference, however small
   - Don't assume "that can't matter"

5. **Understand Dependencies**
   - What other components does this need?
   - What settings, config, environment?
   - What assumptions does it make?

6. **Ao fundir/promover duplicata, cada divergência é pergunta, não ruído**
   - A cópia "mais completa" não é necessariamente a certa. Para cada
     diferença entre as cópias, rastreie o CONSUMIDOR do efeito — quem lê o
     estado depois, inclusive no caminho de exceção (`finally` roda ANTES do
     tratador de quem chamou) — antes de escolher qual lado vira o padrão.

7. **Audite os validadores, não só os valores**
   - Checagem que não consegue falhar (`return True`, faixa mais larga que o
     tipo) não é checagem: fabrica confiança. Procure a propriedade que
     OBRIGATORIAMENTE difere entre instâncias independentes (um ponteiro de
     heap é diferente em cada processo) e teste essa.
   - Numa cadeia "tenta A; se inválido, tenta B", meça QUAL ramo serviu cada
     chamada. Um guarda permissivo que aceita o lixo de A transforma B em
     código morto — e o chamador recebe um valor plausível e errado.
   - Parâmetro que precisa de ajuste (teto, margem, fallback) costuma indicar
     a UNIDADE errada. Antes de afinar números, veja se o sistema já expõe a
     fronteira natural (região de alocação, página, partição) e adote-a.

### Phase 3: Hypothesis and Testing

**Scientific method:**

1. **Form Single Hypothesis**
   - State clearly: "I think X is the root cause because Y"
   - Write it down
   - Be specific, not vague

2. **Test Minimally**
   - Make the SMALLEST possible change to test hypothesis
   - One variable at a time
   - Don't fix multiple things at once
   - **Teste que DISCRIMINA, não que concorda:** para decidir entre duas
     fontes do mesmo valor, use dois sujeitos cujo valor verdadeiro difere; a
     fonte que responde igual para os dois mede outra coisa.
   - **Estado limpo ANTES de cada passo:** numa sequência de toggles, afirme
     a linha de base antes de medir. "Mandei o reset" não é "observei o
     reset" — e experimento que falhou no objetivo ainda produziu um estado:
     leia-o antes de descartar a rodada.
   - **Negativo vale o espaço de busca:** "não achei X" é fato sobre a sua
     busca. Declare o espaço (todo offset, alinhado ou não; toda largura e
     sinal; as formas derivadas do valor) junto com a conclusão.

3. **Verify Before Continuing**
   - Did it work? Yes → Phase 4
   - Didn't work? Form NEW hypothesis
   - DON'T add more fixes on top
   - **Conte a premissa, não as tentativas:** N hipóteses que caíram pela
     MESMA premissa são uma falha só. Antes de recomendar parar, nomeie a
     premissa comum e procure a abordagem que não a faz; recomende "buscar
     dentro de X está esgotado", nunca "a pergunta está fechada".

4. **When You Don't Know**
   - Say "I don't understand X"
   - Don't pretend to know
   - Ask for help
   - Research more

### Phase 4: Implementation

**Fix the root cause, not the symptom:**

1. **Create Failing Test Case**
   - Simplest possible reproduction
   - Automated test if possible (`tests/`, pytest)
   - One-off test script if no framework
   - MUST have before fixing
   - Invoque o agente `tdd-guide` (ECC) para escrever o teste que falha
     corretamente, se for um caso novo de teste (não uma reprodução manual).
   - Propriedade ESTRUTURAL ("não chama X") se afirma na árvore (`ast`),
     nunca por substring: o texto inclui as docstrings que citam justamente o
     proibido. Para desindentar fonte de método, `textwrap.dedent`.
   - Dublê é uma afirmação sobre o contrato do produtor: confira o real
     ANTES de mexer na asserção, e faça o dublê falhar para o lado DIFÍCIL —
     nunca mais permissivo que o real.
   - Teste que falha no cenário que VOCÊ inventou pode estar fixando um
     limite real: reescreva para o caso medido E acrescente um teste que
     afirma o limite, com o porquê. Fronteira sem teste é lida como garantia
     sem fronteira.

2. **Implement Single Fix**
   - Address the root cause identified
   - ONE change at a time
   - No "while I'm here" improvements
   - No bundled refactoring

3. **Verify Fix**
   - Test passes now?
   - Suíte inteira continua passando? (regra "GATILHO DE SEGURANÇA" deste
     projeto — reuso/correção não pode custar estabilidade, roda a suíte
     inteira, nunca só a área mexida)
   - Issue actually resolved? Confirme com evidência real (rodar o comando,
     ver o output) antes de declarar concluído — nunca por afirmação.
   - **Suíte verde não prova fiação.** Módulo que ninguém importa e função
     que ninguém chama passam em qualquer teste de comportamento. Depois de
     mover ou compor, confira que o ponto de entrada IMPORTA e ALCANÇA as
     partes (teste que importa a entrada; AST do grafo de chamadas).
   - **O timeout da ferramenta encerra a espera, não o processo.** Estourou o
     tempo? Liste e mate o que você lançou antes de seguir.
   - **Novo modo de falha é contrato novo para TODO chamador.** Deu a uma
     função uma exceção, `None` ou `ok: false` que ela não tinha antes? Grep
     TODAS as chamadas dela, em toda camada (backend, ponte, frontend) — não
     só a vizinhança do diff — antes de declarar completo. O chamador
     distante que ninguém revisou é o que quebra em produção.

4. **If Fix Doesn't Work**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1, re-analyze with new information
   - **If ≥ 3: STOP and question the architecture (step 5 below)**
   - Isso já é, por si só, o gatilho pra segunda opinião do `claude-council`
     (ver `CLAUDE.md`, seção "Segunda opinião") — debugging que falhou 2+
     vezes sem bater é um dos dois momentos concretos declarados lá.
   - DON'T attempt Fix #4 without architectural discussion

5. **If 3+ Fixes Failed: Question Architecture**

   **Pattern indicating architectural problem:**
   - Each fix reveals new shared state/coupling/problem in different place
   - Fixes require "massive refactoring" to implement
   - Each fix creates new symptoms elsewhere

   **STOP and question fundamentals:**
   - Is this pattern fundamentally sound?
   - Are we "sticking with it through sheer inertia"?
   - Should we refactor architecture vs. continue fixing symptoms?

   **Discuss with the user before attempting more fixes**

   This is NOT a failed hypothesis - this is a wrong architecture.

## Red Flags - STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals new problem in different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (see Phase 4.5) e considere
`claude-council` como insumo de análise (nunca veredito).

## User's Signals You're Doing It Wrong

**Watch for these redirections:**
- "Não está acontecendo isso?" - You assumed without verifying
- "Vai mostrar...?" - You should have added evidence gathering
- "Para de chutar" - You're proposing fixes without understanding
- "Pensa com calma nisso" - Question fundamentals, not just symptoms
- "Travamos?" (frustrado) - Your approach isn't working

**When you see these:** STOP. Return to Phase 1.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question pattern, don't fix again. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Ler logs (frequência → incidente → intervalo entre linhas), ler erros, reproduzir, checar mudanças, conferir o instrumento; teste falhando: triagem (a)–(d) | Understand WHAT and WHY |
| **2. Pattern** | `graphify query`, achar exemplo funcionando, comparar, auditar os validadores | Identify differences |
| **3. Hypothesis** | Form theory, test minimally, teste que discrimina, base limpa, conte a premissa | Confirmed or new hypothesis |
| **4. Implementation** | `tdd-guide`, fix, suíte inteira, fiação (importa e alcança), processos lançados encerrados, evidência real | Bug resolved, tests pass |

## When Process Reveals "No Root Cause"

If systematic investigation reveals issue is truly environmental, timing-dependent, or external:

1. You've completed the process
2. Document what you investigated (`docs/decisoes/<area>.md` se for algo que
   já reprovou com medição — regra deste projeto, não se perde)
3. Implement appropriate handling (retry, timeout, error message — lembre da
   regra "onde havia espera cega, agora se pergunta": nada de teto fixo sem
   medir)
4. Add monitoring/logging for future investigation

**But:** 95% of "no root cause" cases are incomplete investigation.

## Supporting Techniques

- **`root-cause-tracing.md`** - Trace bugs backward through call stack to find original trigger (exemplos em TS, técnica agnóstica de linguagem)
- **`defense-in-depth.md`** - Add validation at multiple layers after finding root cause

*(A terceira técnica original do superpowers, "condition-based waiting", não
foi trazida porque já é regra permanente deste projeto: "Onde havia espera
cega, agora se PERGUNTA" — `CLAUDE.md`, seção "Regras que atravessam tudo".)*
