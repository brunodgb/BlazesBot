# BlazesBot — contexto para continuar o desenvolvimento

Cole este arquivo inteiro no início da conversa no Claude Code. Ele contém tudo
que foi descoberto até aqui, por que cada decisão foi tomada, e o que falta.

---

## 1. O que é o projeto

Bot de **boss-rush da Bewitcher Cave** para o MMORPG **Talisman Online**,
servidor oficial, cliente **ver.6400**. Python 3.12, Windows, roda como
administrador.

O bot ignora todos os mobs da cave: entra, atravessa até o boss
(**Blaze Skull Marshal**), mata, se cura, sai e repete. Quando a bolsa fica com
pouco espaço livre volta à cidade, vende o excedente e compra Return Charm. Faz
auto-login e relogin sozinho, com várias contas em paralelo.

**Estado atual: o auto-login funciona bem. A rota dentro da cave ainda não foi
testada de ponta a ponta.**

---

## 2. Restrições que não podem ser violadas

Estas surgiram de erros reais e custaram tempo. Não as reverta.

**O bot NUNCA fecha o cliente do jogo.** A fila de login passa de três horas em
dia cheio. Fechar uma janela logada custa uma tarde de testes. Se algo dá errado,
o bot avisa e tenta de novo na mesma janela. A única exceção é quando o próprio
jogo se fecha sozinho — aí não há janela com que trabalhar.

**Roda obrigatoriamente como administrador.** O jogo roda elevado, e o Windows
aplica UIPI: um processo de integridade média não consegue enviar mensagens de
janela nem ler a memória de um processo elevado — **e faz isso sem gerar erro**.
O sintoma é o pior possível: tudo parece funcionar e nada acontece.

**Sem memória legível, o bot não farma.** O farm lê HP, posição e alvo a cada
decisão. Sem essas leituras ele repete ações no vazio — invocar pet sete vezes,
montar e desmontar em loop. Existe um portão em `supervisor._operate` que mantém
a conta online e recusa farmar enquanto `memory.critical_ok()` for falso.

**A pausa bloqueia no envio de input, não nos laços.** Verificar só em `tick()`
não funcionava: as sequências disparam vários cliques entre um tick e outro, e o
login inteiro não passava por tick nenhum.

---

## 3. Descobertas técnicas que sustentam tudo

### 3.1 Ponteiro base da memória

```
PLAYER_BASE_RVA = 0x00D4514C      # ver.6400, em blazesbot/core/memory.py
PLAYER_BASE     = 0x0114514C      # = IMAGE_BASE (0x400000) + RVA
```

Confirmado em **dois clientes simultâneos**, com personagens de nível 1 e 65 e
resoluções diferentes: os dois apontaram para o mesmo RVA. Histórico das
versões: `0x00D1EB80` (5135), `0x00D450EC` (6139), `0x00D4514C` (6400).

Os **offsets internos da struct são estáveis desde a 5135** — só o endereço base
se move entre versões. Quando o jogo atualizar, use
`7-DESCOBRIR-MEMORIA.bat`: ele procura o nome do personagem na memória, valida
o candidato por HP/nível/coordenadas e mostra o novo RVA.

Offsets principais, a partir de `[PLAYER_BASE]`:

| Campo | Offset | Observação |
|---|---|---|
| nome | `0xBC` | string |
| HP | `0x3B8` | |
| HP máx (base) | `0xDC` | somar buff `0xE0` e % `0xE4` |
| MP | `0x3BC` | |
| X | `0x810` | float, **dividir por 20** |
| Y | `0x814` | float, **dividir por 20** |
| em combate | `0x854` | |
| sentado | `0x290` | valor 200 |
| montado | `0x8B0` | |
| pet ativo | `0x10A8` | |

Endereços estáticos úteis:

```
0x012CE35C   modal na tela (DC, erro de login, confirmação — é contextual)
0x0106D328 + 0x3D8   tamanho do time   (o offset é obrigatório)
0x012CE2DC → [0x18,0x8C,0x3C] + 0x64   1º resultado do Surroundings
```

O último é valioso: a string tem o formato `text="Nome [x,y]"`, ou seja, dá para
**conferir** o resultado da busca antes de clicar nele.

### 3.2 A interface do jogo não escala com a resolução

Medi o mesmo recorte contra prints de dimensões diferentes: casa com pontuação
**1.000** em todos. Os elementos têm **tamanho fixo em pixels** e são ancorados
às bordas ou ao centro. Aumentar a resolução dá mais cenário, não uma UI maior.

Duas consequências:

1. Um template recortado em 1024x768 **funciona em 1920x1080**.
2. O espaçamento entre elementos da mesma janela é constante. Confirmado: a
   distância do título "Server List" até o botão Ok deu **exatamente (+68,+334)**
   em dois prints de tamanhos diferentes.

Por isso o bot **localiza um elemento por imagem e calcula os vizinhos a partir
dele** (`TEMPLATE_ANCHORS` em `core/coords.py`), em vez de confiar em coordenada
absoluta.

**A resolução vem da janela medida, nunca da configuração.** Um bug real: a
configuração dizia 1024x768, o jogo estava em 1280x960, e o clique da senha caía
no campo de usuário.

### 3.3 Armadilha da captura de tela

`GetWindowDC` devolve contexto da **janela inteira**, com barra de título. Se o
bitmap é dimensionado pela área de cliente e desenhado a partir dessa origem, o
conteúdo aparece **~28 px deslocado para baixo**. Isso não atrapalha "o elemento
está na tela?", mas estraga qualquer coordenada derivada — e como os campos de
usuário e senha ficam a 30 px um do outro, o clique caía no campo errado.

Correção em `core/vision.py`: `PrintWindow` captura a janela inteira e o recorte
da área de cliente vem depois; `BitBlt` usa `GetDC`, cujo contexto já nasce na
área de cliente.

`PrintWindow` também **retorna sucesso mesmo produzindo quadro preto**. Por isso
a validação é pelo conteúdo (`frame_is_blank`), não pelo código de retorno.

---

## 4. Como o bot anda

Três meios, escolhidos pela distância. Detalhes completos em `NAVEGACAO.md`.

**Mapa-múndi (tecla M)** — acima de 50 unidades. Cada região tem `centre` (a
coordenada no meio da tela) e `scale` (unidades por pixel):

```
pixel_x = largura/2 + (centre_x - alvo_x) / scale_x     # scale_x é negativo
pixel_y = altura/2  + (centre_y - alvo_y) / scale_y
```

Dados em `core/zones.py`, 12 regiões e 109 locais, vindos do GhostBot. A região
da cave é `vast_mountain`: centro `(989,-489)`, escala `(-1.38, 1.38)`.

Se outro jogador está no ponto exato, o jogo **recusa** o caminho — por isso o
bot tenta 9 pontos vizinhos.

**Minimapa** — ajuste fino. **1.7 pixels por unidade** (não é 1:1), máximo de
**30 px** do centro. Centro em `(919,115)` a 1024x768, ancorado no canto
superior direito.

**Surroundings** — teleporte por nome, o mais robusto quando o destino tem nome.

---

## 5. O caminho real até a cave

Descoberto por prints do jogo. **Não é coordenada, é uma sequência de NPCs.**

```
1. Surroundings -> aba NPC -> buscar "Fay"
   => "Transport Fay [178,-518]"   (Stone City)
2. Clicar no resultado -> caminha até o NPC
3. Clique DIREITO no NPC -> janela Dialogue
4. Na lista "Transport to", clicar em "Ghost Din Woods"
   (custa 7 moedas, exige nível 48)  => teleporta
5. Surroundings -> aba NPC -> buscar "Skull"
   => "Skull Herald [1395,-636]"   (Vast Mountain)
6. Clicar no resultado -> caminha até o NPC
7. Clique DIREITO -> Dialogue
8. Clicar no link "Enter Bewitcher Cave"  => entra
```

