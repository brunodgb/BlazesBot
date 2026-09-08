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

## Quando usar (e quando NÃO) — diretiva permanente do usuário (06/09/2026)

**Sem limite de uso.** O roster default é zero-custo (seção acima), então não
há cota a poupar — peça uma segunda opinião sempre que a dúvida for real, sem
se policiar por frequência. O que resta é critério de **sinal**, não de custo:

**Usar:**
- Decisões de arquitetura com tradeoffs reais (qual lib, qual design pattern).
- Debugging dead-end (já tentou 2+ vezes, nada bateu).
- Cross-check de segurança/performance/maintainability em mudança grande.
- "Estou em dúvida entre A e B, o que o council acha?"
- Qualquer dúvida real, mesmo pequena — o custo zero já resolveu a hesitação.

**NÃO usar:**
- Implementação mecânica (uma linha, um fix óbvio) — não é limite de cota,
  é que não há pergunta real ali para perguntar a ninguém.
- Perguntas com resposta única e clara.
- Decisões de código deste projeto que dependem do **estado do jogo** —
  council é externo, **não tem acesso à memória do bot, ao graphify nem
  aos logs JSONL**. Para debugging real do BlazesBot: graphify + logs.

**A resposta é insumo, nunca veredito.** Trate todo retorno do council como
material de análise, não como verdade absoluta:
- Avalie criticamente os pontos levantados — um assento pode estar certo,
  errado, ou certo pela razão errada.
- Compare as respostas dos assentos entre si e contra a alternativa que você
  já tinha em mente antes de perguntar.
- Teste a solução escolhida contra o cenário mais extremo que ela precisa
  aguentar antes de aplicar — o council opina sobre o caso geral; quem conhece
  o caso extremo deste projeto (memória, offsets, o que já reprovou em
  `docs/decisoes/`) é você.
- A decisão final é sempre sua. Concordância entre assentos não é prova —
  é só mais um dado. Os 3 assentos da OpenRouter hoje são 3 modelos distintos
  (tabela acima), então concordância entre eles não é o mesmo modelo
  respondendo duas vezes — mas isso muda se `OPENROUTER_MODELS` for editado
  para repetir um id.

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

# Skill: i18n (interface em PT-BR / EN / ES)

Mecanismo central de tradução da interface — texto deixa de ser fixo no
HTML/JS/PyQt6 e passa a vir de um dicionário único por chave.

- **Fonte:** `blazesbot/locales/traducoes.json` — `{"chave": {"pt-br": "...",
  "en": "...", "es": "..."}}`. PT-BR é obrigatório em toda chave; EN/ES podem
  faltar sem quebrar nada.
- **Resolução:** `blazesbot/core/i18n.py` (`core/` porque não sabe que
  ecossistema existe — GUI e Web usam o mesmo módulo). `traduzir(chave,
  idioma)` cai para PT-BR se o idioma não existe ou a chave não tem entrada
  nele; se a própria chave não existe, devolve `[chave]` em vez de lançar —
  testado em `tests/test_i18n.py`, inclusive o caso real de fallback
  (`diag_dpapi_indisponivel` não tem `"es"` de propósito).
- **Config:** `BotConfig.idioma` (`data/config.json`), default `"pt-br"`.

## Onde cada interface está (estado em 07/09/2026)

- **Web (`web/`) — retrofit completo do que é HTML/JS estático e dinâmico**,
  verificado ao vivo (Chrome + CDP, `test-web.ps1`, ver
  `docs/decisoes/interface.md` para a receita — incluindo o editor de conta
  ABERTO durante a troca de idioma, o caso mais difícil). Dropdown na titlebar
  (`#sel-idioma`), bridge `Api.definir_idioma` (mesmo padrão de
  `definir_senha`/`definir_login` — aplica na hora, grava no `config.json`),
  `constantes.traducoes` manda os 3 idiomas já resolvidos de uma vez (sem
  round-trip ao trocar). **311 chaves.**
  **Convertido — todo texto que é PRÓPRIO da interface (não vem do
  backend):** as 6 seções inteiras (Contas, Cliente, Estatísticas, Quedas,
  Log, Diagnóstico), o modal de edição de conta com as 5 abas (Personagem,
  Teclas — 28 rótulos de tecla + os balões de ajuda —, APP, Bewitcher Cave,
  HH), o modal de confirmação, todo toast, todo tooltip (`title`), todo
  placeholder, o `alt` da imagem de queda, o `aria-label` da alça de
  arrastar, e os rótulos que `main.js` monta em tempo de execução (linhas da
  tabela de Contas, cartões de queda, explicação do modo de sincronia do
  time, prévia da macro do APP).
