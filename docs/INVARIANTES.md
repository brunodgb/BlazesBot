# INVARIANTES por área — o que não pode ser violado

> **Saiu do `CLAUDE.md` em 27/08/2026**, pela regra de governança do usuário: o
> `CLAUDE.md` guarda skills, arquitetura global e regras técnicas críticas; regra
> de ÁREA mora aqui. O conteúdo abaixo é **verbatim** — nada foi reescrito nem
> resumido na mudança.
>
> **LEIA A SEÇÃO DA ÁREA ANTES DE MEXER NELA.** Cada item é o que não pode ser
> violado. A especificação técnica está em `docs/REGRAS.md`; o **porquê medido**,
> em `docs/decisoes/<area>.md` — e é lá que mora a alternativa que já reprovou.

---
## Injeção de teclado — `docs/decisoes/sistema.md`

> A regra permanente ("nenhuma mensagem sai para uma janela que não é o jogo")
> está no `CLAUDE.md`. Aqui está o que ela exige na prática.

- **`WM_KEYUP` SE MANDA COM `lParam` MONTADO, NUNCA COM ZERO.** Os bits 30
  (estado anterior) e 31 (transição) têm de valer 1, e o scan code sai de
  `MapVirtualKey(vk, 0)` — nunca de literal, porque o scan é físico e muda com o
  layout. Com `lParam = 0` a mensagem se contradiz e o cliente descarta: era por
  isso que o SHIFT segurado no navegador contaminava o jogo em segundo plano
  (11/09/2026). A fórmula mora em `core/teclado_win32.lparam_de_keyup`.
- **MAS ISSO SÓ ALCANÇA `GetKeyState`.** Mensagem sintética não toca
  `GetAsyncKeyState` nem RawInput, que leem o hardware. Nenhuma toca. Quem
  prometer isolamento total por mensagem está errado.
- **`_enviar_tecla` ACEITA `lparam`, COM PADRÃO ZERO.** Zero está certo para
  `WM_KEYDOWN` e `WM_CHAR`; só o KEYUP precisa do registro montado, e quem
  precisa passa.
- **IDENTIDADE SE PROVA, NÃO SE SUPÕE.** O pino da janela só fecha com uma
  leitura POSITIVA de `client.exe`. "Não consegui ler o processo" **bloqueia** ao
  estabelecer o pino — nunca houve prova. Custou 918 caracteres digitados no
  Bloco de Notas do usuário em 09/09/2026.
- **MAS "NÃO SEI" NÃO REVOGA PINO JÁ CONFIRMADO.** Um `AccessDenied` passageiro
  não pode trocar um defeito raro (tecla na janela errada) por um permanente
  (bot mudo). As duas metades são travadas por teste.
- **TETO DE `LIMITE_DE_CARACTERES` (50) POR INJEÇÃO, e ele RECUSA por exceção.**
  Truncar mandaria 50 caracteres de lixo e esconderia o defeito. Nada que este
  bot digita passa de ~20 caracteres.
- **TETO DE `LIMITE_DE_BACKSPACES` (64) NA LIMPEZA DE CAMPO**, e o BACKSPACE sai
  pelo NOME resolvido em `VK_CODES` (0x08), nunca por literal.
- **CARACTERE DE CONTROLE É RECUSADO.** Não existe em login, senha nem nick — é
  a assinatura de bytes crus de memória chegando como se fossem texto.
- **A JANELA É RECONFERIDA A CADA CARACTERE**, e a digitação PARA quando ela
  deixa de ser confiável. É o caso normal do relogin: o cliente cai com a senha
  sendo digitada.
- **MODIFICADORES SÃO SOLTOS ANTES DE CADA INJEÇÃO** (uma vez por texto, não por
  caractere): SHIFT grudado transforma o login inteiro em maiúsculas.
- **DIGITAÇÃO PARCIAL ABORTA O LOGIN.** Login pela metade não é login: é
  tentativa queimada no servidor, e tentativa queimada é o caminho para a conta
  bloqueada.
- **O LOG NUNCA MOSTRA O TEXTO** — só o rótulo (`login`/`senha`) e o tamanho.
  Senha em arquivo de log é senha vazada.
- Travado por `tests/test_injecao_de_texto_blindada.py` (18) e
  `tests/test_trava_da_janela.py`.

---
## Login e relogin — `docs/decisoes/login-e-relogin.md`

> É o ecossistema BASE: **todo** ecossistema, presente e futuro, obedece.

- **A QUEDA É PERCEBIDA POR UMA THREAD QUE NÃO É A DO BOT.** O vigia global
  (`bot/sentinela.py`) acorda a cada `CADENCIA_DO_VIGIA` (6 s) e pergunta pelas
  contas todas. Vigia dentro do laço do bot **não funciona**: `SendMessageW`
  síncrono contra janela travada bloqueia a thread que enviou, para sempre — e a
  conferência estava sempre na linha seguinte.
- **O TETO É 20 SEGUNDOS**, da queda até o `TerminateProcess`, em qualquer
  ecossistema (BC, HH, APP) e **também com a conta ociosa ou no backoff**.
  `confirmações × cadência ≤ 20 s` é conta, não estimativa: travamento 3×6 s =
  18 s; janela sumida 2×6 s; processo e aviso na tela matam na primeira volta.
  Travado por `tests/test_vigia_global.py`.
- **DURANTE O LOGIN O VIGIA SÓ RECONHECE FATO DO SISTEMA OPERACIONAL** —
  processo sumido e janela sumida. **Aviso na tela e travamento ficam
  suspensos** enquanto `login.run()` está no comando (`_login_em_curso`, virado
  no mesmo ponto em que o backoff zera). Motivo medido: o template do vigia é UM
  só, `state_conn_prefix.png`, que casa com a palavra "Connection" — e as telas
  de login têm uma FAMÍLIA de caixas que começam com ela, desenhadas no MESMO
  centro (`"Connection failed"` = 0.835, `"Connecting to the server"` = 0.787,
  medidos em `login_states.py`). O `LoginDetector` convive com isso porque tem
  **escada ordenada** e deixa o genérico opinar por último; o vigia usa o
  genérico sozinho. O limiar 0.92 foi medido contra população **em jogo** —
  usá-lo fora dela é o que o projeto proíbe. Custou um laço de relogin a cada
  19 s em 09/09/2026. Agravante do travamento: a **fila de login** passa de três
  horas e não há medição de como o cliente bombeia mensagens nela.
- **O LOGIN/RELOGIN NÃO SE INSTANCIA EM ECOSSISTEMA NENHUM — ELE RODA EM
  PARALELO** (diretriz do usuário, 11/09/2026). O vigia é uma **thread própria**,
  registrada UMA vez no `run()` do supervisor, que recebe PEÇAS (o login e uma
  função que devolve `(pid, hwnd)`) e nunca um `BotContext`. Ecossistema novo
  recebe detecção, kill, Histórico e relogin **sem escrever uma linha** e sem
  chamar nada. O vigia não importa nada de `bc/`, `app/` nem `hh/` — travado por
  AST em `tests/test_vigia_global.py`.
- **O VIGIA LÊ A TELA** (`sentinela.OLHAR_A_TELA = True`). Desligá-lo travou três
  contas de APP/Fada em 11/09/2026, porque **o watchdog inline só existe no BC**
  — `ctx.watchdog` é injetado num lugar só (`bc/routine.py`), e quem não é BC sai
  por `return` na primeira linha de `check_watchdog`. A Fada é o caso extremo:
  não chama `ctx.tick()` e só percebe queda por `IsWindow` DEPOIS do laço, que a
  caixa na tela nunca deixa terminar. Os 48 falsos positivos que motivaram o
  desligamento aconteceram todos nas telas de login, e a suspensão de juízo
  durante o login já os cobre — é anterior ao interruptor.
- **O HISTÓRICO DE QUEDAS NÃO DEPENDE DE O ECOSSISTEMA TER ANOTADO.**
  `_registrar_queda` consulta o anúncio do vigia quando `ctx.ultima_queda` está
  vazio. É o funil do Histórico para todo ecossistema, presente e futuro.
- **RESÍDUO CONHECIDO:** a *saída* da thread do ecossistema ainda é cooperativa
  (o vigia mata, mas quem desiste do laço é o próprio ecossistema). Ver
  `docs/decisoes/login-e-relogin.md`.
- **QUATRO SINAIS, E O QUARTO É NOVO.** Processo sumido, janela sumida e aviso na
  tela continuam em `watchdog.avaliar_saude` — a UMA definição de queda, sem
  estado, que todo mundo chama. O **travamento** mora no vigia porque exige
  memória entre ciclos (`STRIKES_PARA_JANELA_TRAVADA`), e `avaliar_saude` não tem
  nem pode ter estado. Não são duas definições concorrentes: é um sinal a mais.
- **A SONDA DE TRAVAMENTO VEM ANTES DA CAPTURA.** `PrintWindow` manda `WM_PRINT`
  síncrono: fotografar janela travada penduraria a thread do vigia como pendura
  a do bot. Só se fotografa janela que acabou de responder a `WM_NULL`.
- **O VIGIA NÃO ENCOSTA NO QUE É DA THREAD DO BOT.** Nada de `ctx.memory` (o
  handle é fechado pelo dono), nada de `capture_window` (o pool de GDI é
  dicionário sem cadeado e `_release` o destrói) — use
  `core.vision.capture_window_isolado`. `TemplateLibrary` própria. O único estado
  que cruza a fronteira é o anúncio, sob cadeado.
- **ANUNCIAR ANTES DE MATAR, e a ordem não é trocável.** O kill desbloqueia a
  thread do bot na mesma hora; sem o anúncio já publicado, ela veria só "processo
  sumiu" e o Histórico de Quedas registraria o efeito no lugar da causa.
- **MATAR É PELA RAIZ.** `kill_client` é `TerminateProcess` direto, com
  `taskkill /F /T` de reserva. **Nada de `terminate()`, `ALT+F4` ou clique no X**:
  quem chega nessa função já não está ouvindo, e a cortesia custava 5 s de um
  orçamento de 20.
- **QUEM RELIGA CONTINUA SENDO O SUPERVISOR.** O vigia não sabe o que é login. A
  thread do bot lê o anúncio (`BotContext.check_watchdog`), levanta
  `Disconnected`, e o `run()` faz `_encerrar_caido` → backoff → nova sessão.
- **O ANÚNCIO MORRE JUNTO COM O CONTROLE DA JANELA**, em `_release()` — o ponto
  por onde os CINCO caminhos de morte de sessão passam, e não em cada um deles.
  Apaga-se também sozinho quando a conta volta noutro PID. Anúncio esquecido de
  pé derruba a sessão NOVA no primeiro `tick` — relogin em laço, o defeito com o
  sinal invertido. **Foi por faltar isso que a queda tratada pelo LOGIN
  (`ClientClosed`) deixava o anúncio vivo.**
- **NENHUMA CONFERÊNCIA DE QUEDA DENTRO DE `_sleep_interruptible`.** As quatro
  chamadas de backoff do `run()` estão dentro de blocos `except`, e exceção
  levantada ali não é pega pelos `except` do mesmo `try`: sobe para o
  `except BaseException` de baixo e **ENCERRA a thread da conta**. Aconteceu em
  09/09/2026, 00:56. E não há o que ganhar ali: durante o backoff a conta não
  tem cliente (`_release` zerou pid e hwnd), então o único anúncio possível é o
  velho — e cortar o backoff é errado, ele existe para não martelar o servidor
  de login. A espera da conta ociosa é `ctx.tick()`, que consulta.
- **SAIR DA VIGILÂNCIA AO ENCERRAR** (`sentinela.esquecer`, no `finally` do
  `run`). Sem isso o vigia mata o cliente que o usuário acabou de assumir na mão.
- **A CONTA ENTRA NO VIGIA UMA VEZ POR EXECUÇÃO, não por sessão.** O tempo ruim é
  passado FORA de uma sessão: backoff, espera de login, conta ociosa.
- **O REPOUSO CUSTA 0% DE CPU** — `Event.wait`, nunca `time.sleep`. É a única
  thread que roda o tempo todo, com o bot ocioso ou não.
- Interruptor: `sentinela.MATAR_JANELA_TRAVADA` (o único critério que mata janela
  que o Windows ainda considera viva).

---
## O laço do APP — `docs/decisoes/cura-no-app.md`

- **PERÍMETRO DE 12: PASSOU, RECOLHE** (09/09/2026). Personagem a mais de
  `coleira_do_ponto.RAIO_DO_PERIMETRO` do ponto ⇒ aborta ataque, macro e
  espera, ANDA de volta, aperta a tecla de limpeza e TABa. É a QUARTA versão da
  coleira; leia o topo de `core/coleira_do_ponto.py` antes de mexer.
- **QUEM CORTA, ANDA.** A 1ª versão media a mesma coisa e DELEGAVA a caminhada
  à trava de posição, que se recusa a andar em batalha — personagem parado
  apanhando, para sempre. O recolhimento anda EM BATALHA: é a exceção
  deliberada a `ANDAR_SO_FORA_DE_BATALHA`.
- **E SABE DESISTIR.** Três recolhimentos seguidos sem chegar (parede no
  caminho) e o perímetro só MEDE por um minuto, deixando o bot lutar onde está.
  Sem isso, o corte a cada volta é o travamento permanente com outro nome.
- **O PERÍMETRO NÃO RECUSA ALVO.** Foi a recusa que matou a 2ª e a 3ª versões:
  cada recusa custa um TAB, e cada TAB afasta a seleção.
- **TRÊS PONTOS DETECTAM, UM AGE:** topo da volta, meio da macro e dentro da
  espera fatiada cortam; só o topo da volta caminha. Dois lugares andando
  seriam duas caminhadas concorrentes para o mesmo ponto.
- **EM BATALHA SEM ALVO E LEVANDO DANO, O BOT TABA NA HORA** (07/09/2026). O
  TAB só existia no ramo FORA de batalha: morto o mob, com outro batendo, a
  volta abortava na primeira linha e o personagem ficava apanhando parado. O
  reflexo pula pet, comida, caminhada e bolsa — com dano entrando, cada um
  desses é tempo apanhando.
- **QUEM ACUSA A AGRESSÃO É A VIDA CAINDO**, não a flag de combate
  (`core/vigia_da_vida.py`). A flag é um ESTADO e fica alta por motivos que não
  são dano; a vida caindo é um EVENTO. Só QUEDA conta (regeneração e cura
  sobem), a régua anda para os dois lados, e "não sei" não acusa nada.
- **TRÊS TRAVAS CONTRA O TAB INFINITO:** só se entra no reflexo SEM alvo vivo;
  o alvo adquirido CONSOME a marca; e há cadência (`ESPERA_SEM_ALVO`) entre
  dois TABs do reflexo — sem ela, um golpe por segundo viraria um TAB por
  segundo.
- **VIDA BAIXA EM BATALHA BEBE ONDE ESTÁ** (07/09/2026). Toda a cura ficava
  atrás de "saiu de batalha", e com quatro a oito mobs batendo essa flag não
  baixa: três personagens morreram vendo a vida cair de 35% a zero sem uma
  poção. O socorro NÃO anda e NÃO senta — andar arrasta mob, e quem mata quem
  está batendo é a macro. Uma poção por vez, na cadência.
