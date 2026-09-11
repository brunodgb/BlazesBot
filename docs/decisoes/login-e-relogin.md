# Login e relogin — o ecossistema BASE

> A REGRA está no `CLAUDE.md`. Aqui fica a MEDIÇÃO que a sustenta.
> Leia antes de mexer em `login.py`, `login_states.py` ou `watchdog.py`.

## 18/08/2026 - a conta de APP que caiu e nao relogou

Relato: cinco contas cairam ao mesmo tempo. As quatro de BC fecharam a janela e
relogaram; a do APP ficou na tela com a caixa "Connection interrupted, please
open client again.", apertando teclas contra ela.

### A causa NAO era o template

Medido contra a captura daquela janela (`data/templates/entrada/queda-app.png`):

    state_conn_prefix       0.973   CASA   (limiar 0.80)
    state_conn_interrupted  0.936   CASA

E contra os 19 prints de queda reais em `logs/quedas/`, o mesmo template casa a
**0.98** em 17 deles, sempre em (384,186). O reconhecimento e solido.

### A causa era ninguem olhar

O modo APP e despachado no TOPO do laco de `_operate` com `continue`, entao o
`watchdog.check()` daquele laco **nunca era alcancado** enquanto o APP rodava. A
unica conferencia era `if not win32gui.IsWindow(self.hwnd)` DEPOIS de
`executor.rodar()` retornar -- ou seja, so pegava janela que ja tinha morrido.

Corroboracao independente: dos **19** prints em `logs/quedas/`, **nenhum** e de
conta APP. Nao porque nao caissem -- porque ninguem percebia.

### Por que a correcao nao foi dar o `BotContext` ao APP

`_rodar_modo_app` nao recebe o `BotContext` DE PROPOSITO: ele carrega o estado do
FARM, e e isso que faz o modo APP funcionar justamente quando a leitura de
memoria nao responde. O `Watchdog` precisa de um ctx.

Duplicar a regra nos dois lugares seria pior que o defeito -- duas definicoes de
queda divergem na primeira manutencao. Entao a regra foi extraida para
`watchdog.avaliar_saude(pid, hwnd, janela_existe, templates)`, que recebe PECAS.
Quem tem contexto (`Watchdog`) e quem nao tem (o modo APP) chamam a MESMA funcao.

A conferencia chega ao executor como FUNCAO INJETADA, no mesmo molde do pet e da
barra de atalhos -- o executor continua importando so `core.inputs`.

**Cadencia:** o teto de `VISUAL_CHECK_SECONDS` (10 s) vive fora da funcao, em
quem chama. Volta curta nao fotografa; volta longa fotografa na primeira
oportunidade. Mesmo custo do BC.

---

## 18/08/2026 - "nao reconhece o erro" era reconhecer o erro ERRADO

Medido com as quatro capturas em `data/templates/entrada/`:

| captura | prefixo generico | template especifico |
|---|---|---|
| `login-conn-failed.png` | **0.835** (1o da lista) | `state_conn_failed` **0.994** (4o) |
| `login-connecting.png` | **0.787** | `state_connecting` **0.997** |
| `login-ip-address.png` | - | `state_acquiring_ip` **0.997** |
| `queda-app.png` | **0.973** | - |

`state_conn_prefix` casa com a palavra "Connection", comum a "Connection
interrupted" E a "Connection failed". Sendo o PRIMEIRO da `_SIGNATURES`, ele
classificava a tela de FALHA como CONEXAO INTERROMPIDA.

**O estrago nao e o rotulo.** `_handle_conn_interrupted` clica no deslocamento do
botao **Ok**; essa caixa tem **Cancel**, em outro lugar. O clique cai no vazio e
o login fica parado indefinidamente -- o sintoma relatado.

E `login-connecting` marcava **0.787**, a **0.013** do limiar: uma renderizacao
um pouco diferente e ela cairia na mesma armadilha.

### Os botoes sao DIFERENTES, e isso e o que torna a confusao cara

    Connection interrupted        -> Ok
    Connection failed            -> Cancel
    Connecting to the server     -> Cancel
    Acquiring server IP address  -> Ok

### Templates novos, medidos

`state_connecting.png` e `state_acquiring_ip.png` (209x23), recortados das
capturas reais. Ambos marcam **0.997** na propria tela e no maximo **0.675** em
qualquer outra, sem nenhum falso positivo nos 19 quadros de queda. Vao de ~0.32
contra o limiar de 0.80.

O `state_acquiring_ip.png` ja tinha detector e handler prontos no codigo
esperando o arquivo (`OPTIONAL_TEMPLATES`) -- ganho de graca.

### A tela "Connecting to the server" e espera legitima

Palavra do usuario: *"e uma espera legitima, mas caso leve mais de 6 segundos,
pode clicar em 'Cancel', pois deve ter travado por causa do servidor do jogo."*
`SEGUNDOS_CONECTANDO = 6.0`. O `CANCEL_OFFSET_CONNECTING = (16, 142)` e medido:
o template casa (centro) em (495,222) e o centro do Cancel esta em (511,364) na
captura de referencia. A subtracao cancela a barra de titulo da captura.

---

## O UNICO motivo para matar uma janela do jogo

Parado na tela de usuario e senha por mais de `LOGIN_SCREEN_MAX_SECONDS` (150 s)
sem avancar.

