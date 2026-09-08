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
from ...core import catador, diario, esconder_jogadores, logmodo
from ...core.vision import capture_window, find_template
from .. import mural
from ..combate import CombatEngine
from ..context import (
    BotContext,
    Disconnected,
    FarmDesligado,
    StopRequested,
)
from ..espera_do_reseter import esperar_o_reseter
from ..navegacao import Navigator, PersonagemMortoNoPortao
from ..team import TeamService
from . import bosses, mapa_hh
from .entrada import EntradaDaHH
from .manutencao import ManutencaoDaHH
from .ponto_do_boss import do_trecho
from .progresso import ProgressoDaCave
from .vendedor import VendedorDaHH

# ---------------------------------------------------------------------------
# Tempos e tetos
# ---------------------------------------------------------------------------

# Teto da tentativa de chegar na porta da cave. A viagem passa por dois painéis
# de arredores e um teleporte; acima disto algo está errado de verdade.
MAX_SEGUNDOS_ATE_A_PORTA = 10 * 60.0

# Teto da rajada de tentativas de entrar. UMA HORA, e é o número do BC.
#
# Não é generosidade: a instância pode estar cheia, e desistir devolve o
# personagem para o começo do ciclo sem ter feito nada. Uma hora de tentativa
# custa quase zero (a tentativa é clique e leitura de memória) e ainda entra;
# desistir em 5 minutos custa a run inteira. Regra do usuário, 03/09/2026:
# *"tem que ficar fazendo as tentativas para entrar, como é feito em BC, pois
# são várias e várias tentativas até conseguir entrar"*.
MAX_SEGUNDOS_NA_PORTA = 1 * 60 * 60.0

# Entre uma tentativa de entrada e a seguinte. É o RESTO do orçamento da
# disputa, não um gasto: a tentativa em si (dois cliques mais a confirmação
# curta) é que leva o tempo. Mesmo valor do BC.
ENTRE_TENTATIVAS_DE_ENTRAR = 0.025

# De quantas em quantas tentativas escrever uma linha no log.
#
# Sem isto a disputa enche o log com uma linha por tentativa -- são milhares por
# hora. Com isto o log continua dizendo "estou tentando", que é a informação que
# interessa, sem afogar todo o resto.
TENTATIVAS_POR_LINHA_DE_LOG = 15

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

# Quanto esperar, num ponto de batalha, para a flag de combate LIGAR.
#
# Número do usuário, 03/09/2026: *"sempre que tiver em um waypoint de ataque
# deve esperar no máximo 5 segundos para entrar em batalha, caso não entre em
# batalha pode continuar para os próximos waypoints"*. E ele confirmou que vale
# no ponto do BOSS também.
#
# É O QUE TORNA BARATO REFAZER UM TRECHO JÁ LIMPO -- e é por isso que existe.
# Depois de uma morte o bot volta pelo começo da perna; num ponto onde não
# sobrou nada, cinco segundos de silêncio dizem "aqui já foi" e ele segue.
#
# O QUE ISSO CUSTA, e está escrito para aparecer no log quando acontecer: um
# boss VIVO que demore mais de 5 s para agredir é pulado, e a run perde esse
# boss. O usuário foi avisado e escolheu assim -- ver `docs/decisoes/hh.md`.
SEGUNDOS_PARA_ENGAJAR = 5.0

# Quanto esperar, por tentativa, a volta ao ponto depois da luta.
#
# Mesmo valor que `entrada.SEGUNDOS_POR_TENTATIVA_DE_ENCOSTAR` usa para encostar
# no NPC: é a mesma ação (um clique de minimapa e a caminhada até lá), e o
# trajeto aqui é ainda mais curto.
SEGUNDOS_POR_TENTATIVA_DE_VOLTAR = 1.8

# Teto para conseguir sair da cave pelo NPC.
#
# Bem menor que o da ENTRADA (uma hora) porque a natureza é outra: entrar
# disputa vaga com outros jogadores e depende deles saírem; sair não depende de
# ninguém -- se não sai, é o clique que está errando o NPC, e insistir cinco
# minutos já dá dezenas de tentativas. Passou disso, RECUPERAR se situa de novo.
MAX_SEGUNDOS_PARA_SAIR = 5 * 60.0