- **A VIDA SE CONFERE DENTRO DA ESPERA DA LINHA**, não só entre as linhas. Uma
  rotação de macro chega a 21 s, e foi nesse buraco que um personagem foi de
  100% a zero.
- **TECLA SEM EFEITO TEM DESFECHO, NÃO SÓ AVISO** (`core/teclado_mudo.py`). Duas
  teclas independentes mudas com mob vivo por perto ⇒ ESC uma vez ⇒ relogin.
  É o SEGUNDO motivo para o bot derrubar a própria sessão, e a justificativa é a
  da primeira: conta que não recebe tecla produz o mesmo que conta deslogada, e
  a deslogada tem conserto automático. Uma tecla só NÃO acusa, e spot vazio
  nunca acusa. Porquê medido em `docs/decisoes/madrugada-07-09-2026.md`.

`bot/app/executor.py` + `cura.py`. **Todos os números moram lá**; a
especificação em `docs/REGRAS.md`.

### O LAÇO QUE RODA é o SIMPLES (`LACO_SIMPLES = True`, 26/08/2026)

Decisão do usuário depois de refinamentos que foram ficando piores:
*"vamos voltar ao simples — dá TAB, deixa rodar a macro até o final, só para no
meio se SAIR DE BATALHA; não verifica mais vida, não verifica mais nada"*.

```
FORA de batalha → pet → comida → voltar ao ponto → limpar bolsa → TAB único → linha 0 → macro
EM batalha       → roda a macro de novo, SEM TAB e SEM conferência
saiu de batalha  → corta a macro no meio, volta ao topo
vida < 30%       → a cura, entre voltas (inalterada)
```

- **ORDEM ESTRITA: TODO "fora de batalha" ANTES do TAB, o TAB por ÚLTIMO.** Pet,
  comida, trava de posição e limpeza da bolsa vêm PRIMEIRO; a aquisição de alvo
  é a ÚLTIMA coisa antes da linha 1 (a regra absoluta do Core Loop). A limpeza
  da bolsa passou do fim da volta para cá em 29/08/2026.
- **UM SÓ CAMINHO DÁ TAB, `_adquirir_alvo`** (29/08/2026). O relógio dos 4 s
  do time NÃO TABa mais em `rodar()` — só PEDE via `_tab_solicitado`, consumido
  pela volta. É IDEMPOTENTE (`_mesmo_alvo_verificado`): se já tenho o alvo VIVO
  confirmado, o TAB não sai de novo mesmo que o relógio e o portão peçam na mesma
  volta. Foi o fim do TAB duplo no modo "copiar".
- **O GUARD SE COMPÕE COM AS TRÊS TROCAS QUE VALEM:** alvo morto/sumiu libera o
  TAB; o mob do PENHASCO (`_inalcancavel_id`) não é protegido; e o contador
  `VOLTAS_SEM_BATALHA_PARA_TROCAR = 3` (alvo vivo travado) VENCE a idempotência.
- **SEM ALVO REAL A MACRO NÃO RODA — o veredito da aquisição é PROPAGADO**
  (30/08/2026). O vazamento fechado: `_conseguir_o_tab` engolia o `False` de
  `_garantir_alvo` e a macro disparava com `target_id == 0` (ou travado no
  cadáver). Agora ele PROPAGA: id não mudou nem está vivo ⇒ `_garantir_alvo`
  volta `False` ⇒ `_adquirir_alvo` volta `False` ⇒ a volta retorna ao Core Loop
  **antes da linha 1** — nenhuma skill sai no vazio. No caminho cego (sem
  leitura de memória) o contrato histórico permanece: TAB cego, macro roda.

- **NÃO LÊ O ALVO EM LUGAR NENHUM** — nem HP, nem id, nem nome, nem a barra. A
  única pergunta é *"estou em batalha?"*, da struct do PERSONAGEM, que nunca
  falhou em nenhuma medição.
- **EM BATALHA NÃO SE DÁ TAB** — é isso que impede o defeito que matou o
  personagem: não existe caminho onde ele larga um mob de pé.
- **O MOB DO PENHASCO SE RESOLVE SOZINHO:** TABa nele, roda a macro, nunca entra
  em batalha, termina fora de batalha e TABa de novo. A régua virou
  consequência de não existir.
- **A LINHA 0 DA MACRO É O TAB** (`espera_depois_do_tab_ms`, padrão 1000): tecla
  **espelho** de `keys.next_target`, só-leitura, posição fixa, tempo editável.
  **NÃO é `AppStep`.** Piso de **100 ms** em todo tempo do APP; **20 linhas**.
- **QUEM JÁ ESTÁ NO PONTO NÃO RECEBE ORDEM DE ANDAR** — clique no minimapa é
  ordem de andar, e ordem pendente **cancela a poção**.
- **CURA:** vida < 30% ⇒ espera SAIR DE BATALHA, volta ao ponto, bebe até 90%
  (até 5 poções, 15 s). **Só se anda ANTES de beber.** **Beber PÕE SENTADO** —
  não sentar prova que a poção acabou; aí ele SENTA (até 30 s). Devolve **DE
  PÉ** e não conta volta.
- **`is_sitting()` e `pet_active()` SÃO TRI-ESTADO** (consertadas na FONTE): da
  **2ª poção em diante** ele já está sentado, então "sentou" não prova nada.

### O que ficou PARADO (interruptor, não apagado)

Morte pelo HP, a segunda porta pela TELA, o pedágio das 3 linhas cegas, a régua
do penhasco, a urgência. **Cada uma tem medição atrás**, e
`tests/test_tab_no_app.py` desliga o interruptor e exercita todas — religar é
trocar um `True` por `False` e 134 testes voltam a valer.

A conferência de id no TAB RELIGOU como parte do TAB único (`_adquirir_alvo` +
`_mesmo_alvo_verificado`): o TAB de abertura agora confere id/hp em memória e é
idempotente, não cego por timer. O porquê está em
`docs/decisoes/tab-unico-do-app.md`.

- **O ALVO VEM PELO MESMO CAMINHO DO BC** (`TargetHybrid`) quando for religado.
  O portão `critical_ok()` vale **só para as leituras do personagem**.
- **MEDIÇÃO EM ABERTO:** mobs vivos e inteiros existem FORA da janela que
  `_procurar_entidade` varre (`docs/decisoes/alvo-o-que-esta-medido.md`, itens
  39–41). Achar o array de verdade é o que devolve a leitura do alvo.

## Esconder jogadores e pet bug — feito PELO BOT, por conta

- **O PROGRAMA DE TERCEIRO ESTÁ DESLIGADO** (`petbug.ATIVADO = False`,
  07/09/2026). Decisão do usuário: *"ou usar o PetBug.exe ou fazer por dentro do
  bot; os 2 ao mesmo tempo não faz sentido (...) ele executa isso em TODOS os
  client.exe SEM DISTINÇÃO"*. Um clique no programa patchava até as contas de
  APP. Interruptor e não remoção — religar é uma linha.
- **A TECLA DE ESCONDER FICA PRESA, e nunca é solta** (`WM_KEYDOWN` sem
  `WM_KEYUP`, `esconder_jogadores.prender_a_tecla`). A tecla esconde ENQUANTO
  está apertada; nunca soltar é esconder para sempre — sem abrir o chat, que é
  o defeito mais caro do truque antigo. `Input.key_up` RECUSA soltá-la.
- **REAFIRMA-SE A TECLA**, no login e antes de cada tentativa de entrada (BC e
  HH). Tecla fisicamente presa repete sozinha; reafirmar é imitar isso, e é o
  que devolve o esconder depois de um relogin.
- **O PATCH DE MEMÓRIA É NOSSO** (`core/patch_do_cliente.py`): dois
  `mov [reg+0x10A8]` NOPados no `client.exe`, com os mesmos bytes do programa.
  RECUSA quando o padrão não aparece exatamente uma vez, confere a releitura, e
  é idempotente. Engenharia reversa completa em
  `docs/decisoes/pet-bug-engenharia-reversa.md`.
- **SÓ CONTAS DE CAVE (BC e HH).** Decisão do usuário: *"os APP não precisa
  aplicar"*. O portão é `if self.account.farms:` (= `bc_farm or hh_farm`) e ele
  não pode ser alargado.
- **A TECLA ESCONDE OS PETS TAMBÉM** — medido pelo usuário em 10/09/2026, contra
  o que estava escrito. Duas consequências: o patch do pet **não** existe para
  desobstruir clique (com a tecla presa não há pet na tela), e sim para **não
  cair**; e conferir o patch pelo VISUAL exige soltar o F12 — com o bot rodando
  não se vê pet nenhum, patcheado ou não. A resposta objetiva é
  `python -m blazesbot.tools.conferir_petbug` (`19-CONFERIR-PETBUG.bat`).

## PetBug (o programa de terceiro, hoje desligado)

- **O PATCH DE MEMÓRIA É NOSSO AGORA** (`core/patch_do_cliente.py`, 07/09/2026):
  dois `mov [reg+0x10A8]` NOPados no `client.exe`, com os mesmos bytes do
  programa de terceiro. Ele RECUSA quando o padrão não aparece exatamente uma
  vez, confere a releitura depois de escrever, e é idempotente. Roda JUNTO com o
  `.exe` — o `.exe` ainda é quem manda o F12. Engenharia reversa completa em
  `docs/decisoes/pet-bug-engenharia-reversa.md`.
- **SÓ CONTAS DE CAVE (BC e HH) RECEBEM O PATCH.** Decisão do usuário em
  07/09/2026: *"os APP não precisa aplicar"*. O portão é
  `if self.account.farms:` (= `bc_farm or hh_farm`) e ele não pode ser alargado.
- **REAPLICAR NÃO ALTERNA O F12.** O programa manda `WM_KEYDOWN` de VK_F12 SEM
  `WM_KEYUP`, então a tecla fica logicamente presa e os jogadores ficam
  escondidos; um segundo KEYDOWN é auto-repetição, não uma borda nova. É o que
  torna a reaplicação segura.
- **INSTÂNCIA NOVA A CADA APLICAÇÃO** (07/09/2026). Mata o que estiver aberto e
  abre outro antes de clicar em `Patch`. Não é higiene: a confirmação lê o log
  do programa e aceita o texto que já estava lá, então **janela reusada
  confirma clique que não fez nada**. Log limpo é a prova. Interruptor:
  `petbug.NOVA_INSTANCIA_SEMPRE`.
- **A JANELA MINIMIZADA É RESTAURADA SEM SER ATIVADA** (`SW_SHOWNOACTIVATE`) —
  ativar roubaria o foco do cliente do jogo.
- **A ENTRADA DA CAVE REAPLICA O PATCH** depois de N falhas MECÂNICAS seguidas:
  jogador na frente do NPC é a causa medida de o diálogo não abrir. Instância
  cheia NÃO conta (ali os cliques saíram). Porquê em
  `docs/decisoes/madrugada-07-09-2026.md`.

## Deletar itens: LIGADO, e só no ecossistema APP

`blazesbot/bot/app/deletador.py`. O BC resolve bolsa cheia vendendo; o APP roda
longe de vendedor. Detalhe e medição: `docs/REGRAS.md` (seção "Deletar itens")
e `docs/decisoes/deletador.md`.

- Fluxo **NÃO usa tecla**: item → ícone de deletar → caixa → **Ok** (derivado do
  título por `(-76,+172)`).
- **SÓ ABAIXO DA LINHA DE ABAS** "Item | Quest | Arrange | Ext." — acima é
  equipamento em uso; sem achar a linha, **não apaga nada**.
- **O RETÂNGULO TEM DE PASSAR DO FIM DA GRADE**, nunca fechar nela: a bolsa
  principal tem **5 linhas** entre dy +13 e +190 (35 px cada, ancoradas nas
  abas), e o retângulo vai até +195. Fechar em +186 custou a 5ª linha inteira —
  `matchTemplate` quer o modelo INTEIRO dentro do recorte, e não há casamento
  parcial (`deletador.md`, 10/09/2026).
- `data/templates/deletar/` é a **LISTA BRANCA única** (PNG autoriza, tirar
  revoga), relida a cada chamada. A tecla do inventário é interruptor ⇒ o estado
  é **LIDO antes**; `None` não é "aberto".
- **CEGO NÃO ENCOSTA NA TECLA** (17/09/2026). `inventario_esta_aberto` devolvendo
  `None` — sem quadro **ou sem o modelo do ícone** — encerra a limpeza sem
  apertar nada. Apertar sem saber FECHA a bolsa que o usuário deixou aberta, e o
  fim não devolve (ele também fecha olhando); e apagar depende da tela do mesmo
  jeito, então não se perde limpeza nenhuma.
- **SEM O MODELO, A RESPOSTA É "NÃO SEI".** O ícone de deletar é a evidência de
  que a bolsa está aberta: sem o PNG carregado, "não achei o ícone" NÃO é "a
  bolsa está fechada". Foi essa mentira que fechou o inventário do usuário
  durante sete horas quando os templates mudaram de pasta.
- Gatilho `AppConfig.apagar_lixo_a_cada` (padrão 10, `0` = nunca). **CAMPO NOVO
  EM `AppConfig`/`AccountSettings` PRECISA ENTRAR NO `_app_from_dict` /
  `_settings_from_dict`** (travado por `tests/test_config_ida_e_volta.py`).
- **AFERIÇÃO ANTES DE CONFIAR** (`bot/app/afericao.py`, desenho em
  `bot/afericao_do_lixo.py`): fotografa o que seria apagado sem clicar. Deletar
  não tem desfazer.
- **CADA CONTA GUARDA AS EXCEÇÕES, NUNCA A LISTA INTEIRA** (`desativados`, em
  `AppConfig` e `HHConfig`). A pasta continua dizendo o que PODE ser apagado, e
  PNG novo nela vale em todas as contas sem ninguém ligar nada. Guardar os
  ATIVOS mataria esse invariante e poria 208 nomes por conta no `config.json`.
- **A LISTA É LIDA NO MOMENTO DA LIMPEZA** (`deletador.modelos_ativos`), nunca
  capturada na montagem do executor: a interface e a thread da conta
  compartilham o mesmo objeto de configuração, então salvar vale na limpeza
  seguinte, sem religar o bot.
- **QUEM APAGA E QUEM CONFERE CARREGAM PELA MESMA PORTA** (`_carregar`). Uma
  aferição que enxergasse mais que a exclusão desenharia retângulo em item que
  aquela conta não apaga.

## Time do APP

### A montagem do time — 16/09/2026

- **SÓ O LÍDER MONTA.** Seguidor que volta sem time não faz nada, só roda a
  macro: quando ele volta e o resto do time ficou online, **o jogo o recoloca no
  time sozinho** (mecânica medida pelo usuário). O líder é quem pergunta, e
  quando ele não tem time, convida todos.
- **NÃO SE CONVIDA ÀS CEGAS.** Só entra na fila quem publicou sinal de vida nos
  últimos `mural.ESTADO_VALIDO_SEGUNDOS` — conta deslogada não recebe convite e
  não gasta ciclo.
- **UM CONVITE POR VEZ.** A Block list é LIMPA antes de cada registro, então o
  alvo do clique direito é sempre a primeira linha. Não existe código que
  distinga linhas, e reconhecer qual é de quem convidaria a pessoa errada
  quando o recorte não batesse.
