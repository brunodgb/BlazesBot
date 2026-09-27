"""A retenção do log de dev: DOIS dias, e varrida de hora em hora.

DOIS DEFEITOS MEDIDOS EM 06/09/2026, e são independentes:

  1. **A varredura só acontecia no `__init__`** — uma vez por processo. O bot
     fica ligado por dias, então a retenção existia no papel e não acontecia:
     `logs/dev/arquivo/` estava com 324 MB, o arquivo do dia com **298 MB sem
     comprimir**, o de ontem nunca comprimido e cinco dias velhos que já
     deveriam ter sido apagados.

  2. **Sete dias de retenção contaminam a resposta.** Uma auditoria do ponteiro
     de nome do alvo varreu os sete dias (1.160.883 linhas) e concluiu "50,4%
     ilegível" — mas os consertos `d9bc023` e `1a5b19c` entraram em 01/09 às
     15:20 e 15:34. Metade da amostra descrevia um bot que não existe mais.
     Refeita na janela de dois dias, a mesma medição deu **46,8%**. O log de dev
     não é histórico: é a fotografia do bot DE AGORA.

Palavras do usuário (06/09/2026): *"os logs dev principalmente podem mudar
bastante a cada atualização que fizemos, e ter lixo ou informação que se tornou
irrelevante atrapalha em vez de ajuda."*
"""
import gzip
import logging
import time

from blazesbot.core import log_limitado
from blazesbot.core.log_limitado import ArquivoDeLogLimitado


def _handler(caminho, maximo=10, folga=5, arquivar=True):
    h = ArquivoDeLogLimitado(caminho, maximo=maximo, folga=folga,
                             arquivar=arquivar)
    h.setFormatter(logging.Formatter("%(message)s"))
    return h


def _record(texto: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="blazes.teste", level=logging.INFO,
        pathname=__file__, lineno=1, msg=texto, args=(), exc_info=None,
    )


def _dia(quantos_atras: int) -> str:
    return time.strftime("%Y-%m-%d",
                         time.localtime(time.time() - quantos_atras * 86400))


def _plantar(pasta, quantos_atras, sufixo=".jsonl", conteudo="linha\n"):
    """Um arquivo morto com a data no NOME, como o de produção."""
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / f"log-{_dia(quantos_atras)}{sufixo}"
    alvo.write_text(conteudo, encoding="utf-8")
    return alvo


# ---------------------------------------------------------------------------
# os números
# ---------------------------------------------------------------------------

def test_a_retencao_e_de_dois_dias():
    assert log_limitado.DIAS_DE_ARQUIVO_MORTO == 2


def test_a_varredura_e_de_hora_em_hora():
    assert log_limitado.INTERVALO_ENTRE_LIMPEZAS == 3600.0


# ---------------------------------------------------------------------------
# 1. a retenção em si -- pela DATA NO NOME, não pelo mtime
# ---------------------------------------------------------------------------

def test_apaga_o_que_passou_de_dois_dias_e_mantem_o_resto(tmp_path):
    pasta = tmp_path / "arquivo"
    hoje = _plantar(pasta, 0)
    ontem = _plantar(pasta, 1, sufixo=".jsonl.gz")
    anteontem = _plantar(pasta, 2, sufixo=".jsonl.gz")
    velho = _plantar(pasta, 5, sufixo=".jsonl.gz")

    h = _handler(tmp_path / "log.jsonl")
    try:
        h._limpar_arquivo_morto()
    finally:
        h.close()

    assert hoje.exists()
    assert ontem.exists()
    assert not anteontem.exists(), "anteontem passou dos 2 dias"
    assert not velho.exists()


def test_o_mtime_NAO_salva_um_arquivo_velho(tmp_path):
    """Quem diz de que dia é o conteúdo é o NOME.

    Um arquivo de cinco dias atrás que recebeu uma linha hoje tem mtime de hoje
    — pelo mtime ele sobreviveria à retenção para sempre.
    """
    pasta = tmp_path / "arquivo"
    velho = _plantar(pasta, 5, sufixo=".jsonl.gz")
    velho.touch()                       # mtime = agora

    h = _handler(tmp_path / "log.jsonl")
    try:
        h._limpar_arquivo_morto()
    finally:
        h.close()

    assert not velho.exists()


