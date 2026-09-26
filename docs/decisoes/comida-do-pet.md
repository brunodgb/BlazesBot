# Comida do pet — o porquê medido

> **Duas rodadas.** A Parte I (27/08/2026) consertou a GRADE e o APERTO. A Parte II (13/09/2026) consertou a LATÊNCIA — o defeito que sobrou, e o que quase custou o pet da conta `creubo`.

> **Investigação de 27/08/2026.** Fonte de tudo aqui: `logs/dev/blazes-dev.jsonl`
> (26/08 22:52 → 27/08 01:21) e `data/config.json`. O relato do usuário:
>
> * *"o bot parou de usar a comida do pet"*
> * *"eu estou acompanhando pela quantidade de pet food que eu tenho e não está
>   baixando, eu estou a horas com a quantidade 20"*
>
> Eram **dois defeitos diferentes com o mesmo sintoma**, um por ecossistema.

---

## 0. O que NÃO é o defeito (para não se procurar de novo)

**Não existe sensor de fome.** Não há ponteiro de fome/stamina do pet mapeado; o
único campo de pet em `core/memory.py` é `OFF_PET_ACTIVE` (0x10A8), que responde
*"invocado sim/não"*. O gatilho é **relógio puro**, em `core/pet.py`, e isso é
deliberado: a fome do jogo é temporal.

**O gatilho estava certo.** `PetFeeder.deve_alimentar` / `registrar_alimentacao`
ancoram no VENCIMENTO e não na refeição, e re-ancoram no presente quando o atraso
passa de um intervalo. Nenhum dos dois defeitos abaixo está na decisão.

**A fiação do supervisor estava certa.** Tecla, intervalo como função (muda a
quente) e `feed_on_start` chegavam corretos ao executor.

**A gravação do `config.json` é atômica e sob lock**, e os supervisores
compartilham o MESMO objeto `BotConfig` — não há escrita perdida entre contas.

**As duas UIs mutam campo por campo** (`web_app.salvar`, `account_dialog`), então
salvar uma conta na tela **não** apaga `proxima_comida_em`.

---

## 1. APP — a grade amnésica (o defeito de "parou de usar")

### A medição

Conta `blazestpas` (APP, intervalo 51 min, `feed_on_start=False`,
`proxima_comida_em = 0.0`). Última refeição registrada: **23:18:33**. Depois
disso, **12 reinícios do executor em 88 minutos**:

```
23:53:32  Modo APP iniciado    sessão de  1,0 min
23:54:51  Modo APP iniciado    sessão de  1,4 min
23:56:33  Modo APP iniciado    sessão de 45,0 min   <- faltaram 6 min para os 51
00:42:46  Modo APP iniciado    sessão de 12,0 min
00:55:09  Modo APP iniciado    sessão de  1,0 min
00:56:17  Modo APP iniciado    sessão de  0,3 min
00:56:43 / 01:08:09 / 01:12:41 / 01:20:29 / 01:21:03 / 01:21:46
```

**Zero refeições em 123 minutos**, com intervalo de 51.

### A causa

`ExecutorDeMacro.__init__` construía `PetFeeder()` **sem `vence_em` e sem
gravador**. `proxima_comida_em` aparecia em três lugares no projeto, todos no BC:

```
blazesbot/bot/bc/combat.py:917   leitura
blazesbot/bot/bc/combat.py:3410  gravação
blazesbot/config.py:281          o campo
```

Então cada nascimento do executor caía no braço "grade não iniciada" de
`deve_alimentar`, que **RE-ANCORA** o vencimento em `agora + 51 min` e devolve
False. Nenhuma sessão viveu tanto. O relógio parecia sempre correto e a única
coisa que ele nunca fazia era vencer.

**E o defeito se realimenta:** quanto mais o bot cai, mais reinícios, mais vezes
a conta volta a zero.

### O conserto

A persistência **subiu para o `core`** (regra de PROMOÇÃO do `CLAUDE.md`): o
`PetFeeder` recebe um `gravar` opcional e o chama a cada mudança da grade —
`registrar_alimentacao` **e** o nascimento da grade dentro de `deve_alimentar`.
Essa segunda gravação é a que consertou o APP: a grade recém-criada vai para o
disco na hora, em vez de morrer com o processo.