**Isto REVERTE a decisao anterior**, que estava escrita no codigo: *"NAO fecha o
jogo. Antes isso levava a reabrir o cliente, e perder a janela custa horas de
fila. Recomeca a sequencia na MESMA janela."*

O que mudou o veredito: recomecar na mesma janela **nao tirava o cliente do
estado travado**. Ele fica parado ali indefinidamente e a conta nao volta. Uma
conta parada a noite inteira custa mais que a fila -- e a fila e um custo
possivel, nao certo.

Custo aceito explicitamente pelo usuario.

**O cronometro conta SO na primeira tela.** Avancou para lista de servidores ou
selecao de personagem, zera (`login_screen_since = 0.0` no `else` do laco). Era
exigencia do usuario: *"tem que ser 2,5min na tela de colocar usuario e senha,
que e a primeira tela."*

---

## O BACKOFF QUE NUNCA ZERAVA (26/08/2026 -- defeito, nao ajuste)

O laco de sessao sempre foi infinito, e isso esta certo: conta ativa tem que
estar logada, custe o tempo que custar. O que estava errado era o **backoff**.

```python
# supervisor.py, AccountSupervisor.run(), ANTES
attempt = 0
while not self.stop_event.is_set():
    try:
        self._run_session()
        self._status("Rotina concluida")
        return                      # <- o corpo do try SEMPRE termina aqui
    except Disconnected:
        attempt += 1
        ...
    else:
        attempt = 0                 # <- INALCANCAVEL
```

O `else:` de um `try/except` so roda quando o corpo do `try` **nao levantou** --
e aqui, quando ele nao levanta, ele **retorna**. Aquele `attempt = 0` era o unico
zeramento depois da inicializacao, e nunca executou uma vez sequer.

### O que isso custava

`backoff_delay(attempt, cap)` e `min(2 ** (attempt - 1), cap)`, com
`relogin_backoff_cap = 300`. Como `attempt` so crescia pela vida inteira da
thread:

| quedas acumuladas | espera antes do relogin |
|---|---|
| 1 | 1 s |
| 4 | 8 s |
| 9 | 256 s |
| 10 ou mais | **300 s, para sempre** |

A partir da nona queda a conta esperava **cinco minutos cravados antes de cada
relogin** -- mesmo com horas de sessao saudavel entre uma queda e outra. Uma
conta que caiu de madrugada acordava o dia inteiro pagando o teto.

Nao e "trava no login", mas e o mais perto disso que existia, e foi o que o
usuario descreveu ao pedir que o bot *"nunca trave no login, sempre consiga
logar mesmo que demore"*.

### O conserto

O contador virou `self.tentativas_de_login` (estado do supervisor) e zera **no
login CONCLUIDO**, dentro de `_run_session`, nos dois caminhos -- janela adotada
ja logada e sequencia de login inteira.

E o unico sinal honesto: o backoff existe para espacar tentativas de login que
estao **falhando**, e um login que funcionou provou que ele cumpriu o papel.
Como local de `run()` ele nem alcancavel era de dentro do `_run_session`.

Depois disso: N falhas seguidas ainda escalam 1 -> 2 -> 4 -> 8 s normalmente,
mas uma sessao que viveu quatro horas e caiu recomeca em **1 s**.

Travado por `tests/test_backoff_do_login.py`, que reprova o **padrao** inteiro:
nenhum `try/except/else` cujo corpo termine em `return` pode voltar.

### O que JA existia e nao precisou de nada

- **Fechar a janela travada e reabrir**: `LOGIN_SCREEN_MAX_SECONDS = 150.0`, a
  secao acima.
- **Nunca desistir**: o `while not self.stop_event.is_set()` nunca teve teto de
  tentativas.

---

## SENHA ERRADA DESATIVA A CONTA (26/08/2026)

A unica excecao a "nunca desistir", e ela nao e sobre tempo.

Mais tentativas nao resolvem senha errada, e **cada recusa e uma tentativa
registrada no servidor** -- o caminho para a conta bloqueada. Aqui o custo de
insistir nao e tempo, e a conta.

### Cinco recusas, e sao cinco NO TOTAL

`MAX_CREDENTIAL_ERRORS` subiu de 3 para **5**, por escolha do usuario. E cinco no
total, nao cinco por ciclo de relogin: `credential_errors` nasce zerado a cada
`LoginSequence` e o `BadCredentials` encerra a conta na primeira vez que o limite
estoura. Contar por ciclo multiplicaria isso por cada tentativa e o servidor
veria dezenas de senhas erradas da mesma conta -- exatamente o dano que o limite
existe para evitar.

**So a TELA DE ERRO conta.** `credential_errors` sobe dentro de
`_handle_login_error`, que so roda quando o detector casa `state_login_error.png`
(a assinatura de `LoginScreen.LOGIN_ERROR`). Demora, fila e tela travada nao
somam ali -- cada uma tem seu proprio caminho. Foi exigencia do usuario:
*"lembrando que o BadCredentials tem um texto especifico em tela, entao so
quando aparecer que erro que contabiliza"*.

### O que mudou no desfecho

Antes: `_teardown()` + `return`. A thread morria, a conta sumia da execucao **sem
que nada na tela dissesse que ela tinha morrido**, e na execucao seguinte ela
voltava a queimar as mesmas recusas.