- **A troca de idioma RE-RENDERIZA o que já está dinamicamente construído**,
  não só varre `data-i18n`: `aplicarIdioma()` chama de novo `renderContas()`,
  `atualizarFiltroLog()`, `popularSeletores()`, `carregarStats()`,
  `carregarQuedas()` (se a aba já foi aberta), e — o caso mais delicado —
  re-busca e repreenche o editor de conta (`obter_conta` +
  `preencherEditor`) **se ele estiver aberto no momento da troca**. Sem isto,
  o modal já aberto ficaria com tooltip e rótulo dinâmico no idioma antigo até
  ser fechado e reaberto.
- **PyQt6 (`blazesbot/gui/`) — NÃO TOCADO.** A regra permanente "duas
  interfaces convivem" (`CLAUDE.md`) exige que qualquer coisa na Web exista
  também na GUI PyQt6. Isso está PENDENTE: nem o campo de idioma, nem o
  seletor, nem uma única chave do dicionário foram plugados lá. Enquanto
  isso não for feito, a Web tem uma capacidade que a GUI não tem — o mesmo
  tipo de dívida que o `CLAUDE.md` já rastreia em "Candidatos de promoção".

## O que continua em PT-BR fixo, e por quê (pendência real, não esquecimento)

Tudo abaixo é texto **composto no Python**, não na interface — traduzi-lo
exigiria mudar a fonte, não a tela, e a decisão de arquitetura é maior que
"adicionar mais uma chave". Cada item foi deixado de propósito, com o texto
em PT-BR passando direto (`r.erro`, `r.resumo` etc., sem tradução):

