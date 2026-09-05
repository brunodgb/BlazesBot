# Quality gates do toolkit ESLint, portados para Python

> **Por que este arquivo existe:** o toolkit `soumatheusgomes/vibe-coding-toolkit`
> traz três regras de ESLint (teto de linhas por arquivo, proibição de
> `console` direto, proibição da UI importar o cliente do banco) que são uma
> forma compacta de dizer três princípios que valem para qualquer projeto. O
> BlazesBot é Python + frontend estático Vite — a porta ESLint do toolkit não
> se aplica literalmente. Mas os **princípios** se aplicam, e este arquivo
> registra a portação para Python em 04/09/2026.

================================================================
O QUE ENTROU (e o que NÃO entrou)
================================================================

Os três gates portados vivem em `tests/test_quality_gates_python.py`:

1. **Teto de 800 linhas por arquivo** (`test_max_linhas_por_arquivo`).
   **NÃO** é o 350 do toolkit — ver "POR QUE 800, E NÃO 350" abaixo, que é
   a correção medida de 05/09/2026.

2. **`print()` só em scripts de diagnóstico** (`test_print_so_em_scripts_de_diagnostico`).
   Lista de exceções documentada na docstring do teste: `tools/`, mais
   `core/calibracao.py`, `core/indice_de_*.py`, `bot/instrumentar_clique.py`
   e `bot/teste_do_cursor.py` — todos rodam como `python -m X` ou são
   entradas CLI do bot (ver `18-AFERIR-ALVO-ALIADO.bat`), não fazem parte
   do bot rodando por horas.

3. **Fronteira de camadas.** O terceiro gate do toolkit (UI não pode
   importar cliente do banco) **não foi duplicado aqui**: a contraparte
   Python é o `tests/test_ecossistemas.py` que já existia antes desta
   portação, e ele faz a coisa certa para a arquitetura do BlazesBot
   (bc/app/hh não se importam, core não conhece bot, bot não conhece
   ecossistema — exceto o supervisor, que é quem escolhe qual roda).

================================================================
POR QUE WARN, NÃO ERROR (passo 6 do prompt 08)
================================================================

A regra do toolkit é clara: *"gate que nasce vermelho em cima de código que
já existia não é gate, é ruído que alguém vai desligar na primeira
sexta-feira"*. Os dois gates novos nascem em `pytest.warns` (avisam, não
reprovam). A linha de base medida está abaixo, e a migração é o trabalho
do próximo prompt do toolkit (`09-file-size-refactor`) — a porta
`max-lines` já está pronta para virar `assert` no dia em que a contagem
zerar, e o `print` idem.

================================================================
POR QUE 800, E NÃO 350 (correção medida — 05/09/2026)
================================================================

O 350 foi **importado** do toolkit sem ser medido nesta base, e reprovou
45 dos 90 `.py`. O `CLAUDE.md` deste projeto manda o contrário: *"Número
novo precisa de MEDIÇÃO"*. Medido, o 350 não serve — por duas razões
independentes.

**1. O teto ficava ABAIXO da mediana do projeto.**

```
mediana ... 410     teto  350 -> 45 arquivos (50%)
p75 ....... 664     teto  500 -> 34 arquivos
p90 ...... 1511     teto  800 -> 19 arquivos (21%)
p95 ...... 2164     teto 1200 -> 12 arquivos
```

Um teto abaixo da mediana não sinaliza exceção: descreve o projeto
inteiro. E fila de 45 itens parece infinita — foi exatamente isso que
levou a sessão de 04-05/09 a partir `executor.py` e `combate.py` na
marreta (ver "O QUE DEU ERRADO" abaixo). Gate só funciona com fila
finita e visivelmente vencível.

**2. Só 40% das linhas deste projeto são código executável.**

```
código executável ...... 22.475  (40%)
docstring .............. 13.136  (23%)
comentário ............. 11.907  (21%)
em branco ...............  7.621  (13%)
```

O 350 do toolkit foi calibrado para TypeScript/JSX, onde a densidade de
código é bem maior. Aqui:

> **350 linhas cruas ~= 142 linhas de código real.**
> **350 linhas de código real ~= 858 linhas cruas.**