Agora: `self.account.enabled = False` **gravado no `config.json`**, e so entao o
encerramento. A conta **desmarcada na interface E o aviso**: ela nao tenta mais
sozinha, nao volta na proxima execucao, e reativar e o mesmo clique com que se
confere a senha. `BotManager.sync_accounts()` alinha os supervisores com
`enabled_accounts()`, entao isso significa "nao tenta mais" de verdade.

### O efeito colateral que precisa estar escrito

Uma conta aposentada por senha errada que era **reseter** de outra conta faz o BC
dependente cair no ramo *"nao existe mais"* do portao da cave: ele desliga o
`bc_farm` daquela conta e avisa, em vez de esperar para sempre por alguem que o
proprio bot acabou de aposentar. Ver `docs/decisoes/reset-de-time.md`.

## A conversa dos OUTROS derrubava a conta (01/09/2026)

### O que foi observado

O usuário notou contas reabertas e marcadas como queda que, **pela imagem**, não
tinham caído. O `logs/quedas/*.jpg` permite conferir isso sem hipótese: o print
não é uma captura nova, é **o quadro que disparou a queda** — quem reconheceu foi
ele mesmo (ver o docstring de `quadro_com_aviso_de_conexao`).

Em `20260901-022514-blazesgamer.jpg` o personagem está em pé em Guild Demesne,
com "Janitor of Guild D..." selecionado, HP cheio. Não há caixa de diálogo
nenhuma. O que há é uma linha de chat:

    [world] [zmypx]: maintenance more connection interrupted?

### A medição

