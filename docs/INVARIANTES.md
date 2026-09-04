# INVARIANTES por área — o que não pode ser violado

> **Saiu do `CLAUDE.md` em 27/08/2026**, pela regra de governança do usuário: o
> `CLAUDE.md` guarda skills, arquitetura global e regras técnicas críticas; regra
> de ÁREA mora aqui. O conteúdo abaixo é **verbatim** — nada foi reescrito nem
> resumido na mudança.
>
> **LEIA A SEÇÃO DA ÁREA ANTES DE MEXER NELA.** Cada item é o que não pode ser
> violado. A especificação técnica está em `docs/REGRAS.md`; o **porquê medido**,
> em `docs/decisoes/<area>.md` — e é lá que mora a alternativa que já reprovou.

---
## O laço do APP — `docs/decisoes/cura-no-app.md`

`bot/app/executor.py` + `cura.py`. **Todos os números moram lá**; a
especificação em `docs/REGRAS.md`.

### O LAÇO QUE RODA é o SIMPLES (`LACO_SIMPLES = True`, 26/08/2026)

Decisão do usuário depois de refinamentos que foram ficando piores:
*"vamos voltar ao simples — dá TAB, deixa rodar a macro até o final, só para no
meio se SAIR DE BATALHA; não verifica mais vida, não verifica mais nada"*.

```
FORA de batalha → pet → comida → voltar ao ponto → limpar bolsa → TAB único → linha 0 → macro
EM batalha       → roda a macro de novo, SEM TAB e SEM conferência
saiu de batalha  → corta a macro no meio, volta ao topo
vida < 30%       → a cura, entre voltas (inalterada)
```

- **ORDEM ESTRITA: TODO "fora de batalha" ANTES do TAB, o TAB por ÚLTIMO.** Pet,
  comida, trava de posição e limpeza da bolsa vêm PRIMEIRO; a aquisição de alvo
  é a ÚLTIMA coisa antes da linha 1 (a regra absoluta do Core Loop). A limpeza
  da bolsa passou do fim da volta para cá em 29/08/2026.
- **UM SÓ CAMINHO DÁ TAB, `_adquirir_alvo`** (29/08/2026). O relógio dos 4 s
  do time NÃO TABa mais em `rodar()` — só PEDE via `_tab_solicitado`, consumido
  pela volta. É IDEMPOTENTE (`_mesmo_alvo_verificado`): se já tenho o alvo VIVO
  confirmado, o TAB não sai de novo mesmo que o relógio e o portão peçam na mesma
  volta. Foi o fim do TAB duplo no modo "copiar".
- **O GUARD SE COMPÕE COM AS TRÊS TROCAS QUE VALEM:** alvo morto/sumiu libera o
  TAB; o mob do PENHASCO (`_inalcancavel_id`) não é protegido; e o contador
  `VOLTAS_SEM_BATALHA_PARA_TROCAR = 3` (alvo vivo travado) VENCE a idempotência.
- **SEM ALVO REAL A MACRO NÃO RODA — o veredito da aquisição é PROPAGADO**
  (30/08/2026). O vazamento fechado: `_conseguir_o_tab` engolia o `False` de
  `_garantir_alvo` e a macro disparava com `target_id == 0` (ou travado no
  cadáver). Agora ele PROPAGA: id não mudou nem está vivo ⇒ `_garantir_alvo`
  volta `False` ⇒ `_adquirir_alvo` volta `False` ⇒ a volta retorna ao Core Loop
  **antes da linha 1** — nenhuma skill sai no vazio. No caminho cego (sem
  leitura de memória) o contrato histórico permanece: TAB cego, macro roda.

- **NÃO LÊ O ALVO EM LUGAR NENHUM** — nem HP, nem id, nem nome, nem a barra. A
  única pergunta é *"estou em batalha?"*, da struct do PERSONAGEM, que nunca
  falhou em nenhuma medição.
- **EM BATALHA NÃO SE DÁ TAB** — é isso que impede o defeito que matou o
  personagem: não existe caminho onde ele larga um mob de pé.
- **O MOB DO PENHASCO SE RESOLVE SOZINHO:** TABa nele, roda a macro, nunca entra
  em batalha, termina fora de batalha e TABa de novo. A régua virou
  consequência de não existir.
- **A LINHA 0 DA MACRO É O TAB** (`espera_depois_do_tab_ms`, padrão 1000): tecla
  **espelho** de `keys.next_target`, só-leitura, posição fixa, tempo editável.
  **NÃO é `AppStep`.** Piso de **100 ms** em todo tempo do APP; **20 linhas**.
- **QUEM JÁ ESTÁ NO PONTO NÃO RECEBE ORDEM DE ANDAR** — clique no minimapa é
  ordem de andar, e ordem pendente **cancela a poção**.
- **CURA:** vida < 30% ⇒ espera SAIR DE BATALHA, volta ao ponto, bebe até 90%
  (até 5 poções, 15 s). **Só se anda ANTES de beber.** **Beber PÕE SENTADO** —
  não sentar prova que a poção acabou; aí ele SENTA (até 30 s). Devolve **DE
  PÉ** e não conta volta.
- **`is_sitting()` e `pet_active()` SÃO TRI-ESTADO** (consertadas na FONTE): da
  **2ª poção em diante** ele já está sentado, então "sentou" não prova nada.

### O que ficou PARADO (interruptor, não apagado)

Morte pelo HP, a segunda porta pela TELA, o pedágio das 3 linhas cegas, a régua
do penhasco, a urgência. **Cada uma tem medição atrás**, e
`tests/test_tab_no_app.py` desliga o interruptor e exercita todas — religar é
trocar um `True` por `False` e 134 testes voltam a valer.

A conferência de id no TAB RELIGOU como parte do TAB único (`_adquirir_alvo` +
`_mesmo_alvo_verificado`): o TAB de abertura agora confere id/hp em memória e é
idempotente, não cego por timer. O porquê está em
`docs/decisoes/tab-unico-do-app.md`.

- **O ALVO VEM PELO MESMO CAMINHO DO BC** (`TargetHybrid`) quando for religado.
  O portão `critical_ok()` vale **só para as leituras do personagem**.
- **MEDIÇÃO EM ABERTO:** mobs vivos e inteiros existem FORA da janela que
  `_procurar_entidade` varre (`docs/decisoes/alvo-o-que-esta-medido.md`, itens
  39–41). Achar o array de verdade é o que devolve a leitura do alvo.

## Deletar itens: LIGADO, e só no ecossistema APP

`blazesbot/bot/app/deletador.py`. O BC resolve bolsa cheia vendendo; o APP roda
longe de vendedor. Detalhe e medição: `docs/REGRAS.md` (seção "Deletar itens")
e `docs/decisoes/deletador.md`.

- Fluxo **NÃO usa tecla**: item → ícone de deletar → caixa → **Ok** (derivado do
  título por `(-76,+172)`).
- **SÓ ABAIXO DA LINHA DE ABAS** "Item | Quest | Arrange | Ext." — acima é
  equipamento em uso; sem achar a linha, **não apaga nada**.
- `data/templates/deletar/` é a **LISTA BRANCA única** (PNG autoriza, tirar
  revoga), relida a cada chamada. A tecla do inventário é interruptor ⇒ o estado
  é **LIDO antes**; `None` não é "aberto".
- Gatilho `AppConfig.apagar_lixo_a_cada` (padrão 10, `0` = nunca). **CAMPO NOVO
  EM `AppConfig`/`AccountSettings` PRECISA ENTRAR NO `_app_from_dict` /
  `_settings_from_dict`** (travado por `tests/test_config_ida_e_volta.py`).
- **AFERIÇÃO ANTES DE CONFIAR** (`bot/app/afericao.py`): fotografa o que seria
  apagado sem clicar. Deletar não tem desfazer.

## Time do APP — `docs/decisoes/time-do-app.md`

A mesma macro rodando em até cinco contas (um líder + `MAXIMO_DE_SEGUIDORES_DO_TIME`
seguidores). Pedido do usuário em 27/08/2026.

- **QUEM MONTA O TIME É O LÍDER.** `AppConfig.time_logins` só tem efeito na
  conta que o preencheu. Conta que aparece na lista de outra é SEGUIDORA, e o
  time dela própria é ignorado enquanto isso — é essa regra única que impede o
  nó de A liderar B enquanto B lidera A.
- **SÓ A MACRO É EMPRESTADA**: as 20 linhas, os delays e
  `espera_depois_do_tab_ms`. **NUNCA** `_base_pos_x`/`_base_pos_y` (é a
  coordenada DAQUELE personagem — copiar manda o seguidor andar para o mapa
  errado) nem `KeyBinds.next_target` (descreve o teclado daquele cliente).
- **O EMPRÉSTIMO É EM TEMPO DE EXECUÇÃO.** O `config.json` do seguidor não é
  reescrito. Nenhum caminho do time pode gravar a macro do líder em outra conta.
- **NINGUÉM FICA PARADO ESPERANDO.** A largada tem TETO: quem não chega a tempo
  segue batendo sozinho e entra na próxima largada que alcançar. Barreira sem
  teto é proibida — um seguidor curando deixaria os outros parados.
- **`bc_farm` E APP NUNCA JUNTOS.** Conta farmando a cave não aparece na escolha
  do time e não é convocada. Convocar arrancaria a conta do meio de uma run
  (teleporte gasto, boss vivo) — run perdida em silêncio.
- **SAIR DO TIME POR `bc_farm` NÃO APAGA O LOGIN** de `time_logins`. O clique é
  reversível; apagar configuração por causa dele, não.
- **CAMPO NOVO DO `AppConfig` PRECISA ENTRAR NO `_app_from_dict`** — vale para
  `time_logins`/`time_modo` como para qualquer outro (travado por
  `tests/test_config_ida_e_volta.py`).