Aplicar 350 aqui é aplicar um teto **2,5x mais apertado** do que o
toolkit pretendia. E 44% do arquivo é docstring e comentário — que é
precisamente o que o `CLAUDE.md` **exige** ("porquê medido",
"documentação de transição no mesmo passo"). Um teto de linhas cruas
em 350 **pune a documentação que outra regra do projeto manda
escrever**: dois gates brigando.

**Por que 800 e não outro número:**

- **~325 linhas de código real** — o ponto de pressão que o toolkit de
  fato queria ("abaixo de ~200 vira briga, acima de ~500 para de
  pressionar" — em linhas de CÓDIGO, não cruas).
- **Acima do p75 (664)** — reprova o outlier, não a mediana.
- **19 arquivos** em vez de 45: fila finita.
- **Já era o padrão do usuário.** `~/.claude/rules/ecc/code-review.md`
  diz *"Files are cohesive (<800 lines)"*. O 350 veio de fora e
  atropelou calado uma régua que já existia.

Se um dia o teto for apertado, aperte sobre **linhas de código**, não
cruas — assim ele não pune docstring, que neste projeto é obrigatória.

================================================================
O QUE DEU ERRADO COM O 350 (04-05/09/2026)
================================================================

Com 45 offenders, a execução do prompt `09-file-size-refactor` violou o
próprio prompt em quatro pontos, e o resultado foi descartado (tag
`refatoracao-350-descartada`, 25 commits):

- O prompt proíbe blob residual — *"a file holding whatever was left
  over is **a failure, not a result**"*. Foram criados
  `_modulo_legado.py` (1902L) e `_antigo.py` (906L).
- O prompt manda cortar **por responsabilidade**; foi cortado por grupo
  de métodos ("os 20 do alvo"), e `_alvo.py` saiu com 891L — acima até
  do teto novo.
- O prompt manda *"do not proceed with a failing check"*; a suíte
  quebrou em `1851de6` (05/09 07:23) e **seguiram mais 8 commits** em
  cima do vermelho.
- A verificação final do prompt (quantos arquivos ainda acima do teto)
  daria **44 -> 50**: o objetivo declarado andou para trás.

O que ficou de bom e foi preservado: os dois gates, e o split de
`core/vision.py` (`e96648e`) — cortado por domínio real
(`captura`/`templates`/`barra`/`marcadores`), sem blob, sem injeção,
suíte verde. **É o molde para os próximos.**

================================================================
MEDIÇÃO DE 04/09/2026 — LINHA DE BASE (com o teto antigo de 350)
================================================================

TETO 350 — 44 offenders (do maior para o menor):
*(fotografia histórica; o teto vigente é 800 — ver seção acima)*


```
   3735  blazesbot/bot/combate.py
   2939  blazesbot/bot/app/executor.py
   2755  blazesbot/bot/supervisor.py
   2596  blazesbot/bot/bc/routine.py
   2498  blazesbot/core/memory.py
   2164  blazesbot/bot/navegacao.py
   1935  blazesbot/config.py
   1929  blazesbot/bot/ui_do_jogo.py
   1895  blazesbot/gui/main_window.py
   1548  blazesbot/core/vision.py
   1511  blazesbot/bot/hh/routine.py
   1449  blazesbot/web_app.py
   1415  blazesbot/gui/account_dialog.py
   1134  blazesbot/bot/login.py
   1111  blazesbot/core/inputs.py
   1105  blazesbot/core/calibracao.py
    972  blazesbot/bot/team.py
    935  blazesbot/bot/vendedor.py
    852  blazesbot/bot/bc/amostragem_de_cliques.py
    834  blazesbot/bot/hh/mapa_hh.py
    738  blazesbot/bot/fada.py
    721  blazesbot/core/coords.py
    664  blazesbot/bot/app/sincronia.py
    643  blazesbot/bot/context.py
    640  blazesbot/bot/mural.py
    635  blazesbot/bot/app/deletador.py
    629  blazesbot/core/target_hybrid.py
    603  blazesbot/bot/bc/mapa_bc.py
    596  blazesbot/bot/app/cura.py
    590  blazesbot/bot/app/afericao_do_aliado.py
    564  blazesbot/bot/bc/localizacao.py
    535  blazesbot/bot/bc/ui_service.py
    509  blazesbot/bot/bc/vendor.py
    505  blazesbot/bot/instrumentar_clique.py       (exceção de print; não de teto)
    503  blazesbot/core/quedas.py
    487  blazesbot/bot/teste_do_cursor.py           (exceção de print; não de teto)
    460  blazesbot/bot/recorte_do_time.py
    444  blazesbot/core/petbug.py
    433  blazesbot/core/indice_de_tempos.py         (exceção de print; não de teto)
    422  blazesbot/bot/hh/entrada.py
    410  blazesbot/core/rota.py
    407  blazesbot/bot/bc/combat.py
    388  blazesbot/gui/theme.py
    352  blazesbot/bot/hh/fada.py
```

`PRINT()` EM LOCAL PROIBIDO — 1 violação:

```
  blazesbot/bot/app/afericao_do_aliado.py:478: print(texto, flush=True)
```

================================================================
POR QUE ESSA ÚNICA VIOLAÇÃO DE `print` FICOU DE FORA DA LISTA
================================================================

A função `_avaliar` em `afericao_do_aliado.py` é uma peça compartilhada
chamada tanto pelo executor do APP quanto pelos scripts de aferição. O
`print(texto, flush=True)` na linha 478 joga o resultado na tela para o
operador que rodou o script — e o executor, que importa essa função, é
também quem está sendo usado pelo mesmo operador no momento da aferição.

A escolha foi **não** adicionar `afericao_do_aliado.py` à lista de
exceções, porque a função **é código de aplicação** (o executor é
chamado de dentro do bot rodando). A correção certa é separar o caminho
de relatório do caminho de cálculo: a função devolve um `dict`/`str`, e
quem chama decide se imprime ou loga. **Não foi feita nesta portação** —
a regra do passo 6 do prompt 08 é *"instale o gate e meça o que ele
pega; refactor é trabalho separado, com revisão própria"*. O próximo
passo é mover o `print` para o `__main__` do script que importa a
função, e tirar a saída do caminho de produção.

================================================================
DECISÕES QUE SAÍRAM DA LISTA (e por quê)
================================================================

- **`__init__.py` puro-reexport** (vazio ou só com docstring) tem
  contagem zerada e é ignorado — contar ele como arquivo só porque
  existe é a armadilha que o prompt 08 avisa.

- **`_salvar_print` em `core/quedas.py`** parece violar mas é só o
  nome de uma função (começa com `_`, a regex `(?<![\w.])print\(` exige
  que `print` não venha precedido de letra/dígito/`_`/`.`).

- **String literais que contêm "print("** também passam: a regex casa
  na linha inteira mas o `print(` literal em uma string é
  `repr(...)` retornando, e o `re.compile` da linha só
  pega chamadas, não menções.

- **`bot/instrumentar_clique.py` e `bot/teste_do_cursor.py`** foram
  ADICIONADOS à lista de exceções de print depois de contados. São
  entradas CLI chamadas por `.bat` (ver `18-AFERIR-ALVO-ALIADO.bat`),
  e o usuário rodando o script quer ver a saída. Tirá-los seria tirar
  funcionalidade existente sem motivo. **Não há `print` que não seja
  de UI legada para o operador.**

================================================================
COMO RODAR
================================================================

```
python -m pytest tests/test_quality_gates_python.py -v
```

Cada `::test_max_linhas_por_arquivo[<arquivo>]` que violar emite
`UserWarning` listando o tamanho atual e o teto. O segundo gate emite
uma `UserWarning` consolidadada com a lista de violações. **A suíte
inteira passa** hoje (19 warns com o teto de 800); o dia em que virar 0
warns é o dia em que a regra passa a reprovar de verdade — basta tirar o
`with pytest.warns(...)` e usar `assert` direto.

================================================================
A FILA COM O TETO DE 800 (medida em 05/09/2026)
================================================================

```
   3735  blazesbot/bot/combate.py
   2939  blazesbot/bot/app/executor.py
   2755  blazesbot/bot/supervisor.py
   2596  blazesbot/bot/bc/routine.py
   2498  blazesbot/core/memory.py
   2164  blazesbot/bot/navegacao.py
   1935  blazesbot/config.py
   1929  blazesbot/bot/ui_do_jogo.py
   1895  blazesbot/gui/main_window.py
   1511  blazesbot/bot/hh/routine.py
   1449  blazesbot/web_app.py
   1415  blazesbot/gui/account_dialog.py
   1134  blazesbot/bot/login.py
   1111  blazesbot/core/inputs.py
   1105  blazesbot/core/calibracao.py
    972  blazesbot/bot/team.py
    935  blazesbot/bot/vendedor.py
    852  blazesbot/bot/bc/amostragem_de_cliques.py
    834  blazesbot/bot/hh/mapa_hh.py
```

**Esta fila não é uma lista de tarefas com prazo.** É catraca: o valor
do gate está em não deixar nascer o 20º.

================================================================
TRIAGEM DE COSTURA (05/09/2026) — 15 DOS 19 NÃO SE DIVIDEM
================================================================

Antes de cortar qualquer arquivo, foi medida a estrutura dos 19: quanto
do arquivo é UMA classe, e quantas funções top-level existem. O
resultado muda o tamanho do problema.

| padrão | arquivos | o que significa |
|---|---|---|
| **Uma classe gorda** (59–92% do arquivo é UMA classe) | **15** | Sem costura em nível de ARQUIVO |
| **Costura real** (muitas funções top-level) | **4** | Divisível quando valer a pena |

Os 15 sem costura, com a classe que os domina:

```
combate.py .......... CombatEngine        52 métodos  (74% do arquivo)
app/executor.py ..... ExecutorDeMacro     47 métodos  (74%)
supervisor.py ....... AccountSupervisor   41 métodos  (85%)
bc/routine.py ....... BossRushRoutine     37 métodos  (84%)
core/memory.py ...... Memory              82 métodos  (74%)
navegacao.py ........ Navigator           32 métodos  (80%)
ui_do_jogo.py ....... UIDoJogo            34 métodos  (70%)
gui/main_window.py .. MainWindow          59 métodos  (92%)
hh/routine.py ....... HHRoutine           34 métodos  (86%)
web_app.py .......... _App                45 métodos  (63%)
account_dialog.py ... AccountDialog       20 métodos  (92%)
login.py ............ LoginSequence       26 métodos  (84%)
core/inputs.py ...... Input               27 métodos  (68%)
team.py ............. TeamService         18 métodos  (59%)
vendedor.py ......... JanelaDeVenda       19 métodos  (65%)
```

**Isto explica retroativamente o desastre de 04-05/09.** `executor`,
`combate` e `supervisor` são exatamente este padrão. Não se move um
método de uma classe para outro arquivo sem uma de três coisas:
herança, mixin, ou injeção (`Classe.metodo = funcao`). A sessão
anterior escolheu injeção — a pior das três — porque a costura que ela
procurava **não existia**. Não foi descuido: era o arquivo errado.

Pela regra do próprio prompt 09 (*"say so, leave it alone, and move to
the next file"*), **os 15 saem da fila**. Quebrá-los não é refatoração,
é **redesenho**: trocar a classe gorda por objetos colaboradores. É
decisão grande, no motor de produção, e precisa de medição própria — não
se faz sob pressão de um gate de lint.

Os 4 com costura real (`config.py`, `core/calibracao.py`,
`bc/amostragem_de_cliques.py`, `hh/mapa_hh.py`) podem ser divididos
quando houver motivo — dois deles são ferramentas de diagnóstico que nem
rodam dentro do bot, então o ganho é pequeno e não há pressa.

================================================================
COMO A CATRACA FUNCIONA (é o que o gate faz hoje)
================================================================

`tests/test_quality_gates_python.py` tem a lista `HERDADOS` com os 19
arquivos e o tamanho que cada um tinha em 05/09/2026. O gate:

| situação | resultado |
|---|---|
| arquivo dentro do teto, fora da lista | passa |
| arquivo **NOVO** acima de 800 | **REPROVA** |
| herdado que **CRESCEU** desde 05/09 | **REPROVA** |
| herdado igual ou menor, ainda acima de 800 | avisa (`warn`) |
| herdado que baixou **para dentro** do teto | **REPROVA** até a entrada sair de `HERDADOS` |

Os três `REPROVA` foram verificados criando os casos de propósito, não
por leitura do código — um gate que não falha é o problema que estamos
consertando. A fila, portanto, **só pode encolher**: nada grande nasce,
nada grande cresce, e quem sai da lista não volta.