- **ROTAÇÃO COM TETO:** quem não aceita volta para o fim da fila; ao fim de
  `time_do_app.TENTATIVAS_POR_MEMBRO` passadas a montagem encerra e o resto fica
  para o ciclo seguinte. O líder não fica parado por causa de uma conta fora.
- **EM BATALHA NÃO SE MONTA TIME** — abrir a Block list com mob batendo é o
  personagem parado apanhando. Mesma regra do pet, da comida e da bolsa.
- **O ARRANQUE DO APP CONFERE O TIME**, antes da primeira volta: o usuário abre
  o BlazesBot com as contas já logadas, e sem essa conferência o bot ia direto
  para a macro com o time desfeito.

- **O SEGUIDOR ACEITA DENTRO DA MACRO**, na espera fatiada da linha — não entre
  as voltas. O líder espera poucos segundos por cada convite, e uma volta de
  macro passa disso sozinha. O `InviteAcceptor` vive num ramo do laço do
  supervisor que o modo APP nunca alcança.
- **NENHUM CLIQUE ESQUERDO SAI SEM PROVA DE QUE A CAIXA EXISTE**
  (`InviteAcceptor(exigir_caixa=True)`). O Ok é clique esquerdo, o mesmo que faz
  o personagem andar. Imagem primeiro; `memory.modal_open()` é a via que
  responde com o cliente fora de primeiro plano. A conta de RESET mantém o
  clique cego de hoje — lá ela fica parada num canto, e apertar a regra mudaria
  um farm que roda.

- **PICK MODE: FREE, ao formar o time.** Sem ele o loot dos mobs não é
  recolhido. O submenu **não abre com clique** — clicar em "Pick Mode:" FECHA o
  menu (medido à mão pelo usuário); abre com o mouse POR CIMA
  (`Input.passar_o_mouse`, `WM_MOUSEMOVE` sintético, sem cursor físico).
- **SEM PROVA, NENHUM CLIQUE NO SUBMENU.** Não existe template de menu de
  contexto em disco — `menu_leave_team.png` e `menu_team_up.png` são carregados
  e não existem, e as coordenadas medidas é que são o mecanismo. Aqui a prova é
  a REGIÃO MUDAR (`vision.regiao_mudou`). Errar a linha do submenu selecionaria
  "Dice" ou "Teamlead", que é pior que não fazer nada.
- **O "Free" fica na MESMA ALTURA do hover** — ele é o primeiro item e o submenu
  abre alinhado com a linha. Deduzir a altura seria um segundo palpite.

- **O MENU DE CONTEXTO DO CONVITE MUDA DE TAMANHO COM A DISTÂNCIA.** Perto do
  convidado o cliente acrescenta Follow, View Equipment, Trade e Duel, e
  "Team up" desce três linhas (7 → 12 itens). O BC convida a conta de reset, do
  outro lado do mapa; o APP convida quem está ao lado. Qual dos dois veio se
  mede pela ALTURA da caixa que apareceu (`vision.altura_da_mudanca`), e a
  medida erra SEMPRE para o menu CURTO: ali o erro é "View Equipment", que o
  `_fechar_janelas` seguinte fecha — errar para o longo no menu curto clicaria
  em "Recruit Apprentice", um pedido de aprendiz para a outra conta.

- **O CONTEXTO DO ACEITADOR TEM DE SABER QUEM ELE É.** O seguidor monta um
  `BotContext` próprio para aceitar dentro da macro, e ele nasce com
  `char_name = None` — quem preenche é a sessão do supervisor, em OUTRO
  contexto. O `InviteAcceptor` reconhece o convite pelo anúncio interno
  (`convite_pendente(meu_nick)`): com o nick vazio, o caminho do anúncio — o
  único que funciona sem imagem — nem começa, e o seguidor recusa tudo calado.
  Medido em 16/09/2026: quatro convites, zero cliques, caixa na tela por seis
  horas.
- **RECUSA SEM PROVA DEIXA RASTRO.** Havendo convite anunciado e nem imagem nem
  `modal_open()` para confirmar a caixa, o aceitador registra UMA linha dizendo
  qual via faltou. Sem ela, "não aceitou em 4s" do lado do líder é tudo o que
  existe — e não diz nada sobre o lado que não clicou.

Porquê de cada decisão: cabeçalho de `bot/time_do_app.py`.
 — `docs/decisoes/time-do-app.md`

A mesma macro rodando em até cinco contas (um líder + `MAXIMO_DE_SEGUIDORES_DO_TIME`
seguidores). Pedido do usuário em 27/08/2026.

- **QUEM MONTA O TIME É O LÍDER.** `AppConfig.time_logins` só tem efeito na
  conta que o preencheu. Conta que aparece na lista de outra é SEGUIDORA, e o
  time dela própria é ignorado enquanto isso — é essa regra única que impede o
  nó de A liderar B enquanto B lidera A.
- **SÓ A MACRO É EMPRESTADA**: as 20 linhas, os delays e
  `espera_depois_do_tab_ms`. **NUNCA** `_base_pos_x`/`_base_pos_y` (é a
  coordenada DAQUELE personagem — copiar manda o seguidor andar para o mapa
  errado) nem `KeyBinds.next_target` (descreve o teclado daquele cliente).
- **O EMPRÉSTIMO É EM TEMPO DE EXECUÇÃO.** O `config.json` do seguidor não é
  reescrito. Nenhum caminho do time pode gravar a macro do líder em outra conta.
- **NINGUÉM FICA PARADO ESPERANDO.** A largada tem TETO: quem não chega a tempo
  segue batendo sozinho e entra na próxima largada que alcançar. Barreira sem
  teto é proibida — um seguidor curando deixaria os outros parados.
- **`bc_farm` E APP NUNCA JUNTOS.** Conta farmando a cave não aparece na escolha
  do time e não é convocada. Convocar arrancaria a conta do meio de uma run
  (teleporte gasto, boss vivo) — run perdida em silêncio.
- **A ESCOLHA DO TIME MOSTRA SÓ QUEM DÁ PARA CONVOCAR** (07/09/2026). Fica de
  fora quem está **inativa**, com **outra função** (BC, HH ou o **APP próprio**)
  ou **já no time de outro líder**. Esconder quem tem o APP marcado NÃO impede
  montar time: o seguidor roda com a caixa "Ativar Modo APP" **dele** desmarcada
  — é a convocação que o faz rodar (`_SupervisorDaConta._lider_do_time`), e
  candidata com a caixa marcada é conta que já trabalha por si. A regra mora num lugar só, `_App._candidatas_do_time`: a tela
  recebe o motivo pronto, não três campos para remontar. A **contagem** do que
  ficou de fora vai junto — conta que some sem explicação é o usuário procurando
  uma conta que ele sabe que cadastrou.
- **QUEM JÁ ESTÁ NO TIME APARECE SEMPRE, e HABILITADO** — inelegível ou não. A
  tela grava o que está marcado: esconder o que está gravado apagaria o login de
  `time_logins`, e travar marcado tiraria do líder a única forma de removê-lo. O
  motivo fica à vista, em âmbar.
- **SAIR DO TIME POR `bc_farm` NÃO APAGA O LOGIN** de `time_logins`. O clique é
  reversível; apagar configuração por causa dele, não.
- **CAMPO NOVO DO `AppConfig` PRECISA ENTRAR NO `_app_from_dict`** — vale para
  `time_logins`/`time_modo` como para qualquer outro (travado por
  `tests/test_config_ida_e_volta.py`).
- **`time_modo` fora de `MODOS_DO_TIME` nunca entra**: a normalização é feita
  nos DOIS lados (leitura do config e ponte web), como o piso de 100 ms.
- **O TAB NÃO EXISTE PARA TROCAR DE ALVO, e sim para conseguir um.** Ele sai
  quando FALTA alvo: o mob caiu (saiu de batalha), não há id, ou a memória não
  responde. Ter alvo e não estar em batalha **não** é motivo — a luta pode
  ainda não ter começado. Rede de segurança contra o mob inalcançável:
  `VOLTAS_SEM_BATALHA_PARA_TROCAR`. Vale COM e SEM time.
- **Nos modos `copiar` e `largada` a volta do time é CEGA**: TAB → macro e nada
  mais. Sem conferir alvo no meio, sem cortar a volta na saída de batalha. Não
  é só simplicidade: a sincronia só se sustenta se a volta de todas as contas
  durar o MESMO tanto, e cada conferência acrescenta tempo a uma e não às
  outras. No `mesmo_alvo` as conferências ficam — é a morte do alvo que faz o
  líder virar a volta e o time pegar o mob seguinte junto.
- **Cada comparação de `TARGET_ID` no alinhamento vai para o log.** É a única
  via de descobrir por que o alinhamento falha; o valor comparado é o de
  `TARGET_ID_ADDR` (`core/target_hybrid`), lido da memória de cada cliente.
- **O SEGUIDOR NÃO DORME O DELAY DELE** — só o piso. Quem dá o ritmo é a marca
  da linha do líder. Dormir o próprio delay ALÉM de esperar a marca é o que
  fazia a defasagem ser preservada volta após volta (medido: 13 s estáveis).
- **A marca é comparada com `>=` sobre `(época, volta, linha)`** — marca já dada
  não faz esperar. É isso que faz o atrasado alcançar em vez de travar.
- **O teto do alinhamento tem de caber DENTRO do teto da largada.** Ele é
  derivado, não escrito à mão: com o alinhamento maior, o líder desiste antes
  de o seguidor alinhar e o modo `mesmo_alvo` nunca cumpre o que promete.
- **No `mesmo_alvo` o TAB de abertura da volta é VETADO** — ele trocaria o alvo
  que a largada acabou de alinhar.
- **`esperar_a_largada` devolve `False` SÓ para parar de verdade.** "Não
  consegui sincronizar" é sempre "vai assim mesmo" -- sincronia nunca derruba
  a macro nem cancela uma volta.
- **TODA espera da sincronia tem TETO**, e estourar o teto não cancela nada:
  quem não chegou segue batendo sozinho e entra na próxima largada.
- **A eleição do líder temporário é DETERMINÍSTICA** (maior `max_hp`; empate
  ou memória muda, ordem do login). Cada conta decide na própria thread: um
  sorteio daria respostas diferentes e o time teria DOIS líderes anunciando.
- **O número de volta comparado é o DO LÍDER** (`volta_do_time`), nunca o
  contador local de cada conta — eles divergem assim que alguém perde uma
  largada.
- **Os tempos da sincronia são PROVISÓRIOS** (`bot/app/sincronia.py`), por
  decisão do usuário: rodar primeiro, medir pelos logs depois. Todo número lá
  é declarado como provisório e a classe registra o que a medição precisa.
- **O MURAL MORA EM UM LUGAR SÓ** (`bot/mural.py`). Ele é o quadro de avisos
  entre as contas do MESMO processo, e é usado pelo time do jogo (BC) e pelo
  time do APP. Duplicá-lo cria dois dicionários de batidas: o reseter bate num
  e o farm consulta o outro, e a conta espera para sempre na porta da cave sem
  erro nenhum. Travado por `tests/test_ecossistemas.py`.
- **Os três quadros do mural compartilham um lock de propósito** — convite e
  aceite são as duas pontas da MESMA conversa. Separar os mutexes muda a
  exclusão mútua entre elas sem alterar função nenhuma.
- **A PyQt6 NÃO conhece o time** (congelada em 27/08/2026). A exceção é uma
  lista fechada em `tests/test_app_config_campo_por_campo.py`
  (`CAMPOS_SO_DA_WEB`) — não é permissão para novos campos ficarem fora da GUI.

- **`TARGET_ID` EM ZERO NO MEIO DA MACRO CORTA A VOLTA.** Zero é o jogo dizendo
  "não há nada selecionado" — o mob morreu e o cliente limpou o alvo, ele sumiu
  de vista, ou uma janela roubou a seleção. As linhas que sobram sairiam para o
  vazio. Conferido a CADA linha, porque é a leitura mais barata do bot (~1 µs).
  `None` não corta: sem leitura o modo cego roda a macro inteira, como sempre.

## A Fada — `docs/decisoes/fada.md`

A conta marcada como `Fada` que, **em time**, cura em vez de atacar. Fora de um
time a flag não faz nada.

- **A VÍTIMA AVISA, a Fada não adivinha.** Quem lê a vida é o próprio
  personagem, pela memória. A Fada nunca decide quem curar olhando barra de
  tela.
- **ALVO ALIADO NÃO É ALVO.** A tecla de auto-seleção deixa a conta com ELA
  PRÓPRIA selecionada, e a regra "TAB só quando falta alvo" via um alvo
  válido: a conta nunca mais TABava e rodava a macro contra nada (medido em
  campo, 01/09/2026). Toda conta EM TIME pergunta ao mural se o alvo atual é
  de alguém do time — e, se for, TABa. Fora de time a pergunta não existe.
- **DEPOIS DA AUTO-SELEÇÃO, TAB.** O id é publicado e o alvo é largado no
  mesmo passo. Publicar sem largar é deixar a conta presa em si mesma.
- **QUEM IDENTIFICA A VÍTIMA É O SLOT**, lido da memória — o `TARGET_ID`
  publicado é REDE, não portão. Ele só recusa a cura quando existe E não
  bate (aí há prova de que o clique pegou outra pessoa). Exigi-lo para curar
  fez a Fada clicar 357 vezes sem curar ninguém: portão que falha fechado é
  pior que portão nenhum.
- **ELA VOLTA AO PONTO ONDE COMEÇOU** (07/09/2026). A Fada não anda sozinha,
  mas é ARRASTADA: a cura em grupo tem alcance e seguir o time que avança a
  tira do lugar seguro. O ponto é a **primeira posição lida** quando ela
  começa — não há waypoint fora da cave. A conferência tem cadência
  (`fada_ociosa.SEGUNDOS_ENTRE_CONFERENCIAS_DO_PONTO`) e a mecânica é a MESMA
  do APP (`core/volta_ao_ponto.py`).
- **ANDAR EXCLUI SENTAR, e sentar exclui andar.** A tecla de sentar
  interrompe a ordem de andar do minimapa, e a Fada senta a cada giro por
  desenho — então, enquanto ela está voltando ao ponto, o descanso e os
  cuidados de ociosa NÃO acontecem. A marca de "estou indo" dura a cadência
  inteira; sem isso ela mandaria andar e se sentaria 0,1 s depois.
- **ANDAR SÓ COM A FILA VAZIA E FORA DE BATALHA** — o mesmo lugar do laço em
  que ela cuida do pet e da bolsa, e pelo mesmo motivo.
- **NENHUMA VÍTIMA LEVA MAIS QUE `MAXIMO_DE_TENTATIVAS_POR_VITIMA` CLIQUES.**
  A contagem é POR VÍTIMA, e quem estoura sai da fila e se vira com poção.
  Sem esse freio, qualquer defeito de seleção vira centenas de cliques — e
  o personagem sai andando.
- **A LEITURA DO ALVO SÓ VALE ~150 ms DEPOIS DA AÇÃO.** Medido: 36 a 123 ms
  entre o clique e a memória virar. Perguntar antes disso lê o alvo ANTERIOR.
- **A FADA FICA FORA DA LARGADA**, da macro e da sincronia. Contá-la como
  membro trava o time esperando uma confirmação que nunca vem.