Três detalhes que quebram tudo se esquecidos:

- **A lista abre na aba "Player".** Os NPCs só aparecem depois de clicar na aba
  **NPC**.
- **Os links do diálogo mudam de posição** conforme o texto do NPC. São
  localizados por template próprio (`link_ghost_din_woods.png`,
  `link_enter_bc.png`), não por deslocamento.
- **Interação com NPC é botão DIREITO.**

Implementado em `blazesbot/bot/ui_service.py`.

---

## 6. Estrutura do código

```
main.py                    entrada; modos --check, --detect, --capture-test,
                           --login-test, --find-base, --headless
blazesbot/
  config.py                configuração em 3 níveis (ver abaixo)
  core/
    memory.py              leitura de memória e mapa de offsets
    inputs.py              teclado e mouse via SendMessage, com jitter
    coords.py              pontos de tela ancorados + TEMPLATE_ANCHORS
    zones.py               regiões do mapa-múndi e conversões
    vision.py              captura de janela e template matching
    secrets.py             senha cifrada com DPAPI
    stats_diarias.py       histórico diário de runs por conta (7 dias)
  bot/
    context.py             contexto compartilhado, GameState, RunStats
    watchdog.py            detecção de queda
    navigation.py          mapa-múndi + minimapa + Surroundings
    ui_service.py          painel de arredores e diálogos de NPC
    team.py                reset do boss por troca de time
    combat.py              luta, cura, pet, buffs
    vendor.py              venda a partir do slot X, Return Charm
    routine.py             máquina de estados do boss-rush
    login.py               auto-login por fases
    login_states.py        detecção de tela em camadas
    supervisor.py          ciclo de vida: janela, login, operação, relogin
  tools/find_base.py       descoberta do ponteiro base
data/templates/            recortes de tela usados no reconhecimento
data/stats_diarias.json    histórico diário de runs por conta (gerado em runtime)
```

### Configuração em três níveis

A separação segue a pergunta *"isto muda quando eu trocar de cave?"*:

1. **Máquina** (`BotConfig`) — Client.bat, contas simultâneas
2. **Personagem** (`AccountSettings`) — montaria, teclas, pet, poções
3. **Atividade** (`BCConfig`) — boss, rota, reset de time, venda

Quando entrarem outras caves, cada uma ganha o próprio bloco ao lado de `bc`,
sem tocar nos dois primeiros níveis.

---

## 7. Decisões de projeto e o porquê

**Venda por geometria, não por lista de itens.** A grade do NPC tem 6 colunas ×
4 linhas. Ao tirar um item, os seguintes **sobem**. Clicar repetidamente na mesma
posição N drena tudo de N para frente e nunca toca nos slots anteriores. Os bots
de referência usam ~200 templates de ícone de lixo; a proteção geométrica é
melhor porque o padrão é **preservar**, não vender.

**O gatilho de vender é o espaço livre na bolsa, não a contagem de runs.** O bot
conhece a capacidade total porque o usuário informa quantas bolsas de expansão
tem (`BagConfig.bolsas`); sem isso seria impossível (depende de quais Expand
Bags estão `Permanent` em vez de `Expired`, só se descobre lendo a tela). A
opção antiga de "voltar a cada N runs" foi removida — basta o espaço livre.

**Poção de HP não é comprada pelo bot.** Poções têm níveis e cada cidade vende
até um nível. Comprar automaticamente traria a poção fraca da cidade onde o bot
estiver. É por isso que a proteção dos primeiros slots existe: poções **são**
vendáveis.

**Sem seleção de classe.** Filtrar campos por classe atrapalhava: o Wizard se
cura com a Super Skill, então esconder "cura" para quem não é Fairy tirava a
opção mais útil dele.

