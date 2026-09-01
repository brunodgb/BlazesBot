"""Ecossistema **HH** — o farm de boss-rush da Black Wind Camp Dungeon.

===========================================================================
A REGRA DOS ECOSSISTEMAS
===========================================================================

O BlazesBot é UM sistema com vários ecossistemas. Hoje são três:

    blazesbot/bot/bc/    o farm de boss-rush da Bewitcher Cave
    blazesbot/bot/app/   a macro de teclado, independente da cave
    blazesbot/bot/hh/    este aqui — 4 bosses na Black Wind Camp Dungeon

**UM ECOSSISTEMA NUNCA IMPORTA DO OUTRO.** O que eles têm em comum sobe para
as camadas de baixo, e é só isso que pode ser compartilhado:

    blazesbot/bot/       o SISTEMA: supervisor, contexto, login, watchdog.
                         É o supervisor que decide qual ecossistema roda.
    blazesbot/core/      capacidades que não sabem que ecossistema existe:
                         teclado e mouse, captura de tela, memória, log,
                         coordenadas -- e, desde a chegada da HH, também o
                         COMBATE, a NAVEGAÇÃO e a UI DO JOGO.

Configuração global — as TECLAS, principalmente — é compartilhada de
propósito: elas descrevem o jogo, não o ecossistema.

===========================================================================
POR QUE A HH NÃO É UM "MODO" DA BC
===========================================================================

Tentador, e errado. As duas entram numa cave, matam boss e vendem, mas tudo
que decide o comportamento é diferente:

  * OUTRA CAVE. A BC atravessa Centipede Zone, Skull Tomb e Secret Altar até
    UM boss no Secret Cemetery. A HH tem QUATRO bosses em quatro trechos
    encadeados dentro da mesma instância.
  * OUTRA ROTA DE CHEGADA. A BC vai para Ghost Din Woods pelo Transport Fay e
    fala com o Skull Herald. A HH usa o MESMO Fay, mas o destino é
    `West Suburb of Stone City` -- que só aparece ROLANDO a lista do diálogo --
    e de lá busca a `Mutual Quest Woman` no painel de arredores para chegar ao
    `Elite Axe Monk Soldier`.
  * OUTRO VENDEDOR. Rich Man em Stone City vs `Roaming Apothecary` do lado de
    fora da HH.
  * OUTRO CICLO DE TIME. Na BC o reset entra e sai antes da cave. Na HH+Fada a
    curandeira ENTRA JUNTO, acompanha e cura, e o desfaz-refaz do time acontece
    DEPOIS de sair.

Enfiar isso em `BCRoute.mode` transformaria a rotina da BC num arquivo com dois
comportamentos alternados por `if` -- e cada `if` desses é uma chance de mexer
na HH e quebrar a BC.

===========================================================================
A PROMOÇÃO QUE A HH FORÇOU -- DEPENDÊNCIA CRUZADA, LEIA ANTES DE MEXER
===========================================================================

A HH não pode importar de `bc/`, e duplicar o combate e a navegação é proibido
pela diretiva de reuso. Então o que os dois usam DESCEU:

    core/combate.py      rotação de ataque, TAB confirmado pela troca de id,
                         esperar a flag de combate baixar, curar, sentar para
                         recuperar, pet, buffs
    core/navegacao.py    clique de minimapa, detecção de travamento,
                         destravamento pelos vizinhos, varredura em círculo,
                         manutenção de montaria e pet em movimento
    core/ui_do_jogo.py   painel de arredores, busca por NPC, ir ao resultado,
                         o par de cliques NPC+link com o diálogo conferido,
                         encostar no ponto exato antes de clicar

**MEXER NESSES TRÊS MEXE NOS DOIS ECOSSISTEMAS.** O que NÃO subiu, e por quê:

  * as FASES do combate. `fase_dos_guardas` e `fase_do_boss` são o roteiro da
    Bewitcher Cave; a HH tem quatro bosses em sequência. Roteiro é do
    ecossistema.
  * a trava do Cemetery Guard e o Package Courage. São daquele boss e daquele
    item.
  * as ROTAS. `mapa_bc` e `mapa_hh` são dados medidos de duas caves diferentes.
  * quais NPCs, quais links e quais coordenadas. A máquina de falar com NPC é do
    jogo; com QUEM falar é do ecossistema.

Ver `docs/decisoes/hh.md`, seção 8, para o critério aplicado item por item.
"""
