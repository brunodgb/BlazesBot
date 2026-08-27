"""FERRAMENTA TEMPORÁRIA -- acompanha a BATALHA ao vivo. Só LÊ.

Módulo FOLHA: nada do bot importa daqui.

=========================================================================
ELA NÃO REIMPLEMENTA NADA -- e é esse o ponto
=========================================================================

Pedido do usuário em 26/08/2026: *"cria um .bat que acompanha em tempo real a
batalha e USA A FUNÇÃO DE TARGET DO `target_hybrid`, pois eu quero ir vendo o
que está acontecendo"*.

Então o que esta ferramenta faz é **chamar o mesmo caminho que o bot chama**, e
imprimir. Peça por peça, tudo é reuso:

    `TargetHybrid.ler(..., com_tela=False)`  o alvo (id, nome, HP, nível)
    `TargetHybrid.linha_do_log(...)`         a MESMA linha que o BC escreve
    `MorteDoAlvo.veredito` / `.contar`       o veredito e a trava por identidade
    `watchdog.client_pids()`                 quais `client.exe` existem
    `core.janelas.titulo_do_pid()`           como se chama cada um
    `Memory.vida_pct` / `in_battle`          o personagem

Uma ferramenta de diagnóstico que reimplementa a leitura que ela deveria estar
diagnosticando **não diagnostica nada**: ela mostra o comportamento da cópia. Se
o que aparece aqui estiver errado, o bot está errado do mesmo jeito -- é para
isso que ela serve.

NÃO CAPTURA A TELA (`com_tela=False`) e **não escreve nada** no jogo. A reserva
pela barra desenhada é do BC; aqui a pergunta é o que a MEMÓRIA responde.
"""
from __future__ import annotations

import logging
import time

from ..bot.watchdog import client_pids
from ..core.janelas import titulo_do_pid
from ..core.memory import Memory
from ..core.target_hybrid import (
    MorteDoAlvo,
    TargetHybrid,
    investigar_alvo_perdido,
)

# Cadência da leitura. É memória pura -- algumas leituras de 4 bytes por volta,
# sem captura -- então 0,1 s custa microssegundos de processador e mostra a
# batalha correndo em vez de aos saltos.
PASSO = 0.1

# Teto padrão, para a ferramenta fechar sozinha se você esquecer dela aberta.
SEGUNDOS_PADRAO = 900.0

# De quanto em quanto tempo repetir uma linha que NÃO mudou.
#
# Sem isto, uma luta longa contra um mob de muita vida ficaria com a tela parada
# e ninguém saberia se a ferramenta morreu ou se o jogo está quieto. Com isto,
# ela dá sinal de vida sem afogar a tela.
SEGUNDOS_ENTRE_ECOS = 5.0


def _calar_o_pymem() -> None:
    """Tira o `Process N is being debugged` do meio da leitura.

    O `pymem` loga isso em DEBUG a cada `Memory(pid)`, e como esta ferramenta
    abre um handle por cliente só para montar a lista, a tela nasce com uma
    linha de ruído entre cada linha útil -- medido na primeira rodada de
    26/08/2026, com o usuário escolhendo o PID no meio do barulho.

    SÓ AQUI, e não no logger raiz: em `dev` esse DEBUG vai para o
    `blazes-dev.jsonl` e lá ele não atrapalha ninguém. Quem cala é a
    ferramenta, para a ferramenta.
    """
    logging.getLogger("pymem").setLevel(logging.WARNING)


