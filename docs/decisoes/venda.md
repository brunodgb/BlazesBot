# Venda de itens — decisões e medições

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.
>
> **Onde mora o código (25/09/2026):** a leitura do slot por imagem
> (`_nota_do_slot_vazio`, `_esta_vazio`, `_confirmar_slot_vazio` e as
> constantes do miolo) saiu de `bot/vendedor.py` para `bot/leitura_do_slot.py`,
> mixin da `JanelaDeVenda`, sem mudar lógica — o arquivo tinha passado do teto
> da catraca de tamanho. O interruptor `CONFERIR_SLOT_VAZIO` e o
> `_clicar_no_slot` ficaram em `vendedor.py`.

- **Começar o bot em Stone City VENDE antes de sair farmando**
  (`routine._vender_ao_iniciar_se_estiver_na_cidade`, chamada UMA vez no início
  do `run()`). Quem para o bot na cidade quase sempre parou ali com a bolsa
  carregada, e sair para a cave sem vender é começar a execução com o espaço
  que ela vai precisar já ocupado.
  - **NÃO chama `run_maintenance()`**, e isso é a decisão. Ela é a ida COMPLETA
    à cidade e começa por `voltar_para_a_cidade()` — estando já na cidade,
    gastaria uma pedra (ou a recarga do token) para chegar onde o personagem já
    está. Pior: ela RECUSA a venda sem tecla de retorno configurada e desliga o
    `bc_farm` da conta, exigência que aqui não faz sentido nenhum porque não há
    de onde voltar. O que se chama é o par que o `teste_venda` já valida para
    exatamente esta situação: `travel_to_vendor()` → `sell_from_slot()`.
    **Nada do `VendorService` foi tocado.** `buy_supplies()` fica de fora pelo
    mesmo motivo de lá: repõe pedra gasta, e aqui não se gastou nenhuma.
  - **Quem reconhece a cidade é a COORDENADA *ou* o NOME**
    (`mapa_bc.esta_em_stone_city`) — e aqui os dois, ao contrário do resto da
    rotina. A caixa de coordenada (`y <= -490` **e** `x <= 500`) é por
    construção um **limite inferior**: foi derivada de dois pontos medidos (o
    vendedor e a Fay), e Stone City é uma CIDADE.
    - **Medido em 14/08/2026, duas partidas com 19 s de diferença:**
      `(205,-498)` foi reconhecida e vendeu; `(237,-484)` **não** foi e saiu
      para a cave com a bolsa cheia — 6 unidades acima do corte. As duas são
      Stone City e o jogo dizia isso nas duas.
    - **O nome cobre o resto da cidade.** A falha conhecida dele é ficar PRESO
      num nome antigo, e o caso medido é ficar preso numa área da CAVE estando
      fora dela — não o contrário. "Stone City" lido é sinal positivo confiável.
    - **O custo de errar é assimétrico**, e é o que autoriza ser permissivo:
      não reconhecer manda o bot para a cave com a bolsa cheia (o que trava o
      bot); reconhecer por engano faz `travel_to_vendor` procurar o Rich Man,
      não achar, devolver False e a rotina seguir com um aviso.
    - O `x <= 500` continua no caminho da coordenada porque o Y de Ghost Din
      Woods (1395,**-635**) também passa pelo corte. Travado por teste.
  - **É complemento: nunca impede o bot de começar.** Falha na venda vira aviso
    e a execução segue para o SITUAR normal — parar aqui trocaria "comecei sem
    vender" por "não comecei". Parada, DC e desligamento do farm continuam
    subindo, como em qualquer outro ponto do laço.
  - Roda dentro do `ctx.farming = True`, então desmarcar o BC no meio da venda
    de início corta na hora, igual ao resto.
- A **venda automática de itens** é acionada por **contagem de runs**
  (`runs_before_selling` em `BCVendor`, default 5) — o usuário configura em
  quantas runs quer vender antes de o bot parar. A contagem começa em cada
  execução do bot BC (reset para 0 a cada início) e é decidida em
  `routine.py._seguir_depois_de_sair`. A venda em si (VendorService /
  `sell_start_slot`) continua a mesma.
- **Sem tecla de retorno a venda desliga a conta:** se na hora de vender
  (`VendorService.run_maintenance`) nem `guild_token` nem `stone_charm` tiverem
  tecla configurada, o bot **não tenta** voltar/viajar: desliga `bc_farm`
  daquela conta, salva (`config.save()`, persiste) e devolve False — o farm
  para na próxima iteração. As views refletem o checkbox BC vazio ao vivo:
  a web via `estado()`→`farm` por conta (sync no `atualizarEstado` de
  `web/main.js`) e a GUI no `_refresh_status` (só seta o checkbox quando difere,
  para não disparar `stateChanged` à toa).
