"""Ecossistema **APP** — a macro de teclado, independente do farm da cave.

===========================================================================
A REGRA DOS ECOSSISTEMAS
===========================================================================

O BlazesBot é UM sistema com vários ecossistemas. Hoje são dois:

    blazesbot/bot/bc/    o farm de boss-rush da Bewitcher Cave
    blazesbot/bot/app/   este aqui — manda tecla e espera, em laço

**UM ECOSSISTEMA NUNCA IMPORTA DO OUTRO.** O que eles têm em comum sobe para
as camadas de baixo, e é só isso que pode ser compartilhado:

    blazesbot/bot/       o SISTEMA: supervisor, contexto, login, watchdog.
                         É o supervisor que decide qual ecossistema roda.
    blazesbot/core/      capacidades que não sabem que ecossistema existe:
                         teclado e mouse, captura de tela, memória, log.

Configuração global — as TECLAS, principalmente — é compartilhada de
propósito: elas descrevem o jogo, não o ecossistema. A aba APP, porém, NÃO
tem filtro de tecla repetida: aqui a mesma tecla se repete na sequência por
desenho, e barrar isso seria proibir o uso normal do módulo.

=========================================================================
ISOLAMENTO DO EXECUTOR -- LEIA ANTES DE MEXER
=========================================================================

O `ExecutorDeMacro` é AUTÔNOMO: a única coisa que ele usa de fora é
`blazesbot.core.inputs.Input`, que é o envio de tecla para uma janela -- a mesma
infraestrutura que o login usa, e que não é lógica de farm.

Tudo que precisa de mais que isso chega como FUNÇÃO INJETADA pelo supervisor
(o pet, a página da barra de atalhos, e o deletar). Assim o executor continua
sem saber o que é `BotContext`, e sem ele a macro roda exatamente como sempre
rodou.

O que ele NÃO faz, e não deve passar a fazer:

  * ler memória do jogo (HP, posição, alvo, montaria);
  * reconhecer tela por imagem;
  * navegar mapa ou waypoint;
  * consultar qualquer estado do bot BC.

Antes, o executor recebia o `BotContext` do bot BC inteiro (memória, templates,
coordenadas, navegação) e era chamado de DENTRO da rotação de ataque do combate.
Isso amarrava os dois: mexer na rotação do BC mudava o comportamento do APP, e
ligar o APP mudava o combate do BC. Agora são dois sistemas que não se conhecem.
"""
from .executor import FATIA_DE_ESPERA, ExecutorDeMacro

__all__ = ["FATIA_DE_ESPERA", "ExecutorDeMacro"]