`state_conn_prefix.png` é **só a frase** "Connection interrup" (114×25), sem
moldura — recortada assim de propósito, para casar com as duas variantes do
aviso ("Connection interrupted." e "Connection interrupted, please open client
again."). O preço é que ela casa **onde quer que a frase apareça**.

Rodando o template contra os 22 prints de `logs/quedas/`, com a verdade de campo
conferida a olho:

| | nota | centro do casamento | onde |
|---|---|---|---|
| queda real (12 prints) | 0.980 – 0.983 | (441, 198) | a caixa modal |
| chat dos outros (10 prints) | 0.799 – 0.844 | (241, 570) | o rodapé esquerdo |

O limiar era **0.80** — *abaixo* do ruído do chat. Duas rajadas de relogin
saíram daí:

    29/08 03:04  5 contas   notas 0.799-0.844
    01/09 02:25  5 contas   notas 0.808-0.814

Nenhuma delas tinha caído.

### O conserto: duas defesas, cada uma suficiente sozinha

1. **REGIÃO** — a busca só olha em volta de `coords.aviso_de_conexao`
   (`_from_base(441, 198, CENTER)`), com `RAIO_DA_BUSCA_DO_AVISO = 120`. A caixa
   variou 4 px nos 12 prints reais (é opaca e centralizada); 120 px é folga de
   trinta vezes isso, e o chat fica 372 px abaixo — fora por larga margem.
   Com a região, a melhor nota dos falsos cai de **0.844 para 0.421**.
2. **LIMIAR** — de 0.80 para **0.92**, o meio entre 0.844 (pior falso) e 0.980
   (pior queda real).

Margem final medida: **+0.559** (0.421 → 0.980), contra as **−0.044** de antes
(o limiar ficava abaixo do pior falso).

**Por que as duas, se cada uma resolve.** A frase no chat é um evento que o bot
não controla e não pode prever: qualquer jogador a digita quando quiser, quantas
vezes quiser. Uma defesa só significa que a próxima build do jogo, ou um recorte
de template refeito, volta a custar cinco relogins simultâneos. É o mesmo
raciocínio do `state_team_invite_texto.png`.

### Alternativas consideradas e reprovadas

- **Recortar o template com a moldura da caixa.** Reprovado pela mesma razão
  medida no `package_courage` e citado no cabeçalho do `bc/hotbar.py`: moldura
  dourada domina a correlação e a margem despenca. Além disso o template
  precisa casar com as **duas** variantes do texto, que têm larguras diferentes.
- **Só subir o limiar.** Funciona nos dados de hoje (margem +0.137), mas depende
  de o chat nunca renderizar a frase com contraste melhor — e o chat muda de cor
  por canal.
- **Exigir duas leituras seguidas.** Custa 10 s a mais para reagir a uma queda
  real (`VISUAL_CHECK_SECONDS`), e nesse intervalo a conta aperta teclas contra
  um cliente morto. Não se paga: a região já resolve sem custo nenhum.

### O que mais saiu daqui

A busca estava **duplicada** — `avaliar_saude` (a definição de queda para todo
ecossistema) e `Watchdog._quadro_com_aviso_de_conexao` (a cadência do BC) faziam
a mesma coisa em cópias separadas. Só uma teria sido consertada. Agora as duas
chamam `watchdog.quadro_com_aviso_de_conexao(hwnd, templates)`.

Travado por `tests/test_queda_por_aviso_de_conexao.py`, que roda contra os prints
reais: os 10 falsos não podem passar, as 12 quedas reais não podem falhar, e a
margem entre as duas populações não pode cair abaixo de +0.30.

## O bug de conexão do jogo estava desativando conta com a senha CERTA (01/09/2026)

### O que aconteceu

Numa `LoginSequence` de **796 s** na conta `blazesofgamer`, com o jogo no bug de
"Conexão interrompida" que o usuário relatou durar **semanas**:

| evento | vezes |
|---|---|
| **lista de servidores alcançada** | **85** |
| conexão interrompida | 85 |
| tela de erro de usuário/senha | **5** |

E a ordem em que cada erro apareceu:

```
 5 lista de servidores  ->  1 erro de usuário ou senha
13 lista de servidores  ->  1 erro de usuário ou senha
17 lista de servidores  ->  1 erro de usuário ou senha
11 lista de servidores  ->  1 erro de usuário ou senha
39 lista de servidores  ->  1 erro de usuário ou senha
```

Desfecho:

```
BadCredentials: o servidor recusou a conta 'blazesofgamer' 5 vezes.
                Confira usuário e senha.
```

### A prova de que a senha estava certa

**O servidor só mostra a lista de servidores DEPOIS de aceitar usuário e senha.**
A conta alcançou essa tela **85 vezes**. Cada um dos 5 erros veio depois de 5,
13, 17, 11 e 39 autenticações consecutivas bem-sucedidas.

Não era recusa: era erro esporádico do servidor, quase certamente parte da mesma
instabilidade que produzia as 85 quedas de conexão.

### Por que o estrago era grande

`supervisor.py`, no `except BadCredentials`:

```python
self.account.enabled = False
self.config.save()
```

A conta é **desativada e isso é persistido**. Ela sai de rotação e só volta com
intervenção manual. Ou seja: um bug do JOGO desativava conta boa, em silêncio, e
o aviso na interface dizia "confira usuário e senha" — apontando para o lugar
errado.

### O defeito, exatamente

`credential_errors` zerava **só no `__init__`**. Isso estava correto e
documentado — *"o contador nasce zerado a cada `LoginSequence`"* —, mas **uma
sequência dura horas e dezenas de ciclos de login**. Dentro de uma única
sequência o contador nunca zerava, mesmo tendo autenticado 85 vezes. "Cinco
recusas" virava, na prática, "cinco erros somados ao longo de horas".

### A correção

Zerar `credential_errors` quando o detector **vê a lista de servidores**, porque
isso é prova de credencial aceita. O idioma já existia no arquivo: o ramo do
`CHAR_SELECT` logo abaixo já zera o contador de tentativas às cegas pelo mesmo
tipo de raciocínio, e o `else` já zera `login_screen_since`.

**O limite de cinco continua inteiro.** Senha realmente errada nunca alcança a
lista de servidores, então nada zera e a conta é desativada na quinta recusa —
que é o comportamento certo, porque cada recusa real é uma tentativa registrada
no servidor e o custo de insistir é a conta.

### O detalhe que quase passou

O reset tem de ficar **FORA** do `if self.phase is not Phase.SERVER`.
`_do_credentials` faz `_set_phase(Phase.SERVER)` logo depois de clicar em OK,
**sem prova nenhuma** de que o servidor aceitou. Com o reset aninhado nesse `if`,
ele seria pulado justamente nos ciclos em que o palpite otimista já acertou a
fase — ou seja, quase sempre, e o defeito voltaria calado.

Travado por `tests/test_contador_de_credenciais.py::test_o_reset_esta_FORA_do_if_da_fase`,
que lê o AST do `run()` e exige o reset entre os comandos diretos do ramo.

### Como isto foi descoberto

Não foi procurando: caiu de um teste de relogin do resolvedor de alvo. Eu derrubei
o cliente com `taskkill /F` e o login não voltou. Minha primeira explicação foi
que o `taskkill` deixava a sessão presa no servidor — **e estava errada**. O
usuário informou que a "Conexão interrompida" é bug do jogo há semanas, e foi
essa informação que virou a leitura do log: 85 autenticações bem-sucedidas contra
5 erros esporádicos.

A lição: quando a explicação de uma falha é "artefato do meu método", vale
contar as evidências antes de fechar. O log já tinha o número que separava as
duas hipóteses.

Log completo e contagens: `Teste-Ponteiros/RESULTADOS.md` seção 16.

## 08/09/2026 — o vigia era COOPERATIVO, e por isso não podia funcionar

Relato do usuário: contas que caem ou **travam** ficam presas para sempre. O
requisito passou a ser explícito: **detectar em no máximo 20 s, em qualquer
ecossistema, mesmo com o bot ocioso, e matar o `client.exe` pela raiz.**

### A causa: vigia e vigiado eram a MESMA thread

`Watchdog.check()` só rodava quando alguém da thread do bot o chamava —
`ctx.tick()`, `_guard()`, o `conferir_saude` entre linhas da macro. Isso supõe
que a thread do bot continua andando, e a queda destrói justamente essa
premissa.

O bot fala com o jogo por **`SendMessageW` síncrono** (é a regra permanente: a
mensagem confere a janela e sai síncrona, com a coordenada no `lParam`).
`SendMessageW` contra uma janela **travada não tem timeout** — ele bloqueia a
thread que enviou, indefinidamente. A thread do bot parava dentro de uma tecla,
e a conferência que perceberia a queda estava na linha seguinte, que nunca era
alcançada. Não era o vigia que não via: era o vigia que estava parado no mesmo
buraco do vigiado.

### Três buracos, e o terceiro é o que prendia a conta

1. **Travamento não era sinal de queda.** `avaliar_saude` responde por processo
   morto, janela sumida e o aviso na tela. Um cliente **congelado** tem processo
   vivo, janela viva e nenhuma caixa para fotografar: os três sinais dizem
   "saudável". Este era o caso do "preso para sempre".
2. **Janelas cegas.** Ninguém chamava `check()` durante o backoff entre relogins
   (até 300 s), com a conta ONLINE e ociosa, nem durante o login.
3. **Politesse cara.** `kill_client` chamava `terminate()` e esperava **5 s**
   antes do `kill()` — cinco segundos pedindo educadamente a um processo que,
   por definição de quem chama essa função, já não está ouvindo. Um quarto do
   orçamento inteiro.

### A saída: uma thread só, fora do bot — `bot/sentinela.py`

Um `Vigia` para o processo inteiro, acordando a cada **6 s** com
`Event.wait` (bloqueio no núcleo: **0% de CPU em repouso**, e o `desligar()`
continua instantâneo — `time.sleep` daria uma das duas coisas, nunca as duas).

A escada de sinais, do mais barato ao mais caro, e **a ordem é a economia**:

| # | sinal | como | confirmações | pior caso |
|---|---|---|---|---|
| 1 | processo sumiu | `psutil.pid_exists` | 1 | 6 s |
| 2 | janela sumiu | `IsWindow` | 2 | 12 s |
| 3 | **janela travada** | `SendMessageTimeout(WM_NULL)` | 3 | **18 s** |
| 4 | aviso na tela | captura + template 0.92 | 1 | 6 s |

**Por que a sonda vem ANTES da captura, e não é detalhe:** `PrintWindow` (o
primeiro caminho de `capture_window`) manda `WM_PRINT` **síncrono**. Fotografar
uma janela travada penduraria a thread do vigia exatamente como pendura a do bot
— o vigia morreria da doença que veio diagnosticar. Só se fotografa janela que
acabou de provar que responde.

### Os números, e por que não são arredondamento

* **6 s de cadência** sai da conta `confirmações × cadência ≤ 20 s`. Com 3
  confirmações no sinal mais ruidoso, o teto é 18 s, e sobram 2 s de folga.
* **3 confirmações para o travamento** = 18 s de laço de mensagens
  **completamente parado**, contra uma sonda que uma janela viva responde em
  microssegundos mesmo carregando cenário. `WM_NULL` não faz nada: o único custo
  é a viagem até a fila do cliente e a volta. **Lag de servidor não conta como
  falso positivo** — lag de rede não para o laço de mensagens do Windows; o
  cliente continua repintando e respondendo, só não recebe pacote.
* **1 confirmação para processo sumido e para o aviso na tela.** Processo não
  ressuscita, e o aviso já passa por região presa à caixa mais limiar 0.92, com
  margem medida de **+0.559** sobre o pior falso (ver `RECONNECT_THRESHOLD`).
  Confirmar seria só atrasar o relogin.
* **2 confirmações para janela sumida** fecham uma fresta de arquitetura, não do
  jogo: o `hwnd` que o vigia lê vem do supervisor em outra thread, e existe uma
  volta entre o supervisor trocar de janela e o vigia enxergar a nova.

### O isolamento — o que o vigia NÃO pode tocar

É a parte que erra calada, então virou regra e teste
(`tests/test_vigia_global.py`):

* **Nada de `ctx.memory`.** O handle é aberto e **fechado** pela thread do bot.
  Todo sinal do vigia é sistema operacional, não jogo.
* **Nada de `capture_window`.** O pool de GDI (`vision._pools`) é um dicionário
  de módulo **sem cadeado**, com um DC e um bitmap por janela, e
  `AccountSupervisor._release` chama `release_pool`. Duas threads no mesmo
  bitmap dão quadro rasgado; destruir o DC durante o BitBlt da outra dá handle
  inválido **em silêncio**. Por isso nasceu `core.vision.capture_window_isolado`,
  que aloca o seu e devolve.
* **`TemplateLibrary` própria**, tocada só pela thread do vigia.
* O único estado que atravessa a fronteira é o **anúncio** (`Posto.queda`),
  escrito e lido com o cadeado segurado.

### O desfecho: matar é o que DEVOLVE a conta

Confirmada a queda, o vigia **anuncia e depois mata** — e a ordem não é trocável.

Matar o processo **desbloqueia a thread do bot na mesma hora**: um
`SendMessageW` contra uma janela que deixou de existir retorna imediatamente. Se
o anúncio saísse depois do kill, a thread acordaria, veria só "processo sumiu" e
o Histórico de Quedas registraria **o efeito no lugar da causa**.

O relogin **não mudou**: a thread do bot acorda, lê o anúncio em
`BotContext.check_watchdog`, levanta `Disconnected`, e o `run()` faz
`_encerrar_caido` → backoff → nova sessão → login. O vigia não sabe o que é
login e não precisa saber.

### O que mudou em volta

* `kill_client` virou **`TerminateProcess` direto** (`psutil.Process.kill()`),
  com `taskkill /F /T` de reserva e confirmação por `pid_exists`. Sem
  `terminate()`, sem espera de cortesia.
* `check_watchdog` consulta o vigia **antes** do watchdog inline — e antes do
  `return` das contas sem `Watchdog`. Era por ali que **tudo que não é BC**
  ficava cego neste caminho.
* O `conferir_saude` do APP consulta o mesmo anúncio.
* `_registrar_queda` passou a ler posição e local **defensivamente**: a queda
  agora pode ser decretada de outra thread, que matou o processo antes desta
  linha, e uma exceção ali perderia o cartão inteiro justamente na queda que
  mais importa.
* Novo motivo no Histórico de Quedas: **`travou`** — *"O jogo congelou e parou de
  responder"*.

### O interruptor

`sentinela.MATAR_JANELA_TRAVADA = True`. É o único critério de morte que mata uma
janela que o Windows ainda considera viva — se um dia derrubar conta boa, a volta
atrás é uma linha, e não uma edição no meio do laço. Travado por teste.

### O que NÃO subiu, e por quê

A **memória** ainda não é fonte de queda, apesar da regra MEMÓRIA PRIMEIRO. Um
ponteiro de conexão que zera seria o sinal mais rápido e mais barato de todos,
mas ele **não está medido** — e a regra do projeto é que número novo precisa de
medição, com ferramenta que só loga e sabe reprovar, comparando com a fonte
antiga no MESMO instante. Enquanto isso não existir, o vigia decide por sinais
do sistema operacional, que são fatos do Windows e não limiares chutados. É o
próximo passo natural deste módulo.

## 09/09/2026, 00:56 — o vigia matou o supervisor que ele deveria salvar

Primeira noite com o vigia global em campo. Traceback:

```
ClientClosed: o cliente foi encerrado pelo aviso de conexão interrompida
During handling of the above exception, another exception occurred:
  File "supervisor.py", line 2594, in run
    self._sleep_interruptible(delay)
  File "supervisor.py", line 340, in _sleep_interruptible
    raise Disconnected(anuncio[2])
Disconnected: aviso de conexão interrompida na tela
PARANDO por falha inesperada: aviso de conexão interrompida na tela
```

### A sequência

1. O aviso "Connection interrupted" apareceu **durante o login**. Quem tratou foi
   o próprio `login._handle_conn_interrupted`: encerrou o cliente e levantou
   `ClientClosed`. Comportamento correto e anterior ao vigia.
2. O vigia tinha visto **o mesmo aviso** e deixado o anúncio publicado.
3. O `except ClientClosed` do `run()` fez `_release()` e chamou o backoff.
4. `_sleep_interruptible` leu o anúncio e levantou `Disconnected` — **de dentro
   de um bloco `except`**.
5. Exceção levantada dentro de um `except` **não é pega pelos `except` do mesmo
   `try`**. Ela subiu direto para a rede de baixo (`except BaseException`), que
   registra "PARANDO por falha inesperada" e **encerra a thread da conta**.

Resultado: o mecanismo escrito para devolver a conta ao ar em 20 s tirou a conta
do ar até alguém olhar. Pior que o defeito original.

### As duas causas, e as duas correções

**(a) Consulta em lugar estruturalmente errado.** O `run()` já avisava disso no
próprio comentário da rede de baixo: *"há dois caminhos que passavam por fora
[do laço]: uma exceção levantada DENTRO de um `except`..."*. As quatro chamadas
de backoff estão todas em handlers.

A consulta **saiu** de `_sleep_interruptible`, e não havia o que perder: durante
o backoff a conta **não tem cliente** — `_release` já zerou `pid` e `hwnd`, e o
vigia pula postos sem janela. O único anúncio possível ali é o velho. E cortar o
backoff por causa dele é errado duas vezes: o backoff existe para não martelar o
servidor de login. A cobertura da conta ONLINE E OCIOSA nunca dependeu dessa
espera — ela é `ctx.tick()` no laço de `_operate`, que consulta o vigia por
`check_watchdog`.

**(b) Anúncio que sobrevivia à sessão.** A limpeza só existia no braço
`except Disconnected`. A queda tratada pelo **login** sai por `ClientClosed`, que
não passava por ali. A limpeza mudou para **`_release()`** — o ponto por onde os
cinco caminhos de morte de sessão passam. Um lugar, não cinco.

### A lição, e ela é geral

**Nada que rode dentro de um `except` do laço de vida pode levantar exceção
nova.** Não é regra do vigia: é regra do `run()`. A rede de baixo existe para
não perder o log, não para ser o caminho normal — quando ela dispara, a conta
morre.

Travado por `tests/test_vigia_global.py`, com o teste dirigindo o `run()` de
verdade: sessão que morre por `ClientClosed` com anúncio vivo, e o desfecho
exigido é chegar à sessão seguinte. Verificado que ele REPROVA sem a correção —
com o mesmo traceback do campo.

## 09/09/2026, 01:08 — o vigia derrubava a conta ENTRANDO NA FILA

Laço de relogin a cada 19 s, sempre igual, na conta `blazesgamer`:

```
01:07:59  Servidor 'Light in the Darkness' confirmado como selecionado
01:08:01  VIGIA: aviso de conexão interrompida na tela — matando o cliente (PID 35908)
01:08:01  Fase do login: aguardando entrar (fila ou personagem)
01:08:01  a janela do cliente desapareceu durante o login. Relogin #2
01:08:01  Reabrindo em 2s
```

Dois segundos depois de confirmar o servidor, no instante em que o login entra
na fila, o vigia decretava queda e matava o cliente. O login, sem a janela,
reportava "a janela do cliente desapareceu" — **a causa verdadeira se perdia** —
e o ciclo recomeçava.

### O que foi descartado antes de achar a causa

**Região uniforme degenerando `TM_CCOEFF_NORMED`.** Hipótese plausível (divisão
pelo desvio-padrão zero numa tela de carregamento preta), e **refutada por
medição**:

| quadro | nota do `state_conn_prefix` |
|---|---|
| preto puro / cinza uniforme / branco puro | **0.000** |
| ruído aleatório | 0.071 |
| gradiente sutil | 0.060 |

Nenhum chega perto de 0.92. Não é isso.

### A causa, e ela já estava medida no próprio projeto

O template do vigia é **um só**: `state_conn_prefix.png`. Ele casa com a palavra
**"Connection"** — foi recortado assim de propósito, para pegar as duas variantes
de "Connection interrupted". Mas nas telas de login existe uma **família** de
caixas que começam com essa palavra, e todas são desenhadas no **mesmo centro**
onde o aviso de queda aparece. Medido em 18/08/2026 e registrado em
`login_states.py`:

```
"Connection failed"          state_conn_prefix = 0.835
"Connecting to the server"   state_conn_prefix = 0.787
```

O `LoginDetector` convive com isso porque tem **escada ordenada**: pergunta pelos
templates específicos primeiro (`state_conn_failed`, `state_connecting`) e só
deixa o genérico opinar **por último**. É comentário explícito lá:

> *"O GENÉRICO POR ÚLTIMO entre os modais. (…) por casar só no prefixo ele
> PRECISA ser o último a opinar."*

**O vigia não tem escada.** Ele usa o genérico sozinho, e ainda travado na região
onde essas caixas aparecem — a defesa por região, que funciona contra o chat (que
fica no rodapé), não protege contra caixa centralizada.

E o limiar de **0.92 não cobre isso**: ele foi medido contra população **em
jogo** — o aviso real (0.980-0.983) de um lado, linhas de chat (0.421 na região)
do outro. **As telas de login nunca estiveram em nenhuma das duas populações.**
O vigia foi a primeira coisa na história do projeto a rodar esse template contra
elas. Usar limiar fora da população onde foi medido é exatamente o que o
`CLAUDE.md` proíbe.

### A correção

Durante `login.run()`, o vigia **só reconhece fato do sistema operacional**:
processo sumido e janela sumida. Aviso na tela e travamento ficam suspensos.

* Fato não admite interpretação: processo que sumiu não voltou, e a conta presa
  num processo morto continua sendo resgatada em 6 s.
* Juízo sobre a tela de login é do `LoginDetector`, que já tem o tratamento certo
  para cada uma daquelas caixas. **Duas leituras da mesma tela divergem na
  primeira manutenção** — e esta divergiu antes da primeira.
* O **travamento** cai junto, com agravante próprio: a **fila de login passa de
  três horas** e não existe medição nenhuma de como o cliente bombeia mensagens
  enquanto espera nela. Matar cliente na fila é o dano mais caro que este bot
  sabe causar.

A trava é `AccountSupervisor._login_em_curso`, entregue ao vigia como
`em_sessao=lambda: not self._login_em_curso`. Ela vira `False` no **mesmo ponto**
em que `tentativas_de_login` zera — o único sinal honesto de que o login
concluiu, e ele serve aos dois caminhos (janela adotada já logada e sequência de
login inteira).

### O que isso NÃO resolve, e é do usuário saber

Se o servidor estiver recusando de verdade logo depois da escolha do servidor, o
laço continua — mas agora ele é o laço **projetado**: quem detecta é o login,
quem trata é `_handle_conn_interrupted`, e o backoff cresce 1, 2, 4, 8 … até 300
s. A diferença é que a causa aparece certa no log, o cliente na fila não é morto
por engano, e a caixa é clicada em vez de a janela ser arrancada.

### Dívida deixada aberta, de propósito

Não existe medição do `state_conn_prefix` contra as telas de login **com a
região travada no centro** — só contra a tela inteira (0.835 / 0.787). Sem essa
medição não dá para dizer qual limiar separaria as populações, e por isso a
saída foi **suspender**, não **subir o limiar**: número novo precisa de medição,
e arredondar para cima é como se erra calado.

## 09/09/2026 — o vigia deixou de ler a tela: 48 decretos, nenhuma queda

O usuário corrigiu o escopo, e a correção importa:

> *"antes da mudança o relogin estava funcionando bem (pelo menos parecia
> estar), só o ato de fechar uma conta que já caiu que não estava acontecendo em
> 100% das vezes — então tinha contas que caíam, mas elas não eram identificadas
> e ficavam em um 'limbo'."*

