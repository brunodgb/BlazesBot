# MEMÓRIA PRIMEIRO — o princípio, e como ele foi conquistado

> **A REGRA:** tudo que der para responder lendo a memória do jogo é lido da
> memória. Imagem, tecla-e-espera e template matching são **reserva**, para o
> que a memória não responde. Palavras do usuário em 25/08/2026:
>
> > *"eu tinha desistido de usar a memória, mas como agora conseguimos fazer
> > funcionar, ele vai ser muito importante... tudo que conseguirmos fazer
> > direto pela memória do jogo é melhor do que fazer por imagem ou de qualquer
> > outro jeito."*

Este arquivo existe porque a regra é **contra-intuitiva na história deste
projeto**: a memória já tinha sido tentada e abandonada. Quem chegar aqui daqui
a seis meses vai encontrar comentários antigos dizendo que leitura por ponteiro
não presta, e precisa saber por que a conclusão virou.

---

## Por que a memória tinha sido abandonada

Não foi preguiça nem preconceito. Foi medição, e a medição estava certa **para
o que se sabia na época**:

| tentativa | resultado medido | onde |
|---|---|---|
| `jogador+0x808` como alvo | acertava **1,0%** dos ciclos | item 37 |
| `jogador+0x80C` como reserva | é o **PET** | itens 26-28 |
| "slots estáticos de seleção" | eram o array de entidades, não seleção | itens 26-28 |
| cadeias de UI do GhostBot (`ADDR_UI_ROOT`, `CHAIN_TARGET_*`) | não chegam ao alvo | 21/08 |
| `0x0115CB80` | muda quando o alvo muda — *"não se sabe o que o valor É"* | itens 26-38 |

O veredito registrado era: **"o HP da memória está certo; falta a
IDENTIDADE"** — por entidade o alvo real acompanhava a barra em até 87,5% dos
ciclos, mas não havia como saber QUAL entidade era o alvo. Sem identidade, o
HP certo não serve para nada, e a tela virou a fonte por eliminação.

## O que mudou

Uma linha de código de 2019, num bot que ninguém tinha lido inteiro.

O `search_id()` do GhostBot (`lib/talisman_online_python/pointers.py`), escrito
para a versão **6139**:

```python
targetid = read_int(0x115CB20)            # o id do alvo
base     = 0x0107C6B0                     # o array de entidades
while base <= 0x0EFFFFFF:
    a = read_int(base)                    # ponteiro para a entidade
    if read_int(a + 0x8) == targetid:     # <<< A CHAVE
        pointer = a; break
    base += 0x4
x = read_float(pointer + 0x810) / 20
y = read_float(pointer + 0x814) / 20
```

**`0x0115CB80` guarda o ID da entidade selecionada, e a entidade carrega esse
mesmo id em `+0x8`.** O valor nunca foi um enigma: é uma **chave estrangeira**.
O projeto tinha as duas tabelas — o id e o array — e não tinha o `JOIN`.

Três coincidências que não são coincidência:

1. `self.base = 0x0107C6B0` é **idêntico** ao `ADDR_ENTITY_SCAN_BASE` daqui;
2. `+0x810`/`+0x814` divididos por **20** são os `OFF_X`/`OFF_Y` e a mesma
   escala do `Memory.position()`;
3. `0x115CB20 + 0x60 = 0x115CB80`, o rebase medido do banco de estáticos
   (o mesmo `+0x60` que a virada 6139 → 6400 exigiu dos outros).

## A confirmação, numa luta inteira

`18-CASAR-ALVO`, 25/08/2026, PID 3172. A cada 2 s, na MESMA captura: o id, a
entidade cujo `+0x8` bate, o HP dela, e o da barra da tela.

> **A ferramenta já não existe** — foi removida junto com o resto do aparato de
> descoberta (ver "O que foi removido", no fim). O log abaixo é o que ela
> produziu, e é a medição que autorizou a virada.

```
'Gun Witch'  nv50  hp=8/100   barra=6.7%    CASOU (1.3pp)
'Gun Witch'  nv50  hp=0/100   barra=0.0%    CASOU (0.0pp)
'Blaze Skull Marshal' nv50  hp=98/100  barra=99.3%  CASOU (1.3pp)
   ... 30 ciclos casando dentro de 5pp ...
'Blaze Skull Marshal' nv50  hp=1/100   barra=0.0%    <- a fase 1 PARA em 1
'Blaze Skull Marshal' nv51  hp=75/100  barra=50.0%   <- entidade NOVA, fase 2
```

**E nos ciclos em que as duas discordaram, a errada era a TELA:**

* `hp=6/100` contra `barra=23,1%` — a barra desenhada **atrasa**;
* `hp=75/100` contra `barra=50,0%` — a **amarela sobreposta à vermelha** da
  fase 2, que o `total_do_boss` tenta desentortar por conta.

