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

## A PyQt6 foi CONGELADA (27/08/2026)

> *"vamos manter a versão PyQt6 parada no tempo, pode até documentar isso, sem
> deletar por agora, mas acredito que vou abandonar ela de vez, pois a versão
> web está ficando muito superior e mais bonita."* — decisão do usuário.

**O que "congelada" significa, exatamente:** ela continua funcionando, continua
lançada pelo `3-INICIAR.bat`, continua lendo e gravando o mesmo
`data/config.json` e continua sendo mantida quando algo que ela JÁ mostra muda.
O que ela não recebe é **função nova**.

**Por que isso precisou virar decisão escrita:** a regra permanente do projeto é
que mexer em interface é mexer NAS DUAS, e ela não é só uma frase no
`CLAUDE.md` — é travada por teste. `tests/test_app_config_campo_por_campo.py`
descobre os campos do `AppConfig` por introspecção e cobra cada um em quatro
lugares, dois deles no `gui/account_dialog.py`. Um campo que só existe na web
reprova a suíte por construção.

**Como a exceção foi feita:** uma lista fechada e nomeada,
`CAMPOS_SO_DA_WEB`, com uma âncora (`test_a_excecao_da_gui_congelada_nao_cresce_sozinha`)
que reprova se ela crescer. Isso mantém a regra valendo para todos os outros
campos — o que morreria em silêncio seria a alternativa: afrouxar o teste para
"a GUI não conta mais".

**O que NÃO se perde com o congelamento:** os campos do time são gravados no
`config.json` por `asdict` e lidos por `_app_from_dict`, que a GUI também usa.
Abrir uma conta pela PyQt6 e salvar **não apaga** o time — ela apenas não o
mostra nem o edita. Quem for descongelar precisa de um widget novo em
`_aba_app`, leitura em `_carregar` e escrita em `_aplicar`; os três lugares
estão nomeados no teste.


## 28/08/2026 — reordenar contas arrastando, grupos do usuário, e o ícone

Pedido: reordenação por arrastar-e-soltar na tabela de contas, agrupamento
visual, persistência da ordem, e ícone novo. Precedido de análise arquitetural
nos três eixos, com as decisões abaixo tomadas pelo usuário ANTES de existir
código.

### O que a análise mudou no pedido

Três premissas do pedido não se sustentaram na leitura:

1. **Não faltava `sort_order`.** A ordem JÁ é persistida — é a ordem do array
   `accounts` no `config.json`. Faltava a UI poder mudá-la. Um campo de ordem
   criaria uma SEGUNDA fonte de verdade sobre a mesma coisa, e a pergunta "se o
   campo discordar do array, quem manda?" não tem resposta boa.
2. **Não faltava gravação segura.** `BotConfig.save()` já escreve em `.tmp` e
   troca com `os.replace`, sob `_LOCK_ARQUIVO`.
3. **`team_id` NÃO PODE EXISTIR.** `docs/decisoes/time-do-app.md` registra que
   time simétrico foi RECUSADO, e `INVARIANTES.md` grava "quem monta o time é o
   líder". Um `team_id` por conta é o time simétrico por outro nome, e reabre o
   nó de A liderar B enquanto B lidera A.

### D1 — A IDENTIDADE DA CONTA NA INTERFACE É UM `uid`, NÃO O ÍNDICE

O `id` que a web usava era o índice do array (`web_app.contas()`), e
`_conta()` documentava a premissa: *"o índice é estável enquanto o editor está
aberto (modal bloqueia a tabela)"*. **Arrastar viola essa premissa por
construção.**

Seis operações de escrita eram endereçadas por índice: `definir_login`,
`definir_senha`, `definir_posicao`, `definir_servidor`, `remover_conta`,
`salvar_personagem`. A falha concreta: a UI reordena, a ordem no disco é outra, e
o `definir_senha` seguinte grava **a senha na conta errada** — o que é login
quebrado E senha certa perdida, sem desfazer.

Escolhido o `uid` (e não "índice com reload obrigatório") porque o usuário pediu
*"a forma mais estável"*: `uid` acerta a conta mesmo com a GUI e a web abertas ao
mesmo tempo, cenário em que o reload não protege. De brinde, apaga um defeito que
já existia: `!contaIdSelecionado` tratava a PRIMEIRA conta (índice `0`) como
"nada selecionado", então o botão Remover não ligava para ela.

O `uid` é gerado na criação, **imutável**, e invisível em toda interface — mesma
categoria de `last_hwnd`/`last_pid`. Conta de `config.json` antigo recebe um na
leitura.

### D2 + D3 — O GRUPO É ORGANIZACIONAL E NÃO REPRESENTA NADA DO BOT

Decisão do usuário: *"ele nao precisa representar nada, pode ser um agrupamento a
escolha do usuario, para ele poder organizar e deixar mais facil visualmente"*.

Isto é o que resolve a tensão entre D2 (*"só reordena"*) e o agrupamento: D2
existia para impedir que soltar uma conta dentro de um grupo editasse
`time_logins` pelas costas — com teto de 4 seguidores, bloqueio de `bc_farm` e
recusa por já liderar outro time, um drop podia falhar por regra. **Como o grupo
não é time, arrastar entre grupos não tem efeito colateral nenhum**: é rótulo
visual, e mover é seguro.

- **A ordem é ordem; o time é `time_logins`; o grupo é rótulo.** Três coisas
  ortogonais. Nenhuma deriva da outra.
- `time_logins` continua indexado por LOGIN, portanto imune a reordenação.
- O grupo é **um campo de texto livre por conta** (`Account.grupo`). Os grupos
  existentes são os valores distintos, na ordem em que aparecem no array — então
  **a ordem dos grupos também sai do array**, e continua havendo uma fonte de
  verdade só.
- Conta sem grupo (`""`) não ganha cabeçalho: ausência de rótulo é o rótulo.

### O arraste é POINTER EVENTS, não HTML5 Drag & Drop

Três razões, em ordem de peso:

1. **A linha é quase toda campo de entrada** — login editável, senha, dois
   `<select>`, três caixas e o botão Editar. Arrastar pela linha inteira brigaria
   com selecionar texto no login. Exige ALÇA dedicada, e alça é trivial com
   Pointer Events.
2. **`<tr>` é hostil ao DnD nativo**: a imagem de arraste de uma linha de tabela
   sai deformada e `<table>` não aceita placeholder arbitrário entre linhas.
