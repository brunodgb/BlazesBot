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

## "segue X" só vale com o APP do líder LIGADO (08/09/2026)

Relato: *"esse 'segue...' só deve aparecer se o líder estiver com o APP ativo, se
não, deixa o 'só login', pois só faz sentido aparecer se o líder estiver junto,
já que eu também posso ativar individualmente e posso estar com o APP inativo do
líder."*

O selo saía de `lideres_do_time_do_app()`, que respondia "quem tem esta conta na
lista dele" — e lista guardada **não é** time valendo. O supervisor sempre soube
disso: `_SupervisorDaConta._lider_do_time` só convoca quando *"esse alguém está
com o modo APP LIGADO (líder desligou, time acabou)"*. A tabela contava uma
verdade que o bot não estava praticando — a conta ficava só no login e a tela
dizia que ela trabalhava para outra.

A condição entrou na mesma função, junto das outras duas que já faziam o líder
ser **efetivo**: líder que segue outro não lidera, e a resolução é numa passada
só. Nenhum outro consumidor existe — a função foi criada para a tabela.

**Desligar o APP não apaga o time montado.** `time_logins` continua intacto (a
invariante de que "sair do time por `bc_farm` não apaga o login" vale igual
aqui); o que muda é só o que a tela diz. Religar o APP do líder devolve o "segue
X" sem o usuário remontar nada — travado no teste.

Verificado na tela, nos dois estados, com a config real do usuário:

| líder `blazestpas` | gamerblazes | mfaustoapp069 |
|---|---|---|
| APP **ligado** | `segue blazestpas` | `segue blazestpas` |
| APP **desligado** | `só login` | `só login` |

### O portão de tamanho do `config.py` estourou no caminho

A mudança são 2 linhas de código, mas o comentário que explica o porquê pôs o
arquivo em 2143 linhas contra um teto de 2136 (`test_quality_gates_python.py`).
Em vez de dividir o arquivo — refatoração grande e fora do pedido — condensei a
docstring que eu mesmo tinha escrito nessa função em 06/09: o texto longo é
exatamente o que a Governança manda morar **aqui**, não no código. O arquivo
voltou a 2136.

Fica o registro de que `config.py` está **no limite exato**: a próxima linha que
entrar ali vai ter de vir com a divisão em pacote que o portão pede.


## O seguidor nunca aceitava: o contexto do aceitador não sabia quem ele era — 16/09/2026

### O sintoma

*"Reabri o bot e ativei o APP, mas só tem o líder e a fada no time; o terceiro
integrante, que seria o WizzOfBlazes5, não está em equipe — ele deveria ser
chamado, mas não foi, simplesmente começa a macro."*

### O que o log dizia — e o que ele não dizia

O líder tinha feito a parte dele, e a montagem funcionou como desenhada:

```
09:39:13  [blazestpas] Time do APP: faltam gamerblazes no time. Convidando um por vez.
09:39:23  [blazestpas] 'WizzOfBlazes5' não aceitou em 4s.
09:39:30  [blazestpas] 'WizzOfBlazes5' não aceitou em 4s.
09:39:36  [blazestpas] 'WizzOfBlazes5' não aceitou em 4s.
09:39:43  [blazestpas] gamerblazes não entraram em 4 passada(s).
```

Do lado do seguidor, **nada**. Nem aceite, nem recusa, nem aviso — e ele estava
rodando a macro, com o aceitador ligado, a duas conferências por segundo.

Seis horas depois, num religar do bot:

```
15:09:21  [gamerblazes] Template 'state_team_invite_texto.png' CASOU em (544, 199)
15:09:21  [gamerblazes] Convite de time ACEITO — sem verificação possível @ (431, 331)
15:09:26  [gamerblazes] Modo APP iniciado
```

A caixa do convite tinha ficado na tela o tempo inteiro. Quem a aceitou foi o
aceitador do SUPERVISOR, nos segundos entre o login e o começo da macro — e foi
por isso que, quando fui medir, os três já estavam no time.

