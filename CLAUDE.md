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

## Segunda opinião: `claude-council` (diretriz permanente — 06/09/2026, gatilho reforçado 07/09/2026)

Peça uma segunda opinião ao council **sempre que a dúvida for real, sem se
policiar por custo** — o roster default é zero-custo (ver `docs/SKILLS.md`).
**"Dúvida real" não é para sentir, é para reconhecer em DOIS momentos
concretos, que não podem passar batido:** (1) o instante em que uma
investigação — sua ou de um agente — termina e vira decisão de arquitetura
com 2+ caminhos plausíveis, **antes** de escrever o código, não depois; (2)
debugging que já falhou 2+ vezes sem bater. Terminou de investigar e o
próximo passo é decidir "como implementar" — isso já é o gatilho, mesmo que
nenhuma dúvida explícita tenha sido sentida. A resposta é **insumo para
análise, nunca veredito**: avalie criticamente os pontos levantados, compare
com abordagens alternativas e teste a solução escolhida contra o cenário
mais extremo antes de aplicar — a decisão final é sempre sua, não do
council. Ele é externo: **não tem acesso à memória do bot, ao graphify nem
aos logs** — não substitui essas fontes para decisão sobre o estado do jogo.
Contrato completo, assentos ativos e quando NÃO vale a pena invocar:
`docs/SKILLS.md`, seção "claude-council".

## Skills instaladas no projeto (`.claude/skills/`)

- **`find-docs`** (Context7) — documentação atual de biblioteca externa.
- **`task-observer`** — meta-skill auto-invocada: observa a sessão e propõe
  skills/melhorias. Custo aceito: 24 KB de SKILL.md por sessão de trabalho.
- **`find-skills`** (vercel-labs) — acha e instala skill nova quando falta
  capacidade real. Invocar sozinho ao notar a lacuna, não só se pedirem.
- **`systematic-debugging`** e **`receiving-code-review`** (portadas de
  `obra/superpowers` 14/09/2026, plugin inteiro fica desligado — as outras
  12 skills dele duplicam ECC/regras já ativas) — a primeira antes de propor
  qualquer correção de defeito (causa raiz antes de remendo, 4 fases), a
  segunda ao avaliar o que `code-reviewer`/`security-reviewer`/`claude-council`
  apontam (verificar antes de implementar, nunca concordância performática).
- **`grilling-extras`** (25/09/2026) — complemento **obrigatório** das sessões
  de grilling (`mattpocock-skills:grilling`/`grill-me`), que é plugin e não
  aceita edição durável: pergunta o que é DOMÍNIO, anuncia para veto o que é
  ENGENHARIA, e só leva ao council as de engenharia. Carregar junto, sempre.

## Agentes especializados do ECC: proativo, não sob pedido (diretriz permanente — 09/09/2026)

O plugin `ecc@ecc` traz agentes de revisão auto-descobertos (não é preciso o
usuário pedir): `code-reviewer`, `security-reviewer`, `python-reviewer`,
`tdd-guide`, `build-error-resolver`, `refactor-cleaner`, `architect`,
`planner`, `doc-updater`, `e2e-runner`. **Invoque-os sozinho, no momento
certo:** `python-reviewer` depois de editar `.py`, `security-reviewer` em
código que toca senha/entrada externa/rede, `tdd-guide` ao escrever teste
novo, `code-reviewer` depois de qualquer edição não trivial, `doc-updater`
sempre que a alteração mudar conhecimento/convenção (a regra 2 já manda
atualizar o doc certo no mesmo passo — ele é quem faz isso, não só eu
lembrar), `e2e-runner` depois de qualquer mudança em `web/` (fecha o
"testar no navegador antes de reportar pronto" sem eu dirigir o
`test-web.ps1` na mão). Onde o `mattpocock-skills` (plugin global,
todos os projetos do usuário) oferece o mesmo papel (`tdd`, `code-review`,
`research`), o ECC vence NESTE projeto — nunca invocar os dois pro mesmo
diff/decisão. Auditoria completa dos plugins do projeto, tabela de conflito
e o que foi desligado e por quê: `docs/SKILLS.md`, seção "plugins e agentes
do projeto".

## Regras de manutenção (obrigatórias)

0. **Toda alteração ⇒ `git commit`, no mesmo passo — mesmo a menor delas**
   (diretiva permanente do usuário, 01/09/2026). O bot roda por horas em várias
   contas, e defeito aqui só aparece DEPOIS: a única forma barata de voltar ao
   que funcionava é ter um ponto por alteração. Um commit gordo com cinco
   assuntos não dá para desfazer pela metade — então **um assunto, um commit**,
   com a mensagem dizendo o que mudou de comportamento, não que arquivo mudou.
   Nunca junte "de passagem" o conserto de outra coisa.
0b. **A árvore é COMPARTILHADA com outras sessões** (25/09/2026: uma vizinha
   tinha 7 arquivos alterados enquanto outra trabalhava). Commite com pathspec
   (`git commit -- <seus arquivos>`), nunca `git add -A`/`commit -a`. Para
   desfazer o que é SEU: `git diff -- <arquivos> > x.patch` e `git apply -R
   x.patch` — nunca `git checkout --`/`stash` no arquivo inteiro, que apaga a
   edição da vizinha sem aviso.
1. **Toda alteração no código ⇒ atualizar o graphify:** `graphify update .`
   (reextrai AST-only e regenera `graph.json` + `GRAPH_REPORT.md`).
