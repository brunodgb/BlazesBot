"""
Ícone de ajuda com dica instantânea.

Duas decisões:

1. TODA explicação mora aqui, não na tela. Texto solto espalhado polui e faz o
   olho pular o que importa, que são os campos. Quem quer saber passa o mouse.

2. A dica aparece NA HORA. O atraso padrão do Qt (cerca de meio segundo) faz
   parecer que o ícone não funciona, e a pessoa desiste antes de a dica surgir.
   Aqui ela é mostrada no `enterEvent`, sem espera.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QLabel, QToolTip, QWidget

from .theme import ACCENT, BG_DEEP, BORDER


class HelpTip(QLabel):
    """Um "?" que explica um campo ou um grupo."""

    def __init__(self, texto: str, parent: QWidget | None = None) -> None:
        super().__init__("?", parent)
        self._texto = texto
        self.setToolTip(texto)
        self.setFixedSize(20, 20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setStyleSheet(f"""
            QLabel {{
                color: {ACCENT};
                background: {BG_DEEP};
                border: 1px solid {BORDER};
                border-radius: 10px;
                font-weight: 700;
                font-size: 13px;
            }}
            QLabel:hover {{
                border-color: {ACCENT};
                color: #E08A4C;
            }}
        """)

    def enterEvent(self, event) -> None:
        # Mostra imediatamente, sem o atraso padrão do Qt.
        QToolTip.showText(
            self.mapToGlobal(QPoint(self.width(), self.height() // 2)),
            self._texto,
            self,
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().leaveEvent(event)

    def set_help(self, texto: str) -> None:
        self._texto = texto
        self.setToolTip(texto)
