"""CURA DO ECOSSISTEMA APP: não morrer, e se curar em lugar seguro.

Combinado com o usuário em 25/08/2026. A ideia em uma frase: *"garantir que o
personagem não morra, e sim se cure em um lugar seguro, que é onde o usuário
decidiu que seria o ponto inicial"*.

=============================================================================
O FLUXO
=============================================================================

Ao terminar CADA rotação da macro (nunca no meio de uma):

    vida >= 30%          -> nada acontece
    vida <  30%          -> esperar SAIR DE BATALHA (até 2 s, perguntando)
                              ainda em batalha -> roda mais uma volta da macro
                              fora de batalha  -> volta ao ponto e cura

    voltar ao ponto      -> um clique no minimapa, perguntando a posição,
                            teto de 5 s. Chegou antes, cura antes.
    curar                -> com tecla de poção: bebe, espera até 15 s, repete
                            até 90% ou até 5 poções
                         -> sem tecla de poção: senta até 30 s, ou até os 90%
                         -> a poção NÃO saiu (não sentou): acabaram -> senta

    entrou em batalha    -> em QUALQUER ponto da cura, volta a rodar a macro

=============================================================================
SENTAR NÃO É UMA TRAVA -- E ESTE ARQUIVO JÁ ERRROU ISSO
=============================================================================

**O personagem sentado ataca, anda e faz qualquer coisa livremente.** Sentar não
prende nada: é um ESTADO que sai sozinho na primeira ação, e o que ele faz é
AUMENTAR a regeneração base de vida e de mana. Regra do jogo, dita pelo usuário
em 01/09/2026.

Disso decorre a regra deste arquivo:

    **O BOT SÓ SENTA. NUNCA APERTA A TECLA PARA LEVANTAR.**

E não é indiferença -- levantar é ATIVAMENTE PIOR, por dois motivos:

1. **Perde a regeneração** que é a única razão de sentar. Sair antes da hora
    joga fora exatamente o efeito que se foi buscar.
2. **A tecla é INTERRUPTOR e o estado é uma corrida.** Se o personagem já saiu
    do sentado sozinho -- levou dano, a macro mandou uma tecla, qualquer coisa
    --, apertá-la de novo o SENTA, e senta bem na hora em que ele precisa
    reagir. Foi por isso que existiu um `_levantar()` aqui, e é por isso que ele
    não existe mais.

A VERSÃO ANTIGA DESTE ARQUIVO AFIRMAVA O CONTRÁRIO ("sentado, a macro inteira
bate no chão; as teclas saem e o jogo ignora"). Isso NÃO acontece neste jogo. A
afirmação sobreviveu em docstrings por semanas e chegou a ser restaurada uma vez
depois de removida, porque parecia bem fundamentada. Não estava.

SÓ SE ANDA ANTES DE BEBER, nunca depois. Andar é uma AÇÃO, e ação tira o
personagem do sentado -- ou seja, um clique no minimapa depois da poção cancela
a regeneração extra. Por isso `_voltar_ao_ponto` roda uma vez, antes de
`_curar`, e nenhum caminho da cura volta a andar. Travado por
`tests/test_cura_do_app.py`.

=============================================================================
POR QUE FORA DE BATALHA
=============================================================================

Medição do usuário: a poção de fora de batalha **não funciona** em combate. Os
2 s de espera existem porque o jogo demora a baixar a flag depois que o mob
morre -- não é o mob que está vivo, é o jogo se atualizando.

E é aí que entra o alvo: desde 25/08/2026 o bot lê `hp/max_hp` do alvo pela
memória. Se o alvo ainda tem vida, esperar a flag baixar é esperar por nada --
tem mob vivo batendo, e o certo é rodar a macro para matá-lo. Palavras do
usuário: *"caso não saia de batalha meio logo, é pq pode ter outro mob
atacando"*.

=============================================================================
O RISCO QUE FICA DE PÉ, E É ESCOLHA DO USUÁRIO
=============================================================================

Com vida baixa e mob encadeando, o bot roda a macro volta após volta sem nunca
sair de batalha, e pode morrer com a proteção ligada. **É a decisão dele**, e é
a certa: *"não adianta continuar insistindo se não está curando, pois só vai
fazer o personagem morrer para o mob"*. Rodar a macro é o que mata o mob.

O que o código faz a respeito é AVISAR (`VOLTAS_PRESAS_PARA_AVISAR`): é
informação que só o usuário pode agir sobre -- ponto inicial ruim, mob demais,
ou macro fraca demais.

=============================================================================
ECOSSISTEMA APP -- NÃO IMPORTA DE `bc/`
=============================================================================

Este módulo é FOLHA do ecossistema APP. Tudo que ele precisa do jogo chega como
FUNÇÃO INJETADA, do mesmo jeito que o `ExecutorDeMacro` já recebe pet e posição
-- o executor tem `hwnd`, e o `Memory` precisa de `pid`, que quem tem é o
supervisor.
"""
from __future__ import annotations

