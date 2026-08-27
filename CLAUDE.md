# BlazesBot — instruções de trabalho

Bot de **boss-rush da Bewitcher Cave** para o MMORPG **Talisman Online**
(servidor oficial, cliente ver.6400). Python 3.12, Windows, roda como
administrador. Auto-login e relogin automáticos, várias contas em paralelo.

## Governança deste arquivo (regra permanente — 27/08/2026)

**O `CLAUDE.md` é o NÚCLEO DE OPERAÇÕES, não a documentação do projeto.** Ele é
lido inteiro no começo de cada sessão, então tudo que está aqui compete por
atenção com tudo mais que está aqui.

### O que PODE entrar

1. **Configuração de skill** — qual skill existe, quando é obrigatória, o que ela
   substitui.
2. **Diretriz arquitetural global** — o que vale para o sistema INTEIRO:
   fronteira entre ecossistemas, reuso e promoção, as duas interfaces.
3. **Regra técnica crítica que exige atenção CONSTANTE** — a que a IA tem de
   carregar em toda tarefa, não só quando toca uma área (padrões obrigatórios de
   Python, de HTML/CSS/JS, de estrutura, e as regras que atravessam tudo).

### O que é PROIBIDO entrar

**Documentação de projeto, guia de uso, roteiro de teste e ata de decisão.**
Também: regra de ÁREA (combate, navegação, venda, APP, interface…), número
medido, histórico e relato de defeito. Nada disso se perde — cada coisa tem
destino:

| conteúdo | destino |
|---|---|
| regra de área ("o que não pode ser violado") | `docs/INVARIANTES.md` |
| especificação técnica e medição | `docs/REGRAS.md` |
| **porquê medido**, log, alternativa reprovada | `docs/decisoes/<area>.md` |
| índice das decisões | `docs/decisoes/README.md` |
| contrato de skill (detalhado) | `docs/SKILLS.md` |
| toda espera do bot *(gerado)* | `docs/TEMPOS.md` |
| constantes e interruptores *(gerado)* | `docs/INTERRUPTORES.md` |
| manual do usuário | `COMECE-AQUI.md` (config, teclas, venda, login), `NAVEGACAO.md` (Navigator, montaria, minimapa) |
| restrições e decisões de projeto com o porquê | `CONTINUAR-NO-CLAUDE-CODE.md` |

### Como aplicar

- **Na dúvida, sai.** Se a regra só importa quando alguém toca uma área
  específica, ela não é deste arquivo — é do `docs/INVARIANTES.md`, com o link
  daqui.
- **Escreva SÓ o necessário** para o sistema continuar funcionando e melhorando.
  Há folga até o teto de 35k **de propósito** — ela existe para diretriz global
  nova (padrão de Python, de HTML/CSS/JS, de estrutura) caber sem disputar
  espaço, **não** para acomodar o que a tabela acima manda para `docs/`.
- **Estourou o teto? NÃO suba o teto.** Mova conteúdo para `docs/`; comprimir
  texto só deixa o arquivo pior do mesmo tamanho.
- **Regra sem destino é regra perdida.** Quem tira algo daqui move VERBATIM para
  o arquivo de destino no mesmo passo — nunca apaga.

### Antes de mexer em qualquer área

1. `graphify query "<pergunta>"` — o grafo orienta primeiro (ver abaixo).
2. `docs/INVARIANTES.md`, a seção da área — o que não pode ser violado.
3. `docs/decisoes/<area>.md` — o porquê medido. **Quase tudo ali já reprovou com
   medição**; número novo precisa de medição, nenhum é arredondamento.

## Ao começar uma sessão de trabalho: invoque o `task-observer`

**AUTO-INVOCADA.** Antes de qualquer tarefa de múltiplos passos que use
ferramentas e produza entregável, invoque a skill `task-observer` (conversa
curta e pergunta avulsa não contam). Ela propõe skills novas em
`skill-observations/`, e não substitui os destinos já definidos: convenção e
decisão vão para aqui, arquitetura para o graphify.

## Regra de ouro: o graphify manda

