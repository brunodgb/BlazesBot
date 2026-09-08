"""APELIDO -- o deletador mora em `bot/deletador.py` desde 08/09/2026.

=========================================================================
POR QUE SUBIU
=========================================================================

Ele nasceu no ecossistema APP e virou peça de TRÊS: o APP limpa a bolsa entre
voltas da macro, e as duas caves precisam apagar o lixo que o NPC não compra.

`bot/hh/` NÃO PODE IMPORTAR `bot/app/` -- `tests/test_ecossistemas.py` cruza
todos os pares de ecossistema, e o supervisor é a única exceção. Então a
alternativa a promover era DUPLICAR o módulo, e duplicar código que APAGA item
é ter duas listas de exclusão divergindo em silêncio.

O destino é `bot/` e não `core/` porque ele recebe `BotContext`: o critério é o
que o módulo IMPORTA, não o quanto ele parece genérico.

=========================================================================
POR QUE APELIDO, E NÃO RE-EXPORTAÇÃO NOME POR NOME
=========================================================================

`_estado_das_filas` é REBINDADO com `global` dentro do módulo. Uma re-exportação
copia o valor no instante do import, e a partir daí as duas cópias divergem --
quem olhasse por aqui veria a fila de antes. Trocar `sys.modules` devolve o
MESMO objeto de módulo, então estado, `global` e monkeypatch de teste continuam
funcionando como se nada tivesse mudado de lugar.

=========================================================================
DEPENDÊNCIA CRUZADA: MEXER LÁ MEXE NOS TRÊS
=========================================================================

**Quem usa:** `bot/supervisor.py` (limpeza entre voltas do APP),
`bot/hh/routine.py` (manutenção da HH, com pasta PRÓPRIA) e as ferramentas de
aferição do APP.

**O que NÃO subiu:** nada. O módulo foi inteiro.
"""
from __future__ import annotations

import sys

from .. import deletador as _real

sys.modules[__name__] = _real