- **Conteúdo do Log — mecanismo IMPLEMENTADO, catálogo PARCIAL** (diretiva do
  usuário, 07/09/2026: "só o que é visto pelo usuário, e só a partir da
  troca — log já gravado fica como está"). Ver "Log: só o que é gerado a
  partir da troca" logo abaixo para como funciona e como estender.
- **Histórico de Quedas**: `q.rodando_texto`, `q.motivo_texto`,
  `q.fazendo_texto`, `q.onde_texto`, `q.quando_texto` vêm PRONTOS de
  `core/quedas.py::amigavel()`. Mesma pendência do Log, em miniatura.
- **Cards de Estatísticas**: `c.rotulo` de cada card vem de `stats_diarias.py`
  via `_App.constantes()`/`stats_conta`.
- **Opções de resolução/montaria/bolsas/cliques de venda**: os RÓTULOS
  completos (`"90%   (1.0x)"`, `"1 bolsa   (10 espaços)"`) são montados em
  `_App.constantes()`, não na Web.
- **Resumo dos testes de Diagnóstico**: `r.resumo_curto` (amostragem de
  cliques) e `r.resumo` (conferência de exclusão) vêm prontos de
  `amostragem_de_cliques.py`/`afericao.py`. Só o texto ao REDOR (toasts de
  início/erro) foi convertido.

## Log: só o que é gerado a partir da troca (implementado em 07/09/2026)

Diretiva do usuário, mais estreita do que "traduzir todo o log": **linha já
escrita fica exatamente como foi gravada; só o log GERADO depois da troca de
idioma sai no idioma novo.** Não existe (e não faz sentido existir)
retradução do que já está na tela ou no arquivo — histórico é histórico.

- **Sem tocar nenhuma das ~775 chamadas** `log.info/warning/error(...)`
  espalhadas por `bot/`, `bot/bc/`, `bot/app/`, `bot/hh/`, `core/`. O
  TEXTO-FONTE de cada chamada (ex.: `"Revivendo"`, `"Não consegui salvar a
  configuração: %s"`) já É a chave — não existe um nome de chave separado
  para inventar por call site.
- **Fonte:** `blazesbot/locales/logs.json` — `{"template pt-br exato":
  {"en": "...", "es": "..."}}`. Diferente de `traducoes.json`, aqui **não há
  PT-BR dentro do valor**: a própria chave já é o PT-BR.
- **Resolução:** `blazesbot/core/i18n.py` —
  `definir_idioma_do_log(idioma)` / `idioma_atual_do_log()` guardam o idioma
  do log como **estado do processo** (não da UI — os call sites de log rodam
  nas threads dos supervisores, sem acesso a `BotConfig`).
  `traduzir_mensagem_de_log(template)` faz o lookup pelo texto-fonte; sem
  entrada no catálogo, ou catálogo sem aquele idioma, devolve o `template`
  **inalterado** — é assim que as chamadas ainda não catalogadas continuam
  saindo em PT-BR sem quebrar nada.
- **Ligação:** `blazesbot/web_app.py::_LogHandler._formatar()`. Troca o
  TEMPLATE da mensagem pela tradução e refaz o `%`-substituição com os
  MESMOS args — nunca muta `record.msg`/`record.args`, porque outro handler
  no mesmo logger (o log de dev, se algum dia existir um) recebe o MESMO
  objeto `record` e tem que continuar vendo o PT-BR original. Testado em
  `tests/test_log_traduzido.py`, inclusive a garantia de não-mutação.
  `_App.__init__` acerta o idioma do log a partir do `config.json` salvo
  (log já sai certo desde a primeira linha, sem esperar o usuário reabrir o
  seletor); `_App.definir_idioma()` atualiza a cada troca.
- **Cobertura real do catálogo agora: 98 templates**, verbatim grepados do
  código-fonte (não parafraseados) — cobrindo os 3 casos de duplicata exata
  confirmados pela investigação (`"Não consegui salvar a configuração: %s"`
  × 6, `"Não abri o diálogo do %s"` × 4, `"PetBug: %s"` × 3) mais uma boa
  fatia de mensagens sem argumento de `combate.py`, `morte.py`, `login.py`,
  `team.py`, `bc/routine.py`, `bc/ui_service.py`, `supervisor.py`,
  `hh/fada.py`, `hh/routine.py`. **Isto está longe de cobrir as ~90–140
  famílias reais** que a investigação completa mediu — é um catálogo vivo,
  cresce por adição, não por reescrita.
- **Para catalogar uma mensagem nova:** copie o texto-fonte EXATO (grep no
  `.py`, nunca de memória — um espaço ou acento diferente não bate a chave e
  a mensagem some do catálogo em silêncio, sem erro), adicione a entrada em
  `logs.json` com `en`/`es`, e pronto — nenhum código muda. Mensagens com
  `%s`/`%.0f%%` no meio da frase: mantenha os placeholders na MESMA posição
  em toda tradução (reordenar argumento por idioma não é suportado; é
  `%`-formatting posicional, não nomeado).
- **NÃO cataloga:** `log.debug(...)` (em produção o logger fica travado em
  `INFO+` — `web_app.definir_nivel_log` —, então debug já não chega à tela
  do usuário final) nem mensagens que carregam payload estruturado em vez de
  prosa (ex.: `core/cronometro.py` loga um `json.dumps(...)` inteiro).

## Armadilhas reais encontradas (guarde antes de estender)

- **Elemento reescrito por outro código nunca leva `data-i18n` estático.**
  `#estado-roda` e `#diag-status` são reescritos a cada poll de 1,5 s a partir
  do ESTADO do bot — um `data-i18n` ali seria sobrescrito meio segundo depois.
  A correção certa é o PRÓPRIO ponto que escreve o texto chamar `t(chave)` (é
  o que `atualizarEstado()` já faz). **Vale para qualquer texto dinâmico
  novo: `t(chave)` no ponto de escrita, nunca `data-i18n` num elemento que
  outro código também escreve.**
- **Variável local chamada `t` derruba a tradução em silêncio.** `t` já era
  usado como nome de variável comum neste arquivo (ex.: `const t =
  est.total || {}` dentro de `atualizarEstado`) — isso SOMBREIA a função
  global `t()` de tradução dentro daquele escopo, e qualquer chamada
  `t("chave")` ali dentro vira `TypeError`, não erro visível na tela. Achado
  testando de verdade (nenhum teste automatizado pega isso). Renomeada para
  `totais`. Ao adicionar uma chamada `t(...)` nova, confira que não há `const
  t`/`let t`/parâmetro `t` no mesmo escopo.
- **Elemento com filho (checkbox, ícone) não leva `data-i18n` na própria
  tag** — isso sobrescreve `textContent` e apaga o filho. O texto precisa
  estar num `<span>` próprio ao lado (padrão usado em toda a navegação
  lateral e nos rótulos de tecla com balão de ajuda).
- **Trecho com HTML embutido (`<code>`, `<b>`) usa `data-i18n-html`**
  (`innerHTML`), nunca `data-i18n` — os 4 parágrafos do Diagnóstico e os 3 da
  aba HH são os únicos casos; o HTML vem inteiro da própria tabela de
  tradução, nunca de entrada do usuário, então não há risco de injeção.
- **Mensagem com valor embutido no meio da frase usa `t(chave, {parametros})`**
  — `t()` substitui `{nome}` no texto traduzido pelo valor correspondente.
  Nunca concatene o valor por fora (`t("x") + valor`): a posição do valor na
  frase muda de idioma para idioma (`{n} contas` vs `{n} accounts`).
