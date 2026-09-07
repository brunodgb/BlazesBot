# Time do APP — a mesma macro em até cinco contas ao mesmo tempo

> **Pedido do usuário em 27/08/2026.** *"quero fazer um sistema de sincronização,
> onde eu posso escolher até 4 outras contas cadastradas e todas vão rodar a
> macro daquela conta, de forma sincronizada, para que sempre ataquem juntos,
> façam todas as verificações juntos e sempre voltem para o mesmo ponto
> inicial."*
>
> Este arquivo guarda o **porquê**. A regra que não pode ser violada está em
> `docs/INVARIANTES.md`, seção "Time do APP".

## STATUS EM 28/08/2026: OS DOIS MODOS SINCRONIZADOS NÃO FUNCIONAM

**Declarado pelo usuário depois de rodar com duas contas de verdade:** nem
*"começar cada volta juntos"* (`largada`) nem *"começar juntos e com mesmo
alvo"* (`mesmo_alvo`) entregam o que prometem. `copiar` — que é só a macro
emprestada, sem sincronia — não faz parte deste veredito.

Fica escrito aqui porque a área vai continuar sendo mexida (a Fada), e quem
chegar depois precisa saber que **isto está em aberto, não resolvido**.

### O que foi observado, em ordem

1. **Defasagem estável.** Log real: voltas de ~20 s com **13 s de atraso fixo**
   entre as contas, volta após volta. A largada ficava aberta 3 s de um ciclo de
   20, e quem perdia rodava uma volta solo inteira — a defasagem era preservada.
2. **`mesmo_alvo` sem alinhar.** *"raramente atacam o mesmo mob"*. Duas causas
   distintas: o modo salvo no `config.json` era `largada` (o usuário trocou na
   tela e não salvou), e o desenho de então deixava o atrasado mandar a linha
   VELHA dele.

### O que foi corrigido DEPOIS dessa observação, e ainda não foi validado

Nenhuma destas correções chegou a rodar com duas contas. **Elas não devem ser
tratadas como "funciona" até alguém medir de novo:**

- sincronia linha a linha em vez de por volta (o líder marca cada tecla);
- o seguidor deixou de ter cursor próprio: ele manda a linha que o líder
  anunciou, não a dele;
- teto de espera passou a incluir o delay da linha (com teto fixo de 2 s e
  macro de 3000 ms, o líder era dado como sumido em toda linha longa);
- teto do alinhamento passou a caber dentro do teto da largada;
- o TAB de abertura da volta deixou de desfazer o alinhamento;
- volta cega nos modos simples, para a volta de todas as contas durar o mesmo;
- o TAB deixou de trocar um alvo que já existe.

### O que NUNCA foi medido, e é onde a dúvida mora

**O `TARGET_ID` do mesmo mob é o mesmo número em dois clientes diferentes?**
Ninguém verificou. Se não for, `mesmo_alvo` é impossível pelo caminho atual e a
correção não é de sincronia — é de premissa. Por isso cada comparação passou a
ir para o log.

## O que foi decidido, e o que foi RECUSADO

Cada linha abaixo saiu de uma pergunta feita ao usuário antes de existir código.
A coluna da direita é o que **não** foi feito — e é a parte que costuma se
perder.

