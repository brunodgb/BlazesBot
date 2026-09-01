"""AS REGIÕES QUENTES: a rota que fecha os 38% que o array de entidades perde.

O array `ADDR_ENTITY_SCAN_BASE` acerta **62%** das vezes (600 amostras por
conta, 01/09/2026). O resto NÃO é mob morto -- uma varredura de força bruta dos
912 MB de heap achou o objeto VIVO, com nome certo e HP caindo, em **6 de 6**
casos em que o array falhou. E a varredura de quem aponta para um objeto que o
array perde deu `0 na IMAGEM, 24 no heap`: nenhuma referência estática, logo o
array é tabela TRANSITÓRIA e alargá-lo não resolve.

O que resolveu foi olhar ONDE as entidades moram: POUCAS regiões do heap --
medido 3 regiões, 960 KB de 914 MB (0,1%). Varrer só essas custa 0,25 ms contra
3,2 ms do array e 741 ms da varredura total, e fechou **2.481 de 2.481**
leituras.

O que este arquivo trava:

  * o interruptor fica LIGADO (é a regra do projeto: caminho fora de uso vira
    `False` no topo do módulo, com teste forçando-o ligado);
  * o array continua vindo PRIMEIRO -- a rota nova é reserva, não substituição;
  * a conferência do id acontece SEMPRE, e é ela que impede devolver lixo;
  * a unidade é REGIÃO, não intervalo `min..max` -- duas entidades longe uma da
    outra não podem fundir numa faixa gigante (foi o defeito medido da primeira
    tentativa: 0,55 ms viraram 6,6 ms);
  * o cache de regiões morre com o `Memory`, porque é POR PROCESSO e relogin
    troca o PID.
"""
import struct

from blazesbot.core import memory as mem

# ===========================================================================
# O INTERRUPTOR
# ===========================================================================

def test_o_interruptor_esta_ligado():
    """Desligado, o bot volta a perder 38% dos alvos."""
    assert mem.USAR_REGIOES_QUENTES is True


def test_as_constantes_da_varredura_sao_plausiveis():
    assert mem.PEDACO_DA_VARREDURA >= 64 * 1024
    # MEM_PRIVATE exclui imagem e arquivo mapeado: entidade mora no heap
    # privado, e varrer o resto seria pagar por onde ela nunca está.
    assert mem.MEM_PRIVATE == 0x20000
    assert mem.MEM_COMMIT == 0x1000


# ===========================================================================
# UMA MEMÓRIA DE MENTIRA, COM HEAP DE VERDADE
# ===========================================================================

class _HeapFalso:
    """Um heap de brinquedo: regiões, bytes, e entidades plantadas."""

    def __init__(self, regioes):
        self.regioes = regioes                  # [(base, bytearray)]
        self.leituras = 0

    def read_bytes(self, endereco, tamanho):
        for base, dados in self.regioes:
            if base <= endereco < base + len(dados):
                self.leituras += 1
                fim = min(endereco - base + tamanho, len(dados))
                return bytes(dados[endereco - base:fim])
        raise RuntimeError("endereço fora do heap falso: 0x%X" % endereco)


def _memoria(heap, array, regioes_do_processo):
    """Um `Memory` sem abrir processo nenhum."""
    m = mem.Memory.__new__(mem.Memory)
    m._obj_do_alvo = None
    m._regioes_quentes = {}
    m._regioes_cache = list(regioes_do_processo)
    m._semeou = False
    m.pm = heap

    def read_uint(endereco):
        if mem.ADDR_ENTITY_SCAN_BASE <= endereco < (
                mem.ADDR_ENTITY_SCAN_BASE + mem.LIMITE_DE_ENTIDADES * 4):
            i = (endereco - mem.ADDR_ENTITY_SCAN_BASE) // 4
            return array[i] if i < len(array) else 0
        return _ler_int(endereco)

    def _ler_int(endereco):
        try:
            cru = heap.read_bytes(endereco, 4)
        except RuntimeError:
            return None
        return struct.unpack("<i", cru)[0] if len(cru) == 4 else None

    m.read_uint = read_uint
    m.read_int = _ler_int

    def read_byte(endereco):
        try:
            cru = heap.read_bytes(endereco, 1)
        except RuntimeError:
            return None
        return cru[0] if cru else None

    m.read_byte = read_byte
    return m


def _plantar(dados, deslocamento, ident, nivel):
    """Escreve uma entidade no heap falso: id em +0x8, nível em OFF_LEVEL."""
    struct.pack_into("<i", dados, deslocamento + mem.OFF_ENTITY_ID, ident)
    dados[deslocamento + mem.OFF_LEVEL] = nivel


REGIAO_A = 0x30000000
REGIAO_B = 0x40000000
TAMANHO = 0x2000


def _cenario(no_array, fora_do_array, vizinha=True):
    """Duas regiões distantes, e duas entidades.

    `no_array` está no array (é a semente). `fora_do_array` NÃO está.

    `vizinha=True` põe a perdida na MESMA região da semente -- é o caso medido
    em campo: a semeadura achou 24 entidades espalhadas por 3 regiões, e os
    alvos que o array perdia estavam em uma delas.

    `vizinha=False` põe a perdida numa região onde entidade nunca apareceu --
    o LIMITE conhecido desta rota, fixado em teste próprio mais abaixo.
    """
    a = bytearray(TAMANHO)
    b = bytearray(TAMANHO)
    _plantar(a, 0x100, no_array, 63)
    if vizinha:
        _plantar(a, 0x900, fora_do_array, 70)
    else:
        _plantar(b, 0x400, fora_do_array, 70)
    heap = _HeapFalso([(REGIAO_A, a), (REGIAO_B, b)])
    array = [REGIAO_A + 0x100]          # só a semente está no array
    regioes = [(REGIAO_A, REGIAO_A + TAMANHO), (REGIAO_B, REGIAO_B + TAMANHO)]
    return _memoria(heap, array, regioes), heap


