"""Histórico de quedas do jogo — o que a tela "Histórico de Quedas" mostra.

=========================================================================
PARA QUE SERVE
=========================================================================

Quando o cliente do jogo cai, o bot mata a janela e religa. Até aqui isso
acontecia em silêncio: de manhã o usuário via "relogins: 7" e nada mais. Esta
tela responde, para cada queda, as quatro perguntas que ele faz:

    QUANDO foi          data e hora exatas
    O QUE aconteceu     o jogo fechou / a janela sumiu / perdeu a conexão
    O QUE ele fazia     "estava lutando contra o chefe", e onde
    COMO estava a tela  o print, quando é possível tirar um

=========================================================================
POR QUE ESTE MÓDULO VIVE NO CORE
=========================================================================

A interface (web) só mostra: o "corpo" fica lá, e o resto mora aqui. Gravar, podar, traduzir para português
de gente e montar o relatório de suporte acontece tudo aqui; lá em cima só se
desenha.

Ele também não importa NADA de `blazesbot.bot` -- quem chama traduz o motivo
para uma das chaves de `MOTIVOS`. Core não depende de bot.

=========================================================================
A ORDEM QUE NÃO PODE SER TROCADA
=========================================================================

`AccountSupervisor._encerrar_caido` MATA o cliente -- é a única situação em que
o bot fecha o jogo. O registro e o print têm que sair ANTES disso, senão não há
mais janela para fotografar nem processo para consultar.

E o print só existe numa das três quedas. Nas outras duas (processo encerrado,
janela sumiu) a janela já morreu quando a queda é detectada: o cartão sai sem
print, sem inventar explicação.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ===========================================================================
# RETENÇÃO
# ===========================================================================

# Por TEMPO, e não por contagem: a pergunta é "o que aconteceu essa noite", e
# ela não tem número fixo de respostas. Três dias cobrem o fim de semana.
DIAS_GUARDADOS = 3

PASTA = Path("logs") / "quedas"
ARQUIVO = PASTA / "quedas.jsonl"

# Linhas de log guardadas por conta. NÃO aparecem na tela (ver `FASES`); vão
# para o arquivo e para o relatório de suporte.
LINHAS_DE_LOG_GUARDADAS = 20

# Qualidade do JPEG. O print aqui é para OLHO HUMANO ler um aviso, não para
# casamento de template -- compressão não atrapalha nada. Medido no
# `diagnostico_do_link`: o mesmo quadro em PNG dá 1,4 MB; em JPEG 85 fica na
# casa das centenas de KB, com o texto do aviso perfeitamente legível.
QUALIDADE_DO_JPEG = 85

# Largura da MINIATURA, gravada ao lado do print inteiro.
#
# Ela existe por uma restrição da web, não por estética: a página roda em
# `file://` e o WebView2 bloqueia `<img src>` apontando para outro arquivo
# local. A imagem tem que viajar embutida (data URI), e mandar o print inteiro
# de 30 quedas seriam megabytes por carregamento. A miniatura fica na casa dos
# 15 KB; o print inteiro só é pedido quando o usuário CLICA nela.
LARGURA_DA_MINIATURA = 320

# ===========================================================================
# TRADUÇÃO PARA PORTUGUÊS DE GENTE
# ===========================================================================

# As três quedas que o watchdog reconhece. A chave é passada por quem chama;
# assim o core não importa `bot.watchdog`.
MOTIVOS: dict[str, str] = {
    "processo": "O jogo fechou sozinho",
    "janela": "A janela do jogo desapareceu",
    "conexao": "O jogo perdeu a conexão com o servidor",
    # O QUARTO MOTIVO, desde 08/09/2026. Só o vigia global o produz: processo
    # vivo, janela existindo, nenhuma caixa na tela -- e o laço de mensagens do
    # cliente parado por 18 s seguidos. Ver `bot/sentinela.py`.
    "travou": "O jogo congelou e parou de responder",
}
MOTIVO_DESCONHECIDO = "O jogo parou de responder"

# O QUE ELE ESTAVA FAZENDO, derivado da FASE da rotina.
#
# ESTA É A GARANTIA DE QUE NADA DE DEV VAZA PARA A TELA, e é por isso que a
# frase NÃO vem da última linha de log. Log é texto livre: fala de waypoint,
# flag de combate, teto do diálogo, endereço de memória, coordenada de clique.
# Um filtro sobre texto livre é lista negra -- só protege do que se lembrou de
# proibir. Aqui a fonte é um conjunto FECHADO de nomes de fase, e cada frase foi
# escrita à mão: não existe caminho pelo qual um endereço de memória chegue à
# tela.
FASES: dict[str, str] = {
    "SITUAR": "Estava se localizando no mapa",
    "PREPARAR": "Estava se preparando (montaria e bichinho)",
    "ATE_A_ENTRADA": "Estava indo até a entrada da caverna",
    "ENTRAR": "Estava tentando entrar na caverna",
    # O nome antigo do PREPARAR_DENTRO do BC (até 26/09/2026): quedas já
    # gravadas ainda o trazem.
    "CURAR": "Estava se curando",
    "PREPARAR_DENTRO": "Estava se preparando dentro da caverna (vida, buffs e bichinho)",
    "ATE_O_ALTAR": "Estava atravessando a caverna até o Altar",
    "ENTRAR_NO_COVIL": "Estava abrindo a passagem para o covil do chefe",
    "ATE_OS_GUARDAS": "Estava indo até os quatro guardas",
    "GUARDAS": "Estava lutando contra os quatro guardas",
    "ATE_O_BOSS": "Estava indo até o chefe",
    "BOSS": "Estava lutando contra o chefe",
    "SAIR": "Estava saindo da caverna",
    "MANUTENCAO": "Estava vendendo os itens na cidade",
    "RECUPERAR": "Estava se recuperando de um problema",
}
FASE_DESCONHECIDA = "Estava começando a rodar"


def frase_do_motivo(chave: str | None) -> str:
    return MOTIVOS.get(chave or "", MOTIVO_DESCONHECIDO)


def frase_da_fase(fase: str | None) -> str:
    return FASES.get((fase or "").upper(), FASE_DESCONHECIDA)


def frase_do_tempo(segundos: float | None) -> str:
    """"2 h 14 min", "37 min", "48 s" — nunca "8073.4"."""
    if not segundos or segundos <= 0:
        return ""
    s = int(segundos)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    return f"{s // 3600} h {(s % 3600) // 60:02d} min"


def frase_do_quando(carimbo: float, hoje: date | None = None) -> str:
    """"Hoje, 03:47:12" / "Ontem, 22:10:05" / "11/08, 04:02:59".

    `hoje` é injetável para o teste não depender do calendário da máquina.
    """
    quando = datetime.fromtimestamp(carimbo)
    referencia = hoje or date.today()
    dias = (referencia - quando.date()).days
    hora = quando.strftime("%H:%M:%S")
    if dias == 0:
        return f"Hoje, {hora}"
    if dias == 1:
        return f"Ontem, {hora}"
    return f"{quando.strftime('%d/%m')}, {hora}"


# ===========================================================================
# AS ÚLTIMAS LINHAS DE LOG DE CADA CONTA
# ===========================================================================


class CapturaDeLog(logging.Handler):
    """Guarda as últimas linhas de cada conta, para a hora da queda.

    Uma `deque` por conta, com `maxlen` -- custo constante e sem crescimento.
    As interfaces têm filas parecidas, mas elas são DELAS: a queda é gravada
    pelo supervisor, numa thread que não conhece interface nenhuma, e depender
    da fila da interface deixaria o registro vazio quando o bot roda sem interface.
    """

    def __init__(self, maximo: int = LINHAS_DE_LOG_GUARDADAS) -> None:
        super().__init__()
        self._maximo = maximo
        self._por_conta: dict[str, deque[str]] = {}
        self._trava = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            partes = record.name.split(".", 1)
            conta = partes[1] if len(partes) > 1 else ""
            linha = (f"{time.strftime('%H:%M:%S', time.localtime(record.created))}"
                     f" [{record.levelname}] {record.getMessage()}")
            with self._trava:
                fila = self._por_conta.get(conta)
                if fila is None:
                    fila = deque(maxlen=self._maximo)
                    self._por_conta[conta] = fila
                fila.append(linha)
        except Exception:
            # Handler de log NUNCA derruba quem está logando.
            pass

    def ultimas(self, conta: str) -> list[str]:
        with self._trava:
            return list(self._por_conta.get(conta, ()))


_captura: CapturaDeLog | None = None


def instalar_captura_de_log() -> CapturaDeLog:
    """Anexa a captura ao logger `blazes`. Idempotente."""
    global _captura
    if _captura is None:
        _captura = CapturaDeLog()
        _captura.setLevel(logging.DEBUG)
        logging.getLogger("blazes").addHandler(_captura)
    return _captura


def ultimas_linhas(conta: str) -> list[str]:
    return _captura.ultimas(conta) if _captura is not None else []


# ===========================================================================
# GRAVAR
# ===========================================================================


def nome_da_miniatura(nome: str) -> str:
    return nome.replace(".jpg", "-mini.jpg")


def _salvar_print(quadro: Any, destino: Path) -> bool:
    """Grava o quadro em JPEG, mais a miniatura ao lado. Devolve se conseguiu.

    Quadro em branco NÃO vira print: `capture_window` devolve sucesso mesmo
    produzindo tela preta, e um retângulo preto no cartão diria ao usuário
    "a tela estava assim", que é mentira.
    """
    if quadro is None:
        return False
    try:
        import cv2

        from .vision import frame_is_blank

        if frame_is_blank(quadro):
            return False
        PASTA.mkdir(parents=True, exist_ok=True)
        parametros = [int(cv2.IMWRITE_JPEG_QUALITY), QUALIDADE_DO_JPEG]
        if not cv2.imwrite(str(destino), quadro, parametros):
            return False

        altura, largura = quadro.shape[:2]
        if largura > LARGURA_DA_MINIATURA:
            escala = LARGURA_DA_MINIATURA / largura
            mini = cv2.resize(
                quadro, (LARGURA_DA_MINIATURA, max(1, int(altura * escala))),
                interpolation=cv2.INTER_AREA)
        else:
            mini = quadro
        cv2.imwrite(str(destino.parent / nome_da_miniatura(destino.name)),
                    mini, parametros)
        return True
    except Exception:
        return False


# Cache do `data:` URI por nome de arquivo. O JPEG é IMUTÁVEL depois de escrito
# (o nome carrega o carimbo de tempo), então reencodar é trabalho jogado fora.
#
# Sem o cache, `listar()` relia e reencodava em base64 a miniatura de CADA queda
# retida a CADA abertura da aba: com 3 dias de retenção e várias contas são
# dezenas ou centenas de registros, ~20 KB de texto cada, montados em Python e
# depois embutidos num literal JS executado por `webview.Invoke` na THREAD DE UI
# do WebView2. A janela congelava por segundos a cada abertura, e o custo crescia
# com o tempo de operação.
#
# Limitado para o cache não virar o próximo vazamento: a poda de 3 dias remove
# arquivos, e entradas órfãs saem quando o teto é atingido.
_MAX_EMBUTIDAS_EM_CACHE = 120
_EMBUTIDAS: dict[str, str] = {}


def imagem_embutida(nome: str | None) -> str | None:
    """O JPEG como `data:` URI, para o `<img>` da web.

    A página roda em `file://` e o WebView2 recusa `<img src>` apontando para
    outro arquivo local -- a imagem precisa viajar embutida.
    """
    if not nome:
        return None
    em_cache = _EMBUTIDAS.get(nome)
    if em_cache is not None:
        return em_cache
    try:
        import base64

        dados = (PASTA / nome).read_bytes()
        uri = "data:image/jpeg;base64," + base64.b64encode(dados).decode()
        if len(_EMBUTIDAS) >= _MAX_EMBUTIDAS_EM_CACHE:
            _EMBUTIDAS.clear()
        _EMBUTIDAS[nome] = uri
        return uri
    except OSError:
        return None


def registrar(
    *,
    conta: str,
    personagem: str | None = None,
    motivo: str,
    fase: str | None = None,
    posicao: tuple[int, int] | None = None,
    local: str | None = None,
    run: int | None = None,
    segundos_rodando: float | None = None,
    relogin: int | None = None,
    pid: int | None = None,
    quadro: Any = None,
    agora: float | None = None,
) -> dict[str, Any]:
    """Grava UMA queda. Chamado ANTES de o cliente ser encerrado.

    `quadro` é a captura que DETECTOU a queda (o watchdog já a tem na mão).
    Passar `None` é o caso normal das quedas em que a janela já morreu -- o
    registro sai sem print, e isso não é erro.

    Nunca levanta: uma falha ao gravar o histórico não pode atrapalhar o
    relogin, que é o que devolve a conta ao ar.
    """
    carimbo = agora if agora is not None else time.time()
    registro: dict[str, Any] = {
        "quando": carimbo,
        "conta": conta,
        "personagem": personagem,
        "motivo": motivo,
        "fase": fase,
        "posicao": list(posicao) if posicao else None,
        "local": local,
        "run": run,
        "segundos_rodando": segundos_rodando,
        "relogin": relogin,
        "pid": pid,
        "log": ultimas_linhas(conta),
        "print": None,
    }
    try:
        nome = (f"{datetime.fromtimestamp(carimbo).strftime('%Y%m%d-%H%M%S')}"
                f"-{conta or 'conta'}.jpg")
        if _salvar_print(quadro, PASTA / nome):
            registro["print"] = nome

        PASTA.mkdir(parents=True, exist_ok=True)
        with ARQUIVO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        podar(agora=carimbo)
    except Exception:
        logging.getLogger("blazes").debug(
            "Não consegui gravar o histórico de quedas", exc_info=True)
    return registro


# ===========================================================================
# PODAR, LER
# ===========================================================================


def _carregar() -> list[dict[str, Any]]:
    if not ARQUIVO.exists():
        return []
    registros = []
    try:
        for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            try:
                registros.append(json.loads(linha))
            except ValueError:
                continue          # linha truncada por escrita concorrente
    except OSError:
        return []
    return registros


def podar(agora: float | None = None) -> int:
    """Apaga o que passou de `DIAS_GUARDADOS`. Devolve quantos saíram.

    Apaga a LINHA e o JPEG juntos -- histórico sem imagem seria meio registro,
    e imagem sem histórico seria lixo que ninguém encontra.
    """
    corte = (agora if agora is not None else time.time()) - DIAS_GUARDADOS * 86400
    registros = _carregar()
    ficam = [r for r in registros if r.get("quando", 0) >= corte]
    if len(ficam) == len(registros):
        return 0
    try:
        vivos = {r.get("print") for r in ficam}
        for r in registros:
            nome = r.get("print")
            if nome and nome not in vivos:
                (PASTA / nome).unlink(missing_ok=True)
                (PASTA / nome_da_miniatura(nome)).unlink(missing_ok=True)
        ARQUIVO.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ficam),
            encoding="utf-8")
    except OSError:
        return 0
    return len(registros) - len(ficam)


def amigavel(registro: dict[str, Any],
             hoje: date | None = None) -> dict[str, Any]:
    """O registro cru + os campos já em português, prontos para desenhar.

    A tradução acontece AQUI e não na interface: traduzir em dois lugares
    divergiria na primeira frase que
    alguém ajustasse.
    """
    pos = registro.get("posicao")
    return {
        **registro,
        "quando_texto": frase_do_quando(registro.get("quando", 0), hoje),
        "motivo_texto": frase_do_motivo(registro.get("motivo")),
        "fazendo_texto": frase_da_fase(registro.get("fase")),
        "onde_texto": _onde(registro.get("local"), pos),
        "rodando_texto": frase_do_tempo(registro.get("segundos_rodando")),
        "print_caminho": (str(PASTA / registro["print"])
                          if registro.get("print") else None),
        # Só a MINIATURA vai na listagem. O print inteiro é pedido à parte,
        # quando o usuário clica -- 30 quedas com o print inteiro seriam megabytes
        # embutidos em cada carregamento da tela.
        "print_mini": imagem_embutida(
            nome_da_miniatura(registro["print"]) if registro.get("print")
            else None),
    }


def _onde(local: str | None, pos: list | None) -> str:
    """"no covil (80, -406)" — o lugar em palavras e a coordenada atrás."""
    coord = f"({pos[0]}, {pos[1]})" if pos and len(pos) == 2 else ""
    if local and coord:
        return f"{local} {coord}"
    return local or coord


def listar(conta: str | None = None, hoje: date | None = None
           ) -> list[dict[str, Any]]:
    """As quedas dos últimos dias, da mais recente para a mais antiga.

    `conta=None` (o padrão da tela) traz todas -- é a pergunta real, "o que
    aconteceu essa noite", que atravessa contas.
    """
    podar()
    registros = _carregar()
    if conta:
        registros = [r for r in registros if r.get("conta") == conta]
    registros.sort(key=lambda r: r.get("quando", 0), reverse=True)
    return [amigavel(r, hoje) for r in registros]


def contas_com_quedas() -> list[str]:
    """Logins que aparecem no histórico, para o seletor da tela."""
    vistos = {r.get("conta") for r in _carregar() if r.get("conta")}
    return sorted(vistos)


# ===========================================================================
# RELATÓRIO DE SUPORTE
# ===========================================================================


def relatorio(registros: list[dict[str, Any]]) -> str:
    """O texto do botão "Copiar relatório". Leva TUDO.

    Este botão existe para chegar ao desenvolvedor, então ele carrega o que a
    tela esconde de propósito: fase crua, coordenadas, PID e as linhas de log.
    Levar só o que está na tela faria o dev receber o mesmo que já viu no print
    do usuário e ter que pedir o arquivo assim mesmo.
    """
    if not registros:
        return "Nenhuma queda nos últimos %d dias." % DIAS_GUARDADOS

    partes = [f"HISTÓRICO DE QUEDAS ({len(registros)} nos últimos "
              f"{DIAS_GUARDADOS} dias)", ""]
    for r in registros:
        partes.append(f"=== {r.get('quando_texto', '')} — conta "
                      f"{r.get('conta') or '?'}"
                      + (f" ({r['personagem']})" if r.get("personagem") else ""))
        partes.append(f"{r.get('motivo_texto', '')}.")
        onde = r.get("onde_texto") or ""
        partes.append(f"{r.get('fazendo_texto', '')}"
                      + (f", em {onde}" if onde else "") + ".")
        detalhe = [
            f"fase={r.get('fase')}",
            f"run={r.get('run')}",
            f"relogin={r.get('relogin')}",
            f"pid={r.get('pid')}",
            f"rodando={r.get('rodando_texto') or '-'}",
            f"motivo_bruto={r.get('motivo')}",
        ]
        partes.append("  [técnico] " + " | ".join(detalhe))
        if r.get("print_caminho"):
            partes.append(f"  [print] {r['print_caminho']}")
        linhas = r.get("log") or []
        if linhas:
            partes.append(f"  [últimas {len(linhas)} linhas de log]")
            partes.extend(f"    {x}" for x in linhas)
        partes.append("")
    return "\n".join(partes)
