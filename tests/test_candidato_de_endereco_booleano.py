"""Testa `candidato_de_endereco_booleano`, o primitivo booleano da calibração.

=============================================================================
O QUE ESTE ARQUIVO PROTEGE
=============================================================================

`candidato_de_endereco_booleano` (memory.py) é o único ponto onde o
`+0x60` de `ADDR_MODAL` e `ADDR_LOOT_WINDOW` passa pelo placar. Ele é chamado
por `_prover_o_modal` (vendor.py) e `_prover_a_janela_de_loot` (routine.py) para
cada candidato, e o resultado alimenta `calibracao.julgar_booleano`.

O método sofre DUAS escolhas de projeto que têm conseqüências diretas no
placar, e este arquivo fixa ambas:

1. **None vs False na falha de leitura.** `read_int` devolve `None` quando a
   memória não responde (processo fechando, ponteiro inválido). O método
   **precisa** propagar o `None` -- `julgar_booleano` o conta como SILENCIO
   (`acertou=None`), e acumula em `sem_leitura`. Trinta silêncios encerram o
   candidato como `sem_resposta`. Um `False` mentiroso seria contado como
   `acertou=False` (erro), e atrasaria o descarte de um offset que nunca existiu.

2. **bool(valor) vs valor == 1.** A flag é "0 = ausente, 1 = presente", mas
   `read_int` lê DINT — um bit de padding ou overflow pode devolver 2, 3...
   `bool(valor)` trata tudo >0 como True; `== 1` rejeitaria um candidato
   perfeitamente válido só porque leu 2.

Sem este teste nenhuma das duas garantias está em lugar nenhum: o método é
três linhas e "óbvio", e o óbvio é o primeiro a quebrar sem aviso.
"""
import pytest

from blazesbot.core.memory import Memory


def _memory_lendo(valor: object) -> Memory:
    """Instância de `Memory` cujo `read_int` devolve `valor` para qualquer
    endereço -- sem abrir processo nenhum."""
    m = Memory.__new__(Memory)
    m.pm = None
    m.pid = 0
    m.read_int = lambda _addr: valor      # type: ignore[method-assign]
    return m


# ---------------------------------------------------------------------------
# 1. None na falha de leitura -- a distinção que salva do placar
# ---------------------------------------------------------------------------

def test_none_propaga_para_julgar_booleano():
    """`read_int` falhou (processo morreu) → `None`, nunca `False`.

    `julgar_booleano` faz `if lido is None or na_tela is None`, e o `None`
    vira `acertou=None` → `sem_leitura`. Um `False` aqui apagaria a distinção
    e o candidato nunca chegaria a `sem_resposta`.
    """
    m = _memory_lendo(None)
    assert m.candidato_de_endereco_booleano(0x012CE3BC) is None


def test_zero_devolve_false():
    """Endereço existe, flag desligada → `False` (não `None`)."""
    m = _memory_lendo(0)
    assert m.candidato_de_endereco_booleano(0x012CE3BC) is False


# ---------------------------------------------------------------------------
# 2. bool(valor), não valor == 1
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [1, 2, 3, 0x10, 0xFF, 0xFFFFFFFF])
def test_qualquer_valor_nao_zero_e_true(valor):
    """Qualquer inteiro não-zero é True. Isso é o contrato, não é acidente.

    O cliente usa DINT; `read_int` pode trazer bits de padding. `bool(2)` é
    True, e isso é exatamente o que `julgar_booleano` espera:
    `bool(lido) == bool(na_tela)`.
    """
    m = _memory_lendo(valor)
    assert m.candidato_de_endereco_booleano(0x012CE3BC) is True


# ---------------------------------------------------------------------------
# 3. Os dois candidatos reais passam pelo mesmo primitivo
# ---------------------------------------------------------------------------

def test_os_dois_candidatos_do_modal_sao_independentes():
    """O método NÃO escolhe -- testa cada candidato isoladamente.

    `CANDIDATOS_DO_MODAL = (0x012CE35C, 0x012CE3BC)`: o herdado do GhostBot e
    o +0x60. O seletor (`escolher`) decide uma vez; este método é chamado com
    CADA um para que a calibração pontue individualmente. Se um dos dois
   respondesse e o outro não, o placar tem que refletir isso — não um "sim
    médio" entre os dois.
    """
    valores = {0x012CE35C: 0, 0x012CE3BC: 1}
    m = Memory.__new__(Memory)
    m.pm = None
    m.pid = 0
    m.read_int = lambda addr: valores[addr]      # type: ignore[method-assign]

    assert m.candidato_de_endereco_booleano(0x012CE35C) is False
    assert m.candidato_de_endereco_booleano(0x012CE3BC) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
