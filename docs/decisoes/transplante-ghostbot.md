# Transplante do GhostBot — o que veio, o que ficou, e por quê

**Data**: 2026-08-18
**Origem**: `GhostBot` (`github.com/chestm007/GhostBot`), bot de terceiro para o
mesmo jogo. 5.759 linhas de Python, 82 arquivos.

---

## AVISO DE LICENÇA — leia antes de copiar qualquer coisa

O GhostBot é **GPL-2.0** (`pyproject.toml`, `LICENSE` na raiz). Algoritmo e
técnica não são protegidos; **expressão de código é**. Copiar trecho dele para
cá contaminaria o BlazesBot com GPL.

**Nada foi copiado.** Tudo o que entrou foi reescrito do zero a partir da
técnica, em idioma e convenção desta casa. Mantenha assim.

---

## O achado que reclassificou três defeitos

Boa parte do `core/memory.py` já vinha do GhostBot — está dito no próprio
arquivo, na linha do `ADDR_TEAM_SIZE`: *"Descoberto no GhostBot"*. Já estavam
portados `ADDR_MODAL`, `ADDR_TARGET_ID`, `ADDR_LOOT_WINDOW`,
`ADDR_NOTIFICATION`, `ADDR_SYSTEM_MENU`, `ADDR_CAMERA`, `ADDR_TEAM_SIZE`,
`ADDR_ENTITY_SCAN_BASE`, `CHAIN_TARGET_*`, `CHAIN_BAG_*`, `CHAIN_DIALOG`,
`CHAIN_SUR_FIRST` e os `OFF_*` do jogador.

**O que veio junto e não estava dito: aqueles valores são da versão 6139 do
cliente.** O jogo está na 6400, e entre as duas o segmento de dados andou
**+0x60**. Isso já tinha sido medido e corrigido em DOIS endereços:

| constante | 6139 | 6400 |
|---|---|---|
| `PLAYER_BASE_RVA` | `0x00D450EC` | `0x00D4514C` |
| `ADDR_UI_ROOT` | `0x012CE2E0` | `0x012CE340` |

E os vizinhos do mesmo banco ficaram para trás. São exatamente as leituras que
o projeto documentava como quebradas:

| constante | valor herdado | candidato +0x60 | o que o projeto dizia |
|---|---|---|---|
| `ADDR_SURROUNDINGS` | `0x012CE2DC` | `0x012CE33C` | *"a leitura de arredores por memória não funciona neste cliente"* |
| `ADDR_MODAL` | `0x012CE35C` | `0x012CE3BC` | *"`ADDR_MODAL` está errado, `modal_open()` é sempre False"* |
| `ADDR_TEAM_SIZE` | `0x0106D328` | `0x0106D388` | *"a confirmação dependia de `team_size()`, e essa leitura não funciona"* |

A aritmética do primeiro é o apoio mais forte da hipótese:
`0x012CE2DC + 0x60 = 0x012CE33C`, que é **`ADDR_UI_ROOT - 4`**. Nas DUAS versões
o campo dos arredores fica um DWORD abaixo da raiz de UI. Não é coincidência: é
a mesma tabela.

**A lição, e ela vale além deste caso:** constante dependente de versão nunca é
uma constante — é uma medição com prazo. Rebasear uma e deixar as vizinhas cria
um defeito que se disfarça de limitação do ambiente, que é a forma mais duradoura
de defeito. *"Não funciona neste cliente"* virou um fato arquivado, e não era.

### Por que não trocamos a constante e pronto

Porque isso repetiria o erro que estamos consertando: enfiar no código um
endereço que ninguém mediu NESTE cliente. O `+0x60` é hipótese forte, não fato.

`core/rebase.py` mede os dois e escolhe, com um piso inegociável — **nunca ficar
pior que hoje**:

    candidato PLAUSÍVEL  e  atual NÃO plausível   ->  troca
    qualquer outro caso                           ->  mantém o atual

**"Ambos plausíveis" não troca.** Um endereço errado que por acaso lê um valor na
faixa esperada é o modo de falha mais caro que existe aqui — ler lixo com sucesso
é pior que não ler, que é a mesma regra do `memory.resolve`.