| decisão | o que foi recusado, e por quê |
|---|---|
| **O time é do LÍDER.** Quem monta o time é a conta que preencheu `time_logins`; quem aparece na lista de outra é seguidora, e o time dela é ignorado. | Time simétrico (todo mundo lidera todo mundo). Abre o nó de A liderar B enquanto B lidera A, e não existe resposta certa para "de quem é a macro". |
| **Empresta SÓ a macro** — as 20 linhas, os delays e `espera_depois_do_tab_ms`. | Emprestar a configuração inteira. `_base_pos_x/_base_pos_y` são a coordenada **daquele** personagem: copiar manda o seguidor andar para o mapa errado. A tecla do TAB é `KeyBinds.next_target`, que descreve o teclado daquele cliente. |
| **Empréstimo em tempo de execução.** O `config.json` do seguidor fica intacto. | Gravar a macro do líder por cima da macro do seguidor. Apaga configuração do usuário sem desfazer, pelo ganho de zero. |
| **Barreira com teto na largada de cada volta**, e quem estoura o teto **continua batendo** e entra na próxima largada que alcançar. | (a) Barreira sem teto: um seguidor curando deixa os outros três parados. (b) Atrasado esperando parado: personagem parado num farm morre, e o usuário foi explícito — *"o ideal é nenhum personagem ficar parado esperando, sempre batendo"*. |
| **Três modos**: `copiar` (só a macro), `largada` (padrão), `mesmo_alvo`. | Um modo só. O usuário quis poder escolher, e os três custam coisas diferentes. |
| **`mesmo_alvo` compara `TARGET_ID`.** O líder publica o id; o seguidor dá TAB até o próprio alvo bater. | Tecla de *assist*. **Não existe** neste jogo — conferido campo a campo em `KeyBinds` (19 campos, nenhum de assist). |
| **Morte = sair de batalha**, e o líder publica. | Cada conta descobrir sozinha. Quem está cego (memória não lê) nunca corta a volta e fica batendo no cadáver. Publicar é de graça: o canal já existe para o alvo. |
| **Líder caído: assume quem tem mais `max_hp()`**, calculado no instante da queda; sem memória, aleatório; o líder real retoma na próxima largada. | Time parar até o líder voltar. Relogin leva minutos, e parado o personagem morre. |
| **`bc_farm` e APP nunca juntos.** Conta farmando a cave não aparece na escolha e fica "fora: farmando BC". | Arrancar a conta do meio de uma run. Teleporte gasto, travessia feita, boss vivo — é run perdida em silêncio, o defeito nº 1 que `test_reset_de_time.py` existe para impedir. |
| **Seguidor sai do time por `bc_farm` SEM ser apagado** de `time_logins`. | Remover o login do `config.json`. Apaga configuração por causa de um clique reversível. |
| **A party DENTRO do jogo o usuário monta na mão** (por enquanto). | O bot montar a party ao ativar o time. Exige mudar a precedência do `supervisor` (hoje `app.enabled` corta o laço antes do aceitador de convite, `supervisor.py:1031`) — e essa precedência é o que impede APP e farm de disputarem o teclado. |
| **A vida circula no mural, mas hoje só decide a eleição.** | O time reagir a vida baixa (esperar/recuar por um membro curando). É a barreira sem teto por outro nome. O dado já circula para quando isso for pedido. |

## O que o CÓDIGO impôs (e não estava no pedido)

Levantado por leitura antes de escrever a primeira linha:

1. **O executor do APP não pode importar de `blazesbot.bot`.**
   `tests/test_ecossistemas.py:89` lê o AST e reprova qualquer `blazesbot.*` que
   não seja `blazesbot.core`; `tests/test_saude_em_todo_ecossistema.py:90`
   reprova até o **nome** `BotContext`. Toda sincronia chega ao executor como
   **callable injetado** — o `__init__` (`executor.py:715`) já recebe 20+ deles,
   e `cura` é uma **fábrica que recebe `self`** (`executor.py:964`), que é o
   molde exato para um objeto de sincronização.
2. **Por isso o mural vai para `bot/`, não para `core/`.** O executor não ganha
   o import de qualquer forma, e o mural sabe o que é conta/nick — conceito de
   `bot/`. `core/` não compraria nada.
3. **`rodar()` ignora o retorno de `uma_volta()`** (`executor.py:2698`): quem
   encerra o laço é só `self._continuar()`. Uma barreira que devolva "pare" pelo
   retorno **não seria observada**.
4. **`LACO_SIMPLES = True`** (`executor.py:139`): o corpo antigo de `uma_volta`
   (L2302-2465) **não roda**. O caminho vivo é `_uma_volta_simples` (L2467).
5. **Armadilha do move:** as três funções de ACEITE usam `_LOCK_CONVITES`, não
   um lock próprio (`bc/team.py:288-313`). Separar os murais em módulos
   diferentes **duplica o mutex** e muda a exclusão mútua sem alterar corpo de
   função nenhum.
6. **`test_reset_de_time.py:139`** exige que a primeira instrução de
   `InviteAcceptor.check_and_accept` seja `bater(...)` como **`ast.Name`** (nome
   nu). Vira `mural.bater(...)` ⇒ reprova.
7. **`test_reset_de_time.py:85`** faz `monkeypatch.setattr(mod_team.time, ...)`:
   um facade em `bc/` que só re-exporte símbolos, sem `import time`, levanta
   `AttributeError`.
8. **`tests/test_linha_zero_do_app.py:56-65`** é o teste de layout da aba APP:
   exige **exatamente duas** ocorrências de `$$("#corpo-app tr.app-linha")` e
   **zero** de `$$("#corpo-app tr")`. Dividir a tabela em dois `tbody` reprova —
   ou, pior, um seletor sem `.app-linha` leva a linha 0 do TAB para dentro de
   `steps`.
9. **`tests/test_campos_numericos_da_web.py:70`** só cobra o piso de 100 ms
   quando o rótulo `(ms)</span>` vem colado no `<input>`. Reordenar o markup
   **desliga a verificação em silêncio** — o teste continua verde sem conferir
   nada.