- **AS DUAS BARRAS SÃO A RÉGUA ÚNICA, seja qual for o método.** A primeira diz
  QUANDO precisa de cura (Fada ou poção, tanto faz); a segunda, QUANTO precisa
  atingir para voltar a rodar a macro. Em time valem as do LÍDER; fora de time,
  as da própria conta. A constante fixa de 30% deixou de mandar.
- **A VÍTIMA SENTA NO PONTO INICIAL para esperar a Fada, e NÃO LEVANTA.** Antes
  ela esperava de pé, puxando mob.
- **SENTAR NÃO É UMA TRAVA — o bot SÓ SENTA, nunca aperta a tecla para
  levantar.** Sentado o personagem ataca e age livremente; o estado sai sozinho
  na primeira ação, e o que ele faz é AUMENTAR a regeneração base de vida e de
  mana (regra do jogo, usuário, 01/09/2026). Levantar é pior que inútil: perde a
  regeneração, e como a tecla é interruptor pode SENTAR o personagem na hora de
  reagir. A única leitura de `is_sitting` que sobrou serve para não apertar a
  tecla com ele já sentado. O porquê, e o erro que se repetiu duas vezes, em
  `docs/decisoes/cura-no-app.md` (seção "O bot SÓ SENTA").
- **TENDO FADA DE PÉ, ELA É A ÚNICA FONTE DE CURA DO TIME.** A poção só volta
  quando ela para de bater no mural.
- **A BATIDA SAI DE TODA ESPERA**, não só do topo do laço. Ela ficava só lá, e
  a Fada não volta ao topo enquanto cura: a vítima via 5 s de silêncio e bebia
  poção **enquanto estava sendo curada** (medido em campo, 6 s entre as duas
  linhas do log). Se ela está esperando, está viva — e é a espera que prova.
- **BOLSA E PET SÓ COM A FILA VAZIA E FORA DE BATALHA**, e com CADÊNCIA — não
  a cada giro do laço. A condição é conferida antes de CADA um dos dois, e não
  só na entrada: abrir o inventário com alguém esperando cura mata o alguém.
- **SEM TECLA DE PET, NEM PET NEM BOLSA.** Fada sem pet não cata item, então
  não tem lixo para apagar. Uma condição só porque é a mesma causa.
- **ANTES DE SENTAR, PERGUNTA À MEMÓRIA — e vale para todo lugar que senta.**
  A tecla é INTERRUPTOR: apertá-la com o personagem já sentado o faz LEVANTAR.
  Controle interno não basta, porque ele descreve o que o BOT fez e não o que
  aconteceu: um golpe levanta o personagem sem passar pelo bot, e um relogin
  devolve o estado sem avisar. Já sentado ⇒ não faz nada. Sem leitura, o
  controle interno é tudo o que há.
- **A FADA NÃO FAZ SHUFFLE ANTI-AFK.** Ele mora no executor de macro, e ela
  não roda o executor. A ausência é deliberada: ela passa a sessão parada.
- **EM BATALHA ELA CUIDA DE SI**, não da fila: seleciona-se e cura até sair.
  O time só protege quem está atacando, e quem espera cura não está — a
  proteção com que ela contava não existia na hora em que ela precisava. Quem
  avisa o time é a BATIDA, que carrega o estado de batalha junto.
- **QUEM ESPERA CURA VOLTA À MACRO enquanto a Fada estiver em batalha.**
  Atacando, o time mata o que está batendo nela — é a forma mais rápida de ela
  voltar a curar.
- **MORTO NÃO É CURADO** e para de rodar o APP (só em time). A Fada ignora e
  segue para o próximo.
- **O PONTO INICIAL DO TIME É O DO LÍDER** — isto INVERTE a regra anterior, e a
  inversão tem trava: só adota se estiver no MESMO MAPA. `_voltar_para_base`
  anda pelo minimapa, e destino fora do raio útil vira clique na borda: no mapa
  errado o personagem anda contra a parede indefinidamente.
- **A GEOMETRIA DO PAINEL É DERIVADA**: primeiro retrato em (28,204) e um passo
  fixo. Nunca cinco literais soltos. O painel encolhe por baixo, e quantos
  slots varrer é "membros − ela" — mas quem confirma é a memória, não a conta.

## HH (Black Wind Camp Dungeon) — `docs/decisoes/hh.md`

> **Terceiro ecossistema, aberto em 01/09/2026.** Integração do bot de terceiros
> em Lua/UoPilot (`OutrosBots/HH - cave full - ARVV3N`). O **porquê** de cada
> item, incluindo o que daquele bot foi REPROVADO, está em
> `docs/decisoes/hh.md`.

### O que NÃO pode ser violado

- **`hh/` NUNCA importa de `bc/` nem de `app/`**, e o contrário também não.
  Travado por `tests/test_ecossistemas.py`, que agora cruza TODOS os pares de
  ecossistema — pasta nova ganha as verificações de graça.
- **TODO IMPORT RELATIVO TEM QUE APONTAR PARA ALGO QUE EXISTE** (02/09/2026,
  `test_todo_import_relativo_aponta_para_algo_que_existe`). É a trava que faltava
  para o refactor de pastas: o teste acima só pergunta *"importa de outro
  ecossistema?"*, e um import que aponta para o VAZIO não cita ecossistema
  nenhum. **Medido:** o `cd2ef2b` subiu `bc/ui_service.py` para
  `bot/ui_do_jogo.py` levando junto um `from . import mapa_bc` escrito dentro de
  uma função — na casa nova o `.` virou `bot/`, onde `mapa_bc` não existe. Como
  o import era LOCAL, o módulo carregava, o bot arrancava e a suíte passava; o
  erro só nascia quando o personagem chegava no ponto e ia clicar num NPC.
  Resultado no log de 02/09: **42 `cannot import name 'mapa_bc'` seguidos** em
  `ENTRAR_NO_COVIL` — o bot dizia "Usando o Altar Stone para entrar no covil" e
  estourava 1 ms depois, sem soltar o clique direito. `sair_da_cave` e a entrada
  da HH usam a mesma função e estavam quebradas do mesmo jeito, ainda sem
  ninguém ter visto. O mesmo teste achou um segundo caso na mesma hora:
  `vendedor.py` com `from ...core.vision` (um nível a mais, sobra da subida de
  `bc/vendor.py`).
- **QUEM SOBE PARA `bot/` PERDE O DIREITO A `mapa_bc`.** `bot/` serve todos os
  ecossistemas: reapontar aquele import para `bc/mapa_bc` teria consertado o
  sintoma e criado a dependência que a pasta existe para proibir. O certo era o
  `core` — `mapa_bc.distancia` já era só um reexport de `core.rota.distancia`.
- **NADA é recriado.** Diretiva do usuário (01/09/2026): *"tudo que já existir no
  nosso BlazesBot você não precisa recriar, apenas utilizar onde necessário."*
  Combate, navegação, painel de arredores, venda, catador, deletador, pet,
  esconder jogadores, time e mural JÁ EXISTEM — a HH usa, não reescreve.
- **Os 66 waypoints são o único ativo insubstituível.** Vieram do bot Lua que
  roda esta cave hoje, em produção. Travados por `tests/test_mapa_hh.py`:
  contagem por trecho, continuidade, clique calibrado em todos, e o ponto de luta
  igual ao último waypoint do trecho.
- **O `via` (clique calibrado) é RESERVA, nunca via principal.** Quem anda é o
  motor de navegação, que calcula a partir da posição ATUAL e sabe destravar. Um
  clique fixo foi calibrado numa posição e, usado de outra, aponta para o lugar
  errado. Ver `core/rota.py`.
- **A área interna da HH está medida em 2 dos 66 waypoints**; o resto vale o
  marcador `AREA_INTERNA_NAO_MEDIDA`. Medidos em 03/09/2026, nos prints do
  usuário: `Happiness Hall Dungeon` em (55,33) e `Happiness Hall Main Hall` em
  (529,118) — e eles provam que **o interior NÃO é uma área só**. Quem depender
  de área tem de tratar a ausência; nome novo só entra junto com a linha que diz
  de que print ele saiu, e o inventário (`mapa_hh.areas_medidas()`) é travado
  por `test_a_area_interna_continua_marcada_como_nao_medida`. Consequência
  prática, inalterada: a retomada de rota da HH volta ao waypoint mais próximo e
  **não** recua para o início da área — recuar sobre um marcador devolveria o
  personagem ao waypoint 1 da cave a cada escorregão.
- **`Memory.location()` NÃO distingue dentro de fora da HH.** Ele devolve
  `Black Wind Camp Dungeon` nos dois lados — medido no log de 03/09/2026, 673
  menções e uma única string. Os nomes `Happiness Hall *` são rótulo da **TELA**
  (`ROTULO_DE_TELA_DA_CHEGADA`, `AREA_DA_SAIDA`) e **não podem ser comparados**
  com o que o ponteiro devolve. Travado por
  `test_os_nomes_de_Happiness_Hall_sao_da_TELA_e_nao_do_PONTEIRO`.
- **A ETAPA DA VIAGEM SAI DE NOME + COORDENADA** (`mapa_hh.etapa_pelo_lugar`),
  e a divisão é fixa: a **coordenada** responde "dentro ou fora", o **nome**
  responde "quão longe da cave, do lado de fora". Nenhum dos dois sozinho — o
  nome não separa dentro de fora, e a coordenada não separa as etapas de fora
  porque o teleporte da Fay espalha o ponto de chegada. Lugar desconhecido cai
  em `ETAPA_LONGE` (viagem completa): "não sei" custa uma viagem, nunca um
  clique no lugar errado.
- **"Estou dentro" é respondido pela COORDENADA, não pelo nome do lugar**
  (`mapa_hh.esta_dentro_da_hh`: X e Y positivos). É o que o bot em Lua já fazia
  e o que o usuário confirmou em 03/09/2026 — e é obrigatório, porque o interior
  tem mais de um nome de área. O par de chegada é sempre **(55,33)**, padrão do
  jogo.
- **OS TEMPLATES DA ENTRADA ESTÃO PRONTOS** (03/09/2026) e moram em
  `data/templates/` — não em `entrada/`, que é a pasta de EVIDÊNCIA. Falta um
  só: `link_sell_item.png`, e sem ele apenas a VENDA recusa.
- **Template tem que ser RECORTE, não tela.** O primeiro `link_enter_hh.png`
  entregue tinha 1029×804: um template do tamanho da tela casa em qualquer lugar
  e não localiza nada. Travado por
  `test_o_template_e_um_RECORTE_e_nao_uma_tela`.
- **A CÂMERA vai para a pose padrão antes de todo clique posicional** — preparo
  da run, cada trecho de waypoints, a ida da Fada à porta e a ida ao vendedor.
  Os `via` calibrados de cada waypoint foram medidos nessa pose, e é nas curvas
  onde o cálculo falha que eles entram.
- **A coordenada de link de diálogo NÃO transfere entre NPCs.** Medido:
  o `vendor_sell_tab` da BC cai 35 px abaixo do "Sell Item" do vendedor da HH,
  porque a posição dos links depende de quantas linhas o NPC escreve antes deles.
  Link de diálogo se acha por IMAGEM — `_onde_clicar_no_link_de_vender` é gancho.
- **`Happiness Hall` é o nome da INSTÂNCIA, não do lugar.** A zona é
  `Black Wind Camp Dungeon`, que é o que a memória devolve. Confundir os dois
  faria a validação de lugar rejeitar a leitura.
- **A HH e a BC nunca rodam juntas.** O despacho é `APP → HH → BC`, com ordem
  fixa: marcar as duas roda a HH, e o log diz isso. Ligar a HH com o BC rodando
  devolve o controle no próximo ponto seguro.
- **O destino do Fay é `West Suburb of Stone City`, e ele SÓ APARECE ROLANDO a
  lista.** A rolagem é um PASSO conferido pelo aparecimento do link — nunca um
  número fixo de cliques na seta. Clique cego na seta é o vício do bot Lua.
- **Não se clica de fora do ponto de conversa.** O painel de arredores caminha
  até PERTO da `Mutual Quest Woman` (-358,-289); a conversa é em (-342,-288). É o
  mesmo defeito já medido na BC em 25/08/2026, quando o clique a 2 passos pegou o
  White Eagle.
- **O ÚLTIMO PASSO ATÉ UM PONTO DE CONVERSA É PELO MINIMAPA, NÃO PELO PAINEL**
  (14/09/2026, `UIService.garantir_coordenada_da_entrada`). A entrada da BC era
  a única que corrigia o desvio **repetindo o painel de arredores**, com a
  justificativa de que ele *"comprovadamente pousa no ponto certo"*. **A medição
  derrubou isso:** no log ele pousou FORA **34 vezes** — de 4 a 12 unidades,
  mediana **6**, contra `TOLERANCIA_DO_NPC_DA_ENTRADA = 2` —, e em 2 delas as
  três tentativas se esgotaram sem corrigir; o usuário achou o bot parado sem
  conseguir entrar. Repetir o painel é repetir a ferramenta que acabou de errar.
  - **A outra razão daquela decisão CONTINUA válida** e é o que define o
    remédio: *"caminhar por coordenada usa clique no chão, que é o que desloca o
    personagem"*. Por isso a correção **não** é clique no chão —
    `encostar_no_ponto` anda pelo **minimapa** (`nav.goto(usar_mapa=False)`),
    que é ordem de andar, não clique na cena 3D.
  - **É a peça que o altar, a saída, a Fay e o vendedor já usam.** A Fay tem o
    defeito IDÊNTICO documentado desde 25/08: *"o painel caminha até PERTO, ele
    aceita folga por construção"*. A entrada era a que faltava.
  - **O painel fica como RESERVA**, para quando o personagem está longe de
    verdade — ali o minimapa iria clique por clique.
  - `TENTATIVAS_DE_ENCOSTAR_NA_ENTRADA = 2` (um clique de minimapa alcança ~17,6
    unidades e o pior caso medido foi 12) e `TETO_POR_TENTATIVA_NA_ENTRADA = 2.5`
    — TETO, não gasto: quem encerra é a chegada. Travado por
    `tests/test_coordenada_exata_da_entrada.py`.
- **A cave PRECISA de reset** (regra do jogo): sem desfazer e refazer o time os
  bosses não renascem. Dois modos: **HH solo** (igual à BC — reset aceita, o farm
  entra, o time é desfeito) e **HH + Fada** (as duas entram, a Fada acompanha e
  cura, e o desfaz-refaz acontece FORA, depois de sair).
- **A CONTA de reset é UMA por conta logada, e não uma por cave**
  (`AccountSettings.reset_nick`, 08/09/2026). O que é da HH é o MODO (solo ou
  fada). Dois campos criavam três estados impossíveis, e um deles custou uma HH
  rodando sem time em laço — ver `docs/decisoes/reset-de-time.md`, Decisão 8.
- **A HH NÃO ENTRA com o reseter offline**: trava no `_garantir_o_time`, depois
  de conferir o time e antes do convite. É a MESMA trava do BC
  (`bot/espera_do_reseter.py`) — o que é de cada cave é ONDE ela fica. Entrar
  sem reset joga fora o teleporte, a travessia e a run inteira.
