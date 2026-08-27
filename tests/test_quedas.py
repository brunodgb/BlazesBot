"""Histórico de quedas (`core/quedas.py`) — lógica pura.

O que estes testes protegem, em ordem de importância:

  1. NADA DE DEV VAZA PARA A TELA. A frase do "onde parou" vem de um conjunto
     FECHADO de fases, e não da última linha de log. Se alguém trocar isso por
     um filtro sobre texto livre, o teste do vazamento reprova.
  2. A poda de 3 dias apaga a linha E as imagens juntas.
  3. O relatório de suporte leva o técnico; a tela não.
"""
import json
import time
from datetime import date

import pytest

from blazesbot.core import quedas

UM_DIA = 86400


@pytest.fixture(autouse=True)
def _pasta_temporaria(tmp_path, monkeypatch):
    """Cada teste com a sua pasta — nenhum toca em `logs/quedas/` de verdade."""
    monkeypatch.setattr(quedas, "PASTA", tmp_path / "quedas")
    monkeypatch.setattr(quedas, "ARQUIVO", tmp_path / "quedas" / "quedas.jsonl")


# ===========================================================================
# A GARANTIA: nada de dev na tela
# ===========================================================================


def test_toda_fase_da_rotina_tem_frase_amigavel():
    """Se alguém criar um estado novo na rotina e esquecer da frase, o usuário
    veria a fase crua. Este teste liga as duas listas."""
    from blazesbot.bot.bc.routine import State

    faltando = [s.name for s in State if s.name not in quedas.FASES]
    assert not faltando, f"sem frase amigável: {faltando}"


@pytest.mark.parametrize("fase", list(quedas.FASES))
def test_nenhuma_frase_carrega_jargao(fase):
    """As frases são lidas por quem não sabe o que é waypoint nem flag."""
    frase = quedas.FASES[fase].lower()
    for jargao in ("waypoint", "flag", "hwnd", "pid", "0x", "template",
                   "ponteiro", "offset", "struct", "tab", "memória"):
        assert jargao not in frase, f"{fase}: {jargao!r} em {frase!r}"


def test_fase_desconhecida_nao_vaza_o_nome_cru():
    """Fase que não está no mapa cai numa frase genérica — NUNCA no nome cru,
    que é o caminho pelo qual `ENTRAR_NO_COVIL` apareceria na tela."""
    assert quedas.frase_da_fase("FASE_QUE_NAO_EXISTE") == quedas.FASE_DESCONHECIDA
    assert "FASE_QUE_NAO_EXISTE" not in quedas.frase_da_fase("FASE_QUE_NAO_EXISTE")


def test_motivo_desconhecido_tambem_nao_vaza():
    assert quedas.frase_do_motivo("xpto") == quedas.MOTIVO_DESCONHECIDO
    assert quedas.frase_do_motivo(None) == quedas.MOTIVO_DESCONHECIDO


def test_o_registro_amigavel_nao_traz_as_linhas_de_log_no_texto():
    """As 20 linhas ficam no registro (para o arquivo e o relatório), mas
    nenhum dos campos `_texto` pode conter log."""
    reg = quedas.amigavel({
        "quando": time.time(), "motivo": "conexao", "fase": "BOSS",
        "log": ["01:02:03 [DEBUG] ALVO guardas fonte=memoria hp_memoria=0"],
    })
    textos = " ".join(v for k, v in reg.items()
                      if k.endswith("_texto") and isinstance(v, str))
    assert "hp_memoria" not in textos
    assert "DEBUG" not in textos


# ===========================================================================
# As frases
# ===========================================================================


def test_frase_do_tempo():
    assert quedas.frase_do_tempo(48) == "48 s"
    assert quedas.frase_do_tempo(37 * 60) == "37 min"
    assert quedas.frase_do_tempo(8073) == "2 h 14 min"
    assert quedas.frase_do_tempo(0) == ""
    assert quedas.frase_do_tempo(None) == ""


def test_frase_do_quando_usa_hoje_e_ontem():
    hoje = date(2026, 8, 13)
    agora = time.mktime((2026, 8, 13, 3, 47, 12, 0, 0, -1))
    assert quedas.frase_do_quando(agora, hoje).startswith("Hoje, 03:47")
    assert quedas.frase_do_quando(agora - UM_DIA, hoje).startswith("Ontem, 03:47")
    assert quedas.frase_do_quando(agora - 3 * UM_DIA, hoje).startswith("10/08,")


def test_onde_junta_lugar_e_coordenada():
    """O lugar em palavras para o usuário, a coordenada atrás para o dev."""
    reg = quedas.amigavel({"quando": 0, "local": "Secret Cemetery",
                           "posicao": [80, -406]})
    assert reg["onde_texto"] == "Secret Cemetery (80, -406)"


def test_onde_sem_um_dos_dois_nao_deixa_sobra():
    assert quedas.amigavel({"quando": 0, "local": "Stone City"})[
        "onde_texto"] == "Stone City"
    assert quedas.amigavel({"quando": 0, "posicao": [1, 2]})[
        "onde_texto"] == "(1, 2)"
    assert quedas.amigavel({"quando": 0})["onde_texto"] == ""


