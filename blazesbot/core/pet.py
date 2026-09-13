"""Gerenciamento de pet compartilhado entre ecossistemas.

A lógica de alimentação do pet é a mesma para BC e APP: respeitar um intervalo
configurado, alimentar fora de combate/desmontado, e tratar o caso de "nunca
alimentou ainda" (quando `feed_on_start = False`).

Este módulo mora no `core/` porque NÃO sabe que ecossistema existe -- recebe
funções de leitura/ação e devolve decisões puras.

===========================================================================
A CADÊNCIA É FIXA, E ISSO É PEDIDO DO USUÁRIO (25/08/2026)
===========================================================================

*"É importante que a comida do pet só seja depois do tempo estipulado. Caso
esteja fora da cave e passar o tempo, você alimenta na próxima vez que entrar,
mas já vai contando para o próximo uso, para não dar tempos errados e ele acabar
ficando em comida X vezes ao dia -- por exemplo, se configurar a cada 50 minutos
tem que alimentar 28,8 vezes por dia."*

E o motivo dele: *"para o pet no jogo o tempo vai passando e vai gastando a fome
dele; se chega a 0 ele automaticamente some."*

---------------------------------------------------------------------------
A DIFERENÇA ENTRE ANCORAR NO VENCIMENTO E ANCORAR NA REFEIÇÃO
---------------------------------------------------------------------------

A versão anterior guardava o INSTANTE DA ÚLTIMA REFEIÇÃO e somava o intervalo a
partir dele. Com atraso, a cadência escorregava:

    intervalo 50 min, venceu 10:00, o bot só conseguiu alimentar 10:12

        ancorado na refeição   -> próxima 11:02   (escorregou 12 min)
        ancorado no vencimento -> próxima 10:50   (a grade não se move)

Doze minutos por atraso, ao longo de um dia, viram refeições a menos -- e o pet
some por fome, que é exatamente o desfecho que se quer evitar. Aqui a grade é
fixa: o atraso encurta AQUELA refeição, não desloca as seguintes.

---------------------------------------------------------------------------
A GRADE TEM QUE SOBREVIVER A REINÍCIO -- E ISSO É DEPENDÊNCIA CRUZADA
---------------------------------------------------------------------------

MEDIDO EM 27/08/2026, no `logs/dev/blazes-dev.jsonl`. A conta de APP
`blazestpas` (intervalo de 51 min) reiniciou o executor **12 vezes em 88
minutos** -- relogin, religar o modo, queda de janela. Como o APP nascia com
`PetFeeder()` sem grade, cada reinício caía no braço "grade não iniciada" e
RE-ANCORAVA o vencimento em `agora + 51 min`. Nenhuma sessão viveu tanto:

    23:56:33 -> 00:41:28   45 min de sessão, 51 min de intervalo
    00:42:46 -> 00:54:46   12 min
    00:55:09 -> 00:56:08    1 min
    ...

Resultado: **zero refeições em 123 minutos**, com o relógio sempre parecendo
correto. E o defeito PIORA quanto mais o bot cai, porque cada queda zera a
conta -- a única coisa que ele nunca faz é vencer.

O BC não tinha o problema porque lia e gravava `settings.pet.proxima_comida_em`
por fora, no `bc/combat.py`. Isso era metade da regra vivendo num ecossistema
só. Agora a persistência mora AQUI, na forma de um `gravar` opcional:

    PetFeeder(vence_em=<do disco>, gravar=<função que grava no disco>)

**DEPENDÊNCIA CRUZADA -- quem usa:** `bot/bc/combat.CombatEngine` (grava em
`settings.pet.proxima_comida_em` + `config.save()`) e
`bot/app/executor.ExecutorDeMacro` (mesmo destino, por funções que o
`bot/supervisor` injeta -- o executor não conhece `BotConfig`). Mexer aqui mexe
nos dois.

**O QUE NÃO SUBIU, e por quê:** o CAMINHO do disco. `core/` não sabe que existe
`config.json`, nem que existe conta. Ele recebe uma função de uma linha e a
chama; quem monta a função é o ecossistema.

**QUEM PASSA `gravar` É RESPONSÁVEL POR NÃO LEVANTAR.** Falha de gravação não
pode derrubar uma run: o pior desfecho aceitável é a grade voltar ao que estava
no disco. As duas pontas engolem e logam.

---------------------------------------------------------------------------
GRAVAR TAMBÉM QUANDO A GRADE APENAS COMEÇA
---------------------------------------------------------------------------

`deve_alimentar` grava nos DOIS momentos em que `_vence_em` muda, e o segundo é
o que consertou o APP: quando a grade NASCE (primeira pergunta, sem
`feed_on_start`), ela já vai para o disco. Sem isso, uma sessão curta continuava
jogando fora o relógio que ela mesma acabou de criar.

---------------------------------------------------------------------------
SEM FILA
---------------------------------------------------------------------------

Se o atraso for maior que um intervalo inteiro (bot parado uma hora, por
exemplo), a grade seria alcançada com duas ou três refeições seguidas. Isso não
alimenta melhor: a barra de comida tem teto e o excedente vira ração jogada
fora. Então, quando o atraso passa de um intervalo, a grade é RE-ANCORADA no
presente em vez de acumular dívida.
"""
from __future__ import annotations

