"""
Catálogo de nomes de lugar e validação da string lida da memória.

=========================================================================
POR QUE ESTE ARQUIVO EXISTE
=========================================================================

O nome do lugar ("Ghost Din Woods", "Bewitcher Cave", "Secret Cemetery") é a
informação que diz ao bot ONDE ele está, e portanto O QUE faz sentido fazer.
Sem ela o bot executa comandos da localização errada -- abre o painel de
arredores dentro da cave, tenta entrar na cave estando dentro, procura o NPC de
transporte estando em Ghost Din Woods.

O problema real, registrado em produção duas vezes: a leitura passou a devolver
`None` no personagem que estava rodando a BC, e só voltou ao normal depois de
FECHAR E REABRIR o jogo. Fechar o jogo custa horas de fila -- é inaceitável como
solução.

=========================================================================
O QUE FOI DESCOBERTO ANALISANDO A LEITURA
=========================================================================

A leitura antiga era:

    ptr  = resolve(PLAYER_BASE, [0x7F8, 0xF4])      # três derreferências
    text = read_string(ptr, offset=0x44C)            # mais uma
    if re.match(r"^[\\w ']+$", text): return text     # <- AQUI
    return None

Duas falhas graves, e a segunda explica o sintoma:

1. `\\w` NÃO aceita hífen nem ponto. `"Man-eater Tribe"` é uma das áreas da BC
   e é REJEITADA por esse filtro. Qualquer nome com pontuação virava `None`.

2. Quando o filtro rejeita, a função devolve `None` -- e joga fora a string que
   ela ACABOU DE LER. O log dizia "localização = None" tanto quando a memória
   estava ilegível quanto quando ela estava perfeitamente legível e só o filtro
   não gostou do texto. São dois problemas completamente diferentes e o
   diagnóstico não distinguia um do outro.

O log de produção também mostrou `'8tcher Cave'` no lugar de `'Bewitcher Cave'`:
o começo da string se perde às vezes. Ou seja, além de aceitar pontuação, a
validação precisa aceitar nome TRUNCADO -- e é isso que este módulo faz,
casando pela CAUDA contra o catálogo de nomes conhecidos.

=========================================================================
A REGRA QUE SUBSTITUI O FILTRO
=========================================================================

Nunca descartar em silêncio. A resolução é em três níveis, do mais forte ao
mais fraco, e cada nível diz de onde veio a resposta:

  EXATO    -- a string é um nome do catálogo. Confiança total.
  PARCIAL  -- a string é a cauda de um nome do catálogo ('8tcher Cave').
              Confiança total, e o nome devolvido é o COMPLETO.
  FORMATO  -- não está no catálogo, mas tem cara de nome de lugar (Maiúscula
              palavra por palavra -- ver `_PALAVRA_DE_LUGAR`). Aceita e AVISA,
              porque pode ser uma área que ainda não catalogamos.

Só o que não passa em nenhum dos três é tratado como ilegível -- e, mesmo aí, a
string bruta é preservada para o log.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# ---------------------------------------------------------------------------
# Áreas de dentro da Bewitcher Cave
# ---------------------------------------------------------------------------
#
# Vêm dos waypoints medidos no jogo. Saber que estes nomes existem é o que
# permite ao bot responder "estou dentro da cave?" pela string, sem depender de
# coordenada. Ver `bot/mapa_bc.py` para a rota que passa por cada uma.
AREAS_BC: tuple[str, ...] = (
    "Bewitcher Cave",
    "Centipede Zone",
    "Man-eater Tribe",
    "Bloodsucker Zone",
    "Skull Tomb",
    "Secret Altar",
    "Secret Cemetery",
)

# Lugares de FORA da cave que o bot pisa no ciclo normal. Manter esta lista
# curta e específica é de propósito: ela existe para reconhecer o caminho da
# rotina, não para catalogar o jogo inteiro.
LUGARES_DA_ROTA: tuple[str, ...] = (
    "Stone City",
    "Stone City North",
    "Stone City South",
    "Ghost Din Woods",
    "Vast Mountain",
)

# O lugar em que o personagem está quando NÃO está na cave e o X é grande.
#
# Sair da instância devolve o personagem aqui, na coordenada da entrada, e este é
# o único lugar da rotina com X na casa dos milhares. Por isso ele é a resposta
# quando a memória insiste numa área da cave com o X denunciando o contrário --
# ver `bot/localizacao.py`. Fica no catálogo, e não solto nos módulos que usam,
# para não existirem duas grafias do mesmo nome.
LUGAR_FORA_DA_CAVE = "Ghost Din Woods"
assert LUGAR_FORA_DA_CAVE in LUGARES_DA_ROTA


def _todos_os_nomes() -> tuple[str, ...]:
    """Catálogo completo: áreas da BC, caminho da rotina e o mapa-múndi.

    O catálogo do mapa-múndi entra porque o bot também precisa reconhecer
    lugares por onde ele passa sem querer -- se o personagem for arrastado para
    outra região, reconhecer o nome é o que permite voltar.
    """
    from .zones import LOCAL_PARA_ZONA

    nomes = set(AREAS_BC) | set(LUGARES_DA_ROTA) | set(LOCAL_PARA_ZONA)
    return tuple(sorted(nomes, key=len, reverse=True))


# Calculado uma vez: o catálogo não muda em tempo de execução.
NOMES_CONHECIDOS: tuple[str, ...] = _todos_os_nomes()
_POR_MINUSCULA: dict[str, str] = {n.lower(): n for n in NOMES_CONHECIDOS}

# Menor cauda que ainda identifica um lugar com segurança. Abaixo disso,
# 'Cave' casaria com meia dúzia de nomes diferentes e o bot escolheria um ao
# acaso -- pior que admitir que não sabe.
MINIMO_CAUDA = 5

# Forma de um nome de lugar aceitável quando ele NÃO está no catálogo.
#
# Aceita hífen, apóstrofo e ponto de propósito: 'Man-eater Tribe', "Zhao's
# Palace" e "Loo's Village" são nomes reais do jogo, e o filtro antigo (que
# usava apenas `\\w` e espaço) rejeitava os dois primeiros.
_FORMATO_DE_NOME = re.compile(r"^[A-Za-z][A-Za-z0-9 '\-\.]{2,48}$")

# Proporção mínima de letras. Lixo de memória tende a vir com muitos dígitos e
# símbolos; nome de lugar é quase todo letra e espaço.
_MINIMO_DE_LETRAS = 0.60

# A CARA DE NOME, palavra por palavra -- MEDIDO em 26/09/2026. Os dois filtros
# acima deixavam passar 35 lixos distintos de 42.770 leituras do log de dev
# (`D5vl` x216, `UUUU...` x188, `hCKD` x181, `PV8`, `CPC`, `HxH`, pedaços de
# mensagem como `ase try later again.`). Todo nome de verdade -- os 116 do
# catálogo e os que o log mostrou fora dele (`Happiness Hall Main Hall`...) --
# é Maiúscula-minúsculas palavra por palavra, com conectivo minúsculo no meio
# ("East of Simen Mountain"); nenhum dos 35 lixos é.
_PALAVRA_DE_LUGAR = re.compile(r"^[A-Z][a-z'\-\.]*$")
_CONECTIVO = re.compile(r"^[a-z]{2,}$")
_PALAVRA_INTEIRA = re.compile(r"^[A-Z][a-z]{2,}")


class Resolucao:
    """Como um nome de lugar foi reconhecido. Vira texto no log."""

    EXATO = "exato"
    PARCIAL = "parcial"
    FORMATO = "formato"
    RECUSADO = "recusado"


def limpar(bruto: str | None) -> str:
    """Tira ruído das bordas da string lida da memória.

    Remove caracteres de controle e espaços, e corta no primeiro caractere que
    não pode fazer parte de um nome. NÃO remove o que vem antes da primeira
    letra: esse pedaço é justamente a pista de que a string veio truncada, e o
    casamento por cauda cuida disso.
    """
    if not bruto:
        return ""
    texto = "".join(c for c in bruto if c == " " or c.isprintable())
    return texto.strip().strip("\x00").strip()


def _proporcao_de_letras(texto: str) -> float:
    uteis = [c for c in texto if not c.isspace()]
    if not uteis:
        return 0.0
    return sum(c.isalpha() for c in uteis) / len(uteis)


def _tem_cara_de_nome(texto: str) -> bool:
    """Abre com palavra Maiúscula, segue com Maiúsculas ou conectivos, e tem ao
    menos uma palavra de três letras. Ver `_PALAVRA_DE_LUGAR`."""
    palavras = texto.split()
    if not palavras or not _PALAVRA_DE_LUGAR.match(palavras[0]):
        return False
    if not all(_PALAVRA_DE_LUGAR.match(p) or _CONECTIVO.match(p)
               for p in palavras[1:]):
        return False
    return any(_PALAVRA_INTEIRA.match(p) for p in palavras)


def casar_por_cauda(texto: str) -> str | None:
    """Nome completo de um lugar cuja string veio com o começo corrompido.

    `'8tcher Cave'` -> `'Bewitcher Cave'`.

    Testa TODOS os sufixos, do mais longo para o mais curto, e aceita o primeiro
    que identifique um único lugar do catálogo. Sufixo mais longo primeiro porque
    é o mais específico -- quanto mais curta a cauda, mais nomes ela serve.

    POR QUE NÃO BASTA CORTAR ANTES DA PRIMEIRA LETRA: era o que esta função fazia,
    com `^[^A-Za-z]*`, e funcionava para `'8tcher Cave'`. Mas a corrupção real
    registrada em produção foi `'\\z5tcher Cave'` -- e ali existe uma LETRA (o `z`)
    no meio do lixo. O corte parava nela, a cauda ficava `'z5tcher cave'`, nenhum
    nome termina assim, e o nome era perdido justamente no caso que motivou a
    função existir.

    Ambíguo continua sendo o mesmo que desconhecido: escolher um dos empatados
    levaria o bot a agir como se estivesse em outro lugar.
    """
    limpo = texto.strip().lower()
    for inicio in range(len(limpo)):
        cauda = limpo[inicio:].strip()
        # As caudas só encurtam: abaixo do mínimo, as seguintes também estarão.
        # 'Cave' sozinho serviria a meia dúzia de lugares diferentes.
        if len(cauda) < MINIMO_CAUDA:
            break
        achados = {n for n in NOMES_CONHECIDOS if n.lower().endswith(cauda)}
        if len(achados) == 1:
            return achados.pop()
    return None


def resolver(bruto: str | None) -> tuple[str | None, str]:
    """Transforma a string lida da memória em (nome do lugar, como reconheci).

    Devolve `(None, RECUSADO)` só quando a string não tem nada de nome de lugar.
    Em qualquer outro caso devolve o melhor nome disponível -- e o segundo
    elemento diz o quanto confiar nele.
    """
    texto = limpar(bruto)
    if not texto:
        return None, Resolucao.RECUSADO

    exato = _POR_MINUSCULA.get(texto.lower())
    if exato:
        return exato, Resolucao.EXATO

    parcial = casar_por_cauda(texto)
    if parcial:
        return parcial, Resolucao.PARCIAL

    if (_FORMATO_DE_NOME.match(texto)
            and _proporcao_de_letras(texto) >= _MINIMO_DE_LETRAS
            and _tem_cara_de_nome(texto)):
        return texto, Resolucao.FORMATO

    return None, Resolucao.RECUSADO


def melhor_candidato(
    candidatos: Iterable[tuple[str, str | None]],
) -> tuple[str | None, str, str]:
    """Escolhe a melhor leitura entre várias tentativas.

    Recebe pares `(origem, string bruta)` -- a mesma informação lida por
    caminhos diferentes da memória -- e devolve
    `(nome, como reconheci, de qual origem)`.

    A ordem de preferência é pela QUALIDADE do reconhecimento, não pela ordem
    das tentativas: uma leitura secundária que casa exatamente com o catálogo
    vale mais que a leitura principal que só passou pelo filtro de formato.
    """
    ranking = {Resolucao.EXATO: 0, Resolucao.PARCIAL: 1, Resolucao.FORMATO: 2}
    melhor: tuple[str | None, str, str] = (None, Resolucao.RECUSADO, "")
    melhor_nota = 99

    for origem, bruto in candidatos:
        nome, como = resolver(bruto)
        if nome is None:
            continue
        nota = ranking[como]
        if nota < melhor_nota:
            melhor_nota = nota
            melhor = (nome, como, origem)
            if nota == 0:
                break
    return melhor


def e_dentro_da_cave(nome: str | None) -> bool:
    """O nome pertence ao interior da Bewitcher Cave?

    Compara com o catálogo de áreas em vez de procurar o pedaço "cave" no
    texto: as áreas internas se chamam "Centipede Zone", "Secret Altar",
    "Man-eater Tribe" -- nenhuma delas tem "cave" no nome, e procurar por
    pedaço deixaria o bot achar que saiu da instância no meio do caminho.
    """
    if not nome:
        return False
    return nome in AREAS_BC
