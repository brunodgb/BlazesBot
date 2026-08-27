# O ALVO: RESOLVIDO — este arquivo é HISTÓRICO

> # ⛔ NÃO COMECE POR AQUI
>
> **A investigação do alvo TERMINOU em 25/08/2026.** As duas perguntas abertas
> que este arquivo passava adiante foram respondidas, e o desenho que ele
> descreve — morte por barra da tela mais `EnemyDead.png` — **não é mais o
> caminho principal**.
>
> **Hoje o alvo vem da MEMÓRIA, inteiro:** `0x0115CB80` é o ID da entidade
> selecionada, e a entidade guarda esse id em `+0x8`. Nome, HP exato, nível e
> posição saem de uma leitura, sem captura de tela.
>
> **Leia `docs/decisoes/memoria-primeiro.md`.** É lá que estão o achado, a
> confirmação numa luta inteira, o porquê de a memória ganhar da imagem e o
> inventário do que ainda decide por imagem.
>
> Este arquivo fica como REGISTRO de como se chegou lá: as tentativas que
> reprovaram, as armadilhas de método que custaram tempo, e as medições cruas.
> Tudo abaixo descreve **código que já não existe**.

## O DESENHO DE HOJE, em uma tela

```
0x0115CB80 == 0            ->  sem alvo. Não decide nada.
0x0115CB80 mudou de valor  ->  alvo novo.
vida > 10%                 ->  vivo. NÃO procura marcador nenhum.
vida <= 10%                ->  a MESMA captura serve o EnemyDead.png:
       marcador bateu      ->  MORREU. Libera o TAB.
       marcador não bateu  ->  sobrou vida. Continua rotacionando skill.
não deu para ler           ->  "não sei". Não gasta TAB.
```

No **boss** isso é **só log** — quem encerra a luta continua sendo a saída de
combate.

## AS TRÊS PEÇAS

| peça | onde | o que faz |
|---|---|---|
| identidade | `0x0115CB80` | `0` = sem alvo; valor diferente = alvo diferente. **Não se sabe o que o número significa** |
| vida | `vision.ler_barra_do_alvo` | offset FIXO x 466→600, y 46→48 da área de cliente; conta COLUNA |
| morte | `EnemyDead.png` | só consultado abaixo de 10%, no MESMO quadro da barra |

## O QUE FOI MEDIDO PARA ISSO (25/08)

* **A barra não escala com a resolução.** O usuário mediu em 1024×768 e repetiu
  em 1680×1050 sem mudar coordenada: continuou acompanhando o dano. Vermelho
  cheio `(188-190, 0, 2-3)`, vazio `(55, 9, 45)`, 134 colunas.
* **A busca proporcional antiga quebrava fora de 1024.** `largura * 0.30` a 1680
  começa em x=504 e a barra começa em 466 — sobravam 96 das 134 colunas, abaixo
  do mínimo, e a leitura devolvia `None` para sempre.
* **O piso de 0,7% era da régua, não do mob.** A conta antiga dividia pixels
  vermelhos pela ÁREA do retângulo e as bordas diluíam. Contando COLUNA, morto lê
  **zero cravado** — e é isso que um dia permite descer o limiar de 2% para 1%.
* **O amarelo do `boss_2_fase.png` lê BGR (0, 204, 231)** na faixa medida: a
  detecção da fase 2 pela cor foi confirmada contra o modelo real em disco.
* **As duas barras do boss são sobrepostas** (palavras do usuário): a amarela é a
  metade de cima e vai revelando a vermelha. Total = `50 + 50×amarela`, depois
  `50×vermelha`. É o que explica a razão barra/memória de exatamente **2,0**
  medida em 21/08 (item 35) — a memória contava o total, a tela desenhava uma.
* **O log do bot estava mudo por um método morto.** O único lugar que logava HP%
  era `TargetHybrid.ler_alvo()` — `async`, e **ninguém chamava**. Nas 14 lutas de
  24-25/08: 0 linhas de vida, 14/14 com `alvo visto=False`, 14/14 com nome
  `ilegivel`, 28 estouros de `'Memory' object has no attribute
  'candidato_de_alvo'`.

## O QUE SAIU DO CÓDIGO (e por quê não é "interruptor")

`VigiaDoAlvo` e o consenso inteiro, 36 constantes órfãs, os seis embrulhos
`_target_*`, `_get_target_info*`, `_screen_target_hp_pct`, os caminhos antigos
(`fight_boss`, `lutar_contra_guardas`, `_mirar_*`, `_confirmar_covil_vazio`), a
máquina `async` do `target_hybrid`, e as 12 provas de calibração do ponteiro.