def test_nome_fora_do_padrao_NAO_e_tocado(tmp_path):
    pasta = tmp_path / "arquivo"
    pasta.mkdir(parents=True)
    intruso = pasta / "anotacoes-do-usuario.txt"
    intruso.write_text("nao apague", encoding="utf-8")

    h = _handler(tmp_path / "log.jsonl")
    try:
        h._limpar_arquivo_morto()
    finally:
        h.close()

    assert intruso.exists()


# ---------------------------------------------------------------------------
# 2. compressão: nunca no arquivo que ainda recebe linha
# ---------------------------------------------------------------------------

def test_comprime_o_de_ontem_e_apaga_o_original(tmp_path):
    pasta = tmp_path / "arquivo"
    ontem = _plantar(pasta, 1, conteudo="uma linha\n" * 200)
    # Silencioso há tempo bastante -- ver `_esta_quieto`.
    antigo = time.time() - 10 * 60
    import os
    os.utime(ontem, (antigo, antigo))

    h = _handler(tmp_path / "log.jsonl")
    try:
        h._limpar_arquivo_morto()
    finally:
        h.close()

    assert not ontem.exists()
    comprimido = ontem.with_suffix(ontem.suffix + ".gz")
    assert comprimido.exists()
    with gzip.open(comprimido, "rt", encoding="utf-8") as f:
        assert f.read().count("uma linha") == 200


def test_o_arquivo_de_HOJE_nunca_e_comprimido(tmp_path):
    """Ele ainda recebe anexação; comprimir perderia o que vier depois."""
    pasta = tmp_path / "arquivo"
    hoje = _plantar(pasta, 0, conteudo="linha\n" * 50)

    h = _handler(tmp_path / "log.jsonl")
    try:
        h._limpar_arquivo_morto()
    finally:
        h.close()

    assert hoje.exists()
    assert not hoje.with_suffix(hoje.suffix + ".gz").exists()


def test_arquivo_recem_escrito_NAO_e_comprimido(tmp_path):
    """A guarda da virada da meia-noite.

    O arquivo de "ontem" pode receber a última anexação de uma poda que começou
    antes das 00:00. `_comprimir` copia e apaga o original, então comprimir nesse
    vão perderia aquela anexação.
    """
    pasta = tmp_path / "arquivo"
    ontem = _plantar(pasta, 1, conteudo="linha\n")   # mtime = agora

    h = _handler(tmp_path / "log.jsonl")
    try:
        h._limpar_arquivo_morto()
    finally:
        h.close()

    assert ontem.exists(), "comprimiu um arquivo que ainda podia estar sendo escrito"
    assert not ontem.with_suffix(ontem.suffix + ".gz").exists()


# ---------------------------------------------------------------------------
# 3. periodicidade -- o defeito principal
# ---------------------------------------------------------------------------

def test_a_varredura_NAO_repete_dentro_do_intervalo(tmp_path, monkeypatch):
    h = _handler(tmp_path / "log.jsonl")
    chamadas = []
    monkeypatch.setattr(ArquivoDeLogLimitado, "_limpar_sem_atropelar",
                        lambda self: chamadas.append(1))
    try:
        for _ in range(50):
            h.emit(_record("x"))
    finally:
        h.close()

    assert chamadas == [], "varreu a pasta no meio do intervalo"


def test_passado_o_intervalo_a_varredura_acontece(tmp_path, monkeypatch):
    """Era isto que faltava: com o bot ligado por dias, a limpeza nunca vinha."""
    h = _handler(tmp_path / "log.jsonl")
    chamadas = []
    monkeypatch.setattr(ArquivoDeLogLimitado, "_limpar_sem_atropelar",
                        lambda self: chamadas.append(1))
    try:
        h._ultima_limpeza = time.time() - log_limitado.INTERVALO_ENTRE_LIMPEZAS - 1
        h.emit(_record("x"))
        # E uma segunda vez logo depois NÃO dispara de novo.
        h.emit(_record("x"))
    finally:
        h.close()

    assert chamadas == [1]


