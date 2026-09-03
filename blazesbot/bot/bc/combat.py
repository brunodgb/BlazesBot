"""O ROTEIRO de combate da Bewitcher Cave: as fases, os nomes, o boss.

=========================================================================
O QUE ESTA CLASSE ACRESCENTA AO MOTOR
=========================================================================

`CombatEngine` (em `bot/combate.py`) sabe LUTAR: rotação de ataque, TAB
confirmado, esperar a flag de combate baixar, curar, sentar para recuperar,
pet, buffs. Ele não sabe de cave nenhuma, e é por isso que a HH usa o mesmo.

`CombateBC` acrescenta o ROTEIRO desta cave -- que fases existem, em que ordem,
com que nomes:

  * a FASE DOS GUARDAS, quatro `Gun Witch` no waypoint, com a trava do
    `Cemetery Guard`: puxá-lo tira a run da rota. No motor isso virou o conceito
    geral de ALVO PROIBIDO, e aqui só se diz qual é o nome.
  * a FASE DO BOSS, que tem duas partes -- o `Blaze Skull Marshal` não zera:
    some por volta de 7%, a struct é liberada e nasce outro, agora nível 51, que
    é o que morre de verdade.
  * a cura antes do boss e entre as fases.

A HH tem quatro bosses em sequência e nenhuma dessas coisas. É por isso que o
roteiro fica aqui e o motor não.

**A CLASSE CONTINUA SE CHAMANDO `CombatEngine` PARA QUEM IMPORTA DAQUI.** A
rotina da BC constrói `CombatEngine(ctx, nav)` em vários lugares e os testes
também; trocar o nome deles seria mexer em código estável para nenhum ganho.
`CombateBC` é o nome real, e `CombatEngine` é o apelido que este módulo exporta.
"""
from __future__ import annotations

from ...core import vision
from ...core.vision import capture_window, find_template

# O MOTOR ENTRA COMO MÓDULO, NÃO POR VALOR -- e isso é correção, não estilo.
#
# `from ..combate import combate.USAR_IMAGEM_DA_FASE_2` copia o valor no momento do
# import. Trocar o interruptor no motor depois disso não chega aqui, e o
# roteiro segue rodando com a cópia -- em silêncio. Foi o que aconteceu:
# `test_desligado_nao_le_a_tela` desligou a leitura no motor e o roteiro leu a
# tela assim mesmo.
#
# Qualificando por módulo (`combate.USAR_IMAGEM_DA_FASE_2`) existe UM valor, e é
# o do motor. Vale para todo interruptor -- eles são feitos para ser trocados.
from .. import combate
from ..combate import CombatEngine as _Motor
from ..combate import FimDeCombate

NOME_DOS_GUARDAS = "Gun Witch"
NOME_DO_BOSS = "Blaze Skull Marshal"
# O ÚNICO nome que faz o bot parar de bater no waypoint dos guardas. Ver
# `SO_O_ALVO_PROIBIDO_PARA_O_GOLPE`. Está no censo acima com 5
# structs e nome INLINE -- é das entidades mais legíveis do covil, e por isso a
# memória serve de trava tão bem quanto o `cemetery_guard.png` da tela, sem
# pagar captura.
NOME_DO_CEMETERY_GUARD = "Cemetery Guard"


