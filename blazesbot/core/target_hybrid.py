"""O VIGIA DO ALVO: identidade pela MEMÓRIA, vida pela TELA.

Duas perguntas, duas fontes, cada uma onde ela é boa:

* **quem é o alvo** -- `0x0115CB80`. Não sabemos o que o número significa, e não
  precisamos: `0` é "sem alvo", qualquer outro valor é "tem alvo", e valor
  DIFERENTE é "trocou de alvo". É o que o usuário mediu e é tudo o que se usa
  dele. Custa ~1 µs.
* **quanta vida ele tem** -- a barra desenhada, no offset fixo medido
  (`vision.ler_barra_do_alvo`). Custa uma captura.

===========================================================================
O QUE MUDOU EM 25/08/2026, E POR QUE
===========================================================================

**Saiu o `asyncio`.** A versão anterior tinha `ler_alvo()` assíncrono, com
`asyncio.Lock` e um atraso obrigatório de 50-100 ms depois da troca de alvo --
e **ninguém chamava esse método**. O bot usava `ler_alvo_snapshot()`, síncrono,
que não logava nada. Consequências medidas nas 14 lutas de 24-25/08:

    0 linhas com a % de vida do alvo
    14 de 14 lutas com "o alvo chegou a ser visto=False"
    14 de 14 com "NOME ilegivel" e "vou bater SEM LER o nome"

O bot inteiro roda em threads, uma por conta, com `ctx.tick()`. Máquina
assíncrona no meio disso não tem quem a rode.

**`pid` e `hwnd` deixaram de ser guardados.** Eles eram fixados na construção,
e depois de um relogin a janela e o processo mudam -- o objeto continuava lendo
a memória de um processo morto e capturando uma janela que não existe mais, sem
avisar. Agora quem chama passa os atuais em toda leitura, e o handle é reaberto
quando o `pid` muda.

**Saiu a varredura da tabela de entidades.** A versão anterior chamava
`entidades_vivas()` a cada leitura e procurava `ent["obj"] == target_id` -- ou
seja, comparava um valor de significado desconhecido com um endereço de heap,
pagando ~800 leituras de memória para quase nunca achar. O que aquilo produzia
era `nome=None` sempre, e daí os 14/14 `ilegivel`.
"""
from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from . import vision
from .entidades import parece_entidade
from .memory import (
    ADDR_ENTITY_SCAN_BASE,
    ADDR_TARGET_ID,
    LIMITE_DE_ENTIDADES,
    OFF_ENTITY_ID,
    Memory,
)
from .vision import LeituraDaBarra

if TYPE_CHECKING:
    from .vision import BGRFrame

_logger = logging.getLogger("blazes.target_hybrid")

# Endereço estático do Target ID, medido pelo usuário em 21/08/2026.
# client.exe + 0xD5CB80 = 0x0115CB80.
#
# O QUE O VALOR SIGNIFICA AINDA NÃO SE SABE, e está registrado assim de
# propósito. O que está medido é o COMPORTAMENTO, e é só dele que se depende:
#
#     valor 0          -> não há alvo
#     valor != 0       -> há alvo
#     valor MUDOU      -> o alvo é outro
#
# Palavras do usuário: *"ele sempre muda o valor dele quando mudar de target,
# então ele é muito confiável"*. Descobrir o significado é assunto do log de
# investigação (`logs/target_id/`), não deste módulo.
# Reexportado do banco de endereços: ver `core/memory.ADDR_TARGET_ID`
# para a medição de que ele guarda o ID DA ENTIDADE selecionada e para
# a chave `+0x8` que liga o id à entidade.
TARGET_ID_ADDR = ADDR_TARGET_ID

# Abaixo desta fração a barra conta como VAZIA.
#
# O ÚNICO limiar de vida do projeto -- o `combat` importa daqui. Ter dois
# números para a mesma pergunta (havia `LIMIAR_DE_VIDA_DO_ALVO = 0.01` no
# `combat` e `0.02` aqui) é a receita para os dois divergirem.
#
# 0.02 e não 0.01 por medição do usuário: com 0.01 o mob morto ainda lia 0,7%.
# **Aquele piso era da régua antiga**, que dividia pixels vermelhos pela ÁREA do
# retângulo e diluía o valor nas linhas de borda. `ler_barra_do_alvo` conta
# COLUNA, e no teste sintético o mob morto dá 0.000 cravado. O limiar folgado
# fica como margem para ruído de compressão, não para corrigir a régua.
LIMIAR_VIDA_TELA = 0.02

