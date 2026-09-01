# Análise Arquitetural: Input Bleed (Teclado + Mouse)

**Data:** 30/08/2026  
**Origem:** Solicitação do usuário para análise rigorosa de baixo nível e plano de ação em três eixos.

---

## Resumo do Problema

O bot envia tecla `'1'` mas o jogo recebe `'Shift+1'`. O jogo lê **RawInput/hardware state**, não apenas a fila de mensagens. O cursor físico também sangra: `WM_MOUSEMOVE` físicos entre `WM_LBUTTONDOWN/UP` transformam cliques em arrastos.

Estado atual:
- **Teclado**: `MODO_DE_TECLA = "postmessage"` com `lParam=0` — **sem mitigação de modificadores**
- **Mouse**: `MODO_DE_CLIQUE = "postmessage_puro"`, `USAR_MOUSE_SHIELD = False` — **sem shield ativo**
- **Validação de janela**: `_janela_confiavel()` com pinagem de PID + verificação de `client.exe` — **funciona para HWND recycling**

---

## EIXO 1 — Sandbox Engineer: Isolamento de Modificadores (Teclado)

### Causa Raiz
O jogo usa **RawInput** (`RegisterRawInputDevices` para teclado) **OU** `GetKeyboardState`/`GetAsyncKeyState` — ambos leem o **estado global de hardware** mantido pelo kernel do Windows (por sessão de usuário). Injeção de mensagem (`PostMessageW`/`SendMessageW`) afeta apenas a fila da janela alvo, **não o estado de hardware**.

Quando o usuário segura `Shift` fisicamente:
1. Kernel marca `Shift` como "pressed" no estado global da sessão
2. Bot posta `WM_KEYDOWN` para `'1'` (`VK=0x31`, `lParam=0`)
3. Jogo processa `WM_KEYDOWN` E consulta RawInput/`GetKeyboardState` → vê `Shift` pressionado
4. Resultado: jogo recebe `Shift+1`

### Soluções Candidatas (ordem de viabilidade)

| Abordagem | Viabilidade | Complexidade | Cobertura |
|-----------|-------------|--------------|-----------|
| **A. AttachThreadInput** (bot thread ↔ game thread) | **Alta** se mesma desktop + mesma integridade | Média | Isola estado de teclado virtual (`GetKeyboardState`); **não isola RawInput** |
| **B. WM_KEYUP/WM_KEYDOWN sintéticos para modificadores** antes de cada tecla | **Alta** | Baixa | Força estado "limpo" na fila da janela; **não afeta RawInput/hardware state** |
| **C. Bloquear input físico global** (hook `WH_KEYBOARD_LL` engolindo modificadores) | **Baixa** — quebra sessão do usuário | Alta | Isola RawInput mas custo inaceitável |
| **D. Driver de kernel / filter driver** | **Muito baixa** — fora do escopo | Extrema | Única que isola RawInput de verdade |

### Análise Técnica: AttachThreadInput

```c
// Precisa do thread ID da thread que bomba mensagens do jogo
DWORD gameThreadId = GetWindowThreadProcessId(gameHwnd, &pid);
AttachThreadInput(GetCurrentThreadId(), gameThreadId, TRUE);
// Agora GetKeyboardState() no bot reflete o estado DA THREAD DO JOGO
```

**Pré-requisitos (hard constraints):**
- Mesmo **desktop** (WinSta0\Default) — jogo não pode estar em desktop isolado
- Mesmo **nível de integridade** — ambos elevated (bot já roda como admin ✓)
- Thread do jogo deve ser **attachable** (não pode ter `CS_OWNDC` problemático ou thread pool)

**O que isola:** `GetKeyboardState`, `GetAsyncKeyState`, `GetKeyState` — estado virtual da thread.

**O que NÃO isola:** **RawInput** — `WM_INPUT` entrega dados HID brutos do dispositivo, independentes de thread. Se o jogo registrou `RegisterRawInputDevices` para teclado (comum em jogos anti-cheat ou engines modernas), `AttachThreadInput` **não resolve**.

### Análise Técnica: Sintéticos WM_KEYUP/WM_KEYDOWN

```python
# Antes de cada key_down('1'):
input.key_up('SHIFT')
input.key_up('CTRL')
input.key_up('ALT')
input.key_down('1')
input.key_up('1')
```

**Prós:** Zero dependência de thread, funciona com `PostMessageW` atual.
**Contras:** Apenas limpa a **fila de mensagens da janela**. Se o jogo lê RawInput, o modificador físico continua "pressed" no hardware.

