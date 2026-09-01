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
ESPERA_ENTRE_CURAS = 0.6

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
ESPERA_DEPOIS_DE_ERRAR = 0.5


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
        self._dormir = dormir
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
        self._sentada = False
        self._avisou_sem_time = False

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
                self.mural.bater_fada(self.meu_login)

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
            # Ela não luta, mas também não cura apanhando: sentar não gruda e a
            # cura sai no meio do dano. Espera a briga acabar.
            return True

        fila = self.mural.fila_de_cura(self._membros_do_time())
        fila = [x for x in fila if x != self.meu_login]

        # A AUTO-CURA VEM ANTES DA FILA. Fada morta não cura ninguém, e ela é a
        # única do time que não tem quem a cure.
        minha_vida = self._vida_pct()
        if minha_vida is not None and minha_vida <= self._pedir_pct():
            return self._curar_a_mim_mesma(minha_vida)

        if not fila:
            return self._descansar()

        if not self._tenho_mana_para_curar():
            return self._descansar(por_falta_de_mana=True)

        return self._atender(fila[0])

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

    def _levantar(self) -> None:
        """Sai do chão para agir.

        A tecla de sentar é INTERRUPTOR e o bot não sabe em que estado está --
        por isso quem controla é este par de métodos, e só eles mexem em
        `_sentada`. Apertar por engano com ela de pé a faria sentar bem na hora
        de curar.
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

    def _atender(self, login_vitima: str) -> bool:
        """Cura quem está na frente da fila. `False` = é para parar."""
        nick = self._nick_de(login_vitima)
        if not nick:
            self.log.warning("FADA: %s não tem nick conhecido — não sei quem "
                             "clicar. Tirando da fila.", login_vitima)
            self.mural.cancelar_pedido(login_vitima)
            return True

        slot = self._slot_do_nick(nick)
        if slot is None:
            # Ela não está no painel: saiu do time, ainda não entrou, ou a
            # leitura falhou. Não é erro da vítima -- só não dá para curar agora.
            self.log.info("FADA: %s não está no meu painel de time — pulando.", nick)
            return True

        self._levantar()
        if not self._clicar_no_retrato(slot):
            return False

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
                return True
            self.log.warning(
                "FADA: cliquei no slot %d esperando %s e caí em OUTRO alvo "
                "(tentativa %d de %d). NÃO vou curar.",
                slot + 1, nick, tentativas, MAXIMO_DE_TENTATIVAS_POR_VITIMA)
            return self._dormir(ESPERA_DEPOIS_DE_ERRAR)

        self._tentativas.pop(login_vitima, None)
        return self._curar(login_vitima, nick)

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
        limite = time.monotonic() + TETO_PARA_O_ALVO_VIRAR
        while time.monotonic() < limite:
            atual = self._id_do_alvo()
            if atual == esperado:
                return False                # bateu
            if atual:
                # Já há alvo e é OUTRO: o clique pegou quem não devia.
                return True
            if not self._dormir(PASSO_DA_CONFERENCIA_DO_ALVO):
                return False
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
        self._levantar()
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
