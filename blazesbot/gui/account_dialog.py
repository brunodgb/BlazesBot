"""
Editor de configuração de uma conta.

ORGANIZAÇÃO -- e ela segue a pergunta "isto muda quando eu trocar de cave?"

  Personagem  -> não muda. Montaria, pet, limiares de poção.
  Teclas      -> não muda. A tecla da poção é a mesma em qualquer lugar.
  Bewitcher Cave -> muda. Boss, rota, reset de time, venda.

Separar assim faz o jogador configurar teclas e poções UMA vez e reaproveitar em
tudo. Quando entrarem outras caves, cada uma ganha a própria aba ao lado da BC,
sem tocar nas duas primeiras.

EXPLICAÇÕES ficam nos ícones "?", não na tela. Texto solto espalhado faz o olho
pular os campos, que são o que a pessoa vem fazer aqui.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..bot.combate import SEGUNDOS_DA_POCAO_DE_VIDA
from ..config import (
    LIMITE_DO_NOME_DO_GRUPO,
    MAX_BOLSAS,
    MINIMO_DE_ESPERA_DO_APP_MS,
    MINIMO_DELAY_MS,
    MODO_FADA_DA_HH,
    MODO_SOLO_DA_HH,
    MOUNT_SPEEDS,
    PASSOS_DO_APP,
    PET_FEED_MINUTES,
    PET_FEED_MINUTOS_MAX,
    PET_FEED_MINUTOS_MIN,
    SELL_CLICK_OPTIONS,
    SLOTS_POR_BOLSA,
    Account,
    BotConfig,
    mount_multiplier,
    ms_para_segundos,
    normalizar_modo_do_reset,
    segundos_para_ms,
)
from .help_tip import HelpTip
from .key_capture import KeyCapture
from .theme import STYLESHEET, TEXT_DIM
from .widgets import PercentBar

AJUDA_ESCONDER = (
    "Esconde os outros jogadores da tela.\n"
    "\n"
    "Como configurar no jogo:\n"
    "\n"
    "  1. Aperte ESC\n"
    "  2. Clique em Keys\n"
    "  3. Procure a tecla de esconder personagens\n"
    "     (F12 costuma ser o padrão)\n"
    "\n"
    "PARA QUE SERVE AQUI: o catador de loot clica no CHÃO, e\n"
    "outro personagem em cima do cadáver muda o que o clique\n"
    "acerta. O bot segura esta tecla e abre o chat, o que faz\n"
    "o esconder GRUDAR até o fim da sessão — e refaz isso\n"
    "antes de cada entrada na cave, porque apertar a tecla de\n"
    "novo desfaz.\n"
    "\n"
    "É OPCIONAL: sem tecla configurada o bot não mexe nisso."
)

AJUDA_HOTBAR = (
    "Faz o bot voltar à página 1 da barra de atalhos,\n"
    "que é a usada pelo bot.\n"
    "\n"
    "Como configurar no jogo:\n"
    "\n"
    "  1. Aperte ESC\n"
    "  2. Clique em Keys\n"
    "  3. Procure “Main Hotkey Page 1” e escolha uma tecla livre\n"
    "  4. Apague as teclas de Page 2 e Page 3 — sem elas, nada\n"
    "     tira a barra da página 1 por acidente\n"
    "\n"
    "É OPCIONAL: sem tecla configurada o bot continua clicando\n"
    "no botão, como sempre fez."
)

AJUDA_ESC = (
    "Clique no campo e aperte a tecla que você usa no jogo.\n"
    "\n"
    "ESC apaga o atalho e deixa como “não usar”.\n"
    "\n"
    "Aceita: 1-9 e 0, A-Z, F1-F12, teclado numérico,\n"
    "SPACE, TAB, ENTER, SHIFT, CTRL, ALT."
)


class AccountDialog(QDialog):
    def __init__(self, conta: Account, parent: QWidget | None = None,
                 config: BotConfig | None = None) -> None:
        super().__init__(parent)
        self.conta = conta
        self.st = conta.settings
        # A CONFIGURAÇÃO INTEIRA, e não só esta conta: o seletor de reseter é
        # montado a partir das OUTRAS contas (as marcadas como "aceitar convites
        # de time"). Opcional para não quebrar quem constrói o diálogo sozinho
        # -- sem ela o seletor mostra apenas o que já está gravado.
        self.config = config
        # (rótulo, campo) de cada tecla da aba Teclas. Preenchido por
        # `_bloco_teclas` e lido por `_tecla_em_uso`, que é o que impede a
        # MESMA tecla de acabar em duas funções. Tem que existir ANTES de as
        # abas serem montadas, porque é durante a montagem que ele é populado.
        self._campos_de_tecla: list[tuple[str, KeyCapture]] = []

        self.setWindowTitle(f"Configuração de '{conta.login or 'nova conta'}'")
        self.setStyleSheet(STYLESHEET)
        self.resize(720, 660)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(14, 12, 14, 12)
        raiz.setSpacing(10)
        raiz.addWidget(self._cabecalho())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scroll(self._aba_personagem()), "🧙  Personagem")
        self.tabs.addTab(self._scroll(self._aba_teclas()), "⌨  Teclas")
        self.tabs.addTab(self._scroll(self._aba_app()), "⚡  APP")
        self.tabs.addTab(self._scroll(self._aba_bc()), "🕯  Bewitcher Cave")
        self.tabs.addTab(self._scroll(self._aba_hh()), "🗡  HH")
        raiz.addWidget(self.tabs, 1)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok = botoes.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Aplicar")
        ok.setObjectName("primary")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._aplicar)
        botoes.rejected.connect(self.reject)
        raiz.addWidget(botoes)

        self._carregar()
        self._atualizar_rotulos()

    # ==================================================================
    # Auxiliares de layout
    # ==================================================================

    @staticmethod
    def _scroll(inner: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(inner)
        return area

    @staticmethod
    def _grupo(titulo: str, ajuda: str) -> tuple[QGroupBox, QFormLayout]:
        """Grupo com um "?" no canto, sem texto explicativo solto."""
        box = QGroupBox(titulo)
        fora = QVBoxLayout(box)
        fora.setContentsMargins(12, 8, 12, 10)
        topo = QHBoxLayout()
        topo.addStretch()
        topo.addWidget(HelpTip(ajuda))
        fora.addLayout(topo)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        fora.addLayout(form)
        return box, form

    @staticmethod
    def _nota(html: str) -> QLabel:
        """Nota curta dentro de um grupo, no tom secundário do tema."""
        rot = QLabel(html)
        rot.setObjectName("hint")
        rot.setWordWrap(True)
        return rot

    @staticmethod
    def _com_ajuda(widget: QWidget, ajuda: str) -> QWidget:
        """Campo com um "?" ao lado."""
        wrap = QWidget()
        linha = QHBoxLayout(wrap)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(7)
        linha.addWidget(widget, 1)
        linha.addWidget(HelpTip(ajuda))
        return wrap

    def _cabecalho(self) -> QWidget:
        wrap = QWidget()
        linha = QHBoxLayout(wrap)
        linha.setContentsMargins(0, 0, 0, 0)
        titulo = QLabel(self.conta.login or "nova conta")
        titulo.setObjectName("title")
        linha.addWidget(titulo)
        linha.addStretch()
        self.selo = QLabel()
        self.selo.setObjectName("badge")
        linha.addWidget(self.selo)
        return wrap

    # ==================================================================
    # Aba: Personagem  (vale em qualquer atividade)
    # ==================================================================

    def _aba_personagem(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)

        # -- Identificação da janela -----------------------------------
        box, f = self._grupo("Personagem no jogo", (
            "O nick do personagem desta conta.\n"
            "\n"
            "Para que serve: o bot renomeia a janela do jogo com o nick e\n"
            "guarda o nick aqui. Na próxima vez que você abrir o bot, ele\n"
            "varre os clientes abertos, encontra o que tem este personagem\n"
            "e assume o controle dele — sem abrir outro cliente e sem\n"
            "passar pela fila de login, que em dia cheio passa de três\n"
            "horas.\n"
            "\n"
            "Você pode preencher à mão, e é o que resolve a primeira vez.\n"
            "Depois disso o bot SOBRESCREVE este campo a cada login com o\n"
            "nome que ler na memória do jogo — então trocar de personagem\n"
            "nesta conta se corrige sozinho.\n"
            "\n"
            "Precisa ser único entre as contas: dois nicks iguais fariam\n"
            "duas contas disputarem a mesma janela."
        ))
        self.in_nick = QLineEdit()
        self.in_nick.setPlaceholderText("o bot preenche no primeiro login")
        self.in_nick.textChanged.connect(self._atualizar_rotulos)
        f.addRow("Nick do meu personagem:", self.in_nick)
        outer.addWidget(box)

        # -- Função da conta -------------------------------------------
        box, f = self._grupo("Função desta conta", (
            "Login e relogin automático valem para toda conta ativa.\n"
            "\n"
            "BC Farm é marcado na lista de contas, não aqui.\n"
            "\n"
            "Aceitar convites de time serve para a conta que você deixa\n"
            "parada só para resetar a cave das outras: ela clica em Ok\n"
            "sozinha e não precisa fazer mais nada além de estar online.\n"
            "Funciona com BC Farm desligado."
        ))
        self.ck_aceitar = QCheckBox("Aceitar convites de time (conta de reset)")
        f.addRow(self.ck_aceitar)
        self.ck_catador = QCheckBox("Catar loot do chão (pet sem auto pick)")
        self.ck_catador.setToolTip(
            "Depois de matar o boss, clica no chão para recolher os itens.\n"
            "Só faz sentido na conta cujo pet NÃO tem a skill de auto pick —\n"
            "com o pet certo ele já recolhe sozinho."
        )
        f.addRow(self.ck_catador)
        outer.addWidget(box)

        # -- Montaria ---------------------------------------------------
        box, f = self._grupo("Montaria", (
            "OBRIGATÓRIA. O personagem precisa TER a montaria e andar\n"
            "sempre montado: toda a rota da BC foi medida assim, e o bot\n"
            "monta antes de qualquer deslocamento e remonta se ela cair.\n"
            "\n"
            "A velocidade escala o tempo que o bot espera em cada trecho\n"
            "da rota.\n"
            "\n"
            "Informe a real: declarar mais do que você tem faz o bot\n"
            "concluir que travou antes da hora. Declarar menos só o deixa\n"
            "mais paciente."
        ))
        self.cb_mount = QComboBox()
        for pct in MOUNT_SPEEDS:
            self.cb_mount.addItem(f"{pct}%   ({mount_multiplier(pct):.1f}x)", pct)
        self.cb_mount.currentIndexChanged.connect(self._atualizar_rotulos)
        f.addRow("Velocidade:", self.cb_mount)
        outer.addWidget(box)

        # -- Pet --------------------------------------------------------
        box, f = self._grupo("Pet", (
            "Pet sem comida DESAPARECE, e um pet que sumiu no meio da cave\n"
            "estraga a run sem avisar. Por isso não existe liga/desliga:\n"
            "com o farm ativo o pet é obrigatório e o bot alimenta sempre.\n"
            "\n"
            "A conta do jogo: cada comida dá 5 de felicidade, o máximo é\n"
            "100, e o pet perde 1 a cada 10 minutos. Ou seja, uma comida\n"
            f"cobre {PET_FEED_MINUTES} minutos — que é o intervalo padrão aqui.\n"
            "\n"
            "“Usar ao ligar o bot” só é útil se você não acabou de\n"
            "alimentar à mão; sem isso o bot espera o intervalo cheio."
        ))
        self.ck_pet_login = QCheckBox("Invocar o pet depois de cada login")
        f.addRow(self.ck_pet_login)
        self.ck_pet_start = QCheckBox("Usar comida de pet ao ligar o bot")
        f.addRow(self.ck_pet_start)
        # Mesma faixa e mesmo passo do campo na web (40..60, de 5 em 5) --
        # ver `PET_FEED_MINUTOS_MIN`/`MAX`.
        # GRUPO: rótulo só para organizar a lista de contas. Não é o time do
        # APP (`time_logins`) nem a party da cave (`accept_team_invites`) --
        # o bot não muda nada por causa dele. Espelha o campo da web.
        self.in_grupo = QLineEdit()
        self.in_grupo.setMaxLength(LIMITE_DO_NOME_DO_GRUPO)
        self.in_grupo.setPlaceholderText("sem grupo")
        self.in_grupo.setToolTip(
            "Rótulo só para VOCÊ organizar a lista de contas: as que tiverem "
            "o mesmo grupo aparecem juntas.\n\n"
            "NÃO é o time do modo APP nem a party da cave — o bot não muda "
            "nada por causa deste campo.\n\n"
            "Vazio deixa a conta fora de qualquer grupo."
        )
        f.addRow("Grupo:", self.in_grupo)

        self.cb_pet_feed = QComboBox()
        for m in range(PET_FEED_MINUTOS_MIN, PET_FEED_MINUTOS_MAX + 1, 5):
            self.cb_pet_feed.addItem(f"a cada {m} minutos", m)
        f.addRow("Comida de pet:", self.cb_pet_feed)
        outer.addWidget(box)

        # -- Poções -----------------------------------------------------
        box, f = self._grupo("Poções e cura", (
            "As poções “de batalha” são itens diferentes no jogo, com\n"
            "recarga própria. O bot usa essa em combate e a normal fora\n"
            "dele — usar a de batalha fora do combate desperdiça item caro.\n"
            "\n"
            "O bot NÃO usa poção de mana. A mana só é olhada para decidir\n"
            "se o AoE entra na rotação do boss (aba Bewitcher Cave).\n"
            "\n"
            "Abortar a luta com HP baixo é preferível a morrer: morrer\n"
            "custa tempo de volta ao ponto.\n"
            "\n"
            "O “mínimo para iniciar” é ALVO, não gatilho: ao entrar na\n"
            "cave o bot se cura ATÉ ele e só então começa a andar.\n"
            "\n"
            "A ordem é SS de cura primeiro, depois poção. A SS é\n"
            "instantânea e não é item comprado — se ela já fechar a\n"
            "diferença, nenhuma poção é gasta. Nem toda classe tem SS de\n"
            "cura; sem a tecla de Super Skill configurada o bot vai\n"
            "direto para a poção.\n"
            "\n"
            "CADA POÇÃO LEVA 15 SEGUNDOS e andar cancela o efeito. Por\n"
            "isso o personagem fica parado esse tempo depois de cada uma:\n"
            "sair andando gastaria o item e receberia uma fração da cura.\n"
            "\n"
            "“Preferir a skill de cura” economiza poção, que é recurso\n"
            "comprado. A skill custa só mana e recarga."
        ))
        self.bar_bhp = PercentBar("HP", 90, tipo="hp")
        f.addRow("Poção em combate:", self.bar_bhp)
        self.bar_emerg = PercentBar("HP", 25, tipo="hp")
        f.addRow("Abortar a luta abaixo de:", self.bar_emerg)
        self.bar_hp = PercentBar("HP", 85, tipo="hp")
        f.addRow("Mínimo de HP para iniciar a Cave:", self.bar_hp)
        self.lbl_cura = QLabel()
        self.lbl_cura.setObjectName("hint")
        self.lbl_cura.setWordWrap(True)
        f.addRow("", self.lbl_cura)
        self.bar_hp.valueChanged.connect(self._atualizar_rotulos)
        outer.addWidget(box)

        # -- Bolsas -----------------------------------------------------
        box, f = self._grupo("Bolsas", (
            "Quantas bolsas VÁLIDAS este personagem tem. Cada uma dá 30\n"
            f"espaços, e o máximo é {MAX_BOLSAS} (a base mais duas Expand Bag).\n"
            "\n"
            "Por que você informa em vez de o bot ler: uma Expand Bag\n"
            "marcada como “Expired” continua aparecendo na interface do\n"
            "jogo mas NÃO recebe item. Deduzir a capacidade da tela erraria\n"
            "exatamente no caso que importa — e errar aqui significa perder\n"
            "drop sem ninguém notar.\n"
            "\n"
            "O gatilho de voltar para vender fica na aba Bewitcher Cave,\n"
            "junto do resto da venda."
        ))
        self.cb_bolsas = QComboBox()
        for n in range(1, MAX_BOLSAS + 1):
            self.cb_bolsas.addItem(
                f"{n} bolsa{'s' if n > 1 else ''}   ({n * SLOTS_POR_BOLSA} espaços)", n
            )
        self.cb_bolsas.currentIndexChanged.connect(self._atualizar_rotulos)
        f.addRow("Quantidade de bolsas:", self.cb_bolsas)
        self.lbl_bolsas = QLabel()
        self.lbl_bolsas.setObjectName("hint")
        self.lbl_bolsas.setWordWrap(True)
        f.addRow("", self.lbl_bolsas)
        outer.addWidget(box)

        outer.addStretch()
        return page

    # ==================================================================
    # Aba: Teclas  (vale em qualquer atividade)
    # ==================================================================

    def _tecla_em_uso(self, tecla: str,
                      exceto: KeyCapture | None = None) -> str | None:
        """O rótulo do campo que já usa esta tecla, ou None se estiver livre.

        Passada a cada `KeyCapture` da aba Teclas. Existe porque o jogo não
        permite a mesma tecla em duas funções -- e uma repetição aqui produziria
        um erro silencioso: o bot mandaria a tecla achando que faz uma coisa
        enquanto o jogo faz outra.
        """
        alvo = (tecla or "").upper()
        if not alvo:
            return None
        for rotulo, campo in self._campos_de_tecla:
            if campo is exceto:
                continue          # o próprio campo não conflita consigo
            if campo.key().upper() == alvo:
                return rotulo
        return None

    def _bloco_teclas(self, titulo: str, ajuda: str,
                      campos: list[tuple[str, ...]]) -> QGroupBox:
        """Grupo de atalhos em duas colunas.

        Cada campo é `(rótulo, atributo)` ou `(rótulo, atributo, ajuda)`. Com o
        terceiro item, o campo ganha um "?" só dele, ao lado -- para quando a
        explicação é do CAMPO e não do grupo inteiro (o caso do atalho de
        hotbar, que exige mexer no Keys Setting do jogo).
        """
        box = QGroupBox(titulo)
        fora = QVBoxLayout(box)
        fora.setContentsMargins(12, 8, 12, 10)
        topo = QHBoxLayout()
        topo.addStretch()
        topo.addWidget(HelpTip(ajuda + "\n\n" + AJUDA_ESC))
        fora.addLayout(topo)

        grade = QGridLayout()
        grade.setHorizontalSpacing(14)
        for i, campo in enumerate(campos):
            rotulo, attr = campo[0], campo[1]
            ajuda_do_campo = campo[2] if len(campo) > 2 else ""
            captura = KeyCapture(conflito=self._tecla_em_uso)
            setattr(self, attr, captura)
            # Registro dos campos de tecla da aba Teclas, para o verificador de
            # repetição saber quem existe. As teclas do APP ficam de fora de
            # propósito: lá a MESMA tecla se repete na sequência por desenho.
            self._campos_de_tecla.append((rotulo.rstrip(":"), captura))
            coluna = (i % 2) * 2
            grade.addWidget(QLabel(rotulo), i // 2, coluna,
                            Qt.AlignmentFlag.AlignRight)
            grade.addWidget(
                self._com_ajuda(captura, ajuda_do_campo) if ajuda_do_campo
                else captura,
                i // 2, coluna + 1)
        fora.addLayout(grade)
        return box

    @staticmethod
    def _hint_teclas() -> QLabel:
        """Aviso das duas regras do jogo que mais confundem quem configura."""
        rot = QLabel(
            "<b>Três regras do jogo que valem para todas as teclas:</b><br>"
            "• <b>Andar é sempre montado</b> — a tecla da montaria é "
            "<b>obrigatória</b>. Toda a rota da BC (tempos, tolerâncias, alcance "
            "de cada clique) foi medida montado; a pé o trajeto passa do dobro e "
            "o trem de mobs da cave alcança. O bot monta antes de qualquer "
            "deslocamento e remonta se a montaria cair no caminho.<br>"
            "• <b>Montado nada funciona</b> — poção, comida de pet, invocar pet, "
            "cura, buff e itens de retorno exigem estar a pé. O bot desmonta "
            "sozinho antes de cada uma e <b>remonta em seguida</b>. A "
            "<b>única</b> exceção é a skill de velocidade, que age na "
            "montaria.<br>"
            "• <b>Skill em si mesmo precisa de alvo</b> — o bot aperta <b>F1</b> "
            "antes da cura e dos buffs, para selecionar o próprio personagem. "
            "Sem isso a skill sairia no mob selecionado.<br><br>"
            "<b>Guild Token</b> tem preferência sobre a pedra de retorno: ele não "
            "gasta item (recarga de 10 min). A pedra é o plano B, e o bot "
            "recompra na venda cada uma que usar."
        )
        rot.setObjectName("hint")
        rot.setWordWrap(True)
        return rot

    def _aba_teclas(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)

        aviso = QLabel("Clique no campo e aperte a tecla.  ESC = não usar.")
        aviso.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        linha = QHBoxLayout()
        linha.addWidget(aviso)
        linha.addWidget(HelpTip(AJUDA_ESC))
        linha.addStretch()
        outer.addLayout(linha)

        outer.addWidget(self._bloco_teclas("Ataque", (
            "Todas as teclas deste bloco são usadas em ROTAÇÃO, na ordem\n"
            "em que aparecem aqui: aperta uma, na próxima investida aperta\n"
            "a seguinte, e ao chegar no fim volta ao começo. Uma investida\n"
            "a cada 0,5 s. Deixe em branco as que não usar.\n"
            "\n"
            "O AoE entra na rotação, não substitui ninguém. Com Ataque 1 e\n"
            "AoE configurados, a sequência fica 1, AoE, 1, AoE...\n"
            "\n"
            "NÃO existe controle de recarga, de propósito: skill em recarga\n"
            "simplesmente não sai e a rotação segue para a próxima. O que\n"
            "importa é o personagem estar atacando sem parar.\n"
            "\n"
            "O AoE só é usado se tiver tecla: sem tecla, a opção não\n"
            "existe. Muitas classes não têm AoE, e um interruptor à parte\n"
            "seria só uma forma de errar. Nos 4 guardas ele sai da rotação\n"
            "(veja a aba Bewitcher Cave), e abaixo do limite de mana também."
        ), [
            ("Ataque 1:", "k_atk1"), ("Ataque 2:", "k_atk2"),
            ("Ataque 3:", "k_atk3"), ("Ataque 4:", "k_atk4"),
            ("AoE:", "k_aoe"), ("Break Soul:", "k_break"),
        ]))

        outer.addWidget(self._bloco_teclas("Cura e buffs", (
            "A Super Skill é a cura mais forte de várias classes — o\n"
            "Wizard, por exemplo, se cura com ela. Depois de matar o boss\n"
            "o bot dispara poção, Super Skill e sentar em sequência\n"
            "rápida: assim as duas curas correm ao mesmo tempo e sentar\n"
            "amplifica a regeneração de HP e de mana.\n"
            "\n"
            "Os buffs são aplicados depois de cada login."
        ), [
            ("Super Skill:", "k_super"), ("Skill de cura:", "k_heal"),
            ("Reviver aliado:", "k_revive"),
            ("Buff 1:", "k_buff1"), ("Buff 2:", "k_buff2"),
            ("Buff 3:", "k_buff3"), ("Buff 4:", "k_buff4"),
        ]))

        outer.addWidget(self._bloco_teclas("Consumíveis", (
            "A poção “de batalha” é um item diferente, com recarga\n"
            "própria. Deixe em branco se você não usa.\n"
            "\n"
            "Não há poção de mana: o bot não usa. A mana só é consultada\n"
            "para decidir se o AoE entra na rotação do boss.\n"
            "\n"
            "Poção de HP não é comprada pelo bot: poções têm níveis e\n"
            "cada cidade vende só até um certo nível. Você abastece com a\n"
            "que quiser — e é para isso que serve proteger os primeiros\n"
            "slots na venda, já que poções são vendáveis."
        ), [
            ("Poção de HP:", "k_hp"), ("HP de batalha:", "k_bhp"),
            ("Comida de pet:", "k_petfood"), ("Pedra de retorno:", "k_stone"),
        ]))

        outer.addWidget(self._bloco_teclas("Deslocamento e interface", (
            "Os padrões são os do próprio jogo, em System Interface >\n"
            "Keys Setting:\n"
            "\n"
            "  Sit/Stand ............ X\n"
            "  Shift to Next Target . TAB\n"
            "  Item Interface ....... I\n"
            "  Community Interface .. F   (lista de amigos)\n"
            "\n"
            "A lista de amigos é usada no reset de time: é lá que o nick\n"
            "do reseter é registrado.\n"
            "\n"
            "BARRA DE ATALHOS p.1 é OPCIONAL, e vale configurar: o jogo\n"
            "deixa ligar uma tecla a cada página da barra, e a da página 1\n"
            "leva DIRETO ao destino, com um toque. Sem ela o bot faz o\n"
            "que sempre fez: dois cliques no botão de subir, que sobe e\n"
            "PARA no 1."
        ), [
            ("Montaria:", "k_mount"), ("Skill de velocidade:", "k_speed"),
            ("Guild Token:", "k_guild"), ("Invocar pet:", "k_pet"),
            ("Sentar:", "k_sit"), ("Próximo alvo:", "k_next"),
            ("Auto-seleção:", "k_self"),
            ("Seguir (HH + Fada):", "k_follow"),
            ("Inventário:", "k_inv"), ("Lista de amigos:", "k_fl"),
            ("Atalho Hotbar 1:", "k_hotbar", AJUDA_HOTBAR),
            ("Esconder jogadores:", "k_esconder", AJUDA_ESCONDER),
        ]))

        outer.addWidget(self._hint_teclas())

        outer.addStretch()
        return page

    # ==================================================================
    # Aba: APP  (macro de teclado, independente do farm da cave)
    # ==================================================================

    def _aba_app(self) -> QWidget:
        """Editor da macro do modo APP.

        Duas colunas por linha, e nada além disso: a tecla e quanto esperar depois
        dela. É o formato do UoPilot.

            1   TAB   800 ms
            2   1     800 ms
            3   1     800 ms
            4   5     500 ms

        NÃO EXISTE MAIS A COLUNA "usar". Antes cada linha tinha uma caixa própria,
        e havia duas maneiras de a mesma linha não rodar: sem tecla, ou com tecla e
        desmarcada. A segunda parecia configurada sem estar. Agora a regra é uma:
        linha com tecla roda, linha sem tecla não. Quem liga e desliga é só a caixa
        "Ativar o modo APP nesta conta".

        O rótulo "send" também saiu de cada linha. Ele era decoração fixa,
        repetida dezesseis vezes, ocupando uma coluna inteira para dizer o que a
        aba já diz.
        """
        page = QWidget()
        outer = QVBoxLayout(page)

        box, f = self._grupo("Modo APP", (
            "Um executor de macro de teclado, no estilo do UoPilot.\n"
            "\n"
            "Cada linha é uma tecla e um tempo de espera. O executor manda\n"
            "a tecla, espera o tempo daquela linha, e passa para a\n"
            "seguinte. Na última, recomeça da primeira, em laço contínuo\n"
            "até você desligar.\n"
            "\n"
            "Linha COM tecla roda; linha sem tecla é ignorada. ESC num\n"
            "campo de tecla limpa a linha. TAB é aceito como tecla.\n"
            "\n"
            "ISTO NÃO TEM LIGAÇÃO COM O FARM DA CAVE. É um sistema\n"
            "separado: ele manda tecla e espera, e não lê memória, não\n"
            "reconhece tela e não navega mapa. As abas Teclas e Bewitcher\n"
            "Cave não influenciam nada aqui, e o modo APP não muda nada\n"
            "lá.\n"
            "\n"
            "A ÚNICA EXCEÇÃO é o pet: antes de cada volta o modo APP\n"
            "confere se ele está ativo e, se tiver caído, aperta a tecla\n"
            "de invocar pet da aba Teclas. Num cliente em que a memória\n"
            "não lê, ele não faz nada disso e a macro roda igual.\n"
            "\n"
            "LIGAR E DESLIGAR É NA LISTA DE CONTAS, na coluna APP — vale\n"
            "na hora do clique, com o bot rodando. Aqui fica só a\n"
            "sequência. Se o BC farm estiver ligado na mesma conta, o modo\n"
            "APP tem preferência: os dois disputariam o teclado."
        ))
        outer.addWidget(box)

        # LIMPEZA DA BOLSA, só do ecossistema APP. O BC resolve bolsa cheia
        # vendendo; aqui, que roda longe de vendedor, deletar é a única saída.
        limpeza = QGroupBox("Limpeza da bolsa")
        lf = QHBoxLayout(limpeza)
        lf.setContentsMargins(12, 8, 12, 10)
        lf.addWidget(QLabel("Apagar o lixo a cada"))
        self.sp_app_limpar = QSpinBox()
        self.sp_app_limpar.setRange(0, 999)
        self.sp_app_limpar.setFixedWidth(80)
        lf.addWidget(self.sp_app_limpar)
        lf.addWidget(QLabel("voltas da sequência   (0 = nunca)"))
        lf.addStretch()
        lf.addWidget(HelpTip(
            "A cada tantas voltas, o bot abre o inventário com a tecla de\n"
            "Inventário da aba Teclas e apaga os itens que reconhecer como\n"
            "lixo, comparando com os modelos salvos.\n"
            "\n"
            "Ele tem no máximo 10 segundos para isso. Passou disso, volta a\n"
            "rodar a macro e continua de onde parou na volta seguinte.\n"
            "\n"
            "0 = nunca apagar nada.\n"
            "\n"
            "ANTES DE CONFIAR NISSO, use o botão 'Conferir modelos de\n"
            "exclusão' na aba Diagnóstico: ele fotografa a sua bolsa e\n"
            "DESENHA o que seria apagado, sem apagar nada. Deletar não tem\n"
            "desfazer."))
        outer.addWidget(limpeza)

        # TRAVA DE POSIÇÃO -- trava o personagem na posição em que o APP foi
        # iniciado. Ele anda de pé, sem montaria, se mover; e a cada 30 voltas
        # sem se mover, dá um passo lateral de 6 pixels e volta. Desligue para
        # permitir que o caractere ande livremente (ex.: reposicionar manual).
        trava = QGroupBox("Trava de posição")
        tf = QHBoxLayout(trava)
        tf.setContentsMargins(12, 8, 12, 10)
        tf.addWidget(QLabel("Travar posição ao iniciar o APP"))
        self.cb_app_travar = QCheckBox()
        self.cb_app_travar.setChecked(True)
        tf.addWidget(self.cb_app_travar)
        tf.addWidget(QLabel("shuffle a cada"))
        self.sp_app_shuffle = QSpinBox()
        self.sp_app_shuffle.setRange(1, 999)
        # Passo de 5 (igual ao `step` na web): o padrão é 30 voltas, e de 1 em 1
        # seriam 30 toques para sair do zero.
        self.sp_app_shuffle.setSingleStep(5)
        self.sp_app_shuffle.setValue(30)
        self.sp_app_shuffle.setFixedWidth(60)
        tf.addWidget(self.sp_app_shuffle)
        tf.addWidget(QLabel("voltas sem movimento"))
        tf.addStretch()
        tf.addWidget(HelpTip(
            "Salva a posição do personagem quando o modo APP começa e devolve\n"
            "ele andando (sem montaria) se ele se mover mais de 1 unidade.\n"
            "A cada 30 voltas sem movimento, dá um passo lateral de 6 pixels\n"
            "e volta — anti-AFK leve.\n"
            "\n"
            "Desligue para permitir reposicionamento manual durante o APP.\n"
            "Requer leitura de memória; sem ela, a trava é ignorada."))
        outer.addWidget(trava)

        grade_box = QGroupBox("Sequência")
        grade_fora = QVBoxLayout(grade_box)
        grade_fora.setContentsMargins(12, 8, 12, 10)

        LARGURA_NUMERO = 28
        LARGURA_TECLA = 120
        LARGURA_ESPERA = 120

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(10)
        for texto, largura, alinhamento in (
            ("#", LARGURA_NUMERO, Qt.AlignmentFlag.AlignRight),
            ("tecla", LARGURA_TECLA, Qt.AlignmentFlag.AlignLeft),
            ("esperar", LARGURA_ESPERA, Qt.AlignmentFlag.AlignLeft),
        ):
            rot = QLabel(texto)
            rot.setFixedWidth(largura)
            rot.setAlignment(alinhamento | Qt.AlignmentFlag.AlignVCenter)
            rot.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
            cabecalho.addWidget(rot)
        cabecalho.addStretch()
        grade_fora.addLayout(cabecalho)

        grade = QGridLayout()
        grade.setHorizontalSpacing(10)
        grade.setVerticalSpacing(4)
        # A grade não deve esticar as colunas: com larguras fixas iguais às do
        # cabeçalho, rótulo e campo ficam alinhados de verdade.
        grade.setColumnStretch(3, 1)

        # ==============================================================
        # A LINHA 0: o TAB, e o tempo depois dele
        # ==============================================================
        #
        # Pedido do usuário em 26/08/2026: *"como a macro 0, mas sem poder
        # editar o botão e não pode colocar em outro lugar, sempre será a
        # primeira, e o tempo sim será editável"*.
        #
        # A TECLA É ESPELHO, NÃO CÓPIA: ela mostra o que estiver na aba Teclas em
        # "Próximo alvo". Escrever "TAB" fixo aqui faria a tela mentir para quem
        # trocou a tecla — o bot apertaria uma e a tela mostraria outra.
        zero = QLabel("0")
        zero.setFixedWidth(LARGURA_NUMERO)
        zero.setAlignment(Qt.AlignmentFlag.AlignRight
                          | Qt.AlignmentFlag.AlignVCenter)
        zero.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")

        self.app_tecla_do_tab = QLineEdit()
        self.app_tecla_do_tab.setReadOnly(True)
        self.app_tecla_do_tab.setFixedWidth(LARGURA_TECLA)
        self.app_tecla_do_tab.setToolTip(
            "A tecla de 'Próximo alvo' da aba Teclas. O bot aperta esta tecla "
            "sozinho quando o alvo morre — ela não é uma linha da macro e não "
            "sai de lugar.")

        self.sp_app_espera_tab = QSpinBox()
        self.sp_app_espera_tab.setRange(MINIMO_DE_ESPERA_DO_APP_MS, 10000)
        # 100 ms, igual ao `step` do mesmo campo na web (`PASSO_ESPERA_APP`):
        # é a granularidade útil de um delay de macro, e o mesmo campo não pode
        # andar diferente em cada interface.
        self.sp_app_espera_tab.setSingleStep(100)
        self.sp_app_espera_tab.setSuffix(" ms")
        self.sp_app_espera_tab.setValue(1000)
        self.sp_app_espera_tab.setFixedWidth(LARGURA_ESPERA)
        self.sp_app_espera_tab.setToolTip(
            "Quanto esperar entre o TAB e a linha 1. Curto demais, a primeira "
            "skill da rotação se perde.")
        self.sp_app_espera_tab.valueChanged.connect(self._atualizar_previa_app)

        grade.addWidget(zero, 0, 0)
        grade.addWidget(self.app_tecla_do_tab, 0, 1)
        grade.addWidget(self.sp_app_espera_tab, 0, 2)

        self.app_linhas: list[tuple[KeyCapture, QSpinBox]] = []
        for i in range(PASSOS_DO_APP):
            linha = i + 1          # a linha 0 ocupa a primeira da grade
            numero = QLabel(f"{i + 1}")
            numero.setFixedWidth(LARGURA_NUMERO)
            numero.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
            numero.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")

            tecla = KeyCapture()
            tecla.setFixedWidth(LARGURA_TECLA)
            tecla.keyChanged.connect(self._atualizar_previa_app)

            espera = QSpinBox()
            espera.setRange(MINIMO_DE_ESPERA_DO_APP_MS, 10000)
            espera.setSingleStep(100)   # ver `sp_app_espera_tab`
            espera.setSuffix(" ms")
            espera.setValue(800)
            espera.setFixedWidth(LARGURA_ESPERA)
            espera.valueChanged.connect(self._atualizar_previa_app)

            grade.addWidget(numero, linha, 0)
            grade.addWidget(tecla, linha, 1)
            grade.addWidget(espera, linha, 2)
            self.app_linhas.append((tecla, espera))
        grade_fora.addLayout(grade)
        outer.addWidget(grade_box)

        # Prévia: mostra exatamente a ordem em que as teclas vão sair. Sem ela é
        # fácil deixar um buraco no meio e não perceber.
        self.lbl_previa_app = QLabel()
        self.lbl_previa_app.setObjectName("hint")
        self.lbl_previa_app.setWordWrap(True)
        outer.addWidget(self.lbl_previa_app)

        outer.addStretch()
        return page

    def _atualizar_previa_app(self, *_args) -> None:
        """Prévia da macro: as linhas com tecla, na ordem, e a volta completa."""
        ativas = [(t.key(), e.value()) for t, e in self.app_linhas if t.key()]
        # A PRÉVIA NÃO OLHA MAIS SE O MODO ESTÁ LIGADO. A caixa de ligar saiu
        # desta janela e foi para a lista de contas; aqui só se edita a sequência,
        # e a prévia descreve o que ela FARIA -- ligada ou não.
        if not ativas:
            self.lbl_previa_app.setText(
                "Nenhuma linha preenchida — o modo APP não teria o que enviar. "
                "Preencha a tecla e o tempo de cada linha abaixo."
            )
            return
        desenho = " → ".join(f"<b>{k}</b> ({ms}ms)" for k, ms in ativas)
        total = sum(ms for _k, ms in ativas)
        self.lbl_previa_app.setText(
            f"Sequência: {desenho} → recomeça da primeira.<br>"
            f"{len(ativas)} linha(s), volta completa em {total / 1000:.1f}s."
        )

    # ==================================================================
    # Aba: Bewitcher Cave  (específico desta atividade)
    # ==================================================================

    def _aba_bc(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)

        # -- Boss -------------------------------------------------------
        box, f = self._grupo("Boss", (
            "O boss tem segunda fase: o HP dele chega a zero e ele se\n"
            "transforma. Por isso HP do alvo em zero NÃO é vitória.\n"
            "\n"
            "O bot só sai da luta depois de insistir no TAB por vários\n"
            "segundos sem achar nada vivo, e de uma varredura final que\n"
            "tenta achar. Isso custa uns segundos por run e evita o erro\n"
            "caro: ir embora com o boss vivo e perder a run inteira.\n"
            "\n"
            "Curar naquele instante evita entrar na segunda fase com vida\n"
            "baixa, porque ela começa com o dano cheio.\n"
            "\n"
            "O AoE é usado SÓ no boss. Por ser instantâneo, ele soma dano\n"
            "sem o personagem parar para conjurar, e encurtar a luta do\n"
            "boss é o que encurta a run. Nos 4 guardas ele não entra: eles\n"
            "vêm um de cada vez, então área não acerta mais ninguém e a\n"
            "mana gasta ali é a que falta na segunda fase.\n"
            "\n"
            "O limite de mana evita ficar sem recurso justamente nessa fase:\n"
            "abaixo dele o AoE sai da rotação e o personagem continua\n"
            "atacando com as skills comuns, sem pausa nenhuma.\n"
            "\n"
            "O TAB não é apertado enquanto o boss está vivo -- ele já é o\n"
            "alvo, e trocar de alvo no meio da luta seria perder dano. Nos\n"
            "guardas é o contrário: um TAB depois de cada morte."
        ))
        self.in_boss = QLineEdit()
        f.addRow("Nome do boss:", self.in_boss)
        # EM MILISSEGUNDOS, como todo campo de tempo das duas interfaces (o
        # usuário pediu uma unidade só; havia segundos, ms e minutos na mesma
        # tela). O `attack_delay` continua `float` de SEGUNDOS no `config.json`
        # e no `combat.py` -- a conversão é na fronteira, em `_carregar`/`_gravar`.
        self.sp_delay = QSpinBox()
        self.sp_delay.setRange(MINIMO_DELAY_MS, 5000)
        self.sp_delay.setSingleStep(100)
        self.sp_delay.setSuffix(" ms")
        # 500 ms é o intervalo medido no jogo, e vale tanto para os guardas
        # quanto para o boss -- é o mesmo laço de ataque nos dois.
        self.sp_delay.setToolTip(
            "Tempo entre duas teclas da rotação de ataque. O medido no jogo é "
            "500 ms. Não é limite de recarga: skill em recarga não sai e a "
            "rotação segue para a próxima."
        )
        f.addRow("Intervalo entre skills:", self.sp_delay)
        self.ck_heal2 = QCheckBox("Curar antes da segunda fase")
        f.addRow(self.ck_heal2)
        self.bar_aoe_mana = PercentBar("Mana", 30, tipo="mp")
        self.lbl_aoe = QLabel("Usar AoE no boss com mana acima de:")
        f.addRow(self.lbl_aoe, self.bar_aoe_mana)
        outer.addWidget(box)

        # -- Rota -------------------------------------------------------
        box, f = self._grupo("Rota até o boss", (
            "A rota vai direto ao boss, sem atacar nenhum mob do caminho.\n"
            "Isso é o desenho do bot, não uma escolha: ignorar o trajeto é\n"
            "o que torna a run curta e o que evita morrer em pack.\n"
            "\n"
            "Matar os 4 guardas do covil também não é opção — é a fase que\n"
            "coloca o personagem em combate ali, e o boss vem depois dela."
        ))
        self.ck_speed = QCheckBox("Usar a skill de velocidade dentro da cave")
        f.addRow(self.ck_speed)
        f.addRow("", self._nota(
            "A skill de velocidade dura 30 s e recarrega em 6 min, e é a única "
            "que funciona montado. Por isso ela é usada <b>só dentro da cave</b>, "
            "onde o tempo custa vida — o bot cronometra a recarga em vez de "
            "apertar a tecla no vazio.<br><br>"
            "O caminho da cave (58 waypoints até o Altar Stone) fica no código, "
            "não aqui: ele é propriedade do jogo. O bot reconhece a área de cada "
            "waypoint e, se o personagem sair da rota por lag, rollback ou "
            "interferência, retoma pelo waypoint mais próximo."
        ))
        outer.addWidget(box)

        # -- Reset de time ----------------------------------------------
        box, f = self._grupo("Reset do boss", (
            "Fazendo a cave duas vezes seguidas sem mudar de time, o boss\n"
            "NÃO renasce — a instância continua com ele morto e a run é\n"
            "perdida. Entrar num time novo reseta a cave.\n"
            "\n"
            "Deixe uma conta parada, cadastrada aqui no bot só para\n"
            "login, e marque nela “aceitar convites de time”. Informe o\n"
            "nick dela neste campo.\n"
            "\n"
            "Campo vazio = não usa reset de time.\n"
            "\n"
            "Como o convite é enviado: o bot abre a lista de amigos,\n"
            "vai na aba Block, deixa ali só o nick do reseter e envia o\n"
            "time. É o único jeito de mirar alguém que está longe.\n"
            "Sair do time depois de entrar é automático — é pré-requisito\n"
            "do boss-rush solo, não uma preferência."
        ))
        # LISTA FECHADA, não texto livre. O reseter precisa ser uma conta
        # cadastrada AQUI: é isso que permite ao bot perceber que ela caiu e
        # segurar a entrada em vez de perder a run. Nick digitado à mão podia
        # apontar para qualquer coisa -- inclusive para nada.
        self.in_reset = QComboBox()
        self.in_reset.setToolTip(
            "Só aparecem contas marcadas como “aceitar convites de "
            "time”. Marque a flag na conta de reset para ela aparecer aqui."
        )
        f.addRow("Conta de reset:", self.in_reset)
        outer.addWidget(box)

        # -- Venda ------------------------------------------------------
        box, f = self._grupo("Venda e retorno", (
            "A grade da janela do NPC tem 6 colunas por 4 linhas. Ao\n"
            "tirar um item de um slot, os seguintes SOBEM para preencher\n"
            "o buraco.\n"
            "\n"
            "O bot clica repetidamente na mesma posição: tudo dali para\n"
            "frente passa por ali e é vendido, e os slots anteriores\n"
            "nunca se movem — portanto nunca são tocados. A proteção é\n"
            "geométrica, não uma lista de exceções.\n"
            "\n"
            "O GATILHO de ir vender é a contagem de runs da cave (campo\n"
            "“Vender a cada”). A leitura de itens da bolsa era imprecisa\n"
            "e o bot nunca entrava em venda por esse caminho.\n"
            "\n"
            "Os cliques vão de 6 em 6 porque cada linha da grade tem 6\n"
            "slots. Mais cliques cobrem bolsas com mais itens; sobrar\n"
            "clique é inofensivo.\n"
            "\n"
            "A posição da grade é medida automaticamente — nada para\n"
            "calibrar à mão."
        ))
        self.sp_runs = QSpinBox()
        self.sp_runs.setRange(1, 999)
        self.sp_runs.setSuffix(" runs")
        self.sp_runs.valueChanged.connect(self._atualizar_rotulos)
        f.addRow("Vender a cada:", self.sp_runs)
        self.ck_bag = QCheckBox("Sair para vender pelo espaço livre da bolsa")
        self.ck_bag.setChecked(False)
        self.ck_bag.setEnabled(False)
        self.ck_bag.setToolTip(
            "DESATIVADO. A leitura de itens da bolsa gerava gatilhos imprecisos "
            "e o bot nunca entrava em venda. O gatilho atual é por contagem de "
            "runs, no campo acima."
        )
        f.addRow(self.ck_bag)
        self.sp_slot = QSpinBox()
        self.sp_slot.setRange(1, 24)
        self.sp_slot.valueChanged.connect(self._atualizar_rotulos)
        f.addRow("Vender a partir do slot:", self.sp_slot)
        self.lbl_slot = QLabel()
        self.lbl_slot.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        f.addRow("", self.lbl_slot)
        self.cb_cliques = QComboBox()
        for n in SELL_CLICK_OPTIONS:
            self.cb_cliques.addItem(f"{n} cliques", n)
        f.addRow("Cliques por passada:", self.cb_cliques)
        self.ck_charm = QCheckBox("Comprar Return Charm")
        f.addRow(self.ck_charm)
        outer.addWidget(box)

        outer.addStretch()
        return page

    # ==================================================================
    # Rótulos derivados
    # ==================================================================

    def _atualizar_rotulos(self, *_args) -> None:
        nick = self.in_nick.text().strip()
        self.selo.setText(
            (f"Farm da {self.conta.cave_ligada.upper()} ligado"
             if self.conta.cave_ligada else "só login")
            + (f"  ·  {nick}" if nick else "")
        )

        slot = self.sp_slot.value()
        if slot <= 1:
            self.lbl_slot.setText("vende todos os itens da janela")
        else:
            self.lbl_slot.setText(
                f"protegidos: slots 1 a {slot - 1}"
            )

        # -- bolsas: mostra a conta feita, não só os números escolhidos ----
        bolsas = self.cb_bolsas.currentData() or 1
        capacidade = bolsas * SLOTS_POR_BOLSA
        self.lbl_bolsas.setText(
            f"{capacidade} espaços no total. O bot volta para vender a cada "
            f"<b>{self.sp_runs.value()}</b> run(s) da cave."
        )

        # -- cura: um alvo só, e o que ele custa em tempo -------------------
        #
        # Não há mais aviso em vermelho aqui. Ele existia porque dois limiares
        # podiam ser configurados de um jeito em que a poção nunca era usada; com
        # um número só isso deixou de ser possível.
        minimo = self.bar_hp.value()
        segundos = SEGUNDOS_DA_POCAO_DE_VIDA
        self.lbl_cura.setText(
            f"Ao entrar na cave, o bot se cura até <b>{minimo}%</b> antes de "
            f"andar. Usa a SS de cura primeiro (se houver tecla) e depois poção "
            f"de HP, uma de cada vez.<br><br>"
            f"Cada poção leva <b>{segundos:.0f} segundos</b> e <b>andar cancela "
            f"o efeito</b> — por isso o personagem fica parado esse tempo antes "
            f"de tomar a próxima ou começar o caminho. Quanto maior o mínimo, "
            f"mais poções e mais tempo parado."
        )

    # ==================================================================
    # Carregar / aplicar
    # ==================================================================

    def _aba_hh(self) -> QWidget:
        """A HH (Black Wind Camp Dungeon): quatro bosses e o reset.

        MENOR QUE A ABA DA BC DE PROPÓSITO. A rota não entra aqui -- ela é
        propriedade do jogo e mora em `bot/hh/mapa_hh.py`, medida waypoint por
        waypoint. Enquanto o caminho da BC morou no `config.json`, uma rota
        antiga gravada continuou sendo usada depois de a certa ser medida, e era
        impossível perceber porque tudo parecia configurado.
        """
        page = QWidget()
        outer = QVBoxLayout(page)

        # -- Reset ------------------------------------------------------
        box, f = self._grupo("Reset da cave (obrigatório)", (
            "A CAVE NÃO RENASCE SOZINHA. Sem desfazer e refazer o time, os\n"
            "quatro bosses não voltam e a run seguinte vem vazia. Isso é\n"
            "regra do jogo, não do bot.\n"
            "\n"
            "SOLO -- a conta de reset aceita o convite, o personagem entra e\n"
            "o time é desfeito na hora. Ela nunca entra na cave. É o mesmo\n"
            "que a Bewitcher Cave já faz.\n"
            "\n"
            "COM A FADA -- as duas entram juntas. A Fada acompanha o\n"
            "personagem e cura quando precisa; ao sair, o time é desfeito e\n"
            "refeito, e só então dá para entrar de novo.\n"
            "\n"
            "Sem conta de reset o bot roda, mas avisa no log: da segunda run\n"
            "em diante você entra numa cave sem boss."
        ))
        self.cb_hh_modo = QComboBox()
        self.cb_hh_modo.addItem("Solo — a conta de reset não entra",
                                MODO_SOLO_DA_HH)
        self.cb_hh_modo.addItem("Com a Fada — ela entra e cura",
                                MODO_FADA_DA_HH)
        f.addRow("Modo:", self.cb_hh_modo)
        self.in_hh_reset = QComboBox()
        self.in_hh_reset.setToolTip(
            "Só contas cadastradas NESTE bot. É isso que permite ao bot saber "
            "que ela caiu e segurar a entrada, em vez de entrar sem reset e "
            "perder a run."
        )
        f.addRow("Conta de reset:", self.in_hh_reset)
        outer.addWidget(box)

        # -- Combate ----------------------------------------------------
        box, f = self._grupo("Combate", (
            "São QUATRO bosses em sequência, um por trecho da cave. O bot\n"
            "desmonta antes de cada luta (montado o jogo recusa as skills) e\n"
            "remonta para andar.\n"
            "\n"
            "Quem encerra cada luta é a flag de combate do jogo, não um\n"
            "cronômetro. O limite abaixo é rede de segurança para o caso de a\n"
            "flag ficar presa em ligado."
        ))
        self.sp_hh_delay = QSpinBox()
        self.sp_hh_delay.setRange(MINIMO_DELAY_MS, 5000)
        self.sp_hh_delay.setSingleStep(100)
        self.sp_hh_delay.setSuffix(" ms")
        self.sp_hh_delay.setToolTip(
            "Tempo entre duas teclas da rotação de ataque. O medido no jogo é "
            "500 ms."
        )
        f.addRow("Intervalo entre skills:", self.sp_hh_delay)
        self.bar_hh_aoe = PercentBar("Mana", 30, tipo="mp")
        f.addRow("Usar AoE com mana acima de:", self.bar_hh_aoe)
        self.sp_hh_limpar = QSpinBox()
        self.sp_hh_limpar.setRange(0, 20)
        self.sp_hh_limpar.setToolTip(
            "A pé, o bot para a cada N waypoints e limpa os mobs do caminho.\n"
            "Montado ele não para -- e atravessar montado é a forma normal.\n"
            "0 desliga a limpeza."
        )
        f.addRow("Limpar mobs a cada (a pé):", self.sp_hh_limpar)
        outer.addWidget(box)

        # -- Venda ------------------------------------------------------
        box, f = self._grupo("Venda", (
            "O vendedor da HH é o Roaming Apothecary, do lado de FORA da\n"
            "cave -- a poucos passos da porta. Não gasta pedra de retorno\n"
            "nem token de guilda, diferente da Bewitcher Cave.\n"
            "\n"
            "Quem manda ir vender é a BOLSA (aba Personagem). O número de\n"
            "runs abaixo é o teto para quando a leitura da bolsa falhar."
        ))
        self.sp_hh_slot = QSpinBox()
        self.sp_hh_slot.setRange(1, 40)
        self.sp_hh_slot.setToolTip(
            "Os primeiros slots são equipamento e consumível. Vender a partir "
            "deles seria vender o que o bot precisa."
        )
        f.addRow("Vender a partir do slot:", self.sp_hh_slot)
        self.sp_hh_runs = QSpinBox()
        self.sp_hh_runs.setRange(1, 50)
        f.addRow("Vender no máximo a cada:", self.sp_hh_runs)
        outer.addWidget(box)

        outer.addStretch(1)
        return page

    def _montar_lista_de_reset(self, atual: str, combo=None) -> None:
        """Preenche o seletor de reseter e seleciona o que já está gravado.

        =================================================================
        POR QUE LISTA FECHADA
        =================================================================

        O campo era texto livre e o nick digitado podia apontar para qualquer
        coisa. O reseter tem que ser uma conta cadastrada NESTE bot por um
        motivo operacional: é isso que permite ao bot saber que ela caiu e
        segurar a entrada da cave em vez de entrar sem reset e perder a run.
        Um nick de outra máquina é invisível daqui.

        =================================================================
        TRÊS CASOS, E O TERCEIRO É O QUE NÃO PODE SUMIR
        =================================================================

        1. CONTA MARCADA E JÁ LOGADA -> entra na lista, selecionável.
        2. CONTA MARCADA QUE NUNCA LOGOU -> entra DESABILITADA. O nick é lido
           da memória no primeiro login, então ela ainda não tem um. Deixar
           selecionar gravaria string vazia -- que no `BCConfig.reset_nick`
           significa exatamente "não usar reset de time", ou seja, seria um
           jeito silencioso de DESLIGAR a função achando que ligou.
        3. O QUE ESTÁ GRAVADO E NÃO É NENHUMA DAS DUAS -> entra assim mesmo, no
           fim, marcado como problema, e continua SELECIONADO. Sumir com ele
           seria eu apagando a configuração de alguém sem avisar; mostrando, o
           usuário vê o que está errado e troca num clique.
        """
        combo = combo if combo is not None else self.in_reset
        combo.clear()
        combo.addItem("Nenhuma (sem reset de time)", "")

        atual = (atual or "").strip()
        conhecidos: set[str] = set()
        if self.config is not None:
            for conta in self.config.reset_accounts():
                if conta is self.conta:
                    continue           # ninguém reseta a si mesmo
                nick = conta.last_char_name.strip()
                if nick:
                    combo.addItem(f"{nick} — ({conta.login})", nick)
                    conhecidos.add(nick.lower())
                else:
                    combo.addItem(
                        f"({conta.login}) — ainda não logou, sem nick", "")
                    item = combo.model().item(combo.count() - 1)
                    if item is not None:
                        item.setEnabled(False)

        if atual and atual.lower() not in conhecidos:
            combo.addItem(f"{atual} — ⚠ não é conta de reset deste bot", atual)

        indice = combo.findData(atual) if atual else 0
        combo.setCurrentIndex(max(0, indice))

    def _carregar(self) -> None:
        st = self.st
        k, pet, pot, bc = st.keys, st.pet, st.potions, st.bc

        self.in_nick.setText(self.conta.last_char_name)
        self.in_grupo.setText(self.conta.grupo)
        self.ck_aceitar.setChecked(st.accept_team_invites)
        self.ck_catador.setChecked(st.usar_catador)

        idx = self.cb_mount.findData(st.mount_speed_pct)
        self.cb_mount.setCurrentIndex(idx if idx >= 0 else 0)

        self.ck_pet_login.setChecked(pet.summon_on_login)
        self.ck_pet_start.setChecked(pet.feed_on_start)
        idx = self.cb_pet_feed.findData(pet.feed_every_minutes)
        if idx < 0:
            self.cb_pet_feed.addItem(
                f"a cada {pet.feed_every_minutes} minutos", pet.feed_every_minutes
            )
            idx = self.cb_pet_feed.count() - 1
        self.cb_pet_feed.setCurrentIndex(idx)

        self.bar_hp.setValue(pot.hp_pct)
        self.bar_bhp.setValue(pot.battle_hp_pct)
        self.bar_emerg.setValue(pot.emergency_pct)

        idx = self.cb_bolsas.findData(st.bags.bolsas)
        self.cb_bolsas.setCurrentIndex(idx if idx >= 0 else 0)

        self.sp_app_limpar.setValue(st.app.apagar_lixo_a_cada)
        self.cb_app_travar.setChecked(st.app.travar_posicao)
        self.sp_app_shuffle.setValue(st.app.shuffle_apos_n_voltas)
        self.app_tecla_do_tab.setText(st.keys.next_target or "TAB")
        self.sp_app_espera_tab.setValue(st.app.espera_depois_do_tab_ms)
        for (tecla, espera), passo in zip(self.app_linhas, st.app.steps):
            tecla.set_key(passo.key)
            espera.setValue(passo.delay_ms)
        self._atualizar_previa_app()

        ataques = list(k.attack_skills) + [""] * 4
        for i, attr in enumerate(("k_atk1", "k_atk2", "k_atk3", "k_atk4")):
            getattr(self, attr).set_key(ataques[i])
        self.k_aoe.set_key(k.aoe_skill)
        self.k_break.set_key(k.break_soul)
        self.k_super.set_key(k.super_skill)
        self.k_heal.set_key(k.heal_skill)
        self.k_revive.set_key(k.revive_skill)
        buffs = list(k.buffs) + [""] * 4
        for i, attr in enumerate(("k_buff1", "k_buff2", "k_buff3", "k_buff4")):
            getattr(self, attr).set_key(buffs[i])
        self.k_hp.set_key(k.hp_potion)
        self.k_bhp.set_key(k.battle_hp_potion)
        self.k_petfood.set_key(k.pet_food)
        self.k_stone.set_key(k.stone_charm)
        self.k_mount.set_key(k.mount)
        self.k_speed.set_key(k.speed_skill)
        self.k_guild.set_key(k.guild_token)
        self.k_pet.set_key(k.pet_summon)
        self.k_sit.set_key(k.sit)
        self.k_self.set_key(k.self_target)
        self.k_follow.set_key(k.follow)
        self.k_next.set_key(k.next_target)
        self.k_inv.set_key(k.inventory)
        self.k_fl.set_key(k.friend_list)
        self.k_hotbar.set_key(k.hotbar_page_1)
        self.k_esconder.set_key(k.hide_players)

        self.in_boss.setText(bc.boss_name)
        self.sp_delay.setValue(segundos_para_ms(bc.attack_delay))
        self.ck_heal2.setChecked(bc.heal_before_second_phase)
        self.bar_aoe_mana.setValue(bc.aoe_until_mana_pct)

        self.ck_speed.setChecked(bc.usar_skill_de_velocidade)
        self._montar_lista_de_reset(bc.reset_nick)

        # --- HH -----------------------------------------------------------
        hh = st.hh
        i = self.cb_hh_modo.findData(hh.modo_do_reset)
        self.cb_hh_modo.setCurrentIndex(i if i >= 0 else 0)
        self._montar_lista_de_reset(hh.reset_nick, self.in_hh_reset)
        self.sp_hh_delay.setValue(int(round(hh.attack_delay * 1000)))
        self.bar_hh_aoe.setValue(hh.aoe_until_mana_pct)
        self.sp_hh_limpar.setValue(hh.limpar_mobs_a_cada)
        self.sp_hh_slot.setValue(hh.vendor.sell_start_slot)
        self.sp_hh_runs.setValue(hh.vendor.runs_before_selling)

        self.sp_runs.setValue(bc.vendor.runs_before_selling)
        self.sp_slot.setValue(bc.vendor.sell_start_slot)
        idx = self.cb_cliques.findData(bc.vendor.sell_clicks)
        if idx < 0:
            self.cb_cliques.addItem(f"{bc.vendor.sell_clicks} cliques",
                                    bc.vendor.sell_clicks)
            idx = self.cb_cliques.count() - 1
        self.cb_cliques.setCurrentIndex(idx)
        self.ck_charm.setChecked(bc.vendor.buy_return_charm)

    def _reseter_seria_desmarcado(self) -> bool:
        """Desmarcar 'aceitar convites' de um reseter quebra outra conta.

        MESMO PROBLEMA DE DELETAR OU DESATIVAR, por uma porta diferente: a
        conta continua no ar, mas deixa de aceitar o convite -- e a conta que
        depende dela passa a não conseguir resetar a cave. O sintoma é o
        mesmo ("o boss parou de nascer") e a causa fica igualmente escondida.

        Por isso o bloqueio é aqui, na hora de salvar, e não numa validação
        depois: neste instante o usuário sabe o que acabou de mexer.
        """
        if self.config is None or self.ck_aceitar.isChecked():
            return False
        if self.st.accept_team_invites is False:
            return False                    # já estava desmarcado: nada mudou
        dependentes = self.config.accounts_reset_by(self.conta)
        if not dependentes:
            return False
        quem = ", ".join(f"'{c.login}'" for c in dependentes)
        QMessageBox.warning(
            self, "Esta conta é o reset da cave",
            f"'{self.conta.login}' é a conta de RESET de {quem}.\n\n"
            "Desmarcando 'aceitar convites de time' ela para de aceitar o "
            "convite, essa(s) conta(s) não resetam a Bewitcher Cave, o boss "
            "não renasce e a run é perdida.\n\n"
            "Troque o reset na edição dessa(s) conta(s) primeiro."
        )
        return True

    def _aplicar(self) -> None:
        st = self.st
        k, pet, pot, bc = st.keys, st.pet, st.potions, st.bc

        # O nick vive na CONTA, não nas configurações do personagem: ele
        # identifica a janela do jogo, e isso não muda de atividade para
        # atividade.
        self.conta.last_char_name = self.in_nick.text().strip()
        self.conta.grupo = self.in_grupo.text().strip()[:LIMITE_DO_NOME_DO_GRUPO]
        if self._reseter_seria_desmarcado():
            return                          # nada é salvo; o diálogo continua aberto
        st.accept_team_invites = self.ck_aceitar.isChecked()
        st.usar_catador = self.ck_catador.isChecked()
        st.mount_speed_pct = self.cb_mount.currentData() or MOUNT_SPEEDS[0]

        pet.summon_on_login = self.ck_pet_login.isChecked()
        pet.feed_on_start = self.ck_pet_start.isChecked()
        pet.feed_every_minutes = self.cb_pet_feed.currentData() or PET_FEED_MINUTES

        pot.hp_pct = self.bar_hp.value()
        pot.battle_hp_pct = self.bar_bhp.value()
        pot.emergency_pct = self.bar_emerg.value()

        st.bags.bolsas = self.cb_bolsas.currentData() or 1

        st.app.apagar_lixo_a_cada = self.sp_app_limpar.value()
        st.app.travar_posicao = self.cb_app_travar.isChecked()
        st.app.shuffle_apos_n_voltas = self.sp_app_shuffle.value()
        st.app.espera_depois_do_tab_ms = self.sp_app_espera_tab.value()
        for passo, (tecla, espera) in zip(st.app.steps, self.app_linhas):
            passo.key = tecla.key()
            passo.delay_ms = espera.value()

        k.attack_skills = [
            c.key() for c in (self.k_atk1, self.k_atk2, self.k_atk3, self.k_atk4)
            if c.key()
        ]
        k.aoe_skill = self.k_aoe.key()
        k.break_soul = self.k_break.key()
        k.super_skill = self.k_super.key()
        k.heal_skill = self.k_heal.key()
        k.revive_skill = self.k_revive.key()
        k.buffs = [
            c.key() for c in (self.k_buff1, self.k_buff2, self.k_buff3, self.k_buff4)
            if c.key()
        ]
        k.hp_potion = self.k_hp.key()
        k.battle_hp_potion = self.k_bhp.key()
        k.pet_food = self.k_petfood.key()
        k.stone_charm = self.k_stone.key()
        k.mount = self.k_mount.key()
        k.speed_skill = self.k_speed.key()
        k.guild_token = self.k_guild.key()
        k.pet_summon = self.k_pet.key()
        k.sit = self.k_sit.key()
        k.self_target = self.k_self.key()
        k.follow = self.k_follow.key()
        k.next_target = self.k_next.key()
        k.inventory = self.k_inv.key()
        k.friend_list = self.k_fl.key()
        k.hotbar_page_1 = self.k_hotbar.key()
        k.hide_players = self.k_esconder.key()

        bc.boss_name = self.in_boss.text().strip()
        bc.attack_delay = ms_para_segundos(self.sp_delay.value())
        bc.heal_before_second_phase = self.ck_heal2.isChecked()
        bc.aoe_until_mana_pct = self.bar_aoe_mana.value()
        bc.usar_skill_de_velocidade = self.ck_speed.isChecked()
        bc.reset_nick = (self.in_reset.currentData() or "").strip()

        # --- HH -----------------------------------------------------------
        hh = st.hh
        hh.modo_do_reset = normalizar_modo_do_reset(self.cb_hh_modo.currentData())
        hh.reset_nick = (self.in_hh_reset.currentData() or "").strip()
        hh.attack_delay = self.sp_hh_delay.value() / 1000.0
        hh.aoe_until_mana_pct = self.bar_hh_aoe.value()
        hh.limpar_mobs_a_cada = self.sp_hh_limpar.value()
        hh.vendor.sell_start_slot = self.sp_hh_slot.value()
        hh.vendor.runs_before_selling = self.sp_hh_runs.value()
        bc.vendor.runs_before_selling = self.sp_runs.value()
        bc.vendor.sell_start_slot = self.sp_slot.value()
        bc.vendor.sell_clicks = self.cb_cliques.currentData() or 24
        bc.vendor.buy_return_charm = self.ck_charm.isChecked()

        self.accept()
