# Reset de time: a lista fechada e a trava na porta da cave (26/08/2026)

> O **porquê** desta área. A regra resumida está no `CLAUDE.md`; a
> especificação, em `docs/REGRAS.md` (seção "Reset de time"). Leia este arquivo
> **antes** de mexer em qualquer coisa aqui.

---

## O problema que já existia, e ninguém via

Fazendo a Bewitcher Cave duas vezes seguidas sem mudar de time, o boss **não
renasce**: a instância continua com ele morto e a run é perdida. Entrar num time
novo reseta a cave. Isso o `bot/team.py` já resolvia.

O que **não** estava resolvido é o que acontece quando a conta de reset cai.

```python
# routine.py, antes de 26/08/2026
self.team.montar_time()      # <- o retorno era DESCARTADO
```

`montar_time()` devolve `False` quando o time não formou, e ninguém lia. Com o
reseter caído às 03h, o bot seguia entrando na cave a noite inteira: cada
entrada gastava teleporte, travessia e disputa da porta para chegar num boss que
já estava morto. **Run perdida atrás de run perdida, em silêncio.**

O usuário resumiu assim, em 26/08/2026:

> *"quero que se o bot perceber que a conta que seria a reset cair, em vez de
> continuar tentando entrar, fazer a conta de BC parar temporariamente até a
> conta reset voltar, então vai ser uma trava temporaria e não volta até a conta
> reset estar online, então o bot tem que ter essa inteligencia"*

---

## Decisão 1 — o campo de texto livre virou LISTA FECHADA

`BCConfig.reset_nick` continua sendo um **nick**, gravado igual. O que mudou é
como ele é escolhido: um `QComboBox` na GUI e um `<select>` na web, montados a
partir de `BotConfig.reset_accounts()` — as contas **ativas** marcadas com
`accept_team_invites`.

### Por que continua sendo o nick, e não um índice ou o login

Porque o nick **não é rótulo, é o valor operacional**. Ele é digitado na Block
list para o convite existir (`garantir_reseter_registrado`) e é ele que casa com
`ctx.char_name` do outro lado (`InviteAcceptor._modo_estrito`). Guardar
login/índice obrigaria a resolver nick a cada uso, e quebraria enquanto a conta
ainda não logou. Zero campo novo, zero migração de schema, zero mexida em
`_settings_from_dict`.

### Por que fechar a lista — o arranjo de duas máquinas MORREU de propósito

O `_modo_estrito` foi escrito assumindo que o reseter podia estar em **outro
PC**, e o campo de texto livre existia para isso. Isso acabou, e por ordem
explícita do usuário:

> *"a ideia é o reseter sempre estar cadastrado dentro do bot, e nao em outro
> computador (…) tem que ser obrigatoriamente dentro do sistema, pois assim
> garantimos que tudo vai funcionar perfeitamente"*

E é operacionalmente necessário: **um reseter fora deste processo é invisível
daqui.** Sem observá-lo não há batida, sem batida não há trava, e sem trava o bot
volta a entrar sem reset sem ter como saber. A trava inteira depende da lista
fechada.

### A conta marcada que nunca logou aparece DESABILITADA

O nick é lido da memória no primeiro login, então uma conta recém-cadastrada não
tem nick. Deixar selecioná-la gravaria `reset_nick = ""` — que no código
significa exatamente **"não usar reset de time"**. Seria um jeito silencioso de
*desligar* a função achando que ligou. Ela aparece na lista, cinza, dizendo
"ainda não logou, sem nick".

### O que está gravado e não é candidato continua VISÍVEL

Terceira opção da lista, no fim, com "⚠ não é conta de reset deste bot", e
continua **selecionada**. Sumir com ela seria o bot apagando a configuração de
alguém sem avisar; mostrando, o usuário vê o que está errado e troca num clique.

---

## Decisão 2 — a migração LIGA a flag sozinha (e sabe quando não deve)

O campo era texto livre, então existe `config.json` em disco com o nick digitado
à mão e a flag `accept_team_invites` **desmarcada**. Sem migração, todos eles
viravam reset órfão na primeira abertura.

`BotConfig._migrar_reset_de_time` roda no fim do `from_dict`, com todas as contas
já construídas — é a **única** migração que olha uma conta a partir de outra.

