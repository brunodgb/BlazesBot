"""Cronometrar o pacote INTEIRO sem o pacote inteiro pagar por isso.

PEDIDO DO USUÁRIO, 07/09/2026: *"em todos os módulos, funções e laços, para que
mesmo o que já esteja testado e documentado seja retestado para garantir que
está tudo realmente como deveria, ou se dá para melhorar de alguma forma, seja
diminuindo ou aumentando os tempos"*.

São **1.631 funções** no pacote, e medir custa +298 ns por chamada — 30% numa
função de 1 µs. Embrulhar as 1.631 de forma permanente deixaria o bot mais
lento justamente para descobrir que ele está lento.

A SAÍDA É O EMBRULHO QUE SE APOSENTA: mede as primeiras
`AMOSTRAS_PARA_DECIDIR` chamadas e, se a média ficou abaixo do piso, devolve a
função original no lugar dela. **O censo fica** — a função aposentada continua
no relatório com o seu n, mínimo, média e máximo. Mede-se tudo; paga-se só pelo
que vale.

E NADA DISSO ACONTECE NO IMPORT: **56 arquivos de teste deste projeto leem
`inspect.getsource`** de métodos reais. Um wrapper no lugar do método quebraria
os 56 de uma vez.
"""
import json

import pytest

from blazesbot.core import cronometro as cr
from blazesbot.core import instrumentacao as ins
from blazesbot.core import relatorio_de_latencia as rel


@pytest.fixture(autouse=True)
def limpo(tmp_path, monkeypatch):
    cr.zerar_para_teste()
    monkeypatch.setattr(cr, "PASTA", tmp_path)
    monkeypatch.setattr(cr, "ARQUIVO", tmp_path / "latencia.jsonl")
    monkeypatch.setattr(rel, "PASTA", tmp_path)
    monkeypatch.setattr(rel, "ARQUIVO", tmp_path / "latencia.jsonl")
    yield
    ins.desinstrumentar_tudo()
    cr.zerar_para_teste()


def _cobaia():
    """UMA CLASSE NOVA POR TESTE, e não uma compartilhada.

    O embrulho vive NA CLASSE (`setattr(cls, nome, ...)`), então uma cobaia de
    módulo atravessaria os testes já embrulhada e o teste seguinte embrulharia
    o embrulho — dois cronômetros contando a mesma chamada. Foi exatamente o
    que aconteceu na primeira versão deste arquivo: `n` deu 15 em vez de 20.
    """
    class _Cobaia:
        def rapida(self):
            return 1

        def __repr__(self):
            return "<cobaia>"

        def gera(self):
            yield 1
    return _Cobaia


def _embrulhar(dono, nome, rotulo="teste.alvo"):
    f = vars(dono)[nome]
    setattr(dono, nome, ins._embrulhar(dono, nome, f, rotulo))
    return f


# ---------------------------------------------------------------------------
# 1. a aposentadoria -- o coração do desenho
# ---------------------------------------------------------------------------

def test_funcao_rapida_se_aposenta_e_devolve_a_original():
    Cobaia = _cobaia()
    original = _embrulhar(Cobaia, "rapida")
    assert hasattr(Cobaia.rapida, "__wrapped__")

    c = Cobaia()
    for _ in range(ins.AMOSTRAS_PARA_DECIDIR):
        c.rapida()

    assert Cobaia.rapida is original, "o embrulho não se aposentou"


def test_funcao_CARA_continua_embrulhada(monkeypatch):
    """Acima do piso, o cronômetro é ruído — vale continuar medindo."""
    monkeypatch.setattr(cr, "PISO_PARA_CRONOMETRAR", 0.0)  # tudo é "caro"
    Cobaia = _cobaia()
    original = _embrulhar(Cobaia, "rapida")

    c = Cobaia()
    for _ in range(ins.AMOSTRAS_PARA_DECIDIR + 5):
        c.rapida()

    assert Cobaia.rapida is not original
    assert hasattr(Cobaia.rapida, "__wrapped__")


def test_o_CENSO_da_aposentada_NAO_se_perde(tmp_path):
    """É o ponto do pedido: descobrir o custo de TUDO, inclusive do que é
    barato demais para continuar sendo medido."""
    Cobaia = _cobaia()
    _embrulhar(Cobaia, "rapida", "teste.rapida")
    c = Cobaia()
    for _ in range(ins.AMOSTRAS_PARA_DECIDIR):
        c.rapida()

    cr.despejar()
    linhas = [json.loads(l) for l
              in (tmp_path / "latencia.jsonl").read_text(encoding="utf-8").splitlines()]
    censo = {l["nome"]: l for l in linhas}
    assert censo["teste.rapida"]["n"] == ins.AMOSTRAS_PARA_DECIDIR