**A regra do projeto protege alternativa que FUNCIONA.** Essas dependiam de
`Memory.target_object/target_hp/target_name/candidato_de_alvo`, que já tinham
sido removidos — ligar o interruptor levaria a `AttributeError`, não a outro
comportamento. Caminho que não pode ser ligado não é interruptor, é entulho.

**O que FICOU atrás de interruptor:** `USAR_PORTAO_DE_NOME = False` (o portão de
nome dos guardas, inteiro, esperando uma fonte de nome) e
`USAR_OFFSET_FIXO_DA_BARRA = True` (a busca pela âncora azul continua como
reserva).

## AS PERGUNTAS ABERTAS

1. **O que o `0x0115CB80` significa?** Índice? handle? id de servidor? O
   `INVESTIGAR_O_TARGET_ID = True` grava cada troca em
   `logs/target_id/<conta>.txt` com valor cru, delta, tempo desde a última troca
   e a vida naquele instante. **Se o valor levar ao nome do alvo, o portão dos
   guardas religa e o bot volta a saber em quem está batendo.**
2. **O `EnemyDead.png` ainda dá falso positivo?** O escore vai para o log em toda
   consulta. O usuário disse que troca a imagem se continuar falhando.
3. **Dá para descer `LIMIAR_VIDA_TELA` de 0.02 para 0.01?** O log grava o valor
   bruto abaixo de 10% justamente para responder isso com número.
4. **A troca de fase do boss pelo ID bate com a barra amarela?** Os dois sinais
   estão ligados e logam separado; três ou quatro lutas de boss respondem.

## A REDE DE SEGURANÇA

```
.venv\Scripts\python.exe -m pytest -q          720 passam
.venv\Scripts\python.exe -m ruff check blazesbot/ tests/ main.py
```

`tests/test_alvo_pela_tela.py` trava o desenho novo inteiro (29 testes): a régua
em três resoluções, o zero cravado, o `None` quando não dá para ler, as duas
barras do boss, o marcador só abaixo de 10%, uma captura por leitura, a morte que
não sai duas vezes, o log linha a linha, e o `snapshot()` sem tela.

---

# HISTÓRICO — a passagem de bastão de 21/08/2026

O que está daqui para baixo descreve o desenho ANTERIOR. As MEDIÇÕES continuam
valendo (são elas que sustentam as decisões acima); o código descrito não existe
mais.

## 1. O ESTADO EM UMA FRASE

**O HP da memória está certo (0,11pp contra a barra); o que falta é a
IDENTIDADE — saber DE QUEM é aquele HP — e a régua que julga isso (a barra da
tela) está torta em dois modos diferentes.**

Nenhum ponteiro decide nada em produção hoje. Isso é ordem do usuário e não é
para ser revertido sem ele:

> *"os ponteiros não devem afetar a decisão da troca de target e afins, por hora
> é apenas para gerar log e entendermos sem atrapalhar a execução do bot."*

> *"por agora a ideia é o ponteiro de memória não votar, apenas testarmos e
> conseguirmos bastante log e coisas que possam corroborar e garantir que vai
> estar 100% antes de ativarmos."*

Critério de aceitação dado por ele: **acima de 99% de acerto**, na coluna
DISCRIMINANTE.

---

## 2. OS NÚMEROS QUE VALEM (medidos, com o arquivo ao lado)

| o que | número | onde |
|---|---|---|
| HP da memória contra a barra, quando se sabe qual entidade | **0,11pp** | `'Blaze Skull Marshal' 73/100` × barra 72,9% |
| a entidade certa acompanhando a barra | **87,5%** (35/40) | `27220-20260821-072606.jsonl` |
| `jogador+0x808` acertando o alvo | **1,0%** (97 respostas) | `analisar_correlacao.py` |
| melhor slot estático (`0xc7c714`) | **30,1%** | idem |
| razão barra/memória no boss | **1,0 ou exatamente 2,0** (54 × 43 ciclos) | itens 35 |
| TETO no BC (alguém na mesa bate) | **92,5%** e **68,9%** | dois runs de BC |
| TETO no APP | **4,3%** | `29500-20260821-071943.jsonl` |
| entidades por ciclo (censo consertado) | **57 a 137** (antes: 7) | as 4 coletas |
| cegueira no instante da morte (antes do conserto) | **39% das leituras**, 63 de 77 lutas, mediana 6,7 s | `blazes-dev-2026-08-20.jsonl` |

