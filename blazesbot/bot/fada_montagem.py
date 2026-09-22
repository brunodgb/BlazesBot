"""A MONTAGEM DA FADA -- as peças que o laço de cura recebe prontas.

Saiu de `supervisor.py` em 04/09/2026, empurrado pela catraca de tamanho
(`tests/test_quality_gates_python.py`): o supervisor não pode crescer, e a Fada
é justamente a parte que mais vai crescer daqui para frente (reviver aliado,
perceber a própria queda, bater o coração durante as tarefas lentas).

O QUE MORA AQUI: abrir a memória e o teclado da conta, montar os "callables"
que a `FadaDoTime` consome e ligar o laço. Nada de decisão de cura -- essa é da
`FadaDoTime`, que continua sem saber que supervisor existe.

`sup` é o `AccountSupervisor` da conta. Recebe o supervisor inteiro, e não meia
dúzia de campos soltos, porque a montagem usa dele coisas que só ele sabe
responder (quem é o dono da macro, quem está no time, o nick de cada login) --
e porque a alternativa seria uma lista de argumentos que muda a cada peça nova.
"""

from __future__ import annotations

import logging
import time

import win32gui

from ..core import volta_ao_ponto
from ..core.coords import coords_for_window
from ..core.memory import Memory
from .context import Disconnected

# Respiro quando a Fada não consegue nem começar (memória fechada, por exemplo).
#
# `_operate` chama de novo assim que esta função devolve: sem a pausa, uma falha
# de leitura vira laço quente -- a conta gira sem dormir, sem curar e sem cair,
# que é o pior dos três estados.
SEGUNDOS_ENTRE_TENTATIVAS = 1.0


