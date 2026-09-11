# A espera ATIVA e o orquestrador — 11/09/2026

> Pedido do usuário: *"projete um orquestrador central — uma lógica de controle
> dinâmico que não dependa de tempos arbitrários. O sistema deve validar
> ativamente o estado das ações (ex: verificar se a UI carregou, ou se já
> chegou no lugar especificado) e prosseguir para a próxima tarefa de forma
> instantânea assim que a condição for satisfeita"*.

---

## 1. O QUE HAVIA: A MESMA IDEIA, QUATRO VEZES

A forma certa já existia — espalhada, cada cópia com o seu laço, o seu
`time.time()`, o seu teto e o seu jeito de dizer "desisti":

| onde | o que perguntava |
|---|---|
| `UIDoJogo.esperar_a_chegada` | a posição virou a do destino? |
| `UIDoJogo._esperar_o_dialogo` | o diálogo apareceu? (teto adaptativo) |
| `rajada_de_npc.clicar_ate_abrir` | clica, pergunta, para quando abre |
| `Memory._esperar_o_termometro` | escreve e espera o campo MEXER |

Quatro laços é onde nasce a quinta cópia — e a quinta costuma sair cega,
porque escrever `tick(0.5)` é mais rápido que escrever um laço.

## 2. O ORQUESTRADOR — `core/espera.py`

Uma peça com o laço, os dois tetos, o passo, o Parar e a telemetria. Quem usa
declara só o que é seu: **a pergunta**.

```python
fim = espera.ate(chegou, ctx=ctx, teto=0.12, passo=0.04, o_que="chegada.HH")
```

**Não é agendador e não é máquina de estados.** As máquinas de estado do bot
continuam onde estão; o que subiu foi a espera.

### As três respostas, e por que são três

`True` segue agora; `False` pergunta de novo; **`None` é "não dá para saber"** —
cliente minimizado devolve quadro preto e nenhum template casa. Tratar `None`
como "não aconteceu" faria toda volta ir até o teto, e é defeito que este
projeto já pagou duas vezes.

### Dois tetos, e pelo menos um obrigatório

Tempo (`teto`) e voltas (`voltas_maximas`). A rajada de NPC conta CLIQUES, não
segundos; a chegada conta segundos. `ate()` sem nenhum dos dois **levanta
`ValueError`** — espera sem teto é laço infinito com outro nome.

### O passo nunca passa do que falta

Dormir o passo inteiro na última volta é como um teto de 0,12 s vira 0,16 s.

## 3. A TELEMETRIA PASSOU A VIR DE GRAÇA

Toda espera que passa pelo orquestrador é **cronometrada** (`espera.<o_que>`) e
**contada por desfecho** (`confirmado` / `teto` / `voltas` / `nao_sei`).

`cronometro.marcar(nome, desfecho)` é o caminho quente novo: **sem relógio**,
dois lookups de dicionário e um `+= 1` (~80 ns, contra 298 ns de `anotar`). Ele
mora no mesmo balde por thread, sai no mesmo despejo de 30 s e no mesmo arquivo
— porque "quanto custou" e "como terminou" só querem dizer alguma coisa juntos.

**Por que isso é o coração da iteração:** na auditoria de 10/09/2026 foi preciso
CONTAR STRINGS EM PROSA no log de dev para descobrir as 61.928 tentativas de
entrada que estouraram o teto. Isso quebra na primeira vez que alguém reescreve
a mensagem. Agora `relatorio_de_latencia` tem a tabela **COMO AS AÇÕES
TERMINAM**, com o percentual de confirmação por espera.

## 4. A CATRACA — `tests/test_catraca_da_espera_cega.py`

O número de esperas `FIXO` por módulo **pode cair, nunca subir**. Não é
proibição: existem esperas sem observável (o `hold` entre KEYDOWN e KEYUP, o
respiro antes do Sell, a cadência de skill), e cada uma tem a justificativa
escrita. O que não pode é a lista crescer sem ninguém ver.

E a catraca **aperta**: um terceiro teste reprova quando um módulo tem MENOS
espera cega que a tabela — quem converteu, trava o ganho no mesmo commit.

Linha de base de 11/09/2026: **250** esperas cegas no projeto, sendo 36 em
`combate.py`, 28 em `navegacao.py`, 16 em `app/executor.py`, 14 em
`ui_do_jogo.py`.

## 5. O QUE A MEDIÇÃO DISSE SOBRE "ERRADICAR OS TEMPOS FIXOS"

Honestamente: **no caminho de UI e navegação, o trabalho já está quase feito** —
e os dados dizem onde NÃO vale mexer.

| espera cega | custo medido em 48 h | tem observável? |
|---|---|---|
| rajada de clique direito | ~7 h (resolvida em 10/09) | sim — o diálogo |
| janela de confirmação da entrada | 4,3 h (resolvida em 10/09) | sim — a posição |
| `Input.key` `hold` = 50 ms | 8,6 h | **não** — tecla de duração zero é ignorada |
| delays do macro do APP | 67 h | **não é hardcoded** — é configuração do usuário |
| painel Surroundings (2,0 s cegos) | ~60 s (30 usos) | sim, mas não paga |
| View Reset (0,175 s cego) | ~8 min | sim, mas não paga o orçamento de linhas |

O que sobra de espera cega relevante é **mecânica de jogo** (sem observável) ou
**configuração do usuário**. Converter o que não paga seria trocar risco por
milissegundo.

**É por isso que a entrega desta iteração é o orquestrador e a catraca, e não
uma lista de números cortados:** a próxima espera cega que importar vai se
denunciar sozinha na tabela de desfechos, em vez de ficar escondida num
`tick(0.5)` que ninguém mede.