- **`time_modo` fora de `MODOS_DO_TIME` nunca entra**: a normalização é feita
  nos DOIS lados (leitura do config e ponte web), como o piso de 100 ms.
- **O TAB NÃO EXISTE PARA TROCAR DE ALVO, e sim para conseguir um.** Ele sai
  quando FALTA alvo: o mob caiu (saiu de batalha), não há id, ou a memória não
  responde. Ter alvo e não estar em batalha **não** é motivo — a luta pode
  ainda não ter começado. Rede de segurança contra o mob inalcançável:
  `VOLTAS_SEM_BATALHA_PARA_TROCAR`. Vale COM e SEM time.
- **Nos modos `copiar` e `largada` a volta do time é CEGA**: TAB → macro e nada
  mais. Sem conferir alvo no meio, sem cortar a volta na saída de batalha. Não
  é só simplicidade: a sincronia só se sustenta se a volta de todas as contas
  durar o MESMO tanto, e cada conferência acrescenta tempo a uma e não às
  outras. No `mesmo_alvo` as conferências ficam — é a morte do alvo que faz o
  líder virar a volta e o time pegar o mob seguinte junto.
- **Cada comparação de `TARGET_ID` no alinhamento vai para o log.** É a única
  via de descobrir por que o alinhamento falha; o valor comparado é o de
  `TARGET_ID_ADDR` (`core/target_hybrid`), lido da memória de cada cliente.
- **O SEGUIDOR NÃO DORME O DELAY DELE** — só o piso. Quem dá o ritmo é a marca
  da linha do líder. Dormir o próprio delay ALÉM de esperar a marca é o que
  fazia a defasagem ser preservada volta após volta (medido: 13 s estáveis).
- **A marca é comparada com `>=` sobre `(época, volta, linha)`** — marca já dada
  não faz esperar. É isso que faz o atrasado alcançar em vez de travar.
- **O teto do alinhamento tem de caber DENTRO do teto da largada.** Ele é
  derivado, não escrito à mão: com o alinhamento maior, o líder desiste antes
  de o seguidor alinhar e o modo `mesmo_alvo` nunca cumpre o que promete.
- **No `mesmo_alvo` o TAB de abertura da volta é VETADO** — ele trocaria o alvo
  que a largada acabou de alinhar.
- **`esperar_a_largada` devolve `False` SÓ para parar de verdade.** "Não
  consegui sincronizar" é sempre "vai assim mesmo" -- sincronia nunca derruba
  a macro nem cancela uma volta.
- **TODA espera da sincronia tem TETO**, e estourar o teto não cancela nada:
  quem não chegou segue batendo sozinho e entra na próxima largada.
- **A eleição do líder temporário é DETERMINÍSTICA** (maior `max_hp`; empate
  ou memória muda, ordem do login). Cada conta decide na própria thread: um
  sorteio daria respostas diferentes e o time teria DOIS líderes anunciando.
- **O número de volta comparado é o DO LÍDER** (`volta_do_time`), nunca o
  contador local de cada conta — eles divergem assim que alguém perde uma
  largada.
- **Os tempos da sincronia são PROVISÓRIOS** (`bot/app/sincronia.py`), por
  decisão do usuário: rodar primeiro, medir pelos logs depois. Todo número lá
  é declarado como provisório e a classe registra o que a medição precisa.
- **O MURAL MORA EM UM LUGAR SÓ** (`bot/mural.py`). Ele é o quadro de avisos
  entre as contas do MESMO processo, e é usado pelo time do jogo (BC) e pelo
  time do APP. Duplicá-lo cria dois dicionários de batidas: o reseter bate num
  e o farm consulta o outro, e a conta espera para sempre na porta da cave sem
  erro nenhum. Travado por `tests/test_ecossistemas.py`.
- **Os três quadros do mural compartilham um lock de propósito** — convite e
  aceite são as duas pontas da MESMA conversa. Separar os mutexes muda a
  exclusão mútua entre elas sem alterar função nenhuma.
- **A PyQt6 NÃO conhece o time** (congelada em 27/08/2026). A exceção é uma
  lista fechada em `tests/test_app_config_campo_por_campo.py`
  (`CAMPOS_SO_DA_WEB`) — não é permissão para novos campos ficarem fora da GUI.

- **`TARGET_ID` EM ZERO NO MEIO DA MACRO CORTA A VOLTA.** Zero é o jogo dizendo
  "não há nada selecionado" — o mob morreu e o cliente limpou o alvo, ele sumiu
  de vista, ou uma janela roubou a seleção. As linhas que sobram sairiam para o
  vazio. Conferido a CADA linha, porque é a leitura mais barata do bot (~1 µs).
  `None` não corta: sem leitura o modo cego roda a macro inteira, como sempre.

## A Fada — `docs/decisoes/fada.md`

A conta marcada como `Fada` que, **em time**, cura em vez de atacar. Fora de um
time a flag não faz nada.

- **A VÍTIMA AVISA, a Fada não adivinha.** Quem lê a vida é o próprio
  personagem, pela memória. A Fada nunca decide quem curar olhando barra de
  tela.
- **ALVO ALIADO NÃO É ALVO.** A tecla de auto-seleção deixa a conta com ELA
  PRÓPRIA selecionada, e a regra "TAB só quando falta alvo" via um alvo
  válido: a conta nunca mais TABava e rodava a macro contra nada (medido em
  campo, 01/09/2026). Toda conta EM TIME pergunta ao mural se o alvo atual é
  de alguém do time — e, se for, TABa. Fora de time a pergunta não existe.
- **DEPOIS DA AUTO-SELEÇÃO, TAB.** O id é publicado e o alvo é largado no
  mesmo passo. Publicar sem largar é deixar a conta presa em si mesma.
- **QUEM IDENTIFICA A VÍTIMA É O SLOT**, lido da memória — o `TARGET_ID`
  publicado é REDE, não portão. Ele só recusa a cura quando existe E não
  bate (aí há prova de que o clique pegou outra pessoa). Exigi-lo para curar
  fez a Fada clicar 357 vezes sem curar ninguém: portão que falha fechado é
  pior que portão nenhum.
- **NENHUMA VÍTIMA LEVA MAIS QUE `MAXIMO_DE_TENTATIVAS_POR_VITIMA` CLIQUES.**
  A contagem é POR VÍTIMA, e quem estoura sai da fila e se vira com poção.
  Sem esse freio, qualquer defeito de seleção vira centenas de cliques — e
  o personagem sai andando.
- **A LEITURA DO ALVO SÓ VALE ~150 ms DEPOIS DA AÇÃO.** Medido: 36 a 123 ms
  entre o clique e a memória virar. Perguntar antes disso lê o alvo ANTERIOR.
- **A FADA FICA FORA DA LARGADA**, da macro e da sincronia. Contá-la como
  membro trava o time esperando uma confirmação que nunca vem.
- **AS DUAS BARRAS SÃO A RÉGUA ÚNICA, seja qual for o método.** A primeira diz
  QUANDO precisa de cura (Fada ou poção, tanto faz); a segunda, QUANTO precisa
  atingir para voltar a rodar a macro. Em time valem as do LÍDER; fora de time,
  as da própria conta. A constante fixa de 30% deixou de mandar.
- **A VÍTIMA SENTA NO PONTO INICIAL para esperar a Fada, e NÃO LEVANTA.** Antes
  ela esperava de pé, puxando mob.
- **SENTAR NÃO É UMA TRAVA — o bot SÓ SENTA, nunca aperta a tecla para
  levantar.** Sentado o personagem ataca e age livremente; o estado sai sozinho
  na primeira ação, e o que ele faz é AUMENTAR a regeneração base de vida e de
  mana (regra do jogo, usuário, 01/09/2026). Levantar é pior que inútil: perde a
  regeneração, e como a tecla é interruptor pode SENTAR o personagem na hora de
  reagir. A única leitura de `is_sitting` que sobrou serve para não apertar a
  tecla com ele já sentado. O porquê, e o erro que se repetiu duas vezes, em
  `docs/decisoes/cura-no-app.md` (seção "O bot SÓ SENTA").
- **TENDO FADA DE PÉ, ELA É A ÚNICA FONTE DE CURA DO TIME.** A poção só volta
  quando ela para de bater no mural.
- **A BATIDA SAI DE TODA ESPERA**, não só do topo do laço. Ela ficava só lá, e
  a Fada não volta ao topo enquanto cura: a vítima via 5 s de silêncio e bebia
  poção **enquanto estava sendo curada** (medido em campo, 6 s entre as duas
  linhas do log). Se ela está esperando, está viva — e é a espera que prova.
- **BOLSA E PET SÓ COM A FILA VAZIA E FORA DE BATALHA**, e com CADÊNCIA — não
  a cada giro do laço. A condição é conferida antes de CADA um dos dois, e não
  só na entrada: abrir o inventário com alguém esperando cura mata o alguém.
- **SEM TECLA DE PET, NEM PET NEM BOLSA.** Fada sem pet não cata item, então
  não tem lixo para apagar. Uma condição só porque é a mesma causa.
- **ANTES DE SENTAR, PERGUNTA À MEMÓRIA — e vale para todo lugar que senta.**
  A tecla é INTERRUPTOR: apertá-la com o personagem já sentado o faz LEVANTAR.
  Controle interno não basta, porque ele descreve o que o BOT fez e não o que
  aconteceu: um golpe levanta o personagem sem passar pelo bot, e um relogin
  devolve o estado sem avisar. Já sentado ⇒ não faz nada. Sem leitura, o
  controle interno é tudo o que há.