Decide **uma vez por rótulo, por processo**, e guarda. Decisão INCONCLUSIVA
(nenhum dos dois respondeu) **não** é guardada: o painel de arredores só produz
texto quando está ABERTO, e cravar a resposta com ele fechado seria decidir no
vazio.

Travado por `tests/test_rebase_de_endereco.py` (18 casos, lógica pura, sem jogo).

---

## O segundo achado: a detecção de time estava CEGA pelas duas vias

Além de `team_size()` não responder, `bot/team.py` carrega
`TEAM_MEMBER_TEMPLATE = "state_team_member.png"` — e **esse arquivo nunca
existiu** em `data/templates/`. `templates.load()` devolve `None`,
`_time_pela_imagem()` devolve `None`, `estado_do_time` devolve `None` sempre.

O preço está medido no próprio `team.py`: onze aceites falsos seguidos para um
único convite.

`14-RECORTAR-TIME.bat` conserta a segunda via sem ninguém medir nada com régua.
O painel de membro **se repete** — cada companheiro desenha a mesma moldura, uma
abaixo da outra, com espaçamento uniforme. Então um bom recorte é aquele que,
procurado no próprio quadro, **se acha N vezes em intervalos regulares**. A
ferramenta varre candidatos, procura cada um com `find_all_templates` (a MESMA
função que vai consumir o template depois), recusa recorte liso, e fica com o
que mais se repete de forma regular. Desenha o que achou num JPEG e grava o PNG.

**O critério de aceite é o mesmo que o consumidor usa** — um template que passa
ali é um template que funciona lá, não "parece certo na imagem".

Travado por `tests/test_recorte_do_time.py`, com quadros **sintéticos**: um teste
que dependesse de captura real do cliente não rodaria em máquina nenhuma sem o
jogo instalado, logado e com o time formado — e teste que não roda não trava nada.

---

## O terceiro achado: a tecla ficou em `SendMessageW`

O clique migrou para `PostMessageW` em 18/08/2026. A tecla não.

E o prêmio do PostMessage nunca foi o stuttering — está em
`stuttering-mouse.md`: **`SendMessageW` não tem timeout.** Um cliente que para
de bombear a fila (o cenário do "Connection interrupted", que este bot existe
para detectar) prende a thread daquela conta **para sempre**. O
`watchdog.check()` que dispararia o relogin nunca é alcançado, e a conta morre
em silêncio dizendo "Rodando".

Com a tecla em `SendMessageW` esse defeito continuava inteiro, e nos piores
lugares: o ecossistema APP é 100% teclado, o BC aperta tecla o tempo todo, e o
login digita usuário e senha — travar ali é travar na tela onde o cliente mais
costuma parar de responder.

`MODO_DE_TECLA = "postmessage"`. O `lParam` segue em zero de propósito: mudar o
mecanismo E o conteúdo da mensagem no mesmo passo tornaria impossível saber a
qual dos dois creditar uma regressão.

---

## O quarto achado: o `wait` composto não acordava

`_AnyEvent` compõe o stop GLOBAL e o `own_stop`, mas o `wait` era
`self._eventos[-1].wait(timeout)` — só o próprio. Acionar o global não acordava
ninguém.

O estrago não ficava no `supervisor.py`: como o `wait` não era confiável,
`BotContext.tick()` cumpria toda espera em fatias de 0,025 s de `time.sleep`
conferindo a flag entre elas — **40 acordadas por segundo, por conta**, para
quase sempre não encontrar nada. O polling era a compensação de um `wait`
quebrado.

Duas metades: `BotManager.stop()` faz **fan-out** para o `own_stop` de cada
supervisor (a propagação vai no escritor, porque parar é raro e esperar é o
caminho quente), e o `wait` fatia por `TETO_DA_FATIA_DE_ESPERA = 0.25` como rede
para quem acionar o global sem passar pelo fan-out. `FATIA_DA_ESPERA` passou de
0,025 para 0,25 e **mudou de significado**: não é mais a latência do Parar (que
virou zero), é a cadência do watchdog dentro de esperas longas.

