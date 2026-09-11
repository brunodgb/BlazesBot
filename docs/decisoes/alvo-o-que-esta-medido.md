# O alvo: o que está MEDIDO, o que está em ABERTO, o que foi REFUTADO

Este arquivo existe por ordem do usuário, em 20/08/2026:

> "Você não vai mais trabalhar com achismo, direto você está voltando atrás no
> que você faz ou fala, você deve ir em base a tudo que estou entregando de
> informação e documentar os possíveis acertos, então vamos caminhando de pouco
> em pouco até ficar 100% apenas em base o que for correto"

O pedido é justo e tem causa. Eu afirmei e voltei atrás três vezes no mesmo dia:
*"o mob nunca passa por HP 0"*, *"escala 243 não prova pet"* e *"`+0x18` é o
ID"*. Nas três, a frase saiu com mais confiança do que a medição sustentava.

**Regra deste arquivo: nada entra na tabela MEDIDO sem a linha de log que prova.**
Hipótese vai para ABERTO, e continua lá até virar medição. Quem escreve aqui não
pode promover uma linha de ABERTO para MEDIDO sem colar a evidência junto.

---

## MEDIDO — cada linha tem a evidência ao lado

| # | fato | evidência |
|---|---|---|
| 1 | **`jogador+0x808` é a SELEÇÃO.** Nulo quando nada está na mira; entrega a struct certa quando há alvo, com o nome legível inline (`+0xBC`). | `10-DESCOBRIR-ALVO` 09:55 (`0x808=0`), 10:04 (`->'Gun Witch'`), 13:49/13:51/13:51, 17:58 |
| 2 | **`jogador+0x80C` é o PET do próprio personagem.** | seis rodadas × cinco contas, 20/08/2026 |
| 3 | **243/243 é escala de PET**, e a grade traz os pets de outros jogadores na mesma escala. A escala diz *pet*, não diz *de quem*. | grade das 17:59: `Ganoderma` nv30 243/243 (pet de outro), `0x315ee648` nv22 243/243 (o próprio) + confirmação do usuário |
| 4 | **100/100 é a escala de inimigo — e também a de recurso de coleta fora da cave.** Recursos **não recebem TAB** e não existem dentro da cave, então nunca chegam ao `+0x808`. | grade das 17:59: `Fresh Berry` nv10 100/100, `Magnesite Ore` nv6 100/100 + explicação do usuário |
| 5 | **O mob morto FICA na seleção** com `hp = 0/100`, ponteiro válido e nome legível, por **7 a 13 segundos**. | `combate.log` 20:36:44→20:36:57 (13 s, Gun Witch) e 20:36:55→20:37:02 (7 s, Guard of Screw Bay) |
| 6 | **`hp = 0` chega ANTES** do ponteiro sumir e ANTES da flag de combate baixar. | mesmo log: 27220 hp=0 às 20:36:44, ponteiro sumiu 20:36:57, flag 20:37:02. 29500 hp=0 às 20:36:55, flag 20:36:57, ponteiro 20:37:02 |
| 7 | **O ponteiro NUNCA ficou pendurado.** Zero ocorrências do estado `pendurado`. | placar: `estado_do_alvo` só tem as linhas `valido` (11.693) e `nulo` (692); `pendurado` não existe |
| 8 | **`flag_combate 0x854` GABARITOU** — primeiro ponteiro a passar no critério. | placar: 15.356 amostras, 0,1% erro, 30 runs |
| ~~9~~ | ~~A struct do mob morto acaba sendo removida da grade~~ **DERRUBADO em 20/08/2026 — era filtro da minha ferramenta.** Ver pergunta G. | — |
| 10 | **`+0x18` é vtable, não ID.** O mesmo `0x00edc828` apareceu para mobs diferentes, em endereço de faixa de módulo. | três rodadas do `10-DESCOBRIR-ALVO`, 20/08/2026 |
| 11 | **`OFF_HP = 0x3B8` está correto.** | o alvo real leu 3/100 por ele; e o `combate.log` mostrou 100 → 48 → 24 → 0 no mesmo campo |
| 13 | **`describe_object` do `10-DESCOBRIR-ALVO` descartava TODO cadáver** (`_plausible_hp` exigia `1 <= hp`). Nenhum dos seis relatórios tem uma linha com `hp = 0`. | os seis JSON em `logs/descobrir_alvo/`: o menor HP em grade é 7, nunca 0 |
| 14 | **A validação da PRODUÇÃO (`_entidade_no_campo`) NÃO olha HP** — só nível e HP máximo. Por isso o bot devolve o cadáver, e o `pendurado` do placar continua em zero. | fonte de `memory._entidade_no_campo` + placar |
| 15 | **A memória CONFERE com a tela.** `0x808 -> 0x35691b48`, memória **57/100 (57,0%)** contra barra **56,8%** — **0,2pp**. Primeira comparação direta com gabarito, e o mob era exatamente o único que o usuário tinha atacado. | `27220-211528.json`, 21:15:28 |
| 16 | **Entidade tem o MESMO layout do jogador, inclusive o campo de alvo em `+0x808`.** `0x35692350` é `0x35692c50 + 0x808` e guarda ponteiro para outra entidade — mobs também têm alvo. | mesma leitura, seção (c) |
| 17 | **`jogador+0x80C` fica ZERO quando o pet não está invocado**, mesmo com 17 entidades em escala de pet (243/243) na grade. Ele não é "o pet mais próximo": é o pet DAQUELE personagem, ou nada. | mesma leitura (`0x80C = 0`, 17× 243/243 na grade) contra a das 20:36 (`0x80C = 0x356ae720`) |
| 18 | **A struct do mob morto NÃO é removida — ela FICA na grade em `0/100`.** `0x35691b48` estava em **57/100** às 21:15:28 e em **0/100** às 21:18:54, **mesmo endereço, mesmo slot**, 3m26s depois. Isto FECHA a pergunta G. | `27220-211528.json` × `27220-211854.json` |
| 19 | **O nome em `+0xBC` PARA de ler quando o mob morre** — `0x35691b48` lia `'Gun Witch'` e passou a ler `None`. **Mas isso NÃO é sinal de morte:** na mesma janela `0x35681bd0` ('Evil Centipede') também virou `None` **estando em 100/100**. O nome é instável nos dois estados. | mesmo par de leituras |
| 20 | **O `EnemyDead.png` dá FALSO POSITIVO com o mob VIVO, e não por margem.** Três TABs em nove segundos com `hp_memoria=35`, fonte única `marcador de morte na tela`, e escore **0,971 / 0,955** contra limiar 0,85. | `logs/blazesbot.log` 21:40:40 / :46 / :49 + escores no log de dev |
| 21 | **O `_por_consenso` deixava o marcador ATROPELAR a barra desenhada** — `testemunhas` vencia `vivo` incondicionalmente, contrariando a regra que o `CLAUDE.md` já escrevia para o marcador. | mesma linha de log: `(1 fonte(s))` com a barra em ~35% lida na mesma passada |
| 22 | **`jogador+0x808` NÃO é a seleção visual do jogador** — aponta para `Cemetery Guard` (HP cheio) enquanto a tela mostra `Gun Witch` com HP ~30%. | 4 execuções `10-DESCOBRIR-ALVO` (01:13, 01:14, 01:33, 01:34): `+0x808` SEMPRE = Cemetery Guard 100/100; barra SEMPRE ~30%; grade SEMPRE tem Gun Witch batendo com a tela |
| 23 | **Existem DOIS ponteiros ESTÁTICOS** que apontam DIRETO para a entidade alvo visual (sem passar pelo player): RVA `0x00C7C8D0` e `0x00C7C994`. | `pointer_scan` em `27220-0x310fca98-013249.json`: 2 endereços estáticos nível 1, nenhum `DENTRO DO JOGADOR`, nenhuma cadeia UI conhecida chega |
| 24 | **Cadeias conhecidas (UI_ROOT, TARGET_SELECT_BASE) NÃO chegam ao alvo visual** — nem com deslocamento ±0x60, nem seguindo os elos. | `pointer_scan`: 0 resultados para `ESTATICO ADDR_UI_ROOT...` e `CADEIA CHAIN_TARGET_... (funciona!)` |
| 25 | **A seleção visual é guardada em tabela estática global**, não no player. O `jogador+0x808` é outro campo (ex.: último alvo atacado / target do servidor). | Hipótese consolidada pelos itens 22-24 |
| 12 | **O byte da flag é o `+0x854`.** | `combate.log` grava o diff: `+0x854: 1 -> 0` em toda transição SIM→nao |
| 26 | **Os "slots de seleção visual" são entradas do ARRAY DE ENTIDADES, passo 4.** Os 15 RVAs estáticos achados pelos 7 `pointer_scan` são todos múltiplos de 4 dentro de `[ADDR_ENTITY_SCAN_BASE + 0x64, +0x2E8]` — índices 25 a 186. | os 7 JSON de `logs/pointer_scan/`, cruzados com `ADDR_ENTITY_SCAN_BASE = 0x0107C6B0` |
| 27 | **Cada um desses RVAs guarda UMA entidade e não muda: 15 de 15 guardaram um ÚNICO valor** ao longo dos 7 scans. Alvos diferentes apareceram em RVAs diferentes porque cada entidade tem o seu slot. | mesmos 7 JSON: nenhum RVA repetiu com valor diferente |
| 28 | **Nenhum slot acompanha a barra.** Três ciclos seguidos com a barra caindo `71,4% → 65,6% → 55,4%`: todos os 9 slots que resolveram devolveram o MESMO objeto e o MESMO `100/100`. | `logs/pointer_scan/log-27220.txt`, três blocos consecutivos |
| 29 | **`hp <= 0` na memória NUNCA apareceu com alvo vivo desenhado: 0 ocorrências em 152 leituras** que trouxeram barra e HP na mesma linha. | `logs/dev/arquivo/blazes-dev-2026-08-20.jsonl`, linhas `ALVO` com `barra=` e `hp_memoria=` |
| 30 | **Depois que o pet saiu do `target_object` (19h), o erro médio do `0x808` contra a barra caiu para 4,98pp** nas leituras discriminantes, com as melhores a **0,2pp** (barra 56,83 × hp 57). Antes das 14h era 29,70pp. | mesmo arquivo, recortado por hora |
| 31 | **O bot ficava CEGO no instante da morte.** 561 das 1.431 leituras de combate (39%) saíram com `fonte=nada`; **as 561 tinham `hp_memoria=0` e `marcador="-"`** (tela nunca capturada). 63 das 77 lutas tiveram janela cega, mediana **6,7 s**, máximo **12,5 s**, sempre abrindo em t≈2,5 s. | mesmo arquivo; causa em `combat._alvo_morreu` (curto-circuito por fonte sem voto) |
| 32 | **89 dos 194 vereditos `vivo` (46%) foram decididos só por "sem marcador de morte"**, com a barra indisponível — vários com `hp_memoria=243`, que é o pet. | mesmo arquivo |
| 34 | **A tabela lida com PASSO 4 lista 57 a 137 entidades por ciclo** (antes: 7). Aparecem pets (243), jogadores (729) e duas escalas novas — `48` e `10`. | `logs/correlacao/*.jsonl`, 21/08/2026, 4 coletas |
| 35 | **A razão barra/memória do boss é 1,0 OU EXATAMENTE 2,0** — 54 ciclos contra 43, com razões medidas de 1,988 a 2,080, nunca um valor intermediário estável. A fase 2 tem DUAS barras: a memória conta o TOTAL, a tela desenha a ATUAL. `44/100` na memória aparece como `87,5%` na tela. | `27220-20260821-113607.jsonl` (97 ciclos discriminantes com o boss na mesa) + `27220-...-072606.jsonl` |
| 36 | **`vision.vida_do_alvo` devolve número confiante quando NÃO está olhando o quadro do alvo.** Na conta APP produziu **14 valores distintos** em quatro blocos, com piso em **14,2** e vãos de `17,2→35,4`, `37,9→54,7`, `57,2→99,8`; e em **96% dos ciclos discriminantes nenhuma** das ~69 entidades tinha aquele HP. Na conta BC, 38 e 78 valores contínuos desde 0,0. | `29500-20260821-071943.jsonl` × os dois de BC |
| 37 | **Nenhum ponteiro identifica QUAL entidade é o alvo.** Acerto discriminante: `jogador+0x808` **1,0%** (97 respostas), melhor slot (`0xc7c714`) **30,1%**, `0x80C` 0%. Por ENTIDADE, o alvo real chega a **87,5%** (`Blaze Skull Marshal`, 35/40) — ou seja o HP está certo e a IDENTIDADE é que falta. | `analisar_correlacao.py` sobre as 4 coletas |
| 38 | **O nome em `+0xBC` é buffer reciclado.** O MESMO endereço `0x2c963048` leu, em sequência: `'Guard of Screw Bay'`, `'2ed Villager'`, `'Cursed Villager'`, `'You got 196 Experience'`, `'0.bmp'`, `'ctor\\eff_10plus.eva'`, `'Bip_mon008 R UpperArm'`. Não serve como identidade. | `29500-20260821-071943.jsonl`, série do mesmo `obj` |
| 33 | **`trocas_ptr` era zero por construção.** `VigiaDoAlvo.observar` zerava `ponteiro_anterior`/`trocas_de_ponteiro` a cada leitura (duas linhas coladas do `__init__`). Nas 1.431 linhas o rótulo `MUDOU` nunca saiu, inclusive quando o ponteiro trocou entre duas linhas (`0x35678288` → `0x356b2b40`). | mesmo arquivo + leitura do fonte |

