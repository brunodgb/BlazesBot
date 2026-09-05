"""Em que trecho a run da HH está, e o que já foi feito nesta ida à cave.

=========================================================================
POR QUE ISTO É UM MÓDULO, E NÃO TRÊS CAMPOS NA ROTINA
=========================================================================

Eram três atributos soltos em `HHRoutine` -- `_trecho`, `_trechos_feitos` e
`_run_em_andamento` --, lidos e escritos em seis lugares diferentes, sem nenhum
ponto que declarasse "a run começou" ou "a run acabou". A auditoria de
05/09/2026 achou dois defeitos que nascem exatamente dessa dispersão:

  * `_trecho == len(TRECHOS)` é o valor que "acabaram os trechos" deixa, e um
    dos leitores não sabia disso: indexava a tupla fora do fim e estourava
    `IndexError` em SITUAR, onze vezes em dez segundos;
  * o progresso atravessa o desliga/liga do farm (a rotina é guardada no
    supervisor de propósito), e nenhum dos três campos tinha dono para dizer
    quando invalidar.

Aqui eles têm UM dono e UMA pergunta cada. Quem quer saber se acabou pergunta
`acabou()`; ninguém mais faz essa conta.

=========================================================================
O QUE ESTE MÓDULO NÃO É
=========================================================================

NÃO É PERSISTÊNCIA. Regra do usuário, 03/09/2026: *"não precisa ser
persistente, só verificar enquanto está com o bot aberto"*. O que ele guarda
morre com o processo -- e é assim que tem de ser, porque o desfaz-refaz do time
ressuscita os quatro bosses a cada saída da cave.

NÃO SABE NAVEGAR NEM LUTAR. Ele conta trechos. Quem decide o que fazer com a
contagem é a rotina.
"""
from __future__ import annotations


class ProgressoDaCave:
    """A contagem dos trechos de uma ida à cave.

    `total` é quantos trechos a cave tem -- vem de `mapa_hh`, e não é lido aqui
    de propósito: assim o progresso é testável sem carregar o mapa, e um mapa
    com cinco bosses não pede mudança nenhuma neste arquivo.
    """

    def __init__(self, total: int) -> None:
        self._total = total
        self._trecho = 0
        self._feitos: set[int] = set()
        self._em_andamento = False

    # ==================================================================
    # Leitura
    # ==================================================================

    @property
    def trecho(self) -> int:
        """O índice do trecho atual. Pode valer `total` -- ver `acabou`."""
        return self._trecho

    @property
    def em_andamento(self) -> bool:
        """Há uma run acontecendo DENTRO da cave?

        É o que faz a retomada respeitar o trecho em que a run parou, em vez de
        escolher pelo waypoint mais próximo: os quatro trechos se cruzam no
        mapa, e quem morre no trecho 3 revive perto do trecho 1.
        """
        return self._em_andamento

    @property
    def feitos(self) -> int:
        return len(self._feitos)

    @property
    def total(self) -> int:
        return self._total

    def acabou(self) -> bool:
        """Não há mais trecho para fazer nesta ida à cave?

        UM LUGAR SÓ RESPONDE ISSO, e é o ponto do módulo. Duas contas dessas em
        lugares diferentes divergiriam, e o sintoma seria um `IndexError` num
        ramo e um trecho refeito no outro.

        Devolve True também para índice negativo ou disparatado: se o valor não
        aponta para um trecho de verdade, não há trecho a retomar, e o desfecho
        seguro é a saída -- o único estado que funciona de qualquer ponto de
        dentro da cave.
        """
        return not (0 <= self._trecho < self._total)

    def ja_foi_feito(self, trecho: int) -> bool:
        return trecho in self._feitos

    # ==================================================================
    # Escrita -- os três momentos do ciclo de vida
    # ==================================================================

    def entrei_na_cave(self) -> None:
        """Instância nova: os bosses estão todos vivos de novo.

        O desfaz-refaz do time (`MANUTENCAO`) ressuscita os quatro, então
        lembrar o que foi morto na ida anterior faria o bot pular sala cheia.
        """
        self._trecho = 0
        self._feitos.clear()
        self._em_andamento = False

    def a_run_comecou(self) -> None:
        """O preparo de dentro terminou e a contagem da run vale.

        Separado de `entrei_na_cave` porque a disputa da porta pode ter levado
        uma hora, e porque quem retoma no meio da cave (morreu e reviveu
        dentro) passa por aqui sem ter passado por lá.
        """
        self._em_andamento = True

    def sai_da_cave(self) -> None:
        """Fora. O que foi feito lá dentro deixa de valer."""
        self._trecho = 0
        self._feitos.clear()
        self._em_andamento = False

    def marcar_feito_e_avancar(self) -> int | None:
        """Fecha o trecho atual e devolve o próximo PENDENTE.

        `None` quando não sobrou nenhum -- e aí quem chamou sabe que o que falta
        é sair. Pular os já feitos é o que faz a morte custar apenas o caminho
        de volta: o personagem revive no começo da cave, refaz a perna e, num
        ponto que já limpou, não perde nem os segundos de espera.
        """
        if not self.acabou():
            self._feitos.add(self._trecho)

        proximo = self._trecho + 1
        while proximo < self._total and proximo in self._feitos:
            proximo += 1

        self._trecho = proximo
        return None if self.acabou() else proximo

    def pular_para(self, trecho: int) -> None:
        """Retomada por distância, quando não há run em andamento.

        É o caso de abrir o bot com o personagem já dentro da cave: ele não tem
        como saber o que já foi feito, e quem resolve isso é a espera curta em
        cada ponto de batalha -- ponto limpo não engaja, e o bot segue.
        """
        self._trecho = trecho


__all__ = ["ProgressoDaCave"]