- **A Fada é uma peça só, em `bot/fada.py`.** Ela cura de onde está e não sabe
  andar. Quem viaja, entra na cave e segue o líder é `bot/hh/fada.py`, que a
  COMPÕE: um giro do laço de cura (`_uma_volta`) é chamado de dentro do laço de
  seguir. **As duas na MESMA volta** — dois laços concorrentes na mesma conta
  seriam duas mãos no mesmo teclado.
- **No modo HH+Fada, o ciclo de time é do LÍDER.** A Fada só acompanha. Duas
  contas decidindo desfazer o mesmo time é uma corrida cujo resultado é um time
  desfeito no meio da cave.
- **A tecla de SEGUIR nasce vazia**, porque o cliente não tem atalho padrão para
  o follow. Vazia = não configurada: a Fada avisa uma vez e continua curando de
  onde está. Chutar um padrão faria ela apertar algo que faz outra coisa.
- **O vendedor é o `Roaming Apothecary`, fora da cave** — a venda da BC com outro
  NPC. Isso é dado de rota, não módulo de venda novo.
- **O CLIQUE DIREITO DA SAÍDA TEM ANEL DE TENTATIVA** (`hh.md` §30,
  `core/halo.py`): a mira medida primeiro e, só se ela falhar, os oito vizinhos
  a 14 px. **Duas travas obrigatórias:** para no diálogo aberto (senão clica
  dentro dele) e para assim que a POSIÇÃO muda (clique no chão faz o personagem
  andar, e o vizinho seguinte já vale para outra cena). Ligado só na SAÍDA —
  uma vez por run; na rajada de entrada seria multiplicar o que já funciona.
- **VENDER E ENTRAR SÃO DOIS PONTOS** (`hh.md` §29): vende-se parado em
  `PONTO_DA_VENDA` (−343,−294) e entra-se de `PONTO_DA_ENTRADA` (−342,−288), a
  ~6 unidades. **Depois de vender, VOLTA para a entrada** — `tentar_entrar_na_hh`
  recusa o clique de fora dela, e sem a volta a rajada inteira passa sem um
  clique sair. O clique direito no vendedor (`coords.hh_vendor_npc`) foi medido
  DO PONTO DA VENDA: os dois números andam juntos e nenhum se ajusta sozinho.
- **A VENDA TEM DOIS GATILHOS, E A BOLSA NÃO É UM DELES** (`hh.md` §27): a
  **largada** (na porta, uma vez por vez que o farm é ligado, incondicional) e a
  **cota de runs** (`hh.vendor.runs_before_selling`, na `MANUTENCAO`). Leitura de
  quantidade de item na bolsa INFORMA (log e diagnóstico); não DECIDE.
- **A ordem é VENDER e depois DELETAR**, nos dois momentos (`hh.md` §25 e §27):
  a venda tira o volume maior de uma vez, e a deleção — que é item a item por
  template — varre uma bolsa curta.
- **A HH vende pelo SLOT DA HH** (`hh.vendor.sell_start_slot`), entregue por
  `VendedorDaHH._config_da_venda`. `ctx.settings.vendor` devolve o da BC, e ler
  dali fazia a HH vender pelo número da outra cave (`hh.md` §28). A proteção dos
  itens bons é GEOMÉTRICA: slot errado vende o EQUIPAMENTO.
- **Sem a janela de venda LOCALIZADA na tela, não se clica na grade.** Tendo o
  template da âncora e não a achando, `_ponto_do_slot` devolve `None` e a venda
  encerra: o clique cairia na cena 3D e faria o personagem ANDAR para longe do
  ponto de onde os cliques no vendedor funcionam. Sem o template, segue pelas
  coordenadas calculadas — aí não há o que perguntar.

#### Decisão de cave NÃO mora em código compartilhado (06/09/2026)

> **Regra do usuário:** *"tem decisões que só servem para um, mas para o outro
> não, então vão ter funções que até podem ser compartilhadas, mas tem funções
> que não devem ser compartilhadas"*.

- **NO BC NÃO SE DESMONTA ANTES DO WAYPOINT DOS GUN WITCH.** No caminho do
  covil os mobs são para **ignorar**. Travado por
  `tests/test_montaria_do_bc_no_caminho.py`.
- **FORA DE COMBATE E SEM MONTAR HÁ 10 s: O BOT ANDA 6 UNIDADES** (06/09/2026,
  `_passo_para_destravar_a_montaria`). Relato do usuário: *"às vezes ao tentar
  ativar a montaria o jogo fica cancelando sozinho... o fato de andar desbuga
  esse problema"*. **Medido:** dos 26 episódios de "Montaria confirmada depois
  de Ns insistindo" (mediana 40 s), **23 tinham combate** — já cobertos por
  `limpar_o_combate` — e **3 não tinham**: 9 s, 13 s e 35 s. O de 35 s é o
  retrato: parado em (423, 53), dentro da cave, fora de combate, 35 s de tecla
  sem efeito, e então a montaria sobe sozinha. Insistir mais não resolve — a
  tecla já saía a cada `INTERVALO_REMONTAR`; faltava mudar o ESTADO.
  - `SEGUNDOS_ANTES_DE_CUTUCAR = 10.0` e `PASSO_PARA_DESTRAVAR_A_MONTARIA = 6`,
    os dois números do usuário. O passo é minúsculo de propósito: ~17,6 unidades
    é um clique de minimapa e 7 é a tolerância do waypoint — **6 cabe DENTRO da
    tolerância** e não tira o personagem do ponto.
  - **UM passo por intervalo, não um por ciclo** — passo demais tira do ponto e
    o remédio vira o problema. **A direção GIRA** (`BUSSOLA`): sempre para o
    mesmo lado, uma parede faria todo passo falhar calado.
  - **EXIGE `in_battle() is False`**, confirmação POSITIVA e não `is not True`:
    andar puxa mob, e em combate quem resolve é o golpe. "Não sei" mantém o
    comportamento antigo (insistir na tecla).
  - **O passo é CONFERIDO** (`_clicar_offset_e_verificar` mede a posição antes e
    depois), não é clique no escuro. Travado por
    `tests/test_passo_para_destravar_a_montaria.py`.
- **ATRIBUTO COM NOME DE MÉTODO APAGA O MÉTODO** (06/09/2026). `Navigator.
  __init__` guardava `self._dentro_da_cave = False` e depois nasceu um método
  homônimo: `self._dentro_da_cave()` virava `False()` — **55 `TypeError` no
  log**, derrubando `CURAR` e `ATE_O_ALTAR` para `RECUPERAR` sempre que o portão
  chegava no ciclo de `CICLOS_ANTES_DE_IR_A_PE`. O atributo era escrito e nunca
  lido. Travado genericamente por `tests/test_init_nao_sombreia_metodo.py`, que
  cruza por AST os `self.X = ...` do `__init__` com os métodos da classe.
- **UM GANCHO POR PERGUNTA, NÃO POR FUNÇÃO.** `destravar_o_combate` e
  `matar_quando_o_trajeto_trava` chamam a MESMA função (`limpar_o_combate`) e
  mesmo assim são dois, porque respondem a perguntas diferentes:

  | gancho | pergunta | quem liga |
  |---|---|---|
  | `destravar_o_combate` | *"não consigo MONTAR porque estou em batalha"* — matar é a única saída, o jogo recusa a montaria em combate | **as duas** caves |
  | `matar_quando_o_trajeto_trava` | *"estou montado, andando, e sem progresso"* — matar é **escolha** | **só a HH** |

- **GANCHO DE POLÍTICA NASCE DESLIGADO.** Foi por não ser assim que o BC
  regrediu: em 04/09 a matança da HH entrou direto no laço de deslocamento
  compartilhado, e em 06/09 o log da fase `ENTRAR_NO_COVIL` mostrou
  *"Desmontando antes da luta de destravar (andar até (242,22))"* seguido de
  *"NÃO DESTRAVEI em 60s: 9 morte(s), 8 TAB, 176 golpes"* — sessenta segundos
  e nove mobs, a pé, num corredor que era para atravessar.

#### Navegação presa — vale para as DUAS caves (`navegacao.md`, 04/09/2026)

- **MANOBRA QUE ANDA ZERO UNIDADE NÃO É MANOBRA.** O destravamento descarta o
  candidato que já está dentro da tolerância de chegada, e devolve `None`
  quando não sobra nenhum. Fingir sucesso ali zerava o contador de travas do
  chamador e produziu **4 min 10 s** num ponto só. A régua do filtro é a mesma
  da tentativa (`_tolerancia_do_candidato`) — nunca duas cópias.
- **SEM PROGRESSO E EM BATALHA: MATA.** O jogo prende o personagem em combate e
  nenhum clique de minimapa resolve. `destravar_o_combate` deixou de ser só do
  portão da montaria. Matar vem **antes** do teto e da manobra: matar é
  continuar, e a HH tem mobs a matar junto com os bosses.
- **FICAR PRESO TEM PRAZO: 30 s** (`TETO_PRESO_NO_MESMO_PONTO`). Conta só tempo
  inútil — matar e avançar zeram o relógio. Estourado, o controle volta para a
  rotina: enquanto a navegação insiste, o `_guard()` não roda, e Parar e
  watchdog ficam sem resposta.
- **O PONTO DO BOSS É O FIM DO CAMINHO DE CADA TRECHO.** Os dois são declarados
  separados e já divergiram (04/09: um waypoint comentado, o ponto apontando
  para ele). A diferença coube na tolerância e o defeito não apareceu como
  erro — apareceu como o bot insistindo num waypoint que não existia mais.
  Travado por `test_o_ponto_do_boss_e_o_FIM_do_caminho_de_cada_trecho`.

#### O que a sessão de 04/09/2026 fixou — o porquê medido em `hh.md` §13

- **`FarmDesligado`, `StopRequested` e `Disconnected` são tratados ANTES do
  `except Exception`** no laço da HH. Ordem de `except` aqui é semântica: o
  geral na frente engoliria os três sinais que não são defeito. `Disconnected`
  pode ser capturado, mas só para `raise` seco.
- **Nenhum clique de entrada sai depois de o personagem já ter entrado.** O par
  de cliques não é atômico (180–420 ms de espera do diálogo no meio), e dentro
  da cave o mesmo ângulo é o NPC de SAÍDA — o bot entrava e saía na mesma volta.
  A conferência é ENTRE os dois cliques (`ainda_vale`), não só antes do par.
- **TODO ESC DO BOT PASSA POR `largar_a_mira`** (07/09/2026). ESC sem mira abre
  o **MENU DO SISTEMA**, e ele atravessa a run: **os 3 episódios de "saída da
  cave travada" que o log mostra por inteiro foram TODOS precedidos, ~2,5 min
  antes, por `_travar_no_alvo_proibido` apertando ESC às cegas** no waypoint dos
  guardas. A janela sobreviveu à luta do boss e engoliu o clique direito no
  Skull Herald — **305 cliques que não abriram o diálogo** contra 267 saídas
  concluídas. A trava existia desde 06/09 e este chamador tinha ficado de fora,
  e era justamente o que aperta no instante em que o alvo pode ter acabado de
  sair. Travado por `tests/test_janela_na_saida.py`.
- **CLIQUE ENGOLIDO É EVENTO DE JANELA, E O GUARDA VALE PARA OS SEIS PARES**
  (`INTERVALO_DO_GUARDA_DE_JANELA = 3.0`). `desobstruir_a_cena` existia e era
  chamada em UM lugar só — a entrada. Agora o funil
  (`_clicar_no_npc_e_no_link`) limpa a cena **quando o diálogo não abre**, então
  a tentativa seguinte encontra a tela limpa: cobre link da cave, Altar Stone,
  saída, Rich e a entrada da HH de uma vez.
  - **NA FALHA, e não antes do clique**: `desobstruir_a_cena` documenta que o
    guarda é POR EVENTO e não por clique, porque a disputa da entrada dispara
    dois cliques por segundo. No caminho feliz não custa nada.
  - **ESTRANGULADO a 3 s**, porque janela não aparece sozinha: entre duas
    tentativas separadas por segundos nada mudou. Uma captura (~10 ms) a cada
    3 s é 0,3% do trecho, contra uma por tentativa.
  - **O guarda da entrada continua onde estava** — antes da rajada. O novo é a
    segunda linha de defesa.
- **NÃO SE CHEGA NO WAYPOINT DO BOSS COM A MIRA PRESA** (02/09/2026,
  `combate.largar_a_mira`, chamado no fim de `_do_guardas`). O cadáver do último
  Gun Witch fica selecionável por 7 a 13 s (medido), então `target_id != 0` na
  saída da fase é o caso NORMAL, não a exceção. **O ESC SÓ SAI COM ALVO
  CONFIRMADO NA MEMÓRIA** — sem mira o ESC abre o MENU do jogo, e menu aberto
  engole o clique na cena 3D (`docs/decisoes/janela-na-frente.md`).
  `id_do_alvo() is None` ("não sei") **não aperta nada**. Teto de
  `TENTATIVAS_DE_LARGAR_A_MIRA = 2`, porque o ESC também fecha janela aberta;
  `TETO_PARA_A_MIRA_CAIR = 0.60` é o mesmo teto medido das ações de UI do
  cliente. Falhar **não trava a run**: registra e segue. Roda DEPOIS de
  `curar_antes_do_boss` (que pode sentar) e FORA do `if/else`, para cobrir também
  o desfecho que não fechou pela flag. Travado por `tests/test_largar_a_mira.py`.