## Por que a memória é melhor, item por item

Não é gosto. A tela tem uma lista de modos de falha que um inteiro lido da
struct simplesmente não tem — e **todos eles erram calados**, que é o pior tipo
de erro:

| defeito da tela | onde apareceu |
|---|---|
| piso de 0,7% com o mob MORTO (bordas diluindo a média por área) | item 36 |
| piso de 14,2% na conta APP (régua devolvendo float confiante medindo outra coisa) | item 36 |
| barra amarela sobreposta à vermelha na fase 2 | item 35, e o log acima |
| `EnemyDead.png` com falso positivo **medido** com o mob VIVO (0,955-0,971 contra limiar 0,85) | 20/08 |
| a busca proporcional quebrando fora de 1024×768 | 25/08 |
| atraso de um ciclo em relação ao estado real | o log acima |

Some-se: a memória **não paga captura de janela**. `alvo_atual()` no caminho
normal são ~5 leituras de 4 bytes contra um `PrintWindow` da janela inteira mais
um `matchTemplate`.

E ela responde com a janela **minimizada ou coberta**, que é o que permite rodar
várias contas em paralelo sem coreografia de foco.

---

## Como ficou, no código

`Memory.alvo_atual()` devolve `obj`, `id`, `nome`, `nivel`, `hp`, `max_hp`,
`pct` e `pos`. `TargetHybrid.ler()` chama ela PRIMEIRO e **não captura nada**
quando ela responde.

**O atalho do ponteiro.** O SLOT do array muda durante a luta (medido: 30 → 29
→ 28, conforme entidades em volta somem), mas o ENDEREÇO da entidade não. O
caminho normal é UMA leitura conferindo que o `obj` guardado ainda responde por
este id; a varredura dos `LIMITE_DE_ENTIDADES` slots só roda quando o alvo
troca.

**`hp == 0` é morte — menos na fase 1 do boss**, que para em `hp=1` e some,
nascendo a fase 2 como entidade nova (id novo, endereço novo, nível 50 → 51).
Não é caso a tratar: o boss nunca foi dado por morto por HP, e a regra
*"boss só morre ao SAIR DE BATALHA"* já cobria. Agora ela tem o porquê medido.

**A tela continua inteira como RESERVA.** Medido: no instante em que um alvo
novo é selecionado, a entidade pode demorar um ciclo a entrar no array (1
leitura em ~45 numa luta de boss). Cair para "não sei" ali gastaria uma volta do
laço à toa.

**O log da vida mudou junto**, e um defeito real quase passou: com a memória
respondendo, `info.barra` é `None` no caminho normal, e o `_valor_mostrado`
devolvia `0.0` nesse caso. O log mostraria **0% para todo alvo vivo**, e o
`registrar` acharia que a vida despencava a cada leitura. Hoje a linha sai
assim:

```
ALVO Gun Witch  100.0%  [##########]  (100/100, nv50)  alvo novo
ALVO Gun Witch   86.0%  [#########-]  (86/100, nv50)  -14%
ALVO Gun Witch   52.0%  [#####-----]  (52/100, nv50)  -34%
ALVO Blaze Skull Marshal   75.0%  [########--]  (75/100, nv51)  alvo novo
```

E `INVESTIGAR_O_TARGET_ID` foi **desligado**: `logs/target_id/` existia para
descobrir o que o valor significa, e a pergunta está respondida.

**Só a memória declara morte.** A tela ficou podendo dizer "ainda vivo" e "não
sei", nunca "morreu". A assimetria não é preciosismo: o `EnemyDead.png` tem
falso positivo **medido** com o mob VIVO (0,955-0,971 contra limiar 0,85), e o
que o segurava era só ser consultado abaixo de 10% de barra. Com a memória na
frente, esse resguardo saiu do caminho normal e sobrou uma reserva capaz de
declarar morte com um template que erra — o que explica o relato *"vi um TAB
aqui sem o mob ter morrido"*: basta a entidade faltar no array por um ciclo
(medido: 1 em ~45) com a barra num vão de redesenho.

Não se perde nada: a reserva cobre um vão de UM ciclo, e no seguinte a memória
responde — 0,15 s depois. E se a memória estivesse permanentemente muda, o bot
já não funcionaria de qualquer jeito: posição, HP e flag de combate saem todos
dela.

**O outro TAB, o que não é morte.** O bot tem exatamente dois lugares que
apertam a tecla de alvo, e é bom saber disso ao ler o log:

| onde | quando | é morte? |
|---|---|---|
| `atacar_ate_sair_de_combate` | `if morreu:` | **sim** |
| `_fase_boss` | o boss não engajou em `SEGUNDOS_ANTES_DO_TAB_NO_BOSS = 4.0` s | **não** — é ir buscar o boss que não veio |

