"""Isto tem cara de entidade do jogo? -- os filtros de plausibilidade.

=========================================================================
PECA PROMOVIDA -- DEPENDENCIA CRUZADA
=========================================================================

**De onde veio:** `_plausible_hp`, `_plausible_level` e `_plausible_coord`
eram funções de módulo do `blazesbot/tools/find_base.py` (o
`7-DESCOBRIR-MEMORIA`). Cada uma nasceu de um falso positivo REAL medido no
jogo, e a lista está no docstring de `describe_object`, lá.

**Quem usa hoje:** `tools/find_base.py` e
`core/target_hybrid.investigar_alvo_perdido` (o `9-VIGIAR-COMBATE`). Mexer
aqui mexe nos dois.

**Por que subiu:** em 26/08/2026 a investigação do alvo perdido precisou da
mesma pergunta -- *"este endereço tem cara de struct de entidade?"* -- e a
primeira versão dela reimplementou o filtro pela metade. O resultado apareceu
na primeira medição, com o jogo na frente:

    0x1095C228  ?  nv32  hp=1/390876288        <- lixo aprovado
    0x2F28A424  ?  nv2   hp=0/1030909696       <- lixo aprovado

`hp <= max_hp` sozinho aprova qualquer coisa, porque `max_hp` gigante torna a
relação trivialmente verdadeira. Os filtros que já existiam no
`7-DESCOBRIR-MEMORIA` reprovariam os dois na primeira linha -- eles só não
estavam onde o segundo consumidor pudesse alcançá-los.

**A lição, e ela é a diretiva de promoção em uma frase:** quando uma pergunta
aparece pela segunda vez, o custo de reimplementá-la não é o tempo de escrever
-- é reaprender, com o jogo na frente, tudo o que a primeira versão já sabia.
"""
from __future__ import annotations

from .memory import OFF_HP as OFF_HP_DA_ENTIDADE
from .memory import OFF_LEVEL, OFF_MAX_HP

# Teto de HP que ainda é HP. Cinco milhões é folgado de sobra para qualquer
# entidade desta build, e reprova de longe o `390876288` que o lixo devolveu.
HP_MAXIMO_PLAUSIVEL = 5_000_000

# Faixa de nível. 200 é folga: o jogo vai a 8x, e o boss da cave é nv51.
NIVEL_MAXIMO_PLAUSIVEL = 200


def hp_plausivel(valor: int | None) -> bool:
    """Um HP que é HP. `None` (não consegui ler) reprova."""
    return valor is not None and 1 <= valor <= HP_MAXIMO_PLAUSIVEL


def nivel_plausivel(valor: int | None) -> bool:
    """Um nível que é nível. Zero reprova: entidade no mundo tem nível."""
    return valor is not None and 1 <= valor <= NIVEL_MAXIMO_PLAUSIVEL


def coordenada_plausivel(valor: float | None) -> bool:
    """Uma coordenada dentro do mapa, já dividida pelos 20 da escala do jogo."""
    if valor is None:
        return False
    coordenada = valor / 20.0
    return -20_000 <= coordenada <= 20_000


def parece_entidade(memoria, obj: int) -> dict | None:
    """`obj` tem cara de struct de entidade? Devolve o que deu para ler.

    Os quatro filtros, e o que cada um pega:

      1. **ENDEREÇO ALINHADO em 4** -- struct de objeto sempre é. Sozinho já
         derruba metade do lixo de uma varredura por valor.
      2. **HP e HP MÁXIMO PLAUSÍVEIS**, cada um por si. `hp <= max_hp` sozinho
         não serve: com `max_hp = 390876288` a relação é trivialmente
         verdadeira e o lixo passa -- foi o que aconteceu na medição de
         26/08/2026.
      3. **HP <= HP MÁXIMO** -- relação que vale em qualquer entidade viva.
      4. **NÍVEL PLAUSÍVEL** -- entidade no mundo tem nível; zero é o que sobra
         quando os bytes lidos não são nível nenhum.

    O NOME NÃO ENTRA COMO FILTRO, e isso é deliberado: existe um estado REAL,
    medido em 26/08/2026, de entidade legítima com o nome ilegível
    (`#245506802  100/100, nv61`). Exigir nome esconderia justamente o caso que
    se quer enxergar.
    """
    if obj <= 0x10000 or obj % 4:
        return None
    hp = memoria.read_int(obj + OFF_HP_DA_ENTIDADE)
    maximo = memoria.read_int(obj + OFF_MAX_HP)
    nivel = memoria.read_byte(obj + OFF_LEVEL)
    if not hp_plausivel(maximo) or hp is None or hp < 0 or hp > maximo:
        return None
    if not nivel_plausivel(nivel):
        return None
    return {
        "obj": obj,
        "nome": memoria._nome_da_entidade(obj),
        "nivel": nivel,
        "hp": hp,
        "max_hp": maximo,
    }