**A cura depois do boss é uma sequência específica:** poção → Super Skill →
sentar, em rajada rápida. Assim as duas curas correm ao mesmo tempo, e sentar
amplifica a regeneração de HP e mana.

**Pet a cada 50 minutos.** Cada comida dá 5 de felicidade, o máximo é 100, e o
pet perde 1 a cada 10 minutos. Sem liga/desliga: com farm ativo o pet é
obrigatório.

**Reset do boss por troca de time.** Fazendo a cave duas vezes seguidas sem mudar
de time, o boss **não renasce**. Uma conta parada com "aceitar convites"
resolve. O convite é enviado registrando o nick na **Block list** da janela de
amigos — é o único jeito de mirar alguém que está longe.

Quatro detalhes do fluxo, todos aprendidos com erro:

* O time é montado **só ao chegar na coordenada da entrada**, nunca antes. O
  caminho até lá passa por teleporte e caminhada automática, e mexer na Block
  list longe da porta não adianta nada.
* A Block list é **conferida antes de mexer**: se o nick do reseter já é a
  primeira linha, nada é removido. Remover e re-adicionar em toda run gastava
  cliques numa janela modal e foi o que fez o texto do convite cair dentro do
  campo de nick.
* O time é **mantido durante todas as tentativas de entrada** e desfeito só
  depois de confirmar que está dentro. A BC é disputada: uma tentativa pode não
  pegar, e a instância nova (que é o que o reset produz) só existe quando a
  entrada dá certo.
* Sair do time é pelo **menu do retrato** (clique direito no rosto, canto
  superior esquerdo, "Leave the team"). Comando de chat não serve: o cliente
  responde "You speak too fast" e o texto aparece para os outros jogadores.

**Quem convidou? Pelo anúncio interno, não por OCR.** A conta de reset vê
"[Nick] invite you to join the team" e precisa recusar convite de estranho —
entrar no time de um desconhecido quebra o reset das contas de verdade. Ler esse
nick exigiria OCR. Como todos os supervisores rodam **no mesmo processo**, a
conta que farma simplesmente ANUNCIA que convidou (`team.anunciar_convite`), e a
conta de reset consulta o anúncio. Sem anúncio recente → Cancel. Como segunda
camada, o bot guarda o recorte do "[Nick]" na primeira vez e compara nas
seguintes, o que cobre a corrida de um estranho convidar no mesmo instante. Se
nenhuma conta desta execução usa este personagem como reseter (a outra pode
estar em outra máquina), não há o que verificar e ele aceita — recusar tudo
tornaria esse arranjo impossível.

**Não usamos `write_position`.** Os bots de referência teleportam escrevendo as
coordenadas na memória. Funciona, mas movimento client-side é validável
server-side de forma trivial e retroativa. O bot anda de verdade.

**O NICK identifica a janela, e é gravado em disco.** O cliente dá o mesmo título
a todas as instâncias, então o bot renomeia a janela com o nick do personagem. Só
que o nick vinha da memória e vivia apenas em memória: fechar o bot apagava a
pista, e na volta ele abria um cliente NOVO para uma conta que já estava online —
de volta para a fila de três horas. Agora `AccountSupervisor._gravar_personagem`
grava no `config.json` (`Account.last_char_name`) assim que o nome é lido, e o
campo **Nick do meu personagem** permite preencher à mão na primeira vez. A ordem
de autoridade é sempre **memória > nick guardado > login**; nome vazio nunca
apaga o que já está lá, porque a leitura falha legitimamente enquanto o mundo
carrega. Há uma segunda chance de leitura depois do login (na espera pela
memória), justamente para o caso em que o mundo ainda estava carregando quando o
login terminou.

**Todos os delays têm jitter.** Padrão perfeitamente regular é assinatura óbvia.

### 7.1 Auditoria do bot de referência (T-R0XX)