Quem monta a função de gravar: `CombatEngine._gravar_grade_da_comida` (BC) e
`SupervisorDeConta._gravar_grade_da_comida_do_app` (APP). **Mesmo campo, mesmo
arquivo.** O `core` continua sem saber que existe `config.json`.

**Reprodução travada em teste:** `tests/test_comida_do_pet.py` roda as 12 sessões
de 7 min duas vezes — sem disco dá 0 refeições (o defeito), com disco dá 1.

---

## 2. BC — o aperto que a ação seguinte cancela (o defeito de "a quantidade não baixa")

### A medição

O BC (`creubo`, 56 min) **alimentava na hora certa** — a grade dele sempre foi
persistida:

```
23:19:34  Alimentando o pet (a cada 56 min)
00:18:04  Alimentando o pet (a cada 56 min)   (+58,5 min)
01:13:31  Alimentando o pet (a cada 56 min)   (+55,5 min)
```

E ainda assim a bolsa não baixava. As **três** ocorrências têm exatamente a mesma
forma no log:

```
-2,0s  Desmontando para aplicar buffs
-0,0s  Barra de atalhos na página 1 por tecla (invocar o pet)   <- tecla 'P'
+0,0s  Alimentando o pet (a cada 56 min)                        <- tecla '6'
+0,6s  Não estou montado; montando antes de atravessar a cave
+0,7s  Barra de atalhos na página 1 por tecla (montar)
+3,8s  Montaria ativa
```

Duas coisas erradas aparecem aí, e as duas são de temporização.

### Causa A — montar cancela o uso do item

`feed_pet` esperava `tick(0.5)` depois da tecla, e o passo seguinte de
`_do_preparar_dentro` é **montar**. Ou seja: **600 ms depois de apertar a comida o bot
aperta a montaria.** Montar interrompe o uso do item, e o desfecho é o pior
possível — a grade avança, o disco é gravado, o log diz "alimentei" e a bolsa
diz que não.

Isso também explica por que o sintoma é RECENTE: até 25/08/2026 a comida era
adiantada em `_do_ate_a_entrada`, fora da cave. Ela foi movida para o passo 4 do
preparo de entrada, imediatamente antes do passo 5 (montar).

**Conserto:** `SEGUNDOS_PARA_A_COMIDA_SER_USADA` em `core/pet.py` (1,5 s),
usado pelos dois ecossistemas. **O valor NÃO está medido** e isso está escrito no
próprio comentário: ele é herdado do irmão medido mais próximo (`ensure_pet`
espera 1,5 s depois da tecla de invocar, `docs/tempos-originais.json`). Como
medir: contar os itens na bolsa antes e depois, baixando o número até a contagem
parar de cair. Custo: pago uma vez por hora, na run que alimenta.

### Causa B — a barra de atalhos não assentava

`hotbar.ir_para_a_pagina_1` apertava a tecla da página e **devolvia na hora**.
`ENTRE_CLIQUES` (25 ms) valia só ENTRE cliques; depois do último, nada. Medido:
`P` e `6` saem no MESMO instante, três vezes de três.

"O cliente processou a mensagem" não é "a barra está desenhada na página 1": a
mensagem é tratada no WndProc, a barra troca no quadro seguinte.

**Por que só a comida sofria:** todo outro consumidor **insiste e confere** — a
montaria repete a tecla até a memória confirmar (é por isso que ela funciona no
mesmo log, 3 s depois), a poção até o HP subir. Comida do pet e buffs são os dois
únicos que apertam UMA vez e acreditam.

**Conserto:** `ASSENTAR_A_PAGINA = 0.08` em `bc/hotbar.py`, nos DOIS caminhos
(tecla e clique), antes de devolver. Também **não medido**; é o menor valor ainda
maior que um quadro a 60 fps (16,7 ms), pago em momento-chave e não em laço. Como
medir: ir para a página 3, chamar `ir_para_a_pagina_1` e ler o dígito da bola
(as máscaras estão no cabeçalho do módulo) baixando o valor até o dígito voltar a
sair errado.

