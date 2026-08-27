"""Ecossistema **Bewitcher Cave** — o farm de boss-rush.

===========================================================================
A REGRA DOS ECOSSISTEMAS
===========================================================================

O BlazesBot é UM sistema com vários ecossistemas. Hoje são dois:

    blazesbot/bot/bc/    este aqui — entra na cave, atravessa, mata o boss,
                         sai, vende, repete
    blazesbot/bot/app/   a macro de teclado, independente da cave

**UM ECOSSISTEMA NUNCA IMPORTA DO OUTRO.** O que eles têm em comum sobe para
as camadas de baixo, e é só isso que pode ser compartilhado:

    blazesbot/bot/       o SISTEMA: supervisor, contexto, login, watchdog.
                         Serve todos os ecossistemas -- é o supervisor que
                         decide qual deles roda para cada conta.
    blazesbot/core/      capacidades que não sabem que ecossistema existe:
                         teclado e mouse, captura de tela, memória,
                         coordenadas, log, configuração.

Configuração global — as TECLAS, principalmente — é compartilhada de
propósito: elas descrevem o jogo, não o ecossistema.

O motivo da regra é prático: mexer num ecossistema não pode quebrar o outro.
Enquanto `bc/` e `app/` não se importarem, isso é garantido pelo próprio
grafo de dependências, e não pela lembrança de quem edita.
"""
