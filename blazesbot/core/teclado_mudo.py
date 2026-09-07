"""TECLADO MUDO: quando as teclas param de chegar ao cliente, e o que fazer.

=========================================================================
O QUE ACONTECEU EM 07/09/2026 -- 9 h 30 min de uma conta parada
=========================================================================

Da auditoria de 13 h de log (conta `blazestpas`, modo APP):

    02:32:38  o alvo caiu (HP) na linha 9 -- tudo normal
    02:32:41  APP: 1 TAB(s) sem resposta, e HÁ 2 mob(s) vivo(s) por perto
    02:32:44  A bolsa não apareceu em 2.0s depois da tecla 'I'
    ...
    09:29:04  APP: 10390 TAB(s) sem resposta, e HÁ 6 mob(s) vivo(s) por
              perto (o mais próximo a 3). NADA está sendo atacado.
    ...
    12:0x     o usuário mexeu no cliente e tudo voltou

**Nove horas e meia. Zero mobs mortos. 11.978 voltas abortadas de 12.585.**

A leitura de memória funcionou o tempo todo (posição, tabela de entidades,
vida). O que morreu foi a ENTRADA: nem o TAB trocava alvo, nem a tecla de
inventário abria a bolsa. O bot DETECTOU tudo isso e escreveu no log uma vez
por minuto, por nove horas, sem nunca mudar de estratégia.

O defeito não é a detecção -- é não haver DESFECHO para ela.

=========================================================================
POR QUE DUAS AÇÕES, E NÃO "N TABs"
=========================================================================

Apontado pelo council em 07/09/2026: TAB sozinho não prova nada. Ele pode ser
inaplicável (nada ao alcance), o alvo pode não mudar por regra do jogo, a
verificação do efeito pode estar errada. *"O detector deve ser baseado em uma
sequência de ações verificáveis"*.

Então este módulo só acusa quando DUAS teclas independentes falham no mesmo
período: a de trocar alvo E a de abrir a bolsa. Uma pode ser circunstância; as
duas juntas, com mob vivo a três unidades de distância, é entrada inoperante.

E a causa continua sendo HIPÓTESE. Chat aberto, janela modal, `HWND` recriado,
cliente ignorando mensagem sintética, thread de UI degradada -- o log não
separa. Por isso o desfecho não tenta consertar a causa: ele tenta o barato
(ESC) e, não resolvendo, entrega o problema para quem sabe recomeçar do zero.

=========================================================================
A ESCADA, E O QUE FICOU DE FORA
=========================================================================

    suspeito  -> ESC, UMA vez  -> ainda mudo -> declarar queda (relogin)

**O CLIQUE NEUTRO FICOU DE FORA, de propósito.** Era o degrau do meio óbvio
(devolver o foco clicando na área de jogo) e o council reprovou com um
argumento que vale mais que a conveniência: *"não use coordenada aparentemente
vazia como premissa de segurança -- UI, NPCs, drops, overlays e câmera podem
mudar (...) se não há região garantidamente segura, pule o clique e vá para
relogin controlado"*. Clicar às cegas pode selecionar o que não devia, e o
custo de errar é maior que os minutos do relogin.

**O ESC SAI UMA VEZ POR INCIDENTE**, e não em laço: ele também LARGA A MIRA, e
uma tecla que cancela ação legítima não pode virar cadência.

Este módulo é só CONTABILIDADE -- não aperta tecla, não lê memória, não conhece
janela. Quem age é o ecossistema; aqui se decide.
"""

from __future__ import annotations

# O QUE A LIMPEZA DA BOLSA DEVOLVE quando a bolsa NÃO apareceu depois da tecla.
#
# Mora aqui, e não no deletador, porque quem PERGUNTA é o executor -- e ele
# importa só `core.*` (`tests/test_ecossistemas.py`). O deletador importa daqui
# para devolver; o executor importa daqui para entender. Um valor, uma casa.
#
# É diferente de `0` ("não havia lixo"), e essa diferença é o conserto: os dois
# eram `0`, e o `0` calado deixou a segunda testemunha do teclado mudo sem ter
# como depor.
BOLSA_NAO_ABRIU = -1

# Quanto tempo as duas teclas precisam estar mudas antes de o ESC sair.
#
# Curto porque o ESC é barato e reversível (sem alvo, largar a mira não custa
# nada -- e "sem alvo" é justamente a situação aqui). O que não pode é sair a
# cada segundo: ver o cabeçalho.
SEGUNDOS_ATE_O_ESC = 30.0