---

## ABERTO — hipótese, não afirmação

| # | pergunta | por que ainda não é resposta |
|---|---|---|
| A | **`hp <= 0` na seleção serve para decidir morte?** | O item 5 e 6 mostram que o sinal existe e é o mais cedo. Mas *"existe"* não é *"nunca erra"*. A prova `alvo_morto_por_hp` começou a medir agora; sem placar não há resposta. |
| B | **Por que a memória do `0x808` diverge da barra, às vezes?** **Pista forte em 21:18:54, e ela muda a hipótese. RESPOSTA PARCIAL em 21/08: o `0x808` NÃO é a seleção visual.** | **Item 22 MEDIDO:** `jogador+0x808` aponta para `Cemetery Guard` (100/100) enquanto a tela desenha `Gun Witch` ~30%. O `pointer_scan` achou DOIS ponteiros estáticos (RVA `0xC7C8D0`, `0xC7C994`) que apontam DIRETO para o Gun Witch visual — sem passar pelo player. Cadeias UI conhecidas NÃO chegam. **Hipótese forte:** a seleção visual é tabela estática global; `0x808` é "último alvo atacado" ou target do servidor. **Falta validar** se um dos dois RVAs bate consistentemente como seleção visual (modo 3 do `10-DESCOBRIR-ALVO`). |
| I | **Por que o `EnemyDead.png` casa a 0,97 com o mob vivo?** | Subir o limiar não resolve (0,971 é casamento confiante). O template está achando algo real na faixa do quadro do alvo que não é o marcador de morte. **Não sei o quê**, e o veto conserta o SINTOMA sem responder isto. Vale recortar o template de novo, ou fotografar a faixa quando ele casar. |
| H | **29 das 44 entidades da grade não têm nome legível** (e 2 leem lixo: `'9@'`, `'19@'`). O nome mora inline em `+0xBC` numas e por ponteiro em outras — na 27780 `+0xBC via ptr` deu `'Janitor of Guild Demesne'`. | Não bloqueia o alvo (a seleção lê o nome certo), mas bloqueia qualquer decisão baseada em VARRER a grade por nome. Falta descobrir o que separa os dois casos. |
| C | **O `alvo_presente` a 17,8% de erro é defeito ou é o cadáver?** | O item 5 explica a maior parte: ponteiro válido com a barra vazia é o cadáver, não falha do ponteiro. Mas "a maior parte" não é "toda", e a repartição só sai comparando com o `alvo_morto_por_hp`. |
| D | **`modal 0x012ce3bc`** | 977 amostras, 3,6% erro, 7 runs. Ida ao vendedor é rara; falta run. |
| E | **`team_size`** | Sem gabarito — falta o template do painel de time. |
| F | **A identidade da seleção (`alvo_selecao`)** | O critério "mudou no TAB" reprova o campo CERTO quando sobra um mob vivo, porque o TAB reseleciona o mesmo. A metade que credita ("não muda sem TAB") ainda não produziu amostra. |

