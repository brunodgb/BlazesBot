"""Telemetria de latência: mede sem poluir o código e sem entupir o disco.

=========================================================================
POR QUE ISTO NÃO É `time.time()` ESPALHADO
=========================================================================

O projeto já mede tempo em vários lugares — o cronômetro por estado da rotina,
o `docs/TEMPOS.md` gerado, a `calibracao`, o `diagnostico_fino`. O que faltava
era o **caminho quente**: quanto custa uma leitura de memória, quanto custa
mandar uma tecla, quanto custa uma volta do laço. Medir isso com `time.time()`
solto exigiria duas linhas em cada ponto e uma terceira para logar — e o log
sairia por chamada, que é exatamente o que não pode acontecer aqui.

=========================================================================
O QUE MEDIR, E O QUE NÃO — O PISO DE 10 µs, MEDIDO
=========================================================================

Medir custa, e o número é DESTA implementação -- não de um esboço. Medido em
07/09/2026, 200.000 repetições, melhor de 3 rodadas:

    chamada crua ..............  21 ns
    com @cronometrar .......... 319 ns   (+298 ns)
    com `with cronometro()` ... 332 ns   (+310 ns)

Contra o que se mede, isso vira:

    | alvo do bloco | @cronometrar | with cronometro |
    |---------------|--------------|-----------------|
    |     1 µs      |    29,8 %    |     31,0 %      |
    |    10 µs      |     3,0 %    |      3,1 %      |
    |    25 µs      |     1,2 %    |      1,2 %      |
    |    50 µs      |     0,6 %    |      0,6 %      |
    |   100 µs      |     0,3 %    |      0,3 %      |

**DAÍ A REGRA: não se cronometra nada abaixo de `PISO_PARA_CRONOMETRAR`.**
`Memory.read_int` é documentado em ~1 µs — instrumentá-lo custaria **30%** de
uma das operações mais repetidas do bot, para medir o que já se sabe. Quem quer
o custo da leitura mede a leitura COMPOSTA (`alvo_atual`, `snapshot`), que é
dezenas de microssegundos e é o número que interessa de verdade.

O primeiro esboço custava 434 ns. O que tirou 136 ns foi pôr o acumulador
INLINE em `anotar` (a chamada de método respondia por ~40%) e trocar o
`getattr` com padrão por `try/except`. Ver o corpo de `anotar`.

=========================================================================
O ANTI-SPAM É AGREGAÇÃO, E NÃO É OPCIONAL
=========================================================================

Em 06/09/2026 UMA mensagem de log gerou **531.411 linhas e 290 MB em 48
minutos** — 93% do log de dev daquele dia (ver `docs/decisoes/sistema.md`). Um
telemetro que escrevesse por chamada faria pior: o laço de combate roda a cada
50 ms, em seis contas.

Então aqui NÃO EXISTE escrita por chamada. Cada medição soma num acumulador em
memória (n, mínimo, máximo, soma) e uma thread solta despeja UMA linha por nome
a cada `INTERVALO_DE_DESPEJO`. Mil chamadas viram uma linha, e a linha diz mais
que as mil: n, mínimo, média e máximo.

=========================================================================
O ACUMULADOR É POR THREAD -- e isso não é enfeite
=========================================================================

O bot roda uma thread por conta. `acumulado.n += 1` não é atômico entre
threads, e um `Lock` no caminho quente pagaria mais que a própria medição.
Acumulador por thread resolve os dois: zero trava onde importa, e de quebra o
despejo sai separado por conta, que é como se lê o resultado.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from .log_limitado import ArquivoDeLogLimitado

# ===========================================================================
# O INTERRUPTOR
# ===========================================================================
#
# `False` devolve o bot ao estado anterior com CUSTO ZERO, e não "custo quase
# zero": desligado, `@cronometrar` devolve a função ORIGINAL, sem embrulho
# nenhum. Não é um `if` dentro do wrapper -- esse `if` custaria a chamada extra
# que a medição acima cobra.
TELEMETRIA_LIGADA = True

# Abaixo disto, NÃO se cronometra. Ver o bloco "O PISO DE 10 µs" acima: a 1 µs o
# decorador custa 16%; a 10 µs, 1,6%.
PISO_PARA_CRONOMETRAR = 10e-6

# De quanto em quanto tempo a thread despeja o que foi acumulado.
#
# Trinta segundos: uma volta de macro do APP dura segundos e uma run de BC dura
# minutos, então meio minuto agrega o bastante para a linha ser estatística e é
# curto o bastante para um pico aparecer perto de onde aconteceu. Com seis
# contas e ~20 nomes instrumentados, são ~4 linhas por segundo no pior caso --
# contra as 658/s do incidente de 06/09.
INTERVALO_DE_DESPEJO = 30.0

# Onde a latência mora. SEPARADO do log de dev de propósito: são perguntas
# diferentes ("o que o bot fez" contra "quanto cada coisa custou"), e misturá-las
# faria a telemetria empurrar a evidência de defeito para fora da janela do log
# de dev, que é curta (4.000 linhas).
PASTA = Path("logs/latencia")
ARQUIVO = PASTA / "latencia.jsonl"

# Quantas linhas o arquivo quente guarda. O `ArquivoDeLogLimitado` cuida do
# resto -- arquivo morto por dia, compressão e a retenção de 2 dias, tudo
# reusado de `core/log_limitado.py` em vez de reescrito aqui.
LINHAS_NO_ARQUIVO_QUENTE = 3000


def _caminho_dos_handlers(log: logging.Logger) -> str | None:
    for h in log.handlers:
        alvo = getattr(h, "caminho", None) or getattr(h, "baseFilename", None)
        if alvo:
            return str(alvo)
    return None


class _Acumulado:
    """Os quatro números de um nome, numa thread. `__slots__` é caminho quente."""

    __slots__ = ("maximo", "minimo", "n", "soma")

    def __init__(self) -> None:
        self.n = 0
        self.soma = 0.0
        self.minimo = 0.0
        self.maximo = 0.0



class _Balde:
    """Os acumuladores de UMA thread, mais quem ela é.

    DUAS PERGUNTAS NO MESMO BALDE, e não é economia de arquivo: "quanto custou"
    e "como terminou" são lidas JUNTAS -- uma espera de 280 ms só quer dizer
    alguma coisa quando se sabe se ela terminou confirmada ou no teto. Dividir
    em dois módulos duplicaria o registro por thread, a thread de despejo e o
    arquivo, para depois exigir um `join` na hora de ler.
    """

    __slots__ = ("conta", "desfechos", "nomes", "thread")

    def __init__(self) -> None:
        self.nomes: dict[str, _Acumulado] = {}
        self.desfechos: dict[str, dict[str, int]] = {}
        self.conta = ""
        self.thread = threading.current_thread().name


_local = threading.local()
# Todos os baldes já criados. A thread do despejo caminha por aqui; o caminho
# quente nunca toca nesta lista depois do primeiro registro.
_baldes: list[_Balde] = []
_trava_do_registro = threading.Lock()


def _meu_balde() -> _Balde:
    balde = getattr(_local, "balde", None)
    if balde is None:
        balde = _Balde()
        _local.balde = balde
        with _trava_do_registro:
            _baldes.append(balde)
    return balde


def anotar(nome: str, gasto: float) -> None:
    """Soma uma medição ao acumulador desta thread. NÃO escreve nada.

    TUDO INLINE, e isso é medição e não gosto: com `_Acumulado.somar` como
    método, a chamada extra respondia por ~40% do custo de medir. Aqui não há
    função auxiliar nenhuma no caminho quente -- é a única parte deste arquivo
    onde legibilidade perde para custo, e perde por número.

    O `try/except` em vez de `getattr(_local, "balde", None)` pelo mesmo
    motivo: o caminho comum não paga nada, e o `AttributeError` acontece uma vez
    por thread na vida do processo.
    """
    try:
        nomes = _local.balde.nomes
    except AttributeError:
        nomes = _meu_balde().nomes
    ac = nomes.get(nome)
    if ac is None:
        ac = _Acumulado()
        nomes[nome] = ac
        ac.minimo = gasto
    elif gasto < ac.minimo:
        ac.minimo = gasto
    if gasto > ac.maximo:
        ac.maximo = gasto
    ac.n += 1
    ac.soma += gasto


def marcar(nome: str, desfecho: str) -> None:
    """Conta COMO uma ação terminou. NÃO escreve nada, e não olha o relógio.

    =====================================================================
    MAIS BARATO QUE MEDIR TEMPO, E RESPONDE O QUE O TEMPO NÃO RESPONDE
    =====================================================================

    `anotar` paga dois `perf_counter` (298 ns medidos). Aqui não há relógio
    nenhum: dois lookups de dicionário e um `+= 1`, na casa de 80 ns.

    E é a pergunta que faltava. Na auditoria de 10/09/2026 foi preciso CONTAR
    STRINGS EM PROSA no log de dev para saber quantas tentativas de entrada
    falharam (`"NÃO confirmado"` -> 61.928). Isso quebra na primeira vez que
    alguém reescrever a mensagem, e não sobrevive a `log.debug`.

    O NOME É DA AÇÃO, o desfecho é COMO ela terminou -- os dois curtos, porque
    viram chave de dicionário no caminho quente:

        marcar("espera.entrada_na_hh", "confirmado")
        marcar("espera.entrada_na_hh", "teto")
    """
    try:
        desfechos = _local.balde.desfechos
    except AttributeError:
        desfechos = _meu_balde().desfechos
    por_desfecho = desfechos.get(nome)
    if por_desfecho is None:
        desfechos[nome] = {desfecho: 1}
        return
    por_desfecho[desfecho] = por_desfecho.get(desfecho, 0) + 1


class cronometro:   # minúsculo de propósito: é usado como `with cronometro(...)`
    """Mede um BLOCO. Use para trecho sem função própria.

        with cronometro("bc.travessia.waypoint"):
            ...

    Só para blocos acima de `PISO_PARA_CRONOMETRAR` -- ver o topo do arquivo.
    """

    __slots__ = ("_inicio", "nome")

    def __init__(self, nome: str) -> None:
        self.nome = nome
        self._inicio = 0.0

    def __enter__(self) -> cronometro:
        self._inicio = time.perf_counter()
        return self

    def __exit__(self, *_) -> None:
        # `finally` implícito: exceção no bloco também é medida. Um trecho que
        # estoura é justamente o que interessa cronometrar.
        anotar(self.nome, time.perf_counter() - self._inicio)


def cronometrar(nome: str):
    """Mede uma FUNÇÃO.

        @cronometrar("memoria.alvo_atual")
        def alvo_atual(self): ...

    DESLIGADO, devolve a função original -- zero embrulho, zero custo. É por
    isso que o interruptor mora aqui e não dentro do wrapper.
    """
    if not TELEMETRIA_LIGADA:
        return lambda f: f

    def envolver(f):
        def medido(*a, **k):
            inicio = time.perf_counter()
            try:
                return f(*a, **k)
            finally:
                anotar(nome, time.perf_counter() - inicio)
        # Sem `functools.wraps`: ele copia seis atributos por decoração e este
        # projeto tem testes que leem `inspect.getsource` do ORIGINAL. Copiar o
        # nome e o doc à mão cobre o que a introspecção do projeto usa.
        medido.__name__ = getattr(f, "__name__", nome)
        medido.__doc__ = f.__doc__
        medido.__wrapped__ = f
        return medido
    return envolver


# ===========================================================================
# O DESPEJO -- uma linha por nome por janela, numa thread solta
# ===========================================================================

_logger: logging.Logger | None = None
_thread_do_despejo: threading.Thread | None = None
_parar = threading.Event()


def _preparar_o_logger() -> logging.Logger:
    """O logger da latência, criado uma vez e CONFERIDO depois.

    A conferência do caminho não é zelo de teste: `logging.getLogger` devolve
    sempre o MESMO objeto, para o processo inteiro. Guardar só um `_logger` e
    confiar nele deixava o handler antigo escrevendo no arquivo antigo quando
    `ARQUIVO` mudava -- e aí a telemetria some, sem erro nenhum, no arquivo que
    ninguém está lendo.
    """
    global _logger
    log = logging.getLogger("blazes.latencia")
    if _logger is not None and _caminho_dos_handlers(log) == str(ARQUIVO):
        return _logger
    for h in list(log.handlers):
        log.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    PASTA.mkdir(parents=True, exist_ok=True)
    log.setLevel(logging.INFO)
    # NÃO propaga: a latência não pode aparecer no log de dev nem no console.
    # "100% invisível para o usuário final" é requisito, não preferência.
    log.propagate = False
    if not log.handlers:
        # REUSA `ArquivoDeLogLimitado`: teto de linhas, arquivo morto por dia,
        # compressão e a retenção de 2 dias já vivem lá. Reescrever isso aqui
        # seria a duplicata que o CLAUDE.md proíbe.
        # FOLGA = O PRÓPRIO MÁXIMO, pelo mesmo motivo do log de dev
        # (`log_json.FOLGA_DO_LOG_JSON`): com folga de 100 cada despejo de ~555
        # linhas disparava ~5 podas do arquivo inteiro (2.885 em 4,3 h, medido
        # em 26/09/2026).
        handler = ArquivoDeLogLimitado(
            ARQUIVO, encoding="utf-8",
            maximo=LINHAS_NO_ARQUIVO_QUENTE, folga=LINHAS_NO_ARQUIVO_QUENTE,
            arquivar=True)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
    _logger = log
    return log


def despejar() -> int:
    """Escreve o acumulado e zera. Devolve quantas linhas saíram.

    Zera o acumulador ANTES de formatar a linha, e não depois: a thread da conta
    continua medindo enquanto esta escreve, e trocar o objeto é o que impede
    perder as medições desse intervalo.
    """
    import json

    linhas = 0
    log = _preparar_o_logger()
    agora = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with _trava_do_registro:
        baldes = list(_baldes)
    for balde in baldes:
        # Troca o dicionário inteiro por um novo: a thread dona volta a
        # acumular do zero no dela sem que esta precise travar nada.
        colhido, balde.nomes = balde.nomes, {}
        for nome, ac in colhido.items():
            if not ac.n:
                continue
            log.info(json.dumps({
                "ts": agora,
                "nome": nome,
                "conta": balde.conta or None,
                "thread": balde.thread,
                "n": ac.n,
                "min_ms": round(ac.minimo * 1000, 3),
                "med_ms": round(ac.soma / ac.n * 1000, 3),
                "max_ms": round(ac.maximo * 1000, 3),
                "total_ms": round(ac.soma * 1000, 1),
            }, ensure_ascii=False))
            linhas += 1

        # OS DESFECHOS SAEM NA MESMA LINHA-A-LINHA, com `tipo` para o leitor
        # separar sem adivinhar. Uma linha por NOME, com todos os desfechos
        # dele: é o formato que responde "de 62.149 tentativas, quantas
        # confirmaram" sem juntar nada depois.
        colhidos, balde.desfechos = balde.desfechos, {}
        for nome, por_desfecho in colhidos.items():
            log.info(json.dumps({
                "ts": agora,
                "tipo": "desfecho",
                "nome": nome,
                "conta": balde.conta or None,
                "thread": balde.thread,
                "n": sum(por_desfecho.values()),
                "desfechos": por_desfecho,
            }, ensure_ascii=False))
            linhas += 1
    return linhas


def marcar_a_conta(conta: str) -> None:
    """Diz de quem é esta thread. Chamado uma vez, quando o supervisor nasce."""
    _meu_balde().conta = conta


def _laco_do_despejo() -> None:
    while not _parar.wait(INTERVALO_DE_DESPEJO):
        try:
            despejar()
        except Exception:
            # Telemetria que derruba o bot é pior que telemetria nenhuma.
            pass


def ligar() -> None:
    """Sobe a thread do despejo. Idempotente; nada acontece com o interruptor
    desligado."""
    global _thread_do_despejo
    if not TELEMETRIA_LIGADA or _thread_do_despejo is not None:
        return
    _parar.clear()
    _thread_do_despejo = threading.Thread(
        target=_laco_do_despejo, name="telemetria", daemon=True)
    _thread_do_despejo.start()


def desligar() -> None:
    """Para a thread e despeja o que sobrou. Para o encerramento e os testes."""
    global _thread_do_despejo
    _parar.set()
    t, _thread_do_despejo = _thread_do_despejo, None
    if t is not None:
        t.join(timeout=2.0)
    try:
        despejar()
    except Exception:
        pass


def zerar_para_teste() -> None:
    """Esquece tudo. SÓ para teste -- produção nunca precisa disto.

    SOLTA OS HANDLERS, e não só a variável: `logging.getLogger` devolve SEMPRE
    o mesmo objeto, então zerar `_logger` sem fechar o handler deixava o logger
    escrevendo no arquivo da rodada anterior -- um teste passava e o seguinte
    escrevia no arquivo do primeiro.
    """
    global _logger
    with _trava_do_registro:
        _baldes.clear()
    if hasattr(_local, "balde"):
        del _local.balde
    log = logging.getLogger("blazes.latencia")
    for h in list(log.handlers):
        log.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    _logger = None