Travado por `tests/test_parada_acorda_na_hora.py`.

---

## O que o GhostBot faz de excepcional (e ainda não entrou)

Fica registrado para os lotes seguintes:

1. **Comportamento é objeto numa lista, não fase numa máquina de estados.** O
   laço dele é `for function in functions: function.run()`, e cada função se
   auto-porteira. Ligar/desligar por conta é omitir da lista.
2. **`@run_at_interval`** transforma "espera um intervalo antes da primeira vez"
   e "não rode em combate" em DECLARAÇÃO, em vez de repetir a lógica em cada
   rotina. É o `feed_on_start` do pet, generalizado.
3. **Travamento por N sinais independentes de progresso** (`AttackContext`): só
   é travado se NENHUM dos sinais mudou no prazo; qualquer um rearma o relógio.
4. **Coordenação entre contas** (`Fairy`): uma conta lê o HP das OUTRAS pela
   memória delas, não por pixel, e cura a mais fraca clicando no slot do time.
5. **Clique posicional que limpa o alvo antes e confere pelo movimento depois**,
   com anel de offsets e `for/else` para "esgotou".
6. **NPC localizado por coordenada real** lida do painel de arredores, em vez de
   ponto de parada decorado.
7. **`selectors` no IPC**: bloqueio no kernel em vez de polling.

**Confirmação independente que ele deu de graça:** a escala do minimapa dele é
`(-1.7, 1.7)` — o mesmo `MINIMAP_SCALE` medido aqui, e ele explicita que **o eixo
X é NEGADO**. E o `_sell_items` dele clica o mesmo slot 24 vezes antes do Sell,
confirmando a regra da grade que COMPACTA.

---

## LISTA DE DESCARTE — não reintroduzir

Isto existe para que ninguém "redescubra" essas funções daqui a um ano.

- **`pointers.search_id()`** — varredura de força bruta de `0x0000CE00` a
  `0x0EFFFFFF` de 4 em 4 bytes: **até 62 milhões de `ReadProcessMemory` por
  chamada**, com `print()` dentro. A pior função das duas bases.
- **`lib/utils.with_timeout()`** — `Thread` + `join(timeout)` e, ao estourar,
  levanta **deixando a thread rodando para sempre**. Combinada com `search_id`
  (é assim que `target_location` a usa), vaza uma thread queimando um núcleo,
  uma por chamada.
- **Toda a camada de I/O dele.** Captura sem pool (aloca e destrói DC + bitmap a
  cada quadro), `cv2.imread` do disco a cada busca de template, `SendMessage`
  síncrono, 200 ms de sleep por clique, `MAKELONG` que quebra com coordenada
  negativa, zero proteção contra o cursor físico. Este projeto está à frente em
  cada ponto.
- **`get_with_case()` + `type_keys()`** — o mapeamento de tecla está tão errado
  (`vk + 0x20` para maiúscula) que a chamada precisa de `.swapcase()` para
  compensar.
- **`var_or_none()`** — 50 linhas reinventando coerção, com ramos impossíveis.
- **`lib/math.linear_distance`** — aplica `abs` a cada componente antes do
  `math.hypot`, que já eleva ao quadrado.
- **`functions/script.py`** e **`stats.py`** — inacabados (`_run` devolve `None`,
  `NotImplementedError`).
- **`LoginLock`** — `acquire` nunca é chamado no caminho de login, e o "lock" é
  atributo de classe com corrida check-then-set. Só a IDEIA presta (liberar em
  server-select, não no fim do login).
- **`Message.from_json_handling_multiple`** — desfaz coalescência de TCP com
  `replace('}{', ...)`, e parte no meio de qualquer payload com objeto aninhado.

### Defeitos dele que vale conhecer, para não repetir ao portar a técnica

1. **`Attack._cur_attack_queue = []` é atributo de CLASSE** — todas as contas dão
   `pop(0)` na MESMA fila de rotação. Mesmo padrão em `Fairy._team_members`,
   `ImageFinder.items`, `LoginLock._waiting`. Mutável em classe é estado global
   disfarçado.
