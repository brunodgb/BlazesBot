# A madrugada de 07/09/2026 — auditoria forense de 13 h de log

Três travas encontradas em `logs/dev/arquivo/blazes-dev-2026-09-07.jsonl`
(23:17 → 12:22, 71.003 linhas, 5 contas). Nenhuma delas era falha de leitura de
memória: nas três o bot **sabia** o que estava acontecendo e não tinha desfecho.

## Placar do período

| conta | modo | o que produziu | o que aconteceu |
|---|---|---|---|
| `creubo` | BC | 79 bosses até 07h, **0 das 08h às 12h** | jogador na frente do NPC + teto congelado |
| `blazestpas` | APP | mobs até 02:32, **0 até 12:05** | teclas não chegavam ao cliente |
| `gamerblazes` | APP | ~330 alvos/h a noite inteira | saudável (1 morte) |
| `mfaustoapp069` | Fada | 686 curas | saudável |

Três mortes, nenhuma exceção não tratada, nenhum vazamento de memória: o volume
de log por hora ficou estável (4,2k–6,7k linhas/h), e o crescimento das 08h em
diante foi **do laço travado**, não de degradação.

---

## TRAVA 1 — a entrada da cave parou por 3 h 51 min (`creubo`)

A espera pelo diálogo do NPC tem teto adaptativo: `max(12 últimas aberturas) ×
2`, limitado a [180, 600] ms. **A amostra só entra quando o diálogo ABRE.**

```
08:14:05  o teto congela em 427 ms
08h  427ms x 2733   | entradas na cave: 0
09h  427ms x 3574   | entradas na cave: 0
10h  427ms x 3573   | entradas na cave: 0
11h  427ms x 3569   | entradas na cave: 0
12:05:07  um diálogo abre  ->  DENTRO da cave 25 s depois
```

Nas horas saudáveis o teto varia o tempo todo (180, 286, 327, 650…). A partir
das 08:14 fica **idêntico por 13.449 tentativas seguidas** — e teto adaptativo
que não se mexe é a assinatura de uma realimentação morta.

**A causa é estrutural.** A latência real subiu (o cliente tinha acabado de
relogar às 07:55), passou dos 427 ms, e toda tentativa virou reprovação. Como
reprovação não gera amostra, o teto não podia subir. **A medição que levantaria
o teto só podia vir do sucesso que o próprio teto impedia.** A conta só saiu
quando, por acaso, uma abertura veio abaixo dos 427 ms.

### A causa REAL, dada pelo usuário depois da auditoria

*"Se não usa ele [o `BlazesBot - PetBug.exe`], fica outros players na frente e
isso faz ele não conseguir clicar no NPC de entrar na cave."*

E o log confirma, em uma linha: **o patch foi aplicado UMA vez em 13 h**, às
23:27:03. Nunca mais — nem depois do relogin das 07:55, que trocou o cliente
(`hwnd` novo às 07:55:06). Das 08h às 12h a conta clicou 13.449 vezes num NPC
que tinha jogador na frente. **O diálogo não abria porque o clique direito não
chegava nele.** O teto congelado não era a causa: era o que impedia a
recuperação por acaso de acontecer mais cedo.

Duas correções, então, e as duas são necessárias:

