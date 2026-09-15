"""O contrato de POSIÇÃO de um ponto de luta da HH.

=========================================================================
POR QUE ISTO EXISTE
=========================================================================

Auditoria de 05/09/2026, defeito #2. A rotina aceitava "saí de batalha" como
"limpei este ponto" -- e as duas coisas não são a mesma.

O que o log mostrou, no primeiro boss:

    DESTRAVADO (o pacote do Fa-Yuan) em 39s: 6 morte(s), 6 TAB, 91 golpes
    ALVO MORREU: Elite Blackshirt Bandit                     (x6)
    HH: andei atrás dos mobs do Fa-Yuan (de (275,138) para (317,149))
    Não consegui parar em (275,138) ... (estou em (317,149))
    ...
    a run continua no trecho do Dupla (1 de 4 já feitos)

O personagem perseguiu mobs, limpou um pacote **46 unidades fora** do ponto do
boss (271,137), e a run creditou o Fa-Yuan. O boss nunca engajou.

Três defeitos encadeados produziram isso, e este módulo fecha os três:

  1. A ÂNCORA ERA UMA POSIÇÃO CAPTURADA, e não o waypoint do mapa. Sob rollback
     ela guarda onde o rollback largou o personagem -- no log, (275,138) em vez
     de (271,137).
  2. A VITÓRIA NÃO CONFERIA ONDE ACONTECEU. `limpar_o_combate` responde "a flag
     baixou", nunca "o ponto está limpo".
  3. A FALHA DO RETORNO ERA DESCARTADA: `_voltar_ao_ponto` era `-> None` e
     jogava fora o booleano de `encostar_no_ponto`.

=========================================================================
O QUE ESTE MÓDULO NÃO DECIDE
=========================================================================

Ele não sabe lutar, nem quando desistir. Responde *"estou nele?"* e, desde
13/09/2026, *"o que saiu de batalha ali conta como vitória?"* -- e quem age é a
rotina.

O `voltar_para_ele` SAIU nessa data. Ele caminhava de volta ao ponto depois da
luta, e o sucesso dessa caminhada virou, sem querer, o certificado de morte do
boss -- que é o defeito de §35. Quem refaz o caminho agora é o estado
`ATE_O_BOSS`, que anda pelo mapa em vez de clicar em linha reta, e a caminhada
deixou de provar qualquer coisa sobre o boss.
"""
from __future__ import annotations

from typing import NamedTuple

from . import mapa_hh

# Quantos vetos SEGUIDOS de rollback um mesmo trecho aguenta antes de a rotina
# parar de insistir e mandar se situar de novo.
#
# TRÊS, e o número não é arredondamento: cada veto custa refazer o trecho
# inteiro (`MAX_SEGUNDOS_POR_TRECHO`), então insistir sem limite prenderia a run
# num ponto. Três cobre a dessincronia passageira -- nas 9 ocorrências medidas
# em 11/09/2026 nenhuma se repetiu no mesmo trecho -- e ainda devolve o controle
# à máquina de estados em tempo de ela tentar outra coisa.
#
# E O DESFECHO DE ESTOURAR NÃO É CREDITAR. Creditar sem prova é exatamente o
# defeito que esta trava existe para fechar; quem decide depois é o `RECUPERAR`,
# que relê onde o personagem está.
VETOS_ANTES_DE_DESISTIR = 3


class PontoDoBoss:
    """O waypoint que fecha um trecho, e a régua de estar nele.

    `ponto` vem SEMPRE do mapa (`TRECHOS_DOS_BOSSES[...][2]`, que é o último
    waypoint do trecho). Nunca de uma leitura de posição: leitura é onde o
    personagem está, e o contrato é sobre onde ele DEVERIA estar.
    """

    def __init__(self, rotulo: str, ponto: tuple[int, int],
                 tolerancia: int) -> None:
        self.rotulo = rotulo
        self.ponto = ponto
        self.tolerancia = tolerancia

    def distancia_de(self, pos: tuple[int, int] | None) -> float | None:
        """Quão longe do ponto. `None` quando não há leitura."""
        if pos is None:
            return None
        return mapa_hh.distancia(pos, self.ponto)

    def estou_nele(self, pos: tuple[int, int] | None) -> bool:
        """O personagem está no ponto, dentro da tolerância?

        SEM LEITURA, RESPONDE `False`. É o oposto do resto do bot, onde "não
        sei" costuma liberar -- e aqui é de propósito: esta resposta autoriza
        CREDITAR um boss. Creditar sem saber onde o personagem está é
        exatamente o defeito que o módulo existe para fechar; o custo de errar
        para o lado seguro é refazer um trecho.
        """
        distancia = self.distancia_de(pos)
        return distancia is not None and distancia <= self.tolerancia

class VeredictoDoBoss(NamedTuple):
    """Creditar este boss, e a frase que explica por quê."""

    creditar: bool
    motivo: str