def _escolher_pid() -> int | None:
    """Lista os `client.exe` NUMERADOS e devolve o escolhido.

    *"Faça eu poder escolher o pid, liste eles que tenha o mesmo nome, só para
    eu escolher o número."*

    Todos os processos se chamam `client.exe`, então o nome não separa nada --
    quem separa é o **título da janela** e o **nick lido na memória**. O número
    da esquerda é só para digitar.

    Devolve `None` quando não há cliente aberto ou quando a pessoa desiste.
    """
    _calar_o_pymem()
    pids = sorted(client_pids())
    if not pids:
        print("Nenhum client.exe em execução.")
        print("Abra o jogo, ENTRE COM UM PERSONAGEM e rode de novo.")
        return None

    if len(pids) == 1:
        pid = pids[0]
        print(f"Um cliente só ({pid} — {_rotulo(pid)}). Usando ele.\n")
        return pid

    print("Clientes abertos:\n")
    for numero, pid in enumerate(pids, start=1):
        print(f"  [{numero}]  PID {pid:>6}   {_rotulo(pid)}")
    print()

    while True:
        try:
            escolha = input(f"Escolha o número (1-{len(pids)}), "
                            "ou Enter para sair: ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not escolha:
            return None
        if escolha.isdigit() and 1 <= int(escolha) <= len(pids):
            return pids[int(escolha) - 1]
        print(f"  Não entendi {escolha!r}. Digite um número de 1 a {len(pids)}.")


def _rotulo(pid: int) -> str:
    """Como este cliente se chama, para uma pessoa escolher.

    O NICK VEM PRIMEIRO quando dá para lê-lo: é o que o usuário reconhece. O
    título da janela é a reserva, e ele existe mesmo quando a memória não abre
    (cliente na tela de login, por exemplo).
    """
    titulo = titulo_do_pid(pid)
    try:
        memoria = Memory(pid)
    except Exception:
        return titulo
    try:
        nick = memoria.char_name()
    except Exception:
        nick = None
    finally:
        memoria.close()
    return f"{nick}  ({titulo})" if nick else titulo


def _estado_do_personagem(memoria: Memory | None) -> str:
    """Vida e batalha, numa frase. `?` é "não sei", nunca zero."""
    if memoria is None:
        return "personagem: sem leitura"
    try:
        vida = memoria.vida_pct()
        batalha = memoria.in_battle()
    except Exception:
        return "personagem: sem leitura"
    quanto = "?" if vida is None else f"{vida:.0f}%"
    como = {True: "EM BATALHA", False: "fora de batalha",
            None: "batalha: ?"}[batalha]
    return f"personagem: vida {quanto}  {como}"


def run_vigiar_combate(pid: int = 0, segundos: float = 0.0) -> int:
    """O laço. `pid=0` pergunta qual cliente; `segundos=0` usa o padrão."""
    if not pid:
        escolhido = _escolher_pid()
        if escolhido is None:
            return 1
        pid = escolhido

    teto = segundos if segundos > 0 else SEGUNDOS_PADRAO
    hibrido = TargetHybrid()
    morte = MorteDoAlvo()
    try:
        memoria: Memory | None = Memory(pid)
    except Exception as exc:
        print(f"Não consegui abrir o processo {pid}: {exc}")
        memoria = None

    print("=" * 72)
    print(f"VIGIANDO A BATALHA  —  PID {pid}  ({_rotulo(pid)})")
    print("Só LÊ. Ctrl+C para encerrar.")
    print("=" * 72)
    print()

    anterior: float | None = None
    # Ids que ja foram investigados. Ver o bloco dentro do laco.
    investigados: set[int] = set()
    # O id da leitura anterior -- ver o bloco "DE QUAL ID VEIO".
    anterior_id: int | None = None
    ultima_linha = ""
    ultimo_eco = 0.0
    fim = time.time() + teto
    try:
        while time.time() < fim:
            # A MESMA CHAMADA QUE O BOT FAZ. `com_tela=False` porque a reserva
            # pela barra desenhada é do BC e exige captura -- aqui a pergunta é
            # o que a MEMÓRIA responde.
            info = hibrido.ler(pid, hwnd=0, com_tela=False)

            if not info.tem_alvo:
                linha = "sem alvo"
            else:
                # ==========================================================
                # O ID RESPONDE E A ENTIDADE NAO APARECE: INVESTIGA
                # ==========================================================
                #
                # *"Eu vejo que o value do 0115CB80 altera, mas nao acha o
                # target no array -- mas em algum lugar da memoria do jogo ele
                # esta, pq o mob existe, a chave existe."*
                #
                # UMA VEZ POR ID. A varredura percorre o processo inteiro e
                # custa segundos; repetir a cada leitura transformaria o vigia
                # num travamento. E o `set` responde a pergunta que interessa
                # de qualquer jeito -- ela e sobre o id, nao sobre o instante.
                if (info.entidade is None and memoria is not None
                        and info.target_id not in investigados):
                    investigados.add(info.target_id)
                    for texto in investigar_alvo_perdido(memoria,
                                                         info.target_id):
                        print(f"           {texto}")
                # A MESMA LINHA QUE O BC ESCREVE NO LOG DA CONTA.
                linha = hibrido.linha_do_log(info, anterior, segunda_fase=False)
                # ==========================================================
                # TRÊS ESTADOS, E O DO MEIO ESTAVA ESCONDIDO
                # ==========================================================
                #
                # A medição de 26/08/2026 mostrou um estado que ninguém tinha
                # separado: **entidade ACHADA e nome ILEGÍVEL**
                # (`#245506802  100/100, nv61`). Ele saía com a mesma cara de
                # "entidade não achada", porque `linha_do_log` cai no
                # `nome or #id` -- e os dois pedem consertos opostos.
                if info.entidade is not None and not info.entidade["nome"]:
                    linha += "   (entidade OK, NOME ilegível)"
                # ==========================================================
                # DE QUAL ID VEIO -- a pergunta que o log de 26/08 nao respondia
                # ==========================================================
                #
                # Quando um id ORFAO (que nao resolve) finalmente vira um mob
                # legivel, existem duas explicacoes OPOSTAS:
                #
                #   MESMO id  -> era o mob NOVO, e a entidade dele chegou
                #                atrasada ao array. Recusar joga fora um alvo
                #                bom; o certo e ESPERAR.
                #   OUTRO id  -> era o cadaver do mob que acabou de morrer, e o
                #                bot trocou. O certo e dar TAB de novo, em vez
                #                de esperar a roda reiniciar.
                #
                # Sem o id na linha, os dois aparecem como "alvo novo" -- que e
                # exatamente o que faltou no log de 26/08. Nada de conserto sai
                # daqui ate esta linha dizer qual dos dois e.
                if info.mudou and anterior_id is not None:
                    linha += f"   [id {info.target_id} ← era {anterior_id}]"
                if info.mudou:
                    anterior_id = info.target_id
                if info.entidade is not None:
                    anterior = info.entidade["hp"] / info.entidade["max_hp"]
                if info.mudou:
                    morte.esquecer()
                if (morte.veredito(info.entidade) is True
                        and morte.contar(info.target_id)):
                    linha += "   <<< MORREU"

            agora = time.time()
            mudou = linha != ultima_linha
            if mudou or agora - ultimo_eco >= SEGUNDOS_ENTRE_ECOS:
                ultima_linha, ultimo_eco = linha, agora
                relogio = time.strftime("%H:%M:%S")
                print(f"[{relogio}] {linha}")
                if mudou:
                    print(f"           {_estado_do_personagem(memoria)}")
            time.sleep(PASSO)
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        hibrido.fechar()
        if memoria is not None:
            memoria.close()
    return 0
