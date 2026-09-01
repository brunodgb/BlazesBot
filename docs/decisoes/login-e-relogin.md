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