Ou seja: **os leitores de tela já funcionavam**. O que faltava era a conta que
cai e ninguém fecha.

### O saldo da primeira noite, contado no log

`logs/dev/blazes-dev.jsonl`, 09/09/2026:

| | |
|---|---|
| decretos do vigia | **48** |
| por "aviso de conexão interrompida na tela" | **48 (100%)** |
| contas atingidas | **1** (`blazesgamer`, sempre na tela de login) |
| decretos nas outras 4 contas, a noite inteira | **0** |
| decretos pela sonda de travamento | **0** |
| quedas que os leitores antigos não teriam pego | **0** |

Quarenta e oito mortes, nenhuma delas uma queda.

### A conclusão, e ela é sobre desenho, não sobre limiar

O aviso na tela já tinha **dois** leitores: o watchdog inline (na thread da
conta, a cada 10 s) e o `LoginDetector` (durante o login). O vigia virou o
**terceiro leitor da mesma tela** — e um terceiro leitor não soma cobertura:
soma uma chance de errar sozinho, ainda por cima num contexto onde o limiar dele
nunca foi medido.

E o caso que motivou tudo — a conta em **limbo** — não é falta de leitura de
tela. É a thread da conta parada dentro de um `SendMessageW` síncrono, sem poder
perguntar nada a ninguém. Quem responde isso são os três sinais que **sobram**:
processo sumido, janela sumida e a sonda de travamento. Nenhum deles vê a tela,
nenhum depende de limiar, e nenhum pode ser bloqueado pela janela que está
diagnosticando.