# Abaixo desta fração de vida vale a pena procurar o `EnemyDead.png`.
#
# NÚMERO NOVO, escolhido com o usuário em 25/08/2026: *"a ideia do EnemyDead é
# só ser usado quando o ler_alvo_snapshot identificar que a % da vida está
# abaixo dos 10%"*. Acima disso o marcador não é consultado -- o mob está vivo e
# procurar sprite é custo por nada.
#
# A MESMA CAPTURA serve os dois: a barra já foi lida daquele quadro, e o
# marcador é procurado no mesmo. Não existe segunda captura em lugar nenhum.
FAIXA_PARA_OLHAR_O_MARCADOR = 0.10


# Casas do desenho da barra no log.
#
# EM ASCII, E ISSO NÃO É FEIURA GRATUITA. `main.py` cria o
# `logs/sessao-atual.log` **sem `encoding`**, então ele usa o do sistema (cp1252
# nesta máquina) -- e `█`/`░` levantam `UnicodeEncodeError` dentro do `logging`
# na primeira linha. O handler foi corrigido para utf-8 junto com esta mudança,
# mas o console do Windows continua sendo cp1252 em muitas configurações, e log
# que some quando o terminal muda não é log.
CASAS_DO_DESENHO = 10


class MorteDoAlvo:
    """*"Aquele mob morreu?"* -- a MESMA resposta em todo ecossistema.

    =========================================================================
    PECA COMPARTILHADA -- DEPENDENCIA CRUZADA BC <-> APP
    =========================================================================

    **Quem usa:** `bot/combate.py` (`CombatEngine._alvo_morreu_pela_memoria`)
    e `bot/app/executor.py` (`ExecutorDeMacro._alvo_morreu` /
    `_cortar_a_volta`). Mexer aqui mexe nos DOIS -- rode a suite inteira.

    **Por que mora no `core/`:** o criterio do projeto e uma pergunta so --
    *isso e sobre o JOGO ou sobre o que este ecossistema faz?*. "O mob morreu"
    e sobre o JOGO: a struct e a mesma, o cadaver dura os mesmos 7 a 13 s, e
    `hp == 0` quer dizer a mesma coisa para quem farma boss e para quem roda
    macro. O que e de cada ecossistema e o que FAZER com a resposta.

    **O que estava duplicado (medido em 26/08/2026):** as duas pontas
    implementavam a mesma regra em lugares diferentes, com o mesmo nome de
    atributo (`_ultimo_alvo_morto_id`) e o mesmo comentario explicando que a
    trava e por IDENTIDADE e nao por tempo. Duas copias da mesma decisao e
    duas chances de so uma delas ser corrigida.

    **O que NAO subiu para ca, de proposito:** a reserva pela TELA
    (`SO_A_MEMORIA_DECLARA_MORTE`, `EnemyDead.png`, a barra desenhada) fica no
    BC, porque o modo APP nao captura tela; e a reserva pela FLAG DE COMBATE
    fica no APP, porque o BC ja resolve o mesmo caso por outro caminho. Aqui
    fica so o que as duas fazem IGUAL.
    """

    def __init__(self) -> None:
        # A trava e por IDENTIDADE, nao por tempo: o cadaver fica selecionavel
        # de 7 a 13 s (medido em 20/08/2026). Uma trava de relogio curta demais
        # conta o mesmo obito duas vezes; longa demais engole o seguinte.
        self._ultimo_morto: int | None = None

    @staticmethod
    def veredito(entidade: dict | None) -> bool | None:
        """`True` morreu, `False` vivo, `None` nao sei.

        `hp == 0` E MORTE, e a struct ja foi validada por quem leu
        (`Memory.alvo_atual` recusa `hp` fora de `0..max_hp`). Confirmar por N
        amostras foi tentado no APP e ficou PIOR -- o cadaver deixava de ser
        reconhecido na primeira pergunta da volta.

        A fase 1 do boss NAO zera (para em `hp=1` e some, nascendo a fase 2 como
        entidade nova). Nao e caso a tratar: o boss nunca foi dado por morto por
        HP.
        """
        if entidade is None:
            return None
        hp = entidade.get("hp")
        if hp is None:
            return None
        return hp <= 0

    def ja_contei(self, ident: int | None) -> bool:
        """Esta morte ja foi contada? Nao mexe em nada."""
        return bool(ident) and self._ultimo_morto == ident

    def contar(self, ident: int | None) -> bool:
        """Marca a morte deste alvo. `True` = e a PRIMEIRA vez.

        Quem chama usa o `False` para calar o log e o contador -- nunca para
        mudar o VEREDITO. Travar o veredito junto faria o portao "alvo vivo,
        nao mexe" reler o cadaver ja contado como se fosse alvo, e bloquear o
        TAB nele.
        """
        if self.ja_contei(ident):
            return False
        self._ultimo_morto = ident
        return True

    def esquecer(self) -> None:
        """Zera a trava. Usado quando o ecossistema recomeca do zero."""
        self._ultimo_morto = None


