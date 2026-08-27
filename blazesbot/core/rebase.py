"""Escolha entre o endereço estático ATUAL e o candidato REBASEADO.

=============================================================================
POR QUE ISTO EXISTE
=============================================================================

Boa parte dos endereços estáticos deste projeto foi transplantada do GhostBot,
e está dito com todas as letras em `memory.py`: *"Descoberto no GhostBot"*. O
que veio junto e não estava dito é que aqueles valores são da **versão 6139 do
cliente**, e o jogo está na **6400**.

Entre as duas versões o segmento de dados inteiro andou **+0x60**. Isso já foi
medido e corrigido em DOIS endereços:

    PLAYER_BASE_RVA   0x00D450EC  ->  0x00D4514C     (+0x60)
    ADDR_UI_ROOT      0x012CE2E0  ->  0x012CE340     (+0x60)

E o comentário do `ADDR_UI_ROOT` registra a lição: *"o segmento de dados
inteiro andou junto, e este endereço tinha ficado para trás"*.

Os VIZINHOS do mesmo banco ficaram para trás também -- e são exatamente as
leituras que o projeto documenta como quebradas:

    ADDR_SURROUNDINGS  0x012CE2DC   "a leitura de arredores por memória não
                                     funciona neste cliente"
    ADDR_MODAL         0x012CE35C   "ADDR_MODAL está errado (guarda ponteiro,
                                     modal_open() é sempre False)"
    ADDR_TEAM_SIZE     0x0106D328   "a confirmação dependia de team_size(), e
                                     essa leitura não funciona neste cliente"

Ou seja: três defeitos arquivados como *propriedade do cliente* têm a mesma
assinatura de um rebase parcial. Note a aritmética do primeiro:
`0x012CE2DC + 0x60 = 0x012CE33C`, que é `ADDR_UI_ROOT - 4` -- nas DUAS versões
o endereço dos arredores fica um DWORD abaixo da raiz de UI. Não é
coincidência; é a mesma tabela.

=============================================================================
POR QUE NÃO TROCAR A CONSTANTE E PRONTO
=============================================================================

Porque isso seria repetir o erro que estamos consertando: enfiar no código um
endereço que ninguém mediu NESTE cliente. O `+0x60` é hipótese forte, não fato.

Então o desenho é: **tenta os dois e fica com o que responder**, com um piso
inegociável -- **nunca ficar pior que hoje**. A troca só acontece quando a
evidência é inequívoca:

    candidato PLAUSÍVEL  e  atual NÃO plausível   ->  troca
    qualquer outro caso                           ->  mantém o atual

"Ambos plausíveis" NÃO é motivo para trocar. Um endereço errado que por acaso
lê um valor no intervalo esperado é o modo de falha mais caro que existe aqui
-- ler lixo com sucesso é pior que não ler, e `memory.resolve` já foi escrito
com essa regra.

=============================================================================
DECIDE UMA VEZ, NÃO A CADA LEITURA
=============================================================================

O binário não muda no meio da sessão, então medir a cada leitura é pagar duas
chamadas ao SO para reconfirmar o que já se sabe -- num caminho que roda dentro
do laço de combate. A decisão é tomada na primeira leitura e guardada.

Uma decisão INCONCLUSIVA (nenhum dos dois respondeu) não é guardada: ela
significa "ainda não deu para saber", não "não tem resposta". O caso concreto é
o painel de arredores, que só produz texto quando está ABERTO -- provar com ele
fechado não prova nada, e cravar a resposta ali seria decidir no vazio.

Módulo de LÓGICA PURA: não importa `pymem`, não conhece endereço nenhum, recebe
funções de LEITURA. É o que permite testar a decisão inteira sem o jogo aberto,
no mesmo molde do `VigiaDoAlvo`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "DESLOCAMENTO_6139_PARA_6400",
    "Decisao",
    "SeletorDeEndereco",
    "candidato_rebaseado",
]


# Deslocamento MEDIDO entre a versão 6139 e a 6400 do cliente, em dois
# endereços independentes (`PLAYER_BASE_RVA` e `ADDR_UI_ROOT`). É o mesmo para
# os dois, e é a hipótese que este módulo testa nos vizinhos que ficaram para
# trás.
DESLOCAMENTO_6139_PARA_6400 = 0x60


def candidato_rebaseado(endereco: int) -> int:
    """O mesmo endereço, deslocado para a versão 6400."""
    return endereco + DESLOCAMENTO_6139_PARA_6400


@dataclass(frozen=True, slots=True)
class Decisao:
    """O que foi decidido para um endereço, e com base em quê.

    Guardar o PORQUÊ junto com a escolha não é luxo: é o que faz uma linha de
    log responder "por que ele trocou?" sem ninguém precisar reabrir o assunto.
    """

    rotulo: str
    escolhido: int
    atual: int
    candidato: int
    valor_atual: Any
    valor_candidato: Any
    motivo: str

    @property
    def trocou(self) -> bool:
        return self.escolhido != self.atual

    def __str__(self) -> str:
        return (
            f"{self.rotulo}: {'CANDIDATO' if self.trocou else 'atual'} "
            f"@{self.escolhido:#010x} ({self.motivo}) -- "
            f"{self.atual:#010x}={self.valor_atual!r}, "
            f"{self.candidato:#010x}={self.valor_candidato!r}"
        )


class SeletorDeEndereco:
    """Decide, uma vez por rótulo, qual endereço estático usar.

    Uma instância por instância de `Memory` -- ou seja, uma por processo do
    cliente. Morre junto com ela, então não existe entrada órfã apontando para
    um processo que já fechou (a mesma armadilha que `vision._pools` e
    `ui_service._BUSCAS_SEM_LEITURA` pagaram caro).
    """

    def __init__(self, registrar: Callable[[str], None] | None = None) -> None:
        self._decidido: dict[str, int] = {}
        self._historico: dict[str, Decisao] = {}
        self._registrar = registrar

    # -- consulta ----------------------------------------------------------

    def decisoes(self) -> dict[str, Decisao]:
        """Cópia do que já foi decidido -- para o log e para o diagnóstico."""
        return dict(self._historico)

    def ja_decidiu(self, rotulo: str) -> bool:
        return rotulo in self._decidido

    # -- a escolha ---------------------------------------------------------

    def escolher(
        self,
        rotulo: str,
        atual: int,
        ler: Callable[[int], Any],
        plausivel: Callable[[Any], bool],
        candidato: int | None = None,
    ) -> int:
        """Devolve o endereço a usar para `rotulo`.

        `ler(endereco)` faz a leitura COMPLETA a partir daquele endereço --
        cadeia de ponteiros inclusive -- e devolve o valor final (ou `None`).
        `plausivel(valor)` responde se aquele valor pode ser o que se procura.

        A primeira chamada mede; as seguintes só consultam o que foi decidido.
        """
        guardado = self._decidido.get(rotulo)
        if guardado is not None:
            return guardado

        alvo = candidato if candidato is not None else candidato_rebaseado(atual)

        valor_atual = self._ler_sem_explodir(ler, atual)
        valor_candidato = self._ler_sem_explodir(ler, alvo)

        atual_ok = self._plausivel_sem_explodir(plausivel, valor_atual)
        candidato_ok = self._plausivel_sem_explodir(plausivel, valor_candidato)

        if candidato_ok and not atual_ok:
            decisao = Decisao(rotulo, alvo, atual, alvo, valor_atual,
                              valor_candidato,
                              "o candidato +0x60 respondeu e o atual não")
        elif atual_ok and not candidato_ok:
            decisao = Decisao(rotulo, atual, atual, alvo, valor_atual,
                              valor_candidato,
                              "o atual respondeu; o candidato não")
        elif atual_ok and candidato_ok:
            # Empate NÃO troca. Ver o cabeçalho: dois endereços plausíveis
            # significa que a plausibilidade não distingue, e trocar aí é
            # apostar. Fica o de hoje, e a ambiguidade vai para o log.
            decisao = Decisao(rotulo, atual, atual, alvo, valor_atual,
                              valor_candidato,
                              "AMBOS plausíveis -- mantém o atual, sem apostar")
        else:
            # Inconclusivo: NÃO guarda. Pode ser só a hora errada de perguntar
            # (o painel de arredores fechado, o cliente ainda carregando).
            decisao = Decisao(rotulo, atual, atual, alvo, valor_atual,
                              valor_candidato,
                              "nenhum dos dois respondeu -- tenta de novo depois")
            self._anotar(rotulo, decisao, guardar=False)
            return atual

        self._anotar(rotulo, decisao, guardar=True)
        return decisao.escolhido

    # -- internos ----------------------------------------------------------

    def _anotar(self, rotulo: str, decisao: Decisao, guardar: bool) -> None:
        if guardar:
            self._decidido[rotulo] = decisao.escolhido
        anterior = self._historico.get(rotulo)
        self._historico[rotulo] = decisao
        # Só registra o que é NOVIDADE. Sem isto, um rótulo inconclusivo
        # (que repete a cada leitura, por desenho) encheria o log de dev com a
        # mesma linha -- e log que se repete deixa de ser lido.
        if self._registrar is not None and (
            anterior is None or anterior.motivo != decisao.motivo
        ):
            try:
                self._registrar(str(decisao))
            except Exception:
                # Registrar nunca pode derrubar uma leitura de memória.
                pass

    @staticmethod
    def _ler_sem_explodir(ler: Callable[[int], Any], endereco: int) -> Any:
        try:
            return ler(endereco)
        except Exception:
            return None

    @staticmethod
    def _plausivel_sem_explodir(plausivel: Callable[[Any], bool], valor: Any) -> bool:
        if valor is None:
            return False
        try:
            return bool(plausivel(valor))
        except Exception:
            return False
