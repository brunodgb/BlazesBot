# Como a caminhada funciona — guia para você ajustar

Este documento explica **tudo** que faz o personagem se mover: os três meios de
transporte, onde cada coordenada vive no código, como medir uma coordenada nova
e como ajustar a rota da Bewitcher Cave.

---

## 0. A regra que vem antes de todas: **andar é sempre montado**

A montaria não é uma otimização de tempo neste bot — é **pré-requisito**. Tudo
que está escrito neste documento foi medido com o personagem **montado**: os
orçamentos de tempo de cada trecho, as tolerâncias dos waypoints, as ~18 unidades
de alcance de um clique no minimapa e a skill de velocidade, que afeta a montaria
e não o personagem. A pé, o trajeto passa do dobro da duração, e dentro da cave
dobrar a duração é o trem de mobs alcançando.

Por isso a exigência **não** fica espalhada pelos estados da rotina. Ela mora em
dois pontos estruturais do `Navigator`, e todo movimento passa por um deles:

| Onde | O que faz |
|---|---|
| `garantir_montaria_para_andar()` | **portão** na entrada de toda função que produz movimento: `follow_path`, `_mover_pelo_mapa`, `travel_via_surroundings` e o clique no painel de arredores |
| `_manter_montaria()` | roda a **cada volta** do laço de deslocamento (~0,12 s) e repõe a montaria assim que ela cai |

Duas situações em que o bot anda a pé, e as duas estão certas:

- **O jogo recusou montar** (o personagem está sendo atacado, por exemplo). Parar
  até conseguir seria morrer com os mobs em cima, então ele sai a pé e o laço
  aciona a tecla a cada 2,5 s até pegar. O bot **não consulta flag de combate
  nenhuma** para decidir isso — ele tenta e confere o resultado na memória. Só
  isso: a flag ficava ligada quase toda a travessia da cave, e consultá-la
  bloqueava justamente as remontagens que importavam. Passados **8 segundos** a
  pé, uma linha de log explica a demora; a tentativa de remontar já estava
  acontecendo desde o primeiro segundo.
- **A tecla acabou de ser acionada.** A tecla da montaria é um **interruptor**:
  apertá-la de novo antes de o cliente confirmar desmonta quem acabou de montar.
  Existe um intervalo mínimo de **2,5 s** entre toques, e *todos* os lugares que
  tocam nela (portão, laço, parada para poção) compartilham o mesmo
  cronômetro — antes eram cronômetros separados, e o resultado era montar e
  desmontar em seguida.

O **desmonte deliberado** (só nos DOIS pontos de luta do covil) tem uma exceção
à regra de "segurar enquanto em combate". O bot normalmente **não desmonta em
batalha** (`ensure_dismounted` ignora o pedido com a flag de combate ligada),
porque desmontar no meio de um trajeto com mobs em cima é parar pra morrer. Mas
nos **waypoints dos 4 mobs antes do boss** e **do boss** — os únicos dois pontos
em que o personagem PRECISA atacar, e montado o jogo ignora a tecla de skill —
o desmonte é permitido **mesmo em combate**: é lá que acaba o trajeto e começa
a luta. A exceção é passada como `permitir_em_batalha=True` de
`_descer_para_lutar("guardas"/"boss")` para `ensure_dismounted`; qualquer outro
desmonte (poção, curar, preparo) continua segurando em batalha.

**Como conferir no log.** Toda conclusão de trajeto traz quanto tempo foi a pé:

```
Caminho concluído: 58 waypoints em 92.4s (1.6s por ponto)          <- tudo montado
Caminho concluído: 58 waypoints em 148.7s (2.6s por ponto) | 41s a pé
```

O sufixo `| Xs a pé` só aparece quando houve tempo a pé. Se ele aparecer sempre,
o problema é a tecla da montaria (`Editar conta ▸ Teclas ▸ Montaria`) ou a
montaria não estar disponível no personagem.

---

## 1. Os três meios de transporte

O bot escolhe pela distância até o destino.

| Meio | Quando usa | Alcance | Precisão |
|---|---|---|---|
| **Mapa-múndi** (tecla M) | distância acima de **50 unidades** | a região inteira | chega perto |
| **Minimapa** | distância abaixo de 50 | ~18 unidades por clique | exata |
| **Surroundings** | destino tem nome | qualquer lugar do mapa | exata |

### 1.1 Mapa-múndi — o transporte de longa distância

Este é o que resolve "sair da cidade e chegar na frente da cave".

O bot aperta **M**, o mapa da região abre, ele dá um **clique direito** no ponto
que corresponde ao destino, fecha o mapa e espera. O caminho em si é feito pelo
**pathfinding do próprio jogo**, que desvia de obstáculos sozinho — é por isso
que este meio é tão superior a uma lista de waypoints.