**Liga a flag não inventa intenção.** Quem escreveu aquele nick já declarou que
aquela conta é o reseter; a flag é a mesma declaração dita de outro jeito.

**Mexer numa conta que farma inventaria.** Se o nick aponta para uma conta com
`bc_farm` ou modo APP ligado, ligar a flag seria o bot decidindo que ela deve
parar de farmar — e essa decisão não é dele. Nesse caso a migração não toca em
nada, e o caso cai no veto por conta, com a mensagem exata.

Princípio que ficou: **migração automática só onde ela reafirma o que o usuário
já disse.** No instante em que precisaria escolher por ele, ela para e avisa.

---

## Decisão 3 — a BATIDA prova a capacidade, não a descreve

A pergunta parece ser *"a conta de reset está logada e saudável?"*. Responder
isso com uma checagem — processo vivo, hwnd válido, memória legível — tem **falso
positivo por construção**:

```python
# supervisor.py, _operate
if self.account.settings.app.enabled:
    self._rodar_modo_app()
    continue                      # <- nunca chega no aceitador
if ctx.settings.accept_team_invites:
    aceitador.check_and_accept()
```

Uma conta em **modo APP** passa em todas aquelas provas e **nunca aceita convite
nenhum**. Login, relogin e farm da cave têm o mesmo problema, por caminhos
diferentes: são quatro regras a escrever, e cada uma é uma chance de esquecer a
quinta.

Então a batida não descreve a capacidade — ela **é consequência de exercê-la**:

```python
def check_and_accept(self) -> bool:
    bater(self._meu_nick)          # PRIMEIRA linha, antes até do cooldown
```

Se a linha não executou, a conta não tem como clicar no Ok, e a batida não sai.
Modo APP, login, relogin, farm e conta parada caem fora **sozinhos, sem uma regra
escrita para cada um**.

**Antes do cooldown**, e isso importa: o cooldown é sobre *clicar* (não vale
capturar a tela cinco vezes por segundo), não sobre *estar disponível*. Batendo
depois dele, a disponibilidade herdaria a cadência do clique sem motivo.

Isto só funciona porque todas as contas rodam **no mesmo processo** — a mesma
base do registro de convites (`_CONVITES`) que já estava ali.

### `SILENCIO_MAXIMO = 5.0` — número DERIVADO, não medido

O laço da conta de reset gira a `tick(0.5)`, então ela bate ~2×/s e 5 s são
**dez voltas dela**. Folga suficiente para uma volta lenta não virar queda falsa,
e ainda assim a queda aparece para quem farma em ~5 s. Se este número mudar,
mude junto com o `tick(0.5)` do `_operate` — eles são o mesmo número visto de
dois lados.

### Nunca ter batido conta como OFFLINE

Ela bate duas vezes por segundo desde que sobe, então "nenhuma batida" não é
dúvida: é que ela ainda não chegou lá. Tratar isso como "provavelmente está ok"
devolveria exatamente a run perdida que a trava existe para evitar.

---

## Decisão 4 — o portão fica num lugar só POR CAVE: antes do `montar_time()`

`BossRushRoutine._do_entrar`, imediatamente antes do convite. A HH ganhou o
portão dela em 08/09/2026, no `_garantir_o_time` — mesmo princípio, outro
ponto; ver a **Decisão 10**.

### Por que não travar no meio da run

O reseter só importa **no instante da entrada** — é a única coisa que ele faz.
Travar no meio do covil perderia a run atual por causa de um problema que só
afeta a **próxima**. A run em curso termina inteira — boss, venda, viagem de
volta — e o personagem estaciona no ponto de entrada que ele já conquistou, então
voltar a tentar custa zero.

Foi decisão explícita do usuário (Q5, 26/08/2026): *"só trava imediatamente antes
de montar_time()"*.

### Por que `ctx.tick` e nunca `time.sleep`

Duas razões, e a primeira é a que morde:

