"""
Onde o personagem está — decidido por duas fontes independentes.

=========================================================================
O PROBLEMA QUE ESTE MÓDULO RESOLVE
=========================================================================

O nome do lugar falha de DUAS formas, e elas exigem tratamentos diferentes.

FORMA 1 -- O NOME NÃO LÊ. Duas vezes em produção o campo parou de ser lido no
personagem que rodava a BC, e só voltou depois de FECHAR E REABRIR o jogo.
Reabrir custa horas de fila -- então "reabrir o jogo" não é solução, é o
problema.

FORMA 2 -- O NOME LÊ, E LÊ ERRADO. Descoberta depois, e pior que a primeira: ao
sair da instância o cliente às vezes não reescreve o campo, que fica preso na
última área de dentro. O personagem está em (1395,-629), na entrada em Ghost Din
Woods, e a memória insiste em 'Secret Cemetery'. Oito episódios em dois dias de
diário. O bot, que dava prioridade absoluta ao nome lido, concluía que estava no
covil do boss e ia "até os guardas" parado do lado de fora -- ou reclicava no NPC
de saída para sempre. Só uma troca de mapa de verdade reescreve o campo, e é por
isso que passar em Stone City "desbugava".

A forma 2 não se resolve procurando um ponteiro melhor, e nem dá para forçar o
cliente a reescrever o campo de fora. Resolve-se DESMENTINDO o nome com a
coordenada, que é a leitura que nunca falhou -- ver o veto em
`_decidir_se_esta_na_cave`. E a boa notícia é que o conserto se dá sozinho: uma
vez que o bot aceita que está fora, ele entra na cave de novo, e a carga do mapa
reescreve o nome.

Nos dois casos a resposta é a mesma: o bot PARA DE DEPENDER de uma única fonte.

  FONTE 1 -- o nome do lugar na memória. Precisa, dá o nome exato, e é a que
             falha.
  FONTE 2 -- a COORDENADA. Nunca falhou em nenhum log: HP e posição continuaram
             legíveis mesmo nas duas ocorrências do bug. E como o caminho
             inteiro da cave está medido em `mapa_bc.py`, a coordenada diz a
             área com precisão suficiente para decidir o que fazer.

A fonte 2 sozinha tem um limite honesto: coordenada de jogo não é única no mundo.
Por isso ela é combinada com a ÚLTIMA TRANSIÇÃO CONHECIDA -- o bot sabe que
acabou de clicar em "Enter Bewitcher Cave" estando em (1395,-635), e que a
posição saltou para (423,53); isso é entrada na cave, não coincidência de
coordenada.

=========================================================================
E O REGISTRO
=========================================================================

Toda mudança e toda falha vão para `logs\\localizacao.log`, com a posição e o
rastro da cadeia de ponteiros. Havia um caso em que o bot não fez nada e não
gerou log, e sem registro o diagnóstico virou adivinhação -- este arquivo existe
para que isso não se repita com o ponteiro de localização.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ...core import diario
from ...core.lugares import LUGAR_FORA_DA_CAVE, e_dentro_da_cave
from . import mapa_bc

# Cadência do batimento no diário. Uma linha a cada meio minuto dá uma trilha
# contínua da run inteira sem inflar o arquivo -- e é ela que vai mostrar o
# instante exato em que a leitura para de funcionar.
INTERVALO_DO_BATIMENTO = 15.0

# Tempo com o nome ilegível a partir do qual o bot passa a tratar a fonte de
# memória como quebrada e opera pela coordenada. Curto de propósito: parar o
# farm porque uma string não leu seria desperdiçar a run.
SEGUNDOS_PARA_DESCONFIAR = 3.0

# Salto de posição que caracteriza teleporte (entrada na cave, portal do altar,
# pedra de retorno). Abaixo disso é caminhada.
SALTO_DE_TELEPORTE = 150.0

# Quão perto da coordenada de chegada da cave conta como "entrei".
RAIO_DA_CHEGADA = 40.0


@dataclass
class Situacao:
    """Fotografia de onde o personagem está e de quanto confiar nisso."""

    posicao: tuple[int, int] | None = None
    local: str | None = None          # melhor nome disponível
    area: str | None = None           # sub-área da cave, pela coordenada
    fonte: str = "desconhecida"          # memoria | coordenada | cache
    local_lido: str | None = None     # o que a memória devolveu agora
    dentro_da_cave: bool = False
    memoria_ok: bool = False             # a memória respondeu E a resposta serve
    segundos_sem_nome: float = 0.0
    divergencia: bool = False            # memória e coordenada discordam
    nome_preso: bool = False             # a memória respondeu, e respondeu ERRADO

    @property
    def confiavel(self) -> bool:
        """Dá para decidir o que fazer com esta informação?

        Coordenada legível já basta: é ela que sustenta a rota. O nome do lugar
        é confirmação, não requisito -- tratá-lo como requisito é o que
        travaria o bot durante o bug do ponteiro.
        """
        return self.posicao is not None

    def resumo(self) -> str:
        return mapa_bc.descrever(self.posicao, self.local)


@dataclass
class _Cache:
    nome: str | None = None
    quando: float = 0.0
    posicao: tuple[int, int] | None = None


class RastreadorDeLocal:
    """Mantém, atualiza e registra onde o personagem está.

    Um por conta. É consultado a todo momento pela rotina -- a ideia é que o bot
    nunca execute um passo sem antes conferir se ele faz sentido de onde ele
    está.
    """

    def __init__(self, memory, log, conta: str = "") -> None:
        self.memory = memory
        self.log = log
        self.conta = conta
        self.situacao = Situacao()

        self._cache = _Cache()
        self._sem_nome_desde: float = 0.0
        self._ultimo_batimento: float = 0.0
        self._ultimo_registrado: str | None = None
        self._falha_registrada = False
        self._esperado: str | None = None
        # Episódio de nome preso em curso. Separado do cronômetro de nome
        # ilegível porque são falhas diferentes: uma é o campo em branco, a outra
        # é o campo com conteúdo velho.
        self._preso_desde: float = 0.0
        self._preso_registrado = False

    # ==================================================================
    # Expectativa
    # ==================================================================

    def esperar(self, local: str | None) -> None:
        """Declara onde o bot ACREDITA que está ou deveria estar.

        A rotina chama isto antes de cada etapa. Serve para dois fins: o log
        passa a dizer "esperava Ghost Din Woods, estou em Stone City" em vez de
        só "estou em Stone City", e a própria rotina pode consultar
        `fora_do_esperado()` para se corrigir antes de executar um passo que não
        faz sentido no lugar em que ela está.
        """
        if local != self._esperado:
            self._esperado = local

    def fora_do_esperado(self) -> bool:
        """A situação atual contradiz o que a rotina esperava?

        Só responde True quando há informação suficiente para afirmar isso. Sem
        nome de lugar E sem área por coordenada, a resposta é False: acusar
        divergência sem base faria o bot se "corrigir" para lugar nenhum.
        """
        if self._esperado is None:
            return False
        atual = self.situacao.local or self.situacao.area
        if atual is None:
            return False
        return atual != self._esperado

    # ==================================================================
    # Atualização
    # ==================================================================

    def atualizar(self, marco: str | None = None) -> Situacao:
        """Relê posição e nome do lugar, decide onde está e registra.

        `marco` força uma linha no diário com um rótulo -- usado nos momentos em
        que a localização decide o passo seguinte: antes de entrar na cave,
        depois de entrar, antes do Altar Stone, antes do boss, depois de sair,
        antes de vender.
        """
        agora = time.time()
        m = self.memory

        posicao = m.position()
        detalhe = m.location_detail()
        nome_lido = detalhe.get("nome")  # type: ignore[assignment]

        # ==============================================================
        # O NOME PRESO -- a segunda forma de falha, que este módulo não previa
        # ==============================================================
        #
        # O módulo foi escrito para o nome ILEGÍVEL (None). O log mostrou uma
        # forma pior: o nome LÊ, e lê ERRADO. Ao sair da instância o cliente às
        # vezes não reescreve o campo, que fica preso na última área de DENTRO --
        # 'Secret Cemetery', porque é a última que ele escreveu antes da saída.
        #
        # É ocasional, não sistemático. Na coordenada da entrada o campo leu
        # 'Ghost Din Woods' 149 vezes contra 23 presas em 'Secret Cemetery'. E não
        # se cura sozinho: só uma troca de mapa de verdade reescreve o campo, que
        # é por que passar em Stone City "desbugava".
        #
        # Um nome lido valia mais que qualquer outra coisa na decisão logo abaixo,
        # e o resultado está no diário: parado em (1395,-629), do lado de fora, o
        # bot foi "até os guardas", fez "travessia da cave" e "curou dentro da
        # cave". Oito episódios em dois dias.
        #
        # A contradição é detectável sem ambiguidade porque a coordenada da
        # entrada está a quase mil unidades da caixa da cave. Ver
        # `mapa_bc.posicao_esta_fora_da_cave` para o porquê de a implicação valer
        # só neste sentido.
        nome_preso = bool(
            nome_lido
            and e_dentro_da_cave(nome_lido)  # type: ignore[arg-type]
            and mapa_bc.posicao_esta_fora_da_cave(posicao)
        )

        nova = Situacao(
            posicao=posicao,
            local_lido=nome_lido,          # type: ignore[arg-type]
            memoria_ok=bool(nome_lido) and not nome_preso,
            area=mapa_bc.area_da_posicao(posicao),
            nome_preso=nome_preso,
        )

        if nome_preso:
            # NÃO entra no cache. Cachear um nome preso propagaria a mentira para
            # depois -- `_deduzir` confia no cache para decidir se uma coordenada
            # ambígua conta como área da cave, e com o cache envenenado o veto da
            # coordenada seria contornado pelo próprio bot.
            self._registrar_nome_preso(nova, agora)

            # O X GRANDE DÁ O NOME, e não só o desmentido.
            #
            # Desmentir a memória deixava `local` em None, e None obriga cada
            # consumidor a decidir o que fazer sem informação. O X resolve isso:
            # acima de 500 o único lugar da rotina é Ghost Din Woods -- é para lá
            # que sair da instância devolve o personagem, e é a coordenada da
            # entrada. Então a resposta não é "não sei", é "estou em Ghost Din
            # Woods", que é o que a rotina precisa ouvir para ir entrar de novo.
            #
            # Só o X autoriza isso. Sair da CAIXA pelo Y (Stone City, por exemplo)
            # diz que não estou na cave, mas não diz onde estou -- e nesse caso
            # inventar um nome seria pior que admitir a ignorância.
            if mapa_bc.x_contradiz_a_cave(posicao):
                nova.local = LUGAR_FORA_DA_CAVE
                nova.fonte = "coordenada (nome preso, X fora da cave)"
            else:
                nova.local = nova.area
                nova.fonte = "coordenada (nome preso)"
        elif nome_lido:
            # A memória respondeu: ela manda. Zera o cronômetro de falha.
            if self._falha_registrada:
                diario.localizacao().info(
                    "%s | RECUPERADO | o nome do lugar voltou a ser lido "
                    "depois de %.0fs | nome=%r pos=%s",
                    self.conta, agora - self._sem_nome_desde, nome_lido, posicao,
                )
                self.log.info(
                    "Localização voltou a ser legível depois de %.0fs: %r",
                    agora - self._sem_nome_desde, nome_lido,
                )
            self._sem_nome_desde = 0.0
            self._falha_registrada = False
            self._fim_do_nome_preso(nome_lido, posicao, agora)  # type: ignore[arg-type]
            nova.local = nome_lido          # type: ignore[assignment]
            nova.fonte = "memoria"
            self._cache = _Cache(nome_lido, agora, posicao)  # type: ignore[arg-type]
        else:
            if self._sem_nome_desde == 0.0:
                self._sem_nome_desde = agora
            nova.segundos_sem_nome = agora - self._sem_nome_desde
            self._registrar_falha(detalhe, posicao, nova.segundos_sem_nome)
            self._fim_do_nome_preso(None, posicao, agora)
            nova.local, nova.fonte = self._deduzir(posicao, agora)

        nova.dentro_da_cave = self._decidir_se_esta_na_cave(nova)
        nova.divergencia = bool(
            nova.local_lido and nova.area and nova.local_lido != nova.area
        )

        self.situacao = nova
        self._registrar(nova, marco, agora)
        return nova

    # ==================================================================
    # Dedução por coordenada
    # ==================================================================

    def _deduzir(
        self,
        posicao: tuple[int, int] | None,
        agora: float,
    ) -> tuple[str | None, str]:
        """Nome do lugar sem a memória: coordenada primeiro, cache depois.

        A REGRA DO X VALE AQUI TAMBÉM. Sem ela, um nome de cave guardado no cache
        seria devolvido enquanto o personagem está em Ghost Din Woods -- a mesma
        mentira do nome preso, só que vinda do cache em vez da memória. As duas
        formas de falha precisam responder a mesma coisa.
        """
        if mapa_bc.x_contradiz_a_cave(posicao):
            return LUGAR_FORA_DA_CAVE, "coordenada (X fora da cave)"

        area = mapa_bc.area_da_posicao(posicao)
        if area is not None:
            # A coordenada bate com um waypoint conhecido da cave. Só vale como
            # resposta se o bot tem motivo para crer que está na cave -- ou
            # porque a última leitura boa era de dentro dela, ou porque a
            # posição está na caixa da cave e o cache já era de lá.
            if e_dentro_da_cave(self._cache.nome) or self._cache.nome is None:
                return area, "coordenada"
            # Última leitura boa era de FORA: pode ser coincidência de
            # coordenada. Prefere o cache e deixa o log mostrar o conflito.
            return self._cache.nome, "cache"

        if self._cache.nome and agora - self._cache.quando < 600.0:
            return self._cache.nome, "cache"
        return None, "desconhecida"

    def _decidir_se_esta_na_cave(self, s: Situacao) -> bool:
        """Está dentro da instância?

        Ordem de confiança:
          0. VETO DA COORDENADA: se a posição está claramente fora da caixa da
             cave, não está dentro -- e nenhum nome lido muda isso.
          1. Nome lido da memória pertence ao catálogo de áreas da cave.
          2. A coordenada bate com um waypoint da cave E o histórico é
             compatível (a última posição conhecida também era da cave, ou
             houve um salto de teleporte para a coordenada de chegada).
          3. Cache recente de dentro da cave, com a posição ainda na caixa.
        """
        # O veto vem ANTES do nome porque a implicação é lógica, não estatística:
        # a caixa contém a instância inteira, logo estar longe dela prova que não
        # está dentro. E a coordenada é a única leitura que não falhou em nenhum
        # log -- inclusive nos episódios de nome preso, em que ela era o que
        # estava certo enquanto o nome mentia.
        if mapa_bc.posicao_esta_fora_da_cave(s.posicao):
            return False

        if s.local_lido:
            return e_dentro_da_cave(s.local_lido)

        if s.area is not None and e_dentro_da_cave(s.area):
            return True

        if e_dentro_da_cave(self._cache.nome):
            return mapa_bc.posicao_esta_na_caixa_da_cave(s.posicao)

        return False

    # ==================================================================
    # Registro
    # ==================================================================

    def _registrar_nome_preso(self, s: Situacao, agora: float) -> None:
        """Grava UMA linha por episódio de nome preso, não por leitura.

        A rotina consulta a localização a cada 0,12 s; uma linha por leitura
        afogaria o arquivo. O que interessa é o instante em que a contradição
        aparece e o que cada fonte dizia naquele instante -- é essa linha que, nos
        oito episódios do diário, teria dito de imediato o que levou horas para
        ser encontrado comparando posições no log.
        """
        if self._preso_desde == 0.0:
            self._preso_desde = agora
        if self._preso_registrado:
            return
        self._preso_registrado = True

        diario.localizacao().warning(
            "%s | NOME PRESO | a memória diz %r mas a coordenada %s está fora da "
            "cave | vale a coordenada: NÃO estou na instância | area_por_coordenada=%r",
            self.conta, s.local_lido, s.posicao, s.area,
        )
        self.log.warning(
            "O nome do lugar está PRESO em %r, mas estou em %s — fora da cave. "
            "O cliente não reescreveu o campo ao sair da instância. Vale a "
            "coordenada; entrar na cave de novo reescreve o nome.",
            s.local_lido, s.posicao,
        )
        diario.registrar_evento(
            self.conta, "nome-preso",
            f"memória={s.local_lido!r} contradita pela coordenada",
            s.posicao, s.local_lido,
        )

    def _fim_do_nome_preso(
        self,
        nome_lido: str | None,
        posicao: tuple[int, int] | None,
        agora: float,
    ) -> None:
        """Fecha o episódio quando a contradição deixa de existir."""
        if not self._preso_registrado:
            self._preso_desde = 0.0
            return
        duracao = agora - self._preso_desde
        self._preso_desde = 0.0
        self._preso_registrado = False
        if nome_lido:
            diario.localizacao().info(
                "%s | NOME LIBERADO | voltou a acompanhar a posição depois de "
                "%.0fs | nome=%r pos=%s",
                self.conta, duracao, nome_lido, posicao,
            )
            self.log.info(
                "O nome do lugar destravou depois de %.0fs: agora lê %r em %s",
                duracao, nome_lido, posicao,
            )
        else:
            diario.localizacao().info(
                "%s | NOME LIBERADO | o nome parou de contradizer a posição "
                "depois de %.0fs, mas agora está ilegível | pos=%s",
                self.conta, duracao, posicao,
            )

    def _registrar_falha(
        self,
        detalhe: dict,
        posicao: tuple[int, int] | None,
        segundos: float,
    ) -> None:
        """Grava UMA linha detalhada por episódio de falha, não por leitura.

        Uma linha por leitura encheria o arquivo em segundos (a rotina consulta
        a posição a cada 0,12 s) e afogaria justamente a informação útil. O que
        importa é o INÍCIO do episódio, com o rastro completo da cadeia, e
        depois o batimento periódico mostrando que continua falhando.
        """
        if self._falha_registrada:
            return
        if segundos < SEGUNDOS_PARA_DESCONFIAR:
            return
        self._falha_registrada = True

        brutos = detalhe.get("brutos") or {}
        diario.localizacao().warning(
            "%s | FALHA | nome do lugar ilegível há %.0fs | pos=%s | "
            "ponteiro=%s | reconhecimento=%s | leituras=%s | ultimo_bom=%r (%.0fs atras, pos=%s)",
            self.conta, segundos, posicao, detalhe.get("ponteiro"),
            detalhe.get("reconhecimento"), brutos,
            self._cache.nome,
            time.time() - self._cache.quando if self._cache.quando else -1,
            self._cache.posicao,
        )
        self.log.warning(
            "Não consigo LER o nome do lugar há %.0fs (ponteiro %s, leituras %s). "
            "Sigo pela coordenada: %s. Detalhe em logs\\localizacao.log.",
            segundos, detalhe.get("ponteiro"), brutos,
            mapa_bc.descrever(posicao, None),
        )
        diario.registrar_evento(
            self.conta, "localizacao-perdida",
            f"ponteiro={detalhe.get('ponteiro')} leituras={brutos}",
            posicao, self._cache.nome,
        )

    def _registrar(self, s: Situacao, marco: str | None, agora: float) -> None:
        """Diário: mudanças, marcos e batimento periódico."""
        chave = f"{s.local}|{s.fonte}|{s.dentro_da_cave}"

        if marco:
            diario.localizacao().info(
                "%s | MARCO %s | %s | fonte=%s cave=%s esperado=%r",
                self.conta, marco, s.resumo(), s.fonte, s.dentro_da_cave,
                self._esperado,
            )
            self.log.info("[%s] %s", marco, s.resumo())
            self._ultimo_batimento = agora

        if chave != self._ultimo_registrado:
            self._ultimo_registrado = chave
            diario.localizacao().info(
                "%s | MUDOU | %s | fonte=%s cave=%s",
                self.conta, s.resumo(), s.fonte, s.dentro_da_cave,
            )
            if s.divergencia:
                diario.registrar_evento(
                    self.conta, "divergencia",
                    f"memória diz {s.local_lido!r} e a coordenada diz {s.area!r}",
                    s.posicao, s.local_lido,
                )

        if agora - self._ultimo_batimento >= INTERVALO_DO_BATIMENTO:
            self._ultimo_batimento = agora
            diario.localizacao().debug(
                "%s | batimento | %s | fonte=%s cave=%s sem_nome=%.0fs",
                self.conta, s.resumo(), s.fonte, s.dentro_da_cave,
                s.segundos_sem_nome,
            )

    # ==================================================================
    # Perguntas que a rotina faz
    # ==================================================================

    def teleportou(self, posicao_antes: tuple[int, int] | None) -> bool:
        """A posição saltou o bastante para ser teleporte, e não caminhada?"""
        atual = self.situacao.posicao
        if posicao_antes is None or atual is None:
            return False
        return mapa_bc.distancia(posicao_antes, atual) > SALTO_DE_TELEPORTE

    def chegou_na_cave(self, posicao_antes: tuple[int, int] | None) -> bool:
        """Confirma a entrada na instância.

        Um VETO e três sinais. O veto vem primeiro e é absoluto; dos sinais,
        basta um:

          0. VETO -- a coordenada está claramente fora da cave. Nada confirma
             entrada de um lugar que comprovadamente não é a cave.
          1. A decisão já vetada de estar dentro (`dentro_da_cave`).
          2. A posição está a poucas unidades da coordenada de chegada.
          3. Houve teleporte E a posição caiu na caixa da cave.

        O sinal 2 é o mais valioso, porque funciona exatamente quando o nome do
        lugar não lê.

        ESTA FUNÇÃO CONSULTAVA O NOME CRU, e era um furo no veto. O sinal 1 era
        `e_dentro_da_cave(s.local_lido)` -- o valor que a memória devolveu, sem
        passar pela conferência da coordenada. Com o campo preso em 'Secret
        Cemetery', a tentativa de entrada FALHAVA ("Não abri o diálogo do Skull
        Herald") e mesmo assim isto respondia True:

            14:36:10  Não abri o diálogo do Skull Herald
            14:36:10  DENTRO da cave na tentativa 1 | (1380, -622) |
                      memória='Ghost Din Woods'

        Repare na própria linha do log: `memória=` mostra `s.local`, que já vinha
        corrigido para Ghost Din Woods, enquanto o portão lia `s.local_lido`, ainda
        preso. As duas fontes discordavam e o portão consultava a errada -- e daí
        o bot foi curar, atravessar a cave e procurar o waypoint 1 a 1191 unidades
        de distância.

        A lição vale além deste caso: `local_lido` é MATÉRIA-PRIMA, serve para log
        e para diagnóstico. Quem decide usa `dentro_da_cave`, que é o valor já
        conferido contra a coordenada.
        """
        s = self.situacao

        if mapa_bc.posicao_esta_fora_da_cave(s.posicao):
            return False

        if s.dentro_da_cave:
            return True

        if s.posicao is not None:
            if mapa_bc.distancia(s.posicao, mapa_bc.CHEGADA_NA_CAVE) <= RAIO_DA_CHEGADA:
                return True
            if (self.teleportou(posicao_antes)
                    and mapa_bc.posicao_esta_na_caixa_da_cave(s.posicao)):
                return True
        return False

    def na_entrada_da_cave(self, tolerancia: int = 12) -> bool:
        """Está na coordenada de onde a cave pode ser aberta?"""
        pos = self.situacao.posicao
        if pos is None:
            return False
        return mapa_bc.distancia(pos, mapa_bc.ENTRADA_EM_GHOST_DIN) <= tolerancia