---

## REFUTADO — e o que cada erro custou

| afirmação minha | o que a derrubou | o erro de método |
|---|---|---|
| *"O mob que morre não vai para HP 0 — a struct é removida"* | grade das 17:59 com `0/100`; e o `combate.log` das 20:36 com o cadáver parado em 0 por 13 s | conclusão de **ausência** a partir de amostragem esparsa: as leituras da cave estavam a 53 s e 96 s de distância |
| *"Escala 243 não prova pet"* | o usuário: `Ganoderma` **também é pet**, de outro jogador | tratei *"não é o seu pet"* como *"não é pet"* — joguei fora uma heurística boa |
| *"`+0x18` é o provável ID"* | o mesmo valor para três mobs diferentes | li o rótulo da minha própria ferramenta como se fosse medição |
| *"A struct do mob morto é REMOVIDA da grade"* | o item 13: `describe_object` descartava todo `hp = 0`, então a grade caía uma linha por morte **por causa do filtro** | li a saída da minha própria ferramenta como se fosse o cliente falando — o mesmo erro do rótulo `"provável ID"`, pela terceira vez |
| *"Ausência do ponteiro é o sinal de morte"* | itens 5 e 6: a ausência chega **7 a 13 s DEPOIS** do `hp = 0` | escolhi o sinal antes de medir a latência dos dois |
| *"Existem DOIS ponteiros estáticos que apontam para o alvo visual"* (item 23) e *"a seleção visual é guardada em tabela estática global"* (item 25) | itens **26, 27 e 28**: os RVAs são entradas do array de entidades (passo 4), **cada um guarda uma entidade fixa**, e nenhum acompanha a barra caindo | li o resultado do meu próprio `pointer_scan` como se fosse o cliente falando — **a quarta vez** que este erro de método aparece aqui. Um scan feito com o mob X selecionado acha os endereços que apontam para X; sem repetir o scan com OUTRO alvo e conferir se o MESMO endereço mudou de valor, "aponta para o alvo" e "aponta para aquela entidade" são indistinguíveis |

---

## O `10-DESCOBRIR-ALVO`: o que ele faz e o que ele NÃO faz

Avaliação de 20/08/2026, a pedido do usuário. **Ele não está 100%** — e o que
faltava era estrutural, não detalhe.

### O buraco que foi fechado hoje: ele não tinha gabarito

A ferramenta lia **só memória** (`capture_window` e `vision` apareciam **zero**
vezes no arquivo). O único conferidor era o nome que o usuário digita, e nome
confere **identidade**, não **valor**. Consequência direta: ela nunca teve como
responder a pergunta B desta página —

    alvo_hp|0x808   ultimo erro: 14:46:00 leu=100 esperado=3.5 erro=96.5pp

— porque repetiria o `100` com a mesma confiança da memória.

*A tela é o gabarito e a memória é a aluna* é a regra do projeto inteiro, e esta
ferramenta era **a única peça da investigação que não a seguia**.

Agora ela captura a janela do PID no mesmo instante e compara:

- `MEMORIA CONFERE COM A TELA` — diferença ≤ 3pp;
- `MEMORIA DIVERGE DA TELA` — e aponta esta página, pergunta B;
- `SEM GABARITO DE TELA` — com o motivo (minimizada, quadro em branco, quadro do
  alvo não desenhado). **Ausência de gabarito é dita em voz alta**, senão o
  relatório volta a ser memória não conferida com cara de conclusão.

