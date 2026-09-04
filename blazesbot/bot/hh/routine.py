"""A rotina da HH: quatro bosses em sequência, e o reset que os faz renascer.

=========================================================================
O CICLO
=========================================================================

    SITUAR ............ onde estou? Dentro da cave, na porta, ou em Stone City?
    PREPARAR .......... câmera, CAP e montaria. NADA que exija estar a pé
    ATE_A_PORTA ....... Fay -> West Suburb -> Mutual -> (-342,-288), e o PET
    ENTRAR ............ o time é montado AQUI, e a porta é disputada
    PREPARAR_DENTRO ... poção, buffs, pet, comida, montaria -- nesta ordem
    ATE_O_BOSS ........ um trecho de waypoints; repete para os 4 bosses
    BOSS .......... luta, loot
    SAIR .......... pelo NPC, de volta para fora
    MANUTENCAO .... vender, deletar, desfazer e refazer o time
    RECUPERAR ..... morreu ou algo saiu do roteiro

FORA DA CAVE NÃO SE PREPARA NADA que dependa de estar a pé. É regra do
usuário (03/09/2026) e é o que a BC já faz: buff, poção e comida de pet moram no
`PREPARAR_DENTRO`, depois que a instância abriu. A única exceção é o PET, que é
conferido uma vez ao CHEGAR na porta -- e conferido de novo lá dentro, porque a
tela de carregamento é justamente onde ele some.

A DIFERENÇA DE FORMA CONTRA A BC é que os quatro bosses são um LAÇO sobre
`mapa_hh.TRECHOS_DOS_BOSSES`, e não quatro pares de estados. Acrescentar um
quinto boss é uma linha de dados, não dois estados novos e mais um `if`.

=========================================================================
O RESET -- REGRA DO JOGO, NÃO DO BOT
=========================================================================

Sem desfazer e refazer o time, os bosses NÃO RENASCEM e a run seguinte não tem o
que matar. Dois modos, e a diferença é o que a segunda conta faz depois de entrar:

    "solo"   a conta de reset aceita o convite, o personagem entra, o time é
             DESFEITO e a cave é feita sozinha. A reset nunca entra. É
             exatamente o que a BC já faz.

    "fada"   AS DUAS entram. A Fada acompanha e cura. O desfaz-refaz acontece
             FORA, depois de sair -- e só então dá para entrar de novo.

O modo muda ONDE o ciclo de time acontece, não o que ele é: em "solo" ele fecha
no `ENTRAR`; em "fada", no `MANUTENCAO`. Ver `docs/decisoes/hh.md`, seção 4.

=========================================================================
NADA AQUI É MOTOR
=========================================================================

Andar é `bot/navegacao.py`, lutar é `bot/combate.py`, operar janela é
`bot/ui_do_jogo.py`, vender é `VendorService`, catar é `core/catador.py`,
deletar é `bot/app/deletador.py`, o pet é `core/pet.py`, o time é
`bot/team.py` e a coordenação com a Fada é o `bot/mural.py`. Esta rotina é a
ORDEM em que essas coisas acontecem nesta cave, e mais nada.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum, auto

from ...config import CAVE_HH, MODO_FADA_DA_HH
from ...core import catador, esconder_jogadores, logmodo
from ...core.vision import capture_window, find_template
from .. import mural
from ..combate import CombatEngine
from ..context import BotContext, StopRequested
from ..navegacao import Navigator
from ..team import TeamService
from . import mapa_hh
from .entrada import EntradaDaHH
from .vendedor import VendedorDaHH

# ---------------------------------------------------------------------------
# Tempos e tetos
# ---------------------------------------------------------------------------

# Teto da tentativa de chegar na porta da cave. A viagem passa por dois painéis
# de arredores e um teleporte; acima disto algo está errado de verdade.
MAX_SEGUNDOS_ATE_A_PORTA = 10 * 60.0

# Teto da rajada de tentativas de entrar. A vaga é disputada e cada tentativa
# custa cerca de 1 segundo -- ver `bot/ui_do_jogo.py`.
MAX_SEGUNDOS_NA_PORTA = 5 * 60.0

# Entre uma tentativa de entrada e a seguinte. É o RESTO do orçamento, não um
# gasto: a tentativa em si já leva ~1 s.
ENTRE_TENTATIVAS_DE_ENTRAR = 0.25

# Teto de um trecho de waypoints até um boss. O trecho mais longo tem 22
# waypoints; com montaria isso é bem menos de um minuto.
MAX_SEGUNDOS_POR_TRECHO = 5 * 60.0

# Quanto esperar entre estados DENTRO da cave.
#
# Curto de propósito: lá dentro os mobs vêm atrás, e folga de tempo é dano
# tomado. Fora da cave não há pressa.
PASSO_DENTRO_DA_CAVE = 0.05
PASSO_FORA_DA_CAVE = 0.4

# Quantas voltas do laço sem sair do estado antes de desconfiar.
VOLTAS_ANTES_DE_RECUPERAR = 3

# Quanto o personagem pode estar longe do ponto do boss e ainda contar como
# "no ponto".
#
# MESMO VALOR DO BC (`routine.TOLERANCIA_DO_PONTO_DO_BOSS`), e pelo mesmo
# motivo: o pathfinding para onde para, e exigir a coordenada exata faria o bot
# voltar a andar por uma unidade de arredondamento.
TOLERANCIA_DO_PONTO = 15


# O botão "Pick up all" da janela de loot, achado por template.
#
# É ELE, E SÓ ELE, que autoriza o clique esquerdo do catador: esquerdo na cena
# 3D faz o personagem ANDAR, e andar no ponto do boss é sair da rota. Mesmo
# template e mesmo limiar da BC -- o botão é do jogo, não da cave.
TEMPLATE_PICK_UP_ALL = "btn_pick_up_all.png"
LIMIAR_DO_PICK_UP_ALL = 0.85


class State(Enum):
    SITUAR = auto()
    PREPARAR = auto()
    ATE_A_PORTA = auto()
    ENTRAR = auto()
    PREPARAR_DENTRO = auto()
    ATE_O_BOSS = auto()
    BOSS = auto()
    SAIR = auto()
    MANUTENCAO = auto()
    RECUPERAR = auto()


# Estados que acontecem DENTRO da instância, com os mobs vindo atrás.
ESTADOS_DENTRO_DA_CAVE = frozenset({
    State.PREPARAR_DENTRO, State.ATE_O_BOSS, State.BOSS, State.SAIR,
})


class HHRoutine:
    """Executa ciclos de boss-rush na HH até parada ou desconexão."""

    def __init__(self, ctx: BotContext) -> None:
        self.ctx = ctx
        self.nav = Navigator(ctx, mapa_hh)
        self.combat = CombatEngine(ctx, self.nav)
        self.ui = EntradaDaHH(ctx, self.nav)
        self.vendedor = VendedorDaHH(ctx, self.nav)
        self.team = TeamService(
            ctx, nick_do_reset=lambda: ctx.settings.hh.reset_nick)
        self.state = State.SITUAR
        # Em qual dos quatro trechos a run está. É o índice em
        # `mapa_hh.TRECHOS_DOS_BOSSES`, e é o que faz os quatro bosses serem um
        # laço em vez de quatro pares de estados.
        self._trecho = 0
        self._voltas_no_estado = 0
        self._ultimo_estado: State | None = None
        self._runs_na_ultima_venda = 0
        # Se a morte desta vez já foi contada no placar.
        self._contou_a_morte = False

    # ==================================================================
    # O laço
    # ==================================================================

    def run(self, max_runs: int | None = None,
            should_continue: Callable[[], bool] | None = None) -> None:
        """Executa ciclos até parada, desconexão ou limite de runs.

        `should_continue` é consultado no início de cada iteração. É assim que
        desligar o farm pela interface tem efeito imediato: a rotina devolve o
        controle num ponto seguro, entre estados, sem interromper uma ação pela
        metade.

        NÃO TRATA `Disconnected`: deixa subir para o supervisor, que é quem sabe
        matar o cliente, relançar e relogar. Login e relogin são a fundação, e
        todo ecossistema usa a MESMA -- ver o `CLAUDE.md`.
        """
        ctx = self.ctx
        ctx.log.info(
            "Iniciando HH (Black Wind Camp Dungeon) | reset: %s (%s) | "
            "montaria %s%% | venda a partir do slot %s",
            ctx.settings.hh.modo_do_reset,
            ctx.settings.hh.reset_nick or "sem conta de reset",
            ctx.settings.mount_speed_pct,
            ctx.settings.hh.vendor.sell_start_slot,
        )
        # Começa SITUANDO, nunca preparando: uma conta que já está no meio da
        # cave continua de onde estava, em vez de tentar entrar estando dentro --
        # o que faria o clique cair no chão e tirar o personagem da rota.
        self.state = State.SITUAR
        self._runs_na_ultima_venda = ctx.stats.runs

        # Desligar a HH pela interface precisa cortar a fase atual NO MEIO.
        # `farming` é o sinal para `ctx.raise_if_stopped` detonar `FarmDesligado`.
        # O `finally` garante que a flag cai mesmo em exceção ou `return` --
        # senão o laço "online" seguinte re-detonaria a parada e derrubaria a
        # sessão, o oposto do desejado.
        ctx.farming = True
        # QUEM está no ar. É o que faz a parada conferir o
        # interruptor desta cave, e não `account.farms`.
        ctx.cave_em_farm = CAVE_HH
        try:
            while True:
                if should_continue is not None and not should_continue():
                    ctx.log.info("HH desligada; devolvendo o controle")
                    return
                if max_runs is not None and ctx.runs_completed >= max_runs:
                    ctx.log.info("Limite de %s runs atingido", max_runs)
                    return

                self._guard()
                self._contar_a_volta()
                logmodo.fase(self.state.name.lower())

                handler = getattr(self, f"_do_{self.state.name.lower()}")
                handler()

                ctx.tick(PASSO_DENTRO_DA_CAVE
                         if self.state in ESTADOS_DENTRO_DA_CAVE
                         else PASSO_FORA_DA_CAVE)
        finally:
            ctx.farming = False
            ctx.cave_em_farm = ""

    def _guard(self) -> None:
        """A parada e a queda respondem ENTRE estados, sempre."""
        self.ctx.raise_if_stopped()
        self.ctx.wait_if_paused()
        self.ctx.check_watchdog()

    def _contar_a_volta(self) -> None:
        """Quantas voltas seguidas no mesmo estado.

        Um estado que não avança não é erro por si -- a porta da cave é
        disputada e repetir ali é o normal. O contador existe para o log poder
        dizer "estou há N voltas em ENTRAR", que é a diferença entre "está
        tentando" e "está travado".
        """
        if self.state is self._ultimo_estado:
            self._voltas_no_estado += 1
        else:
            self._voltas_no_estado = 0
            self._ultimo_estado = self.state

    def _ir_para(self, estado: State, motivo: str = "") -> None:
        if motivo:
            self.ctx.log.info("HH: %s", motivo)
        self.state = estado

    def _falhar(self, mensagem: str,
                proximo: State = State.RECUPERAR) -> None:
        self.ctx.log.warning("HH: %s", mensagem)
        self.state = proximo

    # ==================================================================
    # SITUAR -- onde estou?
    # ==================================================================

    def _do_situar(self) -> None:
        """Descobre em que ponto do ciclo a conta está, e entra por ali.

        TRÊS RESPOSTAS POSSÍVEIS, e a ordem de checagem importa:

          1. DENTRO da cave -- o personagem morreu e reviveu lá, ou o bot foi
             ligado com a run em andamento. Retoma pelo trecho mais próximo, sem
             tentar entrar de novo.
          2. Na PORTA -- saiu da cave e a run seguinte pode começar da entrada.
          3. Em qualquer outro lugar -- vai preparar e depois viajar.

        SEM LEITURA DE POSIÇÃO NÃO SE DECIDE NADA: sem saber onde está, qualquer
        escolha é chute, e chute aqui significa clicar no NPC errado ou andar
        para o lado oposto. Espera a leitura voltar.
        """
        ctx = self.ctx
        pos = ctx.memory.position()
        if pos is None:
            ctx.log.info("HH: sem leitura de posição; aguardando para me situar")
            ctx.tick(1.0)
            return

        if mapa_hh.esta_dentro_da_hh(pos):
            self._retomar_dentro_da_cave(pos)
            return

        if mapa_hh.distancia(pos, mapa_hh.PONTO_DA_ENTRADA) <= 30:
            self._ir_para(State.PREPARAR,
                          f"estou na porta da cave ({pos}); preparando")
            return

        self._ir_para(State.PREPARAR, f"estou em {pos}; preparando para viajar")

    def _retomar_dentro_da_cave(self, pos: tuple[int, int]) -> None:
        """Já estou dentro: descobre por qual trecho continuar.

        Escolhe o trecho cujo waypoint mais próximo está mais perto. Não é
        adivinhação: os quatro trechos ocupam regiões distintas da cave, e a
        distância separa bem.
        """
        melhor, menor = 0, float("inf")
        for i, (_rotulo, caminho, _ponto) in enumerate(mapa_hh.TRECHOS_DOS_BOSSES):
            _indice, dist = mapa_hh.mais_proximos(pos, caminho)[0]
            if dist < menor:
                melhor, menor = i, dist

        self._trecho = melhor
        rotulo = mapa_hh.TRECHOS_DOS_BOSSES[melhor][0]
        # PASSA PELO PREPARO, e não direto para o trecho. Quem chega aqui ou
        # morreu e reviveu dentro, ou abriu o bot com a run em andamento -- nos
        # dois casos a vida, os buffs e o pet estão em estado desconhecido, que é
        # exatamente o que o preparo resolve. E ele começa curando.
        self._ir_para(
            State.PREPARAR_DENTRO,
            f"já estou DENTRO da cave em {pos}; retomando no trecho do "
            f"{rotulo} (waypoint a {menor:.0f} unidades)")

    # ==================================================================
    # PREPARAR -- pet, buffs, poção, cap, montaria
    # ==================================================================

    def _do_preparar(self) -> None:
        """FORA DA CAVE SÓ ACONTECE O QUE NÃO DÁ PARA FAZER DENTRO.

        =================================================================
        O QUE SAIU DAQUI, E POR QUÊ
        =================================================================

        Regra do usuário, 03/09/2026: *"o uso de SS, o uso de buff, o uso de
        poção de cura, qualquer coisa que precisar é só depois que entrar na
        cave e não fora, como é feito no bot BC"*. É a mesma regra que a
        Bewitcher Cave já seguia desde 25/08/2026 -- ver `bc.routine._do_curar`.

        Buff, poção e comida de pet foram para `_do_preparar_dentro`. Os dois
        motivos são medidos e valem igual aqui:

          * TUDO ISSO EXIGE ESTAR A PÉ, e montado o jogo IGNORA a tecla sem
            devolver erro -- o bot "aperta e nada acontece". Desmontar no meio
            do trajeto custa a descida, a ação e a remontagem.
          * ENTRAR É DISPUTADO e pode levar até uma hora de tentativa. Nesse
            intervalo o personagem regenera de graça: curar antes é gastar
            poção que a espera ia devolver.

        FICA AQUI: a câmera, a montaria para viajar, e a decisão de vender.
        O PET fica em `_do_ate_a_porta` -- é a única verificação que acontece
        fora, e só ao CHEGAR na porta (regra do usuário na mesma data).
        """
        ctx = self.ctx

        # A CÂMERA NA POSE PADRÃO, e é a primeira coisa do preparo.
        #
        # Mesma exigência da BC (`BossRushRoutine._do_preparar`): todo clique de
        # NPC e todo clique de minimapa deste ecossistema é POSICIONAL na cena
        # 3D. Com a câmera fora do padrão, a coordenada certa aponta para o lugar
        # errado -- e o bot em Lua sabia disso, chamava `setCamera(380, 0, 40)`
        # no começo de cada run. A diferença é que aqui a pose é lida da memória
        # e conferida (`Memory.camera_na_pose_certa`), em vez de escrita às
        # cegas sobre um ponteiro resolvido no início do script.
        ctx.apply_camera()

        # A bolsa manda ir vender ANTES de entrar, não depois de encher.
        if self._precisa_vender():
            self._ir_para(State.MANUTENCAO, "a bolsa pede venda antes de entrar")
            return

        # MONTARIA PARA VIAJAR. A regra do usuário é curta: *"a montaria você
        # irá sempre que precisar, dentro e fora da cave"* -- e só desce para
        # atacar. Aqui é o começo de um trajeto, então sobe.
        self.nav.garantir_montaria_para_andar("ir até a porta da HH")

        self._ir_para(State.ATE_A_PORTA, "indo para a porta da cave")

    def _precisa_vender(self) -> bool:
        """A bolsa está cheia, ou já passaram runs demais desde a última venda?

        DUAS FONTES, e a segunda é rede: a leitura de bolsa pode falhar, e um
        teto por contagem de runs garante que a venda acontece de qualquer jeito.
        """
        ctx = self.ctx
        # `precisa_vender` devolve False quando a contagem não pôde ser lida --
        # vender sem saber quantos itens existem levaria o bot a viajar sem
        # motivo e a clicar na grade de uma janela talvez vazia.
        if ctx.settings.bags.precisa_vender(ctx.memory.bag_count()):
            return True

        desde = ctx.stats.runs - self._runs_na_ultima_venda
        return desde >= ctx.settings.hh.vendor.runs_before_selling

    # ==================================================================
    # ATE_A_PORTA
    # ==================================================================

    def _do_ate_a_porta(self) -> None:
        """Stone City -> West Suburb -> a coordenada de conversa.

        JÁ ESTAR NA PORTA É O CASO NORMAL a partir da segunda run: sair da cave
        devolve o personagem ali perto. Conferir antes evita uma viagem inteira
        (dois painéis e um teleporte) para chegar onde já se está.
        """
        ctx = self.ctx
        pos = ctx.memory.position()

        if pos is not None and mapa_hh.distancia(
                pos, mapa_hh.PONTO_DA_ENTRADA) <= 30:
            if self.ui.garantir_coordenada_da_entrada():
                self._conferir_o_pet_na_porta()
                self._ir_para(State.ENTRAR, "já estou na porta")
                return

        if not self.ui.viajar_para_a_hh():
            self._falhar("não consegui viajar para a HH", State.RECUPERAR)
            return

        if not self.ui.ir_ate_o_npc_da_hh():
            self._falhar("não cheguei na porta da cave", State.RECUPERAR)
            return

        self._conferir_o_pet_na_porta()
        self._ir_para(State.ENTRAR, "na porta da cave")

    def _conferir_o_pet_na_porta(self) -> None:
        """A ÚNICA verificação que acontece fora da cave, e é aqui.

        Regra do usuário, 03/09/2026: *"o pet também pode verificar fora da
        cave, mas só ao chegar na frente da cave, antes não precisa"*.

        O LUGAR É ESTE, e não dentro do laço de tentativas: a rajada de entrada
        pode durar uma hora com uma tentativa a cada 25 ms, e reler o pet ali
        seriam centenas de leituras por minuto de uma coisa que não muda com o
        personagem parado na porta. Aqui roda uma vez, ao chegar.

        Dentro da cave o pet é conferido DE NOVO (`_do_preparar_dentro`), e a
        repetição é de propósito: a tela de carregamento da instância é
        justamente onde ele some.
        """
        if self.ctx.settings.pet.summon_on_login:
            self.combat.ensure_pet()

    # ==================================================================
    # ENTRAR -- a vaga é disputada
    # ==================================================================

    def _do_entrar(self) -> None:
        """Monta o time, tenta entrar em rajada, e confirma pela POSIÇÃO.

        O TIME É MONTADO AQUI, não antes: mexer na lista no meio do caminho não
        adianta e o convite podia expirar durante o teleporte.

        F12 PRESO DURANTE A RAJADA. Daqui saem dois cliques por segundo na cena
        3D disputando a vaga, e um jogador parado na frente do NPC engole todos
        eles.
        """
        ctx = self.ctx
        if not self._garantir_o_time():
            return

        self.ui.preparar_entrada()
        limite = time.time() + MAX_SEGUNDOS_NA_PORTA

        with esconder_jogadores.segurado(
                tecla=ctx.settings.keys.hide_players,
                segurar=ctx.key_down, soltar=ctx.key_up, log=ctx.log):
            while time.time() < limite:
                self._guard()

                if not self.ui.tentar_entrar_na_hh():
                    self.ui.registrar_falha_de_entrada()
                    ctx.tick(ENTRE_TENTATIVAS_DE_ENTRAR)
                    continue

                if self.ui.esperar_entrar():
                    self._entrou()
                    return

                self.ui.registrar_falha_de_entrada()
                ctx.tick(ENTRE_TENTATIVAS_DE_ENTRAR)

        self._falhar(f"não consegui entrar em {MAX_SEGUNDOS_NA_PORTA:.0f}s",
                     State.RECUPERAR)

    def _entrou(self) -> None:
        """Dentro. No modo solo, o time é desfeito AQUI.

        A CONTAGEM DA RUN NÃO COMEÇA AQUI, e sim no `_do_preparar_dentro` --
        mesmo desenho da BC. A disputa da porta pode ter levado uma hora e o
        preparo leva mais alguns segundos; contar a run a partir daí é o que
        torna o tempo por run comparável entre uma volta e outra.
        """
        ctx = self.ctx
        self._trecho = 0

        if ctx.settings.hh.modo_do_reset != MODO_FADA_DA_HH:
            # SOLO: a conta de reset já cumpriu o papel dela. Desfazer agora é o
            # que faz os bosses renascerem para a PRÓXIMA run -- e é o mesmo
            # desenho da BC.
            if ctx.settings.hh.reset_nick:
                self.team.sair_do_time()
        else:
            ctx.log.info("HH+Fada: mantendo o time; ela entra junto e acompanha")

        # AVISA A FADA. Ela espera na porta e NÃO entra primeiro: cada entrada
        # abre uma cópia da instância, e entrar antes do líder gastaria a dela
        # numa cópia onde ele não está. Ver `bot/hh/fada.py`.
        self._publicar_onde_estou(dentro=True)
        self._ir_para(State.PREPARAR_DENTRO, "dentro da cave; preparando")

    # ==================================================================
    # PREPARAR_DENTRO -- tudo que exige estar a pé, num lugar só
    # ==================================================================

    def _do_preparar_dentro(self) -> None:
        """O PREPARO DE ENTRADA. É o `_do_curar` da BC, com os mesmos motivos.

        =================================================================
        A ORDEM, E POR QUE ELA É ESTA
        =================================================================

            1. CURAR    -- primeiro, porque buff em personagem que vai morrer é
                           buff desperdiçado
            2. BUFFS    -- com a vida já cheia
            3. PET      -- de novo: a tela de carregamento da instância é onde
                           ele some, e a checagem da porta ficou do outro lado
                           dela
            4. COMIDA   -- por último, porque o cronômetro dela começa a valer
                           daqui (ver `PetFeeder`)
            5. MONTAR   -- e é AQUI que os cronômetros da run começam

        É a ordem da BC, ponto por ponto. O usuário pediu a checagem de pet em
        primeiro lugar; ela acontece antes, na PORTA (`_conferir_o_pet_na_porta`),
        e por isso a sequência aqui dentro pode manter a da BC -- que existe
        porque cada passo depende do estado que o anterior deixa.

        =================================================================
        DEPOIS DAQUI SÓ SE CURA EM EMERGÊNCIA
        =================================================================

        Regra do usuário, 03/09/2026: *"curas em outros momentos só se for
        realmente necessário, pois a cave de HH é bem mais fraca que a cave de
        BC"*. O que sobra no meio da run é o portão de emergência que a
        navegação já aplica em qualquer trajeto (`potions.emergency_pct`), e
        nada mais.
        """
        ctx = self.ctx

        # 1 e 2. VIDA E BUFFS.
        self.combat.curar_ao_entrar()
        self.combat.apply_buffs()

        # 3. PET.
        if ctx.settings.pet.summon_on_login:
            self.combat.ensure_pet()

        # 4. COMIDA DO PET. Exige estar a pé, e a pé fora da cave é o que a
        #    regra proíbe. Se a hora passou lá fora, ela é dada agora -- a
        #    cadência não escorrega porque o `PetFeeder` ancora no vencimento.
        self.combat.feed_pet()

        # 5. MONTARIA. O portão INSISTE até confirmar: dentro da cave não se
        #    anda a pé, porque a pé não se chega no boss.
        self.nav.garantir_montaria_para_andar("atravessar a cave")

        # A RUN PASSA A CONTAR AQUI, e começa mesmo que algo acima tenha
        # falhado: amarrar a contagem ao sucesso do preparo faria a run com
        # problema sumir das estatísticas, e é justamente ela que interessa.
        ctx.stats.begin_run()

        rotulo = mapa_hh.TRECHOS_DOS_BOSSES[self._trecho][0]
        self._ir_para(State.ATE_O_BOSS,
                      f"preparo feito; indo para o {rotulo}")

    def _garantir_o_time(self) -> bool:
        """Monta o time de reset, se houver conta configurada.

        SEM `reset_nick` A CAVE SÓ RENDE NA PRIMEIRA RUN, e isso é dito no log em
        vez de silenciosamente aceito: quem ligou a HH sem conta de reset
        provavelmente não sabe que os bosses não renascem.
        """
        ctx = self.ctx
        nick = self.team.nick_do_reset()
        if not nick:
            if self._voltas_no_estado == 0:
                ctx.log.warning(
                    "HH sem conta de reset configurada: os bosses NÃO renascem "
                    "sem desfazer e refazer o time, então da segunda run em "
                    "diante a cave vem vazia.")
            return True

        # `estado_do_time` E NÃO `in_team`, e a diferença é o `None`.
        #
        # `in_team` achata "não estou em time" e "não consegui ler o time" no
        # mesmo `False` -- o próprio `bot/team.py` documenta que essa confusão já
        # custou caro uma vez, quando `sair_do_time` saía sem clicar porque a
        # leitura tinha falhado. Aqui o desfecho de "não sei" é o mesmo de "não
        # estou": tentar montar. Montar estando em time é barato; entrar sem
        # reset é achar a cave vazia da segunda run em diante.
        #
        # E ESTA LINHA JÁ DERRUBOU O BOT: era `self.team.in_team()`, com
        # parênteses, e `in_team` é `@property`. `TypeError: 'bool' object is
        # not callable` estourava a sessão inteira, o supervisor soltava o
        # controle e recomeçava -- o bot ficava reiniciando na porta da cave a
        # cada 5 s, para sempre. Medido no log de 03/09/2026, 19:02.
        if self.team.estado_do_time is True:
            return True

        if self.team.montar_time():
            return True

        self._falhar(f"não consegui montar time com {nick}", State.RECUPERAR)
        return False

    # ==================================================================
    # ATE_O_BOSS -- o laço dos quatro trechos
    # ==================================================================

    def _do_ate_o_boss(self) -> None:
        """Percorre o trecho atual. Sem montaria, limpa os mobs pelo caminho.

        A LIMPEZA A PÉ VEM DO BOT EM LUA e a razão é dele: montado o personagem
        não para, então limpar só faz sentido a pé. `limpar_mobs_a_cada = 0`
        desliga.
        """
        ctx = self.ctx
        rotulo, caminho, ponto = mapa_hh.TRECHOS_DOS_BOSSES[self._trecho]

        ctx.log.info("HH: indo para o %s (trecho %s/%s, %s waypoints)",
                     rotulo, self._trecho + 1,
                     len(mapa_hh.TRECHOS_DOS_BOSSES), len(caminho))

        # A CÂMERA ANTES DE CADA TRECHO. O clique de minimapa é calculado a
        # partir do centro dele, mas o `via` calibrado de cada waypoint foi
        # medido com a câmera na pose padrão -- e é justamente nas curvas onde o
        # cálculo falha que o `via` entra. Câmera fora do padrão faz a reserva
        # apontar para o lugar errado exatamente quando ela é necessária.
        ctx.apply_camera()

        self.nav.garantir_montaria_para_andar(f"trecho do {rotulo}")

        if not self.nav.seguir_rota(caminho,
                                    max_seconds=MAX_SEGUNDOS_POR_TRECHO):
            self._falhar(f"não cheguei no {rotulo}", State.RECUPERAR)
            return

        self._limpar_os_mobs_do_caminho(rotulo)

        # DESMONTA ANTES DE LUTAR: montado o jogo recusa as skills.
        self.nav.ensure_dismounted()
        ctx.log.info("HH: no ponto do %s (%s)", rotulo, ponto)
        self._ir_para(State.BOSS)

    def _limpar_os_mobs_do_caminho(self, rotulo: str) -> None:
        """A PÉ, limpa os mobs que vieram atrás. Montado, não faz nada.

        =================================================================
        VEM DO BOT EM LUA, E A RAZÃO É DELE
        =================================================================

        `travelPath` limpa a cada 3 passos quando `MOUNT ~= "ON"` e não limpa
        nada montado -- *"com montaria ON o char nao para: so mata nos bosses"*.
        A decisão está certa: montado o personagem atravessa, e atravessar é o
        que torna a run curta.

        A PÉ é outra história: sem montaria o trem de mobs alcança, e chegar no
        boss com quatro mobs somando dano por trás é o que perde a run.

        `limpar_mobs_a_cada = 0` desliga -- é o modo "confio na montaria".

        NUNCA DERRUBA A RUN. Limpar é prevenção; levantar aqui custaria a
        instância já gasta.
        """
        ctx = self.ctx
        a_cada = ctx.settings.hh.limpar_mobs_a_cada
        if a_cada <= 0:
            return
        if ctx.memory.is_mounted():
            # Montado o personagem não para -- e parar aqui seria desfazer
            # justamente o que a montaria compra.
            return

        try:
            ctx.log.info("HH: a pé no trecho do %s; limpando os mobs do caminho",
                         rotulo)
            self.combat.limpar_o_combate(f"caminho do {rotulo}")
        except StopRequested:
            raise
        except Exception as exc:
            ctx.log.warning("HH: limpeza do caminho falhou (segue a run): %s",
                            exc)

    # ==================================================================
    # BOSS
    # ==================================================================

    def _do_boss(self) -> None:
        """Luta com o ritual do BC, cata o loot, e HONRA o desfecho.

        =================================================================
        O RITUAL É O DO BC, E ISSO É O PONTO
        =================================================================

        `CombatEngine.lutar_contra_um_boss` traz tudo que a Bewitcher Cave
        aprendeu numa luta de boss: desmontar antes (montado o jogo recusa as
        skills), esperar a flag com prazo CURTO e sem beber poção na frente do
        boss, conferir MORTE antes de bater, TAB de aquisição quando o boss não
        vem sozinho, `exige_ter_entrado` para a confirmação não declarar vitória
        em 1,5 s, golpe durante a confirmação de saída, e o placar no disco no
        fim da luta.

        A versão anterior desta função fazia uma fração disso -- e passava
        `alvo_esperado` com os rótulos de comentário do bot em Lua, nomes que
        nunca foram medidos. O portão de nome devolvia `acabaram` na primeira
        leitura e a luta terminava SEM UM GOLPE, reportando vitória.

        =================================================================
        E O DESFECHO É HONRADO
        =================================================================

        A versão anterior descartava o `fim`: avançava o trecho sempre. Morrer
        no boss 2 fazia o bot seguir para o boss 3 -- morto, sem vida, sem pet.
        Agora derrota manda para RECUPERAR, que é quem sabe se o personagem
        reviveu dentro ou fora da cave.
        """
        ctx = self.ctx
        rotulo, _caminho, ponto = mapa_hh.TRECHOS_DOS_BOSSES[self._trecho]

        # NÃO SE ESPERA COMBATE DE LONGE. Absorvido do `BossRushRoutine._do_boss`:
        # se o personagem não está no ponto, ele volta a andar em vez de ficar
        # parado esperando uma flag que não vai ligar.
        #
        # Sem leitura de posição segue: recusar aqui travaria a run, e quem
        # decide então é a flag de combate ligar ou não.
        pos = ctx.memory.position()
        if pos is not None and mapa_hh.distancia(pos, ponto) > TOLERANCIA_DO_PONTO:
            ctx.log.info(
                "HH: não estou no ponto do %s (estou em %s, o ponto é %s). Volto "
                "a andar antes de esperar o combate.", rotulo, pos, ponto)
            self._ir_para(State.ATE_O_BOSS)
            return

        # A CURA VEM ANTES DE ENCOSTAR, e não depois da luta.
        #
        # Na frente do boss não se bebe poção -- ele encosta e o efeito para na
        # hora. É o mesmo motivo de o BC curar no fim da fase dos guardas, antes
        # de andar até o boss.
        self.combat.curar_antes_do_boss()
        if ctx.snapshot().dead:
            self._falhar(f"morri antes de encostar no {rotulo}")
            return

        fim = self.combat.lutar_contra_um_boss(
            rotulo, tabs_ao_morrer=mapa_hh.tabs_ao_morrer(rotulo))
        ctx.log.info("HH: %s -- %s", rotulo, fim.resumo())

        # `saiu_de_combate` É A VITÓRIA, e é como a BC lê o mesmo objeto
        # (`_do_boss`: `venceu = fim.saiu_de_combate`). Morte, prazo estourado e
        # flag ilegível devolvem False.
        if not fim.saiu_de_combate:
            self._falhar(f"não venci o {rotulo}: {fim.motivo}")
            return

        self._catar_o_loot()
        self._recuperar_entre_os_bosses(rotulo)

        self._trecho += 1
        if self._trecho >= len(mapa_hh.TRECHOS_DOS_BOSSES):
            self._ir_para(State.SAIR, "quatro bosses feitos; saindo")
        else:
            proximo = mapa_hh.TRECHOS_DOS_BOSSES[self._trecho][0]
            self._ir_para(State.ATE_O_BOSS, f"indo para o {proximo}")

    def _recuperar_entre_os_bosses(self, rotulo: str) -> None:
        """Senta para recuperar, se a vida pedir. Absorvido do BC.

        O BC senta depois da fase dos guardas (`SEGUNDOS_SENTADO_APOS_GUARDAS`)
        porque é o único lugar da run onde ficar parado é seguro. Na HH os
        equivalentes são os intervalos entre os quatro bosses: o ponto está
        limpo, e o trecho seguinte começa com um trajeto.

        SÓ SE PRECISAR. `precisa_curar` é o portão -- sentar com a vida cheia
        seria pagar segundos por nada em toda run saudável.
        """
        ctx = self.ctx
        estado = ctx.snapshot()
        if not self.combat.precisa_curar(estado.hp_pct):
            return
        ctx.log.info("HH: vida %.0f%% depois do %s -- sentando para recuperar",
                     estado.hp_pct, rotulo)
        self.combat.sentar_para_recuperar()

    def _catar_o_loot(self) -> None:
        """Recolhe o loot do chão, para quem não tem pet com auto-pick.

        `usar_catador` é POR CONTA: o usuário tem contas com o pet certo e contas
        sem ele, e um interruptor global obrigaria a escolha errada para metade
        delas.
        """
        ctx = self.ctx
        if not ctx.settings.usar_catador:
            return

        # NUNCA DERRUBA A RUN. Falhar em catar custa itens; levantar aqui
        # custaria a run inteira, com o boss já morto e a instância gasta.
        try:
            resultado = catador.catar(
                ponto_do_loot=ctx.coords.loot,
                localizar_botao=self._onde_esta_o_pick_up_all,
                clicar_direito=ctx.right_click,
                clicar_esquerdo=ctx.click,
                esperar=ctx.tick,
                log=ctx.log,
            )
            ctx.log.info("HH catador: %s", resultado)
        except StopRequested:
            raise
        except Exception as exc:
            ctx.log.warning("HH: catador falhou (segue a run): %s", exc)

    def _onde_esta_o_pick_up_all(self) -> tuple[int, int] | None:
        """Onde está o botão de recolher, se estiver na tela.

        É ELE, E SÓ ELE, que autoriza um clique esquerdo -- o esquerdo na cena
        3D faz o personagem ANDAR, e andar no ponto do boss é sair da rota.
        """
        ctx = self.ctx
        tpl = ctx.templates.load(TEMPLATE_PICK_UP_ALL)
        if tpl is None:
            return None
        quadro = capture_window(ctx.hwnd)
        if quadro is None:
            return None
        return find_template(quadro, tpl, threshold=LIMIAR_DO_PICK_UP_ALL)

    # ==================================================================
    # SAIR
    # ==================================================================

    def _do_sair(self) -> None:
        """Volta ao ponto de saída e sai pelo NPC."""
        ctx = self.ctx
        self.nav.garantir_montaria_para_andar("saída da cave")
        if not self.nav.seguir_rota(mapa_hh.CAMINHO_ATE_A_SAIDA,
                                    max_seconds=MAX_SEGUNDOS_POR_TRECHO):
            self._falhar("não cheguei no ponto de saída", State.RECUPERAR)
            return

        ctx.stats.end_run(ok=True)
        self._publicar_onde_estou(dentro=False)
        self._ir_para(State.MANUTENCAO, "run concluída")

    # ==================================================================
    # MANUTENCAO -- vender, deletar, e o ciclo de time
    # ==================================================================

    def _do_manutencao(self) -> None:
        """Vender se precisar, e refazer o time para os bosses renascerem.

        NO MODO FADA O CICLO DE TIME É AQUI, e não no `ENTRAR`: as duas
        atravessaram a cave juntas, então o time só pode ser desfeito depois de
        sair. Desfaz, refaz, e só então a próxima entrada tem bosses.
        """
        ctx = self.ctx

        if self._precisa_vender():
            self._vender()
            self._runs_na_ultima_venda = ctx.stats.runs

        if ctx.settings.hh.modo_do_reset == MODO_FADA_DA_HH:
            self._reciclar_o_time()

        self._ir_para(State.PREPARAR, "manutenção feita; próxima run")

    def _vender(self) -> None:
        """A venda no `Roaming Apothecary`, do lado de fora da cave."""
        ctx = self.ctx
        ctx.log.info("HH: indo vender no %s", self.vendedor.NOME_DO_VENDEDOR)
        vendidos = self.vendedor.vender()
        ctx.log.info("HH: %s slot(s) vendido(s)", vendidos)

    def _publicar_onde_estou(self, *, dentro: bool) -> None:
        """Conta à Fada se o líder está dentro da cave.

        É o único sinal que ela precisa do líder, e ele existe porque a ordem de
        entrada importa: a Fada espera este aviso para entrar atrás.

        NUNCA LEVANTA. O mural é conveniência entre contas; falhar em publicar
        faz a Fada esperar o teto dela e entrar de qualquer forma -- que é o
        comportamento certo, e está documentado lá.
        """
        try:
            mural.publicar_estado(self.ctx.account_login,
                                  dentro_da_hh=bool(dentro))
        except Exception as exc:
            self.ctx.log.debug("HH: não publiquei o estado no mural (%s)", exc)

    def _reciclar_o_time(self) -> None:
        """Desfaz e refaz o time. É o que faz os bosses renascerem.

        REGRA DO JOGO, não do bot -- e por isso não é opcional no modo fada.
        """
        ctx = self.ctx
        if not ctx.settings.hh.reset_nick.strip():
            return
        ctx.log.info("HH+Fada: desfazendo o time para os bosses renascerem")
        self.team.sair_do_time()

    # ==================================================================
    # RECUPERAR
    # ==================================================================

    def _do_recuperar(self) -> None:
        """Algo saiu do roteiro. Volta a se situar, sem inventar.

        MORTE ENTRA AQUI. O personagem morto revive dentro ou fora da cave, e
        `_do_situar` já sabe distinguir os dois pela coordenada -- que é
        exatamente o que o bot em Lua faz com `if ptr.getX() > 0`.
        """
        ctx = self.ctx
        estado = ctx.snapshot()
        if estado.dead:
            # A RUN CONTA COMO PERDIDA UMA VEZ SÓ.
            #
            # `_do_recuperar` volta a cada 2 s enquanto o personagem está morto,
            # e chamar `end_run` em todas inflava o contador de falhas -- uma
            # morte apareceria como dezenas de runs perdidas no placar.
            if not self._contou_a_morte:
                self._contou_a_morte = True
                ctx.log.warning("HH: personagem morto; aguardando o revive")
                ctx.stats.end_run(ok=False)
            ctx.tick(2.0)
            return

        self._contou_a_morte = False

        self._trecho = 0
        self._ir_para(State.SITUAR, "recuperando: vou me situar de novo")


__all__ = ["ESTADOS_DENTRO_DA_CAVE", "HHRoutine", "State"]
