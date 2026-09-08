"""VIGIA DA VIDA: a vida CAIU desde a leitura anterior?

=========================================================================
O BURACO QUE ELE FECHA
=========================================================================

Morto o mob, se a flag de combate continua alta (outro mob batendo), o laço do
APP não tinha o que fazer: o TAB só existia no ramo FORA de batalha, e o ramo EM
batalha rodava a macro contra um alvo que já não existe. A volta abortava na
primeira linha, e o personagem ficava apanhando parado até morrer -- foi o que
matou três personagens em 07/09/2026
(`docs/decisoes/madrugada-07-09-2026.md`).

=========================================================================
VIDA QUE CAI É PROVA POSITIVA DE AGRESSÃO
=========================================================================

A flag de combate diz *"estou em batalha"*, que é um ESTADO -- e ela fica alta
por motivos que não são dano entrando. A vida caindo diz *"estão me batendo
AGORA"*, que é um EVENTO.

É a distinção que o usuário já tinha feito para a observação depois da morte:
*"dá para conferir pela vida atual do personagem, que vai estar descendo
também"*.

=========================================================================
AS TRÊS REGRAS, E CADA UMA FECHA UM ERRO
=========================================================================

**SÓ QUEDA CONTA.** Regeneração e cura SOBEM a vida, então nunca disparam -- a
comparação é estritamente `<`.

**A RÉGUA ANDA PARA OS DOIS LADOS.** Toda leitura vira a nova régua, inclusive
quando a vida sobe. Sem isso, uma poção deixaria a régua velha lá atrás e o
próximo golpe pareceria uma queda muito maior do que foi.

**"NÃO SEI" NÃO ACUSA NADA.** Sem leitura, a régua fica como está e a marca não
muda. Inventar agressão a partir de leitura falha faria o bot reagir no escuro.

QUEDA DE UM DÉCIMO JÁ CONTA, e é de propósito: quem consome isto só age quando
NÃO tem alvo vivo (ver `executor._reflexo_de_sobrevivencia`), então o falso
positivo custa um TAB. Exigir um limiar custaria vida no caso em que o dano
entra devagar -- que é justamente o caso em que ninguém percebe.

MÓDULO DE USO GERAL: recebe NÚMEROS e não `BotContext`. Não lê memória, não
aperta tecla, não conhece janela. Qualquer ecossistema pode usar.
"""

from __future__ import annotations

__all__ = ["VigiaDaVida"]


class VigiaDaVida:
    """A régua da vida entre duas voltas. Uma instância por conta."""

    def __init__(self) -> None:
        self.ultima: float | None = None
        self.sob_ataque = False

    def anotar(self, vida: float | None, lutando: bool) -> bool:
        """Registra a leitura e devolve se há agressão em curso.

        `lutando=False` derruba a marca: fora de batalha não há agressão em
        curso, e manter a marca a faria atravessar até a luta seguinte.
        """
        if vida is None:
            return self.sob_ataque
        anterior = self.ultima
        self.ultima = vida
        if not lutando:
            self.sob_ataque = False
            return False
        if anterior is not None and vida < anterior:
            self.sob_ataque = True
        return self.sob_ataque

    def caiu_de(self) -> float | None:
        """A régua anterior, só para o log dizer de quanto para quanto."""
        return self.ultima

    def consumir(self) -> None:
        """Marca atendida -- o agressor virou alvo. Ver o item 2 do reflexo."""
        self.sob_ataque = False
