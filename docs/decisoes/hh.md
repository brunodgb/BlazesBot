# HH — Black Wind Camp Dungeon: o terceiro ecossistema

> **Aberto em 01/09/2026.** Registro da engenharia reversa do bot de terceiros
> em Lua/UoPilot (`D:\Versoes do Bot\OutrosBots\HH - cave full - ARVV3N`) e das
> decisões de integração ao BlazesBot. A **regra** de área mora em
> `docs/INVARIANTES.md` (seção "HH"); a **especificação** em `docs/REGRAS.md`.
> Aqui fica o **porquê**, incluindo o que foi REPROVADO e não deve voltar.

---

## 1. O QUE É A HH

Cave de boss-rush com **4 bosses**, em Talisman Online, cliente v6400. A zona
externa se chama **`Black Wind Camp Dungeon`** e o grupo do painel de arredores
diz **`Outside Black Wind Camp`** — ambos lidos da tela em 01/09/2026, não
inferidos. O apelido "HH" é do usuário e do bot original; o jogo não usa essa
sigla em nenhum lugar, e por isso ela **não entra em `core/lugares.py`**: lá vale
o nome que a memória devolve.

Os 4 bosses, com os rótulos que o bot Lua usa nos comentários:

| # | rótulo do Lua | ponto medido | trecho |
|---|---|---|---|
| 1 | **Fa-Yuan** | (273, 138) | 22 waypoints desde (80, 42) |
| 2 | **Dupla** (dois bosses juntos) | (410, 135) | 16 waypoints |
| 3 | **Green Robmaster** | (551, 192) | 12 waypoints |
| 4 | **Purple** (last) | (527, 108) | 15 waypoints |

