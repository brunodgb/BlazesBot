"""OS PONTEIROS MEDIDOS QUE AINDA NAO DECIDEM NADA.

Pedido do usuario em 02/09/2026: "colocar tudo em producao os ponteiros que
realmente funcionam e documentar bem o que cada ponteiro faz, mesmo que hoje nao
utilize".

Entram como CAPACIDADE e aparecem no diagnostico -- nenhuma decisao do bot
depende deles. O que este arquivo trava e que eles nao se perdam, que a
aritmetica do espelho continue certa, e que "nao sei" siga sendo `None`.

=========================================================================
O BLOCO DE +0x3A0 -- E A HIPOTESE QUE ELE DERRUBOU
=========================================================================

O objeto do personagem guarda uma SEGUNDA COPIA do bloco de estado:

    hp    0x3B8  <->  0x758        xp    0x3C8  <->  0x768
    mp    0x3BC  <->  0x75C        ouro  0x410  <->  0x7B0

O QUE EU AFIRMEI, E ERA FALSO: "as quatro concordam em 6 de 6 clientes, entao e
uma SEGUNDA FONTE do mesmo instante -- divergir significa que a leitura esta
errada". Isso fecharia de graca a exigencia de "duas fontes no mesmo instante"
que este projeto cobra de toda leitura, o que era bom demais para ser verdade.

COMO CAIU:

  * campo: 19 divergencias em 720 comparacoes, TODAS no `hp`, todas em contas
    em COMBATE;
  * eu culpei a minha janela de leitura e passei a ler o par num bloco unico --
    e as divergencias AUMENTARAM (de 2 em 480 para 19 em 720);
  * amostragem de 20 ms: 2945 amostras, 10 divergentes, o atrasado MAIOR em
    19 de 19, e as 10 divergentes sendo UM evento que se resolveu em 204 ms.

E UMA COPIA ATRASADA ~200 ms. Divergir quer dizer "mudou agora", nao "errou" --
como validador ele acusaria durante o combate, que e quando o bot mais precisa
confiar no que le.

O ATRASO VIRA CAPACIDADE: comparar as duas copias diz "o HP caiu" sem guardar
estado entre ticks e sem depender de quando foi o tick anterior, numa leitura
so. E o que `hp_caiu_agora` faz.
"""
from __future__ import annotations

import inspect
import struct

from blazesbot.core import memory as mem

# ===========================================================================
# O ESPELHO
# ===========================================================================

def test_a_aritmetica_do_espelho_fecha_nos_quatro():
    """Se um offset novo entrar no bloco, o espelho dele e offset + 0x3A0."""
    assert mem.ESPELHO_DELTA == 0x3A0
    pares = (
        (mem.OFF_HP, mem.OFF_HP_ESPELHO),
        (mem.OFF_MP, mem.OFF_MP_ESPELHO),
        (mem.OFF_XP, mem.OFF_XP_ESPELHO),
        (mem.OFF_GOLD, mem.OFF_GOLD_ESPELHO),
    )
    for original, espelho in pares:
        assert original + mem.ESPELHO_DELTA == espelho, (
            "0x%X + 0x3A0 deveria ser 0x%X" % (original, espelho))


def test_os_offsets_do_espelho_sao_os_medidos():
    assert mem.OFF_HP_ESPELHO == 0x758
    assert mem.OFF_MP_ESPELHO == 0x75C
    assert mem.OFF_XP_ESPELHO == 0x768
    assert mem.OFF_GOLD_ESPELHO == 0x7B0


BASE_FALSA = 0x30000000


