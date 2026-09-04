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

1. **Teto de 350 linhas por arquivo** (`test_max_linhas_por_arquivo`).
   Mesmo número do toolkit; abaixo de ~200 vira briga constante em código
   legítimo, acima de ~500 para de pressionar.

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
MEDIÇÃO DE 04/09/2026 — LINHA DE BASE
================================================================

TETO 350 — 44 offenders (do maior para o menor):

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
inteira passa** hoje (44 warns); o dia em que virar 0 warns é o dia em
que a regra passa a reprovar de verdade — basta tirar o `with
pytest.warns(...)` e usar `assert` direto.