- **A FADA NÃO FAZ SHUFFLE ANTI-AFK.** Ele mora no executor de macro, e ela
  não roda o executor. A ausência é deliberada: ela passa a sessão parada.
- **EM BATALHA ELA CUIDA DE SI**, não da fila: seleciona-se e cura até sair.
  O time só protege quem está atacando, e quem espera cura não está — a
  proteção com que ela contava não existia na hora em que ela precisava. Quem
  avisa o time é a BATIDA, que carrega o estado de batalha junto.
- **QUEM ESPERA CURA VOLTA À MACRO enquanto a Fada estiver em batalha.**
  Atacando, o time mata o que está batendo nela — é a forma mais rápida de ela
  voltar a curar.
- **MORTO NÃO É CURADO** e para de rodar o APP (só em time). A Fada ignora e
  segue para o próximo.
- **O PONTO INICIAL DO TIME É O DO LÍDER** — isto INVERTE a regra anterior, e a
  inversão tem trava: só adota se estiver no MESMO MAPA. `_voltar_para_base`
  anda pelo minimapa, e destino fora do raio útil vira clique na borda: no mapa
  errado o personagem anda contra a parede indefinidamente.
- **A GEOMETRIA DO PAINEL É DERIVADA**: primeiro retrato em (28,204) e um passo
  fixo. Nunca cinco literais soltos. O painel encolhe por baixo, e quantos
  slots varrer é "membros − ela" — mas quem confirma é a memória, não a conta.

## HH (Black Wind Camp Dungeon) — `docs/decisoes/hh.md`

> **Terceiro ecossistema, aberto em 01/09/2026.** Integração do bot de terceiros
> em Lua/UoPilot (`OutrosBots/HH - cave full - ARVV3N`). O **porquê** de cada
> item, incluindo o que daquele bot foi REPROVADO, está em
> `docs/decisoes/hh.md`.

### O que NÃO pode ser violado

- **`hh/` NUNCA importa de `bc/` nem de `app/`**, e o contrário também não.
  Travado por `tests/test_ecossistemas.py`, que agora cruza TODOS os pares de
  ecossistema — pasta nova ganha as verificações de graça.
- **TODO IMPORT RELATIVO TEM QUE APONTAR PARA ALGO QUE EXISTE** (02/09/2026,
  `test_todo_import_relativo_aponta_para_algo_que_existe`). É a trava que faltava
  para o refactor de pastas: o teste acima só pergunta *"importa de outro
  ecossistema?"*, e um import que aponta para o VAZIO não cita ecossistema
  nenhum. **Medido:** o `cd2ef2b` subiu `bc/ui_service.py` para
  `bot/ui_do_jogo.py` levando junto um `from . import mapa_bc` escrito dentro de
  uma função — na casa nova o `.` virou `bot/`, onde `mapa_bc` não existe. Como
  o import era LOCAL, o módulo carregava, o bot arrancava e a suíte passava; o
  erro só nascia quando o personagem chegava no ponto e ia clicar num NPC.
  Resultado no log de 02/09: **42 `cannot import name 'mapa_bc'` seguidos** em
  `ENTRAR_NO_COVIL` — o bot dizia "Usando o Altar Stone para entrar no covil" e
  estourava 1 ms depois, sem soltar o clique direito. `sair_da_cave` e a entrada
  da HH usam a mesma função e estavam quebradas do mesmo jeito, ainda sem
  ninguém ter visto. O mesmo teste achou um segundo caso na mesma hora:
  `vendedor.py` com `from ...core.vision` (um nível a mais, sobra da subida de
  `bc/vendor.py`).
- **QUEM SOBE PARA `bot/` PERDE O DIREITO A `mapa_bc`.** `bot/` serve todos os
  ecossistemas: reapontar aquele import para `bc/mapa_bc` teria consertado o
  sintoma e criado a dependência que a pasta existe para proibir. O certo era o
  `core` — `mapa_bc.distancia` já era só um reexport de `core.rota.distancia`.
- **NADA é recriado.** Diretiva do usuário (01/09/2026): *"tudo que já existir no
  nosso BlazesBot você não precisa recriar, apenas utilizar onde necessário."*
  Combate, navegação, painel de arredores, venda, catador, deletador, pet,
  esconder jogadores, time e mural JÁ EXISTEM — a HH usa, não reescreve.
- **Os 66 waypoints são o único ativo insubstituível.** Vieram do bot Lua que
  roda esta cave hoje, em produção. Travados por `tests/test_mapa_hh.py`:
  contagem por trecho, continuidade, clique calibrado em todos, e o ponto de luta
  igual ao último waypoint do trecho.
- **O `via` (clique calibrado) é RESERVA, nunca via principal.** Quem anda é o
  motor de navegação, que calcula a partir da posição ATUAL e sabe destravar. Um
  clique fixo foi calibrado numa posição e, usado de outra, aponta para o lugar
  errado. Ver `core/rota.py`.
- **A área interna da HH está medida em 2 dos 66 waypoints**; o resto vale o
  marcador `AREA_INTERNA_NAO_MEDIDA`. Medidos em 03/09/2026, nos prints do
  usuário: `Happiness Hall Dungeon` em (55,33) e `Happiness Hall Main Hall` em
  (529,118) — e eles provam que **o interior NÃO é uma área só**. Quem depender
  de área tem de tratar a ausência; nome novo só entra junto com a linha que diz
  de que print ele saiu, e o inventário (`mapa_hh.areas_medidas()`) é travado
  por `test_a_area_interna_continua_marcada_como_nao_medida`. Consequência
  prática, inalterada: a retomada de rota da HH volta ao waypoint mais próximo e
  **não** recua para o início da área — recuar sobre um marcador devolveria o
  personagem ao waypoint 1 da cave a cada escorregão.
- **`Memory.location()` NÃO distingue dentro de fora da HH.** Ele devolve
  `Black Wind Camp Dungeon` nos dois lados — medido no log de 03/09/2026, 673
  menções e uma única string. Os nomes `Happiness Hall *` são rótulo da **TELA**
  (`ROTULO_DE_TELA_DA_CHEGADA`, `AREA_DA_SAIDA`) e **não podem ser comparados**
  com o que o ponteiro devolve. Travado por
  `test_os_nomes_de_Happiness_Hall_sao_da_TELA_e_nao_do_PONTEIRO`.
- **A ETAPA DA VIAGEM SAI DE NOME + COORDENADA** (`mapa_hh.etapa_pelo_lugar`),
  e a divisão é fixa: a **coordenada** responde "dentro ou fora", o **nome**
  responde "quão longe da cave, do lado de fora". Nenhum dos dois sozinho — o
  nome não separa dentro de fora, e a coordenada não separa as etapas de fora
  porque o teleporte da Fay espalha o ponto de chegada. Lugar desconhecido cai
  em `ETAPA_LONGE` (viagem completa): "não sei" custa uma viagem, nunca um
  clique no lugar errado.
- **"Estou dentro" é respondido pela COORDENADA, não pelo nome do lugar**
  (`mapa_hh.esta_dentro_da_hh`: X e Y positivos). É o que o bot em Lua já fazia
  e o que o usuário confirmou em 03/09/2026 — e é obrigatório, porque o interior
  tem mais de um nome de área. O par de chegada é sempre **(55,33)**, padrão do
  jogo.
- **OS TEMPLATES DA ENTRADA ESTÃO PRONTOS** (03/09/2026) e moram em
  `data/templates/` — não em `entrada/`, que é a pasta de EVIDÊNCIA. Falta um
  só: `link_sell_item.png`, e sem ele apenas a VENDA recusa.
- **Template tem que ser RECORTE, não tela.** O primeiro `link_enter_hh.png`
  entregue tinha 1029×804: um template do tamanho da tela casa em qualquer lugar
  e não localiza nada. Travado por
  `test_o_template_e_um_RECORTE_e_nao_uma_tela`.
- **A CÂMERA vai para a pose padrão antes de todo clique posicional** — preparo
  da run, cada trecho de waypoints, a ida da Fada à porta e a ida ao vendedor.
  Os `via` calibrados de cada waypoint foram medidos nessa pose, e é nas curvas
  onde o cálculo falha que eles entram.
- **A coordenada de link de diálogo NÃO transfere entre NPCs.** Medido:
  o `vendor_sell_tab` da BC cai 35 px abaixo do "Sell Item" do vendedor da HH,
  porque a posição dos links depende de quantas linhas o NPC escreve antes deles.
  Link de diálogo se acha por IMAGEM — `_onde_clicar_no_link_de_vender` é gancho.
- **`Happiness Hall` é o nome da INSTÂNCIA, não do lugar.** A zona é
  `Black Wind Camp Dungeon`, que é o que a memória devolve. Confundir os dois
  faria a validação de lugar rejeitar a leitura.
- **A HH e a BC nunca rodam juntas.** O despacho é `APP → HH → BC`, com ordem
  fixa: marcar as duas roda a HH, e o log diz isso. Ligar a HH com o BC rodando
  devolve o controle no próximo ponto seguro.
- **O destino do Fay é `West Suburb of Stone City`, e ele SÓ APARECE ROLANDO a
  lista.** A rolagem é um PASSO conferido pelo aparecimento do link — nunca um
  número fixo de cliques na seta. Clique cego na seta é o vício do bot Lua.
- **Não se clica de fora do ponto de conversa.** O painel de arredores caminha
  até PERTO da `Mutual Quest Woman` (-358,-289); a conversa é em (-342,-288). É o
  mesmo defeito já medido na BC em 25/08/2026, quando o clique a 2 passos pegou o
  White Eagle.