2. **`_battle_pots` tem as teclas trocadas** — testa `battle_hp_pot` com
   `battle_mana_threshold` e aperta `battle_mana_pot`. Os dois blocos espelham o
   erro.
3. **`get_x()`/`get_y()`**: `x > 0 and math.floor(x) or math.ceil(x)` devolve `1`
   quando `0 < x < 1`, porque `floor(x)` é `0` e cai no `or`. O idioma `and/or`
   como ternário quebra sempre que o valor legítimo é falsy.
4. **`if 0 > client.level >= 89:`** — condição impossível, guarda morta.
5. **`DC_POINTER` e `CONFIRM_BOX_POINTER` são o MESMO endereço** com significados
   diferentes. Isso é o que já estava registrado aqui como *"contextual"*, e é a
   razão de `modal_open()` poder continuar não confiável **mesmo depois do
   rebase** — o rebase conserta o endereço, não a ambiguidade do campo.
6. **`should_run` consulta `in_battle` (uma syscall) ANTES do relógio**, em toda
   passada e para toda rotina, num laço sem espera nenhuma.

---

## Regras que nasceram daqui

Estão no `CLAUDE.md`; o porquê medido está acima e nos arquivos de área:

- `docs/decisoes/cliques-e-resolucao.md` — `MODO_DE_TECLA`.
- `docs/decisoes/sistema.md` — `_AnyEvent`, `FATIA_DA_ESPERA`, o índice de
  constantes.

---

# Catador de loot e esconder jogadores — o saque dos OUTROS bots

**Data**: 2026-08-19. Origem: `OutrosBots/T-R0XX-BOT-V1.8.3` e
`OutrosBots/AutoFarmBot`. O GhostBot **não tem** nada disso — só os ponteiros
`is_loot()`/`loot_window()`, que ele nem chega a usar.

## O problema, na palavra do usuário

O pet com a skill **auto pick** recolhe os itens sozinho. Nem todo pet tem —
uma conta dele tem, outra não. Como o bot é para ser automático, a conta sem o
pet certo precisa catar na mão. **Por isso o gatilho é por CONTA**
(`AccountSettings.usar_catador`), e não global: um interruptor global obrigaria
a escolha errada para metade das contas.

## Três implementações encontradas, duas aproveitadas

| # | onde | o que faz | veredito |
|---|---|---|---|
| 1 | `T-R0XX.bc_manual_auto_pick` | anel de 8 cliques direitos em cruz ao redor do centro da tela, depois clique no "Pick Up" | **o esqueleto** — por mensagem de janela, sem mouse físico. Mas é CEGO |
| 2 | `AutoFarmBot.auto_pick` | grade 5×5, e depois de CADA clique procura o botão na tela; achou, clica e para; aborta se o HP cair | **a lógica** — mas usa `pyautogui`, que move o mouse FÍSICO |
| 3 | `T-R0XX.autopick` | lê `is_loot()`, e **escreve a posição do cadáver por cima da do personagem** para o loot cair no pé | **DESCARTADO**: `write_position` é proibido aqui |

O que ficou: o anel e a mensagem de janela do #1, a conferência a cada clique do
#2. E a conferência aqui é melhor que a dos dois, porque este projeto pergunta à
MEMÓRIA (`loot_window_open()`) em vez de procurar um botão na tela — leitura de
microssegundos que não fala com o jogo.

**Custo: ~0,3 s no caso comum, contra os ~3,8 s fixos do T-R0XX.**

## O risco estava invertido, e isso decidiu o desenho

O instinto — e o `CLAUDE.md` em cinco lugares — diz que o perigo é o clique que
cai na cena 3D e faz o personagem ANDAR. Então o anel de oito cliques parecia
ser o problema.

