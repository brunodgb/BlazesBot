"""
Widgets customizados do BlazesBot.

`PercentBar` reproduz o controle de limiar do RaaskiBot: um rótulo sobre barra
colorida mostrando "HP: 85%" e um deslizador ao lado. É mais legível que um
campo numérico solto, porque a cor comunica de imediato do que se trata e a
largura da barra dá a noção do valor sem precisar ler o número.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .theme import ACCENT, BASE, BG_DEEP, BORDER, BORDER_SOFT, TEXT, TEXT_DIM

# Cores por tipo de recurso
COR_HP = "#8E2B22"
COR_HP_BORDA = "#C4544A"
COR_MP = "#22488E"
COR_MP_BORDA = "#4A7BC4"
COR_NEUTRA = BASE


class PercentBar(QWidget):
    """Limiar em porcentagem, com barra colorida e deslizador."""

    valueChanged = pyqtSignal(int)

    def __init__(
        self,
        rotulo: str = "HP",
        valor: int = 50,
        minimo: int = 1,
        maximo: int = 100,
        tipo: str = "hp",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.rotulo = rotulo

        if tipo == "hp":
            fundo, borda = COR_HP, COR_HP_BORDA
        elif tipo == "mp":
            fundo, borda = COR_MP, COR_MP_BORDA
        else:
            fundo, borda = COR_NEUTRA, BORDER

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFixedWidth(118)
        self.label.setStyleSheet(f"""
            background: {fundo};
            border: 1px solid {borda};
            border-radius: 5px;
            padding: 4px 6px;
            color: {TEXT};
            font-weight: 600;
        """)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(minimo, maximo)
        self.slider.setValue(valor)
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BG_DEEP};
                border: 1px solid {BORDER_SOFT};
                height: 5px;
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {borda};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                border: 1px solid {TEXT};
                width: 11px;
                margin: -5px 0;
                border-radius: 5px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {TEXT};
            }}
        """)
        self.slider.valueChanged.connect(self._on_change)

        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        self._atualiza(valor)

    def _on_change(self, valor: int) -> None:
        self._atualiza(valor)
        self.valueChanged.emit(valor)

    def _atualiza(self, valor: int) -> None:
        self.label.setText(f"{self.rotulo}: {valor}%")

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, valor: int) -> None:
        self.slider.setValue(valor)


class SideNav(QListWidget):
    """Navegação lateral por seções, no lugar de abas no topo.

    Com muitas seções, abas no topo ficam apertadas e cortam o texto. A lista
    vertical acomoda nomes longos e deixa claro onde você está.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(186)
        self.setSpacing(2)
        self.setStyleSheet(f"""
            QListWidget {{
                background: {BG_DEEP};
                border: 1px solid {BORDER_SOFT};
                border-radius: 8px;
                padding: 7px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border-radius: 6px;
                color: {TEXT_DIM};
                font-weight: 600;
            }}
            QListWidget::item:hover {{
                background: {BORDER_SOFT};
                color: {TEXT};
            }}
            QListWidget::item:selected {{
                background: {BASE};
                color: {TEXT};
            }}
        """)

    def adicionar(self, texto: str, icone: str = "") -> None:
        """Adiciona uma seção, opcionalmente com um ícone antes do nome.

        O ícone é um caractere (emoji), não um arquivo: não há o que instalar,
        funciona em qualquer máquina e escala com a fonte. Serve para achar a
        seção de relance -- com o bot rodando, a pessoa alterna entre Contas e
        Log várias vezes por minuto.
        """
        item = QListWidgetItem(f"{icone}  {texto}" if icone else texto)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.addItem(item)


class StatCard(QWidget):
    """Caixinha de estatística: rótulo em cima, valor grande embaixo."""

    def __init__(self, rotulo: str, valor: str = "0", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)

        self.lbl_rotulo = QLabel(rotulo)
        self.lbl_rotulo.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        self.lbl_valor = QLabel(valor)
        self.lbl_valor.setStyleSheet(
            f"color: {TEXT}; font-size: 19px; font-weight: 700;"
        )

        layout.addWidget(self.lbl_rotulo)
        layout.addWidget(self.lbl_valor)

        self.setStyleSheet(f"""
            StatCard {{
                background: {BG_DEEP};
                border: 1px solid {BORDER_SOFT};
                border-radius: 7px;
            }}
        """)

    def set_value(self, valor: str) -> None:
        self.lbl_valor.setText(valor)


def formata_duracao(segundos: float) -> str:
    """Formata segundos como '1d 2h 3m 4s', omitindo o que for zero."""
    total = int(max(0, segundos))
    dias, resto = divmod(total, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segs = divmod(resto, 60)
    if dias:
        return f"{dias}d {horas}h {minutos}m"
    if horas:
        return f"{horas}h {minutos}m {segs}s"
    if minutos:
        return f"{minutos}m {segs}s"
    return f"{segs}s"