O projeto tem um **grafo de conhecimento** em `graphify-out/`. Antes de responder
qualquer pergunta sobre o código ou fazer qualquer alteração, consulte o grafo
primeiro: `graphify query "<pergunta>"`, `graphify path "<A>" "<B>"`,
`graphify explain "<conceito>"`, `graphify-out/GRAPH_REPORT.md`. Só grep/leitura
bruta depois que o grafo orientou, ou para debugar linhas específicas.

## Documentação de biblioteca: Context7 (`/find-docs`)

Antes de responder sobre **biblioteca externa** (PyQt6, pywebview, Tailwind v4,
Vite, pymem, OpenCV, pytest, ruff), use a skill `find-docs` (Context7) em vez de
responder de memória — essas libs mudam. Não substitui o graphify.

## Skills instaladas no projeto (`.claude/skills/`)

- **`find-docs`** (Context7) — documentação atual de biblioteca externa.
- **`task-observer`** — meta-skill auto-invocada: observa a sessão e propõe
  skills/melhorias. Custo aceito: 24 KB de SKILL.md por sessão de trabalho.

## Regras de manutenção (obrigatórias)

1. **Toda alteração no código ⇒ atualizar o graphify:** `graphify update .`
   (reextrai AST-only e regenera `graph.json` + `GRAPH_REPORT.md`).
2. **Toda alteração que mude conhecimento/convenção ⇒ atualizar o documento do
   destino certo** (ver a tabela na Governança) **no mesmo passo**. Regra de área
   vai para `docs/INVARIANTES.md`, especificação para `docs/REGRAS.md`, porquê
   medido para `docs/decisoes/`. Nenhum deles pode descrever um comportamento
   que o código já não tem.
3. **Tamanho:** teto de **35k caracteres**, travado por
   `tests/test_claude_md_tamanho.py`. Mas **quem organiza este arquivo é a
   Governança, não o teto** — o teto é a rede de segurança para o caso de ela
   ser ignorada. O mesmo teste reprova **cabeçalho de ÁREA** aqui dentro, e é
   essa trava que dá a forma: 20k só de diretriz arquitetural é saudável, 15k
   com regra de combate é doente. Encostou no teto ⇒ **mova conteúdo, não
   comprima texto** — com a Governança valendo, ficar cheio quase sempre
   significa que entrou algo cujo destino é `docs/`.

## Ecossistemas: UM sistema, vários mundos (regra permanente)

O BlazesBot é **um sistema** com vários **ecossistemas**. Estrutura de pastas É a
regra:

```
blazesbot/core/      capacidades que NÃO sabem que ecossistema existe
blazesbot/bot/       o SISTEMA — serve todos os ecossistemas
blazesbot/bot/bc/    ecossistema Bewitcher Cave (farm de boss-rush)
blazesbot/bot/app/   ecossistema APP (macro de teclado) + deletador
```

- **UM ECOSSISTEMA NUNCA IMPORTA DO OUTRO** (`bc/` ↔ `app/`). O comum desce para
  `bot/` ou `core/`. Mexer num não pode quebrar o outro (garantido pelo grafo de
  dependências, não pela memória). Travado por `tests/test_ecossistemas.py`
  (lê o AST: reprova `bc/ → app/`, `app/ → bc/`, `core/ → bot/`).
- **`bot/` do meio existe porque o supervisor decide QUAL ecossistema roda.**
  Login, watchdog e `BotContext` valem para qualquer conta, então moram aqui.
- **Configuração global é compartilhada de propósito** — principalmente as
  TECLAS (descrevem o JOGO, não o ecossistema). A única coisa que os dois usam
  igual.
- **`core/` nunca importa de `bot/`.** Inverter cria ciclo e tira a reusabilidade
  do core. É por isso que `core/quedas.py` recebe o motivo da queda como string.
- **A aba APP NÃO tem filtro de tecla repetida** — lá a mesma tecla se repete por
  desenho.

### REUSO E PROMOÇÃO — diretiva permanente do usuário (26/08/2026)

**A base é VIVA: refatorar para manter a organização é parte do trabalho, não
uma tarefa à parte.**

1. **REUSO PRIMÁRIO. Duplicação é inaceitável.** Antes de escrever função
   nova, procure o que já resolve aquilo. Duas funções iguais em lugares
   diferentes são duas chances de só uma ser corrigida.