### A medição que fechou o caso

Leitura ao vivo dos seis clientes, com o bot rodando:

```
BlazesAPP1     tamanho_do_time()=3   ['BlazesAPP1', 'Tsuki69', 'WizzOfBlazes5']
Tsuki69        tamanho_do_time()=3   ['BlazesAPP1', 'Tsuki69', 'WizzOfBlazes5']
WizzOfBlazes5  tamanho_do_time()=3   ['BlazesAPP1', 'Tsuki69', 'WizzOfBlazes5']
```

Ou seja: no instante da medição o time estava completo e `falta_alguem` devolvia
`[]` com razão. O defeito não estava na montagem — estava no ACEITE, horas
antes.

### A causa

`aceitador_do_seguidor` monta um `BotContext` **novo** — o modo APP roda fora do
contexto do farm, e não há de quem pegar emprestado. Esse contexto nasce com
`char_name = None`: quem preenche é a sessão do supervisor
(`supervisor.py`, `ctx.char_name = char_name`), **no contexto dela**.

E o `InviteAcceptor` identifica o convite pelo anúncio interno:

```python
remetente_anunciado = convite_pendente(self._meu_nick)   # _meu_nick = ctx.char_name
```

Com o nick vazio o dicionário do mural nunca bate, `remetente_anunciado` é
`None` e **o caminho do anúncio nem começa**. Sobra o da imagem — e dentro da
macro o `PrintWindow` deste cliente quase nunca devolve quadro, que é a razão de
o caminho do anúncio existir.

O `bater(self._meu_nick)` da primeira linha caía na mesma armadilha: com nick
vazio, a batida também não saía.

### Por que os testes não pegaram

Todos os dublês de contexto passavam `char_name="Um"`. O teste exercitava o
`InviteAcceptor` — que estava certo — e nunca a FÁBRICA que monta o contexto
dele. Por isso o teste novo (`test_o_contexto_do_aceitador_SABE_QUEM_E`)
exercita `aceitador_do_seguidor`, não o aceitador.

### O que mudou

1. **O contexto passa a saber quem é.** Primeiro o nome CONFIRMADO no login
   (`sup._ctx_atual.char_name`, que veio da memória), e o do config como
   reserva — que é com ele que o líder anuncia (`_nick_do_login`).
2. **A recusa sem prova deixa rastro**, uma vez por convite, dizendo qual das
   duas vias faltou: imagem ou memória. Recusar calado foi o que escondeu isto
   por um dia inteiro — o líder registrava "não aceitou em 4s" e do outro lado
   não havia uma linha sequer.

### O que ainda não se sabe

Se `memory.modal_open()` acende para a caixa de convite de time. É a via que
responde com o cliente fora de primeiro plano, e sem ela o seguidor continuará
recusando quando a captura vier preta — só que agora **dizendo isso no log**. A
próxima run responde.

## CINCO CAUSAS PARA UM SINTOMA SÓ — 19/09/2026

O usuário relatou três coisas no mesmo dia, e por trás delas havia **cinco**
defeitos independentes. Todos silenciosos, todos no mesmo caminho: o time do
APP não se montava.

O relato: *"quando eu paro a função APP do líder e recomeço, ele não está
verificando se ele está em team — eu removi todos do team e não fez o envio"*;
*"o seguidor está demorando muito para aceitar, vi o líder enviando team 3 ou 4
vezes"*; *"os 2 damage estão em team, mas a fada não está, e os dois estão
atacando normalmente, sem enviar o team para a terceira integrante"*.

### O que o log mostrou (todas as medições são de `blazes-dev.jsonl` do dia)

