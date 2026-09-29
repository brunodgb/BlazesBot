# BlazesBot v1.0

Bot de **boss-rush da Bewitcher Cave** para Talisman Online (servidor oficial).

Ignora toda a cave e todos os mobs do caminho: entra, monta, atravessa até o
Secret Altar, teleporta para o esconderijo do boss, mata o **Blaze Skull
Marshal**, recupera vida, sai e repete. Quando a bolsa enche, vai ao vendedor,
vende a partir do slot que você escolher, recompra poções e volta.

Relogin automático quando o servidor cai, com reativação obrigatória do pet.

---

## ⚠️ Leia isto antes de qualquer coisa

**1. O bot PRECISA rodar como administrador.** Não é preferência.

O jogo roda elevado, e o Windows aplica UIPI (isolamento de privilégio de
interface). Um processo de integridade média não consegue enviar mensagens de
janela para um processo elevado, nem abrir handle da memória dele. E faz isso
**sem gerar erro** — as mensagens são descartadas em silêncio. O sintoma é o
pior possível para diagnosticar: o bot "roda", não reclama de nada, e
simplesmente não acontece nada no jogo.

**2. Rode `--check` antes do primeiro uso.** É o diagnóstico que confirma se o
mapa de memória vale para a sua versão do cliente.

**3. Calibre a grade de venda.** Os valores padrão de `cell_w`, `cell_h` e
`columns` são estimativas. Um erro aqui faz o bot clicar no slot errado — e o
único item que você não quer vender é justamente o que está nos primeiros
slots. Detalhes em "Calibração".

**4. Use uma conta descartável nos primeiros testes.** Não a principal.

---

## Instalação

Requer **Python 3.11+** e **Windows**.

```bat
pip install -r requirements.txt
```

Jogo em **1024x768**, modo janela: `System > Graphics > Screen Size`. É a única
resolução com coordenadas validadas.

---

## Primeiros passos, em ordem

### 1. Diagnóstico de memória

Abra o jogo, **entre com um personagem** e então:

```bat
python main.py --check
```

Saída esperada:

```
  [ ok  ] Nome do personagem     = WizzOfBlazes
  [ ok  ] HP                     = 1987
  [ ok  ] Posição (X, Y)         = (30, 17)
  ...
DIAGNÓSTICO: mapa de memória 100% válido nesta versão do cliente.
```

Se os campos críticos falharem, veja "Quando o jogo atualizar".

### 2. Configuração

```bat
python main.py
```

Preencha, na ordem das abas:

**Geral** — caminho do `Client.bat`, nível da montaria (+7 a +12), contas
simultâneas.

**Contas** — login, senha, posição do personagem na tela de seleção
(Left/Center/Right) e servidor. Senhas são cifradas com DPAPI do Windows.

A coluna **Personagem** é o nick que identifica a janela do jogo daquela conta.
Se você já tem os clientes abertos e logados, preencha à mão — o bot então
reconhece cada janela e assume o controle **sem abrir outro cliente e sem voltar
para a fila de login**. A partir do primeiro login o campo se mantém sozinho: o
bot lê o nome na memória, renomeia a janela com ele e grava no `config.json`.

**Teclas** — as teclas **da sua barra de atalhos**. É o bot que pressiona; você
só declara quais são. Skills de ataque são usadas em rotação, na ordem em que
você escrever (`1,2,3`).

**Combate** — intervalo entre skills, limiares de poção, tempo máximo de luta.

**Venda e Compra** — o slot inicial de venda e a geometria da grade.

### 3. Teste supervisionado

Rode com o jogo visível e **assista à primeira run inteira**. Não deixe
sozinho antes de ver um ciclo completo funcionar.

---

## Como funciona a venda a partir do slot X

Este era o requisito mais delicado — vender lixo sem vender item bom — e a
solução é geométrica, não heurística.

A janela de venda do NPC lista **apenas itens vendáveis**, e ao vender um item
os demais **sobem uma posição**. Então basta clicar repetidamente na **mesma
posição X**: tudo que estiver em X ou depois acaba passando por X e sendo
vendido, e os slots 1..X-1 nunca se movem — portanto nunca são tocados.

Configurando `3`, os dois primeiros itens da janela estão protegidos **por
construção**. Não é uma lista de exceções que pode estar incompleta: é a
geometria da grade.

Isso é mais seguro que a abordagem dos bots de referência, que reconhecem cada
ícone de lixo por template matching com ~200 arquivos `.bmp`. Naquele modelo,
um item de lixo que você esqueceu de cadastrar fica na bolsa (inofensivo), mas
o modelo inverso — vender tudo menos uma whitelist — seria perigoso. Aqui o
padrão é preservar.

---

## Calibração

### Grade de venda (obrigatório)

Na aba **Venda e Compra**, seção "Geometria da grade":

