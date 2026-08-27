# Cliques, entrada da cave e resolução — decisões e medições

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.

- **EXPERIMENTO — o clique DIREITO sai em rajada de 4**
  (`inputs.CLIQUES_DIREITOS_POR_TENTATIVA = 4`, pedido do usuário). Vale para
  TODO clique direito do bot: NPC, Altar Stone, saída da cave e movimento pelo
  mapa. Voltar ao de sempre é pôr `1` — mesmo molde do `MODO_DE_CLIQUE`.
  - **A aposta:** medido, o MESMO clique na MESMA coordenada abre o diálogo
    **78% das vezes** fora do instante ruim. Um em cada cinco se perde sem nada
    estar errado com a coordenada; repetir rápido aposta que parte desses 22% é
    o cliente engolindo a mensagem.
  - **Custo medido: 27,8 ms → 156,4 ms por clique direito** (cada um é
    `SendMessageW` SÍNCRONO, então são quatro idas e voltas). Perto dos 368 ms
    de mediana da abertura do diálogo, cabe.
  - **NÃO se aplica ao clique ESQUERDO**, e a assimetria é deliberada: o
    esquerdo tem efeito POR CLIQUE. Quatro cliques num item da grade de venda
    gastariam quatro da contagem configurada pelo usuário; quatro no link de um
    NPC repetiriam o pedido. Travado por teste.
  - **NÃO se aplica ao MOVIMENTO PELO MINIMAPA** (`ctx.right_click(ponto,
    repetir=False)`, nos dois pontos do `navigation.py`). Ali cada clique é uma
    ORDEM DE ANDAR: o pixel foi calculado a partir da posição ATUAL, e entre um
    clique e o seguinte o personagem já saiu do lugar — o 2º, 3º e 4º apontam
    para um destino deslocado. O usuário sentiu isso como "perda de precisão de
    andar pelo mapa". A regra que separa os dois casos: **repetir vale para
    clique que ABRE alguma coisa (o efeito não se acumula), não para clique que
    MOVE.** Travado por teste, inclusive por leitura do fonte — um
    `ctx.right_click(ponto)` novo no laço de movimento reprova.
  - O clique do **mapa-múndi** (`_mover_pelo_mapa`) continua repetindo: ele é
    deliberado, espaçado por `tick(2.0)` e verificado por leitura de posição a
    cada desvio. Se aparecer imprecisão ali também, é a mesma correção.
  - **O RISCO A VIGIAR é clique que ALTERNA estado.** Um menu que abre no
    primeiro clique e fecha no segundo termina FECHADO com número par. O caso
    concreto é `team.py`, que clica no próprio retrato para abrir o menu de sair
    do time — e é esse menu que reseta o boss. Se o reset parar de funcionar, é
    o primeiro lugar a olhar.
- **MEDIDO — o clique direito NÃO era o gargalo da entrada; o teto fixo era.**
  Run de validação de 13/08/2026 (`logs/dev/blazes-dev.jsonl`, fase ENTRAR, 26
  min): **292 aberturas reais**, min 210 / mediana 368 / max 588 ms. **189 delas
  (65%) estavam acima do teto fixo antigo de 350 ms** e eram jogadas fora por
  impaciência — na tela isso parecia exatamente "ele tenta clicar e não abre".
  O teto adaptativo resolveu essa metade, e **nada em `inputs.py` precisou
  mudar** (`MODO_DE_CLIQUE` segue em `"sendmessage"`).
- **A falha ANDOU DE LUGAR: agora é o clique no LINK, e está medida.** Na mesma
  run, ZERO entradas em 26 minutos. O diálogo abre, o link é clicado, o
  personagem não entra. E a taxa de abertura do clique direito separa os dois
  momentos de forma que não é ruído:
  ```
  clique direito LOGO APÓS um clique no link :  41/291 = 14%
  clique direito em qualquer outro momento   : 251/320 = 78%
  ```
  Cinco vezes e meia. Não é recarga do NPC — fora daquele instante o MESMO
  clique, na MESMA coordenada, abre 78% das vezes. Algo fica na tela depois do
  clique no link e engole o clique seguinte por cerca de um segundo.
  - **O candidato concreto:** `coords.cave_enter_confirm` = **(258,364)**,
    medido em 1024x768 (a resolução do cliente da run, então vale literal) e
    **nunca lido por código nenhum** — grep completo acha só a definição. O link
    que a descoberta por imagem encontra fica em **(302,365)**: mesma linha, 44
    px ao lado. Ou existe um passo de confirmação que alguém mediu e nunca ligou
    no fluxo, ou aquilo é medição velha do próprio link. **As duas levam a
    lugares opostos e nenhuma está provada** — não amarrar o clique em (258,364)
    sem a foto (ver abaixo): se não houver caixa, esse clique cai na cena 3D e o
    personagem anda, que é justamente o que o bot evita hoje.
  - Outro suspeito a conferir na mesma foto: o personagem está **montado**
    durante toda a tentativa (`falar_com_npc` chama `garantir_montaria_para_andar`).