Detalhe de cada linha nos **itens 26 a 38** de `alvo-o-que-esta-medido.md`.

---

## 3. O QUE MUDOU NESTA SESSÃO (inventário completo)

### Produção — `blazesbot/bot/bc/combat.py`

Quatro defeitos medidos, cada um com interruptor e dente:

| interruptor | valor | o que consertou |
|---|---|---|
| `CURTO_CIRCUITO_SO_PARA_QUEM_VOTA` | `True` | a tela era calada quando a memória lia `hp<=0` — e a memória não vota. 39% das leituras sem NENHUMA testemunha, sempre no instante da morte |
| `AUSENCIA_DE_FONTE_NAO_ZERA_O_CONTADOR` | `True` | leitura muda apagava a confirmação de morte já acumulada |
| `MARCADOR_AUSENTE_NAO_E_TESTEMUNHA_DE_VIDA` | `True` | "não achei o sprite" contava como "vi o mob vivo" — 46% dos vereditos `vivo` |
| `CARENCIA_ACABA_QUANDO_A_SELECAO_TROCA` | `True` | **NÃO IMPLEMENTADO** — ninguém lê este interruptor. Ver §5 |

Mais:

* `VigiaDoAlvo.observar` **parou de zerar** `ponteiro_anterior`/`trocas_de_ponteiro`
  (eram duas linhas coladas do `__init__`, e é por isso que `trocas_ptr` era 0 nas
  1.431 linhas de log). `observar` agora recebe `ponteiro=` e `memoria_vota=`;
  `instrumentar()` virou formatador (`texto_do_ponteiro()`).
* `_memoria_pode_votar()` — a CREDENCIAL. `MEMORIA_VOTA_NA_MORTE` é tri-estado
  (`False` | `True` | `QUANDO_GABARITAR`) e está em **`False`**. Resolvida uma vez
  por luta; qualquer falha responde `False`.
* Prova nova `morte_por_hp_arriscada` (`PROVA_DA_CREDENCIAL_DA_MEMORIA`), amostrada
  **só quando a memória diz MORTO** — a taxa de erro dela É a taxa de falso
  positivo do sinal. Mais a linha `PONTEIRO DISCORDOU DA TELA` no log.

### Produção — `blazesbot/core/memory.py`

* **`USAR_SELECAO_ESTATICA = False`.** Ligado, `target_object()` devolvia
  `candidatos_validos[0]` — um vizinho arbitrário — e daí sai o `target_name()`
  que alimenta o **portão de nome dos guardas** (que manda o bot parar de bater e
  de dar TAB). Os 12 "slots de seleção" são entradas do array de entidades, passo
  4: cada um guarda UMA entidade fixa (itens 26-28).

### Produção — `blazesbot/core/calibracao.py`

* `situacao(prova, candidato)` e `gabaritou(prova, candidato)` — acessores de
  leitura, para o CÓDIGO poder perguntar ao placar.

### Ferramentas

* **`teste_correlacao_alvo.py`** (`16-TESTAR-CORRELACAO-ALVO.bat`) — reescrita.
  Censo pela tabela estática com **passo 4** (era `0x1108`, o passo das structs no
  heap, e o censo nem era chamado). 2 s de cadência, 10 minutos, fecha sozinha,
  grava `logs/correlacao/<pid>-<data>.jsonl` + `.txt`. Registra por ciclo: barra,
  **geometria da régua**, censo inteiro com delta, os 12 slots, `0x808`, `0x80C`,
  quem sofreu dano, quem morreu (hp→0), quem sumiu da tabela, ambiguidade.
* **`analisar_correlacao.py`** (novo) — julga os JSONL já gravados, com a régua
  corrigida (só ciclo discriminante; aceita fator 1 ou 2). Roda com o bot de pé.
* O `.bat` foi reescrito **com `goto` em vez de `if (...)`** — ver §6, armadilha 4.

### Testes

* `tests/test_cegueira_no_instante_da_morte.py` — 16 testes, com dente para cada
  um dos quatro consertos e para a credencial.
* `tests/test_alvo_sem_o_pet.py` — +4 testes da tabela estática, incluindo o dente
  que preserva o defeito atrás do interruptor.

### Documentação

