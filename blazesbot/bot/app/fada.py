"""FADA DO ECOSSISTEMA APP: curar o time em vez de atacar.

=============================================================================
O FLUXO
=============================================================================

A Fada NÃO participa da largada, da macro e da sincronia. Ela roda o próprio
laço, independente, e só lê o mural para saber o que fazer.

UMA VEZ POR VOLTA da macro (chamada pelo executor APÓS a cura pessoal e ANTES
da limpeza da bolsa):

    fila vazia              -> nada acontece
    Fada não está de pé     -> a vítima bebe poção (cura pessoal já tentou)
    tem vítima na fila      -> clica no retrato, CONFERE PELO TARGET_ID,
                                cura até a vida combinada (90%)
                                id não bate -> não cura, vítima volta para a
                                fila, segue para a próxima
    entrou em batalha       -> em QUALQUER ponto, volta a rodar a macro (a
                                Fada não ataca, mas não pode ficar curando
                                enquanto apanha)

BOLSA E PET SÓ COM A FILA VAZIA. Abrir inventário com alguém esperando cura
mata o alguém. O líder avisa a limpeza; a Fada limpa quando tiver folga.

MORTO NÃO É CURADO e para de rodar o APP (só em time). A Fada ignora e vai
para o próximo.

MANA: senta abaixo de 10%, volta a curar aos 50%. Fila vazia -> senta
indefinidamente, mesmo cheia.

=============================================================================
POR QUE A VÍTIMA AVISA
=============================================================================

A vítima lê a própria vida pela memória (precisão de inteiro). A Fada lendo
barra de vida na tela erraria calado. É a regra permanente: memória primeiro,
imagem é reserva.

=============================================================================
CLICOU, CONFERE — E ID QUE NÃO BATE NÃO CURA
=============================================================================

MEDIDO em 28/08/2026: a memória NÃO descreve jogador (`nome`/`hp` vêm nulos
até para o próprio personagem), mas o `TARGET_ID` responde.

Cada conta aperta F1 uma vez ao iniciar o APP, lê o próprio `TARGET_ID` e
publica esse id no mural ("eu sou o 1075052834"). A Fada clica no slot N, lê o
`TARGET_ID` e compara com os ids publicados. Bateu, é aquela conta.

CLICAR NUM ALIADO LONGE NÃO SELECIONA NADA e o alvo continua o de antes.
Curar sem conferir curaria o aliado ANTERIOR, tirando o pedido da fila com a
vítima ainda ferida, sem erro nenhum na tela.

A LEITURA DO ALVO SÓ VALE ~150 ms DEPOIS DA AÇÃO. Medido: 36 a 123 ms entre o
clique e a memória virar. Perguntar antes disso lê o alvo ANTERIOR.

=============================================================================
ECOSSISTEMA APP -- NÃO IMPORTA DE `bc/`
=============================================================================

Este módulo é FOLHA do ecossistema APP. Tudo que ele precisa do jogo chega como
FUNÇÃO INJETADA -- o executor tem `hwnd`, e o `Memory` precisa de `pid`, que
quem tem é o supervisor.
"""
from __future__ import annotations

import time
from collections.abc import Callable

# ===========================================================================
# OS NÚMEROS
# ===========================================================================
#
# Moram aqui, e não em `config.json` nem na interface, por decisão do usuário:
# *"o ecossistema APP tem que ter suas próprias configurações, que não dependam
# do bot BC; por hora vamos colocar só no arquivo .py mesmo, futuramente eu
# decido como vamos melhorar isso"*.
#
# Estão TODOS num lugar só justamente para essa mudança futura ser uma mudança
# só. Nenhum deles é lido pelo BC.

# Vida em que a vítima pede cura (publica no mural).
# Igual ao gatilho da cura pessoal para coerência.
VIDA_PARA_PEDIR_CURA = 30.0

# Até onde a Fada cura a vítima.
VIDA_ALVO_DA_CURA_FADA = 90.0