- **A cave PRECISA de reset** (regra do jogo): sem desfazer e refazer o time os
  bosses não renascem. Dois modos: **HH solo** (igual à BC — reset aceita, o farm
  entra, o time é desfeito) e **HH + Fada** (as duas entram, a Fada acompanha e
  cura, e o desfaz-refaz acontece FORA, depois de sair).
- **A Fada é uma peça só, em `bot/fada.py`.** Ela cura de onde está e não sabe
  andar. Quem viaja, entra na cave e segue o líder é `bot/hh/fada.py`, que a
  COMPÕE: um giro do laço de cura (`_uma_volta`) é chamado de dentro do laço de
  seguir. **As duas na MESMA volta** — dois laços concorrentes na mesma conta
  seriam duas mãos no mesmo teclado.
- **No modo HH+Fada, o ciclo de time é do LÍDER.** A Fada só acompanha. Duas
  contas decidindo desfazer o mesmo time é uma corrida cujo resultado é um time
  desfeito no meio da cave.
- **A tecla de SEGUIR nasce vazia**, porque o cliente não tem atalho padrão para
  o follow. Vazia = não configurada: a Fada avisa uma vez e continua curando de
  onde está. Chutar um padrão faria ela apertar algo que faz outra coisa.
- **O vendedor é o `Roaming Apothecary`, fora da cave** — a venda da BC com outro
  NPC. Isso é dado de rota, não módulo de venda novo.

#### O que a sessão de 04/09/2026 fixou — o porquê medido em `hh.md` §13

- **`FarmDesligado`, `StopRequested` e `Disconnected` são tratados ANTES do
  `except Exception`** no laço da HH. Ordem de `except` aqui é semântica: o
  geral na frente engoliria os três sinais que não são defeito. `Disconnected`
  pode ser capturado, mas só para `raise` seco.
- **Nenhum clique de entrada sai depois de o personagem já ter entrado.** O par
  de cliques não é atômico (180–420 ms de espera do diálogo no meio), e dentro
  da cave o mesmo ângulo é o NPC de SAÍDA — o bot entrava e saía na mesma volta.
  A conferência é ENTRE os dois cliques (`ainda_vale`), não só antes do par.
- **Cave sem alvo proibido é caso legítimo.** `NOME_DO_ALVO_PROIBIDO` nasce
  `None` e só a BC o preenche; sem nome, o veredito é `bate` e **não**
  `acabaram` — `acabaram` encerraria a luta na primeira leitura, sem um golpe.
- **Toda rotina com `Navigator` + `CombatEngine` LIGA `destravar_o_combate`.**
  Sem isso o portão da montaria detecta a batalha e só sabe insistir na tecla
  contra uma recusa do jogo. Custou 41 s à HH e 24 min à BC, em datas
  diferentes, pelo mesmo motivo.
- **Fora do ponto do boss e EM BATALHA: mata, não anda.** Voltar para
  `ATE_O_BOSS` exige montaria, e em batalha o jogo recusa montar — é beco sem
  saída. `in_battle() is True`: ilegível não autoriza sair batendo.
- **No meio da cave só a MONTARIA é garantida.** Buff, poção e comida exigem
  estar a pé, e a pé no meio da cave é o trem de mobs encostando. O portão é
  `acabei_de_entrar` (55,33 ± `rota.NA_ROTA`).
- **A saída não clica de fora do ponto.** (527,124) e clique (626,526),
  remedidos em 04/09 porque a montaria entrava na frente do NPC. Sete unidades
  de folga bastam para o clique pegar OUTRO NPC que fica por perto.

#### O que a sessão de 03/09/2026 fixou — o porquê medido em `hh.md` §12

- **FORA DA CAVE NÃO SE PREPARA NADA QUE EXIJA ESTAR A PÉ.** Buff, poção e
  comida de pet moram em `PREPARAR_DENTRO`. Regra do usuário, e é a mesma que a
  BC segue desde 25/08/2026: montado o jogo IGNORA a tecla sem devolver erro, e
  entrar é disputado — durante a espera o personagem regenera de graça. **A
  única exceção é o PET**, conferido uma vez ao CHEGAR na porta, e **fora** do
  laço de tentativas (a rajada pode dar centenas de leituras por minuto).
- **O PET é conferido nos DOIS lados da tela de carregamento** — na porta e no
  preparo de dentro. A repetição é de propósito: é ali que ele some.
- **A CURA TEM TRÊS MOMENTOS, e só três:** a entrada (`curar_ao_entrar`), o
  top-up antes de encostar em cada boss (`curar_antes_do_boss`), e a
  emergência. Sentar entre os bosses foi REMOVIDO — era o terceiro no mesmo
  ponto, e sentar já tinha sido medido e reprovado na BC.
- **PARA CURAR TEM QUE ESTAR FORA DE BATALHA, e a saída é MATANDO**
  (`limpar_o_combate`). Escolha do usuário entre pular, esperar e matar. A
  emergência usa `potions.emergency_pct`, **não** o limiar normal: os mobs da HH
  são fracos e o normal faria a run passar o tempo bebendo. Não sair de batalha
  no teto **não trava** — a cura fica para a volta seguinte.
- **A NATUREZA DE CADA PONTO MORA NO MAPA, e a rotina obedece.** Não pode haver
  `if rotulo == "..."` na rotina. Pontos 1 e 3 são pacotes de mobs **ranged**:
  sem AoE (a skill de área é de curta distância e passa embaixo deles) e com o
  ritual `limpar_o_combate`. Pontos 2 e 4 são boss, com AoE e
  `lutar_contra_um_boss`.
- **O TAB de um ponto tem UM dono.** Zero no pacote porque quem o dá é o próprio
  `limpar_o_combate`; zero no boss único porque trocar de alvo perde dano; dois
  na Dupla porque sem ele o segundo boss nunca é adquirido.
- **CINCO SEGUNDOS PARA ENGAJAR, em qualquer ponto de batalha — inclusive o do
  boss.** Não engajou, o bot segue. É o que torna barato refazer um trecho
  depois de uma morte. **Custo aceito pelo usuário e registrado:** um boss vivo
  que demore mais de 5 s é pulado, e o log diz isso em voz alta.
- **VOLTA-SE AO PONTO depois de matar.** Mob ranged não vem até o personagem, e
  começar o trecho seguinte fora do waypoint faz a retomada escolher índice
  errado.
- **O PROGRESSO DOS BOSSES É VOLÁTIL E ZERADO AO SAIR DA CAVE.** O desfaz-refaz
  do time ressuscita os quatro; lembrar entre entradas faria o bot pular sala
  cheia. Dentro da mesma ida, a retomada respeita o **trecho em andamento** — os
  quatro trechos se cruzam no mapa, e escolher pela distância refaria bosses já
  mortos.
- **CAIR NÃO PODE JOGAR FORA O PROGRESSO DA RUN.** `RECUPERAR` não zera o
  trecho; quem decide por onde continuar é `_retomar_dentro_da_cave`.
- **A RAJADA DE ENTRADA É A DO BC**: uma hora de teto, 25 ms entre tentativas,
  confirmação de 0,25 s, volta à coordenada ao derivar, e redescoberta do NPC
  **só** na falha mecânica (instância cheia é a razão normal de não entrar).
  Estourar o teto volta para `ATE_A_PORTA`, não para `RECUPERAR`.
- **SAIR DA CAVE É FALAR COM O `Servant Child`**, achando "Leave Happiness Hall"
  por template e confirmando pela POSIÇÃO (-342,-288). Andar até (529,119) e
  declarar a run concluída deixava o personagem dentro. Os três cliques cegos do
  Lua estão REPROVADOS: clique que erra o NPC cai no chão, e clique no chão faz
  o personagem andar para fora do ponto de onde o NPC é alcançável.
- **`WAYPOINTS_QUE_BLOQUEIAM` ≠ `WAYPOINTS_PROBLEMATICOS`.** O primeiro é sobre
  MOBS que barram a passagem (só (232,188) hoje, e só se limpa **se o combate já
  começou**); o segundo alarga a tolerância onde a geometria não deixa encostar.
  Valem para o mesmo ponto hoje, e é por isso que misturá-los seria fácil e
  errado.

### Promoções que a HH forçou — dependência cruzada

Mexer nestes mexe nos DOIS ecossistemas:

**MEXER EM QUALQUER UM DESTES MEXE NAS DUAS CAVES.** Todas feitas em
01–02/09/2026.

| módulo | veio de | o que NÃO subiu, e por quê |
|---|---|---|
| `core/rota.py` | `bc/mapa_bc.py` | as rotas em si (dados de duas caves diferentes) e o reconhecimento de lugar da BC (caixa da cave) |
| `core/stone_city.py` | `bc/mapa_bc.py` | o **Rich Man** — vendedor é escolha do ecossistema, não da cidade |
| `bot/navegacao.py` | `bc/navigation.py` | as rotas, as áreas apertadas, os textos de busca |
| `bot/ui_do_jogo.py` | `bc/ui_service.py` | quais NPCs, quais links, quais coordenadas |
| `bot/combate.py` | `bc/combat.py` | as FASES, a trava do Cemetery Guard, o Package Courage |
| `bot/vendedor.py` | `bc/vendor.py` | o Rich Man, a volta para a cidade (pedra/token), a compra de suprimentos |
| `bot/hotbar.py`, `bot/velocidade.py` | `bc/` | nada — subiram inteiros, sem alteração |
| `bot/fada.py` | `bc/`→ não: de `app/fada.py` | o DESLOCAMENTO — esta Fada cura de onde está; quem viaja e segue é `bot/hh/fada.py` |

### O CRITÉRIO, e ele é uma pergunta só

*O que este módulo IMPORTA?*