- **O ponto de parada do vendedor é (158,-494), EXATO.** `POSICAO_DO_VENDEDOR`
  mudou de (153,-492) para (158,-494) (remedido pelo usuário), e **as
  coordenadas de tela andam junto**: o `vendor_npc` saiu de (464,377) para
  **(172,301)** — quase 300 px. Mexer numa sem remedir a outra põe o clique na
  parede.
  - **Um número só** (`mapa_bc.PRECISAO_NO_PONTO_DO_VENDEDOR = 0.9`), lido por
    quem ANDA (`travel_to_vendor`) e por quem CLICA (`_open_npc`). Antes eram
    dois — a chegada aceitava 4 unidades e o clique aceitava 12 —, e 12 de folga
    é outro lugar, com o NPC girado na tela. Mesma lição do incidente da
    tolerância 3.
  - **Duas etapas:** o painel de arredores caminha até perto (folga 4) e depois
    o ajuste fino encosta no ponto exato (`TENTATIVAS_DE_ENCOSTAR_NO_VENDEDOR` ×
    `SEGUNDOS_POR_TENTATIVA_NO_VENDEDOR`), igual ao patamar do Altar Stone. Fora
    do ponto **não clica**: o clique direito cairia no chão e o personagem
    andaria, piorando a tentativa seguinte.
  - **O diálogo NÃO se move** com a posição do personagem — conferido em dois
    prints (título em (320,188) e (321,192)). Por isso `vendor_sell_tab`
    continua valendo.
  - **`npc_leave` estava ERRADO**: apontava para (513,302), que cai na cena 3D ao
    lado do personagem, não no botão "Close" do diálogo (medido em (365,653)).
    Usado só em `buy_supplies`, que é raro — por isso passou tanto tempo sem
    aparecer.
- **A venda insiste até vender: 10 ciclos, e então DESLIGA o BC farm da conta.**
  `CICLOS_DE_VENDA = 10` ciclos completos (reposicionar → abrir diálogo →
  vender), cada um já com as próprias repetições por dentro. Não vender não pode
  ser desfecho silencioso: a bolsa enche, o bot trava e o usuário perde item.
  Esgotando os dez, `bc_farm = False` + `config.save()` — a conta fica **online,
  logada, com o relogin ativo**, o checkbox desmarca nas duas interfaces (que é o
  sinal de que precisa de intervenção), e **não volta a tentar vender**. Não
  fecha o cliente, não mexe no `stop_event`, não para o bot inteiro. Mesmo
  desfecho que já existia para "sem tecla de retorno configurada".
