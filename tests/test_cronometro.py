"""A telemetria de latência: mede, agrega, e não pode custar nem entupir.

TRÊS COISAS ESTE ARQUIVO TRAVA, e todas as três já foram problema aqui:

  1. **Não pode escrever por chamada.** Em 06/09/2026 UMA mensagem de log gerou
     531.411 linhas e 290 MB em 48 minutos — 93% do log de dev daquele dia. Um
     telemetro ingênuo faria pior: o laço de combate roda a cada 50 ms, em seis
     contas.
  2. **Desligado tem de custar ZERO**, e não "quase zero": `@cronometrar`
     devolve a função ORIGINAL, sem embrulho.
  3. **Não pode derrubar o bot.** Telemetria que estoura é pior que telemetria
     nenhuma.

O custo de medir está medido no topo de `core/cronometro.py`: +298 ns por
chamada, o que dá 3,0% num alvo de 10 µs e 30% num de 1 µs. Daí o piso.
"""
import json
import threading

import pytest

from blazesbot.core import cronometro as cr


@pytest.fixture(autouse=True)
def limpo(tmp_path, monkeypatch):
    """Cada teste com o seu arquivo e os seus baldes."""
    cr.zerar_para_teste()
    monkeypatch.setattr(cr, "PASTA", tmp_path)
    monkeypatch.setattr(cr, "ARQUIVO", tmp_path / "latencia.jsonl")
    yield
    cr.zerar_para_teste()