| # | Sintoma | Causa |
|---|---|---|
| 1 | religar não confere o time | o relógio da cadência é do SUPERVISOR, que sobrevive ao ligar/desligar do modo APP |
| 2 | a Fada nunca é convidada | `_esta_de_pe` olhava só o canal que a macro publica; a Fada bate em OUTRO |
| 3 | o seguidor demora a aceitar | no modo `copiar` toda volta é cega, e a volta cega não passava pelo `_esperar` |
| 4 | a Fada não aceitaria nem se recebesse | o laço dela nunca teve aceitador — como o modo APP até 16/09 |
| 5 | o seguidor larga antes do time | as threads arrancam juntas; ninguém esperava ninguém |

**1. A cadência velha.** Religado 13 s depois de parar (11:42:10), nenhuma
conferência. Religado 2min35 depois (11:45:20), conferência 1,6 s após o
arranque. `_proxima_conferencia_do_time` é atributo do supervisor, e o modo APP
é reiniciado dentro dele: o comentário que dizia *"a cadência começa zerada"*
valia para um supervisor recém-criado, não para o religar — que é exatamente
quando o usuário acabou de mexer no time. A chamada do arranque passou a furar
a cadência (`no_arranque=True`); a regra de batalha continua valendo.

**2. Dois canais de sinal de vida.** Quatro ciclos seguidos de *"mfaustoapp069
sem sinal de vida agora; fica para o próximo ciclo"* (11:45:21, 11:46:50,
11:48:27, 11:49:28) com a Fada rodando — e, do lado dela, *"WizzOfBlazes5 não
está no meu painel de time — esperando ele aparecer"*. As duas se esperando
para sempre. A macro do APP publica em `publicar_estado` a cada volta; a Fada
nunca passa por lá, ela bate em `bater_fada` de dentro do laço de cura.
`_esta_de_pe` agora aceita os dois.

**3. A volta cega era surda.** O gancho do aceite morava só em
`executor._esperar`, e `sincronia.volta_cega()` é verdadeira em todo modo que
não seja `mesmo_alvo` — o padrão é `copiar`. Medido: convites às 11:45:21,
11:45:28 e 11:45:35, e o aceite saindo às **11:45:42.867, 16 ms depois de
"Modo APP encerrado"** — quem clicou foi o aceitador do supervisor, com a macro
já parada. O `_dormir` (a espera cega) passou a perguntar também.

Para isso caber dentro da linha, `check_and_accept` deixou de **capturar a tela
antes de saber se há convite**: eram ~15 ms a cada meio segundo gastos para
descobrir que não havia nada a fazer, e dentro da linha esse tempo entraria em
UMA conta e desalinharia o time — que é justamente o que a volta cega existe
para evitar. Agora a captura só acontece com convite anunciado (no aceitador do
APP; o da conta de reset continua olhando a tela, é por lá que ele reconhece
convite de estranho).

**4. A Fada sem aceitador.** `fada_montagem.py` não tinha uma linha sobre
convite. É o mesmo defeito que o modo APP teve até 16/09/2026, pelo mesmo
motivo: `rodar()` fica horas dentro do laço e o aceitador do supervisor só volta
a rodar quando ele termina. Ela reusa a MESMA peça do APP
(`time_do_app.aceitador_do_seguidor`), que não sabe o que é macro.

**5. Ninguém esperava ninguém.** *"Quando eu starto a função APP por um líder, a
primeira coisa que deve ser vista, antes de executar qualquer outra coisa, de
qualquer um se mexer, é verificar e montar o team."* No log, a macro do seguidor
começou às 11:45:20.972 e a conferência do líder às 11:45:21.853 — **0,9 s de
diferença**, e o seguidor já batendo. O seguidor agora espera entrar no time
antes de `executor.rodar()`.

A espera precisou de três coisas, e a primeira não é detalhe:

- **publicar sinal de vida enquanto espera.** O líder só convida quem está de pé
  (regra 2 acima), e quem está parado ali ainda não rodou uma volta — sem
  publicar, os dois se esperariam. Foi o que transformou a publicação numa peça
  com nome (`publicar_que_estou_de_pe`), usada pelos dois chamadores.