import time
from collections.abc import Callable

from ...core import volta_ao_ponto

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
# só. Nenhum deles é lido pelo BC -- o BC tem os dele em `PotionConfig`.

# Abaixo de quanta vida a proteção dispara.
#
# 30, e não os 20 do desenho inicial: o próprio usuário subiu na revisão final
# -- *"assim tem uma margem de erro maior e a probabilidade de morrer é menor"*.
# A margem existe porque entre o gatilho e a primeira poção há uma volta de
# macro para terminar, até 2 s de espera de batalha e até 5 s de caminhada.
# AS DUAS BARRAS SÃO A RÉGUA ÚNICA, e valem seja qual for o método.
#
# Decisão do usuário em 01/09/2026: *"a barra é sempre do líder do time, que vai
# mandar; não vai ser mais usado a constante fixa. E caso não esteja em time
# aquele valor vai ser o usado para poção (...) essa ali vai ser a régua de
# quando saber que precisa de cura INDEPENDENTE DA FORMA, e o outro será o
# quanto ele precisa atingir para voltar a rodar as macros."*
#
# Estes dois números continuam aqui como PADRÃO de quem roda sem configuração
# injetada -- o supervisor sempre injeta, e em time injeta os do líder. Apagá-los
# só trocaria "padrão explícito" por "explode se ninguém injetar".
VIDA_PARA_CURAR = 30.0

# Até onde curar. Acima disso não se bebe mais nada.
VIDA_ALVO_DA_CURA = 90.0

# Quanto esperar entre uma poção e a próxima.
#
# É o tempo de efeito da poção no jogo, medido pelo usuário. A espera PERGUNTA a
# vida a cada `PASSO_DA_PERGUNTA` e sai no instante em que bate o alvo -- quem
# comprou poção forte não paga os 15 s.
SEGUNDOS_ENTRE_POCOES = 15.0

# Teto de poções por ciclo de cura.
#
# *"Normalmente em no máximo 2 deve curar, pois depende do nível da poção que o
# usuário comprou."* Chegar a 5 significa poção fraca demais para o dano que o
# personagem toma -- e aí insistir é gastar item sem sair do lugar.
#
# O contador ZERA toda vez que o ciclo é abandonado por batalha: cada volta ao
# ponto é um ciclo novo.
MAXIMO_DE_POCOES = 5

# Teto da caminhada de volta ao ponto inicial.
#
# *"Em no máximo 5 segundos é para chegar no ponto inicial, mas vai verificando,
# se chegar antes pode começar a se curar antes."* Estourado, cura onde estiver:
# melhor curar no lugar errado do que morrer esperando chegar no certo.
#
# O NÚMERO MORA NO `core/` desde 09/09/2026: o recolhimento do perímetro faz a
# MESMA pergunta física (quanto tempo leva para voltar andando), e número lido
# por dois lados mora num lugar só.
SEGUNDOS_PARA_VOLTAR_AO_PONTO = volta_ao_ponto.SEGUNDOS_PARA_CHEGAR

# Teto sentado, para quem não tem tecla de poção configurada.
#
# O "até" é do usuário e tem motivo: *"o mob pode acabar vindo atacar e, se for
# o caso, deve começar a rodar a macro para poder matar o mob"*.
#
# NÃO É POR VULNERABILIDADE. Sentado o personagem reage normalmente (ver o
# cabeçalho). A espera é cortada porque MATAR O MOB é melhor uso do tempo do que
# regenerar com ele batendo -- e a macro tira o personagem do sentado sozinha,
# sem tecla nenhuma.
SEGUNDOS_SENTADO = 30.0

