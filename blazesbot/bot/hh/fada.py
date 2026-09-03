"""A Fada da HH: ela ENTRA na cave, SEGUE o líder e cura de lá.

=========================================================================
A DIFERENÇA CONTRA A FADA DO TIME DO APP
=========================================================================

`bot/fada.py` (a `FadaDoTime`) cura DE ONDE ESTÁ. Ela não anda, e é por isso que
ela funciona sem `BotContext`: tudo chega injetado, e o laço dela é ler a fila de
cura do mural e clicar em retrato.

Na HH a curandeira precisa de DESLOCAMENTO -- viajar até a porta, entrar junto
com o líder e acompanhá-lo pelos quatro trechos. Isso depende de navegação e de
UI do jogo, ou seja, de `BotContext`.

Então este módulo COMPÕE em vez de herdar:

    EntradaDaHH    viajar até a porta e entrar          (a mesma do líder)
    FadaDoTime     UM GIRO do laço de cura, injetado    (a mesma do APP)
    seguir()       a peça nova, e é só uma tecla

E as duas últimas rodam NA MESMA VOLTA (`acompanhar`). Dois laços concorrentes
na mesma conta seriam duas mãos no mesmo teclado -- e o `_uma_volta` da
`FadaDoTime` existe exatamente para ser chamado de fora assim.

=========================================================================
POR QUE SEGUIR COM A TECLA DO JOGO, E NÃO COM WAYPOINTS
=========================================================================

A Fada poderia refazer os 66 waypoints por conta própria. Seria pior de três
formas:

  1. Ela chegaria nos pontos em outro instante que o líder, e curar de longe não
     funciona -- a distância de cura é do jogo.
  2. Dois personagens andando por cliques de minimapa no mesmo corredor se
     atravessam, e o detector de travamento de cada um acorda por causa do outro.
  3. SEGUIR NÃO TEM COMO SAIR DA ROTA. O pathfinding do jogo leva a Fada
     exatamente por onde o líder passou, inclusive nas curvas onde o clique
     calculado falha -- que é justamente onde os `via` calibrados existem.

É o que o bot em Lua faz (`keys.follow = "p"`, clique no slot 1 do time), e é a
parte dele que estava certa.

A TECLA NÃO TEM PADRÃO NO CLIENTE. `KeyBinds.follow` nasce vazia, e vazia
significa "não configurada": a Fada AVISA e não tenta. Chutar uma tecla faria
ela apertar algo que faz outra coisa -- e, dentro da cave, "outra coisa" pode ser
qualquer coisa.

=========================================================================
O CICLO DE TIME É DO LÍDER, NÃO DELA
=========================================================================

Quem desfaz e refaz o time é a rotina do líder, no `MANUTENCAO`, depois de sair
da cave -- é o que faz os bosses renascerem. A Fada só ACOMPANHA: ela entra
porque está no time, e sai quando o time cai.

Isso é de propósito. Duas contas decidindo desfazer o mesmo time é uma corrida,
e o resultado dela é um time desfeito no meio da cave.
"""
from __future__ import annotations

from ...core import lugares
from ..context import BotContext
from ..navegacao import Navigator
from . import mapa_hh
from .entrada import EntradaDaHH

# Quanto esperar entre duas leituras enquanto acompanha o líder.
#
# A Fada não decide nada por conta própria dentro da cave: ela olha se ainda está
# no time, se está seguindo, e se alguém pediu cura. Tudo isso é leitura de
# memória, que custa microssegundos -- o que se paga aqui é o `tick`, e é ele que
# faz o botão Parar responder na hora.
PASSO_DO_ACOMPANHAMENTO = 0.3

# De quanto em quanto tempo reafirmar a tecla de seguir.
#
# O jogo LARGA o follow em várias situações: o líder sai do alcance, a Fada toma
# dano, uma janela abre. Reafirmar é barato (uma tecla) e é o que evita a Fada
# ficar parada num corredor enquanto o líder mata o boss 4.
INTERVALO_DE_REAFIRMAR_O_FOLLOW = 4.0

# Teto da espera pelo líder entrar na cave.
#
# A Fada chega na porta e espera: ela NÃO entra primeiro. Entrar antes do líder
# gastaria a instância dela numa cópia onde ele não está.
TETO_ESPERANDO_O_LIDER = 3 * 60.0
PASSO_ESPERANDO_O_LIDER = 0.5


