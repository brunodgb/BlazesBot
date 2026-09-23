"""
Reset do boss por troca de time.

O PROBLEMA

Fazendo a Bewitcher Cave duas vezes seguidas sem mudar de time, o boss NÃO
renasce -- a instância continua com ele morto e a run é perdida. Entrar num time
novo reseta a cave.

QUANDO O TIME É MONTADO

Só ao CHEGAR na coordenada da entrada da cave, imediatamente antes de tentar
entrar. Fazer isso mais cedo era desperdício e risco: o caminho até lá passa por
teleporte e caminhada automática, o convite podia expirar no meio, e mexer na
Block list longe da entrada não adianta nada.

O time é mantido durante TODAS as tentativas de entrada -- a BC é disputada e
uma tentativa pode não pegar -- e só é desfeito depois de confirmar que o
personagem está dentro.

COMO O CONVITE É FEITO

Pelo MENU DE CONTEXTO da entrada na Block list. São três passos:

  1. o nick do reseter é registrado na Block list (`garantir_reseter_registrado`),
     porque é a única aba onde se digita um nome arbitrário e ele passa a existir
     como entrada selecionável, mesmo com o jogador do outro lado do mapa;
  2. clique com o botão DIREITO na linha do nick;
  3. abre um menu de contexto e nele se clica em **Team up**.

NÃO EXISTE CONVITE POR TEXTO NESTE JOGO. O `/invite <nick>` que este arquivo usava
não funciona -- não é um comando do cliente. Toda a construção em volta dele era
elaborada e inútil: fechar as janelas antes de digitar para o texto não cair no
campo de nick, o comentário explicando que o cliente responde "Your invitation
sent out", as duas tentativas. Nada disso enviava convite nenhum, e era a
explicação inteira para "a conta de reset não está funcionando" -- não havia
convite para aceitar.

O menu de contexto acompanha o CURSOR, então "Team up" fica num deslocamento fixo
a partir do ponto onde o botão direito foi clicado, e não numa coordenada absoluta
da tela. Ver `DESLOCAMENTO_TEAM_UP`.

COMO O CONVITE É ACEITO

Pela conta de reset, e sem ler nada da tela. As duas contas rodam NO MESMO
PROCESSO: quem convida ANUNCIA internamente, e quem foi convidado clica no Ok na
coordenada medida (437,335). Isso funciona mesmo quando a captura de imagem está
indisponível -- que é o normal em cliente DirectX fora de primeiro plano, e era
justamente por isso que a conta de reset não clicava em nada.

COMO SE SAI DO TIME

Dois cliques medidos: botão DIREITO no retrato em (44,48), depois "Leave the
team" em (92,97). Comando de chat não serve: o cliente responde "You speak too
fast" e o texto aparece para os outros jogadores. E só depois de ENTRAR na cave:
a instância nova nasce no instante da entrada, e sair do time antes disso
desperdiçaria o reset.
"""
from __future__ import annotations

import time

from ..core import diario
from ..core.coords import BLOCK_ENTRY_REGION, TEMPLATE_ANCHORS
from ..core.vision import (
    LearnedCrops,
    altura_da_mudanca,
    capture_window,
    find_template,
    region_is_uniform,
)
from .context import BotContext

# O MURAL É IMPORTADO POR NOME, e não como módulo. Não é estilo: o
# `tests/test_reset_de_time.py` lê o AST de `InviteAcceptor.check_and_accept` e
# exige que a primeira instrução seja `bater(...)` como NOME NU -- é assim que
# ele prova que a batida sai antes de qualquer outra coisa. `mural.bater(...)`
# vira um `ast.Attribute` e o teste reprova.
from .mural import (
    aceite_pendente,
    anunciar_aceite,
    anunciar_convite,
    bater,
    consumir_aceite,
    consumir_convite,
    convite_pendente,
)

INVITE_TEMPLATE = "state_team_invite.png"          # legado, com nick embutido
INVITE_TEXT_TEMPLATE = "state_team_invite_texto.png"
INVITE_THRESHOLD = 0.80
ANCHOR_THRESHOLD = 0.80
MENU_LEAVE_TEMPLATE = "menu_leave_team.png"

# Painel do companheiro de time, desenhado abaixo do retrato do próprio
# personagem quando alguém está no time (nick, vida e mana dele).
#
# OPCIONAL. Serve de segunda via para "estou em time?", só quando a memória não
# responde -- e sem ele o comportamento é o de antes. Recortar a moldura do painel,
# não o nick: o nick muda de conta para conta, a moldura não.
TEAM_MEMBER_TEMPLATE = "state_team_member.png"

# Semelhança a partir da qual um recorte aprendido é considerado o mesmo texto.
#
# ARMADILHA DE COLISÃO (HOTFIX 21/09/2026): nomes como 'WizzOfBlazes' e
# 'WizzOfBlazes5' diferem apenas num caractere -- na mesma fonte e na mesma
# posição isso representa ~5-8% dos pixels. Com 0.90 ambos casavam com o
# recorte aprendido do mais curto: `score('WizzOfBlazes') >= 0.90` era `True`
# mesmo com 'WizzOfBlazes5' na linha, o sistema concluía "já está registrado"
# e pulava o re-registro -- o convite saía para o nick errado.
#
# 0.97 exige divergência de apenas 3%, o que distingue qualquer par de nicks
# que diferem em ≥1 caractere alfanumérico na fonte do jogo (medido: a
# diferença de um dígito muda ~10% dos pixels no recorte).
SEMELHANCA_MINIMA = 0.97

# Item "Team up" do menu de contexto da entrada na lista.
MENU_TEAM_UP_TEMPLATE = "menu_team_up.png"

# Deslocamento do "Team up" a partir do ponto do CLIQUE DIREITO.
#
# Deslocamento, e não coordenada absoluta: o menu de contexto nasce no cursor, e a
# linha do nick muda de lugar conforme a janela. Amarrar isso a um ponto fixo da
# tela erraria assim que a lista mudasse de posição.
#
# Medido no print do menu aberto sobre a entrada da Block list. Os itens têm passo
# de ~21 px, e QUANTOS itens vêm depende da DISTÂNCIA até o convidado (medido
# pelo usuário em 16/09/2026): perto dele o cliente acrescenta as opções que só
# existem com o personagem à vista, e "Team up" desce três linhas.
#
#     LONGE, 7 itens             PERTO, 12 itens
#     +13  [nick]                +13  [nick]
#     +33  Copy Name             +33  Follow
#     +54  ---------             +54  Copy Name
#     +75  Team up        <--    +75  View Equipment
#     +96  Whisper               +96  ---------
#     +117 Add Foe               +117 Trade
#     +138 Recruit Apprentice    +138 Team up          <--
#                                +159 Duel ... +243 Recruit Apprentice
#
# O BC convida a conta de reset, do outro lado do mapa; o APP convida quem está
# ao lado. Este deslocamento é o do menu CURTO -- no longo ele cai em "View
# Equipment": abre a janela de equipamento e convite nenhum sai.
DESLOCAMENTO_TEAM_UP = (32, 75)