- **A CONFERÊNCIA DE SLOT VAZIO ESTÁ DESLIGADA** (`CONFERIR_SLOT_VAZIO = False`
  no topo do `vendor.py`, decisão do usuário em 14/08/2026: *"comenta por hora
  essa verificação de slot vazio e deixa clicar a quantidade total de vezes que
  o usuário configurou como estava antes"*). Desligada, a venda faz exatamente o
  que fazia antes de a conferência existir: clica as `sell_clicks` vezes
  configuradas, em passadas de 24, com o Sell no fim de cada uma.
  - **Interruptor, não comentário** — mesmo molde do `USAR_TAB_NOS_GUARDAS` e do
    `FONTE_DA_MORTE_DO_ALVO`. O caminho continua inteiro e os testes o exercitam
    com o interruptor FORÇADO ligado, para ele não apodrecer desligado; ligar de
    volta um dia não pode ser ligar código não testado.
    `test_o_interruptor_esta_desligado` lê o valor **no import**, antes da
    fixture — perguntar depois provaria a fixture, não o código.
  - **Desligada ela é mais RÁPIDA:** some uma captura de tela por clique.
  - **A caixa "It's precious item" NÃO é afetada** — continua conferida a cada
    clique, com interruptor ou sem, porque com ela aberta a passada inteira
    vende zero.
  - **O log diz em que modo a venda rodou**, na primeira linha.
- **O SLOT VAZIO É DECIDIDO PELO CONTRASTE DO MIOLO, não por casamento de
  modelo — o casamento foi medido e reprovado.** (Tudo desta seção está no
  caminho DESLIGADO acima; fica registrado porque custou medição de produção que
  não se recupera de graça.) Produção, 12:11 de 14/08/2026:
  ```
  Slot com item   nota 0.503      limiar 0.70
  Slot VAZIO      nota 0.708      margem: 0.008   <- ruído, não sinal
  ```
  A venda parou em **2 cliques de 66**. E repetir a leitura não conserta: o
  0.708 é ESTÁVEL, então 3, 10 ou 50 leituras seguidas dariam todas positivo.
  - **A causa é a borda amarela de HOVER.** O slot que o bot confere está
    SEMPRE com ela: o bot não move o cursor físico, mas `_prime_cursor` manda
    `WM_MOUSEMOVE` para a coordenada do clique antes de cada clique, então o
    jogo desenha a borda justamente no slot que se quer examinar. A borda ocupa
    boa parte do recorte e **existe nos DOIS estados** — então era ELA que
    dominava o casamento, não o conteúdo. Acrescentar o modelo com hover
    (`state_slot_vazio_hover.png`) resolveu o "nunca casa" e criou este: os dois
    modelos passaram a casar com a borda dos dois estados.
  - **O miolo resolve porque a borda fica FORA dele.** Ícone de item é colorido
    e cheio de detalhe; slot vazio é quase liso. Medido nas fotos reais deste
    cliente (24 células cheias e 24 vazias da MESMA janela, mais os dois
    modelos): **cheio 46,75 no pior caso** (mediana 60,11), **vazio com hover
    9,76**, **vazio limpo 3,69**. Vão de 37 pontos contra os 0.008 anteriores.
    `CONTRASTE_QUE_E_SLOT_VAZIO = 25.0` fica a 2,5× do pior vazio e a menos da
    metade do pior cheio.
  - **`LADO_DO_MIOLO_DA_CELULA = 24`, e 28 já quebra:** a 28 a borda começa a
    entrar e o MESMO modelo de slot vazio salta de **9,76 para 57,80** — voltaria
    a passar por item. O número não é arredondamento, é o limite medido.
  - **É mais barato que o casamento** (um recorte e um desvio-padrão, sem
    `matchTemplate`), então a venda não perdeu velocidade nenhuma.
  - **Os dois PNGs continuam no repo**, e o `state_slot_vazio_hover.png` virou o
    corpo de prova do teste que impede o miolo de crescer. O que saiu foi o
    casamento deles da DECISÃO — travado por teste, que reprova se
    `matchTemplate` voltar ao `_nota_do_slot_vazio`.
  - **Qualquer leitura COM ITEM zera a contagem** (pedido do usuário): são 3
    leituras seguidas de vazio, e uma só com item derruba a confirmação inteira
    e a venda volta a clicar. Item na grade é prova de que não acabou.
- **A VENDA FICOU 3× MAIS RÁPIDA, e o que destravou isso foi uma imagem.** A
  confirmação por clique (recorte antes → clique → `tick(0.20)` → recorte
  depois → subtração) existia para responder UMA pergunta: *"acabaram os itens
  deste slot?"*. Ela era indireta por uma limitação que este arquivo mesmo
  registrava — *"em todos os prints a grade está CHEIA, então não existe
  amostra de célula vazia para medir"*. O usuário recortou
  `state_slot_vazio.png` e a limitação acabou.
  - **SÃO DOIS MODELOS, e os dois são obrigatórios: o slot vazio COM e SEM a
    borda de hover.** O slot que o bot confere está SEMPRE com o mouse em cima:
    o bot não move o cursor físico, mas `_prime_cursor` manda `WM_MOUSEMOVE`
    para a coordenada do clique antes de cada clique — então o jogo desenha a
    borda amarela justamente no slot que se quer examinar. Conferir só contra o
    slot "limpo" era comparar com uma aparência que nunca está ali, e foi por
    isso que a primeira versão **nunca casou** e a venda seguia clicando no
    vazio. Medido: os dois modelos marcam **0.264 um contra o outro** — um não
    cobre o outro. Vale a MAIOR das duas notas.
  - **Medido na grade real:** slot vazio **0.967**, célula com item **0.37** —
    vão de **0.598**. `LIMIAR_DO_SLOT_VAZIO = 0.70` fica no meio. O modelo de
    hover marca 0.515 num slot vazio SEM hover e 0.33 em célula cheia: nenhum
    dos dois passa o limiar por engano. O casamento custa **~0 ms** numa
    janelinha em volta do ponto.
  - **A nota E o nome do modelo que casou vão para o log a cada leitura.** É o
    que responde, na primeira venda real, se o modelo de hover está certo — e
    se o limiar de 0.70 (calibrado na grade da BOLSA, não na de VENDA) está no
    lugar.
  - **Custo por clique: 272 ms → 91 ms (3×).** Passada de 24: **6,5 s → 2,2 s**
    (e com `TENTATIVAS_POR_SLOT = 3` o pior caso antigo chegava a 20 s).
    A economia veio da espera fixa: `ESPERA_ENTRE_CLIQUES_DA_VENDA` é 30 ms,
    não 200. **Não é zero de propósito** — o clique tem efeito de estado (o item
    sai, os de trás sobem) e colar arriscaria clicar durante o rearranjo.
  - **TRÊS leituras vazias SEGUIDAS para parar** (`LEITURAS_VAZIAS_PARA_PARAR`),
    e **sempre no MESMO slot — o que está sendo clicado**. A leitura sai ~30 ms
    depois do clique, com os itens ainda SUBINDO para preencher o buraco: um
    quadro pego aí mostra o slot vazio sem ele estar. Uma leitura só encerraria
    a venda com item na bolsa; três exigem que o transitório se repita em três
    ciclos seguidos, e ele não se repete — o clique seguinte já mostra o item
    que subiu. Custo de confirmar o fim: **274 ms** (3 cliques). O custo do erro
    oposto é a venda parar com item na bolsa, e bolsa cheia trava o bot.
  - **A conferência é um recorte em volta do ponto CLICADO, nunca a tela toda.**
    O `alvo` que o `ctx.click` recebe é o mesmo que a conferência recebe. A
    grade tem outros slots vazios (os de baixo, que nunca tiveram item), e
    procurar na janela inteira acharia qualquer um deles e encerraria a venda
    com item ainda no slot que interessa. Travado por teste, por leitura do
    fonte.
  - Conferir A CADA CLIQUE continua melhor que a cada 10: para em 3 cliques em
    vez de até 10, pelo mesmo custo (a captura já acontece para a caixa
    "precious").
  - **UMA captura serve às DUAS perguntas** do ciclo: a caixa "It's precious
    item" e o slot vazio. É por isso que conferir o slot é de graça.
  - **A caixa precious continua conferida a CADA clique** — decisão do usuário,
    com o motivo: ela aparece com MUITA frequência na venda, às vezes em
    sequência, e com ela aberta os itens param de subir e a passada inteira
    vende zero. Conferir a cada 10 perderia até 9 cliques por aparição.
  - **Saíram `TENTATIVAS_POR_SLOT`, `TETO_DE_CLIQUES_FISICOS`,
    `MUDANCA_MINIMA_NO_SLOT` e a `_cauda_vazia`** — os quatro eram a resposta
    indireta para a mesma pergunta. O teto de cliques físicos não foi jogado
    fora: sem repetição, físico e efetivo são 1:1 e ele deixa de existir por
    construção.
  - **Slot vazio encerra a VENDA INTEIRA**, não só a passada: os itens sobem
    para preencher, então slot N vazio quer dizer que não há nada de N para
    frente — as passadas seguintes clicariam no nada. E o Sell ainda é clicado:
    o que já subiu tem que virar dinheiro.
  - **RESSALVA:** o 0.966/0.368 foi medido na grade da BOLSA (o print
    disponível); o modelo veio da janela de VENDA. Por isso a nota vai para o
    log a cada conferência — a primeira venda real traz o número para cravar o
    limiar. Os dois erros são baratos: limiar alto gasta cliques no vazio,
    baixo encerra cedo e a passada seguinte pega o resto.
- **O slot vazio encerra a venda, mas a confirmação é ESPAÇADA — contar leituras
  coladas ao clique não separa "acabou" de "está rearranjando".** Medido na
  venda das 10:43 de 14/08/2026: a passada parou com **22 dos 66 cliques**
  dizendo "acabaram os itens", com a grade CHEIA — a foto da própria run
  (`logs/diagnostico-do-link/104345.082-...-t+750.png`) mostra 24 itens na
  página 1/3 e o slot 4 com item.
  - **A causa é a própria mecânica da venda:** ao tirar um item, os seguintes
    SOBEM para preencher o buraco, e entre o item sair e o próximo descer o
    slot fica **de verdade vazio** por um instante. A
    `ESPERA_ENTRE_CLIQUES_DA_VENDA` (0,03 s) foi encurtada de propósito para
    clicar mais rápido que isso — então as três leituras naquela cadência caem
    dentro do MESMO vão. Subir o contador de 2 para 3 não resolveria; o que
    resolve é `_confirmar_slot_vazio`, que **relê sem clicar**, espaçando as
    leituras por `ESPERA_PARA_CONFIRMAR_VAZIO` (0,25 s). Uma leitura com item
    derruba a confirmação INTEIRA — item na grade é prova de que não acabou.
  - **O custo só é pago quando alguma leitura diz vazio**, ou seja no fim da
    venda (uma vez) ou num vão ocasional. O caminho rápido continua rápido.
  - **`bag_count()` não serve de veredito aqui, e o log engana:** a mesma venda
    registrou `0 itens vendidos (60 -> 60)` tendo vendido — a leitura de bolsa é
    imprecisa, como este arquivo já registrava. Quem prova a venda é a GRADE:
    comparando as fotos de 10:43 e 10:55, os slots protegidos 1..3 estão
    idênticos e o conteúdo do slot 4 em diante mudou.
  - **A âncora da janela de venda está CERTA e a geometria base não.** Medido
    na foto real: `_sell_anchor` casa a 0.951 e põe o slot 4 em (554,292), que é
    o 4º ícone da primeira fileira; `sell_grid` calculado põe em (552,327), que é
    o slot **10**. Por isso `_ponto_do_slot` prefere a janela localizada — a
    queda para as coordenadas calculadas é rede, não equivalente.
  Travado por `tests/test_venda_rearranjo.py`, que simula a venda inteira com o
  vão de rearranjo e tem um **dente**: reintroduzida a contagem colada, a venda
  de 66 para em menos de 10 e o teste exige que isso seja reproduzível.
- **A venda decide por IMAGEM, não por memória de UI.** As leituras de estado de
  UI desta build não respondem: `bag_open()` falhou em **5 de 5 runs** no log de
  dev, e `modal_open()` (a mesma espécie de flag) era o que impedia o Ok da caixa
  de item precioso de ser clicado. Regra que ficou: **a cada clique, conferir na
  TELA se o esperado aconteceu; se não, repetir.**
  - **O par de cliques do NPC** (`_open_npc`) usa
    `ui._abrir_dialogo_e_clicar` — clica no Rich Man, **confere que o diálogo
    abriu** (`state_dialogue.png`), e só então clica em "Sell Item". Antes os
    dois cliques saíam em sequência e só o resultado era conferido: sem diálogo,
    o clique no link caía na cena 3D e **o personagem andava** — e com 4 voltas,
    cada uma o empurrava mais para longe. As duas coordenadas foram conferidas
    contra prints e estão certas; o defeito era clicar sem saber.
  - **A caixa "It's precious item"** é detectada pelo template do **TEXTO**
    (`state_precious_item.png`, 192×17, recortado de print do usuário). Medido:
    **1.000** com a caixa na tela, **0.454–0.483** nos três prints sem ela;
    `LIMIAR_DA_CAIXA_PRECIOSA = 0.80`. O template não pode ser o botão: a caixa e
    a janela de venda usam botões idênticos (Ok/Cancel × Sell/Cancel). O **Ok é
    derivado** do texto (`TEMPLATE_ANCHORS["precious"]`, deslocamento `(-43,141)`
    **a partir do CENTRO** — `find_template` devolve centro, e medir do canto
    poria o clique 96 px ao lado).
  - **Cada clique na grade é verificado por diferença de imagem**: recorte do
    slot antes e depois (`MUDANCA_MINIMA_NO_SLOT`). Mudou = surtiu efeito. Não é
    "a célula está vazia?" porque esse limiar **não tem como ser calibrado** — em
    todos os prints disponíveis a grade da bolsa está cheia, e chutar aqui
    repetiria o incidente da tolerância 3. A diferença compara o slot com ele
    mesmo e dispensa calibração.
  - **A contagem do usuário é de cliques QUE SURTIRAM EFEITO.** Um clique
    engolido é repetido sem consumir a conta (até `TENTATIVAS_POR_SLOT`), com teto
    de `TETO_DE_CLIQUES_FISICOS` (1,5×) contra laço. Quando um slot não responde
    nem depois das repetições, a **cauda vazia** é marcada e dali em diante sai 1
    clique por unidade restante — a contagem configurada é honrada sem repetir
    contra a grade vazia (24 configurados numa grade vazia custam 26 cliques, não
    72).
  - **`bag_count()` não decide mais nada.** Ele parava as passadas
    ("nada saiu da bolsa"), e o próprio `CLAUDE.md` já registrava que essa
    leitura é imprecisa. Sobrou só no log.
- **"It's precious item, please confirm!" — o Ok é CONFIRMADO, não só clicado.**
  Clicar num item precioso na grade de venda abre a caixa; o item só sai depois
  do **Ok** (coordenada `confirm_ok`, medida e conferida contra print do
  usuário). Com a caixa aberta, TODO clique seguinte na grade — e o próprio
  **Sell** — é engolido. `VendorService._dismiss_confirm` clica o Ok e **relê o
  flag de modal** para conferir que fechou, insistindo até `TENTATIVAS_NO_OK`
  (3). Medido em simulação: com UM Ok ignorado pelo cliente, a versão anterior
  (um clique, sem conferir) perdia 1 item de 10; com dois ignorados, 2 de 10 —
  a caixa ficava na tela e os cliques seguintes eram gastos da contagem sem
  vender nada. Se nem 3 Ok fecharem, **avisa e segue**: `modal_open()` é um flag
  genérico (serve também para DC e erro de login), então "ainda aberta" pode ser
  leitura ruim, e abortar a passada por isso trocaria um problema por outro. A
  conferência roda ANTES de cada clique da grade e antes do clique em Sell.
- A **leitura de bolsa para o gatilho de venda está DESATIVADA**. ler a
  quantidade de itens da bolsa (`bag_count` / `BagConfig`)
  se mostrou imprecisa e o bot nunca entrava na venda por esse caminho.
  `VendorService.precisa_ir_vender()` está desativado (devolve sempre `None`) e
  é o botão `ck_bag` ("Revender pelo espaço livre da bolsa") no diálogo de
  conta que aparece desmarcado/desabilitado para deixar claro ao usuário que a
  opção por espaço na bolsa está off.


---

## 18/08/2026 — o Rich só existe em Stone City, e o bot não conferia

Relato: *"o filtro por Rich e a ida até ele só deve acontecer em Stone City. Se
tiver em outra localização não irá funcionar, vai apenas ficar andando em um
loop."*

### Duas causas

**1. O retorno não era conferido nem repetido.** `voltar_para_a_cidade`
confirmava o teleporte pelo **salto de posição** (`SALTO_QUE_CONFIRMA`) — que
prova que ALGO aconteceu, não que o destino é Stone City. E o chamador
**ignorava o retorno**: era `self.voltar_para_a_cidade()` sem `if`.

**2. `travel_to_vendor` não tinha portão de local.** Fora da cidade ela abria o
painel de arredores, o filtro por "Rich" não achava nada e o personagem andava.
Pago **10 vezes**, uma por ciclo de venda.

### Como chegar — números do usuário

    Token × 10, uma a cada 10 s, conferindo Stone City APÓS CADA USO
    Pedra × 3,  uma a cada 10 s, conferindo APÓS CADA USO
    Tecla não configurada ⇒ o bloco dela é PULADO inteiro

O Token vem primeiro e é tentado muito porque **não gasta item**. A recarga
interna do bot **não barra** a tentativa: *"às vezes pode ter ocorrido uma falha
na contagem"* — apertar na recarga não custa nada além do tempo.

A pedra são só 3, porque ela **gasta**, e o usuário explicou por que 3 bastam:
*"é garantido que vai usar, pq não tem recarga, é só o usuário ter comprado
anteriormente."*

### A pedra falhar é DIAGNÓSTICO, não azar

Se a pedra foi usada e o bot não chegou, só há duas explicações — estoque zerado
ou **tecla configurada errada** — e as duas exigem intervenção. O log diz isso
com essas palavras, com a coordenada e o nome lidos ao lado. Repetir em silêncio
esconderia um erro de configuração do usuário. *(Insight dele, não meu: minha
recomendação original era só "aceitar e registrar".)*

### As 3 rodadas, com uma run de BC entre elas

Não vendeu ⇒ roda **1 run de BC** e tenta de novo, até **3 rodadas**
(`routine.RODADAS_DE_VENDA_ANTES_DE_DESLIGAR`).

**A run de BC é a manobra de destravamento, e isso é mais engenhoso do que
parece:** ela termina passando pela saída da cave e pela Fay, que é **troca de
mapa de verdade** — e o `bot/bc/localizacao.py` registra que só uma troca de mapa
reescreve o campo do nome do lugar, justamente a leitura que fica presa na área
anterior e faz o bot achar que não está em Stone City.

- **A run extra NÃO conta para o gatilho.** `_runs_na_ultima_venda` não é
  atualizado no caminho de falha, então o bot volta a tentar vender assim que a
  run terminar, em vez de farmar as 8 configuradas de novo. É o ponto mais fácil
  de implementar errado, e tem teste próprio.
- **Zera na venda bem-sucedida.** Sem isso, duas falhas separadas por horas de
  farm somariam e desligariam a conta sem motivo.
- **Esgotadas as 3, o BC da conta é DESLIGADO** e salvo: *"caso não chegue a
  vender os itens, o bot deve parar de funcionar, deve ser desligado."* A conta
  fica online e logada, e o checkbox desmarcado é o sinal. Mesmo desfecho que já
  existia para "sem tecla de retorno" e para os 10 ciclos sem vender.

### Ressalva registrada a pedido

O portão usa `mapa_bc.esta_em_stone_city`, que é **coordenada OU nome** —
reutilizar a função existente foi decisão do usuário. O nome é a leitura com
**oito episódios de travamento** registrados no `localizacao.py`. A decisão é
defensável (o teleporte é troca de mapa, que reescreve o campo), mas **se o laço
voltar, é o primeiro lugar a olhar** — e isso está escrito no código, junto da
chamada.

Travado por `tests/test_ida_para_stone_city.py` (11 testes).

---

# O Rich é PROCURADO na tela, não decorado numa coordenada

**Data**: 2026-08-19. Pedido do usuário: *"em vez de usar uma coordenada fixa
para o vendor_npc, você vai buscar ele na tela para clicar, assim tendo mais
precisão."*

## A medição que já estava no código e ninguém tinha usado

O comentário de `coords.vendor_npc` guarda o número que justifica a mudança:

> *"AS DUAS ANDAM JUNTAS: mudar a posição de parada sem remedir o `vendor_npc`
> põe o clique na parede. Quando o usuário mudou de (153,-492) para (158,-494),
> o NPC saiu de (464,377) para (172,301) -- quase 300 px."*

**Cinco unidades de mundo movem o NPC quase 300 px na tela.** Ou seja, ~60 px
por unidade. `PRECISAO_NO_PONTO_DO_VENDEDOR = 0.9` limita o erro a ~54 px, e não
o elimina: dentro da tolerância o Rich ainda passeia dezenas de pixels, e o
clique direito que erra cai na cena 3D.

Achar por imagem tira a dependência entre as duas coordenadas -- que era a coisa
mais frágil da venda, e a única que exigia remedir a tela ao mexer no chão.

## A propriedade inegociável: nunca pior que hoje

`_onde_clicar_no_rich()` **nunca devolve `None`**. Template ausente, captura
falhando, quadro em branco, casamento fraco: todos caem em `coords.vendor_npc`,
que é exatamente o que o bot fazia antes. O caminho novo só pode melhorar a
mira; se não responder, o comportamento é o de sempre -- e o log diz qual dos
dois foi usado, com a distância entre eles.

É o que os quatro primeiros testes travam. Um localizador que devolvesse `None`
numa dessas trocaria uma mira imprecisa por uma venda que não acontece.

## A busca é LIMITADA, e isso não é otimização

`RAIO_DA_BUSCA_DO_VENDEDOR = 200` px em volta da coordenada esperada. Não é
velocidade: é evitar casar um sprite de NPC do outro lado do cenário, porque um
clique direito lá é um clique no lugar errado.

200 px contra os ~54 px que a tolerância permite dá três vezes de folga -- e o
teste amarra essa relação à medição (300 px / 5 unidades) em vez de ao número,
para que mexer na tolerância de parada faça o teste falar.

`LIMIAR_DO_VENDEDOR = 0.80`, e erra para MENOS de propósito: sprite de NPC contra
cenário 3D é mais difícil que ícone de UI, e falso negativo cai na reserva
enquanto falso positivo manda o clique para o lugar errado.

## O que NÃO mudou

O portão de posição fica: `_no_ponto_do_vendedor()` continua barrando o clique
de fora do ponto. Achar o Rich na tela melhora a MIRA; não autoriza clicar de
longe.

---

## O respiro em volta do botão "Sell" (25/08/2026)

> *"Na hora de vender os itens, tem vezes que ao tentar clicar no botão 'Sell'
> está tudo tão rápido que acaba não clicando... criar uma pequena delayzinha
> para garantir o clique e não atropelar funções. De resto está perfeito, é só
> nesse momento mesmo."*

**Por que justo ali, e não em qualquer clique.** O Sell é o **único clique do
bot que chega na cola de uma rajada**: até `CLIQUES_POR_PASSADA` (24) cliques
nos slots a `ESPERA_ENTRE_CLIQUES_DA_VENDA` (0,065 s) cada, um atrás do outro.
O cliente ainda está digerindo a lista quando o Sell entra na fila.

**E o custo de errar é alto**: um Sell engolido marca a passada inteira como
vendida sem ter vendido nada. O item volta para a bolsa cheia, e o bot segue
achando que resolveu.

```
ESPERA_ANTES_DO_SELL  = 0.30   <- era o que faltava
ESPERA_DEPOIS_DO_SELL = 0.5    <- já existia, como um `0.5` solto no código
```

O "depois" **já estava lá**, sem nome, no meio da função. Ganhou constante para
aparecer no `docs/INTERRUPTORES.md` e poder ser ajustado sem caçar a linha.

### É espera cega, e é exceção consciente à regra do projeto

A regra é *"onde havia espera cega, agora se PERGUNTA"*. Aqui não dá: **"o
cliente terminou de digerir 24 cliques" não tem observável.** Perguntar exigiria
reprocurar a âncora do Sell por template a cada passada — uma captura de tela
para responder algo que um terço de segundo resolve.

### O número é observação de campo, e isso está dito

Não é medição instrumentada: é o usuário vendo o clique se perder. Foi escolhido
para ficar confortavelmente acima da cadência da rajada (0,065) e na mesma ordem
do respiro que já existia depois (0,5). **Se ainda escapar, é aqui que se mexe.**

Travado por `tests/test_venda.py::test_o_Sell_tem_respiro_ANTES_e_DEPOIS`, que
lê o AST e confere a ORDEM — respiro, clique, respiro. E por um segundo teste
que garante que o respiro é maior que a cadência da rajada: um respiro da ordem
do intervalo entre os cliques não seria respiro nenhum, seria mais um clique.

## O total de cliques é do PERSONAGEM, não da cave (09/09/2026)

> *"a 'quantidade de cliques' que hoje está na configuração de BC, ela deve ir
> para a aba do personagem, para valer para todas as caves, pois na hora da
> venda essa vai ser a quantidade de cliques totais como é feito em BC"*

### E o número justifica o escopo

Ele não descreve a cave — descreve **quanta bolsa este personagem tem para
esvaziar**. A cave muda o que cai dentro do inventário, não o tamanho dele. Dois
campos para um número só criavam a mesma classe de problema que a conta de reset
já tinha criado: valores divergentes sem resposta para "qual vale".

Na conta do usuário eles **divergiam de verdade**: BC 72, HH 24. O do BC ganhou
a migração, porque foi ele que o usuário apontou como o certo.

### Hierarquia

```
account.settings.sell_clicks            ← ENTRA (escopo do personagem)
account.settings.bc.vendor.sell_clicks  ← SAI
account.settings.hh.vendor.sell_clicks  ← SAI
account.settings.*.vendor.max_sell_passes ← FICA na cave
```

**`max_sell_passes` continua de cave** porque ele é o TETO de idas à janela de
venda, e isso é característica do trajeto daquela cave — não do inventário.

### O derivado virou função

`BCVendor.passadas_necessarias` era uma `@property` que lia `self.sell_clicks`.
Com o total fora da cave, ela virou `passadas_para(cliques)` — **recebe** o
total em vez de ir buscá-lo. Uma propriedade que fosse ler `AccountSettings`
faria a configuração da cave depender da conta, o contrário da direção em que
essa árvore aponta.

### O rótulo da PyQt6 estava mentindo

Ele dizia **"Cliques por passada"**, e o campo nunca foi isso: o bot divide o
total em passadas de 24 (`CLIQUES_POR_PASSADA`), que é o limite do jogo por
venda. Na migração o rótulo passou a ser **"Total de cliques na venda"**. A
interface web já dizia "Quantidade de Cliques", que estava certo.

### Onde ficou, nas duas interfaces

Ao lado do **uso de bolsas**, na aba Personagem — que é o mesmo assunto: quantos
slots existem para esvaziar, e quantos cliques isso custa.

## Os dois gatilhos da venda (09/09/2026)

A leitura de itens da bolsa **não dispara mais venda em cave nenhuma**. Regra do
usuário: *"esse valor é instável e gera falhas"* — e o BC já havia removido esse
gatilho antes de a HH existir, pelo mesmo motivo. A HH o tinha reintroduzido.

Sobraram dois, e só dois:

1. **cota de runs** — `stats.runs − runs_na_ultima_venda >= runs_before_selling`;
2. **largada da rotina** — uma vez por largada, incondicional, na porta da cave.

**Medir continua; decidir não.** A contagem de itens aparece nos logs (bolsa
antes e depois da venda) e no painel de diagnóstico. `BagConfig.capacidade`
continua alimentando os logs das duas caves.

**Ficou órfão:** `BagConfig.precisa_vender` e `BagConfig.espaco_livre` não têm
mais nenhum chamador de decisão, e `folga_minima` só é validado. Não foram
removidos porque `BagConfig` é configuração compartilhada e a remoção mexeria em
validação e interface — está registrado aqui para quem for limpar.

O detalhe de POR QUE a largada vende na porta e não antes está em
`docs/decisoes/hh.md` §27.

## O deletador diz quanto FALTOU, em toda passada (11/09/2026)

### O que estava invisível

Um modelo que **nunca** casa é mudo: a passada apaga os outros, o log diz
"7 item(ns) deletado(s)" e parece tudo certo.

Relato do usuário sobre o `Trap-Meshwork`: *"agora adicionei de volta, porém não
está deletando os itens que são iguais"*. Medido nos logs: dos 15 modelos da HH,
**treze apagaram** (o `Purple-Cowry` 52 vezes) e **dois nunca apagaram** —
`Trap-Meshwork` e `Warm-Jade`.

E o diagnóstico que existia (09/09/2026) não respondia: ele só rodava quando a
passada apagava **zero**, e as passadas da HH estavam apagando de 2 a 9 itens.

### O relatório agora sai sempre, e de graça

`find_all_templates` ganhou `placar`: uma lista opcional que recebe o maior
valor de correlação visto. **Não custa nada** — o `matchTemplate` já rodava e
esse número era simplesmente descartado.

Com isso, a versão anterior do diagnóstico (`_explicar_o_zero`, que refazia o
casamento só para medir) **foi embora**: custava ~90 ms por passada e, pior,
media *depois*, com a bolsa já diferente daquela em que a decisão foi tomada.

### Como ler o número

| faixa | significado | o que fazer |
|---|---|---|
| **0,30–0,60** | o item não está na tela, ou o modelo é de outro item | nada |
| **0,80–0,91** | o item **está** lá e o recorte quase bate | refazer o PNG |

O limiar é `LIMIAR_EM_COR = 0.92`.

### O que a medição offline já disse sobre os dois modelos

Comparados com os treze que funcionam (22×22, 4 canais opacos, todos):

| modelo | desvio | bordas | nitidez (Laplaciano) |
|---|---|---|---|
| média dos 13 que funcionam | — | — | **14 937** |
| `Purple-Cowry` (52 exclusões) | 43,7 | 33,1% | 3 437 |
| **`Warm-Jade`** | **30,7** | **20,0%** | **1 067** |
| **`Trap-Meshwork`** | 49,4 | 39,0% | 4 302 |

**O `Warm-Jade` se explica**: é a menor nitidez de todas, e a imagem confirma —
o recorte pegou só o **miolo liso** de uma esfera laranja, sem contorno e sem o
fundo escuro do slot. Correlação precisa de estrutura para travar; gradiente
suave correlaciona igualmente bem com qualquer outro gradiente suave.

**O `Trap-Meshwork` NÃO se explica por aí**: 4 302 é mais que o `Purple-Cowry`,
que apaga o tempo todo. Ele também é um recorte do miolo (o interior azul da
pedra, sem contorno), mas a medida offline não basta para afirmar a causa — ela
precisa do casamento contra um quadro que contenha o item, e é isso que o
relatório novo passa a dar na próxima passada.


## O SELL ERA UM COMMIT SEM RECIBO (20/09/2026)

### O relato e o que o log respondeu

O usuário descreveu *"o clique final no botão Sell falha de forma intermitente;
o bot acha que vendeu, fecha/reabre a loja e os itens continuam lá"*.

Meio certo. O bot **não** achava que vendeu — ele media e registrava. Sobre 129
vendas do log:

| | |
|---|---|
| vendas concluídas | 129 |
| **com ZERO itens** | **7 (5,4%)** |
| bolsa não baixou | as mesmas 7 |

`55->55`, `57->57`, `32->32`, `28->28`, `31->31`, `33->33`, `55->55` — todas na
conta `creubo`. A conferência `antes - depois` já existia; ela só chegava
**tarde demais para agir**, no fim da venda inteira. Servia para registrar o
prejuízo, não para evitá-lo.

### A bimodalidade é o que aponta o culpado

A distribuição é **tudo ou nada**: ou saem ~20 itens (58→36, 58→35, 55→35…), ou
sai **nenhum**. Nunca 3 de 20.

Isso não é compatível com "um clique entre 72 se perdeu". É compatível com
perder o **commit**: os 24 cliques montam a lista e o Sell concretiza. Perder o
Sell não perde metade da passada — perde a passada inteira.

### Hipóteses reprovadas, todas por medição

| hipótese | o que a mediu derrubou |
|---|---|
| **janela ausente ou deslocada** | em 6 dos 7 casos a âncora FOI casada por imagem (`janela localizada`), e `_ponto_do_slot` já devolve `None` sem âncora — o bot não clica no vazio |
| **o guarda de janela fechando a venda** | disparou em **44 das 122 vendas BOAS** também; não separa os grupos |
| **tempo** | `ESPERA_ANTES_DO_SELL = 0.40` já tinha sido adicionada por um defeito idêntico (*"um Sell engolido marca a passada como vendida sem ter vendido nada"*), e o defeito voltou em 5,4%. Tempo não fecha isso: fecha CONFERÊNCIA |

O que sobrou: `ctx.click(botao_vender)` saía **uma vez, cego**.

### Por que a BOLSA e não o botão renderizado

O pedido original era validar que *"o botão Sell está clicável"*. Isso é
**pré-condição**, e ela não prova nada: o botão pode estar desenhado e o
`SendMessageW` ser ignorado assim mesmo — que é exatamente o defeito.
`bag_count()` prova o **efeito**, custa microssegundos, funciona minimizado e é
MEMÓRIA PRIMEIRO.

### Por que reclicar é seguro

Porque **nenhum clique novo no slot acontece entre as tentativas**: a lista já
está montada, e o Sell repetido concretiza a MESMA venda. O risco invertido — o
primeiro Sell ter sido aceito e a bolsa ainda não ter atualizado — é tratado
pela ordem: o reclique só sai depois de a bolsa ser perguntada até o teto. Se
ela baixar, não há segundo clique; e se sair mesmo assim, cai numa lista vazia,
com `_dismiss_confirm` logo atrás.

Travado por `tests/test_sell_conferido_pela_bolsa.py`.

### DÍVIDA ABERTA: `vendedor.py` precisa ser dividido

Este conserto levou o arquivo de 996 para **1068 linhas**, e o teto herdado da
catraca de tamanho é **1028** (baseline 935 de 05/09/2026, +10% de margem).
`tests/test_quality_gates_python.py::test_max_linhas_por_arquivo` está
**vermelho de propósito** desde 20/09/2026.

O número NÃO foi subido: a catraca existe justamente para impedir isso, e o
texto dela manda dividir por RESPONSABILIDADE (2 a 7 módulos, 120 a 800 linhas).
Decisão do usuário em 20/09: commitar o hotfix primeiro — a venda parada custa
5,4% das idas — e dividir `JanelaDeVenda` no commit seguinte, como assunto
próprio. Cuidado ao dividir: `bc/vendor.py` e `hh/vendedor.py` herdam desta
classe.

### O `break` foi TENTADO e REPROVADO no mesmo dia

A primeira versão encerrava a venda quando o Sell falhava as três vezes
("commit quebrado, não adianta seguir"). Parecia certo e
`tests/test_venda_rearranjo.py` o derrubou na hora: com a grade vendendo
normalmente e a bolsa do dublê parada, ele encerrava na primeira passada — **24
itens de 66**.

A lição: `bag_count` pode simplesmente atrasar além do teto, e aí parar mata uma
venda que estava funcionando. O reclique fica; a decisão de abandonar a ida,
não. Uma passada que não confirmou grita no log e no diário, e a seguinte tenta.

### O respiro depois do Sell virou pergunta

`ESPERA_DEPOIS_DO_SELL = 0.60` era gasto fixo em **toda passada, três por
venda**. Virou o TETO de `_bolsa_depois_do_sell`, por `core/espera.ate` — sai no
instante em que a bolsa baixa, e o teto só é pago quando a venda de fato não
saiu, que é justamente quando vale esperar.

### Alcance: BC e HH, sem injetar em dois lugares

`sell_from_slot` é **uma só**, em `bot/vendedor.py`. `bc/vendor.py` e
`hh/vendedor.py` herdam de `JanelaDeVenda` e já a chamavam — consertar ali
conserta os dois. Injetar a rotina em cada ecossistema seria a duplicata que o
`CLAUDE.md` proíbe. Travado por `test_os_DOIS_ecossistemas_herdam_o_mesmo_conserto`.
