# Combate, alvo e memória — decisões e medições

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.

- **A cura antes do boss é FORA de combate, no waypoint dos 4 mobs — não na
  frente do boss.** Depois de matar os guardas e sair de batalha, `_do_guardas`
  chama `combat.curar_antes_do_boss()`: se a vida estiver **abaixo de 40%**
  (`LIMINAR_TOPUP_ANTES_DO_BOSS` em `combat.py`), tenta a **Super Skill** (ou
  skill de cura) UMA vez e **confere o efeito pelo ponteiro de HP** (lê antes,
  espera `SEGUNDOS_DEPOIS_DA_SUPER_SKILL`, relê; subiu = curou, acabou); se não
  subiu (recarga) usa **1 poção de HP** e fica parado os 15 s. Acima de 40% não
  gasta item. Na **espera do boss** (`esperar_entrar_em_combate`,
  `pocao_na_espera=False`) **NÃO se bebe poção** — o boss encosta e cancela o
  efeito na hora —; se faltar vida, o bot **senta** para regenerar de graça
  enquanto aguarda (SEM PRAZO). Sustentação DURANTE a luta continua por
  `maintain(em_luta=True)` com `battle_hp_pct`. Esse limite de 40% é um único
  valor fixo no código (não editável na tela, como `max_heal_seconds`).
- **EXPERIMENTO — troca de alvo por TAB nos guardas, lendo a barra de vida na
  TELA.** Interruptor `USAR_TAB_NOS_GUARDAS` no topo do `combat.py`; o caminho
  antigo está INTACTO em `_fase_dos_guardas_sem_tab` e voltar é trocar `True` por
  `False`. Motivo: a fase leva 33-43 s (6 runs medidas); perceber a morte e
  trocar na hora encurta.
  - **A morte do alvo é lida por MEMÓRIA, com a tela como reserva.** Nasceu só
    pela tela porque o alvo não lia; isso mudou e está confirmado no
    `2-DIAGNOSTICO` com um Gun Witch na mira: `HP do alvo 100/100 → 90/100`
    depois de uma skill, nome e nível corretos. A memória custa
    microssegundos contra ~11 ms da captura, a cada 0,3 s de luta. A tela
    (`vision.vida_do_alvo`) responde quando a entidade SOME da memória —
    que é justamente o caso de morte com a struct já removida.
  - **A âncora é a barra AZUL de mana do alvo**, não uma coordenada fixa. Medido
    em dois prints do usuário: **um pixel** de diferença na largura da janela
    (1024 vs 1025) moveu o quadro **5 linhas**. A barra azul tem largura
    constante (137 px) e existe vivo E morto; a faixa vermelha fica sempre 7
    linhas acima dela, e a PRIMEIRA linha da faixa é borda (vermelha mesmo com o
    mob morto), por isso é descartada da conta. Resultado medido: **vivo 0.998,
    morto 0.000**.
  - **`LIMIAR_DE_VIDA_DO_ALVO = 0.01`** — o erro caro é ler "morto" num mob quase
    morto, dar TAB e deixá-lo vivo. Medido: 2% de vida ainda lê 0.0136 = vivo.
  - **`CARENCIA_APOS_O_TAB = 1.5`** (nenhuma classe mata em menos que isso): sem
    ela, ler no vão do redesenho veria a barra do alvo ANTIGO e queimaria os 3
    TABs em menos de um segundo.
  - **`TABS_NOS_GUARDAS = 3`** é TETO, não meta (4 mobs, o 1º vira alvo sozinho).
    Classes de área saem de combate com 1-2 TABs e a fase segue igual — **quem
    decide o fim continua sendo a flag de combate**. Quadro ausente conta como
    morte (o jogo tira o quadro algum tempo depois), mas captura em branco não.
  - **A fase COM TAB usa AoE** conforme a config (`usar_aoe=True`); a sem TAB
    continua sem.
- **No boss, TAB depois de 5 s sem engajar** (`SEGUNDOS_ANTES_DO_TAB_NO_BOSS`) e
  começa a rotação normal — atacar é o que puxa o boss que não vem sozinho.
  Isso trocou a espera SEM_PRAZO por ação, e criou um risco que precisou de
  portão: com a luta forçada a flag ainda está baixa quando a rotação começa, e
  a confirmação de saída declararia **vitória em 1,5 s sem luta nenhuma**. O
  `exige_ter_entrado` do `atacar_ate_sair_de_combate` exige a flag ter subido ao
  menos uma vez antes de aceitar "saiu de combate"; e `LIMITE_PARA_A_LUTA_COMECAR`
  (15 s) devolve o controle se o TAB não pegou o alvo certo, em vez de girar a
  rotação contra o nada até o prazo da luta.
- **A raiz das cadeias de UI mudou para `0x012CE340`** (era `0x012CE2E0`).
  Medido com o `10-DESCOBRIR-ALVO` em **nove execuções** (5 clientes, 2 rodadas):
  a raiz velha morre no 2º elo (`0x253d7325`, desalinhado) em todas; a nova é
  plausível em todas. **+0x60 é o mesmo deslocamento que a `PLAYER_BASE` sofreu**
  da ver.6139 para a 6400 — o segmento de dados andou junto e este endereço tinha
  ficado para trás. Consequência esperada: `bag_open()` volta a responder (falhava
  5 de 5 runs, custando 2 s por run). **Falta confirmar com o `2-DIAGNOSTICO`.**
- **`ADDR_MODAL` (0x012CE35C) está medidamente errado como flag booleano:** ele
  guarda um PONTEIRO (`0x03427d40`), nunca 0 nem 1, então `modal_open()` é sempre
  False. É a causa medida do Ok do item precioso nunca ser clicado. O candidato
  `0x012CE3BC` (+0x60) lê 0 sem modal na tela — consistente, mas **não provado**:
  falta uma medição COM a caixa aberta. Não foi trocado.
- **O nome da entidade: quem lê inline e quem lê por ponteiro.** Medido no covil:
  `Gun Witch` (4 structs), `Cemetery Guard` (5) e `Skull Herald` guardam o nome
  INLINE em `+0xBC`; o **`Blaze Skull Marshal` guarda por PONTEIRO** — lê `'8@'`
  direto. As duas interpretações já estavam implementadas em `target_name()`, e é
  por isso que a ordem importa (texto primeiro, ponteiro depois).
- **`jogador+0x80C` é o PET.** Em duas rodadas com alvos diferentes ele apontou
  sempre para a mesma entidade de **243/243** que acompanhava o personagem — a
  escala de pet/jogador (`ESCALA_DE_INIMIGO`). Como `target_object` cai nele
  quando `0x808` está vazio, mirar o pet é desfecho possível.
- **A SEGUNDA FASE DO BOSS troca a struct e PERDE a seleção.** Medido no
  `2-DIAGNOSTICO`, com o Blaze Skull Marshal transformado:
  ```
  fase 1:  +0x808 = 0x470da560 'Blaze Skull Marshal' nv50   7/100
  fase 2:  +0x808 = 0x470dc770 'Skull Herald'        nv30 100/100   <- a SELEÇÃO
           +0x80C = 0x470d9458 'Blaze Skull Marshal' nv51  11 -> 6  <- o OPONENTE
  ```
  A struct da fase 1 foi **liberada e reaproveitada por um `Fireball` de nível
  1**. A seleção ficou para trás; só `+0x80C` acompanhou o boss novo.
  - Por isso `Memory.alvo_e_oponente()` devolve **os dois campos**, e
    `_alvo_permitido` aceita quando o nome esperado está em **qualquer um** deles.
    Exigir só a seleção faria o bot recusar o boss e gastar os 6 TAB na fase que
    decide a run.
  - **A fase 1 não zera** — ela some por volta de 7% e nasce a seguinte. Nada a
    fazer: quem encerra é a flag de combate, que não baixa na transformação.
    `_registrar_troca_de_fase` só REGISTRA no log, para "o HP do boss subiu de 7
    para 11" não parecer defeito de leitura.
- **O portão do alvo existe SÓ nos guardas. No boss ele foi REMOVIDO.**
  - **No boss: entrou em combate, ataca — nada além disso.** O TAB no meio da
    luta trocava o alvo justamente na virada da fase 1 para a 2, e a virada se
    resolve continuando a bater: a segunda fase pega o alvo sozinha assim que
    ataca. O único TAB que sobrou no boss é o de ENGAJAR
    (`SEGUNDOS_ANTES_DO_TAB_NO_BOSS`, 1 vez depois de 5 s sem combate).
    `registrar_troca_de_fase=NOME_DO_BOSS` é só log —
    `PRIMEIRA FASE MORTA: ... Continuo atacando SEM TAB`.
  - **Nos guardas: alvo que não é `Gun Witch` ENCERRA a fase na PRIMEIRA
    leitura**, sem gastar TAB e sem soltar skill. Não é falha: os quatro são
    sempre os primeiros alvos do TAB, então ler outro nome significa que
    morreram. Atacar qualquer outro mob ali só gasta tempo de run e puxa mob que
    não precisava vir — foi assim que a run das 11:33 saiu da rota (o waypoint
    estava certo; o que tirou o personagem do lugar foi bater no mob errado).
  - **`TABS_POR_ALVO_ERRADO` e `ATACAR_QUANDO_NAO_SEI_O_NOME` SAÍRAM.** Não há
    mais TAB por alvo errado em lugar nenhum. O TAB de morte
    (`tabs_ao_morrer=TABS_NOS_GUARDAS`) continua — é como o bot passa para o
    próximo Gun Witch.
  - **Nome ilegível: `CARENCIA_SEM_LER_O_NOME = 3.0`.** O bot SEGURA o golpe
    enquanto o nome não lê, e só bate sem saber em quem se ainda estiver em
    combate depois dos 3 s. Medido em simulação: numa luta que acaba em 2 s o bot
    não solta **nenhum** golpe — saiu de batalha, não há mais ninguém para
    atacar, vai para o waypoint do boss.
  - **A flag baixou DEPOIS de a luta ter começado ⇒ o golpe PARA**, nos dois
    pontos. O bloco do golpe não olhava para `falso_desde`, então o bot batia
    durante toda a `CONFIRMACAO_DE_SAIDA_DE_COMBATE` (1,5 s) DEPOIS de a luta
    acabar — que é como se convida o mob seguinte.
    **O `ja_entrou` na condição não é detalhe:** ele separa "a luta ACABOU" de "a
    luta ainda NÃO COMEÇOU". Sem ele o engajamento forçado do boss morre — lá o
    bot dá o TAB dos 5 s com a flag ainda baixa e entra na rotação justamente
    para PUXAR o boss, porque **TAB sozinho não engaja, quem engaja é o golpe**.
    Com a flag baixa contando como "acabou", ele giraria o laço sem soltar skill
    nenhuma até o prazo e perderia a run parado na frente do boss (medido em
    simulação: 0 golpes).
    A simulação disso exige **relógio falso começando em valor não-zero**:
    `falso_desde = 0.0` é o sentinela de "ainda não baixou", e um relógio em 0.0
    torna os dois indistinguíveis — a primeira versão do teste passava ATÉ COM O
    DEFEITO presente.
  - **O boss só é dado por morto quando SAI DE BATALHA** (`fim.saiu_de_combate`),
    nunca por HP zerado — é isso que faz a troca de fase não enganar, já que a
    flag não baixa na transformação.
- **Portão do alvo nas duas lutas** (`atacar_ate_sair_de_combate(alvo_esperado=)`):
  `_alvo_vale_o_golpe` recusa o golpe e dá TAB quando o alvo é o próprio
  personagem/pet (por **identidade de ponteiro** e pela **escala de HP**, não por
  nome) ou quando o nome não é `NOME_DOS_GUARDAS` / `NOME_DO_BOSS`. Bater no mob
  errado PUXA mob que não precisava vir.
  - **Falha ABERTA** (`ATACAR_QUANDO_NAO_SEI_O_NOME = True`): nome ilegível ⇒
    ataca. O nome do BOSS vem por ponteiro, a forma mais frágil; recusar por não
    ler perderia a run inteira, e atacar o mob errado só custa mobs a mais.
  - **`TABS_POR_ALVO_ERRADO = 6`**, e esgotado o orçamento ele **volta a bater** —
    ficar sem atacar na frente do boss é o pior dos dois erros.