2. **PROMOÇÃO É OBRIGAÇÃO, NÃO OPÇÃO.** Lógica nasce específica e evolui: viu
   que uma função de um ecossistema tem utilidade geral, **abstraia as
   dependências locais e mova para o `core/`** — no mesmo passo, não "depois".
3. **RIGOR DE DIRETÓRIO.** Local fica na pasta do ecossistema; compartilhado
   fica em `core/`. A pasta É a declaração de escopo.
4. **DOCUMENTAÇÃO DE TRANSIÇÃO, no mesmo passo.** Quem promove escreve no
   código que aquilo é **dependência cruzada**: quem usa, de onde veio, o que
   NÃO subiu e por quê. Mexer ali mexe em todos — e isso tem que estar escrito.
5. **GATILHO DE SEGURANÇA.** Reuso não pode custar estabilidade: valide o
   efeito colateral rodando a **suíte inteira**, nunca só a área mexida.
6. **TARGET tem RIGOR MÁXIMO** — use o que já funciona no BC. Hoje o comum vive
   em `core/target_hybrid.py`: **`TargetHybrid`** (a leitura: id, nome, HP,
   nível, posição) e **`MorteDoAlvo`** (o veredito `hp <= 0` e a trava por
   identidade). NÃO subiu, e por quê: a reserva pela **TELA** fica no BC (o APP
   não captura) e a reserva pela **FLAG DE COMBATE** fica no APP.

**Candidatos de promoção já identificados** (ainda em duplicata): confirmar o
TAB pela troca do id (`app/executor._esperar_o_alvo_trocar` × o TAB do
`bc/combat`), e a espera fatiada que responde ao Parar
(`app/executor._dormir` × `BotContext.tick`).

- **COMPARTILHADO vs. ESPECÍFICO — o critério é UMA pergunta:** *isso é sobre o
  JOGO ou sobre o que este ecossistema faz?* Sobre o jogo desce para `core/`
  (`Memory.vida_pct()`, `in_battle()`, `alvo_atual()`, as teclas); o resto fica
  no ecossistema (*quando* curar, *até* quanto). Duas funções só quando a
  PERGUNTA é diferente. Exemplos em `docs/decisoes/memoria-primeiro.md`.

## LOGIN E RELOGIN: o ecossistema BASE (regra permanente)

Login e relogin **não são etapa do BC nem do APP** — são a fundação. Detalhe e
medição: `docs/REGRAS.md` (seção "Login e relogin") e
`docs/decisoes/login-e-relogin.md`.

**Todo ecossistema — presente e futuro — é obrigado a:**
1. **Perceber a queda ENQUANTO roda** (`executor.rodar()` leva horas).
2. **Usar a MESMA definição de queda**, `watchdog.avaliar_saude(pid, hwnd,
   janela_existe, templates)` — ela recebe PECAS, não `BotContext`, para o APP
   chamá-la sem depender do farm.
3. **Ter o mesmo desfecho:** fecha janela → relogin → a conta **volta sozinha**
   para o modo em que estava.
4. **Gravar no Histórico de Quedas** (`ctx.ultima_queda`).


O **detalhe de área** (telas modais, o único motivo para matar uma janela, o
backoff, a senha errada) está em `docs/INVARIANTES.md`, seção "Login e relogin".

## Duas interfaces convivem (regra permanente)

O bot tem **DUAS interfaces** com o MESMO backend:

- **PyQt6** (original) — `blazesbot/gui/*`, lançada por `3-INICIAR.bat`.
- **Web (pywebview)** — frontend `web/` (Vite + Tailwind v4) compilado para
  `dist/`; ponte `blazesbot/web_app.py`, lançada por `INICIAR-WEB.bat`. Abre
  `dist/index.html` via WebView2 (Windows 11, sem navegador instalado). Janela
  frameless, `resizable=False`, 1200×800; arrasto 100% JS via
  `DRAG_REGION_SELECTOR = ".titlebar"`.

Ambas leem/gravam `data/config.json` e usam o mesmo core. **REGRA PERMANENTE —
nunca quebrar:** mexer em interface ⇒ mexer **nas duas** para manter as MESMAS
funcionalidades. Backend compartilhado no core; só o "corpo" da tela se duplica.
`pywebview` é dependência (`requirements.txt`).