3. **Zero dependência nova.** Trazer SortableJS contraria a diretriz de preferir
   nativo, e o WebView2 abre por `file://`, onde CDN não carrega.

O DOM **só é reordenado no drop** (um `insertBefore`); durante o arraste o
feedback é `transform`, que não causa reflow de layout.

### Por que NÃO tem debounce, contrariando o pedido

O pedido pedia debounce ou gravação assíncrona para o caso de "arrastar e fechar
o app no mesmo segundo". **Debounce é exatamente o mecanismo que perde a última
alteração quando a janela fecha.** O que o justificaria é gravação caríssima ou
muito frequente, e medido, não é nenhum dos dois: `data/config.json` tem **18 946
bytes com 7 contas** (~2,7 KB por conta; 50 contas dariam ~135 KB), a gravação é
atômica, e `_aplicar()` já grava o arquivo inteiro **a cada caixa clicada** hoje.

Então: **gravação síncrona no drop**, e se ela falhar a tabela **volta à ordem
anterior** e avisa — a tela nunca mostra uma ordem que o disco não tem.

### Performance: virtualização foi RECUSADA

`renderContas` recria a tabela inteira (`innerHTML = ""`), mas só em ação
explícita — **nunca no poll**; o poll de 1500 ms toca as linhas cirurgicamente
(`tr[data-login]`), com o comentário de que re-renderizar apagaria uma edição
inline em andamento. Há precedente: arraste em curso não é destruído pelo poll.

Com 50 contas, o custo do arraste é `transform` em até 50 nós por quadro (sem
reflow) e um `insertBefore` no drop. O gargalo plausível é a RECRIAÇÃO (50
`<select>` de servidor), que é pré-existente e não vem do arraste. Virtualizar
quebraria o arraste para fora da viewport e a busca do navegador para resolver um
problema que 7 contas não têm.

### D4 — ícone: monograma "B" em chama (opção C)

`web/favicon.ico` era **referenciado em dois lugares e não existia** — o
quadradinho que o usuário via no titlebar era o placeholder de imagem quebrada do
WebView2. Não havia `setWindowIcon` em lugar nenhum: a janela e a barra de
tarefas também estavam sem ícone.

São **duas peças, e não uma**: SVG inline no titlebar (zero requisição, imune ao
CSP e ao `file://`, herda `currentColor`) e um `.ico` multi-resolução de verdade
para a janela, a GUI e a taskbar. FontAwesome e Material Icons foram recusados:
webfont externa não carrega em `file://`, e via npm entra um pacote inteiro para
um glifo.


## O `dist/` é o que roda — e ele mentiu por uma sessão inteira (04/09/2026)

A tecla nova de reviver foi acrescentada em `web/index.html`, mapeada em
`web/main.js`, transportada pela ponte nos dois sentidos e carregada/gravada na
GUI PyQt6. Os testes de paridade — que existem justamente para o campo não
"aparecer e não gravar" — passaram todos.

E a aba **Teclas na tela continuava sem o campo.**

Motivo: `pywebview` abre **`dist/index.html`**, o bundle do Vite. `web/` é
fonte; `dist/` é o que existe para o usuário. Sem `npm run build`, o HTML novo
fica no disco sem nunca chegar à tela.

### Por que nenhum teste pegou

Os quatro testes de paridade leem `web/index.html`, `web/main.js`,
`blazesbot/web_app.py` e `blazesbot/gui/account_dialog.py`. Nenhum lia o
artefato. E `dist/` está no `.gitignore`, então a tentação é dizer que teste
nenhum pode olhar para ele.

Pode, com uma condição: **pular quando não existe.** Num clone novo ou na CI o
teste é irrelevante; na máquina de quem desenvolve, ele é a única coisa que
separa "mexi no HTML" de "o usuário viu". `test_o_dist_COMPILADO_tem_o_campo`
não cobra que o build seja feito — cobra que o build **que existe** esteja em dia.


## 28/08/2026 (2) — a tela de contas: coluna Função, estados e alvos

Pedido: *"ele deve bater o olho e identificar instantaneamente qual conta está
rodando, em qual ecossistema (APP, BC, HH) e quais são as divisões lógicas"*.

### O diagnóstico mudou o problema

Lendo o `config.json` de verdade antes de desenhar: **quatro das sete contas
estão ativas SEM ecossistema nenhum marcado** — só logam e relogam. A tela dava a
elas o mesmo peso visual das que trabalham. E `creubo` está no grupo `BC` mas
roda **HH**, com duas contas no grupo `APPs` sem APP marcado: o usuário estava
usando o GRUPO como substituto do ecossistema, porque o ecossistema não era
escaneável.

Ou seja, a pergunta que a tela não respondia não era "onde está a linha" — era
**"o que esta conta faz?"**.

**Segundo achado: o dado de "está rodando" já chegava no navegador e era jogado
fora.** `estado().contas` só traz conta EM EXECUÇÃO, com `runs`, `uptime`,
`relogins` e cronômetro; a tabela usava isso para espelhar DUAS caixas e
descartava o resto.

### As três colunas de caixa viraram UMA coluna Função

BC, HH e APP eram três checkboxes idênticos de 14px, e o que distinguia um do
outro estava no `<th>` — **fora da linha**: para ler um ✓ o olho subia ao
cabeçalho e voltava, uma vez por linha.

Cada selo é **pictograma + sigla**, e a sigla não é enfeite: **BC e HH são as
duas cavernas**, dois pictogramas de caverna não se distinguem a 16px, e o erro
que isso causa é caro (põe a conta na cave errada). Os símbolos saem do que cada
ecossistema tem de próprio: **caveira** para BC (o boss é o `Blaze Skull
Marshal`), **fada** para HH (a Fada é a mecânica que só a HH tem), **teclado**
para APP (o APP é uma sequência de teclas). Espadas e alvo foram recusados:
descrevem COMBATE, e os três combatem.

**O `<input type="checkbox">` NATIVO continua ali**, escondido sob o `<label>`,
com o estado desenhado por `:has(.selo-caixa:checked)`. Trocar por `<button>`
custaria reimplementar `role="switch"`, `aria-checked`, Tab e barra de espaço — e
é aí que esse tipo de reforma quebra acessibilidade sem ninguém notar.

### O alvo de clique era metade do mínimo

`.chk` media **14×14 px** — metade dos 24×24 que a WCAG 2.5.8 pede — e havia
**quatro por linha**, encostados. O `<label>` passou a ser o alvo, com 28×28: área
de clique **4× maior sem crescer a linha**. Medido depois: o alvo fica dentro da
célula (205→233 contra 195,8→245,3) e o clique acerta nas duas bordas.