`sentinela.OLHAR_A_TELA = False`. Não foi apagado — é interruptor, com teste
forçando-o ligado para a lógica continuar exercitada.

### O que é preciso para religar

Medir `state_conn_prefix` contra as telas de login **com a região travada no
centro** — a medição que não existe. Só ela diria qual limiar separa a queda
real (0.980-0.983 em jogo) da família "Connection failed" / "Connecting to the
server". Subir o 0.92 no chute é como se erra calado.

## 11/09/2026 — três contas de APP/Fada travadas com a caixa na tela

Relato, com print: `Tsuki69` (Fada do APP) parada com
*"Connection interrupted, please open client again."* na tela, sem relogin. Nos
minutos seguintes, mais duas contas de APP no mesmo estado.

### Foi regressão do commit `49b668a`, e a justificativa dele estava errada

Ao desligar `sentinela.OLHAR_A_TELA` eu escrevi que o aviso na tela *"já tinha
DOIS leitores: o watchdog inline e o `LoginDetector`"*.

**O watchdog inline só existe no BC.** `ctx.watchdog` é injetado num lugar só —
`bc/routine.py`, no `__init__` da rotina. Verificado por AST em todo o pacote:
é a única atribuição. Conta de APP, de Fada e de HH sem BC tem
`ctx.watchdog = None`, e `BotContext.check_watchdog` sai por `return` na
primeira linha. **Elas nunca tiveram o segundo leitor que eu supus.**

