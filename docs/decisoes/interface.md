# As duas interfaces — decisões e medições

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.

- **A web tem balão de ajuda por CAMPO** (`.ajuda` + `#balao-ajuda`, em
  `style.css`/`main.js`), equivalente ao `HelpTip` da GUI. **O balão vive no
  `<body>` com `position: fixed`**, e isso não é capricho: os painéis do modal
  rolam (`overflow-y: auto`) e um balão posicionado dentro deles seria CORTADO na
  borda — justamente nos campos de baixo, que são os que mais precisam de
  explicação. O JS calcula a posição a partir do `getBoundingClientRect()` do
  "?" e vira para a esquerda/para cima quando não cabe (a janela é travada em
  1200×800, então isso acontece de verdade). O texto vai em `data-ajuda` com
  `&#10;` nas quebras e `white-space: pre-line` no CSS.
  Na GUI o equivalente é o terceiro item opcional de cada campo em
  `_bloco_teclas`: `(rótulo, atributo, ajuda)` põe um `HelpTip` só daquele campo.
- **Tecla repetida é BARRADA nas duas interfaces, na digitação.** O jogo não
  permite a mesma tecla em duas funções — cada uma tem um destino só no Keys
  Setting —, então aceitar descreveria algo que não existe: o bot mandaria a
  tecla achando que troca de barra e o jogo dispararia uma skill, **sem nunca
  perceber**. `KeyBinds.teclas_repetidas()` é o backstop em `validate()`; na web
  o bloqueio está no `keydown` (varre `[id^="ed-k-"]`) e na GUI no
  `KeyCapture.keyPressEvent` via `AccountDialog._tecla_em_uso`. **As teclas do
  APP ficam de fora da conta de propósito** — lá a MESMA tecla se repete na
  sequência por desenho. O próprio campo também é ignorado: reapertar a mesma
  tecla nele é nada-a-fazer, não conflito.