# Quanto esperar a flag de batalha baixar depois que a macro termina.
#
# Não é o mob estar vivo -- é o jogo demorar a considerar "fora de batalha". Por
# isso é curto: se em 2 s não baixou, ou tem outro mob batendo (e aí o certo é
# rodar a macro) ou o jogo está muito atrasado.
SEGUNDOS_ESPERANDO_SAIR_DE_BATALHA = 2.0

# Quanto esperar o personagem SENTAR depois de apertar a tecla de poção.
#
# BEBER PÕE O PERSONAGEM SENTADO -- medição do usuário, e é o observável que
# faltava para saber se a poção saiu de verdade. Ver `_a_pocao_saiu`.
#
# Curto de propósito: é animação local do cliente, não ida ao servidor. E a
# espera PERGUNTA `is_sitting` a cada `PASSO_DA_PERGUNTA`, saindo no instante em
# que o estado aparece -- o teto só é pago quando a poção NÃO saiu, que é
# exatamente o caso em que se quer descobrir rápido.
SEGUNDOS_PARA_SENTAR_COM_A_POCAO = 1.0

# Cadência de toda pergunta deste módulo. Leitura de memória é ~1 µs; o custo é
# o `sleep`, e 0,1 s é fino o bastante para nenhum teto ser ultrapassado por
# mais que isso.
PASSO_DA_PERGUNTA = 0.1

# ===========================================================================
# O SOCORRO EM BATALHA -- 07/09/2026
# ===========================================================================
#
# TRÊS MORTES EM 13 h DE LOG, e as três com a mesma assinatura:
#
#     01:07:49  vida em 35% mas ainda em batalha. Rodando mais uma volta.
#     01:07:52  vida em 29% mas ainda em batalha. Rodando mais uma volta.
#     01:08:06  MORRI
#
# O personagem viu a própria vida cair de 35% a zero e NÃO BEBEU UMA POÇÃO. Não
# foi falha de leitura nem de tecla: `cuidar()` lia a vida, via que estava
# abaixo do limiar, chamava `_esperar_sair_de_batalha`, recebia `False` -- e
# voltava SEM CURAR, porque toda a cura estava atrás dessa porta. Com quatro a
# oito mobs batendo, a flag de batalha nunca baixa, e a porta nunca abre.
#
# O JOGO PERMITE BEBER EM BATALHA -- o BC já faz isso (`PotionConfig.
# battle_hp_pct`). Era só o APP que não fazia.
#
# O LIMIAR É O MESMO `pedir_pct` DO USUÁRIO, e isso é deliberado: não se
# inventa um número novo quando já existe um medido para a mesma pergunta
# ("preciso de cura?"). O que muda não é QUANDO curar -- é não deixar de curar
# por causa de uma flag.
#
# UMA POÇÃO POR VEZ, e volta a rodar a macro na hora. Beber em série parado é o
# oposto do que salva: quem mata quem está batendo é a macro. O laço longo de
# `_curar_com_pocao` (até 5 poções, esperando o efeito) continua sendo o da cura
# fora de batalha.
SEGUNDOS_ENTRE_SOCORROS = SEGUNDOS_ENTRE_POCOES

# Quantas voltas presas em batalha com vida baixa antes de gritar.
#
# NÃO É UM TETO -- o bot continua rodando a macro para sempre, que é a decisão
# do usuário. É só o aviso de que a situação não está se resolvendo sozinha.
VOLTAS_PRESAS_PARA_AVISAR = 5


