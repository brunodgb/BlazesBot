"""O LAÇO DE UMA CAVE -- o esqueleto que o BC e a HH repetiam.

=========================================================================
DEPENDÊNCIA CRUZADA -- de onde veio, quem usa, o que NÃO veio
=========================================================================

Promovido em 26/09/2026 (auditoria de 25/09, decisão Q17 do grilling).
`BossRushRoutine.run` (`bot/bc`) e `HHRoutine.run` (`bot/hh`) eram o MESMO laço
em 164 e 111 linhas -- e já tinham divergido. Só o BC tinha o cronômetro e o
tempo por estado no log; a HH ganhou os dois aqui. E só o BC limpava o contexto
do log ao sair -- no `finally`, o que apagava a fase ANTES de o supervisor
gravá-la no Histórico de Quedas: toda queda do BC ia para lá sem dizer o que
ele estava fazendo. Aqui a limpeza é só na saída limpa.

QUEM USA: as duas rotinas de cave, por herança. MEXER AQUI MEXE NAS DUAS.

O QUE FICOU EM CADA CAVE, e por quê:

  * a mensagem de largada, e o que roda antes do laço e a cada volta (a venda da
    largada do BC; o `a_hh_comecou` e o contador de voltas da HH) -- são regra
    de cave, e entram pelos GANCHOS abaixo;
  * os PASSOS ENTRE ESTADOS -- números medidos e diferentes nas duas (0,06/0,15
    no BC, 0,05/0,4 na HH); cada cave diz os seus;
  * a transição de falha (`_falhar`): o BC conta falhas seguidas, a HH não.

O CONTRATO DE QUEM HERDA está declarado na classe, e o `tests/test_sem_chamada_
orfa.py` o confere. O despacho é pela convenção `_do_<estado em minúsculas>`,
que as duas caves já seguiam -- `tests/test_rotina_de_cave.py` confere que todo
estado tem o seu.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ..core import diario, logmodo
from ..core.cronometro import cronometro
from .context import Disconnected, FarmDesligado, StopRequested
from .navegacao import PersonagemMortoNoPortao

# Um estado que segue no mesmo lugar por mais que isto (segundos) também vai
# para o log -- é o sinal de um estado que está repetindo (luta que não fecha,
# porta cheia). É LIMIAR de log, não espera: por isso fica fora do `TEMPOS.md`.
LIMIAR_DO_ESTADO_LONGO = 5.0


class RotinaDeCave:
    """O laço de estados de uma cave. Quem herda diz QUAL cave e o que é dela."""

    # -- o que cada cave declara --------------------------------------------
    NOME: str = ""              # "BC" / "HH": prefixo do log e da telemetria
    CAVE: str = ""              # `ctx.cave_em_farm` -- o interruptor desta cave
    LARGADA: str = ""           # o motivo do F12 preso na largada
    PASSO_DENTRO: float = 0.0   # a pausa entre estados, dentro e fora da cave
    PASSO_FORA: float = 0.0
    ESTADO_INICIAL: Any = None
    ESTADO_DE_RECUPERAR: Any = None
    ESTADOS_DENTRO_DA_CAVE: frozenset = frozenset()

    # -- o contrato de quem herda (declarado para ser lido, não adivinhado) -
    ctx: Any
    state: Any
    esconder: Any
    combat: Any

    def _guard(self) -> None:
        """Parar, pausar e o watchdog ENTRE estados. Quem herda fornece."""
        raise NotImplementedError

    def _falhar(self, mensagem: str) -> None:
        """A transição de falha. Quem herda fornece (o BC conta as seguidas)."""
        raise NotImplementedError

    # -- os ganchos: o que é regra de cave, e não de laço -------------------
    def _anunciar_a_largada(self) -> None:
        """A linha de log da largada."""

    def _antes_do_laco(self) -> None:
        """Roda depois de escolher o estado inicial e antes do F12 preso."""

    def _ao_comecar(self) -> None:
        """Roda já com `farming` ligado, antes da primeira volta."""

    def _a_cada_volta(self) -> None:
        """Roda a cada volta, antes do estado."""

    # -- o laço -------------------------------------------------------------
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
        self._anunciar_a_largada()
        # Começa SITUANDO, nunca preparando: uma conta que já está no meio da
        # cave continua de onde estava, em vez de tentar entrar estando dentro --
        # o que faria o clique cair no chão e tirar o personagem da rota.
        self.state = self.ESTADO_INICIAL
        self._antes_do_laco()
        # O F12 PRESO JÁ NA LARGADA -- *"no momento que eu clicar em BC ou HH,
        # antes de começar a andar"* (usuário, 10/09/2026). REAFIRMAR É O
        # CORRETO, e não redundância: tecla fisicamente presa repete sozinha, e
        # reenviar recupera o estado quando o cliente o perde (relogin).
        self.esconder.prender(self.LARGADA)

        # Desligar a cave pela interface precisa cortar a fase atual NO MEIO.
        # `farming` é o sinal para `ctx.raise_if_stopped` detonar `FarmDesligado`.
        # O `finally` garante que a flag cai em QUALQUER saída -- senão o laço
        # "online" seguinte re-detonaria a parada e derrubaria a sessão, o
        # oposto do desejado.
        ctx.farming = True
        # QUEM está no ar: é o que faz a parada conferir o interruptor DESTA
        # cave, e não `account.farms`.
        ctx.cave_em_farm = self.CAVE
        try:
            self._ao_comecar()
            while True:
                if should_continue is not None and not should_continue():
                    ctx.log.info("%s: farm desligado; devolvendo o controle",
                                 self.NOME)
                    break
                if max_runs is not None and ctx.runs_completed >= max_runs:
                    ctx.log.info("Limite de %s runs atingido", max_runs)
                    break

                self._guard()
                # A COMIDA DO PET, CONFERIDA A CADA VOLTA (13/09/2026): só age
                # depois de a refeição passar do prazo, e aí fura o veto do
                # desmonte. (A chamada antiga, que não furava, era custo sem
                # efeito e ficou comentada até então.) O preparo de entrada
                # continua sendo o caminho normal; isto é a rede para quando ele
                # não chega -- venda longa, disputa de entrada, run retomada.
                self.combat.cuidar_da_comida_no_laco(
                    em_transito=self.state in self.ESTADOS_DENTRO_DA_CAVE)
                self._a_cada_volta()
                # A fase vai para o JSON de dev ANTES do estado rodar: o log do
                # estado sai com ela.
                logmodo.fase(self.state.name.lower())

                anterior = self.state
                handler = getattr(self, f"_do_{anterior.name.lower()}")
                # CRONÔMETRO POR ESTADO: é o número que diz ONDE o tempo da run
                # é gasto (foi assim que apareceu que o trajeto da cave custava
                # 8,6 s por waypoint). A passagem individual vai para o log; o
                # `cronometro` agrega a distribuição (n, mínimo, média, máximo),
                # que é o que mostra se um estado piorou. Custo: ~310 ns.
                comecou = time.time()
                try:
                    with cronometro(f"{self.NOME.lower()}.estado.{anterior.name}"):
                        handler()
                except (StopRequested, Disconnected):
                    # Parar a conta e cair são do supervisor, não daqui.
                    raise
                except PersonagemMortoNoPortao as exc:
                    # O portão da montaria avisando que não há o que insistir:
                    # cadáver não monta. Não é defeito -- sem este ramo sairia
                    # com traceback pelo `except Exception` --, e o desfecho é o
                    # mesmo do `_guard()` ao ver o personagem morto.
                    ctx.log.warning("%s. Indo para RECUPERAR.", exc)
                    self.state = self.ESTADO_DE_RECUPERAR
                except FarmDesligado:
                    # DESLIGAR A CAVE NÃO É DEFEITO. `ctx.tick` detona
                    # `FarmDesligado` de dentro da navegação, do combate e da
                    # venda; sem este ramo a exceção subia até o supervisor como
                    # "Erro inesperado na sessão", COM TRACEBACK, e derrubava a
                    # sessão -- medido na HH em 03/09/2026: 15 vezes em 33 min.
                    ctx.log.info(
                        "%s: farm desligado no meio de %s; devolvendo o "
                        "controle (a conta fica online, parada, com relogin)",
                        self.NOME, anterior.name)
                    break
                except Exception as exc:
                    ctx.log.exception("%s: erro no estado %s: %s",
                                      self.NOME, anterior.name, exc)
                    diario.registrar_evento(
                        ctx.account_login, "excecao",
                        f"{self.NOME} {anterior.name}: {type(exc).__name__}: {exc}",
                        ctx.memory.position(), ctx.memory.location(),
                    )
                    self._falhar(f"exceção em {anterior.name}")

                gasto = time.time() - comecou
                if self.state is not anterior:
                    ctx.log.info("%s levou %.1fs -> %s | posição %s",
                                 anterior.name, gasto, self.state.name,
                                 ctx.memory.position())
                elif gasto > LIMIAR_DO_ESTADO_LONGO:
                    ctx.log.info("%s levou %.1fs e continua no mesmo estado",
                                 anterior.name, gasto)

                # A pausa entre estados: dentro da cave cada décimo conta, porque
                # os mobs do caminho continuam vindo enquanto o bot pensa.
                ctx.tick(self.PASSO_DENTRO
                         if self.state in self.ESTADOS_DENTRO_DA_CAVE
                         else self.PASSO_FORA)
        except FarmDesligado:
            # REDE DE SEGURANÇA: o `ctx.tick` do fim do laço e o `_guard()` do
            # começo ficam FORA do `try` do estado. A cave pode apagar ali
            # também, e o desfecho tem de ser o mesmo -- controle devolvido
            # limpo, sem derrubar a sessão.
            ctx.log.info("%s: farm desligado; devolvendo o controle", self.NOME)
        finally:
            ctx.farming = False
            ctx.cave_em_farm = ""
        # SAÍDA LIMPA -- farm desligado ou limite de runs: a fase sai do contexto
        # do log, senão a conta parada seguiria carimbando a última. NUMA QUEDA,
        # NÃO: a exceção pula esta linha, e o supervisor ainda vai ler a fase
        # para o Histórico de Quedas (`_registrar_queda`), depois que ela sai.
        # Por isso as saídas do laço são `break`, e não `return`.
        logmodo.limpar()