**UMA captura só**, reusada no veredito e no JSON. Duas leituras da tela em
instantes diferentes fariam o relatório poder discordar de si mesmo.

### Cadáver na grade agora é rotulado

Item 5 desta página: o morto fica na grade e na seleção por 7 a 13 s. O
diagnóstico de memória chegou a listar `0/100` sob o título *"entidades VIVAS por
perto"*, e quem lê uma linha dessas escolhe um cadáver como candidato. A grade
marca `[MORTO -- a struct fica na grade por segundos]`, e o veredito avisa quando
a própria seleção é um cadáver.

### O defeito que as suas duas leituras de 20:36 e 20:53 expuseram

As duas saíram com **dois vereditos contraditórios sobre o mesmo ponteiro**:

```
* SELECAO PENDURADA: ... essa struct NAO valida mais como entidade
* SELECAO CONFERE:   ... = 'Gun Witch' ... O ponteiro do alvo esta CERTO
```

A grade do mesmo relatório tinha aquele endereço como `nv 50, 10/100,
'Gun Witch'`. A frase "não valida" era falsa.

**Causa:** eu escrevi o veredito em cima de `describe_object`, que recusa
`hp = 0` (item 13). Todo alvo morto virava "pendurado". E `describe_object` **não
é** o validador que o bot usa: `_entidade_no_campo` olha nível e HP máximo, e
**não olha HP** (item 14). Ferramenta que julga por regra diferente da produção
descreve um bot que não existe.

**Corrigido em três lugares:**

1. `describe_object(obj, aceitar_morto=True)` — a grade e o veredito passam a
   enxergar cadáver; o default preserva o comportamento antigo para o
   `find_base`, cuja busca da struct do jogador foi calibrada com o filtro.
2. O estado da seleção agora sai por **um** veredito, mutuamente exclusivo e com
   o critério da produção: `SELECAO VIVA` / `SELECAO MORTA (nao pendurada)` /
   `SELECAO PENDURADA`.
3. O `CONFERE` virou `O NOME CONFERE`, e diz explicitamente que confere
   **identidade**, não estado. A frase *"o ponteiro do alvo está CERTO"* saiu.

**O que era "pendurado" nas suas duas leituras era, quase certamente, `hp = 0`.**
A de 20:53 tem a barra da tela em `0.0%`, o que corrobora. A próxima leitura no
mesmo momento dirá `SELECAO MORTA` em vez de `PENDURADA` — e se ainda disser
`PENDURADA`, aí é o caso raro de verdade.

### O que AINDA falta, e é o próximo passo

**Ela é um INSTANTE, e o que interessa é a SÉRIE.** Tudo o que esta investigação
descobriu de valor veio de leituras repetidas: os 13 segundos de cadáver saíram
do `combate.log`, não de um retrato. E o usuário já provou, duas vezes, que a mão
não acerta o instante.

Um modo de **amostragem** — a mesma varredura de candidatos, repetida N vezes em
M segundos, relatando quais campos **acompanharam** a barra da tela e quais só
coincidiram uma vez — é o que separa o campo certo do acaso. É o modelo do Cheat
Engine (o discriminador é a MUDANÇA, não a varredura) aplicado à ferramenta
manual.

**Não foi feito ainda**, de propósito: um passo por vez, e o gabarito de tela
precisa existir antes, porque é ele que dá o eixo contra o qual "acompanhar"
significa alguma coisa.

## Como esta investigação continua

Um passo por vez, e cada passo com evidência:

1. **Deixar o placar acumular** `alvo_morto_por_hp`. Ele responde a pergunta A,
   que é a que decide se o veredito de morte muda.
2. **Nada é promovido automaticamente.** `MEMORIA_VOTA_NA_MORTE = False` continua,
   e a decisão de ligar é do usuário, olhando o placar.
3. **A pergunta B fica esperando dado**, não fica esperando teoria minha.

---

## 39. A chave do alvo estava no GhostBot o tempo todo (25/08/2026) — **MEDIDO**

**FECHADO.** Confirmado numa luta inteira no cliente 6400, e é o item que
encerra esta investigação: o alvo passou a ser lido da MEMÓRIA e a tela virou
reserva. Ver `docs/decisoes/memoria-primeiro.md` para a virada completa.

O projeto sabia as duas metades e não sabia que elas se encaixavam:

| metade | o que se sabia | onde |
|---|---|---|
| o id | `0x0115CB80` muda quando o alvo muda, `0` é sem alvo — *"não se sabe o que o valor É"* | itens 26-38 |
| as entidades | `0x0107C6B0` é array de ponteiros, e o HP delas **está certo** (87,5% contra a barra) | item 37 |

O `search_id()` do GhostBot (`lib/talisman_online_python/pointers.py`) junta:

```python
targetid = read_int(0x115CB20)            # o MESMO endereço, antes do +0x60
base     = 0x0107C6B0                     # o MESMO array de entidades
while base <= 0x0EFFFFFF:
    a = read_int(base)                    # ponteiro para a entidade
    if read_int(a + 0x8) == targetid:     # <<< A CHAVE DE JUNÇÃO
        pointer = a; break
    base += 0x4
x = read_float(pointer + 0x810) / 20      # os MESMOS OFF_X / OFF_Y / 20
y = read_float(pointer + 0x814) / 20
```

Três coincidências que não são coincidência:

1. `self.base = 0x0107C6B0` é **idêntico** ao `ADDR_ENTITY_SCAN_BASE` daqui;
2. `0x810`/`0x814` divididos por **20** são os `OFF_X`/`OFF_Y` e a mesma escala
   do `Memory.position()`;
3. `0x115CB20 + 0x60 = 0x115CB80`, o rebase medido do banco de estáticos.

**Conclusão candidata:** `0x0115CB80` guarda o **ID da entidade selecionada**, e
a entidade guarda esse id em **`+0x8`**. O valor nunca foi enigma — é chave
estrangeira. O bot já tinha as duas tabelas e não tinha o `JOIN`.

**Por que isso importa tanto:** o item 37 mediu que o HP *por entidade* está
certo e que o problema era só saber DE QUEM. Se `+0x8` casar, volta tudo de uma
vez: nome, HP exato, nível e posição do alvo, sem depender da tela — e o
`USAR_PORTAO_DE_NOME`, aposentado por falta de fonte de nome, pode religar.

**Como o GhostBot usava:** só para `target_location` (ir até o alvo). Ele
**varre até 130 MB de memória** procurando qualquer dword que aponte para uma
struct com aquele id — daí o `with_timeout(..., timeout=1)` em volta. Aqui não
precisa: o array já é conhecido, são 512 slots.