def test_a_varredura_sai_do_caminho_quente(tmp_path, monkeypatch):
    """Numa THREAD, e não é enfeite.

    `emit` roda com o lock do handler segurado. Comprimir o arquivo de ontem
    (centenas de MB) ali dentro pararia o log de TODAS as contas pelo tempo do
    gzip.
    """
    h = _handler(tmp_path / "log.jsonl")
    threads = []
    monkeypatch.setattr(log_limitado.threading, "Thread",
                        lambda **kw: threads.append(kw) or _Fake())
    try:
        h._ultima_limpeza = time.time() - log_limitado.INTERVALO_ENTRE_LIMPEZAS - 1
        h.emit(_record("x"))
    finally:
        h.close()

    assert len(threads) == 1
    assert threads[0]["daemon"] is True, "thread não-daemon seguraria o encerramento"


class _Fake:
    def start(self):
        pass


def test_sem_arquivar_nao_varre_nada(tmp_path, monkeypatch):
    """Os diários usam o mesmo handler SEM arquivo morto. Não têm o que varrer."""
    h = _handler(tmp_path / "log.txt", arquivar=False)
    chamadas = []
    monkeypatch.setattr(ArquivoDeLogLimitado, "_limpar_sem_atropelar",
                        lambda self: chamadas.append(1))
    try:
        h._ultima_limpeza = 0.0
        h.emit(_record("x"))
    finally:
        h.close()

    assert chamadas == []


def test_duas_varreduras_ao_mesmo_tempo_nao_se_atropelam(tmp_path):
    h = _handler(tmp_path / "log.jsonl")
    try:
        h._limpando.acquire()           # simula uma varredura já em curso
        # A segunda desiste na hora em vez de varrer a pasta em paralelo.
        h._limpar_sem_atropelar()
        h._limpando.release()
    finally:
        h.close()


def test_poda_que_NAO_CONSEGUE_reescrever_nao_rearquiva_o_mesmo_bloco(tmp_path, monkeypatch):
    """Arquivo quente preso por outro processo (editor, antivírus): a reescrita
    falha. Antes, o bloco descartado já tinha ido para o arquivo morto, o
    contador não zerava, e CADA linha nova relia o arquivo inteiro e arquivava o
    mesmo bloco de novo -- com a folga de 4000 do log de dev, 4000 linhas
    duplicadas por linha escrita (achado S14-12, 27/09/2026)."""
    h = _handler(tmp_path / "quente.jsonl", maximo=10, folga=5)

    def _preso(*_a, **_k):
        raise PermissionError("arquivo em uso por outro processo")

    monkeypatch.setattr(log_limitado.os, "replace", _preso)
    try:
        for i in range(30):
            h.emit(_record(f"linha {i}"))
    finally:
        h.close()
    arquivadas = sum(len(p.read_text(encoding="utf-8").splitlines())
                     for p in (tmp_path / "arquivo").glob("*"))
    assert arquivadas == 0, "arquivou o que não conseguiu tirar do quente"
    quente = (tmp_path / "quente.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(quente) == 30, "a reescrita falha não pode perder linha"


def test_a_poda_normal_arquiva_cada_linha_UMA_vez(tmp_path):
    h = _handler(tmp_path / "quente.jsonl", maximo=10, folga=5)
    try:
        for i in range(40):
            h.emit(_record(f"linha {i}"))
    finally:
        h.close()
    quente = (tmp_path / "quente.jsonl").read_text(encoding="utf-8").splitlines()
    morto = [linha for p in (tmp_path / "arquivo").glob("*")
             for linha in p.read_text(encoding="utf-8").splitlines()]
    assert sorted(quente + morto, key=lambda s: int(s.split()[1])) == \
        [f"linha {i}" for i in range(40)]
