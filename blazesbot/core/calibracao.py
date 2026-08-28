"""Calibração de ponteiros: a TELA é o gabarito, a memória é a aluna.

=========================================================================
O PEDIDO, E O PROBLEMA QUE ELE RESOLVE
=========================================================================

Pedido do usuário em 19/08/2026:

    "O ideal era fazer funcionar os ponteiros de memória; por isso era bom criar
    uma forma dentro do bot dele ficar lendo as memórias todas as runs, quando
    chega no waypoint dos Gun Witch e no waypoint do Blaze Skull Marshal, pois
    assim a cada run feita vai refinando cada vez mais os ponteiros até ficar
    perfeito. (...) Assim, mesmo sem eu testar visualmente, os logs vão nos
    dizendo o caminho."

E a regra de ouro dele, na mesma conversa: **"a memória não decide nada
atualmente, mas testar ela até ela acertar; quando ela gabaritar como a tela, nós
teremos achado os pontos certos."**

Isso inverte um arranjo que já custou caro. Até aqui a memória e a tela eram
TESTEMUNHAS DO MESMO JÚRI, e cada modo (`"memoria"`, `"tela"`, `"imagem"`)
elegia uma e calava as outras -- com o resultado medido de 69 leituras sem
veredito e 38 s batendo num cadáver. Agora a tela é o GABARITO e a memória é a
ALUNA: ela é lida, corrigida e pontuada, e não vota em nada.

=========================================================================
O QUE ESTE MÓDULO É, E O QUE ELE NUNCA FAZ
=========================================================================

É um PLACAR. Recebe amostras (`candidato X leu Y, o gabarito era Z`), acumula
contadores e grava. Não lê memória, não captura tela, não decide nada -- quem
sabe ler cada ponteiro é quem chama, e é assim que este módulo fica em `core/`
sem conhecer ecossistema nenhum (a regra permanente do `CLAUDE.md`).

**NUNCA:** escreve em memória, aperta tecla, clica, ou levanta exceção para quem
chama. Falha de disco aqui não pode custar uma run.

=========================================================================
POR QUE "RUNS DISTINTAS" ESTÁ NO CRITÉRIO
=========================================================================

Um candidato que acerta 50 vezes na MESMA sessão pode estar certo -- ou pode ter
caído num endereço que, naquele processo, por acaso continha o valor certo. O
episódio do `+0x60` (`core/rebase.py`) é a prova de que endereço muda entre
versões do cliente, e a struct muda entre sessões.

Então `gabaritou` exige acerto em várias RUNS, não só várias amostras.

=========================================================================
E POR QUE "AMOSTRAS DISCRIMINANTES"
=========================================================================

No instante em que se chega ao waypoint, todo mundo está com a vida cheia. Um
candidato que leia qualquer coisa perto de 100 "acerta" ali sem provar nada -- e
o log de 19/08/2026 mostra exatamente isso: `hp_memoria=100` constante enquanto o
personagem batia.

A amostra que separa ponteiro certo de ponteiro sortudo é a do MEIO DA LUTA, com
a vida caindo. `discriminante=True` marca essas, e `gabaritou` exige um mínimo
delas.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import logmodo

# ===========================================================================
# INTERRUPTOR
# ===========================================================================
#
# `False` = nada é amostrado, nada é gravado, e `registrar` devolve na hora.
#
# O custo de cada amostra é microssegundos (leitura de ponteiro) mais o que o
# chamador já ia pagar de tela. Mas isto atravessa o caminho quente do combate,
# então tem interruptor como tudo o mais que atravessa caminho quente.
ATIVADA = True

# Onde o placar mora. Pequeno, permanente, NUNCA rotaciona -- é o arquivo que o
# usuário e eu vamos abrir para decidir o que promover.
CAMINHO_DO_PLACAR = Path("data") / "calibracao.json"

# ===========================================================================
# OS CRITÉRIOS
# ===========================================================================
#
# Tolerância do HP em pontos percentuais. A barra é PIXEL CONTADO e a memória é
# número inteiro: divergir 1 ou 2 pontos por arredondamento é o comportamento
# normal, e reprovar por isso reprovaria o ponteiro CERTO.
TOLERANCIA_DO_HP = 3.0

# Faixa em que uma amostra de HP prova algo. Fora dela (vida cheia ou vazia)
# qualquer leitura próxima do extremo "acerta" por acidente.
FAIXA_DISCRIMINANTE = (5.0, 95.0)

# Para um candidato ser declarado `gabaritou`.
AMOSTRAS_PARA_GABARITAR = 50
DISCRIMINANTES_PARA_GABARITAR = 20
RUNS_PARA_GABARITAR = 10

# Para um candidato ser declarado `reprovado` e PARAR de ser amostrado. Não é
# julgamento final -- é economia: continuar medindo quem já errou uma em cada
# cinco é gastar CPU no caminho quente para reconfirmar o óbvio.
AMOSTRAS_PARA_REPROVAR = 100
TAXA_DE_ERRO_PARA_REPROVAR = 0.20

# ===========================================================================
# TOLERÂNCIA DE ERRO POR PROVA -- e o número saiu de medição
# ===========================================================================
#
# `gabaritou` exige ZERO erro, e isso é certo para prova cujo GABARITO é exato:
# a barra de vida desenhada, a caixa na tela, o botão na tela. Errar ali é o
# ponteiro errando.
#
# `flag_combate` é diferente: o gabarito dela é **por CONSEQUÊNCIA** ("barra
# acima de 20% ⇒ há luta"), e consequência tem ruído próprio -- a barra pode
# estar desenhada no instante em que o combate acabou de terminar.
#
# Medido em 20/08/2026, 12 runs: **8 erros em 6.452 amostras = 0,12%**, e o
# último erro é exatamente essa assinatura (`leu=False esperado=True`). O
# ponteiro `0x854` é o que o bot usa para encerrar as fases e ele funciona; exigir
# zero dele é exigir perfeição do ORÁCULO, não do ponteiro.
#
# 1% é oito vezes o ruído observado -- folga para não reprovar por acaso, e ainda
# duas ordens de grandeza abaixo do que qualquer candidato ruim produz (os
# reprovados desta noite estão em 40%, 61%, 96% e 100%).
TOLERANCIA_DE_ERRO_POR_PROVA = {"flag_combate": 0.01}

# ===========================================================================
# `sem_resposta`: QUEM NUNCA RESPONDE TAMBÉM TEM DE SAIR DE CENA
# ===========================================================================
#
# Defeito medido em 20/08/2026, três runs depois de a varredura entrar no código:
#
#     VARREDURA  0 eventos no log
#
# E o placar explicava. Dos quatro candidatos do alvo, `0x808` e `0x80c` estavam
# `reprovado`, mas **`0x868` e `0x86c` nem apareciam**: a validação de entidade os
# rejeita, então `hp_lido` sai `None`, o julgamento sai `acertou=None`, e amostra
# assim -- corretamente -- não conta.
#
# Só que `_lista_fechada_esgotou` pergunta se TODOS estão reprovados. Candidato
# sem registro nenhum não está reprovado, então a lista nunca "esgotava" e a
# varredura nunca começava. **Um candidato que nunca responde bloqueava a
# escalada para sempre**, e justamente para o ponteiro que mais precisa dela.
#
# A correção é dar um fim para o silêncio. Trinta tentativas sem leitura é
# generoso: um campo que aponta para entidade válida responde na PRIMEIRA -- e
# quem não respondeu trinta vezes não vai responder na trigésima primeira.
#
# `sem_resposta` é diferente de `reprovado` de propósito: reprovado ERROU, este
# nem chegou a opinar. O placar mostra os dois, e a diferença é o que diz "o
# offset não existe nesta struct" contra "existe e aponta para outra coisa".
TENTATIVAS_SEM_LEITURA_PARA_DESISTIR = 30

# De quantas em quantas amostras o placar vai para o disco.
#
# Não é a cada amostra: com cinco contas amostrando no meio da luta isso seria
# uma reescrita de arquivo por leitura de combate. Não é só no fim da run
# tampouco -- uma queda perderia a sessão inteira de dados, e o objetivo é
# acumular ao longo de muitas noites.
AMOSTRAS_ENTRE_GRAVACOES = 40

# ===========================================================================
# Estado de MÓDULO, com lock -- cinco contas no mesmo processo
# ===========================================================================
#
# Mesmo desenho do `petbug` e do quadro de convites do `bot/mural.py`, e pelo mesmo
# motivo: os supervisores são threads do MESMO processo, então o placar é um só e
# precisa de lock. Duas contas amostrando o mesmo candidato somam evidência em vez
# de brigar por ela.
_LOCK = threading.Lock()
_PLACAR: dict[str, dict[str, Any]] = {}
_CARREGADO = False
_DESDE_A_ULTIMA_GRAVACAO = 0


@dataclass
class Veredito:
    """O que o placar diz sobre um candidato AGORA."""

    prova: str
    candidato: str
    amostras: int = 0
    acertos: int = 0
    discriminantes_certas: int = 0
    runs: int = 0
    situacao: str = "aprendendo"   # aprendendo|gabaritou|reprovado|sem_resposta
    # Tentativas que não deram leitura nenhuma. Não são amostras nem erros --
    # ver `TENTATIVAS_SEM_LEITURA_PARA_DESISTIR`.
    sem_leitura: int = 0

    @property
    def taxa_de_erro(self) -> float:
        return 0.0 if not self.amostras else 1.0 - self.acertos / self.amostras


@dataclass
class Amostra:
    """Uma comparação: o que o candidato leu contra o que a tela mostrava.

    `acertou=None` significa "não deu para julgar" -- sem gabarito ou sem
    leitura. Amostra assim NÃO conta, nem a favor nem contra: é a mesma regra que
    vale para o veredito de morte, onde "não sei" nunca foi resposta.
    """

    prova: str
    candidato: str
    acertou: bool | None
    lido: Any = None
    esperado: Any = None
    discriminante: bool = False
    conta: str = ""
    id_run: str = ""
    detalhe: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def quem_esta_medindo() -> tuple[str, str]:
    """`(conta, id_run)` da thread atual. UM lugar só, e é correção de defeito.

    ==================================================================
    O `runs=0` DA PRIMEIRA NOITE
    ==================================================================

    A primeira versão pedia `getattr(ctx, "id_run", "")` ao `BotContext`, que
    **não tem esse campo**. O `getattr` com default devolveu `""` calado, e o
    placar da noite inteira saiu assim:

        flag_combate  0x854  aprendendo  324 amostras  100% acerto  runs=0

    324 amostras perfeitas que **não podiam gabaritar**, porque o critério exige
    10 runs distintas e o contador estava preso em zero. É a lição do
    `CLAUDE.md` sobre `getattr` com default: ele não conserta a dependência, ele
    esconde.

    A identificação da run mora no `logmodo`, num `threading.local` que o
    supervisor marca no começo de cada run -- e cada conta roda na própria
    thread, então ler daqui devolve a run DAQUELA conta. É a mesma fonte que o
    `LogJsonHandler` usa para enriquecer o log, o que garante que o placar e o
    log falem da mesma run.
    """
    try:
        ctx = logmodo.contexto_atual()
        return str(ctx.get("conta") or ""), str(ctx.get("id_run") or "")
    except Exception:
        return "", ""


def _veredito_de(linha: dict[str, Any]) -> Veredito:
    """Converte a linha do placar no veredito. Num lugar só, porque três
    caminhos devolvem veredito e três cópias divergiriam."""
    return Veredito(
        prova=linha["prova"], candidato=linha["candidato"],
        amostras=linha["amostras"], acertos=linha["acertos"],
        discriminantes_certas=linha["discriminantes_certas"],
        runs=len(linha["runs"]), situacao=linha["situacao"],
        sem_leitura=int(linha.get("sem_leitura", 0)))


def _chave(prova: str, candidato: str) -> str:
    return f"{prova}|{candidato}"


def _carregar_se_preciso() -> None:
    """Lê o placar do disco na primeira vez. Falha vira placar vazio."""
    global _CARREGADO
    if _CARREGADO:
        return
    _CARREGADO = True
    try:
        if CAMINHO_DO_PLACAR.is_file():
            bruto = json.loads(CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))
            if isinstance(bruto, dict):
                _PLACAR.update(bruto.get("candidatos", {}))
    except Exception:
        pass


def _mesclar_do_disco() -> None:
    """Traz do arquivo o que este processo não viu. Chamado sob `_LOCK`.

    Regra: para cada candidato, fica quem tem MAIS amostras. Contador de amostra
    só cresce, então "mais" é sempre "mais informado" -- e a mescla é monótona,
    sem precisar de relógio nem de versão.
    """
    try:
        if not CAMINHO_DO_PLACAR.is_file():
            return
        bruto = json.loads(CAMINHO_DO_PLACAR.read_text(encoding="utf-8"))
        do_disco = bruto.get("candidatos", {}) if isinstance(bruto, dict) else {}
    except Exception:
        return
    for chave, linha in do_disco.items():
        minha = _PLACAR.get(chave)
        if minha is None or int(linha.get("amostras", 0)) > int(
                minha.get("amostras", 0)):
            _PLACAR[chave] = linha


def _entrada(prova: str, candidato: str) -> dict[str, Any]:
    chave = _chave(prova, candidato)
    linha = _PLACAR.get(chave)
    if linha is None:
        linha = {
            "prova": prova,
            "candidato": candidato,
            "amostras": 0,
            "acertos": 0,
            "discriminantes": 0,
            "discriminantes_certas": 0,
            "runs": [],
            "situacao": "aprendendo",
            "sem_leitura": 0,
            "primeira_vez": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ultima_vez": "",
            "ultimo_erro": "",
        }
        _PLACAR[chave] = linha
    return linha


# As duas formas de um candidato sair de cena, e elas dizem coisas diferentes:
# `reprovado` ERROU (o offset existe e aponta para outra coisa); `sem_resposta`
# nem chegou a opinar (o offset não existe nesta struct). Ver
# `TENTATIVAS_SEM_LEITURA_PARA_DESISTIR`.
ENCERRADAS = ("reprovado", "sem_resposta")


def deve_amostrar(prova: str, candidato: str) -> bool:
    """`False` para candidato ENCERRADO -- é a economia do caminho quente.

    Encerrado é `reprovado` (errou demais) ou `sem_resposta` (nunca conseguiu ser
    lido). Quem chama consulta isto ANTES de pagar a leitura, e é o que mantém o
    custo caindo conforme a calibração converge.
    """
    if not ATIVADA:
        return False
    with _LOCK:
        _carregar_se_preciso()
        linha = _PLACAR.get(_chave(prova, candidato))
        return linha is None or linha["situacao"] not in ENCERRADAS


def situacao(prova: str, candidato: str) -> str:
    """`aprendendo` | `gabaritou` | `reprovado` | `sem_resposta` | `sem_registro`.

    Existe para o CÓDIGO poder perguntar ao placar, e não só o relatório. É a
    diferença entre "uma pessoa lê o placar e troca um interruptor" e "o bot
    consulta a prova antes de confiar num ponteiro".

    `sem_registro` é diferente de `aprendendo`: nunca houve amostra nenhuma. Quem
    decide credencial precisa dessa distinção -- prova que não existe não é prova
    que está aprendendo.
    """
    with _LOCK:
        _carregar_se_preciso()
        linha = _PLACAR.get(_chave(prova, candidato))
        return "sem_registro" if linha is None else str(linha["situacao"])


def gabaritou(prova: str, candidato: str) -> bool:
    """O candidato já GABARITOU nesta prova?

    A pergunta que autoriza um ponteiro a decidir alguma coisa. Ver
    `_classificar` para o critério (zero erro, 50 amostras, 20 discriminantes,
    10 runs distintas) e `AMOSTRAS_PARA_GABARITAR`.
    """
    return situacao(prova, candidato) == "gabaritou"


def registrar(amostra: Amostra) -> Veredito | None:
    """Contabiliza uma amostra. Devolve o veredito do candidato, ou `None`.

    NUNCA LEVANTA. Este método é chamado do meio da luta; um erro de disco aqui
    não pode ser o motivo de uma run perdida.
    """
    if not ATIVADA:
        return None
    try:
        if amostra.acertou is None:
            # O SILÊNCIO É CONTABILIZADO, e não descartado.
            #
            # Descartar era o defeito: `0x868` e `0x86c` nunca produziam leitura,
            # nunca entravam no placar, e por isso nunca eram encerrados -- o que
            # travava `_lista_fechada_esgotou` e impedia a varredura de começar.
            # "Não sei" continua não contando como amostra nem como erro; o que
            # ele passa a fazer é ser CONTADO, para o silêncio ter um fim.
            return _contar_silencio(amostra)
        return _registrar(amostra)
    except Exception:
        return None


def _contar_silencio(amostra: Amostra) -> Veredito | None:
    """Uma tentativa que não deu leitura. Não conta como amostra nem como erro."""
    with _LOCK:
        _carregar_se_preciso()
        linha = _entrada(amostra.prova, amostra.candidato)
        linha["sem_leitura"] = int(linha.get("sem_leitura", 0)) + 1
        linha["ultima_vez"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if (linha["amostras"] == 0
                and linha["sem_leitura"] >= TENTATIVAS_SEM_LEITURA_PARA_DESISTIR):
            # SÓ com zero amostras: um candidato que já respondeu antes e ficou
            # mudo agora não é "offset inexistente" -- é leitura que falhou, e
            # aposentá-lo por isso perderia um candidato bom por causa de um
            # trecho ruim da run.
            linha["situacao"] = "sem_resposta"
        return _veredito_de(linha)


def _registrar(amostra: Amostra) -> Veredito:
    global _DESDE_A_ULTIMA_GRAVACAO
    with _LOCK:
        _carregar_se_preciso()
        linha = _entrada(amostra.prova, amostra.candidato)
        linha["amostras"] += 1
        linha["ultima_vez"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if amostra.discriminante:
            linha["discriminantes"] += 1
        if amostra.acertou:
            linha["acertos"] += 1
            if amostra.discriminante:
                linha["discriminantes_certas"] += 1
        else:
            linha["ultimo_erro"] = (
                f"{amostra.ultima_vez_texto()} leu={amostra.lido!r} "
                f"esperado={amostra.esperado!r} {amostra.detalhe}".strip())

        # RUNS DISTINTAS, e é uma LISTA com teto e não um contador: contador
        # somaria a mesma run duas vezes se a amostra vier de dois pontos dela.
        if amostra.id_run and amostra.id_run not in linha["runs"]:
            linha["runs"].append(amostra.id_run)
            del linha["runs"][:-RUNS_PARA_GABARITAR * 3]

        _classificar(linha)
        _DESDE_A_ULTIMA_GRAVACAO += 1
        precisa_gravar = _DESDE_A_ULTIMA_GRAVACAO >= AMOSTRAS_ENTRE_GRAVACOES
        veredito = _veredito_de(linha)

    if precisa_gravar:
        salvar()
    return veredito


def _classificar(linha: dict[str, Any]) -> None:
    """Decide `aprendendo` / `gabaritou` / `reprovado`.

    GABARITAR EXIGE ZERO ERRO. Não é rigor por gosto: o que se vai fazer com um
    ponteiro promovido é DECIDIR MORTE, e morte gasta TAB. Um candidato que erra
    uma em cinquenta erraria uma vez por noite -- e a run em que ele errar é
    indistinguível, no log, de uma run normal.
    """
    amostras = linha["amostras"]
    acertos = linha["acertos"]
    erros = amostras - acertos

    tolerancia = TOLERANCIA_DE_ERRO_POR_PROVA.get(linha["prova"], 0.0)
    if (erros <= amostras * tolerancia
            and amostras >= AMOSTRAS_PARA_GABARITAR
            and linha["discriminantes_certas"] >= DISCRIMINANTES_PARA_GABARITAR
            and len(linha["runs"]) >= RUNS_PARA_GABARITAR):
        linha["situacao"] = "gabaritou"
        return

    if (amostras >= AMOSTRAS_PARA_REPROVAR
            and erros / amostras >= TAXA_DE_ERRO_PARA_REPROVAR):
        linha["situacao"] = "reprovado"
        return

    # QUEM ERROU DEIXA DE SER `gabaritou`. A promoção não é permanente: um
    # candidato que passou e depois erra volta a aprender, porque o cliente pode
    # ter mudado (é o cenário do `+0x60`) e um rótulo velho mentiria.
    linha["situacao"] = "aprendendo"


def salvar(mesclar: bool = True) -> bool:
    """Grava o placar. `False` se não deu -- e não deu nunca é fatal."""
    global _DESDE_A_ULTIMA_GRAVACAO
    if not ATIVADA:
        return False
    try:
        with _LOCK:
            dados = {
                "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
                "criterios": {
                    "tolerancia_do_hp": TOLERANCIA_DO_HP,
                    "amostras_para_gabaritar": AMOSTRAS_PARA_GABARITAR,
                    "discriminantes_para_gabaritar":
                        DISCRIMINANTES_PARA_GABARITAR,
                    "runs_para_gabaritar": RUNS_PARA_GABARITAR,
                },
                "candidatos": _PLACAR,
            }
            # ==========================================================
            # MESCLA COM O DISCO ANTES DE ESCREVER
            # ==========================================================
            #
            # Defeito medido em 20/08/2026: eu reabri `alvo_hp` num processo
            # separado, e o BOT -- que estava rodando com as entradas velhas em
            # memória -- sobrescreveu a reabertura no flush seguinte. Perda de
            # atualização clássica: os dois escrevem o arquivo INTEIRO, e o
            # último a escrever vence com a cópia dele.
            #
            # A mescla é por MAIS AMOSTRAS, e isso funciona porque contador de
            # amostra só CRESCE: quem tem mais viu mais, e é a versão mais
            # informada. Duas contas do mesmo processo não brigam (compartilham
            # `_PLACAR` sob lock); o que isto protege é processo contra processo.
            #
            # CONSEQUÊNCIA que precisa ficar dita: `reabrir` põe a contagem em
            # ZERO, e zero PERDE a mescla. **Reabrir exige o bot parado** -- ver
            # o aviso em `reabrir`.
            #
            # `mesclar=False` é para `reabrir`: lá o objetivo é APAGAR, e a
            # mescla por "mais amostras" ressuscitaria exatamente o que se quer
            # apagar. Um teste pegou isto na primeira versão.
            if mesclar:
                _mesclar_do_disco()
            CAMINHO_DO_PLACAR.parent.mkdir(parents=True, exist_ok=True)
            # ESCRITA ATÔMICA: arquivo temporário e `replace`. Cinco contas e uma
            # queda no meio de um `write` deixariam um JSON truncado -- e aí a
            # próxima leitura perderia TODA a evidência acumulada, que é
            # exatamente o que este arquivo existe para não deixar acontecer.
            temporario = CAMINHO_DO_PLACAR.with_suffix(".tmp")
            temporario.write_text(
                json.dumps(dados, ensure_ascii=False, indent=2),
                encoding="utf-8")
            temporario.replace(CAMINHO_DO_PLACAR)
            _DESDE_A_ULTIMA_GRAVACAO = 0
        return True
    except Exception:
        return False


def resumo() -> list[Veredito]:
    """O placar inteiro, do mais promissor para o menos. Para leitura humana."""
    with _LOCK:
        _carregar_se_preciso()
        linhas = list(_PLACAR.values())
    saida = [_veredito_de(l) for l in linhas]
    ordem = {"gabaritou": 0, "aprendendo": 1, "reprovado": 2,
             "sem_resposta": 3}
    saida.sort(key=lambda v: (ordem.get(v.situacao, 9), v.taxa_de_erro,
                              -v.amostras))
    return saida


def zerar_para_teste() -> None:
    """Só para os testes: limpa o estado de módulo."""
    global _CARREGADO, _DESDE_A_ULTIMA_GRAVACAO
    with _LOCK:
        _PLACAR.clear()
        _CARREGADO = True
        _DESDE_A_ULTIMA_GRAVACAO = 0


# ===========================================================================
# Os julgamentos -- lógica PURA, recebe leituras e devolve amostra
# ===========================================================================

def julgar_hp(
    *, prova: str, candidato: str, hp_lido: int | None,
    max_hp_lido: int | None, hp_da_tela: float | None,
    escala_de_inimigo: int, conta: str = "", id_run: str = "",
) -> Amostra:
    """Compara o HP que um candidato leu com o que a barra da tela mostra.

    `hp_da_tela` é a FRAÇÃO (0.0 a 1.0) que `vision.vida_do_alvo` devolve, e é o
    gabarito. `None` nele = sem gabarito, e a amostra não conta.

    A ESCALA ENTRA NO JULGAMENTO, e é o que teria pegado o defeito medido: no log
    de 19/08/2026 apareceu `hp_memoria=243`, que é o PET (`243/243` é a escala de
    jogador/pet, documentada em `memory.py`). Um candidato que aponta para o pet
    erra, mesmo que o número seja plausível.
    """
    if hp_da_tela is None or hp_lido is None:
        return Amostra(prova=prova, candidato=candidato, acertou=None,
                       lido=hp_lido, esperado=hp_da_tela, conta=conta,
                       id_run=id_run, detalhe="sem gabarito ou sem leitura")

    esperado = hp_da_tela * 100.0
    discriminante = FAIXA_DISCRIMINANTE[0] < esperado < FAIXA_DISCRIMINANTE[1]

    if max_hp_lido is not None and max_hp_lido != escala_de_inimigo:
        return Amostra(
            prova=prova, candidato=candidato, acertou=False, lido=hp_lido,
            esperado=round(esperado, 1), discriminante=discriminante,
            conta=conta, id_run=id_run,
            detalhe=f"max_hp={max_hp_lido} nao e escala de inimigo "
                    f"({escala_de_inimigo}) -- provavel pet ou jogador")

    erro = abs(float(hp_lido) - esperado)
    return Amostra(
        prova=prova, candidato=candidato, acertou=erro <= TOLERANCIA_DO_HP,
        lido=hp_lido, esperado=round(esperado, 1), discriminante=discriminante,
        conta=conta, id_run=id_run, detalhe=f"erro={erro:.1f}pp")


def julgar_booleano(
    *, prova: str, candidato: str, lido: bool | None,
    na_tela: bool | None, conta: str = "", id_run: str = "",
) -> Amostra:
    """Compara um estado de UI lido na memória com o que a tela mostra.

    Serve para `ADDR_MODAL` (caixa aberta?) e `ADDR_LOOT_WINDOW` (janela de loot
    aberta?), que são os dois ponteiros herdados do GhostBot cujo valor nunca foi
    confirmado nesta versão do cliente.

    **Toda amostra é discriminante aqui**, ao contrário do HP: um booleano não tem
    "extremo em que qualquer leitura acerta" -- errar `False` quando é `True` é
    tão informativo quanto o contrário.
    """
    if lido is None or na_tela is None:
        return Amostra(prova=prova, candidato=candidato, acertou=None,
                       lido=lido, esperado=na_tela, conta=conta, id_run=id_run,
                       detalhe="sem gabarito ou sem leitura")
    return Amostra(
        prova=prova, candidato=candidato, acertou=bool(lido) == bool(na_tela),
        lido=bool(lido), esperado=bool(na_tela), discriminante=True,
        conta=conta, id_run=id_run)


# `Amostra.ultima_vez_texto` mora aqui e não na dataclass para o `dataclass`
# continuar sendo só dados -- é o mesmo motivo pelo qual `VigiaDoAlvo` recebe
# leituras em vez de ir buscá-las.
def _ultima_vez_texto(self: Amostra) -> str:
    return time.strftime("%H:%M:%S")


Amostra.ultima_vez_texto = _ultima_vez_texto      # type: ignore[attr-defined]


# ===========================================================================
# O LEITOR -- `python -m blazesbot.core.calibracao`
# ===========================================================================
#
# O placar é JSON, e JSON não é feito para ser lido de olho. Este relatório é o
# que o usuário abre quando volta ao chat para decidir o que promover.
#
# Ele NÃO promove nada. A decisão é do usuário, e foi assim que ele pediu:
# *"quando tiver dados o suficiente eu volto aqui no chat, lemos tudo que foi
# analisado e colocamos em prática o que realmente funciona."*

def relatorio() -> str:
    """O placar em texto, pronto para colar no chat."""
    linhas = resumo()
    if not linhas:
        return ("Nenhuma amostra ainda. O placar enche durante as runs de BC -- "
                "a prova do alvo roda a cada leitura de combate.")

    saida = ["PLACAR DA CALIBRACAO DE PONTEIROS", ""]
    saida.append(f"critério para GABARITAR: {AMOSTRAS_PARA_GABARITAR} amostras, "
                 f"{DISCRIMINANTES_PARA_GABARITAR} delas discriminantes, "
                 f"{RUNS_PARA_GABARITAR} runs distintas, ZERO erro")
    for prova, tol in sorted(TOLERANCIA_DE_ERRO_POR_PROVA.items()):
        saida.append(f"  exceção: {prova} aceita até {tol:.1%} de erro "
                     f"(gabarito por CONSEQUÊNCIA tem ruído próprio)")
    saida.append("")
    # `mudo` é a coluna que faltava, e a falta dela escondeu um defeito por três
    # runs: `0x868` e `0x86c` não apareciam no relatório de jeito nenhum, então
    # não havia como ver que a lista fechada estava presa esperando por eles.
    cabeca = (f"{'prova':16s} {'candidato':14s} {'situacao':12s} "
              f"{'amostras':>9s} {'acertos':>8s} {'erro':>7s} "
              f"{'discr.':>7s} {'runs':>5s} {'mudo':>5s}")
    saida.append(cabeca)
    saida.append("-" * len(cabeca))
    for v in linhas:
        saida.append(
            f"{v.prova:16s} {v.candidato:14s} {v.situacao:12s} "
            f"{v.amostras:9d} {v.acertos:8d} {v.taxa_de_erro:6.1%} "
            f"{v.discriminantes_certas:7d} {v.runs:5d} {v.sem_leitura:5d}")

    gabaritaram = [v for v in linhas if v.situacao == "gabaritou"]
    saida.append("")
    if gabaritaram:
        saida.append("GABARITARAM (candidatos a promover, decisão do usuário):")
        for v in gabaritaram:
            saida.append(f"  {v.prova} -> {v.candidato}")
    else:
        faltam = min((AMOSTRAS_PARA_GABARITAR - v.amostras
                      for v in linhas if v.situacao == "aprendendo"),
                     default=0)
        saida.append("Ninguém gabaritou ainda.")
        if faltam > 0:
            saida.append(f"  o mais adiantado precisa de ~{faltam} amostras "
                         f"a mais (e das runs distintas).")
    return "\n".join(saida)


# ===========================================================================
# A PENEIRA -- filtragem progressiva, o mecanismo do Cheat Engine
# ===========================================================================
#
# Pedido do usuário em 20/08/2026: *"acho interessante testar mais candidatos,
# no caso vários e vários conforme for entendendo e vendo que não é o correto, o
# próprio bot tentar usar o cheat engine e ir tentando filtrar por si só."*
#
# E o placar da primeira noite justifica: os quatro candidatos da lista fechada
# do alvo REPROVARAM (`0x808` com 96% de erro, `0x80c` com 100%, e os `+0x60` nem
# produziram amostra julgável). A lista fechada acabou.
#
# ---------------------------------------------------------------------------
# COMO O CHEAT ENGINE FAZ, E O QUE MUDA AQUI
# ---------------------------------------------------------------------------
#
# No CE o fluxo é: "valor desconhecido" -> varre tudo -> **o valor mudou** ->
# filtra os que mudaram junto -> repete até sobrar pouco. O que faz aquilo
# funcionar não é a varredura, é a MUDANÇA: cada valor novo elimina os endereços
# que só coincidiam.
#
# Aqui o valor não é desconhecido -- a barra da tela DIZ qual é. Então a primeira
# passada já filtra por igualdade, e as seguintes filtram de novo quando a vida
# muda. É o CE com gabarito, e converge mais rápido.
#
# ---------------------------------------------------------------------------
# O QUE É VARRIDO: os CAMPOS DO PERSONAGEM, não a memória inteira
# ---------------------------------------------------------------------------
#
# Varrer o processo procurando o NÚMERO da vida daria milhões de endereços e um
# resultado inútil: um endereço absoluto de heap muda a cada sessão. O que serve
# é o OFFSET dentro da struct do personagem, que é estável para a versão do
# cliente -- é a forma de todos os ponteiros que este bot já usa.
#
# Então a varredura testa cada campo do personagem COMO SE fosse o ponteiro do
# alvo: valida como entidade e compara o HP dela com a barra. É o mesmo teste que
# `_entidade_no_campo` já faz, repetido ao longo da struct.
#
# ---------------------------------------------------------------------------
# EXIGIR MUDANÇA É O QUE IMPEDE APRENDER LIXO
# ---------------------------------------------------------------------------
#
# Filtrar duas vezes com a MESMA vida não elimina ninguém -- todo endereço que
# passou na primeira passa na segunda. Pior: daria a impressão de convergência.
# `MUDANCA_MINIMA_PARA_FILTRAR` exige que a barra tenha se movido antes de a
# peneira apertar, e é a tradução direta do "the value has changed" do CE.

# Quantos sobreviventes bastam para promover a candidatos de verdade. Acima
# disso a peneira continua apertando; abaixo, o placar normal assume e cada um
# passa a precisar das 50 amostras, 20 discriminantes e 10 runs.
SOBREVIVENTES_PARA_PROMOVER = 8

# Quantas passadas com vida DIFERENTE antes de promover. Uma passada só elimina
# quem coincidia naquele instante; três com valores distintos é o que o CE faz
# na prática antes de acreditar no resultado.
PASSADAS_PARA_PROMOVER = 3

# Quanto a vida da tela precisa ter mudado (em pontos percentuais) para a
# passada seguinte valer. Menos que isto e a peneira aperta sem eliminar nada.
MUDANCA_MINIMA_PARA_FILTRAR = 5.0


@dataclass
class Peneira:
    """Filtragem progressiva de offsets. LÓGICA PURA: não lê memória.

    Recebe `{offset: hp_lido}` de quem sabe ler, e o `esperado` da tela. Guarda
    quem sobrevive e devolve quantos restam.

    Estado POR PROCESSO e não persistido: os sobreviventes só valem enquanto a
    struct daquela sessão for a mesma. O que atravessa noites é o PLACAR, que
    recebe os promovidos -- e ele exige runs distintas justamente para não
    confiar numa sessão só.
    """

    prova: str
    sobreviventes: set[int] | None = None
    passadas: int = 0
    ultimo_esperado: float | None = None
    # DESQUALIFICAÇÃO É PERMANENTE, e isto é conserto de defeito no desenho.
    #
    # Com `somar` (união), um campo desqualificado por `remover` voltava a ser
    # ADMITIDO no TAB seguinte -- ele muda sempre, então muda no TAB também. A
    # peneira ficava readmitindo justamente quem ela acabou de descartar.
    #
    # Um teste pegou. A lista negra fecha o ciclo: quem tremulou uma vez está
    # fora para sempre, e nenhuma evidência positiva o traz de volta.
    desqualificados: set[int] = field(default_factory=set)

    def peneirar(self, achados: dict[int, float], esperado: float) -> int:
        """Uma passada. Devolve quantos offsets sobraram.

        `-1` quando a passada foi RECUSADA por falta de mudança -- e recusar é o
        ponto: apertar com a mesma vida não elimina ninguém.
        """
        if (self.ultimo_esperado is not None
                and abs(esperado - self.ultimo_esperado)
                < MUDANCA_MINIMA_PARA_FILTRAR):
            return -1

        casaram = {off for off, hp in achados.items()
                   if abs(float(hp) - esperado) <= TOLERANCIA_DO_HP}
        self.sobreviventes = (casaram if self.sobreviventes is None
                              else self.sobreviventes & casaram)
        self.passadas += 1
        self.ultimo_esperado = esperado
        return len(self.sobreviventes)

    def intersectar(self, candidatos: set[int]) -> int:
        """Aperta com um conjunto JÁ DECIDIDO por quem chama.

        `peneirar` compara número contra gabarito numérico; esta versão recebe o
        conjunto pronto. Serve para gabarito que não é número -- o caso é
        "mudou de valor no TAB", em que quem sabe julgar é quem viu o antes e o
        depois.

        SEM a guarda de `MUDANCA_MINIMA_PARA_FILTRAR`, e de propósito: lá a
        exigência existe porque apertar com a MESMA vida não elimina ninguém.
        Aqui cada passada é um TAB, e todo TAB é um evento novo por definição --
        não há como "repetir o mesmo valor".
        """
        self.sobreviventes = (set(candidatos) if self.sobreviventes is None
                              else self.sobreviventes & set(candidatos))
        self.passadas += 1
        return len(self.sobreviventes)

    def somar(self, candidatos: set[int]) -> int:
        """UNIÃO: acumula quem já apresentou a evidência ao menos uma vez.

        ==============================================================
        POR QUE UNIÃO, E NÃO INTERSEÇÃO, PARA A IDENTIDADE
        ==============================================================

        `intersectar` exige a evidência em TODA passada, e para a identidade isso
        estava ERRADO -- medido em 20/08/2026, 12 runs:

            alvo_selecao|0x808   10 amostras   0 acertos   "nao mudou no TAB"

        E `0x808` é **provadamente** a seleção: três rodadas do
        `10-DESCOBRIR-ALVO` mostraram `+0xBC = 'Gun Witch'` na struct que ele
        aponta. Ou seja o critério reprovava o campo CERTO.
        
        A razão é regra de jogo: **com um único mob vivo sobrando, o TAB
        reseleciona o MESMO** -- e a fase dos guardas termina justamente assim,
        com um vivo por vez. Não mudar num TAB é legítimo.
        
        O que continua valendo é o outro lado: mudar SEM TAB desqualifica
        (`remover`). Então identidade = "mudou em ALGUM TAB" **e** "nunca mudou
        fora de TAB".
        """
        novos = set(candidatos) - self.desqualificados
        self.sobreviventes = (novos if self.sobreviventes is None
                              else (self.sobreviventes | novos)
                              - self.desqualificados)
        self.passadas += 1
        return len(self.sobreviventes)

    def remover(self, candidatos: set[int]) -> int:
        """DESQUALIFICA de vez. Devolve quantos sobraram.

        ==============================================================
        POR QUE A PENEIRA PRECISA DE UM "NÃO"
        ==============================================================

        `intersectar` guarda quem PASSOU num teste positivo. Isto tira quem
        falhou num teste NEGATIVO -- e sem ele o critério da identidade fica pela
        metade.

        Medido no `combate.log` de 20/08/2026: o campo em uso (`0x808`) passeia
        por endereços diferentes do mesmo pool de entidades a cada leitura, troca
        de nome conforme o personagem ANDA (`Evil Centipede` -> `Poleax
        Aborigine` -> `Poison Rattan`) e às vezes cai no pet (243/243). Ou seja
        ele **muda sempre**.

        Um campo assim passaria em todo TAB e gabaritaria sendo lixo. Seleção é
        ESTÁVEL enquanto o alvo vive: tem de mudar no TAB **e** ficar parada
        entre TABs. `remover` é a metade que faltava.

        Não conta passada: desqualificar não é evidência a favor de ninguém.
        """
        self.desqualificados |= set(candidatos)
        if self.sobreviventes is None:
            return -1
        self.sobreviventes -= self.desqualificados
        return len(self.sobreviventes)

    @property
    def pronta(self) -> bool:
        """Poucos sobreviventes e passadas suficientes: hora de promover."""
        return (self.sobreviventes is not None
                and 0 < len(self.sobreviventes) <= SOBREVIVENTES_PARA_PROMOVER
                and self.passadas >= PASSADAS_PARA_PROMOVER)

    @property
    def esgotada(self) -> bool:
        """Ninguém sobreviveu. Recomeçar é melhor que paralisar -- a struct pode
        ter mudado no meio (troca de alvo, morte do mob) e a interseção zerou por
        isso, não porque não existe resposta."""
        return self.sobreviventes is not None and not self.sobreviventes

    def recomecar(self) -> None:
        """Zera a busca -- MAS NÃO a lista negra.

        Quem tremulou continua fora: aquilo foi medido e não deixa de ser
        verdade porque a interseção zerou. Limpar a lista negra aqui faria a
        peneira reaprender o mesmo descarte a cada recomeço.
        """
        self.sobreviventes = None
        self.passadas = 0
        self.ultimo_esperado = None


def reabrir(prova: str, candidato: str | None = None) -> int:
    """Zera o histórico de uma prova (ou de um candidato) e devolve quantos.

    ==================================================================
    POR QUE ISTO É NECESSÁRIO, E É DEFEITO MEDIDO
    ==================================================================

    Em 20/08/2026 a reserva `0x80C` (o PET) saiu do `target_object`, e a leitura
    de `alvo_hp|0x808` passou a significar outra coisa. Mas o placar já o tinha
    **reprovado** (100 amostras, 96% de erro) na leitura ANTIGA -- e reprovado não
    volta a ser amostrado.

    Resultado: doze runs depois do conserto, `alvo_hp` estava com TODOS os
    candidatos encerrados (`0x808` e `0x80c` reprovados, `0x868` e `0x86c` sem
    resposta) e **não havia como medir o conserto**. O placar guardava a memória
    de um defeito já corrigido e bloqueava a evidência nova.

    A regra que fica: **mudou o que a leitura significa? reabra a prova.** O
    placar mede leituras, não intenções, e não tem como adivinhar que o código
    mudou por baixo dele.
    """
    global _DESDE_A_ULTIMA_GRAVACAO
    with _LOCK:
        _carregar_se_preciso()
        _mesclar_do_disco()
        alvos = [chave for chave, linha in _PLACAR.items()
                 if linha["prova"] == prova
                 and (candidato is None or linha["candidato"] == candidato)]
        for chave in alvos:
            del _PLACAR[chave]
        _DESDE_A_ULTIMA_GRAVACAO = AMOSTRAS_ENTRE_GRAVACOES
    if alvos:
        # SEM MESCLA -- ver `salvar`. E ATENÇÃO: se o bot estiver RODANDO, ele
        # tem as entradas velhas em memória e vai reescrevê-las no flush
        # seguinte. Foi o que aconteceu em 20/08/2026: reabri `alvo_hp` com o bot
        # de pé e a reabertura durou até o próximo `AMOSTRAS_ENTRE_GRAVACOES`.
        #
        # Reabrir exige o bot PARADO, e o leitor avisa isso na tela.
        salvar(mesclar=False)
    return len(alvos)


def candidatos_em_jogo(prova: str) -> list[str]:
    """Rótulos que ainda vale a pena medir nesta prova.

    ==================================================================
    O PLACAR É QUEM SABE QUEM MEDIR -- e isto corrige um defeito
    ==================================================================

    A varredura promove sobreviventes como candidatos novos
    (`varredura:0x9a4`), mas quem amostrava iterava uma LISTA FIXA no código.
    Resultado: o promovido recebia UMA amostra, no instante da promoção, e nunca
    mais -- e precisa de `AMOSTRAS_PARA_GABARITAR` para valer algo. A peneira
    convergia e o resultado morria ali.

    Perguntar ao placar resolve os dois lados: o promovido entra na medição na
    volta seguinte, e o conjunto SOBREVIVE A REINÍCIO do bot -- o placar está em
    disco, a lista no código não sabia de nada.

    Devolve só quem não está encerrado (`reprovado` / `sem_resposta`), então quem
    chama não precisa filtrar de novo.
    """
    with _LOCK:
        _carregar_se_preciso()
        return [linha["candidato"] for linha in _PLACAR.values()
                if linha["prova"] == prova
                and linha["situacao"] not in ENCERRADAS]


def julgar_texto(
    *, prova: str, candidato: str, lido: str | None, esperado: str,
    conta: str = "", id_run: str = "",
) -> Amostra:
    """Compara um NOME lido na memória com o nome esperado pelo CENÁRIO.

    ==================================================================
    POR QUE TEXTO VALE AO LADO DO NÚMERO
    ==================================================================

    Um número pode coincidir por acaso -- foi o `hp_memoria=100` em vida cheia
    que obrigou a inventar `discriminante`. Um nome não: `Gun Witch` num campo
    aleatório não acontece.

    E o gabarito é de CENÁRIO, não de tela: no waypoint dos guardas o alvo se
    chama `Gun Witch`, no do boss `Blaze Skull Marshal`. Não custa captura.

    COMPARAÇÃO POR CONTINÊNCIA, não por igualdade: o cliente às vezes devolve o
    nome com sufixo de nível ou espaço à direita, e exigir igualdade exata
    reprovaria a leitura CERTA por causa de formatação.

    **TODA amostra é discriminante** -- como no booleano, não existe extremo em
    que qualquer leitura acerta.
    """
    if not lido:
        return Amostra(prova=prova, candidato=candidato, acertou=None,
                       lido=lido, esperado=esperado, conta=conta,
                       id_run=id_run, detalhe="nome nao leu")
    acertou = esperado.lower() in str(lido).lower()
    return Amostra(
        prova=prova, candidato=candidato, acertou=acertou, lido=lido,
        esperado=esperado, discriminante=True, conta=conta, id_run=id_run,
        detalhe="" if acertou else f"leu {lido!r}")


# Piso para um valor parecer ponteiro de entidade. Abaixo disto é zero, flag ou
# contador -- não é endereço de heap no espaço de usuário.
PISO_DE_PONTEIRO = 0x10000


def julgar_troca(
    *, prova: str, candidato: str, antes: int | None, depois: int | None,
    conta: str = "", id_run: str = "",
) -> Amostra:
    """O campo MUDOU de valor atravessando um TAB?

    ==================================================================
    O GABARITO MAIS FORTE QUE EXISTE AQUI, E NÃO CUSTA TELA
    ==================================================================

    Fato de jogo estabelecido pelo usuário: **o TAB nunca mira mob morto**. Logo,
    depois de um TAB a seleção É outra entidade -- necessariamente, sem depender
    de captura, de barra desenhada ou de template.

    Então o campo que GUARDA a seleção tem de mudar de valor. Um campo que não
    muda não é a seleção, e nenhuma quantidade de coincidência de HP conserta
    isso.

    É o teste que faltava. O log de 20/08/2026 mostrou `ptr=0x2f768910` com
    `trocas_ptr=0` atravessando TRÊS TABs -- e ao mesmo tempo o HP daquele
    endereço mudando de 9 para 0. Ou seja: o campo aponta para algo vivo, mas
    NÃO é a seleção. Sem esta prova, essa distinção fica no log e não no placar.

    ==================================================================
    OS DOIS VALORES PRECISAM PARECER PONTEIRO
    ==================================================================

    Sem isso, um campo que oscila entre 0 e lixo "trocaria" a cada TAB e
    gabaritaria sem ser nada. `PISO_DE_PONTEIRO` é a mesma faixa que
    `Memory.resolve` já usa para recusar elo inválido.

    **Toda amostra é discriminante** -- não existe extremo em que qualquer
    leitura acerta.
    """
    if antes is None or depois is None:
        return Amostra(prova=prova, candidato=candidato, acertou=None,
                       lido=depois, esperado="mudar", conta=conta,
                       id_run=id_run, detalhe="leitura faltou")
    if antes < PISO_DE_PONTEIRO or depois < PISO_DE_PONTEIRO:
        return Amostra(
            prova=prova, candidato=candidato, acertou=None, lido=depois,
            esperado="mudar", conta=conta, id_run=id_run,
            detalhe=f"nao parece ponteiro ({antes:#x} -> {depois:#x})")
    if antes == depois:
        # NÃO MUDAR NÃO É ERRO -- corrigido em 20/08/2026 por medição.
        #
        # `0x808` levou 0 de 10 aqui, e ele é PROVADAMENTE a seleção (o
        # `10-DESCOBRIR-ALVO` leu `'Gun Witch'` na struct que ele aponta, três
        # rodadas). O critério reprovava o campo certo.
        #
        # A regra de jogo explica: com um único mob vivo sobrando, o TAB
        # reseleciona o MESMO -- e a fase dos guardas acaba exatamente assim.
        #
        # Então "não mudou" passa a ser NÃO JULGÁVEL. Um campo que nunca muda
        # acumula `mudo` e é encerrado por `sem_resposta`, que é o desfecho certo
        # para "isto não é a seleção".
        return Amostra(
            prova=prova, candidato=candidato, acertou=None,
            lido=f"{antes:#x}", esperado="mudar", conta=conta, id_run=id_run,
            detalhe="nao mudou neste TAB (pode ser o ultimo mob vivo)")
    return Amostra(
        prova=prova, candidato=candidato, acertou=True,
        lido=f"{antes:#x}->{depois:#x}", esperado="mudar", discriminante=True,
        conta=conta, id_run=id_run)


if __name__ == "__main__":       # pragma: no cover - ferramenta de leitura
    import sys

    # `--reabrir <prova> [candidato]` zera o histórico de uma prova.
    #
    # Existe porque o placar mede LEITURAS, e quando o código muda o que a
    # leitura significa, o histórico antigo passa a mentir -- e `reprovado` não
    # volta a ser amostrado. Foi o que aconteceu com `alvo_hp` em 20/08/2026: a
    # reserva do pet saiu do `target_object` e o placar continuou com o veredito
    # da leitura velha, cego para o conserto. Ver `reabrir`.
    if len(sys.argv) > 2 and sys.argv[1] == "--reabrir":
        _prova = sys.argv[2]
        _candidato = sys.argv[3] if len(sys.argv) > 3 else None
        _n = reabrir(_prova, _candidato)
        print(f"reabertos {_n} candidato(s) da prova {_prova!r}"
              f"{'' if _candidato is None else ' (' + _candidato + ')'}.")
        print("A medição recomeça do zero na próxima run.")
        print()
        print("*** O BOT PRECISA ESTAR PARADO. ***")
        print("Com ele rodando, as entradas velhas estão na memória dele e")
        print("voltam para o arquivo no flush seguinte -- foi o que aconteceu")
        print("em 20/08/2026, e a reabertura durou poucos segundos.")
    else:
        print(relatorio())
