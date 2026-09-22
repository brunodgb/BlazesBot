"""A ÂNCORA DO TIME — o ponto inicial do líder, que vale para todos.

Cada conta guarda o SEU ponto inicial (`app._base_pos_x/_y` no config, ou a
primeira posição lida). Em time isso ESPALHA o grupo: quem ligou o bot dois
passos para o lado volta para dois passos para o lado, e a trava de distância de
cada um puxa para um lugar diferente. Sob ataque isso é um time esticado — a
Fada fora do alcance da cura, o dano longe do mob que bate no vizinho.

Pedido do usuário em 22/09/2026: em time, o ponto do LÍDER vale para todos.

=========================================================================
POR QUE UM ARQUIVO SÓ PARA ISTO
=========================================================================

Mesmo motivo do `mural_da_morte.py`: o `mural.py` está no teto de 800 linhas do
portão de qualidade, e a âncora é justamente uma parte que não compartilha
estado com o resto — um dicionário próprio, uma tranca própria. O `mural`
reexporta tudo, então quem lê continua dizendo `mural.publicar_ancora(...)`.

=========================================================================
SEM VALIDADE, AO CONTRÁRIO DA LARGADA
=========================================================================

Uma largada é um INSTANTE (entrou ou perdeu); a âncora é um FATO que dura a
sessão inteira do líder. Um prazo aqui faria o seguidor perder a referência no
meio do farm e voltar para a dele — exatamente o espalhamento que isto existe
para impedir. Quem apaga é o líder, ao encerrar o modo APP.
"""
from __future__ import annotations

import threading

_ANCORAS: dict[str, tuple[int, int]] = {}      # login do líder -> (x, y)
_LOCK_ANCORA = threading.Lock()


def publicar_ancora(lider: str, ponto: tuple[int, int] | None) -> None:
    """O líder publica o ponto inicial que o time inteiro vai usar.

    `None` e `(0, 0)` são RECUSADOS: (0,0) é o que a leitura de posição devolve
    quando o personagem ainda não entrou no mundo, e ancorar o time ali mandaria
    todo mundo andar para o canto do mapa.
    """
    if not lider or ponto is None:
        return
    x, y = ponto
    if x == 0 and y == 0:
        return
    with _LOCK_ANCORA:
        _ANCORAS[lider.strip().lower()] = (int(x), int(y))


def ancora_do_time(lider: str) -> tuple[int, int] | None:
    """O ponto inicial que o líder publicou. `None` = ele ainda não publicou."""
    if not lider:
        return None
    with _LOCK_ANCORA:
        return _ANCORAS.get(lider.strip().lower())


def esquecer_ancora(lider: str) -> None:
    """O líder parou: a âncora dele não descreve mais nada."""
    if not lider:
        return
    with _LOCK_ANCORA:
        _ANCORAS.pop(lider.strip().lower(), None)


def zerar_para_teste() -> None:
    """Esvazia o quadro. SÓ para teste — ver `mural.zerar_o_time_para_teste`."""
    with _LOCK_ANCORA:
        _ANCORAS.clear()
