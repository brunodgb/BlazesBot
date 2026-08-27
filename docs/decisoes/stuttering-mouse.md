# Stuttering do Mouse Físico — Evolução da Solução

**Data inicial**: 2026-08-14  
**Problema relatado**: Cursor físico do usuário apresenta stuttering (micro-travadas, teleportes de poucos pixels) quando o bot BC está rodando.

---

## Diagnóstico

### Sintomas Observados
- Stuttering constante com alta frequência
- Pior quando cursor está em **outras janelas** (não sobre o jogo)
- 1 conta BC ativa com milhares de cliques/segundo
- "Teleportes" de poucos pixels = perda de eventos de mouse

### Causa Raiz 1: Bloqueio do Message Loop
`SendMessageW` é uma chamada **BLOQUEANTE**:
1. Bloqueia a thread do bot até o WndProc do jogo responder
2. Durante o bloqueio, o Windows **atrasa o processamento de eventos do cursor físico**
3. Com milhares de cliques/segundo, o message loop do Windows fica **congestionado**

**Resultado**: Mouse físico perde eventos → stuttering visível.

### Causa Raiz 2: Cursor Físico Interfere nos Cliques do Bot
Quando cursor físico está sobre a janela do jogo durante um clique do bot:
- O jogo lê a posição do cursor físico via `GetCursorPos()`
- O clique acontece na posição física, não na posição programada
- Com cursor em movimento: ~5-10% de falha nos cliques

---

## Evolução das Soluções