import time
from collections.abc import Callable

# ===========================================================================
# QUANTO TEMPO A COMIDA PRECISA ANTES DA PRÓXIMA AÇÃO
# ===========================================================================
#
# NÃO É ESPERA DE CORTESIA -- É A JANELA EM QUE A AÇÃO SEGUINTE CANCELA O ITEM.
#
# MEDIDO NO LOG EM 27/08/2026 (`logs/dev/blazes-dev.jsonl`, conta `creubo`). O
# preparo de entrada (`RotinaBC._do_curar`) dá a comida e MONTA em seguida, e as
# três alimentações do log têm exatamente a mesma forma:
#
#     +0.0s  Alimentando o pet (a cada 56 min)      <- a tecla sai aqui
#     +0.6s  Não estou montado; montando antes de atravessar a cave
#     +0.7s  Barra de atalhos na página 1 (montar)  <- tecla 'P'
#     +3.8s  Montaria ativa
#
# Ou seja: **600 ms depois de apertar a comida o bot aperta a montaria**, porque
# a espera de dentro do `feed_pet` era `tick(0.5)`. Montar interrompe o uso do
# item, e o sintoma é o que o usuário relatou -- *"estou a horas com a
# quantidade 20"*: o log diz que alimentou, a bolsa diz que não.
#
# O VALOR NÃO É MEDIDO AINDA, e isso está escrito de propósito. Ele é herdado do
# irmão medido mais próximo: `ensure_pet` espera 1,5 s depois da tecla de
# invocar (`docs/tempos-originais.json`), no mesmo cliente e no mesmo tipo de
# ação. É TETO conservador, não gasto fixo -- só custa em run que alimenta, ou
# seja uma vez por hora.
#
# COMO MEDIR (para quem vier depois): conte os itens na bolsa antes e depois,
# variando este número para baixo até a contagem parar de cair. Enquanto isso não
# for feito, o número fica aqui, com este comentário.
SEGUNDOS_PARA_A_COMIDA_SER_USADA = 1.5