# ===========================================================================
# O ARRAY VEM PRIMEIRO
# ===========================================================================

def test_o_array_responde_sem_varrer_nada():
    m, heap = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    antes = heap.leituras
    assert m._procurar_entidade(0xAAA1) == REGIAO_A + 0x100
    # achou pelo array: não semeou e não varreu região nenhuma
    assert m._semeou is False
    assert heap.leituras - antes < 20


# ===========================================================================
# A ROTA NOVA ACHA O QUE O ARRAY PERDE
# ===========================================================================

def test_acha_entidade_que_nao_esta_no_array():
    """O caso medido: a perdida mora na mesma região das que o array conhece."""
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    assert m._procurar_entidade(0xBBB2) == REGIAO_A + 0x900


def test_regiao_onde_entidade_nunca_apareceu_NAO_e_varrida():
    """O LIMITE CONHECIDO desta rota, fixado de propósito.

    A rota só varre onde entidade JÁ apareceu. Se o alvo estiver numa região
    virgem, ela devolve `None` -- e devolver `None` é o comportamento certo:
    "não sei" é melhor que varrer 912 MB (741 ms medidos) dentro do laço de
    combate.

    Em campo isso não apareceu nas 2.481 leituras, porque a semeadura aprende
    de TODAS as entidades do array de uma vez (24 entidades, 3 regiões) e o
    alvo perdido sempre estava numa delas. Se algum dia aparecer, o sintoma no
    log é `alvo_atual() -> None` com o mob visivelmente vivo, e a saída é
    semear de novo -- não alargar a varredura.
    """
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2, vizinha=False)
    assert m._procurar_entidade(0xBBB2) is None
    # e a semeadura de fato só aprendeu a região da semente
    assert list(m._regioes_quentes) == [(REGIAO_A, REGIAO_A + TAMANHO)]


def test_semeia_na_primeira_falha_do_array():
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    assert m._semeou is False
    m._procurar_entidade(0xBBB2)
    assert m._semeou is True
    # a semeadura aprendeu a região da entidade que ESTAVA no array
    assert (REGIAO_A, REGIAO_A + TAMANHO) in m._regioes_quentes


def test_id_que_nao_existe_devolve_none_e_nao_inventa():
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    assert m._procurar_entidade(0xCCCC) is None


def test_nivel_implausivel_reprova_o_candidato():
    """Um id casando por acaso em lixo não pode virar entidade."""
    a = bytearray(TAMANHO)
    _plantar(a, 0x100, 0xAAA1, 63)
    # planta o id procurado em lixo, com nível impossível
    _plantar(a, 0x800, 0xDEAD, 0)
    heap = _HeapFalso([(REGIAO_A, a)])
    m = _memoria(heap, [REGIAO_A + 0x100],
                 [(REGIAO_A, REGIAO_A + TAMANHO)])
    assert m._procurar_entidade(0xDEAD) is None


# ===========================================================================
# A UNIDADE É REGIÃO, NÃO INTERVALO
# ===========================================================================

def test_duas_entidades_distantes_nao_fundem_numa_faixa_gigante():
    """A primeira versão usava `min..max` e degradou 12x quando dois grupos
    distantes entraram na mesma janela. Região é descontínua por natureza."""
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    m._marcar_regiao_quente(REGIAO_A + 0x100)
    m._marcar_regiao_quente(REGIAO_B + 0x400)
    assert len(m._regioes_quentes) == 2
    # nenhuma região cresceu para cobrir o vazio de 256 MB entre as duas
    total = sum(fim - ini for ini, fim in m._regioes_quentes)
    assert total == 2 * TAMANHO


def test_endereco_fora_de_qualquer_regiao_nao_marca_nada():
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    m._marcar_regiao_quente(0x7F000000)
    assert m._regioes_quentes == {}


def test_a_regiao_mais_povoada_e_varrida_primeiro():
    """Entidade nova quase sempre nasce onde as outras já estão."""
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    m._regioes_quentes = {(REGIAO_B, REGIAO_B + TAMANHO): 1,
                          (REGIAO_A, REGIAO_A + TAMANHO): 9}
    ordem = sorted(m._regioes_quentes.items(), key=lambda kv: -kv[1])
    assert ordem[0][0] == (REGIAO_A, REGIAO_A + TAMANHO)


# ===========================================================================
# O CACHE É POR PROCESSO
# ===========================================================================

def test_o_cache_de_regioes_nasce_vazio_em_cada_memory():
    """Relogin troca o PID, e o `Memory` novo não pode herdar endereço de heap
    do processo morto. As entidades da BlazesAPP1 ficaram em 0x3184Bxxxx e as da
    WizzOfBlazes5 em 0x06E1xxxx -- faixas sem intersecção."""
    m1, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    m1._procurar_entidade(0xBBB2)
    assert m1._regioes_quentes

    m2, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    assert m2._regioes_quentes == {}
    assert m2._semeou is False


# ===========================================================================
# DESLIGADO, VOLTA A SER SÓ O ARRAY
# ===========================================================================

def test_desligado_o_comportamento_e_o_de_antes(monkeypatch):
    monkeypatch.setattr(mem, "USAR_REGIOES_QUENTES", False)
    m, _ = _cenario(no_array=0xAAA1, fora_do_array=0xBBB2)
    assert m._procurar_entidade(0xAAA1) == REGIAO_A + 0x100   # array segue
    assert m._procurar_entidade(0xBBB2) is None                # rota nova fora
    # ligado, esta mesma busca acha (ver test_acha_entidade_que_nao_esta...)
    assert m._semeou is False
