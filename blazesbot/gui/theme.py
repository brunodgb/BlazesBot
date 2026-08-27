"""
Tema visual do BlazesBot.

=========================================================================
A PALETA
=========================================================================

O vermelho #541E1B é a identidade: ele fica nos FUNDOS, nas bordas, nas abas
selecionadas e nos cabeçalhos. Um âmbar quente (#E08A4C) é o destaque -- vizinho
do vermelho no círculo cromático, o que dá contraste de brilho sem briga de
matiz.

=========================================================================
O TEXTO NÃO É VERMELHO. ISTO É DELIBERADO.
=========================================================================

A versão anterior tingia o texto com o mesmo matiz do fundo: #F2E7E2 para o texto
normal e #B49A93 para o secundário -- os dois são rosas dessaturados. Sobre painel
vermelho escuro, texto rosado tem pouca separação de matiz E pouca separação de
luminosidade: o olho lê com esforço, e as explicações (que usam justamente o tom
secundário) ficavam praticamente ilegíveis.

Agora o texto é NEUTRO, e a escala é por função e por contraste medido sobre o
fundo #1F0C0B:

  TEXT       #F7F5F5   ~16:1  o que se lê de verdade -- rótulos, valores, log
  TEXT_DIM   #BEB7B6    ~8:1  explicações e legendas; passa AA com folga
  TEXT_FAINT #8E8483   ~4.6:1 apenas placeholder e texto desabilitado

A identidade continua vermelha porque quem carrega a identidade é o fundo. Cor
tem que sobrar para o que precisa de destaque -- e num painel onde tudo é
vermelho, nada é.
"""
from __future__ import annotations

# Base pedida
BASE = "#541E1B"

# Fundos, do mais profundo ao mais claro (mesmo matiz da base)
BG_DEEP = "#150807"
BG = "#1F0C0B"
PANEL = "#2C1311"
PANEL_ALT = "#3A1815"

# Bordas e separadores
BORDER = "#7A322C"
BORDER_SOFT = "#4A201C"

# Destaque: âmbar quente, análogo ao vermelho da base
ACCENT = "#E08A4C"
ACCENT_HOVER = "#F0A063"
ACCENT_PRESSED = "#BE7038"
ACCENT_SOFT = "#8A5030"

# Texto -- NEUTRO de propósito. Ver o comentário no topo do arquivo.
TEXT = "#F7F5F5"
TEXT_DIM = "#BEB7B6"
TEXT_FAINT = "#8E8483"

# Estados. Claros o bastante para serem lidos sobre fundo escuro, e não apenas
# para colorir uma borda: eles aparecem como TEXTO em avisos.
OK = "#8FC46A"
WARN = "#F0C24A"
ERR = "#F07A6E"

FONT = "Segoe UI"