**Mitigação parcial:** Enviar `WM_KEYUP` para modificadores **com `lParam` contendo bit 31 (transition flag)** — alguns jogos checam isso. Mas ainda não toca RawInput.

### Veredito Eixo 1

| Cenário | Solução Recomendada |
|---------|---------------------|
| Jogo usa **apenas** `GetKeyboardState`/`GetAsyncKeyState` | **AttachThreadInput** — isola completamente |
| Jogo usa **RawInput** (provável em cliente 6400) | **Nenhuma solução user-mode completa**. Sintéticos `WM_KEYUP` para modificadores **reduzem janela de sangramento** mas não eliminam. Driver de kernel seria necessário para isolamento total. |
| Híbrido (RawInput para movimento, fila para teclas) | **AttachThreadInput + Sintéticos** — defesa em profundidade |

**Ação imediata:** Implementar **sintéticos `WM_KEYUP` para SHIFT/CTRL/ALT antes de cada `key_down`** (baixo custo, ganho marginal mensurável). Paralelamente, instrumentar para detectar se jogo usa RawInput: logar `WM_INPUT` recebido via hook de janela ou `RegisterRawInputDevices` dumpeado.

---

## EIXO 2 — Pointer Engineer: Desacoplamento do Mouse (100% Invisível)

### Causa Raiz
Mouse físico gera `WM_MOUSEMOVE` **entre** o `WM_LBUTTONDOWN` e `WM_LBUTTONUP` postados pelo bot. O jogo rastreia posição via `WM_MOUSEMOVE`; um move físico no meio sobrescreve a posição rastreada → `UP` cai em coordenada diferente do `DOWN` → jogo interpreta como **arrasto** → personagem anda.

Evidência medida (`mouse_shield.py`, 18/08/2026):
- **Sem shield, mouse movendo**: 1/20 acertos, 14/20 personagem andou
- **Com shield, mouse movendo**: 20/20 acertos, 0 andadas
- **Cursor PARADO a 780px**: 20/20 em ambas — **jogo HONRA `lParam` do botão**

### Estado Atual dos Caminhos

| Modo | Síncrono? | Shield? | Taxa (mouse movendo) | Bloqueio thread bot |
|------|-----------|---------|---------------------|---------------------|
| `sendmessage` | Sim | Sim (80ms teto) | 16/20 (4 andadas) | **112 ms/clique** (medido!) |
| `sendmessage_rapido` | Sim | Sim (80ms teto) | 20/20 | ~5 ms real, 80 ms teto |
| `postmessage_puro` | **Não** | **Não** (desligado) | 20/20 (lab) / "às vezes falha" (prod) | **~0 ms** |

**O problema do `postmessage_puro` sem shield:** `PostMessageW` enfileira e retorna. As 4 mensagens ficam na fila até o jogo bombear. Não há sinal de "processado". O shield bloquearia por **80 ms fixos** (teto viraria gasto real) — mouse do usuário preso 80 ms/janela, inaceitável.

### Soluções Candidatas

| Abordagem | Viabilidade | Latência Bot | Mouse Usuário | Complexidade |
|-----------|-------------|--------------|---------------|--------------|
| **A. `sendmessage_rapido` (1ms sleep) + Shield reativado** | **Alta** | ~5 ms/clique | ~5 ms real (liberado no `finally`) | Baixa — trocar interruptor |
| **B. `postmessage_puro` + Shield com timeout adaptativo** | Média | ~0 ms | 80 ms fixos (sem sinal de fim) | Média — precisa heurística de "já processou" |
| **C. `SendMessageW` com `SMTO_BLOCK` + timeout curto** | Média | Timeout ms | Sem shield necessário? | Média — `SendMessageTimeoutW` |
| **D. Verificar se jogo honra `lParam` no `UP` sem `MOVE` intermediário** | **Alta** (já medido: honra) | — | — | Baixa — teste direto |

### Análise: Opção A (`sendmessage_rapido` + Shield)

**Por que funciona:** 
- `SendMessageW` **bloqueia até WndProc processar** → retorno = prova de processamento
- `finally` chama `shield.liberar()` → mouse preso **~5 ms reais**, não 80 ms
- Medido: **20/20 com mouse movendo**, 0 andadas
- Custo: 112 ms/clique medido em instrumentação (thread do jogo ocupada) — **mas** isso é o custo de `SendMessageW` esperando a thread do jogo processar a enxurrada de eventos. Com 1ms sleep entre down/up, o custo **real do clique** é ~5 ms; os 112 ms incluem espera da thread do jogo.

