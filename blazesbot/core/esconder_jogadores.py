"""Esconder os outros jogadores: a tecla F12 PRESA, e mais nada.

=============================================================================
O QUE É
=============================================================================

A tecla de esconder jogadores (F12, por padrão) esconde **enquanto está
apertada**. Então o bot a aperta e NÃO SOLTA -- `prender_a_tecla`, apoiada em
`Input.segurar_para_sempre`, que põe a tecla numa lista de intocáveis para que
nenhum `key_up` posterior a solte.

Regra do usuário, dita em 07/09/2026 e reafirmada em 10/09/2026: *"é sobre
deixar a tecla F12 down sempre clicado, nunca soltar"*, e *"a regra é apenas dar
um key_down no F12 apenas, sem o key_up"*.

Serve para o clique direito no chão não acertar outro personagem quando o bot
vai catar loot, e de quebra tira da tela dezenas de personagens que o cliente
desenharia.

=============================================================================
O TRUQUE DO CHAT FOI REMOVIDO -- 10/09/2026
=============================================================================

Havia aqui uma sequência que "grudava" o esconder: com a tecla presa, abrir o
chat com Enter deixava os personagens escondidos permanentemente; soltava-se a
tecla e fechava-se o chat com outro Enter.

**Ela não servia para o bot**, e quem disse foi quem a ensinou: *"o truque do
F12 só funciona para o usuário, não precisa ser feito pelo bot, então pode
remover esse truque que ensinei, ele não faz sentido para o bot"*.

Ela já estava desligada por interruptor desde 19/08/2026, e carregava o defeito
mais caro deste módulo: **se o segundo Enter não pegasse, o chat ficava aberto**
-- e daí em diante toda tecla do bot (skill, poção, montaria, TAB) ia para o
campo de texto, com um Enter posterior PUBLICANDO aquilo no chat.

Com a tecla simplesmente presa, nada disso existe: não se abre chat nenhum.

O que sobrou é isto e o `segurado(...)`, que segura a tecla durante um bloco --
e que também está desligado por interruptor, porque com a tecla presa para
sempre não há o que segurar.

Ver `docs/decisoes/hh.md` §28.
"""
from __future__ import annotationsfrom collections.abc import Callable__all__ = ["PRENDER_A_TECLA", "SEGURAR_ATIVADO", "prender_a_tecla",
           "segurado"]

# ===========================================================================
# A TECLA PRESA PARA SEMPRE -- o caminho do patcher, trazido em 07/09/2026
# ===========================================================================
#
# `True` = o bot manda `WM_KEYDOWN` da tecla de esconder e NUNCA o `WM_KEYUP`,
#          reafirmando de tempos em tempos. Sem chat, sem Enter, sem risco.
#
# É o que o `BlazesBot - PetBug.exe` faz, descoberto lendo o binário
# (`docs/decisoes/pet-bug-engenharia-reversa.md`): a tecla esconde ENQUANTO
# ESTÁ APERTADA, então um KEYDOWN que nunca é solto esconde para sempre.
#
# POR QUE ISTO É MELHOR QUE O TRUQUE DO CHAT: o truque desta casa prendia a
# tecla e ABRIA O CHAT com Enter para "grudar" o estado -- e o chat que não
# fecha é o defeito mais caro deste módulo (toda tecla do bot vira texto, e um
# Enter posterior PUBLICA aquilo). O caminho do patcher chega no mesmo lugar
# sem nunca tocar no chat.
PRENDER_A_TECLA = True

# ===========================================================================
# INTERRUPTOR DO F12 PRESO -- DESLIGADO EM 19/08/2026
# ===========================================================================
#
# `False` = `segurado(...)` não segura nada. O `with` continua nos lugares, e o
#           bloco roda igual.
# `True`  = segura a tecla durante o processo (entrada na cave, venda, Fay).
#
# POR QUE DESLIGOU: o usuário passou a usar o `RaaskiBot - PetBug.exe`, que faz o
# esconder POR SESSÃO (e mais um "pet bug" contra disconnect) num clique que cobre
# todos os clientes. Ver `core/petbug.py`.
#
# *"por enquanto desativa esse click no F12, em vez disso você vai executar esse
# arquivo"* -- e "por enquanto" é o motivo de isto ser interruptor e não remoção:
# o caminho longo já corrigia o defeito do bloco curto e continua testado, então
# religar não é ligar código não verificado.
SEGURAR_ATIVADO = False

