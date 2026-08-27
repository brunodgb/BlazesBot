# Comida do pet — o porquê medido

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
`_do_curar` é **montar**. Ou seja: **600 ms depois de apertar a comida o bot
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
comido"*. **O BC não tinha essa guarda**, e `_do_curar` roda logo depois de
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
* **`feed_pet` do BC tem um único chamador**, `_do_curar`
  (`bc/routine.py:1165`). A checagem no laço principal está **comentada** e não
  em interruptor (`bc/routine.py:2518`). Consequência: conta que não completa
  entradas na cave nunca come. Mantido por decisão do usuário em 27/08/2026 —
  *"talvez até esta executando a função que deve continuar dentro do `_do_curar`
  como está hoje"*.
* **`CombatEngine.vale_alimentar_antes_de_entrar` é código morto** (zero
  chamadores). Sobrou da alimentação pré-entrada removida em 25/08/2026.
* **`apply_buffs` também aperta uma vez e acredita**, e também não garante a
  página. Não foi tocado nesta rodada porque o usuário não relatou buff falhando
  — mas é o irmão gêmeo do defeito consertado aqui.
