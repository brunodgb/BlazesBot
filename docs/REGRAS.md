# Regras detalhadas do BlazesBot (medição e especificação)

> **Arquivo complementar ao `CLAUDE.md`.** Em 20/08/2026 o `CLAUDE.md` foi enxugado para ficar abaixo de 35k caracteres (índice de regras); a medição completa e a especificação de cada área foram movidas para cá, **verbatim**. O `CLAUDE.md` guarda a REGRA resumida + o link; aqui fica o DETALHE que a sustenta. Leia isto ANTES de mexer na área — quase tudo aqui já foi tentado do outro jeito e reprovou com medição.
>
> Para o PORQUÊ medido de cada regra (log de produção, alternativa que reprovou), veja também `docs/decisoes/` — este arquivo é a especificação técnica; os `docs/decisoes/` são a evidência.

---

### Sistema — `docs/decisoes/sistema.md`

- **A PARADA ACORDA QUEM ESPERA; não é descoberta por polling.**
  `_AnyEvent.wait` esperava só o evento PRÓPRIO, então acionar o stop GLOBAL não
  acordava ninguém — e era por isso que o `tick()` fatiava `time.sleep` em
  0,025 s, **40 acordadas por segundo por conta**. Agora `BotManager.stop()` faz
  FAN-OUT para o `own_stop` de cada supervisor (a propagação vai no ESCRITOR,
  porque parar é raro e esperar é o caminho quente) e o `tick()` espera no
  evento. `request_stop` continua acionando só o próprio: parar uma conta não
  derruba as outras. Travado por `tests/test_parada_acorda_na_hora.py`.
- **`FATIA_DA_ESPERA` MUDOU DE SIGNIFICADO** (0,025 → 0,25). Não é mais a
  latência do Parar, que virou ZERO; é a cadência do watchdog dentro de esperas
  longas.
- **`docs/INTERRUPTORES.md` é GERADO** (`python -m
  blazesbot.core.indice_de_constantes`): as 331 constantes ajustáveis, com valor,
  arquivo:linha, quem lê cada uma e o porquê resumido. **Editar lá não muda
  nada** — muda-se no arquivo indicado. Dois dentes em
  `tests/test_indice_de_constantes.py`: índice desatualizado reprova, e **todo
  `NOME = valor` de interruptor citado neste arquivo tem que bater com o
  código**. O segundo nasceu de um defeito real — este arquivo afirmava que o
  Mouse Shield estava ligado enquanto o código o tinha desligado.
  **Consequência para quem escreve aqui:** citar um valor ANTIGO na forma
  `NOME = valor` reprova a suíte, mesmo em frase histórica; escreva a história
  em prosa e deixe a forma com crases só para o valor de HOJE.
  `docs/decisoes/` fica de fora da checagem de propósito — valor antigo lá é a
  medição, não o erro.
- **Endereço estático herdado do GhostBot é da versão 6139 do cliente.** O
  `core/rebase.py` mede o valor atual e o candidato **+0x60** (o deslocamento
  medido entre 6139 e 6400) e **só troca quando o candidato responde E o atual
  não** — empate mantém o atual, porque ler lixo com sucesso é pior que não ler.
  Decide uma vez por processo; INCONCLUSIVO não é guardado. Ver
  `docs/decisoes/transplante-ghostbot.md`.
- **Pino de janela `(hwnd, pid)` por conta** (`last_hwnd`/`last_pid` no
  `config.json`, invisível nas interfaces): único jeito de reconhecer a janela NO
  MEIO do login. Nick lido na memória vale mais; nick diferente ⇒ apaga o pino.
- **Log em dois ambientes** (`BLAZES_MODO` = `dev` | `prod`). O usuário vê os
  arquivos legíveis e a tela; **só em dev** existe `logs/dev/blazes-dev.jsonl`
  (uma linha JSON por registro, com `conta`, `id_run`, `fase`, arquivo/linha e
  milissegundos). Trocar DEBUG↔INFO ao vivo só em dev.
- **A barra de atalhos tem que estar na PÁGINA 1** (`bot/bc/hotbar.py`): em outra
  página a MESMA tecla dispara outra coisa. **Clica, não lê** — o botão sobe e
  PARA no 1, então 2 cliques bastam de qualquer lugar. Sete momentos-chave,
  recarga de 10 s no caminho com `ctx`. **Duas portas**, para não quebrar o
  isolamento do APP: `garantir_pagina_1(ctx, ...)` e `subir_para_a_pagina_1(
  clicar, ponto)`. `KeyBinds.hotbar_page_1` é opcional e leva direto.
- **No APP a página 1 é garantida na largada E antes de CADA volta**, por função
  injetada pelo supervisor (o executor importa só `core.inputs`).
- **Desligar o BC pela interface é IMEDIATO** e não derruba a conta: `bc_farm` →
  False levanta `FarmDesligado` em `raise_if_stopped` (só com `ctx.farming`), que
  sobe limpa até `routine.run`. A conta fica online, parada, com relogin.
- **Rede de segurança:** `./.venv/Scripts/python.exe -m pytest -q` e
  `-m ruff check blazesbot/ tests/ main.py`. As categorias intencionais estão no
  `ignore` do `pyproject.toml`.
- **O plugin ECC (hooks) está com escopo `project` apontando para a pasta temp
  do Claude.** Se o GateGuard atrapalhar, `ECC_GATEGUARD=off`.

### Combate — `docs/decisoes/combate.md`

- **NADA SOBRE O ALVO É AFIRMADO SEM LINHA DE LOG ATRÁS.**
  `docs/decisoes/alvo-o-que-esta-medido.md` tem três tabelas — **MEDIDO** (cada
  fato com a evidência ao lado), **ABERTO** (hipótese, e continua hipótese) e
  **REFUTADO** (o que eu afirmei e caiu, com o erro de método). Ordem do usuário
  em 20/08/2026, depois de eu voltar atrás três vezes no mesmo dia. Promover uma
  linha de ABERTO para MEDIDO exige colar a evidência junto — não basta o
  raciocínio parecer fechado.

- **A TELA É O GABARITO E A MEMÓRIA É A ALUNA**
  (`core/calibracao.py`, `MEMORIA_VOTA_NA_MORTE = False`). A memória continua
  sendo LIDA e vai para o log, mas **não decide nada** até o placar dizer
  `gabaritou`. Decisão do usuário em 19/08/2026; medições e desenho em
  `docs/decisoes/combate.md`.
  - **O TAB NUNCA MIRA MOB MORTO** — fato de jogo dado pelo usuário. Logo
    `trocas_ptr=0` em três TABs prova que **o ponteiro não acompanha a seleção**,
    não que o TAB falhou. O AoE mata no mesmo instante do TAB, e é isso que
    parecia "TAB no cadáver".
  - **Três erros medidos no mesmo log:** `hp_memoria=243` (é o **PET**; 243/243 é
    escala de jogador/pet), `hp_memoria=9` atravessando um TAB (leitura velha), e
    `hp_memoria=100` constante por 38 s. **Quem denuncia o pet é a ESCALA**, não a
    validação de entidade — o pet é entidade legítima. **243/243 é escala de PET,
    e ela diz "pet" mas não diz "de quem"**: cada personagem tem um pet, então
    numa área com outros jogadores a grade tem vários 243/243 (o `Ganoderma`
    nível 30 da leitura das 17:59 é o pet de outro jogador). **O SEU é o do
    `+0x80C`**, e o que separa um do outro é o NOME — o do usuário se chama
    `Nine Tails Fox` nas duas contas. Confirmado por ele em 20/08/2026, depois
    de eu ter concluído errado que a escala não valia.
  - **`gabaritou` exige TRÊS coisas juntas:** 50 amostras com **zero** erro, 20
    delas **discriminantes** (vida da tela entre 5% e 95% — no waypoint todos
    estão com 100 e qualquer leitura parada "acerta"), e **10 runs distintas**
    (acertar na mesma sessão pode ser sorte de heap; o `+0x60` é a prova). Um
    erro DERRUBA o rótulo — cliente novo invalida o que passou.
  - **`reprovado` para de ser amostrado** — é a economia que faz o custo cair
    conforme converge: hoje 4 leituras de ponteiro por leitura de combate, no fim
    uma.
  - **Cada ponteiro é provado onde a verdade dele está DESENHADA na tela:**
    `alvo_hp` e `flag_combate` a cada leitura de combate; `modal` no
    `_ponto_do_ok` do vendedor (o método que *substituiu* o `modal_open()`);
    `janela_de_loot` no localizador do "Pick up all" (o botão **é** a janela).
    `team_size` está de fora — falta o template do painel de time.
  - **A BARRA PASSOU A SER LIDA SEMPRE** no consenso (4,14 ms), porque ela é o
    gabarito. `calibracao.ATIVADA = False` devolve a economia inteira; travado
    por teste.
  - **NADA é promovido automaticamente.** O usuário lê
    `15-PLACAR-CALIBRACAO.bat` e decide.
  - **TRÊS PENEIRAS, universos e critérios diferentes** (`calibracao.Peneira`,
    filtragem progressiva estilo Cheat Engine — o que a faz funcionar é a
    MUDANÇA, não a varredura):
    1. **`alvo_hp`** — campos do PERSONAGEM cujo HP casa com a barra. Já rodou e
       convergiu em `0x808`: **não existe campo melhor na struct**.
    2. **`hp_da_entidade`** — campos DENTRO da entidade. Hipótese dos erros
       `leu=100` constantes: `ESCALA_DE_INIMIGO = 100` é o HP **máximo**, então
       um cem fixo é o que se leria se `OFF_HP` apontasse para o máximo. Barata:
       o ponteiro é resolvido uma vez (~512 leituras contra ~7.700).
    3. **`alvo_selecao`** — IDENTIDADE, e ela exige **DUAS** coisas, porque uma
       sozinha aprova lixo: o campo **MUDA atravessando um TAB** (o TAB nunca
       mira mob morto, logo a seleção mudou) **E NÃO MUDA entre leituras sem
       TAB** (seleção é estável enquanto o alvo vive). O `combate.log` de
       20/08/2026 provou que a segunda metade é indispensável: `0x808` passeia
       pelo pool de entidades a cada leitura com o personagem só ANDANDO —
       `Evil Centipede` → `Poleax Aborigine` → `Poison Rattan`, e às vezes o
       **pet** (243/243) —, ou seja **muda sempre** e passaria em todo TAB. Não custa tela nenhuma. Nasceu
       de `ptr=0x2f768910` com `trocas_ptr=0` atravessando três TABs *com o HP
       daquele endereço mudando* — ou seja `0x808` aponta para algo vivo, mas
       **não é a seleção**. Leitura CRUA (`valor_cru_do_campo`): validar antes de
       comparar transformaria a mudança em silêncio. Os DOIS valores precisam
       parecer ponteiro, senão um campo que oscila entre 0 e lixo "trocaria"
       sempre.
  - **O ALVO SEMPRE FUNCIONOU; O DEFEITO ERA A NOSSA RESERVA.** Achado de
    20/08/2026, duas rodadas do `10-DESCOBRIR-ALVO` × cinco contas:
    `jogador+0x808` é **nulo quando nada está na mira** (resposta honesta) e
    entrega a struct certa quando há alvo — `+0xBC` lê `'Gun Witch'` inline. E
    **`jogador+0x80C` é o PET** (nível 32, escala 243/243) nas duas rodadas e nas
    cinco contas. `target_object()` caía de um para o outro, então **sem alvo o
    bot lia o pet em silêncio**. É a explicação de TODA a série medida: o
    `hp_memoria=243`, o `leu=100` constante, os 96% de erro e a "tremulação" do
    `combate.log`. Agora `USAR_RESERVA_DO_OPONENTE = False` e sem alvo a resposta
    é `None`. Ler o pet é pior que não ler — o bot decide em cima dele.
  - **CONFIRMADO EM PRODUÇÃO** pelo `9-VIGIAR-COMBATE` de 20/08/2026, o mesmo
    campo antes e depois: a tremulação **desapareceu** (`'Cemetery Guard'
    @0x35682cd8` × 5, `'Gun Witch' @0x35678288` × 15, endereço parado com nome
    real), e as contas sem alvo passaram de `hp=243/243` / `729/729` para
    `alvo=nao`. Três rodadas do `10-DESCOBRIR-ALVO` × cinco contas concordam.
  - **A VIRADA DE FASE DO BOSS TAMBÉM LIA O PET.**
    `_registrar_troca_de_fase` fazia `oponente if oponente is not None else
    selecao` — preferia o `0x80C`. O endereço do pet é ESTÁVEL, então a struct
    "atual" ficava constante e o método caía no `return`: **a virada nunca era
    vista pela memória**. E os dois *"PRIMEIRA FASE MORTA"* que saíram a 1 s de
    luta eram o ponteiro do pet aparecendo e sumindo. Agora lê a SELEÇÃO, e um
    teste lê o AST para proibir a escolha condicional de volta.
  - **A STRUCT DO MOB QUE MORRE É REMOVIDA — mas HP 0 EXISTE.** Experimento
    controlado de 20/08/2026: três leituras da mesma cena, matando os Gun Witch
    um por um. `0x3568a410` estava em **57/100** e sumiu; `0x35690a40` estava em
    **6/100**, ficou em 6/100, e sumiu. A grade caiu **40 → 39 → 38**, uma
    entidade por morte.
    - **A CONCLUSÃO "nunca passa por zero" ERA MINHA E ESTAVA ERRADA**, refutada
      no mesmo dia: a leitura das 17:59 numa conta APP lista
      `0x2c963048 nível 58 **0/100** 'Guard of Screw Bay'` na grade. O cadáver
      **fica** em zero por um tempo. As três leituras da cave eram espaçadas de
      53 s e 96 s — janela curta nenhuma sobrevive a esse intervalo, e eu tirei
      conclusão de AUSÊNCIA a partir de amostragem esparsa. O que aquele
      experimento prova é só que a struct **acaba** sendo removida.
    - **Então por que `hp <= 0` nunca funcionou?** Não por falta do estado: por
      `target_object()` devolver o **PET** (243/243), que nunca chega a zero. A
      explicação certa é a reserva do `0x80C`, e ela já explicava todo o resto da
      série medida.
    - O sinal de morte do lado da memória continua sendo **o ponteiro DEIXAR DE
      VALIDAR** (`_entidade_no_campo`) — caminho "ausência" do `VigiaDoAlvo`,
      **inalcançável** enquanto a reserva existia. Mas `hp <= 0` volta à mesa
      como sinal legítimo, e é o que `alvo_presente` / `estado_do_alvo` vão medir.
    - **`0x808` é ESTÁVEL**: o mesmo `0x3568f938` nas três leituras, ao longo de
      2,5 minutos em que dois mobs morreram em volta. Mata a hipótese de
      "entidade mais próxima" e é a estabilidade que o critério de identidade
      exige.
    - Nessas três leituras **`0x80C` era ZERO** — o pet nem estava invocado. Mais
      uma razão para nunca tê-lo como reserva: ele é volátil.
  - **`+0x18` NÃO é o ID da entidade** — hipótese minha, REFUTADA no mesmo dia: o
    relatório rotula `0x00edc828` como "provável ID", e o MESMO valor apareceu
    nas duas rodadas apontando para mobs DIFERENTES, num endereço de faixa de
    módulo. É **vtable**. `entidade_por_id` e o passo do array (`0x1108`) ficam
    como utilidade testada, sem prova ligada em cima deles.
  - **`OFF_HP = 0x3B8` está CONFIRMADO** (o alvo real leu 3/100 por ele), e
    **`+0x9AC` NÃO é o nome** (lixo em cinco contas). As duas hipóteses anteriores
    morreram por medição.
  - **`alvo_nome`** — gabarito de CENÁRIO (`Gun Witch` / `Blaze Skull Marshal`),
    sem custo de captura. Vale ao lado do HP porque **número coincide por acaso,
    nome não**. Comparação por CONTINÊNCIA: o cliente devolve sufixo de nível e
    espaço à direita.
  - **INSTRUMENTAÇÃO NUNCA LÊ ESTADO FORA DO `try`.** Apareceu QUATRO vezes nesta
    sessão, e na última dentro do bloco do TAB — onde a exceção abortaria a luta.
    O dente que pega é ler o **ponto de chamada** no AST: testar o método
    protegido não descobre que a guarda foi contornada.
- **A STRUCT DO MOB MORTO NÃO É REMOVIDA — ela FICA na grade em `0/100`.** Medido
  em 20/08/2026 com o filtro já corrigido: `0x35691b48` estava em 57/100 às
  21:15:28 e em **0/100 às 21:18:54, mesmo endereço e mesmo slot**, 3m26s depois.
  Isso fecha a pergunta que a correção abaixo tinha aberto.
  - **O nome em `+0xBC` para de ler quando o mob morre** (`'Gun Witch'` → `None`),
    **mas isso não é sinal de morte**: na mesma janela um 'Evil Centipede' em
    100/100 também virou `None`. O nome é instável vivo e morto.