def _linhas(tmp_path):
    arq = tmp_path / "latencia.jsonl"
    if not arq.exists():
        return []
    return [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# 1. o anti-spam -- a razão de o módulo existir assim
# ---------------------------------------------------------------------------

def test_cem_mil_medicoes_viram_UMA_linha(tmp_path):
    for _ in range(100_000):
        cr.anotar("laco.combate", 0.0005)

    assert cr.despejar() == 1
    (linha,) = _linhas(tmp_path)
    assert linha["n"] == 100_000
    assert linha["nome"] == "laco.combate"


def test_a_linha_diz_mais_que_as_cem_mil(tmp_path):
    """n, mínimo, média e máximo — uma linha solta não mostra distribuição."""
    for gasto in (0.001, 0.002, 0.003, 0.010):
        cr.anotar("memoria.alvo_atual", gasto)

    cr.despejar()
    (linha,) = _linhas(tmp_path)
    assert linha["n"] == 4
    assert linha["min_ms"] == 1.0
    assert linha["max_ms"] == 10.0
    assert linha["med_ms"] == pytest.approx(4.0)
    assert linha["total_ms"] == pytest.approx(16.0)


def test_despejar_ZERA_para_a_janela_seguinte(tmp_path):
    cr.anotar("x", 0.001)
    cr.despejar()
    assert cr.despejar() == 0, "despejou de novo o que já tinha saído"

    cr.anotar("x", 0.002)
    cr.despejar()
    linhas = _linhas(tmp_path)
    assert [l["n"] for l in linhas] == [1, 1]


def test_nada_e_escrito_fora_do_despejo(tmp_path):
    """Medir NÃO toca no disco. Só o despejo escreve."""
    for _ in range(5_000):
        cr.anotar("y", 0.001)

    assert _linhas(tmp_path) == []


# ---------------------------------------------------------------------------
# 2. o custo -- desligado é ZERO, ligado é o wrapper
# ---------------------------------------------------------------------------

def test_desligado_devolve_a_funcao_ORIGINAL(monkeypatch):
    """Não é um `if` dentro do wrapper: esse `if` custaria a chamada extra."""
    monkeypatch.setattr(cr, "TELEMETRIA_LIGADA", False)

    def f():
        return 42

    assert cr.cronometrar("nada")(f) is f


def test_ligado_preserva_nome_doc_e_retorno():
    def f(a, b=2):
        """documentação."""
        return a + b

    medido = cr.cronometrar("p")(f)
    assert medido(1, b=3) == 4
    assert medido.__name__ == "f"
    assert medido.__doc__ == "documentação."
    assert medido.__wrapped__ is f


def test_o_piso_esta_documentado_e_e_de_10us():
    """A 1 µs o decorador custa 30% — `read_int` NÃO se instrumenta."""
    assert cr.PISO_PARA_CRONOMETRAR == 10e-6


# ---------------------------------------------------------------------------
# 3. não pode derrubar o bot
# ---------------------------------------------------------------------------

def test_excecao_no_bloco_e_MEDIDA_e_sobe(tmp_path):
    """Um trecho que estoura é justamente o que interessa cronometrar."""
    with pytest.raises(ValueError):
        with cr.cronometro("estourou"):
            raise ValueError("de propósito")

    cr.despejar()
    assert [l["nome"] for l in _linhas(tmp_path)] == ["estourou"]


def test_excecao_na_funcao_e_MEDIDA_e_sobe(tmp_path):
    @cr.cronometrar("f.estourou")
    def f():
        raise RuntimeError("de propósito")

    with pytest.raises(RuntimeError):
        f()

    cr.despejar()
    assert [l["nome"] for l in _linhas(tmp_path)] == ["f.estourou"]


# ---------------------------------------------------------------------------
# 4. uma thread por conta -- sem trava no caminho quente
# ---------------------------------------------------------------------------

def test_cada_conta_sai_na_sua_linha(tmp_path):
    def trabalhar(nome, gasto):
        cr.marcar_a_conta(nome)
        for _ in range(100):
            cr.anotar("memoria.snapshot", gasto)

    ts = [threading.Thread(target=trabalhar, args=(f"conta{i}", 0.001 * (i + 1)))
          for i in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    assert cr.despejar() == 3
    por_conta = {l["conta"]: l for l in _linhas(tmp_path)}
    assert set(por_conta) == {"conta0", "conta1", "conta2"}
    assert por_conta["conta0"]["med_ms"] == pytest.approx(1.0)
    assert por_conta["conta2"]["med_ms"] == pytest.approx(3.0)
    assert all(l["n"] == 100 for l in por_conta.values())


def test_o_acumulador_e_por_thread_e_nao_global():
    """`ac.n += 1` não é atômico; um `Lock` no caminho quente pagaria mais que
    a própria medição. Por thread resolve os dois."""
    baldes = []

    def pegar():
        cr.anotar("z", 0.001)
        baldes.append(cr._meu_balde())

    ts = [threading.Thread(target=pegar) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    assert len({id(b) for b in baldes}) == 4


# ---------------------------------------------------------------------------
# 5. a instrumentação de verdade está nos lugares certos -- e NÃO no read_int
# ---------------------------------------------------------------------------

def test_o_read_int_NAO_e_instrumentado():
    """~1 µs documentado. Instrumentá-lo custaria 30% da operação mais repetida
    do bot, para medir o que já se sabe."""
    from blazesbot.core.memory import Memory

    assert not hasattr(Memory.read_int, "__wrapped__")


@pytest.mark.parametrize("modulo,classe,metodo", [
    ("blazesbot.core.memory", "Memory", "alvo_atual"),
    ("blazesbot.core.inputs", "Input", "_click"),
    ("blazesbot.bot.context", "BotContext", "snapshot"),
])
def test_os_pontos_quentes_estao_instrumentados(modulo, classe, metodo):
    import importlib

    alvo = getattr(getattr(importlib.import_module(modulo), classe), metodo)
    assert hasattr(alvo, "__wrapped__"), f"{classe}.{metodo} perdeu o cronômetro"


def test_o_laco_do_BC_mede_por_ESTADO():
    import inspect

    from blazesbot.bot.bc import routine

    fonte = inspect.getsource(routine.BossRushRoutine.run)
    assert 'cronometro(f"bc.estado.{previous.name}")' in fonte


def test_o_supervisor_liga_a_telemetria_e_carimba_a_conta():
    import inspect

    from blazesbot.bot.supervisor import AccountSupervisor

    fonte = inspect.getsource(AccountSupervisor.run)
    assert "cronometro_mod.ligar()" in fonte
    assert "marcar_a_conta" in fonte


# ---------------------------------------------------------------------------
# 6. invisível para o usuário
# ---------------------------------------------------------------------------

def test_o_log_de_latencia_NAO_propaga_para_o_log_de_dev(tmp_path):
    """"100% invisível" é requisito: a latência não pode empurrar a evidência
    de defeito para fora da janela curta do log de dev (4.000 linhas)."""
    cr.anotar("x", 0.001)
    cr.despejar()

    import logging
    assert logging.getLogger("blazes.latencia").propagate is False


def test_o_arquivo_de_latencia_e_separado_do_log_de_dev():
    assert "latencia" in str(cr.ARQUIVO)
    assert "blazes-dev" not in str(cr.ARQUIVO)