`CLAUDE.md` (regras novas na seção Combate), `alvo-o-que-esta-medido.md` (itens
26-38, e os itens 23/25 movidos para REFUTADO), `docs/INTERRUPTORES.md`
regenerado, grafo atualizado.

**Rede de segurança no fim desta sessão: 859 testes passam, 1 skip, ruff limpo.**

---

## 4. AS DUAS PERGUNTAS ABERTAS, COM O EXPERIMENTO DE CADA UMA

### A. POR QUE A RÉGUA DO APP MEDE OUTRA COISA? *(faça esta primeiro)*

Sintoma medido: na conta APP a barra produziu **14 valores distintos** em quatro
blocos, piso em **14,2**, vãos em `17,2→35,4`, `37,9→54,7`, `57,2→99,8` — e em
**96% dos ciclos discriminantes nenhuma** das ~69 entidades tinha aquele HP. Na
conta BC, 38 e 78 valores **contínuos desde 0,0**.

Barra de vida de verdade é contínua. Essa salta em bloco.

`vision.vida_do_alvo` procura a corrida AZUL (barra de mana) dentro de
`FAIXA_DO_QUADRO_DE_ALVO = (0.30, 0.70, 0, 140)` — o `y` é **absoluto em pixels**
— e mede o vermelho num retângulo `LINHAS_ENTRE_HP_E_MP` acima. Achou outra
corrida azul, mediu outro retângulo, e devolve float sem dizer nada.

**O experimento já está armado:** a coleta agora grava `geometria` por ciclo
(tamanho do quadro, `y`/`x`/largura da corrida azul achada, linhas da vida,
`vermelho/area`, `linhas_com_vermelho`, `largura_do_vermelho`). Rode 10 minutos
nas duas contas e rode o analisador: ele imprime a geometria agrupada e avisa
`A GEOMETRIA MUDOU` sozinho.

Hipótese principal a confirmar ou derrubar: **as janelas têm tamanhos diferentes**,
então o `y` absoluto cai em outro lugar da UI. Se for isso, o conserto é o mesmo
padrão que o projeto já usa para tudo — `coords._from_base` com âncora — e a
função precisa aprender a dizer *"não achei o quadro do alvo"* em vez de devolver
número. Segunda hipótese: no APP não há alvo, e a corrida azul achada é de outro
elemento.

**Não conserte `vision.py` no escuro.** Um print da faixa recortada quando
`linhas_com_vermelho` for 1 ou 2 responde em um minuto.

### B. QUEM É O ALVO? (a identidade)

O que está medido: o HP está certo, o ponteiro não identifica. `0x808` = 1,0%,
melhor slot 30,1%, entidade certa 87,5%.

O caminho que os dados apontam: **a identidade não vem de ponteiro fixo, vem da
SÉRIE** — a entidade cujo HP acompanha a barra ao longo de N ciclos, aceitando
fator 1 ou 2. Já dá 87,5% a 2 s de cadência, e a produção lê a cada
`CADENCIA_DA_LEITURA_DO_ALVO = 0.15`.

Só ataque isto **depois** da pergunta A: enquanto o teto for 4,3% em uma conta,
nenhum método pode passar dele, e você vai medir a régua achando que mede o
ponteiro.

Pistas já registradas para quando chegar aqui:

* o **TAB** é o gabarito mais forte de identidade e não custa tela
  (`calibracao.julgar_troca`), mas **em 129 dos 190 TABs do log de 20/08 a seleção
  não mudou** — explicar isso é parte da pergunta;
* o **nome não serve como identidade**: o mesmo endereço leu
  `'Guard of Screw Bay'`, `'2ed Villager'`, `'You got 196 Experience'`, `'0.bmp'`,
  `'ctor\eff_10plus.eva'` (item 38);
* a **escala** serve como peneira: 100 inimigo, 243 pet, 729 jogador — e
  apareceram duas novas, `48` e `10`, ainda sem explicação.

---

## 5. O QUE ESTÁ PENDENTE, EM ORDEM

1. **Pergunta A** (a régua). Critério de saída: TETO ≥ 90% nas DUAS contas.
2. **Pergunta B** (a identidade). Critério de saída: um método com acerto
   discriminante > 99% em ≥ 10 runs distintas.
3. **Só então** ligar `MEMORIA_VOTA_NA_MORTE` — e a decisão é do usuário lendo o
   `15-PLACAR-CALIBRACAO.bat`, não automática.