Pior na Fada, e é por isso que ela travou primeiro:

* ela **não chama `ctx.tick()` em ponto nenhum** — nem a consulta ao vigia acontece;
* a única queda que ela percebe é `IsWindow`, **depois** que o laço retorna
  (`fada_montagem.py`, a correção de 04/09/2026);
* a caixa "Connection interrupted" deixa a janela **viva** → o laço nunca
  retorna → a conta fica presa para sempre.

Corroboração no log daquele dia: os três decretos do vigia foram **todos** por
"processo do cliente encerrado". Nenhum por tela, porque o interruptor estava
desligado.

### E os 48 falsos positivos que motivaram o desligamento?

Já estavam resolvidos quando desliguei. Os 48 aconteceram **todos nas telas de
login**, e a suspensão de juízo durante o login
(`SO_FATO_DO_SISTEMA_DURANTE_O_LOGIN`, commit `32bf95f`) é **anterior** ao
interruptor. Com ela valendo, o vigia só lê a tela com a sessão estabelecida —
exatamente a população onde o limiar 0.92 foi medido, com margem de +0.559.

Desligar depois disso foi zelo em cima de causa já consertada, e custou três
contas travadas. `OLHAR_A_TELA = True`.

### O invariante que o usuário formulou, e que isto passa a cumprir

