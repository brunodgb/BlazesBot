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

#### Decisão de cave NÃO mora em código compartilhado (06/09/2026)

> **Regra do usuário:** *"tem decisões que só servem para um, mas para o outro
> não, então vão ter funções que até podem ser compartilhadas, mas tem funções
> que não devem ser compartilhadas"*.

- **NO BC NÃO SE DESMONTA ANTES DO WAYPOINT DOS GUN WITCH.** No caminho do
  covil os mobs são para **ignorar**. Travado por
  `tests/test_montaria_do_bc_no_caminho.py`.
- **UM GANCHO POR PERGUNTA, NÃO POR FUNÇÃO.** `destravar_o_combate` e
  `matar_quando_o_trajeto_trava` chamam a MESMA função (`limpar_o_combate`) e
  mesmo assim são dois, porque respondem a perguntas diferentes:

  | gancho | pergunta | quem liga |
  |---|---|---|
  | `destravar_o_combate` | *"não consigo MONTAR porque estou em batalha"* — matar é a única saída, o jogo recusa a montaria em combate | **as duas** caves |
  | `matar_quando_o_trajeto_trava` | *"estou montado, andando, e sem progresso"* — matar é **escolha** | **só a HH** |

- **GANCHO DE POLÍTICA NASCE DESLIGADO.** Foi por não ser assim que o BC
  regrediu: em 04/09 a matança da HH entrou direto no laço de deslocamento
  compartilhado, e em 06/09 o log da fase `ENTRAR_NO_COVIL` mostrou
  *"Desmontando antes da luta de destravar (andar até (242,22))"* seguido de
  *"NÃO DESTRAVEI em 60s: 9 morte(s), 8 TAB, 176 golpes"* — sessenta segundos
  e nove mobs, a pé, num corredor que era para atravessar.

#### Navegação presa — vale para as DUAS caves (`navegacao.md`, 04/09/2026)

- **MANOBRA QUE ANDA ZERO UNIDADE NÃO É MANOBRA.** O destravamento descarta o
  candidato que já está dentro da tolerância de chegada, e devolve `None`
  quando não sobra nenhum. Fingir sucesso ali zerava o contador de travas do
  chamador e produziu **4 min 10 s** num ponto só. A régua do filtro é a mesma
  da tentativa (`_tolerancia_do_candidato`) — nunca duas cópias.
- **SEM PROGRESSO E EM BATALHA: MATA.** O jogo prende o personagem em combate e
  nenhum clique de minimapa resolve. `destravar_o_combate` deixou de ser só do
  portão da montaria. Matar vem **antes** do teto e da manobra: matar é
  continuar, e a HH tem mobs a matar junto com os bosses.
- **FICAR PRESO TEM PRAZO: 30 s** (`TETO_PRESO_NO_MESMO_PONTO`). Conta só tempo
  inútil — matar e avançar zeram o relógio. Estourado, o controle volta para a
  rotina: enquanto a navegação insiste, o `_guard()` não roda, e Parar e
  watchdog ficam sem resposta.
- **O PONTO DO BOSS É O FIM DO CAMINHO DE CADA TRECHO.** Os dois são declarados
  separados e já divergiram (04/09: um waypoint comentado, o ponto apontando
  para ele). A diferença coube na tolerância e o defeito não apareceu como
  erro — apareceu como o bot insistindo num waypoint que não existia mais.
  Travado por `test_o_ponto_do_boss_e_o_FIM_do_caminho_de_cada_trecho`.

#### O que a sessão de 04/09/2026 fixou — o porquê medido em `hh.md` §13

- **`FarmDesligado`, `StopRequested` e `Disconnected` são tratados ANTES do
  `except Exception`** no laço da HH. Ordem de `except` aqui é semântica: o
  geral na frente engoliria os três sinais que não são defeito. `Disconnected`
  pode ser capturado, mas só para `raise` seco.