> **CORRIGIDO EM 18/08/2026 — LEIA O FIM DESTE ARQUIVO ANTES DE USAR ESTE
> BLOCO.** A conclusão registrada aqui ("PostMessage não é confiável para
> coordenadas de clique") é FALSA. Os dois testes de PostMessage mandavam os
> BOTÕES por `SendMessageW`, que fura a fila e chega antes do move postado --
> eles garantiam a inversão que os reprovou. PostMessage PURO só foi testado em
> 18/08/2026, e passou 20/20.

### ❌ TESTE 1: PostMessage Híbrido (FALHOU — pelo motivo errado)
**Estratégia**: `PostMessageW` para WM_MOUSEMOVE (assíncrono), `SendMessageW` para botões.

**Resultado**: "Clique parcial" — botões visualmente pressionados mas ações não executam.

**Causa**: WM_MOUSEMOVE assíncrono não garante que chegou antes do botão → clique acontece na posição antiga.

**Decisão**: Abandonado. PostMessage não é confiável para coordenadas de clique.

---

### ✅ TESTE 2: SendMessage Rápido (SUCESSO)
**Estratégia**: Manter `SendMessageW` (síncrono, confiável) mas reduzir `time.sleep()` entre down/up.

**Mudança**: 
- ANTES: `time.sleep(jitter(0.03, 0.4))` = 18-42ms
- AGORA: `time.sleep(0.001)` = 1ms fixo

**Resultado**:
- ✅ Stuttering FORA da janela do jogo: **ELIMINADO** (redução 96% do bloqueio)
- ✅ Cliques funcionam 100%
- ✅ Nenhuma regressão funcional

**Status**: Implementado, modo ativo padrão: `MODO_DE_CLIQUE = "sendmessage_rapido"`

**Arquivo**: `blazesbot/core/inputs.py`, método `_click_sendmessage_rapido()`

---

### ✅ TESTE 3: Mouse Shield (SOLUÇÃO ATUAL)

**Problema**: cursor físico sobre a janela do jogo interfere nos cliques do bot.

**Estratégia**: hook externo `WH_MOUSE_LL` no processo do BOT (não injeta nada
no jogo) que engole o MOVIMENTO físico durante os cliques.

**Arquivo**: `blazesbot/core/mouse_shield.py` + `USAR_MOUSE_SHIELD = True`.

---

#### MEDIÇÃO DE 18/08/2026 — `blazesbot/bot/teste_do_cursor.py`

20 cliques por condição, na janela real, alvo a 760-980 px do cursor físico.

**Com o cursor PARADO sobre a janela:** 20/20 nas duas condições.

**Com o cursor EM MOVIMENTO sobre a janela** -- e é esta que decide:

| condição | acertos | personagem ANDOU |
|---|---|---|
| sem shield | **1/20 (5%)** | **14 de 20** |
| com shield | **20/20 (100%)** | **0** |
| reafirmando a coordenada, sem shield | 4/20 (20%) | 11 de 20 |

#### A PRIMEIRA MEDIÇÃO ESTAVA ERRADA POR 20×, E O ERRO ERA DA MÉTRICA

As primeiras corridas deram 19-20/20 sem shield, e este documento chegou a
registrar "95-98%". **Era falso.** A métrica automática perguntava "o minimapa
mudou?", e ela é CEGA para o pior desfecho: o clique que cai na cena 3D faz o
personagem ANDAR, e o personagem andando TAMBÉM muda o minimapa. Clique errado
contava como acerto.

Quem viu o defeito foi o USUÁRIO, na tela -- "várias vezes meu personagem andou"
-- não o número. A ferramenta passou a conferir a POSIÇÃO a cada clique: andou
⇒ errou o alvo, por mais que a imagem tenha mudado. A taxa real sem shield caiu
de 95% para **5%**.

Lição, e vale além deste caso: **uma métrica que confunde "mudou" com "mudou
pelo motivo certo" mede o próprio defeito como se fosse sucesso.** O sinal foi
observação humana contra número automático, e o humano estava certo.

#### O QUE ISSO MUDA NA CLASSIFICAÇÃO DO SHIELD

Ele não é "melhora a taxa" nem "tradeoff proteção vs fluidez". **Sem ele o bot
é inutilizável enquanto o usuário mexe o mouse sobre a janela do jogo** -- 5% de
acerto -- e o desfecho não é clique perdido, é o personagem SAIR DO LUGAR, o
problema que o `CLAUDE.md` persegue em cinco pontos diferentes. Com 5 contas em
paralelo e o usuário usando o computador, isso acontece o tempo todo.

#### O QUE A MEDIÇÃO DERRUBOU

**`GetCursorPos` não é o caminho.** Com o cursor PARADO a 780 px do alvo, 20 de
20 cliques acertaram. Se o jogo lesse a posição do cursor, os 20 teriam caído
onde o mouse estava. **Foi essa afirmação, que este documento sustentava, que
motivou a DLL do TESTE 4** -- ela hookeava `GetCursorPos`, ou seja a função
errada, e é por isso que "funcionou em laboratório e falhou em produção".

O mecanismo compatível com TODOS os dados: o jogo usa a posição que ele mesmo
rastreia pelas mensagens `WM_MOUSEMOVE`. O `_prime_cursor` do bot escreve essa
posição; um `WM_MOUSEMOVE` FÍSICO chegando no meio a sobrescreve, e o clique sai
onde o mouse do usuário está. Com o mouse parado não há evento físico, e por
isso parado sempre funcionou.

*(Nota: os dados NÃO separam "o jogo honra o lParam do botão" de "o jogo honra a
posição que o prime acabou de escrever" -- com o mouse parado as duas hipóteses
dão o mesmo resultado. A distinção não muda nenhuma decisão, mas não deve ser
afirmada sem medir.)*

#### O QUE NÃO FUNCIONA — reafirmar a coordenada (medido, não deduzido)

Parecia a correção óbvia e sem hook: reafirmar `WM_MOUSEMOVE` entre o down e o
up, para o up cair onde o down caiu. **É PIOR que não fazer nada** -- 12/20 (60%)
e 17/20 (85%) em duas corridas, contra 19-20/20 sem tratamento.

O motivo é o `wParam`: o move extra vai com `MK_LBUTTON`, que significa "o mouse
moveu COM O BOTÃO APERTADO" -- a definição de arrasto. Em vez de impedir o
arrasto, ele FABRICA um em todo clique; numa das corridas o jogo travou nesse
estado por seis cliques seguidos, com diferença de imagem 0,00.

Vale para os DOIS caminhos que fazem isso, ambos marcados `NÃO LIGAR` no
`inputs.py`: `sendmessage_repetido` (que já existia) e
`sendmessage_rapido_reafirmado` (escrito para este teste).

#### O TEMPO DE BLOQUEIO É 80 ms, E É NÚMERO MEDIDO

Evolução: 50 → 100 → 150 → 15 → **80**. O 15 ms foi CALCULADO ("o clique dura
~5 ms, 3x de margem basta") e reprovou na prática -- o movimento físico passava
por baixo. O usuário ajustou para 80 na mão. Por meses o documento e o docstring
disseram 15 enquanto o código fazia 80.

O preço é assumido e conferido: durante os 80 ms o mouse do usuário para de
responder **dentro da janela do jogo**. Fora dela, nada muda.

#### O CUSTO POR EVENTO — o que foi consertado em 18/08/2026

Um `WH_MOUSE_LL` roda no caminho crítico de TODO evento de mouse do sistema.
A versão anterior, a cada evento, chamava `WindowFromPoint` (chamada entre
processos) e disputava um lock global -- era esse o "micro-stutter" que o
documento aceitava como tradeoff. Pior: o lock era o MESMO que a instalação
segurava enquanto dormia até 1 s esperando o hook subir, e acima de ~300 ms o
Windows DESINSTALA o hook em silêncio (`LowLevelHooksTimeout`).

Reescrito com três decisões, medido em **0,6 µs por evento** fora de clique:

1. a primeira pergunta é uma comparação de float ("algum bloqueio ativo?"), e o
   caso comum devolve ali, sem Win32 e sem lock;
2. nenhum lock no callback -- ele só LÊ, e leitura de `dict`/float é atômica;
3. retângulo da janela em CACHE, lido na thread do bot. De quebra some um
   defeito: `WindowFromPoint` devolve a janela-FILHA sob o cursor, que num
   cliente que renderiza em child window nunca bateria com o hwnd guardado.

E só o MOVIMENTO é engolido: clique e roda do usuário passam sempre, porque não
mexem a posição e portanto não criam o arrasto.

---

### ❌ TESTE 4: Cursor Hook DLL (ABANDONADO — 2026-08-16)
**Estratégia**: Injeção de DLL no processo do jogo + hook inline de `GetCursorPos`.

**Como Funciona**:
1. `cursor_hook.dll` injetada no `client.exe`
2. Hook inline intercepta `GetCursorPos()` dentro do jogo
3. Durante cliques do bot: jogo "vê" cursor na posição programada
4. Cursor físico completamente ignorado pelo jogo

**Resultado**:
- Mesmo com os hooks instalados (status SIM/SIM, injeção ok), o resultado em
  produção continuou problemático. O hook inline em `GetCursorPos` não cobria
  todos os caminhos que o jogo usa para ler o cursor, deixando falhas quando o
  jogo resolve a posição por outro módulo/path.
- O usuário confirmou que o ORIGINAL, `SendMessageW` síncrono, era o que
  funcionava.

**Decisão**: A DLL foi **ABANDONADA** e todo o código/binários foram removidos
do repositório em 2026-08-16. O Mouse Shield (TESTE 3) continua como solução
padrão. Documentação completa em `docs/decisoes/dll-cursor-hook.md`.

---

## Hierarquia de Soluções (Estado Atual)

```
1. MOUSE SHIELD (TESTE 3)
   - Se USAR_MOUSE_SHIELD = True
   - Eficácia: 95-98% (quase perfeito)
   - Invasão: Baixa (hook externo)
   ↓ fallback se shield falhar ou desativado

2. SEM PROTEÇÃO (TESTE 2)
   - Sempre disponível
   - Eficácia: SendMessage rápido funciona, mas cursor físico interfere
   - Invasão: Zero
```

---

## Medição de Sucesso

### Linha Base (ANTES — sendmessage com 30ms)
- Stuttering fora da janela: constante, alta frequência
- Teleportes: visíveis (poucos pixels)
- Cliques com cursor sobre janela: interferência total
- Taxa de entrada da cave: 78% (baseline)

### TESTE 2 (sendmessage_rapido, 1ms)
- ✅ Stuttering fora da janela: **ELIMINADO**
- ✅ Teleportes fora da janela: ausentes
- ⚠️ Cliques com cursor sobre janela: interferência permanece
- ✅ Taxa de entrada da cave: 78% (sem regressão)

### TESTE 3 (Mouse Shield, 150ms)
- ✅ Stuttering fora da janela: ausente (mantido)
- ✅ Cliques com cursor parado sobre janela: 100%
- ⚠️ Cliques com cursor em movimento sobre janela: 95-98%
- ⚠️ Micro-stutters dentro da janela: perceptíveis (tradeoff)

### TESTE 4 (DLL) — ABANDONADO
- ✅ Stuttering: ausente
- ✅ Cliques com cursor em movimento: 100% (quando funcionava)
- ⚠️ Comportamento estranho: possível (teleportes de cursor)
- ✅ Taxa de entrada da cave: ≥78% (sem regressão)
- ❌ **Problema**: hook incompleto — jogo lê cursor por caminhos não hookeados
- **Status**: ABANDONADO, código removido em 2026-08-16

---

## Alternativas Descartadas

1. **Reduzir cadência de cliques**: Quebraria navegação medida (`INTERVALO_RECLIQUE`, `MARGEM_RECLIQUE`)
2. **PostMessage total**: Cliques parciais (WM_MOUSEMOVE assíncrono não garante ordem)
3. **Async/await total**: Reescrita de 80% da base, sem garantia de resolver
4. **Thread pool maior**: Problema não é CPU, é bloqueio de I/O Win32
5. **Mover cursor físico**: Multi-contas roubam cursor umas das outras (PROIBIDO no projeto)
6. **DLL de cursor (TESTE 4)**: Abandonada — hook incompleto, código removido

---

## Conclusão

**Mouse Shield (TESTE 3) é a solução final, agora com medição própria.**
- Cursor parado: 20/20. Cursor em movimento: 20/20, com o personagem NUNCA
  saindo do lugar — contra 1/20 e 14 andadas sem ele.
- Não é tradeoff: fora da janela do jogo o custo é de **0,6 µs por evento**, e
  dentro dela o bloqueio dura o tempo REAL do clique (~5 ms medidos), porque o
  `liberar()` o solta no `finally`. Os 80 ms viraram TETO, pago só quando a
  thread do bot é preemptada no meio do clique.
- A DLL (TESTE 4) foi abandonada e removida — consulte `docs/decisoes/dll-cursor-hook.md`



---

## 18/08/2026 — auditoria de I/O de mouse: o que sobrou

Pedido: encontrar hook mal feito ou "input flooding" que sequestre a fila de
eventos do SO e engasgue o mouse físico.

### O EIXO DA ESCRITA NÃO SE APLICA — e o motivo é estrutural

Auditado por AST, não por leitura: **não existe `SendInput`, `mouse_event` nem
`SetCursorPos` em `core/inputs.py`.** Todo clique do bot vai por `SendMessageW`
direto ao WndProc do jogo.

`SendMessageW` **não passa pela fila de raw input do sistema** — ele chama o
WndProc da janela alvo. Então o bot **não tem como afogar o barramento do
mouse**: ele não injeta nada nesse caminho. A hipótese de "milhares de
`mouse_event` por segundo saturando a fila" não descreve este código.

O que o lado da escrita já causou de stuttering foi outra coisa, e está
resolvido: `SendMessageW` é BLOQUEANTE, e o `time.sleep(jitter(0.03))` entre down
e up prendia a thread por 18-42 ms por clique, atrasando o processamento dos
eventos do cursor. O TESTE 2 cortou para 1 ms e o stuttering fora da janela foi
eliminado (registrado acima).

Travado por `tests/test_hook_do_mouse_nao_vive_para_sempre.py`, que lê o AST de
`inputs.py` — o arquivo CITA `SendInput` no cabeçalho para explicar por que não o
usa, e um teste por texto reprovaria por causa do comentário.

### O EIXO DA LEITURA: um hook, correto, e vivo demais

Só existe **um** hook global no projeto (`WH_MOUSE_LL`, em
`core/mouse_shield.py`). Não há `pynput`, não há hook de teclado, e **não há
polling de `GetCursorPos`** em produção — as ocorrências são todas em comentário
ou na ferramenta temporária `bot/teste_do_cursor.py`.

O hook é necessário e está medido (sem ele: 1/20, com o personagem ANDANDO em 14
dos 20 cliques). O callback já está em **0,602 µs por evento** com o bot ocioso,
remedido nesta auditoria.

**O que estava errado: nada desinstalava o hook.** Ele era instalado na criação
do primeiro `Input` e vivia até o processo morrer — **inclusive com o bot
parado**. O usuário parava o bot na interface, ia usar o computador, e cada
evento de mouse do sistema continuava sendo marshalado para o nosso processo,
esperando o callback voltar. Mesmo a 0,6 µs, um hook de baixo nível força essa
travessia por evento, e com o bot parado ela não compra nada.

`BotManager.stop()` agora chama `_soltar_o_mouse_do_usuario()`.

**A desinstalação é ADIADA, e isso é o ponto delicado:** `stop()` apenas
SINALIZA a parada, e as threads das contas podem estar no meio de um clique.
Arrancar o hook ali deixaria justamente esse clique sem proteção — o pior momento
possível. Então quem desinstala é uma thread daemon que espera as contas
terminarem (`join`, teto de 20 s). Rodar isso na thread do chamador travaria a
interface no clique de Parar.

Reinstalar é automático: o `Iniciar` seguinte cria `Input` novo → `MouseShield` →
hook. Isso depende do conserto do `uninstall_hook` feito no mesmo dia (ele
deixava `_hook_thread` preenchido, e `_ensure_hook_installed` retornava de
imediato para sempre — o shield nunca voltava, em silêncio).

### Veredito

O stuttering **do lado da escrita** foi neutralizado no TESTE 2 e não volta pelo
caminho da fila do SO, porque o bot não escreve nela. O custo **do lado da
leitura** está em 0,6 µs por evento durante a operação e passa a ser **zero com o
bot parado**. Nenhuma mudança na mecânica do clique: `MODO_DE_CLIQUE` segue em
`sendmessage_rapido`, a rajada de clique direito segue em 2 × 22 ms, e o teto do
bloqueio segue em 80 ms com `liberar()` no `finally`.


---

## 18/08/2026 — PostMessage PURO: 20/20, com e sem shield

### O que estava errado na conclusão de agosto

Os dois experimentos rotulados "PostMessage" (`postmessage_hibrido` e
`postmessage_com_delay`) **nunca usaram PostMessage no clique.** Os dois mandam
os botões por `SendMessageW`:

    PostMessageW(WM_MOUSEMOVE)  -> vai para a FILA, processado quando o jogo bombeia
    SendMessageW(down)          -> FURA A FILA, chama o WndProc na hora

O botão chegava **antes** do move. O sintoma registrado — *"o clique acontece na
posição antiga"* — é exatamente essa inversão, e o `postmessage_hibrido` a
produzia enquanto o próprio docstring dele afirmava que os botões síncronos
"garantem ordem correta".

Ou seja: o que foi testado e reprovado foi **misturar os dois mecanismos**, que é
a única combinação que não pode funcionar. A conclusão *"PostMessage é instável
com este jogo. Descartado."* não se sustentava.

### A medição, com o mouse do usuário EM MOVIMENTO sobre a janela

| fase | acertos | personagem ANDOU |
|---|---|---|
| SEM shield (`sendmessage_rapido`) | 6/20 (30%) | 14 |
| **COM shield — o padrão de hoje** | **16/20 (80%)** | **4** |
| REAFIRMADO — controle negativo | 9/20 (45%) | 11 |
| **PostMessage puro + shield** | **20/20 (100%)** | **0** |
| **PostMessage puro SEM shield** | **20/20 (100%)** | **0** |

**O controle negativo validou a corrida.** A fase "reafirmado" está medida como
ruim (fabrica arrasto); ela reprovou em 45%, então a medição estava separando as
coisas. Numa corrida em que tudo desse alto, ela é o que denunciaria que a
medição parou de medir — o resumo aborta o veredito se ela passar.

**O padrão ficou em 16/20 nesta corrida**, contra 20/20 nas anteriores. Ou o
mouse foi mexido mais agressivamente, ou o 20/20 era otimista. De um jeito ou de
outro, a barra que o PostMessage enfrentou foi mais dura que a das corridas
anteriores, e ele passou nas duas variantes.

### Por que PostMessage puro funciona onde o híbrido falhava

Mensagens **postadas** na mesma fila saem em FIFO. Com as quatro postadas e
nenhuma furando a fila, a ordem que o jogo vê é a que se mandou. E um
`WM_MOUSEMOVE` físico que chegue no meio **entra na fila**, atrás das nossas —
não fura. É por isso que o shield deixa de ser necessário: o mecanismo que ele
protegia (furar a ordem) não existe mais.

### O prêmio maior não é o stuttering

`PostMessageW` **não bloqueia**. Isso elimina um defeito aberto e documentado:
`SendMessageW` não tem timeout, então um cliente que para de bombear mensagens —
o cenário do "Connection interrupted", que este bot detecta — prende a thread
daquela conta **para sempre**. O `finally` do shield não roda, o
`watchdog.check()` que dispararia o relogin nunca é alcançado, e a conta morre em
silêncio dizendo "Rodando".

### O que a medição NÃO cobre

Honestidade sobre o alcance, antes de qualquer troca em produção:

- **Só clique ESQUERDO, num botão de UI.** A produção usa clique DIREITO para
  NPC, Altar Stone, saída da cave e movimento — e a rajada manda 2 cliques com
  22 ms entre eles. Com PostMessage eles entram na fila; não foi medido.
- **Não cobre a abertura de DIÁLOGO**, que é a métrica historicamente frágil (os
  78% / 14% do clique no link foram medidos com SendMessage).
- **20 cliques por fase.** 20/20 contra 16/20 é p≈0,11 por Fisher — "não é pior"
  está estabelecido para o critério combinado (100% e zero andadas), "é melhor"
  não está.
- **Perde-se a confirmação implícita**: `SendMessageW` só retorna depois de o
  WndProc rodar. Custo aceito pelo usuário; o projeto já não confia nela (a regra
  é conferir o efeito por imagem e repetir).


### CORREÇÃO no mesmo dia: as duas fases de PostMessage eram o MESMO teste

`block_momentarily()` e `liberar()` só eram chamados dentro de
`_click_sendmessage_rapido`. O `_click_postmessage_puro` **não tocava no
shield** — então na fase rotulada "PostMessage + shield" o hook estava
instalado e **nunca engolia evento nenhum**.

As duas fases mediram a mesma coisa. O resultado correto é **40/40 para
PostMessage com o mouse físico inteiramente LIVRE**, e a comparação entre ter e
não ter shield com PostMessage **nunca havia sido feita**.

### E a produção corrigiu o laboratório

Rodando sem shield, o usuário observou: *"ainda tem vezes que acaba não clicando
todas as vezes se eu mexo o mouse na janela do jogo"* — melhor que SendMessage,
mas não perfeito. Observação de produção supera medição de escopo menor: o teste
usa só clique ESQUERDO num botão de UI, em 20 amostras por fase.

`_click_postmessage_puro` passou a engajar o shield, e `USAR_MOUSE_SHIELD` voltou
para `True`.

### O shield no caminho postado NÃO é solto no fim

No caminho síncrono, `liberar()` é possível porque **o retorno do `SendMessageW`
é prova de que o WndProc rodou** — o bloqueio já não serve para nada.

Com PostMessage não existe essa prova. As quatro mensagens ficam na FILA até o
jogo bombear. Soltar logo depois de postar liberaria o mouse físico **antes** de
o jogo processar o que acabamos de enfileirar, e um `WM_MOUSEMOVE` físico nessa
janela é processado ANTES do nosso botão — exatamente a falha que o shield existe
para impedir.

Então aqui o bloqueio **expira sozinho** por `TETO_DO_BLOQUEIO_MS`: ele deixa de
ser teto e volta a ser gasto. É o preço de não ter confirmação, e o usuário paga
em milissegundos de mouse preso **dentro da janela do jogo**.

Travado por dois testes que leem o AST (`test_hook_do_mouse_nao_vive_para_sempre`):
o caminho postado tem que CHAMAR `block_momentarily`, e não pode chamar
`liberar()` nem `SendMessageW` — este último reintroduziria a inversão de fila
que reprovou os dois híbridos de agosto.


### E o shield saiu de novo — agora por MECANISMO, não por medição

Testadas as duas configurações em produção, o usuário decidiu desligar o shield
com PostMessage: *"por ser assíncrono ele não funciona como quando usa o
SendMessage"*. A observação está certa e explica a assimetria:

| | intervalo a proteger | prova de fim | custo real |
|---|---|---|---|
| `sendmessage_rapido` | do prime ao up, **conhecido** | o retorno do `SendMessageW` | ~5 ms (teto de 80) |
| `postmessage_puro` | até o jogo bombear, **desconhecido** | não existe | 80 ms cheios |

No caminho síncrono o shield protege um intervalo delimitado, e o `liberar()` no
`finally` transforma os 80 ms de teto em ~5 ms de gasto. No caminho postado não
há intervalo delimitado nem sinal de fim: o bloqueio vira um chute de 80 ms que
pode terminar antes ou depois da hora, **cobrando o preço cheio sem entregar a
proteção precisa**.

Estado atual: `MODO_DE_CLIQUE = "postmessage_puro"`, `USAR_MOUSE_SHIELD = False`.
**Não existe hook global nenhum no processo.**

### O que fica em aberto, e não vai ser chutado

Com PostMessage e sem shield ainda há perda ocasional de clique quando o usuário
mexe o mouse sobre a janela — melhor que SendMessage, não perfeito. **A causa não
está explicada.**

O que se sabe: não é ordem entre as nossas mensagens (todas postadas, FIFO), não
é `GetCursorPos` (medido), e o shield não resolve (testado). O que sobra como
hipótese não medida é o jogo processar o move físico da fila entre o nosso move e
o nosso botão -- mas nesse caso o shield deveria ter ajudado, e não ajudou.

Próximo passo honesto seria instrumentar o que o jogo REALMENTE recebe, não
tentar mais uma variante às cegas. Três variantes já foram testadas assim nesta
investigação e duas custaram dias.

**ATENÇÃO ao reverter para `sendmessage_rapido`:** ele exige
`USAR_MOUSE_SHIELD = True`. SendMessage sem shield deu **6/20** com o mouse em
movimento, o pior resultado de toda a investigação. Os dois andam juntos.


---

## 19/08/2026 — INSTRUMENTAÇÃO: o que o jogo recebe e quando processa

`blazesbot/bot/instrumentar_clique.py` (`14-INSTRUMENTAR-CLIQUE.bat`), 3 modos x
40 cliques, com o mouse do usuário em movimento contínuo (~2,4 eventos/ms).

| modo | thread presa | post -> efeito | TOTAL | acertos |
|---|---|---|---|---|
| `postmessage_puro` | **2,5 ms** | 103,3 ms | **105,8 ms** | **39/40** |
| `postmessage_puro` + shield | 2,6 ms | 86,7 ms | 89,3 ms | 37/40 |
| `sendmessage_rapido` + shield | **111,8 ms** | 17,7 ms | 129,5 ms | 37/40 |

### 1. `SendMessageW` prende a thread por 112 ms, não por 5

Este arquivo vinha estimando ~5 ms de bloqueio por clique. **É 112 ms** — 45x
mais. O motivo está nos próprios dados: `SendMessageW` entre processos espera a
thread do jogo processar, e ela está ocupada mastigando a enxurrada de eventos do
mouse físico.

Consequência para o bot, não só para o mouse: na venda os cliques saem a cada
65 ms. Com o usuário mexendo o mouse, cada um custaria 112 ms de thread -- a
sequência inteira rodaria a **um terço da velocidade**.

### 2. PostMessage é mais rápido de ponta a ponta

105,8 ms contra 129,5 ms, apesar da latência maior até o efeito. A latência do
PostMessage é a nossa mensagem esperando na fila **atrás dos eventos físicos**, e
a prova é a fase com shield: bloqueando os físicos, a mediana cai de 103 para
87 ms e o pior caso de 297 para 133 ms.

### 3. O mouse físico NÃO causa as falhas restantes

| modo | moves/ms nos ACERTOS | nos PERDIDOS |
|---|---|---|
| `postmessage_puro` | 2,44 | 2,34 |
| `sendmessage_rapido` + shield | 4,15 | 2,23 |

Iguais -- e no SendMessage os perdidos tiveram MENOS movimento que os acertos. A
hipótese que sobrava depois de eliminar `GetCursorPos` e a ordem das mensagens
acaba de cair também.

**ARMADILHA DE LEITURA, e ela quase enganou:** a contagem BRUTA de eventos nos
cliques perdidos é ~10x maior (2200-2800 contra 200-300) e parece causa óbvia.
Não é: nos perdidos a sonda roda o teto de 1,2 s e nos bons ela para no efeito
(~0,1 s). Normalizada, a taxa é a mesma. A ferramenta passou a reportar
**moves/ms** justamente por isso -- é a terceira vez nesta investigação que uma
métrica não normalizada quase produz a conclusão errada.

### 4. A decisão, e o que o shield entrega

`MODO_DE_CLIQUE = "postmessage_puro"` com `USAR_MOUSE_SHIELD = False`. É a
configuração com mais acertos (39/40), com a thread livre e o mouse do usuário
livre.

O shield entrega **latência menor** (87 contra 106 ms) e **zero ganho de
confiabilidade** (37/40 contra 39/40 -- empate estatístico), cobrando 80 ms do
mouse do usuário por clique. Não compensa. Se um dia a latência virar o gargalo,
ele é o botão para isso -- e aí o número dele deve cobrir a latência medida
(~103 ms de mediana, 297 no pior caso), não os 80 ms de hoje, que expiram ANTES
de o jogo processar.

### 5. O que continua sem explicação

~2,5% de cliques perdidos, em TODOS os modos, sem correlação com o mouse. Não é
`GetCursorPos`, não é ordem das nossas mensagens, não é o mouse físico, e o
shield não resolve. As falhas são espalhadas no tempo, não agrupadas.

O que NÃO foi descartado ainda: o jogo descartar mensagem com a fila saturada, e
a própria sonda perder a mudança. Quem for atrás disso tem o JSON evento a evento
em `logs/instrumentacao/`.