- **O NOME DO ALVO NÃO É CONFIÁVEL O BASTANTE PARA SER JUIZ ÚNICO** (auditado em
  02/09/2026 sobre 1.160.883 linhas de log). Das 1.390 leituras do portão de
  nome: **701 `ilegivel` / `lido=nada` (50,4%)**, 619 `'Gun Witch'`, 62
  `'Cemetery Guard'`, 7 `'Blaze Skull Marshal'` — e **uma leitura corrompida,
  `'PDtery Guard'`**, que é `'Cemetery Guard'` com os dois primeiros bytes
  trocados. Três consequências:
  - **Filtro estrito de nome ("só ataca se ler o nome certo") está PROIBIDO.**
    Com metade das leituras ilegíveis ele para o golpe em metade dos ciclos —
    exatamente o defeito medido em 26/08 ("sobrou 1 Gun Witch de pé e o bot
    parado") que `SO_O_ALVO_PROIBIDO_PARA_O_GOLPE` corrigiu.
  - **A TELA continua como reserva do alvo proibido** (`cemetery_guard.png`).
    Tirá-la deixaria a trava cega em metade das leituras. Duas fontes que falham
    por motivos diferentes é a única redundância que vale algo.
  - **A leitura corrompida é o achado mais grave**: não é uma falha, é uma
    string plausível e ERRADA. Ela desqualifica igualdade de nome como veredito
    único, e é por isso que o portão compara por `in` e trata `[]` como
    `ilegivel` em vez de "alvo errado".
- **O TAB É CONFIRMADO PELA TROCA DO ID, NÃO POR SLEEP** (06/09/2026,
  `core/target_hybrid.esperar_o_alvo_trocar`). Era `press(0,15) + tick(0,6)` =
  **750 ms fixos por morte, com o laço inteiro parado** — nenhuma skill sai ali.
  Medido em 274 mortes do log: mediana de 760 ms da detecção até o TAB, **204
  delas (74%) entre 0,70 e 0,85 s**, ou seja exatamente `press + tick`. Agora
  pergunta de 10 em 10 ms e devolve no instante em que o jogo troca o id.
- **A CARÊNCIA DE 2,4 s SÓ VALE QUANDO A TROCA NÃO SE CONFIRMA.** Ela nasceu de
  um problema de TELA ("o quadro do alvo novo leva um instante para desenhar");
  a leitura vem da MEMÓRIA desde 25/08 e o id já é conferido. Confirmada a
  troca, vale a **cadência normal (0,15 s)** — e **não zero**: zerar fazia a
  leitura seguinte sair no passo do laço (50 ms), e com uma leitura de morte
  presa em `True` isso queima TAB na velocidade do laço (medido no dublê: 12 TAB
  em 3 s). A trava por identidade de `MorteDoAlvo` barra o MESMO id, não uma
  pilha de cadáveres com ids diferentes.
- **A CARÊNCIA NUNCA PROTEGEU DE BATER NO CADÁVER** — não olhar não é proteger.
  Quem protege é a trava por IDENTIDADE. Confundir as duas foi o que manteve
  2,4 s de cadáver na mira, que é o "stuck on corpse" relatado.
- **AS DUAS HIPÓTESES SOBRE O PONTEIRO ESTÃO REPROVADAS** (bancada de ponteiros,
  01/09/2026, `Teste-Ponteiros/RESULTADOS.md`): o HP **não** congela no último
  valor (nome e vida vêm 321/321 e 361/361 quando o alvo é reconhecido) e a
  morte **não** desaloca a instância — o oráculo varreu 912 MB de heap nos 6
  casos de falha e achou o objeto **em 6 de 6**, com `hp=0/100` legível no
  cadáver. Frase do relatório: *"a detecção de MORTE sempre funcionou. O erro
  vive só no meio da luta."*
- **Cave sem alvo proibido é caso legítimo.** `NOME_DO_ALVO_PROIBIDO` nasce
  `None` e só a BC o preenche; sem nome, o veredito é `bate` e **não**
  `acabaram` — `acabaram` encerraria a luta na primeira leitura, sem um golpe.
- **Toda rotina com `Navigator` + `CombatEngine` LIGA `destravar_o_combate`.**
  Sem isso o portão da montaria detecta a batalha e só sabe insistir na tecla
  contra uma recusa do jogo. Custou 41 s à HH e 24 min à BC, em datas
  diferentes, pelo mesmo motivo.
- **Fora do ponto do boss e EM BATALHA: mata, não anda.** Voltar para
  `ATE_O_BOSS` exige montaria, e em batalha o jogo recusa montar — é beco sem
  saída. `in_battle() is True`: ilegível não autoriza sair batendo.
- **No meio da cave só a MONTARIA é garantida.** Buff, poção e comida exigem
  estar a pé, e a pé no meio da cave é o trem de mobs encostando. O portão é
  `acabei_de_entrar` (55,33 ± `rota.NA_ROTA`).
- **A saída não clica de fora do ponto.** (527,124) e clique (626,526),
  remedidos em 04/09 porque a montaria entrava na frente do NPC. Sete unidades
  de folga bastam para o clique pegar OUTRO NPC que fica por perto.

#### O que a sessão de 03/09/2026 fixou — o porquê medido em `hh.md` §12

- **FORA DA CAVE NÃO SE PREPARA NADA QUE EXIJA ESTAR A PÉ.** Buff, poção e
  comida de pet moram em `PREPARAR_DENTRO`. Regra do usuário, e é a mesma que a
  BC segue desde 25/08/2026: montado o jogo IGNORA a tecla sem devolver erro, e
  entrar é disputado — durante a espera o personagem regenera de graça. **A
  única exceção é o PET**, conferido uma vez ao CHEGAR na porta, e **fora** do
  laço de tentativas (a rajada pode dar centenas de leituras por minuto).
- **A COMIDA DO PET É A SEGUNDA EXCEÇÃO, E TEM PRAZO** (13/09/2026). Ela espera
  o `PREPARAR_DENTRO` como todo o resto — mas só até 15 min de atraso
  (`LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS`). Passado isso é dada ONDE O BOT
  ESTIVER, pagando o desmonte. Medido: 46 min presos em `ATE_A_PORTA` deixaram o
  pet da `creubo` 77 min sem comer num intervalo de 50, e ele quase sumiu. Ver a
  seção "Pet (obrigatório)" e `docs/decisoes/comida-do-pet.md` §II.
- **O PET é conferido nos DOIS lados da tela de carregamento** — na porta e no
  preparo de dentro. A repetição é de propósito: é ali que ele some.
- **A CURA TEM TRÊS MOMENTOS, e só três:** a entrada (`curar_ao_entrar`), o
  top-up antes de encostar em cada boss (`curar_antes_do_boss`), e a
  emergência. Sentar entre os bosses foi REMOVIDO — era o terceiro no mesmo
  ponto, e sentar já tinha sido medido e reprovado na BC.
- **PARA CURAR TEM QUE ESTAR FORA DE BATALHA, e a saída é MATANDO**
  (`limpar_o_combate`). Escolha do usuário entre pular, esperar e matar. A
  emergência usa `potions.emergency_pct`, **não** o limiar normal: os mobs da HH
  são fracos e o normal faria a run passar o tempo bebendo. Não sair de batalha
  no teto **não trava** — a cura fica para a volta seguinte.
- **A NATUREZA DE CADA PONTO MORA NO MAPA, e a rotina obedece.** Não pode haver
  `if rotulo == "..."` na rotina. Pontos 1 e 3 são pacotes de mobs **ranged**:
  sem AoE (a skill de área é de curta distância e passa embaixo deles) e com o
  ritual `limpar_o_combate`. Pontos 2 e 4 são boss, com AoE e
  `lutar_contra_um_boss`.
- **O TAB de um ponto tem UM dono.** Zero no pacote porque quem o dá é o próprio
  `limpar_o_combate`; zero no boss único porque trocar de alvo perde dano; dois
  na Dupla porque sem ele o segundo boss nunca é adquirido.
- **CINCO SEGUNDOS PARA ENGAJAR, em qualquer ponto de batalha — inclusive o do
  boss.** Não engajou, o bot segue. É o que torna barato refazer um trecho
  depois de uma morte. **Custo aceito pelo usuário e registrado:** um boss vivo
  que demore mais de 5 s é pulado, e o log diz isso em voz alta.
- **VOLTA-SE AO PONTO depois de matar.** Mob ranged não vem até o personagem, e
  começar o trecho seguinte fora do waypoint faz a retomada escolher índice
  errado.
- **O PROGRESSO DOS BOSSES É VOLÁTIL E ZERADO AO SAIR DA CAVE.** O desfaz-refaz
  do time ressuscita os quatro; lembrar entre entradas faria o bot pular sala
  cheia. Dentro da mesma ida, a retomada respeita o **trecho em andamento** — os
  quatro trechos se cruzam no mapa, e escolher pela distância refaria bosses já
  mortos.
- **CAIR NÃO PODE JOGAR FORA O PROGRESSO DA RUN.** `RECUPERAR` não zera o
  trecho; quem decide por onde continuar é `_retomar_dentro_da_cave`.
- **A RAJADA DE ENTRADA É A DO BC**: uma hora de teto, 25 ms entre tentativas,
  confirmação de 0,25 s, volta à coordenada ao derivar, e redescoberta do NPC
  **só** na falha mecânica (instância cheia é a razão normal de não entrar).
  Estourar o teto volta para `ATE_A_PORTA`, não para `RECUPERAR`.
- **SAIR DA CAVE É FALAR COM O `Servant Child`**, achando "Leave Happiness Hall"
  por template e confirmando pela POSIÇÃO (-342,-288). Andar até (529,119) e
  declarar a run concluída deixava o personagem dentro. Os três cliques cegos do
  Lua estão REPROVADOS: clique que erra o NPC cai no chão, e clique no chão faz
  o personagem andar para fora do ponto de onde o NPC é alcançável.
- **`WAYPOINTS_QUE_BLOQUEIAM` ≠ `WAYPOINTS_PROBLEMATICOS`.** O primeiro é sobre
  MOBS que barram a passagem (só (232,188) hoje, e só se limpa **se o combate já
  começou**); o segundo alarga a tolerância onde a geometria não deixa encostar.
  Valem para o mesmo ponto hoje, e é por isso que misturá-los seria fácil e
  errado.

### Promoções que a HH forçou — dependência cruzada

Mexer nestes mexe nos DOIS ecossistemas:

**MEXER EM QUALQUER UM DESTES MEXE NAS DUAS CAVES.** Todas feitas em
01–02/09/2026.

| módulo | veio de | o que NÃO subiu, e por quê |
|---|---|---|
| `core/rota.py` | `bc/mapa_bc.py` | as rotas em si (dados de duas caves diferentes) e o reconhecimento de lugar da BC (caixa da cave) |
| `core/stone_city.py` | `bc/mapa_bc.py` | o **Rich Man** — vendedor é escolha do ecossistema, não da cidade |
| `bot/navegacao.py` | `bc/navigation.py` | as rotas, as áreas apertadas, os textos de busca |
| `bot/ui_do_jogo.py` | `bc/ui_service.py` | quais NPCs, quais links, quais coordenadas |
| `bot/combate.py` | `bc/combat.py` | as FASES, a trava do Cemetery Guard, o Package Courage |
| `bot/vendedor.py` | `bc/vendor.py` | o Rich Man, a volta para a cidade (pedra/token), a compra de suprimentos |
| `bot/hotbar.py`, `bot/velocidade.py` | `bc/` | nada — subiram inteiros, sem alteração |
| `bot/fada.py` | `bc/`→ não: de `app/fada.py` | o DESLOCAMENTO — esta Fada cura de onde está; quem viaja e segue é `bot/hh/fada.py` |

### O CRITÉRIO, e ele é uma pergunta só

*O que este módulo IMPORTA?*

- não importa nada de `bot/` ⇒ cabe no **`core/`** (`rota`, `stone_city`);
- recebe `BotContext` ⇒ vai para **`bot/`**, porque `core/` importar de `bot/`
  inverteria a dependência e tiraria a reusabilidade do core.

**"Parece genérico" NÃO é o critério.** O relatório inicial da HH mandou
navegação, combate e UI para o `core/` exatamente por esse raciocínio, e estava
errado — os três recebem `BotContext`. Ver `docs/decisoes/hh.md`, seção 8.0.

### Como um ecossistema pede um dado da cave a um motor compartilhado

**INJETA, nunca importa.** Travado por
`test_o_sistema_nao_depende_de_ecossistema_nenhum`, que reprova qualquer arquivo
de `bot/` que importe de `bc/`, `app/` ou `hh/`. O supervisor é a única exceção,
porque ESCOLHER qual ecossistema roda é a função dele — e um segundo teste trava
essa lista em um nome só.

Três formas, todas em uso:

| forma | exemplo | quando |
|---|---|---|
| o mapa no construtor | `Navigator(ctx, mapa_hh)` | o motor pergunta uma coisa ao mapa (`tolerancia_do_waypoint`) |
| atributo de classe | `NOME_DO_ALVO_PROIBIDO` | a resposta é um dado, e `None` é resposta válida |
| gancho com padrão neutro | `_esta_fora_da_cave()`, `_no_ponto_do_vendedor()` | a resposta exige lógica; o padrão nunca bloqueia |

E o padrão neutro é regra: **"não sei" não bloqueia.** Não curar dentro da cave
mata o personagem; um desmonte a mais fora dela custa alguns segundos.

### A armadilha da reexportação — medida, não teórica

`from ..combate import USAR_IMAGEM_DA_FASE_2` **copia o valor no import.** Trocar
o interruptor no motor não chega ao ecossistema, e ele segue com a cópia, em
silêncio. Foi o que `test_desligado_nao_le_a_tela` pegou: a leitura de tela
desligada no motor continuou acontecendo.

**Interruptor entra QUALIFICADO POR MÓDULO** (`combate.USAR_IMAGEM_DA_FASE_2`),
para existir um valor só. A forma `X as X` só vale para nome que não muda em
tempo de execução — classe, função, constante de dado.

**`core/` vs `bot/` não é escolha de gosto.** `core/rota.py` é função pura sobre
coordenadas e cabe no `core/`. Navegação, combate e UI recebem `BotContext`, que
mora em `bot/` — pôr no `core/` inverteria a dependência e tiraria a
reusabilidade do core, e `tests/test_ecossistemas.py` reprova. `bot/` é a camada
que o `CLAUDE.md` já define como *o SISTEMA — serve todos os ecossistemas*.

**Cada mapa injeta seus dados, a regra é uma só.** `mapa_bc.onde_retomar` e
`mapa_hh.onde_retomar` são invólucros de uma linha sobre `core.rota.onde_retomar`.
A BC passa `AREAS_APERTADAS`; a HH **não passa**, porque a área dela é marcador —
e mandar o bot voltar ao início da área sobre um marcador o devolveria ao
waypoint 1 da cave a cada escorregão.

## Fechar painel dentro do jogo — `docs/decisoes/memoria-primeiro.md`

Vale para qualquer ecossistema que decida limpar a tela do jogo.

1. **NUNCA aperte ESC uma quantidade fixa de vezes.** O ESC **alterna**: com
   painel aberto ele fecha, com a tela **limpa** ele **ABRE o menu do sistema**
   — medido seis vezes seguidas, sempre o mesmo nó (`0` ↔ `0x15142AB0`). Um
   "aperta 3× para garantir" deixa o jogo pior do que achou.
2. **PERGUNTE depois de cada tecla** — `Memory.algum_painel_aberto()` — e pare
   no instante em que ela devolver `False`.
3. **`False` NÃO prova tela limpa.** É sinal de **uma via**: `True` é certeza,
   `False` é "nenhum dos quatro sinais acusou". Quem tratar esse `False` como
   prova volta a errar calado, que é o defeito que a memória vem eliminar.
4. **`system_menu_open()` NÃO vê o menu do ESC** — diz `False` com ele aberto.
   Não use esse leitor para concluir nada sobre o menu do sistema.

## Estado atual relevante — as REGRAS

Cada item é o que **não pode ser violado**. O detalhe de cada área mora em
`docs/REGRAS.md`; o porquê medido, em `docs/decisoes/`.

### Pet (obrigatório)

- Verificado e invocado **NO INÍCIO** de cada execução de farm BC (após venda
  inicial, antes do loop). `ensure_pet()` também roda no PREPARAR e após reviver.
  Respeita `settings.pet.summon_on_login` (padrão True).
- Alimentação respeita `feed_on_start`: False (padrão) ⇒ cronômetro inicia sem
  alimentar. O estado é UM número, `PetFeeder.vence_em`, que começa em `None`
  (grade não iniciada) e **não** em `0.0` (que seria "venceu em 1970"). Ele
  sobrevive a reinício em `PetConfig.proxima_comida_em`, gravado pelo próprio
  `PetFeeder` a cada mudança — inclusive quando a grade apenas NASCE.
- **A FOME É DERIVADA DA GRADE, NUNCA UM SEGUNDO ESTADO.** Não existe
  `pet_needs_food` guardado e não deve existir: `com fome == agora >= vence_em`,
  e isso já fica *latched* sozinho até alguém alimentar. As leituras do laço
  (`esta_com_fome`, `atraso_minutos`, `a_fome_e_urgente`) são **PURAS** — não
  mutam a grade e não gravam em disco, porque rodam num laço de até 20 voltas por
  segundo. Quem MUTA é só `deve_alimentar` (faz a grade nascer) e
  `registrar_alimentacao`.
- **A COMIDA É CONFERIDA A CADA VOLTA DO LAÇO, NOS TRÊS ECOSSISTEMAS**
  (13/09/2026). HH e BC por `CombatEngine.cuidar_da_comida_no_laco`, que só age
  depois do prazo e **fica em silêncio quando não vai agir** — falar a cada volta
  inunda o log, e foi por isso que a versão antiga da linha da BC ficou
  comentada. O APP alimenta na primeira volta calma e, no ramo de batalha,
  **acusa** em vez de forçar (`_avisar_se_a_comida_esta_presa`).
- **A ESPERA PELO LUGAR CERTO TEM PRAZO** (`LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS`
  = 15 min). Até lá a comida espera o preparo de entrada; passado o prazo ela é
  dada ONDE O BOT ESTIVER, furando o veto de desmonte fora da cave
  (`_preparar_para_agir(..., mesmo_fora_da_cave=True)`). Buff e poção **não**
  ganharam essa saída — adiar os dois não custa o pet.
- **A BATALHA NUNCA CEDE, nem com a comida atrasada.** Em combate o jogo ignora a
  tecla, e apertá-la faria o `PetFeeder` registrar uma refeição que não houve.
  `in_battle()` é tri-estado: só `True` barra.
- **A COTA DIÁRIA É GARANTIDA PELO PRAZO, não pela sorte.** 28,8 refeições/dia
  com intervalo de 50 min só fecham porque o atraso nunca alcança um intervalo
  inteiro — é aí que `registrar_alimentacao` re-ancora a grade e a refeição do dia
  some. Daí os dois lados do número: **abaixo** de `PET_FEED_MINUTOS_MIN` (40) e
  **acima** da cauda normal das janelas (p90 = 10,8 min em 128 janelas medidas).
  Ver `docs/decisoes/comida-do-pet.md`.
- **Trava de posição no APP** (`AppConfig.travar_posicao`, padrão True): salva a
  posição como base; andou > `TOLERANCIA_POSICAO` (1) ⇒ devolvido andando pelo
  minimapa. Só com memória respondendo.
- **O ID PUBLICADO MORRE COM A SESSÃO** (04/09/2026, `mural.esquecer_id` em
  `_release`). `mural._IDS` é dicionário de módulo e sobrevive ao relogin; a
  entidade, não. **Id velho é pior que id nenhum**: a Fada compara o id novo do
  jogo com o velho do mural, conclui que clicou na pessoa errada e descarta a
  vítima certa. Sem id ela confia no slot do painel, que é a regra do usuário.
- **A ESPERA PELA FADA TEM TRÊS SAÍDAS, E NENHUMA É ETERNA** (04/09/2026):
  a Fada AVISA que desistiu (`fada_desistiu_de` ⇒ poção), o teto de 60 s
  (`TETO_DA_ESPERA_PELA_FADA` ⇒ poção) e **entrar em batalha sentada ⇒ voltar à
  macro** (não é poção: é parar de apanhar de graça). A marca da desistência
  **não pode ser apagada no `pedir_cura`** — a desistência já removeu o pedido,
  então a republicação da vítima chega lá igual a um pedido novo, e limpar ali
  reabre o laço desistir/re-pedir.
- **A BATIDA DA FADA TEM VALIDADE, E TAREFA LONGA AVISA ANTES** (04/09/2026).
  `bater_fada(..., vale_por=)`; nunca encurta os 5 s padrão, nunca passa de
  `TETO_DA_BATIDA_LONGA` (15 s), e ao terminar a tarefa ela bate de novo com a
  validade normal para o aviso não sobrar. Sem isso, a limpeza de bolsa (teto de
  10 s) fazia o time inteiro dar a Fada por morta e beber poção com ela viva ao
  lado. **A batida sai também do topo de `_uma_volta`** — é o único ponto por
  onde passam os dois chamadores (o `rodar()` do APP e o laço da HH).
- **A FADA PERCEBE A PRÓPRIA QUEDA COMO QUALQUER OUTRO MODO** (04/09/2026).
  Janela morta no fim de `rodar_a_fada` ⇒ `Disconnected` ⇒ relogin e Histórico
  de Quedas, igual ao `_rodar_modo_app`. E `_montar_a_fada` **captura
  `Disconnected` e relança ANTES** do `except Exception` — engolir a queda ali
  deixava a Fada da HH acompanhando o líder com a janela fechada.
- **MEXEU NO `web/`, RODE `npm run build`** (04/09/2026). A janela do bot abre
  **`dist/index.html`**, que é o Vite compilado — editar `web/index.html` sem
  compilar não muda nada do que o usuário vê, e **nenhum teste reclamava**.
  Medido no campo `revive_skill`: campo no HTML, mapeado no `main.js`,
  transportado pela ponte nos dois sentidos, suíte inteira verde — e a aba
  Teclas na tela continuava sem ele. Travado por
  `test_o_dist_COMPILADO_tem_o_campo` (pula quando não há `dist/`, porque ele é
  gerado e ignorado pelo git).
- **TIME DESFEITO NO JOGO ⇒ A CONTA VOLTA À POÇÃO** (07/09/2026). O jogo desfaz
  a party sozinho quando todos morrem, e nada no bot era avisado: a vítima
  esperava o teto inteiro por uma cura que sem painel não tinha como sair. A
  prova é `Memory.tamanho_do_time()` (conta o próprio personagem: **≤ 1 é sem
  party**), conferida **antes de publicar o pedido** no mural. `None` **não**
  desliga a Fada — só o ponteiro CONFIRMANDO derruba a dependência. Isto é
  contingência, não conserto: **recriar a party continua pendente**.
- **NO REVIVER, QUEM MANDA É O SLOT — NÃO O ID** (06/09/2026). O retrato do
  morto continua clicável, mas o clique **não põe o id dele no `TARGET_ID`**;
  exigir que batesse reprovava a única coisa que ia funcionar (medido: a Fada
  desistiu em 2 s e a vítima queimou 58 s de prazo). O id continua sendo lido e
  vai para o log como diagnóstico. **Na CURA o id continua vetando** — lá o alvo
  está vivo, o clique seleciona, e é ele que impede curar o aliado errado.
- **A JANELA DO REVIVER É DE 10 s, COM NO MÁXIMO 3 TOQUES**, e o morto que não
  levanta **continua na fila** — o prazo dele é de 60 s, e largar no primeiro
  ciclo desperdiça 50. O teto de toques é cinto de segurança contra o laço de
  357 cliques de 01/09/2026, não sobre tempo.
- **A FADA REVIVE, E A CURA VEM PRIMEIRO** (04/09/2026, `bot/fada_reviver.py`).
  O morto só fura a fila dos feridos depois de `SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA`
  (40 s) — antes disso a cura tem prioridade, porque morto não apanha e tem
  prazo próprio. **Ela avisa no mural que começou a conjurar ANTES de apertar**,
  e **a vítima sai da fila dos mortos no instante em que fica de pé** — os dois
  lados desse contrato existem para o feitiço de 5 s não ser desperdiçado.
  Valem as mesmas regras da cura: id que não bate não revive, freio de 3
  tentativas, mana conferida antes do toque, sem tecla avisa uma vez e segue.
- **A BOLSA: PERGUNTA-SE SE ABRIU, E SÓ SE FECHA O QUE A TELA DIZ ESTAR ABERTO**
  (07/09/2026). A espera cega de 0,58 s custou **268 limpezas seguidas perdidas**
  em duas contas, com zero itens apagados; e o `finally` apertava a tecla
  incondicionalmente — sendo ela um interruptor, os toques se anulavam em pares.
  Ícone ausente no teto ⇒ **não se aperta de novo**: o que não está aberto não
  precisa ser fechado.
- **A MORTE É A PRIMEIRA PERGUNTA DA VOLTA** (07/09/2026), antes de pet, comida,
  trava de posição, bolsa e aquisição — e continua sendo conferida por linha.
  Só dentro das linhas ela era inalcançável: morto não adquire alvo, a volta
  abortava na aquisição, e uma conta ficou **96 minutos morta** apertando TAB
  sem o ciclo disparar.
- **MORTE EXIGE DUAS LEITURAS SEGUIDAS DE `hp == 0`.** Uma amostra não basta:
  zero aparece transitoriamente em troca de mapa, carregamento, respawn e
  leitura de ponteiro inconsistente. `None` continua valendo NÃO nas duas.
- **O APP RECONHECE A PRÓPRIA MORTE** (04/09/2026, `bot/morte.py`). `hp == 0`
  lido da memória, conferido **a cada linha** junto do alvo zerado — antes disso
  a macro seguia apertando tecla contra um cadáver, e no log de 7 h de duas
  contas de APP não havia UM evento de morte. Sem leitura, **não há morte**:
  cego não declara morte, senão pararia a macro de uma conta viva.
- **O CICLO DA MORTE TEM ORDEM FIXA:** avisa o time → espera a Fada no máximo
  `PRAZO_PARA_A_FADA` (60 s) → clica o "Ok" do jogo → senta e regenera → volta ao
  ponto pelo `Navigator`. **Sem Fada no time (ou sendo eu a Fada), revive na
  hora** — não há por que esperar. **Feitiço em curso ESTICA o prazo** (a skill
  tem 5 s de preparo; sem esticar, a vítima se auto-revive no meio dele e a
  mana da Fada vai fora).
- **OS DOIS "Ok" FICAM A 133 px UM DO OUTRO, E O ERRADO CUSTA O SPOT.** O do
  convite da Fada teleporta para ela; o do jogo revive no lugar cobrando mais
  Exp. Por isso o convite é o **único** ponto do ciclo decidido por IMAGEM
  (`convite_reviver.png`, limiar 0.9) e o clique sai **onde o template casou**,
  nunca numa coordenada fixa.
- **TRÊS MORTES SEGUIDAS SEM VOLTAR AO PONTO PARAM A CONTA.** É "seguidas", não
  "no total": voltar zera o contador. Sem ele, um spot que virou armadilha vira
  um moedor de tentativas a noite toda.
- **O ALVO CAÍDO CORTA A VOLTA, E A ORDEM É: SAÍDA DE BATALHA, DEPOIS HP**
  (06/09/2026). *"Se ainda diz 'mob vivo' mas saiu de batalha, é porque a
  leitura está errada e o sair de batalha manda mais, pois garante que não tem
  ninguém batendo no personagem"* — por isso `_a_batalha_acabou` é conferida
  ANTES de `_o_alvo_caiu_pelo_hp`. Inverter a ordem põe uma leitura ruim de HP
  na frente da prova forte.
- **DENTRO DA VOLTA, A PERGUNTA SOBRE O ALVO É SÓ DE MEMÓRIA.**
  `_o_alvo_caiu_pelo_hp` lê `hp <= 0` e nada mais; **HP ilegível NÃO VOTA**.
  `_alvo_morreu` (o veredito completo, da aquisição) continua PROIBIDO no laço:
  ele cai na cascata da TELA quando o HP falta, e a tela custa uma captura por
  consulta — travado por `tests/test_laco_simples_do_app.py`.
- **CAIU O ALVO, A SAÍDA DE BATALHA É CONFIRMADA ATIVAMENTE POR ATÉ 2 s**
  (`SEGUNDOS_PARA_CONFIRMAR_A_SAIDA`). Sai no instante em que a flag baixa;
  estourar o teto **não é fracasso**, é o outro desfecho útil: quer dizer que há
  outro mob batendo, e aí o bot volta a atacar em vez de sentar, andar ou abrir
  a bolsa.
- **O TAB QUE NÃO RESPONDE TEM DE FALAR, E DIZER QUAL DAS DUAS CAUSAS É**
  (06/09/2026). "A tecla não pega" e "não há mob ao alcance" produzem o MESMO
  silêncio no `TARGET_ID` e pedem consertos opostos; só `core/vizinhanca.py`
  separa as duas. Há mob por perto ⇒ **ERROR** (a tecla não chega, ou eles estão
  fora do alcance do TAB); nenhum mob ⇒ **WARNING** de spot vazio. O aviso
  **rearma a cada minuto** — medido: duas contas ficaram 96 e 212 minutos
  apertando TAB sem uma linha no log, porque o aviso saía uma vez por sessão e a
  linha "não trouxe mob vivo" era suprimida justamente quando o TAB emudecia.
- **NADA RECUSA UM ALVO VIVO POR DISTÂNCIA** (HOTFIX de 06/09/2026, com conta
  morta). O TAB do jogo entrega o mob **mais próximo primeiro** e vai afastando
  a cada toque: recusar o primeiro empurra a seleção para fora, e o bot acaba
  correndo até um mob distante com meia dúzia de outros atrás. **O primeiro
  alvo vivo que o TAB traz é, por construção, o melhor que existe** — procurar
  outro é o próprio dano. `core/coleira_do_ponto.py` virou MEDIÇÃO; se um dia
  houver régua de novo, ela não pode ser feita de recusa (recusa custa TAB, e
  TAB custa distância) — teria de perguntar ANTES do TAB, varrendo
  `entidades_vivas()`.
- **O RELÓGIO DO TIME NÃO TROCA ALVO BOM.** O pedido de TAB dos 4 s
  (`conferir_a_parada`) passa por `_tenho_alvo_vivo()` antes de virar tecla: com
  alvo vivo selecionado, ele é descartado. `_mesmo_alvo_verificado` já deveria
  barrar, mas depende do registro da aquisição — alvo herdado de outra volta
  escapava.


## Espera ativa — `docs/decisoes/espera-ativa.md`

- **TODA espera COM observável passa por `core/espera.ate`**: a pergunta é de
  quem chama, o laço/teto/passo/Parar/telemetria são do orquestrador. Quem não
  tem o que perguntar usa `ctx.tick` e assume por escrito que espera cego.
- **`None` NÃO é "não aconteceu"** — é "não dá para saber" (cliente minimizado,
  sem template, memória ilegível). Tratar os dois igual faz toda volta ir até o
  teto.
- **Espera sem teto nenhum levanta `ValueError`.** Um dos dois — tempo ou
  voltas — é obrigatório.
- **O número de esperas CEGAS pode cair, nunca subir**
  (`tests/test_catraca_da_espera_cega.py`, linha de base de 11/09/2026: 250).
  A catraca também APERTA: converteu uma, baixa o número no mesmo commit.

## Telemetria de latência — `core/cronometro.py`

- **NÃO SE CRONOMETRA NADA ABAIXO DE `PISO_PARA_CRONOMETRAR = 10 µs`.** Medir
  custa **+298 ns** por chamada (medido em 07/09/2026, 200.000 repetições, esta
  implementação): 30% num alvo de 1 µs, 3,0% em 10 µs, 1,2% em 25 µs. Daí
  `Memory.read_int` (~1 µs documentado) **não** ser instrumentado — custaria 30%
  da operação mais repetida do bot para medir o que já se sabe. Quem quer o
  custo da leitura mede a leitura COMPOSTA (`alvo_atual`, `snapshot`).
- **NÃO EXISTE ESCRITA POR CHAMADA.** Cada medição soma num acumulador em
  memória e uma thread solta despeja UMA linha por nome a cada
  `INTERVALO_DE_DESPEJO = 30 s`. Cem mil medições viram **uma** linha — e a
  linha diz mais que as cem mil (n, mínimo, média, máximo). O motivo é medido:
  em 06/09 uma única mensagem gerou 531.411 linhas e 290 MB em 48 minutos.
- **DESLIGADO CUSTA ZERO, não "quase zero"**: baixado o interruptor
  `TELEMETRIA_LIGADA`, `@cronometrar` devolve a **função original**, sem
  embrulho. Um `if` dentro do wrapper custaria a chamada extra que a medição
  acima cobra.
- **O ACUMULADOR É POR THREAD.** `ac.n += 1` não é atômico entre threads e um
  `Lock` no caminho quente pagaria mais que a medição. Por thread resolve os
  dois — e o despejo já sai separado por conta.
- **O LOG É SEPARADO E NÃO PROPAGA** (`logs/latencia/`, `propagate = False`).
  Misturar com o log de dev empurraria a evidência de defeito para fora da
  janela curta dele (4.000 linhas). A retenção, a compressão e o arquivo morto
  são REUSADOS de `core/log_limitado.py`, não reescritos.
- **TELEMETRIA QUE DERRUBA O BOT É PIOR QUE TELEMETRIA NENHUMA**: o laço do
  despejo engole exceção, e exceção no bloco medido é **medida e sobe**.
- **O PACOTE INTEIRO É MEDIDO, mas o embrulho SE APOSENTA**
  (`core/instrumentacao.py`, 07/09/2026). Pedido do usuário: *"em todos os
  módulos, funções e laços, para que mesmo o que já esteja testado e
  documentado seja retestado"*. São **1.631 funções**; embrulhar todas de forma
  permanente deixaria o bot mais lento para descobrir que ele está lento. Então
  cada embrulho mede `AMOSTRAS_PARA_DECIDIR = 20` chamadas e, se a média ficou
  abaixo do piso, **devolve a função original no lugar dela**. O CENSO FICA: a
  aposentada continua no relatório com o seu n, mínimo, média e máximo. Medido:
  **1.292 funções instrumentadas em 0,3 s**.
- **A INSTRUMENTAÇÃO TOTAL NUNCA ACONTECE NO IMPORT.** **56 arquivos de teste**
  leem `inspect.getsource` de métodos reais; um wrapper no lugar do método
  quebraria os 56 de uma vez. Quem chama é o supervisor, com o bot subindo —
  único ponto por onde todo ecossistema passa. Ficam de fora: o próprio
  cronômetro (recursão), geradores (mediria a criação, não a execução), dunder,
  `tools/` e `gui/`.
- **O RELATÓRIO ORDENA POR TOTAL, NÃO POR MÉDIA**
  (`python -m blazesbot.core.relatorio_de_latencia`). Uma função de 400 ms
  chamada 3× custa 1,2 s; uma de 0,4 ms chamada 20.000× custa 8 s — a média
  premia a primeira e é a segunda que decide a duração da run.
- Travado por `tests/test_cronometro.py` e
  `tests/test_instrumentacao_total.py`.

## O log de dev — `docs/decisoes/sistema.md`

- **RETENÇÃO DE 2 DIAS** (`DIAS_DE_ARQUIVO_MORTO = 2`, 06/09/2026). Era 7, e o
  motivo da mudança **não é disco, é a qualidade da resposta**: o log de dev é a
  fotografia do bot DE AGORA, e sete dias pressupõem código estável por sete
  dias. **Já custou um veredito errado** — uma auditoria do ponteiro de nome
  varreu os 7 dias (1.160.883 linhas) e deu "50,4% ilegível", mas os consertos
  `d9bc023` e `1a5b19c` entraram em 01/09 às 15:20 e 15:34: metade da amostra
  descrevia um bot que não existe mais. Refeita em 2 dias, a mesma medição deu
  **46,8%** (231 leituras). Diretiva do usuário: *"ter lixo ou informação que se
  tornou irrelevante atrapalha em vez de ajuda."*
- **A VARREDURA É PERIÓDICA, NÃO SÓ NO ARRANQUE**
  (`INTERVALO_ENTRE_LIMPEZAS = 3600`). Ela rodava uma vez por processo, no
  `__init__`, e o bot fica ligado por dias — a retenção existia no papel e não
  acontecia. Medido em 06/09: **324 MB** na pasta, 298 MB no arquivo do dia sem
  comprimir, o de ontem nunca comprimido e **cinco dias velhos** que já deveriam
  ter sido apagados.
- **A VARREDURA RODA NUMA THREAD DAEMON, FORA DO CAMINHO QUENTE.** `emit` roda
  com o lock do handler segurado: comprimir centenas de MB ali dentro pararia o
  log de TODAS as contas pelo tempo do gzip.
- **NUNCA SE COMPRIME O QUE AINDA RECEBE LINHA.** O arquivo de HOJE está fora por
  construção, e o de ontem só entra depois de
  `SEGUNDOS_DE_SILENCIO_ANTES_DE_COMPRIMIR = 60` — na virada da meia-noite ele
  pode receber a última anexação de uma poda começada antes das 00:00, e
  `_comprimir` copia e apaga o original.
- **QUEM DIZ DE QUE DIA É O CONTEÚDO É O NOME, NÃO O MTIME.** O mtime muda a cada
  anexação; um arquivo velho que recebeu linha hoje sobreviveria à retenção para
  sempre.
- Travado por `tests/test_retencao_dos_logs.py`.


## A tela de contas — `docs/decisoes/interface.md`

Reordenação por arraste, grupos do usuário, coluna Função e estados da linha.
Pedidos entre 28/08 e 06/09/2026.

- **A ORDEM DAS CONTAS É A ORDEM DO ARRAY `accounts`.** Não existe campo de ordem
  e **não pode existir**: seriam duas fontes de verdade, com a pergunta sem
  resposta "se discordarem, quem manda?". Reordenar é
  `BotConfig.reordenar_contas(uids)`, e `save()` grava.
- **A IDENTIDADE DA CONTA NA INTERFACE É `Account.uid`, NUNCA O ÍNDICE.** Com a
  tabela reordenável, escrita por índice grava **a senha na conta errada** —
  login quebrado e senha certa perdida, sem desfazer. A tela nunca recebe uid
  repetido (`garantir_uids_unicos`, na leitura do arquivo E antes de responder a
  lista): duas contas com o mesmo uid são indistinguíveis para ela.
- **REORDENAR NÃO PODE PERDER CONTA.** Desduplica por identidade de OBJETO, põe
  no fim quem a tela não citou, e **aborta** em vez de gravar lista menor.
- **`Account.grupo` É RÓTULO VISUAL.** **Nenhum caminho do bot pode ler dele** —
  travado por AST. Ordem, **time do APP** (`time_logins`, por login, no líder) e
  **grupo** são ORTOGONAIS; nenhuma deriva da outra.
- **O ARRASTE NÃO TEM DEBOUNCE.** Grava no soltar; se falhar, a tabela recarrega
  do backend — a tela nunca mostra ordem que o disco não tem. Debounce é o que
  perde a última alteração quando a janela fecha.
- **NA GUI A REORDENAÇÃO É POR BOTÃO.** A `QTableWidget` tem seis
  `setCellWidget`, e o arraste do Qt move os itens mas **não** os widgets de
  célula: a senha de uma conta ficaria na linha de outra.
- **UMA coluna "Função"**, não três de caixa: o rótulo tem de ficar DENTRO do
  controle. Selo é **só a sigla** (virão mais funções, e quem separava BC de HH
  sempre foi a sigla — dois pictogramas de caverna não se distinguem a 16px).
- **O `<input type="checkbox">` NATIVO fica**, escondido sob o `<label>` e nunca
  com `display: none` (tiraria do Tab). **Alvo de clique ≥ 24×24** — eram 14×14,
  quatro por linha.
- **QUATRO ESTADOS, QUATRO CANAIS**, porque coexistem: selecionada → BORDA;
  inativa → OPACIDADE; no ar → PONTO; ativa e parada → nada. `.linha-ativa`
  significa **selecionada**, não "conta ativa". **ZEBRA E CARDS SÃO PROIBIDOS**:
  zebra consome o fundo (canal de "selecionada") e card quebra o alinhamento
  entre contas, o arraste e o cabeçalho de grupo (`colspan`).
- **A COLUNA RUN SÓ SE PREENCHE PARA CAVE.** O APP é macro de teclado: não existe
  "run" ali. Conta parada mostra **vazio, não zero**.
- **O PONTO DE CONEXÃO É CONFERIDO, não deduzido.** "Estar na lista do resumo"
  não é "estar no ar": `conectada` passa por `IsWindow` (o handle fica em cache
  depois da janela morrer) e `relogando` exige `not stop_event.is_set()` —
  **encerrar de propósito não é queda**. Vermelho tem pulso mais rápido além da
  cor.
- **A SEGUIDORA DE TIME NÃO É "SÓ LOGIN"** — ela roda a macro do líder com
  `AppConfig.enabled` desligado. **Um líder que é ele próprio seguidor não lidera
  ninguém**: a cadeia tem de ser resolvida.
- **O ÍCONE DA BARRA DE TAREFAS EXIGE AppUserModelID**, não só `icon=`. O
  `webview.start(icon=)` aplica na JANELA (medido com `WM_GETICON`), mas sem
  `SetCurrentProcessExplicitAppUserModelID` o Windows agrupa sob o `python.exe` e
  usa o ícone DELE. Vai no **começo** do `run()`. O `.ico` é gerado em **DIB
  clássico** (o `System.Drawing.Icon` do WinForms é o consumidor mais restrito) e
  **sem 256** — nada na barra passa de 48.
- **O TOPO MOSTRA SÓ "BlazesBot".** O bot roda BC, HH e APP.
- **O APP ABRE `dist/`, NÃO `web/`** — e o `3-INICIAR-WEB.bat` não faz build,
  enquanto o backend é lido do código-fonte em toda execução. Alteração em
  `web/` sem `npm run build` põe o usuário rodando Python de agora com tela de
  horas atrás, e o defeito aparece como "funcionalidade que funcionava parou",
  sem nada errado no código. Travado por `tests/test_dist_atualizado.py`, que
  compara CONTEÚDO (as chaves de i18n do HTML), nunca data de arquivo.
- **TODO TOKEN DE FUNDO TEM VERSÃO CLARA.** Fundo sem versão clara é área da tela
  no tema errado, e o defeito é silencioso. Faltava `--color-cab`: a barra de
  título ficava escura no tema claro e os botões dela, que usam `--color-ink`,
  desapareciam. O **nome** usa `text-ink`, nunca `text-white`; o **ícone** não
  muda — ele é a identidade e tem contraste próprio nos dois temas.
- **A TROCA DE TEMA DESLIGA AS TRANSIÇÕES POR UM QUADRO** (`.trocando-tema`, e o
  handler a tira depois de DOIS `requestAnimationFrame`). Cor que vem de custom
  property e está numa lista de transições **fica presa no valor do tema
  anterior** — o Blink não reavalia. Medido: 200+ elementos. Nunca consertar isso
  tirando `color` de cada regra: a próxima regra nova nasceria com o defeito.
- Travado por `tests/test_ordem_e_grupo_das_contas.py` (30) e
  `tests/test_tabela_de_contas_visual.py` (25).

## A janela Editar — `docs/decisoes/interface.md`

Refatoração de 06/09/2026: exclusividade das funções, tooltip e altura das abas.

- **UMA CONTA TEM UMA FUNÇÃO SÓ.** BC, HH e APP são MUTUAMENTE EXCLUSIVAS:
  marcar uma **troca**, nunca soma. Não é regra de tela — quem impõe é
  `BotConfig.definir_funcao_da_conta`, o **único** ponto de escrita das três
  flags. `alternar_farm`/`alternar_hh`/`alternar_app` **não podem voltar**: em
  duas chamadas ("desliga BC", "liga HH") existe um instante com as duas ligadas,
  e o supervisor lê os campos a cada volta.
- **CONFIGURAÇÃO COM DUAS MARCADAS É INVÁLIDA, e sobe CORRIGIDA.** O critério é a
  precedência LEGADA (app > hh > bc) — a que o laço do supervisor já praticava —
  para o bot continuar fazendo exatamente o que fazia. Não é o laço que resolve
  em silêncio a cada ciclo: `from_dict` normaliza uma vez.
- **O CONTROLE DA TELA É RÁDIO, com `name` por conta.** Caixa comunica semântica
  falsa. Sem `name` único os grupos se misturam entre linhas.
- **"NENHUMA FUNÇÃO" É ESTADO VÁLIDO, e tem de ser ALCANÇÁVEL pela tabela.** A
  conta sobe, loga, reloga e não faz mais nada. Clicar no que já está ligado
  desliga — e esse clique se resolve **a partir do selo**: o rádio é escondido
  (`position: absolute; opacity: 0`) e quem o recebe é o `<span>` IRMÃO dele
  dentro do mesmo `<label>`. Rádio nativo não desmarca sozinho, e no rádio já
  marcado o `change` também não dispara: sem tratamento próprio, ligar o BC era
  uma porta sem volta. Na GUI, desmarcar a caixa manda `""`.
- **O ESPELHO AO VIVO TAMBÉM É EXCLUSIVO.** Ele corrigia BC e HH de forma
  independente, e com rádio isso **reintroduzia a função antiga a cada poll de
  1,5 s** — medido na tela.
- **TROCAR COM O BOT RODANDO É PERMITIDO, e AVISA o custo.** Trocar no meio de
  uma run da cave perde aquela run (teleporte gasto, boss vivo). Bloquear seria
  tirar uma função que o usuário usa; avisar deixa a decisão com ele.
- **O BALÃO DE AJUDA VIVE NO `<body>` E É POSICIONADO EM COORDENADA DE
  VIEWPORT.** `getBoundingClientRect()` já é relativa ao viewport e o balão é
  `position: fixed` — **somar `window.screenX`/`screenY` o joga para fora da área
  visível**. Ele grampeia nas quatro bordas (a janela é travada em 1200×800).
- **ALTURA DE PAINEL NÃO SE CALCULA À MÃO.** Nada de `calc(90vh - 160px)`: o
  painel é `flex: 1; min-height: 0` dentro de um flex de altura fixa. Cabeçalho,
  abas e rodapé são `shrink-0` — Salvar e Cancelar ficam acessíveis em qualquer
  aba.
- **O "?" ANCORA NO RÓTULO** (`absolute top-0 right-0`), não numa linha própria:
  em `flex-col` ele caía abaixo do input e gastava uma linha por campo.
- **O RÓTULO FICA EM CIMA DO CAMPO, NAS CINCO ABAS.** Em caixa alta pequena, e
  sem exceção — a grade de teclas já teve o rótulo ao lado, cortava 59px de
  altura e foi **reprovada pelo usuário** por ser a única aba com outro formato.
  Altura se ganha pela largura da coluna, que é invisível, não pelo formato, que
  é o que a pessoa vê.
- **RÓTULO É ELEMENTO, NUNCA NÓ DE TEXTO SOLTO.** Texto solto dentro de `.campo`
  não é selecionável em CSS: não recebe estilo, não trunca e não alinha.
- Travado por `tests/test_janela_editar.py` (16).
