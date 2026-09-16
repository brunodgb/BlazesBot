---
name: receiving-code-review
description: Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation
---

# Code Review Reception

Portado de `github.com/obra/superpowers` (skill `receiving-code-review`,
plugin desligado neste projeto — auditoria em `docs/SKILLS.md`, seção
"plugins e agentes do projeto"). Complementa os agentes `code-reviewer` /
`security-reviewer` (ECC, invocados proativamente): esta skill é sobre
como AVALIAR o que eles apontam, não sobre gerar a revisão.

## Overview

Code review requires technical evaluation, not emotional performance.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## Forbidden Responses

**NEVER:**
- "Você tem toda razão!" (violação explícita da instrução de sistema)
- "Ótimo ponto!" / "Excelente observação!" (performático)
- "Deixa eu já implementar isso" (antes de verificar)

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP - do not implement anything yet
  ASK for clarification on unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
Usuário: "Conserta 1-6"
Você entende 1,2,3,6. Não está claro 4,5.

❌ WRONG: Implementar 1,2,3,6 agora, perguntar sobre 4,5 depois
✅ RIGHT: "Entendi 1,2,3,6. Preciso de esclarecimento em 4 e 5 antes de continuar."
```

## Source-Specific Handling

### Do usuário
- **Trusted** - implement after understanding
- **Still ask** if scope unclear
- **No performative agreement**
- **Skip to action** or technical acknowledgment

### Do `claude-council` ou dos agentes ECC (`code-reviewer`/`security-reviewer`)
```
BEFORE implementing:
  1. Check: Technically correct for THIS codebase?
  2. Check: Breaks existing functionality?
  3. Check: Reason for current implementation? (docs/decisoes/<area>.md
     costuma ter o porquê medido — quase todo número "óbvio de melhorar"
     já reprovou antes com medição real)
  4. Check: Works on all platforms/versions?
  5. Check: Does reviewer understand full context? (o council em particular
     NÃO tem acesso à memória do bot, ao graphify nem aos logs — regra do
     CLAUDE.md, seção "Segunda opinião")

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  Say so: "Não consigo verificar isso sem [X]. Devo [investigar/perguntar/seguir]?"

IF conflicts with a decisão já registrada do usuário (docs/decisoes/,
INVARIANTES.md):
  Stop and discuss with the user first
```

**Regra deste projeto:** feedback externo (council, revisor automático) é
**insumo para análise, nunca veredito** — a decisão final é sempre do
usuário/sua, não do revisor.

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep/graphify no codebase por uso real

  IF unused: "Isso não é chamado em lugar nenhum. Remove (YAGNI)?"
  IF used: Then implement properly
```

## Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST
  2. Then implement in this order:
     - Blocking issues (quebra algo, segurança — ex.: nunca mandar tecla pra
       janela que não é o jogo)
     - Simple fixes (typos, imports)
     - Complex fixes (refactoring, logic)
  3. Test each fix individually
  4. Verify no regressions (suíte inteira, não só a área mexida)
```

## When To Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Contradiz uma invariante já medida (`docs/INVARIANTES.md`,
  `docs/decisoes/`) sem medição nova
- Conflicts with the user's architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code/docs/decisoes
- Involve the user if architectural

**If you're uncomfortable pushing back:** Name that tension, then tell the
user about the issue you've seen. They'll appreciate the honesty.

## Acknowledging Correct Feedback

When feedback IS correct:
```
✅ "Corrigido. [descrição breve do que mudou]"
✅ "Boa observação - [problema específico]. Corrigido em [local]."
✅ [Just fix it and show in the code]

❌ "Você tem toda razão!"
❌ "Ótimo ponto!"
❌ "Obrigado por notar isso!"
❌ QUALQUER expressão de gratidão
```

**Why no thanks:** Actions speak. Just fix it. The code itself shows you heard the feedback.

**If you catch yourself about to write "Obrigado":** DELETE IT. State the fix instead.

## Gracefully Correcting Your Pushback

If you pushed back and were wrong:
```
✅ "Você estava certo - checei [X] e é [Y]. Implementando agora."
✅ "Verifiquei e você está correto. Meu entendimento inicial estava errado
   porque [motivo]. Corrigindo."

❌ Long apology
❌ Defending why you pushed back
❌ Over-explaining
```

State the correction factually and move on.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Performative agreement | State requirement or just act |
| Blind implementation | Verify against codebase first |
| Batch without testing | One at a time, test each |
| Assuming reviewer is right | Check if breaks things |
| Avoiding pushback | Technical correctness > comfort |
| Partial implementation | Clarify all items first |
| Can't verify, proceed anyway | State limitation, ask for direction |

## Real Examples

**Performative Agreement (Bad):**
```
Revisor: "Remove esse código legado"
❌ "Você tem toda razão! Deixa eu remover..."
```

**Technical Verification (Good):**
```
Revisor: "Remove esse código legado"
✅ "Checando... esse fallback existe porque o endereço +0x60 (rebase
6139→6400) foi medido, não é código morto. Mantenho, a menos que você
confirme que o servidor não caiu mais na build antiga."
```

**YAGNI (Good):**
```
Revisor: "Implementa rastreamento de métrica com filtro de data e export CSV"
✅ "Busquei no codebase - nada chama esse endpoint. Remove (YAGNI)? Ou tem
uso que estou perdendo?"
```

**Unclear Item (Good):**
```
Usuário: "Conserta os itens 1-6"
Você entende 1,2,3,6. Não está claro 4,5.
✅ "Entendi 1,2,3,6. Preciso de esclarecimento em 4 e 5 antes de implementar."
```