O segundo sai com o mob vivo por desenho, e a linha de log dele diz
`TAB para ADQUIRIR o alvo (não é morte de ninguém)`. Um TAB novo em qualquer
outro lugar reprova em
`test_existem_exatamente_DOIS_lugares_que_apertam_a_tecla_de_alvo`.

**O portão de nome religou** (`USAR_PORTAO_DE_NOME = True`). Ele tinha sido
aposentado com a previsão exata do que aconteceu: *"quem descobrir uma fonte de
nome muda só este método, e o portão volta a funcionar inteiro"*. Mudou-se só
`_nomes_do_alvo`.

---

## O método que funcionou, e que vale repetir

Foi assim que a charada caiu, e é receita para a próxima:

1. **Ler o bot de referência inteiro, não só o pedaço que interessa.** A chave
   estava numa função (`search_id`) que o próprio GhostBot quase não usa — ela
   serve só para `target_location`, e a chamada vive atrás de um
   `with_timeout(..., timeout=1)` porque a varredura dele é força bruta em 130 MB.
2. **Desconfiar de "não se sabe o que o valor é".** Um valor que muda junto com
   uma seleção quase sempre é chave de alguma coisa. Pergunte "chave de QUÊ",
   não "que número é este".
3. **Procurar o mesmo endereço nas duas versões.** `0x115CB20` → `0x115CB80` é
   o `+0x60` do banco inteiro. Se um endereço herdado "não responde", teste o
   rebase antes de descartá-lo — foi o mesmo erro que manteve a câmera escrevendo
   em lugar nenhum por anos.
4. **Instrumentar antes de decidir.** O `18-CASAR-ALVO` foi escrito para
   REPROVAR de três jeitos (nenhuma entidade / mais de uma / diferença grande),
   não para confirmar. Ferramenta que só sabe concordar não mede nada.
5. **Comparar contra a fonte antiga, no MESMO instante.** Foi comparar com a
   barra que mostrou que a memória estava certa **e** que a tela estava errada —
   as duas informações vieram do mesmo log.

---

## O que ainda decide por imagem — o mapa do que dá para migrar

Inventário de 25/08/2026. Nada aqui é dívida a pagar às pressas: cada migração
precisa da mesma prova que o alvo teve.

| onde | o que decide por imagem | dá para memória? |
|---|---|---|
| `bot/login_states.py` | telas de login (usuário/senha, fila, erro) | **talvez** — `queue_text` e `modal_open` já existem em memória e ainda não decidem |
| `bot/bc/team.py` | painel de time | `team_size` **já existe** em memória; falta o `state_team_member.png` para comparar |
| `bot/bc/vendor.py` | janela de venda, caixa "precious" | `bag_open`/`bag_count` existem; a janela de venda não |
| `bot/bc/ui_service.py` | diálogo de NPC, painel Surroundings | `dialog_open` e `surroundings_first` **já existem** e estão EM VALIDAÇÃO |
| `bot/bc/routine.py` | entrada da cave, link | — |
| `bot/app/deletador.py` | linha de abas, ícone de deletar | — |
| `bot/watchdog.py` | "Connection interrupted" e afins | — |
| `bot/bc/combat.py` | `cemetery_guard.png` (único template que sobrou no combate) | **sim, e já está** — o nome da entidade responde |

**Os candidatos mais maduros** são os que o `2-DIAGNOSTICO` já imprime sob o
rótulo *"UI por memória — EM VALIDAÇÃO, não decide nada ainda"*: `dialog_open`,
`surroundings_first`, `bag_open`, `modal_open`, `loot_window_open`,
`system_menu_open`, `queue_text`. Eles estão prontos para virar decisão assim
que alguém rodar contra a tela e o resultado casar — exatamente o caminho que o
alvo percorreu.

## Compartilhado e específico — a regra que atravessa os ecossistemas

Pedido explícito do usuário em 25/08/2026, para outras sessões respeitarem:

> *"Como os 2 ecossistemas vão usar os pontos de memória em geral, a ideia é que
> ela seja universal e o `Memory.py` possa ser usado pelos 2, e futuramente até
> por mais ecossistemas que já estou pensando em criar... tem coisas que são
> específicas do ecossistema e tem coisas que são compartilhadas, e é importante
> existir essa distinção; e no compartilhado tem que cuidar para um não quebrar
> o outro. Então caso necessário use funções diferentes para ecossistemas
> diferentes, mas tente evitar retrabalho, ter funções duplicadas que fazem a
> mesma coisa."*

**O critério, em uma pergunta:** *isso é sobre o JOGO ou sobre o que este
ecossistema faz?*

