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

Plugin de Claude Code que consulta vários modelos em paralelo e mostra as
respostas lado a lado, com síntese honesta de onde concordam e onde divergem.

- **Fonte:** `https://github.com/hex/claude-council` (MIT, autor `hex`).
- **Instalado pelo CLI oficial** (`claude plugin install
  claude-council@hex-claude-marketplace --scope project`), versão **2026.9.9**,
  commit `14653c8`, em
  `~/.claude/plugins/cache/hex-claude-marketplace/claude-council/2026.9.9`.
  **Não clonar à mão** em `~/.claude/plugins/` — o CLI reescreve
  `installed_plugins.json` e o clone manual some sem aviso.
- **Ativação:** `.claude/settings.local.json` (escopo de projeto).

## Assentos configurados (medidos em 2026-09-06)

`COUNCIL_PROVIDERS="openrouter-1,openrouter-2,openrouter-3,codex"` — 4 assentos,
todos de **custo zero**, uma rodada completa em **13 s**:

| assento | modelo | papel |
|---|---|---|
| `openrouter-1` | `z-ai/glm-5.2:free` | melhor nota em código entre os gratuitos (256k) |
| `openrouter-2` | `cohere/north-mini-code:free` | treinado para terminal e agente de código (256k) |
| `openrouter-3` | `minimax/minimax-m3:free` | contexto de 1M — base inteira no prompt |
| `codex` | Codex CLI v0.150.1 | reusa a subscription OpenAI já autenticada |

O roster **degrada sozinho**: assento que falha reporta o erro na própria coluna
e os outros respondem. Isso importa porque o andar gratuito é instável por
natureza — medido: `minimax-m3:free` bate o **teto diário** (`limit_rpd`, e
crédito não levanta) e `glm-5.2:free` alterna entre responder e
"Provider returned error" conforme o upstream que a OpenRouter sorteia.

**Modelo local foi descartado** (decisão do usuário, 06/09/2026): a RTX 3060
não sustenta modelo útil. Medido antes de descartar: `qwen2.5-coder:14b` derruba
o runner (`llama runner process has terminated`, falha também fora do plugin);
`qwen3:14b` responde em 42 s; `qwen2.5-coder:32b` paga 19 GB de carga — contra
~8 s do OmniRoute. O `ollama` não entra mais no roster local: o assento que
usava esse nome foi substituído pelo provedor próprio `omniroute` (abaixo).

**`thinkingmachines/inkling-small:free` NÃO entra:** a própria OpenRouter recusa
chamada de API para ele ("only available on agentic harnesses"). Não é
configuração — não há assento possível.

## OmniRoute: o 5º assento (opcional, provedor próprio)

O **OmniRoute** (`http://localhost:20128`) é o gateway local do usuário, e
`BlazesBot-IA` é o combo de IAs dele. Ele fala OpenAI
(`/v1/chat/completions`), e **responde em ~8 s**.

**É um provedor de verdade, não emprestado do `ollama`.** A primeira versão
desta configuração colocava a chave do OmniRoute dentro de `OLLAMA_HOST` — um
atalho que funcionava, mas o `ollama` e o OmniRoute não têm relação nenhuma
entre si, e o script do `ollama` não manda header de autenticação, então a
chave precisava viajar escondida no userinfo da URL. Substituído por
**`scripts/providers/omniroute.sh`**, um provedor próprio no mesmo molde do
`openai.sh`/`grok.sh`: `Authorization: Bearer` normal, endpoint e modelo
configuráveis por variável de ambiente própria. Rótulo da coluna: `omniroute`.

Três arquivos do plugin foram tocados para isso (fora do repositório do
BlazesBot — ver "Atenção: sobrevive a update?" abaixo):

- `scripts/providers/omniroute.sh` — o provedor (novo arquivo).
- `scripts/lib/providers.sh` — uma linha em `get_model()`:
  `omniroute) echo "${OMNIROUTE_MODEL:-BlazesBot-IA}" ;;`. A descoberta
  (`discover_providers`) não precisou de nada: um nome que não é nenhuma CLI
  conhecida cai no caso genérico, gated em `OMNIROUTE_API_KEY`.
- `scripts/check-status.sh` — uma sonda em `check_provider()` (`GET /v1/models`
  com Bearer) e uma linha `format_status "OmniRoute" "omniroute" ...`. Antes
  disso o `/claude-council:status` **reprovava o assento que funcionava**,
  porque sondava com `ollama list` — protocolo que o OmniRoute nunca falou.
  Medido depois do conserto: `✓ Connected (1769ms)`.

