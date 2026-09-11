"""MOB VÁLIDO TEM VIDA MÁXIMA 100 — e é assim que se sabe que é mob.

=========================================================================
O DEFEITO QUE ORIGINOU ESTE ARQUIVO
=========================================================================

Relato do usuário: *"em HH, parece que em algumas vezes não identifica que o
target morreu e não dá TAB, mas é só às vezes"*.

Nos logs, a assinatura:

    ALVO #461589701  0.0% [----------] (1/1177280513, nv1)  alvo novo
    ALVO #461589701  0.0% [----------] (1/1177280513, nv1)  +0%   (x5, por 9 s)

`max_hp = 1.177.280.513`, nível 1, sem nome. **Não é mob** — e os `max_hp`
absurdos são padrões de bits de FLOAT lidos como inteiro (`0x3F800000` = float
`1.0`). Com um fantasma preso, o HP não muda e o TAB não tem para onde ir.

Custo medido em ~23 h de HH: 44 leituras fantasma, 25 episódios, **250,5 s
travados**, pior episódio de **37,4 s**, 100% na fase `boss`.

=========================================================================
POR QUE O TESTE ANTIGO NÃO PEGAVA
=========================================================================

Era `hp <= max_hp`. O próprio projeto já tinha provado que não serve
(`core/entidades.py`, medição de 26/08/2026):

    "hp <= max_hp sozinho aprova qualquer coisa, porque max_hp gigante torna a
     relação trivialmente verdadeira"

Com `max_hp = 1177280513` e `hp = 1`, a relação é verdadeira e o lixo passava.

=========================================================================
A REGRA, E A MEDIÇÃO QUE A SUSTENTA
=========================================================================

Regra do usuário: *"mob e boss de verdade sempre vai ter a vida máxima 100"*.
Conferida contra **45.162 leituras** de alvo nos logs:

    conta APP    15.545 leituras   100,00% == 100   NENHUMA exceção
    conta BC     16.208 leituras    99,98% == 100   3 exceções (lixo)
    conta HH     13.409 leituras    98,96% == 100   46 + padrões de float

E o corte é limpo POR NOME, que é o que fecha: dos 99 nomes distintos já vistos
como alvo, todo nome real lê 100 e só 100 — `Elite Fatal Centipede` em 1439
leituras, `Green Robe Master` em 293, `Zaton` em 272, o boss `Gun Witch` (nv50)
em 7. Todo valor diferente de 100 veio de entrada SEM NOME (`#id`).
"""
from __future__ import annotations

import inspect
import logging

from blazesbot.core import memory as mem


def _memoria(hp, maximo, alvo_id=1108344853, nivel=1, nome=None):
    """Um alvo de mentira com o HP e o máximo que se quiser."""
    m = mem.Memory.__new__(mem.Memory)
    obj = 0x30000000
    valores = {
        mem.ADDR_TARGET_ID: alvo_id,
        obj + mem.OFF_ENTITY_ID: alvo_id,
        obj + mem.OFF_HP: hp,
        obj + mem.OFF_MAX_HP: maximo,
        obj + mem.OFF_LEVEL: nivel,
    }
    m.read_int = lambda e: valores.get(e)
    m.read_uint = lambda e: valores.get(e)
    m.read_byte = lambda e: valores.get(e)
    m.read_float = lambda e: 0.0
    m._obj_do_alvo = obj
    m._id_do_alvo = alvo_id
    m._procurar_entidade = lambda _id: obj
    m._nome_da_entidade = lambda _obj: nome
    return m


# ===========================================================================
# A CONSTANTE E O INTERRUPTOR
# ===========================================================================

def test_a_vida_maxima_de_mob_e_100():
    assert mem.VIDA_MAXIMA_DE_MOB == 100
    assert mem.EXIGIR_VIDA_MAXIMA_DE_MOB is True


def test_a_medicao_fica_escrita_junto_da_constante():
    """Sem os números, o próximo a ler isto afrouxa a regra por precaução."""
    fonte = inspect.getsource(mem)
    assert "45.162 leituras" in fonte
    assert "Gun Witch" in fonte


# ===========================================================================
# O FANTASMA MEDIDO É RECUSADO
# ===========================================================================

def test_o_fantasma_do_log_e_recusado():
    """O caso exato do log: `(1/1177280513, nv1)` sem nome."""
    assert _memoria(hp=1, maximo=1177280513).alvo_atual() is None


def test_os_outros_max_hp_do_log_tambem():
    """Todos são padrões de bits de float lidos como inteiro."""
    for maximo in (1065353216, 1230735792, 1153705192, 167772159, 15813412,
                   1868767232, 530806632, 901313472):
        assert _memoria(hp=0, maximo=maximo).alvo_atual() is None, (
            "max_hp=%d passou" % maximo)