1. **É o `tick` que roda o watchdog desta conta** (`context.py`, seção "PORQUE O
   WATCHDOG ESTÁ AQUI"). Uma conta de BC também cai. Parada por horas num
   `time.sleep`, ela ficaria **cega para a própria queda** — que é literalmente o
   defeito que o `test_saude_em_todo_ecossistema.py` existe para impedir.
2. As três saídas vêm de graça, já implementadas: Parar (`stop_event`),
   desmarcar o BC farm (`raise_if_stopped` levanta `FarmDesligado`) e ligar o
   modo APP (`should_continue`).

### Sem interruptor novo

`reset_nick` preenchido já é a declaração de que sem reset a run não presta. É a
mesma regra que o próprio campo já documentava: *"Vazio = não usa reset de time.
Não há liga/desliga separado: o campo em branco já diz tudo, e um interruptor a
mais seria só uma forma de errar."*

---

## Decisão 5 — "caiu" e "não existe mais" são estados DIFERENTES

Esta é a parte que impede a trava de virar uma conta parada a noite inteira.

| estado | como se reconhece | desfecho |
|---|---|---|
| **caiu** | a batida envelheceu, mas `problema_do_reset` diz `None` | espera; o relogin é o comportamento padrão, ela volta sozinha |
| **não existe mais** | `problema_do_reset` responde algo | **desliga o `bc_farm` desta conta, salva e avisa** |

"Não existe mais" cobre: reseter removido, desativado, desmarcado, posto para
farmar, posto em modo APP — **ou aposentado por senha errada** (ver
`login-e-relogin.md`).

A condição é reavaliada **a cada volta do laço**, não só na entrada: a
configuração muda com o bot rodando. Sem reavaliar, o bot esperaria para sempre
por alguém que ele mesmo aposentou.

O desfecho não é padrão novo: é exatamente o que a venda sem tecla de retorno já
faz (`vendor.py`) — desliga o `bc_farm` daquela conta, salva, e o checkbox
desmarcando nas duas interfaces **é** o aviso.

---

## Decisão 6 — o veto é POR CONTA, não tudo-ou-nada

`BotConfig.validate()` é tudo-ou-nada: devolve a lista de problemas e o
`BotManager.start()` **não sobe supervisor nenhum**. Para o reset de time isso é
desproporcional — uma conta apontando para um reseter que não existe não é motivo
para as outras quatro ficarem fora do ar.

Por isso `problema_do_reset` **não** está no `validate()`. O desfecho é: a conta
loga, fica **online**, com relogin ativo, e só o **BC dela** não roda.

**A tecla da lista de amigos veio junto.** Ela reprovava a execução inteira
(`AccountSettings.validate()`); agora veta só o BC daquela conta. Mudança de
**alcance**, não de rigor — continua obrigatória.

---

## Decisão 7 — tirar um reseter do ar é IMPEDIDO, não avisado

Deletar, desativar, ou **desmarcar "aceitar convites de time"** — as três portas
levam ao mesmo estrago, e as três são bloqueadas com aviso grande, nas duas
interfaces.

> *"se aquela conta for reseter de outra, se o usuario tentar deletar ou
> desativar, voce vai dar um aviso bem grande para ele e vai impedir, pois assim
> ele troca primeiro o reset e depois deleta a conta ou desativa"*

**Por que impedir e não só avisar:** o sintoma ("o boss parou de nascer") aparece
horas depois e não aponta para cá em nada. E **por que aqui e não na validação:**
neste instante o usuário está com a tela na mão e o contexto na cabeça — desfazer
é um clique. Descoberto três horas depois, no meio de uma run, o mesmo problema
custa reabrir tudo e reconstruir o raciocínio.

Na web o bloqueio é **no backend** (`web_app.bloqueio_de_reseter`), não só na
tela: é por onde toda remoção passa, e um erro no frontend não pode furá-lo. O
aviso é modal, nunca toast — o toast some em 2,6 s.

**Só contas ATIVAS contam como dependentes** (`accounts_reset_by`). Uma conta
desativada não roda, então ela não fica órfã de nada hoje; barrar a exclusão por
causa dela criaria trabalho por um problema que não existe. Se for reativada
depois, `problema_do_reset` a pega com a mensagem certa.

---

## Decisão 8 — o campo POR CAVE virou UM, no escopo do personagem

### O pedido

> *"Hoje a configuração da 'Conta Reset' está sendo definida separadamente em
> cada aba de Cave (BC, HH). Isso é um erro de design. A conta reset é 1 única
> por conta logada."*

### O histórico dá razão a ele

Enquanto existiram `bc.reset_nick` e `hh.reset_nick`, havia **três estados
impossíveis** — e o bot pagou por dois deles:

| estado | o que aconteceu |
|---|---|
| preencher um e esquecer o outro | **Medido em 03/09/2026.** O usuário configurou o campo da HH; o do BC ficou vazio. `TeamService.montar_time` lia o do BC, devolvia `False` na primeira linha, a HH rodava sem time, os bosses não renasciam e a rotina caía em `RECUPERAR` — em laço, para sempre. |
| preencher os dois com nicks diferentes | Não existe resposta certa. Duas caves, dois reseters, e o aceitador de convites reconhecendo só um. |
| código compartilhado sem saber qual ler | `problema_do_reset`, `accounts_reset_by` e o modo estrito do aceitador liam o do BC. O aceitador teve que passar a olhar **os dois** para não perder o reseter da HH — remendo que só existia por causa do desenho. |

Um campo só não tem nenhuma dessas perguntas. E o remendo do aceitador saiu.

### A hierarquia nova

```
account.settings.reset_nick          ← ENTRA (escopo do personagem)
account.settings.bc.reset_nick       ← SAI
account.settings.hh.reset_nick       ← SAI
account.settings.hh.modo_do_reset    ← FICA na HH
```

**O modo continua na HH** porque "solo ou fada" é decisão *daquela cave* — a BC
não tem modo nenhum. Já **quem** reseta é a mesma conta para as duas, e no modo
fada é ela que entra junto e cura.

### A migração — o ponto de maior risco

Quem já tinha o reseter configurado não pode abrir o bot e encontrar o campo em
branco. A regra:

1. `reset_nick` no nível da conta, se existir;
2. senão `bc.reset_nick`;
3. senão `hh.reset_nick`;
4. senão `team_reset.reset_nick` (v1/v2), e só se nada mais recente preencheu.

**O BC ganha quando as duas estão preenchidas** com nicks diferentes: era dele
que o bot de fato lia para vetar o farm e travar a entrada, então é o valor que
já estava em uso.

**E a migração LÊ DO BRUTO, antes do `_filtra`.** Isso não é detalhe: os blocos
`bc` e `hh` passam por `_filtra`, que descarta toda chave que não é campo da
dataclass. Com `reset_nick` fora de `BCConfig`/`HHConfig`, ler pelo objeto
jogaria o valor antigo fora **em silêncio** — nenhum erro, nenhum aviso, e o
usuário veria a conta de reset vazia. Travado por
`tests/test_conta_de_reset_unica.py`.

---

## Decisão 9 — o seletor mora na aba PERSONAGEM, nas duas interfaces

Nas **duas interfaces** (regra permanente do projeto):

* **PyQt6** — grupo *"Conta de reset (vale para TODAS as caves)"* na aba
  Personagem, logo depois de "Função desta conta". Saiu da aba BC (o grupo
  "Reset do boss" inteiro) e da aba HH (onde sobrou só o Modo).
* **Web** — sexta célula da grade da aba Personagem, ao lado de "Grupo". Duas
  linhas cheias de três campos, sem crescer a altura da aba e sem scroll novo.
  A aba BC perdeu o grupo "Reset do Time" e a "Rota na Cave" passou a ocupar a
  linha inteira.

**Continua LISTA FECHADA**, nas duas. O reseter precisa ser uma conta cadastrada
neste bot — é isso que permite ao bot perceber que ela caiu e segurar a entrada.
Nick de outra máquina é invisível daqui.

**A ponte também mudou:** `web_app.py` expõe e grava `reset_nick` no nível da
conta, ao lado de `accept_team_invites`. Removê-lo dos blocos de cave sem
adicionar aqui foi um erro que os testes pegaram — o editor mostraria a lista
sempre em "Nenhuma".

---

## Decisão 10 — o portão SUBIU para `bot/` e serve as duas caves

### O pedido

> *"O ecossistema HH precisa da mesma trava já existente no BC. Antes de rodar
> a cave, o HH deve checar se a Conta Reset global configurada está
> online/conectada. Se estiver offline, o bot HH DEVE pausar a rota, entrar em
> modo de espera e aguardar a reconexão."*

O pedido dizia *"clonando a lógica validada do BC"*. Ela foi **promovida** para
`bot/espera_do_reseter.py`, que é mais forte e é o que o `CLAUDE.md` exige
("REUSO PRIMÁRIO. Duplicação é inaceitável").

**E aqui não é preciosismo.** A parte difícil da trava não é esperar — é
distinguir:

| estado | desfecho | por quê |
|---|---|---|
| **o reseter caiu** | espera, ele volta | relogin é o comportamento padrão de toda conta, então a espera tem fim |
| **o reseter não existe mais** | desliga o farm da cave, salva, avisa | removido, desativado, desmarcado, posto para farmar ou aposentado por senha errada NÃO volta — esperar seria uma conta parada a noite inteira |

Uma cópia que errasse essa distinção perderia runs ou travaria para sempre, e o
sintoma apareceria horas depois sem apontar para a causa. É por isso que a
condição é reavaliada **a cada volta**, e não só na entrada: `problema_do_reset`
lê a configuração VIVA.

### O que NÃO subiu, e por quê

**Onde cada cave trava.** Cada uma tem um ponto de não-retorno diferente:

* **BC** — no `_do_entrar`, depois de conquistar a coordenada de entrada e antes
  do convite. A run em curso termina inteira e o personagem estaciona no ponto
  que já conquistou.
* **HH** — no `_garantir_o_time`, depois do `estado_do_time` e antes do convite.
  Quem já está em time não precisa de convite, então não faz sentido esperar por
  quem convidar. E travar mais cedo (no `SITUAR`, no `ATE_A_PORTA`) pararia a
  conta por um problema que só afeta a entrada, jogando fora a travessia já
  feita.

Ver `docs/INVARIANTES.md`, "Decisão de cave NÃO mora em código compartilhado".

### O interruptor certo é desligado

O BC fazia `ctx.account.bc_farm = False` direto. Compartilhado, isso viraria
"desliga o BC mesmo quando é a HH que está travada". Entrou
`BotContext.desligar_o_farm_desta_cave()`, **espelho de
`_a_cave_continua_ligada`** e ao lado dela de propósito: são a mesma tabela
de-cave-para-interruptor lida nos dois sentidos, e duas cópias divergiriam em
silêncio.

Sem saber qual cave é, desliga **as duas** — direção segura: quem chega ali já
concluiu que o farm não pode continuar.

### A espera não congela nada

* cada conta roda **na thread dela** (`AccountSupervisor`), então nenhuma espera
  aqui toca a thread da interface — nem a PyQt6 nem a webview;
* é `ctx.tick`, **nunca** `time.sleep`: é o `tick` que mantém o watchdog desta
  conta vivo enquanto ela está parada (uma conta de cave também cai, e parada
  por horas num `sleep` ela ficaria cega para a própria queda);
* é ele que dá as três saídas de graça — Parar, desmarcar o farm da cave
  (`FarmDesligado`) e ligar o modo APP.

### Os números da espera

| constante | valor | natureza |
|---|---|---|
| `PASSO_DA_ESPERA_DO_RESETER` | 1,0 s | **derivado**: quem responde é uma leitura de dicionário em memória, e a trava dura minutos (um relogin inteiro), não milissegundos |
| `INTERVALO_DO_AVISO_DO_RESETER` | 300 s | **cosmético**: uma linha escrita quarenta minutos atrás não avisa ninguém |

A prova de que o reseter está no ar é o **batimento** (`mural.reseter_online`,
`SILENCIO_MAXIMO = 5 s`), e não uma checagem de processo/janela/memória — uma
conta em modo APP passa em todas essas provas e nunca aceita convite nenhum. Ver
o cabeçalho de `bot/mural.py`.

---

## O que NÃO foi feito, e por quê

- **Badge/estado visual próprio para "travado" nas interfaces.** A mensagem de
  status já diz tudo, e um estado visual novo é trabalho em *duas* interfaces por
  informação que a mensagem já dá. Se a trava se mostrar frequente, aí sim vale —
  com o dado de frequência na mão.
- **Contador de tempo travado nas estatísticas.** O cronômetro da run só começa
  **depois** do portão (no fim do preparo de entrada), então o tempo parado já
  fica fora das médias de graça. O que existe é uma linha de log ao liberar
  (*"Parado 14 min esperando 'X'"*) — sem ela, a queda de produtividade
  apareceria no fim do dia sem explicação.
- **Encurtar o backoff de relogin para quem é reseter.** Ver
  `login-e-relogin.md`: o defeito real do backoff era outro, e foi consertado.
  Mexer no valor exigiria medição que ninguém tem.