- **Nenhum clique de entrada sai depois de o personagem já ter entrado.** O par
  de cliques não é atômico (180–420 ms de espera do diálogo no meio), e dentro
  da cave o mesmo ângulo é o NPC de SAÍDA — o bot entrava e saía na mesma volta.
  A conferência é ENTRE os dois cliques (`ainda_vale`), não só antes do par.
- **NÃO SE CHEGA NO WAYPOINT DO BOSS COM A MIRA PRESA** (02/09/2026,
  `combate.largar_a_mira`, chamado no fim de `_do_guardas`). O cadáver do último
  Gun Witch fica selecionável por 7 a 13 s (medido), então `target_id != 0` na
  saída da fase é o caso NORMAL, não a exceção. **O ESC SÓ SAI COM ALVO
  CONFIRMADO NA MEMÓRIA** — sem mira o ESC abre o MENU do jogo, e menu aberto
  engole o clique na cena 3D (`docs/decisoes/janela-na-frente.md`).
  `id_do_alvo() is None` ("não sei") **não aperta nada**. Teto de
  `TENTATIVAS_DE_LARGAR_A_MIRA = 2`, porque o ESC também fecha janela aberta;
  `TETO_PARA_A_MIRA_CAIR = 0.60` é o mesmo teto medido das ações de UI do
  cliente. Falhar **não trava a run**: registra e segue. Roda DEPOIS de
  `curar_antes_do_boss` (que pode sentar) e FORA do `if/else`, para cobrir também
  o desfecho que não fechou pela flag. Travado por `tests/test_largar_a_mira.py`.