| pergunta | onde mora | exemplo |
|---|---|---|
| sobre o **jogo** | `core/` — universal | `Memory.vida_pct()`, `in_battle()`, `alvo_atual()`, as TECLAS |
| sobre o **que este ecossistema faz** | `bot/bc/` ou `bot/app/` | *quando* curar, *até* quanto, *onde* se esconder |

O `Memory` responde **"quanta vida eu tenho"**. Quem decide **"a partir de
quanto isso é perigoso"** é cada ecossistema, e os dois têm números diferentes
de propósito: o BC usa `PotionConfig` (`hp_pct = 85`, `battle_hp_pct = 15`), o
APP usa `bot/app/cura.py` (`VIDA_PARA_CURAR = 30`).

**O retrabalho que isso evitou, na prática.** O percentual de vida do jogador
estava calculado inline em `bc/navigation.py`, e o APP ia escrever um terceiro.
Virou `Memory.vida_pct()`, no `core`, usado pelos dois. Sem isso seriam três
implementações da mesma conta — e a terceira é sempre a que ninguém atualiza.

**Não confundir com `EstadoDoJogo.hp_pct`:** aquela formata valores que o
`snapshot()` **já leu** e não toca na memória; esta **lê**. As duas devolvem o
mesmo número quando o snapshot é do mesmo instante, e a diferença importa em
laço apertado, onde reler é justamente o que se quer evitar.

**Quando é legítimo ter duas funções.** Quando a PERGUNTA é diferente, não
quando só o chamador é. `Memory.vida_pct()` (personagem) e
`AlvoInfo.hp_pct` (alvo) são duas perguntas; duas cópias de `hp/max_hp*100` para
o mesmo personagem são uma só.

**O que continua proibido:** `bc/` importar de `app/` e vice-versa; `core/`
importar de `bot/`. Travado por `tests/test_ecossistemas.py`, que lê o AST.

## Como adicionar uma leitura nova por memória

1. Endereço e offsets vão para `core/memory.py`, **com o comentário da
   medição** — `ADDR_*`/`OFF_*`/`CHAIN_*` são medição do binário, não ajuste.
2. Se o endereço vier do GhostBot/T-R0XX, teste **o valor e o `+0x60`**
   (`core/rebase.py` já faz isso para vários).
3. Ferramenta temporária em `blazesbot/tools/`, que **só lê e só loga**, e que
   sabe REPROVAR.
4. Rode contra a fonte antiga no MESMO instante, e guarde o log.
5. Só então a decisão migra — e a fonte antiga fica como **reserva**, não
   apagada.

---

## O que foi removido, e por quê

Descoberto o mecanismo, o aparato de DESCOBERTA vira peso morto. Removido em
25/08/2026, a pedido do usuário: *"tudo que era para teste referente à memória,
que agora já está 100%, pode remover em definitivo"*.

| removido | o que era | o que respondeu |
|---|---|---|
| `blazesbot/tools/find_target.py` (71 KB) | os 3 modos do `10-DESCOBRIR-ALVO`: busca por nome, pointer scan e teste de estáticos | qual é o alvo — **e já estava quebrado**: importava `ADDR_TARGET_SELECT_BASE` e `CHAIN_TARGET_*`, que não existem mais |
| `blazesbot/tools/casar_alvo.py` + `18-CASAR-ALVO.bat` | o casamento id ↔ entidade contra a barra | se `+0x8` vale na 6400 — **vale** |
| `TargetHybrid.investigar()` + `INVESTIGAR_O_TARGET_ID` | gravava cada troca de id em `logs/target_id/` | o que o valor significa — **o ID da entidade** |
| `--find-target`, `--pointer-scan`, `--test-static-target`, `--target-addr`, `--target` | as flags dos três modos | — |
| `logs/descobrir_alvo/`, `logs/pointer_scan/`, `logs/target_id/`, `logs/correlacao/`, `logs/casar_alvo/` | os dados brutos daquelas medições | — |

**A conferência permanente ficou no `2-DIAGNOSTICO`**, que agora imprime o alvo
inteiro pela memória. É a diferença entre DESCOBRIR (uma vez, com ferramenta
dedicada) e CONFERIR (sempre, com o diagnóstico que já existe):

```
[alvo] 'Gun Witch' nv50 hp=8/100 (8.0%) pos=(103, -404)
    id=0x01832bd5 -> entidade 0x2e9a99b0  (o id é chave: a entidade guarda ele em +0x8)
```

**Se o jogo atualizar**, é lá que o problema aparece, e o bloco diz qual dos dois
endereços andou:

* id respondendo e **nenhuma** entidade com ele ⇒ `ADDR_ENTITY_SCAN_BASE` mudou;
* id **sem responder** ⇒ `ADDR_TARGET_ID` mudou.

E a receita para reconstruir a ferramenta, se um dia for preciso, está em "O
método que funcionou" acima — junto com o algoritmo do `search_id()` inteiro,
que é o que a ferramenta fazia.