**Tradeoff:** 112 ms/clique × 15 cliques/seg (venda) = 1.68s/seg → **o bot roda a 1/3 da velocidade**. Mas: clique **funciona sempre**.

### Análise: Opção D — O jogo honra `lParam` sem `MOVE` intermediário?

Já medido em `mouse_shield.py` (cursor PARADO a 780px): **20/20 acertos sem shield**. O jogo **usa a coordenada do `lParam` do botão**. O problema é **apenas** o `WM_MOUSEMOVE` físico no meio.

Se pudéssemos garantir que **nenhum `WM_MOUSEMOVE` físico entra entre DOWN e UP**, o `postmessage_puro` funcionaria sem shield.

**Como garantir sem shield global?**
1. **PostMessage + verificação de efeito** (imagem) + repetição — já é a regra do projeto
2. **`SendMessageTimeoutW` com `SMTO_ABORTIFHUNG` + timeout 5ms** — se jogo não processa em 5ms, aborta e repete. Não bloqueia thread do bot indefinidamente.

### Veredito Eixo 2

**Recomendação primária: Voltar para `sendmessage_rapido` + reativar `USAR_MOUSE_SHIELD = True`**

Razões:
1. **Já medido 20/20 com mouse movendo** — única configuração com prova de produção
2. Shield custa **~5 ms reais** (liberado no `finally`), não 80 ms
3. `sendmessage_rapido` elimina o stuttering de 15ms (93% redução)
4. O custo de 112 ms/clique medido é **thread do jogo ocupada** — não do bot. O bot fica preso esperando o jogo, mas o clique **sai certo**. Com `postmessage_puro`, o bot roda rápido mas o clique **às vezes falha**.

**Experimento paralelo:** Testar `SendMessageTimeoutW(SMTO_ABORTIFHUNG, 5ms)` — se retorna `FALSE` com `GetLastError()==ERROR_TIMEOUT`, repetir. Isso daria o melhor dos dois mundos: não trava o bot, mas tem confirmação de processamento.

---

## EIXO 3 — Kernel Manager: Veredito Final — Isolamento via Thread Attachment

### Pergunta Central
> **O `AttachThreadInput` entre a thread do bot e a thread de mensagem do jogo resolve o Input Bleed definitivamente?**

### Resposta Curta
**NÃO, não resolve definitivamente se o jogo usa RawInput.** Resolve **parcialmente** (estado virtual de teclado) e **não resolve** mouse (RawInput mouse é separado).

### Análise Detalhada

#### O que `AttachThreadInput` faz
```c
AttachThreadInput(botThreadId, gameThreadId, TRUE);
```
- Fundi as **filas de entrada** das duas threads
- `GetKeyboardState()` no bot → lê estado da thread do jogo
- `SetKeyboardState()` no bot → escreve no estado da thread do jogo
- `GetAsyncKeyState()` → reflete estado da thread do jogo
- **Mouse**: `GetCursorPos`/`SetCursorPos` **não** são afetados (são globais de sessão, não por thread)

#### O que `AttachThreadInput` NÃO faz
| API | Afetada? | Por quê |
|-----|----------|---------|
| `GetKeyboardState` | **Sim** | Estado por thread |
| `GetAsyncKeyState` | **Sim** | Estado por thread |
| `GetKeyState` | **Sim** | Estado por thread |
| `RawInput (WM_INPUT)` | **NÃO** | Dispositivo HID → kernel → `WM_INPUT` para janela registrada |
| `RegisterRawInputDevices` | **N/A** | Registro por janela, não por thread |
| `GetCursorPos` | **Não** | Cursor global de sessão |
| `SetCursorPos` | **Não** | Cursor global de sessão |
| `WH_MOUSE_LL` hook | **Não** | Hook global de sessão |
| `WH_KEYBOARD_LL` hook | **Não** | Hook global de sessão |

#### Cenários de Uso do Jogo (Cliente 6400)

| Cenário | Como o jogo lê teclado | `AttachThreadInput` resolve? |
|---------|------------------------|------------------------------|
| Legado (fila de mensagens) | `WM_KEYDOWN`/`WM_CHAR` | **Sim** — fila compartilhada |
| `GetAsyncKeyState` polling | Estado virtual por thread | **Sim** |
| `GetKeyboardState` snapshot | Estado virtual por thread | **Sim** |
| **RawInput teclado** | `WM_INPUT` com dados HID brutos | **NÃO** |
| RawInput mouse | `WM_INPUT` mouse | **NÃO** |

