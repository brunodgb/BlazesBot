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

## A rajada de clique direito passou a PERGUNTAR — 11/09/2026

### O piso medido

Telemetria de 09 e 10/09/2026 (`logs/latencia/latencia.jsonl`, 81,6 milhões de
chamadas cronometradas):

| o que | n | média | mínimo |
|---|---|---|---|
| `Input._click_postmessage_puro` (o clique em si) | 957.315 | 2,68 ms | 2,04 ms |
| `Input.right_click` (a rajada inteira) | 116.666 | 295,93 ms | 2,08 ms |
| `UIDoJogo._abrir_dialogo_e_clicar` | 64.076 | 491,26 ms | **424,32 ms** |
| `UIDoJogo.dialogo_esta_aberto` (a pergunta) | 224.353 | 27,61 ms | 0,02 ms |

**O mínimo de 424 ms é a assinatura do desperdício:** nenhuma conversa com NPC
no bot inteiro custou menos que a rajada cega, porque a rajada cega ERA o piso.
Dez cliques a 44 ms de espaçamento são 396 ms pagos sempre, inclusive quando o
primeiro já abriu o diálogo.

### A conta que decidiu

Perguntar custa **27,61 ms** e responde. Esperar um espaçamento custa **44 ms** e
não responde. Então perguntar entre os cliques é mais barato que o silêncio
entre eles — e é a regra da casa (*"onde havia espera cega, agora se PERGUNTA"*)
aplicada ao maior custo fixo do caminho quente.

| cenário | antes | agora |
|---|---|---|
| abre no 1º clique (caso comum) | 424 ms | ~30 ms |
| abre no 3º clique | 424 ms | ~150 ms |
| nunca abre (3,9% das rajadas) | ~420 ms + teto | ~743 ms + teto |

O pior caso ficou mais caro, e é aceito: ele acontece em 2.473 de 64.076
rajadas, e o tempo a mais é gasto PERGUNTANDO — que é o que pega o diálogo
atrasado, em vez de dormir até o fim e perguntar uma vez só.

### `CLIQUES_DIREITOS_POR_TENTATIVA` virou TETO

Com a rajada cega, subir o número custava 44 ms por clique em TODA conversa do
bot. Com a pergunta no meio, quem abre no primeiro clique não paga os outros
nove. O 10 continua lá, e agora é de graça.

### O que NÃO mudou

* **Sem captura, a rajada sai inteira e cega.** Cliente minimizado é modo normal
  de operação deste bot: ali `capture_window` devolve quadro preto e nenhum
  template casa. Recusar a rajada nesse caso deixaria a entrada na cave
  impossível, então a aposta original continua valendo onde não há o que
  perguntar.
* **O clique continua sendo um só por vez** (`repetir=False`): a repetição
  passou a ser do laço, e quem a controla é a resposta, não o relógio.
* **`_esperar_o_dialogo` continua atrás**, com o teto adaptativo: o diálogo pode
  chegar depois do último clique, e é ele quem conta as falhas seguidas.

### Travado por

`tests/test_rajada_de_npc.py` — para no clique que abriu, espaçamento só entre
cliques, teto de cliques respeitado, rajada inteira quando não há imagem, e a
integração em `_clicar_no_npc_e_no_link` (que não pode voltar a clicar cego).
O interruptor `PERGUNTAR_ENTRE_OS_CLIQUES = False` devolve o comportamento
antigo inteiro.


## O menu do convite muda de tamanho com a distância — 16/09/2026

### O sintoma

O APP não montava o time. O convite sai pelo menu de contexto da entrada na
Block list (`TeamService._enviar_convite`), e o clique em "Team up" é um
deslocamento medido a partir do clique direito: `(32, 75)`.

### A medição

O usuário mandou o print do menu aberto com o convidado PERTO. O cliente
acrescenta as opções que só existem com o personagem à vista, e o menu passa de
7 para 12 itens:

|        | LONGE, 7 itens | PERTO, 12 itens |
|--------|----------------|-----------------|
| +13    | [nick]         | [nick]          |
| +33    | Copy Name      | Follow          |
| +54    | ---------      | Copy Name       |
| **+75**| **Team up**    | View Equipment  |
| +96    | Whisper        | ---------       |
| +117   | Add Foe        | Trade           |
| **+138**| Recruit Apprentice | **Team up** |
| +159…  | —              | Duel, Whisper, Add Foe, Apply to Master, Recruit Apprentice |

O passo é de ~21 px nos dois. No menu longo, o deslocamento de `+75` cai em
**"View Equipment"**: abre a janela de equipamento e convite nenhum sai.

Isso não é caso de borda do APP — é o caso NORMAL dele: *"normalmente o APP é o
que vai estar perto"*. O BC nunca viu o problema porque lá o convidado é a conta
de reset, parada do outro lado do mapa.

### Por que medir a altura, e não escolher por ecossistema

"O APP usa o longo, o BC usa o curto" seria uma regra sobre o ecossistema,
quando o que manda é a DISTÂNCIA — o seguidor do APP pode estar longe (morto,
em outro mapa) e o convite sairia errado do mesmo jeito.

Não há recorte do menu em disco (`menu_team_up.png` é carregado e não existe),
mas uma caixa opaca sobre a cena 3D muda toda linha que cobre. `altura_da_mudanca`
conta as linhas SEGUIDAS que mudaram entre o quadro de antes do clique direito e
o de depois: ~150 px no menu curto, ~250 px no longo, limiar em 200.

Captura não é dependência nova aqui: `_enviar_convite` já **precisa** de captura
para achar a Block list por template (`_pontos("block_list")`). Se ela falhar, a
função já devolvia `False` antes de chegar no menu. O quadro de antes é o MESMO
que localiza a lista — nenhuma captura a mais.

### Errar para o curto é o lado barato

A assimetria decide os empates, e é por isso que todo "não sei" fica no curto:

* deslocamento curto no menu longo → **"View Equipment"**, uma janela que o
  `_fechar_janelas` seguinte fecha;
* deslocamento longo no menu curto → **"Recruit Apprentice"**, um pedido de
  aprendiz para a outra conta — que é justamente a conta com um aceitador de
  caixa rodando.

Daí as três recusas: sem quadro, recorte fora da tela, e régua que bateu no fim
sem nunca parar (a tela inteira mudando é a cena, não um menu).

### Travado por

`tests/test_menu_do_convite.py` — os dois menus medidos caem de lados opostos do
limiar, a régua para na primeira linha igual (mob passando mais abaixo não
estica a caixa), e o quadro de ANTES é capturado antes do clique direito. Esse
último é auto-sabotagem: capturar depois compararia o menu com ele mesmo, a
régua daria zero e todo menu pareceria curto — sem nenhum sintoma novo.