**O experimento foi o `18-CASAR-ALVO`** (removido depois de responder). A cada
2 s, na MESMA captura, ele lia o id, achava a entidade cujo `+0x8` bate, e
comparava o HP% dela com o da BARRA DA TELA. Podia reprovar de três jeitos —
nenhuma entidade com o id, mais de uma, ou diferença acima de 5pp.

**Não reprovou por nenhum.** Uma luta inteira, `Gun Witch` e as duas fases do
boss, casando dentro de 5pp — e nos poucos ciclos de divergência a errada era a
TELA (`hp=6/100` contra `barra=23,1%`; `hp=75/100` contra `barra=50,0%` na fase
2, por causa da amarela sobreposta).

**Dois achados de brinde, dos quais o desenho depende:**

1. **A fase 1 do boss NÃO zera** — para em `hp=1` e some, nascendo a fase 2 como
   ENTIDADE NOVA: id novo, endereço novo, e **nível 50 → 51**. É o porquê medido
   da regra *"boss só é dado por morto quando SAI DE BATALHA"*.
2. **O SLOT do array muda durante a luta** (30 → 29 → 28) mas o ENDEREÇO da
   entidade não. Por isso o atalho do ponteiro em `alvo_atual()` guarda o `obj`,
   e não o índice.

**A conferência permanente ficou no `2-DIAGNOSTICO`**, que imprime o alvo
inteiro pela memória. Descoberto o mecanismo, a pergunta que sobra é "ainda
responde?" — e essa é de diagnóstico, não de ferramenta temporária.


---

## 39. A "array de entidades" provavelmente NÃO é uma array de entidades — ABERTO (26/08/2026)

**Relato do usuário, com o `9-VIGIAR-COMBATE` na frente:**

> *"Tem alguma coisa fazendo nem sempre ler o target. Eu vejo que o value do
> `0115CB80` altera, mas não acha o target no array — mas em algum lugar da
> memória do jogo ele está, PQ O MOB EXISTE, A CHAVE EXISTE."*

### O que o log mostra

```
[08:54:52] ALVO Rose Snake  100.0%  (100/100, nv61)  alvo novo
[08:54:54] ALVO #230967247    0.0%                   alvo novo
[08:54:58] ALVO Rose Snake  100.0%  (100/100, nv61)  alvo novo
[08:55:00] ALVO #230967247    0.0%                   alvo novo
```

E na sequência do TAB, quase só ausências:

```
[08:55:23] ALVO #230902882   [08:55:25] ALVO #196152077
[08:55:28] ALVO #220472947   [08:55:30] ALVO #230967247
[08:55:31] ALVO Rose Snake  100.0%  (100/100, nv61)
```

**O `mudou` é `True` nas duas pontas**, então `ADDR_TARGET_ID` está realmente
mudando de valor — não é a entidade sumindo do array com o id parado.

### A aritmética que levanta a hipótese

A janela varrida por `_procurar_entidade` é
`ADDR_ENTITY_SCAN_BASE` (`0x0107C6B0`) mais `LIMITE_DE_ENTIDADES * 4` bytes, ou
seja, até `0x0107CEB0`. Os **sete "slots de seleção visual"** descobertos em
21/08/2026 caem TODOS dentro dela:

| slot estático | índice na janela |
|---|---|
| `0x0107C714` | 25 |
| `0x0107C71C` | 27 |
| `0x0107C758` | 42 |
| `0x0107C79C` | 59 |
| `0x0107C8FC` | 147 |
| `0x0107C948` | 166 |
| `0x0107C998` | 186 |

**Hipótese:** aquilo não é uma array de entidades. É uma região estática que
contém, entre outras coisas, ponteiros para entidades **recentemente
selecionadas**. Achar um mob ali é sorte de ele ter passado pela seleção — e o
log bate exatamente com isso: os que aparecem inteiros são os engajados, e o TAB
ciclando produz quase só ausências.

A interpretação de "array" veio do `search_id()` do GhostBot e nunca foi
medida — foi herdada.

### O que os ids sugerem

| id não achado | hex | | id conhecido BOM | hex |
|---|---|---|---|---|
| 251809232 | `0x0F024DD0` | | 20187649 | `0x01340A01` |
| 230967247 | `0x0DC447CF` | | | |
| 230902882 | `0x0DC34C62` | | | |
| 196152077 | `0x0BB10B0D` | | | |
| 220472947 | `0x0D242673` | | | |

Os não achados vivem em `0x0B..0x0F`; o único id BOM registrado (do log de
25/08) vive em `0x01`. **Isso é sugestivo, não é medição** — há um id bom só na
amostra, e um id não prova família.

### Como confirmar — o instrumento já existe

`core/target_hybrid.investigar_alvo_perdido()`, chamado pelo `9-VIGIAR-COMBATE`
**uma vez por id**: varre o processo atrás do id, e para cada ocorrência testa
se `endereço - 0x8` tem cara de struct de entidade (alinhado, `hp <= max_hp`,
nome/nível legíveis). Depois pergunta se existe ponteiro para esse `obj` dentro
da janela varrida.

Os três desfechos, e o que cada um quer dizer:

| o que a investigação diz | conclusão |
|---|---|
| a entidade EXISTE e **não** está na janela varrida | a hipótese está certa: procuramos no lugar errado |
| a entidade existe **e** está na janela | a hipótese caiu; o defeito é outro (cache, corrida) |
| o id não aparece em lugar nenhum | `ADDR_TARGET_ID` está guardando algo que não é id de entidade |

**Ainda não foi rodado com o jogo na frente.** Enquanto não for, isto é
hipótese com aritmética atrás — e não medição.

### O que NÃO fazer antes de medir

Alargar `LIMITE_DE_ENTIDADES` no chute. Se a região não for uma array, varrer
mais bytes só aumenta a chance de casar um inteiro qualquer com o id procurado —
e um falso positivo aqui vira um mob inventado, com HP inventado, decidindo TAB
e morte.


---

## 40. A hipótese do item 39 foi REFUTADA pela primeira medição (26/08/2026)

Rodei o `9-VIGIAR-COMBATE` com o jogo na frente. **A hipótese dos "slots de
seleção" não se confirmou** — e é importante que isso fique escrito, porque a
aritmética que a sustentava continua verdadeira e vai tentar convencer a próxima
pessoa de novo.

### O que a investigação devolveu

