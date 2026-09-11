# Sistema: janela, log, hotbar, testes — decisões e medições

> Recortado do `CLAUDE.md` em 14/08/2026, **verbatim**. O
> `CLAUDE.md` guarda a REGRA em uma ou duas linhas e aponta para cá; aqui
> fica a MEDIÇÃO que sustenta cada uma. Leia antes de mexer nesta área —
> quase toda decisão aqui já foi tentada do outro jeito e reprovou.

- **Pino de janela (hwnd, pid) por conta — interno e invisível.** Cada conta
  guarda no `config.json` o par `(hwnd, pid)` da janela que ela abriu
  (`last_hwnd`/`last_pid` no `Account`, campo serial — NÃO aparece em nenhuma
  interface, só existe no arquivo). Ao adotar janela, `_adotar_janela_existente`
  tenta PRIMEIRO o pino salvo (`_validar_hwnd_salvo`: `IsWindow` + o hwnd
  pertence ao mesmo pid salvo + pid ∈ `client_pids()` + título começa com
  "Talisman Online" ou já foi batizado por nós) — roda em QUALQUER sessão,
  ignorando `_primeira_sessao`, e é o único jeito de reconhecer a janela NO MEIO
  do login (sem nick legível, título genérico). O pino é gravado (só quando muda,
  via `remember_window`) nos três caminhos de aquisição — adota existente,
  reutiliza cliente aberto, lança cliente novo; é APAGADO (`forget_window`)
  quando a validação falha, quando `_encerrar_caido` mata o cliente, ou quando a
  memória lê um nick diferente (a janela passou a ser de outra conta — não
  roubar). Se duas contas tiverem o mesmo pino, a primeira a assumir fica com a
  janela e a segunda apaga o próprio pino e abre cliente novo. Nick lido na
  memória vale mais que o pino: bate = assume; difere = não reclama.
- **Log: dois ambientes, separando o que é do usuário do que é de dev.** A
  execução se configura por variável de ambiente `BLAZES_MODO` (`dev` | `prod`,
  default `dev`), resolvida UMA vez por processo em `blazesbot/core/logmodo.py`
  (cache proposital — o env não muda durante a vida do processo). O nível do
  logger raiz `blazes` é `DEBUG` em dev (se `verbose`) e `INFO` em prod, setado
  em `setup_logging()` (`main.py`, usado pela PyQt6; `web_app.py` o importa com
  `verbose=True`).
  - **O que o USUÁRIO vê** (todos os ambientes): os arquivos legíveis
    (`logs/sessao-atual.log`, `logs/blazesbot.log`) e a tela de log na
    interface — texto simples, leve, sem o detalhe de dev.
  - **O que é SÓ do DESENVOLVEDOR** (criado por `LogJsonHandler` em
    `blazesbot/core/log_json.py`, anexado SOMENTE em modo dev): o arquivo
    estruturado `logs/dev/blazes-dev.jsonl`, uma linha JSON por registro,
    enriquecido com contexto do `logmodo` (`conta`, `id_run`, `fase` —
    thread-local) + o que o `LogRecord` carrega (`arquivo`, `linha`, `funcao`,
    `thread`, `exc` completo). Em prod a pasta `logs/dev/` nem é criada — o
    detalhe de dev só existe na máquina de quem desenvolve. O sink reusa a
    poda por linha do `ArquivoDeLogLimitado` (`LOG_JSON_MAXIMO = 4000`).
  - **Correlação:** em `routine.py`, a cada run o contexto ganha um
    `id_run` (`uuid.uuid4().hex[:10]`) via `logmodo.contexto(conta, id_run)` e
    `logmodo.fase(...)` no laço principal, dando um ID único para rastrear uma
    run inteira pelo JSON (ob. request-ID do DevOps checklist). O contexto é
    thread-local (cada conta roda na própria thread) e é limpo no `finally` do
    `run()`.
  - **Interface:** mudar o nível de DEBUG↔INFO ao vivo só em modo dev. Na web
    o checkbox "detalhado" no cabeçalho do log (chama
    `Api.definir_nivel_log`); na GUI o `ck_debug` — em prod o checkbox aparece
    desmarcado e desabilitado e o nível fica preso em INFO.
  - **Regra de trabalho (pedido do usuário, valendo sempre):** ao investigar
    qualquer problema, analisar PRIMEIRO os logs atrás (o `logs/dev/blazes-dev.jsonl`)
    para ver se há indício que ajude, antes de mexer no código.
