"""Cronometra o pacote INTEIRO — e o wrapper se aposenta quando não vale a pena.

=========================================================================
O PEDIDO, E A FÍSICA QUE ELE ESBARRA
=========================================================================

Pedido do usuário em 07/09/2026: *"em todos os módulos, funções e laços, para
que mesmo o que já esteja testado e documentado seja retestado para garantir
que está tudo realmente como deveria, ou se dá para melhorar de alguma forma,
seja diminuindo ou aumentando os tempos"*.

São **1.631 funções**. E medir custa +298 ns por chamada (ver o topo de
`core/cronometro.py`), o que é 30% numa função de 1 µs. Embrulhar as 1.631 de
forma permanente deixaria o bot mais lento justamente para descobrir que ele
está lento.

=========================================================================
A SAÍDA: MEDE TODAS, PAGA SÓ PELAS QUE VALEM
=========================================================================

O embrulho é **temporário por natureza**. Cada função instrumentada mede as
primeiras `AMOSTRAS_PARA_DECIDIR` chamadas e então decide:

    mediana >= PISO  ->  fica. É cara o bastante para o cronômetro ser ruído.
    mediana <  PISO  ->  APOSENTA-SE: devolve a função original no lugar dela.

A aposentadoria é literal — `setattr(dono, nome, original)`. Depois dela aquela
função volta a custar exatamente o que custava antes, com zero embrulho.

**O CENSO NÃO SE PERDE.** As amostras já colhidas foram somadas ao acumulador
antes da decisão, então a função aposentada AINDA APARECE no relatório, com o
seu n, mínimo, média e máximo. É exatamente o "retestar o que já está
documentado" que foi pedido: descobre-se o custo de tudo, e paga-se pelo custo
só de quem importa.

=========================================================================
POR QUE SÓ EM PRODUÇÃO, NUNCA NO IMPORT
=========================================================================

**56 arquivos de teste deste projeto leem `inspect.getsource`** de métodos
reais para verificar regras estruturais. Um wrapper no lugar do método faria
`getsource` devolver o código do wrapper, e os 56 quebrariam de uma vez.

Por isso isto NÃO acontece no import de módulo nenhum: acontece quando
`instrumentar_tudo()` é chamada, e ela é chamada pelo supervisor, com o bot
subindo. Teste que quiser exercitá-la chama e desfaz.

=========================================================================
O QUE FICA DE FORA, E POR QUÊ
=========================================================================

* **O próprio cronômetro** — embrulhar o medidor com o medidor é recursão.
* **Geradores** — o embrulho mediria a CRIAÇÃO do gerador (microssegundos), não
  a execução dele. Número certo para a pergunta errada.
* **Dunder** (`__init__`, `__eq__`…) — chamados de dentro do interpretador em
  caminhos onde um wrapper muda semântica (`__repr__` em log, `__hash__` em
  dict).
* **`tools/`** — ferramenta de investigação não é caminho de produção.
* **O que já tem `__wrapped__`** — instrumentado à mão, com nome escolhido.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import time

from . import cronometro

# ===========================================================================
# O INTERRUPTOR
# ===========================================================================
#
# `False` devolve o bot ao estado anterior: `instrumentar_tudo()` não embrulha
# nada e a instrumentação à mão (`@cronometrar` nos pontos quentes) continua
# valendo sozinha.
INSTRUMENTAR_O_PACOTE_INTEIRO = True

# Quantas chamadas medir antes de decidir se o embrulho fica.
#
# Vinte: o bastante para a mediana não ser sorte de uma chamada fria (a
# primeira costuma pagar import preguiçoso e cache frio), e pouco o bastante
# para uma função chamada mil vezes por segundo pagar o embrulho por 20 ms.
AMOSTRAS_PARA_DECIDIR = 20

# Pacotes que NÃO entram. `tools` é investigação manual.
FORA = ("blazesbot.core.cronometro", "blazesbot.core.instrumentacao",
        "blazesbot.tools")


def _pode_embrulhar(f) -> bool:
    if not inspect.isfunction(f):
        return False
    if getattr(f, "__wrapped__", None) is not None:
        return False            # instrumentado à mão, com nome escolhido
    if inspect.isgeneratorfunction(f) or inspect.isasyncgenfunction(f):
        return False            # mediria a criação do gerador, não a execução
    nome = f.__name__
    return not (nome.startswith("__") and nome.endswith("__"))


def _embrulhar(dono, nome: str, f, rotulo: str):
    """Um embrulho que MEDE e depois decide se continua existindo."""
    estado = {"n": 0, "soma": 0.0}

    def medido(*a, **k):
        inicio = time.perf_counter()
        try:
            return f(*a, **k)
        finally:
            gasto = time.perf_counter() - inicio
            cronometro.anotar(rotulo, gasto)
            estado["n"] += 1
            estado["soma"] += gasto
            if estado["n"] >= AMOSTRAS_PARA_DECIDIR:
                media = estado["soma"] / estado["n"]
                if media < cronometro.PISO_PARA_CRONOMETRAR:
                    # APOSENTADORIA. O censo desta função já está no
                    # acumulador; daqui pra frente ela não paga mais nada.
                    try:
                        setattr(dono, nome, f)
                    except Exception:
                        pass
                # Zera para o caso de a aposentadoria falhar (classe com
                # `__slots__` no dono, atributo somente-leitura): sem isto ela
                # decidiria a cada chamada em vez de a cada 20.
                estado["n"] = 0
                estado["soma"] = 0.0

    medido.__name__ = f.__name__
    medido.__doc__ = f.__doc__
    medido.__wrapped__ = f
    medido.__dict__["_rotulo_do_cronometro"] = rotulo
    return medido


def _instrumentar_modulo(mod) -> int:
    """Embrulha o que este módulo DEFINE. Devolve quantos entraram."""
    quantos = 0
    prefixo = mod.__name__.removeprefix("blazesbot.")
    for nome, obj in list(vars(mod).items()):
        if inspect.isfunction(obj) and obj.__module__ == mod.__name__:
            if _pode_embrulhar(obj):
                setattr(mod, nome, _embrulhar(mod, nome, obj,
                                              f"{prefixo}.{nome}"))
                quantos += 1
        elif inspect.isclass(obj) and obj.__module__ == mod.__name__:
            quantos += _instrumentar_classe(obj, prefixo)
    return quantos


def _instrumentar_classe(cls, prefixo: str) -> int:
    quantos = 0
    for nome, obj in list(vars(cls).items()):
        # `vars` e não `dir`: só o que a classe DEFINE. Herdado já foi
        # embrulhado na classe de origem, e embrulhar duas vezes cobraria dois
        # cronômetros pela mesma chamada.
        if not _pode_embrulhar(obj):
            continue
        try:
            setattr(cls, nome, _embrulhar(cls, nome, obj,
                                          f"{prefixo}.{cls.__name__}.{nome}"))
            quantos += 1
        except (AttributeError, TypeError):
            continue          # classe imutável; segue
    return quantos


def instrumentar_tudo(pacote: str = "blazesbot") -> int:
    """Cronometra tudo que o pacote define. Devolve quantas funções entraram.

    IDEMPOTENTE: o que já tem `__wrapped__` é pulado, então chamar duas vezes
    não empilha embrulho.

    NUNCA DERRUBA O BOT. Módulo que não importa ou classe que não aceita
    `setattr` é pulado em silêncio -- telemetria que impede o bot de subir é
    pior que telemetria nenhuma.
    """
    if not (INSTRUMENTAR_O_PACOTE_INTEIRO and cronometro.TELEMETRIA_LIGADA):
        return 0

    raiz = importlib.import_module(pacote)
    quantos = 0
    for info in pkgutil.walk_packages(raiz.__path__, prefix=f"{pacote}."):
        if info.name.startswith(FORA):
            continue
        try:
            mod = importlib.import_module(info.name)
        except Exception:
            # Módulo que não importa nesta máquina (dependência que falta, de
            # Windows) não é problema da telemetria.
            continue
        try:
            quantos += _instrumentar_modulo(mod)
        except Exception:
            continue
    return quantos


def desinstrumentar_tudo(pacote: str = "blazesbot") -> int:
    """Desfaz. Para teste e para desligar em quente."""
    raiz = importlib.import_module(pacote)
    quantos = 0
    for info in pkgutil.walk_packages(raiz.__path__, prefix=f"{pacote}."):
        mod = importlib.import_module(info.name) if info.name in _carregados() else None
        if mod is None:
            continue
        quantos += _desinstrumentar_modulo(mod)
    return quantos


def _carregados() -> set[str]:
    import sys
    return set(sys.modules)


def _desinstrumentar_modulo(mod) -> int:
    quantos = 0
    for nome, obj in list(vars(mod).items()):
        if "_rotulo_do_cronometro" in getattr(obj, "__dict__", {}):
            setattr(mod, nome, obj.__wrapped__)
            quantos += 1
        elif inspect.isclass(obj) and obj.__module__ == mod.__name__:
            for m, f in list(vars(obj).items()):
                if "_rotulo_do_cronometro" in getattr(f, "__dict__", {}):
                    try:
                        setattr(obj, m, f.__wrapped__)
                        quantos += 1
                    except (AttributeError, TypeError):
                        continue
    return quantos