**A conversão de coordenada para pixel.** Cada região é desenhada no mapa com
uma escala própria. Precisamos de dois números por região:

- **`centre`** — a coordenada de jogo que cai **no meio da tela** quando o mapa
  daquela região está aberto
- **`scale`** — quantas unidades de coordenada cabem em 1 pixel, em X e em Y

A fórmula:

```
pixel_x = largura_da_tela / 2  +  (centre_x - alvo_x) / scale_x
pixel_y = altura_da_tela  / 2  +  (centre_y - alvo_y) / scale_y
```

O `scale_x` é **negativo** porque o eixo X do mapa é invertido em relação ao do
jogo. Isso já está embutido no sinal.

**Exemplo real — a entrada da Bewitcher Cave.** A entrada está em
`(1395, -635)`, em Ghost Din Woods, que pertence à região `vast_mountain`:

```
centre = (989, -489)      scale = (-1.38, 1.38)

dx = 989 - 1395  = -406
dy = -489 + 635  =  146

pixel_x = 512 + (-406 / -1.38) = 512 + 294 = 806
pixel_y = 384 + ( 146 /  1.38) = 384 + 106 = 490
```

Então, em 1024x768, o bot clica em **(806, 490)** no mapa. Em 1632x918 o mesmo
destino dá **(1110, 564)** — a fórmula usa o tamanho real da janela, então
funciona em qualquer resolução.

**O truque dos desvios.** Se outro jogador estiver exatamente no ponto de
destino, o jogo **recusa** o caminho em vez de parar ao lado. Por isso o bot
tenta uma lista de pontos vizinhos:

```python
DESVIOS_DO_MAPA = ((0, 0), (20, 0), (-20, 0), (20, 20), (-20, 20),
                   (-20, -20), (0, -20), (20, -20), (0, 20))
```

Ele clica, espera 2 segundos, verifica se a posição mudou. Se mudou, o caminho
foi aceito e ele para de tentar. Depois o minimapa fecha a diferença.

**Onde mexer:** `blazesbot/core/zones.py`, dicionário `ZONAS`.

### 1.2 Minimapa — ajuste fino

O **centro do minimapa representa a posição atual do personagem**. Clicar
deslocado do centro manda andar naquela direção.

```
deslocamento_x = (atual_x - alvo_x) × (-1.7)
deslocamento_y = (atual_y - alvo_y) × ( 1.7)

clique = centro_do_minimapa + deslocamento
```

Dois números importam:

- **1.7 pixels por unidade** de coordenada. O minimapa **não** é 1:1 — essa foi
  uma correção que veio da análise do GhostBot. Com 1:1 o bot ainda funcionava,
  porque o movimento é iterativo e se autocorrige, mas cada passo saía menor do
  que devia.
- **Máximo de 30 pixels** do centro. Clique além disso cai fora do widget e não
  faz nada. Por isso cada passo no minimapa cobre no máximo ~18 unidades
  (30 ÷ 1.7).

O centro do minimapa em 1024x768 é **(919, 115)**, ancorado no canto superior
direito — em outras resoluções ele acompanha a borda.

**Onde mexer:** `blazesbot/core/zones.py`, constantes `MINIMAP_SCALE` e
`MINIMAP_MAX_PIXELS`.

### 1.3 Surroundings — teleporte por nome

O painel de arredores lista lugares e NPCs próximos. O bot digita um fragmento
do nome, clica no primeiro resultado, e o jogo caminha até lá.

É o mais robusto quando o destino **tem nome**, porque não depende de coordenada
nenhuma. Os fragmentos usados hoje:

| Fragmento | Destino |
|---|---|
| `ku` | entrada da Bewitcher Cave |
| `Din` | Ghost Din Woods |
| `Rich` | NPC vendedor (Rich Man) |

**A conferência antes de clicar.** A memória expõe o **primeiro resultado** da
busca, com nome e coordenadas. Isso vem de um ponteiro descoberto no GhostBot:

```
0x012CE2DC → [0x18, 0x8C, 0x3C] → +0x64
```

A string tem o formato `... text="Nome [x,y]" ...`, e o bot extrai nome e
coordenadas com uma expressão regular. Com isso ele **confirma** que a busca
achou o lugar certo antes de clicar. Sem essa conferência, uma busca que
trouxesse outro lugar de nome parecido levaria o personagem para o lugar errado
sem ninguém perceber.

**Onde mexer:** `config.py`, campos `cave_search_text`, `woods_search_text` e
`vendor_search_text` em `BCRoute` e `BCVendor`.

---

## 2. Onde cada coordenada vive

```
blazesbot/core/zones.py        regiões do mapa, escalas, conversões
blazesbot/config.py  (BCRoute) a rota da cave: entrada, waypoints, boss
blazesbot/core/coords.py       pontos de tela: minimapa, botões, NPC
```