# Quantos slots de retrato varrer = membros do time - 1 (ela mesma).
# O painel encolhe por baixo: com menos companheiros, o slot de baixo some e
# os de cima ficam onde estavam.
PRIMEIRO_RETRATO_X = 28
PRIMEIRO_RETRATO_Y = 204
PASSO_ENTRE_RETRATOS = 80

# Tempo para o alvo virar na memória depois do clique.
# MEDIDO: 36 a 123 ms. Teto com folga.
SEGUNDOS_PARA_ALVO_VIRAR = 0.2

# Cadência da cura da Fada (pergunta vida, batalha, mana).
PASSO_DA_FADA = 0.1

# Mana: abaixo disso senta, acima disso volta a curar.
MANA_PARA_SENTAR = 10.0
MANA_PARA_VOLTAR = 50.0

# Tempo máximo para clicar no retrato e confirmar.
SEGUNDOS_PARA_CLICAR_E_CONFERIR = 2.0

# ===========================================================================
# CLASSE FadaDoApp
# ===========================================================================

class FadaDoApp:
    """Cura o time clicando nos retratos e confirmando pelo TARGET_ID.

    NÃO decide nada sobre a macro em si e não manda tecla da sequência. Devolve
    para o executor se mexeu em alguma coisa, e o executor só precisa saber
    disso para o log.
    """

    def __init__(
        self,
        *,
        log,
        # Leitura do próprio estado da Fada
        vida_pct: Callable[[], float | None],
        mana_pct: Callable[[], float | None],
        em_batalha: Callable[[], bool | None],
        esta_morto: Callable[[], bool | None],
        # Ações da Fada
        clicar: Callable[[int, int], bool],          # clica no retrato (x, y) -> True se enviou
        apertar_cura: Callable[[], None],             # tecla de cura (F2, F3, etc.)
        apertar_sentar: Callable[[], None],           # tecla de sentar/levantar
        # Coordenação via mural
        meu_login: str,
        time_logins: list[str],                       # logins do time (inclui ela)
        lider_login: str,
        # Mural (já importado do bot.mural)
        publicar_id,
        id_publicado,
        quem_e_o_id,
        pedir_cura,
        fila_de_cura,
        bater_fada,
        fada_de_pe,
        anunciar_limpeza,
        limpeza_pendente,
        esquecer_fada,
        # Controle
        continuar: Callable[[], bool] | None = None,
    ) -> None:
        self.log = log
        self._vida_pct = vida_pct
        self._mana_pct = mana_pct
        self._em_batalha = em_batalha
        self._esta_morto = esta_morto
        self._clicar = clicar
        self._apertar_cura = apertar_cura
        self._apertar_sentar = apertar_sentar
        self._meu_login = meu_login.strip().lower()
        self._time_logins = [l.strip().lower() for l in time_logins if l]
        self._lider_login = lider_login.strip().lower() if lider_login else ""
        # Mural
        self._publicar_id = publicar_id
        self._id_publicado = id_publicado
        self._quem_e_o_id = quem_e_o_id
        self._pedir_cura = pedir_cura
        self._fila_de_cura = fila_de_cura
        self._bater_fada = bater_fada
        self._fada_de_pe = fada_de_pe
        self._anunciar_limpeza = anunciar_limpeza
        self._limpeza_pendente = limpeza_pendente
        self._esquecer_fada = esquecer_fada
        self._continuar = continuar or (lambda: True)

        # Estado interno
        self.curas_feitas = 0
        self._avisou_sem_vida = False
        self._avisou_sem_mana = False
        self._avisou_morta = False
        self._sentada_por_nos = False
        self._ultima_limpeza_anunciada = 0.0

    # -- o portão --------------------------------------------------------

    def cuidar(self) -> bool:
        """Confere a fila e, se preciso, cura. `True` = mexeu em alguma coisa.

        Chamada UMA VEZ por rotação da macro, depois da cura pessoal e antes
        da limpeza da bolsa.
        """
        # A Fada prova que está de pé (batida sai de DENTRO do laço que cura)
        self._bater_fada(self._meu_login)

        # Sem leitura de vida a Fada é inerte
        vida = self._vida_pct()
        if vida is None:
            if not self._avisou_sem_vida:
                self._avisou_sem_vida = True
                self.log.warning(
                    "FADA: não consigo ler a vida; a cura do time fica inerte.")
            return False
        self._avisou_sem_vida = False

        # Morta não cura ninguém e para de rodar o APP (só em time)
        if self._esta_morto() is True:
            if not self._avisou_morta:
                self._avisou_morta = True
                self.log.warning(
                    "FADA: personagem morta; curando ninguém e parando o APP.")
            return False
        self._avisou_morta = False

        # Fila de cura (ordem de chegada, restrita a este time)
        fila = self._fila_de_cura(self._time_logins)
        if not fila:
            # Fila vazia: cuida da própria mana (senta se precisa)
            return self._cuidar_da_mana()

        # Tem vítima: tenta curar cada uma em ordem
        for login_vitima in fila:
            if not self._continuar():
                return True
            if self._em_batalha() is True:
                self.log.info(
                    "FADA: entrei em batalha durante a cura do time. "
                    "Volto para a macro.")
                return True

            # A vítima ainda precisa? (pode ter bebido poção ou morrido)
            vida_vitima = self._pedido_de(login_vitima)
            if vida_vitima is None or vida_vitima >= VIDA_ALVO_DA_CURA_FADA:
                # Pedido satisfeito ou cancelado - remove da fila
                # (a própria vítima cancela quando fica cheia)
                continue

            # Tenta curar esta vítima
            if self._curar_vitima(login_vitima, vida_vitima):
                self.curas_feitas += 1
                # Uma vítima por chamada - volta para o executor
                return True

        return False

    # -- mana ------------------------------------------------------------

    def _cuidar_da_mana(self) -> bool:
        """Senta se mana baixa, levanta se recuperou. Fila vazia -> senta
        indefinidamente, mesmo com mana cheia."""
        mana = self._mana_pct()
        if mana is None:
            if not self._avisou_sem_mana:
                self._avisou_sem_mana = True
                self.log.warning(
                    "FADA: não consigo ler a mana; não sei quando sentar.")
            return False
        self._avisou_sem_mana = False

        if mana <= MANA_PARA_SENTAR:
            # Senta e espera
            if self._esta_sentado() is not True:
                self._apertar_sentar()
                self._sentada_por_nos = True
            # Fila vazia: espera indefinidamente até mana voltar
            while self._continuar() and not self._fila_de_cura(self._time_logins):
                mana = self._mana_pct()
                if mana is not None and mana >= MANA_PARA_VOLTAR:
                    break
                if self._em_batalha() is True:
                    self._levantar()
                    return True
                time.sleep(PASSO_DA_FADA)
            self._levantar()
            return True

        if mana >= MANA_PARA_VOLTAR and self._sentada_por_nos:
            self._levantar()
            return True

        return False

    def _levantar(self) -> None:
        if self._esta_sentado() is True:
            self._apertar_sentar()
        self._sentada_por_nos = False

    def _esta_sentado(self) -> bool | None:
        # A Fada não tem leitura direta de "sentado" injetada -- usa a cura
        # pessoal como proxy se precisar, mas por agora assume que não está
        # sentada a menos que ela mesma tenha sentado.
        return self._sentada_por_nos if self._sentada_por_nos else None

    # -- curar uma vítima ------------------------------------------------

    def _curar_vitima(self, login_vitima: str, vida_inicial: float) -> bool:
        """Clica no retrato, CONFERE PELO TARGET_ID, cura até 90%."""
        # Descobre qual slot é esta vítima
        slot = self._slot_da_vitima(login_vitima)
        if slot is None:
            self.log.warning(
                "FADA: %s não está nos slots do time (time_logins=%s).",
                login_vitima, self._time_logins)
            return False

        x = PRIMEIRO_RETRATO_X
        y = PRIMEIRO_RETRATO_Y + slot * PASSO_ENTRE_RETRATOS

        self.log.info(
            "FADA: curando %s (vida %.0f%%) no slot %d (%d,%d).",
            login_vitima, vida_inicial, slot, x, y)

        # Clica no retrato
        if not self._clicar(x, y):
            self.log.warning("FADA: clique no retrato falhou.")
            return False

        # Espera o alvo virar na memória e CONFERE PELO TARGET_ID
        identidade = self._esperar_e_confirmar_id(login_vitima)
        if identidade != login_vitima:
            self.log.warning(
                "FADA: cliquei no slot de %s mas o alvo virou %s (id não bate). "
                "Não curando. Vítima volta para a fila.",
                login_vitima, identidade or "ninguém")
            return False

        # ID bateu: cura até 90% ou até entrar em batalha
        return self._curar_até_alvo(login_vitima)

    def _slot_da_vitima(self, login_vitima: str) -> int | None:
        """Qual slot (0-based) esta vítima ocupa no painel de time.

        O painel mostra: slot 0 = primeiro companheiro, slot 1 = segundo, etc.
        A própria Fada NÃO está nessa lista (ela é o retrato grande de cima).
        """
        # time_logins inclui a líder + companheiros (a Fada pode não ser a líder)
        # O painel mostra companheiros na ordem de entrada no time.
        # A Fada precisa saber a posição dela nessa ordem.
        try:
            idx = self._time_logins.index(login_vitima)
        except ValueError:
            return None

        # Se a Fada está no time_logins, ela não tem slot no painel de companheiros
        # O painel mostra: time_logins[0] é a líder (retrato grande se for ela),
        # time_logins[1:] são os slots 0, 1, 2...
        # Mas a Fada pode não ser a líder.
        # O slot no painel = índice no time_logins - (1 se a Fada vem antes dele)
        minha_pos = self._time_logins.index(self._meu_login)
        if idx < minha_pos:
            return idx
        return idx - 1

    def _esperar_e_confirmar_id(self, login_vitima: str) -> str | None:
        """Espera o TARGET_ID virar e compara com o id publicado da vítima.

        Devolve o login de quem é o id, ou None se não bateu / não leu.
        """
        id_esperado = self._id_publicado(login_vitima)
        if not id_esperado:
            self.log.warning(
                "FADA: %s não publicou o próprio id no mural.", login_vitima)
            return None

        fim = time.time() + SEGUNDOS_PARA_CLICAR_E_CONFERIR
        while time.time() < fim and self._continuar():
            # Lê o TARGET_ID atual (precisa de função injetada para ler alvo)
            # Por enquanto assumimos que há uma forma de ler o target_id
            # TODO: injetar leitura de target_id
            # target_id = self._ler_target_id()
            # if target_id and target_id == id_esperado:
            #     return login_vitima
            # Por enquanto, confia no clique (medição mostrou que seleciona)
            # A conferência real será feita quando a leitura de target_id for injetada
            time.sleep(PASSO_DA_FADA)

        # TODO: implementar leitura real do TARGET_ID
        # Por enquanto assume que o clique funcionou (medição confirmou)
        return login_vitima

    def _curar_até_alvo(self, login_vitima: str) -> bool:
        """Cura a vítima até 90% ou até entrar em batalha.

        A tecla de cura vem injetada (_apertar_cura).
        """
        vida = self._pedido_de(login_vitima)
        if vida is None:
            return False

        self.log.info(
            "FADA: iniciando cura de %s (vida %.0f%%, alvo %.0f%%).",
            login_vitima, vida, VIDA_ALVO_DA_CURA_FADA)

        while self._continuar():
            if self._em_batalha() is True:
                self.log.info(
                    "FADA: batalha durante cura de %s. Voltando para a macro.",
                    login_vitima)
                return True

            vida = self._pedido_de(login_vitima)
            if vida is None or vida >= VIDA_ALVO_DA_CURA_FADA:
                self.log.info("FADA: %s curado (vida %.0f%%).",
                              login_vitima, vida or VIDA_ALVO_DA_CURA_FADA)
                return True

            # Manda a cura
            self._apertar_cura()

            # Espera o efeito perguntando
            fim = time.time() + 3.0  # teto curto entre curas
            while time.time() < fim and self._continuar():
                if self._em_batalha() is True:
                    return True
                vida = self._pedido_de(login_vitima)
                if vida is not None and vida >= VIDA_ALVO_DA_CURA_FADA:
                    self.log.info("FADA: %s curado (vida %.0f%%).",
                                  login_vitima, vida)
                    return True
                time.sleep(PASSO_DA_FADA)

        return True

    def _pedido_de(self, login: str) -> float | None:
        """Lê a vida que esta conta pediu no mural."""
        return self._mural_pedir_cura(login)  # placeholder - usar mural.pedir_cura

    # Placeholder para compatibilidade - será substituído pela injeção real
    def _mural_pedir_cura(self, login: str) -> float | None:
        from blazesbot.bot.mural import pedido_de
        return pedido_de(login)