10. **`tests/test_linha_zero_do_app.py:158`** exige `dist/` recompilado: mudar
    `web/` sem `npm run build` reprova.

## MEDIR DEPOIS, NÃO ANTES — decisão do usuário em 27/08/2026

> *"é importante deixar rodando mesmo sem as medições, para justamente a gente
> testar em um cenário real, e após termos os logs a gente ajusta os tempos e a
> sincronia perfeita."*

Isto INVERTE a recomendação que estava escrita aqui (medir antes de escrever
qualquer número). O que a inversão obriga, em troca:

1. **Todo número provisório é declarado como tal** — no código e no
   `docs/TEMPOS.md`. Um número provisório que não se anuncia vira, em duas
   semanas, um número medido que ninguém lembra de ter medido.
2. **A rodada real É a medição.** A sincronia registra no log o que a aferição
   registraria: quanto cada conta atrasou na largada e por quê, quantos TABs o
   alinhamento custou, e quantas vezes o teto estourou. Sem isso a rodada
   confirma "funciona" ou "não funciona" e não diz mais nada.
3. **O provisório erra para o lado seguro.** Na dúvida, esperar de mais é
   perder alguns segundos por volta; esperar de menos é comparar contra o alvo
   ANTERIOR e concluir "não alinhou" quando alinhou — erro calado, o tipo que
   este projeto persegue.

## O que ainda NÃO está medido

Nenhum número de sincronia foi escrito, e não será antes destas duas medições —
regra do projeto ("número novo precisa de MEDIÇÃO"):

1. **Atraso entre o TAB e a memória mostrar o `TARGET_ID` novo.** É o piso
   físico da cadência de alinhamento. Mais rápido que isso e a conta compara
   contra o alvo **anterior**, concluindo "não alinhou" quando alinhou — erro
   calado. Ferramenta no molde de `bot/app/afericao.py` (adota a janela sem
   subir a thread, `_release()` no `finally` de toda saída).
2. **Distribuição do atraso entre as contas na largada**, de onde sai o teto
   `T` da barreira. Instrumentar o executor para logar atraso e causa, rodar a
   macro real do usuário, e tirar `T` do percentil.

Os 4 s da regra "sem trocar de estado de batalha ⇒ TAB" **não são medidos**: são
valor declarado pelo usuário, e entram no `docs/TEMPOS.md` marcados como tal. Os
`4.0` que já existem no BC são de outras coisas
(`SEGUNDOS_SENTADO_APOS_GUARDAS`, `SEGUNDOS_ANTES_DO_TAB_NO_BOSS`).

## POR VOLTA NÃO BASTOU — a rodada real de 28/08/2026

