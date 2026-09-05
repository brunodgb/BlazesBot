"""O QUADRO DOS MORTOS -- quem caiu, desde quando, e quem já está sendo revivido.

Quadro SEPARADO do de cura (`mural.py`), e não é só arrumação: as duas filas têm
ordens diferentes. A de cura é rigorosamente por chegada; a de morte espera a vez
ATÉ um limite e então fura a fila dos feridos. Misturá-las obrigaria cada leitor
a perguntar "isto é morte ou ferimento?" a cada item.

Mora em arquivo próprio porque o `mural.py` encostou no teto de 800 linhas -- e
o quadro da morte é justamente a parte que não compartilha estado nenhum com o
resto: dicionários próprios, tranca própria. `mural` reexporta tudo, então quem
já dizia `mural.morri(...)` continua dizendo.
"""

from __future__ import annotations

import threading
import time

_LOCK_MORTE = threading.Lock()

# login -> (quando morreu, nick)
#
# A FILA DOS MORTOS É SEPARADA DA DOS FERIDOS de propósito. Elas têm ordens
# diferentes: a de cura é rigorosamente por chegada; a de morte espera a vez
# ATÉ um limite e então fura a fila. Misturá-las obrigaria cada leitor a
# perguntar "isto é morte ou ferimento?" a cada item.
_MORTOS: dict[str, tuple[float, str]] = {}
# login da vítima -> quando a Fada começou a conjurar o reviver nela
_CONJURANDO: dict[str, float] = {}

# A partir de quantos segundos de morto a vítima FURA a fila dos feridos.
#
# Decisão do usuário em 04/09/2026: *"o ideal é colocar o morto à frente só se
# estiver demorando muito (...) tirando isso a cura vem primeiro"*. Um ferido
# esperando alguns segundos a mais continua vivo; um morto esperando o farm
# inteiro é uma conta zerada.
#
# 40 s e não 50: o morto se revive sozinho em 60 s (`morte.PRAZO_PARA_A_FADA`) e
# a skill leva 5 s preparando. Com 50 a Fada começaria o feitiço encostada no
# prazo, contando com a esticada para não desperdiçar mana; com 40 ela tem
# folga de sobra.
SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA = 40.0


def morri(login: str, nick: str = "") -> None:
    """A conta avisa o time que caiu. Repetir não muda a hora da morte."""
    if not login:
        return
    chave = login.strip().lower()
    with _LOCK_MORTE:
        anterior = _MORTOS.get(chave)
        quando = anterior[0] if anterior else time.monotonic()
        _MORTOS[chave] = (quando, (nick or (anterior[1] if anterior else "")))


def esquecer_morte(login: str) -> None:
    """De pé de novo (ou desistiu) -- sai da fila dos mortos."""
    if not login:
        return
    chave = login.strip().lower()
    with _LOCK_MORTE:
        _MORTOS.pop(chave, None)
        _CONJURANDO.pop(chave, None)


def esta_morto(login: str) -> bool:
    if not login:
        return False
    with _LOCK_MORTE:
        return login.strip().lower() in _MORTOS


def fila_de_reviver(membros: list[str] | tuple[str, ...]) -> list[str]:
    """Os mortos do time, do que caiu primeiro para o que caiu por último."""
    permitidos = {m.strip().lower() for m in membros if m}
    with _LOCK_MORTE:
        itens = [(quando, login) for login, (quando, _n) in _MORTOS.items()
                 if login in permitidos]
    return [login for _quando, login in sorted(itens)]


def morto_ha_muito_tempo(login: str) -> bool:
    """Já passou da hora de este morto furar a fila dos feridos?"""
    if not login:
        return False
    with _LOCK_MORTE:
        dados = _MORTOS.get(login.strip().lower())
    if dados is None:
        return False
    return (time.monotonic() - dados[0]) >= SEGUNDOS_DE_MORTO_PARA_FURAR_A_FILA


def nick_do_morto(login: str) -> str:
    """O nick que a conta publicou ao morrer.

    A Fada precisa dele para achar o slot no painel, e o morto é justamente
    quem ela NÃO consegue perguntar de outro jeito.
    """
    if not login:
        return ""
    with _LOCK_MORTE:
        dados = _MORTOS.get(login.strip().lower())
    return dados[1] if dados else ""


def comecei_a_conjurar(login_vitima: str) -> None:
    """A Fada avisa que o feitiço de reviver COMEÇOU nesta vítima.

    Sem este aviso, o morto se auto-revive no meio dos 5 s de preparo: a Fada
    perde 1168 de mana e a janela de convite aparece para quem já está vivo.
    """
    if not login_vitima:
        return
    with _LOCK_MORTE:
        _CONJURANDO[login_vitima.strip().lower()] = time.monotonic()


def fada_conjurando_em(login_vitima: str) -> bool:
    """A Fada está conjurando o reviver em mim agora? Vale pelo tempo do preparo."""
    if not login_vitima:
        return False
    with _LOCK_MORTE:
        quando = _CONJURANDO.get(login_vitima.strip().lower())
    return quando is not None and (time.monotonic() - quando) <= VALIDADE_DO_FEITICO


# Por quanto tempo o aviso "estou conjurando" continua de pé.
#
# Os 5 s de preparo mais folga. Passado isso sem a vítima levantar, o feitiço
# não saiu (ela saiu de alcance, a Fada morreu, a tecla não pegou) -- e o morto
# volta a contar o prazo dele em vez de esperar para sempre por um feitiço que
# não vem.
VALIDADE_DO_FEITICO = 8.0
