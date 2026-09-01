"""A FADA: a conta que, em time, cura os aliados em vez de atacar.

=========================================================================
O QUE MUDOU DEPOIS DA MEDIÇÃO DE 31/08/2026
=========================================================================

O desenho original dependia de a vítima anunciar tudo e de a Fada descobrir
"quem é quem" clicando. Duas medições derrubaram isso -- para melhor:

1. **O time é legível pela memória** (`Memory.time_do_jogo`), com os NOMES na
   ordem do jogo, e a MESMA ordem lida de clientes diferentes. Tirando a própria
   Fada dessa lista, sobra exatamente a ordem dos retratos no painel. Ela não
   precisa mais adivinhar nem descobrir clicando.
2. **A vida de cada companheiro é legível** (`Memory.vida_do_time`). A Fada VÊ a
   cura fazer efeito, em vez de esperar a vítima avisar que ficou cheia.

O que a vítima ainda publica no mural, e por quê: o **máximo** de vida dela (a
memória do time traz o HP atual, não o máximo) e o **pedido** em si -- que é o
que põe a ordem da fila e o que faz a Fada saber que alguém está esperando.

=========================================================================
CURAR SEM CONFERIR É CURAR O ERRADO
=========================================================================

Medido: clicar num retrato de aliado que não dá para selecionar **não muda o
alvo** -- ele continua sendo o de antes. Lançar a cura logo depois do clique
curaria o aliado ANTERIOR: o pedido sai da fila e a vítima continua ferida, sem
erro nenhum na tela.

Por isso a regra é dura e está no `docs/INVARIANTES.md`: **id que não bate, não
cura.** A vítima volta para a fila e a Fada segue para a próxima.

=========================================================================
O LAÇO
=========================================================================

    fila vazia            -> volta ao ponto, senta, recupera mana
    mana < piso           -> senta até o teto de volta, mesmo com fila
    tem alguém na fila    -> levanta, clica no retrato, CONFERE o id,
                             cura até o alvo combinado, próximo
    entrou em batalha     -> a cura para; ela não luta, mas também não cura
                             apanhando

Bolsa e pet **só com a fila vazia**: abrir inventário com alguém esperando cura
mata o alguém.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

# Cadência do laço da Fada quando não há nada a fazer.
#
# Ela não manda tecla nesse estado -- só olha o mural. Dez vezes por segundo é
# barato e é o que faz um pedido ser atendido "na hora" em vez de "na próxima
# volta de alguém".
PASSO_DA_FADA = 0.1

# Depois do clique no retrato, quanto esperar a memória mostrar o alvo novo.
#
# MEDIDO em 28/08/2026: de 36 a 123 ms entre a ação e a memória virar. 400 ms é
# ~3x o pior caso -- perguntar antes disso leria o alvo ANTERIOR e a Fada
# concluiria "não selecionei" tendo selecionado.
TETO_PARA_O_ALVO_VIRAR = 0.4
PASSO_DA_CONFERENCIA_DO_ALVO = 0.02

# Quanto tempo insistir numa cura antes de desistir daquela vítima.
#
# PROVISÓRIO -- não medido. O tempo de cura depende dos itens da Fada e até de
# crítico, então o teto existe só para a fila não travar quando a vida não sobe
# (vítima morta, fora de alcance, cura sem efeito).
TETO_DA_CURA_SEGUNDOS = 20.0

# Entre uma tecla de cura e a seguinte.
#
# PROVISÓRIO. Curto porque a skill tem o próprio tempo de conjuração e o jogo
# ignora o excesso; o custo de errar para baixo é tecla desperdiçada, e para
# cima é vítima esperando.
ESPERA_ENTRE_CURAS = 0.34

# Quantas vezes tentar selecionar a MESMA vítima antes de desistir dela.
#
# NÃO É REFINAMENTO, É FREIO. Medido em campo em 01/09/2026: com a confirmação
# falhando (a vítima não publicava o id), o laço clicou no mesmo retrato **357
# vezes**, dez por segundo -- e o personagem saiu ANDANDO de tanto clique.
#
# A regra é a mesma de sempre: quem não dá para curar cai para a poção. Insistir
# infinitamente não cura ninguém e ainda estraga o que estava funcionando.
MAXIMO_DE_TENTATIVAS_POR_VITIMA = 3

# Depois de uma tentativa que não pegou, espera antes da seguinte.
#
# Sem isto, três tentativas sairiam em 300 ms -- rápido demais para o cliente
# responder, e as três falhariam pelo mesmo motivo. Meio segundo é folga
# suficiente sobre o atraso medido (36 a 123 ms) para a tentativa seguinte ser
# de fato uma tentativa nova.
ESPERA_DEPOIS_DE_ERRAR = 0.333


class FadaDoTime:
    """O laço da Fada. Não ataca, não roda macro: cura e senta.

    Tudo chega por injeção -- este arquivo não abre memória, não conhece
    `BotContext` e não sabe o que é `AccountSupervisor`. Quem monta é o
    supervisor, que já sabe dessas coisas.
    """

    def __init__(
        self,
        *,
        log: Any,
        meu_login: str,
        meu_nick: Callable[[], str | None],
        # -- leitura do próprio estado
        vida_pct: Callable[[], float | None],
        mana_pct: Callable[[], float | None],
        em_batalha: Callable[[], bool | None],
        # -- leitura do time (memória, medida em 31/08/2026)
        companheiros: Callable[[], list[str] | None],
        vida_do_time: Callable[[], list[dict] | None],
        id_do_alvo: Callable[[], int | None],
        # -- ações
        clicar_no_retrato: Callable[[int], bool],
        apertar_cura: Callable[[], None],
        apertar_sentar: Callable[[], None],
        auto_selecionar: Callable[[], None],
        # -- o mural
        mural: Any,
        membros_do_time: Callable[[], list[str]],
        nick_de: Callable[[str], str],
        # -- controle
        continuar: Callable[[], bool],
        dormir: Callable[[float], bool],
        pedir_pct: Callable[[], float],
        parar_pct: Callable[[], float],
        mana_para_sentar: float = 10.0,
        mana_para_voltar: float = 50.0,
    ) -> None:
        self.log = log
        self.meu_login = (meu_login or "").strip().lower()
        self._meu_nick = meu_nick
        self._vida_pct = vida_pct
        self._mana_pct = mana_pct
        self._em_batalha = em_batalha
        self._companheiros = companheiros
        self._vida_do_time = vida_do_time
        self._id_do_alvo = id_do_alvo
        self._clicar_no_retrato = clicar_no_retrato
        self._apertar_cura = apertar_cura
        self._apertar_sentar = apertar_sentar
        self._auto_selecionar = auto_selecionar
        self.mural = mural
        self._membros_do_time = membros_do_time
        self._nick_de = nick_de
        self._continuar = continuar
        # TODA ESPERA BATE NO MURAL.
        #
        # A batida ficava só no topo do laço externo, e a Fada não volta lá
        # enquanto cura -- ela fica até `TETO_DA_CURA_SEGUNDOS` dentro do laço
        # de cura. Resultado medido em campo (01/09/2026): a vítima via 5 s de
        # silêncio, concluía "a Fada sumiu" e bebia poção **enquanto estava
        # sendo curada**. O log mostrou as duas linhas com 6 s de diferença.
        #
        # Embrulhar a espera resolve na raiz: não importa em que ponto do código
        # ela esteja, se ela está esperando é porque está viva e trabalhando.
        self._dormir_de_verdade = dormir
        self._dormir = self._dormir_batendo
        self._pedir_pct = pedir_pct
        self._parar_pct = parar_pct
        self.mana_para_sentar = mana_para_sentar
        self.mana_para_voltar = mana_para_voltar

        self.curas = 0
        self.curas_sem_efeito = 0
        self.cliques_errados = 0
        # Quantas vezes seguidas cada vítima falhou. Zera quando ela é atendida
        # ou sai da fila -- é por vítima, não global: uma que não dá para curar
        # não pode fazer a Fada desistir das outras.
        self._tentativas: dict[str, int] = {}
        # Quem já foi avisado como "fora do painel". Evita repetir a mesma linha
        # dez vezes por segundo enquanto a situação não muda.
        self._avisei_fora_do_painel: set[str] = set()
        self._sentada = False
        self._avisou_sem_time = False
        # Estado publicado na batida. Guardado num campo porque a batida sai de
        # dentro de QUALQUER espera, inclusive de dentro da auto-cura -- e lá
        # não há como perguntar de novo sem custar uma leitura por espera.
        self._em_briga = False

    def _dormir_batendo(self, segundos: float) -> bool:
        """Espera, batendo no mural antes. Ver o porquê no `__init__`.

        A BATIDA LEVA O ESTADO DE BATALHA junto, e é assim que o time descobre
        que ela está ocupada se defendendo -- sem mensagem nova e sem leitura
        nova, porque a batida já ia sair de qualquer forma.
        """
        self.mural.bater_fada(self.meu_login, em_batalha=self._em_briga)
        return self._dormir_de_verdade(segundos)

    # -- o laço ------------------------------------------------------------

    def rodar(self) -> None:
        """Roda até mandarem parar. É o `executor.rodar()` da Fada."""
        self.log.info("FADA iniciada — %s", self.resumo())
        try:
            while self._continuar():
                # A BATIDA SAI DAQUI, de dentro do laço que cura. Uma Fada
                # logada mas presa numa janela passa em qualquer checagem
                # externa e não cura ninguém; a batida não descreve a
                # capacidade, ela a prova.
                self.mural.bater_fada(self.meu_login,
                                      em_batalha=self._em_briga)

                if not self._uma_volta():
                    return
                if not self._dormir(PASSO_DA_FADA):
                    return
        finally:
            self.mural.esquecer_fada(self.meu_login)
            self.log.info("FADA encerrada — %s", self.resumo())

    def _uma_volta(self) -> bool:
        """Um giro do laço. `False` = é para parar."""
        if self._em_batalha() is True:
            # EM BATALHA ELA CUIDA DE SI, e não da fila.
            #
            # Decisão do usuário em 01/09/2026: *"caso a fada entre em batalha
            # ela vai apertar F1 e começar a se curar até sair de batalha (...)
            # a ideia aqui é não deixar a fada morrer de forma alguma"*.
            #
            # Isto INVERTE a decisão anterior, que era ela continuar tentando
            # sentar e confiar na proteção do time. O motivo mudou: o time só
            # protege se estiver atacando, e quem está esperando cura NÃO está
            # -- então a proteção que ela contava não existia justamente na hora
            # em que ela precisava. Quem avisa o time é a batida, que agora leva
            # o estado de batalha junto.
            self._em_briga = True
            return self._me_defender()
        self._em_briga = False

        fila = self.mural.fila_de_cura(self._membros_do_time())
        fila = [x for x in fila if x != self.meu_login]
        self._esquecer_quem_saiu_da_fila(fila)

        # A AUTO-CURA VEM ANTES DA FILA. Fada morta não cura ninguém, e ela é a
        # única do time que não tem quem a cure.
        minha_vida = self._vida_pct()
        if minha_vida is not None and minha_vida <= self._pedir_pct():
            return self._curar_a_mim_mesma(minha_vida)

        if not fila:
            return self._descansar()

        if not self._tenho_mana_para_curar():
            return self._descansar(por_falta_de_mana=True)

        # PERCORRE A FILA, não trava no primeiro.
        #
        # Quem está na frente pode não dar para atender agora (fora do painel,
        # ainda entrando no time). Parar nele deixaria TODOS os de trás sem
        # cura -- e como a Fada continua batendo, eles esperariam para sempre
        # achando que há Fada disponível. A ordem de chegada é respeitada: só
        # se pula quem não dá para atender NESTE instante.
        for login_vitima in fila:
            atendido, seguir = self._atender(login_vitima)
            if not seguir:
                return False
            if atendido:
                return True
        return True

    def _me_defender(self) -> bool:
        """Em batalha: seleciona a si mesma e cura até sair. `False` = parar.

        NÃO OLHA A PRÓPRIA VIDA para decidir se começa -- em batalha ela cura e
        pronto. O gatilho de porcentagem existe para decidir quando VALE A PENA
        parar a macro; aqui a macro nem está rodando, e o custo de uma cura a
        mais é uma tecla.

        Ela sai no instante em que a batalha acaba: quem termina isto é o time
        matando o que está batendo nela.
        """
        self._levantar()
        self._auto_selecionar()
        # TETO, e ele não é sobre desistir: é sobre DEVOLVER O CONTROLE ao laço
        # principal de tempos em tempos. Sem ele, uma batalha que não acaba (ou
        # uma leitura de combate presa em `True`) prende a Fada aqui para
        # sempre -- e nada mais dela gira: nem a batida com estado novo, nem a
        # parada pelo botão Parar em pontos que não sejam a espera.
        #
        # Ela volta para cá na volta seguinte se ainda estiver apanhando, então
        # o comportamento visível é o mesmo; o que muda é que o laço respira.
        limite = time.monotonic() + TETO_DA_CURA_SEGUNDOS
        while self._continuar() and time.monotonic() < limite:
            if self._em_batalha() is not True:
                self.log.info("FADA: saí da batalha — volto para a fila de cura.")
                self._em_briga = False
                return True
            self._apertar_cura()
            if not self._dormir(ESPERA_ENTRE_CURAS):
                return False
        return self._continuar()

    # -- descanso ----------------------------------------------------------

    def _descansar(self, por_falta_de_mana: bool = False) -> bool:
        """Sem ninguém para curar (ou sem mana), senta e recupera.

        Sentar é a única coisa útil que ela pode fazer: não ataca, não coleta,
        e a mana é o insumo da próxima cura.
        """
        if self._sentada:
            return True
        if por_falta_de_mana:
            self.log.info("FADA: mana abaixo de %.0f%% — sentando para recuperar.",
                          self.mana_para_sentar)
        self._apertar_sentar()
        self._sentada = True
        return True

    def _sair_do_descanso(self) -> None:
        """Registra que o descanso acabou. **NÃO aperta tecla nenhuma.**

        SENTAR NÃO É UMA TRAVA (regra do jogo, usuário, 01/09/2026): sentada, a
        Fada clica, seleciona e cura normalmente, e o estado sai sozinho na
        primeira ação que ela tomar. O que sentar faz é AUMENTAR a regeneração
        base de vida e de mana -- que é exatamente o que ela veio buscar.

        ISTO APERTAVA A TECLA E CHAMAVA-SE `_levantar`. Apertar era pior que
        inútil: a tecla é INTERRUPTOR, então se ela já tivesse saído do chão
        sozinha (levou dano, a volta anterior clicou em alguém), o toque a
        SENTAVA -- bem na hora de curar, que é o único momento em que ela tem
        pressa. O toque também jogava fora a regeneração do caminho.

        O QUE FICOU É SÓ A CONTABILIDADE, e ela continua necessária: `_sentada`
        é a histerese da mana (`_tenho_mana_para_curar` pede
        `mana_para_voltar` enquanto sentada e `mana_para_sentar` de pé). Sem
        zerar a marca aqui, ela ficaria presa no patamar alto para sempre.
        """
        self._sentada = False

    def _levantar(self) -> None:
        """Sai do chão para agir.

        A tecla de sentar é INTERRUPTOR e o bot não sabe em que estado está --
        por isso só este par de métodos mexe em `_sentada`. Apertar por engano
        com ela de pé a faria sentar bem na hora de curar.
        """
        if not self._sentada:
            return
        self._apertar_sentar()
        self._sentada = False

    def _tenho_mana_para_curar(self) -> bool:
        """Piso para começar, teto para voltar.

        Dois números e não um: com um só, ela sentaria e levantaria a cada
        ponto de mana, sem nunca acumular o bastante para uma cura inteira.
        """
        mana = self._mana_pct()
        if mana is None:
            # Sem leitura de mana ela não adivinha -- tenta curar. O pior caso é
            # uma tecla sem efeito; o pior caso do contrário é não curar nunca.
            return True
        if self._sentada:
            return mana >= self.mana_para_voltar
        return mana > self.mana_para_sentar

    # -- atender a fila ----------------------------------------------------

    def _esquecer_quem_saiu_da_fila(self, fila: list[str]) -> None:
        """Limpa o estado de quem não está mais esperando.

        Sem isto, duas coisas apodrecem: a contagem de tentativas de um pedido
        antigo condena o pedido NOVO da mesma conta na primeira falha, e os dois
        dicionários crescem para sempre com contas que nunca voltam.
        """
        na_fila = set(fila)
        for login in [x for x in self._tentativas if x not in na_fila]:
            self._tentativas.pop(login, None)
        nicks = {self._nick_de(x) for x in na_fila}
        self._avisei_fora_do_painel &= nicks

    def _atender(self, login_vitima: str) -> tuple[bool, bool]:
        """Tenta curar esta vítima. Devolve `(atendida, continuar)`.

        `atendida=False` com `continuar=True` significa "não deu para esta
        agora, tente a próxima da fila" -- e é o que impede um pedido que não
        dá para atender de segurar todos os outros.
        """
        nick = self._nick_de(login_vitima)
        if not nick:
            self.log.warning("FADA: %s não tem nick conhecido — não sei quem "
                             "clicar. Tirando da fila.", login_vitima)
            self.mural.cancelar_pedido(login_vitima)
            return False, True

        slot = self._slot_do_nick(nick)
        if slot is None:
            # Ela não está no painel: saiu do time, ainda não entrou, ou a
            # leitura falhou. NÃO conta como tentativa falha -- pode ser
            # passageiro, e mandá-la para a poção por isso seria injusto.
            #
            # MAS ESPERA ANTES DE OLHAR DE NOVO, e avisa UMA vez. Sem isso o
            # laço gira a 10 Hz repetindo a mesma linha: medido em campo,
            # treze avisos idênticos em dois segundos.
            if nick not in self._avisei_fora_do_painel:
                self._avisei_fora_do_painel.add(nick)
                self.log.info("FADA: %s não está no meu painel de time — "
                              "esperando ele aparecer.", nick)
            return False, self._dormir(ESPERA_DEPOIS_DE_ERRAR)
        self._avisei_fora_do_painel.discard(nick)

        self._sair_do_descanso()
        if not self._clicar_no_retrato(slot):
            return False, False

        if self._clique_saiu_errado(login_vitima, nick):
            # ID QUE NÃO BATE NÃO CURA. O clique pode não ter pego, e o alvo
            # continua o de antes -- curar agora curaria o aliado ANTERIOR.
            self.cliques_errados += 1
            tentativas = self._tentativas.get(login_vitima, 0) + 1
            self._tentativas[login_vitima] = tentativas
            if tentativas >= MAXIMO_DE_TENTATIVAS_POR_VITIMA:
                # DESISTE DELA, e isso é o freio: sem ele o laço volta em 100 ms
                # e clica de novo, para sempre. Ela cai para a poção.
                self._tentativas.pop(login_vitima, None)
                self.mural.cancelar_pedido(login_vitima)
                self.log.warning(
                    "FADA: %s não selecionou em %d tentativas — tirando da fila. "
                    "Ele se vira com poção.", nick, tentativas)
                return False, True
            self.log.warning(
                "FADA: cliquei no slot %d esperando %s e caí em OUTRO alvo "
                "(tentativa %d de %d). NÃO vou curar.",
                slot + 1, nick, tentativas, MAXIMO_DE_TENTATIVAS_POR_VITIMA)
            return False, self._dormir(ESPERA_DEPOIS_DE_ERRAR)

        self._tentativas.pop(login_vitima, None)
        return True, self._curar(login_vitima, nick)

    def _slot_do_nick(self, nick: str) -> int | None:
        """Em que retrato do painel este nick está. `None` = não está lá.

        A ordem vem da MEMÓRIA (`companheiros`), não da configuração: o jogo
        ordena o painel por ordem de entrada no time, e a lista do config está
        na ordem em que o usuário marcou as contas. Eram ordens diferentes, e
        confiar na do config faria a Fada clicar no retrato errado.
        """
        lista = self._companheiros()
        if not lista:
            if lista is None and not self._avisou_sem_time:
                self._avisou_sem_time = True
                self.log.warning("FADA: não consigo ler o time pela memória.")
            return None
        alvo = nick.strip().lower()
        for i, nome in enumerate(lista):
            if nome.strip().lower() == alvo:
                return i
        return None

    def _clique_saiu_errado(self, login_vitima: str, nick: str) -> bool:
        """O clique selecionou OUTRA pessoa? `True` = não cure.

        =================================================================
        QUEM IDENTIFICA É O SLOT, NÃO ESTA CONFERÊNCIA
        =================================================================

        A versão anterior exigia que a vítima tivesse publicado o próprio
        `TARGET_ID` e SÓ curava com ele batendo. Isso estava errado por dois
        motivos, e o segundo custou caro em campo:

        1. **Era redundante.** Desde que o time passou a ser lido da memória, o
           slot já É a identificação: `companheiros_de_time()` diz, em ordem,
           quem está em cada retrato. Clicar no slot 2 é clicar em quem a
           memória diz que está no slot 2.
        2. **Falhava FECHADA.** Sem o id publicado a resposta era "não cure", e
           o laço voltava em 100 ms para clicar de novo. Medido em 01/09/2026:
           357 cliques no mesmo retrato, zero curas, e o personagem saiu andando
           de tanto clique.

        Agora o id é REDE, não portão: quando a vítima publicou um e ele NÃO
        bate, aí sim há prova de que o clique pegou outra pessoa -- e curar
        curaria o aliado errado. Sem id publicado, confia-se no slot e cura-se.
        """
        esperado = self.mural.id_publicado(login_vitima)
        if not esperado:
            return False                    # sem rede: o slot basta
        # ESPERA O TETO INTEIRO ANTES DE CONDENAR.
        #
        # A versão anterior devolvia "errado" no PRIMEIRO olhar em que o id
        # fosse diferente e não-zero -- e logo depois do clique ele SEMPRE é: a
        # memória leva de 36 a 123 ms (medido) para mostrar o alvo novo, então o
        # que se lê nesse instante é o alvo ANTERIOR. Ou seja, a conferência
        # reprovava toda cura em que houvesse um alvo antes, que é o caso comum.
        #
        # Só é "outro alvo" o que continuar diferente depois de o teto passar.
        limite = time.monotonic() + TETO_PARA_O_ALVO_VIRAR
        while time.monotonic() < limite:
            if self._id_do_alvo() == esperado:
                return False                # bateu
            if not self._dormir(PASSO_DA_CONFERENCIA_DO_ALVO):
                return False
        atual = self._id_do_alvo()
        if atual and atual != esperado:
            return True                     # deu tempo e ficou em outro
        # Alvo zerado ou ilegível: não é prova de erro, e tratar "não sei" como
        # erro foi o que travou tudo da primeira vez.
        # Nada foi lido a tempo. Não é prova de erro -- e tratar "não sei" como
        # erro é justamente o que travava tudo.
        self.log.debug("FADA: não li o alvo a tempo ao clicar em %s; sigo pelo "
                       "slot.", nick)
        return False

    # -- a cura em si ------------------------------------------------------

    def _curar(self, login_vitima: str, nick: str) -> bool:
        """Aperta a cura até o alvo combinado. `False` = é para parar."""
        alvo_pct = self._parar_pct()
        maximo = self._maximo_da_vitima(login_vitima)
        comeco = time.monotonic()
        vida_no_comeco = self._quanto_de_vida(login_vitima, nick, maximo)

        self.log.info("FADA: curando %s até %.0f%% (vida %s%%).",
                      nick, alvo_pct,
                      f"{vida_no_comeco:.0f}" if vida_no_comeco is not None else "?")

        while time.monotonic() - comeco < TETO_DA_CURA_SEGUNDOS:
            if not self._continuar():
                return False
            if self._em_batalha() is True:
                self.log.info("FADA: entrei em batalha durante a cura de %s.", nick)
                return True

            # O PEDIDO SUMIU = A VÍTIMA SE DEU POR CURADA.
            #
            # É ela quem decide quando está boa: ao chegar no alvo, ela volta
            # para a macro e retira o pedido. A Fada não tinha como saber disso
            # e ficava curando um pedido que não existia mais até o teto de 20 s
            # -- medido em campo (01/09/2026): a vítima avisou "curado (94%)" e
            # nove segundos depois a Fada anunciou que tinha desistido dela.
            #
            # O sumiço do pedido É o aviso. Não precisa de mensagem nova nem de
            # leitura nenhuma: ele já estava ali.
            if self.mural.pedido_de(login_vitima) is None:
                self.curas += 1
                self.log.info("FADA: %s tirou o pedido — está curado. Próximo.",
                              nick)
                return True

            pct = self._quanto_de_vida(login_vitima, nick, maximo)
            if pct is not None and pct >= alvo_pct:
                self.curas += 1
                self.mural.cancelar_pedido(login_vitima)
                self.log.info("FADA: %s curado (%.0f%%). Próximo.", nick, pct)
                return True

            self._apertar_cura()
            if not self._dormir(ESPERA_ENTRE_CURAS):
                return False

        # TETO ESTOURADO. A vida não subiu o bastante: vítima morta, fora de
        # alcance, ou a cura não está saindo. Desistir dela é o que impede a
        # fila inteira de travar num caso perdido -- ela cai para a poção.
        self.curas_sem_efeito += 1
        self.mural.cancelar_pedido(login_vitima)
        self.log.warning(
            "FADA: desisti de %s depois de %.0fs sem chegar a %.0f%%. Ele volta "
            "a se virar com poção.", nick, TETO_DA_CURA_SEGUNDOS, alvo_pct)
        return True

    def _curar_a_mim_mesma(self, minha_vida: float) -> bool:
        """A Fada é a única do time sem quem a cure.

        Ela se seleciona com a tecla de auto-seleção -- a mesma que a medição de
        28/08/2026 provou pôr o próprio id no `TARGET_ID`.
        """
        self._sair_do_descanso()
        self._auto_selecionar()
        alvo_pct = self._parar_pct()
        self.log.info("FADA: minha vida em %.0f%% — curando a mim mesma até %.0f%%.",
                      minha_vida, alvo_pct)
        comeco = time.monotonic()
        while time.monotonic() - comeco < TETO_DA_CURA_SEGUNDOS:
            if not self._continuar():
                return False
            atual = self._vida_pct()
            if atual is not None and atual >= alvo_pct:
                self.curas += 1
                return True
            self._apertar_cura()
            if not self._dormir(ESPERA_ENTRE_CURAS):
                return False
        return True

    # -- leitura da vida do companheiro ------------------------------------

    def _vida_do_companheiro(self, nick: str) -> int | None:
        vidas = self._vida_do_time()
        if not vidas:
            return None
        alvo = nick.strip().lower()
        for membro in vidas:
            if str(membro.get("nome", "")).strip().lower() == alvo:
                return membro.get("hp")
        return None

    def _quanto_de_vida(self, login_vitima: str, nick: str,
                        maximo: int | None) -> float | None:
        """A vida da vítima em %, pela fonte MAIS CONFIÁVEL disponível.

        1. **O que ela mesma publicou.** A vítima lê o próprio `hp`/`max_hp` com
           precisão de inteiro e republica enquanto espera. É a fonte boa.
        2. **A struct do time**, como reserva -- e só como reserva: o offset da
           vida do companheiro ainda NÃO está confirmado. A primeira tentativa
           leu o campo errado (o MÁXIMO), e a Fada concluía "já está com 100%"
           sem apertar a cura uma vez sequer. Foi assim em campo, 01/09/2026.
        """
        anunciado = self.mural.pedido_de(login_vitima)
        if anunciado is not None:
            return float(anunciado)
        return self._pct_do_companheiro(nick, maximo)

    def _pct_do_companheiro(self, nick: str, maximo: int | None) -> float | None:
        """A vida do aliado em porcentagem.

        A memória do time traz o HP ATUAL; o MÁXIMO vem do mural, publicado pela
        própria vítima (que é quem lê o próprio máximo). Sem o máximo não há
        porcentagem -- e aí a Fada cai no que a vítima anunciou.
        """
        hp = self._vida_do_companheiro(nick)
        if hp is None or not maximo:
            return None
        return max(0.0, min(100.0, hp * 100.0 / maximo))

    def _maximo_da_vitima(self, login_vitima: str) -> int | None:
        estado = self.mural.estado_da_conta(login_vitima) or {}
        maximo = estado.get("max_hp")
        return int(maximo) if maximo else None

    def resumo(self) -> str:
        return (f"fada: {self.curas} curas, {self.curas_sem_efeito} sem efeito, "
                f"{self.cliques_errados} cliques que não pegaram")