### Causa C — `feed_pet` não garantia a página, ele pegava carona

O `feed_pet` do BC nunca chamou `garantir_pagina_1`. A página vinha do
`ensure_pet` imediatamente anterior — **e só quando `summon_on_login` está
ligado**. Desligado, a tecla da comida saía com a página NÃO verificada, e na
página errada o mesmo `6` dispara outra coisa sem que o bot tenha como perceber.
Agora `feed_pet` garante a página ele mesmo (a recarga de 5 s do `hotbar` evita
o clique a mais quando o `ensure_pet` acabou de garantir).

### Causa D — em batalha a tecla é engolida e a grade avançava

O APP já barrava a comida em combate e o comentário dele explica por quê: *"a
tecla de alimento é IGNORADA pelo jogo em combate, mas o `PetFeeder` registrava a
refeição mesmo assim -- o pet passava fome com o cronômetro dizendo que tinha
comido"*. **O BC não tinha essa guarda**, e `_do_preparar_dentro` roda logo depois de
entrar na cave, onde o aggro é a regra. Guarda adicionada, tri-estado: só `True`
barra, "não sei" passa.

---

## 3. O que mais apareceu na investigação (consertado no mesmo passo)

* **APP, `feed_on_start`: o espelho invertido.** `rodar()` fazia
  `feed_pet(force=True)` a cada início. Com 12 reinícios em 88 min isso são 12
  refeições — exatamente o *"ele acabar ficando em comida X vezes ao dia"* que a
  regra do usuário proíbe. Só não acontecia porque a conta de APP está com
  `False`; `creubo` e `mfausto2` estão com `True`. Além disso era o **único**
  aperto de tecla do APP antes do primeiro `antes_da_volta`, ou seja com a página
  da barra não verificada. Agora a largada é cobrada dentro do primeiro
  `feed_pet` do laço, depois da garantia da barra.
* **Tecla que o `Input` recusa avançava a grade.** `Input.key` devolve False para
  tecla que ele não sabe traduzir; ninguém olhava. Agora vira `ERROR` (+ evento
  no diário, no BC) e a grade **não** avança.

---

## 4. O que continua ABERTO

* **Os dois números novos não estão medidos**
  (`SEGUNDOS_PARA_A_COMIDA_SER_USADA`, `ASSENTAR_A_PAGINA`). As receitas de
  medição estão nos comentários e repetidas acima.
* **Não há confirmação de que o item foi consumido.** Não existe ponteiro de fome
  e a contagem da bolsa não é lida. Enquanto isso, o que existe é o log de estado
  no instante do aperto (`montado / batalha / sentado / pet`), que é o que
  transforma *"não funciona"* em *"não funciona QUANDO"*.
* **`feed_pet` do BC tem um único chamador**, `_do_preparar_dentro`
  (`bc/routine.py:1165`). A checagem no laço principal está **comentada** e não
  em interruptor (`bc/routine.py:2518`). Consequência: conta que não completa
  entradas na cave nunca come. Mantido por decisão do usuário em 27/08/2026 —
  *"talvez até esta executando a função que deve continuar dentro do `_do_preparar_dentro`
  como está hoje"*.
* **`CombatEngine.vale_alimentar_antes_de_entrar` é código morto** (zero
  chamadores). Sobrou da alimentação pré-entrada removida em 25/08/2026.
* **`apply_buffs` também aperta uma vez e acredita**, e também não garante a
  página. Não foi tocado nesta rodada porque o usuário não relatou buff falhando
  — mas é o irmão gêmeo do defeito consertado aqui.


---

# PARTE II — A LATÊNCIA (13/09/2026): o defeito que sobrou

> Relato do usuário: *"O pet da conta 'creubo' quase desapareceu no ecossistema
> HH. O timer estourou enquanto o bot estava fora da cave e a alimentação foi
> ignorada/perdida."*

A Parte I consertou **a grade** (o APP não a guardava) e **o aperto** (a montaria
cancelava o item). Sobrou um terceiro defeito, de natureza diferente: a grade
estava certa, a tecla saía, e mesmo assim o pet passou fome.

