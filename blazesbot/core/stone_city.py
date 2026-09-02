"""Stone City e o NPC de transporte: o que as DUAS caves usam da cidade.

=========================================================================
POR QUE ISTO SUBIU PARA O `core/`
=========================================================================

Nasceu dentro de `bot/bc/mapa_bc.py`, onde a Bewitcher Cave era a única cave que
existia. Com a chegada da HH ficou evidente o que sempre foi verdade: **o
Transport Fay e Stone City não são da Bewitcher Cave.** A cidade é o ponto de
partida das duas, e é o MESMO NPC no MESMO ponto que leva às duas -- só o destino
escolhido no diálogo difere:

    Bewitcher Cave   Fay -> "Ghost Din Woods"                (Need 7, nível 48)
    HH               Fay -> "West Suburb of Stone City"       (Need 5, nível 20)

Deixar isso em `mapa_bc` obrigaria `bot/hh/entrada.py` a importar de `bc/`, o que
`tests/test_ecossistemas.py` reprova -- e com razão: seria a HH dependendo da
Bewitcher Cave para saber onde fica um NPC de cidade.

**DEPENDÊNCIA CRUZADA: mexer aqui mexe nas duas caves.** `mapa_bc` reexporta
todos estes nomes, então o código da BC continua chamando pelos nomes de sempre.

Mora no `core/` porque é dado e função pura sobre coordenadas: não conhece
`BotContext` e não precisa.

O QUE NÃO SUBIU, e por quê: o **Rich Man**, o vendedor de Stone City. Ele é o
vendedor da BC; a HH vende no `Roaming Apothecary`, do lado de fora da cave dela.
Vendedor é escolha do ecossistema, não da cidade.
"""
from __future__ import annotations

Ponto = tuple[int, int]

# ---------------------------------------------------------------------------
# O NPC de transporte
# ---------------------------------------------------------------------------

# Par (texto de busca no painel de arredores, nome para confirmar a leitura).
NPC_DE_TRANSPORTE = ("Fay", "Transport Fay")

# Onde o Transport Fay fica, em Stone City. Medido no jogo.
POSICAO_DA_FAY: Ponto = (178, -518)

# Folga aceita para considerar que já se está no ponto de falar com ela.
#
# APERTADA DE PROPÓSITO. O painel de arredores caminha até PERTO -- ele aceita
# folga por construção --, e clicar de onde ele largar foi o defeito medido em
# 25/08/2026: a 2 passos de distância o ponto genérico de NPC caía no White Eagle
# que estava no caminho, o diálogo não abria, e a rotina concluía "não estou em
# Stone City" e gastava o item de retorno.
PRECISAO_NO_PONTO_DA_FAY = 1.5

# Quantas vezes tentar encostar no ponto exato antes de desistir da viagem.
TENTATIVAS_DE_ENCOSTAR_NA_FAY = 6
SEGUNDOS_POR_TENTATIVA_NA_FAY = 1.8


# ---------------------------------------------------------------------------
# Reconhecer a cidade
# ---------------------------------------------------------------------------

Y_DE_STONE_CITY = -490

NOME_DE_STONE_CITY = "Stone City"

# O X MÁXIMO QUE PODE EXISTIR NUMA INSTÂNCIA.
#
# Regra dada de fora e ela vale por si: acima de 500 em X não existe nada dentro
# de cave. Serve aqui para separar Stone City de Ghost Din Woods, que fica em
# (1395,-635) -- o Y dele também passa pelo corte da cidade, e quem separa os
# dois é o X.
X_MAXIMO_DENTRO_DA_CAVE = 500


def nome_e_stone_city(local: str | None) -> bool:
    """O jogo está DIZENDO que o personagem está em Stone City?

    Sinal COMPLEMENTAR ao da coordenada, e não substituto -- ver
    `esta_em_stone_city`.
    """
    return bool(local) and NOME_DE_STONE_CITY.lower() in str(local).lower()


def posicao_esta_em_stone_city(pos: Ponto | None) -> bool:
    """A coordenada AFIRMA que o personagem está em Stone City?

    DOIS limites, e o segundo não é redundante: Ghost Din Woods fica em
    (1395,-635), e o Y dele também passa por `Y_DE_STONE_CITY`. Quem separa os
    dois é o X.

    Confere contra os pontos medidos:

        vendedor  (158,-494)  -> True
        Fay       (178,-518)  -> True
        boss      ( 80,-406)  -> False   (y acima do corte)
        saída     ( 81,-398)  -> False
        Ghost Din (1395,-635) -> False   (x além do limite)

    Nunca responde True sem posição: "não sei" não é "está".
    """
    if pos is None:
        return False
    return pos[1] <= Y_DE_STONE_CITY and pos[0] <= X_MAXIMO_DENTRO_DA_CAVE


def esta_em_stone_city(pos: Ponto | None, local: str | None = None) -> bool:
    """Está em Stone City? Vale a COORDENADA **ou** o NOME.

    =======================================================================
    POR QUE OS DOIS, quando o resto do projeto usa só a coordenada
    =======================================================================

    A caixa de coordenada é, por construção, um LIMITE INFERIOR: ela foi
    derivada de dois pontos medidos (o vendedor e a Fay), e Stone City é uma
    CIDADE -- tem muito mais chão que isso. Medido no log de 14/08/2026, duas
    partidas com 19 segundos de diferença:

        (205,-498) -> reconhecida, vendeu antes de sair
        (237,-484) -> NÃO reconhecida, foi direto para a Fay com a bolsa cheia

    As duas são Stone City; o jogo dizia isso nas duas. A segunda ficava 6
    unidades acima do corte de `y <= -490`.

    O NOME cobre o resto da cidade. A falha conhecida dele é FICAR PRESO num
    nome antigo -- e o caso medido é ficar preso numa área da CAVE estando fora
    dela, não o contrário. Um "Stone City" lido é sinal positivo confiável.

    E o custo de errar é assimétrico, o que autoriza ser permissivo aqui:

      * deixar de reconhecer  -> sai para a cave com a bolsa cheia, que é o que
                                 trava o bot (o defeito medido acima);
      * reconhecer por engano -> a viagem até o vendedor procura o NPC pelo
                                 painel de arredores, não acha, devolve False,
                                 e a rotina segue para o farm com um aviso.
    """
    return posicao_esta_em_stone_city(pos) or nome_e_stone_city(local)
