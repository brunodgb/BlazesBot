"""Arquivo de log com teto de linhas: passou do limite, a mais antiga sai.

=========================================================================
POR QUE NÃO O `RotatingFileHandler` DA BIBLIOTECA
=========================================================================

O rotativo padrão corta por BYTES e guarda os pedaços em arquivos `.1`, `.2`.
Isso resolve espaço em disco, não é o que foi pedido: o pedido é ter sempre, num
arquivo só, no máximo N linhas -- as N últimas. Com o rotativo, achar "as últimas
500 linhas" significaria abrir dois arquivos e emendar na ordem certa.

=========================================================================
POR QUE NÃO REESCREVER A CADA LINHA
=========================================================================

Manter exatamente N linhas o tempo todo exigiria reescrever o arquivo inteiro a
cada `emit`. Com quatro contas escrevendo ao mesmo tempo isso vira disco parado.

Em vez disso o arquivo cresce até `N + FOLGA` e é aparado de uma vez, voltando
para N. O custo de reescrever é pago uma vez a cada FOLGA linhas, e o arquivo
nunca passa de `N + FOLGA` -- ou seja, o teto continua valendo, com uma margem
conhecida em vez de uma reescrita por linha.
"""
from __future__ import annotations

import gzip
import logging
import shutil
import threading
import time
from pathlib import Path

# Quantas linhas o arquivo guarda. As mais antigas são descartadas.
LINHAS_MAXIMAS = 500

# Quanto ele pode passar antes de a poda acontecer. Podar de cem em cem em vez de
# uma a uma troca cem reescritas por uma só. Vale para os arquivos de 500 linhas;
# os dois GRANDES que arquivam (dev e telemetria) podam com folga = máximo --
# ver `log_json.FOLGA_DO_LOG_JSON`.
FOLGA_ANTES_DE_PODAR = 100

# ===========================================================================
# O ARQUIVO MORTO: o que a poda descarta deixou de ser PERDIDO
# ===========================================================================
#
# Pedido do usuário em 19/08/2026: *"em vez de zerar, você passa para um segundo
# arquivo que não é lido com frequência e ele vai salvar tudo que precisa."*
#
# O MOTIVO É MEDIDO. O log de dev cobre **28 minutos** (4.000 registros, 1,5 MB) e
# a cada poda o mais antigo era jogado fora. Durante a investigação da morte do
# alvo, as 69 leituras que continham a prova **desapareceram entre duas consultas
# minhas** -- e o plano de calibração depende justamente de acumular evidência ao
# longo de muitas runs.
#
# POR QUE NÃO PESA NO BOT, e é aqui que o desenho importa: a gravação acontece
# **uma vez por poda**, num único `writelines` do bloco inteiro que sairia. Não é
# um segundo handler recebendo `emit` a cada linha -- isso dobraria o custo do
# caminho quente. A poda já acontece uma vez a cada `FOLGA_ANTES_DE_PODAR` linhas,
# e o arquivamento pega carona nela.
#
# Um arquivo POR DIA, e a retenção é em DIAS e não em bytes -- mesmo desenho da
# retenção dos prints de queda. Dia é a unidade em que se pensa sobre isto ("o que
# aconteceu ontem à noite"); byte não é.
# DOIS DIAS, e o motivo NAO e disco -- e a qualidade da resposta.
#
# Diretiva do usuario em 06/09/2026: *"os logs dev principalmente podem mudar
# bastante a cada atualizacao que fizemos, e ter lixo ou informacao que se tornou
# irrelevante atrapalha em vez de ajuda."*
#
# ISTO JA CUSTOU UM VEREDITO ERRADO. Em 06/09/2026 uma auditoria do ponteiro de
# nome do alvo varreu 1.160.883 linhas -- os sete dias inteiros -- e concluiu
# "50,4% ilegivel". Mas os consertos `d9bc023` ("o nome sai certo em 100% das
# leituras, nao em 21%") e `1a5b19c` ("o alvo resolve em 100%, e nao em 62%")
# entraram em **01/09 as 15:20 e 15:34**. Metade da amostra descrevia um bot que
# nao existe mais, e a media dos dois mundos nao descreve nenhum dos dois.
#
# Log de dev nao e historico: e a fotografia do bot DE AGORA. Sete dias de
# retencao pressupoem um codigo estavel por sete dias, e este nao e.
DIAS_DE_ARQUIVO_MORTO = 2