@dataclass(frozen=True)
class AlvoInfo:
    """O alvo neste instante. `None` em qualquer campo é "não sei", nunca zero."""

    target_id: int | None           # 0 = sem alvo; None = não consegui ler
    mudou: bool                     # o id é diferente do da leitura anterior
    barra: LeituraDaBarra | None    # None = não consegui ler a barra
    quadro: BGRFrame | None         # a captura desta leitura, para reuso
    timestamp: float
    entidade: dict | None = None    # o alvo lido da MEMÓRIA; None = não achei

    @property
    def tem_alvo(self) -> bool:
        return self.target_id not in (0, None)

    @property
    def pela_memoria(self) -> bool:
        """A memória respondeu por este alvo?

        Quando responde, ela é a fonte de TUDO: identidade, HP, nível e
        posição. A tela nem é capturada.
        """
        return self.entidade is not None

    @property
    def fonte(self) -> str:
        return "memoria" if self.pela_memoria else "tela"

    @property
    def nome(self) -> str | None:
        """O nome do alvo, ou `None`. SÓ a memória responde isto.

        Ele voltou a existir em 25/08/2026. O `USAR_PORTAO_DE_NOME` tinha sido
        aposentado porque *"não há fonte de nome hoje"* -- e agora há.
        """
        return None if self.entidade is None else self.entidade["nome"]

    @property
    def hp_pct(self) -> float | None:
        """Fração 0..1 de vida do alvo, ou `None`.

        MEMÓRIA PRIMEIRO. A barra desenhada só responde quando a memória não
        achou a entidade -- ela atrasa (medido: 23,1% na tela contra 6% na
        memória, no mesmo instante) e não sabe dizer que atrasou.
        """
        if self.entidade is not None:
            return self.entidade["pct"]
        return None if self.barra is None else self.barra.vida

    @property
    def vivo_na_tela(self) -> bool:
        hp = self.hp_pct
        return hp is not None and hp > LIMIAR_VIDA_TELA

    @property
    def vale_olhar_o_marcador(self) -> bool:
        """O `EnemyDead.png` ainda tem serventia nesta leitura?

        NÃO, quando a memória respondeu: `hp == 0` é morte exata, e consultar um
        template com falso positivo medido (0,955-0,971 com o mob VIVO) só
        poderia piorar uma resposta que já está certa.
        """
        if self.pela_memoria:
            return False
        hp = self.hp_pct
        return hp is not None and hp <= FAIXA_PARA_OLHAR_O_MARCADOR