**1. O patcher passou a ser confiável.** `NOVA_INSTANCIA_SEMPRE`: mata a
instância aberta e abre outra antes de clicar. Foi o que o usuário pediu
(*"tem vezes que se já está aberto não funciona, acredito que seja pq deve
estar minimizado"*) e há uma razão de engenharia junto: a confirmação lê o log
do programa e **aceita o texto que já estava lá** — com a janela reusada, um
`patch applied` de uma hora atrás confirma um clique que não fez nada. Log
limpo é o que torna a prova honesta. A janela também é restaurada se estiver
minimizada, sem roubar o foco (`SW_SHOWNOACTIVATE`).

Isto INVERTE a regra anterior (*"caso esteja aberto, não reabra"*), e o motivo
dela — dois patchers mexendo nos mesmos clientes — continua respeitado: mata-se
ANTES de abrir, então em nenhum instante existem dois.

**2. A entrada da cave sabe pedir o patch de novo.** Vinte falhas MECÂNICAS
seguidas (o diálogo não abriu) reaplicam o PetBug, com cadência de 2 min.
Instância cheia não conta: ali os cliques saíram e não há ninguém no caminho.

### O teto congelado, que continua sendo um defeito

**O conserto:** falhas CONSECUTIVAS passam a afrouxar o teto em degraus
(`ui_do_jogo._afrouxar_o_teto`), até `TETO_DO_DESESPERO`; qualquer abertura zera
a contagem. O teto duro é 1,2 s — número do council: *"1,0–1,2 s, não 2 s, para
um NPC competitivo"*.

**O que o council apontou e NÃO foi adotado:** decair o contador em vez de
zerá-lo no sucesso (*"um sucesso isolado depois de 30 falhas não prova que o
problema sumiu"*). Não adotado porque o sistema já se corrige por outro lado: a
abertura lenta que finalmente passa ENTRA na amostra e levanta o teto aprendido
sozinha. Zerar não perde a informação — ela foi para a média.

**Fica anotado, sem conserto:** a amostra (`_ABERTURAS_DO_DIALOGO`) é uma global
de módulo compartilhada por todas as contas e todos os tipos de diálogo. Um
diálogo rápido (Altar Stone) derruba o teto de um lento (Skull Herald) — e isso
aparece no log: 3 a 13 falhas por hora no piso de 180 ms, que exige aberturas
abaixo de 90 ms. O afrouxamento cobre a consequência; a separação por tipo
continua pendente e não tem medição própria ainda.

---

## TRAVA 2 — o personagem morria vendo a própria vida cair (3 mortes)

```
01:07:49  vida em 35% mas ainda em batalha. Rodando mais uma volta da macro.
01:07:52  vida em 29% mas ainda em batalha. Rodando mais uma volta da macro.
01:08:06  MORRI
```

Nenhuma poção. `cuidar()` lia a vida, via que estava abaixo do limiar, chamava
`_esperar_sair_de_batalha`, recebia `False` — e **voltava sem curar, porque toda
a cura estava atrás dessa porta.** Com quatro a oito mobs batendo, a flag de
batalha nunca baixa e a porta nunca abre.

A terceira morte tem outra assinatura, e é pior: **100% → morto em 21 s, sem uma
única leitura de vida no meio.** `cuidar()` roda uma vez por rotação da macro, e
aquela rotação durou 21 s.

**O conserto, em duas partes:**

1. `cura.socorro()` — vida abaixo do limiar EM BATALHA bebe UMA poção onde
   estiver. Não anda (arrasta mob), não senta, não espera o efeito: quem mata
   quem está batendo é a macro. Cadência de `SEGUNDOS_ENTRE_SOCORROS`.
2. O socorro entra na **espera fatiada da linha** (`executor._esperar`), e não só
   entre as linhas. O council foi explícito: *"a verificação só entre linhas não
   é um watchdog"* — uma linha de 3 s deixa 3 s de cegueira.

**O limiar é o `pedir_pct` do próprio usuário** (30% por padrão). Não se inventa
número novo quando já existe um medido para a mesma pergunta: o que mudou não é
QUANDO curar, é não deixar de curar por causa de uma flag.

**Efeito colateral bom:** o aviso "N voltas presas em batalha" praticamente
desaparece quando há poção — porque agora ele bebe. Ele continua existindo para
quem não tem tecla de poção, que é quando não há socorro possível.

---

## TRAVA 2b — a ociosidade sob ataque (o irmão da TRAVA 2)

A TRAVA 2 consertou *"não bebeu poção"*. Sobrou a outra metade do mesmo
momento: **o bot também não ATACAVA**.

O laço tinha dois ramos, e o TAB só existia num deles:

```
FORA de batalha  -> pet, comida, caminhada, bolsa, TAB, macro
EM batalha       -> roda a macro de novo               <- e se não há alvo?
```

Morto o mob com outro batendo, a flag de combate continua alta: o laço entra no
ramo EM BATALHA, roda a macro contra um alvo que já não existe, e a volta aborta
na primeira linha (`alvo zerado`). Repete. **O personagem fica apanhando parado
até morrer** — foi assim que a vida caiu de 35% a zero em 17 s.

### O que acusa a agressão

A flag de combate NÃO serve: ela é um estado e fica alta por motivos que não são
dano entrando. Quem serve é a **vida caindo** — um evento. É a mesma distinção
que o usuário já tinha feito para a observação depois da morte: *"dá para
conferir pela vida atual do personagem, que vai estar descendo também"*.

`core/vigia_da_vida.py` guarda a régua, e três regras a tornam confiável:

| regra | o erro que ela fecha |
|---|---|
| só QUEDA conta (`<` estrito) | regeneração e cura SOBEM a vida — nunca disparam |
| a régua anda para os dois lados | sem isso, uma poção deixa a régua velha e o golpe seguinte parece maior |
| "não sei" não acusa nada | leitura falha faria o bot TABar no escuro |

Queda de um décimo já conta, e é de propósito: o falso positivo custa UM TAB, e
só quando não há alvo vivo. Exigir limiar custaria vida no caso em que o dano
entra devagar — que é justamente o caso em que ninguém percebe.

### O reflexo, e o que impede o TAB infinito

Em batalha + sem alvo vivo + vida caindo ⇒ **TAB urgente e macro**, pulando pet,
comida, caminhada e bolsa (a bolsa sozinha tem teto de 10 s).

Três travas, e as três são necessárias:

1. **A porta:** só se entra SEM alvo vivo. Adquirido o alvo, a volta seguinte
   nem entra — o bot passa a rodar a macro até o mob cair.
2. **A marca é consumida** no aceite. Sem isso, um alvo adquirido com a vida
   ainda caindo (o mob bate enquanto morre) reentraria.
3. **A cadência:** um golpe por segundo seria um TAB por segundo. O freio é
   `ESPERA_SEM_ALVO`, o mesmo que o ramo calmo já paga — não é número novo.

### Um mecanismo que existia e estava desligado

`_observar_depois_da_morte` + `_urgir` já faziam quase isto: detectavam "matei o
mob e a vida caiu, tem outro batendo" e marcavam urgência. Só que a chamada é
`if morreu and not LACO_SIMPLES:` — e `LACO_SIMPLES` é `True` desde 26/08/2026.
**O mecanismo nunca rodou em produção.** O reflexo é a mesma ideia, no laço que
roda de verdade.

---

## TRAVA 3 — as teclas pararam de chegar e o bot insistiu 9 h 30 min

```
02:32:38  o alvo caiu (HP) na linha 9          <- último ato normal
02:32:41  1 TAB(s) sem resposta, e HÁ 2 mob(s) vivo(s) por perto
02:32:44  A bolsa não apareceu em 2.0s depois da tecla 'I'
...
09:29:04  10390 TAB(s) sem resposta, e HÁ 6 mob(s) vivo(s) por perto
          (o mais próximo a 3). NADA está sendo atacado.
```

**Nove horas e meia. 11.978 voltas abortadas de 12.585. Zero mobs mortos.**

A leitura de memória funcionou o tempo todo — posição, tabela de entidades e
vida respondiam. O que morreu foi a ENTRADA. O bot detectou, nomeou e escreveu
no log uma vez por minuto, por nove horas, sem nunca mudar de estratégia.

**A causa continua sendo hipótese** (chat aberto, janela modal, cliente
ignorando mensagem sintética, thread de UI degradada) — o log não separa, e um
clique do usuário por volta das 12:00 resolveu. Por isso o conserto **não tenta
consertar a causa**.

**O conserto:** `core/teclado_mudo.py`, uma escada.

```
duas teclas mudas por 30 s  ->  ESC, UMA vez
ainda mudo aos 5 min        ->  declarar queda (relogin)
dois relogins sem efeito    ->  desiste e grita
```

**DUAS teclas, não "N TABs"** — do council: *"TAB sozinho não prova nada (…) o
detector deve ser baseado em uma sequência de ações verificáveis"*. TAB pode ser
inaplicável; TAB **e** a tecla de inventário mudos no mesmo período, com mob
vivo a três unidades, é entrada inoperante. Foi preciso fazer o deletador
devolver `BOLSA_NAO_ABRIU` em vez de `0`: os dois eram zero, e o zero calado
deixou a segunda testemunha sem poder depor.

**Spot vazio não conta.** Sem mob por perto, o TAB não fazer nada é o jogo
funcionando — relogar ali trocaria uma conta parada por uma conta deslogada.

**O clique neutro ficou de fora, de propósito.** Era o degrau do meio óbvio
(devolver o foco clicando na área de jogo) e o council reprovou: *"não use
coordenada aparentemente vazia como premissa de segurança (…) se não há região
garantidamente segura, pule o clique e vá para relogin controlado"*. Clicar às
cegas pode selecionar o que não devia; o relogin custa minutos e é reversível.

**O ESC sai uma vez por incidente**, nunca em laço: ele também larga a mira.

**Este é o SEGUNDO motivo para o bot derrubar a própria sessão** (o primeiro é a
janela morta / tela de reconexão, em `docs/INVARIANTES.md`). A justificativa é a
mesma da primeira: uma conta que não recebe tecla produz exatamente o que uma
conta deslogada produz — nada —, com a diferença de que a deslogada tem conserto
automático.

---

## O que NÃO estava quebrado

- **Sem vazamento e sem degradação.** O volume por hora e o tempo por waypoint
  ficaram estáveis das 23h às 12h; o pico das 08h em diante é o laço travado.
- **Sem exceção não tratada.** Zero tracebacks em 71.003 linhas.
- **A Fada e o `gamerblazes` rodaram a noite inteira** — 686 curas, ~330 alvos
  por hora, sem intervenção.
- **O ciclo da morte funcionou nas três mortes**: a Fada reviveu em 7 s na
  última delas. O que faltou foi não morrer.

## Ainda em aberto (medido, sem conserto)

- **`creubo`, 212 relogins e 105 "Conexão interrompida"** concentrados em 07h e
  08h. É episódio de rede, não defeito do bot — mas não há backoff: o relogin
  tenta na mesma cadência a 1 ou a 100 falhas.
- **Navegação com 163 travamentos e 150 rollbacks** ("Voltei do waypoint 55 para
  perto do 52"), todos recuperados pelo destravamento por vizinhos. Custa
  segundos por run e não impediu nada.
- **A amostra global do teto do diálogo** — ver TRAVA 1.