A primeira versão sincronizava só o COMEÇO de cada volta, que foi o que ficou
combinado no Q3 (*"não precisa ser linha a linha juntos, mas sempre dar tab e
começar a macro juntos"*). **A rodada real reprovou.** Medido no log:

```
00:13:21  blazestpas   volta 17 largou sem gamerblazes (teto 3s)
00:13:34  gamerblazes  sem largada de blazestpas em 3s -- indo sozinho
00:13:41  blazestpas   volta 18 largou sem gamerblazes
```

As duas contas rodavam voltas de **~20 s defasadas em ~13 s**, volta após
volta. O mecanismo:

1. a largada ficava aberta 3 s de um ciclo de 20 — uma janela de **15%**;
2. quem perdia a janela rodava uma volta solo INTEIRA;
3. como a volta solo dura o mesmo tanto, **a defasagem era preservada
   exatamente**. Nada puxava ninguém de volta.

E a causa de o atrasado nunca alcançar: ele **dormia o próprio delay ALÉM de
esperar o líder**. Nunca corria mais rápido que o líder, então nunca fechava a
diferença.

### O que passou a valer

O líder marca **cada linha** da macro (`mural.abrir_passo`); o seguidor espera a
marca antes de mandar a mesma tecla, por `threading.Condition` — aviso em
microssegundos, e não uma olhada a cada 50 ms. E, decisivo: **o seguidor não
dorme o delay dele**, só o piso de `MINIMO_DE_ESPERA_DO_APP_MS`. Quem dá o ritmo
é a marca.

A propriedade que conserta a defasagem é a comparação `>=` sobre
`(época, volta, linha)`: **marca já dada não faz esperar**. O atrasado manda as
linhas no piso até emparelhar, e uma conta uma volta inteira atrás destrava na
hora, porque a marca da volta seguinte já é "maior" que qualquer linha da
anterior.

### E a primeira correção ainda estava errada

Marcar cada linha não bastou, porque cada conta continuava com **cursor
próprio** e a marca era só uma autorização. Com o seguidor atrasado, a
comparação `>=` autorizava a linha **velha** dele: ele despejava as teclas
atrasadas a cada 100 ms enquanto o líder já estava na linha 12. Emparelhava no
relógio e divergia no conteúdo — e o efeito, medido pelo usuário rodando,
foi *"raramente atacam o mesmo mob"*.

**O seguidor não tem cursor próprio.** Ele espera a marca e manda **a linha que
a marca diz**, não a dele. Ficar para trás deixa de significar "mandar tecla
velha" e passa a significar "pular direto para onde o time está" — que é o que
*"mesmo comando ao mesmo tempo"* quer dizer. Se a marca já é de outra volta, a
volta local termina ali: o resto dela bateria fora de hora, e a largada seguinte
realinha tudo, inclusive o alvo.

E o "líder sumiu" vale por **volta**, não por linha: sem isso, um líder que caiu
no meio da volta custava um teto por linha restante — vinte esperas seguidas.

### Dois furos achados lendo o código contra a descrição do usuário

Nenhum dos dois teria aparecido em teste de unidade — os dois só falham com duas
contas de verdade:

1. **O teto do alinhamento era MAIOR que o teto da largada** (4 s contra 3 s): o
   líder desistia de esperar antes de o seguidor terminar de alinhar, e
   *"quando todos estão com o mesmo target_id todos começam juntos"* — a razão
   de o modo existir — nunca acontecia quando o alinhamento demorava. O
   alinhamento passou a ser DERIVADO do teto da largada, para não poder voltar
   a divergir.
2. **O TAB de cortesia do começo da volta desfazia o alinhamento.** A largada
   punha as contas todas no mob do líder e, uma linha depois, cada uma apertava
   TAB e ia para outro mob. No modo `mesmo_alvo` esse TAB passou a ser vetado
   pela sincronia.

## A IDENTIDADE DE UMA LARGADA É `(líder, época, volta)`

Não é o número da volta, e não é só o nome do líder. Os três juntos, porque
cada pedaço fecha um buraco que a revisão do Codex encontrou:

- **o número sozinho** recomeça do 1 a cada reinício do executor (relogin, o
  usuário religando o modo), e o estado publicado sobrevive a esse reinício.
  Uma confirmação da execução ANTERIOR valia para a volta 1 da nova, e o líder
  largava sozinho achando que o seguidor já tinha entrado;
- **sem o nome do líder**, a confirmação de um líder temporário contava para o
  titular, e vice-versa;
- **sem a época**, trocar de líder fazia a largada 1 do novo ser recusada
  porque o seguidor "já tinha entrado na largada 1" — a do antigo.

E a largada é **FECHADA** assim que o líder para de esperar. Antes ela
continuava válida enquanto o relógio permitisse: um seguidor entrava numa
largada já abandonada e os dois se contavam como juntos estando segundos fora
de fase.

## O SORTEIO VIROU ORDEM FIXA -- desvio do que foi combinado

Na conversa ficou *"se a memória não ler, escolhe um aleatório"* para o líder
temporário. **Foi implementado como ordem determinística** (maior `max_hp`;
empate ou memória muda, ordem do login), e o desvio é de correção, não de
gosto:

**cada conta decide isso sozinha, na própria thread.** Um sorteio faria a conta
A concluir "quem assume é B" e a conta B concluir "quem assume é C" -- e o time
passaria a ter DOIS líderes anunciando largadas concorrentes, que é pior que
não ter nenhum. Com ordem fixa todo mundo calcula a mesma resposta sem precisar
combinar nada. Travado por
`tests/test_sincronia_do_time.py::test_a_eleicao_e_deterministica_para_todas_as_contas`.

## DOIS DEFEITOS QUE OS TESTES PEGARAM ANTES DE RODAR

Ficam registrados porque os dois são invisíveis em leitura e silenciosos em
produção -- o time simplesmente não sincronizaria, sem erro nenhum:

1. **O líder perdia a liderança na primeira volta.** Ele só publica estado no
   FIM da largada, então qualquer seguidor que já tivesse publicado ganhava a
   eleição -- e o líder declarado passava a esperar a largada de quem ele
   lidera. Ninguém anunciava nada. Corrigido: quem é o líder declarado e está
   rodando não elege ninguém.

2. **`volta_pronta` comparava contadores diferentes.** O seguidor publicava o
   número da volta DELE e o líder comparava com o número da volta DELE. As duas
   contagens divergem no instante em que alguém perde uma largada, então a
   barreira "todos prontos" fechava só por coincidência. Corrigido com
   `volta_do_time`, que é sempre o número do líder.

## Os blocos, na ordem

| # | bloco | estado |
|---|---|---|
| 1 | Campos `time_logins` / `time_modo` no `AppConfig`, ponte web, testes | **feito** |
| 2 | Aba APP em duas colunas + painel do Time na direita + `npm run build` | **feito** |
| 3 | Promoção do `team.py`: `bot/mural.py` (quadro de avisos) + `bot/team.py` (time no jogo) | **feito** |
| 4 | Sincronia: mural do time, convocação no supervisor, largada no executor | **feito** |
| 5 | Ajuste dos tempos pelos logs da rodada real | a fazer |

A ordem não é gosto: **2** precisa dos campos de **1** e **4** precisa do mural
de **3**. Cada bloco fecha com a suíte inteira e uma revisão do Codex.

## A escolha do time: esconder é melhor que desabilitar (07/09/2026)

A lista de candidatas mostrava **todas** as outras contas cadastradas: as
inelegíveis iam desabilitadas, em 40% de opacidade, com o motivo escrito ao lado
("farmando a cave", "já no time de blazestpas"). O raciocínio original está no
comentário que saiu: *conta que some é o usuário procurando uma conta que ele
sabe que cadastrou.*

Com sete contas cadastradas isso se inverteu. O usuário: *"não quero que mostre
as contas inativas e as contas que estão fazendo outra coisa, ou se já tiverem em
outro time, pois é melhor nem mostrar se já não dá para usar aquelas contas no
time. Só cria uma lista cada vez maior."* Medido na config real dele: para um
líder, 4 candidatas visíveis contra 2 ocultas; para outras contas, 2 contra 4 —
mais da metade da lista era enfeite.

Vale notar que `docs/INVARIANTES.md` **sempre** disse que conta farmando a cave
"não aparece na escolha do time". Era o código que divergia do invariante escrito.

O que ficou de fora, e a ordem em que o motivo é decidido: **inativa** → **BC** →
**HH** → **APP próprio** → **já no time de outro**.

O APP próprio entrou numa segunda passada, e a primeira versão errou aqui. Eu
deixei quem tem `app.enabled` aparecendo, com o argumento de que "puxar para o
time uma conta que hoje roda a macro sozinha é o caso normal de montar um time".
O usuário olhou a tela e apontou o contrário: *"faltou esconder o que está
rodando APP, no caso o líder BlazesAPP1, está aparecendo para outras contas, mas
ele que está com a flag APP ativo e já é líder de um time."*

Ele está certo, e o argumento que eu usei estava simplesmente errado: **o
seguidor roda com a caixa "Ativar Modo APP" DELE desmarcada** — é a convocação
que o faz rodar (`_SupervisorDaConta._lider_do_time`, pedido do usuário em
27/08/2026). Então esconder quem tem a caixa marcada não fecha nenhuma porta:
candidata com a caixa marcada é conta que **já trabalha por si**, e puxá-la seria
tirá-la do que ela faz. O motivo distingue os dois casos, porque para quem olha
eles são diferentes: **"líder de um time"** (tem `time_logins`) explica por que
várias contas sumiram de uma vez; **"rodando o APP"** é a conta solitária.

### Duas coisas que este ajuste consertou de quebra

**A regra estava em dois lugares.** A tela remontava o motivo a partir de três
campos soltos (`farmando_bc`, `farmando_hh`, `lider_de_outro`). Dois lugares
decidindo a mesma coisa, e no dia em que aparecesse uma quarta função só um deles
saberia dela. Agora o backend manda o `motivo` pronto.

**O time perdia um login ao salvar.** A tela fazia `cx.checked = false` na conta
inelegível — e `lerTimeDoApp` salva o que está marcado. Ligar BC numa seguidora e
depois abrir o editor do líder e salvar **apagava** aquele login de
`time_logins`, violando a invariante escrita de que "sair do time por `bc_farm`
não apaga o login". Por isso quem já está no time aparece **sempre e habilitado**,
com o motivo em âmbar: o conflito fica visível e tirar continua sendo decisão do
líder. Verificado em tela com duas contas do time em conflito (uma em BC, uma
inativa): as duas marcadas, nenhuma travada, `time_logins` intacto.

### Dívida de paridade, preexistente

Esta lista **só existe na interface web** — a `account_dialog.py` da PyQt6 nunca
teve a escolha do time do APP (só menciona `time_logins` num comentário). A regra
da elegibilidade fica na ponte web hoje; quando a lista chegar à PyQt6, ela
desce para `BotConfig` e as duas telas passam a chamar a mesma função.
