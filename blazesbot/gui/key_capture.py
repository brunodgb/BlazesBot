"""
Captura de tecla por pressionamento.

Em vez de escolher numa lista com 69 opções, o jogador clica no campo e aperta a
tecla que usa no jogo. É mais rápido e elimina a chance de escolher a tecla
errada na lista.

ESC limpa o atalho -- é a mesma convenção do RaaskiBot ("[ESC] will
remove/disable the shortcut"), então quem já usa o outro bot não precisa
aprender nada novo.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QPushButton, QToolTip

from .theme import ACCENT, BG_DEEP, BORDER_SOFT, TEXT, TEXT_FAINT, WARN

# Teclas do Qt que o bot sabe enviar, mapeadas para o nome usado internamente.
_ESPECIAIS: dict[int, str] = {
    Qt.Key.Key_Space.value: "SPACE",
    Qt.Key.Key_Tab.value: "TAB",
    Qt.Key.Key_Return.value: "ENTER",
    Qt.Key.Key_Enter.value: "ENTER",
    Qt.Key.Key_Shift.value: "SHIFT",
    Qt.Key.Key_Control.value: "CTRL",
    Qt.Key.Key_Alt.value: "ALT",
    Qt.Key.Key_Insert.value: "INSERT",
    Qt.Key.Key_Delete.value: "DELETE",
    Qt.Key.Key_Home.value: "HOME",
    Qt.Key.Key_End.value: "END",
    Qt.Key.Key_Up.value: "UP",
    Qt.Key.Key_Down.value: "DOWN",
    Qt.Key.Key_Left.value: "LEFT",
    Qt.Key.Key_Right.value: "RIGHT",
}


def _nome_da_tecla(event: QKeyEvent) -> str | None:
    """Converte o evento de teclado no nome que o bot usa. None = não aceita."""
    codigo = event.key()

    if codigo == Qt.Key.Key_Escape.value:
        return ""                                  # ESC = não usar

    if codigo in _ESPECIAIS:
        return _ESPECIAIS[codigo]

    # F1 a F12
    if Qt.Key.Key_F1.value <= codigo <= Qt.Key.Key_F12.value:
        return f"F{codigo - Qt.Key.Key_F1.value + 1}"

    # Teclado numérico: o jogo trata como teclas separadas das de cima.
    if event.modifiers() & Qt.KeyboardModifier.KeypadModifier:
        if Qt.Key.Key_0.value <= codigo <= Qt.Key.Key_9.value:
            return f"NUM{codigo - Qt.Key.Key_0.value}"

    # Dígitos e letras
    if Qt.Key.Key_0.value <= codigo <= Qt.Key.Key_9.value:
        return chr(codigo)
    if Qt.Key.Key_A.value <= codigo <= Qt.Key.Key_Z.value:
        return chr(codigo)

    return None


class KeyCapture(QPushButton):
    """Campo de atalho: clique e aperte a tecla. ESC limpa."""

    keyChanged = pyqtSignal(str)

    def __init__(self, valor: str = "", parent=None, conflito=None) -> None:
        super().__init__(parent)
        self._valor = (valor or "").upper()
        self._capturando = False
        # Função opcional: recebe (tecla, este_campo) e devolve o RÓTULO do
        # campo que já a usa, ou None se estiver livre. O próprio campo é
        # ignorado na conta -- reapertar a mesma tecla nele é um nada-a-fazer,
        # não um conflito. Ver `keyPressEvent`.
        self._conflito = conflito
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(96)
        self.clicked.connect(self._iniciar_captura)
        self._atualizar()

    # -- estado ------------------------------------------------------------

    def key(self) -> str:
        return self._valor

    def set_key(self, valor: str) -> None:
        self._valor = (valor or "").upper()
        self._capturando = False
        self._atualizar()

    def _atualizar(self) -> None:
        if self._capturando:
            self.setText("aperte a tecla…")
            cor, borda, texto = BG_DEEP, WARN, WARN
        elif self._valor:
            self.setText(self._valor)
            cor, borda, texto = BG_DEEP, ACCENT, TEXT
        else:
            self.setText("— não usar —")
            cor, borda, texto = BG_DEEP, BORDER_SOFT, TEXT_FAINT

        self.setStyleSheet(f"""
            QPushButton {{
                background: {cor};
                border: 1px solid {borda};
                border-radius: 6px;
                padding: 6px 10px;
                color: {texto};
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {ACCENT};
            }}
        """)
        self.setToolTip(
            "Clique e aperte a tecla que você usa no jogo.\n"
            "ESC limpa o atalho (não usar)."
        )

    # -- captura -----------------------------------------------------------

    def _iniciar_captura(self) -> None:
        self._capturando = True
        self._atualizar()
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._capturando:
            super().keyPressEvent(event)
            return

        nome = _nome_da_tecla(event)
        if nome is None:
            # Tecla que o bot não sabe enviar: ignora e continua esperando.
            return

        # TECLA REPETIDA NÃO PASSA. O jogo não permite a mesma tecla em duas
        # funções -- cada uma tem um destino só no Keys Setting --, então
        # aceitar aqui descreveria algo que não existe: o bot acharia que
        # trocou de barra de atalhos e na verdade disparou uma skill, sem
        # nunca perceber. O erro seria silencioso, e é por isso que ele é
        # barrado na digitação, e não só na hora de salvar.
        if self._conflito is not None:
            onde = self._conflito(nome, self)
            if onde:
                QToolTip.showText(
                    self.mapToGlobal(self.rect().bottomLeft()),
                    f"A tecla {nome} já está em “{onde}”.\n"
                    "O jogo não aceita a mesma tecla em duas funções.",
                    self)
                return          # continua capturando: aperte outra

        self._valor = nome
        self._capturando = False
        self._atualizar()
        self.keyChanged.emit(self._valor)

    def focusOutEvent(self, event) -> None:
        if self._capturando:
            self._capturando = False
            self._atualizar()
        super().focusOutEvent(event)
