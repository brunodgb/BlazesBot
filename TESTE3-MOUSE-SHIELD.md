# ✅ TESTE 3: Mouse Shield (Hook Externo) - IMPLEMENTADO

**Data**: 2026-08-14  
**Status**: Pronto para teste  
**Tipo**: Hook WH_MOUSE_LL externo (sem injetar DLL)

---

## O Que Foi Implementado

### Novo Módulo: `blazesbot/core/mouse_shield.py`

**Função**: Bloqueia eventos de mouse físico sobre a janela do jogo durante cliques do bot.

**Como Funciona**:
1. Hook global `WH_MOUSE_LL` instalado no **processo do bot** (não injeta no jogo)
2. Detecta quando mouse físico está sobre a janela do bot
3. **Bloqueia** eventos APENAS durante os cliques
4. Cada janela (conta) tem controle independente

**Diferença da DLL**:
- ❌ DLL (cursor_hook.c): Injeta no jogo, intercepta GetCursorPos (invasivo)
- ✅ Hook externo: Roda no bot, intercepta antes de chegar no jogo (não invasivo)

---

## Integração com `inputs.py`

### Interruptor Adicionado (Linha ~43)
```python
USAR_MOUSE_SHIELD = True  # Ativado por padrão
```

### Integração na Classe `Input`
- `__init__`: Cria `MouseShield` para a janela
- `_click_sendmessage_rapido`: Bloqueia antes do clique, desbloqueia depois

### Proteção
- `try/finally` garante desbloqueio mesmo em exceção
- Fallback se MouseShield falhar ao instalar

---

## Como Testar

### 1. Reiniciar o Bot
- Fechar completamente
- Abrir de novo (para carregar o novo módulo)

### 2. Iniciar 1 Conta BC

### 3. Testar Mouse Físico
**Passar o cursor sobre a janela do jogo DURANTE o bot:**
- ✅ **ANTES (sem shield)**: Cliques erravam quando cursor estava sobre o jogo
- ✅ **AGORA (com shield)**: Cliques devem funcionar independente do cursor físico

### 4. Verificar Comportamento
- **A)** Bot clica normalmente? (login, NPC, entrada da cave)
- **B)** Seu cursor físico continua fluido?
- **C)** Quando você passa o cursor sobre o jogo, o bot IGNORA seu cursor?

**Tempo de teste**: 10-15 min (1-2 runs completas)

---

## Resultados Possíveis

### ✅ Sucesso Total
- Bot clica corretamente independente do cursor físico
- Cursor físico fluido (sem travadas)
- **→ SOLUÇÃO FINAL!**

### ⚠️ Cursor Físico Trava
- Hook global tem overhead
- **→ Aumentar threshold de bloqueio (só bloquear em cliques importantes)**

### ❌ Cliques Ainda Falham
- Hook não consegue bloquear rápido o suficiente
- **→ Solução final: Mouse Shield 150ms (aceitar 2-5% de falha como compromisso)**
  *(A DLL de TESTE 4 foi experimentada e ABANDONADA — consulte
  `docs/decisoes/dll-cursor-hook.md`)*

---

## Desativar Se Necessário

Editar `blazesbot/core/inputs.py` linha ~43:
```python
USAR_MOUSE_SHIELD = False
```

Reiniciar o bot.

---

## Arquitetura Técnica

### Hook WH_MOUSE_LL
```
[Mouse Físico] → Windows
                    ↓
              [Hook do Bot] ← Detecta: cursor sobre janela X?
                    ↓
        SIM → Bloqueia evento (retorna 1)
        NÃO → Deixa passar (CallNextHookEx)
                    ↓
              [Janela do Jogo]
```

### Estado por Janela
```python
_blocked_windows = {hwnd1, hwnd2, ...}  # Set de janelas bloqueadas agora

shield.block()    # Adiciona hwnd ao set
shield.unblock()  # Remove hwnd do set
```

### Thread do Hook
- Hook precisa de message loop próprio
- Thread daemon criada automaticamente
- Hook global compartilhado por todas as contas

---

## Segurança

### Não Injeta DLL
- ✅ Zero injeção no processo do jogo
- ✅ Não modifica memória do jogo
- ✅ Não altera comportamento do jogo

### Risco de Ban
- **Baixíssimo**: Hook externo é invisível para o servidor
- **Não detectável**: Jogo não sabe que o hook existe
- **Mesma categoria** de ler memória (que você já faz)

---

## Limitações Conhecidas

1. **Overhead**: Hook global processa TODOS os eventos de mouse do sistema
2. **Latência**: Pode ter ~1-2ms de latência (aceitável)
3. **Windows pode cancelar**: Se o hook atrasar >300ms, Windows remove automaticamente

---

## Próximos Passos

**Se funcionar bem (1 semana sem problemas)**:
- Tornar padrão (`USAR_MOUSE_SHIELD = True` permanente)
- Documentar em `COMECE-AQUI.md`
- Atualizar `CLAUDE.md`

**Se falhar**:
- *(A DLL de TESTE 4 foi experimentada e ABANDONADA — consulte
  `docs/decisoes/dll-cursor-hook.md`)*
- O Mouse Shield 150ms é a solução final — aceitar ~2-5% de falha com cursor
  em movimento como compromisso aceitável