def verificar_morte_do_boss(
    ponto: PontoDoBoss,
    onde_acabou: tuple[int, int] | None,
    memoria_confirmou: bool,
) -> VeredictoDoBoss:
    """A DUPLA VALIDAÇÃO: a flag baixou, mas ONDE ela baixou?

    =====================================================================
    O EXPLOIT QUE ISTO FECHA
    =====================================================================

    `in_battle == False` responde *"não há mais ninguém batendo em mim"*, e
    isso tem DUAS causas que a flag não distingue: o alvo morreu, ou o
    personagem deixou de estar perto dele. Um rollback de servidor produz a
    segunda sem a primeira -- o servidor puxa o personagem para trás, os mobs
    ficam fora de alcance, a flag cai, e a rotina lê "vitória".

    Cruzar a flag com a POSIÇÃO NO INSTANTE EM QUE ELA CAIU anula isso, porque
    o rollback é justamente um evento de posição: ele não consegue produzir os
    dois fatos ao mesmo tempo. Morte verdadeira acontece ao alcance do boss;
    rollback acontece longe dele, por definição.

    =====================================================================
    POR QUE "VOLTEI PARA O PONTO" NÃO SERVE COMO PROVA
    =====================================================================

    Era o que a rotina fazia antes, e é o defeito medido em 11/09/2026: saiu de
    batalha longe, caminhou de volta, e o sucesso da CAMINHADA creditava o boss.
    Mas voltar a pé para uma coordenada é trivial -- prova apenas que o
    pathfinding funciona. As 9 ocorrências do log:

        boss      onde a batalha acabou   distância   desfecho
        Purple    (470,108)                      56   CREDITOU e SAIU DA CAVE
        Purple    (469,109)                      57   CREDITOU e SAIU DA CAVE
        Purple    (471,107)                      55   CREDITOU e SAIU DA CAVE
        Purple    (471,108)                      55   CREDITOU e SAIU DA CAVE
        Purple    (471,108)                      55   CREDITOU e SAIU DA CAVE
        Fa-Yuan   (322,146) e outras 3       27..57   CREDITOU

    Nenhuma delas tem `ALVO MORREU` nem confirmação de morte pela memória: o
    bot lutou 17-19 s, deu 109-123 golpes de rotação, a flag caiu 55 unidades
    fora, e o trecho foi creditado. Com o `Purple` -- o ÚLTIMO boss -- creditar
    significa **sair da cave**, que é o relato do usuário.

    =====================================================================
    AS DUAS PROVAS QUE VALEM, E A ORDEM DELAS
    =====================================================================

      1. **A MEMÓRIA VIU O NOME CAIR.** Vale de qualquer lugar: responde *"o
         boss morreu?"*, que é a pergunta de verdade. É o caminho normal (309
         confirmações no mesmo log);
      2. **A POSIÇÃO NO INSTANTE DA SAÍDA.** Reserva para quando a identidade
         não foi legível -- pacote de mobs sem nome, alvo por id. Dentro da
         tolerância do ponto, sair de batalha só tem uma explicação.

    `onde_acabou is None` NÃO credita, e é o único lugar do ecossistema onde
    "não sei" veta em vez de liberar. O motivo está em `estou_nele`: esta
    resposta autoriza creditar um boss, e o custo de errar para o lado seguro é
    refazer um trecho -- contra perder a cave inteira.

    =====================================================================
    O QUE ACONTECE COM A PERSEGUIÇÃO LEGÍTIMA DE MOB RANGED
    =====================================================================

    Mob ranged não vem até o personagem, então limpar o pacote às vezes termina
    a dezenas de unidades do ponto. Sob a regra nova esse caso perde o crédito
    IMEDIATO -- e não perde o boss: a rotina refaz o trecho, chega ao ponto, e
    `esperar_entrar_em_combate` não engaja porque está limpo. Aí o crédito sai
    pelo caminho de `SEGUNDOS_PARA_ENGAJAR`, com o personagem COMPROVADAMENTE
    no ponto. Troca-se um palpite por uma volta a mais e uma prova melhor.

    Ver `docs/decisoes/hh.md` §35.
    """
    if memoria_confirmou:
        return VeredictoDoBoss(
            True, f"{ponto.rotulo}: a memória confirmou a morte pelo nome")

    distancia = ponto.distancia_de(onde_acabou)
    if distancia is None:
        return VeredictoDoBoss(
            False,
            f"{ponto.rotulo}: saí de batalha SEM leitura de posição. Não "
            f"credito o boss sem saber onde a batalha acabou -- refaço o "
            f"trecho.")

    if distancia <= ponto.tolerancia:
        return VeredictoDoBoss(
            True,
            f"{ponto.rotulo}: saí de batalha a {distancia:.0f} unidades do "
            f"ponto (tolerância {ponto.tolerancia}) -- estava nele, o boss "
            f"caiu")

    return VeredictoDoBoss(
        False,
        f"ROLLBACK no {ponto.rotulo}: a batalha acabou em {onde_acabou}, a "
        f"{distancia:.0f} unidades do ponto {ponto.ponto} (tolerância "
        f"{ponto.tolerancia}). Sair de batalha longe do boss é dessincronia, "
        f"não vitória -- NÃO credito, volto e reengajo.")


def do_trecho(trecho: int, tolerancia: int) -> PontoDoBoss:
    """O ponto do trecho `trecho`, lido do mapa.

    Existe para que ninguém monte o par (rótulo, ponto) na mão: os dois vêm da
    MESMA linha de `TRECHOS_DOS_BOSSES`, e separá-los é como o ponto do boss e
    o fim do caminho divergiram em 04/09/2026.
    """
    rotulo, _caminho, ponto = mapa_hh.TRECHOS_DOS_BOSSES[trecho]
    return PontoDoBoss(rotulo, ponto, tolerancia)


__all__ = ["VETOS_ANTES_DE_DESISTIR", "PontoDoBoss", "VeredictoDoBoss", "do_trecho",
           "verificar_morte_do_boss"]