**Env vars:** `OMNIROUTE_API_KEY` (obrigatória), `OMNIROUTE_MODEL` (obrigatória
— sem default de vendor que faça sentido numa máquina que não configurou
nada), `OMNIROUTE_HOST` (opcional, default `http://localhost:20128`).

**Por que ele NÃO está no `COUNCIL_PROVIDERS` default.** A chave é
infraestrutura local do usuário — decisão deliberada de não colocar no
`settings.json` global, diferente da `OPENROUTER_API_KEY`. Fica em
`.claude/council.env` (ignorado pelo git), opt-in:

```bash
set -a; source .claude/council.env; set +a
/claude-council:ask --providers=omniroute,codex,openrouter-1 "..."
```

**Custo:** quem decide o que o `BlazesBot-IA` consome é a configuração do
OmniRoute, não o council — a regra de "só grátis" abaixo não alcança esse
assento.

**Atenção: sobrevive a `claude plugin update`? NÃO.** As três edições acima
vivem dentro do cache do plugin
(`~/.claude/plugins/cache/hex-claude-marketplace/claude-council/2026.9.9/`),
que o CLI **reconstrói do zero** a partir do marketplace a cada update —
exatamente o motivo pelo qual clonar o plugin à mão não sobrevive (ver nota no
topo deste documento). Um `claude plugin update claude-council` apaga
`omniroute.sh` e as duas edições em `providers.sh`/`check-status.sh` sem
avisar. Se isso acontecer, refazer é reaplicar este mesmo bloco — o conteúdo
dos três trechos está descrito acima.

## Custo: ZERO, por desenho (diretiva permanente do usuário — 06/09/2026)

**Nada pago. Nunca.** Acabou a cota de um modelo, aquele assento simplesmente
para de responder — não existe troca por alternativa paga. O que sustenta isso:

- **Todo id do roster termina em `:free`.** É o sufixo que prende a chamada ao
  andar gratuito da OpenRouter; medido: a resposta volta com `"cost": 0`.
- **A OpenRouter não tem degrade automático neste plugin.** O mapa
  `MODEL_FALLBACKS` (`scripts/lib/model_fallback.sh`) cobre openai, grok,
  perplexity, gemini e kimi — **nenhum assento `openrouter`**. Sem entrada no
  mapa, o código segue por "no configured fallback: one plain attempt": o
  assento falha e pronto, não reenvia para outro modelo.
- **`OPENROUTER_MODEL="z-ai/glm-5.2:free"` está fixado como trava.** Não é
  redundância com `OPENROUTER_MODELS`: um `--providers=openrouter` (sem número)
  não casa com o roster e cai no default do plugin, que é
  **`anthropic/claude-sonnet-5` — PAGO**. A trava neutraliza esse caminho.
- **`codex` não é metered:** `codex login status` responde *"Logged in using
  ChatGPT"* — assinatura de valor fixo, não chave de API por token.
- **Se um dia entrar chave de Gemini/OpenAI/Grok/Perplexity/Kimi, o combinado
  quebra:** esses cinco TÊM degrade automático para modelo pago no mapa acima.
  Não adicione chave desses provedores sem antes tratar isso.

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
- Em loop, sem filtro — invocar o council a cada alteração de 3 linhas gasta
  cota do andar gratuito sem retorno.

## Como invocar

```
# Padrão: usa o roster de COUNCIL_PROVIDERS
/claude-council:ask "Should I use UUID or BIGINT primary keys here?"

# Forçando assentos específicos
/claude-council:ask --providers=openrouter-1,codex "Review this design"

# Com lentes (roles)
/claude-council:ask --roles=balanced "Compare these two strategies"

# Debate em duas rodadas (cada assento vê os outros e rebate)
/claude-council:ask --debate --providers=openrouter-1,codex "..."

# Verificar o que está de pé
/claude-council:status
```

Direto pela shell (sem slash command):
```bash
set -a; source .claude/council.env; set +a
cd ~/.claude/plugins/cache/hex-claude-marketplace/claude-council/2026.9.9
bash scripts/query-council.sh --providers=openrouter-1,codex -- "Your question"
```

## Onde mora cada peça da configuração