```
investigando o id 254031539 (0x0F2436B3)...
  o id NÃO APARECE em lugar nenhum da memória

investigando o id 232865654 (0x0DE13F76)...
  o id aparece em 3358 lugar(es).
  nenhum desses endereços tem cara de entidade

investigando o id 230967247 (0x0DC447CF)...
  o id aparece em 25 lugar(es).
  0x1095C21C  ?  nv1   hp=278248512/290249544
  0x1095C228  ?  nv32  hp=1/390876288
```

**Ela NUNCA achou uma entidade de verdade fora da janela varrida.** Achou lixo —
e os dois "candidatos" reaparecem para ids DIFERENTES, que é a assinatura
clássica de falso positivo.

### O que estava errado do meu lado

O filtro `hp <= max_hp` **não filtra nada** quando o `max_hp` é gigante: a
relação vira trivialmente verdadeira. Os filtros bons já existiam no
`7-DESCOBRIR-MEMORIA` (`1 <= hp <= 5.000.000`, `1 <= nível <= 200`) e eu os
reimplementei pela metade em vez de reusar — exatamente o que a diretiva de
promoção proíbe. Agora moram em `core/entidades.py` e os dois consumidores usam
os mesmos.

### O que a medição MOSTROU, e isto é novo

**1. Existem valores em `ADDR_TARGET_ID` que não são id de entidade nenhuma.**
`254031539` não aparece em lugar nenhum da memória do processo. Um id que não
existe em lugar nenhum não é um id. E `232865654` aparece 3358 vezes sem uma
struct sequer — é padrão de bytes comum, não identificador.

**2. Eles aparecem LOGO DEPOIS DA MORTE do mob.** Em todas as ocorrências com
hora anterior conhecida:

| morte | id ruim | atraso |
|---|---|---|
| 09:06:14 | 09:06:15 `#230967247` | 1 s |
| 09:06:54 | 09:06:56 `#233061191` | 2 s |
| 09:07:16 | 09:07:25 `#232865654` | 9 s |

A leitura boa volta poucos segundos depois, sozinha.

**3. EXISTE UM TERCEIRO ESTADO, e ele estava escondido.** Em 09:06:04:

```
ALVO #245506802  100.0%  [##########]  (100/100, nv61)
```

Entidade **achada** (tem HP e nível), **nome ilegível**. Isso saía com a mesma
cara de "entidade não achada", porque `linha_do_log` cai no `nome or #id`. São
defeitos diferentes e pedem consertos opostos. O vigia agora marca
`(entidade OK, NOME ilegível)`.

**4. Quando resolve, resolve perfeitamente.** `Rose Snake 100/100 nv61`, luta
inteira, HP descendo linha a linha até `<<< MORREU`. Seis lutas seguidas sem uma
falha. O caminho de leitura está certo.

### A leitura que sobra

Não é "a array é outra coisa". É que **depois da morte o cliente despacha a
entidade e `ADDR_TARGET_ID` fica segurando um valor que não corresponde mais a
nada** — cadáver liberado, id órfão, ou o campo sendo reusado para outra coisa
nesse intervalo.

**Ainda é leitura, não medição.** O que dá para afirmar é o que está nos quatro
pontos acima.

### Quanto tempo dura -- e aqui eu tinha errado

A primeira redação deste item dizia "poucos segundos". O próprio log do usuário
diz outra coisa:

| id órfão | apareceu | resolveu | durou |
|---|---|---|---|
| `#55779919` | 09:05:45 | 09:05:47 | 2 s |
| `#254031539` | 09:05:47 | 09:05:55 | **8 s** |
| `#230967247` | 09:06:15 | 09:06:26 | **11 s** |
| `#233061191` | 09:06:56 | 09:07:04 | **8 s** |

**Oito a onze segundos**, e não "poucos". Isso muda a conclusão.

### O que isso custa ao bot

O bot **não trava** — as travas de 26/08 seguram:

* a **reserva pela flag de combate** (`USAR_COMBATE_COMO_RESERVA_DE_MORTE`) —
  `True → False` com o alvo selecionado declara a morte sem precisar do HP;
* o **escape de "não sei" persistente** (2 voltas) — libera o TAB quando o alvo
  fica ilegível volta após volta.

O defeito de 25/08 (28 minutos batendo em cadáver) não pode voltar por este
caminho.

**Mas ele PAGA.** Durante esses 8 a 11 s o ciclo é: TAB → `_alvo_aceitavel`
recebe `None` → recusa → desiste (`TENTATIVAS_DE_TAB = 1`) → espera
`SEGUNDOS_PARA_A_RODA_REINICIAR` → volta seguinte tenta de novo. São **duas a
três voltas gastas por morte**, sem bater em nada.

E isso conversa direto com o relato do usuário sobre atraso entre matar e voltar
a bater. A parte da confirmação do TAB (a cadência de 100 ms) já foi consertada;
esta aqui é outra fatia, e maior.

### A pergunta que sobra, e como respondê-la

**O id órfão é do mob MORTO ou do mob NOVO?**

* se for do **morto**, o TAB acertou o cadáver e o certo é dar TAB de novo em
  vez de esperar a roda reiniciar;
* se for do **novo**, a entidade dele ainda não entrou no array, e o certo é
  **esperar** — recusar joga fora um alvo bom.

**São consertos opostos, e por isso nenhum foi feito.** O que responde é uma
linha de log: quando o id órfão finalmente resolver, ele resolve **para o mesmo
id** (era o novo, chegou atrasado) ou **para um id diferente** (era o morto, e o
bot trocou)? No log de 26/08 os dois casos aparecem como `alvo novo`, que é
justamente a informação que falta.

### O que NÃO fazer

Continua valendo o do item 39: **não alargar `LIMITE_DE_ENTIDADES` no chute.** A
medição mostrou que varrer mais só produziria mais lixo como o `0x1095C228`.


---

## 41. A hipótese do item 39 está CONFIRMADA — e o item 40 me refutou cedo demais (26/08/2026)

**Eu errei duas vezes seguidas nesta área, e as duas do mesmo jeito: concluindo
antes de o instrumento estar bom.**

* No item 39 afirmei a hipótese com aritmética, sem medição.
* No item 40 a **refutei** com uma medição feita por um filtro quebrado.

A segunda é a pior das duas: uma refutação errada fecha a investigação. Só não
fechou porque o próprio log trazia o lixo (`hp=1/390876288`) na cara.

### A medição, com o filtro consertado

```
investigando o id 250872911 (0x0EF4044F)...
  0x36709F28  Rose Snake  nv61  hp=100/100  — NÃO está na janela varrida

investigando o id 248663124 (0x0ED24C54)...
  0x36705B08  Rose Snake  nv61  hp=100/100  — NÃO está na janela varrida

investigando o id 267525630 (0x0FF21DFE)...
  0x367027F0  Rose Snake  nv61  hp=100/100  — NÃO está na janela varrida
```