def test_aposentada_para_de_cobrar():
    """Depois da aposentadoria não sai mais medição nenhuma daquele nome."""
    Cobaia = _cobaia()
    _embrulhar(Cobaia, "rapida", "teste.parou")
    c = Cobaia()
    for _ in range(ins.AMOSTRAS_PARA_DECIDIR):
        c.rapida()
    cr.despejar()                       # limpa o acumulado

    for _ in range(500):
        c.rapida()

    assert cr.despejar() == 0, "continuou medindo depois de aposentar"


# ---------------------------------------------------------------------------
# 2. o que NÃO entra
# ---------------------------------------------------------------------------

def test_dunder_fica_de_fora():
    """`__repr__` é chamado de dentro do interpretador, em log e em erro."""
    assert not ins._pode_embrulhar(vars(_cobaia())["__repr__"])


def test_gerador_fica_de_fora():
    """O embrulho mediria a CRIAÇÃO do gerador, não a execução dele — número
    certo para a pergunta errada."""
    assert not ins._pode_embrulhar(vars(_cobaia())["gera"])


def test_quem_ja_tem_cronometro_a_mao_nao_e_embrulhado_de_novo():
    from blazesbot.core.memory import Memory

    assert not ins._pode_embrulhar(vars(Memory)["alvo_atual"])


def test_o_proprio_cronometro_fica_de_fora():
    """Embrulhar o medidor com o medidor é recursão."""
    assert "blazesbot.core.cronometro" in ins.FORA
    assert "blazesbot.core.instrumentacao" in ins.FORA


# ---------------------------------------------------------------------------
# 3. não roda sozinho -- os 56 testes de `getsource` dependem disso
# ---------------------------------------------------------------------------

def test_importar_o_modulo_NAO_instrumenta_nada():
    from blazesbot.bot.bc.routine import BossRushRoutine

    assert not hasattr(BossRushRoutine._do_guardas, "__wrapped__"), (
        "instrumentou no import: os 56 testes que leem `inspect.getsource` de "
        "métodos reais passariam a ler o código do wrapper")


def test_o_interruptor_desliga_tudo(monkeypatch):
    monkeypatch.setattr(ins, "INSTRUMENTAR_O_PACOTE_INTEIRO", False)
    assert ins.instrumentar_tudo() == 0


def test_o_supervisor_e_quem_chama():
    import inspect

    from blazesbot.bot.supervisor import AccountSupervisor

    assert "instrumentacao.instrumentar_tudo()" in inspect.getsource(
        AccountSupervisor.run)


# ---------------------------------------------------------------------------
# 4. de ponta a ponta, no pacote de verdade
# ---------------------------------------------------------------------------

def test_instrumenta_o_pacote_e_desfaz():
    quantos = ins.instrumentar_tudo()
    assert quantos > 500, f"instrumentou só {quantos} funções"

    from blazesbot.core import zones
    assert hasattr(zones.distancia_linear, "__wrapped__")

    ins.desinstrumentar_tudo()
    from blazesbot.core import zones as z2
    assert not hasattr(z2.distancia_linear, "__wrapped__")


def test_instrumentar_duas_vezes_nao_empilha():
    ins.instrumentar_tudo()
    from blazesbot.core import zones
    uma = zones.distancia_linear

    ins.instrumentar_tudo()
    assert zones.distancia_linear is uma, "empilhou um segundo embrulho"


def test_o_relatorio_ordena_por_TOTAL_e_nao_por_media(tmp_path):
    """Uma função de 400 ms chamada 3x custa 1,2 s; uma de 0,4 ms chamada
    20.000x custa 8 s. A média premia a primeira, e é a segunda que decide a
    duração da run."""
    cr.anotar("rara.e.lenta", 0.4)
    cr.anotar("rara.e.lenta", 0.4)
    cr.anotar("rara.e.lenta", 0.4)
    for _ in range(20_000):
        cr.anotar("comum.e.rapida", 0.0004)
    cr.despejar()

    texto = rel.relatorio(2)
    onde_vai = texto.split("ONDE O TEMPO VAI")[1].split("OS PICOS")[0]
    assert onde_vai.index("comum.e.rapida") < onde_vai.index("rara.e.lenta")


def test_o_relatorio_sem_dado_explica_em_vez_de_estourar():
    assert "Nenhuma medição" in rel.relatorio()