- **aceitar o convite enquanto espera.** A macro ainda não começou, então o
  gancho de dentro dela não existe.
- **ter TETO DERIVADO**, não inventado: `ESPERA_PELA_RESPOSTA ×
  TENTATIVAS_POR_MEMBRO × membros`, que é o pior caso da montagem do líder.
  Estourado, a macro começa assim mesmo — ficar parado esperando um líder que
  não vem é pior que farmar sozinho, e o convite continua sendo aceito lá
  dentro.

Não espera por líder desligado, por líder que não está no APP, nem com mob
batendo.

### O que este dia ensinou sobre o log

As cinco causas eram **silenciosas**: `montar_o_time` volta calado quando a
cadência segura, quando não há ninguém faltando e quando a leitura do time não
responde. O que quebrou o caso foi a única linha que alguém teve o cuidado de
escrever — *"sem sinal de vida agora"* — e a comparação de dois religares com
tempos diferentes. Decisão herdada de 16/09 e confirmada: **recusa sem rastro
esconde defeito por dias.**

### O Pick Mode: Free funcionou

Confirmado pelo usuário no mesmo dia (*"sem eu ter feito nada manualmente,
percebi que está no Free"*) e pelo log: `Pick Mode: submenu aberto; clicando em
'Free' em (232, 121)`. O hover sintético abre o submenu neste cliente — a dúvida
de 15/09 está respondida.

## A SEGUNDA RODADA DO MESMO DIA — 19/09/2026, tarde

Com as cinco causas da manhã corrigidas, o usuário testou de novo e viu duas
coisas: *"o líder enviou o convite para a fada, ela aceitou e ele começou a
rodar a macro — tem que enviar a todos do time"*; e *"depois de um tempo do
líder rodando a macro, ele enviou o team para o outro integrante, mas ele não
aceitou e voltou a ficar parado sem fazer absolutamente nada"*.

Mais três causas, todas no log do teste.

### 1. A fila era calculada UMA vez (e por 150 ms)

    13:10:37.295  gamerblazes sem sinal de vida agora; fica para o próximo ciclo
    13:10:37.295  faltam mfaustoapp069 no time. Convidando um por vez
    13:10:43.400  'Tsuki69' entrou (time com 2)
    13:10:44.182  Modo APP iniciado

O seguidor publicou o sinal de vida **logo depois** daquela leitura — ele
estava, naquele instante, entrando no `esperar_o_lider_montar`. Como a fila era
montada uma vez, ele ficou de fora da montagem inteira: o time começou a macro
com 2 de 3, e o terceiro só seria convidado 60 s adiante.

**A fila passou a ser refeita a cada passada**, sem quem já aceitou (o aceite
chega pelo anúncio da outra ponta antes de o jogo mostrar o time) e sem repetir
o aviso de quem está ausente. Com quatro passadas, quem sobe no meio entra.

### 2. O anúncio saía ANTES do clique

    13:11:57.714  faltam gamerblazes no time. Convidando um por vez
    13:11:57.772  Convite de 'BlazesAPP1' anunciado, mas sem prova de caixa na tela
    13:12:02.289  Clicando em 'Team up' em (575, 396)

`_enviar_convite` leva de 4 a 5 s — limpa a Block list, registra o nick, abre o
menu de contexto e só então clica. O anúncio saía no começo disso, e o
convidado, que exige prova, procurava uma caixa que **ainda não existia**. A
recusa estava certa; o anúncio é que estava cedo. Ele passou para depois do
clique.

Vale registrar que o mecanismo funciona quando as duas pontas se encontram: a
Fada recusou às 13:10:37.711 pelo mesmo motivo e, 4,7 s depois, casou o template
(`state_team_invite_texto.png` em (544,199)) e aceitou. **A prova por imagem
responde** — ela só precisa que a caixa esteja lá.

### 3. Setenta e cinco segundos parado, surdo e mudo

    13:12:08.335  vida em 80%; curando com poção (tecla 9)
    13:13:23.962  gastei 5 poção(ões) e a vida parou em 99%, abaixo dos 100%

Entre essas duas linhas não há mais nada dessa conta. `_curar_com_pocao` bebe
até cinco poções esperando 15 s por cada uma, e nesse intervalo:

- **o mural a dá por offline** — o sinal de vida vale 30 s e quem o publicava
  era o gancho por volta, que não roda aqui. Foi por isso que às 13:13:09 o
  líder registrou *"gamerblazes sem sinal de vida agora"* com ele rodando.
- **ela não atende convite** — o gancho do aceite mora nas esperas do executor,
  e a cura tem as esperas dela.

Os quatro convites do líder caíram nesse buraco, e a caixa ficou na tela
**engolindo as teclas**: *"a bolsa não apareceu em 2.0s depois da tecla 'I'"*,
*"1 TAB(s) sem resposta"*. É o "parado sem fazer absolutamente nada".

As duas faltas têm a mesma causa — o que roda uma vez por volta não serve para
nenhuma delas — então viraram **uma peça só: o pulso do time** ("estou de pé" +
"aceito convite"), chamado na cadência das esperas fatiadas: `_esperar`,
`_dormir` e as quatro esperas da cura (`cura._passo`). O gancho
`aceitar_convite` do executor passou a se chamar `pulso_do_time`, que é o que
ele faz.

**Custo**: duas escritas em dicionário a cada 0,16 s. A captura de tela só
acontece quando há convite anunciado — foi o que tornou possível chamar isso de
dentro da linha sem desalinhar o time.

### Um número que o usuário vai querer olhar

A poção gastou cinco unidades para ir de 80% a 99% e parou *abaixo* do alvo,
porque `cura_parar_pct` está em 100%. Alvo em 100% com poção fraca é receita
para o personagem passar mais de um minuto parado bebendo — o log já avisa
(*"poção provavelmente fraca demais"*), mas quem decide o número é ele.

## A ÂNCORA DO TIME — o ponto do líder vale para todos (22/09/2026)

Pedido do usuário: *"o Líder deve ditar a coordenada âncora (Ponto Inicial) para
todos os seguidores e fadas, forçando um agrupamento perfeito"*.

### O problema, e por que ele é de combate

Cada conta guarda o SEU ponto inicial (`app._base_pos_x/_y` no config, ou a
primeira posição lida). A trava de distância puxa cada uma para o dela: quem
ligou o bot dois passos para o lado volta para dois passos para o lado. Sob
ataque isso é um time esticado — **a Fada é quem mais sofre**, porque ela não
persegue ninguém: fica parada curando, e a cura tem alcance.

### O canal é o MURAL, e não arquivo

As contas são **threads do mesmo processo** (`supervisor-<login>`), e o mural já
é a memória compartilhada delas, com tranca — é por onde passam a largada, o
sinal de vida, o id de cada um e o convite. Um `team_anchor.json` acrescentaria
disco, leitura em laço e um arquivo velho para limpar, para transportar **dois
inteiros entre threads que enxergam o mesmo dicionário**.

Ele mora em `bot/mural_da_ancora.py`, e não dentro do `mural.py`, pelo mesmo
motivo do quadro dos mortos: o `mural.py` está no teto de 800 linhas do portão
de qualidade — a âncora tem dicionário e tranca próprios, então sai limpa. O
`mural` reexporta, e quem lê continua dizendo `mural.publicar_ancora(...)`.

**SEM VALIDADE, ao contrário da largada.** Uma largada é um INSTANTE (entrou ou
perdeu); a âncora é um FATO que dura a sessão do líder. Um prazo faria o
seguidor perder a referência no meio do farm e voltar para a dele — exatamente o
espalhamento que isto existe para impedir. Quem apaga é o líder, ao encerrar.

### As três travas

1. **PUBLICA UMA VEZ, e só o líder.** No arranque do modo APP, junto de onde a
   base já era decidida. Publicar durante o farm moveria a âncora do time para
   onde o líder estivesse — e ele anda, porque a macro anda.
2. **O seguidor ESPERA (teto de 4 s).** É a trava de concorrência: sem ela ele
   montaria a trava de distância com a posição dele e só descobriria a do líder
   na volta seguinte — ou nunca, porque a base entra no executor por parâmetro e
   é lida uma vez. O teto é `ESPERA_PELA_RESPOSTA`, já medido, contra uma
   defasagem real de ~0,9 s entre o arranque de duas contas (log de 19/09/2026).
   Estourado, ele usa o ponto dele: começar espalhado é ruim, não começar é pior.
3. **SOLO NÃO MUDA NADA.** As duas funções devolvem sem fazer nada quando não há
   time (`_tem_time_do_app()`), e o seguidor nunca publica (`_dono_da_macro()`).
   Não existe caminho em que a mesma conta faça as duas coisas.

### A ÂNCORA VAI PARA O CONFIG TAMBÉM — correção de 23/09/2026

O desenho de ontem trocava a base só em memória, com o argumento de que gravar
no `config.json` "apagaria o ponto solo da conta". **Esse ponto solo não
existe**, e o usuário apontou: *"a cada vez que a função APP é recomeçada esse
valor é substituído"*.

Conferido no código: cem linhas antes da âncora, TODO arranque do modo APP lê a
posição atual do personagem e grava por cima de `_base_pos_x/_base_pos_y` — é
assim que o usuário muda o ponto base, parando e reiniciando o APP. O que estava
no config não era um ajuste guardado: era a foto do arranque anterior.

Então gravar não apaga nada, e o próximo arranque solo do seguidor sobrescreve
sozinho com a posição de quem está rodando. **O que a gravação compra é o config
e o que o bot USA dizerem a mesma coisa**: divergentes, qualquer leitor do config
— a tela, um diagnóstico, um caminho de código que ninguém auditou — responderia
com um ponto que o executor não está usando.

A gravação é segura entre as threads pelo mesmo motivo que a de cem linhas antes:
`BotConfig.save` escreve num arquivo ao lado e substitui de uma vez, sob tranca,
justamente porque "os supervisores gravam do mesmo objeto em threads
diferentes".

### (0,0) é recusado

É o que a leitura de posição devolve quando o personagem ainda não entrou no
mundo. Ancorar o time ali mandaria todo mundo andar para o canto do mapa.

### E a FADA precisou da mesma linha, no arquivo dela — 23/09/2026

A gravação acima mora em `supervisor._rodar_modo_app`, e **a Fada nunca passa
por lá**: o laço dela é o `fada_montagem.rodar_a_fada`. O sintoma foi o usuário
reabrir o bot e olhar o `config.json`:

    blazestpas (líder)   base = (1870, 1668)
    gamerblazes          base = (1870, 1668)
    blazesgamer          base = (1870, 1668)
    blazesofgamer        base = (1870, 1668)
    mfaustoapp069 (Fada) base = (0, 0)        <-- ela

Os três de dano estavam certos porque passam pelo modo APP. Ela estava em (0,0)
porque **nada nunca tinha escrito a base dela** — o bloco que salva a posição no
arranque é do modo APP também. A âncora agora vai para o config dela no mesmo
ponto em que semeia o `ponto_inicial`.

A lição, que vale para o resto: **a Fada é um ecossistema de laço próprio.**
Toda vez que algo entra no arranque do modo APP e vale para o time, é preciso
perguntar se ela também precisa — porque ela não passa por nenhuma linha de lá.
Foi assim com o aceite de convite (19/09), com a batida no mural e agora com a
âncora.