def _memoria(valores, bloco_ilegivel=False, sem_personagem=False):
    """Uma memoria de mentira que serve um BLOCO CRU.

    O `espelho_confere` le um bloco unico de proposito, para garantir que
    original e espelho vem do MESMO INSTANTE -- entao o duble tem de servir
    bytes, nao inteiros avulsos.
    """
    m = mem.Memory.__new__(mem.Memory)
    inicio = min(mem.OFF_HP, mem.OFF_MP, mem.OFF_XP, mem.OFF_GOLD)
    fim = max(mem.OFF_HP_ESPELHO, mem.OFF_MP_ESPELHO,
              mem.OFF_XP_ESPELHO, mem.OFF_GOLD_ESPELHO) + 4
    bloco = bytearray(fim - inicio)
    for off, valor in valores.items():
        struct.pack_into("<i", bloco, off - inicio, valor)

    class _Pm:
        @staticmethod
        def read_bytes(endereco, tamanho):
            if bloco_ilegivel:
                raise RuntimeError("regiao ilegivel")
            deslocamento = endereco - (BASE_FALSA + inicio)
            return bytes(bloco[deslocamento:deslocamento + tamanho])

    m.pm = _Pm()
    m.read_uint = lambda _endereco: (0 if sem_personagem else BASE_FALSA)

    def campo(off):
        return BASE_FALSA + off

    def ler(endereco):
        off = endereco - BASE_FALSA
        return valores.get(off)

    m._player_field = campo
    m.read_int = ler
    return m


def _memoria_simples(valores, ilegivel=()):
    """Duble para os leitores campo-a-campo (`experiencia`, `relogio_ms`).

    Eles nao precisam de bloco: cada um le um offset so, e nao ha par para
    conferir no mesmo instante.
    """
    m = mem.Memory.__new__(mem.Memory)

    def campo(off):
        return None if off in ilegivel else BASE_FALSA + off

    def ler(endereco):
        if endereco is None:
            return None
        return valores.get(endereco - BASE_FALSA)

    m._player_field = campo
    m.read_int = ler
    return m


def _assentado():
    return {
        mem.OFF_HP: 1987, mem.OFF_HP_ESPELHO: 1987,
        mem.OFF_MP: 4666, mem.OFF_MP_ESPELHO: 4666,
        mem.OFF_XP: 89064, mem.OFF_XP_ESPELHO: 89064,
        mem.OFF_GOLD: 597839, mem.OFF_GOLD_ESPELHO: 597839,
    }


def test_bloco_assentado_devolve_os_pares_iguais():
    m = _memoria(_assentado())
    assert m.bloco_atrasado() == {"hp": (1987, 1987), "mp": (4666, 4666),
                                  "xp": (89064, 89064),
                                  "ouro": (597839, 597839)}
    assert m.hp_caiu_agora() == 0


def test_o_hp_caindo_aparece_como_QUANTO_caiu():
    """O caso medido: atrasado MAIOR que o atual, dentro da janela de ~200 ms."""
    valores = _assentado()
    valores[mem.OFF_HP] = 1783                    # levou 204 de dano
    m = _memoria(valores)
    assert m.bloco_atrasado()["hp"] == (1783, 1987)
    assert m.hp_caiu_agora() == 204


def test_hp_SUBINDO_nao_vira_dano_negativo():
    """A subida NAO foi medida -- nas contas livres o HP estava cheio e nenhuma
    tecla da barra gastou mana fora de batalha. Caso nao observado sai `0`, nunca
    um negativo que alguem somaria por acidente."""
    valores = _assentado()
    valores[mem.OFF_HP] = 2200
    m = _memoria(valores)
    assert m.hp_caiu_agora() == 0


def test_o_bloco_ilegivel_devolve_None_INTEIRO_e_nao_False():
    m = _memoria(_assentado(), bloco_ilegivel=True)
    assert m.bloco_atrasado() is None
    assert m.hp_caiu_agora() is None


def test_sem_personagem_carregado_devolve_None():
    m = _memoria(_assentado(), sem_personagem=True)
    assert m.bloco_atrasado() is None
    assert m.hp_caiu_agora() is None


def test_o_par_e_lido_em_UMA_leitura():
    """Em duas chamadas o intervalo entre elas entra na diferenca -- e a
    diferenca e exatamente o que se quer medir."""
    fonte = inspect.getsource(mem.Memory.bloco_atrasado)
    assert "read_bytes" in fonte
    assert "BLOCO UNICO" in fonte


