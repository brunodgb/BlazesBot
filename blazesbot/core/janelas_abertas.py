"""Janela do jogo na frente do clique: detectar e tirar do caminho.

=========================================================================
O DEFEITO QUE ISTO IMPEDE
=========================================================================

Relato do usuário em 26/08/2026, com print: o personagem parado na coordenada
exata da entrada da cave (1395,-635), o Skull Herald já selecionado, o time de
reset já formado -- e o painel "Surroundings" aberto **na frente**, engolindo o
clique. A run inteira travada por uma janela que ninguém fechou.

A causa estava em `ui_service.fechar_surroundings`, que tratava "não consigo
VER o painel" como "o painel não está aberto" e voltava em silêncio achando que
tinha fechado. Mas o buraco maior era não existir NENHUMA conferência antes dos
cliques na cena 3D: o bot clicava e torcia.

E clique engolido não é uma tentativa que falha de graça. O botão de fechar da
janela fica SOBRE a cena, então um clique que erra cai no chão -- e clicar no
chão faz o personagem ANDAR, para longe da coordenada, tornando a tentativa
seguinte pior que esta. É o mecanismo que transforma "estou um pouco fora do
lugar" em "o bot se perdeu andando".

=========================================================================
POR QUE DOIS SINAIS, E O QUE CADA UM RESPONDE
=========================================================================

Eles não são redundantes -- respondem perguntas DIFERENTES, e as duas são
necessárias:

  * o **X de fechar** responde *"onde clico para fechar?"*. É a resposta
    acionável, e é o que torna seguro fechar sem saber QUE janela é: a posição
    do clique não é adivinhada, é localizada por imagem.

  * a **moldura dourada** responde *"tem janela na tela?"*. É a rede: existem
    janelas SEM X (as `Expand Bag`, a caixa de chat), e para elas o X é cego.

A moldura NÃO conta janelas -- o filigrama se repete ao longo da borda, então
uma janela só produz de 2 a 7 casamentos. Por isso aqui nunca se conta nada: o
laço pergunta *"ainda tem janela?"* e fecha UMA por passada, reconferindo. É o
mesmo desenho do `bc/team._fechar_janelas`, e pelo mesmo motivo: fechar uma
janela MUDA a tela, então as posições calculadas antes podem já não valer.

=========================================================================
A MEDIÇÃO (26/08/2026) -- 16 quadros
=========================================================================

11 quadros COM janela (Surroundings, Ranking List, Apprenticeship, Competition,
Item/inventário, Skill, Character, Guild, Friend List, e mais dois dentro da
cave) e 5 SEM janela nenhuma (andando na cave, perto do last boss, porta da
cave, boss fase 1 e fase 2).

    sinal      pior COM janela   pior SEM janela   margem
    X          0.898             0.327             +0.571
    moldura    0.829             0.391             +0.438

O falso positivo é notavelmente ESTÁVEL entre cenas opostas: Stone City ao sol
dá 0.390/0.318 e a cave escura dá 0.391/0.327. Não é um sinal que depende do
cenário -- e isso é o que autoriza um limiar fixo.

As capturas que sustentam estes números foram removidas depois de medidas, a
pedido do usuário. Refazer a medição exige capturas novas.

=========================================================================
EM COR, E NÃO EM CINZA -- porque a medição acima FOI FEITA EM COR
=========================================================================

O caminho padrão do `find_template` converte o quadro para luminância, e a
medição deste módulo não foi feita assim. Casar em cinza com limiares medidos em
cor seria aplicar um número a um espaço que não é o dele -- exatamente o tipo de
número sem medição atrás que este projeto recusa.

E cor não é conveniência de quem mediu, é o modo CERTO para este alvo. O
`vision.load_color` já documenta o motivo: em cinza, dois elementos de mesma
forma e cores diferentes marcam 0.98 um contra o outro. O X de fechar é VERMELHO
sobre placa escura, e a HUD do jogo é cheia de glifos escuros do mesmo tamanho --
é o vermelho que o separa deles.

Por isso os dois sinais usam `find_all_templates(colorido=True)` com
`TemplateLibrary.load_color`, e nunca `find_template`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .vision import find_all_templates

# Templates. Medidos e recortados em 26/08/2026 -- ver o cabeçalho.
TEMPLATE_DO_X = "janela_fechar.png"
TEMPLATE_DA_MOLDURA = "janela_moldura.png"

# Limiar do X. É o 0.80 que o projeto inteiro já usa (`INVITE_THRESHOLD`,
# `ANCHOR_THRESHOLD`), e ele cabe aqui com folga MEDIDA dos dois lados: 0.098
# acima do pior verdadeiro e 0.473 abaixo do pior falso positivo.
LIMIAR_DO_X = 0.80

# Limiar da moldura, e ele NÃO é o 0.80 do projeto -- de propósito.
#
# O pior verdadeiro da moldura foi 0.829, e veio de uma cena ESCURA dentro da
# cave, que é justamente onde este guarda importa. Com 0.80 sobrariam 0.029 de
# folga, apostando que nenhuma janela futura, numa cena ainda mais escura, cai
# abaixo disso -- e a amostra que define esse piso é UMA.
#
# 0.65 fica no MEIO do vão medido (0.391 de falso, 0.829 de verdadeiro): 0.26
# acima do falso e 0.18 abaixo do verdadeiro. Quando o vão é de 0.44, o limiar
# deve ficar no meio dele, não colado numa das bordas.
LIMIAR_DA_MOLDURA = 0.65

# Quantas janelas fechar numa chamada antes de desistir.
#
# Não é "quantas janelas existem" -- é um teto contra laço infinito, para o caso
# de um clique de fechar não surtir efeito. Quatro cobre o pior caso observado
# (inventário + duas bolsas) com folga; mais que isso seria insistir contra uma
# janela que não fecha.
MAXIMO_DE_JANELAS = 4


@dataclass(frozen=True)
class Leitura:
    """O que este quadro diz sobre janelas na frente.

    `tem_janela` é TRI-ESTADO, e a distinção é o ponto todo deste módulo:

        True  -> vi janela
        False -> olhei e não tem
        None  -> NÃO SEI (sem captura, ou sem os templates em disco)

    Foi tratar `None` como `False` que produziu o defeito original: o painel
    ficava aberto e o código seguia achando que a tela estava limpa.
    """

    tem_janela: bool | None
    ponto_de_fechar: tuple[int, int] | None

    @property
    def sei_fechar(self) -> bool:
        return self.ponto_de_fechar is not None


def ler(quadro, templates) -> Leitura:
    """Lê o quadro UMA vez e diz se há janela e onde fechá-la.

    O X é procurado PRIMEIRO, e a ordem é por custo: janela aberta é quase
    sempre uma que o próprio bot abriu, e as que o bot abre têm X. Achando o X,
    a moldura nem roda -- o caso comum paga um casamento, não dois.

    A ordem inversa (moldura como triagem) seria pior justamente por parecer
    natural: a moldura é o sinal de margem MENOR, e usá-la como primeiro filtro
    poria o sinal mais fraco decidindo se o mais forte chega a rodar.
    """
    if quadro is None or getattr(quadro, "ndim", 0) != 3:
        # Quadro precisa vir em COR. Um quadro em cinza aqui não é "tela
        # desconhecida", é carga errada -- e responder `False` a isso seria
        # dizer "está limpo" sem ter olhado.
        return Leitura(None, None)

    alvo_x = templates.load_color(TEMPLATE_DO_X)
    moldura = templates.load_color(TEMPLATE_DA_MOLDURA)
    if alvo_x is None and moldura is None:
        # Sem os dois templates em disco não há como olhar. "Não sei" -- e quem
        # chama não pode transformar isso em "está limpo".
        return Leitura(None, None)

    if alvo_x is not None:
        achados = find_all_templates(
            quadro, alvo_x, threshold=LIMIAR_DO_X, colorido=True)
        if achados:
            # `find_all_templates` devolve do mais forte para o mais fraco.
            return Leitura(True, achados[0])

    if moldura is not None:
        if find_all_templates(quadro, moldura,
                              threshold=LIMIAR_DA_MOLDURA, colorido=True):
            # Janela SEM X: existe (bolsas, chat), e não há clique de fechar
            # seguro para ela. Quem chama decide -- e a regra do projeto é que
            # "não sei fechar" libera o clique em vez de travar a run.
            return Leitura(True, None)
        if alvo_x is not None:
            return Leitura(False, None)     # os dois olharam e não acharam

    return Leitura(None, None)


def pontos_de_fechar(quadro, templates) -> list[tuple[int, int]]:
    """TODOS os X visíveis. Só para diagnóstico -- o laço fecha um por vez."""
    if quadro is None or getattr(quadro, "ndim", 0) != 3:
        return []
    alvo_x = templates.load_color(TEMPLATE_DO_X)
    if alvo_x is None:
        return []
    return find_all_templates(quadro, alvo_x,
                              threshold=LIMIAR_DO_X, colorido=True)


def desobstruir(
    capturar: Callable[[], object],
    templates,
    clicar: Callable[[tuple[int, int]], None],
    esperar: Callable[[float], None],
    log=None,
    passo: float = 0.25,
    teto: int = MAXIMO_DE_JANELAS,
) -> bool | None:
    """Tira janelas da frente e CONFIRMA. Devolve o veredito TRI-ESTADO.

        True  -> a tela está limpa (conferido por imagem)
        False -> ainda tem janela e eu não sei fechá-la
        None  -> não sei (sem captura, ou sem templates)

    RECEBE PEÇAS, NÃO `BotContext` -- mesma decisão de `watchdog.avaliar_saude`.
    É o que permite o ecossistema APP usar este guarda sem passar a depender do
    farm da cave, e é o que mantém `core/` sem importar de `bot/`.

    UMA JANELA POR PASSADA, com recaptura entre elas. Fechar uma janela muda a
    tela: a de baixo pode se reposicionar e as sub-janelas somem junto com a mãe
    (as `Expand Bag` fecham com o inventário). Clicar numa leva de coordenadas
    calculadas de uma vez só significa clicar em posições obsoletas -- e cada
    clique obsoleto cai na cena 3D e MANDA O PERSONAGEM ANDAR, que é exatamente
    o estrago que este guarda existe para impedir.
    """
    for _ in range(teto):
        leitura = ler(capturar(), templates)

        if leitura.tem_janela is None:
            return None                      # não sei: quem chama decide
        if leitura.tem_janela is False:
            return True                      # limpo, e conferido
        if not leitura.sei_fechar:
            # Tem janela e não tem X. Fechar às cegas seria clicar num
            # interruptor sem ver o estado -- o erro que já produziu o
            # pisca-pisca do painel de arredores.
            if log is not None:
                log.warning(
                    "Tem janela na frente e ela não tem botão de fechar "
                    "reconhecível. Não vou clicar às cegas.")
            return False

        if log is not None:
            log.info("Janela na frente do clique; fechando em %s",
                     leitura.ponto_de_fechar)
        clicar(leitura.ponto_de_fechar)
        esperar(passo)

    if log is not None:
        log.warning("Fechei %s janela(s) e ainda tem alguma na frente", teto)
    return False