# ===========================================================================
# QUANTO ATRASO A REFEIÇÃO AGUENTA ANTES DE FURAR O VETO DA CAVE
# ===========================================================================
#
# A REGRA "SÓ DENTRO DA CAVE" É PREFERÊNCIA, NÃO DOGMA -- e este número é o
# ponto em que ela cede.
#
# Regra do usuário (25/08/2026): fora da cave o bot não desmonta com o pet
# ativo, e a comida espera o preparo de entrada. O motivo era bom: em Stone
# City o bot descia da montaria a cada cura, buff e comida no meio do trajeto,
# e cada desmonte custa descer + agir + subir.
#
# O QUE ESSA REGRA NÃO PREVIU é a janela de alimentação sumir por muito tempo.
# MEDIDO EM 13/09/2026 (`logs/dev/`, conta `creubo`, HH, intervalo de 50 min),
# 128 janelas de alimentação (`preparar_dentro`):
#
#     mediana   6,5 min     p90  10,8 min
#     p75       8,1 min     p99  21,4 min        MAX  52,7 min
#
# A cauda é o defeito. Às 14:06:22 o bot entrou em `ATE_A_PORTA` e ficou lá
# **46 minutos**; a refeição venceu às 14:27, dentro dessa janela, e só foi dada
# às 14:54:28 -- **77 minutos** depois da anterior, num intervalo de 50. Foi a
# vez em que o pet do usuário quase sumiu.
#
# POR QUE 15 MINUTOS, E NÃO OUTRO NÚMERO. Ele tem de ficar ACIMA da cauda normal
# (p90 = 10,8 min) para não disparar em operação saudável, e MUITO ABAIXO de um
# intervalo inteiro (40..60 min, grampeado em `config.PET_FEED_MINUTOS_*`) --
# porque é ao completar um intervalo de atraso que `registrar_alimentacao`
# RE-ANCORA a grade e a refeição do dia é perdida de verdade. 15 min é 25% a 37%
# do intervalo configurável: dispara em 1 das 127 janelas medidas, e nunca
# chega perto do ponto de perda.
#
# É ISTO QUE FAZ A COTA DIÁRIA FECHAR. Com o atraso limitado a 15 min, o ramo
# "SEM FILA" de `registrar_alimentacao` nunca é alcançado -- então as 28,8
# refeições/dia de um intervalo de 50 min deixam de depender de o bot estar no
# lugar certo na hora certa.
#
# O QUE ELE CUSTA: um desmonte + remonte fora da cave, no máximo uma vez por
# intervalo. Medido em `bot/hh/combate.py`: 4,2 s (desmonte 08:47:36,2 ->
# `Pet ativo` 08:47:40,4). São 4 s a cada 50 min = 0,13% do tempo. A regra de
# 25/08 combatia DEZENAS de desmontes por trajeto; um a cada 50 minutos não é
# a mesma coisa, e um pet que some custa a run inteira.
LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS = 15.0

# Entre duas TENTATIVAS de alimentar depois de o prazo estourar.
#
# NÃO É CADÊNCIA DE ALIMENTAÇÃO -- é o intervalo entre tentativas que FALHARAM.
# A tentativa pode não ir para frente por algo que o `PetFeeder` não resolve:
# não consegui desmontar, janela na frente, personagem morto. O laço da HH roda
# a cada 0,05 s; sem esta cadência, uma recusa viraria 20 tentativas por
# segundo -- tecla e desmonte em rajada contra um estado que não mudou.
#
# 30 s é o mesmo valor, pelo mesmo motivo, de `core/petbug.INTERVALO_MINIMO`:
# não insistir num estado que não muda sozinho. Com a refeição já 15 min
# atrasada, mais 30 s não move o ponteiro; uma rajada de teclas move.
CADENCIA_DAS_TENTATIVAS_DE_COMIDA = 30.0