## 5. A medição

`logs/dev/`, conta `creubo`, HH, intervalo de 50 min. 128 janelas de
alimentação (`preparar_dentro`) entre 12:25 e 15:30 de 13/09/2026:

| percentil | intervalo entre janelas |
|---|---|
| mediana | **6,5 min** |
| p75 | 8,1 min |
| p90 | 10,8 min |
| p99 | 21,4 min |
| **MAX** | **52,7 min** |

Acima de 10 min: 17 de 127. Acima de 25 min: **1** de 127. A cauda é o defeito.

As três refeições do dia, e o buraco:

```
12:47:23  Alimentando o pet (a cada 50 min)
13:37:32  Alimentando o pet (a cada 50 min)   +50,1 min   <- correto
14:54:28  Alimentando o pet (a cada 50 min)   +76,9 min   <- 27 min de atraso
15:20:43  Alimentando o pet (a cada 50 min)   +26,3 min   <- a grade recuperando
```

A janela de 52,7 min, reconstituída fase a fase:

```
14:01:52  ate_o_boss     run normal
14:06:07  situar -> preparar
14:06:22  ate_a_porta    <-- entra aqui
14:27:32  (a refeição vence, e o bot está FORA da cave)
14:52:42  ate_a_porta    <-- sai aqui, 46 minutos depois
14:54:25  preparar_dentro
14:54:28  Alimentando o pet
```

## 6. O diagnóstico: a espera não tinha teto

A grade **não falhou** — ela segurou a refeição e a seguinte veio 26 min depois,
recuperando a cadência. O que falhou foi a **latência até a próxima janela de
alimentação**, e ela era limitada apenas pela cadência de entradas na cave, que
não tem teto.

Duas causas somadas, as duas por desenho:

1. **Um único ponto de alimentação por ecossistema.** BC alimenta em `_do_preparar_dentro`,
   HH em `_do_preparar_dentro`. Nenhum dos dois tem conferência no laço
   principal — a da BC existe, mas **comentada** desde 25/08/2026.
2. **O veto de desmonte fora da cave** (`_preparar_para_agir`,
   `DESMONTAR_FORA_DA_CAVE_SO_SEM_PET`): fora da cave, com o pet ativo, nenhuma
   ação que exija estar a pé acontece. Inclusive a comida.

Enquanto o preparo chega a cada 6,5 min, o desenho é ótimo: a comida sai de graça,
com o personagem já parado e a pé por causa da cura. Ele só quebra na cauda.

### Por que a proposta "flag de fome + só dentro da cave" NÃO resolveria

A proposta avaliada era: o cronômetro liga `pet_needs_food = True`; o Core Loop
lê a flag e alimenta quando `in_cave == True`. Ela foi **recusada nas duas
metades**, e a medição é o motivo:

* **A metade "flag" já existe, e duplicá-la piora.** A fome já está inteiramente
  contida em `_vence_em`: `com fome == agora >= _vence_em`. E já é *latched* de
  graça — só `registrar_alimentacao` move o número. Um booleano ao lado seria um
  segundo estado para o mesmo fato, exatamente o que o cabeçalho de `core/pet.py`
  proíbe desde a primeira versão (*"dois números para a mesma coisa divergem no
  primeiro atraso"*): processo que morre com a flag ligada, flag ligada por um
  ecossistema e lida por outro, flag zerada "para destravar" e a refeição some.
  O que faltava não era estado novo — era uma **leitura que não mutasse**
  (`deve_alimentar` faz a grade nascer, então não serve para o laço).
* **A metade "só dentro da cave" não teria mudado nada neste incidente.** O bot
  passou os 46 minutos em `ATE_A_PORTA`, **fora** da cave. Uma conferência
  condicionada a `in_cave == True` nunca teria disparado.
* **E "dentro da cave" não é sinônimo de "seguro".** Neste bot é quase o
  contrário: `ATE_O_BOSS` e `BOSS` são onde parar custa o trem de mobs. A janela
  boa não é um LUGAR, é um ESTADO — parado e a pé.

## 7. O conserto: a espera passa a ter prazo

**`LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS = 15.0`** (`core/pet.py`). Passado esse
atraso, a comida é dada **onde o bot estiver**, pagando o desmonte.

Os dois lados do número, ambos medidos:

* **Acima da cauda normal** (p90 = 10,8 min), senão dispara em operação saudável
  e o bot desmonta à toa. Dispara em **1 das 127** janelas medidas.
* **Abaixo de um intervalo inteiro** (40..60 min, `config.PET_FEED_MINUTOS_*`),
  porque é ao completar um intervalo de atraso que `registrar_alimentacao`
  **re-ancora** a grade — e aí a refeição do dia é perdida de verdade.

**É esta segunda metade que faz a cota diária fechar.** Com o atraso limitado a
15 min, o ramo "SEM FILA" nunca é alcançado, e as 28,8 refeições/dia de um
intervalo de 50 min deixam de depender de o bot estar no lugar certo na hora
certa. Travado por `test_a_cota_de_28_refeicoes_por_dia_FECHA_com_a_rede`, que
simula 24 h com a janela boa aparecendo a cada 46 min (a duração do travamento
medido) e exige exatamente **28** refeições.

### O que custa

Um desmonte + remonte fora da cave, no máximo uma vez por intervalo. Medido em
`bot/hh/combate.py`: **4,2 s** (desmonte 08:47:36,2 → `Pet ativo` 08:47:40,4).
São 4 s a cada 50 min = **0,13% do tempo**.

A regra de 25/08/2026 combatia **dezenas** de desmontes por trajeto — cura, buff
e comida a cada passo em Stone City. Um desmonte a cada 50 minutos não é a mesma
coisa, e um pet que some custa a run inteira. Por isso o veto virou
**preferência com prazo**, e não foi removido: sem atraso ele continua valendo
integralmente (`test_NO_PRAZO_o_veto_de_fora_da_cave_CONTINUA_valendo`).

### O que NUNCA cede

**A batalha.** Em combate o jogo ignora a tecla de alimento; insistir registraria
uma refeição que não houve — o defeito consertado em 26/08/2026. `in_battle()` é
tri-estado e só `True` barra: "não sei" passa.

## 8. A forma do conserto

```
core/pet.py           A POLÍTICA (pura, testável sem jogo)
                      · esta_com_fome()       leitura derivada, não muta
                      · atraso_minutos()      idem
                      · a_fome_e_urgente()    idem
                      · tentativa_liberada()  cadência anti-rajada
bot/combate.py        A AÇÃO (o que toca o jogo)
                      · cuidar_da_comida_no_laco()  a rede de segurança
                      · feed_pet(em_transito=)      o aperto
bot/hh/routine.py     uma linha no laço principal
bot/bc/routine.py     uma linha no laço principal (a que estava comentada)
bot/app/executor.py   auditoria: ver §9
```

**As leituras são PURAS de propósito.** O laço da HH roda a cada 0,05 s
(`PASSO_DENTRO_DA_CAVE`) — até 20 voltas por segundo. Se a conferência mutasse
ou gravasse, viraria escrita em disco em rajada. Travado por
`test_as_leituras_de_fome_NAO_MUTAM_a_grade`.

**E ela não fala quando não vai agir.** A versão ingênua (chamar `feed_pet` toda
volta, que é o que a linha comentada da BC fazia) logava *"NÃO desmonto para
alimentar o pet"* 20 vezes por segundo durante o trajeto inteiro fora da cave.
Era por isso que a linha estava comentada. Travado por
`test_a_rede_NAO_age_enquanto_o_atraso_esta_dentro_do_prazo`, que exige `linhas
== []`.

**`CADENCIA_DAS_TENTATIVAS_DE_COMIDA = 30.0`** segura a rajada quando a tentativa
falha por algo que o `PetFeeder` não resolve (não desmontei, janela na frente,
personagem morto). Mesmo valor e mesmo motivo de `core/petbug.INTERVALO_MINIMO`.

## 9. A auditoria do APP

**Não havia adiamento para consertar.** O APP não tem veto de cave: ele já
alimenta na primeira volta calma, que é o mais cedo possível em mundo aberto, e
a grade dele já vem do disco desde a Parte I.

O que a auditoria achou foi um **silêncio**. O único bloqueio do APP é a
batalha — correto e não negociável, pela mecânica do jogo. Só que uma conta que
luta sem parar (macro de AoE em ponto cheio) pode atravessar vários vencimentos
sem uma linha de log, e o pet some sem aviso.

Então o APP **acusa em vez de forçar**: `_avisar_se_a_comida_esta_presa()`, no
ramo de batalha do laço vivo, com `CADENCIA_DO_AVISO_DE_COMIDA = 300 s` para dar
uma linha por luta longa em vez de centenas. É o equivalente do
`cuidar_da_comida_no_laco`, com a diferença de que lá a espera tem um veto para
furar e aqui tem uma mecânica do jogo, que não se fura.

## 10. Cobertura de estados, depois do conserto

| situação | antes | depois |
|---|---|---|
| HH/BC, preparo de entrada chega em 6,5 min | alimenta | alimenta (inalterado) |
| HH/BC, preso fora da cave 46 min | **fome** | alimenta aos 15 min de atraso |
| HH, run retomada no meio da cave (pula o preparo) | **fome até a próxima entrada** | alimenta aos 15 min de atraso |
| BC, ciclo de venda longo | **fome** | alimenta aos 15 min de atraso |
| HH/BC, em travessia (`em_transito`) | n/a | espera; fura o prazo se passar de 15 min |
| HH/BC, em batalha | não alimenta (grade intacta) | idem, e agora em silêncio no laço |
| APP, fora de batalha | alimenta | alimenta (inalterado) |
| APP, batalha sem fim | **fome silenciosa** | alimenta quando sair; avisa a cada 5 min |

## 11. O que continua ABERTO depois desta rodada

* **`LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS` é derivado, não medido de frente.**
  Ele vem da distribuição das janelas (p90 = 10,8) e do limite da grade (40 min),
  não de uma medição da fome real do pet no jogo. **A medição que falta é a do
  jogo**: quantos minutos o pet aguenta sem comer antes de sumir. Com esse número
  o limite deixa de ser inferido.
* **Continua sem confirmação de que o item foi consumido** (§4). A rede de
  segurança reduz a latência, mas não sabe se a tecla fez efeito.
* **`vale_alimentar_antes_de_entrar` continua morta.** Agora com um agravante:
  ela resolvia, de forma pior, o problema que a rede de segurança resolve.
  Candidata a remoção na próxima limpeza.
* **`apply_buffs` continua apertando uma vez e acreditando** (§4).

## O PET NÃO ESTAVA LÁ — 17/09/2026

### O que o teste do usuário mostrou

Conta `creubo`, HH, comida a cada 50 min, 20 horas de farm:

| | |
|---|---|
| refeições registradas | **26**, intervalos de 47 a 53 min |
| comida saindo da bolsa | **sim**, o usuário viu a quantidade cair |
| felicidade | **94 → 45** |

E a alimentação de 16/09 às 21:20, que levou o pet de 78 para 100, **foi à mão**:
*"eu alimentei o pet manualmente, não foi o bot"*.

### A medição que fechou

Cruzando o log de dev com o horário da entrada na cave:

    00:49:28   4,0 s depois de "Entrada na HH confirmado"
    01:38:48   3,0 s depois
    02:25:25   5,0 s depois
    03:16:11   4,0 s depois

**Toda alimentação automática acontece 3 a 5 segundos depois de o personagem
entrar na instância.** Ao trocar de mapa o servidor RECRIA o pet no mundo novo;
naqueles segundos a tecla sai, o item é consumido, e não há a quem dar.

### Por que o APP nunca teve o problema

Ele não troca de mapa. Alimenta no meio da macro, com o pet no mundo há horas —
e era o único ecossistema que mantinha a felicidade alta. A pista estava na
pergunta do usuário desde o começo.

### As duas correções anteriores não eram erradas — eram insuficientes

| data | o que se achou | o que era |
|---|---|---|
| 27/08 | a montaria saía 600 ms depois da comida | verdade, e foi encurtado para 1,5 s |
| 16/09 | a montaria saía 1,65 s depois — 150 ms fora da janela | verdade, e virou barreira de 4 s |
| 17/09 | **o pet ainda não estava no mapa** | a causa raiz |

As duas primeiras protegiam o item de ser CANCELADO. Esta protege o item de ser
gasto num mundo onde o pet ainda não voltou. São defeitos diferentes no mesmo
gesto, e os três consertos convivem.

### Como ficou

1. **`UIDoJogo.esperar_a_chegada` marca a troca de mapa** (`pet.trocou_de_mapa`).
   É o único ponto por onde passam entrada, saída e teleporte.
2. **`PetFeeder.deve_alimentar` recusa** enquanto o mapa tiver menos de
   `SEGUNDOS_NO_MAPA_ANTES_DE_ALIMENTAR` (30 s) — **e a grade NÃO avança**, que
   é o que impede a refeição de ser dada por perdida.
3. **Nem a urgência fura a regra.** Comida queimada não alimenta nem atrasada.
4. **A segunda chance é no ponto do boss**, depois do loot: personagem parado, a
   pé, fora de combate, mapa com minutos de vida. É o momento que mais se parece
   com a alimentação manual que funcionou.

### Os 30 segundos

Não são medidos — são conservadores por assimetria, a mesma lógica da barreira
da montaria: alimentar cedo demais **queima a refeição inteira**, e esperar meio
minuto numa run de vários minutos não custa nada. Quem quiser medir: baixe até a
felicidade voltar a cair depois de um dia de farm.

### Travado por

`tests/test_comida_depois_da_troca_de_mapa.py` — **desde 25/09/2026**. Até ali
esta frase citava `tests/test_comida_do_pet.py`, e ele não tinha nenhum destes
testes: a guarda foi para produção sem a trava que esta ata anunciava. O que
ninguém pode desfazer sem o teste reprovar: a recusa logo depois da troca de
mapa, a grade que não avança nessa recusa, e a chamada no ponto do boss.

## O BC ficava de fora — 25/09/2026

A frase "`UIDoJogo.esperar_a_chegada` é o único ponto por onde passam entrada,
saída e teleporte" era **falsa para o BC**. A entrada do BC tinha um laço de
espera próprio (`_reconhecer_entrada`), e a saída era um `tick(1.5)` cego — nenhum
dos dois marcava a troca de mapa. Então a comida do `_do_preparar_dentro`, segundos depois
da entrada, saía com o pet sendo recriado: o mesmo mecanismo que derrubou a
felicidade de 94 para 45 na HH. E o BC não tinha a 2ª chance no ponto do boss.

Achado pela auditoria de 25/09/2026, lendo o código — nenhuma conta rodou BC no
período dos logs. A causa foi a duplicata: o laço copiado deixou de chamar o
efeito colateral que o ponto comum chamava.

Como ficou: as duas transições do BC passam pelo `esperar_a_chegada` (a entrada
com `em_disputa=True`, a saída com o mesmo 1,5 s agora como teto de pergunta), e
o `_do_boss` do BC dá a comida **por último, depois do `package_courage` e antes
de montar** — regra do usuário: *"faça a ação antes de ativar a montaria"*.

## Os 30 segundos, em medição — 25/09/2026

Os 30 s da guarda não são medidos: são conservadores por assimetria. O ideal do
usuário é a comida sair SÓ na entrada, e o que impede é justamente esse tempo —
na entrada, a refeição é recusada e vai para o pós-boss.

`core/pet.MEDIR_A_VOLTA_DO_PET = True`: cada troca de mapa confirmada amostra o
`pet_active()` por 30 s numa thread à parte (leitura de ponteiro sem estado) e
grava uma linha com os trechos. `python -m blazesbot.tools.medir_a_volta_do_pet`
julga: se o sinal some e volta de forma consistente (80% de 30 trocas), os 30 s
fixos viram uma espera por ele, com teto na cauda medida — e a comida pode voltar
para a entrada. Se fica `True` o tempo todo, a leitura não enxerga a recriação do
pet e os 30 s ficam. Travado por `tests/test_medicao_da_volta_do_pet.py`.