- não importa nada de `bot/` ⇒ cabe no **`core/`** (`rota`, `stone_city`);
- recebe `BotContext` ⇒ vai para **`bot/`**, porque `core/` importar de `bot/`
  inverteria a dependência e tiraria a reusabilidade do core.

**"Parece genérico" NÃO é o critério.** O relatório inicial da HH mandou
navegação, combate e UI para o `core/` exatamente por esse raciocínio, e estava
errado — os três recebem `BotContext`. Ver `docs/decisoes/hh.md`, seção 8.0.

### Como um ecossistema pede um dado da cave a um motor compartilhado

**INJETA, nunca importa.** Travado por
`test_o_sistema_nao_depende_de_ecossistema_nenhum`, que reprova qualquer arquivo
de `bot/` que importe de `bc/`, `app/` ou `hh/`. O supervisor é a única exceção,
porque ESCOLHER qual ecossistema roda é a função dele — e um segundo teste trava
essa lista em um nome só.

Três formas, todas em uso:

| forma | exemplo | quando |
|---|---|---|
| o mapa no construtor | `Navigator(ctx, mapa_hh)` | o motor pergunta uma coisa ao mapa (`tolerancia_do_waypoint`) |
| atributo de classe | `NOME_DO_ALVO_PROIBIDO` | a resposta é um dado, e `None` é resposta válida |
| gancho com padrão neutro | `_esta_fora_da_cave()`, `_no_ponto_do_vendedor()` | a resposta exige lógica; o padrão nunca bloqueia |

E o padrão neutro é regra: **"não sei" não bloqueia.** Não curar dentro da cave
mata o personagem; um desmonte a mais fora dela custa alguns segundos.

### A armadilha da reexportação — medida, não teórica

`from ..combate import USAR_IMAGEM_DA_FASE_2` **copia o valor no import.** Trocar
o interruptor no motor não chega ao ecossistema, e ele segue com a cópia, em
silêncio. Foi o que `test_desligado_nao_le_a_tela` pegou: a leitura de tela
desligada no motor continuou acontecendo.

**Interruptor entra QUALIFICADO POR MÓDULO** (`combate.USAR_IMAGEM_DA_FASE_2`),
para existir um valor só. A forma `X as X` só vale para nome que não muda em
tempo de execução — classe, função, constante de dado.

**`core/` vs `bot/` não é escolha de gosto.** `core/rota.py` é função pura sobre
coordenadas e cabe no `core/`. Navegação, combate e UI recebem `BotContext`, que
mora em `bot/` — pôr no `core/` inverteria a dependência e tiraria a
reusabilidade do core, e `tests/test_ecossistemas.py` reprova. `bot/` é a camada
que o `CLAUDE.md` já define como *o SISTEMA — serve todos os ecossistemas*.

**Cada mapa injeta seus dados, a regra é uma só.** `mapa_bc.onde_retomar` e
`mapa_hh.onde_retomar` são invólucros de uma linha sobre `core.rota.onde_retomar`.
A BC passa `AREAS_APERTADAS`; a HH **não passa**, porque a área dela é marcador —
e mandar o bot voltar ao início da área sobre um marcador o devolveria ao
waypoint 1 da cave a cada escorregão.

## Fechar painel dentro do jogo — `docs/decisoes/memoria-primeiro.md`

Vale para qualquer ecossistema que decida limpar a tela do jogo.

1. **NUNCA aperte ESC uma quantidade fixa de vezes.** O ESC **alterna**: com
   painel aberto ele fecha, com a tela **limpa** ele **ABRE o menu do sistema**
   — medido seis vezes seguidas, sempre o mesmo nó (`0` ↔ `0x15142AB0`). Um
   "aperta 3× para garantir" deixa o jogo pior do que achou.
2. **PERGUNTE depois de cada tecla** — `Memory.algum_painel_aberto()` — e pare
   no instante em que ela devolver `False`.
3. **`False` NÃO prova tela limpa.** É sinal de **uma via**: `True` é certeza,
   `False` é "nenhum dos quatro sinais acusou". Quem tratar esse `False` como
   prova volta a errar calado, que é o defeito que a memória vem eliminar.
4. **`system_menu_open()` NÃO vê o menu do ESC** — diz `False` com ele aberto.
   Não use esse leitor para concluir nada sobre o menu do sistema.

## Estado atual relevante — as REGRAS

Cada item é o que **não pode ser violado**. O detalhe de cada área mora em
`docs/REGRAS.md`; o porquê medido, em `docs/decisoes/`.

### Pet (obrigatório)

- Verificado e invocado **NO INÍCIO** de cada execução de farm BC (após venda
  inicial, antes do loop). `ensure_pet()` também roda no PREPARAR e após reviver.
  Respeita `settings.pet.summon_on_login` (padrão True).
- Alimentação respeita `feed_on_start`: False (padrão) ⇒ cronômetro inicia sem
  alimentar. `_last_feed` começa em `None` (nunca alimentou), não `0.0`.
- **Trava de posição no APP** (`AppConfig.travar_posicao`, padrão True): salva a
  posição como base; andou > `TOLERANCIA_POSICAO` (1) ⇒ devolvido andando pelo
  minimapa. Só com memória respondendo.
- **A COLEIRA DOS 12 PIXELS — o afastamento é conferido A CADA LINHA da macro,
  não só no prelúdio** (04/09/2026, `MAXIMO_DE_PIXELS_DO_PONTO = 12`). Passou do
  teto ⇒ a volta é CORTADA na hora; quem anda de volta é a trava de posição do
  prelúdio seguinte, e ela continua sendo o único lugar que caminha. Motivo do
  usuário: *"tem vezes que o jogo dá bug e dá target em um mob bem longe, só que
  com isso acaba chamando outros mobs e provavelmente vai morrer no caminho"* —
  antes disso o personagem só era trazido de volta no FIM da macro, chegando com
  a fila atrás. **Não confundir com `TOLERANCIA_POSICAO` (1)**: aquela é a folga
  do "já voltei", esta é o teto do quanto ele pode se afastar andando, e é maior
  de propósito. `None` (sem leitura de posição, ou trava desligada) **não corta**.
- O modo APP também alimenta o pet (`ExecutorDeMacro.feed_pet` via `PetFeeder`).
- **A GRADE DA COMIDA É A MESMA NOS DOIS ECOSSISTEMAS, E VEM DO DISCO** — 27/08/2026.
  BC e APP constroem o `PetFeeder` com `vence_em=settings.pet.proxima_comida_em`
  e passam um `gravar` que escreve nesse mesmo campo. O `PetFeeder` grava a cada
  mudança da grade, **inclusive quando ela apenas NASCE**. Sem isso o APP
  re-ancorava o vencimento a cada reinício e **nunca** alimentava — medido: 12
  reinícios em 88 min, zero refeições em 123 min, intervalo de 51.
- **A TECLA DA COMIDA NÃO SAI EM BATALHA, E A GRADE NÃO AVANÇA.** O jogo ignora
  o alimento em combate; avançar a grade com a tecla engolida deixa o pet um
  intervalo inteiro sem comer com o relógio dizendo que comeu. Vale nos dois
  ecossistemas. `in_battle()` é tri-estado: só `True` barra.
- **A COMIDA GARANTE A PÁGINA 1 DA BARRA ELA MESMA** e espera
  `SEGUNDOS_PARA_A_COMIDA_SER_USADA` antes de devolver — a ação seguinte
  (montar, ou a primeira linha da macro) CANCELA o uso do item.
- **TECLA QUE O `Input` RECUSA NÃO AVANÇA A GRADE** (erro de configuração vira
  `ERROR` + evento no diário, não refeição fantasma).

### Reset de time — `docs/decisoes/reset-de-time.md`

- **O RESETER SAI DE UMA LISTA FECHADA** de contas ativas com "aceitar convites
  de time"; fora deste processo ele é invisível, e sem observá-lo não há trava.
- **A BATIDA PROVA, NÃO DESCREVE:** `bater()` é a 1ª linha de
  `check_and_accept`, antes do cooldown — APP, login e farm caem fora sozinhos.
- **O PORTÃO É ÚNICO**, antes do `montar_time()`, esperando em `ctx.tick` (que
  mantém o watchdog desta conta vivo), sem teto. **"Caiu" espera; "não existe
  mais" desliga o `bc_farm` e avisa**, reavaliado a cada volta.
- **TIRAR UM RESETER DO AR É IMPEDIDO** nas duas interfaces.

### Sistema — `docs/decisoes/sistema.md`

- A parada **acorda quem espera** (fan-out em `BotManager.stop()`); o `tick()`
  espera no evento, não fatia `time.sleep`. `FATIA_DA_ESPERA` é a cadência do
  watchdog em esperas longas (não a latência do Parar, que é zero).
- `docs/INTERRUPTORES.md` é **GERADO** (`python -m
  blazesbot.core.indice_de_constantes`): 331 constantes. Editar lá não muda nada.
  `tests/test_indice_de_constantes.py` reprova valor antigo citado como
  `NOME = valor` — escreva história em prosa, deixe `NOME = valor` só para o
  valor de HOJE.
- Endereço estático do GhostBot é da v6139; `core/rebase.py` mede candidato
  **+0x60** e só troca quando o candidato responde e o atual não.
- Pino de janela `(hwnd, pid)` por conta (`last_hwnd`/`last_pid` no `config.json`,
  invisível). Nick lido na memória vale mais; nick diferente ⇒ apaga o pino.
- Log em dois ambientes (`BLAZES_MODO` = `dev` | `prod`); só em dev existe
  `logs/dev/blazes-dev.jsonl`.
- A barra de atalhos tem que estar na **PÁGINA 1** (`bot/bc/hotbar.py`): clica,
  não lê (2 cliques bastam). No APP, garantida na largada e antes de cada volta.