## Regras que atravessam tudo (atenção CONSTANTE)

Estas NÃO são regra de área: valem em toda tarefa, em qualquer arquivo.
É por isso que elas ficam aqui e o resto foi para `docs/INVARIANTES.md`.

- **MEMÓRIA PRIMEIRO (regra permanente).** Tudo que der para responder lendo a
  memória é lido da memória; imagem, template e tecla-e-espera são **reserva**.
  Não é gosto: a tela tem uma coleção de modos de falha que um inteiro da struct
  não tem, e **todos erram calados**. Memória não paga captura e responde com a
  janela minimizada. O porquê, o inventário do que ainda decide por imagem e a
  receita para migrar: **`docs/decisoes/memoria-primeiro.md`**.
- **MAS SÓ DEPOIS DE MEDIDO**, com ferramenta que só loga e sabe REPROVAR, e
  comparando com a fonte antiga no MESMO instante. A fonte antiga vira reserva —
  **não se apaga**.
- **ENDEREÇO HERDADO QUE "NÃO RESPONDE": TESTE O `+0x60` ANTES DE DESCARTAR.**
  É o rebase medido do banco de estáticos na virada 6139 → 6400 (`TARGET_ID`
  `0x0115CB20` → `0x0115CB80`). Ignorar isso manteve a câmera escrevendo em
  lugar nenhum por anos.
- **NENHUMA MENSAGEM SAI PARA UMA JANELA QUE NÃO É O JOGO** (regra permanente,
  `CONFERIR_A_JANELA_ANTES_DE_ENVIAR = True`). Toda tecla e todo clique conferem
  ANTES de sair: `hwnd` não-zero e não-`HWND_BROADCAST`, janela viva, **mesmo
  PID** de quando o `Input` nasceu, e esse PID é um `client.exe`. Motivo medido:
  o Windows **RECICLA HWND**, o handle vira o Bloco de Notas e a senha era
  digitada lá. **"Não sei" NÃO bloqueia** — bot mudo é pior que o defeito.
  Detalhe em `docs/decisoes/sistema.md`.
- **Nunca mover o cursor FÍSICO.** Cliques são `SendMessageW` síncrono com
  coordenada no `lParam`. Interruptor `MODO_DE_CLIQUE` em `inputs.py`. **Sem DLL,
  sem hook de `GetCursorPos`.**
- **`write_position` é PROIBIDO** — o bot anda de verdade.
- **Onde havia espera cega, agora se PERGUNTA** (confira o efeito, saia no
  instante). Teto vira aviso, não gasto fixo.
- **A cada clique, conferir o esperado; se não, repetir** — quem decide é a
  IMAGEM (leituras de UI desta build não respondem).
- **Interruptor, não comentário nem apagar** — caminho fora de uso vira
  `X = False` no topo do módulo, com teste forçando-o ligado.
- **Número novo precisa de MEDIÇÃO** (tolerância, limiar, teto, cadência).
- **TEMPO NOVO ENTRA NO `docs/TEMPOS.md`** — constante OU literal (`tick(0.5)`).
  **GERADO** (`python -m blazesbot.core.indice_de_tempos`), travado por
  `tests/test_indice_de_tempos.py`. Traz **atual × ORIGINAL**
  (`docs/tempos-originais.json`, o ponto de restauração) e a natureza: **TETO**,
  **PASSO** ou **FIXO** (espera cega — é onde há tempo a ganhar).
- **Um número lido por dois lados mora num lugar só** (ex.: `mapa_bc.PRECISAO_*`).
- **RESOLUÇÃO: a UI do jogo NÃO escala** — todo ponto entra por
  `coords._from_base(x, y, âncora)`. 1024×768 é a base medida, não a única.
  Travado por `tests/test_coords.py`.
- **Ao investigar QUALQUER problema, ler os logs primeiro**
  (`logs/dev/blazes-dev.jsonl`).

## Skills e Agent skills

As definições completas de skill (pywebview + Web Frontend, GUI e Interatividade,
Issue tracker, Domain docs) moram em **`docs/SKILLS.md`** — mantidas lá para não
inchar este arquivo. Leia `docs/SKILLS.md` quando for mexer em interface ou
precisar do contrato de skill.
