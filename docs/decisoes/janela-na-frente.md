# Janela aberta na frente do clique (26–27/08/2026)

> O **porquê medido** desta área. A regra resumida está no `CLAUDE.md`; a
> especificação, em `docs/REGRAS.md` (seção "Janela na frente do clique").
> Leia este arquivo **antes** de mexer no painel de arredores ou no guarda.

---

## O relato, e o print que resolveu

> *"tem vezes que eu percebo que a aba surroundings tem aberto muitas vezes em
> sequência, em vez de abrir 1x, filtrar e ir (…) eu vi o personagem na
> coordenada da entrada da cave BC e com o surroundings aberto, impedindo o
> clique pois estava na frente atrapalhando"*

O print mostrava o estado completo: personagem em **(1395,-635)** — a coordenada
exata da entrada —, **Skull Herald já selecionado**, **time de reset já
formado** com `WizzOfBlazes5`, e o painel Surroundings aberto por cima da cena.
O bot tinha feito tudo certo e não conseguia clicar.

E um segundo relato, que virou o achado mais importante:

> *"teve vezes onde digitava 'Skull' e logo em seguida clicava 0 que é o botão
> da montaria configurado, ficando 'Skull00000000...'"*

---

## Os quatro defeitos, e nenhum deles era o que parecia

### 1. `fechar_surroundings` não distinguia "não vi" de "não está aberto"

```python
pontos = self._pontos("surroundings")
if not pontos:
    return                 # <- "não consigo VER" tratado como "não está aberto"
```

`abrir_surroundings` faz essa distinção com todo cuidado — tem um método só para
isso, `_consigo_enxergar`, com o comentário *"NÃO CONSIGO ENXERGAR é diferente de
NÃO ESTÁ ABERTO"*. **A função irmã não fazia.**

Num quadro ruim — animação, névoa, rumor passando por cima — o template cai
abaixo do limiar por um instante e a função **voltava em silêncio achando que
tinha fechado**. É a explicação direta do print.

**Conserto:** relê até `LEITURAS_ANTES_DE_DESISTIR_DE_VER = 3` antes de aceitar
cegueira, e devolve **tri-estado** (`True` fechei / `False` cliquei e não sumiu /
`None` não sei) em vez de `None` sempre.

### 2. Ela tinha UM ponto de chamada no arquivo inteiro

`ir_para_resultado`, e só no caminho de **sucesso**. Três saídas deixavam o painel
aberto:

- `ir_para_resultado` devolvendo `False` por não localizar o painel;
- `buscar_npc` devolvendo `None` depois das três tentativas;
- `abrir_surroundings` que **clicou no botão** e não viu o painel a tempo — abriu,
  e ninguém fechava.

**Conserto: o painel ganhou um DONO, e o dono é o TRAJETO** (`trajeto_pelo_painel`).
Não é a abertura, e o motivo é concreto: `buscar_npc` termina com o painel
**aberto de propósito**, porque quem chamou ainda vai clicar no `first_result`
para disparar o auto-path. A unidade de trabalho é *buscar o NPC e sair andando
até ele* — quem sabe onde isso começa e termina é o trajeto.

Chamar `fechar_surroundings()` à mão em cada `return` que falta seria só criar um
quarto lugar para esquecer no próximo `return` que alguém escrever. No
gerenciador, o fechamento é consequência de **sair do bloco**, inclusive por
exceção, e a regra fica visível na indentação.

### 3. As tentativas eram ANINHADAS: 3 × 3 = 9 aberturas

`garantir_coordenada_da_entrada` retenta 3×, e cada volta chama
`ir_ate_o_npc_da_cave` → `buscar_npc`, que retenta outras 3×. **Ninguém escolheu
o nove** — ele é o produto de duas camadas que não sabem uma da outra.

E a trava de tempo não resolvia isso: espaçar 9 aberturas a 2 s viraria **18
segundos parado** na porta de uma BC disputada. Trocaria um sintoma visual por um
custo de run.