### A rota da BC, em `config.py`, classe `BCRoute`

```python
cave_entrance  = (1395, -635)     # entrada da cave
boss_position  = (70, -406)       # onde o boss fica

boss_approach = [                 # aproximação final, 5 passos
    (185, -406), (165, -406), (125, -406), (105, -406), (80, -406),
]

altar_path = [                    # 38 waypoints da entrada até o Secret Altar
    (400, 65), (373, 81), (354, 111), ...
]

tricky_waypoints = [              # pontos onde costuma travar
    (120, 145), (223, -98), (189, 44),
]
```

Os `tricky_waypoints` recebem **tolerância maior** (8 unidades em vez de 3).
São lugares onde a geometria do mapa faz o personagem encostar e nunca chegar
exatamente na coordenada. Esses três vieram de comentários no código do T-R0XX,
que marcou justamente onde o bot dele travava.

---

## 3. Como medir uma coordenada nova

Três formas, da mais simples para a mais precisa:

**No próprio jogo.** A posição aparece no canto superior direito, ao lado do
minimapa, no formato `Stone City [278, -513]`. Vá até o ponto e leia.

**Com o diagnóstico.** Rode `2-DIAGNOSTICO.bat` com o personagem parado no
ponto. Ele imprime `posição (X, Y) = (278, -513)`, junto de HP, localização e o
resto do estado.

**Gravando uma rota inteira.** Ande o trajeto devagar, parando nos pontos onde
quer um waypoint, e anote cada posição. Waypoints muito próximos desperdiçam
tempo; muito distantes fazem o personagem tentar atravessar parede. Um bom
espaçamento é de 30 a 50 unidades em terreno livre, e menor em corredores.

---

## 4. O ciclo completo da BC, passo a passo

Cada linha abaixo corresponde a um estado da máquina em
`blazesbot/bot/routine.py`.

```
PREPARE
  • fixa a câmera em (380, 0, 40)
  • invoca o pet e aplica os buffs
  • alimenta o pet

TO_ENTRANCE
  • monta
  • Surroundings "ku" → entrada da cave (1395, -635)
  • se falhar: Surroundings "Din" e tenta de novo

ENTER_CAVE
  • se há nick de reset configurado: monta o time
  • clique no NPC de entrada, depois em confirmar
  • confirma a entrada vendo a posição mudar drasticamente
  • desfaz o time

TO_ALTAR
  • monta, refixa a câmera
  • percorre os 38 waypoints de altar_path

ENTER_ALTAR
  • clique no NPC do altar, depois em entrar
  • confirma vendo a posição mudar

GUARDAS  (FASE 1)
  • chega no ponto dos 4 mobs e NÃO aperta TAB -- eles atacam na chegada;
    a luta gira pela flag de combate, sem ponteiro de alvo e sem AoE
  • saiu da luta: se a vida estiver ABAIXO de 40% (`LIMINAR_TOPUP_ANTES_DO_BOSS`),
    top-up AQUI e não na frente do boss: Super Skill (ou skill de cura) UMA vez
    conferindo o efeito, e se a vida não subiu (recarga) usa 1 poção de HP e fica
    parado os 15 s. No waypoint do boss NÃO se bebe poção -- o boss encosta e
    cancela o efeito na hora.

TO_BOSS
  • posicionamento final em boss_position (70, -406)

KILL_BOSS  (Fase 2, por flag de combate)
  • desmonta, espera a flag de combate engajar (SEM PRAZO), sem TAB;
    poção de batalha por limiar (`battle_hp_pct`), com AoE
  • na ESPERA do boss, se faltar vida, SENTA para regenerar em vez de beber
    poção; sair de combate confirmado = vitória
  • trata a segunda fase (o boss se transforma quando o HP zera)

HEAL
  • poção → Super Skill → sentar, em sequência rápida

LEAVE_CAVE
  • sai da instância
  • se a bolsa encher (espaço livre abaixo da folga): vai vender

MAINTENANCE
  • Surroundings "Rich" → NPC vendedor (153, -492)
  • vende a partir do slot configurado
  • compra Return Charm
  • volta para TO_ENTRANCE
```

---

## 5. Quando o personagem trava

Dois casos distintos, com respostas distintas:

**Travado no lugar (a resposta não sobe mais uma escada longa).** O usuário
pediu para ir DIRETO ao relançamento pelos waypoints mais próximos. O passo
lateral (`_destravar`) foi REMOVIDO DE VEZ: ele andava o personagem 1-2u no
lugar — e era exatamente isso que impedia o relançamento de disparar (o
gatilho pede posição estática, e o passo lateral nunca deixava ela ficar
parada). O log mostrava o bot fazendo `destravando 1` de 5 em 5 s, 40 s
seguidos, sem concluir que estava travado de verdade. Hoje:

1. **Relança pelos 3 waypoints mais próximos, POR PROXIMIDADE**
   (`relancar_pelos_mais_proximos`) — o mais perto primeiro (pode ser o da
   frente ou o de trás; a distância euclidiana é quem decide). Com
   `precisa_avancar=True` ele só aceita um waypoint que faça a rota AVANÇAR
   além do travado — alcançar um waypoint **atrás** fazia a rota re-apontar
   para o MESMO alvo intransponível (era o loop "cheguei no 1/10, a rota
   continua do 2/10" que recomeçava para sempre). Se todos os candidatos são
   atrás ou inalcançáveis, vai pro item 2. Chegou num waypoint oficial, a
   rota natural continua do seguinte — `indice = alcancado` basta, o laço
   avança.
2. **Círculo de offsets** (última carta, dentro da rotina acima) — clica em
   pontos **ligeiramente deslocados** (8 direções de bússola × raios 1, 2,
   3, 5), primeiro ao redor da **PRÓPRIA posição** (quebrar o "bolsão" de onde
   o jogo recusa autopath — no Secret Altar o jogo mesmo logava "Failed to
   auto-path"), depois ao redor do waypoint mais próximo — para trocar o
   ângulo de saída. Cada clique é curto (~2 s) + cheque de movimento (andou,
   confirma o waypoint com `goto`). Teto de 45 s.
3. **Retomada de rota** (`onde_retomar`, orçamento 2) — se o relançamento
   falhou e o círculo não destravou, recalcula por onde entrar.
4. **DEPOIS de esgotado** — devolve o controle para a rotina se resituar
   (foi isso que destravou o caso real: SITUAR → retomada pelo 46 → alcançou).

**Rollback / lag (o personagem voltou na rota sem o bot pedir).** A posição
recuou vários waypoints num instante. O bot reconfirma a posição ~0,5 s depois
(para não relançar no meio do "pulo" do lag) e relança pelos 3 waypoints mais
próximos da posição reconfirmada, por proximidade. Chegou num deles, a rota
continua dali; se não, retoma do waypoint para onde voltou.

**Fora da cave (sem rota):** não há waypoints para relançar nem círculo (os
dois dependem da rota). O próprio laço fica reclicando o alvo e o bot desiste
depois de 6 ciclos de "sem progresso" (`travas > 6`), devolvendo o controle
para a rotina se resituar.

**Onde mexer:** `blazesbot/bot/navigation.py` — `relancar_pelos_mais_proximos`
(relançamento), `_tentar_circulo` + `_clicar_offset_e_verificar` +
`_pontos_do_circulo` (círculo). O método `_destravar` (passo lateral) foi
REMOVIDO. A ordem da varredura do círculo (raio por raio vs. direção por
direção) é a constante `CIRCULO_POR_RAIO`, e o N de waypoints é o argumento
`n` de `relancar_pelos_mais_proximos` (default 3).

---

## 6. Ajustes que provavelmente você vai querer fazer

**A rota do altar não serve para o seu caminho.** Substitua a lista
`altar_path` em `config.py` pelos seus waypoints. Comece com poucos pontos bem
espaçados: como o mapa-múndi entra em ação acima de 50 unidades, trechos longos
podem virar um único waypoint.

**O personagem trava sempre no mesmo ponto.** Acrescente aquela coordenada em
`tricky_waypoints` — ela passa a aceitar 8 unidades de tolerância em vez de 3.

**Um clique de NPC não acerta.** Os pontos de NPC estão em `core/coords.py`
(`cave_enter_npc`, `altar_npc`, `vendor_npc`). Note que a interação com NPC usa
**clique direito**, não esquerdo.

**A escala de uma região está errada.** Se o clique no mapa cai longe do
destino, o `scale` daquela região precisa de ajuste. O método: escolha um
destino conhecido, deixe o bot clicar, veja onde ele parou, e corrija a escala
pela razão entre a distância desejada e a obtida.

**O minimapa erra a distância.** Ajuste `MINIMAP_SCALE` em `core/zones.py`. Com
valor alto demais o personagem passa do ponto; baixo demais ele dá passos curtos
e demora.

---

## 7. Créditos das descobertas

A navegação junta o que três projetos abertos descobriram, mais medições nossas:

| Origem | Contribuição |
|---|---|
| **T-R0XX** | mecânica do minimapa, coordenadas de tela em 1024x768, os 38 waypoints do altar e os pontos de travamento |
| **GhostBot** | navegação por mapa-múndi com as escalas de cada região, escala real do minimapa (1.7), leitura do primeiro resultado do Surroundings, lista de desvios quando o caminho é recusado |
| **Raaski / AutoFarmBot** | arquitetura híbrida: memória para estado, imagem para interface |
| **Nossas medições** | ponteiro base da ver.6400, ancoragem por template para funcionar em qualquer resolução, geometria da grade de venda |
