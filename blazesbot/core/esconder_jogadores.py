"""Esconder os outros jogadores, pelo truque do F12 preso com o chat.

=============================================================================
O QUE É, E POR QUE É UM TRUQUE
=============================================================================

A tecla de esconder jogadores (F12, por padrão) esconde enquanto está apertada.
Existe um comportamento do cliente que a faz GRUDAR: com a tecla presa, abrir o
chat com Enter deixa os personagens escondidos permanentemente. Solta-se a tecla
e fecha-se o chat com outro Enter, e o esconder continua valendo.

Serve para o clique direito no chão não acertar outro personagem quando o bot vai
catar loot, e de quebra tira da tela dezenas de personagens que o cliente
desenharia.

=============================================================================
É POR SESSÃO, E O USUÁRIO PODE DESFAZER SEM QUERER
=============================================================================

O grude vale para a sessão. E apertar F12 de novo o desfaz -- inclusive sem
querer, que é o caso comum quando a mesma máquina é usada pela pessoa.

Por isso a sequência roda **antes de CADA entrada na cave**, não uma vez no
login. Custa quatro teclas.

=============================================================================
O PERIGO: SE O CHAT FICAR ABERTO, O BOT DIGITA EM VEZ DE JOGAR
=============================================================================

A sequência ABRE o chat de propósito e depois o fecha. Se o segundo Enter não
pegar, **o chat fica aberto** -- e daí em diante toda tecla do bot (skill, poção,
montaria, TAB) vai para o campo de texto em vez de ir para o jogo. O bot parece
rodando e não faz nada; e um Enter posterior **publica** aquilo no chat.

É a classe de defeito que este projeto persegue -- a ação que parece ter
acontecido e não aconteceu -- com o agravante de o desfecho ser público.

Então o fechamento é CONFERIDO, pelo template `state_chat_aberto.png`: a carinha
amarela no fim da barra de digitação, que só existe com o chat aberto. O template
é a carinha e **não a barra inteira**, porque o texto ao lado do `say:` muda e um
template que inclui texto variável envelhece na primeira mensagem.

E há uma armadilha no conserto: **Enter ALTERNA**. Apertar Enter "por garantia"
quando não se sabe o estado tem metade de chance de ABRIR o chat em vez de
fechar. Por isso, quando a leitura não responde, este módulo **não aperta nada** e
devolve "não sei" -- deixar como está é melhor que apostar.

MÓDULO DE USO GERAL: recebe PEÇAS e não `BotContext`, no molde do
`watchdog.avaliar_saude`. Qualquer ecossistema pode chamar.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["ATIVADO", "SEGURAR_ATIVADO", "TECLA_DO_CHAT", "Resultado",
           "esconder_jogadores", "segurado"]

# ===========================================================================
# INTERRUPTOR -- DESLIGADO EM 19/08/2026
# ===========================================================================
#
# `False` = o truque não é executado. `esconder_jogadores` devolve na hora, sem
#           apertar nada, e -- isto é o que importa -- com `seguro_para_seguir`
#           VERDADEIRO: desligado não pode bloquear a entrada na cave.
# `True`  = executa a sequência inteira.
#
# Decisão do usuário: "por enquanto vamos deixar sem ele, para testar outra
# hora". O pedido foi para COMENTAR o bug, e a convenção da casa diz o
# contrário: *"Interruptor, não comentário nem apagar. Caminho que sai de uso
# vira `X = False` no topo do módulo, com os testes forçando o caminho ligado
# para ele não apodrecer."*
#
# A diferença importa aqui mais que no caso comum. O que este módulo faz é
# ABRIR O CHAT DE PROPÓSITO, e o que o torna seguro é a conferência de que ele
# fechou. Código comentado não roda em teste nenhum: quando alguém
# descomentasse, meses depois, estaria ligando um caminho que abre o chat sem
# ninguém ter conferido que a parte que o fecha continua funcionando. Ligar de
# volta não pode ser ligar código não testado -- e é exatamente por isso que a
# regra existe.
#
# `tests/test_esconder_jogadores.py` força `ATIVADO = True` para todo o módulo,
# então a sequência inteira continua sendo exercitada a cada corrida da suíte.
ATIVADO = False

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

# Tecla que abre e fecha o chat. Não é configurável: é o Enter, e ele não muda.
TECLA_DO_CHAT = "ENTER"

# Espera entre os passos da sequência. O cliente precisa processar a abertura do
# chat antes de a tecla ser solta, senão o grude não acontece.
ESPERA_ENTRE_PASSOS = 0.3

# Enters de fechamento antes de desistir. Enter ALTERNA o chat, então cada
# tentativa só acontece com a leitura dizendo "ainda aberto" -- nunca no escuro.
TENTATIVAS_DE_FECHAR = 3

# Leituras seguidas sem resposta antes de desistir de conferir. A captura falha
# durante queda e relogin, e insistir ali não produz informação.
LEITURAS_SEM_RESPOSTA = 2


@dataclass(frozen=True, slots=True)
class Resultado:
    escondeu: bool
    chat_fechado: bool | None      # None = não deu para conferir
    motivo: str

    @property
    def seguro_para_seguir(self) -> bool:
        """Só é seguro com o chat CONFIRMADAMENTE fechado.

        `None` não conta. Seguir com o chat possivelmente aberto é entrar na cave
        com o teclado do bot desviado para o campo de texto -- e essa run está
        perdida antes de começar.
        """
        return self.chat_fechado is True

    def __str__(self) -> str:
        return self.motivo


def _conferir(chat_aberto: Callable[[], bool | None]) -> bool | None:
    """Pergunta se o chat está aberto, insistindo só enquanto NÃO SEI."""
    for _ in range(LEITURAS_SEM_RESPOSTA):
        resposta = chat_aberto()
        if resposta is not None:
            return resposta
    return None


def esconder_jogadores(
    *,
    tecla: str,
    segurar: Callable[[str], None],
    soltar: Callable[[str], None],
    apertar: Callable[[str], None],
    chat_aberto: Callable[[], bool | None],
    esperar: Callable[[float], None],
    log,
) -> Resultado:
    """Faz a sequência e CONFERE que o chat fechou.

    Devolve sempre; nunca levanta. Quem chamou decide o que fazer com um
    `seguro_para_seguir` falso -- e no BC a decisão é não entrar na cave.

    `tecla` vazia = o usuário não configurou, e não há nada a fazer. Isso é
    sucesso, não falha: o esconder é conveniência, não requisito.
    """
    if not ATIVADO:
        # `chat_fechado=True` de propósito: desligado, o módulo não mexeu no
        # chat, então não há nada de inseguro. Devolver `None` aqui faria a
        # entrada na cave ser abortada por uma coisa que nem aconteceu.
        return Resultado(False, True, "esconder jogadores DESLIGADO "
                                      "(esconder_jogadores.ATIVADO)")

    if not tecla:
        return Resultado(False, True, "sem tecla de esconder jogadores "
                                      "configurada; nada a fazer")

    try:
        segurar(tecla)
        esperar(ESPERA_ENTRE_PASSOS)
        apertar(TECLA_DO_CHAT)          # abre o chat COM a tecla presa: gruda
        esperar(ESPERA_ENTRE_PASSOS)
    finally:
        # `finally` e não "solta depois": uma exceção no meio deixaria F12 preso,
        # e o bot inteiro passaria a jogar com a tecla apertada.
        soltar(tecla)
    esperar(ESPERA_ENTRE_PASSOS)

    for tentativa in range(1, TENTATIVAS_DE_FECHAR + 1):
        aberto = _conferir(chat_aberto)
        if aberto is None:
            return Resultado(True, None,
                             "não consegui conferir se o chat fechou; não vou "
                             "apertar Enter no escuro (ele ALTERNA)")
        if not aberto:
            return Resultado(True, True,
                             f"jogadores escondidos, chat fechado na tentativa "
                             f"{tentativa}")
        log.info("Esconder jogadores: o chat ainda está aberto (tentativa %s)",
                 tentativa)
        apertar(TECLA_DO_CHAT)
        esperar(ESPERA_ENTRE_PASSOS)

    return Resultado(True, False,
                     f"o chat continuou aberto depois de {TENTATIVAS_DE_FECHAR} "
                     "tentativas de fechar")


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
