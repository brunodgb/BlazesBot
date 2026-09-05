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

from ..core.coords import coords_for_window
from ..core.memory import Memory


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

    log = logging.getLogger(f"blazes.{sup.account.login}")
    teclas = sup.account.settings.keys
    app = sup.account.settings.app

    try:
        memoria = Memory(sup.pid)
    except Exception as exc:
        log.warning("FADA: não consegui abrir a memória (%s). Sem ela a "
                    "Fada não age.", exc)
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
        try:
            memoria.close()
        except Exception:
            pass
    if not app.fada:
        sup._status("Fada desligada")
    return None