- **A GRADE CAINDO 40 → 39 → 38 ERA O FILTRO DA MINHA FERRAMENTA, não o cliente.**
  `describe_object` exigia `1 <= hp`, então **todo cadáver era descartado em
  silêncio** — nenhum dos seis relatórios do `10-DESCOBRIR-ALVO` tem uma linha
  com `hp = 0`. Eu li a queda da grade como "o cliente remove a struct" e virou
  regra aqui. **Se a struct é removida em algum momento, hoje NÃO se sabe**
  (`docs/decisoes/alvo-o-que-esta-medido.md`, pergunta G). O que está medido é o
  contrário: o cadáver FICA na seleção, com `hp = 0`, por 7 a 13 s.
  - **A validação da PRODUÇÃO não olha HP** (`_entidade_no_campo`: nível e HP
    máximo). É por isso que o bot devolve o cadáver e o `pendurado` do placar
    continua em zero — e é por isso que ferramenta e bot precisam julgar pela
    MESMA regra: julgando pela sua, o `10-DESCOBRIR-ALVO` chamou de "pendurada"
    toda seleção morta, em duas leituras seguidas.
- **HP 0 EXISTE, e o cadáver fica.**
  Quatro leituras do `10-DESCOBRIR-ALVO` em 20/08/2026 mostraram 57/100 e 6/100
  desaparecendo da grade, que caiu 40 → 39 → 38, uma entidade por morte. **Eu
  concluí dali que o mob nunca passa por zero, e isso estava ERRADO** — a leitura
  das 17:59 numa conta APP lista `0/100` na grade. As leituras da cave eram
  espaçadas de 53 s e 96 s, e conclusão de ausência a partir de amostragem
  esparsa não vale. `hp <= 0` nunca funcionou porque `target_object()` devolvia o
  **PET** (243/243, que não chega a zero), não porque o estado não exista.
  **E o `combate.log` das 20:36 inverteu a hierarquia que eu tinha escrito:** o
  cadáver FICA na seleção com `hp = 0`, ponteiro válido e nome legível, por **7 a
  13 segundos** — e `hp = 0` chega **ANTES** do ponteiro sumir e ANTES da flag
  baixar. Então "ausência" é o sinal MAIS TARDIO, não o mais robusto; e é
  ambíguo (morrer × ainda-não-adquiri), o que `hp = 0` não é. Se isso vira
  decisão de produção, quem responde é o placar (`alvo_morto_por_hp`), não eu.
  - **O caso decisivo o usuário NÃO consegue medir**, e ele explicou por quê: o
    cadáver desaparece antes de a leitura manual sair. A leitura das 14:08, feita
    logo depois de matar um Gun Witch, já não tinha cadáver na grade. **A janela é
    curta para a mão e não para o bot**, que lê a cada `CADENCIA_DA_PROVA` —
    então quem mede é ele (`PROVAR_A_AUSENCIA_DO_ALVO`).
  - **DUAS provas, e a segunda não é redundância.** `alvo_presente` é a
    AFIRMAÇÃO (ponteiro válido ⟺ alvo vivo desenhado); `estado_do_alvo` é o
    CENSO, que reparte as mesmas amostras em `nulo` / `pendurado` / `valido`. Um
    placar com 99% de acerto **não diz** se o 1% que sobra é seleção perdida ou
    ponteiro pendurado, e a diferença entre os dois é a diferença entre ler e não
    ler memória liberada.
  - **O censo NÃO consulta `deve_amostrar`**, e é decisão: estado raro é
    exatamente o que interessa, e deixar o placar reprovar a linha `pendurado`
    pararia de contar o caso que ela existe para flagrar. Travado por dente.
  - **"Quadro sumiu" é INFORMAÇÃO aqui**, não motivo para não amostrar: sem alvo
    na tela o ponteiro deveria estar ausente, e isso é conferível. As outras
    provas saem no `None`; esta é chamada ANTES da guarda, e um dente lê o
    CAMINHO DE CHAMADA para a ordem não se inverter.
- **`--reabrir` EXIGE O BOT PARADO, e isso já falhou DUAS vezes** (20/08/2026).
  `salvar()` mescla com o disco por "mais amostras vence" — monótono porque
  contador de amostra só cresce, e é o que impede um processo de apagar o que o
  outro gravou. Mas reabrir põe a contagem em ZERO, e zero **perde** a mescla:
  com o bot rodando, a cópia velha dele volta no flush seguinte. `reabrir` grava
  **sem mesclar** e avisa em maiúsculas; ainda assim, o bot precisa estar fora.
- **`frame_is_blank` AMOSTRA o quadro de 8 em 8 px**
  (`vision.PASSO_DA_AMOSTRAGEM_DO_QUADRO`), e isso é conserto de QUEDA, não
  otimização. `np.std` sobre `uint8` aloca um temporário **float64 do tamanho do
  quadro**: 18 MB por chamada. Derrubou o bot em 20/08/2026 —
  *"Unable to allocate 18.0 MiB ... float64"* e `OpenBLAS error: Memory
  allocation still failed`. Apareceu quando a calibração multiplicou por ~10 a
  frequência de captura (~180 MB/s de rotatividade em blocos grandes).
  **Amostrado dá o MESMO veredito** (real 46,67 → 45,41; preto 0,00 → 0,00) com
  **52× menos memória e 65× mais rápido** (8-10 ms → 0,13 ms). Os 8 ms eram
  pagos a cada captura — o teste "barato" custava mais que o casamento de
  template que ele protege. Travado por `tests/test_quadro_em_branco.py`, com
  teto de alocação de 2 MB.
- **O log de dev ARQUIVA em vez de descartar**
  (`log_limitado.DIAS_DE_ARQUIVO_MORTO = 7`): a poda anexa o que sairia em
  `logs/dev/arquivo/blazes-dev-AAAA-MM-DD.jsonl`, num **único `writelines` por
  poda** — não é handler por linha, que dobraria o caminho quente. O log quente
  cobre só **28 minutos**, e nesta própria investigação a prova desapareceu entre
  duas consultas. Retenção pela DATA NO NOME, nunca pelo mtime.
  - **O arquivo de dias ANTERIORES é comprimido** (`COMPRIMIR_ARQUIVO_MORTO`):
    medido **23 MB → 740 KB, 32×**. Só dias anteriores — o de hoje ainda recebe
    anexação. Comprime para `.tmp`, renomeia, e só então apaga o original: uma
    queda no meio deixa a evidência intacta.
- **NENHUM TESTE ESCREVE EM `data/`** (`tests/conftest.py`, autouse). A suíte
  encheu o `data/calibracao.json` de amostras fabricadas, e aquele arquivo existe
  para decidir promoção de ponteiro a partir de evidência REAL — misturar as duas
  corrompe a decisão que ele embasa.
- **A morte do alvo sai do CONSENSO: OU de sinais positivos, confirmado por N
  leituras seguidas** (`FONTE_DA_MORTE_DO_ALVO = "consenso"`). Os modos
  `"memoria"`, `"tela"` e `"imagem"` seguem inteiros e testados.
  - **NENHUM JUIZ ÚNICO SERVE, e isso está medido.** Os três modos anteriores
    elegiam um juiz e calavam os outros; cada um fica cego do seu jeito
    (ponteiro que devolve cadáver, quadro que expira, sprite que não casa) e com
    um só a cegueira dele É o veredito. O sintoma foi sempre **falso negativo**:
    bot preso no corpo, sem TAB. O modo `"imagem"` durou uma run — log de
    19/08/2026: **69 leituras, 0 vereditos de morte, 0 TABs, `hp_memoria=100`
    constante por 38 s**. `alvo_morto_na_tela` nunca casou em produção.
  - **Sinais:** `hp<=0`, ponteiro sumiu, marcador na tela, barra vazia, quadro
    sumiu. **Basta UM** para a leitura contar; são precisas
    `SINAIS_PARA_CONFIRMAR_MORTE` leituras SEGUIDAS para o TAB sair.
  - **ORDEM DO CUSTO, com curto-circuito:** memória (~1 µs) → marcador
    (1,23 ms) → barra (4,14 ms). Memória dizendo morto resolve em microssegundos
    e **a tela nem é capturada**; marcador achando dispensa a barra.
  - **O CONTADOR SUBSTITUIU O PORTÃO, e a diferença é estrutural:** portão de
    estado **pode ficar fechado para sempre** (alvo adquirido já morto por AoE
    nunca é visto vivo — 35 mortes recusadas numa fase); contador **sempre**
    resolve em N leituras. Custo: (N−1) × `CADENCIA_DA_LEITURA_DO_ALVO`.
  - **O PORTÃO SÓ VALE PARA AUSÊNCIA.** "Quadro sumiu" / "ponteiro sumiu" é
    ambíguo entre morrer e "ainda não adquiri"; `hp=0`, barra vazia e marcador
    presente **não são** — passam direto. Foi a universalização do portão, em
    13/08, que criou o falso negativo.
  - **N LEITURAS, NÃO N FONTES.** O cadáver de 13/08 aparecia ao mesmo tempo no
    ponteiro e na barra — duas testemunhas do MESMO engano. O que separa engano
    de morte é o tempo entre leituras. Travado por dente.
  - **QUEM SEGURA O CADÁVER HOJE é o contador + `CARENCIA_APOS_O_TAB`**, que
    zera junto em `trocou_de_alvo()`. **Encurtar a carência reabre o defeito de
    13/08** (3 TAB em 3 s); travado por teste.
  - **O ESCORE do marcador vai para o LOG** (`vision.marcador_de_morte`), nunca
    para a decisão: `False` não distinguia "faltou 0,01 no limiar" de "casou
    0,12", e é assim que limiar e faixa deixam de ser palpite.
- **"Só relato a morte de um alvo que eu vi VIVO"** (`VigiaDoAlvo`, lógica pura,
  recebe LEITURAS e não fontes). Vale para TODO veredito de morte: o número pode
  ser do cadáver. O TAB FECHA o portão de novo, e o vigia é POR LUTA.
  `LIMIAR_DE_VIDA_DO_ALVO = 0.01` (mob a 2% lê 0.0136 = VIVO).
- **Nos guardas há portão de NOME; no boss NÃO há.** E desde **26/08/2026** o
  portão tem UM nome só: **`SO_O_CEMETERY_GUARD_PARA_O_GOLPE_NOS_GUARDAS`**.
  - **Cemetery Guard na mira ⇒ ESC, para o golpe, ESPERA a saída de combate.**
    Uma porta só (`_travar_no_cemetery_guard`) para as duas fontes: a MEMÓRIA
    (nome da entidade selecionada) e a TELA (`cemetery_guard.png`, depois de
    cada TAB). ESC sai **uma vez** — repetido fecha janela do jogo.
  - **Qualquer outro nome ⇒ CONTINUA batendo.** *"Rotaciona skill até sair de
    batalha ou até identificar o Cemetery Guard como target"* (usuário, com a
    run observada: sobrou 1 Gun Witch de pé e o bot parado). Antes, UMA leitura
    de nome diferente ligava `acabaram_os_alvos` e segurava golpe e TAB até o
    fim da fase — e aí só havia dois desfechos, morrer ou estourar o prazo.
  - **A trava não sumiu, ficou específica.** "Não bater no que sobrou" (a run
    das 11:33, que saiu da rota por puxar mob que não precisava vir) continua
    atendida contra o Cemetery Guard, que é justamente quem foi medido no covil
    ao lado dos guardas — 5 structs, nome INLINE (`NOME_DO_CEMETERY_GUARD`).
  - **O TETO DE TAB NÃO BARRA MAIS A TROCA COM A FLAG ALTA**
    (`TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS`): a segunda porta do mesmo defeito.
    Uma passada de AoE que derruba dois de uma vez faz o TAB cair em cadáver e
    gastar orçamento, e com o teto esgotado a rotação sai contra um morto — de
    fora, exatamente "sobrou um Gun Witch e o bot não está mais atacando".
    `flag is True` e não `flag`: **ilegível não autoriza gastar TAB**. Cada TAB
    paga `CARENCIA_APOS_O_TAB` e passa pelo `pos_tab_callback`, que é onde o
    Cemetery Guard é conferido — mais TAB exercita a trava, não a afrouxa.
  - **A FASE CONTINUA SÓ ENCERRANDO PELA SAÍDA DE COMBATE**
    (`EXIGIR_SAIR_DE_COMBATE_NOS_GUARDAS`, inalterado): *"não pode chegar no
    waypoint do boss já estando em batalha"*. Com a flag alta o portão devolvia
    vitória em **4,4 s** (medido), e chegar no boss em combate faz
    `esperar_entrar_em_combate` voltar na hora — a luta do boss começa sem o
    boss e termina "vitoriosa" quando o outro mob morre.
  - **CUSTO ACEITO, e agora é o oposto do anterior:** se algo que não é Cemetery
    Guard entrar na mira com o personagem em combate, o bot bate nele.
  - Travado por `tests/test_guardas_batem_ate_sair_de_combate.py`. No boss:
    entrou em combate, ataca — o único TAB é o de ENGAJAR (5 s). Nome ilegível:
    `CARENCIA_SEM_LER_O_NOME = 3.0` segura o golpe.
- **A BARRA DESENHADA VETA O MARCADOR** (`BARRA_DESENHADA_VETA_O_MARCADOR`), e é
  conserto de defeito reproduzido pelo usuário em 20/08/2026: *"na metade da vida
  do mob tem dado TAB em vez de matar"*. O log tem os três TABs em nove segundos,
  `hp_memoria=35`, **fonte única `marcador de morte na tela`** — e escore
  **0,971**, não margem de limiar. O `_por_consenso` punha o marcador em
  `testemunhas`, e `testemunhas` vencia `vivo` incondicionalmente: o marcador
  atropelava a barra. **Isso já contrariava a regra escrita logo abaixo**, que
  vale para o modo `"tela"` e da qual o `"consenso"` divergiu em silêncio.
  - **O veto é estreito:** só age com a barra LIDA e ACIMA de
    `LIMIAR_DE_VIDA_DO_ALVO`. Barra vazia ou não lida ⇒ o marcador decide como
    antes, e o impasse que ele resolve (alvo adquirido já morto, 35 mortes
    recusadas numa fase) continua resolvido.
  - **A DISCORDÂNCIA PASSOU A IR PARA O MOTIVO** (`CONTRA: ...`). Foi a ausência
    dela que atrasou este diagnóstico: a linha dizia `(1 fonte(s))` e **não dizia
    que a barra discordava** — "uma fonte" e "uma fonte contra outra" ficavam
    indistinguíveis no log.
  - **Por que o template casa a 0,97 com o mob vivo continua EM ABERTO**
    (`docs/decisoes/alvo-o-que-esta-medido.md`, pergunta I). O veto conserta o
    sintoma; a causa não está medida.
- **O MARCADOR DE MORTE NA TELA é a CONFIRMAÇÃO FINAL** (`EnemyDead.png`,
  `USAR_IMAGEM_DE_MORTE`). Ele **só opina quando o veredito normal sai
  INCONCLUSIVO** — barra desenhada continua decidindo, e ele não atropela
  ninguém.
  - **É o sinal de IDENTIDADE que faltava.** O marcador vive no QUADRO DO ALVO,
    que mostra a seleção ATUAL — exatamente o que o ponteiro não fazia (ele
    continuava devolvendo o cadáver antigo depois do TAB). Por isso ele pode
    furar o portão: o portão existe para não contar a morte do alvo ANTERIOR, e
    esta leitura não é do anterior.
  - **Consertou o impasse medido:** 35 mortes recusadas numa fase e 6 s sem TAB
    com mobs vivos, que é o que o usuário relatou nos Gun Witch.
  - **Procura SÓ na faixa do quadro do alvo.** O quadro do PRÓPRIO personagem é
    igual e fica no canto superior esquerdo — varrer a tela inteira faria "eu
    morri" ser lido como "o mob morreu". Travado por teste.
  - **`False` NÃO é "está vivo"** — é ausência do marcador, e ausência não é
    resposta. Só o `True` age.
  - **Só é LIDO quando a barra falha**, e não a cada 0,3 s da luta: casar
    template no caminho normal seria custo por nada.
  - **Vale para qualquer mob, inclusive o boss** — a leitura mora no
    `_alvo_morreu`, compartilhado. Mas na luta do boss `tabs_ao_morrer = 0`,
    então ali um veredito de morte não gasta TAB: **quem encerra o boss continua
    sendo SAIR DE BATALHA**, nunca esta imagem.
- **O PORTÃO PODE SEGURAR O TAB PARA SEMPRE; o conserto está DESLIGADO**
  (`USAR_PRAZO_DO_PORTAO = False`). Medido 18/08/2026: 35 mortes recusadas numa
  fase, 6 s sem TAB com mobs vivos — pior com AoE, que mata os quatro fora de
  ordem e faz o alvo seguinte ser adquirido JÁ MORTO. Um prazo conserta isso e
  **reintroduz o defeito de 13/08** (3 TABs no cadáver): "cadáver para sempre" e
  "cadáver novo" são o MESMO observável, a diferença não é tempo, é IDENTIDADE.
  O ponteiro é o único sinal de identidade e está **só no log** até haver
  medição que o autorize.