# QUAL DOS DOIS MENUS VEIO se mede na hora, pela ALTURA da caixa que apareceu
# (`altura_da_mudanca`): não existe recorte do menu em disco, e uma caixa opaca
# sobre a cena 3D muda toda linha que cobre. A régua começa 8 px abaixo do
# clique -- dentro do cabeçalho, já opaco -- e acima de 200 px a caixa é o menu
# longo (150 px e 250 px medidos; o limiar fica no meio).
#
# TODO "NÃO SEI" FICA NO CURTO: sem quadro, recorte fora da tela, ou régua que
# bateu no fim sem nunca parar (isso é a cena se mexendo, não menu). Errar para
# o curto é o lado barato -- "View Equipment" abre uma janela que o
# `_fechar_janelas` seguinte fecha. Errar para o longo no menu curto cairia em
# "Recruit Apprentice", um pedido de aprendiz para a outra conta.
LINHAS_A_MAIS_QUANDO_PERTO = 3
ALTURA_DA_LINHA_DO_MENU = 21
INICIO_DA_MEDIDA_DO_MENU = 8
LARGURA_DA_MEDIDA_DO_MENU = 40
ALTURA_MAXIMA_DO_MENU = 300
ALTURA_DO_MENU_LONGO = 200

# Tempo para o menu de contexto aparecer depois do clique direito.
ESPERA_DO_MENU = 0.35

# Quanto esperar a outra conta aceitar. Ela recebe o anúncio interno e clica no
# Ok em ~2 s; 8 s cobre uma volta inteira do laço dela com folga, e esperar mais
# só atrasaria a disputa pela entrada da cave.
ESPERA_PELA_RESPOSTA = 4.0

# De quanto em quanto tempo conferir se o time já formou.
#
# 0,2 s, e não 1 s. A conta de reset aceita de primeira quase sempre, e com o
# passo de um segundo o convite aceito no primeiro instante ainda custava um
# segundo cheio parado na porta da cave. Ler o time é uma leitura de memória --
# conferir cinco vezes por segundo não pesa.
PASSO_DA_ESPERA_DO_TIME = 0.1

# Quantas linhas da lista limpar antes de desistir.
MAX_ENTRADAS = 12


# Quantas vezes clicar no Ok para o MESMO convite anunciado.
#
# Mais de um porque o anúncio chega no instante do envio e a caixa pode levar um
# ou dois segundos para aparecer -- um clique dado antes disso não aceita nada.
# Mas com teto: sem ele, o log real registrou ONZE cliques para um convite já
# aceito no primeiro, porque a parada dependia de `team_size()` responder.
MAX_CLIQUES_DE_ACEITE = 5