### Quatro estados, quatro canais — e por que a zebra foi recusada

Os estados COEXISTEM, então nenhum pode usar o recurso visual de outro:

| estado | canal |
|---|---|
| selecionada (para remover) | barra na borda esquerda (`linha-ativa`, já existia) |
| inativa | opacidade 45% |
| **no ar agora** | ponto verde + contagem de runs |
| ativa e parada | nada, que é o normal |

`.linha-ativa` tem nome infeliz e **não** quer dizer "conta ativa": é a linha
SELECIONADA. Por isso o fundo não podia carregar "ativa" — já estava ocupado, e é
a mesma razão de a **faixa alternada (zebra) ter sido recusada**: ela consumiria
o fundo inteiro para decoração.

**Cards individuais também foram recusados**, por quatro motivos: quebram o
alinhamento vertical que permite comparar servidor e posição entre contas;
o arraste depende de linhas de altura previsível; o cabeçalho de grupo é um
`<tr colspan>` e deixaria de existir; e com padding de card 7 contas já não
caberiam numa tela.

**Sem cronômetro por linha**, de propósito: texto que muda a cada segundo em N
linhas é ruído e re-render à toa. O cronômetro ao vivo já existe inteiro na aba
Estatísticas de BC.

### Um defeito silencioso corrigido no caminho

`COLUNAS_DA_TABELA_DE_CONTAS` estava em **9** com a tabela em **10** colunas: a
coluna HH entrou depois e a constante não acompanhou, então o `colspan` do
cabeçalho de grupo ficava uma coluna curto. `colspan` errado não dá erro — só
deixa a tabela torta em silêncio. Agora são 8 colunas e um teste trava a
sincronia.

### O que só apareceu MEDINDO na tela

1. **A coluna Função comeu a largura**: "Center" virou "Cente", o servidor virou
   "Light in the Darkn" e o botão Editar quebrou em duas linhas. A grade de
   larguras passou a ser explícita; esticam só Login e Servidor.
2. **O indicador empilhou abaixo do login** e a linha foi de 40 para **67px** —
   e só nas contas em execução, deixando a tabela com duas alturas. A célula do
   login virou flex; as alturas ficaram uniformes em 49-50px.
3. **O tema claro reprovou**: as siglas dos selos LIGADOS usavam cor clara fixa
   sobre preenchimento claro e sumiam. O APP escapou por acaso, porque já usava
   `--accent-fg`, que tem as duas variantes. Viraram tokens.
4. **O estado DESLIGADO reprovou AA no tema claro**: `--color-faint` dá 4,78:1 no
   escuro mas **3,28:1** sobre o painel branco, com sigla de 9,5px. Virou
   `--selo-off-texto`, `#7a6863` no claro (5,27:1). Medição final: **mínimo 4,78
   no escuro e 5,27 no claro**, todos acima de AA.

### Achados da revisão do Codex

- **`top: 27px` no cabeçalho de grupo era número mágico** e o `<th>` media 27,5 —
  meio pixel de fresta, que qualquer mudança de fonte ou zoom abriria. Virou
  `--altura-cabecalho-tabela`, que o `<th>` impõe e o sticky consome.
- **O pulso do ponto verde animava `box-shadow`**, que repinta a cada quadro: com
  dezenas de contas no ar seriam dezenas de repaints contínuos. Passou a animar
  só `opacity` e `transform`, que o compositor resolve sozinho.
- **A margem negativa do alvo** foi apontada como risco e **medida**: não vaza da
  célula nem invade a linha vizinha. Fica como está, com a medição registrada.

### Densidade

50px por linha (era ~30). Com 20 contas dá ~1000px de rolagem, e é por isso que o
**cabeçalho de grupo é `sticky`**: rolar sem saber em que grupo se está era o
custo real do scroll, não a altura.


### 28/08/2026 (3) — a ordem das colunas, e RUN como coluna própria

Pedido: *"o ideal é ser ativo|login|senha|run|servidor|posiçao|função|editar"*, e
*"as runs so aparece para aqueles que tiverem rodando cave, o APP nao deve
aparecer a quantidade de runs pois nao faz sentido"*.

**As duas informações que eu tinha juntado foram separadas**, e é a parte que
importa deste ajuste:

- **O PONTO VERDE** diz "está no ar" e vale para **qualquer** ecossistema, APP
  incluído. Fica ao lado do login.
- **A COLUNA RUN** diz quantas runs a conta fechou, e **só se preenche para
  cave**. O modo APP é macro de teclado: não existe "run" ali, e um número seria
  inventar uma medida que o ecossistema não tem.

Juntas num rótulo só, como estavam, a conta de APP ficaria **sem indicador
nenhum** — ela roda, mas não tem run. Conferido na tela com o cenário real:
`creubo` (HH, no ar) mostra `12`; `blazestpas` (APP, no ar) mostra o ponto e a
coluna Run **vazia**, embora o resumo do supervisor tenha mandado 7 runs para
ela. Quem filtra é a tela.

Conta parada mostra **vazio, não zero**: zero diria "rodou e não fechou nenhuma",
que é outra coisa.

**O filtro usa `farm`/`farm_hh` do RESUMO**, não do disco — é a mesma fonte que
alimenta as duas caixas de cave, então as três contam a mesma história.

### O slot do ponto tem largura fixa, e a classe é PRÓPRIA

Movido para ANTES do login: depois dele ficava solto no meio da célula, porque o
campo é `flex: 1` e empurrava o ponto para a borda direita, longe do nome.

E ele usa `.conta-ao-vivo.parada`, **não** a classe `.escondida` global: aquela é
`display: none !important`, e o `!important` vencia — o slot sumia e o nome da
conta pulava 15px ao entrar no ar, fazendo a coluna dançar a cada poll. Medido:
os logins começavam em **325px ou 340px** conforme a conta estivesse rodando;
depois do conserto, **340px para todas**.


### 06/09/2026 — o seguidor de time, selos compactos e o ponto vermelho

Três pedidos: mostrar que a conta de APP ativa **por causa do líder** está
trabalhando (e não "só login"); **encolher os selos**, porque virão mais funções;
e o ponto ficar **vermelho quando a conta caiu e está em relogin**.

#### "só login" estava MENTINDO sobre a conta seguidora