- **A flag baixou DEPOIS de a luta começar ⇒ o golpe PARA.** O `ja_entrou`
  separa "acabou" de "ainda não começou" — sem ele o engajamento forçado do boss
  morre: TAB sozinho não engaja, quem engaja é o golpe.
- **O boss só é dado por morto quando SAI DE BATALHA**, nunca por HP zerado: a
  segunda fase troca a struct, perde a seleção e o HP "sobe". **Ordem do usuário
  em 19/08/2026, e ela não tem exceção** — nem imagem nem ponteiro declara
  vitória no boss. Travado por `tests/test_virada_de_fase_nao_e_vitoria.py`, que
  fixa o conjunto de vitórias do laço lendo o AST.
- **NO BOSS O GOLPE NÃO PARA ENQUANTO A SAÍDA É CONFIRMADA**
  (`ATACAR_DURANTE_A_CONFIRMACAO_NO_BOSS`). A virada de fase derruba a flag por
  um instante, e **quem reengaja a fase seguinte é o GOLPE** — parado, ninguém
  reengaja, os 2,5 s de confirmação correm e a virada é declarada VITÓRIA com o
  boss de pé. Medido no log de 19/08/2026 (`creubo`): flag baixou aos 22 s,
  confirmada aos 25 s, `package_courage` → SAIR → Skull Herald; o usuário viu na
  tela e desligou o bot para impedir. **A regra da vitória não mudou** — o que
  mudou é o bot deixar de ficar passivo enquanto confirma.
  - **SÓ NO BOSS.** Parar o golpe foi correção de defeito real ("bater depois da
    luta convida o mob seguinte"), e isso vale onde HÁ mob seguinte. Na sala do
    boss não há, e depois dele o bot vai embora. O default do parâmetro é
    `False`; um teste lê o AST para garantir que só a chamada do boss pede.
  - **O dublê do teste precisou modelar CAUSALIDADE**: a primeira versão
    roteirizava a flag por tempo, e nesse mundo o caminho antigo passava. A flag
    só volta se o golpe sair. Com o interruptor desligado, o teste reprova em
    **24,6 s** — o mesmo número do log de produção.
- **A BREAK SOUL SÓ SAI NA SEGUNDA FASE DO BOSS**
  (`USAR_BREAK_SOUL_SO_NA_FASE_2`). Ela já teve dois estados errados: primeiro
  nunca era apertada, depois passou a sair SEMPRE — contra guardas, lixo e a
  fase 1 —, chegando em recarga na luta que decide a run.
  - **A virada de fase é vista por DOIS caminhos independentes, e os dois
    levantam a MESMA bandeira** por `_marcar_fase`, que é idempotente. Por
    MEMÓRIA: `_registrar_troca_de_fase`, na MESMA linha em que sai o log
    *"PRIMEIRA FASE MORTA: ... trocou de struct"*. Por TELA:
    `_conferir_fase_2_na_tela` (`USAR_IMAGEM_DA_FASE_2`, modelo
    `boss_2_fase.png`) — **a fase 2 tem DUAS vidas, e a primeira é AMARELA**;
    amarelo só existe ali. Redundância vale porque as duas falham por motivos
    diferentes: a de memória precisa do nome legível no instante da troca, a de
    tela não precisa de memória nenhuma.
  - **O amarelo é casado EM COR, e é medição:** em cinza a fase 1 marca **0,874**
    (acima do 0,85 de marcador de UI) e a Break Soul sairia no primeiro segundo
    da luta. Em cor a fase 1 dá 0,792 e a fase 2 degradada 0,985 —
    `LIMIAR_DA_FASE_2_DO_BOSS = 0.92` fica no vão. `load_color`, nunca `load`.
  - **A bandeira é LATCH, e a leitura SÓ acontece enquanto ela está baixa.** O
    amarelo ACABA (vem a vermelha), então baixar no `False` tiraria a Break Soul
    da metade final da fase 2. A conferência mora DENTRO do
    `if registrar_troca_de_fase` — é esse portão que garante "só na luta do
    boss"; fora dele a skill vazaria para os guardas. Travado por AST.
  - **`vida_do_alvo` LÊ `0.0` ENQUANTO A VIDA AMARELA ESTÁ NA TELA** — medido: o
    amarelo falha no `r > g*1.6` e a fração de vermelho sai zero, que naquele
    módulo é "o mob morreu". **Não é defeito ativo** só porque o veredito de
    morte é consultado apenas com `tabs_ao_morrer > 0`, e o boss usa o default 0.
    **NÃO alargue o teste de vermelho para aceitar amarelo:** é o mesmo número
    que descarta o fundo alaranjado da caverna. Bomba registrada e travada por
    teste, não consertada. **NÃO é o `fases_vistas` do
    `fight_boss`** — esse caminho está DESATIVADO (a chamada em `routine.py` é
    comentário) e quem luta é `fase_do_boss_por_combate`. A primeira versão
    ligou a bandeira lá e a skill nunca saiu em produção.
  - Só é seguro ali porque `registrar_troca_de_fase` é passado por UM chamador
    (`fase_do_boss_por_combate`): o método nunca roda na luta dos guardas.
  - **A bandeira é POR LUTA**, baixada no começo de `atacar_ate_sair_de_combate`
    junto com `_struct_do_alvo`. Zerar só no `fight_boss` não bastava, pelo mesmo
    motivo: código morto não zera nada, e a bandeira vazaria para os guardas da
    run seguinte — defeito intermitente, que só aparece a partir da segunda run.
- **`USAR_TAB_NOS_GUARDAS`** (interruptor); o caminho antigo está intacto em
  `_fase_dos_guardas_sem_tab`. `TABS_NOS_GUARDAS = 3` é TETO, não meta.
- **EM BATALHA O PERSONAGEM NÃO SE CURA.** Durante a luta o bot só luta. A
  única coisa consumível ali é a **poção de batalha**, e ela é RESERVA: só
  abaixo de `battle_hp_pct`, cujo padrão passou de 90% para **15%**. A skill de
  cura e o **F1 estão PROIBIDOS em batalha** — skill em si mesmo precisa de
  alvo, o F1 troca o alvo para o próprio personagem, e o engajamento do boss
  depende de quem está selecionado. Era bomba armada, não defeito ativo: sem
  tecla de cura configurada o `maintain` só bebia poção, e o F1 passaria a sair
  no meio da luta do boss no dia em que alguém configurasse a cura da Fairy.
  Travado por `tests/test_cura_por_skill.py`, com dente.
- **A cura por SKILL é um LAÇO, e ela vive nos INTERVALOS** — os três pontos
  onde o bot já parava para se curar: ao entrar na cave, no top-up depois de
  matar os guardas, e na recuperação fora da instância. `MODO_DE_CURA`.
- **APERTAR e CONFERIR têm cadências diferentes, e é aí que está o ganho.** A
  cura tem `SEGUNDOS_DE_CONJURACAO_DA_CURA = 1.6`; apertar a cada 0,1 s seriam
  DEZESSEIS apertos por conjuração — medido em simulação: **400 apertos contra
  3** para a mesma cura. Então aperta uma vez por conjuração e **confere a cada
  0,1 s** (leitura de memória, não fala com o jogo), saindo no instante em que a
  vida sobe. O teto é por **tentativa sem efeito** (3), não por relógio: sem
  mana ou em recarga isso custa ~7 s para descobrir, contra os 120 s de
  `max_heal_seconds` — que foi dimensionado para POÇÃO e não quer dizer nada
  aqui.
- **`prefer_heal_skill` NÃO EXISTE MAIS.** Quem tem tecla de cura tem cura — a
  configuração é a declaração. Era um segundo lugar dizendo o que a tecla já
  diz, e dois lugares dizendo a mesma coisa acabam discordando.
- **A poção de HP deixou de ser tecla obrigatória** quando há tecla de cura, e
  vice-versa. Uma das duas tem que existir.
- **A cura antes do boss é FORA de combate**, no waypoint dos 4 mobs: abaixo de
  40%, o laço de cura (ou a Super Skill, para quem não tem tecla de cura, com o
  efeito **conferido pelo ponteiro de HP**); sem efeito, poção. Na espera do
  boss NÃO se bebe poção (o boss cancela) — senta.
- **O TOP-UP ANTES DO BOSS VAI ATÉ 100%, SENTADO, e cumpre os 15 s.** Eram três
  defeitos no mesmo trecho, relatados em 19/08/2026: não sentava, a espera saía
  CURTA e nada era conferido.
  - **Jitter não pode entrar em DURAÇÃO QUE O JOGO EXIGE.** `ctx.tick(15.0)`
    sorteia `jitter(base, 0.15)` = 12,75 s a 17,25 s, e a poção dura 15 s — nas
    vezes baixas faltavam 2,25 s de efeito, sem nada no log dizendo isso. O prazo
    passou a ser por RELÓGIO: as fatias jitteram, o total não encurta.
  - **Uma poção de cada vez** até `ALVO_DO_TOPUP_ANTES_DO_BOSS = 100`, e **sai no
    instante em que enche** — não paga o resto dos 15 s. Teto por
    `max_heal_seconds`; estourar é aviso e a run segue.
  - **NÃO MEXE NA POSTURA** — nem senta nem levanta. A poção já senta sozinha e
    qualquer movimentação levanta; `sit` é interruptor, e mexer nele por garantia
    é a forma mais fácil de terminar de pé quando se queria sentado. A primeira
    versão sentava antes de beber, e o usuário mandou tirar.
  - **Precisou de poção e depois MORREU ⇒ o BC daquela conta é DESLIGADO.** Chegar
    no boss abaixo de 50% já é run apertada; morrer depois de gastar poção aponta
    ESTOQUE acabando, e conta sem poção não fecha run nenhuma. A conta fica
    online, com relogin; o checkbox desmarca nas duas interfaces.
  - Travado por `tests/test_topup_antes_do_boss.py`, e o dublê **modela o pior
    sorteio do jitter** — sem isso o teste da espera curta não pegaria nada.
- **Desmonte em batalha só nos 2 pontos de luta** (guardas e boss). Qualquer
  outro desmonte segura em batalha.
- **CATADOR DE LOOT** (`core/catador.py`), para a conta cujo pet **NÃO tem a
  skill de auto pick**. Gatilho `AccountSettings.usar_catador`, **por conta** —
  o usuário tem contas com o pet certo e contas sem ele. Roda pós-boss, **ANTES**
  do `package_courage`, porque ele abre o inventário e o que está no chão precisa
  entrar na bolsa antes.
  - **O botão é achado POR IMAGEM** (`btn_pick_up_all.png`), nunca por
    coordenada fixa — e é isso que torna o clique seguro **por construção**.
    Neste jogo quem move o personagem é o botão ESQUERDO; o direito interage.
    Então o anel de cliques direitos é livre, e o perigoso é o do "Pick up all":
    **sem o botão VISTO na tela, não há coordenada para clicar**. Sem essa
    regra ele cairia na cena 3D e o personagem andaria, a segundos da saída.
  - **Clica, espera 2 s, reconfere, clica de novo — até o botão SUMIR**,
    relocalizando a cada volta. O critério e a cadência são do usuário: *"deve
    esperar uns 2 segundos e verificar novamente... vai fazendo isso até o botão
    sumir da tela"*. **Conferir cedo demais é pior que esperar demais**: o botão
    ainda está lá porque o jogo não terminou de recolher, e os cliques do teto
    são gastos contra um recolhimento em andamento. `TETO_DE_CLIQUES = 10` é
    rede de segurança (20 s no pior caso), não meta.
  - **Procura depois de CADA clique do anel** e sai no primeiro sucesso (contra
    os ~3,8 s cegos do T-R0XX, de onde veio o anel).
  - **`loot_window_open()` NÃO decide nada** — vai só no log. `ADDR_LOOT_WINDOW`
    é mais um endereço herdado do GhostBot na versão 6139 e nunca confirmado
    aqui; o log das primeiras noites é que vai dizer se ele responde.
  - COMPLEMENTO: nunca derruba a run.
- **O ESCONDER JOGADORES HOJE É O `BlazesBot - PetBug.exe`**
  (`core/petbug.py`), programa de terceiro que o usuário já usava. Ele faz o
  esconder POR SESSÃO **e um "pet bug" contra disconnect**, num clique que cobre
  TODOS os clientes abertos. Com ele, o F12 preso saiu de uso
  (`esconder_jogadores.SEGURAR_ATIVADO = False`).
  - **Gatilho: a cada sessão de conta com BC**, ou seja a cada queda e relogin —
    decisão do usuário. O patch age nos clientes que estão RODANDO, e quem caiu
    volta num cliente NOVO. Só contas de BC.
  - **Cinco contas caem juntas ⇒ UM clique.** `INTERVALO_MINIMO = 30` com estado
    de módulo e lock: o primeiro aplica para todos. O intervalo é reservado ANTES
    de agir, senão duas contas passam pela janela de tempo.
  - **O clique vai no `hwnd` do BOTÃO** (`TButton` de texto `Patch`), por
    `BM_CLICK` — sem coordenada, e **funciona MINIMIZADO**, que é como a janela
    costuma ficar (medido: minimizada, `GetClientRect` devolve `(0,0,0,0)`). A
    coordenada fixa que o usuário autorizou fica como RESERVA.
  - **O RESULTADO É CONFERIDO** lendo o log do próprio programa (`TMemo`, por
    `WM_GETTEXT`): *"[OK] Patch applied to all running clients."* — "cliquei"
    deixou de ser a única coisa que se sabe.
  - **RENOMEAR A JANELA NÃO FUNCIONA** — medido: `WM_SETTEXT` devolve 0 e o título
    não muda. É formulário Delphi. O código de rename foi removido, não deixado
    como tentativa. A busca é pelo pedaço `"PetBug"`, que cobre os dois nomes.
  - COMPLEMENTO: falha nunca derruba a sessão.
- **O F12 preso está DESLIGADO** (`SEGURAR_ATIVADO = False`), e o caminho segue
  inteiro e testado. Quando ligado, ele segura a tecla **durante o processo
  inteiro** — entrada na cave, venda e Fay. Não só em volta do clique: o usuário
  mediu que o bloco curto *"acaba fazendo não clicar direito, principalmente ao
  entrar na cave"*.
  - **O mecanismo é a FILA.** Com `MODO_DE_CLIQUE = "postmessage_puro"` as quatro
    mensagens do clique são POSTADAS, e o KEYDOWN/KEYUP do F12 entram na MESMA
    fila encostados nelas — o cliente processa a tecla no meio do clique. Bloco
    longo tira a tecla de perto das mensagens do clique.
  - **`Input.key_down` CONTA ANINHAMENTO, por janela.** O bot segura a mesma
    tecla em blocos aninhados (o processo por fora, o par de cliques por dentro);
    sem contagem o bloco INTERNO soltaria a tecla com o externo ainda a querendo,
    e o log das duas vezes diria "segurei". O `WM_KEYDOWN` sai na primeira
    chamada e o `WM_KEYUP` só no zero. Contador por `Input` — uma conta não solta
    a tecla da outra.
  - **`key_up` sem `key_down` manda um KEYUP solto de propósito**: é rede para
    tecla presa por descuido, e soltar por engano é o lado seguro do erro.
  - **UM lugar cobre os QUATRO cliques de NPC** (link da cave, Rich, Altar Stone,
    saída): todos passam por `ui._abrir_dialogo_e_clicar`, e o `with` de dentro
    dele continua ali como rede para clique futuro. Travado por testes que leem
    o AST, nos três processos e no par de cliques.
  - **A tecla é solta em QUALQUER saída**, inclusive exceção — é context manager,
    não duas chamadas. Tecla presa que não é solta faz o bot passar o RESTO DA
    SESSÃO jogando com ela apertada.
  - **NÃO ESTÁ MEDIDO que segurar por MENSAGEM funcione.** `key_down` manda um
    `WM_KEYDOWN`; se o jogo consultar `GetAsyncKeyState`, mensagem nenhuma o
    convence. A favor: o `key()` normal faz skill sair, então o jogo reage à
    mensagem. O usuário vai conferir na tela (as outras contas dele são os
    "outros jogadores" na entrada e no vendedor). Custo de errar: uma mensagem
    ignorada.
- **ESCONDER JOGADORES pelo truque do F12 — DESLIGADO hoje**
  (`esconder_jogadores.ATIVADO = False`, decisão do usuário em 19/08/2026: "para
  testar outra hora"). O caminho está inteiro e os testes o forçam LIGADO, e
  aqui isso vale dobrado — o que o módulo faz é ABRIR O CHAT de propósito, e o
  que o torna seguro é a conferência de que ele fechou; comentar deixaria a
  parte perigosa para ser religada com a proteção nunca exercitada.
  **Desligado NÃO bloqueia a entrada na cave** — travado por teste.
  (`core/esconder_jogadores.py`, `KeyBinds.hide_players`, opcional): segura a
  tecla, abre o chat com Enter (o esconder GRUDA pela sessão), solta, fecha o
  chat. Rodaria **antes de CADA entrada na cave**, porque é por sessão e apertar
  a tecla de novo desfaz.
  - **A tecla é solta num `finally`** — presa, o bot inteiro passa a jogar com
    ela apertada.
  - **O fechamento do chat é CONFERIDO** (`state_chat_aberto.png`, a carinha
    amarela que só existe com o chat aberto — a barra inteira não serve, o texto
    ao lado do `say:` muda). Chat aberto desvia TODA tecla do bot para o campo de
    texto: a run morre em silêncio e um Enter depois **publica** aquilo no chat.
    Por isso é a única coisa da entrada que pode ABORTÁ-LA.
  - **Enter ALTERNA**, então leitura sem resposta NÃO aperta nada. Apertar "por
    garantia" tem metade de chance de abrir o que se queria fechar.
- **Pós-boss usa o(s) `package_courage`** pelo inventário, casamento **EM COR**
  (0.92; em cinza o vão não existe). COMPLEMENTO: nunca derruba a run. Três
  travas: `bag_open()` antes de clicar, posição a CADA clique, progresso por
  rodada.
- **FORA DA CAVE A GRADE TEM RECURSO DE COLETA em 100/100**, a mesma escala de
  inimigo — `Fresh Berry` nível 10 e `Magnesite Ore` nível 6 na leitura das 17:59.
  **Eles NÃO recebem alvo pelo TAB** (fato de jogo dado pelo usuário) e não
  existem dentro da cave, então nunca chegam ao `+0x808`: a escala 100 continua
  segura para decidir alvo. Vale saber porque quem varre a GRADE (não a seleção)
  vai topar com eles.
- **Memória:** raiz das cadeias de UI em `0x012CE340`; `ADDR_MODAL` está errado
  (guarda ponteiro, `modal_open()` é sempre False); `jogador+0x80C` é o PET; nome
  de entidade vem inline **ou** por ponteiro, e a ordem importa.
- **A simulação** (`tests/test_combat_vigia_do_alvo.py`) roda a luta inteira com
  relógio determinístico começando em **10.000,0** — `0.0` é sentinela. TRÊS
  dentes.

### Navegação — `docs/decisoes/navegacao.md`

- **Destravamento por VIZINHOS NA ROTA** (`destravar_pelos_vizinhos`): os três
  gatilhos (rollback, parado, sem progresso) chamam a mesma manobra, que devolve
  o índice ALCANÇADO.

  - A referência é a **posição ATUAL**, nunca o índice em que a rota achava que
    o personagem estava. Candidatos são os **imediatos** na ordem da lista —
    nunca "o mais próximo em linha reta": a rota é um CAMINHO, e pular waypoint
    é atravessar parede. Ordem: mais próximo → seguinte → anterior (no rollback,
    o anterior primeiro).
  - **Na rota, só frente.** A rota vai INTEIRA, com `comecar_em=N`.
  - Trava do retrocesso: não voltar duas vezes ao MESMO waypoint, e depois de um
    retrocesso só tentar a frente até a rota AVANÇAR além dele. **A memória é
    POR RUN**, zerada só em `routine`.
  - **2 passadas × 4 s**, números MEDIDOS (16 das 18 chegadas em ≤4 s). Eles
    escaparam para 1×1,5 s no halvamento e foi a causa do laço de 18/08/2026.
    `follow_path` direto; falhou tudo ⇒ devolve o controle ao SITUAR.
  - **Candidato que falhou não é tentado de novo no episódio**
    (`_candidatos_que_falharam`); falhados os imediatos, a manobra SE AFASTA na
    rota até `ALCANCE_DA_EXPANSAO`, pela ORDEM DA ROTA e nunca por distância.
    Zerada ao chegar; esgotada, recomeça em vez de paralisar.
  - `FOLGA_ROLLBACK = 1`: voltar 2+ índices é rollback. O passo lateral
    (`_destravar`) foi REMOVIDO; o círculo de offsets e `onde_retomar` seguem
    definidos mas DESLIGADOS do fluxo.
- **Antes de clicar no Altar Stone o bot encosta EXATO em (218,45)** — e se não
  encostar, **NÃO CLICA**. `mapa_bc.PRECISAO_NO_PATAMAR_DO_ALTAR = 0.9`, lida
  pelos dois lados. **"Parou" não é "chegou"**: só a LEITURA DE POSIÇÃO confirma
  (o `wait_until_still` devolve True só por ter parado). View Reset só quando o
  personagem andou.
- **A SAÍDA da cave tem UM número:** `PRECISAO_NO_PONTO_DA_SAIDA = 0.9`, lida por
  quem anda e por quem clica. Falhar sem clicar é melhor que falhar clicando —
  ali o clique perdido faz o personagem sair andando pelo covil.
- **O zoom do minimapa é padronizado a cada run** (batente + 2 cliques de volta).
  **Padrão, NÃO zoom-out máximo:** `MINIMAP_SCALE = 1.7` px/unidade foi medido no
  zoom em que o jogo abre, e toda a navegação sai daí.
- **O teleporte da Fay tem teto de 3 s e sai no instante em que confirma**, pela
  COORDENADA (`x_contradiz_a_cave`). Estourar o teto NÃO muda o retorno — vira
  aviso, senão um teleporte lento viraria item de retorno gasto à toa.
- **Tempos fora da cave:** o teto da espera do diálogo APRENDE
  (`limite_da_espera_do_dialogo`, 0,35–1,20 s, 1,6× acima da pior abertura). A
  lição "o leitor de arredores não funciona neste cliente" mora em
  `_BUSCAS_SEM_LEITURA`, por hwnd, no MÓDULO — na instância era reaprendida a
  cada run.

### Cliques e entrada da cave — `docs/decisoes/cliques-e-resolucao.md`

- **A TECLA TAMBÉM É `PostMessage`** (`MODO_DE_TECLA = "postmessage"`). O clique
  migrou em 18/08/2026 e a tecla ficou para trás — e o prêmio do PostMessage
  nunca foi o stuttering: **`SendMessageW` não tem timeout**, então um cliente
  que para de bombear mensagens prende a thread daquela conta PARA SEMPRE, sem
  nunca alcançar o `watchdog.check()`. Com a tecla síncrona esse defeito ficava
  inteiro no APP (100% teclado), no BC e no LOGIN (que digita a senha). Toda
  tecla passa por `Input._enviar_tecla`, ponto ÚNICO — trocar o interruptor troca
  `key`, `type_text` e `clear_field` de uma vez. O `lParam` segue em ZERO de
  propósito: mudar mecanismo e conteúdo no mesmo passo tornaria impossível
  creditar uma regressão.
- **O clique DIREITO sai em rajada** (`inputs.CLIQUES_DIREITOS_POR_TENTATIVA`).
  **NÃO se aplica ao clique ESQUERDO** (tem efeito POR clique) nem ao
  **MOVIMENTO PELO MINIMAPA** (`right_click(ponto, repetir=False)`) — ali cada
  clique é uma ORDEM DE ANDAR calculada da posição atual, e repetir perde
  precisão. A regra: **repetir vale para clique que ABRE, não para clique que
  MOVE.** Travado por teste, inclusive por leitura do fonte.
- **O RISCO A VIGIAR é clique que ALTERNA estado** — número par termina FECHADO.
  O caso é `team.py` (menu de sair do time, que reseta o boss).
- **A entrada da cave falha no clique no LINK, e está medida:** clique direito
  logo após um clique no link abre 14% das vezes, contra 78% em outro momento.
  `coords.cave_enter_confirm` (258,364) existe e **nunca é lido** — não amarrar
  nada nele sem foto.
- **O MOUSE SHIELD ESTÁ DESLIGADO** (`USAR_MOUSE_SHIELD = False`,
  `core/mouse_shield.py`), e **estar desligado depende de `MODO_DE_CLIQUE =
  "postmessage_puro"`**. Os dois andam juntos: o shield existia para impedir que
  um `WM_MOUSEMOVE` FÍSICO furasse a ordem das nossas mensagens, e com as quatro
  POSTADAS na fila esse mecanismo deixa de existir — um move físico entra na fila
  ATRÁS delas. **Voltar `MODO_DE_CLIQUE` para `"sendmessage_rapido"` obriga a
  religar o shield**, e o `inputs.py` diz isso no lugar da constante.
  - Hook `WH_MOUSE_LL` no processo DO BOT — não injeta nada no jogo.
  - **A medição que o tornava obrigatório era com SendMessage**, e continua
    valendo para ele: com o mouse do usuário em movimento sobre a janela, **sem
    shield 1/20 (5%), e o personagem ANDOU em 14 dos 20 cliques; com shield 20/20
    e nenhuma andada.** Com `postmessage_puro`, 40/40 com o mouse inteiramente
    livre. Ver `docs/decisoes/stuttering-mouse.md` para a corrida inteira.
  - **Com ele desligado NÃO EXISTE HOOK GLOBAL NENHUM**: o `MouseShield` nem é
    criado, e o mouse do usuário deixa de pagar a travessia do `WH_MOUSE_LL` a
    cada evento.
  - Este parágrafo já esteve errado: afirmava, em maiúsculas, que o shield era
    OBRIGATÓRIO e estava ligado, enquanto o código o tinha desligado. Agora
    `tests/test_indice_de_constantes.py` reprova quando o valor de um interruptor
    citado neste arquivo não bate com o do código — então a divergência não
    sobrevive a uma corrida de testes.
  - **O desfecho ruim não é clique perdido, é o personagem SAIR DO LUGAR** — o
    mesmo problema que esta lista persegue em cinco pontos.
  - **O bloqueio é TETO, não gasto:** `TETO_DO_BLOQUEIO_MS = 80` (medido pelo
    usuário; o 15 ms calculado reprovou), e o clique chama `liberar()` no
    `finally` — na prática o mouse fica preso ~5 ms.
  - **Fora da janela do jogo, 0,6 µs por evento:** a primeira pergunta do
    callback é uma comparação de float. Sem lock e sem `WindowFromPoint`.
  - **Só o MOVIMENTO é engolido.** Clique e roda do usuário passam sempre.
  - **O hook é DESINSTALADO quando o bot para** (`_soltar_o_mouse_do_usuario`).
    Antes vivia até o processo morrer, cobrando do mouse do usuário com o bot
    parado. A desinstalação ESPERA as contas terminarem, em thread daemon —
    `stop()` só sinaliza, e arrancar o hook ali deixaria o clique em voo sem
    proteção.
  - **O bot NÃO injeta na fila de input do SO** — não há `SendInput`,
    `mouse_event` nem `SetCursorPos`; `SendMessageW` chama o WndProc direto. Logo
    "afogar o barramento do mouse" não é risco deste código. Travado por teste
    que lê o AST (o arquivo cita `SendInput` em comentário).
- **`GetCursorPos` NÃO é como o jogo resolve a posição do clique** — medido (20
  de 20 com o cursor parado a 780 px). Foi a suposição contrária, nunca medida,
  que motivou a DLL de inline hook: dois dias, abandonada.
- **REAFIRMAR a coordenada entre down e up é PIOR que não fazer nada** (4/20
  contra 1/20): o `WM_MOUSEMOVE` extra vai com `MK_LBUTTON` e fabrica arrasto.
  `sendmessage_repetido` e `sendmessage_rapido_reafirmado` estão marcados **NÃO
  LIGAR**; `MODO_DE_CLIQUE` está em `"sendmessage_rapido"`.
- **CUIDADO COM MÉTRICA QUE CONFUNDE "MUDOU" COM "MUDOU PELO MOTIVO CERTO".** A
  primeira medição do shield deu 95% para o que era 5%: ela perguntava "o
  minimapa mudou?", e o personagem andando (o DEFEITO) também muda o minimapa.

### Venda — `docs/decisoes/venda.md`

- **Gatilho por CONTAGEM DE RUNS** (`runs_before_selling`, default 5). A leitura
  de bolsa está DESATIVADA — imprecisa; `precisa_ir_vender()` devolve `None`.
- **Começar o bot em Stone City VENDE antes de sair farmando.** Chama
  `travel_to_vendor()` → `sell_from_slot()`, **não** `run_maintenance()` (que
  gastaria pedra para ir aonde já se está). Reconhece pela COORDENADA **ou** pelo
  NOME — errar é assimétrico: não reconhecer trava o bot com a bolsa cheia. É
  complemento: falha vira aviso.
- **O RICH SÓ EXISTE EM STONE CITY, e chegar lá é CONFERIDO.**
  `travel_to_vendor` recusa fora da cidade (`esta_em_stone_city`) — sem o portão
  o filtro por "Rich" não acha nada e o personagem anda em LAÇO, 10 vezes. Para
  chegar: **Token × 10 e pedra × 3, uma a cada 10 s, conferindo após CADA uso**;
  tecla vazia pula o bloco dela; a recarga interna não barra o Token. **Pedra
  usada sem chegar é DIAGNÓSTICO** (ela não tem recarga ⇒ tecla errada ou
  estoque zerado), e o log diz isso.
- **Não vendeu ⇒ 1 run de BC e tenta de novo, até 3 rodadas**, e então DESLIGA o
  `bc_farm`. A run troca de mapa, e só isso reescreve o nome do lugar. **A run
  extra NÃO conta para o gatilho**; as rodadas zeram quando a venda dá certo.
- **O RICH É PROCURADO NA TELA** (`vendedor.png`), não clicado numa coordenada
  decorada. O motivo está medido no próprio `coords.py`: quando o ponto de
  parada mudou de (153,-492) para (158,-494) — **cinco unidades de mundo** —, o
  NPC saiu de (464,377) para (172,301), **quase 300 px**. A tolerância de 0,9
  unidade limita o erro, não o elimina. `coords.vendor_npc` continua como
  RESERVA: sem template, sem captura ou sem casamento, clica onde sempre clicou
  — nunca pior que antes. A busca é LIMITADA a um retângulo em volta do
  esperado, porque casar um sprite de NPC do outro lado do cenário seria um
  clique direito no lugar errado. Travado por
  `tests/test_vendedor_por_imagem.py`, com dente.
- **O ponto de parada do vendedor é (158,-494), EXATO**, e as coordenadas de
  TELA andam junto com ele. Um número só (`PRECISAO_NO_PONTO_DO_VENDEDOR = 0.9`)
  para quem anda e para quem clica. Fora do ponto **não clica**.
- **Sem tecla de retorno, a venda DESLIGA o `bc_farm` e salva** — mesmo desfecho
  dos 10 ciclos sem vender. A conta fica online e logada; o checkbox desmarcado
  é o sinal.
- **A CONFERÊNCIA DE SLOT VAZIO ESTÁ DESLIGADA** (`CONFERIR_SLOT_VAZIO = False`):
  a venda clica o total configurado, em passadas de 24, com Sell no fim de cada.
  Ao religar, quem decide é o **contraste do miolo** (24×24, corte 25,0), não
  casamento de modelo — a borda de hover existe nos dois estados e dominava o
  casamento (margem medida de 0.008).
- **A caixa "It's precious item" é conferida a CADA clique** (com ela aberta a
  passada vende zero): TEMPLATE DO TEXTO, com o **Ok derivado** — a caixa e a
  janela de venda têm botões idênticos. `_dismiss_confirm` confirma que fechou,
  até `TENTATIVAS_NO_OK = 3`.
- **O par de cliques do NPC usa `ui._abrir_dialogo_e_clicar`**: clica, CONFERE
  que o diálogo abriu, e só então clica no link. Sem diálogo o clique cai na
  cena 3D e o personagem ANDA.
- **`_ponto_do_slot` prefere a janela LOCALIZADA por imagem** (`_sell_anchor`);
  as calculadas são rede, não equivalente — medido, elas apontam para o slot 10
  quando a âncora aponta para o 4.
- **A grade da janela de venda COMPACTA** (ao tirar um item os seguintes sobem),
  ao contrário do inventário: é o que faz clicar N vezes no mesmo ponto esvaziar
  de N para frente, protegendo os slots 1..N-1.

### As duas interfaces — `docs/decisoes/interface.md`

- **Tela "Histórico de Quedas"** entre Estatísticas de BC e Log, núcleo em
  `core/quedas.py` (GUI e web só desenham). Só queda REAL (gatilho `ctx.ultima_
  queda`, que só o watchdog escreve). Registrada em `_run_session` **antes** de
  `_encerrar_caido` matar a janela — ordem obrigatória. Print só no
  `RECONNECT_DIALOG`, e é o PRÓPRIO quadro que detectou. JPEG + miniatura
  embutida (o WebView2 recusa `<img src>` local). **NADA DE DEV NA TELA**: a
  frase vem de `FASES`, mapa FECHADO. Retenção de 3 dias.
- **Cronômetros AO VIVO** (`run_now`, `boss_now`, `boss_atingido`) começam a
  contar quando o bot CONFIRMA que está dentro da cave. Os cards da última run
  são FIXOS.

- **Tecla repetida é BARRADA na digitação, nas duas interfaces.** O jogo não
  permite a mesma tecla em duas funções. **As teclas do APP ficam de fora da
  conta de propósito** — lá a mesma tecla se repete por desenho.
- **A ORDEM DAS CONTAS É A ORDEM DO ARRAY `accounts`** — não existe campo de
  ordem, e não pode existir. Reordenar é `BotConfig.reordenar_contas(uids)`, que
  desduplica por identidade de OBJETO, põe no fim quem a tela não citou e
  **aborta** em vez de gravar lista menor (perder conta ali é perder senha
  cifrada). **A identidade da conta na interface é `Account.uid`, NUNCA o
  índice** — com a tabela reordenável, escrita por índice grava senha na conta
  errada. A tela nunca recebe uid repetido (`garantir_uids_unicos`).
- **`Account.grupo` É RÓTULO VISUAL e nenhum caminho do bot pode ler dele**
  (travado por AST). Ordem, time do APP (`time_logins`) e grupo são ORTOGONAIS.
  O arraste **não tem debounce**: grava no soltar e, se falhar, recarrega do
  backend. Na GUI a reordenação é por BOTÃO — a `QTableWidget` tem seis
  `setCellWidget` e o arraste do Qt não move widget de célula.
- **A RODA DO MOUSE SOBE E DESCE TODO CAMPO NUMÉRICO** da web (`type="number"` e
  `type="range"`), incluindo os que a aba APP cria em tempo de execução — por
  isso o ouvinte é **delegado no `document`**, não instalado campo por campo.
  **O PASSO É O `step` DO CAMPO**, declarado no `index.html`: um passo por campo,
  o mesmo para a setinha e para a roda. `Shift` multiplica por 10. O handler é
  obrigado a **disparar `input` e `change`** (os rótulos de % dos sliders são
  escritos por ouvintes de `input`), **respeitar `min`/`max`** e **arredondar
  pela casa decimal do passo** (0,5 + 0,1 em float dá 0.6000000000000001). A roda
  só é consumida em cima de campo numérico; em qualquer outro lugar o painel
  continua rolando.
- **NENHUM CAMPO NUMÉRICO ACEITA 0.** Mínimo **1**; se for delay ou espera,
  mínimo **`MINIMO_DELAY_MS` = 100**. **ÚNICA EXCEÇÃO: `ed-app-limpar`**
  (`apagar_lixo_a_cada`), onde o 0 é um MODO — "nunca apagar" — e forçar 1 faria
  o deletador rodar a cada volta; apagar item **não tem desfazer**. A exceção é
  declarada no HTML, no teste (`EXCECAO_QUE_ACEITA_ZERO`) e em
  `docs/decisoes/interface.md`.
- **A TELA FALA MILISSEGUNDOS; O `config.json` CONTINUA EM SEGUNDOS.**
  `attack_delay` e `launch_delay` seguem `float` de segundos porque é o que
  `combat.py` e o supervisor leem — trocar a unidade no armazenamento obrigaria a
  migrar todo `config.json` existente para ganhar nada. A conversão é de
  APRESENTAÇÃO: `config.segundos_para_ms`/`ms_para_segundos` (Python) e as
  homônimas em `web/main.js`. **A IDA E A VOLTA TÊM DE FECHAR** — se não
  fecharem, abrir e salvar a tela sem tocar em nada muda a configuração
  (`test_o_tempo_vai_e_volta_sem_perda`). Valor inválido sobe para o piso, nunca
  para zero.
- **O INTERVALO DE COMIDA DO PET É A ÚNICA EXCEÇÃO DE UNIDADE**: continua em
  MINUTOS, faixa fechada **40..60** (`PET_FEED_MINUTOS_MIN`/`MAX`). Em ms pediria
  7 dígitos, e não é delay de mecânica — é grade de longo prazo. A faixa é
  **GRAMPEADA NA LEITURA** (`pet_feed_na_faixa`), não recusada na validação: o
  combo antigo da GUI oferecia 10/20/30 min e recusar faria o bot rejeitar a
  configuração inteira de quem já usava. Arquivo velho sobe corrigido — mesmo
  contrato do piso de 100 ms —, e a ponte reaplica.
- **`max_clients` FOI APOSENTADO** (26/08/2026): quantas contas rodam é decidido
  só por `enabled_accounts()`. O campo **saiu de vez e NÃO virou interruptor** —
  a convenção do interruptor vale para caminho de código, e isto era um TETO:
  teto órfão em `config.json` antigo continuaria cortando contas ativas em
  silêncio, sem nenhuma tela para desfazer. Fora nas cinco camadas (as duas UIs,
  a ponte, `config.py` e `supervisor.py`), travado por
  `test_max_clients_foi_APOSENTADO_de_ponta_a_ponta`.
- **EM `type="range"`, `step` MANDA NA GRADE DE VALORES, não no tamanho do
  toque.** Com `min="1" step="5"` a grade vira 1, 6, 11 … 96 e **90% fica
  inalcançável** — e 90% é o mínimo de vida para começar uma run. Slider fica com
  `step="1"` e declara o passo grosso da roda em **`data-passo-roda`**; é a única
  exceção à regra do `step`.
- **PASSO DE CAMPO É O MESMO NAS DUAS INTERFACES.** Todo `QSpinBox` já responde à
  roda por conta do Qt; o que não pode divergir é o passo. Alinhados: espera da
  APP = 100 ms (era 50 na GUI), shuffle = 5.
- **Balão de ajuda por CAMPO** na web (`.ajuda` + `#balao-ajuda`), no `<body>`
  em `position: fixed` — dentro do painel que rola seria CORTADO. Na GUI é o
  terceiro item de `_bloco_teclas`.
- **Login e senha editáveis inline** na tabela da web; a senha real NUNCA sai do
  Python (DPAPI) — a web só recebe `tem_senha`.
- **CURSOR DE LOG NUNCA É ÍNDICE DE DEQUE.** `puxar_log` recebe cursor ABSOLUTO
  e o histórico é `deque` com teto: passado o teto, comparar os dois direto fazia
  o histórico INTEIRO voltar a cada poll de 300 ms (~2 MB de literal JS na thread
  de UI, 3,3×/s). **Era a causa do congelamento da interface com o bot ainda
  rodando.** Traduza: `descartadas = _total - len(_historico)`. Mesma regra no
  frontend (`podarCache` poda cache e DOM juntos).
- **DICIONÁRIO POR `hwnd` PRECISA SER LIMPO NA MORTE DA JANELA**, e o motivo é
  CORREÇÃO: o Windows RECICLA hwnd, e a entrada órfã vai para a janela nova que
  herdou o número. Vale para `vision._pools` (DC + bitmap de ~3 MB por relogin;
  estourar handles GDI trava até a pintura da PyQt6) e
  `ui_service._BUSCAS_SEM_LEITURA`. Liberados em `_release()`, ANTES de
  `self.hwnd = None`.
- **Todo arquivo de log tem teto** (`ArquivoDeLogLimitado`), inclusive os três
  diários — eram os únicos sem, e o `localizacao.log` chegou a 4,8 MB.
- **UI web é Tailwind v4 + Vite de alta densidade.** O `body` NUNCA rola; cada
  seção é coluna flex com cabeçalho fixo e conteúdo `overflow-y-auto`. Siga essa
  densidade (fontes 12-13px, paddings contidos).
- **Editar `web/*` exige `npm run build`** — o pywebview abre o `dist/`.
- **A TELA DE LOG TEM TRÊS COLUNAS: hora | conta | mensagem**, alinhadas entre
  TODAS as linhas por `grid-template-columns: subgrid` (cada `.linha-log` é seu
  próprio grid; sem `subgrid` cada uma mediria sozinha e nada alinharia). Fica
  sob `@supports`, com `display: flex` como base — fora do suporte se perde só o
  alinhamento. **É o alinhamento que conserta a linha longa:** a continuação cai
  sob a própria mensagem, não sob a hora, e a linha continua sendo UMA coisa.
  `renderLog` separa a hora (`RE_HORA_DA_LINHA`, o formatter de
  `web_app._LogHandler`) num span só para o CSS ter onde pegar — é **só
  apresentação**: o clique direito e o botão "Copiar" seguem copiando `l.linha`
  inteira, com a hora no lugar, e `#btn-copiar-log` lê `logCache`, nunca o DOM.
  Linha que não casar com a hora entra inteira na coluna da mensagem.
- **NO LOG, FIO ENTRE LINHAS — NUNCA FAIXA ALTERNADA (zebra).** `podarCache`
  remove a PRIMEIRA linha da caixa, então `:nth-child(even)` inverteria a
  paridade de todas as linhas a cada poda; saturado em `LOG_CACHE_MAX = 4000`
  isso é uma piscada de tela inteira a cada poll de 300 ms.
  `.linha-log + .linha-log { border-top }` não tem paridade.
- **A CAIXA DO LOG NASCE SEM LAYOUT.** `.secao` é `display: none` e o app abre em
  Contas; escondida, `scrollHeight` e `clientHeight` são 0 e o
  `caixa.scrollTop = caixa.scrollHeight` de `renderLog` **não faz nada**. Medido
  ao entrar na aba com 35 linhas no cache: `sobrou: 381` px. Por isso
  `navegar("log")` chama `colarNoFimDoLog()` (dentro de
  `requestAnimationFrame`, porque a altura ainda não foi medida no instante da
  troca de `display`). **REFUTADO no caminho:** reexibir a seção NÃO dispara
  `scroll` — instrumentado, zero eventos.
- **`MARGEM_DO_FIM_DO_LOG = 26` (uma linha), não 8 px.** Arrastar a barra e parar
  20 px antes do fim desligava o acompanhamento em silêncio. Quem parou a menos
  de uma linha do fim quis dizer "fim".
- **A ROLAGEM PERSEGUE O FIM.** `scrollTo({behavior:"smooth"})` mira alvo FIXO e
  no log ao vivo o fim se move — terminaria atrás. O laço em
  `requestAnimationFrame` recalcula o alvo a cada quadro e vence
  `APROXIMACAO_POR_QUADRO_DO_LOG = 0.28` do que falta (medido: 12 quadros,
  ≈200 ms por lote). Acima de `SALTO_SUAVE_MAXIMO_DO_LOG = 340` px vai
  INSTANTÂNEO e a perseguição desiste no meio se o salto crescer: em rajada
  (250 linhas/poll) alcançar vale mais que enfeitar — medido `atrasoMax: 4 px`.
- **A TRAVA `rolagemDaTela` É OBRIGATÓRIA** e **gesto do usuário cancela a
  perseguição.** A rolagem animada dispara `scroll` em cada quadro, em posições
  intermediárias: sem a trava a animação desligaria o seguir-fim no meio do
  próprio movimento. `wheel`/`pointerdown`/`keydown`/`touchstart` cancelam —
  senão a tela briga com o arrasto do usuário. Esses eventos chegam ANTES do
  `scroll` que causam.
- **`prefers-reduced-motion` NÃO GATEIA OS EFEITOS DO LOG.** `MinAnimate = 0`
  nesta máquina faz o Chromium reportar `reduce` (as duas instâncias de Chrome
  do preview reportaram), e o portão apagaria os efeitos pedidos. Quem decide é o
  interruptor `EFEITOS_DO_LOG` via `podeAnimarOLog()`, **num lugar só** — o CSS
  não tem portão próprio.
- **O efeito de chegada (`.log-chegando`) tem DOIS tetos:** só lote pequeno
  (`LOTE_MAXIMO_ANIMADO_NO_LOG = 12`) e **nunca em reconstrução** — trocar o
  filtro repinta até 4000 linhas e o primeiro carregamento traz o histórico
  inteiro. Conferido: 0 das últimas 250 linhas de uma rajada foi animada.
- **MEDIR ANIMAÇÃO EXIGE CHROME VISÍVEL.** `test-web.ps1` abre com
  `-WindowStyle Hidden` e janela sem apresentação **não produz quadros** —
  `requestAnimationFrame` nunca dispara. Isso já produziu uma conclusão falsa
  ("`behavior:smooth` não anima em motor nenhum"). Prefira interceptar
  `scrollTop` com `Object.defineProperty` a amostrar em `rAF`: a ordem dos
  callbacks esconde os valores intermediários.
- **Hierarquia do log por tokens, sem cor nova na paleta:** `--log-msg` é o
  conteúdo (o mais claro), `--log-hora` é referência (apagada), `--log-fio` e
  `--log-realce` dão o ritmo. A etiqueta da conta deriva o próprio fundo da cor
  inline de `corConta` com `color-mix(in srgb, currentColor 15%, transparent)`.
  `--log-hora` no tema claro é `#77655f` porque `#9a8884` dava **2,97:1** sobre
  `#f5efed` — abaixo de AA para 11px.
- **DEBUG só em dev** nas duas interfaces: `run()` forçava DEBUG por cima do INFO
  que o `setup_logging` define em prod, multiplicando o volume ~10× e antecipando
  o defeito acima de horas para minutos.

### Ferramentas TEMPORÁRIAS — `docs/decisoes/ferramentas-temporarias.md`

Módulos FOLHA (nada do bot os importa), marcados `TEMPORÁRIO`. Os dois primeiros
exigem o **bot parado**, adotam a janela com `_adotar_janela_existente()` **sem
iniciar a thread** e devolvem o PID com `_release()` no `finally` de TODA saída —
sem isso o bot de verdade abriria um cliente novo.

- **`bot/bc/teste_venda.py`** — botão "Testar Venda": só `travel_to_vendor()` +
  `sell_from_slot()`.
- **`bot/bc/amostragem_de_cliques.py`** — "Amostrar Cliques": varre um grid em
  volta do alvo e mede taxa de abertura e latência. **Reancora antes de cada
  amostra** (clique que erra MOVE o personagem) e nunca usa
  `ui._esperar_o_dialogo`, para não envenenar o teto adaptativo.
- **`bot/recorte_do_time.py`** (`14-RECORTAR-TIME.bat`) — recorta o
  `state_team_member.png` que `bot/team.py` carrega e **nunca existiu em disco**.
  Acha o painel pela REPETIÇÃO (um bom recorte se acha N vezes em espaçamento
  regular, conferido com o MESMO `find_all_templates` que vai consumi-lo),
  DESENHA o que achou num JPEG e grava o PNG. Mora em `bot/` e não em `bc/`
  porque o painel de time serve os dois ecossistemas. Não clica em nada.
- **`bot/bc/diagnostico_do_link.py`** — fotografa em volta do clique no link.
  `ATIVADO` no topo, `MAXIMO_DE_EPISODIOS = 12` por processo. Não clica.
- **`tools/ler_camera.py`** (`17-LER-CAMERA.bat`) — vigia a struct da câmera AO
  VIVO e imprime UMA LINHA a cada mudança (`MUDOU = 0.0005`, o ruído de
  interpolação medido andando). Fecha sozinha em `SEGUNDOS_PADRAO = 300`.
  **SÓ LÊ** — travado por teste de AST (`write_float`/`set_camera` não podem
  aparecer no módulo). Existe porque ninguém sabe quais são os três números
  (`rotacao/angulo/zoom`) com a câmera na pose CERTA: os `(380, 0, 40)` que o
  bot escreve são da versão 6139. Roda-se ela, faz-se o **Lock the View** na
  mão, e a última linha impressa é a pose de referência. Exige **um PID só** —
  a câmera é de UMA janela, e misturar dois clientes na mesma tela não responde
  nada. Ver `docs/decisoes/navegacao.md`, seção da câmera.

---

## O catálogo de tempos — `docs/TEMPOS.md` (gerado)

Todo tempo do bot num lugar só: **252 esperas**, com valor atual, **valor
original**, natureza, arquivo, linha, função e para que serve.

**É GERADO**, e por um motivo prático: número de linha apodrece em uma semana.
Escrever à mão significaria um arquivo que aponta para o lugar errado depois do
primeiro refactor.

```
./.venv/Scripts/python.exe -m blazesbot.core.indice_de_tempos
```

### O que ele cataloga que nenhum outro índice cataloga

O `INTERRUPTORES.md` lista CONSTANTES. Este lista **TEMPO**, e inclui as
**esperas literais no meio das funções** (`ctx.tick(0.5)`) — que são metade das
esperas do bot e não aparecem em índice de constantes nenhum. São justamente as
que mais atrapalham quem quer acelerar o bot: espera cega escondida dentro de
uma função não aparece em lugar nenhum.

### A natureza é o que decide se vale mexer

| natureza | o que é | encurtar significa |
|---|---|---|
| **TETO** | prazo máximo; quem responde antes não paga | arriscar **o caso lento**, não o comum |
| **PASSO** | cadência de uma pergunta em laço | gastar **CPU**, não relógio |
| **FIXO** | espera **cega**: paga sempre, inteira | **ganho puro** — é aqui que se mexe |

A classificação lê o **nome e o comentário**. `ESPERA_DO_TELEPORTE` tem cara de
espera fixa e o comentário dele abre com *"TETO da espera do teleporte -- não é
mais o tempo gasto, é o limite"*: classificar só pelo nome marcaria como dívida
de espera cega justamente uma conversão que já foi feita.

### O ponto de restauração

`docs/tempos-originais.json` guarda a fotografia dos valores de referência. A
tabela mostra atual e original lado a lado e marca com **⚠** o que mudou.

**Ele NÃO é atualizado sozinho, e isso é de propósito.** Se toda geração
refotografasse os valores, o "original" seria sempre o de agora e o arquivo não
serviria para nada. Refotografar é ato deliberado:

```python
from blazesbot.core.indice_de_tempos import extrair, gravar_originais
gravar_originais(extrair())
```

Só depois de um valor novo estar provado em produção.

### A identidade não usa a linha

A chave de cada tempo é `arquivo::NOME` (ou `arquivo::função::valor`, para os
literais). Se a linha entrasse na identidade, **todo ajuste de código apagaria o
ponto de restauração de tudo abaixo dele**.

---

## O TAB do ecossistema APP — o bot adquire o alvo sozinho (25/08/2026)

> *"Na macro não vai mais precisar que o usuário cadastre o TAB como primeira
> linha; você irá dar o TAB e rodar a macro quando identificar que o target é
> diferente de 0 pela memória."*

### Por que isso é melhor que a linha 1

O TAB como primeira linha era apertado **toda volta, inclusive no meio de uma
luta**. E aí ele trocava de alvo: largava o mob machucado e recomeçava outro do
zero. O usuário não tinha como saber — **apertar TAB sem enxergar o alvo é
apostar**.

Agora o bot LÊ (`Memory.id_do_alvo`, `0` = nenhum):

```
tem alvo  -> a tecla nem sai
não tem   -> UM TAB, e espera o id aparecer (teto 0,6 s, sai no instante)
```

É a mesma virada que o combate do BC fez em 25/08 — ver
`docs/decisoes/memoria-primeiro.md`.

De brinde, **uma linha da macro a menos** é uma linha a mais de skill, já que o
número de passos é fixo.

### O ciclo completo do alvo no APP

As duas metades da mesma regra, e as duas só existem porque o bot agora
**enxerga** o alvo (`hp/max_hp` pela memória):

```
morreu antes de a macro acabar  -> CORTA a rotação aqui e vai para o próximo
não morreu                      -> NÃO aperta TAB; recomeça a macro no MESMO mob
```

> *"Caso o mob morra antes de acabar a macro inteira, pode ir para o próximo mob
> sem terminar a macro. Ou, caso não morra, você não aperta TAB: você recomeça a
> macro até garantir que ele morreu, daí você passa para o próximo mob."*

Terminar de bater num cadáver é tempo puro perdido, e o mob seguinte está
esperando. Antes disso o bot era cego: rodava a sequência inteira ou nada, e o
TAB da linha 1 trocava de alvo toda volta — largando o mob machucado no meio.

**A conferência acontece DENTRO da espera de cada linha**
(`PASSO_DA_CONFERENCIA_DO_ALVO = 0.1`), não só entre elas: uma linha de 3000 ms
sem isso faria o bot bater num cadáver por até três segundos.

### O TAB só conta quando o ID MUDA

Defeito relatado: *"os tabs não estão funcionando direito; tem que perceber que
o value do alvo alterou para confirmar se trocou, aí sim pode começar a rodar a
macro"*.

A primeira versão perguntava só **"tem id?"** depois do TAB — e tinha: **o
cadáver continua selecionado, com o MESMO id**. O bot apertava TAB, lia o id do
corpo, dava a troca por feita, e rodava a macro contra um cadáver. A cada volta.

A confirmação passou a ser o id ficar **DIFERENTE** do de antes:

| depois do TAB | veredito |
|---|---|
| id igual ao de antes | não trocou — aperta de novo |
| id `0` (nada selecionado) | mudou, mas não para um alvo — aperta de novo |
| id novo, mob **vivo** | trocou. Pode rodar a macro |
| id novo, mas **cadáver** | o corpo está na roda do TAB — aperta de novo |

### Dois cortes, porque são dois fracassos diferentes

> *"Caso precise de mais de 1 TAB até notar a troca de target."*

A roda do TAB contém **todas** as entidades próximas — e num ponto de farm os
**cadáveres se acumulam**: cada corpo fica na roda por 7 a 13 s, e o bot mata
continuamente. Três ou quatro corpos ao mesmo tempo é o normal, não a exceção.

| corte | quando | por quê |
|---|---|---|
| `TENTATIVAS_DE_TAB = 8` | girou a roda e só achou cadáver | ciclar é **barato**: cada salto sai no instante em que o id muda |
| `TABS_SEM_RESPOSTA_PARA_DESISTIR = 2` | o id não mudou nenhuma vez | a tecla **não está pegando**, e aqui cada tentativa paga o teto inteiro |

Sem essa separação, uma tecla mal configurada custaria
`8 × SEGUNDOS_PARA_O_ALVO_APARECER` — quase 5 s por volta, para sempre. E com as
3 tentativas da primeira versão, o bot desistia com mob **vivo a dois saltos**.

Esgotado qualquer um dos dois, **a macro roda assim mesmo** e sai um aviso que
diz **qual** foi o motivo — macro de buff ou de pesca não pode parar por falta
de alvo, e quem lê o log precisa saber se o problema é a tecla ou é não ter mob.

### CADÁVER NÃO É ALVO

O corpo fica selecionável por **7 a 13 s** depois da morte (medido em
20/08/2026), então `id != 0` continua verdadeiro. Por isso o TAB não pode ser
decidido pelo id sozinho — quem decide é a **VIDA**:

| leitura | o TAB sai? |
|---|---|
| `id == 0` | sim — não há alvo |
| `id != 0` e `hp > 0` | **não** — alvo vivo, trocar largaria o mob machucado |
| `id != 0` e `hp == 0` | sim — é cadáver |
| não deu para ler a vida | **não** — "não sei" nunca larga um mob que pode estar vivo |

O erro seguro aqui é bater em quem já morreu por mais uma volta; o inseguro é
largar um mob vivo, porque o largado continua batendo.

### O que ele NÃO faz

**Não bloqueia a volta.** Se depois do TAB continuar sem alvo — não há mob por
perto —, a macro roda assim mesmo: macro de buff, de pesca ou de qualquer coisa
que não seja luta não pode parar por falta de alvo. Travado por um teste de AST
que reprova qualquer `return` com valor ou `raise` dentro de `_garantir_alvo`.

**Não derruba a volta se a leitura falhar.** Memória é leitura de processo
alheio e pode falhar a qualquer instante; sem leitura, o APP roda exatamente
como antes — mesmo contrato do pet e da trava de posição.

**Não para por falta de configuração.** Sem a tecla "Próximo alvo", vira aviso
uma vez por sessão.

## O laço do APP depois de 26/08/2026 — a revisão do Core Loop

Esta seção é o detalhe do que o `CLAUDE.md` resume na seção "Cura no APP".
O porquê medido de cada item mora em `docs/decisoes/cura-no-app.md`.

### O que estava quebrado, e como se soube

O usuário relatou dois sintomas em dias seguidos:

* 25/08 — o bot bate em cadáver e não sai mais dele;
* 26/08 — *"começou a ficar andando e dando tab, chamou vários mobs e morreu"*.

O primeiro está **medido**. `logs/dev/arquivo/blazes-dev-2026-08-25.jsonl`,
agregado por mensagem:

| ocorrências | linha |
|---:|---|
| 1251 | `APP alvo: Rose Snake nv61 0/100 (0%)` |
| 79 | `APP alvo: Rose Snake nv61 100/100 (100%)` |
| 5 | `APP: alvo novo ... começando a macro da linha 1` |
| 9 (máx.) | `o alvo caiu no meio da macro` |
| 0 | `TAB(s) seguidos e o alvo não mudou` |
| 0 | `sem tecla de 'próximo alvo' configurada` |

E a janela cronológica de 13:42:51 → 14:10:01 é uma linha `0/100` a cada ~21 s
por **28 minutos**, cadência de metrônomo — uma volta inteira da macro (14
linhas / 13000 ms mais overhead) contra o mesmo corpo, sem um único TAB.

**Localização por eliminação:** zero linhas de "a tecla não pega", zero de "sem
tecla configurada", uma de "girei a roda". O TAB nunca foi tentado. O único
caminho que sai de `_garantir_alvo` sem tentar nada e sem logar nada é o portão
`if id_antes and not self._alvo_morreu(): return True`.

**A causa:** `_alvo_morreu()` respondia `False` quando `alvo_atual()` devolvia
`None`, e `alvo_atual()` devolve `None` para três causas distintas (sem alvo /
entidade ausente do array / struct inconsistente). Prova de não-determinismo: na
MESMA volta, `_alvo_morreu()` lia `None` e milissegundos depois
`_registrar_o_alvo()` lia a entidade com `hp=0` e imprimia a linha.

### As regras que saíram disso

1. **HP legível decide na primeira leitura.** `hp <= 0` é morte;
   `alvo_atual()` já validou `0 <= hp <= max_hp` antes de responder. Uma versão
   intermediária exigiu N amostras consecutivas e ficou PIOR — o cadáver
   deixava de ser reconhecido no começo da volta e o portão voltava a bloquear
   o TAB.
2. **HP ilegível: decide a flag de combate**
   (`USAR_COMBATE_COMO_RESERVA_DE_MORTE`). A transição `True → False` com o
   alvo ainda selecionado prova a morte. A flag NÃO baixar não prova nada — ou
   o mob está vivo, ou tem outro mob batendo. A reserva **só sabe dizer
   "morreu"**, e o veredito é **latch por identidade**: a transição acontece uma
   vez, e sem guardá-la a pergunta seguinte voltaria a "não sei".
3. **"Não sei" persistente libera o TAB**
   (`VOLTAS_COM_ALVO_ILEGIVEL_PARA_TROCAR = 2`). Com outro mob batendo, nem o
   HP nem a batalha respondem sobre este alvo. Uma leitura boa zera o contador
   — a entidade some do array por 1 leitura em ~45 com o mob VIVO.
4. **Um ponto de vida derruba toda suspeita**, inclusive o latch da reserva.
5. **A mesma morte não sai duas vezes** (`_ultimo_alvo_morto_id`). Trava a
   CONTAGEM e o LOG, **nunca o veredito** — travar o veredito faria
   `_garantir_alvo` reler "alvo vivo" no cadáver já contado.
6. **Sem tecla de alvo e sem alvo vivo, a volta não roda.** Devolver `True`
   mandava a macro contra o nada, a volta era cortada na primeira linha sem
   enviar tecla e sem pagar espera, e `rodar()` girava com a CPU em 100%.

### O critério de aquisição: qualquer vida, desde que seja outro alvo

`EXIGIR_ALVO_INTEIRO = False` desde 26/08/2026, revogando o pedido de 25/08.
Ligado, num ponto de farm movimentado quase todo mob da roda está machucado: o
bot recusava todos, girava `TENTATIVAS_DE_TAB` inteiras, devolvia `False`, e a
volta seguinte recomeçava a roda — TAB contínuo, e cada TAB é um mob a mais
olhando para o personagem. É o sintoma de 26/08.

Quem separa um alvo do anterior é a **IDENTIDADE** (`_esperar_o_alvo_trocar`
exige id diferente). Cadáver continua recusado (`hp <= 0`).

### A régua do inalcançável, reancorada

`LINHAS_SEM_DANO_PARA_TROCAR = 3` (era 2; o usuário subiu em 26/08).

O portão `hp >= max_hp` **saiu**. Ele existia para impedir que a régua largasse
um mob em luta — mas pergunta ao `max_hp`, e com mobs machucados sendo
adquiridos ele calaria a régua para sempre no próprio mob do penhasco.

O que substitui é `_ja_tirou_vida`, e diz a mesma coisa ancorada na
**aquisição**: *"desde que peguei este alvo, eu ALGUMA VEZ tirei vida dele?"*.

| situação | referência | veredito |
|---|---|---|
| adquirido a 100, ainda 100 após 3 linhas | 100 | LARGA |
| adquirido a 60, ainda 60 após 3 linhas | 60 | LARGA |
| adquirido a 100, ferido para 97, parado em 97 | 100 → dano visto | CALA para sempre |
| HP ilegível | — | não conta, nem a favor nem contra |

**A régua larga marcando UM id** (`_largar_o_alvo_inalcancavel`), gasto na volta
seguinte e apagado — nunca uma lista de ignorados. Ela **não aperta tecla**:
existe um só lugar que adquire alvo, e é o passo 4 da volta, com conferência de
id novo, os dois respiros e régua recomeçada.

### A roda do TAB é ordenada por DISTÂNCIA — 26/08/2026

Informação do usuário, e ela derruba o raciocínio que sustentava
`TENTATIVAS_DE_TAB = 8`:

> *"Ainda está se perdendo no tab. O ideal é tentar manter só no PRIMEIRO tab,
> para evitar ficar indo em mobs muito longes, pq o tab vai primeiro no mob MAIS
> PERTO e conforme vai clicando ele vai indo nos mobs mais LONGES."*

A versão anterior dizia *"ciclar é barato"* e media o custo de oito saltos em
**milissegundos**. O custo nunca foi tempo: **cada salto é um mob mais longe**, e
engajar longe faz o personagem atravessar o ponto de farm até ele, puxando o que
estiver no caminho. A roda de oito era o motor do *"chamou vários mobs e morreu"*.

`TENTATIVAS_DE_TAB = 1` — **um único TAB por aquisição.**

A primeira versão deste conserto usou **dois** saltos, com o argumento de que o
segundo servia para passar pelo cadáver do mob recém-morto (que está encostado
no personagem e fica selecionável de 7 a 13 s). O usuário voltou no mesmo dia e
cortou o argumento:

> *"Eu quero que seja apenas 1 único tab por vez, pois com essa questão de
> GARANTIR o tab, está fazendo ir em outro mob e não no mais perto."*

E ele está certo sobre o que o segundo salto de fato faz. "Passar pelo cadáver"
era o caso imaginado; o caso que ACONTECE é o segundo salto cair no segundo mob
mais próximo — que é literalmente *"ir em outro mob e não no mais perto"*.
**Insistir para GARANTIR um alvo troca a mira certa por uma mira qualquer.**

**Quando o único salto não serve:** a volta acaba sem macro, o bot paga
`SEGUNDOS_PARA_A_RODA_REINICIAR` (3,0 s) e a volta seguinte tenta de novo — de
novo no mais perto. Nada é "garantido", e é esse o ponto: **é melhor ficar sem
alvo por alguns segundos do que ter o alvo errado.**

O caminho de vários saltos **não foi apagado**, virou interruptor: subir a
constante religa `ESPERA_ENTRE_TABS` e o resto do laço sem mexer em mais nada.

> O 3,0 s **não tem medição atrás** e está dito assim no código: ninguém mediu em
> quanto tempo a roda deste cliente reinicia. É folga confortável e barata — só
> é paga quando NÃO houve alvo.

`TABS_SEM_RESPOSTA_PARA_DESISTIR` continua em 2, mas **passou a contar entre
VOLTAS** em vez de dentro da rajada: com um único salto por aquisição, um
contador local nunca chegaria a dois, e uma tecla mal configurada seria relatada
como *"só cadáver por aqui"* para sempre — o diagnóstico errado, com o usuário
procurando mob onde o problema é a tecla.

Os dois cortes existem porque os dois fracassos pedem **ações** diferentes: um
manda esperar, o outro manda configurar. E enquanto o veredito da tecla morta
não existe (faltam voltas), o log **cala** em vez de arriscar o diagnóstico
errado; o aviso da tecla sai **uma vez por sequência** e rearma quando a tecla
volta a responder.

### A linha 0 da macro — o TAB, e o tempo depois dele

> *"Como a macro 0, mas sem poder editar o botão e não pode colocar em outro
> lugar, sempre será a primeira, e o tempo sim será editável; aquele 1 segundo
> após o tab será isso."* (26/08/2026)

**Ela não é um `AppStep`.** Como linha de verdade obrigaria `passos_ativos`,
`uma_volta` e a régua do inalcançável (que conta LINHAS da macro) a conhecer uma
exceção que não bate em ninguém. A tela **desenha** como linha 0; o executor lê
um número de outro lugar.

| | |
|---|---|
| tecla | **espelho** de `KeyBinds.next_target` (aba Teclas), somente leitura |
| tempo | `AppConfig.espera_depois_do_tab_ms`, padrão 1000, editável |
| posição | fixa, sempre a primeira; as linhas da macro seguem em **1..20** |

**A tecla é espelho e não cópia**: escrever `TAB` fixo faria a tela mentir para
quem trocou a tecla — o bot apertaria uma e a tela mostraria outra.

**Isto não devolve o TAB para dentro da macro.** O bot continua decidindo
sozinho quando apertá-lo, lendo a memória; a linha 0 dá **visibilidade** (ver
que o TAB acontece, e onde) e **controle do tempo**. O TAB como linha 1 era
apertado toda volta e largava mob machucado — defeito medido, consertado em
25/08/2026 e que não volta.

Na web, a linha 0 **não tem a classe `app-linha`**, e é isso que a mantém fora
de `steps` e fora da prévia. Travado por `tests/test_linha_zero_do_app.py`.

### O piso de 100 ms em todo campo de tempo do APP

> *"O mínimo vai ser 100ms em todos os campos do APP."*

`MINIMO_DE_ESPERA_DO_APP_MS = 100`, e ele vale para as 20 linhas da macro **e**
para a linha 0. Zero deixava duas teclas saírem no mesmo instante e o cliente
engolia a segunda — o mesmo defeito do botão "Sell" da venda, espalhado pela
sequência inteira.

O piso é aplicado em **três lugares**, e a repetição é deliberada:

* `AppStep.__post_init__` — qualquer linha construída em qualquer lugar já
  nasce respeitando o mínimo;
* `_app_from_dict` e a ponte web — arquivo salvo por versão antiga sobe
  corrigido, e "a tela impõe" não é garantia, é boa vontade;
* os campos das duas telas.

O executor guarda a **própria cópia** do número porque ele não importa
`blazesbot.config` (isolamento travado por teste); um teste confere que as duas
batem.

### O alvo do APP vem pelo MESMO caminho do BC

> *"Sobre o HP do target, está sendo analisado como fazemos no Gun Witch?"*
> (26/08/2026)

Não estava. As duas pontas terminam em `Memory.alvo_atual()`, mas o APP passava
a leitura pelo `_ler` do supervisor — e o `_ler` tem o portão `critical_ok()`,
que exige `hp()`, `max_hp()` **e** `position()` **do personagem**.

Nenhuma das três tem relação com o alvo, e `position()` é uma cadeia de
ponteiros. **Uma leitura ruim da posição do personagem vetava a leitura do
mob**, e o executor recebia o mesmo `None` de *"a entidade sumiu do array"* —
caindo na reserva e no escape de "alvo ilegível" onde o BC lia tudo.

Hoje o APP usa `TargetHybrid` (`core/target_hybrid.py`), como o BC:

| | antes | agora |
|---|---|---|
| caminho | `_ler(memoria_do_pet.alvo_atual)` | `TargetHybrid.entidade_do_alvo(pid)` |
| portão | `critical_ok()` | nenhum |
| relogin troca o PID | handle velho, em silêncio | reabre sozinho |

O portão **continua valendo** para as leituras do PERSONAGEM (vida, batalha,
sentado, posição, pet), que é para o que ele foi feito. E o APP continua **sem
a reserva da tela**: só `entidade_do_alvo` e `id_do_alvo`, que são memória pura.

### A poção cancelada, e a ordem de andar que ninguém pediu

> *"O primeiro uso da poção está gerando algum problema; ele clica na poção,
> CONSOME ela, mas CANCELA logo em seguida."* (26/08/2026)

`mandar_voltar_para_base()` clicava **sempre**, inclusive com o personagem
parado em cima da base. Clique direito no minimapa é **ordem de andar**, e uma
ordem pendente cancela a bebida no instante seguinte.

O `_voltar_ao_ponto` da cura conferia a distância DEPOIS e concluía *"cheguei no
ponto inicial; vou me curar"* — verdade, e tarde. No log de 25/08 essa linha
aparece 23 vezes e nenhuma parecia defeito.

Agora a distância é conferida **antes**: dentro de `TOLERANCIA_POSICAO`, devolve
`True` **sem clicar**. `True` e não `False`, porque *"já estou lá"* é sucesso —
`False` significa "não havia como voltar" e faria a cura avisar que vai curar no
lugar errado. **"Não sei" continua clicando.**

### O atraso entre o TAB e a linha 1

> *"Às vezes está existindo alguma delay entre o clicar o TAB e começar a macro,
> e NÃO é a configuração nova, pois eu testei colocando 100ms. (...) Nós
> desenhamos a ordem para o TAB ser o ÚLTIMO e logo em seguida rodar a macro."*

Duas causas somadas:

| causa | conserto |
|---|---|
| `_esperar_o_alvo_trocar` reusava `PASSO_DA_ESPERA_DA_BASE` (0,1 s) — cadência de CAMINHADA — e perdia até 100 ms por aquisição | `PASSO_DA_CONFIRMACAO_DO_TAB = 0.01`; a leitura do id é um `read_int` (~1 µs) |
| a régua e o log ficavam DEPOIS do respiro, entre o fim da espera e a primeira tecla (e o log escreve em disco) | o respiro passou a ser a **ÚLTIMA** coisa da aquisição |

NÃO É "um número lido por dois lados": *"cheguei?"* e *"trocou?"* são perguntas
diferentes, com custos e urgências diferentes.

De brinde: a régua recebe o `alvo` que quem chama já leu (uma leitura a menos e
sem duas fotos de instantes diferentes), e a linha *"APP alvo: ..."* deixou de
sair duplicada logo depois de *"alvo novo ..."*.

### As conferências são só fora de batalha

> *"Saiu de batalha → pet → comida → voltar ao ponto → TAB → e por assim vai."*

Regra **geral**, não só da urgência. Antes só a caminhada era barrada em
batalha, e a comida tinha um defeito calado por causa disso: a tecla de alimento
é **ignorada pelo jogo em combate** (está escrito no próprio `feed_pet`), mas o
`PetFeeder` registrava a refeição assim mesmo — o pet passava fome com o
cronômetro dizendo que tinha comido.

Custo aceito: numa luta longa o pet não é conferido até ela acabar. Durante a
luta o pet ou já está lá, ou não chegaria a tempo de ajudar naquela luta.

### Em batalha o personagem NÃO anda

> *"É bom ter essas delays e deixar os 2 segundos de retorno para o lugar, A
> MENOS QUE ESTEJA EM BATALHA é claro (...) é bom ter mais cuidado para não sair
> puxando os outros mobs e fazer ele morrer."*

`SEGUNDOS_PARA_A_TRAVA_DEVOLVER` **continua em 2,0 s** — o pedido não é andar
menos, é não andar na hora errada. Atravessar o ponto de farm com um mob em cima
faz ele acompanhar e passar por outros: o personagem chega na base com três em
cima em vez de um.

`ANDAR_SO_FORA_DE_BATALHA = True` guarda as **duas** ações que tiram o personagem
do lugar (a caminhada de volta e o shuffle anti-AFK), pelo mesmo método
`_lutando()` — se cada uma tivesse a própria régua, uma ficaria para trás no
conserto seguinte. Ele consulta duas fontes e basta UMA dizer que há luta:

| fonte | falha quando |
|---|---|
| flag de combate em `True` | demora a subir no primeiro golpe |
| alvo selecionado com vida | a entidade some do array por 1 leitura em ~45 |

**"Não sei" vale FALSE**, e aqui isso é deliberado: a resposta serve para
SUPRIMIR uma ação. Se "não sei" suprimisse, um cliente sem leitura de memória
nunca voltaria ao ponto e derivaria pelo mapa — pior que voltar na hora errada.

### O respiro depois da morte

`ESPERA_DEPOIS_DA_MORTE = 1.0`, pago **só quando um mob caiu**.

> *"Está trocando de alvo rápido demais, aí acaba colocando o personagem em
> risco."*

Não é só cautela — ele tem trabalho técnico. No instante seguinte ao golpe que
mata, a flag de combate ainda está em `True` (o jogo leva um momento para
baixar), e neste laço **duas decisões dependem dela**: a caminhada de volta (que
não pode sair em batalha) e o portão da cura (que espera sair de batalha para
beber). Sem o respiro, as duas leem "ainda em batalha" logo depois de uma morte
limpa: a caminhada é suprimida sem motivo e a cura adia sem motivo.

### Os respiros em volta do TAB

`ESPERA_ANTES_DO_TAB` (0,6 s) e `ESPERA_DEPOIS_DO_TAB` (1,0 s), pedidos pelo
usuário em 26/08/2026 — o de baixo subiu de meio segundo.

| respiro | o que se perde sem ele |
|---|---|
| ANTES | a **própria aquisição**: o TAB chega em cima das últimas teclas da macro e é engolido, e o bot roda mais uma volta inteira contra o cadáver |
| DEPOIS | a **primeira skill da rotação**, a que abre a luta |

Regras:

* **só são pagos quando uma tecla vai sair** — alvo vivo na mira não gasta nada,
  então o custo é uma vez por mob morto, não uma vez por volta;
* **o de cima é pago UMA VEZ por aquisição, nunca por tecla.** A roda gira até
  `TENTATIVAS_DE_TAB` vezes e 0,6 s por salto somaria ~4,8 s sem comprar nada.
  As teclas da macro que podem engolir o TAB só existem antes do primeiro salto;
  entre saltos, `_esperar_o_alvo_trocar` só devolve com o id JÁ trocado, ou seja,
  com o TAB anterior processado;
* **há ainda um terceiro tempo aqui**, `ESPERA_ENTRE_TABS` (0,35 s), pago ENTRE
  saltos da roda: `_esperar_o_alvo_trocar` devolve no instante em que o id muda,
  então sem ele os saltos saíam em rajada. É menor que o de entrada de propósito
  — são propósitos diferentes, e ele não pode ser longo a ponto de a roda do jogo
  reiniciar no meio da aquisição;
* **o de baixo é a LINHA 0 da macro** desde 26/08/2026 — vem de
  `AppConfig.espera_depois_do_tab_ms` e não mais da constante, que passou a ser
  só o padrão de quem roda sem configuração;
* **na URGÊNCIA o de cima não é pago e o de baixo é.** O de cima existe para o
  TAB não chegar em cima das teclas da macro, e na urgência a macro foi cortada
  e a observação já gastou até 3 s. O de baixo garante que a primeira skill da
  rotação não se perca, e perder a abertura da luta com um mob em cima é pior
  que gastar o tempo. **A pausa de reinício da roda também não é paga na
  urgência** — ela é otimização de mira, e com um mob batendo tentar de novo
  vale mais que tentar melhor;
* **nenhum deles é `time.sleep`.** Passam por `_dormir`, que fatia e responde
  ao Parar. `_esperar` não serve aqui: ele confere a morte do alvo lá dentro, e
  na aquisição o alvo selecionado é o cadáver que se quer largar — devolveria
  "pare" no primeiro décimo de segundo.

### Contadores

| contador | quando incrementa |
|---|---|
| `voltas` | **só** no fim natural do laço das linhas, no mesmo mob |
| `voltas_abortadas` | qualquer saída antecipada |
| `mortes_vistas` | corte por morte, uma vez por identidade |
| `alvos_inalcancaveis` | abandono pela régua do penhasco |
| `tabs_dados` | cada tecla de alvo enviada |

`voltas` alimenta a limpeza de bolsa (`voltas % a_cada`) e o shuffle anti-AFK.
Contar aborto contaminava os dois: num ponto de farm com muita morte eles
disparavam cedo demais.

### O shuffle anti-AFK

Não sai em combate nem com alvo vivo (sair andando com mob em cima é parte do
*"chamou vários mobs e morreu"*), e suas duas esperas deixaram de ser
`time.sleep(1.0)` cego — passam por `_esperar`, que responde ao Parar e confere
a morte do alvo lá dentro.

### `is_sitting()` virou tri-estado — o conserto foi na FONTE

`Memory.is_sitting()` devolvia `bool` puro: falha de leitura virava `False`, ou
seja "está de pé". O contrato tri-estado estava documentado com todo cuidado no
CONSUMIDOR (`bot/app/cura.py`), e a fonte nunca o cumpriu.

**Medido:** 4 avisos de "acabaram as poções" na MESMA sessão de 25/08 em que
houve 3 curas bem-sucedidas com 2 poções cada.

Consequências consertadas:

* `_a_pocao_saiu()` volta a poder responder "não sei", que segue bebendo;
* **da segunda poção em diante a prova não vale** — ele já está sentado pela
  primeira, então "está sentado" não prova que a tecla saiu. O estado é lido
  ANTES de apertar e a prova só é aceita quando ele estava de pé;
* com a leitura ilegível (`None`) a cura **senta assim mesmo, uma vez só**. Não
  há `_levantar()`: o bot só senta, porque sentar não é trava e sim bônus de
  regeneração. Ver `docs/decisoes/cura-no-app.md`, seção "O bot SÓ SENTA".

Os quatro consumidores do BC não mudam de comportamento — todos usam a leitura
em contexto booleano, e `None` é falso exatamente como `False` era.

## Reuso e promoção — a diretiva permanente (26/08/2026)

Duas diretivas do usuário no mesmo dia, e elas são a mesma regra em dois tempos:
**não duplicar** (reuso) e **não deixar apodrecer** (promoção).

> *"A duplicação de funções é inaceitável. (...) Se você identificar que uma
> função restrita a um ecossistema possui utilidade geral, é sua OBRIGAÇÃO
> refatorá-la, abstrair suas dependências locais e promovê-la para o Core
> Global. (...) Ao trabalhar com fluxos do TARGET, aplique esta regra com rigor
> máximo."*

O resumo está no `CLAUDE.md`, seção "REUSO E PROMOÇÃO". Aqui fica a primeira
aplicação dela, que serve de modelo.

### O que estava duplicado: o veredito de morte do alvo

Medido em 26/08/2026, a partir de uma pergunta do usuário: *"sobre o HP do
target, está sendo analisado como fazemos no Gun Witch?"*.

Não estava — e havia **duas duplicatas empilhadas**:

| duplicata | BC | APP (antes) |
|---|---|---|
| leitura do alvo | `TargetHybrid.entidade_do_alvo` | `_ler(memoria_do_pet.alvo_atual)`, com o portão `critical_ok()` |
| veredito `hp <= 0` | `CombatEngine._alvo_morreu_pela_memoria` | `ExecutorDeMacro._alvo_morreu` |
| trava por identidade | `_ultimo_alvo_morto_id` | `_ultimo_alvo_morto_id` |

O nome do atributo era o **mesmo nos dois**, e o comentário explicando que a
trava é por identidade e não por tempo estava escrito **duas vezes**, com as
mesmas palavras. Duas cópias da mesma decisão são duas chances de só uma ser
corrigida — que é exatamente o que a diretiva proíbe.

### O que subiu para o `core/`, e o que NÃO subiu

`core/target_hybrid.MorteDoAlvo`, usada por `bot/bc/combat.py` e
`bot/app/executor.py`:

* `veredito(entidade)` — `True` morreu, `False` vivo, `None` não sei. `hp == 0`
  é morte na primeira leitura, porque `Memory.alvo_atual()` já validou a struct;
* `contar(ident)` — a trava por IDENTIDADE. `False` = esta morte já saiu;
* `esquecer()` — o reset por luta.

**Não subiu, e o porquê importa tanto quanto o que subiu:**

| ficou onde | o quê | por quê |
|---|---|---|
| BC | reserva pela TELA (`EnemyDead.png`, a barra, `SO_A_MEMORIA_DECLARA_MORTE`) | o modo APP não captura tela |
| APP | reserva pela FLAG DE COMBATE, escape de "alvo ilegível", urgência | o BC resolve o mesmo caso por outro caminho |

**O critério é o mesmo de sempre:** *isso é sobre o JOGO ou sobre o que este
ecossistema faz?*. "O mob morreu" é sobre o jogo. "O que fazer quando ele
morre" é de cada um.

### Como a promoção foi feita sem quebrar o BC

O `CombatEngine` é código de produção do farm, e o gatilho de segurança da
diretiva vale principalmente para ele. Duas decisões que mantiveram o risco
baixo:

* **o nome antigo continua existindo.** `_ultimo_alvo_morto_id` virou
  **propriedade** que lê e escreve na peça compartilhada. O caminho da tela, o
  reset por luta e os testes já falavam essa língua, e trocar o nome deles seria
  mexer em código estável para nenhum ganho;
* **a peça é criada preguiçosamente.** Vários testes do BC constroem o
  `CombatEngine` sem passar pelo `__init__` (via `__new__`), e é assim que eles
  exercitam uma regra sem montar um jogo inteiro. Exigir a construção completa
  só porque uma peça mudou de casa seria cobrar dos testes o preço de um
  conserto que não é deles.

A primeira tentativa **quebrou 28 testes do BC** exatamente por causa desse
segundo ponto — e essa é a evidência de que o gatilho de segurança da diretiva
("valide o efeito colateral rodando a suíte inteira") não é formalidade.

### Rastreabilidade

Travado por `tests/test_ecossistemas.py`, que confere que:

* os dois ecossistemas importam e usam a MESMA peça;
* nenhum dos dois reimplementa a trava;
* a documentação da dependência cruzada existe no `core/` **e nas duas pontas**,
  dizendo quem usa, o que não subiu e por quê;
* a peça promovida **não importa nada de `blazesbot.bot`** — senão ela não é
  core, é acoplamento com outro nome.

### Candidatos de promoção já identificados

Ainda em duplicata, registrados aqui para não se perderem:

* **confirmar o TAB pela troca do id** — `app/executor._esperar_o_alvo_trocar`
  contra o TAB do `bc/combat`. As duas pontas apertam a tecla de alvo e esperam
  o id mudar, com tetos e cadências diferentes;
* **a espera fatiada que responde ao Parar** — `app/executor._dormir` contra
  `BotContext.tick`. A mesma pergunta ("espere, mas atenda o botão de parar")
  resolvida duas vezes.


## A segunda porta: a vida do alvo pela TELA (26/08/2026)

### Por que ela existe

A medição do item 41 de `docs/decisoes/alvo-o-que-esta-medido.md` provou que
mobs **vivos e inteiros** (`Rose Snake nv61 100/100`) existem na memória em
`0x3670xxxx` e **não são alcançáveis** pela janela que `_procurar_entidade`
varre. Recusar alvo porque "a entidade não apareceu" estava jogando fora mob
bom, ao alcance.

Enquanto o array de verdade não for achado, a barra desenhada é a única fonte
que responde por esses mobs.

### A cascata

| ordem | fonte | custo | quando |
|---|---|---|---|
| 1 | `Memory.alvo_atual()["pct"]` | ~1 µs | sempre que responde |
| 2 | `TargetHybrid.vida_pela_tela(hwnd)` | **uma captura** | só quando a 1 falhou |
| 3 | "não sei" | — | e continua não sendo veredito |

A régua do inalcançável usa a **mesma cascata** — decisão do usuário: *"se não
ler o HP pela memória, lê pela tela; se não alterar nada a vida, o mob está
inacessível, pode dar um novo TAB"*. A barra responde bem a **direção**, que é o
que essa régua pergunta; o que ela erra é o valor exato e o atraso.

> Por causa disso, a referência da régua passou a ser guardada em **fração
> (0..1)** e não em pontos de vida — a barra só sabe responder em fração, e
> misturar as duas unidades faria a régua achar que o mob curou de `1,0` para
> `100`.

### A cadência, e por que ela é um portão

`LINHAS_ANTES_DE_OLHAR_A_TELA = 2` e `INTERVALO_MINIMO_DA_TELA = 0.5`, e as duas
condições valem **juntas**:

* antes da **terceira linha** da rotação a tela nem é tentada — logo depois do
  TAB a entidade pode simplesmente ainda não ter entrado no array (medido: 1
  leitura em ~45), e pagar captura para descobrir isso é caro;
* nunca **duas vezes na mesma linha**, e nunca com menos de **meio segundo**
  entre uma e outra. É o *"a cada 500 ms ou a cada linha, o que for MAIOR"* do
  usuário: linha longa manda a linha, linha curta manda o meio segundo.

**O número importa.** A conferência do alvo roda a cada
`PASSO_DA_CONFERENCIA_DO_ALVO` (0,1 s) dentro da espera de cada linha. Se a tela
entrasse ali seriam **10 capturas por segundo por conta** — com 5 clientes, 50
por segundo. A cadência visual do BC (`VISUAL_CHECK_SECONDS`) é de 10 s.

### O pedágio: 3 linhas batendo CEGO

Isto **inverte, só no APP**, a regra `SO_A_MEMORIA_DECLARA_MORTE` do BC. Lá a
tela nunca declara morte, por causa do falso positivo medido do `EnemyDead.png`
(0,955–0,971 com o mob VIVO). Aqui ela pode — e o preço é
`LINHAS_BATENDO_CEGO_DEPOIS_DA_TELA = 3`.

> *"Continua batendo, sem perguntar mais, só apenas bater cego até as 3
> próximas linhas. É apenas uma garantia extra."*

**Bate cego mesmo:** o `_cortar_a_volta` fica de fora dessas linhas de
propósito, e a espera usa `_esperar_cego`, que não confere alvo nenhum.
Perguntar de novo é exatamente o que "bater cego" não faz.

É seguro porque a assimetria de custo é conhecida: **bater num cadáver custa
tempo; trocar de alvo com o mob VIVO custa o personagem** — foi o defeito de
25/08/2026.

Três exceções encerram o pedágio antes:

| o quê | por quê |
|---|---|
| a memória volta com `hp > 0` | um ponto de vida derruba toda suspeita |
| **sair de batalha** | regra geral: *"se saiu de batalha, é garantido que matou e não tem outro mob batendo"* |
| a macro acabar | *"caso tenha cadastrado"* — o pedágio é o que sobrar |

### O mestre continua sendo sair de batalha

Nada disso mexe em quem manda nas **verificações, na poção e na volta ao
ponto**: quem manda é a saída de batalha. O que a segunda porta faz é dar ao bot
uma resposta sobre o alvo quando a memória não tem — não mudar de quem é a
palavra final sobre o ciclo.

E o teto da observação depois da morte voltou para **3 s** (tinha ido a 2):
*"se não sair de batalha em até 3 segundos, pode dar TAB, que provavelmente vai
ter um segundo mob batendo — então ele não irá sair de batalha de forma
alguma"*.

---

## Reset de time: a lista fechada e a trava na porta (26/08/2026)

> A **especificação**. O porquê medido está em `docs/decisoes/reset-de-time.md`;
> o backoff e a senha errada, em `docs/decisoes/login-e-relogin.md`.

### Quem pode ser reseter

`BotConfig.reset_accounts()` — contas **ativas** (`enabled`) marcadas com
`accept_team_invites`. É a lista que as duas interfaces oferecem, e **não existe
mais texto livre**: um reseter fora deste processo é invisível daqui, e sem
observá-lo não há batida, sem batida não há trava.

A conta marcada que **nunca logou** aparece na lista **desabilitada** — sem nick
lido da memória, selecioná-la gravaria `""`, que significa *não usar reset de
time*. O nick já gravado que não é candidato aparece no fim, com aviso, e
continua **selecionado**.

### O veredito por conta — `BotConfig.problema_do_reset(conta)`

Devolve `None` (ok) ou a frase do problema. Reprova, nesta ordem:

| condição | mensagem trata de |
|---|---|
| `reset_nick` vazio | — (`None`: não usa reset) |
| sem `keys.friend_list` | a tecla da lista de amigos |
| nick não é conta deste bot | reseter não cadastrado |
| nick é a própria conta | ninguém reseta a si mesmo |
| reseter desativado | `enabled = False` |
| reseter sem a flag | `accept_team_invites` |
| reseter com `bc_farm` | farmando, ele não está na porta |
| reseter em modo APP | `_operate` nunca chega no aceitador |

**NÃO está em `validate()`, e isso é decisão.** `validate()` é tudo-ou-nada: uma
conta errada derrubaria a execução inteira. O desfecho aqui é **veto por conta** —
ela loga, fica online, com relogin, e só o **BC dela** não roda. A regra da tecla
da lista de amigos **veio junto**, saindo do `AccountSettings.validate()`:
mudança de **alcance**, não de rigor.

### A migração

`BotConfig._migrar_reset_de_time`, no fim do `from_dict`, com todas as contas já
construídas. Liga `accept_team_invites` na conta que o `reset_nick` já apontava —
**só se ela estiver limpa** (sem `bc_farm`, sem `app.enabled`). Conta suja ou nick
que não bate com ninguém: **não toca em nada**, e o caso cai no veto por conta.

### A batida — `bot/mural.py`

- `bater(nick)` é a **primeira linha de `InviteAcceptor.check_and_accept`**,
  **antes do cooldown**. A posição é a regra: ela prova a capacidade em vez de
  descrevê-la, então modo APP, login, relogin e farm caem fora sozinhos.
- `SILENCIO_MAXIMO = 5.0` — **derivado**, não medido: dez voltas do `tick(0.5)`
  da conta de reset. Muda junto com aquele `0.5`.
- `reseter_online(nick)` — **nunca ter batido conta como offline**.
- `silencio_do_reseter(nick)` — `None` = nunca bateu nesta execução; existe para
  a linha de log dizer *quanto* tempo.

### O portão — `BossRushRoutine._esperar_o_reseter()`

**Um lugar só**, imediatamente antes de `self.team.montar_time()`. A run em curso
termina inteira — boss, venda, viagem de volta — e o personagem estaciona no
ponto de entrada já conquistado.

- Espera em **`ctx.tick(PASSO_DA_ESPERA_DO_RESETER = 1.0)`**, nunca `time.sleep`:
  é o `tick` que mantém o **watchdog desta conta** vivo durante a trava, e é ele
  que dá as três saídas prontas (Parar, desmarcar o BC farm ⇒ `FarmDesligado`,
  ligar o modo APP).
- **Sem teto de espera.** `reset_nick` preenchido é a declaração de que sem reset
  a run não presta. Sem interruptor novo.
- Aviso ao entrar, **repetido a cada `INTERVALO_DO_AVISO_DO_RESETER = 300.0`**
  (cosmético, sem medição) e ao sair, com a **duração** via `frase_do_tempo` de
  `core/quedas.py` (reuso, não função nova).
- **`problema_do_reset` é reavaliado a cada volta** — a configuração muda com o
  bot rodando. Respondeu algo ⇒ `bc_farm = False` + `config.save()` + log de erro,
  o mesmo desfecho da venda sem tecla de retorno.

### Tirar um reseter do ar é IMPEDIDO

Três portas, mesmo estrago, todas bloqueadas nas **duas** interfaces: deletar,
desativar, e **desmarcar "aceitar convites de time"**. Quem responde é
`BotConfig.accounts_reset_by(reseter)` — **só contas ativas** contam como
dependentes.

- PyQt: `MainWindow._bloqueado_por_ser_reseter` (remoção e `COL_ATIVA`, que
  **volta a marcar** a caixa) e `AccountDialog._reseter_seria_desmarcado`.
- Web: `_App.bloqueio_de_reseter`, consultado **no backend** por
  `remover_conta`, `ativar_conta` e `salvar_personagem` — um erro no frontend não
  pode furar. O aviso é **modal (`avisar`), nunca toast**: toast some em 2,6 s.

### Estatística

O tempo travado **já fica fora das médias de graça**: o cronômetro da run só
começa no fim do preparo de entrada, que é **depois** do portão. O que existe é a
linha de log da duração ao liberar.

### Travado por

`tests/test_reset_de_time.py` — a batida, a posição dela por AST, o veredito caso
a caso, a migração, o portão antes do `montar_time()`, a espera por `ctx.tick`, e
a lista fechada nas duas interfaces.

---

## Login e relogin: o backoff e a senha errada (26/08/2026)

> Porquê medido em `docs/decisoes/login-e-relogin.md`.

- **O contador de tentativas é `AccountSupervisor.tentativas_de_login`** e zera
  **no login CONCLUÍDO** (`_run_session`, nos dois caminhos). Era local de `run()`
  e zerava num `else:` de `try/except` **inalcançável** — o corpo termina em
  `return`. Consequência: a partir da nona queda, **300 s antes de cada relogin,
  para sempre**.
- **`MAX_CREDENTIAL_ERRORS = 5`**, e são cinco **no total** — o contador nasce
  zerado a cada `LoginSequence` e o `BadCredentials` encerra na primeira vez que
  estoura. **Só a tela `state_login_error.png` conta**; demora, fila e tela
  travada têm caminhos próprios.
- **Senha errada DESATIVA a conta e grava** (`enabled = False` + `config.save()`).
  A conta desmarcada na interface **é** o aviso; `sync_accounts()` alinha os
  supervisores com `enabled_accounts()`, então ela não volta sozinha.
- Um reseter aposentado assim faz o BC dependente cair no ramo *"não existe
  mais"* do portão da cave.
- **Nada disso mexe** no `LOGIN_SCREEN_MAX_SECONDS = 150.0` nem no laço infinito
  de sessão: os dois já faziam o que o usuário pediu.

Travado por `tests/test_backoff_do_login.py`, que reprova o **padrão** —
nenhum `try/except/else` cujo corpo termine em `return` pode voltar.

---

## Janela na frente do clique (26-27/08/2026)

> A **especificação**. O porquê medido e os números estão em
> `docs/decisoes/janela-na-frente.md`.

### O guarda -- `core/janelas_abertas.py`

Recebe **PEÇAS**, não `BotContext` (mesma decisão de `watchdog.avaliar_saude`) --
é o que permite o APP usar sem depender do farm e mantém `core/` sem importar de
`bot/`.

**DOIS sinais, respondendo perguntas diferentes:**

| sinal | pergunta | limiar | template |
|---|---|---|---|
| **X de fechar** (18x18) | *onde clico para fechar?* | `LIMIAR_DO_X = 0.80` | `janela_fechar.png` |
| **moldura** (100x16) | *tem janela na tela?* | `LIMIAR_DA_MOLDURA = 0.65` | `janela_moldura.png` |

- **EM COR, nunca em cinza** — `find_all_templates(colorido=True)` com
  `load_color`. Os limiares foram medidos em cor; `find_template` converte para
  luminância e aplicaria o número a outro espaço. Travado por AST.
- **A moldura NÃO conta janelas** (o filigrama se repete: 2 a 7 casamentos para
  UMA janela). O X conta 1 sempre — a menos, nunca a mais. Por isso o laço
  **nunca conta**: pergunta *"ainda tem janela?"* e fecha **uma por passada**,
  reconferindo. `MAXIMO_DE_JANELAS = 4` é teto contra laço infinito.
- **Leitura TRI-ESTADO** (`True` / `False` / `None` = não sei). Quadro em cinza
  ou sem template é `None`, nunca `False`.
- **"NÃO SEI" NÃO BLOQUEIA**, e janela **sem X** não é fechada às cegas — fechar
  às cegas é clicar num interruptor sem ver o estado, e o botão fica **sobre a
  cena 3D**.

### Onde o guarda roda

**POR EVENTO, não por clique.** Hoje: `preparar_entrada()`, uma vez, antes da
rajada de tentativas de entrada (que dispara 2 cliques/s na cena 3D).

**NÃO roda antes do clique direito da Block list** (`team._enviar_convite`) — ele
precisa da lista **aberta**, e o guarda a fecharia. O caso está coberto pela
ordem em `_do_entrar`: `montar_time()` -> `preparar_entrada()` -> rajada.
Travado por teste.

**Guarda de "cena limpa" só vale antes de clique na CENA.** Clique dentro de
janela tem outra pergunta, e `_pontos(...)` já a responde.

### O painel de arredores

- **O DONO É O TRAJETO** (`trajeto_pelo_painel`), não a abertura: `buscar_npc`
  termina com o painel **aberto de propósito**, porque quem chamou ainda vai
  clicar no `first_result`. Fecha em **qualquer** saída, inclusive por exceção.
  Usado por `_viajar_para_ghost_din_woods` e `ir_ate_o_npc_da_cave`.
- **`fechar_surroundings` devolve TRI-ESTADO** e relê até
  `LEITURAS_ANTES_DE_DESISTIR_DE_VER = 3` antes de aceitar cegueira. Antes ela
  tratava *"não consigo ver"* como *"não está aberto"* e voltava em silêncio.
- **`ABERTURAS_POR_TRAJETO = 4`**, num contador só, zerado por
  `comecar_trajeto()`. Estourado, `abrir_surroundings` devolve `None` e os laços
  de retentativa param sozinhos. Antes eram **3 x 3 = 9**, produto acidental de
  duas camadas. Número **derivado**: 1 normal + 3 modos de falha documentados.
- **A cadência é carimbada em TRÊS pontos** e vale o mais recente: abrir,
  auto-path e fechar (`_marcar_uso_do_painel`). Carimbada só na abertura, ela
  media *abrir -> abrir* e quase nunca mordia. `INTERVALO_ENTRE_USOS_DO_PAINEL =
  2.0` continua **cosmético**, sem medição atrás.
- **ORDEM: montaria -> Surroundings.** O `garantir_montaria_para_andar` de
  `ir_para_resultado` foi **APAGADO**: ele rodava com o campo de busca FOCADO e o
  portão **insiste sem teto**, então a tecla da montaria era digitada dentro da
  busca (`Skull00000000...`). Era redundante — `abrir_surroundings` já exige
  montaria antes de abrir. Travado por AST nos dois sentidos.

### Regra que generaliza

**Nenhuma tecla pode sair enquanto um campo de texto tem o foco.** O bot não tem
noção de foco, então a proteção é de **ORDEM**: tudo que aperta tecla acontece
**antes** de abrir a janela que tem campo.

### Travado por

`tests/test_janela_na_frente.py` — a leitura tri-estado, o casamento colorido por
AST, o laço que fecha uma por passada, o teto, o `fechar_surroundings` que sabe
dizer que não fechou, o dono do painel, o orçamento, a ordem da montaria, o
guarda antes da rajada, e a auto-sabotagem que ele não comete.