def test_NAO_existe_leitor_que_trate_o_atraso_como_ERRO_DE_LEITURA():
    """A hipotese refutada nao pode voltar disfarcada de melhoria: ela concluia
    "a leitura esta errada" de uma diferenca que e so o atraso de 200 ms, e
    acusaria justamente durante o combate."""
    assert not hasattr(mem.Memory, "espelho_confere"), (
        "espelho_confere voltou -- ele lia a copia atrasada como segunda fonte "
        "do mesmo instante, e isso foi refutado com 2945 amostras de 20 ms")
    fonte = inspect.getsource(mem.Memory.bloco_atrasado)
    assert "NAO E VALIDADOR" in fonte


def test_o_atraso_medido_fica_escrito_junto_do_offset():
    """Sem o numero, o proximo a ler isto refaz a hipotese errada."""
    fonte = inspect.getsource(mem)
    assert "204 ms" in fonte
    assert "HIPOTESE REFUTADA" in fonte


# ===========================================================================
# EXPERIENCIA -- os dois acumuladores, com o significado EM ABERTO
# ===========================================================================

def test_experiencia_devolve_os_dois():
    m = _memoria_simples({mem.OFF_XP: 89064, mem.OFF_XP_SECUNDARIA: 2107})
    assert m.experiencia() == (89064, 2107)


def test_experiencia_ilegivel_e_None():
    m = _memoria_simples({}, ilegivel={mem.OFF_XP, mem.OFF_XP_SECUNDARIA})
    assert m.experiencia() == (None, None)


def test_o_significado_da_xp_fica_declarado_como_ABERTO():
    """Nao se pode chamar 0x3C8 de "a XP": a barra do jogo mostra 4.5291% e
    nenhum par de DWORD do objeto reproduz esse numero. Quem ler tem de saber."""
    fonte = inspect.getsource(mem.Memory.experiencia)
    assert "NAO ESTA DETERMINADO" in fonte or "NÃO ESTÁ DETERMINADO" in fonte


# ===========================================================================
# O RELOGIO
# ===========================================================================

def test_relogio_ms():
    m = _memoria_simples({mem.OFF_RELOGIO_MS: 25484745})
    assert m.relogio_ms() == 25484745
    assert mem.OFF_RELOGIO_MS == 0x85C


def test_relogio_ilegivel_e_None():
    m = _memoria_simples({}, ilegivel={mem.OFF_RELOGIO_MS})
    assert m.relogio_ms() is None


def test_o_relogio_declara_que_nao_foi_testado_travado():
    """Ele e candidato a detector de congelamento, mas nunca foi visto com um
    cliente de fato travado -- e isso tem de estar escrito, senao alguem faz o
    watchdog depender dele."""
    fonte = inspect.getsource(mem.Memory.relogio_ms)
    assert "NUNCA TESTADO" in fonte or "nunca testado" in fonte


# ===========================================================================
# O NIVEL DO MEMBRO DO TIME
# ===========================================================================

def test_o_nivel_do_membro_esta_no_offset_medido():
    """Desalinhado de proposito: uma busca por int32 alinhado nunca o acharia,
    e foi a busca exaustiva que o achou."""
    assert mem.OFF_MEMBRO_NIVEL == 0x42
    assert mem.OFF_MEMBRO_NIVEL % 4 != 0


def test_os_tres_campos_do_membro_cabem_no_passo():
    """Os campos medidos ficam dentro dos 0x88 bytes do bloco do membro."""
    for off in (mem.OFF_MEMBRO_HP, mem.OFF_MEMBRO_MANA_MAXIMA,
                mem.OFF_MEMBRO_NIVEL):
        assert 0 <= off < mem.PASSO_ENTRE_MEMBROS


# ===========================================================================
# O DIAGNOSTICO EXPOE AS CAPACIDADES NOVAS
# ===========================================================================

def test_o_probe_expoe_o_bloco_atrasado_xp_e_relogio():
    """Capacidade que nao decide nada ainda TEM de aparecer no diagnostico --
    e assim que ela e conferida em campo antes de alguem depender dela."""
    fonte = inspect.getsource(mem.Memory.probe)
    for chave in ("bloco +0x3A0 (atraso ~200 ms)",
                  "hp caiu nos ultimos ~200 ms", "xp (0x3C8, 0x3CC)",
                  "relogio ms (0x85C)"):
        assert chave in fonte, "o probe deixou de expor %r" % chave