**Três mobs VIVOS, inteiros, com nome e nível — e nenhum deles alcançável pela
janela que o bot varre.** A hipótese do item 39 está confirmada:
`ADDR_ENTITY_SCAN_BASE` + `LIMITE_DE_ENTIDADES` **não cobre as entidades do
mundo**. Ela cobre um subconjunto — e os sete "slots de seleção visual" morando
lá dentro continuam sendo a explicação mais econômica de qual subconjunto é.

As três entidades vivem em `0x3670xxxx`, um pool a mais de 800 MB da janela
estática. A janela guarda **ponteiros**; as structs estão longe.

### E o id órfão NÃO é o mob novo chegando atrasado

A pergunta em aberto do item 40 tinha duas respostas opostas. O `[id X ← era Y]`
respondeu, e em **todas** as sete transições do log:

```
era 268509212 -> 263391642   DIFERENTE
era 263391642 -> 250872911   DIFERENTE
era 250872911 -> 250760263   DIFERENTE
...
```

**Nunca o mesmo id.** Ou seja: não é a entidade do alvo chegando atrasada ao
array — é o bot **trocando de alvo** enquanto os ids não resolvem. Ele TABa,
não consegue ler, desiste, TABa de novo. O `#250872911` era um Rose Snake vivo
e inteiro, e foi recusado por não estar na janela.

### O que isto quer dizer para o bot

**A leitura do alvo pela memória é boa quando funciona e não dá para depender
dela para SABER QUE HÁ ALVO.** Ela responde por um subconjunto dos mobs — o
subconjunto que passou pela seleção —, e o TAB alcança muitos que estão fora.

Recusar alvo porque "a entidade não apareceu" está jogando fora **mob vivo,
100/100, ao alcance**. É o oposto do que a régua do inalcançável existe para
fazer.

### O que NÃO fazer (agora com medição atrás)

Alargar `LIMITE_DE_ENTIDADES` continua errado, e agora dá para dizer por quê:
as entidades estão em `0x3670xxxx` e a janela é estática em `0x0107Cxxx`. Não é
questão de varrer mais slots — **é outra região**. Achar o array de verdade é
uma investigação de memória própria, não um número maior.


## MEDIDO: o atraso da flag de combate depois de o alvo cair (07/09/2026)

4977 saídas de batalha registradas em produção (duas contas de APP, um dia):

| medida | valor |
|---|---|
| mínimo | 0,00 s |
| mediana | 1,41 s |
| p90 / p95 / p99 | **1,91 / 1,91 / 1,91** |
| máximo | **1,92 s** |
| média / desvio | 1,27 / 0,57 |
| estouros do teto de 2,0 s | **517** (9,4% de 5494 eventos) |

**`p90 = p95 = p99` com máximo 1,92 não é uma distribuição — é uma parede.** O
teto de 2,0 s estava CENSURANDO a cauda: todo atraso real acima dele saía do
lado dos "estouros". Parte dos 517 "tem outro mob batendo" era só a flag
demorando um pouco mais.

O council resumiu em uma frase: *"sem a cauda, qualquer teto é chute"*.

### O que mudou

- **Teto: 2,0 → 2,5 s** (número aceito pelo usuário). Custo conhecido: meio
  segundo a mais nos casos em que realmente há outro mob — 517 × 0,5 s ≈ 4 min
  numa sessão de horas.
- **O estouro passou a ser MEDIDO, não presumido.** Concluir "tem outro mob
  batendo" só porque a flag não baixou era o furo da regra: flag travada,
  leitura inválida e desync do cliente caem na mesma classe de "não baixou", e
  nenhuma delas se resolve voltando a atacar. Agora o estouro pergunta à tabela
  de entidades (`core/vizinhanca.py`) e o log diz qual dos dois casos é.

### O que o próximo log tem de responder

Se os estouros continuarem em ~9% **com mob por perto**, 2,5 s basta e o
diagnóstico está certo. Se aparecerem estouros **sem mob nenhum por perto**, o
problema não é o teto — é a flag ou a leitura, e aí a decisão muda de lugar.

---

## O ALVO FANTASMA — por que às vezes o HH não vê a morte e não dá TAB (10/09/2026)

Relato do usuário: *"em HH, parece que em algumas vezes não identifica que o
target morreu e não dá TAB, mas é só às vezes"*. Achado nos logs, com número.

### A base de medição

105.207 linhas da conta de HH em ~23 h de farm, e 12.909 leituras de alvo com
os campos completos em todos os logs disponíveis.

### O caminho saudável é sólido — não é aí que está o problema

| medida | resultado |
|---|---|
| `ALVO MORREU` | 2474 |
| `Alvo caiu em <pacote>: TAB N de M` | 2460 |
| morte **com** TAB em seguida | **2468 de 2474** |
| atraso morte → TAB | mediana **0,157 s**, p90 0,194 s |
| acima de 2 s | 8 (0,3%) |

As 6 mortes sem TAB não são defeito: quatro são o mesmo episódio de fantasma
(abaixo) e duas são luta de **destravamento**, onde `0 TAB` é o desenho —
o log registra `DESTRAVADO … 1 morte(s), 0 TAB` e o bot seguiu certo.

**Então a detecção de morte por memória está certa.** O que falha é *o que ele
está olhando quando falha*.

### O defeito: o alvo resolvido NÃO É UM MOB

A assinatura, crua do log:

```
ALVO #461589701  0.0% [----------] (1/1177280513, nv1)  alvo novo
ALVO #461589701  0.0% [----------] (1/1177280513, nv1)  +0%      (x5, por 9 s)
```

`max_hp = 1.177.280.513`, nível 1, sem nome. E os `max_hp` absurdos são
**padrões de bits de float** lidos como inteiro:

| valor lido | em hexa | como float |
|---|---|---|
| 1065353216 | `0x3F800000` | **1.0** |
| 1177280513 | `0x462BE001` | 11000.001 |
| 1153705192 | `0x44C424E8` | 1569.15 |
| 1230735792 | `0x495B89B0` | 899227.0 |

Um objeto que guarda float onde um mob guarda int **não é um mob**. O JOIN
`entidade+0x8 == TARGET_ID` casou com outra estrutura.

**HIPÓTESE QUE EU LEVANTEI E QUE CAIU:** *"o `TARGET_ID` está guardando um
float"*. O id fantasma `1108344853` decodifica como float `36.0`, o que parecia
confirmar — mas um id **real** (`1091567835`) decodifica como `9.0`. A
decodificação não discrimina, e a hipótese não se sustenta. O que está medido é
o **objeto resolvido**, não a origem do id.

### O custo medido