def rodar_a_fada(sup, so_montar: bool = False):
    """Roda o laço da Fada enquanto o time estiver de pé.

    MESMO ISOLAMENTO DO MODO APP: a `FadaDoTime` não recebe `BotContext`,
    não abre memória e não conhece supervisor. Tudo chega por injeção, e
    quem sabe abrir o processo do jogo é este arquivo, que já sabia.

    A DIFERENÇA para o modo APP é que aqui a memória NÃO é opcional. A Fada
    precisa saber quem está no time, onde cada um está no painel e quanta
    vida tem -- sem isso ela clicaria às cegas, e clique às cegas cura o
    aliado errado. Sem memória ela avisa e não faz nada, que é melhor.
    """
    from ..core.inputs import Input as _Input
    from . import mural
    from .fada import FadaDoTime
    from .time_do_app import aceitador_do_seguidor, ancora_do_lider

    log = logging.getLogger(f"blazes.{sup.account.login}")
    teclas = sup.account.settings.keys
    app = sup.account.settings.app

    try:
        memoria = Memory(sup.pid)
    except Exception as exc:
        # MEMÓRIA QUE NÃO ABRE QUASE SEMPRE É JANELA QUE MORREU.
        if not win32gui.IsWindow(sup.hwnd):
            raise Disconnected(
                "janela do cliente fechada antes de a Fada começar") from exc
        log.warning("FADA: não consegui abrir a memória (%s). Sem ela a "
                    "Fada não age.", exc)
        time.sleep(SEGUNDOS_ENTRE_TENTATIVAS)
        return

    entrada = _Input(sup.hwnd)
    pontos = coords_for_window(sup.hwnd)

    def _seguro(fn, padrao=None):
        try:
            return fn()
        except Exception:
            return padrao

    def clicar_no_retrato(slot: int) -> bool:
        """Clique esquerdo no retrato do companheiro `slot` (0-based)."""
        ponto = getattr(pontos, f"team_member_{slot + 1}", None)
        if ponto is None:
            return False
        entrada.left_click(ponto[0], ponto[1])
        return True

    def dormir(segundos: float) -> bool:
        """Espera fatiada: o botão Parar responde no meio dela."""
        fim = time.monotonic() + max(0.0, segundos)
        while time.monotonic() < fim:
            if sup.stop_event.is_set():
                return False
            time.sleep(min(0.05, max(0.0, fim - time.monotonic())))
        return not sup.stop_event.is_set()

    # ==================================================================
    # O PONTO INICIAL DA FADA
    # ==================================================================
    #
    # Pedido do usuário em 07/09/2026: *"a fada deve voltar ao ponto inicial
    # para evitar zonas de risco"*. Ela não anda de propósito, mas é ARRASTADA:
    # a cura em grupo tem alcance, e seguir o time que avança a tira do lugar
    # seguro sem ninguém mandar.
    #
    # O PONTO É ONDE ELA ESTAVA QUANDO COMEÇOU, e não uma coordenada
    # configurada. Motivo: é o mesmo critério que o APP já usa (a base é a
    # primeira posição lida), o usuário posiciona a Fada onde quer antes de
    # ligar, e não existe waypoint fora da cave -- decisão dele em 06/09/2026:
    # *"como no caso do APP não vão existir waypoints, vai ter que usar o ponto
    # inicial como base"*.
    #
    # SEM CENTRO DE MINIMAPA, NÃO ANDA. `coords_for_window` responde por
    # resolução, então isso só acontece com janela em tamanho não medido -- e
    # aí a resposta certa é ficar parada, não clicar num pixel adivinhado.
    ponto_inicial: list[tuple[int, int] | None] = [None]
    centro_do_minimapa = getattr(pontos, "minimap_center", None)

    def voltar_ao_ponto() -> bool:
        """`True` = mandei andar de volta. A distância é UMA leitura de memória.

        BARATO POR DESENHO (o pedido era explícito: *"uma rotina de verificação
        de distância que opere com baixo custo computacional"*). O caro seria
        decidir isto por tela; aqui não há captura nenhuma: lê-se a posição
        (quatro bytes) e compara-se com a guardada. A cadência é de quem chama
        -- `fada.SEGUNDOS_ENTRE_CONFERENCIAS_DO_PONTO`.
        """
        pos = _seguro(memoria.position)
        if pos is None:
            return False
        if ponto_inicial[0] is None:
            ponto_inicial[0] = pos
            log.info("FADA: ponto inicial guardado em %s — volto para cá se "
                     "me arrastarem.", pos)
            return False
        if volta_ao_ponto.cheguei(pos, ponto_inicial[0]) is not False:
            # `True` (estou no ponto) e `None` (não sei) têm o mesmo desfecho:
            # não andar. Andar sem saber onde se está é como o bot se perde.
            return False
        log.info("FADA: fui arrastada para %s (o ponto é %s) — voltando.",
                 pos, ponto_inicial[0])
        return volta_ao_ponto.mandar_andar(
            pos, ponto_inicial[0], centro_do_minimapa,
            lambda x, y: entrada.right_click(x, y, repetir=False))

    # ==================================================================
    # OS CUIDADOS DE OCIOSA: pet e bolsa
    # ==================================================================
    #
    # SEM TECLA DE PET, NENHUM DOS DOIS EXISTE. Decisão do usuário em
    # 01/09/2026: uma Fada sem pet não cata item nenhum, então não tem lixo
    # para apagar -- e verificar pet em quem não tem é gasto pelo gasto.
    # Uma condição só porque é a mesma causa.
    #
    # A FADA NÃO FAZ SHUFFLE ANTI-AFK, e isso não precisou de código: ele
    # mora no executor de macro, e ela não roda o executor. Fica dito aqui
    # porque a ausência é deliberada, não esquecimento -- ela passa a sessão
    # parada de propósito.
    tecla_do_pet = (getattr(teclas, "pet_summon", "") or "").strip()
    tecla_da_bolsa = (getattr(teclas, "inventory", "") or "").strip()

    cuidar_do_pet = None
    limpar_a_bolsa_da_fada = None
    if tecla_do_pet:
        def cuidar_do_pet() -> None:
            """Invoca o pet se ele não estiver de pé."""
            try:
                if memoria.pet_active() is False:
                    log.info("FADA: pet sumiu — invocando.")
                    entrada.key(tecla_do_pet)
            except Exception as exc:
                log.debug("FADA: não deu para conferir o pet (%s).", exc)

        if tecla_da_bolsa:
            def limpar_a_bolsa_da_fada() -> None:
                """A receita é do supervisor -- ver `abrir_a_bolsa_e_apagar`.

                Aqui só se ENGOLE a falha: bolsa cheia é chateação, cura que
                para é o time inteiro morrendo.
                """
                try:
                    sup.abrir_a_bolsa_e_apagar(tecla_da_bolsa)
                except Exception as exc:
                    log.warning("FADA: falha ao limpar a bolsa: %s", exc)
    else:
        log.info("FADA: sem tecla de pet configurada — não cuido de pet nem "
                 "de bolsa (sem pet ela não cata item).")

    # O CONVITE DE TIME, A MESMA PEÇA DO MODO APP -- 19/09/2026.
    #
    # `aceitador_do_seguidor` não sabe o que é macro: monta um `InviteAcceptor`
    # com `exigir_caixa=True` para esta conta e devolve (aceitar, fechar). Aqui
    # ela vale pelo mesmo motivo que lá: `rodar()` fica horas dentro do laço, e
    # o aceitador do supervisor só roda quando esse laço termina -- a Fada
    # esperava para sempre por um convite que nunca clicaria.
    #
    # SÓ NO LAÇO PRÓPRIO. Com `so_montar` quem gira é o laço da HH, que já
    # aceita convite por conta dele -- e é ele o dono do que for aberto aqui.
    atender_convite = fechar_o_aceitador = None
    if not so_montar:
        atender_convite, fechar_o_aceitador = aceitador_do_seguidor(sup)

        # A ÂNCORA DO TIME -- 22/09/2026. A Fada é quem mais sofre com o ponto
        # individual: ela não persegue ninguém, fica parada curando, e o alcance
        # da cura é o que define se o time vive. Ancorada dois passos ao lado do
        # líder, ela passa o farm inteiro dois passos fora do alcance.
        #
        # SEMEAR ANTES DO LAÇO é o que faz isto funcionar: `voltar_ao_ponto`
        # guarda a posição ATUAL dela na primeira chamada em que o ponto ainda é
        # `None`. Com o ponto do líder já posto, aquela captura não acontece.
        ancora = ancora_do_lider(sup)
        if ancora is not None:
            ponto_inicial[0] = ancora
            log.info("FADA: ponto inicial veio do líder %s — é para lá que eu "
                     "volto se me arrastarem.", ancora)

    fada = FadaDoTime(
        log=log,
        meu_login=sup.account.login,
        meu_nick=lambda: _seguro(memoria.char_name),
        vida_pct=lambda: _seguro(memoria.vida_pct),
        mana_pct=lambda: _seguro(memoria.mana_pct),
        em_batalha=lambda: _seguro(memoria.in_battle),
        esta_sentado=lambda: _seguro(memoria.is_sitting),
        companheiros=lambda: _seguro(memoria.companheiros_de_time),
        vida_do_time=lambda: _seguro(memoria.vida_do_time),
        id_do_alvo=lambda: _seguro(memoria.id_do_alvo),
        clicar_no_retrato=clicar_no_retrato,
        apertar_cura=lambda: entrada.key(teclas.heal_skill),
        # SEM TECLA, SEM REVIVER: `None` faz a Fada avisar uma vez e seguir
        # curando -- os mortos se reviverm sozinhos no prazo deles.
        apertar_reviver=((lambda: entrada.key(teclas.revive_skill))
                         if (teclas.revive_skill or "").strip() else None),
        apertar_sentar=lambda: entrada.key(teclas.sit),
        auto_selecionar=lambda: entrada.key(teclas.self_target),
        mural=mural,
        membros_do_time=sup._membros_do_time,
        nick_de=sup._nick_do_login,
        continuar=lambda: (
            not sup.stop_event.is_set()
            and sup._sou_a_fada()
            and bool(win32gui.IsWindow(sup.hwnd))
        ),
        dormir=dormir,
        # AS DUAS BARRAS SÃO DO LÍDER quando há time -- é o que faz o time
        # inteiro se comportar igual. `_dono_da_macro` já responde isso.
        pedir_pct=lambda: float(sup._dono_da_macro().settings.app.cura_pedir_pct),
        parar_pct=lambda: float(sup._dono_da_macro().settings.app.cura_parar_pct),
        cuidar_do_pet=cuidar_do_pet,
        limpar_a_bolsa=limpar_a_bolsa_da_fada,
        voltar_ao_ponto=voltar_ao_ponto,
        atender_convite=atender_convite,
    )

    # O PRÓPRIO ID, PUBLICADO ANTES DE COMEÇAR. É o que permite a QUALQUER
    # Fada confirmar um clique nesta conta -- e a Fada também é alvo de si
    # mesma na auto-cura.
    sup._publicar_o_proprio_id(memoria, entrada, log)

    # SÓ MONTAR: quem pediu vai chamar `_uma_volta` dentro do laço dele.
    # A memória fica aberta de propósito -- é ela que a Fada lê a cada giro,
    # e quem chamou é dono do ciclo de vida dela.
    if so_montar:
        return fada

    try:
        fada.rodar()
    finally:
        if fechar_o_aceitador is not None:
            try:
                fechar_o_aceitador()
            except Exception:
                pass
        try:
            memoria.close()
        except Exception:
            pass

    # A QUEDA DA FADA É QUEDA COMO QUALQUER OUTRA -- 04/09/2026.
    #
    # Até esta data a Fada era o ÚNICO modo que não percebia a própria queda:
    # `rodar()` termina sozinho quando o `continuar` vê a janela morta, e o
    # `_operate` só chamava tudo de novo -- sem relogin, sem Histórico. Relato
    # do usuário: *"se a fada cai, muitas vezes o bot não reconhece"*. É a mesma
    # linha que `_rodar_modo_app` tem desde 18/08/2026. Porquê em
    # `docs/decisoes/fada.md`.
    if not win32gui.IsWindow(sup.hwnd):
        raise Disconnected("janela do cliente fechada durante o modo Fada")
    if not app.fada:
        sup._status("Fada desligada")
    return None