> *"É importante que o login/relogin não dependa de forma alguma dos outros
> ecossistemas (…) se eu adicionar novos ecossistemas, ele continue verificando
> se caiu a conta para derrubar e logar ela novamente."*
>
> *"O login/relogin não deve precisar ser instanciado em outros ecossistemas,
> deve rodar em paralelo com eles, para que na hora que adicionar mais, não
> precise chamar o watchdog."*

O desenho que cumpre isso é o vigia global: **thread paralela**, registrada
**uma vez** no `run()` do supervisor, recebendo **peças** (o login e uma função
que devolve `(pid, hwnd)`) e nada de `BotContext`. Ele não importa nada de
`bc/`, `app/` nem `hh/` — travado por AST.

O que um ecossistema novo recebe **sem escrever uma linha**:

| etapa | quem faz | o ecossistema participa? |
|---|---|---|
| perceber a queda | vigia, thread própria | não |
| matar o cliente | vigia (`TerminateProcess`) | não |
| gravar no Histórico | `_registrar_queda`, lendo o anúncio | não |
| relogar | `AccountSupervisor.run` | não |

O `_registrar_queda` passou a consultar `sentinela.cobrar_a_queda` quando
`ctx.ultima_queda` está vazio — é o que faz o cartão do Histórico sair também
para quem não tem onde anotá-lo, que era o caso da Fada.

### O resíduo, declarado e não escondido

**A SAÍDA da thread do ecossistema ainda é cooperativa.** O vigia mata o
processo, e a partir daí toda mensagem é barrada pelo funil
(`Input._janela_confiavel`) — mas quem faz a thread do ecossistema *desistir* é
ainda o próprio ecossistema: o BC e a HH pelo `check_watchdog`, o APP pelo
`conferir_saude`, a Fada pelo `IsWindow` do fim do laço.

Na prática isso se resolve sozinho na volta ao `_operate`, que chama `ctx.tick()`.
O caso ruim é o ecossistema novo que rode um laço longo sem voltar — o mesmo
defeito que o APP teve em 18/08/2026.

O caminho natural é o funil do `Input` parar a thread quando houver anúncio para
aquela conta, já que ele é o ponto único por onde todo ecossistema fala com o
jogo. Não foi feito aqui: é decisão de arquitetura com mais de um caminho, e as
contas estavam travadas agora.