# De quanto em quanto tempo varrer a pasta do arquivo morto.
#
# ANTES A VARREDURA SO ACONTECIA NO `__init__` -- uma vez por processo. E o bot
# fica LIGADO por dias: medido em 06/09/2026, com o processo no ar desde a
# vespera, o arquivo do dia estava com **298 MB sem comprimir**, o de ontem nunca
# tinha sido comprimido e nenhum dia velho tinha sido apagado. A retencao existia
# no papel e nao acontecia.
#
# Uma hora: a resposta so muda na virada do dia, entao varrer de hora em hora
# erra por no maximo uma hora e custa um `glob` por hora.
INTERVALO_ENTRE_LIMPEZAS = 3600.0

# Quanto tempo um arquivo precisa estar QUIETO para poder ser comprimido.
#
# Na virada da meia-noite o arquivo de "ontem" pode ainda receber a ultima
# anexacao de uma poda que comecou antes das 00:00. `_comprimir` copia e apaga o
# original, entao uma anexacao nesse vao se perderia. Um minuto de silencio e
# folga de sobra para uma janela que dura milissegundos.
SEGUNDOS_DE_SILENCIO_ANTES_DE_COMPRIMIR = 60.0

# O arquivo morto de DIAS ANTERIORES é comprimido. Medido no arquivo da noite de
# 20/08/2026: **23 MB -> 740 KB, 32x menos**, e é a mesma evidência -- JSONL é
# texto repetitivo, o melhor caso possível para gzip.
#
# SÓ DIAS ANTERIORES: o arquivo de HOJE ainda recebe anexação, e comprimir um
# arquivo aberto para escrita perderia o que vier depois.
#
# Sem isto a conta é 23 MB por noite x 7 dias de retenção = ~165 MB. Com isto,
# ~5 MB. O único custo é `gzip.open` para ler depois, e ler é raro.
COMPRIMIR_ARQUIVO_MORTO = True


