# Time do APP — a mesma macro em até cinco contas ao mesmo tempo

> **Pedido do usuário em 27/08/2026.** *"quero fazer um sistema de sincronização,
> onde eu posso escolher até 4 outras contas cadastradas e todas vão rodar a
> macro daquela conta, de forma sincronizada, para que sempre ataquem juntos,
> façam todas as verificações juntos e sempre voltem para o mesmo ponto
> inicial."*
>
> Este arquivo guarda o **porquê**. A regra que não pode ser violada está em
> `docs/INVARIANTES.md`, seção "Time do APP".

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

## Os blocos, na ordem

| # | bloco | estado |
|---|---|---|
| 1 | Campos `time_logins` / `time_modo` no `AppConfig`, ponte web, testes | **feito** |
| 2 | Aba APP em duas colunas + painel do Time na direita + `npm run build` | a fazer |
| 3 | Promoção do `team.py`: mural e mecânica do jogo para `bot/`, política do reset fica em `bc/` | a fazer |
| 4 | As duas ferramentas de medição | a fazer |
| 5 | Sincronia: mural do time, injeção no supervisor, largada no executor | a fazer |

A ordem não é gosto: **2** precisa dos campos de **1**; **5** precisa do mural de
**3** e dos números de **4**. Cada bloco fecha com a suíte inteira e uma revisão
do Codex.