**É o contrário.** O usuário corrigiu: neste jogo quem move o personagem é o
botão **ESQUERDO**; o direito interage. Então o anel de direitos é livre, e o
clique perigoso é o **ÚLTIMO** — o esquerdo no "Pick Up", que sem a janela de
loot aberta cai na cena 3D e manda o personagem andar **a segundos da saída da
cave**.

Por isso a regra do módulo: *o clique esquerdo só sai com a janela CONFIRMADA*.
Travado por `test_o_clique_esquerdo_so_sai_com_a_janela_confirmada`, com dente —
a versão cega do T-R0XX faz o teste reprovar.

## Três peças já estavam portadas, e nenhuma ligada

`coords["loot"]` (505,390), `coords["pickup"]` (447,479) e
`memory.loot_window_open()` já existiam no BlazesBot, vindas do T-R0XX, e
**nenhuma era lida por linha nenhuma**. Faltava só a função.

Não foram usadas as variantes de BC do T-R0XX (`center_screen` 510,370 e
`pick_up` 450,478): 5 px e 3 px de diferença, sem medição neste cliente.

## Esconder jogadores: um bug do cliente, e o perigo dele

O usuário descreveu o truque: com a tecla de esconder (F12) **presa**, abrir o
chat com Enter faz o esconder **grudar** pela sessão. Solta-se a tecla e
fecha-se o chat com outro Enter.

É por sessão, e apertar a tecla de novo desfaz — inclusive sem querer. Por isso
roda **antes de CADA entrada na cave**, não uma vez no login.

**O perigo é o chat ficar aberto.** A sequência o abre de propósito; se o Enter
de fechar não pegar, toda tecla do bot daí em diante — skill, poção, montaria,
TAB — vai para o campo de texto em vez de ir para o jogo. O bot parece rodando e
não faz nada, e um Enter posterior **publica** aquilo no chat do jogo. É a classe
de defeito que este projeto persegue — a ação que parece ter acontecido e não
aconteceu — com o agravante de o desfecho ser público.

Duas defesas:

1. **A tecla é solta num `finally`.** Presa, o bot inteiro passa a jogar com ela
   apertada. Travado por `test_a_tecla_e_sempre_solta_mesmo_com_excecao`.
2. **O fechamento é CONFERIDO** por template, e a entrada na cave é **abortada**
   se não fechar.

### O template é a CARINHA, não a barra

O usuário apontou: recortar a barra inteira pegaria o texto ao lado do `say:`,
que muda — um template com texto variável envelhece na primeira mensagem. A
carinha amarela no fim da barra só existe com o chat aberto.

O recorte não foi feito no olho: a carinha é o único ponto de amarelo saturado
naquela faixa, então foi achada por **cor** (HSV, matiz 18-38, saturação e valor
altos) e validada procurando-a de volta no próprio quadro — **um único casamento,
até com limiar 0,95**. Daí `LIMIAR_DO_CHAT_ABERTO = 0.90`.

### A armadilha do conserto: Enter ALTERNA

Apertar Enter "por garantia" sem saber o estado tem **metade de chance de ABRIR**
o que se queria fechar. Por isso, com a leitura sem resposta, o módulo **não
aperta nada** e devolve `None` — deixar como está é melhor que apostar. E `None`
não conta como seguro: sem confirmação, a entrada na cave não acontece.

## O que NÃO entrou

`bc_hide_players` do T-R0XX (segurar a tecla durante o autopick) ficou de fora:
o truque do F12 resolve melhor e vale para a sessão inteira. E `debug_pet_ap`,
apesar do nome, não checa auto-pick de pet nenhum — são dois cliques direitos
perto do ponto de "stop" a cada 3 s.

### O F12 nasceu DESLIGADO (19/08/2026)

Decisão do usuário no mesmo dia: *"comenta o bug do F12, para testar outra hora,
por enquanto vamos deixar sem ele"*. O pedido foi para COMENTAR; entrou como
`ATIVADO = False`, que é a convenção da casa — *"Interruptor, não comentário nem
apagar... com os testes forçando o caminho ligado para ele não apodrecer."*

