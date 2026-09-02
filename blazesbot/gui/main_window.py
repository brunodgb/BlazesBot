"""
Janela principal do BlazesBot.

A tela principal ficou deliberadamente pequena: **Contas**, **Cliente**,
**Estatísticas de BC** e **Log**. Tudo que é específico de personagem -- classe,
montaria, teclas, poções, rota, venda -- mora no editor da conta, aberto pelo
botão "Editar". Duas razões:

  * Configuração de personagem é POR CONTA. Deixá-la na tela principal dava a
    impressão errada de que valia para todas.
  * Quem só quer auto-login não precisa ver nada de farm. As abas de farm só
    aparecem no editor quando a conta está marcada como BC Farm.

Como antes, tudo é aplicado em TEMPO REAL no mesmo objeto que os supervisores
estão lendo, então vale no próximo ciclo deles.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import date
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# TEMPORÁRIO: botões "Testar a venda" e "Amostrar cliques"
from ..bot.app import afericao
from ..bot.bc import amostragem_de_cliques, teste_venda
from ..bot.supervisor import BotManager
from ..config import ICONE_DO_APP, Account, BotConfig, segundos_para_ms
from ..core import logmodo, quedas, stats_diarias
from ..core.coords import (
    SUPPORTED_RESOLUTIONS,
    VALIDATED_RESOLUTION,
    get_coords,
)
from ..core.secrets import dpapi_available
from .account_dialog import AccountDialog
from .help_tip import HelpTip
from .theme import STYLESHEET
from .widgets import SideNav, StatCard, formata_duracao

POSITIONS = ["Left", "Center", "Right"]
ACCOUNT_ROLE = Qt.ItemDataRole.UserRole + 1
(COL_ATIVA, COL_LOGIN, COL_SENHA, COL_POS, COL_SERVIDOR, COL_FARM, COL_HH,
 COL_APP, COL_EDITAR) = range(9)

# Largura das colunas que só têm uma caixa de marcar. É o tamanho da caixa
# mais uma folga mínima para o cabeçalho -- essas colunas não precisam de mais
# que isso, e o espaço economizado vai para login e senha, que são os campos
# em que se digita.
LARGURA_DA_CAIXA = 46
ALTURA_LINHA = 40           # linhas baixas cortavam os campos ao editar

# Seções da navegação lateral. O ícone vem antes do nome porque a barra é
# estreita: o desenho é reconhecido de relance e o texto confirma.
SECOES: list[tuple[str, str]] = [
    ("🎮", "Contas"),
    ("🖥", "Cliente"),
    ("📊", "Estatísticas de BC"),
    ("💥", "Histórico de Quedas"),
    ("📜", "Log"),
    ("🩺", "Diagnóstico"),
]
NOMES_DAS_SECOES = [nome for _icone, nome in SECOES]

# Cadência com que a interface esvazia a fila de log. 5 vezes por segundo é
# imperceptível para quem lê e reduz o trabalho da thread da interface por um
# fator de ~100 em relação a tratar cada linha na hora que ela nasce.
INTERVALO_DE_DESCARGA_MS = 200

# Máximo de linhas escritas no widget por descarga. Existe porque um pico de
# log (o bot subindo quatro contas ao mesmo tempo, cada uma varrendo janelas)
# gera milhares de linhas em poucos segundos, e escrever tudo de uma vez
# devolveria a travada que este mecanismo existe para eliminar.
MAX_LINHAS_POR_DESCARGA = 400

# Linhas mantidas em memória para permitir refiltrar por conta.
MAX_LINHAS_GUARDADAS = 12000


class QtLogHandler(logging.Handler):
    """Enfileira o log para a interface, marcando de qual conta veio.

    O nome do logger é sempre `blazes.<login>`, então dá para separar as linhas
    por conta e permitir ler o log de uma só -- com várias contas rodando ao
    mesmo tempo, um log único fica impossível de acompanhar.

    =====================================================================
    POR QUE UMA FILA, E NÃO UM SINAL POR LINHA
    =====================================================================

    Esta era a causa da INTERFACE TRAVANDO. A versão anterior emitia um sinal
    Qt por registro de log. Com quatro contas em nível DEBUG e laços de rota
    que releem a posição a cada 0,12 s, isso são centenas de eventos por
    segundo chegando na thread da interface -- e cada um fazia:

        append numa lista  +  varredura do combo de contas  +
        appendPlainText no widget  +  recontagem O(n) das 12 000 linhas

    O resultado era exatamente o sintoma relatado: clicar num botão ou trocar
    de aba não respondia, porque a thread da interface não tinha folga para
    processar o clique. E como o bot lê a caixa "BC farm" da interface, a
    lentidão respingava no farm.

    Agora o handler só faz `append` numa `deque` -- operação atômica, sem Qt e
    sem lock. A interface esvazia a fila num temporizador, em lote. O log
    continua completo (os arquivos são escritos por outro handler, sempre), e a
    interface volta a responder na hora.
    """

    def __init__(self, fila: deque[tuple[str, str]]) -> None:
        super().__init__()
        self.fila = fila
        self.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            partes = record.name.split(".", 1)
            conta = partes[1] if len(partes) > 1 else ""
            self.fila.append((conta, self.format(record)))
        except Exception:
            pass


class MainWindow(QMainWindow):
    log_line = pyqtSignal(str)
    log_entry = pyqtSignal(str, str)      # (conta, linha)
    # TEMPORÁRIO: resultado do teste isolado de venda, vindo da thread dele.
    # Sinal porque tocar em widget fora da thread da interface trava o Qt.
    teste_venda_pronto = pyqtSignal(dict)
    # TEMPORÁRIO: resultado da amostragem de cliques, pelo mesmo motivo.
    amostragem_pronta = pyqtSignal(dict)
    # Resultado da conferência dos modelos de exclusão (thread própria).
    afericao_pronta = pyqtSignal(dict)

    def __init__(self, config_path: Path) -> None:
        super().__init__()
        self.config_path = config_path
        self.config = BotConfig.load(config_path)
        self.manager: BotManager | None = None
        self._loading = True
        # Histórico completo (para refiltrar por conta) e a fila que as threads
        # do bot alimentam. A fila é `deque` com `maxlen`: se a interface ficar
        # atrás, ela descarta as linhas MAIS ANTIGAS da fila em vez de crescer
        # sem limite -- e o arquivo de log continua tendo tudo.
        self._log_entries: deque[tuple[str, str]] = deque(maxlen=MAX_LINHAS_GUARDADAS)
        self._fila_de_log: deque[tuple[str, str]] = deque(maxlen=40000)
        self._contagem_por_conta: dict[str, int] = {}
        self._total_de_linhas = 0
        self._contas_no_filtro: set[str] = set()

        self.setWindowTitle("BlazesBot — Talisman Online — Bewitcher Cave")
        # ÍCONE DA JANELA E DA BARRA DE TAREFAS. Não existia: nem aqui nem no
        # pywebview havia `setWindowIcon`, e o `favicon.ico` que a web
        # referenciava não estava no repositório. Um arquivo só serve às duas
        # telas -- duas cópias divergiriam na primeira troca de arte.
        icone = ICONE_DO_APP
        if icone.exists():
            self.setWindowIcon(QIcon(str(icone)))
        self.resize(1200, 800)
        self.setStyleSheet(STYLESHEET)

        self._build_ui()
        self._load_into_widgets()
        self._wire_live_updates()
        self._loading = False

        # Os dois sinais só existem para quem quer escrever no log DE DENTRO da
        # interface. O log das threads do bot entra pela fila, sem passar por
        # sinal -- ver `QtLogHandler`.
        self.log_line.connect(lambda linha: self._enfileirar("", linha))
        self.log_entry.connect(self._enfileirar)
        self.teste_venda_pronto.connect(self._fim_do_teste_de_venda)  # TEMPORÁRIO
        self.amostragem_pronta.connect(self._fim_da_amostragem)       # TEMPORÁRIO
        self.afericao_pronta.connect(self._fim_da_afericao)
        logger = logging.getLogger("blazes")
        logger.addHandler(QtLogHandler(self._fila_de_log))
        # Nível conforme o ambiente: detalhado (DEBUG) no dev; INFO+ em prod
        # (o usuário não recebe o detalhe de desenvolvimento).
        nivel_gui = logging.DEBUG if logmodo.eh_dev() else logging.INFO
        logger.setLevel(nivel_gui)
        self._enfileirar(
            "", "BlazesBot pronto." +
               (" Log detalhado ligado." if nivel_gui == logging.DEBUG else ""))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(1500)

        # Temporizador só do log, mais rápido que o de estatísticas: as linhas
        # precisam aparecer logo, mas em lote.
        self._timer_log = QTimer(self)
        self._timer_log.timeout.connect(self._descarregar_log)
        self._timer_log.start(INTERVALO_DE_DESCARGA_MS)

    # ==================================================================
    # Estrutura
    # ==================================================================

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        root.addLayout(self._build_header())

        corpo = QHBoxLayout()
        corpo.setSpacing(12)
        self.nav = SideNav()
        for icone, nome in SECOES:
            self.nav.adicionar(nome, icone)
        self.nav.currentRowChanged.connect(
            lambda i: self.paginas.setCurrentIndex(max(0, i))
        )
        # O histórico de quedas carrega ao ABRIR a seção, não no `_refresh_status`:
        # ele lê arquivo e monta imagens, e queda é evento raro -- refazer isso
        # duas vezes por segundo seria trabalho para mostrar a mesma lista.
        self.nav.currentRowChanged.connect(self._ao_trocar_de_secao)
        corpo.addWidget(self.nav)

        self.paginas = QStackedWidget()
        self.paginas.addWidget(self._pg_contas())
        self.paginas.addWidget(self._scroll(self._pg_cliente()))
        self.paginas.addWidget(self._scroll(self._pg_stats()))
        self.paginas.addWidget(self._pg_quedas())
        self.paginas.addWidget(self._pg_log())
        self.paginas.addWidget(self._scroll(self._pg_diagnostico()))
        corpo.addWidget(self.paginas, 1)
        root.addLayout(corpo, 1)

        root.addLayout(self._build_controls())
        self.status_label = QLabel("Parado.")
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

        self.setCentralWidget(central)
        self.nav.setCurrentRow(0)

    @staticmethod
    def _scroll(inner: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(inner)
        return area

    @staticmethod
    def _hint(texto: str) -> QLabel:
        label = QLabel(texto)
        label.setObjectName("hint")
        label.setWordWrap(True)
        return label

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(1)
        t = QLabel("BlazesBot")
        t.setObjectName("title")
        s = QLabel("Bewitcher Cave · boss-rush · auto-login")
        s.setObjectName("subtitle")
        col.addWidget(t)
        col.addWidget(s)
        row.addLayout(col)
        row.addStretch()
        selo = QLabel("edição ao vivo")
        selo.setObjectName("badge")
        selo.setToolTip("Qualquer alteração vale na hora, mesmo com o bot rodando.")
        row.addWidget(selo)
        return row

    def _build_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.btn_start = QPushButton("Iniciar")
        self.btn_start.setObjectName("primary")
        self.btn_start.clicked.connect(self._start)
        self.btn_pause = QPushButton("Pausar")
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_pause.setEnabled(False)
        self.btn_stop = QPushButton("Parar")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)
        self.ck_debug = QCheckBox("log detalhado")
        self.ck_debug.setChecked(True)
        self.ck_debug.setToolTip(
            "Registra cada passo do bot, incluindo as decisões internas.\n"
            "Deixe ligado enquanto estamos ajustando: é o que permite\n"
            "entender onde algo deu errado."
        )
        self.ck_debug.stateChanged.connect(self._aplicar_nivel_log)
        if not logmodo.eh_dev():
            # Em prod o detalhe de desenvolvimento não fica exposto a usuários.
            self.ck_debug.setChecked(False)
            self.ck_debug.setEnabled(False)

        dica = QLabel("Parar não fecha o jogo.")
        dica.setObjectName("hint")
        for w in (self.btn_start, self.btn_pause, self.btn_stop):
            row.addWidget(w)
        row.addSpacing(12)
        row.addWidget(self.ck_debug)
        row.addSpacing(12)
        row.addWidget(dica)
        row.addStretch()
        return row

    def _aplicar_nivel_log(self) -> None:
        dev = logmodo.eh_dev()
        self.ck_debug.setEnabled(dev)
        nivel = logging.DEBUG if (dev and self.ck_debug.isChecked()) else logging.INFO
        logging.getLogger("blazes").setLevel(nivel)
        self._enfileirar(
            "", f"nível de log: {'DETALHADO' if nivel == logging.DEBUG else 'normal'}"
        )

    # ==================================================================
    # Contas
    # ==================================================================

    def _pg_contas(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(self._hint(
            "Senhas cifradas com DPAPI do Windows."
            if dpapi_available()
            else "AVISO: pywin32 ausente — senhas ficariam em texto puro."
        ))

        self.tbl = QTableWidget(0, 9)
        self.tbl.setHorizontalHeaderLabels(
            ["Ativa", "Login", "Senha", "Posição", "Servidor", "BC", "HH", "APP", ""]
        )
        h = self.tbl.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(COL_LOGIN, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(COL_SENHA, QHeaderView.ResizeMode.Stretch)
        for coluna, largura in ((COL_ATIVA, LARGURA_DA_CAIXA),
                                (COL_POS, 110), (COL_SERVIDOR, 185),
                                (COL_FARM, LARGURA_DA_CAIXA),
                                (COL_HH, LARGURA_DA_CAIXA),
                                (COL_APP, LARGURA_DA_CAIXA),
                                (COL_EDITAR, 92)):
            self.tbl.setColumnWidth(coluna, largura)
        # As colunas de caixa ficam FIXAS. Interativas, elas voltavam a esticar
        # quando a janela era redimensionada, e o espaço ia para onde não faz
        # falta.
        for coluna in (COL_ATIVA, COL_FARM, COL_HH, COL_APP):
            h.setSectionResizeMode(coluna, QHeaderView.ResizeMode.Fixed)
        # Linhas altas o bastante para o campo de senha e os seletores caberem
        # inteiros. Com a altura padrão, clicar num campo o cortava pela metade.
        self.tbl.verticalHeader().setDefaultSectionSize(ALTURA_LINHA)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setMinimumHeight(240)
        layout.addWidget(self.tbl, 1)

        botoes = QHBoxLayout()
        add = QPushButton("Adicionar conta")
        add.clicked.connect(self._nova_conta)
        rem = QPushButton("Remover selecionada")
        rem.setObjectName("danger")
        rem.clicked.connect(self._remove_row)

        # ORDEM DAS CONTAS: botões, e NÃO arraste de linha.
        #
        # A web reordena arrastando; aqui não pode. Esta tabela tem SEIS
        # `setCellWidget` (senha, posição, servidor, BC, APP, editar), e o
        # arraste interno do Qt move os `QTableWidgetItem` mas NÃO move os
        # widgets de célula: a senha de uma conta ficaria na linha de outra.
        # Botão mexe no MODELO e repopula, então widget e dado nunca se
        # separam. A funcionalidade é a mesma nas duas telas -- reordenar e
        # gravar --, só o gesto difere, e o motivo está medido aqui.
        self.bt_subir = QPushButton("▲")
        self.bt_subir.setToolTip("Mover a conta selecionada para cima")
        self.bt_subir.setFixedWidth(34)
        self.bt_subir.clicked.connect(lambda: self._mover_conta(-1))
        self.bt_descer = QPushButton("▼")
        self.bt_descer.setToolTip("Mover a conta selecionada para baixo")
        self.bt_descer.setFixedWidth(34)
        self.bt_descer.clicked.connect(lambda: self._mover_conta(1))

        botoes.addWidget(add)
        botoes.addWidget(rem)
        botoes.addSpacing(12)
        botoes.addWidget(self.bt_subir)
        botoes.addWidget(self.bt_descer)
        botoes.addStretch()
        layout.addLayout(botoes)

        layout.addWidget(self._hint(
            "<b>Login e relogin automático valem para toda conta ativa</b> — é a "
            "função básica e não se desliga.<br><br>"
            "<b>BC Farm</b> decide se a conta também roda o boss-rush. Pode "
            "marcar e desmarcar <b>com o bot rodando</b>.<br><br>"
            "O <b>nick do personagem</b> fica em <b>Editar</b>: é ele que faz o "
            "bot reconhecer a janela do jogo que já está logada nesta conta, em "
            "vez de abrir outro cliente e voltar para a fila.<br><br>"
            "<b>Editar</b> abre a configuração daquele personagem: classe, "
            "montaria, teclas, poções, rota e venda. Cada conta tem a sua — "
            "montaria, pet e necessidade de poção mudam de personagem para "
            "personagem."
        ))
        return page

    def _nova_conta(self) -> None:
        """Adiciona uma conta em branco.

        Com o bot em execução, a conta nasce INATIVA de propósito: você preenche
        usuário e senha com calma e, ao marcar "Ativa", ela entra no ar e faz o
        login sozinha -- sem parar as outras contas nem reiniciar o bot.
        """
        rodando = bool(self.manager and self.manager.running())
        conta = Account(enabled=not rodando)
        self._add_row(conta, novo=True)
        self.tbl.setCurrentCell(self.tbl.rowCount() - 1, COL_LOGIN)
        if rodando:
            self.log_line.emit(
                "Conta adicionada como INATIVA. Preencha usuário e senha e "
                "marque 'Ativa' para ela entrar no ar."
            )

    def _mover_conta(self, passo: int) -> None:
        """Move a conta selecionada uma posição, e GRAVA.

        Reordena `config.accounts` -- a ordem das contas É a ordem do array,
        não existe campo de ordem (ver `BotConfig.reordenar_contas`). Depois
        repopula a tabela inteira: é o que mantém cada widget de célula com o
        dado da conta certa.

        A seleção ACOMPANHA a conta, não a posição. Sem isso, clicar ▲ duas
        vezes moveria duas contas diferentes.
        """
        linha = self.tbl.currentRow()
        conta = self._account_of_row(linha)
        if conta is None:
            return
        contas = self.config.accounts
        try:
            de = contas.index(conta)
        except ValueError:
            return
        para = de + passo
        if not (0 <= para < len(contas)):
            return
        contas.insert(para, contas.pop(de))

        self._loading = True
        try:
            self.tbl.setRowCount(0)
            for c in contas:
                self._add_row(c)
        finally:
            self._loading = False
        self.tbl.setCurrentCell(para, COL_LOGIN)
        self._apply_live()

    def _add_row(self, conta: Account, novo: bool = False) -> None:
        antes = self._loading
        self._loading = True
        tbl = self.tbl
        linha = tbl.rowCount()
        tbl.insertRow(linha)
        tbl.setRowHeight(linha, ALTURA_LINHA)

        ativa = QTableWidgetItem()
        ativa.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        ativa.setCheckState(
            Qt.CheckState.Checked if conta.enabled else Qt.CheckState.Unchecked
        )
        # A referência ao objeto vive aqui: é o que mantém a ligação com o
        # supervisor que já está rodando aquela conta.
        ativa.setData(ACCOUNT_ROLE, conta)
        tbl.setItem(linha, COL_ATIVA, ativa)
        tbl.setItem(linha, COL_LOGIN, QTableWidgetItem(conta.login))

        senha = QLineEdit()
        senha.setEchoMode(QLineEdit.EchoMode.Password)
        senha.setPlaceholderText("senha")
        if conta.password_enc:
            try:
                senha.setText(conta.get_password())
            except Exception:
                senha.setPlaceholderText("(não foi possível decifrar)")
        senha.textChanged.connect(
            lambda t, c=conta: (c.set_password(t), self._apply_live())
        )
        tbl.setCellWidget(linha, COL_SENHA, senha)

        pos = QComboBox()
        pos.addItems(POSITIONS)
        pos.setCurrentText(conta.position or "Center")
        pos.currentTextChanged.connect(
            lambda t, c=conta: (setattr(c, "position", t), self._apply_live())
        )
        tbl.setCellWidget(linha, COL_POS, pos)

        coords = get_coords("1024x768")
        servidores = list(coords.server_rows)
        srv = QComboBox()
        srv.addItems(servidores)
        atual = coords.normalize_server(conta.server)
        if atual in servidores:
            srv.setCurrentText(atual)
        srv.currentTextChanged.connect(
            lambda t, c=conta: (setattr(c, "server", t), self._apply_live())
        )
        tbl.setCellWidget(linha, COL_SERVIDOR, srv)

        farm = QCheckBox()
        farm.setChecked(conta.bc_farm)
        farm.setToolTip("Pode marcar e desmarcar com o bot rodando.")
        farm.stateChanged.connect(lambda _v, c=conta: self._toggle_farm(c, farm))
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(farm, 0, Qt.AlignmentFlag.AlignCenter)
        tbl.setCellWidget(linha, COL_FARM, wrap)

        # HH na lista, ao lado do BC: são duas caves, e a troca entre elas é o
        # que se faz o tempo todo. Marcar as DUAS roda a HH -- o supervisor tem
        # ordem fixa de propósito, para a escolha ser previsível.
        hh = QCheckBox()
        hh.setChecked(conta.hh_farm)
        hh.setToolTip(
            "HH (Black Wind Camp Dungeon): quatro bosses em sequência.\n"
            "Pode marcar e desmarcar com o bot rodando.\n"
            "Marcada junto com BC, roda a HH.\n"
            "A conta de reset fica em Editar conta > HH -- sem ela os bosses\n"
            "não renascem e a cave vem vazia da segunda run em diante."
        )
        hh.stateChanged.connect(lambda _v, c=conta: self._toggle_hh(c, hh))
        wrap_hh = QWidget()
        lay_hh = QHBoxLayout(wrap_hh)
        lay_hh.setContentsMargins(0, 0, 0, 0)
        lay_hh.addWidget(hh, 0, Qt.AlignmentFlag.AlignCenter)
        tbl.setCellWidget(linha, COL_HH, wrap_hh)

        # MODO APP na lista, e não só dentro do editor: ligar e desligar é o que
        # se faz o tempo todo, e abrir uma janela para isso era um passo a mais em
        # cada troca. A CONFIGURAÇÃO da sequência continua em Editar conta > APP.
        app = QCheckBox()
        app.setChecked(conta.settings.app.enabled)
        app.setToolTip(
            "Modo APP: macro de teclado em laço.\n"
            "Pode marcar e desmarcar com o bot rodando.\n"
            "As linhas ficam em Editar conta > APP."
        )
        app.stateChanged.connect(lambda _v, c=conta: self._toggle_app(c, app))
        wrap_app = QWidget()
        lay_app = QHBoxLayout(wrap_app)
        lay_app.setContentsMargins(0, 0, 0, 0)
        lay_app.addWidget(app, 0, Qt.AlignmentFlag.AlignCenter)
        tbl.setCellWidget(linha, COL_APP, wrap_app)

        editar = QPushButton("Editar")
        editar.clicked.connect(lambda _c=False, c=conta: self._editar_conta(c))
        tbl.setCellWidget(linha, COL_EDITAR, editar)

        self._loading = antes
        if novo:
            self._apply_live()

    def _toggle_farm(self, conta: Account, caixa: QCheckBox) -> None:
        conta.bc_farm = caixa.isChecked()
        if self.manager and self.manager.running():
            estado = "LIGADO" if conta.bc_farm else "desligado"
            self.log_line.emit(f"[{conta.login}] BC farm {estado} em tempo real")
        self._apply_live()

    def _toggle_hh(self, conta: Account, caixa: QCheckBox) -> None:
        """Liga/desliga a HH direto da lista, valendo em tempo real.

        Espelha `_toggle_farm`. A rotina consulta `hh_farm` a cada volta e entre
        estados, então desmarcar aqui devolve o controle no próximo ponto seguro
        -- sem interromper uma ação pela metade.
        """
        conta.hh_farm = caixa.isChecked()
        if self.manager and self.manager.running():
            estado = "LIGADA" if conta.hh_farm else "desligada"
            self.log_line.emit(f"[{conta.login}] HH {estado} em tempo real")
        self._apply_live()

    def _toggle_app(self, conta: Account, caixa: QCheckBox) -> None:
        """Liga/desliga o modo APP direto da lista, valendo em tempo real.

        Espelha `_toggle_farm`. O executor consulta `app.enabled` a cada volta e
        entre teclas, então desmarcar aqui encerra a macro sem reiniciar nada --
        e marcar volta a rodar na volta seguinte do laço de vida.
        """
        conta.settings.app.enabled = caixa.isChecked()
        if self.manager and self.manager.running():
            estado = "LIGADO" if conta.settings.app.enabled else "desligado"
            self.log_line.emit(f"[{conta.login}] modo APP {estado} em tempo real")
        self._apply_live()

    def _editar_conta(self, conta: Account) -> None:
        item = self.tbl.item(self.tbl.currentRow(), COL_LOGIN)
        if item is not None and not conta.login:
            conta.login = item.text().strip()
        dialogo = AccountDialog(conta, self, config=self.config)
        if dialogo.exec():
            self._apply_live()
            self.log_line.emit(
                f"[{conta.login}] configuração atualizada "
                f"(personagem '{conta.last_char_name or 'não informado'}', "
                f"montaria {conta.settings.mount_speed_pct}%, "
                f"venda a cada {conta.settings.bc.vendor.runs_before_selling} "
                f"runs do slot {conta.settings.bc.vendor.sell_start_slot})"
            )

    def _account_of_row(self, linha: int) -> Account | None:
        item = self.tbl.item(linha, COL_ATIVA)
        if item is None:
            return None
        conta = item.data(ACCOUNT_ROLE)
        return conta if isinstance(conta, Account) else None

    def _collect_accounts(self) -> list[Account]:
        contas: list[Account] = []
        for linha in range(self.tbl.rowCount()):
            conta = self._account_of_row(linha)
            if conta is None:
                continue
            item = self.tbl.item(linha, COL_LOGIN)
            if item is not None:
                conta.login = item.text().strip()
            item = self.tbl.item(linha, COL_ATIVA)
            if item is not None:
                conta.enabled = item.checkState() == Qt.CheckState.Checked
            # O NICK não é lido daqui de propósito. Quem manda nele é o bot, que
            # grava o nome lido da memória a cada login; ler a célula neste ponto
            # (chamado a cada salvamento) reverteria o nick recém-descoberto pelo
            # texto ainda antigo da tela. A edição manual entra por
            # `_on_table_item`, que só dispara quando VOCÊ digita.
            if conta.login:
                contas.append(conta)
        return contas

    def _bloqueado_por_ser_reseter(self, conta: Account, acao: str) -> bool:
        """Impede tirar do ar uma conta que outra usa como reset da cave.

        POR QUE IMPEDIR, E NÃO SÓ AVISAR. Sem o reseter, a conta que depende
        dele não consegue resetar a cave -- e sem reset o boss não renasce e a
        run é perdida. O sintoma disso ("o boss parou de nascer") aparece horas
        depois e não aponta para cá em nada.

        E POR QUE AQUI, E NÃO NA VALIDAÇÃO. Neste instante o usuário está com a
        tela na mão e o contexto na cabeça: desfazer é um clique, e trocar o
        reset da outra conta primeiro é o caminho natural. Descoberto três horas
        depois, no meio de uma run, o mesmo problema custa reabrir tudo e
        reconstruir o raciocínio.

        Só contas ATIVAS contam como dependentes -- ver
        `BotConfig.accounts_reset_by`.
        """
        dependentes = self.config.accounts_reset_by(conta)
        if not dependentes:
            return False
        quem = ", ".join(f"'{c.login}'" for c in dependentes)
        QMessageBox.warning(
            self, "Esta conta é o reset da cave",
            f"Não dá para {acao} '{conta.login}': ela é a conta de RESET de "
            f"{quem}.\n\n"
            "Sem ela essa(s) conta(s) não conseguem resetar a Bewitcher "
            "Cave, o boss não renasce e a run é perdida.\n\n"
            "Troque o reset na edição dessa(s) conta(s) primeiro; depois volte "
            "aqui."
        )
        return True

    def _remove_row(self) -> None:
        linha = self.tbl.currentRow()
        if linha < 0:
            return
        conta = self._account_of_row(linha)
        if conta is not None and self._bloqueado_por_ser_reseter(conta, "remover"):
            return
        self.tbl.removeRow(linha)
        self._apply_live()
        if conta is not None:
            # Remove os contadores órfãos desta conta. Sem esta limpeza, o
            # dicionário `_contagem_por_conta` acumula entradas para sempre
            # — vazamento lento, mas real em execuções de dias.
            login = conta.login
            if login:
                self._contagem_por_conta.pop(login, None)
                self._contas_no_filtro.discard(login)
            self._sincronizar_contas()

    # ==================================================================
    # Cliente (global)
    # ==================================================================

    def _pg_cliente(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._hint(
            "Estas configurações são <b>da máquina</b> e valem para todas as "
            "contas. O que é do personagem fica em <b>Editar</b>, na lista de "
            "contas."
        ))

        box = QGroupBox("Cliente do jogo")
        form = QFormLayout(box)
        linha = QHBoxLayout()
        self.in_client_bat = QLineEdit()
        btn = QPushButton("Procurar…")
        btn.clicked.connect(self._browse_client)
        linha.addWidget(self.in_client_bat)
        linha.addWidget(btn)
        wrap = QWidget()
        wrap.setLayout(linha)
        form.addRow("Caminho do Client.bat:", wrap)

        self.cb_resolution = QComboBox()
        self.cb_resolution.addItem("detectar automaticamente", "auto")
        for res in SUPPORTED_RESOLUTIONS:
            rotulo = (f"{res}   (validada)" if res == VALIDATED_RESOLUTION
                      else res)
            self.cb_resolution.addItem(rotulo, res)
        form.addRow("Resolução do jogo:", self.cb_resolution)
        self.lbl_res = QLabel()
        self.lbl_res.setObjectName("hint")
        self.lbl_res.setWordWrap(True)
        form.addRow("", self.lbl_res)

        # EM MILISSEGUNDOS, como todo campo de tempo das duas interfaces. O
        # `launch_delay` segue `float` de segundos no `config.json` (ver
        # `config.segundos_para_ms`) -- só o rótulo mudou de unidade.
        self.cb_launch_delay = QComboBox()
        for seg in (4, 6, 8, 10, 12, 15, 20, 30):
            self.cb_launch_delay.addItem(f"{seg * 1000} ms", float(seg))
        form.addRow("Espera após abrir o cliente:", self.cb_launch_delay)

        self.ck_minimize = QCheckBox("Minimizar clientes após o login")
        form.addRow(self.ck_minimize)

        self.ck_reuse = QCheckBox("Aproveitar cliente já aberto na tela de login")
        linha_reuse = QHBoxLayout()
        linha_reuse.setContentsMargins(0, 0, 0, 0)
        linha_reuse.addWidget(self.ck_reuse, 1)
        linha_reuse.addWidget(HelpTip(
            "O bot SEMPRE reconhece uma janela como sendo desta conta quando\n"
            "consegue identificá-la — pelo nome do personagem lido da memória\n"
            "ou pelo título da janela. Isso não se desliga e poupa a fila.\n"
            "\n"
            "Esta opção é outra coisa: pegar um cliente QUALQUER que esteja\n"
            "parado na tela de login e usá-lo para esta conta.\n"
            "\n"
            "Vem desligada porque, com várias contas subindo juntas, uma podia\n"
            "adotar o cliente que a outra acabou de abrir — e o resultado era o\n"
            "bot não abrir a janela que devia, ou abrir várias.\n"
            "\n"
            "Ligue se você deixa clientes abertos na tela de login de propósito\n"
            "para o bot usar."
        ))
        wrap_reuse = QWidget()
        wrap_reuse.setLayout(linha_reuse)
        form.addRow(wrap_reuse)
        outer.addWidget(box)

        auto = QGroupBox("Calibração")
        af = QFormLayout(auto)
        af.addRow(self._hint(
            "Não há nada para calibrar à mão. O bot <b>mede a área de cliente "
            "da janela</b> e localiza as janelas do jogo por imagem, "
            "calculando as posições a partir delas. Isso vale para a grade de "
            "venda, para os campos de login e para os botões — em qualquer "
            "resolução."
        ))
        outer.addWidget(auto)

        con = QGroupBox("Queda de conexão")
        cf = QFormLayout(con)
        cf.addRow(self._hint(
            "O bot só religa por sinal inequívoco: o processo do cliente morreu, "
            "a janela desapareceu, ou o aviso <b>“Connection interrupted”</b> "
            "está na tela.<br><br>"
            "<b>Não existe detecção por inatividade.</b> Personagem parado "
            "vendendo itens não é motivo para religar."
        ))
        outer.addWidget(con)
        outer.addStretch()
        return page

    # ==================================================================
    # Estatísticas e log
    # ==================================================================

    def _pg_stats(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)

        # Filtro por personagem: lista os NICKS das contas que tenham pelo
        # menos uma run registrada hoje (ou na sessão). A conta em si (login)
        # não aparece -- só o nick, para filtrar "de quem quero ver".
        topo = QHBoxLayout()
        topo.addWidget(QLabel("Personagem:"))
        self.cb_stats_conta = QComboBox()
        self.cb_stats_conta.setMinimumWidth(220)
        # guarda o login como itemData; o texto exibido é o nick
        self.cb_stats_conta.currentIndexChanged.connect(self._preencher_stats_conta)
        topo.addWidget(self.cb_stats_conta, 1)
        self.lbl_stats_sem_conta = QLabel("Nenhuma personagem com runs registradas.")
        self.lbl_stats_sem_conta.setObjectName("hint")
        topo.addWidget(self.lbl_stats_sem_conta)
        topo.addStretch()
        outer.addLayout(topo)

        self.cards: dict[str, StatCard] = {}
        grid = QGridLayout()
        grid.setSpacing(9)
        definicoes = [
            ("run_agora", "⏱ Tempo da run atual"),
            ("boss_agora", "⏱ Tempo até o boss (atual)"),
            ("runs_hoje", "Runs hoje"), ("success_hoje", "Sucesso hoje"),
            ("fail_hoje", "Falhas hoje"), ("taxa_hoje", "Taxa de sucesso"),
            ("media_hoje", "T. médio hoje"),
            ("boss_ult", "T. até boss (últ.)"), ("total_ult", "T. total (últ.)"),
            ("total_hoje", "T. total das runs hoje"),
            ("sessao_runs", "Runs na sessão"),
            ("sessao_ok", "Sessão (ok/falhas)"),
        ]
        for i, (chave, rotulo) in enumerate(definicoes):
            card = StatCard(rotulo, "—")
            self.cards[chave] = card
            grid.addWidget(card, i // 4, i % 4)
        outer.addLayout(grid)

        # Dias anteriores: hoje é o número principal (cards de cima), então
        # esta tabela guarda ontem e os dias que vieram antes, para comparar o
        # progresso do dia atual com os anteriores. Dados persistidos entre
        # sessões em data/stats_diarias.json.
        self.lbl_historico_titulo = QLabel("Dias anteriores")
        self.lbl_historico_titulo.setObjectName("hint")
        outer.addWidget(self.lbl_historico_titulo)
        self.tbl_historico = QTableWidget(0, 6)
        self.tbl_historico.setHorizontalHeaderLabels(
            ["Dia", "Runs", "Sucesso", "Falhas", "T. até boss", "Tempo médio"])
        # Estica as colunas para ocupar a caixa inteira de ponta a ponta, em
        # vez de cada uma se apertar no tamanho do conteúdo.
        self.tbl_historico.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tbl_historico.horizontalHeader().setStretchLastSection(True)
        self.tbl_historico.verticalHeader().setVisible(False)
        self.tbl_historico.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_historico.setMaximumHeight(200)
        outer.addWidget(self.tbl_historico)
        outer.addWidget(self._hint(
            "<b>Hoje</b> vem do histórico persistido (sobrevive ao fechar o "
            "bot). <b>Sessão</b> é só esta execução. <b>T. até boss (últ.)</b> "
            "é o trajeto até a frente do boss (combate fora) da última run; "
            "<b>T. total (últ.)</b> é essa run inteira."
        ))
        outer.addStretch()
        return page

    def _pg_log(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        topo = QHBoxLayout()
        topo.addWidget(QLabel("Conta:"))
        self.cb_log_conta = QComboBox()
        self.cb_log_conta.addItem("todas as contas", "")
        self.cb_log_conta.setMinimumWidth(210)
        self.cb_log_conta.currentIndexChanged.connect(self._redesenhar_log)
        topo.addWidget(self.cb_log_conta)
        self.lbl_log_contagem = QLabel()
        self.lbl_log_contagem.setObjectName("hint")
        topo.addWidget(self.lbl_log_contagem)
        topo.addStretch()
        layout.addLayout(topo)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setObjectName("log")
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(8000)
        layout.addWidget(self.txt_log)

        rodape = QHBoxLayout()
        btn = QPushButton("Limpar log")
        btn.clicked.connect(self._limpar_log)
        rodape.addWidget(btn)
        abrir = QPushButton("Abrir pasta de logs")
        abrir.clicked.connect(self._abrir_logs)
        rodape.addWidget(abrir)
        rodape.addWidget(HelpTip(
            "O log também é gravado em arquivo, sempre:\n"
            "\n"
            "  logs\\sessao-atual.log   — só desta execução\n"
            "  logs\\blazesbot.log      — histórico acumulado\n"
            "\n"
            "Se a interface travar ou fechar, o arquivo continua lá. É o\n"
            "arquivo que você me manda quando algo der errado."
        ))
        rodape.addStretch()
        layout.addLayout(rodape)
        return page

    # ==================================================================
    # Diagnóstico
    # ==================================================================

    def _pg_diagnostico(self) -> QWidget:
        """Onde olhar quando algo dá errado.

        Existe porque houve um caso em que o bot não fez nada e não gerou log, e
        sem registro o diagnóstico virou adivinhação. Os arquivos abaixo são
        escritos SEMPRE, e cada um tem um assunto só -- pequenos o bastante para
        serem lidos inteiros.
        """
        page = QWidget()
        outer = QVBoxLayout(page)

        # TEMPORÁRIO --------------------------------------------------------
        box = QGroupBox("🧪  Teste isolado da venda")
        f = QVBoxLayout(box)
        f.addWidget(self._hint(
            "Roda <b>só a venda</b>: vai até o vendedor pelo painel de arredores "
            "e vende a partir do slot configurado. Não volta para a cidade, não "
            "recompra nada, não entra na cave — ao terminar, para.<br><br>"
            "<b>Antes de clicar:</b> o bot precisa estar <b>parado</b>, a conta "
            "selecionada na aba <b>Contas</b>, e o personagem já <b>em Stone "
            "City</b> com o jogo aberto.<br><br>"
            "Enquanto a venda roda, este mesmo botão vira o <b>cancelar</b>."
        ))
        linha = QHBoxLayout()
        self.btn_teste_venda = QPushButton("🛒  Testar a venda (conta selecionada)")
        self.btn_teste_venda.clicked.connect(self._testar_venda)
        linha.addWidget(self.btn_teste_venda)
        linha.addStretch()
        f.addLayout(linha)
        outer.addWidget(box)

        box = QGroupBox("🎯  Amostragem de coordenadas de clique direito")
        f = QVBoxLayout(box)
        f.addWidget(self._hint(
            "Mede <b>qual coordenada abre o diálogo</b>. Varre um grid em volta "
            "do alvo que o bot usa hoje, cronometra cada clique direito e "
            "ranqueia por <b>taxa de abertura</b> e <b>latência</b>. O "
            "resultado vai para o log e para <code>logs/amostragem/</code>."
            "<br><br>"
            "<b>Antes de clicar:</b> bot <b>parado</b>, conta selecionada na "
            "aba <b>Contas</b>, e o personagem parado num dos pontos de clique "
            "direito — <b>vendedor</b> ou <b>Transport Fay</b> (Stone City), "
            "<b>entrada da cave</b> (Ghost Din Woods) ou <b>saída da cave</b> "
            "(dentro do covil). A ferramenta reconhece o ponto sozinha pela "
            "posição.<br><br>"
            "O <b>Altar Stone fica de fora</b>: é o único cercado de mobs, e "
            "clique que erra faz o personagem andar.<br><br>"
            "Enquanto roda, este mesmo botão vira o <b>cancelar</b>."
        ))
        linha = QHBoxLayout()
        self.btn_amostragem = QPushButton(
            "🎯  Amostrar cliques neste ponto (conta selecionada)")
        self.btn_amostragem.clicked.connect(self._amostrar_cliques)
        linha.addWidget(self.btn_amostragem)
        linha.addStretch()
        f.addLayout(linha)
        outer.addWidget(box)
        # -------------------------------------------------------- TEMPORÁRIO

        box = QGroupBox("🗑  Conferir os modelos de exclusão (não apaga nada)")
        f = QVBoxLayout(box)
        f.addWidget(self._hint(
            "Fotografa a sua bolsa e <b>desenha</b> o que a limpeza automática "
            "do modo APP apagaria — com um retângulo em cada item reconhecido "
            "e o nome do modelo. <b>Não clica em item nenhum e não apaga.</b>"
            "<br><br>"
            "Os modelos vieram de outro bot, de uma versão anterior do cliente, "
            "e <b>nunca foram medidos contra o seu jogo</b>. Deletar não tem "
            "desfazer — confira a imagem antes de ligar a limpeza na aba APP."
            "<br><br>"
            "<b>Antes de clicar:</b> bot <b>parado</b>, conta selecionada na "
            "aba <b>Contas</b>, personagem no jogo e a tecla de "
            "<b>Inventário</b> configurada."
        ))
        linha = QHBoxLayout()
        self.btn_conferir_exclusao = QPushButton(
            "🗑  Conferir modelos de exclusão (conta selecionada)")
        self.btn_conferir_exclusao.clicked.connect(self._conferir_exclusao)
        linha.addWidget(self.btn_conferir_exclusao)
        linha.addStretch()
        f.addLayout(linha)
        outer.addWidget(box)

        box = QGroupBox("🩺  Arquivos que o bot escreve sempre")
        f = QVBoxLayout(box)
        f.addWidget(self._hint(
            "<b>logs\\localizacao.log</b> — toda mudança e toda FALHA de leitura "
            "do nome do lugar, com a posição do personagem e o valor de cada elo "
            "da cadeia de ponteiros.<br>"
            "É o arquivo do problema do ponteiro de localização: quando ele "
            "quebrar, aqui vai estar o instante exato e <b>onde na cave</b> o "
            "personagem estava.<br><br>"
            "<b>logs\\eventos.log</b> — o que não deveria ter acontecido: morte, "
            "travamento na rota, rollback, retomada de rota, ação sem efeito "
            "(poção que não curou, pet que não apareceu), divergência entre a "
            "memória e a coordenada, time que não formou.<br><br>"
            "<b>logs\\sessao-atual.log</b> — tudo, desta execução.<br>"
            "<b>logs\\blazesbot.log</b> — tudo, acumulado."
        ))
        linha = QHBoxLayout()
        btn = QPushButton("📂  Abrir a pasta de logs")
        btn.clicked.connect(self._abrir_logs)
        linha.addWidget(btn)
        linha.addStretch()
        f.addLayout(linha)
        outer.addWidget(box)

        box = QGroupBox("🔎  O problema do ponteiro de localização")
        f = QVBoxLayout(box)
        f.addWidget(self._hint(
            "O nome do lugar já parou de ser lido duas vezes, e voltou só depois "
            "de fechar e reabrir o jogo — o que custa horas de fila e é "
            "inaceitável.<br><br>"
            "<b>O bot não depende mais dessa leitura.</b> Ele decide onde está por "
            "duas fontes independentes: o nome na memória (quando lê) e a "
            "COORDENADA, comparada com todos os waypoints medidos da cave. A "
            "coordenada nunca falhou em nenhum log — então, com o ponteiro "
            "quebrado, o bot continua sabendo em qual área da cave está e segue "
            "farmando.<br><br>"
            "<b>Para descobrir a causa</b>, rode <b>8-VIGIAR-LOCALIZACAO.bat</b> "
            "em paralelo com o bot e deixe aberto. Ele não mexe no jogo: só lê o "
            "ponteiro a cada segundo e grava. Na próxima vez que quebrar, o "
            "arquivo terá a posição e o elo exato que falhou."
        ))
        outer.addWidget(box)

        box = QGroupBox("⚔️  O alvo morreu, ou só saiu do quadro?")
        f = QVBoxLayout(box)
        f.addWidget(self._hint(
            "Hoje o bot decide que o alvo morreu quando o <b>HP do alvo</b> chega a "
            "zero. Há indício de que isso pode falhar: foi visto no covil um quadro "
            "de alvo exibindo <b>Gun Witch</b> enquanto a tela escrevia "
            "<i>“Invalid target.”</i> a cada tecla de ataque e <i>“Leave Battle”</i> "
            "em verde. Ou seja, o mob já não era alvo válido e o quadro continuava "
            "lá.<br><br>"
            "Se o quadro ficar <b>parado</b> depois da morte, o bot bate em nada até "
            "o tempo limite: 25 s por guarda, e no boss os minutos inteiros.<br><br>"
            "<b>Para saber qual é o caso</b>, rode <b>9-VIGIAR-COMBATE.bat</b> em "
            "paralelo e passe pelos 4 guardas. Ele grava, no mesmo instante, a flag "
            "de combate e o quadro do alvo em <b>logs\\combate.log</b>. Procure a "
            "palavra <b>SUSPEITA</b>: ela marca combate encerrado com o alvo ainda "
            "de vida cheia.<br><br>"
            "A flag de combate <b>não decide nada</b> no bot — ela já foi vista "
            "presa em ligado. Ela está sendo medida antes de voltar a mandar em "
            "alguma coisa."
        ))
        outer.addWidget(box)

        box = QGroupBox("🧪  Ferramentas de linha de comando")
        f = QVBoxLayout(box)
        f.addWidget(self._hint(
            "<b>2-DIAGNOSTICO.bat</b> — confere a memória de todos os clientes. "
            "Agora ele também detalha a localização: mostra o que cada leitura "
            "devolveu e onde a cadeia parou.<br>"
            "<b>5-DETECTAR-TELA.bat</b> — mostra ao vivo qual tela o bot "
            "reconhece.<br>"
            "<b>6-TESTE-CAPTURA.bat</b> — salva em PNG o que o bot enxerga.<br>"
            "<b>7-DESCOBRIR-MEMORIA.bat</b> — acha o ponteiro base quando o jogo "
            "atualizar.<br>"
            "<b>8-VIGIAR-LOCALIZACAO.bat</b> — vigia o ponteiro do nome do lugar."
        ))
        outer.addWidget(box)

        outer.addStretch()
        return page

    def _conferir_exclusao(self) -> None:
        """Conferência dos modelos de exclusão, numa thread própria."""
        import threading

        if self.manager and self.manager.running():
            QMessageBox.warning(
                self, "Bot rodando",
                "Pare o bot antes de conferir — os dois disputariam o teclado "
                "e o mouse do mesmo cliente.")
            return
        conta = self._account_of_row(self.tbl.currentRow())
        if conta is None:
            QMessageBox.information(
                self, "Nenhuma conta",
                "Selecione a conta na aba Contas antes de conferir.")
            return

        self.btn_conferir_exclusao.setEnabled(False)
        self.btn_conferir_exclusao.setText("🗑  Conferindo…")

        def trabalho() -> None:
            resultado = afericao.rodar(self.config, conta,
                                       on_status=self._on_status)
            self.afericao_pronta.emit(resultado)

        threading.Thread(target=trabalho, daemon=True,
                         name="conferir-exclusao").start()

    def _fim_da_afericao(self, resultado: dict) -> None:
        self.btn_conferir_exclusao.setEnabled(True)
        self.btn_conferir_exclusao.setText(
            "🗑  Conferir modelos de exclusão (conta selecionada)")
        if not resultado.get("ok"):
            QMessageBox.warning(self, "Conferir modelos",
                                resultado.get("erro", "falhou"))
            return
        # O texto vem PRONTO do Python — as duas interfaces dizem o mesmo.
        QMessageBox.information(self, "Conferir modelos",
                                resultado.get("resumo", ""))
        caminho = resultado.get("arquivo")
        if caminho:
            import os

            try:
                os.startfile(str(Path(caminho).resolve()))
            except Exception:
                pass

    # ==================================================================
    # Histórico de Quedas
    # ==================================================================

    def _pg_quedas(self) -> QWidget:
        """A mesma tela da web, com os mesmos textos.

        As frases vêm PRONTAS do `core.quedas` — as duas interfaces mostram o
        mesmo conteúdo, e duas traduções separadas divergiriam na primeira
        frase que alguém ajustasse.
        """
        page = QWidget()
        outer = QVBoxLayout(page)

        topo = QHBoxLayout()
        titulo = QLabel("Histórico de Quedas")
        titulo.setObjectName("tituloSecao")
        topo.addWidget(titulo)
        topo.addStretch()
        topo.addWidget(QLabel("Conta:"))
        self.cb_quedas_conta = QComboBox()
        self.cb_quedas_conta.setMinimumWidth(180)
        self.cb_quedas_conta.currentIndexChanged.connect(
            lambda _i: self._carregar_quedas())
        topo.addWidget(self.cb_quedas_conta)
        btn_copiar = QPushButton("Copiar relatório")
        btn_copiar.setToolTip(
            "Copia tudo, inclusive os detalhes técnicos, para você enviar ao "
            "suporte.")
        btn_copiar.clicked.connect(self._copiar_relatorio_de_quedas)
        topo.addWidget(btn_copiar)
        btn_pasta = QPushButton("Abrir a pasta")
        btn_pasta.clicked.connect(self._abrir_pasta_de_quedas)
        topo.addWidget(btn_pasta)
        outer.addLayout(topo)

        outer.addWidget(self._hint(
            "Toda vez que o jogo cai, o bot religa sozinho e anota aqui o que "
            f"aconteceu. Guardamos os últimos {quedas.DIAS_GUARDADOS} dias."))

        self.lista_quedas = QListWidget()
        self.lista_quedas.setWordWrap(True)
        self.lista_quedas.itemDoubleClicked.connect(self._abrir_print_da_queda)
        outer.addWidget(self.lista_quedas, 1)
        return page

    def _ao_trocar_de_secao(self, indice: int) -> None:
        if 0 <= indice < len(NOMES_DAS_SECOES) \
                and NOMES_DAS_SECOES[indice] == "Histórico de Quedas":
            self._carregar_quedas()

    def _conta_de_quedas(self) -> str | None:
        return self.cb_quedas_conta.currentData() or None

    def _carregar_quedas(self) -> None:
        registros = quedas.listar(self._conta_de_quedas())
        self._quedas_atuais = registros

        # Seletor: "Todas as contas" primeiro e padrão — a pergunta real é "o
        # que aconteceu essa noite", que atravessa contas.
        contas = quedas.contas_com_quedas()
        assinatura = "|".join(contas)
        if getattr(self, "_sig_quedas", None) != assinatura:
            self._sig_quedas = assinatura
            atual = self.cb_quedas_conta.currentData()
            self.cb_quedas_conta.blockSignals(True)
            self.cb_quedas_conta.clear()
            self.cb_quedas_conta.addItem("Todas as contas", None)
            for c in contas:
                self.cb_quedas_conta.addItem(c, c)
            idx = self.cb_quedas_conta.findData(atual)
            self.cb_quedas_conta.setCurrentIndex(max(0, idx))
            self.cb_quedas_conta.blockSignals(False)

        self.lista_quedas.clear()
        if not registros:
            self.lista_quedas.addItem(
                f"Nenhuma queda nos últimos {quedas.DIAS_GUARDADOS} dias. 👍")
            return
        for r in registros:
            linhas = [
                f"{r['quando_texto']} — conta {r.get('conta') or '?'}"
                + (f" ({r['personagem']})" if r.get("personagem") else ""),
                f"{r['motivo_texto']}.",
                f"{r['fazendo_texto']}"
                + (f", em {r['onde_texto']}" if r.get("onde_texto") else "") + ".",
            ]
            detalhe = []
            if r.get("run"):
                detalhe.append(f"run {r['run']}")
            if r.get("rodando_texto"):
                detalhe.append(f"rodando há {r['rodando_texto']}")
            if r.get("relogin"):
                detalhe.append(f"religou sozinho (relogin #{r['relogin']})")
            if detalhe:
                linhas.append(" · ".join(detalhe))
            if r.get("print_caminho"):
                linhas.append("📷 dê dois cliques para ver o print da tela")
            item = QListWidgetItem("\n".join(linhas))
            item.setData(Qt.ItemDataRole.UserRole, r.get("print_caminho"))
            self.lista_quedas.addItem(item)

    def _abrir_print_da_queda(self, item: QListWidgetItem) -> None:
        caminho = item.data(Qt.ItemDataRole.UserRole)
        if not caminho:
            return
        import os

        try:
            os.startfile(str(Path(caminho).resolve()))
        except Exception as exc:
            QMessageBox.warning(self, "Print", f"Não consegui abrir: {exc}")

    def _copiar_relatorio_de_quedas(self) -> None:
        texto = quedas.relatorio(getattr(self, "_quedas_atuais", []))
        QApplication.clipboard().setText(texto)
        self._enfileirar("", "relatório de quedas copiado")

    def _abrir_pasta_de_quedas(self) -> None:
        import os

        try:
            quedas.PASTA.mkdir(parents=True, exist_ok=True)
            os.startfile(str(quedas.PASTA.resolve()))
        except Exception as exc:
            QMessageBox.warning(self, "Pasta", f"Não consegui abrir: {exc}")

    # TEMPORÁRIO ----------------------------------------------------------
    def _testar_venda(self) -> None:
        """Roda só a venda, na conta selecionada, numa thread própria.

        Thread porque a venda leva minutos: rodar na thread da interface
        congelaria a janela inteira (e o log, que é justamente o que se quer
        acompanhar).
        """
        import threading

        # O próprio botão é a saída: com o bot parado, o botão Parar da barra
        # fica desabilitado, então não haveria como interromper a venda. A
        # flag é local (e não `teste_venda.em_andamento()`) porque ela precisa
        # valer JÁ no clique -- a thread só toma o lock dela um instante depois,
        # e nesse vão um clique duplo abriria dois testes.
        if getattr(self, "_teste_venda_ativo", False):
            teste_venda.cancelar()
            self.btn_teste_venda.setEnabled(False)
            self.btn_teste_venda.setText("⏹  Cancelando…")
            return

        if self.manager and self.manager.running():
            QMessageBox.warning(
                self, "Bot rodando",
                "Pare o bot antes de testar a venda — os dois disputariam o "
                "teclado e o mouse do mesmo cliente.")
            return
        conta = self._account_of_row(self.tbl.currentRow())
        if conta is None:
            QMessageBox.information(
                self, "Nenhuma conta",
                "Selecione a conta na aba Contas antes de testar a venda.")
            return

        self._teste_venda_ativo = True
        self.btn_teste_venda.setText("⏹  Vendendo… (clique para parar)")
        self._enfileirar(conta.login, "teste de venda iniciado")

        def trabalho() -> None:
            resultado = teste_venda.rodar(self.config, conta,
                                          on_status=self._on_status)
            self.teste_venda_pronto.emit(resultado)

        threading.Thread(target=trabalho, daemon=True,
                         name="teste-de-venda").start()

    def _fim_do_teste_de_venda(self, resultado: dict) -> None:
        self._teste_venda_ativo = False
        self.btn_teste_venda.setEnabled(True)
        self.btn_teste_venda.setText("🛒  Testar a venda (conta selecionada)")
        if resultado.get("ok"):
            self._enfileirar("", f"teste de venda concluído: "
                                 f"{resultado.get('vendidos', 0)} item(ns)")
        else:
            QMessageBox.warning(self, "Teste de venda",
                                resultado.get("erro", "falhou"))

    def _amostrar_cliques(self) -> None:
        """Varre coordenadas de clique direito no ponto onde o personagem está.

        Mesmo desenho do teste de venda: thread própria (a varredura leva
        minutos) e o próprio botão como saída.
        """
        import threading

        if getattr(self, "_amostragem_ativa", False):
            amostragem_de_cliques.cancelar()
            self.btn_amostragem.setEnabled(False)
            self.btn_amostragem.setText("⏹  Cancelando…")
            return

        if self.manager and self.manager.running():
            QMessageBox.warning(
                self, "Bot rodando",
                "Pare o bot antes de amostrar — os dois disputariam o teclado "
                "e o mouse do mesmo cliente.")
            return
        conta = self._account_of_row(self.tbl.currentRow())
        if conta is None:
            QMessageBox.information(
                self, "Nenhuma conta",
                "Selecione a conta na aba Contas antes de amostrar.")
            return

        self._amostragem_ativa = True
        self.btn_amostragem.setText("⏹  Amostrando… (clique para parar)")
        self._enfileirar(conta.login, "amostragem de cliques iniciada")

        def trabalho() -> None:
            resultado = amostragem_de_cliques.rodar(self.config, conta,
                                                    on_status=self._on_status)
            self.amostragem_pronta.emit(resultado)

        threading.Thread(target=trabalho, daemon=True,
                         name="amostragem-de-cliques").start()

    def _fim_da_amostragem(self, resultado: dict) -> None:
        self._amostragem_ativa = False
        self.btn_amostragem.setEnabled(True)
        self.btn_amostragem.setText(
            "🎯  Amostrar cliques neste ponto (conta selecionada)")
        if not resultado.get("ok"):
            QMessageBox.warning(self, "Amostragem de cliques",
                                resultado.get("erro", "falhou"))
            return
        # O texto vem PRONTO do Python (`amostragem_de_cliques.resumir`): as
        # duas interfaces mostram exatamente o mesmo veredito.
        resumo = resultado.get("resumo", "")
        self._enfileirar("", "amostragem concluída — "
                             + resumo.replace("\n", " | "))
        QMessageBox.information(self, "Amostragem de cliques", resumo)
    # ---------------------------------------------------------- TEMPORÁRIO

    def _abrir_logs(self) -> None:
        import os
        from pathlib import Path as _P

        pasta = _P("logs").absolute()
        pasta.mkdir(exist_ok=True)
        try:
            os.startfile(str(pasta))
        except Exception as exc:
            self._enfileirar("", f"não consegui abrir a pasta: {exc}")

    # -- log por conta ------------------------------------------------------

    def _enfileirar(self, conta: str, linha: str) -> None:
        """Põe uma linha na fila. NÃO toca na interface.

        Existe para o código da própria interface usar o mesmo caminho das
        threads do bot. Escrever direto no widget aqui traria de volta a
        travada: `_start` sozinho gera dezenas de linhas em sequência.
        """
        self._fila_de_log.append((conta, linha))

    def _descarregar_log(self) -> None:
        """Passa a fila para a tela, em lote. Chamado pelo temporizador.

        Três decisões que fazem a diferença:

          * UM `appendPlainText` para o lote inteiro, não um por linha. Cada
            chamada refaz o layout do documento; 400 chamadas por descarga
            custam ~400 vezes mais que uma só.
          * A contagem é INCREMENTAL. Antes ela era recalculada varrendo as
            12 000 linhas guardadas a cada linha nova -- ou seja, trabalho
            quadrático na thread da interface.
          * O combo de contas ganha item novo só quando aparece uma conta ainda
            não vista, controlado por um `set`, em vez de varrer o combo.
        """
        if not self._fila_de_log:
            return

        filtro = self.cb_log_conta.currentData() or ""
        mostrar: list[str] = []
        novas_contas: list[str] = []

        for _ in range(MAX_LINHAS_POR_DESCARGA):
            try:
                conta, linha = self._fila_de_log.popleft()
            except IndexError:
                break

            self._log_entries.append((conta, linha))
            self._total_de_linhas += 1
            if conta:
                self._contagem_por_conta[conta] = (
                    self._contagem_por_conta.get(conta, 0) + 1
                )
                if conta not in self._contas_no_filtro:
                    self._contas_no_filtro.add(conta)
                    novas_contas.append(conta)

            if not filtro or filtro == conta:
                prefixo = "" if filtro else (f"[{conta}] " if conta else "")
                mostrar.append(prefixo + linha)

        for conta in novas_contas:
            self.cb_log_conta.addItem(conta, conta)

        if mostrar:
            self.txt_log.appendPlainText("\n".join(mostrar))

        if self._fila_de_log:
            # Sobrou fila: avisa em vez de esconder. Fila crescendo significa
            # que o bot está gerando log mais rápido do que dá para mostrar --
            # o arquivo continua completo, mas é bom saber.
            self._atualizar_contagem_log(f" · {len(self._fila_de_log)} na fila")
        else:
            self._atualizar_contagem_log()

    def _redesenhar_log(self) -> None:
        """Refaz a tela do log quando o filtro de conta muda.

        Uma escrita só, com o texto inteiro montado antes -- o laço com um
        `appendPlainText` por linha demorava segundos com o histórico cheio, e
        durante esse tempo a interface ficava congelada.
        """
        filtro = self.cb_log_conta.currentData() or ""
        linhas = [
            (linha if filtro else (f"[{conta}] " if conta else "") + linha)
            for conta, linha in self._log_entries
            if not filtro or conta == filtro
        ]
        self.txt_log.setPlainText("\n".join(linhas))
        self.txt_log.moveCursor(QTextCursor.MoveOperation.End)
        self._atualizar_contagem_log()

    def _atualizar_contagem_log(self, extra: str = "") -> None:
        filtro = self.cb_log_conta.currentData() or ""
        if filtro:
            total = self._contagem_por_conta.get(filtro, 0)
            self.lbl_log_contagem.setText(f"{total} linha(s) desta conta{extra}")
        else:
            self.lbl_log_contagem.setText(f"{self._total_de_linhas} linha(s){extra}")

    def _limpar_log(self) -> None:
        self._log_entries.clear()
        self._fila_de_log.clear()
        self._contagem_por_conta.clear()
        self._total_de_linhas = 0
        self.txt_log.clear()
        self._atualizar_contagem_log()

    # ==================================================================
    # Tempo real
    # ==================================================================

    def _wire_live_updates(self) -> None:
        self.in_client_bat.textChanged.connect(self._apply_live)
        for w in (self.cb_resolution, self.cb_launch_delay):
            w.currentIndexChanged.connect(self._apply_live)
        self.cb_resolution.currentIndexChanged.connect(self._atualizar_resolucao)
        self.ck_minimize.stateChanged.connect(self._apply_live)
        self.ck_reuse.stateChanged.connect(self._apply_live)
        self.tbl.itemChanged.connect(self._on_table_item)

    def _atualizar_resolucao(self, *_args) -> None:
        res = self.cb_resolution.currentData() or "auto"
        if res == "auto":
            self.lbl_res.setText(
                "<b>Recomendado.</b> O bot mede a janela do jogo e usa o tamanho "
                "real, seja qual for. Não há como a configuração divergir do "
                "jogo — e essa divergência já causou o login clicar no campo "
                "errado."
            )
        elif res == VALIDATED_RESOLUTION:
            self.lbl_res.setText(
                "Resolução em que tudo foi medido e validado em produção. Mesmo "
                "assim, o bot confere o tamanho real da janela e usa o que "
                "encontrar."
            )
        else:
            self.lbl_res.setText(
                "A interface do jogo <b>não escala</b> — os elementos têm tamanho "
                "fixo e são ancorados às bordas. O bot localiza os botões por "
                "imagem e calcula o resto a partir deles.<br><br>"
                "Esta escolha é apenas um palpite inicial: o que vale é o tamanho "
                "medido da janela quando o cliente abre."
            )

    def _apply_live(self, *_args) -> None:
        if self._loading:
            return
        self._collect()
        try:
            self.config.save(self.config_path)
        except Exception as exc:
            self.log_line.emit(f"Não foi possível salvar a configuração: {exc}")

    def _on_table_item(self, item: QTableWidgetItem) -> None:
        if self._loading:
            return
        conta = self._account_of_row(item.row())
        alternou_ativa = False
        if conta is not None:
            if item.column() == COL_ATIVA:
                marcada = item.checkState() == Qt.CheckState.Checked
                # DESATIVAR um reseter deixa outra conta órfã: mesmo bloqueio da
                # remoção. A caixa VOLTA a marcar, e o `_loading` evita que essa
                # volta dispare este mesmo tratador de novo.
                if not marcada and self._bloqueado_por_ser_reseter(
                        conta, "desativar"):
                    self._loading = True
                    try:
                        item.setCheckState(Qt.CheckState.Checked)
                    finally:
                        self._loading = False
                    return
                conta.enabled = marcada
                alternou_ativa = True
            elif item.column() == COL_LOGIN:
                conta.login = item.text().strip()
        self._apply_live()
        if alternou_ativa and conta is not None:
            self._sincronizar_contas(conta)

    def _sincronizar_contas(self, conta: Account | None = None) -> None:
        """Põe o bot em execução de acordo com as contas ativas agora."""
        if not (self.manager and self.manager.running()):
            return
        if conta is not None and conta.enabled:
            problemas = conta.validate()
            if problemas:
                QMessageBox.warning(
                    self, "Conta incompleta",
                    "Não foi possível ativar esta conta:\n\n• "
                    + "\n• ".join(problemas),
                )
                return
        iniciadas = self.manager.sync_accounts()
        for login in iniciadas:
            self.log_line.emit(f"[{login}] conta ativada — abrindo o jogo e logando")

    # ==================================================================
    # Carregar / coletar
    # ==================================================================

    def _load_into_widgets(self) -> None:
        cfg = self.config
        self.in_client_bat.setText(cfg.client_bat)
        idx = self.cb_resolution.findData(cfg.resolution)
        self.cb_resolution.setCurrentIndex(idx if idx >= 0 else 0)
        self._atualizar_resolucao()
        idx = self.cb_launch_delay.findData(float(cfg.launch_delay))
        if idx < 0:
            self.cb_launch_delay.addItem(
                f"{segundos_para_ms(cfg.launch_delay)} ms",
                float(cfg.launch_delay))
            idx = self.cb_launch_delay.count() - 1
        self.cb_launch_delay.setCurrentIndex(idx)
        self.ck_minimize.setChecked(cfg.minimize_clients)
        self.ck_reuse.setChecked(cfg.reuse_login_screen_clients)

        self.tbl.setRowCount(0)
        for conta in cfg.accounts:
            self._add_row(conta)

    def _collect(self) -> None:
        cfg = self.config
        cfg.client_bat = self.in_client_bat.text().strip()
        cfg.resolution = self.cb_resolution.currentData() or "auto"
        cfg.launch_delay = self.cb_launch_delay.currentData() or 8.0
        cfg.minimize_clients = self.ck_minimize.isChecked()
        cfg.reuse_login_screen_clients = self.ck_reuse.isChecked()

        cfg.accounts = self._collect_accounts()

    # ==================================================================
    # Controles
    # ==================================================================

    def _browse_client(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecione o Client.bat", "", "Batch (*.bat);;Todos (*.*)"
        )
        if caminho:
            self.in_client_bat.setText(caminho)

    def _start(self) -> None:
        """Liga o bot, registrando cada passo.

        Tudo aqui é envolvido em try/except e logado. Numa versão anterior o bot
        simplesmente não fez nada e não gerou log nenhum -- sem registro, não há
        como saber onde parou, e depurar vira adivinhação.
        """
        self.nav.setCurrentRow(NOMES_DAS_SECOES.index("Log"))
        self._enfileirar("", "=" * 56)
        self._enfileirar("", "Botão Iniciar pressionado")

        try:
            self._apply_live()
            self._enfileirar(
                "", f"configuração coletada: {len(self.config.accounts)} conta(s), "
                    f"{len(self.config.enabled_accounts())} ativa(s)"
            )

            problemas = self.config.validate()
            if problemas:
                for p in problemas:
                    self._enfileirar("", f"CONFIGURAÇÃO INVÁLIDA: {p}")
                QMessageBox.warning(
                    self, "Configuração incompleta",
                    "Corrija antes de iniciar:\n\n• " + "\n• ".join(problemas),
                )
                return

            self._enfileirar("", "criando o gerenciador")
            self.manager = BotManager(self.config, on_status=self._on_status)

            self._enfileirar("", "chamando start() do gerenciador")
            erros = self.manager.start()
            if erros:
                for e in erros:
                    self._enfileirar("", f"ERRO AO INICIAR: {e}")
                QMessageBox.warning(self, "Não foi possível iniciar",
                                    "\n• ".join([""] + erros))
                self.manager = None
                return

            vivos = [s.account.login for s in self.manager.supervisors]
            self._enfileirar("", f"supervisores criados: {vivos or 'NENHUM'}")
            if not vivos:
                self._enfileirar(
                    "", "ATENÇÃO: nenhum supervisor subiu. Veja as linhas de "
                        "'sincronizando' acima para ver qual conta foi "
                        "descartada e por quê."
                )

            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.btn_pause.setEnabled(True)

        except Exception as exc:
            import traceback

            self._enfileirar("", f"FALHA AO INICIAR: {type(exc).__name__}: {exc}")
            for linha in traceback.format_exc().splitlines():
                self._enfileirar("", "   " + linha)
            logging.getLogger("blazes").exception("Falha ao iniciar")
            QMessageBox.critical(
                self, "Falha ao iniciar",
                f"{type(exc).__name__}: {exc}\n\n"
                "O detalhe completo está na aba Log.",
            )
            self.manager = None

    def _toggle_pause(self) -> None:
        if not self.manager:
            return
        if self.manager.paused:
            self.manager.resume()
            self.btn_pause.setText("Pausar")
        else:
            self.manager.pause()
            self.btn_pause.setText("Retomar")

    def _stop(self) -> None:
        if self.manager:
            self.manager.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("Pausar")

    def _on_status(self, login: str, mensagem: str) -> None:
        self.log_line.emit(f"[{login}] {mensagem}")

    def _refresh_status(self) -> None:
        if not self.manager:
            return
        rodando = self.manager.running()
        if not rodando:
            self._stop()
        # Sessão vem do gerenciador (vazio se o bot está parado); "hoje" vem do
        # histórico persistido, que continua disponível mesmo parado.
        resumo = self.manager.summary() if rodando else {}
        total = {"runs": 0, "success": 0, "fail": 0, "relogins": 0}
        for login, d in resumo.items():
            for chave in ("runs", "success", "fail", "relogins"):
                total[chave] += d[chave]

        self._preencher_seletor_stats(resumo)

        # Reflete ao vivo o BC farm de cada linha: o bot pode desligar a flag
        # sozinho (ex.: a conta foi vender sem tecla de retorno configurada).
        # Só seta quando difere, para não disparar stateChanged à toa.
        for linha in range(self.tbl.rowCount()):
            item = self.tbl.item(linha, COL_ATIVA)
            if item is None:
                continue
            conta = item.data(ACCOUNT_ROLE)
            wrap_hh = self.tbl.cellWidget(linha, COL_HH)
            if wrap_hh is not None:
                caixa_hh = wrap_hh.findChild(QCheckBox)
                if caixa_hh is not None and caixa_hh.isChecked() != conta.hh_farm:
                    caixa_hh.setChecked(conta.hh_farm)
            wrap = self.tbl.cellWidget(linha, COL_FARM)
            caixa = wrap.findChild(QCheckBox) if wrap else None
            if caixa is not None and caixa.isChecked() != conta.bc_farm:
                caixa.setChecked(conta.bc_farm)

        if not rodando:
            self.status_label.setText("Parado.")
            return
        prefixo = "PAUSADO — " if self.manager.paused else "Rodando — "
        self.status_label.setText(
            prefixo
            + f"{len(resumo)} conta(s)   |   {total['runs']} runs   "
              f"({total['success']} ok / {total['fail']} falhas)   |   "
              f"{total['relogins']} relogins"
        )

    def _preencher_seletor_stats(self, resumo: dict[str, dict]) -> None:
        """Preenche o seletor de personagens com quem tem pelo menos uma run.

        Só entram contas com run registrada HOJE (persistida) ou na sessão;
        quem nunca rodou não aparece. A primeira da lista é a de MAIS runs --
        e é ela que vem selecionada, porque é a que o usuário mais provavelmente
        quer ver. Preserva a seleção atual quando a conta continua elegível.
        """
        candidatos: list[tuple[int, str, str]] = []  # (total_runs, login, nick)
        for conta in self.config.accounts:
            login = conta.login
            if not login:
                continue
            dia = stats_diarias.ultimos_dias(login, 1)[0][1]
            sess = resumo.get(login, {})
            total = dia.get("runs", 0) + sess.get("runs", 0)
            if total <= 0:
                continue
            nick = (conta.last_char_name or "").strip() or login
            candidatos.append((total, login, nick))
        candidatos.sort(key=lambda t: -t[0])

        atual = self.cb_stats_conta.currentData() or ""
        self.cb_stats_conta.blockSignals(True)
        self.cb_stats_conta.clear()
        for _total, login, nick in candidatos:
            self.cb_stats_conta.addItem(nick, login)
        idx = self.cb_stats_conta.findData(atual)
        if idx < 0:
            idx = 0 if candidatos else -1
        self.cb_stats_conta.setCurrentIndex(idx)
        self.cb_stats_conta.blockSignals(False)
        self.lbl_stats_sem_conta.setVisible(not candidatos)
        self._preencher_stats_conta()

    def _preencher_stats_conta(self) -> None:
        """Preenche os cards com os dados da personagem selecionada."""
        login = self.cb_stats_conta.currentData() or ""
        if not login:
            for card in self.cards.values():
                card.set_value("—")
            self.tbl_historico.setRowCount(0)
            return

        resumo = self.manager.summary() if (self.manager and self.manager.running()) else {}
        sess = resumo.get(login, {})
        hoje = stats_diarias.ultimos_dias(login, 1)[0][1]
        runs = hoje.get("runs", 0)

        # "Tempo da run atual" é o cronômetro AO VIVO: run_now vem da sessão
        # (RunStats.run_now_seconds) e zera entre runs. O card é repreenchido
        # a cada _refresh_status (1,5 s), então o tempo "corre" visivelmente.
        run_now = sess.get("run_now", 0.0)
        self.cards["run_agora"].set_value(
            "—" if not sess or run_now <= 0 else formata_duracao(run_now))
        # "Tempo até o boss (atual)" é o cronômetro do trajeto AO VIVO: conta
        # do início da run e CONGELA na chegada do boss (RunStats.boss_now_seconds,
        # que zera entre runs). Mesma cadência do card "Tempo da run atual".
        boss_now = sess.get("boss_now", 0.0)
        self.cards["boss_agora"].set_value(
            "—" if not sess or boss_now <= 0 else formata_duracao(boss_now))

        self.cards["runs_hoje"].set_value(str(runs))
        self.cards["success_hoje"].set_value(str(hoje.get("success", 0)))
        self.cards["fail_hoje"].set_value(str(hoje.get("fail", 0)))
        self.cards["taxa_hoje"].set_value(
            "—" if not runs else
            f"{100.0 * hoje.get('success', 0) / runs:.0f}%")
        self.cards["media_hoje"].set_value(
            "—" if not runs else formata_duracao(
                hoje.get("total_run_seconds", 0.0) / runs))
        # "T. até boss (últ.)" e "T. total (últ.)" são FIXOS: referem-se à
        # ÚLTIMA run concluída (a anterior à atual), persistida. O ao vivo fica
        # nos cards "Tempo da run atual" e "Tempo até o boss (atual)" acima.
        self.cards["boss_ult"].set_value(
            "—" if not runs else formata_duracao(
                hoje.get("last_boss_seconds", 0.0)))
        self.cards["total_ult"].set_value(
            "—" if not sess else formata_duracao(sess.get("last_run", 0.0)))
        self.cards["total_hoje"].set_value(
            "—" if not runs else formata_duracao(
                hoje.get("total_run_seconds", 0.0)))
        self.cards["sessao_runs"].set_value(str(sess.get("runs", 0)))
        self.cards["sessao_ok"].set_value(
            f"{sess.get('success', 0)} ok / {sess.get('fail', 0)} falhas")
        self._preencher_historico(login)

    def _preencher_historico(self, login: str) -> None:
        """Preenche a tabela com os DIAS ANTERIORES da personagem selecionada.

        Hoje não entra na listagem: ele é o número principal, nos cards de
        cima. Aqui aparecem ontem, anteontem… até a semana, para o usuário
        comparar o progresso do dia atual com os anteriores. Só gera linhas se
        houver histórico salvo em disco para esta personagem.
        """
        hoje_iso = date.today().isoformat()
        linhas: list[tuple[str, str, str, str, str, str]] = []
        if stats_diarias.conhece(login):
            for dia, d in stats_diarias.ultimos_dias(login):
                if dia == hoje_iso:
                    continue
                media = (d["total_run_seconds"] / d["runs"]
                         if d["runs"] else None)
                boss = (d.get("total_boss_seconds", 0.0) / d["runs"]
                        if d["runs"] else None)
                linhas.append((
                    dia,
                    str(d["runs"]),
                    str(d["success"]),
                    str(d["fail"]),
                    "—" if boss is None else formata_duracao(boss),
                    "—" if media is None else formata_duracao(media),
                ))

        self.tbl_historico.setRowCount(len(linhas))
        for i, linha in enumerate(linhas):
            for j, valor in enumerate(linha):
                item = QTableWidgetItem(valor)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_historico.setItem(i, j, item)

    def closeEvent(self, event) -> None:
        if self.manager:
            self.manager.stop()
        try:
            self.config.save(self.config_path)
        except Exception:
            pass
        event.accept()