**Conserto:** `ABERTURAS_POR_TRAJETO = 4`, num contador só
(`_aberturas_do_trajeto`), zerado por quem **inicia** um trajeto. Estourado,
`abrir_surroundings` devolve `None` — e aí **os dois laços de retentativa param
sozinhos**, sem precisar desmontar nenhum deles.

Número **derivado, não medido**: 1 (caso normal) + os 3 modos de falha que o
próprio arquivo já documenta.

### 4. A trava de 2 s existia e media a coisa errada

`INTERVALO_ENTRE_USOS_DO_PAINEL = 2.0` era carimbado **só na abertura**, então o
intervalo media *abrir → abrir*. Um ciclo inteiro passa dos 2 s, então a
reabertura seguinte **não pagava nada**.

**Conserto:** o carimbo sai em **três** pontos e vale o mais recente — ao abrir,
ao clicar no auto-path e ao fechar. Toda interação reinicia a contagem, inclusive
a tentativa que abre e nem chega a clicar. O caminho feliz continua não pagando
nada: entre a Fay, a entrada e o vendedor passam minutos.

O 2.0 continua **cosmético**, sem medição atrás, e por decisão do usuário:
*"é uma medição da minha cabeça, para não ficar reabrindo sem necessidade"*.

---

## O `Skull00000000...` — o laço infinito digitando na busca

`ir_para_resultado` acionava o portão da montaria **depois** de localizar o
painel:

```python
pontos = self._pontos("surroundings")
self.nav.garantir_montaria_para_andar(f"caminhar até {destino}")   # <- aqui
ctx.click(pontos["first_result"])
```

A sequência que quebra:

1. `buscar_npc` clica no campo de busca e digita `Skull`. **O campo fica com o
   foco.**
2. `ir_para_resultado` chama o portão da montaria — com o painel aberto e o campo
   ainda focado.