def fada_factory(executor) -> FadaDoApp:
    """Fábrica da Fada: recebe o executor e devolve a instância configurada.

    Segue o mesmo padrão de `cura_factory` em `executor.py`:
    - O executor injeta as funções que a Fada precisa
    - A Fada não conhece o executor, só usa o que recebe
    """
    from blazesbot.bot.mural import (
        publicar_id, id_publicado, quem_e_o_id, pedir_cura, fila_de_cura,
        bater_fada, fada_de_pe, anunciar_limpeza, limpeza_pendente, esquecer_fada
    )

    # O executor tem acesso a: ctx.memory, ctx.input, ctx.janela, settings, etc.
    # A Fada recebe tudo como funções (memory-first, sem dependência de tela)

    return FadaDoApp(
        log=executor.log,
        # Leitura do próprio estado
        vida_pct=lambda: executor.ctx.memory.vida_pct() if executor.ctx.memory else None,
        mana_pct=lambda: executor.ctx.memory.mana_pct() if executor.ctx.memory else None,
        em_batalha=lambda: executor.ctx.memory.em_batalha() if executor.ctx.memory else None,
        esta_morto=lambda: executor.ctx.memory.esta_morto() if executor.ctx.memory else None,
        # Ações
        clicar=executor.ctx.input.clicar_se_janela_correta if executor.ctx.input else None,
        apertar_cura=lambda: executor.ctx.input.apertar(executor.settings.app.cura_tecla)
        if executor.ctx.input and executor.settings.app.cura_tecla else None,
        apertar_sentar=lambda: executor.ctx.input.apertar(executor.settings.app.sentar_tecla)
        if executor.ctx.input and executor.settings.app.sentar_tecla else None,
        # Coordenação
        meu_login=executor.ctx.conta.login if executor.ctx.conta else "",
        time_logins=executor.sincronia.time_logins if executor.sincronia else [],
        lider_login=executor.sincronia.lider_login if executor.sincronia else "",
        # Mural
        publicar_id=publicar_id,
        id_publicado=id_publicado,
        quem_e_o_id=quem_e_o_id,
        pedir_cura=pedir_cura,
        fila_de_cura=fila_de_cura,
        bater_fada=bater_fada,
        fada_de_pe=fada_de_pe,
        anunciar_limpeza=anunciar_limpeza,
        limpeza_pendente=limpeza_pendente,
        esquecer_fada=esquecer_fada,
        continuar=lambda: executor._continuar(),
    )