  # Skill: Desenvolvedor Desktop Web (pywebview + Web Frontend)

## Arquitetura Obrigatória
Este projeto usa o `pywebview` (WebView2) para criar uma aplicação desktop.
- Backend: Python puro.
- Frontend: Tecnologias Web (HTML, CSS, JS puro).
- NUNCA use bibliotecas como Tkinter, PyQt ou Streamlit.

## Regras de Integração Python-JS
1. Toda função Python que o frontend chama é método público da classe `Api`
   (o objeto `js_api` do pywebview) em `blazesbot/web_app.py` — métodos que
   começam com `_` NÃO são expostos.
2. Do lado JS, o backend é chamado via `window.pywebview.api.<nome>(...)`
   (cada chamada resolve uma Promise com o retorno). O helper `chamar()` no
   `web/main.js` faz isso com tolerância a falha (devolve `null`).
3. Mantenha a separação rígida:
   - Python NUNCA formata HTML. Ele retorna dicionários/JSON ou executa lógicas de sistema.
   - JavaScript NUNCA processa regras de negócio pesadas. Ele chama o Python via `window.pywebview.api.nome_funcao_python()`.

## Estrutura de Pastas Esperada
- `main.py` (Ponto de entrada do aplicativo PyQt6; a web só importa
  `require_admin`/`setup_logging` dele).
- `web/` (Pasta exclusiva do frontend, editada na mão).
  - `web/index.html` — classes utilitárias Tailwind, preservando os IDs do JS.
  - `web/style.css` — Tailwind v4 (`@import "tailwindcss"` + `@theme`) e os
    componentes que o JS toca em runtime (`.painel-aba`, `.estado-roda`,
    `.captura`, `.toast`, `.cel-texto`, `.linha-log`, etc.).
  - `web/main.js`
- `vite.config.js` (raiz) — plugin Tailwind, `root: 'web'`,
  `build.outDir: '../dist'`, `base: './'` (URLs relativas para o `file://`).
- `dist/` — saída de `npm run build`; é o que o pywebview abre.

## Regras de Design
- A interface deve parecer um software nativo: oculte barras de rolagem desnecessárias, evite a seleção acidental de texto (`user-select: none` no CSS) e use um esquema de cores Dark Mode moderno com bom contraste.

# Skill: GUI (Interface Gráfica) e Interatividade

## 1. Regras de Design e Experiência do Usuário (UX)

**Objetivo**: Criar interfaces bonitas, intuitivas e que pareçam profissionais (estilo "desktop nativo" ou "SaaS moderno").

- **Seleção de Itens (Grid View)**:
    - **Grid Flexível**: Use `display: grid` no CSS para criar layouts responsivos que se ajustam ao tamanho da janela.
    - **Interação de Clique**: O clique em um item deve:
        1. Marcar visualmente o item selecionado (ex: borda colorida, fundo "injetado").
        2. **Atualizar o estado do Python imediatamente** (evite buffers).
        3. O item selecionado deve ser "arrastável" ou transferível para slots de ação.
    - **Visualização de Dados**: Cada célula do grid deve mostrar claramente:
        - Ícone do item.
        - Nome do item.
        - Quantidade (se aplicável).
        - **Preço de venda** (valor em ouro/moeda). Opcional: preço de compra (custo) para referência.

- **Navegação e Controle**:
    - **Barra de Título/Controle**: Em vez da barra nativa do Windows/Linux, crie uma barra customizada no topo com:
        - Botão de Minimizar.
        - Botão de Fechar.
        - Botão de "Modo Escuro/Claro" (Toggle Theme).
        - Ícone do Aplicativo.
    - **Layout Limpo**: Evite scrollbars horizontais. Se o conteúdo exceder, use scroll vertical ou redimensione o grid.

## 2. Arquitetura Técnica (pywebview + Web)

- **Princípio RPC (Remote Procedure Call)**: A interface é apenas "visão". A lógica é "cérebro" (Python).
- **Atualização em Tempo Real**:
    - O `web_app.py` NÃO usa push do Python→JS: segue o mesmo desenho da GUI, um
      handler enfileira o log numa `deque` e o JS PUXA por poll
      (`puxar_log` a cada ~300 ms; `estado` a cada 1,5 s). Isso evita chamar o
      bridge de outras threads.
    - Para eventos de UI (como arrastar e soltar), use eventos de mouse/toque padrão (`dragstart`, `dragover`, `drop`).

## 3. Limitações Técnicas (O que NÃO fazer)

- **NÃO** use `confirm()` ou `alert()` do navegador. Crie componentes de modal/popup customizados no HTML/CSS.
- **NÃO** faça consultas pesadas (ex: processar milhares de itens) diretamente no clique inicial. Use Web Workers no JS se necessário, ou delegue ao Python de forma assíncrona.

## Agent skills

### Issue tracker