def test_o_residuo_de_max_hp_1_tambem_e_recusado():
    """Os 13 que escapavam do teto de 5 milhões: `max_hp` de 1, 2 e 3.

    É por isso que a regra é `== 100` e não um teto: um teto alto não pega o
    lixo pequeno, e o lixo pequeno era 30% dos casos.
    """
    for maximo in (1, 2, 3):
        assert _memoria(hp=1, maximo=maximo).alvo_atual() is None


# ===========================================================================
# O MOB DE VERDADE PASSA -- e isto é o que impede a regra de virar estorvo
# ===========================================================================

def test_o_mob_de_verdade_passa():
    alvo = _memoria(hp=47, maximo=100, nivel=29, nome="Elite Fatal Centipede")
    assert alvo is not None
    lido = alvo.alvo_atual()
    assert lido is not None
    assert lido["hp"] == 47 and lido["max_hp"] == 100
    assert lido["nome"] == "Elite Fatal Centipede"


def test_o_mob_MORTO_passa_e_continua_sendo_morte():
    """`hp == 0` com `max_hp == 100` é morte, e morte tem de ser reconhecida —
    era o caminho que funcionava e não pode ter sido quebrado."""
    lido = _memoria(hp=0, maximo=100, nivel=29, nome="Zaton").alvo_atual()
    assert lido is not None
    assert lido["hp"] == 0
    assert lido["pct"] == 0.0


def test_o_boss_passa():
    """`Gun Witch` nv50 lia 100 nas 7 leituras — boss não é exceção à regra."""
    lido = _memoria(hp=100, maximo=100, nivel=50, nome="Gun Witch").alvo_atual()
    assert lido is not None and lido["nivel"] == 50


def test_o_mob_sem_NOME_mas_com_vida_certa_passa():
    """`#id` tem DOIS significados, e misturá-los infla o problema por 4 vezes: 163
    leituras eram mob real com o nome não lido (inofensivo) contra 44 fantasmas.
    O nome NÃO é filtro — `core/entidades.py` diz isso de propósito, porque
    existe estado real de entidade legítima com o nome ilegível."""
    lido = _memoria(hp=88, maximo=100, nivel=27, nome=None).alvo_atual()
    assert lido is not None and lido["nome"] is None


# ===========================================================================
# O LOG QUE O USUÁRIO PEDIU
# ===========================================================================

def test_a_recusa_VAI_PARA_O_LOG_com_o_que_permite_julgar(caplog):
    """Pedido do usuário: *"é bom adicionar isso ao log e ver se isso é 100%
    verdade, principalmente em HH"*. A linha tem de trazer o suficiente para
    julgar se a regra errou."""
    with caplog.at_level(logging.WARNING, logger="blazes.memory"):
        _memoria(hp=1, maximo=1177280513, alvo_id=461589701,
                 nivel=1).alvo_atual()
    texto = caplog.text
    assert "ALVO RECUSADO" in texto
    assert "1177280513" in texto            # a vida máxima que reprovou
    assert "461589701" in texto             # o id, para procurar na memória
    assert "nível" in texto or "nivel" in texto


def test_o_log_sai_UMA_VEZ_por_combinacao(caplog):
    """O fantasma medido repetia a MESMA leitura a cada 2 s por até 37 s. Sem
    limite, o log vira ruído e a informação se perde no volume."""
    m = _memoria(hp=1, maximo=1177280513)
    with caplog.at_level(logging.WARNING, logger="blazes.memory"):
        for _ in range(20):
            m.alvo_atual()
    assert caplog.text.count("ALVO RECUSADO") == 1


def test_vida_maxima_DIFERENTE_loga_de_novo(caplog):
    """Combinação nova é informação nova: se aparecer um valor inédito, ele tem
    de aparecer no log mesmo que o id seja o mesmo."""
    m = _memoria(hp=1, maximo=1177280513)
    with caplog.at_level(logging.WARNING, logger="blazes.memory"):
        m.alvo_atual()
        novo = {
            mem.ADDR_TARGET_ID: 1108344853,
            0x30000000 + mem.OFF_ENTITY_ID: 1108344853,
            0x30000000 + mem.OFF_HP: 1,
            0x30000000 + mem.OFF_MAX_HP: 1065353216,
            0x30000000 + mem.OFF_LEVEL: 1,
        }
        m.read_int = novo.get
        m.read_uint = novo.get
        m.read_byte = novo.get
        m.alvo_atual()
    assert caplog.text.count("ALVO RECUSADO") == 2


# ===========================================================================
# O INTERRUPTOR DEVOLVE O COMPORTAMENTO ANTIGO
# ===========================================================================

def test_desligado_volta_a_aceitar_o_fantasma(monkeypatch):
    """Existe para o caso de aparecer alvo legítimo com outra vida máxima. E o
    teste deixa explícito o que se perde ao desligar: o fantasma volta."""
    monkeypatch.setattr(mem, "EXIGIR_VIDA_MAXIMA_DE_MOB", False)
    assert _memoria(hp=1, maximo=1177280513).alvo_atual() is not None