# Quanto tempo mudo até declarar queda e mandar relogar.
#
# Cinco minutos, e o número vem dos dois lados da conta: o relogin medido nesta
# base custa de 1 a 3 min, e cinco minutos SEM MATAR NADA com mob vivo por
# perto não é uma situação que exista com o cliente saudável -- spot vazio é
# outro caminho e não chega aqui (ver `ha_mob_por_perto`).
#
# Contra o que aconteceu: nove horas e meia. Qualquer número desta ordem já
# teria devolvido a conta ao farm 100 vezes.
SEGUNDOS_ATE_O_RELOGIN = 300.0

# Espaço mínimo entre dois relogins automáticos por teclado mudo.
#
# O relogin é a saída CARA, e um relogin que não resolve não pode virar laço:
# se a causa for outra (conta banida, cliente quebrado), a conta relogaria para
# sempre. Passado o segundo ciclo sem efeito, o desfecho certo é a conta ficar
# parada e VISÍVEL -- ver `desistiu`.
SEGUNDOS_ENTRE_RELOGINS = 900.0

# Quantos relogins por teclado mudo antes de desistir e só gritar.
MAXIMO_DE_RELOGINS = 2


class TecladoMudo:
    """Contabiliza as teclas sem efeito e diz o que fazer. Não faz nada.

    Uma instância por conta. Todo tempo entra por parâmetro (`agora`), para o
    teste não depender de relógio.
    """

    def __init__(self) -> None:
        # Quando o aviso falou por último. Mora aqui, e não em quem chama,
        # porque é contabilidade -- e porque quem chama já tem contas demais.
        self._falei_em = 0.0
        self._tab_mudo_desde: float | None = None
        self._bolsa_muda_desde: float | None = None
        self._esc_enviado_em: float | None = None
        self._ultimo_relogin_em: float | None = None
        self._relogins = 0

    # -- o que o ecossistema RELATA ---------------------------------------

    def tab_sem_resposta(self, agora: float, ha_mob_por_perto: bool) -> None:
        """O TAB não trocou o alvo.

        SEM MOB POR PERTO NÃO CONTA, e é isso que separa "entrada morta" de
        "spot vazio": num spot vazio o TAB não ter efeito é o comportamento
        CERTO do jogo, e relogar por isso seria trocar uma conta parada por
        uma conta parada e deslogada.
        """
        if not ha_mob_por_perto:
            self.tab_respondeu()
            return
        if self._tab_mudo_desde is None:
            self._tab_mudo_desde = agora

    def tab_respondeu(self) -> None:
        """O alvo trocou: a entrada está viva. Zera o incidente inteiro."""
        self._tab_mudo_desde = None
        self._esc_enviado_em = None

    def bolsa_nao_abriu(self, agora: float) -> None:
        if self._bolsa_muda_desde is None:
            self._bolsa_muda_desde = agora

    def bolsa_abriu(self) -> None:
        self._bolsa_muda_desde = None
        self._esc_enviado_em = None

    # -- o que o ecossistema PERGUNTA -------------------------------------

    def mudo_desde(self) -> float | None:
        """Desde quando as DUAS teclas estão sem efeito. `None` = nem todas."""
        if self._tab_mudo_desde is None or self._bolsa_muda_desde is None:
            return None
        return max(self._tab_mudo_desde, self._bolsa_muda_desde)

    def o_que_fazer(self, agora: float) -> str | None:
        """`"esc"`, `"relogar"` ou `None`. Chamável a cada volta.

        Marca o degrau como consumido ao devolvê-lo -- quem chama é obrigado a
        agir, e ninguém recebe o mesmo degrau duas vezes.
        """
        desde = self.mudo_desde()
        if desde is None:
            return None
        parado = agora - desde

        if self._esc_enviado_em is None:
            if parado >= SEGUNDOS_ATE_O_ESC:
                self._esc_enviado_em = agora
                return "esc"
            return None

        if parado < SEGUNDOS_ATE_O_RELOGIN or self.desistiu():
            return None
        if (self._ultimo_relogin_em is not None
                and agora - self._ultimo_relogin_em < SEGUNDOS_ENTRE_RELOGINS):
            return None
        self._ultimo_relogin_em = agora
        self._relogins += 1
        return "relogar"

    def forcar_novo_aviso(self) -> None:
        """Faz o próximo `avisar` falar, ignorando a cadência. Para TESTE."""
        self._falei_em = 0.0

    def desistiu(self) -> bool:
        """Já relogou o máximo e continua mudo: agora é caso para o humano."""
        return self._relogins >= MAXIMO_DE_RELOGINS


# =========================================================================
# O AVISO E O DESFECHO -- funcoes, e nao metodos do executor
# =========================================================================
#
# Elas moram no `core/` por DUAS razoes, e a segunda e a que manda:
#
# 1. O executor do APP importa SO `blazesbot.core.*`
#    (`tests/test_ecossistemas.py`) -- e um modulo irmao em `bot/app/` seria
#    exatamente o import proibido.
# 2. **Isto e sobre o JOGO, nao sobre o APP.** "O cliente parou de aceitar
#    tecla" acontece igual no BC, e a resposta seria a mesma. O criterio de
#    promocao do projeto e essa pergunta, e ela responde sozinha.
#
# NADA AQUI CONHECE JANELA. O ESC chega como funcao (`apertar_esc`), o
# desfecho de queda tambem (`declarar_queda`), e o log e o de quem chamou --
# ele ja identifica a conta.