class TeamService:
    """Monta e desfaz time para forçar o reset da cave."""

    def __init__(self, ctx: BotContext, nick_do_reset=None) -> None:
        self.ctx = ctx
        # QUEM CONVIDAR, injetado por quem construiu.
        #
        # ERA `ctx.settings.bc.reset_nick` LIDO AQUI DENTRO, e isso deixou a HH
        # sem time: o usuário configurou o campo da HH, o do BC estava vazio, e
        # `montar_time` devolvia False na primeira linha -- a rotina caía em
        # RECUPERAR, em laço, para sempre. Medido em 03/09/2026.
        #
        # OS DOIS CAMPOS VIRARAM UM (`settings.reset_nick`, escopo do
        # personagem) em 08/09/2026, e a injeção continua aqui de propósito:
        # ela é o que permite a uma cave futura ter reseter próprio sem mexer
        # neste arquivo.
        #
        # `None` = o do personagem, que agora é o único que existe.
        self._nick_do_reset = nick_do_reset
        self.aprendidos = LearnedCrops(ctx.templates.folder / "aprendidos")
        # Nick que foi efetivamente registrado na Block list NESTA sessão.
        #
        # HOTFIX 21/09/2026 (colisão de nomes): a verificação visual
        # (`_primeira_entrada_e`) pode retornar True para nicks parecidos, como
        # 'WizzOfBlazes' e 'WizzOfBlazes4', mesmo com SEMELHANCA_MINIMA elevado.
        # Este campo garante que, se o nick solicitado é DIFERENTE do que foi
        # registrado aqui, o cache visual é ignorado e o re-registro é forçado.
        self._nick_registrado_na_blocklist: str | None = None

    def nick_do_reset(self) -> str:
        """O nick da conta que reseta a cave que está rodando."""
        if self._nick_do_reset is not None:
            return str(self._nick_do_reset() or "").strip()
        return self.ctx.settings.reset_nick.strip()

    # -- utilidades --------------------------------------------------------

    def _pontos(self, grupo: str, quadro=None) -> dict[str, tuple[int, int]] | None:
        """Localiza uma janela por imagem e devolve os pontos dela."""
        nome_template, deslocamentos = TEMPLATE_ANCHORS[grupo]
        template = self.ctx.templates.load(nome_template)
        if template is None:
            return None
        if quadro is None:
            quadro = capture_window(self.ctx.hwnd)
        if quadro is None:
            return None
        base = find_template(quadro, template, threshold=ANCHOR_THRESHOLD)
        if base is None:
            return None
        return {n: (base[0] + dx, base[1] + dy)
                for n, (dx, dy) in deslocamentos.items()}

    # NÃO existe `_send_chat`. Ela servia a um só propósito -- mandar
    # `/invite <nick>` -- e esse comando não existe no jogo. Manter um utilitário
    # de chat aqui só convidaria a reinventar o caminho que não funciona. Sair do
    # time também não usa chat, por outro motivo: o cliente responde "You speak
    # too fast" e o texto fica visível para os outros jogadores.

    def team_size(self) -> int | None:
        """Membros no time, pela memória (com o offset correto)."""
        return self.ctx.memory.team_size()

    def _time_pela_imagem(self) -> bool | None:
        """Time formado, olhando o painel de membro no canto da tela.

        Quando o convite é aceito, o cliente desenha a barra do companheiro logo
        abaixo do retrato do próprio personagem -- nick, vida e mana dele. Esse
        painel só existe quando há alguém no time, então reconhecê-lo é
        confirmação direta de que o convite foi aceito.

        É a SEGUNDA via, não a primeira: a memória responde a mesma pergunta com um
        número exato e sem custo de captura. Isto serve para quando a memória não
        responde -- e aí a alternativa era o bot concluir "não entrou no time" e
        reconvidar para sempre, com o companheiro já do lado.

        None quando não há como saber: template ausente ou captura indisponível.
        """
        ctx = self.ctx
        template = ctx.templates.load(TEAM_MEMBER_TEMPLATE)
        if template is None:
            return None
        quadro = capture_window(ctx.hwnd)
        if quadro is None:
            return None
        return find_template(quadro, template,
                             threshold=ANCHOR_THRESHOLD) is not None

    @property
    def estado_do_time(self) -> bool | None:
        """Estou em time? `None` quando NÃO DÁ PARA SABER.

        Existe porque `in_team` achata "não estou" e "não consegui ler" no mesmo
        `False`, e essa confusão custou caro: `sair_do_time` começava com
        `if not self.in_team: return True` e SAÍA SEM CLICAR quando a leitura de
        time falhava. Do lado de fora parecia que as coordenadas estavam erradas;
        na verdade nenhum clique chegava a ser enviado.
        """
        tamanho = self.team_size()
        if tamanho is not None:
            return tamanho > 1
        return self._time_pela_imagem()

    @property
    def in_team(self) -> bool:
        """Estou em time? Memória primeiro, painel de membro como reserva."""
        tamanho = self.team_size()
        if tamanho is not None:
            return tamanho > 1

        # Memória ilegível. Antes esta situação devolvia False direto, o que fazia
        # o bot reconvidar indefinidamente estando já em time.
        pela_imagem = self._time_pela_imagem()
        if pela_imagem is not None:
            self.ctx.log.info(
                "Sem leitura de time na memória; o painel de membro na tela diz "
                "que %s em time", "ESTOU" if pela_imagem else "NÃO estou",
            )
            return pela_imagem
        return False

    @staticmethod
    def _regiao(ponto: tuple[int, int],
                caixa: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        dx, dy, w, h = caixa
        return (ponto[0] + dx, ponto[1] + dy, w, h)

    # -- janela de amigos --------------------------------------------------

    def _abrir_lista(self) -> dict[str, tuple[int, int]] | None:
        """Abre a lista de amigos e vai para a aba Block."""
        ctx = self.ctx
        tecla = ctx.settings.keys.friend_list
        if not tecla:
            ctx.log.warning("Sem tecla de lista de amigos configurada")
            return None

        # Já pode estar na aba Block de uma run anterior.
        pontos = self._pontos("block_list")
        if pontos:
            return pontos

        ctx.press(tecla)
        ctx.tick(0.6)

        pontos = self._pontos("friend_list")
        if pontos:
            ctx.click(pontos["aba_block"])
            ctx.tick(0.45)

        pontos = self._pontos("block_list")
        if pontos is None:
            ctx.log.warning("Não localizei a aba Block da lista de amigos")
        return pontos

    def _fechar_janelas(self, tentativas: int = 3) -> bool:
        """Fecha a caixa de nick e a lista de amigos, CONFIRMANDO que fecharam.

        Chamado DEPOIS de acionar o "Team up": os cliques da entrada da cave vêm
        em seguida e são posicionais na cena 3D, então uma janela de lista aberta
        na frente engole o clique no NPC.

        Confirmar o fechamento por imagem, e não só apertar a tecla, é o que
        distingue "fechei" de "achei que fechei" -- a tecla da lista alterna, e
        apertá-la com a lista já fechada a REABRE.
        """
        ctx = self.ctx
        tecla = ctx.settings.keys.friend_list

        for _ in range(tentativas):
            ctx.raise_if_stopped()
            quadro = capture_window(ctx.hwnd)

            dialogo = self._pontos("block_input", quadro=quadro)
            if dialogo:
                ctx.click(dialogo["cancel"])
                ctx.tick(0.35)
                continue

            lista = (self._pontos("block_list", quadro=quadro)
                     or self._pontos("friend_list", quadro=quadro))
            if lista:
                if tecla:
                    ctx.press(tecla)
                ctx.tick(0.4)
                continue

            if quadro is None:
                # Sem captura não há como confirmar. Fecha às cegas pela tecla e
                # aceita, porque insistir num laço cego não melhora nada.
                if tecla:
                    ctx.press(tecla)
                    ctx.tick(0.3)
                return False
            return True

        ctx.log.warning("A janela de amigos não confirmou fechamento")
        return False

    def _limpar_lista(self, pontos: dict[str, tuple[int, int]]) -> None:
        """Remove todas as entradas da Block list.

        Clica sempre na PRIMEIRA linha: ao remover uma entrada, as de baixo
        sobem. É a mesma lógica da venda -- clicar na mesma posição drena a
        lista inteira sem precisar saber quantas entradas existem.

        Para de remover quando a primeira linha fica lisa, ou seja, quando a
        lista esvaziou. Antes eram sempre 12 passadas, e as sobrando clicavam
        num Remove sem seleção.
        """
        ctx = self.ctx
        ctx.log.info("Limpando a Block list")
        regiao = self._regiao(pontos["primeira_entrada"], BLOCK_ENTRY_REGION)

        for volta in range(MAX_ENTRADAS):
            ctx.raise_if_stopped()
            quadro = capture_window(ctx.hwnd)
            if quadro is not None and region_is_uniform(quadro, regiao):
                if volta:
                    ctx.log.info("Block list vazia depois de %s remoção(ões)", volta)
                return
            ctx.click(pontos["primeira_entrada"])
            ctx.tick(0.15)
            ctx.click(pontos["botao_remove"])
            ctx.tick(0.25)
            # Caixa de confirmação, se houver.
            if ctx.memory.modal_open():
                ctx.click(ctx.coords.confirm_ok)
                ctx.tick(0.2)

    def _adicionar_nick(self, pontos: dict[str, tuple[int, int]], nick: str) -> bool:
        """Adiciona um nick à Block list pelo botão Block.

        No campo vai SÓ O NICK. Nada de comando, nada de prefixo: a caixinha é um
        campo de nome, e qualquer outra coisa ali registra uma entrada inútil.
        """
        ctx = self.ctx
        ctx.log.info("Registrando '%s' na Block list", nick)
        ctx.click(pontos["botao_block"])
        ctx.tick(0.5)

        dialogo = self._pontos("block_input")
        if dialogo is None:
            ctx.log.warning("A caixa de digitar o nick não apareceu")
            return False

        ctx.click(dialogo["campo_nick"])
        ctx.tick(0.2)
        ctx.input.clear_field(24)
        ctx.tick(0.1)
        ctx.input.type_text(nick)
        ctx.tick(0.2)
        ctx.click(dialogo["ok"])
        ctx.tick(0.6)
        return True

    def _primeira_entrada_e(self, pontos: dict[str, tuple[int, int]],
                            nick: str) -> bool | None:
        """A primeira linha da Block list já é este nick?

        True  = é ele, não precisa mexer em nada.
        False = tem outra coisa ali (ou a lista está vazia).
        None  = não foi possível decidir (sem captura, ou nunca aprendi o
                recorte deste nick) -- e aí quem chama refaz o registro, que é a
                ação segura.

        GUARDA DO CACHE DE NICK (HOTFIX 21/09/2026): se o nick solicitado difere
        do que foi registrado nesta sessão (`_nick_registrado_na_blocklist`), a
        função retorna False imediatamente, forçando o re-registro. Isso impede
        que o recorte visual de 'WizzOfBlazes' case com a linha 'WizzOfBlazes5'
        -- mesmo com SEMELHANCA_MINIMA alto, o match visual nunca é acionado
        quando o nick mudou.
        """
        ctx = self.ctx

        # GUARDA PRIMÁRIA: nick diferente do registrado = re-registro obrigatório.
        # Verificação de string exata (case-insensitive) ANTES de qualquer imagem.
        nick_limpo = nick.strip()
        registrado = (self._nick_registrado_na_blocklist or "").strip()
        if registrado.lower() != nick_limpo.lower():
            ctx.log.info(
                "Block list: nick solicitado '%s' difere do registrado '%s'; "
                "forçando re-registro sem usar comparação visual.",
                nick_limpo, registrado or "(nenhum)",
            )
            return False

        regiao = self._regiao(pontos["primeira_entrada"], BLOCK_ENTRY_REGION)
        quadro = capture_window(ctx.hwnd)
        if quadro is None:
            return None

        if region_is_uniform(quadro, regiao):
            ctx.log.info("Block list está vazia")
            return False

        score = self.aprendidos.score(f"block_{nick_limpo}", quadro, regiao)
        if score is None:
            ctx.log.debug("Ainda não conheço o recorte de '%s' na Block list",
                          nick_limpo)
            return None
        confere = score >= SEMELHANCA_MINIMA
        ctx.log.info(
            "Primeira linha da Block list %s '%s' (semelhança %.2f, limiar %.2f)",
            "é" if confere else "NÃO é", nick_limpo, score, SEMELHANCA_MINIMA,
        )
        return confere

    def garantir_reseter_registrado(self, nick: str) -> bool:
        """Deixa a Block list com o nick do reseter na primeira linha.

        Só remove se o que está lá não for ele -- é o que o fluxo pede e o que
        evita mexer numa janela modal sem necessidade.
        """
        ctx = self.ctx
        pontos = self._abrir_lista()
        if pontos is None:
            return False

        ja_esta = self._primeira_entrada_e(pontos, nick)
        if ja_esta is True:
            ctx.log.info("'%s' já está na Block list; nada a remover", nick)
            return True

        if ja_esta is False:
            self._limpar_lista(pontos)
            pontos = self._pontos("block_list") or pontos
        else:
            # Não deu para reconhecer. Limpar e registrar de novo é idempotente e
            # deixa a lista no estado esperado de qualquer maneira.
            self._limpar_lista(pontos)
            pontos = self._pontos("block_list") or pontos

        if not self._adicionar_nick(pontos, nick):
            return False

        # Registra o nick que acabou de ser escrito -- ANTES de aprender a imagem.
        # É este valor que a guarda primária de `_primeira_entrada_e` usa para
        # decidir se o re-registro é obrigatório, por comparação de string exata.
        nick_limpo = nick.strip()
        self._nick_registrado_na_blocklist = nick_limpo

        # Aprende o recorte da linha recém-escrita: é o único momento em que o
        # bot SABE o que está ali, porque acabou de digitar.
        pontos = self._pontos("block_list") or pontos
        regiao = self._regiao(pontos["primeira_entrada"], BLOCK_ENTRY_REGION)
        quadro = capture_window(ctx.hwnd)
        if self.aprendidos.save(f"block_{nick_limpo}", quadro, regiao):
            ctx.log.info(
                "Guardei como '%s' é escrito na Block list — nas próximas runs "
                "eu reconheço e não removo nada", nick_limpo,
            )
        return True

    # -- ciclo de reset ----------------------------------------------------

    def _achar_team_up(
        self, ponto_do_clique: tuple[int, int], antes=None
    ) -> tuple[tuple[int, int], str]:
        """Onde clicar para acionar o "Team up". Devolve (ponto, como achei).

        Imagem primeiro, deslocamento como reserva -- é o mesmo critério do
        "Leave the team": template é mais forte que coordenada, porque não depende
        de o menu ter exatamente os itens que estavam no print.

        O deslocamento não é um só: ele DESCE quando o menu vem longo, que é o
        caso do convidado perto. `antes` é o quadro de ANTES do clique direito, e
        é comparando com o de agora que se mede a caixa -- ver
        `DESLOCAMENTO_TEAM_UP`.
        """
        ctx = self.ctx
        quadro = capture_window(ctx.hwnd)
        template = ctx.templates.load(MENU_TEAM_UP_TEMPLATE)
        if template is not None and quadro is not None:
            achado = find_template(quadro, template, threshold=ANCHOR_THRESHOLD)
            if achado is not None:
                return achado, "template do item"
        x, y = ponto_do_clique
        dx, dy = DESLOCAMENTO_TEAM_UP
        alto = altura_da_mudanca(
            antes, quadro, x + dx, y + INICIO_DA_MEDIDA_DO_MENU,
            LARGURA_DA_MEDIDA_DO_MENU, ALTURA_MAXIMA_DO_MENU)
        if ALTURA_DO_MENU_LONGO <= alto < ALTURA_MAXIMA_DO_MENU:
            dy += LINHAS_A_MAIS_QUANDO_PERTO * ALTURA_DA_LINHA_DO_MENU
            return (x + dx, y + dy), f"menu longo ({alto}px): o convidado está perto"
        return (x + dx, y + dy), f"deslocamento medido (caixa de {alto}px)"

    def _enviar_convite(self, nick: str) -> bool:
        """Envia o convite pelo MENU DE CONTEXTO da entrada na Block list.

        É o ÚNICO caminho -- não existe convite por texto neste jogo.

            1. o nick tem que estar na lista, senão não há linha para clicar
            2. clique DIREITO na linha dele
            3. clique em "Team up" no menu que aparece

        O passo 1 reaproveita exatamente o mesmo reconhecimento que já garantia o
        registro do reseter: a linha é `primeira_entrada` da janela localizada por
        imagem. Ou seja, achar ONDE está o nick não é código novo -- é a mesma
        informação que já era usada para decidir se precisava registrar.
        """
        ctx = self.ctx
        if not self.garantir_reseter_registrado(nick):
            ctx.log.warning(
                "Não consegui deixar '%s' na Block list; sem a linha dele não há "
                "onde clicar com o botão direito", nick,
            )
            return False

        # Relocaliza a janela: o registro pode ter fechado e reaberto coisas. O
        # quadro fica guardado porque ele é o "antes" da régua do menu.
        antes = capture_window(ctx.hwnd)
        pontos = self._pontos("block_list", antes)
        if pontos is None:
            ctx.log.warning(
                "Não localizei a Block list para abrir o menu de '%s'", nick)
            return False

        linha = pontos["primeira_entrada"]
        ctx.log.info("Abrindo o menu de contexto de '%s' na linha %s", nick, linha)
        ctx.right_click(linha)
        ctx.tick(ESPERA_DO_MENU)

        alvo, origem = self._achar_team_up(linha, antes)
        ctx.log.info("Clicando em 'Team up' em %s [%s]", alvo, origem)
        ctx.click(alvo)
        ctx.tick(0.5)

        # Fecha a lista: deixá-la aberta atrapalha os cliques da entrada da cave,
        # que vêm em seguida e são posicionais na cena 3D.
        self._fechar_janelas()
        return True

    def montar_time(self) -> bool:
        """Monta o time com a conta de reset. Chamado NA ENTRADA da cave.

        Campo de nick vazio significa "não usar reset de time" -- não existe um
        interruptor separado, porque ele seria só uma forma de errar.

        =================================================================
        O CONVITE É POR MENU DE CONTEXTO, NÃO POR TEXTO
        =================================================================

        Esta função mandava `/invite <nick>` no chat. Esse comando NÃO EXISTE no
        jogo: nada era enviado, e a espera de oito segundos por uma resposta que
        nunca vinha concluía "não entrou no time" em toda run. Era a explicação
        completa para "a conta de reset não está funcionando".

        O caminho que funciona é clicar: botão direito na linha do nick na Block
        list, e "Team up" no menu que aparece (ver `_enviar_convite`).

        E como as duas contas rodam NESTE MESMO PROCESSO, o convite é ANUNCIADO
        internamente: a conta de reset não precisa ler nick nenhum da tela, ela
        recebe o aviso e clica no Ok.
        """
        ctx = self.ctx
        nick = self.nick_do_reset()
        if not nick:
            return False

        if self.in_team:
            ctx.log.info("Já estou em time (%s membros); não convido de novo",
                         self.team_size())
            return True

        remetente = ctx.char_name or ctx.account.login
        for tentativa in (1, 2):
            ctx.raise_if_stopped()
            ctx.log.info("Convidando '%s' para o time (tentativa %s)",
                         nick, tentativa)
            # Descarta aceite ANTIGO antes de convidar. Sem isto, um aceite que
            # sobrou da run anterior faria esta espera terminar na hora, com o
            # convite novo ainda por aceitar -- e o bot entraria na cave achando
            # que trocou de time.
            consumir_aceite(remetente)
            # Anuncia ANTES de clicar: a outra conta pode ver a caixa no mesmo
            # instante, e um anúncio que chega depois faria ela recusar o convite.
            anunciar_convite(nick, remetente)
            if not self._enviar_convite(nick):
                continue

            # A resposta depende de a outra conta clicar no Ok -- o que ela faz
            # em cerca de dois segundos, porque recebeu o anúncio.
            #
            # A ESPERA ERA GROSSA DEMAIS. Antes o laço fazia `tick(1.0)` ANTES de
            # conferir, então um convite aceito no primeiro instante ainda custava
            # um segundo cheio, e a conferência só acontecia de segundo em segundo.
            # Na prática a conta de reset aceita de primeira, e essa granularidade
            # era tempo parado na porta da cave sem tentar entrar.
            #
            # Agora confere ANTES de esperar e depois a cada 0,2 s.
            comecou = time.time()
            limite = comecou + ESPERA_PELA_RESPOSTA
            while True:
                # DUAS FORMAS DE CONFIRMAR, e a segunda é a que funciona aqui.
                #
                # `in_team` depende de `memory.team_size()`, que não responde
                # neste cliente -- foi por isso que o log mostrou o convite aceito
                # às 02:17:22 e quem convidou desistindo às 02:17:45.
                #
                # O ACEITE ANUNCIADO não depende de leitura nenhuma: as duas
                # contas rodam neste processo, e quem aceitou avisa. Se o bot
                # enviou o convite e o bot clicou no Ok, o time está formado --
                # não há terceira parte envolvida para duvidar.
                if self.in_team:
                    ctx.log.info(
                        "Time formado com %s membros em %.1fs (reset garantido)",
                        self.team_size(), time.time() - comecou,
                    )
                    consumir_aceite(remetente)
                    return True

                quem_aceitou = aceite_pendente(remetente)
                if quem_aceitou is not None:
                    ctx.log.info(
                        "'%s' aceitou o convite em %.1fs (aviso interno das duas "
                        "pontas; reset garantido)",
                        quem_aceitou, time.time() - comecou,
                    )
                    consumir_aceite(remetente)
                    return True

                if time.time() >= limite:
                    break
                ctx.tick(PASSO_DA_ESPERA_DO_TIME)
            ctx.log.warning("'%s' não entrou no time em %.0fs",
                            nick, ESPERA_PELA_RESPOSTA)

        ctx.log.warning(
            "Não consegui formar time com '%s'. Sigo para a entrada da cave: sem "
            "troca de time o boss pode não renascer, mas é melhor tentar a run do "
            "que travar aqui. Confira se a conta de reset está online e com "
            "'aceitar convites de time' marcado.", nick,
        )
        diario.registrar_evento(
            ctx.account_login, "time-nao-formado",
            f"convidei '{nick}' e ele não entrou; o boss pode não renascer",
            ctx.memory.position(), ctx.memory.location(),
        )
        return True

    def sair_do_time(self) -> bool:
        """Sai do time por DOIS CLIQUES medidos no cliente.

            clique DIREITO em (44,48)   -> abre o menu do próprio personagem
            clique esquerdo em (92,97)  -> "Leave the team"

        Não há comando de chat que valha a pena: o cliente responde "You speak too
        fast" e o texto fica visível para os outros jogadores.

        SÓ DEPOIS DE ENTRAR NA CAVE. O time existe para que a instância criada
        seja nova -- sem trocar de time o boss não renasce -- e a instância nasce
        no instante em que a entrada dá certo. Sair antes desperdiçaria o reset,
        e é por isso que quem chama isto é o estado que acabou de confirmar a
        entrada.

        As duas coordenadas são medidas, e não calculadas: a versão anterior
        somava um deslocamento a um retrato em (57,66) e o clique caía em "PK
        Mode" quando o menu tinha um número diferente de linhas. O template
        continua sendo tentado primeiro, quando existe, porque imagem é mais
        forte que coordenada.
        """
        ctx = self.ctx

        # O GUARDA QUE IMPEDIA OS CLIQUES.
        #
        # Aqui havia `if not self.in_team: return True`, e `in_team` devolve False
        # tanto para "não estou em time" quanto para "não consegui ler o time". Com
        # a leitura falhando, a função saía DIRETO -- sem clique nenhum, e ainda
        # devolvendo sucesso. Do lado de fora parecia coordenada errada; na
        # verdade nada era enviado.
        #
        # Agora só desiste quando a leitura CONFIRMA que não há time. Estado
        # desconhecido tenta assim mesmo: sair de um time que não existe custa dois
        # cliques, e não sair custa o reset do boss -- que é o motivo do time.
        estado = self.estado_do_time
        if estado is False:
            ctx.log.debug("Leitura de time confirma que não estou em time; "
                          "não preciso sair")
            return True
        if estado is None:
            ctx.log.info(
                "Não consegui LER se estou em time. Vou tentar sair mesmo assim: "
                "dois cliques custam pouco, e ficar em time custa o reset do boss."
            )

        for tentativa in range(1, 4):
            ctx.raise_if_stopped()
            ctx.right_click(ctx.coords.own_portrait)
            ctx.tick(0.4)

            alvo: tuple[int, int] | None = None
            template = ctx.templates.load(MENU_LEAVE_TEMPLATE)
            if template is not None:
                quadro = capture_window(ctx.hwnd)
                if quadro is not None:
                    alvo = find_template(quadro, template, threshold=ANCHOR_THRESHOLD)
            if alvo is None:
                alvo = ctx.coords.menu_leave_team

            ctx.log.debug("Clique em 'Leave the team' em %s (tentativa %s, %s)",
                          alvo, tentativa,
                          "template" if template is not None else "coordenada")
            ctx.click(alvo)
            ctx.tick(0.5)

            depois = self.estado_do_time
            if depois is False:
                ctx.log.info("Saí do time (tentativa %s)", tentativa)
                return True
            if depois is None:
                # Sem leitura não dá para confirmar, e insistir com o menu já
                # fechado clicaria no que estiver naquela coordenada. Uma tentativa
                # é o que faz sentido às cegas.
                ctx.log.info(
                    "Cliquei em 'Leave the team', mas não consigo LER o time para "
                    "confirmar. Sigo em frente sem repetir o clique."
                )
                return True

        ctx.log.warning(
            "Não consegui sair do time pelo menu do retrato. A run continua, mas "
            "o próximo reset pode não valer."
        )
        diario.registrar_evento(
            ctx.account_login, "time-nao-desfeito",
            "continuo em time depois de 3 tentativas de 'Leave the team'",
            ctx.memory.position(), ctx.memory.location(),
        )
        return False


class InviteAcceptor:
    """Aceita convites de time -- e recusa os que não são das nossas contas.

    Usado pela conta de reset, aquela que fica parada só para as outras
    conseguirem resetar a cave.

    QUEM ENVIOU?

    A caixa mostra "[Nick] invite you to join the team". Ler esse nick exigiria
    OCR -- e não precisa: os supervisores de todas as contas rodam NO MESMO
    PROCESSO, então quem convida simplesmente ANUNCIA, e quem recebe consulta o
    anúncio. Informação exata, sem imagem nenhuma no caminho.

    Isso é o que faz o reset funcionar mesmo sem captura de tela. A versão
    anterior exigia encontrar o template do convite antes de qualquer coisa; em
    cliente DirectX fora de primeiro plano o PrintWindow devolve quadro preto,
    nenhum template casa, e a conta de reset ficava olhando a caixa sem clicar.
    Agora, com anúncio na mão, ela clica no Ok pela coordenada medida.

    Sem anúncio e em modo estrito, o convite é de estranho e leva Cancel: entrar
    no time de um estranho quebraria o reset das contas de verdade, porque o bot
    não controla quando esse estranho sai.

    Se NENHUMA conta desta execução usa este personagem como reseter, não há como
    verificar nada localmente -- a outra conta pode estar em outra máquina. Nesse
    caso o comportamento é o antigo: aceita. Recusar tudo seria pior, porque
    deixaria o reset impossível nesse arranjo.
    """

    def __init__(self, ctx: BotContext, cooldown: float = 0.5,
                 exigir_caixa: bool = False) -> None:
        self.ctx = ctx
        self.cooldown = cooldown
        # SÓ CLICA COM A CAIXA CONFIRMADA -- 16/09/2026, para o modo APP.
        #
        # O caminho do anúncio clica no Ok pela coordenada medida ANTES de a
        # caixa aparecer, de propósito: ela leva um ou dois segundos e um clique
        # cedo demais não aceitaria nada. Numa conta de reset, parada num canto,
        # clique perdido não custa nada.
        #
        # NO MODO APP CUSTA: o Ok é clique ESQUERDO, o mesmo que faz o
        # personagem andar, e um que caia na cena 3D tira a conta do ponto de
        # farm. Pedido do usuário em 15/09/2026: *"é importante que só clique
        # depois que aparecer a mensagem de aceitar, mesmo que isso atrase um
        # pouco o aceitar"*.
        #
        # LIGADO POR INSTÂNCIA, e não para todo mundo: o reset da cave funciona
        # hoje com o clique cego, e apertar a regra lá mudaria um farm que roda
        # sem ninguém ter pedido.
        self.exigir_caixa = exigir_caixa
        self._last_check = 0.0
        self._accepted = 0
        self._recusados = 0
        self._modo_logado: bool | None = None
        # Cliques dados no Ok para o convite anunciado ATUAL. Zera quando o
        # anúncio é consumido -- ver `MAX_CLIQUES_DE_ACEITE`.
        self._cliques_de_aceite = 0
        # De quem foi o convite cuja falta de prova eu já avisei.
        self._sem_prova: str | None = None

    # -- modo de verificação -----------------------------------------------

    @property
    def _meu_nick(self) -> str:
        return (self.ctx.char_name or "").strip()

    def _modo_estrito(self) -> bool:
        """Alguma conta que está FARMANDO aqui me usa como reseter?

        Só quem farma envia convite. Contas desativadas ou com o farm desligado
        não contam: se contassem, o modo estrito ligaria sem ninguém para
        anunciar convite, e todos os convites seriam recusados.
        """
        meu = self._meu_nick.lower()
        if not meu:
            return False
        # UM CAMPO SÓ desde 08/09/2026 (`settings.reset_nick`). Antes eram
        # dois, e olhar só o do BC deixava o reseter da HH invisível: o modo
        # estrito não ligava por causa dele, e um convite da HH chegava sem
        # ninguém reconhecer quem convidou.
        return any(
            conta.settings.reset_nick.strip().lower() == meu
            for conta in self.ctx.config.farming_accounts()
        )

    def _modal_na_tela(self) -> bool:
        """O jogo diz que há uma caixa modal aberta? Leitura de MEMÓRIA.

        `modal_open()` é o mesmo flag genérico que a Block list já usa para
        saber se a confirmação do Remove apareceu. Ele não distingue QUAL caixa
        -- e não precisa: quem diz que existe um convite é o anúncio interno;
        isto só confirma que há algo clicável na tela.
        """
        try:
            return bool(self.ctx.memory.modal_open())
        except Exception:
            return False

    def _achar_caixa(self, quadro) -> tuple[int, int] | None:
        """Centro do texto invariante do convite, se a caixa está na tela."""
        for nome in (INVITE_TEXT_TEMPLATE, INVITE_TEMPLATE):
            template = self.ctx.templates.load(nome)
            if template is None:
                self.ctx.log.debug("Template '%s' não carregado", nome)
                continue
            ponto = find_template(quadro, template, threshold=INVITE_THRESHOLD)
            if ponto is not None:
                self.ctx.log.info("Template '%s' CASOU em %s (threshold=%.2f)", nome, ponto, INVITE_THRESHOLD)
                return ponto
            #else:
                #self.ctx.log.debug("Template '%s' NÃO casou (threshold=%.2f)", nome, INVITE_THRESHOLD)
        #self.ctx.log.warning("Nenhum template de convite casou — quadro=%s", "ok" if quadro is not None else "None")
        return None

    # -- decisão -----------------------------------------------------------

    def check_and_accept(self) -> bool:
        # A BATIDA VEM ANTES DE TUDO, INCLUSIVE DO COOLDOWN -- e a posição é a
        # regra, não um detalhe de estilo.
        #
        # Ela é o que diz a quem farma que este personagem PODE aceitar um
        # convite agora. Colocada aqui, isso deixa de ser uma afirmação sobre a
        # conta e passa a ser uma consequência de o código ter chegado neste
        # ponto: quem está em modo APP, logando, relogando ou farmando nunca
        # chega, e por isso nunca bate. Ver `bater()` no topo do módulo.
        #
        # ANTES do cooldown porque o cooldown é sobre CLICAR (não vale a pena
        # capturar a tela cinco vezes por segundo), não sobre estar disponível.
        # Batendo depois dele, a batida herdaria a cadência do clique sem motivo.
        bater(self._meu_nick)

        ctx = self.ctx
        agora = time.time()
        if agora - self._last_check < self.cooldown:
            return False
        self._last_check = agora

        # A CAPTURA SÓ QUANDO HÁ MOTIVO -- 19/09/2026.
        #
        # Ela vinha antes de qualquer pergunta, inclusive quando não havia
        # convite nenhum: ~15 ms a cada meio segundo, gastos para descobrir que
        # não havia nada a fazer. No modo APP isso é o que impedia perguntar
        # dentro da espera da linha, porque o tempo entraria em UMA conta e
        # desalinharia o time (ver `sincronia.volta_cega`).
        #
        # `exigir_caixa` é o que separa os dois usos: o aceitador do APP só
        # aceita convite ANUNCIADO por uma conta deste bot, e sem anúncio não há
        # imagem que interesse. O da conta de reset continua olhando a tela --
        # é por lá que ele reconhece convite de estranho.
        remetente_anunciado = convite_pendente(self._meu_nick)
        quadro = (capture_window(ctx.hwnd)
                  if (remetente_anunciado is not None or not self.exigir_caixa)
                  else None)
        ponto = self._achar_caixa(quadro) if quadro is not None else None

        # CAMINHO PRINCIPAL: uma conta DESTE bot acabou de me convidar.
        #
        # As duas contas rodam no mesmo processo, então não há nada para ler da
        # tela: o anúncio interno já diz que o convite é legítimo e que ele
        # acabou de sair. O Ok fica numa coordenada medida (437,335), a mesma de
        # todas as caixas de confirmação do cliente -- clicar nela é suficiente e
        # funciona mesmo quando a captura de imagem está indisponível, que é
        # justamente o caso em cliente DirectX fora de primeiro plano.
        #
        # Isto importa porque era aqui que o reset falhava: sem captura, o
        # template do convite nunca casava e a conta de reset não clicava em nada.
        if remetente_anunciado is not None:
            # O PORTÃO (só com `exigir_caixa`): sem prova de que a caixa está na
            # tela, não sai clique.
            #
            # A IMAGEM é a primeira via (e dá o ponto exato). A MEMÓRIA é a
            # segunda, e é a que responde quando o `PrintWindow` devolve quadro
            # preto -- que é o caso normal deste cliente fora de primeiro plano.
            if self.exigir_caixa and ponto is None and not self._modal_na_tela():
                self._avisar_sem_prova(remetente_anunciado, quadro)
                return False
            # Onde clicar: o Ok localizado por imagem quando ela existe (mais
            # forte), senão a coordenada medida.
            if ponto is not None:
                _, deslocamentos = TEMPLATE_ANCHORS["team_invite"]
                onde = (ponto[0] + deslocamentos["ok"][0],
                        ponto[1] + deslocamentos["ok"][1])
                origem = f"caixa localizada na imagem (template_centro={ponto}, ok_offset={deslocamentos['ok']})"
            else:
                onde = ctx.coords.confirm_ok
                origem = f"coordenada medida confirm_ok={ctx.coords.confirm_ok} (sem imagem disponível)"

            self._cliques_de_aceite += 1
            ctx.log.info("Tentando aceitar convite de '%s' — %s → clicando em %s (tentativa %s/%s)",
                         remetente_anunciado, origem, onde, self._cliques_de_aceite, MAX_CLIQUES_DE_ACEITE)
            self._aceitar(
                onde,
                f"'{remetente_anunciado}' (conta deste bot) convidou — {origem} "
                f"(clique {self._cliques_de_aceite} de {MAX_CLIQUES_DE_ACEITE})",
            )

            # AVISA DE VOLTA. Quem convidou está esperando, e é isto que ele
            # espera -- não a leitura de `team_size`, que não funciona aqui.
            anunciar_aceite(remetente_anunciado, self._meu_nick)

            # QUANTAS VEZES CLICAR.
            #
            # O anúncio chega no instante do ENVIO, e a caixa pode levar um ou
            # dois segundos para aparecer. Por isso o clique se repete: um clique
            # dado antes de a caixa existir não aceitaria nada.
            #
            # Mas antes a repetição só parava quando `team_size()` respondesse --
            # e como ela nunca responde neste cliente, o log real registrou ONZE
            # cliques seguidos para um convite que já tinha sido aceito no
            # primeiro. Agora o teto é explícito.
            # A LEITURA QUE RESPONDE -- 15/09/2026.
            #
            # Era `team_size()`, que NUNCA respondeu neste cliente: a parada
            # caía sempre no teto de cliques, mesmo com o convite aceito no
            # primeiro. `tamanho_do_time()` lê pelo ponteiro rebaseado
            # (`ADDR_TEAM`, o +0x60) e foi provada ao vivo em seis clientes em
            # 31/08/2026 -- ver `core/memory.py`.
            #
            # O QUE ISSO COMPRA: parar de clicar assim que o time se forma. No
            # modo APP cada clique esquerdo perdido é o personagem andando, e
            # é por isso que a troca vem ANTES do time do APP, não junto.
            tamanho = self.ctx.memory.tamanho_do_time()
            if (tamanho is not None and tamanho > 1) or (
                    self._cliques_de_aceite >= MAX_CLIQUES_DE_ACEITE):
                consumir_convite(self._meu_nick)
                self._cliques_de_aceite = 0
                if tamanho is not None and tamanho > 1:
                    ctx.log.info("Time confirmado com %s membros", tamanho)
                else:
                    ctx.log.debug(
                        "Cliquei no Ok %s vezes e avisei quem convidou; "
                        "encerrando este convite", MAX_CLIQUES_DE_ACEITE)
            return True

        if quadro is None or ponto is None:
            return False

        _, deslocamentos = TEMPLATE_ANCHORS["team_invite"]
        ok = (ponto[0] + deslocamentos["ok"][0], ponto[1] + deslocamentos["ok"][1])
        cancel = (ponto[0] + deslocamentos["cancel"][0],
                  ponto[1] + deslocamentos["cancel"][1])

        # O modo pode MUDAR com o bot rodando (basta ligar o BC farm da outra
        # conta), então é reavaliado sempre e registrado quando troca.
        estrito = self._modo_estrito()
        if estrito != self._modo_logado:
            self._modo_logado = estrito
            ctx.log.info(
                "Convites de time: %s",
                f"só das contas deste bot que me usam como reseter ({self._meu_nick})"
                if estrito else
                "aceito qualquer um — nenhuma conta desta execução me usa como "
                "reseter, então não tenho com o que comparar",
            )

        if not estrito:
            self._aceitar(ok, "sem verificação possível")
            return True

        # Chegou aqui: há uma caixa de convite na tela e NENHUMA conta deste bot
        # a anunciou (o caminho do anúncio, no topo da função, já teria aceitado e
        # retornado). Em modo estrito isso é convite de estranho -- entrar no time
        # de um estranho quebraria o reset das contas de verdade, porque o bot não
        # controla quando esse estranho sai.
        #
        # NÃO existe mais comparação do nick por recorte aprendido. Ela era a
        # forma de decidir quando o anúncio não bastava, e virou código morto no
        # instante em que o anúncio passou a ser o caminho principal: com as duas
        # contas no mesmo processo, o anúncio é informação exata, e comparar
        # pixels de nick só adicionava um jeito de errar.
        self._recusar(
            cancel,
            "nenhuma conta deste bot convidou este personagem agora",
        )
        return True

    def _avisar_sem_prova(self, remetente: str, quadro) -> None:
        """Conta UMA vez por convite que não houve prova de caixa na tela.

        Sem esta linha a recusa é INVISÍVEL: o líder registra "não aceitou em
        4s" e deste lado não há nada -- foi assim que o time do APP não se
        formou em 16/09/2026 sem deixar rastro. Ela diz qual das duas vias
        faltou, imagem ou memória, que é a pergunta que sobra.
        """
        if self._sem_prova == remetente:
            return
        self._sem_prova = remetente
        self.ctx.log.info(
            "Convite de '%s' anunciado, mas sem prova de caixa na tela "
            "(imagem: %s; memória: não) -- não clico às cegas.",
            remetente, "sem quadro" if quadro is None else "não casou")

    def _aceitar(self, ponto: tuple[int, int], motivo: str) -> None:
        self._sem_prova = None
        self._accepted += 1
        self.ctx.log.info("Convite de time ACEITO (%s no total) — %s @ %s",
                          self._accepted, motivo, ponto)
        self.ctx.click(ponto)
        self.ctx.tick(0.5)

    def _recusar(self, ponto: tuple[int, int], motivo: str) -> None:
        self._recusados += 1
        self.ctx.log.info("Convite de time RECUSADO (%s no total) — %s",
                          self._recusados, motivo)
        self.ctx.click(ponto)
        self.ctx.tick(0.5)

    @property
    def accepted(self) -> int:
        return self._accepted

    @property
    def refused(self) -> int:
        return self._recusados
