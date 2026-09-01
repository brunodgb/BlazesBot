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
                                └─ andar até (-343, -289)
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
`(-343, -289)`. **A distância entre as duas é o ponto todo:** o painel caminha
até PERTO (aceita folga por construção), e clicar de onde ele largar é o defeito
já medido na BC em 25/08/2026 — a 2 passos o clique caiu no White Eagle que
estava no caminho. Por isso `(-343, -289)` é encostado com o mesmo mecanismo do
`_encostar_na_fay` / `_no_ponto_do_vendedor`, e **não se clica de fora do ponto**.

### 2.3 A âncora do Lua confirma a coordenada

`hh.lua` usa `entrance = {-342, -286}` como o ponto de onde tenta entrar, e
`farmer.lua` usa `sellPos = {-344, -297}` para o vendedor. As duas ficam a menos
de 4 unidades de `(-343, -289)`. Ou seja: **a coordenada do usuário e a do bot
que roda hoje concordam**, o que é a confirmação mais forte disponível sem
medir de novo. O valor que entra no código é o do usuário, `(-343, -289)`, porque
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

## 9. O QUE AINDA NÃO ESTÁ MEDIDO

Registrado aqui para não virar palpite depois:

1. **Nomes de área DENTRO da cave.** Só se sabe o de fora
   (`Black Wind Camp Dungeon` / `Outside Black Wind Camp`). Sem isso,
   `Waypoint.area` da HH é um marcador e não um dado, e
   `lugares.e_dentro_da_cave` não sabe responder pela HH.
2. **Os nomes exatos dos 4 bosses**, para a trava por identidade. Os rótulos do
   Lua entram como esperado e a leitura confirma.
3. **A coordenada do `Roaming Apothecary`** e o ponto de encostar nele.
4. **O template do link `West Suburb of Stone City`** e a coordenada da seta de
   rolagem do diálogo.
5. **O ponto de spawn interno.** O Lua usa `insidexY = {55, 33}`; não foi
   conferido na tela.