- **O NOME DO ALVO NÃO É CONFIÁVEL O BASTANTE PARA SER JUIZ ÚNICO** (auditado em
  02/09/2026 sobre 1.160.883 linhas de log). Das 1.390 leituras do portão de
  nome: **701 `ilegivel` / `lido=nada` (50,4%)**, 619 `'Gun Witch'`, 62
  `'Cemetery Guard'`, 7 `'Blaze Skull Marshal'` — e **uma leitura corrompida,
  `'PDtery Guard'`**, que é `'Cemetery Guard'` com os dois primeiros bytes
  trocados. Três consequências:
  - **Filtro estrito de nome ("só ataca se ler o nome certo") está PROIBIDO.**
    Com metade das leituras ilegíveis ele para o golpe em metade dos ciclos —
    exatamente o defeito medido em 26/08 ("sobrou 1 Gun Witch de pé e o bot
    parado") que `SO_O_ALVO_PROIBIDO_PARA_O_GOLPE` corrigiu.
  - **A TELA continua como reserva do alvo proibido** (`cemetery_guard.png`).
    Tirá-la deixaria a trava cega em metade das leituras. Duas fontes que falham
    por motivos diferentes é a única redundância que vale algo.
  - **A leitura corrompida é o achado mais grave**: não é uma falha, é uma
    string plausível e ERRADA. Ela desqualifica igualdade de nome como veredito
    único, e é por isso que o portão compara por `in` e trata `[]` como
    `ilegivel` em vez de "alvo errado".
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
- **O ID PUBLICADO MORRE COM A SESSÃO** (04/09/2026, `mural.esquecer_id` em
  `_release`). `mural._IDS` é dicionário de módulo e sobrevive ao relogin; a
  entidade, não. **Id velho é pior que id nenhum**: a Fada compara o id novo do
  jogo com o velho do mural, conclui que clicou na pessoa errada e descarta a
  vítima certa. Sem id ela confia no slot do painel, que é a regra do usuário.
- **A ESPERA PELA FADA TEM TRÊS SAÍDAS, E NENHUMA É ETERNA** (04/09/2026):
  a Fada AVISA que desistiu (`fada_desistiu_de` ⇒ poção), o teto de 60 s
  (`TETO_DA_ESPERA_PELA_FADA` ⇒ poção) e **entrar em batalha sentada ⇒ voltar à
  macro** (não é poção: é parar de apanhar de graça). A marca da desistência
  **não pode ser apagada no `pedir_cura`** — a desistência já removeu o pedido,
  então a republicação da vítima chega lá igual a um pedido novo, e limpar ali
  reabre o laço desistir/re-pedir.
- **A BATIDA DA FADA TEM VALIDADE, E TAREFA LONGA AVISA ANTES** (04/09/2026).
  `bater_fada(..., vale_por=)`; nunca encurta os 5 s padrão, nunca passa de
  `TETO_DA_BATIDA_LONGA` (15 s), e ao terminar a tarefa ela bate de novo com a
  validade normal para o aviso não sobrar. Sem isso, a limpeza de bolsa (teto de
  10 s) fazia o time inteiro dar a Fada por morta e beber poção com ela viva ao
  lado. **A batida sai também do topo de `_uma_volta`** — é o único ponto por
  onde passam os dois chamadores (o `rodar()` do APP e o laço da HH).
- **A FADA PERCEBE A PRÓPRIA QUEDA COMO QUALQUER OUTRO MODO** (04/09/2026).
  Janela morta no fim de `rodar_a_fada` ⇒ `Disconnected` ⇒ relogin e Histórico
  de Quedas, igual ao `_rodar_modo_app`. E `_montar_a_fada` **captura
  `Disconnected` e relança ANTES** do `except Exception` — engolir a queda ali
  deixava a Fada da HH acompanhando o líder com a janela fechada.
- **MEXEU NO `web/`, RODE `npm run build`** (04/09/2026). A janela do bot abre
  **`dist/index.html`**, que é o Vite compilado — editar `web/index.html` sem
  compilar não muda nada do que o usuário vê, e **nenhum teste reclamava**.
  Medido no campo `revive_skill`: campo no HTML, mapeado no `main.js`,
  transportado pela ponte nos dois sentidos, suíte inteira verde — e a aba
  Teclas na tela continuava sem ele. Travado por
  `test_o_dist_COMPILADO_tem_o_campo` (pula quando não há `dist/`, porque ele é
  gerado e ignorado pelo git).
- **NO REVIVER, QUEM MANDA É O SLOT — NÃO O ID** (06/09/2026). O retrato do
  morto continua clicável, mas o clique **não põe o id dele no `TARGET_ID`**;
  exigir que batesse reprovava a única coisa que ia funcionar (medido: a Fada
  desistiu em 2 s e a vítima queimou 58 s de prazo). O id continua sendo lido e
  vai para o log como diagnóstico. **Na CURA o id continua vetando** — lá o alvo
  está vivo, o clique seleciona, e é ele que impede curar o aliado errado.
- **A JANELA DO REVIVER É DE 10 s, COM NO MÁXIMO 3 TOQUES**, e o morto que não
  levanta **continua na fila** — o prazo dele é de 60 s, e largar no primeiro
  ciclo desperdiça 50. O teto de toques é cinto de segurança contra o laço de
  357 cliques de 01/09/2026, não sobre tempo.
- **A FADA REVIVE, E A CURA VEM PRIMEIRO** (04/09/2026, `bot/fada_reviver.py`).
  O morto só fura a fila dos feridos depois de `SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA`
  (40 s) — antes disso a cura tem prioridade, porque morto não apanha e tem
  prazo próprio. **Ela avisa no mural que começou a conjurar ANTES de apertar**,
  e **a vítima sai da fila dos mortos no instante em que fica de pé** — os dois
  lados desse contrato existem para o feitiço de 5 s não ser desperdiçado.
  Valem as mesmas regras da cura: id que não bate não revive, freio de 3
  tentativas, mana conferida antes do toque, sem tecla avisa uma vez e segue.
- **O APP RECONHECE A PRÓPRIA MORTE** (04/09/2026, `bot/morte.py`). `hp == 0`
  lido da memória, conferido **a cada linha** junto do alvo zerado — antes disso
  a macro seguia apertando tecla contra um cadáver, e no log de 7 h de duas
  contas de APP não havia UM evento de morte. Sem leitura, **não há morte**:
  cego não declara morte, senão pararia a macro de uma conta viva.
- **O CICLO DA MORTE TEM ORDEM FIXA:** avisa o time → espera a Fada no máximo
  `PRAZO_PARA_A_FADA` (60 s) → clica o "Ok" do jogo → senta e regenera → volta ao
  ponto pelo `Navigator`. **Sem Fada no time (ou sendo eu a Fada), revive na
  hora** — não há por que esperar. **Feitiço em curso ESTICA o prazo** (a skill
  tem 5 s de preparo; sem esticar, a vítima se auto-revive no meio dele e a
  mana da Fada vai fora).
- **OS DOIS "Ok" FICAM A 133 px UM DO OUTRO, E O ERRADO CUSTA O SPOT.** O do
  convite da Fada teleporta para ela; o do jogo revive no lugar cobrando mais
  Exp. Por isso o convite é o **único** ponto do ciclo decidido por IMAGEM
  (`convite_reviver.png`, limiar 0.9) e o clique sai **onde o template casou**,
  nunca numa coordenada fixa.
- **TRÊS MORTES SEGUIDAS SEM VOLTAR AO PONTO PARAM A CONTA.** É "seguidas", não
  "no total": voltar zera o contador. Sem ele, um spot que virou armadilha vira
  um moedor de tentativas a noite toda.
- **O ALVO CAÍDO CORTA A VOLTA, E A ORDEM É: SAÍDA DE BATALHA, DEPOIS HP**
  (06/09/2026). *"Se ainda diz 'mob vivo' mas saiu de batalha, é porque a
  leitura está errada e o sair de batalha manda mais, pois garante que não tem
  ninguém batendo no personagem"* — por isso `_a_batalha_acabou` é conferida
  ANTES de `_o_alvo_caiu_pelo_hp`. Inverter a ordem põe uma leitura ruim de HP
  na frente da prova forte.
- **DENTRO DA VOLTA, A PERGUNTA SOBRE O ALVO É SÓ DE MEMÓRIA.**
  `_o_alvo_caiu_pelo_hp` lê `hp <= 0` e nada mais; **HP ilegível NÃO VOTA**.
  `_alvo_morreu` (o veredito completo, da aquisição) continua PROIBIDO no laço:
  ele cai na cascata da TELA quando o HP falta, e a tela custa uma captura por
  consulta — travado por `tests/test_laco_simples_do_app.py`.
- **CAIU O ALVO, A SAÍDA DE BATALHA É CONFIRMADA ATIVAMENTE POR ATÉ 2 s**
  (`SEGUNDOS_PARA_CONFIRMAR_A_SAIDA`). Sai no instante em que a flag baixa;
  estourar o teto **não é fracasso**, é o outro desfecho útil: quer dizer que há
  outro mob batendo, e aí o bot volta a atacar em vez de sentar, andar ou abrir
  a bolsa.
- **NADA RECUSA UM ALVO VIVO POR DISTÂNCIA** (HOTFIX de 06/09/2026, com conta
  morta). O TAB do jogo entrega o mob **mais próximo primeiro** e vai afastando
  a cada toque: recusar o primeiro empurra a seleção para fora, e o bot acaba
  correndo até um mob distante com meia dúzia de outros atrás. **O primeiro
  alvo vivo que o TAB traz é, por construção, o melhor que existe** — procurar
  outro é o próprio dano. `core/coleira_do_ponto.py` virou MEDIÇÃO; se um dia
  houver régua de novo, ela não pode ser feita de recusa (recusa custa TAB, e
  TAB custa distância) — teria de perguntar ANTES do TAB, varrendo
  `entidades_vivas()`.
- **O RELÓGIO DO TIME NÃO TROCA ALVO BOM.** O pedido de TAB dos 4 s
  (`conferir_a_parada`) passa por `_tenho_alvo_vivo()` antes de virar tecla: com
  alvo vivo selecionado, ele é descartado. `_mesmo_alvo_verificado` já deveria
  barrar, mas depende do registro da aquisição — alvo herdado de outra volta
  escapava.