1. No jogo, vá ao vendedor e abra a janela de venda com itens na bolsa.
2. Tire um print e meça, em pixels **relativos à área de cliente** da janela:
   - centro do **slot 1** → `X do slot 1`, `Y do slot 1`
   - distância entre centros de dois slots vizinhos na horizontal → `Largura da célula`
   - o mesmo na vertical → `Altura da célula`
   - quantos slots cabem por linha → `Colunas`
3. Confira o cálculo: com `sell_start_slot = 3`, a coordenada mostrada deve
   cair exatamente sobre o terceiro slot.

Teste com a bolsa contendo **apenas itens descartáveis** na primeira vez.

### Câmera

O bot fixa a câmera em `(380, 0, 40)` no início de cada ciclo. Sem câmera fixa,
qualquer clique posicional na cena 3D é imprevisível. Se a sua câmera preferida
for outra, ajuste `camera` no `config.json` — mas mantenha-a fixa.

### Minimapa

A navegação inteira depende do minimapa **expandido e na posição padrão**. Não
mova nem encolha o painel.

---

## A mecânica de navegação

Vale entender, porque é o que torna o bot possível.

O minimapa tem **escala 1:1** com as coordenadas do jogo — 1 unidade de
coordenada = 1 pixel — e o **centro do minimapa representa a posição atual do
personagem**. Então para ir até `(tx, ty)`:

```
delta_x = x_atual - tx
delta_y = y_atual - ty
clique_x = centro_x - delta_x
clique_y = centro_y + delta_y      <- eixo Y invertido
```

Um **clique direito** nesse ponto faz o personagem auto-caminhar até lá.

Consequências: não é preciso andar com WASD nem calcular rotas, mas o alcance é
limitado ao raio do minimapa — é por isso que a rota até o altar tem 38
waypoints em vez de um destino único.

Para trechos longos, o bot usa o painel **Surroundings** como teleporte por
texto: digita um fragmento (`"ku"` para a cave, `"Rich"` para o vendedor) e
clica no primeiro resultado. Bem mais robusto que waypoints.

---

## Detecção de queda: 4 sinais

O bot de referência usa **um** sinal e apenas mata o processo. Isso deixa dois
buracos: crash do cliente (o flag nunca é setado) e freeze (cliente vivo, jogo
parado). O BlazesBot usa quatro sinais independentes:

| Sinal | Método | Cobre |
|---|---|---|
| Flag em `0x012CE35C` persistente | memória | queda do servidor |
| `psutil.pid_exists()` falso | processo | crash |
| Posição **e** HP congelados | memória | freeze |
| Falha de leitura da memória | processo | processo morrendo |

O primeiro exige **persistência** (20 s por padrão) porque esse endereço é
compartilhado com caixas de confirmação legítimas. Sem essa espera, vender um
item seria interpretado como queda de servidor.

Durante a luta o sinal de freeze é suspenso — parado atacando o boss é normal.

Ao confirmar a queda: mata o cliente, espera com backoff exponencial (1, 2, 4,
8… até 5 min), relança o `Client.bat`, descobre o novo PID por diferença,
reloga, **reativa o pet** e retoma o ciclo.

---

## Arquitetura

```
main.py                     entrada, checagem de admin, modo --check
blazesbot/
  config.py                 esquema de configuração, validação, JSON
  core/
    memory.py               leitura de memória e mapa de offsets
    inputs.py               teclado e mouse via SendMessage + jitter
    coords.py               coordenadas de tela por resolução
    vision.py               captura de janela e template matching
    secrets.py              cifragem de senha com DPAPI
  bot/
    context.py              contexto compartilhado e snapshot de estado
    watchdog.py             detecção de queda, crash e freeze
    navigation.py           minimapa, waypoints, unstuck, Surroundings
    combat.py               luta contra o boss, cura, pet, buffs
    vendor.py               venda a partir do slot X, recompra
    routine.py              máquina de estados do boss-rush
    supervisor.py           ciclo de vida: lançar, logar, farmar, religar
```

O `supervisor.py` é a peça que os bots de referência não têm: neles o
auto-login e o farm são programas separados. Aqui é um laço fechado.

### Estados da rotina

```
PREPARE -> TO_ENTRANCE -> ENTER_CAVE -> TO_ALTAR -> ENTER_ALTAR
   -> TO_BOSS -> KILL_BOSS -> HEAL -> LEAVE_CAVE
        -> (bolsa cheia?) MAINTENANCE -> TO_ENTRANCE
        -> (senão)                       TO_ENTRANCE
```

Qualquer estado pode cair em `RECOVER` (morte ou falhas repetidas) ou levantar
`Disconnected`, que sobe até o supervisor.

---

## Montaria e velocidade

| Nível | Bônus | Multiplicador | Fator de tempo |
|---|---|---|---|
| +7 | +90% | 1.90x | 1.000 |
| +8 | +100% | 2.00x | 0.950 |
| +9 | +110% | 2.10x | 0.905 |
| +10 | +120% | 2.20x | 0.864 |
| +11 | +130% | 2.30x | 0.826 |
| +12 | +140% | 2.40x | 0.792 |