| medida | resultado |
|---|---|
| leituras fantasma | **44** de 6144 (0,7%) |
| episódios | **25** |
| tempo total travado | **250,5 s** em ~23 h (0,3%) |
| pior episódio | **37,4 s** |
| fase | **`boss` em 100%** dos casos |
| perto de um `O TAB nao trocou` | 71% |

`O TAB nao trocou o alvo em 350 ms` aparece **300 vezes**, em rajadas de até 4.
Com um fantasma travado, o HP lido não muda (`+0%`) e o TAB não tem para onde
ir — que é exatamente *"não identifica que morreu e não dá TAB"* visto de fora.

### A causa: o filtro certo existe e NÃO está no caminho vivo

`Memory.alvo_atual()` valida assim:

```python
if hp is None or maximo is None or maximo <= 0 or hp < 0 or hp > maximo:
    return None
```

É `hp <= max_hp` — **e o próprio projeto já provou que isso não serve.** O
docstring de `core/entidades.py` diz, de uma medição de 26/08/2026:

> `hp <= max_hp` sozinho aprova qualquer coisa, porque `max_hp` gigante torna a
> relação trivialmente verdadeira

Com `max_hp = 1177280513` e `hp = 1`, a relação é trivialmente verdadeira e o
lixo passa. E `TargetHybrid.veredito` confia nisso: *"a struct já foi validada
por quem leu"*.

O filtro que funciona — `hp_plausivel`, com `HP_MAXIMO_PLAUSIVEL = 5_000_000` —
existe em `core/entidades.py` desde 26/08/2026, escrito **para este mesmo
lixo**, e está ligado em **um lugar só**: `investigar_alvo_perdido`, que é
ferramenta de diagnóstico. O caminho que o combate usa não o alcança.

É o caso da diretiva de promoção outra vez: *quando uma pergunta aparece pela
segunda vez, o custo não é escrever de novo — é reaprender com o jogo na frente
o que a primeira versão já sabia.*

### O que a correção resolveria, medido contra o log

| | resultado |
|---|---|
| leituras REAIS reprovadas por engano | **0 de 5600** |
| fantasmas pegos pelo teto de HP | **31 de 44 (70%)** |
| fantasmas que ainda escapariam | **13** — todos `max_hp = 1` ou `2` |

Custo zero em falso positivo, 70% do defeito. **Não foi aplicado ainda** — o HH
está rodando e mexer no combate é assunto de sessão própria, com o usuário
olhando.

### O resíduo, e o número que FALTA medir

Os 13 que escapam têm `max_hp = 1`, e `hp_plausivel(1)` aprova porque 1 está na
faixa. Medição que sustentaria um piso:

> em **12.909** leituras de alvo, `max_hp` foi **exatamente 100** em 12.823
> (99,3%), e **todo** valor diferente de 100 era fantasma. `max_hp <= 10`
> apareceu 23 vezes, **todas** fantasma. Nenhuma leitura real abaixo de 100.

**Mas isso é só HH:** as contas de BC e APP registram alvo em outro formato e
não entram nesta conta. Antes de virar piso, precisa da medição do outro lado —
senão é número inventado, e a regra do projeto é que número novo precisa de
medição.

### Detalhe menor, mas que engana quem lê o log

`#id` no lugar do nome tem **dois** significados, e misturar os dois infla o
problema por 4×:

| caso | quantas | é defeito? |
|---|---|---|
| `#id` com `hp/nível` plausíveis | 163 | **não** — mob real, nome não lido, e o `core/entidades.py` diz de propósito que nome não entra como filtro |
| `#id` com `hp/nível` absurdos | 44 | **sim** — é o fantasma |

### A CORREÇÃO APLICADA — mob válido tem vida máxima 100 (11/09/2026)

Regra do usuário: *"mob e boss de verdade sempre vai ter a vida máxima 100, pelo
menos com base em todas as leituras que fiz até o momento… então mob válido é
para ser identificado dessa forma"*.

**Conferida antes de virar regra**, contra 45.162 leituras de alvo nos logs:

| conta | leituras | `== 100` | exceções |
|---|---|---|---|
| APP | 15.545 | **100,00%** | **nenhuma** |
| BC | 16.208 | 99,98% | 3, todas padrão de float |
| HH | 13.409 | 98,96% | `1` (46×) e padrões de float |

E o corte é limpo **por nome**, que é o que fecha: dos **99 nomes distintos** já
vistos como alvo, todo nome real lê 100 e só 100 — `Elite Fatal Centipede` em
1439 leituras, `Green Robe Master` em 293, `Zaton` em 272, e o boss `Gun Witch`
(nv50) em 7. **Todo** valor diferente de 100 veio de entrada sem nome (`#id`).
A única exceção nomeada foi `JBU`, com cara de nick de jogador — e recusar
jogador é o comportamento certo para quem caça mob.

**Por que `== 100` e não um teto:** o teto de 5 milhões do `core/entidades.py`
pegaria 31 dos 44 fantasmas. Os 13 que escapavam têm `max_hp` de 1, 2 ou 3 — o
lixo *pequeno*, que nenhum teto alto alcança. A igualdade pega os 44.

**Validado contra os clientes vivos**, 180 s com o farm rodando: **13.031 alvos
aceitos, ZERO falso positivo**, incluindo os mobs de HH (`Elite Axe Monk
Soldier`, `Roaming Apothecary`, `Buddhist Monk Purple Moon`) e jogadores, que
também leem 100.

**O log que o usuário pediu:** cada recusa sai uma vez por combinação
`(id, vida máxima)`, com id, nome, hp e nível — o suficiente para julgar se a
regra errou. Uma vez por combinação é requisito, não economia: o fantasma
medido repetia a mesma leitura a cada 2 s por até 37 s.

### CORREÇÃO A UMA AFIRMAÇÃO MINHA: o bot NÃO trava para sempre

Eu tinha deixado no ar que o fantasma prendia o bot. **Não prende.** O log
mostra a recuperação: o fantasma entra às 05:34:56, e às 05:34:57 a **flag de
combate baixa** e o bot conclui certo (*"a memória confirmou a morte de Green
Robe Master"*). A flag é a segunda fonte, e ela funciona.

O custo real do fantasma é **TAB desperdiçado e segundos** — no episódio acima,
`TAB 12 de 2` e 26 s de luta —, não travamento permanente. Isso não diminui o
valor do conserto, mas muda o tamanho do problema, e o número honesto continua
sendo os **250,5 s em ~23 h**.

**E o patch é seguro pelo mesmo motivo:** com `None` no lugar do fantasma, o
`veredito` devolve `None`, que cai no ramo `morreu=False` — o laço segue e sai
pela flag. Não há spam de TAB.