Issues e specs vivem como arquivos markdown em `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Layout single-context: um `CONTEXT.md` + `docs/adr/` na raiz. See `docs/agents/domain.md`.

# Skill: claude-council (consulta multi-agente)

Plugin de Claude Code que consulta múltiplos IAs em paralelo (Gemini, OpenAI,
Grok, Perplexity, Kimi, OpenRouter, codex CLI, Antigravity, **Ollama local**)
e mostra as respostas lado a lado, com síntese honesta de concordância.

- **Fonte:** `https://github.com/hex/claude-council` (MIT, autor `hex`).
- **Instalado em:** `~/.claude/plugins/marketplaces/hex-claude-marketplace/claude-council`
  (versão 2026.9.8, commit `9d49926`).
- **Ativação:** `.claude/settings.local.json` (escopo local no projeto,
  como o usuário pediu).
- **Status atual dos provedores** (verificado em 2026-09-06):
  - **Ollama** ✓ conectado (703ms, v0.21.0) — modelo default `llama3.2`
    (não instalado). Para usar o `qwen2.5-coder:14b` já presente no host,
    exportar `OLLAMA_MODEL="qwen2.5-coder:14b"` antes de invocar.
  - **Codex CLI** ✓ conectado (761ms, v0.150.1) — reusa a subscription
    OpenAI já autenticada do projeto.
  - **Gemini, OpenAI, Grok, Perplexity, Kimi, OpenRouter** — chave não
    setada. Adicionar via env var para ativar.
  - **Kimi CLI, Antigravity, Grok CLI** — não instalados.

## Quando usar (e quando NÃO)

**Usar:**
- Decisões de arquitetura com tradeoffs reais (qual lib, qual design pattern).
- Debugging dead-end (já tentou 2+ vezes, nada bateu).
- Cross-check de segurança/performance/maintainability em mudança grande.
- "Estou em dúvida entre A e B, o que o council acha?"

**NÃO usar:**
- Implementação mecânica (uma linha, um fix óbvio).
- Perguntas com resposta única e clara.
- Decisões de código deste projeto que dependem do **estado do jogo** —
  council é externo, **não tem acesso à memória do bot, ao graphify nem
  aos logs JSONL**. Para debugging real do BlazesBot: graphify + logs.
- Em loop, sem filtro — o cache já cuida, mas invocar o council para cada
  alteração de 3 linhas custa Ollama/Codex sem retorno.

## Como invocar

```
# Padrão: usa COUNCIL_PROVIDERS ou todos os conectados
/claude-council:ask "Should I use UUID or BIGINT primary keys here?"

# Forçando provedores específicos
/claude-council:ask --providers=ollama,codex "Review this design"

# Com lentes (roles)
/claude-council:ask --roles=balanced "Compare these two strategies"

# Debate em duas rodadas (cada provedor vê os outros e rebate)
/claude-council:ask --debate --providers=ollama,codex "..."

# Verificar o que está funcionando
/claude-council:status
```

Direto pela shell (sem slash command):
```bash
cd ~/.claude/plugins/marketplaces/hex-claude-marketplace/claude-council
bash scripts/query-council.sh --providers=ollama,codex -- "Your question"
```

## Configuração local

- **Template de env:** `.claude/council.env.example` (copie para
  `council.env` e descomente o que quiser). Ativar com `set -a; source
  .claude/council.env; set +a` antes de invocar.
- **Ollama model:** fixar via `OLLAMA_MODEL="qwen2.5-coder:14b"`. Sem isto,
  o default `llama3.2` falha e o plugin escolhe fallback verificado.
- **Stop-gate:** **DESLIGADO por padrão** (decisão do usuário em 2026-09-06).
  Razão: o stop-gate envia o diff não-commitado para um provedor revisar;
  o bot tem offsets de memória do jogo, paths internos e padrões que não
  devem vazar. Ollama local seria aceitável, mas o desenho "um commit por
  menor alteração" (governança) já é o próprio gate. Para ativar: ver
  `.claude/council.env.example` e a doc do plugin.

## Princípio de uso neste projeto

- Council **complementa** graphify, INVARIANTES e REGRAS — **não substitui**.
- Para qualquer decisão sobre o jogo: graphify + memória primeiro; council
  só se a dúvida for metodológica/arquitetural.
- `task-observer` continua sendo a meta-skill auto-invocada para observar
  padrões. Não acionar o council a partir de observação do task-observer.

## Limitações conhecidas

- Sem `tmux` no host Windows → streaming side pane indisponível; o council
  cai no renderer perl/Rich (output bufferizado no terminal).
- Sem `jq` global → scripts falham. Já resolvido (jq 1.8.2 em
  `~/.local/bin/jq.exe`, que está no PATH do usuário).
- README menciona flags `--list-default`, `--list-default-models` e
  `--list-available` no `check-status.sh` que NÃO existem na versão
  2026.9.8 (issue upstream menor).