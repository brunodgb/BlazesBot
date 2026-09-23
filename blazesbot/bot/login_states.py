"""
Detecção da tela de login em CAMADAS, do sinal mais confiável ao menos.

Lição aprendida na prática: depender só de reconhecimento de imagem foi um
erro. O `PrintWindow` do Windows retorna SUCESSO mesmo produzindo quadro
totalmente preto em clientes DirectX que não estão em primeiro plano. Com a
imagem em branco, todo template falha e o bot conclui "tela desconhecida" para
sempre -- sem nunca agir.

Agora há três camadas independentes:

  1. MEMÓRIA  -- nome do personagem e posição legíveis = está no mundo.
                 Não depende de imagem nenhuma.
  2. TÍTULO   -- o cliente escreve o servidor no título ao conectar:
                   'Talisman Online | ver.6400'                    (antes)
                   'Talisman Online | Light in the Darkness | ...'  (depois)
                 Separa a fase de login/servidor da fase de fila/personagem.
  3. IMAGEM   -- templates, só quando a captura realmente funciona.

Quando a camada 3 não está disponível, o login continua funcionando às cegas
guiado pelas camadas 1 e 2 -- que é como os bots de referência sempre
funcionaram.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import win32gui

from ..core.memory import Memory
from ..core.vision import TemplateLibrary, capture_window, find_template

THRESHOLD = 0.80

# Templates cuja AUSÊNCIA não impede nada: existe um caminho alternativo para
# cada um, e o alternativo é que garante o funcionamento.
#
# `state_acquiring_ip.png` -- o aviso "Acquiring server IP address.", que aparece
# quando os servidores estão fora do ar. Sem o template, ele é fechado pela flag
# de modal persistente (ver `login._modal_travando_antes_do_servidor`). Com o
# template, o reconhecimento é imediato em vez de esperar a persistência.
OPTIONAL_TEMPLATES = frozenset({"state_acquiring_ip.png"})

# Elementos que só existem DENTRO do jogo. Recortados de prints reais em
# 1024x768; margem de separação medida em ~0.77 contra as telas de login.
IN_WORLD_TEMPLATES = ("state_in_world_bar.png", "state_in_world_chat.png")


class LoginScreen(str, Enum):
    """Telas possíveis entre abrir o cliente e estar no mundo."""

    IN_WORLD = "no mundo"
    CHAR_SELECT = "seleção de personagem"
    QUEUE = "fila de login"
    CONN_INTERRUPTED = "conexão interrompida"
    LOGIN_ERROR = "erro de usuário ou senha"
    LOGIN_BUSY = "servidor de login ocupado"
    CONN_FAILED = "falha de conexão"
    CONNECTING = "conectando ao servidor (espera legítima)"
    SERVER_IP = "servidores fora do ar (Acquiring server IP address)"
    TEAM_INVITE = "convite de time"
    SERVER_LIST = "lista de servidores"
    LOGIN_SCREEN = "tela de login"
    CONNECTED = "conectado ao servidor (fila ou personagem)"
    PRE_SERVER = "antes do servidor (login ou lista)"
    NO_CAPTURE = "sem captura de imagem"
    UNKNOWN = "desconhecida"


class Phase(str, Enum):
    """Em que ponto do roteiro de login estamos.

    Serve de memória de curto prazo para quando a imagem não está disponível:
    o bot sabe o que acabou de fazer e portanto o que esperar em seguida.

    ENTERING cobre fila E seleção de personagem de propósito. Sem imagem é
    impossível distinguir as duas, e a ação correta é a mesma nos dois casos:
    tentar entrar periodicamente. Se ainda estiver na fila, a tentativa é
    inofensiva; quando a fila acabar, ela funciona.
    """

    CREDENTIALS = "credenciais"
    SERVER = "servidor"
    ENTERING = "aguardando entrar (fila ou personagem)"


@dataclass
class Detection:
    screen: LoginScreen
    point: tuple[int, int] | None = None
    server_in_title: str | None = None
    capture_ok: bool = False
    title: str = ""
    # Quadro usado nesta detecção. Guardado de propósito: capturar duas vezes
    # para a mesma decisão é caro e, pior, a segunda captura pode falhar
    # sozinha -- foi exatamente isso que travou o bot na seleção de personagem.
    frame: object = None

    @property
    def connected(self) -> bool:
        """Já passou da fase de login/servidor?"""
        return self.server_in_title is not None


# ORDEM DE TESTE -- e a ordem importa muito.
#
# Os AVISOS vêm primeiro, antes de identificar a tela de fundo. Motivo: o aviso
# "Connection interrupted." aparece SOBRE a tela de personagens e SOBRE a lista
# de servidores. Com a ordem invertida, o template de "Create Char" casava, o bot
# concluía "seleção de personagem" e o aviso nunca era fechado -- ficava clicando
# em Enter Game atrás de uma caixa modal que bloqueava tudo.
#
# NOTA: o `cancel.bmp` que vem dos bots do T-R0XX NÃO é usado. Ele casa com o
# botão "Cancel" da LISTA DE SERVIDORES também, não só o da fila -- e por isso a
# detecção de fila original dá falso positivo na tela de servidores.
# ===========================================================================
# O STATUS DO SERVIDOR NA LISTA -- "Online" x "Offline"
# ===========================================================================
#
# MEDIDO no print 1:1 de 22/09/2026, o MESMO recorte nas quatro linhas da lista
# ("Light in the Darkness" Offline, os outros três Online):
#
#     linha Offline (a real) ....... 1.000
#     linhas Online ................ 0.713   (as três, idênticas)
#
# Margem de +0.287, e o limiar fica no meio. O template foi recortado da linha
# SELECIONADA (fundo azul do realce), que é o único estado em que o bot faz esta
# pergunta -- ele seleciona a linha antes de olhar.
TEMPLATE_SERVIDOR_OFFLINE = "server_offline.png"
LIMIAR_DO_OFFLINE = 0.85

# Do NOME do servidor até a coluna de status, e a largura da busca: o nome
# centra em x=345 e o status ocupa 476-509 no mesmo print. A janela é generosa
# porque "Online" tem 6 letras e "Offline" tem 7.
DO_NOME_ATE_O_STATUS = 147
LARGURA_DA_BUSCA_DO_STATUS = 120

# ===========================================================================
# A POLÍTICA DA LISTA DE SERVIDORES -- quantas vezes insistir, quanto esperar
# ===========================================================================
#
# Mora aqui, junto das medições da MESMA tela, e não em `login.py`: são três
# números sobre como lidar com a lista, e o `LoginSequence` só os consome.

# Cliques na linha antes de desistir da seleção -- clique engolido é comum aqui.
TENTATIVAS_DE_SELECAO = 3

# Voltas à mesma tela antes de sair pelo Cancel -- a REDE do reconhecimento do
# nome, para o Ok engolido e a captura cega.
VOLTAS_NA_LISTA_DE_SERVIDORES = 3

# Entre uma ida à lista e a seguinte com o servidor fora do ar. 30 s e não os
# ~1,5 s do laço: 854 idas em 9 min martelavam o servidor de autenticação por
# nada (medido em 22/09/2026). Ver `docs/decisoes/login-e-relogin.md`.
ESPERA_PELO_SERVIDOR_FORA_DO_AR = 30.0


# ===========================================================================
# O NOME DO SERVIDOR NA LINHA -- para NÃO depender de índice fixo
# ===========================================================================
#
# `Coords.server_rows` é uma lista ESTÁTICA, e a lista do jogo MUDA: servidor
# entra em manutenção e some da tela, e todos os índices abaixo dele deslocam.
# Em 22/09/2026 isso fez a conta entrar em OUTRO servidor.
#
# A saída é ler o NOME de cada linha. MEDIDO em CINCO prints 1:1 de 22/09/2026 --
# listas de 4 e de 3 servidores, e três da mesma lista com uma seleção diferente
# em cada, para o recorte ser cobrado NOS DOIS ESTADOS. Cada template contra
# cada linha dos cinco:
#
#     pior ACERTO ......... 0.999
#     melhor FALSO ........ 0.442
#     margem .............. +0.557   (limiar 0.80: +0.358 do falso, +0.199 do acerto)
#
# DOIS ACHADOS que mudaram o recorte, os dois medidos e nenhum suposto:
#
#   1. O ESTADO NÃO IMPORTA. Recorte do selecionado x do não selecionado dá
#      margem de +0.586 x +0.581 -- 0.005 de diferença. `TM_CCOEFF_NORMED`
#      normaliza o contraste, então o mesmo template serve para os dois fundos e
#      NÃO é preciso binarizar nem guardar duas versões por servidor.
#   2. LARGURA FIXA É MELHOR que recorte ajustado ao texto de cada nome: o pior
#      acerto subiu de 0.971 para 0.999. O recorte tem 140 px (o centro ± 70) e a
#      busca 160 (± 80) -- os 20 px de folga absorvem o deslize da janela, que
#      variou 3 px entre os prints.
LIMIAR_DO_NOME_DO_SERVIDOR = 0.80

# Meia-largura da busca em torno do CENTRO do nome, e não coluna absoluta: o
# ponto da linha já vem resolvido por âncora/resolução, então derivar dele faz a
# busca acompanhar. 80 px cobre o nome mais largo medido (279-408, centro 344).
MEIA_LARGURA_DO_NOME = 80

_SIGNATURES: list[tuple[LoginScreen, tuple[str, ...]]] = [
    # --- avisos modais, sempre primeiro ---
    #
    # A ORDEM DENTRO DESTE BLOCO É DO MAIS ESPECÍFICO PARA O MAIS GENÉRICO, e
    # isso não é estilo: é correção de um defeito MEDIDO em 18/08/2026.
    #
    # `state_conn_prefix` casa com a palavra "Connection", que é comum a
    # "Connection interrupted" E a "Connection failed". Com ele em primeiro,
    # a tela de FALHA DE CONEXÃO era reconhecida como CONEXÃO INTERROMPIDA:
    #
    #     login-conn-failed.png:  state_conn_prefix = 0.835  (casava, 1o)
    #                             state_conn_failed = 0.994  (certo, mas 4o)
    #
    # O estrago não é só o rótulo errado. `_handle_conn_interrupted` clica no
    # deslocamento do botão **Ok**, e essa caixa tem **Cancel**, em outro lugar
    # -- o clique cai no vazio e o login fica parado para sempre. Era o sintoma
    # relatado como "não reconhece o erro".
    #
    # A tela "Connecting to the server" marca 0.787 no mesmo template genérico,
    # a 0.013 do limiar: estava a um fio de cair na mesma armadilha.
    (LoginScreen.CONN_FAILED, ("state_conn_failed.png",)),
    (LoginScreen.CONNECTING, ("state_connecting.png",)),
    (LoginScreen.LOGIN_ERROR, ("state_login_error.png",)),
    (LoginScreen.LOGIN_BUSY, ("state_login_busy.png",)),
    # O GENÉRICO POR ÚLTIMO entre os modais. `state_conn_prefix` casa nas duas
    # variantes de "Connection interrupted." -- é para isso que ele existe --
    # mas por casar só no prefixo ele PRECISA ser o último a opinar.
    (LoginScreen.CONN_INTERRUPTED, ("state_conn_prefix.png", "state_conn_interrupted.png")),
    (LoginScreen.SERVER_IP, ("state_acquiring_ip.png",)),
    # --- telas de fundo ---
    (LoginScreen.CHAR_SELECT, ("state_char_select.png", "btn_enter_game.png")),
    (LoginScreen.QUEUE, ("state_queue.png", "state_queue_busy.png")),
    (LoginScreen.SERVER_LIST, ("state_server_list.png",)),
    (LoginScreen.LOGIN_SCREEN, ("state_login_screen.png",)),
]


class LoginStateDetector:
    def __init__(
        self,
        hwnd: int,
        memory: Memory,
        templates: TemplateLibrary | None = None,
    ) -> None:
        self.hwnd = hwnd
        self.memory = memory
        self.templates = templates or TemplateLibrary(Path("data") / "templates")
        self.capture_failures = 0
        self.capture_successes = 0

    # -- camada 2: título --------------------------------------------------

    def window_title(self) -> str:
        """Título da janela, limpo.

        O cliente às vezes devolve o título com quebra de linha no fim, o que
        atrapalha a extração do nome do servidor.
        """
        try:
            return (win32gui.GetWindowText(self.hwnd) or "").strip()
        except Exception:
            return ""

    def server_in_title(self) -> str | None:
        """Extrai o servidor do título, se o cliente já conectou.

        'Talisman Online | ver.6400'                   -> None
        'Talisman Online | Light in the Darkness | ...' -> 'Light in the Darkness'
        """
        title = self.window_title()
        if "|" not in title:
            return None
        parts = [p.strip() for p in title.replace("\n", " ").split("|")]
        if len(parts) >= 3 and parts[1] and not parts[1].lower().startswith("ver."):
            return parts[1]
        return None

    # -- camada 1: memória -------------------------------------------------

    def memory_says_in_world(self) -> bool:
        """No mundo segundo a memória.

        Usa QUALQUER um dos três sinais em vez de exigir todos. Exigir nome E
        posição juntos era frágil: se só uma das leituras falhasse, o bot
        concluía que não havia entrado e continuava clicando em "Enter Game" --
        já dentro do jogo, o que faz o personagem sair andando pelo mapa.
        """
        if self.memory.char_name():
            return True
        if self.memory.position() is not None:
            return True
        hp = self.memory.hp()
        return hp is not None and hp > 0

    def image_says_in_world(self, frame=None) -> bool:
        """No mundo segundo a imagem, pelo HUD.

        Barra de ação e abas de chat só existem dentro do jogo. Serve de rede
        de segurança quando a leitura de memória falha.
        """
        if frame is None:
            frame = capture_window(self.hwnd)
        if frame is None:
            return False
        for name in IN_WORLD_TEMPLATES:
            template = self.templates.load(name)
            if template is None:
                continue
            if find_template(frame, template, threshold=THRESHOLD) is not None:
                return True
        return False

    def in_world(self) -> bool:
        """Verdadeiro se qualquer camada confirmar que o personagem entrou."""
        if self.memory_says_in_world():
            return True
        return self.image_says_in_world()

    # -- detecção ----------------------------------------------------------

    def detect(self) -> Detection:
        title = self.window_title()
        server = self.server_in_title()

        # Camada 1 -- memória, sem depender de imagem nenhuma.
        if self.memory_says_in_world():
            return Detection(LoginScreen.IN_WORLD, None, server, True, title)

        # Camada 3 -- imagem, se houver.
        frame = capture_window(self.hwnd)
        if frame is None:
            self.capture_failures += 1
            # Camada 2 -- sem imagem, o título ainda diz muito.
            screen = LoginScreen.CONNECTED if server else LoginScreen.PRE_SERVER
            return Detection(screen, None, server, False, title)

        self.capture_successes += 1

        # Camada 3a -- HUD do jogo. Testado antes das telas de login porque é
        # a confirmação mais importante: enquanto o bot não sabe que entrou,
        # ele continua clicando e faz o personagem andar.
        if self.image_says_in_world(frame):
            return Detection(LoginScreen.IN_WORLD, None, server, True, title, frame)

        for state, names in _SIGNATURES:
            for name in names:
                template = self.templates.load(name)
                if template is None:
                    continue
                point = find_template(frame, template, threshold=THRESHOLD)
                if point is not None:
                    return Detection(state, point, server, True, title, frame)

        # Captura funcionou mas nenhuma assinatura casou: tela de transição.
        screen = LoginScreen.CONNECTED if server else LoginScreen.UNKNOWN
        return Detection(screen, None, server, True, title, frame)

    def find_button(
        self,
        template_name: str,
        frame=None,
    ) -> tuple[int, int] | None:
        """Localiza um botão. Reaproveita `frame` se ele for passado."""
        template = self.templates.load(template_name)
        if template is None:
            return None
        if frame is None:
            frame = capture_window(self.hwnd)
        if frame is None:
            return None
        return find_template(frame, template, threshold=THRESHOLD)

    def _modelo_do_servidor(self, nome: str):
        """O template do NOME daquele servidor, ou `None` se não existir.

        O arquivo é `servidor_<slug>.png`, e o slug sai do próprio nome. Cada
        servidor precisa do seu recorte -- quem não tem simplesmente não é
        reconhecido, e o login cai no índice estático de sempre.
        """
        slug = re.sub(r"[^a-z0-9]+", "_", nome.lower()).strip("_")
        return self.templates.load(f"servidor_{slug}.png")

    def sabe_reconhecer(self, nome: str) -> bool:
        """Existe recorte para reconhecer este servidor na lista?"""
        return self._modelo_do_servidor(nome) is not None

    def linha_do_servidor(self, frame, nome: str, primeira, linhas: int,
                          altura: int = 20) -> int | None:
        """Em QUE LINHA da lista aquele servidor está. `None` = não está.

        É o que tira o login da dependência de índice fixo: a lista do jogo
        muda (manutenção tira um servidor e os de baixo sobem), e contar linhas
        a partir de uma lista estática põe a conta em OUTRO servidor.

        `None` também quando não dá para olhar -- sem quadro ou sem recorte
        daquele nome. Quem chama distingue os dois casos por `sabe_reconhecer`:
        "não está na lista" manda cancelar, "não sei reconhecer" não.
        """
        modelo = self._modelo_do_servidor(nome)
        if frame is None or modelo is None:
            return None
        x0 = max(0, primeira[0] - MEIA_LARGURA_DO_NOME)
        for indice in range(linhas):
            y = primeira[1] + indice * altura
            regiao = (x0, max(0, y - altura // 2),
                      MEIA_LARGURA_DO_NOME * 2, altura)
            if find_template(frame, modelo,
                             threshold=LIMIAR_DO_NOME_DO_SERVIDOR,
                             region=regiao) is not None:
                return indice
        return None

    def servidor_offline(self, frame, primeira, indice: int,
                         altura: int = 20) -> bool:
        """A coluna "Server Status" daquela LINHA diz **Offline**?

        Pela linha escolhida, e não pela tela: quase sempre há algum servidor
        offline na lista, e olhar a tela inteira derrubaria a conta pelo status
        alheio.

        `False` quando não dá para olhar (sem quadro, sem template) -- não saber
        não é motivo para cancelar um login.

        Mora AQUI, e não no `LoginSequence`, porque é leitura de TELA DE LOGIN:
        é o mesmo papel do `find_button` e das assinaturas deste módulo. O
        `LoginSequence` decide o que fazer com a resposta; ele não lê pixel.
        """
        if frame is None:
            return False
        modelo = self.templates.load(TEMPLATE_SERVIDOR_OFFLINE)
        if modelo is None:
            return False
        y = primeira[1] + indice * altura
        regiao = (
            primeira[0] + DO_NOME_ATE_O_STATUS - LARGURA_DA_BUSCA_DO_STATUS // 2,
            max(0, y - altura // 2),
            LARGURA_DA_BUSCA_DO_STATUS,
            altura,
        )
        return find_template(frame, modelo, threshold=LIMIAR_DO_OFFLINE,
                             region=regiao) is not None

    def capture_working(self) -> bool:
        """Se a captura já funcionou alguma vez nesta sessão."""
        return self.capture_successes > 0

    def missing_templates(self) -> list[str]:
        """Templates que faltam e cuja falta ATRAPALHA.

        Os opcionais ficam de fora: avisar sobre eles em todo login viraria ruído
        permanente, e ruído permanente é o que faz um aviso deixar de ser lido.
        Quem quiser saber deles chama `optional_missing()`.
        """
        expected = {name for _, names in _SIGNATURES for name in names}
        expected.add("btn_enter_game.png")
        expected.update(IN_WORLD_TEMPLATES)
        expected -= OPTIONAL_TEMPLATES
        return sorted(n for n in expected if self.templates.load(n) is None)

    def optional_missing(self) -> list[str]:
        """Templates opcionais ausentes -- há um caminho alternativo para cada."""
        return sorted(n for n in OPTIONAL_TEMPLATES
                      if self.templates.load(n) is None)