# ===========================================================================
# Gravar, podar, listar
# ===========================================================================


def _gravar(conta="creubo", quando=None, **extra):
    return quedas.registrar(conta=conta, motivo="conexao", fase="BOSS",
                            agora=quando or time.time(), **extra)


def test_gravar_e_listar():
    _gravar()
    lista = quedas.listar()
    assert len(lista) == 1
    assert lista[0]["motivo_texto"] == "O jogo perdeu a conexão com o servidor"
    assert lista[0]["fazendo_texto"] == "Estava lutando contra o chefe"


def test_lista_vem_da_mais_recente_para_a_mais_antiga():
    agora = time.time()
    _gravar(quando=agora - 100)
    _gravar(quando=agora)
    lista = quedas.listar()
    assert lista[0]["quando"] > lista[1]["quando"]


def test_filtro_por_conta():
    _gravar(conta="creubo")
    _gravar(conta="outra")
    assert len(quedas.listar()) == 2               # None = todas
    assert len(quedas.listar("creubo")) == 1
    assert quedas.contas_com_quedas() == ["creubo", "outra"]


def test_poda_de_tres_dias():
    agora = time.time()
    _gravar(quando=agora)
    _gravar(quando=agora - 2 * UM_DIA)
    _gravar(quando=agora - 4 * UM_DIA)          # fora
    assert quedas.podar(agora=agora) == 1
    assert len(quedas.listar()) == 2


def test_a_poda_apaga_o_print_e_a_miniatura_junto():
    """Histórico sem imagem seria meio registro; imagem sem histórico seria
    lixo que ninguém encontra."""
    agora = time.time()
    quedas.PASTA.mkdir(parents=True, exist_ok=True)
    velho = quedas.PASTA / "velho.jpg"
    mini = quedas.PASTA / quedas.nome_da_miniatura("velho.jpg")
    velho.write_bytes(b"x")
    mini.write_bytes(b"x")
    quedas.ARQUIVO.write_text(json.dumps({
        "quando": agora - 5 * UM_DIA, "conta": "c", "print": "velho.jpg",
    }) + "\n", encoding="utf-8")

    quedas.podar(agora=agora)
    assert not velho.exists()
    assert not mini.exists()


def test_linha_corrompida_nao_derruba_a_leitura():
    """Escrita concorrente pode truncar a última linha."""
    quedas.PASTA.mkdir(parents=True, exist_ok=True)
    quedas.ARQUIVO.write_text(
        json.dumps({"quando": time.time(), "conta": "c"}) + "\n{lixo",
        encoding="utf-8")
    assert len(quedas.listar()) == 1


def test_sem_arquivo_a_lista_e_vazia():
    assert quedas.listar() == []
    assert quedas.contas_com_quedas() == []


def test_quadro_none_grava_sem_print():
    """Os dois tipos de queda em que a janela já morreu. Não é erro."""
    reg = _gravar(quadro=None)
    assert reg["print"] is None
    assert quedas.listar()[0]["print_mini"] is None


def test_gravar_nunca_levanta(monkeypatch):
    """Falhar em gravar o histórico não pode atrapalhar o relogin."""
    monkeypatch.setattr(quedas, "PASTA", None)      # quebra tudo lá dentro
    assert _gravar()["conta"] == "creubo"           # devolveu, não explodiu


# ===========================================================================
# As últimas linhas de log
# ===========================================================================


def test_captura_guarda_as_ultimas_linhas_por_conta():
    import logging

    captura = quedas.CapturaDeLog(maximo=3)
    for i in range(5):
        captura.emit(logging.LogRecord(
            "blazes.creubo", logging.INFO, "f", 1, "linha %d", (i,), None))
    captura.emit(logging.LogRecord(
        "blazes.outra", logging.INFO, "f", 1, "de outra", (), None))

    linhas = captura.ultimas("creubo")
    assert len(linhas) == 3                    # o maxlen segurou
    assert "linha 4" in linhas[-1]
    assert captura.ultimas("outra") == [x for x in captura.ultimas("outra")]
    assert len(captura.ultimas("outra")) == 1


def test_instalar_captura_e_idempotente():
    import logging

    a = quedas.instalar_captura_de_log()
    b = quedas.instalar_captura_de_log()
    assert a is b
    assert sum(1 for h in logging.getLogger("blazes").handlers
               if isinstance(h, quedas.CapturaDeLog)) == 1


# ===========================================================================
# O relatório de suporte
# ===========================================================================


def test_relatorio_leva_o_tecnico_que_a_tela_esconde():
    """Este botão existe para chegar ao desenvolvedor: leva fase crua,
    coordenadas, PID e as linhas de log."""
    _gravar(posicao=(80, -406), local="Secret Cemetery", run=12, pid=4321,
            relogin=3, segundos_rodando=8073.0)
    texto = quedas.relatorio(quedas.listar())
    assert "fase=BOSS" in texto
    assert "pid=4321" in texto
    assert "(80, -406)" in texto
    assert "Estava lutando contra o chefe" in texto


def test_relatorio_vazio_nao_inventa():
    assert "Nenhuma queda" in quedas.relatorio([])