# Entre uma tentativa de sair e a seguinte. Maior que o da entrada porque cada
# tentativa aqui inclui um diálogo inteiro (abrir, achar o link, clicar), e não
# dois cliques guardados.
ENTRE_TENTATIVAS_DE_SAIR = 1.0

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
        # LIGA O PORTÃO DA MONTARIA NO COMBATE, e esta linha faltava.
        #
        # Em batalha o jogo RECUSA montar, e o portão insiste sem teto. Sem esta
        # ligação `_diagnosticar_o_portao` lia a flag, concluía "estou em
        # batalha" e só sabia dizer *"não tenho destravamento ligado; sigo
        # insistindo"* -- o bot ficava apertando a tecla da montaria contra uma
        # recusa do jogo até os mobs morrerem por conta própria.
        #
        # Medido no log de 03/09/2026, 23:44: **41 segundos** parado no meio da
        # cave, com o trem de mobs em cima. É o mesmo defeito que custou 24
        # minutos à BC em 31/08 e que a linha gêmea (`bc/routine.py`) conserta
        # lá desde então.
        #
        # A ROTINA É QUEM PODE FAZER A LIGAÇÃO: `combate` já importa
        # `navegacao`, e o contrário faria ciclo.
        # O DESTRAVAMENTO PASSA PELA MIRA NA HH, e é por isso que o gancho
        # aponta para um método daqui e não direto para o motor: a coreografia
        # de `limpar_o_combate` é compartilhada com o BC e não pode ganhar um
        # F1 que só a HH pediu.
        self.nav.destravar_o_combate = self._destravar_o_combate
        # E TAMBÉM QUANDO O TRAJETO TRAVA -- isto é decisão DESTA cave.
        #
        # Regra do usuário, 04/09/2026: *"é importante não deixar ficar sem
        # progresso, arranjar uma forma de continuar a cave, mas sem pular a
        # morte dos boss, pois aqui em HH, junto com os boss, tem vários mobs
        # que precisam ser mortos"*. Matar é continuar.
        #
        # O BC NÃO LIGA ESTE, e a diferença é regra dele: nunca sair da montaria
        # antes do waypoint dos Gun Witch. Ver `bot/navegacao.py`, o bloco dos
        # dois ganchos.
        self.nav.matar_quando_o_trajeto_trava = (
            self._matar_ate_sair_de_batalha)
        self.ui = EntradaDaHH(ctx, self.nav)
        self.vendedor = VendedorDaHH(ctx, self.nav)
        # O QUE ACONTECE FORA DA CAVE, entre uma run e a seguinte: descarte do
        # lixo e venda. Mora em `hh/manutencao.py` -- são decisões que não
        # falam com a máquina de estados nem sabem em que trecho a run parou.
        self.manutencao = ManutencaoDaHH(ctx, self.vendedor)
        self.team = TeamService(
            ctx, nick_do_reset=lambda: ctx.settings.reset_nick)
        self.state = State.SITUAR
        # O PROGRESSO DOS TRECHOS TEM DONO, e é `hh/progresso.py`.
        #
        # Eram três campos soltos aqui (`_trecho`, `_trechos_feitos`,
        # `_run_em_andamento`), lidos e escritos em seis lugares sem nenhum que
        # declarasse "a run começou" ou "acabou" -- e foi dessa dispersão que
        # nasceu o `IndexError` em SITUAR de 05/09/2026.
        self.progresso = ProgressoDaCave(len(mapa_hh.TRECHOS_DOS_BOSSES))
        self._voltas_no_estado = 0
        self._ultimo_estado: State | None = None
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
            ctx.settings.reset_nick or "sem conta de reset",
            ctx.settings.mount_speed_pct,
            ctx.settings.hh.vendor.sell_start_slot,
        )
        # Começa SITUANDO, nunca preparando: uma conta que já está no meio da
        # cave continua de onde estava, em vez de tentar entrar estando dentro --
        # o que faria o clique cair no chão e tirar o personagem da rota.
        self.state = State.SITUAR
        # LIGAR A HH ZERA A LIMPA DA LARGADA. A rotina é guardada pelo
        # supervisor e sobrevive a desligar/ligar o farm; sem isto, só a
        # primeira largada da sessão limpava a bolsa.
        self.manutencao.a_hh_comecou()

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

                anterior = self.state
                handler = getattr(self, f"_do_{self.state.name.lower()}")
                try:
                    handler()
                except (StopRequested, Disconnected):
                    # Parar a conta e cair são do supervisor, não daqui.
                    raise
                except FarmDesligado:
                    # DESLIGAR A HH NÃO É DEFEITO.
                    #
                    # `ctx.tick` chama `raise_if_stopped`, que detona
                    # `FarmDesligado` assim que o interruptor da cave cai -- e
                    # `tick` é chamado de dentro da navegação, do combate e da
                    # venda. Sem este ramo a exceção subia até o supervisor,
                    # que a registrava como "Erro inesperado na sessão" COM
                    # TRACEBACK e derrubava a sessão inteira: a conta soltava o
                    # controle e refazia login, janela e contexto.
                    #
                    # Medido no log de 03/09/2026: **15 vezes em 33 minutos**,
                    # cada uma reconstruindo a sessão. É o mesmo desenho que a
                    # BC já tinha em `bc/routine.py`.
                    ctx.log.info(
                        "HH desligada no meio de %s; devolvendo o controle "
                        "(a conta fica online, parada)", anterior.name)
                    return
                except PersonagemMortoNoPortao as exc:
                    # O portão da montaria avisando que não há o que insistir:
                    # cadáver não monta. Não é exceção inesperada, e o desfecho
                    # é o mesmo do `_guard()` ao ver o personagem morto.
                    ctx.log.warning("%s. Indo para RECUPERAR.", exc)
                    self.state = State.RECUPERAR
                except Exception as exc:
                    ctx.log.exception("HH: erro no estado %s: %s",
                                      anterior.name, exc)
                    diario.registrar_evento(
                        ctx.account_login, "excecao",
                        f"HH {anterior.name}: {type(exc).__name__}: {exc}",
                        ctx.memory.position(), ctx.memory.location(),
                    )
                    self._falhar(f"exceção em {anterior.name}")

                ctx.tick(PASSO_DENTRO_DA_CAVE
                         if self.state in ESTADOS_DENTRO_DA_CAVE
                         else PASSO_FORA_DA_CAVE)
        except FarmDesligado:
            # REDE DE SEGURANÇA: o `ctx.tick` do fim do laço e o `_guard()` do
            # começo ficam FORA do `try` do handler. A HH pode apagar ali
            # também, e o desfecho tem de ser o mesmo -- controle devolvido
            # limpo, sem derrubar a sessão.
            ctx.log.info("HH desligada; devolvendo o controle")
            return
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

        QUEM RESPONDE É `mapa_hh.etapa_pelo_lugar`, lendo NOME e COORDENADA
        juntos -- a regra da verificação dupla que o usuário pediu em
        04/09/2026. As quatro etapas e o porquê de cada régua estão lá; aqui só
        se obedece.

        SEM LEITURA DE POSIÇÃO NÃO SE DECIDE NADA: sem saber onde está, qualquer
        escolha é chute, e chute aqui significa clicar no NPC errado ou andar
        para o lado oposto. Espera a leitura voltar.

        O NOME, ESSE, PODE FALTAR. Ele só refina o lado de FORA (já passei do
        teleporte?), e o desfecho de não saber é a viagem completa -- que
        funciona de qualquer lugar. Bloquear por falta de nome seria trocar uma
        viagem a mais por uma conta parada.
        """
        ctx = self.ctx
        pos = ctx.memory.position()
        if pos is None:
            ctx.log.info("HH: sem leitura de posição; aguardando para me situar")
            ctx.tick(1.0)
            return

        etapa = mapa_hh.etapa_pelo_lugar(ctx.memory.location(), pos)

        if etapa == mapa_hh.ETAPA_DENTRO:
            self._retomar_dentro_da_cave(pos)
            return

        self._ir_para(State.PREPARAR, f"{etapa} ({pos}); preparando")

    def _retomar_dentro_da_cave(self, pos: tuple[int, int]) -> None:
        """Já estou dentro: descobre por qual trecho continuar.

        =================================================================
        O TRECHO EM ANDAMENTO GANHA DA DISTÂNCIA
        =================================================================

        Quem morre no trecho 3 revive no começo da cave, e dali um waypoint do
        trecho 1 fica mais perto que qualquer coisa do 3 -- os quatro trechos se
        cruzam no mapa. Escolher pela distância refaria os bosses já mortos, e
        encontraria as salas vazias: o reset só acontece na SAÍDA.

        Então a distância só decide quando NÃO HÁ run em andamento, que é o caso
        de abrir o bot com o personagem já dentro da cave. Nesse caso ele não
        tem como saber o que já foi feito, e os 5 s de espera em cada ponto de
        batalha (`SEGUNDOS_PARA_ENGAJAR`) é que resolvem: ponto limpo não
        engaja, e o bot segue.
        """
        if self.progresso.em_andamento:
            # ===========================================================
            # "TODOS OS TRECHOS FEITOS" É UM ESTADO LEGÍTIMO
            # ===========================================================
            #
            # `_avancar_o_trecho` deixa `_trecho == len(TRECHOS)` no intervalo
            # entre matar o último boss e sair da cave. Nesse intervalo não há
            # trecho para retomar -- há uma SAÍDA pendente.
            #
            # Sem este ramo a linha de baixo indexava a tupla fora do fim e
            # estourava `IndexError`. Medido no log de 05/09/2026: o usuário
            # desligou a HH às 20:02:14 com "os quatro feitos, saindo" e religou
            # às 20:02:35 -- SITUAR estourou ONZE vezes em dez segundos, cada
            # uma virando `exceção em SITUAR` -> RECUPERAR -> SITUAR.
            #
            # POR QUE O ESTADO ATRAVESSA O DESLIGA/LIGA: a rotina é guardada em
            # `supervisor._rotina_da_hh` de propósito -- recriá-la a cada volta
            # do laço externo faria a run voltar ao primeiro boss. O preço é que
            # `_trecho` sobrevive, e quem lê tem de estar preparado.
            if self.progresso.acabou():
                self._ir_para(
                    State.SAIR,
                    f"de volta DENTRO da cave em {pos}; os "
                    f"{self.progresso.total} trechos já estão "
                    f"feitos -- o que falta é sair")
                return

            rotulo = mapa_hh.TRECHOS_DOS_BOSSES[self.progresso.trecho][0]
            self._ir_para(
                State.PREPARAR_DENTRO,
                f"de volta DENTRO da cave em {pos}; a run continua no trecho do "
                f"{rotulo} ({self.progresso.feitos} de "
                f"{self.progresso.total} já feitos)")
            return

        melhor, menor = 0, float("inf")
        for i, (_rotulo, caminho, _ponto) in enumerate(mapa_hh.TRECHOS_DOS_BOSSES):
            _indice, dist = mapa_hh.mais_proximos(pos, caminho)[0]
            if dist < menor:
                melhor, menor = i, dist

        self.progresso.pular_para(melhor)
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
        if self.manutencao.precisa_vender():
            self._ir_para(State.MANUTENCAO, "a bolsa pede venda antes de entrar")
            return

        # MONTARIA PARA VIAJAR. A regra do usuário é curta: *"a montaria você
        # irá sempre que precisar, dentro e fora da cave"* -- e só desce para
        # atacar. Aqui é o começo de um trajeto, então sobe.
        self.nav.garantir_montaria_para_andar("ir até a porta da HH")

        self._ir_para(State.ATE_A_PORTA, "indo para a porta da cave")


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
        etapa = mapa_hh.etapa_pelo_lugar(
            ctx.memory.location(), ctx.memory.position())

        if etapa == mapa_hh.ETAPA_NA_PORTA:
            if self.ui.garantir_coordenada_da_entrada():
                self.manutencao.descartar_o_lixo_ao_comecar()
                self._conferir_o_pet_na_porta()
                self._ir_para(State.ENTRAR, "já estou na porta")
                return

        # O TELEPORTE DA FAY SÓ SE EU AINDA NÃO PASSEI POR ELE: estando onde
        # ela deposita, ou mais perto, quem responde é o NOME do lugar e não o
        # X e Y. Refazer o teleporte dali levaria o personagem de volta para
        # Stone City, para LONGE da cave. Ver `docs/decisoes/hh.md` §17.
        if etapa not in (mapa_hh.ETAPA_NA_VIZINHANCA, mapa_hh.ETAPA_NA_PORTA):
            if not self.ui.viajar_para_a_hh():
                self._falhar("não consegui viajar para a HH", State.RECUPERAR)
                return
        else:
            ctx.log.info(
                "HH: %s -- pulo o teleporte da Fay e vou direto pelos "
                "arredores", etapa)

        if not self.ui.ir_ate_o_npc_da_hh():
            self._falhar("não cheguei na porta da cave", State.RECUPERAR)
            return

        self.manutencao.descartar_o_lixo_ao_comecar()
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

        F12 PRESO DURANTE A RAJADA. Daqui saem cliques na cena 3D disputando a
        vaga, e um jogador parado na frente do NPC engole todos eles.

        =================================================================
        A RAJADA É A DO BC, E A FORMA DELA É O PONTO
        =================================================================

        Regra do usuário, 03/09/2026: *"tem que ficar fazendo as tentativas para
        entrar, como é feito em BC, pois são várias e várias tentativas até
        conseguir entrar, pois pode estar cheio a cave"*.

        Quatro coisas vieram de lá, e cada uma resolve um jeito de a disputa
        fracassar:

          * TETO DE UMA HORA em vez de cinco minutos. Desistir devolve o
            personagem ao começo do ciclo sem ter feito nada.
          * CONFIRMAÇÃO CURTA (0,25 s, ver `entrada.TETO_DA_ENTRADA`) em vez de
            dois segundos. Enquanto o bot esperava, ninguém estava tentando.
          * VOLTAR À COORDENADA quando o personagem deriva. Fora do ponto de
            conversa todo clique erra o NPC, e cada erro empurra mais.
          * REDESCOBRIR SÓ NA FALHA MECÂNICA. Instância cheia é a razão normal
            de não entrar; redescobrir por causa dela custaria segundos por
            tentativa.

        E o fracasso do teto volta para `ATE_A_PORTA`, não para `RECUPERAR`:
        uma hora na porta sem entrar não é queda nem morte -- é a cave cheia, e
        a resposta certa é refazer o caminho e tentar de novo.
        """
        ctx = self.ctx
        if not self._garantir_o_time():
            return

        self.ui.preparar_entrada()
        comeco = time.time()
        limite = comeco + MAX_SEGUNDOS_NA_PORTA
        tentativa = 0

        # REAFIRMA A TECLA PRESA -- o mesmo que o BC faz antes de cada
        # tentativa de entrada. Tecla fisicamente presa repete sozinha, e
        # reafirmar é o que devolve o esconder depois de um relogin (janela
        # nova, estado zerado). Ver `esconder_jogadores.prender_a_tecla`.
        esconder_jogadores.prender_a_tecla(
            ctx.settings.keys.hide_players, ctx.segurar_para_sempre, ctx.log)

        with esconder_jogadores.segurado(
                tecla=ctx.settings.keys.hide_players,
                segurar=ctx.key_down, soltar=ctx.key_up, log=ctx.log):
            while time.time() < limite:
                self._guard()
                tentativa += 1

                # ANTES DE CLICAR: ainda estou onde a cave pode ser aberta?
                pos = ctx.memory.position()

                # Entrei numa tentativa anterior e só descobri agora. Acontece
                # quando o servidor demora mais que a janela de confirmação.
                if mapa_hh.esta_dentro_da_hh(pos):
                    ctx.log.info(
                        "Já estou dentro da HH em %s (tentativa %s, %.0fs de "
                        "disputa)", pos, tentativa, time.time() - comeco)
                    self._entrou()
                    return

                # DERIVA. Um mob que empurra, um clique que escorregou, e o
                # personagem sai da coordenada de conversa -- daí em diante todo
                # clique erra o NPC, e cada erro faz o personagem andar mais.
                # Voltar é mais barato que insistir de longe. Igual ao BC.
                if pos is not None and mapa_hh.distancia(
                        pos, mapa_hh.PONTO_DA_ENTRADA
                ) > mapa_hh.PRECISAO_NO_PONTO_DA_ENTRADA:
                    self.ui.garantir_coordenada_da_entrada()
                    continue

                # `False` = a MECÂNICA falhou (o diálogo não abriu, o clique não
                # pegou). `True` = os dois cliques saíram e o pedido foi feito.
                cliques_sairam = self.ui.tentar_entrar_na_hh()

                if self.ui.esperar_entrar():
                    ctx.log.info(
                        "DENTRO da HH na tentativa %s (%.0fs de disputa)",
                        tentativa, time.time() - comeco)
                    self._entrou()
                    return

                # SÓ A FALHA MECÂNICA CONTA para a redescoberta do NPC e do
                # link. Instância cheia é a razão NORMAL de não entrar, e
                # redescobrir por causa dela custaria segundos por tentativa no
                # meio da disputa.
                if not cliques_sairam:
                    self.ui.registrar_falha_de_entrada()

                if tentativa % TENTATIVAS_POR_LINHA_DE_LOG == 0:
                    ctx.log.info(
                        "Ainda do lado de fora da HH depois de %s tentativas "
                        "(%.0fs). A instância deve estar cheia; continuo.",
                        tentativa, time.time() - comeco)

                ctx.tick(ENTRE_TENTATIVAS_DE_ENTRAR)

        self._falhar(
            f"não entrei na HH em {MAX_SEGUNDOS_NA_PORTA / 60:.0f} min "
            f"({tentativa} tentativas)", State.ATE_A_PORTA)

    def _entrou(self) -> None:
        """Dentro. No modo solo, o time é desfeito AQUI.

        A CONTAGEM DA RUN NÃO COMEÇA AQUI, e sim no `_do_preparar_dentro` --
        mesmo desenho da BC. A disputa da porta pode ter levado uma hora e o
        preparo leva mais alguns segundos; contar a run a partir daí é o que
        torna o tempo por run comparável entre uma volta e outra.
        """
        ctx = self.ctx
        # ENTRADA NOVA, INSTÂNCIA NOVA: os quatro bosses estão vivos de novo.
        self.progresso.entrei_na_cave()

        if ctx.settings.hh.modo_do_reset != MODO_FADA_DA_HH:
            # SOLO: a conta de reset já cumpriu o papel dela. Desfazer agora é o
            # que faz os bosses renascerem para a PRÓXIMA run -- e é o mesmo
            # desenho da BC.
            if ctx.settings.reset_nick:
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

        # ===============================================================
        # NO MEIO DA CAVE NÃO SE VERIFICA NADA
        # ===============================================================
        #
        # Regra do usuário, 04/09/2026: *"as verificações são somente na entrada
        # da cave, se tiver no meio da cave não deve ser verificado nada, então
        # só naquele waypoint inicial você faz as verificações e usa os buffs"*.
        #
        # O motivo é o mesmo que tirou o preparo de FORA da cave, um degrau
        # adiante: tudo isto exige estar A PÉ, e a pé no meio da cave é o trem
        # de mobs encostando. Quem chega aqui sem ser pela porta é quem morreu e
        # reviveu dentro, ou quem abriu o bot com a run em andamento -- e nos
        # dois casos o que urge é voltar a andar, não beber poção parado.
        #
        # A MONTARIA NÃO É "VERIFICAÇÃO", e por isso continua: é a condição para
        # andar, e a pé o personagem não chega no boss. Regra medida.
        if not mapa_hh.acabei_de_entrar(ctx.memory.position()):
            ctx.log.info(
                "HH: retomando no meio da cave -- só garanto a montaria. Buff, "
                "poção e comida ficam para a próxima entrada.")
            self.nav.garantir_montaria_para_andar("atravessar a cave")
            ctx.stats.begin_run()
            self.progresso.a_run_comecou()
            rotulo = mapa_hh.TRECHOS_DOS_BOSSES[self.progresso.trecho][0]
            self._ir_para(State.ATE_O_BOSS, f"seguindo para o {rotulo}")
            return

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
        self.progresso.a_run_comecou()

        rotulo = mapa_hh.TRECHOS_DOS_BOSSES[self.progresso.trecho][0]
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

        # `estado_do_time` E NÃO `in_team`, e a diferença é o `None`: aqui o
        # desfecho de "não sei" é o mesmo de "não estou" -- tentar montar.
        # Montar estando em time é barato; entrar sem reset é achar a cave
        # vazia da segunda run em diante.
        #
        # E ESTA LINHA JÁ DERRUBOU O BOT, com `in_team()` numa `@property`.
        # Ver `docs/decisoes/hh.md` §19.
        if self.team.estado_do_time is True:
            return True

        # O PORTÃO DO RESETER -- único ponto de trava da HH, e AQUI porque este
        # é o instante em que o reseter é NECESSÁRIO: travar mais cedo pararia
        # a conta por um problema que só afeta a entrada, perdendo até a
        # travessia já feita. E depois do `estado_do_time`, porque quem já está
        # em time não precisa de convite. A trava é a MESMA do BC
        # (`bot/espera_do_reseter.py`). Ver `docs/decisoes/hh.md` §19.
        esperar_o_reseter(ctx, onde="no portão do time da HH")

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
        rotulo, caminho, ponto = mapa_hh.TRECHOS_DOS_BOSSES[self.progresso.trecho]

        ctx.log.info("HH: indo para o %s (trecho %s/%s, %s waypoints)",
                     rotulo, self.progresso.trecho + 1,
                     len(mapa_hh.TRECHOS_DOS_BOSSES), len(caminho))

        # A CÂMERA ANTES DE CADA TRECHO. O clique de minimapa é calculado a
        # partir do centro dele, mas o `via` calibrado de cada waypoint foi
        # medido com a câmera na pose padrão -- e é justamente nas curvas onde o
        # cálculo falha que o `via` entra. Câmera fora do padrão faz a reserva
        # apontar para o lugar errado exatamente quando ela é necessária.
        ctx.apply_camera()

        self.nav.garantir_montaria_para_andar(f"trecho do {rotulo}")

        # POR QUAL WAYPOINT COMEÇAR -- e quase nunca é o primeiro. O trecho é
        # REFEITO sempre que a run volta para cá (boss longe do ponto, rollback,
        # personagem arrastado na luta), e nesses casos ele está no FIM do
        # trecho. Clicar o waypoint 1 dali manda o minimapa em LINHA RETA por
        # cima das paredes da mansão -- medido em 08/09/2026. `comecar_em` em vez
        # de FATIAR: a rota inteira preserva o waypoint anterior, candidato do
        # destravamento. Ver `docs/decisoes/hh.md` §16.
        onde = mapa_hh.onde_retomar(ctx.memory.position(), caminho)
        if onde.indice > 0:
            ctx.log.info("HH: retomando o trecho do %s pelo waypoint %s/%s -- %s",
                         rotulo, onde.indice + 1, len(caminho), onde.motivo)

        if not self.nav.seguir_rota(caminho,
                                    max_seconds=MAX_SEGUNDOS_POR_TRECHO,
                                    comecar_em=onde.indice,
                                    ao_chegar=self._ao_chegar_no_waypoint):
            self._falhar(f"não cheguei no {rotulo}", State.RECUPERAR)
            return

        self._limpar_os_mobs_do_caminho(rotulo)

        # DESMONTA ANTES DE LUTAR: montado o jogo recusa as skills.
        #
        # `permitir_em_batalha=True` porque este É um ponto de luta -- e chegar
        # nele já em combate é o normal na HH. Sem a exceção, `ensure_dismounted`
        # recusa e só escreve "Em combate: ignorando o pedido para desmontar".
        self.nav.ensure_dismounted(permitir_em_batalha=True)
        ctx.log.info("HH: no ponto do %s (%s)", rotulo, ponto)
        self._ir_para(State.BOSS)

    def _ao_chegar_no_waypoint(self, waypoint: tuple[int, int]) -> None:
        """Nos pontos que costumam ter mob barrando, limpa ANTES de seguir.

        =================================================================
        O PONTO É UM SÓ, E ELE VEM DO BOT EM LUA
        =================================================================

        O (232,188) aparece em dois arquivos do bot original com a mesma
        instrução: matar os mobs que bloqueiam antes de continuar. É uma
        passagem estreita, e um mob parado nela faz a navegação bater na
        geometria e chamar o destravamento em círculo.

        SÓ SE O COMBATE JÁ COMEÇOU, e essa é a diferença contra o Lua. Ele mata
        ali sempre que está a pé, porque não lê a flag; nós lemos. Numa volta em
        que o ponto está limpo isto não custa uma leitura de tela nem um clique
        -- só a pergunta à memória, que é o que a regra "memória primeiro" torna
        barata.

        MONTADO NÃO PARA. Em batalha não se monta, então chegar aqui montado já
        significa que não há combate -- mas a conferência fica explícita porque
        montado o jogo IGNORA a tecla de skill sem devolver erro, e girar a
        rotação sem dano é a armadilha silenciosa de sempre.
        """
        ctx = self.ctx
        if not mapa_hh.bloqueia_a_passagem(waypoint):
            return
        if ctx.memory.is_mounted():
            return
        if ctx.memory.in_battle() is not True:
            return

        ctx.log.info(
            "HH: cheguei no %s em combate -- é o ponto onde os mobs bloqueiam a "
            "passagem. Limpando antes de seguir.", waypoint)
        try:
            self._matar_ate_sair_de_batalha(f"passagem em {waypoint}")
        except StopRequested:
            raise
        except Exception as exc:
            ctx.log.warning(
                "HH: limpeza da passagem falhou (segue a run): %s", exc)

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
            self._matar_ate_sair_de_batalha(f"caminho do {rotulo}")
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
        alvo = do_trecho(self.progresso.trecho, TOLERANCIA_DO_PONTO)
        rotulo, ponto = alvo.rotulo, alvo.ponto

        # NÃO SE ESPERA COMBATE DE LONGE. Absorvido do `BossRushRoutine._do_boss`:
        # se o personagem não está no ponto, ele volta a andar em vez de ficar
        # parado esperando uma flag que não vai ligar.
        #
        # Sem leitura de posição segue: recusar aqui travaria a run, e quem
        # decide então é a flag de combate ligar ou não.
        pos = ctx.memory.position()
        if pos is not None and mapa_hh.distancia(pos, ponto) > TOLERANCIA_DO_PONTO:
            # EM BATALHA NÃO SE ANDA -- MATA-SE. Este ramo era um beco sem
            # saída: `ATE_O_BOSS` começa exigindo montaria, e em batalha o jogo
            # RECUSA montar -- o bot apertava a tecla contra a recusa para
            # sempre (medido em 04/09/2026). Não muda de estado: a volta
            # seguinte relê a posição e decide de novo.
            #
            # A MONTARIA É ESCUDO AQUI TAMBÉM: montado, o caminho de volta é
            # ANDAR, e andar montado funciona com a flag alta.
            #
            # `is True` e não `not ...`: ilegível NÃO autoriza sair batendo.
            # Ver `docs/decisoes/hh.md` §13.
            if ctx.memory.in_battle() is True and not ctx.memory.is_mounted():
                ctx.log.info(
                    "HH: fora do ponto do %s (%s, o ponto é %s), EM BATALHA e "
                    "A PÉ. Não dá para andar nem montar assim -- matando até "
                    "sair de combate.", rotulo, pos, ponto)
                self._matar_ate_sair_de_batalha(
                    f"voltar ao ponto do {rotulo}")
                return

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

        # CINCO SEGUNDOS PARA A FLAG LIGAR, e é isto que torna barato refazer um
        # trecho já limpo depois de uma morte: ponto vazio não engaja.
        if not self.combat.esperar_entrar_em_combate(
                rotulo, limite=SEGUNDOS_PARA_ENGAJAR, pocao_na_espera=False):
            if ctx.snapshot().dead:
                self._falhar(f"morri esperando o {rotulo} engajar")
                return
            # SILÊNCIO SÓ VALE COMO "LIMPO" SE EU ESTIVER NO PONTO.
            #
            # Longe dele, não engajar não prova nada -- prova só que o
            # personagem está longe. Creditar ali foi o defeito #2 da auditoria.
            if not alvo.estou_nele(ctx.memory.position()):
                self._falhar(
                    f"o {rotulo} não engajou, mas eu estou a "
                    f"{alvo.distancia_de(ctx.memory.position()) or -1:.0f} "
                    f"unidades do ponto -- refazendo o trecho",
                    State.ATE_O_BOSS)
                return
            ctx.log.info(
                "HH: o %s não engajou em %.0fs, e eu ESTOU no ponto -- está "
                "limpo, sigo para o trecho seguinte. (Se ele estava VIVO e só "
                "demorou, esta run perde este boss; é a regra escolhida.)",
                rotulo, SEGUNDOS_PARA_ENGAJAR)
            self._avancar_o_trecho(rotulo)
            return

        if not self._lutar_no_ponto(rotulo):
            return

        # VI O BOSS CAIR? Prova mais forte que a posição: responde "o boss
        # morreu?" e não "estou no lugar certo?". SÓ AFIRMA -- não ter visto cai
        # no contrato de posição, logo abaixo. Ver `hh/bosses.py`.
        if self._vi_o_boss_cair(rotulo):
            self._catar_o_loot()
            self._avancar_o_trecho(rotulo)
            return

        # VOLTA PARA O PONTO, E A FALHA IMPORTA.
        #
        # Sair de batalha responde "a flag baixou", nunca "o ponto está limpo".
        # No log de 05/09 o personagem limpou um pacote 46 unidades fora do
        # ponto do Fa-Yuan, o retorno falhou, e a run creditou o boss assim
        # mesmo. Não voltou ⇒ o boss continua lá ⇒ refaz o trecho.
        if not alvo.voltar_para_ele(
                ctx.memory.position(), self.ui.encostar_no_ponto, ctx.log,
                SEGUNDOS_POR_TENTATIVA_DE_VOLTAR):
            self._falhar(
                f"saí de batalha no {rotulo} mas não consegui voltar ao ponto "
                f"-- não dá para creditar o boss daqui",
                State.ATE_O_BOSS)
            return

        self._catar_o_loot()
        self._avancar_o_trecho(rotulo)

    def _vi_o_boss_cair(self, rotulo: str) -> bool:
        """A memória confirmou a morte do boss DESTE ponto, pelo nome?

        Ponto de dois bosses exige os DOIS. Ver `hh/bosses.py`.
        """
        # `_morte` é `core/target_hybrid.MorteDoAlvo`, que já decide a morte e
        # agora lembra o NOME de quem caiu. Chega-se a ela pelo motor porque a
        # catraca não deixa `combate.py` crescer nem uma linha.
        nomes = bosses.nomes_do_boss(rotulo)
        morte = self.combat._morte
        if not nomes or not all(morte.caiu(n) for n in nomes):
            return False
        self.ctx.log.info("HH: a memória confirmou a morte de %s -- o %s está "
                          "feito.", ", ".join(nomes), rotulo)
        return True

    def _matar_ate_sair_de_batalha(self, motivo: str, *,
                                   usar_aoe: bool = False) -> bool:
        """O CORE LOOP de combate da HH: bate e troca de alvo até sair.

        =================================================================
        SEM PAUSA ENTRE UMA MORTE E O TAB SEGUINTE
        =================================================================

        Regra do usuário, 06/09/2026: *"o bot deve atacar e alternar alvos (TAB)
        ininterruptamente até que o estado global confirme a saída da batalha
        (`in_battle == False`)"*.

        O que isto SUBSTITUIU na HH foi `combate.limpar_o_combate`, cuja
        coreografia é: mata um, **PARA três segundos sem bater** olhando a flag,
        e só então TAB. Aqueles três segundos são `ESPERA_APOS_A_MORTE_ANTES_DO_TAB`
        e existem por medição -- **do BC**: lá o TAB imediato depois da morte
        mira o mob seguinte, o golpe o puxa, e o bot troca um travamento por
        outro. Na HH os mobs do ponto PRECISAM morrer, então puxar o seguinte é
        o objetivo, não o acidente.

        `limpar_o_combate` continua existindo e continua sendo do BC. Ela não
        foi tocada -- ver `docs/INVARIANTES.md`, "Decisão de cave NÃO mora em
        código compartilhado".

        =================================================================
        QUEM DÁ O TAB É O PRÓPRIO LAÇO DE ATAQUE
        =================================================================

        `atacar_ate_sair_de_combate` com `tabs_ao_morrer > 0` lê o HP do alvo a
        cada `CADENCIA_DA_LEITURA_DO_ALVO` e, na leitura em que o alvo cai,
        dispara `_trocar_de_alvo()` NA HORA -- dentro do mesmo laço que segue
        girando a rotação de skills. Não há espera; a única carência é
        `CARENCIA_APOS_O_TAB`, que existe para não ler a barra do alvo antigo.

        É a mesma mecânica da luta do segundo boss, que é o padrão que o usuário
        apontou como ideal.

        =================================================================
        ALVO SUMIDO COM A FLAG ALTA NÃO ENCERRA A LUTA
        =================================================================

        `TAB_ATE_SAIR_DE_COMBATE_NOS_GUARDAS` mantém a troca liberada enquanto a
        flag estiver alta, mesmo depois de o orçamento de TAB acabar. Apanhar de
        algo que o TAB não pegou continua sendo luta, e o laço continua tentando
        adquirir. Quem protege disso virar eternidade é o teto
        (`cave.max_fight_seconds`), não a contagem de alvos.
        """
        ctx = self.ctx
        self._mirar_o_primeiro_mob(motivo)
        # DESMONTAR AQUI EXIGE `permitir_em_batalha`: `ensure_dismounted()`
        # recusa descer com a flag de combate alta, e chegar no ponto já em
        # combate é o NORMAL na HH. Sem a exceção, os pontos de pacote lutavam
        # MONTADOS, com dano zero (medido em 07/09/2026).
        #
        # E O GESTO É `_descer_para_lutar`, não a chamada com a flag: ele também
        # força a barra de atalhos na página 1. Ver `docs/decisoes/hh.md` §15.
        self.combat._descer_para_lutar(motivo)
        fim = self.combat.atacar_ate_sair_de_combate(
            motivo,
            usar_aoe=usar_aoe,
            limite=float(ctx.cave.max_fight_seconds),
            tabs_ao_morrer=mapa_hh.TABS_NO_PACOTE,
            # O GOLPE NÃO PARA ENQUANTO A SAÍDA É CONFIRMADA: é o que a regra
            # pede -- ininterrupto até `in_battle == False`.
            atacar_na_confirmacao=True,
            # TAB QUE NAO SAI DO CADAVER: F1 + TAB. Medido em 4,4% das mortes.
            ao_falhar_o_tab=self.combat.reancorar_o_alvo,
        )
        ctx.log.info("HH: %s -- %s", motivo, fim.resumo())
        return fim.saiu_de_combate

    def _destravar_o_combate(self, motivo: str) -> bool:
        """O remédio do portão da montaria, com a mira da HH na frente.

        `limpar_o_combate` é do motor e serve as duas caves; o F1 é regra só
        desta. Ver `docs/decisoes/hh.md` §20.
        """
        self._mirar_o_primeiro_mob(f"destravar em {motivo}")
        return self.combat.limpar_o_combate(motivo)

    def _mirar_o_primeiro_mob(self, motivo: str) -> None:
        """AUTO-SELEÇÃO + TAB para abrir a luta. Sem condição nenhuma.

        TODA entrada de combate da HH passa por aqui -- pacote, boss e o
        destravamento do portão da montaria. Chegar num ponto de luta com a mira
        em qualquer coisa é o normal aqui, e conferir cada caso possível custa
        leitura e acerta menos que simplesmente reancorar.

        DENTRO da luta quem troca de alvo é a MORTE do alvo. A única exceção é o
        TAB que não sai do cadáver, e ela é reação a falha medida, não pergunta.

        Ver `docs/decisoes/hh.md` §14 e §20.
        """
        self.combat.reancorar_o_alvo(f"início de {motivo}")

    def _montar_ao_sair_do_combate(self, motivo: str) -> None:
        """Montaria no instante em que a luta acaba, e não no trecho seguinte.

        Regra do usuário, 06/09/2026: *"somente após sair oficialmente de
        batalha, o bot deve invocar a montaria e retomar a navegação"*.

        Antes disso a montaria só subia no começo de `ATE_O_BOSS` -- ou seja,
        depois do loot e da contabilidade do trecho, tudo a pé. O portão já sabe
        não fazer nada quando já está montado, então em batalha nenhuma isto
        custa uma tecla a mais.
        """
        self.nav.garantir_montaria_para_andar(motivo)

    def _lutar_no_ponto(self, rotulo: str) -> bool:
        """A luta deste ponto, com o ritual que a NATUREZA dele pede.

        =================================================================
        DOIS RITUAIS, E O MAPA É QUEM ESCOLHE
        =================================================================

        BOSS (um ou dois): `lutar_contra_um_boss` -- o ritual inteiro do BC,
        que já é o "matou, TAB, continua batendo" do segundo boss, mais o TAB de
        aquisição quando o boss não vem sozinho.

        PACOTE DE MOBS RANGED: `_matar_ate_sair_de_batalha` -- o MESMO laço de
        ataque, com orçamento de TAB e sem AoE. Até 06/09/2026 era
        `limpar_o_combate`, que para três segundos depois de cada morte antes de
        trocar; a parada é medição do BC e não vale aqui.

        E SEM AoE nos pontos ranged (`mapa_hh.PONTOS_SEM_AOE`): a skill de área
        é de curta distância, o mob ranged fica parado longe atirando, e a área
        passa embaixo dele. Girar AoE ali é gastar o tempo da rotação sem dano.

        OS DOIS CAMINHOS TERMINAM IGUAL: só saem quando a flag de combate cai.
        """
        ctx = self.ctx
        self.combat._morte.esquecer()   # por episódio; ver `hh/bosses.py`

        if mapa_hh.e_pacote_de_mobs(rotulo):
            if self._matar_ate_sair_de_batalha(
                    f"o pacote do {rotulo}", usar_aoe=mapa_hh.usa_aoe(rotulo)):
                self._montar_ao_sair_do_combate(f"sair do {rotulo}")
                return True
            self._falhar(f"não saí de batalha no pacote do {rotulo}")
            return False

        # A MIRA ABRE A LUTA DE BOSS TAMBÉM: a aquisição de
        # `lutar_contra_um_boss` parte de ONDE A MIRA ESTAVA. §20.
        self._mirar_o_primeiro_mob(rotulo)
        fim = self.combat.lutar_contra_um_boss(
            rotulo,
            usar_aoe=mapa_hh.usa_aoe(rotulo),
            tabs_ao_morrer=mapa_hh.tabs_ao_morrer(rotulo))
        ctx.log.info("HH: %s -- %s", rotulo, fim.resumo())

        # `saiu_de_combate` É A VITÓRIA, e é como a BC lê o mesmo objeto.
        # Morte, prazo estourado e flag ilegível devolvem False.
        if fim.saiu_de_combate:
            self._montar_ao_sair_do_combate(f"sair do {rotulo}")
            return True
        self._falhar(f"não venci o {rotulo}: {fim.motivo}")
        return False

    def _avancar_o_trecho(self, rotulo: str) -> None:
        """Fecha este trecho e vai para o próximo pendente -- ou para a saída.

        A CONTAGEM É DO `ProgressoDaCave`; aqui fica só o que a rotina faz com
        a resposta dele.
        """
        seguinte = self.progresso.marcar_feito_e_avancar()
        if seguinte is None:
            self._ir_para(State.SAIR,
                          f"{rotulo} foi o último; os quatro feitos, saindo")
            return
        self._ir_para(
            State.ATE_O_BOSS,
            f"indo para o {mapa_hh.TRECHOS_DOS_BOSSES[seguinte][0]}")

    # A CURA ENTRE OS BOSSES SAIU, e a ausência é a decisão.
    #
    # Ela sentava alguns segundos quando `precisa_curar` dizia que sim, no
    # intervalo entre um trecho e o seguinte. Dois motivos para tirar:
    #
    #   * ERA O TERCEIRO MOMENTO DE CURA NO MESMO PONTO. `curar_antes_do_boss`
    #     já faz o top-up no começo do trecho seguinte, e o intervalo entre os
    #     dois é o tempo de andar -- curar duas vezes ali é pagar duas.
    #   * SENTAR FOI MEDIDO E REPROVADO NA BC (ver `sentar_para_recuperar`):
    #     quatro segundos parado não recuperavam o suficiente para mudar a luta.
    #
    # E a regra do usuário (03/09/2026) é justamente essa: *"curas em outros
    # momentos só se for realmente necessário, pois a cave de HH é bem mais
    # fraca que a cave de BC"*. O que sobrou são dois momentos: a entrada, e o
    # top-up antes de encostar em cada boss.

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
        """Vai até o ponto de saída e SAI de verdade, pelo `Servant Child`.

        =================================================================
        ANTES ESTE ESTADO NÃO SAÍA DA CAVE
        =================================================================

        Ele andava até (529,119) e declarava a run concluída -- sem falar com
        NPC nenhum. O personagem ficava dentro, e a "run seguinte" começava a
        tentar entrar numa cave em que já estava.

        =================================================================
        O PADRÃO É O DA ENTRADA, E NÃO O DO LUA
        =================================================================

        Um clique direito no NPC (`coords.hh_exit_npc`), o diálogo conferido, e
        o link "Leave Happiness Hall" achado por TEMPLATE. O bot em Lua dá três
        cliques direitos às cegas em alturas diferentes porque não sabe ler a
        tela; um clique que erra o NPC cai no chão, e clique no chão faz o
        personagem ANDAR -- saindo do ponto de onde o NPC é alcançável.

        INSISTE ATÉ A POSIÇÃO CONFIRMAR, e é a mesma forma da entrada: quem diz
        que saiu é a coordenada, não o clique ter saído. O Lua também confere
        assim (`farmer.exitCave`), e refaz o diálogo quando a espera passa.

        A PÉ PARA FALAR: `falar_com_npc` já garante isso, e é o mesmo motivo de
        sempre -- montado o jogo ignora a interação sem devolver erro.
        """
        self.nav.garantir_montaria_para_andar("saída da cave")
        if not self.nav.seguir_rota(mapa_hh.CAMINHO_ATE_A_SAIDA,
                                    max_seconds=MAX_SEGUNDOS_POR_TRECHO):
            self._falhar("não cheguei no ponto de saída", State.RECUPERAR)
            return

        if not self._falar_com_o_npc_da_saida():
            return

        self._saiu()

    def _falar_com_o_npc_da_saida(self) -> bool:
        """Insiste no diálogo de saída até a POSIÇÃO dizer que saiu."""
        ctx = self.ctx
        limite = time.time() + MAX_SEGUNDOS_PARA_SAIR
        tentativa = 0

        while time.time() < limite:
            self._guard()
            tentativa += 1

            # JÁ SAÍ? Pode ter saído na tentativa anterior e a confirmação ter
            # fechado antes da resposta do servidor.
            if not mapa_hh.esta_dentro_da_hh(ctx.memory.position()):
                return True

            # CHEGA PRIMEIRO, DEPOIS CLICA. A navegação declara o trecho
            # concluído dentro da tolerância de rota (7), e sete unidades já
            # bastam para o clique pegar o NPC errado -- ver
            # `garantir_coordenada_da_saida`.
            self.ui.garantir_coordenada_da_saida()

            if self.ui.tentar_sair_da_hh() and self.ui.esperar_sair():
                ctx.log.info("HH: fora da cave na tentativa %s", tentativa)
                return True

            ctx.log.info(
                "HH: tentativa %s de sair não confirmou; refazendo o diálogo "
                "do %s", tentativa, mapa_hh.NPC_DA_SAIDA)
            ctx.tick(ENTRE_TENTATIVAS_DE_SAIR)

        self._falhar(
            f"não saí da cave em {MAX_SEGUNDOS_PARA_SAIR / 60:.0f} min "
            f"({tentativa} tentativas)", State.RECUPERAR)
        return False

    def _saiu(self) -> None:
        """Fora. A run fecha aqui, e o progresso da cave é esquecido.

        O PORQUÊ de esquecer está em `progresso.sai_da_cave`.
        """
        ctx = self.ctx
        ctx.stats.end_run(ok=True)
        self.progresso.sai_da_cave()
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

        # A ORDEM É DELETAR E DEPOIS VENDER, e ela importa.
        #
        # O lixo da HH não é comprado pelo NPC: levá-lo para a janela de venda
        # gasta cliques na grade em item que não sai, e ele volta ocupando o
        # mesmo slot. Apagar primeiro deixa a bolsa com só o que tem preço --
        # e a venda, que vende a partir de um slot configurado, passa a
        # encontrar mercadoria onde antes achava lixo.
        self.manutencao.descartar_o_lixo()

        if self.manutencao.precisa_vender():
            self.manutencao.vender()
            # SÓ CONTA COMO FEITA SE PÔDE ACONTECER. Ver `hh.md` §21.
            if self.manutencao.a_venda_esta_impedida:
                ctx.log.error(
                    "HH: a venda NÃO aconteceu; não conto como feita e tento "
                    "de novo na próxima run.")
            else:
                self.manutencao.anotar_a_venda()

        if ctx.settings.hh.modo_do_reset == MODO_FADA_DA_HH:
            self._reciclar_o_time()

        self._ir_para(State.PREPARAR, "manutenção feita; próxima run")



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
        if not ctx.settings.reset_nick.strip():
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

        # VIVO, MAS ALGO SAIU DO ROTEIRO. O caso mais comum aqui é o trajeto ter
        # sido abortado por HP crítico (`Navigator._manutencao_em_movimento`
        # devolve um motivo quando a vida cai abaixo de `emergency_pct`).
        self._curar_em_emergencia()

        # O TRECHO EM ANDAMENTO NÃO É JOGADO FORA: quem caísse no trecho 3
        # voltaria a fazer o 1 e encontraria a sala vazia -- os bosses só
        # renascem no reset, que acontece na SAÍDA. Quem decide por onde
        # continuar é `_retomar_dentro_da_cave`.
        self._ir_para(State.SITUAR, "recuperando: vou me situar de novo")

    def _curar_em_emergencia(self) -> None:
        """Cura fora da rotina, e só quando a vida realmente pede.

        =================================================================
        PARA CURAR TEM QUE ESTAR FORA DE BATALHA -- E A SAÍDA É MATANDO
        =================================================================

        Regra do usuário, 03/09/2026: *"para se curar tem que estar fora de
        batalha"*, e quando perguntado o que fazer estando em batalha com a vida
        baixa ele escolheu MATAR: *"você deve matar os mobs até sair de
        batalha"*.

        `limpar_o_combate` é exatamente isso, e já existia no motor: mata um,
        para e olha a flag, e só então TAB para o próximo. Se o teto dela
        estourar sem sair de batalha, **não trava**: a cura é pulada, o bot
        volta a se situar, e na volta seguinte tenta de novo.

        =================================================================
        E SÓ ABAIXO DA EMERGÊNCIA
        =================================================================

        `precisa_curar` (o limiar normal, `potions.hp_pct`) seria demais aqui:
        os mobs da HH são fracos e a run passaria o tempo bebendo. Quem manda é
        `potions.emergency_pct` -- o mesmo número que faz a navegação abortar o
        trajeto, e por isso o mesmo que trouxe o bot até este estado.

        DENTRO DA CAVE QUEM CURA É `curar_ao_entrar`: rajada curta, sem sentar.
        `heal_to_full` senta e é para fora da instância.
        """
        ctx = self.ctx
        pct = ctx.memory.vida_pct()
        if pct is None or pct > ctx.settings.potions.emergency_pct:
            return

        if ctx.memory.in_battle() is True:
            ctx.log.warning(
                "HH: vida em %.0f%% e ainda EM BATALHA. Não dá para curar assim "
                "-- matando até sair de combate.", pct)
            if not self._matar_ate_sair_de_batalha("curar em emergência"):
                ctx.log.warning(
                    "HH: não saí de batalha no teto; deixo a cura para a volta "
                    "seguinte em vez de travar aqui.")
                return

        ctx.log.info("HH: vida em %.0f%% (emergência é %s%%); curando",
                     pct, ctx.settings.potions.emergency_pct)
        self.combat.curar_ao_entrar()


__all__ = ["ESTADOS_DENTRO_DA_CAVE", "HHRoutine", "State"]