3. O portão **INSISTE SEM TETO** (ver `navigation`, *"NUNCA A PÉ DENTRO DA
   CAVE"*: *"Não há teto para desistir"*). Enquanto a memória não confirmar a
   montaria, ele aperta a tecla ciclo após ciclo, **para sempre**.
4. A tecla é `0`. Cada `0` cai **dentro do campo de busca**.

E o portão ainda chama `hotbar.garantir_pagina_1`, que **clica** — mais um clique
com o painel na frente.

**Conserto: a chamada foi APAGADA, e ela era redundante.** Quem chega ali passou
por `abrir_surroundings`, que já exige montaria **antes** de abrir. Ordem
determinada pelo usuário:

> *"o garantir_montaria_para_andar tem que ser antes do surroundings, pois quando
> faz o auto path ele já começa a andar, então não faz sentido essa ordem, tem que
> ser garantir_montaria_para_andar → surroundings"*

Risco avaliado: se a montaria cair entre abrir e clicar (~1-2 s), o auto-path é
**pathfinding do jogo**, não caminhada por clique, e `_manter_montaria` repõe a
montaria durante o trajeto.

**Lição que generaliza:** *nenhuma tecla pode ser enviada enquanto um campo de
texto tem o foco.* O bot não tem noção de foco, então a proteção é de **ordem**:
tudo que aperta tecla acontece **antes** de abrir a janela que tem campo.

---

## O guarda de janela — `core/janelas_abertas.py`

### Como a medição aconteceu

Eu disse ao usuário que não tinha como medir isso (precisava de capturas do
jogo). Ele mandou **nove capturas** com janelas diferentes. Depois mandou o
recorte da moldura. Depois mandou **cinco capturas sem janela nenhuma**, incluindo
cave escura e as duas fases do boss. A medição saiu em minutos.

Registro do método, porque ele vale mais que o resultado: **"não é mensurável"
quase sempre significa "eu não tenho o dado" — e o usuário tem.**

### Os números (16 quadros)

| sinal | pior COM janela | pior SEM janela | margem |
|---|---|---|---|
| **X de fechar** (18×18) | **0.898** | **0.327** | **+0.571** |
| **moldura** (100×16) | 0.829 | 0.391 | +0.438 |

O falso positivo é **estabilíssimo** entre cenas opostas: Stone City ao sol dá
0.390/0.318, cave escura dá 0.391/0.327. Variação de ~0.001 e ~0.009. **É isso que
autoriza um limiar fixo.**

Custo: **~33 ms por casamento**, os dois iguais — o custo é o quadro, não o
template.

### Por que DOIS sinais, e não um

Eles respondem perguntas **diferentes**:

- o **X** responde *"onde clico para fechar?"*. É a resposta acionável, e é o que
  torna seguro fechar sem saber que janela é: a posição não é adivinhada, é
  localizada por imagem a 0.9+.
- a **moldura** responde *"tem janela na tela?"*. É a rede: existem janelas
  **sem X** (as `Expand Bag`, a caixa de chat), e para elas o X é cego.

**Nenhum dos dois é contador de janela.** A moldura dá de 2 a 7 casamentos numa
tela com **uma** janela só, porque o filigrama se repete ao longo da borda. O X dá
sempre 1, inclusive na tela com três janelas — ele conta a menos, nunca a mais.

Por isso o laço **nunca conta nada**: ele pergunta *"ainda tem janela?"* e fecha
**uma por passada**, reconferindo. Fechar uma janela **muda a tela** (a de baixo
se reposiciona, as sub-janelas somem com a mãe), então uma leva de coordenadas
calculadas de uma vez só seria clicar em posições obsoletas — e cada clique
obsoleto cai na cena 3D e **manda o personagem andar**.

### Os limiares, e por que eles são diferentes

- **X: 0.80** — o padrão do projeto (`INVITE_THRESHOLD`, `ANCHOR_THRESHOLD`), com
  folga medida de 0.098 acima do pior verdadeiro e 0.473 abaixo do pior falso.
- **moldura: 0.65** — e **não** o 0.80. O pior verdadeiro dela (0.829) veio de uma
  cena **escura dentro da cave**, que é justamente onde o guarda importa; 0.80
  deixaria 0.029 de folga apostando que nenhuma janela futura, numa cena ainda
  mais escura, cai abaixo disso — e a amostra que define esse piso é **uma**. 0.65
  fica **no meio do vão** (0.391 / 0.829). Quando o vão é de 0.44, o limiar mora
  no meio dele, não colado numa borda.

### EM COR, e não em cinza — e isso quase passou batido

O caminho padrão do `find_template` **converte o quadro para luminância**, e a
medição foi feita em **cor**. Casar em cinza com limiares medidos em cor seria
aplicar um número a um espaço que não é o dele.

E cor é o modo **certo** para este alvo, não só o que foi medido: o
`vision.load_color` já documenta que em cinza dois elementos de mesma forma e
cores diferentes marcam 0.98 um contra o outro. O X é **vermelho** sobre placa
escura, e a HUD do jogo é cheia de glifos escuros do mesmo tamanho — é o vermelho
que o separa deles.

Travado por `test_o_casamento_e_COLORIDO_no_codigo`, que lê o AST: `load` e
`load_color` diferem por uma palavra e o resultado errado **não levanta exceção**,
só devolve números de outro espaço.

### Por evento, não por clique

O caminho rápido da entrada dispara **dois cliques por segundo** disputando a
vaga. Conferir antes de cada um seria uma captura por tentativa no único trecho
onde o projeto inteiro cortou espera para caber.

E não precisa: **janela não aparece sozinha.** Ela aparece porque o bot abriu, ou
porque o jogo mostrou uma caixa. O guarda roda ao **entrar** numa sequência de
cliques — hoje em `preparar_entrada`, uma vez, antes da rajada.

Razão do usuário, e ela fecha o caso: *"caso for interferência do usuário ele vai
fechar, mas se foi sozinho o usuário pode não estar no computador vendo"*.

### "Não sei" NÃO bloqueia

Mesma regra permanente do `CONFERIR_A_JANELA_ANTES_DE_ENVIAR` (*"bot mudo é pior
que o defeito"*) e do `na_posicao_de_clicar`, que devolve `True` sem leitura
*"porque recusar travaria o bot num laço sem saída"*.

E janela **sem X** não é fechada às cegas: fechar às cegas é clicar num
**interruptor** sem ver o estado — o erro que já produziu o pisca-pisca do painel
de arredores (*"o primeiro clique FECHA, o segundo REABRE"*). Pior: o botão de
fechar fica **sobre a cena 3D**, então um clique errado ali manda o personagem
andar.

---

## A AUTO-SABOTAGEM que o guarda NÃO comete

O clique **direito** da Block list (`team._enviar_convite`) precisa da lista
**ABERTA**. Um guarda que exige "nenhuma janela aberta" antes dele **fecharia a
própria lista** que ele vai operar.

Por isso o guarda **não** roda ali, e o caso está coberto de outro jeito: em
`_do_entrar` a ordem é `montar_time()` → `preparar_entrada()` → rajada de
cliques, então o guarda roda **depois** do time formado e **antes** dos cliques
da cena 3D. Se o `team._fechar_janelas` falhar em fechar a lista, o guarda pega.

Travado por `test_o_guarda_NAO_roda_antes_do_clique_direito_da_block_list`.

Regra que generaliza: **guarda de "cena limpa" só vale antes de clique na CENA.**
Clique dentro de janela tem outra pergunta — *"a janela CERTA está na frente?"* —
e ela já tem resposta: `_pontos(...)` localiza a janela antes de clicar.

---

## A limpeza de `data/templates/` (27/08/2026)

A pedido do usuário, depois de a medição estar feita. **32 arquivos, 33 MB → 23 MB.**

- **17 capturas de evidência** (`entrada/janelas/`) — os quadros que sustentam os
  números deste documento. Removidos com a medição já registrada aqui; refazê-la
  exige capturas novas.
- **15 recortes órfãos**, nenhum citado por código: `EnemyDead2`,
  `block_wizzofblazes{,2,4,5}`, `chat_aberto`, `icone_deletar`, `pick_up_all`,
  `prova_cheat_engine`, `skull_herald_saida`, `slot_vazio{,2,_mouse}`, `tab_npc`,
  `state_team_member-STALL-NAO-USAR`.

**A auditoria importou mais que a limpeza.** Cinco deles pareciam em uso num
`grep` ingênuo, e cada "citação" era de um arquivo **diferente**:
`chat_aberto.png` × `state_chat_aberto.png`, `pick_up_all.png` ×
`btn_pick_up_all.png`, `slot_vazio.png` × `state_slot_vazio.png`,
`icone_deletar.png` × `btn_delete_item.png`. E `tab_npc` no código é **chave de
deslocamento**, não template.

**`data/templates/deletar/` NÃO FOI TOCADA** — são 206 PNGs e ela é a **lista
branca lida em runtime** (`PASTA_DO_LIXO.glob("*.png")`). Tirar um arquivo dali
**revoga a permissão de apagar aquele item**. Nada ali é "não usado".

---

## O que ficou de fora, e por quê

- **Trava em tempo de execução** proibindo `press`/`click` com o painel aberto.
  Poria uma trava no caminho de *todo* input do bot para proteger uma janela de 2
  segundos, e uma exceção no meio de uma run é um jeito novo de perder a run. A
  regra é feita valer por **teste de AST**, sem custo em produção.
- **Template para as janelas sem X** (`Expand Bag`, chat). Nenhuma apareceu num
  relato de clique engolido — as bolsas são filhas do inventário e somem com ele,
  o chat é ancorado embaixo à esquerda. Criar template para janela que nunca
  atrapalhou é inventar mais um limiar para errar.
- **Estágio de identificação** (descobrir *qual* janela é antes de fechar). O X já
  é a resposta acionável; rodar mais nove comparações para descobrir um nome que
  ninguém usa é custo puro.