- **A barra de atalhos tem uma TECLA opcional** (`KeyBinds.hotbar_page_1`,
  rotulada **"Atalho Hotbar 1"** na aba Teclas > Interface & Sistema, nas DUAS
  interfaces, com um "?" próprio explicando o passo a passo no jogo — ESC >
  Keys > "Main Hotkey Page 1", e apagar as teclas de Page 2 e 3). O jogo deixa ligar uma
  tecla a cada página da barra; a da página 1 leva **direto ao destino, com um
  toque**, enquanto o clique precisa de dois justamente porque só sabe subir um
  degrau por vez. **Vazia por padrão** — sem ela o bot faz exatamente o que
  sempre fez. Tendo tecla, ela é usada em TODOS os pontos (os seis momentos do
  farm e o APP).
  - **A recarga de 10 s só vale para o CLIQUE.** Ela existe porque os momentos-
    chave vêm em rajada e dois cliques repetidos custam tempo e ruído; um toque
    não tem esse custo, e pagar por ele com o risco de a barra ficar na página
    errada seria trocar o barato pelo caro. Medido: 6 chamadas seguidas dão 2
    cliques (recarga cortando) ou 6 teclas.
  - **`ir_para_a_pagina_1(clicar, ponto, esperar, apertar, tecla)`** substituiu o
    `subir_para_a_pagina_1` e devolve `"tecla"` ou `"clique"` para o log. As duas
    portas continuam (`garantir_pagina_1(ctx, ...)` para o farm).
- **No APP a página 1 é garantida na largada E antes de CADA volta.** Uma vez na
  largada não bastava: a sequência roda em laço por horas, e um clique do usuário
  na barra estragaria todas as voltas seguintes sem ninguém perceber. O executor
  recebe `antes_da_volta` como FUNÇÃO, pelo mesmo motivo do pet — `modo_app`
  importa só `core.inputs` e continua assim; quem monta o clique/tecla é o
  `supervisor`, dentro de `try/except` (é complemento: sem ele a macro roda como
  sempre rodou).
- **A barra de atalhos tem que estar na PÁGINA 1** (`blazesbot/bot/hotbar.py`,
  módulo independente usado pelo BC e pelo APP). O jogo tem 3 páginas e uma bola
  verde no rodapé mostra qual; as teclas configuradas apontam para os slots da
  página 1, e em outra página a MESMA tecla dispara outra coisa — sem o bot
  perceber.
  - **Clica, não lê.** O botão de subir (`coords.hotbar_page_up`, medido em
    (539,733) contra quatro prints, erro máximo de 5 px num botão de 22×22)
    **sobe e PARA no 1**: 3→2→1, 2→1→1, 1→1→1. Então 2 cliques levam à página 1
    de qualquer lugar, inclusive já estando nela — não existe reconhecimento que
    possa errar. Ler o dígito é possível (máscara da tinta azul sobre o verde
    separa 1/2/3 com margem de 0,60–0,77; casar a bola INTEIRA não serve, a
    moldura domina e a margem cai para 0,037), mas só economizaria dois cliques.
  - **Sete momentos-chave**, não a cada tecla: a **entrada na cave**
    (`routine._do_entrar`, logo depois do `begin_run`, com `forcar=True` — a
    entrada é a fronteira certa, tudo daí em diante depende das teclas, e a
    disputa pode ter levado minutos com o usuário mexendo na janela); `_descer_para_lutar` (guardas e
    boss, com `forcar=True` — ali a tecla errada custa a run), o portão da
    montaria, `ensure_pet`, `curar_antes_do_boss` (só depois do portão dos 40%) e
    o início do modo APP. O inventário do package_courage ficou de fora por
    decisão. Pôr no `ctx.press` custaria ~3 s de captura por luta de boss.
  - **Recarga de 10 s** no caminho com `ctx` (mesmo desenho do `resetar_visao`):
    o portão da montaria é chamado por trajeto, e a manobra de destravamento abre
    até 6 trajetos curtos seguidos — sem recarga seriam 12 cliques em segundos.
  - **Duas portas, para não quebrar o isolamento do APP:**
    `garantir_pagina_1(ctx, ...)` para o farm e `subir_para_a_pagina_1(clicar,
    ponto)` para quem não tem `BotContext`. O executor do APP continua
    importando só `core.inputs` — quem monta o clique é o `supervisor`, e dentro
    de `try/except`: é complemento, e sem ele a macro roda como sempre rodou.