**Probabilidade no Talisman Online 6400:** **Alta** que use RawInput para teclado (comum em MMOs para anti-macro) e **certa** para mouse (movimento suave).

### Veredito Final

| Eixo | Isolamento via `AttachThreadInput` | Isolamento Total (User-Mode) |
|------|------------------------------------|------------------------------|
| **Teclado - Modificadores** | **Parcial** (só estado virtual) | **Impossível** sem driver se jogo usa RawInput |
| **Teclado - Teclas normais** | **Parcial** (só estado virtual) | **Impossível** sem driver se jogo usa RawInput |
| **Mouse - Posição** | **Não** (cursor é global) | **MouseShield** (hook `WH_MOUSE_LL`) — funciona, medido |
| **Mouse - Cliques** | **Não** | **MouseShield** + `SendMessageW` síncrono — funciona, medido |

### Conclusão Arquitetural

**O isolamento completo de Input Bleed em user-mode NÃO EXISTE** para jogos que usam RawInput. O Windows **não expõe** API para:
- Spoofar estado de hardware HID para uma janela específica
- Isolar `WH_MOUSE_LL`/`WH_KEYBOARD_LL` por thread/janela
- Virtualizar dispositivos de input por processo

**O que É viável (defesa em profundidade):**

1. **Teclado**: Sintéticos `WM_KEYUP` para SHIFT/CTRL/ALT antes de cada tecla + `AttachThreadInput` (se attachable) → reduz sangramento de modificadores para fila de mensagens
2. **Mouse**: `sendmessage_rapido` (1ms) + `MouseShield` reativado → 20/20 medido, ~5 ms custo real
3. **Detecção**: Instrumentar para confirmar se jogo usa RawInput (log `WM_INPUT`, dumpear `RegisterRawInputDevices`)

**Se RawInput confirmado:** Aceitar sangramento residual de modificadores físicos. Mitigar com:
- Sintéticos `WM_KEYUP` antes de cada tecla (já proposto)
- Orientar usuário: "não segure Shift/Ctrl/Alt enquanto bot roda" (documentar)
- `AttachThreadInput` como camada extra se thread attachable

**Não perseguir:** Driver de kernel, filter driver, DLL injection — fora do escopo, risco de ban/anti-cheat, manutenção inviável.

---

## Plano de Ação Consolidado

### Imediato (Esta Sessão)
1. [ ] Implementar `key_down` com **sintéticos `WM_KEYUP` para SHIFT/CTRL/ALT** antes do `WM_KEYDOWN` alvo
2. [ ] Mudar `MODO_DE_CLIQUE = "sendmessage_rapido"` e `USAR_MOUSE_SHIELD = True`
3. [ ] Adicionar log de `WM_INPUT` recebido (hook `WndProc` temporário) para detectar RawInput

### Curto Prazo (Próximas Sessões)
4. [ ] Testar `AttachThreadInput` — obter `GetWindowThreadProcessId`, tentar attach, medir sangramento de modificadores
5. [ ] Experimentar `SendMessageTimeoutW(SMTO_ABORTIFHUNG, 5ms)` como alternativa ao `sendmessage_rapido` + shield
6. [ ] Documentar limitação conhecida: "Modificadores físicos sangram se jogo usa RawInput — não segure Shift/Ctrl/Alt"

### Métricas de Validação
- **Teclado**: Taxa de `Shift+1` indesejado → 0 em 1000 teclas com usuário segurando Shift
- **Mouse**: Taxa de cliques certos com mouse movendo → 20/20 (atual: "às vezes falha" no `postmessage_puro`)
- **Latência**: Tempo de clique ≤ 10 ms (atual: 112 ms medido no `sendmessage_rapido` — investigar se é thread do jogo ou bot)

---

## Referências Cruzadas

- `blazesbot/core/inputs.py` — implementação atual (linhas 1-1152)
- `blazesbot/core/mouse_shield.py` — shield medido 20/20 (linhas 1-351)
- `docs/decisoes/dll-cursor-hook.md` — histórico de tentativas falhas
- `docs/decisoes/stuttering-mouse.md` — por que `PostMessage` importa (timeout infinito do `SendMessageW`)
- `docs/INVARIANTES.md` — regra "Nenhuma mensagem sai para janela que não é o jogo"
- `docs/REGRAS.md` — especificações de teclado/mouse

---

**Princípio norteador:** "Memória primeiro, medido depois, interruptor sempre." Nenhuma das soluções acima quebra o contrato de isolamento de ecossistemas (BC ↔ APP) nem a paridade PyQt6 ↔ Web.