A conta que roda a macro de outra tem `AppConfig.enabled` **desligado** — quem
liga o APP é o LÍDER, e o time dela própria é ignorado (`INVARIANTES.md`, "Time
do APP"). Resultado: três caixas vazias, e a tabela a chamava de "só login". Ela
está trabalhando, só que a mando de outra.

Agora `contas()` manda `lider_do_time` e a coluna Função mostra **`segue <login>`**
num selo tracejado — tracejado porque o estado **não é dela**: ninguém marcou
nada ali e não há o que desmarcar naquela linha. É informação, não controle.

#### O pictograma saiu

Ele entrou como reforço, mas quem removia a ambiguidade BC×HH sempre foi a
**sigla** — dois pictogramas de caverna não se distinguem a 16px. Tirar o desenho
não custa clareza e devolve espaço: cada selo caiu de **~52px para 26px**, e o
trio de ~170px para **93px**. É o que faz esta coluna aguentar a quarta função
sem espremer o resto da tabela.

#### O ponto verde MENTIA sobre a conexão

Ele era verde por a conta estar na **lista** do resumo — e a conta que caiu
continua nela, por minutos, tentando religar. O ponto dizia "no ar" com o
personagem fora do jogo. Quem responde de verdade é o `hwnd`: é ele que morre
junto com a sessão.

Vermelho além da cor tem **pulso mais rápido** (1s contra 2,4s): daltonismo
vermelho-verde é o mais comum, e o ritmo era o único canal livre.

### Os cinco achados da revisão do Codex

1. **Parar não é cair.** O Parar também mata a janela, e `tentativas_de_login` só
   zera quando o login CONCLUI: sem olhar o `stop_event`, apertar Parar pintava
   "Caiu — reconectando" em toda conta que já tivesse tentado logar.
2. **Falso verde.** `bool(sup.hwnd)` sozinho deixava a tela verde entre a janela
   morrer e o laço perceber — o handle fica em cache. Agora passa por
   `_janela_viva`, que confere com `IsWindow` (syscall local, uma por conta a
   cada 1,5 s) e **tolera falha**: erro ali não pode derrubar o resumo, que
   alimenta a tela inteira.
3. **O(n²).** `lider_do_time_do_app` varre todas as contas e era chamada **uma
   vez por conta**. Virou `lideres_do_time_do_app()`, um índice montado numa
   passada.
4. **CADEIA DE LÍDERES.** Com C liderando A e A liderando B, a consulta direta
   devolvia "A" para B — mas a lista de A é **ignorada** enquanto ela é seguidora
   de C, então B não está em time nenhum e "segue A" seria mentira. Um líder que
   é ele próprio seguidor não lidera ninguém. Conferido:
   `{C→A, A→B}` resolve para `{a: "C"}` apenas.
5. **Acessibilidade.** O estado era dito por COR e por `title`, e nenhum dos dois
   chega a leitor de tela. O ponto ganhou `role="img"` e `aria-label` reescrito
   junto com a cor; sem ponto, `aria-hidden` para não virar ruído.


### 06/09/2026 (2) — o ícone do bot, e por que ele era o do Python

Dois pedidos: tirar o `| Bewitcher Cave` do topo (o bot roda BC, HH **e** APP —
anunciar uma das caves ali está errado desde que a HH existe), e dar ao bot um
ícone de verdade, porque **a barra de tarefas mostrava a cobrinha do Python**.

#### O desenho: a referência do usuário, com o B no miolo

Base é a imagem que ele mandou: chama de silhueta escura com ombros
**recortados** (é o recorte que faz ler "fogo" e não "gota d'água"), contorno
luminoso e miolo aceso.

A tensão: a referência é **rica em detalhe interno** — muitas línguas finas — e
isso não sobrevive a 16px, que é o tamanho da barra de tarefas. Foram desenhadas
e comparadas três leituras nos tamanhos reais (16/24/32/48) e sobre fundo claro
**e** escuro:

| leitura | veredito |
|---|---|
| B pequeno na base, três línguas (fiel à referência) | bonita a 110px, **desaparece a 16px** |
| **B grande em ouro, línguas laterais recuadas** | **lê em todos os tamanhos — escolhida** |
| B vazado num miolo dourado (negativo) | forte a 110px, o vazado **fecha e some** a 16/24px |

É a terceira vez que essa mesma lição aparece nesta tela: **o que sobrevive a
tamanho pequeno é massa e forma simples**, não detalhe.

#### DUAS HIPÓTESES ERRADAS antes da causa real — vale registrar

1. **"O pywebview não suporta `icon=` no Windows."** A docstring do próprio
   `webview.start` diz *"Supported only on GTK/QT"* — mas o backend WinForms
   **lê** `_state['icon']`. Refutada lendo o backend.
2. **"O `.ico` estava em PNG embutido e o `System.Drawing.Icon` não lê."**
   Plausível, e **medida**: montei o mesmo ícone nos dois formatos e pedi ao .NET
   os dois. **Carregou os dois.** Hipótese morta.

**A causa real, medida:** subi uma janela pywebview igual à do bot e perguntei o
ícone dela com `WM_GETICON` — **a janela TEM ícone próprio**, nos dois tamanhos.
O `icon=` sempre funcionou. O que faltava era o **AppUserModelID**: sem ele o
Windows agrupa a janela sob o processo que a criou (`python.exe`) e o botão da
barra de tarefas usa o ícone **dele**, por mais bonito que seja o da janela.

`SetCurrentProcessExplicitAppUserModelID("BlazesOfGamer.BlazesBot")`, chamado no
**começo** do `run()` — antes de qualquer janela existir. O teste de guarda exige
essa ordem, e pegou a primeira versão, em que a chamada estava depois do
`create_window`.

#### O `.ico` continua em DIB clássico

Mesmo com a hipótese refutada, o arquivo ficou em DIB e não em PNG embutido:
`System.Drawing.Icon` é o consumidor mais restrito da cadeia, e não há vantagem
em usar o formato que ele lê pior. Tamanhos 16/20/24/32/40/48/64 — **sem 256**,
porque nada na barra de tarefas passa de 48 e quadros grandes são exatamente onde
o .NET clássico costuma engasgar.

## A janela Editar — o porquê medido (06/09/2026)

Pedido: reduzir o scroll (principalmente na aba Teclas), consertar os tooltips
que não apareciam, polir a nomenclatura, e — no meio do trabalho — tornar as
funções mutuamente exclusivas. O **council** foi consultado antes de escrever
código; **2 dos 4 assentos responderam** (openrouter-1 devolveu "model
unavailable for free", openrouter-3 "rate limit exceeded"), e o codex revisou o
diff depois.

### Os tooltips: NÃO era o binding

A suspeita natural é o ouvinte — e ela estava errada. Os ouvintes de
`mouseover`/`mouseout` sempre estiveram certos e delegados. O balão era criado,
preenchido e ficava com `opacity: 1`: **ele existia, visível, em lugar nenhum.**

A causa é uma mistura de sistemas de coordenada. `getBoundingClientRect()`
devolve posição relativa ao **viewport**; o balão é `position: fixed`, que também
é resolvido no **viewport**. O código somava `window.screenX`/`window.screenY` —
a posição da **JANELA NA TELA** — antes de escrever em `style.left/top`. Numa
janela em (200, 100), o balão de um ícone a 400px do topo do viewport ia para
500px… fora da área visível, porque a janela tem 800px e o resto do offset
somava. Com a janela em (0,0) o defeito **desaparece**, e é por isso que ele
sobreviveu tanto tempo.

O conserto é remover as duas somas. Depois disso o balão precisa de duas coisas
que não tinha:

- **grampo nas quatro bordas** (`const grampo = (v, min, max)`): a janela é
  travada em 1200×800 e campo na borda é caso real, não hipótese;
- **atraso de 80 ms no fechar**: sem ele, atravessar dois ícones vizinhos apaga e
  reacende o balão a cada pixel. E movimento **dentro** do próprio ícone não é
  saída (`!icone.contains(e.relatedTarget)`).

O balão vive no `<body>` de propósito: os painéis do modal rolam
(`overflow-y: auto`), e um balão dentro deles seria **cortado**.

`focusin`/`focusout` entraram junto — só no mouse, a ajuda não existe para quem
navega por Tab.

### A altura: o número mágico e a linha desperdiçada

O painel tinha `max-height: calc(90vh - 160px)`. O 160 é um chute da soma de
cabeçalho + abas + rodapé; **medido, dá ~153px**. Número mágico que mente assim
que qualquer uma das três barras muda de altura — o painel sobra ou vaza, e nada
avisa. Saiu: `.painel-aba` é `flex: 1; min-height: 0` dentro de um flex de altura
fixa, e o flex resolve a altura certa sozinho. (`min-height: 0` não é enfeite:
sem ele o `overflow-y: auto` não funciona dentro de flex.)

Medições a 100% de DPI, painel de 565px, altura NATURAL do conteúdo:

| aba | antes | depois | folga |
|---|---|---|---|
| Personagem | 458 | 452 | 113 |
| Teclas | 560 | 528 | 37 |
| APP | — | cabe | — |
| Bewitcher Cave | 391 | 391 | 174 |
| HH | 587 (rolava 22px) | 487 | 78 |

Três mudanças, em ordem de resultado por unidade de risco:

1. **Coluna mais estreita na grade de teclas** (190px → 118px): 7 colunas em vez
   de 4, e um grupo de 8 teclas cabe em duas linhas em vez de três. Isso exigiu
   embrulhar o rótulo — ele era **nó de texto solto**, e nó de texto não é
   selecionável em CSS: não recebia estilo nenhum, não truncava, não alinhava.
   Com `<span class="rotulo">` ele passa a ser o mesmo rótulo do resto do modal
   (caixa alta, 10.5px), e é isso que permite a coluna estreita.
2. **O "?" ancorado no rótulo** (`.campo:has(> .ajuda)` relativo, `.campo >
   .ajuda` absoluto no canto). Como terceiro filho de um `flex-col` ele caía
   ABAIXO do input: uma linha inteira por campo (20px × 8 campos só na HH) e um
   símbolo solto, longe do rótulo que explica. Ancorado, custa **zero** altura.
   Isso sozinho tirou a HH de 563 para 487.
3. **Gap vertical e margem de parágrafo na HH** (`gap-y-3`, `mb-2`): pagou os
   22px que faltavam, sem tirar informação da tela.

**A folga era o requisito**, não o zero de scroll: o usuário avisou que vai
ACRESCENTAR funções. 78px é o pior caso, e quando estourar o scroll interno já
funciona com cabeçalho e rodapé fixos.

#### O que NÃO se fez, e por quê

- **Crescer o modal** (`h-[92vh]`, `max-h`): compra ~16px e some no primeiro
  campo novo. Trata o sintoma.
- **Fundir os 4 grupos de teclas**: economiza os títulos (~60px) e destrói a
  única divisão semântica de 29 campos idênticos. Caro em legibilidade.
- **Popover API / `anchor-positioning`**: o alvo é WebView2 evergreen e daria,
  mas o defeito era aritmética de coordenada — trocar a tecnologia esconderia a
  causa em vez de consertá-la.
- **Padronizar os 25 rótulos de tecla em caixa alta**: na grade de teclas o
  rótulo divide a linha com o campo, e ali texto normal se lê melhor. Foi por
  isso que o `font: inherit` do `.rotulo` ficou **escopado** a `.grade-teclas`
  em vez de sair: fora dela o vizinho é LOGIN/SENHA, e herdar deixava só o campo
  com ajuda ("Grupo") com outra tipografia.

### Exclusividade: na ESCRITA, não na leitura

O supervisor tinha **precedência implícita** — o laço testava `app.enabled`
primeiro e dava `continue`. Com BC e APP marcados rodava o APP e o BC ficava
"ligado e ignorado", com a tela mostrando dois selos acesos para uma conta que
fazia uma coisa só.

Impor na **leitura** (uma `funcao_ativa()` que resolve e o resto obedece)
manteria o arquivo mentindo e o defeito visual intacto. Impor na **escrita** é
uma função só, `definir_funcao_da_conta`, que liga uma e desliga as outras — e
`funcao_ativa_da_conta` fica como leitura de conveniência, não como árbitro.

Config antigo com duas marcadas **sobe corrigido**, pelo critério da precedência
legada (app > hh > bc): é a que o supervisor já praticava, então o bot continua
fazendo exatamente o que fazia. Normaliza uma vez, na leitura do arquivo, não a
cada ciclo do laço.

Função desconhecida é **recusada** (`ValueError`): erro de digitação na ponte não
pode desligar as três em silêncio.

O controle virou **rádio** com `name` por conta. Caixa comunica semântica falsa —
sugere que a combinação é válida. E clicar no que já está ligado **desliga**:
"nenhuma função" é estado válido, a conta fica só no login e relogin.

Trocar com o bot **rodando** continua permitido. Bloquear seria tirar uma função
que o usuário usa; o que a troca custa (a run em andamento) vai para o log.

#### O que quase passou: o espelho ao vivo

O `marcarNoAr` corrigia BC e HH de forma **independente**. Com rádio, isso
reintroduzia a função antiga **a cada poll de 1,5 s** — a pessoa clicava em HH e
o BC voltava sozinho um segundo depois. Pegou na verificação em tela, não em
teste: o teste de unidade não tem poll.

#### A tentativa que foi REPROVADA PELO USUÁRIO: rótulo ao lado do campo

O primeiro corte na aba Teclas foi pôr rótulo e campo na MESMA linha
(`.grade-teclas .campo` como `flex-row`). Funcionou pelos números — a soma dos
quatro grupos caiu de 469px para 410px, item de 47px para 24px — e depois de
embrulhar o rótulo solto os 29 campos caíram em 4 colunas exatas (286, 504, 722,
940). Duas rodadas de ajuste: com `flex: 1` no rótulo o campo ia para a borda da
coluna e largava o rótulo que nomeia; com largura fixa (6,75rem) o par ficou
junto e nada truncou.

**O usuário reprovou mesmo assim**, e a palavra dele foi *estranheza* — sem
conseguir apontar o quê. O quê era **consistência**: esta era a ÚNICA aba do
modal com o rótulo ao lado. Em todas as outras (e nas outras telas do bot) o
rótulo fica em cima, em caixa alta pequena. O olho aprende um formato de campo e
o aplica nas cinco abas; a aba que foge do formato custa atenção toda vez.

Lição, e ela não é sobre CSS: **59px de altura não pagam um formato só desta
tela.** A altura voltou pela COLUNA (118px em vez de 190px), que é um ajuste
invisível, em vez do FORMATO, que é o que a pessoa vê. A folga ficou em 37px, a
menor do modal e menos que os 80px do desenho reprovado — e é a troca certa.

#### O que a exclusividade quebrou: não havia como DESLIGAR

Reportado pelo usuário logo depois: com BC ligado não dava para voltar a
"nenhuma função". O tratamento existia — clicar no rádio marcado desliga — e
mesmo assim não funcionava.

O rádio é **escondido** (`position: absolute; opacity: 0`, nunca `display: none`,
que o tiraria do foco por Tab) e quem recebe o clique é o `<span class=
"selo-sigla">` que fica **ao lado** dele, dentro do mesmo `<label>`. O handler
procurava `.selo-caixa` a partir do alvo com `closest()` — e `closest` sobe pela
árvore: o rádio é **IRMÃO** do span, nunca ancestral. Nunca achava nada.

O que fecha a armadilha é o rádio marcado **não disparar `change`**: o caminho
normal também não corrigia. Ligar o BC era uma porta sem volta, e nenhum teste
pegou porque o teste de unidade clica no input, não no que a pessoa vê.

O conserto resolve pelo `.selo` (`closest(".selo")` e então
`querySelector(".selo-caixa")`), que é o elemento que de fato recebe o clique.
Verificado em tela: BC ligado → clique no selo → nenhum rádio marcado, o backend
grava `""`, e o poll de 1,5 s não reacende. As dicas das três funções passaram a
dizer a regra — a antiga ainda ensinava "Marcada junto com BC, roda a HH", a
combinação que deixou de existir.

## O tema claro: a barra de título e a cor que fica presa (07/09/2026)

Relato do usuário, olhando a tela: *"a barra de cima na versão dia não muda de
cor, só o minimizar e o fechar que mudam de cor, mas daí ficam na mesma cor da
barra e com isso acabam sumindo (...) e o próprio nome 'BlazesBot' também precisa
alterar de cor, só o ícone que é padrão e não deve alterar."*

Três defeitos independentes no mesmo canto da tela.

### 1. Um token de fundo sem versão clara

`:root[data-tema="claro"]` redefinia `surface`, `panel`, `panel2`, `deep`, as
linhas e os textos — **e não `--color-cab`**, o fundo da barra de título. Ela
ficava no `#150807` do tema escuro. Como os botões dela usam `--color-ink`, que
no claro é escuro, minimizar e fechar viravam texto escuro sobre fundo escuro.
O relato descreve exatamente isso.

`--color-cab: #efe7e5` no claro, um passo mais escuro que `surface` de propósito:
é o que dá ao hover (`--color-panel`, branco) um contraste que se vê.

O teste que trava isso não confere só `cab`: exige versão clara para **todos** os
tokens de fundo. Fundo sem versão clara é uma área da tela no tema errado, e o
defeito é silencioso — nada avisa, só se vê.

### 2. Cor fixa no nome

`text-white` no "BlazesBot". Virou `text-ink`. O **ícone ao lado não muda**, como
o usuário pediu: ele é a identidade, e tem contraste próprio nos dois temas.

### 3. A COR QUE FICA PRESA NO TEMA ANTERIOR — o defeito de verdade

Depois dos dois primeiros consertos, medi de novo pelo caminho do usuário (clique
no botão de tema) e ✕ e — **continuavam em `#f7f5f5`**, agora brancos sobre a
barra clara. O mesmo sintoma, espelhado.

A causa não é o token: `getPropertyValue("--color-ink")` no próprio botão
devolvia `#2b1a18`, o valor certo. Um `<div>` novo no mesmo lugar, com
`color: var(--color-ink)` inline, pintava certo. **No botão existente, nem o
inline funcionava.** O que revelou a causa foi `transition: none` nele: o
computed virava `#2b1a18` no mesmo instante.

**Quando a cor vem de uma custom property que troca no `:root`, o Blink não
reavalia uma propriedade que está na lista de transições:** a transição não
dispara e o valor antigo persiste. Não é um caso de borda — varrendo a tela
depois da troca, **282 elementos** tinham transição que inclui `color` (ou
`transition-all`) e mais de 200 estavam pintados com a cor do tema anterior:
`nav-item`, `bt`, `cel-texto`, `cel-opt`, `alca-arraste`. A "versão dia meio
errada" era isto.

#### O conserto é UM, no ponto da troca

`:root.trocando-tema *` com `transition: none !important`; o handler põe a classe
**antes** de mudar `data-tema` e a tira depois de **dois**
`requestAnimationFrame` — o primeiro ainda é o quadro em que o tema mudou.

Medido depois: **zero** elementos presos, nos dois sentidos, ida e volta.

Tirar `color` de cada regra também consertaria, e foi a primeira versão (só na
titlebar). Foi revertida: seria o mesmo conserto repetido em dezenas de lugares,
e **a próxima regra nova nasceria com o defeito** — ninguém lembra de uma regra
que não existe ainda. De graça, a troca de tema deixou de fazer a onda de
animação que atravessava a tela.

O risco desta solução é a classe ficar grudada no `<html>`: aí toda transição da
interface morre, sem erro nenhum — a tela só fica seca. É o que o último teste
vigia (a classe é de tempo de execução, nunca do markup, e todo `add` tem
`remove`).

### Paridade

A PyQt6 **não tem tema claro** — `blazesbot/gui/theme.py` é uma paleta escura só.
Nada a espelhar aqui.

## "Funcionava e parou": era o pacote, não o código (08/09/2026)

Relato: *"tiveram vários bugs e mudanças visuais (...) várias funcionalidades
visuais que funcionavam parecem ter parado, como o ponto verde piscando, a caixa
do 'parado' onde mostra as runs, entre outras coisas."*

**No código-fonte não havia defeito nenhum nesses dois itens.** Verificado no
artefato empacotado, servido por HTTP e com a ponte real espelhada (constantes,
config e contas vindas do `config.json` de verdade): estado `● Rodando`, resumo
`15 runs · 14 ok · 1 falhas / 1 relogins`, sete linhas na tabela, pontos verde /
vermelho / oculto conforme `conectada` e `relogando`, zero erro de JS.

### A causa: o app abre `dist/`, e nada obriga o `dist/` a existir em dia

O `3-INICIAR-WEB.bat` chama `python -m blazesbot.web_app`, que abre
`dist/index.html`. Ele **não** faz build. O **backend**, ao contrário, é lido do
código-fonte em toda execução.

Medido: `dist/index.html` estava com data de 21:55 enquanto `web/index.html` era
de 22:16 e `web/main.js` de 22:32. **Duas sessões seguidas mexeram em `web/`
(o i18n cobrindo a Web inteira) e nenhuma rodou `npm run build`.** O usuário
rodava, ao mesmo tempo, Python de agora e tela de 40 minutos antes — uma
combinação que não existe em lugar nenhum do repositório: ninguém a testou,
ninguém a revisou, e nenhum teste da suíte a alcançava.

É o pior formato de defeito para caçar: quem procura no código não encontra nada,
porque o código está certo.

#### A prova

Pondo de volta o `dist/index.html` de 21:55 e rodando os testes novos, os dois
primeiros reprovam na hora; com o pacote atual, passam. O diagnóstico não é
inferência — é reprodução.

#### A trava

`tests/test_dist_atualizado.py`, e a comparação é por **conteúdo, não por data**:
`mtime` não sobrevive a um clone e daria reprovação aleatória. O critério são as
chaves de i18n do HTML — cada texto novo da tela cria uma, então o conjunto
cresce a cada alteração e o pacote atrasado sempre tem menos. Dois testes
irmãos cobrem o build interrompido no meio: `vite build` limpa o `outDir` antes
de escrever, então um `index.html` órfão aponta para assets que não estão lá e a
tela sobe **sem CSS e sem JS, sem erro na janela**.

`dist/` é ignorado pelo git, então em clone novo os três se pulam sozinhos.

E a regra subiu para o `CLAUDE.md` (item 1b das Regras de manutenção): alteração
em `web/` exige `npm run build` no mesmo passo, ao lado do `graphify update .`.

### O defeito de verdade que a varredura achou

Varrendo a tela por textos no formato `[chave]` (o placeholder que `t()` devolve
quando a chave não resolve), sobrou **um**: `0 [log_linhas_exibidas]`, no rótulo
do Log.

`init()` chama `renderLog()` **fora** do `.then(obter_constantes)` — o log é
desenhado antes de o dicionário chegar. Isso por si só se corrigiria, e é o que
acontece com a caixa de estado: `pollEstado` repete a cada 1,5 s. Mas `renderLog`
só roda de novo quando **chega log novo**: com o bot parado, o rótulo ficava
preso no placeholder para sempre.

O contador virou função própria (`atualizarContadorDoLog`), chamada também por
`aplicarIdioma` — que já redesenha contas, filtro do log, stats e quedas, e a que
faltava era só esta.

### Uma coisa que NÃO se traduziu, de propósito

`diag_dpapi_indisponivel` não tem `es`, e eu traduzi antes de olhar: dois testes
de `test_i18n.py` usam justamente essa chave como **fixture do fallback** para
espanhol. Revertido — a tradução não tinha sido pedida e o comportamento para
`es` já é o correto (cai para PT-BR).

Fica registrado o cheiro, que é de outra área: usar uma chave real de produção
como fixture significa que ninguém pode traduzi-la sem quebrar a suíte. O teste
deveria montar o próprio dicionário.

## O desligar da função voltou, e o primeiro conserto nunca tinha ficado de pé (08/09/2026)

Relato: *"se ativo alguma função só consigo trocar entre elas, mas não deixar sem
função, era algo que já tínhamos resolvido e voltou."*

Ele está certo em tudo, inclusive no "voltou" — mas a verdade é pior: **o
conserto de 06/09 nunca esteve certo. Ele ganhava uma corrida, e parou de
ganhar.**

### A trilha de eventos, que é a prova

Espionando `mousedown`, `click` e `change` na linha e clicando de verdade no
selo já ligado:

```
mousedown:selo-sigla    <- o handler desliga: cx.checked = false, definir_funcao("")
click:selo-sigla
click:selo-caixa        <- o <label> ativa o rádio
change:bc=true          <- o handler de change RELIGA: definir_funcao("bc")
```

`preventDefault()` no **mousedown** não impede o `<label>` de ativar o controle
no `click` seguinte. Desligar era imediatamente desfeito por um religar.

Por que passou no teste de 06/09: `definirFuncao` chama `carregarContas()` na
volta da ponte, o que **recria a linha inteira**. Quando essa resposta chegava
antes do `click`, o rádio original já não existia e a cadeia morria ali. Era uma
corrida — e o stub de teste, sincrônico e leve, ganhava sempre; a ponte real do
pywebview e um stub com o dicionário de i18n inteiro (73 KB) perdem.

### O conserto

O `mousedown` passa a **só anotar** quem estava ligado (`dataset.jaLigado`) --
no `click` o rádio já pode ter mudado e não daria mais para saber. Quem desliga
é o `click`, com `preventDefault()`: ali a ativação do label ainda é cancelável,
o rádio não volta a marcar e nenhum `change` sai atrás.

Verificado com clique REAL, cinco vezes seguidas: `bc → NENHUMA → hh → NENHUMA →
app → NENHUMA`, e a troca direta continua trocando (`bc → hh → app → bc`, sempre
uma só ligada).

### A lição, que é sobre o TESTE e não sobre o código

O teste antigo verificava que o tratamento **existia** (`mousedown`,
`preventDefault`, `definirFuncao(uid, "")`). Tudo isso continuava lá quando o
defeito voltou — porque o que estava errado era o **evento**, não a existência.

O teste agora exige o `preventDefault` no **click** e **proíbe** `definirFuncao`
dentro do `mousedown`, nomeando a corrida. Guarda que confere presença de código
não protege de defeito de ordem.

### Varredura do resto: nada mais voltou

Como o pedido foi "veja se não aconteceu mais nada nesse sentido", rodei uma
bateria em tela sobre o pacote, no tamanho real da janela (1200×800): ordem das
colunas, contagem de runs só na cave, ponto verde/vermelho/oculto, "segue
blazestpas" em vez de "só login", caixa de estado com as runs, tema claro (barra,
nome e botões), rolagem das cinco abas do Editar, tooltip dentro da janela, roda
do mouse nos numéricos e o mínimo dos campos. **Tudo passou** — o único mínimo
abaixo de 1 são os dois "limpar a bolsa a cada", onde `0` significa "nunca" e é
invariante.

Dois falsos alarmes meus nessa bateria, que valem registro porque custam tempo:
o viewport do Chrome de preview voltou em **1184×649** depois de um reinício, e a
649px de altura *toda* aba rola — a janela real tem 800. E o balão de ajuda é
`#balao-ajuda`, não `.balao-ajuda`: procurei pela classe errada e li "SEM BALÃO"
num balão que estava lá. **Medição de tela precisa conferir o tamanho da janela
antes de acusar layout.**

## A seleção de itens do deletador nasce SÓ NA WEB (18/09/2026)

`AppConfig.desativados` — os itens que cada conta não apaga — entra em
`CAMPOS_SO_DA_WEB`, a lista fechada de campos que a PyQt6 não carrega. É a
primeira adição àquela lista desde 27/08/2026, e ela exige decisão escrita.
Aqui está.

**Por que:**

1. **O usuário está descontinuando a PyQt6** (18/09/2026, com estas palavras:
   *"vai ser alterado apenas no web isso, a versão PyQt6 eu estou
   descontinuando"*). A interface antiga está congelada desde 27/08.
2. **Não é um campo, é uma JANELA.** A seleção são 208 miniaturas com busca,
   filtro e ação em massa. Na PyQt6 isso seria a primeira imagem da interface
   inteira: **não existe um único `QPixmap` em `blazesbot/gui/`**, e não existe
   um único diálogo aberto de dentro do editor — o único padrão é
   `MainWindow` → `AccountDialog.exec()`.
3. **O campo não se perde.** Como os outros da lista, ele é gravado por
   `asdict` e lido por `_app_from_dict`: a PyQt6 não o mostra e não o edita,
   mas também não o apaga. Quem abrir o editor antigo e salvar não perde a
   seleção feita na web.

**O que a exceção NÃO afrouxa:** os dois testes da ponte continuam valendo. O
campo tem de ser lido do payload em `salvar_personagem` e enviado para a tela
em `conta_editor`, senão `test_app_config_campo_por_campo` reprova.

## O rótulo que aparece não pode mover a tabela (22/09/2026)

Pedido: *"mesmo que algo seja adicionado na tela como o 'segue xxx' não deve
mudar a localização do resto (...) cada elemento sempre no seu devido lugar
(...) e lembrando que funções podem ter mais futuramente."*

A coluna Função era `width: 1%` — o truque de "encolha até o conteúdo". Numa
tabela `table-layout: auto` isso significa que a **linha mais larga decide a
largura da coluna**, e o resto da tabela se reorganiza atrás dela. Como o rótulo
de estado só existe em algumas linhas ("segue \<líder\>") e o texto varia com o
login, bastava uma conta seguidora entrar para tudo se mexer.

**Medido no navegador**, trocando só o texto de um selo por um login longo: a
célula Função foi de **205 → 322px** e a coluna Login caiu de **181 → 64px**.

### Por que `width` no `<td>` não bastou

Primeira tentativa: largura fixa na coluna. Não resolveu, e o motivo é do
modelo de tabela: em `table-layout: auto` o `width` do `<td>` é uma **sugestão**
— quem manda é a largura intrínseca do conteúdo, e com `white-space: nowrap` ela
é o texto inteiro. Medido: 208 → 322 mesmo com o `width` declarado.

`table-layout: fixed` resolveria de um golpe, mas redistribui TODAS as colunas
(Login e Servidor deixariam de esticar) — muito risco para o que o pedido exige.

### O que resolveu: um slot que existe sempre

Duas condições, e **nenhuma sozinha basta**:

1. **O slot está em toda linha, mesmo vazio** (`<span class="selo-estado">`).
   Só a largura fixa não bastaria: a coluna ainda mudaria conforme quantas
   linhas tivessem rótulo — 3px de diferença, medidos.
2. **O slot tem largura fixa e trunca** (`width: 96px` + `ellipsis`). Só o slot
   sempre presente não bastaria: o texto dele voltaria a mandar na coluna.

Com as duas, as 9 colunas ficam nas mesmas posições em três cenários: com
rótulo, sem nenhum rótulo, e com um login absurdamente longo. O nome completo
continua no `title`.

### As próximas funções

A largura da coluna é `calc(var(--funcoes-na-coluna) * 31px + 112px)`. O que
cresce com uma função nova são os **selos**, que são iguais em toda linha e
portanto não desalinham nada; o **rótulo** é quem cede espaço, truncando. Função
nova = trocar um número, num lugar só.

### Uma coisa que NÃO mudou, de propósito

O texto "só login" continua vindo de `content:` no CSS, e portanto não se
traduz. Tentei trazê-lo para o JS com uma chave nova e `t()` devolveu
`[selo_so_login]` **mesmo com a chave chegando no payload de `obter_constantes`**
— verificado instrumentando o stub. É um defeito do i18n que merece investigação
própria; empurrá-lo junto desta alteração misturaria dois assuntos, então a
chave não usada foi removida e o texto ficou onde estava. Fica registrado.