# De quanto em quanto tempo o TAB MUDO volta a falar -- 06/09/2026.
#
# Medido em campo: duas contas passaram 96 e 212 minutos apertando TAB a cada 2 s
# sem UMA linha no log. O aviso da tecla morta saía uma vez e nunca mais, e a
# linha "o TAB não trouxe mob vivo" era suprimida justamente quando o TAB parava
# de responder. Da segunda linha em diante, silêncio total.
#
# Um minuto é o intervalo que faz o problema aparecer no log sem afogá-lo: são
# ~30 tentativas de TAB entre duas linhas.
SEGUNDOS_ENTRE_AVISOS = 60.0


def reagir(estado, log, agora: float, apertar_esc,
           declarar_queda=None) -> None:
    """A escada do teclado mudo: ESC uma vez, depois queda.

    AQUI SÓ SE AGE -- quem DECIDE é `TecladoMudo.o_que_fazer`, logo acima.

    O ESC É SEGURO NESTE PONTO e em nenhum outro: chega-se aqui sem alvo (o
    TAB não trouxe nenhum), então a mira que ele larga não existe. Fora daqui,
    ESC em laço cancelaria ação legítima -- por isso quem decide se ele pode
    sair não é quem aperta.
    """
    acao = estado.o_que_fazer(agora)
    if acao is None:
        return

    mudo_desde = estado.mudo_desde() or agora
    parado = agora - mudo_desde

    if acao == "esc":
        log.warning(
            "TECLADO MUDO há %.0fs — nem o TAB troca alvo nem a "
            "tecla de bolsa abre a bolsa. Mandando UM ESC: se houver "
            "chat ou janela do jogo aberta comendo as teclas, é isto que "
            "devolve o controle.", parado)
        apertar_esc()
        return

    # RELOGAR. É a saída cara, e ela existe porque a barata já falhou:
    # 9 h 30 min de conta viva, lendo memória, com mob a três unidades de
    # distância e NADA sendo atacado (07/09/2026).
    log.error(
        "TECLADO MUDO há %.0f min e o ESC não resolveu. O cliente "
        "não recebe mais tecla nenhuma; vou tratar como QUEDA e relogar — "
        "parada a conta não produz nada mesmo.", parado / 60.0)
    if declarar_queda is None:
        log.error(
            "...mas ninguém ligou o desfecho de queda neste executor. A "
            "conta vai continuar muda até alguém olhar.")
        return
    declarar_queda("teclado mudo")


def avisar(estado, log, agora: float, tecla: str, tabs_sem_resposta: int,
           quantos: int, mais_perto: float | None) -> None:
    """Fala do TAB que não responde -- e VOLTA A FALAR, a cada minuto.

    =================================================================
    O SILÊNCIO DE 96 MINUTOS -- medido em 06/09/2026
    =================================================================

    O aviso saía UMA vez por sessão (`_avisou_tecla_morta`) e a linha "o TAB
    não trouxe mob vivo" era suprimida exatamente quando o TAB parava de
    responder. Da segunda tentativa em diante, silêncio: duas contas ficaram
    96 e 212 minutos apertando TAB a cada 2 s sem uma única linha no log, e
    o usuário só descobriu olhando a tela.

    E O AVISO SOZINHO NÃO BASTAVA, porque ele acusava a coisa errada: dizia
    "a tecla não está pegando" quando a causa mais provável é não haver mob
    vivo ao alcance. As duas são indistinguíveis pelo `TARGET_ID` -- só a
    tabela de entidades separa uma da outra, e é ela que entra aqui.
    """
    if (agora - estado._falei_em
            < SEGUNDOS_ENTRE_AVISOS):
        return
    primeiro = estado._falei_em == 0.0
    estado._falei_em = agora
    
    if quantos:
        log.error(
            "%s TAB(s) sem resposta, e HÁ %d mob(s) vivo(s) por perto "
            "(o mais próximo a %.0f). Ou a tecla %r não chega ao jogo, ou "
            "eles estão fora do alcance do TAB. NADA está sendo atacado.",
            tabs_sem_resposta, quantos, mais_perto or 0, tecla)
        return
    log.warning(
        "%s TAB(s) sem resposta e NENHUM mob vivo por perto — o spot "
        "está vazio %s. Sigo tentando; não há o que atacar.",
        tabs_sem_resposta,
        "(ou a leitura da vizinhança não respondeu)" if primeiro else "")