- **Desmonte em batalha só nos 2 pontos de luta.** O bot NÃO desmonta com a
  flag de combate ligada (`ensure_dismounted` ignora o pedido e loga "Em
  combate: ignorando o pedido para desmontar.") — exceto nos **waypoints dos
  4 mobs antes do boss** e **do boss**, os únicos pontos em que o personagem
  precisa atacar (montado o jogo ignora a tecla de skill). Lá desmontar em
  combate é o objetivo, e a exceção chega via `permitir_em_batalha=True`, de
  `_descer_para_lutar("guardas"/"boss")` para `ensure_dismounted`. Qualquer
  outro desmonte (poção, curar, preparo) continua segurando em batalha.

- **Pós-boss, antes de montar e sair, o bot usa o(s) `package_courage` pelo
  inventário.** No ramo de vitória do `_do_boss` (personagem ainda no waypoint
  do boss, a pé), `_usar_package_courage()` abre o inventário com a tecla JÁ
  configurada (`keys.inventory`, mesmo valor de `KeyBinds.inventory` — sem nova
  config), procura TODOS os matches do template
  `data/templates/package_courage.png` (27×33, recortado à mão pelo usuário;
  era `.jpeg`) com `vision.find_all_templates` e clica com o botão **DIREITO**
  no centro de cada um — o boss sempre dropa esse item e o uso o remove da
  bolsa. É um **COMPLEMENTO que nunca derruba a run**: até
  `RODADAS_DE_USO_DO_PACKAGE` (5) rodadas de busca-clique, e **para antes se
  achar 0 matches** (a confirmação de que sumiu É a própria procura seguinte sem
  matches); se a captura vier preta/None (`frame_is_blank`) NÃO decreta sumiço —
  re-tenta até `CAPTURAS_INVALIDAS_PACKAGE` (3) e então segue SEM confirmação.
  Sem tecla de inventário ou sem template → passo pulado. 100% core (a regra das
  duas interfaces não é tocada).
  - **O casamento é EM COR** (`templates.load_color` + `find_all_templates(...,
    colorido=True)` + `LIMIAR_DO_PACKAGE_EM_COR = 0.92`), varrendo a janela
    INTEIRA (a bolsa pode ser arrastada para qualquer canto). Remedido com o PNG
    atual: item verdadeiro 0.971–0.999 em cor, distratores de mesma forma e cor
    diferente 0.583–0.878 — vão limpo, 0.92 no meio. **Em cinza o vão não
    existe** (os mesmos distratores marcam 0.932–0.989). A troca de JPEG para
    PNG alargou a margem: sem compressão em lugar nenhum do caminho (template
    PNG + captura BitBlt), o pior caso do item verdadeiro subiu de 0.934 para
    0.971.
  - **Os tempos são pequenos DE PROPÓSITO, e nenhum deles protege o
    reconhecimento.** O passo levava 3–4 s por run (6 runs no log de dev) e o
    casamento custa **33 ms** — tudo o mais era espera fixa. A regra que
    substituiu: onde havia espera cega, agora se PERGUNTA. Não há mais
    `tick(0.4)` depois da tecla — o laço de `bag_open()` já trata "ainda não
    abriu", e trata melhor; ele consulta a cada `PASSO_DA_ESPERA_DA_BOLSA`
    (0.05 s, era 0.15). `ASSENTAMENTO_DA_BOLSA` (0.25) é o desenho da janela
    terminando de pintar (a memória confirma antes de a tela estar pronta) e,
    nas rodadas seguintes, o item sumindo depois do uso.
    `ENTRE_CLIQUES_NO_PACKAGE` (0.05) é curto porque o clique é **síncrono**
    (`SendMessageW`): quando a chamada volta, o cliente já processou.
    `DEPOIS_DE_FECHAR_A_BOLSA` (0.05) porque nada depende dele. Medido em
    simulação com relógio determinístico: o que o bot gasta por conta própria
    caiu de 1,44 s para 0,69 s com 1 item, e de 2,49 s para 1,04 s com 8. O
    resto é latência do jogo abrindo a bolsa, que nenhuma versão encurta.
  - **As três travas não foram tocadas:** `bag_open()` antes de qualquer clique,
    posição conferida a CADA clique dentro do laço (clique que cai no chão move
    o personagem), e progresso por rodada (duas rodadas sem a contagem cair =
    falso positivo, desiste).

- **A MORTE DO ALVO VOLTOU A SER DECIDIDA PELA TELA** (`FONTE_DA_MORTE_DO_ALVO
  = "tela"`, interruptor no topo do `combat.py`). É REVERSÃO decidida por
  evidência de produção, e o caminho por memória **continua inteiro e sem uso**
  — `"memoria"` o traz de volta; desligado não é apagado, e ele tem testes
  próprios para não apodrecer.
  - **Por que a memória saiu, tendo entrado com medição.** Os dois fatos que a
    trouxeram continuam verdadeiros (o `2-DIAGNOSTICO` mostrou o HP
    acompanhando o dano; ponteiro custa microssegundos contra ~10 ms de
    captura). O que não se sustentou foi a leitura DENTRO da luta real, medida
    às 02:02 de 13/08/2026 na fase dos guardas:
    ```
    t=1.5s ... t=18.8s   hp=100      <- 89 golpes no meio, HP parado
    t=21.0s              hp=52
    t=22.7s              hp=0   -> TAB 1
    (1,5s depois)        hp=0   -> TAB 2      <- o MESMO cadáver
    t=25.8s              hp=0   -> TAB 3      <- e de novo
    ```
    Duas falhas numa luta só: o HP não acompanhou o dano, e depois da morte o
    ponteiro CONTINUOU devolvendo o cadáver. Os três TAB do orçamento em três
    segundos. A barra na tela não tem esse problema — ela pertence ao QUADRO do
    alvo, e o quadro some quando o alvo sai da seleção.
  - **Custo aceito:** com a tela decidindo, cada leitura da cadência de 0,3 s
    vira uma captura — ~1,3 s de CPU por fase, por conta.
  - **A memória continua sendo LIDA, só não decide.** O HP vai para o log ao
    lado do veredito (`hp_memoria=`), o que transforma a reversão em medição
    contínua. Simulado com o cenário de produção: a barra desce de 0.94 a 0.10
    com `hp_memoria=100` congelado, e em t=22.5 o ponteiro diz `hp=0` com a
    barra em 0.10 — `veredito=vivo`. **Um** TAB onde a produção queimou três.
- **O PORTÃO "só relato a morte de um alvo que eu vi VIVO" é UNIVERSAL.**
  O veredito saiu de `_alvo_morreu` para `VigiaDoAlvo` (`combat.py`), classe de
  **lógica pura** — recebe LEITURAS, não fontes; quem faz I/O continua sendo
  `_alvo_morreu`. Foi isso que permitiu simular a luta inteira sem o jogo.
  - **A primeira versão aplicava o portão SÓ à ausência**, com o raciocínio de
    que leitura positiva de morte (`hp = 0`, barra vazia) não tem dúvida a
    resolver. Tem: o número pode ser do CADÁVER. Foi assim que o log registrou
    `veredito=MORREU (hp=0) | ja_tive_alvo=False` — o caminho da memória nem
    consultava o portão. Agora todo veredito de morte passa por `_julgar`.
  - **O defeito:** `if vida is None: return True  # quadro sumiu = morreu`.
    Três situações caíam nesse mesmo `True`: (1) o alvo AINDA NÃO foi adquirido,
    (2) a leitura falhou num instante, (3) o alvo SUMIU depois de ter existido.
    Só (3) é morte. Com (1) o TAB saía no primeiro instante da luta, o alvo
    virava um `Cemetery Guard`, o nome não lia na hora e depois de
    `CARENCIA_SEM_LER_O_NOME` o bot batia sem saber em quem — o "atacando mobs
    que não são Gun Witch" relatado.
  - **Enquanto o alvo novo não aparecer VIVO, morte lida é morte do anterior.**
    É a regra inteira, e ela cobre os dois sintomas de uma vez: o TAB no
    primeiro instante da luta (alvo ainda não adquirido) e a rajada de TAB no
    cadáver depois da morte.
  - **`LIMIAR_DE_VIDA_DO_ALVO = 0.01` continua valendo** e continua sendo o que
    protege o erro caro: mob a 2% de vida lê 0.0136 na barra, e isso é VIVO.
  - **O TAB FECHA O PORTÃO DE NOVO** (`VigiaDoAlvo.trocou_de_alvo`), e sem isso
    a correção ficava pela metade — **a simulação pegou**: TAB aos 5,1 s (a
    morte real) e outro aos 6,6 s, exatamente um `CARENCIA_APOS_O_TAB` depois.
    Os dois mecanismos resolvem coisas diferentes e por isso convivem: a
    carência cobre o REDESENHO do quadro (tempo), o portão cobre a AQUISIÇÃO do
    alvo (evento). Alvo que demore mais que a carência para ser adquirido passa
    pela primeira e é barrado pelo segundo.
  - **O vigia é POR LUTA.** Se o portão atravessasse, a luta seguinte começaria
    com ele aberto e a ausência do primeiro instante voltaria a valer como morte.
  - **`CARENCIA_APOS_O_TAB` já cobria o começo da luta** (`proxima_leitura =
    inicio + CARENCIA_APOS_O_TAB`) — conferido, não foi preciso mexer.
  - **O portão do nome nos guardas e a ausência de portão no boss não foram
    tocados.** O que sumiu foi o TAB por leitura ambígua, não a regra.
- **LOG DA FASE DOS GUARDAS** (pedido do usuário para acompanhar).
  DEBUG para a linha de fato do alvo (fonte/veredito, troca de alvo), INFO
  quando um TAB é SEGURADO, e um resumo da fase no fim. O log `ALVO` detalhado
  (que traz o ponteiro) **foi removido** — ele poluía e mascarava `None` como
  `hp_tela=0.0%`. Quem precisa do ponteiro lê `texto_do_ponteiro()` isoladamente
  (testado em `test_cegueira_no_instante_da_mortal.py`).
  - **Volume é requisito, não detalhe.** O arquivo de texto guarda 500 linhas no
    total; uma fase que gere 130 empurra todo o resto para fora. Duas versões
    afogaram antes de a terceira ficar: a primeira repetia "TAB segurado" a cada
    leitura (43 linhas numa luta), a segunda usava o texto COM o HP como chave
    de mudança — e o HP muda a cada golpe, então toda leitura contava como
    mudança. Por isso `LeituraDoAlvo.chave` é `fonte/veredito` **sem os
    números**: a descida normal de vida rende UMA linha.
  - **O `lido=` do log NÃO é `target_name()`.** É `_ultimos_nomes_do_alvo`, o
    que o próprio veredito leu (`alvo_e_oponente`). Imprimir a outra leitura ao
    lado do veredito produzia linhas como `veredito=ilegivel lido='Gun Witch'`.
  - **O aviso de "bati sem ler o nome" usa flag própria**, não `sem_ler_desde`:
    mexer no relógio ali reiniciaria a carência e o bot passaria a bater de 3 em
    3 segundos — mudança de comportamento disfarçada de log.
- **A simulação de combate** (`tests/test_virada_de_fase_nao_e_vitoria.py`; o test_combat_vigia_do_alvo.py citado aqui antes nunca entrou no git — conferido em 25/09/2026) roda
  `atacar_ate_sair_de_combate` INTEIRO com o jogo dublado e **relógio
  determinístico começando em 10.000,0** — `0.0` é o sentinela de
  `falso_desde`, `sem_ler_desde` e `proximo_ataque`, e um relógio em zero torna
  "ainda não aconteceu" indistinguível de "aconteceu no instante 0". Prova alvo
  nunca adquirido, cadáver repetido, leitura falhando no meio, mob a 2%, morte
  real, virada para mob errado e o volume do log — mais o caminho por memória,
  que está desligado e por isso precisa de teste para não apodrecer. **Tem TRÊS
  DENTES**: reintroduzem o "não sei = morreu", o portão aplicado só à ausência
  (o defeito exato do log de produção) e o portão que não fecha no TAB; os três
  exigem que a simulação reprove.
  - **O teste do padrão do interruptor lê o valor no IMPORT**
    (`FONTE_PADRAO_NO_CODIGO`), antes da fixture que força `"tela"` em todo
    teste. Perguntar a `combat` depois da fixture deixaria o teste vazio — ele
    provaria a fixture, não o código.


---

## 18/08/2026 — o portão que segurava o TAB, e por que o conserto NÃO foi ligado

Relato: *"tem vezes onde ele não está acionando o TAB, os mobs ainda estão vivos
mas não está dando TAB neles, às vezes para no primeiro TAB. Principalmente
quando o usuário cadastra o AOE."*

### O que o log mostra (03:46, `logs/dev/blazes-dev.jsonl`)

    03:46:04  barra=0.0000  hp_memoria=100  ja_tive_alvo=False  -> nao-sei
    03:46:06  barra=0.0000  hp_memoria=100  ja_tive_alvo=False  -> nao-sei
    03:46:07  ausencia      hp_memoria=100  -> TAB segurado (26o)
    03:46:10  barra=0.9979  hp_memoria=100  -> vivo    <- 6 s depois
    ...
    FASE 1 encerrada: ausencias NAO contadas como morte=35

**35 mortes recusadas numa fase**, com 6 segundos seguidos de paralisia. É o
portão ("só relato a morte de um alvo que eu vi VIVO") fazendo o oposto do que
foi feito para fazer.

### Por que o AoE piora

Com AoE o dano bate nos quatro Gun Witch ao mesmo tempo. Eles morrem FORA DE
ORDEM, e o alvo seguinte frequentemente já está morto quando a seleção chega
nele. O portão nunca o vê vivo, e o TAB nunca sai. **Com AoE isso é a regra, não
a exceção** — que é exatamente a correlação que o usuário observou.

*(O AoE ESTÁ ligado na fase, `usar_aoe=True` na linha 1766 dentro de
`_fase_dos_guardas_com_tab`. Houve um engano meu ao ler a linha 1823, que é do
caminho DESLIGADO `_fase_dos_guardas_sem_tab` — não há divergência entre código e
doc aqui.)*

### O conserto óbvio funciona e reintroduz o defeito de 13/08

Prazo no portão: fechado há mais de N segundos em combate ⇒ a morte lida vale.
Implementado, e a simulação pegou na hora
(`test_o_cadaver_repetido_gasta_UM_TAB_e_nao_tres`): com a barra em 0.0 para
sempre, o prazo gasta os TRÊS TAB do orçamento no cadáver — o defeito medido em
13/08.

**A razão é de fundo, não de ajuste.** "Cadáver para sempre" e "adquiri um
cadáver novo" produzem o MESMO OBSERVÁVEL: barra 0.0 com o portão fechado.
Nenhum prazo separa os dois, porque a diferença entre eles não é TEMPO, é
IDENTIDADE — no primeiro é o mesmo alvo, no segundo é outro.

### O que foi entregue, e o que ficou esperando medição

- `USAR_PRAZO_DO_PORTAO = False`. O caminho fica inteiro e é exercitado com o
  interruptor FORÇADO (`test_alvo_nunca_adquirido_GASTA_TAB_depois_do_prazo`),
  para ligar de volta não ser ligar código não rodado.
- Os DOIS defeitos ganharam teste, separados pelo tempo: nenhum TAB antes do
  prazo (o de 13/08) e TAB depois dele (o de 18/08).
- **O PONTEIRO NÃO ESTA NO LOG DE PRODUÇÃO.** O método `instrumentar()`,
  que registrava `ptr=0x...` a cada leitura, **foi removido** — o ponteiro passa
  a ser lido isoladamente via `texto_do_ponteiro()` quando o usuário precisa, nunca
  no loop de combate.

O ponteiro não decide porque não há medição que autorize: o log de produção
mostrava a memória errando nas DUAS direções — `barra=0.9979 | hp_memoria=0` e
`barra=0.0000 | hp_memoria=100`. Decisão do usuário: *"eu só vou conseguir deixar
a memória decidir quando ela for 100% confiável, e hoje não consigo ver isso;
atualmente pela tela ele acerta mais do que pela memória."*

Com algumas fases reais registradas, a inspeção de ponteiro (via
`texto_do_ponteiro()`) responde por medição: o ponteiro muda quando o alvo troca
de verdade? Fica igual enquanto o alvo é o mesmo? Se sim, ele passa a ser o
discriminador de identidade e o prazo pode ser ligado com ele ao lado — e aí dá
para identificar cada mob individualmente, que é o objetivo maior.

**É o oposto do que custou os dois dias da DLL de cursor**, onde o mecanismo foi
consertado com base numa hipótese nunca medida.

### Efeito colateral bom

O dublê `_Ctx.press` da simulação não aceitava o `hold` que a produção passa no
TAB (`ctx.press(tecla, 0.15)`), e isso mantinha **5 testes** reprovando por
`TypeError` — escondendo o que eles provavam. Corrigido: as pendências caíram de
9 para 4.

---

# A cura por skill, e por que ela NUNCA entra em batalha

**Data**: 2026-08-19. Pedido do usuário, com uma correção dele no meio da
implementação (ver "A poção de batalha volta", abaixo).

## O F1 é o centro de tudo

Skill em si mesmo precisa de alvo, e o alvo é o próprio personagem — por isso
existe `auto_selecionar()` (F1) antes da cura e dos buffs, e está escrito no topo
do `combat.py` desde antes disto.

**F1 no meio da luta LARGA o alvo.** E o engajamento do boss depende de quem está
selecionado: *"TAB sozinho não engaja, quem engaja é o golpe"*.

Isto era **bomba armada, não defeito ativo**. O `maintain(em_luta=True)` é
chamado de seis pontos dentro de luta — o laço de ataque, os guardas, as duas
fases do boss —, mas sem tecla de cura configurada ele só bebia poção, e poção
não precisa de alvo. **O F1 passaria a sair no meio da luta do boss no dia em que
alguém configurasse a tecla de cura da Fairy**, que é exatamente o que esta
mudança introduziria.

Decisão do usuário: **em batalha o personagem não se cura.** Durante a luta o bot
luta; a cura mora nos intervalos, que é onde ele já parava para se curar.

## A poção de batalha volta, e é RESERVA

A primeira versão da regra tirava tudo da batalha. O usuário corrigiu: a poção de
batalha **pode** ser usada em combate — é a única consumível possível ali —, mas
só abaixo de **15%** e só se houver tecla configurada.

Então `battle_hp_pct` passou de **90% para 15%**. Aos 90% o bot bebia poção de
batalha quase o tempo todo durante a luta; aos 15% ela é o susto, não a
manutenção.

**Vizinhança que importa:** `emergency_pct = 25` aborta a luta. Com os dois nos
valores de fábrica a abortagem chega ANTES da poção, o que é o desfecho certo e
faz a poção ser último recurso de verdade. Subir `battle_hp_pct` acima de
`emergency_pct` inverte isso — é escolha legítima, mas é escolha.

## Apertar e conferir têm cadências opostas

O pedido original era apertar a cura a cada 0,1 s até bastar. A cura tem **1,6 s
de conjuração** (informado pelo usuário), então 0,1 s são **dezesseis apertos por
conjuração**. Dois modos de falha, e o segundo é o grave:

* custo: dezesseis mensagens onde uma basta, com risco de lag que o próprio
  usuário levantou;
* **se o cliente reinicia a conjuração ao receber a tecla de novo, o laço nunca
  completa uma cura** — e parece estar trabalhando o tempo todo. Isso não foi
  medido, e não se deixa em pé um caminho que depende de não ser verdade.

A separação: **apertar fala com o jogo; conferir é leitura de memória e não toca
nele.** Cada um com a sua cadência.

    aperta ....... uma vez por conjuração (1,6 s + 0,6 s de margem)
    confere ...... a cada 0,1 s, e a vida SUBIR encerra a espera

**Medido em simulação** (`tests/test_cura_por_skill.py`, com o cliente falso
respeitando a conjuração): para levar 50% a 85% curando 15% por conjuração, o
laço correto aperta **3 vezes**; a versão que aperta na cadência da conferência
aperta **400**. Mesma cura, 133× menos mensagens.

É a regra da casa aplicada: *"onde havia espera cega, agora se PERGUNTA"*.
Conjuração que termina em 1,4 s não paga os 0,2 s que faltavam para o relógio
fechar, e conjuração interrompida é descoberta em 0,1 s em vez de 2,2 s.

## O teto é por TENTATIVA SEM EFEITO, não por relógio

`max_heal_seconds = 120` foi dimensionado para poção — o comentário dele diz
"cada poção leva 15 s, então isto dá oito". Para skill esse número não significa
nada, e um teto por relógio faria uma conta sem mana passar dois minutos
apertando tecla à toa.

A pergunta certa não é *"já passaram 120 s?"*, é *"a vida subiu?"*. Três
conjurações seguidas sem subir significam que a cura não está saindo — recarga,
mana ou interrupção. Custa ~7 s descobrir, contra 120 s. `max_heal_seconds` fica
como rede externa, para o caso de cada conjuração curar um tico com o alvo longe.

`SUBIDA_MINIMA_PARA_CONTAR = 1.0` existe para que regeneração natural e ruído de
leitura não contem como sucesso — sem isso o laço giraria para sempre achando que
progride.

## Números, e o que foi medido

| constante | valor | origem |
|---|---|---|
| `SEGUNDOS_DE_CONJURACAO_DA_CURA` | 1.6 | **informado pelo usuário** |
| `MARGEM_DA_CONJURACAO` | 0.6 | não medido — folga de latência |
| `INTERVALO_DE_CONFERENCIA` | 0.1 | não medido — pedido do usuário, e é só leitura |
| `TENTATIVAS_SEM_EFEITO` | 3 | não medido |
| `SUBIDA_MINIMA_PARA_CONTAR` | 1.0 | não medido |
| `battle_hp_pct` | 15 | **decisão do usuário** |

**Só o 1,6 s é medição.** Os outros quatro são ponto de partida, e o log registra
cada cura — vida antes, vida depois, quantos apertos, por que parou — para que a
primeira noite de operação produza os números de verdade.

## `prefer_heal_skill` saiu

Era um segundo lugar para dizer o que a tecla já diz. O `combat.py` já escrevia a
regra: *"Sem perfil de classe: quem tem tecla de cura tem cura. A configuração é
a declaração."* Dois lugares dizendo a mesma coisa acabam discordando — e o
desfecho seria uma tecla configurada que não é usada, sem nenhuma pista do porquê.
Saiu das duas interfaces e do `config.json`; chave antiga é lida e ignorada.

Junto: **a poção de HP deixou de ser tecla obrigatória** quando há tecla de cura.
Exigir que uma Fairy cadastre uma poção que nunca vai usar é pedir configuração
falsa. Uma das duas tem que existir.

## Reverter

`MODO_DE_CURA = "pocao"` no topo do `combat.py`. O caminho anterior está inteiro
em `_manter_vida_caminho_antigo` e tem teste próprio, para que voltar atrás não
seja ligar código não testado. **Atenção:** aquele caminho usa a skill de cura em
batalha, com F1 — ligá-lo reintroduz o F1 no meio da luta do boss.

---

# A Break Soul só na segunda fase do boss

**Data**: 2026-08-19. Pedido do usuário.

## Ela já esteve errada de duas formas opostas

1. **Nunca era apertada.** A tecla era gravada no `config.json`, aparecia na
   janela, era listada como opcional na validação — e nenhuma linha do bot a
   usava. O texto de ajuda do bloco já prometia que tudo ali entrava em rotação.
2. **Passava a sair SEMPRE.** O conserto do primeiro erro a acrescentou à
   rotação sem condição nenhuma: bastava a tecla existir. Ou seja, ela saía
   contra os quatro Gun Witch, contra qualquer mob do caminho e contra a
   primeira fase do boss.

O segundo estado é o que esta decisão corrige, e o custo dele é o mesmo que já
tinha tirado o AoE da luta dos guardas — está escrito no `_rotacao_de_ataque`:
*"mana é exatamente o que falta na segunda fase do boss, logo depois"*. Gastar a
Break Soul antes é chegar na luta que decide a run com ela em recarga.

## Como a fase é sabida

`fight_boss` já contava `fases_vistas`, e a virada é detectada por **duas formas
independentes**:

* **forma A** — o HP SUBIU no mesmo endereço (a segunda fase se cura instantânea,
  e o zero pode nunca aparecer em leitura nenhuma);
* **forma B** — a mira passou para uma entidade NOVA com vida.

As duas chamam `_marcar_fase(fases_vistas)`. Ele é um método, e não uma
atribuição solta em cada ramo, exatamente porque são dois lugares: escrever a
mesma linha duas vezes é o convite para consertar uma e esquecer a outra.

## A bandeira é POR LUTA, e isso não é detalhe

`_na_segunda_fase_do_boss` é atributo de instância, e o `CombatEngine` **vive
entre as runs**. Uma bandeira que sobrevivesse ao fim da luta faria a Break Soul
sair contra os guardas da run SEGUINTE — e esse defeito seria **intermitente**:
some ao reiniciar o bot e só aparece a partir da segunda run, que é a categoria
mais cara de defeito para diagnosticar.

Por isso `fight_boss` virou uma casca fina que baixa a bandeira na entrada e num
`finally`, chamando `_lutar_contra_o_boss` no meio. **`finally` e não "zera no
fim do laço"**: o laço tem seis saídas, e a que interessa é justamente a que
ninguém lembra — a exceção (parada pelo usuário, queda, watchdog).

Travado por `tests/test_break_soul_so_na_fase_2.py`, com dente nos dois: a
rotação antiga faz o teste da regra reprovar, e um `fight_boss` sem `finally`
faz o teste do vazamento reprovar.

## O que NÃO mudou

Ela **acrescenta** à rotação, não substitui ninguém — mesmo desenho do AoE. Com
um ataque, AoE e Break Soul configurados, a rotação na fase 2 fica de três
teclas, então a Break Soul sai em uma investida a cada três. Se ela precisar sair
mais que isso, é outra decisão e outro número.

## Reverter

`USAR_BREAK_SOUL_SO_NA_FASE_2 = False` no topo do `combat.py` devolve o
comportamento anterior (sai sempre que a tecla existir), e há teste cobrindo esse
caminho para que ele não apodreça.

### CORREÇÃO: a bandeira estava sendo levantada em CÓDIGO MORTO

**19/08/2026, relatado pelo usuário:** *"é quando roda esse log que trocou para a
fase 2 e deve começar a tentar usar a Skill Break Soul, apesar de termos
configurado isso anteriormente, não funcionou."*

A primeira versão levantava `_na_segunda_fase_do_boss` nos dois pontos em que
`fight_boss` incrementa `fases_vistas` — que é onde a contagem de fase mora, e
parecia o lugar óbvio.

**`fight_boss` está desativado.** A chamada dele em `routine.py:1452` é
comentário; quem luta contra o boss é `fase_do_boss_por_combate`
(`routine.py:1830`), e ela não conta fase nenhuma — o que encerra a luta é a
flag de combate.

Ou seja: a bandeira nunca subia, e a Break Soul nunca saía. O código estava
correto, testado e ligado no lugar que não roda.

**Onde ela sobe agora:** em `_registrar_troca_de_fase`, na mesma linha em que sai
o log que o usuário citou. É o único ponto do caminho vivo que percebe a
passagem — a struct do boss é trocada (a fase 1 some por volta de 7%, a struct é
liberada e nasce outro `Blaze Skull Marshal` de nível 51).

**Por que ali não vaza para os guardas:** `registrar_troca_de_fase` é passado por
UM chamador só, `fase_do_boss_por_combate`. Fora da luta do boss o método nem é
chamado.

**E a bandeira desce no começo de `atacar_ate_sair_de_combate`**, junto com
`_struct_do_alvo`, que é onde toda luta começa. O `finally` do `fight_boss`
continua lá, mas pelo mesmo motivo de antes ele não zera nada: código morto não
zera. Sem essa segunda correção a bandeira de uma run sobreviveria para a luta
dos guardas da seguinte.

**A lição, e ela não é sobre este defeito:** o método se chamava
`_registrar_troca_de_fase` e o docstring dele abria com *"Só LOG: não decide
nada, e é de propósito"*. Foi essa frase que me fez procurar a decisão em outro
lugar — e a decisão não existia em lugar nenhum, porque ninguém precisava dela
até agora. **Nome e docstring são o mapa que a próxima pessoa usa; quando o mapa
diz "aqui não tem nada", ninguém cava.** Os dois foram reescritos junto com o
código.

Travado por `test_a_troca_de_struct_do_boss_levanta_a_bandeira` e
`test_depois_da_troca_a_break_soul_entra_na_rotacao`, que exercitam o caminho
VIVO — e por `test_a_bandeira_desce_no_comeco_de_TODA_luta`, que lê o AST.

---

# `EnemyDead.png`: a confirmação final da morte do alvo

**Data**: 2026-08-19. O usuário trouxe a imagem: *"identifique os momentos que
verifica a morte de algum mob e use essa imagem como confirmação final... pois
tem vezes que a verificação atual falha e acaba não dando os TABs necessários,
por exemplo nos Gun Witch."*

## O impasse que ela resolve estava medido e sem saída

O portão do `VigiaDoAlvo` é UNIVERSAL desde 13/08/2026 -- *"só se relata a morte
de um alvo que se viu VIVO"*. Foi correção de um defeito caro: o ponteiro
devolvia o cadáver depois do TAB e queimava os três TAB do orçamento em três
segundos.

Ele criou o impasse oposto, medido no log de 18/08/2026: **35 mortes recusadas
numa fase, 6 s seguidos sem TAB com mobs vivos.** Pior com AoE, que mata os
quatro Gun Witch fora de ordem e faz o alvo seguinte ser adquirido JÁ MORTO --
nunca visto vivo, portão fechado, morte recusada, TAB não sai. É exatamente o
sintoma que o usuário relatou.

`PRAZO_DO_PORTAO_FECHADO` foi escrito para desempatar e está DESLIGADO, e a razão
registrada era uma parede: *"'cadáver para sempre' e 'cadáver novo' são o MESMO
observável, a diferença não é tempo, é IDENTIDADE. O ponteiro é o único sinal de
identidade."*

## Por que a imagem passa por onde o prazo não passava

**O marcador está no QUADRO DO ALVO, e o quadro do alvo mostra a seleção ATUAL.**

É precisamente a propriedade que o ponteiro não tinha, e que causou o defeito de
13/08: ele continuava devolvendo o cadáver antigo depois do TAB. A tela não --
quando a seleção muda, o quadro muda.

Então "o marcador está lá" significa **"o que eu tenho selecionado NESTE instante
está morto"**. É um sinal de identidade, e é por isso que ele pode furar o
portão: o portão existe para impedir que a morte do alvo ANTERIOR seja contada, e
esta leitura não é do anterior.

Não era necessário um ponteiro. Era necessário um sinal ligado à seleção, e a
tela já era um.

## É CONFIRMAÇÃO FINAL, e isso não é detalhe de implementação

Ela só é consultada quando o veredito normal devolve `None`. Barra desenhada
continua decidindo, memória continua só no log, e nada do que funciona é tocado.

Três consequências, todas travadas por teste:

1. **Não atropela a barra.** Barra cheia com o marcador na tela = alvo VIVO. Se
   ela atropelasse, um falso positivo do template mataria um mob de vida cheia e
   o TAB trocaria de alvo no meio da luta.
2. **`False` não é "está vivo".** Ausência do marcador é ausência de informação.
   Tratar ausência como resposta é o defeito original desta classe.
3. **Só é LIDA quando a barra falha.** Casar template a cada 0,3 s durante a luta
   inteira seria custo por nada -- a barra ausente é o único caso em que o
   veredito pode sair inconclusivo com a tela disponível.

## A busca é restrita à faixa do quadro do alvo

`FAIXA_DO_QUADRO_DE_ALVO`, a mesma de `vida_do_alvo`. E o motivo é o que aquele
comentário já registrava: **o quadro do PRÓPRIO personagem é igual e fica no
canto superior esquerdo.** Varrer a tela inteira faria "eu morri" ser lido como
"o mob morreu" -- e o bot apertaria TAB com o personagem no chão.

`LIMIAR_DO_MARCADOR_DE_MORTE = 0.85`, errando para MAIS: falso positivo declara
morte e gasta um TAB; falso negativo só devolve o comportamento de hoje.

## Vale para qualquer mob, inclusive o boss -- mas não decide o boss

O usuário observou que a imagem identifica qualquer mob morto, até o boss. Ela
já cobre todos: a leitura mora em `_alvo_morreu`, que é compartilhado por toda
`atacar_ate_sair_de_combate` -- guardas, boss e qualquer luta.

**E na luta do boss ela não gasta TAB**, porque só a chamada dos guardas passa
`tabs_ao_morrer=TABS_NOS_GUARDAS`; o boss usa o padrão `0`. Isso preserva a regra
medida: *"o boss só é dado por morto quando SAI DE BATALHA, nunca por HP zerado:
a segunda fase troca a struct, perde a seleção e o HP sobe."* Um marcador visível
entre as fases não pode virar vitória.

## O dublê da simulação precisou crescer

Quatro testes reprovaram com `AttributeError: '_Ctx' object has no attribute
'templates'`. A correção foi no DUBLÊ, não na produção: `ctx.templates` existe no
`BotContext` de verdade, e usar `getattr(ctx, "templates", None)` seria moldar o
código ao dublê e esconder uma dependência real -- o mesmo erro que já escondeu
cinco testes reprovando aqui antes.

## Travas

`test_combat_vigia_do_alvo.py` ganhou seis casos que rodam pela SIMULAÇÃO
completa, incluindo o **controle negativo** (mesmo cenário, marcador ausente,
nenhum TAB) -- sem ele o teste principal provaria só que algum TAB saiu, não que
foi o marcador. E `test_marcador_de_morte.py` cobre a leitura, com o caso do
quadro do próprio personagem.

---

# O top-up antes do boss: três defeitos no mesmo trecho

**Data**: 2026-08-19, relatado pelo usuário: *"ao usar a poção de vida antes do
boss, ele não está ficando os 15 segundos parado sentado; é importante ficar até
o final e conferir se está com a vida cheia para matar, pois quem precisou da
poção vai precisar se curar -- normalmente é um personagem mais fraco, que
depende de estar full vida para começar a luta contra o boss."*

Uma frase, três defeitos.

## 1. Não sentava

O código apertava a poção e esperava. `k.sit` não era tocado em nenhum momento
ali -- quem senta é o `heal_to_full`, que roda FORA da instância. "Parado
sentado" nunca aconteceu nesse trecho.

Agora senta **uma vez**, antes da primeira poção, com o estado LIDO por
`is_sitting()` antes de apertar -- `sit` é interruptor, e apertá-lo sentado
LEVANTA.

**E não levanta no fim.** O usuário confirmou que qualquer movimentação, ataque
ou montaria levanta o personagem, e o trajeto ao boss vem logo depois. Uma tecla
de levantar aqui seria um interruptor a mais para dar errado.

## 2. A espera saía CURTA -- e este é o defeito invisível

`ctx.tick(15.0)` passa o valor por `jitter(base, 0.15)`:

    15 s  ->  entre 12,75 s e 17,25 s

Nas vezes em que sorteava baixo, **faltavam 2,25 s do temporizador da poção**.

O jitter existe por um bom motivo -- delays perfeitamente fixos são assinatura de
automação -- mas estava sendo aplicado a uma **duração que o JOGO exige**, não a
uma cadência nossa. É a mesma classe de erro que este arquivo já registra em
outro lugar: número medido que escapou para um contexto onde não vale.

E era invisível: nada no log dizia "faltaram 2 s". O sintoma era só "a poção
rendeu menos do que devia", que ninguém atribui a um sorteio.

**A correção é o prazo por RELÓGIO.** As fatias podem jitterar à vontade; quem
manda é `time.time()`, então o total nunca sai curto.

### O teste precisou de um dublê ADVERSÁRIO

A primeira versão do teste não pegava nada. O dublê avançava o relógio
exatamente pelo valor pedido, então o código defeituoso (`ctx.tick(15.0)`)
avançava 15 s no teste e passava.

**Um teste que não pode falhar no defeito que nomeia é pior que teste nenhum** --
ele dá a impressão de cobertura. O dublê passou a avançar pelo **pior sorteio**
(0,85x), e com ele o método antigo produz 12,75 s e reprova. Teste
determinístico tem que modelar o adversário, não a média.

## 3. Não conferia nada

Logava `"Vida depois do top-up: X%"` e seguia ao boss com qualquer X. Uma poção
num personagem a 20% não chega perto de cheio, e o gatilho só dispara abaixo de
50%.

Agora: **uma poção de cada vez** até `ALVO_DO_TOPUP_ANTES_DO_BOSS = 100.0`, e
**sai no instante em que enche** -- decisão do usuário: *"caso atinja os 100%
pode continuar, sem ter que esperar os 15 segundos totais"*. Uma de cada vez
porque cada poção rende o efeito completo; disparar várias juntas desperdiça item
comprado. Mesmo desenho do laço de `curar_ao_entrar`.

Teto por `max_heal_seconds`: sem poção na bolsa, insistir prenderia a run com o
boss esperando. Estourar é aviso, e a run segue.

## A regra nova: precisou de poção e morreu ⇒ BC desligado

Também do usuário: *"caso ele precisou se curar e depois aconteça do personagem
morrer, você deve parar o bot BC daquela conta, pois deve estar com falta de item
essencial para rodar o bot."*

O raciocínio é bom e vale registrar: chegar no boss abaixo de 50% já é sinal de
run apertada; **morrer depois disso, tendo gasto poção, aponta estoque
acabando** -- e uma conta sem poção não termina run nenhuma. Insistir a noite
inteira gasta a instância, o item que ainda resta e o tempo, sem fechar um boss.

Desfecho igual ao que a venda já usa quando não há tecla de retorno: `bc_farm`
desligado e salvo, **a conta fica online** com relogin, e o checkbox desmarca nas
duas interfaces. A marca é POR RUN e só é levantada pelo top-up -- morte por
outra causa não desliga nada.

### O sentar SAIU do top-up (19/08/2026)

A primeira versão sentava antes de beber. O usuário mandou tirar: *"antes de usar
a poção de cura não precisa sentar... a poção já faz sentar. O sentar pode ser
usado em outros momentos caso necessário."*

E é bom que tenha saído. **`sit` é interruptor**, e cada aperto desnecessário é
uma chance de o personagem terminar no estado ERRADO. Com a poção sentando
sozinha, apertar a tecla antes só acrescentava um caminho para dar errado.

Não ficou como interruptor `= False`: a regra da casa existe para preservar
comportamento MEDIDO que sai de operação, não para guardar código que o usuário
recusou antes de rodar. O `heal_to_full`, fora da instância, continua sentando
onde faz falta.

---

# A segunda fase do boss vista NA TELA: a barra amarela

**Data**: 2026-08-19. Pedido do usuário: *"caso encontre isso em algum momento da
luta contra o boss é pq entrou na segunda fase e é o momento de usar a Break Soul
caso esteja configurada a tecla."* Modelo: `data/templates/boss_2_fase.png`.

E o esclarecimento que veio depois, e que muda o desenho: *"a segunda fase do boss
tem 2 barras de vida, uma amarela que é a primeira e depois que terminar a amarela
vem a barra vermelha, normal como outros mobs; aí quando zera a barra vermelha ele
morre, e fica como naquela imagem que identifica a morte."*

## O que o recorte É, medido

57×22 px, e não foi preciso adivinhar onde ele mora. Rodando os **mesmos testes de
cor do `vida_do_alvo`** sobre ele, linha por linha:

| linhas | "azul" | "vermelho" | o que é |
|---|---|---|---|
| 1 | 0% | **100%** | a borda superior, que `vida_do_alvo` descarta |
| 2–9 | 0% | **0%** | a barra de VIDA — e ela é AMARELA |
| 15–20 | **100%** | 0% | a barra de MANA |

A geometria fecha com as constantes que já estavam no `vision.py`: mana começando
em y=15 põe `fim = 15 - LINHAS_ENTRE_HP_E_MP = 8` e `comeco = 1`, então a faixa de
vida que o código lê é `[2:9]` — exatamente as linhas amarelas. Ou seja **o amarelo
ocupa a mesma fatia de tela que o vermelho ocupa nas outras lutas**, o que confirma
que ele é a primeira vida da fase 2 e não um enfeite ao lado.

## O sinal tem PRAZO, então a bandeira é LATCH

O amarelo existe só no primeiro trecho da fase 2. Duas consequências:

1. **Nada baixa a bandeira.** A leitura roda a cada 1 s **enquanto a bandeira está
   baixa** e para depois — uma barra de vida inteira de boss é folgada para essa
   cadência. Se um `False` pudesse baixá-la, a Break Soul sairia de rotação
   exatamente na metade final da fase 2, a que decide a run.
2. **Ausência de amarelo não é fase 1** — pode ser fase 2 já no vermelho. Mesma
   regra do `alvo_morto_na_tela`: só o `True` age.

## EM COR, e isso é medição, não gosto

    o modelo contra SI MESMO          cinza 1.000   cor 1.000
    o modelo contra a FASE 1          cinza 0.874   cor 0.792
    fase 2 degradada (jpeg 70+ruído)                cor 0.985
    fase 2 com 12% menos brilho                     cor 1.000

**Em cinza a fase 1 marca 0,874** — acima do 0,85 que este projeto usa para
marcador de UI. Em cinza a Break Soul começaria a sair no primeiro segundo da luta
do boss, que é *exatamente* o defeito que ela existe para evitar. É a mesma lição
que `TemplateLibrary.load_color` já traz medida: forma igual e matiz diferente é
indistinguível em luminância.

Em cor sobra um vão limpo entre 0,792 e 0,985. `LIMIAR_DA_FASE_2_DO_BOSS = 0.92`
fica no meio dele, e é o mesmo valor que o `package_courage` já usa em cor.

(A fase 1 da medição é **sintética**: o mesmo recorte com a faixa de vida
recolorida para o vermelho saturado que o `vida_do_alvo` procura, preservando a
luminância linha a linha. O que ela mede é a pergunta certa — *cinza separa duas
barras de mesma forma e matiz diferente?* — e a resposta é não.)

## É o SEGUNDO sinal, não o substituto

A troca de struct (`_registrar_troca_de_fase`) continua valendo e continua sendo a
primeira a falar. Os dois levantam a MESMA bandeira por `_marcar_fase`, que é
idempotente — o segundo a chegar não repete o log.

Redundância só vale quando as duas metades falham por motivos **diferentes**, e
aqui valem: o sinal por struct depende de a memória responder E de o nome do boss
ser legível no instante exato da troca; este depende só da tela.

## A CONSEQUÊNCIA QUE NÃO ERA O PEDIDO: `vida_do_alvo` LÊ 0.0 NA VIDA AMARELA

Se a primeira vida da fase 2 é amarela, ela falha no teste `r > g * 1.6` e a fração
de "vermelho" na faixa sai ZERO. Medido, colando o recorte na faixa do quadro do
alvo com largura de barra realista: **`vida_do_alvo` devolve `0.0`** — que naquele
módulo significa *"barra vazia com o quadro presente: o mob morreu"*.

**NÃO é defeito ativo, e é por sorte de desenho:** o veredito de morte só é
consultado quando quem chama pede TAB (`if tabs_ao_morrer and ...`), e a luta do
boss não passa `tabs_ao_morrer` — vale o default ZERO, porque quem encerra o boss é
SAIR DE BATALHA. Então ninguém pergunta, e a leitura errada nunca é usada.

**É bomba armada, e fica REGISTRADA em vez de "consertada".** Alargar o teste de
vermelho para aceitar amarelo mexeria justamente no número que descarta o **fundo
alaranjado da caverna** (vermelho alto com verde alto junto — está comentado no
`vida_do_alvo`), e amarelo é exatamente isso. Trocaria um defeito dormente por um
falso positivo na leitura de vida dos guardas, que é caminho quente.

Dois testes prendem a bomba: um afirma o `0.0` (e que a fase 1 sintética no mesmo
lugar lê vida cheia, provando que o zero vem da COR e não da geometria), e o outro
lê o AST para reprovar se o default de `tabs_ao_morrer` deixar de ser 0 ou se a
luta do boss passar a pedir TAB.

## Testes: `tests/test_fase_2_pela_tela.py`, 19 casos

Com dente — seis defeitos injetados, seis reprovações: limiar frouxo, casamento em
cinza, faixa virando a tela inteira, bandeira baixando no `False`, a leitura saindo
de dentro do `if registrar_troca_de_fase`, e o modelo carregado em cinza.

O último merece nota: o portão é lido **pelo AST**, e não por texto — comentário
citando o nome não conta. Fora do `if`, a barra amarela poderia levantar a bandeira
na luta dos guardas, e a Break Soul vazaria para lá.

---

# A virada de fase virava VITÓRIA, e o bot ia embora com o boss de pé

**Data**: 2026-08-19. Relatado pelo usuário: *"eu vi acontecer visualmente isso,
de entender que foi para a segunda fase e ele tentar usar o auto pick, daí abriu o
inventário e foi para o Skull Herald para sair da cave, só não saiu pq eu desativei
o bot e impedi."*

## O log, conta `creubo`

    16:38:39  Em combate (boss) depois de 0.0s esperando
    16:39:01  A flag de combate baixou em boss (22s de luta, 98 golpes).
              Confirmando por 2.5s antes de encerrar.
    16:39:03  Fora de combate confirmado: 2.5s contínuos com a flag baixa
    16:39:03  Sai de combate no boss -- considerando o Blaze Skull Marshal
              derrotado
    16:39:04  package_courage: 1 clique -> BOSS levou 25.5s -> SAIR
    16:39:07  Saindo da cave pelo Skull Herald

O `fase_do_boss_por_combate` listava esse caso no próprio docstring como *"flag
baixando com o boss vivo e o personagem vivo -- **não foi observado** e não tem
como ser distinguido sem voltar aos ponteiros de alvo"*. **Agora foi observado**, e
deu para distinguir sem ponteiro nenhum.

## NÃO foi a detecção da fase 2

Vale registrar porque a correlação era convincente — o bot foi embora no instante
em que o boss virou de fase. Mas:

* `grep "SEGUNDA FASE VISTA NA TELA"` no log: **zero**;
* `grep "Break Soul entra na rotação"`: **zero**;
* `combat.py` foi salvo às **16:44:40**, depois do reinício das **16:38:38** — o
  processo que lutou não tinha o código novo;
* e `_marcar_fase(2)` só escreve um `bool` e uma linha de log.

Quem encerrou foi a confirmação de saída de combate, que é anterior a tudo isso.

## O mecanismo: o bot fica PASSIVO justamente na virada

O bloco do golpe tinha `if not (falso_desde and ja_entrou)`, ou seja **para de
bater no instante em que a flag baixa**. Isso foi correção de um defeito real
("bater depois da luta acabar convida o mob seguinte").

Só que **quem engaja a fase seguinte é o GOLPE** — está escrito no próprio
docstring do boss: *"a fase 2 pega o alvo sozinha assim que ataca"*. Parado,
ninguém reengaja: a flag fica baixa os 2,5 s inteiros, a saída confirma, e a run
segue para o loot e para o Skull Herald.

Bater durante a confirmação inverte isso. Boss em transformação volta a engajar, a
flag sobe, `falso_desde` zera, a luta continua. Boss morto não reage a golpe
nenhum, a flag fica baixa e a vitória sai igual.

## A REGRA DA VITÓRIA NÃO MUDOU

Ordem do usuário, no mesmo dia: *"o boss derrotado só deve ser considerado quando
sai de batalha."*

Então **não** há confirmação por imagem nem por ponteiro no boss. A tentação era
grande — o `EnemyDead.png` estava ali e o próprio usuário havia dito que o boss
morto *"fica como naquela imagem"*. Não foi usado. O que mudou é só o bot deixar de
ficar passivo enquanto confirma. `tests/test_virada_de_fase_nao_e_vitoria.py` fixa
o conjunto de vitórias do laço lendo o AST, para que uma quarta forma apareça na
suíte.

## SÓ NO BOSS

Parar o golpe continua valendo nos GUARDAS, onde há mob seguinte para convidar. Na
sala do boss não há, e depois dele o bot vai embora. O parâmetro
`atacar_na_confirmacao` tem default `False`, e um teste lê o AST para garantir que
só a chamada do boss pede `True`.

## O DUBLÊ PRECISOU MODELAR CAUSALIDADE

Registro de um erro meu, porque a lição é reaproveitável. A primeira versão do
teste roteirizava a flag por TEMPO — "baixa aos 22 s, volta aos 24 s" — e nesse
mundo **o caminho antigo passava**: a flag voltava sozinha antes dos 2,5 s, sem
golpe nenhum. Um teste que não pode falhar no defeito que nomeia é pior que teste
nenhum.

A flag do dublê passou a **reagir ao golpe**: baixa em `queda` e só volta se um
golpe sair depois disso. `reengaja_ao_golpe=False` é o boss morto.

Com o interruptor desligado, o teste reprova em **24,6 s** — o mesmo número do log
de produção (22 s de luta + 2,5 s de confirmação).

---

# Nos guardas, o portão de nome deixou de ENCERRAR a fase

**Data**: 2026-08-19, na sequência do defeito da virada de fase. Pedido do
usuário: *"no waypoint do Gun Witch, também só deve considerar os 4 Gun Witch
mortos quando sair de batalha, para garantir 100%, pois não pode chegar no
waypoint do boss já estando em batalha."*

## Por que chegar no boss em combate perde a run

`fase_do_boss_por_combate` abre com `esperar_entrar_em_combate("boss")`. Com a
flag **já alta**, ela devolve na hora; o bot entra na rotação contra o que estava
batendo nele; e quando **isso** morre, a flag baixa — e flag baixando é o que
declara o boss derrotado. A run vai para o loot e para o Skull Herald sem o boss
ter sido tocado.

É o **mesmo desfecho** do defeito da virada de fase, por outra porta. Daí o "para
garantir 100%".

## O que o portão de nome fazia

Ele devolvia `FimDeCombate(True, "acabaram os Gun Witch")` na **primeira leitura**
de um nome diferente — sem olhar a flag de combate. Medido no teste com a flag
presa em alta: vitória em **4,4 s**, com o bot ainda em batalha.

## O que mudou, e o que NÃO mudou

**NÃO mudou:** o portão continua **parando o golpe e o TAB** na primeira leitura.
Essa parte tem medição própria e é anterior — *"bater no que sobrou puxaria mob que
não precisava vir e gastaria tempo de run; foi assim que a run das 11:33 saiu da
rota"*.

**Mudou:** ele deixou de encerrar. O bot para de bater, para de dar TAB e
**espera a saída de combate**, que sempre foi quem decide o fim da fase.

E o mecanismo não é novo: é exatamente o do **Cemetery Guard**, que já fazia
`pode_bater = False` e seguia no laço até a flag baixar. O portão de nome passou a
usar a mesma porta. (De brinde, isso explica por que o `pos_tab_callback` dos
guardas sempre devolve `False`: ele já obedecia a esta regra.)

## O custo, dito inteiro

Parado e ainda em combate, **nada mata o que está batendo**. Se a flag não baixar,
a fase estoura `LIMITE_DA_FASE_DOS_GUARDAS` e devolve **derrota** — a run falha em
vez de seguir.

É de propósito, e é a troca que o usuário pediu: run que falha, o supervisor
repete; run que chega no boss em combate mata o boss no papel e vai embora sem ele.

`maintain` continua rodando na espera (a poção de batalha ainda sai abaixo de
`battle_hp_pct`), e a morte do personagem continua sendo detectada e devolvendo
derrota.

**A alternativa** seria continuar batendo até sair de combate — e ela contradiz a
medição da run das 11:33. Se o log passar a mostrar fases estourando o prazo aqui,
é ela que está na fila.

> **A fila andou em 26/08/2026.** Ver a seção seguinte: a alternativa entrou, e
> a trava de "não bater no que sobrou" passou a valer contra **um nome só**.

---

# A alternativa entrou: nos guardas, só o Cemetery Guard para o golpe

**Data**: 2026-08-26. Pedido do usuário, com uma run observada: *"no waypoint dos
Gun Witch em BC, tem que continuar atacando até sair de batalha, só deve continuar
se saiu de batalha; a única trava é se der TAB no Cemetery Guard, que já existe,
pois quando identifica ele aperta 'esc'. A questão é que eu vi em uma das runs
acontecer de sobrar 1 Gun Witch e não estava mais atacando — então rotaciona skill
até sair de batalha ou até identificar o Cemetery Guard como target."*

## O sintoma, e as DUAS portas que levavam a ele

**"Sobrou 1 Gun Witch e o bot não estava mais atacando"** tinha duas causas
independentes, e as duas produzem exatamente a mesma cena:

**1. O portão de nome era largo demais.** `_veredito_do_alvo` devolve `acabaram`
para **qualquer** nome que não seja `Gun Witch`, e uma única leitura assim ligava
`acabaram_os_alvos` — que segura o golpe **e** o TAB até o fim da fase. Basta uma
entidade de passagem entrar na mira (o cadáver do anterior sai da seleção, o TAB
passa por um `Cemetery Guard`, a entidade demora um ciclo a aparecer no array —
item medido em ~1 em 45) para o bot parar de bater com um guarda vivo em cima
dele. Daí só havia dois desfechos, e os dois são ruins: o Gun Witch restante mata
o personagem, ou a fase estoura `LIMITE_DA_FASE_DOS_GUARDAS` e devolve derrota.

**2. O teto de TAB barrava a troca com a flag ainda alta.** `TABS_NOS_GUARDAS = 3`
foi dimensionado para "4 mobs, o primeiro vira alvo sozinho". Uma passada de AoE
que derruba dois de uma vez faz o TAB seguinte cair em **cadáver** e gastar
orçamento à toa. Esgotado o teto, o alvo morto **fica na mira por 7 a 13 s**
(medido) e a rotação sai contra ele: teclas saindo, nada acontecendo.

## O que mudou

```
antes:  nome != 'Gun Witch'       -> para o golpe e o TAB, até o fim da fase
agora:  nome == 'Cemetery Guard'  -> ESC, para o golpe, espera a saída de combate
        qualquer outro nome       -> CONTINUA batendo
```

* **`SO_O_ALVO_PROIBIDO_PARA_O_GOLPE`** — o portão de nome só para a
  luta pelo nome que foi medido como perigoso.
* **`TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS`** — com a flag **`is True`** e o alvo
  morto, o TAB continua saindo depois do teto. `is True` e não `flag`: ilegível
  (`None`) é NÃO SEI, e não sei nunca gastou TAB nesta casa.
* **`_travar_no_alvo_proibido`** — UMA porta para as duas fontes. A da MEMÓRIA
  (nome da entidade selecionada, no portão de nome) e a da TELA
  (`cemetery_guard.png`, no `pos_tab_callback`) chegam no mesmo lugar: ESC uma
  vez, `_alvo_proibido_encontrado = True`, e o laço segue esperando a flag
  baixar. Duas cópias do ESC divergiriam em silêncio, e a que ficasse para trás
  deixaria o bot puxando o guarda por uma das duas fontes.

## Por que isso NÃO desfaz a medição da run das 11:33

A regra antiga era *"bater no que sobrou puxaria mob que não precisava vir"*. Ela
continua valendo — o que mudou é que ela deixou de ser aplicada por **exclusão**
(qualquer nome != `Gun Witch`) e passou a ser aplicada por **identificação**
(`Cemetery Guard`). E o censo do covil diz que dá para fazer isso: o Cemetery
Guard tem **5 structs com nome INLINE**, das entidades mais legíveis de lá.
Identificar custa ~3 leituras de 4 bytes, e não tem falso positivo.

Como bônus, mais TAB **exercita** a trava em vez de afrouxá-la: cada TAB passa
pelo `pos_tab_callback`, que é justamente onde o `cemetery_guard.png` é conferido.

## O custo, dito inteiro — e agora ele é o OPOSTO do anterior

Se algo que **não** é Cemetery Guard entrar na mira com o personagem em combate, o
bot bate nele e pode puxar um vizinho. A troca anterior era a inversa: o bot ficava
parado apanhando. O usuário escolheu esta, com a run na mão.

O que **não** mudou é o que fechava o defeito mais caro: a fase continua
encerrando **só** pela saída de combate (`EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS`),
então chegar no waypoint do boss já em batalha continua impossível.

Não é rajada de TAB: cada troca paga `CARENCIA_APOS_O_TAB` (2,4 s) e
`LIMITE_DA_FASE_DOS_GUARDAS` (40 s) continua sendo o teto de tudo.

## Testes

`tests/test_guardas_batem_ate_sair_de_combate.py`, seis casos — os interruptores
ligados, o nome estranho que não para o golpe, o Cemetery Guard que para (com ESC
**uma** vez e nenhuma skill depois), a porta única das duas fontes, o TAB que
passa do teto com a flag alta, e o TAB que **não** passa do teto com a flag
ilegível.

---

# Calibração de ponteiros: a TELA é o gabarito, a memória é a aluna

**Data**: 2026-08-19. Pedido do usuário: *"o ideal era fazer funcionar os ponteiros
de memória; por isso era bom criar uma forma dentro do bot dele ficar lendo as
memórias todas as runs (...) até ficar perfeito. Assim, mesmo sem eu testar
visualmente, os logs vão nos dizendo o caminho."*

E a regra que decide o desenho: *"a memória não decidir nada atualmente, mas
testar ela até ela acertar; quando ela gabaritar como a tela, nós teremos achado
os pontos certos."*

## O que isso inverte

Até aqui memória e tela eram **testemunhas do mesmo júri**, e cada modo elegia
uma e calava as outras. O custo está medido: `"imagem"` durou uma run e produziu
**69 leituras, 0 vereditos, 0 TABs, 38 s batendo num cadáver**.

Agora a tela é o **gabarito** e a memória é a **aluna**: lida, pontuada, e sem
voto (`MEMORIA_VOTA_NA_MORTE = False`).

## O fato de jogo que fechou o diagnóstico

O usuário: *"o TAB nunca pega mob morto; o que pode acontecer é que, como o AoE é
instantâneo, na hora que deu TAB ele já usou a skill e o mob morreu basicamente ao
mesmo tempo."*

Isso mata a hipótese de que o TAB não estava funcionando. Se TAB nunca mira
cadáver, então a seleção **mudou** nas três trocas do log — e `trocas_ptr=0` prova
que **o ponteiro não acompanha a seleção**. Os 3 TABs eram legítimos; o ponteiro é
que está errado.

## Os três erros da memória, medidos no mesmo log

| leitura | o que era |
|---|---|
| `hp_memoria=243` | o **PET**. `243/243` é a escala de jogador/pet, e o próprio `memory.py` documenta que cair na reserva `0x80C` significa mirar o pet |
| `hp_memoria=9` duas vezes | o mesmo valor atravessando um TAB, com `ptr` idêntico — leitura velha |
| `hp_memoria=100` por 38 s | constante enquanto o personagem batia |

**A escala é o que denuncia o pet**, e não a validação de entidade — o pet é uma
entidade legítima. Por isso ela entra no julgamento (`julgar_hp`).

## Como o placar decide

`gabaritou` exige **três coisas ao mesmo tempo**, e cada uma fecha um jeito de
aprender errado:

* **50 amostras com ZERO erro** — o que se faz com um ponteiro promovido é decidir
  morte, e morte gasta TAB. Quem erra uma em cinquenta erraria uma vez por noite,
  numa run indistinguível de uma normal no log.
* **20 amostras DISCRIMINANTES** (vida da tela entre 5% e 95%) — no waypoint todo
  mundo está com 100, e um ponteiro parado em 100 "acerta" ali sem provar nada. É
  literalmente o `hp_memoria=100` do log.
* **10 RUNS distintas** — acertar 50 vezes na mesma sessão pode ser sorte de heap.
  O episódio do `+0x60` é a prova medida de que endereço muda entre versões, e a
  struct muda entre sessões.

`reprovado` (>20% de erro em 100 amostras) **para de ser amostrado**: é a economia
que faz o custo cair conforme a calibração converge — hoje são quatro leituras de
ponteiro por leitura de combate, no fim será uma.

E `gabaritou` **não é permanente**: um erro derruba o rótulo. Cliente novo
invalida o que passou, e rótulo velho mentiria para quem confia no placar.

## Onde cada ponteiro é provado, e por quê ali

| prova | candidatos | gabarito | onde |
|---|---|---|---|
| `alvo_hp` | `0x808`, `0x80C`, `+0x60` de cada | a barra de vida na tela | **a cada leitura de combate** |
| `flag_combate` | `0x854`, `+0x60` | por CONSEQUÊNCIA: barra acima de 20% ⇒ há luta | idem |
| `modal` | `ADDR_MODAL`, `+0x60` | a caixa "It's precious item" na tela | a cada clique de venda |
| `janela_de_loot` | `ADDR_LOOT_WINDOW`, `+0x60` | o botão "Pick up all" na tela | no catador, pós-boss |

A escolha do lugar não é comodidade: **é o único ponto onde a resposta certa está
desenhada na tela no mesmo instante**. O `modal` vai no `_ponto_do_ok` do vendedor
porque aquele método *substituiu* o `modal_open()` — então é exatamente ali que se
testa se aquele ponteiro poderia voltar. O `janela_de_loot` vai no localizador do
"Pick up all" pelo mesmo motivo: o botão na tela **é** a janela aberta.

`team_size` ficou de fora: o oráculo dele depende de um template de painel de time
que ainda não existe (ver a decisão do recortador).

## A barra passou a ser lida SEMPRE, e é troca consciente

No consenso, a barra era pulada quando o marcador já fechava o caso — economia de
4,14 ms. Agora ela é o **gabarito**, então pular perde a amostra. O usuário
autorizou o tempo pedindo *"o máximo de recorrência possível"*.

Com `calibracao.ATIVADA = False` a economia volta inteira — travado por teste, para
que um caminho experimental não cobre para sempre.

## O log de dev deixou de perder evidência

O log cobre **28 minutos** (4.000 registros, 1,5 MB) e a poda jogava o resto fora.
Durante esta própria investigação, as 69 leituras que continham a prova
**desapareceram entre duas consultas**.

Agora a poda **arquiva** em `logs/dev/arquivo/blazes-dev-AAAA-MM-DD.jsonl`, num
único `writelines` por poda — não é um segundo handler recebendo `emit` por linha,
que dobraria o custo do caminho quente. Retenção de 7 dias, por DATA NO NOME e não
por mtime (o mtime muda a cada anexação, então um arquivo de ontem que recebeu
linha hoje pareceria de hoje). Provado: 300 registros emitidos num teto de 50,
**300 guardados**.

## A suíte estava escrevendo em `data/`

Pego lendo o relatório do placar: `data/calibracao.json` tinha amostras
**fabricadas por teste** (`0x808` com 53 amostras, `0x80C` reprovado com 100).
Nada daquilo veio do jogo.

O estrago não é arquivo sujo — é que aquele placar existe para decidir qual
ponteiro promover a partir de evidência REAL, e evidência inventada misturada com
evidência de produção corrompe justamente a decisão. `tests/conftest.py` agora
redireciona o placar para diretório temporário em **toda** a suíte.

## O que NÃO foi feito, de propósito

* **Nada é promovido automaticamente.** Decisão do usuário: *"quando tiver dados o
  suficiente eu volto aqui no chat, lemos tudo que foi analisado e colocamos em
  prática o que realmente funciona."* O leitor é `15-PLACAR-CALIBRACAO.bat`.
* **Sem varredura de memória.** É o passo seguinte, e só entra se nenhum candidato
  da lista fechada acertar numa visita inteira — varrer por run com a lista
  produzindo acerto é CPU queimada em cinco contas.

## A struct do mob que morre é REMOVIDA, não zerada (20/08/2026)

Quatro leituras controladas do `10-DESCOBRIR-ALVO`, feitas pelo usuário no
waypoint dos Gun Witch. Ele matou um mob entre cada leitura, começando pelo de
57 de HP:

| hora | Gun Witch na grade | grade total | `0x808` | `0x80C` |
|---|---|---|---|---|
| 13:49:27 | 57/100, 9/100, 6/100 | 40 | `0x3568f938` (o de 9) | 0 |
| 13:51:03 | 9/100, 6/100 | 39 | `0x3568f938` | 0 |
| 13:51:56 | 9/100 | 38 | `0x3568f938` | 0 |
| 14:08:15 | 100/100 × 3 (respawn) | 49 | `0x3567e8b8` | `0x356ae720` (pet, 243) |

**Nenhum dos dois mobs passou por HP 0.** O de 57 desapareceu inteiro; o de 6
ficou em 6 por duas leituras e desapareceu. A grade caiu exatamente uma entidade
por morte: 40 → 39 → 38.

Consequências:

1. ~~**`hp <= 0` é um estado que quase não existe.**~~ **REFUTADO no mesmo dia
   — ver a seção seguinte.** O sinal de morte do lado da
   memória é o ponteiro **deixar de valer**, que é o caminho "ausência" do
   `VigiaDoAlvo` — e ele era **inalcançável** enquanto a reserva do `0x80C`
   impedia `target_object()` de devolver `None`. A arquitetura estava certa; o
   *fallback* a envenenava.
2. **`0x808` é estável.** Ficou parado no mesmo `0x3568f938` por 2,5 minutos
   enquanto dois mobs morriam em volta. A hipótese de "entidade mais próxima"
   está morta.
3. **Nas três primeiras leituras `0x80C` era ZERO** — o pet não estava invocado.
   Mais uma razão para nunca usá-lo como reserva: ele não é sequer sempre
   presente.

### O caso decisivo não é medível pela mão do usuário

Falta a leitura do mob **SELECIONADO** morrendo — é ela que separa "o campo vai
a zero" de "o campo fica pendurado". O usuário tentou:

> "eu acredito que vai a zero, mas o mob desaparece com o tempo, com isso as
> minhas leituras manuais demoram um pouco, então acaba sumindo antes de eu
> fazer a leitura dele morto"

A leitura das 14:08 é a prova: feita logo depois de matar um Gun Witch, ela já
não tinha cadáver na grade **nem ponteiro pendurado** — três Gun Witch, todos
100/100.

**A janela é curta para a mão e não para o bot**, que lê a cada
`CADENCIA_DA_PROVA` = 0,5 s. Daí `PROVAR_A_AUSENCIA_DO_ALVO` e
`memory.estado_do_alvo()`, que devolve `nulo` / `pendurado` / `valido` mais o
valor CRU — distinguir os dois primeiros é o objetivo inteiro.

O placar ganha duas linhas, e a segunda não é redundância: `alvo_presente|0x808`
é a afirmação promovível (se gabaritar, o veredito de morte ganha uma fonte de
~1 µs), e `estado_do_alvo|<estado>` é o censo. Um placar com 99% de acerto não
diz se o 1% restante é seleção perdida ou memória liberada.

**Sem tolerância de erro declarada, de propósito.** O gabarito é a barra da tela,
que atrasa em relação à memória, então algum ruído é esperado — mas o número sai
da medição, não do palpite. Se a taxa estabilizar num valor pequeno e constante,
esse é o atraso da amostragem, e aí ele entra em
`TOLERANCIA_DE_ERRO_POR_PROVA` com medição atrás.

## REFUTAÇÃO no mesmo dia: HP 0 existe (20/08/2026, 17:59)

Eu concluí, das três leituras da cave, que **o mob não passa por HP 0**. Errado.

O usuário rodou o diagnóstico de memória numa conta **APP**, matando mobs fora da
cave, e a grade de entidades trouxe:

```
 dist      struct   nv         HP         posicao  nome
    7  0x2c964150   58    48/100   (2588, -365)  'Guard of Screw Bay'
   13  0x2c965258   58   100/100   (2586, -357)  'Guard of Screw Bay'
   20  0x2c963048   58     0/100   (2564, -375)  'Guard of Screw Bay'   <== ZERO
```

**O cadáver fica em `0/100`.** E o `10-DESCOBRIR-ALVO` de 41 s antes (17:58:49)
tinha grade 8 sem nenhum zero — ou seja o zero apareceu e ficou na janela entre
as duas leituras.

### O erro de método, que é a parte que importa

As três leituras da cave foram às 13:49:27, 13:51:03 e 13:51:56 — **96 s e 53 s
de intervalo**. Nenhum estado de poucos segundos sobrevive a essa amostragem.
Eu tirei conclusão de **ausência** a partir de amostragem esparsa, que é
exatamente o erro que a regra *"número novo precisa de MEDIÇÃO"* existe para
evitar, na versão qualitativa.

O que aquele experimento prova, e só isso: **a struct acaba sendo removida**, uma
entidade por morte. Se ela passa por zero antes, ele não tinha resolução para
dizer.

### E a explicação certa de por que `hp <= 0` nunca funcionou

Não é falta do estado: é que `target_object()` devolvia o **PET** (243/243), que
não chega a zero. A reserva do `0x80C` já explicava o `hp_memoria=243`, o
`leu=100` constante, os 96% de erro e a tremulação do `combate.log` — e explica
isto também. Uma causa, cinco sintomas.

**Consequência prática:** `hp <= 0` volta à mesa como sinal legítimo de morte,
agora que a reserva saiu. Quem vai dizer se ele serve é o placar, pelas linhas
`alvo_presente` e `estado_do_alvo`.

## 243/243 é escala de PET — e a grade tem os pets dos outros (20/08/2026)

A grade das 17:59, fora da cave:

```
 dist      struct   nv         HP   nome
    1  0x315ee648   22   243/243   None              <== o pet do usuário (+0x80C)
   10  0x2e6280f8   10   100/100   'Fresh Berry'
   16  0x2c967468   30   243/243   'Ganoderma'       <== pet de OUTRO jogador
   19  0x2e582d50    6   100/100   'Magnesite Ore'
   34  0x2e6a6010   30   243/243   None              <== outro pet
```

**Eu concluí daqui que "escala 243 não prova pet", e estava errado.** O usuário
corrigiu:

> "`Ganoderma` também é um pet, mas não é o meu pet, o meu nas duas contas se
> chama `Nine Tails Fox`. existe vários pets e nomes, normalmente cada player tem
> um pet por personagem, então é importante considerar isso."

Eu tratei *"não é o seu pet"* como *"não é pet"*. A heurística vale:

- **Escala 243/243 = PET.** Ela diz **pet**, e não diz **de quem**.
- **Numa área com outros jogadores a grade tem vários 243/243**, um por
  personagem. Quem separa é o **NOME**.
- **O pet do próprio personagem é o do `+0x80C`** — seis rodadas medidas, cinco
  contas. É por isso que a reserva ali era tão daninha: ela não pegava "um pet
  qualquer", pegava justamente o do personagem que estava lutando, sempre
  presente e com endereço estável.

**Consequência para o `10-DESCOBRIR-ALVO`:** o rótulo passou de
`**O PET** (escala 243, nao 100)` — confiante e ambíguo — para
`escala 243: PET (a grade tem os pets dos outros jogadores tambem; o SEU e o do
+0x80C)`.

## Recurso de coleta usa a escala de inimigo, e não recebe TAB (20/08/2026)

Na mesma grade, `Fresh Berry` nível 10 e `Magnesite Ore` nível 6 estão em
**100/100** — a escala de inimigo. O usuário explicou o que eles são:

> "acredito que seja realmente um minério, pois o jogo tem um sistema de coletar
> minério, mas eles não recebem target pelo TAB e é só fora da cave"

Duas propriedades, e as duas importam:

1. **Não recebem alvo pelo TAB.** Então nunca chegam ao `+0x808`, e a escala 100
   continua segura para decidir alvo. A prova `alvo_presente` não é poluída por
   eles.
2. **Só existem fora da cave.** Dentro, a grade é de inimigos e pets.

**Onde isso morde:** quem varre a **GRADE** em vez de ler a seleção — a lista
"entidades vivas por perto" do diagnóstico e a ideia de "atacar a mais próxima e
viva" que ela sugere. Ali um minério a 19 de distância entra na lista como
candidato legítimo, com nível e HP plausíveis, e nenhum dos dois campos o
denuncia. É mais uma razão para o alvo sair da SELEÇÃO e não de varredura.

## Um diagnóstico meu que mentia com confiança (corrigido)

Na mesma saída das 17:59, `target_detail()` imprimia:

> o campo do alvo aponta para `0x315ee648`, mas aquilo **não valida como
> entidade** (nível ou HP máximo fora de faixa). Provável ponteiro sobrando de um
> mob que morreu

E três blocos abaixo, na mesma saída, a grade listava `0x315ee648` como
**nível 22, 243/243, a UM de distância**. Entidade válida, e não cadáver de nada.

**A causa é acoplamento velho.** `selecionado` vem de `target_object()`, que desde
`USAR_RESERVA_DO_OPONENTE = False` lê **só** o `+0x808`; mas o `bruto` mostrado cai
para o `+0x80C` para ter algo a exibir. Com a seleção vazia e o pet invocado, os
dois falam de campos **diferentes**, e o `elif` concluía sobre o campo errado.

Agora a validade é conferida **no campo que está sendo mostrado**, e o texto para
esse caso diz o que realmente acontece: *"nada na mira: +0x808 é ZERO, que é a
resposta honesta"*.

É a terceira vez nesta investigação que uma **frase confiante sobre a coisa
errada** custa tempo — as outras duas foram o rótulo `"provável ID"` (que era
vtable) e o `"ESTE É O CAMINHO"`. Rótulo errado custa mais que rótulo nenhum.

## O nome do alvo saía errado em 79% das leituras (01/09/2026)

`+0xBC` da entidade guarda um **PONTEIRO** para o nome, e logo depois dele há um
buffer com resto de OUTRA entidade:

```
+0x0B8  FF FF FF FF | D8 6F 82 31 | 53 68 61 6D 61 6E 00
                      ^ ponteiro    ^ buffer velho: "Shaman"
```

`_nome_da_entidade` tentava o **inline primeiro**. Ler inline devolve os bytes do
próprio ponteiro seguidos do buffer: `D8 6F 82 31` + `Shaman` = `.o.1Shaman`,
que sai como **`'o1Shaman'`**. É a origem de toda a família de nomes corrompidos
observada nos logs — `'X1Shaman'`, `'0x1Shaman'`, `'71Shaman'`, `'L4Shaman'`,
`'6P4Shaman'`, `'8i1Shaman'`, `'R1Shaman'`: **o prefixo varia porque o PONTEIRO
varia**, e o sufixo é sempre o mesmo buffer velho.

### A medição

38 amostras do mesmo mob, com o bot rodando:

| o que a produção devolveu | vezes |
|---|---|
| `'Burning Deadwood'` (certo) | 8 |
| `'o1Shaman'` / `'1Shaman'` (lixo) | 30 |

| forma de ler | nome plausível |
|---|---|
| inline primeiro (como estava) | **8/38 — 21%** |
| desreferenciar `+0xBC` primeiro | **38/38 — 100%** |

Confirmado depois em **2.481 leituras** ao longo de 5 baterias: 100%, com
**zero divergência** e o id do objeto conferindo em todas.

### Por que a régua não resolve, e a ordem sim

`_parece_nome` **aprova** `'o1Shaman'` porque `_CARACTERES_DE_NOME` aceita
dígito — e **tem de aceitar**: `Tsuki69` e `WizzOfBlazes4` são nomes de jogador
legítimos. Não existe régua que separe `'o1Shaman'` de `'Tsuki69'` sem quebrar o
segundo. Logo a única correção certa é a **ORDEM**, não o filtro.

### As duas vias continuam necessárias

Na medição, **~80% dos nomes saíram pelo ponteiro e ~20% legitimamente inline**.
O docstring original já dizia *"Inline em umas, PONTEIRO em outras"* — estava
certo sobre a existência dos dois ramos e errado só sobre a prioridade. Tirar o
ramo inline quebraria um quinto das leituras.

### Por que isso não era cosmético

O docstring de `_parece_nome` afirmava: *"nenhuma decisão do bot depende dele: o
nome só aparece em diagnóstico e log."* **Isso deixou de ser verdade** quando
`USAR_PORTAO_DE_NOME` foi religado em 25/08/2026. O nome alimenta:

- `_veredito_do_alvo(alvo_esperado)` — o portão que existe justamente para
  evitar *"atacando mob que não é o esperado"*;
- `_e_o_alvo_proibido()` — decide travar ou destravar.

Um nome errado em 79% das leituras estava alimentando essas duas decisões.

### A lição de método

A ordem errada ficou invisível porque a função **sempre devolvia algo
plausível**, e o lixo até compartilhava o sufixo com o nome verdadeiro
(`o1Shaman` × `Odd Shaman`) — parecia quase-acerto, não ramo errado. Em cadeia
`tenta A, senão B`, é a **permissividade da régua** que decide qual ramo roda:
régua que aceita a falha de A transforma B em código morto, e quem chama recebe
uma resposta errada plausível em vez de erro. Medir a **distribuição dos ramos**
teria mostrado o defeito no primeiro log.

Bancada, logs e matriz completa: `Teste-Ponteiros/RESULTADOS.md`, seções 11.3,
12.5 e 13.6.

## O array de entidades perde 38% dos alvos, e a saída são as REGIÕES QUENTES (01/09/2026)

### O que estava errado, medido

`ADDR_ENTITY_SCAN_BASE` (o array de 512 slots) acerta **62%** das leituras --
600 amostras por conta, com o bot rodando. Isso NÃO era "mob morto, id velho",
que foi a primeira explicação e estava errada.

Uma varredura de força bruta dos 912 MB de heap, procurando objeto com
`+0x8 == TARGET_ID` e campos de entidade plausíveis, achou o objeto **VIVO** em
**6 de 6** casos em que o array falhou:

```
[caso 1] O OBJETO EXISTE -- obj=0x31870DB0 nv=63 hp=11/100 'Burning Deadwood'
[caso 3] O OBJETO EXISTE -- obj=0x31870DB0 nv=63 hp=0/100  'Burning Deadwood'
```

Nome certo, HP legível caindo de 11 para 0. Não é desalocação: **é rota
faltando**, e portanto 100% é alcançável.

### Por que alargar o array não resolve

Para um objeto que o array perde, a varredura de quem aponta para ele deu:

```
24 referencia(s): 0 na IMAGEM, 24 no heap
REFERENCIAS NA IMAGEM (estaticos): (nenhuma)
```

**Zero referências estáticas.** O array não é o container de entidades, é uma
tabela **transitória** -- a suspeita que já estava escrita aqui (*"a seleção
visual é guardada em MÚLTIPLOS endereços estáticos"*) se confirmou. Passar de
512 para 4096 slots não acha o que não está em endereço estático nenhum.

### O que o código do jogo diz

`client.exe+411A70` desmontado (`capstone`, lendo a seção de código do processo):

```asm
lea  esi, [ecx + 0x10]     ; o CONTAINER e this+0x10
call 0x8110a0              ; a busca
mov  edi, [eax]            ; \ retorno = PAR de iteradores
mov  ebx, [eax+4]          ; /
mov  ebp, [esi+4]          ; end() do container
cmp  ebx, ebp              ; == end() -> nao achou
```

E `client.exe+4110A0` é descida de **árvore rubro-negra do MSVC**:

```asm
mov edx, [ecx+4]              ; container+0x04 = _Myhead
mov eax, [edx+4]              ; _Myhead+0x04   = RAIZ
cmp byte ptr [eax+0x15], 0    ; +0x15 = _Isnil
  cmp [eax+0xc], esi          ; +0x0C = CHAVE
  mov eax, [eax+8]            ; +0x08 = _Right
  mov eax, [eax]              ; +0x00 = _Left
```

Layout do nó, lido do próprio jogo: `_Left/+0x00`, `_Parent/+0x04`,
`_Right/+0x08`, chave em `+0x0C`, valor em `+0x10`, `_Color`/`_Isnil` em
`+0x14`/`+0x15`.

**Confirma que a estrutura é árvore, não array** -- e portanto que uma varredura
linear de array não pode dar 100% por construção.

### A árvore daquele lookup NÃO serve (hipótese reprovada)

Descer por ela seria O(log n) e o caminho ideal. Mas **não é ela**: varrendo o
heap por quem aponta para o objeto do alvo saíram 23 referências -- 11 com cara
de slot de array, 12 campos, e **ZERO nós de árvore**. Três endereços tinham o
`TARGET_ID` em `-0x4` do ponteiro, mas `_Color`/`_Isnil` traziam texto (`88`,
`70` = `'X'`, `'F'`). Teste de passo fixo: os pares válidos caem em `k`
irregulares (−307, −285, −242, −185, −143, −37), e um dos sítios estava dentro
de um buffer XML da UI (`<Item type="TEXT" text="0/…`).

O mapa de `client.exe+411A70` indexa outra coisa. **O que ele indexa segue
desconhecido.**

### A rota que resolveu

Observar ONDE as entidades moram. Elas ficam em **POUCAS regiões do heap**:

```
3 regioes, 960 KB no total   (de 914 MB = 0,1% do heap)
  0x3184B000..0x31884000   228 KB   508 entidades
  0x2C8A8000..0x2C927000   508 KB     7 entidades
  0x315AC000..0x315E4000   224 KB     1 entidade
```

Varrer só essas custa **0,25 ms**, contra 3,2 ms do array e 741 ms da varredura
total. Resultado: **2.481 de 2.481** leituras (100%), nome e HP em todas, id
conferindo em todas, zero divergência.

### A UNIDADE é região, não intervalo -- e isso foi medido do jeito difícil

A primeira versão modelou a localidade como **uma janela contígua** `min..max`
dos endereços vistos. Funcionou enquanto as entidades estavam juntas. Então a
semeadura achou 24 entidades em `0x2C4Cxxxx` com o alvo em `0x3186xxxx`: a
janela esticou para cobrir as duas, bateu no teto de 8 MB, e a rota **piorou de
0,55 para 6,6 ms** -- ficou mais lenta que o array que vinha substituir.

A correção não foi calibrar o teto e a margem: foi trocar a **unidade** para
REGIÃO do `VirtualQueryEx`. Naturalmente descontínua, não estica sobre espaço
vazio, e os três parâmetros da v1 (margem, teto, recentragem) desapareceram
junto com a abstração errada.

**Fato corrigido:** eu havia escrito que as entidades ficavam "num pool contíguo
de ~150 KB". Falso -- ficam em pelo menos **três** regiões espalhadas por 12 MB
de espaço de endereço.

### O arranque a frio, e a semeadura

Numa bateria de 700 amostras o **único** caso em que nenhuma rota barata
respondeu foi a **amostra 0**: sem região aprendida, não há onde varrer, e só a
força bruta (741 ms) respondeu.

Não era defeito da rota -- era arranque a frio. `semear_regioes_quentes()` varre
o array **uma vez** e aprende de **todas** as entidades, não só do alvo: 24
entidades e 3 regiões em **5,16 ms**. A semeadura é PREGUIÇOSA (roda na primeira
falha do array, não no construtor), então quem nunca perde uma entidade não paga
nada por esta rota.

### O que impede devolver lixo

A varredura acha o id em qualquer lugar do heap onde aqueles 4 bytes apareçam.
Duas conferências separam entidade de coincidência: o id tem de **bater de novo
numa leitura direta** de `+0x8`, e o **nível** tem de estar em 1..250. Sem
isso, um inteiro casando por acaso viraria "alvo com HP inventado".

### O LIMITE CONHECIDO, e por que ele fica

A rota só varre onde entidade **já apareceu**. Alvo numa região virgem devolve
`None` -- e `None` é a resposta certa: *"não sei"* é melhor que varrer 912 MB
dentro do laço de combate. Não apareceu nas 2.481 leituras, porque a semeadura
aprende de todas as entidades do array de uma vez. Se aparecer, o sintoma é
`alvo_atual() -> None` com o mob visivelmente vivo, e a saída é **semear de
novo**, não alargar a varredura. Travado em
`tests/test_regioes_quentes.py::test_regiao_onde_entidade_nunca_apareceu_NAO_e_varrida`.

### Relogin

O cache de regiões é **por processo**, e morre com o `Memory` -- que é
exatamente o desejado, porque relogin troca o PID e endereço de heap do processo
morto não vale nada no novo. Prova indireta medida: as entidades da `BlazesAPP1`
ficaram em `0x3184Bxxxx` e as da `WizzOfBlazes5` em `0x06E1xxxx`, faixas sem
intersecção.

Teste de reanexo a frio (duas vidas independentes no mesmo processo): as duas
resolveram na **primeira tentativa**, aprenderam as **mesmas 3 regiões**, e o
custo de voltar do zero foi **anexo 24,8 ms + semeadura 5,23 ms**. Uma troca de
PID real não foi observada em 14 min de vigia -- isso não reprova nada, só não
houve o evento.

### Validação em campo, com o patch dentro

`Memory.alvo_atual()` da produção, 200 amostras por conta:

| | BlazesAPP1 | WizzOfBlazes5 |
|---|---|---|
| `alvo_atual()` respondeu | **200/200** | **191/191** |
| com nome | **100%** | **100%** |
| com HP | **100%** | **100%** |
| nomes corrompidos | **nenhum** | **nenhum** |

`'Odd Shaman'` sai limpo -- antes saía `'o1Shaman'`. Custo médio de
`alvo_atual()`: **0,270 ms**; pior caso 24,97 ms (é a semeadura, uma vez).

Bancada, scripts e logs: `Teste-Ponteiros/RESULTADOS.md` seções 12 e 13.

## Painel de UI por memória, e a afirmação que o campo derrubou (02/09/2026)

### O que motivou

Medição de 600 leituras, 6 contas em operação, comparando um estático novo com
todos os leitores de estado de UI da produção:

| leitor da produção | resultado |
|---|---|
| `modal_open()` | `False` em 599 de 600 |
| `dialog_open()` | **`None` em 600 de 600** — sempre *"não sei"* |
| `loot_window_open()` | `False` em 600 |
| `system_menu_open()` | `False` em 600 |

`dialog_open()` responder `None` em 100% é consequência direta de
`ADDR_DIALOG_ROOT` (`0x0117B27C`) estar **morto nos 6 clientes** — o `+0x60` da
virada 6139 → 6400 é `0x0117B2DC`, e é esse que resolve. E a captura de tela, que
seria a reserva, devolve **quadro preto** em cliente DirectX fora do primeiro
plano — a condição **normal** deste bot, que roda várias contas ao mesmo tempo.

O estático novo (`0x012CE3D8`) dizia *"algo aberto"* em **270 de 600 leituras
(45%)** em que todos os leitores acima diziam nada, com **zero contradições** no
sentido inverso.

### O que eu afirmei, e o campo derrubou

Escrevi duas regras, validadas em bancada com 3 rodadas de alternância de tecla:

1. `bandeira == 0` ⇒ **nada aberto, com certeza**;
2. `bandeira != 0` **e** `segunda fenda == 0` ⇒ é a **bolsa**.

As duas caíram. Lendo os valores crus lado a lado com a cadeia de bolsa **já
validada** (`CHAIN_BAG_OPEN`, 902 fechada / 903 aberta), em seis contas:

```
bandeira | segunda | cadeia | vezes
---------+---------+--------+------
   != 0  |   != 0  |   902  |  12    painel aberto, bolsa fechada
   != 0  |   != 0  |   903  |  11    bolsa ABERTA, e `segunda` != 0   <- mata (2)
   == 0  |   != 0  |   903  |   7    bolsa aberta, bandeira em ZERO   <- mata (1)
   == 0  |   == 0  |   902  |   6    nada aberto
```

E a validação do patch inteiro contou **105 de 240 leituras** em desacordo com a
cadeia. Depois de reduzir, o caso previsto pelo contraexemplo (`False` com a
bolsa aberta) aparece em **73 de 240 (30,4%)** — exatamente o que o docstring
agora avisa.

### Por que o erro não foi para produção

Porque a validação em campo comparava a regra nova com uma **segunda fonte
independente** e **contava a discordância**. Um leitor sozinho devolveria
`False` com confiança e ninguém saberia — que é o modo de falha que este projeto
combate desde a barra de vida do alvo.

Isso vale como regra: **capacidade nova de memória entra com uma segunda fonte
ao lado e um contador de desacordo**, não com um teste de bancada só. Bancada
prova que o campo responde ao estímulo; campo prova que ele responde à
realidade, que é outra coisa.

### O que entrou

| entrou | o que é |
|---|---|
| `quest_aberto()` | discriminador validado: `1` só com o Quest aberto, `0` com os outros cinco painéis, em 3 de 3 rodadas, e `0` em 5 de 5 contas sem Quest lidas no mesmo instante |
| `dialogo_de_ui_a_frente()` | **sinal de uma via**: o `True` afirma, o `False` não conclui nada |
| `BAG_CLOSED_VALUE = 902` | o comentário herdado dizia *"0 or 903"*; o `0` nunca apareceu em 840 leituras |
| valores crus no `probe()` | bandeira, 2ª fenda e a cadeia da bolsa lado a lado — num sinal de uma via, booleano não basta para investigar |

### O que NÃO entrou, e por que

**`modal_open()` não foi reescrito.** `ADDR_MODAL` existe para dizer *"há caixa
de confirmação, erro de login ou DC na frente"*, e o watchdog conclui DC pela
**persistência** desse sinal. A bandeira acende com a **bolsa** e com o **quest
log**, que não são modais — trocar um pelo outro faria o watchdog ver "modal" a
cada abertura de bolsa. Seria trocar um defeito conhecido por um pior. O
problema do `ADDR_MODAL` fica registrado e sem conserto.

E os leitores antigos seguem **independentes** de propósito: se algum passasse a
ler a bandeira, as duas fontes viravam uma, e a discordância — que foi o que
pegou este erro — deixaria de existir. Travado em
`tests/test_paineis_por_memoria.py::test_os_leitores_antigos_seguem_independentes`.

### O que fica em aberto

Distinguir **Item, Skill, Attribute, Guild e System** entre si. O Quest saiu; o
candidato do Guild (`0x012DC180`) respondeu também ao System em 1 de 3 rodadas e
não passa. Duas hipóteses de identificar o painel por um campo **dentro** do
objeto foram refutadas antes (texto de instância, e nome de formulário `.frm`, 1
de 6) — e a vtable é a mesma nos seis (`client.exe+B33CC4`), então a classe não
discrimina.

Bancada, scripts e logs: `Teste-Ponteiros/RESULTADOS.md`, seções 20 e 22 a 24.
