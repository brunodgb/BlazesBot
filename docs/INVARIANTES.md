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
FORA de batalha  → pet → comida → voltar ao ponto → 600 ms → TAB → linha 0 → macro
EM batalha       → roda a macro de novo, SEM TAB e SEM conferência
saiu de batalha  → corta a macro no meio, volta ao topo
vida < 30%       → a cura, entre voltas (inalterada)
```

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
do penhasco, a conferência de id no TAB, a urgência. **Cada uma tem medição
atrás**, e `tests/test_tab_no_app.py` desliga o interruptor e exercita todas —
religar é trocar um `True` por `False` e 134 testes voltam a valer.

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

## A Fada — `docs/decisoes/fada.md`

A conta marcada como `Fada` que, **em time**, cura em vez de atacar. Fora de um
time a flag não faz nada.

- **A VÍTIMA AVISA, a Fada não adivinha.** Quem lê a vida é o próprio
  personagem, pela memória. A Fada nunca decide quem curar olhando barra de
  tela.
- **CLICOU, CONFERE.** Depois de clicar no retrato, a Fada lê o `nome` do alvo
  pela memória e compara com quem pediu. O mapa slot→nick é aprendido, mas
  **conferido sempre**: a ordem do painel muda quando alguém reentra no time.
- **A FADA FICA FORA DA LARGADA**, da macro e da sincronia. Contá-la como
  membro trava o time esperando uma confirmação que nunca vem.
- **SEM FADA DE PÉ, A POÇÃO VOLTA.** "De pé" é a batida dela no mural, e essa
  batida sai de DENTRO do laço que cura — nunca de uma checagem externa.
- **BOLSA E PET SÓ COM A FILA VAZIA.** Abrir inventário com alguém esperando
  cura mata o alguém.
- **MORTO NÃO É CURADO** e para de rodar o APP (só em time). A Fada ignora e
  segue para o próximo.
- **O PONTO INICIAL DO TIME É O DO LÍDER** — isto INVERTE a regra anterior, e a
  inversão tem trava: só adota se estiver no MESMO MAPA. `_voltar_para_base`
  anda pelo minimapa, e destino fora do raio útil vira clique na borda: no mapa
  errado o personagem anda contra a parede indefinidamente.
- **A GEOMETRIA DO PAINEL É DERIVADA**: primeiro retrato em (28,204) e um passo
  fixo. Nunca cinco literais soltos. O painel encolhe por baixo, e quantos
  slots varrer é "membros − ela" — mas quem confirma é a memória, não a conta.

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
- **A ENTIDADE PODE DEMORAR UM CICLO A APARECER** no array logo depois de
  selecionar (medido: 1 em ~45) — por isso a tela continua como reserva.
- **NOS GUARDAS, SÓ O CEMETERY GUARD PARA O GOLPE** (26/08,
  `SO_O_CEMETERY_GUARD_PARA_O_GOLPE_NOS_GUARDAS`): outro nome não para nada —
  rotaciona skill **até sair de batalha**. Cemetery Guard na mira ⇒ ESC (uma
  vez) e espera a saída, por UMA porta (`_travar_no_cemetery_guard`) que serve
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
- Travado por `tests/test_saude_em_todo_ecossistema.py` (lê o AST).