- Desligar o BC pela interface é **IMEDIATO** e não derruba a conta (`bc_farm` →
  False levanta `FarmDesligado`).
- Rede de segurança: `./.venv/Scripts/python.exe -m pytest -q` e
  `-m ruff check blazesbot/ tests/ main.py`.

### Combate — `docs/REGRAS.md` (seção "Combate") + `docs/decisoes/combate.md`

- **COMECE POR `docs/decisoes/memoria-primeiro.md`.** A investigação do alvo
  TERMINOU em 25/08/2026 e aquele arquivo é o resultado.
- **NADA SOBRE O ALVO É AFIRMADO SEM LINHA DE LOG ATRÁS.** O que está MEDIDO /
  ABERTO / REFUTADO mora em `docs/decisoes/alvo-o-que-esta-medido.md`.
- **O ALVO INTEIRO VEM DA MEMÓRIA. A TELA É RESERVA.** Virada de 25/08/2026,
  e é a mudança mais importante desta área desde que ela existe. `alvo_atual()`
  devolve **nome, HP exato, nível e posição** numa leitura, sem captura.
- **O `0x0115CB80` É O ID DA ENTIDADE SELECIONADA — e a entidade carrega o
  MESMO id em `+0x8`.** É chave estrangeira, nunca foi enigma; veio do
  `search_id()` do GhostBot.
- **CONFIRMADO NUMA LUTA INTEIRA** em 25/08: onde memória e tela discordaram,
  **a errada era a tela** — e ela **erra calada**.
- **`hp == 0` É MORTE — MENOS NA FASE 1 DO BOSS**, que **para em `hp=1`** e
  some, nascendo a fase 2 como ENTIDADE NOVA (id novo, endereço novo, nível
  50 → 51). Não é caso a tratar: o boss nunca foi dado por morto por HP.
- **QUEM CONFERE HOJE É O `2-DIAGNOSTICO`** — as ferramentas de DESCOBERTA
  foram removidas. Se o jogo atualizar, é lá que aparece: id respondendo e
  entidade não achada ⇒ `ADDR_ENTITY_SCAN_BASE` andou; id sem responder ⇒
  `ADDR_TARGET_ID` andou.
- **O ATALHO DO PONTEIRO:** o SLOT do array muda durante a luta (30 → 29 → 28),
  o ENDEREÇO da entidade não — o caminho normal é UMA leitura conferindo o `obj`
  guardado; a varredura só roda quando o alvo troca.
- **A CADEIA DIRETA DO ALVO É COMPLEMENTO, NÃO SUBSTITUTO** (item 42, 31/08/2026).
  `Memory.alvo_hp_direto()` e `Memory.alvo_nome_direto()` entram em
  `alvo_atual()` como **fallback** quando a struct falha ou atrasa: a struct
  continua sendo a coluna vertebral porque é a única que tem `max_hp`,
  `obj`, `pos` e `nivel` — a cadeia direta só responde HP e nome. Trocar a
  struct pela cadeia é proibido: perderíamos posição e nível.
- **A FLAG `ha_alvo_selecionado()` DISTINGUE TRÊS ESTADOS** (item 42) que
  `id_do_alvo() != 0` confunde: sem mira / alvo normal da luta / id órfão
  de 8 a 11 s. Disponível para quem quiser usar; mexer no consumidor
  (`bot/bc/combat.py`) é assunto à parte, e exige placar de `alvo_morto_por_hp`.
- **A ENTIDADE PODE DEMORAR UM CICLO A APARECER** no array logo depois de
  selecionar (medido: 1 em ~45) — por isso a tela continua como reserva.
- **DESTRAVAMENTO: PRESO EM BATALHA, MATA MOB A MOB** (01/09/2026,
  `combat.limpar_o_combate`). Não é fase da run, é RESGATE — chamado de fora
  pelo portão da montaria, nunca pelo fluxo normal. A coreografia é do usuário e
  cada passo tem dente:
  - **UM alvo por vez, SEM AoE.** Área acerta quem está em volta e PUXA mob que
    não estava em combate — trocaria um travamento por outro.
  - **Morreu ⇒ PARA e olha a flag por `ESPERA_APOS_A_MORTE_ANTES_DO_TAB = 3.0`.**
    O TAB imediato depois da morte mira o mob seguinte e o golpe o puxa; a pausa
    é o que impede a bola de neve. Ela **sai antes** quando a saída confirma e
    **se estende** para completar `CONFIRMACAO_DE_SAIDA_DE_COMBATE` se a flag
    baixou perto do fim — cortar a confirmação gastaria um TAB à toa.
  - **`TETO_DO_DESTRAVAMENTO = 60.0`** ("no máximo atrasar 1 minuto", usuário).
    O prazo de cada mob (`LIMITE_POR_MOB_NO_DESTRAVAMENTO = 20.0`) é cortado
    pelo que sobra do teto, e o último TAB não sai se não houver rodada adiante.
  - **`False` NÃO encerra nada:** o portão da montaria continua insistindo e
    chama de novo. O teto limita quanto tempo o bot passa BATENDO, não quanto
    insiste em montar.
  - **AQUI o Cemetery Guard APANHA** (`DESTRAVAMENTO_BATE_NO_ALVO_PROIBIDO`).
    A trava abaixo existe para EVITAR puxá-lo; se o destravamento está rodando é
    porque o ESC e a espera já falharam — e foi essa espera que produziu os 24
    minutos. Sai WARNING e registro no diário. **Fora do destravamento a trava
    continua inteira.**
  - **Manutenção (poção/cura) roda DENTRO**, a cada 1 s, e morte do personagem
    encerra a rodada. O portão da montaria não tinha nenhuma das duas.
- **NOS GUARDAS, SÓ O CEMETERY GUARD PARA O GOLPE** (26/08,
  `SO_O_ALVO_PROIBIDO_PARA_O_GOLPE`): outro nome não para nada —
  rotaciona skill **até sair de batalha**. Cemetery Guard na mira ⇒ ESC (uma
  vez) e espera a saída, por UMA porta (`_travar_no_alvo_proibido`) que serve
  memória e tela. E o teto de TAB não barra a troca com a flag ALTA
  (`TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS`): TAB em cadáver era a outra porta do
  mesmo defeito. O portão de nome segue LIGADO (`USAR_PORTAO_DE_NOME`, ~3
  leituras de 4 bytes); `ilegivel` = NÃO SEI, e não sei nunca autoriza parar de
  bater nem gastar TAB.
- **SÓ A MEMÓRIA DECLARA MORTE; A TELA SÓ SABE DIZER "AINDA VIVO"**
  (`SO_A_MEMORIA_DECLARA_MORTE = True`). Assimetria de propósito: o
  `EnemyDead.png` tem falso positivo MEDIDO com o mob VIVO, e sem isso sobraria
  uma RESERVA capaz de declarar morte com um template que erra. "Não sei"
  **nunca gasta TAB**.
- **EXISTEM DOIS TABS NO BC, E SÓ UM É POR MORTE:** o do laço da luta
  (`atacar_ate_sair_de_combate`) e o de **ADQUIRIR o boss** que não engajou em
  `SEGUNDOS_ANTES_DO_TAB_NO_BOSS = 4.0` s — esse sai com o mob vivo por
  desenho. Travado por teste de AST.
- **A MESMA MORTE NÃO SAI DUAS VEZES.** A trava é por IDENTIDADE
  (`_ultimo_alvo_morto_id`), não por tempo — o cadáver fica selecionável 7 a 13 s.
- **A VIRADA PARA A FASE 2 É VISTA PELO ID DO ALVO** (a fase 1 morre e nasce
  outro Blaze Skull Marshal ⇒ alvo novo). O sinal da TELA (barra amarela)
  continua ligado ao lado; os dois levantam a mesma bandeira, que é latch.

### A TELA, que agora é a RESERVA — `docs/decisoes/combate.md`

Vale só quando a memória não achou a entidade, e continua inteira. As regras que
custaram medição estão no `docs/decisoes/combate.md`; o que não pode ser
violado:

- **A BARRA É LIDA NUM OFFSET FIXO MEDIDO, NÃO PROCURADA**
  (`USAR_OFFSET_FIXO_DA_BARRA`) — a UI do jogo não escala.
- **CONTA COLUNA, NÃO ÁREA**, e **SABE DIZER "NÃO SEI"** (`None`).
- **MORTE = BARRA VAZIA *E* `EnemyDead.png`**, e o marcador só é consultado
  abaixo de 10% — falso positivo medido com o mob VIVO. **Com a memória
  respondendo, ele não é consultado NUNCA.**
- **UMA CAPTURA POR LEITURA**, e o boss tem **duas barras sobrepostas**.

### Navegação — `docs/REGRAS.md` (seção "Navegação") + `docs/decisoes/navegacao.md`

- **NUNCA A PÉ DENTRO DA CAVE (regra permanente).** O portão da montaria
  INSISTE até a memória confirmar — não existe mais "andou a pé mesmo assim".
  Motivo do usuário: **a pé não se chega no last boss**, então andar a pé não é
  "mais devagar", é perder a run mais tarde, depois de gastar a travessia.
  Grita a partir de `CICLOS_ANTES_DE_GRITAR = 5`; desiste só sem tecla
  configurada, que é erro de config.
