# COMECE AQUI — Guia para quem nunca usou Python

Guia para zero conhecimento de Python. Siga na ordem, não pule etapas.

---

## O que mudou nesta versão (leia se você já tentou antes)

Se você recebeu o erro **`ModuleNotFoundError: No module named 'psutil'`**, a
causa foi esta: o `pip` instalou as bibliotecas em um Python, e o bot rodou com
**outro** Python. Isso acontece muito no Windows quando existe mais de uma
instalação, ou quando o script se eleva para administrador e o ambiente muda.

**Corrigido.** Agora a instalação cria um Python isolado **dentro da própria
pasta do bot** (`.venv`), e todos os atalhos usam explicitamente esse Python.
Não existe mais como errar o alvo.

Se você já rodou a versão antiga: **apague a pasta `.venv`** se ela existir e
rode `1-INSTALAR.bat` de novo.

---

## Visão geral

```
1-INSTALAR.bat       instala tudo             (uma vez só, sem admin)
2-DIAGNOSTICO.bat    testa ler o jogo         (com admin)
3-INICIAR.bat        interface de config      (com admin)
4-TESTE-LOGIN.bat    testa SÓ o login         (com admin)
5-DETECTAR-TELA.bat  mostra o que o bot vê    (com admin)
6-TESTE-CAPTURA.bat  salva print do que vê    (com admin)
7-DESCOBRIR-MEMORIA.bat  acha o ponteiro base (com admin)
```

Você não digita nenhum comando. Os atalhos pedem administrador sozinhos, com o
mesmo truque de PowerShell do seu `Client.bat`.

---

## PASSO 1 — Instalar o Python

Só precisa fazer uma vez na vida.

### 1.1 Baixar

**https://www.python.org/downloads/**

Recomendo **3.12 ou 3.13**. Evite a versão mais nova de todas — às vezes as
bibliotecas ainda não têm suporte pronto. Se o botão grande oferecer algo muito
novo, role até "Looking for a specific release?" e pegue um **3.12.x**.

### 1.2 Instalar

> ### ⚠️ ANTES DE CLICAR EM QUALQUER COISA
>
> Na parte de baixo da primeira tela do instalador tem uma caixinha:
>
> **`[ ] Add python.exe to PATH`**
>
> **MARQUE ELA.** Ela vem desmarcada por padrão, e sem ela o Windows não
> encontra o Python. É o erro nº 1 de quem instala pela primeira vez.

Com a caixinha marcada → **Install Now** → espere.

Se no final aparecer **"Disable path length limit"**, clique também.

### 1.3 Reiniciar o computador

Não é frescura. É o jeito mais confiável de o Windows reconhecer o Python.

---

## PASSO 2 — Extrair os arquivos

1. Botão direito no `BlazesBot.zip` → **Extrair Tudo**
2. Extraia para um caminho **simples**: `C:\BlazesBot` ou `D:\BlazesBot`
   - Evite Desktop, Documentos, OneDrive, ou caminhos com acento
3. **Não mova nem renomeie nada de dentro.** O bot é um conjunto de arquivos em
   subpastas; tirar algo de lugar quebra tudo

Você deve ver isto:

```
D:\BlazesBot\
    1-INSTALAR.bat
    2-DIAGNOSTICO.bat
    3-INICIAR.bat
    4-TESTE-LOGIN.bat
    5-DETECTAR-TELA.bat
    6-TESTE-CAPTURA.bat
    7-DESCOBRIR-MEMORIA.bat
    COMECE-AQUI.md        <- este arquivo
    README.md
    main.py
    verificar.py
    requirements.txt
    blazesbot\            <- o código
    data\                 <- templates de imagem
```

---

## PASSO 3 — `1-INSTALAR.bat`

Dois cliques. **Este passo não pede administrador** — não precisa.

Ele vai:
1. Encontrar seu Python
2. Criar a pasta `.venv` (o Python isolado do bot)
3. Baixar cerca de 150 MB de bibliotecas — leva de 2 a 10 minutos
4. **Verificar uma por uma** se instalaram

No fim você deve ver:

```
  [ ok  ] pymem (leitura de memória)
  [ ok  ] psutil (processos)
  [ ok  ] OpenCV (reconhecimento de imagem)
  [ ok  ] NumPy (cálculo)
  [ ok  ] pywin32 / janelas
  [ ok  ] pywin32 / criptografia
  [ ok  ] PyQt6 (interface)
  [ ok  ] módulos do BlazesBot

Tudo pronto.
```

**Se alguma linha der `[FALHA]`**, a mensagem já diz o comando para instalar
aquela biblioteca manualmente. Se persistir, me mande a mensagem.

---

## PASSO 4 — `2-DIAGNOSTICO.bat`

Confirma que o bot consegue ler as informações do jogo.

1. Abra o Talisman Online pelo seu `Client.bat`
2. **Entre com um personagem** — precisa estar no mundo, não na tela de login
3. Dois cliques em `2-DIAGNOSTICO.bat` → **Sim** na permissão → aperte uma tecla

O que você quer ver:

```
  [ ok  ] Nome do personagem     = WizzOfBlazes
  [ ok  ] Nível                  = 60
  [ ok  ] HP                     = 1987
  [ ok  ] Posição (X, Y)         = (30, 17)
  [ ok  ] Ouro                   = 7040
  ...
DIAGNÓSTICO: mapa de memória 100% válido nesta versão do cliente.
```

Alguns campos podem dar `[FALHA]` e isso é **normal** — "Nome do alvo" só tem
valor com alvo selecionado, por exemplo. O que importa são os três críticos:
**nome do personagem, HP e posição**.

Se os três críticos falharem, cole a saída aqui no chat.

---

## PASSO 5 — `3-INICIAR.bat` e configurar

Dois cliques → **Sim** na permissão. Abre a janela com abas.

> ### Por que administrador é obrigatório
>
> Seu jogo roda como administrador. O Windows tem uma regra (UIPI) que impede
> um programa comum de mandar cliques e teclas para um programa administrador,
> e de ler a memória dele.
>
> O detalhe cruel: **o Windows não dá erro**. Ele simplesmente ignora. Então
> sem administrador o bot abre, parece funcionar, e nada acontece no jogo. Se
> isso acontecer algum dia, a primeira coisa a checar é a elevação.

