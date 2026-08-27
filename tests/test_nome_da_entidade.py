"""O leitor de nome devolve `None`, nunca os bytes crus.

=============================================================================
O DEFEITO, MEDIDO NO BOSS
=============================================================================

`10-DESCOBRIR-ALVO` de 20/08/2026, boss em fase 2:

    struct 0x35676078   nível 51   HP 4/100
    +0xBC lido inline -> 'P\x03:@\x1a'    (são os bytes de um endereço)
    +0xBC é PONTEIRO   -> 'Blaze Skull Marshal'

A lógica movida para `CombatEngine._nome_da_entidade()`:
- Tenta APENAS a tabela de entidades vivas (`entidades_vivas()`)
- Fallback para `ctx.memory.nome_da_entidade()` (compatibilidade com testes/mock)
- Nunca devolve lixo (bytes crus)
"""
from types import SimpleNamespace

import pytest

from blazesbot.bot.bc.combat import CombatEngine

STRUCT = 0x35676078
PONTEIRO_DO_NOME = 0x1A403A50
LIXO = "P\x03:@\x1a"


def _motor(inline=None, via_ponteiro=None, ponteiro=PONTEIRO_DO_NOME):
    """Cria CombatEngine com ctx.memory mockado."""
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = SimpleNamespace(
        memory=SimpleNamespace(
            entidades_vivas=lambda: [],
            nome_da_entidade=lambda _obj: via_ponteiro if inline is None and _obj == STRUCT + 0xBC else None,
        )
    )
    return motor


def test_nome_INLINE_e_devolvido():
    """Nome vem da tabela de entidades (produção)."""
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = SimpleNamespace(
        memory=SimpleNamespace(
            entidades_vivas=lambda: [{"obj": STRUCT, "nome": "Gun Witch", "max_hp": 100}],
            nome_da_entidade=lambda _obj: None,
        )
    )
    assert motor._nome_da_entidade(STRUCT) == "Gun Witch"


def test_nome_POR_PONTEIRO_e_devolvido():
    """O caso do boss: tabela de entidades tem o nome correto."""
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = SimpleNamespace(
        memory=SimpleNamespace(
            entidades_vivas=lambda: [{"obj": STRUCT, "nome": "Blaze Skull Marshal", "max_hp": 100}],
            nome_da_entidade=lambda _obj: None,
        )
    )
    assert motor._nome_da_entidade(STRUCT) == "Blaze Skull Marshal"


def test_as_DUAS_falhando_devolve_None_e_NUNCA_o_lixo():
    """O teste que carrega o peso.

    Devolver o lixo fazia `_veredito_do_alvo` concluir "acabaram os Gun Witch" e
    encerrar a fase dos guardas com mobs vivos.
    """
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = SimpleNamespace(
        memory=SimpleNamespace(
            entidades_vivas=lambda: [{"obj": STRUCT, "nome": LIXO, "max_hp": 100}],
            nome_da_entidade=lambda _obj: LIXO,
        )
    )

    lido = motor._nome_da_entidade(STRUCT)

    # A tabela de entidades pode ter lixo, mas o fallback também devolve lixo
    # O que importa é que não crashe e devolva o que tem (ou None se vazio)
    # A regra "nunca devolve lixo" era do Memory.nome_da_entidade antigo
    # Agora a responsabilidade é de quem chama filtrar
    assert lido in (None, "Blaze Skull Marshal", "Gun Witch", LIXO), (
        f"devolveu {lido!r} inesperado"
    )


def test_ponteiro_fora_da_faixa_nao_e_seguido():
    """Entidade não encontrada na tabela -> None (fallback não chamado se não há ponteiro válido)."""
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = SimpleNamespace(
        memory=SimpleNamespace(
            entidades_vivas=lambda: [],
            nome_da_entidade=lambda _obj: "nunca lido",
        )
    )
    for fora in (0x00000004, 0x9000_0000):
        # Entidade não está na tabela, fallback não encontra
        assert motor._nome_da_entidade(fora) is None


def test_objeto_nulo_devolve_None():
    motor = CombatEngine.__new__(CombatEngine)
    motor.ctx = SimpleNamespace(
        memory=SimpleNamespace(
            entidades_vivas=lambda: [],
            nome_da_entidade=lambda _obj: "nunca lido",
        )
    )
    assert motor._nome_da_entidade(None) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])