Analisado em 2026-08-07: `G:\Desktop\T-R0XX Auto Login 1024x768 [New Server]\extraido`
(sistema de login automático, fonte descompactada de PyInstaller). Conclusão:
**não há nada a absorver** — o que valia a pena já foi incorporado, e o BlazesBot
está à frente justamente onde o T-R0XX é fraco.

O que o T-R0XX faz: dispara os clientes e detecta o PID novo por diff do
`psutil`; por conta, acha a janela pelo PID e clica nos campos com
**coordenadas fixas 1024×768**; detecta erro/queda de login por **ponteiro de
memória absoluto** (`LOGIN_ERROR_POINTER`) e re-tenta recursivamente; lê o nome
do char e renomeia a janela.

Já absorvido (e melhorado):
- Input por `SendMessageW` no hwnd com priming `WM_SETCURSOR`/`WM_MOUSEMOVE` —
  `core/inputs.py` usa a mesma técnica e o docstring do `_prime_cursor` credita
  o T-R0XX. O BlazesBot acrescenta jitter, mais teclas (NUM, setas, DELETE) e
  leitura da área de cliente por `GetClientRect`.
- Renomear a janela com o nome do char (`Input.set_title`), fila, erro de login,
  nome lido da memória — tudo já coberto.

Único candidato real, **não adotado**: checar **erro de login por ponteiro de
memória** (1 byte, determinístico) em vez de template. Por quê não: o ponteiro é
absoluto e específico do cliente do T-R0XX ("New Server", ver.6xxx); o BlazesBot
é ver.6400 (`PLAYER_BASE_RVA 0x00D4514C`) e precisaria re-derivar o ponteiro por
sondagem de memória. E `login_states.py` é de propósito em camadas
(memória → título → imagem) porque sinal único falha. Revisitar só se um dia a
sondagem da ver6400 achar um flag estável e ele provar valor em campo.

Onde o T-R0XX é pior (não copiar):
- Resolução fixa 1024×768 com coords hardcoded; o BlazesBot aceita todas as
  resoluções (ancoragem por template + `coords.py`).
- Senhas em texto puro no `accounts.json`; o BlazesBot usa DPAPI.
- Sem variação de timing nos cliques; o BlazesBot aplica jitter.
- Detecção de tela por template isolado; o BlazesBot usa camadas.

---

## 8. Bugs já corrigidos — não reintroduza

| Bug | Causa | Correção |
|---|---|---|
| Login em laço, apagava o usuário | captura deslocada 28 px | recorte correto da área de cliente |
| Clique fora dos campos fora de 1024x768 | confiava na resolução da configuração | mede a janela |
| Rede de segurança descartava a âncora certa | comparava com a resolução errada | encontrado > calculado |
| `RecursionError` no primeiro clique | substituição automática pegou a chamada interna | `self.input.left_click` |
| Pausar não parava | verificava só em `tick()` | bloqueia no envio de input |
| Fechava cliente logado | exigia ler o nome para concluir o login | nunca falha por isso |
| Derrubava conta parada | detecção por inatividade | removida |
| Não clicava no Ok de avisos | ordem de detecção | avisos antes das telas de fundo |
| `cancel.bmp` dava falso positivo | também casa com a lista de servidores | template exclusivo |
| Abria vários clientes | adoção gulosa de cliente livre | virou opção, desligada |
| Comportamento errático no farm | agia sem confirmar resultado | portão de memória |
| Abria cliente novo para conta já logada | o nick só existia em memória: a janela era batizada com ele, mas o `config.json` guardava string vazia | `_gravar_personagem` grava no arquivo a cada login; campo editável à mão |
| `--login-test` e `--detect` quebravam | `run_login_test` e `run_detect` eram chamados mas nunca definidos | implementados; o teste de login reusa o supervisor de produção |
| Conta de reset nunca aceitava convite | o template `state_team_invite.png` foi recortado **com o nick do remetente dentro** — só casava com convite daquele personagem | `state_team_invite_texto.png`, só a parte invariante do texto |
| `/invite Nick` digitado dentro da caixinha da Block list | o convite era enviado por chat enquanto a janela modal ainda estava aberta, e o ENTER + texto caíam no campo de nick | `_fechar_janelas` confirma por imagem que a caixa e a lista fecharam antes de qualquer digitação |
| Removia e re-adicionava a Block list em toda run | não havia como saber o que estava escrito na linha | recorte aprendido: confere primeiro, só remove se não for o nick certo |
| Saía do time por comando de chat | `/leaveteam` não é comando: virava fala pública e o cliente reclamava | menu do retrato (clique direito no rosto) → "Leave the team" |
| Uma tentativa só de entrar na cave | a BC é disputada e a tentativa pode não pegar | laço de até 3 min conferindo a localização, com o time mantido |