4. **`alvo_hp|0x808` está congelado em `reprovado`** com 100 amostras de UMA run de
   70 s (14:44–14:46 de 20/08), colhidas ANTES de o pet sair do `target_object`.
   `reprovado` não volta a ser amostrado. Reabrir com
   `python -m blazesbot.core.calibracao --reabrir alvo_hp` — **e o bot tem de
   estar PARADO**, senão a cópia velha dele volta no flush seguinte (já falhou
   duas vezes por isso).
5. **`CARENCIA_ACABA_QUANDO_A_SELECAO_TROCA` está declarado e não implementado.**
   Falta o laço de `atacar_ate_sair_de_combate` guardar o ponteiro de antes do TAB
   e encurtar `proxima_leitura` quando ele mudar. **Não implemente antes de
   explicar os 129/190 TABs sem troca de seleção.**
6. **12 erros de ruff em `blazesbot/tools/find_target.py`** (imports fora de ordem
   e 3 não usados). Não são desta sessão e não foram tocados.
7. **Pendência antiga que continua valendo:** rodar `14-RECORTAR-TIME.bat` — sem o
   `state_team_member.png` o bot não sabe se está em time por caminho nenhum.

---

## 6. ARMADILHAS (cada uma já custou tempo)

1. **Não deixe ponteiro decidir.** É ordem do usuário. Se for mexer em
   `target_object`, `target_name`, `target_hp` ou no consenso, confira antes o que
   passa a decidir com aquilo.
2. **Ainda LÊEM ponteiro e DECIDEM** (não neutralizados de propósito, porque são
   antigos e desligá-los mudaria o farm): o **portão de nome dos guardas** e a
   **virada de fase do boss**. Estão no radar do usuário; ele decide.
3. **Citar valor de constante no `CLAUDE.md` na forma `NOME = valor` reprova a
   suíte** se não bater com o código (`tests/test_indice_de_constantes.py`).
   História em prosa, valor de hoje com crases. E rode
   `python -m blazesbot.core.indice_de_constantes` depois de mexer em interruptor.
4. **`.bat`: nada de `(` `)` `<` `>` dentro de texto.** Parêntese dentro de bloco
   `if (...)` fecha o bloco no meio e a janela morre sem mensagem — foi o
   "fecha sozinho ao digitar o PID". `<` e `>` viram redirecionamento
   ("Acesso negado"). O `16` usa `goto` justamente para não ter bloco.
5. **`CARENCIA_APOS_O_TAB = 2.4` é travado por teste** e mexer para baixo reabre o
   defeito de 13/08 (3 TABs no cadáver).
6. **Nenhum teste escreve em `data/`** (`tests/conftest.py`, autouse) — o
   `calibracao.json` decide promoção com evidência real.
7. **Ferramenta que julga por régua diferente da produção descreve um bot que não
   existe.** Foi o que fez o `10-DESCOBRIR-ALVO` chamar todo cadáver de "seleção
   pendurada". Por isso o `16` importa as constantes de `vision` em vez de ter as
   próprias.
8. **O erro de método que já apareceu QUATRO vezes:** ler o rótulo da própria
   ferramenta como se fosse o cliente falando (`"provável ID"`, `"a struct é
   removida"`, `"slots de seleção visual"`). Scan feito com UM alvo selecionado
   acha os endereços que apontam para AQUELE alvo; sem repetir com outro alvo e
   conferir se o MESMO endereço mudou de valor, "aponta para o alvo" e "aponta
   para aquela entidade" são indistinguíveis.

---

## 7. COMANDOS

```bat
REM coletar (uma janela por conta; 10 min e fecha sozinha)
16-TESTAR-CORRELACAO-ALVO.bat

REM julgar o que já foi coletado (pode rodar com o bot de pé)
.venv\Scripts\python.exe analisar_correlacao.py
.venv\Scripts\python.exe analisar_correlacao.py logs/correlacao/29500-*.jsonl

REM placar da calibração de produção
15-PLACAR-CALIBRACAO.bat

REM rede de segurança
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check blazesbot/ tests/ main.py
.venv\Scripts\python.exe -m blazesbot.core.indice_de_constantes
graphify update .
```

Logs que importam: `logs/correlacao/*.jsonl` (coleta nova),
`logs/dev/blazes-dev.jsonl` + `logs/dev/arquivo/` (o log de dev, com as linhas
`ALVO` do combate), `logs/pointer_scan/`, `logs/descobrir_alvo/`.