- **MAS INSISTIR NÃO PODE SER MUDO — o portão DIAGNOSTICA e AGE** (01/09/2026,
  `CICLOS_ANTES_DE_DESTRAVAR = 2`). Medido: **1465 s** (24 min) num waypoint,
  62 ciclos, 453 linhas idênticas, sem UMA leitura de batalha, morte ou vida.
  A partir do 2º ciclo o portão lê a causa:
  - **EM BATALHA ⇒ chama o destravamento** (`combat.limpar_o_combate`, injetado
    pela rotina em `nav.destravar_o_combate`). Em combate o jogo RECUSA montar,
    e só um golpe resolve — insistir na tecla nunca ia resolver.
  - **MORTO ⇒ levanta `PersonagemMortoNoPortao`**, que a rotina converte em
    `RECUPERAR`. Antes o laço apertava a tecla num cadáver **para sempre**:
    `_guard()` só roda no topo do laço principal e o portão nunca devolvia.
  - **"NÃO SEI" (`in_battle() is None`) NÃO destrava.** Não saber é motivo para
    continuar insistindo na tecla, nunca para gastar um minuto puxando mob.
  - **O invariante continua inteiro:** o portão NÃO ganhou teto para desistir.
    Destravamento que falha devolve `False` e o portão chama de novo.
  - Travado por `tests/test_destravamento_do_combate.py`.
- **`INTERVALO_REMONTAR = 3.0`**, e o número é medição: montar leva de 1 a 3 s
  conforme a montaria. Com 1,50 s o segundo toque caía DENTRO da subida — e a
  tecla é interruptor, então ele desmontava quem estava montando.
- **FORA DA CAVE SÓ DESMONTA SE O PET ESTIVER INATIVO**
  (`DESMONTAR_FORA_DA_CAVE_SO_SEM_PET = True`). Cura, buff e comida saíram do
  trajeto; invocar o pet é a única exceção. "Não sei onde estou" NÃO bloqueia a
  ação — não curar dentro da cave mata, um desmonte a mais fora custa segundos.
- **O PREPARO DE ENTRADA concentra tudo que exige estar a pé**
  (`_do_curar`): cura → buffs → pet → comida → montar. É onde a comida do pet é
  dada; antes ela era adiantada fora da cave e desmontava no meio do caminho.
  A COMIDA É O PASSO 4 E MONTAR É O 5, e essa vizinhança tem preço: medido em
  27/08/2026, a tecla da montaria saía 600 ms depois da comida e **cancelava o
  uso do item** — o log dizia que alimentou e a bolsa não baixava. Quem separa os
  dois é a espera de dentro do `feed_pet`.
- **OS CRONÔMETROS DA RUN COMEÇAM NA MONTARIA**, não ao confirmar a entrada.
  Ficam de fora a disputa da entrada e o preparo inteiro. Começam mesmo se algo
  do preparo falhar — run com problema tem de aparecer na estatística.
- **A GRADE DA COMIDA DO PET É FIXA** e sobrevive a reinício
  (`PetConfig.proxima_comida_em`, gravado pelo próprio `PetFeeder` — ver a seção
  "Pet"): ela avança a partir do VENCIMENTO, não da refeição. Atraso encurta aquela refeição, não desloca as seguintes — é o que
  mantém as ~28,8 refeições/dia com intervalo de 50 min. Atraso maior que um
  intervalo re-ancora no presente em vez de virar fila.
- **O AUTO-PATH DO SURROUNDINGS CLICA UMA VEZ E ESPERA PARAR.** Quem encerra a
  espera é "parou de andar" (ou chegar perto, como atalho).
- **O `[x,y]` DO PAINEL ESTÁ NA MESMA ESCALA DE `position()`** — MEDIDO: painel
  `Rich Man (153, -493)` contra `POSICAO_DO_VENDEDOR (158, -494)`.
- **MESMO ASSIM, REABRIR O PAINEL POR COORDENADA CONTINUA DESLIGADO**
  (`CONFIRMAR_CHEGADA_POR_COORDENADA = False`): ligado, ele transforma um ATALHO
  de saída em VEREDITO, e virou loop de aberturas na ida à Fay.
- **JANELA ABERTA ENGOLE O CLIQUE NA CENA 3D** —
  `docs/decisoes/janela-na-frente.md`. **O DONO DO PAINEL É O TRAJETO**
  (`trajeto_pelo_painel`), que fecha em toda saída, inclusive por exceção;
  `fechar_surroundings` é TRI-ESTADO e relê antes de aceitar cegueira ("não vi"
  ≠ "não está aberto"). **ORDEM: montaria → Surroundings** — o portão da
  montaria INSISTE SEM TETO, e com o campo de busca focado ele digitava a tecla
  dentro da busca (`Skull00000000...`). **`ABERTURAS_POR_TRAJETO = 4`** num
  contador só (era 3×3=9, produto acidental). Cadência carimbada em TRÊS pontos
  (abrir, auto-path, fechar) — só na abertura ela media *abrir→abrir* e não
  mordia. **O guarda (`core/janelas_abertas.py`) roda POR EVENTO**, com dois
  sinais MEDIDOS em COR: o X de fechar (0.80) e a moldura (0.65). **"Não sei"
  não bloqueia**, e ele NÃO roda antes do clique direito da Block list — lá
  fecharia a janela que precisa estar aberta.
- Destravamento por **VIZINHOS NA ROTA** (rollback/parado/sem progresso → mesma
  manobra, devolve o índice alcançado). Referência é a posição ATUAL; candidatos
  são os imediatos na ordem da lista. Na rota, só frente.
- Altar Stone: encosta EXATO em (218,45) ou **NÃO CLICA** (`PRECISAO_NO_PATAMAR_
  DO_ALTAR = 0.9`). Saída da cave: `PRECISAO_NO_PONTO_DA_SAIDA = 0.9`.
- **A CÂMERA — o detalhe medido está em `docs/decisoes/navegacao.md`**, leia
  ANTES de mexer. O que não pode ser violado: `ADDR_CAMERA` resolve NULO e quem
  responde é `ADDR_CAMERA_VIVA` (= `+0x60`), então dá para corrigir por ESCRITA;
  a pose mora NUM LUGAR SÓ (`POSE_DA_CAMERA` em `core/memory.py`, propriedade do
  JOGO, nunca da config); a PROVA espera o jogo desenhar; e o termômetro
  (`ADDR_ANGULO_DA_CAMERA`) SÓ LÊ e saiu da decisão — pode não ser constante.
- **A FAY EXIGE O PONTO EXATO ANTES DO CLIQUE**, igual ao vendedor:
  `POSICAO_DA_FAY = (178, -518)`, `PRECISAO_NO_PONTO_DA_FAY = 1.5`. **Não clica
  de fora do ponto** — a 2 passos o clique pegava o White Eagle, o diálogo não
  abria, e a rotina gastava o item de retorno para ir aonde já estava.
- **FALHAR NA FAY NÃO É "NÃO ESTOU EM STONE CITY".** Quem responde isso é a
  POSIÇÃO (`esta_em_stone_city`), não o clique que falhou — senão o item de
  retorno é gasto para viajar para a cidade em que o personagem já está.
- Teleporte da Fay: teto de 3 s, sai no instante em que confirma.
- Tempos fora da cave: teto da espera do diálogo APRENDE (`_BUSCAS_SEM_LEITURA`).

### Cliques e entrada da cave — `docs/REGRAS.md` (seção "Cliques") + `docs/decisoes/cliques-e-resolucao.md`

- **A TECLA TAMBÉM É `PostMessage`** (`MODO_DE_TECLA = "postmessage"`): toda tecla
  passa por `Input._enviar_tecla`. `SendMessageW` não tem timeout ⇒ cliente parado
  prende a thread para sempre.
- **O clique DIREITO sai em rajada** (`CLIQUES_DIREITOS_POR_TENTATIVA`); não se
  aplica ao esquerdo nem ao movimento pelo minimapa (repetir perde precisão).
- **O MOUSE SHIELD ESTÁ DESLIGADO** (`USAR_MOUSE_SHIELD = False`) e isso depende
  de `MODO_DE_CLIQUE = "postmessage_puro"` (as 4 mensagens na fila tornam o hook
  desnecessário). Voltar `MODO_DE_CLIQUE` para `"sendmessage_rapido"` obriga a
  religar o shield. `GetCursorPos` NÃO é como o jogo resolve a posição do clique.
- **O F12 preso está DESLIGADO** (`SEGURAR_ATIVADO = False`): o mecanismo é a fila
  (`key_down` conta aninhamento por janela; a tecla é solta em QUALQUER saída).
- Esconder jogadores hoje é o `BlazesBot - PetBug.exe` (`core/petbug.py`), por
  sessão, um clique cobre todos os clientes. O truque do F12 está DESLIGADO.

### Venda — `docs/REGRAS.md` (seção "Venda") + `docs/decisoes/venda.md`

- Gatilho por **CONTAGEM DE RUNS** (`runs_before_selling`, default 5). Começar em
  Stone City **VENDE antes** de sair farmando.
- O Rich só existe em Stone City e chegar lá é **CONFERIDO**; é **procurado na tela**
  (`vendedor.png`), não em coordenada decorada. Ponto de parada exato (158,-494),
  `PRECISAO_NO_PONTO_DO_VENDEDOR = 0.9`.
- **CONFERÊNCIA DE SLOT VAZIO DESLIGADA** (`CONFERIR_SLOT_VAZIO = False`): clica o
  total configurado em passadas de 24. Caixa "It's precious item" conferida a cada
  clique.
- **O "SELL" TEM RESPIRO ANTES E DEPOIS** (`ESPERA_ANTES_DO_SELL = 0.30`,
  `ESPERA_DEPOIS_DO_SELL = 0.5`): é o único clique que chega na cola de uma
  RAJADA de 24 cliques a 0,065 s, e um Sell engolido marca a passada como
  vendida **sem ter vendido nada**. Espera cega e exceção consciente à regra —
  "o cliente digeriu os 24 cliques?" não tem observável.
- Sem tecla de retorno ⇒ venda DESLIGA o `bc_farm` e salva. A grade da janela de
  venda COMPACTA (clicar N vezes no mesmo ponto esvazia de N pra frente).

