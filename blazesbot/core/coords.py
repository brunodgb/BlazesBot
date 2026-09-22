"""
Coordenadas de tela, ancoradas — funcionam em qualquer resolução.

DESCOBERTA QUE PERMITE ISSO

Medi o mesmo template em prints de dimensões diferentes e ele casa com score
1.000 em todos. Ou seja: **a interface do jogo não escala com a resolução** — os
elementos têm tamanho fixo em pixels e são ancorados às bordas ou ao centro da
tela. Aumentar a resolução dá mais cenário, não uma UI maior.

Duas consequências práticas:

  1. Um template recortado em 1024x768 funciona em 1920x1080. Localizar
     elementos por imagem é resolução-independente.
  2. As coordenadas podem ser derivadas: em vez de "x=515", guardamos
     "centralizado horizontalmente, 33 px acima da base" e calculamos para
     qualquer tamanho de janela.

RESSALVA HONESTA

Todos os prints que usei para medir são de 1024x768. O modelo de ancoragem de
cada elemento (centro, base, canto superior direito) é dedução a partir do
layout, não medição em duas resoluções diferentes. Em 1024x768 os valores são
idênticos aos validados em produção — não há regressão. Em outras resoluções, é
derivação de boa-fé, e o bot prefere sempre a posição ENCONTRADA por template
quando ela existe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Resolução em que tudo foi medido.
BASE_W, BASE_H = 1024, 768

# Resoluções oferecidas pelo cliente (System > Graphics > Screen Size).
SUPPORTED_RESOLUTIONS = (
    "800x600", "1024x768", "1130x635", "1152x864", "1176x664",
    "1280x720", "1280x768", "1280x800", "1280x960", "1280x1024",
    "1360x768", "1366x768", "1440x900", "1440x1080", "1477x831",
    "1600x900", "1600x1024", "1632x918", "1680x1050", "1920x1080",
)
VALIDATED_RESOLUTION = "1024x768"


class Anchor(str, Enum):
    """A que ponto da janela o elemento está preso."""

    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    TOP_CENTER = "top_center"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"


def _anchor_origin(anchor: Anchor, width: int, height: int) -> tuple[int, int]:
    if anchor is Anchor.CENTER:
        return width // 2, height // 2
    if anchor is Anchor.TOP_LEFT:
        return 0, 0
    if anchor is Anchor.TOP_RIGHT:
        return width, 0
    if anchor is Anchor.TOP_CENTER:
        return width // 2, 0
    if anchor is Anchor.BOTTOM_LEFT:
        return 0, height
    if anchor is Anchor.BOTTOM_RIGHT:
        return width, height
    return width // 2, height  # BOTTOM_CENTER


@dataclass(frozen=True)
class Spot:
    """Um ponto da tela, guardado como âncora + deslocamento."""

    anchor: Anchor
    dx: int
    dy: int

    def at(self, width: int, height: int) -> tuple[int, int]:
        ox, oy = _anchor_origin(self.anchor, width, height)
        return ox + self.dx, oy + self.dy


def _from_base(x: int, y: int, anchor: Anchor = Anchor.CENTER) -> Spot:
    """Converte uma coordenada medida em 1024x768 em âncora + deslocamento."""
    ox, oy = _anchor_origin(anchor, BASE_W, BASE_H)
    return Spot(anchor, x - ox, y - oy)


C = Anchor.CENTER
TR = Anchor.TOP_RIGHT
BC = Anchor.BOTTOM_CENTER
BL = Anchor.BOTTOM_LEFT
BR = Anchor.BOTTOM_RIGHT

# ---------------------------------------------------------------------------
# Mapa de pontos, medidos em 1024x768
# ---------------------------------------------------------------------------
#
# A âncora de cada um foi escolhida pelo comportamento do layout:
#   * Caixas de diálogo e painéis do jogo -> CENTER
#   * Fila de botões da tela de personagem -> BOTTOM_CENTER
#   * Minimapa e botões do canto -> TOP_RIGHT
#   * Abas de chat -> BOTTOM_LEFT
# Retratos do painel de time. O primeiro foi MEDIDO no cliente; o passo é
# derivado do print que o usuário enviou (28/08/2026) e ainda precisa de
# conferência na aferição -- por isso é UM número, e não quatro coordenadas.
PRIMEIRO_RETRATO_DO_TIME = (28, 204)
PASSO_ENTRE_RETRATOS_DO_TIME = 80
MAXIMO_DE_RETRATOS_DO_TIME = 4


_SPOTS: dict[str, Spot] = {
    # -- retrato do próprio personagem, canto superior esquerdo --------------
    # Clicar com o botão DIREITO no rosto abre o menu do personagem, e é de lá
    # que se sai do time ("Leave the team"). Não existe outro caminho de UI para
    # isso -- comando de chat aparece para os outros jogadores e o cliente ainda
    # responde "You speak too fast".
    #
    # As duas coordenadas foram MEDIDAS no cliente: (44,48) para o clique
    # direito no retrato e (92,97) para o item do menu. A versão anterior usava
    # (57,66) mais um deslocamento calculado, e o clique caía fora do item.
    "own_portrait": _from_base(44, 48, Anchor.TOP_LEFT),
    "menu_leave_team": _from_base(82, 97, Anchor.TOP_LEFT),

    # -- painel de time: os retratos dos COMPANHEIROS ------------------------
    #
    # Ficam na coluna esquerda, ABAIXO do retrato do próprio personagem -- que
    # não faz parte desta lista (ele é o `own_portrait` acima, maior).
    #
    # Clicar com o botão ESQUERDO no rosto de um companheiro o SELECIONA como
    # alvo -- é o que a Fada usa para mirar a cura (`docs/decisoes/fada.md`).
    #
    # O PRIMEIRO FOI MEDIDO pelo usuário: (28, 204). Os outros três são
    # DERIVADOS de um passo fixo, e é assim que tem de ficar -- quatro literais
    # soltos seriam quatro chances de só um ser corrigido quando a medição do
    # passo mudar.
    #
    # O painel ENCOLHE POR BAIXO: com menos companheiros, o slot de baixo some e
    # os de cima ficam onde estavam. Então o slot 1 sempre existe (para haver
    # time é preciso líder + 1) e a varredura vai só até o número de membros.
    **{
        f"team_member_{i + 1}": _from_base(
            PRIMEIRO_RETRATO_DO_TIME[0],
            PRIMEIRO_RETRATO_DO_TIME[1] + i * PASSO_ENTRE_RETRATOS_DO_TIME,
            Anchor.TOP_LEFT)
        for i in range(MAXIMO_DE_RETRATOS_DO_TIME)
    },

    # -- minimapa: coração da navegação, ancorado no canto superior direito ---
    "minimap_center": _from_base(919, 115, TR),
    # ZOOM do minimapa. São CINCO níveis: o padrão no meio, dois de aproximar
    # e dois de afastar -- medido pelo usuário. Do máximo de um lado ao do outro
    # são 4 cliques, e os botões PARAM no extremo (clicar demais não passa).
    #
    # PADRONIZAR NO PADRÃO, e não no zoom-out máximo, e a razão é dura:
    # `zones.MINIMAP_SCALE = 1.7` px/unidade foi MEDIDO com o jogo no zoom em que
    # ele abre -- o padrão --, porque estes botões nunca tinham sido usados pelo
    # bot. Toda a navegação sai dessa escala (`ALCANCE_DO_MINIMAPA` = 30/1.7 ≈
    # 17,6 unidades por clique). Em outro zoom a escala é outra, e cada clique de
    # movimento passaria do alvo.
    #
    # Zoom-out máximo poderia ser MELHOR (mais unidades por clique = menos
    # cliques por trajeto), mas exige remedir a escala -- e errar ali quebra o
    # movimento em todo lugar de uma vez.
    "minimap_zoom_out": _from_base(995, 126, TR),
    "minimap_zoom_in": _from_base(995, 100, TR),
    "mouse_park": _from_base(900, 182, TR),
    # View Reset -- recentra a câmera. É apertado ANTES de qualquer tentativa de
    # entrar na cave: sem a câmera na posição padrão, os cliques posicionais no
    # NPC caem no lugar errado.
    #
    # Esta é a MELHOR confirmação de que a UI é ancorada e não escalada: medido
    # em (865,57) a 1024x768 e em (1476,59) a 1632x918. A diferença em X entre a
    # borda direita e o botão ficou em -159 e -156 px -- ou seja, constante. O
    # valor abaixo é a média, e erra no máximo 3 px nas duas resoluções.
    "reset_view": _from_base(867, 58, TR),
    "surroundings_button": _from_base(975, 58, TR),

    # -- painéis centrais ----------------------------------------------------
    # Botão que SOBE a página da barra de atalhos (a seta para cima, ao lado da
    # bola verde que mostra 1, 2 ou 3).
    #
    # O bot só funciona com a barra na página 1 -- é ali que estão as teclas que
    # o usuário configurou. Na página errada, a mesma tecla dispara outra coisa.
    #
    # MEDIDO por template contra quatro prints do usuário, com janelas de 1023 a
    # 1028 de largura: o centro do botão ficou entre (535,728) e (539,734), ou
    # seja, uma variação de 4 a 6 px num botão de 22x22 -- sempre dentro dele. O
    # usuário mediu (539,734) por conta própria, o que confere.
    #
    # A âncora BOTTOM_CENTER é a convenção desta barra (ela acompanha o rodapé).
    # As duas amostras de casamento perfeito não separam BOTTOM_CENTER de
    # TOP_LEFT nesta precisão -- a diferença esperada entre as duas era de 2,5 px
    # e a medição tem essa mesma ordem de erro. Com 22 px de botão, as duas
    # acertam; se algum dia aparecer resolução muito diferente e o clique errar,
    # é aqui que se olha.
    "hotbar_page_up": _from_base(539, 733, BC),
    "world_map": _from_base(654, 105, C),
    # Ok das caixas de confirmação. Serve para três coisas medidas no mesmo
    # ponto: aceitar convite de time, confirmar venda de "precious item" e
    # fechar avisos comuns.
    "confirm_ok": _from_base(437, 335, C),
    "revive_ok": _from_base(515, 469, C),
    "loot": _from_base(505, 390, C),
    "pickup": _from_base(447, 479, C),
    "surroundings_input": _from_base(590, 540, C),
    "surroundings_first_link": _from_base(299, 261, C),

    # -- vendedor (NPC Rich, em Stone City) ----------------------------------
    #
    # Medidas em 1024x768 estando o personagem na coordenada de jogo
    # `mapa_bc.POSICAO_DO_VENDEDOR` -- hoje (158,-494). Fora dessa posição os
    # cliques no NPC não acertam, e a venda confere a coordenada antes de clicar
    # com `mapa_bc.PRECISAO_NO_PONTO_DO_VENDEDOR`.
    #
    # AS DUAS ANDAM JUNTAS: mudar a posição de parada sem remedir o `vendor_npc`
    # põe o clique na parede. Quando o usuário mudou de (153,-492) para
    # (158,-494), o NPC saiu de (464,377) para (172,301) -- quase 300 px.
    "vendor_npc": _from_base(284, 336, C),        # clique DIREITO no NPC
    "vendor_sell_tab": _from_base(266, 430, C),   # abre a janela de venda
    # O `Roaming Apothecary` da HH, do lado de fora da cave.
    #
    # REMEDIDO pelo usuário em 09/09/2026, com o personagem parado no ponto NOVO
    # da venda (`mapa_hh.PONTO_DA_VENDA`, -343,-294): clique DIREITO em (490,519)
    # da ÁREA DE CLIENTE, numa janela de 1029 de largura -- o valor abaixo é o
    # equivalente na base 1024x768. Cai sobre o corpo do NPC, abaixo do nome.
    #
    # ERA (475,450), medido em 03/09/2026 do waypoint da PORTA (-342,-288). Os
    # dois pontos de parada distam ~6 unidades de mundo, e o NPC andou 69 px na
    # tela -- a mesma ordem de grandeza já medida na BC, onde cinco unidades
    # moveram o Rich Man quase 300 px.
    #
    # ANDA JUNTO COM `mapa_hh.PONTO_DA_VENDA`: este ponto é um clique na cena
    # 3D, então ele só vale a partir daquela coordenada. Mudar uma sem remedir a
    # outra faz o clique cair no chão -- e clique no chão faz o personagem ANDAR.
    "hh_vendor_npc": _from_base(488, 519, C),
    # O `Servant Child` da HH, DENTRO da cave, no ponto de saída (529,119).
    #
    # MEDIDO pelo usuário em 03/09/2026: clique DIREITO aqui abre o diálogo,
    # que traz o link "Leave Happiness Hall".
    #
    # ANDA JUNTO COM `mapa_hh.CAMINHO_ATE_A_SAIDA`: é um clique na cena 3D, e
    # só vale a partir daquela coordenada. Mudar uma sem remedir a outra faz o
    # clique cair no chão -- e clique no chão faz o personagem ANDAR, saindo
    # justamente do ponto de onde o NPC é alcançável.
    "hh_exit_npc": _from_base(626, 526, C),
    "vendor_sell_button": _from_base(472, 717, BC),
    "vendor_purchase_tab": _from_base(282, 395, C),
    "vendor_buy_slot": _from_base(194, 327, C),
    "vendor_buy_button": _from_base(182, 712, BC),
    # "Close" do diálogo do NPC. MEDIDO no rodapé da janela, em (365,653) com
    # janela de 1029 de largura -- o valor abaixo é o equivalente na base.
    #
    # ESTAVA EM (513,302), QUE CAI NA CENA 3D, ao lado do personagem. Clique na
    # cena 3D FAZ O PERSONAGEM ANDAR: é o mesmo defeito que o par de cliques do
    # NPC tinha. Usado só em `buy_supplies`, que é raro (só quando uma pedra de
    # retorno foi gasta), e por isso passou tanto tempo sem aparecer.
    "npc_leave": _from_base(363, 653, C),

    # Onde um NPC costuma cair na tela depois do caminhar automático, com a
    # câmera no padrão (View Reset + os valores fixados por memória). É o centro
    # do clique direito da Transport Fay e da entrada da cave -- `falar_com_npc`
    # parte daqui e aplica o deslocamento de cada NPC por cima.
    #
    # MEDIDO EM (482,353) a 1024x768. Estava calculado à mão dentro do
    # `ui_service`, e MISTURANDO OS DOIS MODELOS: `largura//2 - 30` em X
    # (ancorado, certo) e `altura * 0.46` em Y (PROPORCIONAL, errado). A
    # proporção contradiz a descoberta que abre este arquivo -- a UI não escala,
    # e mais resolução dá mais cenário, não elementos maiores; logo o ponto
    # guarda um deslocamento FIXO do centro, não uma fração da altura.
    #
    # A 1024x768 os dois dão o MESMO número (int(768*0.46) = 353 = 384-31), então
    # a troca não muda nada na resolução validada. Fora dela a proporção erra, e
    # o erro cresce com a tela: 13 px a 1920x1080, 10 px a 1280x1024, 7 px para o
    # outro lado a 800x600. Num NPC de algumas dezenas de pixels isso come a
    # margem inteira -- e come justamente na entrada da cave, que ainda aplica
    # -48 por cima.
    "npc_padrao": _from_base(482, 353, C),

    # -- cave ----------------------------------------------------------------
    # NPC Skull Herald da ENTRADA, em Ghost Din Woods (1395,-635).
    "cave_enter_npc": _from_base(446, 462, C),
    "cave_enter_confirm": _from_base(258, 364, C),
    # Altar Stone, no Secret Altar. Só acerta a partir do waypoint (218,45) --
    # é clique posicional na cena 3D, então a posição do personagem faz parte da
    # coordenada.
    "altar_npc": _from_base(429, 437, C),         # clique DIREITO no Altar Stone
    "altar_enter": _from_base(276, 337, C),       # link "Secret Cemetery"
    # NPC Skull Herald da SAÍDA, dentro do covil, na posição (81,-398). Mesmo
    # nome e mesmo NPC da entrada: o jogo usa os dois para entrar e sair.
    "cave_exit_npc": _from_base(616, 326, C),     # clique DIREITO
    "cave_exit_link": _from_base(250, 364, C),    # link "Leave Bewitcher Cave"
    "cave_exit": _from_base(301, 364, C),         # legado; mantido por compat

    # -- tela de login -------------------------------------------------------
    "login_account": _from_base(625, 395, C),
    "login_password": _from_base(613, 425, C),
    "login_ok": _from_base(518, 495, C),
    "login_error_close": _from_base(515, 333, C),
    # Ok da caixa "Acquiring server IP address." -- o aviso que aparece quando os
    # servidores estão fora do ar.
    #
    # É o MESMO quadro de mensagem do erro de senha, na mesma posição: medido em
    # (512,335) contra (515,333) do outro. A coincidência não é sorte, é o cliente
    # reaproveitando a mesma janela -- e é o que permite tratar avisos novos deste
    # tipo sem precisar de coordenada nova.
    "server_ip_ok": _from_base(512, 335, C),
    "server_ok": _from_base(557, 531, C),
    # O CANCEL DA LISTA DE SERVIDORES, medido no print 1:1 de 22/09/2026:
    # o Ok fica em x=557 e o Cancel em x=669, mesmo y. O delta de 112 px é
    # o que importa -- e a folga é o próprio botão, que tem 57 px de
    # largura (`data/templates/cancel.bmp`), então erro de leitura de uma
    # dezena de pixels ainda acerta.
    "server_cancel": _from_base(669, 531, C),

    # ONDE FICA O TEXTO "Connection interrupted" DENTRO DA CAIXA.
    #
    # NÃO é ponto de clique: é o CENTRO DA BUSCA do template que decide se a
    # conta caiu (`watchdog.RECONNECT_TEMPLATE`). Existe porque o template é só
    # a frase, sem moldura -- e a MESMA frase aparece no chat quando outro
    # jogador a digita. Procurar na tela inteira derrubou 10 contas vivas.
    #
    # MEDIDO nos 12 prints de queda real de `logs/quedas/` (31/08 e 01/09/2026):
    # o casamento cai em (441, 198) em onze deles e em (441, 202) no outro --
    # 4 px de variação, porque a caixa é opaca e sempre centralizada.
    #
    # Âncora CENTER pela regra da tabela lá em cima: caixa de diálogo do jogo é
    # centralizada na área de cliente, então em outra resolução ela acompanha o
    # centro -- e é justamente por isso que não pode ser literal.
    "aviso_de_conexao": _from_base(441, 198, C),

    # -- seleção de personagem: fila de botões presa à base ------------------
    "enter_game": _from_base(515, 735, BC),
    "char_left": _from_base(398, 640, BC),
    "char_center": _from_base(515, 640, BC),
    "char_right": _from_base(633, 641, BC),
}

# Lista de servidores: primeira linha e passo entre linhas.
_SERVER_FIRST_ROW = _from_base(345, 247, C)
SERVER_ROW_HEIGHT = 20


# Geometria da grade de venda, medida no print real.
SELL_COLUMNS = 6
SELL_ROWS = 4
SELL_CELL_W = 34
SELL_CELL_H = 35
SELL_SLOTS = SELL_COLUMNS * SELL_ROWS      # 24

# Altura de linha nas listas da janela de amigos.
FRIEND_ROW_HEIGHT = 15

# ---------------------------------------------------------------------------
# Regiões lidas por comparação de imagem
# ---------------------------------------------------------------------------
#
# O jogo não expõe o texto destas duas listas na memória, e o projeto não tem
# OCR. A saída é comparar PIXELS: o bot recorta a região uma vez, quando sabe o
# que está escrito ali, e depois reconhece o mesmo texto comparando o recorte
# guardado com o que está na tela. Como a fonte, a posição e o fundo são sempre
# os mesmos, a comparação é confiável -- e específica do nick, que é justamente
# o que precisa ser distinguido.
#
# Formato: (dx, dy, largura, altura) relativo ao ponto de referência.

# Primeira entrada da Block list, em relação ao ponto "primeira_entrada".
BLOCK_ENTRY_REGION = (-42, -8, 150, 16)

# "[Nick]" de quem enviou o convite de time, em relação ao CENTRO do texto
# invariante "invite you to join the team,". O nick vem ANTES do texto, e um
# nick mais longo empurra o texto para a direita -- por isso a região é folgada
# à esquerda: cabe nick de até ~20 caracteres.
INVITE_NICK_REGION = (-205, -8, 128, 16)

# O item "Leave the team" NÃO é mais calculado por deslocamento.
#
# Existia aqui um `MENU_LEAVE_TEAM_OFFSET = (38, 66)`, somado à posição do
# retrato. O problema é que o menu do personagem tem um número VARIÁVEL de linhas
# -- "Leave the team" só aparece quando há time -- então o mesmo deslocamento caía
# em "PK Mode" dependendo do estado. Agora são duas coordenadas MEDIDAS e
# independentes, `own_portrait` e `menu_leave_team`, ambas no mapa de pontos
# acima. O template continua sendo tentado primeiro, porque imagem é mais forte
# que coordenada.


@dataclass
class SellGrid:
    # Geometria medida no cliente real. Não é para o jogador mexer: o bot
    # localiza a janela de venda por imagem e calcula a grade a partir dela.
    """Geometria da grade de itens na janela de venda do NPC.

    O truque central da venda: ao vender um item, os demais SOBEM uma posição.
    Clicar repetidamente na MESMA posição N drena tudo de N para frente e nunca
    toca nos slots 1..N-1. A proteção é geométrica, não uma lista de exceções.
    """

    origin_x: int = 450
    origin_y: int = 327
    cell_w: int = SELL_CELL_W
    cell_h: int = SELL_CELL_H
    columns: int = SELL_COLUMNS

    def slot_xy(self, slot: int, width: int = BASE_W, height: int = BASE_H) -> tuple[int, int]:
        idx = max(1, slot) - 1
        row, col = divmod(idx, self.columns)
        # A janela de venda é centralizada, então o slot 1 acompanha o centro.
        base = _from_base(self.origin_x, self.origin_y, C).at(width, height)
        return base[0] + col * self.cell_w, base[1] + row * self.cell_h


@dataclass
class Coords:
    """Coordenadas resolvidas para uma resolução específica."""

    resolution: str = VALIDATED_RESOLUTION
    width: int = BASE_W
    height: int = BASE_H

    server_rows: list[str] = field(default_factory=lambda: [
        "White Horse [NEW]",
        "Tiger Fish (WW)",
        "Sky Ice (GSM&BI)",
        "All Stars",
        "Light in the Darkness",
    ])
    server_aliases: dict[str, str] = field(default_factory=lambda: {
        "Giant Sky Medal": "Sky Ice (GSM&BI)",
        "Blue Ice": "Sky Ice (GSM&BI)",
        "Sky Ice": "Sky Ice (GSM&BI)",
        "Wild Wave(EE)": "Tiger Fish (WW)",
        "Wild Wave (EE)": "Tiger Fish (WW)",
        "Tiger Fish": "Tiger Fish (WW)",
        "White Horse": "White Horse [NEW]",
    })
    sell_grid: SellGrid = field(default_factory=SellGrid)

    # -- resolução de pontos ------------------------------------------------

    def point(self, nome: str) -> tuple[int, int]:
        spot = _SPOTS.get(nome)
        if spot is None:
            raise KeyError(f"ponto de tela desconhecido: '{nome}'")
        return spot.at(self.width, self.height)

    def __getattr__(self, nome: str) -> tuple[int, int]:
        """Permite `coords.enter_game` além de `coords.point("enter_game")`."""
        if nome in _SPOTS:
            return _SPOTS[nome].at(self.width, self.height)
        raise AttributeError(nome)

    @property
    def is_validated(self) -> bool:
        """True na resolução em que tudo foi medido em produção."""
        return self.resolution == VALIDATED_RESOLUTION

    # -- personagem ---------------------------------------------------------

    @property
    def char_slots(self) -> dict[str, tuple[int, int]]:
        """Plaquinhas de nome na tela de seleção.

        É na PLAQUINHA que se clica para escolher o personagem, não no corpo do
        modelo 3D: tamanho e posição do modelo variam por classe e gênero, a
        plaquinha não.
        """
        return {
            "Left": self.point("char_left"),
            "Center": self.point("char_center"),
            "Right": self.point("char_right"),
        }

    # -- servidores ---------------------------------------------------------

    def sell_slot_xy(self, slot: int) -> tuple[int, int]:
        """Coordenada do slot na janela de venda, nesta resolução."""
        return self.sell_grid.slot_xy(slot, self.width, self.height)

    @property
    def server_first_row_y(self) -> int:
        return _SERVER_FIRST_ROW.at(self.width, self.height)[1]

    @property
    def server_row_x(self) -> int:
        return _SERVER_FIRST_ROW.at(self.width, self.height)[0]

    @property
    def server_row_height(self) -> int:
        return SERVER_ROW_HEIGHT

    def normalize_server(self, nome: str) -> str:
        if nome in self.server_rows:
            return nome
        return self.server_aliases.get(nome, nome)

    def server_index(self, nome: str) -> int:
        alvo = self.normalize_server(nome)
        try:
            return self.server_rows.index(alvo)
        except ValueError:
            return -1

    def server_point(self, nome: str) -> tuple[int, int] | None:
        indice = self.server_index(nome)
        if indice < 0:
            return None
        x, y = _SERVER_FIRST_ROW.at(self.width, self.height)
        return x, y + indice * SERVER_ROW_HEIGHT

    @property
    def server_slots(self) -> dict[str, tuple[int, int]]:
        x, y = _SERVER_FIRST_ROW.at(self.width, self.height)
        return {
            nome: (x, y + i * SERVER_ROW_HEIGHT)
            for i, nome in enumerate(self.server_rows)
        }


# ---------------------------------------------------------------------------
# Âncoras por template
# ---------------------------------------------------------------------------
#
# Melhor que derivar por âncora de tela: LOCALIZAR o elemento por imagem e
# calcular os vizinhos a partir dele. Como a UI tem tamanho fixo, o
# deslocamento entre dois elementos da mesma janela é constante em qualquer
# resolução. Os valores abaixo foram medidos em 1024x768.
TEMPLATE_ANCHORS: dict[str, tuple[str, dict[str, tuple[int, int]]]] = {
    "login": ("state_login_screen.png", {
        "login_account": (90, -72),
        "login_password": (78, -42),
        "login_ok": (-17, 28),
    }),
    # Deslocamentos conferidos em DOIS prints de dimensões diferentes: o
    # espaçamento entre o título "Server List" e o botão Ok deu exatamente
    # (+68, +334) nos dois. É a confirmação de que a UI tem tamanho fixo.
    "server": ("state_server_list.png", {
        "server_first_row": (-148, 51),
        "server_ok": (68, 334),
        # +112 em x sobre o Ok, mesmo y -- ver `server_cancel` acima.
        "server_cancel": (180, 334),
    }),
    # Avisos que travam o login. Deslocamentos medidos em prints reais.
    # ATENÇÃO: "Connection failed" tem botão **Cancel**, não Ok.
    "login_busy": ("state_login_busy.png", {"ok": (15, 124)}),
    "conn_failed": ("state_conn_failed.png", {"cancel": (7, 131)}),
    # "Acquiring server IP address." -- servidores fora do ar.
    #
    # O deslocamento até o Ok deu (+33, +134). Compare com o do erro de senha,
    # (+21, +133): o mesmo dy. É o mesmo quadro de mensagem, então a medição de um
    # confirma a do outro.
    #
    # O template ainda NÃO existe em data/templates -- e o bot funciona sem ele:
    # a detecção por flag de modal persistente (ver `login.py`) já fecha este
    # aviso. Recortar `state_acquiring_ip.png` do texto "Acquiring server IP
    # address." só deixa o reconhecimento imediato em vez de esperar a
    # persistência.
    "acquiring_ip": ("state_acquiring_ip.png", {"ok": (33, 134)}),
    # Convite de time. O template é SÓ O TEXTO INVARIANTE ("invite you to join
    # the team,").
    #
    # O template antigo (`state_team_invite.png`) foi recortado com o nick de
    # quem convidava dentro dele -- "[BlazesTamer] invite you to..." -- então só
    # casava com convite daquele personagem. Era por isso que a conta de reset
    # nunca aceitava nada: o convite chegava, e o reconhecimento simplesmente
    # não encontrava a caixa. O arquivo novo tem apenas a parte que não muda.
    "team_invite": ("state_team_invite_texto.png", {
        "ok": (-113, 132),
        "cancel": (34, 132),
    }),
    # Janela de venda do NPC: grade de 6 colunas x 4 linhas, passo 34 x 35.
    # "It's precious item, please confirm!" -- a caixa que trava a venda.
    #
    # O template é SÓ O TEXTO INVARIANTE, recortado de um print do usuário
    # (192x17). O texto não muda nunca; o que muda atrás dele é a janela de
    # venda, e por isso a moldura e os botões não servem de template -- a caixa
    # de confirmação e a janela de venda usam botões idênticos (Ok/Cancel contra
    # Sell/Cancel), e um template de botão casaria nos dois.
    #
    # Medido nos quatro prints do processo de venda:
    #     com a caixa na tela .... 1.000
    #     sem a caixa (3 prints) . 0.454 a 0.483
    #
    # O deslocamento até o Ok foi medido no mesmo print. ATENÇÃO À ÂNCORA: o
    # `find_template` devolve o CENTRO do casamento, não o canto -- é a mesma
    # convenção dos outros grupos daqui (repare no dx negativo do "sell"). Medido
    # do canto seria (+53,+149); do centro do template de 192x17 é (-43,+141),
    # que é o valor abaixo. Trocar a âncora sem trocar o número poria o clique
    # 96 px à direita do botão.
    #
    # Derivar o Ok do texto encontrado, em vez de usar a coordenada fixa
    # `confirm_ok`, é o que faz o clique acompanhar a caixa se ela aparecer em
    # outro lugar -- e ela é desenhada por cima da janela de venda, que
    # comprovadamente NÃO aparece sempre no mesmo lugar (é por isso que existe o
    # `_sell_anchor`).
    "precious": ("state_precious_item.png", {"ok": (-43, 141)}),

    # "Are you sure to delete [...]?" -- a caixa do DELETADOR (ecossistema APP).
    #
    # Mesma lição da caixa acima, e pelo mesmo motivo: o template é só o TÍTULO
    # ("Delete Co...", 90x21), nunca o botão. Os botões Ok e Cancel desta caixa
    # são idênticos entre si em forma e cor -- um template de botão casaria nos
    # dois, e clicar em Cancel não apaga (mal menor) enquanto o inverso não é
    # verdade em outras caixas.
    #
    # Medido no print do usuário (`data/templates/entrada/confirmar.png`):
    #     com a caixa na tela ....... 1.000
    #     sem a caixa (inventário) .. 0.391
    #
    # O deslocamento foi medido no mesmo print, pelo brilho das colunas: o Ok
    # fica em (439,364) e o centro do título em (515,192) -- logo (-76,+172) a
    # partir do CENTRO, que é o que o `find_template` devolve.
    "delete_confirm": ("state_delete_confirm.png", {"ok": (-76, 172)}),
    "sell": ("state_sell_window.png", {
        "slot1": (-90, 70),
        "sell_button": (-68, 488),
        "cancel_button": (64, 488),
    }),
    # Lista de amigos. Usada para registrar o nick do reseter na aba Block --
    # é lá que se consegue digitar um nome arbitrário e tê-lo como entrada
    # selecionável, mesmo com o jogador longe.
    "friend_list": ("state_friend_list.png", {
        "aba_friends": (-80, 33),
        "aba_foe": (-1, 33),
        "aba_block": (79, 33),
        "primeira_entrada": (-85, 98),
        "whisper": (-84, 409),
        "add": (85, 409),
        "team_up": (-84, 432),
    }),
    "block_list": ("state_block_list.png", {
        "aba_friends": (-80, 33),
        "aba_block": (79, 33),
        "primeira_entrada": (-85, 98),
        "botao_block": (-84, 413),
        "botao_remove": (1, 413),
        "botao_options": (85, 413),
    }),
    "block_input": ("state_block_input.png", {
        "campo_nick": (-6, 67),
        "ok": (-69, 88),
        "cancel": (76, 88),
    }),
    # Painel "Surroundings" (arredores). Deslocamentos medidos a partir do
    # título da janela. A aba NPC é obrigatória: a lista abre em "Player" e os
    # NPCs, que é o que interessa, só aparecem na outra aba.
    "surroundings": ("state_surroundings.png", {
        "tab_player": (-112, 32),
        "tab_npc": (-31, 32),
        "first_result": (-97, 99),
        "search_field": (131, 377),
        "refresh": (-123, 372),
        "close": (-25, 372),
    }),
    # Janela de diálogo de NPC. Os LINKS variam de posição conforme o texto, e
    # por isso são localizados por template próprio, não por deslocamento.
    "dialogue": ("state_dialogue.png", {
        "close": (-1, 453),
    }),
    "char": ("btn_enter_game.png", {
        "char_left": (-117, -95),
        "char_center": (0, -95),
        "char_right": (118, -95),
    }),
}


def parse_resolution(texto: str) -> tuple[int, int]:
    """Converte '1280x720' em (1280, 720)."""
    partes = texto.lower().replace("*", "x").split("x")
    if len(partes) != 2:
        raise ValueError(f"resolução inválida: '{texto}'")
    return int(partes[0]), int(partes[1])


def coords_for_size(width: int, height: int) -> Coords:
    """Coordenadas para o tamanho REAL da área de cliente.

    Este é o caminho certo em produção. Confiar na resolução escolhida na
    interface causou um bug difícil: o jogo estava em 1280x960 enquanto a
    configuração dizia 1024x768, então as coordenadas medidas estavam válidas
    para uma tela que não era a que estava aberta. Medir a janela elimina a
    possibilidade de divergência.

    O tamanho zerado cai para 1024x768. Isso acontece de verdade: `GetClientRect`
    devolve 0x0 numa janela que está sendo criada ou destruída, e sem esta
    proteção TODAS as coordenadas passariam a ser calculadas a partir de zero --
    ou seja, o bot clicaria no canto superior esquerdo da tela.

    ATENÇÃO HISTÓRICA: esta função estava DUPLICADA neste arquivo, e a segunda
    definição -- sem a proteção acima -- sobrescrevia esta silenciosamente. A
    proteção existia no código e não valia nada.
    """
    if width <= 0 or height <= 0:
        width, height = BASE_W, BASE_H
    return Coords(resolution=f"{width}x{height}", width=width, height=height)


def coords_for_window(hwnd: int) -> Coords | None:
    """Coordenadas derivadas do tamanho REAL da janela do jogo.

    Preferir isto a qualquer resolução configurada. O motivo é concreto: se a
    configuração disser 1024x768 e o jogo estiver rodando em 1280x960, todas as
    coordenadas saem erradas -- e o erro é silencioso, porque nada no bot
    percebe a divergência. Medir a janela elimina essa classe de problema e
    dispensa o jogador de informar a resolução.
    """
    try:
        import win32gui

        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        largura, altura = right - left, bottom - top
        if largura <= 0 or altura <= 0:
            return None
        return coords_for_size(largura, altura)
    except Exception:
        return None


def get_coords(resolution: str = VALIDATED_RESOLUTION) -> Coords:
    """Coordenadas para uma resolução qualquer.

    Não recusa resoluções fora da lista: o cliente oferece muitas e o modelo de
    ancoragem vale para todas. A lista serve para a interface oferecer opções.
    """
    try:
        largura, altura = parse_resolution(resolution)
    except ValueError:
        largura, altura = BASE_W, BASE_H
        resolution = VALIDATED_RESOLUTION
    return Coords(resolution=resolution, width=largura, height=altura)