A diferença importa mais aqui que no caso comum. Este módulo **abre o chat de
propósito**, e o que o torna seguro é a conferência de que ele fechou. Código
comentado não roda em teste nenhum: quem descomentasse meses depois estaria
ligando a parte perigosa com a proteção nunca exercitada. `ATIVADO = False`
mantém a sequência inteira sendo verificada a cada corrida da suíte, via um
`autouse` que força `True` no módulo de teste.

**E o desligado não pode bloquear a entrada na cave.** É a única coisa da
entrada que pode abortá-la, então um `seguro_para_seguir` falso no caminho
desligado faria desligar uma conveniência quebrar o farm inteiro. Travado por
`test_desligado_NAO_bloqueia_a_entrada_na_cave`.

O catador continua LIGADO e independente: ele não depende do esconder para
funcionar — o covil do boss é instância, então não costuma haver estranho em
cima do cadáver.

### CORREÇÃO no mesmo dia: o botão é achado por IMAGEM, não por coordenada

A primeira versão do catador clicava em `coords.pickup` (447,479) e usava
`loot_window_open()` como critério de parada. O usuário corrigiu: o botão é o
**"Pick up all"**, e *"até ele sumir deve ficar clicando nele... quando sumir o
botão aí de fato pode abrir o inventário"*.

A correção melhora três coisas de uma vez, e a primeira é a que importa:

1. **Segurança por construção.** O clique ESQUERDO é o único que move o
   personagem. Clicar numa coordenada fixa é clicar onde o botão DEVERIA estar;
   clicar onde ele foi VISTO significa que, sem botão, não há coordenada para
   clicar. Deixa de ser "protegido por uma checagem" e passa a ser impossível.
2. **Critério de parada observável.** "O botão sumiu" é o próprio jogo dizendo
   que pegou tudo.
3. **Não depende de `ADDR_LOOT_WINDOW`**, que é mais um endereço herdado do
   GhostBot na versão 6139 e **nunca confirmado neste cliente**. Ele continua
   sendo lido, mas só vai para o LOG — é o jeito barato de descobrir ao longo
   das primeiras noites se ele responde. Não decide nada.

O template (`btn_pick_up_all.png`, 82×20) veio de captura do usuário. O botão é
**relocalizado a cada volta** em vez de clicado sempre no mesmo ponto: custa uma
captura e cobre a janela ter se movido ou uma segunda ter aberto em outro lugar.

`TETO_DE_CLIQUES = 10` é rede de segurança, no mesmo espírito de
`max_heal_seconds`: quem decide é o botão sumir, e o teto só existe para que uma
janela travada não prenda a run com o boss já morto e a instância gasta. Dez
cliques a ~0,4 s são ~4 s no pior caso — travado por teste, para a rede não
passar a custar mais que o problema que evita.

Dois dentes: a versão de coordenada fixa clica com o esquerdo sem loot no chão
(reprova), e a versão de um clique só deixa o botão na tela (reprova).

### O F12 hoje: PRESO durante o par de cliques no NPC (19/08/2026)

O truque do chat continua `ATIVADO = False`, guardado para teste futuro. A forma
que roda é outra, e é do usuário:

> *"em vez de tentar o bug, você vai deixar apertada o F12... toda vez que for
> apertar no NPC precisa clicar o F12; sempre que precisar o clique no NPC fora
> da cave é importante que o F12 esteja apertado... só no par de clique, porque
> só atrapalha quando tenta clicar no NPC em si."*

**A regra dele é melhor que os três blocos que eu havia proposto**, e por um
motivo estrutural: TODO clique de NPC do bot passa por um lugar só,
`UIService._abrir_dialogo_e_clicar`. Um `with` ali cobre o link da cave, o Rich,
o Altar Stone e a saída — e nenhum clique de NPC futuro esquece de se proteger.
Travado por um teste que lê o AST da função.

`core.esconder_jogadores.segurado(...)` é context manager e não duas chamadas
porque as saídas deste trecho são muitas: fim normal, `StopRequested`,
`Disconnected`, `FarmDesligado` e qualquer falha do clique. **Tecla presa que não
é solta faz o bot passar o resto da sessão jogando com ela apertada.**