### As duas interfaces (UI) — `docs/REGRAS.md` (seção "Interface") + `docs/decisoes/interface.md`

- Tela "Histórico de Quedas" (núcleo `core/quedas.py`): só queda REAL, registrada
  ANTES de matar a janela. Retenção de 3 dias.
- Cronômetros AO VIVO começam ao confirmar que está dentro da cave; cards da última
  run são fixos.
- Tecla repetida é **BARRADA** na digitação (exceto APP, que repete por desenho).
- **A RODA DO MOUSE SOBE E DESCE TODO CAMPO NUMÉRICO da web**; o passo é o `step`
  DO CAMPO (igual para setinha e roda; `Shift` = 10×), o mesmo nas duas telas. O
  handler dispara `input`/`change`, respeita `min`/`max` e arredonda pela casa do
  passo. **Em `type="range"` o `step` manda na GRADE** — slider usa `step="1"` e o
  passo grosso vai em `data-passo-roda`, senão 90% é inalcançável.
- **NENHUM CAMPO NUMÉRICO ACEITA 0** — mínimo 1, ou `MINIMO_DELAY_MS` = 100 se
  for tempo; única exceção é `ed-app-limpar` (0 = "nunca apagar"). **A TELA FALA
  MS e o `config.json` segue em SEGUNDOS** (`config.segundos_para_ms`; a ida e a
  volta têm de fechar). Só a comida do pet segue em MINUTOS (40..60, grampeada na
  LEITURA). **`max_clients` FOI APOSENTADO**: quem manda é `enabled_accounts()`.
- CURSOR DE LOG NUNCA É ÍNDICE DE DEQUE (usa cursor absoluto + `deque` com teto).
- Dicionário por `hwnd` é **LIMPO NA MORTE DA JANELA** (Windows recicla hwnd).
- UI web é Tailwind v4 + Vite de alta densidade; `body` nunca rola. Editar `web/*`
  exige `npm run build`. DEBUG só em dev.
- **A tela de Log tem TRÊS COLUNAS** (hora | conta | mensagem) alinhadas por
  `subgrid` (flex como base no `@supports`) — é o que faz a linha longa que quebra
  continuar sendo UMA linha. O texto COPIADO sai de `l.linha` inteira.
- **NO LOG, FIO ENTRE LINHAS — NUNCA FAIXA ALTERNADA** (`podarCache` remove a
  primeira linha, e `:nth-child` inverteria a paridade de todas a cada poda: uma
  piscada de tela a cada 300 ms). **A caixa NASCE SEM LAYOUT** (`.secao` é
  `display: none`), então `navegar("log")` chama `colarNoFimDoLog()`; a rolagem
  **persegue** o fim por `rAF`, e quem gateia os efeitos é `EFEITOS_DO_LOG`.

### Ferramentas TEMPORÁRIAS — `docs/REGRAS.md` (seção "Ferramentas") + `docs/decisoes/ferramentas-temporarias.md`

Módulos FOLHA (`TEMPORÁRIO`), nada do bot os importa. Os de adoção de janela
exigem o **bot parado** e devolvem o PID com `_release()` no `finally`.

- `bot/bc/teste_venda.py` — "Testar Venda".
- `bot/bc/amostragem_de_cliques.py` — "Amostrar Cliques" (reancora antes de cada
  amostra; não usa `_esperar_o_dialogo`).
- `bot/recorte_do_time.py` — recorta `state_team_member.png` (nunca existiu em
  disco). Mora em `bot/`, não `bc/` (serve os dois ecossistemas).
- `tools/vigiar_combate.py` — `9-VIGIAR-COMBATE`: acompanha a batalha AO VIVO.
  **NÃO reimplementa nada** — chama `TargetHybrid.ler(com_tela=False)` e
  `linha_do_log`, a MESMA linha que o BC escreve. Ferramenta que reimplementa a
  leitura diagnostica a cópia, não o bot (foi por isso que a versão antiga foi
  apagada). Lista os `client.exe` NUMERADOS (nick + título). **SÓ LÊ.**
- `tools/ler_camera.py` — `17-LER-CAMERA`: vigia a struct da câmera AO VIVO.
  **SÓ LÊ** (travado por teste de AST). Existe para MEDIR a pose certa.
- `bot/bc/diagnostico_do_link.py` — fotografa em volta do clique no link
  (`ATIVADO`, `MAXIMO_DE_EPISODIOS = 12`). Não clica.

### Login e relogin — `docs/decisoes/login-e-relogin.md`

- A queda **NÃO é complemento**: pet e barra de atalhos entram em `try/except`; a
  conferência de saúde **sobe a exceção** (engolir deixaria a macro apertando
  teclas contra uma caixa de erro por horas).
- Telas modais do login: `_SIGNATURES` vai do mais específico ao mais genérico;
  template que casa por PREFIXO é o último a opinar. "Connecting to the server" é
  espera legítima (`SEGUNDOS_CONECTANDO = 6.0`) → clica **Cancel**, sem matar.
- **O ÚNICO motivo para matar uma janela:** parado na tela de usuário/senha por
  mais de 150 s sem avançar. O cronômetro conta SÓ na primeira tela.
- **O BACKOFF DE RELOGIN ZERA NO LOGIN CONCLUÍDO** — era um `else:` de
  `try/except` inalcançável, e da 9ª queda a conta esperava 300 s antes de CADA
  relogin. **Senha errada (só a tela do erro, 5 recusas) DESATIVA a conta.**
- **O AVISO DE CONEXÃO SÓ CONTA DENTRO DA CAIXA.** O template
  (`state_conn_prefix.png`) é só a frase, sem moldura, então casa também com o
  CHAT — outro jogador digitando "connection interrupted" no canal mundial
  derrubou 10 contas vivas (29/08 e 01/09/2026). A busca é presa a
  `coords.aviso_de_conexao` com raio `RAIO_DA_BUSCA_DO_AVISO`, e o limiar é
  **0.92** (era 0.80, abaixo do ruído do chat). As duas defesas são
  independentes de propósito: a frase no chat é evento que o bot não controla.
- **A definição visual da queda mora em UMA função**,
  `watchdog.quadro_com_aviso_de_conexao(hwnd, templates)` — `avaliar_saude` e o
  `Watchdog` do BC chamam a mesma. Eram duas cópias; a divergência custaria
  exatamente o defeito acima em só um dos caminhos.
- Travado por `tests/test_saude_em_todo_ecossistema.py` (lê o AST) e
  `tests/test_queda_por_aviso_de_conexao.py` (roda contra os prints reais de
  `logs/quedas/`).


## Ordem, identidade e grupo das contas — `docs/decisoes/interface.md`

A tabela de contas pode ser reordenada arrastando (web) ou por botões ▲▼ (GUI).
Pedido do usuário em 28/08/2026.

- **A ORDEM DAS CONTAS É A ORDEM DO ARRAY `accounts`.** Não existe campo de ordem
  e **não pode existir**: seriam duas fontes de verdade para a mesma coisa, com a
  pergunta sem resposta "se o campo discordar do array, quem manda?". Reordenar é
  `BotConfig.reordenar_contas(uids)`, e `save()` grava.
- **A IDENTIDADE DA CONTA NA INTERFACE É O `Account.uid`, NUNCA O ÍNDICE.** Era o
  índice, e a premissa que sustentava isso ("o índice é estável enquanto o editor
  está aberto") morre com a tabela reordenável: com a ordem da tela diferente da
  do disco, `definir_senha` grava **a senha na conta errada** — login quebrado e
  senha certa perdida, sem desfazer. O `uid` é gerado na criação, **imutável** e
  invisível em toda tela.
- **REORDENAR NÃO PODE PERDER CONTA.** `reordenar_contas` desduplica por
  identidade de OBJETO (não por uid), põe no fim quem a tela não citou, e
  **aborta** em vez de gravar uma lista menor. Perder conta ali é perder a senha
  cifrada dela.
- **A TELA NUNCA RECEBE UID REPETIDO** (`garantir_uids_unicos`, chamado na leitura
  do arquivo E antes de responder a lista). Duas contas com o mesmo uid são
  indistinguíveis para a interface: arrastar a segunda moveria a primeira.
- **`Account.grupo` É RÓTULO VISUAL, ESCOLHIDO PELO USUÁRIO.** Não representa
  nada para o bot. **Nenhum caminho do bot pode ler dele** — travado por
  `test_NENHUM_caminho_do_bot_le_o_grupo`, que lê o AST. Se algum comportamento
  passar a depender do rótulo, arrastar uma conta na tabela mudaria o que o bot
  FAZ.
- **AS TRÊS COISAS SÃO ORTOGONAIS:** a **ordem** é o array, o **time do APP** é
  `time_logins` (por LOGIN, no líder — imune a reordenação), a **party do BC** é
  `accept_team_invites`, e o **grupo** é rótulo. Nenhuma deriva da outra.
- **O ARRASTE NÃO TEM DEBOUNCE.** Grava no soltar, síncrono; se falhar, a tabela
  **recarrega do backend** — a tela nunca mostra uma ordem que o disco não tem.
  Debounce é justamente o que perde a última alteração quando a janela fecha.
- **NA GUI A REORDENAÇÃO É POR BOTÃO, NÃO POR ARRASTE.** A `QTableWidget` tem
  seis `setCellWidget`, e o arraste interno do Qt move os `QTableWidgetItem` mas
  **não** os widgets de célula: a senha de uma conta ficaria na linha de outra. A
  funcionalidade é a mesma nas duas telas; só o gesto difere.
- Travado por `tests/test_ordem_e_grupo_das_contas.py` (28 testes).