class PetFeeder:
    """Controla o cronômetro de alimentação do pet.

    Gerencia QUANDO alimentar, não COMO (o "como" é responsabilidade de quem
    chama: desmontar, apertar a tecla, confirmar o efeito). Separar a decisão
    da ação torna a lógica testável sem depender do jogo.

    O estado é UM número -- `vence_em`, o instante em que a próxima refeição
    passa a ser devida. `None` = a grade ainda não começou.
    """

    def __init__(
        self,
        vence_em: float | None = None,
        gravar: Callable[[float], None] | None = None,
    ) -> None:
        # QUANDO A PRÓXIMA REFEIÇÃO VENCE (epoch), não quando a última aconteceu.
        # Ver o cabeçalho do módulo para a diferença medida.
        #
        # `None` = grade não iniciada, e é diferente de `0.0` (que seria "venceu
        # em 1970" e forçaria alimentação imediata). Com `None`, a primeira
        # refeição respeita `feed_on_start`.
        #
        # Recebe valor no construtor para o estado SOBREVIVER A REINÍCIO: sem
        # isso a grade nasce de novo a cada restart e a promessa de N refeições
        # por dia se perde justamente nas sessões em que o bot é reiniciado.
        self._vence_em: float | None = vence_em

        # QUEM GRAVA A GRADE NO DISCO. `None` = ninguém, e aí a grade vale só
        # para este processo -- que é como o APP rodava, e é o defeito medido no
        # cabeçalho deste módulo.
        #
        # Recebe FUNÇÃO porque `core/` não conhece `config.json` nem conta. E a
        # função NÃO PODE LEVANTAR: ver o contrato no cabeçalho.
        self._gravar = gravar

        # A última TENTATIVA de alimentar fora de hora (não a última refeição --
        # essa é `_vence_em`). Só a rede de segurança usa; ver
        # `tentativa_liberada` e `CADENCIA_DAS_TENTATIVAS_DE_COMIDA`.
        #
        # NÃO É PERSISTIDO de propósito: é anti-rajada dentro de um processo, e
        # um processo novo tem direito à primeira tentativa imediata.
        self._ultima_tentativa = 0.0

    # -- estado, para quem persiste ---------------------------------------

    @property
    def vence_em(self) -> float | None:
        """O instante da próxima refeição, para gravar em disco."""
        return self._vence_em

    # -- decisão -----------------------------------------------------------

    def deve_alimentar(
        self,
        intervalo_minutos: int,
        force: bool = False,
    ) -> bool:
        """Decide se é hora de alimentar o pet.

        Args:
            intervalo_minutos: Intervalo configurado entre alimentações.
            force: Se True, alimenta independentemente da grade (usado para
                   `feed_on_start = True`).

        Returns:
            True se deve alimentar agora, False caso contrário.
        """
        agora = time.time()

        # Grade não iniciada: só alimenta se for `force=True` (feed_on_start).
        # Sem force, a grade começa AGORA e a primeira refeição vence daqui a um
        # intervalo -- é o mesmo comportamento de antes, dito pela grade.
        if self._vence_em is None:
            if not force:
                self._vence_em = agora + self._intervalo(intervalo_minutos)
                # GRAVA A GRADE RECÉM-NASCIDA. Sem isto, uma sessão mais curta
                # que o intervalo joga fora o relógio que ela mesma criou -- e a
                # próxima sessão cria outro. Foi assim que o APP passou 123 min
                # sem alimentar. Ver o cabeçalho do módulo.
                self._persistir()
                return False
            return True

        return force or agora >= self._vence_em

    # -- leitura da fome: DERIVADA, nunca guardada --------------------------
    #
    # =======================================================================
    # POR QUE NÃO EXISTE UM `pet_needs_food` GUARDADO
    # =======================================================================
    #
    # A proposta natural é um booleano: o cronômetro estoura e liga
    # `pet_needs_food = True`; quem alimenta desliga. Ele NÃO existe aqui, e a
    # razão é a mesma que o cabeçalho deste módulo já usa contra guardar a hora
    # da última refeição: **dois estados para o mesmo fato divergem no primeiro
    # atraso**.
    #
    # A fome já está inteiramente contida em `_vence_em`:
    #
    #     com fome  ==  agora >= _vence_em
    #
    # E ela já é LATCHED de graça -- continua verdadeira volta após volta,
    # porque só `registrar_alimentacao` move `_vence_em`. Um booleano ao lado
    # não acrescentaria nada e acrescentaria um jeito de errar: processo que
    # morre com a flag ligada e a grade gravada, flag ligada por um ecossistema
    # e lida por outro, flag que alguém zera "para destravar" e a refeição some.
    #
    # O que faltava não era estado novo: era uma leitura que NÃO MUTASSE.
    # `deve_alimentar` faz a grade NASCER quando ela é `None`, então não serve
    # para ser chamada a cada volta do laço só para perguntar. Estas duas abaixo
    # servem: são puras, não gravam, e respondem `False`/`0.0` enquanto a grade
    # não começou.

    def esta_com_fome(self, intervalo_minutos: int) -> bool:
        """A refeição já venceu? LEITURA PURA -- não muta, não grava.

        É a "flag de fome": derivada da grade, e não um segundo estado ao lado
        dela. Grade não iniciada responde `False` -- sem grade não há vencimento,
        e quem faz a grade nascer é `deve_alimentar`, no ato de alimentar.
        """
        if self._vence_em is None:
            return False
        return time.time() >= self._vence_em

    def atraso_minutos(self, intervalo_minutos: int) -> float:
        """Há quantos minutos a refeição está VENCIDA. `0.0` se não venceu.

        LEITURA PURA. É o número que decide se o veto da cave ainda vale (ver
        `LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS`).
        """
        if self._vence_em is None:
            return 0.0
        return max(0.0, (time.time() - self._vence_em) / 60.0)

    def a_fome_e_urgente(self, intervalo_minutos: int) -> bool:
        """O atraso passou do ponto em que esperar o lugar certo sai caro.

        LEITURA PURA. Quem chama usa isto para decidir se paga um desmonte fora
        da cave -- ver o porquê medido em
        `LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS`.
        """
        return (self.atraso_minutos(intervalo_minutos)
                >= LIMITE_DE_ATRASO_DA_COMIDA_EM_MINUTOS)

    def tentativa_liberada(self) -> bool:
        """A cadência permite outra tentativa? MARCA a tentativa ao liberar.

        Chamada só pela rede de segurança (a alimentação atrasada), e nunca pelo
        caminho normal: o preparo de entrada alimenta uma vez por run e não
        precisa de anti-rajada.

        MARCA AO LIBERAR, num único método, de propósito. O par
        "posso?" + "marque" é fácil de usar pela metade, e a metade que falta é
        justamente a que segura a rajada. Ver
        `CADENCIA_DAS_TENTATIVAS_DE_COMIDA`.
        """
        agora = time.time()
        if agora - self._ultima_tentativa < CADENCIA_DAS_TENTATIVAS_DE_COMIDA:
            return False
        self._ultima_tentativa = agora
        return True

    def registrar_alimentacao(self, intervalo_minutos: int) -> None:
        """Marca que o pet foi alimentado e AVANÇA A GRADE.

        Chame isso APÓS apertar a tecla de comida e confirmar o efeito.

        A grade avança a partir do VENCIMENTO, não do agora -- é isso que impede
        o atraso de empurrar as refeições seguintes. Ver o cabeçalho do módulo.
        """
        agora = time.time()
        intervalo = self._intervalo(intervalo_minutos)
        base = self._vence_em if self._vence_em is not None else agora
        proximo = base + intervalo

        # SEM FILA: atraso maior que um intervalo inteiro re-ancora no presente
        # em vez de acumular refeições em dívida.
        if proximo <= agora:
            proximo = agora + intervalo
        self._vence_em = proximo
        self._persistir()

    def _persistir(self) -> None:
        """Manda a grade para o disco, se houver quem grave.

        Não engole exceção: o contrato é que `gravar` não levante (está no
        cabeçalho). Engolir aqui esconderia uma ponta mal escrita nos dois
        ecossistemas de uma vez.
        """
        if self._gravar is None or self._vence_em is None:
            return
        self._gravar(self._vence_em)

    # -- leitura -----------------------------------------------------------

    def minutos_para_alimentar(self, intervalo_minutos: int) -> float:
        """Quanto falta para a comida do pet vencer.

        Negativo quando já venceu; `0.0` quando a grade ainda não começou.
        """
        if self._vence_em is None:
            return 0.0
        return (self._vence_em - time.time()) / 60.0

    def tempo_desde_ultima_alimentacao(self, intervalo_minutos: int) -> float | None:
        """Há quantos segundos a refeição anterior venceu. `None` sem grade.

        É derivado da grade (`vencimento - intervalo`), e não guardado à parte:
        dois números para a mesma coisa divergem no primeiro atraso.
        """
        if self._vence_em is None:
            return None
        return time.time() - (self._vence_em - self._intervalo(intervalo_minutos))

    @staticmethod
    def _intervalo(intervalo_minutos: int) -> float:
        return max(1, int(intervalo_minutos)) * 60.0
