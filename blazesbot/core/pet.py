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