- **Rede de segurança além do `verificar.py`:** `tests/` tem a suíte de
  **pytest de lógica pura** (`coords`, `logmodo`, `stats_diarias`,
  `log_limitado`, `mapa_bc`) — rode
  `./.venv/Scripts/python.exe -m pytest -q` depois de mexer nesses módulos.
  **ruff** (`./.venv/Scripts/python.exe -m ruff check blazesbot/ main.py --fix`)
  aplica só correções seguras; as categorias intencionais (S110 try/except pass,
  UP042 `str+Enum`, B023, DTZ011, UP031...) estão documentadas no `ignore` do
  `pyproject.toml`, então o `check` fecha em 0 sem refatorar estrutura.
- **O plugin ECC (hooks) está com escopo `project` apontando para a pasta temp
  do Claude, não para o repo** — é por isso que o GateGuard ("Fact-Forcing
  Gate") e afins podem bloquear edits/setup aqui. Se atrapalhar trabalho de
  manutenção, rode a sessão com `ECC_GATEGUARD=off` (ou remova
  `gateguard-fact-force` de `ECC_DISABLED_HOOKS`). Reinstalar o plugin em escopo
  `user` resolve de vez.
- **Desligar o BC pela interface é IMEDIATO e não derruba a conta:** desmarcar o
  checkbox (`bc_farm` → False) corta a fase atual NO MEIO (navegação, combate,
  entrada, venda). O sinal é a exceção `FarmDesligado`, levantada em
  `BotContext.raise_if_stopped` quando a flag `ctx.farming` está ativa (True
  SOMENTE durante `routine.run`) e `account.farms` apagou; como navigation e
  combat não têm `except`, ela sobe limpa até o `routine.run`, que a captura e
  devolve o controle sem `_fail`. A conta então fica **online, parada, com o
  relogin ativo** (o `_operate` muda para "Online, sem farmar") — o usuário
  pode assumir manualmente sem parar o bot inteiro. O `finally` do `run()`
  derruba `ctx.farming` em qualquer saída, senão o laço "online" seguinte
  re-detonaria a parada. Retomar (re-marcar) usa o SITUAR atual, que já
  funciona. Nenhuma mudança de UI: os dois checkboxes já gravam
  `conta.bc_farm` ao vivo no mesmo objeto de config.
- **Trava de posição no APP (2026-08-16):** salva `(x, y)` ao iniciar
  `_rodar_modo_app` e devolve o personagem andando (sem montaria) se ele se
  afastar mais que `TOLERANCIA_POSICAO = 1` unidade — o mesmo `RUIDO_DA_POSICAO`
  usado na navegação da cave. O deslocamento é medido no eixo que maior se
  desviaa: `dx > 1` OU `dy > 1` dispara a devolução. Após
  `shuffle_apos_n_voltas` (30) voltas sem movimento, dá um shuffle de
  `SHUFFLE_DEFAULT_PIXELS = 6` unidades no eixo X e volta à base — anti-AFK
  leve, visível no minimapa como um "tremulação". A base é zerada a cada
  (re)início do APP: o usuário relociona e clica para voltar. Toda a leitura
  de posição e o clique no minimapa chegam do `supervisor` como callbacks
  (`posicao_atual`, `mover_para`), preservando o isolamento do executor
  (`core.inputs` + `core.pet` só). Sem leitura de memória, os callbacks são
  `None` e o APP segue exatamente como antes — nada quebra.
  - **Devolução ao término da macro (2026-08-16):** quando o laço do `rodar()`
    termina (`continuar()` devolve False), o executor chama `mover_para(base)`
    uma última vez. Isso cobre o caso em que o usuário para a macro depois de
    andar — o character volta ao ponto de onde começou. Se a base não foi salva
    (sem leitura de memória) ou o callback é `None`, nada acontece — o
    encerramento segue como sempre fez.
  - **Diagnostic log (2026-08-16):** `_salvar_base`, `_corrigir_posicao` e
    `mover_para` emitem logs de INFO/DEBUG/WARNING que mostram: `base salva em
    (x, y)`, `atual=X base=Y dx=N dy=N`, `mover_para: clicando minimapa
    (px,py)`. Confira `logs/dev/blazes-dev.jsonl` com `BLAZES_MODO=dev`.

---

## A tecla vazando para outra janela no login (25/08/2026)

**O relato:**

> *"no login tem vezes que o clique das teclas está vazando, na verdade parece
> até ser outras teclas bem aleatórias... por exemplo `rggddwlqrjcrw` digitou
> isso no bloco de notas enquanto abria o jogo e foi sozinho, eu percebi isso
> pois teve vezes que do nada no jogo começou a abrir janelas aleatórias e
> quando cliquei em outro lugar começou a digitar e quando a conta logava
> parava."*

### Como isso é possível, se o bot usa `PostMessageW`?

`PostMessageW` entrega a UMA janela. Não existe vazamento por foco — o bot não
usa `SendInput` nem `keybd_event` em lugar nenhum (varrido: **nenhuma mensagem
de teclado sai fora do `core/inputs.py`**). Então o `hwnd` estava errado. Três
jeitos de isso acontecer:

1. **O Windows RECICLA HWND.** A janela do cliente morre — queda, relogin,
   cliente fechado — e o Windows entrega o MESMO número de handle a outra
   janela. O `Input` guardava o `hwnd` no `__init__` e **não conferia nunca
   mais**. A partir daí, `PostMessageW(hwnd, WM_CHAR, ...)` digita no Bloco de
   Notas.
2. **`hwnd = 0xFFFF` é `HWND_BROADCAST`** e entrega a TODAS as janelas de topo.
   Explicaria os dois sintomas ao mesmo tempo: texto no Bloco de Notas E painéis
   abrindo no jogo.
3. **Um `hwnd` de outra conta** faz uma conta digitar na janela da outra.

**Por que no login:** é onde a janela está NASCENDO (o supervisor pode ter o
handle de antes), e a digitação de usuário/senha é o trecho com mais teclas
seguidas do bot inteiro. *"Quando a conta logava parava"* — porque a digitação
acabou.

### A trava

`Input._janela_confiavel()`, chamada ANTES de cada mensagem, nos **três** pontos
de saída — `_enviar_tecla` (toda tecla), `_click` (os oito caminhos de clique) e
`set_title`. Confere que o `hwnd`:

* não é zero, não é negativo, não é `HWND_BROADCAST`;
* ainda é janela viva (`IsWindow`);
* **ainda pertence ao mesmo PID** de quando o `Input` nasceu;
* e esse PID é um `client.exe`.

Falhou qualquer uma, **a mensagem não sai** e o motivo vai para o log — uma vez
por motivo, não por mensagem, senão uma senha vira 13 linhas iguais.

### As duas armadilhas que a trava tinha que evitar

Estas duas custaram mais pensamento que a trava em si, e as duas são a mesma
ideia: **trocar um defeito raro por um permanente é o pior negócio possível.**

1. **"Não sei" não é "não é o jogo".** Se o `psutil` levantar `AccessDenied` ao
   ler o nome do processo e isso valesse "não é o jogo", o bot ficaria MUDO. O
   nome do processo só bloqueia quando é lido com sucesso E é diferente; leitura
   falhada mantém o que já se sabia. O pino do PID sozinho já segura o defeito
   relatado.
2. **O pino fecha TARDE.** No login a janela está nascendo e pode não dizer de
   quem é ainda. Fixar `None` como pino e comparar contra ele travaria tudo para
   sempre. Então o pino se fecha na primeira leitura que der certo — e a
   identidade é conferida ANTES de fixar, senão o pino fecharia no Bloco de
   Notas e a trava viraria decoração.

Travado por `tests/test_trava_da_janela.py` (21 testes), incluindo uma varredura
de AST que reprova qualquer módulo que mande mensagem de TECLADO fora do
`Input` — um ponto de saída novo sem `_janela_confiavel` é um vazamento novo.


## O diagnóstico fino do APP — 06/09/2026

> *"Vamos tentar trackear todo tipo de problema com vários logs em vários pontos
> que você considerar que pode ser problemático, pois assim vamos ter
> comprovações e conseguir tomar medidas mais precisas do que fazer, mas pode
> ser log dev, não precisa mostrar tudo na UI."* — usuário

`core/diagnostico_fino.py` é um interruptor só (`LIGADO`) e um `anotar()` que
prefixa tudo com **`DIAG:`** — o prefixo é o que permite separar medição de
operação com um `grep`, sem depender do nível do log.

### O que passou a ser medido, e por quê

| ponto | linha | a pergunta que ela responde |
|---|---|---|
| aquisição | `DIAG: ALVO ... mob->base=N mob->personagem=N` | **o problema é o spot ou o bot?** A régua compara o mob com a BASE, e só com isso não dá para separar "mob longe de mim" de "eu longe da base" |
| saída de batalha | `DIAG: SAIDA DE BATALHA: a flag baixou N.NNs depois de o alvo cair` | os 2 s do teto são generosos ou apertados? O teto foi posto **antes** de existir esta medição |
| volta | `DIAG: VOLTA completa em N.Ns` / `VOLTA cortada: <motivo>` | quanto tempo cada volta custa, e qual saída domina |
| morte | `DIAG: MORTE #N \| posição=... \| em batalha=... \| distância do ponto=...` | morri no meu spot com adds, ou longe, arrastado? |
| retorno | `DIAG: RETORNO ok/FALHOU em Ns \| distância antes=... depois=...` | a volta ao ponto funciona, e quanto custa |
| Fada (reviver) | `FADA/REVIVER: clique N ... id esperado=... lido=...` | o clique no retrato pega? É o dado que explicou os 1583 cliques "em outro alvo" |

**Nenhuma dessas linhas muda comportamento**, e o diagnóstico da morte é
explicitamente à prova de falha: leitura que explode vira `"?"` em vez de
derrubar o ciclo — log de medição que leva a macro junto seria pior que não
medir.

### A vizinhança da morte — fechado em 06/09/2026

**Quantos mobs estavam em cima** era o ponto que faltava, e é o que separa
*"morri com um mob só, então é dano ou cura"* de *"morri com quatro em cima,
então é o spot ou a corrida"*.

Ele lê `entidades_vivas()` e conta quem está a até `RAIO_DA_VIZINHANCA` (40) do
personagem, no instante da morte:

```
DIAG: MORTE #1 | mobs vivos a até 40: 4 [Guly Horn Horse@6, Evil Apprentice@11, ...]
```

**A leitura é aberta e fechada ali mesmo.** O `Memory` do modo APP é um local do
supervisor, e puxá-lo até o ciclo da morte obrigaria a mexer na montagem inteira
por uma linha de log — uma morte por vez, um handle por morte, e um `finally`
que garante que ele não vaza. Como todo o resto do diagnóstico, ele **nunca
levanta**: falha vira texto (`vizinhança=? (motivo)`), porque diagnóstico que
derruba o ciclo da morte é pior que diagnóstico nenhum.


## O LOG DE DEV SE LIMPAVA UMA VEZ POR PROCESSO (06/09/2026)

### Os dois defeitos, e eles são independentes

**1. A retenção existia no papel.** `_limpar_arquivo_morto` era chamada só no
`__init__` do handler — uma vez por processo. O bot fica ligado por dias. Estado
encontrado em 06/09, com o processo no ar desde a véspera:

```
blazes-dev-2026-08-31.jsonl.gz     2,3 MB
blazes-dev-2026-09-01.jsonl.gz     2,7 MB
blazes-dev-2026-09-02.jsonl.gz     2,5 MB
blazes-dev-2026-09-03.jsonl.gz     2,0 MB
blazes-dev-2026-09-04.jsonl.gz     1,0 MB
blazes-dev-2026-09-05.jsonl.gz     1,1 MB   <- nunca comprimido pelo processo
blazes-dev-2026-09-06.jsonl      312,8 MB   <- o do dia, sem comprimir
                                 -------
                                 324,4 MB
```

Com `DIAS_DE_ARQUIVO_MORTO = 7` nada tinha vencido ainda — mas a compressão de
ontem também não tinha acontecido, e ela é 32×. O desenho estava certo; o
gatilho é que nunca era puxado de novo.

**2. Sete dias de retenção contaminaram um veredito.** Em 06/09 uma auditoria do
ponteiro de nome do alvo varreu a pasta inteira — 1.160.883 linhas — e concluiu:

| leitura | ocorrências |
|---|---|
| `nada` (ilegível) | 701 — **50,4 %** |
| `['Gun Witch']` | 619 |
| `['Cemetery Guard']` | 62 |
| `['Blaze Skull Marshal']` | 7 |
| `['PDtery Guard']` | 1 — corrompida |

Só que `d9bc023` (*"o nome do alvo sai certo em 100% das leituras, não em 21%"*)
e `1a5b19c` (*"o alvo resolve em 100%, e não em 62%"*) entraram em **01/09 às
15:20 e 15:34**. Metade da amostra era de antes deles. Refeita na janela de dois
dias (231 leituras):

| leitura | ocorrências |
|---|---|
| `['Gun Witch']` | 111 — 48,1 % |
| `nada` (ilegível) | 108 — **46,8 %** |
| `['Cemetery Guard']` | 11 |
| `['Blaze Skull Marshal']` | 1 |

**O veredito não mudou** (nome ainda não serve de juiz único), mas o NÚMERO
mudou, e a leitura corrompida saiu da janela — ela era do período contaminado.
A lição não é sobre este número: é que média de dois mundos não descreve nenhum
dos dois.

### O que ficou

`DIAS_DE_ARQUIVO_MORTO = 7 → 2`, e a varredura passa a rodar de hora em hora
(`INTERVALO_ENTRE_LIMPEZAS = 3600`) numa **thread daemon**, disparada do `emit`
por um portão de tempo. A thread não é enfeite: `emit` roda com o lock do
handler segurado, e um gzip de centenas de MB ali dentro pararia o log de todas
as contas.

Duas guardas entraram junto, e as duas são sobre não perder evidência:
`SEGUNDOS_DE_SILENCIO_ANTES_DE_COMPRIMIR = 60` (na virada da meia-noite o
arquivo de "ontem" ainda pode receber a anexação de uma poda começada antes das
00:00, e `_comprimir` copia e apaga o original), e uma trava que impede duas
varreduras simultâneas.

### Alternativas reprovadas

| alternativa | por que não |
|---|---|
| Varrer a cada poda | O comentário original já dizia por que não: a resposta muda uma vez por dia, e varrer a cada 100 linhas é custo de disco repetido para nada. |
| Varrer dentro do `emit`, síncrono | `emit` roda com o lock do handler. Comprimir 300 MB ali para o log de todas as contas. |
| Thread permanente com `sleep` | Uma thread viva o tempo todo para acordar de hora em hora. A de vida curta faz o mesmo e morre. |
| Retenção por BYTES | Dia é a unidade em que se pensa sobre isto ("o que aconteceu ontem à noite"). Byte não é — e o volume por dia varia 10× conforme o que está sendo depurado. |
| Manter 7 dias e filtrar por data na consulta | Depende de quem consulta lembrar de filtrar. Foi exatamente o que não aconteceu na auditoria que errou. |

## 09/09/2026 — 918 caracteres de lixo digitados no Bloco de Notas

Relato: durante um laço de relogin, o bot foi gerando uma string de letras
minúsculas aleatórias, ~10 caracteres por tentativa de login. O usuário a
capturou porque **o Bloco de Notas estava em foco e recebeu tudo**:

```
dcgspkjpxfeublmmumyvpcbbwjvkdrqwzzxsvcfgtmgiviiuzlvsqiuekskvyoggokjodgnuoc... (918)
```

### O que a evidência dizia antes de qualquer leitura de código

Três fatos, e cada um elimina uma família inteira de hipóteses:

1. **Chegou ao Bloco de Notas.** `PostMessageW` e `SendMessageW` entregam a
   **um** `hwnd`. Para o caractere aparecer noutro programa, o `hwnd` que o bot
   usava **era** do outro programa. Isso aponta direto para o handle reciclado —
   o defeito que a trava de janela existe para impedir.
2. **~10 caracteres por tentativa**, acumulando. 918 / 10 ≈ 92 tentativas, que a
   ~19 s por relogin dá ~29 min. Bate com o laço observado.
3. **Estatística da string:** 918 caracteres, alfabeto `b`–`z` (**a letra `a`
   não aparece uma única vez**), entropia 4.620 bits/char contra log₂(25) =
   4.644, vogais em 14.2% (texto natural fica perto de 40%), 466 bigramas
   distintos em 917 — ou seja, **uniforme e sem repetição**.

### O que foi DESCARTADO por medição

* **Gerador de string aleatória no bot.** Não existe: `random.choice`,
  `ascii_lowercase` e `ascii_letters` não aparecem em lugar nenhum do pacote.
* **Biblioteca de entrada global.** `pyautogui`, `keyboard`, `pynput` e
  `pydirectinput` **não estão nem instalados**, e não há `keybd_event` nem
  `SendInput` em `blazesbot/`. `MODO_DE_TECLA = "postmessage"`.
* **Laço de limpeza mapeado na tecla errada.** `clear_field` sempre resolveu
  `"BACKSPACE"` por `VK_CODES` → `0x08`. Nunca digitou letra.
* **Programa vizinho.** O `T-R0XX Auto Login` também usa `SendMessage`
  direcionado (`keyboard.write` → `WM_CHAR` no `hwnd`), e não estava em
  execução. `petbug.ATIVADO = False` barra o patcher de terceiro.

### A causa: o PINO TARDIO liberava sem prova

Em `Input._motivo_para_nao_enviar`:

```python
nome = _nome_do_processo(dono)
if nome is not None and nome != NOME_DO_PROCESSO_DO_JOGO:
    return "a janela é do processo X, não de client.exe"
self._pid_da_janela = dono          # fecha o pino
return None                         # e LIBERA o envio
```

`nome is None` significa **"não consegui ler o processo"**, e caía no caminho do
`None` de retorno — ou seja, **liberava**. Pior: `self._nome_do_processo` ficava
`None` para sempre, e a conferência periódica mais abaixo é
`if self._nome_do_processo is not None and != ...` — **nunca mais disparava**. O
`Input` ficava permanentemente preso a uma janela que ninguém provou ser o jogo.

No laço de relogin isso é o cenário exato: o cliente morre no meio do login, o
Windows recicla o valor do HWND, o `Input` seguinte nasce com um handle que
agora é de outra janela — e a leitura do processo falha justamente porque tudo
está mudando ao mesmo tempo.

### A correção é uma DISTINÇÃO, não uma trava nova

"Não sei" tem dois significados, e eles não podem ter o mesmo desfecho:

| momento | "não sei" | por quê |
|---|---|---|
| **ESTABELECER** o pino | **BLOQUEIA** | nunca houve prova de que é o jogo; ficar mudo alguns ciclos é reversível, senha no programa errado não é |
| **MANTER** um pino já confirmado | **não bloqueia** | comportamento original, intacto: `AccessDenied` passageiro não pode emudecer o bot |

A segunda linha é `core/injecao_de_texto.py`, que confere **conteúdo** onde a
trava confere **destino**: teto de 50 caracteres (recusa por exceção, não
trunca), recusa de caractere de controle, e reconferência da janela **a cada
caractere** — antes, `_enviar_tecla` barrava mensagem por mensagem em silêncio
e o laço ia até o fim.

### O que continua sem explicação, e está registrado de propósito

**Por que as letras eram aleatórias e por que o `a` nunca aparece.** O login
digita duas strings fixas (`account.login` e `get_password()`); texto repetido
daria bigramas repetidos, e a medição mostra o contrário. A trava fechada
impede o vazamento independentemente da resposta, e a próxima ocorrência agora
deixa rastro: a recusa sai no log com o rótulo (`login`/`senha`) e o tamanho,
sem nunca mostrar o texto.

## 11/09/2026 — o SHIFT do navegador entrava no jogo em segundo plano

Relato: com o jogo em **segundo plano** e o usuário segurando SHIFT no
navegador por alguns segundos, o cliente passava a ler "SHIFT + tecla do bot".
O comando virava outro e a skill não saía.

### A função existia e não funcionava

`Input._liberar_modificadores_fisicos` já mandava `WM_KEYUP` para SHIFT, CTRL e
ALT antes de cada tecla alvo. Ela não tinha efeito porque `_enviar_tecla`
chumbava `LPARAM(0)` — e **um `WM_KEYUP` com `lParam` zerado é malformado**.

O `lParam` de uma mensagem de teclado não é campo livre: é um registro de bits.
Com ele em zero a mensagem afirma duas coisas ao mesmo tempo:

* bit 30 = 0 → *"a tecla NÃO estava pressionada"*
* bit 31 = 0 → *"NÃO está havendo transição para solta"*

Ou seja, descreve um KEYUP de uma tecla que nunca esteve apertada e que não está
sendo solta. O cliente lê o registro, vê a contradição, e descarta.

### A matemática, campo por campo

```
bits  0-15   contagem de repetição      -> 1
bits 16-23   SCAN CODE da tecla         -> scan_code << 16
bit     24   tecla estendida            -> 0
bits 25-28   reservado                  -> 0
bit     29   contexto (ALT apertado)    -> 0
bit     30   ESTADO ANTERIOR            -> 1   (a tecla ESTAVA apertada)
bit     31   ESTADO DE TRANSIÇÃO        -> 1   (está sendo SOLTA agora)
```

`lparam = 1 | (scan_code << 16) | (1 << 30) | (1 << 31)`

Medido nesta máquina:

| tecla | vk | scan code | lParam |
|---|---|---|---|
| SHIFT | 0x10 | 0x2A | `0xC02A0001` |
| CTRL | 0x11 | 0x1D | `0xC01D0001` |
| ALT | 0x12 | 0x38 | `0xC0380001` |

O **scan code** sai de `win32api.MapVirtualKey(vk, MAPVK_VK_TO_VSC)` e nunca de
literal: o VK é lógico e igual em toda máquina, o scan code é **físico** e muda
com o layout. Scan errado é outra tecla.

### O que este conserto NÃO resolve, e está escrito para ninguém supor que sim

Um `WM_KEYUP` na fila da janela conserta o estado de teclado **por thread** —
o que `GetKeyState` devolve quando o cliente processa a mensagem. Ele **não**
toca `GetAsyncKeyState` nem RawInput, que leem o hardware, e **nenhuma mensagem
sintética toca**. Se este cliente ler o estado assíncrono, o vazamento continua
e a saída não existe por mensagem.

O `lParam` malformado era, ainda assim, um defeito real: ele impedia até o
caminho que poderia funcionar. Conserta-se o que está errado e mede-se o efeito.

### Por que a matemática ficou em `core/teclado_win32.py`

`core/inputs.py` estava em **1221 linhas com teto de 1222** na catraca de
tamanho do projeto — ou seja, não podia crescer, e a regra da casa é *mover
conteúdo, não comprimir texto*. Mas o motivo de fundo não é a contagem: montar
um registro de bits do Windows **não precisa saber nada sobre o bot** — não
conhece `hwnd`, nem conta, nem `MODO_DE_TECLA`. É a mesma pergunta que
`core/janelas.py` responde para janelas.

### O que ficou de fora, de propósito

`key_up` e o laço de soltura de `inputs.py` mandam `WM_KEYUP` com o **mesmo**
`LPARAM(0)` malformado — as teclas que o próprio bot solta. O escopo deste
hotfix foi fixado nas duas funções do vazamento de modificadores; o restante
fica registrado aqui para não se perder.