- **RESOLUÇÃO: existe UM modelo, e ele mora no `coords.py`** — âncora +
  deslocamento FIXO em pixels. A descoberta que abre aquele arquivo é que a UI
  do jogo **não escala**: mais resolução dá mais cenário, não elementos maiores.
  Todo ponto novo tem que entrar por `_from_base(x, y, âncora)`, nunca por conta
  feita à mão em quem usa. 1024x768 é a base MEDIDA, não a única suportada.
  - **`coords.npc_padrao` = `_from_base(482, 353, C)`** nasceu de uma violação
    dessa regra: `ui_service._ponto_padrao_do_npc` calculava
    `(largura//2 - 30, int(altura*0.46))` — **X ancorado (certo) e Y
    proporcional (errado), os dois modelos no mesmo cálculo**. A 1024x768 os
    dois dão o MESMO número (`int(768*0.46) = 353 = 384-31`), então a troca é
    não-regressão provada na resolução validada; fora dela a proporção erra, e o
    erro cresce com a tela: **13 px a 1920x1080**, 10 px a 1280x1024, 7 px para
    o outro lado a 800x600. Num NPC de algumas dezenas de pixels isso come a
    margem — e come na entrada da cave, que ainda aplica `alturaDif=-48` por
    cima. Travado por teste (`test_coords.py`), inclusive o número da divergência.
  - **O deslocamento vencedor da amostragem é PORTÁVEL entre resoluções** pelo
    mesmo motivo (elemento de tamanho fixo, deslocamento de tamanho fixo), e por
    isso o raio/passo do grid são em pixels. Mas a resolução da medição vai
    gravada no arquivo e no resumo: se um dia duas amostragens se contradisserem,
    é esse campo que denuncia a causa.
- **Cliques de mouse são SÍNCRONOS via SendMessageW (nunca movem o cursor
  físico).** `_prime_cursor` manda `WM_SETCURSOR` + `WM_MOUSEMOVE`, ambos via
  `SendMessageW` com a coordenada no `lParam`; depois o `_click` manda
  `WM_LBUTTONDOWN/UP` (ou `WM_RBUTTONDOWN/UP`) também via `SendMessageW`, com um
  `sleep(jitter(...))` curto (0.03s) entre DOWN e UP. Coordenadas no espaço
  client. É o comportamento ORIGINAL do bot (BlazesBot18-22), que funcionava —
  voltamos a ele.

  **INTERRUPTOR `MODO_DE_CLIQUE`** (topo do `inputs.py`), pedido do usuário para
  experimentar sem arriscar o que funciona: `"sendmessage"` é o de sempre e o
  padrão; `"sendmessage_repetido"` reafirma o `WM_MOUSEMOVE` colado ao botão.
  A hipótese do experimento vem de uma observação medida pelo usuário: **com o
  cursor FÍSICO sobre a janela, o clique acontece ONDE O CURSOR ESTÁ**, não na
  coordenada enviada — ou seja, o cliente lê a posição de outro lugar que não o
  `lParam` do botão. Pesquisa de agosto/2026 confirma que jogos que leem
  `GetCursorPos` **exigem detour dessa função**, ou seja DLL — descartado pelo
  usuário. **Não existe biblioteca Python que resolva**: é arquitetura Win32.
  E todas as dependências já estão em versão atual (opencv 5.0.0.93, numpy
  2.5.1, pymem 1.14.0, PyQt6 6.11.0, pywebview 6.2.1, pywin32 312) — não há
  ganho em atualizar.

    **NOTA HISTÓRICA — o "segundo mouse virtual" (inline hook) e o PostMessage
  foram DESLIGADOS.**
  Depois do SendMessageW original, chegamos a implementar e testar duas
  alternativas que não funcionaram bem em produção:
  (1) **PostMessage puro com coordenada no `lParam`** — o jogo resolve PARTE
  dos cliques por `GetMessagePos` (que o PostMessage preenche), mas em outros
  (como o Altar Stone, `altar_npc`) o clique caía onde o cursor FÍSICO estava,
  não abrindo o diálogo;
  (2) um DLL de 32 bits (`blazesbot/native/cursor_hook.c` → `cursor_hook.dll`)
  que fazia **Inline Hook direto nas FUNÇÕES `user32!GetCursorPos` e
  `user32!SetCursorPos`** no processo do jogo (GetCursorPos devolve posição
  VIRTUAL enquanto o bot clica; SetCursorPos é engolido), injetado por um EXE
  de 32 bits (`injector.exe`, porque o bot é 64-bit e o `pymem.inject_dll`
  resolve LoadLibrary no host — endereço inválido no processo 32-bit via
  WOW64), comunicando via mapeamento compartilhado por PID
  (`Local\BlazesBotHook_<pid>`, struct `{active,x,y,status}`). Os prologues
  reais do user32 (dump `injector.exe --prologue`, Win11): `GetCursorPos` =
  `8B FF 55 8B EC` (5 B) e `SetCursorPos` = `FF 25 C4 BD 54 76` (6 B); o
  `install_inline` reconhecia os dois + a variante clássica `64 A1 2C 00 00 00`.
  **Mesmo com os hooks instalados (status SIM/SIM, injeção ok), o resultado em
  produção continuou problemático.** O usuário então confirmou que o ORIGINAL,
  `SendMessageW` síncrono, era o que funcionava — e é o caminho de clique atual
  em `inputs.py` (acima).
  **O código da DLL foi REMOVIDO do repositório** em 2026-08-16 após o
  abandono. A implementação (`cursor_hook.py`, `cursor_hook.c`, `injector.*`,
  `compilar.bat`, scripts de teste `.bat`) foi apagada — consulte
  `docs/decisoes/dll-cursor-hook.md` para o registro completo da decisão.