class ArquivoDeLogLimitado(logging.FileHandler):
    """`FileHandler` que mantém no máximo `maximo` linhas no arquivo."""

    def __init__(
        self,
        caminho,
        mode: str = "a",
        encoding: str = "utf-8",
        maximo: int = LINHAS_MAXIMAS,
        folga: int = FOLGA_ANTES_DE_PODAR,
        arquivar: bool = False,
    ) -> None:
        """`arquivar=True` manda o que a poda descarta para `<pasta>/arquivo/`.

        Desligado por padrão de propósito: os logs legíveis do usuário
        (`sessao-atual.log`, os diários) são resumos, e guardar o que sai deles
        não serve para nada. Quem liga é o log de dev, que é a matéria-prima da
        calibração -- ver `DIAS_DE_ARQUIVO_MORTO`.
        """
        # Garante que o diretório do arquivo exista antes de abrir (ex.: o
        # `logs/dev/` do JSON dev, que é subpasta criada por nós).
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(caminho, mode=mode, encoding=encoding)
        self.caminho = Path(caminho)
        self.maximo = max(1, int(maximo))
        self.folga = max(1, int(folga))
        self._linhas = self._contar()
        self.pasta_do_arquivo_morto = (
            self.caminho.parent / "arquivo" if arquivar else None)
        # Quando a pasta foi varrida pela última vez, e a trava que impede duas
        # varreduras ao mesmo tempo. Ver `INTERVALO_ENTRE_LIMPEZAS`.
        self._ultima_limpeza = 0.0
        self._limpando = threading.Lock()
        if self.pasta_do_arquivo_morto is not None:
            # A primeira é SÍNCRONA, no arranque: o processo ainda não está
            # logando, então não há caminho quente a atrapalhar, e começar já
            # limpo é o certo.
            self._ultima_limpeza = time.time()
            self._limpar_arquivo_morto()

    # -- contagem ------------------------------------------------------

    def _contar(self) -> int:
        """Linhas já existentes no arquivo. Zero se ele não existe ou não lê."""
        try:
            with open(self.caminho, encoding=self.encoding or "utf-8",
                      errors="replace") as arq:
                return sum(1 for _ in arq)
        except OSError:
            return 0

    # -- escrita -------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        # UM REGISTRO PODE VALER VÁRIAS LINHAS -- um traceback é um `emit` só e
        # dez linhas no arquivo. Contar registros daria um teto errado justamente
        # nos casos em que o log cresce depressa.
        try:
            texto = self.format(record)
        except Exception:
            texto = ""
        self._linhas += texto.count("\n") + 1

        if self._linhas > self.maximo + self.folga:
            self._podar()

        self._limpar_de_tempos_em_tempos()

    def _limpar_de_tempos_em_tempos(self) -> None:
        """Varre a pasta do arquivo morto de hora em hora, FORA do caminho quente.

        Numa THREAD, e isso não é enfeite: `emit` roda com o lock do handler
        segurado, e comprimir o arquivo de ontem (centenas de MB) ali dentro
        pararia o log de TODAS as contas pelo tempo do gzip. A thread é daemon
        para não segurar o encerramento do bot.

        O que ela varre não é o que está sendo escrito: comprimir pula o arquivo
        de HOJE, e a retenção só alcança datas velhas. O arquivo quente e o
        arquivo do dia nunca são tocados por ela.
        """
        if self.pasta_do_arquivo_morto is None:
            return
        agora = time.time()
        if agora - self._ultima_limpeza < INTERVALO_ENTRE_LIMPEZAS:
            return
        # Carimba ANTES de disparar: se a varredura demorar mais que o intervalo,
        # carimbar no fim faria a seguinte sair imediatamente atrás dela.
        self._ultima_limpeza = agora
        threading.Thread(target=self._limpar_sem_atropelar,
                         name="limpeza-do-arquivo-morto", daemon=True).start()

    def _limpar_sem_atropelar(self) -> None:
        """Uma varredura por vez. Falha nunca sobe -- é thread solta."""
        if not self._limpando.acquire(blocking=False):
            return
        try:
            self._limpar_arquivo_morto()
        except Exception:
            pass
        finally:
            self._limpando.release()

    def _podar(self) -> None:
        """Reescreve o arquivo mantendo só as últimas `maximo` linhas.

        Roda DENTRO do `emit`, que o `logging` já chama com o lock do handler
        segurado -- então duas threads não podam ao mesmo tempo.

        Qualquer falha de disco aqui é engolida de propósito: um arquivo de log
        que não consegue ser aparado não pode derrubar o farm. No pior caso ele
        cresce, que é o comportamento de antes.
        """
        try:
            self.acquire()
            try:
                if self.stream:
                    self.stream.close()
                    self.stream = None  # type: ignore[assignment]

                with open(self.caminho, encoding=self.encoding or "utf-8",
                          errors="replace") as arq:
                    linhas = arq.readlines()

                mantidas = linhas[-self.maximo:]
                # O QUE SAI VAI PARA O ARQUIVO MORTO ANTES de ser perdido, e num
                # `writelines` só. Se isto falhar, a poda SEGUE: o teto do
                # arquivo quente é o que protege o disco, e arquivar é o extra.
                descartadas = linhas[:-self.maximo] if self.maximo else linhas
                if descartadas and self.pasta_do_arquivo_morto is not None:
                    self._arquivar(descartadas)
                with open(self.caminho, "w", encoding=self.encoding or "utf-8") as arq:
                    arq.writelines(mantidas)

                # Recontagem a partir do que SOBROU, e não do contador: o contador
                # é só o gatilho, e estimativa acumulada erra com o tempo.
                self._linhas = len(mantidas)
            finally:
                if not self.stream:
                    self.stream = self._open()
                self.release()
        except Exception:
            pass

    # -- arquivo morto -------------------------------------------------

    def _caminho_do_dia(self) -> Path:
        """Um arquivo por dia, nomeado pela data.

        `time.localtime` e não UTC: quem vai ler isto pensa em "ontem à noite",
        e o fuso do relógio da máquina é o fuso dessa frase.
        """
        assert self.pasta_do_arquivo_morto is not None
        dia = time.strftime("%Y-%m-%d", time.localtime())
        return self.pasta_do_arquivo_morto / f"{self.caminho.stem}-{dia}{self.caminho.suffix}"

    def _arquivar(self, linhas: list[str]) -> None:
        """Anexa em bloco o que a poda vai descartar. Falha nunca propaga."""
        try:
            self.pasta_do_arquivo_morto.mkdir(parents=True, exist_ok=True)
            with open(self._caminho_do_dia(), "a",
                      encoding=self.encoding or "utf-8") as arq:
                arq.writelines(linhas)
        except Exception:
            pass

    def _limpar_arquivo_morto(self) -> None:
        """Comprime o de dias anteriores e apaga o que passou da retenção.

        Pela DATA NO NOME, não pelo mtime: o mtime muda a cada anexação, então um
        arquivo de ontem que recebeu linha hoje pareceria de hoje -- e sobreviveria
        à retenção para sempre. O nome é o que diz de que dia é o conteúdo.

        Roda no arranque e depois de hora em hora, numa thread -- ver
        `_limpar_de_tempos_em_tempos`. Era SÓ no arranque, e como o bot fica
        ligado por dias a retenção existia no papel e não acontecia: medido em
        06/09/2026, 298 MB sem comprimir no arquivo do dia e cinco dias velhos
        que deveriam ter sido apagados.
        """
        try:
            agora = time.time()
            limite = agora - DIAS_DE_ARQUIVO_MORTO * 86400
            hoje = time.strftime("%Y-%m-%d", time.localtime())
            prefixo = f"{self.caminho.stem}-"
            for antigo in list(self.pasta_do_arquivo_morto.glob(
                    f"{prefixo}*")):
                data = self._data_no_nome(antigo, prefixo)
                if data is None:
                    continue      # nome fora do padrão: não é nosso, não mexe
                try:
                    quando = time.mktime(time.strptime(data, "%Y-%m-%d"))
                except ValueError:
                    continue
                if quando < limite:
                    antigo.unlink(missing_ok=True)
                    continue
                if (COMPRIMIR_ARQUIVO_MORTO and data != hoje
                        and antigo.suffix != ".gz"
                        and self._esta_quieto(antigo, agora)):
                    self._comprimir(antigo)
        except Exception:
            pass

    @staticmethod
    def _esta_quieto(arquivo: Path, agora: float) -> bool:
        """O arquivo parou de receber linha? Ver
        `SEGUNDOS_DE_SILENCIO_ANTES_DE_COMPRIMIR`.

        Não ler o mtime devolve `False`: na dúvida não se comprime, porque o
        preço de comprimir cedo é perder a última anexação e o de comprimir
        tarde é uma hora a mais de disco.
        """
        try:
            return (agora - arquivo.stat().st_mtime
                    >= SEGUNDOS_DE_SILENCIO_ANTES_DE_COMPRIMIR)
        except OSError:
            return False

    @staticmethod
    def _data_no_nome(caminho: Path, prefixo: str) -> str | None:
        """A data do nome, com ou sem `.gz`. `None` se o nome não é nosso."""
        nome = caminho.name
        if not nome.startswith(prefixo):
            return None
        resto = nome[len(prefixo):]
        for sufixo in (".gz", ""):
            if sufixo and resto.endswith(sufixo):
                resto = resto[: -len(sufixo)]
                break
        return resto.rsplit(".", 1)[0] or None

    @staticmethod
    def _comprimir(arquivo: Path) -> None:
        """`x.jsonl` -> `x.jsonl.gz`, e só apaga o original se der certo.

        A ordem importa: comprime para um `.tmp`, renomeia, e só então apaga. Uma
        queda no meio deixa o original intacto -- perder a evidência de uma noite
        para economizar disco seria o pior negócio possível.
        """
        try:
            destino = arquivo.with_suffix(arquivo.suffix + ".gz")
            temporario = destino.with_suffix(".tmp")
            with open(arquivo, "rb") as entrada,                     gzip.open(temporario, "wb", compresslevel=6) as saida:
                shutil.copyfileobj(entrada, saida, length=1 << 20)
            temporario.replace(destino)
            arquivo.unlink(missing_ok=True)
        except Exception:
            pass