class TargetHybrid:
    """Lê o alvo. Não decide nada, não aperta tecla, não guarda janela.

    Guarda só o que precisa atravessar leituras: o último id (para saber que
    trocou), a última vida (para o log sair por MUDANÇA) e o handle do processo.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger or _logger
        # UM `Memory`, não um `pymem` cru: a leitura do alvo por memória mora
        # em `Memory.alvo_atual`, e ter dois caminhos de leitura era ter dois
        # mapas de offsets para manter em sincronia.
        self._memoria: Memory | None = None
        self._pid_aberto: int | None = None
        self._ultimo_id: int | None = None
        self._ultima_vida: float | None = None
        self._ultimo_eco = 0.0
        self._avisou_sem_barra = False

    # -- memória ---------------------------------------------------------

    def _processo(self, pid: int) -> Memory | None:
        """O `Memory` daquele PID, reaberto quando o PID muda.

        RELOGIN TROCA O PID. Guardar o handle da construção era ler a memória de
        um processo morto para sempre, em silêncio -- ver o cabeçalho.
        """
        if self._memoria is not None and self._pid_aberto == pid:
            return self._memoria
        self.fechar()
        try:
            memoria = Memory(pid)
        except Exception as exc:
            self._log.debug("Não consegui abrir o processo %s: %s", pid, exc)
            return None
        self._memoria, self._pid_aberto = memoria, pid
        return memoria

    def id_do_alvo(self, pid: int) -> int | None:
        """Só o id, sem tocar na tela. ~1 µs.

        É esta a leitura que vale FORA da luta: dá para saber que existe alvo e
        que ele trocou sem pagar captura nenhuma.
        """
        memoria = self._processo(pid)
        return None if memoria is None else memoria.id_do_alvo()

    def entidade_do_alvo(self, pid: int) -> dict | None:
        """O alvo inteiro, da MEMÓRIA. `None` = sem alvo ou não achei.

        Nome, HP exato, nível e posição -- tudo de uma leitura, sem captura.
        Ver `Memory.alvo_atual` para a medição que pôs isto na frente da tela.
        """
        memoria = self._processo(pid)
        return None if memoria is None else memoria.alvo_atual()

    # -- a leitura completa ----------------------------------------------

    def ler(self, pid: int, hwnd: int, *, com_tela: bool = True) -> AlvoInfo:
        """O alvo agora. `com_tela=False` lê só o id.

        UMA CAPTURA, no máximo, e só quando `com_tela`. O quadro volta dentro do
        `AlvoInfo` para quem precisar do `EnemyDead.png` usar o MESMO instante --
        duas capturas em instantes diferentes fazem a barra e o marcador
        discordarem sobre o mesmo momento.
        """
        agora = time.time()
        entidade = self.entidade_do_alvo(pid)
        target_id = (entidade["id"] if entidade is not None
                     else self.id_do_alvo(pid))
        mudou = target_id != self._ultimo_id
        if mudou:
            self._ultimo_id = target_id
            self._ultima_vida = None
            self._avisou_sem_barra = False

        if not com_tela or target_id in (0, None):
            return AlvoInfo(target_id=target_id, mudou=mudou, barra=None,
                            quadro=None, timestamp=agora, entidade=entidade)

        # A MEMÓRIA RESPONDEU: não captura nada.
        #
        # É o ganho maior desta virada, e não é só velocidade. A captura era a
        # origem de todos os erros CALADOS desta área -- o piso de 0,7% com o
        # mob morto, a barra amarela sobreposta à vermelha, o marcador com falso
        # positivo, a régua que devolvia float confiante medindo outra coisa. Um
        # `hp` inteiro vindo da struct não tem nenhum desses modos de falha.
        if entidade is not None:
            return AlvoInfo(target_id=target_id, mudou=mudou, barra=None,
                            quadro=None, timestamp=agora, entidade=entidade)

        quadro = None
        barra = None
        try:
            quadro = vision.capture_window(hwnd)
            if quadro is not None and not vision.frame_is_blank(quadro):
                barra = vision.ler_barra_do_alvo(quadro)
        except Exception as exc:
            self._log.debug("Falha ao ler a barra do alvo: %s", exc)

        return AlvoInfo(target_id=target_id, mudou=mudou, barra=barra,
                        quadro=quadro, timestamp=agora, entidade=None)

    def vida_pela_tela(self, hwnd: int) -> float | None:
        """Só a barra desenhada: fração 0..1, ou `None` = não consegui ler.

        =================================================================
        PECA COMPARTILHADA -- o modo APP passou a usar a tela em 26/08/2026
        =================================================================

        **Quem usa:** o `ler()` daqui (caminho do BC) e, injetada pelo
        supervisor, a segunda porta do `bot/app/executor.py`. Mexer aqui mexe
        nos dois.

        **Por que ela existe separada do `ler()`:** o `ler()` guarda estado
        (`_ultimo_id`, `_ultima_vida`) para saber que o alvo TROCOU. Chamar
        `ler()` de novo só para pegar a barra estragaria esse estado -- o
        segundo chamador veria `mudou=False` num alvo que mudou. Aqui não se
        guarda nada: uma captura, uma leitura, e pronto.

        **CUSTA UMA CAPTURA DE JANELA.** Quem chama controla a cadência -- ver
        `INTERVALO_MINIMO_DA_TELA` no executor do APP, e `VISUAL_CHECK_SECONDS`
        no watchdog. No caminho do bot isto nunca é chamado em laço apertado.
        """
        try:
            quadro = vision.capture_window(hwnd)
        except Exception as exc:
            self._log.debug("Falha ao capturar para a barra do alvo: %s", exc)
            return None
        if quadro is None or vision.frame_is_blank(quadro):
            return None
        try:
            barra = vision.ler_barra_do_alvo(quadro)
        except Exception as exc:
            self._log.debug("Falha ao ler a barra do alvo: %s", exc)
            return None
        # `None` é "NÃO SEI", e a régua da barra sabe dizer isso: sem as cores na
        # faixa, ela devolve `None` em vez de um float confiante.
        return None if barra is None else barra.vida

    # -- o log -----------------------------------------------------------

    def registrar(self, info: AlvoInfo, *, segundos_entre_ecos: float = 2.0,
                  segunda_fase: bool = False) -> None:
        """A linha de vida do alvo, por MUDANÇA, com eco quando parada.

        Pedido do usuário em 25/08/2026: *"pela tela de log do bot eu não estou
        vendo a % de vida do mob, quero poder ir vendo a cada alteração"*.

        Por MUDANÇA e não por leitura porque a leitura roda a cada 0,15 s: uma
        linha por leitura são ~250 por luta, e o arquivo de texto guarda 500 no
        total -- uma fase sozinha empurraria o resto para fora.
        """
        if info.target_id in (0, None):
            return
        vida = info.hp_pct
        agora = info.timestamp

        if vida is None:
            # AUSÊNCIA DE BARRA É DITA EM VOZ ALTA, uma vez por alvo. Sem isso,
            # "não consegui ler" e "o mob está cheio" ficam iguais no log -- e
            # foi exatamente essa confusão que escondeu a régua quebrada.
            if not self._avisou_sem_barra:
                self._avisou_sem_barra = True
                self._log.info(
                    "ALVO #%s  --  não consegui ler a barra (o quadro do alvo "
                    "não está onde deveria)", info.target_id)
            return

        # O QUE VAI NA TELA é o TOTAL quando o boss está na fase 2, e a barra da
        # vez no resto. O delta acompanha esse mesmo número -- comparar a barra
        # da vez fazia a vida "subir 54%" no instante em que a amarela acaba e a
        # vermelha assume, que é justamente quando ela não subiu nada.
        mostrado = self._valor_mostrado(info, segunda_fase)
        mudou_a_vida = (self._ultima_vida is None
                        or abs(mostrado - self._ultima_vida) >= 0.005)
        if not (info.mudou or mudou_a_vida
                or agora - self._ultimo_eco >= segundos_entre_ecos):
            return

        anterior = self._ultima_vida
        self._ultima_vida = mostrado
        self._ultimo_eco = agora
        self._log.info("%s", self.linha_do_log(info, anterior, segunda_fase))

    @staticmethod
    def _valor_mostrado(info: AlvoInfo, segunda_fase: bool) -> float:
        """A vida que o log mostra.

        MEMÓRIA PRIMEIRO, e aqui ela é simples: `hp/max_hp` **já é o total**.
        A conta de somar as duas barras (`total_do_boss`) existe só porque a
        TELA desenha a amarela por cima da vermelha e nenhuma das duas sozinha
        é a vida do boss. A struct não tem esse problema -- na fase 2 ela leu
        `75/100` enquanto a barra lia 50,0%.

        DEFEITO QUE ISTO CONSERTA: com a virada para memória, `info.barra` é
        `None` no caminho normal, e a versão anterior devolvia `0.0` nesse
        caso. O log passaria a mostrar 0% para todo alvo vivo -- e o `registrar`
        acharia que a vida tinha despencado a cada leitura.
        """
        if info.entidade is not None:
            return info.entidade["pct"]
        barra = info.barra
        if barra is None:
            return 0.0
        if barra.na_segunda_fase or segunda_fase:
            return barra.total_do_boss(True)
        return barra.vida

    def linha_do_log(self, info: AlvoInfo, anterior: float | None,
                     segunda_fase: bool) -> str:
        """A linha, montada. Separada do `registrar` para o teste poder olhá-la."""
        barra = info.barra
        mostrado = self._valor_mostrado(info, segunda_fase)
        cheios = int(round(mostrado * CASAS_DO_DESENHO))
        desenho = "[" + "#" * cheios + "-" * (CASAS_DO_DESENHO - cheios) + "]"

        # PELA MEMÓRIA: nome e HP exato, que é o que o usuário quer ver
        # correndo na tela de log. `8/100` diz mais do que `8.0%`, e o nome
        # responde "estou batendo no quê?" sem ninguém precisar olhar o jogo.
        if info.entidade is not None:
            e = info.entidade
            quem = e["nome"] or f"#{info.target_id}"
            corpo = (f"{quem}  {mostrado * 100:5.1f}%  {desenho}  "
                     f"({e['hp']}/{e['max_hp']}" +
                     (f", nv{e['nivel']}" if e["nivel"] else "") + ")")
            if info.mudou:
                cauda = "alvo novo"
            elif anterior is None:
                cauda = ""
            else:
                cauda = f"{(mostrado - anterior) * 100:+.0f}%"
            return f"ALVO {corpo}  {cauda}".rstrip()

        if barra is not None and barra.na_segunda_fase:
            corpo = (f"{mostrado * 100:5.1f}% total  {desenho}  "
                     f"(amarela {barra.amarelo * 100:.0f}%)  fase 2")
        elif segunda_fase and barra is not None:
            corpo = (f"{mostrado * 100:5.1f}% total  {desenho}  "
                     f"(vermelha {barra.vermelho * 100:.0f}%)  fase 2")
        else:
            corpo = f"{mostrado * 100:5.1f}%  {desenho}"

        if info.mudou:
            cauda = "alvo novo"
        elif anterior is None:
            cauda = ""
        else:
            cauda = f"{(mostrado - anterior) * 100:+.0f}%"

        # O BRUTO ENTRA QUANDO A BARRA ESTÁ QUASE VAZIA. É o número que separa
        # "morreu" de "sobrou um fio de vida", e é ele que vai permitir descer o
        # limiar de 2% para 1% com medição atrás em vez de tentativa.
        if barra is not None and 0.0 < barra.vida <= FAIXA_PARA_OLHAR_O_MARCADOR:
            cauda = f"{cauda}  (bruto {barra.vida * 100:.1f}%, "
            cauda += f"{barra.primeiro_x}-{barra.ultimo_x} de {barra.colunas})"

        return f"ALVO #{info.target_id}  {corpo}  {cauda}".rstrip()

    def fechar(self) -> None:
        if self._memoria is not None:
            try:
                self._memoria.close()
            except Exception:
                pass
        self._memoria = None
        self._pid_aberto = None


# ===========================================================================
# QUANDO O ID RESPONDE E A ENTIDADE NAO APARECE -- a investigacao
# ===========================================================================
#
# Relato do usuario em 26/08/2026, com o `9-VIGIAR-COMBATE` na frente:
#
#     *"Tem alguma coisa fazendo nem sempre ler o target. Eu vejo que o value
#      do 0115CB80 altera, mas nao acha o target no array -- mas em algum lugar
#      da memoria do jogo ele esta, PQ O MOB EXISTE, A CHAVE EXISTE."*
#
# Ele esta certo, e a suspeita tem aritmetica atras dela. Os SETE "slots de
# selecao visual" descobertos em 21/08/2026 (`0x0107C714`, `0x0107C79C`,
# `0x0107C8FC`, `0x0107C71C`, `0x0107C948`, `0x0107C758`, `0x0107C998`) caem
# TODOS dentro da janela que `_procurar_entidade` varre --
# `ADDR_ENTITY_SCAN_BASE` (0x0107C6B0) mais `LIMITE_DE_ENTIDADES * 4` bytes
# termina em 0x0107CEB0. Eles ocupam os slots 25, 27, 42, 59, 147, 166 e 186
# dos 512.
#
# Isso levanta a hipotese de que a tal "array de entidades" **nao e uma array
# de entidades**: e uma regiao estatica que contem, entre outras coisas,
# ponteiros para entidades RECENTEMENTE SELECIONADAS. Se for isso, achar o mob
# ali e sorte de ele ter passado pela selecao -- e o log do usuario bate: os
# mobs que aparecem inteiros sao os engajados, e o TAB ciclando produz quase so
# ausencias.
#
# ISTO AQUI NAO DECIDE NADA E NAO CONSERTA NADA. E instrumento: ele responde
# ONDE o id vive, para a hipotese virar medicao em vez de continuar hipotese.
# A regra do projeto e essa -- nada sobre o alvo e afirmado sem linha de log
# atras.
#
# CUSTA CARO: varre a memoria do processo inteiro. Nunca no caminho do bot; so
# em ferramenta, e uma vez por id.

# Quantos endereços mostrar por id. Mais que isto vira parede de texto.
MAXIMO_DE_ACHADOS = 12


def _esta_na_janela_varrida(memoria: Memory, obj: int) -> int | None:
    """Em que slot da janela varrida existe um ponteiro para `obj`? `None`=nenhum.

    É a pergunta que separa "a entidade não existe" de "a entidade existe e nós
    estamos procurando no lugar errado" -- e as duas pedem consertos opostos.
    """
    for i in range(LIMITE_DE_ENTIDADES):
        if memoria.read_uint(ADDR_ENTITY_SCAN_BASE + i * 4) == obj:
            return i
    return None


def investigar_alvo_perdido(memoria: Memory, alvo_id: int) -> list[str]:
    """ONDE esse id vive? Linhas prontas para uma pessoa ler.

    Chamada só por ferramenta, e só quando o id responde mas a entidade não
    aparece. **Varre o processo inteiro** -- não é para o caminho do bot.
    """
    linhas: list[str] = [
        f"investigando o id {alvo_id} (0x{alvo_id & 0xFFFFFFFF:08X}) "
        "na memória do processo..."]
    try:
        achados = memoria.pm.pattern_scan_all(
            struct.pack("<i", alvo_id), return_multiple=True) or []
    except Exception as exc:
        linhas.append(f"  não consegui varrer: {exc}")
        return linhas

    if not achados:
        linhas.append("  o id NÃO APARECE em lugar nenhum da memória — então "
                      "ele não é id de entidade nenhuma, e o campo do alvo "
                      "está guardando outra coisa.")
        return linhas

    linhas.append(f"  o id aparece em {len(achados)} lugar(es).")
    entidades = 0
    for endereco in list(achados)[:MAXIMO_DE_ACHADOS]:
        # A ENTIDADE GUARDA O PRÓPRIO ID EM `+0x8`. Se este endereço for esse
        # campo, a struct começa 8 bytes antes.
        candidato = parece_entidade(memoria, endereco - OFF_ENTITY_ID)
        if candidato is None:
            continue
        entidades += 1
        slot = _esta_na_janela_varrida(memoria, candidato["obj"])
        onde = ("NÃO está na janela varrida" if slot is None
                else f"está no slot {slot} da janela varrida")
        linhas.append(
            f"  0x{candidato['obj']:08X}  {candidato['nome'] or '?'}"
            f"  nv{candidato['nivel']}  hp={candidato['hp']}/"
            f"{candidato['max_hp']}  — {onde}")

    if not entidades:
        linhas.append("  nenhum desses endereços tem cara de entidade — o id "
                      "aparece, mas não como campo `+0x8` de uma struct.")
    else:
        linhas.append(
            "  se a entidade EXISTE e NÃO está na janela varrida, o defeito "
            "não é a leitura do alvo: é o lugar onde procuramos. Ver o bloco "
            "acima sobre os slots de seleção visual.")
    return linhas