**O que NÃO está medido, e é honesto dizer:** `Input.key_down` manda um
`WM_KEYDOWN`. Se o jogo trata a mensagem e guarda a própria flag até o `WM_KEYUP`,
a tecla conta como presa; se ele consulta `GetAsyncKeyState`, mensagem nenhuma o
convence — e foi exatamente essa suposição não medida que motivou a DLL
abandonada de dois dias (`dll-cursor-hook.md`).

A favor: o `key()` normal faz skill e poção saírem, então o jogo REAGE à mensagem.
Contra: ninguém mediu ESTE caso. O usuário optou por conferir na tela — as outras
contas dele são os "outros jogadores" na entrada da cave e no vendedor, então se
funcionar elas desaparecem. Por isso o log diz quando segurou e quando soltou:
sem isso não há como separar "não funciona" de "não rodou".

**Custo de errar: zero** — uma mensagem ignorada pelo cliente.

O usuário também revelou que usa um programa de terceiro que faz o esconder por
sessão E um "esquema de pet bug" que ajuda a não tomar disconnect, sem ter o
código. Fica registrado como pista: se o disconnect voltar a incomodar, o pet é
onde procurar.

#### O bloco ficou LONGO, e o motivo é a fila de mensagens

Primeira versão: F12 preso só em volta do par de cliques. O usuário observou que
não presta — *"clicar só pelo tempo do clique acaba fazendo não clicar direito,
principalmente ao entrar na cave"*.

**O mecanismo é a fila POSTADA.** Com `MODO_DE_CLIQUE = "postmessage_puro"` as
quatro mensagens do clique vão para a fila da janela. O `WM_KEYDOWN` e o
`WM_KEYUP` do F12 entram na MESMA fila, imediatamente antes e depois delas —
então o cliente processa a tecla no meio do clique. Segurar durante o processo
inteiro tira as mensagens da tecla de perto das mensagens do clique.

É a mesma família de lição que já derrubou o `postmessage_hibrido` e o
`sendmessage_rapido_reafirmado`: **o que estraga o clique é mensagem alheia
encostada nele na fila**, e a correção nunca é "mandar mais", é afastar.

Os três blocos ficaram em `tentar_entrar_na_cave`, `viajar_para_ghost_din_woods` e
`VendorService._open_npc` — exatamente os três momentos que o usuário nomeou.

#### Aninhar exigiu CONTAGEM

O `with` de dentro de `_abrir_dialogo_e_clicar` continua lá, como rede para
qualquer clique de NPC futuro. Com os blocos longos por fora, a mesma tecla passa
a ser segurada duas vezes — e sem contagem o bloco INTERNO soltaria a tecla
enquanto o externo ainda a queria.

**O defeito seria invisível:** o clique do NPC rodaria protegido, o resto do
processo (caminhada, conferência de coordenada, tentativas seguintes) rodaria
desprotegido, e o log das duas vezes diria "segurei".

`Input.key_down` passou a contar por tecla: `WM_KEYDOWN` na primeira chamada,
`WM_KEYUP` só quando o contador volta a zero. **O contador é por `Input`, ou seja
por janela** — cinco contas em paralelo têm cinco contadores, e uma não solta a
tecla da outra.

`key_up` sem `key_down` correspondente manda um KEYUP solto de propósito: é rede
para tecla presa por descuido, e um KEYUP de tecla não apertada é ignorado pelo
jogo. Soltar por engano é o lado seguro do erro.

---

# O `BlazesBot - PetBug.exe`: o esconder jogadores saiu do bot

**Data**: 2026-08-19. Decisão do usuário: *"por enquanto desativa esse click no
F12, em vez disso você vai executar esse arquivo."*

## O que o programa faz, e por que ele ganha do F12

É um programa de terceiro que o usuário já usava, e ele faz DUAS coisas:

* o **esconder jogadores por sessão** — o mesmo efeito que o truque do F12
  tentava produzir, mas de verdade e sem depender de abrir o chat;
* um **"pet bug"** que, segundo ele, ajuda a não tomar disconnect — algo que o
  bot não tinha nem sabia fazer.

