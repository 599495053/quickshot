from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QPushButton

from .theme import app_stylesheet

APP_STYLE = app_stylesheet()


def make_card(object_name: str = "card") -> QFrame:
    card = QFrame()
    card.setObjectName(object_name)
    card.setFrameShape(QFrame.Shape.NoFrame)
    return card


def set_button_role(button: QPushButton, role: str = "secondary", compact: bool = False) -> QPushButton:
    button.setProperty("role", role)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(30 if compact else 34)
    return button
