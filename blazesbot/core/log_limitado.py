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
import time
from pathlib import Path

# Quantas linhas o arquivo guarda. As mais antigas são descartadas.
LINHAS_MAXIMAS = 500

# Quanto ele pode passar antes de a poda acontecer. Podar de cem em cem em vez de
# uma a uma troca cem reescritas por uma só.
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
DIAS_DE_ARQUIVO_MORTO = 7

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
        if self.pasta_do_arquivo_morto is not None:
            # A LIMPEZA É UMA VEZ POR PROCESSO, não por poda. Varrer a pasta a
            # cada poda seria custo de disco repetido para uma resposta que muda
            # uma vez por dia.
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

        Roda UMA VEZ por processo (no `__init__`), não por poda: varrer a pasta a
        cada poda seria custo de disco repetido para uma resposta que muda uma vez
        por dia.
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
                        and antigo.suffix != ".gz"):
                    self._comprimir(antigo)
        except Exception:
            pass

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