E o log dele diz *"Patch applied to all running clients"*: **um clique cobre
todos os clientes abertos**. O F12 preso protegia um processo de uma conta; isto
protege as cinco de uma vez, pela sessão inteira.

Não há código para portar — o usuário não o tem. Então o bot o OPERA.

## O pedido era coordenada fixa, e deu para fazer melhor

Ele autorizou o caminho simples: *"o botão Patch é fixo, não muda, então só
clicar no lugar fixo."* Ia funcionar. Mas inspecionar a janela mostrou outra
coisa:

    hwnd=1119894  classe='TButton'  texto='Patch'
    hwnd=202164   classe='TMemo'    (o log)

São controles Win32 reais (programa Delphi), e isso troca duas apostas por dois
fatos:

**1. O clique vai no `hwnd` do botão, por `BM_CLICK`.** Não há coordenada para
envelhecer, não há como errar o alvo, e **funciona com a janela minimizada** —
que é como ela costuma ficar. Medido: minimizada, `GetClientRect` devolve
`(0,0,0,0)`, então qualquer conta baseada em tamanho de tela falharia ali. A
coordenada fixa ficou como RESERVA, para nunca ser pior que o pedido original.

**2. O resultado é CONFERIDO.** `WM_GETTEXT` no `TMemo` devolve o que a janela
mostra, e é o próprio programa dizendo se aplicou. É a regra da casa — *a cada
clique, conferir se o esperado aconteceu* — aplicada a software de terceiro.

Detalhe que precisou de decisão: o programa reescreve **as mesmas três linhas** a
cada Patch. Exigir que o texto MUDE reprovaria uma aplicação bem-sucedida só
porque ela produziu a mesma saída — e da segunda vez em diante esse é o caso
comum, porque o gatilho é a cada queda. O que se exige é o texto DIZER que
aplicou.

## Renomear a janela: TENTADO, MEDIDO, NÃO FUNCIONA

O usuário pediu para renomear a janela para "BlazesBot - PetBug". Contra a janela
real:

    WM_GETTEXT              -> 'RaaskiBot - PetBug'
    SetWindowText(...)      -> sem erro
    SendMessage(WM_SETTEXT) -> devolveu 0        (recusado)
    WM_GETTEXT depois       -> 'RaaskiBot - PetBug'  (não mudou)

Formulário Delphi não aceita o `Caption` trocado de fora. **O código de rename foi
REMOVIDO em vez de ficar como tentativa**: função que provadamente não faz nada é
peso morto, e a próxima pessoa gastaria o mesmo tempo descobrindo o mesmo.

O usuário resolveu a parte que dava — renomeou o ARQUIVO. E a busca da janela é
pelo pedaço `"PetBug"`, escolhida justamente para sobreviver a um rename; ela
cobre os dois nomes de qualquer forma.

## Cinco contas, um clique

Cinco contas caem juntas com frequência — está medido na regra do login. Como um
clique cobre todos os clientes, cinco supervisores chamando isto ao mesmo tempo
produziriam cinco cliques idênticos.

`INTERVALO_MINIMO = 30 s`, com estado de módulo e lock (mesmo desenho do quadro de
convites do `bot/mural.py`, e pelo mesmo motivo: os supervisores rodam no mesmo
processo). **O intervalo é reservado ANTES de agir** — marcar depois deixaria duas
contas passarem pela janela de tempo enquanto a primeira ainda está clicando.

## Onde o gatilho mora

No começo de cada sessão do supervisor, depois do login e **só para contas com BC**
— o gatilho que o usuário pediu foi *"a cada vez que uma conta com Bot BC ativa
cair"*, e uma conta que caiu volta exatamente por ali, num cliente novo que o
patch anterior não alcançou. A primeira sessão também passa, o que é desejável: o
patch é necessário desde o começo.

**COMPLEMENTO:** falha nunca derruba a sessão. É programa de terceiro, e uma
conta logada e pronta para farmar não pode ser perdida porque um patcher externo
não respondeu.