def prender_a_tecla(tecla: str, segurar_para_sempre, log) -> bool:
    """Deixa a tecla de esconder jogadores apertada, para sempre. `True` = mandou.

    `segurar_para_sempre` é injetado (`Input.segurar_para_sempre`) -- este
    módulo continua sem saber o que é janela.

    PODE (E DEVE) SER CHAMADA DE NOVO. Uma tecla fisicamente presa repete
    sozinha; reafirmar é imitar isso, e é o que recupera o estado quando o
    cliente o perde -- num relogin, por exemplo, em que a janela é outra.

    SEM TECLA CONFIGURADA NÃO HÁ O QUE FAZER, e isso não é erro: quem não
    configurou o esconder simplesmente não usa.
    """
    if not PRENDER_A_TECLA:
        return False
    tecla = (tecla or "").strip()
    if not tecla:
        return False
    try:
        return bool(segurar_para_sempre(tecla))
    except Exception as exc:
        log.debug("Esconder jogadores: não deu para prender %r (%s).",
                  tecla, exc)
        return False


# ===========================================================================
# A OUTRA FORMA: SEGURAR A TECLA DURANTE O CLIQUE NO NPC
# ===========================================================================
#
# O truque do chat acima está DESLIGADO e fica guardado para teste futuro. Esta é
# a forma que roda hoje, e ela é do usuário (19/08/2026):
#
#   *"em vez de tentar o bug, você vai deixar apertada o F12 desde o momento que
#   chegou na coordenada até terminar o processo"* -- e, refinando: *"toda vez que
#   for apertar no NPC precisa clicar o F12; sempre que precisar o clique no NPC
#   fora da cave é importante que o F12 esteja apertado... só no par de clique,
#   porque só atrapalha quando tenta clicar no NPC em si."*
#
# É uma regra melhor que os três blocos que eu havia proposto, e por um motivo
# estrutural: TODO clique de NPC do bot passa por um lugar só,
# `UIService._abrir_dialogo_e_clicar`. Uma mudança ali cobre o link da cave, o
# Rich, o Altar Stone e a saída -- sem espalhar `with` por quatro arquivos.
#
# ---------------------------------------------------------------------------
# O QUE NÃO ESTÁ MEDIDO, E É HONESTO DIZER
# ---------------------------------------------------------------------------
#
# `Input.key_down` manda **um** `WM_KEYDOWN`. Se o jogo trata a mensagem e guarda
# a própria flag até o `WM_KEYUP`, a tecla conta como presa. Se ele consulta o
# estado do teclado (`GetAsyncKeyState`), mensagem nenhuma o convence.
#
# A favor: o `key()` normal faz skill e poção saírem, então o jogo REAGE à
# mensagem. Contra: ninguém mediu ESTE caso. O usuário vai olhar a tela -- as
# outras contas dele são os "outros jogadores" na entrada da cave e no vendedor,
# então se funcionar elas desaparecem.
#
# Por isso o log diz claramente quando segurou e por quanto tempo: sem isso não
# há como separar "não funciona" de "não rodou".
#
# CUSTO DE ERRAR: zero. Uma mensagem ignorada pelo cliente.


class _Segurado:
    """Segura a tecla enquanto o bloco roda, e SOLTA em qualquer saída.

    Context manager e não duas chamadas porque as saídas são muitas: fim normal,
    `StopRequested`, `Disconnected`, `FarmDesligado`, e qualquer exceção do
    clique. **Tecla presa que não é solta faz o bot inteiro passar a jogar com ela
    apertada** -- e aqui isso duraria o resto da sessão.

    Sem tecla configurada, o bloco roda e nada acontece.
    """

    __slots__ = ("_inicio", "_log", "_pegou", "_segurar", "_soltar", "_tecla")

    def __init__(self, tecla, segurar, soltar, log, relogio):
        self._tecla = tecla
        self._segurar = segurar
        self._soltar = soltar
        self._log = log
        self._inicio = relogio
        self._pegou = False

    def __enter__(self):
        if not SEGURAR_ATIVADO or not self._tecla:
            return self
        self._segurar(self._tecla)
        self._pegou = True
        self._log.info("Esconder jogadores: segurando %s durante o clique no NPC",
                       self._tecla)
        return self

    def __exit__(self, *_excecao):
        if self._pegou:
            self._soltar(self._tecla)
            self._log.info("Esconder jogadores: soltei %s", self._tecla)
        return False        # nunca engole a exceção de quem chamou


def segurado(
    *,
    tecla: str,
    segurar: Callable[[str], None],
    soltar: Callable[[str], None],
    log,
    relogio: Callable[[], float] | None = None,
):
    """`with segurado(...):` mantém a tecla de esconder presa dentro do bloco.

    Recebe PEÇAS, como o resto deste módulo -- é o que permite qualquer
    ecossistema usar, e testar sem jogo aberto.
    """
    return _Segurado(tecla, segurar, soltar, log, relogio)