### Seção **Cliente**

- **Caminho do Client.bat** → "Procurar…" e aponte para o seu `Client.bat`
- **Resolução** → deixe `1024x768`, e **coloque o jogo nessa resolução**
  (`System > Graphics > Screen Size` dentro do jogo)
- **Contas simultâneas** → comece com **1**
- **Nível da montaria** → a sua (+7 a +12). A velocidade aparece ao lado

### Seção **Contas** ← faça esta antes do teste de login

**Adicionar conta** e preencha:

| Coluna | O que colocar |
|---|---|
| Ativa | marcado |
| Login | seu usuário do jogo |
| Senha | sua senha — fica cifrada no disco |
| Posição | qual plaquinha de nome clicar: Left, Center ou Right |
| Servidor | o seu servidor |
| **BC Farm** | marque para esta conta farmar a cave |

Sobre **Servidor**: a lista do jogo tem hoje **5 servidores**, nesta ordem:

```
White Horse [NEW]
Tiger Fish (WW)
Sky Ice (GSM&BI)
All Stars
Light in the Darkness
```

Houve fusão de servidores no cliente ver.6400 — `Sky Ice (GSM&BI)` é a junção
de Giant Sky Medal com Blue Ice, e `Tiger Fish (WW)` a de Tiger Fish com Wild
Wave. Se você tinha um nome antigo salvo, o bot converte sozinho para o novo.

A lista de servidores **abre já com uma linha selecionada** — normalmente a
última que você usou. Por isso o bot sempre clica na linha do servidor
escolhido e, quando há imagem disponível, **confere que o realce azul mudou de
lugar** antes de apertar Ok. Sem essa conferência ele entrava no servidor
errado.

Sobre **Posição**: é em qual **plaquinha de nome** o bot clica na tela de
seleção, da esquerda para a direita. Com um personagem só, ele fica no meio →
`Center`.

Sobre **BC Farm** — **login e relogin automático valem para toda conta ativa**,
é a função básica e não se desliga. A caixa **BC Farm** decide apenas se aquela
conta também roda o boss-rush da cave.

E ela pode ser marcada e desmarcada **com o bot rodando**. Marque durante a
execução e a conta começa a farmar em segundos, sem reabrir o jogo nem
reiniciar o bot. Desmarque e ela volta a ficar só online — a rotina devolve o
controle num ponto seguro, entre estados, nunca no meio de uma ação.

No log você vê a confirmação:

```
[gamerblazes] BC farm LIGADO em tempo real
```

Isso permite, por exemplo, deixar quatro contas online e ir ligando o farm de
uma em uma conforme você acompanha.

### Seção **Teclas**

Aqui você diz **quais teclas o bot deve apertar**. Olhe a barra de atalhos do
seu personagem e transcreva.

- **Skills de ataque** → separadas por vírgula, na ordem de uso: `1,2,3`
- **Poção de HP** → a tecla da poção: `5`
- **Montaria** → `0`
- **Invocar pet** → obrigatório: `9`
- **Buffs** → `7,8` (aplicados depois de cada login)
- **Sentar** → usada para regenerar vida
- **Próximo alvo** → normalmente `TAB`
- **Inventário** → normalmente `B`

Aceita `1`–`9`, `A`–`Z`, `F1`–`F12`, `NUM0`–`NUM9`, `TAB`, `SPACE`, `ENTER`.

### Seção **Venda**

Para o teste de login você pode deixar como está. **Antes de rodar o ciclo
completo**, volte aqui e calibre a grade — instruções no fim deste guia.

### Salvar

Clique em **Salvar configuração**. Se aparecer uma lista de problemas, corrija.
Ela é chata de propósito.

Depois **feche o BlazesBot**.

---

## PASSO 6 — `4-TESTE-LOGIN.bat` ← o seu primeiro teste

Este modo faz **somente o login** e para. Não farma nada.

1. **Feche o jogo** completamente (para não confundir instâncias)
2. Dois cliques em `4-TESTE-LOGIN.bat` → **Sim** → aperte uma tecla

### O bot agora entende em que tela está

Esta é a diferença mais importante desta versão. Antes ele seguia uma
sequência fixa de cliques com esperas cegas; se algo saísse do roteiro, ele
continuava adiante achando que tinha dado certo — foi por isso que, com senha
errada, ele nem clicava no "Ok" do aviso.

Agora ele **olha a tela** a cada segundo e reage ao que realmente está lá:

| Tela | O que o bot faz |
|---|---|
| Tela de login | digita usuário e senha, clica Ok |
| **Erro de usuário/senha** | fecha o aviso e **tenta de novo** (até 3 vezes) |
| Lista de servidores | seleciona o seu servidor e confirma |
| **Conexão interrompida** | fecha o aviso e refaz de onde parou |
| **Fila de login** | apenas **espera**, sem clicar em nada |
| Seleção de personagem | clica na posição do char e em **Enter Game** |
| No mundo | lê o nome do personagem e renomeia a janela |

Não existe mais ordem assumida: se cair a conexão no meio do login, ou se a
fila aparecer antes do esperado, ele lida com isso.

Sobre a **fila**: o bot deliberadamente não clica no botão da caixa de fila — o
único que existe ali é o "Cancel", e clicar nele seria sair da fila.

Enquanto está conectado esperando, ele **verifica a cada 20 segundos** se o
botão "Enter Game" já apareceu. Se apareceu, seleciona o personagem e entra.

**Não existe limite de tempo na fila.** Fila de servidor cheio passa de três
horas em dia ruim, e qualquer limite que eu escolhesse viraria bug: o bot
desistiria no meio, reiniciaria o login e voltaria para o **fim** da fila — o
pior resultado possível. Então ele espera indefinidamente e só sai dessa espera
por um **sinal concreto**:

| Sinal | O que o bot faz |
|---|---|
| Entrou no mundo | segue para o modo da conta |
| Processo ou janela do cliente morreu | relança e reloga essa conta |
| Aviso de erro detectado na tela | trata o aviso |
| Servidor desapareceu do título | volta a preencher as credenciais |
| Você mandou parar | encerra sem fechar o jogo |

Limite de tempo existe só nas telas de **login e lista de servidores** (10
minutos), que respondem em segundos — ali, demora realmente é sintoma.

A cada 5 minutos de espera ele registra no log que continua vivo, com
diagnóstico entre colchetes:

```
Aguardando entrar há 47min. Sem limite de tempo: só saio daqui se entrar,
se aparecer erro na tela ou se o cliente cair.
[captura=nao | modal=True | fila='Server is busy...']
```

Esses campos entre colchetes me interessam: se `captura=nao` no seu caso, eles
dizem quais sinais sobram para detectar uma queda durante a fila. Se você
passar por uma queda na fila, me mande essas linhas.

Depois de logado, ele verifica **a cada minuto** se surgiu a mensagem
*"Connection interrupted, please open client again."* Quando ela aparece, o
cliente está morto mesmo com o processo vivo, então isso dispara o relogin
daquela conta: fecha, reabre e loga só ela.

Sobre a **senha errada**: depois de 3 recusas ele **para e avisa**, em vez de
ficar tentando para sempre — insistir com senha errada não resolve e só
acumula tentativas na conta.

### Saída esperada

```
[1/4] Lançando o cliente…
      OK: cliente iniciado (PID 8468)
[2/4] Aguardando a janela…
      OK: janela localizada (hwnd 1247832)
[3/4] Executando o login…
      Tela detectada: tela de login
      Preenchendo credenciais de 'blazesgamer' (tentativa 1)
      Tela detectada: lista de servidores
      Selecionando servidor 'Light in the Darkness'
      Tela detectada: fila de login
      Na fila de login. Aguardando, sem clicar em nada.
      Tela detectada: seleção de personagem
      Selecionando personagem na posição 'Center'
      Botão Enter Game localizado em (513, 731)
      Tela detectada: no mundo
[4/4] Confirmando estado…
  Personagem:  BlazesTeste
  HP:          1987 / 1987
  Posição:     (30, 17)
  Título da janela: 'BlazesTeste'

============================================================
  LOGIN CONCLUÍDO COM SUCESSO — 'BlazesTeste'
============================================================
```

O cliente fica **aberto de propósito**, para você conferir.

### Se algo não for reconhecido

Rode o `5-DETECTAR-TELA.bat`. Ele mostra ao vivo o que o bot está enxergando
enquanto você navega manualmente pelas telas:

```
tela detectada               título da janela                     ponto
------------------------------------------------------------------------
tela de login                Talisman Online | ver.6400           (535, 494)
lista de servidores          Talisman Online | ver.6400           (488, 199)
fila de login                Talisman Online | Light in t...      (514, 269)
seleção de personagem        Talisman Online | All Stars |...     (71, 739)
no mundo                     BlazesTeste                          None
```

Se alguma tela aparecer como **"desconhecida"**, me mande um print dela que eu
recorto o template.

## PASSO 7 — Só depois: o ciclo completo

Quando o login funcionar, aí sim volte ao `3-INICIAR.bat`.

### Antes: calibrar a grade de venda

É o único trabalho manual de verdade, e é o que impede o bot de vender item
bom.

Na seção **Venda**, grupo "Geometria da grade de venda":

1. No jogo, vá ao vendedor e **abra a janela de venda** com itens na bolsa
2. **Encoste a janela do jogo no canto superior esquerdo da tela** — isso evita
   confusão de coordenadas
3. `Print Screen`, cole no Paint
4. No Paint, passe o mouse sobre o **centro do primeiro slot**. As coordenadas
   aparecem no canto inferior esquerdo. Anote → `X do slot 1`, `Y do slot 1`
5. Mesma coisa no **segundo slot**. A diferença entre os X é a
   **Largura da célula**
6. Mesma coisa num slot da **linha de baixo**. A diferença entre os Y é a
   **Altura da célula**
7. Conte quantos slots cabem numa linha → **Colunas**

E defina **Vender a partir do slot**. Com `3`, os slots 1 e 2 ficam protegidos —
aparece escrito na tela para você confirmar.

### Teste a venda com bolsa de lixo

Antes de confiar:

1. Deixe na bolsa **apenas itens que você não se importa de perder**
2. Ponha algo nos slots 1 e 2 (os protegidos)
3. Rode e deixe chegar na venda
4. **Confirme que os slots 1 e 2 sobreviveram**

Se a calibração estiver errada, você descobre aqui sem perder nada.

### Rode assistindo

Jogo visível, clique em **Iniciar**, e **assista uma run inteira** do começo ao
fim antes de deixar sozinho. A aba **Log** mostra tudo.

