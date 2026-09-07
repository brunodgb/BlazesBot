"""O CICLO DA MORTE — o que uma conta faz entre cair e voltar a farmar.

Até 04/09/2026 o APP não tinha nenhum: `Personagem morto detectado` e
`Revivendo` só existiam no BC (`bot/bc/routine.py`). No APP, morrer significava a
macro seguir apertando tecla contra um cadáver até alguém notar — e no log de
7 h de duas contas de APP não há UM evento de morte, não porque não morreram,
mas porque ninguém perguntava.

MORA NO `bot/`, E NÃO NO `bot/app/`, porque os dois lados precisam dele: a conta
que roda macro e a própria Fada, que também morre e também é do `bot/`. Nada
aqui sabe que ecossistema existe — tudo chega injetado, como na `FadaDoTime`.

=======================================================================
A ORDEM, E O PORQUÊ DE CADA PRAZO (decisões do usuário em 04/09/2026)
=======================================================================

1. **Avisa o time e espera a Fada, no máximo um minuto.**
   *"Não dá para esperar a Fada, pelo menos não mais que 5 minutos, pois aí o
   jogo revive ele sozinho; o ideal é esperar no máximo 1 minuto."* O jogo tem
   um prazo próprio (~5 min) até reviver por conta dele; um minuto deixa margem
   larga e não deixa a conta parada à toa.

2. **Se a Fada começar a conjurar, o prazo estica.**
   A skill tem **5 s de preparo**. Sem esticar, dá para ela começar aos 58 s e a
   vítima se auto-reviver aos 60, no meio do feitiço: 1168 de mana jogados fora
   e uma janela de convite aparecendo para quem já está vivo.

3. **Vencido o prazo (ou sem Fada no time), ele mesmo revive.**
   O "Ok" do jogo revive NA HORA, perto de onde caiu, com mais perda de Exp —
   e é essa perda que compra o resto da noite farmando.

4. **Antes de andar, senta e regenera.** Revivido pela Fada ele ganha vida
   junto; revivido sozinho, não. Atravessar o spot fraco é a definição do que a
   coleira dos 12 existe para evitar. Com mob em cima ele anda mesmo assim:
   parado ali é pior.

5. **Volta ao ponto inicial.** Quem caminha é o `Navigator` (mapa-múndi e
   minimapa), injetado — o APP não tem waypoints, então o destino é o ponto
   inicial e a referência é a posição atual.

6. **Três mortes seguidas sem conseguir voltar param a conta.** Sem esse
   contador, um spot que virou armadilha vira um moedor de tentativas a noite
   toda.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from ..core import diagnostico_fino

# Quanto o morto espera pela Fada antes de se reviver sozinho.
PRAZO_PARA_A_FADA = 60.0

# Quanto o prazo estica quando a Fada avisa que COMEÇOU a conjurar.
#
# Os 5 s de preparo da skill mais folga para a janela aparecer e o clique sair.
EXTENSAO_PELO_FEITICO = 15.0

# Passo entre duas perguntas durante a espera. Tudo o que ele pergunta é
# memória ou dicionário do mural; a única coisa cara é o template do convite, e
# ela tem cadência própria.
PASSO_DA_ESPERA = 0.3

# Cadência da conferência do convite da Fada na TELA.
#
# É a única leitura de imagem deste ciclo, e ela existe porque as duas janelas
# ("aceita ser revivido?" e a de morte) ficam a 133 px uma da outra: clicar no
# lugar errado manda o personagem para o ponto de nascimento. Meio segundo é
# muito mais rápido que os 5 s de preparo da skill.
CADENCIA_DO_CONVITE = 0.5

# Quanto se espera o `hp` subir depois de um clique que deveria reviver.
TETO_PARA_O_REVIVE_PEGAR = 10.0

# Teto da regeneração sentada antes de andar de volta.
#
# Sentar acelera a regeneração, mas ela continua lenta: sem teto, uma conta
# revivida com 5% ficaria sentada meia hora. Um minuto devolve o suficiente para
# atravessar o spot, que é tudo o que se quer aqui.
TETO_DA_REGENERACAO = 60.0

# Teto da caminhada de volta ao ponto inicial.
#
# O `Navigator` tem o teto dele (180 s x `time_factor`), mas ele é para a rota
# da BC. Aqui o número é o desta viagem: se em três minutos o personagem não
# chegou, alguma coisa está errada -- e insistir custa mais que contar a falha
# e deixar a volta seguinte tentar de novo.
TETO_DO_RETORNO = 180.0

# Mortes seguidas SEM conseguir voltar ao ponto antes de parar a conta.
MORTES_SEGUIDAS_PARA_PARAR = 3


class CicloDaMorte:
    """Resolve uma morte, do aviso ao personagem de volta no ponto."""

    def __init__(
        self,
        *,
        log,
        meu_login: str,
        mural,
        vida_pct: Callable[[], float | None],
        em_batalha: Callable[[], bool | None],
        esta_sentado: Callable[[], bool | None],
        apertar_sentar: Callable[[], None],
        fada_do_time: Callable[[], str | None],
        sou_a_fada: Callable[[], bool],
        convite_na_tela: Callable[[], bool | None],
        clicar_no_convite: Callable[[], None],
        clicar_no_ok_da_morte: Callable[[], None],
        voltar_ao_ponto: Callable[[], bool],
        # SÓ DIAGNÓSTICO: onde o personagem está e a que distância do ponto.
        # `None` nos dois é aceitável -- o log diz "?" e o ciclo não muda.
        onde_estou: Callable[[], object] | None = None,
        quao_longe: Callable[[], object] | None = None,
        # SÓ DIAGNÓSTICO: quem estava por perto na hora da morte.
        vizinhanca: Callable[[], str] | None = None,
        parar_pct: Callable[[], float],
        continuar: Callable[[], bool],
        dormir: Callable[[float], bool],
        nick: Callable[[], str | None] | None = None,
    ) -> None:
        self.log = log
        self.meu_login = meu_login
        self.mural = mural
        self._vida_pct = vida_pct
        self._em_batalha = em_batalha
        self._esta_sentado = esta_sentado
        self._apertar_sentar = apertar_sentar
        self._fada_do_time = fada_do_time
        self._sou_a_fada = sou_a_fada
        self._convite_na_tela = convite_na_tela
        self._clicar_no_convite = clicar_no_convite
        self._clicar_no_ok_da_morte = clicar_no_ok_da_morte
        self._voltar_ao_ponto = voltar_ao_ponto
        self.__onde_estou = onde_estou
        self.__quao_longe = quao_longe
        self.__vizinhanca = vizinhanca
        self._parar_pct = parar_pct
        self._continuar = continuar
        self._dormir = dormir
        self._nick = nick
        # Mortes SEGUIDAS sem conseguir voltar ao ponto. Zera assim que uma
        # volta dá certo -- é "seguidas", não "no total".
        self.mortes_sem_voltar = 0
        self.mortes = 0

    # -- a pergunta --------------------------------------------------------

    def estou_morto(self) -> bool:
        """`hp == 0` em DUAS leituras seguidas. `None` é NÃO.

        Cego não declara morte: sem leitura, dizer que morreu pararia a macro de
        uma conta viva -- o oposto do que este arquivo existe para consertar.

        E UMA LEITURA NÃO BASTA, apontado pelo council em 07/09/2026: `hp == 0`
        aparece transitoriamente em troca de mapa, em tela de carregamento, no
        respawn e em leitura de ponteiro inconsistente. A segunda amostra custa
        microssegundos e é o que separa "morreu" de "pisquei". Duas leituras
        seguidas de zero num personagem vivo exigiriam duas falhas no mesmo
        instante -- e aí o problema já não é este arquivo.
        """
        primeira = self._ler_vida()
        if primeira is None or primeira > 0.0:
            return False
        segunda = self._ler_vida()
        return segunda is not None and segunda <= 0.0

    def _ler_vida(self) -> float | None:
        try:
            return self._vida_pct()
        except Exception:
            return None

    # -- o ciclo -----------------------------------------------------------

    def resolver(self) -> bool:
        """Do aviso ao personagem de volta no ponto. `False` = pare a conta."""
        self.mortes += 1
        self.log.warning("MORRI. A macro para aqui — avisando o time.")
        # ONDE e COM QUEM. É o que separa "morri no meu spot com dois adds" de
        # "morri longe, arrastado" -- e sem isso a única pista de uma morte é a
        # hora em que ela apareceu no log.
        diagnostico_fino.anotar(
            self.log, "MORTE #%d | posição=%s | em batalha=%s | "
            "distância do ponto=%s",
            self.mortes, self._onde_estou(),
            self._na_briga(), self._quao_longe())
        diagnostico_fino.anotar(self.log, "MORTE #%d | %s",
                                self.mortes, self._quem_estava_em_cima())
        self.mural.morri(self.meu_login, nick=self._meu_nick())
        try:
            revivido_pela_fada = self._esperar_a_fada()
            if not self._continuar():
                return True
            if not revivido_pela_fada and not self._reviver_sozinho():
                # Nem a Fada nem o Ok do jogo puseram este personagem de pé.
                # Contar como "morte sem voltar" é o que impede a conta de
                # ficar tentando reviver a noite toda.
                return self._contar_a_falha()
            self._regenerar_antes_de_andar()
            comeco = time.monotonic()
            longe_antes = self._quao_longe()
            voltou = self._voltar_ao_ponto()
            diagnostico_fino.anotar(
                self.log, "RETORNO %s em %.0fs | distância antes=%s depois=%s",
                "ok" if voltou else "FALHOU", time.monotonic() - comeco,
                longe_antes, self._quao_longe())
            if not voltou:
                self.log.warning("Não consegui voltar ao ponto inicial depois "
                                 "de reviver.")
                return self._contar_a_falha()
        finally:
            self.mural.esquecer_morte(self.meu_login)
        self.mortes_sem_voltar = 0
        self.log.info("De pé e de volta ao ponto — a macro recomeça.")
        return True

    def _na_briga(self):
        """A flag de combate, PROTEGIDA. `"?"` quando a leitura falha.

        LEITURA DE MEMÓRIA EXPLODE -- o processo do jogo morre, o handle fecha,
        o endereço sai do lugar. Em qualquer outro estado isso é aceitável;
        aqui, não: uma exceção no meio do ciclo da morte interrompe a
        recuperação e deixa o personagem no chão. Achado do Codex em
        06/09/2026, ampliado -- ele viu o caso do diagnóstico, e o mesmo padrão
        estava em `_regenerar_antes_de_andar`.

        `"?"` nunca é `True` nem `False`, então todo `is True` / `is not True`
        deste arquivo continua respondendo o que respondia com `None`.
        """
        return self._seguro(self._em_batalha)

    def _sentado(self):
        """`esta_sentado`, protegido pelo mesmo motivo de `_na_briga`."""
        return self._seguro(self._esta_sentado)

    def _quem_estava_em_cima(self) -> str:
        """Os mobs vivos em volta no instante da morte -- a pergunta que fecha
        "morri por causa do spot?".

        É a diferença entre *"morri com um mob só, então é dano ou cura"* e
        *"morri com quatro em cima, então é o spot ou a corrida"* -- e sem ela a
        única pista de uma morte era a hora em que ela apareceu no log.
        """
        if self.__vizinhanca is None:
            return "vizinhança=?"
        try:
            return self.__vizinhanca()
        except Exception as exc:
            return f"vizinhança=? ({exc})"

    def _onde_estou(self):
        return self._seguro(self.__onde_estou)

    def _quao_longe(self):
        return self._seguro(self.__quao_longe)

    @staticmethod
    def _seguro(fn):
        """Diagnóstico NUNCA derruba o ciclo: sem função ou com erro, é "?"."""
        if fn is None:
            return "?"
        try:
            return fn()
        except Exception:
            return "?"

    def _contar_a_falha(self) -> bool:
        self.mortes_sem_voltar += 1
        if self.mortes_sem_voltar < MORTES_SEGUIDAS_PARA_PARAR:
            return True
        self.log.error(
            "%d mortes seguidas sem conseguir voltar ao ponto — PARO esta "
            "conta. O spot virou armadilha, ou o ponto inicial está errado.",
            self.mortes_sem_voltar)
        return False

    def _meu_nick(self) -> str:
        if self._nick is None:
            return ""
        try:
            return (self._nick() or "").strip()
        except Exception:
            return ""

    # -- 1) a Fada ---------------------------------------------------------

    def _esperar_a_fada(self) -> bool:
        """Espera a Fada reviver. `True` = ela reviveu; `False` = revive você.

        NÃO ESPERA QUEM NÃO EXISTE: sem Fada no time, ou sendo eu a própria
        Fada, o prazo não faz sentido nenhum -- ninguém vem. Decisão do usuário:
        *"caso não tenha fada, revive na hora, não faz sentido esperar"*.
        """
        fada = self._fada_do_time() if not self._sou_a_fada() else None
        if not fada:
            self.log.info("Sem Fada no time — revivo na hora.")
            return False

        vence_em = time.monotonic() + PRAZO_PARA_A_FADA
        proximo_olhar = 0.0
        esticado = False
        while self._continuar():
            agora = time.monotonic()
            if self.estou_morto() is False:
                # De pé sem eu ter clicado em nada: alguém reviveu por fora.
                self.log.info("Voltei à vida sem clicar — a Fada resolveu.")
                self._de_pe()
                return True

            if agora >= proximo_olhar:
                proximo_olhar = agora + CADENCIA_DO_CONVITE
                if self._convite_na_tela() is True and self._aceitar_o_convite():
                    return True

            if not esticado and self.mural.fada_conjurando_em(self.meu_login):
                # ELA COMEÇOU O FEITIÇO: esticar o prazo é o que impede a
                # auto-revivência no meio dos 5 s de preparo -- que jogaria a
                # mana dela fora e faria a janela de convite aparecer para um
                # personagem já vivo.
                esticado = True
                vence_em = agora + EXTENSAO_PELO_FEITICO
                self.log.info("A Fada %s começou a conjurar — espero mais %.0fs.",
                              fada, EXTENSAO_PELO_FEITICO)

            if agora >= vence_em:
                self.log.warning("A Fada %s não me reviveu no prazo — revivo "
                                 "sozinho.", fada)
                return False
            if not self._dormir(PASSO_DA_ESPERA):
                return False
        return False

    def _aceitar_o_convite(self) -> bool:
        """Clica o "Ok" do convite e confirma pela VIDA que ele pegou."""
        self.log.info("Convite da Fada na tela — aceito.")
        self._clicar_no_convite()
        return self._esperar_ficar_de_pe("o convite da Fada")

    # -- 2) reviver sozinho ------------------------------------------------

    def _reviver_sozinho(self) -> bool:
        """O "Ok" do jogo: revive na hora, perto de onde caiu, custando Exp."""
        self.log.info("Clicando no Ok da morte — revivo onde estou.")
        self._clicar_no_ok_da_morte()
        return self._esperar_ficar_de_pe("o Ok da morte")

    def _de_pe(self) -> None:
        """SAI DA FILA DOS MORTOS NA HORA em que fica de pé.

        Na hora, e não no fim do ciclo: quem espera esta notícia é a FADA, que
        usa a fila para saber se o feitiço dela pegou. Deixar para o `finally`
        faria ela esperar a caminhada de volta inteira antes de atender o
        próximo -- e o teto dela venceria antes.
        """
        self.mural.esquecer_morte(self.meu_login)

    def _esperar_ficar_de_pe(self, o_que: str) -> bool:
        """Confirma pela MEMÓRIA que o clique reviveu. `False` = não pegou.

        Pela memória e não pela tela: `hp > 0` é a definição de estar vivo, e é
        a mesma leitura que declarou a morte.
        """
        fim = time.monotonic() + TETO_PARA_O_REVIVE_PEGAR
        while time.monotonic() < fim and self._continuar():
            if not self.estou_morto():
                self.log.info("De pé.")
                self._de_pe()
                return True
            if not self._dormir(PASSO_DA_ESPERA):
                return False
        self.log.warning("%s não me pôs de pé em %.0fs.", o_que,
                         TETO_PARA_O_REVIVE_PEGAR)
        return False

    # -- 3) regenerar antes de andar ---------------------------------------

    def _regenerar_antes_de_andar(self) -> None:
        """Senta e espera a vida chegar ao alvo, com teto.

        COM MOB EM CIMA NÃO SE SENTA: parado ali é pior que andar fraco, e é o
        único caso em que a travessia começa na hora.

        SENTAR SÓ SE NÃO ESTIVER SENTADO -- a tecla é interruptor, e apertá-la
        de novo levantaria. Regra geral do usuário: *"sempre antes de sentar
        verifica se já não está sentado, pois se tiver é só não fazer nada"*.
        """
        if self._na_briga() is True:
            self.log.info("Tem mob em cima — ando assim mesmo.")
            return
        alvo = self._parar_pct()
        vida = self._ler_vida()
        if vida is not None and vida >= alvo:
            return
        if self._sentado() is not True:
            self._apertar_sentar()
        fim = time.monotonic() + TETO_DA_REGENERACAO
        while time.monotonic() < fim and self._continuar():
            if self._na_briga() is True:
                self.log.info("Entrei em batalha regenerando — paro por aqui.")
                break
            vida = self._ler_vida()
            if vida is None or vida >= alvo:
                break
            if not self._dormir(PASSO_DA_ESPERA):
                break
        if self._sentado() is True:
            self._apertar_sentar()


def montar_para_o_app(sup, executor, entrada, *, vida_pct, em_batalha,
                      esta_sentado, tecla_de_sentar: str) -> CicloDaMorte:
    """Monta o ciclo para uma conta em modo APP.

    Mora aqui, e não no supervisor, pela catraca de tamanho -- e fica bem: o
    ciclo e as peças dele são o mesmo assunto. `sup` é o `AccountSupervisor`,
    pelo mesmo motivo de `fada_montagem`: a montagem pergunta a ele coisas que
    só ele sabe (quem é a Fada do time, quem é o dono da macro, qual a janela).
    """
    from . import mural
    from .context import BotContext

    def voltar_ao_ponto() -> bool:
        """Anda de volta ao ponto inicial depois de reviver.

        QUEM CAMINHA É O `Navigator`, o mesmo do BC e da HH: ele escolhe
        mapa-múndi para longe e minimapa para perto, sabe destravar quem encostou
        em pedra e sabe refazer o clique com desvio. Escrever caminhada nova aqui
        seria a terceira implementação de andar no projeto -- e a única testada
        em horas de campo é essa.

        O APP não tem waypoints: o destino é o ponto inicial e a referência é a
        posição atual, que é exatamente o que o `goto` faz.
        """
        base = executor._base_pos
        if base is None:
            sup.log.warning("Sem ponto inicial salvo — não sei para onde "
                            "voltar. Fico onde nasci.")
            return True
        ctx = BotContext(
            config=sup.config, account=sup.account, pid=sup.pid, hwnd=sup.hwnd,
            stop_event=sup.stop_event, pause_event=sup.pause_event)
        try:
            from .navegacao import Navigator

            # A PÉ, E COM TETO. As duas coisas foram medidas no mesmo
            # defeito de 06/09/2026: sem `exigir_montaria=False` o portão da
            # montaria insiste para sempre (315 tentativas, 33 min parado numa
            # conta que não tem montaria), e sem teto a volta ficaria tentando
            # a noite inteira em vez de contar a falha e deixar o laço seguir.
            return Navigator(ctx, exigir_montaria=False).goto(
                base, max_seconds=TETO_DO_RETORNO)
        except Exception as exc:
            sup.log.warning("Falhei ao voltar para o ponto (%s).", exc)
            return False
        finally:
            ctx.close()

    def clicar_no_convite() -> None:
        ponto = sup.achar_o_convite_de_reviver()
        if ponto is not None:
            entrada.left_click(ponto[0], ponto[1])

    def clicar_no_ok_da_morte() -> None:
        """O "Ok" do diálogo do JOGO -- revive na hora, perto de onde caiu,
        custando mais Exp. É o mesmo ponto que o BC usa desde sempre
        (`coords.revive_ok`), e NÃO o do convite da Fada: os dois ficam a 133 px
        um do outro, e trocá-los tira o personagem do spot.
        """
        from ..core.coords import coords_for_window

        ponto = coords_for_window(sup.hwnd).revive_ok
        entrada.left_click(ponto[0], ponto[1])

    return CicloDaMorte(
        log=sup.log,
        meu_login=sup.account.login,
        mural=mural,
        vida_pct=vida_pct,
        em_batalha=em_batalha,
        esta_sentado=esta_sentado,
        apertar_sentar=lambda: entrada.key(tecla_de_sentar),
        fada_do_time=sup._fada_do_meu_time,
        sou_a_fada=sup._sou_a_fada,
        convite_na_tela=lambda: sup.achar_o_convite_de_reviver() is not None,
        clicar_no_convite=clicar_no_convite,
        clicar_no_ok_da_morte=clicar_no_ok_da_morte,
        voltar_ao_ponto=voltar_ao_ponto,
        # A BARRA É DO LÍDER, como as duas da cura: é o que faz o time inteiro
        # se comportar igual.
        parar_pct=lambda: float(sup._dono_da_macro().settings.app.cura_parar_pct),
        continuar=lambda: not sup.stop_event.is_set(),
        dormir=executor._dormir,
        nick=lambda: (sup.account.last_char_name or "").strip(),
        # DIAGNÓSTICO: as duas perguntas que o log de uma morte precisava e não
        # tinha -- onde ela aconteceu e a que distância do ponto de farm.
        onde_estou=lambda: executor._posicao_atual() if executor._posicao_atual
        else "?",
        quao_longe=executor.distancia_da_base,
        vizinhanca=lambda: _vizinhanca(sup),
    )


def _vizinhanca(sup) -> str:
    """Quem estava por perto, lido no instante da morte.

    ABRE A LEITURA AQUI, E FECHA NA SAÍDA. O `Memory` do modo APP é um local do
    supervisor, e puxá-lo até aqui obrigaria a mexer na montagem inteira por uma
    linha de log. Uma morte por vez, um handle por morte -- e o `finally` garante
    que ele não vaza.

    NUNCA LEVANTA: diagnóstico que derruba o ciclo da morte é pior que
    diagnóstico nenhum.
    """
    from ..core import vizinhanca
    from ..core.memory import Memory

    memoria = None
    try:
        memoria = Memory(sup.pid)
        return vizinhanca.resumo(memoria)
    except Exception as exc:
        return f"vizinhança=? ({exc})"
    finally:
        if memoria is not None:
            try:
                memoria.close()
            except Exception:
                pass