O nível informado escala o orçamento de tempo de cada trecho: montaria mais
rápida = timeout menor antes do bot concluir que travou. Informar um nível
**maior** que o real causa falso "travado"; informar **menor** só deixa o bot
mais paciente. Na dúvida, declare o real.

---

## Quando o jogo atualizar

Cruzando três versões do cliente:

| | v5135 | v6139 | v6400 |
|---|---|---|---|
| Base do jogador | `+0x00D1EB80` | `+0x00D450EC` | idem 6139 |
| Offset do HP | `0x3B8` | `0x3B8` | `0x3B8` |

**Os offsets internos da struct são estáveis; só a base estática se move** — e
mesmo assim, não se moveu de 6139 para 6400. Então portar é encontrar **um
número**:

1. Cheat Engine como admin, anexado ao `client.exe`.
2. Scan de 4 bytes pelo seu HP → tome dano → next scan → repita até restarem
   poucos endereços.
3. Do endereço do HP, **subtraia `0x3B8`** → base da struct do jogador.
4. Pointer scan até achar o ponteiro estático que aponta para ela.
5. Subtraia `0x00400000` e ponha o resultado em `PLAYER_BASE_RVA`, em
   `blazesbot/core/memory.py`.

Os outros ~40 campos não precisam ser revalidados. Meia hora de trabalho.

---

## Distribuir para os amigos

```bat
pyinstaller --onefile --noconsole --uac-admin ^
  --add-data "data;data" ^
  --name BlazesBot main.py
```

O `--uac-admin` é **obrigatório** — sem ele o executável não pede elevação e
cai no problema silencioso do UIPI.

Cada pessoa monta a própria configuração. **Não compartilhe o `config.json`**:
as senhas são cifradas com DPAPI e vinculadas à conta do Windows, então o
arquivo não funciona em outra máquina — e distribuir credenciais é má ideia de
qualquer forma.

---

## Limitações honestas desta v1

Coisas que eu não pude verificar e que você vai descobrir no primeiro teste:

- **Nada disto foi executado contra o jogo real.** Escrevi com base no código
  de bots que funcionam em produção e no mapa de memória validado, mas não
  tenho Windows nem o cliente aqui. Espere ajustar coordenadas.
- **A geometria da grade de venda é estimada.** É o item nº 1 a calibrar.
- **Entrada na cave e saída** são detectadas por variação grande de
  coordenada, não por flag dedicada. Funciona, mas é heurística — se a cave
  tiver alguma tela intermediária, precisa de ajuste.
- **O portal do Secret Altar** pode exigir grupo (team). O bot de referência
  monta e desfaz team antes de entrar; isso **não** está implementado aqui,
  porque no seu relato o boss-rush é feito direto. Se a entrada exigir team,
  falta portar `bc_team()`.
- **Detecção da fila de login** usa o texto na memória. Se a sua fila
  aparecer de outra forma, ajuste `_in_queue()` em `login.py`.
- **A segunda fase do boss** é tratada re-adquirindo o alvo após o HP zerar.
  Se o boss trocar de nome ao transformar, ajuste `combat.boss_name` ou a
  comparação em `fight_boss()`.
- **Multi-conta** funciona por arquitetura (input em background), mas não foi
  testado com N instâncias. Comece com uma.

---

## Uma nota técnica sobre risco

Duas escolhas deliberadas de projeto, que vale você conhecer:

**Não há escrita de posição na memória.** O código de referência tem uma função
`write_position()` que teleporta o personagem escrevendo as coordenadas
direto. Funciona, mas movimento client-side é validável server-side de forma
trivial e retroativa, mesmo sem anti-cheat instalado — é o tipo de coisa que
aparece em auditoria de log em lote. O BlazesBot anda de verdade.

**Todos os delays têm jitter.** O código de referência usa `time.sleep()` com
valores fixos (0.5, 1.0, 2.0). Um padrão perfeitamente regular é assinatura
óbvia. Aqui todo sleep passa por uma função que aplica variação aleatória.

Sobre banimento: os relatos que encontrei descrevem ondas executadas por
rastreamento de **IP com múltiplas contas**. Se você for rodar várias contas,
considere escalonar horários em vez de logar todas ao mesmo tempo, ou
distribuir as instâncias entre as máquinas dos amigos. A decisão é sua; o dado
fica registrado.

---

## Créditos

O mapa de offsets, as coordenadas de tela e a mecânica de navegação por
minimapa vêm da engenharia reversa feita por **Tony Rogerio (T-R0XX)** nos
bots open source dele, e por **Raaski** no `AutoFarmBot`. O BlazesBot é uma
reimplementação com arquitetura própria — supervisor unificado, detecção de
queda por múltiplos sinais, venda geométrica por slot e senhas cifradas — mas
sem o trabalho de RE deles não existiria.