1b. **Toda alteração em `web/` ⇒ `npm run build`, no mesmo passo.** O app abre
   `dist/`, e o `3-INICIAR-WEB.bat` **não** faz build; o backend, ao contrário, é
   lido do código-fonte em toda execução. Sem o build, o usuário roda Python de
   agora com tela de horas atrás — combinação que não existe no repositório, que
   ninguém testou e que aparece como "funcionalidade que funcionava parou".
   Aconteceu em 07/09/2026, com 40 minutos de atraso no pacote. Travado por
   `tests/test_dist_atualizado.py`.
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
   **O DESTINO É DECIDIDO PELOS IMPORTS**, não pelo quão genérico o código
   parece: a camada mais rasa que já contém todas as dependências do módulo.
   Leia o bloco de imports ANTES de escrever o destino em qualquer documento —
   `tests/test_ecossistemas.py` é o contrato (plano escrito sem isso já apontou
   três módulos para o `core/` e custou quatro documentos corrigidos).
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

**Candidatos de promoção já identificados** (ainda em duplicata): a espera
fatiada que responde ao Parar (`app/executor._dormir` × `BotContext.tick`).
*Confirmar o TAB pela troca do id subiu em 06/09/2026 —
`core/target_hybrid.esperar_o_alvo_trocar`.*

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

## Como a IA trabalha aqui (diretriz permanente — 06/09/2026)

Diretrizes de comportamento para reduzir os erros típicos de LLM em código. Elas
**se somam** às regras deste arquivo; onde houver conflito, a regra específica do
projeto vence. **Contrapartida aceita: cautela acima de velocidade** — em tarefa
trivial, use o bom senso.

### 1. Pensar antes de escrever código

**Não presuma. Não esconda a confusão. Exponha o custo-benefício.**

- Diga as suas premissas em voz alta. Se estiver incerto, PERGUNTE.
- Havendo mais de uma leitura do pedido, apresente as leituras — não escolha uma
  calado.
- Havendo caminho mais simples, diga. Discorde quando for o caso.
- Se algo não estiver claro, PARE. Nomeie o que confunde. Pergunte.

### 2. Simplicidade primeiro

**O mínimo de código que resolve o problema. Nada especulativo.**

- Nenhuma funcionalidade além da pedida.
- Nenhuma abstração para código de uso único.
- Nenhuma "flexibilidade" ou "configurabilidade" que não foi pedida.
- Nenhum tratamento de erro para cenário impossível.
- Escreveu 200 linhas e dava em 50? Reescreva.

Pergunte a si mesmo: *"um engenheiro sênior diria que isto está
complicado demais?"* Se sim, simplifique.

### 3. Alterações cirúrgicas

**Toque só no que precisa. Limpe só a sua própria sujeira.**

- Não "melhore" código, comentário ou formatação vizinhos.
- Não refatore o que não está quebrado.
- Acompanhe o estilo existente, mesmo que você fizesse diferente.
- Viu código morto sem relação com a tarefa? **Avise — não apague.**
- Quando a SUA alteração deixa órfãos: remova os imports, variáveis e funções que
  ela mesma deixou sem uso. Código morto **preexistente** só sai se pedirem.

O teste: **toda linha alterada tem de remontar diretamente ao pedido do
usuário.**

### 4. Execução guiada por objetivo

**Defina o critério de sucesso. Repita até verificar.**

Transforme a tarefa em objetivo verificável:

- "adicionar validação" → "escrever testes para entradas inválidas e fazê-los
  passar"
- "consertar o defeito" → "escrever um teste que o reproduz e fazê-lo passar"
- "refatorar X" → "garantir que a suíte passa antes e depois"

Em tarefa de vários passos, declare um plano curto:

```
1. [passo] → verificação: [conferência]
2. [passo] → verificação: [conferência]
3. [passo] → verificação: [conferência]
```

Critério forte deixa você fechar o laço sozinho; critério fraco ("fazer
funcionar") obriga a esclarecer a cada passo.

### 5. Idioma da resposta (diretriz permanente — 07/09/2026)

**Documentação, comentário de código gerado, mensagem de commit e a resposta
narrativa são sempre em Português do Brasil — independentemente do idioma do
prompt.** Prompt em inglês, fragmento de código em inglês, nome de variável em
inglês: nada disso muda o idioma da resposta. Não vale para **identificador de
código** (nome de função/variável segue o idioma já usado no arquivo) nem para
**string traduzível de interface** (`docs/SKILLS.md`, seção "i18n" — ali PT-BR
é só a chave-fonte, não o único idioma válido).

### 6. Código por script: NUNCA por heredoc (medido em 5 sessões)

Código com barra invertida, crase, aspas aninhadas ou prosa acentuada **não
passa por heredoc de shell**: o `\n` vira quebra de linha real, o `\\` vira `\`,
e o script imprime "ok" do mesmo jeito. Grave o script com a ferramenta de
escrita e rode-o pelo caminho. Depois de TODO patch por script, rode o
parser/linter do alvo — o "ok" prova que a âncora casou, não que o resultado é
válido. E script de patch é migração: passos idempotentes, âncora que só casa
num lugar, contagem de itens antes e depois.

## Skills e Agent skills

As definições completas de skill (pywebview + Web Frontend, GUI e Interatividade,
Issue tracker, Domain docs) moram em **`docs/SKILLS.md`** — mantidas lá para não
inchar este arquivo. Leia `docs/SKILLS.md` quando for mexer em interface ou
precisar do contrato de skill.
