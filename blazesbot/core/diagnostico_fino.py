"""O INTERRUPTOR DO DIAGNÓSTICO FINO — 06/09/2026.

Pedido do usuário: *"vamos tentar trackear todo tipo de problema com vários logs
em vários pontos que você considerar que pode ser problemático, pois assim vamos
ter comprovações e conseguir tomar medidas mais precisas (...) mas pode ser log
dev, não precisa mostrar tudo na UI"*.

São linhas que só existem para MEDIR: distância do mob ao personagem e ao ponto,
atraso entre o HP zerar e a flag de combate baixar, id esperado contra id lido no
clique da Fada, onde o personagem morreu e com quantos mobs em cima, quanto
tempo a volta durou e por que ela terminou.

=======================================================================
POR QUE UM INTERRUPTOR, E NÃO SÓ `log.debug`
=======================================================================

Porque estas linhas precisam sair no arquivo de dev **em produção**, junto com o
resto — é lá que a medição acontece, com o bot rodando horas em várias contas.
Baixar tudo para `debug` esconderia justamente o que se quer ver; deixar em
`info` sem interruptor dobra o log de todo mundo para sempre.

Então: `LIGADO = True` enquanto se caça defeito, `False` quando o log voltar a
ser só operação. Nada aqui muda comportamento — só o que é escrito.
"""

from __future__ import annotations

LIGADO = True


def anotar(log, formato: str, *args) -> None:
    """Uma linha de medição, se o diagnóstico fino estiver ligado.

    O PREFIXO É PADRONIZADO (`DIAG:`) de propósito: é o que permite separar o
    log de medição do log de operação com um `grep`, sem depender do nível.
    """
    if LIGADO:
        log.info("DIAG: " + formato, *args)