STYLESHEET = f"""
* {{
    font-family: "{FONT}", "Noto Sans", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QWidget {{
    background-color: {BG};
}}

/* ---------- Abas ---------- */
QTabWidget::pane {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    top: -1px;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: {BG_DEEP};
    color: {TEXT_DIM};
    border: 1px solid {BORDER_SOFT};
    border-bottom: none;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    padding: 9px 20px;
    margin-right: 3px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {BASE};
    color: {TEXT};
    border-color: {BORDER};
}}
QTabBar::tab:hover:!selected {{
    background: {PANEL_ALT};
    color: {TEXT};
}}

/* ---------- Grupos ---------- */
QGroupBox {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER_SOFT};
    border-radius: 8px;
    margin-top: 16px;
    padding: 14px 12px 10px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 3px 12px;
    background: {BASE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    color: {TEXT};
}}

/* ---------- Campos ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {{
    background: {BG_DEEP};
    border: 1px solid {BORDER_SOFT};
    border-radius: 6px;
    padding: 6px 9px;
    selection-background-color: {ACCENT};
    selection-color: {BG_DEEP};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border: 1px solid {BORDER};
}}
QLineEdit::placeholder {{
    color: {TEXT_FAINT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {ACCENT};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {BG_DEEP};
    border: 1px solid {BORDER};
    selection-background-color: {BASE};
    outline: none;
    padding: 3px;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {PANEL};
    border: none;
    width: 17px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {BASE};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 4px solid {ACCENT};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-top: 4px solid {ACCENT};
}}

/* ---------- Botões ---------- */
QPushButton {{
    background: {BASE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {BORDER};
    border-color: {ACCENT_SOFT};
}}
QPushButton:pressed {{
    background: {BG_DEEP};
}}
QPushButton:disabled {{
    background: {PANEL};
    color: {TEXT_FAINT};
    border-color: {BORDER_SOFT};
}}
QPushButton#primary {{
    background: {ACCENT};
    border-color: {ACCENT_HOVER};
    color: {BG_DEEP};
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#primary:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton#danger {{
    background: {PANEL_ALT};
    border-color: {ERR};
    color: {ERR};
}}
QPushButton#danger:hover {{
    background: {ERR};
    color: {BG_DEEP};
}}

/* ---------- Tabela ---------- */
QTableWidget {{
    background: {BG_DEEP};
    border: 1px solid {BORDER_SOFT};
    border-radius: 6px;
    gridline-color: {BORDER_SOFT};
    selection-background-color: {BASE};
}}
QTableWidget::item {{
    padding: 5px;
    border: none;
}}
QTableWidget::item:selected {{
    background: {BASE};
}}
QHeaderView::section {{
    background: {BASE};
    color: {TEXT};
    border: none;
    border-right: 1px solid {BORDER};
    padding: 8px 6px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background: {BASE};
    border: none;
}}

/* ---------- Caixas de seleção ---------- */
QCheckBox {{
    spacing: 9px;
}}
QCheckBox::indicator, QTableWidget::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {BG_DEEP};
}}
QCheckBox::indicator:hover, QTableWidget::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked, QTableWidget::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT_HOVER};
}}
QCheckBox:disabled {{
    color: {TEXT_FAINT};
}}

/* Radio: sem regra própria, o Fusion desenhava um círculo cinza quase invisível
   sobre o painel escuro -- e a escolha da rota (Padrão / Segura) é feita nele. */
QRadioButton {{
    spacing: 9px;
}}
QRadioButton::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG_DEEP};
}}
QRadioButton::indicator:hover {{
    border-color: {ACCENT};
}}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border: 4px solid {BG_DEEP};
}}

/* ---------- Log ----------
   O log é para LER, e às vezes por horas. Texto cheio (TEXT), não o tom
   secundário: com TEXT_DIM sobre fundo quase preto, acompanhar o bot cansava a
   vista e era exatamente a queixa de legibilidade. */
QPlainTextEdit#log {{
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
    background: {BG_DEEP};
    color: {TEXT};
    border: 1px solid {BORDER_SOFT};
    selection-background-color: {ACCENT_SOFT};
}}

/* ---------- Rodapé ---------- */
QLabel#status {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    color: {TEXT};
    font-weight: 600;
}}
QLabel#hint {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
/* Estados, usados como TEXTO e não só como borda. */
QLabel#ok {{ color: {OK}; font-weight: 600; }}
QLabel#warn {{ color: {WARN}; font-weight: 600; }}
QLabel#err {{ color: {ERR}; font-weight: 600; }}
QLabel#badge {{
    background: {BASE};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 10px;
    color: {ACCENT};
    font-weight: 600;
}}
QLabel#title {{
    font-size: 19px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#subtitle {{
    color: {TEXT_DIM};
    font-size: 12px;
}}

/* ---------- Barra de rolagem ---------- */
QScrollBar:vertical {{
    background: {BG_DEEP};
    width: 11px;
    margin: 0;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 26px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_SOFT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_DEEP};
    height: 11px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 26px;
}}

/* ---------- Diálogos ---------- */
QMessageBox {{
    background: {PANEL};
}}
QToolTip {{
    background: {BG_DEEP};
    color: {TEXT};
    border: 1px solid {ACCENT_SOFT};
    padding: 6px;
}}
"""