class CombateBC(_Motor):
    """O motor de `bot/combate.py` mais o roteiro desta cave."""

    NOME_DO_ALVO_PROIBIDO = NOME_DO_CEMETERY_GUARD

    def _esta_fora_da_cave(self) -> bool:
        """A caixa da Bewitcher Cave responde. Ver o motor para o padrão."""
        from . import mapa_bc

        return mapa_bc.posicao_esta_fora_da_cave(
            self.ctx.memory.position())

    def _registrar_troca_de_fase(self, esperado: str) -> None:
        """A troca de struct do boss: o LOG, e a bandeira da segunda fase.

        O NOME DESTE MÉTODO MENTIA ATÉ 19/08/2026, e a mentira custou uma
        entrega. Ele dizia "Só LOG: não decide nada, e é de propósito" -- e é
        aqui, e só aqui, que a passagem para a fase 2 é percebida no caminho que
        RODA. `fight_boss`, que contava `fases_vistas` e parecia o lugar certo,
        está DESATIVADO (a chamada dele em `routine.py` é comentário); quem luta
        de verdade é `fase_do_boss_por_combate`, que chega aqui.

        Não decide nada, e é de propósito. O boss tem duas fases e a primeira
        NÃO chega a zerar -- medido: ela some por volta de 7%, a struct é
        liberada (foi reaproveitada por um `Fireball` de nível 1 no teste) e
        nasce outro `Blaze Skull Marshal`, agora nível 51, que é o que morre de
        verdade.

        O bot já lida com isso sem saber: quem encerra a fase é a flag de
        combate, que não baixa na transformação. O log existe para contar a
        história -- sem ele, "o HP do boss subiu de 7 para 11" parece defeito de
        leitura.

        A BANDEIRA SOBE NA MESMA LINHA EM QUE O LOG SAI, e isso é o pedido do
        usuário ao pé da letra: *"é quando roda esse log que trocou para a fase
        2 e deve começar a tentar usar a Skill Break Soul"*. Só aqui é seguro:
        `registrar_troca_de_fase` é passado por UM chamador só
        (`fase_do_boss_por_combate`), então este método nunca roda na luta dos
        guardas -- a Break Soul não tem como vazar para lá.
        """
        ctx = self.ctx
        # A SELEÇÃO MANDA, E O `0x80C` NÃO ENTRA -- corrigido em 20/08/2026.
        #
        # Esta linha era `oponente if oponente is not None else selecao`, ou seja
        # **preferia o `0x80C`**. E três rodadas do `10-DESCOBRIR-ALVO`, cinco
        # contas cada, mediram que `0x80C` é o PET (nível 32, escala 243/243).
        #
        # O endereço do pet é ESTÁVEL, então `atual` ficava constante, caía no
        # `return` abaixo e **a virada de fase nunca era vista pela memória**. E
        # os dois "PRIMEIRA FASE MORTA" que saíram a 1 segundo de luta, no log de
        # 19/08, eram o ponteiro do pet aparecendo e sumindo -- não uma troca de
        # struct do boss.
        #
        # `0x808` está PROVADO como a seleção nas mesmas três rodadas: com o mob
        # na mira ele entrega a struct certa e `+0xBC` lê `'Gun Witch'`. Preferir
        # a seleção é o que faz este método voltar a medir o que ele diz medir.
        # ==================================================================
        # AGORA PELO ID DO ALVO -- 25/08/2026
        # ==================================================================
        #
        # Palavras do usuário: *"o ponteiro 0x00D5CB80 sempre muda o valor dele
        # quando mudar de target, então ele é muito confiável; se no waypoint do
        # boss mudar o valor do ponteiro, é porque o boss entrou na segunda
        # fase"*.
        #
        # E faz sentido com o que já estava medido: a primeira fase some por
        # volta de 7%, a struct dela é liberada e nasce OUTRO `Blaze Skull
        # Marshal`. Alvo novo é id novo.
        #
        # NA LUTA DO BOSS O BOT NÃO DÁ TAB (`tabs_ao_morrer=0`), então uma troca
        # de id aqui não tem outra explicação barata. Mesmo assim o sinal da
        # TELA continua ligado ao lado (`_conferir_fase_2_na_tela`, a barra
        # amarela): os dois levantam a MESMA bandeira, que é latch, e o log diz
        # qual chegou primeiro -- é assim que se descobre, com run real, se o
        # ponteiro pode substituir a imagem.
        #
        # Custo: uma leitura de memória, ~1 µs. Nenhuma captura.
        atual = self._target_hybrid.id_do_alvo(ctx.pid)
        if atual in (0, None):
            return
        anterior = self._struct_do_alvo
        self._struct_do_alvo = atual
        if anterior is None or atual == anterior:
            # A PRIMEIRA leitura não é troca -- é a aquisição do alvo. Sem esta
            # guarda a fase 2 seria declarada no primeiro instante da luta.
            return
        ctx.log.info(
            "PRIMEIRA FASE MORTA (pelo ID do alvo): #%s -> #%s. Esperado %r. "
            "Continuo atacando SEM TAB -- a segunda fase pega o alvo sozinha "
            "assim que ataca.",
            anterior, atual, esperado)
        self._marcar_fase(2)

    @staticmethod
    def _offset_do_rotulo(rotulo: str) -> int | None:
        """`"varredura:0x9a4"` ou `"0x808"` -> o inteiro. `None` se não der."""
        try:
            return int(rotulo.removeprefix(combate.PREFIXO_DA_VARREDURA), 16)
        except ValueError:
            return None

    def _conferir_fase_2_na_tela(self) -> None:
        """A barra amarela na tela levanta a bandeira da fase 2.

        SÓ ENQUANTO A BANDEIRA ESTÁ BAIXA -- é a saída antecipada da primeira
        linha, e ela é o que torna o custo aceitável. Depois de levantada não há
        mais nada a descobrir, então a captura e o casamento param de acontecer.

        SÓ NA LUTA DO BOSS. Quem chama já está dentro do `if
        registrar_troca_de_fase`, o mesmo portão do sinal por struct e passado por
        um único chamador (`fase_do_boss_por_combate`). Ler isto na luta dos
        guardas seria dar à Break Soul um caminho para vazar para lá, que é o
        defeito inteiro que `combate.USAR_BREAK_SOUL_SO_NA_FASE_2` existe para fechar.

        COMPLEMENTO: qualquer falha aqui é engolida. A leitura é um SEGUNDO sinal
        de uma bandeira que já tem outro; derrubar a luta do boss por causa de uma
        captura ruim trocaria uma skill a menos por uma run perdida.
        """
        if not combate.USAR_IMAGEM_DA_FASE_2 or self._na_segunda_fase_do_boss:
            return
        try:
            quadro = vision.capture_window(self.ctx.hwnd)
            if quadro is None or vision.frame_is_blank(quadro):
                return
            # `load_color`, não `load`: em cinza a fase 1 casa a 0,874.
            modelo = self.ctx.templates.load_color(combate.TEMPLATE_FASE_2_DO_BOSS)
            if vision.boss_na_segunda_fase(quadro, modelo) is not True:
                return
        except Exception as exc:
            self.ctx.log.debug(
                "Não deu para conferir a fase 2 na tela: %s", exc)
            return
        self.ctx.log.info(
            "SEGUNDA FASE VISTA NA TELA: a barra amarela apareceu no quadro do "
            "alvo. É a primeira das duas vidas da fase 2.")
        self._marcar_fase(2)

    def fase_dos_guardas_por_combate(self) -> FimDeCombate:
        """FASE 1 -- escolhe o caminho pelo interruptor do experimento.

        Ver `combate.USAR_TAB_NOS_GUARDAS`, no topo do arquivo. Os dois caminhos vivem
        lado a lado de propósito: o antigo está intacto e voltar é trocar uma
        palavra.
        """
        if combate.USAR_TAB_NOS_GUARDAS:
            return self._fase_dos_guardas_com_tab()
        return self._fase_dos_guardas_sem_tab()

    def _fase_dos_guardas_com_tab(self) -> FimDeCombate:
        """FASE 1 -- troca de alvo por TAB, olhando a barra de vida na tela.

        O que muda em relação ao caminho de sempre:

          * quando a barra de vida do alvo zera (ou o quadro some), o bot dá TAB
            e passa para o mob seguinte, em vez de esperar o jogo trocar
            sozinho. São até `combate.TABS_NOS_GUARDAS` trocas -- 4 mobs, o primeiro
            vira alvo sozinho ao atacar;
          * a fase usa AoE se o usuário tiver configurado. Sem TAB isso não
            fazia sentido; com a troca de alvo, sim -- e classes que acertam
            vários mobs por golpe terminam sem precisar de todas as trocas.
          * após o 2º TAB (e subsequentes), verifica se o Cemetery Guard apareceu
            na tela. Se sim, para de atacar e aguarda a flag de combate baixar
            antes de prosseguir para o próximo waypoint.

        O QUE NÃO MUDA: quem decide o fim da fase continua sendo a FLAG DE
        COMBATE. As trocas são um teto, não uma meta -- sair de combate com um
        ou dois TAB gastos é o desfecho normal de quem bate em área, e a fase
        segue para o boss do mesmo jeito.
        """
        ctx = self.ctx
        ctx.log.info(
            "FASE 1 (guardas) COM TAB: até %s trocas de alvo, pela barra de "
            "vida na tela. AoE conforme a configuração.", combate.TABS_NOS_GUARDAS)

        # Carrega o template do Cemetery Guard para verificação pós-TAB
        cemetery_guard_template = ctx.templates.load("cemetery_guard.png")

        def _verificar_cemetery_guard(tabs_dados: int) -> bool:
            """Verifica se o Cemetery Guard está na tela após o 1º TAB.

            Se encontrado, seta a flag para parar de atacar, aperta ESC uma vez,
            e retorna False para NÃO encerrar a fase imediatamente - espera sair de combate.
            """
            # Só verifica a partir do 1º TAB (após matar o 1º Gun Witch e dar TAB)
            if tabs_dados < 1:
                return False
            if cemetery_guard_template is None:
                ctx.log.debug("Template cemetery_guard.png não carregado; pulando verificação")
                return False

            quadro = capture_window(ctx.hwnd)
            if quadro is None:
                ctx.log.debug("Captura de tela falhou; pulando verificação de Cemetery Guard")
                return False

            match = find_template(quadro, cemetery_guard_template, threshold=combate.LIMIAR_CEMETERY_GUARD)
            if match is not None:
                # A MESMA PORTA que o portão de nome usa. O ESC e a flag que
                # segura o golpe moram em `_travar_no_alvo_proibido` -- duas
                # cópias divergiriam em silêncio, e a que ficasse para trás
                # deixaria o bot puxando o guarda por uma das duas fontes.
                self._travar_no_alvo_proibido(
                    f"tela, match em {match}", f"após o TAB {tabs_dados}")
            return False  # Não encerra a fase; deixa a flag de combate decidir

        self._descer_para_lutar("guardas")

        if not self.esperar_entrar_em_combate(
                "guardas", limite=combate.ESPERA_ENTRAR_EM_COMBATE_GUARDAS):
            return FimDeCombate(False, "ninguém atacou no ponto dos guardas",
                                0.0, 0)

        fim = self.atacar_ate_sair_de_combate(
            "guardas", usar_aoe=True, limite=combate.LIMITE_DA_FASE_DOS_GUARDAS,
            # Alvo que não é Gun Witch ENCERRA a fase, na primeira leitura e
            # sem gastar TAB nenhum. Não é falha: os quatro são sempre os
            # primeiros alvos do TAB, então ler outro nome significa que
            # morreram. Bater no que sobrou puxaria mob que não precisava vir e
            # gastaria tempo de run -- foi assim que a run das 11:33 saiu da rota.
            tabs_ao_morrer=combate.TABS_NOS_GUARDAS, alvo_esperado=NOME_DOS_GUARDAS,
            pos_tab_callback=_verificar_cemetery_guard)

        # Resumo da fase: a história inteira numa linha, para o log poder ser
        # lido sem reconstruir o laço.
        vigia = getattr(self, "_vigia_do_alvo", None)
        ctx.log.info(
            "FASE 1 (guardas) encerrada: %s | o alvo chegou a ser visto=%s | "
            "ausências NÃO contadas como morte=%s",
            fim.resumo(),
            getattr(vigia, "ja_tive_alvo", "?"),
            getattr(vigia, "sumicos_sem_alvo", "?"),
        )
        if fim.saiu_de_combate:
            ctx.log.info("FASE 1 concluída em %.0fs (%s golpes); indo direto "
                         "para o boss", fim.segundos, fim.golpes)
        return fim

    def _fase_dos_guardas_sem_tab(self) -> FimDeCombate:
        """FASE 1 -- os quatro Gun Witch, e o descanso de 4 s no fim.

        Sem TAB, sem ponteiro de alvo, sem contar mortes: a fase começa quando a
        flag liga e termina quando ela desliga de forma confirmada. Os quatro mobs
        atacam de qualquer forma ao chegar no ponto, então o combate se inicia sem
        o bot procurar ninguém.

        SEM AoE, seguindo a configuração combinada para os guardas. Vale registrar
        que a razão original ("eles vêm um de cada vez, área não acerta mais
        ninguém") é mais fraca neste fluxo, porque sem o TAB os quatro engajam
        juntos. (O caminho COM TAB, `_fase_dos_guardas_com_tab`, já usa AoE
        conforme a configuração do usuário -- ali ele acelera de verdade, porque
        acertar vários mobs por golpe economiza trocas de alvo.)

        O DESCANSO DE 4 SEGUNDOS SAIU. Ele existia com o raciocínio de que era a
        última chance de recuperar vida e mana de graça antes da luta que decide a
        run. Na prática não recuperou o suficiente para mudar nada, e quatro
        segundos parado por run é tempo que a run não tem. Saindo de combate vai
        direto para o boss.
        """
        ctx = self.ctx
        ctx.log.info("FASE 1 (guardas): aguardando a flag de combate ligar. "
                     "Não vou apertar TAB.")

        self._descer_para_lutar("guardas")

        if not self.esperar_entrar_em_combate(
                "guardas", limite=combate.ESPERA_ENTRAR_EM_COMBATE_GUARDAS):
            return FimDeCombate(False, "ninguém atacou no ponto dos guardas",
                                0.0, 0)

        fim = self.atacar_ate_sair_de_combate(
            "guardas", usar_aoe=False, limite=combate.LIMITE_DA_FASE_DOS_GUARDAS)

        if fim.saiu_de_combate:
            ctx.log.info("FASE 1 concluída em %.0fs (%s golpes); indo direto "
                         "para o boss", fim.segundos, fim.golpes)
        return fim

    def fase_do_boss_por_combate(self) -> FimDeCombate:
        """FASE 2 -- o boss da Bewitcher Cave.

        O RITUAL DA LUTA mora em `CombatEngine.lutar_contra_um_boss` desde
        03/09/2026 e serve as duas caves: desmontar, esperar a flag com prazo
        curto, TAB de aquisição se o boss não vem, conferir morte, golpe durante
        a confirmação de saída, gravar o placar. Todo o conhecimento medido está
        documentado lá.

        O QUE É DESTA CAVE, e é só isto: o boss tem DUAS FASES e mantém o mesmo
        nome nas duas. A transição não tira o personagem do combate, então ela
        deixa de ser um problema a resolver -- era toda a complicação do caminho
        antigo, que precisava distinguir "HP zerou e voltou" de "morreu".

        `registrar_troca_de_fase` é só o LOG e a bandeira da segunda fase. O TAB
        no meio da luta trocava o alvo justamente na virada, e a virada se
        resolve continuando a bater: a fase 2 pega o alvo sozinha assim que
        ataca.
        """
        return self.lutar_contra_um_boss(
            "boss", registrar_troca_de_fase=NOME_DO_BOSS)

    def _curar_antes_da_segunda_fase(self) -> None:
        """Cura antes de encostar na fase seguinte, se a conta pedir.

        A segunda fase começa com o dano cheio, e entrar nela com vida baixa é a
        forma mais comum de perder a run depois de já ter feito todo o trajeto.
        """
        ctx = self.ctx
        state = ctx.snapshot()
        if state.hp_pct is None or state.hp_pct >= ctx.settings.potions.hp_pct:
            return
        ctx.log.info("Curando antes da fase seguinte (vida %.0f%%)", state.hp_pct)
        self.maintain(state, em_luta=True)
        ctx.tick(0.3)

    def _marcar_fase(self, fases_vistas: int) -> None:
        """Levanta a bandeira da segunda fase, e diz no log quando a levanta.

        Existe como método -- em vez de uma atribuição solta -- porque a virada
        de fase é detectada por caminhos INDEPENDENTES, e todos precisam
        levantá-la. Escrever a mesma linha em cada lugar é o convite para
        consertar um e esquecer os outros.

        Hoje são dois vivos:

        * `_registrar_troca_de_fase` -- a troca de struct do boss, por MEMÓRIA;
        * `_conferir_fase_2_na_tela` -- a barra amarela, por TELA.

        E é IDEMPOTENTE de propósito: `self._na_segunda_fase_do_boss` na guarda
        faz o segundo a chegar não repetir o log. A bandeira é LATCH -- este
        método é o ÚNICO que a levanta, e nada aqui a baixa; quem a baixa é o
        começo de cada luta, em `atacar_ate_sair_de_combate`.
        """
        if fases_vistas < 2 or self._na_segunda_fase_do_boss:
            return
        self._na_segunda_fase_do_boss = True
        if self.ctx.settings.keys.break_soul and combate.USAR_BREAK_SOUL_SO_NA_FASE_2:
            self.ctx.log.info(
                "Segunda fase: a Break Soul entra na rotação a partir de agora")

    # `curar_antes_do_boss` mora em `bot/combate.py` desde 03/09/2026: "quando e
    # como se curar" é conhecimento do JOGO, e as duas caves precisam do mesmo.
    #
    # O que continua sendo da BC é o MOMENTO de chamar -- `_do_guardas`, depois
    # de sair de batalha e antes de encostar no boss.




# O nome pelo qual a rotina e os testes da BC já conhecem a peça.
CombatEngine = CombateBC