- **`.claude/settings.json`, bloco `env`** — `COUNCIL_PROVIDERS` e
  `OPENROUTER_MODELS`. O Claude Code exporta esse bloco para todo Bash e todo
  hook, então o council já nasce com o roster certo. **Nada de segredo aqui:
  este arquivo é versionado.**
- **`~/.claude/settings.json` (settings GLOBAL do usuário), bloco `env`** — a
  `OPENROUTER_API_KEY`. Fica fora de qualquer repositório, então não há risco de
  commit, e vale para toda sessão de Claude Code sem cerimônia nenhuma. Medido:
  os 3 assentos gratuitos passaram a responder **sem** sourcear nada. Antes disso
  a chave só vivia no `council.env` e um turno normal tinha **só o codex** de pé
  (`Error: OPENROUTER_API_KEY not set` nos outros três).
- **`.claude/council.env`** — `OMNIROUTE_API_KEY` e `OMNIROUTE_MODEL`. Decisão
  deliberada de não subir para o global: é infraestrutura local do usuário, não
  algo que toda sessão de Claude Code devia herdar sem pensar. **Ignorado pelo
  git**; carregar com `set -a; source .claude/council.env; set +a` só quando
  quiser o OmniRoute.
- **`.claude/council.env.example`** — o mesmo template, sem chave, versionado.
- **`.claude/council-stop-gate.json`** — o Stop hook (abaixo).

## Stop-gate (revisão automática do diff) — DESLIGADO

O que é: um hook de `Stop` que, no fim de cada turno, pega o `git diff HEAD` e
manda para um provedor revisar. Se o revisor responder BLOCK, o turno não fecha
— a IA é obrigada a continuar trabalhando no que ele apontou.

**Está `"enabled": false`** em `.claude/council-stop-gate.json`. O arquivo fica
no lugar, com `provider` e `max_iterations` já ajustados, para ligar trocando uma
palavra.

**Por que desligado, medido em 06/09/2026:** ele só se cala em árvore limpa
(`[[ -z "$DIFF" ]] && exit 0`), e **esta árvore nunca está limpa**. Há alteração
não commitada em `web/main.js`, `web/style.css`, `web/index.html` e
`.claude-flow/` desde 05/09 — **8.595 linhas em 5 arquivos**. O gate mandaria
esse diff velho inteiro para revisão no fim de **todo** turno, sem relação
nenhuma com a tarefa em curso: latência de até 120 s e risco de bloqueio por
ruído, para revisar o que ninguém pediu.

Some o motivo se essa sujeira for commitada ou descartada. Mesmo aí o ganho é
pequeno: pela regra 0 do `CLAUDE.md` (**toda alteração ⇒ commit no mesmo passo**)
a árvore deveria estar limpa ao fim do turno, então o gate ficaria mudo — e
quando falasse, seria justamente porque a regra 0 já tinha sido violada.

**Se um dia ligar:** `provider` fica em `codex`. Com codex o diff não sai da
assinatura já autenticada da máquina. **Nunca aponte para `openrouter`** — lá o
diff é revelado duas vezes, à OpenRouter e ao upstream que serve o modelo. O
assento do OmniRoute também não serve aqui: `OMNIROUTE_API_KEY` mora no
`council.env`, que o hook não carrega.

Salvaguardas do gate, quando ligado: não roda em árvore limpa, não se re-dispara
numa continuação que ele mesmo provocou, bloqueia no máximo `max_iterations`
vezes por sessão, e **qualquer falha do revisor libera o Stop** (falha aberta,
`jq` ausente incluído).

## Princípio de uso neste projeto

- Council **complementa** graphify, INVARIANTES e REGRAS — **não substitui**.
- Para qualquer decisão sobre o jogo: graphify + memória primeiro; council
  só se a dúvida for metodológica/arquitetural.
- `task-observer` continua sendo a meta-skill auto-invocada para observar
  padrões. Não acionar o council a partir de observação do task-observer.

## Limitações conhecidas

- Sem `tmux` no host Windows → streaming side pane indisponível; o council
  cai no renderer perl/Rich (output bufferizado no terminal).
- `jq` é obrigatório (scripts falham sem ele). Já resolvido: jq 1.8.2 em
  `~/.local/bin/jq.exe`, que está no PATH do usuário.
- O README do plugin cita flags `--list-default`, `--list-default-models` e
  `--list-available` no `check-status.sh` que NÃO existem na 2026.9.9.
