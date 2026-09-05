"""Quem CAIU numa fase de luta, por nome.

=========================================================================
EVIDÊNCIA POSITIVA, NUNCA PORTÃO
=========================================================================

O nome do alvo não pode BARRAR nada -- o campo guarda texto em algumas
entidades e ponteiro em outras, e slots são reaproveitados. A medição está em
`bot/combate.py`, bloco "NÃO EXISTE MAIS CONFERÊNCIA DO ALVO POR NOME": dois de
três Gun Witch leram lixo.

Com a fonte de nome sendo a ENTIDADE (mudança de 25/08/2026) ele melhorou muito
-- na HH, 74 de 76 leituras vieram limpas e com nível --, mas os ~2,6% de lixo
restantes bastam para a regra continuar valendo: serve para AFIRMAR ("vi o
Fa-Yuan cair") e não para NEGAR ("não vi, logo não morreu").

Quem consulta precisa sempre de um caminho alternativo.

=========================================================================
POR QUE MORA NO `core/`
=========================================================================

"Quem caiu" é pergunta sobre o JOGO, não sobre uma cave: não depende de
`BotContext`, de mapa nem de ecossistema. As duas caves têm a mesma pergunta --
a HH usa para creditar o boss do ponto, e a BC pode usar para a mesma coisa no
Blaze Skull Marshal quando alguém medir o nome dele.
"""
from __future__ import annotations


class RegistroDeMortes:
    """Os nomes vistos caindo desde o último `esquecer`."""

    def __init__(self) -> None:
        self._nomes: set[str] = set()

    def esquecer(self) -> None:
        """Zera o registro. Chamado no começo de cada fase de luta.

        POR EPISÓDIO: sem isto o nome de um boss morto na fase anterior
        provaria a morte do desta.
        """
        self._nomes = set()

    def anotar(self, nomes) -> None:
        """Anota quem caiu. Ignora vazios e `None`."""
        self._nomes.update(n for n in (nomes or ()) if n)

    def caiu(self, nome: str) -> bool:
        """Vi este nome cair?

        Casamento por SUBSTRING e sem caixa, como o resto do bot faz com nome
        de alvo: a leitura às vezes traz espaço a mais ou um sufixo.
        """
        procurado = (nome or "").strip().lower()
        if not procurado:
            return False
        return any(procurado in caiu.lower() for caiu in self._nomes)

    @property
    def nomes(self) -> frozenset[str]:
        return frozenset(self._nomes)


__all__ = ["RegistroDeMortes"]