---

## 9. O que falta

**Prioridade 1 — testar a rota dentro da cave.** O caminho até a entrada foi
reescrito com os NPCs reais e não foi testado. Os 38 waypoints do `altar_path`
vieram do T-R0XX e são de outra época; provavelmente precisam ser refeitos.

**Prioridade 2 — validar a venda.** A geometria foi medida num print, mas o
ciclo completo (viajar, abrir NPC, vender, comprar) não rodou.

**Prioridade 3 — reset de time.** O fluxo foi reescrito com o comportamento
correto (registro na Block list só na porta da cave, conferência antes de
remover, time mantido até entrar, saída pelo menu do retrato, convite recusado
quando não é de uma conta nossa). Falta testar no jogo, e duas coisas dependem
disso:

* **De onde sai o convite.** Hoje é o comando `/invite <nick>`, que é o único
  caminho com prova: o cliente responde "Your invitation sent out, please wait
  for the reply.". Na aba Block só há Block/Remove/Options, e o Team Up da aba
  Friends miraria a lista errada. Se existir um caminho de janela (menu de
  contexto na entrada da Block list, por exemplo), ele é preferível.
* **O template `menu_leave_team.png`.** Sem ele o bot clica num deslocamento
  medido em print, que funciona mas depende de o menu ter sempre o mesmo
  tamanho. Recortar o item "Leave the team" resolve de vez.

Falta também confirmar o nome que o jogo mostra na localização dentro da
instância. O bot aceita qualquer nome que contenha "bewitcher" ou "cave", e
avisa no log com WARNING quando encontra um nome que não reconhece — é por ali
que se descobre o valor real.

**Depois:** outras caves. A configuração já está preparada para isso.

---

## 10. Como testar

```
1-INSTALAR.bat        uma vez, sem admin
2-DIAGNOSTICO.bat     confere a memória em todos os clientes
3-INICIAR-WEB.bat     interface (web)
4-TESTE-LOGIN.bat     só o login
5-DETECTAR-TELA.bat   mostra ao vivo qual tela o bot reconhece
6-TESTE-CAPTURA.bat   salva PNG do que o bot enxerga
7-DESCOBRIR-MEMORIA.bat  acha o ponteiro base
```

O log é gravado sempre em `logs\sessao-atual.log` e `logs\blazesbot.log`, em
nível detalhado. **Peça sempre esse arquivo antes de diagnosticar qualquer
coisa** — houve um caso em que o bot não fez nada e não gerou log, e sem registro
o diagnóstico virou adivinhação.

---

## 11. Estilo do código

Comentários em **português**, explicando o **porquê** e não o quê. Onde uma
decisão parece estranha, o comentário conta o problema que ela resolve — vários
"detalhes" aqui custaram horas de depuração e o comentário é o que impede
alguém de "simplificar" de volta para o bug.

Nomes de variáveis e funções em português nas partes novas; o código herdado
mantém os nomes originais.

Antes de mudar comportamento de segurança (fechar cliente, detecção de queda,
proteção da venda), releia a seção 2 e a tabela da seção 8.