- **Tela "Histórico de Quedas", entre Estatísticas de BC e Log nas DUAS
  interfaces.** Núcleo em `blazesbot/core/quedas.py`; a GUI e a web só desenham.
  Responde, para cada queda: QUANDO (data e hora exatas), O QUE aconteceu, O QUE
  o bot estava fazendo, e COMO estava a tela.
  - **Só queda REAL do jogo** — as três da `watchdog.DcReason`. `Disconnected`
    também é levantada por leitura de memória ruim ("posição ilegível em
    `goto()`"), e isso não é queda: o gatilho é `ctx.ultima_queda`, que **só o
    watchdog escreve**, e não o tipo da exceção.
  - **`ctx.ultima_queda`, e não um campo no watchdog**, porque existem **DOIS
    watchdogs por conta** (um no supervisor, outro na rotina) e quem grava não
    sabe qual dos dois percebeu. O `ctx` é o mesmo para os dois.
  - **A ORDEM É OBRIGATÓRIA:** o registro sai em `_run_session`, num
    `except (Disconnected, ClientClosed)` que regrava e re-levanta. É o último
    ponto em que o `ctx` existe e o cliente ainda está VIVO — quem trata acima
    chama `_encerrar_caido`, que **MATA a janela**.
  - **O print só existe numa das três quedas.** Em `PROCESS_GONE` e
    `WINDOW_GONE` a janela já morreu quando a queda é percebida: o cartão sai
    sem imagem, sem inventar explicação. No `RECONNECT_DIALOG` o print é **o
    próprio quadro que detectou o aviso** (`_quadro_com_aviso_de_conexao` passou
    a devolver o quadro em vez de um booleano) — ele tem o aviso na imagem por
    construção. Uma captura nova, milissegundos depois, sairia preta: o cliente
    pode fechar a qualquer instante, e isso aconteceria justamente no único tipo
    de queda em que o print era possível.
  - **JPEG, mais uma MINIATURA de 320 px ao lado.** A miniatura não é estética,
    é restrição: a página web roda em `file://` e o WebView2 **recusa `<img src>`
    apontando para outro arquivo local**, então a imagem viaja embutida
    (`data:` URI). Mandar 30 prints inteiros por carregamento seriam megabytes;
    a miniatura fica na casa das dezenas de KB e o print inteiro só é pedido
    quando o usuário CLICA (`print_da_queda`).
  - **A tela carrega ao ABRIR a seção, não no poll de 1,5 s** — isto REVISA o
    que eu havia combinado. Com as miniaturas embutidas, repetir o carregamento
    duas vezes por segundo seria megabytes por minuto para mostrar a mesma
    lista, e queda é evento raro. Recarrega ao abrir e ao trocar a conta.
  - **NADA DE DEV NA TELA, e a garantia é por construção.** A frase do "onde
    parou" vem de `FASES`, um mapa FECHADO de nome-de-estado → frase escrita à
    mão — **nunca da última linha de log**. Log é texto livre (fala de waypoint,
    flag de combate, endereço de memória, coordenada de clique), e um filtro
    sobre texto livre é lista negra: só protege do que alguém lembrou de
    proibir. As 20 linhas de log são gravadas, mas só aparecem no arquivo e no
    "Copiar relatório". Travado por teste: toda `State` da rotina precisa ter
    frase, e nenhuma frase pode conter jargão.
  - **Retenção por TEMPO: 3 dias** (`DIAS_GUARDADOS`), e a poda apaga a linha,
    o print e a miniatura JUNTOS — histórico sem imagem é meio registro, imagem
    sem histórico é lixo que ninguém encontra.
  - **"Copiar relatório" leva o técnico que a tela esconde** (fase crua,
    coordenadas, PID, run, relogin, as 20 linhas). Ele existe para chegar ao
    desenvolvedor: levar só o que está na tela faria o dev receber o mesmo que
    já viu no print do usuário.
  - **Seletor com "Todas as contas" primeiro e padrão** — a pergunta real é "o
    que aconteceu essa noite", e ela atravessa contas.
  - **As últimas linhas de log vêm de `quedas.CapturaDeLog`**, instalada em
    `main.py:setup_logging` (o único ponto que as duas interfaces já
    compartilham). Não dá para usar a fila da interface: a queda é gravada por
    uma thread do supervisor, que não conhece interface nenhuma.
  - Gravar **nunca levanta**: falhar no histórico não pode atrapalhar o
    relogin, que é o que devolve a conta ao ar.
- As **estatísticas de tempo têm cronômetros AO VIVO da run em andamento**,
  além dos tempos FIXOS da última run concluída. Os cronômetros **começam a
  contar quando o bot CONFIRMA que está dentro da cave** — o `RunStats.begin_run`
  foi movido para depois do laço de entrada em `routine._do_entrar` (a disputa
  da entrada, que pode levar minutos, fica de fora). As fontes são
  `RunStats.run_now_seconds` (tempo total, deriva de `run_started_at`, que só é
  não-zero DURANTE a run) e `RunStats.boss_now_seconds` (tempo do trajeto até o
  boss, que CONGELA no valor da chegada — `boss_atingido`), expostos por conta
  no `summary()`/`estado()` como `run_now`, `boss_now` e `boss_atingido`
  (0.0/false entre runs). Na web o banner `#cronometro-atual` (na seção
  Estatísticas, FORA do grid que o `carregarStats` recria) mostra os DOIS
  tempos ao vivo em colunas e extrapola localmente entre os polls de 1,5 s para
  \"correr\" fluido; na GUI os cards `run_agora` e `boss_agora` fazem o mesmo,
  repreenchidos em `_preencher_stats_conta` a cada `_refresh_status`. Os cards
  `boss_ult`/`total_ult` (web e GUI) são FIXOS — a última run CONCLUÍDA
  (`last_boss_seconds`/`last_run`), sem atualização ao vivo. O tempo `médio`
  continua sendo cálculo do histórico, não ao vivo.
- Na web, **login e senha também são editáveis inline na tabela de contas**
  (como as células editáveis da GUI): login é um campo de texto direto, senha é
  um campo `type=password`. O **login** gravado via `definir_login` (vazio não
  apaga), e a **senha** via `definir_senha` — o valor real NUNCA sai do Python
  (DPAPI); a web só mostra um indicador visual (`tem_senha`) quando existe.
  Edição detalhada continua no modal "Editar".
- Na web, o **modal Editar tem as MESMAS 4 abas da GUI** (Personagem, Teclas,
  APP, Bewitcher Cave), com alternância que mostra **só os campos da aba ativa**
  (Teclas agrupadas em Ataque/Cura/Consumíveis/Deslocamento; BC em
  Boss/Rota/Reset/Venda; o APP tem prévia da sequência). O log ganhou um botão
  **Copiar** (cop. as linhas filtradas para o clipboard) e a linha de
  startup "BlazesBot (web) pronto..." foi removida.
- A **UI web é Tailwind v4 + Vite de alta densidade** (refatoração UI/UX). O
  `body` NUNCA rola: cada `<section class="secao">` é uma coluna flex com
  cabeçalho `shrink-0` fixo e conteúdo `flex-1 min-h-0 overflow-y-auto
  scroll-thin`. O **modal Editar** tem `max-h-[85vh]` rígido com cabeçalho,
  abas e rodapé fixos (`shrink-0`) e só o meio (`.painel-aba`) rola. Paleta
  zinc (surface 900 / panel 800 / deep 950), bordas `border-white/10`, hover
  `hover:bg-white/5`, accent âmbar, tabela com `thead` sticky. Aos mexer no
  visual, siga essa densidade (fontes 12-13px, paddings contidos) em vez de
  espaçamentos grandes.
- **A edição de UI acontece na pasta `web/`, mas o Python só enxerga as
  mudanças depois que o Vite processa o build.** Sempre que editar `web/*`
  (HTML/CSS/JS), rode `npm run build` na raiz para regenerar o `dist/` que o
  pywebview abre. Scripts: `npm run dev` (dev server) e `npm run build`.
  Tema escuro/claro em `web/style.css` (`@theme` + override
  `[data-tema="claro"]`); o JS ainda lê os tokens `--accent`,
  `--accent-soft`, `--text-faint`, `--err` inline.
- Rodar a web: `INICIAR-WEB.bat` → `python -m blazesbot.web_app` (exige o
  `dist/index.html` já gerado por `npm run build`).
  Compilação rápida dos módulos Python:
  `python -m py_compile blazesbot/**/*.py`.


---

## 18/08/2026 — a interface congela e o bot continua rodando

Sintoma: depois de muito tempo de execução a janela para de responder, mas as
rotinas de background seguem farmando.

### A CAUSA: o canal de log reenviava o histórico inteiro, 3,3x por segundo

`Api.puxar_log` comparava um cursor **absoluto** com o tamanho de uma janela:

    corte = desde_i if 0 <= desde_i <= len(self._historico) else 0

`_total` só cresce (é o número da última linha de sempre). `_historico` é uma
`deque` com `maxlen=MAX_LINHAS_GUARDADAS`: passado o teto ela descarta pela
frente e o índice 0 dela deixa de ser a linha 0 da execução.

Enquanto o total era menor que o teto os dois coincidiam e funcionava. **Na linha
`MAX_LINHAS_GUARDADAS + 1` quebra para sempre:** `desde_i` continua subindo,
`len(_historico)` fica preso no teto, a condição passa a ser sempre falsa e
`corte` vira 0 — o histórico INTEIRO volta em cada poll de 300 ms,
indefinidamente.

**Por que mata a janela e não o bot:** todo retorno de método `js_api` do
pywebview é embutido num literal JS e executado por `evaluate_js`, que chama
`webview.Invoke(...)`. São ~2 MB de script na **thread de UI do WebView2**, 3,3
vezes por segundo. As threads do bot não passam por esse canal.

E o backoff do frontend nunca ligava: com linhas voltando sempre, ele concluía
que havia novidade sempre.

A tradução que faltava: `descartadas = _total - len(_historico)`, e
`corte = max(0, min(desde_i - descartadas, len(_historico)))`. O `max` cobre o
frontend atrasado (aquelas linhas não existem mais) e o `min` cobre o poll
ocioso.

*Havia um comentário no lugar descrevendo uma correção anterior do MESMO trecho
(o `<` que virou `<=`). O defeito da saturação passou por baixo dela.*

### O acelerador: `logger.setLevel(logging.DEBUG)` incondicional

`run()` forçava DEBUG duas linhas depois de `setup_logging` ter definido INFO em
prod. A rotina relê posição a cada 0,12 s por conta; com 4-5 contas o volume sobe
~10x e o teto era atingido em **minutos** em vez de horas — antecipando o
congelamento para quase o começo da execução. Agora é
`DEBUG if logmodo.eh_dev() else INFO`, paridade com a GUI.

### O defeito irmão, no frontend

`renderizadoAte` é índice absoluto em `logCache`, que sofria `shift()` por linha:

1. cada `shift()` deslocava os índices e o render **pulava linhas em silêncio**;
2. saturado em 4000, `logCache.length` ficava constante e `renderizadoAte`
   igualava esse valor **para sempre** — nenhuma linha nova era desenhada, com o
   contador travado em "4000 linhas exibidas".

E `shift()` é O(n): com o backend reenviando 12 000 linhas por poll eram ~8000
shifts sobre 4000 elementos, 3,3x/s, na thread principal.

Agora a poda é **um `splice`** e remove da caixa exatamente os filhos que saem do
cache — só os que estavam desenhados, que com filtro ativo não são todos
(`podarCache`). Mais: `logCursor = r.total || logCursor` tratava um `total`
legítimo de 0 como ausência de valor; virou teste de tipo, com reconstrução
quando o total RETROCEDE.

### Vazamentos de longa duração encontrados no mesmo passe

- **`vision._pools` (GDI).** `release_pool` só era chamado por
  `BotContext.close()`, mas o LOGIN captura a tela antes de existir um
  `BotContext`. Login que falha vaza **um DC + um bitmap de ~3 MB por relogin**.
  Em 24 h isso aproxima o processo do limite de 10 000 handles GDI — e quando ele
  estoura, nenhuma alocação GDI funciona mais, **incluindo a pintura da janela
  PyQt6**. Passou para `AccountSupervisor._release()`, que é chamado nos cinco
  caminhos de morte de janela, e **antes** de `self.hwnd = None` (perdido o hwnd,
  não há chave). Corrige de quebra um defeito de correção: o Windows recicla
  valores de hwnd, e um pool obsoleto era devolvido para a janela nova que
  herdou o número, fazendo BitBlt do DC de uma janela destruída.
- **`ui_service._BUSCAS_SEM_LEITURA`.** Mesma forma — dict por hwnd, nunca
  podado — e o mesmo problema de hwnd reciclado: a lição "o leitor de arredores
  não responde nesta janela" era herdada por uma janela nova. `esquecer_janela()`
  é chamada no mesmo ponto.
- **`quedas.imagem_embutida`.** Relia e reencodava em base64 a miniatura de CADA
  queda retida a CADA abertura da aba (~20 KB de texto por registro, dezenas de
  registros, atravessando `evaluate_js` na thread de UI). O JPEG é imutável, então
  agora é cacheado por nome, com teto.
- **`core/diario.py`.** Os três diários usavam `logging.FileHandler` cru, os
  únicos logs do projeto **sem teto**. `diario.localizacao()` grava em toda falha
  de leitura do nome, com o rastro dos ponteiros — o `logs/localizacao.log` deste
  repositório já está em **4,8 MB**. Passaram para `ArquivoDeLogLimitado`, com
  teto generoso (20 000 linhas) porque o diário existe para ser consultado dias
  depois.
- **`mouse_shield.uninstall_hook`.** Zerava `_hook_handle` e `_hook_installed`
  mas deixava `_hook_thread` preenchido, e `_ensure_hook_installed` começa com
  `if ... or cls._hook_thread is not None: return`. Depois de um uninstall, todo
  shield novo (um por relogin) seguia SEM HOOK em silêncio — e a medição deste
  arquivo diz que sem shield o bot cai de 20/20 para 1/20.

### Fica em aberto, de propósito

**`inputs.py` usa `SendMessageW` sem timeout.** Um cliente que para de bombear
mensagens — o cenário exato do "Connection interrupted" que este bot detecta —
bloqueia a thread daquela conta para sempre; o `finally` do shield não roda e o
`watchdog.check()` (que dispararia o relogin) nunca é alcançado. `
SendMessageTimeoutW` com `SMTO_ABORTIFHUNG` preserva a semântica síncrona
exigida pelo `MODO_DE_CLIQUE`.

**Não foi mexido** porque o caminho do clique é a parte mais medida deste projeto
(ver `docs/decisoes/cliques-e-resolucao.md` e `stuttering-mouse.md`) e alterá-lo
sem medição é o erro que já custou dois dias de DLL. E, decisivo: **este defeito
não é o sintoma relatado** — ele travaria uma thread do BOT, e o relato é que o
bot continua rodando e só a interface morre.

Travado por `tests/test_puxar_log_nao_reenvia_tudo.py` (7 testes), incluindo o
caso "passado o teto" e o de custo limitado por poll.


## 25/08/2026 — a tela de Log era uma parede de texto

**Relato do usuário, textual:** "pensa no usuario leigo vendo isso e ficando
completamente confuso, eu como programador as vzs me perco". O print anexado
mostrava 35 linhas com o MESMO peso visual.

### O que estava errado (medido no print, não suposto)

`.caixa-log` era `font-size: 11px`, `line-height: 1.4`, `padding: 8px` **na
caixa e zero na linha**, e `.linha-log` era um `display: flex` com a linha
inteira como UM nó de texto. Consequências, em ordem de gravidade:

1. **A linha longa que quebrava virava duas linhas.** No print, a continuação
   `pelo painel de arredores (tentativa 1 de 3).` aparece alinhada com o começo
   do texto — indistinguível de um evento novo. Era o pior dos defeitos: o log
   MENTIA sobre quantas coisas tinham acontecido.
2. **A hora tinha o mesmo peso da mensagem.** Em toda linha o olho batia primeiro
   em `05:18:49`, que é referência, não conteúdo.
3. **Nada separava uma linha da outra.** Sem padding vertical e sem fio, 35
   linhas eram um bloco.

### O conserto

**Três colunas — hora | conta | mensagem — alinhadas entre TODAS as linhas por
`subgrid`.** É `subgrid` porque cada `.linha-log` é seu próprio contêiner de
grade: sem ele cada linha mediria as colunas sozinha e nada alinharia. Fica sob
`@supports (grid-template-columns: subgrid)` com o **flex como base** — fora do
suporte se perde só o alinhamento, não a hierarquia nem o ar.

Isso exigiu **uma** mudança em `web/main.js`: `renderLog` separa a hora
(`RE_HORA_DA_LINHA`) e a mensagem em spans próprios, porque CSS não tem onde
pegar num nó de texto solto. É **só apresentação** — o texto copiado (clique
direito e botão "Copiar") continua saindo de `l.linha` inteira, com a hora no
lugar; `#btn-copiar-log` lê `logCache`, nunca o DOM. Linha que não casar com a
hora entra inteira na coluna da mensagem: nunca se perde texto.

**FIO ENTRE LINHAS, NUNCA FAIXA ALTERNADA (zebra).** Esta é a decisão que não
pode ser revertida por gosto. `podarCache` remove a **primeira** linha da caixa;
com `:nth-child(even)` a paridade de TODAS as linhas inverteria a cada poda, e
saturado em `LOG_CACHE_MAX = 4000` isso é uma piscada de tela inteira a cada
poll de 300 ms. `.linha-log + .linha-log { border-top }` não tem paridade.

**Hierarquia por três tokens novos**, sem cor nova na paleta: `--log-msg` (o
conteúdo, o mais claro), `--log-hora` (referência, apagada), `--log-fio`. A
etiqueta da conta deriva o próprio fundo da cor inline de `corConta` com
`color-mix(in srgb, currentColor 15%, transparent)` — uma cor por conta sem
tabela de fundos para manter.

`--log-hora` no **tema claro** é `#77655f` e não `#9a8884`: o segundo dava
**2,97:1** sobre `#f5efed`, abaixo de AA para texto de 11px. `#77655f` dá 4,8:1.

### Aferido no navegador, não no olho

Preview por `test-web.ps1` (Chrome + CDP + `agent-browser`) com o bridge do
pywebview substituído por um stub que serve as linhas do próprio print.
Conferido: as 35 linhas do print, o modo filtrado por uma conta (a coluna da
conta **colapsa**, sem sobra), o tema claro, o realce sob o cursor, e **4 000
linhas com a poda ativa** — DOM e contador continuaram alinhados (4000/4000),
o "seguir o fim" continuou ligado e as colunas não desalinharam.

**O que NÃO foi mexido, de propósito:** `corConta` continua gerando cores
próximas para contas diferentes (no preview, duas contas saíram em tons de verde
parecidos). É defeito real, mas é do gerador de cor, não do log.


## 25/08/2026 (2) — o log não acompanhava, e a rolagem era seca

Relato do usuário: *"garanta que sempre que abrir o bot e entrar no log, ele já
esteja rolando junto com os novos logs, pois tem vez que eu manualmente tenho
que arrastar a barra pra baixo"*. Mais dois pedidos de acabamento: rolagem mais
suave e um efeito na chegada da linha.

### O defeito: A CAIXA DO LOG NASCE SEM LAYOUT, e ninguém a avisava

`.secao` é `display: none` e o app abre em **Contas** — a caixa do log só passa
a existir quando o usuário clica na aba. Enquanto escondida, `scrollHeight` e
`clientHeight` são **0**, então o `caixa.scrollTop = caixa.scrollHeight` que
`renderLog` fazia em todo poll **não fazia nada**.

**Medido**, entrando na aba Log com 35 linhas já no cache:
`{top: 0, alt: 691, total: 1072, sobrou: 381}` — 381 px de log abaixo da dobra,
com a caixa parada no topo. Depois do conserto, o mesmo cenário: `sobrou: 0`.

`logSeguirFim` continuava `true`, então o próximo `renderLog` colaria no fim — só
que `renderLog` só roda quando **chega linha nova**, e o poll faz backoff até
5 s. É por isso que o defeito é intermitente ("tem vez"): quando o bot está
falando muito, a linha seguinte chega antes de o usuário perceber. `navegar()`
agora chama `colarNoFimDoLog()` ao abrir a aba, com `requestAnimationFrame`
porque neste instante a seção acabou de trocar de `display` e a altura ainda não
foi medida.

**Hipótese REFUTADA no caminho:** eu suspeitei que reexibir a seção disparasse um
`scroll` com a caixa no topo, e que fosse esse evento a desligar o seguir-fim.
Instrumentei o `scroll` da caixa: **zero eventos**. A causa é a de cima, não
essa.

### A tolerância de 8 px era uma armadilha

`noFim` usava `scrollHeight - 8`. Arrastar a barra e parar 20 px antes do fim é
trivial — e desligava o acompanhamento em silêncio, sem nada na tela dizendo por
quê. Agora `MARGEM_DO_FIM_DO_LOG = 26`, uma LINHA inteira: quem parou a menos de
uma linha do fim quis dizer "fim".

### Rolagem: PERSEGUIÇÃO, não transição

`scrollTo({behavior: "smooth"})` mira um alvo **fixo**, decidido no instante da
chamada. No log ao vivo o fim **se move** (chegam mais linhas enquanto a tela
desliza), então ele terminaria num ponto que já não é o fim, ficando
permanentemente atrás. O laço em `requestAnimationFrame` recalcula o alvo a cada
quadro e vence `APROXIMACAO_POR_QUADRO_DO_LOG = 0.28` do que falta.

Medido interceptando as escritas de `scrollTop`: `+14.8, +10.8, +8.0, +5.7,
+3.6, +2.9, +2.2, +1.4, +0.7, +1, +1, +1` — 12 quadros, ≈200 ms por lote.

Acima de `SALTO_SUAVE_MAXIMO_DO_LOG = 340` px vai **instantâneo**, e a
perseguição desiste no meio se o salto crescer além disso. Em rajada (250 linhas
por poll) alcançar vale mais que enfeitar: medido `atrasoMax: 4 px` e 29 de 30
amostras em zero, com DOM e contador alinhados em 4000/4000.

**A TRAVA `rolagemDaTela` É OBRIGATÓRIA.** A rolagem animada dispara `scroll` em
cada quadro, todos em posições intermediárias; sem a trava a própria animação
desligaria o seguir-fim no meio do movimento que ela mesma pediu. E **gesto do
usuário manda**: `wheel`, `pointerdown`, `keydown` e `touchstart` cancelam a
perseguição na hora — sem isso a tela brigaria com o arrasto dele. Esses eventos
chegam ANTES do `scroll` que causam, então a trava já caiu quando `aoRolarLog`
vai decidir.

Contrato conferido nos dois sentidos: rolou para cima → parou de acompanhar
(`sobrou` foi de 1079 para 1505); voltou ao fim → retomou (20 de 24 amostras em
zero, atraso máximo de 38 px, capturado no meio da animação).

### `prefers-reduced-motion` FOI DELIBERADAMENTE TIRADO DO CAMINHO

Era o portão natural dos dois efeitos, e reprovou com medição: o Windows desta
máquina está com animação de janela desligada
(`HKCU\Control Panel\Desktop\WindowMetrics\MinAnimate = 0`) e o Chromium
traduz isso em `prefers-reduced-motion: reduce`. As **duas** instâncias de Chrome
abertas para conferir a tela reportaram `reduce` — o WebView2 do bot faria o
mesmo, e os efeitos que o usuário PEDIU não apareceriam nenhuma vez.

Virou o interruptor `EFEITOS_DO_LOG = true` no `main.js`, com
`podeAnimarOLog()` como único ponto de decisão. `false` devolve o respeito
automático à preferência do sistema. O CSS **não** tem portão próprio de
`prefers-reduced-motion`, de propósito: um lugar só decide, e é o `main.js`.

### Efeito de chegada, e os dois tetos que ele precisa

`.log-chegando`: a linha desce 4 px para o lugar e o realce âmbar desvanece.
Só entra em lote **pequeno** (`LOTE_MAXIMO_ANIMADO_NO_LOG = 12`) e
**nunca em reconstrução**.

**Duração: 700 ms, e é PREFERÊNCIA DECLARADA, não medição.** Começou em 420 ms e
o usuário pediu mais lenta ("a mensagem entrar um pouco mais lentamente"). É a
única constante desta área sem número medido atrás — se alguém for mexer, mexa
porque ele pediu de novo, não porque achou.

**As três propriedades não terminam juntas, e é isso que dá entrada em vez de
piscada:** a opacidade fecha em 45%, o deslocamento assenta em 70% e o realce é o
último a sumir. Terminando no mesmo ponto, a linha "aparecia". A curva é
`cubic-bezier(0.16, 0.84, 0.3, 1)` -- `ease-out` longo: quase toda a distância é
vencida no começo e o fim assenta devagar; curva simétrica nesta duração
pareceria lentidão, não suavidade.

Conferido pelo navegador (`getAnimations()`): duração real de 700 ms, curva
computada como pedida, e **4,6 linhas animando ao mesmo tempo em média (máximo
6)** com dois lotes por segundo -- a sobreposição esperada de 2 a 3 lotes, sem
peso. Sem os dois limites o efeito trabalharia contra si:
trocar o filtro repinta até 4000 linhas de uma vez e o primeiro carregamento traz
o histórico inteiro. Conferido na rajada: **0 das últimas 250 linhas** ganhou a
classe.

### Armadilha de medição que custou tempo — anote

O `test-web.ps1` abre o Chrome com `-WindowStyle Hidden`, e **uma janela sem
apresentação não produz quadros**: `requestAnimationFrame` nunca dispara. Isso
fez `scrollTo({behavior: "smooth"})` parecer que "pula direto para o alvo em
qualquer motor" (18 quadros no mesmo valor) — conclusão falsa, artefato da
janela oculta. Para medir animação, suba o Chrome **visível**; e prefira
interceptar `scrollTop` com `Object.defineProperty` a amostrar em `rAF`, porque
a ordem dos callbacks de `rAF` entre o amostrador e a própria animação esconde os
valores intermediários.

---

## A caixa do log nasce SEM LAYOUT (detalhe que saiu do CLAUDE.md em 25/08/2026)

`.secao` é `display: none` enquanto a tela não está selecionada. Escondida, o
`scrollHeight` do elemento é **0** — e o `scrollTop = scrollHeight` que o
`renderLog` faz não tem efeito nenhum.

Por isso `navegar("log")` chama `colarNoFimDoLog()`: é a única oportunidade em
que a caixa já tem layout e ainda não foi mostrada ao usuário.

**A rolagem PERSEGUE o fim**, e não salta uma vez: `requestAnimationFrame` com o
alvo recalculado a cada quadro, porque linhas novas chegam durante a própria
animação. Acima do teto ela vira instantânea.

Duas peças são obrigatórias e parecem opcionais:

* a trava `rolagemDaTela`, que impede duas perseguições simultâneas;
* o cancelamento por gesto — sem ele, o usuário que rola para ler uma linha
  antiga é arrastado de volta para o fim, e o log fica inutilizável.

**`prefers-reduced-motion` NÃO gateia os efeitos.** Quem decide é o interruptor
`EFEITOS_DO_LOG`. A preferência do sistema é sobre animação decorativa; aqui a
rolagem é funcional (é o que mostra a linha nova), e desligá-la por preferência
de movimento esconderia informação.


## 26/08/2026 — a roda do mouse em TODO campo numérico

Pedido do usuário: *"onde tiver esses inputs numericos, faça sempre poder rodar o
scroll com o mouse em cima e ele descer e subir o numero ... analise para o que
serve e qual faria mais sentido"*.

### O que existia

Um ouvinte de `wheel` que só agia dentro de `#corpo-app`, com passo **100 fixo**
para qualquer campo, e três defeitos:

1. **Não avisava quem escuta.** Os rótulos de porcentagem dos sliders são
   escritos por ouvintes de `input`; mexer no `.value` calado deixava o slider
   numa posição e o rótulo com o número velho.
2. **Só cuidava de não passar de zero.** O slot de venda é 1..24
   (`config.validar` recusa fora disso, e a GUI já usava `setRange(1, 24)`) e a
   web deixava rolar até onde quisesse — erro só na hora de salvar.
3. **Não arredondava.** Em ponto flutuante 0,5 + 0,1 dá 0.6000000000000001, e
   esse texto ia direto para dentro do campo.

E discordava de si mesmo: a roda andava 100 nos delays da APP enquanto as
**setinhas do mesmo campo** andavam 50 — dois passos no mesmo campo, dependendo
de como você mexia nele.

### O desenho: o passo é o `step` do campo, e o campo mora no HTML

Não há tabela de passos no `main.js`. Quem descreve o campo é o campo, e o
`step` serve às setinhas e à roda ao mesmo tempo. Passos escolhidos por
significado:

| campo | passo | por quê |
|---|---|---|
| `in-delay-lancamento` | 0,5 s | ajuste fino em segundos; faixa 0..30 como o combo da GUI |
| `ed-pet-feed-min` | 5 min | a grade real é ~50 min; de 1 em 1 seriam 50 toques |
| `ed-app-limpar` | 1 volta | default 10, e o 0 tem significado próprio (nunca) |
| `ed-app-shuffle` | 5 voltas | default 30; mesmo raciocínio do pet |
| `ed-ataque-delay` | 0,1 s | ajuste fino de combate; faixa 0,1..5 como `sp_delay` da GUI |
| `ed-runs-venda` | 1 run | contagem pequena |
| `ed-slot-venda` | 1 slot | slot é discreto, e **max = 24** |
| delays da APP (`ed-app-espera-tab` e as 20 linhas) | 100 ms | granularidade útil de delay de macro, e é o número que o usuário já conhecia |
| `ed-hp`, `ed-bhp`, `ed-emergencia`, `ed-aoe-mana` | 5 % | de 1 em 1 são 99 toques de ponta a ponta |

`Shift` multiplica o passo por 10 — convenção de UI, e evita configurar um
segundo passo só para atravessar a faixa.

### A ARMADILHA DO SLIDER, que eu mesmo criei e desfiz

Em `type="range"` o `step` manda na **GRADE de valores válidos**, não só no
tamanho do toque. Pus `step="5"` nos limiares de vida e com `min="1"` a grade
virou 1, 6, 11 ... 96: **90% ficou inalcançável**, inclusive arrastando o slider
— e 90% é justamente o mínimo de vida para começar uma run. O teto medido virou
96 em vez de 99.

Por isso o slider ficou com `step="1"` (pousa em qualquer inteiro, como sempre) e
o passo grosso da roda foi para um atributo próprio, **`data-passo-roda`**. É a
única exceção à regra "o passo é o `step`", e existe por essa medição.

### Aferido campo por campo, com o gesto real

Disparando `WheelEvent` de verdade em cada um dos **12 campos estáticos** e nos
**21 da aba APP** (o TAB mais as 20 linhas da sequência, criadas em tempo de
execução — é por isso que o ouvinte é delegado no `document`):

- passo de um toque e de `Shift` corretos em todos;
- **piso e teto respeitados em todos** (`10/10`, `30/30`, `240/240`, `99/99`,
  `999/999`, `5/5`, `100/100`, `24/24`, `10000/10000`);
- 90% de novo alcançável nos três sliders de vida;
- o rótulo do slider acompanha (`6%` → `95%`), provando o `input` disparado;
- e a roda **só é consumida em cima de campo numérico**: caixa do log, campo de
  texto, `select` e corpo da página continuam rolando (medido com o retorno de
  `dispatchEvent`).

### Paridade com a GUI PyQt6

Todo `QSpinBox` já responde à roda por conta do Qt, então a funcionalidade não
faltava lá — faltava o passo bater. Alinhados em `account_dialog.py`:
`sp_app_espera_tab` e as esperas das linhas de 50 → **100**;
`sp_app_shuffle` ganhou `setSingleStep(5)`.

`launch_delay` é `QComboBox` na GUI e campo numérico na web — divergência que
**já existia** e não foi tocada; só a faixa da web passou a casar com as opções
do combo. (`max_clients` foi APOSENTADO no mesmo dia — ver a seção seguinte.)

### DIVERGÊNCIA ENCONTRADA E NÃO CONSERTADA — a prévia da sequência da APP

**`#lbl-previa-app` não existe no `index.html`.** `atualizarPreviaApp` está
escrita, o ouvinte de `input` em `#corpo-app` está registrado, e a função sai no
`if (!el) return` — então a prévia "Sequência: ... volta completa em X s", que a
GUI PyQt6 mostra (`_atualizar_previa_app`), **nunca apareceu na web**.

Não foi consertada aqui porque é uma tela nova, fora do pedido. Fica anotada
como dívida de paridade. Quando o elemento entrar, o ouvinte já o alimenta — a
roda do mouse inclusive.


## 26/08/2026 (2) — piso 1, tempo em ms, e um campo aposentado

Pedido do usuário: *"nenhum dos campos deve aceitar 0, e sempre a partir de 1, ou
ser for delay é a partir de 100 ... tudo que for delay ou intervalo de tempo
padroniza em MS e minimo 100 ms"*, restrito aos campos numéricos mexidos na
sessão anterior.

### A TELA FALA MILISSEGUNDOS, O ARQUIVO CONTINUA EM SEGUNDOS

Dois campos estavam em segundos: `attack_delay` (0,5 s) e `launch_delay` (8 s).
Os rótulos e as faixas viraram ms — 500 ms e 8000 ms — mas **o `config.json` não
mudou**: os dois seguem `float` de segundos, porque é o que `combat.py` e o
supervisor leem, e o laço de ataque é a parte mais medida do projeto. Trocar a
unidade no armazenamento obrigaria a migrar todo `config.json` existente para
ganhar nada.

A conversão é de APRESENTAÇÃO e mora em dois pares de funções, um por linguagem:
`config.segundos_para_ms`/`ms_para_segundos` (Python, usado pela GUI e pela
validação) e as homônimas em `web/main.js`. O piso saiu da espera da macro e
virou o piso de qualquer delay: `MINIMO_DE_ESPERA_DO_APP_MS` agora é
`MINIMO_DELAY_MS`, um número num lugar só.

**Conferida a ida e a volta**, porque se não fecharem, abrir e salvar a tela sem
tocar em nada MUDA a configuração: `0,1 / 0,3 / 0,5 / 5 / 8 / 12 / 30 s` voltam
idênticos, e `0`, `None` e negativo sobem para o piso em vez de virarem zero.
Travado em `test_o_tempo_vai_e_volta_sem_perda`.

### AS DUAS COLISÕES, e o que o usuário decidiu

O `0` não era "vazio" em dois campos — era um modo de operação, e travar em 1
removeria a função. Levantei as duas antes de mexer:

**`max_clients` (0 = todas as contas ativas) foi APOSENTADO.** Decisão do
usuário: *"não deve existir, vai ser sempre todas as contas, pois sempre sera em
base as contas ativas"*. Quem manda passou a ser só `enabled_accounts()`.

O campo **saiu de vez, e não virou interruptor** — a convenção do projeto vale
para caminho de código, e isto era um TETO: teto órfão num `config.json` antigo
continuaria cortando contas ativas em silêncio, **sem nenhuma tela para
desfazer**. Removido nas cinco camadas: `web/index.html`, `web/main.js`,
`gui/main_window.py`, `web_app.py` (as duas pontas da ponte), `config.py` (o
campo e a lista de chaves de `from_dict`, então arquivo velho com a chave é
ignorado) e `supervisor.py` (o `ativas[:cap]` e a linha de log). Travado em
`test_max_clients_foi_APOSENTADO_de_ponta_a_ponta`, que reprova qualquer menção
fora de comentário.

**`apagar_lixo_a_cada` (0 = nunca apagar) FICA com mínimo 0.** Decisão do
usuário: *"pode deixar como 0 o minimo, vai sera a unica com isso"*. É a única
exceção da interface e está declarada nos três lugares: comentário no HTML, a
constante `EXCECAO_QUE_ACEITA_ZERO` no teste, e aqui. O motivo de não forçar 1:
com mínimo 1 o deletador passaria a rodar a cada volta, e **apagar item não tem
desfazer**.

### O pet é a única exceção de UNIDADE, e ganhou faixa fechada

Continua em MINUTOS (em ms pediria 7 dígitos para um valor que se ajusta de 5 em
5 minutos, e não é delay de mecânica, é grade de longo prazo). Faixa nova pedida
pelo usuário: **40 a 60 minutos**. Fora dela a conta medida deixa de fechar —
abaixo de 40 o item é desperdiçado (o pet ainda não gastou os 5 de felicidade) e
acima de 60 ele passa fome entre refeições.

A faixa é **grampeada na leitura** (`pet_feed_na_faixa`), não recusada na
validação: o combo antigo da GUI oferecia 10, 20 e 30 minutos, e recusar faria o
bot rejeitar a configuração inteira de quem já usava esses valores. Arquivo velho
sobe corrigido — mesmo contrato do piso de 100 ms. A ponte reaplica, porque "a
tela impõe" não é garantia, é boa vontade. O combo da GUI passou a oferecer a
mesma faixa e o mesmo passo (40..60, de 5 em 5).

### Aferido no navegador

Rolando cada um dos **33 campos** (12 estáticos + 21 da aba APP) todo para baixo:
cada um parou no seu piso — `100` nos de tempo, `40` no pet, `1` nos de contagem
e porcentagem — e **o único que chegou a 0 foi `ed-app-limpar`**, a exceção
declarada. `in-max-clientes` não existe mais na tela.

Suíte: 1149 + 37 testes novos, `ruff` limpo. Os dois índices gerados
(`INTERRUPTORES.md` e o catálogo de tempos) foram regenerados — o
`test_indice_de_constantes` e o `test_indice_de_tempos` pegaram a mudança, que é
exatamente o trabalho deles.