**Como parar:** botão **Parar**, **Pausar**/**Retomar**, ou fechar a janela.

> **O jogo NÃO é fechado quando você manda parar.** O bot solta o controle e
> deixa cada cliente exatamente no estado em que estava — personagem no
> lugar, janelas abertas. Você assume dali. O cliente só é encerrado quando é
> tecnicamente necessário relançar: depois de uma queda de conexão confirmada
> ou de um travamento.

---

## Sobre a captura de imagem (importante)

O bot usa duas fontes de informação, e **ele funciona mesmo se uma faltar**:

| Fonte | O que dá | Depende de quê |
|---|---|---|
| **Memória do jogo** | HP, posição, nome do personagem | nada |
| **Título da janela** | se já conectou num servidor | nada |
| **Imagem da tela** | erro de senha, fila, avisos | captura funcionar |

A captura de imagem de um cliente DirectX **frequentemente falha** quando a
janela não está em primeiro plano: o Windows devolve um quadro totalmente
preto e ainda reporta sucesso. Por isso o login **não depende** dela para
avançar — ele segue o roteiro guiado pela memória e pelo título, e usa a
imagem só para perceber o que sai do roteiro.

**O que você ganha se a captura funcionar:** o bot reconhece sozinho erro de
senha, fila e avisos de desconexão. **O que acontece se não funcionar:** o
login ainda é feito, mas essas situações são tratadas por tempo limite em vez
de reconhecimento direto.

Para saber qual é o seu caso, rode `6-TESTE-CAPTURA.bat` com o jogo aberto. Ele
salva em `logs\` um PNG do que o bot consegue ver:

- **PNG com a imagem do jogo** → captura funciona, tudo habilitado
- **PNG todo preto** → captura indisponível

Se sair preto, vale tentar isto antes de desistir: **não deixe a janela do
BlazesBot cobrindo a janela do jogo.** O método de reserva (BitBlt) copia o que
está de fato na tela naquela região, então qualquer janela em cima atrapalha, e
janela minimizada não funciona. Arraste o BlazesBot para um lado e rode o teste
de novo.

No log do bot, se aparecer *"Sem captura de imagem desta janela"*, é isso.

---

## Várias contas ao mesmo tempo

Na seção **Cliente**, o campo **Limite de contas simultâneas** com valor **0**
significa *todas as contas marcadas como ativas*.

O bot abre **uma instância do jogo para cada conta** e faz os logins **em
paralelo** — cada conta tem sua própria thread, seu próprio cliente e seu
próprio ciclo de relogin. Se uma cair, só ela é reaberta; as outras seguem.

O único trecho que acontece um por vez é *abrir o cliente e descobrir qual
processo é dele*. Isso é necessário porque a identificação é feita comparando
os processos `client.exe` antes e depois de abrir — se dois abrissem no mesmo
instante, um bot poderia adotar a janela do outro. Leva poucos segundos por
conta, e dali em diante tudo é concorrente.

---

## Log por conta

Com várias contas rodando, um log único fica impossível de acompanhar. Na seção
**Log** há um seletor de conta:

- **"todas as contas"** mostra tudo, com o nome da conta na frente de cada linha
- escolhendo uma conta, mostra só as linhas dela, sem prefixo

O histórico é guardado inteiro, então trocar o filtro remonta a visão sem perder
nada.

---

## Reset do boss por troca de time

**O problema:** fazendo a Bewitcher Cave duas vezes seguidas sem mudar de time,
o boss **não renasce**. A instância continua com ele morto e a run seguinte é
perdida. Entrar num time novo reseta a cave.

**Como configurar**, em duas partes:

**Na conta que vai ficar parada** (a "conta de reset"):
1. Cadastre ela normalmente, **sem** marcar BC Farm
2. Em **Editar → Pet e Time**, marque **"Aceitar convites de time
   automaticamente"**

Ela vai ficar online e clicar em **Ok** sozinha sempre que receber um convite.
Não precisa fazer mais nada.

**Nas contas que farmam:**
1. Em **Editar → Pet e Time**, marque **"Trocar de time a cada run"**
2. Informe o **nick** da conta de reset
3. Deixe marcado **"Desfazer o time depois de entrar na cave"**

A cada run, o bot convida esse nick, entra na cave com o time formado e desfaz o
time em seguida — a instância nova já está criada nesse ponto, e ficar em time
atrapalharia o boss-rush solo.

---

## Comida de pet

Pet sem comida **desaparece sozinho**, e um pet que sumiu no meio da cave estraga
a run sem avisar.

Em **Editar → Teclas**, defina a tecla da comida de pet. Em **Editar → Pet e
Time**, escolha o intervalo em minutos. O bot conta o tempo decorrido desde a
última vez e alimenta em qualquer estado em que esteja — não só em pontos
específicos da rota.

---

## Quando o bot vai vender

O gatilho é **contagem de runs**, não espaço na bolsa. Em **Editar → Venda**,
o campo **"Voltar para vender a cada:"** define depois de quantas runs o bot
vai à cidade vender — atingiu esse número, ele vende.

A contagem começa em **zero a cada vez que o bot BC inicia** (cada execução)
e só conta as runs daí pra frente; quando a execução termina, volta a zero.
Por isso o número funciona como "vender a cada N runs de farm".

> **Por que não é por espaço na bolsa?** Ler a quantidade de itens da bolsa se
> mostrou **imprecisa** — o bot nunca reconhecia a bolsa cheia e, na prática,
> nunca ia vender por esse caminho. Por isso a opção por espaço está
> **desativada**: no diálogo de conta, o marcador **"Revender pelo espaço livre
> da bolsa"** aparece desmarcado e apagado. A proteção dos primeiros slots
> continua igual, só o gatilho da ida à cidade mudou.

### Poção de HP não é comprada pelo bot

Isso é deliberado. Poções têm **níveis**, e cada cidade vende só até um certo
nível — comprar automaticamente traria a poção fraca da cidade onde o bot
estiver, que cura menos. Você abastece com a poção do nível que quiser.

E é justamente para isso que serve a proteção dos primeiros slots: poções **são**
vendáveis, e deixá-las na frente da bolsa impede que o bot as venda por engano.

Poção de mana também não é comprada — o pet gera regeneração suficiente.

O bot compra apenas o **Return Charm**, o item de teleporte para a cidade.

### Como a venda funciona

A grade da janela do NPC tem **6 colunas por 4 linhas**, 24 slots. Ao tirar um
item de um slot, os seguintes **sobem** para preencher o buraco.

O bot clica repetidamente na **mesma posição N**: tudo de N para frente passa por
ali e é vendido, e os slots 1..N-1 nunca se movem — portanto nunca são tocados.
Depois clica em **Sell** e a janela fecha.

**Não há nada para calibrar.** O bot localiza a janela de venda por imagem e
calcula os slots a partir dela. A janela não aparece centralizada, então essa é a
única forma que funciona de verdade — e como a interface do jogo tem tamanho
fixo, vale em qualquer resolução.

---

## Atalhos: clique e aperte a tecla

Na aba **Teclas**, os campos não são mais listas. Clique no campo e **aperte a
tecla** que você usa no jogo — ele reconhece números, letras, F1–F12, teclado
numérico, SPACE, TAB e ENTER.

**ESC limpa o atalho** (equivale a "não usar"). É a mesma convenção do
RaaskiBot, então quem já usa o outro bot não precisa aprender nada novo.

O aviso do ESC aparece no topo da aba, num **?** ao lado de cada grupo de teclas
e no rodapé. Repetido de propósito: uma dica única passa batida, e quem não
descobre o ESC fica sem saber como remover um atalho.

---

## Outras resoluções

**Sim, funciona fora de 1024x768** — e o motivo é interessante.

Medi o mesmo recorte de imagem em prints de dimensões diferentes e ele casa com
pontuação máxima em todos. Isso quer dizer que **a interface do jogo não escala
com a resolução**: os elementos têm tamanho fixo em pixels e ficam ancorados às
bordas ou ao centro. Aumentar a resolução dá mais cenário, não uma UI maior.

Duas consequências:

1. Um recorte feito em 1024x768 **funciona em 1920x1080**. Localizar botões por
   imagem é independente de resolução.
2. O espaçamento entre elementos da mesma janela é constante. Confirmei isso: a
   distância entre o título "Server List" e o botão Ok deu **exatamente
   (+68, +334)** em dois prints de tamanhos diferentes.

Então o bot **localiza um elemento por imagem e calcula os vizinhos a partir
dele**, em vez de confiar em coordenada fixa.

### A ressalva, dita com clareza

Todos os prints que usei para medir são de **1024x768**. O modelo de ancoragem de
cada elemento foi deduzido do layout, não medido em duas resoluções diferentes.

- Em **1024x768**, os valores são idênticos aos validados em produção — verifiquei
  9 de 9 pontos batendo exatamente. Zero regressão.
- Em **outras resoluções**, é derivação de boa-fé, e o bot sempre prefere a
  posição **encontrada por imagem** quando ela existe.

Se algum clique cair no lugar errado numa resolução diferente, me mande um print
daquela tela e eu ajusto a âncora.

---

## Contas com o bot já rodando

Você não precisa parar o bot para mexer nas contas.

**Adicionar uma conta nova:** com o bot em execução, ela nasce **inativa** de
propósito. Você preenche usuário e senha com calma, configura o personagem em
**Editar**, e só então marca **Ativa** — nesse instante ela abre o jogo e faz o
login sozinha. As outras contas nem sentem.

**Desativar uma conta:** desmarque **Ativa** e só o supervisor daquela conta é
encerrado. Cada conta tem seu próprio sinal de parada, separado do global.

**Configurar antes de ligar:** o editor mostra **todas** as abas sempre, mesmo
com BC Farm desligado. Assim você prepara classe, teclas, poções e rota com
antecedência, e ao marcar BC Farm a conta já começa com os ajustes certos.

---

## Se o diagnóstico mostrar FALHA na memória

O bot lê HP, posição e nome do personagem direto da memória do cliente. Os
offsets **dentro** da struct do personagem são estáveis desde a ver.5135 — o que
muda entre versões do jogo é o **endereço estático** onde o cliente guarda o
ponteiro para essa struct.

Quando esse endereço muda, todas as leituras falham em cascata. Para resolver
sem precisar de Cheat Engine, use o **`7-DESCOBRIR-MEMORIA.bat`**:

1. Abra o jogo e **entre com o personagem**
2. Rode `7-DESCOBRIR-MEMORIA.bat`
3. Digite o **nome exato** do personagem logado
4. Ele procura o nome na memória, valida qual ocorrência é a struct do
   personagem (conferindo HP, nível e coordenadas) e mostra o endereço estático
   que aponta para ela

A saída fica assim:

```
      #      struct  nivel         HP        posicao
      1  0x1e4a2c50      1     80/80        (381, 1115)

  Candidato 1 — struct 0x1e4a2c50 (nível 1, HP 80/80, posição (381, 1115))
     ponteiro em 0x011450ec   ->   RVA 0x00d450ec
```

Confira qual candidato tem o **seu** nível, HP e posição, e coloque o RVA
correspondente em `PLAYER_BASE_RVA`, no arquivo `blazesbot/core/memory.py`.

Rode a busca duas vezes, fechando e reabrindo o jogo entre elas: o RVA que
aparecer nas duas é o estável.

---

## A interface

### Global vs. por conta — a separação importa

O que é da **máquina** fica na tela principal. O que é do **personagem** fica no
editor de cada conta.

| Onde | O que |
|---|---|
| **Contas** | lista de contas: login, senha, posição, servidor, BC Farm, Editar |
| **Cliente** | caminho do Client.bat, resolução, contas simultâneas, grade de venda |
| **Estatísticas de BC** | filtro por personagem + runs/sucesso/falhas/tempos de hoje + última run + sessão |
| **Log** | tudo que o bot está fazendo |
| **Editar** (por conta) | classe, montaria, teclas, combate, poções, rota, venda |

Faz diferença na prática: montarias têm velocidades diferentes, cada personagem
tem sua própria barra de atalhos, e há classes que nem gastam mana. Uma
configuração única para todas as contas estaria errada para quase todas.

### O editor de conta

Clique em **Editar** na linha da conta.

- Se a conta **não** está marcada como BC Farm, aparece só a aba
  **Personagem** — o resto não faz sentido para quem só vai ficar online.
- Marcando **BC Farm**, aparecem também **Teclas**, **Combate**, **Poções**,
  **Rota** e **Venda**.

### A classe filtra a tela

Escolha a classe na aba Personagem e a interface se ajusta:

| Classe | O que muda |
|---|---|
| **Wizard** | dano à distância, alto gasto de mana — limiar de mana e AoE importam |
| **Monk** | corpo a corpo com cura própria — a skill de cura ganha destaque |
| **Assassin** | não gasta mana relevante — **os campos de mana desaparecem** |
| **Fairy** | suporte com cura própria — skill de cura em primeiro lugar |
| **Tamer** | depende do pet — **as teclas de pet passam a ser obrigatórias** |

Para as classes com cura própria aparece a opção **"Preferir a skill de cura à
poção"**. Vale marcar: poção é recurso comprado, skill custa só mana e recarga.

### Montaria por velocidade, não por nível

Em vez de "+7 a +12", agora se escolhe a **velocidade**: de **90% a 150%**, de 10
em 10. Existem montarias fora da progressão comum, e o que o bot precisa saber é
a velocidade — é ela que escala o tempo de espera de cada trecho da rota.

### Tudo que tem valores conhecidos é lista de seleção

Teclas, classe, velocidade de montaria, servidor, posição, tempo de luta,
intervalos: todos são listas. Digitar nome de tecla à mão só gera erro difícil de
achar depois. Sobram campos numéricos apenas onde não existe conjunto fechado de
opções — como a geometria da grade de venda, que é medida em pixels.

---

## Se o diagnóstico mostrar FALHA na memória

O bot lê HP, posição e nome do personagem direto da memória do cliente. Os
offsets **dentro** da struct do personagem são estáveis desde a ver.5135 — o que
muda entre versões do jogo é o **endereço estático** onde o cliente guarda o
ponteiro para essa struct.

Quando esse endereço muda, todas as leituras falham em cascata. Para resolver
sem precisar de Cheat Engine, use o **`7-DESCOBRIR-MEMORIA.bat`**:

1. Abra o jogo e **entre com o personagem**
2. Rode `7-DESCOBRIR-MEMORIA.bat`
3. Digite o **nome exato** do personagem logado
4. Ele procura o nome na memória, valida qual ocorrência é a struct do
   personagem (conferindo HP, nível e coordenadas) e mostra o endereço estático
   que aponta para ela

A saída fica assim:

```
      #      struct  nivel         HP        posicao
      1  0x1e4a2c50      1     80/80        (381, 1115)

  Candidato 1 — struct 0x1e4a2c50 (nível 1, HP 80/80, posição (381, 1115))
     ponteiro em 0x011450ec   ->   RVA 0x00d450ec
```

Confira qual candidato tem o **seu** nível, HP e posição, e coloque o RVA
correspondente em `PLAYER_BASE_RVA`, no arquivo `blazesbot/core/memory.py`.

Rode a busca duas vezes, fechando e reabrindo o jogo entre elas: o RVA que
aparecer nas duas é o estável.

---

## A interface, seção por seção

A navegação fica na coluna da esquerda. Tudo que você altera vale **na hora**,
mesmo com o bot rodando — não existe botão de salvar.

| Seção | O que tem |
|---|---|
| **Contas** | login, senha, posição, servidor e a caixa **BC Farm** |
| **Cliente** | caminho do Client.bat, resolução, contas simultâneas, montaria |
| **Teclas** | skills, utilidades e poções — inclusive as **de batalha** |
| **Combate** | boss, intervalo entre skills, AoE, cura na segunda fase |
| **Poções** | limiares em barras coloridas, normais e de batalha |
| **Rota** | padrão ou segura, atrair poderosos, retorno à cidade |
| **Venda** | slot inicial, recompra, calibração da grade |
| **Estatísticas de BC** | filtro por personagem + runs/sucesso/falhas/tempos de hoje + última run + sessão |
| **Log** | tudo que o bot está fazendo |

### Poções normais e de batalha

O jogo tem **dois conjuntos de poções** — as normais e as "de batalha", que são
itens diferentes com recarga própria. O bot usa as de batalha quando está em
combate e as normais quando está fora dele. Usar a de batalha fora do combate
desperdiça um item caro, e o inverso pode simplesmente não funcionar.

Cada uma tem seu próprio limiar na seção **Poções**.

### Rota padrão ou segura

- **Padrão** — vai direto ao boss, sem atacar nenhum mob do caminho. Bem mais
  rápida, e é o desenho do bot.
- **Segura** — mata as Gun Witches do caminho antes de encostar no boss. Mais
  lenta, mas evita chegar na luta com vida baixa. Vale enquanto o personagem
  não aguenta o boss folgado.

### Estatísticas de BC

Refere-se só à boss-rush. A página mostra os dados de **uma personagem por
vez**: um seletor no topo lista os **nicks** (sem a conta) de quem tem pelo
menos uma run registrada hoje ou na sessão, já com a de mais runs selecionada;
trocar a seleção atualiza os cartões na hora. Contas que nunca rodaram não
aparecem.

Os cartões de cima mostram, para a personagem escolhida:
- **Hoje** (persistido, sobrevive ao fechar o bot): runs, sucesso, falhas,
  taxa de sucesso, tempo médio e o total de tempo das runs.
- **Última run**: o tempo até o boss da última run do dia é persistido a cada
  run nova (só o da última, substituído a cada uma) e sobrevive ao fechar o
  bot; o total dessa run vem da sessão.
- **Sessão**: runs desta execução e o resultado ok/falhas.

A tabela de baixo traz os **dias anteriores** dessa mesma personagem, para
comparar o progresso do dia atual com os da semana.

**Sucesso** é uma run em que o boss caiu. **Falha** é qualquer run que terminou
sem isso — morte, travamento ou queda de run. A proporção entre as duas é o
melhor sinal de que a configuração está boa ou de que algo precisa de ajuste.

---

## Problemas comuns

### `ModuleNotFoundError: No module named 'psutil'` (ou qualquer outro)

Era o problema da versão antiga. Solução:

1. Apague a pasta `.venv`, se existir
2. Rode `1-INSTALAR.bat` de novo
3. Confirme que as 8 linhas de verificação deram `[ ok ]`

Se ainda acontecer, rode `1-INSTALAR.bat` e me mande a saída inteira.

### "python não é reconhecido como comando"

O PATH não foi configurado. Reinstale o Python marcando
`Add python.exe to PATH`, ou abra o instalador já baixado → **Modify** → Next →
marque **Add Python to environment variables** → Install. Reinicie depois.

### Abre a Microsoft Store quando eu rodo

Windows tem um atalho falso do Python. `Configurações` → `Aplicativos` →
`Configurações avançadas de aplicativo` → `Aliases de execução de aplicativo` →
**desligue** `python.exe` e `python3.exe`.

### Falha ao criar o `.venv`

Pasta em local protegido ou sincronizado. Mova tudo para `C:\BlazesBot`.

### O bot abre mas nada acontece no jogo

Em ordem de probabilidade:

1. **Não está como administrador** — o sintoma silencioso do UIPI
2. Jogo não está em **1024x768**
3. Jogo em tela cheia em vez de janela
4. Minimapa recolhido ou fora da posição padrão

### Log fica preso em "tela desconhecida" e o bot não faz nada

Era um bug da versão anterior, corrigido. O reconhecimento tinha se tornado
100% dependente de captura de imagem — e sem imagem, o bot não reconhecia nada
e nunca agia. Agora o login avança pelo roteiro mesmo sem imagem.

Se ainda acontecer, rode `6-TESTE-CAPTURA.bat` e me mande a saída.

### Log diz "a linha não ficou realçada" mas o servidor está certo

Era ruído da verificação, não erro de seleção. Eu conferia se **uma linha
específica** estava realçada, o que é sensível a poucos pixels de
desalinhamento entre a coordenada medida e a captura real.

Agora o bot **descobre qual linha está realçada** e compara com a esperada.
Tolera ±8 pixels de desalinhamento, e quando erra ele diz qual servidor ficou
selecionado por engano:

```
Está selecionado 'Light in the Darkness' em vez de 'White Horse [NEW]';
clicando de novo
```

### Entrou no servidor errado

Corrigido. A lista de servidores mudou de 7 para 5 nomes (houve fusão), e as
coordenadas antigas apontavam para as linhas erradas. Agora as posições são
calculadas a partir da ordem da lista, e o bot confirma o realce azul antes de
confirmar.

Se a lista mudar de novo no futuro, é só reordenar `server_rows` em
`blazesbot/core/coords.py`.

### O botão Pausar não parava o bot

Corrigido. A pausa só era verificada dentro de `tick()`, e as sequências disparam
vários cliques e teclas entre um tick e outro — o login inteiro, por exemplo, não
passava por tick nenhum. Então clicar em Pausar não impedia o bot de continuar
agindo até a sequência terminar.

Agora a pausa é verificada **no ponto onde o input é enviado**. Pausado significa
literalmente que nenhuma tecla e nenhum clique saem. Testado: com a pausa ativa,
zero comandos enviados; ao liberar, retoma de onde parou.

### Travava em avisos de servidor ocupado ou falha de conexão

Foram acrescentados dois avisos que apareciam e travavam o login:

| Aviso | Botão | O que o bot faz |
|---|---|---|
| "Login server is busy now, please try again." | **Ok** | fecha e repete, **sem contar como senha errada** |
| "Connection failed, please try again later." | **Cancel** | fecha e repete |

O detalhe do segundo importa: ele tem botão **Cancel**, não Ok. Clicar na posição
do Ok das outras caixas não fecharia nada.

E o primeiro não é erro de credencial — contar como senha errada faria o bot
desistir de uma conta boa depois de três avisos do servidor.

### Reabre o cliente se travar na tela de login

Se o bot ficar **5 minutos** na tela de usuário e senha sem avançar, ele encerra
o cliente e reabre. Essa tela responde em segundos; ficar ali minutos significa
que o cliente travou num estado do qual não sai por clique, e reabrir é mais
rápido que insistir.

### Clica fora dos campos quando o jogo não está em 1024x768

Corrigido — e a causa foi um erro meu de prioridade.

Com o jogo em **1280x960**, o bot localizou o campo de usuário por imagem em
`(756, 488)`, que estava **correto**. Mas eu havia posto uma "rede de segurança"
que comparava esse valor com a coordenada de **1024x768** (o que a configuração
dizia) e descartava o valor certo em favor do errado.

Duas correções:

1. **A resolução vem da janela, não da configuração.** O bot mede a área de
   cliente com a mesma chamada que o diagnóstico usa, e loga o valor todas as
   vezes. Se a configuração disser uma coisa e o jogo estiver em outra, quem
   manda é o jogo. Você não precisa mais acertar esse campo.
2. **O que foi encontrado na tela vale mais que o calculado.** A verificação
   agora só descarta a âncora em caso de desvio absurdo (acima de 60 px), o que
   indicaria template casando no lugar errado — e não simples diferença de
   resolução.

No log você verá, a cada login:

```
Área de cliente da janela: 1280x960  (fora de 1024x768: coordenadas derivadas por ancoragem)
```

Testado em 1024x768, 1280x960, 1920x1080 e 800x600: em todos, a distância entre
os campos de usuário e senha sai correta em 30 px, e em 1024x768 os valores são
exatamente os validados em produção.

### Apaga o usuário e digita a senha no lugar, em laço infinito

Corrigido. A causa era um erro sutil na captura de tela que a mudança de
resolução expôs.

A função de captura pedia um contexto gráfico da **janela inteira** — barra de
título e bordas incluídas — mas dimensionava a imagem pela **área de cliente**.
Resultado: a imagem capturada continha a barra de título no topo, e todo o
conteúdo do jogo aparecia **cerca de 28 px deslocado para baixo**.

Esse deslocamento não atrapalhava quando a pergunta era só "este elemento está
na tela?". Mas passou a atrapalhar quando o bot começou a **calcular coordenadas
a partir de elementos localizados**: o clique saía 28 px abaixo do alvo. E como
os campos de usuário e senha ficam a **30 px** um do outro, o clique da senha
caía dentro do campo de usuário — o foco não mudava, os backspaces apagavam o
usuário e a senha era digitada ali. Daí o laço.

Três correções:

1. **A captura recorta a área de cliente de verdade.** PrintWindow captura a
   janela inteira e o recorte é feito depois; BitBlt usa um contexto que já tem
   origem na área de cliente.
2. **Rede de segurança:** na resolução validada, se a coordenada derivada por
   imagem divergir mais de 12 px da medida em produção, o bot usa a medida e
   avisa no log. Um erro desse tipo não passa mais silencioso.
3. **A limpeza do campo de senha foi limitada** a 16 backspaces em vez de 50. Se
   por qualquer motivo o foco não mudar, o estrago fica contido.

O `6-TESTE-CAPTURA.bat` agora mostra o deslocamento detectado, para conferência.

### O editor só mostrava algumas abas

Corrigido. As abas de farm ficavam escondidas quando a conta estava marcada
apenas para login — o que impedia justamente o que faz sentido: configurar o
personagem com calma **antes** de ligar o farm. Agora todas as abas aparecem
sempre.

### Os campos da tabela de contas apareciam cortados

Corrigido. As linhas da tabela usavam a altura padrão, que é menor que os campos
de senha e as listas de seleção — ao clicar, o campo aparecia pela metade. A
altura agora é fixada em 40 px e as colunas têm larguras próprias.

### Derruba contas paradas ("jogo congelado")

Corrigido, e a regra mudou de vez: **personagem parado não é personagem
desconectado**.

A detecção antiga concluía "congelado" quando posição e HP ficavam iguais por um
tempo. Isso está errado neste jogo — é normal deixar um personagem paradinho
por horas com a loja pessoal aberta, sem andar e sem tomar dano. Pior: quando a
leitura de memória falha, os valores nunca "mudam", e a conta caía em loop.

Agora só existem três motivos para religar, todos inequívocos:

1. O processo do cliente não existe mais
2. A janela do cliente não existe mais
3. O aviso **"Connection interrupted"** está na tela

Nada de inatividade, e o flag de modal na memória não derruba mais a conta por
si só (ele é compartilhado com caixas de confirmação legítimas).

### Não clica no Ok do aviso de conexão interrompida

Corrigido. A causa era a **ordem** de verificação: o bot testava primeiro se era
a tela de personagens e só depois se havia aviso. Como o aviso aparece **sobre**
a tela de personagens e sobre a lista de servidores, o template de "Create Char"
casava, o bot concluía "seleção de personagem" e o aviso nunca era fechado —
ficava clicando atrás de uma caixa modal que bloqueava tudo.

Agora os avisos são testados **antes** das telas de fundo. Verificado nos seis
cenários: aviso sobre personagens, aviso sobre servidores, e as quatro telas
limpas.

### Loga certo e poucos segundos depois fecha e reabre o jogo

Corrigido, e era o pior bug até aqui. O código exigia ler o **nome do
personagem** da memória para considerar o login concluído. Quando essa leitura
falhava — mesmo com a posição e o HP legíveis, ou seja, com o personagem
comprovadamente no mundo — ele tratava isso como **falha de login**, e o
supervisor então **matava um cliente perfeitamente logado** e começava do zero.

Agora o login nunca falha por causa disso. Se o nome não vier, o bot avisa no
log e usa o login da conta para batizar a janela:

```
No mundo (posição (381, 1115)), mas não consegui ler o nome do personagem
na memória. Usando o login da conta para batizar a janela.
Isso não impede o login nem o farm.
```

A leitura do nome também ficou mais teimosa: lê 50 bytes em vez de 64 (ler além
do necessário pode cruzar o fim de uma página de memória e falhar por inteiro),
tenta tamanhos menores se falhar, e percorre quatro caminhos diferentes antes de
desistir.

### O personagem sai andando pelo mapa depois de logar

Corrigido, e a causa vale conhecer. O bot só sabe que entrou no mundo se
conseguir **confirmar** — e a confirmação anterior exigia ler **duas** coisas
da memória ao mesmo tempo (nome do personagem *e* posição). Se apenas uma
falhasse, ele concluía que ainda não tinha entrado e continuava clicando em
"Enter Game". Já dentro do jogo, esses cliques caem no chão e o personagem
caminha até lá.

Três correções:

1. Basta **qualquer um** dos sinais de memória (nome, posição ou HP) para
   confirmar a entrada, em vez de exigir todos
2. Foi acrescentada confirmação **por imagem**: barra de ação e abas de chat só
   existem dentro do jogo
3. Depois de **4 tentativas** sem confirmar, o bot **para de clicar** e avisa no
   log em vez de continuar arrastando o personagem

Se você vir esse aviso no log, rode `2-DIAGNOSTICO.bat` e `6-TESTE-CAPTURA.bat`
— ele significa que nem a memória nem a imagem estão disponíveis, e isso
também impediria o bot de BC de funcionar.

### Fica na tela de personagens sem clicar em nada

Corrigido. Era um efeito colateral da captura instável: o bot capturava a tela
duas vezes para a mesma decisão, e quando a segunda captura falhava, ele
desistia de clicar — e repetia isso para sempre. Agora ele reaproveita a
mesma captura e **nunca sai sem agir**: se encontrar o botão na imagem clica
nele, se não encontrar usa a coordenada conhecida.

### O login digita no lugar errado

Coordenadas de tela. Confirme resolução 1024x768 e modo janela.

### O login não passa da tela de senha

Confira usuário e senha na aba Contas. O bot detecta erro de login e tenta 3
vezes antes de desistir — se o log disser "credenciais rejeitadas", é senha
errada mesmo.

### Trava esperando a fila

A detecção de fila usa reconhecimento de imagem do botão "Cancel" da janela de
fila (`data\templates\cancel.bmp`, arquivo original do T-R0XX). Se a sua tela
de fila for diferente, me avise que eu ajusto o template.

---

## Onde ficam os arquivos

| Caminho | O que é |
|---|---|
| `data\config.json` | sua configuração (senhas cifradas) |
| `data\templates\` | imagens de referência |
| `logs\blazesbot.log` | histórico completo — é isto que você me manda |
| `.venv\` | o Python isolado. Não mexa |

**Não compartilhe o `config.json`.** As senhas são cifradas com uma chave da
sua conta do Windows, então o arquivo não funcionaria na máquina de outra
pessoa. Cada um monta a própria configuração.

---

## Resumo de bolso

```
1. Instalar Python  (marcar "Add python.exe to PATH")  ->  reiniciar o PC
2. Extrair em C:\BlazesBot
3. 1-INSTALAR.bat                      (sem admin, uma vez só)
4. Abrir jogo + logar -> 2-DIAGNOSTICO.bat
5. 3-INICIAR.bat -> abas Geral/Contas/Teclas -> Salvar -> fechar
6. Fechar o jogo -> 4-TESTE-LOGIN.bat        <- SEU PRIMEIRO TESTE
7. Só depois: calibrar venda -> testar venda com lixo -> ciclo completo
```

Qualquer erro: cole a mensagem e o `logs\blazesbot.log`.