**ATENÇÃO — os nomes acima NÃO estão medidos.** O bot Lua nunca compara nome de
alvo: os nomes existem só em comentários de `hh.lua`. O usuário confirmou que
são os certos ("pode usar os mesmos nomes que vai estar certo, só precisa fazer a
leitura correta disso"), então eles entram como **rótulo esperado**, e a leitura
de `TargetHybrid` confirma no primeiro contato. Divergência é **log**, nunca
bloqueio — bot mudo é pior que rótulo errado.

---

## 2. A ROTA DE CHEGADA — MEDIDA NA TELA, NÃO HERDADA DO LUA

O bot Lua **não faz esta rota**: ele clica o traço de missão (743, 251) e assume
que o personagem já está por perto. Isso só funciona porque o usuário posiciona
o personagem à mão antes de ligar o script. A rota real, ditada pelo usuário e
confirmada nas capturas de 01/09/2026:

```
Stone City
  └─ NPC "Transport Fay"                      (o MESMO da BC)
       └─ a lista de destinos precisa ser ROLADA ATÉ O FIM
            └─ link "West Suburb of Stone City"   (Need 5, Level 20)
                 └─ TP
                      └─ painel de Arredores, aba NPC, busca "Mutual"
                           └─ "Mutual Quest Woman [-358, -288]"
                                └─ andar até (-342, -288)
                                     └─ NPC "Elite Axe Monk Soldier"
                                          └─ entra na cave
```

### 2.1 Por que a rolagem da lista é um passo de primeira classe

`West Suburb of Stone City` **não aparece na primeira tela do diálogo**. A BC
nunca precisou rolar: `Ghost Din Woods` (Need 7, Level 48) está na parte visível
da lista. Confirmado nas duas primeiras capturas: sem rolar, a lista mostra de
`Sky Village` a `Star Town`; rolando até o fim aparecem
`West Suburb of Stone City`, `Beauty Village` e `Arm Broken Bluff`.

Consequência de projeto: `clicar_link()` sozinho **não serve** para a HH. Ele
procura o template e desiste em 3 tentativas — e o template nunca vai estar na
tela. Precisa de um passo de rolagem ANTES, e a rolagem tem de ser **verificada
pelo aparecimento do link**, não por número fixo de cliques na seta. Espera cega
na seta é exatamente o vício condenado do Lua (`miniMapMinimize`: 5 cliques ×
500 ms, incondicional).

### 2.2 Por que a busca por "Mutual" e não um waypoint

O painel de Arredores com busca por texto é a máquina que a BC já usa três
vezes (Fay, Skull Herald, Rich Man) — `UIService.buscar_npc()` +
`ir_para_resultado()`. Ela usa o *pathfinding do próprio jogo*, que atravessa a
geometria que um clique de minimapa não atravessa. Medir 30 waypoints novos do
TP até a entrada seria refazer à mão o que o jogo já faz de graça.

`Mutual Quest Woman` está em `(-358, -288)`; a coordenada de conversa é
`(-342, -288)`. **A distância entre as duas é o ponto todo:** o painel caminha
até PERTO (aceita folga por construção), e clicar de onde ele largar é o defeito
já medido na BC em 25/08/2026 — a 2 passos o clique caiu no White Eagle que
estava no caminho. Por isso `(-342, -288)` é encostado com o mesmo mecanismo do
`_encostar_na_fay` / `_no_ponto_do_vendedor`, e **não se clica de fora do ponto**.

### 2.3 A âncora do Lua confirma a coordenada

`hh.lua` usa `entrance = {-342, -286}` como o ponto de onde tenta entrar, e
`farmer.lua` usa `sellPos = {-344, -297}` para o vendedor. As duas ficam a menos
de 4 unidades de `(-342, -288)`. Ou seja: **a coordenada do usuário e a do bot
que roda hoje concordam**, o que é a confirmação mais forte disponível sem
medir de novo. O valor que entra no código é o do usuário, `(-342, -288)`, porque
é o que põe o personagem *de frente* para o Elite Axe Monk Soldier.

---

## 3. O VENDEDOR — `Roaming Apothecary`, FORA DA CAVE

Nível 30, do lado de fora, perto da entrada. Fluxo, ditado pelo usuário e
confirmado nas capturas:

```
clique DIREITO no Roaming Apothecary
  └─ link "Sell Item"
       └─ janela de venda (3 páginas, grade de slots, Total / Bind, Sell / Cancel)
            └─ vende a partir do slot X configurado
```

**É o fluxo da venda da BC com outro NPC.** A janela é a mesma (mesma moldura,
mesma grade, mesmo par Sell/Cancel, mesma paginação 1/3), então
`VendorService.sell_from_slot()` e toda a máquina de "confirmar slot vazio"
valem sem alteração. O que muda: o texto de busca do NPC (`Roaming` em vez de
`Rich`), o link (`Sell Item` em vez do link do Rich) e a coordenada.

Isso é **configuração de rota**, não código novo. Por isso `HHRoute` nasce com
`vendor_search_text` em vez de um `vendor_hh.py`.

Diferença relevante contra o Lua: `farmer.sellItems()` dá **30 cliques fixos**
num slot literal `(448, 327)` com 100 ms entre eles, sem saber se vendeu
alguma coisa — e antes disso navega por 5 cliques cegos de diálogo. A
`VendorService` confere slot vazio antes de clicar. Não há motivo para reproduzir
o comportamento cego.

---

## 4. O RESET — A CAVE NÃO RENASCE SOZINHA

**Regra do jogo, não do bot:** sem desfazer e refazer o time, os bosses não
renascem e a run seguinte não tem o que matar. É a mesma mecânica da BC.

A HH tem **dois modos**, e a diferença entre eles é o que a segunda conta faz
depois de entrar:

### 4.1 HH SOLO — idêntico à BC

```
conta de farm manda convite para a conta de reset
  └─ reset aceita
       └─ farm entra na cave
            └─ o time é DESFEITO
                 └─ começa a cave sozinho
```

A conta de reset nunca entra. Isto é exatamente `TeamService.montar_time()` +
`sair_do_time()` + `InviteAcceptor`, que já existem e já rodam em produção.

### 4.2 HH + FADA — o modo novo

```
conta de farm manda convite para a Fada
  └─ Fada aceita
       └─ AS DUAS entram na cave
            └─ a Fada ACOMPANHA o personagem e CURA quando precisa
                 └─ ao SAIR da cave: desfaz o time, refaz o time
                      └─ e só então pode entrar de novo
```

Três consequências de projeto, todas diferentes do que existe hoje:

1. **A Fada entra na instância.** Hoje a `FadaDoTime` roda parada, curando por
   fila do `mural`. Na HH ela precisa de deslocamento — seguir o líder. O bot
   Lua resolvia isso com a tecla de follow (`keys.follow = "p"`) e o clique no
   slot 1 do time (`cords.team.m1 = {31, 202}`); a `FadaDoTime` já sabe clicar
   no slot do time (`_slot_do_nick`), e o follow é uma tecla que ainda não existe
   em `KeyBinds`.
2. **O ciclo de time fica no fim da run, não no começo.** Na BC o time é montado
   ao chegar na porta e desfeito ao entrar. Na HH+Fada ele sobrevive à cave
   inteira e o desfaz-refaz acontece FORA, depois de sair. Isso muda quem é o
   dono do ciclo: sai do `ENTRAR` e vai para o `MANUTENCAO`.
3. **A Fada é uma conta do ecossistema APP hoje.** Ela é alcançada pela mesma
   porta do APP (`_sou_a_fada()` no supervisor). Convocá-la para a HH significa
   um terceiro caminho no `_operate`, e ela **não pode passar a importar de
   `hh/`** — a coordenação continua pelo `mural`, que é onde ela já lê.

### 4.3 Por que NÃO reaproveitar o `team.txt` do Lua

O bot Lua coordena Farmer e Reseter por **um arquivo de uma palavra**:
`Modules/team.txt`, valores `nil` | `team` | `cure` | `ready` | `solo`. Sem
lock, sem escrita atômica, sem dono, com os dois lados em polling de 0,5–2 s.
**REPROVADO** — o `mural` já resolve isso com época, líder e chave por conta.

Detalhe que fecha o assunto: a `reseter.lua` **nunca cura ninguém**.
`reseter.start()` senta, espera o token `"solo"`, levanta e sai;
`cureTarget`, `cureToStart`, `killBoss` e `revive` existem e **não são chamadas
por nenhum caminho**. A curandeira do bot original é código morto. A `FadaDoTime`
do BlazesBot já faz mais do que aquele arquivo inteiro se propunha a fazer.

---

## 5. OS 65 WAYPOINTS — O ÚNICO ATIVO QUE SOBREVIVE VERBATIM

Cada waypoint do Lua traz DOIS dados: a coordenada de destino (`xY`) e um
**clique de minimapa calibrado à mão** (`via`).

```lua
{xY = {80, 42}, via = {943, 104}},
```

O `via` existe porque o cálculo dinâmico de `travel.miniMap` trava em curva: ele
computa o clique a partir do centro fixo (919, 115), corta o passo pela metade
quando o ponto sai dos limites úteis (895–965 × 75–158) e, quando nada disso
funciona, usa o `via`. Ver `travel.lua:96-103`.

**Decisão:** o `via` entra no `mapa_hh.py` como **camada de RESERVA**, não como
via principal. O `Navigator` do BlazesBot tem detecção de travamento medida
(`SEM_PROGRESSO_SEGUNDOS`, `RUIDO_DA_POSICAO`), destravamento pelos vizinhos,
varredura em círculo e retomada de rota — tudo isso é melhor que um clique fixo.
O `via` é o que se tenta quando o motor medido desiste, e é gratuito guardá-lo.

**O que ainda falta medir:** o nome de ÁREA de cada waypoint. A `Waypoint` da BC
carrega `area`, e é ela que dá as três capacidades descritas em `mapa_bc.py`
(conferir onde está, saber sem a memória, reagir a rollback). Para a HH só
sabemos o nome de FORA. Por isso os waypoints da HH nascem com a área
`AREA_INTERNA_NAO_MEDIDA` — um marcador explícito, e não uma adivinhação
disfarçada de dado.

### 5.1 O ponto (232, 188)

`hh.lua` trata essa coordenada como caso especial em DOIS lugares
(`travelPath:280` e `travel.lua:91`): é um ponto onde os mobs bloqueiam a
passagem e o char fica parado. Entra no `mapa_hh` como waypoint problemático,
pela mesma mecânica de `mapa_bc.WAYPOINTS_PROBLEMATICOS`.

---

## 6. LÓGICAS CONDENADAS — NÃO PASSAM PARA O PYTHON

Levantadas na dissecação de 01/09/2026. Cada uma tem um substituto que já existe.

| # | vício no Lua | por que é condenado | substituto |
|---|---|---|---|
| A | **ponteiros resolvidos UMA vez, no `require`** — todo `local X_POINTER = readmem(...)` roda no load do módulo | a cadeia congela ali; troca de personagem, relog ou troca de zona ⇒ ponteiro velho lendo lixo, **em silêncio**. O próprio autor remendou `getTeam1Name()` (linha 313) para re-resolver a cada leitura, único no arquivo — prova de que bateu nisso | `Memory.resolve()` re-resolve a cada leitura; `read_*` devolve `None` em falha |
| B | `readmem` sem PID e sem validação | retorno `-1`/`0` entra como base aritmética do offset seguinte | `Memory` é por PID, com `critical_ok()` como portão |
| C | **`utility.getTargetHpPct` — régua de TELA disfarçada de memória**: `hpMin=460`, `hpMax=137`, e `isTargetHpFull()` compara com o literal `597` | o HP absoluto do alvo não está disponível: o bot não sabe o HP real de boss nenhum | `TargetHybrid.ler()` → `AlvoInfo`; `MorteDoAlvo` com trava por identidade |
| D | `utility.battleCheck()` — "estou em batalha?" = lê HP, espera 100 ms, lê de novo, caiu? | detecta batalha só enquanto se toma dano | `Memory.in_battle()` |
| E | **158 chamadas `wait()`** (`hh` 62, `farmer` 44, `reseter` 29, `items` 8, `travel` 8, `findimage` 3, `utility` 4) | espera cega paga sempre, mesmo quando o efeito já aconteceu. Pior caso medido no código: `findimage.findImage` dá `wait(1s)` **depois de toda busca, inclusive quando acha** — e `toggleFriendsList` chama isso até 4 vezes ⇒ ≥ 4 s para saber se uma janela está aberta | `BotContext.tick()`, fatiado em `FATIA_DA_ESPERA = 0.25` |
| F | **13 pontos de decisão por imagem**: `friendlist.bmp`, `inside.bmp`, `team_notification_{1,2,3}.bmp`, `destroy-item.bmp` + 54 bitmaps de item a 90 % | a memória responde todos. `inside.bmp` é o caso mais claro: a POSIÇÃO está disponível e é uma leitura de struct | `Memory.position()`, `location()`, `bag_open()`, `modal_open()`; `deletador.deletar_lixo()` |
| G | `findimage.lua` com `0,0,1024,768` hardcoded e `pixel.lua` com `X,Y = 8,31` hardcoded | **travado em resolução** | `coords._from_base(x, y, âncora)` |
| H | **14 labels de `goto`** (`RESTART`, `RUN`, `M1`, `ENTRANCE`, `ENTER`, `TEAM`, `CURE`, `AA`, `CLICK`, `WAIT`, `OUT`, `CUREBOSS`, `TEAMLEAVE`) | não-reentrante, não-testável e **não-parável**: não existe "Parar" no bot Lua — a única forma de interromper é matar o UoPilot | máquina de estados com `run(max_runs, should_continue)`, igual à BC |
| I | **37 laços sem teto** — `agreeTeam`, `closeConfirmOkUp` (zera o próprio contador em 10 e nunca desiste), `leaveTeam`, `reborn`, `checkHpPotion` | cada um é travamento permanente se o ponteiro por trás estiver velho. `checkHpPotion` é o pior: `while getHp() < getMaxHp(): send(potion)` **sem teto e sem verificar se a poção existe** ⇒ acabou a poção, laço infinito | teto + verificação de efeito, como `_esperar_o_efeito_da_pocao` |
| J | **`hh.exit()` está QUEBRADA**: `while X ~= outside[1] and Y ~= insidexY[2]` — `insidexY` é global vazada de `goToCave`, e o `and` (em vez de `or`) faz sair quando qualquer eixo casar | defeito real, não estilo | — |
| K | **`hh.hide()` é `while true do send_down(F12) return end`** — segura F12 e só solta em `unHide()`; script morre no meio ⇒ tecla presa | — | `esconder_jogadores.segurado()`, que solta em qualquer saída, inclusive exceção |
| L | **NENHUMA checagem de cap.** `getBagItems`, `getLastBagItems` e `getVenderBagItems` estão implementados em `pointers.lua:417-429` e **nunca são chamados** | vende toda run, cego, e transborda sem avisar | `Memory.bag_count()` + `BagConfig` + `VendorService.precisa_ir_vender()` |
| M | `autoPick` — **grade 5×5 de força bruta**: `x=370..750/90 × y=150..550/90`, 25 duplo-cliques-direito sempre | — | `catador.catar()`: anel de cliques, e o esquerdo só sai com o botão localizado |
| N | câmera escrita por `writemem` sobre ponteiro de *load-time*, precedida de um `double_left(869,59)` na tela | duas fontes de verdade para a mesma coisa. E `pointers_backup.lua` mostra a base da câmera já rebaseada uma vez (`0x01170054` → `0x0116FFF4`) — a mesma classe do `+0x60` de `docs/decisoes/transplante-ghostbot.md` | `Memory.set_camera` + `camera_na_pose_certa` |
| O | configuração É código-fonte: `TANK_NAME`, `MOUNT`, `POTION_PCT`, `DELETER_BOT`, `AUTOPICK` são globais nos `.txt`; `RESETER = 1` está hardcoded dentro de `hh.lua` | um personagem por cópia de pasta | `AccountSettings`, por conta, nas duas interfaces |
| P | `hh.print()` salva `getimage(0,0,1920,1080)` de um cliente 1024×768 | — | — |
| Q | `killBoss` e `killAtPosition` são a **mesma lógica em 3 cópias** (`farmer.lua:102`, `hh.lua:166`, e uma terceira embutida no laço de cura de `killAtPosition:220`) | três chances de só uma ser corrigida | uma função só |

---

## 7. O QUE O BOT LUA FAZ DE BOM (e é preservado)

Não é uma lista de cortesia — cada item aqui é uma decisão que o bot Lua tomou
certo e que custaria medição para redescobrir:

1. **Os 65 waypoints com clique calibrado.** O ativo.
2. **A sequência dos 4 bosses e as âncoras de posição.** Ordem 1→2→3→4 com
   trechos separados, e o retorno a (274, 139) depois do Fa-Yuan porque
   *"a cave é sinuosa, o atalho direto caía na parede e travava o char"*
   (`hh.lua:283`).
3. **`via` como reserva quando o cálculo dinâmico trava.** A ideia é boa; o que
   muda é a ordem (motor medido primeiro, `via` depois).
4. **Desmontar antes de lutar e remontar para andar.** `farmer.start` faz isso em
   todos os 4 bosses.
5. **Reiniciar de DENTRO quando revive lá.** `if ptr.getX() > 0 and ptr.getY() > 0
   then goto RUN` — reconhece que o respawn é dentro da cave (55, 33) e não
   tenta entrar de novo. É o mesmo papel do estado `SITUAR` da BC.
6. **Limpar mobs a cada 3 passos quando está a pé** (`travelPath:273`), e não
   limpar quando está montado. Decisão correta: montado o char não para.

---

## 8. DECISÕES DE ARQUITETURA (01/09/2026, aprovadas pelo usuário)

1. **HH é um ecossistema próprio**, `blazesbot/bot/hh/`. Não é um modo da BC:
   outra cave, outra rota, outro vendedor, outro ciclo de time.
2. **`bc/combat.py` e `bc/navigation.py` são promovidos** e usados
   pelos dois. Decisão explícita do usuário: *"se o bc/combat.py for útil para
   esse novo, transforme ele em global e use nos 2, mas tomando cuidado para um
   não interferir no outro"*. Copiar está proibido pela Diretiva de Reuso;
   importar `bc/` de dentro de `hh/` está bloqueado por
   `tests/test_ecossistemas.py`. Promover é o único caminho que sobra — e é o
   certo.
3. **`bc/ui_service.py` também sobe**, e este não estava no plano inicial. A
   descoberta que forçou: a rota da HH é `Fay → TP → Arredores → ponto → NPC`,
   ou seja, exatamente `viajar_para_...` + `buscar_npc` + `ir_para_resultado` +
   `garantir_coordenada_da_entrada` + `falar_com_npc`. Painel de arredores e
   diálogo de NPC são do JOGO, não da Bewitcher Cave.

   **CORREÇÃO DO PLANO (mesmo dia): o destino é `bot/`, não `core/`.** O
   relatório inicial disse `core/` para os três módulos grandes, e está errado —
   erro de arquitetura, não de escrita. `Navigator`, `CombatEngine` e `UIService`
   recebem `BotContext`, que mora em `bot/context.py`; levá-los para o `core/`
   faria o `core/` importar de `bot/`: dependência invertida, ciclo, e o `core/`
   deixa de ser reusável fora do bot. É exatamente o que
   `test_o_core_nao_conhece_ecossistema_nenhum` existe para reprovar, e a regra
   está certa.

   O destino é **`blazesbot/bot/`**, e não como consolo: o `CLAUDE.md` já define
   essa camada como *o SISTEMA — serve todos os ecossistemas*, e é onde o
   supervisor, o contexto, o login, o watchdog e o `TeamService` já moram, pelo
   mesmo motivo. O único que **fica no `core/` é o `core/rota.py`**, porque é
   função pura sobre coordenadas: não conhece `BotContext` e não precisa.

   A lição, para a próxima promoção: *o destino de um módulo é decidido pelo que
   ele IMPORTA, não pelo quanto ele parece genérico.*
4. **Nada é recriado.** Diretiva do usuário: *"tudo que já existir no nosso
   BlazesBot você não precisa recriar, apenas utilizar onde necessário."*
5. **O que fica em cada lado da promoção** está em `docs/INVARIANTES.md`,
   seção "HH".

### 8.1 O critério da promoção, aplicado

A pergunta é a de sempre: *isso é sobre o JOGO ou sobre o que este ecossistema
faz?*

| sobe para `core/` | fica no ecossistema |
|---|---|
| rotação de ataque, troca de alvo por TAB confirmada por id, esperar a flag de combate baixar, `heal_to_full`, `sentar_para_recuperar`, `ensure_pet`, `apply_buffs` | as FASES (guardas × boss da BC; os 4 bosses da HH), a trava do Cemetery Guard, o Package Courage |
| cálculo do clique de minimapa, detecção de travamento, destravamento pelos vizinhos, varredura em círculo, manutenção de montaria e pet em movimento | as ROTAS (`mapa_bc` × `mapa_hh`), as áreas apertadas, os textos de busca |
| painel de arredores, busca por NPC, ir ao resultado, par de cliques NPC+link com diálogo conferido, encostar no ponto exato | quais NPCs, quais links, quais coordenadas |

---

## 8.1 O QUE FOI MEDIDO NA TELA EM 03/09/2026

Prints guardados em `data/templates/entrada/` como evidência de onde cada número
saiu — sem eles, refazer um template daqui a seis meses é procurar a tela de
novo no jogo.

| o que | valor | de onde |
|---|---|---|
| **HH = `Happiness Hall`** | — | o link do diálogo diz *"Enter Happiness Hall"* |
| waypoint da porta | **(-342, -288)** | rótulo de `completa2.png`: `Black Wind Camp Dungeon [-342,-288]` |
| posição do Transport Fay | (178, -515) | rótulo de `completa1.png` — confirma `stone_city.POSICAO_DA_FAY` |
| primeiro link do diálogo | cliente (302, 361) | derivado do recorte de `completa2.png` |
| ponto do `Roaming Apothecary` | (475, 450) | medido pelo usuário, com o personagem no waypoint |
| ponto de venda | **o MESMO da porta** | o print mostra o vendedor abaixo do personagem e o NPC da cave acima, na escada |

### `Happiness Hall` NÃO é o nome do lugar

A **zona** se chama `Black Wind Camp Dungeon` — é o que a memória devolve, e o
que entra em `core/lugares.py`. `Happiness Hall` é o nome da **instância**, e ele
aparece em um lugar só: o link de entrar. Confundir os dois faria a validação de
lugar rejeitar a leitura da memória.

### Os três templates, e o que o primeiro ensinou

| arquivo | tamanho | de onde |
|---|---|---|
| `link_west_suburb.png` | 151×18 | `completa1.png` |
| `link_enter_hh.png` | 126×20 | `completa2.png` |
| `dialogo_seta_baixo.png` | 15×19 | a seta ▼ do diálogo do Fay |

Duas correções foram necessárias, e as duas viraram teste:

1. **O primeiro `link_enter_hh.png` era a TELA INTEIRA** (1029×804). Um template
   do tamanho da tela casa com escore alto em qualquer lugar e não localiza
   nada — `find_template` devolveria sempre o mesmo ponto. `test_o_template_e_um_RECORTE_e_nao_uma_tela`
   não sabe se um recorte está certo, mas sabe que uma tela está errada.
2. **O `link_west_suburb.png` veio com 5 linhas da linha DE CIMA.** O que está
   acima do link na lista do Fay MUDA conforme a rolagem, e conteúdo variável
   dentro do template baixa o escore justamente na hora de casar. Cortadas.

E os três ficam em **`data/templates/`**, não em `entrada/` — o `TemplateLibrary`
aponta para a raiz, e `entrada/` é a pasta de evidência. Template deixado só lá é
template que o bot não encontra, e a falha aparece como "a HH não entra".

### A CÂMERA vai para a pose padrão antes de todo clique posicional

Mesma exigência da BC, e o bot em Lua também sabia: ele chamava
`setCamera(380, 0, 40)` no começo de cada run. Todo clique de NPC e de minimapa
deste ecossistema é posicional na cena 3D — com a câmera fora do padrão, a
coordenada certa aponta para o lugar errado.

**A diferença contra o Lua é COMO.** Aqui a pose é lida da memória e conferida
(`Memory.camera_na_pose_certa`), em vez de escrita às cegas sobre um ponteiro
resolvido no início do script — que é o vício condenado no item N da seção 6.

Quatro lugares, travados por teste: o preparo da run, **cada trecho de
waypoints** (o `via` calibrado de cada waypoint foi medido nessa pose, e é
justamente nas curvas onde o cálculo falha que ele entra), a ida da Fada até a
porta, e a ida ao vendedor.

### A VENDA: o clique da BC não transfere, e isso foi medido

    primeiro link do diálogo, no NPC da HH ....... cliente (302, 361)
    `vendor_purchase_tab` da BC .................. cliente (282, 395)
    `vendor_sell_tab` da BC ..................... cliente (266, 430)

Os links do diálogo ficam a ~34 px um do outro, e a posição do **primeiro**
depende de quantas linhas de texto o NPC escreve antes deles. O
`Roaming Apothecary` escreve duas linhas e tem dois links, então o "Sell Item"
dele cai por volta de (302, 395) — 35 px acima e 36 px à esquerda de onde a BC
clica.

É exatamente o que `clicar_link` já documentava: *"os links do diálogo mudam de
posição conforme o texto do NPC, por isso são localizados por imagem e não por
deslocamento fixo"*. **Este caso é a prova.**

Então `_onde_clicar_no_link_de_vender` virou GANCHO: a BC devolve a coordenada
dela (comportamento intacto), a HH acha o link por imagem. Falta recortar
`link_sell_item.png`; sem ele a venda RECUSA e diz no log o que fazer. Um erro
aqui não faz o personagem andar — o ponto errado cai dentro da janela do
diálogo, não na cena —, mas a venda não abre e a bolsa continua cheia.

E a venda da HH **não gasta item de retorno e não abre o painel de arredores**:
o vendedor está no waypoint da porta. Os dois estão travados por teste.

---

## 9. O QUE AINDA NÃO ESTÁ MEDIDO

Registrado aqui para não virar palpite depois:

1. **Nomes de área DENTRO da cave — 2 de 66 medidos.** Os prints de 03/09/2026
   deram `Happiness Hall Dungeon` em (55,33) e `Happiness Hall Main Hall` em
   (529,118). Os outros 64 waypoints continuam com `AREA_INTERNA_NAO_MEDIDA`, e
   `mapa_hh.area_medida()` continua `False` — ela responde pelo CONJUNTO,
   porque o recuo "volte ao começo da área" só serve quando se sabe onde cada
   área começa. O inventário do que já se sabe é `mapa_hh.areas_medidas()`, e o
   teste trava esse dicionário: nome novo só entra com a linha que diz de que
   print ele saiu.
2. **Os nomes exatos dos 4 bosses**, para a trava por identidade. Continuam sem
   medição — e é por isso que `lutar_contra_um_boss` **não tem** portão de
   nome (ver seção 11).
3. ~~A coordenada do `Roaming Apothecary`~~ **FEITO** — (475,450), seção 8.1.
4. ~~O template do link `West Suburb of Stone City` e a seta de rolagem.~~
   **FEITO** em 03/09/2026 — ver seção 8.1. Falta só `link_sell_item.png`.
5. ~~O ponto de spawn interno.~~ **CONFIRMADO NA TELA** em 03/09/2026: o print
   mostra `Happiness Hall Dungeon [55, 33]`, exatamente o `insidexY` do Lua. E
   o usuário confirmou que é sempre esse par — *"o X e Y é igual e sempre vai
   entrar nesse X e Y pois é o padrão do jogo"*.

---

## 10. O QUE FOI CONSTRUÍDO (01–02/09/2026)

### 10.1 As cinco promoções, e o que cada uma custou

A HH não escreveu uma linha de motor. O que ela fez foi FORÇAR a separação
entre "o que é do jogo" e "o que é da Bewitcher Cave" — separação que sempre
devia existir e que só ficou visível quando apareceu um segundo leitor.

| # | promoção | linhas movidas | atrito real |
|---|---|---|---|
| 1 | `core/rota.py` | ~250 | nenhum: função pura sobre coordenadas |
| 2 | `bot/navegacao.py` | 1964 | UM ponto — `tolerancia_do_waypoint`, que virou `Navigator(ctx, mapa)` |
| 3 | `bot/ui_do_jogo.py` | 2103 | nenhum: 29 métodos genéricos contra 13 da BC |
| 4 | `bot/combate.py` | 3970 | CINCO métodos tocavam a cave, quatro deles só em constantes |
| 5 | `bot/vendedor.py` | ~1200 | três ganchos: quem é o vendedor, de onde se clica, qual UI |

**O acoplamento era muito menor do que parecia.** A estimativa inicial falava de
"rachar dois arquivos de 4000 e 2000 linhas"; na prática, dos 50 métodos
genéricos do combate, só um precisou de trabalho de verdade.

### 10.2 Os defeitos que a promoção revelou — e um que ela criou

Estes não são incidentes do processo: são o preço de mexer em código que roda
por horas, e cada um deles ficou travado por teste.

1. **`_ultimo_alvo_morto_id` desapareceu.** O primeiro fatiamento do combate
   indexou os métodos por NOME num dicionário — e aquele nome existe duas vezes
   (property e setter). O getter foi sobrescrito pelo setter, em silêncio.
   *Trava:* um teste compara o conjunto de métodos antes e depois do split.

2. **A BC importou os interruptores POR VALOR.** Ver a seção da armadilha da
   reexportação em `docs/INVARIANTES.md`.

3. **`_open_npc` ficou no motor chamando métodos que foram para a BC.**
   `test_sem_chamada_orfa` pegou — ele varre `self.<nome>` sem `<nome>` na
   classe, e existe exatamente para o defeito que só aparece com o jogo aberto.

4. **`account_dialog.py` importava uma constante que mudou de módulo, e a suíte
   inteira passou.** 1598 testes verdes, e a janela de editar conta não abriria.
   Nenhum teste importava a GUI nem a ponte web. *Trava:*
   `tests/test_as_interfaces_importam.py`, que também confere a PARIDADE entre
   as duas interfaces — "fiz só num lado" agora reprova.

### 10.3 O que a HH faz de diferente da BC, por desenho

| | Bewitcher Cave | HH |
|---|---|---|
| bosses | 1, com duas fases | 4, em sequência |
| forma na rotina | par de estados por fase | **LAÇO** sobre `TRECHOS_DOS_BOSSES` |
| chegada | Fay → Ghost Din Woods → Skull Herald | Fay → **West Suburb** (rolando a lista) → Mutual Quest Woman → Elite Axe Monk Soldier |
| vendedor | Rich Man, em Stone City (gasta pedra/token) | Roaming Apothecary, ao lado da porta |
| ciclo de time | reset entra e sai antes da cave | **solo:** igual à BC · **fada:** as duas entram, o ciclo fecha ao sair |
| alvo proibido | Cemetery Guard | nenhum conhecido |

Os quatro bosses como LAÇO é a decisão de forma mais importante: acrescentar um
quinto é **uma linha em `mapa_hh`**, e não dois estados novos mais um `if`.
Travado por teste — nenhum nome de estado termina em dígito.

### 10.4 O que AINDA FALTA para a HH rodar de ponta a ponta

Em ordem de bloqueio:

1. ~~Os três templates da entrada.~~ **FEITO** em 03/09/2026 (seção 8.1).
   Falta **um**: `link_sell_item.png`, o texto "Sell Item" do diálogo do
   `Roaming Apothecary`. Sem ele a entrada e o farm funcionam; só a venda
   recusa, e o log diz o que falta.
2. **A TECLA DE SEGUIR**, para o modo HH+Fada. `KeyBinds.follow` nasce VAZIA
   porque o cliente não tem atalho padrão para o follow: configure no jogo e
   repita em *Editar conta > Teclas > Seguir*. Sem ela a Fada avisa uma vez e
   acompanha sem seguir — ela continua curando de onde estiver.
3. **A área interna** (seção 9, item 1) e **os nomes dos quatro bosses**
   (item 2). Nenhum dos dois bloqueia; os dois melhoram o log e a retomada.

### 10.5 O modo HH+Fada, e a lacuna que ele quase teve

**Está completo.** A Fada viaja pela MESMA rota do líder, espera o aviso dele no
mural, entra atrás, e acompanha pela tecla de seguir do jogo — que é o que o bot
em Lua faz, e é a parte dele que estava certa.

A sexta promoção saiu daqui: `app/fada.py` → **`bot/fada.py`**. Foi a mais
barata das seis, porque a `FadaDoTime` **já era completamente injetada** — não
recebe `BotContext`, não abre memória, não conhece supervisor. Mover foi trocar
`...core` por `..core`.

**A LACUNA, e ela é instrutiva.** A primeira versão do portão chamava só o
acompanhamento e dava `continue`. A Fada seguiria o líder pela cave inteira e
**nunca curaria** — e a docstring dizia que compunha com a `FadaDoTime`, o que
tornava a leitura do código *mais* enganosa, não menos.

Nenhum teste de comportamento pegaria isso: não havia comportamento errado,
havia uma peça que simplesmente não era chamada. O que fechou foi
`FadaDoTime._uma_volta` — um giro do laço de cura, chamado de dentro do laço de
seguir. **As duas na mesma volta**, porque dois laços concorrentes na mesma conta
seriam duas mãos no mesmo teclado. E a cura vem ANTES do follow na volta: quem
espera cura está tomando dano agora.

O ciclo de time continua sendo do LÍDER, e não dela. Duas contas decidindo
desfazer o mesmo time é uma corrida cujo resultado é um time desfeito no meio da
cave — testes proíbem a Fada de chamar `sair_do_time`, de percorrer waypoints e
de lutar.

---

## 11. A REVISÃO DE 03/09/2026 — três defeitos de transição

Auditoria pedida pelo usuário depois de rodar a HH. Os três sintomas tinham
causas independentes, e cada um virou trava.

### 11.1 Vazamento de estado: ligar a HH marcava a caixa do BC

`Account.farms` significava "o BC está ligado" quando existia uma cave só; virou
`bc_farm or hh_farm` **sem revisar quem lê**. Quatro leitores ficaram com o
significado antigo:

| leitor | efeito |
|---|---|
| `supervisor` (resumo) | publicava `farms` no campo `farm` → o espelho ao vivo **marcava a caixa do BC** |
| `context.raise_if_stopped` | desmarcar o BC com a HH ligada **não cortava a fase no meio** |
| dois status + o rótulo do editor | diziam "BC farm" para conta só de HH |

O primeiro é o sintoma visível; **o segundo é o que ninguém teria visto.**

`farms` fica com o significado honesto — ELEGIBILIDADE, "esta conta está ocupada
farmando?" — e `Account.cave_ligada` responde QUAL, na ordem do despacho.
`ctx.cave_em_farm` diz quem está no ar, e a parada confere o interruptor dela.

### 11.2 Configuração gravada e ignorada

As duas interfaces gravavam `settings.hh.*`; o bot lia `settings.bc.*`. O usuário
pôs `attack_delay = 0,1 s` na HH e o bot atacava com os 0,5 s do BC.

E o pior não era número: **`TeamService` lia `settings.bc.reset_nick`**. Com o
`bc.reset_nick` vazio, `montar_time()` devolvia `False` na primeira linha → a
rotina caía em RECUPERAR → laço, para sempre. **A HH nunca montava time, e sem
time os bosses não renascem.**

`AccountSettings.cave(nome)` + `ctx.cave` resolvem pela cave em execução. Os dois
`Config` têm os MESMOS nomes para os quatro campos do motor, travado por teste —
nome diferente obrigaria um `if` por cave dentro do motor.

### 11.3 Combate empobrecido, e uma luta que se zerava

A HH passava `alvo_esperado` com os rótulos de **comentário** do bot em Lua. O
portão de nome devolve `acabaram` para nome diferente do esperado — certo numa
fase multi-mob, errado num boss único. **A luta terminava na primeira leitura de
nome, sem um golpe, reportando vitória.**

O ritual do BC subiu para `CombatEngine.lutar_contra_um_boss` e serve as duas.
`curar_antes_do_boss` também — e ela **não existia** no `self.combat` da HH:
`AttributeError` no primeiro boss, com a suíte inteira verde.

### 11.4 O padrão que apareceu quatro vezes

`Api.alternar_hh` inexistente · a Fada montada e não ligada · `_open_npc`
chamando método que ficou na BC · `curar_antes_do_boss` fora do motor.

**Suíte verde não prova que as peças estão LIGADAS.** As quatro travas são
estruturais, porque não há comportamento errado para observar — há uma ligação
que não existe:

| trava | o que cruza |
|---|---|
| `test_a_ponte_web_expoe_tudo.py` | todo `chamar("x")` do JS × os métodos da `Api` |
| `test_as_interfaces_importam.py` | os módulos de interface importam, e há paridade entre as duas |
| `test_config_da_cave_e_lida.py` | todo campo do `HHConfig` × um leitor no bot |
| `test_hh_combate_nivelado.py` | todo `self.<colaborador>.<nome>` × a classe real |
| `test_hh_nao_vaza_para_o_bc.py` | todo uso de `.farms`, pelo AST, com o motivo declarado |
| `test_ecossistema_isolado.py` | estragar uma cave não muda a outra (runtime) |

### 11.5 E uma lição sobre os próprios testes

Comparar posição de TEXTO para verificar ordem de execução falhou **sete vezes**
nesta revisão: a docstring do método cita os nomes justamente para explicar a
ordem, e `str.index` encontra a explicação antes do código. Toda verificação de
ordem passou a ser por AST (`_em_ordem`), e `ast.walk` **não** preserva ordem de
código — precisa de `lineno`.

---

## 12. A SESSÃO DE 03/09/2026 — DOIS LOOPS INFINITOS, UM CRASH, E O DESENHO
##     DA PREPARAÇÃO

Esta seção é o resultado de uma sessão de `/grilling` com o usuário (cinco
rodadas) mais a leitura do log de produção de 03/09. Tudo aqui foi **medido** —
no log, no print do jogo, ou no código do bot em Lua.

### 12.1 O crash que reiniciava o bot na porta a cada 5 s

`hh/routine._garantir_o_time` fazia `self.team.in_team()`. **`in_team` é
`@property`**, e com o jogo aberto isso é
`TypeError: 'bool' object is not callable`. A exceção subia até o supervisor,
que soltava o controle e recomeçava a sessão.

O log de 19:02 mostra o ciclo inteiro seis vezes em 21 segundos: *"Logado
como..."* → *"Iniciando HH"* → `situar` → `preparar` → *"já estou na porta"* →
`entrar` → crash → *"Soltando o controle"*.

**A suíte inteira passava.** O teste irmão
(`test_toda_chamada_em_colaborador_da_HH_existe`) só conferia se o NOME existe
na classe — e existe. O que não existe é o direito de chamá-lo. O teste novo
(`test_a_HH_nao_CHAMA_propriedade_de_colaborador`) lê o AST, junta só os
`self.<colaborador>.<nome>(...)` **com parênteses**, e reprova os que são
`@property` na classe real.

Passou a usar `estado_do_time`, que devolve `None` quando a leitura falha em vez
de achatar "não estou" e "não consegui ler" no mesmo `False` — o próprio
`bot/team.py` documenta que esse achatamento já custou caro uma vez.

### 12.2 Os dois loops infinitos — o mesmo defeito, duas geometrias

O usuário relatou o bot "indo e voltando várias vezes" em (227,186) e depois em
(507,107). São o **mesmo defeito**: `core/rota.houve_rollback` perguntava *"qual
waypoint está mais perto do personagem"* quando a pergunta é *"ele foi jogado
para trás"*. Numa rota que só avança as duas coisas coincidem; numa rota que
volta pelo mesmo corredor, não.

| trecho | geometria | por que o mais próximo mentia |
|---|---|---|
| 1 | wp10 (209,182) e wp11 (207,186) a **4,5** unidades — menos que a tolerância de chegada (7) | o bot cruza os dois de uma vez, o índice vai para 12, e o mais próximo continua sendo o 10 |
| 4 | wp13 (510,126) é uma **espora**: desce 19 para depois subir 33 até o wp14 (509,93) | andando de 13 para 14 o personagem passa de novo pela altura do wp12 (507,107) |

Em ambos: "voltei" → relança a navegação → o destravamento escolhe o vizinho de
trás → recruza → "voltei". Para sempre. O log de 19:39 tem 40 voltas em 15 s.

**Os dois pontos são legítimos** — o bot em Lua usa os mesmos, e o `via` de cada
um é diferente (o ponto existe para virar a direção do clique no minimapa, não
para andar 4 unidades). O errado era a régua.

**A correção:** quem decide é o **trecho atual**. Estar em cima da reta que liga
o waypoint anterior ao alvo é a definição de "estou indo para onde mandaram".
Distância ao trecho nos dois casos medidos: **2,3** e **0,7** unidades, contra
as 12 de `NA_ROTA` — a mesma régua que o resto do módulo já usa. Número novo,
nenhum.

O rollback de verdade continua sendo pego: teleporte para trás fica **longe do
trecho atual E perto de um índice bem anterior**. Precisa das duas coisas.

**Uma recomendação minha foi reprovada no caminho.** Na rodada 3 eu propus
"olhar o waypoint mais avançado dentro da tolerância". Ela conserta o trecho 1 e
**não conserta o trecho 4**: em (509,115) nenhum waypoint está dentro da
tolerância 7 (wp12 a 8,2; wp13 a 11,0; wp14 a 22). Só o segundo log mostrou
isso.

### 12.3 A preparação sai de fora e vai para dentro

Regra do usuário: *"o uso de SS, o uso de buff, o uso de poção de cura,
qualquer coisa que precisar é só depois que entrar na cave e não fora, como é
feito no bot BC"*. É a **mesma regra** que a Bewitcher Cave segue desde
25/08/2026, e os dois motivos valem igual:

- **tudo isso exige estar a pé**, e montado o jogo IGNORA a tecla sem devolver
  erro — o bot "aperta e nada acontece";
- **entrar é disputado** e pode levar uma hora; nesse intervalo o personagem
  regenera de graça, então curar antes é gastar poção que a espera ia devolver.

| onde | o que acontece |
|---|---|
| `PREPARAR` (fora) | câmera, decisão de venda, montaria para viajar |
| fim de `ATE_A_PORTA` | **o PET** — a única verificação de fora, e só ao CHEGAR |
| `PREPARAR_DENTRO` | curar → buffs → pet → comida → montar (a ordem do BC) |

O pet é conferido **nos dois lugares de propósito**: a tela de carregamento da
instância fica entre eles, e é justamente onde ele some. E a checagem da porta
fica **fora** do laço de tentativas — a rajada pode durar uma hora com uma
tentativa a cada 25 ms.

A contagem da run passa a começar no preparo de dentro: a disputa da porta pode
ter levado uma hora, e contar dali torna o tempo por run comparável.

### 12.4 A rajada de entrada é a do BC

Regra do usuário: *"tem que ficar fazendo as tentativas para entrar, como é
feito em BC, pois são várias e várias tentativas até conseguir entrar, pois pode
estar cheio a cave"*. Quatro coisas vieram de lá:

| antes (HH) | agora (= BC) | o que resolve |
|---|---|---|
| teto de 5 min | **1 hora** | desistir devolve o personagem ao começo do ciclo sem ter feito nada |
| confirmação de 2,0 s | **0,25 s**, passo 0,04 s | enquanto o bot esperava, ninguém estava tentando |
| — | **voltar à coordenada** ao derivar | fora do ponto todo clique erra o NPC, e cada erro empurra mais |
| redescobria sempre | **só na falha mecânica** | instância cheia é a razão NORMAL de não entrar |

Mais duas: percebe que já entrou numa tentativa anterior (o servidor pode
demorar mais que a janela), e escreve uma linha de log a cada 15 tentativas em
vez de uma por tentativa — são milhares por hora.

Estourar o teto volta para `ATE_A_PORTA`, e não para `RECUPERAR`: uma hora sem
entrar não é queda nem morte.

### 12.5 Cada ponto luta do jeito que a natureza dele pede

Medido pelo usuário no jogo: *"no primeiro boss e no 3 (Green Robmaster) tem
mobs ranged, então o AOE não irá funcionar, de resto pode usar o AOE sem
problemas"*.

| ponto | natureza | ritual | AoE | TAB |
|---|---|---|---|---|
| 1 Fa-Yuan | pacote ranged | `limpar_o_combate` | não | do próprio ritual |
| 2 Dupla | dois bosses | `lutar_contra_um_boss` | sim | 2 por morte |
| 3 Green Robmaster | pacote ranged | `limpar_o_combate` | não | do próprio ritual |
| 4 Purple | boss único | `lutar_contra_um_boss` | sim | 0 |

**Por que a AoE não serve:** a skill de área é de curta distância; o mob ranged
fica parado longe atirando e a área passa embaixo dele. Girar AoE ali é gastar o
tempo da rotação sem dano, e a luta se arrasta até o teto.

**Por que o pacote usa outro ritual:** o que encerra a luta é a lista acabar, e
cada morte pode ou não ser a última. `limpar_o_combate` mata UM, **para e olha a
flag por três segundos**, e só então TAB para o próximo — que é exatamente a
coreografia do `hh.killAtPosition` do Lua, com as três skills normais
(probe/burning/bash) e nenhuma de área. A pausa é como se descobre o fim sem
puxar mob novo.

O TAB do mapa é **0** nos pacotes por motivo OPOSTO ao do boss único: lá quem dá
o TAB é o próprio `limpar_o_combate`. Dois donos do mesmo TAB gastariam dois por
morte, e o segundo miraria quem está FORA do combate.

### 12.6 Cinco segundos para engajar — e o que isso custa

Regra do usuário: *"sempre que tiver em um waypoint de ataque deve esperar no
máximo 5 segundos para entrar em batalha, caso não entre em batalha pode
continuar para os próximos waypoints"*, e ele confirmou que **vale no ponto do
boss também**.

É o que torna barato refazer um trecho depois de uma morte: ponto vazio não
engaja, e o bot passa reto em 5 s.

**O custo está registrado porque eu levantei e o usuário reafirmou:** um boss
VIVO que demore mais de 5 s para agredir é pulado, e a run perde esse boss. Eu
tinha recomendado apertar TAB depois dos 5 s (o que o BC faz) para distinguir
"ponto limpo" de "boss lento"; o usuário escolheu seguir direto. O log diz em
voz alta quando acontece, para dar para conferir no jogo se acontece de verdade.

### 12.7 Voltar ao ponto, e o que já foi feito

**Voltar ao ponto depois de matar** (o Lua faz o mesmo em `hh.killAtPosition`):
mob ranged não vem até o personagem — é o personagem que anda até ele. Sair do
ponto desalinha o trecho seguinte, e foi assim que o rollback falso apareceu no
trecho 1.

**O progresso dos bosses** é lembrado em memória, volátil (regra do usuário:
*"não precisa ser persistente, só verificar enquanto está com o bot aberto"*), e
**zerado ao sair da cave** — o desfaz-refaz do time ressuscita os quatro.

E a retomada respeita o **trecho em andamento** em vez de escolher pelo waypoint
mais próximo: os quatro trechos se cruzam no mapa, e quem morre no trecho 3
revive perto do trecho 1. Escolher pela distância refaria bosses já mortos e
encontraria as salas vazias.

Junto veio o conserto de `RECUPERAR`, que fazia `self._trecho = 0` — jogando
fora o progresso da run em toda queda.

### 12.8 Curar exige estar fora de batalha, e a saída é matando

Regra do usuário: *"para se curar tem que estar fora de batalha"*. Perguntado o
que fazer estando em batalha com a vida baixa, ele escolheu **matar**: *"você
deve matar os mobs até sair de batalha"*.

O trajeto já abortava sozinho abaixo de `emergency_pct` — é
`Navigator._manutencao_em_movimento`, código compartilhado que a HH já herdava.
O que faltava era o **depois**: `RECUPERAR` agora mata até sair de combate e só
então bebe. Não saiu no teto? A cura fica para a volta seguinte — "não consegui"
devolve o controle em vez de travar a conta.

**Usa o limiar de EMERGÊNCIA, não o normal.** Os mobs da HH são fracos (é a
razão que o usuário deu para curar menos) e com o limiar normal a run passaria o
tempo bebendo.

**A cura entre os bosses saiu.** Era o terceiro momento de cura no mesmo ponto —
`curar_antes_do_boss` já faz o top-up no começo do trecho seguinte, e entre os
dois só há o tempo de andar — e sentar já tinha sido medido e reprovado na BC.
Sobraram três momentos: a entrada, o top-up antes de cada boss, e a emergência.

### 12.9 A saída — o estado que não saía

`_do_sair` andava até (529,119) e declarava a run concluída, **sem falar com NPC
nenhum**. O personagem ficava dentro, e a "run seguinte" começava a tentar
entrar numa cave em que já estava.

Medido no print: o diálogo se chama **`Servant Child`**, o texto é *"Don't beat
me. I'm just a servant of here, if you want to leave here, I can help you..."* e
o link verde é **"Leave Happiness Hall"** (`link_leave_hh.png`). O clique
direito é (708,300) na base 1024×768.

**O padrão é o da entrada, e não o do Lua.** Ele dá TRÊS cliques direitos às
cegas em alturas diferentes (526,298 / 524,325 / 529,361) e depois clica num
ponto fixo do diálogo, porque não sabe ler a tela. Um clique que erra o NPC cai
no chão — e clique no chão faz o personagem ANDAR, saindo do ponto de onde o NPC
é alcançável.

Insiste até a POSIÇÃO confirmar (-342,-288), como o Lua também faz. Teto de 5
minutos e não de uma hora: entrar disputa vaga com outros jogadores e depende de
eles saírem; sair não depende de ninguém.

A confirmação da saída espera **3 s**, contra 0,25 s da entrada, e a diferença é
de propósito: a entrada é disputada e esperar ali é tempo em que ninguém está
tentando; a saída paga a troca de mapa inteira uma vez por run.

### 12.10 O ponto onde os mobs bloqueiam

O (232,188) aparece em dois arquivos do Lua com a mesma instrução —
`travel.lua` (*"em 232,188 matando os mobs que bloqueiam"*) e `hh.lua` (*"ataca
mobs em 232,188 até não ter alvo"*). É uma passagem estreita, e um mob parado
nela faz a navegação bater na geometria.

**A diferença contra o Lua é medida:** ele mata ali sempre que está a pé, porque
não lê a flag de combate. Nós lemos — então só paramos se o combate JÁ começou.
Numa volta em que o ponto está limpo isso não custa clique nem captura de tela.

Para isso o navegador ganhou um gancho opcional `ao_chegar`. **Sem gancho o
comportamento é exatamente o de antes**, e é assim que o BC não muda. O gancho
vale para os waypoints ATRAVESSADOS também: a montaria cruza dois ou três numa
leitura só.

`WAYPOINTS_QUE_BLOQUEIAM` é um conceito **diferente** de
`WAYPOINTS_PROBLEMATICOS`: aquele alarga a tolerância de chegada onde a
geometria não deixa encostar, este é sobre MOBS. Os dois calham de valer para o
mesmo ponto hoje, e é por isso que misturá-los seria fácil e errado.

---

## 13. A SESSÃO DE 04/09/2026 — QUATRO DEFEITOS NO LOG, E A VERIFICAÇÃO DUPLA

Tudo aqui saiu do log de produção de 03/09 (23:22 → 00:06) ou de medição do
usuário no jogo.

### 13.1 A correção que abre a seção: o nome do lugar é o mesmo dentro e fora

**`Memory.location()` devolve `Black Wind Camp Dungeon` DENTRO e FORA da cave.**
A linha que confirma a entrada diz, literalmente:

    Entrada na HH confirmado em 0 ms: (55, 33) | local Black Wind Camp Dungeon

Em 673 menções do log é a **única** string de lugar. Os nomes
`Happiness Hall Dungeon` e `Happiness Hall Main Hall` da seção 12 são o rótulo
do canto da **TELA**, e foram registrados ali como se fossem leitura de
ponteiro. Não são.

A consequência é a regra: **quem responde "dentro ou fora" é a COORDENADA**, e o
símbolo passou a se chamar `ROTULO_DE_TELA_DA_CHEGADA` para não sugerir o
contrário.

### 13.2 Os quatro defeitos

| # | o que era | evidência |
|---|---|---|
| 1 | **`FarmDesligado` escapava.** A HH não capturava em lugar nenhum; a exceção subia ao supervisor como "Erro inesperado na sessão" e derrubava tudo | **15 vezes em 33 min**, cada uma refazendo login, janela e contexto |
| 2 | **`NOME_DO_ALVO_PROIBIDO` é `None` no motor** e três pontos chamavam `.lower()` nele | 3 sessões derrubadas, todas em `limpar_o_combate` — **regressão da véspera**, quando a HH passou a usá-lo |
| 3 | **`nav.destravar_o_combate` nunca foi ligado na HH** (só `bc/routine.py:424` liga) | 23:44: *"estou EM BATALHA… não tenho destravamento ligado; sigo insistindo"* — **41 s** parado |
| 4 | **O reinício perdia o trecho em andamento** | 23:40:14 pulou do Fa-Yuan direto para o Dupla |

O #4 é consequência dos #1 e #2: sem os crashes, a sessão não se reconstrói. O
usuário já tinha decidido (03/09) que o progresso **não** é persistente, e os
5 s de espera em cada ponto de batalha cobrem o resto.

O #3 é o **quarto** caso desta integração de peça construída e nunca ligada. Os
outros três: a Fada que não curava, o `Api.alternar_hh` ausente, e o
`curar_antes_do_boss` que não existia no motor.

**O teste que guardava o #1 pedia a coisa errada.** Ele exigia que
`Disconnected` **não aparecesse** em nenhum `except` da HH. Quando o laço ganhou
um `except Exception` (para não morrer por defeito de um estado), esse
`except Exception` passou a engolir `Disconnected` — e a forma de impedir isso é
justamente capturá-lo antes e relançar, que era o que o teste proibia. Agora ele
trava o comportamento (**capturar pode; engolir, não**) e tem um irmão que
confere a ORDEM dos handlers.

### 13.3 O bot entrava na cave e saía na mesma volta

Regra do usuário: *"se for Black Wind Camp Dungeon e X acima de 0 entrou na cave
e precisa parar as tentativas na hora, pois no mesmo ângulo que entra, ele sai"*.

**Não era lentidão de detecção** — o log mostra a entrada aparecendo na memória
em **0 ms**, com as duas tentativas anteriores dizendo "ainda em (-343,-288)".

Era o **par de cliques não ser atômico**: entre o clique direito e o clique no
link há a espera do diálogo, que o log mede em 180–420 ms. Quando uma tentativa
acertava, o personagem entrava — e a tentativa seguinte clicava com direito no
mesmo ângulo, que **dentro** da cave é o NPC de saída. O diálogo abria (então a
conferência dizia "pode clicar") e o clique caía em "Leave Happiness Hall".

`_abrir_dialogo_e_clicar` ganhou `ainda_vale`, chamado depois de o diálogo abrir
e antes do clique no link. A HH passa `_ainda_estou_fora`, que lê a POSIÇÃO —
microssegundos, que é o que torna barato perguntar entre dois cliques. Sem
leitura, **segue**: bot mudo na porta é pior que o defeito.

### 13.4 A verificação dupla — nome E coordenada

Regra do usuário: *"é importante verificar a localização por ponteiro e a
coordenada por ponteiro, fazer a verificação dupla"*. Nenhum dos dois basta:

- **o nome não separa dentro de fora** (§13.1);
- **a coordenada não separa as etapas de fora**, porque o teleporte da Fay
  espalha o ponto de chegada — e o usuário foi explícito: estando em
  `West Suburb of Stone City` deve-se seguir dali *"mesmo que o X e Y não esteja
  certo"*.

A divisão de trabalho em `mapa_hh.etapa_pelo_lugar`: a **coordenada** responde
"dentro ou fora" (é a leitura que nunca falhou em nenhum log, inclusive nos
episódios de nome preso); o **nome** responde "quão longe da cave estou, do lado
de fora".

| etapa | como se chega nela |
|---|---|
| `ETAPA_DENTRO` | posição na caixa `((55,17),(585,246))` |
| `ETAPA_NA_PORTA` | a até 30 unidades de (-342,-288) |
| `ETAPA_NA_VIZINHANCA` | nome em `West Suburb of Stone City` ou `Outside Black Wind Camp` |
| `ETAPA_LONGE` | o padrão — qualquer outra coisa |

O ganho: estando depois do teleporte, o bot **pula a Fay** e vai direto pelos
arredores. Não é só economia de dois painéis — refazer o teleporte estando do
outro lado dele levaria o personagem de volta para Stone City, **andando para
longe da cave**.

`ETAPA_LONGE` como padrão é o desfecho seguro: nome desconhecido (`Wei's
Village`, `Bothy`, um mapa novo) manda fazer a viagem inteira, que funciona de
qualquer lugar. **"Não sei" custa uma viagem, nunca um clique no lugar errado.**

### 13.5 O beco sem saída do ponto do boss

Medido pelo usuário: chegou no X/Y do boss, o bot desmontou para lutar, o
servidor lagou e devolveu o personagem para outro X/Y. A rotina concluía "não
estou no ponto" e voltava para `ATE_O_BOSS` — que começa exigindo montaria. E
**em batalha o jogo recusa montar**. O bot apertava a tecla contra uma recusa,
sem saída.

Resposta do usuário: *"é importante identificar se está em batalha e sair
matando os mobs até sair de batalha, então vai matando 1 por 1, até a flag de
batalha ficar false"*. É `limpar_o_combate`.

E **não muda de estado**: a volta seguinte relê a posição e decide de novo —
matar pode ter bastado sozinho, porque o personagem persegue o mob e às vezes
volta para dentro da tolerância.

### 13.6 No meio da cave não se verifica nada

Regra do usuário: *"as verificações são somente na entrada da cave… só naquele
waypoint inicial você faz as verificações e usa os buffs"*.

É o mesmo motivo que tirou o preparo de FORA da cave, um degrau adiante: tudo
isso exige estar **a pé**, e a pé no meio da cave é o trem de mobs encostando.
Quem chega ao preparo sem ser pela porta morreu e reviveu dentro, ou abriu o bot
com a run em andamento — e nos dois casos o que urge é voltar a andar.

**A montaria não é "verificação"** e continua nos dois ramos: é a condição para
andar, e a pé o personagem não chega no boss.

O portão é `acabei_de_entrar`, e a régua não é número novo: a entrada sempre
deposita em (55,33), o log leu (55,34) um segundo depois, e o primeiro waypoint
fica a 26 unidades. `rota.NA_ROTA` (12) é a régua que o core já usa para a mesma
pergunta.

### 13.7 A saída remedida

    ponto  (529, 119) -> (527, 124)
    clique (708, 300) -> (626, 526)

Do ângulo antigo a **montaria** do personagem ficava na frente do NPC e comia o
clique. Os dois números andam juntos porque o clique é posicional na cena 3D.

E veio a regra que faltava: a navegação declarava o trecho concluído dentro da
tolerância de **rota** (7 unidades), e o bot clicava dali. Sete unidades bastam
para o clique pegar **outro NPC** que fica por perto — e aí o personagem caminha
até ele, saindo do único ponto de onde o `Servant Child` é alcançável.

Agora vale a mesma régua da porta da cave: chega no ponto primeiro, e
`tentar_sair_da_hh` recusa clicar de fora dele.


## 14. A MIRA DA HH — F1 + TAB (08/09/2026)

### O sintoma, relatado pelo usuário

> *"dentro de HH tem vezes que o personagem acaba se auto selecionando ou
> seleciona o pet e quando isso acontece, ele nao seleciona automaticamente
> outro mob automaticamente, entao e importante identificar isso e dar um TAB
> nesses casos, ou faz o seguinte, pressionar F1 que é a tecla de auto seleçao
> e depois dar TAB, assim garante que vai selecionar o mob mais perto"*

E o bot ficava batendo em nada: a rotação girava, a flag de combate continuava
alta porque os mobs seguiam atacando, e o alvo na mira não perdia HP nunca. A
luta só terminava pelo teto.

### Por que DOIS toques, e não só o TAB

O TAB é **cíclico**: ele avança a partir de onde a mira está. Presa no próprio
personagem ou no pet, um TAB sozinho avança para "o seguinte naquele ciclo",
que pode ser o pet de novo.

`keys.self_target` (F1) mira o PRÓPRIO personagem — um estado conhecido e
sempre o mesmo. O TAB dali avança de um ponto fixo, e é isso que torna a
aquisição repetível em vez de depender de onde a mira estava.

**Sem a tecla, só o TAB.** Conta sem `self_target` configurada continua
funcionando — pior, mas funcionando.

### Duas perguntas diferentes, duas respostas

| momento | quem resolve | por quê |
|---|---|---|
| **abertura** de toda luta | `HHRoutine._mirar_o_primeiro_mob` — F1+TAB **sem condição** | o gesto custa duas teclas e acerta sempre; conferir cada caso possível custa leitura e acerta menos |
| **meio** da luta | a MORTE do alvo, e mais nada — TAB imediato e de volta a bater | *"as batalhas devem ser fluidas como exemplifiquei no Boss 2"* |

O usuário fechou a primeira linha no mesmo dia: *"sobre começar a atacar eu
realmente acho que apertar F1 e depois dar o primeiro TAB vai ser o mais
eficiente para atacar os mobs corretos"*.

### O detector de meio de luta foi construído e SAIU

Primeira versão tinha uma segunda régua: contar leituras com o HP do alvo
parado e reancorar depois de 20 delas (3 s). Ela nunca chegou a rodar em
produção porque o usuário cortou o desenho no mesmo dia:

> *"o F1 + TAB e apenas para evitar problemas no incio da batalha, mas as
> batalhas devem ser fluidas como exemplifiquei no Boss 2"*

E o argumento é o certo: a régua lia o HP a cada volta do laço para decidir se
trocava de alvo, e isso é **uma pergunta no meio do caminho** — exatamente o que
a regra global de combate da HH tirou de lá quando substituiu
`limpar_o_combate`. Um caso raro (pet de nível baixo na mira) não paga uma
condição dentro do laço mais quente do bot.

### A exceção à regra "F1 NUNCA SAI EM BATALHA"

`combate.py` tem essa regra no alto do arquivo, e o motivo é medido: **F1 larga
o alvo**, e quem larga o alvo no meio da luta bate no vazio. Foi por ela que a
cura por skill saiu de dentro da batalha.

A abertura da luta na HH **viola a regra de propósito** — ali largar o alvo é o
objetivo, e o TAB da linha seguinte é o que fecha o gesto. A diferença entre as
duas situações é uma linha de código: "F1 e pronto" (a bomba que a regra
desarmou) contra "F1 e TAB" (o que o usuário pediu).

Se o TAB falhar, o pior caso é a mira ficar no próprio personagem até a próxima
abertura de luta — e é por isso que a exceção vale só aqui, e só uma vez por
luta.

### O portão por NÍVEL foi construído e REPROVADO

Primeira tentativa: reconhecer o alvo errado pela faixa de nível. Está medido —
**391 leituras de alvo dentro da HH, todas entre nv26 e nv30**: `Elite Mace
Fatso` nv26, `Elite Play Boy` nv26, `Elite Blackshirt Bandit` nv27, `Elite
Lecher` nv27, `Fa-Yuan` nv27, `Callet Head Young` nv27, `Elite Callet` nv28,
`Elite Black Leopard` nv28, `Zaton` nv28, `Elite Fatal Centipede` nv29, `Green
Robe Master` nv29, `Elite Monk Ranger` nv29, `Elite Axe Monk Soldier` nv30.

**O que reprovou o portão foram duas coisas.** A primeira: o usuário informou
que *"o pet pode ser level 35 ou menos, vai depender do pet do usuario, mas
atualmente o level maximo de um pet é 35"* — a faixa do pet (≤35) **sobrepõe**
a dos mobs (26–30), então o portão pegaria o personagem (nv88, sempre) e só o
pet de nv31 a 35. A segunda, decisiva: com a abertura incondicional o portão
fica **sem pergunta para responder** — não há o que conferir antes de um gesto
que acontece sempre.

O dado dos nv26–30 fica registrado aqui porque é medição, e medição não se
joga fora; o código dele saiu por não ter chamador.

## 15. LUTAR MONTADO NOS PONTOS DE PACOTE (07/09/2026)

Texto movido do comentário de `HHRoutine._matar_ate_sair_de_batalha`, verbatim:

> DESMONTAR AQUI EXIGE `permitir_em_batalha` -- E ERA O DEFEITO
>
> `ensure_dismounted()` RECUSA descer enquanto a flag de combate estiver alta
> ("Em combate: ignorando o pedido para desmontar"), e a recusa é certa em
> quase todo lugar: desmontar sob ataque é ficar lento no meio do trem de
> mobs. A exceção são os PONTOS DE LUTA, onde descer é o objetivo -- montado o
> jogo IGNORA a tecla de skill e não devolve erro.
>
> Este laço chamava a versão sem exceção, e chegar no ponto já em combate é o
> NORMAL na HH (os mobs ranged atiram durante o trajeto). Resultado medido pelo
> usuário em 07/09/2026: nos pontos de pacote -- os bosses 1 e 3 -- o
> personagem lutava MONTADO, com dano zero. Os bosses 2 e 4 passavam porque
> `lutar_contra_um_boss` usa `_descer_para_lutar`, que já passa a exceção.
>
> A CORREÇÃO É USAR O MESMO GESTO, e não repetir a chamada com a flag:
> `_descer_para_lutar` também força a barra de atalhos na página 1, que num
> ponto de luta é a diferença entre bater e apertar tecla vazia. Duas cópias do
> gesto divergiriam, e a que ficasse para trás lutaria com a página errada.

## 16. O TRECHO RECOMEÇAVA PELO WAYPOINT 1 (08/09/2026)

### O log

08:13:57. A luta do Fa-Yuan terminou em **(325,152)**, longe do ponto do boss
(272,136). `PontoDoBoss` mandou a run de volta para `ATE_O_BOSS`, e a rotina
reentrou no trecho 1/4 clicando o waypoint **1/22 — (80,42), a 214 unidades**:

```
08:13:57.192 boss        HH: não estou no ponto do Fa-Yuan (estou em (325, 152), o ponto é (272, 136))
08:13:57.254 ate_o_boss  HH: indo para o Fa-Yuan (trecho 1/4, 22 waypoints)
08:14:45.776 ate_o_boss  sem progresso indo para (80, 42) (waypoint 1/22, distância 214) — relançando (1)
08:14:45.778 ate_o_boss  Navegação travada em (278, 124). Vizinhos: 22 em (272,136) a 13 -> 21 em (282,139) a 16
08:14:47.192 ate_o_boss  sem progresso indo para (272, 136) (waypoint 1/1, distância 13) — relançando (1)
```

### Por que a parede

O clique de minimapa vai em **linha reta** e alcança ~17,6 unidades por vez
(`zones.ALCANCE_DO_MINIMAPA`), então um destino a 214 unidades é percorrido por
uma sequência de pontos intermediários **sobre a reta**. A reta de (325,152) até
(80,42) atravessa a divisa das salas da mansão: o personagem andou até bater na
parede e parou em **(278,124)**, a 13 unidades do waypoint 22 e **sem caminho
até ele**. Daí em diante o jogo respondeu `Failed to auto-path` a cada
tentativa, até o destravamento recuar pelos vizinhos.

Relato do usuário: *"o personagem esta indo para uma direção errada... tem uma
parede que divide em salas diferentes... na verdade eu estou quase ao lado
dele, só tem essa parede dividindo"* e *"depois de um tempo ele ate percebe
isso e volta para a rota correta, porem nao deveria ir ali"*.

### A correção

`mapa_hh.onde_retomar` **já existia e nunca tinha sido ligada** — mais um caso
de "suíte verde não prova que a peça está LIGADA". `_do_ate_o_boss` passou a
calcular o waypoint de entrada e a passá-lo em `comecar_em`.

**`comecar_em`, e não fatia da rota.** A fatia leva embora o waypoint ANTERIOR,
que é candidato do destravamento — foi o que apagou o candidato a 10 unidades
no log de (205,31) no BC. Ver `Navigator.seguir_rota`.

**O trecho é refeito com frequência**, e quase nunca do começo: boss longe do
ponto, rollback, personagem arrastado na luta. Recomeçar pelo waypoint 1 era o
caso comum, não o excepcional.