class FadaDaHH:
    """Acompanha o líder pela HH, curando-o. Não luta e não decide a rota."""

    def __init__(
        self,
        ctx: BotContext,
        lider_nick: str,
        lider_login: str = "",
        selecionar_o_lider=None,
    ) -> None:
        self.ctx = ctx
        self.lider_nick = (lider_nick or "").strip()
        # O mural fala LOGIN e o painel do time fala NICK. Quem traduz é o
        # supervisor, que tem a lista de contas -- por isso os dois entram.
        self.lider_login = (lider_login or "").strip()
        self.nav = Navigator(ctx, mapa_hh)
        self.ui = EntradaDaHH(ctx, self.nav)
        # SELECIONAR O LÍDER VEM INJETADO, e não calculado aqui.
        #
        # Quem sabe transformar "o nick X" em "clique no retrato do slot N" é o
        # supervisor -- ele já monta esse `clicar_no_retrato` para a Fada do
        # APP, com os pontos da resolução da janela. Calcular de novo aqui seria
        # um segundo jeito de achar o mesmo retrato, ou seja, um segundo jeito
        # de errar.
        #
        # `None` = ninguém injetou; a Fada avisa e não tenta seguir.
        self._selecionar_o_lider = selecionar_o_lider
        self._seguindo_desde = 0.0
        self._avisou_sem_tecla = False
        self._avisou_sem_slot = False
        self._avisou_sem_cura = False

    # ==================================================================
    # A tecla
    # ==================================================================

    def tem_tecla_de_seguir(self) -> bool:
        """A tecla está configurada? Sem ela a Fada não acompanha.

        AVISA UMA VEZ E SEGUE VIVA. Ela continua curando de onde estiver -- o que
        se perde é o deslocamento, não a função. Derrubar a conta por falta de
        uma tecla seria trocar "cura pior" por "conta parada".
        """
        if self.ctx.settings.keys.follow.strip():
            return True
        if not getattr(self, "_avisou_sem_tecla", False):
            self._avisou_sem_tecla = True
            self.ctx.log.warning(
                "HH+Fada: a tecla de SEGUIR não está configurada (Editar conta "
                "> Teclas > Seguir). Sem ela eu não acompanho o líder pela "
                "cave -- vou curar de onde estiver. Configure o follow no jogo "
                "e repita a tecla aqui.")
        return False

    def seguir_o_lider(self) -> bool:
        """Clica no retrato do líder e aperta a tecla de seguir.

        Devolve se a tecla saiu. NÃO confirma que está seguindo: o jogo não expõe
        isso, e a confirmação prática é o líder e a Fada continuarem perto -- o
        que a leitura de posição de quem chama já observa.
        """
        import time

        ctx = self.ctx
        if not self.tem_tecla_de_seguir():
            return False

        if not self._selecionar_o_lider_com_aviso():
            return False

        ctx.tick(0.15)
        ok = ctx.press(ctx.settings.keys.follow)
        if ok:
            self._seguindo_desde = time.time()
        return ok

    def _selecionar_o_lider_com_aviso(self) -> bool:
        """Seleciona o líder no painel do time. Avisa UMA vez se não puder.

        Nunca levanta: falhar em selecionar custa um follow; levantar aqui
        custaria a conta.
        """
        if self._selecionar_o_lider is None:
            if not self._avisou_sem_slot:
                self._avisou_sem_slot = True
                self.ctx.log.warning(
                    "HH+Fada: não recebi como selecionar o líder no painel do "
                    "time, então não consigo seguir. É injeção do supervisor.")
            return False
        try:
            return bool(self._selecionar_o_lider())
        except Exception as exc:
            self.ctx.log.debug("HH+Fada: falha ao selecionar o líder (%s)", exc)
            return False

    # ==================================================================
    # Chegar e entrar
    # ==================================================================

    def ir_para_a_porta(self) -> bool:
        """Viaja até a porta da HH. A MESMA rota do líder, o mesmo código."""
        ctx = self.ctx
        # A CÂMERA NA POSE PADRÃO, pelo mesmo motivo do líder: ela vai clicar no
        # mesmo NPC, na mesma coordenada posicional.
        ctx.apply_camera()

        pos = ctx.memory.position()
        if pos is not None and mapa_hh.distancia(
                pos, mapa_hh.PONTO_DA_ENTRADA) <= 30:
            return self.ui.garantir_coordenada_da_entrada()

        if not self.ui.viajar_para_a_hh():
            ctx.log.warning("HH+Fada: não consegui viajar até a HH")
            return False
        return self.ui.ir_ate_o_npc_da_hh()

    def esperar_o_lider_entrar(self) -> bool:
        """Espera o líder estar DENTRO antes de entrar.

        A FADA NÃO ENTRA PRIMEIRO. Cada entrada abre uma cópia da instância;
        entrar antes dele gastaria a dela numa cópia onde ele não está, e aí
        ninguém cura ninguém.

        O sinal é o líder ter saído da porta -- a posição dele, publicada no
        mural pela rotina dele. Sem esse sinal, o teto vence e a Fada tenta
        entrar de qualquer forma: ficar na porta para sempre é pior.
        """
        import time

        from .. import mural

        ctx = self.ctx
        limite = time.time() + TETO_ESPERANDO_O_LIDER
        while time.time() < limite:
            ctx.raise_if_stopped()
            estado = mural.estado_da_conta(self._login_do_lider())
            if estado and estado.get("dentro_da_hh"):
                ctx.log.info("HH+Fada: o líder entrou; vou atrás")
                return True
            ctx.tick(PASSO_ESPERANDO_O_LIDER)

        ctx.log.warning(
            "HH+Fada: o líder não avisou que entrou em %.0fs. Vou tentar entrar "
            "de qualquer forma -- ficar na porta é pior.", TETO_ESPERANDO_O_LIDER)
        return False

    def _login_do_lider(self) -> str:
        """O login do líder, que é a chave do mural."""
        return self.lider_login or self.lider_nick

    def entrar(self) -> bool:
        """Entra na cave. Mesma porta, mesma máquina, mesmo NPC do líder."""
        ctx = self.ctx
        self.ui.preparar_entrada()
        for _ in range(20):
            ctx.raise_if_stopped()
            if self.ui.tentar_entrar_na_hh() and self.ui.esperar_entrar():
                ctx.log.info("HH+Fada: dentro da cave")
                return True
            self.ui.registrar_falha_de_entrada()
            ctx.tick(0.25)
        ctx.log.warning("HH+Fada: não consegui entrar na cave")
        return False

    # ==================================================================
    # Dentro
    # ==================================================================

    def acompanhar(self, continuar, curar_uma_volta=None) -> None:
        """Segue o líder e CURA, no mesmo laço, enquanto ele estiver na cave.

        AS DUAS COISAS NA MESMA VOLTA, e isso é o ponto. Andar e curar são
        responsabilidades diferentes -- o deslocamento é desta classe, a cura é
        da `FadaDoTime` -- mas elas acontecem ao mesmo tempo, e dois laços
        concorrentes na mesma conta seriam duas mãos no mesmo teclado.

        `curar_uma_volta` é UM GIRO do laço da Fada (`FadaDoTime._uma_volta`),
        injetado pelo supervisor. Devolver `False` significa "é para parar", e
        aqui isso encerra o acompanhamento também: se ela não pode mais curar,
        seguir o líder não serve para nada.

        `None` = ninguém injetou a cura. Ela AINDA acompanha -- estar perto é
        útil por si, e o líder pode estar usando poção --, mas isso é bug de
        ligação e vai para o log.

        `continuar` é consultado a cada volta: é assim que a parada do usuário e
        a queda do time encerram o acompanhamento num ponto seguro.
        """
        import time

        ctx = self.ctx
        if curar_uma_volta is None and not self._avisou_sem_cura:
            self._avisou_sem_cura = True
            ctx.log.warning(
                "HH+Fada: não recebi o laço de cura, então vou acompanhar o "
                "líder sem curar. É injeção do supervisor.")

        self.seguir_o_lider()

        while continuar():
            ctx.raise_if_stopped()
            ctx.wait_if_paused()
            ctx.check_watchdog()

            if not mapa_hh.esta_dentro_da_hh(ctx.memory.position()):
                ctx.log.info("HH+Fada: saí da cave; encerrando o acompanhamento")
                return

            # A CURA VEM ANTES DO FOLLOW na volta, e a ordem é escolha: quem
            # está esperando cura está tomando dano AGORA, e um quadro de atraso
            # na cura custa mais que um quadro de atraso no seguir.
            if curar_uma_volta is not None and curar_uma_volta() is False:
                ctx.log.info("HH+Fada: o laço de cura pediu para parar")
                return

            agora = time.time()
            if agora - self._seguindo_desde >= INTERVALO_DE_REAFIRMAR_O_FOLLOW:
                # O jogo LARGA o follow: o líder sai do alcance, a Fada toma
                # dano, uma janela abre. Reafirmar custa uma tecla.
                self.seguir_o_lider()

            ctx.tick(PASSO_DO_ACOMPANHAMENTO)

    # ==================================================================
    # O ciclo inteiro
    # ==================================================================

    def rodar(self, continuar, curar_uma_volta=None) -> None:
        """Porta -> espera o líder -> entra -> acompanha e cura. Uma passada.

        Chamado em laço pelo supervisor. Uma passada por run da cave: ao sair, o
        líder desfaz e refaz o time, e a passada seguinte começa da porta.
        """
        ctx = self.ctx
        if not continuar():
            return

        if mapa_hh.esta_dentro_da_hh(ctx.memory.position()):
            # Já dentro -- o bot foi ligado com a run em andamento, ou a Fada
            # morreu e reviveu lá. Não tenta entrar de novo: o clique cairia no
            # chão e a tiraria do lugar.
            ctx.log.info("HH+Fada: já estou dentro; acompanhando")
            self.acompanhar(continuar, curar_uma_volta)
            return

        if not self.ir_para_a_porta():
            return
        self.esperar_o_lider_entrar()
        if not self.entrar():
            return
        self.acompanhar(continuar, curar_uma_volta)

    # ==================================================================
    # Diagnóstico
    # ==================================================================

    def resumo(self) -> str:
        """Uma linha para o log dizer o que a Fada está fazendo."""
        pos = self.ctx.memory.position()
        onde = ("dentro da cave" if mapa_hh.esta_dentro_da_hh(pos)
                else lugares.limpar(self.ctx.memory.location()) or "fora")
        tecla = self.ctx.settings.keys.follow.strip() or "SEM TECLA"
        return f"HH+Fada: líder={self.lider_nick or '?'} | {onde} | seguir={tecla}"