class CuraDoApp:
    """Cuida da vida do personagem entre uma rotação da macro e a seguinte.

    NÃO decide nada sobre a macro em si e não manda tecla da sequência. Devolve
    para o executor se houve cura, e o executor só precisa saber disso para o
    log -- a volta seguinte roda igual de qualquer jeito.
    """

    def __init__(
        self,
        *,
        log,
        vida_pct: Callable[[], float | None],
        em_batalha: Callable[[], bool | None],
        alvo_atual: Callable[[], dict | None] | None = None,
        distancia_da_base: Callable[[], float | None] | None = None,
        voltar_para_base: Callable[[], bool] | None = None,
        apertar: Callable[[str], None],
        esta_sentado: Callable[[], bool | None] | None = None,
        tecla_de_pocao: Callable[[], str] | None = None,
        tecla_de_sentar: Callable[[], str] | None = None,
        fada: Callable[[float], bool] | None = None,
        pedir_pct: Callable[[], float] | None = None,
        parar_pct: Callable[[], float] | None = None,
        continuar: Callable[[], bool] | None = None,
    ) -> None:
        self.log = log
        self._vida_pct = vida_pct
        self._em_batalha = em_batalha
        self._alvo_atual = alvo_atual or (lambda: None)
        self._distancia_da_base = distancia_da_base or (lambda: None)
        self._voltar_para_base = voltar_para_base or (lambda: False)
        self._apertar = apertar
        self._esta_sentado = esta_sentado or (lambda: None)
        self._tecla_de_pocao = tecla_de_pocao or (lambda: "")
        self._tecla_de_sentar = tecla_de_sentar or (lambda: "")
        # QUEM CHAMA A FADA. `None` = esta conta não está num time com Fada, e
        # a cura se resolve com poção como sempre. Injetado pelo supervisor,
        # que é quem conhece o time e o mural.
        self._fada = fada
        # O LIMIAR VEM DA TELA. Era a constante `VIDA_PARA_CURAR` fixa em 30, e
        # a barra "pedir cura abaixo de" não mandava em nada -- ela só era usada
        # pela Fada. Em time quem manda é o líder (`_dono_da_macro`), que é o
        # que faz o time inteiro se comportar igual.
        #
        # `None` mantém o valor de sempre: quem não injeta nada não muda de
        # comportamento.
        self._pedir_pct = pedir_pct or (lambda: VIDA_PARA_CURAR)
        self._parar_pct = parar_pct or (lambda: VIDA_ALVO_DA_CURA)
        self._continuar = continuar or (lambda: True)

        self.curas = 0
        self.pocoes_gastas = 0
        self._voltas_presas = 0
        # Último socorro em batalha. Ver `SEGUNDOS_ENTRE_SOCORROS`.
        self._ultimo_socorro_em = 0.0
        self._avisou_sem_pocao_no_socorro = False
        self.socorros = 0
        self._avisou_sem_leitura = False
        self._avisou_sem_ponto = False

    # -- o portão --------------------------------------------------------

    def _zero_confirmado(self) -> bool:
        """Uma SEGUNDA leitura diz que a vida é zero mesmo? -- 07/09/2026.

        A regra "cadáver não se cura" tem um risco embutido, apontado pelo
        council: `hp == 0` aparece transitoriamente em troca de mapa, tela de
        carregamento, respawn e leitura de ponteiro inconsistente. Pular a cura
        por causa de UMA amostra ruim é deixar de curar um personagem VIVO --
        que é justamente a morte que esta classe existe para evitar.

        Mesma régua do `CicloDaMorte.estou_morto`, e pelo mesmo motivo: a
        segunda leitura custa microssegundos, e duas amostras de zero no mesmo
        instante num personagem vivo já seriam um problema de outra natureza.

        `None` na segunda leitura vale NÃO: sem prova, a cura acontece. Errar
        curando um morto custa uma tecla; errar não curando um vivo custa a
        conta.
        """
        try:
            segunda = self._vida_pct()
        except Exception:
            return False
        return segunda is not None and segunda <= 0.0

    def cuidar(self) -> bool:
        """Confere a vida e, se preciso, cura. `True` = mexeu em alguma coisa.

        Chamada UMA VEZ por rotação da macro, nunca no meio dela -- decisão do
        usuário: *"a ideia é ao terminar a macro você vai verificar a vida"*.
        """
        vida = self._vida_pct()
        if vida is None:
            # SEM LEITURA DE VIDA A PROTEÇÃO É INERTE, e é honesto dizer uma vez
            # em vez de fingir que está protegendo. Não dá para proteger o que
            # não se enxerga.
            if not self._avisou_sem_leitura:
                self._avisou_sem_leitura = True
                self.log.warning(
                    "APP: não consigo ler a vida do personagem; a proteção de "
                    "vida baixa fica inerte nesta sessão.")
            return False
        self._avisou_sem_leitura = False

        if vida <= 0.0 and self._zero_confirmado():
            # CADÁVER NÃO SE CURA -- 06/09/2026.
            #
            # Medido em campo: *"APP: terminei de regenerar sentado com a vida
            # em 0%"*, 60 s depois de o personagem já estar morto e um segundo
            # ANTES de a macro perceber. Sentar, beber poção e pedir cura à Fada
            # são todos inúteis num morto, e o ciclo da morte (`bot/morte.py`) é
            # quem sabe o que fazer -- ele é conferido na linha seguinte da
            # macro.
            self.log.debug("APP: vida em 0% -- não há o que curar. Quem cuida "
                           "disso é o ciclo da morte.")
            return False

        if vida >= self._pedir_pct():
            self._voltas_presas = 0
            return False

        if not self._esperar_sair_de_batalha(vida):
            # PRESO EM BATALHA COM VIDA BAIXA: era aqui que o personagem
            # morria, voltando sem curar. Ver `SEGUNDOS_ENTRE_SOCORROS`.
            return self.socorro(vida)

        self._voltas_presas = 0
        self._voltar_ao_ponto()

        # A FADA TEM PREFERÊNCIA SOBRE A POÇÃO. Tendo uma Fada de pé no time,
        # quem cura é ela -- e a poção fica para quando ela não estiver lá.
        #
        # `False` aqui não é falha: é "não há Fada", e o caminho segue para a
        # poção exatamente como sempre seguiu. Fora de um time, `_fada` é `None`
        # e nada disto existe.
        if self._fada is not None and self._esperar_a_fada(vida):
            return True
        return self._curar(vida)

    def socorro(self, vida: float | None = None) -> bool:
        """Vida baixa EM BATALHA: bebe UMA poção onde estiver. Não espera nada.

        `True` = apertei a tecla. Chamada de dois lugares, e de propósito:

          * `cuidar()`, quando a espera pela saída de batalha falha -- o caminho
            que matou três personagens em 07/09/2026;
          * o laço das LINHAS da macro (`executor._uma_volta_simples`), porque
            `cuidar()` roda uma vez por rotação e uma rotação chega a 23 s. Na
            terceira morte daquele dia o personagem foi de 100% a zero em 21 s
            sem UMA leitura de vida no meio.

        NÃO ANDA, NÃO SENTA, NÃO ESPERA O EFEITO. Andar em batalha arrasta mob,
        sentar é para regenerar (e a poção já sentou o personagem sozinha), e
        esperar é tempo que a macro deveria estar usando para matar quem bate.
        Quem confere se a poção fez efeito é a próxima chamada -- pela vida.

        SEM TECLA DE POÇÃO NÃO HÁ SOCORRO. A alternativa (sentar) é a cura de
        fora de batalha, e ali ela já existe; aqui ela não serve.
        """
        if vida is None:
            vida = self._vida_pct()
        if vida is None or vida <= 0.0 or vida >= self._pedir_pct():
            return False

        agora = time.time()
        if agora - self._ultimo_socorro_em < SEGUNDOS_ENTRE_SOCORROS:
            return False

        tecla = (self._tecla_de_pocao() or "").strip()
        if not tecla:
            if not self._avisou_sem_pocao_no_socorro:
                self._avisou_sem_pocao_no_socorro = True
                self.log.warning(
                    "APP: vida em %.0f%% em batalha e SEM tecla de poção "
                    "configurada. Não há socorro possível aqui -- configure-a "
                    "em Editar conta > Teclas.", vida)
            return False

        self._ultimo_socorro_em = agora
        self.socorros += 1
        self.pocoes_gastas += 1
        self._apertar(tecla)
        self.log.warning(
            "APP: SOCORRO -- vida em %.0f%% EM BATALHA; bebi poção (tecla %s) "
            "sem sair do lugar. Volto a rodar a macro: quem mata quem está "
            "batendo é ela.", vida, tecla)
        return True

    def _esperar_a_fada(self, vida: float) -> bool:
        """SENTA no ponto inicial e espera a Fada. `False` = não há Fada.

        Sentar não é enfeite: parado e sentado o personagem não puxa mob, não
        gasta a macro contra nada e REGENERA MAIS DEPRESSA enquanto espera --
        sentar aumenta a regeneração base de vida e de mana. É o que o usuário
        descreveu -- *"vai até o ponto inicial e senta, se mantendo sem fazer
        nada, apenas esperando a cura"* -- e o que faltava: antes ele ficava DE
        PÉ esperando.

        NÃO SE LEVANTA NA SAÍDA, e isso é regra do arquivo inteiro (ver o
        cabeçalho): sentado o personagem age normalmente, e a primeira tecla da
        macro já o tira do estado. Havia aqui um `finally` que apertava a tecla
        de volta; ele custava a regeneração e, pior, podia SENTAR o personagem
        bem na hora de reagir, porque a tecla é interruptor e o estado muda
        sozinho entre a leitura e o toque.
        """
        tecla = (self._tecla_de_sentar() or "").strip()
        if tecla and self._esta_sentado() is not True:
            self.log.info("APP: sentando no ponto inicial para esperar a Fada.")
            self._apertar(tecla)
        return self._fada(vida)

    # -- sair de batalha --------------------------------------------------

    def _esperar_sair_de_batalha(self, vida: float) -> bool:
        """`True` = está fora de batalha e pode curar.

        DUAS SAÍDAS ANTECIPADAS, e nenhuma delas é o relógio:

          * a flag baixou -> pode curar, sai na hora;
          * o alvo ainda TEM VIDA -> tem mob vivo batendo, e esperar a flag é
            esperar por nada. Sai na hora para rodar mais uma volta da macro.

        O teto é aviso, não gasto.
        """
        fim = time.time() + SEGUNDOS_ESPERANDO_SAIR_DE_BATALHA
        while time.time() < fim and self._continuar():
            if self._em_batalha() is False:
                return True

            alvo = self._alvo_atual()
            if alvo is not None and (alvo.get("hp") or 0) > 0:
                self._preso_em_batalha(vida, alvo)
                return False

            time.sleep(PASSO_DA_PERGUNTA)

        if self._em_batalha() is False:
            return True
        self._preso_em_batalha(vida, self._alvo_atual())
        return False

    def _preso_em_batalha(self, vida: float, alvo: dict | None) -> None:
        """Conta e, passado o limite, GRITA. Não impede nada."""
        self._voltas_presas += 1
        if self._voltas_presas < VOLTAS_PRESAS_PARA_AVISAR:
            self.log.info(
                "APP: vida em %.0f%% mas ainda em batalha (%s). Rodando mais "
                "uma volta da macro.", vida, self._quem(alvo))
            return
        if self._voltas_presas % VOLTAS_PRESAS_PARA_AVISAR == 0:
            self.log.warning(
                "APP: %s voltas com vida em %.0f%% SEM conseguir sair de "
                "batalha (%s). O personagem não está conseguindo se curar — o "
                "ponto inicial pode não ser seguro, ou a macro pode não estar "
                "dando conta dos mobs.",
                self._voltas_presas, vida, self._quem(alvo))

    @staticmethod
    def _quem(alvo: dict | None) -> str:
        """O alvo em uma frase, para o log. É a informação que faltava."""
        if not alvo:
            return "sem alvo"
        nome = alvo.get("nome") or "?"
        hp, maximo = alvo.get("hp"), alvo.get("max_hp")
        if hp is None or not maximo:
            return f"alvo {nome}"
        return f"alvo {nome} {hp}/{maximo} ({100.0 * hp / maximo:.0f}%)"

    # -- voltar ao ponto --------------------------------------------------

    def _voltar_ao_ponto(self) -> None:
        """Manda voltar e PERGUNTA se chegou, até o teto.

        Sem ponto salvo (trava de posição desligada) ou sem leitura de posição,
        cura onde estiver -- decisão do usuário: nunca deixar de curar por falta
        de ponto.
        """
        if not self._voltar_para_base():
            if not self._avisou_sem_ponto:
                self._avisou_sem_ponto = True
                self.log.info(
                    "APP: sem ponto inicial para voltar; vou curar onde estou.")
            return

        fim = time.time() + SEGUNDOS_PARA_VOLTAR_AO_PONTO
        while time.time() < fim and self._continuar():
            distancia = self._distancia_da_base()
            if distancia is not None and distancia <= 1.0:
                self.log.info("APP: cheguei no ponto inicial; vou me curar.")
                return
            time.sleep(PASSO_DA_PERGUNTA)

        distancia = self._distancia_da_base()
        self.log.info(
            "APP: não confirmei a chegada ao ponto inicial em %.0fs "
            "(distância %s). Curo onde estou — melhor no lugar errado do que "
            "morrer esperando chegar no certo.",
            SEGUNDOS_PARA_VOLTAR_AO_PONTO,
            "?" if distancia is None else f"{distancia:.0f}")

    # -- curar ------------------------------------------------------------

    def _curar(self, vida_inicial: float) -> bool:
        """A tecla vem de `KeyBinds.hp_potion` -- a de FORA de batalha.

        `KeyBinds`, e não `PotionConfig`: tecla descreve o JOGO e é
        compartilhada entre ecossistemas; `PotionConfig` guarda os LIMIARES do
        BC (`hp_pct`, `battle_hp_pct`), que são de quem decide. Trocar os dois
        estourou em produção em 25/08/2026 -- e só na primeira cura de verdade,
        porque a leitura vive num `lambda`.
        """
        tecla = (self._tecla_de_pocao() or "").strip()
        if tecla:
            return self._curar_com_pocao(tecla, vida_inicial)
        return self._curar_sentado(vida_inicial)

    def _curar_com_pocao(self, tecla: str, vida_inicial: float) -> bool:
        """Bebe até 90%, no máximo `MAXIMO_DE_POCOES`."""
        self.log.info("APP: vida em %.0f%%; curando com poção (tecla %s).",
                      vida_inicial, tecla)
        gastas = 0
        vida = vida_inicial

        while gastas < MAXIMO_DE_POCOES and self._continuar():
            # O ESTADO É LIDO ANTES DE APERTAR, e isso decide se a prova vale.
            #
            # A prova de que a poção saiu é o personagem SENTAR. Da segunda
            # poção em diante ele JÁ ESTÁ sentado pela primeira, e aí "está
            # sentado" não prova nada -- seria dar por boa uma tecla apertada
            # contra a bolsa vazia. Nesse caso a pergunta não tem observável e
            # a resposta certa é "não sei", que segue bebendo.
            sentado_antes = self._esta_sentado() is True
            self._apertar(tecla)
            gastas += 1
            self.pocoes_gastas += 1

            # A POÇÃO SAIU MESMO? Ver `_a_pocao_saiu`.
            saiu = None if sentado_antes else self._a_pocao_saiu()
            if saiu is False:
                self.log.warning(
                    "APP: apertei a tecla de poção e o personagem NÃO sentou — "
                    "provavelmente acabaram as poções. Vou me curar sentado, "
                    "que é o que sobra para não morrer.")
                return self._curar_sentado(
                    self._vida_pct() or vida_inicial, ja_avisou=True)

            vida, saiu = self._esperar_o_efeito(SEGUNDOS_ENTRE_POCOES)
            if saiu == "batalha":
                self.log.info(
                    "APP: entrei em batalha durante a cura (vida %.0f%%, %s "
                    "poção(ões)). Volto a rodar a macro — parado o mob mata.",
                    vida if vida is not None else -1, gastas)
                return True
            if vida is not None and vida >= self._parar_pct():
                self.curas += 1
                self.log.info("APP: curado em %.0f%% com %s poção(ões).",
                              vida, gastas)
                return True

        self.log.warning(
            "APP: gastei %s poção(ões) e a vida parou em %s%%, abaixo dos "
            "%.0f%%. Poção provavelmente fraca demais para o dano que o "
            "personagem toma. Volto a rodar a macro.",
            gastas, "?" if vida is None else f"{vida:.0f}", self._parar_pct())
        return True

    def _a_pocao_saiu(self) -> bool | None:
        """O personagem sentou depois da tecla? `None` = não consegui ler.

        =================================================================
        BEBER PÕE O PERSONAGEM SENTADO -- e isso é a prova que faltava
        =================================================================

        Medição do usuário em 25/08/2026. Antes desta leitura, "a poção saiu?"
        era pergunta sem observável: o bot apertava a tecla e só descobria pela
        vida, quinze segundos depois -- e com a bolsa vazia ele repetia isso
        cinco vezes, apertando uma tecla que não fazia nada, enquanto o
        personagem apanhava.

        Agora a bolsa vazia se anuncia em um segundo: apertou e **não sentou**,
        a poção não existe mais.

        `None` NÃO É "não saiu". Sem leitura de estado, concluir "acabaram as
        poções" trocaria a cura boa por sentar no chão -- e "não sei" nunca pode
        virar veredito. Nesse caso segue-se bebendo, como antes.

        =================================================================
        ESTE CONTRATO ERA LETRA MORTA ATÉ 26/08/2026
        =================================================================

        `Memory.is_sitting()` devolvia `bool` puro: falha de leitura virava
        `False`, e o ramo `ilegivel` desta função era inalcançável. Toda leitura
        falha produzia o veredito "acabaram as poções".

        MEDIDO no log de 25/08/2026: 4 avisos de bolsa vazia na MESMA sessão em
        que houve 3 curas bem-sucedidas com 2 poções cada. As poções existiam.

        O conserto foi na FONTE (`is_sitting` passou a `bool | None`), não aqui
        -- o consumidor sempre esteve certo. É a lição que ficou: contrato de
        tri-estado documentado no consumidor é expectativa; a prova mora na
        fonte.
        """
        fim = time.time() + SEGUNDOS_PARA_SENTAR_COM_A_POCAO
        ilegivel = False
        while time.time() < fim and self._continuar():
            sentado = self._esta_sentado()
            if sentado is True:
                return True
            if sentado is None:
                ilegivel = True
            time.sleep(PASSO_DA_PERGUNTA)
        if self._esta_sentado() is True:
            return True
        return None if ilegivel else False

    def _curar_sentado(self, vida_inicial: float,
                       ja_avisou: bool = False) -> bool:
        """Senta e espera a regeneração. DOIS caminhos chegam aqui:

        1. **Sem tecla de poção configurada** -- decisão do usuário: *"caso não
           tenha a tecla de poção fora de batalha configurado, não tenta se
           curar; o que pode fazer é voltar para o ponto inicial e sentar"*.
        2. **A poção não saiu** (o personagem não sentou ao beber), o que quer
           dizer que ela acabou. `ja_avisou=True` porque quem chamou já explicou
           o motivo no log, e repetir só afogaria a linha que importa.

        Nos dois casos é a mesma coisa: **é o que sobra para não morrer**.

        A TECLA DE SENTAR É INTERRUPTOR, então o estado é LIDO ANTES: apertá-la
        de pé senta, apertá-la sentado levanta. É a mesma regra da tecla do
        inventário no deletador.
        """
        tecla = (self._tecla_de_sentar() or "").strip()
        if not tecla:
            self.log.warning(
                "APP: vida em %.0f%% e nenhuma tecla de SENTAR configurada. "
                "Não tenho como curar.", vida_inicial)
            return False

        if not ja_avisou:
            self.log.info(
                "APP: vida em %.0f%% e sem tecla de poção; sentando para "
                "recuperar (até %.0fs).", vida_inicial, SEGUNDOS_SENTADO)

        # SÓ SENTA SE AINDA NÃO ESTIVER SENTADO. A tecla é INTERRUPTOR: apertá-la
        # com o personagem já sentado o LEVANTARIA, que é o oposto do que se
        # quer aqui. Nunca há um segundo `_apertar` -- ver o cabeçalho: o bot só
        # senta, e quem tira o personagem do sentado é a primeira ação da macro.
        if self._esta_sentado() is not True:
            self._apertar(tecla)

        vida, saiu = self._esperar_o_efeito(SEGUNDOS_SENTADO)

        if saiu == "batalha":
            self.log.info(
                "APP: mob veio enquanto eu regenerava sentado (vida %s%%). "
                "Volto a rodar a macro para matá-lo -- a primeira tecla já tira "
                "o personagem do sentado.",
                "?" if vida is None else f"{vida:.0f}")
        else:
            self.curas += 1
            self.log.info("APP: terminei de regenerar sentado com a vida em "
                          "%s%%.", "?" if vida is None else f"{vida:.0f}")
        return True

    def _esperar_o_efeito(self, teto: float) -> tuple[float | None, str]:
        """Espera perguntando. Devolve `(vida, motivo_da_saida)`.

        Motivos: `"alvo"` (chegou aos 90%), `"batalha"` (entrou em combate),
        `"teto"` (o tempo acabou), `"parada"`.

        A VIDA ATUAL É O MAIOR LIMITANTE -- decisão do usuário: chegando aos 90%
        não precisa mais curar, e não se espera o resto do intervalo por nada.
        """
        fim = time.time() + teto
        vida = self._vida_pct()
        while time.time() < fim:
            if not self._continuar():
                return vida, "parada"
            if self._em_batalha() is True:
                return self._vida_pct(), "batalha"
            vida = self._vida_pct()
            if vida is not None and vida >= self._parar_pct():
                return vida, "alvo"
            time.sleep(PASSO_DA_PERGUNTA)
        return self._vida_pct(), "teto"
